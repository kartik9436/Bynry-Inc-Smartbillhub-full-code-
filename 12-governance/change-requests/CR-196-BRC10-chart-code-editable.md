# CR-196-BRC10 · A chart account's code may be changed by a System Admin, even when used

**Raised:** 2026-10-29 by the Product Owner, in chat.

**Requester's words, verbatim:** *"in many cases utilities are giving there own GL codes; which means we have to ability to change existing GL code as per the given utility for that specific tenant; even if they are used ; if user update them they should be applicable after the updation."*

**Ruling record:** decision log 2026-10-29, *"A chart account's CODE may be changed by a System Admin even when the account is used …"* — the eight approved behaviours, Q1–Q4 (all **A**) with their worked examples, the PO's words on the four risks, and our judgment (5a, 5b) with its worked case.

## 1 · Classification (step 1 of `13-change-process.md`)
A **change**: it reverses a signed story rule — US-LED-005 §1 *"its `code`/`type` are frozen once posted against"*, built as **BR-LED-040** (*"A CHART ACCOUNT'S NUMBER AND TYPE ARE NOT EDITABLE AT ALL"*). Not the fast path: it touches the 🔒 chart (which GL account money lands in is unchanged, but what a code means is), a migration, and stored data (a back-fill).

## 2 · What signed statement moves, and what stands
**Amended for CODE only:** US-LED-005 §1 / EP-LED-02 TC-4 and BR-LED-040. **Stands:** TYPE frozen (refused by name, as before); delete refused when referenced, deactivate available (IS-1); every chart change audits (BR-LED-015); the 2200 tax series cannot be hand-typed for a NEW account (BR-BIL-069 / BR-LED-023), and a code edit may not move a non-tax account INTO it. B4/B5 ❄️ untouched: no seeded code or figure moves — a tenant moves its own.

## 3 · Our judgments where the ruling ran out (law 13 — recorded, not re-asked)
1. **5a — `ledger_accounts.seed_key`** (nullable, internal, never on screen, never changed by a code edit): the code an account was seeded or minted under. `_create_missing_accounts` skips a seed row whose key is already held by any of the tenant's accounts (live or retired). Back-filled by `ledger/0021` for rows whose code is a seed code or a 2200-series code. Partial-unique per tenant.
2. **5b — `chart.is_tax_payable_account(code, seed_key)`**: the code-prefix test OR the key-prefix test. Used where an EXISTING account is recognised as tax: the remittance refusal (`journal.record_tax_remittance`), the tax report (`reporting` ×2), the month-end remittance check (`close`), and the GL map's tax section (`chart_api`). The three INPUT checks (`create_tax_authority_account`, `create_account`, `import_accounts`) stay on the typed code — they judge a code being typed, not an account.
3. **The 2200-nn allocator also reads `seed_key`**, so renaming `2200-01` away never lets the number be re-let (BR-LED-023).
4. **`finance_signed` / `seeded` on a chart row read `seed_key or code`**, so a renamed unsigned account never reads as signed (US-LED-017 TC-5).
5. **"Formerly" lives on the account** (`ledger_accounts.code_history`, append-only list of {old, new, by, at}) as well as in `audit_log`, because `audit_log` is pruned (OQ-1340, PO 2026-09-23).
6. **Uniqueness:** against every account of the tenant including retired ones — `uq_ledger_accounts_code` counts soft-deleted rows, so the refusal and the index agree. Same format rules as create (`_clean_code`).
7. **Usage counts** for the confirmation are the ledger's own: distinct bills (`source_type='invoice'`) and payments (`'payment'`) with a journal line on the account, plus all journal lines. The warning names the latest closed month and the latest sent export whose window holds a posted line on the account.
8. **Not changed (PO, *"ok do not make chnages"*):** default lookups by code (risk 3) and exports (risk 4). Also left, and filed: `DEF-LED-10647` — the per-authority remitting basis is keyed by code.

## 4 · What is built
- **Server** — `apps/ledger/chart_api.py` (`PATCH /ledger/accounts/{id}` accepts `code`, one transaction for the whole PATCH; `GET` carries `usage`) · `apps/ledger/services.py` (`change_account_code`, `account_code_usage`, `tax_payable_account_ids`; 5a in `_create_missing_accounts`; the allocator and `create_tax_authority_account` read/stamp `seed_key`; `_chart_row` serves `former_code` + `code_history` and reads its flags by slot) · `apps/ledger/chart.py` (`is_tax_payable_account`, `seed_codes`) · `apps/ledger/selectors.py` (`tax_payable_q`) · 5b in `journal.py` (remittance), `reporting.py` (tax report ×2), `close.py` (month-end remittance check), `chart_api.py` (GL map tax section) · `reporting.trial_balance` + `wire.trial_balance_dict` serve `former_code` (Q1's *"(formerly 4150)"* on the GL report) · `models.py` + **`migrations/0021_cr196_account_seed_key_and_code_history.py`** (🔒 HUMAN-REVIEW-PENDING, review-ledger row) · `openapi/schema.json` regenerated.
- **Web** — `features/ledger/ChartOfAccountsPanel.tsx` (Code field for a System Admin, read-only with *System Admin only.* otherwise; confirmation with counts + Q2 warning at the danger tier; *formerly 4150* on the row; *The type cannot change.*) · `features/ledger/GeneralLedgerPage.tsx` (trial balance *formerly*) · `api/endpoints.ts` · `features/audit/auditEvents.tsx` (`ledger_account.code_changed`). 15 keys in all eleven catalogues, `finance.coa.edit.frozen` retired (`10-scripts/i18n_fanin.py`).
- **Docs** — BR-LED-040 amended for the code; EP-LED-02 (§1, TC-4, field table, acceptance, BR-LED-023 note); EP-LED-06 TC-6 and its consumed-rule row; `03-field-map.md`; stale docstrings in `services.py`/`chart_api.py`/`ChartOfAccountsPanel.tsx`; `10-scripts/def_led_6140_chart_dialogs_walkthrough.mjs`.

## 6 · Tests (red first)
- `06-backend/tests/test_cr196_chart_code_editable.py` — **14 of 17 RED on the previous code** (the 3 that passed: a clerk still renames; type still refused; the allocator case, vacuously, because the rename was refused — it now asserts the rename landed). Green after, plus the trial-balance *formerly* assertion.
- `07-frontend/src/features/ledger/chartCodeEdit.dom.test.tsx` — **6 of 7 RED on the old panel**, then the trial-balance case RED on the old GL page; 8/8 green.
- `tests/test_us_led_005_chart_api.py::tc3b` amended (code from a System Admin now lands; type and a clerk's code still refused).
- **PostgreSQL NOT run** — a PG 16 cluster exists in the container but no role is reachable without switching OS user. The one caught `IntegrityError` is inside its own savepoint and re-raises (law 14 does not arise); the migration's `set_config` back-fill is unexercised on PG.
- **Reds read and dated, none caused here:** `test_us_led_005_chart_api::tc6` (asserts the retired `gl_mapping_bulk_write_is_not_served` code; the response's `unavailable` is untouched here); `test_us_led_015_month_close::tc1/tc2` (`runs_issued` expected `unknown`, billing published `unissued_run_count` in `30ae26b97`, 2026-10-17); `test_be11_openapi::tc02` (public `portal/public/requests` etc. since `74f402702`, 2026-10-13); `test_be11_openapi::tc05` was red on the tip since `1c3b89be7` (CR-194 work routes) and is green after the regeneration; web `moveInOneWord` (since `b58a3da39`, 2026-10-17) and `usEnglishCatalogue` (`82ce807c5` 2026-10-26, `39486a29a` 2026-10-24).

## 5 · Version and rollback
**No version bump in this lane** (coordinator's instruction). **Rollback:** revert the commits; `ledger/0021` reverses by dropping the two columns (a code already changed stays changed — the account's id never moved, so nothing re-points).

**Status:** DONE 2026-10-29 (no version bump in the lane; the release that carries it records the number).
