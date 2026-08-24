"""Unit tests for the Section 23 state machines (no network / DB required)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "setu_database")

from setu.state_machines import (DISASTER, IllegalTransition, RESOURCE, SHELTER, SOS, TEAM,
                                 derive_shelter_status)
from setu.priority import classify_priority


def test_disaster_happy_path():
    path = ["DETECTED", "MONITORING", "WARNING", "CONFIRMED", "ACTIVE", "RESPONSE",
            "RELIEF", "RECOVERY", "CLOSED"]
    for a, b in zip(path, path[1:]):
        assert DISASTER.assert_transition(a, b) == b


def test_disaster_illegal_transition_rejected():
    with pytest.raises(IllegalTransition):
        DISASTER.assert_transition("DETECTED", "CLOSED")
    with pytest.raises(IllegalTransition):
        DISASTER.assert_transition("CLOSED", "ACTIVE")


def test_sos_happy_path():
    path = ["CREATED", "RECEIVED", "VERIFIED", "PENDING", "ASSIGNED", "ACCEPTED",
            "EN_ROUTE", "ARRIVED", "RESCUING", "RESCUED", "COMPLETED"]
    for a, b in zip(path, path[1:]):
        assert SOS.assert_transition(a, b) == b


def test_sos_cannot_skip_states():
    with pytest.raises(IllegalTransition):
        SOS.assert_transition("CREATED", "RESCUED")
    with pytest.raises(IllegalTransition):
        SOS.assert_transition("PENDING", "EN_ROUTE")


def test_sos_branches_allowed_from_active_states():
    for state in ("RECEIVED", "PENDING", "ASSIGNED", "EN_ROUTE"):
        assert SOS.can(state, "CANCELLED_BY_USER")
        assert SOS.can(state, "DUPLICATE")
        assert SOS.can(state, "FALSE_ALARM")
    assert not SOS.can("COMPLETED", "DUPLICATE")


def test_user_not_found_is_not_terminal_and_leads_to_search():
    assert SOS.can("ARRIVED", "USER_NOT_FOUND")
    assert SOS.can("USER_NOT_FOUND", "SEARCHING")
    assert not SOS.is_terminal("USER_NOT_FOUND")


def test_team_machine():
    assert TEAM.can("AVAILABLE", "ASSIGNED")
    assert TEAM.can("ASSIGNED", "AVAILABLE")   # rejection / timeout release
    with pytest.raises(IllegalTransition):
        TEAM.assert_transition("AVAILABLE", "ON_SITE")


def test_shelter_states_and_derivation():
    assert derive_shelter_status(100, 0, "OPEN") == "OPEN"
    assert derive_shelter_status(100, 90, "OPEN") == "NEAR_CAPACITY"
    assert derive_shelter_status(100, 100, "OPEN") == "FULL"
    assert derive_shelter_status(100, 120, "FULL") == "OVER_CAPACITY"
    # CLOSED is a human decision and is never auto-overridden by occupancy math
    assert derive_shelter_status(100, 10, "CLOSED") == "CLOSED"
    assert SHELTER.can("FULL", "OVER_CAPACITY")


def test_resource_machine_discrepancy_reachable():
    path = ["REQUESTED", "APPROVED", "ALLOCATED", "DISPATCHED", "IN_TRANSIT",
            "DELIVERED", "RECEIVED", "DISTRIBUTED"]
    for a, b in zip(path, path[1:]):
        assert RESOURCE.assert_transition(a, b) == b
    assert RESOURCE.can("DELIVERED", "DISCREPANCY")
    with pytest.raises(IllegalTransition):
        RESOURCE.assert_transition("REQUESTED", "DISPATCHED")


def test_priority_triage():
    p1, reasons = classify_priority({"emergencyType": "DROWNING", "injuredCount": 2,
                                     "peopleCount": 3})
    assert p1 == "P1" and reasons
    p3, _ = classify_priority({"emergencyType": "INFO_REQUEST", "peopleCount": 1})
    assert p3 == "P3"
    # one SOS can represent many people — composition raises priority
    p2, _ = classify_priority({"emergencyType": "STRANDED", "peopleCount": 8,
                              "childrenCount": 2, "elderlyCount": 1})
    assert p2 in ("P1", "P2")
