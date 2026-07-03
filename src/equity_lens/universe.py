"""Coverage universe: the companies Equity-Lens covers and how each is valued.

Valuation methodology is assigned per business model, following standard
sell-side practice:
  - "dcf_comps": enterprise DCF cross-checked with peer multiples. For
    operating companies where free cash flow is meaningful.
  - "bank": excess-return model on tangible book value, cross-checked with
    P/TBV vs. return profile. Banks fund with deposits, so enterprise-value
    math (EV, EBITDA, FCF) does not apply.
  - "conglomerate": book-value anchored with look-through to operating
    earnings and the investment portfolio. For Berkshire-style holdcos.
"""

UNIVERSE = {
    "AAPL": {
        "name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "method": "dcf_comps",
        "peers": ["MSFT", "GOOGL", "DELL", "HPQ", "SONY"],
        "cik": "0000320193",
        # Macro-linkage traits (see analysis/macro_links.py). Rules key on
        # these, never on the ticker, so new companies just need tagging.
        "traits": ["consumer_hardware"],
        "intl_revenue_share": 0.58,   # per 10-K geographic segment data
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "sector": "Technology",
        "industry": "Software & Cloud",
        "method": "dcf_comps",
        "peers": ["AAPL", "GOOGL", "ORCL", "CRM", "AMZN"],
        "cik": "0000789019",
        "traits": [],
        "intl_revenue_share": 0.49,
    },
    "KO": {
        "name": "The Coca-Cola Company",
        "sector": "Consumer Staples",
        "industry": "Beverages",
        "method": "dcf_comps",
        "peers": ["PEP", "KDP", "MNST", "MDLZ", "PG"],
        "cik": "0000021344",
        "traits": ["beverage_commodity"],
        "intl_revenue_share": 0.64,
    },
    "FITB": {
        "name": "Fifth Third Bancorp",
        "sector": "Financials",
        "industry": "Regional Banks",
        "method": "bank",
        "peers": ["HBAN", "RF", "KEY", "CFG", "TFC"],
        "cik": "0000035527",
        "traits": ["bank"],
        "intl_revenue_share": None,   # domestic
    },
    "BRK-B": {
        "name": "Berkshire Hathaway Inc.",
        "sector": "Financials",
        "industry": "Diversified Holdings / Insurance",
        "method": "conglomerate",
        "peers": ["PGR", "CB", "ALL", "MKL", "L"],
        "cik": "0001067983",
        "traits": ["holdco_cash"],
        "intl_revenue_share": None,
    },
}

# FRED series used for the macro & industry overview section.
# Fetched keylessly via the fredgraph.csv endpoint.
MACRO_SERIES = {
    "FEDFUNDS": "Effective Federal Funds Rate (%)",
    "DGS10": "10-Year Treasury Yield (%)",
    "T10Y2Y": "10Y-2Y Treasury Spread (%)",
    "CPIAUCSL": "Consumer Price Index (level)",
    "UNRATE": "Unemployment Rate (%)",
    "UMCSENT": "U. Michigan Consumer Sentiment",
    "PCE": "Personal Consumption Expenditures ($B)",
}
