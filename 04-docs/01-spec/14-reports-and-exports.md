# A14 — Reports, Dashboards & Exports

> Part A (extraction). Source: SMARTBillHub prototype «../../05-prototype/UtilityBilling.html». Reports, widgets, exports with columns/filters/ranges/aggregations. Drives index design.
> Cardinal rule: anything not determinable from the UI is «UNKNOWN — <question>», never invented.


## Report library (S44)
**Financial:** AR aging summary · Days sales outstanding · Revenue by service & rate · Payments by method · Sales tax remittance · Trial balance.
**Operations:** Read completeness · High-usage exceptions · Disconnect & reconnect · Billing register · New & closed accounts · Meter inventory.
**Compliance:** PUC quarterly filing · User activity audit · Rate change history.

## Viewer parameter bar (S46)
Date range (This month / Last month / This quarter / Year to date / Custom), Service (All/Electric/Water/Sewer), Account class (All/Residential/Commercial/Industrial), Group by (Age bucket/Service/Cycle/Account class), Run report. Actions: Favorite, Schedule, Export, Print.

## Fully-built report tables
| Report | Columns | Aggregate | KPIs |
|---|---|---|---|
| AR aging summary | Account, Customer, Class, Current, 31–60, 61–90, 90+, Total | sum per bucket + totals | Total AR, Current, 31–60, 61–90, 90+ |
| Revenue by service & rate | Service, Rate schedule, Accounts, Usage rev, Base, Tax, Total | sum per schedule + totals | Total revenue, Usage, Base&fees, Tax |
| Billing register | Bill #, Account, Customer, Services, Usage, Amount, Flag | count + sum | Bills in cycle, Avg bill, Estimated, Exceptions |

Others use a **generic viewer** (Date, Reference, Detail, Category, Amount) → real columns UNKNOWN per report.

## Scheduled (S45)
Report, Frequency ("Every Monday · 6am", "1st of month", "Monthly · 18th"), Delivery (Email · PDF/Excel/CSV), Recipients, Next run, Action (Run now/Edit/Pause/Delete). Recent runs: Report, Run at, Range, By, Rows, Format, Download.

## Builder (S47)
Dataset (Bills/Payments/Accounts/Meter reads/Adjustments & credits/Premises & units) → Columns (Account, Customer, Amount, Service, Cycle, Status, Date) → Filter (No filter / Amount > threshold / Status is past-due / Service is…) → Group by (None/Service/Cycle/Account class/Month) → Date range → Sort (Amount high→low / Date newest / Account) → Run / Save & schedule.

## Dashboard widgets (S7)
Cash today, method mix, outstanding/collections (accounts owed, DSO, write-offs YTD), billing status, exceptions to action, recent activity. Formulas UNKNOWN (A7).

## Accounting exports (S42)
- QuickBooks Online: one **summary journal entry per month** (6 in sample); balanced.
- CSV (generic), IIF (QuickBooks Desktop), Xero journal CSV.
- GL summary columns: GL account, What it is, Debit, Credit; balanced totals.
- "Download period pack".

## Other exports/imports
Lockbox import (Chase BAI2 / BofA CSV) auto-match preview; bank statement import (CSV/OFX/QBO/QFX) or Plaid; deposit slip; tax remittance (PDF+CSV) per authority; statement PDF; bill PDF/print.

## Indexing implication
AR aging (tenant, balance, age); Revenue by service (tenant, service, period); Billing register (tenant, cycle); Payments by method (tenant, method, period); Read completeness (tenant, cycle, status). See B2 §4.



## Addendum — Account ledger + GL (2026-08-07 r2)
- **Account ledger report:** params Account, **Premises (location)**, From, To → columns Date, Type (Bill/Payment/Adjustment/Refund), Reference, Description, Charge, Payment, Running balance; period totals footer; PDF + CSV export.
- **General ledger (Finance tab):** trial balance columns GL account, Name, Type, Debit, Credit; balanced totals; filterable by period + **premises**; exportable. Account-mapping table (source → GL account) shown read-only (edit in Settings → Accounting).
- **By-premises reporting:** single legal entity; premises/units are the locations. Finance reports and the account ledger can be filtered/grouped and downloaded **by premises** (replaces the earlier multi-entity ask).


## Addendum — By-premises summary report (2026-08-07 r3)
Dedicated report (separate from Account ledger). Params: Period, Service, Group by (Premises | Premises → Unit). Columns: Premises (location), Units, Services, Billed, Collected, Owed, Collection %. KPI strip (premises count, billed, collected, owed) + all-premises totals footer. PDF/CSV export. This is the by-premises reporting deliverable (single legal entity; premises = locations).

## Addendum 2026-08-08 — reports audit vs ratified law (28-finding sweep; corrections, not new decisions)
1. **Date basis on EVERY money number** (BR-REP-001/BR-PAY-021): billing-side (billed, revenue, AR, aging, on-time, collection %) = POSTING date; cash/bank-side (cash today, method mix, deposits, bank rec, remittance-collected) = CLEARING date; every widget/report header labels its basis. Supersedes all unstated-basis definitions above.
2. **Sales-tax remittance = DUAL BASIS** (BR-LED-002/013): 4 columns per authority — billed · collected · remitted · outstanding — with the per-authority remitting-basis indicator. Supersedes the collected-only definition.
3. **S36 adds** the subledger tie-out panel (deposit liability / AR / tax payable vs registers; drift = red flag + release blocker) and the full KPI strip (BR-LED-007/016).
4. **S42 export respec** (BR-LED-004/014): recorded IDEMPOTENT export batches (what/when/where/who/hash; re-run blocked), export codes from the **Finance** account-mapping page (not "Settings → Accounting"), drill-back from every figure, dimension-level CSV extracts.
5. **New canned reports** (all read-models over ratified data): Back-bills & penalty bills (compliance — BR-BIL-018/019) · Bill corrections (compliance — reason/scope/approver/deltas, BR-BIL-014) · Write-offs (finance — initiator/approver/GL/aging, BR-PAY-020/BR-LED-008) · Budget billing status (level/actuals/variance/drift/settle-up, BR-BIL-017) · Delivery-queue health (queued/sent/failed/bounced + re-queue, BR-BIL-016/BR-NOT-005) · Returned mail & bad addresses (BR-PAY-018).
6. **Billing register + S30** gain `bill_type` column + filter (cycle|first|final|rebill|backbill|penalty). **Payments reports** gain `purpose` column + filter (BR-PAY-012). **Read reports** gain `channel` column; Read completeness is per plan-required channel set (B2 r8, BR-MET-049).
7. **Filters enumerate live vocabularies, never hardcoded**: services = tenant-enabled set (not Electric/Water/Sewer); consumer class adds **Government**; account filters use the 5 statuses + behavior classes (BR-CUS-055).
8. **Account ledger** Type column = the FULL source vocabulary (incl. deposit, write-off, opening, remittance, manual JE, transfer) so it foots to the AR tie-out (BR-LED-001); AR aging line: imported opening buckets age forward from the cutover as-of date (BR-CUS-048).
9. **Revenue by service & rate** = invoice-line read-model with source drill-back (rate schedule is NOT a journal dimension; BR-LED-001 stands). Trial balance: any GL line expands to its dimensions (BR-LED-009).
10. **Dashboard formulas**: billing status ← bill_runs states; exceptions ← S31.3 cases; write-offs YTD ← approved write_offs (clearing-irrelevant); pending-billing chip ← BR-BIL-015 queue; capture-intents shown as "autopay scheduled" and EXCLUDED from cash/collected KPIs (BR-PAY-015). DSO + collection % definitions = with the PO (RQ battery).
11. **Download standard = IS-11** (PO 2026-08-08): CSV always + PDF where specced; the line-25 "Excel" option is DROPPED for v1 (CSV only); scheduled-run files retained 3 days (tenant-config) — delivery is the email (W6), the download list is a courtesy window.
