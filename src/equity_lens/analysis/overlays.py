"""Analyst judgment overlays: dated, written adjustments for things the
mechanical engine refuses to price — unproven product cycles, pending
narratives, management change.

This is how "what hasn't happened yet" legitimately enters a valuation:
as an explicit, disclosed bet, never as silent engine tuning. The engine's
base target is always computed and reported alongside the adjusted one, so
the scorecard can grade the model and the judgment separately.

Overlays live in data/overlays.json, committed to git — every change is a
dated entry in the paper trail. Two types:

  target_pct — move the blended target by a percentage:
    {"date": "2026-07-03", "type": "target_pct", "value": 0.10,
     "rationale": "...", "review_by": "2026-10-30"}

  scenarios — probability-weighted target replaces the base:
    {"date": ..., "type": "scenarios", "rationale": ...,
     "scenarios": [{"name": "AI re-rating", "target": 280, "probability": 0.4},
                   {"name": "base", "target": 196, "probability": 0.6}]}
"""

import json
from pathlib import Path

OVERLAYS_PATH = Path(__file__).parents[3] / "data" / "overlays.json"


def load_overlays() -> dict:
    if not OVERLAYS_PATH.exists():
        return {}
    with open(OVERLAYS_PATH) as f:
        return json.load(f)


def apply(ticker: str, base_target: float) -> dict:
    """Apply a ticker's overlays to the engine's base target.

    Returns adjusted target plus the full overlay entries for disclosure.
    Overlays of type target_pct compound; a scenarios overlay replaces the
    target with its probability-weighted average (base engine value should
    be one of the scenarios if it deserves weight).
    """
    entries = load_overlays().get(ticker, [])
    if base_target is None or not entries:
        return {"adjusted_target": base_target, "overlays": entries}

    adjusted = base_target
    for e in entries:
        if e["type"] == "target_pct":
            adjusted *= 1 + e["value"]
        elif e["type"] == "scenarios":
            total_p = sum(s["probability"] for s in e["scenarios"])
            if abs(total_p - 1.0) > 0.01:
                continue  # malformed probabilities: skip, disclose nothing
            adjusted = sum(s["target"] * s["probability"] for s in e["scenarios"])
    return {"adjusted_target": adjusted, "overlays": entries}
