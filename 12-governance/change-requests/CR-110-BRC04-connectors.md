# CR-110-BRC04 · Connectors — the Integration Blueprint, built

| | |
|---|---|
| **Raised** | 2026-09-16, by the Product Owner, in the working chat session |
| **Branch block** | `BRC04` = `CR-110`–`CR-114`, branch `claude/gifted-johnson-top7zn`, claimed in `14-id-reservations.md` before this file was written |
| **Classification** | **CHANGE** — a new design arrived for a module that already ships. Not a defect: the product does today what it was asked to do; the agreement moved. |
| **Source** | `05-prototype/05 Integration Blueprint.pdf`, 163 pages, on the DEFAULT branch `claude/confirm-understanding-3ktufc` |
| **Status** | STEP 0 — measuring. Nothing built. |

---

## 0 · Capture — the requester's words, verbatim

These are the Product Owner's own sentences, in the order they were said. They are
quoted rather than summarised because `13-change-process.md` step 1 says so, and
because every paraphrase of a ruling in this repo has eventually been read as the
ruling itself.

> "now lets work on settings -> integration - i ahve upload this file on default branch - can youa ccess it - dont process it rightnow - 05-prototype/05 Integration Blueprint.pdf"

> "this is new design - can you tell me what changes you will do - we are only working on interation right now- we wil not work on runbooks today - i want details in table - what changes you will do on which scren - frontend backend and db/tables - in this chat - confirm how many integrations and how many screens - document images are benchmark"

> "use connector - instead of integration"

> "we dont have apis for all these 28 connector what you will do about it; also where we send - we dont have apis yet what you will do about it - we have added details about it in document - can you check"

> "i want you to put dummary apis in all these 28 conenctor - in phase 2 we will replace them and build a actual logic around them - phase 1 lets have all in place and phase 2 step by step buidl logic fo each conenctor"

> "so when you put dummary apis for us - use this format"

> "youa re correct - so there will be two token 1 for prod and 1 for sandbox"

> "i want you to use panel with acsent - where ever shown it that way"

> "measure all screens- why 5 crs - why not 1"

> "this is good but i want to see all screen when i clikc on connect"

> "please od it 1 cr"

> "please start this"

> "please ensure when you build use images form document to create product screens and use ui generotr skills - this is very important ot follow"

Two further exchanges are rulings about how the work is described rather than
about what is built, and they are recorded here because a later reader will
otherwise re-open both:

> "are you creating 28 tables -in database?"

**No, and the answer is the architecture.** Five tables serve all 28 connectors.
A connector is a ROW, never a table; a 29th connector next year adds no table, no
column and no migration. That is `BR-INT-037` — *adding an API is data, not code* —
which the PO had already confirmed in this same session. The two-token ruling is
the same shape: production and sandbox are **two rows** in one table, not two
columns, which is `BR-INT-026`.

> "why jobs here? plese give me example and explain"

**"Jobs" was the assistant's word and it is withdrawn.** The product already uses
*job* for a queued background task, so it cannot also mean a thing a connector
does. The code's word is **operation** and it stays in the code and in documents
like this one. **On screen there is no collective word at all** — the drawing gives
each one its own name under a heading of what the connector does, and a clerk reads
two named rows. Twilio is the worked example: the form asks three questions
(Account SID, Auth token, Send from number) and the connector then does exactly two
things — **Send texts** (out, we start it) and **Delivery status** (in, they start
it). The heading word is visible to a clerk and therefore the PO's to change; the
build proceeds on *what it does* unless they say otherwise.

---

## 1 · Why ONE change request and not five

The PO asked directly — *"measure all screens- why 5 crs - why not 1"*, then
*"please od it 1 cr"* — and they are right on the merits, not merely as a
preference to be honoured.

A connector screen is **one screen rendered 28 ways from data**. Splitting the work
by screen would have produced five change requests that all edit the same two
components and the same manifest format, which is five sets of merge conflicts and
five places for the same ruling to be recorded differently. The blueprint makes the
same point on its own page 131 — *"that one page renders all 28 correctly, which is
what a drawing is for."*

So: one CR, and the two database migrations land as **their own named commits**
inside it, so the PO can see exactly what changed in the database and nothing else
is hidden beside it.

---

## 2 · What signed statement is being reversed

| Signed today | After this change | Where |
|---|---|---|
| The visible word is **Integration** | The visible word is **Connector** | every screen, every catalogue, all eleven languages |
| 18 connectors have a manifest | 28 do | `apps/integrations/manifests/` |
| A connector has one set of credentials | **Two — production and sandbox** | `BR-INT-026`, already written, now actually reachable from a screen |
| We have no vendor APIs, so a connector cannot be exercised | **Every connector answers a dummy API in phase 1** | new |

**No ❄️ FROZEN B4/B5 figure is touched.** This change goes nowhere near billing
math, so `HUMAN-GUIDE §6` is not engaged and no finance re-sign is required.

---

## 3 · Scope, stated as a boundary

**IN.** The connector grid · the set-up form · the connection view · mappings ·
machine keys · the access log · 28 manifests · dummy APIs for all of them · the
sandbox credential · the rename to Connector.

**OUT, by the PO's own sentence** — *"we wil not work on runbooks today"*. The
blueprint's pages 102–130 are twenty-three runbook drawings on four tabs, and the
blueprint itself says they are *"a different product from the sixty above"*. They
are not in this CR and no lane touches them.

---

## 4 · Step 0 — measuring, which is where this CR is now

Nothing is built until every screen has been measured against its drawing AS AN
IMAGE. That is B14 rule 42 and it is the PO's standing instruction in this
session's own words. Five measurement lanes are dispatched:

| Lane | Measures | Writes |
|---|---|---|
| 1 | the connector grid, mappings, machine keys, the access log | `conformance/step0-connector-screens.md` |
| 2 | the shared SHAPE of a set-up form and a connection view | `conformance/step0-configure-and-view.md` |
| 3 | connectors 01–10, field by field and operation by operation | `conformance/step0-vendors-01-10.md` |
| 4 | connectors 11–19 | `conformance/step0-vendors-11-19.md` |
| 5 | connectors 20–28, plus our own API naming | `conformance/step0-vendors-20-28.md` |

Each produces a **"needs a ruling"** list in plain English with a figure and no
IDs. Those lists come back to the PO before anything is built — that is the whole
purpose of step 0, and it is the step whose absence produced `DEF-GOV-5462` (four
lanes sent to the wrong blueprint) three days ago.

---

## 5 · Version

Allocated at the close of each wave with `10-scripts/allocate.py version --bump change`,
recorded on this row, and visible on screen. `13-change-process.md` step 7 exists
because this is the step that gets skipped.

## 6 · Rollback

Stated before shipping, per step 8. The rename is a catalogue change and reverts as
one. The 10 new manifests are additive — removing a manifest file removes its card
and touches no row. **The two migrations are the only part that is not free to
reverse**, and each is therefore its own commit with its own down path.

---

# Step 0 — what the five measurement lanes found, and the PO's rulings on it

All 28 connectors and all five screens have now been measured against their
drawings AS IMAGES (B14 rule 42). **7 of the 28 can be built from their drawing
exactly as it stands; the rest are short 56 field boxes and 41 operations.**

⚠ **Only ONE connector is new from nothing — Badger BEACON.** The other 13 with no
file today come out of SPLITTING four files we already have: the shared finance
connector becomes five named ERPs, the card connector becomes five named
processors, the meter cloud becomes Itron and Sensus, and City GIS is renamed Esri
ArcGIS. That is the difference between "build 14 connectors" and "split four", and
it is why the measurement was worth doing before the sizing.

---

## RULED · The call limit is REAL and it is built, because it is a security control

**PO, 2026-09-16, verbatim:**

> "this is important - we need to inlcude speed limit - otherwise if somone hack we will not have a control"

**This settles the question the lanes raised on all 28 connectors** — every one of
the 78 drawn operations shows a call limit and `registry.Operation` has 23
attributes, none of them a limit. It is NOT decoration and it does not come off the
drawing.

⚠ **THE PO'S REASON NAMES THE INBOUND DIRECTION AND THE DRAWING SHOWS BOTH, SO
WRITE DOWN WHICH IS WHICH — THEY ARE DIFFERENT FEATURES PROTECTING DIFFERENT
PEOPLE.**

| Direction | Who it protects | Built today? |
|---|---|---|
| A partner calls OUR eight endpoints | **us** — this is the PO's hacking case | **YES** |
| We call a VENDOR's API | them, and us from being cut off | **NO** |

**Inbound is already real and this is the one fact that must not be overstated.**
`runners/serve.py:436 check_rate_limit` is a **sliding window of timestamps**,
per tenant and per credential, defaulting to **100 calls a minute**, read from the
connection's own config by `rate_limit_for` — so a bigger utility can already be
given a bigger number in data. The 101st request in a minute is refused. A sliding
window rather than a fixed bucket is deliberate: a partner cannot take 200 in two
seconds by straddling a minute boundary.

⚠ **AND ITS OWN DOCSTRING STATES THE GAP THAT MATTERS TO THE PO'S REASON, WHICH IS
WHY THIS ENTRY QUOTES IT RATHER THAN REPORTING "RATE LIMITING: BUILT" (hard-won law
1 — a comment claiming a guarantee is not the guarantee, and here the comment is
honest and the summary would have been the lie):**

> "This counter is PROCESS-LOCAL … With N gunicorn workers the effective limit is
> N × 100/min. That is a real gap … the limit as built protects one utility's
> partner from another's … and it does not protect the process from a distributed
> caller. A shared counter needs a store this product does not have yet."

**So against a genuine attacker the built limit is N × 100 a minute, not 100.**
That is the gap the PO's ruling actually buys, and it is the part with a cost:
a shared counter needs a store the product does not have.

**What the ruling therefore commits us to, smallest first:**

| # | The work | Why it is needed |
|---|---|---|
| 1 | Put the limit **on screen** and let a clerk set it | The number is already read from data and no screen shows or sets it |
| 2 | Show the **count beside the ceiling** | The blueprint (p017) draws *"Calls used this week — 4,180 of 10,000"* and it has never rendered. Its own words: *"A limit with no consumption beside it cannot answer the only question a clerk has, which is whether we are near it."* |
| 3 | **Per operation**, not just per connector | p017: *"the limit cannot live where the operation lives. It is a row per connection AND per operation, with the manifest carrying the default that provisioning copies in."* Today it is one number for the whole connector |
| 4 | A **shared counter** | The only item that closes the PO's stated hole. Without it, N workers multiply the limit by N |
| 5 | An **outward** throttle | p017: *"nothing records a throttle keeping US under a vendor's ceiling, so the outward figure promises more than the inward one"* |

⚠ **EVERY LIMIT DRAWN IS AN ILLUSTRATION (B14 rule 37), AND THE BLUEPRINT SAYS SO
ITSELF ON THE SAME PAGE:** *"No value here was read from anything … A builder
taking `10 / min` off a meter row as the real ceiling would be doing exactly what
that rule exists to stop."* So `120/min` and `300/min` are shapes. **The DEFAULT we
ship is ours to choose and write down; only the mechanism is the PO's ruling.**

---

## RULED · The two unnamed vendors stay unnamed — they are placeholders

**PO, 2026-09-16, verbatim:**

> "keep it as it is right now - we will replace them - theya re dummay right now we will replace them later"

This answers the lanes' question *"which mailing house are we going live with?"* and
it closes it rather than deferring it: **bulk email and the print vendor ship as
placeholder connectors**, consistent with the PO's phase-1 ruling that all 28 get a
dummy API and phase 2 builds the real logic one vendor at a time.

⚠ **IT ALSO DECIDES THE LOGIN QUESTION BELOW BY REMOVING ITS SHORTCUT.** That
question could have been answered by naming the vendor; the vendor is deliberately
not named, so the build must handle BOTH shapes — which is option C.

⚠ **AND IT LEAVES ONE THING TRUE THAT A SCREEN MUST NOT SAY.** The blueprint's p146
files these as a defect in their own right — *"offered as live with no connector — a
card a utility can press that cannot work."* A placeholder is fine; a placeholder
that presents itself as ready to connect is the live-screen-behind-a-dead-control
shape of hard-won law 2. **These two cards say *coming soon* and the server refuses
the connect, and the hold carries a test that fires when the real vendor lands.**

---

## OPEN · The login panel asks for three things and the database stores one

Put to the PO with a worked example on 2026-09-16; **no ruling yet.**

**The example is the mailing house.** Our form asks two things — an API key and the
account reference. The drawing asks four: those two, plus a **Token address** and a
**Scope** in a Token panel with a Generate button and an expiry line.

**Why both cannot be true.** Under the drawing two secrets are alive at once: the
typed key, which is what lets us ask for new tokens, and the fetched token, which
goes on every call and dies in an hour. `IntegrationCredential` allows **one active
credential per connection** and it is not a convention — migration `0001` enforces
it with a PostgreSQL EXCLUDE constraint.

| | What the clerk does | Cost | What it costs later |
|---|---|---|---|
| **A · One key only** | Types one secret; the Token panel comes off 13 screens | nothing | A vendor requiring a fetched token **cannot be connected at all**, discovered at go-live |
| **B · Two rows** | Types a key, presses Generate | a migration + renewal | Loses the one-live-login guarantee; *"which secret is current"* becomes a question again |
| **C · Two secrets, one record** ⭐ | Same as B | **no migration** — `payload_enc` is already a free encrypted string | The row's `expires_at` becomes the token's, which is correct: the token is the thing that lapses |
| **D · Discard the typed key** | Types a key once; we keep only the token | nothing | **Breaks in an hour** — without the key we cannot renew. Included because it LOOKS like it honours the one-login rule and does not work |

**Recommendation: C**, and the placeholder ruling above makes it the only safe
answer, because a connector that needs no token simply draws no Token panel.

---

## RULED · All three "controls nothing reads" are BUILT — none comes off the drawing

**PO, 2026-09-16, verbatim:**

> "we ahve to build it - pelase let me know what you need - i already answer it"

against the row that named all three together:

> "Three controls are drawn on nearly every connector that nothing behind them reads — a speed limit on all 78 operations, a nightly run time on about nine screens, and which calls a partner's key may make. Build them, or take them off the screens?"

**All three are BUILT.** This SUPERSEDES the recommendation recorded above that the
clock box come off the nine screens now and be built in phase 2 — the PO chose
build, and the earlier reasoning (*"a box that does nothing is worse than no box"*)
was their sentence in the first place, applied the other way.

| Control | Today | After |
|---|---|---|
| Call limit | one number per connection, inbound only, process-local | per connection AND per operation, on screen, with the count beside it, a shared counter, and an outward throttle |
| Nightly run time | cadence stored (nightly/hourly/manual); **the hour is not**, and nothing computes a next run | a chosen hour that is actually run at |
| Which calls a key may make | one key opens every operation on the connector | a key names the operations it may call; a key with nothing ticked cannot be issued |

⚠ **THE THIRD IS A SECURITY FIX AND THE BLUEPRINT ALREADY CLASSED IT AS ONE** (p017,
`CR-4`, tagged *SECURITY SHAPE · RULED: SCOPE IT*): *"a partner handed a key to push
meter readings can call every other inbound API on that connector — because there is
no field that says which ones they may call."* It affects the six connectors that
issue keys — the five ERPs and the kiosk network. It needs a column and a check at
the door, which is one of this CR's **two migrations**.

⚠ **AND IT IS THE SAME CONCERN THE PO GAVE FOR THE CALL LIMIT** — *"otherwise if
somone hack we will not have a control"* — so the two are one piece of work with one
reason, and they are built together.

---

## DECIDED BY US, not asked again (law 13) — five judgments with their reasoning

**These reached the PO once, as options with figures. Four are settled by rulings the
PO has already given, and the fifth by a query anyone can run. Re-asking would be a
bug in us.**

**1 · RULED BY THE PO — Aclarian is a REAL ERP COMPANY and is built as one.**

> PO, 2026-09-16, verbatim: "this is erp company aclarian"

⚠ **THIS ARRIVED WHILE THIS VERY SECTION WAS BEING WRITTEN THE OTHER WAY, AND THE
DRAFT IT REPLACED IS WORTH RECORDING BECAUSE THE REASONING WAS PLAUSIBLE AND WRONG.**
This lane was about to rule Aclarian a PLACEHOLDER under the PO's own placeholder
ruling of the same hour, on the grounds that the blueprint calls the word *"a partner
we made up for worked examples"* and asks itself whether *Aclara*, the real meter
vendor, was meant. **Both readings were wrong, and in the same way: the blueprint was
doubting its own fixture name, and we were about to promote that doubt into a
product decision.** The PO knows the company. **Aclarian is connector 17, an ERP, and
it is built like Workday and SAP — a real vendor with a real form, not a card that
says coming soon.**

**The count stays 28, and the lesson is law 13's mirror image.** That law says never
ask the PO twice; it does not say decide anything you can construct an argument for.
Applying a ruling to a case it *plainly* covers is right — bulk email and the print
vendor genuinely have no company behind them. **Aclarian looked like that case and was
not**, and the only thing that could tell them apart was a fact the PO holds. The
question was correctly asked; the error was in the hour spent preparing to answer it
ourselves.

**2 · A repeat of a money operation is REFUSED, never reconciled.** Put to the PO
with the worked figure — *"a clerk presses Refund twice inside a minute on a $142.50
refund"* — and the safe direction is the only one: reconcile means the money has
already left twice and we are matching up afterwards. Three operations on the card
connectors (take a payment, refund, return) declare `mode="refuse"` with
`source="request_key"` — **a key WE mint and store BEFORE the request leaves**, which
is the detail the whole thing turns on: the dangerous case is not a double-click but
a reply that never arrives and a retry that follows, and a key minted after the reply
cannot see it. None of the three exists yet, so this is built right rather than
fixed later.

**3 · Card details go on the CARD COMPANY's page. Embedded is NOT offered.** The
drawing offers both. Embedding the card form in our pages puts the whole product
inside the card industry's annual audit — a cost the product carries for ever, taken
on one screen's authority. Offered as a recommendation to the PO with that
consequence stated; not contradicted. Adding embedded later is a change; carrying
the audit is not reversible.

**4 · No partner holds a live key, so splitting the shared finance connector strands
nobody.** This was listed as a fact only the PO holds and **it is not** — it is a
query. Nothing in the product issues a key outside an authenticated API call: the
only caller of `issue_key` is a service function, no seed or fixture issues one, and
the set-up screen **has no route at all** (typing its address returns the product's
*"not built yet"* page). No utility can have connected a partner. The five ERPs
therefore replace the shared connector with no migration of anyone's key. ⚠ **This
stands on TODAY's checkout and nothing keeps it true** — the moment the set-up
screen lands a partner CAN be connected, so the split must land in the same wave as
the screen or before it, never after.

**5 · A blank permission box does NOT mean "everything".** The drawing puts *"Leave
blank for everything the key allows"* under the Scope box. That is the widest
permission as the default, against hard-won law 3 — **the unsafe option must be the
one you type.** Blank means nothing is granted, and a key with nothing ticked cannot
be issued, which is the same sentence the blueprint uses for the May-call column.

---

## Where that leaves step 0

**Nothing is outstanding with the PO.** Every question the five measurement lanes
raised is now either ruled by the PO or decided above with its reasoning. The build
proceeds.

---

## RULED · ONE KEY PER CONNECTION, and the word *token* leaves the product

**PO, 2026-09-16, verbatim:**

> "i only want to issue a key per conenction - that waht we meant with token generation - if you want to called it key - you can call it key - i dont understand the differnt between key and token"

⚠ **THIS RULING REMOVES WORK RATHER THAN ADDING IT, AND IT RETIRES TWO
RECOMMENDATIONS THIS FILE ALREADY CARRIES.** Both the "two secrets in one record"
option and its correction to "two credential rows with a `role` column" are
**WITHDRAWN**. Neither is needed. The database is correct as it stands and this CR
carries no credential migration.

**The cause was one word read in the wrong direction.** The drawing's *Generate
token* button was read as *we ask the vendor for a short-lived token and renew it*
(an OAuth exchange, outbound). The PO means *we generate a key and hand it to the
partner* (inbound) — **which is the `they_hold_ours` shape the product already has**,
complete with the `issued_secret` field kind that is shown once, copyable, and never
re-displayed.

**The measurement that settled it, and it is one command over all 18 manifests:**

| Shape | `auth.mode` | Count | Manifests |
|---|---|---:|---|
| They gave us a key | `we_hold_theirs` (+ one `token_exchange`, one `none`) | **10** | accounting_file · bank_lockbox_file · email_bulk · email_smtp · gis_city · meters_mdm · meters_neptune360 · payments_card · print_vendor · sms_twilio |
| We give them a key | `they_hold_ours` | **2** | gl_partner · payments_kiosk |
| **Both** | — | **0** | — |

**NOT ONE CONNECTOR HOLDS BOTH KINDS OF SECRET.** The one-active-credential
constraint in migration `0001` is therefore not a limitation the drawing exceeds; it
is the right shape, and the two-panel form was a misreading of it.

**What the ruling changes on screen:**

| | |
|---|---|
| **Removed** | the Token address field — there is no vendor to ask · every expiry, renewal and re-authorise path · the word **token**, from every screen and all eleven catalogues |
| **Kept** | the Scope box, because it is *which of our APIs this key may call* — ruled IN by the PO the same day |
| **Renamed** | one word everywhere: **key**. *Generate a key · Replace key · The key for them to use* |

⚠ **`token_exchange` STAYS AS AN AUTH MODE AND THIS RULING DOES NOT TOUCH IT.**
`meters_neptune360` holds the vendor's key and swaps it for a short-lived token when
calling them, because their API demands it. **That is plumbing inside an adapter and
never reaches a clerk** — the clerk types the vendor's key and the word *token*
appears on no screen. A lane must not "simplify" `token_exchange` away on the
strength of this ruling; the ruling is about what a clerk is asked for, not about
what an adapter does.

⚠ **ONE THING TO WATCH RATHER THAN PRE-SOLVE.** A card processor is genuinely
two-way: we call them to take a payment, and they call us back with the settlement.
If the first one built turns out to need a key in EACH direction, that is the one
case where a connection would want two credentials — and it is to be brought back as
a MEASUREMENT against a real form, never as a speculative migration now. None of the
five card connectors exists yet, so nothing is blocked on it.

⚠ **THE DURABLE LESSON IS THE PO'S OWN SENTENCE — *"i dont understand the differnt
between key and token"* — AND THEY WERE RIGHT NOT TO.** The only real difference is
who minted it and whether it expires. Two words for one idea cost this CR two wrong
recommendations before anyone asked whether both words were needed. **B14 rule 34's
shape: one word for one thing, everywhere.**

---

## RULED · The call limit is a GUARD, not a setting — no clerk may change it

**PO, 2026-09-16, verbatim:**

> "so wecant allow clark to reset it; you can have shared counter - and keep nthe check in code - thats it - it will solve - keep the limit in database so if we want to change it later it is easy to do"

**Four instructions, and the third one — *"thats it"* — is a scope boundary, not an aside.**

| # | Ruled | What it means in build terms |
|---|---|---|
| 1 | **No clerk control** | The limit is **display only** on the API table. No input, no Save, no per-tenant editor. A clerk cannot raise their own ceiling — which is the whole point of a guard |
| 2 | **A shared counter** | The one item that actually closes the PO's stated hole. See below |
| 3 | **The check stays in code** | `runners/serve.py check_rate_limit` keeps its shape — a sliding window, refusing the call. Not a policy engine, not configurable behaviour |
| 4 | **The limit lives in the database** | So it can be changed later without a release. Per connection AND per operation, as the blueprint's p017 requires — *"a larger utility buys a larger quota, so the limit cannot live where the operation lives"* |

⚠ **THIS AGREES WITH THE DRAWING RATHER THAN OVERRIDING IT.** p017's own ruled line
reads *"78 operation rows across 56 screens, **display only**"*. The column was never
drawn as an editor; this CR had been carrying "put the limit on screen and let a
clerk set it" as its own first item of work, and that was **our** invention. It is
struck.

⚠ **THE SHARED COUNTER IS THE ONLY PART THAT CLOSES THE STATED HOLE, AND THE CODE
ALREADY SAYS SO IN ITS OWN WORDS** (quoted rather than summarised, because the
summary is where this goes wrong — hard-won law 1):

> "This counter is PROCESS-LOCAL … With N gunicorn workers the effective limit is
> N × 100/min. That is a real gap … the limit as built protects one utility's
> partner from another's … and it does not protect the process from a distributed
> caller. A shared counter needs a store this product does not have yet."

So the PO's *"if somone hack we will not have a control"* is answered by exactly one
of the five items this CR listed, and the other four were ours.

**STRUCK from this CR's scope by *"thats it"*:**
- the clerk-facing editor (item 1 above — never drawn, our invention);
- **the usage count** — the blueprint draws *"Calls used this week — 4,180 of 10,000"*
  and argues for it (*"a limit with no consumption beside it cannot answer the only
  question a clerk has"*). It is a good argument and it is **not what was ruled**. It
  is recorded here as a candidate for later, unbuilt, rather than smuggled in under a
  ruling that did not mention it;
- the **outward** throttle (a ceiling keeping US under a vendor's). Different
  direction, different reason, not the hacking case. Recorded, not built.

**What ships: a `rate_limit` row per connection and per operation, seeded from the
manifest default at provisioning · one shared counter behind `check_rate_limit` ·
the number shown, never edited.** One of this CR's two migrations.

---

## RULED · SCHEDULING BELONGS TO RUNBOOKS — a connector is a connector

**PO, 2026-09-16, verbatim:**

> "we are going to use runbooks to run the scheduled job; since it is not just the job but logic that will be required; hence you can keep it or remove it as required - conenctor i a conenctor not a logic to to ETL"

**This is a MODULE BOUNDARY, and it is the most consequential ruling of the day
because it decides what a connector IS.** A connector holds the address, the key and
the shape of a vendor's API. It does not decide when to call it, what to do with the
answer, or what happens when the answer is wrong. That is logic, and logic is
Runbooks'.

**The PO delegated the keep-or-remove decision explicitly — *"you can keep it or
remove it as required"* — so this is ours to make and to write down (law 13).**

**DECIDED: the time box COMES OFF the nine connector screens.**

The reasoning, in order:
1. **Nothing reads it and nothing ever will**, because the thing that would read it
   now lives in another module. Measured: `.schedule` has **zero readers**, and in
   the connector code `next_run_at` is only ever *set to nothing*.
2. **The PO's own test decides it** — *"a box that does nothing is worse than no
   box"*. A box whose owner has moved to another module can never stop doing nothing.
3. **Leaving it would build the boundary wrong on the screen a clerk trusts.** A time
   on the connector page says the connector schedules; it does not.

⚠ **THIS SUPERSEDES THIS FILE'S OWN "ALL THREE CONTROLS ARE BUILT" ENTRY FOR THE
CLOCK BOX, AND ONLY FOR THE CLOCK BOX.** Earlier today the PO ruled *"we ahve to
build it - i already answer it"* over a row naming three controls together. **The
call limit and the key scope are unchanged and are still built.** The third has since
been given a different home, which is not a reversal — it is the same instruction
landing in the module that can honour it.

⚠ **AND IT LOSES A CLERK NOTHING, WHICH IS WHY IT IS SAFE TODAY.** There is no way to
choose an hour today; the box has never worked. Removing it takes away a promise, not
a capability.

**NOT touched, deliberately:** the connection's existing `cadence` field
(`nightly` / `hourly` / `manual`), which is shipped and read. It is the same boundary
question one layer down and it belongs to the Runbooks hand-over, which the PO put
out of scope for today — *"we wil not work on runbooks today"*. **Recorded here so
the next lane finds it rather than rediscovering it**: when Runbooks take scheduling,
`cadence` goes with it, and the connector keeps only the address, the key and the
shape.

---

# ⚠ THE BOUNDARY · what a connector IS — three rulings in one afternoon that are one rule

**PO, 2026-09-16, across three separate answers, verbatim:**

> "we are going to use runbooks to run the scheduled job; since it is not just the job but logic that will be required; hence you can keep it or remove it as required - **conenctor i a conenctor not a logic to to ETL**"

> "again we will build a runbok with logic to ensure there no twice - **connector is a conector and it control access and limits**"

> "so wecant allow clark to reset it; you can have shared counter - and keep nthe check in code - thats it"

**Read together they are not three answers, they are ONE RULE, and the PO stated it
in their own words in the second quote.** It is recorded here as a boundary rather
than three times as an exception, because it will settle dozens of questions nobody
has asked yet — and because a rule discovered three times and written down none is
exactly the failure hard-won law 10 exists for.

| A CONNECTOR owns | A RUNBOOK owns |
|---|---|
| the address | **when** to call |
| the key | **what to do** with the answer |
| the shape of the payload | what happens when the answer is wrong |
| **who may call** (the key's scope) | **not doing it twice** |
| **how often they may** (the limit) | anything that needs a decision |

**The test, in one sentence: if answering the question needs JUDGMENT, it is a
Runbook. If it is a fact about the door, it is the connector.**

---

## RULED · A repeat of an OUTBOUND money operation is a Runbook's guard, not the connector's

**PO, 2026-09-16, verbatim:**

> "again we will build a runbok with logic to ensure there no twice - connector is a conector and it control access and limits"

⚠ **THIS SUPERSEDES THIS FILE'S OWN DECISION 2 ABOVE**, which read *"A repeat of a
money operation is REFUSED, never reconciled … three operations on the card
connectors declare `mode="refuse"` with `source="request_key"`"*. That decision was
taken by US, correctly flagged as ours, and put to the PO with the worked figure
(*"a clerk presses Refund twice inside a minute on a $142.50 refund"*). **The PO has
now placed it in another module. The answer — never refund twice — is unchanged;
only its home has moved.**

⚠ **AND THE RULING IS DIRECTIONAL, WHICH MATTERS MORE THAN THE RULING ITSELF,
BECAUSE GETTING IT WRONG WOULD DELETE A GUARD THAT ALREADY WORKS.** The PO's example
is a clerk pressing Refund — **us sending**. There is a second, opposite case and it
is NOT what was ruled:

| Case | Example | Whose | Why |
|---|---|---|---|
| **We send twice** | a clerk presses Refund twice on $142.50; or a reply never arrives and something retries | **RUNBOOK** | Deciding whether to act again is judgment |
| **They send twice** | the kiosk network posts the same payment event twice | **CONNECTOR** | It is a fact about the door: *have I already been handed this exact event?* |

**So the inbound half STAYS on the connector and is NOT removed.** It is already
built and already declared — `Idempotency(source="provider_event_id")` with
`key_field` naming where the vendor's event id sits in the body, read by
`inbound.py`, which fails CLOSED when a door needs a key and none is declared. That
is access control in the PO's own sense, and stripping it under this ruling would
open a hole while appearing to obey.

**What this changes in the build:**
- The five card connectors declare **no `request_key` idempotency on their outward
  money operations.** They carry the address, the key and the shape, and nothing else.
- **The consequence is stated rather than discovered:** until the Runbook that guards
  it exists, **a real refund cannot ship.** That is consistent with the PO's own
  phasing — phase 1 is dummy APIs in all 28, phase 2 builds the logic one connector
  at a time — and the refund's logic is phase 2 by definition. **No lane may wire a
  live outbound money call in phase 1 on the grounds that the guard is "somebody
  else's".**
- Every inbound idempotency declaration on every existing manifest is **untouched**.

⚠ **ONE THING TO HAND TO THE RUNBOOKS LANE WHEN IT STARTS, BECAUSE IT IS THE WHOLE
DIFFICULTY AND IT IS EASY TO BUILD WRONG:** the dangerous case is not a clerk
double-clicking — a disabled button handles that. It is **a reply that never
arrives** and a retry that follows. A guard that remembers only calls which
*finished* cannot see it, so the mark must be written **before the request leaves**,
not after it returns. That sentence is the reason this was going to be
`source="request_key"` and it is still true wherever the guard lives.

---

## RULED · Card details go on the CARD COMPANY's page. The choice is not offered.

**PO, 2026-09-16, verbatim:**

> "A · their page only — toggle comes off 4 forms, costs nothing"

**This CONFIRMS the decision this file already recorded as ours** (decision 3 above),
and it is worth having the PO's own word on it rather than our inference, because the
cost of the other answer is permanent and invisible at build time: embedding a card
form puts every server, log and backup inside the card industry's annual audit, for
ever, taken on the authority of one toggle on one wireframe.

**Build effect:** the *Card page* field comes off all five card manifests (the
drawing shows four; `pay_invoicecloud` carries it too). A customer clicks Pay, spends
about fifteen seconds on the processor's own page, and returns. **Embedded is not a
setting a tenant can reach, so no tenant can put us in scope by accident.**

If a customer later demands embedded it is a change request with the audit priced
into it — which is the honest way to take that decision.

---

## RULED · MAPPING LEAVES THE CONNECTOR ENTIRELY — it is business logic

**PO, 2026-09-16, verbatim:**

> "we dont need mapping at connector level it will be in runbook with business logic"

⚠ **THIS IS THE BOUNDARY ABOVE APPLIED A FOURTH TIME, AND IT IS THE LARGEST
APPLICATION OF IT.** Deciding that `ACHCHECK` means *Bank transfer* at this utility
is a judgment about their books. By the test recorded above — *if answering the
question needs JUDGMENT it is a Runbook; if it is a fact about the door it is the
connector* — mapping was never the connector's, and the blueprint drawing it inside
the connector pack is what made it look like it was.

**STRUCK FROM THIS CR, and this is a REMOVAL of measured work, not a deferral:**

| Struck | Was measured at |
|---|---|
| `MAP-01` + `MAP-02`, the mappings screen | 14 drawn elements — 6 built, 5 built differently, 3 not built |
| The pre-fill-and-confirm proposal | this file's own recommendation, now moot |
| Gating go-live on a completed mapping | ditto |

⚠ **THE MAPPINGS SCREEN'S FALSE PREMISE IS THEREFORE NOT OURS TO FIX, AND SAYING SO
IS THE POINT OF THIS PARAGRAPH.** A measurement lane found that `MAP-01`'s own red
note promises the answers *"ship with the connector … seeded identically into every
tenant"*, that **nothing seeds them**, and that a provisioned tenant reads *"14 of 14
not mapped"*. That finding stands and is REAL. It now belongs to whoever builds the
Runbook. **It must not be silently dropped along with the screen** — a finding that
loses its owner is a finding nobody counts, which is the exact failure hard rule 4's
citation history records.

**NOT touched, deliberately, and for a stated reason:**

- **`IntegrationTargetReference` and `mappings.py` stay exactly as they are.** They
  are shipped and read; three manifests declare vocabularies today
  (`accounting_file`, `bank_lockbox_file`, `payments_kiosk`), and `S143` shipped in
  wave D. **Ripping out live machinery on the day its owner changes is how a working
  product breaks**, and Runbooks are out of scope today by the PO's own sentence —
  *"we wil not work on runbooks today"*.
- **The September ruling stands**: an unmapped code records as `other`, keeps the raw
  code and shows red, and nothing is refused on the way in. That is the behaviour a
  clerk sees until the Runbook exists.
- **`mapping_editor` stays in the field-kind vocabulary** and the set-up screen still
  renders one where a manifest declares it. Removing the kind would break three
  shipped connectors to make a boundary point.

**Recorded for the Runbooks hand-over, alongside `cadence`:** mapping moves module
with its table, its screen and the seeding question. The connector keeps the
**vocabulary** — *these are the fourteen words this vendor sends* is a fact about the
vendor, which is the connector's — and the Runbook takes **what each word means
here**, which is judgment.

---

# Where the answers stand — every question step 0 raised

| # | Question | Answer | By |
|---|---|---|---|
| 1 | Two logins on one connector | **One key per connection.** No token vocabulary anywhere | PO |
| 2 | The call limit | **Built. Display only, in the database, shared counter, check in code** | PO |
| 3 | The clock box | **Off the screens — scheduling is Runbooks'** | PO's boundary, our call |
| 4 | Refund pressed twice | **Runbooks'.** Inbound duplicate stays at the door | PO |
| 5 | Is Aclarian real | **A real ERP company.** Built like Workday and SAP | PO |
| 6 | Splitting the key-issuing connector | **Nobody holds a key** — 0 connections, 0 credentials, no route to the set-up screen | Verified, not asked |
| 7 | Bulk email and print vendor | **Stay as placeholders**, saying *coming soon*, with a test that fires when the vendor lands | PO |
| 8 | Mapping answers | **Not the connector's at all** | PO |
| + | Card page | **Their page only** | PO |

**NOTHING IS OUTSTANDING WITH THE PO.** Step 0 is closed.

---

# WAVE C · BUILT — the twenty-eight are declared, at `2.279.0`

**Landed 2026-09-16.** 28 manifests register through `AppConfig.ready()`'s
validation; 86 operations; **no migration, no table and no column**, which is the
whole of `BR-INT-037` and the PO's own answer to *"are you creating 28 tables -in
database?"*

## What was added, and what it came out of

| | |
|---|---|
| Files added | **10** |
| Keys retired | **4** — `payments_card` · `gl_partner` · `meters_mdm` · `gis_city` |
| New from nothing | **1** — `meters_badger` (Badger BEACON) |
| Out of a split | **13** |
| Display names moved | **3** — *Text messages* → **Twilio** · *Water meter cloud* → **Neptune 360** · *City GIS* → **Esri ArcGIS** |
| Version | **`2.279.0`** (`allocate.py version --bump change`) |

## Nobody was stranded, and it was re-measured rather than quoted

This file already recorded that no partner holds a live key — and it recorded, in
the same breath, that the claim *"stands on TODAY's checkout and nothing keeps it
true"*. It was therefore re-run before the split, against the development
database, **tenant by tenant under RLS**:

* **12 connection rows across 4 tenants**, and not one of them is any of the four
  retired keys. They are `bank_lockbox_file`, `email_smtp` and
  `meters_neptune360` — three per tenant.
* **0 rows in `integration_credential`.**

⚠ **THE FIRST READ SAID `(0 rows)` AND WAS WRONG, WHICH IS WORTH RECORDING
BECAUSE IT IS THE EXACT SHAPE OF A CHECK THAT PASSES WRONGLY.**
`SELECT provider_key, count(*) FROM integration_connection GROUP BY provider_key`
returned nothing at all over twelve real rows: **row-level security hides rows
from an aggregate exactly as it hides them from a `SELECT`**, and the role we
connect with is neither superuser nor `BYPASSRLS`. A lane that had taken that
zero as evidence would have reported *nothing to migrate* correctly by accident,
and would have reported it the same way on a live database with a hundred
connections. **`pg_stat_user_tables.n_live_tup` is what exposed it** — it reads
the physical table and said 12 — and the number was then resolved by setting
`app.tenant_id` for each tenant in turn.

## The three refusals that make the set self-checking

Each was shown RED by name before being trusted green, **and each is proved in
`pytest`, the harness that will actually run it** — not through `python3
<module>`, which is `DEF-GOV-3733`'s mistake.

| Refusal | What it closes |
|---|---|
| An operation naming a `host_field` the manifest does not declare | `DEF-INT-5488` — fifteen of eighteen manifests did exactly that, so no connection ever held a host and the endpoint drawn on all 78 API rows could be filled for three connectors |
| An operation with no `rate_limit_per_minute` | The limit is a guard nobody may edit from a screen, so the manifest is the only place it can be got right |
| A seeded `default` on a secret field | A credential in the repository. Hard-won law 3: the unsafe option is the one you type, and here it must not be typeable |

⚠ **THE HOST REFUSAL SKIPS PARTNER-CALLED OPERATIONS, AND THE SKIP CARRIES A
NUMBER.** When `initiative == "them"` the address is the one WE publish, the same
for every tenant, and no clerk configures it; asking those manifests for a host
field would put a box on a form inviting a utility to type our own address.
`Registry.host_coverage()` returns `{"connectors": 28, "checked": 64,
"skipped": 22}` so the blind spot is never a bare zero — `G32`'s lesson, which
reported **0 unresolved** truthfully over 21 live refusals it could not see.

## The PO's rulings, and where each one is asserted

| Ruling | Built as | Asserted in |
|---|---|---|
| One key per connection; *token* leaves the product | No `Token address`, no `Scope` on a token panel, no expiry, no renewal | `test_cr110__no_connector_asks_a_clerk_for_a_token` |
| The call limit is a guard, not a setting | A default per operation, ours and deliberate, that provisioning copies in | `test_cr110__every_operation_names_its_ceiling` |
| Scheduling belongs to Runbooks | **No time-of-day field on any of the 28** | `test_cr110__no_connector_asks_a_clerk_for_a_time_of_day` |
| Never-twice on an OUTBOUND money call is a Runbook's | The five processors declare no duplicate guard — **and are all `coming_soon`** | `test_cr110__outbound_money_declares_no_duplicate_guard` |
| …and the INBOUND half stays | Five inbound guards named and pinned | `test_cr110__inbound_duplicate_guards_are_untouched` |
| The card page is the processor's | **No `Card page` field exists**, so embedded is unreachable | `test_cr110__no_card_connector_offers_an_embedded_card_page` |
| Mapping belongs to Runbooks | No new vocabulary, no new mapping editor; the three shipped ones untouched | `test_cr110__no_new_connector_declares_a_mapping` |
| A blank Scope grants nothing | `scopes` required on all five ERPs, no default | `test_cr110__a_blank_scope_grants_nothing` |
| The two unnamed vendors stay placeholders | `coming_soon`, **with the test that fires when the hold expires** | `test_cr110__an_unnamed_vendor_says_coming_soon` |
| Aclarian is a real ERP company | Built like Workday and SAP, `live`, a real form | its manifest's own docstring |

⚠ **THE OUTWARD MONEY ABSENCE IS ASSERTED AS AN ABSENCE, ON PURPOSE.** This
repository's own lesson is that **nothing here can see an absence** — a retired
address kind took a line off an account header and every check stayed green
(`DEF-CUS-3653`). So `deliver_charge` and `deliver_refund` having no duplicate
guard is a test, not a silence, and the consequence is stated rather than
discovered: **until the Runbook exists, a real refund cannot ship.** All five
processors are `coming_soon` and the server refuses their connect, so that
sentence is enforced rather than promised.

## The ceilings we chose, and why — because nobody can correct them

Every figure the blueprint draws is an illustration (B14 rule 37, and p017 says
so of itself). **None was copied.** The reasoning is in each manifest beside the
number; the shape of it is:

| Kind of call | A minute | Why |
|---|---|---|
| A bill through a hosted mailbox | **30** | A mailbox throttles a sender at about that, so we pace ourselves rather than discover their ceiling by being cut off |
| A bill through the utility's own SMTP | **120** | Their server, paced but under their control |
| A bill through a bulk service | **600** | 40,000 bills — the top of the ICP — in about an hour |
| A text message | **60** | A long code sends about one a second and queues beyond it |
| A meter collection | **60** | One a second is polite to any head-end and never leaves a paged walk waiting on our own throttle; the drawn `10 / min` would cost ten minutes of waiting on a 105-window walk |
| A charge or a refund | **60** | A 40,000-account utility never charges sixty cards in a second; this refuses a runaway retry inside one minute |
| A nightly report we collect | **10** | It runs once. Faster is a retry storm |
| Something a person waits on | **600** | Address search, a card page, map tiles — ten a second is a busy counter and still refuses a script |
| A partner posting to us | **60** | 3,600 an hour, far above real load, and a stolen key gets sixty tries a minute |
| A bill run's delivery receipts | **600** | 40,000 receipts land in a burst; sixty a minute would refuse them for eleven hours |
| A finance system reading from us | **60** | A month-end walk of 40,000 customers pages in 80 calls — under 80 seconds |
| Staff sign-in | **30** | 10–20 staff, so the number that matters is what a brute-forcer gets |

## What the split cost elsewhere, stated so it is not a surprise

Retiring four keys is not only four files. `partner_api.py` named `gl_partner` in
a constant; it now **derives** the partner connectors from the registry by their
auth mode, so a sixth ERP is one manifest and no line of code. `serve.py`'s
credential lookup takes a set of keys rather than one and still makes **ONE
query**, because asking five times in turn would make an unknown key cost a
different amount of time depending on which partner it nearly was — the
enumeration oracle that function exists to close. Five Runbooks definitions that
list provider keys were widened. The GIS adapter's declared key moved with its
manifest, which the adapter registry's own check would have refused otherwise.

## What is open, and what was deliberately not done

* **`OQ-INT-12392` — Twilio call their own password an *Auth token*.** The word is
  off every other screen; theirs is the label printed on Twilio's console and the
  one the drawing shows. A clerk sent looking for an *Auth key* would find nothing
  there. It is a clerk-facing word, so it is the PO's, and it is asked rather than
  settled. The box is left as drawn and the test **pins it by name** so a second
  one cannot appear quietly.
* **`DEF-INT-5495` — thirty-eight shipped operation names do not follow the naming
  format.** The fourteen NEW connectors all do. Renaming the shipped ones is a
  different change with a real blast radius: `integration_run.operation` holds
  those names as data already written, and `charge` alone appears at 33 call
  sites. Filed with the order that works — decide the data question, rename, then
  add the refusal.
* **The usage count beside the ceiling** (*"Calls used this week — 4,180 of
  10,000"*) is not built. It was struck from scope by the PO's *"thats it"* and
  stays struck.
* **`meters_itron` · `meters_sensus` · `meters_badger` are `coming_soon`, and not
  because they are unfinished.** `BR-INT-012` binds them: AMI ingestion for any
  tenant needs the B6 capacity math re-run and an Eng-Lead partition sign-off
  first. That rule bound `meters_mdm` and it binds each connector it became.
* **The five ERPs are `live`, unlike the drawing's `PROPOSED` badge.** The
  capability is shipped — `partner_api.py` serves those three reads today — and
  only the vendor's name is new. Marking them coming-soon would take a working
  partner surface off the product to record that a name changed.

## Rollback

The ten new manifest files are additive: deleting a file removes its card and
touches no row. The four retirements restore by `git revert` of one commit, and
because **no connection or credential row names any of them**, nothing has to be
migrated in either direction. `Field.default` and `Operation.rate_limit_per_minute`
are dataclass attributes with no database behind them. **There is no migration in
this wave, so there is nothing that is not free to reverse.**

---

# WAVE A — BUILT · the connector set-up screen · **`v2.280.0`**

**The screen the whole change request turns on now exists.** Before this wave,
typing `/:tenant/settings/connectors/<key>/configure` returned the product's
*"This screen is not built yet"* page; no URLconf declared the address.

| | |
|---|---|
| Route | `/:tenant/settings/connectors/:providerKey/configure` |
| Screen | **S147 · INT-07**, allocated here and recorded in A1's own addendum |
| Component | `07-frontend/src/features/integrations/ConnectorSetupPage.tsx` — **one**, for all 28 |
| Version | `2.280.0` |
| Built from | the blueprint frames AS IMAGES (B14 rule 42) — `CFG-02` p024 · `CFG-06` p034–035 · `CFG-10` p045–046 · `CFG-23` p079–080 · `CFG-28` p091 |

**`BR-INT-037` is asserted, not claimed.** The route test opens the set-up
address for a vendor **nobody has written** and requires the screen to render.
A front end that routes only keys it knows about is a front end that must be
edited for connector 29, and four passing vendors would be equally true of four
hand-written pages.

## The drawn elements deliberately NOT built, each on a PO ruling of 2026-09-16

**An absence is invisible to every check this repo has**, so each is written
down here, in the screen's own docstring, and as a named assertion in the
walkthrough — not left for a later lane to file as a defect.

| Drawn | Not built because | PO's words |
|---|---|---|
| The whole **Token** panel — *Token address*, *Generate token*, expiry, renewal, re-authorise, and the word *token* | One key per connection; no connector holds both kinds of secret | *"i only want to issue a key per conenction"* |
| The **clock box** — *Time* + *Your time zone. The only part you choose.* | Scheduling moved to Runbooks | *"conenctor i a conenctor not a logic to to ETL"* |
| Any **editor on the call limit** | It is a guard, not a setting. A value in a cell | *"so wecant allow clark to reset it"* |
| The **usage count** — *Calls used this week — 4,180 of 10,000* | Argued for well; not ruled | struck by *"thats it"* |
| The **card-page choice** — *hosted by them \| embedded* | Embedding puts us inside the card industry's audit for ever | *"A · their page only"* |
| **Fields two to a row** | B14 rule 38 — construction is the UI rules' | — |
| The refusal strips' *"See CR-3 and CR-11"* / *"see RAN-2"* | B14 rule 32 — no rule id in clerk copy | — |

⚠ **THE `When it runs` PANEL IS AN EMPTY REGION AND IS REPORTED RATHER THAN
FILLED.** Take the clock box away and the drawn panel holds one sentence —
*"13 of 16 run on a clock…"* — which is the WHEN column above it, aggregated. A
panel whose only control moved to another module and whose only remaining
sentence restates the row above is a heading over nothing, so it is not drawn.
**Nothing was invented to fill it.** `cadence` is untouched.

## What is drawn, has no store, and was NOT invented

**`RATE LIMIT` renders a dash on all 28 connectors.** Nothing stores it; the
back-end lane's `rate_limit` row is what fills it, and the cell already reads
that field, so the column fills itself with no edit to the screen. **No figure
was copied off a frame** — B14 rule 37, and the blueprint says so of its own
numbers on p017.

## Two columns made real, and they are NOT the other lane's three

`Operation.trigger` and `Operation.host_field` have been on the manifest since
wave B and reached no screen, because `_operation_row` did not serialise them —
so `WHEN` and the endpoint under `API · ENDPOINT` would each have been a column
of dashes on all 28 connectors, for ever, with every test green. Two lines in
`apps/integrations/selectors.py`. **Neither is the call limit, the nightly hour
or the key scope.**

## Five defects, four of them found by LOOKING

| Id | What | Found by |
|---|---|---|
| `DEF-INT-5491` | The kicker printed a raw enum: **`ACCOUNTING · OUT.THEM`** | reading the screenshot |
| `DEF-INT-6444` | The key we issue was drawn **twice**, once stranded beside an unrelated label | reading the screenshot |
| `DEF-INT-5493` | The `WHEN` column borrowed the run-history FILTER's words and read *"A partner"* | reading the screenshot |
| `DEF-INT-5494` | The screen **promised** to send a clerk to the vendor and had **no button that could** | reading the screenshot |
| `DEF-GOV-5520` | `G29` and `screenIds.test.tsx` have been RED at the tip since 2026-09-14 and lanes pushed past | reading a failure I did not cause |

⚠ **FOUR OF THE FIVE PASSED `tsc`, THE ROUTE TEST, AND EVERY GATE.** That is
hard-won law 6 with nothing else to say about it: no check in this repo reads
rendered output, and a person looking at a picture is the only instrument.

⚠ **`DEF-GOV-5520` IS NOT ABSORBED** (renumbered from `DEF-GOV-5490` — see the collision table below).** `G29`'s baseline was deliberately left
untouched. Raising it would have paid off another lane's debt inside this
wave's number and made the finding invisible; the counts it reports now include
this wave's one screen, which carries both ids.

## Not done here, and named so it is not assumed

**The eleven catalogues are untouched** — another lane holds them this hour for
the 319-key Connector rename. Every new string names its key and carries its
English through `t(key, { defaultValue })`, which is this module's existing
pattern. **The fan-in is outstanding work, not a finished job.**

---

## ⚠ AN ID COLLIDED THREE WAYS IN ONE AFTERNOON, AND THE CONVENTION FOR FIXING IT WAS DELIBERATELY BROKEN

**`G17` went RED at the tip on 2026-09-16 with TWO duplicate ids, not one:**

| Number | Taken first by | Taken again by |
|---|---|---|
| `DEF-GOV-5490` | the New Connect step 5/6 lane (`6351747f`) | the `CR-110-BRC04` **wave A** lane (`a460ebaa`) |
| ↳ **RESOLVED 2026-09-16** | keeps `DEF-GOV-5490` | renumbered to **`DEF-GOV-5520`** |
| `DEF-INT-5491` | the `CR-110-BRC04` **wave C** lane (`e5fa4189`) | the `CR-110-BRC04` **wave A** lane (`a460ebaa`) |

**This is hard-won law 11 exactly, and every lane's arithmetic was right.** A
sibling working in its own `git worktree` has its rows in NONE of the places a
listing can see until it pushes, so `max + 1` gives the same answer to two
lanes at the same moment. The decision log of the same day records a THIRD lane
hitting the same number and being saved by `allocate.py defect --verify` at push
time — `DEF-SHL-5491` became `DEF-SHL-5492`. **That is the whole difference: the
verify was run once and skipped twice.**

⚠ **`G17`'S OWN MESSAGE SAYS *"renumber the LATER one"*, AND WAVE C RENUMBERED
THE EARLIER ONE INSTEAD — ITS OWN.** The rule exists to minimise citation churn,
and here it would have maximised it:

* wave C's row was cited in **one** place outside the register — a line of this
  file, moved in the same commit;
* wave A's row is cited in **two code comments inside
  `ConnectorSetupPage.tsx`**, a file that lane is live in, plus two lines here.
  Renumbering theirs without moving their citations is `DEF-2804`'s shape — *a
  real id read for a different real id* — and moving them means editing a
  sibling's live file.

**So wave C's naming-drift row is `DEF-INT-5495`** (allocated against the remote
and `--verify`-ed), and **wave A's kicker row keeps `DEF-INT-5491`** with every
citation it already has. The letter of the convention was broken to serve its
reason, which is recorded here rather than left for the next reader to wonder at.

⚠ **`DEF-GOV-5490` WAS NOT WAVE C's TO FIX, AND IS NOW RESOLVED.** Both of its
claimants are other lanes and one of them is live. `G17` names the rows and the
line numbers; whoever owns the later one renumbers it. **It is stated here
because a red nobody names is a red the next reader is told not to look at** —
which is `DEF-CWP-4187`, where two lanes called a red *pre-existing, not mine* in
good faith and the second was the lane that had caused it.

---

## THE CLOSURE BAR FOR THIS CR — the PO's own walk, across all 28

**PO, 2026-09-16, verbatim:**

> "ocne you complete all tasks related to integration/corrector - i want you to do walk - like any clark will do - open each connector and see it open up the detaila nd you are able to perform actions - what it does when you perform actions - what message it gives"

⚠ **THIS IS NOT A NEW REQUIREMENT AND IT MUST NOT BE FILED AS ONE (law 13).** It is
`13-change-process.md`'s existing closure bar, which the PO set on 2026-08-18 —
*"CR is not closed until we have confirm user is able to perform tasks using
screen/broswer/UI"* — restated with the detail that matters for a screen rendered
28 ways: **every connector, not a sample.** A shape that renders for one vendor and
not for another is exactly what a sample walk cannot see.

**`10-scripts/cr110_connector_clerk_walk.mjs` is that walk**, and it is committed
rather than left in a scratch directory because in this environment **only what is
pushed survives** (law 12). Per connector it records the card's every button and
whether each is ENABLED, what pressing the primary control opens or navigates to,
the words that come back, whether the set-up and connection screens open, and a
screenshot.

⚠ **IT ASSERTS WHAT THE STACK SERVES BEFORE IT BELIEVES ANYTHING, AND THAT CLAUSE
IS PAID FOR.** On 2026-09-16 a front end was started on a port **another lane already
held**, so it never bound; the browser was quietly served by the older stack, and
its 18 retired connectors were reported to the PO as a product fault. **A walk
against the wrong backend is not a weaker proof — it is a proof of a different
product.** The run now reads the provider count off the API first and refuses to
walk if it is zero.

⚠ **AND ITS FIRST DRY RUN CAUGHT A CHECK THAT COULD NOT DISTINGUISH — IN THIS
LANE'S OWN CODE, WHICH IS THE POINT OF RECORDING IT.** The walk decided a screen was
missing by looking for the phrase *"not built yet"*. **That phrase is TWO different
sentences:** the product's generic catch-all page says *"This screen is not built
yet"*, and a connector the PO deliberately HELD says *"Coming soon · W7 — not built
yet."* So a correct, ruled refusal scored as a missing screen — and left alone it
would have reported **eleven held connectors as eleven faults** and buried the real
ones underneath. That is law 7's *looking at the wrong thing*, committed by the lane
that had spent the day briefing others about it. The fix distinguishes the two
sentences and says why, in the script, where the next reader is.

**The CR is not closed until this walk runs over all 28 and its result is put to the
PO.**

---

# Wave B — the CONNECTION VIEW screen, built · `2.281.0`

**Track: MAINTENANCE, not Build** (`22-product-maintenance-process.md`). The one
question — *can a user do this task in the product today?* — answers **yes**:
`settings/integrations/:key` is routed at `App.tsx:582` and S142 has shipped since
`CR-069` wave C. This is the redesign case the process names by name, so it borrows
the drawing step from Build and keeps reproduce, locate, blast radius, regression,
version, rollback and the reporter.

⚠ **THE ROUTE DID NOT MOVE AND MUST NOT.** The blueprint draws
`/:tenant/settings/connectors/<key>`; the address stays `settings/integrations/:key`.
Changing a live address breaks every bookmark to buy a word in a place nobody reads
for meaning, and the visible-word rename is the catalogue lane's, together with the
routes, in one act.

## Reproduce → locate → blast radius

* **Reproduced** in a browser at 1440 before any code was read: four connectors on
  `brazosbend` as Dana Whitfield. The screen listed each operation as **two facts in
  a bare `<ul>`** under *WHAT THIS CONNECTION DOES* — a name and a state word. The
  drawing has a **seven-column table**. Captures kept as the *before*.
* **Located** the file actually mounted — `features/integrations/ConnectionDetailPage.tsx`,
  aliased in `App.tsx` as `IntegrationDetailPage` because
  `features/customers/ConnectionDetailPage.tsx` shares the name. The name-matching
  file is not the mounted one, which is the trap step 1 exists for.
* **Blast radius, both ways.** Consumers: `App.tsx`, `ConfirmDialogTier.dom.test.tsx`,
  `WarningBox`. Neighbours sharing the feature: `IntegrationsTab` (whose `StateWord`
  gained an opt-in prop), `AccessLogPanel`, `ConnectModal`, `ValueMappingPage`,
  `MachineKeysPage`. Removed nothing, so the mirror direction is empty —
  `integrations.runs.operationsTitle` is the only key this wave stops calling and it
  stays in the catalogues for the rename lane.

## What was built

| Drawn | Was | Now |
|---|---|---|
| The API table, 7 columns | a `<ul>`, name + state | **`API · ENDPOINT · DIRECTION · WHEN · RATE LIMIT · LAST RUN · RESULT · TEST`** |
| Panel with an accent | unboxed `<h2>` | `<Panel accent>` — the kit's existing prop, no kit change |
| *N APIs on this connector* | *WHAT THIS CONNECTION DOES* | the drawn heading, counted, **never an aggregate state** (`BR-INT-028`) |
| `N APIs` chip by the name | not built | built, and it is a COUNT rather than a word |
| A dot on the state | no dot | `StateWord dot`, one tone map for the card and this page |
| Meta line, four facts | two | **category · every direction · environment · who connected it** |
| *One key. All N APIs use it.* | not built | built, saying **key** |
| Placeholder says so | only the grid said it | the page says it too |

**Served for the first time** (`selectors._operation_row`): `trigger` (on the manifest,
never serialised) · `endpoint` · `rate_limit_per_minute`. **No migration, no new table.**

⚠ **THE RATE LIMIT IS REAL WHERE IT IS SHOWN AND A DASH WHERE IT IS NOT.** A number
appears only on an operation a partner calls — `initiative == "them"` — because
`check_rate_limit` guards that direction and nothing throttles the calls we place.
Measured: a kiosk operation answers **100/min** by default and **250** when the
connection carries one; an SMTP send answers a dash. Printing the inbound ceiling
beside an outbound call would be a figure claiming a guarantee nothing keeps.

## ⚠ EVERY DELIBERATE ABSENCE — one line each, because an absence is invisible to every check here

| Not built | Why, and whose ruling |
|---|---|
| **A rate-limit input, Save or editor** | PO: *"we cant allow clark to reset it … keep the check in code - thats it"*. Display only, and the drawing's own line already read *display only* |
| **The usage count** — *Calls used this week — 4,180 of 10,000* | Drawn on p017 and argued for there; **explicitly struck** by *"thats it"*. Recorded as a later candidate, not smuggled in |
| **The clock box / run time** | Scheduling is Runbooks' — *"conenctor i a conenctor not a logic to to ETL"*. Nothing read `.schedule` anyway |
| **Any mappings work** | *"we dont need mapping at connector level it will be in runbook"*. `S143` is LIVE and untouched — walked in the regression below |
| **The Token panel, expiry, renewal, re-authorise wording** | *"i only want to issue a key per conenction … i dont understand the differnt between key and token"*. The word *token* renders nowhere on this screen, asserted in the walkthrough for all four connectors |
| **A per-row Test BUTTON** (the column IS built) | `DEF-INT-5489`: `POST /integrations/{key}/test` takes a recipient and **no operation**, so a per-row button would run the connector's test and report it against one row. The column carries the manifest's own sentence instead — real information, no dead control. PO's rule: *"a box that does nothing is worse than no box"* |
| **`Test all` in a footer row** | Drawn on p048 and p082. The connector-level test is already reachable from the card, and a second entry point needs the recipient dialog the card already owns — a second copy of a kit dialog. The empty state already names where to test. Left, deliberately, rather than duplicated |
| **`Retry` beside a failed RESULT** | Same door problem as the per-row Test, and the reason text is the clipped half of the drawing (`DEF-INT-5487`) |
| **The red *"No token on this one…"* note** (p082) | RATIONALE — why a control is absent — is **ZERO words on screen** (B14 rule 33). It also uses the retired word |
| **An aggregate status word over the table** | `BR-INT-028`. Asserted for all four connectors |
| **`← Connectors` · kicker `CONNECTOR`** | The 319-key rename is another lane's, in one act with the routes |
| **Two-to-a-row form fields** | B14 rule 38 — where a drawing and our UI rules disagree about how a FORM is built, the UI rules win. Not this screen's anyway |

⚠ **AND ONE ABSENCE THAT IS A FINDING RATHER THAN A CHOICE.** The PO named **bulk
email and the print vendor** as the placeholders. In the registry today both are
`Disposition(kind="live")` with a phase hold; the four actually marked `coming_soon`
are `payments_card`, `meters_mdm`, `sms_twilio` and `sso`. The screen reads the
declared field and so says *Coming soon · v1.1* on Twilio and nothing on the print
vendor. **The manifests are another lane's to correct** and this is written here so
the mismatch is found rather than rediscovered.

## Proof

* **Four connectors walked in a browser at 1440** against a stack built from this
  branch (bundle hash checked against the served page, after a first capture was
  taken from a sibling lane's server on a port I had assumed was free).
* **24 screen checks and 3 neighbour regressions pass** — the grid, `S143` mappings
  and `S144` machine keys all still load, with no console error and no 4xx.
* **The door test was proved RED first, in vitest**, by moving the route in
  `App.tsx` — *"expected [ '/', '/pricing', … ] to include
  '/:tenant/settings/integrations/:key'"* — and it reads `APP_ROUTES`, the array the
  browser router is actually built from, rather than a `<Routes>` of its own.
* **Two copy defects caught only by looking:** *1 APIs* (a `defaultValue` does not
  pluralise) and the state word flung to the far edge of a 1,440px page by
  `justify-between`. Neither is visible to any test in this repository.

## Reds, dated — not called *pre-existing* on faith

| Red | Verdict |
|---|---|
| `routing/screenIds.test.tsx` — *covers every routed screen, in App.tsx's order* | **Pre-existing.** Re-run at the pinned tip `6d526d69` in a clean worktree, with none of this wave's changes: red there too |
| `test_us_int_014_tc7` (the five-table brief) | **Pre-existing.** Same method, red at the tip |
| `test_us_int_023` (the reason once a mailbox is connected) | **Pre-existing, and it took three runs to establish that honestly.** Run ALONE at the tip it PASSES, so the cheap check said *yours*. It also passes alone here, and passes as a whole file here. The thing that settles it is the LIKE-FOR-LIKE run: the same `-k` selection, same harness, at the pinned tip in a clean worktree gives the **identical** result to mine — `2 failed, 436 passed, 26 skipped`, the same two names. It is an ordering interaction inside that selection and it is not this wave's |

⚠ **THE METHOD IS THE POINT, NOT THE VERDICT.** A test that passes in isolation at
the tip and fails in a suite looks exactly like a red you just caused, and the
honest answer costs a second twelve-minute run at the tip with the SAME selection.
`CLAUDE.md`'s habit — *date the ones you call pre-existing* — is what stopped this
being written off either way; two lanes have already reported a red as *not mine*
when one of them had caused it.

## Rollback, stated before shipping

**Code only — revert the commit.** No migration, no schema change, no data repaired
and nothing sent out, so the revert is complete. `DEF-INT-5502`
are register rows and stay filed either way.

**Fixed in 2.281.0.**

---

## ⚠ What re-deriving at the tip found, and it is the most useful thing in this wave

`push_paths.sh` **refused the first push**: seven of the fourteen named paths had
moved between the base this was built from and the live tip. Re-applying onto the
tip's bytes — which law 11 prescribes and which is the only reason any of this was
seen — turned up three collisions with **wave A**, landed while this was being built:

1. **A DUPLICATE `"trigger"` KEY in `_operation_row`.** Wave A serves it for the
   set-up screen; this wave's re-apply added a second one. **A repeated key in a
   Python dict literal is legal and the last one silently wins** — no error, no
   warning, and nothing in the suite could have seen it. Removed; wave A's stands.
2. **`DEF-INT-5502`'s first filing was a DUPLICATE of wave A's `DEF-INT-5488`** —
   both are *an operation's `host_field` names a field its manifest never
   declares*. Two lanes measured the same thing from two screens within an hour.
   The duplicate row was dropped before it was published, and `DEF-INT-5502` is now
   the one genuinely new finding.
3. **Two mechanisms for one fact, kept on purpose rather than by accident.** Wave A
   serves `host_field` — the NAME — and walks it in the screen. This wave serves
   `endpoint` — the resolved VALUE. Both travel, and the comment at each says why:
   a screen that only walks the name draws a dash on every connector we ship,
   because of the very gap `DEF-INT-5488` records. The fallback to the manifest's
   own single field of kind `host` is what makes the column show
   `sftp.bank.example.invalid` instead of nothing.

⚠ **BOTH DEFECT IDS TAKEN AT THE FIRST ATTEMPT WERE ALSO GONE** — `allocate.py
defect --verify` answered *TAKEN — a sibling pushed it* for `5493` and `5494`.
Every arithmetic step had been right; the world had moved. That check costs one
command and it is the whole of law 11's unconditional re-derivation.

⚠ **AND THE RE-DERIVATION ITSELF NEARLY SHIPPED AN EMPTY WAVE, WHICH IS THE
PART WORTH KEEPING.** `git apply` is ATOMIC: two of the nine files failed on a
stale index, so **nothing was applied** — while the per-file lines *"Applied
patch to ConnectionDetailPage.tsx cleanly"* scrolled past looking like success.
`tsc` passed, eslint passed, **75 of 75 vitest cases passed**, and the build
succeeded, because the screen had simply reverted to its shipped self and its
own tests still described that. **What caught it was opening the page in a
browser**, which is hard-won law 6 being the only instrument there is.

⚠ **AND THE BROWSER WALK THEN CAUGHT A SECOND ONE THAT NO TEST COULD.** Reading
`payload.provider.disposition.kind` off a payload that does not carry the field
threw into the error boundary and replaced the whole connector page with
*Unexpected Application Error*. `tsc` could not see it — the type SAID the field
is always there, and the wire decides that, not the type. The field is optional
now, for the reason wave A already gives for `trigger`.

⚠ **THE WALKTHROUGH COULD NOT TELL A CRASHED SCREEN FROM A WORKING ONE.** The
error boundary catches the throw, so `pageerror` stayed EMPTY and the script
reported *errors: none* over a page that was entirely an error message. That is
law 7's *looking at the wrong thing* in this wave's own proof, and it is fixed
in the same commit: every connector is now asserted to RENDER before anything
else is asserted about it.

### Proved again on a CLEAN CHECKOUT of the pushed branch, and two things only that found

Built and walked from a fresh worktree at `dd6522db`, against the 28 connectors
wave A had landed in the meantime. **31 of 31 checks pass**, including
`erp_sap` — a connector that did not exist when this screen was written — which
renders the full seven-column table with **no screen code of its own**. That is
`BR-INT-037` demonstrated rather than asserted.

⚠ **THE WALKTHROUGH'S S144 CHECK WENT RED, AND IT WAS NOT A REGRESSION.** It
named `gl_partner`, and wave A **split that connector into five named ERPs**
while this wave was being built, so the address no longer exists. Fixed to
`erp_sap`, with the reason in the file, because the next lane would otherwise
have spent the same twenty minutes on it. **A walkthrough pinned to a connector
key is pinned to a decision somebody else can reverse.**

⚠ **AND THE `WHEN` COLUMN ANSWERS *WHO* ON ONE VALUE.**
`integrations.runs.trigger.partner` reads **"A partner"**, which is a fine
answer in the run history's *Started by* filter and reads oddly in a column
headed WHEN — an ERP row says *When: A partner*. The blueprint's own word there
is *On demand*. **Not changed here**: it is an existing key in eleven
catalogues, held by the Connector-rename lane this week, and changing an agreed
word in passing is how two lanes end up with two vocabularies. Recorded for that
lane rather than left to be rediscovered.

⚠ **AND TWICE IN THIS WAVE A CAPTURE WAS TAKEN FROM A SIBLING LANE'S SERVER**,
because a port that looked free was not, and once because a copied script still
carried the shared stack's port. Both times the screen looked wrong for reasons
that had nothing to do with this work. **Check the served bundle hash against
the one your own build just wrote** — it is one `curl`, and it is in the
walkthrough's header now.
# WAVE D — BUILT · the two migrations, and nothing else rode along

**Version `2.282.0`** (`10-scripts/allocate.py version --bump change`, against the
remote; written in `07-frontend/package.json`, `package-lock.json` and
`06-backend/pyproject.toml`). Step 7 of the change process, which is the step
that gets skipped.

## The two commits the PO asked for

| Commit | Migration | What it does to the database |
|---|---|---|
| *the call limit* | `integrations/0009_cr110_rate_limit_store.py` | **creates one table**, `integration_rate_limit` — a ceiling in calls per minute, one row per connection AND per operation — with its unique key, a `CHECK (calls_per_minute > 0)`, one index, a real `ON DELETE CASCADE`, and **the signed B2 §3 row-level-security policy in the same migration** |
| *the key's scope* | `integrations/0010_cr110_key_scope.py` | **adds one column**, `integration_credential.scope` (`jsonb NOT NULL DEFAULT '[]'`) — which of our APIs one issued key may call |

A third commit precedes them and carries the **database-design brief**, because
`C34` requires the brief to be anchored before the migration. Everything that
USES the two — the shared counter, the door, the mint, provisioning, the
settings and the tests — is a fourth commit, so each migration commit is a
statement about the database and nothing else is hidden beside it.

## What the shared counter is, and what it does when it breaks

**The store is Django's default cache** (`django.core.cache.cache`), which
`config/settings/base.py` points at Redis when `CACHE_URL` is set. It was chosen
because **this repository already owns this job** — `apps/portal/guards.py`
counts three rate limits and an in-flight budget in exactly that store, for
exactly this reason. A table in PostgreSQL was considered and rejected: it puts
a write on the money database for every partner request including the ones we
are about to refuse, so a flood of refusals would cost US more than the caller,
which is a rate limiter that helps the attacker.

**When it cannot be reached, the call is REFUSED** — the same `429` and
`Retry-After` an over-limit caller gets. There is no arm that serves a request
it could not count, and deliberately no `allow_on_error` argument, because an
argument that could switch this to *allow* is the argument an attacker is trying
to reach. **A per-process cache also refuses**, unless the deployment says
otherwise in writing: `INTEGRATION_SHARED_COUNTER_REQUIRED` is **True** in
`base.py` and False only in `config/settings/test.py`.

⚠ **THAT HAS A DEPLOYMENT COST AND IT IS STATED RATHER THAN DISCOVERED.** A host
with no `CACHE_URL` answers nothing but `429` on its partner routes until
somebody configures one — hard-won law 3, the same shape as `sslmode=disable`
blocking a live deploy. And hard-won law 4: **a host that already has a `.env`
gets nothing from this commit** and must be given `CACHE_URL` by hand.

## With four workers, what is the real limit now?

**It is the limit**, and the proof is two cases rather than one, because one
case conflating them produced a number that meant nothing.
`tests/test_cr110_shared_counter_pg.py` runs **four real operating-system
processes**, each with its own empty module state, each trying the whole
allowance:

| | Result | What it proves |
|---|---|---|
| **One after another** | **20 admitted against a ceiling of 20** — and the fourth process, which has counted nothing of its own, is refused every time | the count crosses a process boundary, which is the whole defect |
| **All four at once** | about **40**, where a per-process counter gives **80** | shared, but not exact on this backend |

⚠ **THE SECOND NUMBER IS STATED RATHER THAN SMOOTHED, AND THE FIRST DRAFT OF
THIS SECTION SMOOTHED IT.** It said *"a call or two loose"*; the measurement
said 40 against 20. The store used for the proof is Django's **database** cache,
because this machine has no Redis, and its `incr` is `get`-then-`set` — four
processes racing on one key lose increments to each other. **The deployment
store is Redis, where `incr` is one atomic server-side operation**, and that is
where the simultaneous case tightens. Writing *a call or two* would have been a
comment claiming a guarantee, which is hard-won law 1 in the one paragraph
somebody would quote.

Four processes and not four threads on purpose: threads share module globals, so
a threaded test would have passed on the broken code too, which is hard-won law
7's *structurally incapable of failing*.

## Rollback, stated before shipping (step 8)

- **`0010`** reverses as `RemoveField`. ⚠ It is a rollback of last resort, not a
  tidy-up: after it, **every issued key can call everything on its connector
  again** — the defect the blueprint named, re-opened.
- **`0009`** reverses by dropping the table; the policy and the cascade go with
  it. `serve.rate_limit_for` then falls back to the connection's `config` value
  and to `DEFAULT_RATE_LIMIT_PER_MINUTE`, so the limit still applies — it simply
  stops being per operation and stops being changeable without a release.
- **The shared counter reverses by setting `INTEGRATION_SHARED_COUNTER_REQUIRED`
  to False**, which returns the product to a per-process count. That is the old
  `N × 100/min` behaviour and it should be a deliberate, temporary act.

## Struck, and still struck

The **usage count** (*"Calls used this week — 4,180 of 10,000"*) and the
**outward throttle** are recorded as candidates and are **not built**, under the
PO's *"thats it"*. Nothing in wave D adds a `used` column, and the migration's
docstring says so, so a later lane widening the table has to widen a ruling
rather than a schema.

## Seven things found while building, filed rather than left in a docstring

| Id | What |
|---|---|
| `DEF-INT-5503` | The **kiosk inbound door had no call limit at all** — a payment machine posts money events at it with no session and no person, and only the two partner READ routes were metered. **Fixed in this wave.** |
| `DEF-INT-5504` | Two vocabularies for one idea — the clerk ticks *payments · bills · customers* and the door enforces `read_payments · read_bills · read_customers`. **Not fixed**: a manifest belongs to the lane that owns the set-up form. |
| `DEF-GOV-5505` | `test_us_int_014_tc7…` has been **RED since 7 September** and reads like a broken tree. **Not fixed**; the rule it guards was honoured anyway. |
| `DEF-GOV-5506` | `makemigrations --check` has been **unclean on `rating` since 10 September**, so every lane's migration guard has a true failure sitting beside it. **Not fixed**: it is a rating lane's file. |
| `DEF-GOV-5507` | **G7 has been RED since 6 September** on five 🔒 migration files that carry no `HUMAN-OWNED` marker — so the gate that enforces the sensitive-path protocol has a true failure sitting beside it, and every lane since has read it as background. **Not fixed**: five other lanes' migrations. |
| `DEF-GOV-5508` | **A `git rebase --skip` discarded seven late fixes of this wave's own, and every law-11 check passed** — they all read a COMMIT, and the loss was in a commit that was never made. Found by grepping the PUSHED tree for one distinctive string per change. **Fixed in this wave**, restored from the dangling commit and pushed as two further named commits rather than by force-pushing a shared branch. |
| `DEF-INT-5510` | **The `smtp_adapter` test fixture unbinds the PRODUCT's email adapter at teardown**, so any suite using it silently disconnects email for every later test in the process. It surfaced as `test_us_int_023_...` failing only in multi-file runs — a red that reads as flakiness and gets re-run rather than read. Bisected to the `040 → 023` ordering and diagnosed by reading `unregister_adapter`, whose own docstring says the product binds at `ready()` and never unbinds. ⚠ **MEASURED, NOT ASSUMED: the same pairing fails identically at `ab1a9044`, the commit before this wave's first push** — `1 failed, 16 passed`. **Not fixed**: a shared test helper with four lanes live in these suites. |

## Six things the tests found that no amount of reading would have

**1 · Adding one column destroyed a database guarantee on the vendor the whole
suite runs on.** `integration_credential.scope` is an `AddField`; SQLite cannot
add a column in place, so Django REBUILDS the table — and the rebuild carries
only the indexes Django knows from the model. `BR-INT-025`'s *exactly one
active key per connection* lives on SQLite as a partial index written in raw
SQL by migration `0001`, so it was dropped and never recreated. The migration
applied cleanly and the guarantee was gone. **PostgreSQL never rebuilds on `ADD
COLUMN`, so the vendor that keeps its guarantee is the one nobody runs by
default and the vendor that loses it is the one every lane runs.** `0010` puts
it back in both directions, and the rule generalises to any future change to
that table.

**2 · The column's database default did not exist, and the migration's own
docstring promised it.** `AddField(default=list)` tells Django what to backfill
with; Django then **drops the database default**, because it applies defaults in
Python. So the third guard — *a row written by some path that forgets arrives
powerless rather than omnipotent* — was a sentence. It surfaced through
`test_us_int_014_pg.py`, a sibling's case about a completely different
guarantee, whose raw `INSERT` omitted a column that did not exist when it was
written: `null value in column "scope" … violates not-null constraint`. **It was
right to fail and it named the real gap rather than the one it was watching** —
reading a failure you did not expect, which is law 7's first habit. `0010` sets
the default explicitly now, and a case of our own holds it.

**3 · The shared counter could never have said yes.** It read
`type(cache).__module__`, and `django.core.cache.cache` is a proxy — so that is
`django.utils.connection` for Redis, memcached, LocMem and Dummy alike, and a
correctly configured Redis deployment would have refused **every** partner
request. Three of our own cases passed over it, all three asserting False and
all three getting False for the wrong reason. **A suite that only ever asks a
predicate to say no cannot tell a working predicate from one incapable of
saying yes.** Found by the four-process proof, which is the only case that
stands up a real shared backend.

**4 · The `ON DELETE CASCADE` this wave tried three times to write cannot be
written where it tried.** See below.

**5 · A list of operation names typed out by hand went stale inside ONE DAY,
and it was this CR's own wave C that staled it.** The scope guard made three
existing suites need a sentence they had never needed — *what may this test's
key do* — and the obvious way to write it is to type the three operation names.
Wave C then split one generic finance card into five named ERPs and renamed
`read_payments` to `serve_payment`, and **nineteen cases went red at once**,
every one of them refusing in the door's five words because the key named
operations the connector no longer had. **The refusal was correct; the fixture
was wrong.** The lists are derived from the manifest now
(`[one.name for one in REGISTRY.require(…).operations if one.they_call_us]`), so
a sixth ERP or a renamed operation costs nothing — which is `BR-INT-037` applied
to a test rather than to code, and the same reason wave C derived
`partner_provider_keys()` instead of keeping a constant.

**6 · A test seam called `cache.clear()` and wiped a store it shares with the
whole product.** `serve.reset_partner_limits()` used to empty a module-level
dict; pointing it at the shared counter turned it into *empty the default
cache*, and it carried a reassuring comment saying that was *"safe because
nothing but a test calls this"*. Three cases in `test_us_int_041` call it. The
damage showed up as `test_us_int_023_..._once_a_mailbox_is_connected` failing in
a seven-file run and passing in every smaller one — **the shape of a leak
between suites, which is the most expensive kind of red because it reads as
flakiness and gets re-run rather than read.** It deletes only the keys this
module wrote now, which is also the honest scope: a test seam has no business
emptying a store it shares.

## One decision worth reading before writing `on_delete=CASCADE` anywhere else

`0009`'s docstring claimed `ON DELETE CASCADE` and the database-design brief
copied the claim. **The database did not have it, and cannot be given it in that
migration.**

`on_delete=models.CASCADE` in a Django model is an APPLICATION cascade: the ORM
issues the child DELETE itself, and the constraint written is `NO ACTION
DEFERRABLE INITIALLY DEFERRED`. The wave then spent sixty lines and **three
rounds of the same failing assertion** learning why it could not simply fix
that, and all three said `assert 3 == 0`:

1. the cascade was Django's, not the database's;
2. the `ALTER TABLE` written to fix it picked the **`tenant_id`** foreign key,
   because the lookup asked for `contype = 'f'` and took the first row, and the
   table has two;
3. the `ALTER TABLE` found **no constraint at all** — Django creates a
   `CreateModel`'s foreign keys through `schema_editor.deferred_sql`, which is
   flushed only **after every operation in the migration has run**. Its own
   `# pragma: no cover — the CreateModel above just wrote it` comment was a lie
   about the line it sat next to.

**So the claim came out of the docstring and out of the brief, instead of the
behaviour being bent to match it.** A third migration would have broken the
Product Owner's *two migrations, their own named commits*, and what we actually
have is already the safe direction: an ORM delete removes the ceilings, and a
raw `DELETE FROM integration_connection` is **REFUSED at commit** rather than
silently orphaning them. The test asserts both halves.

**The transferable part: a test that deletes through the ORM would have passed
over every one of those three states.** It had to delete by raw SQL to be able
to fail — law 7's second habit, *what would make this check pass wrongly*, asked
before the check was written and answered three times over.

---

# CON-01 MAINTENANCE — the card, the toolbar, the footnote and a raw key · `2.282.1`

**Track: MAINTENANCE, not Build** (`22-product-maintenance-process.md`). One
question decides it — *can a user do this task in the product today?* They can:
`settings/integrations` is live, a clerk uses it, and CON-01 is that screen
redrawn. A redesign of a screen people already use is Maintenance by name, and
this is four fixes inside one, so reproduce · locate · blast radius apply and
the drawing step is the one thing borrowed from Build.

## What the PO said

> "panel class for each card - 28 conenctor is not correct - we are using panel
> -accest something - also toolkit is not ocrrect search, filter, colume selctor
> etc desctoption -"

and, looking again:

> "see there is a line on top and color to card - panel ui is not correct"

## 0 · Reproduced first, in a browser, before a line of code was read

At 1440 against the live build, signed in as a System Admin at `brazosbend`.
Measured rather than eyeballed — `getComputedStyle` on the first of the 28
cards, and the page behind it:

| What | Before | Drawn (CON-01) |
|---|---|---|
| The card's top edge | `1px` in `rgb(234,231,231)` | a 2px rule in the accent, on every card |
| The card's background | `rgb(243,242,242)` | a surface of its own |
| The page's background | `rgb(243,242,242)` — **identical** | — |
| The toolbar | search + 11 chips. `+ Filter` 0, `▦` 0 | four parts |
| The footnote | `28 services you can connect.` | `28 connectors · 11 connected. Showing every category.` |
| The ERP category | `integrations.category.erp`, on the chip **and on five card kickers** | `ERP` |

**Six occurrences of the raw key, not one.** The brief named the chip; the
kicker of every ERP card had it too, because both build the same key.

## 1 · Located

`07-frontend/src/features/integrations/IntegrationsTab.tsx`, mounted by
`features/tenancy/SettingsPage.tsx:509` as the `integrations` tab. The card is
its private `Card()`; the toolbar is its `<header>`.

## 2 · Blast radius, both ways

* **`Panel` gained `as="article"`** — one word on an existing union. 81 feature
  files render `Panel` and **none moves a pixel**: every existing call site
  passes `div`, `section` or `aside`. `Panel.test.tsx` green.
* **The `▦` panel MOVED out of `DataTable.tsx` into `components/ColumnChooser.tsx`**
  — 27 live list screens render it. Every byte of markup is unchanged, the three
  decisions (`toggleColumnVisible`'s config-order re-insert, BR-SHL-013's
  identity lock, the reset set) **stayed in `DataTable`** as callbacks, and
  `DataTableColumnPrefs.dom.test.tsx` + `DataTableColumnAnchor.dom.test.tsx` are
  the proof — both green, neither touched.
* **`FilterBar` is rendered, not copied.** The `+ Filter ▾` on this screen is
  the same component `SettingsCustomFields`, `AssetImportsTab` and the routes
  tab already use, through the same `offerableFilters` step.
* **What was REMOVED and who used it:** `integrations.footnote`'s old wording
  (no other call site — grepped), and the card's `border-neutral-200`/`bg-bg`
  and its `<h3>`'s `text-base font-semibold`, which `Panel`'s own
  `[&_h3]:text-h5` outranks and which would otherwise have become two classes
  that render nothing.

## 3 · What changed, and what it became

| Fault | Was | Is |
|---|---|---|
| `DEF-INT-5497` | a hand-rolled `<article>`, no `Panel` import | `<Panel accent as="article">` — the 82nd file to render it |
| `DEF-INT-5498` | two of UI-RULES 12's four parts | four: search · chips · `+ Filter ▾` · `▦` |
| `DEF-INT-5499` | one of the two counts the server sends | both, in two sentences inside B14 rule 33 |
| `DEF-INT-5500` | `integrations.category.erp` in six places | `ERP`, in all eleven catalogues |

## 4 · Proved against the reproduction, in a browser

`10-scripts/def_int_5497_connector_panel_walkthrough.mjs`, 20 checks, all
passing at 1440 on `2.282.1`:

```
✓ every connector card renders through Panel — 28/28
✓ every card carries a 2px rule on its top edge — 28/28
✓ every card has a surface of its own — card rgb(234,233,233) vs page rgb(243,242,242)
✓ the rule is drawn in the accent — rgb(236,48,19)
✓ ① search  ④ 11 chips  ② + Filter ▾  ③ ▦ Columns
✓ pressing one narrows the grid — 28 → 13
✓ unticking the per-API lines takes them off every card — 10 → 0
✓ the footnote carries both counts — 28 connectors · 3 connected.
✓ no raw catalogue key reaches the screen
```

**It reads `getComputedStyle`, which is the whole point.** `Panel.tsx`'s own
docstring records why a class-string assertion cannot see this: `border-width`
and `border-top-width` are different properties that COMPOSE rather than race,
so a card can carry every accent class a grep would look for and still render a
1px grey line. **The red proof is the BEFORE measurement in the table above** —
the same `getComputedStyle` properties, the same selector, the same page, taken
against the shipping build before anything was changed.

**And a component suite beside the code**, proved RED in `npx vitest run` before
a line of the fix existed — 7 of its 8 cases failed, verbatim:

```
× renders every card THROUGH Panel, not as a hand-rolled box
  → expected null not to be null            (the card had no data-panel)
× carries the accent rule and the panel surface, measured against Panel itself
  → expected false to be true
× negative · the retired hand-rolled border and page background are gone
  → expected 'flex flex-col gap-3 border border-neu…' not to contain 'border-neutral-200'
× draws the search box, the category chips, + Filter and the column chooser
  → expected null not to be null
× the footnote prints both counts
  → expected 'Integrations…' to contain '28 connectors · 11 connected.'
× no category reaches a clerk as its raw key
  → expected 'Integrations…' not to contain 'integrations.category.'
```

⚠ **The eighth was already green and is recorded as such:** the card was always
an `<article>`, and that case is there to stop the fix quietly turning it into a
`<div>` and moving the accessibility tree.

**The check worth more than the fix is on the backend**, because
`REGISTRY.categories()` is generated and the next category will do this again:
`06-backend/tests/test_def_int_5500_connector_category_words.py` fails when any
emitted category has no word — proved RED against the pre-fix catalogue read
straight out of `git show HEAD:…/en.json`:

```
AssertionError: connector categories with no word: erp (integrations.category.erp)
AssertionError: connector categories missing a word in some catalogues: {'erp': ['en']}
```

It also refuses the false pass — a line written as its own key would turn the
first case green and change nothing on screen, so that is a case of its own.

## 5 · Regression walked

`vitest src/features/integrations src/components src/styles` — **65 files, 695
passed, 30 todo**, one pre-existing failure (below). `tsc --noEmit` clean, and
**proved capable of failing** by planting `const __proof: number = "not a
number"` and watching `TS2322`. `eslint --max-warnings 0` clean.
`routeBUtilities.test.ts` green over the new file's utilities. At **1280**:
`scrollWidth` 1280 against a client width of 1280 — no sideways scroll, the
toolbar does not wrap. Both new controls are keyboard-reachable
(`<summary>` elements, no `tabindex="-1"`).

## 6 · Reds, dated — not called *pre-existing* on faith

`src/components/regionalReachesTheScreen.dom.test.tsx` fails, naming
`BudgetBillsTab`, `SettleUpForecastPage`, `DisconnectWizard`, `TransferWizard`
and `RunHistory`. **Reproduced on a CLEAN checkout of the tip `357590c9` with no
lane's work in the tree**, and `git log --diff-filter=A` dates
`SettleUpForecastPage.tsx` to `0c2e5570`, version **2.275.0** — seven versions
ago. Filed as `DEF-SHL-5509` rather than left as a sentence in this file.

## 7 · Version and rollback

**`2.282.1`** — `10-scripts/allocate.py version --bump fix`, verified against the
REMOTE at push time (`still free on every branch`). Written in
`07-frontend/package.json`, `package-lock.json` and `06-backend/pyproject.toml`,
with the changelog in the same commit, and **read off the running screen**:
`v2.282.1`.

**Rollback: code only — revert the commit. Done.** Nothing here repairs data,
applies a migration or sends anything out, so nothing is left behind. The ten
catalogue lines revert with it; the one they replace (`integrations.footnote`)
is in the same hunk.

## 8 · THREE THINGS NOT DONE, NAMED SO THEY ARE NOT ASSUMED DONE

1. **The `▦` offers THREE facts and the blueprint names FOUR.** p014 lists *"the
   per-API status lines, the failure reason, the environment line, the link
   row"*. The first three are a contiguous run between the summary and the
   action button, so show, hide AND `UI-RULES 14`'s ↑↓ reorder are all real on
   them. **The link row is not**: CON-01 puts it BELOW the action button, so an
   arrow on a fourth row would move it in an array and change nothing on the
   card — a dead control, which is hard-won law 2's mirror. Offering it means
   moving a live screen's button, which nobody asked for. **Left out and written
   down rather than shipped dead.**
2. **`FilterBar` brings an `All` chip that CON-01 does not draw on row one.**
   `UI-RULES 12` is `[Search…] [All | applied-filter chips ×] [+ Filter ▾] …
   [▦ Columns]`, and IS-4's `All`/clear-all is part of the bar, not a decoration
   on it. B14 rule 38 says the UI rules decide how a control is BUILT, so the
   shared bar is rendered whole rather than re-drawn without one of its parts —
   and the difference is filed here rather than silently resolved either way.
   Two `All` chips are now on screen, one per row; they are named apart for a
   screen reader (*Filter by* and *Filter by category*, both existing keys).
   **If the PO would rather the bar had no `All` here, that is one opt-in prop
   on `FilterBar` and it is theirs to say.**
3. **The rename is NOT done and was not touched** — the tab still reads
   *Integrations*, the route is still `settings/integrations`, and the search
   box still says *Search services…*. **One exception, and it is deliberate:**
   the footnote reads *"28 connectors · 11 connected."* because that is the
   sentence CON-01 draws and the count was the fault being fixed. It is one of
   the 319 catalogue entries the rename wave will move, moved early, and it is
   named here so that wave does not think it is already done.

---

## RULED · EVERY REFUSAL CARRIES A CODE — and the eight split two ways

**PO, 2026-09-16.** First: *"build refusal code in api responses so that we cna know what it is"*. Then, shown
the full eight-row table with the security consequence spelled out against each row: *"go with your
recommendation - implment all these code"*.

⚠ **THE RULING IS THE RECOMMENDATION, WHICH MEANS THE SPLIT IS PART OF IT.** The PO was
explicitly offered the other answer — *"If you'd rather the auth refusals also carry distinct
codes, say so"* — and chose the split. So this is not us softening an instruction; it is the
instruction.

| # | What went wrong | Code | On the wire to a partner | In OUR record |
|---|---|---|---|---|
| 1 | Called too fast — limit reached | `RATE_LIMIT_REACHED` | **distinct**, `429` | distinct |
| 2 | Our counter store is down | `COUNTER_UNAVAILABLE` | **distinct**, `429` | distinct |
| 3 | Key we have never seen | `KEY_UNKNOWN` | one shared code, `404` | **distinct** |
| 4 | Key is real but revoked | `KEY_REVOKED` | one shared code, `404` | **distinct** |
| 5 | Key is real but expired | `KEY_EXPIRED` | one shared code, `404` | **distinct** |
| 6 | Address not on the allowlist | `ADDRESS_NOT_ALLOWED` | one shared code, `404` | **distinct** |
| 7 | Connector switched off | `CONNECTOR_DISABLED` | one shared code, `404` | **distinct** |
| 8 | Key may not call this API | `OPERATION_NOT_IN_SCOPE` | one shared code, `404` | **distinct** |

**Rows 1 and 2 are safe to distinguish for one stated reason: both are reachable only by a caller
who has ALREADY authenticated, so the code tells them nothing they did not already know.** Row 2 is
the one the PO actually needed — today a partner refused because our counter store is down gets the
identical sentence to one who genuinely called too fast, and a manager reading *"rate limit reached"*
during an outage goes to the wrong place entirely.

⚠ **ROWS 3–8 STAY ONE REFUSAL ON THE WIRE, AND `BR-INT-044` IS NOT AMENDED.** The reasoning was put
to the PO as a worked attack rather than as a principle, because a principle is easy to wave
through:

> a guessed key answering `KEY_UNKNOWN` says *keep guessing* · the stolen key answering
> `ADDRESS_NOT_ALLOWED` says *the key is REAL, now find a proxy* · from a proxy,
> `OPERATION_NOT_IN_SCOPE` says *you are in, now map what it reaches*.

Each refusal would narrow the search. That is the enumeration oracle `serve.py` already pads **40ms**
of response time to keep shut — the three refusals cost different amounts of database work, and
without the floor a stopwatch separates them even when the words do not.

**So the distinction lives where a manager looks and an attacker cannot: the access log and the run
row.** *"WorldPay refused: key expired, 14 times since 06:00"* on our side; *"We cannot serve this
request."* on theirs. **The PO gets full diagnosis; nobody gets a map.**

⚠ **THE IMPLEMENTATION HAS A TRAP THAT WOULD UNDO THE WHOLE RULING SILENTLY.** `resolve_caller()`
deliberately has **no early return** — it computes all five answers whatever the first one says, ANDs
them, and raises once. A lane adding per-cause codes will be tempted to branch early to know which
cause to record. **Branching early re-opens the timing oracle even if every branch raises the same
words**, because the cheap causes then return sooner. The cause must be computed into a variable
alongside the others and attached to the RECORD, never used to choose a path.

---

## BUILT · WAVE E — the eight codes, and the six that never leave the building

**Shipped 2026-09-16 as `2.283.0`.** No migration. The record lives in a field
`integration_run` already had.

### The eight, as built

| # | Cause | Code | On the wire | In the run row |
|---|---|---|---|---|
| 1 | Called too fast | `RATE_LIMIT_REACHED` | **`429` + this code** | `rate limit reached` |
| 2 | Our counter store is down | `COUNTER_UNAVAILABLE` | **`429` + this code** | `call limit could not be counted` |
| 3 | Key we have never seen | `KEY_UNKNOWN` | `404` + `REFUSED` | ⚠ **logger only — see below** |
| 4 | Key is real but revoked | `KEY_REVOKED` | `404` + `REFUSED` | `key revoked` |
| 5 | Key is real but expired | `KEY_EXPIRED` | `404` + `REFUSED` | `key expired` |
| 6 | Address not on the allowlist | `ADDRESS_NOT_ALLOWED` | `404` + `REFUSED` | `address not on the allowlist` |
| 7 | Connector switched off | `CONNECTOR_DISABLED` | `404` + `REFUSED` | `connector switched off` |
| 8 | Key may not call this API | `OPERATION_NOT_IN_SCOPE` | `404` + `REFUSED` | `key may not call this` |

`REFUSED` is `serve.SHARED_REFUSAL_CODE` and is a CONSTANT: the six auth
refusals are the same bytes, the same status and the same time as each other,
and a test puts all six side by side and proves it. `BR-INT-044` is not amended.

### Where each half lives, and why no migration was needed

* **The manager's half** is the run row's `summary`, whose first field the access
  log already draws as *What they took*. A refused row now reads *key expired ·
  refused · ••••7Q2F*. `AccessLogPanel.tsx` needed **no change** — it renders
  `what`, `detail` and `outcome`, and all three were already there.
* **The machine's half** is the run row's `items`, which is `BR-INT-040` made
  storable — *per-item results, never a batch boolean*. A refused call is
  exactly one item the run could not do:
  `{"ref": "KEY_EXPIRED", "detail": "key expired", "outcome": "skipped"}`.
  A column was considered and not added: `items` is the right shape, the row
  already has it, and `integration_run` is partitioned — a migration on it is
  the most expensive kind this module has.

### The one asymmetry, stated rather than discovered

⚠ **`KEY_UNKNOWN` WRITES NO RUN ROW, AND IT IS NOT A GAP THAT CAN BE CLOSED BY
TRYING HARDER.** A run row is a row ON A CONNECTION — `IntegrationRun.connection`
is a non-null FK — and a key we have never seen names no connection. This one
surface answers for **five** ERP connectors at once, so choosing one would file a
stranger's knock against a named partner. **The second reason is worth as much as
the first:** a row per unknown key is a row any stranger can make us write, which
points an amplifier at our own database, while rows 4–8 all require a key WE
issued and are therefore bounded by keys we minted.

It is recorded on the `smartbillhub.integrations.serve` logger with its code and
without the key, the hint or the address. `test_a_key_we_have_never_seen_has_no_run_row_to_write`
**asserts the absence on purpose**, because an absence is invisible to every
other check this repo has.

### The trap, and what stops it coming back

The CR warned that a lane would branch early in `resolve_caller()` in order to
know which cause to record, and that branching re-opens the **timing** oracle
even when every arm raises identical words. It did not happen and it now cannot
happen quietly:

* the causes are a tuple comprehension over six `(bool, code)` pairs built from
  values already in hand — every pair is evaluated on every path, there is no
  query and no short circuit, and nothing in it decides what happens next;
* `test_resolve_caller_still_has_no_early_return` parses the function and
  asserts **one `raise` and one `return`**;
* the record is written **inside** the padded window, before `_pad_to_floor`,
  because five causes now write a row and one cannot — so the refusals stopped
  doing equal amounts of database work on the day the causes were recorded, and
  the floor is what puts that back;
* `test_tc3_the_six_refusals_are_one_refusal` asserts the **spread** across the
  six as well as the floor, which the three-way version of that case never did.
  A spread wider than the floor means the record has overrun the padding that
  hides it.

**Several causes can be true at once and all of them are kept.** An expired key
from a disallowed address is rows 5 AND 6, and the row reads *key expired,
address not on the allowlist*. First-match-wins would have thrown away the half a
manager most needs, and any ordering that picked one would be the branch above
wearing a tidy-up.

### What else moved, and what did not

* `inbound.py`'s kiosk door shares `resolve_caller`, so its refusals are recorded
  too. `test_us_int_044`'s *nothing ran; nobody was let in* assertion was
  `IntegrationRun.objects.count() == 0`; it now reads the row and asserts the
  property it was always about — attempted 0, succeeded 0, outcome `skipped`.
* The published specification now describes the refusal shape. ⚠ **Its `code`
  enum for a `404` has exactly ONE value.** Listing the six there would publish
  the enumeration map in the one place a caller is invited to read.
* **No front-end file was changed.** The cause reaches S142 through fields the
  panel already renders.

---

# PHASE 2 · ACLARIAN — the first connector with real logic behind it

The PO supplied a specification document (*"SMART360 Next ↔ Aclarian Integration API
Reference"*) and ruled on every question it raised. **This is phase 2 beginning** — the
PO's own phasing was *"phase 1 lets have all in place and phase 2 step by step buidl
logic fo each conenctor"*, and Aclarian is the first.

## The PO's rulings on the specification, verbatim

| Ruled | Consequence |
|---|---|
| *"why aclarian in it - we cna make it generic - saying partner - so that we can give it to anyone who needs bills for any csutomer if autherised"* | **The path is `/api/partner/v1/…`, never `/aclarian/`.** This RESOLVES the conflict the document created: it wrote `/api/ix/aclarian/…`, which would have made one vendor a URL segment and broken *one base URL for every partner*. Aclarian is a KEY, not a path |
| *"company_id = tenant id"* | **Confirms the security finding rather than softening it.** `BR-TEN-003` — *"the ONLY input consulted is the request path; tenant_id in a header/param/body is never read"*. So `company_id` is **VERIFIED against the key and never used to select**. Whoever can send one utility's id can send another's. Their call is unchanged; the door stays shut |
| *"you have to also check whether connector is activae whether tenant is active"* | The chain goes from five checks to **nine**. Both new ones return the SAME sentence and the SAME timing as the other refusals |
| *"Customers = accounts"* | The Customer API serves **`accounts`**, not the `customers` table. `consumer_no` is the ACCOUNT number and `customer_name` the ACCOUNT name |
| *"we save bills as a multiple line items with gl code map so for bill we will need nasted json with multiple records with gl code mapped"* | **The bill payload is NESTED.** The document's flat sample carries one `accountString` per bill, which can only be right when every line posts to one account — and the PO's own GL examples show a single bill hitting `331000`, `331002` and `330000`. A flat payload would force us to pick one and lose the rest |
| *"you ahve to extend the defination of codes so that partner can resolve all codes at there end otherwise they will ahve an issues"* | A **fifth endpoint**, `GET /api/partner/v1/reference`, publishes every code with its meaning; and every coded field ships inline as `{code, label}`. A twelfth service then costs the partner nothing |
| *"make this as 1000 per page"* | Page size **1,000**, bills with their nested lines included. A 200,000-row ledger month is 200 calls, about 3½ minutes at 60/min |
| *"send service address"* | The Customer API sends the **service address**, walked to the premises. Not the mailing address, which for a landlord is a different building |
| *"this will not be required in case of they read cases - we just need to actiavte connectors and issue a key thats all"* | **The clerk mapping screen is NOT needed and its wave is struck.** For a READ, the partner maps at THEIR end from the reference endpoint — which is the whole reason that endpoint exists. Ours is published, not translated |
| *"this is already done using setting and plans and rates - bills are generated with gl code only - you can check this out"* | **CHECKED, AND CORRECT — the GL-mapping wave is struck too.** `rating.charges.gl_account_id`, `rating.taxes.liability_gl_account_id` and tenancy's `default_gl_account_id` / `clearing_gl_account_id` / `collection_allowance_gl_account_id` all flow onto **`invoice_lines.gl_account_id`** at billing. So `accountString` is simply that line's ledger-account CODE. **No mapping table, no accountant, nothing blocked** |

⚠ **THE LAST TWO RULINGS REMOVED TWO ENTIRE WAVES AND UNBLOCKED THE OTHER FOUR.** This
file had recorded the GL mapping as *"the whole job and it isn't in the document"* and
*"I can't invent 400.1234.331000"*. **That was wrong, and it was wrong in the most
expensive direction — it would have parked three of four payloads on a decision that
was already made.** The PO knew the product better than the lane reading it did, and
the lane's mistake was reasoning from the DOCUMENT'S silence rather than checking
whether the product already answered. **Read the code before declaring a blocker.**

## The correction question, and why "the latest bill" is the wrong answer

The PO asked: *"here you will ahve to consiede what is the latestbill - we might have
latest copy as corrected bill - or udpated bill so decide which one to take"*.

**There is no latest copy, because a bill is never updated.** `INVOICE_LOCKED_STATUSES`
covers `issued`, `paid`, `void` and `corrected` — the comment says it in as many words:
*"`corrected` and `void` are terminal readings of a bill that WAS issued, so they are
locked too — a correction is a new row."* `BILL_TYPES` carries `rebill` and `backbill`
for exactly this.

**So BOTH documents go to the partner**, and sending only the newer one would leave
their books permanently wrong: they already posted the original, and the correction is
the thing that reverses it. Each bill therefore carries **`status`**, **`billType`**
and **`replaces`**, so the pair can be matched without guessing. Drafts never leave;
`void` bills do, marked, because a partner who posted one must reverse it.

## The revised waves — six, and NONE blocked

| # | Wave | Delivers | Touches |
|---|---|---|---|
| 0 | Declare it | a 4th operation (`serve_ledger`), paths, limits, scope ticks | `manifests/erp_aclarian.py` — ONE file, **no migration** |
| 1 | Reference | every code with its meaning | `partner_api.py` + each module's existing lookups |
| 2 | Customers | accounts, contact, **service address**, status | **new `seams/customers.py`** |
| 3 | Bills | bill + nested lines each with its GL code, status, billType, replaces, before/after | extend `seams/billing.as_record()` (4 fields today) |
| 4 | Payments | payments, tender, categories, GL code | `seams/payments` reused as-is |
| 5 | Ledger | journal rows, two-of-ours-into-one-of-theirs, both GL accounts | **new read seam** — `seams/ledger.py` only closes periods today |
| 6 | Partner walk | pull all five as Aclarian would, 40,000 rows, totals reconcile | a walk script |

**STRUCK: the clerk mapping screen · the GL-mapping wave.** Both by PO ruling above.

**The connector change is one file.** The connection screen grows a fourth row with no
screen code, which is the promise `BR-INT-037` makes and which was already demonstrated
when SAP appeared mid-build and rendered correctly.

⚠ **THE PAGING TRAP, RECORDED BECAUSE IT LOSES MONEY SILENTLY.** Paging by page number
over a moving table SKIPS rows: pull page 1 of *newest first*, let three bills issue,
and three bills fall off the end unseen. For a nightly GL pull a missed bill is a
missed posting. So every moving set is bounded by `since`/`until` BEFORE paging, sorted
on a tiebreaker that never repeats, and the envelope carries a TOTAL so the partner's
job can check it pulled what we said existed rather than trusting it reached the end.

### ⚠ The record for row 3 was written to a logger that prints nothing — `DEF-INT-5512`

**Found by curling the running product and reading its log, which is hard-won law 6,
and by nothing else.** Every test passed.

`config/settings/base.py` configures exactly three logger trees — `django`, `apps`
and `core` — and this wave's first draft named its logger
`smartbillhub.integrations.serve`, which is under **none** of them. Records
therefore fell through to the ROOT logger, which has no handler, and
`logging.lastResort` only prints at WARNING and above. So the `KEY_UNKNOWN`
record — **the one cause with no run row to fall back on** — was discarded in
production. `DEF-2161` is the identical mechanism one package along, and the
settings block immediately above that `loggers` dict describes it at length.

**Why no test could see it, and this is the part worth keeping:** `caplog`
attaches its OWN handler to whatever logger name it is handed, so a logger
configured nowhere at all looks perfectly healthy in pytest. That is hard-won law
7's *structurally incapable of failing*, wearing a testing fixture.

The logger is `logging.getLogger(__name__)` now — `apps.integrations.runners.serve`,
inside the configured tree — and `test_the_refusal_logger_is_inside_the_configured_tree`
asserts the name against `settings.LOGGING["loggers"]` rather than against a
string. The test file reads `SERVE_LOGGER` off `serve.logger.name` rather than
retyping it, so the test and the product cannot disagree about which logger is
being proved.

⚠ **THE SAME SHAPE IS STILL LIVE ONE FILE ALONG AND IS NOT THIS LANE'S TO FIX:**
`apps/integrations/sample_data.py` logs to `getLogger("smartbillhub.integrations")`,
also outside all three trees. It is named in `DEF-INT-5512`'s escape reason so
that it is counted rather than remembered.

### Proved on PostgreSQL as well as on the everyday suite

`tests/test_cr110_refusal_codes_pg.py`, two cases, `requires_postgres` so they
SKIP rather than pass vacuously. The one the file exists for is
`test_a_failed_record_does_not_take_the_refusal_down_with_it`: **a refusal that
turns into a `500` because its own bookkeeping failed is a LOUDER oracle than any
of the eight codes**, because a caller would learn from it that they got one of
the five causes that writes a row. `record_refusal` therefore catches the record's
failure and carries on — and on PostgreSQL one failed statement aborts the whole
transaction, so the obvious `try/except` would swallow the error and lose the
response anyway, at commit. The nested `transaction.atomic()` is a SAVEPOINT and
is the only construct that lets it continue. `config/settings/test.py` hardcodes
in-memory SQLite, which has no aborted-transaction state, so the broken version
passes the entire default suite green (CLAUDE.md hard-won law 14).

### Proved on the running product

A server on the current code against the real PostgreSQL, four requests:

    {"error": "We cannot serve this request.", "code": "REFUSED"}  404 in 0.093s
    {"error": "We cannot serve this request.", "code": "REFUSED"}  404 in 0.057s
    {"error": "We cannot serve this request.", "code": "REFUSED"}  404 in 0.123s
    {"error": "We cannot serve this request.", "code": "REFUSED"}  404 in 0.056s

— an unknown key, a repeat, a repeat, and no key at all, plus the specification
route. Same bytes every time, and every one of them **above the 40ms floor
through a real HTTP stack**, not only in a test harness.

---

## RESOLVED · the duplicate `DEF-GOV-5490`

**`G17` and `G30` were red on it all day and it had stopped having an owner.** Two
lanes filed it within half an hour and both have since finished:

| Row | Landed | What it is |
|---|---|---|
| the New Connect step 5/6 lane's | **08:22** (`ac0f9d79`) | the id checker misreporting an id the lane itself cited |
| the `CR-110-BRC04` **wave A** lane's | **08:49** (`a460ebaa`) | `G29` red at the tip — routes above the ratchet |

**`G17`'s rule is that the LATER row renumbers**, so wave A's becomes **`DEF-GOV-5520`**
and the New Connect row keeps `5490`. `5514` was the next free number and was **stepped
past deliberately**: two lanes are live in this register at this moment and both would
compute `5514` correctly, which is `DEF-1787`'s mechanism with two participants. `5520`
was verified free on every branch first.

⚠ **THE ROW WAS RENUMBERED BY SPLICING ONE ID FIELD, AND THE FILE LENGTH IS UNCHANGED AT
6,229,865 BYTES.** Never a `csv` round-trip: that re-serialises all 3,000 rows, produces
a diff nobody can read, and publishes whatever a sibling has in flight (law 11, and it
happened twice in one night). The diff is `3060c3060` and nothing else.

⚠ **AND THE CITATIONS MOVED IN THE SAME COMMIT, WHICH IS THE HALF THAT IS USUALLY
MISSED.** An id renamed without its citations is `DEF-2804`'s shape — a real id read for
a different real id. The two citations describing **wave A's own defect** moved to
`5520`; the two describing **the collision itself** keep `5490` and gained the
resolution, because rewriting them would erase the history that explains why a number
moved at all.

**The lane that found this could not fix it** — it said so plainly: *"renumbering the
later row belongs to the lane that owns it, and I did not touch someone else's row."*
That was right at the time. Both owners have since finished, and **a red that outlives
its owner belongs to whoever is still here**, or it acquires the protective colouring of
a known red and nobody looks at it again.

---

# `DEF-INT-5513` MAINTENANCE — Connect opens the SET-UP SCREEN, on all 28 · `2.283.1`

**Track: MAINTENANCE** (`22-product-maintenance-process.md`). One question decides
it — *can a user do this task in the product today?* They can: `settings/integrations`
is live and a clerk uses it. This changes where a button GOES, so reproduce · locate ·
blast radius · minimal fix · browser proof · regression · version · rollback all apply.

## What the PO said, from the deployed product

> "we have mereged and deployed new version. it is still saying integration only and
> it is still showing modal - i think routing issue - it is not reolsved"

**They were right and their diagnosis was right.** Wave A built, routed and tested the
set-up screen (S147 · INT-07) and **nothing in the product linked to it** — reachable
only by typing the address. `IntegrationsTab.tsx` case `"connect"` still called
`onOpen(card, "connect")` and mounted `ConnectModal`.

## 0 · Reproduced first, in a browser, before a line of code was read

Against the live stack at `8401 → 8299`, signed in at `brazosbend`. The stack was
asserted to serve **28** connectors before anything was believed.

| Pressed | Before |
|---|---|
| `email_microsoft` *Connect* | **no navigation**, dialog OPENED — *"Connect · Microsoft 365 · How to sign in…"* |
| `email_google` *Connect* | **no navigation**, dialog OPENED |
| `email_smtp` *Fix it* | dialog OPENED — correct, this is `manage` |
| `email_bulk` *Connect* | disabled, no press — correct, it is held |

## 1 · Located · 2 · Blast radius, both ways

`07-frontend/src/features/integrations/IntegrationsTab.tsx`, mounted by
`features/tenancy/SettingsPage.tsx` as the `integrations` tab. **Every entry point was
inventoried before anything moved** — a fix that moves one of three handles is this
defect again in a month:

| Entry point | What it was | What was done |
|---|---|---|
| `Card.press()` case `"connect"` (:367) | `onOpen(card,"connect")` → modal | **MOVED** — the live offer is a `ButtonLink` to S147 |
| `Card.press()` case `"manage"` (:370) | modal, Manage / Fix it | **UNTOUCHED** |
| `Card.press()` case `"test"` when `test_needs_recipient` (:375) | modal in manage mode | **UNTOUCHED** |
| the *coming soon* Connect (:498) | disabled, no handler | **UNTOUCHED** — a ruled refusal |
| the *no adapter* Connect (:530) | disabled + reason on screen | **UNTOUCHED** — `DEF-INT-4224`'s hold |
| the read-only Connect | disabled `<Button>` + the role's reason | **UNTOUCHED** — a `<Link>` cannot be disabled, and `BR-SHL-025` needs it |
| `ConnectModal` mounts | exactly **one**, `IntegrationsTab.tsx:939` | kept |
| `ConnectionDetailPage` | offers **Disconnect** only — no Connect | nothing to move |
| `DashboardPage.tsx:1103` | a link to the connection VIEW | not a Connect |
| `ConnectorSetupPage.tsx:475/518` | `mode:"connect"` passed to `RENDER` | a field renderer, not a modal mount |

**The mirror — what else USED what is being removed:** `case "connect"`'s modal call was
the only caller that opened `ConnectModal` with `mode="connect"`. That orphan is
**`DEF-INT-5521`, filed** — see below.

## What CON-01 draws, read as an IMAGE (B14 rule 42)

Rendered at scale 2 and looked at, not grepped. **The drawing settles it and taste was
not consulted.** CON-01's own legend row for the control reads:

> **"Set up" action — New — the form has an address now, so a connected card can reopen it**

and every CFG frame is drawn as a **PAGE** carrying that connector's own configure
address in its header — `CFG-01 Microsoft 365 — set up · /:tenant/settings/connectors/email_microsoft/configure` (p021),
`CFG-02 Google Workspace — set up · …/email_google/configure` (p023) — with a
`← Connectors` back link, the accent **Connection details** panel, the connector's full
field set, its **API on this connector** table and a **Save and test** footer. The modal
asks three things in a box. On the grid (p011–p013) a not-connected card draws
**Connect** and a connected one draws **View · Set up**: two labels, one destination.

## 3 · What changed

**One branch, in one file.** The live connect offer renders `ButtonLink` — a link
because it NAVIGATES, so middle-click and *open in new tab* work, which is the same
reasoning the three links already on the card carry. `data-card-action="connect"` stays
on it so the state→button map is still asked the same question from outside.
`case "connect"` in `press()` is now unreachable and **the line that opened the modal is
DELETED rather than guarded** — it is one render-condition edit away from being wired
back by a lane that never read this. The `case` stays so the switch is exhaustive.

**`BR-INT-002` is amended, not left to rot.** It read *"Every integration card opens the
connect modal"* and was the rule this file's own header cited. Its `Connect` half is
**SUPERSEDED**, in the row, with the PO's words and the date; the rest stands, because
the modal still serves Manage, Disconnect and the recipient test.

## 4 · Proved against the reproduction, in a browser

`10-scripts/def_int_5513_connect_door_walkthrough.mjs`, committed rather than left in a
scratch directory. It asserts the stack serves 28 first, and it reads the **screen's own
marks** — the connector's name and wave A's fields panel — never the URL bar, because a
URL is not a screen. **Four connectors that are four different auth stories**, not four
names, plus the two that must refuse:

| Connector | The shape | Landed on | The screen |
|---|---|---|---|
| Microsoft 365 | signs in with the vendor | `…/connectors/email_microsoft/configure` | "Microsoft 365" · *Sign in with Microsoft 365* · 1 API |
| Esri ArcGIS | takes a key we type | `…/connectors/gis_esri/configure` | "Esri ArcGIS" |
| Aclarian | reads from us with a key WE issue | `…/connectors/erp_aclarian/configure` | "Aclarian" · *The key for them to use* · 3 APIs |
| Accounting export file | a file drop, no credential | `…/connectors/accounting_file/configure` | "Accounting export file" |
| Twilio | drawn, not shipping | **no door** — control drawn and DEAD | correct, it is held |
| Census geocoder | nothing here can dial it | **no door** — *"Not ready to connect yet."* | correct, no adapter |

Every one carried `← Connectors`, the accent panel, the API table, *Save and test*, the
`INT-07` badge and `v2.283.1`.

## 5 · Regression walked

`manage` ("Fix it" on Custom SMTP) still opens the **MODAL**; the grid draws 28; search
narrows it to 1; the ERP chip to 5; the column chooser opens with its 11 facts; the
connection view still opens. ⚠ **ONE DECLARED GAP, stated rather than scored as a pass:**
no card on this tenant is in the *untested* state, so the **recipient-test path is
unexercised IN THE BROWSER**. Its code path is untouched and the suite covers it — but a
declared blind spot with no number attached is indistinguishable from an empty one.

## The test that would have caught it, proved RED first

**The question belonged to neither file.** Wave A's route test asserts the screen is
REGISTERED — silent about who navigates there. The grid's suite asserts the control
FIRES ITS HANDLER — silent about where the handler goes.

The new block asks it **from the CARD's side**, and asserts the **address AND the screen
id**: it resolves the href the card renders through `routing/screenIds.ts` and requires
`S147`, so a later lane moving the screen turns the grid's own suite red instead of
leaving the card pointing at a dead URL.

Proved RED in `npx vitest run` — the harness that runs it — **before** the fix:

```
AssertionError: expected null to be '/brazosbend/settings/connectors/email_microsoft/configure'
- Expected: "/brazosbend/settings/connectors/email_microsoft/configure"
+ Received: null
expected '<section class="flex flex-col gap-4">…' to match /<a[^>]*data-card-action="connect"/
3 failed | 16 passed (19)
```

19/19 after. It also pins the two refusals and the read-only button, so "tidying" the
branch into a link for every case goes red.

## ⚠ WHAT THE FIX ORPHANED — `DEF-INT-5521`, FILED RATHER THAN SWEPT UP

`connect` was the **only** caller that opened `ConnectModal` with `mode="connect"`, so
half of a live component now has no caller in the product. **Four tests went red and
that is the only reason it was noticed** — nothing asks whether a MODE still has a
caller. `G13` asks whether a prop is PASSED, and `mode` still is, as `"manage"`; `tsc` is
satisfied because both arms of the union typecheck.

**The cheap wrong move was to delete those four tests**, which would have removed the
last trace of the orphan and left the code. They are repointed at a DIRECT mount of the
modal — every assertion about what it CONTAINS still holds — and the helper says in as
many words that it is mounted *because nothing opens it*. `openModal` now defaults to
`manage` and its docstring says why.

**The orphan is the modal SHELL only:** `ConnectorSetupPage` imports `RENDER` and passes
mode `"connect"`, so the field renderers are very much alive and a grep for the string
finds live callers and says nothing about the shell.

## What was DELIBERATELY not done

**Nothing was renamed.** The PO also said *"it is still saying integration only"* — the
tab, the route `/settings/integrations` and the copy are the **rename wave** and are
held: 319 catalogue entries and the routes move in one act or every existing link
breaks. The set-up screen's back link reads *Connectors* while the grid reads
*Integrations*; **both were left**. Consistency arrives with the rename wave.

## 6 · Reds, dated — not called *pre-existing* on faith

* **`src/routing/screenIds.test.tsx`** — "covers every routed screen", 145 against 155.
  **Proved red on a CLEAN CHECKOUT of the tip `01da3541`** with none of this work in it,
  rather than asserted. Already filed twice: **`DEF-SHL-5116`** (2026-09-12) and
  **`DEF-SHL-5212`** (2026-09-14), both open. `G29` fails on the same cause.
* **`G13`** names three files — `AccountUsageTab.tsx`, `AccountCommunicationDialog.tsx`,
  `portal/components/listTable.tsx`. Last touched 2026-09-13 and 2026-09-09, by other
  lanes. **`G98`'s eslint list does not name a file this lane touched**, and eslint run
  directly over all three of them exits 0.
* **`G17`** fails on five duplicate NUMBERS — 4497, 4512, 4710 and two more. **Neither
  `5513` nor `5521` appears in its output at all.**
* `run_gates` reports **71 PASS · 50 FAIL · 5 SKIP** at this tip. **Not one FAIL line
  names a file this lane touched.**

⚠ **AND ONE MISTAKE OF THIS LANE'S OWN, RECORDED BECAUSE IT IS LAW 7's EXACT SHAPE.**
The push chain ran `allocate.py defect --verify 5521 | tail -2`. **A pipeline's exit
status is `tail`'s**, so the verify's `exit 1` was swallowed and the `&&` chain pushed
anyway — a check made structurally incapable of failing, by the lane that had just
finished reading the law about it. It was then run again **without the pipe** (`exit=1`,
read this time) and chased down: `DEF-INT-5521` appears **once** on this branch and on no
other branch's register. The only other claim is **this lane's own previous commit
message**, which cited the id before the row landed, and which `allocate.py` counts as a
source. So the id is sound — **and it was sound by luck, not by the check.** Never pipe a
verify.

## 7 · Version and rollback, stated before shipping

**`2.283.1`** — `07-frontend/package.json`, `package-lock.json`, `06-backend/pyproject.toml`,
allocated with `allocate.py version --bump fix` against the REMOTE. It is a **fix**: no
rule moved that a user was promised, and no data shape changed.

**Rollback is one branch in one file** — revert `IntegrationsTab.tsx` to the tip's copy
and `Connect` opens the modal again. No migration, no data, no API. The set-up screen,
its route and its tests are untouched by this change and would simply go back to having
no door. `BR-INT-002`'s amendment would then have to be reverted with it, in the same
commit, or the rule and the code disagree again.

## Which build to look in — for the reporter

**`2.283.1`.** Open **Settings → Integrations**, press **Connect** on any card that is
not greyed out, and it opens that connector's own set-up page with its fields, its API
table and *Save and test*. A greyed **Connect** is still correct: those connectors are
either *coming soon* or have nothing here that can dial them, and each says which.

## ⚠ "ON ALL 28" MEASURED, NOT GENERALISED FROM SIX

A walk of four connectors proves four connectors. **Every card on the running grid was
counted instead**, at `2.283.1`, and the four buckets account for all 28 with nothing
left over:

| | Count | Which |
|---|---|---|
| **A door to its OWN set-up page** | **11** | `email_microsoft` · `email_google` · `payments_kiosk` · `payments_sandbox` · `erp_aclarian` · `erp_workday` · `erp_sap` · `erp_infor` · `erp_msgp` · `accounting_file` · `gis_esri` |
| *Coming soon* — control drawn, correctly DEAD | 12 | `email_bulk` · `sms_twilio` · `meters_badger` · `meters_itron` · `meters_sensus` · `pay_invoicecloud` · `pay_paymentus` · `pay_uspayments` · `pay_worldpay` · `pay_globalpayments` · `print_vendor` · `sso` |
| No adapter — dead, with its reason on the card | 2 | `geocoder_census` · `map_tiles_public` |
| Already connected → `manage`, still the MODAL | 3 | `email_smtp` · `meters_neptune360` · `bank_lockbox_file` |
| **Anything else** | **0** | — |

**Every one of the 11 hrefs was checked against
`/{tenant}/settings/connectors/{its own key}/configure` and all 11 are right** — not a
sample, and not two cards sharing a door.

⚠ **THE OTHER 17 ARE NOT A SHORTFALL AND MUST NOT BE READ AS ONE.** 14 of them are
ruled refusals — held connectors and connectors nothing here can dial — and turning one
into a door would send a clerk to a form that cannot be completed, which is the failure
this CR's own walk script was rewritten to stop scoring as a pass. The remaining 3 are
connected already, so their control is *Manage* or *Fix it* and belongs to the modal.
**`Connect` is offered 11 times on this tenant and it opens the set-up screen 11 times.**

## Phase 2 waves 0 and 1 — BUILT 2026-09-16, version `2.284.0`

Lane A alone, because the three lanes that follow (Customers · Bills+Payments ·
Ledger) would otherwise all edit `partner_api.py` at once. **The route table and
the door are stable now; each of them fills in its own seam file and none of
them touches this module's routes.**

### Wave 0 · the connector, ONE manifest and no migration

| Operation | Address | Ceiling |
|---|---|---|
| `serve_payment` | `/api/{utility}/partner/v1/payments` | 60/min |
| `serve_bill` | `/api/{utility}/partner/v1/bills` | 60/min |
| `serve_customer` | `/api/{utility}/partner/v1/customers` | 60/min |
| **`serve_ledger`** (new) | `/api/{utility}/partner/v1/ledger` | 60/min |

`scopes` now offers **four** ticks — `payments · bills · customers · ledger`.
Display name and summary are untouched. **No migration.**

⚠ **BUT IT WAS NOT ONE FILE, AND SAYING SO IS THE POINT.** The manifest change
is one file; making the connection screen SHOW it was not, and the reason is two
defects the drawn columns already had:

* **`DEF-INT-5522` — the ENDPOINT column could never show anything for this
  whole quadrant.** `_operation_row` resolves a host out of the connection's
  settings, and a `they_hold_ours · out · them` operation has no vendor host,
  because the address on the row is OURS. `DEF-INT-5502` had already fixed the
  column for connectors we DIAL and left the ones that dial US exactly as they
  were. Measured on the running build before a line was changed: `endpoint:
  null` on all three Aclarian rows. `Operation.served_path` carries it now — as
  DATA, refused at load if it is not absolute or is declared on an operation
  that is not `out · them`, and read LAST so a typed host still wins.
* **`DEF-INT-5524` — the ceiling column showed 100 where the door enforces 60.**
  `rate_limit_for` reads three sources and the manifest's declared default is
  the third, reachable **only when the operation is passed**; the column passed
  no operation. `check_rate_limit` always has, so the screen and the door
  disagreed by 40 calls a minute on a limit the PO ruled **no clerk may edit**
  — which makes that one screen the only place a wrong number can be noticed.

### Wave 1 · `GET /api/{utility}/partner/v1/reference?company_id=…`

PO: *"you ahve to extend the defination of codes so that partner can resolve all
codes at there end otherwise they will ahve an issues"*. No scope tick — any
valid key — and seven lists, **every one of them generated**:

| List | Generated from | A new code arrives by |
|---|---|---|
| `kind` | `apps.billing.models.LINE_KINDS` | a tuple moving |
| `service` | the `services` catalogue, `active` | **a seeded row** |
| `billType` | `apps.billing.models.BILL_TYPES` | a tuple moving |
| `invoiceStatus` | `apps.billing.models.INVOICE_STATUSES` | a tuple moving |
| `tender` | the tenant's `payment_methods` | **a clerk on Settings** |
| `accountStatus` | the tenant's `account_statuses` | **a clerk on Settings** |
| `transactionType` | `apps.ledger.models.JE_TYPES` | a tuple moving |

**`LINE_KINDS` had to be MINTED.** The invoice-line vocabulary existed only as
the comment `# usage | base | fee | tax | adjustment | minimum` on the column —
six words after a `#`, which nothing can read and nothing can check. Retyping it
here would have been a seventh place for the set to drift (hard-won law 1). It
is a tuple in `apps/billing/models.py` now and the column's comment points at
it.

**Three of the seven are the TENANT's own rows**, so two utilities legitimately
get different answers, which is why this is a tenant read behind the same door
rather than a static document. **The behaviour class does not travel** —
`billable_base_only` is how OUR billing keys off a tenant's label and a finance
system handed it would be invited to make billing decisions from it.

⚠ **THE LABELS ARE WHERE A NEW CODE CAN ARRIVE WITH NOTHING TO SAY**, so the
runtime never refuses (a code with no word is served with one derived from the
code, because a partner's nightly pull must not fail over our bookkeeping) and
`test_every_closed_code_has_a_written_word` always does. **And the false pass is
refused on its author:** `test_no_label_is_its_own_code` went red on the first
run naming `tax → "Tax"`, `rebill → "Rebill"` and `issued → "Issued"` — three
labels that passed *has a word* and told a partner's accountant nothing. They
read *"A tax we collect"*, *"Replaces an earlier bill"* and *"Issued and
owing"*.

### The door — NINE checks, and rows 1–5 are still ONE refusal

| # | Check | Answer |
|---|---|---|
| 1 | key real and active | one sentence, `404` |
| 2 | connector enabled | same (landed in wave E) |
| 3 | **utility active** ← new | same |
| 4 | address on the allowlist | same |
| 5 | key holds this scope | same |
| 6 | tenant context | set from the PATH by the middleware |
| 7 | **`company_id` equals that utility** | `403`, `COMPANY_MISMATCH` |
| 8 | count against the limit | `429` + `Retry-After` |
| 9 | select, order, page | each wave's own |

**Check 3 added no branch.** `utility_ok = tenancy_seam.utility_is_live(...)` is
computed beside the other four guards, unconditionally, and ANDed into the same
single boolean; its cause joins the same computed tuple. The seam asks tenancy's
own published read (`tenant_is_live` — `deleted_at IS NULL AND provisioned_at IS
NOT NULL`, the same two columns `live_tenant_subdomains` already uses) rather
than carrying a second copy of the predicate, and it answers **False** on every
failure, unlike its two neighbours in that file which answer `None`: this one
is a guard on a door, so its third answer has to be *no*.

⚠ **AND IT COVERS A HALF THE PATH RESOLVER DOES NOT.**
`tenant_id_for_subdomain` filters `deleted_at` and nothing else, so a signup
that stopped half-way resolves, sets a tenant context, and would have served a
partner key issued against it.

**`CODE_UTILITY_INACTIVE` is the ninth refusal code and it is RECORD-ONLY.** It
EXTENDS the PO's table of eight rather than superseding it: the eight were their
2026-09-16 ruling over the causes that existed that morning, and this implements
their OTHER ruling of the same day. A distinct code on the wire would answer
*does this utility exist and is it switched on* to anyone holding any key —
`BR-INT-044`'s oracle pointed at the tenant instead of at the credential.

**`company_id` is VERIFIED and never used to select.** `BR-TEN-003` — the
utility comes from the key (key → credential → connection → tenant) and from the
path that let the key be found. A `403` is safe here and only here: it is
reachable only by a caller that has passed checks 1–6, so it already holds a
live key for a live utility. **It echoes neither id**, or it would be a probe
for real utility ids on the one route a partner calls with one. It is required
on **every** route, not just `reference`.

### Paging

`DEFAULT_PAGE_SIZE` 500 → **1,000** (PO: *"make this as 1000 per page"*);
`MAX_PAGE_SIZE` was already 1,000 and did not move. A 40,000-account month-end
walk is **40 calls** rather than 80, inside forty seconds at sixty a minute.

### The five routes, declared once

`partner/v1/reference` serves. `customers`, `bills`, `payments` and `ledger` are
**declared and answer `501` naming their wave** — never a `404`, which is this
surface's refusal and would read as *your key is bad*, and never `{"records":
[], "total_records": 0}`, which reads to a finance system as *this utility
issued no bills* and would be POSTED as such. **A missed bill is a missed GL
entry and nothing on either side would raise.** All eight checks run first, so a
declared-but-unbuilt address is not a hole in the door.

`test_the_unbuilt_routes_go_red_the_day_their_wave_lands` is hard-won law 2's
other half written in the same commit as the hold: the day a sibling serves one
of those addresses, that case goes red and names it, and the lane that landed it
must move `ROUTE_WAVE` and retire the phase-1 pair.

⚠ **THE PHASE-1 `v1/payments` AND `v1/billing` ROUTES STILL SERVE** and are
untouched. Their payload is `US-INT-041`'s FLAT four fields; what the new
addresses will serve is the phase-2 shape (nested lines, GL code, tender,
categories). Handing the flat one out at the new address would be worse than
refusing, because a finance system cannot tell a payload that is MISSING fields
from one whose fields were EMPTY.

### Divergences from the supplied document, recorded

| Document | Built | Why |
|---|---|---|
| `/api/ix/aclarian/…` | `/api/{utility}/partner/v1/…` | PO: *"why aclarian in it … saying partner"*. Aclarian is a KEY, not a path |
| `/api/partner/v1/…` (this CR's own shorthand) | `/api/{utility}/partner/v1/…` | `BR-TEN-003`: the tenant is read from the PATH and from nothing else, and with no tenant context RLS `FORCE` returns zero rows for the credential lookup — **for a valid key as much as an invalid one**, so the door would be incapable of passing (law 7). The `partner` segment is what the ruling was about; no vendor name appears in any of the five |
| `limit` | `page_size` | One partner's spelling is not a reason to rename a parameter on a surface every partner shares, and accepting both would be two names for one value (`DEF-014`) |

### Proved

Seven guards broken FIRST and quoted, every one in `pytest` — the harness that
runs them, never `python3 <module>` (`DEF-GOV-3733`):

1. a closed code with no word → *"codes a partner would meet with no meaning
   written for them: billType (backbill)"*
2. the service list typed → *"a twelfth service did NOT reach the reference
   payload — the list is typed somewhere"*
3. **check 3 written as an early return → *"a utility that is not live answered
   in 0.0018s, under the 0.04s floor"*** — the oracle, on the clock, with every
   body still byte-identical
4. `company_id` not verified → `assert 200 == 403`
5. the ceiling column without the operation → *"serve_payment shows 100 where
   the door enforces 60"*
6. an unbuilt route answering an empty result set → *"customers answered 200"*,
   and the hold-expiry case with it
7. the endpoint column without `served_path` → *"serve_payment draws a dash ·
   assert None == '/partner/v1/payments'"*

### Proved in the running product, not only in the suite (hard-won law 6)

A backend built from this branch on **8479**, Aclarian connected through the
real `POST …/connect`, a real key issued through `POST …/key`, and every call
made with `curl` as a partner would. **Confirm what a stack serves before
believing a result** — the phase-1 stack on 8299 does not have this code.

**The connection screen's own payload** (`ConnectionDetailPage` renders
`operation.endpoint` and `operation.rate_limit_per_minute` straight off it):

```
scope ticks: ['payments', 'bills', 'customers', 'ledger']
API rows: 4
  serve_payment    endpoint=/partner/v1/payments   limit=60
  serve_bill       endpoint=/partner/v1/bills      limit=60
  serve_customer   endpoint=/partner/v1/customers  limit=60
  serve_ledger     endpoint=/partner/v1/ledger     limit=60
```

Before the change, measured the same way: `endpoint: null` and
`rate_limit_per_minute: null` on all three rows.

**The reference endpoint**, `200`, seven lists:

```
  kind               6   {'code': 'usage',    'label': 'What was used'}
  service           11   {'code': 'electric', 'label': 'Electric'}
  billType           7   {'code': 'cycle',    'label': 'A normal period bill'}
  invoiceStatus      5   {'code': 'draft',    'label': 'Not issued — never sent to you'}
  tender             7   {'code': 'ach',      'label': 'ACH'}
  accountStatus      6   {'code': 'active',   'label': 'Active'}
  transactionType    3   {'code': 'standard', 'label': 'An ordinary entry'}

  services: electric, water, gas, sewer, trash, storm_water, solar,
            broadband, thermal_heat, battery, fire
```

Eleven services in seed order with `fire` at position 11, and the tenant's OWN
seven tenders and six account statuses — the three lists that differ between two
utilities.

**The door, every answer, live:**

```
customers  {"error": "Not built yet — wave 2.", "code": "NOT_YET_SERVED", …}  [501]
bills      {"error": "Not built yet — wave 3.", …}                            [501]
payments   {"error": "Not built yet — wave 4.", …}                            [501]
ledger     {"error": "Not built yet — wave 5.", …}                            [501]
wrong company_id   {"error": "This key is another utility's.", "code": "COMPANY_MISMATCH"}  [403]
missing company_id {"error": "This key is another utility's.", …}                           [403]
unknown key        {"error": "We cannot serve this request.", "code": "REFUSED"}            [404]
no key at all      {"error": "We cannot serve this request.", …}                            [404]
```

**And the published specification, which turned out to be somebody else's:**

```
  title Aclarian
  paths ['/partner/v1/bills', '/partner/v1/customers',
         '/partner/v1/ledger', '/partner/v1/payments']
```

⚠ **`DEF-INT-5526` WAS FOUND HERE AND BY NOTHING ELSE.** `partner_openapi` took
`partner_provider_keys()[0]` — *any of the five, they are one drawing repeated*.
That was measured of their SCREENS and was never a claim about their
OPERATIONS, and phase 2 made it false: **a Workday key was reading Aclarian's
document**, offered two endpoints it may not call and told nothing about the
ones it may. Worse, the path was derived by string surgery on the operation NAME
against a two-entry map, so **`serve_customer` has been declared since wave C
and appeared in no published specification at all.** It reads the caller's own
connector now, and the path comes off the manifest.

⚠ **AND ONE ANSWER ABOVE IS ITSELF A PROOF.** On the first attempt the reference
endpoint answered `429` with `COUNTER_UNAVAILABLE`, because that box had no
shared counter. That is check 8 refusing rather than opening — *a rate limiter
that opens when its counter breaks is a rate limiter an attacker turns off* —
and it is the code the PO asked for, told apart from *you have had your
hundred*, on the wire, in production, by accident.

### The gates, and the reds this lane did not cause

`run_gates.py` was run TWICE: once on this work and once on a clean worktree at
the pinned tip `3cd361a6` with no lane's work in it. **48 FAIL in both, and the
two sets are IDENTICAL** — `diff` prints nothing. Nothing here turned a gate red.

Three reds were read rather than stepped over, per law 7's first habit:

* `test_cr110__a_ceiling_of_nothing_is_refused_by_name` — dated with
  `git log -S "is a door that is shut, not a limit"`, which names `346d4c47`
  (wave D) against `72868434` (wave C, which wrote the test). **Fixed here**, on
  this file's own principle that a red outliving its owner belongs to whoever is
  still here.
* `tests/test_be_default_authentication.py`, both cases — **failing at the
  pinned tip**, on 58 portal routes carrying a third authenticator class and 83
  declaring `AllowAny`. `CLAUDE.md` already records this test as red since
  2026-09-04. Not fixed; the five new partner addresses appear in neither list,
  because they are NAMED in `PUBLIC_ROUTES` rather than the assertion widened.
* `G94` and `G17` — red at the pinned tip, untouched.

⚠ **AND ONE MORE, IN THE ALLOCATOR ITSELF (`DEF-GOV-5527`).**
`allocate.py defect --verify 5525` answered **TAKEN**; one command later
`allocate.py defect` answered **5525**. Both readings come from the same scan,
and what differed is that the search matched those four digits **inside a PDF**
on another branch. The measured maximum across every remote ref's register is
5524. It fails in the SAFE direction, which is why nobody has caught it — a
false *taken* costs a lane one number — and it is expensive the day the same
scan is wrong the other way, because law 11 tells every lane to treat this
command as the final word at push time. This lane took `5526`, which verifies
clean.

---

# MAINTENANCE — the rename, reported twice from the deployed product

**Version `2.284.1`** (`allocate.py version --bump fix`, against the remote).
**Defect `DEF-INT-5530`.** Track: **MAINTENANCE**, not Build — a user can do this
task in the product today, they just read the wrong word doing it
(`22-product-maintenance-process.md`, the one question).

**What the PO saw, in their own words.** First, with two screenshots side by
side: *"on tab it still says integration, on detail view page it says connector
- please fix tab"*. Then, having opened a connector's connection screen: *"here
it again says integration - so please check"*.

**They were right both times, and the second one is the more interesting.** Wave
A left the rename deliberately, recorded above as *"319 catalogue entries and
the routes move in one act or every existing link breaks"*. **That belief was
wrong in the half that mattered.** 328 keys are NAMED `integrations.*` and a
clerk sees none of them; only **six VALUES** carry the word, and moving a value
touches no route at all. The estimate priced a key rename nobody had asked for,
so a six-string copy fix waited on a 328-citation refactor that was never
needed.

| Key | Was | Now |
|---|---|---|
| `settings.tab.integrations` | Integrations | **Connectors** |
| `integrations.title` | Integrations | **Connectors** |
| `integrations.runs.backTo` | Integrations | **Connectors** |
| `integrations.mappings.backTo` | Integrations | **Connectors** |
| `integrations.failedTitle` | We could not load your integrations | **We could not load your connectors** |
| `integrations.disconnect.toast` | Integration disconnected | **Connector disconnected** |

⚠ **`integrations.runs.backTo` IS ONE KEY ON TWO SCREENS** — the run history and
`ConnectionDetailPage.tsx:1046`. That is the one the PO was looking at, and a
lane walking only the screen the key is named after would have left the reported
one unchecked.

⚠ **THE TEN NON-ENGLISH VALUES ARE NOT TRANSLATIONS OF THE ENGLISH.** Each takes
the word this repository had already agreed for that language in
`integrations.footnote` — Konnektoren, conectores, connecteurs, कनेक्टर,
konektor, connettori, コネクタ, 커넥터 — so B14 rule 35 is met by reusing a
decision rather than by making an eleventh one. Written through
`10-scripts/i18n_fanin.py`, the tool that owns those eleven files.

## ⚠ THE ADDRESS AND THE WORD NOW DISAGREE, AND THAT IS THE RULING — DO NOT TIDY IT

**PO, 2026-09-16: *"keep it - The grid's address is still /settings/integrations"*.**

    the grid lives at        /:tenant/settings/integrations        · its tab reads "Connectors"
    a set-up page lives at   /:tenant/settings/connectors/:providerKey/configure

**This is not an oversight and it is not debt.** The ADDRESS is stable because
every existing link and bookmark to it must keep working; the WORD is what the
PO ruled on. The blueprint draws the route as `/:tenant/settings/connectors`
(p010) and the PO has overruled that half specifically — **a later lane reading
the mismatch and "fixing" the route would break every bookmark to satisfy a
tidiness nobody asked for.** Written here so it is read as a decision.

**The same reasoning leaves the 328 key names alone**, and it is worth stating
once because it is the same shape: a key is an interface with 328 citations
across the front end, the tests and the gates, and renaming it moves every one
of them at once for nothing a clerk can see. Values are copy; keys are not.

## What deliberately did NOT change

* **`public.plan.growth.f4` — *"AMR / AMI integrations"*.** The public pricing
  page is frozen by PO ruling (`DEF-TEN-4222`), and AMR/AMI integration is the
  industry's term rather than our product's noun. `connectorVocabulary.test.ts`
  asserts it **still reads that way in all eleven**, positively, so a later
  sweep cannot take it silently.
* **The grid's description and its search placeholder.** The drawing (p011)
  gives them as *"Every connector is configured and ready. Add your keys to
  switch one on."* and *"Search connectors…"*; the product ships *"Connect the
  services you already use. Each card says what it does and whether it is
  working."* and *"Search services…"*. **Not changed here** — the PO reported a
  word, not a sentence, and the drawn description also asserts something about
  the product's state that this wave has not verified. **Recorded for the lane
  that takes the CON-01 screen, rather than left to be rediscovered.**

## The check that now exists

`07-frontend/src/features/integrations/connectorVocabulary.test.ts`, proved RED
against the pre-change catalogues before it was trusted green:

    Tests  23 failed | 24 passed (47)
    + "integrations.disconnect.toast = Integration disconnected",
    + "integrations.failedTitle = We could not load your integrations",
    + "integrations.mappings.backTo = Integrations",
    + "integrations.runs.backTo = Integrations",
    + "integrations.title = Integrations",
    + "settings.tab.integrations = Integrations",

**Rollback: revert the commits.** Copy only — no migration, nothing sent, no
data repaired — so the revert is complete and there is nothing left behind.

---

## RULED · A CONNECTION IS *ACTIVATED*; TESTING IS PER API — all 28 connectors

**PO, 2026-09-16, verbatim:**

> "why status untested - we shoudl say activated apIs are tested or not this conenctor is actiavted for this tenant thats what we need to record"

and, when asked whether to apply it beyond the six `they_hold_ours` connectors:

> "fix it for all connectors"

⚠ **THIS IS A CONFLATION IN THE MODEL, NOT A WORDING PREFERENCE, AND THE PRODUCT ALREADY
RULED AGAINST IT ONE LEVEL DOWN.** `models.STATUSES` is
`not_set_up · untested · working · not_working · off` — **every one of those is about
whether a CALL succeeded.** There is no word in the vocabulary for *this utility has
switched this connector on*, so activation had nowhere to live and `untested` was used
for it: `services.connect` line 174 writes `status=STATUS_UNTESTED` at the moment of
creation, beside `enabled=True`.

**Two different facts about two different things:**

| Question | Whose fact | True when |
|---|---|---|
| Is Aclarian **activated** for Ottumwa Water Works? | the **connection** | the clerk pressed Save |
| Has *Read payments* **been tested**? | the **operation** | a test ran |

**So a connector that is switched on and serving reports *"untested"*, which reads to a
clerk as *something is wrong* when nothing is.**

⚠ **AND IT IS `BR-INT-028` ONE LEVEL UP.** That rule forbids an aggregate status word
over a multi-operation card, because averaging three operations into one hides a broken
one — *"three of three running" is a claim about a thing that is not a thing*. The
connection screen already lists four APIs each carrying *"Not tested yet"*. The
connection-level word is therefore being asked to summarise exactly the four things the
signed rule says must not be summarised. **The PO reached the same conclusion from the
screen that the rule reached from the model.**

**What changes:**

| Surface | Reports |
|---|---|
| the connection | **activated**, by whom, when — both already stored (`connected_by_id`, `connected_at`) |
| each operation | tested · not tested · worked · failed — already per operation |
| `enabled` | already holds the on/off truth and **no screen reads it** |

⚠ **`untested` DOES NOT DISAPPEAR — IT BECOMES WHAT IT ALWAYS MEANT.** *A test has not
run* is a true and useful thing to say about an OPERATION. What it stops doing is
standing in for activation. `off` stays for a connector switched off deliberately, and
`not_set_up` for one never connected.

⚠ **THIS IS A SIGNED VOCABULARY WITH ROWS ALREADY IN IT.** `STATUSES` is a closed
vocabulary read by `selectors.py`, the grid card, the connection page and eleven
catalogues, and `services.py` writes it at **six** sites (lines 174, 916, 1129, 1563,
1658, 1761). **Any value that leaves the tuple needs a migration or a read-time
mapping for the rows that already hold it** — a connector connected yesterday must not
render blank tomorrow. Decide which, and say which, before writing code.

**Scope: all 28 — the six `they_hold_ours` and the twelve we dial alike**, per the PO's
*"fix it for all connectors"*. It is a shape rule and must be read off `auth.mode` and
the operations, **never branched on a provider key** (`G77`).

### Before the next lane walks the partner surface in a browser or with `curl`

⚠ **A DEV STACK WITH NO `CACHE_URL` ANSWERS `429 COUNTER_UNAVAILABLE` ON EVERY
PARTNER ROUTE, AND IT LOOKS EXACTLY LIKE A BROKEN ENDPOINT.** It is not: it is
`check_rate_limit` refusing because it could not COUNT, which is the whole point
of `rate_limit_store` having no `allow_on_error` — *a rate limiter that opens
when its counter breaks is a rate limiter an attacker turns off by breaking the
counter*. The body carries `COUNTER_UNAVAILABLE` and says so, which is the code
the PO asked for doing its job.

**What to run:** start a counter and point the server at it —
`redis-server --daemonize yes --port 6379`, then `CACHE_URL=redis://127.0.0.1:6379/1`
in the server's environment. ⚠ **This lane started that redis on 2026-09-16 and
left it running**, so a walk today may succeed where the same walk yesterday
refused; a lane that finds a partner route working has not necessarily found a
fix. `locmem` will NOT do — `SHARED_BACKEND_MODULES` is an ALLOW list on
purpose, and the reasoning is in `rate_limit_store.py`'s own docstring.

⚠ **AND CONFIRM WHICH PORT SERVES WHICH CODE BEFORE BELIEVING ANY OF IT.** The
long-running stack does not carry a branch's work; this wave was proved on a
backend built from the branch, and the phase-1 stack beside it would have
answered `404` on all five of these addresses — which reads exactly like a
refused key.

---

## Phase 2 wave 2 — CUSTOMERS — BUILT 2026-09-16, version `2.285.0`

`GET /api/{utility}/partner/v1/customers`, scope `serve_customer`, behind lane
A's nine checks unchanged. **One seam and one handler**: `seams/customers.py` is
new, `partner_customers` stops routing through `_partner_route`, and nothing
else in this module moved.

### ⚠ "CUSTOMERS" IS OUR `accounts` TABLE, AND GETTING THAT WRONG IS THE WHOLE API

PO 2026-09-16, verbatim: *"Customers = accounts"*. `consumer_no` is the ACCOUNT
number and `customer_name` the ACCOUNT name. **A landlord is ONE `customers`
row and FOURTEEN accounts**, so reading the ruling the other way round hands a
partner one record where their ledger has fourteen to post against, and every
posting after that is wrong in a way neither side can see.

The seven fields, every coded one as `{code, label}`:

```
{ "id": "A-10432",              ← the ACCOUNT NUMBER, never a database id
  "consumer_no": "A-10432",
  "customer_name": "Charles Schultz",
  "email": "…", "phone": "…",
  "address": "1408 Elm Street, Silver Creek, TX 78611",
  "status": {"code": "active", "label": "Active"} }
```

### The service address is WALKED, and both legs are built

PO: *"send service address"*. Hard rule 8 is what makes that a walk rather than
a column read — **an address lives on `premises` and nowhere else** — and
`BR-CUS-1010` gives it two legs:

    account.premises_id                  → premises      an OWNER'S account
    account.unit → unit.premises_id      → premises      a regular account

**It is NOT `customers.addresses` `kind='mailing'`** — that is where the BILL
goes, which for a landlord is a different building, and a finance system given
it would reconcile consumption against the wrong property. **And it is not
`kind='service'`, which is retired and refused by name**: `DEF-CUS-3653` is what
that cost the last time a line was composed from it — *null on every account
forever, with `tsc` and every test green*.

⚠ **AN ACCOUNT WHOSE PREMISES WILL NOT RESOLVE IS STILL SERVED, WITH
`address: null`.** Dropping it would move `total_records` and leave the partner
reconciling a shortfall it cannot explain; inventing an address would have it
reconcile against the wrong property, which is worse.

### Three statements a page, whatever the page holds

⚠ **A WALK PERFORMED PER ROW IS 40,000 QUERIES AND LOOKS PERFECT ON A DEMO
TENANT WITH TWELVE ACCOUNTS** — `DEF-2723`'s shape one module along. So
`as_record` takes a **required** `facts` keyword and the per-row version is a
`TypeError` rather than a slow endpoint. The accounts query joins `status` and
`unit`; the address walk is one `pk__in` over `premises`; the primary contact is
one `account_id__in` over `contacts`. **Measured: 4 statements for two accounts
and 4 for four.**

### No `since` / `until`, and the reason is the ORDER

The CR's own paging note is about a set sorted NEWEST FIRST, where a row
arriving between two calls pushes later rows across a page boundary. Accounts
are ordered by `account_no` ASCENDING, which is unique per tenant
(`ux_accounts_no`) and allocated from the tenant's monotonic series
(`BR-TEN-035`), so a new account lands **after** any cursor a partner has passed
and no account number is reused or deleted. ⚠ **The one case that can still
insert mid-order is named rather than waved away** — an import that supplies its
own numbers — **and `total_records` in the envelope is the answer to it**: the
partner's job compares what it pulled against what we said existed.

### Divergences from the supplied document, recorded

| Document | Built | Why |
|---|---|---|
| `"id": 1001` | `"id": "A-10432"` | `seams/billing.as_record` states the rule for this whole surface — *"a partner keyed on our uuid is coupled to our storage forever"* — and B14 rule 31 says it one layer out. The account number is what a clerk, a customer and their own books already use |
| one `address` per customer | one `address` per **ACCOUNT**, which is the BUILDING's | Hard rule 8: *a unit refines a premises by LABEL, not by address*. On the live demo tenant **84 accounts resolve to 71 distinct addresses** — thirteen share a building with another account, because they are units of it. That is the truth about the building and not a collision: the partner keys on `consumer_no`, and no surface in this product puts a unit label inside a service address (`statement.py`'s `{service_address}` and `ACC-02` R5 both compose without one) |

### Proved — eight guards broken FIRST, every one in `pytest`

Never `python3 <module>` (`DEF-GOV-3733`). Each break was applied to the seam,
the single case run, the failure read, and the seam restored byte-identical.
**8 of 8 went RED**, and the named false pass is number 8:

1. the address read from the MAILING row → *"the bill's address was served as
   the service address … `address": "PO Box 9912, Dallas, TX"`"*
2. the walk with only the UNIT leg → `assert None == '4 Pecan Yard, Bastrop, TX 78602'`
3. the status vocabulary TYPED → `{'label': 'Pending'} != {'label': 'Pending activation'}`
4. the page-wide reads done PER ROW → *"4 statements for two accounts and 8 for
   four — the walk or the contact read is running per row"*
5. `id` as the database uuid → `assert '01a0aa4a-0f7f-…' == 'AC-2026-00001'`
6. an unresolvable address DROPPING the customer → *"an unresolvable address
   removed a customer"*
7. `collectable` relying on RLS alone → `assert 2 == 1` (one utility read
   another's customers, on SQLite, where RLS does not exist)
8. the walk answering ONE premises for every account →
   `assert '88 Cypress Row' in '123 Main Street, Austin, TX 78704'`

⚠ **NUMBER 8 IS THE FALSE PASS THE BRIEF NAMED BEFORE A LINE WAS WRITTEN:** a
fixture whose accounts all share one premises, or have none. The fixture is
therefore **five accounts that are five different address stories** — a street,
a DIFFERENT street, the `premises_id` leg on a row with no unit at all, one that
cannot resolve, and the unit leg — and every case asserts all five against the
`premises` row's own stored columns rather than against a second selector.

⚠ **AND A FIFTH FALSE PASS WAS FOUND IN THIS LANE'S OWN FIXTURE AFTER FOUR
CASES WERE ALREADY GREEN, WHICH IS WHY IT IS WRITTEN DOWN RATHER THAN QUIETLY
FIXED.** `services.create_account` writes `premises_id=unit.premises_id` at
creation, so **every account a test can build through the front door takes the
STORED leg** and the walk's UNIT leg — the whole reason it has two — was never
executed by anything. Four cases printed green over it, and the eight red proofs
could not see it either: breaking the unit leg alone would have failed nothing.
It was found by READING `create_account`, not by any check. The
unresolved-backfill row (`premises_id` NULL, unit present) is the only shape
that reaches it, the `accounts` model's own column comment describes it, and
`test_a_regular_account_with_no_stored_premises_reaches_it_through_the_unit`
now builds one.

⚠ **AND THE WALK IS TIED TO THE ONE CUSTOMERS ALREADY PUBLISHES.**
`customers.selectors.premises_id_for_account` owns `BR-CUS-1010`'s precedence
and `billing/statement.py` names the hazard of a second copy in as many words —
*"a second statement of `BR-CUS-1010`'s precedence and the one that drifts"*.
Statement reads the published answer, correctly, because it asks about ONE
account; that read reaches metering through `seams.unit_row` + `unit_dict`,
which is a round trip per account and 40,000 of them here. So this seam takes
the unit leg off the row it already joined AND
`test_the_walk_agrees_with_the_customers_modules_own_published_read` asserts the
two answer identically for all five shapes. If either precedence moves, that
case goes red and names the account.

⚠ **ONE FACT THAT CAME OUT OF WRITING THAT CASE AND IS WORTH KEEPING:** no
lawful account can make the walk answer `None`. `ck_accounts_anchored` refuses a
row with neither a unit nor a premises, so the walk's `None` is DEFENSIVE. The
absence a partner actually meets is `address: null` from a premises id that
resolves to no row — a different fact, decided in `address_map`, and the seam
docstring says so now rather than claiming an honest third answer it cannot
produce.

### Proved in the running product (hard-won law 6)

A backend built from this branch on **8481** against the real PostgreSQL, the
key issued through the real `POST …/key`. ⚠ **The stack on 8299 does not have
this code and answers `404` at these addresses** — confirmed before anything was
believed.

```
customers?page_size=3        200   {"total_records": 84, "page": 1,
                                    "page_size": 3, "total_pages": 28, …}
  A-10432  Miller, Sarah    1408 Elm Street, Silver Creek, TX 78611   active/Active
  A-10650  Iversen, Britt   18 Marten Row, Silver Creek, TX 78611     active/Active
  A-10714  Haddad, Nour     3 Kestrel Close, Silver Creek, TX 78611   active/Active

page 28 of 28               200   AC-2026-00061…63, "Clerk Walk Developments LLC"
page_size=1000              200   84 rows · 71 distinct addresses · 0 null
                                  · numbers ascending and unique
                                  · statuses: active 80 · marked_disconnect 1
                                    · vacation_hold 1 · pending_activation 1 · closed 1
wrong company_id            403   {"error": "This key is another utility's.",
                                   "code": "COMPANY_MISMATCH"}
no key at all               404   {"error": "We cannot serve this request.", "code": "REFUSED"}
unknown key                 404   same bytes
```

**A key ticked for `serve_customer` ALONE**, issued live:

```
customers   200   {"total_records": 84, … "A-10432" …}
bills       404   {"error": "We cannot serve this request.", "code": "REFUSED"}
payments    404   same bytes
ledger      404   same bytes
```

**The access log (S142) recorded every one, with the mask and no key:**

```
Customers, everything · 84 records · page 1 of 1 · ••••7d58    succeeded
Customers, everything · 1 records · page 1 of 84 · ••••7feb    succeeded
key may not call this · refused · ••••7feb                     skipped   (×3)
Customers, wrong utility named · refused · ••••7d58            skipped
```

**And the published specification stopped promising a `501` at this address:**

```
/partner/v1/bills      ['200', '404', '429', '501']
/partner/v1/customers  ['200', '404', '429']
/partner/v1/ledger     ['200', '404', '429']
/partner/v1/payments   ['200', '404', '429', '501']
```

### The hold, released — and `DEF-INT-5538`

`ROUTE_WAVE` loses its `customers` row in the same commit that serves the
address. Landing a wave and releasing the hold that pointed at it are two acts
and only the first feels like the work; lane A's
`test_the_unbuilt_routes_go_red_the_day_their_wave_lands` is what made the
second a failure rather than a thing to remember, and **it went red on this row
before this row moved**.

⚠ **AND THREE OF ITS NEIGHBOURS WERE ALREADY RED AT THE TIP, FOR THE RIGHT
REASON, AND NOT BECAUSE OF THIS LANE** (`DEF-INT-5538`). Wave 5 removed the
ledger's row correctly an hour earlier, and
`test_every_unbuilt_route_names_its_wave`,
`test_an_unbuilt_route_is_never_an_empty_result_set` and
`test_the_published_specification_names_all_four_operations` each iterate a
**typed list of four** while asserting against `ROUTE_WAVE`. Dated with
`git log -S` on the assertion text, which names `c2ef372f` — the commit that
wrote both the hold and the case. All three are now driven off `ROUTE_WAVE` and
a derived `ROUTE_VIEWS`; the equality became a **subset**, because whether a
landed route LEFT the map is the hold-expiry case's job and one assertion doing
both did neither well; and the specification case gained its mirror — **a route
that SERVES must stop advertising a `501`**, or a partner writes a branch for a
response it will never receive. **Waves 3 and 4 need no edit to that file.**

⚠ **ONE MISTAKE OF THIS LANE'S OWN, RECORDED BECAUSE IT IS THE SAME SHAPE.** The
first draft of `test_the_route_no_longer_answers_not_yet_served` asserted
`set(ROUTE_WAVE) == {"bills", "payments", "ledger"}` and **was wrong within the
hour**, because wave 5 landed while this was being written. A case that goes red
when somebody else does their job correctly teaches the next lane to edit it
rather than read it. It asserts `"customers" not in ROUTE_WAVE` now, and a
subset for the rest.

### `DEF-INT-5539`, filed and NOT fixed here

`partner_openapi` publishes `from`, `to`, `page` and `page_size` for **every**
operation, so the document offers this route a date window it does not read, and
says nothing about the ledger's `start_date`/`end_date` being **required**. The
parameter loop is one block shared by all four routes with three lanes live in
that file within the hour (law 11), so it belongs to `partner_openapi`'s owner:
carry the accepted parameters as DATA on the `Operation`, the way `served_path`
and `rate_limit_per_minute` already are — which is `DEF-INT-5522`'s own shape.

### The gates, and the reds this lane did not cause

`tests/test_cr110_phase2_partner_customers.py` — **28 cases**, and both partner
files together **68 pass** at this tip. `run_gates` reports **75 PASS · 47 FAIL
· 4 SKIP**, and **not one FAIL line names a file this lane touched** — checked
by grepping every FAIL for all seven paths rather than by reading the list.
`G17`'s five duplicate NUMBERS are 4497, 4512, 4710 and two more, exactly as
wave 1 recorded them; neither `DEF-INT-5538` nor `DEF-INT-5539` appears. The three reds above were read rather
than stepped over, dated with `git log -S`, and fixed on this file's own
principle that a red outliving its owner belongs to whoever is still here.

### Rollback

Revert the commit. **No migration, no data written, no manifest and no screen** —
the route goes back to answering `501` naming wave 2, `ROUTE_WAVE` gets its row
back, and the published specification promises the `501` again. `DEF-INT-5538`'s
repair to the shared test file would have to go back with it, or that file is red
again for the reason it was red before.

---

# PHASE 2 WAVE 5 · THE LEDGER — two of our rows into one of theirs · `2.286.0`

`GET /api/{utility}/partner/v1/ledger` serves real journal data. Lane A's nine
checks, its rate limit, its run row and its `company_id` verification are
unchanged and are not re-argued here; what follows is check 9 — select, order,
page — and the transform, which is the whole of the work.

## The shape problem, and it is not a formatting difference

`JournalLine` carries a **`side` and a NON-NEGATIVE amount**, and its own
docstring says why: *"Direction is a column, so there is exactly one way to
express a credit."* A balanced pair is therefore **TWO ROWS**. Aclarian's
`/ledger` payload is **ONE row** naming a `debitAccount` and a `creditAccount`.

⚠ **AND A BILL DOES NOT COLLAPSE INTO ONE ROW AT ALL.** Measured on the demo
tenant before anything was designed — 168 posted entries, 664 lines:

| debits × credits | entries | what it is |
|---|---|---|
| 1 × 1 | 83 | a payment, a fee |
| 1 × 5 | 80 | a bill: AR against electric usage, electric base, water usage, water base, tax |
| 1 × 2 | 4 | a payment that leaves a credit balance |
| 5 × 1 | 1 | a credit note reversing a bill in full |
| many × many | **0** | — |

## What was built, and the reasoning, because the specification calls this API PROPOSED

The document says *"Final debit/credit handling and GL mapping should follow the
accounting rules agreed with Aclarian."* **No accounting rule is invented.** Two
rules cover every entry this product can post, and both are in
`seams/ledger.as_record`, whose return type is a **LIST** — the plural is the
shape problem made visible in the signature.

**1 · ONE LINE ON ONE SIDE, N ON THE OTHER → N rows, each pairing one line of
the many side against the single COMMON line.** Each row's `amount` is the
many-side line's OWN amount, so the rows sum to the entry's total on both sides.
Nothing is allocated and nothing is chosen. A 1 × 1 entry is the N = 1 case and
lands in exactly their shape; the 5 × 1 credit note is the same rule mirrored.

**2 · MANY ON BOTH SIDES → we do NOT pair, and the row says so.** Which debit
funds which credit is an ALLOCATION RULE nobody has given us. Each line becomes
its own row with its own side filled and the counter-account `null`, which a
partner can SEE. **No such entry exists in the product today**, which is exactly
why the branch is written now rather than met by a customer.

⚠ **THE OBVIOUS MOVE WOULD HAVE LOST MONEY SILENTLY.** Picking the first line
and calling it the credit turns the worked bill below into **one row of $12.00**
and drops **$105.30**, on a row that reads as settled.

## It balances, proved on real data rather than on a fixture

Whole year, Brazos Bend, through the seam:

    OURS    debits 63,303.410000   credits 63,303.410000
    THEIRS  debits 63,303.41       credits 63,303.41

And through a real HTTP stack, walking every page of July with a real issued key
(five pages of ten):

    envelope promised : 213 rows
    actually received : 213 rows
    debits            : 12,418.92
    credits           : 12,418.92

## Paging — the trap that loses money

**The page is a page of ENTRIES, never of lines.** Pairing reads a WHOLE entry,
so a page boundary inside one leaves two half-postings that look perfectly
healthy and that a fixture smaller than a page can never show.

`start_date` and `end_date` are **REQUIRED here alone** — a month at the top of
T5 is ~200,000 rows and an unbounded walk over a moving table is the paging trap
with nothing to bound it. A caller that forgets gets `400` and six words,
**never** the five-word refusal, which would send them to look at their key.

The order ends on the uuid7 primary key, because `entry_date` is a DATE and a
month's entries share a handful of values: page over that with no second key and
one entry comes back twice while another never comes back at all. **A missed
journal entry is a missed posting.**

**Two totals, because two things are counted.** `total_records` counts what
`records` holds — partner ROWS — on this route exactly as on the other four, so
their job can add up what it pulled and compare. `total_entries` is the paged
unit and `total_pages` is derived from it.

**One query for the entries and one for their lines, whatever the page holds.**
`collectable()` prefetches the lines with their account and their ledger account;
without it, reading `line.ledger_account.code` at a thousand entries a page is a
query per line — and it would look perfectly fast on a demo tenant with a hundred.

## Two recorded divergences from the specification's sample

**`transactionType` is the LEDGER'S ENTRY TYPE, not the source document's word.**
Their sample draws `{"code":"payment","label":"Customer payment"}`; ours is
`{"code":"standard","label":"An ordinary entry"}`, read from
`reference.transaction_types()` — **the same list the reference endpoint
publishes under that key**, so the two can never disagree. The column that holds
their word is `source_type`, and `JournalEntry`'s own docstring records that B2
§2 ships it *"with no FK and no chosen vocabulary"* (the O-4 residue). Emitting
it as a `code` would mint a vocabulary this product has never agreed on and hand
it to a partner as settled. What they get instead is `description`, which names
the source document in words — *"Bill BL-2607-000014 issued"*.

**`id` is not our uuid**, which is `seams/billing.as_record`'s rule for the whole
surface: *"a partner keyed on our uuid is coupled to our storage forever."* The
ledger's equivalent of `invoice_no` is `journal_entries.number`. See the defect
below.

## `DEF-LED-5540` — the `JE-` number is never stamped on a posted source event

`BR-LED-021` says the number is stamped when an entry POSTS.
`posting.post_draft()` stamps it; **`posting.post()` — the path every bill,
payment, opening balance, refund and credit note takes — does not.** The
`journal_entry` series exists on the demo tenant and sits at `next_number = 1`,
never consumed. Measured: **168 entries, 168 without a number.**

So `id` and `transactionId` come back `null`, the envelope names the reason ONCE
(`records_note: journal_entry_number_not_stamped_at_post`), and **no number is
composed here** — which is the posture `apps/ledger/journal_api.py` already takes
on the same fact, for the reason it states: a second allocator is how two entries
end up carrying one number, and a partner's books are the last place that should
be found out. Stamping one is a 🔒 posting-path change under human review, not a
side effect of a read. Where a number IS stamped, `id` is it and `transactionId`
carries the row ordinal (`JE-000042-1`), because one entry can be several rows
and a partner keying on a repeated value would collapse a bill's rows into one.

## `consumerNo` — how many entries have none

**Zero, on the demo tenant today**: all 664 lines carry an `account` dimension.
The null path is still built and tested, because a period close, a bank fee, a
depreciation run and an opening balance are all real entries with no customer
behind them — and they are the difference between the customer ledger and the
general ledger. **They are SERVED with `consumerNo: null`, never filtered out.**

## The hold was released, which is the second of the two acts

`ROUTE_WAVE` loses its `ledger` row, so `partner_openapi` stops promising a
`501` over an address that answers `200`. Three cases in
`test_cr110_phase2_partner_reference.py` went RED on exactly that and are the
lane's red proofs — quoted in the report. One of them,
`test_every_unbuilt_route_names_its_wave`, asserted `ROUTE_WAVE == SERVED_ROUTES`,
which was right only while nothing was built; it now asserts the SUBSET **and
names the difference**, so a route that quietly stopped serving cannot slip back
in unnoticed under a loosened check.

## `OQ-INT-12393` is OPEN and is the one thing that reaches the PO

Nothing is blocked and nothing is stubbed — the endpoint serves. The question is
whether the pairing above is the accounting rule Aclarian wants. See the
register row for the worked figure.

---

# PHASE 2 WAVES 3 AND 4 · THE NESTED BILL AND THE PAYMENT · `2.287.0`

Both addresses serve real data. Both went through the nine checks already; what
they answered was `501`.

## The bill is NESTED, and that is a PO ruling overriding the supplied document

PO 2026-09-16, verbatim: *"we save bills as a multiple line items with gl code
map so for bill we will need nasted json with multiple records with gl code
mapped"*. The document's flat sample carries ONE `accountString` per bill, which
can only be right when every line of a bill posts to one account.

**Measured on the running product rather than argued:** the first bill of the
demo tenant, `BL-2607-000001`, has **seven lines across two services and FIVE GL
accounts** — `4100`, `4105`, `4110`, `4115` and `2200-01`. A flat payload would
have had to pick one of the five and lose four.

## `accountString` — already built, and this wave only reads it

PO: *"this is already done using setting and plans and rates - bills are
generated with gl code only - you can check this out"*. It checks out.
`invoice_lines.gl_account_id` is STAMPED at issue (`BR-BIL-010`) and frozen;
this wave resolves it to the chart's code through
`ledger.selectors.account_labels`, the batched read billing's own Charges tab
already uses (published for `DEF-937`, for this exact reason). **Nothing
re-decides where a line posted.**

**HOW MANY SERVED LINES CARRY NO GL ACCOUNT: ZERO, AND THE NUMBER IS WORTH
WRITING DOWN.** Brazos Bend has 647 invoice lines; **seven carry no
`gl_account_id`** (2 base, 1 tax, 4 usage) and **all seven are on the one DRAFT
invoice**, which never leaves. Of the 640 lines on the 81 collectable bills,
640 carry a code. So the `accountString: null` path is real, is tested, and
fires on nothing today — which also means **a live pull cannot tell a correct
null from a missing branch**, and that is why the case exists in the suite.

## The three balance clocks, and they are three different moments

None of the three is stored. Written into the code because the next reader will
assume they are one figure:

| Field | Which clock | Where it comes from |
|---|---|---|
| `before_pay_outstanding` | **as at the bill date** | the bill's OWN stamped `balance_forward` (`BR-BIL-035`), written at issue into `bill_payload` and frozen — so it is the figure PRINTED on the document the customer holds. It never moves again |
| `after_pay_outstanding` | **this document, today** | `before` + this bill − what payments has since allocated against this invoice. Moves every time a payment lands on this bill |
| `amount` | **the account, now** | `billing.open_balance` — everything the account owes at the moment of the call, across every bill |

Worked on the live pair, from the curl output: `BL-2607-000029` is `corrected`
with `before 0.00`, `bill_amount 137.70`, `after 137.70`, `amount 0.00`; its
rebill `BL-2607-000041` carries `before 137.70`. **Five of the 81 bills have all
three figures different**, which is the fixture condition the brief asked for,
met on real data as well as in the suite.

⚠ **AN UNREACHABLE FIGURE IS `null`, NEVER `0.00`** — the posture
`_stamp_balance_forward` already takes. Telling a partner `0.00` about a
customer in arrears says they are square.

## Both documents of a correction go, and `replaces` is how they pair

A bill is never UPDATED, so there is no *latest copy*: `INVOICE_LOCKED_STATUSES`
covers `issued`, `paid`, `void` and `corrected`, and a correction is a NEW ROW.
Sending only the newer one leaves a partner's books permanently wrong — they
have already posted the original and the correction is what reverses it.

**HOW `replaces` IS DERIVED, ASKED AND ANSWERED RATHER THAN INVENTED:** it is
`invoices.corrects_invoice`, a self-FK that lives on the **REPLACEMENT** and
points back at what it replaces — the PO's own ruling of 2026-08-12 closing
`OQ-120` (*"Nod to add the link on the new bill"*). The direction is the whole
of it: an issued bill is immutable, so the original cannot gain a pointer after
the fact, and the rebill learns what it replaces at INSERT. It is UNIQUE per
original (`uq_invoices_one_replacement`), so the chain is a chain and never a
tree. **So nothing had to be invented and nothing is missing.**

Proved live: `BL-2607-000041` comes back with `billType: rebill` and
`replaces: "BL-2607-000029"`, and `BL-2607-000029` comes back in the same page
with `status: corrected`.

⚠ **ONE RECORDED DIVERGENCE: `replaces` IS ALWAYS PRESENT, `null` WHEN A BILL
REPLACES NOTHING.** The supplied document annotates it *present only on a bill
that replaces one*. A finance system pairing a correction cannot tell a key we
OMITTED from a bill that replaces nothing — the same *missing versus empty*
confusion this surface answers `501` rather than `[]` to avoid.

## Two more recorded divergences from the supplied document

* **`id` IS THE BILL NUMBER.** The document draws a numeric id; ours is
  `BL-2607-000041`. `seams/billing` states the rule for the whole partner
  surface: *"a partner keyed on our uuid is coupled to our storage forever."*
* **A LINE CARRIES `unit` BESIDE `quantity`, AND THE DOCUMENT HAS NO SUCH
  FIELD.** CLAUDE.md hard rule 3 — consumption is always stated with an explicit
  unit. `3.000000` of something is not a consumption, and a partner reading
  gallons where we meant thousands of gallons is wrong by a factor of a thousand.
  The live payload carries `kWh` and `kgal`.

## The payment: the four coded fields are OURS, published with labels

PO 2026-09-16: *"this will not be required in case of they read cases - we just
need to actiavte connectors and issue a key thats all"* — which struck the clerk
mapping screen, because **for a READ the partner maps at THEIR end** from the
reference endpoint. So no vocabulary was typed and no mapping screen was built.

| Payload field | Our column | Reference key |
|---|---|---|
| `type` | `payments.type` — payment · credit · adjustment | `paymentType` |
| `projectType` | `payments.purpose` — bill · deposit · plan_down · prepay | `projectType` |
| `tenderType` | the tenant's own `payment_methods` row, code and name | `tender` |
| `paymentPayType` | `payments.status` | `paymentPayType` |

⚠ **THIS DOES NOT REOPEN `BR-INT-054`, AND THE DISTINCTION IS THE WHOLE OF IT.**
What Runbooks owns is the **TRANSLATION** — deciding that our *Bank transfer* is
their `ACHCHECK` — and `serve.partner_fields()` is still where that arrives and
still returns `{}`; the test that asserts so is kept and repointed rather than
deleted. Publishing our own code with our own word is the same act as the
reference endpoint, which the PO commissioned in the same hour for this purpose.

⚠ **`reference.py` GREW THREE VOCABULARIES IN THE SAME COMMIT**, so a partner
that cached the document can resolve every code it meets:
`REFERENCE_KEYS` goes from seven to **ten**. Leaving them out would have put
`paymentPayType: cleared` on a payload with nothing to resolve it against —
the exact failure the PO commissioned the endpoint to prevent.

⚠ **AND THE VENDOR'S DOCUMENT IS NOT IN THIS REPO.** The four field NAMES are
the supplied payload's; what each MEANS in Aclarian's world is written nowhere
we hold. The mapping above is therefore **ours**, recorded here with its
reasoning rather than left to be inferred, and each is a one-line change in one
place if the partner's engineer says otherwise. `FeeEntryId` is
`payments.confirmation` — the reference the money arrived with, which is what a
partner matches a bank line on — and is `null` when the utility recorded none.

## The phase-1 flat pair is RETIRED — `410`, and not upgraded in place

⚠ **THE ONE THING THAT DECIDED IT: `amount` CHANGED MEANING.** On the flat
record `amount` was THE BILL'S OWN TOTAL. On the nested record `amount` is **the
account's balance now** and the bill's total is `bill_amount` — the PO's payload
says so. One key, two meanings, and **a finance system cannot see the
difference**: it would go on posting a receivable from a field that had quietly
started answering a different question. Serving the nested payload at the old
address would have been exactly that, and serving the flat payload at the new
one is the mirror the CR already forbade.

`410` and not `404`, because a `404` on this surface is the REFUSAL — the same
five words a wrong key gets — so a partner would go looking at its credentials
for an address that is simply finished. The body NAMES the replacement. It
authenticates FIRST, exactly like every other route: a retirement notice handed
to an unauthenticated caller answers *this utility exists* to anybody who asks.

**`tests/test_us_int_041_partner_surface.py` MOVED ONTO THE PHASE-2 ADDRESSES
RATHER THAN BEING DELETED WITH THE ROUTES**, and so did
`test_us_int_040_issued_key.py`'s `partner_call`. Every case in those files is
about the DOOR or about the KEY — the allowlist, the three refusals, the rate
limit, two utilities, the envelope, the run row, *last used* — and the door is
the same nine checks at every address. Deleting them with the routes would have
deleted the proofs.

Two cases in `041` were rewritten rather than repointed, because the phase-2
door answers differently and the row is the thing to update:

* **TC-5** asserted that `tenderType`, `projectType` and `accountString` were
  ABSENT (`CR-069` §20.4). Its own message said *"If Runbooks has landed, this
  test is the row to update — do not delete the assertion, move it."* It now
  asserts the whole phase-2 field set AND that `partner_fields()` is still empty.
* **TC-7b** asserted that `company_id` *changes nothing*. True of the flat
  route, which never read it. The PO then ruled *"company_id = tenant id"*,
  which CONFIRMS the finding rather than softening it, so it is now VERIFIED
  against the key and still never used to select. Both halves are asserted.

## `ROUTE_WAVE` is now EMPTY, which is the second of the two acts

Waves 2 and 5 removed their rows within the hour; these two remove the last two.
No address answers *not built yet* any more. The dict STAYS rather than being
deleted with its last row — a sixth address will arrive declared-before-built
exactly as these four did — and `_not_yet_served` reads it with `.get` so an
empty map cannot turn that day's `501` into a `500`.
`test_an_unbuilt_route_is_never_an_empty_result_set` drove four live addresses
and now drives none; its own assertion said *"every wave has landed — retire
this case rather than empty it"*, so it asks the same question of
`_not_yet_served` directly, with no tenant, no key and no `django_db` mark.

## Proved on the running product — hard-won law 6

A backend on this branch's code against the real PostgreSQL, with a key issued
through `services.record_credential`. **The key was issued on a SECOND ERP
connection (`erp_sap`) on purpose:** lane D held an ACTIVE credential on the
Aclarian connection at that moment and `record_credential` deactivates the
previous version **of the connection it is issued on**, so issuing on Aclarian
would have revoked a sibling's key mid-proof. It doubles as proof that the
surface is generic — `BR-INT-037`, and the PO's *"why aclarian in it - we cna
make it generic - saying partner"*.

    GET /partner/v1/bills?company_id=…&page_size=1000
      200 · total_records 81 · total_pages 1 · 0.35s
      81 of 81 bills: Σ lines == bill_amount
      0 of 640 served lines carry a null accountString
      the corrected/rebill pair present and paired
      5 bills with all three balance clocks different

    GET /partner/v1/payments?company_id=…&start_date=…&end_date=…
      200 · total_records 66 · all four coded fields with labels · accountString 1010

    GET /partner/v1/payments  (no dates)   400 DATE_RANGE_REQUIRED
    GET /partner/v1/bills?since=2026-13-45 400 BAD_DATE
    GET /partner/v1/bills  (another utility's company_id) 403 COMPANY_MISMATCH
    GET /v1/payments  410 → /partner/v1/payments
    GET /v1/billing   410 → /partner/v1/bills
    GET /v1/payments  (a key never issued) 404 "We cannot serve this request."

⚠ **THE FIRST ATTEMPT ANSWERED `429 COUNTER_UNAVAILABLE`, WHICH IS LAW 3
WORKING.** With no reachable `CACHE_URL` the shared rate-limit counter refuses
rather than falling back to a per-process count. `.env` names
`redis://redis:6379/1`, a hostname that does not resolve in this container;
pointing the dev server at `127.0.0.1:6379` served every request. **Nothing in
the product is wrong and nothing was changed** — it is recorded because the same
refusal will meet the next lane that curls this surface.

## The paging trap, answered in three places

1. the window is applied BEFORE the page, in SQL, so the set has stopped moving;
2. the sort ends in a column that never repeats (`issued_at, id` · `posted_at,
   id`), so no two rows can swap places between two calls;
3. the envelope carries `total_records`, so the partner's job can CHECK it
   pulled what we said existed rather than trusting it reached the end.

⚠ **AND AN UNREADABLE DATE IS REFUSED RATHER THAN READ AS ABSENT.**
`_parse_date` answers `None` to both *absent* and *`2026-13-45`*, so the first
draft of the bills route read one wrong digit as *no lower bound* and handed
back every bill the utility had ever issued. `400 BAD_DATE` now names it.
The REQUIRED-window refusal reuses wave 5's own `LEDGER_WINDOW_REQUIRED`
sentence and code: two codes for one fact on one surface is `DEF-014`.

## Three defects filed, each measured

* **`DEF-INT-5545`** — `erp_workday`, `erp_sap`, `erp_infor` and `erp_msgp`
  declare no `served_path`, so `partner_openapi` falls back to the phase-1 pair
  and their published specification now advertises two retired addresses. Their
  keys still work at the phase-2 addresses, which serve every connector in
  `partner_provider_keys()`; the document under-reports, the door is not shut.
  One line per manifest, and a manifest is not this lane's to touch. The
  specification says `410` on those two in the meantime.
* **`DEF-INT-5542`** — `open_balances_for_accounts` costs one `SUM(allocations)`
  per INVOICE of every account on the page. Measured: a one-bill page is 17
  statements and a five-bill page is 21; the demo's 81-bill page answers in
  0.35s, which extrapolates to about **4s for the PO's 1,000-row page**. It is
  billing's read, not this wave's. This lane's own three shared reads ARE
  asserted constant-cost, and that case deliberately does not assert a flat
  total — pinning somebody else's defect green is how it would stop being found.
* **`DEF-INT-5543`** — `seams/payments.COLLECTABLE_STATUSES` names `deposited`
  and `settled`, which are not values of `payments.status`. The filter is right
  by accident and the comment above it describes a vocabulary this product does
  not have. Found by writing `paymentPayType`, which publishes the real five.
  Left in place and filed: changing a served set belongs in a commit that says so.

## Seven guards proved RED first, in `pytest`, never `python3 <module>`

| Broken | The failure, verbatim |
|---|---|
| the payload flattened | `KeyError: 'lines'` ×3 |
| `replaces` omitted when null | `assert ('replaces' in {'id': 'BL-2607-000029', …})` |
| one figure served for all three clocks | `assert '78.75' == '68.75'` |
| the flat route serving again | `AssertionError: /v1/payments · assert 200 == 410` |
| the shared reads made per row | `the account name cost 5 statements for five bills and 1 for one` |
| `tenderType` labelled from a typed word | `assert 'Cheque' == 'Check'` |
| the required window dropped | `assert 200 == 400` |

## 7 · Version and rollback, stated before shipping

**`2.287.0`** — a CHANGE: two addresses that refused now serve, two retire, and
the reference document grows three vocabularies. Allocated with
`allocate.py version --bump change` against the REMOTE.

**Rollback is the four code files and nothing else.** No migration, no data, no
new table, no setting. Reverting `partner_api.py`, `seams/billing.py`,
`seams/payments.py` and `reference.py` to the tip's copies puts both addresses
back to `501` and both flat routes back to serving the flat record — and
`ROUTE_WAVE` must be reverted with them in the SAME commit, or the hold-expiry
case is red on a route that is held. A partner that has already switched to the
new addresses would then get `501`, which is the honest answer and not silence.

## Which build to look in — for the reporter

**`2.287.0`.** A partner with an issued key calls
`/api/{utility}/partner/v1/bills?company_id=…` and gets one record per bill with
one row per line, each line naming the GL account it posted to; and
`/api/{utility}/partner/v1/payments?company_id=…&start_date=…&end_date=…` for
the payments, with the tender and the cash account on each. The old
`/v1/payments` and `/v1/billing` answer *this address has been replaced by …*.

## ⚠ THE PORT LESSON, PAID AGAIN — a stack answered with the WRONG CODE

The brief for this lane carried a warning in the PO's own terms: *"Do not trust
any other port; confirm what a stack serves before believing a result — that
cost a full cycle today."* It cost this lane a result as well, and the shape is
worth the four lines.

A dev server was launched on `8478`, the launch **failed with `Error: That port
is already in use`** — a sibling lane already had one there — and the `curl` that
followed went to the sibling's server, which is running the tip from before this
wave. It answered:

    {"error": "Not built yet — wave 3.", "code": "NOT_YET_SERVED", "resource": "bills"}

**A perfectly good, perfectly truthful `501` from the wrong process**, and read
as a result it says *your wave does not work*. Nothing in the response can tell
you which build answered it.

**So the confirmation is a distinguishing REQUEST, not a port number.** Every
figure quoted above was taken from `8611` — a port checked free first — and the
first call made to it was the one that can only be answered one way by each
build: `GET /v1/payments` answers **`410`** on this wave's code and **`200`** on
every build before it. A check that cannot tell the two builds apart is not a
check (hard-won law 7).

---

## PHASE 2 · `DEF-INT-5546` — THE UTILITY LEAVES THE PARTNER URL (2026-09-16)

**PO, having been shown the five addresses as built, verbatim:**

> *"thi si wromg - we agreed not to use utility names in partner apis that was
> our rule - so these urls are not corect - we will resolve utility name using
> keys... please confirm your understanding"*

Confirmed, and they were right. **The five addresses are now:**

```
GET /api/partner/v1/reference
GET /api/partner/v1/customers
GET /api/partner/v1/bills
GET /api/partner/v1/payments
GET /api/partner/v1/ledger
```

One base URL. The same for every partner and every utility.

### How the deviation happened, because that is the part worth keeping

The lane that built the route table **recorded a deviation from the blueprint
and argued it**: `BR-TEN-003` reads the tenant from the path; with no tenant
context RLS `FORCE` returns zero rows for the credential lookup, for a valid key
as much as an invented one; therefore the door would be *incapable of passing*,
which is hard-won law 7's own third shape being cited correctly.

**Every clause is true and the conclusion does not follow.** It is true of a
TENANT table, and it only forces the utility into the URL if the first lookup
must be against one. Blueprint p159 — *WHY NOT PUT IT IN THE PATH* — says it
need not be, in a four-row table, under a diagram:

```
key ──► connection ──► tenant ──► app.tenant_id set ──► RLS does the isolating
```

**Nobody opened that page**, because the lane had a plausible technical
objection and *a recorded deviation reads as a decision rather than as an open
question*. I then repeated its justification to the PO as settled.

> **THE REVIEW RULE THIS BUYS:** when a lane records a DEVIATION from a
> drawing, the review question is not whether its reasoning is sound but
> **whether the drawing already answers it**. B14 rule 42 says a screen is built
> from the drawing as an image; an interface is no different.

### What was built

| # | Change | File |
|---|---|---|
| 1 | `integration_key_directory` — blind index → utility, plus the two ids | `integrations/0011`, `models.py` |
| 2 | Resolve and open the utility from the key | `key_directory.py` |
| 3 | `adopt_partner_tenant`, beside `adopt_session_tenant` | `core/tenancy.py` |
| 4 | The five routes, mounted outside the tenant include | `partner_urls.py`, `config/urls.py` |
| 5 | A directory row per issued key, on the ONE credential write path | `services.record_credential` |
| 6 | Rows dropped on disconnect — and kept on revoke | `services.disconnect` |
| 7 | `partner` is a no-tenant segment and a reserved slug | `core/tenancy.py`, `tenancy/selectors.py` |
| 8 | The exemption declared in both places that have to agree | `isolation_helpers.py`, B2 §3 |
| 9 | 18 cases, both utilities, both directions | `test_cr110_partner_tenant_from_key.py` |

### Why the new table may be RLS-exempt, in three sentences

It is **the same class as `sessions`**, which has been on B2 §3's no-RLS list
since W0 for the identical reason: `/api/jobs/{id}` carries no utility either,
and `adopt_session_tenant` reads the session row to open the one it names — its
own docstring says *"the cookie selects a row, the row states the tenant.
Adopting it is not client input."* It **holds nothing worth taking**: three
opaque ids and a one-way fingerprint, no secret, no name, no money. And it
**authorises nothing** — every guard still runs afterwards against
`integration_credential` under the utility it opened, so a row naming the wrong
utility is refused in the ordinary way with the ordinary five words.

⚠ **AND `sessions` QUIETLY DISPROVED B2 §3's OWN STATED TEST.** The brief says
*"a table belongs here when it has NO `tenant_id`"*; `identity.Session` has
carried one since W0. §3 now records **two** tests — no `tenant_id` at all, or
*its whole job is to resolve the tenant, so a policy on it could only ever be
checked against an answer it has not given yet* — and names the two tables in
class two. `DEF-TEN-4446`'s mistake (a table that merely SOUNDED platform-ish)
is a different thing and is not widened by this.

### BR-TEN-003 is CLARIFIED, and the clarification is that it never said what the code said it said

The rule's own words are **"never client input."** Three places paraphrased that
as *"read from the PATH and from nothing else"* — the middleware, `serve.py` and
`partner_api.py` — and the paraphrase is **narrower than the rule, in the one
direction that mattered**. Nothing is reversed here. A rule was read through a
code comment's summary of it, which is B14's rule-count rot in a different
family.

**Three resolvers are lawful and the product has always had two:** the path's
slug against `tenants`; the session row on the platform paths; and now an issued
key against `integration_key_directory`. All three read something WE wrote
against a table WE keep. None reads a tenant id a caller sent. A fourth is a
decision, not a convenience.

### What did NOT change, which is most of the argument

**Nothing in the door.** By the time `resolve_caller` runs, `app.tenant_id` is
set exactly as it would be on a path-resolved route; the credential lookup is
scoped by RLS exactly as before; TC-5 and TC-7 stay properties of the database.
`company_id` is still accepted and still VERIFIED, never used to select — and
with the segment gone it is the last value on a partner request that names a
utility, which is why `test_a_key_cannot_claim_the_other_utility` exists.

One hunk in the 🔒 file, and it gates a RECORDED CAUSE rather than the refusal:
an unknown key resolves no utility, so `utility_is_live(None)` is correctly
`False` — and recording `UTILITY_INACTIVE` for it would tell a manager their
utility is switched off when the truth is that we never worked out which utility
the caller meant.

**The phase-1 pair did not move.** `/api/{utility}/v1/payments` and
`/v1/billing` still serve the flat `US-INT-041` payload from inside the tenant
include; different address, different payload, their own retirement schedule.

### One thing was already right and is worth recording

**The connection screen has been showing the correct address all along.** The
ENDPOINT column renders `Operation.served_path` verbatim, and Aclarian's four
manifests declare `/partner/v1/payments`, `/bills`, `/customers`, `/ledger` —
with no utility in any of them, because `test_every_aclarian_operation_names_its
_own_path` asserts the vendor's name is absent and the paths were written to the
drawing. So a clerk reading the screen and an engineer reading the router would
have disagreed, and the screen was the one telling the truth.

### Timing, because this surface is measured in milliseconds

`open_utility_for` spends **two statements on every path, hit or miss**. It runs
before `resolve_caller` starts the clock `REFUSAL_FLOOR_S` pads against, so
whatever it costs is added on TOP of the floor rather than absorbed by it — and
a hit that set the GUC while a miss set nothing would be one `set_config` round
trip of difference, measurable, meaning *your key is at least one we issued*. A
miss therefore CLEARS the context rather than leaving it alone: the same two
statements, and fail-closed in its own right.


---

# `DEF-INT-5531`…`5553` MAINTENANCE — the `they_hold_ours` SHAPE, on all six · `2.287.1`

**Track: MAINTENANCE** (`22-product-maintenance-process.md`). One question decides
it — *can a user do this task in the product today?* They can: a clerk opens
`settings/integrations`, presses Connect and fills the form. So reproduce ·
locate · blast radius · minimal fix · browser proof · regression · version ·
rollback · tell the reporter which build.

## What the PO said, from the deployed product

> "even view screen is not correct - font and all details does not match with
> images in document"

> "why we need client id - they read our data - why we need client id here -
> also we need to allow all apis to be read - all 4 currently i can select only
> 1 or you remove it and put selection on off directly on apis"

> "generate key is disable - nothing we are able to press"

and, on scope:

> "we need to follow this rule for all they read cases - not just aclarina -
> please fix this"

> "user can enable both - 4 Set-up page chooses Production or Sandbox - please
> note"

**So this is not Aclarian. It is a SHAPE**, read off `auth.mode` and never off a
provider key (`BR-INT-037`; `G77` fails a provider-key branch and is right):
`erp_aclarian` · `erp_workday` · `erp_sap` · `erp_infor` · `erp_msgp` ·
`payments_kiosk`. Every fault the PO reported for one was five-sixths of a
pattern, and the kiosk is the sixth that breaks a naive sweep.

## 0 · Reproduced first, in a browser, before a line of code was read

Against the live stack at `8401 → 8299`, signed in at `brazosbend`.

⚠ **AND THEN MEASURED AGAIN, BECAUSE THE LIVE STACK IS NOT THE BRANCH.** 8401
serves **2.283.1**; the tip was **2.284.0**, and two of the reported faults had
already moved (the ceiling read `100 / min` where the door enforces 60, and
`serve_ledger` appeared as a raw code in the run list). Everything below is
measured on a stack built from the pinned tip.

⚠ **AND THE SAME TRAP CAUGHT THIS LANE A SECOND TIME, HALF AN HOUR LATER.** The
first walk of the fixed screens reported *"the vestigial client id is GONE — XX"*
against code that had removed it. `pkill -f "PORT=8512"` matches nothing, because
the port is an ENVIRONMENT VARIABLE and not a word on the command line, so the
12:54 backend was still holding 8511 while a 13:39 one had failed to bind and
died. **`ls -l /proc/<pid>/cwd` says which TREE a server runs from and says
nothing about WHEN it started**; `ps` does, and reading it is what found this.
Hard-won law 6's *confirm what a stack serves before believing a result*, on the
process rather than on the bundle.

| Pressed, at 2.284.0 | Before |
|---|---|
| Aclarian's set-up form | `Their client id *`, required, read by nothing |
| `What they may read *` | three chips, **one selectable** — `kind="select"` is single-value |
| every API row | `Read payments · They send` — a row contradicting itself in four words |
| the WHEN column | `A partner` — an answer to WHO |
| the RATE LIMIT column | `—` on every row of every connector |
| `Generate a key` on an unconnected connector | disabled, *"Save this connector, then generate one."* |
| Aclarian's connection view | kicker `CONNECTION`; summary line `Aclarian`, under a heading reading `Aclarian`; **`PASSWORDS ON THIS CONNECTION`** listing four partner keys, with `Replace password` and `Go back to this`; **no `Keys we issue` panel at all** |

## 1 · Located · 2 · Blast radius, both ways

`ConnectorSetupPage.tsx` (S147 · INT-07) and `ConnectionDetailPage.tsx`
(S142 · INT-02), plus the five ERP manifests and `runs.py`'s payload.

**The mirror — what else USED what is being removed**, walked before anything
moved:

| Removed | Who used it |
|---|---|
| `Field(name="client_id")` × 5 | **nothing.** `oauth.py`'s `client_id` is OUR registration with a vendor we DIAL — the opposite direction — so a grep for the name finds live callers and says nothing about this one. One seed command wrote it into `config`; cleaned in the same commit, because `settings_for` drops an unknown key on the way out and a dead value in `config` reads as authoritative to the next reader |
| `Field(name="scopes")` × 5 | three test fixtures, all moved WITH the manifest rather than around it. **The server refuses an undeclared field BY NAME** — `integrations.field.unknown` — which is the manifest being the single source of truth working exactly as intended, and is how eleven cases told us at once |
| `issuePartnerKey(client, key)` | **two callers**, and both were broken: the set-up screen and S144 each posted `{}` to a door that refuses an empty scope |

## 3 · What changed

**The rule is by SHAPE and the code says so once.** `weIssueTheKey` is
`auth.mode === "they_hold_ours"`; a seventh such connector needs no line of code.

* **`DEF-INT-5534` · `client_id` gone from all five ERPs.** For a partner who
  reads from us the KEY identifies them, and the door proves it —
  `serve.resolve_caller` goes key → credential → connection → tenant and
  consults no other input (`BR-TEN-003`). **A required field nothing reads is a
  door a clerk cannot get through**, which is the whole of the PO's *"generate
  key is disable"*: Save refused, so no connection existed, so no key could be
  issued. The kiosk never had one.
* **`DEF-INT-5537` · the `scopes` select gone, replaced by a switch on each API
  row.** The PO offered two fixes and named the one they wanted. One place
  instead of two, so the field and the API list cannot disagree — and **one
  vocabulary instead of two, which closes `DEF-INT-5504`**: what a clerk
  switches on is the operation name the door enforces. The kiosk, which had no
  scope control of any kind, gains the same switches.
* **`DEF-INT-5535` · the key is issued WITH that scope.** Both callers send one.
* **`DEF-INT-5536` · four quadrants, four words.** `doorWord` had three and
  collapsed `out · them` into *They send*. It reads
  `integrations.kicker.{initiative}.{direction}` now, which has all four in all
  eleven languages and is what the connection view already used. ⚠ **The old key
  family `integrations.door.*` is declared in NO catalogue**, so every call fell
  through to a written fallback and the fallback was the whole implementation.
* **`DEF-INT-5493` · the WHEN column answers WHEN.** `integrations.when.*` is
  its own family, on BOTH screens; the run history keeps its past-tense words
  for the question it actually asks.
* **`DEF-INT-5533` · the panel is chosen by shape, in three arms.** A
  `they_hold_ours` connector gets the drawn **`Keys we issue`** panel — `KEY ·
  MAY CALL · ISSUED · STATE` — and no password panel; a `we_hold_theirs` one
  keeps its password panel and gets no keys panel; a `redirect` one keeps its
  sign-in arm. *Replace password* and *Go back to this* are **absent** rather
  than disabled on the issue arm: the first opened a form the server refuses
  (no field of kind `secret` is declared) and the second would **re-activate a
  revoked partner key**, a security control undone by a button labelled as a
  convenience.
* **`DEF-INT-5531` · `Connector`** — the kicker VIEW-17 draws.
* **`DEF-INT-5532` · the summary line** carries the live key and what it may
  call instead of the heading again.
* **`DEF-INT-5550` · the ceiling column** read `rate_limit`, a field no payload
  has ever carried, through a cast to `unknown` that is exactly what stopped
  `tsc` objecting. It reads `rate_limit_per_minute`, with its unit.

## ⚠ Three things the drawing shows that were DELIBERATELY not built

**Each is a difference with a reason, not an oversight.**

1. **`⚠ May call is new. Today one key opens every API on the connector — see
   CR-4.`** — drawn under the keys panel on p062 and p066, and **not built.**
   Two reasons and either is enough: it is **no longer true** (CR-4's scoping is
   built — `machine_auth._validated_scope` refuses a key that names nothing),
   and it is **rationale**, which B14 rule 33 puts at **zero words on screen**.
   Shipping it would put a false sentence on a live screen for a clerk to
   believe.
2. **The summary line's own words.** The drawing reads `••••7Q2F · reads
   payments, bills` while its MAY CALL cell reads `Read payments, Read bills
   +1` — **two vocabularies for one idea on one frame**, and the lower-case set
   is the retired `scopes` field's options. Reviving it would re-create exactly
   what `DEF-INT-5504` is about. Both places use the operation labels.
3. **`Keys we issue` in the footer is a LIVE LINK, not the greyed button the
   drawing shows.** S144 is routed and shipped at
   `settings/integrations/:key/access`. Drawing it dead would be
   `DEF-CWP-3925` — a refusal that outlived the screen it was holding.

## 4 · Proved against the reproduction, in a browser

`10-scripts/cr110_they_hold_ours_clerk_walk.mjs`, committed rather than left in
a scratch directory. **It walks the PO's own eleven steps, twice on two
connectors that are two quadrants, and then a third time on the other
environment**:

| Walk | Shape | What it proves that the others cannot |
|---|---|---|
| `erp_workday` production | `out · them` | they READ from us |
| `payments_kiosk` production | `in · them` | **the one connector in this set that genuinely SENDS** — so a fix mapping `initiative === "them"` to a single phrase is still wrong after the change |
| `erp_workday` sandbox | `out · them` | the switches, the key and the activation belong to the ENVIRONMENT rather than to the connector |

**ALL CHECKS PASSED**, end to end: fill the form, switch an API off, Save and
test, Generate a key, copy it, open the connection screen, and the key is in
`Keys we issue` with the two APIs it may call and nothing more.

## 5 · What the second and third walks found, which one pass could not

⚠ **`DEF-INT-5547` IS THE ONE THAT MATTERS AND IT WAS MEASURED, NOT REASONED.**
The backend does support both environments — `erp_workday` ends the walk with
two connection rows. **But every write route on a connector goes through
`connection_for`, whose entire rule is *"production first, else the only row"*,
and it takes no environment at all.** So a clerk who selects Sandbox, fills the
form and presses `Generate a key` is handed a key that opens **PRODUCTION**.
Counted in the database afterwards, under RLS:

```
('erp_workday', 'production', 'untested', True, 2)   ← both keys landed here
('erp_workday', 'sandbox',    'untested', True, 0)
```

⚠ **AND IT IS WHY THE EXISTING TEST PASSES.**
`test_a_sandbox_connection_mints_a_sandbox_key` creates **only** a sandbox row,
where *"production first, else the only row"* picks the right one **by
accident**. The case that breaks needs BOTH rows, which is the PO's own worked
example — a utility running a finance integration live and in a sandbox — and
is why they asked for the journey to be walked twice.

Five more, each filed rather than left in a docstring:

| | |
|---|---|
| `DEF-INT-5548` | a connector connected in production has **no door** to its sandbox — the card draws *Manage* and the set-up form is reachable only by typing the address |
| `DEF-INT-5549` | the connection view shows one environment and never says which — two rows, two keys, two run histories, one screen |
| `DEF-INT-5551` | S144's *What it reaches* prints *This utility* for every key while the may-call scope is served beside it and read by nothing |
| `DEF-INT-5552` | the **whole** set-up screen runs on English fallbacks — **zero** `integrations.setup.*` keys exist in any of the eleven catalogues |
| `DEF-INT-5554` | the set-up form is **create-only**, and it is the only screen that draws the switches: Save on a live connector answers *"Already connected — open Manage."* and Manage is a modal with no switches on it |

## ⚠ STEP 7 BEFORE STEP 9 — what the product supports, said plainly

The PO's journey puts **Generate a key (7) before Save and test (9)**. **The
product is 9-then-7**, and the walkthrough PRINTS which order it walked rather
than quietly building one and reporting the other:

```
·· STEP ORDER: Generate a key BEFORE Save is NOT AVAILABLE
   — the screen says "Save this connector, then generate one."
```

**It needs a product change, not a clearer screen, and the reason is a real
constraint rather than a UI choice.** A key is a row on `integration_credential`
with a `connection_id`; there is no connection until Save writes one, and
`issue_key` takes a connection. Two ways to honour the PO's order and both are
decisions, not implementations:

* **Save implicitly when Generate is pressed** — one press does two things, and
  the clerk has then connected a connector they may still cancel out of;
* **hold the key in the browser until Save** — a secret alive in a tab with
  nothing to attach it to, which is the opposite of *shown once and stored
  nowhere*.

**Neither is this lane's to choose.** The screen is honest today — the button
says why it is disabled — and the working order is 4 · 5 · 6 · 9 · 7 · 8 · 10 ·
11. It is put to the PO as one question with a figure rather than decided here.

## 6 · Reds, dated — not called *pre-existing* on faith

* **`tests/test_cr083_integrations_sample_data.py::test_the_ledger_seam_writes_nothing_itself`**
  — forbids the literal `.objects.` **anywhere** in `seams/ledger.py`, and wave
  5 added three **reads** to that file. Dated with
  `git log --oneline -- 06-backend/apps/integrations/seams/ledger.py`, which
  names **`eb477162`** (*"phase 2 wave 5: the ledger"*) against `32b643b6` from
  the day before. **Not this lane's, and not silenced** — it is a check that
  cannot tell a read from a write, which is the register's own
  `check-that-does-not-check`.
* Backend, `--reuse-db`: **133 passed, 1 failed**, and the one is that.
* Front end: **171 passed** across the eleven integrations suites, plus the new
  file's 24.

## The test that would have caught all of it, proved RED first

`07-frontend/src/features/integrations/connectorShape.test.tsx` — **24 cases
over THREE fixtures that are three quadrants**, because every fault here is a
rule expressed as a shape and one connector cannot prove a shape.

Proved RED in `npx vitest run` — the harness CI runs, never `node` on a path
nobody uses (`DEF-GOV-3733`) — **at the pinned tip, with none of this work in
it: 17 failed · 7 passed.**

```
× the set-up screen > Aclarian reads They read
  → expected [ 'Read payments', 'They send', …(3) ] to include 'They read'
× the set-up screen > Generate a key POSTS the switched-on operations
  → expected {} to deeply equal { scope: [ 'serve_payment', 'serve_bill' ] }
× the connection view > erp_aclarian: a Keys we issue panel, and NO password panel
  → the drawn Keys we issue panel (p062, p066) is not on the screen
× the connection view > WHEN answers WHEN
  → expected 'A partner' to be 'They call us'
```

24/24 after.

⚠ **AND THE FIXTURE CAUGHT ITSELF ONCE, WHICH IS THE PART WORTH KEEPING.** The
first green run left three red, and one of them was the FIXTURE and not the
code: `cardFor` gave every card an `issued_secret` field, so the switch column
appeared on Custom SMTP — a connector we DIAL, which has nothing to grant — and
the case asserting its ABSENCE was the only thing that noticed. The fields are
built per shape now. Law 7's *looking at the wrong thing*, found by a case
written to look the other way.

## 7 · Version and rollback, stated before shipping

**`2.287.1`**, allocated with `allocate.py version --bump fix` against the
REMOTE, written in `07-frontend/package.json`, `package-lock.json` and
`06-backend/pyproject.toml`, with the changelog in a clerk's words.

**Rollback is `git revert` of the two commits and nothing else.** No migration,
no data written, no API contract moved: the five manifests are DATA read at
`AppConfig.ready()`, so reverting them restores the two fields at the next
restart, and a `config` that still holds `client_id` from before is dropped on
the way out by `settings_for` either way. ⚠ **One thing a revert does NOT undo,
stated because the doc must not imply otherwise:** keys issued while this build
was live keep the scopes they were issued with. That is the point of the change
and it is not damage — but it is a fact about the world, not about the code.

## ⚠ A CITATION OF THIS LANE'S OWN, CORRECTED — `DEF-2804`'s SHAPE

`2.287.1`'s commit message and one comment in `ConnectorSetupPage.tsx` cite
**`DEF-INT-5538`** for the ceiling column. **`DEF-INT-5538` is a REAL ROW ABOUT
SOMETHING ELSE** — a sibling lane's hold-expiry cases — so the id never dangled
and **every id-existence check in the repo passed straight over it**. The
ceiling column is **`DEF-INT-5550`**. The comment is corrected; the commit
message cannot be, so it is corrected here, which is the only place a reader
would find it.

⚠ **AND A SECOND ID MOVED AT PUSH TIME, WHICH IS THE CHECK WORKING RATHER THAN
FAILING.** The create-only finding was filed as `DEF-INT-5553`, and
`allocate.py defect --verify 5553` — run UNCONDITIONALLY at push time, never
inside conflict handling (law 11) — answered **TAKEN**: a sibling had it on
another branch. It is **`DEF-INT-5554`**, renumbered by splicing ONE id field
of ONE row (never a `csv` round-trip, which re-serialises all 3,100 rows), and
**its two citations moved in the same commit** — this record and the
walkthrough's own comment. One commit message cites the old number and cannot
be edited, which is why it is written here. An id renamed without its citations
is `DEF-2804`'s shape, twice in one afternoon.

## 8 · Which build to look in — for the reporter

**`2.287.1`.** Open **Settings → Connectors**, press **Connect** on any of the
six connectors that read from you or send to you — the five finance systems and
the payment kiosk. There is no client id to fill in. Each API has its own
**On/Off** switch, and the ones you leave on are the ones the key you generate
may call. Save, then **Generate a key**, copy it, and open the connector: the
key is listed under **Keys we issue** with the APIs it may call beside it.

**Two things are NOT fixed in this build and are filed:** a connector you have
already connected in Production has no button to set up its Sandbox, and a key
generated while Sandbox is selected is issued against Production.

---

## `ACC-01` — *Who has been reading*, rebuilt to the drawing (`2.287.3`, 2026-09-16)

**What a clerk sees now that they did not before.** The panel at the foot of a
connection page used to say **"Nobody has collected anything yet."** in three
different situations, and that sentence is the reassuring one. We proved it in a
browser on this branch's own build: while the panel was still fetching, after
the fetch failed outright, and on a connector that genuinely had no reads, the
words on the screen were **identical**. On the one screen whose whole job is to
show a partner reading things they should not, that is an all-clear over a
question nobody asked.

It now says three different things:

* still fetching → grey loading bars, and no sentence at all;
* the fetch failed → **"The access log did not load"** over **"We cannot say
  whether anybody has read anything."**, with a **Retry** button;
* the partner really has read nothing → **"Nobody has read anything"** over
  **"This partner has a key and has not used it."**

That needed no new data and no new endpoint — the two facts were already on the
query and simply unread. It closes **`DEF-INT-5484`**.

**Two smaller things now match the drawing.** *"An access log, not a run
history"* was an orange badge floated right of the heading and is now plain grey
text under it. The **WATCH** note at the foot was a filled tan box and is now a
quote with a grey line down its left side.

**Three things this lane decided rather than built, each written down:**

1. The **WATCH** note explains why the screen exists, which our own rule about
   screen words forbids — and the drawing puts it there on a page marked *drawn
   to the rules*. It **stays**, and the question is **`OQ-INT-12394`**.
2. The drawing puts a **Revoke the key** button on this panel. Revoke is already
   built on this same page, a few hundred pixels higher, where a clerk can
   choose which key and is shown the consequence first. A second one here would
   be two ways to cut a partner off on one screen, so it is **not drawn** and
   the panel says why.
3. The drawing also puts an **Allowed addresses** button here, and there is
   nothing behind it anywhere in the product — no screen, no endpoint, no field.
   A button onto nothing is the defect we keep refiling, so it is **not drawn**
   and the gap is **`DEF-INT-5564`**.

**One thing found in the shared component kit and not fixed here.** The kit's
failure block requires a *Download error report* handler, so **98 of its 102
uses across the product pass a do-nothing function** and draw a live button that
downloads nothing. That is **`DEF-INT-5562`**; this panel composes its own
one-button failure block rather than adding two dead controls to a security
screen.

---

# Phase 3 · "please fix all view screen" — VIEW-17 rebuilt (`DEF-INT-5560`, `2.287.4`)

**Track: MAINTENANCE.** One question decides it — *can a user do this task in the
product today?* They can: a clerk opens a connector and reads its run history.
So reproduce · locate · blast radius · minimal fix · browser proof · regression ·
version · rollback · tell the reporter which build.

## What the PO said, from the deployed product (`2.287.2`)

> "this screen does not match with images in document - why?"

and, after a comparison chart:

> "please fix all view screen in that case"

**REPRODUCED** at `/brazosbend/settings/integrations/erp_aclarian`, signed in as
Dana Whitfield, at 1440 and 1280, against a stack whose backend was confirmed to
be this branch's before a single screenshot was believed.

## LOCATE · BLAST RADIUS

One file: `07-frontend/src/features/integrations/ConnectionDetailPage.tsx`. It
is the component behind all 28 `VIEW-` frames, so every connector's page moves
together — which is the PO's *"all view screen"* answered by construction rather
than by 28 edits. **What else used what was removed:** `ManagePanel` was split in
two and nothing outside this file referenced it; `data-manage` appears in no
test, no walkthrough and no gate (`ConnectModal.tsx` has `data-manage-head`,
which is a different attribute on a different screen) and is kept anyway on the
new footer. The three catalogue keys that lost their call site are listed in
`DEF-INT-5561`. **And one finding in a neighbour that this lane did NOT touch:**
`components/StateFrame.tsx` still teaches, in two comments a lane reads at
exactly the moment it is deciding, the rule CLAUDE.md retired by PO ruling on
2026-09-12 — that a Tailwind utility in a file outside `route-b-migrated.txt`
*"renders as nothing at all"*. It does not; the compiler scans the whole of
`src/`, and the real consequence is a red `G31` whose fix is to add the file to
the ledger. The wrong version costs the opposite reflex — reach for a stylesheet
class, which rule 21 forbids. `DEF-SHL-5563`; `StateFrame.tsx` has 102 callers
and two sibling lanes are live on this branch.

## The six rows of the chart this phase owned

| # | The drawing (p066–p067) | Before | After |
|---|---|---|---|
| 1 | `Keys we issue` · `Disconnect` at the BOTTOM, after the activity table | above it | one footer row, last on the page, under a divider, with the footnote right-aligned beside the buttons |
| 2 | **Recent activity** — sentence case, normal weight | **RECENT ACTIVITY**, 12px grey capitals | `<Panel>`'s own `<h3>`: `none, 16px, 800, rgb(32,30,29)` — measured in the browser as byte-identical to *Keys we issue* |
| 3 | a toolbar: search · `All` · `+ Filter ▾` · column chooser | present when runs exist, absent when none | unchanged where runs exist, now INSIDE the drawn panel; still absent on an empty list, deliberately — see the decision log |
| 4 | the activity table with its columns and pagination | present when runs exist; an empty state with a `Test it now` button when none | unchanged where runs exist; the empty block keeps `BR-SHL-012`'s shape and loses the dead button |
| 5 | no description lines | three sentences on one section | none on the populated screen; one helper sentence in the empty block |

## PROVED RED FIRST, in the harness that runs it

`npx vitest run src/features/integrations/ConnectionDetailPage.test.tsx -t "rebuilt to VIEW-17"` — six new cases, six failures against the shipped code:

```
× the footer row sits BELOW the activity table, not above it → expected null to be truthy
× *Recent activity* is the panel's heading, not small grey capitals → expected 'H2' to be 'H3'
× the toolbar and the table are INSIDE the activity panel → expected null to be truthy
× the section carries no description line → expected <p class="text-sm text-neutral-600"> to be null
× the empty block offers no control and no reason line → expected <button type="button" …(5)> to be null
× the append-only note rides in the footer row → expected null to be truthy
```

Then 27/27 green. **What would make each of them pass wrongly is answered in the
test file's own docstring**, because four of the six would: the catalogue value
is ALREADY sentence case and CSS uppercased it, the footer buttons already
existed, the toolbar already existed, and the dead button's prop already had a
caller. Every one of those is why 27 existing cases, `tsc` and every gate passed
over this for 34 releases.

## BROWSER PROOF (law 6 — no gate reads rendered output)

Bundle rebuilt and served from `07-frontend/dist`; the backend confirmed on this
branch by `GET /api/partner/v1/reference` answering `REFUSED` before anything was
believed. Walked at **1440 and 1280**, on three connectors covering all three
shapes — `erp_aclarian` (a key we issue, 4 APIs, a long run history),
`erp_workday` (a key we issue, **nothing run yet**) and `email_smtp` (a password
we hold, 5 runs). Read off the rendered DOM, not off a screenshot: section order,
`getComputedStyle` on every heading, and `scrollWidth > clientWidth`.

* order at both widths: `4 APIs on this connector` → `Keys we issue` → `Recent activity` (toolbar, table) → `Who has been reading` → the footer
* `Recent activity` heading: `[none, 16px, 800, rgb(32,30,29)]` — the same four values as `Keys we issue`; it read `[uppercase, 12px, 800, rgb(125,121,121)]` before
* footer at 1280: `Keys we issue` · `Disconnect` on the left, the footnote on the right, one line, no wrap
* no horizontal scroll at either width, on any of the three

## ROLLBACK

Revert the one commit. Nothing on the wire moved, no migration, no catalogue key
added or removed, no endpoint touched — the change is section order, one heading
element and the removal of one inert button.

## Which build to look in — for the reporter

**`2.287.4`.** Open **Settings → Connectors** and click into any connector.
*Keys we issue* and *Disconnect* are now at the very bottom of the page, under
the run history, with *"Runs are kept exactly as they happened"* on the right of
the same line. The run history is headed **Recent activity** in the same dark
heading as the two panels above it, and its search box, filter chips and table
now sit inside that section's own box. On a connector nothing has run on yet,
the *Test it now* button is gone — it never did anything.

**Two things are NOT fixed in this build and are filed:** the run table's second
column reads **WHAT RAN** where the drawing reads **WHICH API** (`DEF-INT-5565`),
and three catalogue values are now dead in all eleven languages
(`DEF-INT-5561`).


## 9 · The connector card counts its APIs (`DEF-INT-5528`, `2.287.5`)

**What the Product Owner said**, looking at the grid: *"on nepture - don show
all apis on screen - it is breaking the size of the box - you canjust mention
the number"* — and, after a build that had not fixed it, *"neptune list of all
apis also not removed"*.

**What it was.** The card drew one line per operation. `meters_neptune360` has
**sixteen**, so its card stood sixteen lines tall beside neighbours four lines
tall. Counted off the registry: **28 connectors, 87 operations, 10 of them with
more than three** — the grid drew **87 operation lines**.

**What it is.** One line per card: **`16 APIs · 0 working`**. The grid draws
**28 count lines**. A connector nobody has tested reads a bare `2 APIs`; a
one-API connector reads `1 API · 1 working`. Every card now carries its state
word, including a multi-API one.

**Where the detail went.** Nowhere — it was already on the connector's own page,
as a table with each API's direction, trigger, rate limit and last run, one press
away on `View`. The card is the summary. CON-01 p014 says so in as many words.

**The drawing decided it** (B14 rule 42, read as an image): **CON-01 p013** draws
no per-API list on any card, and p014 names Neptune — *"hiding the per-API lines
is the one thing that makes the grid scannable again"*.

**One signed rule was in the way and is NARROWED rather than ignored.**
`BR-INT-028`'s *"not one word averaging them"* had been read to forbid a state
word on a multi-API card, and the code implemented that reading. p013 draws the
opposite (`Esri ArcGIS`, three APIs, *● Not working*). **`BR-INT-028` is
PROPOSED and was never signed**, so B14 rule 41 settles it for the drawing; the
narrowing, its date and the quotation are written into the rule's own row. Had
it been signed this would have been a re-sign, not an amendment.

**The judgment the drawing did not make**, recorded in the decision log with its
reasoning: the `· N working` half appears when the connector **has been tested**,
not when the count is above zero. Both readings reproduce all nine cards the
blueprint draws; they part on a tested connector whose APIs are ALL failing,
where counting would print `3 APIs` — indistinguishable from *not tested yet*,
which is the one thing a clerk most needs to tell it from.

**What was proved RED first**, in `npx vitest run` and not in a bare node script:
three new cases in `IntegrationsTab.test.tsx` failed against the unchanged
component, and the failure output contained `Meter read 1</span>` — the sixteen
rows really were rendering. **The test that was there had to go**: the old
`TC-3` asserted `toContain("Account lookup")`, so it REQUIRED the list this
ruling removes, and its one surviving assertion (`data-operations="3"`) sits on
the new element as happily as the old and could never have caught this.

**Filed, not fixed:** p013 draws a coming-soon card carrying `1 API` and the code
still suppresses it — **`DEF-INT-5566`**. Measured in the browser: **12 of the 28
cards are coming-soon and show no line; all 16 live cards show one.** That is a line added to cards nobody
complained about, so it is its own change.

## 10 · Which build to look in — for the reporter

**`2.287.5`.** Open **Settings → Connectors** and look at **Neptune**. Its card
is now five lines — the category, the name, one sentence, its state word and
`16 APIs · 0 working` — where it was twenty. Every other card shrank the same
way. To see the individual APIs, press **View** on any connected card: they are
listed there with what each one does and when it last ran.

If you would rather see the API line gone altogether, the **▦** button on the
toolbar now offers it as **API count** and will hide it per person.

⚠ **AND ONE THING WENT WRONG IN THE MAKING OF THIS, SELF-REPORTED AS
`DEF-GOV-5567`.** The tip moved under this work — three sibling commits, nine of
the named paths — so every blob was re-derived from the new tip, which is law 11
working. The re-derivation then created its worktree with
`git worktree add … 2>&1 | tail -1` **under `set -e`**. A pipeline's status is
its LAST command, so `tail`'s zero masked git's refusal of a directory that
already existed, and the script walked into **a stale worktree another lane owned**
and wrote fourteen files into it. Nothing downstream could see it: `cd`, `cp` and
the catalogue fan-in all succeeded, and the diff that followed looked unfamiliar
rather than wrong. It was caught by reading that diff, restored file-by-file from
the owning commit's bytes with modes re-set from `git ls-tree`, and verified
byte-identical — that tree now shows only its own lane's two files. **Nothing was
committed or pushed from it.** The catalogues are what proved the damage bounded:
`i18n_fanin` appends rather than rewrites, so after removing the four keys it had
added, the only remaining difference was the one value it was told to overwrite.
**The lesson is not about worktrees: never put a CREATING command in a pipeline
under `set -e`, and assert the postcondition — here, that
`git -C <wt> rev-parse HEAD` is the sha you meant — before writing one byte.**

---

## ⚠ DATED SUPERSESSION NOTE, 2026-09-17 — `company_id` IS REMOVED FROM EVERY PARTNER API (`CR-111-BRC04`)

**This file's worked `403 COMPANY_MISMATCH` lines, its check-7 row, and its sentence
*"`company_id` is still accepted and still VERIFIED, never used to select"* all describe a check
the Product Owner has since removed.** They are left standing rather than rewritten, because they
are the record of what was BUILT and measured on 2026-09-16, and a build record edited to match a
later ruling stops being evidence of anything.

PO verbatim, 2026-09-17, replying to a plain-English explanation that `company_id` SELECTS nothing
but that a mismatch is REFUSED today:

> *"you will ahve to remove company ID filter from all Apis - we cannot tell tenant ID outside our
> system"*

**WHAT IS NOW TRUE.** `company_id` is **not required and refuses nothing**; it is **still accepted
and IGNORED** (Invoice Cloud's document sends it on every call, so refusing an unknown parameter
would break a partner for no benefit); **what they sent is RECORDED on the run row**, so a
misconfigured partner stays visible without being refused; and **`403 COMPANY_MISMATCH` disappears
from every partner route**, taking `_admit`'s check 7 with it. **The door goes from nine checks to
eight.**

⚠ **ISOLATION IS UNTOUCHED AND THIS FILE'S OWN ARGUMENT IS WHY.** `company_id` never isolated
anything — **key → connection → tenant → `app.tenant_id` → RLS `FORCE`** does, which is exactly the
diagram this CR quotes from blueprint p159 (*"Deriving it means there is nothing to check, because
there is nothing that can disagree"*). Removing the parameter removes a cross-check, not a guard.
`BR-TEN-003` is untouched, and `BR-INT-044` is not amended — one fewer route-specific refusal is a
**simpler** surface to read anything out of.

**THE CHAIN, stated not assumed:** PO 2026-09-16 *"company_id = tenant id"* (BUILT, and quoted
verbatim in `serve.py`'s docstring) → PO 2026-09-17 *"company_id = Keys will esnure it map to
tenant ID"* (recorded, **never built**) → PO 2026-09-17 *"remove company ID filter from all Apis"*
(**current, not yet built**).

**Current law: `BR-INT-070`.** Full record: `12-governance/02-decision-log.md` 2026-09-17 ·
[`CR-111-BRC04-invoice-cloud-partner-api.md`](CR-111-BRC04-invoice-cloud-partner-api.md) §2.

# Phase 4 · `CON-01` becomes a TABLE (PO override, 2026-09-17, `2.288.0`)

## 0 · What arrived, and what it overrides

Three rulings on one screen, all on 2026-09-17, verbatim:

> *"we are overriding the deciion and converting it form Grid -> Table - table only"*
> *"Action im looking for - Connect, View, Edit, Keys- based on this status will chnage"*
> — ratified over the full seven-row matrix as *"this is good - please add it"*
> *"Im good with these columes - please implment it"*

⚠ **THE FIRST ONE OVERRIDES THE BLUEPRINT AND B14 RULE 41, AND THAT WAS THE
FIRST THING WRITTEN DOWN — BEFORE A LINE OF TSX** (commit `efecfc56`, which
built nothing on purpose). The Integration Blueprint draws `CON-01` as a card
grid on p011–p013; it did not merely omit a table, **it considered one and
declined to draw it**, on p014, read as an image under B14 rule 42:

> *"If you would rather have a real table view behind a grid/table toggle, that
> is a different and larger change. Say so and I will draw it."*

The PO said so. Under `CLAUDE.md` law 13 a supersession is **STATED, never
assumed**, so it is stated in `12-governance/02-decision-log.md`, stamped at the
head of `CON-01`'s conformance record, and carried in `IntegrationsTab.tsx`'s
own header. **"Table only" is the load-bearing half: no toggle, and the cards
are gone rather than hidden behind one.**

⚠ **p014's ARGUMENT IS NOT REFUTED — IT IS ANSWERED BY THE SHAPE.** The
blueprint wants a `▦` chooser because *"Neptune's card is sixteen operation
lines tall beside neighbours four lines tall"*. A table row is one line tall by
construction, and `DEF-INT-5528` had already collapsed those sixteen lines to
`16 APIs · 14 working` the day before.

## 1 · What the ten columns cost, and the one thing they cannot carry

Every column reads a field `GET /integrations` has served since wave A —
**checked against `integrationsEndpoints.ts`, not assumed** — so this is a
front-end change end to end and `selectors.grid` is untouched. No new endpoint,
no new field, no backend wave.

⚠ **THE CARD'S SUMMARY SENTENCE HAS NO COLUMN, AND IT IS THE ONE REAL LOSS.**
*"Collect readings and keep the meter list in step."* is a SENTENCE, and
`tableTypes.ts` documents at length what a sentence in a cell does: it sets the
height of its whole row and wraps at whatever width the column happens to have.
**Keep the fact, lose the paragraph** — the sentence is on the Connector cell's
`title`, so it is still in the DOM, still reachable by a pointer and by a screen
reader, and still the first thing on the connector's own screen. The provenance
flags the blueprint draws (`NEW CONNECTOR`, `RENAMED`) were never built and are
not built now.

## 2 · The one thing the matrix does NOT say, kept deliberately

The ratified matrix decides enablement **by status**. Whether anything in this
product can actually DIAL a provider is a different axis, and it is already a
ruled refusal (`DEF-INT-4224`): with no adapter,
`POST /integrations/{key}/connect` answers *Cannot be connected yet.* at the
LAST step, after a clerk has typed a host, a port, a username, a password and a
send-from address. The PO met that as *"I cannot add any APIs - nothing ; no
test"*.

**So `Connect` keeps that hold as a fifth reason** — greyed, reading *"Not
ready to connect yet."* — and **this is flagged rather than settled**. Measured
on the demo tenant: of the 21 rows in *Not set up*, **7 offer a live Connect and
14 do not** (7 held on the adapter, 7 coming soon). Dropping the hold to match
the matrix literally would re-open a defect the PO has already reported once.

## 3 · Proved RED first, in the harness that runs it

`npx vitest run src/features/integrations/ConnectorTable.dom.test.tsx` —
**16 of 17 red before a line of the implementation existed.** The exact first
failure:

```
AssertionError: expected '<section class="flex flex-col gap-4">…' to contain 'data-cell="apis"'
 → the row has no actions cell: expected null not to be null
 → expected [] to deeply equal [ 'Connector', 'Category', 'Direction', … ]
```

⚠ **THE SEVENTEENTH PASSED AT BIRTH AND IS RECORDED AS SUCH** — *"no database id
reaches a cell"* is a REGRESSION guard, and the grid never printed an id either,
so it was correctly green over the old screen. A test that is green before the
code exists is not proof of the code; saying which one it is costs a line.

**Five false passes are named in the file before the first assertion**, each
closed by name: a header string that is ALSO a `+ Filter ▾` legend on the same
screen (closed by reading `<thead>` alone, as an ordered array); *the row has
actions* without asserting WHICH for WHICH state (closed by the four names, the
enabled/greyed split and every greyed one's reason, per row, for all seven
states); a one-state fixture (closed by `sevenStates()`); a `Why` column that is
structurally incapable of rendering; and a `connection`-backed cell inventing a
value when `connection` is `null` — 12 of the 28 rows.

## 4 · Proved in a browser, because no gate reads rendered output

`10-scripts/con01_connector_table_walkthrough.mjs`, against a stack whose
**bundle hash and provider count are printed before anything is looked at**.
At 1280 and 1440, all 28 rows:

| measured | result |
|---|---|
| columns, in order | 10 — Connector · Category · Direction · State · APIs · Environment · Where · Last run · Why · Actions |
| page scrolls sideways | **no**, at both widths |
| header wraps | none |
| rows taller than one line | **none** |
| four icons, in order, on every row | **yes**, all 28 |
| greyed icon with no reason | **0** |
| rows with no connection drawing a value in Environment/Where/Why | **0 of 14** |
| search *neptune* | 28 → **1**, footnote *"Showing 1 of 28"* |
| `▦` chooser | 10 columns, **7 locked, hideable: Environment, Where, Why** |
| sort by Last run | works — `09/15 03:54 | 09/16 05:12 | 09/16 05:17` |

**Neptune's row, the card that started all of this, now reads:**
`Neptune 360 | Meters | We collect | ● Not working | 16 · 0 working | Production |
Site SITE-4417 · Water me… | 09/16/2026 05:12 | No connection to the meter cloud. |
[Connect greyed "Already connected"] View Edit Keys` — **one line, 49px**, where
its card was twenty lines.

## 5 · Three things the browser found that no test could

1. **A sentence in a cell took Neptune's row to 122px.** The `Why` column was
   allotted 98px, so *"No connection to the meter cloud."* wrapped to four
   lines; 7 of 28 rows were over one line. Fixed with `block w-32 truncate` and
   the whole sentence on `title`. ⚠ `line-clamp-1` reads better and **is not in
   this theme's emitted stylesheet**, so it would have rendered as nothing while
   every check passed (`DEF-SHL-5088`'s shape) — checked against the BUILT css.
2. **`● Reading from us` wrapped in a 73px State column**, taking four more rows
   to 80px. The state is the fact the eye lands on first, so that cell is
   `whitespace-nowrap`.
3. **`16 · 0 working` broke after the dot** and rendered as two lines — a count
   pretending to be a sentence. Also `whitespace-nowrap`.

## 6 · Reds, dated — not called *pre-existing* on faith

* `components/regionalReachesTheScreen.dom.test.tsx` — *"nothing in the product
  falls back to a hand-written format"*, five offenders, **none of them in this
  change**: `BudgetBillsTab`, `SettleUpForecastPage`, `DisconnectWizard`,
  `TransferWizard`, `RunHistory`. Dated with `git log -S` rather than asserted:
  `DisconnectWizard.tsx` acquired `?? "UTC"` in `f6fa3670` on **2026-09-13**,
  four days before this lane started. **Not mine, and dated.**
* `connectorVocabulary.test.ts`'s exact key count went 343 → 364 and **was
  updated with its arithmetic shown**, not widened: 10 column headers + 2 API
  forms + 4 action labels + 3 greyed reasons + 2 empty-state lines = 21 NEW, and
  `integrations.intro` OVERWRITTEN rather than added (every language's second
  sentence described a CARD). 343 + 21 = 364 reconciles.

## 7 · What this lane got WRONG, self-reported

* **My walkthrough reported *"the search does not filter — 28 rows → 28"* about
  a screen whose search works perfectly.** `input[type="search"]` matches TWO
  boxes here and the FIRST is the app shell's universal search. It was one step
  from a filed defect against working code — law 7's *looking at the wrong
  thing*. Every list control in that script is now scoped to `.data-table-frame`,
  and the trap is written into its header.
* **Two walk thresholds could not distinguish pass from fail.** `> 34px` flagged
  all ten headers as wrapping (a header row is 35px in this theme) and `> 56px`
  flagged all 28 one-line rows as too tall (a one-line row is 59px). Both were
  reporting a fault on a correct screen, which is law 7 habit 3 exactly.
* **A probe left the column preference scrambled in the tenant's stored
  settings.** `BR-SHL-027` persists the `▦` set server-side, so after hiding
  three columns once, every later run measured the SEVEN-column table and
  printed *"ACTIONS visible: yes"* over a screen nobody had changed. Reset
  through the chooser's own *Reset table*; the walk now prints the column COUNT
  every run so a stored preference cannot fool the next reader.
* **I cited two defect ids in code comments before the allocator had answered**
  (`DEF-INT-5570`, which was never free). Corrected to the allocated
  `DEF-INT-5572` / `DEF-INT-5573` before the commit. Cite nothing until the
  allocator has spoken.

## 8 · Filed, not fixed

* **`DEF-INT-5572`** — the *Mappings* link was the ONLY door to `S143` in the
  product, and it is not one of the four ruled actions, so that screen is now
  reachable only by typing its address. **Hard-won law 2's mirror, in the same
  module that paid for `DEF-INT-5513` three weeks ago.** No fifth icon was
  added, because the matrix is ratified and *nothing in it is open*; the test
  was INVERTED rather than deleted, so restoring the door goes red and its
  author reads why it went.
* **`DEF-INT-5573`** — a greyed row action states its reason as a TOOLTIP only,
  which never opens on a touch screen. The card obeyed `DEF-SHL-4043` by drawing
  that reason as a LINE OF TEXT; a row has nowhere to put one. A B14 question,
  raised rather than settled here.
* **`DEF-INT-5577`** — all ten columns measure **1,346px inside a 1,120px
  frame** at 1440, so the Actions cell is off-screen until a clerk scrolls the
  table sideways. The page does not scroll, which is the sanctioned behaviour,
  but the four icons are the point of the ruling. **Hiding the three optional
  columns brings the table to exactly 1,120px and it fits.** It is a PO decision
  — default those three off, or keep ten and accept the sideways scroll — and it
  is raised with both figures rather than decided here.

## 9 · Version and rollback

**`2.288.0`** — a CHANGE and not a fix, so the middle number moves.
`allocate.py version --verify 2.288.0` answered *still free on every branch* at
push time. Written into `07-frontend/package.json`, `package-lock.json` (both
root entries) and `06-backend/pyproject.toml`, each **re-derived from the pinned
tip** rather than from the working tree, because a sibling lane had `2.287.6`
in flight in the same three files.

**Rollback is one revert of the front-end commit.** Nothing migrated, nothing
was written to the database, no endpoint changed and no stored data depends on
this. The only persisted state it touches is each user's own `▦` column set
under `table.S8.columns`, which is per-viewer and rebuilds from the declared
default.

## 10 · Which build to look in — for the reporter

**`2.288.0`.** Open **Settings → Connectors**. Where there were twenty-eight
cards there is now one table, one row per connector, with the search, the
category chips and the `+ Filter ▾` you already had. Every row ends in four
buttons — **Connect, View, Edit, Keys** — always in that order; the ones you
cannot use are greyed and say why when you hover them.

Two things to look at and tell us about:

* **The buttons sit off the right edge until you scroll the table sideways.**
  Press the **▦** button and switch off *Environment*, *Where* and *Why* and
  everything fits. We would like to know whether you want those three off by
  default.
* **The *Mappings* page** — the one that maps a vendor's words to ours — has no
  button pointing at it any more. Tell us if you want one back and where.
