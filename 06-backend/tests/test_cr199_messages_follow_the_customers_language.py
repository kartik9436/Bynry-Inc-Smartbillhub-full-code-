# ── Trace ──────────────────────────────────────────────
# Change:   CR-199-BRC10 lane TPL-SRV-LANG (task S8 + the per-language count)
# Rules:    decision log 2026-10-29 *"A message goes in the customer's preferred
#           language (PO, option B)"* — SUPERSEDES `OQ-CUS-12619` (a) for
#           messages · BR-NOT-006 as amended 2026-10-29 (the customer's
#           language first, the utility's default variant as the fallback) ·
#           BR-CWP-105 / PO 2026-09-07 (the portal keeps the account's own
#           language — unchanged) · BR-BIL-026 (a pinned row keeps its pin)
# Replaces: test_def_not_6354_messages_use_the_utility_language.py, which
#           asserted the superseded rule. Replaced with the new figure, not
#           deleted for green (CR-199-BRC10 §4).
# ───────────────────────────────────────────────────────
"""A message goes in the CUSTOMER's language where the utility published it.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE PO'S WORKED CASE, which every case below is a piece of:             ║
║  Rosa Pemberton, at an English-default utility, chose Español.           ║
║  Springfield published a Spanish "Bill ready" → her bill email is        ║
║  Spanish. No Spanish past-due reminder → her reminder is English.        ║
║  PO, verbatim: "Question: which language should messages be sent in? - B"║
╚══════════════════════════════════════════════════════════════════════════╝

The discriminating fixture is still a PUBLISHED SPANISH VARIANT, for the
reason the replaced file gave: without one every resolution lands on the
`default` variant whatever is asked for, and a case asserting *"English"*
passes over the old code and the new alike. So BOTH halves are asserted on
the same tenant and the same customer: one class published in Spanish, one
not.

────────────────────────────────────────────────────────────────────────────
HOW THESE WERE PROVED RED BEFORE THEY WERE TRUSTED GREEN
────────────────────────────────────────────────────────────────────────────
Run against the tip's writers (82afb3587 — `services.py`,
`service_request_events.py`, `customer_events.py`, `communication_api.py`,
customers' `notifications_seam.py` and `service_request_service.py` swapped
back, this file unchanged): **5 failed, 10 passed.** The five are exactly the
Spanish halves — the bill email, the `es-MX` → `es` case, the pinned row, the
acknowledgement and the dialog's offer — each pinning the utility's `en-US`
or `default` where `es` was published. The English halves passed before and
after, which is what a fallback is, and the count cases are new reads.
"""

import ast
import uuid
from pathlib import Path

import pytest
from django.urls import resolve

from apps.customers import communication_api
from apps.customers import models as customers_models
from apps.customers import service_request_service as sr
from apps.metering import connection_messages as step7
from apps.notifications import message_language
from apps.notifications import models as notification_models
from apps.notifications import service_request_events
from apps.notifications import services
from apps.notifications import template_models as tm
from apps.notifications import template_service
from apps.notifications import template_languages_api
from apps.portal import selectors as portal_selectors
from types import SimpleNamespace

from tests.test_cr094_k_account_communication import _account
from tests.test_new_connect_step7_messages import _a_build
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

#: The marker a Spanish variant carries, so a body can be told apart from the
#: default's without trusting a language column alone.
SPANISH = "Hola."

BILL_READY = "email_bill_ready"
PAST_DUE = "email_past_due"

ROSA = {
    "channel": "physical_form",
    "applicant_kind": "person",
    "applicant_name": "Pemberton, Rosa",
    "applicant_email": "rosa.pemberton@example.test",
    "applicant_phone": "555-0177",
    "address_as_given": "88 Pecan Hollow",
    "property_type": "standalone_owner_occupied",
    "what_they_said": "Moving in on the first",
    "preferred_language": "es",
}


def _utility_language(tenant, code):
    """Settings → Regional's language — the FALLBACK since 2026-10-29."""
    from apps.tenancy import models as tenancy_models

    tenancy_models.TenantSettings.objects.filter(tenant=tenant).update(language=code)


def _publish_variant(admin, code, language, marker=SPANISH):
    """Publish a `language` variant of `code`, built from the seeded default's
    own wording so it validates against the class's palette."""
    default = template_service.resolve(code=code)
    pinned = template_service.load_pinned(template_id=default.template_id, version=default.version)
    row, _created = template_service.register(
        code=code, name=language, actor=admin, language=language
    )
    draft = template_service.save_draft(
        template=row,
        body=f"{marker} {pinned.body}",
        subject=pinned.subject,
        actor=admin,
    )
    template_service.publish(version_row=draft, actor=admin)
    return row


def _spanish_variant(admin, code):
    """An `es` variant of `code` — shared with the New Connection letter test."""
    return _publish_variant(admin, code, "es")


def _account_in(tenant, account_no):
    """`test_cr094_k_account_communication._account`, with the account TYPE
    looked up within the tenant — that helper's unscoped `get_or_create` finds
    one `residential` per tenant once a second utility exists (the T4 case)."""
    from apps.customers import models as customers_models
    from apps.metering import models as metering_models

    status, _ = customers_models.AccountStatus.objects.get_or_create(
        tenant=tenant,
        code="active",
        defaults={"name": "Active", "behavior_class": "occupying"},
    )
    account_type = customers_models.AccountType.objects.filter(
        tenant=tenant, code="residential"
    ).first()
    if account_type is None:
        return _account(tenant, account_no=account_no)
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


def _rosas_account(tenant, language="es", account_no="A-61900"):
    account = _account_in(tenant, account_no)
    customers_models.Account.objects.filter(pk=account.pk).update(preferred_language=language)
    return account


def _queue_email(account, code):
    """One email of `code` to the account, queued exactly as every writer
    queues: the UTILITY's language passed as `language=`, the account named,
    nothing about the customer's preference said by the caller."""
    write = services.queue_document(
        source_type="reminder",
        source_id=uuid.uuid4(),
        channels=(notification_models.CHANNEL_EMAIL,),
        template=services.TemplatePin(code=code),
        account_id=account.pk,
        recipients=(
            services.Recipient(
                channel=notification_models.CHANNEL_EMAIL, address="rosa.pemberton@example.test"
            ),
        ),
        language=template_service_language(),
        job="tests.cr199",
    )
    (message,) = write.messages
    return notification_models.OutboundMessage.objects.get(pk=message.id)


def template_service_language():
    from apps.customers import seams

    return seams.tenant_default_language()


def _body(row):
    return template_service.load_pinned(
        template_id=row.template_id, version=row.template_version
    ).body


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE PO'S WORKED CASE, BOTH HALVES, ON ONE CUSTOMER
# ═══════════════════════════════════════════════════════════════════════════
def test_rosas_bill_ready_email_is_spanish_because_springfield_published_one(brazos, dana):
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        spanish = _publish_variant(dana, BILL_READY, "es")
        rosa = _rosas_account(brazos)

        row = _queue_email(rosa, BILL_READY)
        assert row.template_id == spanish.id
        assert row.template_language == "es"
        assert _body(row).startswith(SPANISH)


def test_rosas_past_due_reminder_is_english_because_none_is_published_in_spanish(brazos, dana):
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        _publish_variant(dana, BILL_READY, "es")  # Spanish exists for ANOTHER class
        rosa = _rosas_account(brazos)

        row = _queue_email(rosa, PAST_DUE)
        assert row.template_language != "es"
        assert row.template_language in ("en-US", tm.VARIANT_DEFAULT)  # the utility's own
        assert not _body(row).startswith(SPANISH)


def test_a_customer_with_no_preference_gets_the_utilitys_language(brazos, dana):
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        _publish_variant(dana, PAST_DUE, "es")
        nobody = _rosas_account(brazos, language=None, account_no="A-61901")

        row = _queue_email(nobody, PAST_DUE)
        assert row.template_language in ("en-US", tm.VARIANT_DEFAULT)  # the utility's own
        assert not _body(row).startswith(SPANISH)


def test_a_regional_preference_finds_its_base_language(brazos, dana):
    """`es-MX` with only `es` published → the `es` wording (the 2026-10-02
    judgment for New Connection letters, now the rule for every message)."""
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        spanish = _publish_variant(dana, PAST_DUE, "es")
        rosa = _rosas_account(brazos, language="es-MX")

        row = _queue_email(rosa, PAST_DUE)
        assert row.template_id == spanish.id
        assert row.template_language == "es"


def test_the_fallback_is_the_utilitys_own_language_variant(brazos, dana):
    """A Spanish-default utility that published Spanish wording: a customer
    who chose English, with no English variant published, gets the UTILITY's
    Spanish — `BR-NOT-006`'s fallback is the utility's default, not the bare
    `default` row."""
    with tenant_ctx(brazos):
        _utility_language(brazos, "es")
        spanish = _publish_variant(dana, PAST_DUE, "es")
        english_speaker = _rosas_account(brazos, language="en-US", account_no="A-61902")

        row = _queue_email(english_speaker, PAST_DUE)
        assert row.template_id == spanish.id
        assert row.template_language == "es"


def test_a_pinned_row_keeps_its_language_when_the_customer_changes_hers(brazos, dana):
    """BR-BIL-026: the pin records the language ACTUALLY used, and a reprint
    renders that, whatever Rosa chooses afterwards."""
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        _publish_variant(dana, BILL_READY, "es")
        rosa = _rosas_account(brazos)
        row = _queue_email(rosa, BILL_READY)

        customers_models.Account.objects.filter(pk=rosa.pk).update(preferred_language="en-US")
        again = notification_models.OutboundMessage.objects.get(pk=row.pk)
        assert (again.template_id, again.template_version, again.template_language) == (
            row.template_id,
            row.template_version,
            "es",
        )
        assert _body(again).startswith(SPANISH)
        # And a NEW message now follows her new choice.
        assert _queue_email(rosa, BILL_READY).template_language != "es"


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE APPLICANT — NO ACCOUNT YET, SO THE REQUEST'S OWN LANGUAGE
# ═══════════════════════════════════════════════════════════════════════════
def _pinned_row(request_no, template_code):
    rows = [
        row
        for row in notification_models.OutboundMessage.objects.filter(
            source_type=service_request_events.SOURCE_SERVICE_REQUEST,
            template_code=template_code,
        )
        if (row.render_context or {}).get("request_no") == request_no
    ]
    assert len(rows) == 1, rows
    return rows[0]


def test_rosas_acknowledgement_is_spanish_where_published(brazos, dana):
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        spanish = _publish_variant(dana, service_request_events.TEMPLATE_ACKNOWLEDGEMENT, "es")
        request = sr.create_request(dana, ROSA)
        sr.submit(dana, request.id)

        row = _pinned_row(request.request_no, service_request_events.TEMPLATE_ACKNOWLEDGEMENT)
        assert row.template_id == spanish.id
        assert row.template_language == "es"


def test_an_english_applicant_at_the_same_utility_gets_english(brazos, dana):
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        _publish_variant(dana, service_request_events.TEMPLATE_ACKNOWLEDGEMENT, "es")
        request = sr.create_request(dana, {**ROSA, "preferred_language": "en"})
        sr.submit(dana, request.id)

        row = _pinned_row(request.request_no, service_request_events.TEMPLATE_ACKNOWLEDGEMENT)
        assert row.template_language in ("en-US", tm.VARIANT_DEFAULT)  # the utility's own


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE COMMUNICATION DIALOG OFFERS WHAT WILL BE SENT
# ═══════════════════════════════════════════════════════════════════════════
def _offerable_code():
    from apps.notifications import customer_events

    offered = customer_events.account_message_templates(language=None)
    assert offered, "the provisioned tenant offers no ready-made wording at all"
    return offered[0]["code"]


def test_the_dialog_names_rosas_language_and_offers_her_spanish_wording(brazos, dana):
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        rosa = _rosas_account(brazos)
        code = _offerable_code()
        _publish_variant(dana, code, "es")

        form = communication_api._form(str(rosa.pk))
        assert form["language"] == "es"
        assert form["fallback_language"] == "en-US"
        offered = {row["code"]: row for row in form["templates"]}
        assert offered[code]["body"].startswith(SPANISH)

        # A customer stating nothing is offered the utility's wording.
        nobody = _rosas_account(brazos, language=None, account_no="A-61903")
        form = communication_api._form(str(nobody.pk))
        assert form["language"] == "en-US"
        offered = {row["code"]: row for row in form["templates"]}
        assert not offered[code]["body"].startswith(SPANISH)


def test_the_portal_still_reads_rosas_own_language(brazos):
    """PO 2026-09-07, unchanged by either ruling."""
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        rosa = _rosas_account(brazos)
        principal = SimpleNamespace(tenant_id=brazos.pk, account_ids=[rosa.pk])
        assert portal_selectors.account_language(principal) == "es"


def test_a_new_builds_letters_fall_back_where_no_spanish_is_published(brazos, dana, monkeypatch):
    """The 2026-10-02 New Connection narrowing, now the rule: the owner's
    `es-MX` with nothing published in Spanish → the utility's language."""
    asked: list = []

    def capture(**kwargs):
        asked.append(kwargs["language"])
        return None

    monkeypatch.setattr(step7.seams, "queue_document", capture)
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        build = _a_build(dana, brazos, "23 Idioma Lane")
        customers_models.Account.objects.filter(pk=build.owner_account_id).update(
            preferred_language="es-MX"
        )
        asked.clear()
        step7.fire_on_approval(dana, build, first=True, activated=[])
        assert asked and set(asked) == {"en-US"}


# ═══════════════════════════════════════════════════════════════════════════
# 4 · HOW MANY CUSTOMERS EACH LANGUAGE REACHES — and only this utility's
# ═══════════════════════════════════════════════════════════════════════════
def test_customer_counts_per_language_fold_the_unstated_into_the_default(brazos, lonestar):
    with tenant_ctx(brazos):
        _utility_language(brazos, "en-US")
        _rosas_account(brazos, "es", "A-70001")
        _rosas_account(brazos, "es", "A-70002")
        _rosas_account(brazos, "en-US", "A-70003")
        _rosas_account(brazos, None, "A-70004")
        before = message_language.customers_by_language()
    # T4 — another utility's accounts never reach this figure.
    with tenant_ctx(lonestar):
        _rosas_account(lonestar, "es", "A-70005")
        lonestar_view = message_language.customers_by_language()
    with tenant_ctx(brazos):
        after = message_language.customers_by_language()
    assert before == after

    rows = {row["language"]: row for row in after["languages"]}
    total_accounts = after["total"]
    # The fixture may own other accounts; ours are measured as a difference
    # from what the tenant held before, never as an absolute guess.
    assert rows["es"]["accounts"] >= 2
    assert rows["en-US"]["is_default"] is True
    assert rows["en-US"]["no_preference"] >= 1
    assert rows["en-US"]["accounts"] >= 2
    assert sum(row["accounts"] for row in after["languages"]) == total_accounts
    # The rows are exactly the New-variant picker's switched-on languages.
    from apps.notifications import template_variants

    with tenant_ctx(brazos):
        offered = {row["value"] for row in template_variants.offered_languages()}
    assert {row["value"] for row in after["languages"]} == offered
    # Lonestar's one Spanish account is Lonestar's alone.
    lonestar_rows = {row["language"]: row for row in lonestar_view["languages"]}
    assert lonestar_rows["es"]["accounts"] == 1


def test_customer_counts_cost_the_same_at_any_size(brazos, django_assert_num_queries):
    """The figure is a GROUP BY, so five more accounts cost no more statements
    (NFR-3/NFR-5: it stays flat at 40,000 accounts)."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with tenant_ctx(brazos):
        _rosas_account(brazos, "es", "A-70010")
        message_language.customers_by_language()  # warm any one-off reads
        with CaptureQueriesContext(connection) as small:
            message_language.customers_by_language()
        for n in range(5):
            _rosas_account(brazos, "de", f"A-7002{n}")
        with django_assert_num_queries(len(small.captured_queries)):
            message_language.customers_by_language()


def test_the_count_route_is_mounted():
    match = resolve("/api/brazosbend/template-languages")
    assert match.func is template_languages_api.template_languages


# ═══════════════════════════════════════════════════════════════════════════
# 5 · THE SOURCE GUARD — `language=` stays the FALLBACK everywhere
# ═══════════════════════════════════════════════════════════════════════════
MESSAGE_WRITER_DIRS = ("apps/customers", "apps/metering")


def test_no_writer_hands_a_preference_to_language_instead_of_preferred_language():
    """Every `language=` keyword in customers and metering, read as source.

    The ruling did not change what `language=` MEANS to `queue_document` and
    the resolver: it is the utility's default, the fallback. The customer's
    preference travels as `preferred_language=` (or is read from the account
    by `queue_document` itself), so a writer passing a preference AS
    `language=` would skip the fallback and pin `default` where the utility's
    own variant was meant. It prints how many it checked, so *"0 found"* can
    never mean *"0 looked at"* (law 7, fifth shape).

    ⚠ **BLIND SPOT, WITH ITS NUMBER:** `language=` KEYWORDS only — a local
    assigned and then passed is invisible here. `connection_messages.
    _letter_language` is that shape, deliberately, and is covered by
    `test_a_new_builds_letters_fall_back_where_no_spanish_is_published`.
    """
    backend = Path(__file__).resolve().parents[1]
    checked = 0
    offenders: list[str] = []
    for folder in MESSAGE_WRITER_DIRS:
        for path in sorted((backend / folder).rglob("*.py")):
            if "migrations" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                for keyword in node.keywords:
                    if keyword.arg != "language":
                        continue
                    checked += 1
                    source = ast.unparse(keyword.value)
                    if "preferred_language" in source or "account_language" in source:
                        offenders.append(
                            f"{path.relative_to(backend)}:{keyword.value.lineno}  language={source}"
                        )
    print(f"language= keywords checked in {', '.join(MESSAGE_WRITER_DIRS)}: {checked}")
    assert checked >= 8, f"only {checked} language= keywords found — the walk is not looking"
    assert offenders == [], "\n".join(offenders)
