# Sector Playbooks

The engine's methodology is organized by sector, the way research
departments are: each sector declares how its companies are valued —
which models, which cash-flow basis, which multiples, which macro
linkages. **Methodology is declared, never auto-detected.** Automatic
heuristics (like the capex/depreciation ratio) run as diagnostics that
flag anomalies for analyst review; they do not silently change the math.

Status: playbooks 1-4 are implemented and battle-tested on live coverage.
The rest are specified here and get implemented as coverage expands
(full build: Session 4, alongside any-ticker search — a new ticker maps
to a sector, the sector picks the playbook).

| # | Sector | Valuation approach | Cash-flow basis | Key multiples | Notes / gotchas |
|---|--------|-------------------|-----------------|---------------|-----------------|
| 1 | **Technology** (software, hardware, internet) | DCF + peer comps + own-history multiple (40/30/30) | Standard (OCF − all capex); watch the AI-datacenter capex diagnostic | P/E fwd & trailing, EV/EBITDA | High franchise premiums; own-history anchor matters. IMPLEMENTED (AAPL, MSFT) |
| 2 | **Consumer Staples** (beverages, food, household) | DCF + comps + own-history (40/30/30) | Standard | P/E, EV/EBITDA | Commodity input linkages (aluminum, sugar); FX exposure high. IMPLEMENTED (KO) |
| 3 | **Banks** (money-center, regional) | Justified P/B on normalized ROE + peer P/E + own-history P/E (equal) | n/a — enterprise FCF is meaningless (deposits are raw material) | P/TBV, P/E | Yield-curve and credit-cycle linkages; never DCF. IMPLEMENTED (FITB) |
| 4 | **Insurance / Financial holdcos** | Justified P/B + peer P/B | n/a | P/B | GAAP earnings polluted by mark-to-market — never P/E. IMPLEMENTED (BRK-B) |
| 5 | **Industrials & Transport** (shipping, rails, airlines, machinery) | DCF + comps, comps-weighted for lessors | **Maintenance** (OCF − depreciation) for fleet/asset buyers; standard for asset-light | EV/EBITDA, P/E; P/NAV where fleet values exist | Cyclical: normalize over the cycle, never extrapolate peak charters/rates. Validated ad-hoc on GSL |
| 6 | **Energy** (E&P, integrated, midstream) | DCF on maintenance basis + comps | **Maintenance** | EV/EBITDA, P/CF, dividends | Revenue = commodity price × volume (WTI linkage wired); reserves depletion matters |
| 7 | **Healthcare** (pharma, devices, services) | DCF + comps (40/30/30) | Standard | P/E, EV/EBITDA | R&D is the real growth capex but is already expensed; pipeline/patent-cliff risk is a judgment overlay, not a model input |
| 8 | **Consumer Discretionary / Retail** | DCF + comps + own-history | Standard; maintenance if heavy store-buildout (declared) | P/E, EV/EBITDA | Retail-sales and sentiment linkages wired; leases distort debt comparisons |
| 9 | **Utilities** | Dividend-based (DDM) + justified P/B on regulated ROE | Maintenance — capex is rate-base growth regulators repay | P/E, dividend yield | Bond-proxy: rate-sensitivity dominates; regulated ROE is set by commissions |
| 10 | **Real Estate / REITs** | FFO-based comps + dividend yield | FFO replaces earnings entirely | P/FFO, dividend yield | GAAP depreciation makes P/E meaningless for property; NOT yet supported by the data layer (FFO isn't a standard XBRL tag) |

## Design rules

1. **Declared, not detected.** A company's playbook comes from its profile
   (sector + optional overrides like `capex_basis`). Diagnostics may say
   "this looks like it needs a different playbook" — a human moves it.
2. **Cross-country differences** (IFRS vs US GAAP tags, 20-F/40-F filings)
   are handled in the data layer, not the playbooks — by the time numbers
   reach a playbook they are comparable.
3. **One company, one playbook.** Conglomerates that genuinely straddle
   sectors get the holdco treatment (sum-of-parts is a Session-later
   ambition).
4. **New sector = new playbook entry here first**, then implementation,
   then a test name run ad-hoc before it enters coverage.
