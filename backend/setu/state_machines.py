"""Section 23 state machines as explicit, testable modules.

Rules enforced here:
* Illegal transitions raise IllegalTransition (mapped to HTTP 409 by routers).
* DisasterEvent / SOS / Shelter / Resource machines are INDEPENDENT — closing a
  disaster never cascade-closes children (design rule #3, spec 22.4).
* "received" != "rescued": every step is a distinct state (design rule #5).
"""
from typing import Dict, Set

from .models import DisasterStatus as D, ResourceStatus as R, SOSStatus as S
from .models import ShelterStatus as SH, TeamStatus as T


class IllegalTransition(Exception):
    def __init__(self, machine: str, current: str, target: str, allowed):
        self.machine, self.current, self.target = machine, current, target
        self.allowed = sorted(allowed)
        super().__init__(
            f"Illegal {machine} transition {current} -> {target}. Allowed: {self.allowed}"
        )


class StateMachine:
    def __init__(self, name: str, transitions: Dict[str, Set[str]],
                 always_allowed: Set[str] = frozenset(), terminal: Set[str] = frozenset()):
        self.name = name
        self.transitions = transitions
        self.always_allowed = set(always_allowed)
        self.terminal = set(terminal)

    def states(self):
        return set(self.transitions.keys())

    def allowed_from(self, current: str) -> Set[str]:
        base = set(self.transitions.get(current, set()))
        if current not in self.terminal:
            base |= self.always_allowed - {current}
        return base

    def can(self, current: str, target: str) -> bool:
        return target in self.allowed_from(current)

    def assert_transition(self, current: str, target: str) -> str:
        if current == target:
            return target
        if not self.can(current, target):
            raise IllegalTransition(self.name, current, target, self.allowed_from(current))
        return target

    def is_terminal(self, state: str) -> bool:
        return state in self.terminal


# --------------------------------------------------------------------------
# 23.1 / 23.6 DisasterEvent
# --------------------------------------------------------------------------
DISASTER = StateMachine(
    "DisasterEvent",
    {
        D.DETECTED.value: {D.MONITORING.value, D.WARNING.value, D.CONFIRMED.value, D.CANCELLED.value},
        D.MONITORING.value: {D.WARNING.value, D.CONFIRMED.value, D.CANCELLED.value, D.CLOSED.value},
        D.WARNING.value: {D.CONFIRMED.value, D.ACTIVE.value, D.CANCELLED.value},
        D.CONFIRMED.value: {D.ACTIVE.value, D.RESPONSE.value, D.CANCELLED.value},
        D.ACTIVE.value: {D.RESPONSE.value, D.RELIEF.value},
        D.RESPONSE.value: {D.RELIEF.value, D.RECOVERY.value},
        D.RELIEF.value: {D.RECOVERY.value},
        D.RECOVERY.value: {D.CLOSED.value},
        D.CLOSED.value: set(),
        D.CANCELLED.value: set(),
    },
    terminal={D.CLOSED.value, D.CANCELLED.value},
)

# Which disaster states put the platform into emergency mode (rescue enabled)
EMERGENCY_STATES = {D.CONFIRMED.value, D.ACTIVE.value, D.RESPONSE.value}


# --------------------------------------------------------------------------
# 23.2 / 23.6 SOS
# --------------------------------------------------------------------------
SOS_BRANCHES = {S.CANCELLED_BY_USER.value, S.DUPLICATE.value, S.FALSE_ALARM.value}

SOS = StateMachine(
    "SOS",
    {
        S.CREATED.value: {S.RECEIVED.value, S.QUEUED_OFFLINE.value},
        S.QUEUED_OFFLINE.value: {S.RECEIVED.value},
        S.RECEIVED.value: {S.VERIFIED.value},
        S.VERIFIED.value: {S.PENDING.value},
        S.PENDING.value: {S.ASSIGNED.value},
        S.ASSIGNED.value: {S.ACCEPTED.value, S.TIMEOUT.value, S.PENDING.value},
        S.TIMEOUT.value: {S.PENDING.value, S.ASSIGNED.value},
        S.ACCEPTED.value: {S.EN_ROUTE.value, S.PENDING.value},
        S.EN_ROUTE.value: {S.ARRIVED.value, S.PENDING.value},
        S.ARRIVED.value: {S.RESCUING.value, S.SEARCHING.value, S.USER_NOT_FOUND.value,
                          S.ALREADY_RESCUED.value},
        S.RESCUING.value: {S.RESCUED.value, S.USER_NOT_FOUND.value, S.SEARCHING.value},
        S.SEARCHING.value: {S.RESCUING.value, S.RESCUED.value, S.NOT_FOUND.value},
        S.USER_NOT_FOUND.value: {S.SEARCHING.value, S.NOT_FOUND.value, S.RESCUED.value},
        S.NOT_FOUND.value: {S.SEARCHING.value, S.COMPLETED.value},
        S.ALREADY_RESCUED.value: {S.COMPLETED.value},
        S.RESCUED.value: {S.COMPLETED.value},
        S.COMPLETED.value: set(),
        S.CANCELLED_BY_USER.value: set(),
        S.DUPLICATE.value: set(),
        S.FALSE_ALARM.value: {S.COMPLETED.value},
    },
    always_allowed=SOS_BRANCHES,
    terminal={S.COMPLETED.value, S.CANCELLED_BY_USER.value, S.DUPLICATE.value},
)

SOS_ACTIVE_STATES = [
    S.CREATED.value, S.QUEUED_OFFLINE.value, S.RECEIVED.value, S.VERIFIED.value,
    S.PENDING.value, S.ASSIGNED.value, S.TIMEOUT.value, S.ACCEPTED.value,
    S.EN_ROUTE.value, S.ARRIVED.value, S.RESCUING.value, S.SEARCHING.value,
    S.USER_NOT_FOUND.value, S.NOT_FOUND.value, S.RESCUED.value,
]

# States a rescue team member may set directly (Section 12.10)
TEAM_SETTABLE_SOS_STATES = {
    S.EN_ROUTE.value, S.ARRIVED.value, S.RESCUING.value, S.SEARCHING.value,
    S.RESCUED.value, S.USER_NOT_FOUND.value, S.NOT_FOUND.value,
    S.ALREADY_RESCUED.value, S.FALSE_ALARM.value,
}


# --------------------------------------------------------------------------
# 23.4 Team
# --------------------------------------------------------------------------
TEAM = StateMachine(
    "Team",
    {
        T.AVAILABLE.value: {T.ASSIGNED.value, T.OFFLINE.value},
        T.ASSIGNED.value: {T.ACCEPTED.value, T.AVAILABLE.value, T.OFFLINE.value},
        T.ACCEPTED.value: {T.EN_ROUTE.value, T.AVAILABLE.value},
        T.EN_ROUTE.value: {T.ON_SITE.value, T.AVAILABLE.value},
        T.ON_SITE.value: {T.RESCUING.value, T.SEARCHING.value, T.COMPLETED.value},
        T.RESCUING.value: {T.COMPLETED.value, T.SEARCHING.value},
        T.SEARCHING.value: {T.RESCUING.value, T.COMPLETED.value},
        T.COMPLETED.value: {T.AVAILABLE.value},
        T.OFFLINE.value: {T.AVAILABLE.value},
    },
)

SOS_TO_TEAM_STATE = {
    S.ASSIGNED.value: T.ASSIGNED.value,
    S.ACCEPTED.value: T.ACCEPTED.value,
    S.EN_ROUTE.value: T.EN_ROUTE.value,
    S.ARRIVED.value: T.ON_SITE.value,
    S.RESCUING.value: T.RESCUING.value,
    S.SEARCHING.value: T.SEARCHING.value,
    S.USER_NOT_FOUND.value: T.SEARCHING.value,
    S.RESCUED.value: T.COMPLETED.value,
    S.COMPLETED.value: T.AVAILABLE.value,
}


# --------------------------------------------------------------------------
# 23.3 Shelter
# --------------------------------------------------------------------------
SHELTER = StateMachine(
    "Shelter",
    {
        SH.OPEN.value: {SH.NEAR_CAPACITY.value, SH.FULL.value, SH.CLOSED.value},
        SH.NEAR_CAPACITY.value: {SH.OPEN.value, SH.FULL.value, SH.CLOSED.value},
        SH.FULL.value: {SH.OVER_CAPACITY.value, SH.NEAR_CAPACITY.value, SH.OPEN.value, SH.CLOSED.value},
        SH.OVER_CAPACITY.value: {SH.FULL.value, SH.NEAR_CAPACITY.value, SH.OPEN.value, SH.CLOSED.value},
        SH.CLOSED.value: {SH.OPEN.value},
    },
)


def derive_shelter_status(capacity: int, occupancy: int, current: str) -> str:
    """Occupancy-driven status. CLOSED is an explicit human decision and is never
    auto-overridden by occupancy math."""
    if current == SH.CLOSED.value:
        return current
    if capacity <= 0:
        return SH.FULL.value
    ratio = occupancy / capacity
    if occupancy > capacity:
        return SH.OVER_CAPACITY.value
    if occupancy == capacity:
        return SH.FULL.value
    if ratio >= 0.85:
        return SH.NEAR_CAPACITY.value
    return SH.OPEN.value


# --------------------------------------------------------------------------
# 23.5 Resource
# --------------------------------------------------------------------------
RESOURCE = StateMachine(
    "ResourceRequest",
    {
        R.REQUESTED.value: {R.APPROVED.value, R.REJECTED.value, R.CANCELLED.value},
        R.APPROVED.value: {R.ALLOCATED.value, R.CANCELLED.value},
        R.ALLOCATED.value: {R.DISPATCHED.value, R.CANCELLED.value},
        R.DISPATCHED.value: {R.IN_TRANSIT.value, R.DELAYED.value},
        R.IN_TRANSIT.value: {R.ARRIVED.value, R.DELIVERED.value, R.DELAYED.value},
        R.DELAYED.value: {R.IN_TRANSIT.value, R.ARRIVED.value, R.DELIVERED.value},
        R.ARRIVED.value: {R.DELIVERED.value, R.RECEIVED.value},
        R.DELIVERED.value: {R.RECEIVED.value, R.DISCREPANCY.value},
        R.RECEIVED.value: {R.DISTRIBUTED.value, R.DISCREPANCY.value},
        R.DISCREPANCY.value: {R.RECEIVED.value, R.DISTRIBUTED.value},
        R.DISTRIBUTED.value: set(),
        R.REJECTED.value: set(),
        R.CANCELLED.value: set(),
    },
    terminal={R.DISTRIBUTED.value, R.REJECTED.value, R.CANCELLED.value},
)

MACHINES = {
    "disaster": DISASTER,
    "sos": SOS,
    "team": TEAM,
    "shelter": SHELTER,
    "resource": RESOURCE,
}
