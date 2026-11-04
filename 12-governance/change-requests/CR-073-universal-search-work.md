## CR-073 — Universal search reaches Work and Plans & Rates: six new groups

### CR-073 · 0 · CAPTURE — the Product Owner's words, verbatim

**Two messages, 2026-09-05, in the working session.**

**The change:**

> *"Extend universal search to include work order , template, parts"*

**And, when the scope was put back to them:**

> *"Don't add reads and finance - add work related items"*

One sentence each, no ID, no form — which is exactly how `13-change-process.md` says a change may
arrive. **The burden of structuring it is ours.**

⚠ **THE SECOND MESSAGE DOES TWO THINGS AND BOTH ARE BINDING.** It **excludes** two modules **by
name** — meter **reads** and **finance** — and it **widens** the first message from three named
tables to *"work related items"*, which is a category rather than a list. So the first sentence's
three are a floor and not a ceiling, and everything in this CR beyond them is ours to justify from
the screens.

⚠ **READS AND FINANCE WERE CONSIDERED AND RULED OUT — THEY WERE NOT OVERLOOKED.** Meter reads are
the highest-volume table in the product and a read has no identifier a person quotes (it is found
by meter, by route and by date, which is what `S25` is for); finance is `Plans & Rates`' neighbour
and its rows are ledger entries and journal lines, which nobody looks up by name. **Both were on
the table and the PO removed them.** A lane six months from now reading this register should not
re-propose either without a new ruling.

⚠ **IT IS THE SAME SENTENCE SHAPE AS THE 2026-09-03 RULING THAT WIDENED THIS RULE LAST TIME**
(*"Universal search will search premises , unit assets , master, regular account , customer id,
bill, payment, requests"*). That one added three groups the signed rule never contemplated and was
applied as an amendment to `BR-SHL-005` rather than as a new rule. This one is applied the same
way, for the same reason, and the precedent is named here so the third widening does not have to
re-argue it.

### CR-073 · 1 · CLASSIFY

**A new requirement.** Universal search does what was agreed — it searches the nine groups the PO
named on 2026-09-03 — and the agreement has grown. Nothing built is wrong, so this is not a
defect, and nothing was left undecided, so it is not an open question.

⚠ **ONE THING FOUND WHILE SIZING IT *IS* A DEFECT AND IS FILED SEPARATELY** — the four Work list
screens do not read `?q=` from the URL, so a per-group *View all* would have opened an unfiltered
list. See §4.

### CR-073 · 2 · WHAT SIGNED STATEMENT IS BEING AMENDED — quoted, never summarised

**`BR-SHL-005`**, `04-docs/05-modules/00-platform-shell/02-business-rules.md`, as it stood on
2026-09-05:

> | BR-SHL-005 | Global search scope **AS AMENDED 2026-09-03 — FOUR GROUPS BECAME NINE, and the
> enumeration is the rule**: `premises` · `units` · `assets` · `master accounts` · `accounts`
> (regular) · `customers` · `bills` · `payments` · `service requests`, **in that order**, by their
> B2 identifiers; grouped ≤5/entity; prefix-then-recency rank; per-group "View all" … |

**The supersedes chain, in full, because this is the third state of one rule:**

| | Scope | Authority |
|---|---|---|
| Original | accounts · premises+units · bills · payments — **four** | PO R1 A1, 2026-08-08 |
| First amendment | **nine** — adds assets, customers, service requests; splits master/regular | PO ruling 2026-09-03 |
| **This amendment** | **fifteen** — appends work orders, templates, parts, workforce, plans, charge codes | **PO ruling 2026-09-05** |

**What is superseded is the ENUMERATION and the count, and nothing else.** Every other clause of
`BR-SHL-005` stands and was not relaxed on the way past: **≤5 rows per group**, **prefix-then-
recency** rank, a **per-group *View all***, and matching on **identifiers** rather than on free
text. `BR-SHL-006` (tenant scoping, RLS FORCE, role-invisible groups omitted rather than empty) is
untouched and is what the new groups are built under.

**THE SIX NEW GROUPS APPEND AT POSITIONS 10–15 AND NOTHING IS RENUMBERED.** That is the
`fire`-at-position-11 posture from `CR-063`, and it is deliberate: renumbering would move every
citation of every existing group at once.

**Nothing ❄️ FROZEN is touched.** B4 and B5 are money math; this is a read path that computes no
money and writes nothing. No `STOP`, no finance re-sign.

### CR-073 · 2a · WHAT WENT IN, WHAT STAYED OUT, AND WHY — the judgment this CR is accountable for

The PO named three tables and then a category. **Everything below the first three is our reading
of *"work related items"*, taken from the screens rather than from the schema**, and the test
applied to each was one question: *is this a thing a person types into a box because they read it
somewhere else?*

| Group | What a person quotes | Why it is in |
|---|---|---|
| **Work orders** | `WO-0011` | The PO named it. It is the number on the dispatch board, on the phone and in the audit line |
| **Templates** | *Meter set* | The PO named it. A template has a `template_no` too (`ST-0004`, allocated on publish) — **both are searched**, name is the label |
| **Parts** | `MTR-W58`, *Water meter* | The PO named it. The number ranks first, the description still finds the row |
| **Workforce** | *R. Patel*, *Crew B*, *Apex Utility Svc* | **ONE group, not three** — `Work-023` already draws people, crews and contractors as rows in one table with one sort, and search follows the screen. A dispatcher types a person's name far more often than anything else in this module |
| **Plans** | `RES-W`, *Residential Water* | Unique per tenant on both columns; the thing a clerk puts an account on |
| **Charge codes** | `LATE-FEE`, *Late payment fee* | **The strongest quoting path in the product**: a charge code is printed on a bill line, and a customer phoning about a line on their bill is the commonest reason anyone searches at all |

**LEFT OUT, EACH WITH ITS REASON — reported rather than silently skipped:**

* ⛔ **Meter reads · finance** — **ruled out by name by the PO.** Not ours to revisit.
* **Work-order rules.** Considered seriously, and the answer is **no**, so it is left out and said
  so. The name *is* a real identifier (unique per tenant, and printed on `Work-007` after *Raised
  by:*), but **there is no rule detail screen** — `App.tsx` serves `/work/rules` and
  `/work/rules/new` and nothing else — so a result row could only ever open the rules list, which
  is a single short page a tenant has five rows on. A group whose best outcome is *the screen you
  would have clicked to anyway* is the passenger the scope ruling warned about.
* **Rate schedules (tariffs).** The screen's own search box matches `name` and nothing else, and a
  schedule is named *Water Residential 2026 v3* — structure, not something said out loud. It is
  reached from the plan that uses it, which IS searchable.
* **Taxes · discounts · rate changes.** Same test, same answer. A discount has a `code` and is the
  closest call of the three; it is left out because nothing prints a discount code where a person
  reads it, and it can be added later at position 16 by the same posture that added these six.
* **Skills · safety kits · part categories · priorities · order types · template child rows ·
  device registrations · cost lines.** Structure. Nobody looks these up; they are picked from a
  list on the screen that owns them.

### CR-073 · 2b · TWO GUARDS THAT COULD NOT FAIL — found by sabotaging them, recorded because the shape recurs

**(a) The isolation suite cannot prove the application tenant filter.** The obvious claim about a
both-tenants query is *"this cannot pass on an unscoped source"*. **It is false under the probe
role, and it was measured rather than reasoned:** `tenant_id=` was deleted from `search_parts`, the
suite was re-run against real PostgreSQL as `sbh_gate_iso`, and it stayed **GREEN** — that role is
precisely the non-superuser role RLS applies to, so layer 2 caught the leak invisibly. That is
defence in depth working AND a check that cannot fail for its stated reason. The file now says so,
and the app filter is proved separately on SQLite, which has no RLS to hide behind.

**(b) A string match is not a behaviour check — twice in one change.** The first draft of that
SQLite proof asserted the string `tenant_id` appeared in each source's SQL; **both sabotages passed
it**, because `select_related` names `tenant_id` in every joined table's SELECT list. The
`DEF-WRK-4094` pin had the identical disease — it matched the helper's name inside the comment
explaining the fix. Both are behavioural now and both were re-proved RED.

### CR-073 · 3 · IMPACT — the ten surfaces

| Surface | What changes |
|---|---|
| **User stories** | `US-SHL-003` (global search) grows by six groups. None becomes obsolete |
| **Business rules** | `BR-SHL-005` amended (nine → fifteen) with both rulings verbatim. `BR-SHL-006` unchanged and load-bearing. `BR-WRK-002` (Work reads other modules only through seams) constrains HOW |
| **Build steps / waves** | No wave order changes. `CR-070`'s Work waves are unaffected — this reads their tables and writes none |
| **Documents** | `core/search.py`, `apps/tenancy/search_api.py`, `apps/assets/search_sources.py`, `GlobalSearchResults.tsx`, `searchDestinations.ts`, `endpoints.ts` all quote the rule's count and are re-stamped in the same commit |
| **Code** | `apps/work/` (new source + seam doors), `apps/rating/` (new source), `core/search.py`, three frontend files, four list screens, eleven locale catalogues. **No 🔒 sensitive path**: no rating MATH (a charge code's `name` and `code` are catalogue columns; no amount, tier or formula is read), no ledger, no money rounding, no idempotency key, no webhook key. **This change adds no migration** |
| **Test cases** | A group case and a rank case per new group, a role case, the union pinned to `GROUP_ORDER`, and the live-PostgreSQL isolation probe extended to all six new tables |
| **E2E journeys** | None assert the old nine-group set. Nothing fails correctly; nothing fails at all |
| **Seed data** | Unchanged. The demo tenant already carries work orders, 24 templates, a parts register, four people and two crews, plans and charge codes — which is why this is demonstrable on the fixture that exists |
| **Open questions** | **ANSWERS none. RE-OPENS none.** Checked in both directions by reading, not by grep: `OQ-WRK-1490` (should `parts` carry stock levels) is untouched — this searches the register that exists and adds no column. `OQ-1360`/`OQ-1361` are fire-service questions and unrelated |
| **The demo fixture** | A person driving the product still sees a coherent utility, and sees more of it: typing `WO-` reaches the dispatch board, and a technician's name reaches the crews screen, from any screen |

### CR-073 · 4 · WHAT IS ALREADY BUILT AND IS NOW WRONG

**Code already shipped on the old rule.** Nothing is *wrong*; two things are *incomplete*:

1. **`core/search.py`'s `GROUP_ORDER` holds nine and `tests/test_be08_search.py` asserts nine.**
   Both move in this change, together — the test is the arbiter `DEF-3460` appointed for how many
   groups there are, so it must not be left behind.
2. ⚠ **THE FOUR WORK LIST SCREENS DO NOT READ `?q=` FROM THE URL** — `OrdersPage`,
   `TemplatesPage`, `PartsPage` and `CrewsPage` each seed from `defaultRequestState(config)` and
   never look at the query string. Every other group's *View all* opens its module list with `?q=`
   applied (`searchDestinations.ts`), so on these four the link would have opened an **unfiltered**
   list while promising a filtered one. **Found by reading the pages rather than by any check** —
   `tsc` passes, the link resolves, the screen renders, and the promise is quietly broken. Filed as
   **`DEF-WRK-4094`** and fixed in this change, because shipping the link without it would be the
   dead-control shape hard-won law 2's mirror clause is about. `PlansTab` and `ChargeCodesTab`
   already call `parseTableParams` and need nothing.

**Data already written.** None. This change writes no row, adds no column and runs no migration,
so there is no tenant left behind and nothing to repair.

**Lanes building right now.** `CR-070`'s Work waves are live in the same branch. **They are not
stopped and nothing is redirected**: this change adds new files and appends to existing ones. It
renames nothing they own and moves no table. If a Work wave lands a further searchable surface, it
appends at position 16 by the same posture.

### CR-073 · 5 · SIZE IT — in plain English, with the figures

**Not the fast path.** It amends a signed rule, so it earns the full process.

**What a person can do afterwards that they cannot do today:** from any screen in the product, type
into the one box at the top and reach a job, a job template, a part, a person, a plan or a charge
code — the same way they already reach a premises, a meter or a bill.

* Type **`WO-0011`** and the job opens.
* Type **`Meter set`** and every template of that name appears, one per service.
* Type **`MTR-W58`** — or **`Water meter`** — and the part appears.
* Type **`Patel`** and the technician's page opens.
* Type **`RES-W`** and the plan opens; type **`LATE-FEE`** and the charge code opens.

**The cost:** fifteen groups instead of nine, so a search that matched everything would show at
most **75 rows** where it showed at most 45. The popover already scrolls and the ≤5 cap per group
is unchanged. Six more queries per keystroke on a 300 ms-debounced box, each an indexed
prefix/substring match over a tenant-scoped table. **Measured rather than assumed — see §6.**

**What breaks if this is wrong:** nothing that writes. The worst case of a mistake here is a row
that does not appear or a link that does not open — and the two ways to get it badly wrong (a
database id shown on screen, a row from another tenant) are each guarded three times over.

### CR-073 · 6 · EXECUTE — through r11, unchanged

| # | Task | Status |
|---|---|---|
| 1 | `BR-SHL-005` amended: nine → fifteen, both rulings verbatim, supersedes chain stated | **DONE** — the 2026-09-03 row is kept below it as the superseded predecessor |
| 2 | Every citing document re-stamped in the same commit | **DONE** — 13-component-registry, 11b-api-audit, 04-flows, EP-SHL-01, plus the six code files that quote the count |
| 3 | `apps/work/seams/metering_seam.py` — read-only queryset doors for orders and templates | **DONE** — G78 shown RED on the direct-import shortcut first |
| 4 | `apps/work/search_sources.py` — four sources, identifier bands recorded | **DONE** |
| 5 | `apps/rating/search_sources.py` — two sources | **DONE** — no rating MATH read; `code` and `name` only |
| 6 | `core/search.py` — `GROUP_ORDER` grows to fifteen, at the end | **DONE** |
| 7 | `endpoints.ts` — `SearchEntity` union grows to fifteen | **DONE** |
| 8 | `GlobalSearchResults.tsx` — `GROUP_LABEL_KEY` grows (forced by `tsc`) | **DONE** |
| 9 | `searchDestinations.ts` — six destinations, each an address the router serves | **DONE** — pinned to the feature modules' own route constants, and walked in a browser |
| 10 | Eleven locale catalogues — six headings each, in each language | **DONE** — 13,817 keys each, sets identical to en.json |
| 11 | `DEF-WRK-4094` — the four Work lists seed `q` from the URL | **DONE** — and `searchDestinations.test.ts` now fails when a `?q=` destination stops parsing it |
| 12 | Backend tests: six groups, rank, role, union pinned to `GROUP_ORDER` | **DONE** — 16 new cases; five guards proved RED first, two rewritten because they could not fail |
| 13 | Isolation probe on real PostgreSQL under the non-superuser role | **DONE** — 9 passed, no vendor skips. ⚠ And it CANNOT prove the app filter: see §2b |
| 14 | Browser walkthrough — every group, working links, and the crowding MEASURED | **DONE** — all six groups typed into the real box on a booted stack and followed to their screens; worst crowding observed **3 groups / 8 rows** against a theoretical 15 / 75; `10-scripts/cr073_search_walkthrough.mjs` |
| 15 | Version, CHANGELOG, decision log, review-ledger row | **DONE** — `2.197.0`, G35 green on all four literals |

### CR-073 · 7 · VERSION

**Lands in `2.197.0`** — `<change>` moves because this is a wave merging, per the 2026-08-26
amendment. Bumped in the four literals `G35` holds in lockstep, with its CHANGELOG entry in the
same commit.

### CR-073 · 8a · WHAT THE BROWSER SHOWED — the closure bar, met

**Verdict, verbatim from the run:** *PASSED — every group renders, every link opens, nothing shows a uuid.* Run over its own leftovers, not a pristine seed: the second run reused the same booted stack and the same database the first run had already been through.

On a booted stack (Postgres + Django + the BUILT SPA, signed in through the real form), every one
of the six groups was typed and followed:

| Typed | Group | Row shown | Where it opened |
|---|---|---|---|
| `WO-` | Work orders | `WO-0039 · Meter set · 240 Sable Court` | `/work/orders/{uuid}` |
| `Meter set` | Job templates | `Meter set · Water · ST-0005` | `/work/templates/{uuid}` |
| `MTR` | Parts (beside Assets) | `MTR-W34`, `MTR-W58`, then `VLV-2200` | `/work/parts?q=…` |
| `Crew` / `Patel` / `Apex` | Crews & technicians | `Crew B (3)`, `R. Patel · Senior technician`, `Apex Utility Svc · Contractor` | `/work/crews?q=…` |
| `RES` | Plans | `RES-STD · Residential Standard` | `/plans-rates/plans/{uuid}` |
| `LATE` | Charge codes | `LATE · Late payment fee` | `/plans-rates/charge-codes/{uuid}` |

**The parts band split is visible in that third row and that is the point of listing it:**
`MTR-W34` and `MTR-W58` rank above `VLV-2200` because the first two match on their NUMBER and the
last only on its description (*MTR bypass valve*). The judgment recorded in §2a is what a person
actually sees.

**Crowding, measured:** worst observed **3 groups / 8 rows** (`RES` and `Meter`), against an
arithmetic worst case of 15 / 75. Nothing is capped and nothing is reordered.

**`DEF-WRK-4094` seen fixed:** `/work/parts?q=MTR` and `/work/crews?q=Crew` each opened their list
with the term already in the screen's own search box.

⚠ **AND THE WALKTHROUGH FOUND `DEF-WRK-4117`, WHICH NOTHING ELSE COULD.** Its first run reported
*"MTR did not produce a Parts group"* and *"Crew did not produce a Crews group"* — not because
either was broken, but because **`seed_demo` seeds no parts, no crews and no technicians**, so
`CR-070`'s Parts and Crews screens are permanently empty on the demo utility. Rows were seeded by
hand to finish this walkthrough. **That defect does NOT block this CR** — it is not one of this
change's own requirements failing (the closure bar's own rule of 2026-08-19) — and it is filed with
its own life.

### CR-073 · 8c · THE SUITES, IN FULL

| Suite | Result |
|---|---|
| Backend search suites | **52 passed** (16 of them new for these six groups) |
| Isolation, real PostgreSQL, non-superuser probe role | **9 passed**, 0 vendor skips |
| Frontend, WHOLE suite | **5,237 passed** · 365 of 368 files green · 4 failures in 3 files |
| `tsc` · `eslint --max-warnings 0` · `vite build` | clean · clean · green |
| Browser walkthrough | **PASSED**, second run, over the first run's leftovers |

**The 4 frontend failures are three files this change does not touch**, and that was checked rather
than assumed: `provisioningSteps.test.ts` fails on `assets:seed_sample_aged_meters has no label in
en.json` — a sibling lane's provisioning step whose key **was already absent at this CR's own
capture commit**; `ConfirmDialogTier.dom.test.tsx` and `templateSendTest.dom.test.tsx` reference
none of `shell.search.*`, `seedQueryFromUrl`, `SearchEntity`, `searchDestinations` or
`GROUP_LABEL_KEY`.

### CR-073 · 8b · THE GATES, AND THE THREE THAT ARE RED FOR SOMEBODY ELSE

**Green and relevant:** `G78` (the Work boundary — shown RED first on the direct-import shortcut
this lane was most likely to take), `G35` (all four version literals at `2.197.0` with a CHANGELOG
entry), `G31` (0 undeclared classes), `G27`.

**Red, and NOT this change's — checked by name rather than assumed:**

| Gate | What it says | Whose |
|---|---|---|
| `G15` | 161 values pasted in English rather than translated | **Portal.** It was ALREADY RED at this CR's own capture commit with **150** findings, before a line of this code existed; the extra 11 arrived from sibling lanes while this lane worked. **None of the 161 is a `shell.search.group.*` key** — grep returns 0 — and this change's six headings are written in each language (Ersatzteile · Refacciones · 部品 · 부품 · Suku cadang) |
| `G13` | an unwired prop | **Portal** — `portal/components/listTable…` |
| `G07` | a migration with no HUMAN-OWNED marker | **`CR-070` wave K** — `tenancy/0039_cr070_k_work_document_kinds.py`. This change adds **no migration at all** |

⚠ **The full `run_gates` suite was NOT run to completion** — it exceeds this lane's command budget
and was killed twice at 580 s. The gates above were run individually instead, which is a weaker
statement than a green suite and is recorded as such rather than glossed. What that leaves
unmeasured is every gate this change does not touch.

### CR-073 · 8 · CLOSE — and the rollback, stated before shipping

**The rollback is cheap and complete, and that is worth knowing:** remove the six entries from
`GROUP_ORDER` and the six from the `SearchEntity` union and the feature is gone, with no data to
undo. **No migration, no written row, nothing irreversible.** The rule amendment would be reversed
by another CR; the code would be reversed by a revert. `DEF-WRK-4094`'s fix is independently
useful and would be kept.

**Status: every task DONE. The closure bar is met — a person performed each task on the screen, in a browser, against the real stack. What remains is human review (step 5), whose row is in `09-human-review-ledger.md` and states the three things being put to the PO.**
