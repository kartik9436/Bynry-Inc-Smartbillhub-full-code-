# CR-184-BRC10 — Receivables by service: what is still owed, aged, per service

**Raised:** 2026-10-14 by the Product Owner, while building a custom report.
**Status:** **ACTIVE — BUILD STARTED** (lane ARSVC, 2026-10-14).
**Branch:** `claude/serene-noether-71ie5b` (`BRC10` lineage). `allocate.py cr` answered **184** against the remote and `--verify 184` reported it free on every branch.
**Classification (`13-change-process.md` §1):** a **CHANGE** — no user can see receivables split by service today. One part of it is a **DEFECT** in a live screen (the ageing's Service filter, §4 R5) and is recorded here because the ruling that fixes it is the same ruling.

## 0 · What arrived, in the requester's words

The PO set out to build *"receivables over 90 days by service"* in the custom report builder and found **no Receivables dataset** to build it on — the nine datasets are invoices, payments, journal lines, meter reads, assets, accounts, rate schedules, audit log and work orders, and none of them holds what is still owed.

The rule was put to them as a choice (decision log 2026-10-14, *"RECEIVABLES BY SERVICE: WHAT IS STILL OWED IS SHARED IN PROPORTION — INSIDE THE ALLOCATION ORDER ALREADY SET (C1 → a)"*). PO verbatim: *"C1 … Option (a) In proportion: the payment is shared by each service's part of the bill. Water owes $40, Sewer owes $20, total $60 ✔ do this now"*.

## 1 · The rule (quoted from the decision log, not summarised)

> **So (a) is applied INSIDE that order, not instead of it (our judgment, law 13):** the class order says how much of each class is still owed; what is owed in a class is then shared across services in proportion to each service's part of that class on the bill. Worked: water 80.00 + sewer 40.00 (usage + base 120.00) + tax 8.00 + late fee 5.00 = 133.00; paid 60.00 → usage + base receives 60.00, leaving 60.00 owed = **water 40.00 + sewer 20.00**; tax 8.00 and fee 5.00 untouched. A tax or fee line that names its service follows it; one that names none is reported on its own row, never guessed onto a service. The rows foot to the ledger receivable or the report says so.

## 2 · What signed statement this reverses

`apps/billing/selectors.invoice_ids_for_service` says, of the ageing's Service filter: *"A BILL IS NOT SPLIT BY SERVICE AND THIS FILTER DOES NOT PRETEND IT IS … the alternative — pro-rating a receivable across the services on it — is a money rule nobody has ruled."* **It is ruled now** (above), so that docstring is amended in the same change. No ❄️ B4/B5 figure is touched: allocation itself (`apps/payments/allocation.py`, GT-7) does not move — this change READS allocations, it writes none.

## 3 · Requirements

| # | What | Where |
|---|---|---|
| R1 | Age what is owed per bill **line** by service: each class's remaining balance (from the allocation record, walked in the tenant's own `allocation_class_order` for money that carries no class breakdown) shared across that class's lines by service in proportion to their amounts. Decimal; rounding remainder placed deterministically so the rows sum **exactly** to the bill's owed amount. | `apps/payments/receivables_by_service.py` (new) |
| R2 | A **Receivables** dataset in the custom report builder — one row per account × service, Current / 1–30 / 31–60 / 61–90 / 90+ / Total, as-of date, server-paginated (`NFR-3`). | `apps/reports/datasets.py` · `queries.py` |
| R3 | A library report **Receivables over 90 days by service** — one row per service: debtors, amount over 90 days, share of the total; as-of date; export through the existing exports mechanism. | `apps/reports/receivables_by_service.py` (new) · `reports/0011` |
| R4 | **Foot check** — the service rows' total against the ledger's AR control total at the as-of date; a difference is stated, never adjusted away. | both of the above |
| R5 | The Finance ageing's **Service filter** uses each bill's service share instead of counting whole bills (it overstated mixed bills). | `apps/payments/billing_seam.aging_positions_page` |

## 4 · Impact (ten surfaces)

Rules: the ruling above becomes the module rule; `invoice_ids_for_service`'s docstring amended. Money: read-only; no posting, no allocation, no rounding event in a stored figure (shares are computed per report run). Data: none written. Screens: the custom builder gains a subject; the library gains a card under Financial; Finance → Who owes you's Service filter shows smaller, correct figures on mixed bills. Open questions: **`OQ-128`** (which class a `minimum`/`adjustment` line belongs to) is still OPEN and is NOT decided here — a part-paid bill carrying such a line is shared by plain proportion over the whole bill and the report COUNTS those bills (§5). Demo fixture: none. Lanes building now: none in these files at the tip read.

## 5 · Judgments where the rules ran out (written before building, step W)

1. **Money paid with no class breakdown** (every allocation before `payments/0015`, credit applications, releases) is walked through the tenant's CURRENT `allocation_class_order` — the order the ruling says to stay inside. A tenant who changed its order since a payment was made sees that payment re-walked under the new order; the stored breakdown, where one exists, always wins.
2. **A bill whose lines do not add up to what it asks** (budget billing, BR-BIL-072 *"Level is due"*) has its class remainders scaled in proportion to what it asks, so the service rows still sum to the bill's owed amount exactly.
3. **A line kind no class places** (`minimum`, `adjustment`, `discount`, `deposit` — `OQ-128`): on an UNPAID bill every line is owed in full and no class is needed; on a PART-PAID bill the class walk cannot run, so the whole bill is shared by proportion over its lines and the report counts the bills shared that way.
4. **Rounding**: each share is cut to 4 decimal places (rounded down); the units left over go one at a time to the shares with the largest cut-off fraction, ties broken by row order (services by code, then the class rows). 100.00 over three equal lines → 33.3334 + 33.3333 + 33.3333.
5. **A line with no service and no class row of its own** is reported under its class (*Taxes*, *Fees*, *Other charges*); a bill with no lines at all is reported under *Other charges*.

## 6 · Version · rollback

Not versioned by this lane (the coordinator bumps). Rollback: reverse `reports/0011` (the card goes), drop the dataset from `DATASETS`, and revert the `aging_positions_page` service branch — nothing was written to any table, so there is no data to undo.
