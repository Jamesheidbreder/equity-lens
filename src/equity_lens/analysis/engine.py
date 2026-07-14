"""Analysis orchestrator: ticker in, complete analysis out.

Routes each company to its methodology from universe.py and blends the
resulting values into a single target price:
  - dcf_comps: 60% DCF / 40% comps (intrinsic view weighted over the
    market-relative check)
  - bank / conglomerate: justified P/B on normalized ROE

The full assumption set rides along in the output so reports can disclose
every input behind the target.
"""

import statistics

from equity_lens.data import edgar, macro, market
from equity_lens.universe import UNIVERSE
from equity_lens.analysis import (macro_links, overlays, ratios, sensitivity,
                                  valuation)

ROE_NORMALIZATION_YEARS = 5

# Target blend for operating companies: intrinsic value (DCF), what peers
# trade at (comps), and what the company's own franchise has historically
# commanded (own multiple). No single lens dominates.
WEIGHTS = {"dcf": 0.40, "comps": 0.30, "own_multiple": 0.30}


def _own_average_pe(ticker: str, eps_by_year: dict, years: int = 5) -> float:
    """The company's average trailing P/E over recent fiscal years:
    mean price during each fiscal year / that year's diluted EPS."""
    import statistics as _st
    hist = market.get_history(ticker, period=f"{years + 1}y")
    pes = []
    for y, eps in list(eps_by_year.items())[-years:]:
        if eps and eps > 0:
            yr_prices = hist[hist.index.year == y]["Close"]
            if len(yr_prices):
                pes.append(yr_prices.mean() / eps)
    return _st.median(pes) if pes else None


def _normalized_roe(ratio_data: dict) -> float:
    """Multi-year average ROE, so the valuation multiple reflects the
    franchise rather than a single good or bad year."""
    roes = [r["roe"] for _, r in sorted(ratio_data["per_year"].items())
            if "roe" in r][-ROE_NORMALIZATION_YEARS:]
    return statistics.mean(roes) if roes else None


def analyze(ticker: str) -> dict:
    """Run the full pipeline for one covered ticker."""
    profile = UNIVERSE[ticker]
    snap = market.get_snapshot(ticker)
    fin = edgar.get_annual_financials(profile["cik"])
    ratio_data = ratios.compute_ratios(fin)

    risk_free = macro.get_series("DGS10").iloc[-1] / 100
    coe = valuation.cost_of_equity(risk_free, snap["beta"])

    # Macro linkages: bounded, trait-based adjustments (see macro_links.py).
    cash_hist = fin["cash"]
    eq_hist = fin["total_equity"]
    cash_to_book = (list(cash_hist.values())[-1] / list(eq_hist.values())[-1]
                    if cash_hist and eq_hist else None)
    macro_adjs = macro_links.compute_adjustments(profile, cash_to_book)
    coe += macro_links.net_adjustment(macro_adjs, "cost_of_equity")

    price = snap["price"]
    # Derive share count from market cap so dual-class companies (BRK) get
    # the economically correct all-class count, not one class's shares.
    shares = (snap["market_cap"] / price if snap["market_cap"] and price
              else snap["shares_outstanding"])
    method = profile["method"]
    models = {}

    peers = market.get_peer_multiples(profile["peers"])

    if method == "dcf_comps":
        fcf_years = {y: r["free_cash_flow"] for y, r in ratio_data["per_year"].items()
                     if "free_cash_flow" in r}
        # Base = 5-year median: robust to one-off years (a single acquisition
        # payout or windfall year can't set the base), unlike a mean.
        recent_fcf = list(fcf_years.values())[-5:]
        fcf_base = statistics.median(recent_fcf) if recent_fcf else None
        fcf_basis = "ocf minus all capex (standard)"

        # Capital-intensive check: when capex persistently runs far above
        # depreciation, the company is buying growth assets (ships, fleets,
        # plants) — charging ALL of it against cash flow mis-values the
        # business. Standard fix: charge maintenance capex only, proxied by
        # depreciation. Threshold of 2x keeps normal companies (capex around
        # 1-1.8x depreciation) on the standard definition.
        capex_hist = list(fin["capex"].values())[-5:]
        dep_hist = list(fin["depreciation"].values())[-5:]
        ocf_hist = list(fin["operating_cash_flow"].values())[-5:]
        if capex_hist and dep_hist and ocf_hist:
            capex_med = statistics.median(capex_hist)
            dep_med = statistics.median(dep_hist)
            if dep_med > 0 and capex_med > 2.0 * dep_med:
                fcf_base = statistics.median(
                    [ocf - dep_med for ocf in ocf_hist])
                fcf_basis = ("maintenance: ocf minus depreciation "
                             f"(capex runs {capex_med / dep_med:.1f}x "
                             "depreciation - growth investment excluded)")

        # Forward-looking growth (consensus) preferred; history as fallback;
        # macro linkages lean on the result within their caps.
        growth = (snap["earnings_growth"] or snap["revenue_growth"]
                  or ratio_data["fcf_cagr_5y"] or ratio_data["revenue_cagr_5y"])
        if growth is not None:
            growth += macro_links.net_adjustment(macro_adjs, "growth")
            # Effective (capped) growth: the base the model actually uses,
            # and the honest center for the sensitivity grid.
            growth = min(max(growth, valuation.TERMINAL_GROWTH), valuation.GROWTH_CAP)

        # Exit multiple: average of what peers trade at and what this company
        # has historically commanded — industry potential and franchise
        # premium both enter the terminal value.
        pe_f = peers["forward_pe"].dropna()
        pe_t = peers["trailing_pe"].dropna()
        peer_mult = (pe_f.median() if not pe_f.empty
                     else (pe_t.median() if not pe_t.empty else None))
        # EPS history: as filed, or derived from net income / current share
        # count for filers (some foreign issuers) that don't tag EPS.
        eps_hist = fin["eps_diluted"]
        if not eps_hist and shares:
            eps_hist = {y: v / shares for y, v in fin["net_income"].items()}
        own_pe = _own_average_pe(ticker, eps_hist)
        mults = [x for x in (peer_mult, own_pe) if x]
        exit_mult = sum(mults) / len(mults) if mults else None

        debt = fin["long_term_debt"]
        cash = fin["cash"]
        net_debt = ((list(debt.values())[-1] if debt else 0)
                    - (list(cash.values())[-1] if cash else 0))
        models["dcf"] = valuation.dcf_value(fcf_base, growth, coe, net_debt,
                                            shares, exit_multiple=exit_mult)
        if models["dcf"].get("assumptions") is not None:
            models["dcf"]["assumptions"]["fcf_basis"] = fcf_basis

        # Current trailing EPS; last 10-K EPS can be ~3 quarters stale.
        eps_10k = fin["eps_diluted"]
        eps_trailing = snap["trailing_eps"] or (list(eps_10k.values())[-1] if eps_10k else None)
        models["comps"] = valuation.comps_value(eps_trailing, snap["forward_eps"], peers)
        models["own_multiple"] = valuation.own_multiple_value(
            own_pe, snap["forward_eps"], eps_trailing)

        vals, weights = [], []
        for name, w in WEIGHTS.items():
            if models[name]["per_share"]:
                vals.append(models[name]["per_share"]); weights.append(w)
        target = (sum(v * w for v, w in zip(vals, weights)) / sum(weights)
                  if vals else None)

        # Sensitivity: flex growth and CoE through the DCF, holding the
        # market-based models fixed, and re-blend at each grid point.
        def _target_at(g, c):
            # clamp_growth=False: the grid explores hypotheticals around the
            # effective assumption; re-capping would flatten the rows.
            d = valuation.dcf_value(fcf_base, g, c, net_debt, shares,
                                    exit_multiple=exit_mult, clamp_growth=False)
            vs, ws = [], []
            for name, w in WEIGHTS.items():
                ps = d["per_share"] if name == "dcf" else models[name]["per_share"]
                if ps:
                    vs.append(ps); ws.append(w)
            return sum(v * w for v, w in zip(vs, ws)) / sum(ws) if vs else None

        sens = (sensitivity.build_grid(_target_at, growth, coe, "FCF growth")
                if growth is not None and target else None)

    else:
        eq = fin["total_equity"]
        book = list(eq.values())[-1] if eq else None
        bvps = book / shares if book and shares else None
        roe = _normalized_roe(ratio_data)
        if roe is not None:
            roe += macro_links.net_adjustment(macro_adjs, "roe")
        models["justified_pb"] = valuation.justified_pb_value(bvps, roe, coe)

        if method == "bank":
            # Banks: justified P/B cross-checked with peer P/E and the bank's
            # own historical P/E — regionals are commonly valued on both.
            models["comps"] = valuation.comps_value(
                snap["trailing_eps"], snap["forward_eps"], peers)
            own_pe = _own_average_pe(ticker, fin["eps_diluted"])
            models["own_multiple"] = valuation.own_multiple_value(
                own_pe, snap["forward_eps"], snap["trailing_eps"])
        else:
            # Holdcos like BRK: GAAP runs unrealized portfolio gains through
            # earnings, so P/E is noise. Cross-check on peer P/B instead.
            peer_pb = peers["price_to_book"].dropna()
            if bvps and not peer_pb.empty:
                models["peer_pb"] = {
                    "per_share": bvps * peer_pb.median(),
                    "assumptions": {"book_per_share": bvps,
                                    "peer_median_pb": peer_pb.median(),
                                    "peers_used": list(peer_pb.index)},
                }

        vals = [m["per_share"] for m in models.values() if m.get("per_share")]
        target = sum(vals) / len(vals) if vals else None

        # Sensitivity: flex ROE and CoE through the justified P/B model,
        # holding market-based cross-checks fixed.
        def _target_at(r, c):
            j = valuation.justified_pb_value(bvps, r, c)
            vs = [j["per_share"]] if j["per_share"] else []
            vs += [m["per_share"] for name, m in models.items()
                   if name != "justified_pb" and m.get("per_share")]
            return sum(vs) / len(vs) if vs else None

        sens = (sensitivity.build_grid(_target_at, roe, coe, "Normalized ROE")
                if roe is not None and target else None)

    # Analyst judgment overlays: dated, disclosed adjustments on top of the
    # frozen mechanical base (see overlays.py). Rating uses the final target.
    overlay = overlays.apply(ticker, target)
    final_target = overlay["adjusted_target"]

    return {
        "ticker": ticker,
        "as_of": __import__("datetime").date.today().isoformat(),
        "profile": profile,
        "snapshot": snap,
        "financials": fin,
        "ratios": ratio_data,
        "cost_of_equity": coe,
        "risk_free_rate": risk_free,
        "macro_adjustments": macro_adjs,
        "sensitivity": sens,
        "models": models,
        "base_target": target,
        "overlay": overlay,
        "target_price": final_target,
        **valuation.make_rating(price, final_target),
    }


def _relative_label(rank: int, n: int) -> str:
    """Position within coverage -> relative stance. The top name is always
    the Top Pick and the bottom always Least Preferred: relative ratings
    force a distribution regardless of the absolute market level."""
    if rank == 0:
        return "Top Pick"
    if rank == n - 1:
        return "Least Preferred"
    p = rank / (n - 1)
    return "Overweight" if p < 0.45 else ("Neutral" if p < 0.7 else "Underweight")


def analyze_universe(tickers: list = None) -> dict:
    """Analyze every covered company and assign relative ratings by ranking
    upside within the coverage universe.

    Absolute rating answers "is it cheap vs our value estimate?";
    relative rating answers "which would we own first?". Both are reported.
    """
    tickers = tickers or list(UNIVERSE)
    results = {tk: analyze(tk) for tk in tickers}
    ranked = sorted((tk for tk in results if results[tk]["upside"] is not None),
                    key=lambda tk: results[tk]["upside"], reverse=True)
    for rank, tk in enumerate(ranked):
        results[tk]["relative_rank"] = rank + 1
        results[tk]["relative_rating"] = _relative_label(rank, len(ranked))
    return results
