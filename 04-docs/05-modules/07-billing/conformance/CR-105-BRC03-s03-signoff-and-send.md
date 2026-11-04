# §03 entries 18 and 19 — Sign off and Send, built

`CR-105-BRC03` · 2026-09-14 · the two commit-side bodies of the four-step bill run

**What was built.** Three new front-end files and two suites, and nothing else. The wizard
shell, the rail, the routing, the Scope step and the band strip belong to other lanes and
none of their files was touched.

| File | What it is |
|---|---|
| `07-frontend/src/features/billing/billRunFourStepShared.tsx` | the props contract, and the pieces both bodies share |
| `07-frontend/src/features/billing/BillRunSignOffStep.tsx` | entry 18, STEP THREE — p082–p084 |
| `07-frontend/src/features/billing/BillRunSendStep.tsx` | entry 19, STEP FOUR — p085–p086 |
| `…/BillRunSignOffStep.dom.test.tsx` · `…/BillRunSendStep.dom.test.tsx` | 30 cases |

**How the drawing was read.** Every page rendered to PNG and read AS AN IMAGE (B14 rule 42),
`10-scripts/pdf/pdf_render.py` at scale 2.0, with a 5× crop of p083's footer band where the
tick and the commit sit. The source is `05-prototype/04 Billing, As Built.pdf`, sha256
`137a2a48…0971`, which matches the element inventory's recorded hash. The text layer was not
read for anything.

---

## 1 · The props contract lane 1 mounts these behind

**The shell's own contract landed mid-build** as `07-frontend/src/features/billing/runWizardContract.ts`
(`938b61a9`), and these bodies were rebuilt against it from the tip rather than against a
guess. It reached two of the same conclusions independently, which is worth recording because
neither lane saw the other's file: **the commit bar belongs to the frame** (B14 rule 38) and
**nothing in a step's props is optional** (hard-won law 2). `signOffCommit()` and `sendCommit()`
below return the shell's own `RunWizardCommit`, so the frame's bar is fed rather than
re-implemented.

Neither body consumes `RunWizardStepProps`. Sign off needs no address at all, and Send builds
its one link through `useTenantPath()` — the app's single way to compose an address, whose own
rule is that *"screens never write `/${tenant}/…` themselves"*. The `tenant` string on that
interface is therefore not read here; taking it and interpolating it would be the hand-written
form that helper exists to prevent.

Neither body fetches, routes or commits. Both are controlled: the shell owns the query, the
tick state and the commit.

```
BillRunSignOffStep  { t, cycleLabel, facts: SignOffFacts, gate, onGateChange, loading, failed }
BillRunSendStep     { t, cycleLabel, facts: SendFacts,   gate, onGateChange, loading, failed }
```

`gate` is the SAME `GateState` record the six-step wizard already keeps, so
`releaseConfirmations(gate)` still sends exactly BR-BIL-058's five and nothing else. Each
body adds one key of its own to that record — `SIGN_OFF_REVIEWED`, `SEND_OPENED_ONE` — which
`untakenGateFacts` cannot see, because it reads `GATE_FACTS` rather than the record's keys.

Four helpers are exported for the shell's footer, because **the commit button is not in
either body** (see §2):

```
signOffBlockedReason(gate, t) -> string | null     signOffCommitLabel(bills, t)
sendBlockedReason(gate, t)    -> string | null     sendCommitLabel(bills, t)
```

**Every prop is REQUIRED and nullable where the fact may be unknown.** Nothing is declared
optional, deliberately: an optional prop that guards a feature is the shape `G13` refuses, and
a `null` that the shell passes explicitly is a fact, where an absent prop is an accident.

---

## 2 · Divergences from the drawing — recorded, not chosen silently

### 2a · The commit button is the wizard footer's, not the body's — **built per the rule**

p083 draws `Sign off and create 1,260 bills` inside the screen's own footer band and p086
draws `Send 1,260 bills` the same way. **B14 rule 38 settles it against the drawing**: where a
drawing and our UI rules disagree about how a FORM is built, the UI rules win, and where a
stepper's commit lives is construction rather than layout (rule 3 — *"the numbered step rail +
a wizard-actions footer"*).

It matters beyond tidiness. **B14 rule 6's danger tier is ENFORCED on rendered output through
`WizardFrame`** (DEF-712) and through `ConfirmDialog` (DEF-718), and rule 6's own status note
records the remaining hole in as many words: *"still unchecked: a commit button that composes
NEITHER shared component"*. A button composed in these bodies would put **the one irreversible
act in the bill run** in exactly that hole. So the bodies carry the words, the counts, the
ticks and the consequence line, and the frame carries the button.

A test in each suite asserts the body composes no commit button, and each was proved red by
adding one.

### 2b · The five gate facts are on Sign off, and p083 does not draw them — **built per the map**

p083 draws ONE tick. The blueprint's own carry-over map (p086–p088) **row 19** puts all five
of BR-BIL-058's facts on this step, `UNCHANGED ×5`, `BR-BIL-058 untouched` — and
`release.authorise_release` refuses the release while any is missing, naming the one that is
absent. Building the page literally would have deleted a signed rule on the strength of an
omission.

So the gate band is **six** controls: the five, in their recorded order and with their existing
labels from `GATE_FACTS`, then the drawn tick. The drawn tick is not a sixth recorded fact and
is never sent as one — p084 says what it is for: *"Not a general `are you sure`. It names the
24 and the 1, because those are the two things a clerk can still do something about."*

Proved by sabotage: deleting the five leaves `Unable to find a label with the text of: I
confirm this run meets our compliance checks.`

### 2c · The group headings exceed B14 rule 33 — **built as drawn, and FILED**

`Where the money stands` is four words, `What is not being billed` five,
`Look at one before it goes` six. Rule 33 caps a heading at three.

**`DEF-BIL-5306`.** Built as drawn under rule 41 — *"the drawing IS the scope"* — and filed
rather than settled in a lane, which is what rule 41 requires of a drawn element that
disagrees with a signed rule. Nothing checks either side: rule 33 is unenforced for its five
kinds and rule 41 has no check at all, so a lane could silently shorten every heading and
nothing would say it happened.

### 2d · `See the specimen →` is not drawn live — **built as an absence**

p083 draws the control. p086 says the specimen does not exist: *"it is genuinely new work: the
renderer exists but only from a sample invoice, not from this run … it is the one thing on
this screen I would build next."* A control that opens nothing is the live-screen-behind-a-
dead-control failure hard-won law 2 records as costing **more** than dead UI, so group 6
renders a stated absence and draws no control until `specimen` is supplied.

### 2e · The one drawn element that is column-headed differently

p082's group 1 draws two column headers, `POPULATION` and `ACCOUNTS`; §5.7 of the element
inventory records only *"column header is `POPULATION`, once"*. The drawing is built. Not
filed — B14 rule 37 territory, and p084's own annotation (*"It is `Population` now, or blank
where the rows name themselves"*) agrees with the drawing.

---

## 3 · What these two screens need and NOBODY SERVES

**This is the backlog these bodies make visible.** Each renders a stated absence today, never a
zero — which is the summary read's own ratified discipline: *"`covered: null` IS NOT ZERO AND
MUST NEVER RENDER AS ZERO … the second one is about to sit under a person's signature."*

| Screen | Group | Fact | Status today |
|---|---|---|---|
| Sign off | 1 | Regular / Master split | **not served.** p084 calls it *"a small addition"* — the account's kind is on the row the run already reads |
| Sign off | 4 | `WHERE THE MONEY STANDS`, all five lines | **not served at all.** No read answers owed-before, payments-applied-since or owed-after for a run |
| Sign off | 5 | In arrears · On the final rung | **not served.** Needs a past-due figure, which billing already refuses for a stated reason: the tenant's business clock does not reach this path, and a wrong past-due is a claim about a customer's money |
| Sign off | 6 | The specimen | **not built** — `BIL-S50`, named on p086 as the next thing to build |
| Send | 1 | The three chosen bills | **not served.** Nothing picks a surprising, an ordinary and an estimated bill out of a run. The DOOR is real: `/{tenant}/billing/bills/{id}/document` is routed and live |
| Send | 2 | The channel table | **not served per run.** `release.UNDERIVABLE_AXES` says why in its own words, and the reason is permanent for this panel: the rows are written at issue, and the account's delivery ELECTION is PROPOSED-SCHEMA and unbuilt. **The drawing already says exactly this** — `Nobody elected`, `Not offered here` |
| Send | 3 | AutoPay | **not served.** Billing has ONE reviewed cross-module FK into customers and none into payments' mandate tables, so the count would be a cross-module reach B1/B2 forbid |

Groups 2 and 3 of Sign off are served whole by `GET /billing/runs/{id}/summary`, and group 1's
in-scope and bills-to-create counts with them.

### 3a · The batch work the PO named, against what is registered

The PO's correction: *"you will need batch jobs to write bills, create pdf and save them, send
email text messages, process autopay ech - you did not include them"*. Billing registers
**five** job kinds — calculate, findings, issue, reprice and the print set.

* **write the bills** — `enqueue_issue`, built.
* **render and store the documents** — `enqueue_print_set`, built; `Print set` is the drawn
  header action on p085 and is a real control.
* **send email and text** — no dispatcher and no sender exists in any module. This is what
  *"Nothing leaves the building"* has always meant, and carry-over row 21 keeps that sentence
  on step 4 word for word.
* **process autopay / ACH** — billing issues and does not collect; p086 draws it as
  `Handed to Payments` for that reason.

**And the four-step split needs a decision the six-step never had to make.** Today
`commitRelease` does release **and** issue in one act at step 6. The drawing puts bill
creation at step 3 (*"Sign off and create 1,260 bills"*) and step 4's own line reads
*"1,260 bills created"* — so issue moves to step 3 and step 4 needs something of its own to
commit. **There is no dispatch endpoint.** This is the shell's call, not these bodies'; both
are built so the shell can wire either shape without either file changing.

---

## 4 · Two things this lane found and could not fix in its own scope

* **`DEF-BIL-5302` was closed by another lane while this one was building** (`78930358`, then
  `fbf07102`), so the sign-off gate now refuses a run whose template cannot be resolved.
  Nothing was papered over in the UI here while it was open, deliberately: a screen refusal
  standing in for a database gap reads exactly like the gate working, and would have had to be
  hunted down and removed once the real refusal landed.
* **The `flagged bills cannot be listed` panel belongs to step 2, not to these two.** It is
  mounted today inside the six-step wizard's step 4, and carry-over rows 14, 15 and 18 all map
  that step onto the new **step 2 Check**. §10's instruction that the panel MUST STAY
  (`DEF-2855` is open) therefore falls to whoever owns step 2. It was not moved onto step 3 or
  4, because inventing a placement is how an element quietly changes screens.

---

## 5 · Proof

**30 cases, 2 suites, all green.** `tsc --noEmit` clean; `eslint --max-warnings 0` clean on all
five files; `routeBUtilities.test.ts` green with the three new files on
`src/styles/route-b-migrated.txt` — and proved to COVER them by planting `itmes-end` in one and
watching it go red.

**Twelve sabotages, each run through the harness that runs the tests (hard-won law 7).** Ten
bit first time. **The two that did not are the useful part:**

* **The B14 rule 31 guard could not see half the screen.** It mounted Sign off with every group
  SERVED, so none of the four stated-absence panels rendered — and a gap panel is exactly where
  an internal reference leaks, because it is the thing that exists to explain itself. The
  sabotage came back GREEN. That is law 7's *"reporting zero over a scope it silently
  excludes"*. The guard now runs over both renderings and the sabotage bites.
* **The fixture sabotage corrected a claim this lane had written down.** Breaking the route
  pattern to a bare `path="*"` — the shape that hid the customer portal's six dead doors —
  changed nothing, because **the staff app does not resolve its tenant the way the portal did**:
  `useTenant()` reads `useLocation().pathname`, not `useParams()`, and `tenantPathFrom` returns
  a bare segment when no tenant is in scope, so it cannot emit the protocol-relative `//…` that
  made a broken portal address read as a good string. The portal failure mode is unreachable
  through this helper. A second case now pins the LOCATION, which is what actually decides.

**Two gate findings against these files were real and are fixed.** `G86` caught a hand-rolled
button in the specimen group — B14 rule 36, the shared kit is how you comply — now `Button` and
`SelectField`. `G44` caught `{words[state]}`, *"a renderer that does not NAME its field cannot
format it"*, now a named branch per state.

**One gate finding is real and cannot be fixed here: `G40` unmounted-components rose by two.**
Both bodies are dead UI until the shell mounts them, which is hard-won law 2 stated exactly
right. **It is not baselined** — silencing law 2's own gate to hide law 2's own finding would be
the worst available move — and it closes the moment lane 1 mounts them.
