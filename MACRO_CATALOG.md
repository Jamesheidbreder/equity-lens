# Macro Linkage Catalog

Every macro/industry linkage Equity-Lens knows about. Each entry names the
free FRED data series, the causal mechanism, and what it adjusts. Rules key
on **traits**, never tickers — tag a company with a trait (human-approved,
suggested by the classifier) and it inherits the linkage.

**Status legend:**
- **WIRED** — implemented in `macro_links.py`, capped, auto-applied to tagged companies
- **CONTEXT** — shown in the report's macro section as evidence for written judgment overlays; does not move numbers
- **PLANNED** — defensible mechanism, not yet implemented

All wired adjustments are capped (growth ±1.5pp, cost of equity ±1pp,
ROE ±1.5pp) and dampened — macro leans on an assumption, never decides it.

## Economy-wide (apply to every company)

| Linkage | FRED series | Mechanism | Adjusts | Status |
|---------|------------|-----------|---------|--------|
| Risk-free rate | DGS10 | 10Y Treasury anchors CAPM cost of equity; higher rates lower all valuations | Cost of equity (directly, uncapped — it IS the input) | WIRED |
| Credit-spread risk premium | BAA10Y | Corporate bond spreads are a market-priced fear gauge; wide spreads = higher equity risk premium | Cost of equity | WIRED |
| Inflation regime | CPIAUCSL | High/volatile inflation compresses multiples, distorts real growth | Context for overlays | CONTEXT |
| Inflation expectations | MICH | Household expectations lead wage demands and Fed policy | Context | CONTEXT |
| Real 10Y rate | REAINTRATREARAT10Y | The true discount-rate burden after inflation | Context | CONTEXT |
| Payrolls | PAYEMS | Employment growth drives aggregate demand | Context | CONTEXT |
| Jobless claims | ICSA | Weekly, fastest-turning recession signal | Context | CONTEXT |
| Unemployment | UNRATE | Consumer health; leads credit losses | Context (wired indirectly via bank delinquencies) | CONTEXT |
| Consumer sentiment | UMCSENT | Willingness to spend, esp. discretionary | Context | CONTEXT |
| Yield-curve slope | T10Y2Y | Inversion is the classic recession lead indicator | Context economy-wide; WIRED for banks | MIXED |

## Multinationals (trait: any company with `intl_revenue_share` set)

| Linkage | FRED series | Mechanism | Adjusts | Status |
|---------|------------|-----------|---------|--------|
| Dollar translation | DTWEXBGS | Strong dollar shrinks foreign revenue in USD terms; scaled by the company's foreign revenue share | Growth | WIRED |

## Banks (trait: `bank`)

| Linkage | FRED series | Mechanism | Adjusts | Status |
|---------|------------|-----------|---------|--------|
| Yield-curve slope → NIM | T10Y2Y | Banks lend long, fund short; steep curve = richer net interest margin | ROE | WIRED |
| Loan delinquencies | DRALACBN | Rising delinquencies foreshadow loan-loss provisions | ROE (penalty only) | WIRED |
| Card delinquencies | DRCCLACBS | Consumer credit stress, earlier-turning than total loans | ROE (penalty only) | WIRED |
| Lending standards | DRTSCILM (SLOOS) | Fed survey: banks tightening = slower loan growth ahead | Context | CONTEXT |
| Deposit cost pressure | FEDFUNDS | Funding cost floor; fast hikes squeeze cheap-deposit advantage | Context | CONTEXT |

## Beverages / staples with commodity inputs (trait: `beverage_commodity`)

| Linkage | FRED series | Mechanism | Adjusts | Status |
|---------|------------|-----------|---------|--------|
| Can + sweetener costs | PALUMUSDM, PSUGAISAUSDM | Aluminum and sugar are direct COGS; inflation pressures gross margin | Growth | WIRED |
| Producer-vs-consumer price gap | PPIACO vs CPIAUCSL | Input costs outrunning shelf prices = margin squeeze for limited-pass-through companies | Growth | WIRED (trait `cost_passthrough_limited`; do not double-tag with `beverage_commodity`) |

## Consumer hardware (trait: `consumer_hardware`)

| Linkage | FRED series | Mechanism | Adjusts | Status |
|---------|------------|-----------|---------|--------|
| Durables spending cycle | PCEDG | Devices are durable-goods purchases; demand above/below trend leans on near-term growth | Growth | WIRED |

## Enterprise software / cloud (trait: `enterprise_software`)

| Linkage | FRED series | Mechanism | Adjusts | Status |
|---------|------------|-----------|---------|--------|
| Business software investment | B985RC1Q027SBEA | National accounts measure of corporate software spend — the demand pool for enterprise IT | Growth | WIRED |

## Cash-heavy holdcos (trait: `holdco_cash`)

| Linkage | FRED series | Mechanism | Adjusts | Status |
|---------|------------|-----------|---------|--------|
| T-bill yield on the cash pile | DTB3 | Cash/bills earn the short rate; scaled by cash-to-book | ROE | WIRED |
| Equity market level | WILL5000INDFC | Marks the investment portfolio | Context | CONTEXT |
| Rail freight carloads | RAILFRTCARLOADSD11 | BNSF-style rail volume proxy | Context | CONTEXT |
| Industrial production | INDPRO | Demand proxy for industrial operating units | Context | CONTEXT |

## Energy producers (trait: `energy_producer`)

| Linkage | FRED series | Mechanism | Adjusts | Status |
|---------|------------|-----------|---------|--------|
| Crude oil price | DCOILWTICO | Revenue is roughly price × volume; the commodity IS the top line | Growth | WIRED |
| Natural gas price | DHHNGSP | Same mechanism for gas-weighted producers | Context (blend into rule later) | CONTEXT |

## Homebuilders / housing chain (trait: `homebuilder_housing`)

| Linkage | FRED series | Mechanism | Adjusts | Status |
|---------|------------|-----------|---------|--------|
| Housing starts | HOUST | Direct volume driver | Growth | WIRED |
| Mortgage rates | MORTGAGE30US | Affordability throttle on demand; rates above norm suppress starts ahead | Growth (combined with starts) | WIRED |
| Building permits | PERMIT | Leads starts by ~1-2 months | Context | CONTEXT |
| Residential construction spend | TLRESCONS | Dollar-value chain demand (suppliers, retailers) | Context | CONTEXT |

## Autos (trait: `auto_cycle`)

| Linkage | FRED series | Mechanism | Adjusts | Status |
|---------|------------|-----------|---------|--------|
| Vehicle sales pace | TOTALSA | Industry volume (SAAR) vs norm = where we are in the cycle | Growth | WIRED |

## Retail (trait: `retail_consumer`)

| Linkage | FRED series | Mechanism | Adjusts | Status |
|---------|------------|-----------|---------|--------|
| Retail sales | RSXFS | Direct demand measure vs trend | Growth | WIRED |
| Consumer sentiment | UMCSENT | Leads discretionary purchases | Context | CONTEXT |

## Industrials / freight (traits: planned)

| Linkage | FRED series | Mechanism | Adjusts | Status |
|---------|------------|-----------|---------|--------|
| Industrial production | INDPRO | Broad factory-sector demand | Growth (trait `industrial_cycle`) | PLANNED |
| Manufacturing workweek | AWHMAN | Hours flex before headcount — early cycle signal | Context | CONTEXT |
| Truck freight rates | PCU4841214841212 | Freight pricing power | Context | CONTEXT |
| All-commodities index | PALLFNFINDEXM | Input costs for manufacturers | Growth (trait `commodity_input_heavy`) | PLANNED |

## Not modelable with free macro data (report as qualitative risks instead)

- Semiconductor cycle (no good free FRED proxy; SIA data is paywalled)
- Airline traffic (TSA data exists but is operational, not FRED)
- Drug pipelines / FDA decisions (event-driven, not time-series)
- Litigation, regulation, management change — judgment overlay territory
