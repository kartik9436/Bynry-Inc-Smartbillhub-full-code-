"""`CR-136-BRC07` `P2.20` — THE LATE COUNT, PROVED ON A REAL POSTGRESQL.

Run it against a database at `payments/0034` and it goes RED, four times. Run
it against one at `payments/0035` and it goes GREEN. That is the whole proof,
and it is taken on PostgreSQL 16 because **SQLite cannot show any of this**
(CLAUDE.md hard-won law 14) and the suite runs there.

WHAT IS BEING PROVED
---------------------
PO ruling 2026-09-23, verbatim: *"(a) Keep it as a forced close and add the
late count beside it… The row reads: force-closed Monday by the supervisor,
declared Tuesday by Dana, $12 short. It leaves the Not counted list. Nothing is
erased"*. The ruling also names the MECHANISM — *"the pairing is a CONSTRAINT,
not a service check, for the same reason `ck_counter_sessions_closed_together`
is"* — so what has to hold is two facts in one CHECK:

  (a) `declared_at` and `declared_by` are **both set or both NULL**
  (b) `declared_at` set **requires `close_kind = 'forced'`** — a counted till
      was already counted, and a system till is nobody's

⚠ SECTION 2 IS THE ONE THAT MATTERS, AND IT IS `DEF-PAY-6207` AGAIN
--------------------------------------------------------------------
**A CHECK constraint refuses a row only when its expression is FALSE, and
PASSES when the expression is NULL.** `close_kind` is NULL on every till that
is still OPEN. So a second branch written the obvious way —

    declared_at IS NOT NULL AND declared_by IS NOT NULL
      AND close_kind = 'forced'

— reads `TRUE AND TRUE AND NULL` = NULL on an open till, the chain becomes
`FALSE OR NULL` = NULL, **and the row is accepted**: a drawer declared as
counted before it was ever sealed, sitting on the *which tills are open* screen
with a count against it. That is the third time this exact fault has been
reachable in this one table; the first two are `payments/0034`.

Section 2 does not take that on trust. It **builds both spellings on a scratch
table in this database, feeds the same row to each, and prints both verdicts**
— so the RED reading survives in the repository instead of being a thing a lane
says it saw once.

WHAT WOULD MAKE THIS CHECK PASS WRONGLY (hard-won law 7, habit 2)
-------------------------------------------------------------------
  * **A FALSE ZERO FROM RLS.** `counter_sessions` carries RLS FORCE and a
    statement with `app.tenant_id` unset matches nothing. Section 0 prints the
    unscoped and the scoped counts side by side, so a zero cannot pass for a
    clean run.
  * **THE INSERT FAILING FOR AN UNRELATED REASON AND READING AS THE GUARD.**
    Every refusal is asserted **by constraint NAME**. A NOT NULL violation, an
    FK violation and three different CHECK violations all raise one Python
    class, and `ck_counter_sessions_closed_together` and
    `ck_counter_sessions_system_is_nobodys` sit on this very table — so a row
    refused by a neighbour would otherwise read as a pass.
  * **THE ROW BEING REFUSED BY A NEIGHBOUR.** Every bad row below is built to
    satisfy BOTH neighbours, so only `ck_counter_sessions_declared_together`
    can refuse it. The system-till case in particular carries its
    `system_day`, no owner, no centre and a zero float for exactly this reason.
  * **A FIX THAT REFUSES EVERYTHING.** Section 3 writes the four shapes the
    schema is SUPPOSED to hold, including the ruling's own worked case, and
    every one must be accepted.
  * **A GREEN THAT MEANS NOTHING WAS TRIED.** Each case prints the row it
    attempted and the verdict.

HOW TO RUN IT

    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p2db?sslmode=disable \\
      python3 manage.py shell < ../10-scripts/cr136_p2_20_declared_readback.py

It writes nothing: every attempt is inside a SAVEPOINT that is rolled back, and
section 2's scratch table is dropped.
"""

import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal

from django.db import connection, transaction

from apps.payments import counter_session_models as tills
from apps.tenancy import models as tenancy_models
from apps.tenancy import published_content_models as tenancy_content
from core.tenancy import tenant_context

TENANT_SUBDOMAIN = os.environ.get("P2_TENANT", "brazosbend")
DAY = date(2026, 9, 21)
MONDAY = datetime(2026, 9, 21, 17, 30, tzinfo=timezone.utc)
TUESDAY = datetime(2026, 9, 22, 8, 40, tzinfo=timezone.utc)

GUARD = "ck_counter_sessions_declared_together"

failures: list[str] = []


class _Undo(Exception):
    """Rolls a savepoint back after a row was ACCEPTED."""


def attempt(label, build, must_name):
    """Try the row. Report which constraint refused it, BY NAME."""
    try:
        with transaction.atomic():
            build()
            raise _Undo
    except _Undo:
        print(f"  [RED ] {label}: **ACCEPTED** — {must_name} did not fire")
        failures.append(f"{label}: the row was ACCEPTED; {must_name} is not doing its job")
        return
    except Exception as exc:  # noqa: BLE001 — the message IS the assertion
        text = str(exc).replace("\n", " ")
        if must_name in text:
            print(f"  [ok  ] {label}")
            print(f"          refused by {must_name}")
            return
        print(f"  [FAIL] {label}: refused, but NOT by {must_name}")
        print(f"          {text[:190]}")
        failures.append(f"{label}: wrong refusal — {text[:150]}")
        return


print("=" * 78)
print("CR-136-BRC07 P2.20 — the late count sits beside the forced close")
print("=" * 78)
print(f"vendor: {connection.vendor}")
if connection.vendor != "postgresql":
    print("REFUSED: meaningless off PostgreSQL (hard-won law 14) — SQLite cannot")
    print("show a CHECK's NULL behaviour and the suite runs there.")
    sys.exit(2)

with connection.cursor() as cur:
    cur.execute("SELECT name FROM django_migrations WHERE app='payments' ORDER BY id DESC LIMIT 1")
    applied = cur.fetchone()[0]
print(f"payments is at: {applied}")
print("  (0034 = the columns do not exist yet and section 1 cannot run;")
print("   0035 = every bad row below is refused by name)")

with connection.cursor() as cur:
    cur.execute(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = %s",
        [GUARD],
    )
    row = cur.fetchone()
print(f"\n{GUARD}:")
print(f"  {row[0] if row else '— NOT PRESENT —'}")
# ⚠ **THE FIRST SPELLING OF THIS TEST ASKED FOR `IS NOT NULL` AND PASSED OVER
# THE BROKEN CONSTRAINT.** The naive spelling contains `declared_at IS NOT
# NULL` and `declared_by IS NOT NULL`, so a substring test for *any* IS NOT
# NULL is true of both and could never fail on the one shape it exists for —
# hard-won law 7's *structurally incapable of failing*, found by running this
# script against the naive constraint and watching it stay silent. It asks for
# the one term that matters, by column name.
if row and "close_kind IS NOT NULL" not in row[0].replace("(", "").replace(")", ""):
    failures.append(
        f"{GUARD} exists but its definition does not test `close_kind IS NOT "
        "NULL` — that is DEF-PAY-6207's shape and the branch is switched off "
        "for every OPEN till, where close_kind is NULL"
    )

tenant = tenancy_models.Tenant.objects.get(subdomain=TENANT_SUBDOMAIN)

print("\n0 · RLS IS ON, AND THE UNSCOPED COUNT IS A LIE (both printed)")
print("-" * 78)
with connection.cursor() as cur:
    cur.execute("SELECT count(*) FROM counter_sessions")
    unscoped = cur.fetchone()[0]
with tenant_context(str(tenant.id)):
    scoped = tills.CounterSession.objects.count()
print(f"  unscoped (app.tenant_id unset): {unscoped}")
print(f"  scoped   (app.tenant_id set)  : {scoped}")

with tenant_context(str(tenant.id)):
    try:
        with transaction.atomic():
            from apps.identity.models import User

            people = list(User.objects.all()[:2])
            if not people:
                raise RuntimeError("this tenant has no user to own a till")
            dana = people[0]
            supervisor = people[1] if len(people) > 1 else people[0]
            centre = tenancy_content.ServiceCentre.objects.first()
            if centre is None:
                centre = tenancy_content.ServiceCentre.objects.create(
                    tenant=tenant, slug="p2-20-probe", name="probe", address="rolled back"
                )

            def forced(**extra):
                """Dana's Monday till, force-closed by the supervisor."""
                base = dict(
                    tenant=tenant,
                    owner=dana,
                    service_centre=centre,
                    opening_float=Decimal("200.0000"),
                    opened_at=MONDAY,
                    closed_at=MONDAY,
                    closed_by=supervisor,
                    close_kind="forced",
                )
                base.update(extra)
                return lambda: tills.CounterSession.objects.create(**base)

            print("\n1 · THE FOUR ROWS THE RULING FORBIDS")
            print("-" * 78)
            print("  Each is built to satisfy ck_counter_sessions_closed_together AND")
            print("  ck_counter_sessions_system_is_nobodys, so only the new guard can")
            print("  refuse it — otherwise a neighbour's refusal would read as a pass.")

            print("\n  1a · half a declaration: a count with nobody's name on it")
            attempt(
                "declared_at set, declared_by NULL, on a forced close",
                forced(declared_at=TUESDAY, declared_by=None),
                GUARD,
            )

            print("\n  1b · half a declaration the other way: a name with no date")
            attempt(
                "declared_by set, declared_at NULL, on a forced close",
                forced(declared_at=None, declared_by=dana),
                GUARD,
            )

            print("\n  1c · ⚠ DEF-PAY-6207's SHAPE — an OPEN till, declared")
            print("       close_kind is NULL on an open till, which is exactly where a")
            print("       branch without `close_kind IS NOT NULL` stops checking.")
            attempt(
                "an OPEN till carrying a declaration",
                lambda: tills.CounterSession.objects.create(
                    tenant=tenant,
                    owner=dana,
                    service_centre=centre,
                    opening_float=Decimal("200.0000"),
                    opened_at=MONDAY,
                    closed_at=None,
                    closed_by=None,
                    close_kind=None,
                    declared_at=TUESDAY,
                    declared_by=dana,
                ),
                GUARD,
            )

            print("\n  1d · a COUNTED till, declared — it was already counted")
            attempt(
                "a counted close carrying a declaration",
                forced(close_kind="counted", declared_at=TUESDAY, declared_by=dana),
                GUARD,
            )

            print("\n  1e · a SYSTEM till, declared — a system till is nobody's")
            attempt(
                "a system till carrying a declaration",
                lambda: tills.CounterSession.objects.create(
                    tenant=tenant,
                    owner=None,
                    service_centre=None,
                    system_day=DAY,
                    opening_float=Decimal("0"),
                    opened_at=MONDAY,
                    closed_at=MONDAY,
                    closed_by=None,
                    close_kind="system",
                    declared_at=TUESDAY,
                    declared_by=dana,
                ),
                GUARD,
            )

            print("\n2 · THE LAWFUL SHAPES ARE STILL ACCEPTED")
            print("-" * 78)
            print("  A fix that refuses everything is not a fix. The first of these is")
            print("  the PO's own worked case: force-closed Monday by the supervisor,")
            print("  declared Tuesday by Dana, $12.00 short.")
            for label, kwargs in (
                (
                    "the ruling's worked case — forced Monday, declared Tuesday, $12 short",
                    dict(
                        owner=dana,
                        service_centre=centre,
                        opening_float=Decimal("200.0000"),
                        opened_at=MONDAY,
                        closed_at=MONDAY,
                        closed_by=supervisor,
                        close_kind="forced",
                        declared_at=TUESDAY,
                        declared_by=dana,
                        difference=Decimal("-12.0000"),
                        note="cheque stuck to the bag",
                    ),
                ),
                (
                    "a forced close nobody has counted yet (Not counted)",
                    dict(
                        owner=dana,
                        service_centre=centre,
                        opening_float=Decimal("200.0000"),
                        opened_at=MONDAY,
                        closed_at=MONDAY,
                        closed_by=supervisor,
                        close_kind="forced",
                    ),
                ),
                (
                    "a normal counted close, never declared",
                    dict(
                        owner=dana,
                        service_centre=centre,
                        opening_float=Decimal("200.0000"),
                        opened_at=MONDAY,
                        closed_at=MONDAY,
                        closed_by=dana,
                        close_kind="counted",
                    ),
                ),
                (
                    "an OPEN till belonging to a person",
                    dict(
                        owner=dana,
                        service_centre=centre,
                        opening_float=Decimal("200.0000"),
                        opened_at=MONDAY,
                    ),
                ),
            ):
                try:
                    with transaction.atomic():
                        tills.CounterSession.objects.create(tenant=tenant, **kwargs)
                        raise _Undo
                except _Undo:
                    print(f"  [ok  ] {label}: accepted, as it must be")
                except Exception as exc:  # noqa: BLE001
                    print(f"  [FAIL] {label}: REFUSED — the guard is too strong")
                    print(f"          {str(exc).replace(chr(10), ' ')[:190]}")
                    failures.append(f"{label} was refused; the guard over-reaches")

            print("\n3 · `NOT COUNTED` IS ONE EXPRESSION AND THIS IS IT")
            print("-" * 78)
            print(f"  counter_session_models.NOT_COUNTED = {tills.NOT_COUNTED}")
            print("  Four readers: 3·1's list, its filter chip, P2.11's notice, and")
            print("  phase 2's done-when. None of them is built on 2026-09-23.")

            raise RuntimeError("__ROLLBACK__")
    except RuntimeError as exc:
        if "__ROLLBACK__" not in str(exc):
            raise

print("\n4 · THE RED READING, KEPT — BOTH SPELLINGS, SAME ROW, ON A SCRATCH TABLE")
print("-" * 78)
print("  ⚠ A lane saying *I saw it accept the bad row before I added the clause*")
print("    is a claim nothing re-checks. This builds both spellings here, now,")
print("    and feeds each the open-till-with-a-declaration from case 1c.")
NAIVE = """
    CREATE TEMP TABLE cr136_naive (
        close_kind   text,
        declared_at  timestamptz,
        declared_by  uuid,
        CONSTRAINT ck_naive CHECK (
            (declared_at IS NULL AND declared_by IS NULL)
            OR (declared_at IS NOT NULL AND declared_by IS NOT NULL
                AND close_kind = 'forced')
        )
    )
"""
GUARDED = """
    CREATE TEMP TABLE cr136_guarded (
        close_kind   text,
        declared_at  timestamptz,
        declared_by  uuid,
        CONSTRAINT ck_guarded CHECK (
            (declared_at IS NULL AND declared_by IS NULL)
            OR (close_kind IS NOT NULL
                AND declared_at IS NOT NULL AND declared_by IS NOT NULL
                AND close_kind = 'forced')
        )
    )
"""
BAD_ROW = (
    "INSERT INTO {} (close_kind, declared_at, declared_by) "
    "VALUES (NULL, now(), gen_random_uuid())"
)


def _run(statement):
    with connection.cursor() as cur:
        cur.execute(statement)


for statement in ("DROP TABLE IF EXISTS cr136_naive", "DROP TABLE IF EXISTS cr136_guarded"):
    _run(statement)
_run(NAIVE)
_run(GUARDED)

for table, spelling, expect_refusal in (
    ("cr136_naive", "close_kind = 'forced'                              ", False),
    ("cr136_guarded", "close_kind IS NOT NULL AND close_kind = 'forced'", True),
):
    try:
        with transaction.atomic():
            _run(BAD_ROW.format(table))
            refused = False
            raise _Undo
    except _Undo:
        pass
    except Exception:  # noqa: BLE001 — the refusal IS the measurement
        refused = True
    verdict = "refused" if refused else "**ACCEPTED** ← the hole"
    mark = "ok  " if refused == expect_refusal else "FAIL"
    print(f"  [{mark}] {spelling}")
    print(f"          an OPEN till carrying a declaration → {verdict}")
    if refused != expect_refusal:
        failures.append(
            f"the `{spelling.strip()}` demonstration did not behave as stated — "
            "section 4 is measuring the wrong thing"
        )
for statement in ("DROP TABLE IF EXISTS cr136_naive", "DROP TABLE IF EXISTS cr136_guarded"):
    _run(statement)
print("  ⚠ THAT IS THE WHOLE OF DEF-PAY-6207 IN FIVE LINES: `FALSE OR NULL` is")
print("    NULL, and a CHECK accepts NULL.")

print("\n5 · NOTHING WAS WRITTEN")
print("-" * 78)
with tenant_context(str(tenant.id)):
    after = tills.CounterSession.objects.count()
print(f"  counter_sessions: {after} (was {scoped})")
if after != scoped:
    failures.append(f"rows left behind: {after} vs {scoped}")

print("\n" + "=" * 78)
if failures:
    print(f"RED — {len(failures)} finding(s) at {applied}")
    for f in failures:
        print(f"  · {f}")
    sys.exit(1)
print(f"GREEN at {applied} — five forbidden rows refused BY NAME, four lawful")
print("shapes accepted, and the naive spelling shown accepting what it must not.")
print("=" * 78)
