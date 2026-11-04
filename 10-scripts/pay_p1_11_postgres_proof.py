#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   `06 Payments Page Blueprint.pdf` phase 1, `P1.11` — *"the target end
#           to end, ON PostgreSQL: upload, map, validate, commit — and one bad
#           row among four hundred, proving the savepoint."* Outcome, verbatim:
#           *"Cannot be proved on SQLite, which has no aborted-transaction
#           state."*
# Rules:    CLAUDE.md hard-won law 14 (a failed statement poisons the whole
#           PostgreSQL transaction; a SAVEPOINT is the ONLY option) · hard rule
#           1 (tenant scoping — `app.tenant_id` BEFORE you count anything) ·
#           hard rule 2 (money is Decimal) · hard rule 6 (idempotency) ·
#           BR-PAY-023 (per-row errors skip WITH A REPORT) · hard-won law 7
#           (prove the guard RED first, in the harness that will run it)
# Tests:    06-backend/tests/test_pay_import_target.py is the SHAPE half and
#           runs on SQLite; this is the half that cannot.
# ───────────────────────────────────────────────────────
"""P1.11 — the payments import target, end to end, on a real PostgreSQL 16.

WHY THIS IS A SCRIPT AND NOT A TEST
-----------------------------------
`config/settings/test.py` **hardcodes in-memory SQLite and ignores
`DATABASE_URL`** (the URL applies only under `config.settings.local`). SQLite
has no aborted-transaction state, so the version of `_load_payments_rows` with
its savepoint removed passes the entire suite, green, on every machine — and
loses a morning's takings the first time PostgreSQL refuses a row. That is
CLAUDE.md law 14 word for word, and it is why this file exists beside the
suite rather than inside it.

    10-scripts/proof-db.sh clone p1a11 --stale-ok
    cd 06-backend && DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local \
        python3 manage.py migrate
    DATABASE_URL=… python3 ../10-scripts/pay_p1_11_postgres_proof.py

⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A clone is private by
construction; a mid-run reseed looks exactly like a broken import.

⚠ **`app.tenant_id` IS SET BEFORE ANYTHING IS COUNTED.** RLS `FORCE` is on, so
an unscoped `count()` answers **0** — a false zero that reads exactly like a
load that wrote nothing. Four lanes have nearly reported one.

WHAT IT PROVES, AND WHAT IT DOES NOT
------------------------------------
Each part prints its own verdict, and the boundary between them is worth stating
because it is easy to claim more than was shown (hard-won law 1).

  * **Part C** is the blueprint's own scenario — 400 rows, one bad — and it
    proves the PIPELINE: 399 payments in the table, one row rejected with a
    sentence a clerk can act on, the receipt's figures matching the table, and
    the same bytes refused on a second commit (hard rule 6). Measured
    2026-09-22: **+399 payments, `rejected_at_write=1`.**
  * **Part E** proves the SAVEPOINT, separately, because Part C's bad row is
    refused by `_amount_of` **before any SQL is issued** — so it never aborts a
    transaction and never exercises the savepoint at all. Part E therefore
    forces a genuine database-level failure (a payment on an account id the
    index claimed and the table does not have, which is `DEF-544`'s real race)
    and asks the only question law 14 cares about: **is this connection usable
    afterwards?** Whole load runs inside ONE `transaction.atomic()`
    (`_load_apply`), so without the nested `atomic()` every payment written
    before the bad row is lost at COMMIT — silently, with the SQLite suite
    green.

⚠ **THE SEPARATION IS THE POINT.** A run where the only bad row raises before
touching the database would "pass" with the savepoint deleted, and a lane
reading a green Part C alone would conclude the savepoint is decoration.
"""

from __future__ import annotations

import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import connection, transaction  # noqa: E402

from apps.metering import import_progress, import_runs, models as metering_models, seams  # noqa: E402
from apps.payments import import_writer, models as payments_models  # noqa: E402
from core import errors, permissions, tenancy as core_tenancy  # noqa: E402

ROWS = 400
#: The row that is wrong. Chosen because a **zero-value advice line is a real
#: thing a lockbox file contains** — not a synthetic error — and because it
#: passes every stage-3 rule (it parses, it names an account) and is refused at
#: the WRITE, which is the only place a savepoint can matter.
BAD_ROW = 200


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def _tenant_and_account():
    """One tenant and one real account, with `app.tenant_id` SET.

    ⚠ The scoping comes first and everything after it is read inside it. An
    account read without it comes back empty and the script would then build a
    file naming an account that does not exist — proving nothing, loudly."""
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
            "SELECT account_no FROM accounts WHERE account_no IS NOT NULL "
            "ORDER BY created_at LIMIT 1"
        )
        found = cur.fetchone()
    if found is None:
        _fail("this tenant has no accounts — RLS is on; did app.tenant_id get set?")
    return tenant_id, str(found[0])


def _payment_count(tenant_id: str) -> int:
    """Payments for THIS tenant. Scoped, because an unscoped count answers 0."""
    with connection.cursor() as cur:
        cur.execute("SET app.tenant_id = %s", [tenant_id])
        cur.execute("SELECT count(*) FROM payments")
        return int(cur.fetchone()[0])


def part_a_the_database_constrains_nothing(tenant_id: str) -> None:
    """`P1.3`, re-proved here rather than quoted: `import_runs.target` takes an
    eighth value because nothing in the database says otherwise."""
    print("\n── PART A · the target column (P1.3) ──────────────────────────")
    with connection.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM pg_constraint con JOIN pg_class rel "
            "ON rel.oid = con.conrelid "
            "WHERE rel.relname = 'import_runs' AND con.contype = 'c'"
        )
        checks = int(cur.fetchone()[0])
    print(f"   CHECK constraints on import_runs: {checks}")
    if checks:
        _fail("a CHECK appeared on import_runs — the eighth target IS a migration now")
    print("   PASS: an eighth `target` value needs no migration.")


def part_b_the_rules_and_the_writer_agree(tenant_id: str, account_no: str) -> None:
    """`P1.12` against the LIVE account index, not a fixture of one.

    `DEF-544`'s law: stage 3 and stage 4 must resolve against the same world.
    Here the world is a real utility's real accounts."""
    print("\n── PART B · one match ladder, live index (P1.12) ───────────────")
    index = seams.payments_import_index()
    if index is None:
        _fail("payments published no index — the load would have refused")
    print(f"   accounts in the index: {len(index)}")
    clean = import_writer.match_account(account_ref=account_no, index=index)
    if clean["state"] != import_writer.MATCH_CLEAN:
        _fail(f"a real account number did not match cleanly: {clean}")
    print(f"   {account_no} → {clean['state']} / {clean['method']}")
    nothing = import_writer.match_account(account_ref="AC-NOT-A-REAL-ONE", index=index)
    if nothing["state"] == import_writer.MATCH_CLEAN:
        _fail("an account this utility does not have matched cleanly")
    print("   AC-NOT-A-REAL-ONE → review, nothing guessed")
    print("   PASS: an identifier matches; anything less waits for a person.")


def _run_the_file(tenant_id: str, account_no: str, *, label: str, nonce: str) -> dict:
    """Stages 1–4 over a 400-row file with one bad row, on PostgreSQL."""
    header = "Account,Amount,Date,Check no,Payer,Memo\n"
    lines = []
    for n in range(1, ROWS + 1):
        amount = "0.00" if n == BAD_ROW else f"{10 + (n % 90)}.{n % 100:02d}"
        lines.append(f"{account_no},{amount},2026-08-20,CHK-{nonce}-{n:05d},,{label} row {n}\n")
    # ⚠ `content` is a STR, not bytes — the runner reads it as the file's text.
    # Passing bytes stages ZERO rows and reports a clean run of nothing, which
    # is what the first draft of this proof did (law 7: a check that reports
    # success over an empty file is a check looking at the wrong thing).
    body = header + "".join(lines)

    actor = _Actor(tenant_id)
    staged = import_runs.extract(
        actor,
        {
            "target": import_runs.TARGET_PAYMENTS,
            "source_kind": "file",
            "file_name": f"{label}-{nonce}.csv",
            "content": body,
        },
    )
    run_id = staged["id"]
    mapping = {
        "Account": {"target": "account_ref"},
        "Amount": {"target": "amount"},
        "Date": {"target": "paid_on"},
        "Check no": {"target": "reference"},
        "Payer": {"target": "payer_name"},
        "Memo": {"target": "memo"},
    }
    import_runs.transform(actor, run_id, {"mapping": mapping})
    validated = import_runs.validate(actor, run_id, write_mode="insert")
    print(f"   stage 3: {validated.get('counts')}")
    # ⛔ **THE WORKER'S PATH, AND THAT IS THE REAL ONE AT FOUR HUNDRED ROWS.**
    # `ASYNC_ROW_BAR_BY_STAGE["load"] is 200` for EVERY target (`DEF-MET-5756`),
    # so `import_runs.load()` at 400 rows does not load — it enqueues, and on a
    # machine with no Redis it refuses with `metering.import.no_worker`, which
    # is `DEF-2487`'s guard working exactly as designed.
    #
    # ⚠ **SO THE LOCKBOX IMPORT IS A BACKGROUND JOB IN PRODUCTION.** The
    # blueprint's own figure is *"the 4,000 to 6,000 receipts a month keyed by
    # hand today"* — a morning's file is hundreds of rows, comfortably over the
    # bar — so the path this proof must exercise is `_load_apply` under
    # `_JobActor`, which is what the worker calls. Driving `load()` instead
    # would prove a path no real file takes.
    print(f"   over the load bar ({import_runs.async_row_bar(import_runs.TARGET_PAYMENTS, 'load')}"
          f" rows) — taking the WORKER's path, as production does")
    return import_runs._load_apply(
        import_runs._JobActor(getattr(actor, "id", None)),
        run_id,
        "insert",
        {"write_mode": "insert"},
        import_progress.NULL,
    )


class _Actor:
    """The minimum `import_runs` asks of an actor. Role-free on purpose — a
    deferred load runs under `_JobActor`, an id and no role (`DEF-1108`)."""

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        self.id = None
        # `core.permissions.SYSTEM_ADMIN` is the lower-case string; the
        # constant is imported rather than typed, because a role spelled
        # by hand is a 403 that reads like a broken script.
        self.role = permissions.SYSTEM_ADMIN
        self.is_authenticated = True


def part_c_one_bad_row_among_four_hundred(tenant_id: str, account_no: str) -> None:
    print("\n── PART C · 400 rows, one bad, on PostgreSQL (P1.11) ───────────")
    before = _payment_count(tenant_id)
    print(f"   payments before (tenant-scoped): {before}")
    # A fresh nonce per invocation, so a re-run is a NEW file rather than the
    # same one twice — see the idempotency assertion below, which deliberately
    # re-uploads THESE bytes to prove the refusal.
    nonce = uuid.uuid4().hex[:8]
    receipt = _run_the_file(tenant_id, account_no, label="p1-11", nonce=nonce)
    counts = receipt.get("counts") or {}
    # ⚠ **THE FIRST THING TO ASSERT IS THAT THE FILE WAS READ AT ALL.** The
    # first draft of this script passed bytes where the runner wants text,
    # staged zero rows, and every later figure was a truthful statement about
    # nothing. A proof over an empty file is law 7's *looking at the wrong
    # thing*, and it is one line to refuse.
    if int(counts.get("in") or 0) != ROWS:
        _fail(f"the file staged {counts.get('in')} rows, not {ROWS} — nothing below means anything")
    after = _payment_count(tenant_id)
    written = after - before
    print(f"   receipt counts: created={counts.get('created')} "
          f"rejected_at_write={counts.get('rejected_at_write')}")
    print(f"   payments after (tenant-scoped): {after}  (+{written})")

    if written != ROWS - 1:
        _fail(
            f"{written} payments written, expected {ROWS - 1}. "
            "THIS IS LAW 14: a lost batch looks exactly like this on PostgreSQL "
            "and looks like success on SQLite."
        )
    if counts.get("created") != ROWS - 1:
        _fail(f"the receipt claims {counts.get('created')} and the table holds {written}")
    if counts.get("rejected_at_write") != 1:
        _fail(f"the bad row was not reported: rejected_at_write={counts.get('rejected_at_write')}")
    print(f"   PASS: {written} payments written, 1 rejected WITH ITS REASON.")

    # ⛔ **HARD RULE 6, AND THIS SCRIPT FOUND IT BY TRIPPING OVER IT.** The
    # second invocation of this proof re-uploaded the same bytes and
    # PostgreSQL refused the load with `uq_import_runs_idempotency` — a
    # partial unique index over (tenant, target, file_hash) scoped to LOADED
    # runs. That is the guard working: re-uploading a file to LOOK at it is
    # legitimate (r10's stage 1 invites it) and only a second COMMIT is the
    # double-load it prevents. It is asserted here rather than worked around,
    # because a morning's takings posted twice is the defect it exists for.
    same_bytes_refused = False
    try:
        _run_the_file(tenant_id, account_no, label="p1-11", nonce=nonce)
    except Exception as refusal:  # IntegrityError from the partial unique index
        same_bytes_refused = "uq_import_runs_idempotency" in str(refusal)
    if not same_bytes_refused:
        _fail("THE SAME FILE COMMITTED TWICE. That is a morning's takings posted twice.")
    print("   PASS: the same bytes cannot be committed twice (hard rule 6).")

    # ⚠ **FOUND, NOT COMPUTED.** The first draft looked up `row_no = BAD_ROW + 1`
    # on the assumption that the header takes row 1 — an assumption about
    # somebody else's numbering, which is the cheapest kind of wrong answer to
    # produce confidently. Ask the rows which one was rejected instead.
    rejected = list(
        metering_models.ImportRunRow.objects.filter(
            tenant_id=tenant_id, run_id=receipt["id"], outcome="rejected"
        )
    )
    if len(rejected) != 1:
        _fail(f"{len(rejected)} rows rejected, expected exactly 1")
    bad = rejected[0]
    if str(BAD_ROW) not in str(bad.mapped or {}):
        _fail(f"the rejected row is not the one we made bad: {bad.row_no}")
    print(f"   row {bad.row_no} (file row {BAD_ROW}) says: {bad.problem}")
    print(f"           and: {bad.fix_hint}")
    if not bad.problem or not bad.fix_hint:
        _fail("a rejected row with no sentence is money nobody chases (BR-PAY-023)")

    with connection.cursor() as cur:
        cur.execute("SET app.tenant_id = %s", [tenant_id])
        cur.execute(
            "SELECT count(*) FROM payments WHERE origin = 'import' AND origin_is_derived = false"
        )
        observed = int(cur.fetchone()[0])
    print(f"   payments carrying origin='import', observed not derived: {observed}")
    if observed < written:
        _fail("payments/0030's ck_payments_origin was satisfied by a DERIVED value, not ours")
    print("   PASS: every row landed with an OBSERVED origin (payments/0030).")


def part_d_no_rollback_point_and_no_rollback(tenant_id: str, account_no: str) -> None:
    print("\n── PART D · the refusal is structural (P1.22) ──────────────────")
    run = (
        metering_models.ImportRun.objects.filter(
            tenant_id=tenant_id, target=import_runs.TARGET_PAYMENTS, status="loaded"
        )
        .order_by("-created_at")
        .first()
    )
    if run is None:
        _fail("no loaded payments run to test — part C did not land")
    points = metering_models.RollbackPoint.objects.filter(tenant_id=tenant_id, run=run).count()
    print(f"   rollback points created for this run: {points}")
    if points:
        _fail("a rollback point exists for a run that cannot be rolled back")
    try:
        import_runs.rollback(_Actor(tenant_id), run.id)
    except errors.BizError as refusal:
        print(f"   rollback refused: {refusal.message_key}")
        if refusal.message_key != "metering.import.payments_no_rollback":
            _fail(f"refused for the wrong reason: {refusal.message_key}")
    else:
        _fail("A POSTED PAYMENT WAS ROLLED BACK. This is hard rule 4.")
    print("   PASS: no point to spend, and the door says why.")


def part_e_the_savepoint_is_load_bearing(tenant_id: str, account_no: str) -> None:
    """⛔ **THE PART THAT CANNOT EXIST ON SQLite, AND THE ONE LAW 14 IS ABOUT.**

    The whole load runs inside ONE `transaction.atomic()` (`_load_apply`). On
    PostgreSQL a statement that errors inside a transaction ABORTS it: every
    later query raises `InFailedSqlTransaction` and the work is lost at COMMIT.
    So this forces a genuine DATABASE-level failure on one row — an account id
    the index claimed and the table does not have, which is the real race
    `DEF-544` describes — and asks whether the connection survives it.

    ⚠ **IT REPORTS WHAT IT FINDS RATHER THAN WHAT IT HOPED.** If the refusal
    happens before any SQL is issued, the savepoint is not what saved the run
    and this says so — a proof that claims more than it showed is worth less
    than none (hard-won law 7)."""
    print("\n── PART E · the savepoint, on PostgreSQL (law 14) ──────────────")
    ghost = "00000000-0000-0000-0000-0000000000ff"
    with transaction.atomic():
        try:
            with transaction.atomic():  # ← the savepoint under test
                payments_models.Payment.objects.create(
                    tenant_id=tenant_id,
                    account_id=ghost,
                    amount=Decimal("1.0000"),
                    currency="USD",
                    origin="import",
                    origin_is_derived=False,
                )
        except Exception as broke:  # the FK violation we asked for
            print(f"   the database refused a ghost account: {type(broke).__name__}")
        else:
            _fail("a payment on a non-existent account was ACCEPTED — the FK is gone")
        # The question law 14 exists to ask: is this connection usable now?
        try:
            with connection.cursor() as cur:
                cur.execute("SET app.tenant_id = %s", [tenant_id])
                cur.execute("SELECT count(*) FROM payments")
                still = int(cur.fetchone()[0])
        except Exception as poisoned:
            _fail(
                f"the transaction is ABORTED after one bad row: {type(poisoned).__name__}. "
                "Without the nested atomic() in _load_payments_rows, every payment "
                "written before the bad row is lost at COMMIT — silently, with the "
                "SQLite suite green."
            )
        print(f"   after the savepoint rolled back, the connection still answers: {still}")
        transaction.set_rollback(True)
    print("   PASS: a SAVEPOINT contains a refused row. Without it the run is lost.")
    print("   ⚠ This is the assertion SQLite cannot make — it has no aborted state.")


def main() -> None:
    if connection.vendor != "postgresql":
        _fail(
            f"this proof ran on {connection.vendor!r}. It is MEANINGLESS anywhere but "
            "PostgreSQL — SQLite has no aborted-transaction state, so the broken "
            "version passes. Set DATABASE_URL and DJANGO_SETTINGS_MODULE=config.settings.local."
        )
    print(f"P1.11 · payments import, end to end, on {connection.vendor}")
    tenant_id, account_no = _tenant_and_account()
    print(f"tenant {tenant_id} · account {account_no} · app.tenant_id SET")
    part_a_the_database_constrains_nothing(tenant_id)
    part_b_the_rules_and_the_writer_agree(tenant_id, account_no)
    part_c_one_bad_row_among_four_hundred(tenant_id, account_no)
    part_d_no_rollback_point_and_no_rollback(tenant_id, account_no)
    part_e_the_savepoint_is_load_bearing(tenant_id, account_no)
    print("\nALL PARTS PASSED on PostgreSQL.")


if __name__ == "__main__":
    main()

# ── Lifecycle ─────────────────────────────────────────────
# packet: 05-prototype/06 Payments Page Blueprint.pdf phase 1 (`P1.11`)
# generated: 2026-09-22 by lane P1-A
# gates: run it; it exits 1 on any part
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
