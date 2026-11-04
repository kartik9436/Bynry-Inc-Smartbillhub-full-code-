# ledger / Finance — Worked Examples & Variations Workbook

> PO directive (2026-08-08): examples, variations, scenarios from the Finance discussion, kept on file. All arithmetic machine-computed (half-up 2dp at finalization). Fixtures chain from the billing workbook (WE-*) and payments scenarios (PE-*): these books are the SAME money, one layer down. Seeds the ledger pack's story TCs + golden tests at freeze.

## LE-1 · Full trial balance — three accounts, deposit lifecycle, master transfer (BALANCED)

Month contains: WE-1 bill (247.87) paid in full incl. 45.00 prior · WE-3 minimum bill (16.42) unpaid · WE-7B final bill (taxable 264.41 + tax 24.99 = 289.40) with deposit applied and remainder transferred to master account ACC-0009.

Postings: opening AR 45.00 · deposit held 150.00 (cash DR / liability CR) · interest accrual 3.50 (DR interest exp / CR liability) · three bills (AR DR 553.69 / revenue CR 506.31 / tax CR 47.38) · deposit application (liability DR 153.50 / AR CR) · master transfer (AR ACC-1055 CR 135.90 / AR ACC-0009 DR 135.90 — AR total unchanged) · payment (cash DR 292.87 / AR CR).

| GL | DR | CR |
|---|---|---|
| 1000 Cash (150.00 + 292.87) | 442.87 | |
| 1200 AR | 152.32 | |
| 6xxx Deposit interest expense | 3.50 | |
| 4xxx Revenue (226.90 + 15.00 + 264.41) | | 506.31 |
| 2200-03 Tax payable (20.97 + 1.42 + 24.99) | | 47.38 |
| 2300 Deposit liability (150.00 + 3.50 − 153.50) | | 0.00 |
| 3000 Opening balance equity | | 45.00 |
| **Totals** | **598.69** | **598.69** ✔ |

**Tie-out (BR-LED-007):** ending AR 152.32 = master-held transfer 135.90 + unpaid WE-3 16.42 — the GL and the account registers agree to the cent, by construction.

## LE-2 · Revenue-by-service slice (BR-LED-001 dimensions)
WE-1 alone: Electric 100.60 (usage 88.60 + base 12.00) · Water 47.50 · Sewer 15.80 · Trash 18.00 · Solar capacity 40.00 · Late fee 5.00 = 226.90 ✔. Same query grouped by premises → LE-6; by authority → LE-3. One dimension set, every slice.

## LE-3 · Remittance — the two bases diverge (BR-LED-002)
July: **billed basis 47.38** (all three bills) vs **collected basis 20.97** (only WE-1's payment cleared; its allocation covered its tax lines in full). State remits on collected → pay 13.87 now, the rest when collected; County on billed → 2.64+2.22+... per-authority rows shown side by side; remittance JE per authority drains 2200-03.

## LE-4 · Accrual auto-reverse (BR-LED-005)
Sep 30 JE-201 (accrual): DR 1210 Unbilled AR 500.00 / CR 4100 500.00 → Oct 1 JE-202 auto-posts the mirror, both linked. October's real bill run posts normally — no double-count.

## LE-5 · ERP export (BR-LED-004)
July export to QuickBooks: one summary JE — 8 GL rows from LE-1's period deltas, each carrying its qbo_ref from the mapping page. Batch EXP-2607-QBO recorded (who/when/hash). Re-running July → blocked with link to the existing batch. Auditor asks "what is the 506.31?" → drill-back lists every dimensioned line.

## LE-6 · By-premises summary (BR-LED-011)
500 Main St (WE-1): billed 247.87 · collected 292.87 · owed 0 · 100% | Oak Grove (WE-3): billed 16.42 · collected 0 · owed 16.42 · 0% | Marina Bay (WE-7B): billed 289.40 · collected 153.50 (deposit) · transferred 135.90 · owed 0 at premises (owed now sits on the master account). Chain integrity per BR-MET-046.

## LE-7 · Tie-out drift detection (BR-LED-007)
Simulated fault: deposit register shows 153.50, GL shows 150.00 → drift −3.50 (a missed interest posting) → S36 red flag names the delta and the subledger — release blocker until explained. Correct state = 0.00/0.00 after application (LE-1).

## LE-8 · Posted-JE "edit" = reverse + repost (BR-LED-003)
JE-104 posted with 250.00 (should be 205.00): one click → JE-105 mirror reversal (linked) + JE-106 draft prefilled → corrected to 205.00 → post. Net effect 205.00; history shows all three, forever.

## LE-9 · Close with a late-dated event (BR-LED-006, BR-TEN-038)
July closed Aug 5. Aug 7 a payment arrives dated Jul 30 → posts into August automatically with an audit note ("period closed; auto-forwarded"), books stay locked, nothing silently lands in a closed month.

## LE-10 · Opening balances tie to GT-16
Cutover batch: DR 1200 AR 184,320.55 (aged buckets per account) / CR 3000 Opening balance clearing 184,320.55 — balanced, idempotent per (batch, account), immutable; forward aging runs from the cutover as-of date (BR-CUS-048/049).

## PO rulings of 2026-08-12 that touch this workbook — NO FIGURE HERE MOVES

Recorded so the next reader knows which examples are now load-bearing for a rule. Every number above stands exactly as computed; what changed is what the product must do with it.

- **LE-3 (47.38 billed / 20.97 collected)** is now the worked case for a **STORABLE per-authority remitting basis** (BR-LED-002 as amended; PO OQ-189 — _"E Remit on what you BILLED, not what you collected - this is also correct"_). Both bases stay computed; the place to RECORD which one each authority files on was built on 2026-08-15 — `tax_remitting_basis_by_authority` on S71 Finance controls (Settings → Configure), keyed by the 2200-nn account. LE-3 is the case that forbids a default: **State files on COLLECTED and County on BILLED in the same month**, so an authority nobody has chosen for is reported by name, never guessed. The collected basis is computable only because a partial payment covers **tax first** (PO OQ-174).
- **LE-4 (JE-201/JE-202) and LE-8 (JE-104 → JE-105 → JE-106)** are written in numbers the product could not produce: the S56 list showed `019ff23d-13ee-7aba-a280-58058e492cb9`. The **`JE-` series is approved (BR-LED-021, PO OQ-176)**, allocated per tenant and **stamped at POST — a draft has no number** (⚠ the decision-log row calls this *"exactly as a draft bill does under BR-BIL-063"*, and BR-BIL-063 in fact numbers a bill **at draft creation** — the contradiction is carried on BR-LED-021, not resolved), so these examples become literal. LE-8's actor is now a **System Admin or Billing Clerk**, never an Executive (BR-LED-003 as amended, PO OQ-175).
- **V-5 (write-off 135.90 → DR 6900 / CR AR)** stays a BAD-DEBT example. A **goodwill concession is a different fact and gets its own account** (BR-LED-022, PO OQ-187) — worked on the year-end figure the PO was shown: **$4,200 = $1,700 given + $2,500 uncollectable**. GT-6's shape: a **$25.00** concession on a **$247.30** invoice leaves the customer owing **$222.30** and the month's revenue unmoved.
- **PE-10's $471.39 batch** is the worked case for **BR-LED-024**: un-reconciling leaves the cash posted; a utility that wants it out posts a manual journal entry.
- **LE-1's tax rows (2200-03)** are the series **BR-LED-023** now numbers automatically: retire **2200-02** and the next authority gets **2200-04** — never 2200-02 again.

## Which of these the PRODUCT now reproduces (2026-08-15, close-the-books lane) — NO FIGURE MOVES

Backend only. Each line names the test that asserts it, so a reader can see the workbook figure come out of the code rather than out of this file.

- **LE-4 — GREEN, except its numbers.** `apps/ledger/manual_je.run_accrual_auto_reversals` posts the Oct 1 mirror through `posting.reverse_entry`, links the pair BOTH ways, and **1210 nets 0.00** while October's revenue is October's bill alone. ⚠ **JE-201 is reproduced and JE-202 is NOT**: BR-LED-021 stamps a number at POST and the mirror is system-posted, which allocates none — true of every system-posted entry in the product. `tests/test_us_led_012_accrual_auto_reverse.py`.
- **LE-8 — the numbers are now literal.** With the tenant's `JE-` counter opened at 104, the first posted entry IS **JE-000104** (`tests/test_us_led_011_manual_je.py`). ⚠ No tenant HAS that counter yet — `apps.tenancy.services.SERIES_DEFAULTS` seeds five series and the journal one is not among them, so entries post UNNUMBERED and say so. The reverse+repost flow itself was already green (2026-08-11).
- **LE-9 — GREEN, and it is the assertion the close turns on.** July closes on Aug 5; a Jul 30-dated event resolves to **Aug 1** with the note *"period closed; auto-forwarded"*; July's trial-balance ROWS AND TOTALS are identical before and after. ⚠ Only the manual JE asks `close.resolve_entry_date` today — a late-dated BILL or PAYMENT still lands where it was dated. `tests/test_us_led_015_month_close.py`.
- **LE-5 — the batch and its gates are GREEN; the NUMBER and the FILE are not.** July exports once, a re-run is blocked with the existing batch on the error, the other granularity and a week inside the month are blocked too, drill-back on the **506.31** revenue opens its dimensioned lines, and a missing `qbo_ref` blocks QBO atomically while CSV stays available. ⚠ **`EXP-2607-QBO` is not reproduced** (no tenant has the `export_batch` series row; the batch records `batch_no = None` and its identity is (period, target)), and **no file is written** — BR-LED-020 v1 is a file export and this lane records the batch and its stored payload. `tests/test_us_led_016_export.py`.
- **LE-1's 598.69 is the WHOLE BOOK, not the July window** — its opening entry is dated at the 2026-06-30 cutover on purpose, so a July-windowed trial balance foots at **553.69**. Both are asserted. The export's totals are asserted to EQUAL `reporting.trial_balance`'s rather than to equal a constant, because the property that matters is one derivation: the ERP and S56 cannot disagree.

## Variations parked for the ledger pack TCs
V-1 partial-payment month (PE-2 figures flow into AR aging) · V-2 NSF month (PE-7: reversal pair + fee line in TB) · V-3 correction month (WE-9: credit note + rebill GL reversals net −19.92 revenue/tax) · V-4 budget month (level 242 cash vs 292.87 revenue — AR timing visible in TB) · V-5 write-off (135.90 → DR 6900 / CR AR after approval) · V-6 refund (PE-9: DR credit / CR cash 57.13) · V-7 multi-authority rate change mid-year (remittance report splits periods).

---

# Cost-of-service capture — LE-11..LE-14 (added 2026-08-15, EP-LED-06)

> Implements the PO rulings of 2026-08-12: **OQ-188 CLOSED** (the product is the system of record for AP and AR both and processes neither) and **OQ-190 CLOSED** (a captured invoice carries an OPTIONAL volume; the unaccounted-for figure is all-or-nothing per period). Placement: `12-governance/02-decision-log.md` 2026-08-15, "THE AP CAPTURE LIVES IN THE LEDGER MODULE".
>
> **NO FIGURE IN LE-1..LE-10 MOVES.** LE-1's July trial balance is **598.69 = 598.69** and stays there, because whether a capture POSTS is **OQ-200, OPEN** — see LE-14. All arithmetic below is machine-checkable from the fixture rows; percentages are volume ratios (BR-LED-032), not money ratios.

## Seed & fixture data — Brazos Bend, July 2026 (the LE-11 purchase set)

**Fixture family:** the same tenant, actors and month as LE-1..LE-9. Tenant **Brazos Bend** (services: Electric · Water · Sewer · Trash · Gas — no Broadband). Actors: **Norma Reyes** (Billing Clerk — captures, edits, voids) · **Alex Reed** (Executive — reads, may not capture, BR-LED-003 as amended) · **Dana Fox** (System Admin). Isolation tenant: **Lone Star Ridge** (J. Okafor). Currency **USD** throughout; amounts stored `NUMERIC(18,6)`, displayed 2dp (OQ-186: API serves 4, screen shows 2).

| # | Reference | Date | Supplier (FREE TEXT — no vendor master, BR-LED-028) | Service / category | Volume | Unit | Amount USD | GL |
|---|---|---|---|---|---|---|---|---|
| CI-1 | RS-2607-0141 | 2026-07-06 | City of Rosenberg — Bulk Water Supply | Water | 400,000 | gal | 1,240.00 | 5110 |
| CI-2 | RS-2607-0158 | 2026-07-13 | City of Rosenberg — Bulk Water Supply | Water | 250,000 | gal | 775.00 | 5110 |
| CI-3 | RS-2607-0175 | 2026-07-20 | City of Rosenberg — Bulk Water Supply | Water | 100,000 | gal | 310.00 | 5110 |
| CI-4 | RS-2607-0192 | 2026-07-27 | City of Rosenberg — Bulk Water Supply | Water | 50,000 | gal | 155.00 | 5110 |
| CI-5 | RS-2607-0208 | 2026-07-31 | City of Rosenberg — Bulk Water Supply | Water | 200,000 | gal | 620.00 | 5110 |
| CI-6 | BVPC-070026 | 2026-07-31 | Brazos Valley Power Cooperative | Electric | 412,000 | kWh | 28,222.00 | 5100 |
| CI-7 | GCGT-2607-88 | 2026-07-31 | Gulf Coast Gas Transmission | Gas | 1,450 | MMBtu | 6,235.00 | 5140 |
| CI-8 | HPV-4471 | 2026-07-15 | Hillcrest Pipe & Valve | O&M | — | — | 1,845.50 | 5200 |
| CI-9 | KMW-2026-118 | 2026-07-22 | Katy Meter Works (40 replacement meters) | Infrastructure | — | — | 12,500.00 | 5300 |

**Unit prices, so every amount is checkable:** water **$3.10 / kgal** (1,000 kgal × 3.10 = 3,100.00 ✔; 400 × 3.10 = 1,240.00 · 250 × 3.10 = 775.00 · 100 × 3.10 = 310.00 · 50 × 3.10 = 155.00 · 200 × 3.10 = 620.00) · electric **$0.0685 / kWh** (412,000 × 0.0685 = 28,222.00 ✔) · gas **$4.30 / MMBtu** (1,450 × 4.30 = 6,235.00 ✔).

**Billed volumes for the same month** (the utility's own invoice lines, read through the billing seam — US-LED-020 §5): Water **910,000 gal** · Electric **389,340 kWh** · Gas **18,900 ccf**.

**Degraded fixture** (drives BR-LED-031's ABSENT case): CI-5 captured **cost-only** — $620.00, no volume — leaving four water purchases carrying **800,000 gal**.

**Isolation fixture:** Lone Star Ridge, `LSR-BW-0091`, City of Bandera, 2026-07-18, Water, **220,000 gal**, $842.00; its own billed volume **214,500 gal**.

## Chart addendum — cost of service · ✅ FINANCE RE-SIGNED 2026-08-18 (BR-LED-037)

⚠ **THIS HEADING READ "PROPOSED chart addendum … NOT SIGNED, pending a finance re-sign" UNTIL 2026-08-18.** On that day the Product Owner — the sign-off authority per their own ruling of 2026-08-11 — finance re-signed all eight codes and names below in the working chat session, together with **4180 Budget billing variance (revenue)**. They were shown the nine codes and names **in plain English**, with the explicit statement that **no dollar figure is attached to any of them** and that **B4/B5 stay ❄️ FROZEN and were NOT edited** — a dated addendum BESIDE the frozen chart, exactly as 4160/4170 were re-signed on 2026-08-11.

**A signature covers only what was shown.** What is ratified is the eight CODES and their NAMES. NOT ratified, and each needing its own ruling: any amount, rate or default posted to these accounts; a rename of any of them; giving one of them a GL designation (a separate ruling AND a migration); and the liability side of a capture, which is still OQ-200 reading (a) and still open.

**The marked-unsigned posture below is unchanged and now governs the NEXT cost account added without a signature.** It is held under test on a SYNTHETIC unsigned code (`06-backend/tests/test_us_led_017_cost_chart.py` TC-5), because no real unsigned subject remains and a guard over an empty set passes vacuously.

The paragraph that follows is the record of the proposal as it stood from 2026-08-15 to 2026-08-18; read it in the past tense.

**This was a PROPOSAL, not law.** B5 line 74 is **❄️ FROZEN — finance-signed 2026-08-08**, and CLAUDE.md is explicit: *"Changing a signed rule or figure needs a finance re-sign via HUMAN-GUIDE §6, never an inline edit."* **B5 IS NOT EDITED BY THIS LANE.** The route is the one the 4160/4170 revenue codes (BR-BIL-067) and the concession account (BR-LED-022) are already on. Until the signature exists these rows seed **marked-unsigned** and no product surface may present them as signed (US-LED-017 TC-5).

**What the chart holds today, for contrast:** exactly **two** expense accounts — **6800 Bank fees** and **6900 Bad debt** (plus **6950 Deposit interest expense**) — every one of them arising from meter-to-cash itself. Purchased power, purchased water, purchased gas, O&M and infrastructure have **no accounts at all**.

| Proposed code | Name | Type | Mirrors | Seeded when |
|---|---|---|---|---|
| 5100 | Purchased power | expense | 4100/4105 Electric | tenant sells Electric |
| 5110 | Purchased water | expense | 4110/4115 Water | tenant sells Water |
| 5120 | Sewer treatment & disposal | expense | 4120 Sewer | tenant sells Sewer |
| 5130 | Trash hauling & disposal | expense | 4130 Trash | tenant sells Trash |
| 5140 | Purchased gas | expense | 4140 Gas | tenant sells Gas |
| 5145 | Broadband transport | expense | 4145 Broadband | tenant sells Broadband |
| 5200 | Operations & maintenance | expense | — (PO's own category, OQ-188) | always |
| 5300 | Infrastructure | expense | — (PO's own category, OQ-188) | always |

**Why 51xx mirrors 41xx digit for digit:** a reviewer checks the whole section in one pass against a ladder finance already signed, and a tenant reading a trial balance finds 4110 and 5110 side by side for the same service. **Seeding follows BR-LED-038** (BR-BIL-067's ruled shape): only the services a tenant sells — Brazos Bend gets 5100 · 5110 · 5120 · 5130 · 5140 · 5200 · 5300 and **not 5145**; Silver Creek Water gets **5110 · 5120** only.

**NOT PROPOSED HERE — the liability side.** If a capture POSTS (OQ-200 reading (a)) the credit needs an `Accounts payable` account in the 2xxx series that **nothing in this product ever drains**, because BR-LED-028 forbids payment runs. That account is deliberately absent from this proposal: it exists only under a reading the PO has not chosen, and proposing it would smuggle the answer into the chart.

## LE-11 · Capture — nine supplier invoices, $51,902.50, and nothing is processed (BR-LED-028/029/030)

Norma Reyes captures CI-1..CI-9 through the S73 modal (IS-6: modal → confirm → toast → `audit_log`). **Register total, July 2026:**

`1,240.00 + 775.00 + 310.00 + 155.00 + 620.00 + 28,222.00 + 6,235.00 + 1,845.50 + 12,500.00 = **51,902.50 USD**`

Per GL account: **5110** 3,100.00 · **5100** 28,222.00 · **5140** 6,235.00 · **5200** 1,845.50 · **5300** 12,500.00 = 51,902.50 ✔.

**What did NOT happen, and it is the rule (BR-LED-028):** no approval was requested, no payment was scheduled, no vendor record was created (the two City-of-Rosenberg spellings a clerk might type are both kept as typed), no ageing bucket exists and no cheque was printed. Two of the nine invoices carry **no volume at all** (CI-8 O&M, CI-9 Infrastructure) and **nothing refused them** — BR-LED-030, PO verbatim *"make a provision and make it optional"*.

**Audit:** nine `supplier_invoice.captured` rows, actor Norma Reyes, append-only (BR-LED-036).

## LE-12 · The reconciliation — 9.00% unaccounted for, and the −13.75% that never prints (BR-LED-031/032)

**Brazos Bend, July 2026, per service (BR-LED-032: `(bought − billed) ÷ bought`, same unit both sides, 2dp, basis labeled):**

| Service | Bought volume | Bought cost | Billed volume | Unaccounted for |
|---|---|---|---|---|
| Water | 1,000,000 gal (5 purchases, all with volume) | 3,100.00 | 910,000 gal | **9.00%** |
| Electric | 412,000 kWh (1 purchase) | 28,222.00 | 389,340 kWh | **5.50%** |
| Gas | 1,450 MMBtu (1 purchase) | 6,235.00 | 18,900 ccf | **ABSENT — `purchase_unit_does_not_match_billed_unit` (MMBtu vs ccf), OQ-201** |
| O&M | — | 1,845.50 | — | — (no volume denominator; BR-LED-031 per-service scope) |
| Infrastructure | — | 12,500.00 | — | — (no volume denominator) |
| **Total cost** | | **51,902.50** | | |

`Water:    (1,000,000 − 910,000) ÷ 1,000,000 = 90,000 ÷ 1,000,000 = 0.0900 → **9.00%**`
`Electric: (412,000 − 389,340) ÷ 412,000    = 22,660 ÷ 412,000    = 0.0550 → **5.50%**`

**This is the PO's own figure** (OQ-188/OQ-190): *bought 1,000,000 gallons, billed 910,000 → 9% unaccounted for* — leak, meter under-registration or theft, **computable only here because only this product holds the billed volumes.**

**THE DEGRADED CASE, which is the whole reason BR-LED-031 exists.** CI-5 is captured cost-only ($620.00, volume omitted — entirely lawful under BR-LED-030). Water now has volume on **4 of 5** purchases totalling **800,000 gal**:

`(800,000 − 910,000) ÷ 800,000 = −110,000 ÷ 800,000 = −0.1375 → **−13.75%**`

— a utility that appears to have delivered more water than it bought. **The product prints the reason instead of the number:** *"no volume captured for 1 of 5 water purchases this period"*. Electric is unaffected and still reads 5.50%: the rule is **per service per period**.

⚠ **A note the next reader needs.** The decision-log row of 2026-08-12 illustrates the message as *"no volume captured for 2 of 5 purchases this period"* while its own arithmetic describes *"volume on four of them totalling 800,000"* — one missing, not two. The fixture above matches the **arithmetic** (1 of 5 missing, denominator 800,000, −13.75%) and takes the quoted string as a message SHAPE. Recorded rather than silently reconciled.

**AND WHY O&M DOES NOT POISON IT.** CI-8 and CI-9 carry no volume and never will — pipe and meters are not a commodity with a delivered quantity. Under the strictest literal reading of *"a period containing any cost-only purchase"* every utility that ever buys a valve would lose its loss figure forever. OQ-190's option (a) — the one the PO answered — says *"an unaccounted-for percentage **per service**"*, so only purchases carrying that service enter its denominator. The tension is flagged on BR-LED-031, not resolved by this workbook.

## LE-13 · Edit, void and the closed period (BR-LED-034/035)

- **Edit while July is OPEN:** CI-3's amount 310.00 → **312.40** on 2026-08-02. The register footer moves to **51,904.90**; the *volume* figures do not move at all, so Water still reads **9.00%**. Audit `supplier_invoice.updated` with before/after.
- **Void, never delete:** CI-4 (RS-2607-0192, $155.00, 50,000 gal) voided 2026-08-03, reason *"duplicate of RS-2607-0175"*. The row **stays visible** in the register with its reason (BR-LED-035) and leaves every aggregate: footer **51,747.50** (51,902.50 − 155.00), water bought **950,000 gal** and **2,945.00**, and the percentage becomes `(950,000 − 910,000) ÷ 950,000 = 40,000 ÷ 950,000 = 0.0421 → **4.21%**`. **A void moves the loss figure, and that is correct** — the gallons were never bought.
- **A capture dated into the closed month:** July closes 2026-08-05 (LE-9). On **2026-08-07** a supplier invoice dated **2026-07-30** arrives; it **auto-posts forward into August** with the audit note *"period closed; auto-forwarded"* (BR-LED-034 riding BR-TEN-038). July's register, its reconciliation and its export batch are **byte-identical** afterwards.
- **⚠ NOT WORKED, because it is not decided:** editing or voiding CI-1 *after* July closes is **OQ-203, OPEN**. July's batch is idempotent (BR-LED-004) so a permitted after-close edit changes a reconciliation the ERP already holds, with no second handover available. No figure is offered for that case.

## LE-14 · The export carries both sides out in ONE batch (BR-LED-039) — and the OQ-200 fork, worked

July 2026 → QuickBooks Online, **after** the period closes (BR-LED-017's L-3b gate is unchanged). Batch **EXP-2607-QBO**, sent 2026-08-08 by Norma Reyes, one content hash, one audit row. **The payable side rides the SAME batch** — a second July batch would be exactly the double-handover BR-LED-004 exists to prevent.

| Section | Rows | Total |
|---|---|---|
| Receivable (LE-5, unchanged) | 8 GL summary rows | Σ DR 598.69 = Σ CR 598.69 |
| **Cost of service (new)** | 5100 **28,222.00** · 5110 **3,100.00** · 5140 **6,235.00** · 5200 **1,845.50** · 5300 **12,500.00** | **51,902.50** |

`28,222.00 + 3,100.00 + 6,235.00 + 1,845.50 + 12,500.00 = **51,902.50**` ✔

**THE FORK, BOTH SIDES WORKED SO THE PO CHOOSES BETWEEN CONSEQUENCES RATHER THAN WORDS (OQ-200):**

- **Reading (a) — capture POSTS** `DR cost-of-service / CR accounts payable`. July's trial balance moves from LE-1's **598.69 = 598.69** to **52,501.19 = 52,501.19** (598.69 + 51,902.50 on both sides). **LE-1 is golden test GT-51** under B5's mechanical allocation (LE-n → GT-(50+n)), so this is a change to a finance-signed figure and takes the HUMAN-GUIDE §6 re-sign route. It also creates a payable **nothing in this product ever drains** (BR-LED-028 forbids payment runs): at $3,100.00 of water a month, twelve months leave **$37,200.00** of settled-elsewhere payable standing in the books. BR-LED-024 is the precedent for what happens next — *"Utility will balance the books by manual journal entry - if required"*.
- **Reading (b) — capture posts NOTHING.** LE-1 is **unmoved**, the reconciliation and the export work exactly as above, and the cost section is a **labelled register extract**. Its total must never be summed into a trial-balance footer that does not contain it (US-LED-021 TC-7) — an unlabelled mixed total is a figure no reader can reconcile.
- **Reading (c) — `DR cost / CR cash` at capture** asserts the invoice was paid. Wrong for anything unpaid, and the product has no way to know. Recorded so it is not re-proposed.

**Nothing is chosen here, and the capture stores its GL account either way** — closing OQ-200 later is a posting decision, not a re-capture.

## Variations parked for the EP-LED-06 TCs
V-8 a period with **no purchases at all** (every service reports ABSENT with reason "no purchases captured", never 0.00%) · V-9 **two suppliers for one service** in a month (denominators sum; the drill-back lists both) · V-10 **a purchase in a foreign currency** against a USD-locked tenant (BR-TEN-042 currency lock; refused, not summed — the DEF-081 mixed-currency lesson) · V-11 **an HOA fixture**: one bulk supplier invoice against 42 member bills, which is the OQ-188 customer type whose whole finance problem this is · V-12 a **negative/credit note from a supplier** (not captured today; a credit memo has no path and is named rather than assumed).
