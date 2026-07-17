# Equity-Lens: What This Project Is

**One sentence:** Equity-Lens is a research platform I built that reads a
company's official financial filings, calculates what its stock is
actually worth, writes an institutional-style research report about it,
and keeps a public, dated record of every call it makes.

**Cost to run: $0.** Every data source is free and public. Every
calculation runs in code I control.

---

## What it produces

- **Research reports.** For each covered company: a rating (BUY, HOLD,
  or SELL), a price target, and a full written report — the same
  structure Wall Street banks publish, with charts, financial tables, a
  valuation walk-through, risks, and catalysts.
- **A coverage universe.** Seven companies so far, deliberately spread
  across different kinds of businesses: Apple, Microsoft, Coca-Cola,
  Fifth Third Bank, Berkshire Hathaway, and two shipping companies
  (Global Ship Lease and Star Bulk).
- **A public scorecard.** Every rating and target is logged with its
  date and stored in version control, where it cannot be quietly
  edited later. Right calls and wrong calls both stay on the record.

## How the valuation engine works

The engine answers one question: **what is one share of this company
actually worth?** It does this with real data and open math — no
guessing, no black box.

**Step 1 — Gather the facts.** The engine pulls three kinds of data
automatically: the company's audited financial statements from the SEC
(the U.S. government filing system), live market prices, and economic
data from the Federal Reserve (interest rates, inflation, and so on).

**Step 2 — Value the company through three independent lenses.** Each
lens answers the same question a different way:

1. **Discounted cash flow.** Add up the cash the business is expected
   to generate in the future, and translate it into today's dollars.
   A dollar arriving in five years is worth less than a dollar today,
   so future cash is discounted using interest rates plus a premium
   for risk. This lens asks: *what are the future profits worth right
   now?*
2. **Peer comparison.** Look at what similar companies cost relative
   to their earnings, and apply that price level to this company.
   This lens asks: *what would this company cost if it were priced
   like its competitors?*
3. **Own history.** Look at the price level this company itself has
   commanded over the past five years, and apply it to today's
   earnings. This lens asks: *what would the stock cost if it were
   priced the way it usually is?*

**Step 3 — Blend and adjust.** The three answers are blended into one
target. The economic backdrop leans on the inputs in small, capped
ways — for example, higher interest rates lower every valuation, and
rising aluminum prices squeeze a soda maker's margins. If the target
sits well above the market price, the stock is rated BUY; well below,
SELL; near it, HOLD.

**Step 4 — Read the disagreement.** If the three lenses roughly agree,
confidence in the answer is high. If they disagree wildly, that is a
finding in itself: the company's value is genuinely uncertain, and the
report says so plainly.

**One size does not fit all.** A bank is not valued like a phone
maker, and a shipping company is not valued like a soda company. The
engine assigns each company a sector playbook that picks the right
methods — banks are valued on their balance sheets, shipping companies
get their fleet spending treated as investment rather than expense.
Every methodology choice is written down in a decision journal with
the reasoning and the evidence that would reverse it.

**Where human judgment fits.** The machine only prices what has
already happened. Some things haven't happened yet — a new product, an
AI bet — and crediting them is a judgment call. Those calls are
allowed, but only through a disclosed, dated adjustment with written
reasoning that appears in the report. The machine's number and the
adjusted number are always shown side by side.

## Why this is different from asking an AI chatbot

A chatbot generates plausible-sounding numbers; this engine calculates
real ones from audited filings, the same way every time, and shows its
work. A chatbot has no memory; this platform keeps score in public.
The gap between our targets and Wall Street's is measured and
explained in every report — their consensus is displayed as a
benchmark, but it never enters our math.

## What's under the hood

| Piece | What it does |
|---|---|
| Data layer | Pulls SEC filings, market prices, and Fed data; handles U.S. and foreign filing formats |
| Valuation engine | The three lenses, sector playbooks, macro adjustments, conviction grading |
| Report generator | Turns the analysis into styled research reports with charts and tables |
| Narratives | Written analysis (thesis, industry, moat, management) in bank-note style, drafted with research and edited by hand |
| Scorecard | The append-only log of every dated call |
| Dashboard | A local web app for browsing the analysis interactively |

Everything is versioned publicly at
[github.com/Jamesheidbreder/equity-lens](https://github.com/Jamesheidbreder/equity-lens) —
the commit history is the build log of the entire project.

*Educational research project. Not investment advice.*
