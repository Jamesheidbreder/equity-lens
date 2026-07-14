"""SEC EDGAR: as-filed financial statement data via the XBRL companyfacts API.

This is the primary source for the financial analysis and valuation
sections — numbers come from what the company actually filed with the SEC,
not from a third-party aggregator.

The SEC requires a descriptive User-Agent on all requests.
"""

import pandas as pd
import requests

COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
# SEC fair-access policy requires identifying requests with a contact email.
HEADERS = {"User-Agent": "Equity-Lens research h8y8vqzpc5@privaterelay.appleid.com"}

# us-gaap concepts to extract, with fallback tags because filers differ in
# which tag they use for the same line item.
CONCEPTS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                "SalesRevenueNet", "RevenuesNetOfInterestExpense",
                "InterestAndDividendIncomeOperating"],
    "net_income": ["NetIncomeLoss"],
    # Bank-specific lines; empty for non-banks.
    "net_interest_income": ["InterestIncomeExpenseNet",
                            "InterestIncomeExpenseAfterProvisionForLoanLoss"],
    "noninterest_income": ["NoninterestIncome"],
    "provision_for_credit_losses": ["ProvisionForLoanLeaseAndOtherLosses",
                                    "ProvisionForCreditLossExpenseReversal",
                                    "ProvisionForLoanAndLeaseLosses"],
    "operating_income": ["OperatingIncomeLoss"],
    "total_assets": ["Assets"],
    "total_equity": ["StockholdersEquity",
                     "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment",
              "PaymentsToAcquireProductiveAssets",
              "PaymentsToAcquireMachineryAndEquipment"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "shares_diluted": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted",
                    "IncomeLossFromContinuingOperationsPerDilutedShare",
                    "DilutedEarningsLossPerShare"],
    "dividends_paid": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
    # Maintenance-capex proxy for capital-intensive companies.
    "depreciation": ["DepreciationDepletionAndAmortization",
                     "DepreciationAmortizationAndAccretionNet", "Depreciation",
                     "DepreciationAndAmortisationExpense"],
}

# IFRS equivalents for foreign private issuers that don't file under
# us-gaap. Checked when the us-gaap taxonomy yields nothing for a concept.
IFRS_CONCEPTS = {
    "revenue": ["Revenue"],
    "net_income": ["ProfitLossAttributableToOwnersOfParent", "ProfitLoss"],
    "operating_income": ["ProfitLossFromOperatingActivities"],
    "total_assets": ["Assets"],
    "total_equity": ["EquityAttributableToOwnersOfParent", "Equity"],
    "operating_cash_flow": ["CashFlowsFromUsedInOperatingActivities"],
    "capex": ["PurchaseOfPropertyPlantAndEquipment"],
    "cash": ["CashAndCashEquivalents"],
    "long_term_debt": ["NoncurrentPortionOfNoncurrentBorrowings",
                       "Borrowings"],
    "eps_diluted": ["DilutedEarningsLossPerShare",
                    "BasicAndDilutedEarningsLossPerShare"],
    "dividends_paid": ["DividendsPaidClassifiedAsFinancingActivities",
                       "DividendsPaid"],
    "depreciation": ["DepreciationAndAmortisationExpense"],
}


def fetch_companyfacts(cik: str) -> dict:
    """Raw XBRL companyfacts JSON for a company (cik is 10-digit, zero-padded)."""
    resp = requests.get(COMPANYFACTS_URL.format(cik=cik), headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _annual_values_in(gaap: dict, tags: list) -> dict:
    """Extract annual (10-K) values for the first tag that has data.

    Values are keyed by the year of the period END date, not the SEC's "fy"
    label — 10-K filings restate prior-year comparatives under the current
    filing's fy label, so trusting "fy" mislabels historical years.

    Duration concepts (revenue, income) are kept only for ~full-year periods;
    instant concepts (assets, equity) are point-in-time balances.

    When several tags carry data, the one with the most RECENT data wins
    (more years as tiebreak) — filers sometimes leave a stale series under
    one tag and report currently under another.
    """
    best = {}
    for tag in tags:
        if tag not in gaap:
            continue
        units = gaap[tag].get("units", {})
        series = {}
        for unit_vals in units.values():
            for item in unit_vals:
                # 10-K for domestic filers; 20-F/40-F are the annual-report
                # equivalents for foreign private issuers.
                if item.get("form") not in ("10-K", "20-F", "40-F") \
                        or "end" not in item:
                    continue
                end = item["end"]
                if "start" in item:  # duration concept: keep full-year periods only
                    days = (pd.Timestamp(end) - pd.Timestamp(item["start"])).days
                    if not 330 <= days <= 400:
                        continue
                year = int(end[:4])
                prev = series.get(year)
                if prev is None or item.get("filed", "") > prev["filed"]:
                    series[year] = {"val": item["val"], "filed": item.get("filed", "")}
        if series and (not best or
                       (max(series), len(series)) > (max(best), len(best))):
            best = series
    return {year: rec["val"] for year, rec in sorted(best.items())}


QUARTERLY_CONCEPTS = {
    "revenue": CONCEPTS["revenue"],
    "net_income": CONCEPTS["net_income"],
    "eps_diluted": CONCEPTS["eps_diluted"],
}


def get_quarterly(cik: str, quarters: int = 8) -> dict:
    """Recent quarterly history from 10-Q filings (plus the 10-K's Q4-
    implied values are NOT derived here — quarters shown are as filed).

    Returns {concept: {(year, end_date): value}} for the most recent
    `quarters` quarters. Foreign filers that don't file 10-Qs return empty.
    """
    facts = fetch_companyfacts(cik)
    gaap = facts.get("facts", {}).get("us-gaap", {})
    out = {}
    for name, tags in QUARTERLY_CONCEPTS.items():
        best = {}
        for tag in tags:
            if tag not in gaap:
                continue
            series = {}
            for unit_vals in gaap[tag].get("units", {}).values():
                for item in unit_vals:
                    if item.get("form") != "10-Q" or "end" not in item \
                            or "start" not in item:
                        continue
                    days = (pd.Timestamp(item["end"])
                            - pd.Timestamp(item["start"])).days
                    if not 80 <= days <= 100:   # single quarters only
                        continue
                    key = item["end"]
                    prev = series.get(key)
                    if prev is None or item.get("filed", "") > prev["filed"]:
                        series[key] = {"val": item["val"],
                                       "filed": item.get("filed", "")}
            if series and (not best or
                           (max(series), len(series)) > (max(best), len(best))):
                best = series
        out[name] = {k: rec["val"] for k, rec in
                     sorted(best.items())[-quarters:]}
    return out


def get_annual_financials(cik: str) -> dict:
    """Annual history for every concept in CONCEPTS.

    Returns {concept_name: {fiscal_year: value}}. Tries us-gaap first, then
    the IFRS taxonomy (foreign private issuers). Concepts a company does not
    report (e.g. capex for a bank) come back empty rather than invented.
    """
    facts = fetch_companyfacts(cik)
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    ifrs = facts.get("facts", {}).get("ifrs-full", {})
    out = {}
    for name, tags in CONCEPTS.items():
        vals = _annual_values_in(us_gaap, tags)
        if not vals and ifrs:
            vals = _annual_values_in(ifrs, IFRS_CONCEPTS.get(name, []))
        out[name] = vals
    return out
