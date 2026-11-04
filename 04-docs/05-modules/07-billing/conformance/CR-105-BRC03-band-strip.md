# The band strip — what was built, and where the drawing and the repo disagreed

`CR-105-BRC03` · the band-strip lane · 2026-09-14 · tip `792b21e3`

**What this is.** The record for one component: `07-frontend/src/features/billing/BillRunBandStrip.tsx`,
its read and its tests. It is written because three of the decisions below are
judgments where the rules ran out, and one is a drawn element that contradicts a
signed rule — which under **B14 rule 41** is the one thing that reaches the
Product Owner. Recorded here rather than asked, following this module's own
precedent (`CR-101-BRC03-one-time-wizard.md` D2 and
`CR-105-BRC03-bill-detail-restructure.md`), and following hard-won law 13: a
judgment recorded with its reasoning is the deliverable; a question is the
failure to make one.

**How it was read.** `05-prototype/04 Billing, As Built.pdf`, pages rendered to
PNG and **read as images** (B14 rule 42) with `10-scripts/pdf/pdf_render.py`:
p039 + p040 at scale 5 (entry 17.L3, the strip drawn at full strength), p049 +
p050 at scale 4 (entry 17.0, the same strip **in flight**), p051 at scale 4
(entry 17, settled), p056 and p058 at scale 4 (17.1 and 17.2 — the only frames
where the SELECTED state is legible). The inventory
(`CR-105-BRC03-s03-element-inventory.md` §3) was the index; the drawing was the
authority.

---

## 1 · What was built

| | |
|---|---|
| Component | `07-frontend/src/features/billing/BillRunBandStrip.tsx` — **pure**, over data passed in. It is drawn on BOTH frames and is coupled to neither. |
| Read | `07-frontend/src/features/billing/bandStripEndpoints.ts` — `GET /billing/runs/{id}/findings/counts` |
| Tests | `07-frontend/src/features/billing/BillRunBandStrip.test.tsx` — **25 cases** |
| Ledger | `07-frontend/src/styles/route-b-migrated.txt` — appended, never rewritten (B14 rule 21) |

**Seven bands, generated tags.** Bands render in the SERVER's order — *ordered
by obligation, so a clerk is finished when the first band is empty* (p040).
Tags are whatever the run raised: nothing in the component iterates a list of
tag ids, so *a case kind the engine did not raise gets no chip* is structural
rather than remembered.

**Indentation is read from `partitions`, not from a list of three ids.** The
server marks the three sub-bands of *Held* with `partitions: "held"`. A test
serves a KNOWN sub-band as top level and asserts it stops being indented —
which is the case a hardcoded list passes every other assertion and fails.

---

## 2 · The arithmetic, and the fixture that makes the guard capable of failing

**A band counts ACCOUNTS. A tag counts CASES. The component derives neither
from the other.** The obvious wrong implementation — total a band by summing
its chips — is one line, and **every drawn frame in the blueprint agrees with
it**: both strips sum to exactly their band (`DEF-BIL-5273`).

So the test fixture sums three ways on purpose:

| Band | Accounts | Chips sum to | |
|---|---|---|---|
| `needs_you` | 12 | **19** | GREATER — p041's own example |
| `held` | 21 | **21** | **EQUAL — the control** |
| `held`, overridden | 9 | **7** | LESS — a server bug the screen must not repair |

**Proved RED in vitest, the harness that runs it.** With the band total changed
to `bandTags.reduce((n, each) => n + each.cases, 0)`:

```
× …chips sum to MORE  → expected '19' to be '12'
× …chips sum to LESS  → expected '7' to be '9'
Tests  2 failed | 23 passed (25)
```

⚠ **The EQUAL case passed on that broken build.** That is the whole reason it is
in there beside the other two rather than instead of them: a fixture whose chips
happen to sum to their band cannot tell the two implementations apart at all.

⚠ **AND THE FIRST DRAFT OF THE `LESS` CASE WAS POINTED AT THE WRONG BAND AND WENT
RED.** It was written against `everything_else` — and that band **draws no
total**, so there was no rendered number to disagree about and the assertion
could only ever fail. Only *Needs you* and *Held* carry a total.

⚠ **AND THE FIRST DRAFT OF THE ASSERTION COULD HAVE PASSED WRONGLY.** It read
`toContain(">12<")` over the whole band row, which a chip whose case count
happened to equal the band's account count would have satisfied. It now reads
the `data-band-accounts` span and nothing else.

---

## 3 · Where the drawing and the repo disagreed

### 3.1 · `Cart count missing` — THE ONE LABEL NOT BUILT AS DRAWN

**This is the one that reaches the PO under B14 rule 41.**

| | |
|---|---|
| Drawn (p040, p051) | `Cart count missing` |
| The server's reason | `unmetered_asset_count_undetermined` (`runs.CALC_ASSET_COUNT_UNAVAILABLE`) |
| Built | **`No count for this service`** |

The drawn chip is **trash-specific**; the server's reason is **every unmetered
service**. The product is onboarding a real customer on **fire**, whose lines
are counted exactly the same way (`CR-063`, and the PO's *"we need it for one of
the customer we want to go live"*). A fire account would read *Cart count
missing*, which is a false sentence about that account.

The product already has generic words for this exact condition, **shipped**:
`billing.run.absent.asset_count_unavailable` = *"Nothing has been counted for
this service"* — seven words, over B14 rule 33's six-word FACT cap. What is
built is **that sentence tightened to five, not the cap widened**, which is this
repo's own precedent of 2026-09-14 (four Romance translations came in at seven
and were tightened rather than the cap moved).

**One word from the PO reverses it.** If the answer is *build it as drawn*, the
change is one entry in `TAG_WORDS`.

### 3.2 · Three band names exceed rule 33's 3-word LABEL cap — BUILT AS DRAWN

*Answered by your default* (4) · *Where the fix is* (4) · *How long it has
waited* (5). They are the QUESTIONS the band answers — p040: *"Held is three
questions, not one, and the band answers all three"* — and shortening them
destroys the question shape the annotation insists on. Recorded, not reworded.

The chip labels are all inside rule 33 once the **2026-09-14 ruled precedent**
is applied — *"a picked reason names what went wrong on the bill, so the cap is
6 words, not 3"*. The six `The reason` chips and the three `Where the fix is`
chips are FACTs, not LABELs; the longest, *No base charge for this type*, is
exactly six. Every top-level chip is three words or fewer.

### 3.3 · `so far` — IN THE DRAWING, NOT IN THE INVENTORY

p049 draws **`Needs you · 87 so far`** and **`Held · 141 so far`** where p051
draws `Needs you · 12` and `Held · 21`. The inventory's §3 transcribes the
counts and **not the suffix**. Read off the page image at scale 4; it is why
the component takes `inFlight`.

### 3.4 · The label column is fixed; the drawing's is not

Measured off p040 at 5×, the first chip of each band starts at **seven
different x positions**. The annotation is explicit — *"band names in a fixed
label so the tags line up in a column"* — and the inventory's reading rule 1
gives the annotation the specification. Fixed column.

### 3.5 · The selected chip

Drawn as **bold text with no border**, confirmed on three frames (p049
`Missing read 31`, p056 `Missing read 4`, p058 `Unusually large 3`), so it is
deliberate. Built with the kit's `ChipToggle` (inverted ink-on-paper). **Which**
chip is selected is the blueprint's — a state; what *selected* LOOKS like is
r10's and the kit's — a style, which `DEF-GOV-5248` leaves with r10. `ChipToggle`
exists so one control does not acquire four appearances (`DEF-3722`).

### 3.6 · Three master-coverage codes, one drawn chip

`BR-CUS-068` refuses coverage three distinct ways
(`master_coverage_unresolved`, `…_spans_two_plans`, `…_repeats_a_service`) and
the server emits one tag per reason CODE, so **three chips appear where the
drawing draws one**. The drawn count is an illustration (rule 37); three faults
a clerk fixes differently are three chips, and each is given its own words
rather than three chips all reading *Master coverage*.

### 3.7 · `No usage` is drawn and the engine does not raise it

It was one of the six dead kinds `G124` was built over. Its words are kept
because they cost nothing; the chip simply never appears until the engine emits
the case — *a case kind the engine did not raise gets no chip*, working as
ruled rather than as remembered.

---

## 4 · What was deliberately NOT decided

| | |
|---|---|
| `OQ-BIL-12358` | Which cycle's bands govern an account held ACROSS cycles. `age_bands_from` is passed through with **no default**; the read will not acquire one. |
| `DEF-BIL-5276` | Whether the KPI strip gains a fifth cell for `In arrears`. That is the cell strip's question. `In arrears` is a CHIP here, which is what both frames draw. |
| `DEF-BIL-5274` | Screen 20's age chips summing to 49 over a band of 47. Screen 20 is not this component. |

**The age boundaries carry no drawn figure.** `Under 14 days` / `Over 60 days`
are illustrations (rule 37) against the PO's *"it depends on cycle
frquency … no hardcoiding"*. The chips read the served boundary: monthly
**31 / 62**, quarterly **92 / 184**, fortnightly **14 / 28**. With no boundary
the chip says the bare word and **no number**.

⚠ **THE NEGATIVE TEST ALONE WOULD HAVE PASSED ON A COMPONENT THAT DREW NO AGE
CHIPS AT ALL**, so it does not stand alone: a positive fortnightly case asserts
14 and 28 *are* drawn when the server says so, and the negative case asserts the
chips are present before asserting the digits are absent. Proved red by
installing the drawn figures as a fallback — 2 failed, 22 passed.

---

## 5 · The two gates this work moved

Measured with `run_gates.py` in this lane's own worktree, before and after.
**Baseline 72 PASS / 48 FAIL / 6 SKIP → after 73 / 49 / 4.** ⚠ **Two of that
movement is an ENVIRONMENT artefact and not this work**: the worktree started
without `node_modules`, so `G54 image-build` and `G98 lint-clean` were SKIP and
could not run; once linked they became PASS and FAIL respectively. `G98` names
**eleven** files and **none is this lane's** — `eslint` over these three files
exits 0. `G54` now genuinely proves `npm run build` (`tsc --noEmit && vite
build`) exits 0 with this component in the tree.

### `G107 one-responsive-direction` — CAUGHT A REAL DEFECT IN THIS COMPONENT, FIXED

The first draft wrote `sm:basis-56`, `sm:flex-nowrap` and `sm:pt-0` — **three
new min-width variants in a theme that is desktop-first**, which `tailwind.css`
states in capitals. Read normally it looks right; it is backwards, because it
makes the phone layout the truth and the desktop the exception. G107's baseline
`may fall, never rise`, so this was **fixed, not parked**: the variants are now
`max-md:`, and G107 no longer names the file.

### `G40 unmounted-components` — ROSE 10 → 11, AND IS LEFT RED ON PURPOSE

`BillRunBandStrip` is rendered by nothing yet: a later wave mounts it in the
in-flight and the settled frame, which this lane does not own. That is exactly
what hard-won law 2 calls dead UI, and G40 is the gate that says so. **It is not
baselined and must not be** — silencing a law-2 gate for your own new component
is the same move as widening a cap to pass your own strings. The honest state is
a red that names the work still to do, and it goes green the moment a frame
renders the strip.

---

## 6 · What this component is NOT covered by

**`G124` reads `billRunShared.tsx` and that file only.** It neither breaks on
this component nor covers it — a declared blind spot, stated with its scope
rather than left to look like coverage (CLAUDE.md law 7). It still reports
`billing_continuity` as the one engine kind the screen does not draw, and this
component renders that kind as **words** (*Billing continuity*) rather than
dropping it or printing the code.

`tagsWithoutWords()` puts a NUMBER on the same gap for this component, the way
`casesWithoutFamily()` does for the live screen.

---

## 7 · A red found on the way, not caused here

`DEF-BIL-5304` — `BillsListPage.tsx:407` declares four search fields and
`BillsPage.test.tsx:328` pins three. Red at the tip since **2026-09-13**
(`cf45a3d2` added the `address` leg); `be6cd38e` edited that very test file on
2026-09-14 without surfacing it. One true red inside `1 failed, 458 passed` over
32 files. **Not fixed here** — which side is wrong is a ruling, and those files
belong to another lane.
