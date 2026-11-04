"""`DEF-PAY-6207` — A CHECK BRANCH COMPARING A NULLABLE COLUMN TO A LITERAL.

Run it against a database at `payments/0033` and it goes RED, twice. Run it
against one at `payments/0034` and it goes GREEN. That is the whole proof, and
it is taken on PostgreSQL because that is where the guarantee has to hold.

THE RULE, WHICH IS THE PART WORTH KEEPING
------------------------------------------
**A CHECK constraint refuses a row only when its expression is FALSE, and
PASSES when the expression is NULL.** So:

  * adding a branch to an OR'd CHECK can only ever make it **WEAKER**, and
  * a branch that compares a **NULLABLE** column to a literal weakens it to
    **nothing** for every row where that column is NULL.

`FALSE OR FALSE OR NULL` is NULL, and NULL is accepted.

TWO CONSTRAINTS HAD IT, NOT ONE
--------------------------------
`DEF-PAY-6207` was filed against `ck_counter_sessions_closed_together`.
`ck_counter_sessions_system_is_nobodys` has the identical shape and is NOT in
the filed row — it was found by checking the other branches, which is what the
rule above tells you to do. Both are asserted here so neither can come back
alone.

WHAT EACH HOLE COSTS
---------------------
  1. **A till sealed with no record of how or by whom.** `closed_at` set,
     `close_kind` NULL, `closed_by` NULL. The PO's ruling of 2026-09-22 —
     *"(b) A System Admin can close it, recorded as a forced close"* — exists
     precisely so a forced close stays distinguishable from a counted one for
     ever, because somebody other than the owner counted a drawer the owner is
     accountable for. This row erases that.
  2. **An OPEN system till.** `system_day` set, `close_kind` NULL, no owner.
     `closed_at` is NULL, so it answers `ix_counter_sessions_open` and appears
     on the *"which tills are open"* screen — a drawer a supervisor would chase
     and that nobody ever sat at. A system till is supposed to be born closed
     for exactly this reason.

WHAT WOULD MAKE THIS CHECK PASS WRONGLY (law 7, habit 2)
---------------------------------------------------------
  * **A FALSE ZERO FROM RLS.** `app.tenant_id` is SET before anything is read
    or written; section 0 prints the unscoped and scoped counts side by side.
  * **THE INSERT FAILING FOR AN UNRELATED REASON AND READING AS THE GUARD.**
    Every refusal is asserted by CONSTRAINT NAME, not by "something raised" —
    a NOT NULL violation, an FK violation and a CHECK violation all raise the
    same Python class.
  * **THE ROW BEING REFUSED BY THE *OTHER* CONSTRAINT.** Case 2's row is built
    to satisfy `ck_counter_sessions_closed_together` (all three closing columns
    NULL), so only `ck_counter_sessions_system_is_nobodys` can refuse it. Case
    1's row carries no `system_day`, so only `closed_together` can refuse it.
  * **A GREEN THAT MEANS "NOTHING WAS TRIED".** Each case prints the row it
    attempted and the verdict, so a reader sees the attempt and not just a tick.

HOW TO RUN IT
-------------
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_def6207?sslmode=disable \\
      python3 manage.py shell < ../10-scripts/def_pay_6207_null_branch_readback.py

It writes nothing: every attempt is inside a SAVEPOINT that is rolled back.
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

TENANT_SUBDOMAIN = os.environ.get("P06_TENANT", "brazosbend")
DAY = date(2026, 9, 22)
MOMENT = datetime(2026, 9, 22, 17, 30, tzinfo=timezone.utc)

failures: list[str] = []


class _Undo(Exception):
    """Rolls a savepoint back after a row was ACCEPTED."""


def attempt(label, build, must_name):
    """Try the row. Report which constraint refused it, BY NAME.

    ⚠ **THE SAVEPOINT ROLLS BACK WHETHER THE ROW WAS ACCEPTED OR REFUSED, AND
    THE FIRST DRAFT OF THIS SCRIPT DID NOT.** When a RED case was accepted its
    row survived inside the outer transaction and collided with a later case:
    section 3's lawful *closed system till* was refused by
    `uq_counter_sessions_system_day` — by the row section 2 had just left
    behind — and printed *"the fix is too strong"*, which was a statement about
    this probe and not about the schema. A check whose earlier case changes the
    answer to its later one is not measuring what it says it measures.
    """
    try:
        with transaction.atomic():
            build()
            raise _Undo
    except _Undo:
        print(f"  [RED ] {label}: **ACCEPTED** — {must_name} did not fire")
        failures.append(f"{label}: the row was ACCEPTED; {must_name} is switched off")
        return
    except Exception as exc:  # noqa: BLE001 — the message IS the assertion
        text = str(exc).replace("\n", " ")
        if must_name in text:
            print(f"  [ok  ] {label}")
            print(f"          refused by {must_name}")
            return
        print(f"  [FAIL] {label}: refused, but NOT by {must_name}")
        print(f"          {text[:170]}")
        failures.append(f"{label}: wrong refusal — {text[:150]}")
        return


print("=" * 78)
print("DEF-PAY-6207 — a CHECK branch comparing a nullable column to a literal")
print("=" * 78)
print(f"vendor: {connection.vendor}")
if connection.vendor != "postgresql":
    print("REFUSED: meaningless off PostgreSQL (hard-won law 14).")
    sys.exit(2)

applied = None
with connection.cursor() as cur:
    cur.execute(
        "SELECT name FROM django_migrations WHERE app='payments' ORDER BY id DESC LIMIT 1"
    )
    applied = cur.fetchone()[0]
print(f"payments is at: {applied}")
print("  (0033 = the hole is open and both cases below go RED;")
print("   0034 = both are refused by name)")

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
            user = __import__("apps.identity.models", fromlist=["User"]).User.objects.first()
            centre = tenancy_content.ServiceCentre.objects.first()
            if centre is None:
                centre = tenancy_content.ServiceCentre.objects.create(
                    tenant=tenant, slug="def6207-probe", name="probe", address="rolled back"
                )
            if user is None:
                raise RuntimeError("this tenant has no user to own a till")

            print("\n1 · A TILL SEALED WITH NO RECORD OF HOW OR BY WHOM")
            print("-" * 78)
            print("  row: closed_at SET · close_kind NULL · closed_by NULL · a real owner")
            print("       (carries no system_day, so ONLY ck_counter_sessions_closed_together")
            print("        can refuse it)")
            attempt(
                "a till sealed with no record of how",
                lambda: tills.CounterSession.objects.create(
                    tenant=tenant,
                    owner=user,
                    service_centre=centre,
                    opening_float=Decimal("200.0000"),
                    opened_at=MOMENT,
                    closed_at=MOMENT,
                    closed_by=None,
                    close_kind=None,
                ),
                "ck_counter_sessions_closed_together",
            )

            print("\n2 · AN OPEN SYSTEM TILL — NOT IN THE FILED ROW, FOUND BY CHECKING")
            print("-" * 78)
            print("  row: system_day SET · close_kind NULL · no owner · all three closing")
            print("       columns NULL (so closed_together is satisfied and ONLY")
            print("       ck_counter_sessions_system_is_nobodys can refuse it)")
            attempt(
                "an OPEN system till",
                lambda: tills.CounterSession.objects.create(
                    tenant=tenant,
                    owner=None,
                    service_centre=None,
                    system_day=DAY,
                    opening_float=Decimal("0"),
                    opened_at=MOMENT,
                    closed_at=None,
                    closed_by=None,
                    close_kind=None,
                ),
                "ck_counter_sessions_system_is_nobodys",
            )

            print("\n3 · THE LAWFUL NEIGHBOURS ARE STILL ACCEPTED")
            print("-" * 78)
            print("  A fix that refuses everything is not a fix. Both shapes the schema")
            print("  is SUPPOSED to hold are written here and must succeed.")
            for label, kwargs in (
                (
                    "a normal counted close",
                    dict(
                        owner=user, service_centre=centre, opening_float=Decimal("200.0000"),
                        opened_at=MOMENT, closed_at=MOMENT, closed_by=user, close_kind="counted",
                    ),
                ),
                (
                    "a CLOSED system till (born closed, nobody's)",
                    dict(
                        owner=None, service_centre=None, system_day=DAY,
                        opening_float=Decimal("0"), opened_at=MOMENT, closed_at=MOMENT,
                        closed_by=None, close_kind="system",
                    ),
                ),
                (
                    "an OPEN till belonging to a person",
                    dict(
                        owner=user, service_centre=centre, opening_float=Decimal("200.0000"),
                        opened_at=MOMENT,
                    ),
                ),
            ):
                # Its own savepoint, rolled back, so no lawful row can collide
                # with the next one either (`uq_counter_sessions_system_day`).
                try:
                    with transaction.atomic():
                        tills.CounterSession.objects.create(tenant=tenant, **kwargs)
                        raise _Undo
                except _Undo:
                    print(f"  [ok  ] {label}: accepted, as it must be")
                except Exception as exc:  # noqa: BLE001
                    print(f"  [FAIL] {label}: REFUSED — the fix is too strong")
                    print(f"          {str(exc).replace(chr(10), ' ')[:170]}")
                    failures.append(f"{label} was refused; the fix over-reaches")

            raise RuntimeError("__ROLLBACK__")
    except RuntimeError as exc:
        if "__ROLLBACK__" not in str(exc):
            raise

print("\n4 · NOTHING WAS WRITTEN")
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
print(f"GREEN at {applied} — both holes refused BY NAME, all three lawful shapes accepted")
print("=" * 78)
