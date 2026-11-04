# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-6376 (the request fee is taken the way Record a payment
#           takes money: a posting date, a reference and a memo) ·
#           DEF-CUS-6374 (cash at that door needs an open till)
# Rules:    CLAUDE.md hard rule 2 · 4 (the receipt's evidence is frozen) · 5
#           (only the ledger writes journal lines) · 7 (audit) · hard-won law
#           14 (prove it on PostgreSQL) · BR-TEN-081 · PO 2026-09-23 §3.4
# Tests:    06-backend/tests/test_def_cus_6376_request_fee_like_record_payment.py
#           — its SQLite half. This file is the half SQLite cannot see.
# ───────────────────────────────────────────────────────
"""`DEF-CUS-6376` / `DEF-CUS-6374` — the money-path claims, PROVED ON POSTGRESQL.

Hard-won law 14: the default suite is in-memory SQLite, which has no triggers,
no row-level security and no aborted-transaction state. So four claims are made
here and nowhere else:

  §2  `payments/0042` froze the three new columns — the DEPLOYED function body,
      read back out of `pg_proc`.
  §3  cash with no open till is refused BEFORE anything is written, and the
      refusal does not poison an enclosing transaction (it is raised in Python
      before any statement fails, so the next query in the same transaction
      still runs).
  §4  with a till open, $70.00 posted for 21 September makes ONE balanced entry
      dated 2026-09-21 — `DR 70.0000 · CR 2400 70.0000` — and a receipt that
      says the same day.
  §5  hard rule 7: both audit rows carry the posting date and the memo.
  §6  the trigger refuses an UPDATE of each new column.

RUN — against a PRIVATE clone migrated to `payments/0042`, never a shared one:

    10-scripts/proof-db.sh clone reqfee --stale-ok
    cd 06-backend
    DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_reqfee?sslmode=disable" \\
    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      python3 manage.py migrate && python3 ../10-scripts/def_cus_6376_request_fee_pg_proof.py

It WRITES (a request, a till, a receipt, an entry), so give it a clone of its own.
Exits 1 on any FAIL.
"""

import json
import os
import sys
import uuid
from datetime import date
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

print("\n§2 · THE DEPLOYED FREEZE FREEZES THE THREE NEW COLUMNS")
with connection.cursor() as cur:
    cur.execute("select prosrc from pg_proc where proname = 'payments_counter_receipt_freeze'")
    body = cur.fetchone()[0]
for column in ("posted_on", "confirmation", "memo"):
    check(f"NEW.{column} is in the frozen list", f"NEW.{column} IS DISTINCT FROM" in body)

tenant = tenancy_models.Tenant.objects.get(subdomain=os.environ.get("SBH_PROOF_TENANT", "brazosbend"))
POSTING_DAY = date(2026, 9, 21)
MEMO = "Paid by her daughter"
CAPTURE = {
    "channel": "physical_form",
    "applicant_kind": "person",
    "applicant_name": f"Proof, Applicant {uuid.uuid4().hex[:6]}",
    "applicant_email": "proof@example.test",
    "address_as_given": "14 Willow Bend, Springfield",
}

with core_tenancy.tenant_context(tenant.id):
    # A staff user with NO till open — the refusal needs one, and the demo seed
    # may have left a till open for somebody.
    candidates = identity_models.User.objects.filter(tenant_id=tenant.id).order_by("created_at")
    user = None
    for one in candidates:
        probe = SimpleNamespace(id=one.id, pk=one.id, role="billing_clerk", user=one)
        if counters.open_counter_for(probe) is None:
            user = one
            break
    assert user is not None, "every staff user already has a till open"
    actor = SimpleNamespace(id=user.id, pk=user.id, role="billing_clerk", user=user)
    print(f"\n  tenant={tenant.subdomain}  clerk={user.email}")
    request = sr.create_request(actor, dict(CAPTURE))
    sr.add_fee_line(actor, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("70.00"))
    print(f"  request={request.request_no}  quoted 70.00")


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


def counter_entries() -> int:
    with core_tenancy.tenant_context(tenant.id):
        with connection.cursor() as cur:
            cur.execute("select count(*) from journal_entries where source_type = 'counter_receipt'")
            return cur.fetchone()[0]


print("\n§3 · NO TILL: CASH AND THE REQUEST'S 'cheque' ARE REFUSED, AND NOTHING IS WRITTEN")
entries_before = counter_entries()
with transaction.atomic():
    refused = post(amount="70.00", method="cash", receipt_no="RCP-PG-0016")
    check(
        "cash with no till → 422 payments.counter.till_required",
        refused.status_code == 422
        and refused.data.get("message_key") == "payments.counter.till_required",
        f"{refused.status_code} {refused.data.get('message_key')} {refused.data.get('br_ref')}",
    )
    # Law 14: the SAME transaction still answers a query — the refusal is a
    # Python raise before any statement, so nothing was aborted.
    with core_tenancy.tenant_context(tenant.id):
        still = cr_models.CounterReceipt.objects.filter(source_id=request.id).count()
    check("the enclosing transaction is not poisoned, and no receipt exists", still == 0)
cheque = post(amount="70.00", method="cheque", receipt_no="RCP-PG-0016")
check("'cheque' (the tender check) with no till → 422", cheque.status_code == 422)
with core_tenancy.tenant_context(tenant.id):
    row = sr.request_row(request.id)
    check("the request took nothing", row.fee_collected is None and not row.fee_receipt_no)
check("no journal entry was made", counter_entries() == entries_before, str(entries_before))

print("\n§4 · WITH A TILL: $70.00 POSTED FOR 21 SEPTEMBER BOOKS ON 21 SEPTEMBER")
with core_tenancy.tenant_context(tenant.id):
    centre = content_models.ServiceCentre.objects.filter(tenant_id=tenant.id).first()
    if centre is None:
        centre = content_models.ServiceCentre.objects.create(
            tenant=tenant, slug=f"proof-{uuid.uuid4().hex[:6]}", name="Proof window",
            address="101 Bend Road",
        )
    counters.open_counter(
        actor,
        service_centre_id=centre.pk,
        opening_float=Decimal("0.0000"),
        opened_at=timezone.now(),
    )
taken = post(
    amount="70.00",
    method="cash",
    receipt_no="RCP-PG-0016",
    posted_at=POSTING_DAY.isoformat(),
    memo=MEMO,
)
check("200, $70.00 collected", taken.status_code == 200, str(taken.data.get("collected")))
with core_tenancy.tenant_context(tenant.id):
    receipt = cr_models.CounterReceipt.objects.get(source_id=request.id)
    check("the receipt says 2026-09-21", receipt.posted_on == POSTING_DAY, str(receipt.posted_on))
    check("the receipt holds the memo", receipt.memo == MEMO)
    with connection.cursor() as cur:
        cur.execute(
            "select entry_date from journal_entries where id = %s",
            [str(receipt.collection_entry_id)],
        )
        entry_date = cur.fetchone()[0]
        check("the ledger entry is dated 2026-09-21", entry_date == POSTING_DAY, str(entry_date))
        cur.execute(
            "select a.code, l.side, l.amount from journal_lines l "
            "join ledger_accounts a on a.id = l.ledger_account_id "
            "where l.journal_entry_id = %s order by l.side",
            [str(receipt.collection_entry_id)],
        )
        legs = cur.fetchall()
    print(f"  legs: {legs}")
    debits = sum(amount for _code, side, amount in legs if side == "debit")
    credits = sum(amount for _code, side, amount in legs if side == "credit")
    check(
        "one balanced pair of 70.0000, the credit to 2400",
        debits == credits == Decimal("70.0000")
        and any(code == "2400" and side == "credit" for code, side, _ in legs),
        f"debits={debits} credits={credits}",
    )

print("\n§5 · HARD RULE 7: BOTH AUDIT ROWS CARRY THE DAY AND THE MEMO")
with core_tenancy.tenant_context(tenant.id):
    with connection.cursor() as cur:
        cur.execute(
            "select action, after from audit_log where entity_id in (%s, %s) "
            "and action in ('service_request.fee_collected', 'counter_receipt.collected')",
            [str(request.id), str(receipt.id)],
        )
        rows = cur.fetchall()
for action, after in rows:
    # `after` is JSON; the driver hands back a dict for jsonb and a str for text.
    after = json.loads(after) if isinstance(after, str) else (after or {})
    check(
        f"{action} carries posted_on and memo",
        after.get("posted_on") == "2026-09-21" and after.get("memo") == MEMO,
        f"posted_on={after.get('posted_on')} memo={after.get('memo')}",
    )
check("both audit rows exist", len(rows) == 2, str([action for action, _ in rows]))

print("\n§6 · THE FREEZE REFUSES AN UPDATE OF EACH NEW COLUMN")
# ⚠ **THE TENANT CONTEXT IS OUTSIDE THE ATOMIC BLOCK, AND THAT IS LAW 14 IN THIS
# FILE.** The first draft opened the context INSIDE it: the trigger's refusal
# aborted the transaction, the context's exit then ran a statement in it, and the
# exception caught here was *"current transaction is aborted"* — the refusal's
# own words masked by a second error. Rolled back first, reset second.
with core_tenancy.tenant_context(tenant.id):
    for column, value in (("posted_on", "2026-09-22"), ("confirmation", "X"), ("memo", "edited")):
        refusal = ""
        try:
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(
                        f"update counter_receipts set {column} = %s where id = %s",
                        [value, str(receipt.id)],
                    )
        except Exception as exc:  # noqa: BLE001 — the refusal IS the result
            refusal = str(exc).splitlines()[0]
        check(
            f"UPDATE {column} is refused by the database", "hard rule 4" in refusal, refusal[:90]
        )
    receipt.refresh_from_db()
    check(
        "…and the row still says what was taken",
        receipt.posted_on == POSTING_DAY and receipt.memo == MEMO,
        f"{receipt.posted_on} {receipt.memo}",
    )

print()
if FAILURES:
    print(f"{len(FAILURES)} FAIL: {FAILURES}")
    sys.exit(1)
print("ALL PASS")
