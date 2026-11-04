#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-136-BRC07 phase 2 — `P2.17`, the journey `J-PAY-counter-shift`:
#           *"08:55 open with a $200 float · seventeen payments in cash, cheque
#           and card · 17:30 count · close"*, and the blueprint's own note that
#           it *"ends on Finance → Deposits"*.
# Rules:    CLAUDE.md hard rule 1 (`app.tenant_id` before anything is counted) ·
#           hard rule 2 (money to four decimals) · hard rule 5 · hard rule 6 ·
#           `CR-136-BRC07` §3.4 (three tenders need a till; the other four keep
#           the system till) · hard-won law 14
# Journey:  08-qa/01-e2e/journeys/JPAYCOUNTERSHIFT-a-shift-at-the-counter.md —
#           this script is what that file's figures were MEASURED from.
# ───────────────────────────────────────────────────────
"""The whole shift, once, on a real database — so the journey states facts.

    10-scripts/proof-db.sh clone p2shift --stale-ok      (or reuse a clone)
    cd 06-backend && DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local \\
        python3 ../10-scripts/cr136_p2_17_counter_shift_readback.py

⚠ **THIS IS A READBACK, NOT A TEST.** It asserts nothing about what OUGHT to
happen; it performs the shift and PRINTS what each step left, including the
last step, which is where `P2.17` runs out of built product. A journey file
written from a plan rather than from a run is how `J19` reached step 1 and
found nothing to click (`DEF-112`).

⚠ **IT RUNS ON PostgreSQL BECAUSE THE DRAWER IS A MONEY PATH.** The SQLite
suite has no RLS, no raw CHECK constraints and no aborted-transaction state,
so a shift walked there proves the arithmetic and nothing about the till.
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

from django.db import connection  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.payments import bankrec_read, counters, ledger_seam, services  # noqa: E402
from apps.payments import bankrec_models as bankrec  # noqa: E402
from apps.payments import models as payment_models  # noqa: E402
from apps.payments.counter_session_models import CounterSession  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.tenancy import published_content_models as content_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

#: The blueprint's own per-tender totals for this shift (p053's 3·2 tiles).
#: **Seventeen payments**, and the card three are here on purpose: §3.4 leaves
#: `card` on the system till, so the drawer holds only the first two rows.
#: ⚠ **EVERY AMOUNT IS TWO DECIMAL PLACES, AND THAT IS A RULE RATHER THAN A
#: TIDY FIXTURE.** `BR-LED-025` (PO 2026-08-12, verbatim *"Refuse and make the
#: caller round"*) makes the ledger REFUSE a posting carrying more than two,
#: and it refuses the whole payment with it. A first draft of this file used
#: `160.5750` a cheque to reach the drawn `1284.60` and `record_payment` raised
#: on the FIRST cheque — which is the product being right and the fixture being
#: wrong, and is worth recording because a journey written from that draft
#: would have promised a walk nobody can take.
SHIFT = (
    ("cash", [Decimal("85.00")] * 6),  # 6 × 85.00 = 510.00
    ("check", [Decimal("160.58")] * 7 + [Decimal("160.54")]),  # = 1284.60
    ("card", [Decimal("134.05")] * 3),  # 3 × 134.05 = 402.15
)
FLOAT = Decimal("200.0000")


def guc(cursor, tenant_id) -> None:
    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def actor_for(user):
    from types import SimpleNamespace

    from apps.identity import models as identity_models

    membership = (
        identity_models.TenantMembership.objects.filter(user=user).select_related("role").first()
    )
    role = getattr(getattr(membership, "role", None), "code", None) or "system_admin"
    return SimpleNamespace(id=user.pk, pk=user.pk, user=user, role=role)


def main() -> int:
    if connection.vendor != "postgresql":
        raise SystemExit(
            f"the connection is {connection.vendor!r}. A drawer walked on SQLite proves the "
            "arithmetic and nothing about the till (CLAUDE.md hard-won law 14)."
        )
    tenant = tenancy_models.Tenant.objects.order_by("created_at").first()
    with connection.cursor() as cur:
        guc(cur, tenant.pk)
    core_tenancy.set_current_tenant(tenant.pk)

    from apps.identity import models as identity_models

    owner = identity_models.User.objects.filter(tenant=tenant).order_by("created_at").first()
    if owner is None:
        owner = identity_models.User.objects.create(
            tenant=tenant, email=f"shift-{uuid.uuid4().hex[:8]}@example.test", full_name="Shift clerk"
        )
    centre = content_models.ServiceCentre.objects.filter(tenant=tenant).first()
    if centre is None:
        centre = content_models.ServiceCentre.objects.create(
            tenant=tenant, slug=f"shift-{uuid.uuid4().hex[:6]}", name="Main office", address="1 Road"
        )
    actor = actor_for(owner)
    print(f"tenant {tenant.subdomain} · clerk {owner.email} · counter {centre.name}\n")

    # Leave this person with no open till — by CLOSING, never by deleting: a
    # till that has taken money is protected by `DepositBatch.session`.
    CounterSession.objects.filter(tenant=tenant, owner=owner, closed_at__isnull=True).update(
        closed_at=timezone.now(), closed_by=owner, close_kind="forced"
    )

    # ── STEP 1 · 08:55, open with a $200 float ─────────────────────────────
    opened = counters.open_counter(
        actor, service_centre_id=centre.pk, opening_float=FLOAT, opened_at=timezone.now()
    )
    session = opened.session
    print("STEP 1  open")
    print(f"        counter   {session.code if hasattr(session, 'code') else session.pk}")
    print(f"        float     {session.opening_float}")
    print(f"        batch     {opened.batch.code} ({opened.batch.method.code}), created={opened.batch_created}")

    # ── STEP 2 · seventeen payments, in three tenders ──────────────────────
    from apps.customers import models as customer_models

    accounts = list(customer_models.Account.objects.filter(tenant=tenant).order_by("pk")[:17])
    if not accounts:
        raise SystemExit("this database holds no accounts — run seed_demo/load_sample_data first")
    print("\nSTEP 2  seventeen payments")
    taken = []
    index = 0
    for method_code, amounts in SHIFT:
        for each in amounts:
            account = accounts[index % len(accounts)]
            index += 1
            recorded = services.record_payment(
                actor,
                account_id=account.pk,
                amount=each,
                posted_at=timezone.now(),
                cleared_at=timezone.now(),
                method_code=method_code,
                idempotency_reference=uuid.uuid4(),
                # ⚠ **THE CARD THREE ARE RECORDED WITHOUT A TILL, AND THE
                # SERVICE REFUSES BY NAME IF YOU TRY.** §3.4: only cash,
                # cheques and money orders pass through a person's hands. A
                # first draft passed the till for all seventeen and
                # `record_payment` refused the FIRST card — *"putting a card
                # swipe in a drawer would make the close count disagree with
                # what is physically there"*. That refusal is the product
                # being right, and it is a STEP of this journey rather than a
                # fixture detail.
                counter_session_id=(
                    session.pk if method_code in ("cash", "check", "money_order") else None
                ),
            )
            taken.append(payment_models.Payment.objects.get(pk=recorded.payment_id))
    for method_code, amounts in SHIFT:
        rows = [p for p in taken if p.method.code == method_code]
        on_till = [p for p in rows if p.counter_session_id == session.pk]
        batched = {p.deposit_batch_id for p in rows if p.deposit_batch_id is not None}
        total = sum((p.amount for p in rows), Decimal("0"))
        print(
            f"        {method_code:<6} {len(rows)} payment(s) {total}  "
            f"on THIS till: {len(on_till)}  distinct batches: {len(batched)}"
        )

    # ── STEP 2b · what the till itself reads (3·2's tiles) ─────────────────
    split = counters.running_split(CounterSession.objects.get(pk=session.pk))
    print("\nSTEP 2b the till's own running split (3·2) — the key is `by_method`")
    for method in split.get("by_method", []):
        print(
            f"        {str(method.get('method_code')):<6} system_total={method.get('system_total')}  "
            f"countable={method.get('countable')}  payments={method.get('payment_count')}"
        )
    print(f"        taken={split.get('taken')}  float={split.get('opening_float')}  "
          f"countable_expected={split.get('countable_expected')}")

    # ── STEP 3 · 17:30, count and close ────────────────────────────────────
    # ⚠ **THE FLOAT IS ALREADY INSIDE THE CASH LINE** (p056, built as drawn):
    # a clerk counts what is in the drawer and the float is in the drawer. So
    # counting EXACTLY is each countable tender's own `system_total`, with no
    # arithmetic on this side at all.
    counted = {
        method["method_code"]: method["system_total"]
        for method in split.get("by_method", [])
        if method.get("countable")
    }
    sealed = counters.close_counter(
        actor,
        session_id=session.pk,
        counted_totals=counted,
        closed_at=timezone.now(),
    )
    print("\nSTEP 3  close, counted exactly")
    print(f"        counted    {counted}")
    print(f"        difference {sealed.difference}")
    print(f"        close_kind {sealed.session.close_kind}")
    print(f"        posted     {sealed.posting_key is not None}  (a zero difference posts nothing)")

    # ── STEP 4 · Finance → Deposits: what the row actually says ────────────
    batches = list(bankrec.DepositBatch.objects.filter(tenant=tenant, session=session))
    listed = bankrec_read.batch_list()
    by_code = {row["code"]: row for row in listed["rows"]}
    print("\nSTEP 4  Finance -> Deposits (`GET /deposit-batches`, S37)")
    for batch in sorted(batches, key=lambda b: b.code):
        row = by_code.get(batch.code)
        print(
            f"        {batch.code:<18} tender={getattr(batch.method, 'code', None):<6} "
            f"recorded={batch.recorded_total} status={batch.status} "
            f"on the Deposits list: {'YES' if row is not None else 'NO'}"
        )
        if row is not None:
            print(f"                           row keys served: {sorted(row.keys())}")
    print(
        "\n        ⚠ what the row does NOT carry: anything naming the TILL or the CLERK. "
        "`P2.10` is that column and it is NOT STARTED."
    )

    # ── the books, for completeness ────────────────────────────────────────
    from apps.ledger import models as ledger_models

    drawer_lines = ledger_models.JournalLine.objects.filter(
        tenant=tenant, source_type=ledger_seam.SOURCE_COUNTER_SESSION, source_id=session.pk
    ).count()
    print(f"\n        journal lines for this counter session: {drawer_lines}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
