# `CR-100-BRC03` — Billing measured against *Billing, As Built*

| | |
|---|---|
| Raised | **2026-09-14** |
| Branch | `claude/eager-johnson-r0k88b` · block `CR-100`–`CR-104`, suffix `BRC03`, claimed in `14-id-reservations.md` |
| Module | **billing** (`04-docs/05-modules/07-billing/`) |
| Drawing | `05-prototype/04 Billing, As Built.pdf` — **249 pages**, 14,363,163 bytes, on the default branch |
| Status | **STEP 1 IN PROGRESS.** Nothing built. No `.tsx` or `.py` touched by any lane |
| Version | **NONE TAKEN.** Step 1 ships nothing; step 7 attaches a version to a CR that SHIPS. `2.262.0` is left free for whoever ships first, rather than going stale (`DEF-GOV-3756` was two lanes both shipping `2.141.0`) |

⚠ **THIS FILE WAS WRITTEN AFTER THE ID WAS ALREADY CITED IN THREE PLACES, AND THAT IS A
DEFECT IN THE PROCESS I FOLLOWED, NOT A DETAIL.** `13-change-process.md` step 0 says a CR is
captured **at arrival**. `CR-100-BRC03` was claimed, then cited by
`conformance/CR-100-BRC03-repo-claims.md`, by a defect row and by the reservations register,
while no file carried the number — **a citation to nothing**, which is the exact shape
`CLAUDE.md` names when it describes *"a citation gate that refuses a repeated id and never
asks whether the id was ever issued."* Recorded here rather than quietly fixed.

## 0 · What arrived, in the requester's words

> *"You are running STEP 1 on the BILLING module… STEP 1 MEASURES AND CLASSIFIES. IT FIXES
> NOTHING… The deliverable is a written record and a set of allocated ids, nothing else."*

and, on completing it:

> *"parallel agents please complete step 1"*

## 1 · Classify

**This is not a change to the agreement. It is a MEASUREMENT**, and this CR exists to carry
the three things a defect row cannot: **a supersedes chain**, **a framing correction**, and
**a question that reaches the PO**.

## 2 · ⛔ The framing the briefing gave was INVERTED, and it would have sized the module wrongly

The briefing said: *"'AS BUILT' is in the title and it changes what you are measuring… the
default reading is the opposite: a difference is DRIFT, not a build item."*

**Measured from the pages — the document is mostly a REDESIGN and says so in its own words.**

| Evidence | Where |
|---|---|
| **`DRAWINGS 91 — 70 redesign · 21 as-built`** | cover figure band, p1 |
| *"There is one drawing per screen and it is the one to build… Their current state is kept directly underneath, **collapsed and marked do not build this**"* | p2, in red |
| *"This entry holds **both**: an AS-BUILT drawing and a **REDESIGN that has never been built**. **Build the REDESIGN**"* | entry 01's caption, p6 |
| **§03–§08: 57 entries, 57 REDESIGN, ZERO as-built.** Every caption says `NEVER BUILT` and names the §17 screen it replaces | measured page by page, p28–p151 |
| 74 pages carry `REDESIGN` · 71 carry `NEVER BUILT` · 68 carry both · `AS BUILT` in caps appears **once** | whole document |

⚠ **SO A DIFFERENCE BETWEEN THE PRODUCT AND AN AS-BUILT DRAWING IS NOT DRIFT TO CLOSE — that
drawing is marked do-not-build.** Had this pass followed the briefing, it would have hunted
drift that mostly is not there and missed the actual build list.

## 3 · The supersedes chains, and the one question that reaches the PO

### ⚠ THE QUESTION: 15 rulings exist in no file, BY A RULING

The document's cover:

> *"Nothing is written to the repository, and on **2026-09-13** that stopped being a working
> constraint and became the decision: **'We ahve to write everything in HTML artifact only
> Billing, as built - noting in repo'**. So this artifact is the system of record… The cost is
> stated rather than hidden: **15 of the 27 rulings quoted here exist in no file, cannot be
> grepped, and nothing can count what depends on them.**"*

**Both figures were CHECKED, not quoted: 27 found against 27 claimed; 15 in no file against
15 claimed.** 12 of 12 rulings claiming a repository home resolve (`BR-BIL-016/060/063/065`,
`OQ-104/112/241` all CLOSED with the ruling verbatim, two decision-log rows, B14 rules
31/37/39, `CLAUDE.md` hard rule 2). **0 of 15 `NOWHERE` rulings appear anywhere in the tree**,
searched by wording and by substance.

⚠ **FOUR OF THE FIFTEEN TOUCH MONEY OR THE LEDGER**, including a worked figure — *fee $0.57,
bill $70.17* — that **exists in no golden test, no rule and no decision row.**

⚠ **AND THE PO HAS ALREADY RULED ON THE IDENTICAL INSTRUCTION ONCE.** Meter Reads' `R7`, two
days earlier, was *"write it down in document and not in repo"*, and its blueprint records
that as **"the CAUSE of all the others being lost"** (`CR-096-BRC02`). On **2026-09-14** the
PO ruled of those instructions: ***"these instructions were to create the blueprint documents
those are resolved."***

**THE QUESTION, and nothing here decides it:** does the 2026-09-13 Billing ruling resolve the
same way — the 15 transcribed into the repo before step 2 builds on them — or does it stand,
in which case **step 2 builds on rulings no lane can find**. It is the PO's ruling against
the PO's ruling, which is precisely and only what reaches them.

**Also carried, undecided:** the document's **one open PO question** — *which balance the
late-fee floor tests, the ageing part or the whole bill* — which **changes what a customer is
charged** and is the missing half of its own ruling 26.

## 4 · What is already built and is now wrong

Measured, with counts, by three lanes:

| Finding | Count |
|---|---|
| Repo claims re-checked / **already false** | 18 / **9** |
| Endpoints claimed vs measured | 36 across 8 → **41 across 9**, all 41 served |
| Endpoints served with **no caller** | **3** + 1 dead duplicate over a live route |
| Signed golden figures / **engine-verified** | 61 / **14** — so **47 have no test that runs the engine** |
| Stated absences the product carries | **78** (prototype states 0) |
| **Dead controls** — visible and unusable | **14** |
| **Rotting holds** | **7**, 5 load-bearing |
| Rule violations | **17** · eleven `RATIFIED ONLY` · **not one catchable by a machine** |
| High-severity defects reading `open` over a product that moved | **3** |

**Defects filed by this pass so far:** `DEF-BIL-5225` · `DEF-BIL-5226` · `DEF-BIL-5227` ·
`DEF-BIL-5228` · `DEF-GOV-5224` · `DEF-GOV-5229`.

⚠ **`DEF-BIL-5226` is the sharpest**: the hold-expiry test written *specifically* to fire the
day its route landed watches one hand-named file, the function landed in another, **it passes
green over an expired hold**, and its failure message begins *"THAT IS GOOD NEWS."*

## 5 · ⛔ A SCOPING CORRECTION STEP 2 MUST NOT MISS

**Not one of §17's thirteen screens carries a drawing to build.** Every entry stamps
`REDRAWN AS … Build that one`; screen 03 reads `No redraw`.

**Three sources say otherwise and all three are stale** — the contents rail's `10 ◆ 13 ◆
14 ◆`, §17's own summary table on p215, and this pass's lane briefs repeating them. §15 (p203)
records why: each of those three once carried a `BUILD THIS` band **and** a `REDRAWN AS`
stamp — *"two drawings to build for one screen, which is exactly the confusion the PO warned
about when the redraws moved."* **A lane scoping step 2 off any of the three builds three
screens the document tells it not to build.**

⚠ **AND THE DOCUMENT'S OWN BUILD ARITHMETIC DOES NOT RECONCILE.** Its p6 table names
**eleven** drawings to build and attributes all of them to §02. The `BUILD THIS` band occurs
on **14 pages**: eleven in §02, **two in §03** (`16 Scope` p46, `17 Check` p51), one in an
appendix. Both numbers are stated here; neither is picked.

## 6 · Size — and the money bar

**Not sized. Step 1 is not finished** (see §8). What is established: **§12's "nine that cost
the most"** is the build index step 2 will be scoped from — `BIL-S90` (a utility above 25,000
accounts cannot run a cycle at all) · `BIL-S56` (the leaving customer's deposit) · `BIL-S91` ·
`BIL-S92` · `BIL-S93` · `BIL-S9` (no error boundary anywhere in the route tree) · `BIL-S1` ·
`BIL-S61` · `BIL-S102` (a hardcoded $25 floor).

⚠ **B4 AND B5 ARE ❄️ FROZEN.** No measurement in this pass moves a signed figure, and none
may: a figure moves by finance re-sign through `HUMAN-GUIDE §6`, never by an inline edit.
**No drawing in §03–§08 shows an edit on an issued bill** — the drawings state hard rule 4
themselves (*"An issued bill takes no update and no delete… which is also why the prototype's
edit specific line items control cannot be ported"*), so the money rule is honoured by the
design rather than fought.

## 7 · Version

**None.** See the header.

## 8 · What is NOT done — step 1 is incomplete as this is written

* **The walk** — one lane running. Billing had **`invoices` 0 · `invoice_lines` 0 ·
  `bill_runs` 0** when measured, so any list walked without seeding is **UNJUDGED**, not
  matched.
* **The §02 per-entry map** — one lane running.
* **The diff, both directions, with counts** — not started; it depends on the map and the walk.
* **60 of the 99 pages in §09–§17 unread** — §14's card bodies among them, so **step 2 must
  open the card for any `BIL-Snn` it scopes.**
* **`DEF-BIL-5097`'s twenty reds were not re-run.**

**This CR is not closable until those land.**
