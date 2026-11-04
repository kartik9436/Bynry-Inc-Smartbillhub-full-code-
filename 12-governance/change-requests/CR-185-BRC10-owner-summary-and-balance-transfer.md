# CR-185-BRC10 · Balance to owner posts (AR to AR), and an Owner summary report

**Raised:** 2026-10-14 by the Product Owner, in chat, answering the landlord questions D1–D5.
**Requester's words (verbatim):** *"D2 … seperate agreemnts - this will not arrive ; D3 … no ; D4 … utility can produce thi using reort ; landload cannot do it on there own today - Option 1 Summary document only: one monthly statement with a section per property and a grand total of $85. Each property's account keeps its own books, and they still pay per property.; D5 … option 1; property is always under landload agreement"*
**Rulings:** decision log 2026-10-14 *"LANDLORD AGREEMENT: NOT NOW — LATER IT ATTACHES TO THE PLAN"* and *"LANDLORD D2–D5: … BALANCE-TO-OWNER POSTS (closes OQ-1250 → a)"*. `OQ-1250` CLOSED → (a).

## 1 · Classification
A **change**, two parts. D5 reverses what was built while `OQ-1250` was open (the tie-back was *recorded only*, `posting: {posted: false}`); D4 adds a report the product never had. Neither is a defect: both did what the open question allowed.

## 2 · What is reversed or added
| Before | After |
|---|---|
| *Balance to owner* (tie back to the owner's account at move-out) records the decision and moves no money: `posting.posted = false`, `oq = OQ-1250` | **D5** — it posts ONE balanced entry through the ledger posting service: **DR accounts receivable (owner account) / CR accounts receivable (tenant account)**, same control account, the account dimension differs, amount = the residue tied back. No revenue, no bad debt, total AR unchanged. Idempotent; audit row; refused by name where the property has no owner account, exactly as before. |
| `US-LED-001`'s contract row *"Master-account balance transfer"* had no product caller | Wired: this is its caller, source type `transfer`, cited to the 2026-10-14 ruling. |
| No owner-level view across properties | **D4** — an **Owner summary** report in the reports library (staff-run, not portal): one owner, a section per property (empty units' base charges, common areas, other owner charges) from the owner accounts' own issued bills in the period, and a grand total. Owner picker, period, export and print. Nothing in the ledger changes; each property's account keeps its own books and is paid per property. |

## 3 · Tasks
| # | Task |
|---|---|
| B1 | `apps/ledger/balance_transfer.py` — composes the AR→AR entry for `posting.post` (🔒 HUMAN-REVIEW-PENDING). |
| B2 | `move_out_settlement.shortfall_decision` posts it on the `transfer` path, inside the decision's transaction; `posting.posted = true` with the entry. |
| B3 | Posting contract table (US-LED-001) row cited to the ruling. |
| B4 | Owner summary read: billing publishes the owner bills' lines, customers the owner's master accounts; `apps/reports/owner_summary.py` viewer + `reports/0012` catalogue row + export resource. |
| F1 | Move-out wizard and move-out record: the tie-back now says it is posted. |
| F2 | Report viewer: an *owner* finder for the required input; print view. |
| T1 | Tests SQLite + PostgreSQL: balanced pair by account and figure, idempotency, no-owner refusal, both balances move by the same, AR total unchanged, isolation; owner summary totals on a 2–3 property fixture. Frontend dom tests. |
| E1 | Walk on a private DB copy; screenshots + README in `05-prototype/owner-summary-balance-transfer-2026-10-14/`. |

## 4 · Status — BUILT, NOT RELEASED (lane OWNER-D4D5, 2026-10-14)
No version bumped and no CHANGELOG line — the release lane does both. **Judgments of ours:** decision log *"BALANCE TO OWNER AND THE OWNER SUMMARY — HOW D4 AND D5 WERE BUILT: TEN JUDGMENTS OF OURS"*. Review row: `12-governance/09-human-review-ledger.md` (CR-185-BRC10).

| # | Built |
|---|---|
| B1 | `apps/ledger/balance_transfer.py` — `post_balance_to_owner`: DR 1200 (owner account) / CR 1200 (tenant account), key `transfer\|<tenant account>\|balance_to_owner`, a different-figure replay refused. 🔒 HUMAN-REVIEW-PENDING, enrolled in `human_owned.txt`. |
| B2 | `move_out_settlement.shortfall_decision` posts it on `transfer` through `customers.seams.post_balance_to_owner`, one transaction with the audit row; amount = the 2-dp shortfall; book date = stated `as_of`, else `accounts.closed_at`, else refused `customers.move_out.balance_to_owner_needs_date`; a ledger refusal → `customers.move_out.balance_to_owner_not_posted`. `posting.posted: true` with the entry. |
| B3 | `US-LED-001` contract row *"Master-account balance transfer"* cites D5 and names its caller; `posting.py` docstring's caller list amended (no code). BR-CUS-097 amended. |
| B4 | `billing.reporting.owner_bill_summary` · `customers.selectors.owner_properties` · `apps/reports/owner_summary.py` · `reports/0012_cr185_owner_summary` (Customers · Statements) · export resource `owner-summary`. |
| F1 | Wizard: *"Posted to the owner's account."* from the server's `posting.posted`; record page dialog *"$186.40 moves to A-10001 now."*; decided *"Posted to A-10001."*; Journal word *Transfer*. 11 catalogues. |
| F2 | Viewer: an *Owner* finder (master accounts) when a report requires `owner`; *Print* beside Download when `controls.printable`. `ReportPrintButton.tsx`. |
| T1 | `tests/test_cr185_balance_to_owner_posts.py` (9) + `tests/test_cr185_owner_summary_report.py` (8) + cr056 tc7: 18 passed on SQLite AND PostgreSQL 16. `ownerSummaryReport.dom.test.tsx` (4) + updated move-out/record tests. Red first: posting off → 7/9 red; sides swapped → red on account and balances; sections mis-read → $155 for $85; viewer chooser/Print removed → 2/4 red. |
| E1 | `05-prototype/owner-summary-balance-transfer-2026-10-14/` — JE-101426-0492 $1,006.06 AC-2026-00041 → AC-2026-00053, total AR $27,885.40 before and after; Owner summary $85.00 for a two-property owner. |

**POSTED AT COMMIT (coordinator ruling 2026-10-14, fixes `DEF-CUS-10152`):** step 3 records and previews; `services.move_out` (payload `shortfall_path: "transfer"`) posts the entry inside the commit for what is owed then. Refused commit → nothing posted; retry → once. Walk: AC-2026-00041 refused, $544.49 untouched; AC-2026-00043 completed, $400.13 to AC-2026-00053, total AR $27,885.40 unchanged. Completion screen: *To the owner · $400.13 · Posted to the owner's account.*

**ONLY MONEY IN THE BOOKS MOVES (coordinator ruling 2026-10-14, supersedes the paragraph above for a drafted final bill; decision log *"BALANCE TO OWNER MOVES ONLY MONEY THAT IS IN THE BOOKS"*):** a commit that drafts a final bill records the tie-back PENDING in `balance_tie_backs` (customers 0085, RLS FORCE) and posts nothing; `billing/issue.py` asks customers through `billing/customers_seam.post_pending_balance_to_owner` when that bill issues, and the ledger posts ONE entry for the closed account's AR then (prior + bill − deposit and interest; payments are already in it). Voided draft → nothing, still pending (shown on the move-out record). Nothing to bill → posted at commit, as above. Record page → posts at once unless a final draft waits. Completion screen: *To the owner · $X · Moves to the owner when the final bill is sent*; the move-out record and the account show *Posted* once it has. Tests: `tests/test_cr185_balance_to_owner_posts.py` (14). Walk: `05-prototype/owner-summary-balance-transfer-2026-10-14/`.

**Open items:**
1. ~~The commit DRAFTS the final bill, so the posted amount includes the drafted total~~ — closed by the ruling above: nothing posts until the bill is issued. A pending tie-back whose draft is voided waits for the next final bill or for a clerk on the move-out record; nothing chases it on its own.
2. `OQ-CUS-12516` (where a shortfall decision is remembered) is now partly answered by the books for the transfer path — after posting, step 3 reads *Short by $0.00*. Collect and payment plan still forget on reload. Not closed here.
3. The owner sections are read from the bill line's own words (`invoice_lines` stores no unit) — `billing.reporting.OWNER_SUMMARY_CLASSIFIED_BY`.
