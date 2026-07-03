"""Market data via Yahoo Finance (yfinance).

Provides current price, trading stats, and history for the covered company
and its peer group. All figures are as-reported by the exchange feed; no
estimates are fabricated here.
"""

import pandas as pd
import yfinance as yf


def get_snapshot(ticker: str) -> dict:
    """Current price, market cap, and trading stats for one ticker."""
    t = yf.Ticker(ticker)
    info = t.info
    return {
        "ticker": ticker,
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap": info.get("marketCap"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "float_shares": info.get("floatShares"),
        "beta": info.get("beta"),
        "trailing_pe": info.get("trailingPE"),
        "trailing_eps": info.get("trailingEps"),
        "forward_pe": info.get("forwardPE"),
        "forward_eps": info.get("forwardEps"),
        "earnings_growth": info.get("earningsGrowth"),
        "revenue_growth": info.get("revenueGrowth"),
        # Street consensus, kept as a sanity benchmark only — never an input
        # to our own valuation.
        "street_target_mean": info.get("targetMeanPrice"),
        "street_analyst_count": info.get("numberOfAnalystOpinions"),
        "price_to_book": info.get("priceToBook"),
        "dividend_yield": info.get("dividendYield"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "avg_volume": info.get("averageVolume"),
        "held_by_institutions": info.get("heldPercentInstitutions"),
        "long_name": info.get("longName"),
        "currency": info.get("currency"),
    }


def get_history(ticker: str, period: str = "5y") -> pd.DataFrame:
    """Daily OHLCV price history."""
    return yf.Ticker(ticker).history(period=period)


def get_peer_multiples(tickers: list) -> pd.DataFrame:
    """Valuation multiples for a peer group, one row per ticker.

    Used by the comparable-company analysis. Missing fields stay NaN rather
    than being guessed.
    """
    rows = []
    for tk in tickers:
        info = yf.Ticker(tk).info
        rows.append({
            "ticker": tk,
            "name": info.get("shortName"),
            "market_cap": info.get("marketCap"),
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "ev_to_ebitda": info.get("enterpriseToEbitda"),
            "ev_to_revenue": info.get("enterpriseToRevenue"),
            "price_to_book": info.get("priceToBook"),
            "profit_margin": info.get("profitMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            "dividend_yield": info.get("dividendYield"),
        })
    return pd.DataFrame(rows).set_index("ticker")
