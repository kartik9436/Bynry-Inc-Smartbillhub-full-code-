#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:   US-RBS-010 · US-RBS-012 (EP-RBS-04) — CR-075 wave `M` tasks `M1`
#          (a full cycle of dry firings) and `M2` (the recurring database diff).
# Rules:   `BR-RBS-003` (dry and live are ONE path; only the writer differs) ·
#          `BR-RBS-002` (a Check holds no writer) · CLAUDE.md hard rule 1 ·
#          `BR-TEN-043` (the business day is an argument) · hard-won law 7
#          (prove the guard RED first, and say what it cannot see)
# Tests:   this IS the check. Its red proof is `--bind-writer`.
# ───────────────────────────────────────────────────────
"""A cycle of DRY firings of the collections ladder, and the diff after each.

⚠ **STARTED BY HAND, NOT BY A SCHEDULE, AND THAT IS THE HONEST STATE OF THE
PRODUCT.** `I2` (cron evaluated in the tenant's timezone) and `I3` (a missed
firing RAISES) are phase 4 under the 2026-09-06 re-cut, so nothing in this
product fires a runbook on a clock yet. Somebody presses Run each Monday, and
this script is that person's hand. **What it costs, said plainly: the PLANS are
soaked and the SCHEDULER is not.** Wave `I` gets its own soak; `M4`'s go/no-go
is about the plans, so it is unaffected — but no one may read this cycle as
evidence that a weekly schedule works, because there is no schedule.

WHAT `M2` ASKS FOR AND WHAT THIS ANSWERS
-----------------------------------------
*"A recurring database diff asserting zero rows written outside the seven
tables, run after each dry firing, and shown RED first with a writer
deliberately bound."* So: every table in the schema is counted before and after
each firing, and any movement outside this module's seven is a failure that
names the table and the two counts.

⚠ **IT COUNTS AS THE TENANT, AND THE FIRST VERSION OF ITS ANCESTOR DID NOT.**
`rbs_c_seed_run.py`'s docstring records the trap and it is repeated here because
it is invisible: row-level security is FORCE'd on every tenant table, and a
session carrying the database's default marker sees NOTHING — so every table
counts 0 before and 0 after, *"nothing moved"* is true of an empty VIEW rather
than of the database, and the script prints a confident pass over a run that
just wrote three rows.

⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY** (the question hard-won law 7 says
you must be able to answer):

  * counting only the tables I remember → it reads EVERY base table out of the
    catalog and derives the runbooks seven by name;
  * counting outside the tenant context → refused above, and the tenant id is
    printed with every snapshot;
  * counting on SQLite, where the policies do not exist → it REFUSES to run
    anywhere but PostgreSQL;
  * **a run that resolved NOTHING.** Zero subjects writes zero rows outside the
    seven tables, truthfully and vacuously. So a firing that plans no records at
    all is reported as a FAILED firing, not a clean one — that is the shape
    `G32` had when it reported *0 unresolved* over 21 live refusals;
  * **a database nobody else has data in.** *"Nothing changed"* over an empty
    schema is not evidence, so the number of tables outside this module that
    carry ANY rows is printed beside the verdict.

⚠ **THE ONE THING IT CANNOT SEE, WITH THE NUMBER THAT PROVES IT: AN UPDATE IN
PLACE.** This is a diff of ROW COUNTS, so an INSERT or a DELETE outside the
seven tables is caught and a port that OVERWROTE a column on ten thousand
existing rows would be invisible. It is not hypothetical and the second cycle
measured it: the second live firing of the red proof advanced the collections
tier on **812 rows of `account_collection_state`** and the table's count did not
move at all — `512 → 812` on the first firing, when 300 rows were inserted, and
then nothing. A declared blind spot with no number attached is indistinguishable
from an empty one (hard-won law 7), so it is stated here with its number rather
than left to be discovered. **What closes it, when somebody needs it closed:** a
per-table `max(updated_at)` or a checksum of the columns that matter, taken in
the same two snapshots.

THE RED PROOF, AND WHY IT NEEDS ITS OWN DATABASE
--------------------------------------------------
`--bind-writer` puts `collections_ladder` on `engine.acts.LIVE_ENABLED_RUNBOOKS`
for the length of the process. `executor.build_context` then hands the steps
their REAL ports, and runbook 8's act — `step_ladder`, payments' own port since
`DEF-RBS-4347`'s ruling on 2026-09-07 — writes the queue row, the
`notice_history` row and the `account_collection_state` tier. **All three tables
belong to other modules**, so the diff goes red on the one thing it exists to
catch. (Before that ruling the act was `queue_notice` and only `outbound_messages`
moved; the ladder never climbed, which is the defect that ruling closed.)

⚠ **RUN IT ON A SEPARATE CLONE.** A bound writer does not only prove the check;
it QUEUES REAL NOTICES and it burns the per-record idempotency keys, which are
`(runbook, action kind, subject, rung)` and carry no date. A red proof taken on
the cycle's own database would silently make every later firing say *"already
sent"* and the cycle would measure the sabotage instead of the product.

USAGE
-----
    # the cycle
    DATABASE_URL=…/sbh_clone_rbsm python3.12 rbs_m_dry_cycle.py \\
      --tenant brazosbend --mondays 2026-09-07,2026-09-14,2026-09-21,2026-09-28,2026-10-05

    # the red proof, on its own clone
    DATABASE_URL=…/sbh_clone_rbsmred python3.12 rbs_m_dry_cycle.py \\
      --tenant brazosbend --mondays 2026-09-07 --bind-writer
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import time

BACKEND = pathlib.Path(__file__).resolve().parents[2] / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

from apps.runbooks import models as runbook_models  # noqa: E402
from apps.runbooks import services  # noqa: E402
from apps.runbooks.engine import acts  # noqa: E402
from apps.runbooks.registry import registry  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

#: The seven tables this module owns (`17-runbooks/03-field-map.md`). Everything
#: else in the schema belongs to another module and a dry run may not touch one.
RUNBOOKS_TABLES = {
    "runbooks",
    "runbook_versions",
    "runbook_runs",
    "runbook_run_records",
    "runbook_schedules",
    "runbook_work_items",
    "runbook_cutover_plans",
}

RUNBOOK_KEY = "collections_ladder"

#: ⚠ **`audit_log` IS OUTSIDE THE SEVEN TABLES AND IS REQUIRED TO MOVE, SO
#: "ZERO OUTSIDE THE SEVEN" IS THE WRONG ASSERTION AND THE FIRST RUN SAID SO.**
#: `M2` asks for *"zero rows written outside this module's seven tables"*. Run
#: it and `audit_log` grows by 835 — correctly: `BR-RBS-022` puts the audit row
#: in the engine so that even a Check leaves a trail, and CLAUDE.md hard rule 7
#: says every money action writes one. It is the one table a runbook is
#: SUPPOSED to write outside itself.
#:
#: **A blanket exemption would be worse than the wrong assertion**, because it
#: is exactly the hole a real foreign write would hide in — so the growth is
#: asserted to the ROW: `audit_log` may move by exactly the number of acts the
#: run performed and by nothing else. A run that wrote 835 records and 1,200
#: audit rows fails here, and so does one that wrote 835 and none.
#:
#: ⚠ **AND IT IS RED UNDER `--bind-writer`, WHICH IS CORRECT AND NOT A FAULT IN
#: THE CHECK.** A bound `step_ladder` writes a queue row, a `notice_history` row
#: and a tier for each account on each channel, and payments and notifications
#: audit their own writes — measured 2026-09-07: **812 acts, +2,948 audit rows**.
#: The equality this asserts is a property of the DRY path — where no port is
#: called and the engine's row is the only one written — and its failure on a
#: live run is the second half of the red proof rather than a false alarm.
AUDIT_TABLES = {"audit_log"}

#: The monthly partitions of `audit_log` (`DB-7`/`NFR-24`). They are the same
#: rows counted twice — the parent and the partition holding them — so they are
#: measured against the same expected number rather than added to it.
AUDIT_PARTITION_PREFIX = "audit_log_"

#: The outcomes that mean `acts.perform` was CALLED, and therefore that one
#: audit row was written. A skip returns a dict and never reaches the engine, so
#: it writes neither a record row nor an audit row — which is itself worth
#: knowing and is printed below.
ACT_OUTCOMES = {"planned", "queued", "already_sent", "failed", "held", "done", "already"}


def every_table() -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        )
        return [row[0] for row in cursor.fetchall()]


def counts(tables: list[str], tenant_id) -> dict[str, int]:
    """Row counts AS THE TENANT — the only way they are real. See the docstring."""
    out: dict[str, int] = {}
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])
        for table in tables:
            cursor.execute(f'SELECT count(*) FROM "{table}"')  # noqa: S608 — names from the catalog
            out[table] = cursor.fetchone()[0]
    return out


def ensure_runbook(tenant, definition):
    """The tenant's row for this shipped template, added if `E1` has not been used.

    Exactly what `rbs_c_seed_run.py` does and for the same reason: putting a
    shipped runbook on a tenant is `POST /runbooks`, and `seed_demo` creates
    none. Nothing here invents a name, a kind or a category — every field comes
    from the shipped definition.
    """
    runbook = runbook_models.Runbook.objects.filter(tenant=tenant, key=definition.key).first()
    if runbook is not None:
        return runbook
    return runbook_models.Runbook.objects.create(
        tenant=tenant,
        key=definition.key,
        name=definition.name,
        kind=definition.kind,
        category=definition.category,
        subject_type=definition.subject_type,
        unit_of_work=definition.unit_of_work,
        tags=list(definition.tags),
        origin=runbook_models.ORIGIN_SHIPPED,
        trigger_kind=runbook_models.TRIGGER_MANUAL,
        enabled=True,
    )


def report_figures(run) -> dict[str, object]:
    """The four things a clerk reads, taken off the STORED report.

    Read back from the row rather than from the in-memory result, because
    `BR-RBS-020` freezes the report at close and the frozen copy is what
    `RBS-006` will draw. A figure taken from the result object could differ
    from the one on screen and nobody would know which was reported.
    """
    blocks = run.report or []
    out: dict[str, object] = {
        "tiles": {},
        "rungs": [],
        "records": 0,
        "outcomes": {},
        "acts": 0,
        "unreadable": 0,
    }
    for block in blocks:
        kind = block.get("block")
        payload = block.get("payload") or {}
        if kind == "kpis":
            out["tiles"] = {tile["label"]: tile["value"] for tile in payload.get("tiles", [])}
        elif kind == "breakdown":
            out["rungs"] = payload.get("rows", [])
        elif kind == "records":
            rows = payload.get("rows", [])
            out["records"] = len(rows)
            outcomes: dict[str, int] = {}
            unreadable = 0
            for row in rows:
                word = _outcome_word(row)
                if word is None:
                    unreadable += 1
                    continue
                outcomes[word] = outcomes.get(word, 0) + 1
            out["outcomes"] = outcomes
            out["unreadable"] = unreadable
            out["acts"] = sum(n for word, n in outcomes.items() if word in ACT_OUTCOMES)
    return out


def _outcome_word(row: dict) -> str | None:
    """One record row's outcome, or `None` when this file cannot find one.

    ⚠ **THE ROW SHAPE MOVED UNDER THIS CHECK AND THE FIRST VERSION READ EVERY
    OUTCOME AS THE EMPTY STRING — `DEF-RBS-4381`, found by the second cycle.**
    Wave `M`'s first cycle read `row["outcome"]`, which is what runbook 8 built
    then. `DEF-RBS-4352`'s fix made every result table conform to the
    renderer's payload contract, so a record row is now
    `{id, meta, cells: {outcome: {kind, text}}}` and the old lookup returns
    `None` for every row on every firing. The audit assertion below then
    expected **zero** audit rows against 812 real ones and called five clean
    firings a failure.
    **It failed LOUDLY, which is the only reason this was cheap** — had the
    arithmetic run the other way it would have reported a clean cycle over a
    check that could no longer see its own subject.

    So: both shapes are read, and a row matching NEITHER is counted as
    `unreadable` and printed beside the verdict rather than silently becoming
    one more empty string. A check that cannot cover its whole subject must
    print what it skipped beside what it checked (hard-won law 7).
    """
    cells = row.get("cells")
    if isinstance(cells, dict) and "outcome" in cells:
        cell = cells["outcome"]
        if isinstance(cell, dict):
            return str(cell.get("text") or "")
        return str(cell or "")
    if "outcome" in row:
        return str(row.get("outcome") or "")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument(
        "--mondays",
        required=True,
        help="comma-separated ISO business days, one per firing. Required — no clock is read.",
    )
    parser.add_argument(
        "--bind-writer",
        action="store_true",
        help="THE RED PROOF: bind the real writers so the diff must fail. Own clone only.",
    )
    parser.add_argument("--out", default="", help="write the cycle's figures to this JSON file")
    args = parser.parse_args()

    if connection.vendor != "postgresql":
        print(
            f"⛔ REFUSED: running on {connection.vendor!r}. The policies a runbook runs under do "
            "not exist on SQLite, so a green result here would mean nothing (hard-won law 7).",
            file=sys.stderr,
        )
        return 2

    tenant = tenancy_models.Tenant.objects.filter(subdomain=args.tenant).first()
    if tenant is None:
        print(f"⛔ no tenant with subdomain {args.tenant!r}", file=sys.stderr)
        return 2

    if args.bind_writer:
        # ⚠ THE SABOTAGE, AND IT IS ANNOUNCED. `LIVE_ENABLED_RUNBOOKS` is empty
        # in the product and the unsafe option is the one you type (law 3).
        acts.LIVE_ENABLED_RUNBOOKS = frozenset({RUNBOOK_KEY})
        print(
            "⚠ WRITER BOUND ON PURPOSE — mode=live AND the runbook on the allow-list. This run "
            "will queue real notices. The database diff below MUST fail on a table that is "
            "neither\n  the seven nor audit_log; if it passes, the diff is the thing that is "
            "broken.\n"
        )

    tables = every_table()
    others = [t for t in tables if t not in RUNBOOKS_TABLES]
    print(f"── {len(tables)} tables in the schema · {len(others)} outside this module")
    print(f"── tenant {tenant.subdomain} ({tenant.id})")

    definition = registry.get(RUNBOOK_KEY)
    firings: list[dict[str, object]] = []
    failures = 0

    with core_tenancy.tenant_context(tenant.id):
        runbook = ensure_runbook(tenant, definition)
        if args.bind_writer:
            # ⚠ **THE SABOTAGE HAS TO GET PAST A REAL GUARD, AND THAT GUARD IS
            # WORTH NAMING.** `services._refuse_an_untrusted_live_run`
            # (`BR-RBS-036`) refuses a live run of an Action until one clean dry
            # run has been reviewed — `runbooks.refusal.dry_run_first`. It fired
            # on the first attempt at this proof, which is the ratchet working.
            # Clearing it here is the sabotage saying out loud what it is doing;
            # the product has no route that clears it, because approving a plan
            # is `L3` and `L3` does not exist.
            runbook.trusted_version = runbook.current_version
            runbook.save(update_fields=["trusted_version"])
            # ⚠ **THE FIRST CYCLE HAD TO PATCH TWO MORE THINGS HERE AND THE
            # SECOND DOES NOT — BOTH WERE FIXED BETWEEN THEM, AND SAYING SO IS
            # THE POINT OF KEEPING THIS COMMENT.**
            #
            # `DEF-RBS-4345` — `services.run_to_completion` wrote `mode` onto
            # the run row and then called `executor.execute` WITHOUT it, so a
            # run whose `runbook_runs.mode` read `live` executed dry and bound
            # no writer. The 2026-09-06 cycle monkey-patched `build_context` to
            # force the mode; wave `N` passed the argument, so the patch is
            # GONE. **It is gone rather than made conditional on purpose**: left
            # in, it would force `live` whatever the product did, and the day
            # somebody drops the argument again this proof would still pass.
            #
            # `DEF-RBS-4343` — with `queue_notice` bound, every act came back
            # `held` because `queue_document` refuses a row that names no
            # template, so the first cycle supplied a template pin here.
            # Runbook 8 no longer holds `queue_notice`: `DEF-RBS-4347`'s ruling
            # made the act `step_ladder`, payments' own port, which calls the
            # same `notices.send_*` the manual modals call and brings its own
            # templates. **Whether that closed `DEF-RBS-4343` is a QUESTION this
            # proof answers rather than an assumption it encodes** — if the acts
            # still come back `held`, nothing is written, the diff cannot go red
            # and this script says so instead of papering over it.
            print(
                "⚠ NOTHING ELSE IS PATCHED. The 2026-09-06 proof also forced the mode "
                "(DEF-RBS-4345)\n  and supplied a template (DEF-RBS-4343); both are the "
                "product's own now, and if the\n  acts come back `held` this run will fail "
                "rather than stand one in.\n"
            )
            print(
                "⚠ the trust ratchet (BR-RBS-036) was cleared BY THIS SCRIPT to reach the live "
                "path. Nothing in the product can do that today.\n"
            )

    for index, raw in enumerate(args.mondays.split(","), start=1):
        as_of = dt.date.fromisoformat(raw.strip())
        before = counts(tables, tenant.id)
        started = time.monotonic()
        with core_tenancy.tenant_context(tenant.id):
            run, _result = services.run_to_completion(
                runbook,
                definition,
                # ⚠ `MODE_LIVE` ONLY UNDER `--bind-writer`, AND THAT IS WHAT
                # MAKES THE RED PROOF REAL. `build_context` reads
                # `if mode != "live" or not acts.live_enabled(key)` — so the
                # FIRST version of this sabotage put the key in the allow-list
                # and left the mode at dry, every port stayed unbound, and the
                # diff went red on the AUDIT row instead of on a foreign write.
                # It looked like a pass of the red proof and was not one: the
                # check had never been shown to catch the thing it exists for.
                mode=(runbook_models.MODE_LIVE if args.bind_writer else runbook_models.MODE_DRY),
                trigger=runbook_models.TRIGGER_MANUAL,
                params={"as_of": as_of.isoformat()},
            )
        took = time.monotonic() - started

        # ⚠ **THE RUN'S CLOCK IS MOVED TO ITS BUSINESS DAY, AND WITHOUT THIS THE
        # CYCLE MEASURES THE WRONG THING.** `duplicates.check` looks for an
        # earlier run of this job `started_at >= now - frequency_hours`, and
        # `now` is the run row's REAL timestamp — correctly, it is a fact about
        # the pass and not about the business day. Five Mondays replayed in one
        # afternoon all fall inside one 24-hour window, so firings 2-5 of the
        # first cycle came back `already_sent` for every account **without ever
        # reaching the per-record key**: no record row and no audit row either,
        # and the run-level check took the credit for the per-record one.
        # A month cannot be soaked in elapsed time, so the run history is made
        # to look like what it would be if the firings really had been a week
        # apart. This is the ONLY thing in this script that writes a product
        # row, and it is announced rather than quiet.
        # ⚠ The business days must therefore be in the PAST: a Monday later than
        # the machine's own clock lands the backdated run INSIDE the next
        # firing's window and the artefact comes straight back.
        with core_tenancy.tenant_context(tenant.id):
            stamp = dt.datetime.combine(as_of, dt.time(7, 0), tzinfo=dt.timezone.utc)
            runbook_models.RunbookRun.objects.filter(pk=run.pk).update(
                started_at=stamp, finished_at=stamp + dt.timedelta(seconds=int(took) or 1)
            )

        after = counts(tables, tenant.id)

        moved_all = {t: (before[t], after[t]) for t in others if before[t] != after[t]}
        moved_inside = {
            t: (before[t], after[t]) for t in RUNBOOKS_TABLES if before.get(t) != after.get(t)
        }
        populated = sum(1 for t in others if before[t] > 0)

        with core_tenancy.tenant_context(tenant.id):
            run.refresh_from_db()
            figures = report_figures(run)
            record_rows = runbook_models.RunbookRunRecord.objects.filter(run_id=run.pk).count()

        # ── the audit half, asserted to the row rather than exempted ────────
        expected_audit = int(figures["acts"] or 0)
        # ⚠ **MEASURED OVER THE AUDIT TABLES THEMSELVES, NOT OVER THE ONES THAT
        # MOVED — AND THE FIRST VERSION DID THE SECOND.** Built from the tables
        # that moved, a firing that wrote NO audit row at all produced an empty
        # mapping, the comparison had nothing to iterate, and the check passed.
        # It did exactly that on firings 2-5 of the first cycle: 835 acts, zero
        # audit rows, verdict "clean". That is hard-won law 7's *reporting zero
        # over a scope it silently excludes*, in the check written to obey law 7,
        # and it was found by reading the output rather than the exit code.
        #
        # ⚠ **THE PARENT IS ASSERTED, THE PARTITIONS ARE ASSERTED AS A SUM.**
        # `audit_log` is partitioned monthly (`DB-7`/`NFR-24`), so a write lands
        # in the parent AND in exactly one child. Comparing every child against
        # the expected number — which the second version did — fails four empty
        # months on a perfectly clean firing. They are the same rows counted
        # twice.
        audit_moves = {t: (before[t], after[t]) for t in others if t in AUDIT_TABLES}
        partitions = {
            t: (before[t], after[t]) for t in others if t.startswith(AUDIT_PARTITION_PREFIX)
        }
        audit_wrong = {
            t: (was, now, now - was)
            for t, (was, now) in audit_moves.items()
            if now - was != expected_audit
        }
        partition_total = sum(now - was for was, now in partitions.values())
        if partition_total != expected_audit:
            audit_wrong["(all audit_log partitions)"] = (0, partition_total, partition_total)
        moved_outside = {
            t: v
            for t, v in moved_all.items()
            if t not in AUDIT_TABLES and not t.startswith(AUDIT_PARTITION_PREFIX)
        }

        print(f"\n══ firing {index} · {as_of} · run {run.pk} · {run.status} · {took:.1f}s")
        print(f"   counts      : {json.dumps(run.counts or {}, sort_keys=True)}")
        print(f"   tiles       : {json.dumps(figures['tiles'], sort_keys=True)}")
        print(f"   outcomes    : {json.dumps(figures['outcomes'], sort_keys=True)}")
        print(f"   by rung     : {json.dumps(figures['rungs'], sort_keys=True)}")
        print(f"   record rows written by THIS run: {record_rows}")
        print(f"   report rows whose outcome this check could not read: {figures['unreadable']}")
        print(f"   runbooks tables that moved : {sorted(moved_inside)}")
        print(f"   audit rows (expected {expected_audit}) : "
              f"{ {t: v[1] - v[0] for t, v in audit_moves.items()} }")
        print(f"   other tables that moved    : {sorted(moved_outside)}")
        print(f"   other tables with any rows : {populated} of {len(others)}")

        verdict = "clean"
        if figures["unreadable"]:
            # ⚠ Not a finding about the RUN — a finding about this CHECK. An
            # outcome word it cannot read is an act it cannot count, so the
            # audit assertion below would be comparing against a number built
            # from a partial view. Fail rather than report over it.
            verdict = "THIS CHECK COULD NOT READ THE RECORD ROWS"
            failures += 1
            print(
                f"\n   ⛔ {figures['unreadable']} of {figures['records']} record rows carry no "
                "outcome this\n      script knows how to read, so the number of acts below is "
                "not the run's.\n      The report's row shape has moved (see `_outcome_word`).",
                file=sys.stderr,
            )
        if audit_wrong:
            verdict = "THE AUDIT TRAIL DOES NOT MATCH THE ACTS"
            failures += 1
            print(
                "\n   ⛔ hard rule 7 — every money action writes `audit_log`, and `BR-RBS-022` "
                "puts\n      that row in the engine so a dry act leaves a trail too. These "
                "counts do not\n      agree with the number of acts this run performed:",
                file=sys.stderr,
            )
            for table, (was, now, delta) in sorted(audit_wrong.items()):
                print(f"      · {table}: {was} → {now} (+{delta}, expected +{expected_audit})",
                      file=sys.stderr)
        if moved_outside:
            verdict = "WROTE OUTSIDE THE SEVEN TABLES"
            failures += 1
            print(
                "\n   ⛔ THIS RUN WROTE OUTSIDE ITS MODULE. `BR-RBS-002`/`BR-RBS-003`: a dry "
                "run\n      reaches writer-less ports, so a row anywhere else is a port that "
                "was bound\n      when it should not have been.",
                file=sys.stderr,
            )
            for table, (was, now) in sorted(moved_outside.items()):
                print(f"      · {table}: {was} → {now}", file=sys.stderr)
        elif int(figures["records"] or 0) == 0:
            # A run over nothing writes nothing, truthfully and vacuously.
            verdict = "RESOLVED NOTHING — the diff proves nothing about this firing"
            failures += 1
            print(
                "\n   ⛔ THIS FIRING PLANNED NO RECORDS AT ALL. Zero rows outside the seven "
                "tables\n      is then true of an empty run rather than of a safe one, and "
                "nothing is\n      concluded from it (hard-won law 7 — a zero over a scope that "
                "excludes\n      everything).",
                file=sys.stderr,
            )
        elif populated < 10:
            verdict = "clean, but the database is too thin to conclude from"

        print(f"   verdict     : {verdict}")
        firings.append(
            {
                "firing": index,
                "as_of": as_of.isoformat(),
                "run_id": str(run.pk),
                "status": run.status,
                "seconds": round(took, 2),
                "counts": run.counts or {},
                "tiles": figures["tiles"],
                "rungs": figures["rungs"],
                "records_in_report": figures["records"],
                "record_rows_this_run": record_rows,
                "moved_outside": {k: list(v) for k, v in moved_outside.items()},
                "audit_moves": {k: list(v) for k, v in audit_moves.items()},
                "acts": expected_audit,
                "outcomes": figures["outcomes"],
                "moved_inside": {k: list(v) for k, v in moved_inside.items()},
                "verdict": verdict,
            }
        )

    print("\n" + "═" * 72)
    if args.bind_writer:
        if failures:
            print("✓ RED AS INTENDED — the diff caught a bound writer. Now run it unbound.")
            outcome = 0
        elif not any(int(f["acts"] or 0) for f in firings):
            # ⚠ **TWO DIFFERENT FAILURES USED TO PRINT ONE SENTENCE, AND THE
            # WRONG ONE.** A bound-writer run that writes nothing can mean the
            # diff is blind — the thing this proof exists to catch — or it can
            # mean the PRODUCT correctly refused every act, which is what
            # happens when the same business day is fired twice and payments
            # answers `already_noticed_today` 720 times. Reporting the first
            # sentence over the second tells a reader the check is broken when
            # the check has simply been given nothing to see (hard-won law 7,
            # habit 3: the output must distinguish pass from fail to a READER).
            print(
                "⛔ THE RED PROOF PROVED NOTHING: the writer was bound and the runbook "
                "performed ZERO acts,\n   so there was no foreign write for the diff to "
                "catch. That is the PRODUCT refusing, not\n   the diff failing — fire a "
                "business day whose acts are actually due.",
                file=sys.stderr,
            )
            outcome = 1
        else:
            print(
                "⛔ THE RED PROOF DID NOT GO RED. A writer was bound, the runbook performed "
                "acts, and the\n   diff still passed — so the diff cannot see the thing it "
                "exists to see.",
                file=sys.stderr,
            )
            outcome = 1
    else:
        print(
            f"{len(firings)} firings · {failures} failed. "
            + ("✓ nothing outside the seven runbooks tables changed" if not failures else "")
        )
        outcome = 1 if failures else 0

    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(firings, indent=2, default=str))
        print(f"── figures written to {args.out}")
    return outcome


if __name__ == "__main__":
    raise SystemExit(main())
