# ── Trace ──────────────────────────────────────────────
# Story:    CR-039 wave F tasks 25 · 26 · 27 (implementation as an order,
#           add-ons as their own rows, all of it on the platform side)
# Rules:    PO 2026-08-26 (the model, verbatim) · PO 2026-08-27 ×3 (the 6/9/12
#           is a DURATION · self-serve is a ZERO-month order · an add-on
#           defaults to $1.00 until priced) · CLAUDE.md hard rule 2 (money
#           stored 4dp) · CR-039 task 27 (the platform boundary)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""CR-039 wave F — the two thirds of the commercial model that were never built.

⚠ **THIS WAVE STOOD STILL FOR A FORTNIGHT ON A GATE THAT WAS FALSE.** It was
marked *"gated on PO figures"*; the PO had given the figures on 2026-08-26 and
they went into an HTML page rather than into the repo. Three genuinely open
questions remained inside that sentence, all three were ruled on 2026-08-27,
and each is pinned below at the behaviour it decides — because a figure that
lives only in a chat window is a figure the next agent does not have
(hard-won law 10, which this wave is the worked example of).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.tenancy import models

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant

pytestmark = pytest.mark.django_db


def test_wave_f__self_serve_is_a_zero_month_ORDER_and_not_the_absence_of_one():
    """PO 2026-08-27: *"youc anhave 0 month implmentaiton"* — the modelling was
    DELEGATED and the build chose a row.

    The reason, asserted rather than described: with a zero-month row, *"how
    many customers are self-serve?"* is one query and the answer is a fact.
    With no row, self-serve is indistinguishable from
    implementation-not-yet-scoped — and this test is what would fail if a later
    lane "simplified" it back to an absence.
    """
    tenant, _ = provisioned_tenant()
    # ⚠ **AMENDED 2026-08-27 (CR-039 wave F task 27).** This test used to create
    # its own order and assert the zero-month COUNT was 1, which was true only
    # while nothing in the product wrote this table. Provisioning now writes the
    # self-serve order itself (BR-TEN-240), so the count is 2 — and asserting a
    # global count over a table something else writes is the DEF-1090 shape one
    # module along. What it asserts now is the SENTENCE it was always about:
    # every zero-month row answers `is_self_serve`, and the query the ruling
    # exists for finds the provisioned tenant's own row without being handed it.
    assert models.ImplementationOrder.objects.get(tenant=tenant).is_self_serve is True
    order = models.ImplementationOrder.objects.create(tenant=tenant, duration_months=0)

    assert order.is_self_serve is True
    # THE QUERY THE ROW EXISTS FOR — it cannot be written against an absence.
    self_serve = models.ImplementationOrder.objects.filter(duration_months=0)
    assert self_serve.count() == 2
    assert all(row.is_self_serve for row in self_serve)
    # And self-serve carries no engagement price: the utility does the work.
    assert order.price == Decimal("0")


@pytest.mark.parametrize("months", [0, 6, 9, 12])
def test_wave_f__the_po_s_four_durations_are_all_lawful(months):
    """*"self serve, 6 months, 9 months, 12 months"* — the PO's own list."""
    tenant, _ = provisioned_tenant()
    order = models.ImplementationOrder.objects.create(
        tenant=tenant, duration_months=months
    )
    assert order.duration_months == months
    assert order.is_self_serve is (months == 0)


def test_wave_f__custom_is_any_length_and_is_not_a_fifth_enum():
    """*"and custom implementation plan"*. `custom` is a length nobody has
    named, so it is expressed as any other positive number — a CHECK that
    allowed only 0/6/9/12 would refuse a real eight-month engagement."""
    tenant, _ = provisioned_tenant()
    order = models.ImplementationOrder.objects.create(tenant=tenant, duration_months=8)
    assert order.duration_months == 8
    assert order.is_self_serve is False


def test_wave_f__an_addon_defaults_to_one_dollar_and_says_it_is_not_yet_priced():
    """PO 2026-08-27: *"we will add price latet currently you default it to $1"*.

    ⚠ The `priced` flag is the half that keeps this honest. $1.00 reaching an
    invoice while LOOKING like a considered price is worse than no add-on at
    all, so the default carries a companion fact saying which it is.
    """
    addon = models.Addon.objects.create(code="EXTRA", name="An extra")
    assert addon.price_month == Decimal("1.0000")
    assert addon.priced is False, "a defaulted price must not present as a decided one"


def test_wave_f__the_addon_catalogue_ships_EMPTY_because_no_addon_was_named():
    """The PO gave the price and NOT the name. Inventing a product's name is the
    same class of error as inventing its price — which is the objection that
    stopped this table being built at all.

    Asserted on a freshly provisioned tenant, so a data migration that quietly
    planted a sample add-on would fail here.
    """
    provisioned_tenant()
    assert models.Addon.objects.count() == 0


def test_wave_f__a_tenant_addon_with_no_price_follows_the_catalogue():
    """NULL means *whatever the catalogue says today*.

    Copying the catalogue price onto every row at sign-up would freeze the
    placeholder $1.00 onto real customers the moment a real price replaced it —
    which is exactly the failure the placeholder was introduced to avoid.
    """
    tenant, _ = provisioned_tenant()
    addon = models.Addon.objects.create(code="EXTRA", name="An extra")
    taken = models.TenantAddon.objects.create(tenant=tenant, addon=addon)
    assert taken.price_month is None

    negotiated = models.TenantAddon.objects.create(
        tenant=tenant, addon=addon, price_month=Decimal("250.0000")
    )
    assert negotiated.price_month == Decimal("250.0000")


def test_wave_f__the_duration_lives_on_the_ORDER_and_the_subscription_is_untouched():
    """PO 2026-08-27: *"it is duration of implmentation project"*.

    Wave F task 24 was written as *"Term on the subscription"*. This asserts the
    reversal structurally: `subscriptions` gains NO term column, so a later lane
    cannot add one believing the task still asks for it.

    ⚠ It also records what that leaves open: with no contract term anywhere,
    **nothing states how long a subscription runs for**. That was not ruled, so
    nothing here pretends it was — and this assertion is where a lane that
    decides it unilaterally will be stopped.
    """
    subscription_columns = {f.name for f in models.Subscription._meta.get_fields()}
    for absent in ("term_months", "term", "committed_until", "renews_at"):
        assert absent not in subscription_columns, (
            f"`{absent}` was added to Subscription — but the 6/9/12 is an "
            "implementation DURATION (PO 2026-08-27), and no contract term has "
            "been ruled at all"
        )
    assert "duration_months" in {
        f.name for f in models.ImplementationOrder._meta.get_fields()
    }


def test_wave_f__money_is_stored_at_four_decimals_on_both_new_tables():
    """CLAUDE.md hard rule 2, which governs Bynry's own money exactly as it
    governs a utility's: stored to 4 decimals, displayed at 2, never float."""
    for model, field in (
        (models.ImplementationOrder, "price"),
        (models.Addon, "price_month"),
        (models.TenantAddon, "price_month"),
    ):
        column = model._meta.get_field(field)
        assert column.decimal_places == 4, f"{model.__name__}.{field}"
        assert column.max_digits == 18, f"{model.__name__}.{field}"


def test_wave_f__the_database_refuses_a_third_instalment():
    """The ruling made checkable: 100% upfront or at most TWO.

    ⚠ **PROVED BY ATTEMPTING IT**, not by reading the migration. A constraint
    nobody has seen refuse anything is a constraint nobody knows is wired — and
    this one was raw `ALTER TABLE` in its first draft, which sqlite silently
    could not apply at all. This test is what would have caught that.
    """
    from django.db import IntegrityError, transaction

    tenant, _ = provisioned_tenant()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            models.ImplementationOrder.objects.create(
                tenant=tenant, duration_months=6, instalments=3
            )


def test_wave_f__the_database_refuses_a_negative_duration():
    """Zero is self-serve and lawful; below zero has no reading."""
    from django.db import IntegrityError, transaction

    tenant, _ = provisioned_tenant()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            models.ImplementationOrder.objects.create(tenant=tenant, duration_months=-1)
