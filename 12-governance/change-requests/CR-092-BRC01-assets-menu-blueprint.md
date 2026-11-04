# CR-092-BRC01 — The Assets menu, read against its blueprint: twenty-four specifications, twelve rule violations, and a baseline that is still true

**Raised:** 2026-09-11 · **Requester:** the Product Owner, in the working chat session
**Branch block:** `BRC01` (`claude/hi-0jmv62`) · **Module:** metering (product name: Meter Reads; owns assets per B2 r4)
**Status:** STEP 1 DONE (6 conformance documents, 41 rows, 35 open) · **five PO rulings 2026-09-12, §6a** · step 2 running — **wave A landed `2.237.1`; wave B lane 1 (the registry, screens 01–06) landed `2.237.5`: six rows fixed, four partially-fixed, record in `04-docs/05-modules/05-assets/conformance/CR-092-lane1-registry-step2.md`**

---

## 0 · CAPTURE — the requester's words, verbatim

> *"https://claude.ai/code/artifact/2f979496-886a-47a2-a125-69035d1b3bff - can you
> read this file and create CR and run step for these cahnges?"*

**The artifact is *The Assets menu, screen by screen*** — a 4,415-line blueprint of
every screen behind the **Assets** rail item: 7 addresses, 35 screens, 56 wireframes,
137 fields traced, 6 journeys walked in a real browser, and **24 live specifications**
in its own `AST-B-##` series.

**"run step" is not ambiguous and is not being re-asked (law 13).** It is the
two-step process this branch already ran for `CR-085`, ruled by the PO on
2026-09-10: **step 1 identifies and writes nothing but findings; step 2 fixes.**

---

## 1 · CLASSIFY — MOSTLY DEFECTS, AND SAYING SO IS THE WHOLE POINT

The process is explicit: *"when it is ambiguous it is a DEFECT, not a change,
because filing our misunderstanding as a 'change' quietly converts our error into
the customer's new requirement"* — and in the beta, *"CR is change in product,
defect is product does not do what is expected"*.

**Applied row by row, the 24 split 14 / 10.**

**FOURTEEN ARE DEFECTS — the product does not do what a SIGNED rule, its own help
text, or its own drawn control already promises:**

| id | the promise that is unmet |
|---|---|
| `AST-B-01` | four KPI figures are labelled and render four em-dashes |
| `AST-B-02` | **`BR-WRK-056` is CONFIRMED** and names four ways in; two were never built |
| `AST-B-03` | the help says the service *"must be one your utility has enabled"* and offers no way to see which |
| `AST-B-04` | `BR-AST-038` lets a Billing Clerk log a repair; that role gets a UUID box |
| `AST-B-05` | a badge cites screen `WRK-19` against an explicit ruling that the route is `WRK-24` — ⚠ **but only 2 of its 9 occurrences are wrong; see §4a** |
| `AST-B-06` | rule 8 — four selects draw the product's chevron only because an ancestor happens to supply it |
| `AST-B-10` | ⚠ **AMENDED — the submit is DISABLED, not enabled** (step 1 lane 4, measured `disabled: true` at both widths). The real fault is that it carries NO REASON: the disable reads `templateId` and never `rows.length`, so `title` and `aria-describedby` are both null and a clerk meets a dead control with nothing explaining it |
| `AST-B-11` | B14 12/13/14/16 — three served lists with no toolbar, no sort, no pager |
| `AST-B-13` | **R12** — ten of eighteen fields render label → helper → input |
| `AST-B-15` | B14 rule 18 — two tabs render no description; the other four run 9, 18, 23 and 24 words against a six-to-eight convention |
| `AST-B-18` | three columns are drawn and empty on every row because the client type narrows a 29-field payload to four |
| `AST-B-20` | **Download saves `file.json` containing a 404** |
| `AST-B-23` | the three in-asset lists are hand-built tables, not `DataTable` |
| `AST-B-26` | 27 of 37 helper strings run over ten words, and that is what breaks the field baseline |

**TEN ARE CHANGES — a capability nobody has asked for until now:**
`AST-B-12` (an edit address), `AST-B-14` (opening read), `AST-B-16` (two served
facts), `AST-B-19` + `AST-B-24` (server-side paging), `AST-B-21` (one asset, one
cost), `AST-B-22` (the attention strip), `AST-B-25` (per-panel edit dialogs),
`AST-B-27` (columns nothing can write), `AST-B-28` (save as draft).

⚠ **THE DISTRIBUTION IS ITSELF THE FINDING, AND IT IS HARD-WON LAW 2 AT SCALE.**
The blueprint counts it: **ten of the twenty-four wait on nothing at all** — the
read exists, the route exists, the endpoint exists, the catalogue key exists. What
is missing is a control, a string, a component swap, or the order of two elements.
**This module is not short of capability. It is short of the last connection
between capability and screen.**

---

## 2 · WHAT SIGNED STATEMENT IS BEING REVERSED

**None. Not one.** Checked rather than assumed, and that is unusual enough to state:

* **No ❄️ FROZEN B4/B5 figure is touched.** `04-money-math-rules.md` and
  `05-golden-tests.md` contain no asset vocabulary and `GT-1`..`GT-61` price no
  screen. Nothing here changes what any bill says or costs.
* **Hard rule 4 does not reach these screens.** Nothing in the Assets menu writes
  an invoice, an invoice line, a payment or a journal entry — which is exactly why
  an edit control here is a feature and not a finding, unlike on a payment.
* **Hard rule 8 is OBEYED and was re-checked field by field:** `assets` declares
  no address column. `location_note` is a note; `assigned_address` is derived
  through the metering seam.

**What is being asserted instead is the opposite of a reversal: several signed
rules are UNMET.** `BR-WRK-056` (CONFIRMED), `BR-AST-038`, `BR-SHL-025`, and B14
rules 7, 12, 13, 14, 15, 16, 18 and 31. A rule that is ratified and unbuilt does
not need re-signing; it needs building.

---

## 3 · STEP 0 — IS THE PACKET CURRENT? **YES, AND IT WAS MEASURED**

This is the step the build process puts first and the one most likely to be
skipped, so it is answered here with commands rather than confidence.

**The blueprint was read on ANOTHER BRANCH**: version `2.234.17`, commit
`79c659d7d`, on `claude/fervent-carson-0uksv0`. This branch is `2.237.0`. **A
document written against a different branch is stale until proved otherwise**, so
it was proved:

```
git diff --numstat 79c659d7d HEAD -- <each cited asset file>
  AssetRegistryPage.tsx   identical      AssetAddWizard.tsx      identical
  AssetDetailPage.tsx     identical      AssetFlowPages.tsx      identical
  AssetLifecycleTab.tsx   identical      AssetRetireWizard.tsx   identical
  AssetInventoryTab.tsx   identical
```

**All seven are byte-identical.** The asset files were last touched on 2026-09-05
and 2026-09-07 — *before* the blueprint was read — and `CR-085`'s eight lanes
touched the portal, not assets.

**Four claims were then spot-checked directly against this tip, not inferred:**

| claim | blueprint | this tip |
|---|---|---|
| `raiseWorkOrderPath` in `AssetDetailPage.tsx` | 0 | **0** ✓ |
| `writeBlockedReason` in `AssetInventoryTab.tsx` | 1 — declared, never read | **1** ✓ |
| `writeBlockedReason` in `AssetLifecycleTab.tsx` | 1 | **1** ✓ |
| `WRK-19` cited in `src` | present, and wrong | **6 files** ✓ |

**So every as-built statement in the blueprint holds on this branch.** A lane may
build from it without re-deriving the whole document — but must still re-check the
one file it is about to change, because that is cheap and this guarantee is dated.

---

## 4 · WHAT A LANE MAY NOT BUILD, AND WHY IT IS WRITTEN HERE

⚠ **FOUR SPECIFICATION NUMBERS ARE WITHDRAWN AND MUST NOT REACH A BUILD PLAN.**
The blueprint strikes them in its own register and says so in words; they are
repeated here because **a struck row still looks like a row**, and the place a lane
reads is a work plan, not a document's appendix:

| withdrawn | what it was | why |
|---|---|---|
| `AST-B-07` | the import refusal's stale copy | the import runner left scope 2026-09-11 |
| `AST-B-08` | reopening a finished import run | same |
| `AST-B-09` | three import sources that do nothing | same |
| `AST-B-17` | a registry-wide Work orders tab | withdrawn the day it was drawn, by PO instruction — *"07 Work orders- remove this wireframe"* |

**The numbers are struck and NOT reused**, for the same reason this repository
never renumbers an id: a citation written last week must not land on something
else this week.

⚠ **THE IMPORTS TAB AND ITS FIVE-STAGE RUNNER ARE OUT OF SCOPE**, by instruction
of 2026-09-11. The registry draws **seven** tabs; the blueprint covers **six**.
That is scope, not a defect, and no lane files against it.

⚠ **THE BLUEPRINT CONTRADICTS ITSELF ON ONE NUMBER, AND THE TABLE WINS.** Its
closing paragraph reads *"Twelve live specifications"* while its own register
carries **24 live rows** and its masthead reads *"Specifications 24 · Withdrawn,
not reused 4"*. The document has been revised 48 times and that sentence did not
move with the table. **Count the table.** This is the same failure shape as B14's
rule-count line, which has now been wrong five separate times for the identical
reason: the thing and the pointer to the thing are two edits, and only the first
one feels like the work.

---

## 3a · ⚠ THE BLUEPRINT'S BROWSER WALK CANNOT BE REPRODUCED ON THIS DATABASE — AND STEP 2 BEGINS BY REPRODUCING

**§3 proved the CODE current. It did not prove the DATA current, and the data is
where the blueprint's only un-re-derivable section lives.**

The blueprint says `seed_demo` gave it *"the tenant **brazosbend** with **126
assets**"*, and its section 07 — the six walked journeys, *"the only section whose
findings could not have been produced by reading the source"* — rests on that
population. **No tenant on this database holds 126.** Measured with
`app.tenant_id` set, because without it RLS `FORCE` correctly returns zero and a
naive count reads as an empty database:

| tenant | assets |
|---|---|
| `brazosbend` | **14** (11 before step 1 lane 5 created three) |
| `oak-ridge` | 74 |
| `pine-hill` | 135 |

**Two lanes hit this independently** — lane 5 counted 11/6/10/1 against the
blueprint's 126/73/121/72 and found it is `oak-ridge` that holds 73/121/72; lane 1
measured *"8 meters here vs 109"* on the same tenant.

⚠ **WHAT THIS DOES AND DOES NOT INVALIDATE.** It does **not** touch any source
read: §3's byte-identity still holds and the specifications stand. It **does** mean
**every ROW-COUNT and PAGINATION finding in the blueprint's section 07 is
unreproducible as written** — the four KPI dashes, the three-page pager, the
per-row query counts — and each needs re-measuring on a tenant with the population,
or on `brazosbend` with the numbers restated.

⚠ **AND THE MAINTENANCE PROCESS MAKES THIS A TRAP RATHER THAN A FOOTNOTE.** Its
first step is **REPRODUCE — never fix what you have not seen**. A step 2 lane that
opens `brazosbend`, fails to reproduce a paging defect on 14 assets, and concludes
*already fixed* will close a live row. **Three lanes have already flagged the
shape**: lane 2 records `AST-B-19`/`AST-B-24` as *"structurally real and
unfalsifiable on this data (max 26 reads, max 1 assignment) — a step-2 lane
following REPRODUCE will fail and must not conclude otherwise"*; lane 1 could not
exercise `/assets/geo` because the tenant has **0 geocoded premises**; lane 4 found
`brazosbend` holds **0 work-order templates**, so its Assets door has only its
refusal state.

**So step 2's first act is to pick its tenant per finding, and say which**, rather
than to trust `brazosbend` because the blueprint named it.

## 4a · TWO ROWS OF THIS CR WERE WRONG, AMENDED 2026-09-11 FROM STEP 1

Written here rather than quietly edited, because the CR is what a build plan is
sized from and both errors were inherited from the blueprint by me without being
re-measured.

**`AST-B-10` — I wrote *"the submit stays enabled over nothing"*. It is DISABLED.**
Lane 4 measured `disabled: true` at 1440 and 1280 and `RaiseWorkOrderPage.tsx:179`
is unambiguous. **The blueprint's own States row says "permanently disabled" and is
right; its register row is the half that misleads, and I copied the register.** The
defect is real and is a different defect: the disable reads `templateId` and never
`rows.length`, so it carries **no reason at all** — `title` null,
`aria-describedby` null — and a clerk meets a dead control with nothing to explain
it and nowhere to go. **That changes the work from "read the refusal" to "state a
reason on a control that already refuses".**

⚠ **`AST-B-05` — THE BLUEPRINT'S DONE-TEST WOULD DESTROY THE RECORD, AND A LANE
FOLLOWING IT LITERALLY WOULD HAVE.** Its register says done looks like
*"`rg "WRK-19" 07-frontend/src` returns nothing"*. Lane 4 counted: **9 lines in 6
files, of which 2 are wrong and 4 are CORRECT** — `screenIds.ts:1308/1492/1583/1584`
**are the retirement ruling itself**, plus two minting precedents and
`TemplatesPage.tsx:87`. Executing that done-test deletes the record of the very
decision the fix implements. **Only `RaiseWorkOrderPage.tsx:57` and `App.tsx:1006`
move.**

⚠ **AND THAT ROW BREAKS A HEURISTIC I GAVE EVERY LANE, SO THE HEURISTIC GETS ITS
EXCEPTION HERE.** I told the lanes *"where the blueprint disagrees with itself, the
register wins"* — true for `AST-B-24`, where section 13 calls it *variation by kind*
and the register calls it *the reads table pages on the server*. **On `AST-B-05` it
is the other way round: section 13 says "two files" and is RIGHT, and the register
is the stale half.** So the rule is not *which section wins* but **whichever side
carries a COUNT that can be re-run** — and when neither does, re-measure before
building. A lane obeying my instruction blindly would have shipped the destructive
grep.

## 5 · THE ID SERIES — `AST-B-##` IS THE BLUEPRINT'S, NOT OURS

The blueprint opened its own series deliberately and says why: *"allocating into
any of them would make this analysis look like scheduled work when it is not."*
That was right for a document and is wrong for a build.

**So the mapping is this CR's job, and it happens in step 1, not before:** each
live `AST-B-##` becomes either a `DEF-MET-####` row (the fourteen) or a story
under this CR (the ten), and **the `AST-B-##` number is carried in the row** so a
reader holding the blueprint can find its fate. Nothing is renumbered in the
blueprint itself; it is a published artifact and stays as it is.

---

## 6 · THE TWO STEPS, AND WHAT EACH MAY WRITE

Ruled by the PO 2026-09-10 and unchanged:

**STEP 1 — IDENTIFY. It writes findings and NOTHING ELSE.** No lane edits a
component, a catalogue, a route or a register row in step 1. Each lane produces a
conformance document under `04-docs/05-modules/…/conformance/` and a list of
proposed defect rows with their evidence. **A lane that fixes something in step 1
has broken the step**, because the point of splitting is that the whole surface is
read before any of it moves.

**STEP 2 — FIX.** Defect rows are filed, then fixed, each proved red first, each
walked in a browser at the widths the audience requires — and for this module that
is **desktop only**: the Assets menu is a clerk and utility-admin surface, so
**1280 and 1440, and nothing narrower** (PO ruling 2026-09-10: *"Calrk and Utility
admin is laptop, and desktop application - not mobile"*). There is no portal screen
in the Assets menu at all.

---

## 6a · THE FIVE RULINGS THAT SET STEP 2's SCOPE (PO, 2026-09-12)

Verbatim, and each is in `12-governance/02-decision-log.md` with its reasoning.

| # | asked | ruled |
|---|---|---|
| 1 | how much of the 35 | ***"c) All 35"*** — **my recommendation of (b) was declined** |
| 2 | the two wordless tabs vs the 22 Aug ruling | ***"a) Fix the figures"*** — D9 STANDS, the tabs stay wordless |
| 3 | 16px or 20px between fields | ***"a) 20 everywhere — the anatomy wins"*** → B14 rule 39 amended |
| 4 | a clerk typing a technician's id | ***"a) Let a clerk read the crew list (name + email only)"*** → `BR-AST-533` |
| 5 | raise work order on a retired asset | ***"a) Show it disabled, with the reason"*** → `BR-AST-534` |

**ALL THIRTY-FIVE ARE IN SCOPE** — 7 high, 16 medium, 12 low; 30 Assets, 4 shared
table, 1 governance.

⚠ **THREE QUESTIONS ARE OPEN AND NO LANE MAY BUILD THEM.** *One asset, one cost* ·
*the shared table's sort and pager* · *the sub-meter's allocation share*. A lane
meeting one of these stops at the boundary and says so — it does not choose a value
(prime directive). ⚠ **The shared-table rows are the trap here: they are IN SCOPE
as findings and their FIX is unruled, so a lane may state the change and must not
make it** — four rows reaching 54 lists is not a decision to take inside an Assets
pass.

⚠ **AND RULING 2 CARRIES A TRAP OF ITS OWN.** *Fix the figures* means the two tabs
**stay wordless** — a lane that "restores the missing descriptions" reverses a PO
ruling of 2026-08-22 **and** breaks `AssetRegistry.test.tsx:760-784`, which asserts
that absence by name. The work is the em-dashes, not the prose.

## 6b · FINAL SCOPE (PO, 2026-09-12) — FORTY ITEMS, AND THE TEN CAPABILITIES ARE IN

> ***"Build 7 the task cannot be done at all today - yoou ahve to implment these also"***
> ***"please add 10 new capabilities also - implment them"***

**Step 2 builds everything.** Both halves of the earlier question are answered the
same way, so the recommendation to defer the ten is withdrawn.

| | count | |
|---|---|---|
| **MAINTENANCE** | **23** | the task exists and the product does it wrongly |
| **BUILD** | **17** | 7 findings where the task cannot be done at all, **plus the blueprint's 10 new capabilities** |
| **TOTAL** | **40** | |

**The ten capabilities, now in scope:** an edit address for an asset (`AST-B-12`) ·
the opening read (`AST-B-14`) · two served Overview facts (`AST-B-16`) ·
server-side paging, front and back (`AST-B-19`, `AST-B-24`) · one lifetime cost
(`AST-B-21`) · the attention strip (`AST-B-22`) · the six per-panel edit dialogs
(`AST-B-25`) · the allocation share (`AST-B-27`) · Save as draft (`AST-B-28`).

⚠ **TWO OF THE TEN CARRY A CONSTRAINT STEP 1 FOUND AND THE BLUEPRINT DOES NOT NAME.**
`AST-B-25`'s six pencils sit on a panel set that **does not exist** — the Overview
draws FOUR panels (`Specifications`, `Assignment`, `Warranty & supplier`,
`Lifecycle`), so `AST-B-16`'s header work sequences **before** it. And `AST-B-28`
has **no button to fix**: neither asset wizard passes `WizardFrame`'s `exit`, so
there is no Save as draft on any of the four add steps or three retire steps — the
spec's *"the button was drawn and saved nothing"* is true of the five customer
wizards only.

⚠ **STILL OUT OF STEP 2, BY RULING 7:** the shared-table rows (sort's third
click, first/last page, the two title sizes, the KPI gap). **Their own CR, sized on
its own** — four rows reaching 54 lists is not a risk to take inside an Assets pass.
A lane meeting one states the change and does not make it.

⚠ **THAT CR NOW EXISTS: `CR-093-BRC01`**, raised 2026-09-12 —
`change-requests/CR-093-BRC01-shared-component-findings.md`, with every figure
re-measured at `672f2f515` rather than copied from the rows.

⚠ **AND WRITING IT FOUND THAT THE COUNT IS FIVE, NOT FOUR — §1's *4 shared-table*
AND THIS PARAGRAPH BOTH UNDERSTATE IT BY ONE.** The rows, each with the older filing
it duplicates where there is one:

| # | the finding | this pass filed | already open since |
|---|---|---|---|
| 1 | the sort's third click never clears | `DEF-SHL-4946` | (`DEF-MET-4957`, dup) |
| 2 | the pager has no first/last jump and no *Page N of M* | `DEF-MET-4958` (dup) | **`DEF-449`, 2026-08-21** |
| 3 | two page-title sizes, 136 heads at the wizard size | `DEF-SHL-4947` | — |
| 4 | rule 15's row-action cap, 16 cells over it | `DEF-SHL-4948` | **`DEF-2453`, 2026-08-30** |
| 5 | the KPI strip's 6px gap | `DEF-SHL-4949` | — |

**The two dates in the decision log's ruling 7 — *"already filed weeks ago
(2026-08-21 and 2026-08-30)"* — are rows 2 and 4, so the ruling was counting FIVE
while its own sentence listed four.** Row 4 is the one that fell out of the
enumeration: it has an Assets-specific twin (`DEF-MET-4956`, the six controls in one
cell on the registry) and was read as an Assets finding on one pass and a shared one
on the other. ⚠ **THE PO'S RULING IS UNAFFECTED — *(b), their own change request*
applies to the shared-component findings as a class**, and a fifth row of the same
kind does not need re-asking (law 13). `CR-093-BRC01` carries all five and says so.
**The lesson is the one this CR keeps re-learning: a list written by description
rather than by id cannot be checked, and this one was wrong for a day in a scope
line.**

## 6d · THE TEN CAPABILITIES — SHOWN BEFORE BUILT, AND THREE ARE APPROVED

The build skill's first rule and the PO's ruling of 2026-09-10 both say the same
thing: **draw it, show it, then build — the middle step is not optional.** Assets
had **no drawn specification in the tree at all**, so the drawings were extracted
first (`08-screen-layouts.md`), then the ten were put to the PO.

| # | capability | state |
|---|---|---|
| `AST-B-21` | one lifetime cost, both halves named | ✅ **APPROVED** — *"Yes build this"* |
| `AST-B-27` | the sub-meter's allocation share | ✅ **APPROVED** — *"this is correct - build it"*, and the four words ratified |
| `AST-B-28` | Save as draft | ✅ **APPROVED** — *"Can you fix this"* |
| `AST-B-22` | the attention strip | ✅ **APPROVED** |
| `AST-B-16` | two served Overview figures | ✅ **APPROVED** |
| `AST-B-25` | a pencil per Overview panel | ✅ **APPROVED** |
| `AST-B-12` | an edit address for an asset | ✅ **APPROVED** — **BUILT `2.239.9`**: `/:tenant/assets/{id}/edit` (`AST-09`), the dialog deleted, and TWO doors point at it (the registry pencil and a new Edit in the asset's own header) |
| `AST-B-19` + `AST-B-24` | server-side paging | ✅ **APPROVED** — and the PO added *"you can do actual figures"*: a lane may SEED the data a finding needs |
| `AST-B-14` | the opening read | ✅ **APPROVED** — *"Build it as drawn — move it to step 2"*. ⚠ **`MeasuringSpecStep` ONLY**, never `DeviceSpecStep`: a device has no register and no multiplier for the warning to describe. It is a MOVE out of `AssignmentStep`, not an addition |

✅ **ALL TEN APPROVED, 2026-09-12. Nothing is awaiting.** They are wave C, and wave C cannot start until wave B lanes 2 and 5 land — five of the ten are in `AssetDetailPage.tsx` and three in `AssetAddWizard.tsx`, both of which have a live lane in them.

**The four ratified allocation words** — the first customer-facing words these
values have ever had, so new keys in eleven catalogues under B14 rule 35:
`rubs` → **Share of the building's total** · `sqft` → **By floor area** ·
`equal` → **Split equally** · `absorb` → **Owner absorbs**.

⚠ **AND THE DRAWINGS CORRECTED THE COORDINATOR ON THE OVERVIEW'S OWN SHAPE.** I
told the PO the Overview redesign had *"four pencils, not six"*, reasoning from step
1's measurement of **today's** live screen (four panels: Specifications, Assignment,
Warranty & supplier, Lifecycle). **Screen 08 draws THREE wireframes, not one**, and
the panel set **varies by asset kind**: a meter gets **six panels with four
pencils**, a non-measuring asset **four**, and the one carrying the attention strip
**five**. Step 1's sequencing point stands — the pencils cannot land on today's
panels — but the count was wrong, and it was wrong because **I compared a
redesign to an as-built and reported the difference as a fact about the redesign.**

## 6c · THE UI SKILL IS MANDATORY, AND IT IS THE ONLY ONE

**`.claude/skills/react-tailwind-css-ui-generator/SKILL.md` is the repository's one
skill** and every lane that writes TSX invokes it **before its first line and again
before calling a screen done** — its own description says exactly that. §1 of this
CR already names it as the third authority: *"not a third rule set: it is how the
two above are obeyed in this tree, and it is what turns a violation from arguable
into nameable."*

**It exists because of this module's own failure shape**, which it states in its
first screen: *"every way this repo gets screens wrong passes `tsc`, passes eslint,
passes every test, and passes every gate — no gate here reads rendered output."*
The four traps it carries that bear hardest on this CR:

* **A Tailwind utility is emitted ONLY for a file on `07-frontend/src/styles/route-b-migrated.txt`.** Written in a file that is not listed, it renders as **nothing at all** while `tsc`, eslint and every `toContain` assertion pass. All fourteen asset feature files ARE listed (§09 of the blueprint checked this) — **but the kit files a wave-A lane touches may not be.**
* **The component kit is 45 components.** A second table, a third button size or a bespoke dialog is a defect, not a contribution.
* **Eleven catalogues.** A missing key reaches a clerk as SILENCE, not an error.
* **The audience decides the widths.** Assets is clerk and utility-admin, so **1280 and 1440, and nothing narrower** — there is no portal screen in this menu.

## 7 · VERSION

| version | wave |
|---|---|
| **`2.237.1`** | step 2 wave A — the field anatomy |
| **`2.237.2`** | step 2 wave B lane 3 — the asset type saves, the purchase date is on the page |
| **`2.237.3`** | step 2 wave B lane 5 — the add-asset wizard's service is a list you pick from |
| **`2.237.4`** | step 2 wave B lane 4 — a clerk names the technician, a greyed-out button says why |
| **`2.237.5`** | step 2 wave B lane 1 — the registry: screens 01–06 |
| **`2.237.6`** | step 2 wave B lane 2 — one asset: the raise-work-order door on the header and the Maintenance tab, the jobs on an asset drawn instead of discarded, the register named in words and the read log back above the fold |
| **`2.237.8`** | step 2 wave C lane 3 — **server-side paging inside an asset** (`AST-B-24`) and the last three unpaged registry reads. Six endpoints gained a page parameter: `/assets/{id}/reads`, `/assignments` and `/maintenance` answer the `{count, next, previous, results}` envelope (`DEF-MET-4995`, filed by the lane before it fixed it); `/assets/stock`, `/assets/lifecycle` and `/assets/geo` carry a `<key>_window` beside their existing keys (`DEF-MET-4962`'s remainder, now closed). Contract in **A11 Addendum r7**; rules `BR-AST-535`/`536`. ⚠ **THE THREE IN-ASSET ROUTES CHANGE SHAPE AND FOUR SHIPPED FRONT-END CONSUMERS READ THEM** — `AssetDetailPage.tsx` (twice), `AssetFlowPages.tsx`, `ReadDetailPage.tsx` and `accountDetailTabs.tsx`, all through three wrappers in `07-frontend/src/api/endpoints.ts`. `AST-B-19`, the front half, is sequenced after this and after wave C lane 1. |

⚠ **ROWS 2–4 WERE READ OFF `CHANGELOG.md` AND THE BRANCH LOG, NOT SUPPLIED BY
THOSE LANES.** Each of them bumped the version correctly and none added itself
here, so this section said "wave A and wave B lane 1" while four waves had
landed — which is the pointer-and-thing problem this repository keeps having,
one table smaller. If a description below misstates a lane's work, that lane
should correct its own row rather than this note being taken as its account.

Later waves take the next fix number from `10-scripts/allocate.py version
--bump fix`, **re-verified at push time** — this lane had `2.237.3` and then
`2.237.4` taken from under it by siblings pushing mid-lane, and only the
re-verify caught it. The CR is not done until every wave has landed and this
table names each.

---

## 8 · ROLLBACK, STATED BEFORE ANYTHING SHIPS

**Every one of the twenty-four reverts independently**, because not one of them
changes a read that already exists — they add a control, a string, a column, an
address or a served figure. **Nothing is refunded and no issued bill changes**;
the Assets menu writes no financial row. The two that touch a server envelope
(`AST-B-19`, `AST-B-24`) revert as one commit each and leave the existing
unpaginated response in place.

---

## Trace

* **Source:** artifact `2f979496-886a-47a2-a125-69035d1b3bff`, *The Assets menu,
  screen by screen*, read at `2.234.17` / `79c659d7d`, 4,415 lines.
* **Baseline verified against** `claude/hi-0jmv62` @ `ed1ac08d4`, 2026-09-11.
* **Process:** `12-governance/13-change-process.md` · `04-docs/02-decisions/12-engineering-plan.md` Addendum r11 · `12-governance/22-product-maintenance-process.md`.
