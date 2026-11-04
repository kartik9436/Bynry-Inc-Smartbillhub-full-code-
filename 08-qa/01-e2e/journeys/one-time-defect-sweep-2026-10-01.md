# One-time bill defect sweep — 2026-10-01

---
id: one-time-defect-sweep-2026-10-01
tier: 2
rules: [BR-BIL-005, BR-BIL-010, BR-BIL-012, BR-BIL-020, BR-BIL-024, BR-BIL-062, BR-SHL-020]
stories: [US-BIL-010, US-BIL-011, US-BIL-012, US-BIL-013, US-BIL-014]
depends_on_journeys: [J74, J75]
# WALKED 2026-10-01 at 1440 in Chromium on PostgreSQL 16 — tip 2.430.0 → 2.431.0, fixes shipped as 2.433.1.
# Spec `07-frontend/e2e/one-time-defect-sweep.spec.ts` (6 of 6 pass).
# Screens `08-qa/screens/one-time-sweep-2026-10-01/` + `sweep-results.json`.
---

**The request, verbatim (PO 2026-10-01):** *"can you check these bugs based on actual code - 26 older one-time
bugs from 29–30 Sept still marked open … Each needs re-checking on today's build, then either closed with proof
or fixed. and fix it"*. Twenty-three of the 26 are this sweep's; `DEF-RAT-8713`, `DEF-BIL-8744` and
`DEF-BIL-8749` belong to lanes that were running and were not touched.

**Which process:** maintenance (`22-product-maintenance-process.md`) — every row is about a screen a clerk uses
today. Each was re-read against the code on the tip, and every claim a clerk can see was reproduced in a browser.

## The world

A copy of J75's `sbh_six` (Six Rivers Utility, the eight one-time bills J75 sent), made with
`createdb -T sbh_six sbh_ots_sweep` and migrated to the tip (`rating/0050`–`0052` had landed since J75, and
without them `/charges` answered 500 — an environment fact, not a product defect). `sbh_six` itself was not
touched. Backend `runserver` on the tip, SPA built with `vite build --mode compose` behind `server.mjs`.

## The result: 20 already fixed · 2 fixed now · 1 waiting for the Product Owner

Most of the September rows were written against two screens that no longer exist. On 2026-09-30 the one-time
bill was redrawn as **one page, four steps — Account · Services · Review · Send** (`9cf662125`, design
`04-docs/05-modules/07-billing/11-one-time-bill-redesign.md`, PO *"your drawing is correct now"*), its API was
rebuilt to the contract (`0b466f991`, build plan A1–A9), and the PO accepted the walk-through on 2.412.4
(decision log 2026-09-30, *"THE ONE-TIME BILL IS ACCEPTED BY THE PO"*, verbatim *"ok"*). The old in-tab form
(`OneTimeBillTab`) and the unfinished three-step wizard (`OneTimeWizardShell`, `OneTimeWhatStep`,
`OneTimeConfirmMount`) were deleted in the same change. **Nobody closed the rows the redraw answered** — the
build plan's R1 filed 22 new gaps and did not walk the 23 older ones — which is why they were still open.

| id | the problem, in one line | verdict | evidence | version |
|---|---|---|---|---|
| `DEF-CUS-7902` | Move-outs *Final read* showed *Taken* and a bare dash when the reading's source was never recorded | **FIXED NOW** | Still red on the tip (38 of 39). The cell had switched to a 3-word short form with the sentence on hover (`DEF-CUS-6177`), and this code had no short form, so it fell to `—`. Added *Source not recorded* in all 11 catalogues; `MoveOutsTab.test.tsx` asserts the words on screen and the sentence in the tooltip — red first, then 39 of 39. DOM test, not a browser walk: the J75 world has no closed move-out with an unrecorded flag | 2.433.1 |
| `DEF-BIL-7924` | The redrawn one-time bill sat at an address nothing linked to | ALREADY FIXED | `9cf662125`: the page takes the tab's own address. Pressing *One-time bill* on the Billing strip lands on `/sixrivers/billing/one-time` with the four-step rail — `1440-01-door.png`; `OneTimeBillDoor.dom.test.tsx` asserts the door by address | 2.411.x → live 2.412.1 |
| `DEF-BIL-7925` | Four database ids on the one-time bill, from the rating engine's refusal sentence | ALREADY FIXED | `7dce84d27` (2.410.9, `DEF-RAT-7991`) gave nine rating refusals a clerk sentence and moved every render site to `refusalSentence`; `62eba2302` (2.412.5) strips ids and rule codes from any engine sentence on the one-time routes. Gate `G139` runs the chain and reads the clerk payload; `test_def_bil_8287__the_engine_sentence_is_cleaned_of_ids_and_rule_codes`. No screen in this walk carried a uuid | 2.410.9 / 2.412.5 |
| `DEF-BIL-7927` | Step 1 asked for the account twice — a search box and a select | ALREADY FIXED | `9cf662125`: one searchable `AccountCombobox`. On all six kinds the account panel holds exactly 1 combobox and 0 text boxes (`sweep-results.json`, `1440-02-step1-interim.png`) | 2.412.1 |
| `DEF-BIL-7928` | Step 1 showed up to 178 words, with rationale | ALREADY FIXED | `9cf662125`. Counted on screen (select options excluded): interim 51, first 55, final 52, catch-up 59, penalty 66, fee 56 — and most of that is the account's own facts. The longest help line is *"From the cycle. Change if needed."* (3 + 3 words); no lede, no rationale | 2.412.1 |
| `DEF-BIL-7929` | Step 3 was two explanation cards and no action | ALREADY FIXED (design superseded) | The drawing the row compared against (blueprint p114) was replaced by the PO-confirmed redesign of 2026-09-30. `9cf662125`: Review shows the bill as a table that foots, the delivery choice and *Save draft · Back · Continue*; Send shows the total, due date, warnings and five confirmations — `1440-07-fee-review.png`, `1440-08-fee-send.png`. No rationale card remains | 2.412.1 |
| `DEF-BIL-7960` | *One-time bill* opened the OLD tab; the redraw had no door | DUPLICATE of `7924` | Same fault, filed later the same day; fixed by `9cf662125` (`1440-01-door.png`) | 2.412.1 |
| `DEF-BIL-7961` | The redraw's step 2 had no control to step 3 | ALREADY FIXED | The three-step wizard was deleted (`9cf662125`). On the new page a fee bill walked Account → Services → Review → Send by *Continue* on every step — `1440-06-fee-step2.png` … `1440-09-fee-sent.png` | 2.412.1 |
| `DEF-BIL-7962` | The redraw's step 3 had no Create control, so it could write no bill | ALREADY FIXED | `9cf662125` + `0b466f991` (one-call Send). Sent from the screen in this walk: **BL-2610-000009, $75.00, run `issued`** (`1440-09-fee-sent.png`, database) | 2.412.1 |
| `DEF-BIL-7967` | The duplicate refusal named the bill by a raw ISO timestamp | ALREADY FIXED | `0b466f991` (A8) serves the bill number; the page shows *"Already billed for this period. BL-2609-000001 · 10/01/2026 · by Priya Shah — Open that bill"* — `1440-04-already-billed.png`; no timestamp, no uuid. (The old catalogue sentence `billing.oneTime.duplicate` still holds `{{ran_at}}` and is rendered by no screen.) | 2.412.1 |
| `DEF-BIL-7968` | A refused first bill showed *"Check the cycle and dates, then retry"* | ALREADY FIXED (cause superseded) | The refusal it quoted (*"did not move in during …"*) cannot arise from the screen: PO change 2026-09-30 made the move-in date a picker the clerk sets, and it IS the bill's period start (`5c2bc32e2`, `one_time.first_bill_move_in`; decision log *"THE MOVE-IN DATE IS A DATE PICKER THE CLERK CAN OVERWRITE"*). Walked: a first bill with move-in 09/01 passes step 1 (`1440-05-first-bill-move-in-set-by-clerk.png`). And no one-time refusal falls back to that sentence any more (`62eba2302`, `DEF-BIL-8288`) | 2.411.5 / 2.412.5 |
| `DEF-BIL-7972` | First bill was offered and could not be produced — the plan minimum does not travel | ALREADY FIXED | The page takes the move-in reading on step 2 (`9cf662125`, `5449c827e` `DEF-BIL-8563`), so a first bill has measured usage. J74 and J75 each sent one: **BL-2609-000003, $388.09**, issued. The plan-minimum route (`first_bill.refuse_without_a_minimum`) still refuses when NO reading exists at all, by its own sentence — the PO's 2026-10-01 minimum ruling is being built by another lane | 2.416.1 |
| `DEF-RAT-7991` | Four uuids on the one-time bill; the guard could not see a runtime value | ALREADY FIXED | `7dce84d27` — its own commit, 2.410.9, never closed. `G139` proved red through `run()` (`10-scripts/tests/g139_red_proof.py`) | 2.410.9 |
| `DEF-RAT-8004` | The nightly run picks the newest of two in-force rate versions; the one-time bill refuses | **STILL OPEN — for the PO** | Unchanged on the tip: `selectors.in_force_version` still orders by `-effective_from` and takes the first. Not a fix a lane may choose — it is the money-path question in the decision log of 2026-09-29, and no ruling has landed. `rating/0047`'s no-overlap constraint makes NEW cases impossible; old ones remain | — |
| `DEF-BIL-8075` | The one-time tab had no Send control | ALREADY FIXED | `0b466f991` (`POST /billing/one-time/{run_id}/send`) + `9cf662125` (Send step). Sent from the screen: BL-2610-000009; J75 sent eight more | 2.412.1 |
| `DEF-BIL-8076` | Bill date was optional but a cycle-less bill cannot issue without one | ALREADY FIXED | Required on the screen (`oneTimeBillModel.clientProblems`) and on the server (`one_time_answer.problems_in`) — `1440-03-problems-at-once.png` shows *"Enter the bill date."* on the field | 2.412.1 |
| `DEF-BIL-8078` | Reading entry on step 2 posted nothing | ALREADY FIXED | `9cf662125`: step 2's Continue stages, validates and posts through Meter Reads' `/read-batches`. Database: the readings typed in J75 (512.0, 108.6, 404.2, 228.5) are stored with an import batch | 2.412.1 |
| `DEF-BIL-8079` | The screen never sent `charge_code`, so a penalty lost its TAMPER line | ALREADY FIXED | `oneTimeBillModel.requestBody` sends it whenever the kind takes one. Database: BL-2609-000007 (penalty) carries **TAMPER $250.00**; BL-2610-000009 carries RECON $75.00 | 2.412.1 |
| `DEF-BIL-8085` | Every one-time rule refusal read as the bulk run's *"Check the cycle …"* sentence | ALREADY FIXED | `0b466f991`: `api._one_time_refusal` never uses `billing.run.refused`; `62eba2302` falls back to the engine's own cleaned sentence. `test_otb_a_one_time_api_contract.py` and `test_def_bil_8288__a_bare_rule_refusal_shows_the_engines_sentence_not_the_generic_one` | 2.412.5 |
| `DEF-BIL-8086` | Only the first problem was returned and the screen ignored `field_errors` | ALREADY FIXED | `0b466f991` (A3) refuses every step-1 problem in one 422, each on its field; the page merges them. Walked: *"Fix 5 things to continue"* — period from, period to, reason, bill date, days to pay, each marked on its own field (`1440-03-problems-at-once.png`) | 2.412.1 |
| `DEF-BIL-8087` | *"Choose an account and a period."* when the missing thing was the reason | ALREADY FIXED | Each problem names its own field: *"Choose a reason."* under Reason (`1440-03-problems-at-once.png`) | 2.412.1 |
| `DEF-BIL-8090` | A first bill's connection charge was not checked for a GL account | ALREADY FIXED | `a1ca2663c` (build plan B12): refused at draft with `billing.oneTime.err.chargeCodeNoGl`; `test_b12_connection_charge_needs_a_gl_account.py` passes | 2.412.1 |
| `DEF-BIL-8091` | Two stale comments: the run-outcome docstring and the issue refusal's *"the cycle"* | **FIXED NOW** (half was fixed) | The issue refusal was fixed in `a1ca2663c` (`billing.issue.noDueTerms`). The docstring was corrected in the same commit and **went stale again the same day**: it said a one-time bill *"has no send path"*, and A6 then built one. Re-worded in `runs.record_run_outcome`. And the refusal's own key, `billing.issue.noDueTerms`, was defined in NO catalogue (`G18` lists it): a clerk would have read the generic line. It now reads *"No days to pay. Set them on the bill."* in all 11 Database: all nine one-time runs read `issued` after Send, through `release_run` → `complete_release` → `record_run_outcome` | 2.433.1 |

## Reds found on the way that this sweep did not cause (law 7, habit 1)

| id | what | dated | state |
|---|---|---|---|
| `DEF-BIL-8806` | `OneTimeBillPage.dom.test.tsx` asserted a due date that is only true on 2026-09-30 | written in `9cf662125`; red from 2026-10-01; proved by pinning the clock | **fixed** (clock pinned, 2.433.1) |
| `DEF-BIL-8807` | `test_def_bil_8287`'s census of unnamed refusals finds two sites in `gather.py` where it expects one | `bd94c047e`, 2026-10-01 09:24 UTC (changes row 44) | open — `gather.py` is another lane's |
| `DEF-CUS-8808` | `screenVoice.guard` Disconnects case: *"How a notice reached the customer…"* is not in the visible text | not bisected; last Disconnects change `4448a4551` (2026-09-25) | open — not a one-time screen |
| `DEF-CUS-5993` | `screenVoice.guard` transfer step 1 (sub-meter) | already filed 2026-09-20 | open, unchanged |

## Re-run

1. `createdb -T sbh_six <copy>` then `manage.py migrate` against the copy.
2. `runserver` on the copy; `npx vite build --mode compose`; `node server.mjs` with `API_PROXY_TARGET`.
3. `E2E_TENANT=sixrivers E2E_EMAIL=priya@sixriversutility.com E2E_BASE_URL=http://127.0.0.1:<web>
   E2E_VIEWPORT=1440 npx playwright test e2e/one-time-defect-sweep.spec.ts --workers=1`.
   ⚠ The fee case SENDS a bill for Unit 2 (Ben Okoro) dated today; a second run on the same copy the same
   day may meet the *Already billed* banner instead — use a fresh copy.

**This journey leaves (for downstream):** one more issued fee bill on the copy (`BL-2610-000009`), and nothing
on `sbh_six`.
