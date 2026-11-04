# CR-085 · step 2 · lane 7 · WHEN MONEY IS TIGHT — what changed, and what did not

**Step 1 identified. This is the FIX step.** The specification is
`CR-085-lane7-drawing.md` (the drawing, quoted) and `CR-085-lane7-findings.md`
(the delta). Read those first; this file is what was DONE about them.

| | |
|---|---|
| Worktree | detached at `56ddf02fa`, `2.235.0` |
| Routes | `/overdue` `/help-paying` `/level-pay` `/level-pay/standing` `/plan` `/plan-offer` `/ask-for-a-plan` `/protections` `/money-back` `/fees` |
| Screens | `CWP-057` `CWP-056` `CWP-044` `CWP-066` `CWP-043` `CWP-063` `CWP-042` `CWP-064` `CWP-045` `CWP-050` |
| Built on | lane 1's `portal/components/states.tsx` — `PortalScreen` and `PortalState`. Nothing in `states.tsx`, `primitives.tsx`, `global.css`, `tokens.css`, `tailwind.css` or either frame was edited by this lane |

---

## 1 · R-10 — what a customer can now do that they could not

**The rule, PO 2026-09-11, verbatim:** *"when a screen tells a customer
something bad, the thing they can do about it must be on that same screen, next
to the message. Not a page away. Not in a menu. Right there."*

Step 1 audited all nine branches on this patch that state bad news or an
absence and found **seven honouring it and two breaching it**. Both breaches
are closed, and the second one was closed **ten times over** rather than once.

### 1a · The worst one: `/level-pay`'s `null` branch

It rendered *"We could not find an account to work this out for."* and **nothing
else** — no button, no telephone number, no link back — on the screen somebody
opens because their bills swing and they want them not to. It was the single
exception among eight empty branches.

It now carries three ways out, inside the card, directly under the sentence:
**Try again** (filled), **Where your budget billing stands**, and **See what
help there is**.

### 1b · The other one: every failed branch on the patch

All eight signed-in screens rendered *"We could not read this right now"* in a
card **with no control of any kind**, while the shell's own `FailedWithRetry`
has one. All ten screens now carry a `waysOut` row on their failed branch.

| screen | the sentence | what is beside it now |
|---|---|---|
| `/overdue` | *We could not read this right now…* | **Try again** · Ask for a payment plan · See what help there is |
| `/help-paying` | *We could not read this right now…* | **Try again** · Ask for a payment plan |
| `/protections` | *We could not read this right now…* | **Try again** · See what help there is |
| `/money-back` | *We could not read this right now…* | **Try again** · What you have paid |
| `/level-pay` | *We could not work this out. Please try again.* | **Try again** · Where your budget billing stands · See what help there is |
| `/level-pay/standing` | *We could not read this. Please try again.* | **Try again** · Budget billing |
| `/plan` | *We could not read your plan.* | **Try again** · Ask for a payment plan |
| `/plan-offer` | *We could not open your offer. Please try again.* | **Try again** · Ask for a payment plan |
| `/fees` | *We could not read this right now…* | **Try again** · Ask us a question |

⚠ **`Try again` IS A REAL CONTROL AND THE TESTS PROVE IT AS ONE.** `states.tsx`
says in its own docstring why it will not make `waysOut` required on a failed
card: on the day it was written *"the read they would retry is held in each
screen's own effect"*, and a required prop would have been satisfied ten times
by a button wired to nothing — `EmptyList`'s `onCta: () => undefined` defect
(`DEF-MET-4764`). So each screen grew an `attempt` counter in its effect's
dependency list, and **every one of the nine cases makes the first read fail,
presses the control, and requires the SECOND read to draw the figure**. A
presence assertion would have passed on a dead button; that is the false pass
these cases exist to rule out.

### 1c · Where R-10 was deliberately NOT applied

* **`/overdue` when nothing is overdue** and **`/fees` when there is nothing to
  pay.** Both are the good answer. A row of buttons under *nothing is overdue*
  invites somebody in good standing to ask for a payment plan they do not need.
  Asserted as an absence, not left to chance.

---

## 2 · R-22 — three states, three sentences

PO 2026-09-11, verbatim: *"differntiate it using text message"*.

Step 1 found this already held on all ten screens — each has three distinct
sentences. What it did **not** have was any way for a check to see it. All
thirty branches now render through `PortalState`, so the kind is in the DOM as
`data-portal-state="loading|empty|failed"` and a walkthrough can assert that
the empty address and the failed address do not render the same kind. No
sentence was reworded for R-22; none was a wordless card to begin with.

---

## 3 · The defects, one line each

### Closed by this lane

| row | what it was | what was done |
|---|---|---|
| `DEF-CWP-4911` | `/plan-offer` printed the offer's DEADLINE as the raw wire date `2026-08-27`, beside four dates on the same screen in `MM/DD/YYYY` | goes through `usePortalDate` like its four neighbours. ⚠ **Its own test asserted the raw string**, so the suite was green *because* the defect was present; the test now asserts `09/16/2026` and that no ISO string is on screen, and it supplies the tenant's Regional settings because the formatter fails closed without them |
| `DEF-CWP-4912` | `/ask-for-a-plan` had **no page heading at all** — its first heading was an `h3` in the rail, so a screen reader announced *There may be help too* as the page | composes the shared `PageHeader` once, above both branches. It is the LAST of `DEF-CWP-4000`'s ten: the head sweep fixed nine screens by MOVING a head, and this one had none to move. The card's own repeated title was removed (B14 rule 32) |
| `DEF-CWP-4914` | `/level-pay/standing` printed **`AS AT POSTING DATE` on two of three KPI tiles**, in the largest type on the screen, to a householder | uses the portal's own `KpiRow`/`KpiTile`. ⚠ `primitives.tsx` **predicted this in its own docstring** and built those components for exactly this reason; the screen imported the staff `KPIStrip` anyway. Its test asserted `.kpi-grid` — the staff component's class — so that assertion could no longer fail on this screen and still reported a pass; it now asserts `[data-kpi-row]` |
| `DEF-CWP-4915` | `/level-pay`'s twelve-month bill chart was titled *This month, either way*, **in all eleven catalogues** | `portal.levelPay.chartTitle` is now *Your bills, month by month*, written per language through `i18n_fanin.apply(..., allow_overwrite=...)` |
| `DEF-CWP-4919` | `/overdue` never said WHICH DAY it was counting from, though `due_on` has been on the wire since `CR-068` wave H | a small line under the headline: *It was due on 07/22/2026.* A separate key rather than an extension of `portal.overdue.headline`, because folding two facts into one plural sentence forces `ja-JP` and `ko-KR` into English word order (B14 rule 35). `null` draws nothing — no em-dash |
| `DEF-CWP-4920` | `/plan-offer` printed the same six-word refusal **three times in a row** under three dead buttons | one reason under the group, in `HeldButton`'s own type and colour; each button keeps the reason on `title` so a hover and a screen reader still get it on the control. Its test asserted `toHaveLength(3)` — it was asserting the defect — and now asserts `1` |
| `DEF-CWP-4141` | `/ask-for-a-plan` caught **five different server refusals** into one sentence that named neither the field nor the bound | both handlers use `refusalText`, the function that owns this job (`DEF-322`, `BR-SHL-020` r2 — it renders `message_key` and strips `detail`). A customer asking for thirteen months now reads *"Choose between 2 and 12 months."*, a key that existed in all eleven catalogues and was rendered by nothing |
| `DEF-CWP-4145` | `ProtectionCard` has accepted an `action` since the day it was written and **nothing ever passed one** — hard-won law 2 in its purest form | the plan card opens `/plan`, the certificate card opens `/help-paying` carrying `CWP-056`'s own five-word label. ⚠ **The moratorium still gets none, deliberately** — nobody applies for a regulator's window. No new key and no new destination: inventing an assistance-programme door would be building to `R-18`, which is a PROPOSAL |
| `DEF-CWP-4181` | `/plan` named an instalment due in eighteen days and offered **no way to pay it**, while `/pay-now` was live and routed | `Pay $22.03` in the head's primary slot, which is where `08-screen-layouts.md` draws it (*· actions ↓ Agreement · Pay the next one*). The amount is the server's own `due_next` row — **nothing is summed**. A closed or fully-paid plan draws no button |
| `DEF-CWP-4183` | the title printed **twice, one line apart** on `/plan` and `/plan-offer` | one `<h1>` each; both cards open on the line the customer came for |
| `DEF-CWP-4720` | `hover:bg-neutral-50` on `/plan-offer`'s agreement link — **a class `tokens.css` does not declare**, so the hover did nothing | the anchor is now the kit's `ButtonAnchor`, which is what `CWP-043` already uses for the same document. Five hand-rolled utilities gone with it |

### Left open, with the reason

| row | why it stays |
|---|---|
| `DEF-CWP-4913` | **Amended rather than fixed, and step 1 mis-framed it.** It reported *"the server sends flags nothing reads"*; the decision log of 2026-09-11 corrects that — there are eleven non-test references. Reading `join_held` / `actions_held` would add a branch that **cannot execute**: `selectors.py` writes `"join_held": True` as a literal and `"join_held_reason": "OQ-CWP-1568"` beside it, which is an internal id B14 rule 31 keeps off the glass in every language. A branch that cannot fail is hard-won law 7's own shape. The reasoning is now in both screens' source |
| `DEF-CWP-4916` | **Fixed in the shared kit by lane 1, not by this lane.** `FormField` now carries two gaps (`mb-1.25` = 5px, `mt-1.5` = 6px) and `TwoUp` carries `gap-5` = 20px, and `global.css`'s `p { margin-block: 1em }` — which is what actually made the measured input→helper gap 17px — is off for the portal. The row is lane 1's to close, and the `.input min-h 36` and page-padding anchors are theirs too |
| `DEF-CWP-4917` | **`MiniTable` is in `primitives.tsx`, which is lane 1's this session.** Three of five tables on this patch are wider than their `overflow-x-auto` container at 390 with no shadow, fade, resting scrollbar or caption. Fixing it in one place fixes all three; forking the component here would be the two-of-everything failure B14 rule 36 exists to stop |
| `DEF-CWP-4918` | **`Payments.tsx` is another lane's screen.** Its comment at line 432 still argues `/level-pay` is *"DELIBERATELY NOT HERE"* seventeen lines below the entry that puts it there |
| `DEF-CWP-4146` | ⚠ **NOT A DEFECT ON THIS SCREEN, AND A GUARD CAUGHT THIS LANE TRYING TO "FIX" IT — see §4** |
| `DEF-CWP-4154` `DEF-CWP-4180` `DEF-CWP-4182` | unchanged. `4182`'s three clauses are a redesign of `/ask-for-a-plan`'s interaction model (three `RadioCard`s in place of free-text term and date, the protection panel moved beside the choice, step 3 reachable), which is its own wave with its own drawing |

---

## 4 · The one change this lane made and REVERTED, because a guard said no

`DEF-CWP-4146` reads *"one column where the plan and the drawing say two"*.
This lane composed a `TwoCol` on `/money-back` — and
`MoneyBack.dom.test.tsx`'s D9 case went red.

That case was written by an earlier lane **for exactly this moment**, and its
own words are the finding:

> *"VERDICT: correct, and the row's premise was wrong for this screen.
> `08-screen-layouts.md` marks `CWP-045` **T4** — A REFUND ON ITS WAY above
> CREDITS ON THE ACCOUNT, two full-width panels, no rail … Recorded as a case
> rather than a note so the next lane reading D9 does not 'fix' it by adding a
> column the drawing does not have."*

Checked against `08-screen-layouts.md` §CWP-045 directly, and the earlier lane
is right. **The change was reverted and the test was not widened**, which is
the only move available: editing a baseline to go green converts a true finding
into a permanently invisible one. The reasoning is now in `MoneyBack.tsx`'s own
source so the third lane does not rediscover it.

**`DEF-CWP-4146` should be closed as `not-a-defect` against `08-screen-layouts.md`
T4.** What that screen *is* missing against the drawing is the `YOUR CREDIT
$84.20` headline and *"enough to cover about half of a typical bill"* — and
**neither figure is on the wire**: `credits[]` is a list of negative amounts
with no total, and nothing anywhere carries a typical monthly bill. Reported,
not invented.

---

## 5 · `OQ-CWP-1568` closed — permission is not a write path

The ruling of 2026-09-11 says a signed-in customer **MAY** accept a payment
plan, ask for different terms, decline one and join budget billing.

**The four controls on this lane's two screens stay HELD, and that is the
answer rather than an omission.** `apps/portal` serves both screens as READS.
`BR-CWP-001` allows the portal rows of exactly six kinds; a plan signature and
a budget enrolment are neither. `write_points.py` says in its own words that
adding a row *"is a ruling and not an edit"*, and `G81` fails the build until
one is recorded. **There is no endpoint to point these buttons at, and this
lane did not invent one.**

What DID change is the thing that was about to rot: both hold notes in
`holds.ts` said *"OQ-CWP-1568, which is OPEN"*. That is now false, and a hold
whose stated reason has stopped being true is `DEF-CWP-3925`'s mechanism one
level up. Both rows now carry the CLOSED ruling and **what is still to decide,
which is ours and not the PO's**:

1. the seventh (and eighth) write point in `write_points.py`;
2. the `audit_log` row each write must leave — CLAUDE.md hard rule 7, *every
   money action writes `audit_log`*;
3. **whether a DECLINE can be reversed** — which matters most of the three,
   because declining is the one a frightened person does by accident.

Both rows stay `unwatched` by this file's own rule: no symbol exists, and none
is forced by any convention, so naming one would be inventing it.

⚠ **The third control the ruling releases is `CWP-040`'s *Turn autopay off*.**
That is another lane's screen and this lane did not edit it — and by the time
this lane re-derived `holds.ts` from the tip, **the autopay lane had already
corrected its own row**, independently, from the same ruling and to the same
conclusion: permission arrived, the write path did not, the control stays held.
Two lanes reading one ruling and landing in the same place is the record doing
its job.

---

## 6 · The stated absence — reported, not filled

`/level-pay/standing`'s drawn *WHAT HAPPENS IN AUGUST* panel computes
*"$11.88 a month, new amount around $183.28"*. **Nothing in this product
computes a projected settle-up instalment or a projected new level.** The built
screen draws the panel's SHAPE and states only what it can derive. **Untouched
by this lane, deliberately.** It is recorded here a second time so no later
lane "completes" the panel by dividing the variance by twelve.

Two more absences met and left alone:

* **`/help-paying`'s five programme cards.** `R-18` is a PROPOSAL. Nothing in
  the product stores an assistance programme; `selectors.help_paying` builds
  three self-service routes in Python gated on `plans_enabled`, and there is no
  programme table anywhere. **No assistance programme was built.**
* **`/money-back`'s `What would you like to do?` radio cards and `Send me
  $84.20`.** A refund election is a write this product has no path for, and it
  is not one of the six kinds.

---

## 7 · Two fixtures that could not tell a working link from a broken one

`HelpPaying.dom.test.tsx` and `MoneyBack.dom.test.tsx` mounted their screens
**bare inside a `MemoryRouter` with no `/:tenant/portal` route** — the exact
fixture defect hard-won law 2 names: `useParams().tenant` is undefined, so
every address the page builds comes out `//portal/…`, a protocol-relative URL
to another host that reads as a perfectly good string to `toContain`. Both now
mount under the real path pattern, and every door on this patch is asserted as
a **whole** address.

⚠ **That is not theoretical here.** This lane wrote `to: view.join_at` on
`/level-pay/standing` — `PortalWayOut.to` is documented as needing an
ALREADY-RESOLVED address, where `ErrandLink` resolves its own — and
`LevelPayStanding.dom.test.tsx`'s TC-5 went red on the whole address. The bug
existed for about four minutes and the fixture is the only reason.

---

## 8 · What this lane could not do

* **`CPB-17` — a signed-out visitor at a signed-in address.** Nine of these ten
  screens render the STAFF `FailedWithRetry` panel on a 401: a grey box outside
  the utility's frame offering *Download error report*, with no nav and no
  sign-in link. `/fees` is the one that handles it properly and is the worked
  example. It is one shape repeated across 34 screens — frame work, not this
  lane's.
* **A telephone number beside a refusal.** *Ring us to answer this offer* names
  no number. `PortalFront.emergency_phone` is what `PublicPricesView` uses, but
  it is the EMERGENCY line and a billing query is not an emergency; and the
  signed-in views take no `front`. Worth a general answer rather than a
  per-screen one.
* **A kit shape for a GROUP of held controls sharing one reason.** `/plan-offer`
  composes the kit's `Button disabled` plus one reason line in `HeldButton`'s
  own type and colour. `primitives.tsx` is lane 1's this session.

---

## 9 · The screen id goes back in the SOURCE — the cost of the frame conversion

Putting all ten screens on `PortalScreen` was right for R-10 and had one effect
nobody looks at. `PortalScreen` renders `data-screen` from a **prop**, so the
literal string `data-screen="CWP-057"` left the source of all ten files. The DOM
is identical, `tsc` passes, and every *rendered* assertion still finds the
attribute — so nothing went red.

**Three SOURCE scanners find a portal screen by that exact literal, and not one
of them reads a prop:**

| Scanner | What it decides | Effect of the blind spot |
|---|---|---|
| `pageHeadCensus.test.ts` · `screenFiles()` | which files the head census covers | ten screens dropped out of the census |
| `g100_every_screen_has_a_door.py` · `SCREEN_MARK` | **which screen a door is on** | worse than unseen — see below |
| `g103_holds_cannot_rot.py` · `DECLARES_SCREEN` | which files it reads for expired holds | *(no effect — see below)* |

⚠ **THE `g100` EFFECT IS SHARPER THAN "INVISIBLE", AND THIS LANE FIRST WROTE IT
DOWN WRONG.** The table above said *ten screens unreachable*. It is the opposite.
`reachable()` reads:

```python
if not screens:
    everywhere |= landing
    continue
```

A file with no literal is not an unknown screen to that gate — **it is read as
THE FRAME**, and its doors are folded into `everywhere`, which seeds the walk
beside the roots. So those files' doors are not lost, they are **promoted to
universally reachable**: the gate then reports reachability it has not proven.
Found by lane 4 going to read `reachable()` rather than relaying this lane's
claim, and verified here at lines 327-328 before being written down.

⚠ **AND THE CONSEQUENCE MUST NOT BE OVERSTATED EITHER.** Lane 4 measured the
counterfactual instead of assuming it: recomputing the walk with those files
given their true ids yields **52/52 both ways**, and the set of screens whose
reachability depends ONLY on the misclassification is **EMPTY**. `g100`'s PASS
is honest today — by the shape of the door graph, not by construction. The blind
spot is real and unfired, and *"green while it cannot see seven screens"* invites
the reading that the gate is lying, which it is not.

**Fixed the way `bills/BillDetail.tsx` already does it.** `PortalScreen` keeps
the loading, empty and failed branches — that is how the head reaches them, and
it is the whole point of lane 1's frame — and the **populated** branch declares
the literal itself. Each of the ten carries the reason in its own source so the
next lane does not tidy it back into the prop.

⚠ **`g103` turned out NOT to be blind, and that matters more than the relief.**
Its front-end loader takes a file when `rel.startswith("portal/")` **or** the
literal matches, so the two hold notes this lane rewrote WERE checked — its
PASS over 36 holds was real. `g100` has no such fallback and was genuinely
blind. Both were run rather than assumed, because **a declared blind spot with
no number beside it is indistinguishable from an empty one.**

⚠ **AND RESTORING VISIBILITY IMMEDIATELY SURFACED A RED THAT IS NOT THIS
LANE'S.** `g100` now fails:

```
FAIL: payments/PayNow.tsx points at "/pay-now/check", which no registered screen serves
    | payments/PayNowCheck.tsx points at "/pay-now/done", which no registered screen serves
```

Dated rather than dismissed, per hard-won law 7 habit 1 — `git log -S
'data-screen="CWP-' origin/claude/hi-0jmv62 -- <file>`, naming the branch:
commit **`e1489091e`** (2026-09-11, *CR-085 step 2 lane 6*) removed BOTH of
`PayNow.tsx`'s `data-screen="CWP-038"` literals and created `PayNowCheck.tsx`
and `PayNowDone.tsx` carrying none. One commit, today, another lane's. It is the
same defect as this section and it is reported, not fixed.

## 10 · `CWP-042` is drawn two ways, and the screen is built on what they agree

Restoring the literal made `plans/AskForPlan.tsx` visible to the census again,
and the census went red on it: the file is listed in `STEP_BAR_INSTEAD` — the
screens drawn with a `Stepper` *instead of* a page head — and this lane had
given it a `PageHeader` for `DEF-CWP-4912`. **That is the list doing exactly
what its author built it to do**, and the red is this lane's.

The two frames disagree:

| Source | What it draws for `CWP-042` |
|---|---|
| `08-screen-layouts.md` T2 line · `wireframes/CWP-042.png` | `Stepper` → `Card`. **No head.** |
| `CR-085` lane 7 drawing, *Screen 42*, at **390 AND 1280** | `← Past due` / *Ask for a payment plan* / *Spread what you owe over several months*. **No stepper.** |

**Decided here, not escalated** (hard-won law 13 — a judgment recorded is the
deliverable): **build the shape they agree on and delete neither.** The head
names the TASK, the step bar names the STEP. The exemption's stated reason —
*"a page head would say it twice and disagree"* — does not apply, because the
two do not say the same thing.

So the `STEP_BAR_INSTEAD` line is removed, with that reasoning written where it
stood, and the drawing's `← Past due` back link is added on
`portal.overdue.title` — a key all eleven catalogues already hold, so **no
catalogue churn**.

**The exemption's cost was measured rather than argued.** `SectionTitle` renders
a `<p>`, not a heading. With no `PageHeader` this screen had **no heading
element anywhere**, so the first one a screen reader met was the rail's
`<h3> There may be help too` — announced as the page, to someone who had just
arrived from the overdue screen.

⚠ **`payments/PayNow.tsx` IS IN THE SAME POSITION AND WAS LEFT ALONE.** It
composes `PageHeader` today (`DEF-CWP-4926`, citing blueprint 35) and is still
listed in `STEP_BAR_INSTEAD`. It does not fire only because it declares no
literal `data-screen`, so `screenFiles()` cannot see it — the §9 defect hiding
the §10 one. The day lane 6 restores that literal the assertion goes red naming
it, and the answer will be this same one. Not this lane's screen.

---

## 11 · Walked in a real browser at 390 AND 1280 — and the phase that actually tests R-10

`10-scripts/render-checks/cr085-lane7-money-is-tight.mjs`, run against **this
worktree's own `dist`** on a private port with the API proxied to the shared
backend — never the shared stack on `:8401`, which is six lanes' at once.

`npm run build` — **`tsc --noEmit && vite build`, both green** — is what produced
that `dist`, which is the check the brief singles out: vitest does not typecheck,
so a green suite over a tree that will not compile is exactly how a branch stays
red for a day. `npm run lint` (`eslint src --max-warnings 0`) also clean.

**Phase 1 — the ten addresses as the tenant actually is: 64/64 checks, 0 failed,
no JS error on any route, at both widths.** Each screen reported which branch it
settled in rather than being assumed into one:

| settled | screens |
|---|---|
| populated | `/help-paying` · `/level-pay` · `/ask-for-a-plan` |
| empty | `/overdue` · `/level-pay/standing` · `/plan` · `/plan-offer` · `/protections` · `/money-back` · `/fees` |

⚠ **IT DOES NOT WAIT ON `[data-screen="CWP-…"]` TO MEAN "THE DATA ARRIVED"
(`DEF-CWP-4941`).** R-10 and R-22 put that mark on the loading and failed
branches too, which is right and which silently turns every such wait into a
RACE — it resolves against the LOADING card, and on a busy machine the same
bundle then reports faults that are not there. **A check whose answer depends on
the load average is not a check.** So this waits for the mark with
`state: "attached"`, waits for `[data-portal-state="loading"]` to DETACH, and
only then reads the branch. The same fault was live in two walkthroughs over
these screens — `cr068-l-overdue-and-protections.mjs` (11 readiness waits) and
`cr068-m-plans-and-level-pay.mjs` (2 waits, 6 locator reads) — and both are
fixed with one shared helper.

⚠ **AND PHASE 1 ON ITS OWN PROVES NOTHING ABOUT R-10, WHICH IS THE WHOLE POINT
OF THIS LANE.** A seeded tenant in good standing never shows a failed card. Ten
healthy screens is ten screens that were never asked the question. **R-10 is a
claim about BAD NEWS** — *"the thing they can do about it must be on that same
screen, next to the message"* — so phase 2 refuses all ten reads at the network
and drives every screen onto its failed branch deliberately, which is hard-won
law 7's *break the guard FIRST*.

Auth, `/portal/session`, `/portal/home` and `/portal/my-accounts` are left
alone: refusing those signs the customer out, and the walk would then be
measuring the sign-in screen while reporting on ten others.

For each refused screen it requires a failed card; a sentence inside it (R-22);
`role="alert"`; at least one way out INSIDE that same card; every way out with a
real `href` or an enabled button; and **every way out with a non-empty client
rect — because "right there" is a claim about PIXELS**, and this is the only
instrument in the repo that can see them. jsdom applies no CSS, so the DOM
suites beside these screens cannot tell a control that is on the card from one
that is `display:none`.

**Phase 2 — every read refused: all nine read-backed screens drew a failed card
at BOTH widths, and every way out on every one of them was inside the card,
wired, and really on screen.** `/ask-for-a-plan` is excluded: it is a form, not a
read, and has no failed branch by design.

**The whole walk: `172/172` checks, `0` failed, no JS error on any route.**

| Phase | Screens | Checks |
|---|---|---|
| as seeded, 1280 + 390 | 10 × 2 | 64 |
| every read refused, 1280 + 390 | 9 × 2 | 108 |

⚠ **ONE CORRECTION TO THIS LANE'S OWN EARLIER CLAIM, BECAUSE IT IS LAW 7'S SHAPE
AND THIS LANE WALKED INTO IT THREE TIMES.** `npm run lint` was reported clean
earlier in this work and **it was not**. `LevelPayStanding.tsx` and
`YourPlan.tsx` each carried an import this lane had stopped using —
`ErrandLink` and `SectionTitle` — and eslint errors on both:

```
20:3  error  'ErrandLink' is defined but never used    @typescript-eslint/no-unused-vars
27:3  error  'SectionTitle' is defined but never used  @typescript-eslint/no-unused-vars
```

The reason it read as clean is the same one three times over: **an exit code
taken from the end of a PIPE.** `eslint … | tail` reports `tail`'s status, not
eslint's, so the command prints its errors and exits 0. The same shape had
already bitten this lane once on a push-retry loop that announced *"PUSHED on
attempt 1"* over a REFUSED push, and once on a `grep -c` that returned 0 and
short-circuited an `&&` chain so the rest of the check never ran. **A check whose
exit status is its own last pipe stage cannot fail**, which is the *structurally
incapable of failing* entry in hard-won law 7, self-inflicted.

Verified properly afterwards — `eslint src --ext .ts,.tsx --max-warnings 0`, no
pipe, status read directly: **exit 0 over the whole of `src`**. The two unused
imports had already been removed at the tip by the close-out lane's *"lint goes
to zero"* commit; this lane's worktree was the stale copy, and both files are now
synced to the tip rather than pushed over it.
