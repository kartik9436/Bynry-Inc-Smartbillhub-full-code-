# The Accounts menu — every screen, and where its drawing is

⚠ **SEVENTEEN ROUTES, AND THE BLUEPRINT DRAWS NINETEEN SCREENS — amended
2026-09-12 by `CR-094-BRC01` step 2 wave G.** The index below was built from
§§01–17, which are the routes that existed; the blueprint's own §10 numbers two
more, **18 Complaints** and **19 Services**, and both are now BUILT. Their rows
are at the foot of the table. **The `17` elsewhere in this file counts ROUTES
AUDITED and is not a count of the document's screens.**

**The drawn specification for the Accounts screens.** Built 2026-09-12
from `05-prototype/02 Accounts Menu Blueprint.pdf` on the PO's instruction
*"extract all screens and run step 1"*, for `CR-094-BRC01`.

⚠ **READ THIS BEFORE YOU BUILD ANYTHING ON THIS MENU.** The UI skill's §1 opens
with the rule this file exists to satisfy: *"A URL is not a drawing. 'The design
doc' is not a drawing. A drawing a lane cannot open is a drawing that will not be
built."* Every row below names the exact pages of the blueprint that draw that
screen, and the two commands that put them on your disk as images.

---

## HOW TO OPEN A DRAWING — two commands, and the sha is load-bearing

```bash
# 1 · fetch the blueprint AT A PINNED COMMIT, never at a branch name
git show "033981d4f39f4b3e703639c074df1f8df7082a6d:05-prototype/02 Accounts Menu Blueprint.pdf" > /tmp/accounts.pdf
sha256sum /tmp/accounts.pdf     # must begin c8d596bb505f5020ce4b9474

# 2 · render the pages you need (scale 2 is legible; mkdir first, it will not)
mkdir -p /tmp/acct && python3 10-scripts/pdf/pdf_render.py /tmp/accounts.pdf /tmp/acct 2 "51,52,53"
```

⚠ **PIN THE COMMIT, NOT THE BRANCH.** The file lives on the repository's default
branch `claude/confirm-understanding-3ktufc`, and a branch name is a moving
target — the exact hazard hard-won law 11 records for `origin/<branch>` being
resolved twice. `033981d4f` is the commit that added it; the `sha256` is there so
a lane can prove it fetched the same bytes this index was built from.

## ⚠ THE TEXT LAYER IS NOT A SUBSTITUTE FOR THE PAGE, AND THIS IS MEASURED

`10-scripts/pdf/pdf_text.py` extracts 309 KB of text from this document and it is
**unsafe for anything that carries a number**:

| what | text layer | image |
|---|---|---|
| prose, labels, headings | **reliable** | reliable |
| **every digit** | **`&`** — the cover's figures read `& of &&` | reliable |
| specification ids | **dropped 8 of 21** (`ACC-S5`, `S7`, `S14`–`S17`, `S20`, `S21`) | reliable |
| figure captions | found **1 of them** | reliable |
| the wireframes themselves | **absent** — vector art | reliable |

**Measured 2026-09-12: 101 of the 242 pages extract under 150 characters and are
essentially pure drawing; 46 more are mixed. So 147 pages must be READ AS IMAGES,
and every figure in this CR was.** A lane quoting a number from the text layer is
quoting `&`.

---

## THE SEVENTEEN SCREENS

`p` = page of the blueprint PDF. Ranges are inclusive and were derived from the
document's own section headings, then spot-checked against rendered pages.

**The `state` column is the blueprint's own chip**, and it is one of four:
`EXISTS BEHIND` · `NEW READ` · `NEW BUILD` · `BLOCKED`. A screen no specification
covers carries `NO COMMITMENT` — **that absence is the finding, not an
oversight.** These extract reliably from the text layer and were taken from it.

⚠ **THE SCREEN IDs (`S21`, `S23` …) ARE DELIBERATELY ABSENT FROM THIS TABLE.**
Each screen's header carries its canonical A1 id beside the route — `S23` for
Change plan, read off the rendered page — but **the text layer drops most of
them**, so filling this column from extraction would fabricate ids for the
ticket vocabulary. **A lane reads its own screen's id off its own header page**,
which is the first page of its range below.

| # | Screen | Route | Drawn at | State | Notes |
|---|---|---|---|---|---|
| 01 | **Accounts list** | `/:tenant/accounts` | **p3–5** | EXISTS BEHIND | the register; seven sibling tabs live here |
| 02 | **Account detail** | `/:tenant/accounts/{accountId}` | **p6–59** | EXISTS BEHIND | **54 pages — by far the largest.** Every tab, every panel |
| 03 | **New account wizard** | `/:tenant/accounts/new` | **p60–65** | EXISTS BEHIND · ⚠ **the drawn `NO COMMITMENT` chip is STALE — `DEF-CUS-5084`** | five steps · **three register rows name it** (`ACC-S4`, `ACC-S6`, `ACC-S18`) |
| 04 | **Move-in wizard** | `/:tenant/accounts/{accountId}/move-in` | **p66–74** | EXISTS BEHIND | five steps become six |
| 05 | **Move-in · standalone** | `/:tenant/move-ins/new` | **p75** | EXISTS BEHIND · ⚠ **no chip drawn, and NO register row names it — `DEF-CUS-5084`** | shares its page with 06 |
| 06 | **Service request capture** | `/:tenant/requests/new` | **p75–85** | EXISTS BEHIND · ⚠ **no chip drawn, and NO register row names it — `DEF-CUS-5084`** | five of its six steps rebuilt · ⚠ **its step-1 drawing is NOT the as-built — `DEF-CUS-5085`, see the note under this table** |
| 07 | **New connect wizard** | `/:tenant/connections/new` | **p86–97** | EXISTS BEHIND · ⚠ **no chip drawn, and NO register row names it — `DEF-CUS-5084`** | ✅ **EIGHT, AS DRAWN, SINCE 2026-09-16** (`DEF-CUS-5186`). This read *"nine steps become eight"* for three weeks. The blueprint's step 1 is **Owner & scope** — *"Two steps, merged, because they are one question"* — and the PO ruled the merge twice, on 2026-09-12 (*"merge the first and second step"*) and again on 2026-09-16. Walked in a browser 2026-09-16 at 1280 and 1440: eight cells, `scrollWidth == clientWidth` at both |
| 08 | **Move-out wizard** | `/:tenant/accounts/{accountId}/move-out` | **p98–106** | EXISTS BEHIND | **six steps, drawn and built** — `DEF-CUS-5077`: this read *"six steps become five"* and was wrong in both directions. The blueprint's routes line reads `S20 · six steps`, its caption reads *"All 6 screens of this flow"*, and `BR-SHL-046` (PO, verbatim *"6 steps"*) is the ruling that made it six. Walked 2026-09-12: six |
| 09 | **Move-out · standalone** | `/:tenant/move-outs/new` | **p107** | EXISTS BEHIND · ⚠ **NO COMMITMENT** | shares its page with 10 |
| 10 | **Close-out** | `/:tenant/accounts/{accountId}/close-out` | **p107–111** | EXISTS BEHIND · ⚠ **NO COMMITMENT** | the screen with no story that owns it |
| 11 | **Transfer wizard** | `/:tenant/transfers/new` | **p112–119** | EXISTS BEHIND | five steps · ✅ **REBUILT 2026-09-12 to the SALE the PO ruled** (`DEF-CUS-5075`) — it shipped the replaced job and its commit answered `422 buyer_required`, so no property could be sold. ⚠ The TAB it lands on still describes the old job (`DEF-CUS-5092`) |
| 12 | **Disconnect wizard** | `/:tenant/disconnects/new` | **p120–131** | ✅ **UNBLOCKED 2026-09-12** | `OQ-CUS-1810` closed by the PO: the notice period is the tenant's own `BR-PAY-017` setting, the clock counts **business days**, the roll uses that tenant's `holiday_calendars`, and an early date **warns without blocking** (*"give a message but allow it"*). The roll is built and served; step 2's protections now read their own endpoint (`DEF-CUS-5076`) |
| 13 | **Change plan wizard** | `/:tenant/accounts/{accountId}/change-plan` | **p132–133** | EXISTS BEHIND | three steps · ⚠ **no stepper is rendered — the code models three steps and draws no rail** |
| 14 | **Payment plan wizard** | `/:tenant/accounts/{accountId}/payment-plan` | **p134–135** | EXISTS BEHIND | three steps · ⚠ **same — no rail on the entry screen** |
| 15 | **Account import** | `/:tenant/accounts/import` | **p136–140** | EXISTS BEHIND | reopening a finished run to fix rejected rows |
| 16 | **Service requests list** | `/:tenant/requests` | **p141** | EXISTS BEHIND | shares its page with 17 |
| 17 | **Service request detail** | `/:tenant/requests/{requestId}` | **p141–148** | EXISTS BEHIND | the five outcomes of a request |
| **18** | **Complaints** — the tab, its four-step form, its record | `/:tenant/accounts?tab=complaints` · `/:tenant/complaints/new` | **p39–45** | ⚠ **THE DRAWING'S `NEW BUILD · NO COMMITMENT` CHIPS ARE STALE FROM 2026-09-12 — BOTH ARE BUILT** (`CR-094-BRC01` step 2 wave G, `2.239.7`) | **six drawings.** ⚠ **NOT IN THE SEVENTEEN** — this index was written from §§01–17 and the blueprint numbers these 18 and 19 itself. A complaint is a WORK ORDER of type `Consumer Complaint`; `BR-CUS-1049` |
| **19** | **Services** — the tab, its form, its record, and the kinds behind both | `/:tenant/accounts?tab=services` · `/:tenant/services/new` | **p46–54** · the kinds screen **p55–56** | ⚠ **SAME — the chips are stale; the tab and the form are built, the drawn `Service fees` step is NOT** | **nine drawings.** The fee step is the drawing's own *"proposal"* (p219) on a model `work_orders` does not have; `BR-CUS-1049` records why it is absent |

⚠ **AND THREE OF THOSE ROWS MOVED ON 2026-09-12 — `CR-094-BRC01` step 2 wave 4.**
Screen **12 is no longer `BLOCKED`**: `OQ-CUS-1810` was closed by the PO and the
earliest-lawful-cut calculation is built, served and on screen. Screen **11 was
rebuilt** to the job the PO ruled on 2026-09-01, and screen **08's step count
was simply wrong** in this table. Screens 09 and 10 keep `NO COMMITMENT` — that
is a statement about what nobody has undertaken, and repairing their transport
did not create a commitment.

⚠ **FOUR ROWS ABOVE WERE THE FINDINGS, NOT THE FURNITURE.** Screen **12 was
`BLOCKED`**. Screens **03, 09 and 10 carry `NO COMMITMENT`** — nobody has
undertaken to build anything on them, and by the blueprint's own rule that
absence is a finding. Screens **13 and 14 model steps the product never draws a
rail for**, which is why the blueprint says their steppers *"could not be
confirmed at all"*.

⚠ **AND ON THE FOUR STARTING-SERVICE SCREENS THE CHIP IS EXACTLY BACKWARDS, SO
IT CANNOT BE READ AT ALL ON THIS MENU — `DEF-CUS-5084`, corrected in the table
above 2026-09-12.** The paragraph above states the chip's own meaning correctly;
the chip itself is wrong about these four, each counted against §12's own rows:

| screen | chip drawn | register rows that actually name it |
|---|---|---|
| **03** new account | ⚠ **`NO COMMITMENT`** | **three** — `ACC-S4` (dates), `ACC-S6` (expired holds), and `ACC-S18`, whose entire subject is that wizard's own review step, drawn across six pages as remedy `R8` |
| **05** move-in standalone | none | **none** |
| **06** request capture | none | **none** — and §13 rebuilds five of its six steps |
| **07** new connect | none | **none** — it lost its step on 2026-09-16 (`DEF-CUS-5186`) and still no register row names it |

**So the door every counter sign-up goes through is marked as uncommitted while
three rows commit to it, and the three screens with a genuine, measured absence
of commitment carry nothing.** The chip was true when the series was
`ACC-S1…ACC-S10` and was not re-walked when the series grew to twenty-one — a
snapshot with no status column, which is the prime directive's own shape one
level out. ⚠ **Read §12's Screens column; do not read the chips.**

⚠ **ROWS 09 AND 10 ARE DELIBERATELY NOT TOUCHED HERE** — they are the
ending-service screens and belong to `CR-094-BRC01` step 2 wave A. Row 10
(Close-out) is separately described in this document as *"the screen with no
story that owns it"*, so its chip may well be right; nobody on this lane
measured it.

⚠ **AND THE CAPTURE'S STEP-1 DRAWING CLAIMS TO BE THE AS-BUILT AND IS WRONG
FOUR WAYS — `DEF-CUS-5085`, measured against the running product at `2.239.0`
in Chromium at 1280 and 1440.** Page 75 says of this flow: *"All 6 screens of
this flow, drawn at 1280 and buildable as drawn. Real app shell, real stepper,
real field labels in the order the component renders them."* Against the screen:

1. **The drawing omits the customer-category group entirely** — seven radios the
   product renders FIRST and gates the step on, put there by the PO on
   2026-08-25 and quoted in the code at `ServiceRequestCapturePage.tsx`: *"on
   this screen - apply as - we need customer categories that we have from
   settings - ehre as drop down"*. **A lane building the drawing deletes a
   control the PO asked for.**
2. **It draws Date of birth and Driver's licence as filled inputs** (`if known`,
   `TX ••••882`). Both are stated absences in the product, because
   `_clean_capture` refuses `dob`, `date_of_birth` and `gov_id_last4` BY NAME.
   Building the drawing rebuilds the dead UI those two code comments exist to
   prevent, and `BR-CUS-092(d)` is quoted at the site: *"a false security
   promise over a government identifier is worse than an absent one"*.
3. **The drawn field order puts `Channel` first**; the product puts the category
   group first, which is the PO ruling above.
4. **It marks `Channel *` required and leaves the category unmarked** — the
   opposite of what the code gates on. `emptyCaptureForm` seeds
   `CAPTURE_CHANNELS[0]`, so `channel` can never be empty and nothing refuses on
   it; the CATEGORY is what `validate()` refuses on. ⚠ **The product was wrong
   here too, in its own way** — the gated group carried no asterisk, no
   `required` and no `aria-required`, so its refusal read *"Fill in what's
   marked above"* over a screen with no mark on it (`DEF-CUS-5082`, fixed at
   `2.239.0`) — **but the fix is to mark the CATEGORY, not to copy the asterisk
   onto `channel`.**

**So for screen 06's step 1 the drawing is the STALE record and the screen is
the current one.** ⚠ **THIS IS NOT THE GENERAL RULE AND MUST NOT BE READ AS
ONE.** `CR-094` and B14 rule 37 both hold that the drawing is the answer, and
the blueprint's own screen-03 section says *"every drawing below is the wizard
as it should be, not as it is"*. The exception here is narrow and is this page's
own doing: it alone claims to be a TRANSCRIPTION of the as-built, and on four
counts it is not. Where the blueprint PRESCRIBES — the other five steps of this
flow, and every other screen in the document — it still wins.

## THE REST OF THE DOCUMENT

| Section | At | What is there |
|---|---|---|
| §01 the standards | p2 | the rule set in precedence order — B14 wins, r10 is its source |
| §09 where screens depart from the rules | p149 | the one repo-wide violation |
| **§10 the remedies, drawn** | **p150–206** | **`R1`–`R9`, the redrawn screens** — this is what a build lane works to |
| §12 the specification register | p207–209 | **SEVENTEEN rows**, ids running to `ACC-S21` — each with *what done looks like on screen*. ⚠ **Not 21 and not 10; see the closing note.** |
| §13 what this pass changed | p209–224 | the analysis's own changelog |
| §14 appendix | p225–242 | the whole document compressed |

---

## WHAT THIS INDEX DOES **NOT** CLAIM

**It is a map, not a transcription.** Nothing here restates what a drawing shows;
every row points at the page so the drawing itself is the authority. That is
deliberate — the Assets pass proved that a lane building from a prose summary of
a wireframe builds the summary, and the drawing is what the PO agreed.

⚠ **AND THE BLUEPRINT IS ITSELF AN AUDIT OF A MOMENT.** Every as-built statement
in it was true at **2.234.15, commit `2824c2e5`, 2026-09-10**. The product is at
**2.237.10** — **219 commits later.** Measured on 2026-09-12: of those commits,
only **six files** in the Accounts surface moved, and **five are heading-size
matcher fixes from B14 rule 40**; the sixth is `UnitPricingPanel.tsx` (+72/−18).
**So the audit's reading still holds** — but a lane proves its own row against the
running product before building, never against this sentence.

⚠ **THE FIGURE THAT DISAGREED WITH ITSELF IS NOW SETTLED — §12 LISTS SEVENTEEN
ROWS (read end to end 2026-09-12, `CR-094-BRC01` step 1 lane 2, `DEF-GOV-5007`).**
⚠ **THIS PARAGRAPH TOLD EVERY LANE TO QUOTE `21` AND `21` WAS THE HIGHEST ID, NOT
A COUNT** — and the two differ here because the series is shared between two uses.
The rows are `ACC-S1` `S2` `S3` `S4` `S5` `S6` `S7` `S8` `S9` `S10` `S14` `S15`
`S16` `S17` `S18` `S20` `S21`. **`ACC-S11`, `ACC-S12` and `ACC-S13` are §10 FINDING
ids** — the alphabetical default, the missing `/`, the six decimals of money — and
carry no register row. ⚠ **AND SO IS `ACC-S19`, WHICH THIS PARAGRAPH SAID *"appears
nowhere in the document"* UNTIL 2026-09-12 — IT IS THE TAG ON REMEDY `R9`, PRINTED
BESIDE ITS HEADING ON PAGE 198** (*"R9 · The customer you already have, flagged where
the details are typed  `ACC-S19`"*, read off the rendered page by `CR-094-BRC01` step 1
lane 1, the same hour lane 2 settled the count). **So all four of the missing numbers have
a home in §10 and none of them is a gap** — `S11` `S12` `S13` are finding ids and `S19` is
a remedy tag — which is a tidier rule than *three findings plus one that does not exist*,
and it matters because a lane sent looking for `ACC-S19` and told it is not there stops
looking. The cover's
**10** is wrong too, and so is the register's own explainer box, which reads
*"`ACC-S1`…`ACC-S10` is a series minted for this document"* directly above a table
that runs to `S21`. **So quote SEVENTEEN ROWS, IDS RUNNING TO `ACC-S21`, and say it
came from counting §12's rows on the rendered pages 207–209.**

⚠ **AND TEN OF THE SEVENTEEN NAME SCREEN 02** — `ACC-S1` `S3` `S5` `S6` `S8` `S14`
`S15` `S16` `S17` `S21`. **`ACC-S4` (every date field behaves the same way) names
`03 · 04 · 08 · 10 · 11 · 12 · 13 · 14` and NOT `02`.**

---

## ⚠ THE ONE DRAWING THIS INDEX TRANSCRIBES, AND WHY IT BREAKS ITS OWN RULE

Everything above is a MAP. **This section is a TRANSCRIPTION**, and the exception
is narrow and has a reason: `R7` was BUILT on 2026-09-12 (`CR-094-BRC01` step 2
wave F), and the UI skill's §1 says the labels must be *"in front of you while you
type"* — *"a link gets skimmed; a quote gets built"*. So the drawing is quoted
here, for the screen that exists, rather than pointed at. **Where this section and
the rendered page 191 disagree, the PAGE wins and this is the stale record.**

### R7 · `ACC-S17` — THE `Accounts` TAB ON A MASTER ACCOUNT

**Drawn at p189–192.** Route `/:tenant/accounts/{accountId}?tab=accounts`, on S21.
**Shown ONLY when the account's `kind` is `master`, immediately after `Overview`.**
⚠ **THIS LINE READ *"thirteen tabs instead of twelve"* UNTIL 2026-09-23**, when
`BR-CUS-1094`'s `Units` tab landed beside it: a master now has **fourteen** and an
ordinary account still has twelve. Both conditional tabs are inserted by
`accountTabIds`, which is the one place the insertion happens.

**The ruling, verbatim (PO 2026-09-12):** *"if the account is of master account,
then after the overview tab, it should show the accounts that are connected to
that master account"*, then, confirming the walk: *"this is correct - you can see
the premises -> units -> regular accounts assocaited with it"*. The blueprint's
own wording of the same ruling: *"change the premises tab to accounts tab. And in
that, show only one table with all the accounts that are associated with this
master account and with their account status."*

**ONE TABLE. `BR-CUS-1048` is the rule; nothing else is on the tab.**

| the table's columns, LEFT TO RIGHT as drawn | what fills it |
|---|---|
| **Account** | `account_no`, a link to that account's own detail — **except on the master's own row**, which is plain text beside a `This account` pill and has no link back to the page you are on |
| **Unit** | `unit_label` for a tenant · ***Common areas ×N*** for the master, from `covered_units` (`covered_unit_ids(account)` — this account's own OPEN service agreements) · a dash where neither can be read |
| **Occupant** | the primary contact's name (`name`), the same value the register's NAME column shows |
| **Kind** | `Master` / `Regular`, from the server's own `kind` through `customers.accounts.kind.*` |
| **Status** | the TENANT's own `status_name` on a pill, tone from the seeded code (`BR-CUS-055`) |
| **Since** | `opened_at` through the shared `DateCell` |
| **Balance** | `MoneyCell`, right-aligned. ⚠ **NO FOOT. NO TOTAL. EVER** — see below |
| **Actions** | one `Open account` icon per tenant row; the master's own row carries none |

**The toolbar** is the kit's: the search (*"Account #, occupant, or unit…"*), one
**Status** filter chip, the column chooser, and the pagination footer. All of it is
served by `GET /accounts?f.premises_id=` — **no new endpoint, no new table and no
new relationship** (`ACC-S17`: *"The tab is the work."*).

**THREE ABSENCES THAT ARE THE DESIGN, NOT GAPS:**

1. **No total under `Balance`.** The blueprint gives the figure and the reason:
   its six rows sum to **`$810.95`**, which is the owner's own **`$69.60`** plus
   **`$741.35`** owed by three tenants who have nothing to do with each other.
   *"Printing it where an owner can see it invites exactly the wrong conclusion."*
2. **No parent/child tree and no rolled-up balance.** `BR-CUS-068` — a master is
   an ordinary account row with one column set. *"Related by address, not by
   link"*, which the tab says in its own closed disclosure.
3. **No `Needing attention` quick filter.** It is TWO statuses rather than one and
   the server publishes no such filter; deriving it client-side would break
   `NFR-3`'s server paging.

**THREE PLACES THE BUILD DEPARTS FROM THE DRAWING, each stamped rather than
absorbed:**

* the drawn `All | Active | Needing attention | Closed` **segment strip** is ONE
  **filter chip** — B14 rule 12 fixes the toolbar's grammar for every list in the
  product, and `AccountsListPage` took the same decision for this same drawing's
  ageing segments;
* the **five KPI tiles** drawn above the table (`BALANCE · ACCOUNTS HERE · ACTIVE ·
  NEEDING ATTENTION · UNITS WITH NO ACCOUNT`) are **NOT built** — that strip is
  `AccountMetricColumns`, rendered once for EVERY tab, so a master-only tile set
  changes the account header on all thirteen tabs rather than this tab body.
  **`DEF-CUS-5105`**;
* the drawing's two explainer boxes are a **closed `<details>`** under the table
  (B14 rule 32's stated absence, rule 33's zero words of rationale on screen) —
  the `CommonAreasTab` precedent, which the PO has already walked.

### `BR-CUS-1094` — THE `Units` TAB ON A MASTER ACCOUNT

**⚠ NO BLUEPRINT PAGE DRAWS THIS TAB, and that is measured rather than assumed:**
nine PDFs were listed with
`git -c core.quotePath=false ls-tree -r --name-only <ref> | grep -i 'pdf$'` (the
flag is load-bearing — `DEF-GOV-6236`) and none carries a Units tab on an ACCOUNT.
**So this section is a MAP of what was built and its reasons, not a transcription
of a drawing**, which is the opposite posture from `R7` above and is said here so
nobody reads it as one.

Route `/:tenant/accounts/{accountId}?tab=units`, on S21. **Shown ONLY when the
account's `kind` is `master`, third — straight after `Accounts`.** Built
2026-09-23, `2.345.0`.

**The ruling, verbatim (PO 2026-09-23):** *"show all units with its status what wil
be billed to master account - can we do that?"* The PO asked for it **before** the
billing change, and their reasoning is the reason it exists: it makes the vacancy
picture visible, and it is how `BR-CUS-1094` gets checked once the run moves —
otherwise the first proof that vacant units bill correctly would be a live bill
run.

**IT IS THE OTHER HALF OF `R7`.** That tab lists every OCCUPYING account at the
address. **A vacant unit has no account at all**, so before this tab a landlord's
empty flats appeared on no list anywhere in the product.

**WHAT THE DESIGN LANGUAGE COMES FROM.** Pages 23–25 of
`05-prototype/Premises & Units Blueprint 2.pdf` draw the PROPERTY's Units tab —
the same building from the other side — read as IMAGES at scale 2.0 (B14 rule 42).
Four of its rulings land here unchanged: the **label leads** with the unit number
quiet beneath it in one cell (and the blueprint corrects an earlier draft of itself
in writing to say `unit_no` is *not* a database id); **a vacant row never draws a
dash** (*"a dash on that row reads as `nothing is billed`, which is the opposite of
true"*); **Occupant, not occupancy** (*"the state is in the status pill where it
belongs"*); and **the footer count is the size of the job**.

| the table's columns, LEFT TO RIGHT | what fills it |
|---|---|
| **Unit** | `label` in bold, linking to the unit, with `unit_no` quiet beneath · a `Common` pill where `is_common_area` |
| **Type** | `unit_type` through `metering.units.type.*` |
| **Floor** | `floor_label`, a stated absence where there is none |
| **Meters** | metering's own `MetersCell`, IMPORTED |
| **Occupant** | metering's own `OccupantCell`, IMPORTED — so the vacancy sentence cannot drift between the owner's screen and the building's |
| **Billed to** | ⚠ **THIS TAB'S ONE NEW COLUMN.** The tenant's `account_no` · a `This account` pill with the BASIS beneath it (*Its own agreement* for a common area, *Vacant — billed here* for an empty unit) · a danger-toned **Nobody** where the unit reaches no payer |
| **Owed** | what the unit owes TODAY, metering's column, `MoneyCell`. ⚠ **A vacant unit reads `Not measured` and NEVER `$0.00`** (`DEF-138`) — no occupying account means the books were never asked |
| **Status** | metering's derived `status` on a pill, metering's own tone map |

**The toolbar** is the kit's: the search (*"Unit, number, or account…"*), **two**
filter chips (`Billed to` and `Occupancy` — B14 rule 12), and the pagination
footer. Served by `GET /accounts/{id}/units`, which is a READ and writes nothing.

**FOUR THINGS THAT ARE THE DESIGN AND NOT GAPS:**

1. **Nothing is stored.** `BR-CUS-1094` is a prohibition as well as a ruling —
   *"No column may cache which units a master account pays for"* — so every answer
   is derived at read time and the screen shows what a run starting NOW would
   decide. `test_br_cus_1094_tc5` moves a tenant in between two reads, in one
   process, and the unit changes hands.
2. **The payer is READ from the two functions the bill run uses**, never
   re-derived: `covered_unit_ids` and `base_charge_only_coverage`, the pair
   `apps/billing/gather` resolves through the seam. A second derivation of a money
   decision is `DEF-127`'s shape on a money path.
3. **A payer, never a price** (`BR-CUS-1040`). `Owed` is today's figure, not a
   forecast; no per-unit standing charge is published outside a bill run.
4. **A vacant unit that will be charged NOTHING says so.**
   `gather._unbilled_unit_tariffs` skips a coverage entry outright on
   `not has_plan`, so *billed to this account* alone would be a promise the run
   does not keep. The row adds `No plan — nothing billed`. **Measured on the
   seeded tenant: 25 of `AC-2026-00051`'s 26 vacant units read that way.**

**TWO ABSENCES, EACH STAMPED:**

* the **four KPI tiles** the property page draws above its table are **NOT built** —
  `AccountMetricColumns` renders once for EVERY tab, so a Units-only tile set
  changes the account header on all fourteen tabs. **`DEF-CUS-5105`** already owns
  that blast radius;
* **`+ New unit` is absent.** It is the property page's primary action and it asks
  for a building; an owner's account screen is not where a unit is created.

**AND ONE THING THE TAB DELIBERATELY CANNOT SHOW.** `occupancy_statuses`' *vacant
base-only* versus *vacant no-billing* — the two are different money, and **no table
in this product carries a foreign key to that list**, so no unit declares one
(`DEF-CUS-6306`; `DEF-BIL-6296` is the same gap one layer up). The tab states what
the RUN will do and does not pretend a reference list drives it.

**Built and proved:** `07-frontend/src/features/customers/MasterAccountsTab.tsx`
(9 cases) · `06-backend/tests/test_cr094_r7_master_accounts_tab.py` (2 cases).
