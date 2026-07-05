"""Equity-Lens dashboard.

Run locally:  streamlit run streamlit_app.py
Deployed on Streamlit Community Cloud from the GitHub repo.

The dashboard is a window onto the same engine that writes the reports —
it calls equity_lens.analysis directly, so numbers here and numbers in the
committed reports come from identical code.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import pandas as pd
import streamlit as st

from equity_lens.universe import UNIVERSE

st.set_page_config(page_title="Equity-Lens", page_icon="📊", layout="wide")

CALLS_CSV = REPO_ROOT / "data" / "calls.csv"
REPORTS_DIR = REPO_ROOT / "reports"


# ---------- cached engine calls ----------

@st.cache_data(ttl=3600, show_spinner="Running the analysis engine (live SEC/FRED/market data)...")
def run_analysis(ticker: str) -> dict:
    from equity_lens.analysis.engine import analyze
    return analyze(ticker)


@st.cache_data(ttl=900, show_spinner=False)
def current_price(ticker: str):
    import yfinance as yf
    h = yf.Ticker(ticker).history(period="5d")["Close"]
    return float(h.iloc[-1]) if len(h) else None


@st.cache_data(ttl=3600, show_spinner=False)
def price_history(ticker: str, period: str = "5y") -> pd.Series:
    from equity_lens.data import market
    return market.get_history(ticker, period=period)["Close"]


def load_calls() -> pd.DataFrame:
    if not CALLS_CSV.exists():
        return pd.DataFrame()
    return pd.read_csv(CALLS_CSV, parse_dates=["date"])


# ---------- header ----------

st.title("📊 Equity-Lens")
st.caption(
    "Automated equity research from primary sources — SEC EDGAR, Yahoo Finance, "
    "FRED. Every number is computed deterministically; every call is on the "
    "public record. [GitHub](https://github.com/Jamesheidbreder/equity-lens) · "
    "Educational project, not investment advice."
)

tab_overview, tab_company, tab_scorecard, tab_reports, tab_method = st.tabs(
    ["Coverage", "Company Analysis", "Scorecard", "Reports", "Methodology"])


# ---------- Coverage tab ----------

with tab_overview:
    calls = load_calls()
    if calls.empty:
        st.info("No calls logged yet — generate reports to start the record.")
    else:
        latest = calls.sort_values("date").groupby("ticker").tail(1).copy()
        latest["current"] = latest["ticker"].map(current_price)
        latest["implied upside"] = latest["final_target"] / latest["current"] - 1
        rank_order = {"Top Pick": 0, "Overweight": 1, "Neutral": 2,
                      "Underweight": 3, "Least Preferred": 4}
        latest = latest.sort_values(by="relative_rating",
                                    key=lambda s: s.map(rank_order))
        show = latest[["ticker", "rating", "relative_rating", "date", "price",
                       "final_target", "current", "implied upside",
                       "street_target"]].rename(columns={
            "rating": "rating (abs)", "relative_rating": "relative",
            "date": "call date", "price": "price at call",
            "final_target": "our target", "current": "price now",
            "street_target": "street target"})
        show["call date"] = show["call date"].dt.date
        st.dataframe(
            show.style.format({
                "price at call": "${:.2f}", "our target": "${:.2f}",
                "price now": "${:.2f}", "street target": "${:.2f}",
                "implied upside": "{:+.1%}"}),
            width="stretch", hide_index=True)
        st.caption(
            "Absolute rating asks *is it cheap vs. our value estimate?* "
            "(BUY > +10% upside, SELL < −10%). Relative rating asks *which "
            "would we own first?* — forced ranking within coverage.")


# ---------- Company Analysis tab ----------

with tab_company:
    tk = st.selectbox("Covered company", list(UNIVERSE),
                      format_func=lambda t: f"{t} — {UNIVERSE[t]['name']}")
    a = run_analysis(tk)
    s = a["snapshot"]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Price", f"${s['price']:,.2f}")
    c2.metric("Target", f"${a['target_price']:,.2f}",
              f"{a['upside']:+.1%} vs price")
    c3.metric("Rating", a["rating"])
    c4.metric("Street target", f"${s['street_target_mean']:,.2f}"
              if s["street_target_mean"] else "n/a")
    c5.metric("Cost of equity", f"{a['cost_of_equity']:.2%}")

    left, right = st.columns(2)

    with left:
        st.subheader("Valuation models")
        rows = [{"model": name.replace("_", " "), "value": m["per_share"]}
                for name, m in a["models"].items() if m.get("per_share")]
        mdf = pd.DataFrame(rows).set_index("model")
        mdf.loc["blended target"] = a["base_target"]
        if a["overlay"]["overlays"]:
            mdf.loc["with overlay"] = a["target_price"]
        mdf.loc["market price"] = s["price"]
        st.bar_chart(mdf, horizontal=True)

        if a["overlay"]["overlays"]:
            with st.expander("Analyst overlay (disclosed judgment)"):
                for o in a["overlay"]["overlays"]:
                    st.markdown(f"**{o['date']} — {o['value']:+.0%}** · "
                                f"review by {o.get('review_by', 'n/a')}\n\n"
                                f"{o['rationale']}")

        st.subheader("Macro linkages applied")
        if a["macro_adjustments"]:
            for adj in a["macro_adjustments"]:
                st.markdown(
                    f"- **{adj['rule'].replace('_', ' ')}** — {adj['reading']} → "
                    f"`{adj['adjustment']:+.2%}` to {adj['target'].replace('_', ' ')}")
        else:
            st.markdown("None currently apply.")

        sens = a.get("sensitivity")
        if sens:
            st.subheader("Sensitivity")
            st.caption(f"Target price across {sens['x_label']} (rows) and "
                       "cost of equity (columns)")
            sdf = pd.DataFrame(
                sens["grid"],
                index=[f"{x:.1%}" for x in sens["x_values"]],
                columns=[f"{c:.1%}" for c in sens["coe_values"]])
            st.dataframe(sdf.style.background_gradient(cmap="RdYlGn", axis=None)
                         .format("{:,.0f}"), width="stretch")

    with right:
        st.subheader("Price — 5 years")
        st.line_chart(price_history(tk), height=220)

        st.subheader("Fundamentals (SEC as-filed)")
        per_year = a["ratios"]["per_year"]
        fy = pd.DataFrame(per_year).T.sort_index()
        if "revenue" in fy:
            st.caption("Revenue ($B)")
            st.bar_chart(fy["revenue"] / 1e9, height=180)
        if "free_cash_flow" in fy:
            st.caption("Free cash flow ($B)")
            st.bar_chart(fy["free_cash_flow"] / 1e9, height=180)
        margins = fy[[c for c in ("net_margin", "operating_margin", "roe")
                      if c in fy]]
        if not margins.empty:
            st.caption("Margins & returns")
            st.line_chart(margins, height=180)


# ---------- Scorecard tab ----------

with tab_scorecard:
    calls = load_calls()
    if calls.empty:
        st.info("No calls logged yet.")
    else:
        st.caption(
            "Every call Equity-Lens has made, priced against today. Calls are "
            "append-only and committed to git — the record cannot be rewritten.")
        sc = calls.copy()
        sc["current"] = sc["ticker"].map(current_price)
        sc["stock since call"] = sc["current"] / sc["price"] - 1
        sc["target upside at call"] = sc["final_target"] / sc["price"] - 1

        def call_direction_right(row):
            if row["rating"] == "BUY":
                return row["stock since call"] > 0
            if row["rating"] == "SELL":
                return row["stock since call"] < 0
            return abs(row["stock since call"]) < 0.10

        sc["direction right so far"] = sc.apply(call_direction_right, axis=1)
        show = sc[["date", "ticker", "rating", "price", "final_target",
                   "street_target", "current", "stock since call",
                   "direction right so far"]].rename(columns={
            "price": "price at call", "final_target": "our target",
            "street_target": "street target", "current": "price now"})
        show["date"] = show["date"].dt.date
        st.dataframe(
            show.style.format({
                "price at call": "${:.2f}", "our target": "${:.2f}",
                "street target": "${:.2f}", "price now": "${:.2f}",
                "stock since call": "{:+.1%}"}),
            width="stretch", hide_index=True)

        n = len(sc)
        right = int(sc["direction right so far"].sum())
        age_days = (pd.Timestamp.now() - sc["date"].min()).days
        m1, m2, m3 = st.columns(3)
        m1.metric("Calls on record", n)
        m2.metric("Direction right so far", f"{right}/{n}")
        m3.metric("Oldest call age", f"{age_days} days")
        if age_days < 90:
            st.caption("⏳ A track record under ~90 days is noise, not signal. "
                       "It's shown anyway — that's the point of keeping score.")


# ---------- Reports tab ----------

with tab_reports:
    files = sorted(REPORTS_DIR.glob("*.md"), reverse=True)
    if not files:
        st.info("No reports generated yet.")
    else:
        pick = st.selectbox("Report", files, format_func=lambda p: p.stem)
        st.markdown(pick.read_text())


# ---------- Methodology tab ----------

with tab_method:
    st.markdown("""
### How Equity-Lens works

1. **Primary data only.** Financial statements come from SEC EDGAR as-filed
   XBRL; market data from Yahoo Finance; macro series from FRED. No paid
   feeds, no scraped analyst content.
2. **Deterministic models.** Operating companies: DCF (40%) + peer comps
   (30%) + the company's own historical multiple (30%). Banks: justified
   price-to-book on normalized ROE, cross-checked with P/E. Cash-heavy
   holdcos: justified P/B cross-checked with peer P/B (their GAAP earnings
   are mark-to-market noise).
3. **Macro linkages.** Trait-based, capped rules (yield curve → bank ROE,
   dollar → multinational growth, aluminum/sugar → beverage margins, ...).
   See [MACRO_CATALOG.md](https://github.com/Jamesheidbreder/equity-lens/blob/main/MACRO_CATALOG.md).
4. **Judgment is disclosed, never hidden.** Analyst overlays are dated,
   written entries applied on top of the frozen mechanical base — both
   numbers are always shown.
5. **The scorecard cannot be rewritten.** Every generated report appends
   its call to an append-only log, committed to git.

**Street consensus is displayed as a benchmark and is never a model input.**
""")
