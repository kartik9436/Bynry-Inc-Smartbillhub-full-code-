# `CR-135-BRC07` — payments blueprint phase 0: the source column's check, and the till table

**Raised:** 2026-09-22 · **Branch:** `claude/laughing-thompson-kpmwih` (`BRC07`)
**Version:** `2.329.0` · **Status:** BUILT, HUMAN-REVIEW-PENDING
**Classification:** BUILD (`12-engineering-plan.md` Addendum r11), not maintenance.
*Can a user do this task in the product today?* **No** — there is no counter
session anywhere in the product, and no payment column carries a CHECK. So it is
Build.

⚠ **THE NUMBER IS MINE AND `allocate.py --verify` SAYS OTHERWISE — READ THIS
BEFORE RENUMBERING ANYTHING.** `cr 135` was verified free on 2026-09-22, taken,
used in three migration filenames and pushed in `76c24705f`. On the next run
`allocate.py cr --verify 135` answered *"TAKEN — a sibling pushed it. Renumber
before you commit"* — **over this lane's own commit.** Every one of the six
files citing `CR-135` anywhere on the branch came from that push. The tool
detects that a number is in use on the remote and then names a cause it never
checked; renumbering on it would have orphaned three migrations that were
already applied to a database. Filed as `DEF-GOV-6198`. The check that settles
it is `git grep -l "CR-135" <each origin ref>`.

---

## 0 · WHAT ARRIVED

`05-prototype/06 Payments Page Blueprint.pdf`, **109 pages, on the DEFAULT
branch `claude/confirm-understanding-3ktufc`** and on no working branch. Phase 0
is **Foundations, 17 tasks**, and the document's own summary of it is *"Nothing
a clerk can see, and everything else waits on it … the only phase with no user
value."*

This CR is the DATABASE half: `P0.1`–`P0.5` and `P0.14`–`P0.17`. `P0.7`–`P0.13`
are the front end and settings, and `P0.6` is not started.

## 1 · CLASSIFY

Build. Nothing here reverses a signed statement, with **one exception**, stated
rather than assumed:

**`P0.3` draws the opening float as `NUMERIC(18,6)` and CLAUDE.md hard rule 2
says a NEW money column declares FOUR decimals** — PO re-sign 2026-08-22,
verbatim: *"We already confirmed this - MOney 4 decimal, percentage 6 decimal ,
display both 2 decimal"*. The signed rule wins and the column is
`NUMERIC(18,4)`. Put to the Product Owner and answered before this lane started;
**not re-asked** (CLAUDE.md hard-won law 13). It is B14 rule 38's shape — where
a drawing and a signed rule disagree about construction, the rule wins, because
the alternative moves a money column on one screen's authority.

## 2 · WHAT SIGNED STATEMENT IS REVERSED

None frozen. `B4`/`B5` are untouched — no rating figure, no golden test, no bill
line moves. `payments/0014`'s allow list is **not widened**, which CLAUDE.md
hard rule 4 names as the only place it may move.

## 3 · IMPACT

| Surface | What moved |
|---|---|
| Schema | `payments` gains two CHECK constraints; `counter_sessions` is created with RLS |
| Migrations | `payments/0030`, `0031`, `0032` — 🔒 migration ordering, 🔒 RLS |
| Models | `apps/payments/models.py` (`PAYMENT_ORIGINS`, `COUNTER_CLOSE_KINDS`, two constraints) · new `counter_session_models.py` · `apps.py` registers it |
| Tests | `tests/test_cr135_p0_foundations.py` · `tests/test_cr135_p0_rls_pg.py` |
| Open questions | none opened, none closed |
| Demo fixture | unchanged — no seed row is added, because phase 0 ships no screen to show one on |
| API | unchanged — no endpoint, no serializer, no OpenAPI change |
| Front end | **nothing**, deliberately. `counter · digital · post` are labels and belong in the i18n catalogue, which is LANE P0-FE's this phase |

⚠ **THE BLUEPRINT'S MIGRATION NUMBERS ARE ALL ONE LOWER THAN THE FILES.** `P0.1`
names `payments/0029` and `P0.3`/`P0.4` name `payments/0030`; `0029` was taken by
`CR-132-BRC07` on the morning of 2026-09-22, so this work is `0030`–`0032`.
Recorded because a lane reading the document and then the tree will otherwise
think a migration is missing.

## 4 · WHAT IS ALREADY BUILT AND IS NOW WRONG

**Nothing is now wrong, and one thing was already wrong.**
`payments/0029`'s docstring names **four** places a payment row is created;
there are **six**, and the sixth
(`apps/integrations/management/commands/seed_partner_morning.py:232`) writes no
origin at all. Filed as `DEF-PAY-6196` and NOT fixed here — the rows are demo
data, and what is wrong is the record rather than the money.

**Lanes building right now:** LANE P0-FE holds `07-frontend/` and
`apps/tenancy/`; this CR touches neither. LANE P0-BATCH was working `P0.6` and
read `counter_sessions` as evidence on an open question about whether a deposit
batch is one session or one session and one tender — **that table is evidence
and is not changed on the strength of it**; the question is with the Product
Owner.

## 5 · SIZE, IN PLAIN ENGLISH WITH A FIGURE

Three migrations, one new table, two new constraints on an existing one, and two
test files. **No screen and no endpoint**, so nothing a clerk does changes
today. The one visible-to-anybody consequence is that a payment can no longer be
recorded with a fourth word for where it came from — and nothing in the product
writes one.

## 6 · EXECUTE

Through r11, unchanged. The decision log of 2026-09-22 carries the four
judgments and what was measured for each; the human-review ledger carries what
would be put to the Product Owner.

## 7 · VERSION

**`2.329.0`** — `<release>.<change>.<fix>`, the CHANGE digit, because this is
new capability rather than a fix.

## 8 · CLOSE, AND THE ROLLBACK STATED BEFORE SHIPPING

**Rollback:** `migrate payments 0029` drops `counter_sessions` and its RLS
policy entirely and removes the two CHECK constraints from `payments`. The 74
demo payment rows keep the origin and the *is a guess* marker they already had.
**Proved on a PostgreSQL 16 clone: forwards, backwards, forwards again, with
`trg_payment_immutable` reading `'O'` at every stage.**

⚠ **`P0.16` IS NOT CLEARED BY THAT.** Its task line is *"migration forwards and
backwards"* and its OUTCOME is *"The deposit re-key is reversible"* — which is
`P0.6`'s migration. `P0.6` is not built, is blocked on two Product Owner
decisions and is not this lane's, so **`P0.16` stays OPEN**. Writing a test that
proved a migration nobody has written reverses would be a check that cannot
fail.

### DEFECTS FILED BY THIS CR

| Id | What |
|---|---|
| `DEF-PAY-6196` | a sixth Payment creation site states no origin, where `payments/0029` counts four |
| `DEF-PAY-6197` | this CR's own — `payments/0030` shipped a PostgreSQL-only `UPDATE` alias, SQLite refused it, and every backend test on the branch errored at setup for about thirty minutes |
| `DEF-GOV-6198` | `allocate.py --verify` blames a sibling for a number the asking lane pushed itself |

---

# WAVE 2 — `P0.6`, THE DEPOSIT-BATCH RE-KEY (LANE P0-BATCH-3, 2026-09-22)

**`2.330.0`.** The last task of phase 0's database half, and the one the first
lane on it **refused to build and was right to refuse**: it raised three
questions rather than guessing, all three have since been answered by the
Product Owner, and this wave builds the answers.

## WHAT A UTILITY CAN DO NOW

At a two-counter office on 22 September, Dana takes **$1,240** of cheques and
Sam takes **$880**. That was **one** deposit for the whole utility, which
neither clerk could be held to. It is now **two**, and the day still ties to
**$2,120**.

## THE FOUR RULINGS, AND WHAT EACH BECAME

| PO ruling (verbatim) | Built as |
|---|---|
| *"(a) Payments and ledger together"* | one piece of work across two modules — and the ledger needed **no change**, proved rather than assumed |
| *"d) Tell them apart by what they lack"* | a PARTIAL key, `WHERE session_id IS NOT NULL`, plus a trigger so nothing joins the legacy population |
| *"we have to make process uniform for all hence we should geneate system generated till"* | a system till that is openly nobody's, born closed, one per tenant per banking day |
| *"(b) Put it in Settings today — DEP-260922-0001 — Settings → Numbering"* | the code ALLOCATED from the `deposit_batch` series, which already existed |

## 7 · VERSION

**`2.330.0`** — the CHANGE digit again; `P0.1`–`P0.5` and `P0.14`–`P0.17`
shipped at `2.329.0`.

## 8 · CLOSE, AND THE ROLLBACK STATED BEFORE SHIPPING

**Rollback:** `migrate payments 0032` drops `session_id` and the partial key,
restores `uq_deposit_batches_day_method`, drops `trg_deposit_batch_needs_session`,
and restores `payments/0005`'s and `payments/0014`'s trigger wording verbatim.

⚠ **IT IS REVERSIBLE ONLY WHILE NO BATCH HAS BEEN CUT ON THE NEW SHAPE**, and
that is said out loud rather than discovered later: restoring the day × method
key over two tills' batches for one day would be refused by the index itself.
Deposits already cut keep their allocated codes — the reverse of an allocation
is not a restoration, because the series counter does not roll back.

⚠ **`P0.16` IS NOW UNBLOCKED AND IS STILL NOT THIS LANE'S.** Its outcome —
*"The deposit re-key is reversible"* — is about `payments/0033`, which now
exists. **LANE P0-DB can take it**, and the paragraph above is the honest
statement of what it will find.

### WHAT THIS WAVE DID NOT DO

* **No data migration**, which `P0.6`'s task row asks for. The PO ruled the
  opposite four hours after the drawing was read: nothing is written to a batch
  already banked. The absence is the fact.
* **No `payments.counter_session_id`** — phase 2's, with the screens that open
  and close a till. Until then every tender banks under the day's system till,
  which is honest rather than a stand-in: no drawer has ever been counted in
  this product.
* **No new CR, defect or business-rule id.** Reasoned in
  `12-governance/14-id-reservations.md`.

### ONE THING THIS WAVE CORRECTED IN A GOVERNANCE DOCUMENT

The row closing `OQ-PAY-12575` says a two-digit counter *"reaches
`DEP-260922-99` and then cannot allocate at all"*. **Measured: it renders
`DEP-260922-100`.** `render` never truncates and `will_overflow` is a
Settings-screen warning that refuses nothing. The four-digit pad was still
taken, because `DEP-260922-0001` is the number the PO wrote; the **yearly
restart** proposed on the same false premise was **not**, because it would put
`numbering_restart_backdated` on the banking path.

---

## 9 · `P0.15`, `P0.16` AND `P0.17` ARE CLOSED (lane P0-DB, `2.330.1`, 2026-09-22)

⚠ **THE TWO LINES ABOVE THAT SAY `P0.16` IS OPEN ARE SUPERSEDED BY THIS
SECTION** — §8's *"`P0.16` IS NOW UNBLOCKED AND IS STILL NOT THIS LANE'S"* and
the earlier *"`P0.16` stays OPEN"*. They were both true when written. Lane P0-DB
took it; this is what it found.

### `P0.15` — the constraint half was done, the backfill half was covered nowhere

And a docstring said it was covered, which is the expensive direction of the
mistake: the next lane reads *already covered* and writes no case
(`DEF-PAY-6206`, fixed). **Five cases now drive `payments/0030`'s own
re-derivation** rather than a re-typed copy of its SQL — a derived guess with an
import link is corrected and stays marked as a guess; an **observed** origin is
left alone; a NULL origin is filled in; a row with no link is untouched; and a
correctable row in **each of two tenants** is corrected, which is the case that
catches a pass that visits only the first tenant. **All five were shown to FAIL
first**, by breaking `payments/0030` one guard at a time.

### `P0.16` — the re-key reverses, and stops reversing the moment two tills have banked

`10-scripts/cr135_migrations_forwards_and_backwards.py` — **PASS**. Phase 0's
**four** migrations (`payments/0030`, `0031`, `0032`, `0033`) applied, reversed
to `0029` and re-applied on a private PostgreSQL 16 clone, with the payments
freeze on at every point and `payments.origin` untouched.

⚠ **AND §8'S ROLLBACK CAVEAT IS NOW PROVED RATHER THAN STATED.** *"It is
reversible only while no batch has been cut on the new shape"* is a claim about
a database, and a claim about a database is worth what a test of it is worth.
STEP 6 cuts exactly the two batches the sentence describes — **one banking day,
one tender, two tills** — and asks PostgreSQL to roll back. It refuses:
*could not create unique index `uq_deposit_batches_day_method` — DETAIL:
Duplicate keys exist.* The seeded rows are then removed, which needs
`trg_deposit_batch_lock` lifted and put straight back, because `BR-PAY-004`
refuses a DELETE on a deposit batch.

**That is a different question from `10-scripts/p06_rekey_readback.py` and from
`d1d281815`**, which reverse an EMPTY table and then show that the second batch
cannot be written. Those prove the consequence of a rollback that has already
happened; this proves whether the rollback can happen at all on a database that
has been used. **Both answers matter and they are opposite in shape.**

⚠ **What a proof naming four migrations cannot do is notice a fifth.**
`test_cr135_p0_foundations.py::test_p0_16_every_phase_0_migration_is_in_the_reversibility_proof`
compares that list with the migrations on disk, so a phase 0 migration landing
without being added turns the ordinary suite RED the day it lands.

### `P0.17` — no new journey, and the list our checks read was four journeys short

Phase 0 added no journey file and no browser spec. ⚠ **The drawing's `354` is a
FILE count and one of those files is `README.md`**, so the generator, `G12` and
the index all said **353** — B14 rule 37, a figure in a drawing is an
illustration. The index itself was two days stale and missing **four** journeys
(`DEF-QAE-6200`, now fixed). It reads **354** today because another lane added a
journey this evening, which is the second reason not to build to the drawn
number.

### WHAT THIS SECTION DID NOT DO, AND ONE OF THEM MATTERS

⚠ **`DEF-PAY-6207` — `payments/0033` switched `ck_counter_sessions_closed_together`
OFF, and it is FILED, NOT FIXED.** ⚠⚠ **FIXED 2026-09-22 by `payments/0034`,
`2.331.1`, LANE P0-BATCH-3 — whose migration it was. The paragraph below is
left as written because it is the measurement that found it, and because
deleting the record of how a guarantee was switched off is worth less than
keeping it. TWO constraints had this shape, not one:
`ck_counter_sessions_system_is_nobodys` had it too and is NOT in the filed
row — it was found by checking the neighbouring branches, and it accepted an
OPEN system till, which would have appeared on the *"which tills are open"*
screen. Both are refused BY NAME on PostgreSQL now, with all three lawful
shapes still accepted.** The new third branch begins
`close_kind = 'system'`. A CHECK refuses a row only when its expression is
FALSE and **passes when it is NULL**, so with `close_kind` NULL that branch is
NULL and the whole chain is `FALSE OR FALSE OR NULL` = NULL — **the row is
accepted**. Measured both ways rather than reasoned: PostgreSQL 16.13 accepted
an INSERT with `closed_at` set and `close_kind` and `closed_by` NULL, and a
SQLite probe of the same expression accepted it too.

**So a till can again be sealed with no record of how** — the exact outcome the
PO's forced-close ruling of 2026-09-22 exists to prevent. Nothing a clerk can
do reaches it today, because phase 0 ships no close service. The cure is one
clause — `close_kind IS NOT NULL AND close_kind = 'system'` — in `payments/0033`,
which belongs to lane P0-BATCH-3 and was in flight when this was measured, so it
is written down rather than applied.

**The general lesson is worth more than the fix: adding a branch to an OR'd
CHECK can only ever make it WEAKER, and a branch comparing a NULLABLE column to
a literal weakens it to nothing for every row where that column is NULL.**

### DEFECTS FROM THIS SECTION

| id | what | state |
|---|---|---|
| `DEF-PAY-6205` | three phase 0 files cited two test files that have never existed | fixed `d15efebf0` |
| `DEF-PAY-6206` | the backfill cases a docstring claimed existed | fixed `d15efebf0` |
| `DEF-PAY-6207` | the closed-together constraint switched off by a NULL comparison — **and a second constraint with it, found by checking** | fixed `payments/0034`, `2.331.1`, by the lane that owned the migration |
| `DEF-QAE-6200` | the journey index two days and four journeys stale | fixed `037fc6f39`, by a sibling |
| `DEF-QAE-6208` | eight journeys a browser spec can never be matched to, hidden by that staleness | **OPEN — customers / move / runbooks lanes** |

## 10 · VERSION

**`2.330.1`** — the FIX digit, because this section ships no new capability: two
defect fixes, one proof script and two test files. `07-frontend/package.json`,
`package-lock.json` and `06-backend/pyproject.toml` all read it, and
`CHANGELOG.md` carries the entry.

**Rollback for this section:** nothing here changes the product. Reverting it
removes two test files' worth of cases, one proof script and four corrected
Trace headers. No migration, no schema, no data.

---

# WAVE — `P0.7`–`P0.13`, THE FRONT END AND SETTINGS (LANE P0-FE, 2026-09-22)

**`2.332.0`.** The other half of phase 0. The database half above ships *"nothing
a clerk can see"*; this one is the only part of phase 0 a clerk does see, and it
is deliberately small: three doors that open onto a stated absence, two kit
pieces, a rule-11 box on three money forms, and one number series.

## WHAT A UTILITY CAN DO NOW

A clerk opening Payments sees the **seven tabs the blueprint draws**, in its
order, and every one of them opens. Three of the seven say plainly that they are
not built yet — which is what the Product Owner chose when the three options were
put to them. On the debtor list the **five ageing bands are cards that filter**
rather than figures that do not, and on the three money forms the product now
says **what the commit will do before the clerk presses it**.

## THE SEVEN, AND THE ARITHMETIC THE TASK TABLE DOES NOT STATE

`P0.8` reads *"It is four today … Every screen in §03 draws seven"*, which reads
as *add three*. It is **4 − 1 + 4**: Counter, Imports and Settlements are new;
**Refunds is new AS A TAB** and is a door to the screen that already exists at
`/finance/refunds`; *Record payments* is relabelled **Payments** and
*Outstandings* **Debtors**; and **Collections leaves the strip**, because the
drawing folds the ladder under Debtors as screen 7·3a.

**No id moves.** An id is in a URL a clerk may have bookmarked.

⚠ **THE LADDER KEEPS A DOOR, AND THAT IS THIS LANE'S JUDGMENT RATHER THAN A
RULING.** The blueprint's own page for 7·3a records that its only door today IS
its tab. Removing the tab with nothing in its place would have made a live,
routed, tested screen unreachable — the exact defect `P0.9`'s outcome exists to
prevent. So the Debtors tab carries a control to it until 7·1 is redrawn in
phase 2. The reasoning is in `02-decision-log.md` under *PHASE 0'S FRONT END*.

## WHAT TURNED OUT TO BE ALREADY DONE

| Task | Finding |
|---|---|
| `P0.7` | Built earlier the same day in `5279285e7`. Verified against the code, not rebuilt. |
| `P0.11`, the stage rail | `components/workflow/StageBar.tsx` is already the kit's and payments holds **no copy** of it. `P1.17` is what makes payments draw it. Building a second rail to satisfy a task line would have been the copy the task exists to prevent. |
| `P0.12`'s premise | *"zero times in staff payments"* stopped being true when `P1.6` put a box on Move and Reapply earlier the same day. The three the blueprint files are still the three below. |

## WHAT IS DELIBERATELY NOT DONE, BECAUSE IT IS PHASE 2's

The four KPI tiles 7·1 is drawn with, that screen's toolbar, and dropping its
bulk bar to *"two plus an overflow"*. Taking four controls off a live screen
inside a phase-0 kit task would be a change a clerk feels. The bucket `<select>`
therefore stays beside the new cards; **both drive the same state**, so they
cannot disagree, which is the only thing that would make keeping both a defect.

And `paymentsBulk.tsx` is not migrated to the kit's toolbar: that is `P1.8`,
which the plan holds on `P0.10`. The kit piece it waits on exists now, and
`selectionToolbarWiring.test.ts` asserts that it has NOT been mounted there, so
the day it is, that case goes red and says so.

## 3 · IMPACT

| Surface | What moved |
|---|---|
| Front end | `paymentsShared.tsx` (the seven-tab register and the holds) · `PaymentsPage.tsx` · `CollectionsPage.tsx` · `OutstandingsTab.tsx` · `ReadsBulkBar.tsx` (metering) · `routing/screenIds.ts` |
| Kit | **new** `components/AgeingCards.tsx` · **new** `components/SelectionToolbar.tsx`, both listed on `route-b-migrated.txt` in their own commits |
| Settings | `core/numbering.py` gains the 31st series, `settlement` |
| Copy | 21 keys across all eleven catalogues through `i18n_fanin.py` |
| Tests | `sevenTabs.dom.test.tsx` · `consequenceOnMoneyForms.dom.test.tsx` · `ageingCards.dom.test.tsx` · `selectionToolbar.dom.test.tsx` · `selectionToolbarWiring.test.ts` · `test_p013_settlement_series.py` |
| Walkthrough | `10-scripts/p0fe_phase0_frontend_walkthrough.mjs` — 20 assertions in a real browser |
| Open questions | none opened, none closed |
| Migrations | **none** |

## 7 · VERSION

**`2.332.0`** — the CHANGE digit, because this is new capability a clerk can
see: three tabs that were not there, two kit components, and a consequence box
on three forms that had none.

**`2.332.1`** — the FIX digit, for the `G44` finding below. Nothing a clerk can
see moved, which is why it is a fix and not a change; it gets a number of its
own so that *which build is this in?* has an answer for it too.

## 8 · CLOSE, AND THE ROLLBACK STATED BEFORE SHIPPING

**Rollback:** every commit in this wave is front end plus one catalogue row.
Reverting them puts the strip back to four tabs, the debtor bands back to KPI
tiles, the three money forms back to no consequence box, and removes the
`settlement` series from `SERIES_CATALOG` — no tenant holds a row for it yet
unless they have been re-seeded, and a row that exists is a format nothing
allocates from. **No migration, no schema, no data.**

### FINDINGS FROM THIS WAVE — TWO IN A BROWSER, ONE BY A GATE I HAD NOT RUN

| what | state |
|---|---|
| the ageing cards clipped their own money: `basis="posting"` inside a card a fifth the width of a KPI tile, under `white-space: nowrap` | fixed `2a9b8c2de` |
| the screen-id badge read `PAY-summary` while a clerk was on **Settlements** — the three new tabs had no `byParam` entry, so the row's default ran | fixed `2a9b8c2de` |
| `SelectionToolbar`'s money slot was named `total` while taking already-rendered output — an invitation to hand the next list a raw six-place decimal, which would print `1234.560000` | fixed `916a3fa38`, `2.332.1` |

The first two were not visible to `tsc`, to 386 payments cases, to the new
component cases or to the Route B compiler check, because **no check in this
repository reads rendered output** (CLAUDE.md hard-won law 6).

**The third was visible to a check, and the check was not run.** `G44` is not
in `run_gates.py --tier1`, and *"none of the red gates is mine"* was reported
off that tier — eighteen gates out of 131. The full run named
`SelectionToolbar.tsx:134` as a new entry above a banked ratchet of 20, and it
was right. Decision log, this date, section 8.

---

# PHASE 1 · `P1.5`, `P1.8` AND `P1.14` (lane P1-C, `2.333.0`, 2026-09-22)

**The last three phase-1 rows phase 0 was holding.** All three are built; two of
them turned out to contain a finding bigger than the task, and both findings are
filed rather than worked around.

## WHAT A UTILITY CAN DO NOW

**A clerk can open Payments → Imports and see every payment file this utility
has ever run**, with its number, its file, who ran it, how many rows came in,
how many loaded and how many were refused — and the one button on that screen
opens the importer at Extract. **That door did not exist this morning.** It is
what `P1.17`, `P1.18`, `P1.19` and `P1.22` were all waiting behind.

**And a clerk who ticks three payments and presses Reverse is now told, before
anything is written, which of the three will actually be reversed, which one
will not, why, and what the money will do** — *$278.10 goes back to 2 accounts.
2 bills re-open.* Yesterday the button said *Reverse 3* and reversed two.

## THE THREE ROWS

| Task | What it turned out to be |
|---|---|
| `P1.5` | Built — and the EXTRACTION the three existing copies had each REPORTED was taken. One component, two callers on its first commit. |
| `P1.8` | Built — the bar, the per-row confirm and B14 rule 11's consequence box, which a bulk money write had never had. |
| `P1.14` | Written and deliberately NOT activated: **two of the four things its outcome sentence asks for are not built**, and both are filed. ⚠ **BOTH WERE BUILT ON 2026-09-23 (`P1.9`, `2.334.0`) AND THE JOURNEY WAS WALKED THE SAME DAY (`2.343.0`) — `P1.14` IS ACTIVE.** The two sections below this one are older than the two above it; read to the end before acting on either. |

## THE FIVE ROWS THAT WERE BUILT AND NEVER REACHED THIS FILE

⚠ **RECORDED 2026-09-23. All five were built, pushed and proved on 2026-09-22 by
lanes P1-A and P1-B, and named only in their commit messages.** This file is
what somebody opens to ask *"is phase 1 finished?"*, and until this section
existed the honest answer it gave was **five short** — which invites the next
reader either to rebuild work that exists or to report the phase incomplete.

**Nothing below is new work.** Each row was verified in the history before being
written here, by the commit named beside it.

| row | what it was | landed in |
|---|---|---|
| `P1.10` | Delete the orphaned write-off route — *"one write-off queue, not two"* | `2cb5e1040`, `4c96baa75` |
| `P1.15` | The `JPAYWRONGACCT` journey: move a payment taken on the wrong account, and BOTH customers' balances move | `037fc6f39` |
| `P1.16` | The `J2-read-to-cash` regression — a hand-recorded payment behaves identically | `037fc6f39` |
| `P1.21` | The seven catalogue keys for the target, in all eleven languages | `ffb61b433`, `c8bce7c8a` |
| `P1.23` | The test that the rollback refusal RENDERS and the button does NOT | `ffb61b433` |

⚠ **`P1.10` IS NOT WHAT ITS TASK ROW ASKED FOR, AND THE DIFFERENCE IS A MONEY
PATH.** The row said *"delete the orphaned write-off route — the queue already
lives as a working panel in Revenue & AR."* Measured: **the panel that survived
the fold offers Approve and NOTHING ELSE, while the standalone page it replaced
offers Approve, Reject AND Reverse** — two acts served since 2026-09-01 and
reachable by nobody. So **the route is gone and the COMPONENT is kept**
(`DEF-PAY-6199`) until the panel gains both acts. Deleting it as drawn would
have taken the only Reject and Reverse doors in the product with it, silently.
**Both suites were green throughout** — one over a page no clerk could reach,
the other over a queue missing two of three acts.

⚠ **AND `P1.15` WAS ONE OF THE EIGHT BADLY-NAMED JOURNEY FILES** (`DEF-QAE-6208`
— a browser spec is matched by FILENAME, and eight files declare an id their
filename does not carry, so they cannot be activated at all). It was the one
where the fix was free because nothing cited it, and it is named for its id now.
**Seven remain, and they belong to the customers, move and runbooks lanes.**

## `P1.5` — "A FOURTH CALLER, NOT A FOURTH IMPLEMENTATION", TAKEN LITERALLY

§03 frame 4·1's page: *"Three copies of this list exist — premises, assets and
accounts … Payments is a fourth caller, not a fourth implementation."* §05's
register row: *"Reuse — the existing imports list, target=payments"*.

`components/workflow/ImportRunsList.tsx` is that list now, and
`AccountImportsTab` went from **515 lines to 100 of configuration** with its 15
existing cases green and unedited — the proof that not one pixel moved.
**PRM-04 and AST-04 are deliberately not migrated** and the decision log says
why: they have diverged on purpose, both predate `DEF-CUS-5009`'s row-action
split, and folding three behaviours in as three flags is three implementations
inside one file.

**What the drawing asked for and was NOT built, with the reason:** 4·1 draws
four KPI tiles (*Waiting · Applied today · Needs a person · Refused*) and SOURCE,
LABEL and AMOUNT columns. `ImportRunRow` serves none of those fields. B14 rule 37
makes a drawn figure an illustration and §05 says *Reuse*; four tiles reading
`—` would be worse than four tiles that are not there.

**No rollback control on a payments run**, and it is a claim about the server
rather than a scope cut: `import_runs.rollback` refuses this target by name and
`_load_payments_rows` creates no rollback point, because a posted payment cannot
be unwritten (hard rule 4).

## `P1.8` — THE FIGURE IN THE BUTTON IS THE FIGURE THAT WILL RUN

The blueprint files the gap and names the fix: *"The product already knows which
four … **it is showing what is already computed**"*. `splitSelection` calls the
same predicate the run calls and adds no rule — a second rule would be a screen
that says one thing before the button and does another after it, over money.

**Worked, on the drawing's own three rows:** three ticked, `$1,080.53` on the
bar, one already a reversal. The bar reads **Reverse 2** and says *2 can be
reversed · 1 cannot*. The confirm says *2 of 3 will be reversed. 1 skipped.*,
draws all three with *Skipped — already a reversal* against the third, and its
consequence box reads **$278.10 goes back to 2 accounts** over **2 bills
re-open** — summed on the storage grid, never a float.

**The refund confirm gets the same shape and the drawing draws only the
reversal's.** That is this lane's judgment, in the decision log so it can be
overturned in a word.

## `P1.14` — THE OUTCOME SENTENCE IS HALF UNBUILT

*"The payments appear on the one list with their run and Source · Post."*

⚠⚠ **THIS WHOLE SECTION IS SUPERSEDED — see *`P1.14` AND `JPAYLOCKBOX` — THE
WALK, RUN* at the foot of this file (2026-09-23, `2.343.0`). All three halves
are TRUE on the running product, measured in a browser.** It is kept because it
records how the verdicts were reached, and because a lane briefed from this
section alone was sent to rebuild work that had already landed.

| half | verdict |
|---|---|
| the one list | **TRUE** |
| Source · Post | **true in the database, invisible on the screen** — `DEF-PAY-6212` |
| their run | **STORED, and not served** — `DEF-PAY-6213`. ⚠ **CORRECTED 2026-09-23, see below** |

⚠⚠ **CORRECTED 2026-09-23 — "NOT SERVABLE AT ALL" WAS FALSE, AND THE CORRECTION
REMOVES ONE OF `P1.9`'s THREE BLOCKERS.**

This row read *"not servable at all"*, and the paragraph under it concluded that
**deleting the old pipeline would delete the only provenance this product has**.
Measured instead of reasoned: **`import_run_rows` carries `created_record_id`
— its own comment reads *"what it made, for rollback"* — and every row already
carries `run_id`. `_load_payments_rows` SETS IT** (`apps/metering/import_runs.py`
line 10856, `row.save(update_fields=[… "created_record_id" …])`), exactly as
`_load_accounts_rows` and `_load_parts_rows` do.

**So every payment imported through the NEW path already records which run made
it, in the same column every other import uses.** `DEF-PAY-6213` is a READ that
is missing, not a link that does not exist — and the fix is serving a column,
not a schema change.

⚠ **WHAT THAT DOES TO `P1.9`, WHICH IS THE POINT OF CORRECTING IT.** The
sequencing fact stated here was one of three reasons the old pipeline is held,
and it was the only one that claimed DATA LOSS. It is withdrawn: the new path
has its own provenance and deleting the old pipeline destroys none of it.
`P1.4` still keeps `payment_import_batches` and `payment_import_rows`, which
hold the history of what the OLD path imported, and that history is not touched
by retiring the code that wrote it.

⚠ **AND THE GENERAL LESSON IS THE ONE THIS FILE KEEPS RECORDING.** *"Not
servable at all"* is a claim about the whole schema, made without grepping the
schema. It was written in good faith by a lane that had measured the SCREEN
honestly and generalised from it, and it was repeated to the Product Owner as a
reason not to do something they had ruled twice. **A claim of absence needs the
same evidence as a claim of presence, and it is cheaper to check.**

## 3 · IMPACT

| Surface | Effect |
|---|---|
| Screens | S35 Imports is LIVE (the tab, its list and its one door) · S33's bulk bar and both of its confirms |
| Endpoints | none new. `GET /imports?f.target=payments` and the runner's existing five stages |
| Kit | `ImportRunsList` (new, 2 callers) · `SelectionRowPreview` (new, 2 callers) · `SelectionToolbar` (payments is its third list) |
| Catalogues | +22 keys across all eleven; 2 retired (the Imports hold) |
| Migrations | **none** |
| Open questions | none opened, none closed |
| Defects | `DEF-RAT-6211` (filed and FIXED) · `DEF-PAY-6212`, `DEF-PAY-6213` (filed, open) |

## 7 · VERSION

**`2.333.0`** — the CHANGE digit, because a clerk can do something they could
not do this morning: open the Imports tab, run a payment file from it, and read
an honest count on the bulk bar.

## 8 · CLOSE, AND THE ROLLBACK STATED BEFORE SHIPPING

**Rollback:** front end and one journey document. Reverting puts the Imports tab
back to its holding panel (its two catalogue keys would have to come back with
it), returns `AccountImportsTab` to its own 515-line body, and puts the bulk bar
back to the tick count. **No migration, no schema, no data**, and no payment
written by the importer is affected either way — those are ordinary `payments`
rows.

**For the reporter:** this is in **2.333.0**.

---

# PHASE 1 · `P1.9` — ONE PATH PER CAPABILITY (lane ONEPATH, `2.334.0`, 2026-09-23)

## WHAT A UTILITY CAN DO NOW

**A clerk opening Payments can see where every payment came from and which batch
it is in.** Two new columns on the one list: **Source** — *Counter · Digital ·
Post* — with a filter beside it, and **Batch**, carrying the import run's number
for money that arrived in a file and the `DEP-` code for money that has been
banked. Neither fact was new; both had been sitting in the database with no
reader.

## WHAT WAS DONE

| | |
|---|---|
| `DEF-PAY-6212` Source | **FIXED.** The list read carries `origin`, S33 draws the column and the filter, eight catalogue keys in all eleven languages |
| `DEF-PAY-6213` the run | **FIXED.** metering publishes `created_record_runs`; payments reads it through a new `metering_seam.py` resolved by name. Bulk — one `IN` per page (`NFR-3`) |
| `DEF-PAY-6216` (new) | **FILED AND FIXED.** The list read hardcoded `deposit_batch_id` to null under a comment saying nothing writes it; `reconciliation.cut_deposit_batches` has written it since bank rec shipped. The Batch column serves the CODE and the uuid stays unserved (B14 rule 31). Closes `DEF-2353`'s screen half |
| `JPAYLOCKBOX` | **UNBLOCKED, NOT ACTIVATED.** Both blockers closed and the journey amended to say so, plus two new checks — **M** Source on the screen, **N** the run's number on the screen. **No spec**: the walk has not been run, and checks **B** and **G** need a booted stack and a real PostgreSQL |
| the four server callers | **NOT REPOINTED** — held with the deletion. ⚠ And it is **three**, not four: `rbs_q_seed_sync.py` names the old module in a COMMENT and calls nothing |
| the deletion | **HELD.** See below |

## ⚠⚠ `P1.9`'s DELETION IS HELD — `DEF-PAY-6217`

**The old pipeline can match a payment by BILL NUMBER and the new one cannot.**
Old ladder: account number → **bill number** → payer name. New ladder: account
number → payer name. The bill column is not even offered — the old parser takes
seven columns including `invoice_ref`, the new target takes six.

**Worked:** a remittance row carrying only `BL-0141` and `292.87` matches CLEAN
today, finds the account and posts. `test_cs2__the_invoice_number_matches_clean_and_names_the_bill`
has asserted it since CR-059. On the new path that row has no account number and
no payer name, so it is a REVIEW and the write refuses it.

⚠ **AND THE NEW TARGET'S OWN COMMENT SAYS THE OPPOSITE** — *"a file the retiring
pipeline accepted is a file this target accepts"* — which is false for a
bill-number file. Hard-won law 1.

**Why it went unnoticed:** the new code argues that a bill reference must stay
provenance and never become an allocation instruction. **The old path agrees and
says so at length**; it used the bill number to find WHOSE money this is and let
`BR-PAY-010` allocate. So the two never disagreed about allocation, and the rung
that was lost had nothing to do with it.

**This is `P1.10` / `DEF-PAY-6199` again**, one module over: a replacement that
does almost everything, both suites green, and nothing in this repository asking
whether it does everything.

**The question for the PO, in one sentence:** *does any utility we are onboarding
send a remittance file that names the BILL and not the ACCOUNT?* If no, the rung
goes with the pipeline. If yes, the new target needs a seventh column and a third
rung before anything is deleted. If unsure, the six endpoints are marked
deprecated in the schema rather than removed.

## ONE MORE DIFFERENCE, FILED — `DEF-PAY-6218`

The old path REFUSES to place a stuck row on an account without a reason and
audits who decided and why; the new path's equivalent patches a cell and
re-validates. **The act survives, the record does not.** CS-2's own sentence:
*"it is the only record of why this money was judged to be this customer's."*

## 3 · IMPACT

| Surface | Effect |
|---|---|
| Screens | S33 and S21's Payments tab gain Source and Batch; the hidden `Deposit batch` column is REMOVED (its cell stated an absence that is no longer true) |
| Endpoints | none new. `GET /payments` gains `f.origin` and three keys on every row |
| Kit | none new — `Chip` is the kit's resting chip and is reused |
| Catalogues | +8 keys across all eleven |
| Migrations | **none** |
| Open questions | none opened, none closed |
| Defects | `DEF-PAY-6212`, `DEF-PAY-6213`, `DEF-PAY-6216` fixed · `DEF-PAY-6217`, `DEF-PAY-6218` filed and OPEN |

## 7 · VERSION

**`2.334.0`** — the CHANGE digit: a clerk can read two facts off the payments
list that no screen has ever shown.

## 8 · CLOSE, AND THE ROLLBACK STATED BEFORE SHIPPING

**Rollback:** front end, one selector, one new seam file, one published read and
a journey document. Reverting takes the two columns and the filter off the list,
puts the hidden `Deposit batch` column back, and leaves every payment row exactly
as it is. **No migration, no schema, no data**, and no money moves either way.

**For the reporter:** this is in **2.334.0**.

---

# PHASE 1 · `P1.14` AND `JPAYLOCKBOX` — THE WALK, RUN (lane P01-FINISH, `2.343.0`, 2026-09-23)

## WHAT A UTILITY CAN DO NOW

**A lockbox or store file now posts its payments on the day the money actually
arrived.** It did not this morning: every payment an import created was dated
the day of the IMPORT, so a customer who paid at the store on the Friday before
a Monday due date was recorded as paying on the Wednesday and charged a late
fee. **And a clerk can now narrow the payments list** — ticking Source, Status
or Type on S33 did nothing at all, on any of the eight filters.

Both were found by walking `JPAYLOCKBOX` on a booted stack. Neither was found by
`tsc`, by any unit suite, or by any gate.

## WHAT WAS DONE

| | |
|---|---|
| `JPAYLOCKBOX` | **WALKED.** Nine steps in Chromium at 1440×1000 against a real PostgreSQL 16 clone, signed in as a real user. **Twelve checks, all twelve pass, and two were watched FAIL first** — `B` on the pre-fix database (0 of 72 dated correctly) and `G` with the loader's savepoint removed (*aborted: InternalError*, a failure that does not exist on SQLite). Canonical run `IMP-260923-02`: 95 rows in, 72 loaded, 23 refused, every payment dated the day the store took the money |
| `P1.14` | **ACTIVE.** All three halves of its outcome sentence measured TRUE on the running product rather than inferred |
| `DEF-PAY-6294` | **FILED AND FIXED.** `_payment_moment` returned `None` for every stage-2 date cell, because a cell is an ISO STRING and it tested `hasattr(value, "year")`. 72 payments dated `2026-09-23` from a file that said `09/19` and `09/20` |
| `DEF-PAY-6293` | **FILED AND FIXED.** Every filter on S33 was decorative: the page serialised its state through a config declaring no filters, so the value never reached the URL and the URL is the only store |
| `DEF-MET-6287` · `6288` · `6289` · `6290` · `6291` · `6292` | **FILED, OPEN.** See below — none is worked around in the journey |
| three scripts | `jpaylockbox_seed_store_file.py` · `jpaylockbox_walkthrough.mjs` · `jpaylockbox_readback.py`, all re-runnable and committed |
| `JPAYLOCKBOX.spec.ts` | **STILL NOT WRITTEN, deliberately.** A Playwright spec is the next lane's, and it now has selectors that are known and two checks that have been seen red |

## ⚠ THE BRIEFING FOR THIS LANE WAS STALE, AND SAYING SO IS THE POINT

It named `DEF-PAY-6212` and `DEF-PAY-6213` as this lane's first two tasks. **Both
were already fixed** — by lane ONEPATH, in `2.334.0`, earlier the same day, and
recorded in this file's own `P1.9` section thirty lines above where the briefing
was written from. The briefing was assembled from the `P1.14` section, which is
older. Nothing was rebuilt, because the register was checked before the code
was: `status=fixed` on both rows.

**That is the coordinator's own warning back at them** — *"I dispatched a
duplicate lane today because I read a board that was only true as of the last
lane that wrote to it"* — and it is this file's recurring lesson in a third
form: a document with two sections about one task tells whoever reads it first
whichever answer they reach first.

## ⚠ THE JOURNEY'S FIXTURE DESCRIBES A FILE THIS PRODUCT REFUSES

Run exactly as written — `PAID` carrying *"a leading `$` and thousands
separators"*, `WHEN` carrying *"the store's own two-digit year"* — stage 3 reads
**95 rows checked · 0 will load · 95 blocked**, for two independent reasons.
The comma is stripped and the `$` is not. And `DATE_FORMAT_PATTERNS` offers no
two-digit-year slash format at all, so `09/19/26` matches nothing — while the
screen advises *"change the format in Settings › Regional"*, which for this file
is advice a clerk cannot take. `DEF-MET-6291`.

**So the walk runs the file BOTH WAYS**: as the store sends it, which is the
finding, and after the two hand edits, which is how the other thirteen checks
get reached. A utility onboarding a grocery store today must edit every row of
every weekend file in a spreadsheet first.

## ⚠ AND THE RECEIPT DOES NOT ADD UP — `DEF-MET-6287`

**95 rows in. The receipt says `Loaded 72 · Rejected 11`.** Twelve rows are on
neither side. `receipt()` reports stage 3's `errors` and never the run's own
`rejected_at_write`, which was **12** on this run. It is not payments-only:
every loader records that figure and no target's receipt reads it.

**It is the same twelve as `DEF-MET-6289`**, which is the other half of the same
story: stage 3 and the dry run both promise *84 will load* for a file the writer
refuses 12 of, because `PAY.NAME_ONLY_MATCH` is a FLAG-ONLY warning over a row
`create_payment_from_import` refuses by name. Its neighbour `PAY.ACCOUNT_ON_FILE`
carries a comment saying exactly why that must not be done — *"the writer refuses
this row, so flagging it would let an operator press commit expecting it to
load — the shape `DEF-544` names"*.

**Neither is worked around in the journey.** A walk that adjusted its own
expectation to match a receipt that does not add up would be the shape hard-won
law 7 calls *looking at the wrong thing*.

## ⚠ THIS LANE'S OWN DEFECT ROW WAS LOST TO AN ID COLLISION, AND IT IS WORTH ONE PARAGRAPH

The date defect was filed at 11:30 as `DEF-PAY-6286`. **Lane P5-SCREENS took the
same number twenty minutes later for a different defect, and a whole-file write
of the register carried this lane's row away entirely** — not renumbered,
GONE: zero rows in the register matched its title. It is re-filed here as
`DEF-PAY-6294`, verified against the remote in the same breath as the push.

**Both lanes' arithmetic was right.** `file_defect.py` asks the working tree,
`HEAD`, `@{upstream}` and every `origin` ref, and a sibling in its own worktree
is in none of them until it pushes — CLAUDE.md law 11, recorded there three
times already. What this occurrence adds is the SECOND half: the collision cost
a ROW, not just a number, and nothing reported it. `allocate.py --verify` at
push time is what caught it, on its seventh outing today.

⚠ **AND THE ROW WAS FILED IN THE SHARED CHECKOUT RATHER THAN IN THIS LANE'S OWN
`git worktree`**, which is what put it in reach of another lane's commit at all.
Six rows of this lane's (`DEF-MET-6287`–`6292`) survived only because a sibling's
pathspec commit happened to publish them — law 11 mechanism five, doing a favour
this time. **Run the allocator inside the tree you push from.**

## 3 · IMPACT

| Surface | Effect |
|---|---|
| Screens | S33's filter bar works — eight filters, none of which did anything |
| Endpoints | none new, none changed |
| Kit | none |
| Catalogues | none |
| Migrations | **none** |
| Data | an imported payment's `posted_at`/`cleared_at` is now the file's day. ⚠ **Rows already written carry the import day and are NOT rewritten** — hard rule 4 |
| Open questions | none opened, none closed |
| Defects | `DEF-PAY-6294`, `DEF-PAY-6293` fixed · `DEF-MET-6287`, `6288`, `6289`, `6290`, `6291`, `6292` filed and OPEN |
| Journeys | `JPAYLOCKBOX` amended with the walked record; `P1.14` ACTIVE |

## 7 · VERSION

**`2.343.0`** — the CHANGE digit rather than the FIX digit, and the reason is
the filter bar: a clerk can narrow the payments list, which they could not do
this morning. The date fix alone would have been `2.342.2`.

## 8 · CLOSE, AND THE ROLLBACK STATED BEFORE SHIPPING

**Rollback:** two source lines, one test file, three scripts and two documents.
Reverting `_payment_moment` puts imported payments back on the import day;
reverting the `filters:` key on `paymentsTableConfig` puts the filter bar back
to decorative. **No migration, no schema, no endpoint**, and no payment row
already written moves either way.

⚠ **WHAT ROLLING BACK WOULD NOT UNDO:** the 72 payments this walk wrote carry
the corrected dates, and any row written by the old code carries the import day.
They cannot be told apart by their `origin` — only by their run.

**For the reporter:** this is in **2.343.0**.
