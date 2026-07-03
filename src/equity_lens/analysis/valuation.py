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
              shares: float, exit_multiple: float = None,
              clamp_growth: bool = True) -> dict:
    """Per-share equity value from a 5-year FCF projection + terminal value.

    Growth fades linearly from the starting rate to terminal growth — the
    standard guard against extrapolating a hot streak forever.

    Terminal value is triangulated two ways, then averaged:
      - Gordon growth: terminal FCF grows at 2.5% forever. Punishes
        franchises with durable moats; treats Apple like a utility.
      - Exit multiple: the year-5 business is worth what comparable
        businesses trade at today (peer forward P/E on FCF as an earnings
        proxy). This is how industry potential enters the math — peers'
        pricing embeds the market's view of the industry's future.
    Averaging both is common sell-side practice: pure Gordon is too harsh
    on quality compounders, pure exit-multiple imports any peer bubble.
    """
    if clamp_growth:
        growth = min(growth if growth is not None else TERMINAL_GROWTH, GROWTH_CAP)
        growth = max(growth, TERMINAL_GROWTH)
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

    tv_gordon = projected[-1] * (1 + TERMINAL_GROWTH) / (coe - TERMINAL_GROWTH)
    terminal_values = [tv_gordon]
    if exit_multiple and exit_multiple > 0:
        terminal_values.append(projected[-1] * exit_multiple)
    terminal = sum(terminal_values) / len(terminal_values)

    pv_terminal = terminal / (1 + coe) ** PROJECTION_YEARS
    equity_value = pv + pv_terminal - (net_debt or 0)

    return {
        "per_share": equity_value / shares,
        "assumptions": {
            "fcf_base": fcf_base, "initial_growth": growth,
            "terminal_growth": TERMINAL_GROWTH, "cost_of_equity": coe,
            "exit_multiple": exit_multiple,
            "projection_years": PROJECTION_YEARS, "net_debt": net_debt,
        },
        "pv_explicit": pv, "pv_terminal": pv_terminal,
        "tv_gordon": tv_gordon,
        "tv_exit": projected[-1] * exit_multiple if exit_multiple else None,
        "terminal_share_of_value": pv_terminal / (pv + pv_terminal),
    }


def comps_value(eps_trailing: float, eps_forward: float, peer_multiples) -> dict:
    """Implied share price from peer-median P/E, trailing and forward.

    Median (not mean) so one crazy peer multiple can't skew the result.
    Forward comps capture where earnings are going, not just where they've
    been; when both views exist they are averaged.
    """
    implied, detail = [], {}
    pe_t = peer_multiples["trailing_pe"].dropna()
    if eps_trailing and eps_trailing > 0 and not pe_t.empty:
        implied.append(eps_trailing * pe_t.median())
        detail["trailing"] = {"eps": eps_trailing, "peer_median_pe": pe_t.median()}
    pe_f = peer_multiples["forward_pe"].dropna()
    if eps_forward and eps_forward > 0 and not pe_f.empty:
        implied.append(eps_forward * pe_f.median())
        detail["forward"] = {"eps": eps_forward, "peer_median_pe": pe_f.median()}
    if not implied:
        return {"per_share": None, "reason": "no positive EPS or peer P/E data"}
    return {
        "per_share": sum(implied) / len(implied),
        "assumptions": {**detail, "peers_used": list(peer_multiples.index)},
    }


def own_multiple_value(own_avg_pe: float, eps_forward: float,
                       eps_trailing: float) -> dict:
    """Implied price at the company's OWN historical average P/E.

    Peer comps ask "what if it were priced like peers?" — harsh on franchises
    that have always commanded a premium. This model asks "what if it were
    priced like its own history?", the standard street anchor for mature
    large caps. Forward EPS preferred (targets look ahead); trailing fallback.
    """
    eps = eps_forward or eps_trailing
    if not own_avg_pe or not eps or eps <= 0:
        return {"per_share": None, "reason": "no own-history P/E or positive EPS"}
    return {
        "per_share": own_avg_pe * eps,
        "assumptions": {"own_avg_pe_5y": own_avg_pe, "eps_used": eps,
                        "eps_basis": "forward" if eps_forward else "trailing"},
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
