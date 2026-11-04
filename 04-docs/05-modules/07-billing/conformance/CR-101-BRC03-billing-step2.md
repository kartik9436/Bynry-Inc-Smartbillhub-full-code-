# `CR-101-BRC03` · Billing §03, the bulk bill run — STEP 2, the build

**What this is.** The record of what step 2 BUILT against §03 of
`05-prototype/04 Billing, As Built.pdf`, and — the half that matters more — what it did
not, with the reason for each. It is scoped from
`conformance/CR-100-BRC03-billing-step1.md` and from the §03 half of
`blueprint/02-runs-single-budget-fix.md` (**31 drawn entries**, p028–p099).

| | |
|---|---|
| Branch | `claude/eager-johnson-r0k88b` · `CR-101-BRC03` |
| Drawing | derived from the DEFAULT branch, sha256 `137a2a48…c200971`, **not from a scratchpad copy** |
| Files built in | `07-frontend/src/features/billing/{BillRunWizard,billRunShared,billRunStep23}.tsx` |
| Version | **none taken** — `2.262.0` is on the branch and a sibling holds it |
| Walked | **1280 and 1440**, in a browser, against a booted stack |

## The three things built

### 1 · The case filter offers the nine kinds the engine raises (`DEF-2596`)

| | |
|---|---|
| Emitted by `runs.py` `AccountProblem(reason="…")` | **2** |
| Emitted by `read_analysis.READ_ANALYSIS_CASES` | **7** |
| **Emitted, total** | **9** |
| Declared by the screen, before | **15** |
| Declared by the screen, after | **9** |
| Families, before → after | 3 → **2** (`owes` held only unraisable kinds) |

The six removed: `overcharge`, `no_usage`, `owes`, `past_due`, `late_fee`, `extra_charge`.
Rule: blueprint §03 p041 — *"A case kind the engine did not raise gets no chip."*

**And the mirror, which costs more:** a served row of an undrawn kind belongs to no family and
would be filtered out of every table. `casesWithNoChip()` names it on screen instead.

**`G124`** reads the Python emitters and the TypeScript constant independently — the two lists
live in two languages and nothing had ever compared them. Proved RED through `run_gates.py`.

### 2 · Step 1's copy is the drawing's — 138 words → 38

Nine strings of `16 Scope`, one of only two §03 entries carrying a `BUILD THIS` band.
Longest sentence **18 → 6**; heading **7 words → 2**; **14 words of rationale removed**, not
shortened (B14 rule 33). The cycle field now shows the chosen cycle's own routes and code,
derived, never typed (B14 rule 37).

### 3 · Is billing continuous? (p046 badge, p048 reasoning)

Three states plus a fourth that renders nothing, driven in a browser from this tenant's real
run history. It costs no new read. **Not a refusal** — the blueprint's own ruling for the gap
case; the overlap refusal it floats was NOT decided here and is not built.

## What was NOT built — 28 of the 31 entries, each with its reason

**The four-step redraw is the big one and it is a wave of its own.** `17.L1`–`17.L5`, `17.0`,
`17 Check`, `17.1`–`17.22`, `18`, `19` all assume a screen that replaces steps 2, 3 and 4 of
the shipped six. That collapse moves `billRunStep23.tsx` (102 KB) and three test files, and it
is where the KPI band, the bands by state, the search, the filters, the `AMOUNT` column and the
reconciliation (*"Nobody is missing from this list"*, the blueprint's own *"most important
thing on the screen"*) all live.

| Blocked or deferred | Why |
|---|---|
| `WHAT THIS COVERS` (5 counts) | `New read S46` — no endpoint counts units, masters, meters or unmetered points for a cycle before a run |
| `Which accounts` · `Also include` | `POST /billing/runs` scopes to a cycle; no sub-scope is taken |
| `DEFAULTS` + `Label this run` | `bill_runs` has no label or defaults columns — a migration |
| `LABEL` · `BY` · `Take it over` | `run_by`/`created_at` are stored and unserved; *Take it over* is a reassignment nobody has ruled |
| The background-run footer sentence | **It would be false today** — the wizard calls `calculate` inline (`DEF-1084`). Hard-won law 1 |
| `20.2` Hold one · `20.3` Release | **`Blocked S37`** — the drawing's own rule table asks the PO whether a standing hold may exist at all |
| `16`'s `Blocked S89` | Unresolved on the drawing |
| `BIL-S90` (25,000 cap) | PO ruled 2026-09-14: the cap stays, a run is scoped to a cycle |
| **`BIL-S39`** (`17.11`, `17.15`, `20`) | **Blocked** — carries both figures with the PO. Nothing per-connection priced, no ladder reset, no fee moved; the two gather refusals untouched |
| **`BIL-S102` + `BIL-S77`** (`17.20`) | **Ruled and real, not started.** The `$25` floor moves from a default argument in `late_fee.py` into tenant settings. Needs a migration and a settings surface; `S77` says one number in one place, so half is worse than none. **Wants its own lane.** The value does not move |

## How to re-run this rather than trust it

```bash
python3 10-scripts/gates/g124_case_chips_the_engine_raises.py     # the two lists, both sides
npx vitest run src/features/billing/cr101PeriodContinuity.test.ts # 8 cases, no drawn date
CHROME_PATH=… node 10-scripts/cr101_billrun_scope_walkthrough.mjs # 1280 and 1440, word counts
```

⚠ **The walkthrough found two faults in ITSELF before it found any in the product**, and both
are hard-won law 7 shapes: it read the cycle picker before the query answered and reported an
empty picker that held seven; and it compared one family's eight kinds against the engine's
nine. It later said **WALK CLEAN while never touching the continuity band**, because it guessed
the runs envelope. An undriven band is a FAILURE there now. **A check whose failure message
reads plausibly is the hardest kind to doubt.**
