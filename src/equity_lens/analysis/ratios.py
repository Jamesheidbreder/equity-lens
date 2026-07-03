"""Financial ratio and trend analysis from as-filed annual data.

Everything here is arithmetic on SEC-filed numbers. Where a company doesn't
report an input (e.g. capex for a bank), the dependent ratio is simply
omitted — nothing is estimated to fill gaps.
"""


def _series_cagr(series: dict, years: int) -> float:
    """Compound annual growth rate over the trailing `years` fiscal years."""
    keys = sorted(series)
    if len(keys) < 2:
        return None
    window = keys[-min(years + 1, len(keys)):]
    first, last = series[window[0]], series[window[-1]]
    n = window[-1] - window[0]
    if not first or first <= 0 or n <= 0:
        return None
    return (last / first) ** (1 / n) - 1


def compute_ratios(fin: dict) -> dict:
    """Ratio history and growth rates from get_annual_financials() output.

    Returns per-year margin/return series plus summary growth metrics.
    """
    rev, ni = fin["revenue"], fin["net_income"]
    op, eq = fin["operating_income"], fin["total_equity"]
    ocf, capex = fin["operating_cash_flow"], fin["capex"]
    years = sorted(rev.keys() | ni.keys())

    per_year = {}
    for y in years:
        row = {}
        if y in rev and rev[y]:
            row["revenue"] = rev[y]
            if y in ni:
                row["net_margin"] = ni[y] / rev[y]
            if y in op:
                row["operating_margin"] = op[y] / rev[y]
        if y in ni and y in eq and eq[y]:
            row["roe"] = ni[y] / eq[y]
        if y in ocf and y in capex:
            row["free_cash_flow"] = ocf[y] - capex[y]
        if row:
            per_year[y] = row

    fcf_series = {y: r["free_cash_flow"] for y, r in per_year.items()
                  if "free_cash_flow" in r}

    return {
        "per_year": per_year,
        "revenue_cagr_5y": _series_cagr(rev, 5),
        "revenue_cagr_3y": _series_cagr(rev, 3),
        "net_income_cagr_5y": _series_cagr(ni, 5),
        "fcf_cagr_5y": _series_cagr(fcf_series, 5),
        "latest_year": years[-1] if years else None,
    }
