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


def verdict_sentence(a: dict) -> str:
    """The whole analysis in one plain-English sentence."""
    up = a["upside"]
    name = a["profile"]["name"]
    if a["rating"] == "BUY":
        stance = (f"looks **undervalued**: we estimate it's worth about "
                  f"**{up:+.0%}** more than today's price")
    elif a["rating"] == "SELL":
        stance = (f"looks **expensive**: we estimate its fair value is about "
                  f"**{abs(up):.0%} below** today's price")
    else:
        stance = "looks **roughly fairly priced** at today's level"
    return (f"{RATING_BADGE[a['rating']]} — **{name}** {stance}. "
            f"Our fair-value estimate is **${a['target_price']:,.2f}** per share; "
            f"the market price is **${a['snapshot']['price']:,.2f}**.")


# ---------- header ----------

st.title("📊 Equity-Lens")
st.caption(
    "**What is this?** A research platform that estimates what stocks are "
    "actually worth — computed from official SEC filings, market data, and "
    "Federal Reserve statistics, not opinions. Every call it makes is dated "
    "and kept on a public scorecard, right or wrong. "
    "[GitHub](https://github.com/Jamesheidbreder/equity-lens) · "
    "Educational project, not investment advice."
)

tab_overview, tab_company, tab_scorecard, tab_reports, tab_method = st.tabs(
    ["🏠 Coverage", "🔍 Company Analysis", "🎯 Scorecard", "📄 Reports",
     "⚙️ How It Works"])


# ---------- Coverage tab ----------

with tab_overview:
    st.subheader("The coverage board")
    st.markdown(
        "The five companies we cover, ranked from **most attractive to own** "
        "to least. *Our target* is what we compute the stock is worth; "
        "*street target* is the average Wall Street analyst's number, shown "
        "for comparison only.")
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
            "Note: most Wall Street analysts disagree with this call — see "
            "*How It Works* for why our numbers run more conservative than "
            "the street's.")

    c1, c2, c3, c4, c5 = st.columns(5)
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
    c5.metric("Required return", f"{a['cost_of_equity']:.1%}",
              help="The yearly return an investor should demand for holding a "
                   "stock this risky (built from the 10-year Treasury yield "
                   "plus a risk premium). Used to discount future cash.")

    left, right = st.columns(2)

    with left:
        st.subheader("How we got the number")
        st.markdown("We value every company through several independent "
                    "lenses, then blend them:")
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
            with st.expander("💭 Analyst judgment applied (click to read)"):
                st.markdown(
                    "Some things — like unproven new products — can't be "
                    "computed from filings. When we choose to credit them, "
                    "the judgment is written down, dated, and shown here:")
                for o in a["overlay"]["overlays"]:
                    st.markdown(f"**{o['date']} — {o['value']:+.0%} to fair "
                                f"value** · review due {o.get('review_by', 'n/a')}"
                                f"\n\n{o['rationale']}")

        with st.expander("🌍 Economic conditions factored in"):
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
            with st.expander("🎛️ How wrong could we be? (sensitivity)"):
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
        st.subheader("The stock — last 5 years")
        st.line_chart(price_history(tk), height=220)

        st.subheader("The business — straight from SEC filings")
        per_year = a["ratios"]["per_year"]
        fy = pd.DataFrame(per_year).T.sort_index()
        if "revenue" in fy:
            st.caption("Revenue — total sales, in billions of dollars")
            st.bar_chart(fy["revenue"] / 1e9, height=180)
        if "free_cash_flow" in fy:
            st.caption("Free cash flow — cash left after running and "
                       "reinvesting in the business ($B)")
            st.bar_chart(fy["free_cash_flow"] / 1e9, height=180)
        margins = fy[[c for c in ("net_margin", "operating_margin")
                      if c in fy]]
        if not margins.empty:
            st.caption("Profit margins — how many cents of each sales dollar "
                       "become profit")
            st.line_chart(margins, height=180)


# ---------- Scorecard tab ----------

with tab_scorecard:
    st.subheader("Do our calls actually work?")
    st.markdown(
        "Every call we've ever made, with the date it was made and what the "
        "stock has done since. Entries are append-only and stored in git — "
        "**the record can't be quietly rewritten**, and wrong calls stay up.")
    calls = load_calls()
    if calls.empty:
        st.info("No calls logged yet.")
    else:
        sc = calls.copy()
        sc["current"] = sc["ticker"].map(current_price)
        sc["stock since call"] = sc["current"] / sc["price"] - 1

        def direction(row):
            if row["rating"] == "BUY":
                return "✅ so far" if row["stock since call"] > 0 else "❌ so far"
            if row["rating"] == "SELL":
                return "✅ so far" if row["stock since call"] < 0 else "❌ so far"
            return "✅ so far" if abs(row["stock since call"]) < 0.10 else "❌ so far"

        sc["working?"] = sc.apply(direction, axis=1)
        sc["rating"] = sc["rating"].map(RATING_BADGE)
        show = sc[["date", "ticker", "rating", "price", "final_target",
                   "current", "stock since call", "working?"]].rename(columns={
            "price": "price at call", "final_target": "our target",
            "current": "price now"})
        show["date"] = show["date"].dt.date
        st.dataframe(
            show.style.format({
                "price at call": "${:.2f}", "our target": "${:.2f}",
                "price now": "${:.2f}", "stock since call": "{:+.1%}"}),
            width="stretch", hide_index=True)

        n = len(sc)
        right_n = int((sc["working?"] == "✅ so far").sum())
        age_days = (pd.Timestamp.now() - sc["date"].min()).days
        m1, m2, m3 = st.columns(3)
        m1.metric("Calls on record", n,
                  help="Each dated rating + target we've published.")
        m2.metric("Moving our way", f"{right_n}/{n}",
                  help="BUYs where the stock is up since the call, SELLs "
                       "where it's down, HOLDs that stayed within ±10%.")
        m3.metric("Oldest call", f"{age_days} days",
                  help="Track records need time. Under ~90 days this is "
                       "weather, not climate.")
        if age_days < 90:
            st.caption("⏳ **Honesty note:** a record this young is mostly "
                       "noise. We show it anyway — keeping score in public "
                       "is the whole point.")


# ---------- Reports tab ----------

with tab_reports:
    st.subheader("Full research reports")
    st.markdown(
        "The complete written research behind each call — the same format "
        "professional analysts publish: thesis, economics, financials, "
        "valuation, risks.")
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
