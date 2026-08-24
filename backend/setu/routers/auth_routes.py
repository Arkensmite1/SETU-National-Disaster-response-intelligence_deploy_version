"""Auth routes — Section 8.2 onboarding + 21.3 RBAC.

OTP is MOCKED: no SMS provider is integrated, the code is returned by the API
for demo use only.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import db
from ..audit import record_audit
from ..auth import (check_otp, current_user, generate_otp, hash_password, make_token,
                    public_user, require_roles, verify_password)
from ..models import Location, Role, User, clean, now_utc

router = APIRouter(prefix="/api/auth", tags=["auth"])


class OtpRequest(BaseModel):
    mobile: str


class OtpVerify(BaseModel):
    mobile: str
    code: str
    name: Optional[str] = None
    ageGroup: Optional[str] = None
    preferredLanguage: Optional[str] = "en"
    emergencyContactName: Optional[str] = None
    emergencyContactPhone: Optional[str] = None
    accessibilityRequirements: List[str] = Field(default_factory=list)
    groupSize: Optional[int] = 1
    homeLocation: Optional[Location] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    ageGroup: Optional[str] = None
    preferredLanguage: Optional[str] = None
    emergencyContactName: Optional[str] = None
    emergencyContactPhone: Optional[str] = None
    accessibilityRequirements: Optional[List[str]] = None
    groupSize: Optional[int] = None
    homeLocation: Optional[Location] = None


class StaffCreate(BaseModel):
    name: str
    email: str
    password: str
    role: Role
    teamId: Optional[str] = None
    shelterId: Optional[str] = None
    ngoId: Optional[str] = None
    ngoName: Optional[str] = None


@router.post("/otp/request")
async def otp_request(payload: OtpRequest):
    mobile = payload.mobile.strip()
    if not mobile.isdigit() or len(mobile) < 10:
        raise HTTPException(status_code=400, detail="Enter a valid 10-digit mobile number")
    code = await generate_otp(mobile)
    return {
        "mobile": mobile,
        "otpSent": True,
        "mocked": True,
        "devOtp": code,   # MOCKED delivery — no SMS gateway configured
        "channelNote": "OTP delivery is MOCKED for this demo build (no SMS provider configured).",
        "expiresInMinutes": 10,
    }


@router.post("/otp/verify")
async def otp_verify(payload: OtpVerify, request: Request):
    if not await check_otp(payload.mobile.strip(), payload.code.strip()):
        raise HTTPException(status_code=401, detail="Incorrect or expired OTP")
    mobile = payload.mobile.strip()
    existing = await db.users.find_one({"mobile": mobile})
    if existing:
        updates: Dict[str, Any] = {"verified": True}
        for field in ("name", "ageGroup", "preferredLanguage", "emergencyContactName",
                      "emergencyContactPhone", "groupSize"):
            val = getattr(payload, field)
            if val:
                updates[field] = val
        if payload.accessibilityRequirements:
            updates["accessibilityRequirements"] = payload.accessibilityRequirements
        if payload.homeLocation:
            updates["homeLocation"] = payload.homeLocation.model_dump()
        await db.users.update_one({"userId": existing["userId"]}, {"$set": updates})
        user = clean(await db.users.find_one({"userId": existing["userId"]}))
        action = "CITIZEN_LOGIN"
    else:
        new_user = User(
            name=payload.name or f"Citizen {mobile[-4:]}", mobile=mobile, role=Role.USER,
            ageGroup=payload.ageGroup, preferredLanguage=payload.preferredLanguage or "en",
            emergencyContactName=payload.emergencyContactName,
            emergencyContactPhone=payload.emergencyContactPhone,
            accessibilityRequirements=payload.accessibilityRequirements or [],
            groupSize=payload.groupSize or 1,
            homeLocation=payload.homeLocation, verified=True,
        )
        doc = new_user.model_dump()
        doc["role"] = Role.USER.value
        if doc.get("homeLocation") and doc["homeLocation"].get("source"):
            doc["homeLocation"]["source"] = str(doc["homeLocation"]["source"])
        await db.users.insert_one(doc)
        user = clean(doc)
        action = "CITIZEN_REGISTER"
    await record_audit(action, "USER", user["userId"], None, {"mobile": mobile},
                       user=user, request=request)
    return {"token": make_token(user), "user": public_user(user)}


@router.post("/login")
async def login(payload: LoginRequest, request: Request):
    user = await db.users.find_one({"email": payload.email.strip().lower()})
    if not user:
        user = await db.users.find_one({"email": payload.email.strip()})
    if not user or not verify_password(payload.password, user.get("passwordHash")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    u = clean(user)
    await record_audit("STAFF_LOGIN", "USER", u["userId"], None, {"role": u.get("role")},
                       user=u, request=request)
    return {"token": make_token(u), "user": public_user(u)}


@router.get("/me")
async def me(user: Dict[str, Any] = Depends(current_user)):
    return public_user(user)


@router.patch("/profile")
async def update_profile(payload: ProfileUpdate, request: Request,
                         user: Dict[str, Any] = Depends(current_user)):
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if "homeLocation" in updates and updates["homeLocation"]:
        updates["homeLocation"]["source"] = str(updates["homeLocation"]["source"])
    if not updates:
        return public_user(user)
    old = {k: user.get(k) for k in updates}
    await db.users.update_one({"userId": user["userId"]}, {"$set": updates})
    await record_audit("PROFILE_UPDATE", "USER", user["userId"], old, updates,
                       user=user, request=request)
    return public_user(clean(await db.users.find_one({"userId": user["userId"]})))


class LocationUpdate(BaseModel):
    location: Location


@router.post("/location")
async def update_location(payload: LocationUpdate, user: Dict[str, Any] = Depends(current_user)):
    loc = payload.location.model_dump()
    loc["source"] = str(loc["source"])
    await db.users.update_one({"userId": user["userId"]}, {"$set": {"lastKnownLocation": loc}})
    return {"ok": True, "lastKnownLocation": loc,
            "approximate": payload.location.is_approximate()}


@router.post("/staff")
async def create_staff(payload: StaffCreate, request: Request,
                       admin: Dict[str, Any] = Depends(require_roles(Role.SUPER_ADMIN, Role.AUTHORITY))):
    email = payload.email.strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="A user with this email already exists")
    u = User(name=payload.name, email=email, role=payload.role,
             passwordHash=hash_password(payload.password), teamId=payload.teamId,
             shelterId=payload.shelterId, ngoId=payload.ngoId, ngoName=payload.ngoName,
             verified=True)
    doc = u.model_dump()
    doc["role"] = payload.role.value
    await db.users.insert_one(doc)
    await record_audit("STAFF_CREATE", "USER", doc["userId"], None,
                       {"email": email, "role": doc["role"]}, user=admin, request=request)
    return public_user(clean(doc))


@router.get("/roles")
async def roles():
    return {"roles": [r.value for r in Role],
            "citizenAuth": "MOBILE_OTP (mocked)", "staffAuth": "EMAIL_PASSWORD"}
