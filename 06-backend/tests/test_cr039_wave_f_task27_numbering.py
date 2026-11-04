# ── Trace ──────────────────────────────────────────────
# Story:    CR-039 wave F task 27 — "all of it on the platform side of the
#           boundary with its own numbering", and task 25's other half
# Rules:    PO 2026-08-27, verbatim: *"when utility will do cofiguration, data
#           migrton by themself then it is self serve and we dont have to
#           implment it - how you want to handle it, youc anhave 0 month
#           implmentaiton"* (the MODELLING delegated; the row is the build's
#           choice, decision log 2026-08-27) · PO 2026-08-27: *"it is duration
#           of implmentation project"* · BR-TEN-035 (a number is allocated
#           inside the transaction that creates the record) · CLAUDE.md hard
#           rule 2 (money 4dp stored) · hard rule 7 (every money action audits)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""CR-039 wave F — the column that shipped without its writer.

**MEASURED BEFORE ANYTHING WAS WRITTEN, on the tip.** Tasks 24–27 landed the
three models and migration `tenancy/0021` on 2026-08-27 and **nothing else**:
`grep` finds `ImplementationOrder` in exactly three places — the model, the
migration and one test file. No service, no allocator, no route, no screen, and
`implementation_orders.order_no` is a nullable column **no line of code has ever
written**. Its own docstring already says what it should hold — *"the
platform-side reference a person quotes — `IMPL-26-0001`. Its own series, on its
own side of the boundary (task 27)"* — which is task 27 describing a thing that
does not exist.

That is the exact pattern this repo has a name for: a column shipped ahead of
its writer (`DEF-920`). It is a good pattern — the schema lands first and the
format lands when it is ruled — and it is only good until somebody finishes it.

**WHAT IS BUILT HERE AND WHAT IS DELIBERATELY NOT.** Built: the platform series,
the allocator, the unique index that makes "no two orders share a number" true
rather than hoped, and the zero-month order the self-serve signup writes. NOT
built and NOT guessed: any price other than the `0.00` a self-serve order carries
by definition (the PO gave the SHAPE, not a figure — decision log 2026-08-27),
any add-on row (the catalogue is empty by ruling), and any screen (see `OQ-610`).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.tenancy import models, platform_numbering, services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant

pytestmark = pytest.mark.django_db


def _payload(subdomain: str, email: str):
    payload = brazosbend_payload()
    payload["subdomain"] = subdomain
    payload["owner"] = {**payload["owner"], "email": email}
    return payload


def test_wave_f27__a_new_tenant_carries_a_QUOTABLE_implementation_reference():
    """The whole of task 27 in one assertion: the number exists, and it is the
    one the model's own docstring named.

    RED-PROVED before the fix, verbatim:

        E   AssertionError: the tenant has no implementation order at all
            assert 0 == 1
    """
    tenant, _ = provisioned_tenant()
    orders = list(models.ImplementationOrder.objects.filter(tenant=tenant))
    assert len(orders) == 1, "the tenant has no implementation order at all"
    order = orders[0]
    assert order.order_no == f"IMPL-{date.today().year % 100:02d}-0001", (
        f"the first order of the year is numbered {order.order_no!r}; the model's "
        "own docstring names IMPL-26-0001"
    )


def test_wave_f27__that_order_is_SELF_SERVE_and_the_zero_is_the_ruling():
    """PO 2026-08-27: *"youc anhave 0 month implmentaiton"*.

    ⚠ **A ROW AND NO ROW ARE DIFFERENT THINGS TO A REPORT**, which is the whole
    reason the build chose a row over an absence. This is the assertion that
    makes *"how many customers are self-serve?"* answerable in one query — and
    the one that fails if a later lane "simplifies" the row away again.

    ⚠ **AND `$0.00` IS NOT A PRICE THIS BUILD CHOSE.** Self-serve is the case
    where the utility does its own configuration and migration, so there is no
    engagement to charge for. The PO gave the SHAPE and not the figure (decision
    log 2026-08-27), so a NON-ZERO self-serve price is a change, not a
    correction — and this test is where that shows up.
    """
    tenant, _ = provisioned_tenant()
    order = models.ImplementationOrder.objects.get(tenant=tenant)
    assert order.duration_months == 0
    assert order.is_self_serve is True
    assert order.price == Decimal("0.0000")
    assert order.currency == "USD"
    assert order.instalments == 1


def test_wave_f27__the_second_tenant_of_the_year_gets_the_second_number():
    """A series is only a series if it counts. Two real provisionings, not two
    calls to the allocator, because what has to hold is that the SIGNUP path
    allocates — an allocator nobody calls is the state this task started in.
    """
    first, _ = provisioned_tenant()
    second, _ = provisioned_tenant(_payload("silvercreek2", "owner2@example.com"))
    yy = f"{date.today().year % 100:02d}"
    numbers = sorted(
        models.ImplementationOrder.objects.filter(tenant__in=[first, second]).values_list(
            "order_no", flat=True
        )
    )
    assert numbers == [f"IMPL-{yy}-0001", f"IMPL-{yy}-0002"], numbers


def test_wave_f27__no_order_can_exist_without_its_number():
    """BR-TEN-035's shape, applied to a platform record: the number is allocated
    inside the transaction that creates the row, so there is no instant in which
    an order exists unnumbered — the same guarantee `transfers.transfer_no` and
    `disconnect_cases.case_no` were built with (CR-039 wave D).
    """
    provisioned_tenant()
    assert not models.ImplementationOrder.objects.filter(order_no__isnull=True).exists()
    assert not models.ImplementationOrder.objects.filter(order_no="").exists()


def test_wave_f27__the_database_refuses_a_duplicate_number():
    """The index is what makes uniqueness TRUE rather than hoped.

    Two signups racing each read the same maximum and would otherwise both write
    `IMPL-26-0001`. The allocator retries on exactly this error, so without the
    constraint the retry has nothing to catch and the race is silent.

    ⚠ **PROVED BY ATTEMPTING IT**, not by reading the migration — the wave F
    lane's own note about its two CHECK constraints, which were raw `ALTER
    TABLE` in their first draft and silently did nothing under sqlite.
    """
    tenant, _ = provisioned_tenant()
    taken = models.ImplementationOrder.objects.get(tenant=tenant).order_no
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            models.ImplementationOrder.objects.create(
                tenant=tenant, duration_months=6, order_no=taken
            )


def test_wave_f27__the_platform_series_is_NOT_one_of_the_tenants_own():
    """Task 27's boundary, asserted structurally.

    The model's docstring is explicit: this number is **Bynry's**, not the
    tenant's — *"a tenant's own numbering is the tenant's to configure"*. A tenant
    that renamed its series on Settings → Numbering must not be able to change
    what its implementation order is called, and a fresh tenant's catalogue must
    not grow a 30th row it cannot meaningfully edit.
    """
    from core import numbering as core_numbering

    catalogue = set(core_numbering.KNOWN_SERIES)
    formats = {fmt for _group, fmts in core_numbering.SERIES_CATALOG.values() for fmt in fmts}
    assert "implementation_order" not in catalogue and "implementation" not in catalogue, (
        "the platform's implementation series has been added to the TENANT's "
        "number-series catalogue — task 27 puts it on the other side of the "
        "boundary"
    )
    assert not any(fmt.startswith("IMPL") for fmt in formats), (
        "an IMPL- format is offered on Settings → Numbering — the tenant can "
        "rename Bynry's own series"
    )
    # …and it does not need a tenant in context, which the tenant kernel does.
    assert platform_numbering.render_order_no(7, date(2026, 8, 27)) == "IMPL-26-0007"
