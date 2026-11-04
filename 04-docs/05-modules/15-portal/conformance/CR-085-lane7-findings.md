# CR-085 · lane 7 · WHEN MONEY IS TIGHT — what is built, against the drawing

**Identify only. Not one line of product code was changed by this lane.**
The drawing is quoted, verbatim and in order, in `CR-085-lane7-drawing.md` beside
this file. Read that first; this file is the delta.

| | |
|---|---|
| Read at | **`2.235.0`**, commit `b4063d1e6`, 2026-09-11 |
| Routes | `/overdue` `/help-paying` `/level-pay` `/level-pay/standing` `/plan` `/plan-offer` `/ask-for-a-plan` `/protections` `/money-back` `/fees` |
| Screens | `CWP-057` `CWP-056` `CWP-044` `CWP-066` `CWP-043` `CWP-063` `CWP-042` `CWP-064` `CWP-045` `CWP-050` |
| Read in | source, and **in a browser at 1280 AND 390**, in four states — populated, empty, failed and signed-out |
| Defects filed | `DEF-CWP-4911` … `DEF-CWP-4920` (ten) |

### How the browser read was done, and why it is not the shared stack

⚠ **THE SHARED STACK CANNOT SHOW THESE SCREENS POPULATED, AND SAYING SO IS PART OF
THE FINDING.** `http://127.0.0.1:8401` serves tenant `brazosbend`, on which
`GET /settings/sample-data` answers `has_run: false`, `seeded_total: 0`; the tenant
holds **one** account (`AC-2026-00001`, Elena Rivera, balance `0.000000`), **no**
`portal_credential` — `POST /portal/auth/sign-in` answers `{"ok":false,"reason":"wrong"}`
for its only contact — and `portal_settings.is_live` is **false**. So on the shared
stack all nine signed-in screens render the signed-out panel and nothing else. That
state was read and is reported below; it is `CPB-17`.

For the other three states the SHIPPED BUNDLE (`07-frontend/dist`, built at
`77689eb3a`; the rule-39 commit `b4063d1e6` touches only documents) was served by a
second `server.mjs` on a private port against a stub API returning the shapes
`portalClient.ts` declares, carrying **the blueprint's own figures** so the running
screen could be read beside the drawing. Nothing on the shared stack was restarted,
re-seeded or killed. The stub and the walkthroughs are this lane's scratch files,
not repository code.

⚠ **WHAT THAT DOES AND DOES NOT PROVE.** It proves what the shipped components
RENDER for a given payload — layout, order, labels, states, spacing, both widths.
It proves nothing about what the SERVER would actually send. Every claim below that
depends on the server is taken from `apps/portal/` source and says so.

---

## 0 · The two findings CR-085's own history records — both re-verified

**(a) "Past due had no Pay button at all" — FIXED, confirmed in a browser.**
`CWP-057`'s rail panel *You can stop this* now carries three controls in one group:
**`Pay $247.30`** (filled), **`Ask for a payment plan`** and **`See what help there
is`** (both outlined), in that order, with the amount taken from the server's own
`owed` through the label Home already uses. That satisfies the drawing's PRIMARY
ACTION note exactly — *"Pay is filled; the plan and the assistance route are outlined
and equally prominent as a pair."* ⚠ **`DEF-CWP-4143` is still `open` in the
register** and should be closed against this reading.

**(b) "Budget billing reachable only through Help paying" — FIXED, two doors now.**
`Payments.tsx`'s `ERRANDS` list carries `{key: "level-pay", to: "/level-pay"}` as one
of eight errand cards, and the Help paying route card keeps its own link. The comment
beside the change is right; ⚠ **a second comment seventeen lines below it still says
`/level-pay` is "DELIBERATELY NOT HERE" and gives a reasoned argument for removing the
door CR-085 added** — filed as **`DEF-CWP-4918`**.

---

## 1 · Screen by screen — every difference

Each block lists **MISSING** (drawn, not built), **EXTRA** (built, not drawn),
**WORDS** (present but different), **ORDER/STATE**, and what is **RIGHT** — because a
list of only faults misreports a screen that is mostly correct.

### `CWP-057` · Past due · `/overdue`

**RIGHT.** Title *Past due* — the drawing's WORDS note, obeyed. One heading, not two
(`DEF-CWP-4144`'s first half is fixed). The three ways out, grouped, pay filled. The
ladder as this account's own record. A future rung reads *no earlier than 08/27/2026*
rather than a date the product will not act on. The deposit renders as
*required, ask us the amount* — an absence in words, no `$0.00`, no em-dash. Colour
is not the only signal: the chip says **TEN-DAY NOTICE** in words.

**MISSING**
* **The whole `WHAT MAKES UP THE $247.30` breakdown** — the drawing's four rows
  (July bill · August bill · Late fee · Total). The screen's rail panel *What it would
  cost* is a different question (owed + reconnection + deposit). ⚠ **This is a DATA
  gap, not a screen gap:** `PortalArrears` carries no per-bill breakdown at all, so
  there is nothing for the screen to draw. The drawing calls it out by name under
  COGNITIVE LOAD — *"customers frequently do not recognise the total"*.
* **The due DATE.** `due_on` is on the wire and no line of `Overdue.tsx` reads it;
  the headline is the relative *"$247.30 is overdue by 22 days"*. The drawing states
  the date in both frames and names it under TONE. `DEF-CWP-4919`.
* **`Ask for a payment plan — from $20.61 a month`** — the drawn label carries the
  cheapest instalment so the alternative is priced before the customer clicks.
* **The explicit shut-off sentence** *"Your service is scheduled to be shut off on
  Aug 27, 2026 unless this is paid, or you arrange a plan, or help is approved."* The
  same fact is in the timeline's last two rows instead.
* **`Any one of these stops the shut-off.`** Built: *"Paying, or agreeing a way to
  pay, stops all of this today."* — same meaning, above the buttons, so this is a
  wording delta rather than an absence.

**WORDS** — `See if you qualify for help paying` → `See what help there is`.
`Total past due` → *So far that comes to* (correct, because the built row is a
subtotal with a named missing part, which the drawing's row is not).

**STATES** — `PROTECTED` is built (`held_by` → *Something is holding this*, with
*"The money is still owed"*). `ALREADY DISCONNECTED` is **not** a distinct state: the
screen has no restore-first branch. `LATE, NOT YET NOTICED` is served as
`tier_unmapped` / no-date rows rather than the drawn *"says when one would be issued"*.
**EMPTY** — *"Nothing is overdue on this account."* — correct per `BR-CWP-093`.
**FAILED** — *"We could not read this right now. Try again in a moment."* in a card
**with no retry control** (true of all eight signed-in screens in this group; the
shell's own `FailedWithRetry` has one).

**NINE FIELDS SERVED AND UNREAD:** `due_on`, `case_open`, `chips`, `tier_reached_on`,
`ladder_running`, `halt_code`, `scheduler`, `reconnection_fee_absence`,
`new_deposit_required`.

---

### `CWP-056` · Help paying · `/help-paying`

⚠ **THIS IS THE LARGEST DIVERGENCE ON THE PATCH AND IT IS A DIFFERENT SCREEN, NOT A
DIFFERENT LAYOUT.** The drawing is a **catalogue of assistance programmes** — five
cards, each with an amount and a qualifying test. What is built is **three
self-service routes**. Only one card overlaps.

| The drawing's five | Built |
|---|---|
| `ENERGY ASSISTANCE — THE BIGGEST ONE` · typical award `$300 – $600` · household income limit `$3,660 a month for 4` · **`Check if you qualify`** | **absent** |
| `SENIOR DISCOUNT · 15% OFF EVERY BILL` · `→ Apply` | **absent** |
| `LOW-INCOME CREDIT · $25.00 A MONTH` · `→ Apply` | **absent** |
| `MEDICAL CERTIFICATE` · `→ Apply` | **built** as *Someone here is unwell · Send a certificate* |
| `ONE-OFF EMERGENCY HELP` · `→ Find help near you` | **absent** |
| — | **EXTRA:** *Spread it out · Ask for a payment plan* |
| — | **EXTRA:** *Level out next year · Look at budget billing* |

* **MISSING:** *"You may qualify for more than one of these at the same time."*
* **MISSING:** every figure. The drawing's whole argument under COGNITIVE LOAD is
  that an amount and a test let somebody self-assess in two seconds.
* **MISSING:** the drawing's RULES line — *"Every programme is tenant-configured"*.
  Measured: `selectors.help_paying` builds the three routes in Python, gated only on
  `portal_settings.plans_enabled`; there is **no programme table** anywhere.
* **PRIMARY ACTION is on the wrong card.** One filled button (R-07 satisfied
  numerically) and it is `Send a certificate` — the narrowest of the three. The
  drawing puts the filled action on the LARGEST programme.
* **RIGHT:** the moratorium is drawn as an `InfoBar` **with no control** — the
  drawing's *"one of them is not a door"*, obeyed, with its window read from the
  record rather than written into the copy.
* **RIGHT:** the `past_final_notice` band says *"All three are still open — please ask
  today"* rather than closing a route. `OQ-CWP-1601` records why.
* **STATES:** `ALREADY RECEIVING`, `APPLICATION OPEN`, `SEASON CLOSED` and
  `NONE CONFIGURED` are **none of them built** — there is no programme to be in a
  state. There is no empty branch at all: the three routes are unconditional.

---

### `CWP-044` · Budget billing · `/level-pay`

**RIGHT.** *"This spreads your bills — it does not lower them."* is on the screen,
bold, **above the button**, exactly where the drawing's HONESTY note puts it. The
customer's own twelve bills are the argument. The word *level pay* appears nowhere on
screen — the drawing's WORDS note obeyed. One heading, not two (`DEF-CWP-4183` fixed
on this screen). The *not enough history* branch names WHICH month and when it becomes
possible, which is more than the drawing asks.

**THE LIVE REFUSAL, AND WHAT IT ACTUALLY BLOCKS — the brief's question, answered.**
There are **two** refusals on this screen and `CPB-18` names only one of them.
1. `portal.levelPay.cannotCompute` — *"We cannot work out a monthly amount for this
   account at the moment."* This **is** `CPB-18`'s quoted sentence. It is the
   **last-resort branch**: it draws only when the account has enough history AND no
   gap explains the absence. It blocks **the figure**.
2. `portal.levelPay.joinHeld` — *"Ring us to join budget billing"*, under a disabled
   **`Join budget billing ✓`**. This one is **unconditional** — `LevelPay.tsx` line
   385 renders `HeldButton` with no test at all. It blocks **enrolment, for
   everybody, always**, including the customer for whom the figure computed
   perfectly. **`CPB-18`'s card does not mention it**, so a reader of the blueprint
   would conclude that working out the amount is the only thing in the way. It is not:
   *no customer can join budget billing from this portal under any circumstances.*
   The hold is registered in `routing/holds.ts` as `unwatched` against `OQ-CWP-1568`
   — which is open — and the server already sends `join_held` / `join_held_reason`
   that the screen never reads (`DEF-CWP-4913`).

**MISSING**
* The four-figure strip `Your lowest $142.10 · Budget amount $171.40 · Your highest
  $228.75 · A year costs $2,056.80`. Built instead: *Your last 12 months · Monthly
  average · Rounded to*. Lowest and highest — the range that makes the argument — are
  nowhere.
* `HOW THE SETTLE-UP WORKS`, the drawing's four explicit rows. Built: a three-bullet
  *What this would mean*, which says the figure is checked and that August settles up,
  and does **not** say what happens if you paid too little (spread over 12 months, no
  interest) or too much (off your next bills, or refunded).
* `You can stop at any time. Any difference is settled then.`
* `every month, starting with your September bill` — the built total row says only
  *You would pay each month*.

**WORDS** — `Start budget billing` → `Join budget billing ✓` (the kit's commit
grammar; a deliberate divergence, worth ratifying rather than leaving as drift).
⚠ **The chart is titled *This month, either way* over twelve months of bills, in all
eleven catalogues** — `DEF-CWP-4915`.

**STATES** — `ALREADY ON IT` built (amount + settle month + door to standing).
`NOT ENOUGH HISTORY` built, and better than drawn. `NOT ELIGIBLE` **not built** —
there is no past-due branch and no link to the payment plan from here.
`SETTLE-UP DUE` **not built**.
**EMPTY** — ⚠ `position === null` renders *"We could not find an account to work this
out for."* — **bad news with no way out and no phone number**, the only one of the
eight empty branches on this patch that fails that test. See §4.

---

### `CWP-066` · Where your budget billing stands · `/level-pay/standing`

**⚠ THE STATED ABSENCE ON THIS PATCH IS HERE, AND IT IS HANDLED CORRECTLY — DO NOT
FILL IT.** The drawing's `WHAT HAPPENS IN AUGUST` panel computes the consequence:
*"that would add about `$11.88` a month"* and *"Your new monthly amount would be
around `$183.28`"*. **Nothing in this product computes a projected settle-up
instalment or a projected new level.** The built screen draws the panel's SHAPE — a
`ConsequenceBox` headed *IN AUGUST* — and states only what it can derive: *"You have
used $142.60 more than you paid, so that is added to the bill."* and *"We work out a
new monthly amount from the year just gone."* **No plausible number is invented.**
That is the right answer and it is recorded here so no later lane "completes" the
panel by dividing the variance by twelve.

**RIGHT.** Behind/ahead/level is the headline. The two-series chart (paid against
used) is the picture the screen is for. The override case shows the VALUE and never
the internal reason. `no changes yet` is a sentence, not an empty table.

**MISSING**
* `Paid so far $1,199.80` and `Used so far $1,342.40` as figures — the built KPI strip
  carries level, variance and settle month only. The two totals exist only as chart
  bars.
* `Months left  5`.
* `Budget year Sep 2025 – Aug 2026 · month 7 of 12 · $171.40 a month` — the sub-line.
  Built: *"7 months counted so far"*, in the rail, in grey.
* **`WHY YOU ARE BEHIND`** — the attribution panel the drawing calls out by name
  (*"'you are behind' is not actionable"*). Entirely absent.
* **`OR CLEAR IT NOW` and its `Pay $142.60`** — there is no pay control of any kind.
* **`→ Stop budget billing`** and *"Leaving budget billing settles the difference
  straight away."* — no leave control.
* `The flat line is what you pay. The bars are what you actually used.` — the legend
  is *What you paid · What it came to*, at the FOOT of the chart, distinguished by
  weight rather than by a stated mapping.
* `DEF-CWP-4180`'s two wireframe items (`↓ CSV`, `IF YOU LEFT TODAY`) — still absent.

**⚠ `POSTING DATE` IS PRINTED ON TWO KPI TILES**, in the largest type on the screen —
`DEF-CWP-4914`.
**AT 390** the *when the level changed* table's fourth column is outside its scroller:
the header renders as `BAL A` — `DEF-CWP-4917`.
**STATES** — `AHEAD` and `LEVEL` built (the variance direction picks the label and the
bullet). `JUST STARTED` **not built** as its own sentence. `REVIEW DUE` **not built**.
**EMPTY** — *"You are not on budget billing, so there is nothing to show here yet."*
plus a door back to `CWP-044`. Correct.

---

### `CWP-043` · Your plan · `/plan`

**RIGHT.** The schedule with three visibly different states (`PAID ON TIME` /
`DUE IN 18 DAYS` / `TO COME`). *New bills still arrive and still have to be paid* in
bold — the drawing's THE SEPARATION, obeyed. `If you miss a payment` is amber and says
the plan stays open. A closed plan stays on screen with its date. The agreement is a
real download (`CPB-03`'s release reached this screen too).

**MISSING**
* **`NEXT PAYMENT $82.44 / Due Oct 1, 2026 · in 18 days` as a panel** — the figure a
  customer opens the screen for. It exists only as a row in the table.
* **`Pay $82.44 now`** and **`Pay the whole $164.86`** — no pay control at all, while
  `/pay-now` is live and routed. `DEF-CWP-4181`, still open.
* **`Paid so far $82.44 of $247.30`** and **`Left to pay $164.86`.** ⚠ The drawing
  says in as many words that *"'Left to pay' is computed for them"*; the built screen
  makes the customer add `$82.44 + $82.42`. That is R-06 (*never ask a customer to
  compute*) breached on the exact line the drawing named.
* `3 months, agreed Aug 20, 2026 · $247.30 total` — the sub-line. Built: *"1 of 3
  paid."*
* `YOU ARE PROTECTED` as its own reassurance heading; built as *While the plan holds*,
  which carries the same three facts.
* **`CPB-21` — who set the plan up.** `PortalPlan` has no such field; the offer screen
  has it and this one does not. See §5.

**⚠ THE TITLE IS PRINTED TWICE**, one line apart — `Your payment plan` (h1) and
`YOUR PAYMENT PLAN` (section title). `DEF-CWP-4183`, still open on this screen.
**AT 390** the `STATUS` column — the only thing on the row a customer came for — sits
51px outside its scroller with no affordance. `DEF-CWP-4917`.
**STATES** — `ON TRACK` built. `MISSED ONE` served as an instalment state and there is
no amber account-level branch. `BROKEN` and `FINISHED` are not distinct branches; a
closed plan renders *Closed on {date}* and keeps the ordinary layout.
**EMPTY** — *"You are not on a payment plan."* + `Ask for a payment plan`. Correct,
and the file's own comment records that the bare sentence was the whole screen until
CR-085.

---

### `CWP-063` · The plan we can offer · `/plan-offer`

**RIGHT.** The instalment schedule with its total. *What accepting this does* as four
consequence bullets read from the server, with the late-fee bullet in two forms so a
plan without fee suspension says so. *Nothing happens until you accept* — a good
sentence the drawing does not have. **`CPB-21` is released here**: the lead reads
*"Dana Whitfield set this up on 08/20/2026"* and falls back to *the office* with the
absence stated separately when nobody was recorded.

**MISSING**
* **`ON TOP OF THIS, YOUR NORMAL BILLS CONTINUE` — *"A typical month is about $180.
  So from September you would be paying roughly $221 a month in total until
  February."*** The drawing calls this **THE TOTAL BURDEN** and says it *"is the
  number that decides whether somebody can keep the plan. Showing the instalment alone
  sets people up to fail in month two."* Built: one bullet, *New bills still arrive
  and still have to be paid*, with no figure. Nothing in the payload carries a typical
  monthly bill, so this is a data gap as well as a screen gap.
* **`Accepting is not a credit agreement and is not reported to anyone.`** The
  drawing's DIGNITY line, absent.
* **`· The shut-off notice dated Aug 27 is cancelled`** — the fourth bullet of
  `WHILE YOU KEEP TO IT`.
* **`THERE MAY BE HELP AS WELL` + `→ See help paying`.** Present on `/ask-for-a-plan`
  and absent here, which is the wrong way round: this is the screen where the customer
  is deciding.
* `6 MONTHS / $41.22 / a month, from Sep 1 · paid off Feb 2027` — the drawn headline
  block. Built: four `What it covers` rows.

**EXTRA** — a third control, `Decline`. The drawing's index row names two
(`Accept this plan · Ask for different terms`), though its body text requires the
customer to be able to decline, so this is defensible; recorded as an addition.

**ALL THREE CONTROLS ARE DEAD.** `Accept this plan ✓`, `Ask for different terms` and
`Decline` are greyed, unconditionally, on `OQ-CWP-1568` — so the screen the drawing
describes as *"the moment between the request and the agreement"* cannot produce an
agreement. **And the same six-word refusal prints three times in a row beneath them**
(`DEF-CWP-4920`). The server's `actions_held` flag that would release them is read by
nothing (`DEF-CWP-4913`).

**⚠ THE DEADLINE PRINTS AS A RAW WIRE DATE** — *"This offer stands until
2026-08-27"* — beside four dates in `MM/DD/YYYY` on the same screen
(`DEF-CWP-4911`). And on the running product it never prints at all: the server sends
`expires_on: null` with `expires_on_unavailable: "OQ-CWP-1566"` on every account, so
every customer reads *"We have not recorded a closing date for this offer."*
**⚠ THE TITLE IS PRINTED TWICE** — `DEF-CWP-4183`.
**STATES** — `COUNTER-OFFER` **not built** (nothing says the offer differs from what
was asked). `EXPIRED` **not built**. `DECLINED` and `ACCEPTED` cannot exist while the
controls are held.
**EMPTY** — absence + `Ask for a payment plan`. Correct.

---

### `CWP-042` · Ask for a payment plan · `/ask-for-a-plan`

⚠ **THE INTERACTION MODEL IS DIFFERENT FROM THE DRAWING'S, AND B14 RULE 38 DOES NOT
COVER THIS PART.** Rule 38 gives our UI rules the CONSTRUCTION of a form — where the
helper sits, the button order. **What the form CONTAINS is still the drawing's**, and
the drawing contains a **bounded choice of three terms, each showing its monthly
figure and its finish date**, with the protection panel beside the choice. Built: a
free-text months box, a native date picker, a free-text up-front box, and a
`See the instalments` button that must be pressed before any figure appears.

* **MISSING — the three `RadioCard`s** and with them the drawing's whole COGNITIVE
  LOAD argument: *"no division, no calendar arithmetic. '$41.22 a month, paid off by
  Feb 2027' is one decision, not two."* (`DEF-CWP-4182`, still open.)
* **MISSING — the finish date.** Nothing on the screen says *paid off by Feb 2027*,
  at any point, before or after preview.
* **MISSING — `First payment  Sep 1, 2026` pre-filled.** The date box opens empty as
  `mm/dd/yyyy`, which is also why the only button on the screen is disabled on arrival.
* **THE CRITICAL PANEL IS AFTER THE ACTION, NOT BESIDE THE CHOICE.**
  `WHILE THE PLAN RUNS` / `IF YOU MISS ONE` render only once `plan !== null`, i.e.
  after `See the instalments` is pressed. The drawing states the opposite in as many
  words: *"It is answered beside the choice, not after submitting."*
* **MISSING — `No interest and no fee, on any of these.`**
* **MISSING — `Most plans are approved straight away.`**
* **RIGHT — `THERE MAY BE HELP TOO` with its door**, and correctly OUTSIDE the preview
  branch, so it is on screen from arrival. The drawing's CROSS-LINK, obeyed.
* **RIGHT — the rounding note now renders only when a remainder exists**
  (`DEF-CWP-4140` fixed; the server's `carries_the_rounding` decides).
* **STILL OPEN — the refusal throws the server's answer away.** A 13-month request is
  refused 422 with `message_key: portal.plan.termOutOfRange` and `{min: 2, max: 12}`;
  `AskForPlan.tsx` catches everything into one `setRefused(t("portal.askPlan.couldNotRead"))`
  = *"We could not work that out. Please check the dates."* — which names neither the
  bound nor the field. `portal.plan.termOutOfRange` (*"Choose between 2 and 12
  months."*) exists in all eleven catalogues and is rendered by nothing.
  `DEF-CWP-4141`, confirmed still open.
* **STILL OPEN — step 3 `Agree` cannot be reached.** The `Stepper` draws three steps
  at `current={2}`; asking produces a reference card and the flow ends. `DEF-CWP-4182`.
* **⚠ NO PAGE HEADING AT ALL.** The only heading in the document is
  `H3: There may be help too`. `DEF-CWP-4912`.
* **NO EMPTY AND NO FAILED BRANCH** — the view renders the form whatever the balance
  read does; a balance that cannot be read simply does not draw, by design.

**B14 RULE 39 — MEASURED, NOT EYEBALLED. See §6.**

---

### `CWP-064` · Your protections · `/protections`

**RIGHT.** Three cards, three different sentences, keyed on LIFETIME — which is the
drawing's point. The payment-plan hold states *no date — see below* and the body says
it lifts the day an instalment is missed; **no date is invented**. A lifted protection
stays on screen marked `Lifted`. The rail states *A hold stops a disconnection. It
does not stop the debt.* — the drawing's HONESTY line, on the screen. Chips carry
words, so colour is not the only signal.

**MISSING**
* **THE VERDICT.** `WHERE YOU STAND RIGHT NOW` — *"You cannot be disconnected until
  Mar 31, 2027"* — is the drawing's first and most important element and there is no
  such panel. The drawing's COGNITIVE LOAD note: *"The verdict comes first, with its
  date."*
* **THE FULL LIST.** `EVERY PROTECTION, AND WHETHER IT APPLIES TO YOU` — six rows
  marked *applies / can apply / does not*. Built: only the protections this account
  already holds. A customer who holds none sees one sentence.
* **`WHAT MUST HAPPEN BEFORE ANY SHUT-OFF`** — the four numbered rules. Absent.
* **`These are the rules your utility follows. If you think one was missed, tell us.`
  + `Something went wrong — tell us`.** Absent.
* **EVERY CARD'S ACTION.** `→ Apply`, `→ Ask for one`, `Send a new certificate`.
  `ProtectionCard` accepts an `action` prop and `Protections.tsx` passes none.
  `DEF-CWP-4145`, confirmed still open, and it is hard-won law 2 in its purest form.
* **The icons.** The drawing marks every row (❄ 🏥 ⚑ 📋 ⚖ ☀) and states the rule
  *"Icons always carry their words"*. Built: no icons. Not a rule breach; a delta.

**WORDS** — title `Your protections` → `What is protecting your supply`.
⚠ The card TITLES are the in-sentence noun phrases — *doctor's certificate*,
*payment plan*, *winter moratorium* — lower-case, because
`portal.protections.kind.*` is written to be inserted into *"A {{kind}} is holding
your supply"* and is reused as a heading. Reads as a bug; not filed separately,
because the fix belongs with `DEF-CWP-4145`'s card work.
**STATES** — `PROTECTED` built. `NOT PROTECTED` built and, since CR-085, carries a way
out. `APPLICATION PENDING` and `EXPIRING` **not built**; `DEF-CWP-4154` records that
the chip has three words for four states.
**EMPTY** — *"Nothing is holding your supply at the moment."* + *"If you are worried
about being cut off, there are still things we can do."* + `See what help there is`.
Correct, and it is R-10 obeyed.

---

### `CWP-045` · Money back · `/money-back`

⚠ **THE DRAWING IS A DECISION SCREEN AND WHAT IS BUILT IS A REPORT.** The drawing's
FOR sentence is *"letting them choose what happens to it"*. The built screen offers
**no control of any kind**.

**MISSING**
* **`What would you like to do?` and its two `RadioCard`s** — *Leave it on the
  account — it comes off your next bills automatically* / *Send it back to bank
  account ····4417 — arrives in 5 to 7 working days*.
* **`Send me $84.20`.**
* **`Total credit  $84.20`** — the credits table has no total row, so the customer
  adds `-$71.40` and `-$12.80` themselves.
* **`YOU ARE IN CREDIT` with the figure as the headline**, and *"Enough to cover about
  half of a typical bill."*
* **`Either choice keeps the money yours...`**

**RIGHT.** Where the credit came from is itemised. The refund's four dated steps. The
separating sentence *A credit comes off your next bill. A refund is money sent back.*
`DEF-CWP-4131` (raw machine timestamp) and `DEF-CWP-4132` (a cancelled refund headlined
*A refund on its way*) are both **FIXED** — every date now goes through
`usePortalDate` and a voided refund reads *A refund we cancelled*. Both rows are still
`open` in the register and should be closed.

**STILL OPEN** — `DEF-CWP-4146`: one column where the plan and the drawing say two;
the render is `flex flex-col gap-4`.
**NOTED, NOT FILED** — the headline amount `$84.20` is rendered inside a
`SectionTitle`, so the screen's single most important figure is smaller than the panel
title above it; and the credits show **negative** amounts to a customer under a
heading *Credits on the account*, where the drawing shows them positive under
*WHERE THE CREDIT CAME FROM*. Both are judgement calls for step 2 rather than faults.
**AT 390** the `USED ON` column is 43px outside its scroller — `DEF-CWP-4917`.
**STATES** — `NO CREDIT` built, with what would create one. `REFUND IN PROGRESS`
built. `BLOCKED` and `CLOSING ACCOUNT` **not built**.

---

### `CWP-050` · `/fees` — and it is **not** the drawing's screen

⚠ **THE ADDRESS THE BLUEPRINT GIVES SCREEN 08 IS ALREADY OCCUPIED.**
`/:tenant/portal/fees` serves `CWP-050`, titled **"What starting service will cost"** —
the fee QUOTE attached to a service application (`SR-26-0061`, *New connection*,
*Meter installation*, *Security deposit*, *To pay now*, *On your first bill*). The
drawing's *Prices and fees* is a **published price list** and shares nothing with it
but the word *fees*. Building screen 08 at this address would displace a live screen;
that is a routing decision for step 2, not a layout one.

**WHAT IS THERE, AND IT IS THE RIGHT ANSWER.** Since CR-085 a **signed-out visitor**
at `/fees` gets `PublicPricesView`, which is the drawing's own `NOT PUBLISHED` state,
done exactly as drawn — *"the phone number, not an empty page"*:
> *Our prices are not shown here yet — ring us and we will go through them.*
> **(281) 555-0164**
plus a real door to `/start-service`, which is the one place a stranger gets a priced
answer today. The file's docstring states why the list is absent and it is worth
quoting, because it is a **stated absence with its reason**, not an oversight: every
figure the drawing shows is already in the database, and what is missing is *"the
RULING about which of it is public"* — `rating.TariffVersion.publish_public` exists,
has never been wired to anything, and is `false` on all twelve rows of this tenant.

**⚠ AND THE DOOR CLOSES THE MOMENT YOU SIGN IN.** The visitor branch is chosen on a
401 from `GET /portal/session`. A signed-in customer at the same address gets the
application-fee screen and can reach neither the price list nor its stated absence.
Recorded as a finding for step 2; not filed, because which screen owns the address is
the thing that has to be ruled first.

**THE LIVE REFUSAL HERE IS `CPB-01`'s** — `Pay $195.00` greyed, reason
*"We cannot take fees online yet"*, registered in `holds.ts` with an honest note that
no symbol can be watched because the fee write point has no settled name.
**EMPTY** — *"There is nothing to pay. We quote the fees once your application is
approved."* Correct.
**NOTED** — the three rail headings are shouted in the catalogue itself
(`portal.fees.beforeYouPayHeading = "BEFORE YOU PAY"`), so the capitals travel into all
eleven languages instead of being a CSS decision.

---

## 2 · The eighty-two open `DEF-CWP` rows — this lane's slice, re-verified

The audits in this folder are dated 2026-09-05 and say *"before citing a row here as
current, open the screen."* Twenty-two of the 82 name a screen on this patch; four of
those belong to other lanes (`CWP-032`, `CWP-038`, `CWP-046`) and one is documentation
(`DEF-CWP-4362`). The seventeen that are ours:

| Row | Verdict today | Evidence |
|---|---|---|
| `DEF-CWP-4000` | **partially fixed — one screen left.** Nine of the ten compose `PageHeader` on every branch; `CWP-042` has none | browser: `CWP-042`'s only heading is an `h3` → `DEF-CWP-4912` |
| `DEF-CWP-4131` | **FIXED** — every date through `usePortalDate` | browser: `08/05/2026`, `Cancelled on 08/…` |
| `DEF-CWP-4132` | **FIXED** — `portal.moneyBack.refundCancelledHeading` | source + catalogue |
| `DEF-CWP-4140` | **FIXED** — the note renders only when a row carries the rounding | `AskForPlan.tsx` `instalments.some(...)` |
| `DEF-CWP-4141` | **STILL OPEN** — one `catch` swallows the server's `message_key` and params | source; `portal.plan.termOutOfRange` rendered by nothing |
| `DEF-CWP-4143` | **FIXED** — `Pay $247.30` filled, with the plan and help beside it | browser, 1280 and 390 |
| `DEF-CWP-4144` | **FIXED** — one heading (`Past due`); the rail link now reads *Your protections* | browser |
| `DEF-CWP-4145` | **STILL OPEN** — `ProtectionCard.action` still passed by nothing | source + browser: no control on any card |
| `DEF-CWP-4146` | **STILL OPEN** — `flex flex-col gap-4`, one column at 1280 | browser |
| `DEF-CWP-4147` | **NOT RE-VERIFIED** — a backend seam; needs a seeded account with open bills, which the shared stack does not have | — |
| `DEF-CWP-4154` | **STILL OPEN** — three chip words for four states | source |
| `DEF-CWP-4180` | **STILL OPEN** — no CSV control, no *IF YOU LEFT TODAY* panel | browser |
| `DEF-CWP-4181` | **STILL OPEN** — no pay control; the file's own comment says so deliberately | source + browser |
| `DEF-CWP-4182` | **STILL OPEN** on all three clauses (columns, free-text term, unreachable step 3) | browser |
| `DEF-CWP-4183` | **HALF FIXED** — `CWP-044` fixed, `CWP-042` moot (no head at all); **`CWP-043` and `CWP-063` still print their title twice** | browser |
| `DEF-CWP-4678` | **NOT REPRODUCIBLE at these figures** — the bars shrink and no label overflows at 390 on either chart; document overflow is none. ⚠ Not proof it is fixed: the longest label this lane drew was `$228.75`. A four-figure label (`$1,199.80`) is untested | browser, 390 |
| `DEF-CWP-4720` | **STILL OPEN** — `hover:bg-neutral-50` at `PlanOffer.tsx:148`; `tokens.css` declares `--color-neutral-100` as its lightest neutral and **no** `neutral-50` | source. Swept all ten screens for the same shape: this is the only instance |

---

## 3 · The twenty-four specifications — which touch these ten screens

| Spec | Screens it names | On this patch | Built? |
|---|---|---|---|
| **`CPB-01`** *A customer can pay by card* | 35·36·37·6·**8** | **`/fees`** | **NOT BUILT.** Live refusal *"We cannot take fees online yet"* under a greyed `Pay $195.00`. No payment provider is wired |
| **`CPB-03`** *A customer can download what we sent them* | 60·**43** | **`/plan-offer`** | **BUILT, and beyond its stated scope.** `CWP-063` serves the agreement as a real `<a>` when one was kept, and falls back to a held control with the STORE's reason when none was. ⚠ **`/plan` (screen 44) also serves it now**, which `CPB-03`'s screen list does not cover — and `YourPlan.tsx` cites **`CPB-14`** for it, which is a different spec (*a proof-of-service letter*, screen 60). Miscitation, recorded |
| **`CPB-18`** *Level pay can work out a monthly amount for every account* | **47 · 48** | **`/level-pay`, `/level-pay/standing`** | **NOT BUILT.** Its quoted refusal is live. ⚠ **And it is not the refusal that blocks the screen** — see `CWP-044` above. `CPB-18` should be amended to name the enrolment hold as well, or a second spec raised |
| **`CPB-21`** *A plan says who set it up* | **43 · 44** | **`/plan-offer`, `/plan`** | **PART BUILT.** Released on `CWP-063` (`offered_by` → *"Dana Whitfield set this up on …"*, closing `OQ-CWP-1567` option (a)). **NOT on `CWP-043`:** `PortalPlan` carries no such field. The spec is half done and reads as done |
| **`CPB-23`** *Every screen carries its How-you-get-here row* | all | all ten | **NOT BUILT** (documentation). Of this lane's ten, **screen 08 `/fees` is one of the 37 with no `How you get here` row at all**, and the blueprint says so on its own card |
| **`CPB-17`** *A signed-out visitor at a signed-in address is offered a sign-in* | 53·54, *"True of every signed-in screen"* | **nine of ten** | **NOT BUILT, and confirmed live on the shared stack.** `/{tenant}/portal/overdue` signed out renders **Failed · We could not open this page. · You're signed out. Sign in again to continue. · Retry · Download error report · Cancel** — a grey panel outside the utility's frame, with no nav and no sign-in link. ⚠ **`/fees` is the ONE screen of the ten that handles it**, and it does so properly, which makes it the worked example for the other nine |
| `CPB-02` `CPB-04`–`CPB-16` `CPB-19` `CPB-20` `CPB-22` `CPB-24` | — | — | none of them names a screen on this patch |

---

## 4 · The twelve unratified drawn rules — which these findings lean on

The blueprint's appendix A marks **12 of its 24 rules `NO HOME — stated only here`**.
They are **PROPOSALS, NOT LAW**, and where a finding depends on one it is said out
loud, because **the PO has to rule it in before step 2 can act on it.**

⚠ **TWO ARE SQUARELY THIS LANE'S AND BOTH ARE UNRATIFIED.**

**`R-10` — *"Bad news never appears without the way out beside it."*** The appendix
calls it *"the strongest rule on the page"*, and it is the rule this whole group of
screens is built around: screen 41's own question ends *"Anything that reads as a
threat without a route out is a failure of this screen."* **Audited across all eight
branches on this patch that state bad news or an absence:**

| Screen | The sentence | A way out beside it? |
|---|---|---|
| `/overdue` populated | *$247.30 is overdue by 22 days* | **yes** — three, grouped |
| `/overdue` empty | *Nothing is overdue on this account.* | not bad news |
| `/protections` empty | *Nothing is holding your supply…* | **yes** — *there are still things we can do* + door |
| `/plan` empty | *You are not on a payment plan.* | **yes** — `Ask for a payment plan` |
| `/plan-offer` empty | *There is no plan waiting for you…* | **yes** — door + ring us |
| `/level-pay/standing` empty | *You are not on budget billing…* | **yes** — door to `CWP-044` |
| `/money-back` empty | *There is no money coming back to you…* | **yes** — what would create one |
| **`/level-pay` empty** | ***"We could not find an account to work this out for."*** | **NO — no door, no phone number, nothing** |
| **all eight `failed` branches** | *"We could not read this right now. Try again in a moment."* | **NO — a sentence in a card with no Retry control**, while the shell's own `FailedWithRetry` has one |

**So R-10 is honoured on seven of nine and breached on two**, and both breaches are
refusals rather than absences. ⚠ **Neither is filed as a defect, and that is
deliberate: R-10 is not law.** If the PO ratifies it, both become defects the same
hour; if they do not, both are acceptable as they stand. **This is the loud flag the
brief asked for.**

**`R-18` — *"Assistance is a first-class path, not a page behind a sign-in."***
Everything in §1's `CWP-056` block depends on it. Measured against the product as it
is: `/help-paying` is signed-in only (a visitor gets the grey Failed panel), it offers
no grant, no discount and no credit, and **nothing in the product stores an assistance
programme at all**. If R-18 is ratified, `CWP-056` is not a screen with gaps — it is a
feature that does not exist, and the gap is a change request, not a defect. If it is
not ratified, the three self-service routes are a legitimate reading of *help paying*
and the drawing's five programme cards are an aspiration. **Step 2 cannot tell which
without a ruling.**

**The other ten, and where they touch this patch:** `R-04` (no emoji as a section
marker — obeyed; the drawing itself uses six on screen 46) · `R-05` (amount due and
due date in the same place on every screen — the account bar carries them, LANE 1's)
· **`R-06`** (*never ask a customer to compute* — breached twice, `Left to pay` on
`CWP-043` and `Total credit` on `CWP-045`, both named by the drawing) · **`R-07`**
(one filled button per screen — held on all ten; on `CWP-056` the filled one is
arguably on the wrong card) · `R-09` (never make a customer remember an account number
— held) · `R-15` (a back-link sits under the bar — LANE 1's) · **`R-22`**
(*loading, empty and failed can never render as the same picture* — **held, and worth
recording**: each of the ten has three distinct sentences, e.g. *Reading your
account… / Nothing is overdue on this account. / We could not read this right now.*)
· `R-19` and `R-23` (not exercised here) · `R-13` (*a route existing is not a door* —
the rule behind §0(b), and the finding that produced the whole appendix).

---

## 5 · B14 rule 39 — measured with `getComputedStyle`, at both widths

`/ask-for-a-plan` is the only form on this patch. Measured on the shipped bundle with
`getComputedStyle` and `getBoundingClientRect`, at **1280 and 390**, both identical:

| Rule 39 says | Measured | Delta |
|---|---|---|
| label → input **5px** | **4px** | −1 |
| input → helper **6px** | **17px** | **+11, nearly 3×** |
| field → field **20px** | **16px** | −4 |
| ratio ≈ **1 : 1 : 4** | ≈ **1 : 4.25 : 4** | the helper sits as far from its own input as the next field's label does from the helper |
| `.input` **6×10, min-h 36** | padding **8px / 12px**, `min-height: auto` | no min-height at all |
| page **24 / 16 / 32** | `main` padding **24 / 20 / 24 / 20** | side 20, bottom 24 |
| `--sp-1` … `--sp-7` | **every one resolves EMPTY** on `documentElement` | the scale is unbuilt — which B14's own status column already states, now measured |

⚠ **THE FAILURE THE PO NAMED IS THE ONE THAT SHIPS.** The ruling says *"the helper
must READ as attached to the input above it, never to the label below it."* At 17px
below its input and 16px above the next field, the helper is effectively equidistant
and reads as floating. Filed as **`DEF-CWP-4916`**, with the note that the fix belongs
in the shared field component rather than on this screen.

**Also seen and not covered by rule 39:** no input on the form carries
`aria-describedby`, and no helper carries an `id`, so none of the three helpers is
announced with its field. And the only button on the screen is **disabled on arrival**
with its reason (*"Fill in the dates first"*) living solely in a `title` attribute —
which a phone has no way to show.

**Noted, not filed (LANE 1's):** the shared portal screen-id chip uses `px-[9px]
py-[3px]` — arbitrary values, and `9` and `3` are two of the four numbers rule 39 bans
by name. It is on every portal screen, so it is the frame's, not this patch's.

---

## 6 · Both widths, every screen

**No screen on this patch scrolls the document sideways at 390** — checked as
`documentElement.scrollWidth > clientWidth` on all ten. The narrow layout stacks: the
two-column screens become one column and the KPI strip stacks.

**The one 390 fault is inside the tables**, and it is `DEF-CWP-4917`: three of the five
`MiniTable`s are wider than their `overflow-x-auto` container — `CWP-043` by 51px
(`STATUS`), `CWP-066` by 40px (`BALANCE AFTER`, which renders as `BAL A`), `CWP-045` by
43px (`USED ON`) — with no shadow, fade, resting scrollbar or caption to say the table
continues. The blueprint's phone frames for screens 44 and 48 are stacks, not narrowed
tables.

---

## 7 · What step 2 needs ruled before it can act

1. **`R-10` and `R-18`** — §4. Two unratified proposals that between them decide
   whether `CWP-056` is a screen with gaps or a feature that does not exist, and
   whether two refusal branches are defects.
2. **`OQ-CWP-1568`** — open. Holds four controls on two screens: *join budget billing*
   and *accept / different terms / decline*. Until it is answered, a customer can
   neither join budget billing nor answer a plan offer from this portal.
3. **`OQ-CWP-1566`** — open. `expires_on` is `null` on every account, so the offer
   deadline the drawing shows can never render.
4. **Who owns `/:tenant/portal/fees`** — the live `CWP-050` or the blueprint's screen
   08. They are different screens with the same address.
5. **`CPB-18`'s wording** — it names the figure refusal and not the enrolment hold,
   which is the one that actually blocks the screen.
6. **`CPB-21`** — released on screen 43, absent on screen 44; the spec reads as done.

---

## 8 · One process note, recorded because law 11 asks for it

This lane's ten defect ids were allocated as **`DEF-CWP-4845`–`4854`** and landed as
**`DEF-CWP-4911`–`4920`**, after **four** renumberings. `file_defect.py` was right about
every ref this checkout could read at allocation time; while this lane was writing,
sibling `CR-085` lanes pushed rows taking `4845`–`4865`, then `4866`–`4878`, then up to
`4910`, and `allocate.py defect --verify` refused each candidate block in turn as
*"TAKEN — a sibling pushed it"*, some of them on branches this checkout does not list.
`DEF-1787`'s shape, four times in one afternoon on one register.

**What caught it every time was the unconditional re-derivation at push time, and
then `push_paths.sh` refusing on a moved path** — never a conflict. The register
merged cleanly on every attempt and would have published ten duplicate numbers each
time. Each round rebuilt the register as **the pinned tip's bytes plus these ten
rows**, proved the prefix byte-identical, and re-verified every id one at a time.
The final push's subtraction check reads `718 0 · 680 0 · 10 0` — insertions only.

⚠ **AND THE RE-DERIVATION HELPER HAD THE BUG IT WAS WRITTEN TO CURE, TWICE, WHICH IS
WORTH MORE THAN THE COLLISION ITSELF.** Its citation rewrite mapped old ids to new in
one pass — and when the blocks OVERLAP (`4876→4879` while `4879→4882` is still to
come) each later line re-replaces what an earlier one just wrote, so four citations
collapsed onto one id. Fixed with placeholders. Then it cached the rows in a state
file on the first run, so every later run searched the document for ids the document
no longer held and silently rewrote almost nothing — a helper reporting success over
a scope it had excluded, which is hard-won law 7's fifth shape in a script eleven
lines long. Both were caught by **counting the distinct ids in the finished file
against the ten rows in the register**, which is the check to run after any
renumbering: every filed id cited at least once, and no id from a retired block left
anywhere.
