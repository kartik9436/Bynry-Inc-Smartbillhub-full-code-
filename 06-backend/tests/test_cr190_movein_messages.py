# ── Trace ──────────────────────────────────────────────
# Change:   CR-190-BRC10 lane MOVEIN-MSG — PO 2026-10-22, decision log entries
#           *"Move-in messaging and the welcome email: four answers…"*, *"Money
#           in emails shows the currency symbol…"* and *"Plan-change email: 'Now'
#           and 'From' show each plan's main charges, one line each"*.
# Defects:  DEF-NOT-10440 (welcome `——`) · DEF-NOT-10441 (deposit email) ·
#           DEF-NOT-10443 (plan-change email)
# Rules:    CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (amounts 2dp,
#           unit prices up to 4dp) · hard rule 8 (the address walked to the
#           premises) · OQ-344 (the cycle's default bill date)
# ───────────────────────────────────────────────────────
"""CR-190 MOVEIN-MSG — every customer token is filled, and money reads `$45.00`.

Each case RENDERS the queued row (`rendering.render_for_dispatch`) rather than
counting it: every earlier test of these messages asserted that a row was
queued, and every one of them passed over a body that read *"Welcome, ——."*
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.metering import models as metering_models
from apps.notifications import customer_context, customer_events, rate_summary, rendering
from apps.notifications import models as notification_models
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors
from apps.tenancy import models as tenancy_models

from tests.test_cr048_b6_b10 import _an_occupant, _move_in, _move_out, _seeded
from tests.test_us_bil_001_prepare import a_cycle
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    brazos,
    dana,
    lonestar,
    make_plan,
    marcus,
    tenant_ctx,
)  # noqa: F401

from tests.move_out_draft_isolation import move_out_draft_isolated  # noqa: E402,F401

# DEF-CUS-10093 — the move-outs here set up a move-in; their final bill is not
# this file's subject, so billing's draft answers `nothing_to_bill`.
pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("move_out_draft_isolated")]

ABSENT = rendering.ABSENT_MARK


def _identity(tenant):
    """The utility's own Settings → Company values the bodies print."""
    tenancy_models.Tenant.objects.filter(pk=tenant.pk).update(
        support_phone="+1 512 555 0100",
        support_email="help@brazos.example",
        website="brazos.example",
    )


def _on_a_monthly_cycle(tenant, unit_id, *, bill_day=5, first_run=date(2026, 7, 1)):
    """Stamp the unit's service points on ONE scheduled Monthly cycle."""
    cycle = a_cycle(tenant, code="CR190-M")
    cycle.frequency = "Monthly"
    cycle.days_to_complete = 3
    cycle.first_run_date = first_run
    cycle.bill_day = bill_day
    cycle.save(update_fields=["frequency", "days_to_complete", "first_run_date", "bill_day"])
    metering_models.ServicePoint.objects.filter(unit_id=unit_id, route_id__isnull=True).update(
        cycle_id=cycle.id
    )
    return cycle


def _welcome_email(tenant, account_id):
    return notification_models.OutboundMessage.objects.get(
        tenant=tenant,
        account_id=account_id,
        template_code=customer_events.TEMPLATE_MOVE_IN,
        channel=notification_models.CHANNEL_EMAIL,
    )


def _moved_in(actor, tenant, *, cycle: bool):
    account, unit = _an_occupant(actor, tenant, label="22 Larkspur Ct", name="Probe, A")
    if cycle:
        _on_a_monthly_cycle(tenant, unit["id"])
    _move_out(actor, account)
    incoming = _move_in(actor, account)
    return incoming, account


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE WELCOME — every token filled; the first bill date from the cycle
# ══════════════════════════════════════════════════════════════════════════


def test_the_welcome_renders_every_token_with_a_real_value(brazos, dana):
    """DEF-NOT-10440 — RED on the tip: the body carried `——` five times."""
    with tenant_ctx(brazos):
        _identity(brazos)
        _seeded(dana)
        incoming, outgoing = _moved_in(dana, brazos, cycle=True)
        row = _welcome_email(brazos, incoming["id"])
        artifact = rendering.render_for_dispatch(row)
        fmt = row_format(brazos)

    assert ABSENT not in artifact.body, artifact.body
    assert artifact.absences == ()
    assert artifact.body.startswith("Welcome, Bea.")
    assert incoming["account_no"] in artifact.body
    # Hard rule 8 — the premises street, then the unit LABEL, then the town.
    assert "1408 Bluestem Ln · 22 Larkspur Ct, Katy, TX 77494" in artifact.body
    # Activation = the incoming tenancy's opened_at (BR-CUS-056: day after).
    start = date.fromisoformat(str(incoming["opened_at"])[:10])
    assert rendering.format_date(start, fmt) in artifact.body
    # OQ-344: bill day 5 in the month after the period the customer moved in.
    period_end = date(start.year + (start.month // 12), start.month % 12 + 1, 1) - timedelta(days=1)
    expected = date(period_end.year + (period_end.month // 12), period_end.month % 12 + 1, 5)
    assert (
        f"We will send your first bill on {rendering.format_date(expected, fmt)}."
        in artifact.body
    )
    assert "due" not in artifact.body.lower()


def row_format(tenant):
    from apps.notifications import tenancy_seam

    formats, _ = tenancy_seam.regional_formats()
    return formats.get("date_format") or rendering.ISO_DATE_FORMAT


def test_no_scheduled_cycle_leaves_the_first_bill_sentence_out_and_prints_no_dash(brazos, dana):
    with tenant_ctx(brazos):
        _identity(brazos)
        _seeded(dana)
        incoming, _ = _moved_in(dana, brazos, cycle=False)
        artifact = rendering.render_for_dispatch(_welcome_email(brazos, incoming["id"]))

    assert ABSENT not in artifact.body, artifact.body
    assert "first bill on" not in artifact.body
    # The paragraphs either side survive, with exactly one blank line between.
    assert "ask for it whenever you call.\n\nAt brazos.example" in artifact.body


def test_first_bill_date_is_the_cycles_bill_day_after_the_activation_period(brazos, dana):
    with tenant_ctx(brazos):
        account, unit = _an_occupant(dana, brazos, label="3 Wren Way", name="Okafor, Ade")
        _on_a_monthly_cycle(brazos, unit["id"], bill_day=5, first_run=date(2026, 8, 1))
        # Activated 12 Oct → period 1–31 Oct → first bill 5 Nov.
        assert customer_context.first_bill_date(account.id, date(2026, 10, 12)) == date(2026, 11, 5)
        # Activated on the anchor day itself → still that period's bill.
        assert customer_context.first_bill_date(account.id, date(2026, 10, 1)) == date(2026, 11, 5)


def test_first_bill_date_is_none_without_a_bill_day(brazos, dana):
    with tenant_ctx(brazos):
        account, unit = _an_occupant(dana, brazos, label="4 Wren Way", name="Okafor, Ade")
        cycle = _on_a_monthly_cycle(brazos, unit["id"])
        cycle.bill_day = None
        cycle.save(update_fields=["bill_day"])
        assert customer_context.first_bill_date(account.id, date(2026, 10, 12)) is None


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE SHARED BUILDER
# ══════════════════════════════════════════════════════════════════════════


def test_greeting_rules():
    assert customer_context.greeting_name("Pat Smith") == "Pat"
    assert customer_context.greeting_name("Smith, Pat") == "Pat"
    assert customer_context.greeting_name("Acme Holdings LLC", "company") == "Acme Holdings LLC"
    assert customer_context.greeting_name("  ") is None


def test_service_address_line_drops_missing_parts_never_fills_them():
    line = customer_context.service_address_line
    assert (
        line(
            {
                "line1": "1408 Elm St",
                "unit_label": "A",
                "city": "Austin",
                "state": "TX",
                "postal_code": "78704",
            }
        )
        == "1408 Elm St · A, Austin, TX 78704"
    )
    assert line({"line1": "1408 Elm St", "city": None, "state": "TX"}) == "1408 Elm St, TX"
    assert line({}) is None and line(None) is None


def test_another_tenants_account_reads_as_nobody(brazos, lonestar, dana):
    """Hard rule 1 — the builder answers through customers' tenant-scoped read."""
    with tenant_ctx(brazos):
        account, _unit = _an_occupant(dana, brazos, label="5 Wren Way", name="Okafor, Ade")
        mine = customer_context.customer_context(account.id)
    assert mine["first_name"] == "Ade" and mine["account_no"]
    with tenant_ctx(lonestar):
        theirs = customer_context.customer_context(account.id)
    assert theirs == {token: None for token in customer_context.CUSTOMER_TOKENS}


# ══════════════════════════════════════════════════════════════════════════
# 3 · MONEY — "$45.00", from CLDR, rounding unchanged
# ══════════════════════════════════════════════════════════════════════════


def test_money_carries_its_symbol_from_the_currency_and_region():
    """PO 2026-10-22: *"Option A — '$45.00' … Nothing is hardcoded."*"""
    fm = rendering.format_money
    assert fm(Decimal("45.0000"), "USD", locale="en_US") == "$45.00"
    assert fm(Decimal("45"), "CAD", locale="en_CA") == "$45.00"
    assert fm(Decimal("45"), "CAD", locale="en_US") == "CA$45.00"
    assert fm(Decimal("45"), "EUR", locale="fr_FR") == "45,00\xa0€"
    # B4 ❄ half-up at 2dp is applied FIRST and unchanged.
    assert fm(Decimal("45.005"), "USD", locale="en_US") == "$45.01"
    # The tenant's own number format wins over the locale's marks.
    assert fm(Decimal("1234.5"), "USD", locale="en_US", number_format="1.234,56") == "$1.234,50"
    # No locale → the old code-after form, never a typed `$`.
    assert fm(Decimal("45"), "USD") == "45.00 USD"


def test_money_locale_is_the_message_language_in_the_utilitys_country():
    assert rendering.money_locale("en", "United States") == "en_US"
    assert rendering.money_locale("default", "Canada") == "en_CA"
    assert rendering.money_locale("fr-FR", "Canada") == "fr_CA"
    assert rendering.money_locale("es-MX", "US") == "es_US"
    assert rendering.money_locale(None, None) is None


def test_unit_prices_keep_up_to_four_places():
    """CLAUDE.md hard rule 2 — PO 2026-10-02."""
    up = rendering.format_unit_price
    assert up(Decimal("0.042500"), "USD", locale="en_US") == "$0.0425"
    assert up(Decimal("8.937500"), "USD", locale="en_US") == "$8.9375"
    assert up(Decimal("0.100000"), "USD", locale="en_US") == "$0.10"
    assert up(Decimal("0.039000"), "USD", locale="en_US") == "$0.039"


def test_a_money_value_round_trips_through_the_queue_with_its_currency():
    encoded = rendering.encode_context({"amount": rendering.Money(Decimal("45.0000"), "USD")})
    decoded = rendering.decode_context(encoded)
    assert decoded["amount"] == rendering.Money(Decimal("45.0000"), "USD")


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE DEPOSIT EMAIL
# ══════════════════════════════════════════════════════════════════════════


def test_the_deposit_email_greets_the_customer_and_prints_money_as_money(brazos, dana):
    """DEF-NOT-10441 — RED on the tip: *"Hi ——"*, *"service at ——"*, `45.0000`."""
    import uuid

    with tenant_ctx(brazos):
        _identity(brazos)
        _seeded(dana)
        account, _unit = _an_occupant(dana, brazos, label="6 Wren Way", name="Okafor, Ade")
        message = customer_events.queue_deposit_received(
            payment_id=uuid.uuid4(),
            account_id=account.id,
            received_on=date(2026, 10, 22),
            amount=Decimal("45.0000"),
            balance=Decimal("0.0000"),
            currency="USD",
            actor=dana,
        )
        row = notification_models.OutboundMessage.objects.get(pk=message.message_id)
        artifact = rendering.render_for_dispatch(row)

    assert ABSENT not in artifact.body, artifact.body
    assert artifact.body.startswith("Hi Ade,")
    assert "6 Wren Way" in artifact.body
    assert "45.0000" not in artifact.body
    assert "$45.00" in artifact.body and "$0.00" in artifact.body
    assert "$45.00" in (artifact.subject or "")
    assert "+1 512 555 0100" in artifact.body  # "Call ——" was Settings → Company


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE PLAN-CHANGE EMAIL — each plan's main charges, one line each
# ══════════════════════════════════════════════════════════════════════════


def _summary(*services, name="Residential Standard"):
    return {"plan_name": name, "services": list(services)}


def _svc(name, base, price, unit, structure="flat", currency="USD"):
    return {
        "service_code": name.lower(),
        "service_name": name,
        "currency": currency,
        "base_amount": base,
        "usage": (
            None if price is None else {"unit_price": price, "unit": unit, "structure": structure}
        ),
    }


def test_the_rate_line_reads_the_way_the_po_wrote_it(brazos):
    with tenant_ctx(brazos):
        line = rate_summary.compose(
            _summary(_svc("Electric", Decimal("12.000000"), Decimal("0.042500"), "kWh")),
            language="en",
            frequency="Monthly",
        )
    assert line == "Residential Standard: base $12.00 a month, usage $0.0425 per kWh"


def test_tiered_and_time_of_day_read_as_the_lowest_price_and_the_structure(brazos):
    with tenant_ctx(brazos):
        tiered = rate_summary.compose(
            _summary(_svc("Water", None, Decimal("3.2"), "kgal", "tiered")),
            language="en",
            frequency=None,
        )
        tou = rate_summary.compose(
            _summary(_svc("Electric", Decimal("14"), Decimal("0.039"), "kWh", "time_of_day")),
            language="en",
            frequency="Quarterly",
        )
    assert tiered == "Residential Standard: usage from $3.20 per kgal, tiered"
    assert (
        tou == "Residential Standard: base $14.00 a quarter, usage from $0.039 per kWh, time of day"
    )


def test_several_services_give_one_line_each(brazos):
    with tenant_ctx(brazos):
        text = rate_summary.compose(
            _summary(
                _svc("Electric", Decimal("12"), Decimal("0.0425"), "kWh"),
                _svc("Water", Decimal("8"), Decimal("3.2"), "kgal", "tiered"),
            ),
            language="en",
            frequency="Monthly",
        )
    assert text.splitlines() == [
        "Residential Standard · Electric: base $12.00 a month, usage $0.0425 per kWh",
        "Residential Standard · Water: base $8.00 a month, usage from $3.20 per kgal, tiered",
    ]


def test_the_connecting_words_follow_the_message_language(brazos):
    with tenant_ctx(brazos):
        text = rate_summary.compose(
            _summary(_svc("Electric", Decimal("12"), Decimal("0.0425"), "kWh")),
            language="es-MX",
            frequency="Monthly",
        )
    assert text.startswith("Residential Standard: cargo fijo ")
    assert "al mes" in text and "por kWh" in text


def _priced_plan(tenant, name, *, base, tiers, model="tiered"):
    """A published water plan whose schedule is in force from 1 Jan 2026."""
    plan = make_plan(tenant, name=name, services=("water",))
    water = tenancy_models.Service.objects.get(code="water")
    charge = rating_models.Charge.objects.create(
        tenant=tenant,
        code=f"BASE-{name[:6].upper()}",
        name=f"{name} base",
        charge_type="recurring",
        amount_rule="flat",
        amount=base,
        service=water,
        is_base=True,
        applies_to_customer_classes=[],
    )
    for row in rating_selectors.plan_rate_schedules(plan.id):
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=row["tariff"],
            model=model,
            uom="kgal",
            currency="USD",
            effective_from=date(2026, 1, 1),
            base_charge_code=charge,
        )
        for seq, (start, end, price) in enumerate(tiers, start=1):
            rating_models.RateTier.objects.create(
                tenant=tenant,
                tariff_version=version,
                seq=seq,
                from_qty=start,
                to_qty=end,
                unit_price=price,
            )
    return plan


def test_plan_charge_summary_reads_the_published_schedule(brazos):
    with tenant_ctx(brazos):
        plan = _priced_plan(
            brazos,
            "Silver Tiered",
            base=Decimal("12.0000"),
            tiers=[(0, 5, Decimal("3.2")), (5, None, Decimal("4.8"))],
        )
        summary = rating_selectors.plan_charge_summary(plan.id, on_date=date(2026, 10, 31))
    assert summary["plan_name"] == "Silver Tiered"
    [water] = summary["services"]
    assert water["base_amount"] == Decimal("12.0000")
    assert water["usage"] == {"unit_price": Decimal("3.2"), "unit": "kgal", "structure": "tiered"}


def test_plan_charge_summary_of_another_tenants_plan_is_none(brazos, lonestar):
    with tenant_ctx(brazos):
        plan = _priced_plan(
            brazos, "Silver Iso", base=Decimal("9"), tiers=[(0, None, Decimal("2"))]
        )
    with tenant_ctx(lonestar):
        assert rating_selectors.plan_charge_summary(plan.id, on_date=date(2026, 10, 31)) is None


def test_the_plan_change_email_fills_every_token(brazos, dana):
    """DEF-NOT-10443 — RED on the tip: *"Now ——"*, *"From 10/31/2026 ——"*."""
    import uuid

    with tenant_ctx(brazos):
        _identity(brazos)
        _seeded(dana)
        old = _priced_plan(
            brazos, "Old Flat", base=Decimal("12"), tiers=[(0, None, Decimal("3.2"))]
        )
        new = _priced_plan(
            brazos,
            "New Tiered",
            base=Decimal("14"),
            tiers=[(0, 5, Decimal("3.9")), (5, None, Decimal("5.1"))],
        )
        account, unit = _an_occupant(dana, brazos, label="7 Wren Way", name="Okafor, Ade")
        _on_a_monthly_cycle(brazos, unit["id"])
        message = customer_events.queue_rate_plan_change(
            assignment_id=uuid.uuid4(),
            account_id=account.id,
            effective_on=date(2026, 10, 31),
            plan_name="New Tiered",
            from_plan_id=old.id,
            to_plan_id=new.id,
            actor=dana,
        )
        row = notification_models.OutboundMessage.objects.get(pk=message.message_id)
        artifact = rendering.render_for_dispatch(row)

    assert ABSENT not in artifact.body, artifact.body
    assert artifact.body.startswith("Hi Ade,")
    assert "Now Old Flat: base $12.00 a month, usage $3.20 per kgal" in artifact.body
    assert "New Tiered: base $14.00 a month, usage from $3.90 per kgal, tiered" in artifact.body


# ══════════════════════════════════════════════════════════════════════════
# 6 · THE SEEDED WORDING AND THE MIGRATION THAT MOVES UNTOUCHED COPIES
# ══════════════════════════════════════════════════════════════════════════


def test_the_migration_carries_the_seeded_wording_exactly():
    import importlib

    from apps.notifications import seed_templates

    mig = importlib.import_module(
        "apps.notifications.migrations.0025_cr190_welcome_first_bill_wording"
    )
    assert mig.NEW_BODY == seed_templates.EMAIL_WELCOME_BODY
    assert mig.SUBJECT == seed_templates.EMAIL_WELCOME_SUBJECT
    assert "due around" in mig.OLD_BODY and "due" not in mig.NEW_BODY.lower()


def test_the_migration_moves_an_untouched_copy_and_leaves_an_edited_one(brazos, dana):
    import importlib

    from django.apps import apps as django_apps
    from django.db import connection

    from apps.notifications import template_models as tm

    mig = importlib.import_module(
        "apps.notifications.migrations.0025_cr190_welcome_first_bill_wording"
    )
    with tenant_ctx(brazos):
        _seeded(dana)
        template = tm.NotificationTemplate.objects.get(
            tenant=brazos, code="email_welcome", category="default", language="default"
        )
        live = tm.NotificationTemplateVersion.objects.get(template=template, status="published")
        # Put this tenant back on the OLD seeded wording, as a published copy.
        live.status = "archived"
        live.save(update_fields=["status"])
        old = tm.NotificationTemplateVersion.objects.create(
            tenant=brazos,
            template=template,
            version=live.version + 1,
            status="published",
            subject=mig.SUBJECT,
            body=mig.OLD_BODY,
        )

        class _Editor:
            pass

        editor = _Editor()
        editor.connection = connection
        mig.republish_unedited(django_apps, editor)

    with tenant_ctx(brazos):
        old.refresh_from_db()
        now = tm.NotificationTemplateVersion.objects.get(template=template, status="published")
        assert old.status == "archived"
        assert now.body == mig.NEW_BODY and now.version == old.version + 1
        # Idempotent — a second pass writes nothing.
        count = tm.NotificationTemplateVersion.objects.filter(template=template).count()
        mig.republish_unedited(django_apps, editor)
    with tenant_ctx(brazos):
        assert tm.NotificationTemplateVersion.objects.filter(template=template).count() == count


# ══════════════════════════════════════════════════════════════════════════
# 7 · CREATE FROM OUR DEFAULT — a contract class with no variant (DEF-NOT-10442)
# ══════════════════════════════════════════════════════════════════════════

AGREEMENT = "contract_service_agreement"


def _from_default(tenant, actor, role, data):
    from apps.notifications import templates_api

    from tests.test_us_ten_helpers import api_call

    return api_call(
        templates_api.create_from_default,
        "post",
        user=getattr(actor, "user", None),
        role=role,
        tenant=tenant,
        data=data,
        code=AGREEMENT,
    )


def test_create_from_our_default_prefills_a_dated_draft(brazos, dana):
    from apps.notifications import seed_templates
    from apps.notifications import template_models as tm

    offered = seed_templates.default_body_for(AGREEMENT)
    response = _from_default(brazos, dana, "system_admin", {"effective_from": "2026-11-01"})
    assert response.status_code == 201, response.data
    assert response.data["version"]["status"] == "draft"
    with tenant_ctx(brazos):
        version = tm.NotificationTemplateVersion.objects.get(
            tenant=brazos, template__code=AGREEMENT
        )
    assert version.body == offered.body
    assert version.effective_from == date(2026, 11, 1)
    # BR-NOT-002 stands: nothing is published by this action.
    assert version.status == "draft"


def test_create_from_our_default_still_needs_a_date(brazos, dana):
    response = _from_default(brazos, dana, "system_admin", {})
    assert response.status_code in (400, 409, 422), response.data


def test_create_from_our_default_is_for_the_system_admin_only(brazos, marcus):
    response = _from_default(brazos, marcus, "billing_clerk", {"effective_from": "2026-11-01"})
    assert response.status_code == 403


def test_create_from_our_default_refuses_a_class_that_already_has_a_variant(brazos, dana):
    first = _from_default(brazos, dana, "system_admin", {"effective_from": "2026-11-01"})
    assert first.status_code == 201
    again = _from_default(brazos, dana, "system_admin", {"effective_from": "2026-11-01"})
    assert again.status_code in (409, 422), again.data


# ══════════════════════════════════════════════════════════════════════════
# 8 · STEP 4 — untick, or another allowed channel, per move-in
# ══════════════════════════════════════════════════════════════════════════


def _move_in_with(actor, account, default_messages, *, name="Newcomer, Bea"):
    from apps.customers import services as customers_services

    from tests import identity_fixtures

    return customers_services.move_in(
        actor,
        str(account.id),
        {
            "account_type": "residential",
            "status": "active",
            "opened_at": (account.opened_at + timedelta(days=1)).isoformat(),
            "contact": {"full_name": name, "email": "bea@example.test"},
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
            "default_messages": default_messages,
        },
    )


def _rows(tenant, account_id, code):
    return notification_models.OutboundMessage.objects.filter(
        tenant=tenant, account_id=account_id, template_code=code
    )


def test_the_plan_tells_the_screen_what_may_change(brazos, dana):
    with tenant_ctx(brazos):
        _seeded(dana)
        plan = {row["key"]: row for row in customer_events.move_in_message_plan()}
    assert plan["move_in_welcome"]["editable"] is True
    assert plan["move_in_welcome"]["allowed_channels"] == ["email", "pdf_print"]
    # Merge MOVEIN-MSG x AGREEMENT: the agreement travels as the click-to-accept
    # request EMAIL (PDF attached) or as the printed letter.
    assert plan["service_agreement"]["allowed_channels"] == ["email", "pdf_print"]


def test_an_unticked_welcome_queues_nothing_and_is_audited(brazos, dana, audit_rows):
    """`audit_rows` is the shared capture sink (`test_us_met_helpers`), so the
    row hard rule 7's writer produced is read where the writer put it."""
    with tenant_ctx(brazos):
        _seeded(dana)
        account, _unit = _an_occupant(dana, brazos, label="8 Wren Way", name="Probe, B")
        _move_out(dana, account)
        incoming = _move_in_with(dana, account, [{"key": "move_in_welcome", "send": False}])
        assert not _rows(brazos, incoming["id"], customer_events.TEMPLATE_MOVE_IN).exists()
        # The agreement, untouched, still goes.
        assert _rows(brazos, incoming["id"], customer_events.TEMPLATE_SERVICE_AGREEMENT).exists()
        assert incoming["move_message"][0]["code"] == "move_message_unticked_by_clerk"
    [audit] = [row for row in audit_rows if row["action"] == "move_in.default_message_changed"]
    assert audit["after"]["unticked"] == ["move_in_welcome"]
    assert audit["entity_type"] == "move_record"


def test_a_channel_change_is_honoured(brazos, dana):
    with tenant_ctx(brazos):
        _seeded(dana)
        account, _unit = _an_occupant(dana, brazos, label="9 Wren Way", name="Probe, C")
        _move_out(dana, account)
        incoming = _move_in_with(
            dana, account, [{"key": "move_in_welcome", "send": True, "channel": "pdf_print"}]
        )
        channels = set(
            _rows(brazos, incoming["id"], customer_events.TEMPLATE_MOVE_IN).values_list(
                "channel", flat=True
            )
        )
    assert channels == {notification_models.CHANNEL_PRINT}


@pytest.mark.parametrize(
    "bad",
    [
        [{"key": "move_in_welcome", "send": True, "channel": "sms"}],
        [{"key": "payment_received", "send": False}],
        [{"key": "move_in_welcome", "send": "no"}],
        [{"key": "move_in_welcome"}, {"key": "move_in_welcome"}],
    ],
)
def test_a_choice_the_class_does_not_allow_is_refused(brazos, dana, bad):
    from core import errors

    with tenant_ctx(brazos):
        _seeded(dana)
        account, _unit = _an_occupant(dana, brazos, label="10 Wren Way", name="Probe, D")
        _move_out(dana, account)
        with pytest.raises(errors.ValidationError):
            _move_in_with(dana, account, bad)
