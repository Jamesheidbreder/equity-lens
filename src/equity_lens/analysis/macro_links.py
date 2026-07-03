"""Macro linkages: bounded, rule-based adjustments to model inputs.

Design principles:
  - Rules key on company TRAITS (bank, beverage_commodity, ...), never on
    tickers, so any newly covered company inherits the right linkages.
  - Every adjustment is CAPPED. A macro reading can lean on an assumption;
    it can never dominate the valuation.
  - Every rule failure is silent-safe: if a FRED series is down or a trait
    is missing, the rule is skipped and the baseline engine is unchanged.
  - Every applied adjustment is returned with its data reading and a
    rationale sentence, so reports can disclose exactly what moved and why.

Adjustment targets:
  "growth"          — added to the DCF growth assumption (cap ±1.5pp)
  "cost_of_equity"  — added to CoE via a credit-spread ERP signal (cap ±1pp)
  "roe"             — added to normalized ROE for banks/holdcos (cap ±1.5pp)
"""

from equity_lens.data import macro

CAPS = {"growth": 0.015, "cost_of_equity": 0.010, "roe": 0.015}

# Dampening: how much of a raw macro reading passes into an assumption.
# Set well below 1 on purpose — macro leans, it doesn't decide.
FX_PASS_THROUGH = 0.30          # of the dollar's 1y move x intl share
COMMODITY_COST_SHARE = 0.15     # rough input-cost share of revenue for beverages
CURVE_TO_ROE = 0.50             # of curve-slope deviation from its 10y median
SPREAD_TO_ERP = 0.50            # of credit-spread deviation from its 10y median
DURABLES_TO_GROWTH = 0.30       # of durables-spending growth deviation


def _clamp(x, cap):
    return max(-cap, min(cap, x))


def _yoy_change(series_id: str) -> float:
    """Latest reading vs ~1 year earlier, as a fraction."""
    s = macro.get_series(series_id)
    past = s[s.index <= s.index[-1] - __import__("pandas").DateOffset(years=1)]
    return s.iloc[-1] / past.iloc[-1] - 1


def _vs_median(series_id: str, years: int = 10) -> tuple:
    """(latest, latest minus the trailing N-year median). For level series
    quoted in percent (spreads, slopes), returned in percentage points."""
    s = macro.get_series(series_id, years=years)
    return s.iloc[-1], s.iloc[-1] - s.median()


def _yoy_vs_trend(series_id: str, trend_years: int = 5) -> tuple:
    """(yoy growth, N-year trend growth, deviation). For 'is demand running
    above or below its own trend?' style rules."""
    import pandas as pd
    s = macro.get_series(series_id, years=trend_years + 1)
    yoy = s.iloc[-1] / s[s.index <= s.index[-1] - pd.DateOffset(years=1)].iloc[-1] - 1
    span = (s.index[-1] - s.index[0]).days / 365.25
    trend = (s.iloc[-1] / s.iloc[0]) ** (1 / span) - 1 if span > 0 else 0.0
    return yoy, trend, yoy - trend


def compute_adjustments(profile: dict, cash_to_book: float = None) -> list:
    """All applicable macro adjustments for a company profile.

    Returns a list of dicts: rule, indicator, reading, target, adjustment,
    rationale. Callers sum adjustments per target and apply them.
    """
    traits = profile.get("traits", [])
    intl = profile.get("intl_revenue_share")
    adjs = []

    def try_rule(fn):
        try:
            result = fn()
            if result:
                adjs.append(result)
        except Exception:
            pass  # rule skipped; baseline engine unaffected

    # ---- Everyone: credit spreads -> equity risk premium ----------------
    def credit_spread_erp():
        latest, dev = _vs_median("BAA10Y")
        adj = _clamp(dev / 100 * SPREAD_TO_ERP, CAPS["cost_of_equity"])
        return {
            "rule": "credit_spread_erp", "indicator": "BAA10Y",
            "reading": f"Baa spread {latest:.2f}%, {dev:+.2f}pp vs 10y median",
            "target": "cost_of_equity", "adjustment": adj,
            "rationale": "Credit spreads are a market-priced risk gauge; "
                         "wider-than-normal spreads raise the equity risk premium.",
        }
    try_rule(credit_spread_erp)

    # ---- Multinationals: dollar strength -> translated growth -----------
    def dollar_translation():
        if not intl:
            return None
        chg = _yoy_change("DTWEXBGS")
        adj = _clamp(-chg * intl * FX_PASS_THROUGH, CAPS["growth"])
        return {
            "rule": "dollar_translation", "indicator": "DTWEXBGS",
            "reading": f"Trade-weighted dollar {chg:+.1%} y/y",
            "target": "growth", "adjustment": adj,
            "rationale": f"~{intl:.0%} of revenue is foreign; a stronger dollar "
                         "shrinks it in translation, a weaker one inflates it.",
        }
    try_rule(dollar_translation)

    # ---- Banks: yield-curve slope -> sustainable ROE ---------------------
    def curve_slope_roe():
        if "bank" not in traits:
            return None
        latest, dev = _vs_median("T10Y2Y")
        adj = _clamp(dev / 100 * CURVE_TO_ROE, CAPS["roe"])
        return {
            "rule": "curve_slope_roe", "indicator": "T10Y2Y",
            "reading": f"10y-2y slope {latest:.2f}%, {dev:+.2f}pp vs 10y median",
            "target": "roe", "adjustment": adj,
            "rationale": "Banks earn the spread between long lending and short "
                         "funding; a steeper-than-normal curve supports richer "
                         "margins and ROE, a flat/inverted curve compresses them.",
        }
    try_rule(curve_slope_roe)

    # ---- Banks: loan delinquencies -> credit-cost drag -------------------
    def delinquency_roe():
        if "bank" not in traits:
            return None
        s = macro.get_series("DRALACBN", years=10)  # delinquency rate, all loans
        latest, year_ago = s.iloc[-1], s[s.index <= s.index[-1] -
                                         __import__("pandas").DateOffset(years=1)].iloc[-1]
        rising = latest - year_ago  # percentage points
        adj = _clamp(-max(rising, 0) / 100 * 1.0, CAPS["roe"])  # only penalize
        if adj == 0:
            return None
        return {
            "rule": "delinquency_roe", "indicator": "DRALACBN",
            "reading": f"Delinquency rate {latest:.2f}%, {rising:+.2f}pp y/y",
            "target": "roe", "adjustment": adj,
            "rationale": "Rising delinquencies foreshadow higher loan-loss "
                         "provisions, which come straight out of bank earnings.",
        }
    try_rule(delinquency_roe)

    # ---- Beverages: aluminum + sugar -> input-cost margin pressure -------
    def commodity_margin():
        if "beverage_commodity" not in traits:
            return None
        moves = []
        for sid in ("PALUMUSDM", "PSUGAISAUSDM"):
            try:
                moves.append(_yoy_change(sid))
            except Exception:
                continue
        if not moves:
            return None
        avg_move = sum(moves) / len(moves)
        adj = _clamp(-avg_move * COMMODITY_COST_SHARE, CAPS["growth"])
        return {
            "rule": "commodity_margin", "indicator": "PALUMUSDM/PSUGAISAUSDM",
            "reading": f"Aluminum & sugar avg {avg_move:+.1%} y/y",
            "target": "growth", "adjustment": adj,
            "rationale": "Cans and sweetener are real input costs for a beverage "
                         "maker; cost inflation pressures margins unless fully "
                         "passed through in price.",
        }
    try_rule(commodity_margin)

    # ---- Consumer hardware: durable-goods spending -> demand cycle -------
    def durables_demand():
        if "consumer_hardware" not in traits:
            return None
        s = macro.get_series("PCEDG", years=6)
        import pandas as pd
        yoy = s.iloc[-1] / s[s.index <= s.index[-1] - pd.DateOffset(years=1)].iloc[-1] - 1
        five_yr_avg = (s.iloc[-1] / s.iloc[0]) ** (1 / 5) - 1
        adj = _clamp((yoy - five_yr_avg) * DURABLES_TO_GROWTH, CAPS["growth"])
        return {
            "rule": "durables_demand", "indicator": "PCEDG",
            "reading": f"Durables spending {yoy:+.1%} y/y vs {five_yr_avg:+.1%} 5y trend",
            "target": "growth", "adjustment": adj,
            "rationale": "Premium devices are durable-goods purchases; demand "
                         "running above/below trend leans on near-term growth.",
        }
    try_rule(durables_demand)

    # ---- Banks: card delinquencies -> earlier-turning credit stress ------
    def card_delinquency_roe():
        if "bank" not in traits:
            return None
        import pandas as pd
        s = macro.get_series("DRCCLACBS", years=10)
        latest = s.iloc[-1]
        year_ago = s[s.index <= s.index[-1] - pd.DateOffset(years=1)].iloc[-1]
        rising = latest - year_ago
        adj = _clamp(-max(rising, 0) / 100 * 0.5, CAPS["roe"])  # penalty only
        if adj == 0:
            return None
        return {
            "rule": "card_delinquency_roe", "indicator": "DRCCLACBS",
            "reading": f"Card delinquency {latest:.2f}%, {rising:+.2f}pp y/y",
            "target": "roe", "adjustment": adj,
            "rationale": "Card delinquencies turn before total loan "
                         "delinquencies; rising consumer credit stress leads "
                         "provisions.",
        }
    try_rule(card_delinquency_roe)

    # ---- Staples w/ limited pricing power: PPI vs CPI margin gap ---------
    def ppi_cpi_margin():
        if "cost_passthrough_limited" not in traits:
            return None
        ppi = _yoy_change("PPIACO")
        cpi = _yoy_change("CPIAUCSL")
        gap = ppi - cpi
        adj = _clamp(-max(gap, 0) * 0.3, CAPS["growth"])  # penalty only
        if adj == 0:
            return None
        return {
            "rule": "ppi_cpi_margin", "indicator": "PPIACO vs CPIAUCSL",
            "reading": f"Producer prices {ppi:+.1%} vs consumer prices {cpi:+.1%} y/y",
            "target": "growth", "adjustment": adj,
            "rationale": "Input costs outrunning shelf prices squeeze margins "
                         "for companies that can't fully pass costs through.",
        }
    try_rule(ppi_cpi_margin)

    # ---- Enterprise software: corporate software investment demand -------
    def software_investment_demand():
        if "enterprise_software" not in traits:
            return None
        yoy, trend, dev = _yoy_vs_trend("B985RC1Q027SBEA")
        adj = _clamp(dev * 0.3, CAPS["growth"])
        return {
            "rule": "software_investment_demand", "indicator": "B985RC1Q027SBEA",
            "reading": f"Business software investment {yoy:+.1%} y/y vs {trend:+.1%} trend",
            "target": "growth", "adjustment": adj,
            "rationale": "National-accounts software investment is the demand "
                         "pool for enterprise IT; spend above/below trend leans "
                         "on growth.",
        }
    try_rule(software_investment_demand)

    # ---- Energy producers: the commodity IS the top line -----------------
    def oil_price_revenue():
        if "energy_producer" not in traits:
            return None
        chg = _yoy_change("DCOILWTICO")
        adj = _clamp(chg * 0.10, CAPS["growth"])
        return {
            "rule": "oil_price_revenue", "indicator": "DCOILWTICO",
            "reading": f"WTI crude {chg:+.1%} y/y",
            "target": "growth", "adjustment": adj,
            "rationale": "Producer revenue is price x volume; the oil price "
                         "moves the top line directly.",
        }
    try_rule(oil_price_revenue)

    # ---- Homebuilders: starts volume + mortgage-rate affordability -------
    def housing_cycle():
        if "homebuilder_housing" not in traits:
            return None
        starts_yoy = _yoy_change("HOUST")
        _, rate_dev = _vs_median("MORTGAGE30US")
        adj = _clamp(starts_yoy * 0.2 - max(rate_dev, 0) / 100 * 0.3,
                     CAPS["growth"])
        return {
            "rule": "housing_cycle", "indicator": "HOUST + MORTGAGE30US",
            "reading": f"Housing starts {starts_yoy:+.1%} y/y; mortgage rate "
                       f"{rate_dev:+.2f}pp vs 10y median",
            "target": "growth", "adjustment": adj,
            "rationale": "Starts are the volume driver; above-normal mortgage "
                         "rates throttle affordability and future demand.",
        }
    try_rule(housing_cycle)

    # ---- Autos: where the sales pace sits in the cycle -------------------
    def auto_sales_cycle():
        if "auto_cycle" not in traits:
            return None
        yoy, trend, dev = _yoy_vs_trend("TOTALSA")
        adj = _clamp(dev * 0.3, CAPS["growth"])
        return {
            "rule": "auto_sales_cycle", "indicator": "TOTALSA",
            "reading": f"Vehicle sales pace {yoy:+.1%} y/y vs {trend:+.1%} trend",
            "target": "growth", "adjustment": adj,
            "rationale": "Industry volume vs its own trend locates the point "
                         "in the auto cycle.",
        }
    try_rule(auto_sales_cycle)

    # ---- Retail: demand vs trend ------------------------------------------
    def retail_sales_demand():
        if "retail_consumer" not in traits:
            return None
        yoy, trend, dev = _yoy_vs_trend("RSXFS")
        adj = _clamp(dev * 0.3, CAPS["growth"])
        return {
            "rule": "retail_sales_demand", "indicator": "RSXFS",
            "reading": f"Retail sales {yoy:+.1%} y/y vs {trend:+.1%} trend",
            "target": "growth", "adjustment": adj,
            "rationale": "Retail sales measure the demand pool directly; "
                         "above/below-trend spending leans on growth.",
        }
    try_rule(retail_sales_demand)

    # ---- Cash-heavy holdcos: T-bill yields -> earnings on the cash pile --
    def cash_yield_roe():
        if "holdco_cash" not in traits or not cash_to_book:
            return None
        latest, dev = _vs_median("DTB3", years=10)
        adj = _clamp(dev / 100 * cash_to_book, CAPS["roe"])
        return {
            "rule": "cash_yield_roe", "indicator": "DTB3",
            "reading": f"3-month T-bill {latest:.2f}%, {dev:+.2f}pp vs 10y median; "
                       f"cash is {cash_to_book:.0%} of book",
            "target": "roe", "adjustment": adj,
            "rationale": "A large cash-and-bills pile earns the short rate; "
                         "rates above their norm mechanically lift returns on it.",
        }
    try_rule(cash_yield_roe)

    return adjs


def net_adjustment(adjs: list, target: str) -> float:
    """Sum of adjustments for one target, re-capped as a final guard."""
    total = sum(a["adjustment"] for a in adjs if a["target"] == target)
    return _clamp(total, CAPS[target])
