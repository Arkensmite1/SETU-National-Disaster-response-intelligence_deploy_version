"""Section 11.3 — SOS priority classification (OPERATIONAL TRIAGE ONLY).

This is not a medical diagnosis and is never presented as one. It is a
deterministic, auditable, server-side ranking used to order the rescue queue.
AI is never the source of a priority decision (design rule #8) — it may only
suggest a re-ordering that a human leader confirms.
"""
from typing import Any, Dict, List, Tuple

P1_EMERGENCIES = {"DROWNING", "TRAPPED_WATER_RISING", "MEDICAL_CRITICAL", "BUILDING_COLLAPSE",
                  "UNCONSCIOUS", "FIRE"}
P2_EMERGENCIES = {"TRAPPED", "STRANDED", "INJURED", "NO_FOOD_WATER", "EVACUATION_NEEDED"}


def classify_priority(payload: Dict[str, Any]) -> Tuple[str, List[str]]:
    reasons: List[str] = []
    score = 0
    etype = (payload.get("emergencyType") or "").upper()
    injured = int(payload.get("injuredCount") or 0)
    people = int(payload.get("peopleCount") or 1)
    children = int(payload.get("childrenCount") or 0)
    elderly = int(payload.get("elderlyCount") or 0)
    accessibility = payload.get("accessibilityRequirement")
    severity = (payload.get("eventSeverity") or "").upper()

    if etype in P1_EMERGENCIES:
        score += 60
        reasons.append(f"Life-threatening emergency type: {etype}")
    elif etype in P2_EMERGENCIES:
        score += 30
        reasons.append(f"Urgent emergency type: {etype}")
    else:
        score += 10
        reasons.append("General assistance request")

    if injured > 0:
        score += 20 + min(injured, 5) * 4
        reasons.append(f"{injured} injured person(s) reported")
    if people > 5:
        score += 10
        reasons.append(f"Large group: {people} people in one SOS record")
    if children > 0:
        score += 10
        reasons.append(f"{children} child(ren) present")
    if elderly > 0:
        score += 10
        reasons.append(f"{elderly} elderly person(s) present")
    if accessibility:
        score += 10
        reasons.append(f"Accessibility requirement: {accessibility}")
    if severity in ("HIGH", "EXTREME"):
        score += 10
        reasons.append(f"Parent event severity {severity}")
    battery = payload.get("batteryStatus")
    if isinstance(battery, int) and battery <= 10:
        score += 5
        reasons.append(f"Device battery critical ({battery}%) — contact may be lost")

    priority = "P1" if score >= 70 else ("P2" if score >= 35 else "P3")
    return priority, reasons


def recommended_team_size(payload: Dict[str, Any]) -> int:
    """Section 11.8 — multi-victim SOS feeds team-size recommendation."""
    people = int(payload.get("peopleCount") or 1)
    injured = int(payload.get("injuredCount") or 0)
    base = 2 + (people // 4)
    return min(base + (1 if injured else 0), 12)


PRIORITY_ORDER = {"P1": 0, "P2": 1, "P3": 2}
