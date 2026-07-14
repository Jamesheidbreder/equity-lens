# Analyst Decision Journal

Dated record of judgment calls: the position taken, the strongest case
against it, and the tripwire — the pre-committed evidence that would
reverse the decision. Entries are append-only; reversals get a new entry
rather than an edit. Companion to the judgment overlays in
`data/overlays.json` (which adjust targets) — this journal records
*methodology* judgments.

---

## 2026-07-14 — MSFT stays on the standard capex basis

**Decision (James Heidbreder):** Microsoft's DCF continues to charge the
full ~$70B+/yr capital expenditure against cash flow (standard basis),
rather than switching to the maintenance basis (OCF minus depreciation)
that the capex/depreciation diagnostic (2.2x) flagged for review.

**Effect at decision time:** blended target $418 (HOLD, +8.1%) instead of
$433 (BUY, +12.1%). This single judgment is rating-determinative, which is
why it is documented here.

**Reasoning:**
1. *Demand proof, don't extend trust.* The maintenance basis implicitly
   assumes the AI datacenter buildout is worth what it cost. That is the
   AI investment thesis in its mildest form — but it is still a belief
   about the future, and this shop's discipline is to pay for delivered
   cash flows only. If the buildout earns its keep, future filings will
   show it and the model will re-rate on evidence.
2. *The arms-race risk.* Microsoft, Google, and Amazon are all spending
   simultaneously. If relative competitive positions end up unchanged,
   this spending was the new cost of staying in the game — a permanent
   expense, properly charged against cash flow — not growth investment.
3. *Depreciation understates true upkeep, twice.* Today's depreciation
   echoes yesterday's smaller asset base and will balloon as the new
   datacenters age; and a large share of the capex is GPUs with
   ~3-5-year economic lives booked against longer accounting lives.
   Both effects mean the maintenance basis (OCF − depreciation) is
   generous on top of generous: it excludes growth capex AND uses a
   floor-estimate of maintenance cost.

**Strongest case against this decision:** Azure capacity is reportedly
demand-constrained — the buildout has waiting customers, which looks like
pre-leased real estate, not speculative construction. Charging it all as
an expense punishes visible, contracted growth.

**Tripwire (what flips this decision):** move MSFT to the maintenance
basis if cloud/AI revenue growth holds ~20%+ while capex growth flattens
for 2+ consecutive quarters — evidence the buildout is earning returns
rather than becoming the permanent price of relevance. Checked at each
quarterly earnings update.

---

## 2026-07-14 — GSL initiated on the maintenance-capex basis

**Decision (James Heidbreder / Equity-Lens):** Global Ship Lease enters
coverage with its DCF on the maintenance basis (operating cash flow less
depreciation), declared per sector playbook #5 (Industrials & Transport,
fleet buyers).

**Reasoning:** GSL's reported capex is dominated by vessel acquisitions —
growth investment, not upkeep. Standard-basis free cash flow charges
whole ships against a single year's cash flow and is distorted by the
lumpiness of purchase timing (the diagnostic shows capex near 2x
depreciation on 5-year medians). Depreciation is the closest available
proxy for maintaining the existing 71-vessel fleet.

**Known bias, disclosed:** depreciation understates true replacement
cost (vessels are replaced at inflated future prices), so the
maintenance basis is generous; we mitigate by capping growth and noting
that the peer-comps lens, not the DCF, is the primary anchor for
cyclical lessors.

**Tripwire:** revisit if fleet growth stops (capex converging to
depreciation would justify the standard basis) or if charter coverage
falls materially below ~85% for the forward year.
