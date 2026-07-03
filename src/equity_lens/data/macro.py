"""Macro data from FRED (Federal Reserve Economic Data).

Uses the keyless fredgraph.csv endpoint, so no API key or account is
required. Each series comes back as a dated time series; the report's
macro & industry overview is built from these.
"""

import io

import pandas as pd
import requests

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def get_series(series_id: str, years: int = 10) -> pd.Series:
    """Fetch one FRED series as a pandas Series indexed by date."""
    resp = requests.get(FRED_CSV_URL, params={"id": series_id}, timeout=30)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col)
    s = pd.to_numeric(df[series_id.upper()], errors="coerce").dropna()
    cutoff = pd.Timestamp.now() - pd.DateOffset(years=years)
    return s[s.index >= cutoff]


def get_macro_dashboard(series_map: dict) -> pd.DataFrame:
    """Latest value, 1-year-ago value, and change for each macro series.

    series_map: {series_id: human-readable label}
    """
    rows = []
    for sid, label in series_map.items():
        s = get_series(sid)
        latest = s.iloc[-1]
        latest_date = s.index[-1]
        year_ago_slice = s[s.index <= latest_date - pd.DateOffset(years=1)]
        year_ago = year_ago_slice.iloc[-1] if len(year_ago_slice) else None
        rows.append({
            "series": sid,
            "indicator": label,
            "latest": latest,
            "as_of": latest_date.date().isoformat(),
            "year_ago": year_ago,
            "change_1y": (latest - year_ago) if year_ago is not None else None,
        })
    return pd.DataFrame(rows).set_index("series")
