"""Section 22.8 / 16.4 — single audit-logging helper.

EVERY write to disaster_events / sos_records / teams / shelters /
resource_requests must go through `record_audit` or `audited_update` so the
timeline is reconstructable. No ad hoc logging elsewhere.
"""
from typing import Any, Dict, Optional

from fastapi import Request

from . import db
from .models import AuditEntry, clean, now_utc


def _actor(user: Optional[Dict[str, Any]]):
    if not user:
        return None, None
    return user.get("userId"), user.get("role")


async def record_audit(action: str, object_type: str, object_id: str,
                       old_value: Any = None, new_value: Any = None,
                       user: Optional[Dict[str, Any]] = None,
                       request: Optional[Request] = None,
                       note: Optional[str] = None) -> Dict[str, Any]:
    uid, role = _actor(user)
    entry = AuditEntry(
        user=uid, userRole=role, action=action, objectType=object_type,
        objectId=object_id, oldValue=old_value, newValue=new_value, note=note,
        device=(request.headers.get("user-agent") if request else None),
        ip=(request.client.host if request and request.client else None),
    )
    doc = entry.model_dump()
    await db.audit_log.insert_one(doc)
    return clean(doc)


async def audited_update(collection, key: Dict[str, Any], updates: Dict[str, Any],
                        action: str, object_type: str, object_id: str,
                        user: Optional[Dict[str, Any]] = None,
                        request: Optional[Request] = None,
                        note: Optional[str] = None,
                        extra_ops: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Update a document and audit exactly the fields that changed."""
    before = await collection.find_one(key)
    if not before:
        return None
    old_slice = {k: before.get(k) for k in updates.keys()}
    ops: Dict[str, Any] = {"$set": {**updates}}
    if extra_ops:
        for op, payload in extra_ops.items():
            ops.setdefault(op, {}).update(payload)
    await collection.update_one(key, ops)
    after = await collection.find_one(key)
    await record_audit(action, object_type, object_id, old_slice, updates,
                       user=user, request=request, note=note)
    return clean(after) if after else None


async def timeline(object_type: str, object_id: str, limit: int = 200):
    cur = db.audit_log.find({"objectType": object_type, "objectId": object_id}).sort("timestamp", 1).limit(limit)
    return [clean(d) async for d in cur]


async def recent(limit: int = 100, object_type: Optional[str] = None,
                 action: Optional[str] = None, user_id: Optional[str] = None):
    q: Dict[str, Any] = {}
    if object_type:
        q["objectType"] = object_type
    if action:
        q["action"] = action
    if user_id:
        q["user"] = user_id
    cur = db.audit_log.find(q).sort("timestamp", -1).limit(limit)
    return [clean(d) async for d in cur]


def touch() -> Dict[str, Any]:
    return {"updatedAt": now_utc()}
