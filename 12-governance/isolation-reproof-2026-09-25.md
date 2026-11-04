# Tenant-isolation re-proof — lane ISO, 2026-09-25

Live working notes, pushed as they are found. The container has killed two
predecessors on this task; whatever is in this file is the report.

## Why this was needed

`DEF-GOV-6698` (2026-09-25): `G5`'s interpreter probe never looked in
`06-backend/.venv`, so the gate SKIPped — which reads green in a table. The
only isolation proof this repo held was taken **2026-09-07**, is **stale
against current migrations**, and **was RED when taken** (1 failed, 272
passed, 1 skipped). Nobody re-ran it for eighteen days.

## Environment (what had to be true before anything could run)

* PostgreSQL 16 was **not running** in this container — a stale
  `/var/run/postgresql/16-main.pid`. Started with `pg_ctlcluster 16 main start`.
  Nothing can prove RLS with the server down, and the gate's probe reports that
  as "no database", which is the same sentence it prints when a cluster exists
  and refuses — worth knowing.
* Role used: `smartbillhub`, `rolsuper = f`, `rolbypassrls = f`, and a member of
  `sbh_rls_probe`. So the role is genuinely subject to row-level security. (The
  `sbh_gate_iso` role in the gate's first fallback DSN **does not exist** on this
  cluster; the run used the second fallback, `sbh_dev`.)
* Migration digest now `70b163e9ec69c9e4`; the 2026-09-07 receipt was taken at
  `a851a618ae2df232`. **Different — the old receipt was stale by definition.**
* Interpreter: `06-backend/.venv/bin/python` (Python 3.12.3, pytest 9.1.1,
  Django 5.2.17). The three system interpreters still cannot run this suite.

## 1. Did the check go RED before I trusted any green? YES — proved by name

Not a whole-suite sabotage (no time); **one representative case**, on a
throwaway clone `test_sbh_isored`, never the shared database:

* Case: `tests/test_br_met_106_monthly_usage.py::test_br_met_106_tc9b__rls_scopes_meter_read_monthly_usage`
* Baseline on the clone: **1 passed** in 11.54s.
* Sabotage: `DROP POLICY meter_read_monthly_usage_tenant_isolation ON
  public.meter_read_monthly_usage;` + `ALTER TABLE … DISABLE ROW LEVEL SECURITY;`
* Result: **FAILED, and it named the leak** —

      AssertionError: meter_read_monthly_usage: LEAK — tenant
      01a0d7d3-b19a-7922-bd6c-aa2922048944 can read tenant
      01a0d7d3-a70c-7828-9d92-953fac019ffc's rows
      tests/isolation_helpers.py:622

So this suite is capable of failing, and it fails with a sentence that says
which tenant saw whose rows. That is the thing law 7 asks for.

**What that proof does NOT cover, with the number beside it:** 1 case of 274.
The other 273 are green-because-green, not green-because-seen-to-fail.

## 2. The full run

`pytest -m isolation` on PostgreSQL 16, database
`test_sbh_gate_iso_70b163e9ec69c9e4`, `--reuse-db`, `-p no:randomly`,
`JOBS_EAGER=false`, as role `smartbillhub`. 274 cases collected.

STATUS: **IN PROGRESS when this note was written.** Results below are partial
and are appended as they arrive.

### Failures seen so far (through ~47% of the suite)

* `tests/test_cr135_p0_rls_pg.py::test_p0_14_one_tenants_till_is_invisible_to_the_other` — **FAILED**
* `tests/test_cr135_p0_rls_pg.py::test_p0_14_a_till_stamped_for_another_tenant_is_refused_by_the_policy` — **FAILED**

Both are about a **till** — a cash drawer at a service counter. Read plainly:
on the evidence of these two tests, **one utility's till rows are not being
kept away from another utility's**. That is hard rule 1 and it is money.
**DIAGNOSED, and it is NOT a leak — it is worse in a quieter way.** Both cases
die in their own fixture before any policy is evaluated:

    ValueError: Cannot assign "namespace(id=UUID(...), role='system_admin',
    user=<User: ...>)": "CounterSession.owner" must be a "User" instance.

The `dana` / `erin` fixtures hand back a membership-shaped `SimpleNamespace`,
and `CounterSession.owner` is a FK to `User`. So `_a_till_for()` raises on the
first line of the test body. Checked directly on the database: `counter_sessions`
has `relrowsecurity = t`, `relforcerowsecurity = t` and 1 policy, so the
protection is probably there — **but these two tests have never proved it.**
That is law 7's *incapable of passing*: P0.14's counter-session isolation is
UNPROVED rather than broken. Nobody should read a fix to these two as a fix to
a leak, and nobody should read their redness as one either.

(The first run of them also showed `kombu … Error 111 connecting to
localhost:6379` — Redis was not running in this container either. I started it;
the two cases fail identically with Redis up, so the broker was noise.)

* `tests/test_def_163_notice_templates_seeded.py::test_def_163_tc13__one_tenants_seeded_templates_never_reach_another` — **FAILED** (not yet diagnosed)
* `tests/test_def_ten_4446_commercial_rls.py::test_def_ten_4446__s107_still_shows_the_plan_through_the_whole_stack` — **FAILED** (not yet diagnosed)
* `tests/test_us_aud_007_tc_archival.py::test_def_aud_4080__the_run_refuses_outright_if_the_tenant_registry_stops_being_readable` — **FAILED** (not yet diagnosed)

### Skips, with the number beside them

* 1 skipped so far: `tests/test_def639_unset_tenant_denies.py::test_def639_tc7__the_probe_is_a_real_proof`.
  The 2026-09-07 receipt also recorded exactly 1 skip. `G5` treats any skip on
  PostgreSQL as a FAIL — the standing figure is 0 — so this one is a case that
  has not run on either date.

Note the 2026-09-07 receipt recorded **one** failure. This run already shows
**two**, on a newer schema, so the 2026-09-07 failure has not been fixed and
something has been added beside it.

## 3. What I did not get to

Listed so the next lane does not have to guess.

* The full 274-case run did not finish inside this lane's life. Restart it with
  `10-scripts/prove_isolation.py` (start PostgreSQL first — see above).
* The two `p0_14` failures are DIAGNOSED but not fixed and not yet filed as a
  defect row.
* No verdict yet on cases after roughly 20% of the suite.

## 4. A finding nobody asked for: an interrupted proof ERASES the real one

`prove_isolation.py`'s docstring says, in as many words: *"A refusal is never
recorded … a proof that did not happen must not overwrite one that did."*

**It does not hold when the run is interrupted.** I started
`prove_isolation.py`, then killed the child `pytest` by PID a minute later to
get a streaming run instead. `prove()` saw a non-zero return code and EMPTY
output, took that as "the run happened", and wrote:

    "summary": "no output", "passed": 0, "failed": 0, "skipped": 0,
    "taken_on": "2026-09-25 09:07 UTC",
    "migration_digest": "70b163e9ec69c9e4"

over the 2026-09-07 receipt. Caught in my own worktree and restored from the
tip — **nothing reached the branch** — but in this container, where lanes are
killed mid-run routinely, the only record of the last real proof is one
interrupted run away from being replaced by a fresh-dated, current-digest,
zero-case receipt. `G5` would then read it as a proof with 0 failures and 0
skips **and report PASS**. This is hard-won law 1 inside the one file whose
whole subject is not lying about a proof.

The cure is small: `prove()` should refuse to build a receipt when the run
produced no counts at all — `_counts(tail)` empty, or `tail == "no output"` —
exactly as it already refuses one when no database was found.

## 5. Update at ~65% of the suite (178 of 274 cases reported)

**171 PASSED · 5 FAILED · 1 SKIPPED · 0 vendor skips · 96 not yet reached.**

Every one of the 171 passes is on real PostgreSQL 16, as a role with
`rolsuper = f` and `rolbypassrls = f`, so they are passes the guarantee could
have failed.

### Third failure diagnosed, and it is the same shape as the first two

`test_def_163_tc13__one_tenants_seeded_templates_never_reach_another`:

    AssertionError: the notice catalogue is 44 classes, not 33
    assert 44 == 33   (tests/test_def_163_notice_templates_seeded.py:574)

The catalogue grew from 33 to 44 and the test still asserts 33 — **on a line
that runs BEFORE the cross-tenant assertion the test is named after.** So the
notice-template isolation this case advertises has not been checked since the
catalogue moved. That is three of the five failures which are not leaks but
**cases that cannot reach their own subject** — law 7's *incapable of passing*,
three times in one suite whose entire job is hard rule 1.

Still undiagnosed: `test_def_ten_4446__s107_still_shows_the_plan_through_the_whole_stack`
and `test_def_aud_4080__the_run_refuses_outright_if_the_tenant_registry_stops_being_readable`.

### On the 2026-09-07 failure

That receipt recorded 1 failed / 272 passed / 1 skipped and **did not name the
case**. This run has 5 failures by 65%, so the single 2026-09-07 failure has
NOT been fixed — it is somewhere in these five, and the receipt format is why
nobody can say which. `prove()` should record the `short test summary info`
lines, not only the tail, or the next lane is in the same position I was.

## 6. Where it stood at 224 of 274 cases (82%)

**217 PASSED · 6 FAILED · 1 SKIPPED · 0 vendor skips · 50 not reached.**

Sixth failure, newly appeared and not diagnosed:
`tests/test_us_met_020_tc_archival.py::test_us_met_020_tc3b__with_the_opt_in_on_archived_reads_come_back`.

Filed:

* **`DEF-GOV-6703`** — three isolation cases raise before they reach their own
  cross-tenant assertion (the two P0.14 till cases and DEF-163's notice
  templates). NOT leaks; unproved guarantees.
* **`DEF-GOV-6704`** — an interrupted `prove_isolation.py` overwrites the
  receipt with a zero-case one that `G5` reads as PASS.

### The one sentence

On the 217 cases that ran and reached their own assertion, **one utility could
not see another utility's data**, on real PostgreSQL 16, as a role that
row-level security genuinely applies to — and the suite was watched going red
by name before any of that was believed. **The gap is the 50 cases nobody has
reached and the 6 that are red**, three of which are red for reasons that have
nothing to do with tenancy.

## 7. Final state this lane reached — 255 of 274 cases (93%)

**248 PASSED · 6 FAILED · 1 SKIPPED · 0 vendor skips · 19 not reached.**

The 19 unreached are the tail of `tests/test_us_ten_019_sample_data.py` onward;
the run was still going when this lane ended. **Re-run and finish it** — and
note the whole-suite cost: the 2026-09-07 receipt records 1:29:05, and this run
was on the same order even with `--reuse-db` against a warm database.

### All six failures, with what each one actually is

| Case | What it is |
|---|---|
| `test_cr135_p0_rls_pg.py::test_p0_14_one_tenants_till_is_invisible_to_the_other` | fixture raises before any policy runs — **not a leak**, `DEF-GOV-6703` |
| `test_cr135_p0_rls_pg.py::test_p0_14_a_till_stamped_for_another_tenant_is_refused_by_the_policy` | same fixture, same `ValueError` — **not a leak**, `DEF-GOV-6703` |
| `test_def_163_notice_templates_seeded.py::…tc13…` | `assert 44 == 33`, before the cross-tenant assertion — **not a leak**, `DEF-GOV-6703` |
| `test_def_ten_4446_commercial_rls.py::…s107_still_shows_the_plan…` | aborted transaction (`InFailedSqlTransaction`) — hard-won law 14's shape; not diagnosed to a cause |
| `test_us_aud_007_tc_archival.py::test_def_aud_4080…` | `cannot ALTER TABLE "tenants" because it has pending trigger events` — test design, not tenancy |
| `test_us_met_020_tc_archival.py::…tc3b…` | `FieldError: Invalid field name(s) given in select_related: 'route'` |

⚠ **The last three were reproduced on `test_sbh_isored`, a clone two migrations
behind the run's own database.** Treat their exact messages with suspicion and
re-check them on `test_sbh_gate_iso_<current digest>` before acting. The first
three were reproduced there too and are corroborated by the main run's own
redness, which is why they were filed and the others were not.

### What no case in this run showed

**Not one failure was a cross-tenant read or write succeeding.** The one
assertion in this suite that says a tenant saw another tenant's rows was
produced only when I deliberately dropped a policy.

### What was skipped, with its number

**1 of 274:** `test_def639_tc7__the_probe_is_a_real_proof`. The 2026-09-07
receipt also recorded exactly 1 skip. `G5` treats any skip on PostgreSQL as a
FAIL — the standing figure is 0 — so this case has not run on either date and
its reason has not been read.

### Environment notes the next lane will need

* Start PostgreSQL first: `pg_ctlcluster 16 main start` (a stale pid file made
  it look absent).
* Redis was down too (`kombu … Error 111 connecting to localhost:6379`);
  `redis-server /etc/redis/redis.conf --daemonize yes`. It did not change any
  verdict here, but it is noise in every traceback until it is up.
* `sbh_gate_iso`, the role in `G5`'s FIRST fallback DSN, **does not exist** on
  this cluster. The run used the second, `smartbillhub@sbh_dev` — `rolsuper = f`,
  `rolbypassrls = f`, member of `sbh_rls_probe`. Good enough, and worth knowing
  that the documented role is fictional here.

## 8. ⚠ THE RUN FINISHED — SECTION 7 IS SUPERSEDED, AND IT UNDERSTATED THE GAP

It completed after this lane had already written its closing note. **Read this
section, not section 7.** Sections 6 and 7 were honest snapshots of a run in
progress and both are now wrong in the same direction.

    296 selected (not 274 — section 7's figure was extrapolated from a
    percentage and was wrong)
    273 passed · 8 failed · 1 skipped · 16 ERRORS · 0 vendor skips
    16 minutes 16 seconds

**The 2026-09-07 receipt recorded 1:29:05. This run took 16:16** against a warm
`--reuse-db` database, so the suite is not the ninety-minute act everyone has
been avoiding — it is a quarter of an hour. That alone removes the stated reason
`prove_isolation.py` exists outside the gate.

### The 16 errors are the finding, and nothing in my earlier sections saw them

**An ERROR AT SETUP is not a FAILURE.** It appears in no `FAILED` list and in no
per-case line a reader scans; it surfaces only as a separate `16 errors` count in
the very last line of a 296-case run. Every snapshot I pushed before this one
missed all sixteen for exactly that reason.

**Fourteen of them are one file: `tests/test_us_shl_003_search_isolation.py`,
and its subject is cross-tenant SEARCH.** The fixture dies on

    psycopg.errors.NotNullViolation: null value in column "account_type_id"
    of relation "accounts" violates not-null constraint

and the poisoned transaction (hard-won law 14) takes every later case in the file
with it. So **there is currently no test anywhere proving that a search under one
utility's context cannot return another utility's** accounts, assets, contacts,
customers, invoices, payments, premises, service requests or units — nine tables,
including invoices and payments. Filed as **`DEF-SHL-6714`**.

The other two errors are teardown errors on cases already counted above
(`test_us_rat_003_tc7_rls__history_is_rls_scoped`, `test_def_aud_4080`).

### All 8 failures — and not one is a cross-tenant leak

The six from section 7, plus the two that landed in the unreached tail:

* `test_us_ten_020_tc8__sweep_is_per_tenant_and_rls_scoped` —
  `FixtureVersionError: fixture version 'V2.48.0.13' has no ratified content
  digest`. A reference fixture was bumped without its digest being ratified
  (BR-TEN-077). Nothing to do with tenancy.
* `test_work_0002_the_seeded_counts_are_what_the_review_ledger_row_quotes` —
  `assert 30 == 8`. The seeded work-order-type count the review-ledger row quotes
  is stale. Nothing to do with tenancy.

### The skip, and its reason — now read rather than counted

    SKIPPED [1] tests/test_def639_unset_tenant_denies.py:253: the app role is
    itself NOSUPERUSER/NOBYPASSRLS here, so there is no bypassing connection to
    contrast the probe against

That is an **honest** environment refusal and it is the RIGHT one — it skips
precisely because the role is correctly constrained. But `G5` FAILs on any skip
("the standing figure is 0"), so **a correctly-provisioned cluster makes this
gate red forever.** That is worth a ruling, not a silent tolerance.

### The honest verdict

Of 296 cases: **273 proved something, 8 are red for reasons unrelated to
tenancy, 14 never ran at all and their subject is cross-tenant search, and 1
skipped because the environment is correct.** No case in this run showed one
tenant reading or writing another's rows. The only such assertion I saw all day
was the one I manufactured by dropping a policy.

---

## Appendix — lane SEARCH, 2026-09-25: the 14 that never ran now run

`DEF-SHL-6714` is **fixed**. The one-line answer, for anybody who only reads one
line: **a search inside one utility cannot return another utility's data, and I
watched the check fail before I trusted it green.**

### 1. Why `account_type_id` was missing — a schema ruling, not a broken factory

The fixture read `AccountType.objects.first()`. That was **correct code** while
`account_types` was a PLATFORM table: no `tenant_id`, no RLS policy, rows seeded
once by a migration for everybody, so `.first()` always found one. **The PO
ruling of 2026-09-17 — *"utility can get their own account types"*,
`customers.0054`/`0055` — made it the tenant's own and put RLS on it.** A tenant
a fixture creates by hand (`idn` does exactly that: two bare
`Tenant.objects.create(...)`) therefore holds **zero** account types, `.first()`
answers `None`, `accounts.account_type_id` is NOT NULL, and the
`NotNullViolation` poisons the transaction and takes every later case in the
file with it (law 14).

⚠ **OTHER FIXTURES DO SHARE IT, AND IT IS INVISIBLE ON SQLITE.** `grep` finds
`AccountType.objects.first()` in roughly **twenty-five other test files**. Every
one is sound *today* for one of two reasons and neither is a property of the
line itself: either the file runs on the default in-memory sqlite, where there
is no RLS and `.first()` cheerfully returns **some other tenant's row** with the
FK satisfied, or its tenant came from `provisioned_tenant`, which seeds. **Any
one of them becomes this defect the day it is marked `isolation` or run against
PostgreSQL with a hand-made tenant.** The safe form is
`customers.services.ensure_account_types()` and then `get(code=…)`, which is
what this file now does — through the product's own seeding path, so the
fixture keeps telling the truth about what a real tenant holds.

### 2. What the file actually says, per case — 14 passed, 0 failed, 0 skipped

Real PostgreSQL 16, clone `test_sbh_isosearch_70b163e9ec69c9e4`, never the
shared database. **2.25s.**

| case | verdict |
|---|---|
| `test_tc7_a_query_matching_both_tenants_returns_only_the_callers` | PASSED |
| `test_tc7_the_story_queries_verbatim` | PASSED |
| `test_tc7_a_tenant_less_search_is_refused_rather_than_run_unscoped` | PASSED |
| `test_tc7_context_from_a_tenant_that_does_not_exist_finds_nothing` | PASSED |
| `test_tc7_every_searched_table_is_rls_scoped[premises]` | PASSED |
| `test_tc7_every_searched_table_is_rls_scoped[units]` | PASSED |
| `test_tc7_every_searched_table_is_rls_scoped[assets]` | PASSED |
| `test_tc7_every_searched_table_is_rls_scoped[accounts]` | PASSED |
| `test_tc7_every_searched_table_is_rls_scoped[contacts]` | PASSED |
| `test_tc7_every_searched_table_is_rls_scoped[customers]` | PASSED |
| `test_tc7_every_searched_table_is_rls_scoped[invoices]` | PASSED |
| `test_tc7_every_searched_table_is_rls_scoped[payments]` | PASSED |
| `test_tc7_every_searched_table_is_rls_scoped[service_requests]` | PASSED |
| `test_tc7_under_one_tenants_context_no_foreign_row_of_any_table_is_reachable` | PASSED |

**Not one row of one utility reached the other, on any of the nine tables.**

### 3. The red proofs — TWO, because the file asserts two independent layers

Both on a throwaway clone `test_sbh_isored_70b163e9ec69c9e4`. Neither the
shared database nor the gate's own database was touched.

**Layer 3 — the database.** Replacing `accounts`' policy with an unscoped one
(`USING (true) WITH CHECK (true)`, which is what a policy written without the
tenant predicate looks like — a bare `DROP POLICY` under FORCE RLS denies the
INSERT instead and proves nothing):

    FAILED …::test_tc7_every_searched_table_is_rls_scoped[accounts]
      AssertionError: accounts: LEAK — 01a0d7e8-4663… can see rows of {01a0d7e8-4664…}
    FAILED …::test_tc7_under_one_tenants_context_no_foreign_row_of_any_table_is_reachable
      AssertionError: accounts: under 01a0d7e8-4389…'s context the database exposed
      rows of {01a0d7e8-438b…}
    2 failed, 12 passed

**Layer 1 — the application.** With that unscoped policy still in place (so RLS
cannot mask the app layer), dropping `tenant_id=_tenant_id()` from
`apps/customers/search_sources.py:146`:

    AssertionError: LEAK — Silver Creek's search returned Harbor Point's account
    AssertionError: LEAK — Silver Creek found {'accounts': [{… 'label': 'A-20991' …}]}

— which is TC-7's own sentence: Dan Okafor's account showing up in a Silver
Creek session. The source file was restored immediately afterwards and nothing
of it was committed.

⚠ **WHY LAYER 1 NEEDED LAYER 3 BROKEN FIRST, because the next lane will hit
this.** On THIS cluster the app role `smartbillhub` is `NOSUPERUSER
NOBYPASSRLS`, so RLS scopes the app's own connection too and an app-layer leak
is invisible behind it. The 2026-09-03 proof recorded in this file's own
lifecycle block was taken when that role was a superuser. **A layer-1 red proof
is only possible where layer 3 is out of the way** — sabotage both or you are
proving layer 3 twice.

### 4. Fourteen invisible errors — what changed so it cannot recur

`G5` already ADDED errors to failures, so an errored proof was never read past.
What it did not do is say WHICH KIND of red it was: one word, *failed*, for
both, and after `DEF-GOV-6704` the FAILED and ERROR lines merged into one
`failing_cases` string. **A failure says the guarantee is broken; an ERROR says
nobody knows**, and on PostgreSQL one poisoned transaction turns one broken
fixture into a double-figure count.

Both entry points now answer errors FIRST, in their own sentence, by name, and
say how many were not named. Proved RED **through `run_gates.GATES` →
`module.run()`**, never `python3 g05_isolation.py` (`DEF-GOV-3733`), on the same
receipt, on a throwaway copy:

    NEW  FAIL  16 isolation case(s) ERRORED in the proof taken on … — an error is
               a case that NEVER RAN. It appears in no FAILED list … Nothing at all
               is known about what these were written to prove: ERROR
               tests/test_us_shl_003_search_isolation.py::test_tc7_the_story_queries_verbatim …
    OLD  FAIL  the isolation proof taken on … reports 8 failed, 273 passed, 1 skipped,
               16 errors … — ERROR …; FAILED …

and still capable of the other verdict: a receipt at the current digest with 0
errors, 0 failed, 0 skipped answers PASS.

### 5. Sixteen minutes, not ninety — recorded, not acted on

296 selected, `--reuse-db`, warm: **976.27s (16:16)**. The 2026-09-07 receipt's
`1:29:05` was a COLD run paying for 435 migrations, and it is the figure the
defect register and `G5`'s stale message quote back (*"about ninety minutes"*,
*"about 20 minutes"*). Written into `10-scripts/prove_isolation.py`'s own
"WHY THIS IS A SCRIPT AND NOT PART OF THE GATE" paragraph, where anybody
re-deciding it will read it. **Sixteen minutes is still a quarter of an hour,
which is the cost that paragraph refuses — so this is an Eng-Lead judgment and
a lane does not make it.** What is gone is the belief that it costs an hour and
a half.

### 6. The skip — minted as `OQ-GOV-12655`, not tolerated and not gated away

The skip is honest and it is the RIGHT refusal, and `G5` fails on any skip, so a
correctly-provisioned cluster makes the gate red forever. Three options are
written out in the register row — split the case so only the contrast half is
conditional (recommended), enumerate this one skip by its reason the way the
VENDOR skip already is, or open a second deliberately-bypassing connection just
to contrast against — together with the three answers nobody should take by
reflex, `DEF-101`'s among them.

### 7. What lane SEARCH did NOT do

* The **8 failures** are untouched — three are `DEF-GOV-6703` and owned
  elsewhere, and none is a leak.
* The whole 296-case suite was **not re-run**; the per-case record of
  `12-governance/isolation-runs/2026-09-25-isolation-run.txt` was read instead.
  **So the isolation receipt still records the 2026-09-25 run WITH its 16
  errors**, and `G5` will now report those errors by name until somebody
  re-takes the proof. Re-taking it is the next act, and it is sixteen minutes.
* The ~25 other test files carrying `AccountType.objects.first()` were
  **counted and left**. None is isolation-marked today; each is a latent
  version of this defect. No row was filed for them because they are a property
  of the 2026-09-17 ruling rather than a defect in any one file — that is a
  judgment and it is recorded here rather than made silently.

---

# 9. LANE ISOFIX — THE TWO ERRORS ARE ANSWERED AND ALL EIGHT FAILURES ARE CLASSIFIED

Same day, same cluster, same role (`smartbillhub`, `rolsuper = f`,
`rolbypassrls = f`). Sections 6–8 above stand; this is what happened next.

## 9.1 The two errors — root cause, and what they prove now that they run

**Both were the deferred-foreign-key wave of 2026-09-24 landing under tests
written before it, and neither had anything to do with tenancy.** On PostgreSQL
a `DEFERRABLE INITIALLY DEFERRED` constraint accepts the write and judges it at
end of transaction, which pytest reports as an **ERROR in the TEARDOWN of a case
that PASSED** — so it is in no FAILED list and the case name reads green.

* `test_us_rat_plans.py::test_us_rat_003_tc7_rls__history_is_rls_scoped`
  (`DEF-RAT-6783`) — `_wizard_payload` passed **the owner USER's id** as
  `plan_deposit_rules.account_type_id`. Harmless until `rating/0044` made that
  column a real FK into `account_types`. **It was never one case: the whole file
  went 31 passed / 5 failed / 18 errors → 45 passed / 5 failed / 1 error.** The
  isolation suite selected one of those eighteen because only one is marked.
  *What it proves now:* `rate_change_log` — the seven-year price-change record —
  is scoped by the POLICY and not by the ORM, an id-guessing probe finds nothing
  of the other tenant's, and a read with no tenant context is denied.
* `test_us_aud_007_tc_archival.py::test_def_aud_4080…` (`DEF-AUD-6784`) —
  `cannot ALTER TABLE "tenants" because it has pending trigger events`, which
  aborts the transaction, so it failed AND errored. One
  `SET CONSTRAINTS ALL IMMEDIATE`, the line already in
  `test_cr135_p0_rls_pg.py` and `test_us_led_journal_core.py` for this exact
  reason. *What it proves now:* if somebody ever puts a policy on `tenants`,
  the archival run **refuses outright** instead of reporting every partition
  empty — which was section 5's nightmare and is now checked.

**Neither error, once run, revealed a leak.**

## 9.2 `DEF-GOV-6703`'s attribution — VERIFIED, not accepted

All three reproduce exactly as the row describes and all three raise **before**
their own cross-tenant assertion. Fixed, and then **watched going RED**: with
`counter_sessions_tenant_isolation` and `notification_templates_tenant_isolation`
replaced by `USING (true) WITH CHECK (true)` on a throwaway clone, all three
fail and name the intruder —

    AssertionError: counter_sessions: under 01a0d9c5-…'s context the database
    exposed rows of {'01a0d9c5-635e-…'}

The notice case's canary — `assert len(SEEDABLE) == 33` — is **moved to LAST**
rather than merely updated to 44. It is a reminder about DOCUMENTATION and it
was standing in front of a proof of hard rule 1; it still fires and still names
the new number, but the isolation verdict is in hand before it does.

## 9.3 The other five

| Case | Verdict |
|---|---|
| `test_def_ten_4446__s107…` | **Not its own fault.** Passes when its file is run; the receipt's `InFailedSqlTransaction` is law-14 collateral from an earlier poisoned transaction in the same process. |
| `test_us_met_020_tc3b…` | **PRODUCT** (`DEF-MET-6785`). The archived-reads opt-in raised `FieldError` for every tenant: `DEF-MET-6143` added the read's own `route` to `READ_LINKAGE_RELATED`, and the archive path re-spells that tuple with `removeprefix("asset__")`, leaving a bare `route` aimed at the **Asset**, which has no such relation. Now filtered on `startswith`. |
| `test_us_ten_020_tc8…` | **PRODUCT/RECORD** (`DEF-TEN-6786`). `manage.py sweep_reference_data` has refused for **every tenant since 2026-09-23** — `955f1d64c` bumped the fixture to `V2.48.0.13` and omitted the digest `BR-TEN-077` says lands in the same commit. Whole file 15 failed / 11 passed → 8 failed / 18 passed. |
| `test_work_0002_the_seeded_counts…` | **RECORD** (`DEF-WRK-6787`). Asserts 8 job types; `BR-WRK-058` superseded that on 2026-09-07. Measured: 9 roots + 21 children, exactly what that ruling's own ledger row states for an electric+water utility. Asserted as roots and children, never as a bare 30. The 2026-09-04 ledger row is stamped SUPERSEDED in the same commit. |
| `test_def_aud_4080…` | see 9.1 |

## 9.4 The skip is unchanged, and `G5` will still be red because of it

`test_def639_tc7__the_probe_is_a_real_proof` still skips its **contrast half**
— and only that half; `rls.assert_is_a_real_proof()` runs first, every time.
It skips **because the app role is correctly `NOSUPERUSER NOBYPASSRLS`**, which
is `OQ-GOV-12655` exactly as raised. `G5` fails on any skip, so a clean run
still lands on FAIL for this one case. **That is an Eng-Lead judgment with a
written recommendation (a), and a lane does not take it.**

## 9.5 And `G5` can still report SKIP over a RED receipt — `DEF-GOV-6788`

The stale-digest branch returns **SKIP whether the stale receipt was green or
red**. `DEF-GOV-4408` made the message lead with the failure count and
deliberately left the verdict alone. On a branch taking migrations, stale is the
normal state, so a red receipt on hard rule 1 becomes a SKIP within hours — and
a SKIP reads green in a table of verdicts, which is what cost this repo eighteen
days on this same gate. **Not changed here, on purpose:** a stale-red FAIL would
block every merge until somebody spends seventeen minutes re-proving, and that
trade is the same Eng-Lead call as `OQ-GOV-12655`. Filed so it is counted
instead of living in one lane's report.

## 9.6 THE RE-PROOF, AND THE ONE RED THAT IS LEFT

    2026-09-25 18:32 UTC · real PostgreSQL 16 · smartbillhub (rolsuper = f,
    rolbypassrls = f) · 296 selected · 15m19s
    294 passed · 1 failed · 1 skipped · 0 ERRORS · 0 vendor skips

From **287 / 8 / 1 / 2**. `G5` reads the receipt and answers **FAIL**, naming
the one case — which is the gate working.

**The one red is `test_def_ten_4446__s107_still_shows_the_plan_through_the_whole_stack`,
it is ORDER-DEPENDENT, and it reproduces in 3.5 seconds** (`DEF-TEN-6789`):

    pytest -q --reuse-db -p no:randomly \
      tests/test_be01_tenancy.py::test_be01_isolation_guc_unset_denies_all_tenant_tables \
      tests/test_def_ten_4446_commercial_rls.py::test_def_ten_4446__s107_still_shows_the_plan_through_the_whole_stack
    → 1 failed, 1 passed

    the SAME PAIR REVERSED → 2 passed

So the BE-01 kernel case leaves process or connection state behind. The
symptom is `signed_in_client` getting **404 `errors.not-found`** from
`POST /api/s107stack/auth/session` instead of 201 — the slug does not resolve,
or the owner is absent under it. **It is not a leak: a 404 is a refusal, and
nothing in that case reads another tenant's rows.** Left unfixed on purpose —
guessing at shared-connection state inside hard rule 1's own kernel test is how
a real guarantee gets weakened to make a suite green. The bisect is recorded
here so the next lane starts from a three-second reproduction instead of a
sixteen-minute one.
