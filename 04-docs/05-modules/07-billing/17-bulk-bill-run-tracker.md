# Bulk bill run — agreed change → task → proof tracker

Status: **LIVE TRACKER**, started 2026-09-30 after the PO asked *"how you will ensure they are
implemented"*. One row per row of `14-bulk-bill-run-changes.md`. Checked by
`10-scripts/bulk_run_trace.py` — run it; do not trust a count written here.

**How a row moves.** `To build` → `In progress` (a lane has it) → `Merged` (on the branch, AND a
test that proves it names the row) → `Walked` (the PO has seen it in a browser, on a named build).
A test proves a row by carrying the marker `BULK-CHG-<n>` (e.g. `BULK-CHG-51`) in its name,
docstring or a comment, and the file goes in *Proved by*. **A row cannot be `Merged` or `Walked`
without a tagged test**, and the close-out (plan C1–C4) cannot finish until every row is `Walked`
(`bulk_run_trace.py --close`).

**Where a new agreement goes.** A new PO point about the bulk run is (1) a new row in the changes
list, (2) a task in the build plan, (3) a row here — in the SAME commit as the decision-log row.
The script fails if any of the three is missing.

| # | Area | Tasks | State | Proved by |
|---|---|---|---|---|
| 1 | Pricing (shared) | pre-plan | Merged | `06-backend/tests/test_br_bil_300_services_rulings_2026_09_30.py`; `06-backend/tests/test_otb_t2_money_paths_pg.py` |
| 2 | Pricing | pre-plan | Merged | `06-backend/tests/test_br_bil_300_services_rulings_2026_09_30.py` |
| 3 | Pricing | pre-plan | Merged | `06-backend/tests/test_b4_missing_base_bills_zero_with_warning.py`; `06-backend/tests/test_otb_t2_money_paths_pg.py` |
| 4 | Pricing | pre-plan | Merged | `06-backend/tests/test_br_bil_300_services_rulings_2026_09_30.py`; `06-backend/tests/test_otb_t2_money_paths_pg.py` |
| 5 | Pricing | pre-plan | Merged | `06-backend/tests/test_br_bil_300_services_rulings_2026_09_30.py`; `06-backend/tests/test_otb_t2_money_paths_pg.py` |
| 6 | Pricing | pre-plan | Merged | `06-backend/tests/test_br_bil_300_services_rulings_2026_09_30.py`; `06-backend/tests/test_otb_t2_money_paths_pg.py` |
| 7 | Pricing | pre-plan | Merged | `06-backend/tests/test_b4_missing_base_bills_zero_with_warning.py` |
| 8 | Send | pre-plan | Merged | `06-backend/tests/test_b11_issue_hardening.py` |
| 9 | Screen | F2 | Merged | `07-frontend/src/features/billing/bulkRun/BulkRunDoor.dom.test.tsx` |
| 10 | Scope | F3 | Merged | `07-frontend/src/features/billing/bulkRun/ScopeStep.dom.test.tsx` |
| 11 | Scope | R2, R4, B3, F3 | Merged | `07-frontend/src/features/billing/bulkRun/ScopeStep.dom.test.tsx` |
| 12 | Scope | B4, F3 | Merged | `07-frontend/src/features/billing/bulkRun/ScopeStep.dom.test.tsx` |
| 13 | Scope | R2, F3 | Merged | `07-frontend/src/features/billing/bulkRun/ScopeStep.dom.test.tsx` |
| 14 | Scope | B4, F3 | Merged | `07-frontend/src/features/billing/bulkRun/ScopeStep.dom.test.tsx` |
| 15 | Scope | B5, F5 | Merged | `06-backend/tests/test_bulk_run_scope.py` |
| 16 | Scope | B1 | Merged | `06-backend/tests/test_bulk_run_scope.py` |
| 17 | Scope | R2, R5, B2 | Merged | `06-backend/tests/test_bulk_run_scope.py` |
| 18 | Scope | R2 | Merged | `06-backend/tests/test_bulk_run_scope.py` |
| 19 | Scope | B1 | Merged | `06-backend/tests/test_bulk_run_scope.py` |
| 20 | Check | B13, F9 | Merged | `06-backend/tests/test_bbr_check_store.py`; `06-backend/tests/test_us_bil_037_clerk_checks.py`; `07-frontend/src/features/billing/bulkRun/BulkRunPage.dom.test.tsx` |
| 21 | Check | R4, B7 | Merged | `06-backend/tests/test_bbr_check_engine.py` |
| 22 | Check | B8 | Merged | `06-backend/tests/test_bbr_check_engine.py`; `06-backend/tests/test_bbr_check_categories.py` |
| 23 | Check | B7 | Merged | `06-backend/tests/test_bbr_check_engine.py` |
| 24 | Check | B21, F7 | Merged | `06-backend/tests/test_bbr_check_engine.py`; `06-backend/tests/test_us_bil_037_clerk_checks.py` |
| 25 | Check | B9, F7 | Merged | `06-backend/tests/test_bbr_check_store.py`; `06-backend/tests/test_us_bil_037_clerk_checks.py`; `07-frontend/src/features/billing/bulkRun/BulkRunPage.dom.test.tsx` |
| 26 | Check | R4, B7 | Merged | `06-backend/tests/test_bbr_check_pg.py` |
| 27 | Tests | T1, T2, T3, T4, T5, T6, T7, T8 | Merged | `06-backend/tests/test_bulk_run_scope.py`; `06-backend/tests/test_bbr_check_pg.py`; `07-frontend/src/features/billing/bulkRun/ScopeStep.dom.test.tsx`; `07-frontend/src/features/billing/bulkRun/BulkRunDoor.dom.test.tsx`; `07-frontend/src/features/billing/bulkRun/BulkRunLinks.dom.test.tsx`; `06-backend/tests/test_bbr_fixed_charge_next_bill.py` |
| 28 | Records | R1 | To build | — |
| 29 | Pricing | R2, R4, B16 | Merged | `06-backend/tests/test_bbr_check_engine.py` |
| 30 | Scope | B5, F5 | Merged | `06-backend/tests/test_bulk_run_scope.py` |
| 31 | Scope | B6, F5 | In progress | — |
| 32 | Scope | B6, F5 | Merged | `06-backend/tests/test_bulk_run_scope.py`; `07-frontend/src/features/billing/bulkRun/BulkRunLinks.dom.test.tsx` |
| 33 | Scope | F5 | In progress | — |
| 34 | Scope | F6 | In progress | — |
| 35 | Scope | R5, B1, F4 | Merged | `07-frontend/src/features/billing/bulkRun/BulkRunPage.dom.test.tsx` |
| 36 | Check | R1, B10, B11, B14, B15, F8, F9, F10, F11 | Merged | `06-backend/tests/test_bbr_check_engine.py`; `06-backend/tests/test_bbr_check_store.py`; `06-backend/tests/test_bbr_inline_fixes.py`; `06-backend/tests/test_bbr_check_categories.py`; `07-frontend/src/features/billing/bulkRun/BulkRunPage.dom.test.tsx` |
| 37 | Sign off | B19, F14 | Merged | `06-backend/tests/test_bbr_sign_off_summary.py`; `06-backend/tests/test_bbr_accuracy_defects.py`; `07-frontend/src/features/billing/bulkRun/BulkRunPage.dom.test.tsx` |
| 38 | Check | R2, B12 | Merged | `06-backend/tests/test_bbr_check_categories.py`; `06-backend/tests/test_bbr_fixed_charge_next_bill.py`; `06-backend/tests/test_bbr_payment_checks.py` |
| 39 | Check → Sign off | B17, F13 | Merged | `07-frontend/src/features/billing/bulkRun/BulkRunPage.dom.test.tsx` |
| 40 | Sign off → Send | R2, B20, F14, F15 | Merged | `06-backend/tests/test_bbr_not_in_run.py`; `06-backend/tests/test_bbr_accuracy_defects.py`; `07-frontend/src/features/billing/bulkRun/BulkRunPage.dom.test.tsx`; `06-backend/tests/test_us_bil_037_clerk_checks.py`; `06-backend/tests/test_bbr_f4_two_sends_pg.py` |
| 41 | Check | B18, F8, F12 | Merged | `06-backend/tests/test_bbr_not_in_run.py`; `07-frontend/src/features/billing/bulkRun/BulkRunPage.dom.test.tsx` |
| 42 | All steps | F19 | Merged | `06-backend/tests/test_bbr_sign_off_summary.py`; `06-backend/tests/test_bbr_not_in_run.py`; `07-frontend/src/features/billing/bulkRun/BulkRunPage.dom.test.tsx`; `07-frontend/src/features/billing/bulkRun/BulkRunLinks.dom.test.tsx` |
| 43 | Scope | B26 | Merged | `06-backend/tests/test_bulk_run_scope.py` |
| 44 | Check | B26 | Merged | `06-backend/tests/test_bbr_check_store.py`; `06-backend/tests/test_bbr_check_engine.py`; `06-backend/tests/test_def_bil_8244_meter_swapped_both_parts.py`; `06-backend/tests/test_po_20261001_no_plan_no_default.py`; `06-backend/tests/test_bbr_never_read_multiplier.py` |
| 45 | Check | B26 | Merged | `06-backend/tests/test_bbr_check_store.py`; `06-backend/tests/test_def_bil_8244_meter_swapped_both_parts.py` |
| 46 | Check | B26 | Merged | `06-backend/tests/test_bbr_check_store.py`; `06-backend/tests/test_bbr_check_engine.py`; `06-backend/tests/test_def_bil_8244_meter_swapped_both_parts.py` |
| 47 | Next bill | B22, T8 | Merged | `06-backend/tests/test_def_bil_8280_clerk_estimate_billed_once.py` |
| 48 | Next bill | B23, T8 | Merged | `06-backend/tests/test_bbr_fixed_charge_next_bill.py` |
| 49 | Next bill | B23, T8 | Merged | `06-backend/tests/test_bbr_fixed_charge_next_bill.py` |
| 50 | Next bill | B23, T8 | Merged | `06-backend/tests/test_bbr_fixed_charge_next_bill.py`; `06-backend/tests/test_bbr_not_in_run.py` |
| 51 | Next bill | B23, T8 | Merged | `06-backend/tests/test_bbr_fixed_charge_next_bill.py`; `06-backend/tests/test_bbr_walk_defects.py` |
| 52 | Next bill | B23, T8 | Merged | `06-backend/tests/test_bbr_fixed_charge_next_bill.py`; `06-backend/tests/test_bbr_plan_extended_notice.py` |
| 53 | Check | B24 | Merged | `06-backend/tests/test_bbr_check_store.py`; `06-backend/tests/test_bbr_check_categories.py`; `06-backend/tests/test_def_bil_8245_recheck_on_new_price_version.py` |
| 54 | Check | B25 | Merged | `06-backend/tests/test_bbr_check_record_locked.py`; `07-frontend/src/features/billing/bulkRun/BulkRunPage.dom.test.tsx` |
| 55 | Check | B27, B28 | Merged | `06-backend/tests/test_b27_batch_reads.py`; `06-backend/tests/test_b28_parallel_check_batches.py` |
| 56 | All steps | E12, E13, E14, E15, E16, E17 | Merged | `07-frontend/e2e/J72-bulk-bill-run.spec.ts`; `07-frontend/e2e/J73-bulk-run-breakdown-and-scale.spec.ts`; `07-frontend/e2e/J72-bulk-bill-run-accuracy.spec.ts`; `07-frontend/e2e/J72-bulk-bill-run-single-account-trace.spec.ts` |
| 57 | Check | B29 | Merged | `06-backend/tests/test_po_20261001_no_plan_no_default.py` |
| 58 | Send / the bill | B29 | Merged | `06-backend/tests/test_po_20261001_overpaid_bill_reads_whole_account.py` |
| 59 | Calculate | B29 | Merged | `06-backend/tests/test_def_bil_8566_cart_prorates_like_the_base.py` |
| 60 | Calculate | B29 | Merged | `06-backend/tests/test_po_20261001_meter_swap_priced_per_meter.py`; `06-backend/tests/test_def_bil_8244_meter_swapped_both_parts.py` |
| 61 | Send / the bill | B29 | Merged | `06-backend/tests/test_po_20261001_overpaid_bill_reads_whole_account.py` |
