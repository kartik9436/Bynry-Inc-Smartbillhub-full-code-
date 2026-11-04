# Balance to owner posts · Owner summary — walk (CR-185-BRC10, 2026-10-14)

Walked by lane OWNER-D4D5 on a **private copy** of the dev database
(`smartbillhub_owner`, dropped afterwards), Brazos Bend Utilities, as Dana
Whitfield (System Admin) at 1440 px. Backend on 8009, the built SPA on 8089.
The copy had Dana's walk password set and `reports/0012` (then numbered 0011) applied — and, for the third walk, `customers/0085` too; nothing else
was changed except the D4 fixture described below.

## D5 — a residue tied back to the owner moves only once it is IN THE BOOKS

⚠ **RE-WALKED a third time, after the coordinator's ruling of 2026-10-14
(*"the transfer must move only money that is IN THE BOOKS"*), on a fresh
private copy.** The first walk posted at step 3 (a refused commit then left
money moved); the second posted at commit, with the not-yet-issued final bill
in the figure (the tenant read −$317.87). Now the commit RECORDS the tie-back
as pending and posts nothing; the entry posts when the final bill is sent from
Billing, for what the closed account then owes per the books. Driven by
`10-scripts/def_cus_10093_move_out_final_draft_walkthrough.mjs`
(`SHORTFALL=transfer`, move-out day 10/14/2026, SM-7042 ticked *Estimate*;
then `SEND=1` on the drafted bill), owner account **AC-2026-00053** (Mill Pond
Apartments LP, 301 Mill Pond Ln).

### AC-2026-00043 (Sam Rylance, Apt 103) — commit, then send the final bill

| Shot | What it shows |
|---|---|
| `D5-ok-step2.png` | Step 2 — reads typed; SM-7042 (no earlier reading) ticked *Estimate* |
| `D5-ok-step3.png` | Step 3 — prior balance $82.26, final bill (draft) $234.74, **Short by $311.90** |
| `D5-ok-step3-decided.png` | *Tie it back* recorded — **"$311.90 moves to AC-2026-00053 when the final bill is sent."** Nothing posted |
| `D5-ok-step4.png`, `D5-ok-done.png` | Completed — **To the owner: $311.90 · Moves to the owner when the final bill is sent**; final bill BL-2610-000251 $234.74 Draft |
| `D5-ok-bill-draft.png`, `D5-ok-approve-dialog.png`, `D5-ok-bill-issued.png` | Billing — the drafted bill approved and sent; **Issued** |
| `D5-record-posted.png` | Move-out record MVO-26-0002, *Still owed* — **To the owner: $317.00 · Posted** |
| `D5-account-posted.png` | Account AC-2026-00043 — **To the owner: $317.00 · Posted** |

### Records checked (read from the database)

| Check | Before the move-out | After the commit | After the final bill was sent |
|---|---|---|---|
| `balance_tie_backs` for AC-2026-00043 | — | **pending**, preview $311.90, final bill BL-2610-000251 | **posted**, $317.00, settled 10/14/2026 |
| Transfer journal entries | 0 | **0** | **1** — JE-101426-0493, 2026-10-14: **DR 1200 · AC-2026-00053 · 317.00 / CR 1200 · AC-2026-00043 · 317.00** |
| AC-2026-00043 AR (1200) | $82.26 | **$82.26** (unchanged) | **$0.00** ($82.26 + the $234.74 bill, JE-101426-0492, − $317.00) |
| AC-2026-00053 (owner) AR | $0.00 | $0.00 | **$317.00** |
| Tenant's total AR (1200) | $27,885.40 | $27,885.40 | **$28,120.14** = $27,885.40 + the $234.74 bill; the transfer added nothing |
| Journal lines in the tenant | 2,686 | 2,686 | +6 bill lines, +2 transfer lines (both on 1200) |

⚠ **Why the preview said $311.90 and the books said $317.00 (`DEF-CUS-10151`,
filed from this walk):** step 3 subtracts the account's $5.10 unapplied
credit from a ledger balance that already contains it — every payment credits
receivables in full when it arrives, so the $82.26 prior balance is already net
of the $5.10. The posted figure is read from the books after the bill issued,
so it is not affected; the preview on step 3 understates by the credit.

### A commit that is REFUSED (from the second walk, unchanged by this ruling)

| Shot | What it shows |
|---|---|
| `D5-refused-step3.png`, `D5-refused-step3-decided.png` | AC-2026-00041, Short by **$1,006.06**; tie-back recorded |
| `D5-refused-step4.png`, `D5-refused-done.png` | The commit refused — *"water still has no usable read and no decision"* (a final-read rule, unrelated). **Account still open, nothing recorded, nothing posted; AR $544.49 unchanged.** |

Not walked in the browser, covered by tests on SQLite and PostgreSQL 16
(`06-backend/tests/test_cr185_balance_to_owner_posts.py`): a voided draft posts
nothing and leaves the tie-back pending; a retry or re-send posts nothing new;
a move-out with nothing left to bill posts at commit; the move-out record waits
for a draft that is still unsent.

## D4 — the Owner summary report

**Walk fixture (private copy only):** Mill Pond Apartments LP was given a second
property — master account **AC-2026-00090** at **88 Pine Vista**, linked to the
same customer — and two issued October owner bills were inserted directly
(`BL-WALK-185-1` on AC-2026-00053: *Unit 7 · water base charge* $15.00, water
usage $30.00, water base charge $10.00; `BL-WALK-185-2` on AC-2026-00090:
electric base charge $30.00). They were inserted as rows, not issued through a
bill run, so they post nothing; the report reads bills only. Driven by
`10-scripts/cr185_owner_summary_walkthrough.mjs` — **ALL PASS** (10 checks).

| Shot | What it shows |
|---|---|
| `D4-1-library.png` | The reports library lists **Owner summary** (Customers · Statements) |
| `D4-2-asks-for-owner.png` | Opened with no owner: the viewer asks for one (*Owner*, *This report opens on one owner.*) |
| `D4-3-maple-style-owner.png` | Found by typing *Mill Pond* (master accounts only): **301 Mill Pond Ln** empty units $15.00 · common areas $40.00 · $55.00; **88 Pine Vista** common areas $30.00; **Grand total $85.00**, 2 properties; Print and Download beside the table |
| `D4-4-print-view.png` | The same page rendered for print |

## Not done on the walk

* The drafted final bill for AC-2026-00043 was not sent from Billing, so the
  tenant at $0.00 after issue was not seen in a browser.
* The CSV download was not opened in the browser; `tests/test_cr185_owner_summary_report.py`
  proves the export path returns every property (3 of 3 on a 2-per-page screen).
