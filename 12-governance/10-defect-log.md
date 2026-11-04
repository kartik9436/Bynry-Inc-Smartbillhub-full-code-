# Defect Log — schema and how to use it

**The data lives in `10-defect-log.csv`.** GitHub renders it as a sortable table, and it opens in Excel — so one file serves both reading and reporting. This file is the data dictionary; it holds no rows, so the two can never drift.

Opened 2026-08-10 on the PO's instruction: *"create a bug history … later we will know where it is going wrong; we will also able to generate report on it."*

## Why a CSV and not a markdown table

A markdown table cannot be pivoted, filtered or counted without hand-work, and the whole point of this log is the counting. GitHub renders `.csv` natively, so nothing is lost in review. `python3 10-scripts/defect_report.py` prints the analysis; its output is **never committed** — one source of truth, derived views generated on demand. (That rule is itself a lesson from 2026-08-10, when the same generated OpenAPI schema was committed twice and the copies drifted.)

## The 14 columns, and why each earns its place

| Column | Values | Why it is here |
|---|---|---|
| `id` | `DEF-###` | Stable reference from commits and stories |
| `reported_on` | ISO date | Trend over time |
| `reported_by` | `PO` · `Eng-Lead` · `test` · `gate` · `CI` | Who is doing the finding. **If PO dominates, the checks are the problem** |
| `title` | one line | Human index |
| `surface` | `frontend` · `backend` · `infra` · `docs` | Where the work landed |
| `module` | the 14 module names, or `platform` | Which area concentrates defects |
| `severity` | `blocker` · `major` · `minor` · `cosmetic` | Blocker = the product cannot be used |
| `found_in` | `spec` · `review` · `test` · `gate` · `CI` · **`deployed`** | **The cost axis.** A defect found by a gate costs minutes; the same defect found on a live deployment costs a support cycle and trust |
| `introduced_in` | `spec` · `story` · `implementation` · `config` · `default` | Where it entered. Separating this from `found_in` is what exposes a *stage* that leaks |
| `category` | see below | **The "where is it going wrong" axis** |
| `escape_reason` | one line | Why no existing check caught it. The single most useful field in the file |
| `status` | `open` · `fixed` · `deferred` · `wontfix` | — |
| `fixed_commit` | short SHA | Traceability to the diff |
| `prevention` | gate/test added, or `none` | **A defect with `none` can recur.** Counting these is the health metric |

### `category` values

| Value | Meaning |
|---|---|
| `unscheduled-reported-gap` | Already written down in a code comment as reported/deferred, never turned into a story |
| `wrong-default` | Code was correct; the shipped default value was not |
| `unwired-prop` | Component built and styled, never given its data |
| `missing-shared-component` | Each screen solved the same problem separately, so each got it differently |
| `unverified-claim` | A comment or doc asserted a guarantee that nothing enforced |
| `stale-doc` | Documentation described a behaviour that had been superseded |
| `incomplete-seed` | Reference or sample data missing so a screen renders empty |
| `spec-divergence` | Two ratified sources disagreed and the conflict was left standing |

## How to add a row

Append one line to the CSV. Quote any field containing a comma. Keep `escape_reason` specific — *"no gate looks at rendered output"* is useful, *"missed it"* is not.

## Reporting

```bash
python3 10-scripts/defect_report.py            # summary
python3 10-scripts/defect_report.py --by module
```
