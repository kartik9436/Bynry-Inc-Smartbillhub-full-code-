# Housekeeping walk — 2026-10-14 (decision log "THE 77 OPEN TASKS FROM ROUNDS 1–3", items 3, 10, 11)

Walked 2026-10-14 by the housekeeping maintenance lane on a **private copy** of the
dev database (`smartbillhub_hk`, made with `createdb -T smartbillhub`, dropped
afterwards), Brazos Bend Utilities, at 1440 px, API on 8013 and the app on 8093,
through `10-scripts/housekeeping_2026_10_14_walk.mjs` (and, for the reopen itself,
the CR-181 lane's own `10-scripts/cr181_returning_customer_walk.mjs`). Every check
quoted below printed PASS unless it says otherwise.

**Set-up on the copy, not a user step:** the copy lacked `customers/0083`, so it was
migrated; Dana Whitfield's (System Admin) and Sam Reyes's (Billing Clerk) passwords and
one portal customer's password were set so the walk could sign in; and Viktor Valdez's
AC-2026-00022 (unit SCW-U-022) was **moved out through the real door**,
`services.move_out`, on **10/12/2026** with final reads W-5021 1,800 / E-5021 3,880 —
it drafted final bill BL-2610-000251 ($178.19) and filed move-out **MVO-26-0002**.

## Item 1 — DEF-CUS-10125 · the Move-outs list keeps a reopened account's earlier move-out

| Shot | Step and what it shows |
|---|---|
| `A1-moveouts-before-reopen.png` | Accounts › Move-outs, search *AC-2026-00022*: one row, **MVO-26-0002 · 10/12/2026 · Completed** |
| `A2-reopen-*.png` | Move-ins › New: SCW-U-022, 10/14/2026, opening reads; search Viktor by name + phone; *Reopen AC-2026-00022*; *Must pay first* refused by name; *Carry it*; Complete → **MVI-26-0022** on the same account |
| `A3-moveouts-after-reopen.png` | Move-outs again, same search: the row is **still there — MVO-26-0002 · 10/12/2026 · Completed** — while the account is live again. Before the fix this row vanished (the list read `accounts.closed_at`, which the reopen clears); that is the red half of `test_def_cus_10125_10126_reopened_account.py` |

**Records after pass A:** `accounts` AC-2026-00022 **active · opened 2026-10-14 · closed —**;
`move_in_reopenings` **previous 2026-08-01 → 2026-10-12 · carry · 168.1800**; `move_records`
**MVO-26-0002 move_out 2026-10-12** and **MVI-26-0022 move_in 2026-10-14**.

## Item 2 — DEF-CUS-10126 · cancelling a move-in that reopened an account restores the old dates

The copy was re-made and set up again (same move-out, MVO-26-0002), and Viktor was
reopened on **10/20/2026** (MVI-26-0023, carry $168.18).

⚠ **How the cancel was pressed.** The details page offers *Cancel move-in…* only on
*Not started*, *Scheduled* and *Waiting on a read* (`moveRecordActions.moveInActionSlots`).
A reopened move-in whose opening reads were all taken reads *Completed* (`B1-cancel-1-
details-before.png` — More holds *Send a message* and *Print*), so the walk sent the two
requests the confirm modal sends — `GET /moves/MVI-26-0023/cancel-preview` and
`POST /moves/MVI-26-0023/cancel` — from the signed-in browser session, and photographed
every screen after. Whether a *Completed* reopened move-in should offer the button is
not this fix's question.

| Shot | Step and what it shows |
|---|---|
| `B0-moveouts-reopened.png` | Move-outs after the reopen: MVO-26-0002 · 10/12/2026 still listed (item 1 again) |
| `B1-cancel-1-details-before.png` | MVI-26-0023 *Completed · Moved in 10/20/2026* |
| (preview) | `closes_on: 2026-10-12` — the account would close on the **earlier tenancy's own date**, not 10/19 |
| `B1-cancel-2-details-cancelled.png` | *Canceled · Moved in 10/20/2026*. ⚠ **The first walk read *Moved in 08/01/2026* here** — the move-in date is read off `accounts.opened_at` and the cancel gives the earlier tenancy's start back; fixed in `16f585d81` and re-photographed |
| `B1-cancel-3-accounts-list.png` | Accounts list, AC-2026-00022 |
| `B2-moveouts-after-cancel.png` | Move-outs: **exactly one** row for the account, MVO-26-0002 · 10/12/2026 (the account's own close again — never listed twice) |

**Records after pass B:**

| Check | Value |
|---|---|
| `accounts` AC-2026-00022 | **closed · opened 2026-08-01 · closed 2026-10-12** (before the fix: closed 2026-10-19, opened 2026-10-20) |
| `service_agreements` | 2 × 2026-08-01 → 2026-10-12 (the earlier tenancy, untouched) + 2 × 2026-10-20 → 2026-10-19 (the move-in's own, ended the day before it started, the ordinary cancel shape) |
| `move_in_reopenings` | MVI-26-0023 · previous 2026-08-01 → 2026-10-12 · carry · 168.1800 (written once, unchanged) |
| `move_records` | MVO-26-0002 move_out 2026-10-12 · MVI-26-0023 move_in 2026-10-20 (unchanged) |
| `audit_log` | `account.closed` (→ closed 2026-10-12) · `account.reopened` (before 2026-08-01/2026-10-12 → after opened 2026-10-20) · `account.move_in_cancelled` (before opened 2026-10-20 → after **opened 2026-08-01, closed 2026-10-12, restored_previous_tenancy true**) |

## Item 4 — DEF-SHL-10116 · New Connection step 2 as a Billing Clerk

| Shot | What it shows |
|---|---|
| `C1-new-connection-step2-clerk.png` | Signed in as **Sam Reyes, Billing Clerk**; New Connection step 2, State **IA** → *Not this utility's state.* (the utility is in Texas). Requests made: `200 /api/brazosbend/shell/display` and **no** `/settings/regional` (which answers a clerk 403, so before the fix the sentence never appeared for a clerk) |

## Item 6 — DEF-CWP-10118 · portal Documents: rows vs failed (never empty)

| Shot | What it shows |
|---|---|
| `F1-portal-documents-1-live.png` | A customer (AC-2026-00001) signed in to the portal: 6 documents listed |
| `F1-portal-documents-2-unreachable.png` | The same page with the documents request dropped in the browser: **"We could not open your documents." · Try again · Get help**, `data-portal-state="failed"`, and not the empty sentence |

The fix itself was test-only (the sentence had been shortened to rule 33 on 2026-10-11 and
two test matchers still looked for the old words); the server's own *queue unreachable*
answer ("We can't show what we sent.") cannot be produced on a working server and is
covered by `Documents.dom.test.tsx`.

## Item 7 — DEF-GOV-10114 (the half that was fixed) · New Connection step 4

| Shot | What it shows |
|---|---|
| `D1-new-connection-step4-strip.png` | Step 4 · Charges draws the seven-cell context strip, now composed from `features/work/buildRecord/BuildContextStrip.tsx` (an empty draft: *Customer — · Premise — · Scope A new premise · Units — · Services — · Counted 0 · 0 · 0 · Plan —*). The filled cells are asserted by `NewConnectRedesignSteps45.dom.test.tsx` |

The build page's *Take payment* dialog was **not** changed (see the lane report): nothing to walk.

## Item 8 — DEF-WRK-10122 · runbook setup shows Settings' value

| Shot | What it shows |
|---|---|
| `E1-runbook-bank-reconciliation-0-template.png`, `E1-…png` | Runbooks › Templates › Bank reconciliation › **+ Add**, then its Scope tab: *Auto-match tolerance · FROM SETTINGS · **$0.00** · Open settings →* `/brazosbend/settings/accounting` — Settings' `finance_controls.bank_match_amount_tolerance` is `0` on the copy. Before the fix: *Not set in Settings* |
| `E2-runbook-leak-alert-0-template.png`, `E2-…png` | Leak and high-usage alert: *Quiet hours · FROM SETTINGS · **08:00–21:00** · Open settings →* `/brazosbend/settings/notifications` (`notification_settings` 08:00 / 21:00 on the copy); *Unattended after* (`runbooks.gate_mode`) still reads **Not set in Settings** — one of the fifteen keys with no Settings field |

## Items 3 and 5 — test/data only, nothing to walk

* **DEF-CUS-10127** — two backend test fixtures made billable (a billing cycle, a priced
  plan and a read on the move day); no product code changed.
* **DEF-INT-10117** — the frozen catalogue count in `connectorVocabulary.test.ts` moved
  502 → 509 with the seven live keys named; no product code changed.
