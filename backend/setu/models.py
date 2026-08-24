"""SETU data model — spec Section 22 + enums for Section 23 state machines.

Hard rules encoded here:
* Location is always {latitude, longitude, accuracy, timestamp, source} (22.2) —
  never a bare lat/lng pair.
* Shelter stores capacity + occupancy only; `available` is DERIVED on read (22.6).
* ResourceRequest keeps requested/approved/allocated/sent/received as five
  independent fields that never overwrite each other (22.7).
* DisasterEvent status and child SOS/Shelter/Resource status are independent (22.4).
"""
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if isinstance(dt, datetime) else dt


# --------------------------------------------------------------------------
# Roles (Section 4 / 21.3)
# --------------------------------------------------------------------------
class Role(str, Enum):
    USER = "USER"                    # Citizen
    RESCUE_LEADER = "RESCUE_LEADER"
    RESCUE_MEMBER = "RESCUE_MEMBER"
    SHELTER_ADMIN = "SHELTER_ADMIN"
    NGO_ADMIN = "NGO_ADMIN"
    AUTHORITY = "AUTHORITY"
    SUPER_ADMIN = "SUPER_ADMIN"


ADMIN_ROLES = {Role.AUTHORITY.value, Role.SUPER_ADMIN.value}
RESCUE_ROLES = {Role.RESCUE_LEADER.value, Role.RESCUE_MEMBER.value}


# --------------------------------------------------------------------------
# Section 5.2 — three tiers of disaster information (never conflated)
# --------------------------------------------------------------------------
class InfoTier(str, Enum):
    FORECAST = "FORECAST"                # A - may happen. No rescue trigger.
    WARNING_ACTIVE = "WARNING_ACTIVE"    # B - significant risk. Prep only.
    DISASTER_ACTIVE = "DISASTER_ACTIVE"  # C - occurring/confirmed. Triggers rescue.


class DisasterType(str, Enum):
    FLOOD = "FLOOD"
    EARTHQUAKE = "EARTHQUAKE"
    CYCLONE = "CYCLONE"
    LIGHTNING = "LIGHTNING"
    FOREST_FIRE = "FOREST_FIRE"
    LANDSLIDE = "LANDSLIDE"
    TSUNAMI = "TSUNAMI"
    HEATWAVE = "HEATWAVE"
    OTHER = "OTHER"


class Severity(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class DisasterStatus(str, Enum):
    DETECTED = "DETECTED"
    MONITORING = "MONITORING"
    WARNING = "WARNING"
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    RESPONSE = "RESPONSE"
    RELIEF = "RELIEF"
    RECOVERY = "RECOVERY"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class SOSStatus(str, Enum):
    CREATED = "CREATED"
    QUEUED_OFFLINE = "QUEUED_OFFLINE"
    RECEIVED = "RECEIVED"
    VERIFIED = "VERIFIED"
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    ACCEPTED = "ACCEPTED"
    EN_ROUTE = "EN_ROUTE"
    ARRIVED = "ARRIVED"
    RESCUING = "RESCUING"
    SEARCHING = "SEARCHING"
    RESCUED = "RESCUED"
    COMPLETED = "COMPLETED"
    # branches
    TIMEOUT = "TIMEOUT"
    CANCELLED_BY_USER = "CANCELLED_BY_USER"
    DUPLICATE = "DUPLICATE"
    FALSE_ALARM = "FALSE_ALARM"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    NOT_FOUND = "NOT_FOUND"
    ALREADY_RESCUED = "ALREADY_RESCUED"


class TeamStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    ASSIGNED = "ASSIGNED"
    ACCEPTED = "ACCEPTED"
    EN_ROUTE = "EN_ROUTE"
    ON_SITE = "ON_SITE"
    RESCUING = "RESCUING"
    SEARCHING = "SEARCHING"
    COMPLETED = "COMPLETED"
    OFFLINE = "OFFLINE"


class ShelterStatus(str, Enum):
    OPEN = "OPEN"
    NEAR_CAPACITY = "NEAR_CAPACITY"
    FULL = "FULL"
    OVER_CAPACITY = "OVER_CAPACITY"
    CLOSED = "CLOSED"


class ResourceStatus(str, Enum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    ALLOCATED = "ALLOCATED"
    DISPATCHED = "DISPATCHED"
    IN_TRANSIT = "IN_TRANSIT"
    DELAYED = "DELAYED"
    ARRIVED = "ARRIVED"
    DELIVERED = "DELIVERED"
    RECEIVED = "RECEIVED"
    DISTRIBUTED = "DISTRIBUTED"
    DISCREPANCY = "DISCREPANCY"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class LocationSource(str, Enum):
    """Section 11.5 fallback chain — GPS unavailable != user unavailable."""
    GPS = "GPS"
    NETWORK = "NETWORK"
    LAST_KNOWN = "LAST_KNOWN"
    MANUAL = "MANUAL"
    LANDMARK = "LANDMARK"


class NetworkMode(str, Enum):
    FULL = "FULL"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


# --------------------------------------------------------------------------
# Section 22.2 — Location (embedded everywhere, never a top-level collection)
# --------------------------------------------------------------------------
class Location(BaseModel):
    latitude: float
    longitude: float
    accuracy: Optional[float] = None          # metres; None => unknown quality
    timestamp: datetime = Field(default_factory=now_utc)
    source: LocationSource = LocationSource.GPS
    landmark: Optional[str] = None            # used when source == LANDMARK

    def is_approximate(self) -> bool:
        if self.source in (LocationSource.MANUAL, LocationSource.LANDMARK,
                           LocationSource.LAST_KNOWN, LocationSource.NETWORK):
            return True
        return self.accuracy is None or self.accuracy > 100


# --------------------------------------------------------------------------
# Section 22.1 — DisasterEvent
# --------------------------------------------------------------------------
class DisasterEvent(BaseModel):
    eventId: str = Field(default_factory=lambda: f"EVT-{uuid.uuid4().hex[:10].upper()}")
    source: str = "NDEM / authorized disaster-information integration"
    sourceReference: Optional[str] = None
    disasterType: DisasterType = DisasterType.FLOOD
    severity: Severity = Severity.MODERATE
    infoTier: InfoTier = InfoTier.FORECAST
    status: DisasterStatus = DisasterStatus.DETECTED
    title: str = ""
    region: Optional[str] = None
    issuedAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)
    validFrom: Optional[datetime] = None
    validUntil: Optional[datetime] = None
    affectedArea: Optional[Dict[str, Any]] = None   # GeoJSON Polygon
    zones: List[Dict[str, Any]] = Field(default_factory=list)  # 6.5 Red/Orange/Yellow/Green
    confidence: Optional[float] = None
    qualityMetadata: Dict[str, Any] = Field(default_factory=dict)
    instructions: List[str] = Field(default_factory=list)
    version: int = 1
    experimental: bool = False   # e.g. landslide forecast — never present as certainty
    history: List[Dict[str, Any]] = Field(default_factory=list)  # 20.7 version history


# --------------------------------------------------------------------------
# Section 22.3 — SOS
# --------------------------------------------------------------------------
class SOSRecord(BaseModel):
    sosId: str = Field(default_factory=lambda: f"SOS-{uuid.uuid4().hex[:10].upper()}")
    userId: str
    eventId: Optional[str] = None
    disasterType: DisasterType = DisasterType.OTHER
    createdAt: datetime = Field(default_factory=now_utc)          # server receipt time
    clientCreatedAt: Optional[datetime] = None                    # original local time (offline queue)
    uploadedAt: Optional[datetime] = None
    origin: Location                                              # first known location, immutable
    lastKnown: Optional[Location] = None                          # updated if user moves
    peopleCount: int = 1
    injuredCount: int = 0
    childrenCount: int = 0
    elderlyCount: int = 0
    emergencyType: str = "TRAPPED"
    description: Optional[str] = None
    networkStatus: NetworkMode = NetworkMode.FULL
    batteryStatus: Optional[int] = None
    status: SOSStatus = SOSStatus.CREATED
    priority: str = "P2"          # operational triage only — never a medical diagnosis
    priorityReasons: List[str] = Field(default_factory=list)
    assignedTeamId: Optional[str] = None
    assignmentHistory: List[Dict[str, Any]] = Field(default_factory=list)
    retryCount: int = 0
    duplicateOf: Optional[str] = None
    clusterId: Optional[str] = None
    photoBase64: Optional[str] = None
    voiceNoteBase64: Optional[str] = None
    landmark: Optional[str] = None
    accessibilityRequirement: Optional[str] = None
    contactName: Optional[str] = None
    contactPhone: Optional[str] = None
    acknowledgedAt: Optional[datetime] = None
    completionReport: Optional[Dict[str, Any]] = None
    liveLocationSharing: bool = True    # 21.2 — stops on COMPLETED
    updatedAt: datetime = Field(default_factory=now_utc)


# --------------------------------------------------------------------------
# Section 22.5 — Team
# --------------------------------------------------------------------------
class Team(BaseModel):
    teamId: str = Field(default_factory=lambda: f"TEAM-{uuid.uuid4().hex[:6].upper()}")
    name: str
    leaderUserId: Optional[str] = None
    memberUserIds: List[str] = Field(default_factory=list)
    memberNames: List[str] = Field(default_factory=list)
    currentLocation: Optional[Location] = None
    status: TeamStatus = TeamStatus.AVAILABLE
    vehicle: str = "BOAT"
    equipment: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    maxOperationalCapacity: int = 10
    communicationStatus: str = "ONLINE"
    activeSosId: Optional[str] = None
    workload: int = 0
    region: Optional[str] = None
    updatedAt: datetime = Field(default_factory=now_utc)


# --------------------------------------------------------------------------
# Section 22.6 — Shelter (available is derived, never stored)
# --------------------------------------------------------------------------
class Shelter(BaseModel):
    shelterId: str = Field(default_factory=lambda: f"SH-{uuid.uuid4().hex[:6].upper()}")
    name: str
    adminUserId: Optional[str] = None
    location: Location
    capacity: int = 100
    occupancy: int = 0
    foodStatus: str = "ADEQUATE"
    waterStatus: str = "ADEQUATE"
    medicalStatus: str = "BASIC"
    status: ShelterStatus = ShelterStatus.OPEN
    facilities: List[str] = Field(default_factory=list)
    contactPhone: Optional[str] = None
    region: Optional[str] = None
    lastUpdated: datetime = Field(default_factory=now_utc)
    occupancyConflict: Optional[Dict[str, Any]] = None  # 16.3 never silently overwrite


# --------------------------------------------------------------------------
# Section 22.7 — ResourceRequest
# --------------------------------------------------------------------------
class ResourceRequest(BaseModel):
    requestId: str = Field(default_factory=lambda: f"REQ-{uuid.uuid4().hex[:8].upper()}")
    shelterId: Optional[str] = None
    eventId: Optional[str] = None
    category: str = "FOOD"
    unit: str = "packets"
    requestedQuantity: int = 0
    approvedQuantity: int = 0
    allocatedQuantity: int = 0
    sentQuantity: int = 0
    receivedQuantity: int = 0
    status: ResourceStatus = ResourceStatus.REQUESTED
    ngoId: Optional[str] = None
    ngoName: Optional[str] = None
    eta: Optional[datetime] = None
    delayReason: Optional[str] = None
    discrepancy: Optional[Dict[str, Any]] = None
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)


# --------------------------------------------------------------------------
# Section 22.8 — AuditLog
# --------------------------------------------------------------------------
class AuditEntry(BaseModel):
    auditId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user: Optional[str] = None
    userRole: Optional[str] = None
    action: str
    timestamp: datetime = Field(default_factory=now_utc)
    objectType: str
    objectId: str
    oldValue: Any = None
    newValue: Any = None
    device: Optional[str] = None
    ip: Optional[str] = None
    note: Optional[str] = None


# --------------------------------------------------------------------------
# Users (Section 8.2 onboarding fields + role)
# --------------------------------------------------------------------------
class User(BaseModel):
    userId: str = Field(default_factory=lambda: f"USR-{uuid.uuid4().hex[:10].upper()}")
    name: str = ""
    mobile: Optional[str] = None
    email: Optional[str] = None
    passwordHash: Optional[str] = None
    role: Role = Role.USER
    ageGroup: Optional[str] = None
    preferredLanguage: str = "en"
    emergencyContactName: Optional[str] = None
    emergencyContactPhone: Optional[str] = None
    accessibilityRequirements: List[str] = Field(default_factory=list)
    groupSize: int = 1
    homeLocation: Optional[Location] = None
    lastKnownLocation: Optional[Location] = None
    teamId: Optional[str] = None
    shelterId: Optional[str] = None
    ngoId: Optional[str] = None
    ngoName: Optional[str] = None
    verified: bool = False
    createdAt: datetime = Field(default_factory=now_utc)


# --------------------------------------------------------------------------
# Section 13 — Search & verification records
# --------------------------------------------------------------------------
class SearchOperation(BaseModel):
    searchId: str = Field(default_factory=lambda: f"SRCH-{uuid.uuid4().hex[:8].upper()}")
    eventId: Optional[str] = None
    sosId: Optional[str] = None
    teamId: Optional[str] = None
    areaDescription: str = ""
    gridCells: List[Dict[str, Any]] = Field(default_factory=list)
    startedAt: datetime = Field(default_factory=now_utc)
    endedAt: Optional[datetime] = None
    peopleFound: int = 0
    peopleMissing: int = 0
    observations: Optional[str] = None
    status: str = "IN_PROGRESS"


class FieldIncident(BaseModel):
    incidentId: str = Field(default_factory=lambda: f"FI-{uuid.uuid4().hex[:8].upper()}")
    eventId: Optional[str] = None
    teamId: Optional[str] = None
    location: Location
    unknownPersons: int = 1
    condition: str = "UNKNOWN"
    transportRequired: bool = False
    notes: Optional[str] = None
    createdAt: datetime = Field(default_factory=now_utc)


def shelter_view(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Derive `available` on read (22.6) + staleness metadata (rule 9)."""
    d = {k: v for k, v in doc.items() if k != "_id"}
    cap = int(d.get("capacity") or 0)
    occ = int(d.get("occupancy") or 0)
    d["available"] = max(cap - occ, 0)
    d["overflow"] = max(occ - cap, 0)
    last = d.get("lastUpdated")
    if isinstance(last, datetime):
        age_min = (now_utc() - last.replace(tzinfo=last.tzinfo or timezone.utc)).total_seconds() / 60
        d["dataAgeMinutes"] = round(age_min, 1)
        d["stale"] = age_min > 60
        d["stalenessNotice"] = (
            f"Last updated {int(age_min)} min ago — information may be outdated"
            if age_min > 60 else f"Last updated {int(age_min)} min ago"
        )
    return d


def loc_doc(location):
    """Serialise an embedded Location for Mongo (enum -> plain str, keep datetime)."""
    if location is None:
        return None
    d = location.model_dump() if hasattr(location, "model_dump") else dict(location)
    src = d.get("source")
    d["source"] = str(src.value if hasattr(src, "value") else src)
    return d


def clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Strip Mongo _id (never expose ObjectId)."""
    return {k: v for k, v in doc.items() if k != "_id"}
