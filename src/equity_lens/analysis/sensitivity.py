"""Sensitivity analysis: how the target price moves when key assumptions move.

Standard in every institutional report. Purpose is honesty about
uncertainty: a target is the center of a range, and the grid shows which
assumptions actually drive it. Rows flex the return/growth assumption;
columns flex the discount rate.
"""

GROWTH_STEPS = [-0.02, -0.01, 0.0, 0.01, 0.02]   # +/- 2pp on growth or ROE
COE_STEPS = [-0.01, -0.005, 0.0, 0.005, 0.01]    # +/- 1pp on cost of equity


def build_grid(target_fn, base_x: float, base_coe: float,
               x_label: str) -> dict:
    """Target price over a grid of assumption shifts.

    target_fn(x, coe) -> blended per-share target (or None). base_x is the
    growth or ROE assumption being flexed.
    """
    rows = []
    for dx in GROWTH_STEPS:
        row = []
        for dc in COE_STEPS:
            try:
                row.append(target_fn(base_x + dx, base_coe + dc))
            except Exception:
                row.append(None)
        rows.append(row)
    return {
        "x_label": x_label,
        "x_values": [base_x + d for d in GROWTH_STEPS],
        "coe_values": [base_coe + d for d in COE_STEPS],
        "grid": rows,   # rows follow x_values, columns follow coe_values
    }
