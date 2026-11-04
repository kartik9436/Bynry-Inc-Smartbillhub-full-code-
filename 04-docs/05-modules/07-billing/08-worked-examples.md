# billing — Worked Examples & Rules-Coverage Workbook (verification fixture)

> **Purpose (PO directive 2026-08-08):** run real examples + variations through the model so billing is verifiably productized, and show WHERE every rule family is managed. All arithmetic below is machine-computed with the ratified rounding rule (per line, half-up, 2dp at finalization; NUMERIC(18,6) upstream). These examples seed the billing golden tests and story TCs at pack authoring.
> Status: fixture + math for PO verification. Rules cited by BR-ID; nothing here invents a rule.

## 1. The fixture tenant — Brazos Bend MUD

One tenant configured end-to-end; every number below is entered through the product surfaces named in §2 (nothing hardcoded).

**Services enabled (8 of the 10-service catalog):** Electric, Water, Gas, Sewer, Trash, Broadband, Solar, Battery.
**Tax authorities (jurisdiction reference data):** TX State 6.25% · Travis County 1.00% · City franchise 2.00% · PUC 0.20% (effective 9.45% on taxable lines).
**Tenant billing settings:** late fee 1.5% min $5.00, grace 5 calendar days from due date · due-days 21 (cycle) · overcharge guardrail 200% · write-off $5 · back-bill cap 12 mo (theft exempt) · deposit interest 2.0%/yr simple · allocation: oldest first, usage+base→taxes→fees.
**Charge codes:** LATE (1.5%/min 5) · NSF $30 · RECONN $45 · CONN $25 · TAMPER $500 — each with its own GL.
**Plans (each = bundle: rate schedules + base + deposit/charge rules per BR-RAT-025):**

| Plan | Services & rates | Base/mo | Deposit (category) |
|---|---|---|---|
| **Residential Standard** | Electric TOU (summer on $0.22 / mid $0.14 / off $0.09; winter $0.18/$0.12/$0.08) · Water tiers (0–5 kgal $4.00 / 5–15 $6.50 / 15+ $8.00) · **Sewer 90% of the water VOLUME @ $5.0000/kgal** · Trash flat $18 | Elec $12 · Water $8 | Residential $150 |
| **Small Commercial** | Electric TOU (on $0.19 / mid $0.12 / off $0.075) + demand $9.50/kW · Water flat $5.20/kgal · **Sewer 90% of volume @ $5.0000/kgal** | Elec $48 · Water $15 | Commercial $400 |

> ⚠ **BOTH SEWER CELLS READ *"Sewer 40% of water usage-$"* / *"Sewer 40%"* UNTIL
> 2026-09-08.** `CR-081` (PO ruling 2026-09-07) moved sewer from a percentage of
> the water CHARGE to a percentage of the water VOLUME priced on a sewer rate of
> its own, and the Product Owner **re-signed six ❄️ frozen figures** the next day
> under HUMAN-GUIDE §6, verbatim: *"C — factor 90%, rate $5.00 → $36.00, which is
> what a real sewer customer actually pays"*. The **90 is a return-to-sewer
> factor** — the share of metered water that physically reaches the sewer,
> 79–95% across North American municipal utilities — and **not** the price ratio
> the 40 was. **The irrigation allowance is NOT made by lowering it**: the
> industry answer is winter-quarter averaging (B4's own *"winter-averaging
> v1.1"*), which this product does not do.
>
> ⚠ **WE-6 IS THE EXCEPTION AND IT IS DELIBERATE.** Its sewer line was NOT among
> the six put to the PO, so it still reads the old way below and is stamped
> there. `10-scripts/03-golden-verify.py` Part 4 asserts that gap so it cannot be
> closed by accident; it is with the PO as `OQ-RAT-12347`.
| **Industrial** | Electric energy $0.085/kWh + demand $11.00/kW (meter multiplier ×10) | Elec $180 | Industrial $1,200 |
| **Riders** | Solar capacity $10/unit · Battery $12/unit (taxable like base, prorated) | — | — |
| **Gas add-on** | Gas flat $1.15/ccf | $6 | — |
| **Broadband add-on** | Flat $49/mo (non-metered — completeness gate skips read-less services) | — | — |

## 2. Where every rule family is MANAGED (the productization map)

| Rule family | Managed in | Level | Versioned? | Who edits | BR anchor |
|---|---|---|---|---|---|
| Service catalog | platform seed → Settings→Services enable/disable | tenant | — | System Admin | BR-RAT-024 |
| Rate schedules (tiers/TOU/demand/seasonal/capacity/%) | Plans & Rates → Rate schedules | per service | **effective-dated tariff versions**; history billed on its version | Admin (publish) | BR-RAT-021/026/028, B2 tariff_versions |
| Plans (bundles) | Plans & Rates → New Plan wizard | plan | plan versions; account snapshots at assignment | Admin publish, Clerk draft | BR-RAT-025, BR-CUS-013/014 |
| Base charges | plan wizard, per service | plan×service | with plan version | Admin | BR-RAT-012/027 |
| Deposits | plan × consumer category (fixed $) | plan | with plan version | Admin | BR-CUS-025, plan_deposit_rules |
| Charge codes / penalties | Settings → Reference data → Charges | tenant | audit-locked once used | Admin | BR-BIL-007, charges table |
| Late fee | Settings → Billing (%, min, grace mode+days) | tenant | audited | Admin | BR-BIL-001/002/008 |
| **Collection floor** — the balance below which the WHOLE ladder stops (no late fee, no certified letter, no disconnection notice) | **Settings → Configure**, beside the collections/dunning settings | tenant | audited | Admin | BR-BIL-001 as amended 2026-08-12 (PO, OQ-137 ladder half + OQ-157) — **seeded default $25.00**, per utility, never a platform constant |
| Taxes | jurisdiction reference + per-authority rates; account exemption flag | tenant + account | rate changes dated | Admin; exemption per account | B4.2, GT-10/11 |
| Credits / debits (adjustments) | account actions → Adjustment (reason + GL + approval) | account | append-only rows | Clerk w/ approval | B4 §Credits, adjustments table |
| Allocation order | Settings → Billing | tenant | audited | Admin | BR-PAY-010 |
| Budget billing | plan flag + Settings → Budget params + per-account override ±30% | tenant + account | audited | Admin; override Clerk+reason | BR-BIL-017, OQ-068 |
| GL mapping | Settings → Finance → Account mapping | tenant | **stamped per line at issue** — history never re-maps | Admin+finance | BR-BIL-010 |
| Templates | Reference data → Templates (designer) | tenant, per type × category | **append-only versions, pinned at issue** | Clerk drafts, Admin publishes | BR-BIL rows pending Lane B B-6..B-8 |
| Read validation / estimation | Settings → Read validation rules | tenant (per service) | audited | Admin | BR-MET-020/026-030 |
| Numbering | Settings → Numbering (series) | tenant | — | Admin | BR-TEN-035 |

## 3. Worked examples (WE) — machine-computed

### WE-1 · Baseline multi-service residential (= BS-1, the reference bill)
Jul 1–31 · TOU 120/200/380 kWh · water 8 kgal · solar 4 units · prior balance $45 past grace.
**Sewer: 90% × 8 kgal = 7.2 kgal @ $5.0000 = $36.00.** Taxable $242.10 → tax $22.87 (15.13+2.42+4.84+0.48) → current **$269.97** → total due **$314.97**. Posting: DR AR 269.97 / CR 4100 88.60 · 4105 12.00 · 4110 39.50 · 4115 8.00 · 4120 36.00 · 4130 18.00 · 4150 40.00 · 2200-03 22.87 · 4200 5.00. *(BR-BIL-010/011, B4.2/4.4, BR-RAT-015 ❄️ SUPERSEDED by CR-081, BR-RAT-018/021/026)*
> ❄️ **RE-SIGNED 2026-09-08.** Read *"Taxable $221.90 → tax $20.97 (13.87+2.22+4.44+0.44) → current $247.87 → total due $292.87"* with `4120 15.80` and `2200-03 20.97` until that date.

### WE-2 · Variation: same bill, tax-exempt account
All tax lines vanish (account-level exemption). Current **$247.10**, total **$292.10**. *(GT-11)*
> ❄️ **MOVED WITH WE-1's RE-SIGN, 2026-09-08.** Read *"Current $226.90, total $271.90"* until then. This is not a seventh signed figure: it is WE-1's own taxable subtotal (`$242.10`) with the tax lines removed, and that subtotal is explicitly part of the re-sign.

### WE-3 · Variation: minimum bill kicks in
Water-only account, 0.4 kgal: usage 1.60 + base 8.00 = 9.60 < min $15.00 → **"Minimum bill adjustment" +5.40 (taxable)**; tax on 15.00 = 1.42 (0.94+0.15+0.30+0.03) → total **$16.42**. *(BR-RAT-028, GT-13)*

### WE-4 · Small Commercial: TOU + demand
On 850×0.19=161.50 · mid 1400×0.12=168.00 · off 2200×0.075=165.00 · **demand 14.2 kW×9.50=134.90** · elec base 48 · water 12 kgal×5.20=62.40 · water base 15 · **sewer 90%×12 kgal = 10.8 kgal @ $5.0000 = 54.00**. Taxable **$808.80** → tax $76.44 (50.55+8.09+16.18+1.62) → total **$885.24**. *(BR-RAT-014/021)*
> ❄️ **RE-SIGNED 2026-09-08 (`CR-081`).** Read *"sewer 40%×62.40=24.96. Taxable $779.76 → tax $73.70 → total $853.46"* until then. ⚠ Note the DIRECTION: on the charge basis this commercial account paid **more** sewer per gallon than a residential one ($5.20/kgal flat vs a $4.9375/kgal tiered average), which the volume basis removes; at 90% every one of the six figures more than doubles anyway.

### WE-5 · Industrial: multiplier ×10
Register delta 4,820 × mult 10 = 48,200 kWh × 0.085 = **4,097.00**; demand 182 kW × 11.00 = 2,002.00; base 180. Taxable $6,279.00 → tax $593.37 → total **$6,872.37**. Multiplier applies BEFORE rating, at read consumption. *(B4.4, GT-5 principle)*

### WE-6 · First bill: move-in Jul 12 (20/31 days) + one-time lines
Bases prorate: elec 12→**7.74**, water 8→**5.16**, trash 18→**11.61**. Tier spans scale: tier-1 5 kgal → **3.225806 kgal**; usage 4.2 kgal → T1 12.90 + T2 0.974194×6.50=6.33. TOU 70/120/210 → 15.40+16.80+18.90. Sewer 40%×19.23=7.69. Taxable $102.53 → tax $9.70. Plus **deposit $150.00 (non-taxable → deposit liability)** + **CONN $25.00 (fee, non-taxable)**. Total first bill **$287.23**. *(BR-BIL-012, B4.3/4.4)*
> ⚠ **THIS EXAMPLE'S SEWER LINE IS STALE AGAINST `CR-081` AND IS DELIBERATELY NOT MOVED — `OQ-RAT-12347`, WITH THE PO.** A signature covers only what was shown, and the 2026-09-08 re-sign named SIX sewer amounts across FIVE worked examples; **this is a seventh, on a sixth example, and nobody put it to them.** On the ruled basis it would be 90% × 4.2 kgal @ $5.0000 = **$18.90**, taking taxable to **$113.74** and the total to **$299.49**. Those three figures are recomputed on every run by `10-scripts/03-golden-verify.py` **Part 4**, beside the signed ones, so this gap cannot be closed by accident in either direction. Do not "fix" the line above without a re-sign.

### WE-7 · Final bill: both settlement directions
Deposit $150 held 14 mo @ 2% simple → interest **$3.50** → deposit credit **$153.50** applies first.
- **Case A** final charges $142.30 → refund **$11.20** → refund flow.
- **Case B** final charges $289.40 → still due **$135.90** → settlement path: collect / master-transfer (landlord-linked units only) / payment plan / (≤$5 would write off). *(BR-BIL-013, BR-CUS-056/057)*

> ⚠ **AMENDED 2026-08-12 (PO ruling, OQ-158) — the deposit settles EVERYTHING OUTSTANDING, not just the final bill.** Verbatim: *"everything outstanding"*. **Both figures above are UNCHANGED**, and that is checkable rather than asserted: WE-7's account carries **no arrears**, so the final bill and the closing position are the same number and the two readings agree. **The case the ruling is about, worked (prototype move-out step 3):** a **$120.84** prior balance sits beside the final charges inside a *Final amount due* of **$184.20**. Applying WE-7's **$153.50** deposit credit to the BILL alone refunds **$90.14** to a customer who still owes **$120.84** on an account that is now closed; under the ruling the **$120.84 is inside the settled base** and the refund does not happen. Pairs with the PO's OQ-179 ruling of the same day — no mid-tenancy deposit differential exists at all, so the deposit is applied exactly ONCE, at closure. *(BR-BIL-013 as amended)*

### WE-8 · Budget bill: level month + settle-up
Trailing-12 actuals $2,904 → level **$242**. July actual 292.87 → variance −50.87 · Aug actual 231.40 → +10.60 · Sep actual 198.75 → +43.25; running balance −50.87 → −40.27 → **+2.98** (bill shows all three columns). Settle-up month: balance collected/credited as a **non-taxable AR-timing line** — revenue and tax were already recognized on the monthly actuals; the level payment is a collection schedule, never a price. *(BR-BIL-017)*

> ⚠ **AMENDED 2026-08-12 (PO ruling, OQ-164) — the FINAL bill of an enrolled account is the LEVEL ONLY.** Verbatim: *"Level only"*. On this chain, with the level **$242** and the variance balance **−40.27**, a move-out asks for **$242.00** — **not $282.27**, which is what folding the accumulated variance into the last level payment would produce. The variance is settled through the settle-up, which is its own event. **The three figures above are unchanged** (−50.87 → −40.27 → **+2.98**), as is the settle-up month's own arithmetic: 242 − 2.98 = **239.02** on a credit, 242 + 40.27 = **282.27** on a collection — that 282.27 is the SETTLE-UP figure and is not the final bill. ⚠ **Still OPEN — OQ-142**, which account the settle-up line touches; the PO challenged the premise on 2026-08-12 and the fork (revenue on actuals + one holding account, versus revenue on the level) is theirs to settle. The tax argument is the reason the fork exists: the customer CONSUMES **$292.87** and is ASKED for **$242.00**, and a state taxes what was consumed. *(BR-BIL-017/072 as amended)*

### WE-9 · Correction workflow: water read 8 → 6 kgal after issue
Recompute: water 26.50 (was 39.50) · **sewer 90%×6 kgal = 5.4 kgal @ $5.0000 = 27.00** (was 36.00 on 8 kgal) · taxable 220.10 → tax 20.80 (13.76+2.20+4.40+0.44) → corrected current **$245.90** vs original 269.97. Execution after Admin approval: credit note **−269.97** (full GL reversal) + rebill **+245.90** (own GL stamps) → customer credit **$24.07**;
> ❄️ **RE-SIGNED 2026-09-08 (`CR-081`).** Read *"sewer 10.60 (was 15.80) · taxable 203.70 → tax 19.25 (12.73+2.04+4.07+0.41) → corrected current $227.95 vs original 247.87 … credit note −247.87 … rebill +227.95 … customer credit $19.92"* until then.
> customer had paid in full → 24.07 carries as credit per allocation rules; corrected bill renders on current template version citing the original. Every record append-only. *(BR-BIL-014, BR-BIL-004, J6)*

> ⚠ **THE OTHER TWO CORRECTION CLASSES WERE RULED 2026-08-12 and neither touches a figure above.** WE-9 is the class-**R** restatement and is unchanged. **Class C (goodwill / concession), OQ-105 + OQ-168:** the credit debits a **separate write-off account** — DR write-off / CR customer credit balance — so the original service revenue is never reversed; worked on **GT-6**, a **$25.00** credit against a **$247.30** invoice leaves **$222.30** owing either way and what moves is the BOOKS. Concessions get their **own** account, separate from bad debt (OQ-187, *"Seperate them"*: a year-end **$4,200** was **$1,700** given + **$2,500** uncollectable) — that account needs a **finance re-sign** and until it exists concessions land on the seeded "Bad debt" designation. **Class D (document-only), OQ-103 + OQ-169 + DEF-084:** the case reissues a **corrected copy**, a later reprint renders **the corrected one**, and reissues **ACCUMULATE** — each composed from the instance before it, so an address fix a week after a name fix cannot bring *Sara* back in place of *Sarah*. Balance delta stays exactly **$0.00**. *(BR-BIL-014/030/041 as amended)*

### WE-10 · Back-bill: 6 unbilled months ACROSS A RATE CHANGE
Water 6 kgal/mo Jan–Jun; tariff v3 until Mar 31 (T1 4.00/T2 6.50/base 8.00), v4 from Apr 1 (4.25/6.85/8.50). Jan–Mar: usage 26.50 + base 8.00 + **sewer 90%×6 kgal @ $5.0000 = 27.00** = **61.50/mo**; Apr–Jun: 28.10 + 8.50 + **27.00** = **63.60/mo**. One bill, 6 period-labeled groups: taxable $375.30 → tax $35.47 (23.46+3.75+7.51+0.75) → total **$410.77**. Each period priced on ITS version — never today's rates. *(BR-BIL-018, B2 tariff_versions)*
> ❄️ **RE-SIGNED 2026-09-08 (`CR-081`) — TWO of the six figures are here.** Read *"sewer 10.60 = 45.10/mo; Apr–Jun: 28.10 + 8.50 + 11.24 = 47.84/mo … taxable $278.82 → tax $26.36 → total $305.18"* until then.
> ⚠ **THE TWO HALVES ARE NOW THE SAME SEWER FIGURE AND THAT IS THE RULING, NOT A COPY-PASTE.** On the charge basis a WATER tariff change moved the sewer line with it ($10.60 → $11.24); on the volume basis the same 6 kgal is the same 5.4 kgal of sewer in both halves, and only a change to **sewer's own** rate can move it. The example still proves what it was written to prove — each period is priced on ITS version — through the water lines, which do move (26.50 → 28.10) and through the base (8.00 → 8.50).

> ⚠ **AMENDED 2026-08-12 (PO rulings, OQ-155 + OQ-191) — a group whose period SPANS the version change is split BY DAYS.** **The six figures above are UNCHANGED:** this fixture's change lands on a month boundary (v3 to 31 Mar, v4 from 1 Apr), so no group straddles it and the ruling has nothing to do here. **The variation the ruling is about, worked on the same tariff — a February group of 6 kgal spanning v3 and v4, 3 kgal and 14/28 days each side:** v3 gives base **4.00** + tier1 **10.00** + tier2 **3.25**; v4 gives base **4.25** + tier1 **10.63** + tier2 **3.43**; **group 35.56**. ⚠ **The question that was put to the PO illustrated this as 35.55 — the RULE is what shipped, and it produces 35.56.** 35.55 sums v4's two tier amounts (10.625 + 3.425 = 14.05) BEFORE rounding; **B4.4 / BR-RAT-003 is finance-signed and rounds PER LINE**, so 10.625 → **10.63** and 3.425 → **3.43** separately (14.06). The cent was reported, never hand-adjusted to match the question's text — the same shape as the **$8.30 → $8.31** tax-split cent ruled the same day. **THE BILL IS STILL TAXED EXACTLY ONCE (B4.2):** each segment's finalized lines are carried into one tax-bearing pass, so tax runs once over Σ(rounded taxable lines) — on a Jan–Jun sub-period split 90/181 and 91/181, subtotal **75.59** → tax **6.24** in one pass, where taxing each segment apart and summing gives **6.23**. **A segment with NO read of its own** (nobody read the meter on the reprice day) gets a **day-weighted usage estimate by default** — 14/28 × 6 kgal = **3 kgal** each side — and **is marked ESTIMATED on the bill**; asking metering for an estimate under BR-MET-026 is a tenant option, and refusing is what happens only when neither estimate can be produced. Day-weighting applies to the **base charge and the tier ladder**; it never invents usage where a read exists (B4.3 as amended 2026-08-11). *(BR-BIL-018 as amended · WE-10 unchanged)*

### WE-11 · Theft/penalty bill
Assessed reads entered per required channel (reason-coded, flagged `assessed`): on 150→33.00 · mid 300→42.00 · off 450→40.50 = 115.50 taxable → tax 10.92 (7.22+1.16+2.31+0.23). **TAMPER charge code $500.00 (fee — non-taxable)**. Total **$626.42**. No hand-typed amounts anywhere; usage priced by the engine, penalty by charge code; Admin-approved; back-bill cap does not apply (theft exempt). *(BR-BIL-018/019)*

### WE-12 · Vacation hold starting Jul 16
Usage lines bill through Jul 15 (interim read): TOU 60/95/160 → 13.20+13.30+14.40; water 3.1 kgal → 12.40; **sewer 90%×3.1 kgal = 2.79 kgal @ $5.0000 = 13.95**. **Bases and flat services continue full month** (base-only class): elec 12 + water 8 + trash 18. Taxable $105.25 → tax $9.95 (6.58+1.05+2.11+0.21) → total **$115.20**.
> ❄️ **RE-SIGNED 2026-09-08 (`CR-081`).** Read *"sewer 4.96 … Taxable $96.26 → tax $9.10 → total $105.36"* until then. *(BR-CUS-055 class, B-9 pending Lane B)*

### WE-13 · Estimated bill + true-up (gas)
Jul read missing → estimate 42 ccf × 1.15 = **$48.30** (line labeled "estimated"). Aug actual: register shows 95 ccf across the 2 months → true-up qty 95−42 = **53 ccf** billed Aug at Aug rates = $60.95. Register arithmetic — no reversal of the July bill. *(BR-BIL-006, BR-MET-026..029, GT-9)*

### WE-14 · Credit bill
Prior credit −$60.00; current charges $42.30 → auto-applied → **amount due $0.00**, remaining credit −$17.70 carries (refundable on request). *(BR-PAY-010)*

### WE-15 · Late-fee variations
(a) overdue $400 → 1.5% = **$6.00** · (b) overdue $45 → floor **$5.00** · (c) partial payment: bill 247.87, paid 200 by due date → fee on the **$47.87 overdue portion only** → $5.00 floor · (d) grace boundary: due Jul 20 + 5 calendar days → fee applies from Jul 26; payment Jul 25 = no fee · (e) business-days mode: due Fri Jul 17 → fee from Jul 24 · (f) first-time waiver = manual staff toggle, audited. *(BR-BIL-001/002/003/008)*

> ⚠ **TWO 2026-08-12 AMENDMENTS, neither of which moves (a)–(f).** **(g) THE $25.00 FLOOR IS A PER-UTILITY SETTING AND IT COVERS THE WHOLE COLLECTION LADDER** (OQ-137 ladder half + OQ-157): under it there is no late fee, **no certified letter and no disconnection notice** — an account leaving **$2.40** unpaid is not chased at all, because the certified letter alone costs **$8.00**. **$25.00 is the seeded DEFAULT**, set per tenant in Settings → Configure; a submetered block averaging **$38** a bill and a municipal water utility averaging **$180** cannot share one figure. Case (b) above (overdue **$45**) is above the default floor and is unaffected; case (c)'s **$47.87** overdue portion likewise. **(h) A PAYMENT WITH NO RECORDED ARRIVAL DATE FALLS BACK TO ITS RECORDED DATE** (OQ-156): **$117.01** due 22 Aug, cheque entered **20 Aug** with no banked date → the lateness test uses 20 Aug and **no fee is assessed**; the same cheque entered **25 Aug** is still overdue, so the fallback forgives nothing. Where an actual arrival date exists it still wins (BR-BIL-071, unweakened). *(BR-BIL-001/071 as amended)*

### WE-16 · Capacity proration
Solar 4 units activated Jul 22 → 10/31 days × $40.00 = **$12.90**, taxable like base. *(GT-15, B4.3)*

### WE-17 · Non-metered services only
Broadband $49 + Trash $18 — no reads exist, completeness gate skips read-less services. Taxable $67.00 → tax $6.33 → total **$73.33**.

### WE-18 · Seasonal boundary mid-cycle (Sep 15 – Oct 14, season flips Oct 1)
No boundary read → pro-rata day split 16/30 summer + 14/30 winter per window (electric only shown): on 120 kWh → 64×0.22=14.08 + 56×0.18=10.08; mid 200 → 106.666667×0.14=14.93 + 93.333333×0.12=11.20; off 380 → 202.666667×0.09=18.24 + 177.333333×0.08=14.19. Usage $82.72 + base 12 → taxable $94.72 → tax $8.95 → total **$103.67**. An ACTUAL read dated Oct 1 would replace the split. *(BR-MET-050, BR-RAT-021)*

> ✅ **BUILT 2026-10-01 — THE ENGINE NOW SPLITS THIS PERIOD, AND WE-18 IS ENGINE-VERIFIED AS GT-34 (`DEF-RAT-8832`, closing `DEF-2840`).** The PO closed `OQ-234` on 2026-09-07 — *"please split  swithch it on"* — and for three weeks nothing built it. Every figure above is now what the product bills, through the bulk run and every one-time bill: on-peak `64 × 0.22 = $14.08` + `56 × 0.18 = $10.08`, usage **$82.72**, total **$103.67** (`06-backend/tests/golden/test_gt34_season_crossing_period.py` on the engine; `06-backend/tests/test_oq234_season_split.py` end to end on PostgreSQL). Rating counts the calendar days of the period in each season (`rating.selectors._season_days_between`) and the engine only divides by them (`rating/pricing/season_split.py`). ⚠ **This note read *"⛔ NOT BUILT — THE ENGINE PRICES THE WHOLE PERIOD AT ONE SEASON"* until that date**, and it was true: the product billed this window entirely at winter prices, on-peak `120 × 0.18 = $21.60` against **$24.16**, a **$2.56** difference on one line, on a bill that footed perfectly. *"An ACTUAL read dated Oct 1 would replace the split"* above WAS NOT built until later the same day — a mid-period read on the boundary does not yet split the period at the read; the split is always by days (`DEF-RAT-8849`). ✅ **BUILT 2026-10-01 (`DEF-RAT-8849`, PO *"yes build the season-change day reading"*).** An ACTUAL reading dated 1 Oct cuts each register there: on-peak 80 before / 40 after bills `80 × 0.22 = $17.60` + `40 × 0.18 = $7.20` = $24.80; with mid 110/90 and off 210/170, usage **$83.50**, total **$104.53** (`tests/test_def_rat_8849_season_change_read.py`). An estimate on 1 Oct, or no reading that day, keeps the day split above unchanged.

## 4. Coverage matrix — which example proves which rule

| Rule area | Proven by |
|---|---|
| GL split + balanced posting | WE-1 |
| Tax base + exemption + per-authority rounding | WE-1/2/3/6 |
| Tiers (reset, scaling, multiplier-before) | WE-1/5/6 |
| TOU windows + seasons + demand | WE-1/4/18 · WE-4/5 |
| Sewer % of water VOLUME (`CR-081`; was % of usage-$ until 2026-09-08) | WE-1/4/9/10/12 (+ WE-6, NOT re-signed — `OQ-RAT-12347`) |
| Minimum bill | WE-3 |
| Capacity + proration | WE-1/16 |
| Proration (move-in, hold, season) | WE-6/12/18 |
| Deposits (charge, interest, apply) | WE-6/7 |
| Settlement matrix (all 5 paths) | WE-7 (+write-off/master noted) |
| Budget level-pay + settle-up | WE-8 |
| Correction (credit note/rebill/re-allocation) | WE-9 |
| Back-bill across versions | WE-10 |
| Penalty / assessed reads | WE-11 |
| Estimation + true-up | WE-13 |
| Credits / allocation | WE-9/14 |
| Late fee (all modes) | WE-15 |
| Non-metered services | WE-17 |

**Not yet exampled (deliberate):** payment allocation across multiple open bills (Payments pre-session), refunds execution, dunning tiers (collections), net-metering kWh credits (v1.1). Gaps beyond that: none known — if the PO spots a missing case, it gets a WE number and a computation.
