# Walk — three fixes from the combined walk, 2026-10-14

`DEF-PAY-10157` (cash at a counter never cleared) · `DEF-REP-10158` (Owner summary
left out a balance moved to the owner) · `DEF-REP-10159` (Receivables by service named
the departed tenant). Decision log: *"A BALANCE MOVED TO THE OWNER CARRIES THE TENANT'S
BILL SHARES WITH IT …"* (2026-10-14).

**Set-up.** Private copy `smartbillhub_fixpay` (`createdb -T smartbillhub`, migrated to
the tip, dropped afterwards). Backend `runserver` on **8017** (local settings), the SPA
built with `vite build --mode walk` and served by `server.mjs` on **8097**. Tenant Brazos
Bend, staff Dana Whitfield (password set on the copy only). Script:
`10-scripts/walk_fixes_payments_reports_2026_10_14.mjs` (`COUNTER=`, `OWNER_ID=`,
`STEPS=counter,reports`). Ledger figures read back in a Django shell on the copy.

The copy is the base database, not the combined walk's copy, so the figures are this
copy's own: the balance to move is AC-2026-00044's **$25.45** (fees 19.80, taxes 5.08,
electric 0.40, water 0.17), moved to Mill Pond's owner account AC-2026-00053 through
`move_out_settlement.post_pending_balance_to_owner` — the same call the final bill's
issue makes — dated 2026-10-14. The full move-out wizard was not re-driven; it was walked
on 2026-10-14 in the combined walk, and this walk is about what the reports read after it.

## Reproduced first (before the fix, same copy)

| | Books (ledger) | What the screen read |
|---|---|---|
| Tenant AC-2026-00044 after the move | **$0.00** | Receivables by service: **$25.45** (fees, taxes, electric, water) |
| Owner AC-2026-00053 after the move | **$25.45** | Receivables by service: **$0.00**, not a row |
| Owner summary, Mill Pond, 10/01–10/31 | owes **$25.45** | Grand total **$0.00**, no line for the move |
| Record a payment, cash | — | *Clearing date* blank → `processing`, nothing posted (the combined walk's PY-261102-0087) |

## 1 · Cash at a counter clears on receipt (`DEF-PAY-10157`) — PASS

| Shot | What it shows |
|---|---|
| `1-01-counter-open.png` | Counter CTR-261014-DW open |
| `1-02-cheque-not-cleared.png` | Method **Check**: Clearing date stays blank; the Check box says *It meets no bill until cleared.* |
| `1-03-cash-clears-on-receipt.png` | Method **Cash**: Clearing date **10/14/2026** = Posting date; the Check box *$25.00 goes to this account. It meets the oldest bills first.*; *Goes into counter CTR-261014-DW* |
| `1-04-payment-recorded.png` | Recorded |

Read back from the books: `PY-261014-0086` (first run) and `PY-261014-0087` (the run the
shots are from), each **cleared** 10/14, $25.00 allocated, in the till; entries
JE-101426-0493 / -0494 **DR 1010 Undeposited funds / CR 1200 AR $25.00** (BR-PAY-039's
receipt leg). Ana's receivable **$187.92 → $162.92 → $137.92**.

## 2 · Owner summary shows the move and foots to the books (`DEF-REP-10158`) — PASS

| Shot | What it shows |
|---|---|
| `2-01-owner-summary-foots.png` | 10/01–10/31: column **Moved from tenants $25.45**, total **$25.45**; tiles Grand total **$25.45** · In the books **$25.45**; no difference sentence |
| `2-02-owner-summary-december-differs.png` | 12/01–12/31: nothing charged or moved, Grand total **$0.00**, In the books **$25.45** → *The total differs from the books.* |

## 3 · Receivables by service names the owner (`DEF-REP-10159`) — PASS

| Shot | What it shows |
|---|---|
| `3-01-receivables-over-90-by-service.png` | The library report as at 2027-03-31 — totals unchanged by the move (moved, not created) |
| `3-02-receivables-builder-owner-rows.png` | The builder's Receivables subject, saved and opened as at 2027-03-31: **AC-2026-00053 Mill Pond Apartments LP** owes Fees $19.80 · Taxes $5.08 · Water $0.17 · Electric $0.40 — the tenant's own shares |

The tenant's absence was read from the read model on the copy (`receivables_dataset`,
whole set): AC-2026-00044 **$0.00, no row**; AC-2026-00053 **$25.45**; population
unchanged. (The screen's check that the tenant is on no row looked at the first 50 rows
sorted by account descending, which may not reach AC-2026-00044 — the read-model figure
is the evidence for that half.)

**Not fixed and filed:** the AR ageing (SQL) still names the tenant — `DEF-REP-10160`.

Every server and the copy were stopped and dropped at the end.
