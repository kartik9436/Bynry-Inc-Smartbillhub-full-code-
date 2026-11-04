#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: the CR-023 import runner's PAYMENTS target (`P1.1`, the eighth),
#            timed against the wall a request actually has to clear —
#            gunicorn's `--timeout 60` (06-backend/docker-entrypoint.sh).
# Defect:   DEF-PAY-6203 — the per-target load bar guard
#           (`tests/test_def2487_accounts_async_bar.py`) measures the ACCOUNTS
#           bar and nothing else, so seven targets carry a bar with no figure
#           behind it and the check reports PASS over all of them.
# Rules:    BR-MET-096 (ONE runner, a target is a parameter) · DEF-2487 (a bar
#           without a measured per-row cost is the defect) · CLAUDE.md hard-won
#           law 7 (a check that cannot cover its whole subject prints what it
#           skipped beside what it checked) · CLAUDE.md hard rule 1 (tenant
#           scoping — `app.tenant_id` BEFORE anything is counted).
# ───────────────────────────────────────────────────────
"""How long does a PAYMENTS import take per row, and is the bar of 200 safe?

`10-scripts/def2487_accounts_bar_benchmark.py` measured the ACCOUNTS target and
its bar of 100 was set from that figure. **`payments` has no figure at all.** It
inherits `ASYNC_ROW_BAR_BY_STAGE["load"] = 200` — the per-stage default — and
nothing in the repository has ever timed it.

That matters because a payments row is not a premises row. Each one walks the
match ladder against the account index, creates a payment through payments' own
writer, and writes an audit row — which is much closer in shape to an ACCOUNTS
row (94 ms, bar 100) than to a premises row (2.03 ms, bar 500). If a payments
row costs what an accounts row costs, 200 of them is 18.8 s, and the bar would
be sitting on the edge of the third of the request DEF-2487 requires.

**This script answers that with a number instead of an argument.**

IT WRITES NOTHING. Every run happens inside one transaction that is rolled back,
so it may be pointed at a dev database as often as it is useful — the same
posture, and for the same reason, as the two benchmarks it is modelled on.

⚠ **IT TIMES THE WORKER'S BODY, NOT THE QUEUE.** Above the bar `load()` enqueues
and answers 202, so timing it would measure a dispatch. `_load_apply` under
`_JobActor` is what the worker actually calls, and it is what `P1.11`'s proof
drives for the same reason.

USAGE
    10-scripts/proof-db.sh clone paybar
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_paybar \\
    python3 10-scripts/pay_p1_1_load_bar_benchmark.py --rows 50 100 200
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault(
    "DATABASE_URL", "postgres://smartbillhub:smartbillhub@127.0.0.1:5432/smartbillhub"
)
# A worker would measure a queue rather than the engine; this times the BODY.
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.db import connection, transaction  # noqa: E402

from apps.metering import import_progress, import_runs  # noqa: E402
from core import permissions, tenancy as core_tenancy  # noqa: E402


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def _tenant_and_account() -> tuple[str, str]:
    """One tenant and one real account, with `app.tenant_id` SET.

    ⚠ **THE SCOPING COMES FIRST AND EVERYTHING AFTER IT IS READ INSIDE IT.**
    RLS `FORCE` is on, so an account read without it comes back empty and this
    script would then time a file naming an account that does not exist — every
    row rejected, a very fast load, and a figure that means nothing. Five lanes
    have nearly reported a false zero this way; the count below is what makes
    the scoping VISIBLE rather than assumed.
    """
    with connection.cursor() as cur:
        cur.execute("SELECT id FROM tenants ORDER BY created_at LIMIT 1")
        row = cur.fetchone()
    if row is None:
        _fail("this database has no tenants — clone a SEEDED template")
    tenant_id = str(row[0])
    core_tenancy.set_current_tenant(tenant_id)
    with connection.cursor() as cur:
        cur.execute("SET app.tenant_id = %s", [tenant_id])
        cur.execute(
            "SELECT count(*) FROM accounts WHERE account_no IS NOT NULL"
        )
        visible = int(cur.fetchone()[0])
        cur.execute(
            "SELECT account_no FROM accounts WHERE account_no IS NOT NULL "
            "ORDER BY created_at LIMIT 1"
        )
        found = cur.fetchone()
    if found is None or not visible:
        _fail("this tenant has no accounts — RLS is on; did app.tenant_id get set?")
    print(f"tenant {tenant_id}: {visible} accounts visible (not a false zero)")
    return tenant_id, str(found[0])


class _Actor:
    """The minimum `import_runs` asks of an actor, for stages 1-3.

    ⚠ **STAGES 1-3 ARE ROLE-GATED AND THE LOAD IS NOT.** `extract` refuses an
    actor with no role (AUTH-002), so this one carries `SYSTEM_ADMIN` — the
    CONSTANT, never a hand-spelled string, because a role typed by hand is a
    403 that reads like a broken script. The LOAD below is driven by
    `_JobActor` instead, which is an id and no role (`DEF-1108`) and is what
    the worker really uses; timing it through a privileged actor would time a
    path production never takes.
    """

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        self.id = None
        self.role = permissions.SYSTEM_ADMIN
        self.is_authenticated = True


def _time_one(tenant_id: str, account_no: str, rows: int) -> dict[str, float]:
    """Stage a file of `rows` payments and time each stage. Rolls back."""
    nonce = uuid.uuid4().hex[:8]
    header = "Account,Amount,Date,Check no,Payer,Memo\n"
    body = header + "".join(
        f"{account_no},{10 + (n % 90)}.{n % 100:02d},2026-08-20,"
        f"CHK-{nonce}-{n:05d},,bar bench row {n}\n"
        for n in range(1, rows + 1)
    )
    actor = _Actor(tenant_id)
    timings: dict[str, float] = {}

    t0 = time.perf_counter()
    staged = import_runs.extract(
        actor,
        {
            "target": import_runs.TARGET_PAYMENTS,
            "source_kind": "file",
            "file_name": f"paybar-{nonce}.csv",
            "content": body,
        },
    )
    timings["extract"] = time.perf_counter() - t0
    run_id = staged["id"]

    mapping = {
        "Account": {"target": "account_ref"},
        "Amount": {"target": "amount"},
        "Date": {"target": "paid_on"},
        "Check no": {"target": "reference"},
        "Payer": {"target": "payer_name"},
        "Memo": {"target": "memo"},
    }
    t0 = time.perf_counter()
    import_runs.transform(actor, run_id, {"mapping": mapping})
    timings["transform"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    validated = import_runs.validate(actor, run_id, write_mode="insert")
    timings["validate"] = time.perf_counter() - t0

    # ⚠ The load is the only stage whose cost DEF-2487 was about, and it is the
    # only one taken through the worker's own entry point.
    t0 = time.perf_counter()
    receipt = import_runs._load_apply(
        import_runs._JobActor(getattr(actor, "id", None)),
        run_id,
        "insert",
        {"write_mode": "insert"},
        import_progress.NULL,
    )
    timings["load"] = time.perf_counter() - t0
    counts = (receipt or {}).get("counts", {}) or {}
    # ⚠ **THE FIRST THING TO ASSERT IS THAT ROWS WERE ACTUALLY WRITTEN.**
    # A load that rejects every row is fast and means nothing; quoting its
    # ms/row as a WRITE cost is law 7's *looking at the wrong thing*, and the
    # receipt key is `created`, never `loaded`.
    timings["_created"] = float(counts.get("created") or 0)
    timings["_counts"] = counts
    timings["_validated"] = validated.get("counts", {}) or {}
    return timings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, nargs="+", default=[50, 100, 200])
    parser.add_argument(
        "--prove-red",
        action="store_true",
        help=(
            "Name an account this utility does NOT have, so every row is refused "
            "at the write. The run must then REFUSE rather than quote a figure — "
            "CLAUDE.md hard-won law 7, and the reason this flag is committed "
            "rather than being a temporary edit somebody made once."
        ),
    )
    args = parser.parse_args()

    tenant_id, account_no = _tenant_and_account()
    if args.prove_red:
        # ⚠ Every row now names an account that is not on file, so the writer
        # refuses all of them and `created` is 0. A benchmark that went on to
        # print "0.4 ms/row" here would be timing REJECTION and calling it a
        # write cost — which is exactly the false pass this guard exists for.
        account_no = "AC-NOT-A-REAL-ONE"
        print("--prove-red: every row names an account that is not on file")
    bar = import_runs.async_row_bar(import_runs.TARGET_PAYMENTS, "load")
    timeout = import_runs.WEB_WORKER_TIMEOUT_SECONDS
    print(f"payments load bar: {bar} rows · web worker timeout: {timeout}s")
    print(f"the bar has to fit inside {timeout / 3:.1f}s (a third of the request)\n")

    print(f"{'rows':>6} {'extract':>9} {'transform':>10} {'validate':>9} "
          f"{'load':>9} {'ms/row':>8} {'loaded':>7}")
    results: list[tuple[int, float]] = []
    for rows in args.rows:
        # ⚠ ONE transaction per size, rolled back — nothing is kept.
        try:
            with transaction.atomic():
                t = _time_one(tenant_id, account_no, rows)
                raise _Rollback(t)
        except _Rollback as done:
            t = done.timings
        except Exception as refused:  # noqa: BLE001
            # ⚠ **A REFUSAL IS THE RIGHT ANSWER, NOT A CRASH.** In `--prove-red`
            # every row names an account that is not on file, and the runner
            # stops the run at stage 3 with `metering.import.approval_required`
            # BEFORE the load — so the guard below is never even reached. Both
            # outcomes are the same property: **no figure is printed over rows
            # that were not written.** That is what this flag proves.
            if args.prove_red:
                print(f"\n  REFUSED: {type(refused).__name__}: {refused}")
                print("  PROVED RED: no ms/row figure was quoted over an "
                      "unwritten row.")
                return 1
            raise
        created = int(t["_created"])
        if created != rows:
            print(f"\n  counts: {t['_counts']}")
            print(f"  validated: {t['_validated']}")
            _fail(f"{created} of {rows} rows were CREATED — this is not a write cost")
        ms_per_row = t["load"] * 1000 / rows
        results.append((rows, ms_per_row))
        print(f"{rows:>6} {t['extract']:>8.2f}s {t['transform']:>9.2f}s "
              f"{t['validate']:>8.2f}s {t['load']:>8.2f}s {ms_per_row:>7.1f} "
              f"{int(t['_created']):>7}")

    worst = max(ms for _, ms in results)
    at_the_bar = bar * worst / 1000
    allowed = timeout / 3
    print(f"\nworst measured cost: {worst:.1f} ms/row")
    print(f"a file AT the bar ({bar} rows) would take {at_the_bar:.1f}s")
    print(f"the third of the request it is allowed: {allowed:.1f}s")
    if at_the_bar > allowed:
        print(f"\nVERDICT: the bar of {bar} is TOO HIGH — that is DEF-2487's arithmetic.")
        return 1
    print(f"\nVERDICT: the bar of {bar} is SAFE, with "
          f"{allowed / at_the_bar:.1f}x margin inside the third.")
    return 0


class _Rollback(Exception):
    """Carries the timings out of the transaction that is being abandoned."""

    def __init__(self, timings: dict[str, float]) -> None:
        super().__init__("rollback")
        self.timings = timings


if __name__ == "__main__":
    raise SystemExit(main())
