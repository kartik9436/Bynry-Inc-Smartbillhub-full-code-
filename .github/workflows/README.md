# Every workflow in this folder is OFF, deliberately

**Ruled by the Product Owner on 2026-09-04, in these words:**

> *"in my repo, in the .github youve written github actions on PR, I dont want any of
> those, I have exhausted all my github actions free minutes and I dont want any github
> actions to run on this project, disable al of them."*

## What was done, and why this shape

All seven workflow files that existed on 2026-09-04 are still here, byte for byte, renamed from `<name>.yml` to
`<name>.yml.disabled`:

| File | What it used to run |
|---|---|
| `gates.yml.disabled` | the gate stack, plus G12's executable red-proof |
| `ci-backend.yml.disabled` | migrations against a real `postgres:16`, then the Python suite; the OpenAPI contract diff |
| `ci-frontend.yml.disabled` | `tsc`, eslint and the vitest suites |
| `qa.yml.disabled` | the Playwright journey specs under `08-qa/` |
| `migration-guard.yml.disabled` | migration ordering |
| `security-scan.yml.disabled` | gitleaks |
| `trace-lint.yml.disabled` | the Trace-header lint |
| `field-app-eas.yml.disabled` | **born disabled, 2026-10-21 (CR-187-BRC10, T-57)** — the native field app's EAS store builds and signed over-the-air updates, by hand-started dispatch only. It never ran; it was written so the pipeline and its secrets could be reviewed before the first store build. See `04-docs/05-modules/18-field-app/15-release-and-rollback.md` |

**GitHub reads only `.yml` and `.yaml` in this folder**, so a renamed file is invisible to
it: no run is queued, nothing is billed, and no check appears on a pull request. Renaming
rather than deleting keeps every definition readable and makes turning one back on a
one-word change — `git mv gates.yml.disabled gates.yml`.

## ⚠ What this costs, stated plainly rather than left to be discovered

**Nothing in this repository is verified by a machine any more.** Every proof is now a
person or an agent running it by hand and quoting the result:

    ./10-scripts/gates/run_gates.py                      # the gate stack
    cd 06-backend && pytest -q                           # the Python suite (SQLite)
    cd 07-frontend && npx tsc --noEmit && npx vitest run  # types and the front end
    node 10-scripts/render-checks/<the wave's>.mjs        # the browser walkthrough

⚠ **AND SEVERAL DOCSTRINGS IN THIS REPOSITORY STILL SAY THEIR CHECK "RUNS IN CI".** They
were true when they were written and they are claims about a thing that no longer happens
— hard-won law 1, in the file that caused it. `g12_selftest.py`, `g54_image_build.py`,
`g55_commit_fix_claims.py`, `g31_declared_classes.py` and `06-backend/tests/test_be11_openapi.py`
each name a workflow by path. They are stamped where they matter; if you add a check, do
not write that CI runs it.

**Law 14 is the sharpest edge.** `config/settings/test.py` hardcodes in-memory SQLite, so
anything that depends on PostgreSQL behaviour — an aborted transaction, a `CHECK`
constraint, row-level security — is proved only by the `tests/*_pg.py` files run against a
real PostgreSQL by hand. `ci-backend.yml` was the only thing that booted one automatically.

## Turning them back on

`git mv <name>.yml.disabled <name>.yml`, one at a time. Before doing so, check the Actions
minutes balance under the account's billing settings — the exhaustion that caused this had
a precise moment: the last run a machine actually picked up was **20:30:52 UTC on
2 September 2026**, and every run after **20:43:29** finished in three to twelve seconds
with `runner_id: 0`, no runner name and no log, on every workflow and every branch.
