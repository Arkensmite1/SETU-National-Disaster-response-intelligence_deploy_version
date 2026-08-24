"""AI = ADVISORY ONLY (spec 6.6 / design rule #8).

Every function here returns a recommendation object carrying
`advisory: True` and `requiresHumanConfirmation: True`. Nothing in this module
is ever allowed to mutate a disaster, SOS, shelter or resource state, and AI
failure must never block an operational flow — callers get a deterministic
fallback instead.
"""
import logging
from typing import Any, Dict, List

log = logging.getLogger("setu.advisory")

ADVISORY_SYSTEM = (
    "You are an ADVISORY assistant inside SETU, India's disaster response coordination "
    "platform. You never declare, confirm, cancel or override a disaster, warning or "
    "safety decision — authoritative disaster information comes only from NDEM / "
    "authorized sources and human authorities. Your only permitted outputs are: "
    "summaries, translations, prioritisation suggestions, duplicate detection hints, "
    "clustering suggestions, resource-demand estimates, route suggestions, anomaly "
    "flags and operational summaries. Always phrase output as a recommendation for a "
    "human decision-maker to confirm. Be terse and operational."
)


def _wrap(kind: str, text: str, fallback_used: bool = False) -> Dict[str, Any]:
    return {
        "kind": kind,
        "advisory": True,
        "requiresHumanConfirmation": True,
        "autoApplied": False,
        "text": text,
        "fallbackUsed": fallback_used,
        "disclaimer": "AI advisory only — a human must confirm before any action is taken.",
    }


async def _ask(prompt: str) -> str:
    import ai_service  # imported lazily so AI outages can never break imports
    return await ai_service.generate_text(prompt, system=ADVISORY_SYSTEM)


async def queue_summary(sos_list: List[Dict[str, Any]], teams: List[Dict[str, Any]]) -> Dict[str, Any]:
    deterministic = (
        f"{len(sos_list)} active SOS records ( "
        f"P1: {sum(1 for s in sos_list if s.get('priority') == 'P1')}, "
        f"P2: {sum(1 for s in sos_list if s.get('priority') == 'P2')}, "
        f"P3: {sum(1 for s in sos_list if s.get('priority') == 'P3')} ), "
        f"{sum(1 for t in teams if t.get('status') == 'AVAILABLE')} of {len(teams)} teams available."
    )
    lines = [
        f"- {s.get('sosId')} | {s.get('priority')} | {s.get('status')} | "
        f"{s.get('emergencyType')} | people={s.get('peopleCount')} injured={s.get('injuredCount')}"
        for s in sos_list[:40]
    ]
    team_lines = [
        f"- {t.get('teamId')} {t.get('name')} | {t.get('status')} | "
        f"caps={','.join(t.get('capabilities') or [])}" for t in teams[:20]
    ]
    prompt = (
        "Write a 4-6 line operational shift summary for a rescue leader. "
        "Highlight the most urgent unassigned cases and any capability gap. "
        "Do not invent facts.\n\nACTIVE SOS:\n" + "\n".join(lines) +
        "\n\nTEAMS:\n" + "\n".join(team_lines)
    )
    try:
        return _wrap("QUEUE_SUMMARY", await _ask(prompt))
    except Exception as exc:  # AI failure must never block operations
        log.warning("advisory queue_summary failed: %s", exc)
        return _wrap("QUEUE_SUMMARY", deterministic, fallback_used=True)


async def cluster_naming(clusters: List[Dict[str, Any]]) -> Dict[str, Any]:
    desc = [
        f"- cluster {c['clusterId']}: {c['sosCount']} SOS, centre "
        f"({c['centre']['latitude']:.4f}, {c['centre']['longitude']:.4f}), "
        f"top priority {c['topPriority']}, people {c['peopleCount']}"
        for c in clusters
    ]
    prompt = (
        "For each SOS cluster below suggest a short operational name and one line "
        "on why it should be prioritised or deprioritised. The rescue leader will "
        "confirm assignments.\n" + "\n".join(desc)
    )
    try:
        return _wrap("CLUSTER_ADVICE", await _ask(prompt))
    except Exception as exc:
        log.warning("advisory cluster_naming failed: %s", exc)
        return _wrap("CLUSTER_ADVICE",
                     "; ".join(f"{c['clusterId']}: {c['sosCount']} SOS, top {c['topPriority']}"
                               for c in clusters), fallback_used=True)


async def duplicate_hint(candidate: Dict[str, Any], existing: List[Dict[str, Any]]) -> Dict[str, Any]:
    prompt = (
        "Assess whether the new SOS is likely a duplicate of any listed existing SOS. "
        "Answer as: LIKELY_DUPLICATE_OF <id> or DISTINCT, plus one short reason. "
        "A human confirms the outcome.\n\nNEW: " + str(candidate) +
        "\n\nEXISTING:\n" + "\n".join(str(e) for e in existing[:10])
    )
    try:
        return _wrap("DUPLICATE_HINT", await _ask(prompt))
    except Exception as exc:
        log.warning("advisory duplicate_hint failed: %s", exc)
        return _wrap("DUPLICATE_HINT", "AI unavailable — deterministic dedup rules applied instead.",
                     fallback_used=True)
