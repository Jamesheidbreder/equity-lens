"""Site data export: everything a front-end needs, as static JSON.

Published to site/ in the repo; GitHub serves the files at
https://raw.githubusercontent.com/Jamesheidbreder/equity-lens/main/site/<file>
with CORS enabled, so any website builder (Lovable, a hand-built static
site) can read them live — no server, no cost. The engine stays the single
source of truth; the website is a skin.

Run: PYTHONPATH=src .venv/bin/python -m equity_lens.reports.export_site
"""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from equity_lens.analysis.engine import analyze_universe
from equity_lens.data import macro, market
from equity_lens.universe import MACRO_SERIES

REPO_ROOT = Path(__file__).parents[3]
SITE_DIR = REPO_ROOT / "site"
CALLS_CSV = REPO_ROOT / "data" / "calls.csv"
REPORTS_DIR = REPO_ROOT / "reports"

MODEL_LABELS = {
    "dcf": "Cash-flow value (DCF)",
    "comps": "Priced like its peers",
    "own_multiple": "Priced like its own history",
    "justified_pb": "Balance-sheet value",
    "peer_pb": "Balance sheet at peer multiples",
}


def _jsonable(o):
    """Fallback for numpy scalars and anything else json chokes on."""
    try:
        return float(o)
    except (TypeError, ValueError):
        return str(o)


def _write(name: str, payload):
    SITE_DIR.mkdir(exist_ok=True)
    path = SITE_DIR / name
    path.write_text(json.dumps(payload, indent=1, default=_jsonable))
    return path


def _company_payload(a: dict) -> dict:
    s = a["snapshot"]
    per_year = a["ratios"]["per_year"]
    fundamentals = [
        {"year": y, **{k: v for k, v in row.items()}}
        for y, row in sorted(per_year.items())]
    hist = market.get_history(a["ticker"], period="5y")["Close"]
    weekly = hist.resample("W").last().dropna()
    return {
        "ticker": a["ticker"],
        "name": a["profile"]["name"],
        "sector": a["profile"]["sector"],
        "industry": a["profile"]["industry"],
        "as_of": a["as_of"],
        "price": s["price"],
        "market_cap": s["market_cap"],
        "beta": s["beta"],
        "pe_trailing": s["trailing_pe"],
        "dividend_yield_pct": s["dividend_yield"],
        "week52_low": s["52w_low"],
        "week52_high": s["52w_high"],
        "rating": a["rating"],
        "relative_rating": a.get("relative_rating"),
        "relative_rank": a.get("relative_rank"),
        "target": a["target_price"],
        "base_target": a["base_target"],
        "upside": a["upside"],
        "street_target": s["street_target_mean"],
        "street_analyst_count": s["street_analyst_count"],
        "cost_of_equity": a["cost_of_equity"],
        "models": [
            {"key": k, "label": MODEL_LABELS.get(k, k),
             "value": m["per_share"], "assumptions": m.get("assumptions")}
            for k, m in a["models"].items() if m.get("per_share")],
        "overlays": a["overlay"]["overlays"],
        "macro_adjustments": a["macro_adjustments"],
        "sensitivity": a.get("sensitivity"),
        "fundamentals": fundamentals,
        "growth": {
            "revenue_cagr_3y": a["ratios"]["revenue_cagr_3y"],
            "revenue_cagr_5y": a["ratios"]["revenue_cagr_5y"],
            "net_income_cagr_5y": a["ratios"]["net_income_cagr_5y"],
            "fcf_cagr_5y": a["ratios"]["fcf_cagr_5y"],
        },
        "business_summary": s["business_summary"],
        "price_history_weekly": [
            {"date": d.date().isoformat(), "close": round(float(v), 2)}
            for d, v in weekly.items()],
    }


def export_all() -> list:
    results = analyze_universe()
    written = []

    # 1. Companies: full analysis per name
    companies = [_company_payload(a) for a in results.values()]
    companies.sort(key=lambda c: c.get("relative_rank") or 99)
    written.append(_write("companies.json", companies))

    # 2. Scorecard: the append-only call log
    calls = []
    if CALLS_CSV.exists():
        with open(CALLS_CSV, newline="") as f:
            for row in csv.DictReader(f):
                calls.append({k: (float(v) if k in
                                  ("price", "base_target", "final_target",
                                   "street_target") and v else v)
                              for k, v in row.items()})
    written.append(_write("scorecard.json", calls))

    # 3. Macro: dashboard latest readings + 10y monthly history per series
    dash = macro.get_macro_dashboard(MACRO_SERIES)
    macro_payload = {"latest": dash.reset_index().to_dict("records"),
                     "history": {}}
    for sid in MACRO_SERIES:
        s = macro.get_series(sid).resample("M").last().dropna()
        macro_payload["history"][sid] = [
            {"date": d.date().isoformat(), "value": round(float(v), 3)}
            for d, v in s.items()]
    written.append(_write("macro.json", macro_payload))

    # 4. Reports: full markdown text of every committed report
    reports = [{"file": p.name, "markdown": p.read_text()}
               for p in sorted(REPORTS_DIR.glob("*.md"), reverse=True)]
    written.append(_write("reports.json", reports))

    # 5. Meta: provenance and the disclaimer every page must show
    written.append(_write("meta.json", {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "https://github.com/Jamesheidbreder/equity-lens",
        "data_sources": ["SEC EDGAR (as-filed XBRL)", "Yahoo Finance",
                         "FRED (Federal Reserve Economic Data)"],
        "disclaimer": "Educational research project. Not investment advice.",
    }))
    return written


if __name__ == "__main__":
    for p in export_all():
        print("wrote", p)
