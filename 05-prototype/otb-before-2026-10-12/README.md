# One-time bill — before the fix (2026-10-12)

Reproduction of `DEF-BIL-10067`, `-10068` and `-10069` (decision log top row, 2026-10-12) on **brazosbend**, build **2.569.0**, before any fix. Every shot is 1440 wide and was taken from the running product. No product code was changed.

## The example, and how it differs from the PO's

Brazos Bend has **electric and water only**. Sewer, trash and storm water are switched off for this tenant and no account carries them, so the PO's water + sewer + trash + storm-water account cannot exist here. The closest account was used:

| PO's example | Here |
|---|---|
| Mark Wood, water + sewer + trash + storm water | **AC-2026-00012 · Luca Lindqvist**, electric + water, plan *Sample — Residential* |
| Water and sewer re-priced 15 Sep | **Electric** re-priced 15 Sep (new version of *Sample — Electric usage*: $0.115 / $0.140 / $0.165 per kWh) |
| Storm water re-priced 20 Sep | **Electric** re-priced again 20 Sep ($0.120 / $0.145 / $0.170) |
| Previous read 2.9 on 31 Aug | Water meter W-9011: **2.9 on 31 Aug** (posted through Meter Reads) |
| Reading typed on step 2: 4.6 | **4.6** typed for W-9011 |

Water could not get its own 15 Sep version: its schedule already has a version from 1 Mar 2027, and the product only accepts a new version dated after the newest one. So **water has no change in September and electric has two** — the bug still shows, because water is cut at electric's dates.

The 29 Sep water read (8.0) had no previous value because the 31 Aug read was added after it, so it was re-posted (same value, "upsert") through Meter Reads; it now reads 2.9 → 8.0 = **5.1 kgal**.

## What was found

| Issue | Reproduced | What the screen shows | Shot |
|---|---|---|---|
| OTB-1 usage stays when the reading changes | **Yes** | W-9011 typed 4.6 (expected 4.6 − 2.9 = 1.7 kgal); Usage stays **5.1 kgal**, and step 3 still bills 5.1 kgal ($20.40) | `otb-01-usage-not-recalculated.png`, `otb-01-04-step2-full-after-typing-4.6.png` |
| OTB-2 Rates table is a sample | **Partly** | The panel is headed *SAMPLE — RESIDENTIAL*, which **is** this account's plan here (the tenant's plans are named "Sample …"); it is not another plan. The PO's "(April)" sample could not be told apart on this tenant | `otb-02-03-rates-not-recalculated.png` |
| OTB-3 Rates table does not recalculate | **Yes** | After typing 4.6: Electric **$127.60**, Water **$44.40**, Before tax **$172.00** — unchanged | `otb-02-03-rates-not-recalculated.png` |
| OTB-4/13 one version shown; usage not split | **Yes** (on electric) | Rates table shows only *Electric · from 09/20/2026*; the 1 Aug and 15 Sep versions are not shown. Step 3 has **one** electric usage line, 800 kWh, Tiered, **$91.60** — not split by version. (Water has no change here, so "water not split" is correct for water.) | `otb-04-13a-rates-one-version-only.png`, `otb-04-13b-step3-usage-one-line-not-split.png` |
| OTB-11/12 base repeated, every service cut 3 ways | **Yes** | Step 3: Electric Base $12.00 **×3**, Water Base $8.00 **×3** (water has no change of its own but is cut at electric's 15 and 20 Sep). Subtotal **$172.00**, tax $3.44, total **$175.44** | `otb-11-12-base-repeated-cut-3-ways.png` |
| OTB-14 trash quantity × rate ≠ amount | **No — no trash on this tenant** | — | — |
| OTB-15 storm water 0 ERU | **No — no storm water on this tenant** | — | — |
| OTB-7 draft saved with the un-recalculated figures | **Yes** | Draft **BL-2609-000101** saved at **$175.44**, water 5.1 kgal (not 1.7). The typed 4.6 was never saved to Meter Reads (no read batch was posted on Continue) | `otb-06-08-09-draft-detail.png` |
| OTB-6 no Approve or Cancel on the draft | **Yes** | No Approve button. *Cancel this bill* is in the ⋯ menu but **disabled**, tooltip "A draft is not canceled — it is simply not issued." *Fix this bill* and *View the bill as sent* are also disabled | `otb-06-draft-no-approve-cancel-disabled.png` |
| OTB-8 "Cycle bill" label | **Yes** | Head reads **BILL · CYCLE BILL** on a one-time draft (stored `bill_type = cycle`) | `otb-08-cycle-bill-label.png` |
| OTB-9 Total due "—" | **Yes** | AMOUNT panel: Current charges $175.44, **Total due —** | `otb-09-total-due-dash.png` |
| OTB-10/17 "Already billed", and late | **Yes** | Second one-time bill, same account, 1–30 Sep: step 1 shows nothing; the refusal arrives at **step 3**: "**Already billed for this period.** BL-2609-000101 · 10/12/2026 · by Dana Whitfield · Open that bill" — the bill is a draft, not billed | `otb-10-17a-step1-no-duplicate-warning.png`, `otb-10-17b-already-billed-at-step3.png` |
| OTB-18 closed month refused | **Yes** | August closed (see below). AC-2026-00054, 16–31 Aug: step 1 says nothing; at Send: "**Failed. The bill was not sent.** … the books refused bill BL-2608-000104 … this journal entry is dated 2026-08-31, which falls inside the CLOSED fiscal period 2026-08-01 … 2026-08-31." | `otb-18a-step1-no-closed-month-note.png`, `otb-18b-step4-ready-to-send.png`, `otb-18-closed-month-refused.png` |

### Also seen (not in the PO's list)

* The draft's Usage panel reads **799.999999 kWh** for an 800 kWh read — the three day-weighted parts do not add back (`otb-x1-usage-799.999999-kwh.png`).
* Electric 800 kWh priced **$91.60**, below both the old price (500 × 0.11 + 300 × 0.135 = $95.50) and the 20 Sep price ($103.50): each of the three parts gets its day-share of the usage and the full 500 kWh first tier, so all 800 kWh fall in tier 1. That is the tiered split rule Q-b the PO has since ruled on.
* On AC-2026-00054's August preview, the Rates table says base $12.00 / $8.00 but step 3 prints Base **$0.00** for both services.
* **September was already closed** in the seed data (closed 2026-08-03 by the seed). Every one-time bill with a period ending in September is refused at Send too, not just August.

## Closing August

The Close page only offers the current month (October), so August was closed through the product's own API, `POST /finance/periods/close` (from 2026-08-01, to 2026-08-31, with a reason) — the same call that page makes.

## Data left in place for the fix lane

| What | Detail |
|---|---|
| Account (example) | **AC-2026-00012**, Luca Lindqvist, 123 Willow Bend Dr · Unit 1 |
| Account (closed month) | **AC-2026-00054**, Nilesh G, 301 Mill Pond Ln · Apt 102 |
| Rate versions | *Sample — Electric usage*: new versions **from 2026-09-15** and **from 2026-09-20** (it is used by every account on *Sample — Residential*) |
| Reads | W-9011: **2.9 on 2026-08-31** (batch RB-2610-0055); 29 Sep read re-posted as 8.0 (RB-2610-0056) |
| Drafts | **BL-2609-000101** AC-2026-00012 1–30 Sep $175.44 · **BL-2608-000102** AC-2026-00054 1–31 Aug $146.88 · **BL-2609-000103** AC-2026-00054 1–30 Sep $141.48 · **BL-2608-000104** AC-2026-00054 16–31 Aug $146.88 (refused at Send) |
| Fiscal close | **August 2026 closed** 2026-10-12 14:20 UTC (September was already closed) |
