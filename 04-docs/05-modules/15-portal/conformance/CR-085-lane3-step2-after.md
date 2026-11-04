# CR-085 step 2 lane 3 · **STARTING AND STOPPING SERVICE, FIXED** — what changed, what was watched go red first, and what was deliberately left alone

**This is the AFTER of `CR-085-lane3-findings.md`**, which is the same lane's
step-1 measurement and is the specification this work was built to. The drawing
it was measured against is `CR-085-lane3-drawing.md` beside it.

**Scope.** Four routes under `/:tenant/portal` — `/start-service`,
`/start-service/:draft`, `/stop-or-restart`, `/final-bill` — and the ten drawn
screens 15–24.

---

## 0 · THE FIVE DEFECTS, AND WHERE EACH ONE STANDS

| Row | Severity | What it was | Now |
|---|---|---|---|
| **`DEF-CWP-4877`** | high | Six fields marked required gated nothing; the refusal threw away the step the server sent | **FIXED** — one arithmetic, four callers, and the refusal names the step with the way back beside it |
| **`DEF-CWP-4876`** | medium | Steps 2, 3 and 4 drew no heading of any kind | **FIXED** — every step carries its drawn title and the address |
| **`DEF-CWP-4875`** | medium | `— deposit on your first bill.` on the first two screens of the move-in journey | **FIXED** — the line is absent, the panel keeps what is true |
| **`DEF-CWP-4874`** | medium | The missing fourth stop step lived only in a code comment | **WRITTEN DOWN, NOT BUILT** — `OQ-CWP-1767`, plan §12, decision log, and the comment is now a citation |
| **`DEF-CWP-4878`** | low | B14 rule 39's wizard anchors | **MEASURED, see §5** — lane 1 moved the shared ones; what remains is named with its figure |

**And two rows CLOSED that were already fixed in code and still read `open`:**
`DEF-CWP-4190` (the final bill's missing heading) and `DEF-CWP-4193` (four raw
machine dates), both at `cd2797715`, both re-checked in source before closing.

**And two NEW rows filed:** `DEF-CWP-4930` (high — an application for an address
we do not hold can never be sent; reproduced, **not fixed**, because the fix is
the server's rule) and `DEF-CWP-4931` (the staff failure panel on a customer's
signed-out screen; **fixed for this lane's two routes**, listed for the other
twelve).

---

## 1 · `DEF-CWP-4877` — THE HIGH ONE, AND BOTH HALVES OF IT

### What it was, walked

`Continue →` was live on step 2 with no date and on step 3 with all five boxes
empty. So an applicant could reach the commit, read back **`Applicant —`**,
**`Email —`**, **`Mobile —`**, press **Send my application ✓**, and be told:

> Finish an earlier step first.

Five words naming no step, no field and no way forward, at the one moment
somebody has decided to act.

⚠ **AND THE SERVER HAD BEEN SENDING THE STEP ALL ALONG.** `services.submit`
raises `portal.application.stepIncomplete` with `params={"step": missing[0]}`
under a comment reading *"⚠ THE DRAFT IS KEPT (US-CWP-013 TC-5). The refusal
names the step."* — **true of the wire and false of the screen**, because the
catalogue sentence has no `{{…}}` in it and i18next drops a parameter nothing
interpolates. That is hard-won law 1 in its plainest form.

### What was built

**ONE list, and four callers read it.** `unfinished()` in
`ApplyForService.tsx` is the browser's copy of
`applications.missing_before_submit` — the same seven keys, **in the same
order**, because the server refuses on `missing[0]` and a screen that held on a
different first item would name one step while the server named another.

| Caller | Asks |
|---|---|
| step 2's gate | is anything this step owns missing? |
| step 3's gate | the same, for its four |
| the commit's gate | anything steps 2 and 3 own |
| `firstUnfinishedStep` | which step to open a returning applicant on |

⚠ **`firstUnfinishedStep` WAS THE SECOND COPY, AND ITS OWN DOCSTRING WARNED
ABOUT IT:** *"Two rules disagreeing about may this be sent would be a second
arithmetic over the same question."* It was right, and there were two.

**The reason is VISIBLE TEXT and not only a `title`.** `BR-CWP-056` asks for
*disabled WITH the reason*; a tooltip is unreachable on the 390px phone the
portal is designed for, so each held control renders its sentence underneath as
well — the shape `HeldButton` already uses, with a live control in it.

**The refusal now names the step, and carries the way back.** R-10, verbatim:
*"the thing they can do about it must be on that same screen, next to the
message."*

> **Finish step 3 first.**  `Go to About you →`

⚠ **THE STEP KEY NEVER REACHES THE GLASS.** `params.step` is `start_date`,
`contact`, `company_name` — internal names, and B14 rule 31 keeps those off a
customer's screen. What renders is the step NUMBER in the sentence and the
step's own drawn NAME on the control, both out of the eleven catalogues.

⚠ **AND STEP 1's TWO KEYS GET NO BUTTON, DELIBERATELY.** `address` and
`services` live on `CWP-008`, which is another route, and re-entering it mints a
new draft token and loses everything typed. A control that did that would be
worse than none.

### A judgment recorded rather than asked (law 13): the asterisk came OFF the date of birth

`missing_before_submit` does not ask for a date of birth and the application is
accepted without one; **wireframe s17 draws the field with no required mark at
all**, and its own *WHY WE ASK* panel calls it the credit check rather than a
condition of applying. A screen demanding it would **refuse applications the
product accepts**, on the journey whose epic says in as many words that *"they
may never become a customer if we refuse them"*. The screen now agrees with the
server rather than the server being asked to agree with the screen.

---

## 2 · `DEF-CWP-4876` — EVERY STEP CARRIES ITS DRAWN TITLE AND THE ADDRESS

Measured in step 1 at 1280 and at 390: `h1` count **0**, `.page-header` nodes
**0** on steps 2, 3 and 4. The page went navigation → step bar → an eleven-pixel
section title. **The half that actually cost an applicant something: after step
1 nothing on screen said which address was being applied for.**

| Step | Title now | Sub-line |
|---|---|---|
| 2 | **When would you like it on?** | `<address> · step 2 of 4` |
| 3 | **About you** | `<address> · step 3 of 4` |
| 4 | **Check this, then send it** | `<address> · step 4 of 4` |

⚠ **TWO CATALOGUE VALUES MOVED FROM SMALL CAPS TO SENTENCE CASE RATHER THAN TWO
NEW KEYS BEING MINTED.** `portal.apply.whenHeading` and `portal.apply.aboutYou`
were `SectionTitle`s that opened those two cards — so giving the screens the
head the drawing asks for would have put **the identical words directly above
them**, which is B14 rule 32's own failure case. Wireframes s16 and s17 draw the
sentence ONCE, at the top, with no section title above the first field.

⚠ **THE RESUMED HEAD IS UNTOUCHED, AND THAT IS THE DRAWING'S CALL.** s19 heads a
returning applicant *"Picked up where you left off. You started this on Sep 6
for 1841 Quarry Hill Ct…"* and names the step BELOW, in the section title —
*"ABOUT YOU — THE PART YOU DID NOT FINISH"*. So the section title is drawn on
that branch and only that branch, and **both heads carry the address**, which is
what was missing.

⚠ **AND THE HEAD IS INSIDE THE `data-screen` MARK.** It used to render above it,
so a rendered check selecting on `[data-screen="CWP-047"]` could not have seen
the heading at all — the same split `components/states.tsx` records as
`DEF-CWP-4926`. It is written out rather than composed from lane 1's
`PortalScreen` for one reason, stated in the code: this screen carries a SECOND
mark, `data-step`, which is what `cr068-c-start-service.mjs` and
`CheckAndSend.dom.test.tsx` select on to tell the three steps apart, and
`PortalScreen` has no slot for it.

---

## 3 · `DEF-CWP-4875` — A SENTENCE MAY NOT BEGIN WITH AN EM DASH

The first two screens of the move-in journey printed:

> — deposit on your first bill.

`money.py` fills `display` in **only** for a currency figure and says why: *"a
server that helpfully sent the string `Included` would have made this one cell
English-only on ten of them"*. So `kind: "none"` correctly means *there is
nothing to quote*, and the screen interpolated `?? "—"` into a SENTENCE.

**A table CELL may be a dash and a sentence may not.** `Money` in
`StartService.tsx` is the cell case and is right as it stands; the bullets now
come from one exported helper, `ifYouApplyBullets`, which **omits any line whose
money cell is not an amount** and keeps the two that are still true:

> $90.00 before we start. · About 3 working days.

⚠ **THE PANEL IS NOT DELETED WHOLE.** Wireframe s16's `NO ESTIMATE AVAILABLE`
state says *"The panel is absent, not shown with a dash"* of the ESTIMATE panel;
deleting this one would take two true sentences with it. The line goes; the
panel stays.

⚠ **ONE COPY, IMPORTED BY BOTH SCREENS**, because the defect was filed against
both and a second copy is a second place the dash comes back.

---

## 4 · `DEF-CWP-4874` — WRITTEN DOWN, NOT BUILT

The stop journey builds **three** steps against **four** drawn. The missing one
asks *where should the final bill go?* — a forwarding address, the deposit we
are holding shown as a figure, and where to send the refund.

**`POST accounts/{id}/stop-or-restart/ask` accepts four things and none of them
is one of those three:** a stop date, a restart date, a reason and a contact.
`GET stop-or-restart` serves no deposit either. **The build is right to refuse
it** — boxes that posted nowhere would collect the one thing a leaving customer
most needs us to have and drop it (hard-won law 2).

**What was wrong is that the whole record lived in a code comment.** No
question, no defect row, no plan entry — which is `DEF-CWP-4203`'s own escape
reason (*"A DEFERRAL WRITTEN AS A CODE COMMENT IS NOT TRACKED BY ANYTHING"*).
It is now in four places:

* **`OQ-CWP-1767`** (OPEN) — the question in plain English with three costed
  options, and the observation that makes the cheap one cheap: **a forwarding
  address already has a lawful home** in `customers.addresses` `kind='mailing'`,
  CLAUDE.md hard rule 8's first exception, *where the BILL goes*;
* **`10-execution-plan.md` §12** — the plan row, which also names the other end
  of the same gap: `CWP-032`'s drawn **WHERE WE SENT IT** block cannot exist
  while this step does not;
* **the decision log of 2026-09-11**;
* **the docstring**, which now CITES those rather than being the record.

⚠ **AND THE FOUR-DATE TIMELINE IS DECIDED RATHER THAN ASKED.** s23 ends with
*meter read Sep 30 · final bill around Oct 5 · due around Oct 20 · deposit back
by Nov 4*. Nothing on the wire carries any of the four, and the blueprint's
**R-23** — *no sentence states a fact it does not derive* — forbids printing
them. **They stay absent**, so a lane reading the drawing later does not
"fix" it by computing four dates in the browser on the screen that closes a
household's water.

---

## 6 · THE TWO RULES THAT ARE LAW, ON MY SCREENS

**R-10** — *"when a screen tells a customer something bad, the thing they can do
about it must be on that same screen, next to the message"* — and **R-22** —
*"differntiate it using text message"*.

Signed out, `/stop-or-restart` and `/final-bill` both drew the STAFF failure
panel: a red *Failed* pill, *"We could not open this page."*, the sentence
*"You're signed out. Sign in again to continue."* and three controls —
**Retry · Download error report · Cancel**. Two things wrong at once: the
sentence tells the customer to sign in and **there is no sign-in control
anywhere on the page**, and *Download error report* is an engineer's control a
customer has nowhere to send. That is blueprint spec **`CPB-17`**, whose own row
says *"True of every signed-in screen, not just one."*

**Both routes now render `PortalState`** with the refusal's own sentence
(`errors.auth-001`, which is already exactly right) and two real ways out inside
the card: **Sign in**, a real portal address so ⌘-click opens it in a second
tab, and **Retry**, the shell's own refetch.

⚠ **`Signed` GAINED AN OPTIONAL PROP RATHER THAN A REWRITE.** It serves four
routes and two of them belong to lanes running in those files right now, so
`/requests` and `/level-pay-standing` are **byte-identical** — the default
branch is untouched. `DEF-CWP-4931` lists the remaining twelve page files so the
next lane can finish it in one pass.

---

## 7 · WHAT WAS DELIBERATELY NOT DONE, AND WHY

* **`R-07` — *one filled button per screen* — IS BROKEN ON SCREEN 15 AND WAS NOT
  FIXED.** After a successful address check there are **two** `variant="primary"`
  buttons on screen at once, `Check →` and `Continue →`. R-07 is one of the
  blueprint's twelve rules marked *NO HOME — stated only here*; it is a
  **proposal**, not law, and a lane that builds to an unratified rule makes it
  law by default. Recorded, not fixed.
* **`R-15` — *a back-link sits under the bar, never inside it* — WAS RULED
  AGAINST.** The PO chose *our signed rules win, blueprint yields*, so a footer
  `← Back` inside a stepper keeps meaning *previous step* (r10 rule 1). Not
  moved.
* **`R-04`, `R-05`, `R-06`, `R-09`, `R-18`, `R-19`, `R-23`** — proposals.
  Nothing was built to them. (R-23 is *obeyed* in several places, which is a
  different statement: the product declines to print a date it cannot derive.)
* **`PortalScreenIdTag` uses `px-[9px] py-[3px]`** — two banned arbitrary values
  — but it is frame, it is behind an env flag, and `13-wireframe-delta.md` 32.12
  already rules the badge legitimate. Left alone; reported here.
* **`DEF-CWP-4930` was reproduced and NOT fixed.** The fix is
  `missing_before_submit`'s rule, which is shared with the clerk-side service
  request, and this lane is scoped to four routes' screens. The front end also
  deliberately does **not** hold *Send* on `services`: a held button would turn a
  bad refusal into a dead end.
* **`Card`'s `gap-4` (field → field 16 against rule 39's 20) was not changed.**
  It is `primitives.tsx`, which this lane was told not to touch, and it is the
  kit's own container rather than a per-screen class — lane 1's note calls it
  *"the one anchor this lane did not fully close"* and carries it on
  `DEF-CWP-4856` as **partially-fixed**.

---

## 8 · HOW IT WAS PROVED — AND EVERY GUARD WAS WATCHED GO RED FIRST

Hard-won law 7: *prove a new guard goes RED before trusting it green*, **in the
harness that will run it**.

| Guard | Broken by | What it said |
|---|---|---|
| the step-2 and step-3 gates | putting `disabled={props.saving}` back | 3 cases: *expected false to be true* |
| the named refusal | putting `refusalText(t, error)` back | *expected 'Finish an earlier step first.Go to Ab…' to contain 'Finish step 3 first.'* |
| the em-dash guard | putting `?? "—"` back | *+ "— deposit on your first bill."* |
| the page heads | deleting `{props.head}` from all three steps | 5 cases: *expected undefined to be 'When would you like it on?'* |

⚠ **AND TWO OF THE FAILURES CAME FOR FREE, WHICH IS THE BEST KIND.** The two
pre-existing cases *"Continue reaches ABOUT YOU"* and *"step 3 draws the
proof-of-identity box HELD"* clicked `Continue` on an **empty** draft and
reached step 3 — **that is the defect, asserted as correct behaviour.** They
went red the moment the gate landed and now answer the step first.

---

## 9 · THE BROWSER RUN THAT WAS OUTSTANDING — AND THE ONE THING IT CAUGHT THAT 325 GREEN TESTS DID NOT

The first push of this lane said plainly that
`10-scripts/render-checks/cr085-lane3-start-and-stop.mjs` was **written and
unrun**, because the container was at load 100–168 and three `tsc` runs had been
OOM-killed. It has now been run, twice, and hard-won law 6 earned its keep
again.

**RED FIRST, AND AGAINST A REAL PRE-FIX BUILD.** The shared stack on `:8401`
still serves the bundle from before this lane landed — it contains the old
five-word refusal and none of the new markers — so it is not a mock of the
defect, it **is** the defect. Pointed at it, the check failed on exactly what
each row was filed for, and printed the evidence rather than an exit code:

```
IF YOU APPLY: ["$90.00 before we start.","— deposit on your first bill.","About 3 working days."]
⛔ no sentence in IF YOU APPLY begins with an em dash          ← DEF-CWP-4875
h1: []
⛔ exactly one <h1> on the step (0)                            ← DEF-CWP-4876
⛔ and the reason is visible text beside it, not only a tooltip ← DEF-CWP-4877
⛔ Continue is HELD on an empty form                            ← DEF-CWP-4877
locator.innerText: Timeout 30000ms exceeded waiting for locator('[data-step-held]')
```

Then, against this lane's own build on `:8413`: **ALL CHECKS PASSED**, at
**390 and at 1280**, both.

### ⚠ THE RESIDUAL — STEP 2 NAMED NO ADDRESS, AND THE SUITE WAS GREEN OVER IT

The first run of the fixed build was **not** clean. Two assertions failed, at
both widths, and both on step 2 only:

```
⛔ the sub-line says step 2 of 4
⛔ and it names the address being applied for — which step 1 was the last place to say
```

**On the exact screen `DEF-CWP-4876` was filed about**, whose whole complaint is
that *after step 1 nothing says which address is being applied for*. Steps 3 and
4 passed.

**Why the suite could not see it, and it is worth more than the fix.** The head
read `props.draft?.address_as_given` and nothing else. A first visit reaches
step 2 with **no draft**: step 1 hands the address over in the address bar and
the draft is not written until the seeding save comes back. The page component
has always known this — it reads `draft?.address_as_given ?? search.get("address")`
— and the wizard inside it did not, so the two differed by exactly one step.
**In the fixture `saveDraft` answered instantly**, so `props.draft` was populated
before any assertion could run and all three heading cases were really testing
the *seeded* state. They passed. The screen was wrong.

That is law 7's *looking at the wrong thing* wearing a green tick, and law 2's
fixture clause — *a fixture that cannot tell a working link from a broken one is
how it hid* — in a new shape: a fixture that cannot tell a **round trip** from an
instant answer.

**The fix** is one line in `ApplyForService.tsx`: the wizard head applies the
same query-string fallback the page already applies. **The guard** is a new
fixture flag, `saveHangs`, that keeps the seeding save in flight — which is what
a first visit actually looks like — and one case, proved red first:

```
× step 2 BEFORE the draft exists — the head still names the address (DEF-CWP-4876, residual)
  AssertionError: expected 'START SERVICEWhen would you like it o…' to contain '31 Palm Ct · step 2 of 4'
  Tests  1 failed | 29 passed (30)
```

**29 of 30 passed with the product broken.** The new case is the only one in the
file that can see it.

### `DEF-CWP-4878` — MEASURED, NOT ASSUMED, AND NOW CLOSED

The brief said *verify with `getComputedStyle` at both widths; do not assume*.
Measured on the running page, identical at 390 and at 1280:

| Rule 39 anchor | Required | Measured |
|---|---|---|
| wizard step cell | 16×20 | **16×20** ✓ |
| wizard step icon gap | 12 | **12** ✓ |
| wizard rail margin-bottom | 24 | **24** ✓ |
| label → input | 5 | **5** ✓ |
| input → helper | 6 | **6** ✓ |
| field → field | 20 | **16** ✗ — `Card`'s `gap-4` in `primitives.tsx`, out of scope, carried on `DEF-CWP-4856` |

`PortalScreenIdTag`'s `px-[9px] py-[3px]` is untouched and reported, as
instructed — it is `states.tsx`.

### WHAT WAS PROVED THIS TIME, WITH FIGURES

* **full-project `tsc --noEmit` RAN** (it had been OOM-killed three times) and
  reports **one** error, and it is **not this lane's**:
  `src/portal/payments/Fees.dom.test.tsx(281,14): TS2304: Cannot find name 'QUOTE'`.
  Dated per law 7 habit (1): `git log -S "QUOTE" -- <file>` → **`0c85f58ce`,
  2026-09-11, `CR-085` step 2 lane 7**, which is still running. **So
  `npm run build` is RED on the branch again**, days after `DEF-GOV-4929` was
  raised for the same thing. The four files that had never been typechecked —
  `requests/signedOutState.tsx`, its test, `StopOrRestartPage.tsx` and
  `FinalBillPage.tsx` — are **absent from the error list**, so they are clean.
* **`signedOutState.dom.test.tsx` RAN** — it had never once been collected.
  **5/5 in 15.9s**, against a 970s timeout before. Both its guards were watched
  red first: removing the sign-in way out gave *expected null not to be null*
  (R-10), and making the failed state repeat the loading sentence gave
  *expected 'Opening your account…Sign inRetry' to contain "You're signed out."*
  (R-22).
* **`src/portal/{guest,requests,bills}`: 24 files, 326 tests, all green** (325
  before the new case).
* **eslint over the same three directories: exit 0.**
