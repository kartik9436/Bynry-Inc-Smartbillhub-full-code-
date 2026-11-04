# J-FIX-TWENTY: the Fix a bill walk (CR-180-BRC10), 2026-10-12/13

The journey is `08-qa/01-e2e/journeys/J-FIX-TWENTY-the-fix-a-bill-scenario-suite.md`. The tenant is `brazosbend` and the user is Dana Whitfield, a System Admin, who sends each case and also approves it.

Every scenario was driven through the screens: Billing → Fix a bill → Bills → Fix → Check → Send → Approve and issue. The screenshots in this folder are named `sNN-1-bills`, `-2-fix`, `-3-check`, `-4-send`, `-send-waiting` and `-done`.

The records were read with a read-only SQL session with `app.tenant_id` set. These tables were checked:

- invoices and invoice_lines
- credit_notes
- correction_cases, correction_case_bills and correction_case_items
- journal_entries and journal_lines
- outbound_messages
- allocations
- meter_reads and read_corrections
- audit_log

**Delivery rows are queued, never sent.** No provider runs locally.

PASS / FAIL in the record columns means what was written, after any fix. A defect id names what the walk found. The fix commits are listed at the end.

## Data limits (said plainly)

- **No account with autopay has a bill on this tenant.** S2 was walked on a single-family account that had paid its bill in full by an ordinary payment.
- **Only August and September are billed.** "Several months" means two months (S4, S5, S7).
- **The master accounts have no bills.** S6 was walked on a small-commercial account.
- **There is no move-out final bill.** S10 was walked on an ordinary September bill.
- **There is no meter with time-of-use registers.** S7 was walked on demand pricing.
- **No 100-bill run exists.** S17 was not walked at 100 bills (see S17).
- **New electric schedule versions take effect on 15 Sep and 20 Sep.** They were added after the September bills were issued. Any re-price of a September bill therefore re-rates its electric charge per part, even when the row named something else (S1, S4, S12, S13 and S15). This follows the signed rule that a bill is priced on the version in force on its service days. It is listed under "Questions" below.

## Scenarios

| # | What was done | Figures (preview → issued) | Bills | Ledger | Payments | Delivery | Meter reads | Audit | Defects |
|---|---|---|---|---|---|---|---|---|---|
| S1 | Residential single-family, Ben Bennett, BL-2610-000053 (unpaid). Wrong reading W-5001 1,057 → 1,054. | $198.90 → $183.60 (−$15.30); issued BL-2610-000109 at $183.60 | PASS: old corrected, snapshot unchanged, new bill links to it, CM-0002 −198.90 | PASS: 2 balanced entries dated 2026-10-02 | PASS: nothing paid | PASS: paper row queued | PASS: 1,054 saved and locked (billed) | PASS | 10077, 10078, 10079, 10080 (all fixed). BL-2610-000109 was issued before 10077 was fixed, so it still prints Total due $382.50 (it is immutable). |
| S2 | Single-family, Elena Ellery, BL-2610-000056, paid in full (no autopay account has a bill). Wrong plan: Sample Commercial v1. No plan on this tenant raises the bill: Residential Standard is refused (time-of-use) and Industrial is refused (demand). | $137.70 → $120.77 (−$16.93) = issued BL-2610-000110 | PASS (CM-0003) | PASS (10-02) | PASS: the $137.70 payment was released by a new −137.70 row; $120.77 went to the new bill; $16.93 stays as credit; no new payment; total due −16.93 | PASS | n/a | PASS | — |
| S3 | Single-family, Ines Iversen, BL-2610-000060, paid. Three rows: reading E-5008 3,596 → 2,996; Local tax 2% → 1.5%; missed charge METER-TEST × 1 ($25). | $221.85 → $163.29 (−$58.56) = BL-2610-000111 | PASS (CM-0004) | PASS; the fee is booked to 4630 | PASS: $163.29 moved to the new bill, $58.56 credit, no refund | PASS | PASS (2,996) | PASS | 10081, 10082, 10083, 10084 (fixed). The first attempt with CC-METERTEST failed at issue; it was resumed with Try again and then closed without correcting. |
| S4 | Multi-family, Sam Rylance. August BL-2609-000043 (paid) and September BL-2610-000093 (part-paid $119.34). Wrong rate: the water schedule moves to its 10/01 version, on both bills. | Aug +$3.21 → $202.11; Sep +$7.80 → $206.70; net +$11.01 = issued | PASS: one case, 2 credit notes and 2 new bills | PASS: August entries posted 2026-10-01 (August is closed), September entries 10-02 | PASS: each bill's payment moved to its own new bill; owes $79.56 → $90.57 | PASS | n/a | PASS | Question: the August new bill is due 09/22/2026, a date already past |
| S5 | Small commercial (no unpaid ones exist). Both months. Rows: wrong plan (to Sample Residential), $25 goodwill on September only, and a customer name change. | Aug +$12.99, Sep +$102.04, net +$115.03; owes $618.28 → $708.31 | PASS: CM-0007 and CM-0008, goodwill CM-0009 −25.00, reissued pages carry the new name | PASS; goodwill posted DR 6900 write-off / CR 2400 customer credit | PASS: the goodwill was drawn down by the September new bill | PASS: paper rows, plus the credit-issued notice | n/a | PASS | 10085 and 10086 found here and on S6. Question: the "Small Commercial" plan would have priced electric at $0.00 with no refusal. |
| S6 | Commercial (masters have no bills), BL-2610-000098, paid. Goodwill $40 only. | Credit only: −$40.00; no new bill | PASS: CM-0010 −40; old bill stays issued | PASS: DR write-off / CR customer credit 40, dated 10-12 | PASS: the credit sits on the account | PASS: credit-issued notice queued by email and paper; no "payment received" receipt after 10086 | n/a | PASS | 10085 (fixed: For finance showed $0, Done showed $0) and 10086 (fixed: the goodwill queued "payment received" receipts on print, email and SMS) |
| S7 | Light industrial, two months, both paid, plus $1,045.09 carried credit. Walked as a wrong plan to Industrial (energy + demand), because no meter has time-of-use registers. | Each bill $5,225.44 → $6,354.28 (demand 100 kW × $11.00 = $1,100.00; energy 54,000 kWh unchanged), net +$2,257.68 = issued | PASS (CM-0011 and CM-0012) | PASS (10-01 and 10-02) | PASS: credit used once; September new bill still owes $1,128.84 | PASS | n/a | PASS | 10087 (fixed: Check had promised "still owed $83.75" on both bills). Question: water fell to $0 "not priced on this plan". |
| S8 | Municipal, August BL-2609-000049, paid. Reprint only: mailing address and bill message. The September bill was refused by BR-BIL-043 (re-pricing moves $4.43). | Amounts identical ($180.40) | PASS: no credit note; reissued copy 1 with the changed fields | PASS: no entry (225 entries before and after) | PASS: unchanged | PASS: paper and portal copy 1 queued | n/a | PASS (document_reissued) | 10088 (fixed: every reprint reason except Customer name was refused) |
| S9 | Single-family, Farid Fontaine, BL-2610-000057, unpaid. Wrong reading E-5005 4,285 → 4,085 on a bill that crosses the 15 and 20 Sep price changes. | $284.07 → $256.94 (−$27.13) = BL-2610-000118 | PASS: per-part lines of 560, 200 and 440 kWh add up to 1,200, each part on its own version; base charge $12 once | PASS | PASS: total due $256.94 | PASS | PASS (4,085, reason names the bill) | PASS | — |
| S10 | No final bill exists. Dev Duval, BL-2610-000055. Period corrected from 09-01..09-30 to 09-11..09-30. A 09-01..09-20 end was refused by BR-BIL-015 (no reading in the shorter period), which is correct. | $501.33 → $535.00 (+$33.67) = BL-2610-000119 | PASS: base prorated 20/30 (electric $12 → $8.00, water $8 → $5.33); new period 09-11..09-30 | PASS | PASS | PASS | n/a | PASS | Question: the whole reading's usage is billed in the 20 days |
| S11 | Commercial, August BL-2609-000048 (August is closed), paid. Wrong tax: TX State 6.25% → 6.0%. | $1,388.09 → $1,384.89 (−$3.20) = BL-2609-000120 | PASS | PASS: Check showed "Posts in Oct 2026" and "Books closed through Sep 2026" before approval; both entries dated 2026-10-01 | PASS: $3.20 to credit | PASS | n/a | PASS | — |
| S12 | Single-family, Rosa Rasmussen, BL-2610-000068, unpaid. Wrong deposit $0 → $150. | $96.90 → $249.20 (+$152.30 = $150 deposit + $2.30 electric re-price) = BL-2610-000121 | PASS: deposit line, not taxed (tax on $97.25 only) | PASS: CR 2300 Customer deposit liability $150.00, never revenue; For finance shows the row | PASS | PASS | n/a | PASS | — |
| S13 | Closed account, Rosa Pemberton, BL-2610-000092, unpaid. Missed charge MOVE-OUT × 1 ($20). | $110.67 → $133.42 = BL-2610-000122 | PASS | PASS | PASS: $133.42 stays outstanding on the closed account; no write-off | PASS | n/a | PASS | 10089 (fixed: refused as "terminal and not billed", including on the parts of a split bill) |
| S14 | A draft bill (AC-2026-00012, AC-2026-00054), and a bill already in an open case (Hugo Hollis's September bill). | — | PASS: both refused at Bills with the reason ("Sep 2026 is a draft. Fix it in its bill run." and "Sep 2026 is already in an open case."); nothing saved | — | — | — | — | — | — |
| S15 | Bulk. The tenant's September cycle run (49 bills), the whole run. Wrong tax: Local 2% → 1.5%. | 38 bills: 37 up +$183.85, 1 down −$5.59, net +$178.26 = issued | PASS: 38 credit notes and 38 new bills, every new total equals the preview | PASS: 76 balanced entries dated 10-02 | PASS: $7,079.04 moved to the new bills | PASS: 38 paper rows | n/a | PASS: sent, approved, 38 executed | 10090 (fixed: the run picker listed 25 runs for 2) and 10091 (open: preview, Send and approve each took about 3 minutes). Question: the tax fell, but 37 bills rose because electric was re-priced on the September versions. |
| S16 | Bulk. The August run (50 bills), Water only. Missed charge INSPECT × 1 ($30). | 43 bills × +$30.00 = +$1,290.00 = issued; 1 bill left out (it cannot be priced) | PASS: 43 credit notes and 43 new bills equal the preview | PASS: 86 entries dated 2026-10-01 | PASS: $13,759.93 moved | PASS: 43 paper rows | n/a | PASS | 10096 (fixed: one bill with no usable water reading had refused the whole case) |
| S17 | **Not walked at 100 bills.** No 100-bill run exists. Seeding 100 accounts with premises, meters, readings and a billing run through the product's own screens was beyond the time available. The largest runs are August (50 bills) and September (49), and they were used for S15 and S16. The part S17 checks — one bill fails, the others stand with no rollback, and Try again touches only the failure — was walked live: S3 (one bill failed at issue, Try again, then closed) and S18 (1 of 46 failed; Try again finished only that one; the 45 done bills were untouched). | — | — | — | — | — | — | — | 10082 (fixed: the screen had no failed or resume state) |
| S18 | Bulk, a price mistake. First, Plans & Rates: water tier 2 corrected over its own window (Aug 1 – Sep 30), from $6.50 to a final $5.50. This was done through the rate-schedule correction route by API, not the screen. Bills step, Aug 1 – Sep 30, Rate: **92 bills on 48 accounts found, across both runs and their replacement bills.** The September bills previewed wrongly because of the readings 10098 had written, so the issue was walked on Aug 1 – Aug 31 only. | 46 bills: 42 down −$330.25, 4 unchanged = issued; 2 left out (cannot be priced) | PASS: 46 credit notes and 46 new bills equal the preview; tier 2 at $5.50 on 42 bills | PASS: 92 entries dated 10-01 | PASS: $14,121.73 moved | PASS | n/a | PASS | 10101, 10102, 10103 (fixed). The 4 unchanged bills were credited and reissued before 10103 was fixed. No period crossed the price change, because the correction covers the whole window; per-part pricing was walked in S9 and S10. |
| S19 | Clara Castillo, August replacement bill BL-2609-000163. A tax row was sent; then water tier 2 was corrected in Plans & Rates; then Approve and issue. | Sent at $399.46; the bill would now be $396.92 | PASS: approval refused with "Figures changed. Check again."; nothing written; the case was then sent back | — | — | — | — | PASS (abandoned) | 10099 (fixed: before the fix the case was approved and the bill failed instead), 10097 and 10098 (found on the first attempt), 10100 (the closed case read "Done") |
| S20 | Farid Fontaine. The clerk went as far as Check and then left. | — | PASS: no case, no row in any money table; the bill was still pickable afterwards | — | — | — | — | Before 10078, two "attempt refused" audit rows were written each time Fix opened; now none | 10078 (fixed) |

## Defects

Each defect below was filed before it was fixed. Each fix was proved RED first, then GREEN. The money fixes were also run on PostgreSQL 16, and the golden suite is unchanged.

| Id | What | Status | Commit |
|---|---|---|---|
| DEF-BIL-10077 | A corrected bill printed the replaced bill's amount again in Total due | fixed | 9f0bc3a3b |
| DEF-BIL-10078 | Fix posted two refused previews on every visit, and each wrote an audit row | fixed | 415fbf484 |
| DEF-BIL-10079 | "This gives the customer money back." beside "Refund: No" | fixed | 9520a978f |
| DEF-BIL-10080 | A corrected reading's reason showed the case's database id on Meter Reads | fixed | 9f0bc3a3b |
| DEF-BIL-10081 | A missed charge failed at issue (a quantity with no unit) | fixed | 98b4bdec9 |
| DEF-BIL-10082 | A failed bill read "Waiting for approval", with no way to retry it | fixed | 98b4bdec9 |
| DEF-BIL-10083 | A charge code with no GL account was previewed and approved, then failed | fixed | 98b4bdec9 |
| DEF-BIL-10084 | For finance left out new lines, so the accounts did not add up to the net | fixed | 6daaf09a1 |
| DEF-PAY-10086 | A goodwill credit sent "payment received" receipts | fixed | b077c5408 |
| DEF-BIL-10085 | For finance had no goodwill entry; Done showed $0 | fixed | a2737c22c |
| DEF-BIL-10087 | Carried credit was promised to every bill of one account | fixed | 29ac7800b |
| DEF-BIL-10088 | Reprint rows were refused (the reason was sent instead of the field) | fixed | cf9445072 |
| DEF-BIL-10089 | A closed account's bill could not be corrected | fixed | b4b3e2e6b, 1dd2e50f2 |
| DEF-BIL-10090 | The run picker listed every rebill run and every empty run | fixed | b2b788687 |
| DEF-BIL-10091 | Bulk preview, Send and approve take about 3 minutes each, past the 60-second web timeout | **open** | — |
| DEF-BIL-10096 | One bill that cannot be priced refused a whole bulk case | fixed | 42085433f |
| DEF-BIL-10097 | The failed-bill panel showed a database id; Done after a retry read "0 bills" | fixed | 32927a6b7 |
| DEF-BIL-10098 | A bill split at a price change saved false "billed" estimate readings | fixed (45 rows already written are not repaired) | 55e7140f7 |
| DEF-BIL-10099 | Figures that moved after Send did not refuse the approval | fixed | 31c45047c |
| DEF-BIL-10100 | A case closed without correcting read "Done" with a net change | fixed | d79232efd |
| DEF-BIL-10101 | A Wrong rate row offered corrected-away schedule versions | fixed | c0ef5dff9 |
| DEF-BIL-10102 | A one-time (cycle-less) bill could not be corrected | fixed | 5bb53deb8 |
| DEF-BIL-10103 | A bulk case reissued bills whose figures did not change | fixed | 5bb53deb8 |

## Left open

- **DEF-BIL-10091: bulk is too slow for a web request.** On 38 bills, the preview, Send and approve each took about 3 minutes. A production worker is killed at 60 seconds. The bulk scope needs to be priced once in a job, and that is design work rather than a minimal fix.
- **The readings DEF-BIL-10098 wrote are still in the data.** There are 45 false "billed" estimate readings, for example E-5002 746.667 kWh on 30 Sep. They will distort the next correction of those September replacement bills, and the October true-up. Removing or voiding a billed reading is Meter Reads' act.
- **Three bills were issued with wrong figures before their fixes.** BL-2610-000109 prints Total due $382.50 (DEF-BIL-10077). Four S18 bills were reissued with no change (DEF-BIL-10103). The S5 goodwill queued receipts (DEF-PAY-10086). All of these are issued or queued records and are not edited.

## Questions for the Product Owner (not decided here; no money rule was guessed)

1. **Unchanged lines move when a bill is re-priced.** When one row is corrected (a water reading, a tax), the other lines on the bill are re-priced on the versions in force now. Should they be? On this tenant, schedule versions were added after the bills were issued. In S15, a tax cut of 0.5% raised 37 of 38 bills.
2. **Some corrected bills are due in the past.** A corrected bill for a closed month is due on the original run's bill date plus its due days. For example, the August corrections are due 09/22/2026. Is a due date in the past intended? The code comment in `corrections.py` warns against inheriting the original due date.
3. **A plan can silently price a service at $0.** A wrong-plan row can pick a plan that does not price one of the account's metered services, so that service is billed at $0.00 with no refusal (S5 Small Commercial, S7 Industrial water). Should the screen refuse it?
4. **Usage is not trimmed with the period.** When the period is shortened and no reading exists at the new start, the whole reading's usage is billed in the shorter period (S10). Is that intended?
5. **The journey expects a refusal for S19 in bulk too.** For one-customer cases the approval is now refused (DEF-BIL-10099). In bulk, a bill whose figures moved still fails at issue, after approval. The reason is that re-pricing a whole run a second time is DEF-BIL-10091's cost.

## Pre-existing reds seen, not caused by this walk

These were each run on HEAD without this walk's change, and they were red there too:

- `test_cr059_cs35_cs38_credit_rows.py::test_cs35__branch_2…`
- `test_us_cwp_005_receipt.py::…never_echoed`
- `test_def2859_estimate_basis.py` (3 cases)
