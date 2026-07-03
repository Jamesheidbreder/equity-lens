"""Report generator: analysis output -> CFA-structure research documents.

Every number in a report comes from the analysis engine; this module only
formats and discloses. Reports are dated markdown files committed to git,
and every generation run appends the calls (rating, target, price) to
data/calls.csv — the scorecard's raw material.

Structure follows CFA Institute research report standards: header block,
investment summary, macro & industry overview, business description,
financial analysis, valuation (all models + sensitivity), risks,
disclosures.
"""

import csv
from datetime import date
from pathlib import Path

from equity_lens.analysis.engine import analyze_universe
from equity_lens.data import macro
from equity_lens.universe import MACRO_SERIES

REPO_ROOT = Path(__file__).parents[3]
REPORTS_DIR = REPO_ROOT / "reports"
CALLS_CSV = REPO_ROOT / "data" / "calls.csv"

TRAIT_RISKS = {
    "bank": "Credit cycle: rising delinquencies and charge-offs flow directly "
            "into provisions and earnings; a flat or inverted yield curve "
            "compresses net interest margin.",
    "beverage_commodity": "Input-cost inflation (aluminum, sweetener) pressures "
                          "gross margin if not passed through in price.",
    "consumer_hardware": "Durable-goods demand is cyclical and replacement "
                         "cycles can extend when consumers are stretched.",
    "holdco_cash": "Falling short rates reduce income on the cash pile; "
                   "equity-market drawdowns mark down the investment portfolio.",
    "enterprise_software": "Corporate IT budgets are cut in downturns; "
                           "competition can compress cloud pricing.",
}


def _m(x, pre="$", nd=2):
    return f"{pre}{x:,.{nd}f}" if x is not None else "n/a"


def _pct(x, nd=1):
    return f"{x:+.{nd}%}" if x is not None else "n/a"


def _bn(x):
    return f"${x / 1e9:,.1f}B" if x is not None else "n/a"


def _fmt_val(v):
    """Human formatting for assumption values of any shape."""
    if isinstance(v, dict):
        return "; ".join(f"{k.replace('_', ' ')} {_fmt_val(x)}" for k, x in v.items())
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if abs(v) >= 1e8:
            return _bn(v)
        if 0 < abs(v) < 1:
            return f"{v:.2%}"
        return f"{v:,.2f}"
    return str(v)


def _header(a: dict) -> str:
    s, p = a["snapshot"], a["profile"]
    # Yahoo reports dividendYield already in percent units.
    div = f"{s['dividend_yield']:.2f}%" if s["dividend_yield"] else "n/a"
    inst = f"{s['held_by_institutions']:.1%}" if s["held_by_institutions"] else "n/a"
    lines = [
        f"# {p['name']} ({a['ticker']}) — {a['rating']}",
        "",
        f"**Equity Research | {p['sector']} — {p['industry']} | {a['as_of']}**",
        "",
        "| | |",
        "|---|---|",
        f"| Rating (absolute) | **{a['rating']}** |",
        f"| Rating (relative, within coverage) | **{a.get('relative_rating', 'n/a')}"
        f"** (#{a.get('relative_rank', '-')} of coverage) |",
        f"| Price | {_m(s['price'])} |",
        f"| Target price | **{_m(a['target_price'])}** "
        f"(base model {_m(a['base_target'])}) |",
        f"| Implied upside | {_pct(a['upside'])} |",
        f"| Street consensus target | {_m(s['street_target_mean'])} "
        f"({s['street_analyst_count'] or '?'} analysts) |",
        f"| Market cap | {_bn(s['market_cap'])} |",
        f"| 52-week range | {_m(s['52w_low'])} – {_m(s['52w_high'])} |",
        f"| Beta | {s['beta'] if s['beta'] is not None else 'n/a'} |",
        f"| Dividend yield | {div} |",
        f"| Institutional ownership | {inst} |",
    ]
    return "\n".join(lines)


def _investment_summary(a: dict) -> str:
    s = a["snapshot"]
    models_line = ", ".join(
        f"{name.replace('_', ' ')} {_m(m['per_share'])}"
        for name, m in a["models"].items() if m.get("per_share"))
    out = [
        "## Investment Summary",
        "",
        f"We rate {a['ticker']} **{a['rating']}** with a target of "
        f"**{_m(a['target_price'])}** vs. a current price of {_m(s['price'])} "
        f"({_pct(a['upside'])} implied). Within our coverage universe the name "
        f"ranks **{a.get('relative_rating', 'n/a')}**.",
        "",
        f"The target blends independent valuation lenses: {models_line}.",
    ]
    if a["overlay"]["overlays"]:
        for o in a["overlay"]["overlays"]:
            out += ["", f"**Analyst overlay ({o['date']}, {_pct(o['value']) if o['type'] == 'target_pct' else 'scenario-weighted'}):** "
                        f"{o['rationale']} *(Review by {o.get('review_by', 'n/a')}.)*"]
    street = s["street_target_mean"]
    if street and a["target_price"]:
        gap = a["target_price"] / street - 1
        out += ["", f"Our target sits {_pct(gap)} vs. street consensus of "
                    f"{_m(street)}. The divergence is our documented view, not "
                    f"an input: consensus never enters the models."]
    return "\n".join(out)


def _macro_section(a: dict, dashboard) -> str:
    out = [
        "## Macro & Industry Overview",
        "",
        "**Economic backdrop (FRED, latest readings):**",
        "",
        "| Indicator | Latest | As of | 1y ago | Change |",
        "|---|---|---|---|---|",
    ]
    for _, row in dashboard.iterrows():
        out.append(f"| {row['indicator']} | {row['latest']:,.2f} | {row['as_of']} "
                   f"| {row['year_ago']:,.2f} | {row['change_1y']:+,.2f} |")
    out += ["", f"Cost of equity: **{a['cost_of_equity']:.2%}** "
                f"(10Y Treasury {a['risk_free_rate']:.2%} risk-free base, CAPM).", ""]
    if a["macro_adjustments"]:
        out += ["**Macro linkages applied to this valuation** (rule-based, "
                "capped; see MACRO_CATALOG.md):", ""]
        for adj in a["macro_adjustments"]:
            out.append(f"- **{adj['rule']}** [{adj['indicator']}] — {adj['reading']}. "
                       f"Adjustment: {adj['adjustment']:+.2%} to {adj['target']}. "
                       f"{adj['rationale']}")
    else:
        out.append("No trait-based macro linkages currently apply.")
    return "\n".join(out)


def _business_section(a: dict) -> str:
    summary = a["snapshot"]["business_summary"] or "Description unavailable."
    return "\n".join(["## Business Description", "", summary])


def _financials_section(a: dict) -> str:
    per_year = a["ratios"]["per_year"]
    years = sorted(per_year)[-6:]
    out = [
        "## Financial Analysis",
        "",
        "Annual figures from SEC EDGAR as-filed XBRL data (10-K).",
        "",
        "| Fiscal year | Revenue | Net margin | Op margin | ROE | Free cash flow |",
        "|---|---|---|---|---|---|",
    ]
    for y in years:
        r = per_year[y]
        out.append(
            f"| {y} | {_bn(r.get('revenue'))} "
            f"| {_pct(r.get('net_margin')) if r.get('net_margin') else 'n/a'} "
            f"| {_pct(r.get('operating_margin')) if r.get('operating_margin') else 'n/a'} "
            f"| {_pct(r.get('roe')) if r.get('roe') else 'n/a'} "
            f"| {_bn(r.get('free_cash_flow'))} |")
    g = a["ratios"]
    out += ["", f"Revenue CAGR: {_pct(g['revenue_cagr_3y'])} (3y), "
                f"{_pct(g['revenue_cagr_5y'])} (5y). "
                f"Net income CAGR (5y): {_pct(g['net_income_cagr_5y'])}. "
                f"FCF CAGR (5y): {_pct(g['fcf_cagr_5y'])}."]
    return "\n".join(out)


def _valuation_section(a: dict) -> str:
    out = ["## Valuation", ""]
    for name, m in a["models"].items():
        title = name.replace("_", " ").title()
        if not m.get("per_share"):
            out += [f"**{title}:** not applicable "
                    f"({m.get('reason', 'no value')}).", ""]
            continue
        out += [f"**{title}: {_m(m['per_share'])}**", ""]
        for k, v in (m.get("assumptions") or {}).items():
            out.append(f"- {k.replace('_', ' ')}: {_fmt_val(v)}")
        out.append("")
    sens = a.get("sensitivity")
    if sens:
        out += [f"**Sensitivity — target price across {sens['x_label']} (rows) "
                "and cost of equity (columns):**", ""]
        header = "| " + sens["x_label"] + " | " + " | ".join(
            f"{c:.1%}" for c in sens["coe_values"]) + " |"
        out += [header, "|" + "---|" * (len(sens["coe_values"]) + 1)]
        for x, row in zip(sens["x_values"], sens["grid"]):
            cells = " | ".join(f"{v:,.0f}" if v else "-" for v in row)
            out.append(f"| {x:.1%} | {cells} |")
    return "\n".join(out)


def _risks_section(a: dict) -> str:
    out = ["## Investment Risks", ""]
    for trait in a["profile"].get("traits", []):
        if trait in TRAIT_RISKS:
            out.append(f"- {TRAIT_RISKS[trait]}")
    intl = a["profile"].get("intl_revenue_share")
    if intl:
        out.append(f"- Currency: ~{intl:.0%} of revenue is earned abroad; "
                   "a strengthening dollar is a mechanical translation headwind.")
    dcf = a["models"].get("dcf")
    if dcf and dcf.get("terminal_share_of_value"):
        out.append(f"- Valuation model risk: {dcf['terminal_share_of_value']:.0%} "
                   "of DCF value sits in the terminal period — the estimate is "
                   "sensitive to terminal assumptions, as the sensitivity grid shows.")
    if a["rating"] == "SELL" and a["snapshot"]["street_target_mean"]:
        out.append("- Against-consensus risk: our rating is below street "
                   "consensus; if the narrative premium we decline to pay for "
                   "is validated by delivered earnings, the stock can continue "
                   "to outperform our target.")
    return "\n".join(out)


def _disclosures(a: dict) -> str:
    return "\n".join([
        "## Disclosures",
        "",
        f"- Generated by Equity-Lens on {a['as_of']} from primary sources: "
        "SEC EDGAR (as-filed XBRL financials), Yahoo Finance (market data), "
        "FRED (macro series).",
        "- All model values are computed deterministically; methodology is "
        "versioned in this repository. Analyst overlays are dated and disclosed "
        "in the Investment Summary.",
        "- Street consensus figures are shown for benchmarking only and are "
        "never model inputs.",
        "- Educational research project. Not investment advice.",
    ])


def generate_report(a: dict, dashboard) -> str:
    return "\n\n".join([
        _header(a), _investment_summary(a), _macro_section(a, dashboard),
        _business_section(a), _financials_section(a), _valuation_section(a),
        _risks_section(a), _disclosures(a),
    ]) + "\n"


def _log_calls(results: dict):
    """Append today's calls to the scorecard log. Never rewrites history;
    re-running on the same day skips already-logged (date, ticker) rows."""
    CALLS_CSV.parent.mkdir(exist_ok=True)
    existing = set()
    if CALLS_CSV.exists():
        with open(CALLS_CSV, newline="") as f:
            existing = {(r["date"], r["ticker"]) for r in csv.DictReader(f)}
    new_file = not CALLS_CSV.exists()
    with open(CALLS_CSV, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["date", "ticker", "price", "base_target", "final_target",
                        "rating", "relative_rating", "street_target"])
        for tk, a in results.items():
            if (a["as_of"], tk) in existing:
                continue
            w.writerow([a["as_of"], tk, a["snapshot"]["price"],
                        round(a["base_target"], 2) if a["base_target"] else None,
                        round(a["target_price"], 2) if a["target_price"] else None,
                        a["rating"], a.get("relative_rating"),
                        a["snapshot"]["street_target_mean"]])


def generate_all() -> list:
    """Analyze the universe, write one dated report per company plus a
    coverage summary, and log the calls."""
    results = analyze_universe()
    dashboard = macro.get_macro_dashboard(MACRO_SERIES)
    today = date.today().isoformat()
    REPORTS_DIR.mkdir(exist_ok=True)
    written = []

    for tk, a in results.items():
        path = REPORTS_DIR / f"{tk}_{today}.md"
        path.write_text(generate_report(a, dashboard))
        written.append(path)

    ranked = sorted(results.values(), key=lambda a: a.get("relative_rank", 99))
    lines = [
        f"# Equity-Lens Coverage Summary — {today}", "",
        "| Rank | Ticker | Rating | Relative | Price | Target | Upside | Street |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for a in ranked:
        s = a["snapshot"]
        lines.append(
            f"| {a.get('relative_rank', '-')} | {a['ticker']} | {a['rating']} "
            f"| {a.get('relative_rating', '-')} | {_m(s['price'])} "
            f"| {_m(a['target_price'])} | {_pct(a['upside'])} "
            f"| {_m(s['street_target_mean'])} |")
    summary_path = REPORTS_DIR / f"coverage_summary_{today}.md"
    summary_path.write_text("\n".join(lines) + "\n")
    written.append(summary_path)

    _log_calls(results)
    return written


if __name__ == "__main__":
    for p in generate_all():
        print("wrote", p)
