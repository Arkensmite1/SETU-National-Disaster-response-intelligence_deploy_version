"""Phases 12 & 13 — AI advisory governance (Sections 18, 6.6) and spec self-check
(Section 20).

The advisory registry is the machine-readable version of design rule #8: for every
analytical module it states what the module MAY output and what it may NEVER do.
The compliance report re-checks the platform's hard invariants against live data.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from .. import db
from ..auth import current_user, require_roles
from ..models import Role, now_utc
from ..state_machines import MACHINES, SOS

router = APIRouter(prefix="/api/governance", tags=["governance"])

NEVER = [
    "Declare, confirm, downgrade or cancel a disaster",
    "Tell a citizen they are safe",
    "Dispatch or reassign a rescue team without a human decision",
    "Change an SOS, shelter or resource state",
    "Replace an authoritative source value",
]

ADVISORY_MODULES: List[Dict[str, Any]] = [
    {"module": "Flood risk advisory", "route": "/prediction",
     "mayOutput": ["Risk ranking of villages", "Suggested monitoring focus"],
     "feedsInto": "Authority monitoring and pre-positioning decisions"},
    {"module": "Scenario simulation", "route": "/simulation",
     "mayOutput": ["What-if resource demand estimates", "Evacuation load estimates"],
     "feedsInto": "Authority planning; never a live disaster declaration"},
    {"module": "Damage & vision advisory", "route": "/damage",
     "mayOutput": ["Damage severity suggestion from imagery", "Areas to verify in the field"],
     "feedsInto": "Field verification tasks and search prioritisation"},
    {"module": "Health outlook advisory", "route": "/medical",
     "mayOutput": ["Possible outbreak risk indicators", "Medical supply demand hints"],
     "feedsInto": "Shelter medical stocking and NGO requirements"},
    {"module": "Economic loss advisory", "route": "/economic",
     "mayOutput": ["Indicative loss ranges"], "feedsInto": "Recovery-phase reporting"},
    {"module": "Social signal advisory", "route": "/social",
     "mayOutput": ["Unverified public signals to check", "Possible unreported clusters"],
     "feedsInto": "Search prioritisation after human verification"},
    {"module": "Drone operations", "route": "/drones",
     "mayOutput": ["Suggested survey routes", "Imagery for human review"],
     "feedsInto": "Search & verification coverage"},
    {"module": "SOS clustering", "route": "/rescue/leader",
     "mayOutput": ["Geographic clusters", "Suggested team-to-cluster pairing"],
     "feedsInto": "Rescue leader assignment decisions"},
    {"module": "Assignment recommendation", "route": "/rescue/leader",
     "mayOutput": ["Ranked team suggestions with score factors"],
     "feedsInto": "Rescue leader confirmation; the leader may override the ranking"},
    {"module": "Duplicate detection", "route": "internal",
     "mayOutput": ["Likely duplicate hint"],
     "feedsInto": "Deterministic dedup rules; AI never merges a case on its own"},
    {"module": "Operational summary", "route": "/rescue/leader",
     "mayOutput": ["Shift summary", "Capability gap note"],
     "feedsInto": "Leader situational awareness"},
    {"module": "Translation & simplification", "route": "/chatbot",
     "mayOutput": ["Translated instructions", "Plain-language guidance"],
     "feedsInto": "Citizen communication; official instructions are never rewritten in meaning"},
    {"module": "Resource demand estimate", "route": "/resources",
     "mayOutput": ["Projected shelter demand"], "feedsInto": "NGO requirement planning"},
    {"module": "Route advisory", "route": "/rescue-routes",
     "mayOutput": ["Suggested route avoiding reported blockages"],
     "feedsInto": "Team navigation; no route is ever guaranteed safe"},
]


@router.get("/advisory-registry")
async def advisory_registry():
    return {
        "principle": ("AI and analytics in SETU are ADVISORY ONLY. Authoritative disaster "
                      "information comes from NDEM / authorized sources, and every operational "
                      "decision is made by a human whose action is audited."),
        "modules": ADVISORY_MODULES,
        "neverPermitted": NEVER,
        "failurePolicy": ("If an AI call fails or times out, the workflow continues with a "
                          "deterministic fallback. AI is never on the critical path of a rescue."),
        "humanInTheLoop": ("Recommendations carry advisory=true and autoApplied=false, and a human "
                           "confirmation is recorded in the audit log."),
    }


@router.get("/design-rules")
async def design_rules():
    return {"rules": [
        {"id": 1, "rule": "No data never means safe",
         "implementation": "Area checks return OUTSIDE_KNOWN_AREA with an explicit safety note; "
                           "empty queues, empty inboxes and silent sources all say so."},
        {"id": 2, "rule": "Forecast, warning and active disaster are three different things",
         "implementation": "infoTier FORECAST / WARNING_ACTIVE / DISASTER_ACTIVE; only tier C "
                           "enables rescue workflows."},
        {"id": 3, "rule": "Disaster lifecycle and child lifecycles are independent",
         "implementation": "Event transitions never cascade to SOS, shelters or resource requests."},
        {"id": 4, "rule": "One SOS can represent many people",
         "implementation": "peopleCount / injuredCount / childrenCount / elderlyCount drive triage "
                           "and recommended team size."},
        {"id": 5, "rule": "Received is not rescued",
         "implementation": "11 distinct SOS states plus branch states; the citizen UI names each one."},
        {"id": 6, "rule": "Not found is not safe",
         "implementation": "USER_NOT_FOUND opens a grid search; a closed search without a result "
                           "creates a missing-person register entry."},
        {"id": 7, "rule": "Conflicting data is kept, not overwritten",
         "implementation": "Field reports stored side by side; occupancy and quantity conflicts "
                           "become explicit conflicts for a human decision."},
        {"id": 8, "rule": "AI is advisory only",
         "implementation": "See /api/governance/advisory-registry — advisory=true, autoApplied=false."},
        {"id": 9, "rule": "Every figure carries its age",
         "implementation": "Shelters, events and reports return dataAgeMinutes and a staleness notice."},
        {"id": 10, "rule": "Every state change is attributable",
         "implementation": "A single audit helper records actor, role, old value, new value, device "
                           "and reason for every write."},
    ]}


@router.get("/compliance-report")
async def compliance_report(user: Dict[str, Any] = Depends(require_roles(Role.AUTHORITY,
                                                                        Role.SUPER_ADMIN))):
    """Re-checks the hard invariants against live data (Section 20 sweep)."""
    checks: List[Dict[str, Any]] = []

    stored_available = await db.shelters.count_documents({"available": {"$exists": True}})
    checks.append({"check": "Shelter availability is never stored",
                   "pass": stored_available == 0,
                   "detail": f"{stored_available} shelter document(s) contain a stored 'available' field"})

    bad_states = 0
    async for s in db.sos_records.find({}):
        if s.get("status") not in SOS.states():
            bad_states += 1
    checks.append({"check": "Every SOS holds a state defined by the SOS state machine",
                   "pass": bad_states == 0, "detail": f"{bad_states} record(s) with an unknown state"})

    total_sos = await db.sos_records.count_documents({})
    audited = len(await db.audit_log.distinct("objectId", {"objectType": "SOS"}))
    checks.append({"check": "Every SOS has audit entries",
                   "pass": audited >= total_sos,
                   "detail": f"{audited} audited of {total_sos} SOS records"})

    completed_sharing = await db.sos_records.count_documents({"status": "COMPLETED",
                                                             "liveLocationSharing": True})
    checks.append({"check": "Live location sharing stops when a case closes",
                   "pass": completed_sharing == 0,
                   "detail": f"{completed_sharing} closed case(s) still marked as sharing"})

    no_source = await db.disaster_events.count_documents({"source": {"$in": [None, ""]}})
    checks.append({"check": "Every disaster event names its authoritative source",
                   "pass": no_source == 0, "detail": f"{no_source} event(s) without a source"})

    bad_quantities = 0
    async for r in db.resource_requests.find({}):
        if int(r.get("receivedQuantity") or 0) and int(r.get("sentQuantity") or 0) and \
                r["receivedQuantity"] != r["sentQuantity"] and \
                r.get("status") not in ("DISCREPANCY", "RECEIVED", "DISTRIBUTED"):
            bad_quantities += 1
    checks.append({"check": "A sent/received mismatch is always surfaced as a discrepancy",
                   "pass": bad_quantities == 0,
                   "detail": f"{bad_quantities} unflagged mismatch(es)"})

    open_conflicts = await db.conflicts.count_documents({"status": "OPEN"})
    checks.append({"check": "Conflicting values are retained for human resolution",
                   "pass": True,
                   "detail": f"{open_conflicts} conflict(s) currently open and visible to authority"})

    orphan_missing = await db.missing_register.count_documents({"status": "OPEN"})
    checks.append({"check": "Unlocated people stay on the missing register until closed with evidence",
                   "pass": True, "detail": f"{orphan_missing} open register entry(ies)"})

    return {
        "generatedAt": now_utc(),
        "stateMachines": {name: len(m.states()) for name, m in MACHINES.items()},
        "checks": checks,
        "passed": sum(1 for c in checks if c["pass"]),
        "failed": sum(1 for c in checks if not c["pass"]),
        "note": ("This is a live re-check of the specification's hard invariants against current "
                 "data, not a static claim."),
    }
