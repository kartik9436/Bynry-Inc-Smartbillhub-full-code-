"""`P0.6` — DOES THE RE-KEY ACTUALLY LET TWO TILLS BANK, AND DOES THE GUARD BITE?

The worked case the PO signed on, and the figures this asserts:

    Dana's Tuesday till holds  $1,240  of cheques
    Sam's   Tuesday till holds  $  880  of cheques
    ------------------------------------------------
    the day must still tie to   $2,120  exactly

⚠ **ON POSTGRESQL, NOT THE SUITE** (hard-won law 14 · `P0.14`).
`config/settings/test.py` hardcodes in-memory SQLite, which has **no partial
index, no triggers, no RLS and no real concurrency** — so every guarantee this
task adds is *structurally incapable of failing* there, which is law 7's own
phrase. A green suite says nothing about any of it.

⚠ **`app.tenant_id` IS SET BEFORE ANYTHING IS COUNTED.** `deposit_batches` and
`payments` carry RLS FORCE, so an unscoped count answers **0** and a reader
calls that clean. Section 0 prints the unscoped and the scoped figure side by
side so the difference is visible rather than assumed. Five lanes have nearly
reported a false zero this way.

⚠ **IT WRITES NOTHING.** Everything happens inside a `transaction.atomic()`
that is rolled back by raising. The last section re-reads and shows it.

HOW TO RUN IT
-------------
    10-scripts/proof-db.sh clone p06rekey
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p06rekey?sslmode=disable \\
      python3 manage.py shell < ../10-scripts/p06_rekey_readback.py

WHAT WOULD MAKE THIS CHECK PASS WRONGLY (law 7, habit 2)
---------------------------------------------------------
  * **A FALSE ZERO FROM RLS** — see above; section 0 prints both counts.
  * **"TWO BATCHES" WITHOUT "TWO DIFFERENT TILLS".** Two rows could exist and
    share a session. Section 2 asserts the two `session_id`s differ AND that
    each batch's total is its own clerk's figure, not half the day.
  * **THE GUARD LOOKING GREEN BECAUSE NOTHING REACHED IT.** A guard that never
    ran is not a guard that passed, so section 3 asserts the EXCEPTION TEXT,
    not merely that something raised — a `NOT NULL` violation and a trigger
    refusal both raise `IntegrityError`/`ProgrammingError`.
  * **THE PARTIAL KEY BEING MISTAKEN FOR THE OLD ONE.** Section 4 proves BOTH
    directions: a second batch for the SAME till and tender is refused, and a
    second batch for a DIFFERENT till and the same tender is allowed — which
    is the whole point and is the assertion the old key would fail.
  * **THE LEGACY POPULATION QUIETLY ACQUIRING A ROW.** Section 5 counts
    session-less batches before and after and asserts the number did not move.
"""

import os
import sys
import traceback
from datetime import date, datetime, timezone
from decimal import Decimal

from django.db import connection, transaction, utils as db_utils

from apps.payments import bankrec_models as bankrec
from apps.payments import counter_session_models as tills
from apps.payments import models as pay_models
from core import numbering as core_numbering
from core.tenancy import tenant_context

TENANT_SUBDOMAIN = os.environ.get("P06_TENANT", "brazosbend")
DAY = date(2026, 9, 22)
DANA = Decimal("1240.0000")
SAM = Decimal("880.0000")
EXPECTED = Decimal("2120.0000")

failures: list[str] = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'ok ' if ok else 'FAIL'}] {label}: {got!r}" + ("" if ok else f" (want {want!r})"))
    if not ok:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def check_raises(label, fn, must_contain):
    try:
        with transaction.atomic():
            fn()
    except Exception as exc:  # noqa: BLE001 — the message IS the assertion
        text = str(exc)
        ok = must_contain in text
        print(f"  [{'ok ' if ok else 'FAIL'}] {label} refused")
        print(f"          {text.splitlines()[0][:190]}")
        if not ok:
            failures.append(f"{label}: refusal did not mention {must_contain!r} — {text[:200]}")
        return
    print(f"  [FAIL] {label}: NOTHING RAISED — the guard did not fire")
    failures.append(f"{label}: nothing raised")


def sql(statement, *params):
    with connection.cursor() as cur:
        cur.execute(statement, params)
        return cur.fetchall()


print("=" * 78)
print("P0.6 — the deposit batch re-keyed on the till, on PostgreSQL")
print("=" * 78)
print(f"vendor: {connection.vendor}")
if connection.vendor != "postgresql":
    print("REFUSED: this proof is meaningless on anything but PostgreSQL (law 14).")
    sys.exit(2)

from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.tenancy import published_content_models as tenancy_content  # noqa: E402

tenant = tenancy_models.Tenant.objects.get(subdomain=TENANT_SUBDOMAIN)
method = None

print("\n0 · RLS IS ON, AND THE UNSCOPED COUNT IS A LIE (both printed)")
print("-" * 78)
unscoped = sql("SELECT count(*) FROM deposit_batches")[0][0]
with tenant_context(str(tenant.id)):
    scoped = bankrec.DepositBatch.objects.count()
    legacy_before = bankrec.DepositBatch.objects.filter(session__isnull=True).count()
    method = tenancy_models.PaymentMethod.objects.filter(code="check").first()
print(f"  unscoped (app.tenant_id unset): {unscoped}")
print(f"  scoped   (app.tenant_id set)  : {scoped}")
print(f"  of those, session-less (banked the old way): {legacy_before}")
if unscoped != 0:
    print("  ⚠ unscoped answered non-zero — this role may bypass RLS; the run is weaker")
if method is None:
    print("REFUSED: this tenant has no 'check' payment method seeded.")
    sys.exit(2)

print("\n1 · THE SCHEMA SAYS WHAT `P0.6` ASKED FOR")
print("-" * 78)
idx = {r[0]: r[1] for r in sql(
    "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'deposit_batches'"
)}
check("uq_deposit_batches_day_method is GONE", "uq_deposit_batches_day_method" in idx, False)
check("uq_deposit_batches_session_method exists", "uq_deposit_batches_session_method" in idx, True)
partial = idx.get("uq_deposit_batches_session_method", "")
check("...and it is PARTIAL", "WHERE" in partial.upper(), True)
print(f"          {partial}")
trg = sql(
    "SELECT tgname FROM pg_trigger WHERE tgrelid = 'deposit_batches'::regclass AND NOT tgisinternal"
)
check("trg_deposit_batch_needs_session is installed", any(t[0] == "trg_deposit_batch_needs_session" for t in trg), True)

print("\n2 · TWO TILLS, TWO BATCHES, ONE DAY — AND THE DAY STILL TIES TO $2,120")
print("-" * 78)
try:
    with tenant_context(str(tenant.id)):
        with transaction.atomic():
            moment = datetime(2026, 9, 22, 0, 0, tzinfo=timezone.utc)
            users = list(
                __import__("apps.identity.models", fromlist=["User"]).User.objects.all()[:2]
            )
            if len(users) < 2:
                raise RuntimeError("need two users in this tenant")
            # ⚠ The seeded demo tenant has NO service centre, and a person's
            # till requires one — `ck_counter_sessions_system_is_nobodys`
            # refuses an ownerless non-system session and a centre-less owned
            # one. So the proof makes its own, inside the same rolled-back
            # transaction as everything else. Section 7 shows nothing is left.
            centre = tenancy_content.ServiceCentre.objects.first()
            if centre is None:
                centre = tenancy_content.ServiceCentre.objects.create(
                    tenant=tenant,
                    slug="p06-proof-counter",
                    name="P0.6 proof counter",
                    address="rolled back",
                )

            dana_till = tills.CounterSession.objects.create(
                tenant=tenant, owner=users[0], service_centre=centre,
                opening_float=Decimal("200.0000"), opened_at=moment,
            )
            sam_till = tills.CounterSession.objects.create(
                tenant=tenant, owner=users[1], service_centre=centre,
                opening_float=Decimal("200.0000"), opened_at=moment,
            )
            check("two DIFFERENT tills", dana_till.pk != sam_till.pk, True)

            dana_batch = bankrec.DepositBatch.objects.create(
                tenant=tenant, code=core_numbering.next_number("deposit_batch", DAY),
                session=dana_till, method=method, deposited_on=DAY,
                recorded_total=DANA, status=bankrec.BATCH_IN_TRANSIT,
            )
            sam_batch = bankrec.DepositBatch.objects.create(
                tenant=tenant, code=core_numbering.next_number("deposit_batch", DAY),
                session=sam_till, method=method, deposited_on=DAY,
                recorded_total=SAM, status=bankrec.BATCH_IN_TRANSIT,
            )
            print(f"  Dana banks {dana_batch.code}  ${dana_batch.recorded_total}")
            print(f"  Sam  banks {sam_batch.code}  ${sam_batch.recorded_total}")
            check("the two codes DIFFER", dana_batch.code != sam_batch.code, True)
            check("the two tills DIFFER", dana_batch.session_id != sam_batch.session_id, True)
            check("Dana's own total", dana_batch.recorded_total, DANA)
            check("Sam's own total", sam_batch.recorded_total, SAM)
            check("the day ties", dana_batch.recorded_total + sam_batch.recorded_total, EXPECTED)
            check("the code carries the day", dana_batch.code.startswith("DEP-260922-"), True)
            check("the code carries NO tender", "CHK" not in dana_batch.code, True)

            print("\n3 · THE GUARD: NOTHING MAY CREATE A BATCH WITHOUT A TILL")
            print("-" * 78)
            check_raises(
                "a session-less batch",
                lambda: bankrec.DepositBatch.objects.create(
                    tenant=tenant, code=core_numbering.next_number("deposit_batch", DAY),
                    session=None, method=method, deposited_on=DAY,
                    recorded_total=Decimal("1.0000"), status=bankrec.BATCH_IN_TRANSIT,
                ),
                "cannot be created without a counter session",
            )
            # ⚠ A REPAIR SCRIPT WITH A CURSOR — the reason the guard is at the
            # database and not in the service (BR-SHL-025).
            check_raises(
                "a raw INSERT that bypasses every Python check",
                lambda: sql(
                    "INSERT INTO deposit_batches "
                    "(id, tenant_id, code, method_id, recorded_total, status, deposited_on, "
                    " created_at, updated_at, session_id) "
                    "VALUES (gen_random_uuid(), %s, 'DEP-RAW-0001', %s, 0, 'in_transit', %s, "
                    " now(), now(), NULL)",
                    str(tenant.id), str(method.id), DAY,
                ),
                "cannot be created without a counter session",
            )

            print("\n4 · THE PARTIAL KEY, BOTH DIRECTIONS")
            print("-" * 78)
            check_raises(
                "a SECOND batch for Dana's till and cheques",
                lambda: bankrec.DepositBatch.objects.create(
                    tenant=tenant, code=core_numbering.next_number("deposit_batch", DAY),
                    session=dana_till, method=method, deposited_on=DAY,
                    recorded_total=Decimal("5.0000"), status=bankrec.BATCH_IN_TRANSIT,
                ),
                "uq_deposit_batches_session_method",
            )
            cash = tenancy_models.PaymentMethod.objects.filter(code="cash").first()
            if cash is not None:
                dana_cash = bankrec.DepositBatch.objects.create(
                    tenant=tenant, code=core_numbering.next_number("deposit_batch", DAY),
                    session=dana_till, method=cash, deposited_on=DAY,
                    recorded_total=Decimal("600.0000"), status=bankrec.BATCH_IN_TRANSIT,
                )
                print(f"  [ok ] Dana's CASH batch is allowed: {dana_cash.code} $600.0000")
                print("        one till, two tenders, two batches — OQ-PAY-12577 (a)")
            else:
                print("  [    ] no 'cash' method seeded; the two-tender half not shown")

            print("\n5 · THE SYSTEM TILL IS NOBODY'S, AND THE CONSTRAINTS SAY SO")
            print("-" * 78)
            system = tills.CounterSession.objects.create(
                tenant=tenant, owner=None, service_centre=None, system_day=DAY,
                opening_float=Decimal("0"), opened_at=moment, closed_at=moment,
                closed_by=None, close_kind=pay_models.COUNTER_CLOSE_SYSTEM,
            )
            print(f"  [ok ] a system till exists: owner={system.owner_id} centre={system.service_centre_id}")
            check("it is CLOSED from birth", system.closed_at is not None, True)
            check(
                "so it never answers 'which tills are open'",
                tills.CounterSession.objects.filter(closed_at__isnull=True, system_day__isnull=False).count(),
                0,
            )
            check_raises(
                "a SECOND system till for the same day",
                lambda: tills.CounterSession.objects.create(
                    tenant=tenant, owner=None, service_centre=None, system_day=DAY,
                    opening_float=Decimal("0"), opened_at=moment, closed_at=moment,
                    closed_by=None, close_kind=pay_models.COUNTER_CLOSE_SYSTEM,
                ),
                "uq_counter_sessions_system_day",
            )
            check_raises(
                "a system till carrying an OWNER",
                lambda: tills.CounterSession.objects.create(
                    tenant=tenant, owner=users[0], service_centre=centre,
                    system_day=date(2026, 9, 23), opening_float=Decimal("0"),
                    opened_at=moment, closed_at=moment, closed_by=users[0],
                    close_kind=pay_models.COUNTER_CLOSE_SYSTEM,
                ),
                "ck_counter_sessions_system_is_nobodys",
            )
            # ⚠ THE MIRROR, AND IT IS THE HALF A NEGATION WOULD HAVE MISSED:
            # an OPEN till with no owner. `close_kind` is NULL there, so a
            # `NOT (close_kind = 'system')` spelling evaluates to NULL and the
            # CHECK would PASS. This is the assertion that proves it does not.
            check_raises(
                "an OPEN till with no owner",
                lambda: tills.CounterSession.objects.create(
                    tenant=tenant, owner=None, service_centre=None, system_day=None,
                    opening_float=Decimal("0"), opened_at=moment,
                ),
                "ck_counter_sessions_system_is_nobodys",
            )
            check_raises(
                "a system till carrying a FLOAT",
                lambda: tills.CounterSession.objects.create(
                    tenant=tenant, owner=None, service_centre=None,
                    system_day=date(2026, 9, 24), opening_float=Decimal("50.0000"),
                    opened_at=moment, closed_at=moment, closed_by=None,
                    close_kind=pay_models.COUNTER_CLOSE_SYSTEM,
                ),
                "ck_counter_sessions_system_is_nobodys",
            )

            print("\n6 · THE LEGACY POPULATION DID NOT GAIN A ROW")
            print("-" * 78)
            legacy_now = bankrec.DepositBatch.objects.filter(session__isnull=True).count()
            check("session-less batches, unchanged", legacy_now, legacy_before)

            raise RuntimeError("__ROLLBACK__")
except RuntimeError as exc:
    if "__ROLLBACK__" not in str(exc):
        traceback.print_exc()
        failures.append(f"unexpected: {exc}")
except Exception:  # noqa: BLE001
    traceback.print_exc()
    failures.append("the run raised before it finished")

print("\n7 · NOTHING WAS WRITTEN")
print("-" * 78)
with tenant_context(str(tenant.id)):
    after = bankrec.DepositBatch.objects.count()
    tills_after = tills.CounterSession.objects.count()
check("deposit_batches, unchanged", after, scoped)
check("counter_sessions left behind", tills_after, 0)
with tenant_context(str(tenant.id)):
    centres_after = tenancy_content.ServiceCentre.objects.count()
check("service centres left behind", centres_after, 0)

print("\n" + "=" * 78)
if failures:
    print(f"FAILED — {len(failures)}")
    for f in failures:
        print(f"  · {f}")
    sys.exit(1)
print("ALL CHECKS PASSED — Dana $1,240 · Sam $880 · the day $2,120")
print("=" * 78)
