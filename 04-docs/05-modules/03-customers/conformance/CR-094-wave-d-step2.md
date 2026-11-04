# CR-094-BRC01 · step 2 wave D — the request queue, the import, and the two wizards with no step rail

**Shipped as `2.239.4`, 2026-09-12.** Step 1 lane 5's record is
`CR-094-lane5-money-and-queue-step1.md`; this is what step 2 did with rows 2, 3,
4 and 7 of its findings table.

**Four rows repaired · four found on the way · one duplicate closed.**

| row | what | verdict |
|---|---|---|
| `DEF-CUS-5010` high | eight refusal keys declared in 0 of 11 catalogues, three of them the reason a control is disabled | **fixed** |
| `DEF-CUS-5009` medium | `Fix the rejected rows` offered only on runs with NO rejected rows | **fixed** — the hold moved onto the right rows; `ACC-S9` still unbuilt |
| `DEF-CUS-5011` medium | the chip read `All` while the server was asked for `segment=open` | **fixed** |
| `DEF-CUS-5071` medium | 2 of 11 customers wizards drew no step rail | **fixed** — both on the shared frame |
| `DEF-CUS-5064` medium | this lane's own new assertion found a fixture whose check could not fail | **fixed** |
| `DEF-CUS-5068` medium | step 1's own instrument has two rail detectors and neither can find a rail | **fixed** |
| `DEF-SHL-5067` medium | the active step's number is invisible on every wizard | **OPEN** — `WizardFrame` is `CR-093`/shared |
| `DEF-WRK-5066` low | the Work rule builder hand-rolls a second step rail | **OPEN** — another wave's file, baselined by name |
| `DEF-AST-5065` medium | five class tokens rendering nothing on three shipped screens | **duplicate** of `DEF-SHL-5088`, filed by a sibling minutes earlier |

---

## 0 · HOW THIS WAS PROVED, AND WHAT THAT IS WORTH

**Every fault was reproduced in Chromium BEFORE a line was changed**, on
PostgreSQL 16 with the fixture untouched (73 accounts, 20 service requests, 5
import runs — two of them finished with rejected rows). The product was built
with `vite build` at HEAD and served by `server.mjs` with `API_PROXY_TARGET` at
the backend, which is the same-origin shape the product ships. Signed in as
`dana@brazosbendutilities.com` on `brazosbend`.

**The instrument is `10-scripts/cr094_wave_d_walkthrough.mjs`**, and it
ASSERTS rather than prints: `26 checks, 0 failed`, at **1280 AND 1440**, exit
code 0. It carries the `ACC-S9` hold-expiry check, so it goes red the day that
specification is built.

**Every guard was broken FIRST and its failure quoted**, through the harness
that runs it green — and one of those red proofs was aimed at the wrong thing
and stayed green, which is recorded in §5 rather than tidied away.

---

## 1 · `DEF-CUS-5010` · S84 → Decision tab and Location & services

### As it was, measured

On `SR-26-0006` (served and vacant) the page printed, as literal text:

```
WHAT THE ADDRESS LOOKUP FOUND
  customers.serviceRequest.lookup.servedAndVacant
New connection   customers.serviceRequest.verdict.newConnection.premiseExists   (disabled)
Move-out         customers.serviceRequest.verdict.moveOut.noAccountHere          (disabled)
Transfer         customers.serviceRequest.verdict.transfer.noLiveAccount         (disabled)
```

each verdict key in the disabled button's `title` AND beside it in a
`role="note"`. On `SR-26-0004` (no premise record), the same shape with
`lookup.noPremiseRecord`. **Counted: 8 keys the resolver can emit, declared in
0 of the 11 catalogues.**

### As it is

`dottedKeysOnScreen: []` on both requests, at both widths, and the three
refusals read:

* *"A premise record already exists here."*
* *"No live account at this address."*
* *"This applicant holds no live account."*

### Two faults, and the catalogue lines alone would have fixed one

`service_requests.lookup_found` **stores a catalogue key**, by design
(`service_request_service.py:1139`, the ruling of 2026-08-19: a screen's words
come from the catalogue and nothing else). Read from the live API rather than
inferred — `GET /api/brazosbend/service-requests/{id}` answers
`"lookup_found": "customers.serviceRequest.lookup.noPremiseRecord"` — and three
screens handed it to `TextOrNotSupplied`, which prints a string as it stands.

`CatalogueSentence` (in `serviceRequestShared.tsx`) resolves it and falls back
to the value, so a legacy row holding real English still reads as English. It is
a second component rather than a widened `TextOrNotSupplied`, because that one
renders free text a person typed and a translator over those would look up
whatever a clerk wrote.

⚠ **THE THIRD SITE IS NOT THIS WAVE'S AND IS NOT FIXED.**
`ServiceRequestCapturePage.tsx:1289` draws the same stored key on the capture
wizard's review step — lane 3 / wave E's screen. The component is in the shared
file, so it is one line.

### Why nothing saw it, and what sees it now

The keys are f-strings built from a `_REASON_KEY` prefix and returned in a
tuple, so **`G32` cannot read them** (it reads `message_key=` keyword arguments
and dict literals, with `ast`) and it reported **0 unresolved** — truthfully, of
everything it can see. **`G33` walks G32's key set by construction**, so the
six-word refusal cap could not reach them either.

`06-backend/tests/test_def_cus_5010_verdict_keys_resolve.py` asks at the RAISE
SITE: it drives `outcome_verdicts()` over every evidence combination and reads
the three `LOOKUP_*` constants, so the key list is exhaustive by construction
rather than by a regex. Five cases — the count is 8, every key resolves in
English, every key is in all eleven, the English is within G33's cap, and no
catalogue line IS its own key.

**Red first, through `pytest`:** `8 key(s) … resolve to NOTHING in en.json`,
parity broken in all eleven.

### The copy

Eight keys, eleven languages, through `10-scripts/i18n_fanin.py` — the tool that
owns those files. Each English line is **one sentence of six words or fewer**
(B14 rule 33 / G33's cap, which binds every new refusal). Each locale is written
against the register its neighbouring `customers.serviceRequest.resolution.*`
keys already set, not translated word for word from the English (B14 rule 35).
**NATIVE-REVIEW-OWED for ten of the eleven.**

⚠ `lookup.servedAndVacant` is byte-identical to `resolution.served_vacant`
— *"Served, and the unit is vacant"* — and that is deliberate. B19 draws the
same sentence for both fields, and inventing a second phrasing for one fact is
what B14 rule 34 exists to stop.

---

## 2 · `DEF-CUS-5009` · S81, the Imports tab

### As it was, measured

| run | in / loaded / rejected | status | offered |
|---|---|---|---|
| `RUN-2822` | 312 / 310 / **2** | Loaded | *Roll back this run* only |
| `RUN-2814` | 1,251 / 1,247 / **4** | Loaded | *Roll back this run* only |
| `RUN-2801` | 88 / 88 / 0 | Loaded | *Roll back this run* |
| `IMP-260912-02` | 3 / 0 / **0** | File read | *Fix the rejected rows*, disabled |

`AccountImportsTab.tsx:227` was `row.status === "loaded" ? rollback : fixRows`
— two branches on a field the clerk does not read, and the `rejected` count
played no part.

### As it is

**Each action asks its own question of its own field.** Roll back where
something LOADED; the fix where something was REJECTED; both on a run where both
are true — reverse all 1,251, or repair the 4. A run still in flight with
nothing rejected is offered neither, because there is nothing to do to it yet.

### The hold, and the test that fires when it goes

Reopening a finished run is **`ACC-S9`** — a specification with no ruling
deferring it — so the fix renders disabled carrying
`metering.imports.fixRowsBlocked`. Hard-won law 2's mirror half says the expiry
test ships in the same commit, and it does, in both harnesses:
`AccountImportsTab.test.tsx`'s `DEF-CUS-5009` block and the walkthrough's
`5009-hold` check. **Both go red the day the reason goes.**

**Red first:** 3 of the 4 new cases fail on the old ternary —
`expected [ 'Roll back this run' ] to include 'Fix the rejected rows'`.

⚠ The file's own exceptions note claimed *"this file asserts only that the
control is offered on a loaded run and blocked with its reason elsewhere"* —
true, and it described the defect. It is corrected in place with that said.

---

## 3 · `DEF-CUS-5011` · S83, the requests list

### As it was, measured

Chip `All` with `aria-pressed="true"`; footer `1–18 of 18`; the one network call
`?segment=open&page=1&per=50&sort=created&dir=desc`; the tenant holds **20**.

### As it is

Chip `Show: Open` over the open ones; `All` is the clear-all control and means
all. `segmentFromState` falls back to `"all"` — the chip's own meaning — and the
drawn default (B19 §12.1 selects **Open**) arrives as an APPLIED filter.

### What was tried and abandoned, because it looks like the obvious fix

Seeding `?f.segment=open` on mount works, and it makes **`DEF-664`'s own case
false** — that case asserts the standalone screen's address starts EMPTY and
gains parameters only when a clerk acts. So the "has the clerk touched this"
fact lives in a ref instead.

⚠ **THE PRICE, stated rather than hidden:** a cleared segment is not shareable,
because a bare URL is the default. Nothing on screen lies while that happens,
which is the whole of this defect. It is the same class as **`DEF-CUS-5091`**
(wave C, OPEN) and belongs to that row's fix.

**Red first:** `Unable to find an element with the text: Show: Open`.

---

## 4 · `DEF-CUS-5071` · S23 change plan · S24 payment plan

### As it was, measured

`railPresent: false`, `dataWizardNodes: 0` on change-plan at step 1 **and at
step 2 after a plan was picked**, and on payment-plan. None of
`Plan`/`Effective`/`Confirm`/`Terms`/`Schedule`/`Agreement` appeared anywhere on
either page, and neither printed `Step n of 3`. The blueprint drew the rail and
stamped its own frame **NO STEPPER IS RENDERED**, unable to tell whether the
rail arrived after the first choice or the drawing was wrong; walking to step 2
settled it.

### As it is — and this was a WIRING job, not a build

Both mount `components/WizardFrame`, so **10 of the 11** customers wizards now
share one rail, one Back/Continue row, one single-flight commit and A18 §3/§4.
**B14 rule 3** is RATIFIED and unenforced: *"Any flow with 2+ stages uses the
numbered step rail (clickable when complete) + a wizard-actions footer."*

The rail is built by `.map()` over the declared const, so a fourth step appears
on it and a step with no label key is a typecheck error. Ten new catalogue keys
in eleven languages carry the three rail labels per flow, the `Step n of 3`
sentence and the A18 §4 what-failed line.

### Measured after, at 1280 and 1440

| | |
|---|---|
| rail | present, three names, step 1 `active`, step 3 `upcoming` |
| B14 rule 39 | rail margin-bottom **24px** · step padding **16×20** · gap **12px** · badge **26×26** |
| B14 rule 40 | page-head title **32px** on both |
| it MOVES | pick a plan → Continue → step 1 `done`, step 2 `active`, `Step 2 of 3`; step 1 navigable, step 3 not (`BR-SHL-018`) |
| a refusal | a service-dropping plan blocks with *"Confirm that the customer knows the service will end."* and the rail does not move |
| no plan possible | `AC-2026-00011` already has one (`BR-CUS-043`), so NO rail and the server's own sentence |

### Two divergences from the drawing, both deliberate

**(a) A greyed Continue becomes a live one that prints its reason on press.**
`GuardedButton` disables with a tooltip; the frame renders the refusal at the
button that refused it (`DEF-178`, and `DEF-936` for the per-step sentence).
**B14 rule 38 settles it** — where a drawing and our UI rules disagree about how
a form is BUILT, the UI rules win — and the alternative was a tenth hand-rolled
footer with its own opinion.

**(b) The RBAC refusal moved to a page-level strip.** The frame reports AFTER a
press, which is right for an unfinished step and wrong for a role that may never
finish it (`BR-SHL-025`). The nine siblings already put it in a strip
(`MoveOutWizard.tsx:816`), so it is reused rather than re-invented — and the
read-only case in `PaymentPlanWizard.test.tsx` is what caught the regression.

### Verified no copy or component was lost in the restructure

`ChangePlanWizard.tsx` moved **+180/−79** and `PaymentPlanWizard.tsx`
**+307/−178**, almost all of it re-indentation. Checked as arithmetic rather
than by eye: the set of `t("…")` keys lost is exactly
`{planChange,paymentPlan}.{back,continue}` (the frame supplies `wizard.back`
and `wizard.continue`), the set gained is exactly the new keys, and the
component-tag census moves only where intended — `GuardedButton` 7→2 and 6→2,
`WizardFrame` 0→1, `RefusalStrip` +1 each, `Panel` +1/+2.

---

## 5 · THE THREE FOUND ON THE WAY, AND THE CHECK THAT COULD NOT SAY IT WAS SOUND

**`DEF-CUS-5064`.** `DEF-CUS-5010`'s assertion was written as *"no internal code
appears anywhere in the rendered Decision tab"* — the clerk's-eye question, not
*"is this key declared"* — and it went red on four more dotted keys. The
fixture sent condition keys the server never sends
(`arrears · eligibility · documents · fees` against `CONDITION_KEYS`'
`no_blocking_arrears · eligibility_evidence · documents_verified ·
fee_settled`), **and the assertion on a blocked approval built its EXPECTED
string from the same unresolvable key** — both halves broken, test green. The
fixture now carries the served payload's vocabulary, read from the live
endpoint.

**`DEF-SHL-5067`, OPEN.** The rail badge composes `bg-surface` and `bg-accent
text-bg` as two class strings on one element; in a utility system the compiled
sheet decides, not the class list. Measured on three wizards: the ACTIVE badge
is `background rgb(234,233,233)` — byte-identical to an UPCOMING badge — with
`color rgb(243,242,242)`. **Near-white on near-white, on every wizard in the
product.** Not fixed here: `WizardFrame` is `CR-093`/shared.

**`DEF-WRK-5066`, OPEN.** `features/customers/wizardRailCensus.test.ts` is
`DEF-CUS-5071`'s prevention column built: of the **18** exported `*_STEPS`
consts in the app, **17** reach the shared frame and `RULE_BUILDER_STEPS` does
not — `features/work/RuleBuilder.tsx:138` draws its own `<ol data-rule-steps>`.
Baselined by name with its row rather than shipped red, and the baseline's own
third case fails when an entry stops reproducing.

⚠ **THAT CENSUS'S FIRST RED PROOF WAS AIMED AT THE WRONG THING AND STAYED
GREEN**, and it is recorded because it is law 7's second habit in miniature. One
reference to `CHANGE_PLAN_STEPS` was deleted from the wizard and the check
passed — correctly: the file still used the const elsewhere and still mounted
the frame. It carries a **self-test** now, with the predicates taking their
sources so three synthetic shapes exercise them, including a const named only in
a comment.

**`DEF-CUS-5068` — and it was found by obeying the brief.** Re-running step 1's
`cr094_lane5_walkthrough.mjs` AFTER the fix still reported `railNodes: 0` and
`namesEveryStep: []`. Neither reading was about the product: the selector was
`[class*=step], [class*=rail], …` and `WizardFrame` carries no such class (its
own docstring records moving those handles to `data-wizard` attributes), and
the word-boundary filter ran against `document.body.textContent`, which
concatenates — the rail reads `1Plan2Effective3Confirm`, where `1Plan` has no
boundary between two word characters. **Both were incapable of passing, on all
ten wizards including the nine that always had a rail**, and step 1's
conclusion was correct anyway, which is why nobody looked. Proved by measuring
one page three ways at once, and fixed: it now answers `railNodes 3`, labels
`1Plan · 2Effective · 3Confirm`, states `active · upcoming · upcoming`.

---

## 6 · WHAT WAS LEFT, AND WHAT IT WOULD TAKE

| left | why | who |
|---|---|---|
| `ServiceRequestCapturePage.tsx:1289` renders the stored lookup key | another wave's screen | wave E · one line, `CatalogueSentence` is built |
| `WizardFrame`'s invisible active badge | moves eleven wizards at once | `DEF-SHL-5067` · `CR-093`/shared |
| `RuleBuilder`'s own rail | another wave's file | `DEF-WRK-5066` |
| `ACC-S9` — reopening a finished run | a BUILD, not maintenance; `PATCH /imports/{run}/rows/{n}` on the workflow's stage 3 | a step-2 build lane · its hold-expiry test is already in place |
| the requests list opening on the oldest | **the PO's**, and already asked | `OQ-CUS-1790`, OPEN — not re-asked (law 13) |
| a chosen sort surviving a refresh | wave C's row, and this wave's price paragraph names it | `DEF-CUS-5091`, OPEN |

**Nothing here resolved an open question by choosing a value, and no registered
refusal was filed as a defect.** `customers.paymentPlan.queueOnly` and the three
import source holds were checked against the register and left alone.

---

## 7 · THE GATE PICTURE, DATED

**Baseline: `73 PASS · 47 FAIL · 3 SKIP` at `e427f4e8e`, 2026-09-12 14:48Z** —
taken before any change. ⚠ **The captured output of that run holds only its
tail**, so the per-gate verdicts for `G1`–`G55` were lost; `G18`'s baseline is
therefore established by arithmetic (240 unparked dead keys and 4 unparked
missing ones cannot be caused by the 4 keys this wave briefly orphaned) rather
than by that record. **A baseline you cannot read is not a baseline**, and
saying so is cheaper than implying one.

| check | before | after |
|---|---|---|
| `G18` dead keys | 472 (244 unparked) | **468 (240 unparked)** — the four this wave orphaned are deleted |
| `G35` version lockstep | PASS at `2.239.3` | **PASS at `2.239.4`** |
| `G67` traceless fixes | 229 | **229** — all six rows closed here name their id in the code |
| `routeBUtilities.test.ts` | RED on 5 orphan tokens (`DEF-AST-5065`) | **PASS** — a sibling fixed it as `DEF-SHL-5088`; mine is closed `duplicate` |
| `eslint src --max-warnings 0` | RED, 3 dead imports | **clean** — a sibling's fix |
| customers vitest | 679 passing | **688 passing**, 36 files |

⚠ **READ ALONGSIDE:** `G18` is RED and was red before this lane started.
`DEF-AST-5065` was filed for a red this lane did not cause and then closed
`duplicate` — two lanes read the same red within the hour, which is what law 7's
first habit produces when it works.

---

## Lifecycle
```
packet:     CR-094-lane5-money-and-queue-step1.md §9 rows 2,3,4,7 ·
            04-docs/05-modules/03-customers/08-screen-layouts.md ·
            B14 rules 3, 12, 15, 32, 33, 35, 38, 39, 40 · B19 §12.1/§12.3 ·
            blueprint pages 132-135, 140, 141-148
built:      2026-09-12 by CR-094-BRC01 step 2 wave D, shipped as 2.239.4
proved:     10-scripts/cr094_wave_d_walkthrough.mjs — 26 checks, 0 failed,
            1280 and 1440, exit 0 · every guard red first
exceptions: (1) two divergences from the drawing under B14 rule 38, §4 ·
            (2) a cleared segment is not shareable, §3 · (3) three findings
            left with the lanes that own the files, §6
status:     VERIFIED-UNRATIFIED
```
