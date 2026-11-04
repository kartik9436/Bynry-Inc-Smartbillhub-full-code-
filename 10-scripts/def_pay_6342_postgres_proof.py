"""`DEF-PAY-6342` — returned post, the flag and the clear, PROVED ON POSTGRESQL.

CLAUDE.md hard-won law 14: *"any code that catches a database error and
continues MUST be proved on PostgreSQL, not on the default suite."*
`apps/payments/returned_mail.mark_returned` catches the duplicate-envelope
`IntegrityError` and carries on, and since `DEF-PAY-6342` it ALSO asks customers
to raise `accounts.bad_address` inside the same transaction. SQLite has no
aborted-transaction state, so the green suite says nothing about whether the
flag write survives a duplicate earlier in the same stack. This does.

RUN — against a CLONE, never a shared database:

    eval "$(10-scripts/proof-db.sh clone badaddr --export)"
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      python3 ../10-scripts/def_pay_6342_postgres_proof.py

Everything it writes is ROLLED BACK at the end, so it can be run again.
`SBH_PROOF_TENANT` picks the tenant; it defaults to the first one.

  §1  the role — a superuser bypasses RLS and would make every figure vacuous
  §2  a letter to an account with NO mailing row is addressed to its premises,
      `source: service_address` (part 1)
  §3  a stack of three pieces inside ONE outer transaction — the second a
      duplicate of the first — writes two events, refuses the duplicate by the
      DATABASE, and still raises the flag on BOTH accounts afterwards
  §4  RED, deliberately: the same duplicate WITHOUT the inner savepoint poisons
      the transaction — law 14's own symptom — which is why the savepoint stays
  §5  the clerk's clear, in the same transaction: every open return resolved,
      the flag lowered, both audited
"""

import os
import sys
import uuid
from datetime import date
from pathlib import Path

import django

_BACKEND = Path(__file__).resolve().parents[1] / "06-backend"
if _BACKEND.is_dir() and str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.db import IntegrityError, connection, transaction  # noqa: E402

from apps.customers import models as customer_models  # noqa: E402
from apps.notifications import models as outbound  # noqa: E402
from apps.notifications import services as notification_services  # noqa: E402
from apps.payments import returned_mail  # noqa: E402
from apps.payments.collections_models import DeliveryReturnEvent  # noqa: E402
from core import audit as core_audit  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


print(f"vendor: {connection.vendor}")
if connection.vendor != "postgresql":
    sys.exit("REFUSED: this proof is meaningless on SQLite. Set DATABASE_URL.")

print("\n§1 · THE ROLE")
with connection.cursor() as cur:
    cur.execute(
        "select current_user, rolsuper, rolbypassrls from pg_roles where rolname = current_user"
    )
    who, is_super, bypasses = cur.fetchone()
    cur.execute("select id from tenants order by provisioned_at nulls last limit 1")
    first_tenant = cur.fetchone()[0]
print(f"  current_user={who} rolsuper={is_super} rolbypassrls={bypasses}")
check("the role cannot bypass RLS", not is_super and not bypasses)

TENANT = uuid.UUID(os.environ.get("SBH_PROOF_TENANT", str(first_tenant)))
PIN = notification_services.TemplatePin(
    code="bill_residential", template_id=uuid.uuid4(), version=1, language="en-US"
)
audit_rows: list = []
previous_sink = core_audit._sink
core_audit.set_audit_sink(audit_rows.append)


def a_letter(account_id):
    source_id = uuid.uuid4()
    notification_services.queue_document(
        source_type="invoice", source_id=source_id, channels=(), template=PIN, account_id=account_id
    )
    return outbound.OutboundMessage.objects.get(
        source_id=source_id, channel=outbound.CHANNEL_PRINT
    )


try:
    with core_tenancy.tenant_context(TENANT):
        with transaction.atomic():  # the OUTER transaction a job or a bulk caller holds
            mailing = customer_models.Address.objects.filter(
                tenant_id=TENANT, kind="mailing", deleted_at__isnull=True
            ).values("account_id")
            candidates = list(
                customer_models.Account.objects.filter(
                    tenant_id=TENANT, unit_id__isnull=False, bad_address=False
                )
                .exclude(pk__in=mailing)
                .order_by("account_no")[:2]
            )
            assert len(candidates) == 2, "the clone needs two unflagged accounts with no mailing row"
            a, b = candidates
            print(f"\n  accounts: {a.account_no} · {b.account_no} (no mailing row on either)")

            print("\n§2 · THE SERVICE-ADDRESS FALLBACK (part 1)")
            letter_a, letter_b = a_letter(a.pk), a_letter(b.pk)
            snap = letter_a.recipient_snapshot or {}
            check(
                "the letter is addressed to the premises",
                bool(letter_a.recipient_address) and letter_a.unavailable_reason is None,
                repr(letter_a.recipient_address),
            )
            check("and says which address", snap.get("source") == "service_address", repr(snap))

            print("\n§3 · A STACK WITH A DUPLICATE, INSIDE ONE TRANSACTION")
            results = returned_mail.mark_returned_bulk(
                pieces=(
                    {"account_id": a.pk, "outbound_message_id": letter_a.pk},
                    {"account_id": a.pk, "outbound_message_id": letter_a.pk},  # the double mark
                    {"account_id": b.pk, "outbound_message_id": letter_b.pk},
                ),
                returned_on=date(2026, 9, 8),
            )
            check(
                "created, refused-by-the-database, created",
                [r.created for r in results] == [True, False, True],
                repr([r.created for r in results]),
            )
            check(
                "the flag was raised for both accounts, the replay raised nothing",
                [r.flag_raised for r in results] == [True, False, True],
            )
            flags = dict(
                customer_models.Account.objects.filter(pk__in=[a.pk, b.pk]).values_list(
                    "account_no", "bad_address"
                )
            )
            check("both STORED flags read true afterwards", all(flags.values()), repr(flags))
            check(
                "two events, not three",
                DeliveryReturnEvent.objects.filter(account_id__in=[a.pk, b.pk]).count() == 2,
            )

            print("\n§4 · RED ON PURPOSE — the same duplicate with NO savepoint")
            with transaction.atomic():  # a savepoint that CONTAINS the damage for this demo
                try:
                    DeliveryReturnEvent.objects.create(
                        tenant_id=TENANT,
                        account_id=a.pk,
                        outbound_message_id=letter_a.pk,
                        returned_on=date(2026, 9, 8),
                    )
                except IntegrityError as exc:
                    print(f"  IntegrityError: {str(exc).splitlines()[0]}")
                    try:
                        DeliveryReturnEvent.objects.filter(account_id=a.pk).count()
                        check("the next statement is refused after an unguarded error", False)
                    except Exception as poisoned:  # noqa: BLE001 — this IS the proof
                        print(f"  {type(poisoned).__name__}: {str(poisoned).splitlines()[0]}")
                        check("the next statement is refused after an unguarded error", True)
                transaction.set_rollback(True)

            print("\n§5 · THE CLERK'S CLEAR, SAME TRANSACTION")
            cleared = returned_mail.clear_account(
                account_id=a.pk, resolution="verified_current", resolved_on=date(2026, 9, 9)
            )
            a.refresh_from_db()
            check("one return resolved, flag lowered", cleared["returns_resolved"] == 1)
            check("the STORED flag reads false", a.bad_address is False)
            actions = [row["action"] for row in audit_rows]
            for code in (
                "delivery.returned",
                "account.bad_address.flagged",
                "bad_address.cleared",
                "account.bad_address.cleared",
            ):
                check(f"audited: {code}", code in actions)

            transaction.set_rollback(True)  # leave the clone exactly as it was
finally:
    core_audit.set_audit_sink(previous_sink)

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} — " + "; ".join(FAILURES))
    sys.exit(1)
print("ALL PASSED on PostgreSQL — every write above was rolled back.")
