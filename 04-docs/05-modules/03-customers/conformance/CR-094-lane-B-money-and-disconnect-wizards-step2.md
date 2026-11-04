# CR-094-BRC01 · step 2 lane B — change plan, payment plan and the disconnect notice

**Three screens: 13 `S23` change plan · 14 `S24` payment plan · 12 `S90` disconnect.**
Drawn at `04-docs/05-modules/03-customers/blueprint/13-change-plan-wizard.md`,
`14-payment-plan-wizard.md` and `12-disconnect-wizard.md`.
Started from `ffe3a8152` (**`2.259.1`**); shipped at **`2.261.0`**.

**The ruling this lane is built on is one day old.** B14 rule 41, PO 2026-09-13,
verbatim: ***"it is expected that Product UI will match extactly the way it is
given in Blueprint document … only exception to the rule can be in case any rule
or BR is not matching or contrdicting - in such case you can ask us."*** So the
drawing is the scope, and only a drawn element that contradicts a signed rule
goes back to the PO.

⚠ **`DEF-CUS-5070` ROUTED THIS THE OTHER WAY ON 2026-09-12** — its prevention
column says *"a step-2 lane builds to the rendered ones"*, i.e. treat the
drawing as the stale document. That was the right reading of the rules that
existed that day. **Rule 41 reversed the default the next morning and the
product is now what moves.** The row is left as filed; this paragraph is the
supersession.

---

## 0 · HOW THIS WAS READ

**The product was booted and driven.** PostgreSQL 16, Django on `127.0.0.1:8031`
(a private instance, so the shared one on `:8011` was never restarted under the
other lanes), the front end built with `vite build` and served by `server.mjs`
on `:8081` with `API_PROXY_TARGET` pointed at it — the same-origin shape the
product ships. Signed in as `dana@brazosbendutilities.com` on `brazosbend`,
Chromium at **1280 and 1440**, the staff app's two required widths (PO
2026-09-10). Account **`A-11812 · Bramble Bakery`**, which is the account the
disconnect blueprint draws.

The blueprint text was quoted into the working notes rather than linked, per the
skill's §1. **The three wizards open as `ModalShell size="wide"` over the
account** (`BR-CUS-1051`, PO 2026-09-13) — the drawings show them as full pages
with the app nav, and that ruling is newer and wins on the CONTAINER. Everything
the drawing puts INSIDE was this lane's to match.

**Walkthroughs:** `census.mjs`, `walk.mjs` and `proofwalk.mjs` under the session
scratchpad, with screenshots and per-step JSON dumps beside them.

---

## 1 · SCREEN 12 — DISCONNECT · `S90` · step 3

### 1.1 · What the drawing has that the product did not

| drawn on step 3 | as built at `ffe3a8152` |
|---|---|
| `What has gone out already` — `NOTICE · SENT · CHANNEL · DELIVERED?` | **absent** |
| `Proof that it was served` — `Served by` · `Reference` · `Signed for on` · `Recorded by` | **absent** |
| *"No proof, no cut."* | absent |
| `How the next one goes out` — six channels | four |
| `The date` — the earliest lawful cut | present, and permanently unreachable |

### 1.2 · The finding, and why it is the important one

Step 3 rendered the refusal **"No final notice is recorded as served. Record it
first."** and offered **no control that could record one**. `assert_service_proved`
refuses a cut without a proof row, so **no cut could be scheduled from this screen
on any account in this tree.**

`POST /disconnect-notices/{id}/proof` has been mounted and answering since
**2026-08-28**, and `disconnects.notices_awaiting_proof` carried the words *"BUILT
AND NOT WIRED — hard-won law 2. No screen calls this yet"* **in its own docstring**
for the same fifteen days. That is hard-won law 1 in its purest form: a comment
naming a gap is a note, not a plan. → **`DEF-CUS-5169`, high.**

**Why nothing caught it.** Both halves are individually green: the endpoint has
server tests, and the screen's own suite asserts the refusal STRING is rendered,
which is true. **Nothing asks whether a refusal that tells a clerk to ACT is
followed by a way to do it.** `G13` asks whether a prop is passed; it cannot ask
whether a door has a handle.

### 1.3 · What was built

* **A new read** — `GET /accounts/{id}/disconnect-notices`
  (`transfer_disconnect_api.py`, `disconnects.notices_for_account`). The only
  notice read in the product was the TENANT-WIDE `awaiting-proof` queue, whose
  rows **named no account**, so a screen holding one household could not tell
  which letters were its own. `account_id` now rides on `proof_payload`, which
  the queue shares — a queue row with no account is a row a clerk cannot act on
  either. The read returns PROVED rows as well: the queue is a worklist, this is
  a record.
* **The drawn notices table**, each letter named the way the drawing names it —
  `Friendly reminder` · `10-day notice` · `Final notice` — keyed off the
  server's tier so a fourth rung needs no list retyped (CLAUDE.md law 12), and
  never `tier_3_48_hour` (B14 rule 31). `DELIVERED?` is a stated absence on
  every row and can never become a tick: `DEF-692`, nothing here delivers.
* **The proof block**, posting to the endpoint above, with its three refusals
  travelling on the control rather than appearing on press (`BR-SHL-025`).

### 1.4 · Two divergences from the drawing, recorded rather than guessed

**(a) `Served on` is drawn nowhere and the server requires it.** The drawing
gives the block four rows and one date, `Signed for on`.
`record_proof_of_service` requires `served_on` and treats `signed_for_on` as
optional, and its own docstring says why: a certified item is posted on one day
and signed for on another, **and the statutory period is counted from the
first**. Copying one date into both columns would manufacture a legal date, so
the field is drawn. *(Not escalated: this is a field the product needs and the
drawing omits, not a drawn element contradicting a rule.)*

**(b) `Recorded by` is not built.** The server holds a user id; B14 rule 31 keeps
a database id off a clerk's screen and no name is served. Stated, not invented.

### 1.5 · What is STILL blocked, and it is not this screen's fault

**`DEF-CUS-5174`, high — nothing in the product advances the ladder or records
that a notice went out.** `POST …/disconnect-case/advance` and `POST
…/disconnect-case/notices` are mounted and answer; a grep of `07-frontend/src`
finds **no caller for either**. Measured: **every notice in the tenant is tier 1
or tier 2 — nine notices, no tier 3.** The cut floor counts from the FINAL
notice, so it answers `notice_not_served` on every account and the date cannot
appear anywhere.

**So this lane removed one of two blockers.** It was hidden by the other: while
no proof could be recorded at all, a missing tier-3 notice was not the binding
constraint and nobody reached it.

### 1.6 · `DEF-CUS-5172` — four channels where the server has five

`transferDisconnectShared.SERVICE_CHANNELS` holds `certified_mail · email ·
text_message · door_hanger`; `disconnects.SERVICE_CHANNELS` and its
`ck_disconnect_notice_service_channel` constraint hold those **plus `posted`**,
and the drawing's `Served by` list names the same five. **That file is not this
lane's**, so the divergence is filed and the proof block names the server's five
locally with a comment saying to delete it when the shared const is fixed. The
drawn `In the portal`, a sixth on the *how it goes out* list, is likewise left.

---

## 2 · SCREEN 13 — CHANGE PLAN · `S23`

### 2.1 · `DEF-CUS-5170` — the screen printed its own repository to a clerk

Read off the rendered page in Chromium, 2026-09-13:

```
NOT CALCULATED  BR-CUS-042 says compute the category differential on a plan
change; BR-CUS-062 says there is no deposit recompute in v1. Both are CONFIRMED.
No differential is stated and none is registered.   BR-CUS-042 · BR-CUS-062 · OQ-179
NOT CALCULATED  B4.3 prorates usage as well as base. …   BR-RAT-004 · OQ-180
These part-period amounts were produced by apps.rating.engine.prorate_base_charge.
NET EFFECT ON THE NEXT BILL  $0.00   This total leaves out: deposit_differential, usage.
```

**Five rule and open-question ids, a Python module path, a function name and two
enum codes.** B14 rule 31 names every one of those families; rule 33 adds the
half that decided the shape of the fix — **RATIONALE is ZERO WORDS on screen** —
and the drawing agrees with both: it gives the deposit absence ONE sentence,
*"The deposit is not worked out again in this version. The amount set at move-in
stands."*

**Why `G28` reported zero, truthfully.** Its part 1 scans the eleven catalogues
and **none of these strings is in a catalogue** — they arrive at run time inside
a server payload and are concatenated into JSX. That is law 7's *reporting zero
over a scope it silently excludes*.

**Fixed by moving the reason, not deleting it:** the codes map to the screen's
own words, and `computed_by` rides on `title`, which rule 31 permits in terms
(*"the internal value may ride on `title` as evidence"*).

### 2.2 · `DEF-CUS-5171` — the head

| | drawn | built at `ffe3a8152` |
|---|---|---|
| kicker | `CHANGE PLAN` | `ACCOUNT A-11812` |
| title | `Pick a plan` → `When does it take effect?` → `Confirm the change` | `Change plan`, on all three |
| sub-line | `Step 1 of 3 · Plan` | `Step 1 of 3` |
| roll-up | `Current plan` · `Current base` | `Current plan` · `Services at this unit` |

`Services at this unit` was **removed**, under rule 41's *"which facts appear is
the drawing's"*. The fact it carried is not lost: the drawing states it as a
sentence under the picker — *"Only plans that cover this account's services are
offered."* — which is the same information in the form a clerk can act on, and
which was itself not built.

### 2.3 · Divergences recorded, not built

* **The drawing shows a `<select>`; the product keeps its radio list.** B14 rule
  38 — *where a drawing and our UI rules disagree about how a FORM is built, the
  UI rules win* — and the list is what carries each plan's base charge, its
  `Current` pill, the services it would drop and the rule that refuses it. A
  select can show none of those. **Recorded; nothing built.**
* **The drawing's step-2 footer is `← Back  Show preview →` with no Continue.**
  The footer is `WizardFrame`'s and is rule 38's again; the in-panel button
  carries the drawn words.
* **The drawn `History row  who · when · from → to · reason · source`** reads as
  a specification annotation rather than a row. Not built, and not invented.

---

## 2A · `DEF-CUS-5178` — THE DOOR THAT COULD ONLY FAIL, AND HOW IT WAS FOUND

**Found the moment `account-dialog-fit.mjs` stopped walking a hardcoded list of
seven controls and started DISCOVERING them from the rendered page** — which is
hard-won law 7's *reporting zero over a scope it silently excludes*, and the
scope it excluded contained this.

**Measured at 1280 and 1440 on `AC-2026-00052`**, a MASTER account with five
sub-accounts and `unit_id: null`: the Change plan dialog is **253px** where every
sibling is 648–836, and it reads

> **Failed · Change plan** — *"We could not find that. It may have been removed,
> or the address may be wrong."* — `Retry` · `Download error report` · `Cancel`

**The address was correct and nothing was wrong.** An account DERIVES its plan
from its unit (`BR-CUS-029` SUPERSEDED), this account holds none, and
`GET /accounts/{id}/plan-changes/options` answers **404** exactly as it should.
**The screen read an HTTP status as a failure when the FACT was already in its
hand.**

### What was built

`detail.unit_id` decides it, **before** the options read and now instead of it:
the query is disabled on an account with no unit, so the product no longer asks
a question whose answer it knows. The refusal is five words — *"This account
holds no unit."* — with *"A plan comes from the unit. Change it where the unit
is."* under it and the way back. **No `Retry`**: a retry over a business refusal
is a control that can only fail again, which is worse than no control because it
says the product thinks it might work. The card is **346px** now, at both widths.

### The half that is NOT this lane's file

The rail gates `Change plan` on `status_behavior_class` (`AccountDetailPage.tsx`),
and a master account is **active and billable** — so the control is LIVE. The
blueprint's own trace line for screen 13 says the door is *"live only on an
account that currently holds its unit"*: **the gate is written on a status and
the fact it means is occupancy of a unit**, and on this shape the two come apart.
Filed, not fixed here. The wizard now refuses properly whichever door opened it —
the rail, a typed address, or the Overview's Plan group under `R5`.

### One case that passed at the tip for the wrong reason

*"never says the address may be wrong"* was a pure `not.toContain`, and at
`ffe3a8152` the unseeded options read left a **loading skeleton** on screen —
which contains the failure copy no more than the refusal does. **A negative
assertion cannot tell "the words are gone" from "nothing rendered."** It asserts
the refusal is PRESENT in the same breath now, and all four cases go red at the
tip.

### And the second finding in the same report did not reproduce

`Disconnect notice` was reported as not opening at 1440 in one run. It opens and
measures **836px at both 1280 and 1440** across three runs since. Recorded as not
reproduced rather than dismissed.

---

## 3 · SCREEN 14 — PAYMENT PLAN · `S24`

Five of the eight step-1 labels were different words, and both remaining drawn
lines under the schedule were absent. All are the drawing's now:

| drawn | was |
|---|---|
| `Cadence` | `How often` |
| `First due` | `First instalment due` |
| `Take by autopay` | `Charge instalments to the method on file` |
| `Suspend late fees while the plan runs` | `…on these arrears while the plan is current` |
| `Suspend disconnect while the plan runs` | `Suspend disconnection while the plan is current` |
| `The arrears position, not the current bill.` | `It cannot be more than the account owes.` |
| `AMOUNT` · `LEFT` | `Instalment` · `Remaining` |
| `The remainder lands on the FINAL row…` | absent |
| `Progress 0 of 5 paid` | absent |
| `Email` · `SMS` · `Print` | `Email` · `Text message` · `Print for signature at the counter` |
| `Send agreement ✓` | `Queue agreement` |

**No drawn figure is built to (B14 rule 37).** The drawing's `$612.75 · $112.75 ·
5 · $100.00` are illustrations and are internally consistent, which says the
drawing was reasoned rather than sketched and nothing more. The progress count is
computed off the schedule the SERVER returned, never off the number typed in
step 1. ❄️ `GT-47` stays the fixture.

### 3.1 · ⚠ THE ONE THING THAT SHOULD REACH THE PO

**The drawing puts `Signed on` and `✓ Record signature` on step 3, BEFORE `Send
agreement ✓`.** The product records a signature on a plan whose agreement has
already been queued, which is `BR-CUS-044` — the plan activates on the
customer's signature, and activation is a clerk **recording a signature they
hold**. Building the drawing literally would have a clerk attest to a signature
on an agreement that does not exist yet.

**This is rule 41's narrow exception — a drawn element that contradicts a
business rule — and it is the only one in these three screens.** It is stated
here and **not built**; the two fields stay where the rule puts them, on the live
plan panel.

---

## 4 · MONEY — correct on all three, and checked rather than assumed

Every figure rendered two decimals at four-decimal storage. Not one of these
three components divides, adds, subtracts or rounds: every amount is a
`NUMERIC(18,6)` string the server produced, drawn through `MoneyCell`. The
payment plan's instalments are sent BACK to the server to be re-summed; ❄️ B4/B5
were not approached and no signed figure moved.

---

## 5 · RULE 33 AND THE DRAWN COPY — recorded, not silently resolved

Rule 41 says build the drawing; rule 33 caps a heading at **3 words** and a fact
at **6**. Several drawn strings are longer — `What has gone out already` (5),
`Proof that it was served` (5), `Only plans that cover this account's services
are offered.` (9). **The drawn headings were built and are recorded here**, on
three grounds: rule 33's status column reads *"NOT ENFORCED for these five
kinds"* and its 606 over-cap strings sit in a shrink-only baseline; the screens
already carry drawn headings of that length (`Why is service being cut?`,
`Protections — anything that stops this`); and escalating a five-word heading
would put dozens of questions to the PO that law 13 says are ours to decide.

**Every REFUSAL string this lane wrote is at or under six words**, because that
half of rule 33 IS enforced (`G33`). The longest drawn sentence was shortened to
`Only plans covering this unit are offered.`

---

## 6 · HOW IT WAS PROVED

* **29 new cases across three suites, every one shown RED FIRST** in a `git
  worktree` at `ffe3a8152`, through **`npx vitest run`** — the harness that runs
  them and never `__main__` (`DEF-GOV-3733`). 26 red on the first pass; **two of
  the three that passed did so for a bad reason** — they built the expected
  string out of the same catalogue the screen renders from, so both sides moved
  together and the case passed over the very defect it was written for. Rewritten
  as literals, they go red too. (The third is a regression guard on behaviour
  that already held, and says so.) That is law 7's second habit — *ask what would
  make this check pass wrongly* — catching a check as it was being written.
* **The write was driven in a browser.** Step 3's three refusals fire in order
  and each names what is missing; the POST answers **201**; the table's `CHANNEL`
  column fills with `Certified mail`; the block moves to the next unproved
  letter. **The floor still says "Record it first"** — correctly: the proved
  letter is tier 2 and the floor counts from the FINAL notice. See §1.5.
* **`0 divergence(s)`** from `acc02-tab-conformance.mjs`, **`0 finding(s)`** from
  `account-dialog-fit.mjs` (14 frames), `G27` green, `npx tsc --noEmit` clean.

### The reds this lane did NOT cause, dated

**Ten cases, all red at `ffe3a8152` — proved by checking out that commit in a
worktree and running them there, not by asserting it** (`DEF-CWP-4187`: two
lanes have called a red pre-existing in good faith when one of them caused it):
eight in `AccountDetailPage.test.tsx`, one in `AccountPanelEdits.dom.test.tsx`,
one in `accountRailHoldExpiry.test.ts`. Gates `G15` (326 untranslated), `G18`
and `G33` were likewise red before this lane started.

**Four reds this lane DID cause and fixed**, in `AccountActions.test.tsx` —
outside the declared write set, and touched deliberately: they asserted `OQ-179`
and the server's engineering sentence were ON SCREEN, which is the rule-31 breach
`DEF-CUS-5170` removed. Leaving them would tell the next lane to put the ids back.

---

## 7 · TWO LANE-COLLISION NOTES, for the record

* **A sibling's commit published this lane's 82 catalogue keys and five defect
  rows** before it pushed them — `4062c1226`, a pathspec commit naming the
  shared catalogues, which takes the whole working-tree content (`DEF-168`,
  mechanism five). **Nothing was lost** and the keys are correct; it is recorded
  because the register and the catalogues are where this keeps happening.
* **`push_paths.sh` refused this lane's first push** on the register, exactly as
  designed — the file had moved under it. Re-derived from the pinned tip,
  appended, and the byte-prefix proved identical before pushing again; the
  sibling's six in-flight rows were held back and written straight back to disk.

---

## 8 · WHAT IS LEFT

| | |
|---|---|
| `DEF-CUS-5174` | no control advances the ladder or records a notice, so no account reaches tier 3 and the cut date still cannot appear |
| `DEF-CUS-5172` | the shared channel list is four where the server and the drawing are five |
| `DEF-CUS-5070` | superseded by rule 41 for these three screens; still open for `S68` account import, which this lane did not touch |
| `OQ-179` · `OQ-180` | both OPEN; no deposit or usage figure is invented and the screen says so |
| `DEF-CUS-5178` | the Change plan DOOR is still live on an account with no unit; the wizard behind it refuses properly now |
| §3.1 | the drawn signature placement, for the PO |
