# Rollback — the one-time bill fixes and the bulk run check engine (2.412.x)

⚠ **SUPERSEDED 2026-10-01 for any rollback from `2.413.0` or later by `15-bulk-bill-run-build-plan.md` § C4.** Its `migrate billing 0031` step drops the Check tables, and sent runs now hold check records the PO ruled are kept as long as the bills. Read C4 before rolling anything back.

Status: **DRAFT, written 2026-09-30 before shipping** (one-time plan C4, bulk plan C4). Finalised when
the last lane of this release merges; every later database change must be added below or this note is
false.

**Roll back to:** the build the PO is running today, **2.411.4**.

## What rolling back undoes

| Change since 2.411.4 | Undone by redeploying 2.411.4? | Database step |
|---|---|---|
| Bill name and addresses (2.411.6) | Yes — bills issued after the rollback print as before | None |
| One-time bill fixes (2.411.7 → 2.412.1) | Yes | None |
| Bulk run check engine (2.412.0): saved check results | Yes | `billing` 0032–0034 must be reversed FIRST (below) |
| Leftover deposit refunded to customer credit, OQ-248 (2.412.2) | Yes for new closures — 2.411.4 refuses the final bill again | None. No migration, no new ledger account (customer credit `2400` is an existing designation) |
| Catch-up stretch nobody read: shared reading, else the meter's estimate, DEF-BIL-8324 (2.412.2) | Yes — 2.411.4 refuses such a catch-up again | None |
| Send card's five confirmations (2.412.2) | Yes — 2.411.4 shows the single tick again | None. Release rows already written keep the five as ticked |

## Database: three changes, all reversible

| Migration | What it adds | Reverse |
|---|---|---|
| `tenancy/0054_def_not_8450_twelve_message_kinds` (2.412.3) | Widens the list of accepted kept-document kinds from 38 to 48 | Reverse is REFUSED while any kept document uses one of the ten new kinds (proved on PostgreSQL). To roll back past it, those kept copies must be exported and removed first, or stay at 2.412.3 for this migration only — kept documents are records, so the safe default is to leave 0054 applied: 2.411.4 runs correctly with the wider list |
| `billing/0034_bbr_check_record_locked_at_send` | Trigger refusing edits to a sent run's check record | Drops the trigger (reverse SQL in the file) |
| `billing/0033_rls_bbr_check_store` | Tenant policies on the four check tables | Drops the policies (reverse SQL in the file) |
| `billing/0032_bbr_check_store` | Four tables: account checks, findings, standing answers, and the decision additions | Drops the tables |

Command, run on the 2.412.x code BEFORE redeploying 2.411.4:
`python manage.py migrate billing 0031`

## What is NOT undone, on purpose

- **Bills already sent stay sent.** Issued bills are never edited or deleted (hard rule 4).
- **Estimates saved into Meter Reads at Send stay.** They are real estimated readings; the next real
  reading trues up against them under either version.
- **A leftover deposit already posted to customer credit stays there** (2.412.2, OQ-248). The entry
  is immutable (hard rule 4) and it is money owed back to that customer: under 2.411.4 it still sits
  in customer credit until refunded. Nothing reverses it; a rollback only stops new ones.
- **Catch-up bills already issued keep their estimated lines** (2.412.2, DEF-BIL-8324). The
  catch-up preview writes nothing, so a rollback leaves no half-made estimate behind.
- **Check results are lost** when 0032 is reversed. They are working data: re-running the check on
  2.412.x rebuilds them. A sent run's check report is lost with them. Back up the four tables first if
  that report must be kept.

## Check after rolling back

1. The version on screen reads 2.411.4.
2. `python manage.py showmigrations billing` shows 0031 as the last applied.
3. Open one sent bill: it still shows and prints.
