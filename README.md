# Equity-Lens

An automated equity research platform that generates institutional-grade research reports from primary sources — SEC filings, market data, and Federal Reserve economic data. Built to CFA Institute research report standards.

## What it does

Enter a ticker. Equity-Lens pulls the company's financial statements from SEC EDGAR, live market data from Yahoo Finance, and the macro backdrop from FRED (Federal Reserve Economic Data), then:

- **Computes** — every valuation number (DCF, peer multiples, financial ratios) is calculated deterministically in Python from filed financials. No black boxes, no hallucinated numbers. The math is auditable line by line.
- **Adapts by sector** — banks are valued on excess returns and price-to-book, not enterprise DCF; conglomerates on sum-of-the-parts logic; operating companies on discounted cash flow plus comparables. The methodology matches the business model.
- **Reports** — output follows the CFA Institute research report structure: investment summary, macro & industry overview, business description, financial analysis, multi-method valuation, risks, and ESG.
- **Keeps score** — every rating and price target is recorded with its date. The scorecard tracks each call against what the market actually did. Wrong calls stay on the record.

## Coverage universe

| Ticker | Company | Sector | Valuation approach |
|--------|---------|--------|--------------------|
| AAPL | Apple Inc. | Technology | DCF + comparables |
| MSFT | Microsoft Corp. | Technology | DCF + comparables |
| KO | The Coca-Cola Company | Consumer Staples | DCF + comparables |
| FITB | Fifth Third Bancorp | Financials (Regional Bank) | Excess returns + P/TBV |
| BRK-B | Berkshire Hathaway | Diversified / Insurance | Book value + look-through |

## Data sources (all free, all primary)

- **SEC EDGAR** — official company filings and XBRL financial statement data
- **Yahoo Finance** — market prices, historical data, peer statistics
- **FRED** — Federal Reserve economic data for the macro overview (rates, inflation, consumer health, sector indicators)

## Why not just ask an AI chatbot?

A chatbot generates plausible numbers; Equity-Lens calculates real ones from filed financials, identically and auditably every run. A chatbot has a knowledge cutoff; Equity-Lens pulls current data at run time. A chatbot forgets; Equity-Lens maintains a dated, versioned track record of every call it has made.

## Project status

Under active development. Build log is the commit history.
