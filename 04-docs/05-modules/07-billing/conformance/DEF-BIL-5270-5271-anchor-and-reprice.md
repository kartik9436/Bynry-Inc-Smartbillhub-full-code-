# DEF-BIL-5270 · DEF-BIL-5271 — the anchor a bill run did not have, and the decision that reached no money

⚠ **AMENDED 2026-09-14 BY PO RULING (decision log, `2352b7c2`) — THE REGISTER
HALF OF `DEF-BIL-5270` AS FIRST BUILT WAS OVERRULED THE DAY IT SHIPPED, AND
EVERYTHING BELOW ABOUT IT IS SUPERSEDED BY §6.** It shipped as a DECISION with
two choices — *bill as it stands* or *hold and investigate*. PO, verbatim:
*"there is no sign off issue - you ahve to raje start reading as 13,500 - we
cannot create wrong conusmption that is loss"*. There is no choice: the period
OPENS at 13,500. The CALENDAR half is untouched and keeps its decision.

**Date** 2026-09-14 · **Branch** `claude/eager-johnson-r0k88b` · **Base tip** `cab896fa`
**Rules** `BR-BIL-1039` (NEW, the billed-through anchor) · `BR-BIL-1038` (NEW, the
phase-4 gate extended) · extends `BR-BIL-053` · reuses `BR-CUS-103`'s anchor from
`cut_bill.py` · `BR-BIL-015` posture · `BR-BIL-023` / `BR-BIL-039` (why a scoped
re-price is safe)

Both defects were **silent**. Nothing raised, nothing logged, no gate moved and no
screen said anything — which is why every existing check passed over them and why
every element below is recorded as a NUMBER rather than as a state.

---

## 1 · What was wrong, measured

| | `DEF-BIL-5270` | `DEF-BIL-5271` |
|---|---|---|
| The claim | a cycle run checks that an account's consumption starts where its last BILL ended | a decision re-prices the accounts it touched, and sign-off refuses a stale draft |
| What was there | metering's stored `(current − prior) × multiplier`, anchored on the previous **READ** | `resolve_cases` wrote rows; the retry endpoint says in its own words *it is not a re-price* |
| What could not be seen | a re-read, a skipped read, a meter exchange or an unissued draft | 44 accounts bulk-decided under one `bulk_action_id`, 44 drafts unchanged |
| Why no check caught it | the Scope band compares run **PERIODS**; two runs tie out while one account is two reads adrift | the `BR-BIL-053` gate counts **UNRESOLVED BREAKS**, and a decision is not a break |

---

## 2 · Element list, and the counts tie out

**`DEF-BIL-5270` — two anchors, both per account, neither optional.**

| # | Element | Where | What decides it |
|---|---|---|---|
| 1 | `anchor_from(billed_through, period_start)` | `runs.py` | the day after the last issued `period_end` vs `period_start` — pure, no query. `period_anchor(account_id, …)` is the one-shot form for a caller holding only an id, and delegates to it |
| 2 | `last_issued_window(account_id)` | `runs.py` | the furthest-billed ISSUED invoice's own period |
| 3 | `register_anchors(readings, unit_ids, anchor_window, scope_services)` | `runs.py` | this period's `prior_read` vs the anchor bill's `current_read`, per service |
| 4 | `_continuity_decisions(data, unit_ids, scope_services)` | `runs.py` | turns 1 and 3 into `AccountProblem(reason="billing_continuity")` |
| 5 | `STAGE_BY_REASON["billing_continuity"] = "measure-consumption"` | `runs.py` | `BR-BIL-040` — the tab that owns the input |
| 6 | `CHOICES_BY_CASE["billing_continuity"]` | `decisions.py` | `bill_as_is` · `investigate` |
| 7 | `HOLDING_CHOICES += ("billing_continuity", "investigate")` | `decisions.py` | `BR-BIL-055`'s one pending queue |

**ONE query per account for BOTH anchors, amended after the first push.** The
loop read the account's billed position twice — once through
`last_issued_invoice_period_end` for the calendar and once through
`last_issued_window` for the register — and both order on `period_end` and find
the same row. It now reads the window once and derives both from it, which is
40,000 fewer queries a run at the top of the ICP. Neither version was wrong, so
no test would ever have said so (`996d45c8`).

**Five states, and they are five on purpose** — `aligned`, `first_bill`, `gap`,
`overlap`, `unknown`. `first_bill` and `unknown` are kept APART from `aligned`
because *we checked and it ties* and *there was nothing to check against* are
different facts, and a check that reports the second as the first is law 7's
*reporting zero over a scope it silently excludes*. Neither raises a clerk-facing
row: there is nothing a clerk can do about a bill issued before this check existed.

**`DEF-BIL-5271` — two halves, and the second is what makes the first real.**

| # | Element | Where | What decides it |
|---|---|---|---|
| 1 | `calculate_run(…, only_accounts=frozenset)` | `runs.py` | narrows the loop; `None` is every ready account |
| 2 | `reprice_accounts(bill_run, account_ids, …)` | `runs.py` | prepare (narrowed by `resume_skip`) → `apply_decisions` → `calculate_run` |
| 3 | `has_drafts_for(bill_run, account_ids)` | `runs.py` | a decision taken BEFORE calculate has nothing to replace |
| 4 | `accounts_touched(rows)` | `decisions.py` | the scope comes from the rows WRITTEN, never from the request |
| 5 | `stale_drafts(bill_run)` | `runs.py` | two grouped queries: `max(invoices.created_at)` vs `max(decisions.created_at)` |
| 6 | `refuse_stale_drafts(bill_run)` | `runs.py` | the one place that refuses |
| 7 | `authorise_release` calls 6 | `release.py` 🔒 | the phase-4 gate |
| 8 | `run_exception_resolve` calls 2 | `api.py` | the wiring — inline, or `REPRICE_JOB` when asked |

**7 + 8 = the two wirings a unit test cannot see**, which is what `G125` is for.

---

## 3 · Worked figures

* **Calendar gap** — billed through 30 Apr, run opens 1 Jun → `gap`, **31 days**,
  `2026-05-01` to `2026-05-31`.
* **Calendar overlap** — billed through 30 Jun, run opens 1 Jun → `overlap`,
  **30 days**. Two rows, not one, and both are true: the period overlaps AND the
  register the bill would price is the register it already priced.
* **Register gap** — May's bill closed at **13,500**, June's read opens at
  **13,800** → **300 kWh on no issued bill**, with the calendar perfectly
  continuous. This is the case a period comparison can never reach.
* **Scoped re-price** — 2 accounts drafted, 1 decided, re-price drafts **1**, and
  the other account's invoice row is the **same primary key** afterwards.
* **The gate** — 1 draft + 1 later decision → `stale_drafts` returns **1** while
  outstanding breaks is **0**, and `authorise_release` refuses.

---

## 4 · Proof

`06-backend/tests/test_def_bil_5270_5271_continuity_and_reprice.py` — **11 passed**.

**Each guard shown RED FIRST**, in a `git worktree` pinned at the tip so the shared
tree was never mutated:

| Guard removed | Measured |
|---|---|
| `_decisions_for` → `_continuity_decisions` | 3 failed, verbatim `assert 0 == 1 … where 0 = len([])` |
| `calculate_run`'s `only_accounts` narrowing | `assert 2 == 1` — a *scoped* re-price drafting both accounts |
| `authorise_release` → `refuse_stale_drafts` | `Failed: DID NOT RAISE <class 'apps.billing.exceptions.BillingRuleError'>` |

**Gate `G125`, proved red through `run_gates.py` and not through the gate file** —
on the pre-fix tip it named all three wirings, then **3 → 2 → 1 → 0** as each file
landed. Its first draft was itself wrong in a way worth recording: it proved its
scanner by planting removals into the REAL files, so on the tree it was written FOR
it reported *"my self-test does not hold"* instead of *"three checks are not
called"* — the exit code right and the sentence a reader acts on wrong. The
self-test now runs against a synthetic source of its own.

**Law 14 · what was proved on real PostgreSQL rather than on the suite's SQLite.**
Nothing in this lane catches a database error and continues, so law 14's trap is
not reachable here: `stale_drafts` and `has_drafts_for` are reads, `period_anchor`
and `register_anchors` are reads, and `reprice_accounts` delegates every write to
`calculate_run`, whose per-account `transaction.atomic()` and `record_break`
savepoint are unchanged and already proved under
`DJANGO_SETTINGS_MODULE=config.settings.local`. **Stated rather than assumed** —
the suite that ran these 11 cases is the SQLite one, and it would not have shown
the difference.

---

## 5 · Reported, not fixed

1. **The register anchor costs one extra reads-seam call per covered unit**, for an
   account that has an issued bill only. It is the only way to recover the closing
   register for a bill ALREADY ISSUED: `bill_payload.services[].read_id` names the
   read and `invoice_lines` carries a quantity, so no register VALUE is frozen
   anywhere. Stamping one at issue would fix nothing retrospectively.
2. **An account held by `investigate` keeps the draft it already had.**
   `apply_decisions` takes it out of `ready`, so stage 6 never runs and the draft is
   not replaced. Discarding it is `BR-BIL-055`'s pending-queue business.
3. **`billing_continuity` draws no chip yet.** `G124` reports an engine kind the
   screen does not draw rather than failing it, and `casesWithoutFamily()` puts it
   on screen — but no `CASE_TABS` entry and no locale key exists, so it is a build
   item for the front-end lane.
4. **`runs.py` is not on `human_owned.txt`** and now holds two money-path
   decisions. Adding a file to that list is a process event and the PO's call.
5. **`DEF-3221` (open, 2026-09-02) is red at the tip and is not mine** — three cases
   in `test_us_bil_003_decisions.py` fail because an account whose meter was simply
   not read is refused with *"billing's read seam publishes no meter multiplier"*.
   Measured on a clean worktree at `cab896fa` with none of this lane's code: the
   same three fail.
6. **The version bump is OWED and was deliberately not taken.**
   `allocate.py version --bump fix` answered **2.266.1** and `--verify 2.266.1`
   says it is still free on every branch. It is not written, because all four
   files that carry a version — `package.json`, `package-lock.json`,
   `pyproject.toml`, `CHANGELOG.md` — hold a **sibling's unpushed bump to
   2.266.0** in this shared tree. Writing 2.266.1 over it and pushing would
   publish that lane's in-flight work with my commit (law 11, mechanism five:
   `DEF-168`), and re-deriving those files from the tip instead would push the
   number BACKWARDS the moment the sibling lands. So the number is reserved here
   in words and the bump belongs to whoever lands after that lane. Meanwhile the
   answer to *"which build?"* is the fixing commit recorded on each defect row by
   `close_defect.py`.


---

## 6 · SUPERSEDING §2's REGISTER ROWS — the anchor, as built (PO ruling 2026-09-14)

**The register case is no longer a decision kind.** `RegisterAnchor`,
`register_anchors` and the `CONTINUITY_UNKNOWN` state are deleted; rows 3 and 7
of §2's first table are gone with them, and `_continuity_decisions` is
calendar-only.

| # | Element | Where | What decides it |
|---|---|---|---|
| 1 | `BilledPosition` · `billed_positions(account, unit, …)` | `runs.py` | the read the last ISSUED bill named (`bill_payload.services[].read_id`, `DEF-098`), found among metering's published heads |
| 2 | `_anchor_quantity(quantity, row, position)` | `runs.py` | `(current − anchor) × multiplier`, on the anchored period only |
| 3 | `ServiceReading.unanchored_prior_read` | `contracts.py` | the trace: what metering's own read counted up from |
| 4 | `ANCHOR_METER_EXCHANGED` | `runs.py` | the anchor read and this read sit on different published `asset_id`s |
| 5 | `ANCHOR_REGISTER_WENT_BACKWARDS` | `runs.py` | the anchor would have to span a wrap, and the span is metering's (`BR-AST-015`) |
| 6 | `ANCHOR_MULTIPLIER_UNSTATED` | `runs.py` | `BR-MET-500` never defaults the factor to 1 |
| 7 | `ANCHOR_TOU_UNANCHORABLE` | `runs.py` | pre-split windows (`BR-RAT-021`) have no per-window anchor |

**4–7 are BLOCKS and not decisions**, each in `NOT_RETRYABLE_HERE`: every
repair is in Meter Reads and nothing on the phase-3 screen performs one.

### Worked figures

* **the ruling's own case** — May closes at 13,500, June's read counts from
  13,800 to 14,212. The period bills **712**, not 412, `prior_read` prints
  **13,500** so the document foots, and `unanchored_prior_read` records the
  13,800 that moved.
* **already aligned** — May closes at 13,800 and June opens at 13,800:
  metering's own **412** stands, untouched, and `unanchored_prior_read` is
  None. This is every account in every pre-ruling fixture, which is why no
  ❄️ B4/B5 figure moves.
* **a wrap the anchor need not span** — May closes at 99,800 and the period
  reads 99,800 → 240: metering's wrap-aware **440** (❄️ GT-4/GT-14) stands and
  billing neither recomputes nor refuses it.
* **a wrap the anchor WOULD have to span** — May closes at 99,800, a re-read on
  10 June catches the wrap, and the billed read is 240 → 700. Refused by name.

### Proof

**15 passed.** RED first, in a worktree pinned at the tip:

| Guard removed | Measured |
|---|---|
| the `_anchor_quantity` call | `assert Decimal('412.000000') == Decimal('712')` — the 300 kWh lost — and neither exclusion fired |
| the ASSET check alone, everything else intact | `assert [] == ['anchor_meter_exchanged']` — the exchange silently anchored into a fiction |

### Reported, not fixed

* **`G124`'s emitted-kind count does NOT move, and nothing is left behind.**
  Both branches always emitted the ONE literal `billing_continuity`, so removing
  the register branch cannot change a count of KINDS — the calendar branch still
  emits it and still draws no chip. An expectation that the count would move
  rests on the two branches having had separate kinds, which they never did.
  Verified: `reason="billing_continuity"` now appears exactly once in `runs.py`,
  at the calendar site.
* **The meter-exchange refusal has a stated blind spot.** It fires when
  metering's analysis seam names a DIFFERENT asset for this period's read. Where
  that seam does not carry the read at all, the asset is unknown and no exchange
  is claimed — an unknown is never an accusation. The residue is an exchange
  whose new meter starts ABOVE the old one's last read AND whose read is
  invisible to the judgment seam; the wrap refusal does not catch that one
  either, because the arithmetic looks ordinary. Closing it needs a published
  `replaced_by_asset` link, which `read_analysis._replacement_row` already
  reports as owed and which is not billing's to mint.
* **Only the CYCLE path anchors.** `backbill` and `single` name their own window
  on purpose and are byte-identical. Whether a single bill should anchor is a
  real question and is not answered here.
