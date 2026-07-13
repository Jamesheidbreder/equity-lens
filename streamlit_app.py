"""Equity-Lens dashboard.

Run locally:  streamlit run streamlit_app.py
Deployed on Streamlit Community Cloud from the GitHub repo.

The dashboard is a window onto the same engine that writes the reports —
it calls equity_lens.analysis directly, so numbers here and numbers in the
committed reports come from identical code. Layout principle: plain-English
verdict first, math behind expanders.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import pandas as pd
import streamlit as st

from equity_lens.universe import UNIVERSE

st.set_page_config(page_title="Equity-Lens", page_icon="📊", layout="wide")

# Apple-inflected fintech look: system font stack, card-style metric tiles
# with soft depth, quiet chrome. Theme colors live in .streamlit/config.toml.
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] * {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI",
               Roboto, Helvetica, Arial, sans-serif;
}
h1, h2, h3 { letter-spacing: -0.02em; }
div[data-testid="stMetric"] {
  background: #ffffff;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 14px;
  padding: 14px 16px 12px 16px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 6px 16px rgba(0, 0, 0, 0.04);
}
div[data-testid="stMetric"] label p { color: #6e6e73; font-size: 0.82rem; }
div[data-testid="stExpander"] {
  background: #ffffff;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}
div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
button[data-baseweb="tab"] { font-weight: 500; }
</style>
""", unsafe_allow_html=True)

CALLS_CSV = REPO_ROOT / "data" / "calls.csv"
REPORTS_DIR = REPO_ROOT / "reports"

RATING_BADGE = {"BUY": "🟢 BUY", "HOLD": "🟡 HOLD", "SELL": "🔴 SELL",
                "NR": "⚪ Not rated"}

MODEL_EXPLAINERS = {
    "dcf": ("Cash-flow value",
            "Add up all the cash we expect the business to generate over time, "
            "translated into today's dollars."),
    "comps": ("Priced like its peers",
              "What the stock would cost if the market priced it like similar "
              "companies."),
    "own_multiple": ("Priced like its own history",
                     "What the stock would cost at the earnings multiple it has "
                     "averaged over the past 5 years."),
    "justified_pb": ("Balance-sheet value",
                     "What the company's net assets are worth, given the "
                     "returns it earns on them."),
    "peer_pb": ("Balance sheet, priced like peers",
                "The same net assets, valued at the multiple comparable "
                "companies trade at."),
}


# ---------- cached engine calls ----------

@st.cache_data(ttl=3600, show_spinner="Running the analysis engine — pulling live SEC filings, market and Fed data (~30s)...")
def run_analysis(ticker: str) -> dict:
    from equity_lens.analysis.engine import analyze
    return analyze(ticker)


@st.cache_data(ttl=900, show_spinner=False)
def current_price(ticker: str):
    import time
    import yfinance as yf
    for _ in range(3):  # Yahoo's chart API intermittently returns nothing
        try:
            h = yf.Ticker(ticker).history(period="5d")["Close"]
            if len(h):
                return float(h.iloc[-1])
        except Exception:
            pass
        time.sleep(1)
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def price_history(ticker: str, period: str = "5y") -> pd.Series:
    import time
    from equity_lens.data import market
    for _ in range(3):
        try:
            h = market.get_history(ticker, period=period)["Close"]
            if len(h):
                return h
        except Exception:
            pass
        time.sleep(1)
    return pd.Series(dtype=float)


@st.cache_data(ttl=3600, show_spinner=False)
def macro_series(series_id: str, years: int = 10) -> pd.Series:
    from equity_lens.data import macro
    return macro.get_series(series_id, years=years)


def load_calls() -> pd.DataFrame:
    if not CALLS_CSV.exists():
        return pd.DataFrame()
    return pd.read_csv(CALLS_CSV, parse_dates=["date"])


# Chart colors: validated categorical pair (dataviz palette slots 1-2).
C_BLUE, C_AQUA = "#2a78d6", "#1baf7a"


def latest_and_prior(series: dict):
    """(latest value, prior-year value) from a {year: value} dict."""
    vals = list(series.values()) if series else []
    return (vals[-1] if vals else None,
            vals[-2] if len(vals) > 1 else None)


def yoy_delta(latest, prior):
    """Streamlit metric delta string: change vs prior fiscal year."""
    if latest is None or not prior:
        return None
    return f"{latest / prior - 1:+.1%} vs prior year"


def bn(x):
    return f"${x / 1e9:,.1f}B" if x is not None else "n/a"


def verdict_sentence(a: dict) -> str:
    """The whole analysis in one plain-English sentence."""
    up = a["upside"]
    name = a["profile"]["name"]
    if a["rating"] == "BUY":
        stance = (f"trades **below our estimate of fair value** — we see "
                  f"roughly **{up:+.0%}** upside")
    elif a["rating"] == "SELL":
        stance = (f"trades **above our estimate of fair value** — by roughly "
                  f"**{abs(up):.0%}**")
    else:
        stance = "trades **close to our estimate of fair value**"
    return (f"{RATING_BADGE[a['rating']]} — **{name}** {stance}. "
            f"Our fair-value estimate is **${a['target_price']:,.2f}** per share; "
            f"the market price is **${a['snapshot']['price']:,.2f}**.")


# ---------- header ----------

st.title("📊 Equity-Lens")
st.caption(
    "Independent equity research, computed rather than opined — fair-value "
    "estimates built from SEC filings, market data, and Federal Reserve "
    "statistics. Every call is dated and kept on a public scorecard, right "
    "or wrong. "
    "[GitHub](https://github.com/Jamesheidbreder/equity-lens) · "
    "Educational project, not investment advice."
)

(tab_overview, tab_company, tab_macro, tab_scorecard, tab_reports,
 tab_method) = st.tabs(
    ["Coverage", "Company Analysis", "Macro Monitor", "Scorecard",
     "Reports", "How It Works"])


# ---------- Coverage tab ----------

with tab_overview:
    st.subheader("Coverage")
    st.markdown(
        "Five companies under coverage, ranked most to least attractive. "
        "*Our target* is the fair value our models compute; *street target* "
        "is the Wall Street consensus — shown for comparison, never used as "
        "an input.")
    calls = load_calls()
    if calls.empty:
        st.info("No calls logged yet — generate reports to start the record.")
    else:
        latest = calls.sort_values("date").groupby("ticker").tail(1).copy()
        latest["current"] = latest["ticker"].map(current_price)
        latest["upside"] = latest["final_target"] / latest["current"] - 1
        rank_order = {"Top Pick": 0, "Overweight": 1, "Neutral": 2,
                      "Underweight": 3, "Least Preferred": 4}
        latest = latest.sort_values(by="relative_rating",
                                    key=lambda s: s.map(rank_order))
        latest["company"] = latest["ticker"].map(
            lambda t: UNIVERSE.get(t, {}).get("name", t))
        latest["rating"] = latest["rating"].map(RATING_BADGE)
        show = latest[["relative_rating", "company", "ticker", "rating",
                       "current", "final_target", "upside", "street_target"]
                      ].rename(columns={
            "relative_rating": "our ranking", "current": "price now",
            "final_target": "our target", "street_target": "street target"})
        st.dataframe(
            show.style.format({
                "price now": "${:.2f}", "our target": "${:.2f}",
                "street target": "${:.2f}", "upside": "{:+.1%}"}),
            width="stretch", hide_index=True)

        with st.expander("How do I read this table?"):
            st.markdown("""
- **Our ranking** — a forced ranking within our coverage: even if the whole
  market looks expensive, something is still first choice. *Top Pick* = own
  first; *Least Preferred* = own last.
- **Rating** — the absolute question, *"is it cheap?"*: 🟢 BUY means we think
  it's worth 10%+ more than its price, 🔴 SELL means 10%+ less, 🟡 HOLD is
  in between.
- **Upside** — the gap between our target and today's price. Positive =
  we think it's underpriced.
- **Street target** — the average of professional analysts' targets. Where we
  differ from the street, that disagreement is deliberate and documented —
  their number is never an input to ours.
""")


# ---------- Company Analysis tab ----------

with tab_company:
    tk = st.selectbox("Pick a company", list(UNIVERSE),
                      format_func=lambda t: f"{UNIVERSE[t]['name']} ({t})")
    a = run_analysis(tk)
    s = a["snapshot"]

    st.markdown(f"### {verdict_sentence(a)}")
    if a["rating"] == "SELL" and s["street_target_mean"]:
        st.caption(
            "Most street analysts rate this stock more favorably. See *How It "
            "Works* for why our estimates run more conservative than the "
            "street's.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Market price", f"${s['price']:,.2f}",
              help="What one share costs right now.")
    c2.metric("Our fair value", f"${a['target_price']:,.2f}",
              f"{a['upside']:+.1%} vs price",
              help="What our models say a share is actually worth. The little "
                   "number shows the gap vs the market price.")
    c3.metric("Rating", a["rating"],
              help="BUY = we think it's worth 10%+ more than its price. "
                   "SELL = 10%+ less. HOLD = roughly fair.")
    c4.metric("Street average", f"${s['street_target_mean']:,.2f}"
              if s["street_target_mean"] else "n/a",
              help="The average price target of professional Wall Street "
                   "analysts covering this stock. Shown for comparison — "
                   "never used in our math.")

    # ---- The financial statements, at a glance ----
    st.markdown("#### From the financial statements — latest fiscal year")
    st.caption("As filed with the SEC in the company's audited annual "
               "report (10-K). Hover any figure for a plain-English "
               "definition.")
    fin = a["financials"]
    rev, rev_p = latest_and_prior(fin["revenue"])
    ni, ni_p = latest_and_prior(fin["net_income"])
    eps, eps_p = latest_and_prior(fin["eps_diluted"])
    fcf_series = {y: r["free_cash_flow"] for y, r in
                  a["ratios"]["per_year"].items() if "free_cash_flow" in r}
    fcf, fcf_p = latest_and_prior(fcf_series)
    nii, nii_p = latest_and_prior(fin.get("net_interest_income", {}))
    cash, _ = latest_and_prior(fin["cash"])
    debt, _ = latest_and_prior(fin["long_term_debt"])
    equity, _ = latest_and_prior(fin["total_equity"])
    divs, _ = latest_and_prior(fin.get("dividends_paid", {}))

    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Revenue", bn(rev), yoy_delta(rev, rev_p),
              help="Total sales for the year — the top line of the income "
                   "statement.")
    f2.metric("Net profit", bn(ni), yoy_delta(ni, ni_p),
              help="What's left after all costs and taxes — the bottom line. "
                   f"That's {ni / rev:.0%} of every sales dollar."
              if ni and rev else "The bottom line of the income statement.")
    f3.metric("Earnings per share", f"${eps:,.2f}" if eps else "n/a",
              yoy_delta(eps, eps_p),
              help="Profit divided by shares — your slice of the earnings "
                   "for each share you own.")
    if fcf is not None:
        f4.metric("Free cash flow", bn(fcf), yoy_delta(fcf, fcf_p),
                  help="Cash generated after running and reinvesting in the "
                       "business — the cash that could be paid out to owners.")
    else:
        f4.metric("Net interest income", bn(nii), yoy_delta(nii, nii_p),
                  help="A bank's core profit engine: interest earned on loans "
                       "minus interest paid on deposits.")

    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Cash held", bn(cash),
              help="Cash and equivalents on the balance sheet — the rainy-day "
                   "fund and war chest.")
    g2.metric("Long-term debt", bn(debt),
              help="Money borrowed and owed beyond the next year, from the "
                   "balance sheet.")
    g3.metric("Shareholders' equity", bn(equity),
              help="Assets minus everything owed — the owners' stake, also "
                   "called book value.")
    yield_note = (f"{s['dividend_yield']:.2f}% yield at today's price"
                  if s["dividend_yield"] else "no regular dividend")
    g4.metric("Dividends paid", bn(divs) if divs else "n/a",
              help="Cash actually mailed to shareholders during the year "
                   f"({yield_note}).")

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Valuation — three independent lenses")
        st.markdown("Each lens values the company independently; the target "
                    "blends them. If they disagree sharply, that itself is "
                    "information.")
        rows = []
        for name, m in a["models"].items():
            if m.get("per_share"):
                label, blurb = MODEL_EXPLAINERS.get(name, (name, ""))
                rows.append({"lens": label, "value": m["per_share"]})
                st.markdown(f"- **{label}: ${m['per_share']:,.0f}** — {blurb}")
        mdf = pd.DataFrame(rows).set_index("lens")
        mdf.loc["→ blended fair value"] = a["base_target"]
        if a["overlay"]["overlays"]:
            mdf.loc["→ after analyst judgment"] = a["target_price"]
        mdf.loc["market price today"] = s["price"]
        st.bar_chart(mdf, horizontal=True)

        if a["overlay"]["overlays"]:
            with st.expander("Analyst judgment applied — dated and disclosed"):
                st.markdown(
                    "Some things — like unproven new products — can't be "
                    "computed from filings. When we choose to credit them, "
                    "the judgment is written down, dated, and shown here:")
                for o in a["overlay"]["overlays"]:
                    st.markdown(f"**{o['date']} — {o['value']:+.0%} to fair "
                                f"value** · review due {o.get('review_by', 'n/a')}"
                                f"\n\n{o['rationale']}")

        with st.expander("Macro conditions in the model"):
            st.markdown(
                "The engine automatically leans on its assumptions when the "
                "economy shifts (every adjustment is small and capped):")
            if a["macro_adjustments"]:
                for adj in a["macro_adjustments"]:
                    st.markdown(f"- **{adj['rule'].replace('_', ' ').title()}** "
                                f"— {adj['reading']}. {adj['rationale']} "
                                f"*(effect: {adj['adjustment']:+.2%})*")
            else:
                st.markdown("None currently apply to this company.")

        sens = a.get("sensitivity")
        if sens:
            with st.expander("Sensitivity — how the estimate moves if assumptions shift"):
                st.markdown(
                    f"No forecast is exact, so here's our fair value if the "
                    f"key assumptions shift: rows flex **{sens['x_label']}**, "
                    f"columns flex the **required return**. Green = higher "
                    f"value, red = lower.")
                sdf = pd.DataFrame(
                    sens["grid"],
                    index=[f"{x:.1%}" for x in sens["x_values"]],
                    columns=[f"{c:.1%}" for c in sens["coe_values"]])
                st.dataframe(sdf.style
                             .background_gradient(cmap="RdYlGn", axis=None)
                             .format("${:,.0f}"), width="stretch")

    with right:
        st.subheader("Share price — five years")
        hist = price_history(tk)
        if len(hist):
            st.line_chart(hist, height=220, color=C_BLUE)
        else:
            st.caption("Price chart temporarily unavailable.")

        st.subheader("Business trends")
        per_year = a["ratios"]["per_year"]
        fy = pd.DataFrame(per_year).T.sort_index()
        if "revenue" in fy:
            st.caption("Revenue ($B) — is the business growing?")
            st.bar_chart(fy["revenue"] / 1e9, height=180, color=C_BLUE)
        if "free_cash_flow" in fy:
            st.caption("Free cash flow ($B) — does growth turn into cash?")
            st.bar_chart(fy["free_cash_flow"] / 1e9, height=180, color=C_AQUA)
        margins = fy[[c for c in ("net_margin", "operating_margin")
                      if c in fy]].rename(columns={
            "net_margin": "net margin", "operating_margin": "operating margin"})
        if not margins.empty:
            st.caption("Profit margins — how many cents of each sales dollar "
                       "become profit")
            st.line_chart(margins, height=180,
                          color=[C_AQUA, C_BLUE][:margins.shape[1]])


# ---------- Macro Monitor tab ----------

with tab_macro:
    st.subheader("Macro monitor")
    st.markdown(
        "The Federal Reserve data the valuation engine reads, charted. These "
        "series feed the models directly — see *How It Works* and the "
        "[macro catalog](https://github.com/Jamesheidbreder/equity-lens/blob/main/MACRO_CATALOG.md).")

    mc1, mc2 = st.columns(2)
    with mc1:
        st.caption("**Interest rates (%)** — the gravity of all valuations: "
                   "higher rates pull every fair value down. The 10-year "
                   "Treasury is the base of our required return.")
        rates = pd.DataFrame({
            "Fed funds rate": macro_series("FEDFUNDS"),
            "10-year Treasury": macro_series("DGS10"),
        })
        st.line_chart(rates, height=220, color=[C_BLUE, C_AQUA])

        st.caption("**Yield-curve slope (10y − 2y, %)** — banks earn this "
                   "spread. Below zero (inverted) is the classic recession "
                   "warning and squeezes bank profits.")
        st.line_chart(macro_series("T10Y2Y"), height=180, color=C_BLUE)

        st.caption("**Inflation (% change vs year ago)** — eats real returns "
                   "and squeezes margins for companies that can't raise "
                   "prices as fast as their costs.")
        cpi = macro_series("CPIAUCSL")
        st.line_chart((cpi / cpi.shift(12) - 1) * 100, height=180, color=C_BLUE)

    with mc2:
        st.caption("**Unemployment rate (%)** — consumer health; when it "
                   "rises, spending and loan repayment follow it down.")
        st.line_chart(macro_series("UNRATE"), height=220, color=C_BLUE)

        st.caption("**Consumer sentiment (U. Michigan)** — how households "
                   "feel, which leads what they buy, especially big-ticket "
                   "items.")
        st.line_chart(macro_series("UMCSENT"), height=180, color=C_BLUE)

        st.caption("**Credit spreads (Baa vs Treasury, %)** — the bond "
                   "market's fear gauge. Wider = investors demanding more "
                   "for risk; our engine raises its required returns when "
                   "this runs above normal.")
        st.line_chart(macro_series("BAA10Y"), height=180, color=C_BLUE)


# ---------- Scorecard tab ----------

with tab_scorecard:
    st.subheader("Track record")
    st.markdown(
        "Every call, dated, with performance since. The log is append-only "
        "and version-controlled — **the record cannot be rewritten**, and "
        "wrong calls stay visible.")
    calls = load_calls()
    if calls.empty:
        st.info("No calls logged yet.")
    else:
        sc = calls.copy()
        sc["current"] = sc["ticker"].map(current_price)
        sc["stock since call"] = sc["current"] / sc["price"] - 1

        def direction(row):
            if row["rating"] == "BUY":
                return "✅ on track" if row["stock since call"] > 0 else "❌ against us"
            if row["rating"] == "SELL":
                return "✅ on track" if row["stock since call"] < 0 else "❌ against us"
            return "✅ on track" if abs(row["stock since call"]) < 0.10 else "❌ against us"

        sc["status"] = sc.apply(direction, axis=1)

        def progress_to_target(row):
            """How far the stock has traveled toward our target since the
            call, as a fraction of the move we predicted."""
            predicted = row["final_target"] - row["price"]
            if not predicted:
                return None
            return (row["current"] - row["price"]) / predicted

        sc["progress to target"] = sc.apply(progress_to_target, axis=1)
        sc["rating"] = sc["rating"].map(RATING_BADGE)
        show = sc[["date", "ticker", "rating", "price", "final_target",
                   "current", "stock since call", "progress to target",
                   "status"]].rename(columns={
            "price": "price at call", "final_target": "our target",
            "current": "price now"})
        show["date"] = show["date"].dt.date
        st.dataframe(
            show.style.format({
                "price at call": "${:.2f}", "our target": "${:.2f}",
                "price now": "${:.2f}", "stock since call": "{:+.1%}",
                "progress to target": "{:+.0%}"}),
            width="stretch", hide_index=True)
        st.caption(
            "*Progress to target*: how much of the move we predicted has "
            "happened. +100% = target reached; negative = the stock moved "
            "against the call.")

        n = len(sc)
        right_n = int((sc["status"] == "✅ on track").sum())
        age_days = (pd.Timestamp.now() - sc["date"].min()).days
        m1, m2, m3 = st.columns(3)
        m1.metric("Calls on record", n,
                  help="Each dated rating + target we've published.")
        m2.metric("Calls on track", f"{right_n}/{n}",
                  help="BUYs where the stock is up since the call, SELLs "
                       "where it's down, HOLDs that stayed within ±10%.")
        m3.metric("Oldest call", f"{age_days} days",
                  help="Track records need time. Under ~90 days this is "
                       "weather, not climate.")
        if age_days < 90:
            st.caption("**Note:** a record this young is statistical noise. It is "
                       "shown regardless — public scorekeeping is the point.")


# ---------- Reports tab ----------

with tab_reports:
    st.subheader("Research reports")
    st.markdown(
        "The complete written research behind each call, in the standard "
        "institutional format: thesis, macro backdrop, financials, "
        "valuation, and risks.")
    files = sorted(REPORTS_DIR.glob("*.md"), reverse=True)
    if not files:
        st.info("No reports generated yet.")
    else:
        pick = st.selectbox("Choose a report", files,
                            format_func=lambda p: p.stem.replace("_", " — "))
        st.markdown(pick.read_text())


# ---------- How It Works tab ----------

with tab_method:
    st.subheader("How Equity-Lens works")
    st.markdown("""
**The one-paragraph version:** we pull companies' official numbers from
their SEC filings, current prices from the market, and economic data from
the Federal Reserve. Code — not opinion — turns those into an estimate of
what each share is worth. When the estimate differs from the market price,
that's a call, and every call goes on a public scorecard.

**Why our numbers run lower than Wall Street's:** analyst targets usually
give full credit to exciting stories (new products, AI plans) before the
cash shows up. Our engine only pays for cash flows that exist, plus a
disclosed, written "judgment overlay" when we deliberately choose to credit
part of a story. The gap between our target and the street's is therefore
a measurement of how much story is in the price.
""")
    with st.expander("The three valuation lenses, in plain English"):
        st.markdown("""
1. **Cash-flow value (DCF).** A business is worth the cash it will hand its
   owners over its lifetime, translated to today's dollars (money later is
   worth less than money now).
2. **Priced like its peers.** If similar companies sell for 20× their annual
   earnings, what would this one cost at that multiple?
3. **Priced like its own history.** Great brands always trade at a premium;
   this lens asks what the stock costs at *its own* usual premium rather
   than punishing it for being popular.

Banks and holding companies get different math (balance-sheet based) because
their businesses genuinely work differently — deposits aren't debt, they're
raw material.
""")
    with st.expander("Glossary — the jargon, translated"):
        st.markdown("""
- **Fair value / target price** — what we compute one share is worth.
- **Upside** — the % gap between fair value and today's price.
- **Market cap** — the price of the whole company (share price × shares).
- **P/E (price-to-earnings)** — how many dollars you pay for $1 of annual
  profit. Higher = more expensive (or more loved).
- **Free cash flow** — profit you could actually take out of the business
  after paying to run and grow it.
- **ROE (return on equity)** — profit as a % of shareholders' money in the
  company. A report card for how hard the owners' capital works.
- **Cost of equity / required return** — the yearly return that makes
  holding this stock's risk worthwhile.
- **Terminal value** — a DCF's estimate of everything beyond year 5,
  compressed into one number.
- **Book value** — assets minus debts; what's left if the company were
  liquidated at balance-sheet prices.
""")
    st.markdown(
        "Full methodology, macro-linkage catalog, and all source code: "
        "[github.com/Jamesheidbreder/equity-lens]"
        "(https://github.com/Jamesheidbreder/equity-lens)")
