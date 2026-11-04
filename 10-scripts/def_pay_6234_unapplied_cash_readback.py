"""`DEF-PAY-6454` — a cancelled payment must not reach the month-end tie-out.

Run it with `selectors.unapplied_cash`'s `.exclude(status=PAYMENT_CANCELLED)`
REMOVED and it goes RED, naming the figure. Run it with the line in place and
it goes GREEN. That is the whole proof.

WHY IT IS A SCRIPT ON POSTGRESQL AND NOT ONLY A SUITE CASE
------------------------------------------------------------
`tests/test_cr137_p3_5_cancelled_is_not_unapplied_cash.py` is the durable
regression and runs on the default SQLite suite. This runs the same question
**where the tie-out actually runs**: on PostgreSQL 16, through the immutability
trigger, with the cancelled row reaching `cancelled` the way a clerk's cancel
reaches it — an `UPDATE` out of `processing`, which the trigger permits and
then freezes. On SQLite the status is simply written, because there is no
trigger there at all (hard-won law 14).

WHAT WENT WRONG
----------------
`unapplied_cash` answers *"real money in the bank that nobody has put on a
bill"* and runbook 9 (`month_end`) step 3 refuses to close against the figure.
It selects with `status__in=PAYMENT_FROZEN_STATUSES`, which is **derived** —
`tuple(s for s in PAYMENT_STATUSES if s != PAYMENT_PROCESSING)` — so
`payments/0036` adding a sixth status added it to a finance tie-out with no
edit anywhere near the query.

A cancelled payment has an `amount`, a `posted_at` and a `bill` purpose and can
never carry an allocation. It would have sat in unapplied cash for ever.

WHAT WOULD MAKE THIS PASS WRONGLY (law 7, habit 2)
----------------------------------------------------
  * **A FALSE ZERO FROM RLS.** Everything runs inside `tenant_context`; the
    unscoped and scoped counts are printed side by side.
  * **A FALSE ZERO FROM AN EMPTY WINDOW.** The CONTROL is an ordinary
    unallocated `cleared` payment in the same window, which MUST be counted —
    without it, a green would only say *this function returns nothing*.
  * **THE PROBE ROW NOT ACTUALLY BEING CANCELLED.** Its status is read back
    from the database after the UPDATE, and the UPDATE is the real one: out of
    `processing`, through the trigger.
  * **THE TWO CASES PASSING SEPARATELY ON A FUNCTION THAT RETURNS ONE ROW.**
    The third case runs both at once and asserts the count as well as the sum.

It writes nothing: everything is inside a transaction that is rolled back.

    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p3db?sslmode=disable \\
      python3 manage.py shell < ../10-scripts/def_pay_6234_unapplied_cash_readback.py
"""

import sys
from decimal import Decimal

from django.db import connection, transaction

from apps.payments import selectors
from apps.tenancy import models as tenancy_models
from core.tenancy import tenant_context

TENANT_SUBDOMAIN = "brazosbend"
CANCELLED_AMOUNT = Decimal("61.0000")
REAL_AMOUNT = Decimal("74.2500")

failures: list[str] = []

print("=" * 78)
print("DEF-PAY-6454 — a cancelled payment is not unapplied cash")
print("=" * 78)
print(f"vendor: {connection.vendor}")
if connection.vendor != "postgresql":
    print("REFUSED: the trigger this probe cancels THROUGH does not exist off PostgreSQL.")
    sys.exit(2)

tenant = tenancy_models.Tenant.objects.get(subdomain=TENANT_SUBDOMAIN)

print("\n0 · RLS IS ON (hard rule 1)")
print("-" * 78)
with connection.cursor() as cur:
    cur.execute("SELECT count(*) FROM payments")
    unscoped = cur.fetchone()[0]
with tenant_context(str(tenant.id)):
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM payments")
        scoped = cur.fetchone()[0]
print(f"  unscoped: {unscoped}   scoped: {scoped}")
if unscoped != 0:
    failures.append("RLS: an unscoped SELECT saw rows")

with tenant_context(str(tenant.id)):
    with connection.cursor() as cur:
        cur.execute(
            "SELECT attname FROM pg_attribute WHERE attrelid='payments'::regclass "
            "AND attnum > 0 AND NOT attisdropped ORDER BY attnum"
        )
        COLUMNS = [row[0] for row in cur.fetchall()]
        cur.execute(
            "SELECT id, posted_at FROM payments WHERE status='cleared' "
            "ORDER BY payment_no LIMIT 1"
        )
        template = cur.fetchone()
    if template is None:
        print("FAIL: no cleared payment to copy.")
        sys.exit(1)
    TEMPLATE_ID, POSTED_AT = template
    WINDOW = (POSTED_AT.date(), POSTED_AT.date())
    print(f"  window: {WINDOW[0]} .. {WINDOW[1]} (the template's own posting day)")

    BLANKED = ("payment_no", "webhook_key", "deposit_batch_id", "journal_entry_id")

    def fresh(status, amount, number):
        picks, params = [], []
        for name in COLUMNS:
            if name == "id":
                picks.append("gen_random_uuid()")
            elif name == "status":
                picks.append("%s")
                params.append(status)
            elif name == "amount":
                picks.append("%s")
                params.append(amount)
            elif name == "payment_no":
                picks.append("%s")
                params.append(number)
            elif name in BLANKED:
                picks.append("NULL")
            else:
                picks.append(f'"{name}"')
        names = ", ".join(f'"{one}"' for one in COLUMNS)
        with connection.cursor() as cur:
            cur.execute(
                f"INSERT INTO payments ({names}) SELECT {', '.join(picks)} "
                f"FROM payments WHERE id = %s RETURNING id",
                params + [TEMPLATE_ID],
            )
            return cur.fetchone()[0]

    def cancel(payment_id):
        """The REAL path: out of `processing`, which the trigger permits and
        then freezes. Not a planted status."""
        with connection.cursor() as cur:
            cur.execute("UPDATE payments SET status='cancelled' WHERE id = %s", [payment_id])
            cur.execute("SELECT status FROM payments WHERE id = %s", [payment_id])
            return cur.fetchone()[0]

    baseline = None
    print("\n1 · THE BASELINE — what this window already holds")
    print("-" * 78)
    with transaction.atomic():
        baseline = selectors.unapplied_cash(*WINDOW)
        print(f"  total {baseline['total']} across {baseline['payment_count']} payment(s)")
        transaction.set_rollback(True)

    print("\n2 · A CANCELLED PAYMENT MUST NOT MOVE THE FIGURE")
    print("-" * 78)
    with transaction.atomic():
        pid = fresh("processing", CANCELLED_AMOUNT, "PY-P3DB-CANCEL")
        landed = cancel(pid)
        print(f"  probe {pid} is now: {landed}")
        if landed != "cancelled":
            failures.append(f"the probe row is {landed!r}, not cancelled — nothing was tested")
        answer = selectors.unapplied_cash(*WINDOW)
        print(f"  total {answer['total']} across {answer['payment_count']} payment(s)")
        if answer["total"] != baseline["total"]:
            failures.append(
                f"a cancelled payment of {CANCELLED_AMOUNT} reached the month-end "
                f"unapplied-cash figure: {baseline['total']} -> {answer['total']}"
            )
            print("    [RED ] the cancelled payment IS counted")
        else:
            print("    [ok  ] the figure did not move")
        transaction.set_rollback(True)

    print("\n3 · THE CONTROL — an ordinary unallocated payment MUST still count")
    print("-" * 78)
    with transaction.atomic():
        fresh("cleared", REAL_AMOUNT, "PY-P3DB-REAL")
        answer = selectors.unapplied_cash(*WINDOW)
        print(f"  total {answer['total']} across {answer['payment_count']} payment(s)")
        if answer["total"] != baseline["total"] + REAL_AMOUNT:
            failures.append(
                f"the control failed: an unallocated cleared payment of {REAL_AMOUNT} "
                f"did not reach the figure ({baseline['total']} -> {answer['total']}). "
                f"Nothing case 2 says can be believed."
            )
            print("    [FAIL] the control did not count — case 2 proves nothing")
        else:
            print("    [ok  ] counted, so case 2's green is a real exclusion")
        transaction.set_rollback(True)

    print("\n4 · BOTH AT ONCE — only the real one counts")
    print("-" * 78)
    with transaction.atomic():
        cancel(fresh("processing", CANCELLED_AMOUNT, "PY-P3DB-CANCEL2"))
        fresh("cleared", REAL_AMOUNT, "PY-P3DB-REAL2")
        answer = selectors.unapplied_cash(*WINDOW)
        print(f"  total {answer['total']} across {answer['payment_count']} payment(s)")
        if answer["total"] != baseline["total"] + REAL_AMOUNT:
            failures.append(
                f"with one cancelled and one real payment the figure is {answer['total']}, "
                f"expected {baseline['total'] + REAL_AMOUNT}"
            )
            print("    [RED ] the cancelled one is in the total")
        else:
            print("    [ok  ] the cancelled one is absent and the real one is present")
        if answer["payment_count"] != baseline["payment_count"] + 1:
            failures.append(
                f"row count {answer['payment_count']}, expected " f"{baseline['payment_count'] + 1}"
            )
        transaction.set_rollback(True)

print("\n" + "=" * 78)
if failures:
    print(f"{len(failures)} FAILURE(S)")
    for one in failures:
        print(f"  - {one}")
    sys.exit(1)
print("ALL GREEN — a cancelled payment is absent from unapplied cash, an ordinary")
print("unallocated one is present, and both at once give one row and the right sum.")
sys.exit(0)
