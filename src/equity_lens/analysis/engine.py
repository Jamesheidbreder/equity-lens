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
from equity_lens.analysis import ratios, valuation

DCF_WEIGHT, COMPS_WEIGHT = 0.60, 0.40
ROE_NORMALIZATION_YEARS = 5


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

    price = snap["price"]
    # Derive share count from market cap so dual-class companies (BRK) get
    # the economically correct all-class count, not one class's shares.
    shares = (snap["market_cap"] / price if snap["market_cap"] and price
              else snap["shares_outstanding"])
    method = profile["method"]
    models = {}

    if method == "dcf_comps":
        fcf_years = {y: r["free_cash_flow"] for y, r in ratio_data["per_year"].items()
                     if "free_cash_flow" in r}
        fcf_base = list(fcf_years.values())[-1] if fcf_years else None
        growth = ratio_data["fcf_cagr_5y"] or ratio_data["revenue_cagr_5y"]
        debt = fin["long_term_debt"]
        cash = fin["cash"]
        net_debt = ((list(debt.values())[-1] if debt else 0)
                    - (list(cash.values())[-1] if cash else 0))
        models["dcf"] = valuation.dcf_value(fcf_base, growth, coe, net_debt, shares)

        peers = market.get_peer_multiples(profile["peers"])
        # Current trailing EPS; last 10-K EPS can be ~3 quarters stale.
        eps_10k = fin["eps_diluted"]
        eps_latest = snap["trailing_eps"] or (list(eps_10k.values())[-1] if eps_10k else None)
        models["comps"] = valuation.comps_value(eps_latest, peers)

        vals, weights = [], []
        if models["dcf"]["per_share"]:
            vals.append(models["dcf"]["per_share"]); weights.append(DCF_WEIGHT)
        if models["comps"]["per_share"]:
            vals.append(models["comps"]["per_share"]); weights.append(COMPS_WEIGHT)
        target = (sum(v * w for v, w in zip(vals, weights)) / sum(weights)
                  if vals else None)

    else:  # bank or conglomerate: justified P/B on normalized ROE
        eq = fin["total_equity"]
        book = list(eq.values())[-1] if eq else None
        bvps = book / shares if book and shares else None
        models["justified_pb"] = valuation.justified_pb_value(
            bvps, _normalized_roe(ratio_data), coe)
        target = models["justified_pb"]["per_share"]

    return {
        "ticker": ticker,
        "profile": profile,
        "snapshot": snap,
        "financials": fin,
        "ratios": ratio_data,
        "cost_of_equity": coe,
        "risk_free_rate": risk_free,
        "models": models,
        "target_price": target,
        **valuation.make_rating(price, target),
    }
