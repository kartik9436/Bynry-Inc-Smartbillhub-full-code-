# `CR-101-BRC03` · step 2 · §06 **Fix a bill** · lane L — the two wiring gaps that made a drawn screen unreachable

**Lane:** L, following lanes A (step 1) and E (step 3 and `26.4`).
**Branch:** `claude/gifted-johnson-top7zn`, worktree `agent-a562936d9344dbfb1`.
**Base tip:** `01e0e586` at the start; **`dd6f9f0f` at the first push (`1801f28a`)** — the
eleven catalogues moved under this lane while it was building and `push_paths.sh`
refused, correctly; every one was re-derived from the pinned tip before anything
was pushed (§7). **Date:** 2026-09-15.
**Process:** `22-product-maintenance-process.md` — a live screen that does not do
what it is expected to do is MAINTENANCE, and the first three steps are reproduce,
locate, blast radius.
**Built through** `react-tailwind-css-ui-generator` (loaded before the first line
of TSX and again before this record) and `build-one-commitment-end-to-end`.

**What this is.** Two defects lane E filed against lane A's files. `DEF-BIL-5368`:
the wizard never collected or sent the goodwill credit, so **no goodwill
correction could be opened at all** and screen `26.4` — built, routed, tested and
translated into eleven languages the day before — had no reachable case in the
product. `DEF-BIL-5381`: the wizard never sends a posting period, so
`BR-BIL-045`'s *"the preview NAMES the posting period before confirm"* is never
satisfied from this screen.

**What this is NOT.** It changes no step body, no correction engine, no figure and
no signed rule. It touches `fixABillSteps.tsx` nowhere — six lanes were in that
file today.

---

## 1 · Which pages were read, as images, and at what scale

B14 rule 42 — *"a screen is built from the drawing AS AN IMAGE; extracted text is
an index, never the specification."* No call was made to the text extractor.

| Page | Read at | What it gave this lane |
|---|---|---|
| p133 | scale 1.5 | screen `26`'s group 2 table, **group 3 `WHY — PICK ONE OR MORE` drawn as `REASON · CLASS` with Goodwill TICKED and no amount box anywhere**, and group 4's sentence for exactly that case |
| p134 | scale 1.5 | screen `26`'s footer (*Nothing is written.* · *Continue →*) and its **five annotations** — *"Eighteen rows, five of which refuse"*, *"Group 4 is the design of this screen … The operator picks a reason; the system says what it will do"* — which is what decided where the field goes |
| p138 | scale 1.5 | `26.4 Goodwill`: the answer band and group 1 `THE CREDIT` drawn as a **read-only** three-row table — *Goodwill credit, agreed with the customer `$40.00`* · *Tax on it `$0.00`* · *Credit on the account `$40.00`* |
| p139 | scale 1.5 | `26.4`'s group 2, its two absent panels, its footer and its **four annotations** — none of which says where the figure is typed |
| p141 | scale 1.5 | `26.6`'s `WHAT YOUR BOOKS DO` panel — `ENTRY · DEBIT · CREDIT · AMOUNT`, the net, *"Two entries, never one netted together."* |
| p142 | scale 1.5 | `26.6`'s loose ends and footer, and its five annotations |

The PNGs were already rendered at scale 1.5 by `10-scripts/pdf/pdf_render.py`
into the wave's shared `SCRATCH/billing/` and were read with the Read tool.

### ⚠ The finding that came out of reading them

**THE BLUEPRINT DRAWS NO INPUT FOR THE GOODWILL AMOUNT ANYWHERE IN §06.** p133
draws Goodwill **ticked**, with group 4 already saying *"issues a goodwill credit
on the account, excluding tax"*; p138 draws the figure as a value in a read-only
table whose own label says it was *"agreed with the customer"* — a fact the clerk
brings, from outside the system. **So the blueprint's own worked example is a case
the product cannot open**, and there is nothing to copy.

Placed by our UI rules, which is exactly what **B14 rule 38** asks for where a
drawing and our rules disagree about how a FORM is built. It is in **group 3, not
group 4**, because p134 annotates group 4 as the system's REPLY — *"The operator
picks a reason; the system says what it will do"* — and an input there would
contradict the drawing's own reading of that group.

---

## 2 · Reproduce · locate · blast radius

**Reproduced** twice before a line was written.

At the SERVICE layer, on `brazosbend`:

```
REFUSED: a goodwill credit of 0.00 is not a concession. A credit-only correction
reduces what the customer pays; zero changes nothing and a negative one is a
charge wearing a credit's name.
```

In the BROWSER at 1440: ticking **Goodwill** and pressing **Continue** left the
rail on step 1 (`def-bil-5368-goodwill-refused-1440.png`, lane E's capture).

**Located.** `openCorrectionBodyFor` in
`07-frontend/src/features/billing/fixABillContract.ts` — the one place the
screen's answers become the server's fields — and `FixABillTab.tsx`'s step 1,
which is the only step before the preview and therefore the only place a figure
the preview needs can be asked for.

**Blast radius, both ways.** Inbound: `openCorrectionBodyFor` has exactly one
caller, `FixABillTab.tsx`'s `previewMutation`; the signature change is therefore
total and the compiler proves it. Outbound: `OpenCorrectionBody.goodwill_amount`
has existed since the type was written and **no caller ever set it** — hard-won
law 2 from the far end, an optional member nothing passes. Nothing else reads the
new `FixABillReasonAnswers`. Lane E's `FixGoodwillStep` renders
`scope.goodwill_amount`, so it goes from drawing a stated absence to drawing a
figure without one line of it changing — which is the point.

---

## 3 · What was built, and where every decision came from

### The field

| Drawn / decided | Where it comes from |
|---|---|
| **appears only for a class-C case** | `strongestClassFor` — the CATALOGUE's own precedence (BR-BIL-042). Gated on the CLASS and never on the reason CODE, so a second class-C reason works the day it lands and nothing is typed out twice (the skill's §12) |
| label **Goodwill credit** | p138's own row words, and **asserted equal to `billing.fix.goodwill.row.credit`** in all eleven catalogues, so a clerk types under the label they read the figure back under one step later. The two live in different files owned by different lanes; the case is the only thing that keeps them one pair of words |
| help **Excludes tax. Agreed with the customer.** | p139's *"Tax excluded, and a tax-inclusive figure is refused"* and p138's own row label. Two FACTS of two and four words (B14 rule 33); the REASON — *the tax is owed whatever the utility forgoes* — is rationale and is zero words on screen |
| **no currency symbol** | the house pattern, not an omission: `MoneyCell.formatMoneyInput`'s own docstring says it is the half of the money pair made for *"a box a person types into and a server parses"* and the one that does not demand a `CHAR(3)`, and `NewAccountWizard`'s base-charge row took the same decision citing `DEF-CUS-5114` (no front-end reader of the tenant's own currency). The figure is rendered AS money, through `MoneyCell` with its currency, on the next step |
| **never re-formatted while typing** | `formatMoneyInput` is for the PRE-FILL. Run on every keystroke it turns `4` into `4.00` and the next digit can never be typed; there is nothing to pre-fill here, and an empty box asks for the figure where `0.00` would be a number nobody read off anything and which submits cleanly |
| the amount joins the **preview key** | it is the whole money of a class-C correction. Without it a clerk could walk back, change `$40.00` to `$400.00`, press Continue and be shown — then approve — the case opened on the old figure, with nothing on screen wrong |

### The two refusals, and the line between us and the server

`goodwillRefusal` is pure, beside `scopeRefusal`, so the ladder is provable
without a browser. It refuses **SHAPE, never a BOUND**:

* an empty box → *"Type the credit amount."* (4 words) — required-ness is the
  screen's; an empty box is a question the clerk has not answered;
* a non-decimal → *"Use digits and one point."* (5 words);
* **zero and a negative are SENT**, and `goodwill_credit_amount` refuses each in
  its own words. A second copy of those rules on the client is a second rulebook
  over money, and it would drift.

---

## 4 · `DEF-BIL-5381` — measured, and NOT closed

The defect's own prevention note proposed sending the clerk's business day
(`todayIso`). **Measured on `brazosbend` before deciding, which is the half that
matters:**

| Measurement | Result |
|---|---|
| the tenant's closed periods | **one** — July 2026 (`2026-07-01` → `2026-07-31`) |
| `ledger.close.resolve_entry_date(2026-07-02)` | **`2026-08-01`**, note `period_closed_auto_forwarded` |
| `resolve_entry_date(2026-08-02)` · `(2026-09-15)` | unchanged, no note |
| `build_impact(..., posting_period=2026-09-15)` on a July bill | raises `posting_period_is_not_the_bill_period`: *"the bill's period is 2026-07-02 and the entries will land in 2026-09-15 (BR-TEN-038: a closed period posts to the earliest open one)"* |
| the same with `posting_period=invoice.service_date` | no warning — but the month named is **July**, which is closed, and the ledger will post it into **August** |

**So both values the client could pick are wrong, in opposite directions.** Today
manufactures a warning about a close that did not happen, on the one panel whose
job is telling an approver what the books do; the bill's own date names a month
the ledger will override. And the client cannot compute the right one: `GET
/corrections/resolve` does not serve `invoice.service_date`, and nothing in the
front end reads a fiscal close. A **batch settles it on its own** — one period
cannot equal N bills' service dates, so every bulk case would carry the same
false warning.

**Decision (decision log, 2026-09-15): the posting period is not this screen's to
pick.** The wizard sends none; `fixABillContract.test.ts` asserts that ABSENCE so
a lane adding one has to come through the case and read why; and step 3 goes on
stating it, which is right and is why nothing looked wrong.

**The fix is a backend hunk, named rather than written here:**
`single_correction._ledger_handoff_section` should resolve the month from the
bill's own period through `ledger.close.resolve_entry_date` when the case carries
none, instead of serving `posting_period: null` — the preview is the one place
both facts are. `DEF-BIL-5381` stays **OPEN** against that surface.

---

## 5 · What was NOT built, and why

| Not built | Why |
|---|---|
| a `posting_period` on the body | §4 — measured, and not this screen's. Sending one would put a false sentence on the books panel |
| a currency on the input | §3 — the house pattern, `DEF-CUS-5114` is the open row |
| a client-side zero / negative / maximum check | bounds are the server's (§3). It already refuses each in words |
| a `MoneyField` component | `DiscountWizard` has a private one and `AccountActions` uses `TextField` + `formatMoneyInput` directly. A third shape would be the defect the kit exists to prevent; this mounts the kit's own formatter and the kit's own `TextField` |
| moving the field NEARER the Goodwill row | **stated rather than hidden**: it sits at the foot of group 3, about 400px below the checkbox it qualifies, because the eighteen drawn rows are one table and a field inside a `REASON · CLASS` table would be a third column the drawing does not have. It is the closest a non-table element can sit to that row. If the Product Owner wants it adjacent, that is a change to how p133 draws group 3, and it is theirs |
| a fifth group for the field | p134 draws four groups and the walkthrough asserts four |

### Three things found by LOOKING at the running screen (hard-won law 6)

1. **The open case is `pending_approval`, not `preview`.** `open_case` writes the
   row as `preview` and moves it to `pending_approval` in the same call once the
   impacts and the hash are stored, so `preview` is a state no reader ever sees.
   The first draft of the walkthrough looked for `preview`, found nothing, and
   reported *"Continue advanced but no case is in preview"* while the case was
   sitting there — a check looking at the wrong thing (law 7's fourth shape),
   caught because the walk prints what it saw instead of only an exit code.
2. **Three catalogues read the decimal example `18.50` as a CLOCK TIME** —
   `fr-FR` and `pt-BR` say *"par ex. 18h50"* / *"por ex. 18h50"* and `ja-JP` says
   *"18時50分"* — under a money box, in the one part of the sentence a clerk
   copies. Filed as **`DEF-RAT-5384`**; not fixed here, because it is rating's key
   and a copy fix in three catalogues is its own small piece of work.
3. **A money-path decision-log row cites the wrong defect.** Lane E's row of this
   date files its second gap as `DEF-BIL-5380`, which is a real but unrelated
   defect (Print bills' broker probe); the row it means is `DEF-BIL-5381`.
   `DEF-2804`'s shape exactly — a real id read for a different real id — so
   nothing dangled and every id-existence check passed over it. Filed as
   **`DEF-GOV-5383`** and corrected in place with a dated stamp, because
   `CLAUDE.md`'s own lesson from `DEF-GOV-5229` is that a finding written only in
   the prose of the file you happen to be in is a finding nobody counts.

---

## 6 · Proof

| Check | Result |
|---|---|
| `npx tsc --noEmit` (local TypeScript **5.5.4**, through `./node_modules/.bin/tsc`) | **clean** — and proved capable of failing FIRST: a planted `const laneLProof: number = "not a number"` raised `TS2322` at `fixABillContract.ts(544,7)`, then was removed |
| `fixABillContract.test.ts` | **15 passed**, 4 of them this lane's |
| `FixABillTab.dom.test.tsx` | **20 passed**, 5 of them this lane's (TC-L1…TC-L5) |
| RED-FIRST · the contract case | sabotaged by deleting the `goodwill_amount` line: `AssertionError: expected { … } to deeply equal { … }`, naming `- "goodwill_amount": "40.00"`. Restored and re-run green |
| RED-FIRST · the DOM cases | sabotaged to the pre-lane state (no field, no refusal): **TC-L1–TC-L4 all red** — *"expected null not to be null"*, *"expected undefined to be 'Type the credit amount.'"*, *"Unable to find a label with the text of: /Goodwill credit/"* ×2. Restored and re-run green |
| RED-FIRST · the label-parity case | pointed at a DIFFERENT row's words: *"de.json calls the field and the 26.4 row different things: expected 'Steuer darauf' to be 'Kulanzgutschrift'"*. Restored |
| Catalogue parity | **4 keys**, `+4 / −0 / ~0` in every one of the eleven, measured as `git diff --numstat` against the pinned tip. Applied through `10-scripts/i18n_fanin.py`, never by hand |
| Browser walk — `10-scripts/cr101_fix_a_bill_goodwill_walkthrough.mjs` | **0 problems at 1440 and at 1280** |
| Screenshots | `SCRATCH/lane-L-shots/` — eight files, **all eight hashes distinct** |

### What the walk actually did, stated rather than implied

Bill **`BL-2608-000042`** (`$160.52`, part paid `$2.42`), Goodwill, `40.00` typed.

* no reason ticked → **no field**; a class-R reason ticked → **no field**;
* **Goodwill ticked → the field is drawn** — *"Goodwill credit\* Excludes tax.
  Agreed with the customer."*;
* Continue with the box EMPTY → **"Type the credit amount."**, still on step 1,
  and **no case opened** (the case list is read before and after);
* Continue with `40.00` → case **`01a0a580-0c5c-79cf-97d2-259c0e15b963`** at 1440
  and **`01a0a580-2be6-7c34-a6e3-ab0f37ae263b`** at 1280, class `credit_only`,
  `scope.goodwill_amount` **`"40.00"`**, and step 2 draws
  `data-fix-step2-variant="26.4"` with **no stated absence** — *Goodwill credit
  `$40.00` · Tax on it `$0.00` · On the account `$40.00`*, every figure at two
  decimals;
* step 3's books panel reads **`POSTS IN  Not set on this preview.`** — §4;
* **no rule id, question id, dotted identifier or uuid** on step 2 or step 3, read
  off the RENDERED DOM; no horizontal scroll at either width.

**Nothing money-bearing was written.** `Send for approval` was never pressed and
neither was step 4's commit, so no signature and no credit note, invoice,
adjustment or journal line exists. Both cases were closed through the screen's own
*Close without correcting*, and the walk ends by asserting **the tenant holds no
open correction case** — it was clean when this lane started and it is clean now.

---

## 7 · Reds, each with its date

| Red | Dated how |
|---|---|
| `push_paths.sh` REFUSED the first push, naming all eleven catalogues as moved between `01e0e586` and the tip | **NOT A RED, THE GUARD WORKING** — and worth recording because it is the case the guard exists for. A sibling added **23 keys** while this lane was building (17,751 → 17,774). Every catalogue was re-derived from the pinned tip's bytes, the four keys re-applied through `i18n_fanin.py`, and `git diff --numstat <tip>` then printed `4 0` for each of the eleven. Had it not refused, those 23 keys would have left the branch by subtraction, with every check in law 11 passing |
| `git diff --numstat <commit>` printed `0 599` for `test_cr101_lane_k_which_bills_a_bulk_correction_takes.py` after the push | **THE UNTRACKED-FILE TRAP, NOT A DELETION** — law 12 records it by name: a file created after the stale HEAD is untracked, so `git diff` keeps calling it deleted even once its bytes are correct, *"the diff is not the check"*. Proved with `cmp` against the commit's own blob: **byte-identical**. HEAD was then synced and the subtraction against the new tip printed nothing |
| The walkthrough's own first run: *"Continue advanced but no case is in preview"* | **CAUSED BY THIS LANE, in the walk and not in the product** — `open_case` leaves the row at `pending_approval`. §5, finding 1. Fixed, and the reason is in the script's own comment so the next walk does not repeat it |

**No red on the branch was inherited and dismissed.** The two suites this lane
owns were green before it started and are green now; `tsc` was clean across the
whole tree at every check. `PastBillingRunsPanel.tsx` and
`pastBillingRuns.dom.test.tsx` differ between this worktree's base and the tip —
those are lane I's, were not touched, and were not pushed.

---

## 8 · What needs somebody else

* **A backend hunk, named in §4:** `_ledger_handoff_section` should resolve the
  posting period from the bill's own period through `close.resolve_entry_date`
  when the case carries none. `DEF-BIL-5381` is the row and it stays OPEN.
* **`DEF-RAT-5384`** — the `18.50` example read as a clock time in three
  catalogues.
* **`DEF-GOV-5383`** — filed and corrected here; nothing left to do.
* **An observation, not filed:** the demo tenant has no Correction number series,
  so the *Corrections so far* list under the wizard draws **49 rows all reading
  *"No case number yet"***, most of them closed by earlier lanes' walks. The
  wording is `DEF-3158`'s fix working (rule 31 — never a database id, and an
  absence stated in words); whether *"yet"* is honest for a tenant that has no
  series is a question for whoever configures one.

---

## 9 · Version and rollback

**Not bumped here** — the orchestrator versions once the wave lands. The CHANGELOG
sentence this lane would have written:

> *"Fix a bill asks for the goodwill credit on its first step, beside the reason
> that needs it, so a concession can be opened at all: type `$40.00` against a
> bill and the second step draws the credit, its excluded tax and what does not
> happen — until today the screen sent no figure and the server refused every one
> of them."*

**Rollback:** code only — revert the commits. No case was approved or executed and
every case opened was closed without correcting.
