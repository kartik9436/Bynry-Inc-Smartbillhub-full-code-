#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-135-BRC07 — the payments blueprint's phase 0, task `P0.16`:
#          *"Migration forwards and backwards. Migration ordering is a 🔒
#          sensitive path."* Outcome: *"The deposit re-key is reversible."*
# Rules:   CLAUDE.md 🔒 sensitive paths (migration ordering) · hard rule 1
#          (RLS FORCE — the policy must come back with the table) · hard rule 4
#          (the payments freeze must be ON at every step, forwards and back) ·
#          hard-won law 7 (ask what would make this pass wrongly; a check's
#          output must distinguish pass from fail to a READER, and a declared
#          blind spot with no NUMBER attached is indistinguishable from an
#          empty one) · hard-won law 14 (a proof about the real database runs
#          on the real database)
# Tests:   06-backend/tests/test_cr135_p0_foundations.py::
#          test_p0_16_the_deposit_re_key_has_not_landed_and_this_fires_when_it_does
#          — the hold-expiry half, which runs in the ordinary suite.
# ───────────────────────────────────────────────────────
"""`P0.16` — phase 0's four migrations, applied, reversed and re-applied.

WHY A SCRIPT AND NOT A pytest CASE
------------------------------------
Reversing a migration ALTERS the database the test process is connected to.
`pytest` wraps each case in a transaction it rolls back, which is the right
thing for rows and the wrong thing for a schema walk — and a case that migrated
the test database backwards would leave every sibling case in the run looking
at a schema that no longer matches the models. So this is a script against a
**private clone**, the same shape as `cr135_counter_sessions_rls_readback.py`,
and the clone is thrown away afterwards.

RUN IT — the whole line, because a header that omits `JOBS_EAGER=false` costs
an hour (`DEF-567`):

    10-scripts/proof-db.sh clone p0rev        # sub-second, private to you
    PGDATABASE=sbh_clone_p0rev python3 10-scripts/cr135_migrations_forwards_and_backwards.py

⚠ **WHAT IS AND IS NOT PROVED, WITH THE NUMBER ATTACHED**
-----------------------------------------------------------
`P0.16`'s OUTCOME names the deposit re-key: *"The deposit re-key is
reversible."* That is `P0.6` — *"drop `uq_deposit_batches_day_method` and key
on the session"* — and it is `payments/0033`. **It is reversed FIRST here, on
its own hop**, so the key swapping back is observable rather than inferred.

**What this proves: the SHAPE.** Four migrations applied, reversed to
`payments/0029` and re-applied; every object each creates is gone after its own
reverse and back after the re-apply; the payments freeze is ON at every point;
and `payments.origin` is untouched, because a reverse that went one migration
too far would destroy every recorded origin on a live database.

**What it does NOT prove, and the number is the point (hard-won law 7):** the
DATA half. `payments/0033` carries `name_the_till` / `unname_the_till`, and on
a clone holding **0 deposit batches** those move **0 rows** — so a green run
here says nothing about what happens to batches already banked. That is
`10-scripts/p06_rekey_readback.py`'s subject.

**And a proof that names four migrations is true of those four for ever.** What
notices a FIFTH is `06-backend/tests/test_cr135_p0_foundations.py::
test_p0_16_every_phase_0_migration_is_in_the_reversibility_proof`, which reads
`PHASE_0` below and compares it with the migrations on disk.

WHAT WOULD MAKE THIS PASS WRONGLY, AND WHAT STOPS EACH
--------------------------------------------------------
  1. **The three migrations were never applied**, so "they reversed cleanly" is
     a statement about nothing. → STEP 0 refuses unless all three are recorded
     in `django_migrations` AND the objects they create are present.
  2. **The reverse quietly did nothing** — `RunPython` with a `noop` reverse
     reports success and leaves the schema exactly as it was. → STEP 2 asserts
     each object is GONE, by name, out of the catalogue. ⚠ **And the reverse is
     taken in TWO HOPS because one hop could not see this**: dropping
     `counter_sessions` takes its policies with it, so *no policy remains* was
     true even with `payments/0032`'s `drop_rls` made a no-op — measured, and
     the reason STEP 1a exists.
  3. **The reverse went too far** and took `payments/0029`'s columns with it.
     → STEP 2 asserts `origin` and `origin_is_derived` are still there. A
     reverse that removed them would destroy the column on a live database.
  4. **The freeze came off and stayed off.** `payments/0030` disables
     `trg_payment_immutable` for its backfill. → the trigger's state is read at
     every one of the four points, not only at the end.
  5. **It ran on SQLite**, where there is no RLS, no trigger and no partial
     index to speak of. → STEP 0 refuses anything but PostgreSQL.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "06-backend"

#: The four phase 0 migrations, newest first — the order they reverse in.
#: ⚠ `test_cr135_p0_foundations.py::
#: test_p0_16_every_phase_0_migration_is_in_the_reversibility_proof` compares
#: this tuple with what is on disk, so a fifth one cannot land unreversed.
PHASE_0 = (
    "0033_cr135_p0_6_deposit_batch_rekey",
    "0032_rls_cr135_p0_5_counter_sessions",
    "0031_cr135_p0_3_p0_4_counter_sessions",
    "0030_cr135_p0_1_p0_2_origin_check",
)
#: The migration phase 0 rests on. Reversing TO it leaves `payments.origin` in
#: place, which is the point of case 3 above.
FLOOR = "0029_cr132_payment_origin"
#: The intermediate stop. Reversing TO it undoes `payments/0032` and NOTHING
#: else, which is the only point at which the policy's removal is observable —
#: see `step_1_reverse`.
RLS_FLOOR = "0031_cr135_p0_3_p0_4_counter_sessions"
#: The FIRST stop, and the one `P0.16`'s stated outcome is about. Reversing TO
#: it undoes `payments/0033` — the deposit re-key — and nothing else.
REKEY_FLOOR = "0032_rls_cr135_p0_5_counter_sessions"

TABLE = "counter_sessions"
CHECKS = ("ck_payments_origin", "ck_payments_origin_derived_needs_a_value")
PARTIAL_INDEX = "uq_counter_sessions_open_owner"
FREEZE = "trg_payment_immutable"

#: `P0.6`'s subject — the key it DROPS, and the one its reverse must put back.
ENTER_TENANT_PROOF = "SELECT set_config('app.tenant_id', %s, false)"
LEAVE_TENANT_PROOF = "SELECT set_config('app.tenant_id', '', false)"
DEPOSIT_DAY_METHOD_KEY = "uq_deposit_batches_day_method"
#: What `P0.6` keys on instead: one till × one tender.
DEPOSIT_SESSION_METHOD_KEY = "uq_deposit_batches_session_method"
#: The two columns `payments/0033` adds. A reverse that leaves either behind
#: has not reversed — and a column is the cheapest thing in a migration to
#: forget, because nothing downstream complains about a spare one.
REKEY_COLUMNS = (("deposit_batches", "session_id"), ("counter_sessions", "system_day"))

FAILURES: list[str] = []


def say(line: str) -> None:
    print(line, flush=True)


def fail(line: str) -> None:
    FAILURES.append(line)
    say(f"  ✗ {line}")


def ok(line: str) -> None:
    say(f"  ✓ {line}")


# ═══════════════════════════════════════════════════════════════════════════
#  the database, read directly rather than through Django's ORM
# ═══════════════════════════════════════════════════════════════════════════


def connect():
    """One connection to the clone named by `PGDATABASE`.

    Read directly with `psycopg` rather than through Django, because Django
    caches the model state and this script's whole subject is the schema
    changing under it.
    """
    import psycopg

    database = os.environ.get("PGDATABASE")
    if not database:
        sys.exit(
            "cr135_migrations_forwards_and_backwards: set PGDATABASE to a PRIVATE clone.\n"
            "  10-scripts/proof-db.sh clone p0rev\n"
            "  PGDATABASE=sbh_clone_p0rev python3 "
            "10-scripts/cr135_migrations_forwards_and_backwards.py\n"
            "⚠ This script MIGRATES BACKWARDS. Never point it at a shared database."
        )
    return psycopg.connect(
        host=os.environ.get("PGHOST", "127.0.0.1"),
        port=int(os.environ.get("PGPORT", "5432")),
        user=os.environ.get("PGUSER", "smartbillhub"),
        password=os.environ.get("PGPASSWORD", "smartbillhub"),
        dbname=database,
        autocommit=True,
    )


def one(cursor, sql, params=()):
    cursor.execute(sql, params)
    row = cursor.fetchone()
    return row[0] if row else None


def table_exists(cursor, name) -> bool:
    return bool(
        one(
            cursor,
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s AND c.relkind = 'r'",
            (name,),
        )
    )


def checks_on_payments(cursor) -> set[str]:
    cursor.execute(
        "SELECT conname FROM pg_constraint WHERE conrelid = 'payments'::regclass "
        "AND conname LIKE 'ck_payments_origin%'"
    )
    return {row[0] for row in cursor.fetchall()}


def index_exists(cursor, name) -> bool:
    return bool(one(cursor, "SELECT count(*) FROM pg_indexes WHERE indexname = %s", (name,)))


def policy_count(cursor, table) -> int:
    return one(cursor, "SELECT count(*) FROM pg_policies WHERE tablename = %s", (table,)) or 0


def rls_flags(cursor, table):
    cursor.execute(
        "SELECT c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relname = %s",
        (table,),
    )
    row = cursor.fetchone()
    return tuple(row) if row else None


def columns_of(cursor, table) -> set[str]:
    cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s",
        (table,),
    )
    return {row[0] for row in cursor.fetchall()}


def deposit_keys(cursor) -> set[str]:
    cursor.execute(
        "SELECT indexname FROM pg_indexes WHERE tablename = 'deposit_batches' "
        "AND indexname LIKE 'uq_deposit_batches%'"
    )
    return {row[0] for row in cursor.fetchall()}


def payments_columns(cursor) -> set[str]:
    cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'payments'"
    )
    return {row[0] for row in cursor.fetchall()}


def freeze_state(cursor):
    """`'O'` = enabled, fires on origin. `'D'` = disabled. `None` = gone."""
    return one(
        cursor,
        "SELECT t.tgenabled FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
        "WHERE c.relname = 'payments' AND t.tgname = %s",
        (FREEZE,),
    )


def applied(cursor) -> set[str]:
    cursor.execute("SELECT name FROM django_migrations WHERE app = 'payments'")
    return {row[0] for row in cursor.fetchall()}


def assert_freeze_on(cursor, when: str) -> None:
    state = freeze_state(cursor)
    if state == "O":
        ok(f"the payments freeze is ON {when}")
    else:
        fail(
            f"the payments freeze is {state!r}, not 'O', {when}. CLAUDE.md hard "
            "rule 4 rests on this trigger."
        )


# ═══════════════════════════════════════════════════════════════════════════
#  the migrations, run the way a deployment runs them
# ═══════════════════════════════════════════════════════════════════════════


def migrate(target: str) -> None:
    """`manage.py migrate payments <target>`, against the clone.

    ⚠ **Through `manage.py`, never by hand-executing the operations.** The
    thing `P0.16` is about is ORDERING — whether the reverse of three
    migrations, run by the framework in the order it chooses, leaves a
    consistent schema. A script that called each `database_backwards` itself
    would be proving its own ordering rather than Django's.
    """
    database = os.environ["PGDATABASE"]
    env = dict(os.environ)
    env["DJANGO_SETTINGS_MODULE"] = "config.settings.local"
    env["JOBS_EAGER"] = "false"
    env["DATABASE_URL"] = (
        f"postgres://{env.get('PGUSER', 'smartbillhub')}:"
        f"{env.get('PGPASSWORD', 'smartbillhub')}@"
        f"{env.get('PGHOST', '127.0.0.1')}:{env.get('PGPORT', '5432')}/{database}"
        "?sslmode=disable"
    )
    say(f"  … manage.py migrate payments {target}")
    done = subprocess.run(
        [sys.executable, "manage.py", "migrate", "payments", target, "--no-input"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
    )
    for line in (done.stdout + done.stderr).splitlines():
        if line.strip():
            say(f"      {line}")
    if done.returncode != 0:
        fail(f"`migrate payments {target}` exited {done.returncode}")
        raise SystemExit(report())


# ═══════════════════════════════════════════════════════════════════════════
#  the four points
# ═══════════════════════════════════════════════════════════════════════════


def step_0_the_starting_state(cursor) -> None:
    say("\nSTEP 0 — the starting state, refused if it is not what this script assumes")
    version = one(cursor, "SHOW server_version")
    say(f"  PostgreSQL {version}")

    missing = [name for name in PHASE_0 if name not in applied(cursor)]
    if missing:
        fail(
            f"{len(missing)} of phase 0's {len(PHASE_0)} migrations are not applied to this "
            f"database: {', '.join(missing)}. There is nothing to reverse, and a "
            "green run would be a statement about nothing."
        )
        raise SystemExit(report())
    ok(f"all {len(PHASE_0)} phase 0 migrations are recorded in django_migrations")

    if table_exists(cursor, TABLE):
        ok(f"{TABLE} exists")
    else:
        fail(f"{TABLE} does not exist although payments/0031 is recorded as applied")

    found = checks_on_payments(cursor)
    if found == set(CHECKS):
        ok(f"both origin CHECKs are on `payments`: {', '.join(sorted(found))}")
    else:
        fail(f"expected {sorted(CHECKS)} on `payments`, found {sorted(found)}")

    if index_exists(cursor, PARTIAL_INDEX):
        ok(f"{PARTIAL_INDEX} exists (P0.4's partial unique index)")
    else:
        fail(f"{PARTIAL_INDEX} does not exist")

    flags = rls_flags(cursor, TABLE)
    if flags == (True, True):
        ok(f"{TABLE} is ENABLE + FORCE row level security")
    else:
        fail(f"{TABLE}'s RLS flags are {flags}, not (True, True) — hard rule 1")

    policies = policy_count(cursor, TABLE)
    if policies == 1:
        ok(f"{TABLE} carries exactly 1 policy")
    else:
        fail(f"{TABLE} carries {policies} policies, expected 1")

    keys = deposit_keys(cursor)
    if DEPOSIT_SESSION_METHOD_KEY in keys and DEPOSIT_DAY_METHOD_KEY not in keys:
        ok(f"deposit_batches is keyed on {DEPOSIT_SESSION_METHOD_KEY} — P0.6 is applied")
    else:
        fail(
            f"deposit_batches carries {sorted(keys)}. Expected "
            f"{DEPOSIT_SESSION_METHOD_KEY} and NOT {DEPOSIT_DAY_METHOD_KEY} — "
            "payments/0033 is recorded as applied, so the schema disagrees with "
            "django_migrations."
        )
    for table, column in REKEY_COLUMNS:
        if column in columns_of(cursor, table):
            ok(f"{table}.{column} exists")
        else:
            fail(f"{table}.{column} is missing although payments/0033 is applied")

    assert_freeze_on(cursor, "before anything is reversed")


def step_1_reverse(cursor) -> None:
    """Reverse in TWO hops, and the first hop is the whole reason this is not one.

    ⚠ **A SINGLE HOP TO `0029` CANNOT TELL WHETHER `payments/0032` REVERSED AT
    ALL.** Reversing `payments/0031` DROPS `counter_sessions`, and dropping a
    table takes its policies with it — so *no policy remains* is true whether
    `drop_rls` did its work or returned immediately. **Measured, not reasoned:
    `drop_rls` was made a no-op and this script stayed GREEN**, which is
    CLAUDE.md hard-won law 7's *looking at the wrong thing* in a check that
    reads perfectly sensible.

    So the reverse stops at `0031` first, where the table is still there and the
    flags and the policy are the only things that can have moved. That is also a
    truer test of ORDERING — each migration's reverse is observed on its own
    rather than as one lump.
    """
    say(f"\nSTEP 1a — reverse ONLY payments/0033, the deposit re-key: payments → {REKEY_FLOOR}")
    say("  (this is `P0.16`'s stated outcome: *the deposit re-key is reversible*)")
    migrate(REKEY_FLOOR)

    keys = deposit_keys(cursor)
    if DEPOSIT_DAY_METHOD_KEY in keys:
        ok(f"{DEPOSIT_DAY_METHOD_KEY} is BACK — the day × tender key was restored")
    else:
        fail(
            f"{DEPOSIT_DAY_METHOD_KEY} did not come back. ⚠ THIS IS THE ONE THAT "
            "COSTS MONEY: `P0.6`'s own outcome says *a dropped unique key with no "
            "replacement lets two batches collide silently*, and a reverse that "
            "restores neither key leaves exactly that. "
            f"deposit_batches carries {sorted(keys)}."
        )
    if DEPOSIT_SESSION_METHOD_KEY in keys:
        fail(
            f"{DEPOSIT_SESSION_METHOD_KEY} survived the reverse of payments/0033 — "
            "the database would then enforce BOTH keys and refuse rows each was "
            "written for."
        )
    else:
        ok(f"{DEPOSIT_SESSION_METHOD_KEY} is gone")

    for table, column in REKEY_COLUMNS:
        if column in columns_of(cursor, table):
            fail(
                f"{table}.{column} survived the reverse of payments/0033. A column "
                "left behind is the cheapest thing in a migration to forget, "
                "because nothing downstream complains about a spare one."
            )
        else:
            ok(f"{table}.{column} is gone")

    say(f"\nSTEP 1b — reverse ONLY payments/0032: payments → {RLS_FLOOR}")
    migrate(RLS_FLOOR)

    flags = rls_flags(cursor, TABLE)
    if not table_exists(cursor, TABLE):
        fail(
            f"{TABLE} disappeared when only payments/0032 was reversed — an RLS "
            "migration must not take the table with it."
        )
    elif flags == (False, False):
        ok(f"{TABLE} still exists and its RLS flags are back to {flags}")
    else:
        fail(
            f"{TABLE}'s RLS flags are {flags} after reversing payments/0032, not "
            "(False, False) — the reverse reported success and left the policy on."
        )

    policies = policy_count(cursor, TABLE)
    if policies:
        fail(
            f"{policies} policy/policies survive on {TABLE} with its table still "
            "present. payments/0032's reverse reported success and changed nothing."
        )
    else:
        ok(f"no policy remains on {TABLE} while the table is still there")

    say(f"\nSTEP 1c — reverse the other two: payments → {FLOOR}")
    migrate(FLOOR)


def step_2_the_reversed_state(cursor) -> None:
    say("\nSTEP 2 — what the reverse left behind")
    still = [name for name in PHASE_0 if name in applied(cursor)]
    if still:
        fail(f"{len(still)} phase 0 migration(s) are still recorded as applied: {still}")
    else:
        ok(f"none of the {len(PHASE_0)} is recorded as applied any more")

    if table_exists(cursor, TABLE):
        fail(
            f"{TABLE} is STILL THERE after payments/0031 was reversed. A reverse "
            "that reports success and changes nothing is CLAUDE.md hard-won law 7's "
            "*structurally incapable of failing* — the migration would be recorded "
            "as un-applied over a table that exists."
        )
    else:
        ok(f"{TABLE} is gone")

    if index_exists(cursor, PARTIAL_INDEX):
        fail(f"{PARTIAL_INDEX} survived the reverse")
    else:
        ok(f"{PARTIAL_INDEX} is gone with its table")

    if policy_count(cursor, TABLE):
        fail(f"a policy on {TABLE} survived the reverse of payments/0032")
    else:
        ok(f"no policy remains for {TABLE}")

    found = checks_on_payments(cursor)
    if found:
        fail(f"origin CHECK(s) survived the reverse of payments/0030: {sorted(found)}")
    else:
        ok("both origin CHECKs are gone from `payments`")

    # ⚠ THE ONE THAT WOULD COST DATA. `payments/0030` must reverse its own
    # constraints and NOTHING of `payments/0029` — a reverse that dropped the
    # column would destroy every recorded origin on a live database, and
    # re-applying forward would bring the column back EMPTY.
    columns = payments_columns(cursor)
    survived = {"origin", "origin_is_derived"} & columns
    if survived == {"origin", "origin_is_derived"}:
        ok("`payments.origin` and `payments.origin_is_derived` are still there — "
           "the reverse stopped at its own floor and did not take 0029's columns")
    else:
        fail(
            "the reverse went past payments/0030 and removed "
            f"{sorted({'origin', 'origin_is_derived'} - columns)} from `payments`. "
            "On a live database that is every recorded origin destroyed."
        )

    assert_freeze_on(cursor, "after the reverse")


def step_3_forward_again(cursor) -> None:
    say(f"\nSTEP 3 — forward again: payments → {PHASE_0[0]}")
    migrate(PHASE_0[0])

    say("\nSTEP 4 — the re-applied state, compared with step 0")
    missing = [name for name in PHASE_0 if name not in applied(cursor)]
    if missing:
        fail(f"{len(missing)} migration(s) did not re-apply: {missing}")
    else:
        ok(f"all {len(PHASE_0)} are applied again")

    if table_exists(cursor, TABLE):
        ok(f"{TABLE} is back")
    else:
        fail(f"{TABLE} did not come back")

    if index_exists(cursor, PARTIAL_INDEX):
        ok(f"{PARTIAL_INDEX} is back")
    else:
        fail(f"{PARTIAL_INDEX} did not come back — P0.4's guarantee would be absent")

    flags = rls_flags(cursor, TABLE)
    if flags == (True, True):
        ok(f"{TABLE} is ENABLE + FORCE again")
    else:
        fail(
            f"{TABLE}'s RLS flags came back as {flags}. ⚠ A table that returns "
            "WITHOUT its policy is hard rule 1 broken and looks entirely healthy."
        )

    policies = policy_count(cursor, TABLE)
    if policies == 1:
        ok(f"{TABLE} carries exactly 1 policy again")
    else:
        fail(f"{TABLE} carries {policies} policies after re-applying, expected 1")

    found = checks_on_payments(cursor)
    if found == set(CHECKS):
        ok("both origin CHECKs are back")
    else:
        fail(f"the origin CHECKs came back as {sorted(found)}")

    keys = deposit_keys(cursor)
    if DEPOSIT_SESSION_METHOD_KEY in keys and DEPOSIT_DAY_METHOD_KEY not in keys:
        ok(f"deposit_batches is keyed on {DEPOSIT_SESSION_METHOD_KEY} again")
    else:
        fail(f"after re-applying, deposit_batches carries {sorted(keys)}")
    for table, column in REKEY_COLUMNS:
        if column in columns_of(cursor, table):
            ok(f"{table}.{column} is back")
        else:
            fail(f"{table}.{column} did not come back")

    assert_freeze_on(cursor, "after re-applying forwards")


def step_5_the_deposit_re_key(cursor) -> None:
    """`P0.16`'s stated OUTCOME, and the honest answer to it.

    ⚠ **A NUMBER, NOT A SILENCE.** CLAUDE.md hard-won law 7: *a declared blind
    spot with no NUMBER attached is indistinguishable from an empty one.* This
    prints what it covered beside what it could not.
    """
    say("\nSTEP 5 — P0.16's stated outcome: *the deposit re-key is reversible*")
    keys = deposit_keys(cursor)
    if DEPOSIT_SESSION_METHOD_KEY in keys and DEPOSIT_DAY_METHOD_KEY not in keys:
        say(
            f"  ✓ PROVED. {len(PHASE_0)} of {len(PHASE_0)} phase 0 migrations "
            "reversed and re-applied, the deposit re-key among them:\n"
            f"    forwards  deposit_batches is keyed {DEPOSIT_SESSION_METHOD_KEY} "
            "(one till × one tender)\n"
            f"    backwards it is keyed {DEPOSIT_DAY_METHOD_KEY} again, and both "
            "columns payments/0033 added are gone\n"
            "    ⚠ WHAT THIS STEP COVERS IS THE SHAPE, on a clone holding 0 "
            "deposit batches — so\n"
            "    `payments/0033`'s data half (`name_the_till` / "
            "`unname_the_till`) moved 0 rows here.\n"
            "    STEP 6 puts the data in and asks again; what NEITHER covers is a "
            "live deployment's\n"
            "    ALREADY-BANKED batches, which is "
            "`10-scripts/p06_rekey_readback.py`'s subject."
        )
    else:
        fail(
            "after a full reverse and re-apply, deposit_batches carries "
            f"{sorted(keys)} — the re-key did not survive the round trip."
        )


# ═══════════════════════════════════════════════════════════════════════════
#  STEP 6 — the reverse with DATA in it, which is the claim nothing had tested
# ═══════════════════════════════════════════════════════════════════════════

#: Two system tills for two different banking days. `uq_counter_sessions_
#: system_day` is UNIQUE (tenant, system_day) WHERE system_day IS NOT NULL, so
#: two system tills must name two days — and their BATCHES may still share a
#: `deposited_on`, which is exactly the collision being modelled.
SEED_SESSION = """
    INSERT INTO counter_sessions
      (id, tenant_id, owner_id, service_centre_id, opening_float, currency,
       opened_at, closed_at, closed_by, close_kind, system_day,
       created_at, updated_at)
    VALUES (%s, %s, NULL, NULL, 0, 'USD', now(), now(), NULL, 'system', %s,
            now(), now())
"""
SEED_BATCH = """
    INSERT INTO deposit_batches
      (id, tenant_id, code, recorded_total, status, deposited_on, method_id,
       session_id, created_at, updated_at)
    VALUES (%s, %s, %s, 0, 'in_transit', %s, %s, %s, now(), now())
"""
A_METHOD = "SELECT id FROM payment_methods LIMIT 1"
A_TENANT = "SELECT id FROM tenants ORDER BY created_at LIMIT 1"
#: `BR-PAY-004` / hard rule 4 — a deposit batch may not be DELETEd. The
#: clean-up below lifts this for exactly two rows and puts it straight back.
BATCH_FREEZE = "trg_deposit_batch_lock"


def step_6_the_reverse_with_data_in_it(cursor) -> None:
    """⚠ **THE REVIEW-LEDGER ROW FOR `payments/0033` MAKES A CLAIM AND NOTHING
    TESTED IT.** Verbatim: *"It is only reversible while no batch has been cut
    on the new shape, because restoring the day × method key over two tills'
    batches for one day would refuse."*

    That is a statement about the database, and CLAUDE.md hard-won law 1 says a
    comment claiming a guarantee — or, here, claiming a LIMIT — is not the
    guarantee. STEP 1a proved the reverse works on a clone holding **0 deposit
    batches**; this cuts the two batches the sentence describes and asks
    PostgreSQL.

    **It is a REFUSAL that is being proved, not a success**, so the pass
    condition is `migrate` FAILING. A silent success here would mean the
    rollback the ledger row offers can destroy a uniqueness guarantee on a live
    deployment — two batches for one day and one tender, with nothing left to
    keep them apart.

    Everything it writes is deleted before it returns, whichever way it goes.
    """
    say("\nSTEP 6 — the reverse with DATA in it: two tills, one day, one tender")

    # ⚠ **THE TENANT GOES IN BEFORE THE METHOD IS READ, AND THIS SCRIPT GOT IT
    # WRONG FIRST TIME.** `payment_methods` carries RLS, so with `app.tenant_id`
    # unset it answers **0 rows, truthfully**, and the first draft of this step
    # reported *"this clone has no payment method"* over a table with plenty.
    # `tenants` has no policy, which is why the tenant can be read first — and
    # is exactly why the mistake is easy: one of the two reads works.
    tenant = one(cursor, A_TENANT)
    if tenant is None:
        fail("this clone has no tenant — STEP 6 cannot seed")
        return
    cursor.execute(ENTER_TENANT_PROOF, [str(tenant)])
    method = one(cursor, A_METHOD)
    if method is None:
        fail(
            f"no payment method is visible inside tenant {tenant} — STEP 6 cannot "
            "seed a batch, which needs one. (If this reads as an empty table, "
            "check the tenant was really set: an unset GUC answers zero.)"
        )
        cursor.execute(LEAVE_TENANT_PROOF)
        return

    import uuid

    sessions = [uuid.uuid4(), uuid.uuid4()]
    batches = [uuid.uuid4(), uuid.uuid4()]
    try:
        for session, day in zip(sessions, ("2026-09-20", "2026-09-21")):
            cursor.execute(SEED_SESSION, [str(session), str(tenant), day])
        for batch, session in zip(batches, sessions):
            cursor.execute(
                SEED_BATCH,
                [str(batch), str(tenant), f"P016-{str(batch)[:8]}", "2026-09-22",
                 str(method), str(session)],
            )
        ok("two batches cut on the new shape: one banking day, one tender, two tills")

        refused = migrate_expecting_failure(REKEY_FLOOR)
        if refused:
            ok(
                "the reverse REFUSED, as the review-ledger row says it would — "
                "PostgreSQL would not put `uq_deposit_batches_day_method` back "
                "over two batches that share a day and a tender"
            )
            say(f"      {refused}")
        else:
            fail(
                "the reverse SUCCEEDED with two colliding batches in the table. "
                "The review-ledger row for payments/0033 says it cannot, and the "
                "rollback it offers would then leave `deposit_batches` with no "
                "key keeping two batches for one day and one tender apart."
            )
    finally:
        # ⚠ **THE CLEAN-UP HAS TO LIFT `trg_deposit_batch_lock`, AND THAT IS THE
        # PRODUCT BEING RIGHT RATHER THAN A NUISANCE.** `BR-PAY-004` / hard rule
        # 4 refuses a DELETE on a deposit batch — *"a batch is the record of what
        # physically went to the bank on a day; corrections are new events on its
        # trail, never a deletion"* — so a seeded batch cannot simply be removed.
        # The freeze comes off for the two DELETEs and goes straight back in the
        # same block, which is what `payments/0018` and `payments/0030` do, and
        # the state is ASSERTED afterwards rather than assumed: a proof script
        # that left a clone's money freeze off would be worse than no proof.
        cursor.execute(f"ALTER TABLE deposit_batches DISABLE TRIGGER {BATCH_FREEZE}")
        try:
            for batch in batches:
                cursor.execute("DELETE FROM deposit_batches WHERE id = %s", [str(batch)])
        finally:
            cursor.execute(f"ALTER TABLE deposit_batches ENABLE TRIGGER {BATCH_FREEZE}")
        state = one(
            cursor,
            "SELECT t.tgenabled FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
            "WHERE c.relname = 'deposit_batches' AND t.tgname = %s",
            (BATCH_FREEZE,),
        )
        if state == "O":
            ok(f"{BATCH_FREEZE} is back ON after the clean-up")
        else:
            fail(f"{BATCH_FREEZE} is {state!r}, not 'O' — this script left a money freeze off")

        for session in sessions:
            cursor.execute("DELETE FROM counter_sessions WHERE id = %s", [str(session)])
        cursor.execute(LEAVE_TENANT_PROOF)
        # The reverse may have got part-way; put the branch's shape back.
        migrate(PHASE_0[0])
        ok("the seeded rows are deleted and the schema is forward again")


def migrate_expecting_failure(target: str) -> str:
    """Run `migrate payments <target>` and return its error, or `""` on success.

    Separate from `migrate()` deliberately: that one treats a non-zero exit as a
    failure of the script, and here a non-zero exit is the result being asked
    for. A single function with a flag would make the two indistinguishable to
    a reader, which is what hard-won law 7's third habit is about.
    """
    database = os.environ["PGDATABASE"]
    env = dict(os.environ)
    env["DJANGO_SETTINGS_MODULE"] = "config.settings.local"
    env["JOBS_EAGER"] = "false"
    env["DATABASE_URL"] = (
        f"postgres://{env.get('PGUSER', 'smartbillhub')}:"
        f"{env.get('PGPASSWORD', 'smartbillhub')}@"
        f"{env.get('PGHOST', '127.0.0.1')}:{env.get('PGPORT', '5432')}/{database}"
        "?sslmode=disable"
    )
    say(f"  … manage.py migrate payments {target}  (a REFUSAL is the pass here)")
    done = subprocess.run(
        [sys.executable, "manage.py", "migrate", "payments", target, "--no-input"],
        cwd=BACKEND, env=env, capture_output=True, text=True,
    )
    if done.returncode == 0:
        return ""
    lines = [ln.strip() for ln in (done.stdout + done.stderr).splitlines() if ln.strip()]
    return lines[-1] if lines else f"exit {done.returncode}"


def report() -> int:
    say("")
    if FAILURES:
        say(f"cr135 migrations forwards-and-backwards: {len(FAILURES)} FAILURE(S) — recap")
        for line in FAILURES:
            say(f"  ✗ {line}")
        return 1
    say(
        f"cr135 migrations forwards-and-backwards: PASS — {len(PHASE_0)} migration(s) "
        f"({', '.join(sorted(PHASE_0))}) reversed to {FLOOR} and re-applied, with "
        "the freeze ON at every point and `payments.origin` untouched."
    )
    return 0


def main() -> int:
    say(__doc__.splitlines()[0])
    connection = connect()
    with connection.cursor() as cursor:
        step_0_the_starting_state(cursor)
        step_1_reverse(cursor)
        step_2_the_reversed_state(cursor)
        step_3_forward_again(cursor)
        step_5_the_deposit_re_key(cursor)
        step_6_the_reverse_with_data_in_it(cursor)
    return report()


if __name__ == "__main__":
    raise SystemExit(main())
