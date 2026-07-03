"""Trait classifier: suggests macro-linkage traits for a company.

Division of labor, by design:
  - The classifier SUGGESTS traits from a fixed vocabulary (TRAIT_MENU).
  - The deterministic rules in macro_links.py do ALL math.
  - A human approves suggestions before they enter universe.py.

The classifier can never invent a linkage or touch a number: suggestions
outside TRAIT_MENU are discarded, and nothing is auto-applied.

Backends, tried in order:
  1. Ollama (free local LLM at localhost:11434) if running — reads the
     company's business summary and picks applicable traits from the menu.
  2. Keyword rules on Yahoo's sector/industry classification — zero
     dependencies, always available.
"""

import json

import requests
import yfinance as yf

TRAIT_MENU = {
    "bank": "Lends and takes deposits; earns the yield-curve spread; "
            "credit losses hit earnings.",
    "beverage_commodity": "Beverage maker with aluminum/sugar input costs.",
    "consumer_hardware": "Sells durable consumer devices; demand follows "
                         "the durable-goods spending cycle.",
    "holdco_cash": "Holding company with a large cash/T-bill pile whose "
                   "yield follows short rates.",
}

# Keyword backend: substrings matched against Yahoo industry/sector strings.
INDUSTRY_KEYWORDS = {
    "bank": ["bank"],
    "beverage_commodity": ["beverage"],
    "consumer_hardware": ["consumer electronics", "computer hardware",
                          "electronic gaming"],
    "holdco_cash": ["insurance—diversified", "conglomerate"],
}

OLLAMA_URL = "http://localhost:11434/api/generate"


def _keyword_suggest(sector: str, industry: str) -> list:
    text = f"{sector} {industry}".lower()
    return [trait for trait, kws in INDUSTRY_KEYWORDS.items()
            if any(kw in text for kw in kws)]


def _ollama_suggest(summary: str, sector: str, industry: str) -> list:
    """Ask a local LLM to pick traits from the menu. Returns [] if Ollama
    isn't running. Output is validated against TRAIT_MENU — the model can
    only choose from the fixed vocabulary, never add to it."""
    menu = "\n".join(f"- {k}: {v}" for k, v in TRAIT_MENU.items())
    prompt = (
        "You classify companies for a research tool. Given the company "
        "description, reply with ONLY a JSON array of applicable trait names "
        f"from this menu (empty array if none apply):\n{menu}\n\n"
        f"Sector: {sector}\nIndustry: {industry}\nDescription: {summary[:1500]}"
    )
    try:
        resp = requests.post(OLLAMA_URL, timeout=60, json={
            "model": "llama3.2", "prompt": prompt, "stream": False,
            "format": "json",
        })
        resp.raise_for_status()
        raw = json.loads(resp.json()["response"])
        candidates = raw if isinstance(raw, list) else raw.get("traits", [])
        return [t for t in candidates if t in TRAIT_MENU]  # menu-validated
    except Exception:
        return []


def suggest_traits(ticker: str) -> dict:
    """Suggest traits for a ticker. Advisory output only — the caller (a
    human) decides what enters universe.py."""
    info = yf.Ticker(ticker).info
    sector = info.get("sector", "")
    industry = info.get("industry", "")
    summary = info.get("longBusinessSummary", "")

    ai = _ollama_suggest(summary, sector, industry)
    keyword = _keyword_suggest(sector, industry)
    suggested = sorted(set(ai) | set(keyword))

    return {
        "ticker": ticker,
        "sector": sector,
        "industry": industry,
        "suggested_traits": suggested,
        "sources": {"ollama": ai, "keywords": keyword},
        "note": "Suggestions only. Traits take effect when a human adds them "
                "to universe.py; all math stays in macro_links.py rules.",
    }
