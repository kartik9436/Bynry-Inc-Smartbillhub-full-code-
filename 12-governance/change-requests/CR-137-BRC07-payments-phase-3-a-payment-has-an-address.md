# `CR-137-BRC07` · Payments blueprint **phase 3 — A payment has an address**

> **READ THIS FIRST IF YOU ARE A NEW SESSION.** This is the live progress record
> for phase 3, kept because the PO asked for one that survives the chat.
> **Every lane updates its own row in §3 in the commit that finishes it.**
> Phase 2's board is the sibling file `CR-136-BRC07-payments-phase-2-the-counter.md`
> and §2 of it (how screens are built) applies here unchanged.

| | |
|---|---|
| **Branch** | `claude/laughing-thompson-kpmwih` |
| **Source document** | `05-prototype/06 Payments Page Blueprint.pdf` — phase 3 task table **pp.18–20**, screen 2·2 and the modals on **pp.34–40** |
| **Tasks** | **21** — 4 backend · 4 db · 4 front end · 5 test · 2 other · 2 e2e |
| **What a clerk can newly do** | **Send a colleague a link to a payment. Cancel one taken by mistake** — *the only genuinely missing logic in the module.* |
| **Done when** | A clerk opens a payment at its own address, cancels one taken five minutes ago, and the history says who did what. |
| **Started** | 2026-09-23, on the PO's approval: *"yes i like your plans lets do it"* |

---

## 1 · The blocker is gone — and here is what it left behind

`P3.18` read *"⚠ Answer `OQ-1340` first"*, outcome *"No screen may call this path a
permanent record until it is answered."* **It is answered.**

**PO ruling 2026-09-23, verbatim:** *"keep the same rule s; when audit log is
delete - it is deleted thats okay"* — option (b) of three, **chosen against the
recommendation**, with the consequence shown first: Dana types cheque `4471` as
`4417` on 8 August and corrects it on 9 August; a year later **no record anywhere**
says it ever read `4417`, and a customer quoting the number on their own cheque
matches nothing in the system. Their call, made, **never re-asked** (law 13).

**Three things follow, and the third is the one that bites a builder:**

1. **`audit_log` has ONE retention rule and no row type is exempt from it.** That
   is now the fact any future retention question is measured against.
2. **The prohibition is permanent, not provisional.** No document, screen or
   docstring may describe correction as a permanent record of the old value —
   not *until it is answered*, but **ever**.
3. ⚠ **THE HONEST BUILD IS SILENCE, NOT A DISCLAIMER, AND THE TWO RULES WOULD
   OTHERWISE FIGHT.** **B14 rule 33 puts RATIONALE at ZERO WORDS ON SCREEN.** So
   the Correction screen says **nothing at all** about how long the old value
   survives — it simply never claims permanence. **A screen that explains the
   retention policy in order to be honest breaks rule 33 while trying to obey
   this ruling.**

⚠ **ONE LIVE STRING IS NOW FALSE.** Every successful correction response carries
`amendment_history_retention_unruled` on `unavailable[]`, and its words say the
retention *"has not been decided"*. **It has.** The key and its sentence move in
the `P3.18` commit — and a key named `_unruled` for a thing that is now ruled is
exactly the stale-pointer rot this repo files most. `CR-059` task 42's S35 copy
loses its *waiting on an answer* caveat in the same commit.

---

## 2 · How the screens are built

**§2 of the phase 2 board applies here word for word.** The short version, because
the PO said it twice: *"use drawing images exactly to build screen; dont use
text"* and *"use ui skills from repo - very important"*.

**B14 rule 42** — build from the drawing **as an image**; `10-scripts/pdf/pdf_render.py`
at scale 2.0, and the numbered notes beneath each drawing are instructions.
**Rule 41** the product matches the drawing exactly · **rule 36** drawing gives
layout, `r10`'s `UI-RULES.md` gives style, the kit is how you comply · **rule 38**
UI rules win on how a FORM is built · **rule 37** a drawn figure is an
illustration · **rule 43** build it as a COMPONENT · **rule 21** Tailwind only,
add the file to `route-b-migrated.txt` · **rule 31** no database id on screen ·
**rule 40** page-head title 32px · **rule 33** as quoted above.

Invoke `.claude/skills/react-tailwind-css-ui-generator`,
`.claude/skills/build-one-commitment-end-to-end`, `.claude/skills/measure-before-you-build`.

---

## 3 · The task board — **UPDATE YOUR ROW IN THE COMMIT THAT FINISHES IT**

`NOT STARTED` · `IN PROGRESS <lane>` · `DONE <commit>` · `BLOCKED <why>`.

| Task | Kind | What | Status |
|---|---|---|---|
| `P3.1` | backend | `GET /payments/{id}` — there is no such read, **which is why a payment has no address** | DONE e9cc747c5 — `GET /payments/{id}` takes the `PMT-` number **or** the uuid (the drawing's address is `/:tenant/payments/PMT-2609-000418`, B14 rule 31); another tenant's payment 404s, never 403 (US-PAY-004 TC-7). Serves `payment_row` VERBATIM plus the header strip (`source`, `reconciled`), `actions`, `receipts[]`, `next_copy_no` and `unavailable[]` |
| `P3.2` | backend | `POST /payments/{id}/cancel` — **the only genuinely missing logic in the module** | DONE e9cc747c5 — `processing → cancelled` on the original **plus a negative reversing row with its own `PMT-` number**, because `payments_totals` nets by ROWS and reads no status (a status move alone leaves the cancelled $158.10 in the day's takings). **No ledger posting and no allocation reversal**: `record_payment` returns before the allocator when `cleared_at is None`, so there is nothing to unpost — said in two codes on every result. Refused on `cleared` and the refusal NAMES Reverse. The STATUS is the idempotency key, so a double-click answers 200 + `created:false` |
| `P3.3` | backend | `POST /payments/{id}/receipt` — re-queues an existing document; templates, channels and queue all exist | DONE e9cc747c5 — `POST /payments/{id}/receipt` re-queues the EXISTING row per channel through `notifications.services.queue_document`, copying the pin, the recipient snapshot and `render_context` (`DEF-NOT-4449`). `copy_no` REQUIRED and served by the detail read, so a double-click collides with its own row in the database. A channel with no receipt is refused by name rather than composed — no second receipt path (PO 2026-09-22). ⚠ the ~30 lines are also in notifications' own view: `DEF-PAY-6231` |
| `P3.4` | backend | An `audit_log` read for the history panel. **What makes Cancel honest — a cancelled payment does not vanish** | DONE e9cc747c5 — `GET /payments/{id}/history`, **paginated in SQL** through audit's published `entity_trail` (`NFR-3`; `connection_reads._history` materialises its whole trail and is the shape this does not copy). Serves `at · what · who · note`; `what` is the audit CODE the screen translates (B14 rule 35) and `who` is a NAME, never a user id (rule 31). **It never claims permanence and says nothing about why**: the retention fact is a CODE on `unavailable[]`, because B14 rule 33 puts rationale at ZERO words on screen |
| `P3.5` | db | A sixth payment state. ⚠ `ck_payments_status` is written against five, so `cancelled` needs a migration that **alters the CHECK** | **DONE `a34053b88`** — `payments/0036`. `cancelled` is the sixth value; **it lands on the FROZEN side** of hard rule 4 and got there by DEFAULT (a derived tuple, and a literal `<> 'processing'` in the trigger), so it was proved rather than inherited. `ck_payments_status` checked for `DEF-PAY-6207`'s fault: it has none, but only because `status` is **NOT NULL at the column** — the CHECK itself would pass a NULL. **Renumbered from 0035 under a live collision with `P2.4`.** |
| `P3.6` | db | The immutability trigger, **both ways** — it permits the move a cancel needs AND freezes the row once it lands. **Neither half is safe to assume** | **DONE `a34053b88`** — ⚠ **NO TRIGGER CHANGE WAS NEEDED, AND THAT IS THE FINDING.** PERMIT: `processing → cancelled` is allowed (`status` is on the `mutable` list) and is NARROW — status + amount in one statement is refused. FREEZE: the next statement against the row is refused — amount, un-cancel, posting date, DELETE. Proved on **PostgreSQL 16**, RED at `payments/0035` first, by `10-scripts/p3_cancel_state_and_trigger_readback.py`, with two CONTROLS (a cleared amount must still be refused · `processing → cleared` must still succeed). **SQLite has neither the CHECK nor the trigger, so the suite proves nothing here.** |
| `P3.7` | db | `payments.corrects_payment_id` — a self FK, the mirror of `reverses_payment` | **DONE `a34053b88`** — `payments/0037`. `reverses_payment`'s declaration exactly, verified by reading `pg_constraint`/`pg_attribute` back. **NO unique constraint** — a payment is reversed once and may be corrected repeatedly (`payments/0014`), so copying `uq_payments_full_reverses` across would re-create the failure CS-34 removed. **`ix_payments_corrects`** `(tenant, corrects_payment)` carries the reverse walk instead. The column is frozen the day it was created — proved. |
| `P3.8` | db | **No change to the allow list.** `payments/0014` is the only place it moves and it moved once, for three columns. Cancel writes a status and a new row; it does not widen immutability | **DONE `ddf29e41e`** — no change; the deliverable is **`G131`**. It reads every `mutable`/`stamps` array in every `payments_payment_immutable()` body (38 files, 9 bodies, 14 arrays) and **FAILS on a fourth name**, and on the bypass (arrays untouched, the branch that consults them removed). Keyed on CONTENT, not the filename: `payments/0033` declares both arrays too, byte-identically, so a filename check would have been wrong the day it was written. Proved RED **six ways through the `run_gates` registry**, and its self-test is part 0 of every run. The DEPLOYED arrays were also read back from `pg_proc.prosrc` and match `payments/0014` exactly. |
| `P3.9` | front end | Screen 2·2 becomes **a page** — its own address, the header strip, the history panel | **DONE `f75b634e3`** — `PaymentDetailPage` at `/:tenant/payments/PMT-…` (the NUMBER, B14 rule 31). Built from **p035 read as an IMAGE**: the head with its four actions, the four-cell header strip, the eleven facts and the two-column bill table **moved from the row panel unchanged**, and ⑦ the history off `GET /payments/{id}/history`. ⚠ **THE ADDRESS COLLIDED WITH `payments/:tab` AND THE FAILURE WOULD HAVE BEEN SILENT** — `paymentsTabFrom` answers an unknown segment with `summary` and never 404s, so a pasted link landed on the Summary tab with nothing saying so. `PaymentsSegmentRoute` decides it in one named function; no existing address changes behaviour. **MEASURED IN CHROMIUM AT 1440 AND 1280:** title **32px** (rule 40) · all five head controls LIVE, `Cancel` alone danger-tiered · strip reads *SOURCE Counter · BATCH CTR-260921-DW · RECONCILED **DEP-260921-CHK** · STATUS Processing* · no uuid on screen · no sideways scroll · 91 words on the page. ⚠ **THE DRAWN `BRM-2609-0041` IS NOT BUILT** — B14 rule 37, a drawn figure is an illustration; this product mints no such series (`OQ-PAY-12602`), so the cell shows the batch's own `DEP-` code and states the absence. |
| `P3.10` | front end | **Delete the row panel in the same commit.** Not before — no way to see what a payment paid off. Not later — two answers to one question | **DONE `f75b634e3`, IN THE SAME COMMIT AS `P3.9`** — `paymentDetail.tsx` and its test are DELETED, `renderExpanded` is gone from the payments config, and the 👁 is a `RowActionLink` (a real link, so middle-click and open-in-new-tab work). ⚠ **THE 👁 WAS NOT A FREE ADDITION.** p030 ⑥: *"👁 Detail · ✎ Edit, then `…` for Receipt and Cancel · **B14 15 caps visible icons at TWO**"*. The visible pair was `✎` + `↺`, so adding the eye would have made THREE — a new rule 15 breach introduced by a fix for something else, and `G37` counts these into a variable it never compares to the cap. **Reverse moved into the `…`**, which SUPERSEDES `DEF-PAY-6214`'s choice of which two stay: that choice was right on 2026-09-22 and was made when the 👁 could not exist. **No capability left** — `moveAndReapply.dom.test.tsx` asserts all three are still one press away. The identity column is a LINK now too, cashing the promise `paymentDetail.tsx` made in its own words: *"it becomes an `InlineLinkAnchor` the day the route exists"*. |
| `P3.11` | front end | Cancel, Correction, Resend — three modals, **consequence boxes on all three money forms**. ⚠ §1.3 applies to the Correction copy | **DONE `f75b634e3`** — three components (rule 43), not inline. **Cancel** 2·3d: ① state and age first, ② Why\* from the server's four reasons, Note, ③ *"$158.10 leaves Ana Alvarez's account. BL-2609-000085 re-opens."*, footer **Keep it · Cancel payment** in the danger tier. **Add a correction** 2·3c: the `+ Noun` creator on the existing record path with `type=adjustment`, ① *"This does not change PMT-…. It writes a new row instead."*, signed amount, ③ *"…will owe $8.10 more."* **Resend** 2·3h: chips (rule 9), and `copy_no` **echoed from `next_copy_no`, never computed** (hard rule 6 — a `+ 1` here posts two receipts). ⚠ **THE RULE-33 TRAP IS HANDLED BY SILENCE.** No modal and no panel says one word about retention — measured in Chromium, zero matches for *retention · audit trail · pruned · for ever · permanent* on the page and on all three modals. ⚠ **TWO KIT GAPS FOUND AND FIXED THE RULE-36 WAY, NOT HAND-ROLLED:** `FormModal.cancelLabel` (optional — without it 2·3d's footer reads *Cancel · Cancel payment*, two buttons whose first word is the same meaning opposite things on the one form that destroys money) and `FieldLabel` exported (`ChipMultiSelect` renders its label only as an `aria-label`; `DEF-SHL-6250`). |
| `P3.12` | front end | The reversal commit moves tier — it renders like Save today while the row action that opens it is already danger-tiered. **The warning is on the act, not just the door** | **DONE `2134150246aad313d90a67f9c5f2750acf518a45`** — `ReversePaymentModal` passes `submitVariant="danger"`. ⚠ **THE DIAGNOSIS ON p46 IS EXACT AND WORTH KEEPING:** `WorkingButton` has taken a `CommitTier` since `DEF-712`, `FormModal` threads `submitVariant` straight through, and **the string did not occur anywhere in `PaymentsPage.tsx`** — all three payments modals passed none. **MEASURED IN CHROMIUM AT 1440, RENDERED OUTPUT (law 6):** the `Reverse payment` commit is now `color rgb(168,22,0)` · `background rgba(0,0,0,0)` · `border rgb(224,52,26)` — outlined red at rest. **THE CONTROL IS THE NEIGHBOUR:** `Save correction` still measures `bg-accent text-bg border-transparent`, deliberately — the drawing says *"Not danger tier — it moves no money by construction"*, so this proves the tier is a CHOICE and not a sweep. The row action keeps its own `danger`. |
| `P3.13` | test | Cancel by status — succeeds on `processing`, refused on `cleared`, and the clerk is pointed at Reverse | **DONE `d8bcee58b`** — ⚠ **THE TWO HEADLINE SENTENCES WERE ALREADY BUILT AND ARE NOT DUPLICATED.** `tests/test_cr137_p3_detail_cancel_receipt.py::test_a_processing_payment_cancels_and_the_money_comes_off_by_a_new_row` and `::test_a_cleared_payment_is_refused_and_told_to_reverse` (lane P3-BACK, `e9cc747c5`) already assert both, the second one word for word. **What was missing is the other four fifths of the vocabulary and the other half of the rule.** `tests/test_cr137_p3_wave2_status_correction.py` adds: **every one of the SIX statuses has exactly one stated cancel answer**, anchored on `len(PAYMENT_STATUSES) == 6` and a hand-written table compared to the tuple AS SETS (`paymentStatusParity.test.ts`'s precedent — *a loop is green on a list that has silently shrunk*; proved RED by deleting `cancelled` from the tuple: `assert 5 == 6`); and **only the `cleared` refusal may name Reverse** — Reverse itself requires a cleared row (`US-PAY-009` TC-5), so a `failed`, `reversed` or already-`cancelled` clerk sent there is refused twice. Proved RED by appending *"Use Reverse on this payment."* to the generic refusal. Plus one ENDPOINT case, because everything else here unit-tests a pure predicate. **SQLite.** |
| `P3.14` | test | The trigger refuses a cancelled UPDATE, **and still permits the three amendable columns** | **DONE `d8bcee58b`** — **`10-scripts/p3_cancel_state_and_trigger_readback.py` gains `§8`, on real PostgreSQL 16.** ⚠ **§4 AND §6 ALREADY PROVED THE TASK'S OWN SENTENCE** (freeze both ways; the three columns permitted on a cancelled row and a fourth refused), so §8 asks the question they do NOT: **the statement the SERVICE actually issues.** `amendments.amend_reference` writes `save(update_fields=[<column>, "updated_at"])` — TWO columns in one statement — and §3 already showed a two-column statement mixing a permitted column with a forbidden one is REFUSED, so *"the three are permitted"* and *"the correction endpoint works on a cancelled payment"* are different claims. All three succeed, `purpose` and `amount` are refused, and the CONTROL — `confirmation` + `amount` together — is refused. **Proved RED against the LIVE database** (the deployed trigger body rewritten). ⚠ **AND THE FIRST RED PROOF FAILED TO GO RED, WHICH IS NOW A NOTE IN §8: a CANCELLED row is governed by the `stamps` array, not by `mutable`** — removing `confirmation` from `mutable` alone leaves every §8 permit green, and a lane checking this proof that way would conclude it cannot fail. A suite case also pins `len(AMENDABLE_FIELDS) == 3` on SQLite and says plainly that it proves the SERVICE and not the trigger. |
| `P3.15` | test | A correction leaves the original **byte-identical**, and `corrects_payment_id` points at it | **DONE `d8bcee58b` — AND THE SECOND HALF CANNOT BE TRUE TODAY, WHICH IS THE FINDING.** ⚠ **`payments.corrects_payment_id` IS A COLUMN NOTHING WRITES (`DEF-PAY-6259`).** `payments/0037` added it and proved it against `pg_constraint`; `models.py` declares it; **measured 2026-09-23 the strings `corrects_payment`/`corrects_payment_id` occur in `06-backend` ONLY in that migration and that model, and in `07-frontend` not at all.** `record_payment` takes `moved_from_payment_id` and has no parameter for it; `AddCorrectionModal` posts `type=adjustment` carrying no reference to the payment it corrects. Hard-won law 2 on a money path, invisible to every check because an absence is. **The half that IS true is proved** — a real adjustment through the real record path, every CONCRETE COLUMN of the original compared before and after, and the new row asserted in the same case so *"nothing moved"* cannot pass on a build that wrote nothing. **The half that is not is a HOLD-EXPIRY TEST** (law 2's own cure): it asserts the column exists and is NULL today and goes RED naming `P3.15` the day anything writes it; proved red by making `record_payment` set it. ⚠ **AND A SECOND LIVE DEFECT CAME OUT OF IT — `DEF-PAY-6260`: `record_payment` refuses EVERY negative amount by name**, so 2·3c's signed `−8.10` — the blueprint's own worked figure, its note ② *"the sign is the whole meaning"*, and the shipped modal's `takesMoneyBack` branch — **cannot be submitted at all**, and the refusal a clerk sees is a true sentence about REVERSALS. Pinned by a case asserting the WORDS. **SQLite.** |
| `P3.16` | test | The reversal commit carries the danger class — B14's own record names a `FormModal` commit as the unchecked case | **DONE `d8bcee58b` — AND IT DID NOT ALREADY EXIST.** ⚠ **THE WAVE-1 REPORT THAT IT WAS COVERED IN `paymentDetailPage.dom.test.tsx` IS WRONG, AND THE MISTAKE IS WORTH NAMING: that file's case asserts the class on the CANCEL modal's commit** (`P3.11`'s component), not on the REVERSAL's. **Measured across the whole of `07-frontend/src`: `border-danger-500` is asserted on a rendered commit in eleven files and on NO `ReversePaymentModal` anywhere**; `reversePayment.test.tsx` — 33 cases, the file that owns this modal — contains the string `danger` **zero** times. So `P3.12`'s one-line change shipped with no test, and `PaymentsPage.tsx` says so beside it in its own words: *"`P3.16` is the test that closes it."* Now closed in `07-frontend/src/features/payments/dangerTierAndTheSwap.dom.test.tsx`: the RENDERED class off the DOM node, **and the CONTROL in the same case** — `Save correction` must NOT be danger, so a build that reddened every commit in the product fails. Proved RED by removing `submitVariant` from the modal. |
| `P3.17` | test | The swap cannot half-land — the panel is gone **and** the page is present, in one test | **DONE `d8bcee58b` — AND WHAT EXISTED WAS WEAKER THAN ITS NAME, TWICE.** `paymentDetailPage.dom.test.tsx` has a describe block titled *"P3.10 — the swap cannot half-land"*, and (1) its three cases are the panel half, the link half and the icon cap — **each in its OWN case**, so neither is satisfied by the broken state the other names, which is the whole point of *in one test*; and (2) its page half mounts `PaymentDetailPage` under a hand-written `<Route path="/:tenant/payments/:paymentRef">` **that the application does not have** — `App.tsx` mounts `PaymentsSegmentRoute` at `payments/:tab`. **A test that declares its own route pattern is testing its own fixture**, which is law 7's *looking at the wrong thing*, recorded in CLAUDE.md as a hold-expiry test asserting a screen was registered where the router mounted it elsewhere. The new case does both halves at once and reads the REAL `APP_ROUTES` — the full pattern `/:tenant/payments/:tab`, and the element compared by IDENTITY — plus a second case mounting through `PaymentsSegmentRoute` itself. ⚠ **AND PROVING IT RED FOUND `DEF-PAY-6261`: `P3.10` removed the expander's CALLER and left its SEAM** — `paymentsTableConfig` still threads `renderExpanded: extras.renderExpanded`, so declaring one at the top of the returned object left every case green. Re-adding the row panel is a one-line caller change nothing would refuse. Filed rather than fixed: `PaymentsPage.tsx` is ~4,000 lines under six phase-2 lanes (law 11). |
| `P3.18` | other | ⚠ **THE QUESTION IS ANSWERED (§1).** What remains is the propagation: `amendment_history_retention_unruled`'s key and sentence, and `CR-059` task 42's S35 copy | **DONE `2134150246aad313d90a67f9c5f2750acf518a45`** — and it had a **THIRD surface neither §1 nor the decision log named**. (1) The `unavailable[]` code is **RENAMED** `amendment_history_retention_unruled` → **`amendment_history_is_not_a_permanent_record`**, sentence rewritten to say the row IS pruned. (2) `CR-059` task 42's S35 copy was **`CorrectionRetentionNote` — a live `<details>` on the Correct-reference form AND its result panel, in all eleven catalogues**, saying *"Whether these are kept for longer has not been decided."* **DELETED, not reworded** (B14 rule 33: rationale is REMOVED, never SHORTENED — a corrected disclaimer keeps the breach). Keys retired through `10-scripts/i18n_fanin.py`'s `retire`. **MEASURED IN CHROMIUM:** `<details>` count on the modal **0**, no retention/audit-trail/permanence word anywhere on the card, rule 11's box intact at *"This payment keeps its money. Only the reference details change."*, 40 words on the whole modal. ⚠ **`CR-059` TASKS 41 AND 42 IN `11-change-requests.md` ARE SUPERSEDED BY THE DECISION-LOG ROW OF 2026-09-23 AND NOT AMENDED IN PLACE** — `push_register_guard.py` compares that file WHOLE-LINE, so an in-place row rewrite reads as a vanished line every time. **`DEF-GOV-6233`** filed; not switched off. |
| `P3.19` | other | **Paper at the window** — the queue is asynchronous; a counter needs a receipt **in hand now**. A counter customer leaves with paper | DONE e9cc747c5 — `GET /payments/{id}/receipt/document` renders the ALREADY-QUEUED `pdf_print` row through notifications' own `render_for_dispatch`, from the PINNED version (BR-BIL-026). **It is a READ**: A11 r2 §4 forbids a synchronous send endpoint anywhere, and this mints none — the queued row is untouched and the print job still takes it, asserted by COUNTING the rows before and after. TEXT, not a PDF (`OQ-149`). Reasoning in the decision log, because the drawing does not settle it |
| `P3.20` | e2e | `J-PAY-put-it-right` — four ways one payment goes wrong in one walk: a mistyped cheque number · a wrong amount · taken in error · a bounce a week later. **Four acts, and only the first writes in place** | **DONE `d8bcee58b`** — `08-qa/01-e2e/journeys/JPAYPUTITRIGHT-four-ways-one-payment-goes-wrong.md`, six steps on one payment (`PMT-2609-000418`, `$158.10`): correct-reference · correction · cancel · reverse · **the FORK asserted in both directions** · invariance. ⚠ **THE ID IS NOT `J-PAY-put-it-right` AND COULD NOT BE.** `G12`'s `VALID_JOURNEY_ID_RE` is `^[JT][A-Za-z0-9]*(?:-\d+)?$`, so a hyphen after `J` fails it, the gate falls back to guessing an id from the filename, and a spec could never be matched to the journey (check 3 matches BY FILENAME). `JPAYWRONGACCT` is the precedent, renamed on 2026-09-22 as one of `DEF-QAE-6208`'s eight; this file is named for its id from birth. **NOT ACTIVATED — no `.spec.ts`**, and the honest reason is narrower than *"the stories are not all built"*: **step 2's own link is not made** (`DEF-PAY-6259`), and a journey first seen green is a journey nobody has proved. The wiring index is regenerated in the same commit. |
| `P3.21` | e2e | `J12-nsf-life` regression — the bounce path, which the tier change touches | **DONE `d8bcee58b`** — two cases in `dangerTierAndTheSwap.dom.test.tsx`, walking J12 step 2 (*Aug 3 — the bank returns the cheque*) through the modal `P3.12` retiered. ⚠ **THE REGRESSION A TIER CHANGE CAUSES IS A DEAD COMMIT, NOT AN UGLY ONE:** `submitVariant` reaches `WorkingButton`, which is the component that owns `type="submit"`, so a tier that swapped it for a plain `<Button>` would render perfectly and submit nothing — and **every one of `reversePayment.test.tsx`'s 33 cases renders this modal and none presses its commit.** So the walk DRIVES it: the reason a clerk gets by touching nothing is still `nsf`, the bank's return date is required and never pre-filled (BR-PAY-021), and the POST body is read off the client. **The CONTROL is the second case** — submit with no date and the schema must refuse and post NOTHING, because a commit that posted whatever it was given passes the happy path just as well. Both proved RED by changing `FormModal`'s commit to `type="button"`. |

---

## 5 · What the drawing says — read as IMAGES, so the next lane need not re-render it

**Written by lane P3-PAGE, 2026-09-23, when `P3.9`/`P3.10`/`P3.11` blocked on `P3.1`.**
B14 rule 42 says a screen is built from the drawing AS AN IMAGE and the extracted
text is only an index. The pages below were rendered at scale 2.0 and read as
images; this section is the INVENTORY taken off them, not a substitute for
looking.

⚠ **THE BLUEPRINT IS NOT ON THIS BRANCH.** `05-prototype/06 Payments Page
Blueprint.pdf` (109 pages) lives on **`origin/claude/confirm-understanding-3ktufc`**
and on no other ref. Get it out without switching branches:

```
git show "origin/claude/confirm-understanding-3ktufc:05-prototype/06 Payments Page Blueprint.pdf" > /tmp/pay.pdf
python3 10-scripts/pdf/pdf_render.py /tmp/pay.pdf <outdir> 2.0 30,35,36,37,40,42,43,44,46,49
```

⚠ **AND THE PAGE NUMBERS IN THE WAVE-1 DISPATCH WERE WRONG.** The dispatch said
the modals were on *"p37–40"*. **They are p40–p50.** The real map:

| What | Pages |
|---|---|
| Phase 3 task table | **19–20** |
| 2·1 the list | **30–34** |
| **2·2 the payment detail** | **35–36** |
| 2·3a Record | 37–38 |
| 2·3b Edit the reference (the modal that ships today) | **39–41** |
| **2·3c Add a correction** | **42–43** |
| **2·3d Cancel** | **43–44** |
| 2·3e Reverse (the tier, `P3.12`) | 44–46 |
| 2·3f Move · 2·3g Reapply | 46–49 |
| **2·3h Resend** | **49–50** |
| §4 *what it changes* — every act and where it lands | 50 |

### `P3.9` · Screen 2·2, as drawn on p35

**Head** — kicker `PAYMENTS › PMT-2609-000418` · title **`PMT-2609-000418`** at
32px (B14 rule 40) · subtitle `$158.10 · Cheque 4471 · taken 09/21/2026 11:42 by
Dana Whitfield`. ⚠ **B14 rule 31: the title is the payment NUMBER.** The address
may carry the uuid; the screen never shows it.

**Actions, right-aligned, in the drawn order:** `Edit` ② · `+ Correction` ③ ·
`Cancel` ④ **in the danger tier** · `↓ Receipt`. ② and ③ *"look like one thing
and are two, and hard rule 4 is what splits them"* (p36): Edit writes IN PLACE
and only the three allowed columns; + Correction cannot touch the payment at all
and writes a new row, so B14 rule 4 gives it `+ Noun`.

**Header strip** — four cells, rule above and below: `SOURCE` → *Counter* /
*Dana Whitfield · Main counter* · `BATCH` → *CTR-260921-DW* / *Attached when
taken* · `RECONCILED` → *BRM-2609-0041* / *Three batches, one credit* ·
`STATUS` → *Cleared*.
⚠ **`BRM-…` IS A REFERENCE THIS PRODUCT DOES NOT MINT** — that is `OQ-PAY-12602`,
raised by P3-BACK, and B14 rule 37 already settles the screen half: **a figure
drawn in a wireframe is an illustration, never a fact to build to.** Show what
the read serves (the deposit batch's own `DEP-` code), never an invented series.

**Panel *This payment*** — the **eleven facts, in the JSX's own order**: Account
(a link) · Customer · Amount · Status · Type · Purpose · Method · Reference ·
Posted · Cleared · Memo. Then a table with **exactly two columns**, `BILL` and
`APPLIED`. **All eleven stay and the bill table is kept exactly** (p36) — they
MOVE from the row panel, they are not rewritten.

**History panel** ⑦ — `WHEN · WHAT · WHO · NOTE`, read from `audit_log`
(`P3.4`). *"It is what makes ④ honest"* — a cancelled payment does not vanish.

**States, drawn (p36):** a payment that met no bill draws **a named absence**,
not an empty table — *"a carried credit, or money that has not cleared"* · a
null clearing date renders **"Not cleared yet"**, NOT the dash a genuinely
absent field draws, because `processing` is a state and not a missing value · a
released allocation appends *released by correction* or *released by reversal*.
**Four different dashes for four different facts:** *No contact recorded · No
instrument · Not cleared yet · No account number*.
**Rules cited on the page:** B14 4 · 6 (④ is danger tier) · 31 · 33 · hard rule 4.

### `P3.10` · what goes, and what it costs

**2·2r Row panel — REMOVE · S33 · PAY-H**, `renderExpanded → PaymentDetailPanel,
paymentDetail.tsx:93 — no address`. **Consumers, greped (`DEF-CUS-3653`'s
lesson — an absence is invisible to every check here):** `PaymentsPage.tsx:149`
imports it, the table config's `renderExpanded` renders it, and
`paymentDetail.test.tsx` covers it. **Three, and nothing else in the repo names
it.**

⚠ **THE 👁 IS NOT A FREE ADDITION — READ p30 ⑥.** The drawing's own note is
*"👁 Detail · ✎ Edit, then `…` for Receipt and Cancel · **B14 15 caps visible
icons at TWO**"*. Today the visible pair is `✎ Correct` + `↺ Reverse`. **Adding
the eye makes three**, which is a NEW rule 15 breach — so **Reverse moves into
the `…`** beside Move and Reapply, exactly as drawn. Cancel and Resend each want
**two doors**: the page, and the row overflow (p44, p50).

### `P3.11` · the three modals, field by field

**2·3c Add a correction** (p42–43) — kicker `CORRECTING PMT-2609-000418`, title
**Add a correction**. ① a banner said *before anything else*: **"This does not
change PMT-2609-000418. It writes a new row beside it."** Then Account
(read-only, *"Taken from the payment. Not editable."*) · **What is wrong** * ·
**Correction amount** * (`−8.10`, help *"Negative takes money back."* — ② *"a
correction can go either way, and the sign is the whole meaning"*) · Posting
date * · Apply to · **Why** * . ③ the rule-11 box, in the customer's terms:
**"Ana Alvarez will owe $8.10 more."** / *"BL-2609-000085 re-opens at $8.10."*
Footer `Cancel` · `Add correction`. **No new endpoint** — the record path with
`type=adjustment`.

**2·3d Cancel** (p43–44) — kicker `PMT-2609-000418 · $158.10 · TAKEN 11:42`,
title **Cancel this payment**. ① state and age first, because the control
behaves differently by status: *"Taken 40 minutes ago, in your open counter.
**Nothing has cleared.**"* · ② **Why** * (required, B14 10) · Note (*"What
happened, in your words."*) · ③ **"$158.10 leaves Ana Alvarez's account."** /
*"BL-2609-000085 re-opens at $158.10."* Footer **`Keep it`** · **`Cancel
payment`, danger tier**. ⚠ **CANCEL IS NOT REVERSE** — *"Cancel is for money
that never cleared … Reverse is for money that arrived and went back"*, and the
drawing's ruling is **one control, and the product chooses by status**. See
`OQ-PAY-12603`: a counter cash payment is `cleared` the same minute, so at a
window this reaches Reverse — put to the PO, not settled in code.

**2·3h Resend** (p49–50) — kicker `PMT-2609-000418 · ANA ALVAREZ`, title **Send
receipt again**. ① *"Sent 09/21 11:42 by email and text."* · ② **Send by** * as
**removable chips + an add control** (B14 rule 9): `Email ×` `Text ×`
`+ Add a channel ▾`, help *"Print goes to the mailing address."* · To
(`ana.alvarez@example.com`, *"From the account. Change it on the customer."*) ·
③ **"Queues two receipts."** / *"Nothing about the payment changes."* Footer
`Cancel` · `Send`. **Not danger — it touches no money.**

⚠ **THE RULE-33 TRAP, AND IT IS ALREADY SPRUNG ONCE.** §1.3 of this board says
the Correction screen says **nothing at all** about retention. The drawing's own
*Fields* row for 2·3b still reads *"Then the retention disclosure"* — **that is
the sentence `P3.18` deleted**, and it is the clearest live example of B14 rule
41's exception: *the only thing that reaches the PO is a drawing that
contradicts a signed rule*. It contradicts two (rule 33's zero-rationale clause
and the ruling of 2026-09-23) and both are already settled, so it is **built as
silence and not re-asked** (law 13).

⚠ **AND THE DRAWN COPY EXCEEDS RULE 33 IN PLACES.** *"This is the only record of
the reason."* is 8 words against a FACT's cap of 6; *"It writes a new row beside
it."* is 7 against a CONSEQUENCE's 6-per-sentence. **Rule 38 says the UI rules
win on how a form is BUILT and the drawing decides what it CONTAINS**, so keep
the meaning and cut to the cap — *"The only record of the reason."* (6),
*"It writes a new row instead."* (6) — and say so rather than silently
following either one.

---

## 6 · What `P3.9`–`P3.11` found that the task table did not say

**Lane P3-PAGE, 2026-09-23.** Each of these was invisible to `tsc`, to every
suite and to every gate, and each was found by one of the two things this repo
has no tool for: **reading the drawing as an image, and opening the page in a
browser.**

| Found | How | Where it went |
|---|---|---|
| ⚠ **`PAYMENT_STATUSES` listed FIVE while the database accepted SIX.** `paymentStatusLabel` resolves `payments.status.${status}` and `t()` returns the KEY on a miss — so **a cancelled payment's pill would have rendered the literal string `payments.status.cancelled`**: a missing word AND a B14 rule 31 breach, on the one row the whole of phase 3 exists to create | Raised by the coordinator, verified against `models.py` and the catalogue | Fixed, plus **`paymentStatusParity.test.ts`** — a COUNT, because a loop over the list is green on a list that is too short. Proved RED at five. It is the `SignupWizard.test.tsx` precedent, for the same reason |
| ⚠ **The page's subtitle rendered `158.100000 · Cheque 4471`** — the raw four-decimal stored amount at the top of a money screen. **CLAUDE.md hard rule 2: display 2** | Chromium, at 1440 | `formatMoney`. `tsc` was happy and every suite was green on it |
| ⚠ **`3 batches, 1 bank lines`** | Chromium | i18next plural forms, `_one`/`_other`, in all eleven catalogues |
| ⚠ **The Cancel footer read `Cancel · Cancel payment`** — the kit's default dismiss word beside a commit called *Cancel payment*, on a destructive money form. The drawing solved it on p044 and there was no prop to build it with | Chromium, and then p044 | `FormModal.cancelLabel`, optional; the modal says **Keep it** |
| ⚠ **`ChipMultiSelect` has no visible label and no required marker** — every other caller borrows one from a surrounding `Panel title=…`, and a modal has no panel | Chromium, asking where the drawn *Send by \** was | `FieldLabel` exported and used; the deeper fix is **`DEF-SHL-6250`** |
| ⚠ **`GET /payments/{id}` serves no `methods[]`**, so Edit's tender picker had no vocabulary on this page | Wiring the Edit modal's second door | One `per=1` list read, only while that modal is open, stated at the call site. **`DEF-PAY-6251`** |
| ⚠ **`push_register_guard.py` refuses every in-place row amendment to `02-decision-log.md` and `11-change-requests.md`** — the identical false alarm `DEF-GOV-5737` removed for the open-questions register | The `P3.18` push | **`DEF-GOV-6233`/`6234`**, filed rather than switched off; `P3.18` appended a dated row instead |

⚠ **AND ONE RED THIS LANE DID NOT CAUSE, DATED (hard-won law 7).**
`cashTotal.dom.test.tsx` has **six** failures — `RecordCounterBanner`
(`CounterDoors.tsx:205`) calls `useTenantPath` with no Router — and they are
**pre-existing**: proved by running that file in a clean worktree at the tip
`b644b61a6`, where they fail identically. A sibling is already on it
(`DEF-PAY-6243`, and the tip commit is titled *"Two suite reds nobody was
reading"*). Not fixed here, and not reported as mine.

---

## 4 · Dispatch

**Wave 1, three lanes, dispatched 2026-09-23**, each in its own `git worktree`.

| Lane | Tasks |
|---|---|
| **P3-BACK** | `P3.1` · `P3.2` · `P3.3` · `P3.4` · `P3.19` |
| **P3-DB** | `P3.5` · `P3.6` · `P3.7` · `P3.8` |
| **P3-PAGE** | `P3.9` · `P3.10` · `P3.11` · `P3.12` · `P3.18` — **`P3.12` and `P3.18` DONE `213415024`; the other three BLOCKED on `P3.1`/`P3.2`/`P3.3`, with the full drawing packet left in §5** |

**Wave 2 — `P3.13`–`P3.17`, `P3.20`, `P3.21`** (five tests, two walks) follow as
their targets land. Each asserts behaviour wave 1 is still writing.

⚠ **PHASE 2 IS RUNNING IN PARALLEL** on the same branch with six lanes. The one
file all of them want is `07-frontend/src/features/payments/paymentsShared.tsx`.
**Re-derive it from the pinned tip at push time and read the numstat as
arithmetic** — a whole-file write there reverts a sibling invisibly (law 11).
⚠ **AND THE PAYMENTS MIGRATION CHAIN IS SHARED** — phase 2's `P2.4` adds a column
to `payments` while `P3.5` alters its CHECK. Check the real maximum before you
number a migration, and expect it to have moved.

⚠ **THAT WARNING CAME TRUE, AND THE FOUR DB TASKS RECORD WHAT IT COST.** `P2.4`
pushed `0035_cr136_…` while `P3-DB` was proving its own `0035`, so the two DB
migrations are **`payments/0036` and `payments/0037`** and `models.py` was
**re-derived from the pinned tip** rather than written over it — the numstat on
`a34053b88` shows 3 deleted lines, all of them this lane's own rewritten
comments. **A defect id went the same way:** `DEF-PAY-6222` was taken by the
lane that put the blueprint PDF on this branch while this lane held it in a
draft. Re-derive BOTH at push time, as one act.

⚠ **THREE THINGS FOR THE LANES STILL TO COME.**
**(1) `P3.9`–`P3.12`:** the sixth status exists in the database and the API
serves it, and the front end types the five **by hand in two places** —
`07-frontend/src/api/endpoints.ts`'s `PAYMENT_STATUSES` and
`paymentsShared.tsx`'s `PaymentStatus`/`paymentStatusTone` — plus a
`payments.status.cancelled` key in each of the eleven catalogues. **A cancelled
payment cannot render until those move**, `tsc` is green either way, and it is
`DEF-PAY-6233` rather than a sentence in this paragraph — a finding recorded
only in the file you happen to be in is a finding nobody can count.
**(2) `P3.2`:** cancel is reachable from `processing` and from nowhere else,
because the trigger refuses every UPDATE on a row that is past it. The service
does not need to enforce that — it needs to say it in words a clerk can act on
before the database says it in words they cannot.
**(3) `P3.14`:** the trigger behaviour it asserts is already proved on
PostgreSQL by `10-scripts/p3_cancel_state_and_trigger_readback.py`. **Read that
script before writing the test** — in particular why every statement in it is
raw SQL, which is the only reason its RED half can run at all.
⚠ **AND `P3.5` HAD A CONSEQUENCE NOBODY WOULD HAVE REVIEWED, WHICH IS WORTH
MORE THAN THE FIX (`DEF-PAY-6454`).** `PAYMENT_FROZEN_STATUSES` is DERIVED, so
the sixth status joined `payments.selectors.unapplied_cash` — the month-end
tie-out runbook 9 refuses to close against — **on a line nobody edited, in a
file nobody had to open.** A cancelled payment can never carry an allocation,
so it would have sat in unapplied cash for ever and overstated the figure.
Nothing had reached it, because no `cancelled` row exists yet. **The habit that
found it is CLAUDE.md's own, recorded for the opposite case: before RETIRING a
value, grep for its CONSUMERS. It runs the same way for ADDING one.**

⚠ **AND THE FIVE BACKEND TASKS ARE NOW PROVED, WHICH THE COMMIT THAT FILLED
THEIR ROWS COULD NOT SAY.** `a292c077c` landed this board carrying the sentence
*"the test suite for this lane's five has not completed a run in this
container"* — three attempts, two of them killed by the kernel OOM killer with
six lanes running `pytest` at once. **That sentence is now false and this is
what replaced it.**

`06-backend/tests/test_cr137_p3_detail_cancel_receipt.py` is **25 of 25 green
on BOTH databases** — 141s on the ordinary SQLite suite (`f1d20c01d`) and
**824s on real PostgreSQL 16** through `--ds=config.settings.pgtest --reuse-db`,
which is the repo's own answer to law 14 and which this lane found only after
building the database for it by hand. **Nine further checks are green on
PostgreSQL** through `10-scripts/p3_back_cancel_resend_pg_proof.py` (`69057b301`), under a
role that is neither a superuser nor RLS-bypassing — `rolsuper=False
rolbypassrls=False`, printed beside the figures, because a figure taken under a
bypassing role is not a claim. What only PostgreSQL could answer: the cancel's
own statement `save(update_fields=["status","updated_at"])` **passes
`trg_payment_immutable`**, the cancelled row is **append-only one statement
later** (the amount refused by the database, quoting BR-PAY-002 back in a
sentence a clerk could read), the reversing row is **`-158.1000` under its own
`PMT-` number and the pair nets to `0.000000`**, and the per-channel savepoint
was proved **RED first** — without it the same call dies on *"current
transaction is aborted, commands ignored until end of transaction block"*,
which is hard-won law 14's own symptom, verbatim.

⚠ **FOUR FAULTS CAME OUT OF THAT FIRST COMPLETE RUN AND ALL FOUR WERE IN THE
TEST FILE, NOT THE PRODUCT** — which is the argument for running a file before
pushing it rather than after. The one that matters is **`DEF-PAY-6249`**:
US-PAY-004 **TC-7**, the case proving another tenant's payment answers 404 and
not 403, named `priya` — a name taken from the story's Actors line, not from any
conftest — so `pytest` reported it as an ERROR at setup rather than a FAILURE
and **it had never executed once.** The others: two history cases came back
empty because `tests/test_us_met_helpers.py` installs an autouse sink that
redirects every audit row into a Python list (`AuditLog.objects.count()` was
**0 for the whole test database** — the read agreed with audit exactly, there
was simply nothing to read; `test_w6_connection_detail.py` sets the precedent
for the fixture that repairs it), and one case built two accounts with one
account number.

⚠ **TWO THINGS THE PROOF FOUND THAT NO TEST ASKED FOR, AND BOTH ARE ABOUT
READING A GUARD RATHER THAN ABOUT A BUG.** **(1)** The ordinary double-click
**never reaches the savepoint at all** — `notifications.services.queue_document`
finds its own row and answers `created: false`, so hard rule 6 is satisfied one
layer ABOVE the unique constraint, and a reader of `resend_receipt`'s savepoint
comment would reasonably assume the collision path is what exercises it. It is
not; the proof poisons the transaction deliberately instead. **(2)** No settings
module sets `ATOMIC_REQUESTS` and no view wraps, so **today each channel's
`atomic()` IS the transaction** — the guard is what keeps the behaviour correct
for the FIRST caller that wraps this call (a bulk action, a job), and the proof
runs under exactly that outer `atomic()`, which is the only shape in which the
question has an answer.

⚠ **AND TWO TOOLS THIS LANE HAND-ROLLED BEFORE FINDING THEM, WHICH IS CLAUDE.md
LAW 11'S CLOSING LESSON IN ITS CHEAPEST FORM — *read `10-scripts/`'s listing
first*.** `config/settings/pgtest.py` already exists and is how law 14 is met in
this repo (`--ds=config.settings.pgtest --reuse-db`; it fails closed on a SQLite
`DATABASE_URL` rather than reporting a green run that proves nothing), and
`10-scripts/proof-db.sh clone <label> --export` already clones a seeded template
in a fraction of a second and reads its stamp. ⚠ **Check the stamp: on
2026-09-23 the newest template stood at `payments/0034`, three behind, and §2 of
any cancel proof is meaningless below `payments/0036` because the sixth status
does not exist there.** Migrate the clone forward (seconds) or rebuild the
template.

---

## 7 · What wave 2 found — three live defects and two reds nobody had read

**Lane P3-TESTS, 2026-09-23.** Wave 2 was five test tasks and two walks. Writing
them found **more product faults than test gaps**, which is the argument for
writing the test before calling the feature done rather than after.

| Found | How | Where it went |
|---|---|---|
| ⚠ **`payments.corrects_payment_id` is a column NOTHING writes.** `P3.7` built it and proved it against `pg_constraint`; no lane owned WIRING it, so `P3.15`'s second half cannot be asserted at all | Grepping for the column's consumers before writing the assertion — CLAUDE.md's own habit, recorded for the opposite case (*before RETIRING a value, grep for its CONSUMERS*) | **`DEF-PAY-6259`** + a HOLD-EXPIRY test that fires the day it is wired |
| ⚠ **2·3c's negative correction cannot be submitted.** `record_payment` refuses every amount ≤ 0 BY NAME; the shipped modal offers a signed one and the blueprint's worked figure is `−8.10`. The refusal a clerk sees is a true sentence about REVERSALS | Posting the drawing's own figure through the real record path. **No test had ever posted a correction** | **`DEF-PAY-6260`**. ⚠ **WHICH SIDE IS WRONG IS NOT A LANE'S TO DECIDE** — `> 0` cites `A2 §S22` and hard rule 4, the drawing cites B14 rule 41. **A drawing contradicting a signed rule is the one thing that reaches the PO** (law 13) |
| ⚠ **`P3.10` removed the row panel's CALLER and left its SEAM.** `paymentsTableConfig` still threads `renderExpanded: extras.renderExpanded`, so the case named *"the payments table declares no expander"* is green with an expander declared | **The RED PROOF of `P3.17`** — declaring one at the top of the returned object left every case green, because the pass-through further down overrides it | **`DEF-PAY-6261`**, filed not fixed (`PaymentsPage.tsx` is ~4,000 lines under six lanes — law 11) |
| ⚠ **A CANCELLED row is governed by the trigger's `stamps` array, NOT by `mutable`** | The first red proof of `§8` **did not go red**: removing `confirmation` from `mutable` alone left every permit green | A note inside `§8`, so the next lane checking that proof does not conclude it cannot fail |
| ⚠ **A correction or an adjustment needs a SYSTEM ADMIN** — this utility's approval threshold is `0`, so the clerk who took the payment cannot correct its amount alone | Every `P3.15` case failing with the threshold refusal on a `billing_clerk` actor | Stated at the fixture in `test_cr137_p3_wave2_status_correction.py`, because it is what a correction actually costs at the counter |

⚠ **TWO REDS THIS LANE DID NOT CAUSE, DATED (hard-won law 7, habit 1).**
**(1) `G12` was FAILING at the tip** — `STALE: 01-journey-story-index.json/.md`.
Dated with `git log -S "US-NOT-011"`: **`e9cc747c5`** (2026-09-23, lane P3-BACK,
this same CR) added a Trace header citing `US-NOT-011`, which flipped `T7-06` to
story-ready and left the generated index one row behind. **Fixed here as a side
effect** — adding a journey requires regenerating it anyway.
**(2) AND FIXING THAT UNCOVERS SEVEN MORE, WHICH THE STALENESS WAS MASKING.**
`G12` short-circuits on a stale index, so its frontmatter check never ran. With
the index fresh it reports **seven journey files whose `id:` and filename
disagree** — `J-MVI-NINETEEN`, `J-MVO-TWENTYSEVEN`, `J-RBS-1/2/3`,
`J-REQ-CLERK-WALK`, `J-TRF-TWENTYFIVE`. **All seven are already `DEF-QAE-6208`**,
which is OPEN and whose own title says *"the stale index had been hiding it"*.
Last touched 2026-09-11 and 2026-09-19, by other lanes. **Not fixed here** — a
rename moves every citation — and **said out loud rather than left for the next
lane to read as new**, because a red that changes shape is exactly the kind that
acquires the protective colouring of a known one.
