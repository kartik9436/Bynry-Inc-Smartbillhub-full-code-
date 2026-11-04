# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-6455 — the counter took part of a service request's
#           application fee; PO ruling 2026-09-24 P4 (`OQ-CUS-12624`):
#           *"all or waived"*.
# Rules:    BR-CUS-090 (stamped 2026-09-24) · CLAUDE.md hard rule 2 (money is a
#           decimal string, 4 dp stored) · hard rule 7 (audit) · hard-won law 14
#           (a refusal inside an enclosing transaction, proved on PostgreSQL)
# Tests:    06-backend/tests/test_po20260921_application_fee_optional.py
#           (`test_oq_cus_12624_…`) and test_cr031_service_request_api.py — the
#           SQLite half. This file is the half SQLite cannot see.
# ───────────────────────────────────────────────────────
"""`DEF-CUS-6455` — a short application fee is REFUSED, PROVED ON POSTGRESQL.

Hard-won law 14: the default suite is in-memory SQLite, which has no aborted-
transaction state. So the claim that matters is made here: **the refusal is a
Python raise before any statement fails, so an ENCLOSING transaction is still
usable afterwards and nothing was written.** Then the whole fee is taken in
that same transaction, which could not happen if the refusal had poisoned it.

  §1  the role is neither a superuser nor bypassing RLS
  §2  quoted $130.00, $25.00 offered, INSIDE an outer `transaction.atomic()` →
      422 `customers.serviceRequest.feeTakeInFull` naming `130.0000 USD`; the
      SAME transaction then answers a query and holds no receipt
  §3  still inside it: $150.00 is refused the same way
  §4  still inside it: $130.00 is taken — one receipt, one balanced
      `130.0000` pair, one audit row — and the outer block COMMITS

RUN — against a PRIVATE clone migrated to your tree, never a shared one:

    10-scripts/proof-db.sh clone rulings --stale-ok
    cd 06-backend
    DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_rulings?sslmode=disable" \\
    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      python3 manage.py migrate && python3 ../10-scripts/def_cus_6455_whole_fee_pg_proof.py

It WRITES (a request, a till, a receipt, an entry). Exits 1 on any FAIL.
"""

import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import django

_BACKEND = Path(__file__).resolve().parents[1] / "06-backend"
if _BACKEND.is_dir() and str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.db import connection, transaction  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.customers import service_request_api as api  # noqa: E402
from apps.customers import service_request_service as sr  # noqa: E402
from apps.identity import models as identity_models  # noqa: E402
from apps.payments import counter_receipt_models as cr_models  # noqa: E402
from apps.payments import counters  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.tenancy import published_content_models as content_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402
from tests.fee_quote_helpers import quote_fee  # noqa: E402
from tests.test_us_ten_helpers import api_call  # noqa: E402

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
print(f"  current_user={who} rolsuper={is_super} rolbypassrls={bypasses}")
check("not a superuser and not bypassing RLS", not is_super and not bypasses)

tenant = tenancy_models.Tenant.objects.get(subdomain=os.environ.get("SBH_PROOF_TENANT", "brazosbend"))
CAPTURE = {
    "channel": "physical_form",
    "applicant_kind": "person",
    "applicant_name": f"Proof, Whole Fee {uuid.uuid4().hex[:6]}",
    "applicant_email": "proof@example.test",
    "address_as_given": "14 Willow Bend, Springfield",
}
RECEIPT = f"RCP-PG-{uuid.uuid4().hex[:6].upper()}"

with core_tenancy.tenant_context(tenant.id):
    # A clerk with a till OPEN — the refusal proved here is the amount, not
    # the till (`DEF-CUS-6374` is `def_cus_6376_request_fee_pg_proof.py`'s).
    user = identity_models.User.objects.filter(tenant_id=tenant.id).order_by("created_at").first()
    actor = SimpleNamespace(id=user.id, pk=user.id, role="billing_clerk", user=user)
    if counters.open_counter_for(actor) is None:
        centre = content_models.ServiceCentre.objects.filter(tenant_id=tenant.id).first()
        if centre is None:
            centre = content_models.ServiceCentre.objects.create(
                tenant=tenant, slug=f"proof-{uuid.uuid4().hex[:6]}", name="Proof window",
                address="101 Bend Road",
            )
        counters.open_counter(
            actor, service_centre_id=centre.pk, opening_float=Decimal("0.0000"),
            opened_at=timezone.now(),
        )
    request = sr.create_request(actor, dict(CAPTURE))
    # `DEF-CUS-6416`: the server prices a line from the tenant's catalogue, so
    # the proof prices its OWN code there first (a private clone — nothing else
    # reads it) and quotes BR-CUS-090's $130.00 as one line through the door.
    quote_fee(actor, request.id, charge_code="CC-PROOF6455", unit_amount=Decimal("130.00"))
    quoted = sr.fee_total_to_collect(request.id)["quoted"]
print(f"  tenant={tenant.subdomain}  clerk={user.email}  request={request.request_no}  quoted={quoted}")
check("the quote is $130.00", quoted == Decimal("130.0000"), str(quoted))


def post(**body):
    return api_call(
        api.service_request_fee_collection,
        "post",
        f"/api/{tenant.subdomain}/service-requests/{request.id}/fee-collection",
        user=user,
        role="billing_clerk",
        tenant=tenant,
        data=body,
        request_id=str(request.id),
    )


def receipts() -> int:
    with core_tenancy.tenant_context(tenant.id):
        return cr_models.CounterReceipt.objects.filter(source_id=request.id).count()


committed = False
with transaction.atomic():  # ← THE ENCLOSING TRANSACTION (law 14)
    print("\n§2 · $25.00 OF $130.00, INSIDE AN OUTER TRANSACTION → REFUSED, NOTHING WRITTEN")
    short = post(amount="25.00", method="cash", receipt_no=RECEIPT)
    params = short.data.get("params") or {}
    check(
        "422 customers.serviceRequest.feeTakeInFull",
        short.status_code == 422
        and short.data.get("message_key") == "customers.serviceRequest.feeTakeInFull"
        and short.data.get("code") == "BIZ-COMPLETENESS",
        f"{short.status_code} {short.data.get('code')} {short.data.get('message_key')}",
    )
    check(
        "…naming the whole fee, 130.0000 USD",
        params.get("amount") == "130.0000" and params.get("currency") == "USD",
        str(params),
    )
    # The SAME transaction still answers — a poisoned one raises here.
    check("the enclosing transaction answers a query; no receipt exists", receipts() == 0)
    with core_tenancy.tenant_context(tenant.id):
        row = sr.request_row(request.id)
    check("the request took nothing", row.fee_collected is None and not row.fee_receipt_no)

    print("\n§3 · $150.00 — MORE THAN THE FEE IS REFUSED THE SAME WAY")
    over = post(amount="150.00", method="cash", receipt_no=RECEIPT)
    check(
        "422 feeTakeInFull naming 130.0000",
        over.status_code == 422
        and (over.data.get("params") or {}).get("amount") == "130.0000",
        f"{over.status_code} {over.data.get('params')}",
    )

    print("\n§4 · $130.00, IN THE SAME TRANSACTION → TAKEN AND BOOKED ONCE")
    whole = post(amount="130.00", method="cash", receipt_no=RECEIPT)
    check(
        "200, $130.00 collected, $0.00 outstanding",
        whole.status_code == 200
        and whole.data.get("collected", {}).get("display") == "130.00"
        and whole.data.get("outstanding", {}).get("display") == "0.00",
        f"{whole.status_code} {whole.data.get('collected')} {whole.data.get('outstanding')}",
    )
    with core_tenancy.tenant_context(tenant.id):
        receipt = cr_models.CounterReceipt.objects.get(source_id=request.id)
        with connection.cursor() as cur:
            cur.execute(
                "select l.side, l.amount from journal_lines l where l.journal_entry_id = %s",
                [str(receipt.collection_entry_id)],
            )
            legs = cur.fetchall()
            cur.execute(
                "select count(*) from audit_log where entity_id = %s "
                "and action = 'service_request.fee_collected'",
                [str(request.id)],
            )
            audits = cur.fetchone()[0]
    debits = sum(a for side, a in legs if side == "debit")
    credits = sum(a for side, a in legs if side == "credit")
    check("one receipt of 130.0000", receipt.amount == Decimal("130.0000"), str(receipt.amount))
    check(
        "one balanced pair of 130.0000",
        len(legs) == 2 and debits == credits == Decimal("130.0000"),
        f"{legs}",
    )
    check("exactly one fee_collected audit row (the refusals wrote none)", audits == 1, str(audits))
    committed = True
check("the outer transaction COMMITTED", committed and receipts() == 1)

print()
if FAILURES:
    print(f"{len(FAILURES)} FAIL: {FAILURES}")
    sys.exit(1)
print("ALL PASS")
