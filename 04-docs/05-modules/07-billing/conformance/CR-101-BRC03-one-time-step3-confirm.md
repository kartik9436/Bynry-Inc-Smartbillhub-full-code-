# One-time bill · step 3 · `23 Confirm and send` — built, and what was not

**Blueprint:** `05-prototype/04 Billing, As Built.pdf` §04, entry **23**, pages
**p114–p116**, with **p101** (the two things every kind shares) and **p113** (a
collapsed kind on step 2) read for context.
**Method:** every page rendered with `10-scripts/pdf/pdf_render.py` at scale 2
and again at scale 4 over four crops, and read **as images** (B14 rule 42).
**Nothing in this record comes from `pdf_text.py`** — §04's mono meta lines lose
every digit, and this screen is almost entirely figures.

**Branch tip when this was built:** `0da36511`, rebased onto `9ff09a56` when the
shell lane published its contract mid-build — see §8.
**Files:** `07-frontend/src/features/billing/oneTimeConfirmShared.ts` (the
contract and the preview mapper) · `OneTimeConfirmStep.tsx` (the body) ·
`OneTimeConfirmMount.tsx` (the slot adapter) ·
`OneTimeConfirmStep.dom.test.tsx` (54 cases).

---

## 1 · WHAT WAS BUILT

The four drawn groups, in the drawn order, with the drawn columns.

| Group | Drawn | Built |
|---|---|---|
| 1 `WHAT IT WILL BILL` | `LINE · BASIS · AMOUNT`, ending in the deposit credit and the remainder | as drawn. Every row is the server's, including both totals and the credit's minus sign |
| 2 `IMPACT ON YOUR BOOKS` | `ENTRY · DEBIT · CREDIT · AMOUNT`, then the three-row remainder legend | as drawn, and the legend's row for **this** bill is marked `aria-current` and bold |
| 3 `THE SPECIMEN` | a `See the specimen →` control | **the control is NOT drawn** while nothing renders a specimen — see §3 |
| 4 `SEND` | `CHANNEL · NOW · WHY`, then two send options | as drawn, with the rows **served** rather than hardcoded — see §3 |

**One screen for all six kinds.** p115: *"The lines table and the books panel
are the kind's; everything around them is identical."* There is no branch on
kind anywhere in the three files.

**The panel sits before the button**, which is p115's own argument: *"This is
the only step that writes. Showing the three entries before the button means
the clerk is not the last person to find out what the bill did to the ledger."*

---

## 2 · TWO ABSENCES WERE WIRED, TWO REMAIN — and the pair that was wrong is why

⚠ **GROUPS 1 AND 2 WERE STATED ABSENCES OVER A LIVE SERVER FOR ABOUT AN HOUR —
`DEF-BIL-5323`, and it is the most instructive thing in this record.** The
backend half landed in `65d1e8e3`; this screen landed after it saying, in its own
words, *"`one_time.preview` returns … and not one money figure."* **That sentence
was true when it was written and false when it was committed.** Both commits were
right in isolation and the pair was wrong — hard-won law 2's mirror, a stated
absence over a live capability — and **nothing in this repo can see it**, because
no gate reads rendered output and a docstring's truth has a clock in it.

The cure is not a gate; it is the test block `DEF-BIL-5323 — the server serves
lines and books`, which feeds this screen **the shape the server actually
sends**. The next time that payload moves, the suite says so.

| Group | State | Evidence |
|---|---|---|
| 1 | **WIRED.** `lines[]` with their basis, `total` as `Charges`, the deposit and what is left | `one_time.py::_priced_body`, `_line_body`, `_settlement_preview_body` |
| 2 | **WIRED.** `books.entries[]` with account codes, the three verdicts, the refusal with both figures | `one_time.py::_books_body`, `posting_seam.preview_bill_entries` |
| 3 | **STILL ABSENT.** The specimen — the word appears nowhere in the billing module, and §03's sign-off records the same gap | `BillRunSignOffStep.tsx` docstring, p086 |
| 4 | **STILL ABSENT.** The channel list for one bill — `delivery_seam.DELIVERY_UNAVAILABLE` models the reasons and nothing serves them to a screen | `06-backend/apps/billing/delivery_seam.py` |

**Groups 3 and 4 still draw no control**, which is the thing this screen was
right to refuse and is unchanged.

Each remaining absence renders a `RunGap` — a `<details>` **closed by default**, which is B14 rule
32's own construction for a stated absence — carrying its reference on
`data-rule-ref`, where support can read it and a clerk cannot (rule 31).

**No fabricated zero, anywhere.** *"Nothing is owed"* and *"we could not work
out what is owed"* are different statements and only one is safe to press a
button under. `no lines served — it says so and fabricates no zero` and
`loading draws skeletons, never zeros` assert it, and both were **proved red**
before being trusted.

---

## 2b · THE MONEY READING, AND THE ONE FIGURE THAT MEANS TWO THINGS

The server serves **`total`** — what this bill charges — and **`closing_position`**
— `total + prior_balance`, composed by `settle_closing_position` under the PO's
`OQ-158` ruling, *"everything outstanding"*. **They differ by every dollar the
customer already owed**, and `final_bill.py` prices that difference at **$120.84**
on the prototype's own move-out: *"the difference between collecting and posting
a cheque to somebody in debt to the utility."*

**Three places had to choose, and each is labelled rather than left to be
inferred:**

| On screen | Figure | Why |
|---|---|---|
| `Charges` | **`total`** | It sits under the lines it is the total of |
| `Still due · to collect` | **`amount_due`** | The server's own settled figure; never `Charges − deposit`, which this screen must not compute |
| The refusal's second figure | **`closing_position`** | It is what `post_deposit_applied` actually compares the deposit against, so it is the only figure that explains the refusal |

⚠ **AND THE THREE ROWS OF GROUP 1 DO NOT FOOT FOR A CUSTOMER IN ARREARS**, because
`amount_due` already carries them. The honest fix was neither to invent an arrears
row the server does not serve nor to show a figure meaning more than its label:
**the BASIS column says what the number is made of** — *"Everything outstanding,
less the deposit"* — which is that column's whole job. The refusal's label moved
from *"This bill charges"* to *"Everything outstanding"* for the same reason. A
figure that silently means *bill plus arrears* under a heading reading *what this
bill charges* is worse than either figure alone.

⚠ **A TAX LINE'S RATE IS ITS `unit_price`, READ AS A FRACTION** — the engine says
the first half (*"a percent rule's unit price IS its rate"*) and `rating.models`
says the second on the column itself (*"percent form, fraction (0.0625)"*). Read
out of the schema, never guessed: `PercentCell` has no safe default and says so.

⚠ **`priced: false` IS `lines: null` PLUS THE SERVER'S SENTENCE, NEVER AN EMPTY
TABLE.** The preview sends `lines: []` and **omits `total` entirely** rather than
`0.00` — its own words: *"a zero here is a money claim about a customer, and on a
bill preview it is the claim that they owe nothing."*

⚠ **The drawn `, tiered` is NOT built.** The line body carries no rule type, and
inventing the word would be a claim about which rule priced the line on the screen
where that matters most.

---

## 3 · DIVERGENCES FROM THE DRAWING, RECORDED RATHER THAN BUILT

Numbered on from `CR-101-BRC03-one-time-wizard.md` §5, which ends at D7, and
**scoped to entry 23**. Screen 21's lane recorded its own six divergences in the
decision log on 2026-09-15 rather than with D-numbers, so nothing collides; a
later lane numbering from D7 again should read both.

| # | The drawing | What is built | Why |
|---|---|---|---|
| **D8** | group 3's `See the specimen →` control | the group renders a **stated absence and no control** | Hard-won law 2's MIRROR — a live screen behind a dead control, priced at *"two working doors out of eight"* on the portal front page. §03's sign-off reached the same conclusion about the same absence on 2026-09-06. ⚠ **The hold carries the test that fires when it expires, in this commit**: the live branch is built and asserted by ADDRESS, prefix-matched and refusing a leading `//` |
| **D9** | four explanatory sentences on the work surface — *"The lines are the kind's. There is no amount field and no parameter to pass one to."*, *"Three entries, three keys, so a re-run posts none of them twice."*, *"Same code and same guarantee as sign-off in §03 …"*, *"Only what can actually leave the building is offered. The rest is named, not hidden."* | **all four dropped**; each is recorded in `oneTimeConfirmShared.ts`'s docstring instead | §5 **D7** already ruled this — *"rationale is ZERO words on screen, and it is removed rather than shortened"* — and PO 2026-09-14, *"reduce the content to 5 to 6 meaningful words"*. The §03 one is also §5 **D6**: a document section reference is internal (rule 31). ⚠ Sentence 1's MEANING stays on screen in the shape rule 32 prescribes for it — the `Editing the charge lines` absence panel, which carry-over row 21 marks **NEVER REMOVE** |
| **D10** | the remainder legend's first cell, *"Posts. Three entries, three keys"* | *"Posts. One key per entry."* | B14 rule 37 — a drawn figure is an ILLUSTRATION. **Three** is what one final bill happened to produce; **one key per entry** is the invariant BR-BIL-005 actually guarantees. The entry count is visible in the table directly above |
| **D11** | the deposit basis written `150.00 + 3.50`, with no currency symbol | `$175.00 + $4.75` — each part through `MoneyCell` | BR-SHL-023 is **ONE** money formatting path, and a symbol-less second one is how `$8.2985` reached a customer (`DEF-088`). B14 rule 38: how a figure is CONSTRUCTED is the UI rules'; what it SAYS is the drawing's |
| **D12** | `Not available` drawn in a box, which reads as a disabled button | a `<span>` carrying the word, with its reason in the next column | BR-SHL-025's disabled-with-a-reason is about **controls**, and a channel state is not one. Asserted: the channel table contains **0** `<button>` and **0** `<input>`. Same conclusion as §03's Send step |
| **D13** | the two send options drawn as two **checkboxes** | ONE `role="radiogroup"` with two radios | B14 rule 38 — two mutually exclusive checkboxes tell a user they can have both. `DEF-569` is this repo shipping the mirror error and its finding is the rule: *"a control's shape is its promise about how many things can be chosen."* **What the two options SAY is the drawing's, verbatim** |
| **D14** | the footer consequence, *"This is the first thing that writes. It creates the bill, mints its number and posts to your books."* — 7 words then 12 | *"This step writes. It posts to your books."* — 3 then 5 | B14 rule 33's fourth kind: a consequence before an irreversible act is ≤ 6 words per sentence, at most two, **never cut below clarity**. Three acts do not fit two six-word sentences; the two a clerk cannot undo are kept and *mints its number* is dropped because *creates the bill* implies it. Asserted by `the consequence is two sentences of six words or fewer` |

### The two that are the PO's, not ours

| # | The conflict | |
|---|---|---|
| **D15** | **Two group headings exceed B14 rule 33's three-word cap for a label** — `What it will bill` (4) and `Impact on your books` (4) | Built **as drawn** under rule 41, and the conflict is recorded rather than settled. Same standing as the four-step run's `RunGroup` headings and as `D2`'s four-word rail label |
| **D16** | **The commit label `Create this bill & print` is five words** against the same three-word cap | Built as drawn under rule 41. It is also the one label that must follow the clerk's choice — *Leave it as a draft* renders `Create this bill`, because a button naming an act it is not about to perform is the one thing a consequence cannot survive |

**D15 and D16 are worth the PO's time; D8–D14 are rules 37 and 38 doing their
job.**

---

## 3b · THE CLAUSE THIS SCREEN OWES p101 — a bill that will only draft says so

p101, verbatim: *"A bill with no cycle has no days to pay of its own — your
ruling was that they are captured at billing time — so an empty field means the
bill **drafts and cannot be issued**. That is the rule refusing, not a guessed
due date starting a late-fee clock."*

**The refusal is at ISSUE, so step 1 lets a clerk walk past an empty `Days to
pay` — correctly. This screen is the last place before the irreversible act
where they can still be told.** Three things follow, and the third is the one
that matters most:

1. **The consequence changes.** *"This creates a draft bill. It cannot be sent
   yet."* — five words and five, B14 rule 33's consequence clause. What will
   happen; never why.
2. **The commit stops promising to print.** `confirmCommitLabel` returns
   `Create this bill` whatever was chosen.
3. ⚠ **THE SEND CHOICE IS NOT OFFERED AT ALL.** Drawing *Print it now* over a
   bill that cannot be issued is hard-won law 2's mirror — the clerk picks it,
   presses the button, and nothing goes. The radio group is **absent** and a
   FACT stands where it was, with the reason in the closed `<details>` rule 32
   prescribes. The channel table still renders: what the routes ARE has not
   changed.

⚠ **AND IT IS DERIVED FROM THE REQUEST, NEVER ASSERTED.** `OneTimeBody` has no
`due_days` member at all, so **no one-time bill carries days to pay today**
(`DEF-BIL-5311`, routed to the backend lane). `oneTimeIssuableFrom` asks the
BODY whether it carries the field rather than declaring that the product cannot
send — the `DEF-BIL-5252` shape. **So the hold expires by itself**: the day
`due_days` joins `OneTimeBody` and the mapper sets it, the answer turns on what
the clerk typed with no edit here, and `HOLD: the request carries no days to pay`
goes red and names the file.

---

## 3c · THE WORDS, IN ELEVEN LANGUAGES

Namespace `billing.oneTimeWizard.confirm.*`, **53 keys**, written into all
eleven catalogues through `10-scripts/i18n_fanin.py` — the tool that owns those
files — never by hand and never by a round-trip.

* `G15` parity: **0 missing, 0 extra**, and **403 NEW untranslated values before
  and 403 after** — this lane added none. Measured, not claimed.
* B14 rule 35 — *a catalogue is written in its own language, not translated from
  English*. One value came back byte-identical: Indonesian `Debit`. It is
  **`Debet`** now, which is the usual Indonesian accounting spelling beside
  `Kredit`, rather than an allowlist entry for an English word.
* ⚠ **Two keys were DELETED rather than translated.** `, {{note}}` and `" + "`
  are punctuation, and a catalogue value identical across eleven files is what
  `G15` correctly calls a paste-in. They are JSX now.
* The five channel words are the REAL codes from
  `apps/notifications/models.py` — `pdf_print`, `email`, `sms`, `in_app`,
  `portal` — read out of the model rather than guessed, and the test fixture
  uses them.

---

## 4 · WHAT THIS SCREEN WILL NOT DO

1. **It computes nothing.** No total, no subtraction, no negation. A screen
   subtracting two numbers it happens to hold is a second implementation of the
   bill's arithmetic, and the two disagree the first time a deposit moves
   between the two reads.
2. **It offers no amount field, and the enforcement is that there is nowhere to
   put one** — §04's one rule (p100). `ConfirmLine` is `readonly` throughout and
   no handler exists.
3. **It does not carry the commit.** B14 rule 38 puts a stepper's commit in the
   wizard-actions footer, where rule 6's danger tier is ENFORCED on rendered
   output and nowhere else (`DEF-712`). The shell reads `confirmCommitLabel`,
   `confirmConsequence` and `confirmBlockedReason` from the contract.
4. **It does not say a one-time bill cannot be sent.** `DEF-BIL-5252` — see §5.

---

## 5 · `DEF-BIL-5252`, AND WHY IT IS NOT CLOSED HERE

The sentence *"A one-time bill can be drafted but not sent yet"* has been false
since **2026-08-23**, when the PO closed `OQ-241` — *"it will be capture at the
time of bulk billing"* — and `create_one_time_run(due_days=…)` became that
capture. The backend deleted its matching row from `ONE_TIME_UNAVAILABLE` the
same day, with its reason. The frontend string did not move.

**It is not carried into this screen, and a test enforces that** — three
different prop combinations are asserted not to contain the sentence, its title
or the phrase. That guard was **proved red** by rendering the sentence.

**It is not CLOSED**, and that is deliberate: closing it means deleting
`billing.oneTime.awaits.send` from all thirteen catalogues **and** its render in
`OneTimeBillTab.tsx`, and the old tab stays live and out of this lane's scope.
Deleting the key alone would put the raw key on screen. It closes in the commit
that retires the old tab, which is the same commit the §04 record already names:
*"the `Sending the bill` panel is removed here, with the drawn Send group in its
place."*

---

## 6 · THE SEND ROWS ARE SERVED, AND THAT IS THE DECISION WORTH ARGUING FOR

The obvious build for group 4 is three literal rows in the front end: print
*Will go*, email *Not available*, the rest *Not available*. **`DEF-BIL-5252` is
precisely that build**, one screen over, three weeks old — *"The stated absence
is a HARDCODED frontend string … not a server-reported gap"* — and when the
question behind it closed, the screen went on stating the opposite of the
product with every gate, test and typecheck green.

So `ConfirmChannel[]` is served and nullable. `delivery_seam.py` already models
the reasons; reading them is the whole fix, and restating them here would be
filing the same defect a second time on the screen written to replace it.

---

## 7 · PROOF

* **54 cases**, all green: `vitest run OneTimeConfirmStep.dom.test.tsx`; the whole
  billing suite stays green at **39 files / 561 cases**.
* **Every new guard proved RED first**, through the same runner the green run
  used — the specimen hold, the `DEF-BIL-5252` absence, the unit rule, the
  radio-group rule, the rule-37 figure guard, the fabricated-zero guard and the
  idempotency-key rule.
* ⚠ **Three of them did not bite on the first attempt and the mutations were
  what was wrong — except the rule-37 guard, where the GUARD was.** Putting the
  drawn `9 / 30 days` into the source left it green, because neither `9` nor
  `30` is greppable alone. The drawn PAIR is, and `9 / 30`, `6.1 kgal` and
  `8.25%` were added to the list, after which the same mutation went red. A
  guard that misses the figure it was written for is law 7's *looking at the
  wrong thing*, and it was found by following law 7 rather than by a gate.
* **Six wiring guards proved RED first**, each naming its own assertion — the
  money one exactly: swapping `closing_position` for the wrong figure puts
  `$206.25` where `$520.11` belongs, and the test says so in those numbers.
* ⚠ **A SEVENTH GUARD WENT RED ON THE RIGHT ANSWER AND HAD TO BE TIGHTENED.**
  `B14 rule 31 — the posting event never reaches the screen` asserted the screen
  did not contain `issued`; the English label for that entry is *"The bill,
  issued"*, so a correct render failed it. It asserts the snake_case events only
  now, and adds the positive half — every entry shows its catalogue word.
* ⚠ **AND ONE RED PROOF LEFT ITS MUTATION BEHIND, WHICH THE SUITE CAUGHT AND
  NOTHING ELSE WOULD HAVE.** The script that breaks each guard in turn restores
  the file as its LAST act; it was run a second time piped to `head -10`, the
  pipe closed early, and the script was killed before that restore. The tax
  basis stayed at `points`, so `0.067300` read **`0.07%`** instead of `6.73%` —
  a wrong money figure on screen, sitting in a file that looked finished. It
  surfaced only because the suite was re-run on the re-derived tree.
  **`| head` on a script whose cleanup matters is a cleanup you have cancelled.**
* ⚠ **ONE BUG IN THIS LANE WAS FOUND BY READING ITS OWN DOCSTRING.** The
  contract says a channel's word *"comes from the catalogue, falling back to a
  sentence and never to the raw value"* — `G44`'s rule, and why `No reading
  (no_read)` once reached a billing clerk (`DEF-2882`). The code did
  `defaultValue: row.channel`, which is the raw value, copied from the
  four-step run's Send step. It now falls back to a sentence and keeps the code
  on `data-channel`; the guard was proved red by putting the old fallback back.
* **A TYPE-LEVEL PIN ON THE SHELL'S SLOT**, and it was proved red by widening
  the mount's own signature: `satisfies the shell's slot signature exactly`
  assigns `OneTimeConfirmMount` into `(props: OneTimeWizardStepProps) =>
  JSX.Element`, so the day that contract moves this file goes red and NAMES the
  step, instead of the mount quietly failing to fill a slot nobody has tried
  yet.
* `tsc --noEmit` clean · `eslint --max-warnings 0` clean on all four files.
* `G31` **PASS, 0 undeclared classes** — and proved load-bearing: removing the
  one ledger line takes it to **35 undeclared**, all named as this file's.
* `routeBUtilities.test.ts` 11/11.

### ⚠ TWO GATES DO NOT RUN IN A FRESH WORKTREE AT ALL

`G54 image-build` and `G98 lint-clean` **SKIP** whenever `07-frontend/node_modules`
is absent, which it always is in a new `git worktree` — the directory is
gitignored. CLAUDE.md's own advice is *"dispatch every lane into its own
`git worktree`"*, so the recommended way to work is also the way these two gates
go quiet. **The gate says so in words** (*"A SKIP here is this environment, not a
pass"*), which is the honest half; what is missing is that nothing tells a lane
its own build and lint were never run.

Measured here: with `node_modules` linked from the main checkout, `G98` is **RED
with 14 eslint errors across 11 files** — unused imports in customers, metering
and assets, **none of them this lane's** — and `tsc`, `vitest` and `vite build`
are all green over them (`DEF-CUS-3935`). A worktree lane sees a clean suite and
those 14 errors are invisible to it.

**Link or install before trusting a gate run in a worktree:**
`ln -s <main checkout>/07-frontend/node_modules 07-frontend/node_modules`.

### Two gates this lane moves, both stated rather than left to be noticed

* **`G40` unmounted-components** was **RED at 10 before this lane started**
  (measured at `0da36511` on 2026-09-15). `OneTimeConfirmStep` makes it **11**
  until the shell mounts it, and this lane may not mount itself. It returns to
  10 in the shell lane's commit.
* **`G38` stated-absences is BLIND to all four of this screen's absences**, and
  to 30 in the product, because `NOTE_ELEMENTS` is `("ArrivesWith",
  "ArrivesWithField")` and `RunGap` is neither. Filed as **`DEF-GOV-5321`**
  rather than written only here — *a finding recorded only in the file you
  happen to be in is a finding nobody can count.*

---

## 8 · HOW THIS MOUNTS — one line in the shell's registry

The shell lane published `oneTimeWizardContract.ts` at `9ff09a56`, mid-build.
Its `OneTimeWizardStepProps` hands a body `tenant`, `draft`, `patch`,
`goToStep` and `stepHref` — **no translator, no server data, no send choice** —
which is right: it is the WIZARD's contract and those are this SCREEN's
concerns. So the body stays purely presentational and `OneTimeConfirmMount.tsx`
is the seam. **The shell's registry line is one tag:**

```tsx
{ id: "confirm", render: (props) => <OneTimeConfirmMount {...props} /> }
```

⚠ The tag is written out rather than held as a value, which is the shell lane's
own rule: a registry rendering `<slot.body …/>` is a dynamic tag and `G40` goes
on reporting every body as unmounted dead UI, correctly.

⚠ **UNTIL THAT LINE IS WRITTEN, `oneTimeWizardSteps.test.tsx` IS RED AND NAMES
THIS FILE — AND THAT IS THE HANDSHAKE WORKING, NOT A DEFECT.** The shell lane
built the hold precisely so a body landing with no slot would say so:

    OneTimeConfirmMount.tsx is built against OneTimeWizardStepProps and no step
    opens it. Point ONE_TIME_WIZARD_BODIES at it and remove its step from
    HELD_ONE_TIME_STEPS — both in one commit.

That is the whole fix, it is two lines in the shell lane's own file, and this
lane may not make it: its scope forbids editing the shell to mount itself. **Do
not silence the test.** It goes green the moment `confirm` is wired, and `G40`
drops back by one at the same time.

⚠ **A SECOND RED IN THAT SUITE IS NOT THIS ONE AND NOT THIS LANE'S.**
`oneTimeWizardContract.test.ts` fails on the kind list — the TypeScript mirror
carries the drawn sixth kind `fee`, the server's `ONE_TIME_KINDS` has five, and
`DEF-BIL-5253` is that gap. `git log -S '"fee"'` dates it to `9ff09a56`, the
shell lane's own contract commit, and this lane's commit touches neither file.

**This lane needs nothing added to `OneTimeWizardStepProps`.** Step 2 previews
and step 3 needs the answer, and the contract carries the REQUEST rather than
the answer — but re-running the preview is the blueprint's own design, not a
workaround: p101, *"The preview writes nothing and is a POST precisely so a
clerk who fixes a plan and previews again sees the fix."* The draft in the
address bar is the whole request, so step 3's read is reproducible from a
bookmarked URL with no React state behind it.

`ConfirmStepProps` — `t`, `facts`, `loading`, `failed`, `send`, `onSendChange`.
**Nothing is optional**, which is hard-won law 2: a step body that needs
something absent from the interface widens it in one commit with the shell that
passes it.

The shell also reads three functions from the contract and owns the footer:
`confirmCommitLabel(send, t)` · `confirmConsequence(t)` ·
`confirmBlockedReason(facts, t)`.

### The commit bar is the shell lane's, and two things must go with it

`OneTimeWizardCommitBar` exists in `oneTimeWizardChrome.tsx` and **nothing
renders it yet** — the shell mounts a slot and stops. Step 3's foot needs it,
fed from this contract: `confirmCommitLabel(send, t)` ·
`confirmConsequence(t)` · `confirmBlockedReason(facts, t)`. A refused commit
then removes the button entirely, which is that component's own rule.

⚠ **Two things must be true before that button is drawn:**

1. **`& print` is a promise the caller has to keep.** `confirmCommitLabel`
   returns `Create this bill & print` only for `print_now`; until the commit
   actually reaches the print path it must be called with `draft`. A button
   that says it will print and does not is `DEF-BIL-5252`'s shape running the
   other way — a screen stating something the product does not do.
2. **The tier is wrong for the act.** The bar hardcodes `variant="primary"`,
   and this is the one irreversible commit in the wizard. B14 rule 6's own
   status column already names the hole — the danger tier is enforced on
   rendered output for `WizardFrame` and `ConfirmDialog` and is *"still
   unchecked: a commit button that composes NEITHER shared component"*. The
   four-step run's equivalent commit does carry the danger tier. Filed as
   **`DEF-BIL-5322`**.

⚠ **Exactly one thing blocks the commit and it is the one the drawing draws** —
the posting refusing when the remainder is owed to the customer, with the
server's sentence and both figures. Every other absence leaves the commit alone:
those are reads that failed, and stranding a clerk in the last step of a wizard
because a read failed takes away the only door they have.
