# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 step 2 wave K — `ACC-S16`, the communication section.
# Rules:    BR-NOT-005 · BR-NOT-013 · BR-PAY-035 · BR-NOT-008 · BR-NOT-024
#           (the print floor, and why `message` is NOT under it) ·
#           CLAUDE.md rule 6 (idempotency) · hard-won law 7 (a guard is proved
#           RED first, in the harness that will run it).
# ───────────────────────────────────────────────────────
"""What a clerk can write from an account, and what this product may claim.

⚠ **EVERY CASE HERE WAS PROVED RED BEFORE IT WAS PROVED GREEN**, and the two
that matter most are the two that check an ABSENCE:

  * `test_a_courtesy_message_is_not_forced_onto_paper` fails the moment
    somebody files this kind under `account` — the nearest existing source kind,
    which carries the `BR-NOT-024` print floor. That would put every quick email
    in an envelope, and nothing on any screen would say so.
  * `test_nothing_claims_to_have_been_sent` fails if a queued row is ever
    reported as `sent`. `BR-NOT-013` is CONFIRMED: no provider adapter exists on
    post, email or SMS, so a row rests `queued`. A screen built on a `sent` here
    tells a clerk their customer was written to when nothing left the building.
"""

import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from apps.customers import notifications_seam
from apps.notifications import customer_events, models

pytestmark = pytest.mark.django_db

ON = date(2026, 9, 12)


@pytest.fixture(autouse=True)
def guc(monkeypatch):
    """The store's own tenant-context fixture, reused verbatim."""
    from django.db import connection as real_connection

    from core import tenancy as core_tenancy
    from tests.test_us_ten_helpers import FakeGucConnection

    if real_connection.vendor != "postgresql":
        monkeypatch.setattr(core_tenancy, "connection", FakeGucConnection())
    core_tenancy._current_tenant.set(None)
    yield
    core_tenancy._current_tenant.set(None)


@pytest.fixture()
def utility(db):
    from apps.tenancy.models import Tenant

    return Tenant.objects.create(
        name="Brazos Bend Utilities", subdomain=f"brazos{uuid.uuid4().hex[:8]}"
    )


def _account(tenant, account_no="A-11812"):
    """The thinnest lawful account — `accounts.status_id` is NOT NULL. Wave I's
    own helper, reused so two waves cannot disagree about what an account is."""
    from apps.customers import models as customers_models

    status, _ = customers_models.AccountStatus.objects.get_or_create(
        tenant=tenant,
        code="active",
        defaults={"name": "Active", "behavior_class": "occupying"},
    )
    account_type, _ = customers_models.AccountType.objects.get_or_create(
        code="residential", defaults={"name": "Residential"}
    )
    # ⚠ `ck_accounts_anchored` — an account stands somewhere. Hard rule 8: the
    # ADDRESS is the premises', and this test declares none of its own.
    from apps.metering import models as metering_models

    premises_type, _ = metering_models.PremisesType.objects.get_or_create(
        tenant=tenant, code="res", defaults={"name": "Residential"}
    )
    premises = metering_models.Premises.objects.create(
        tenant=tenant,
        premise_no=f"P-{account_no}",
        address_line="142 Bakers Row",
        city="Silver Creek",
        premises_type=premises_type,
        services_available=["water"],
        owner_manager="Bramble Bakery",
        status="active",
    )
    # `ck_accounts_regular_has_unit` — a regular account is on a UNIT, and
    # `BR-CUS-017` derives its plan from that unit.
    unit = metering_models.Unit.objects.create(
        tenant=tenant,
        premises=premises,
        unit_no=f"U-{account_no}",
        label="Suite 1",
        unit_type="commercial",
    )
    return customers_models.Account.objects.create(
        tenant=tenant,
        account_no=account_no,
        status=status,
        account_type=account_type,
        premises_id=premises.pk,
        unit=unit,
    )


def _write(account, *, message_id=None, channels=("email",), kind="courtesy", body="Hello."):
    return notifications_seam.queue_account_message(
        message_id=message_id or uuid.uuid4(),
        account_id=account.pk,
        channels=channels,
        subject="About your account balance",
        body=body,
        signed_by="Brazos Bend Utilities",
        on_date=ON,
        kind=kind,
        actor=SimpleNamespace(id=None),
    )


# ═══════════════════════════════════════════════════════════════════════════
#  THE COMMITMENT — a clerk can write to the customer
# ═══════════════════════════════════════════════════════════════════════════


def test_a_clerk_can_write_to_the_customer(utility, monkeypatch):
    from core.tenancy import tenant_context

    with tenant_context(utility.pk):
        account = _account(utility)
        outcome = _write(account)
        assert outcome["refused"] is False, outcome
        assert outcome["channels"] == ("email",)
        row = models.OutboundMessage.objects.get(account_id=account.pk)
        assert row.source_type == "message"
        assert row.template_code == "account_message"
        # The clerk's own words, kept where `BR-NOT-027` part 1 says they live.
        assert row.render_context["message_body"] == "Hello."
        assert row.render_context["message_subject"] == "About your account balance"


def test_nothing_claims_to_have_been_sent(utility):
    """`BR-NOT-013` — a queued row rests queued, and this screen may not imply
    otherwise. RED PROOF: assert `STATUS_SENT` here and it fails naming
    `queued`, which is what a screen showing *Sent* would be doing."""
    from core.tenancy import tenant_context

    with tenant_context(utility.pk):
        account = _account(utility)
        _write(account)
        row = models.OutboundMessage.objects.get(account_id=account.pk)
        assert row.status == models.STATUS_QUEUED
        assert row.sent_at is None


def test_a_courtesy_message_is_not_forced_onto_paper(utility):
    """The reason `message` is its own source kind rather than `account`.

    `account` carries the `BR-NOT-024` print floor, so filing a clerk's one-line
    email under it would queue a LETTER as well — on every message, for ever.
    """
    from core.tenancy import tenant_context

    from apps.notifications import services

    assert "message" not in services.CHANNEL_FLOOR_BY_SOURCE
    with tenant_context(utility.pk):
        account = _account(utility)
        _write(account, channels=("email",))
        channels = set(
            models.OutboundMessage.objects.filter(account_id=account.pk).values_list(
                "channel", flat=True
            )
        )
        assert channels == {"email"}, "a courtesy note must not also be posted"


# ═══════════════════════════════════════════════════════════════════════════
#  THE THREE REFUSALS, each naming the rule that owns it
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "kind", ["payment_reminder", "disconnection_notice", "bill_copy", "balance_proof"]
)
def test_a_regulated_kind_is_refused_with_its_reason(utility, kind):
    """`BR-PAY-035` maps a reminder's tone to a dunning TIER and `BR-NOT-008`
    fixes the disconnect class, so a ladder step composed here would carry no
    tier and write no notice history."""
    from core.tenancy import tenant_context

    with tenant_context(utility.pk):
        account = _account(utility)
        outcome = _write(account, kind=kind)
        assert outcome["refused"] is True
        assert outcome["message_id"] is None
        assert not models.OutboundMessage.objects.filter(account_id=account.pk).exists()


def test_an_empty_message_is_refused(utility):
    from core.tenancy import tenant_context

    with tenant_context(utility.pk):
        account = _account(utility)
        outcome = _write(account, body="   ")
        assert outcome["refused"] is True
        assert not models.OutboundMessage.objects.filter(account_id=account.pk).exists()


def test_a_second_submit_writes_one_message(utility):
    """CLAUDE.md rule 6. The screen mints the id, so a double-clicked *Queue the
    message* finds its own row rather than writing a second one."""
    from core.tenancy import tenant_context

    with tenant_context(utility.pk):
        account = _account(utility)
        once = uuid.uuid4()
        first = _write(account, message_id=once)
        second = _write(account, message_id=once)
        assert first["refused"] is False and second["refused"] is False
        assert models.OutboundMessage.objects.filter(account_id=account.pk).count() == 1
        assert second["code"] == notifications_seam.MOVE_MESSAGE_ALREADY_QUEUED


def test_an_id_spent_on_another_account_is_refused(utility):
    """The one hazard a CLIENT-minted key brings. Without this the second
    message dedupes into the first, the clerk is told *queued*, and a different
    customer's message is never written."""
    from core.tenancy import tenant_context

    with tenant_context(utility.pk):
        one = _account(utility, "A-11812")
        two = _account(utility, "A-11813")
        once = uuid.uuid4()
        assert _write(one, message_id=once)["refused"] is False
        outcome = _write(two, message_id=once)
        assert outcome["refused"] is True
        assert not models.OutboundMessage.objects.filter(account_id=two.pk).exists()


# ═══════════════════════════════════════════════════════════════════════════
#  WHAT THE DIALOG IS TOLD — the two reads, and the door
# ═══════════════════════════════════════════════════════════════════════════


def test_the_dialog_is_told_which_kinds_it_may_queue():
    kinds = {row["kind"]: row["allowed"] for row in notifications_seam.message_kinds()}
    assert kinds["courtesy"] is True
    assert set(k for k, allowed in kinds.items() if not allowed) == set(
        customer_events.REFUSED_MESSAGE_KINDS
    )


def test_the_dialog_is_told_the_truth_about_delivery(utility):
    """`BR-NOT-013` measured rather than described: the three provider channels
    do not deliver on this deployment and the dialog is served that fact."""
    from core.tenancy import tenant_context

    with tenant_context(utility.pk):
        reach = {row["channel"]: row for row in notifications_seam.channel_reachability()}
    assert reach["email"]["delivers"] is False
    assert reach["sms"]["delivers"] is False
    assert reach["pdf_print"]["delivers"] is False
    assert reach["email"]["reason"], "a channel that does not deliver must say why"


def test_the_door_is_wired(utility):
    """Hard-won law 2. The endpoint is resolved through `config/urls.py` here,
    so a lane that drops the include cannot do it silently."""
    from django.urls import resolve

    match = resolve("/api/v1/accounts/abc/communication")
    assert match.func.__module__ == "apps.customers.communication_api"


# ══════════════════════════════════════════════════════════════════════════
# THE READY-MADE MESSAGES (PO 2026-09-13)
# ══════════════════════════════════════════════════════════════════════════
#
# *"it should also have ready to use messages from our Notification rules -
# user will not write it every time"*. The dialog offered none, so every
# message was typed from nothing and every history row read *A message*.


@pytest.fixture()
def seeded(utility):
    """The tenant's own notice templates, planted the way provisioning plants them.

    ⚠ **WITHOUT THIS THE THREE TESTS BELOW PASS OVER AN EMPTY TUPLE** — they
    assert that nothing BAD is offered, and nothing at all is trivially nothing
    bad. That is hard-won law 7's *structurally incapable of failing* shape, and
    it was the first thing this file did when the tests were written.
    """
    from apps.notifications import seed_templates
    from core.tenancy import tenant_context

    with tenant_context(utility.pk):
        seed_templates.seed_notice_templates(on_date=date(2026, 9, 13))
    return utility


def test_the_picker_offers_the_utilitys_own_published_wording(seeded):
    """A clerk starts from an agreed letter, not an empty box."""
    from core.tenancy import tenant_context

    with tenant_context(seeded.pk):
        offered = customer_events.account_message_templates(language="en")
        names = {one["name"] for one in offered}

    assert offered, "nothing offered — the picker would not appear at all"
    # Seeded, published and in an offerable category on every tenant.
    assert "Welcome / account opened" in names
    assert all(one["body"] for one in offered), "an empty body is content invented"


def test_nothing_offered_can_be_queued_into_a_refusal(seeded):
    """⚠ THE INVARIANT THAT MAKES THE PICKER SAFE RATHER THAN A TRAP.

    A clerk's words are queued as ONE class — `account_message` — and rendered
    against ITS palette. A receipt's body carries `{amount}`, `{confirmation}`,
    `{balance_after}`: facts only the payment that caused it holds, which
    `rendering.validate_body` refuses BY NAME. So every token outside the
    palette is blanked before the wording is offered, and a clerk who picks a
    template and presses Queue never meets a refusal they cannot act on.
    """
    from apps.notifications import catalogs, rendering
    from core.tenancy import tenant_context

    palette = set(catalogs.catalog_for(customer_events.TEMPLATE_ACCOUNT_MESSAGE).tokens)
    with tenant_context(seeded.pk):
        offered = customer_events.account_message_templates(language="en")

    leaked = {
        one["code"]: sorted(
            token
            for token in set(rendering.tokens_in(one["body"]) + rendering.tokens_in(one["subject"]))
            if token not in palette
        )
        for one in offered
    }
    leaked = {code: tokens for code, tokens in leaked.items() if tokens}
    assert leaked == {}, f"these would be refused at queue time: {leaked}"


def test_the_ladder_and_the_documents_are_not_offered(seeded):
    """The same two reasons `REFUSED_MESSAGE_KINDS` already gives, one layer down.

    Collections is the dunning LADDER — a step composed here would carry no tier
    and write no `NoticeHistory` row — and billing's classes are DOCUMENTS with
    their own writer. Neither may be started from here.
    """
    from core.tenancy import tenant_context

    with tenant_context(seeded.pk):
        codes = {one["code"] for one in customer_events.account_message_templates()}

    assert "dunning" not in codes
    assert "disconnect_notice_10_day" not in codes
    assert "email_past_due" not in codes
    assert "email_statement" not in codes
    assert "bill_insert" not in codes
