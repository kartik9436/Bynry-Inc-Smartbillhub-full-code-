# CR-125-BRC07 — the disconnect request wizard is built to its drawing, and keeps two actions

**Raised** 2026-09-21 by the Product Owner, in the working chat session.
**Branch block** `CR-125`–`CR-129`, suffix `BRC07`, branch `claude/kind-wozniak-rl0uzt`.
Each number verified with `10-scripts/allocate.py cr --verify <n>` against the REMOTE at the
moment it was taken — `125`, `126` and `127` all answered *still free on every branch*.

---

## 0 · CAPTURE — the requester's words, verbatim

Two messages, in order. Neither was solicited and neither is paraphrased here.

> *"we need to keep only park, complete - two action only"*

> *"biuld it using drawing images - not just content ; images and screen should match
> exactly - build backend frontend, reuse existing ui components, backend code, create
> test cases , end to end test cases, you might want to create cr for this"*

The second arrived against a measured table of all five steps, every data element, and
which of them exist in the product today. **That table is the scope**: it was produced by
rendering blueprint pages 135–141 as images and reading the code beside them.

---

## 1 · CLASSIFY — CHANGE, and one half of it is a DEFECT set

**The two-action ruling is a CHANGE.** Nothing signed says the wizard has five action
controls; it grew them. Reducing them alters what a clerk can do, so it is a change and
not a correction.

**Building the screens to the drawing is mostly DEFECT repair, and is filed as a change
only because it arrives as one instruction.** `B14` rule 41 already says the product UI
matches the blueprint exactly, and `DEF-GOV-5248` already gives the blueprint layout,
copy, flows and states for any module that has one. So a screen that does not match a
drawing it was supposed to match is the product not doing what it was promised to do —
**a defect by the beta's own routing rule** (PO 2026-09-10: *"CR is change in product,
defect is product does not do what is expected"*). Where this CR names an absence, the
absence is the defect; this file is the container, not a re-classification.

⚠ **AND WHERE IT IS AMBIGUOUS IT IS A DEFECT, NOT A CHANGE** (`13-change-process.md` §1),
because filing our own misunderstanding as a *change* quietly converts our error into the
customer's new requirement.

---

## 2 · WHAT SIGNED STATEMENT IS BEING REVERSED

**Nothing frozen. No B4/B5 money figure is touched**, so no finance re-sign is required
and the work may proceed under `r11`.

One rule is NARROWED by the two-action ruling, and it is named rather than assumed:

* the wizard's `Save & exit` and its separate `Record the proof` commit are both
  pre-existing behaviour with no signed rule behind them. They are superseded by this
  ruling. **`Save & exit` and `Park` become ONE act**, and proof of service becomes data
  the wizard carries to its commit rather than a write of its own.

⚠ **THE PROOF CHANGE HAS A LEGAL EDGE AND IT IS STATED HERE SO NOBODY SLIDES PAST IT.**
*No proof, no cut* is enforced server-side by `assert_service_proved`. Folding the proof
write into the final commit does NOT weaken that gate — the same facts are required, in
the same call. What changes is that a clerk who abandons the wizard no longer leaves a
proof row behind. **If that is wrong, it is wrong now and cheaply**; it is written down
here rather than discovered later.

---

## 3 · IMPACT — the ten surfaces

| Surface | Impact |
|---|---|
| Screens | `DisconnectWizard.tsx`, all five steps. Blueprint p135–141 |
| API | No new endpoint is needed for most of it. `GET /accounts/{id}/reconnection-terms` EXISTS and is called by nothing; the protections POST and the ladder-stop POST both EXIST and are called by nothing |
| Schema | Two new columns at least: *who raised the case*, and the *oldest-debt* figure has no source. Both need a ruling before they are added |
| Data dictionary | Unchanged until those two columns are decided |
| Enums | The three ladder-stop reasons already exist server-side |
| Open questions | Who may authorise a safety cut, and on what evidence, is OPEN. Four of the five cut reasons can never succeed today |
| Demo fixture | The reconnection charge code does not resolve on any tenant — see §4 |
| i18n | **101 of the wizard's 132 keys are missing.** The screen is correct in English and untranslated in the other ten languages |
| Tests | New unit cases per step, plus the end-to-end walk the PO asked for. There is no disconnect walkthrough script today |
| Docs | This file, the decision log, and `04-docs/05-modules/03-customers/02-business-rules.md` |

---

## 4 · WHAT IS ALREADY BUILT AND IS NOW WRONG

* **Five action controls**, of which two survive this ruling.
* **Step 2 is read-only over two working write endpoints.** A clerk cannot record a
  medical certificate anywhere in this product.
* **Step 4 renders a refusal over a read that works.**
* **Step 5 reviews 6 of the 14 drawn rows**, and omits eight notice-and-proof facts that
  are already on a payload the wizard fetches on step 3 — at the moment a person presses
  a danger-tier button.
* **Step 1 shows 6 of the 15 drawn customer facts**, with the other 12 already served.

⚠ **AND ONE THING THAT BLOCKS THE WHOLE ACT, FOUND BY DRIVING IT ON REAL POSTGRESQL:**
the completion path looks up a charge code spelled **`CC-RECON`**; the seeded catalogue
spells it **`RECON`** and prices it at **$45.00**, while the blueprint and the signed
worked figure both say **$75.00**. Three sources, two disagreements. **Every cut refuses
today.** That is a question for the PO — which spelling, which price, and whether it
should be a tenant setting — and it is NOT something a lane may resolve by choosing.

---

## 5 · SIZE, AND THE PLAIN-ENGLISH CONFIRMATION

Five screens rebuilt to their drawings, three write paths given doors, one read wired up,
about twelve fields surfaced that the server already sends, and a browser walk that does
not exist yet. **This is not a fast-path change**: it touches a money figure ($75.00
against $45.00), it touches data (two columns with no source), and it touches a rule
(the proof write). So it takes the full process.

**The one number to confirm in plain English:** a reconnection costs **$75.00** in your
drawing and in the signed worked figure, and **$45.00** in the data the product ships
with, under a different code name. Until you say which, no cut can complete at all.

---

## 6 · EXECUTE — through `r11`, unchanged

**Built from the drawing AS AN IMAGE** — `B14` rule 42, PO verbatim: *"When you use images
to create screens your accuracy is higher; hence dont create screens using only Text"*.
`10-scripts/pdf/pdf_render.py` renders; the extracted text of this PDF renders every digit
as `&`, so text alone would lose every figure on the page.

**Reusing what exists** — `B14` rule 43, PO verbatim: *"make them coponents - dont write
stand alone code , engineer it"*. The five steps come out of one 2,000-line page into five
addressable components before anything is rebuilt, because otherwise every lane after the
first is editing the same file and reverting the one before it.

**Where the drawing and our UI rules disagree about how a FORM is built, the UI rules win**
(rule 38). What the form CONTAINS is still the drawing's to decide.

**Every figure drawn is an illustration, never a requirement** (rule 37).

---

## 7 · VERSION

Allocated at the first push of built code, with `10-scripts/allocate.py version --bump change`.

---

## 8 · CLOSE, AND THE ROLLBACK STATED BEFORE SHIPPING

Rollback is per step, because the steps become separate components: revert one component
file and the wizard keeps working with that step as it was. The two-action change and any
schema change roll back independently of the screens.

---

# ADDENDUM — 2026-09-21 · THE CR COVERS ALL FOUR DISCONNECT SURFACES

**PO ruling, verbatim:** *"update the same cr for all 3 or 4 disconenct cases"*, and,
on the record screen, *"okay build it as per specification and as per what you ahve
mentioned - Disconnect details view — every section - i will consolidate actions - too
many actions - keep critical ones"*.

So this CR is **one change across four surfaces**, not four changes:

| # | Surface | Route | State when this CR opened |
|---|---|---|---|
| 1 | **The request wizard** | `/:tenant/disconnects/new` | Five steps, built, and diverging from its drawing on every one |
| 2 | **The list view** | `/:tenant/accounts?tab=disconnects` | Built; nine drawn columns present, the five filter chips removed, no row action |
| 3 | **The case record** | *nowhere* | ⛔ **DOES NOT EXIST — no route, no component, no file.** The drawing says so itself |
| 4 | **The actions** | across 1–3 | **Fifteen routes exist; the screens call five.** Ten write paths have no door |

## 4 · THE ACTIONS — RULED, AND THE RULE IS *FEWER*

**On the wizard**, `2026-09-21`: **two actions only, Park and Complete.** Recorded in the
decision log with the PO's confirmation verbatim (*"this si correct"*).

**On the record**, the same day: *"i will consolidate actions - too many actions - keep
critical ones"*. So the record carries **the three the drawing puts on it** — Hold the
case · Open the account · Mark as cut — **and nothing else.** The other seven server
routes stay doorless **on purpose** until the PO consolidates. **Building them now is
building the thing they have just said is too much.**

⚠ `Mark as cut` is **drawn greyed**, and that is honoured rather than decorated: its
reason appears as VISIBLE TEXT beside it, never a hover title.

## WHAT THE MEASUREMENT OF THE WIZARD'S ACTIONS THEN FOUND

Driving the real service code against real PostgreSQL, inside rolled-back transactions,
turned up five things no reading of the screens had shown. **They are defects, not
change, and they are in scope because this CR rebuilds the surface they live on.**

1. ⛔ **TWO OF THE FIVE CUT REASONS CANNOT EVER COMMIT.** The screen sends `tampering`
   and `abandoned`; the server AND a database check constraint require
   `tampering_or_theft` and `premises_abandoned`. The reason check runs FIRST, so a
   perfectly lawful final-tier case is refused before anything else is looked at — and a
   front-end test asserts the wrong code, pinning the mismatch in place. **Filed as a
   defect; it was in no register.**
2. ⛔ **ALL TWELVE DISTINCT REFUSALS REACH THE CLERK AS THE SAME ELEVEN WORDS.** The
   server writes a specific sentence for each — *"This case is at tier_1_reminder"*,
   *"The ladder is FROZEN by a protection in force: medical_certificate"*, *"Nobody has
   recorded how the tier-3 notice was served"* — and the front end drops it under the
   2026-08-19 rule that server text may not reach a screen. A machine code travels beside
   it **so a screen can branch without parsing English, and no screen branches on it.**
   One of those twelve is fixable by the clerk in thirty seconds on the step they just left.
3. ⛔ **`Save & exit` SAVES NOTHING AT ALL.** No autosave on this wizard. Four steps of
   typing are discarded. **The two-action ruling above already removes this control** —
   which turns out to be a repair as well as a simplification.
4. ⛔ **THE COMMIT IS NOT ONE TRANSACTION**, though the code comments claim *"one payload,
   one address, one transaction"*. It is two writes — the case, then the audit row — with
   no transaction around them and no request-level wrapper switched on. **If the audit
   write failed, the case would be scheduled with no record of who scheduled it**, which
   is CLAUDE.md hard rule 7 (*every money action writes `audit_log`*) resting on luck.
   Hard-won law 1: a comment claiming a guarantee is not the guarantee.
5. ⛔ **`?step=5` OPENS THE REVIEW OVER AN EMPTY FORM WITH THE DANGER BUTTON LIVE**, and
   the resulting refusal renders **an internal field name to a clerk**: *"Enter the cut_on."*
   Two rules at once — a control offered but not permitted, and B14 rule 32's ban on
   internal codes in clerk-facing copy.

Three more, smaller and still real: **the `Leave connected` choices are discarded** (step 5
shows *"Left connected: Water"* and nothing stores it); **the server has no cut-date floor
at all** — a cut was accepted for 1 January 2020 and for the year 2226, the floor lives
only on the screen; and **the service list is unvalidated server-side** — a service named
`"unicorn"` was accepted and recorded.

## ⚠ AND THE DRAWING IS A REDESIGN THAT WAS NEVER BUILT — WHICH IS WHY THIS CR EXISTS

Blueprint pages 135–141 carry their own banner: *"the product's disconnect wizard has five
steps and neither prices the protections nor collects a fee; these five do both."*
**The pages are a redesign published 2026-09-11, not an as-built record.** That is not a
reason to discount them — `B14` rule 41 and `DEF-GOV-5248` make the blueprint the
specification — but every lane must know it is building the drawing's intent and not
documenting today's screen.

## VERSION AND ROLLBACK

Unchanged from §7 and §8. The record screen is new, so its rollback is removing one route;
the list and the wizard roll back per component, which is what the extraction buys.

---

# THE LIST VIEW — added 2026-09-20 on the PO's own instruction

> *"this is correct - build disconnect list view - ensure you follow our toolkit rules
> search, filter, colume selector, you follow ui skills and spacing rules that we set -
> drwaing and screens hosuld match - please build it - you can add this in same cr"*

Said against a measured table of the Disconnects tab. **The drawing is page 142**, read AS
AN IMAGE at scale 8 through `10-scripts/pdf/pdf_render.py` — `B14` rule 42. This PDF's text
layer renders every digit as `&`, so a lane working from extracted text loses every figure
on the page and every column boundary with it.

## WHAT MOVED

| Drawn | Was | Now |
|---|---|---|
| Sub-line `10 tabs · Disconnects · 3 open cases` | two fragments; the count omitted | the tab publishes the SERVER's `open_case_count` to the head |
| `CASE #` column head | `Reference` | `Case #`, in all eleven catalogues |
| STATE reads *At notice* / *Due to cut* | *Notice sent* / *Scheduled* | the drawing's words; the stored codes did not move |
| Five tiles, in the drawn order | two transposed; three labels over three words | p142's order and p142's captions |
| Five chips before `Filter ▾` | deleted in `DEF-1702` | three quick views, and the reason the other two are not there |
| Search names the case number | four legs, none of them the case number | five legs and a prompt that names them |

## THE THREE JUDGMENTS, TAKEN DELIBERATELY AND RECORDED

### 1 · The chips overlap, and this lane did not resolve the overlap — it declined to

`OQ-374` is **OPEN** and blocks exactly this: an account at notice that files a medical
certificate satisfies `At notice` AND `On hold`, and **no rule ranks them**. The prime
directive forbids resolving an open question by choosing a value, and `?segment=` still
refuses everything but `all` on the server.

**So the chips are FILTERS, not B18 §5.8.2's segments.** A segment is an exclusive
partition; a filter asks *does this row's stored `state` equal X*. It needs no ranking, no
exclusivity and no precedence, it hides nothing, and it decides no part of the open
question — which is the same distinction `DISCONNECT_FILTERS` already makes server-side, in
`disconnect_reads.py`'s own words. A held account with a notice out still answers
`At notice`, and its State cell still says it is held.

**The behaviour is stated on screen in four words — *"A held case still appears."*** — a
FACT under `B14` rule 33's six-word cap, in all eleven catalogues.

⚠ **`On hold` IS DRAWN AND IS NOT BUILT, and that is measured rather than forgotten.**
`disconnects.STATE_ON_HOLD` is declared, is in migration `0022`'s CHECK vocabulary, and is
**assigned by nothing** — the hold is derived from `account_protections`. `f.state=on_hold`
can therefore never match a row. A chip wired to it would be hard-won law 7's *incapable of
passing*: live to look at, answering nothing, with `tsc` and every test green. **REPORTED**
as a server need, and the `+ Filter ▾` panel's identical dead option is **FILED**.

⚠ **AND THE QUICK-VIEW ROW DIVERGES FROM `DEF-1700`'s LETTER.** That PO ruling (2026-08-27)
removed four chip rows because each *"duplicated a dimension the same screen already
declared in `TableConfig.filters`"*. This row and the panel share ONE option source
(`payload.states`), ONE param (`f.state`) and ONE selection, and they sit in the single
toolbar row rather than the second row `DEF-1700` was raised against — and p142 draws both.
**That reading is this lane's judgment, not a ruling**, and it is put to the PO rather than
assumed.

### 2 · `↗ Open` was held, the hold EXPIRED the same day, and the door is open

⚠ **THIS JUDGMENT WAS TAKEN, AND THEN OVERTAKEN BY A SIBLING, IN ONE AFTERNOON — AND THE
TEST THAT WAS SUPPOSED TO NOTICE DID NOT (`DEF-CUS-6042`).** The original reasoning is kept
below because it was right when it was written and because what went wrong with it is the
more useful half.

**What happened.** `DisconnectRecordPage` landed in `4ff860296`, mounted in `App.tsx` at
`/:tenant/disconnects/:ref`. The hold-expiry test went on passing. It was written to
survive a RENAME — it filtered on ANY `/disconnects/` address that was not the wizard —
and it was defeated by something else: **there are TWO registries a route can live in, and
it watched the one the router does not use.** The record lane registered the route in
`App.tsx` and never added its `SCREEN_ROUTES` row, so the hold passed, truthfully, over a
registry that did not know the screen existed.

**That is hard-won law 7's fourth shape, which CLAUDE.md states almost word for word:**
*a hold-expiry test asserted a screen was REGISTERED at an address while the router was
mounting it somewhere else.* A hold written carefully still failed, which is why it is
written down here rather than quietly fixed.

**What the hold reads now:** `APP_ROUTES` — the array the router renders — plus the record
lane's OWN exported `DISCONNECT_RECORD_ROUTE` and `DISCONNECT_RECORD_SCREEN`, imported
rather than retyped, because two spellings of one address is the same defect one level
down. Proved by watching it go red against the record route already on the branch.

⚠ **AND BOTH REGISTRIES ARE NOW ASSERTED, BECAUSE WATCHING ONE IS WHAT BROKE IT.** The
record lane added its `SCREEN_ROUTES` row later the same afternoon, so the two agree again
and the case is green rather than a duplicate of somebody else's red. It is what notices if
they stop agreeing about **this** address.

⚠ **WHEN THAT ROW WAS STILL MISSING, THIS LANE DID NOT WRITE IT.** `screenIds.test.tsx` was already failing on
*"covers every routed screen, in App.tsx's order, with nothing extra"* — measured red at
`4ff860296` in a throwaway worktree — and the row belonged to the lane that mounted the
route (`DEF-710`'s own rule). Authoring it here would have taken a red the record lane
needed to see and made it somebody else's silent problem.

**The control, released in the same breath:** one row action per row, `RowActionLink` with
an `EyeIcon`, `to={tenantPath(disconnectRecordPath(case_no))}`. **`B14` rule 15 beats the
drawn button** — p142 draws a bordered `↗ Open`, rule 15 says a row action is an unlabelled
glyph with a tooltip, and rule 38 gives CONSTRUCTION to the UI rules; a labelled button
here would change every table in the product on one screen's authority. What the cell
CONTAINS is still the drawing's: one action, open the case. A row with no case reference is
**disabled with its reason** (`BR-SHL-025`) rather than losing its control.

⚠ **AND THE COLUMN IS HEADED `Actions`, THOUGH p142 DRAWS ITS HEADER BLANK.** Twenty-nine
list tables in this product head it that way; an unlabelled tenth header here would be this
screen departing from every other one on one drawing's authority. Recorded, not silent.

**The walkthrough now FOLLOWS the link** rather than reading its `href`: it clicks, asserts
the address it lands on and the `data-screen` of what answers, and that the page is not a
*"not built yet"*. A href that looks right over a dead page is the mirror-defect this whole
judgment exists to avoid.

#### The original judgment, kept because it was right when written



p142 draws it, and the blueprint's own caption beneath the frame says why it cannot be:
*"no disconnect case page exists"*. Hard-won law 2's mirror — a live control onto a screen
that is not there — is the most expensive defect shape this repo has.

**The action is omitted, and the hold is written as a test that fires when it expires.**
`DisconnectsListDrawing.dom.test.tsx` asserts that `SCREEN_ROUTES` holds
`/:tenant/disconnects/new` and **no other address under `/disconnects/`**. The day a
disconnect case screen is registered, that case goes RED and names this control.

⚠ **It matters more than it did this morning:** the sibling lane landed
`disconnect_record.py`, its read and its server route in `6f7b774df` — **the back end for
that screen now exists and the front end does not.** The hold is one commit from expiring,
which is precisely the state law 2 warns about.

### 3 · `DUE TO CUT` counts a week ahead; the drawing says the date has arrived

p142 captions the tile *"the date has arrived"*. The figure beside it is
`kpis.due_to_cut_this_week`, which `_within_the_week` computes as **seven days forward,
inclusive at both ends**. Those count different things: a cut booked for Friday is in this
figure on Monday and is not in the drawing's.

**The caption states what the figure IS — *"within 7 days of today"*.** Printing the drawn
sentence over the served number would put a FALSE statement on this strip, which is
`DEF-716`, on this same strip, on this same screen. And the figure is **not re-derived on
the screen to match the drawing**: the window is the server's, there is one calendar in this
product, and a second one is how a tile and its list stop agreeing. The drawn definition is
**REPORTED** as a change to `_within_the_week`, for the PO to rule — it changes a number a
clerk works from daily.

## THE `WAITING ON` COLUMN — RULED BEFORE THIS LANE STARTED, RECORDED HERE

p142's **caption** says a `WAITING ON` column is this tab's addition; the **figure** beneath
draws nine columns and none of them is it. `B14` rule 42 makes the drawing AS AN IMAGE the
specification and extracted text only an index. **A caption is text; the figure is the
image. The figure wins** — nine columns, and `waiting_on` keeps rendering where it already
does, inside the State cell of a parked draft. Followed, not re-opened.

## THE DRAWING'S TWO EXPLANATORY NOTES ARE NOT ON SCREEN

p142 puts two notes under the table: *"On hold is not a delay, it is a protection"* and
*"Tier and Last notice answer different questions"*. **Both are RATIONALE — why the product
works this way — and `B14` rule 33 gives rationale ZERO WORDS ON SCREEN.** Rule 33 also says
rationale is REMOVED and not shortened: cutting either to six words would keep the breach
and make it terser. Rule 38's principle decides the collision — where a drawing and our UI
rules disagree about how text is WRITTEN, the UI rules win; what the screen CONTAINS is
still the drawing's. Both sentences live here and in `DisconnectsTab`'s header, which is
what the record is for. A case asserts neither reaches the DOM.

## WHAT THIS LANE NEEDS FROM THE SERVER AND DID NOT BUILD

0. **Shorter TIER chip labels** — p142 writes `10-day` and `Final notice`; the payload sends
   `TIER 2 · 10-DAY` and `TIER 3 · 48-HOUR`, which makes three segments where the drawing
   draws two on the `LAST NOTICE` cell and wraps the `TIER` chip at 1280.
1. **`Export`** — `POST /exports` resolves a registry; `apps/customers/` has no `exports.py`
   and registers no `disconnects` resource, so `BR-SHL-010` keeps the drawn `⇩ Export`
   undrawn. Not disabled-with-reason: that is for a control this ROLE cannot use, not one
   the PRODUCT does not have.
2. **A leg that answers *is this row held*** — so p142's `On hold` chip can exist. Today the
   panel offers a `state` option that can never match.
3. **The `DUE TO CUT` window**, if the PO rules for the drawn definition (judgment 3).
4. ~~**`DEF-CUS-6039`**~~ — FIXED by a sibling during the afternoon; the tab reads live again.
5. **`DEF-CUS-6045`** — the `CASE #` cell's 24-word paragraph, in a file this lane cannot edit.

**Two needs this lane measured were closed by the server lane the same day** and are now
wired: `open_case_count` on the list payload, and `case_no` in the search legs.

## WHAT THE BROWSER FOUND THAT THE SUITE COULD NOT — hard-won law 6

`10-scripts/cr125_disconnect_list_walkthrough.mjs` opens this tab at **1440**, the staff
app's design target. Twenty-two assertions; **three findings that every green vitest case
had passed over**, which is the whole of law 6 (*"no gate looks at rendered output"*).

1. **`LAST NOTICE` was a COLUMN OF THREE where p142 draws ONE LINE.** The date, the tier
   under it, and *"how it was delivered is not recorded"* under that — **on every row**.
   That third line is RATIONALE, so `B14` rule 33 gives it zero words on screen, and it was
   a SECOND COPY: the reader's sentence already rides on the cell's `title`, which is where
   `BR-SHL-025` puts a reason. The cell now reads `TIER 2 · 10-DAY · 04/24/2026`.
   ⛔ **`TC-DSC-6` is untouched and stronger for it** — the guarantee is that no delivery
   CLAIM is rendered, and there is still no map from `emailed`/`posted`/`certified
   sent`/`certified signed` to a label anywhere in the file.
2. **The `Reconnecting` chip said the state's word where p142 says the VIEW's.** A chip
   names a view (*show me the reconnections*) and a State cell names a state, and p142
   heads the tile above it `RECONNECTIONS`. The chip takes the TILE's existing key, so
   nothing new is minted and the two agree; the State cell still reads `Reconnecting`, and
   a case pins that the two words do not drift into one.
3. **`eslint` caught what the walk could not:** the head's two new hooks were written after
   the component's `PermissionDenied` early returns. React refuses that render — but only
   on the denied path, which a System Admin never takes, so the browser was green over it.
   Moved above the returns, where `useCrumbLeaf` one line up already says hooks belong.

4. **`LAST NOTICE` then wrapped MID-LABEL** — `TIER 2 ·` / `10-DAY · 04/24/2026`, a line
   ending on a middle dot. Fixed with `whitespace-nowrap`, and the walk now asserts the
   cell is **one line at 1440 AND at 1280**, with `white-space` actually computing to
   `nowrap` on the rendered element.
   ⚠ **AND THE FIRST ATTEMPT AT THAT FIX NEVER REACHED THE FILE, AND THE WALK WENT GREEN
   OVER IT.** The edit was a python heredoc that hit an `AssertionError` — its anchor had
   moved when `prettier` reformatted the block — inside a BACKGROUNDED `... ; cd … && build`
   chain, so the build succeeded over unchanged source and nothing said otherwise. The run
   printed `noticeLines: 63` **and asserted nothing about it**, which is hard-won law 7 in
   one line: *a check's output must distinguish pass from fail to a READER*. A number
   printed and not checked is not a check. The assertion above is what closes it, and it
   was proved by re-running the walk against the unfixed build first.
   ⚠ **AND THE TIER WORD IS THE SERVER'S.** p142 writes `10-day · 04/24/2026`; the payload's
   chip label is `TIER 2 · 10-DAY`, which carries a separator of its own and makes THREE
   segments where the drawing draws two — and at 1280 it squeezes the TIER column's chip
   onto four lines. The labels come from `disconnect_reads`' `chips`, so shortening them is
   a **server change** and is REPORTED rather than taken here.

5. **THE DATA PATH IS LIVE NOW, AND THE FIRST LIVE WALK FOUND A DEFECT NO FIXTURE COULD.**
   A sibling fixed the migration leaves during the afternoon, so the final walk read the
   real `brazosbend` — six rows, four with a case and two held — and the `CASE #` cell on a
   protected row rendered **the server's 24-word diagnostic as body copy**: *"This account
   is on the list because a protection is in force. No disconnection case has been opened,
   so there is nothing to reference."* In a ~90px column that wraps to **fourteen lines**,
   and the row measures **~280px against ~40px** for a normal one.
   It is `DEF-742`'s defect surviving in a SHARED file: `DisconnectsTab` replaced every
   other server diagnostic with the reader's own sentence and could not reach this one,
   because `RecordNumberCell` is owned by `transferDisconnectShared.tsx`, which a sibling
   lane holds. **Filed as `DEF-CUS-6045`. Not fixed here.**
   ⚠ **AND IT IS THE BEST ARGUMENT IN THIS FILE FOR WALKING LIVE DATA.** Every check passes
   over it — the text is rendered, the key resolves, `tsc` and 51 vitest cases are green —
   and the earlier walks missed it too, because they ran against a hand-typed fixture whose
   `detail` was the word `"none"`. A fixture's short string hides a payload's paragraph.

⛔ **THE EARLIER WALKS COULD NOT EXERCISE THE DATA PATH AT ALL, WHICH WAS ITSELF A FINDING.**
`GET /disconnects` answers **500** on any host provisioned from this branch:
`column disconnect_cases.stopped_note does not exist`, because `customers` has TWO
migration leaves and `manage.py migrate` refuses the whole graph. `0061` was written
against `0059` with its own comment *"Re-point to `0060_*` when that lane lands"*; `0060`
landed in `927f82bb4` and the re-point did not. **The Disconnects tab is DOWN on this
branch for everyone** — it renders *"The disconnects could not be loaded."* Filed as
**`DEF-CUS-6039`**, severity high, and NOT fixed here: this lane owns no backend file.
The walkthrough tries the live read first, falls back to p142's own three rows through a
route intercept, and **prints a loud line saying the data path was not walked** — reporting
a fixture walk as a live one is the dishonesty hard-won law 7 is about.

## AN ID COLLISION, CAUGHT BY THE CHECK THAT IS SUPPOSED TO CATCH IT

Between this lane's first push and its second, siblings took `6031`–`6038`. This lane was
holding `DEF-RAT-6031` and `DEF-CUS-6032` — **different strings, the same NUMBERS**, and
CLAUDE.md is explicit that the module segment is provenance and the number is what has to
be unique. It then happened AGAIN: the renumbered `6034`/`6035` were taken while the
citations were being updated, and `file_defect.py` itself refused a third attempt with
*"DEF-RAT-6038 was taken while this run was reading the remote"*. **Three rounds on one
branch in twenty minutes** — which is what "one running number across a register eight
lanes are writing" costs, and why the re-derivation is unconditional rather than a branch
of conflict handling.

**Nothing downstream would have caught it**: a duplicate number in a 3,500-row register
reads as a register. What caught it is law 11's *re-derive BOTH the file content AND the
ids at push time, unconditionally* — the register was restored to the tip byte for byte
(`diff` empty) and the two rows re-filed through `10-scripts/file_defect.py`, which asks
the REMOTE. They are now **`DEF-RAT-6040`** and **`DEF-CUS-6039`**, and every citation of
the old numbers moved in the same commit. `DEF-CUS-6030` was untouched: it is this lane's
own row, already pushed, which is why the sibling's numbering started where it did.

## ROLLBACK

Per file. `DisconnectStateChips.tsx` is a new component and reverting it takes the quick
views off the toolbar with nothing else moving. The tile order, the column head and the
state vocabulary are one commit each on `DisconnectsTab.tsx` and the catalogues; the
sub-line is one optional prop on `DisconnectsTab` and one branch in `AccountsListPage`.

---

## 9 · THE DISCONNECT CASE RECORD — added 2026-09-20 (blueprint p143 · p144 · p145)

**PO ruling, verbatim:** *"okay build it as per specification and as per what you
ahve mentioned - Disconnect details view — every section - i will consolidate
actions - too many actions - keep critical ones"*.

This CR was raised for the WIZARD. The record is added to it rather than given a
number of its own, because it is the same instruction, the same drawing and the
same branch block — and because the wizard's own §4 finding (the reconnection
charge code) is what this screen has to render a refusal for.

### 9.1 · WHAT WAS BUILT

| | |
|---|---|
| Route | **`/disconnects/{ref}`** — a NEW top-level route beside `/disconnects/new`, declared AFTER the static segment so `new` can never read as a case number |
| Address | the **CASE NUMBER** (`DSC-26-0003`), never a uuid — B14 rule 31, and the blueprint's own URL |
| Endpoint | **`GET /disconnects/{ref}`**, `apps/customers/disconnect_record.py`, its own module with its own `urlpatterns` (the `transfer_disconnect_api` precedent), included in `config/urls.py` AFTER that module so `disconnects/schedule` keeps its route |
| Components | **eight**, under `07-frontend/src/features/customers/disconnect/record/` — four panels, two dialogs, the row primitives, the wire shape. B14 rule 43's test is addressability |
| Tests | **20 cases**: 14 backend (`tests/test_disconnect_record_page.py`), 14 screen, 6 dialog. Every one proved RED first in the harness that runs it |
| i18n | **112 keys in all eleven catalogues**, appended by sort — 112 insertions and 0 deletions per file |

### 9.2 · THE ACTION SET — THREE, AND THAT IS THE RULING

Fifteen disconnect routes are mounted on the server and the product's screens
call five, so **ten write paths have no door.** The PO has seen that list and
ruled *"too many actions - keep critical ones"*. The record carries:

1. **Hold the case** — `POST /accounts/{id}/protections` (p144)
2. **Open the account** — a door
3. **Mark as cut** — `POST /accounts/{id}/disconnect-case/cut` (p145), DRAWN GREYED

**Deliberately absent:** Stop the ladder · Advance a tier · Lift a protection ·
Mark reconnecting · Restore service. They are undrawn and the PO is
consolidating. `disconnect_record.ACTIONS` is the whole set and a fourth entry
is a ruling, not a commit; a test asserts none of the five reaches the screen.

⚠ **THIS IS THE FIRST CALLER OF BOTH WRITES.** Each was built, role-gated and
tested on 2026-08-25 and has had no door since — hard-won law 2 read from the
engine end.

### 9.3 · WHAT THE DRAWING ASKS FOR AND THE PRODUCT CANNOT GIVE

Each is rendered as a STATED ABSENCE and none is derived from something near it.

| Drawn on p143/p145 | Why it is absent |
|---|---|
| `Oldest debt · 62 days past due` | **No column, no read, no seam.** `amount_owed_at_open` is a figure, not an age; `opened_on` is when the CASE opened. Ageing the AR ledger is payments' work and nothing publishes it. **A schema change and a ruling** |
| `Raised by <name>` | `disconnect_cases` has `opened_on` and **no actor column**. `audit_log` holds it and is PRUNED, so the name would vanish from a regulator-facing record. The DATE half IS served. **A schema change and a ruling** |
| `NOTICES SENT` · `STATE` | `delivery_state` is written NULL **by rule** — no adapter delivers anything |
| `NOTICES SENT` · `CHANNEL` | `service_channel` is the PROOF channel, null until a person attests. Drawn on a row that HAS been attested to |
| `Reconnection fee` | §4's three-way disagreement. **Every cut on every tenant in this tree refuses today** and the record renders the server's refusal |
| `Who did it · Field crew · WO-26-0402` (p145) | `commit_cut` takes no such argument, no column holds it, and no crew-outcome vocabulary exists (`OQ-383`) |

### 9.4 · THE HOLD DIALOG'S THREE PROMISES — THE DECISION AND ITS REASON

p144 promises the cut date is cleared, the ladder stops and the case moves to
`On hold`. **`record_protection` writes a protection row and touches the case not
at all.** The ladder DOES stop, because `halt_reason` is computed on every call —
that is the module's design and not an accident. The other two are false:
`cut_scheduled_for` is unchanged and `disconnect_cases.state = 'on_hold'` is
**assigned by nothing, anywhere in this repository.**

**RULED: the dialog stops promising them**, and states the cut date STAYING as
its own consequence, in the `Not now` half. Making them true is a write into
`disconnects.py`, which a sibling lane holds. The rows come from the SERVER, so
the day that module starts clearing the date one list moves and the test goes
red until both surfaces move with it.

### 9.5 · THE DOOR THIS SCREEN IS OWED

`DisconnectsTab.tsx` draws no row action *because there was nowhere to go*. That
refusal stops being true at this commit. The destination is
`DISCONNECT_RECORD_ROUTE` = `/disconnects/:ref`, built by
`disconnectRecordPath(caseNo)`. **A live screen behind a dead control costs more
than dead UI.**

### 9.6 · WHAT IS STILL OPEN AFTER THIS

* the reconnection fee — §4's number, the PO's to settle. **No cut can complete
  until it is.**
* the two columns with no source (§9.3) — both need a ruling before they exist.
* whether a tier-3 cut needs the SIGNATURE back, not only certified mail —
  unwritten in every signed document, and `assert_service_proved` deliberately
  does not read `signed_for_on`.
