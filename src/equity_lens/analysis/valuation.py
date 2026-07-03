"""Valuation models. Every number is computed; assumptions are explicit
and returned alongside results so reports can disclose them.

Three methodologies, matched to business model (see universe.py):

1. DCF (dcf_value) — for operating companies. Projects free cash flow,
   discounts at WACC, adds a Gordon-growth terminal value. Answers: "what
   are all future cash flows worth today?"

2. Comparables (comps_value) — market-relative check. Applies the peer
   median P/E to the company's earnings. Answers: "what would this earn
   stream be worth if priced like its peers?"

3. Excess returns / justified P/B (bank_value, holdco_value) — for banks
   and financial holdcos, where deposits/float are raw material rather than
   financing, so enterprise FCF is meaningless. Uses the single-stage
   residual income shortcut: fair P/B = (ROE - g) / (CoE - g). A bank
   earning exactly its cost of equity is worth book; more is worth a
   premium, less a discount.
"""

EQUITY_RISK_PREMIUM = 0.05   # long-run US ERP, standard sell-side assumption
TERMINAL_GROWTH = 0.025      # ~long-run nominal GDP floor
PROJECTION_YEARS = 5
DEFAULT_BETA = 1.0
GROWTH_CAP = 0.15            # cap projected FCF growth; past hypergrowth doesn't annuitize


def cost_of_equity(risk_free: float, beta: float) -> float:
    """CAPM: risk-free rate plus beta times the equity risk premium."""
    return risk_free + (beta if beta is not None else DEFAULT_BETA) * EQUITY_RISK_PREMIUM


def dcf_value(fcf_base: float, growth: float, coe: float, net_debt: float,
              shares: float) -> dict:
    """Per-share equity value from a 5-year FCF projection + terminal value.

    Growth fades linearly from the starting rate to terminal growth — the
    standard guard against extrapolating a hot streak forever. Discounting
    uses cost of equity (FCF here is a proxy for equity holders' cash flow);
    net debt is then subtracted to move from operating value to equity value.
    """
    growth = min(growth if growth is not None else TERMINAL_GROWTH, GROWTH_CAP)
    if fcf_base is None or fcf_base <= 0 or shares in (None, 0):
        return {"per_share": None, "reason": "no positive FCF base or share count"}

    pv, fcf = 0.0, fcf_base
    fades = [growth + (TERMINAL_GROWTH - growth) * t / (PROJECTION_YEARS - 1)
             for t in range(PROJECTION_YEARS)]
    projected = []
    for t, g in enumerate(fades, start=1):
        fcf *= (1 + g)
        projected.append(fcf)
        pv += fcf / (1 + coe) ** t

    terminal = projected[-1] * (1 + TERMINAL_GROWTH) / (coe - TERMINAL_GROWTH)
    pv_terminal = terminal / (1 + coe) ** PROJECTION_YEARS
    equity_value = pv + pv_terminal - (net_debt or 0)

    return {
        "per_share": equity_value / shares,
        "assumptions": {
            "fcf_base": fcf_base, "initial_growth": growth,
            "terminal_growth": TERMINAL_GROWTH, "cost_of_equity": coe,
            "projection_years": PROJECTION_YEARS, "net_debt": net_debt,
        },
        "pv_explicit": pv, "pv_terminal": pv_terminal,
        "terminal_share_of_value": pv_terminal / (pv + pv_terminal),
    }


def comps_value(eps: float, peer_multiples) -> dict:
    """Implied share price at the peer-median trailing P/E.

    Median (not mean) so one crazy peer multiple can't skew the result.
    """
    pe = peer_multiples["trailing_pe"].dropna()
    if eps is None or eps <= 0 or pe.empty:
        return {"per_share": None, "reason": "no positive EPS or peer P/E data"}
    return {
        "per_share": eps * pe.median(),
        "assumptions": {"eps": eps, "peer_median_pe": pe.median(),
                        "peers_used": list(pe.index)},
    }


def justified_pb_value(book_per_share: float, roe: float, coe: float,
                       growth: float = TERMINAL_GROWTH) -> dict:
    """Fair value from the justified price-to-book multiple.

    fair P/B = (ROE - g) / (CoE - g). Standard for banks and financial
    holdcos. ROE is normalized (multi-year average) by the caller so one
    good or bad year doesn't set the multiple.
    """
    if not book_per_share or roe is None or coe - growth <= 0:
        return {"per_share": None, "reason": "missing book value or ROE"}
    fair_pb = max((roe - growth) / (coe - growth), 0.0)
    return {
        "per_share": book_per_share * fair_pb,
        "assumptions": {"book_per_share": book_per_share, "normalized_roe": roe,
                        "cost_of_equity": coe, "growth": growth,
                        "fair_pb_multiple": fair_pb},
    }


def make_rating(price: float, target: float) -> dict:
    """Rating from upside to blended target: Buy > +10%, Sell < -10%."""
    if price in (None, 0) or target is None:
        return {"rating": "NR", "upside": None}
    upside = target / price - 1
    rating = "BUY" if upside > 0.10 else ("SELL" if upside < -0.10 else "HOLD")
    return {"rating": rating, "upside": upside}
