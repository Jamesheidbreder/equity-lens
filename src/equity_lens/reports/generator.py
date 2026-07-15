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
from equity_lens.data import macro, market
from equity_lens.reports import charts
from equity_lens.universe import MACRO_SERIES

REPO_ROOT = Path(__file__).parents[3]
REPORTS_DIR = REPO_ROOT / "reports"
CALLS_CSV = REPO_ROOT / "data" / "calls.csv"
NARRATIVES_DIR = REPO_ROOT / "narratives"

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


MODEL_TITLES = {
    "dcf": "Discounted cash flow",
    "comps": "Peer comparables",
    "own_multiple": "Own historical multiple",
    "justified_pb": "Justified price-to-book",
    "peer_pb": "Peer price-to-book",
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
    models_line = "; ".join(
        f"{MODEL_TITLES.get(name, name).lower()} values the shares at "
        f"{_m(m['per_share'])}"
        for name, m in a["models"].items() if m.get("per_share"))
    out = [
        "## Investment Summary",
        "",
        f"We rate {a['ticker']} **{a['rating']}** with a price target of "
        f"**{_m(a['target_price'])}**, against a current price of "
        f"{_m(s['price'])} ({_pct(a['upside'])} implied return). Within our "
        f"coverage universe, the name ranks **{a.get('relative_rating', 'n/a')}**.",
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
    """Key-financials exhibit: metrics as rows, fiscal years as columns —
    the standard research-note format. Rows appear only when the company
    reports the underlying data, so banks and industrials each get a table
    that makes sense for them."""
    fin = a["financials"]
    per_year = a["ratios"]["per_year"]
    years = sorted(per_year)[-5:]

    rev = fin["revenue"]
    growth = {y: rev[y] / rev[p] - 1 for y, p in zip(years[1:], years[:-1])
              if y in rev and p in rev and rev.get(p)}
    net_debt = {y: fin["long_term_debt"][y] - fin["cash"].get(y, 0)
                for y in years if y in fin["long_term_debt"]}
    # EBITDA derived the standard way: operating income + D&A. The row
    # drops automatically for filers (e.g. banks) missing either input.
    ebitda = {y: fin["operating_income"][y] + fin["depreciation"][y]
              for y in years
              if y in fin["operating_income"] and y in fin.get("depreciation", {})}
    ebitda_margin = {y: ebitda[y] / rev[y] for y in ebitda
                     if rev.get(y)}
    fcf = {y: per_year[y]["free_cash_flow"] for y in years
           if per_year.get(y, {}).get("free_cash_flow") is not None}

    def row(label, series, fmt):
        if not any(series.get(y) is not None for y in years):
            return None
        cells = [fmt(series[y]) if series.get(y) is not None else "—"
                 for y in years]
        return f"| {label} | " + " | ".join(cells) + " |"

    pct = lambda v: f"{v:+.1%}" if isinstance(v, float) else "—"
    pct0 = lambda v: f"{v:.1%}"
    rows = [
        row("Revenue", {y: rev.get(y) for y in years}, _bn),
        row("Revenue growth", growth, pct),
        row("EBITDA", ebitda, _bn),
        row("EBITDA margin", ebitda_margin, pct0),
        row("Operating margin",
            {y: per_year[y].get("operating_margin") for y in years}, pct0),
        row("Net income", {y: fin["net_income"].get(y) for y in years}, _bn),
        row("Net margin",
            {y: per_year[y].get("net_margin") for y in years}, pct0),
        row("Diluted EPS", {y: fin["eps_diluted"].get(y) for y in years},
            lambda v: f"${v:,.2f}"),
        row("Net interest income",
            {y: fin.get("net_interest_income", {}).get(y) for y in years}, _bn),
        row("Free cash flow", fcf, _bn),
        row("Return on equity",
            {y: per_year[y].get("roe") for y in years}, pct0),
        row("Net debt", net_debt, _bn),
        row("Shareholders' equity",
            {y: fin["total_equity"].get(y) for y in years}, _bn),
        row("Dividends paid",
            {y: fin.get("dividends_paid", {}).get(y) for y in years}, _bn),
    ]
    out = [
        "## Financial Analysis",
        "",
        "### Key financials (as filed with the SEC)",
        "",
        "| Fiscal year | " + " | ".join(str(y) for y in years) + " |",
        "|---|" + "---|" * len(years),
    ] + [r for r in rows if r]
    g = a["ratios"]
    out += ["", f"Revenue CAGR: {_pct(g['revenue_cagr_3y'])} (3y), "
                f"{_pct(g['revenue_cagr_5y'])} (5y). "
                f"Net income CAGR (5y): {_pct(g['net_income_cagr_5y'])}. "
                f"FCF CAGR (5y): {_pct(g['fcf_cagr_5y'])}."]
    return "\n".join(out)


def _quarterly_section(a: dict) -> str:
    q = a.get("quarterly") or {}
    rev = q.get("revenue", {})
    if len(rev) < 2:
        return None
    ni, eps = q.get("net_income", {}), q.get("eps_diluted", {})
    derived = set(q.get("_derived", []))
    out = ["### Recent quarters", "",
           "| Quarter ended | Revenue | Net income | Diluted EPS |",
           "|---|---|---|---|"]
    for end in rev:
        mark = "\\*" if end in derived else ""
        out.append(f"| {end}{mark} | {_bn(rev.get(end))} | {_bn(ni.get(end))} "
                   f"| {_m(eps.get(end)) if eps.get(end) is not None else '—'} |")
    if derived & set(rev):
        out += ["", "\\* Fiscal fourth quarters have no 10-Q of their own; "
                    "they are derived as the annual filing less the three "
                    "reported quarters. Quarterly EPS is not derived."]
    return "\n".join(out)


def _dcf_walk_section(a: dict) -> str:
    dcf = a["models"].get("dcf") or {}
    walk = dcf.get("walk")
    if not walk:
        return None
    ass = dcf["assumptions"]
    out = ["### DCF walk — the projection, year by year", "",
           f"The base free cash flow of {_bn(ass['fcf_base'])} is measured as "
           f"{ass.get('fcf_basis', 'standard')}. Growth fades from "
           f"{ass['initial_growth']:.1%} toward {ass['terminal_growth']:.1%}, "
           f"and each year is discounted at {ass['cost_of_equity']:.2%}.",
           "",
           "| Year | Growth | Free cash flow | Discount factor | Present value |",
           "|---|---|---|---|---|"]
    for w in walk:
        out.append(f"| {w['year']} | {w['growth']:+.1%} | {_bn(w['fcf'])} "
                   f"| {w['discount_factor']:.3f} | {_bn(w['present_value'])} |")
    out += ["",
            f"- Sum of explicit-period value: {_bn(dcf['pv_explicit'])}",
            f"- Terminal value: average of Gordon growth ({_bn(dcf['tv_gordon'])}) "
            f"and exit multiple ({_bn(dcf['tv_exit']) if dcf.get('tv_exit') else 'n/a'}), "
            f"discounted to {_bn(dcf['pv_terminal'])} "
            f"({dcf['terminal_share_of_value']:.0%} of total value)",
            f"- Less net debt {_bn(ass['net_debt'])} → equity value "
            f"{_bn(dcf.get('equity_value'))} → **{_m(dcf['per_share'])} per share**"]
    return "\n".join(out)


def _peer_comp_section(a: dict) -> str:
    peers = a.get("peer_multiples") or []
    if not peers:
        return None
    s = a["snapshot"]
    out = ["### Comparable companies", "",
           "| Company | Mkt cap | P/E (ttm) | P/E (fwd) | EV/EBITDA | P/B "
           "| Net margin | ROE |",
           "|---|---|---|---|---|---|---|---|"]

    def fmt(x, pat="{:.1f}"):
        # x == x filters NaN (NaN never equals itself)
        return pat.format(x) if x is not None and x == x else "—"

    out.append(f"| **{a['ticker']} (subject)** | {_bn(s['market_cap'])} "
               f"| {fmt(s['trailing_pe'])} | {fmt(s['forward_pe'])} | — "
               f"| {fmt(s['price_to_book'])} | — | — |")
    for p in peers:
        out.append(
            f"| {p.get('name') or p['ticker']} | {_bn(p.get('market_cap'))} "
            f"| {fmt(p.get('trailing_pe'))} | {fmt(p.get('forward_pe'))} "
            f"| {fmt(p.get('ev_to_ebitda'))} | {fmt(p.get('price_to_book'))} "
            f"| {fmt(p.get('profit_margin'), '{:.1%}')} "
            f"| {fmt(p.get('return_on_equity'), '{:.1%}')} |")
    out += ["", "Medians of this table drive the peer-comps lens and the "
                "DCF exit multiple. Peer selection is disclosed in "
                "universe.py and versioned."]
    return "\n".join(out)


def _esg_section(a: dict) -> str:
    s = a["snapshot"]
    fin = a["financials"]
    div_years = len(fin.get("dividends_paid") or {})
    lines = ["## ESG & Governance", "",
             "Free primary ESG data is limited; this section reports only "
             "what can be grounded in market and filing data, and flags "
             "sector-specific exposures qualitatively."]
    facts = []
    if s.get("held_by_institutions"):
        facts.append(f"- Institutional ownership: {s['held_by_institutions']:.0%} "
                     "— professional holders with governance voting power.")
    if s.get("float_shares") and s.get("shares_outstanding"):
        facts.append(f"- Public float: {s['float_shares'] / s['shares_outstanding']:.0%} "
                     "of shares outstanding.")
    if div_years:
        facts.append(f"- Dividend record: cash returned to shareholders in "
                     f"each of the last {div_years} fiscal years on file — "
                     "a capital-discipline signal.")
    env_notes = {
        "beverage_commodity": "- Environmental exposure: packaging (aluminum, "
                              "plastic) and water sourcing are the material "
                              "environmental themes for beverage producers.",
        "consumer_hardware": "- Environmental/social exposure: hardware supply "
                             "chains (sourcing, labor, e-waste) are the "
                             "material themes for device makers.",
        "bank": "- Governance exposure: regulatory capital and risk oversight "
                "are the material governance themes for banks.",
        "holdco_cash": "- Governance note: key-person and succession risk are "
                       "material for founder-led holding companies.",
        "enterprise_software": "- Social exposure: data privacy and AI "
                               "governance are the material themes for cloud "
                               "platforms.",
    }
    for t in a["profile"].get("traits", []):
        if t in env_notes:
            facts.append(env_notes[t])
    return "\n".join(lines + [""] + facts) if facts else "\n".join(lines)


def _valuation_section(a: dict) -> str:
    weights_note = {
        "dcf_comps": "Weights: discounted cash flow 40%, peer comparables "
                     "30%, own historical multiple 30%.",
        "bank": "The target averages the three lenses equally.",
        "conglomerate": "The target averages the two lenses equally.",
    }.get(a["profile"]["method"], "")
    out = ["## Valuation", "",
           "We value the company using several independent methods, each of "
           "which can be wrong for different reasons. Close agreement across "
           "methods increases our confidence in the blended target. A wide "
           "spread indicates the value is genuinely uncertain, and we hold "
           f"the target with lower conviction accordingly. {weights_note}", ""]
    for name, m in a["models"].items():
        title = MODEL_TITLES.get(name, name.replace("_", " ").title())
        if not m.get("per_share"):
            out += [f"**{title}:** not applicable "
                    f"({m.get('reason', 'no value')}).", ""]
            continue
        out += [f"### {title} — {_m(m['per_share'])} per share", "",
                "| Assumption | Value |", "|---|---|"]
        for k, v in (m.get("assumptions") or {}).items():
            label = k.replace("_", " ").capitalize()
            out.append(f"| {label} | {_fmt_val(v)} |")
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


def _conclusion_section(a: dict, narrative: dict) -> str:
    """Closing decision card: the whole report restated in five lines.
    Computed from engine output so it can never drift from the numbers."""
    s = a["snapshot"]
    vals = [m["per_share"] for m in a["models"].values() if m.get("per_share")]
    spread = (max(vals) / min(vals)) if vals and min(vals) > 0 else None
    conviction = ("high" if spread and spread < 1.5 else
                  "moderate" if spread and spread < 2.5 else "low")
    lens_vals = [_m(m["per_share"]) for m in a["models"].values()
                 if m.get("per_share")]
    lens_line = (", ".join(lens_vals[:-1]) + ", and " + lens_vals[-1]
                 if len(lens_vals) > 1 else "".join(lens_vals))
    out = ["## Investment Conclusion", ""]
    headline = None
    if narrative.get("thesis"):
        first = narrative["thesis"].strip().splitlines()[0]
        if first.startswith("**"):
            headline = first.strip("* ")
    if headline:
        out.append(f"*{headline}*")
        out.append("")
    overlay_note = (f" A disclosed analyst overlay adjusts this to "
                    f"{_m(a['target_price'])}." if a["overlay"]["overlays"]
                    else "")
    conviction_line = (
        f"- **Conviction:** {conviction}. The widest and narrowest lenses "
        f"differ by {spread:,.1f}x. Tighter agreement between independent "
        f"methods means higher confidence in the target." if spread else
        "- **Conviction:** not assessed. Too few models produced a value.")
    out += [
        f"- **The call:** {a['rating']}. Our target is {_m(a['target_price'])} "
        f"against a current price of {_m(s['price'])}, an implied return of "
        f"{_pct(a['upside'])}. Street consensus stands at "
        f"{_m(s['street_target_mean'])}.",
        f"- **The evidence:** our independent lenses value the shares at "
        f"{lens_line}. The blended base case is "
        f"{_m(a['base_target'])}.{overlay_note}",
        conviction_line,
        f"- **Within coverage:** ranked {a.get('relative_rating', 'n/a')}, "
        f"#{a.get('relative_rank', '—')} among the names we cover.",
        "- **Standing review:** we re-examine the rating at every quarterly "
        "report against the triggers listed under Catalysts. Calls and "
        "targets are logged, dated, and never rewritten.",
    ]
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


def load_narrative(ticker: str) -> dict:
    """Written analysis sections from narratives/<TICKER>.md.

    The file is human-edited (drafted by the analyst team, reviewed line by
    line) and versioned; sections are delimited by
    `<!-- section: name -->` markers. Reports regenerate around the prose,
    so numbers refresh without touching the written analysis.
    """
    path = NARRATIVES_DIR / f"{ticker}.md"
    if not path.exists():
        return {}
    import re
    parts = re.split(r"<!--\s*section:\s*([a-z_]+)\s*-->", path.read_text())
    # parts: [preamble, name, content, name, content, ...]
    return {parts[i]: parts[i + 1].strip()
            for i in range(1, len(parts) - 1, 2)}


def _make_charts(a: dict) -> dict:
    """All report charts for one company; failures degrade to no chart."""
    tk = a["ticker"]
    out = {}
    try:
        hist = market.get_history(tk, period="5y")["Close"]
        out["price"] = charts.price_chart(
            tk, hist, a["target_price"], a["snapshot"]["street_target_mean"])
    except Exception:
        pass
    try:
        out["fundamentals"] = charts.fundamentals_chart(
            tk, a["ratios"]["per_year"])
        out["margins"] = charts.margins_chart(tk, a["ratios"]["per_year"])
    except Exception:
        pass
    try:
        out["sensitivity"] = charts.sensitivity_heatmap(tk, a.get("sensitivity"))
    except Exception:
        pass
    try:
        out["quarterly"] = charts.quarterly_chart(tk, a.get("quarterly") or {})
    except Exception:
        pass
    return {k: v for k, v in out.items() if v}


def _img(path: str, alt: str) -> str:
    return f"![{alt}]({path})"


def generate_report(a: dict, dashboard, chart_paths: dict = None) -> str:
    c = chart_paths or {}
    n = load_narrative(a["ticker"])
    parts = [_header(a)]
    if "price" in c:
        parts.append(_img(c["price"], "Share price, five years"))
    parts.append(_investment_summary(a))
    if "thesis" in n:
        parts.append("## The Investment Thesis\n\n" + n["thesis"])
    parts.append(_macro_section(a, dashboard))
    if "macro" in c:
        parts.append(_img(c["macro"], "Economic backdrop"))
    parts.append(_business_section(a))
    if "segments" in n:
        parts.append("### Segments and revenue drivers\n\n" + n["segments"])
    if "industry" in n:
        parts.append("## Industry Overview and Competitive Positioning\n\n"
                     + n["industry"])
    if "moat" in n:
        parts.append("### The moat — durability of the franchise\n\n"
                     + n["moat"])
    parts.append(_financials_section(a))
    if "fundamentals" in c:
        parts.append(_img(c["fundamentals"], "Revenue and cash generation"))
    if "margins" in c:
        parts.append(_img(c["margins"], "Profit margins"))
    q = _quarterly_section(a)
    if q:
        parts.append(q)
    if "quarterly" in c:
        parts.append(_img(c["quarterly"], "Quarterly revenue"))
    if "management" in n:
        parts.append("## Management and Capital Allocation\n\n"
                     + n["management"])
    parts.append(_valuation_section(a))
    walk = _dcf_walk_section(a)
    if walk:
        parts.append(walk)
    peers = _peer_comp_section(a)
    if peers:
        parts.append(peers)
    if "sensitivity" in c:
        parts.append(_img(c["sensitivity"], "Sensitivity heatmap"))
    if "catalysts" in n:
        parts.append("## Catalysts and What Would Change Our Mind\n\n"
                     + n["catalysts"])
    parts += [_risks_section(a), _esg_section(a),
              _conclusion_section(a, n), _disclosures(a)]
    return "\n\n".join(parts) + "\n"


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

    from equity_lens.reports import html_report

    # Shared economic-backdrop panel, generated once per run.
    try:
        cpi = macro.get_series("CPIAUCSL")
        macro_chart = charts.macro_panel(
            macro.get_series("FEDFUNDS"), macro.get_series("DGS10"),
            macro.get_series("T10Y2Y"), ((cpi / cpi.shift(12) - 1) * 100).dropna(),
            macro.get_series("UNRATE"))
    except Exception:
        macro_chart = None

    for tk, a in results.items():
        path = REPORTS_DIR / f"{tk}_{today}.md"
        chart_paths = _make_charts(a)
        if macro_chart:
            chart_paths["macro"] = macro_chart
        report_md = generate_report(a, dashboard, chart_paths)
        path.write_text(report_md)
        written.append(path)
        written.append(html_report.write_html(a, report_md, today))

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
