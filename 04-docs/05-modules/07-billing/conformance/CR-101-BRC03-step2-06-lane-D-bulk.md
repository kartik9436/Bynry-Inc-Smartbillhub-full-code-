# `CR-101-BRC03` · step 2 · §06 **Fix a bill** — lane D, the many-bill shapes `26.2` and `26.3`

**Lane:** D of a four-lane wave (C: `26.1`/`26.5` · D: `26.2`/`26.3` · E: `26.4` and step 3 ·
F: step 4). **Branch:** `claude/gifted-johnson-top7zn`, own worktree
`agent-ac340940e6a84e94b`. **Base:** `05f555ed` at the start; **pushed onto `fe3490a1` and
then `6bc4ea65`** as five sibling commits landed underneath (§7). **Commits:** `550bb803`
(the screens, the registry line, 38 catalogue keys) · `e9bc75b6` (the three faults the
PICTURES found, the walkthrough script, 7 more keys, two defect rows). **Date:** 2026-09-15.
**Process:** `22-product-maintenance-process.md` — a live screen redrawn end to end is
MAINTENANCE. **Built through** `react-tailwind-css-ui-generator` (loaded before the first
line of TSX and again before this record) and `build-one-commitment-end-to-end`.

**What this is.** One commitment: the step-2 body a case with MANY BILLS renders under —
entry `26.2 Several months` and entry `26.3 A batch` — built to the drawing, wired into the
registry lane C and lane E share, walked in a browser at 1440 and 1280, and closed with
what it could not build and why.

**What this is NOT.** It is not `26.1`, `26.4` or `26.5` (lanes C and E), not step 3 or 4,
and it changes nothing on the server.

---

## 1 · Which pages were read, AS IMAGES, and at what scale

| Page | Read at | What it holds for this lane |
|---|---|---|
| p129 | scale 1.5 | §06's case table — what `26.2` and `26.3` each show and deliberately do not (THEIR MONEY · TAX · DISCOUNTS · WHAT GOES OUT), and *"An absent panel is drawn, never omitted"* |
| p135 | scale 1.5 | `26.2`'s header, its clerk sentence (*"Wrong rate since March…"*), the page head `The correction · Six months · one account · wrong rate · class R`, and the answer band |
| p136 | scale 1.5, **and cropped at scale 4** | `26.2` group 1 `BILL BY BILL` — the exact columns and the per-row note — the ⚠ band, group 2 `EACH MONTH ON ITS OWN TERMS`, the footer, the four annotations; then `26.3`'s header |
| p137 | scale 1.5, **and cropped twice at scale 4** | `26.3`'s whole frame: the answer band, group 1 `WHICH BILLS, RESOLVED ONCE`, group 2 `WHICH WAY THEY MOVE`, group 3 `ROWS THAT NEED A HUMAN EYE`, the footer |
| p138 | scale 1.5 | `26.3`'s four annotations — *"The approved set is a list, not a query"*, *"↑ and ↓ are not optional, and a test proves it"*, *"The totals tie out"*, *"A warning and a refusal are drawn differently on purpose"* |

The scale-4 crops were needed because a whole page at scale 4 is 4896x3168 and is
downsampled again by the reader, so nothing is gained: `10-scripts/pdf/pdf_render.py`
renders pages, and a CROP is what raises pixels-per-glyph. **No call was made to the text
extractor** (B14 rule 42). §06 is p129–p144; p145 opens §07 and was not read.

---

## 2 · Reproduce · locate · blast radius

**Reproduced** at `05f555ed` by reading `corrections_api._case_detail`: a case whose
`scope_kind` is not `single` gets `aggregate` and **no `sections`/`section_order` at all**.
The carried step-2 body renders `NineSections(only=STEP2_SECTIONS)`, which returns `null`
when `section_order` is empty — so **step 2 for every run, cycle, plan, service and
date-range case was the status pill and nothing else**, under a sentence saying the new
layout was not built. Not a regression; simply never built.

**Located:** the step-2 slot is `FIX_A_BILL_BODIES[1]` in
`07-frontend/src/features/billing/fixABillSteps.tsx`, rendered through
`FixABillStepBodyView` from `FixABillTab.tsx` at `/:tenant/billing/fix` and
`/:tenant/accounts/:accountId/issue-credit`.

**Blast radius, both ways.** Inbound: nothing imported a bulk step-2 body, because none
existed. Outbound: the one shared structure is the step-2 registry, edited by three lanes
in one afternoon — §7 is what that cost and what it taught. `billing.fix.settle.*` is
shared with step 3's settlement panel and was READ, not reworded; the four column headers
that replaced it are new keys (§4).

---

## 3 · What is on screen, group by group, and where every figure comes from

**Nothing on this screen is computed.** A screen that subtracted one money value from
another would be a second definition of the thing it subtracted (`DEF-2416`), which is why
`settlement_preview` exists server-side. Every figure renders through `MoneyCell` with its
own currency, at two decimals from the server's six (`CLAUDE.md` rule 2).

### The answer band, on both variants

Drawn: *"412 bills are affected. 389 go up and 23 go down, for a net of +$4,593.80."* —
21 words where B14 rule 33 caps a FACT at six. Built as **three short facts** —
`24 bills change. · 23 up, 1 down. · Net $689.37` — which is rule 33's own clause that two
sentences of six beat one of twelve, and **loses nothing**: BR-BIL-046 and p138 both insist
the two directions are never collapsed into the net, and both are still on the face of it.
Money goes through `MoneyCell` rather than into an interpolated string, because a figure
inside a sentence cannot carry its currency.

### `26.2 Several months` — two groups, as p136 draws

| Group | What it draws | Served by |
|---|---|---|
| 1 `Bill by bill` | one row per pinned bill: BILL · PERIOD · WAS · BECOMES · CHANGE · **PAID · MOVES ACROSS · TO CREDIT · STILL TO PAY** · NEEDS AN EYE | `bills_detail[i].impact` and `impact.settlement` |
| 2 `Each month on its own terms` | tax by authority, then the discounts cell | `aggregate.tax_by_authority`, `aggregate.discounts` |

### `26.3 A batch` — five groups

| Group | What it draws | Served by |
|---|---|---|
| 1 `Which bills, resolved once` | What · Bills · Frozen *At preview* | `scope_kind`, `aggregate.bills` |
| 2 `Which way they move` | Credited in full · Replacements issued · ↑ Owing more · ↓ Owing less · Net across the batch, each with BILLS and TOTAL | `aggregate` |
| 3 `Rows that need a human eye` | one row per warning the server can raise, with its count and a live `List them` | `bills_detail[i].warnings[].code` |
| 4 `Bill by bill` | the same table, COLLAPSED and searchable (p129) | as above |
| 5 `Tax and discounts` | by authority across the batch; `Accounts affected` | `aggregate` |

`List them` is the drawing's accent link and it is a `<button>` that writes the table's
declared `warning` filter and opens the disclosure — so the clerk gets the kit's chip and
the way to clear it, and the control is never dead (hard-won law 2's mirror).

### The Product Owner's action-table row 18, answered

*"Show payments already made in the period, and applied"* was marked **"Built but in step 3,
not step 2"**. Four columns now carry it on every row of both variants —
**Paid · Moves across · To credit · Still to pay** — from `impact.settlement`, which is
CS-36's own four figures. Where payments could not be asked the server sends `null` and the
cell reads *Not read yet*; **it never reads `$0.00` on a guess** (BR-SHL-020, lane B's
judgment 5), and a case asserts exactly that.

---

## 4 · Four things the drawing shows that the server cannot answer — drawn as absences, each with the test that fires when it is served

| Absence, in the clerk's words | Measured | The case that fires |
|---|---|---|
| **PERIOD** reads *Not read yet* on every row | `selectors.correction_bill_row` serves no period, and neither does `BillImpact.as_dict` — `invoice_no` and `account_id` and nothing else. The single-bill case gets its period from section 1 of nine, which reads the `Invoice` directly | `TC-D6.1` reads `correction_bill_row`'s body and goes RED the day `period_start` joins it. `DEF-BIL-5358` |
| **No paid total across a batch** — the figure is simply not drawn | `AggregatePanel.as_dict` totals credits, replacements, ↑, ↓ and net. Nothing sums what has been paid. Adding the page up here would be a client-side money total over whatever rows happen to show | `TC-D6.2` reads `as_dict`'s body for a `paid…` key. `DEF-BIL-5359` |
| **No per-bill checkbox on `26.2`; no *Beyond the 12-month cap · Removed from the set* row on `26.3`** | Both draw a window PARTLY allowed. `refuse_upward_beyond_window` **raises**, and `open_case` calls it inside the loop, so one bill past the cap with an upward delta refuses the WHOLE case at step 1. No case ever HOLDS such a bill | recorded, not tested — it is a product question. `DEF-BIL-5360` |
| **No `Narrowed by` row** | `detail.scope` carries `plan_id` / `service_code`. A uuid may not be rendered (B14 rule 31) and a raw service code may not either (`DEF-BIL-5336`), and the case payload carries no name | recorded. The hunk is a `scope_in_words` on the case |

⚠ **AND ONE THAT IS A FINDING RATHER THAN AN ABSENCE: `GET /corrections/{id}` SERVES EVERY
PINNED BILL IN ONE RESPONSE.** `_case_detail` builds `bills_detail` from `case_bills(case)`
with no envelope, no `page` and no `per`, so a T5 run of 40,000 bills is 40,000 impact
objects in one GET. The screen windows what it was already given — it adds no cap
(`NFR-5`) and could not page what arrived whole — and `TC-D6.3` names the screen that must
follow the day `_case_detail` pages its rows. `DEF-BIL-5361`.

---

## 5 · The walk, and what it found that no check could

**Stack:** this lane's own Django on `127.0.0.1:8206` from its own worktree
(`config.settings.local`, `JOBS_EAGER=false`, the shared PostgreSQL 16), `npx vite build`
served by `server.mjs`. Signed in through the real door as
`dana@brazosbendutilities.com` on `brazosbend`.

### ⚠ 5.1 The tenant cannot open a class-R bulk case AT ALL — `DEF-BIL-5377`

`POST /corrections` with a bulk scope and a class-R reason returns **422**:

> *account 'AC-2026-00042' is not in the billable set for its unit (BR-CUS-055).*

That account is **closed** and holds two issued bills. **Six scopes were tried and six
refused:** the June run, a date range over June, four rate plans, cycle CY-001, and both
service scopes that match anything at all (`electric` and `water` each resolve all 79
correctable bills, and both of the closed account's bills are in both). A class-**D** case
over the same cycle opens fine — 79 bills, 201 — which is what places the refusal in the
re-pricing path rather than in the scope. That probe case was **abandoned with a reason**;
no live case was left on the tenant (checked: 0).

**Why it matters past this seed:** at 40,000 accounts a utility always has closed ones, so
as it stands **bulk corrections do not work at T5**, and the refusal a clerk reads is an
account number and a customers rule id.

### 5.2 So the screens were walked against a stubbed CASE, and that is stated rather than implied

`10-scripts/cr101_fix_a_bill_step2_bulk_walkthrough.mjs` drives the real product: the real
sign-in, the real tabs, the real step 1, the real reason catalogue, the real scope-resolve
read. **Exactly two calls were answered by a shim** — `POST /corrections` for a bulk scope
and the `GET` of that case — because the tenant cannot produce one. The payload is built
from the REAL 79-bill case this tenant DID open: real bill numbers, real line labels, the
real tax authority. Synthetic are the class, the deltas and the settlement figures: the
four things the closed account stops the engine producing.

**36 checks green at 1440 and 1280**, both variants: the variant each case renders under,
no stated absence over a drawn screen, both directions in the answer, the five groups, the
five which-way rows, the warning counts, `List them` opening the collapsed list filtered
to its warning, two decimals everywhere, the month stated as absent on every row, no uuid,
and no horizontal page scroll. The two "page error 404" lines per width are the shim's:
the abandon posts the synthetic case id to Django, which correctly does not know it.
Abandon itself was proved against the REAL server by `POST …/abandon` on the 79-bill case.

### 5.3 ⚠ THREE FAULTS CAME OUT OF THE PICTURES, AND NOT ONE COULD HAVE FAILED A TEST

1. **The NEEDS AN EYE column carried whole warning SENTENCES.** A sentence in a cell sets
   the height of its whole ROW — `TableColumnConfig.cell`'s own docstring is written
   against exactly this — and seven bills became a wall three times their drawn height.
   The cell holds three or four words now (`Already paid in full`, `Posting period is
   closed`, `Nets to zero`, `Asks for more` — the drawing's own labels) with the sentence
   on `title`. Group 3 reads the same way.
2. **Ten columns are 1,073px inside a 960px step at 1280**, and every wrapper up to the
   page computes `overflow-x: visible` (measured in Chromium, not inferred). `NEEDS AN
   EYE` was not cramped, it was **unreachable**. The table scrolls inside its own container
   now; the kit gap is **`DEF-SHL-5378`** (FIXED IN THE KIT 2026-10-01, `3a135b4e8` — the screen's own wrapper is plain again) and was not this lane's to change under 145
   callers.
3. **The four payment headers were step 3's panel vocabulary** (`Replacement takes`,
   `Returns to credit`) and are what ran the table off the edge. They take p143's own
   shorter words now. The bill number no longer wraps onto three lines.

Every one of these passed `tsc`, eslint, 22 DOM cases and every gate while the screen was
wrong. jsdom performs no layout; the instrument was a person looking at a capture.

---

## 6 · Proof

| Check | Result |
|---|---|
| `npx tsc --noEmit` (local TypeScript 5.5.4) | **clean**, and proved capable of failing first: a planted `const laneDProof: number = "not a number"` raised `TS2322` at line 799, then was removed by a script that asserts the file is still over 1,000 bytes before writing |
| `npx vitest run FixWhatStepBulk.dom.test.tsx` | **22/22** |
| the whole Fix a bill family on the synced tree | **145/145** — `FixWhatStepBulk` 22 · `FixWhatStepSingle` 29 · `FixGoodwillStep` 11 · `FixChangesStep` 21 · `FixSendStep` 25 · `fixABillSteps` 11 · `FixABillTab` 15 · `routeBUtilities` 11 |
| `eslint --max-warnings 0` on this lane's files | exit 0 |
| `G31 declared-classes` | **PASS**, 0 undeclared classes — the file is on `route-b-migrated.txt`, so `routeBUtilities.test.ts` owns it and passes 11/11 |
| Catalogue parity | **+45 / −0 / ~0** in every one of the eleven (38, then 4, then 3), through `i18n_fanin.py`; 0 of the 450 non-English values is byte-identical to English |
| Browser walk, 1440 and 1280 | **36 checks green**, §5.2 — and §5.3 is what it found that the checks could not |
| Screenshots | six distinct files (md5-checked), §8 |

### Every guard proved RED FIRST, in `npx vitest run` — the harness that runs it

| Sabotage | What went red, verbatim |
|---|---|
| the registry stops pointing at this body | `TC-D5.1` *a variant is in both lists, or in neither: expected [ '26.1', '26.4', '26.5' ] to deeply equal [ Array(5) ]* · `TC-D5.2` *expected undefined to be [Function FixWhatStepBulk]* · `TC-D5.3` *expected undefined to be '26.3'* |
| `26.2` left in BOTH the drawn map and the hold | `TC-D5.1` *26.2 is drawn AND still named in the hold: expected true to be false* |
| `"period_start"` planted in `correction_bill_row` | `TC-D6.1` *correction_bill_row now serves a period — release the absence: drop the `data-fix-absent="period"` cell in FixWhatStepBulk.tsx, render the month, and close DEF-BIL-5358.* |
| `"paid_total"` planted in `AggregatePanel.as_dict` | `TC-D6.2` *the aggregate now carries a paid figure — draw it on the totals line of 26.3 and close DEF-BIL-5359. Do NOT sum the page here.* |
| `StandardPagination` planted in `_case_detail` | `TC-D6.3` *the case detail now pages its bill rows — FixWhatStepBulk must read the envelope instead of windowing bills_detail, and DEF-BIL-5361 closes.* |

⚠ **AND ONE CASE WAS FOUND LOOKING AT THE WRONG THING BEFORE IT WAS TRUSTED.** `TC-D3.5`
read the search result synchronously after `fireEvent.change`, and the kit DEBOUNCES the
box — so it passed on the PRE-search rows. It waits now, and the genuinely-empty state
moved to its own case (`TC-D3.7`), because the kit owns the no-results line and names the
TERM while this screen owns the empty one and names the SET (`DEF-BIL-5340`'s lesson).

---

## 7 · ⚠ The shared step-2 registry, three lanes, one afternoon — and the part worth keeping

This lane designed a variant registry (`FIX_A_BILL_STEP2_BODIES` + a held-variant list) and
wrote it into `fixABillSteps.tsx`. **Before it could push, lane C landed the same idea
under different names** — `STEP2_DRAWN_BODIES`, `TheCorrectionBody`, each lane declaring its
own variants as a constant exported from its own file — with a comment saying what a
sibling's edit should be. **This lane threw its version away and adopted lane C's**, which
is what re-reading the tip before re-applying is FOR: the final hunk in that file is three
lines (`+8 / −3`), and the alternative was two registries doing one job.

**The ids collided four times.** `DEF-BIL-5351`–`5354` were taken by a sibling while this
lane worked; renumbered to `5355`–`5358`, and lane C took `5355`/`5356` in the meantime;
renumbered to `5357`–`5360`, and lane F took `5357`; renumbered to **`5359`–`5362`**, which
is what shipped. The two later rows collided twice more and are **`DEF-BIL-5377`** and
**`DEF-SHL-5378`**. Every one was caught by `allocate.py defect --verify` re-run against the
tip at push time, never by arithmetic done earlier.

⚠ **AND THE COMMIT MESSAGE OF `550bb803` NAMES THE OLD NUMBERS** (`5355`–`5358`), because
the message was written before the last renumber and a pushed message cannot be amended.
**The ids in the CODE, the TESTS and this record are the right ones**; the message is
wrong and is left visible rather than quietly rewritten.

⚠ **AND A SIBLING MAINTAINED THIS LANE'S TEST CORRECTLY, WHICH IS THE GOOD NEWS.** When
lane E landed `26.4`, `TC-D5.4` — *"a HELD variant still reaches the carried body"* — was
FLIPPED rather than deleted, and `TC-D5.1` was widened for the day step 2 leaves the hold
list altogether. The second push therefore re-derived the test file **from the tip** and
re-applied only this lane's own two later hunks; writing back this worktree's copy would
have subtracted lane E's work by subtraction, with every check green.

---

## 8 · The pictures

`SCRATCH/lane-D-shots/` — six distinct files (md5-checked), full-page at a tall viewport so
one capture holds the whole step (width is the design variable):

| File | What it shows |
|---|---|
| `step2-batch-1440.png` · `step2-batch-1280.png` | `26.3 A batch` as it opens — the answer, the five groups, the rows collapsed |
| `step2-batch-listed-1440.png` · `step2-batch-listed-1280.png` | the same after `List them` — the collapsed list open and filtered to that warning, 8 of 24 bills |
| `step2-months-1440.png` · `step2-months-1280.png` | `26.2 Several months` — seven bills open, one row each, the month stated as absent |

Compared by eye against p136 and p137: presence, order and labels match group for group.
The differences are exactly the four in §4 plus the three in §5.3, which were fixed.

---

## 9 · Reds this lane did not cause, each dated

| Red | Dated how |
|---|---|
| `G13 unwired` — `AccountUsageTab.tsx`, `AccountCommunicationDialog.tsx`, `portal/components/listTable.tsx` | none is this lane's file; the same three lane A dated on 2026-09-15, `AccountUsageTab.tsx` last moved **`f6fa3670`, 2026-09-13** |
| `G33 refusal-copy` — `integrations.field.site_id` and two more | the same three lane A dated to **`cf45a3d2`, 2026-09-13**; none of this lane's 45 keys is named |
| `G106 cited-ids-exist` — 12 phantom ids in `customers`, `rating`, `runbooks` | files this lane never touched |
| `G98 lint-clean` — 10 files | this lane's three files are clean at `--max-warnings 0`; the ten are in `assets`, `customers` and `portal` |
| `G40 unmounted components` — **15, and `FixWhatStepBulk` is one of them** | ⚠ **THIS ROW SAID THE OPPOSITE FIRST AND THE FIRST VERSION WAS WRONG.** It read *"with `550bb803` the body is assigned and rendered in `fixABillSteps.tsx` … and the count returns to the tip's"*, which was an inference from lane A's record and not a measurement. Measured by calling the detector directly: **`FixWhatStepSingle`, `FixWhatStepBulk` and `FixGoodwillStep` are ALL on the list of fifteen** — every step-2 body all three lanes built. The cause is the registry's shape, not any one lane's: `STEP2_DRAWN_BODIES` is built with `Object.fromEntries(… .map(…))` and rendered through a local binding inside `TheCorrectionBody`, and `G40`'s indirection clause follows neither. **Writing this lane's two as LITERALS was tried and did NOT clear it** — `FixGoodwillStep` is a literal and is on the list too — so the shared file was put back to lane C's bytes rather than left carrying a comment claiming a guarantee it does not have (hard-won law 1). Filed as **`DEF-SHL-5379`**, with the gate's own output as half the finding: it prints FOUR of its fifteen names, so a lane asking *is mine on the list* cannot tell from the message. `CarriedWhatItChangesBody` is on it because lane E replaced it in the registry and left the function — lane E's, dated **`6cd93b5a`, 2026-09-15** |

---

## 10 · Version, changelog and rollback

**Not bumped here** — the orchestrator versions once the wave lands. The line this lane
would have written, on top of wave 1's `2.276.0`:

> **`2.277.0`** — *"Fix a bill's second step now draws the screen the blueprint draws for a
> correction that holds many bills: a window over several months shows one row per bill
> with what it was, what it becomes and what changes, and a batch shows which bills were
> resolved, which way they move, the rows that need a human eye and every bill collapsed
> behind a search. Both show what has already been paid against each bill and where that
> money goes, which is the step-2 gap the Product Owner asked for. Before this, step 2 for
> a run, a cycle, a plan, a service or a date range showed a status pill and nothing
> else."*

**Rollback:** code only — revert `550bb803` and `e9bc75b6`. No case was approved or
executed; the one probe case opened against the real server was abandoned with a reason,
and the walk's cases were never written to the tenant at all.

<!-- packet: CR-101-BRC03@lane-D · sources: 05-prototype/04 Billing, As Built.pdf §06 p129, p135–p138 read as IMAGES · CR-101-BRC03-step2-06-lane-A-step1.md §1 · CR-101-BRC03-step2-06-lane-B-backend.md §2.2 §3 · 06-backend/apps/billing/{bulk_corrections,corrections,corrections_api,selectors}.py -->
