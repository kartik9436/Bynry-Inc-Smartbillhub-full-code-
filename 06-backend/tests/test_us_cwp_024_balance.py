# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-024 (EP-CWP-04) — the balance read. Screens: CWP-018's
#           consequence panel · CWP-022's lead tile · CWP-023
# Rules:    BR-CWP-015 (separately, and totalled for information — NEVER merged
#           into one invoice) · BR-CWP-041 (nothing above the issued bill) ·
#           BR-CWP-043 (owing is a separate column from amount; part-paid is a
#           third state) · BR-CWP-047 (never cached) · CLAUDE.md hard rule 2
# Tests:    this file
# Impacts:  apps/portal/seams/payments_seam.py · apps/portal/api.py
# ───────────────────────────────────────────────────────
"""The four figures `US-CWP-024` names, each computed by the code that ships.

⚠ **NOT ONE FIGURE BELOW IS ASSERTED AGAINST A CONSTANT THIS FILE COMPUTED.**
`872.82` is the sum of four bills this fixture wrote and the READ added up;
`102.18` is what the seam makes of a `142.18` bill with `40.00` allocated to
it. If the arithmetic moved, these go red — which is the only thing that makes
them worth having.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from apps.portal.seams import payments_seam
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    LANDLORD_BILLS,
    LANDLORD_TOTAL,
    MARIA_EMAIL,
    MARIA_PASSWORD,
    PART_PAID_OPEN,
    an_issued_bill,
    elm_street_account,
    enrol_maria,
    switch_on,
)

AUGUST = date(2026, 8, 26)
DUE = date(2026, 9, 14)


@pytest.mark.django_db
def test_us_cwp_024_tc1_one_bill_is_owed_in_full(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total="142.1800", issued_on=AUGUST, due_on=DUE
        )
        balance = payments_seam.account_balance(account.pk)
    assert balance["owing"] == "142.1800"
    assert balance["bills_open"] == "142.1800"
    assert balance["due_on"] == DUE.isoformat()
    assert balance["open_bill_count"] == 1


@pytest.mark.django_db
def test_us_cwp_024_tc3_a_part_paid_bill_is_neither_paid_nor_unpaid(pine_hill, sarah):
    """`BR-CWP-043` — `$142.18` with `$40.00` against it owes **`$102.18`**.

    ⚠ **AND THE BILL IS STILL THERE.** A read that dropped a part-paid bill
    would show the customer nothing owing on a bill they still owe money on;
    one that showed it whole would ask them to pay twice.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total="142.1800", issued_on=AUGUST, due_on=DUE
        )
        allocate(pine_hill, account, bill, "40.0000")
        balance = payments_seam.account_balance(account.pk)
    assert balance["owing"] == PART_PAID_OPEN, balance
    assert balance["open_bill_count"] == 1, "a part-paid bill is still an open bill"


def allocate(tenant, account, invoice, amount: str):
    """One payment, allocated against one bill — payments' own two rows."""
    from datetime import UTC, datetime

    from apps.payments import models as payment_models

    payment = payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        amount=Decimal(amount),
        currency=getattr(account, "currency", None) or "USD",
        status=payment_models.PAYMENT_CLEARED,
        posted_at=datetime(2026, 8, 30, 10, 0, tzinfo=UTC),
    )
    payment_models.Allocation.objects.create(
        tenant=tenant, payment=payment, invoice=invoice, amount=Decimal(amount)
    )
    return payment


@pytest.mark.django_db
def test_us_cwp_024_tc2_four_accounts_total_872_82_and_are_never_merged(pine_hill, sarah):
    """`BR-CWP-015`. Four rows, one total, and **no field that could be paid**.

    The `$0.00` account is one of the four rather than an absence: an account
    that owes nothing is a property the customer still holds, and hiding it
    would make the total disagree with the switcher.
    """
    switch_on(pine_hill, sarah)
    accounts = four_accounts(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        for account, total in zip(accounts, LANDLORD_BILLS):
            if Decimal(total) > 0:
                an_issued_bill(
                    pine_hill,
                    account,
                    number=f"BL-2608-{str(account.account_no)[-4:]}",
                    total=total,
                    issued_on=AUGUST,
                    due_on=DUE,
                )
        summary = payments_seam.balance_summary([a.pk for a in accounts], as_of=AUGUST)
    assert summary["account_count"] == 4, summary
    assert summary["total_owing"] == LANDLORD_TOTAL, summary["total_owing"]
    assert [row["owing"] for row in summary["accounts"]].count("0.0000") == 1
    # ⚠ NOTHING HERE IS PAYABLE. There is no merged invoice, no single amount,
    # and no reference a payment could be posted against.
    assert not {"invoice", "invoice_no", "pay_reference", "amount_due"} & set(summary)


def four_accounts(tenant, actor):
    """The landlord's four, built on the units the fixture ALREADY seeds.

    ⚠ **THE FIRST DRAFT CREATED UNITS `B`, `C` AND `D` FROM SCRATCH AND COULD
    NOT.** `seed_street` gives `1408 Elm St` its units `A`, `B` and `Common` and
    NO `services_available`; wave C's `seed_priced_addresses` is what puts water,
    a plan and an occupant on `A`. So a unit created here asking for `water`
    is asking a premises that offers none, and a `D` that the street's own
    fixture never drew is a shape the product would never see.

    **Using the seeded units instead is not a workaround — it is the demo
    script's own landlord**: `A`, `B` and the **common areas** at 1408 Elm St,
    plus one more at `31 Palm Ct`, which wave C seeds priced and connected. Four
    accounts across two buildings, which is what a landlord actually holds, and
    the master over the common areas is one more flat entry (`BR-CWP-013`).
    """
    from apps.customers import models as customers_models
    from apps.customers import services as customers_services
    from apps.metering import models as metering_models

    first = elm_street_account(tenant, actor)
    made = [first]
    with tenant_context(tenant.id):
        premises_id = first.premises_id or first.unit.premises_id
        plan_id = first.unit.rate_plan_id
        wanted = [
            unit
            for unit in metering_models.Unit.objects.filter(premises_id=premises_id).order_by("label")
            if unit.pk != first.unit_id
        ]
        palm = (
            metering_models.Unit.objects.filter(premises__address_line=sample_data.PALM_CT)
            .order_by("label")
            .first()
        )
        if palm is not None:
            wanted.append(palm)
        for unit in wanted[:3]:
            existing = customers_models.Account.objects.filter(unit_id=unit.pk).first()
            if existing is not None:
                made.append(existing)
                continue
            if unit.rate_plan_id is None and plan_id is not None:
                sample_data._put_on_plan(actor, unit.pk, str(plan_id), ["water"])
            created = customers_services.create_account(
                actor,
                {
                    "unit_id": str(unit.pk),
                    "account_type": "residential",
                    "opened_at": "2026-01-05",
                    "contact": {"full_name": "Elm Street Holdings", "phone": "(512) 555-0199"},
                    # ⚠ **A COMPANY NEEDS ITS TAX ID AND A PHONE IS NOT ENOUGH**
                    # (`BR-CUS-1024`, PO 2026-09-01: *"if it is Company then we
                    # ask for Tax ID"*). An earlier draft passed a phone and
                    # `create_account` refused it by name — the door doing its
                    # job, and the reason a fixture goes through the door.
                    "customer": {
                        "display_name": "Elm Street Holdings",
                        "kind": "company",
                        "identity": {"tax_id": "74-1234567"},
                    },
                    # ⚠ **THE PLAN ASKS A DEPOSIT, SO THE ACCOUNT MUST ANSWER
                    # IT** — `DEF-CWP-6424`'s refusal, one fixture along, and
                    # this landlord opens THREE accounts on that same priced
                    # plan. Since `39d6ee638` (2.348.0, `OQ-CUS-12620` (a))
                    # *"No" only when the plan asks none*, and the plan prices a
                    # `$150.00` residential deposit, an open with no `deposit`
                    # block is refused by `customers.deposit.planAsksDeposit`.
                    # `required` without `take_now` is the plan's figure
                    # ASSESSED and left for the first bill: **no money moves**,
                    # which is why the `872.82` these cases assert does not.
                    "deposit": {"decision": "required"},
                },
            )
            customers_services.activate_account(actor, created["id"])
            made.append(customers_models.Account.objects.get(pk=created["id"]))
    assert len(made) == 4, (
        f"the landlord fixture built {len(made)} account(s), not four — the seeded units at "
        f"{sample_data.ELM_ST} and {sample_data.PALM_CT} are what it stands on"
    )
    return made


@pytest.mark.django_db
def test_us_cwp_024_tc5_the_balance_endpoint_never_lets_a_browser_cache_it(pine_hill, sarah):
    """`BR-CWP-047` — *a credit that was real on Tuesday can be spent by
    Thursday*. Both halves: no cache in the code, and `no-store` on the wire."""
    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    response = client.get(f"/api/{pine_hill.subdomain}/portal/balance/summary")
    assert response.status_code == 200, response.content
    assert "no-store" in response["Cache-Control"]


@pytest.mark.django_db
def test_us_cwp_024_tc6_an_account_outside_the_set_answers_the_same_404_as_one_that_does_not_exist(
    pine_hill, sarah
):
    """`BR-CWP-010` — both halves in the query, and the two refusals are the
    SAME so the set cannot be enumerated by watching which one comes back."""
    import re
    import uuid

    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    others = four_accounts(pine_hill, sarah)[1:]
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    somebody_else = client.get(
        f"/api/{pine_hill.subdomain}/portal/accounts/{others[0].pk}/balance"
    )
    nobody = client.get(f"/api/{pine_hill.subdomain}/portal/accounts/{uuid.uuid4()}/balance")
    assert somebody_else.status_code == nobody.status_code == 404

    # ⚠ **THIS COMPARED RAW BYTES UNTIL 2026-09-04 AND COULD NEVER PASS
    # (`DEF-CWP-3761`).** Every error envelope carries `trace_id = uuid.uuid4().hex`
    # (`core/errors.py`), a fresh 32-hex string per REQUEST, so two refusals are
    # byte-identical only if the same request is compared with itself. The wave
    # recorded this case as *unproved*; it was **unprovable as written**, which
    # is the worse of the two and the reason it gets a defect row rather than a
    # tweak.
    #
    # ⚠ **AND THE PROPERTY THE RULE WANTS IS NOT BYTE-EQUALITY — IT IS
    # INDISTINGUISHABILITY.** A random id present in BOTH bodies tells an
    # attacker nothing about which case occurred; it is noise by construction.
    # What WOULD be a tell is the field appearing in one and not the other, or
    # differing in shape, so both are asserted below. Byte-equality is a
    # stronger claim than the rule makes and, here, an impossible one.
    import json

    left, right = json.loads(somebody_else.content), json.loads(nobody.content)
    for body in (left, right):
        assert re.fullmatch(r"[0-9a-f]{32}", body["trace_id"]), (
            f"trace_id {body['trace_id']!r} is not the usual shape — a refusal whose trace id "
            "LOOKS different is as much a tell as one that is absent (BR-CWP-010)"
        )
    assert left.pop("trace_id") != right.pop("trace_id"), (
        "two refusals shared a trace id — it is meant to be per-request, and a REUSED one "
        "would correlate the two requests instead of separating them"
    )
    assert left == right, (
        f"{left!r} vs {right!r} — with the per-request trace id set aside, an id in the "
        "utility and an id nowhere must be refused identically (BR-CWP-010)"
    )
