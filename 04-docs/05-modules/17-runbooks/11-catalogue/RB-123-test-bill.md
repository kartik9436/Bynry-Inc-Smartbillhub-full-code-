# RB-123 — Runbook 23 · Test bill

> **BUILT — `CR-075` wave F, 2026-09-06** (`US-RBS-004`, `06-backend/apps/runbooks/definitions/test_bill.py`).
> Scope, parameters and steps below came from the catalogue and are now what the code declares.
>
> ⚠ **THE RESULT SCREEN IS STILL NOT DRAWN IN THE SOURCE**, and that has not changed: `RBS-006-R23`
> is a **composed** build sheet, written by the wave-F lane from the twelve report blocks, and it says
> so at the top where every other sheet carries a derivation note. Where the source later draws
> `S152-R23`, the source wins and that sheet is the thing to fix.

## What it declares

| | |
|---|---|
| **Kind** | Check |
| **Category** (one home, from the fixed list of sixteen) | Billing |
| **Tags** | `Billing` · `Plans & Rates`. The source's tag table covers runbooks 1–22 only, so these are the build lane's, chosen from tags the catalogue already uses. |
| **Phase** | 1b |
| **Trigger** | **Manual, and nothing else.** PO ruling 2026-09-06: a person starts it — a clerk picks an account and presses Run. The catalogue row C2 says the same: **staff, on demand**. A schedule over one account would be a report nobody asked for, every day, for ever. |
| **Subject and unit of work** | `account` · **account-period**. Not declared in the source (its coverage table stops at runbook 22); this is the build lane's, and the subject type is one of the twelve. |
| **Step modes** | All four are `set` mode over a pinned set of ONE account — the shape runbook 1 already uses. A `set` step's answer lands in `set_results`, which is the only channel a later step can read an earlier one through, and step 3 has to read step 2's priced lines. |
| **Result blocks it composes** | **`KPIs · Sentence · Records · Reconciled`** when the account prices; **`Sentence · Records`** when it does not. Four of the twelve, and the two it does NOT draw are listed under *Judgments* below. |
| **Ports it holds** | **None** — it is a Check, so it is constructed with no ports. |
| **Proves** | US-RBS-004 |
| **Waits on** | — |

> A Check is constructed with **no ports**, so a write is not refused at runtime — it is unavailable (`BR-RBS-002`, `TC-RBS-1`).

## What it answers

Answers: price one account exactly as the bill run would, explain every line, and consume no bill number. The clerk's "what would this customer's bill be" and the implementer's proof that a plan works before go-live.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Account | 🔍 one account | value, not editable on this screen |
| Period | A cycle, or as at a date | value, not editable on this screen |
| Services | The account's own | value, not editable on this screen |

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Account | 🔍 one account | `ref:object`, required | — |
| Period | A cycle, or **as at a date** | `window`, required. Defaults to the last whole calendar month; `as_at` defaults to the period end | — |
| Compare with | Last issued bill | `enum` — `last_issued_bill` · `nothing` | — |
| Show | Every line, explained | `enum` — one choice, because the card names one | — |
| Rounding | From Settings · 4 stored, 2 shown | read-only, Settings-owned (dashed) | **Settings** |

⚠ **THE PERIOD'S SECOND HALF DECIDES THE PRICE, AND IT TOOK A REAL RUN TO NOTICE.** `BR-RAT-007`
prices on the SERVICE date, and for a cycle run that is the **bill day**, not the last day of the
period. On the seeded utility the July bills carry `service_date = 2026-08-02` and the water rate
moved from `$4.00` to `$4.24` a kgal on 1 August, so re-pricing July at the period end answers
**$158.10** on account `AC-2026-00001` where the customer was billed **$160.52**. Neither figure is
wrong — they are two different questions — so the date is a parameter and **the result screen states
which one priced the run**.

## Steps

Source heading: **Steps 4 · all read**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Load the account, unit, plan and reads | As the bill run would see them on bill day | `read` |
| 2 | Price through the real engine | The same code path as the run; never a second implementation | `read` |
| 3 | Explain every line | Base, each block, taxes, fees, prorations, in words | `read` |
| 4 | Compare with the last bill | Line by line, difference per line | `read` |

## Guards — what it may never touch

- It is a Check, so it is constructed with no ports and writes nothing.
- **No bill number is consumed.**
- It prices through the **real engine** — the same code path as the run, never a second implementation.

## Produces

A complete priced bill with every line explained, or one refusal sentence naming the service and the date. **No bill number is consumed and nothing is written.**

**Done looks like** (the commitment's own sentence, RB-123, status UNVERIFIED): A clerk picks one account and sees a complete priced bill with every line explained, or one refusal sentence naming the service and the date; no bill number is consumed.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R23.png` | `RBS-004-R23.md` | `…/runbooks/test-bill` | `S150-R23`, figure 43 |
| Result | **not drawn** | `RBS-006-R23.md` — **COMPOSED, not derived** | `…/runbooks/test-bill/runs/{run}` | `S152-R23` — reserved, not designed |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

**The result screen is reserved and not designed in the source.** `RBS-006-R23.md` is the wave-F
lane's composition of the twelve blocks, written before a component was, and it carries that fact in
place of a derivation note. There is no picture: `rbs-f-test-bill.mjs` saves `rbs-006-r23-priced.png`
and `rbs-006-r23-refused.png` from the running product, which is a record of what shipped rather than
of what was designed.

> The source document numbers these screens `S150-R23` and `S152-R23`. This repository numbers them `RBS-004-R23` and `RBS-006-R23` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## The judgments this lane made, which the documents did not settle

The Product Owner asked for these to be surfaced rather than assumed — *"if you have questions on
Runbook you should ask instead of assuming"* (2026-09-06). **None of them is a question and none
touches a signed figure**; each is a decision stated plainly enough that a wrong one is cheap to
reverse. They are written out in full in `definitions/test_bill.py`'s own docstring, where a reader
of the CODE meets them, and listed here for a reader of the catalogue.

| | The judgment | Why |
|---|---|---|
| **J1** | **What "explained" means for a line** — ONE sentence per line, in the clerk's own words, built from what the line already carries: its quantity, its unit, its unit price, and for a tax line the rate. | It is **not** the engine's own message. Those quote `BR-BIL-015`, `BR-RAT-090` and `BR-CUS-1010` by name, and B14 rule 32 keeps a rule id off a screen. |
| **J2** | **A refusal shows nothing else** — the Sentence card and an empty Records table, and no KPI strip and no comparison beside them. | `US-RBS-004` says *"**ONE** refusal sentence"*. A strip of em dashes is three more things to read for no fact. The services that WOULD have priced are not listed either: the bill refused as a whole, and half a bill is what this runbook exists to stop a clerk believing. |
| **J3** | **A zero-amount line is drawn**, with its explanation, like any other. | `$0.00` for sewer is a fact the engine produced, and a clerk asking *"why is sewer nothing this month"* is asking about that row. Dropping it would make the bill on this screen a different bill from the one the run produces. |
| **J4** | **The comparison is an OUTER join, matched on the line's wording.** A line present on one side only is drawn with an em dash on the other. | `TC-RBS-004.4`: *"an inner join silently hides new and removed lines"* — the two rows a clerk is actually looking for. The description is the only key the two sides share: a priced line has no id (it was never written) and an issued line's `service_id` is NULL on taxes and fees. Where a description CHANGED between the bills the row appears twice, once on each side — visible and honest, where a fuzzy match would be neither. |
| **J5** | **A second run is not bounded.** No frequency parameter, and *Run again* is never disabled. | `OQ-RBS-1737` closed on 2026-09-06 with re-running bounded in time, the frequency a parameter and 24 hours its default — **and a test bill is re-run constantly by design**. Nothing in the engine bounds a re-run today in any case, so this is a statement of intent for the wave that builds it, made here rather than left for that wave to guess. |
| **J6** | **No `downloads` block.** | The two result files stream `runbook_run_records` and **nothing writes a record row yet** — `close_run` freezes the report and writes none. The button would download an empty file, which is the dead-control shape hard-won law 2's 2026-09-05 mirror is about. Runbook 4, the closest analogue in this catalogue, carries no download either. **When a wave persists record rows, this gains one.** |
| **J7** | **No `verdict` block.** | A leading verdict becomes the page head's sub-line and the Sentence card would then say the same thing twice — the description budget B14 rule 32 exists to protect. The outcome of a test bill is a bill or a stop, and `sentence` is the block whose stated job is *"a stop, a find, read this aloud"*. |
| **J8** | **The period defaults to the last whole calendar month.** | The card says *"A cycle, or as at a date"* and settles neither, and a window parameter with no value cannot run. The month that has ended is the period a clerk answering *"what would this bill be"* almost always means, and they can change it. |
| **J9** | **The window carries an `as_at`, and the screen says which date priced the run** — a fourth KPI tile, *Priced as at*. | Found by RUNNING it, not by reading. See the warning under **Parameters**: `$158.10` against `$160.52` on the same account, same period, two service dates. A clerk who cannot see that date cannot explain the gap and would file a defect against a bill that is correct. |
| **J10** | **The pricing call is filed under the BILLING seam, not the rating seam.** | `10-execution-plan.md` `F2` says *"a seam to rating"*, and in the code the chain from an ACCOUNT to a PRICED LINE is billing's: `billing.runs.price_account` measures the account and then calls `billing.rating_seam.price_bill`, which is the door into `apps.rating.engine`. Filing that in a file whose declaration reads `operations → rating` would be a sentence about the boundary that is not true of the code behind it (hard-won law 1). The rating seam carries step 3's tax reads instead. Both seams were already register rows. |

## Open questions and stated absences

- **The result screen is not drawn in the source.** `RBS-006-R23.md` is composed and says so; the source still wins if it ever draws one.
- **`Recorded` / `In the books` is NOT the comparison's heading pair.** B14 rule 34 fixes those two words for *held here* versus *posted*, and neither side here is that: this run is held **nowhere**, because nothing was written. The columns are *This run* and *Last issued bill*. `RBS-006-R9` already draws *Billed* / *In the books* rather than the literal pair, so a heading naming its own side is the established shape.
- **Every money KPI tile in this module reads *"posting date"* beside it** — `DEF-RBS-4350`, found by this wave's browser walkthrough, which is the first runbook to draw one. Runbook 23 posts nothing at all, so the strip contradicts its own Sentence card two inches below. `KpisBlock` hardcodes the basis and `MoneyBasis` has only two values; the fix belongs to the lane that owns the renderer.
- **Why this card exists:** named in the specification's catalogue (C2), story `US-RBS-004`, phase 1b and four wireframes — **and defined nowhere** until 2026-09-06. It is the demonstration a prospect sees on their own data.
- PO ruling, 5 September 2026 — **sequencing: test bill and readiness check before anything else**, chosen from test bill first / cutover first / help first.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-123: VERIFIED** (2026-09-06, `CR-075` wave F) — and the tests that moved it were each
shown failing first. `TC-RBS-004.3` on real PostgreSQL: the same account through the test bill and
through a real bill run gives an identical line set at four decimals — *electric usage* `49.4400` and
*electric base charge* `18.5000` — and its RED proof plants a second implementation off by `0.0025`, a
quarter of a cent, then asserts BOTH that four decimals catch it and that two do not (`49.44` either
way). On the seeded utility, **six of six** accounts re-priced identically to their own issued bills;
`AC-2026-00001` is `$160.5200` over 7 lines. Three test bills in a row left every one of the tenant's
30 number series exactly where it was. The six-word refusal cap went red on its first run — *"Storm
water has no read for August."* is seven words — and the table was rewritten; it is now checked
against **13 reasons × 12 subjects** rather than one.
