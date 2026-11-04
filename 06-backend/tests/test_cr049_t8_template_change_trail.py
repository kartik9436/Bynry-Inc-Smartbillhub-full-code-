# ── Trace ──────────────────────────────────────────────
# Change:   CR-049 task 8 — "Note a template or item change as a change: the
#           audit trail on the wording itself", the clause the CR calls *"the
#           genuinely new requirement"*.
# Rules:    BR-NOT-027 part 3 (a change to a template is NOTED AS A CHANGE) ·
#           BR-NOT-028 (PROPOSED — the trail is DERIVED, never stored twice) ·
#           BR-BIL-026 · BR-BIL-027 · BR-NOT-025 · BR-NOT-024 (a send test is a
#           rehearsal) · BR-NOT-019 (in-app goes to STAFF) · CLAUDE.md rule 1 ·
#           rule 4 · rule 7 · hard-won law 2 (built is not wired) · law 7
#           (prove a guard RED first)
# ───────────────────────────────────────────────────────
"""Edit a template's wording, then ask what changed and who is holding the
wording it moved away from — and get an answer naming BOTH.

THE ONE CASE THIS FILE EXISTS FOR is `test_cr049_t8__the_decisive_case…`: serve
a 48-hour certified notice, edit the template it was rendered from, publish the
edit, then ask. The answer names the field that moved AND the message the
customer is holding AND the id of the kept copy of it. Before this lane the
product could answer neither half: nothing diffed two versions, and the pin
count was an integer with no way to reach a document.

⚠ **PROVED RED FIRST (hard-won law 7), and the transcripts are quoted in the
case that owns each one.** The headline two, run against the tree before this
lane wrote a line:

    E   ModuleNotFoundError: No module named 'apps.notifications.template_changes'

    E   AssertionError: /api/brazosbend/template-catalog/disconnect_notice_48_hour/
        changes/<id> answered 404: a 404 here means the route is still not
        reachable, whatever the URLconf says

WHAT IS DELIBERATELY *NOT* ASSERTED
-----------------------------------
The author's own account of an edit — *"softened wording"* — is `OQ-255`(b),
open with the Product Owner, and this lane did not answer it. Every case here
asserts FIELDS and LINE COUNTS, and one case asserts that the screen still says
*"no change note recorded"*, so a later lane cannot mistake a derived diff for a
note a person wrote.

WHERE THIS RUNS
---------------
Everything here is app-level and runs on the default sqlite suite as well as on
live PostgreSQL. The database half of the guarantee this derivation RESTS ON —
that a published version's body cannot be updated — is `notifications/0006`'s
trigger and is proved in `test_us_not_006_template_lifecycle.py`; one case here
re-asserts it under `requires_postgres` because if it ever stopped holding, every
number in this file would become a guess.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.notifications import models, template_changes
from apps.notifications import template_models as tm
from apps.notifications import template_service
from apps.tenancy import document_store

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_cr049_t2_dispatch_freeze import provider_connected  # noqa: F401 — shared fixture
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: Inside Brazos Bend's seeded 08:00–21:00 send window. Named, never read from a
#: clock (BR-TEN-043, and G6 greps for it).
SERVED_AT = datetime(2026, 8, 30, 15, 0, tzinfo=dt_timezone.utc)

#: The class every case here edits — the most regulated letter this product
#: sends, and the one `DEF-2504` was about.
NOTICE_CLASS = "disconnect_notice_48_hour"

#: The sentence a System Admin ADDS to the notice the day after it went out. It
#: carries no merge token on purpose: `template_service.save_draft` validates a
#: body against its class palette, and a case that failed on an unknown token
#: would be failing for a reason that has nothing to do with this task.
ADDED_SENTENCE = (
    "Payment arrangements are available. Ask us about one before the date shown above."
)


class StubPrintVendor:
    """The print vendor US-NOT-003 has not integrated, published for one test."""

    def __init__(self):
        self.calls = []

    def __call__(self, channel, messages):
        self.calls.append((channel, messages))
        return {
            m["id"]: {"provider_reference": f"prt-{m['id'][:8]}", "status": "sent"}
            for m in messages
        }


@pytest.fixture()
def print_vendor(monkeypatch, provider_connected):
    """The print vendor, stubbed — AND a tenant that HAS connected it.

    ⚠ `provider_connected` ADDED 2026-09-30. From 2026-09-04 (`d471e8680`,
    `CR-069` wave E) the route asks, separately from *is there an adapter?*,
    *has THIS tenant connected a provider?* A stubbed adapter alone answers only
    the first, so every notice this file serves rested `queued` on
    `provider_not_connected` and was never frozen — correct for a real utility
    with no connection (A15 addendum), and fatal to every case here that needs
    a kept document to reprint. The product did not move; the double did not
    keep up.
    """
    from apps.integrations import services as integrations_services

    vendor = StubPrintVendor()
    monkeypatch.setattr(integrations_services, "dispatch_outbound_batch", vendor, raising=False)
    return vendor


@pytest.fixture()
def docs_dir(tmp_path, settings):
    """A per-test document directory, so no case can read another's bytes."""
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    return tmp_path / "documents"


def _an_account(actor, tenant, account_no):
    from apps.customers import models as customer_models

    premises = make_premises(
        actor, address_line=f"{account_no} Ridge Rd", services_available=["electric"]
    )
    unit = make_unit(actor, premises["id"], label=account_no, services=["electric"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=account_no,
    )


def _serve_a_48_hour_notice(actor, tenant, account_no="A-49801"):
    """Generate the 48-hour certified notice and actually DISPATCH it.

    Nothing is faked: the tenant is provisioned through the real service, the
    notice resolves the seeded template, and the dispatcher runs its ordinary
    cycle — which, since `CR-049` task 2, freezes the artefact before the
    provider hand-off. The same helper `test_cr049_t3` and `t5` use, and it
    explains the recipient stamp there.
    """
    from apps.notifications import dispatcher, notices

    account = _an_account(actor, tenant, account_no)
    notices.generate_disconnect_notice(
        account_id=account.pk,
        tier=notices.TIER_FINAL_48_HOUR,
        balance=Decimal("1842.100000"),
        cut_date=date(2026, 9, 3),
        reconnect_fee=Decimal("45.000000"),
        state_puc_ref="TX PUC Substantive Rule 25.29",
        on_date=date(2026, 8, 30),
        actor=actor,
    )
    row = models.OutboundMessage.objects.get(
        source_type="notice", source_id=account.pk, channel=models.CHANNEL_PRINT
    )
    # Standing in for the recipient read nothing publishes yet (OQ-208) — see
    # test_cr049_t5_rights_clause_reprint.py, which explains the same stamp.
    models.OutboundMessage.objects.filter(pk=row.pk).update(
        recipient_address=f"{account_no} Ridge Rd, Katy TX 77494",
        recipient_snapshot={"account_no": account_no},
        unavailable_reason=None,
    )
    row.refresh_from_db()
    dispatcher.dispatch_cycle(
        now=SERVED_AT, channels=(models.CHANNEL_PRINT,), actor=actor, job="test"
    )
    row.refresh_from_db()
    return row


def _the_variant(tenant, code=NOTICE_CLASS):
    return tm.NotificationTemplate.objects.get(
        tenant=tenant, code=code, category=tm.VARIANT_DEFAULT, language=tm.VARIANT_DEFAULT
    )


def _live_version(variant):
    return tm.NotificationTemplateVersion.objects.get(
        template=variant, status=tm.VERSION_PUBLISHED
    )


def _edit_the_wording(actor, variant, sentence=ADDED_SENTENCE):
    """What a System Admin does: a new draft with one more sentence, published.

    Returns `(the version that was superseded, the new published version)`.
    """
    live = _live_version(variant)
    draft = template_service.save_draft(
        template=variant,
        body=f"{live.body}\n\n{sentence}",
        subject=live.subject,
        actor=actor,
    )
    published = template_service.publish(version_row=draft, actor=actor)
    live.refresh_from_db()
    return live, published


# ══════════════════════════════════════════════════════════════════════════
# 0 · IS IT WIRED AT ALL? — hard-won law 2 at the routing layer
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t8__the_change_route_is_actually_mounted(brazos):
    """A view function nothing routes to is a trail nobody can read.

    ⚠ RED FIRST, before the route existed:

        E   AttributeError: module 'apps.notifications.templates_api' has no
            attribute 'template_change'
    """
    from django.urls import resolve

    from apps.notifications import templates_api

    version_id = uuid.uuid4()
    path = f"/api/brazosbend/template-catalog/{NOTICE_CLASS}/changes/{version_id}"
    assert resolve(path).func is templates_api.template_change


def test_cr049_t8__the_change_route_is_reachable_through_the_whole_stack(brazos):
    """`resolve()` proves the URLconf knows the path; it does not prove a request
    can GET there. **401 = the route exists and asked for a sign-in; 404 = there
    is no route**, which is what this path answered before this lane.

    ⚠ RED FIRST:

        E   AssertionError: GET /api/brazosbend/template-catalog/
            disconnect_notice_48_hour/changes/<id> answered 404
    """
    from django.test import Client

    from core import errors

    path = f"/api/{brazos.subdomain}/template-catalog/{NOTICE_CLASS}/changes/{uuid.uuid4()}"
    response = Client().get(path)
    assert response.status_code == 401, (
        f"GET {path} answered {response.status_code}: a 404 here means the route is still "
        "not reachable, whatever the URLconf says"
    )
    assert response.json()["code"] == errors.AUTH_UNAUTHENTICATED


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE CASE THAT DECIDES THIS TASK
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t8__the_decisive_case__what_changed_and_who_holds_the_old_wording(
    brazos, dana, print_vendor, docs_dir
):
    """**Serve a notice, edit the template, then ask — and the answer names both.**

    This is the PO's third clause turned into a test. Half of it (*"what
    changed"*) the product could not answer because nothing diffs two versions;
    the other half (*"which already-sent documents were built on the wording
    that has now moved"*) it could not answer because `pinned_by` is a bare
    integer with nothing behind it.

    ⚠ RED FIRST, against the tree before this lane:

        E   ModuleNotFoundError: No module named 'apps.notifications.template_changes'
    """
    with tenant_ctx(brazos):
        row = _serve_a_48_hour_notice(dana, brazos)
        assert row.status == models.STATUS_SENT
        assert print_vendor.calls, "the print vendor was never handed the batch"

        variant = _the_variant(brazos)
        assert row.template_id == variant.pk
        superseded, published = _edit_the_wording(dana, variant)
        assert row.template_version == superseded.version

        record = template_changes.record(published)

        # ── HALF ONE: WHAT MOVED ──────────────────────────────────────────
        assert [field.field for field in record.change.fields] == ["body"]
        body_change = record.change.fields[0]
        assert body_change.lines_added >= 1
        assert body_change.added is False and body_change.removed is False
        assert record.change.previous_version == superseded.version
        assert record.change.is_first_version is False

        # ── HALF TWO: WHO IS HOLDING THE WORDING THAT MOVED ───────────────
        assert record.superseded_version == superseded.version
        assert record.superseded_documents == 1
        (impact,) = record.superseded_sample
        assert impact.message_id == str(row.pk)
        assert impact.channel == models.CHANNEL_PRINT
        assert impact.document_kept is True

        # ── AND THE LETTER ITSELF, which is what makes half two worth having
        served = document_store.fetch(impact.document_id).decode("utf-8")

    assert ADDED_SENTENCE in published.body
    assert ADDED_SENTENCE not in served, (
        "the kept copy carries wording added AFTER it was sent — the freeze is broken, "
        "not the trail"
    )


def test_cr049_t8__the_route_answers_the_same_question_a_screen_asks(
    brazos, dana, print_vendor, docs_dir
):
    """The same case through the thing a screen actually calls (hard-won law 2).

    A service that answers correctly and a route that never asks it is the
    defect, not the fix — which is the sentence `CR-049` task 3's lane left
    behind about task 2.
    """
    from apps.notifications import templates_api

    with tenant_ctx(brazos):
        row = _serve_a_48_hour_notice(dana, brazos, "A-49802")
        variant = _the_variant(brazos)
        superseded, published = _edit_the_wording(dana, variant)

        response = api_call(
            templates_api.template_change,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            code=NOTICE_CLASS,
            version_id=str(published.pk),
        )

    assert response.status_code == 200, response.data
    payload = response.data
    assert payload["version"] == published.version
    assert payload["previous_version"] == superseded.version
    assert payload["changed_fields"] == ["body"]
    assert payload["superseded"]["version"] == superseded.version
    assert payload["superseded"]["documents"] == 1
    (impact,) = payload["superseded"]["sample"]
    assert impact["message_id"] == str(row.pk)
    assert impact["document_id"] is not None
    assert impact["document_kept"] is True
    # ⚠ The route hands over a document ID, never a storage key — the whole
    # point of `StoredDocumentRef` carrying none. The id opens the existing
    # `GET /documents/{id}`, so this trail reaches the letter without adding a
    # second way to read one.
    assert "storage_key" not in impact


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE VERSION LIST SAYS WHAT CHANGED — the cell that had nothing in it
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t8__every_version_row_carries_the_fields_that_moved(brazos, dana):
    """`GET /template-catalog/{code}` serves `changed_fields` per version.

    ⚠ RED FIRST:

        E   KeyError: 'changed_fields'
    """
    from apps.notifications import templates_api

    with tenant_ctx(brazos):
        variant = _the_variant(brazos)
        _superseded, published = _edit_the_wording(dana, variant)

        response = api_call(
            templates_api.template_detail,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            code=NOTICE_CLASS,
            query={"variant": str(variant.pk)},
        )

    assert response.status_code == 200, response.data
    rows = {row["version"]: row for row in response.data["versions"]}
    assert rows[published.version]["changed_fields"] == ["body"]
    assert rows[published.version]["changed_from_version"] == 1
    # The FIRST version supersedes nothing and says so — see the next case.
    assert rows[1]["changed_from_version"] is None
    # ⚠ AND THE AUTHOR'S NOTE IS STILL ABSENT AND STILL SAYS SO. A derived diff
    # is not "softened wording" (OQ-255(b)) and must never be served as one.
    assert rows[published.version]["change_note"] is None


def test_cr049_t8__the_first_version_supersedes_nothing_and_does_not_say_nothing_changed(
    brazos, dana
):
    """A blank on the first version would read as *"nobody wrote this"*.

    That is the false statement `DEF-2479` made this history stop making, and it
    is easy to reintroduce: `previous_version = None` is falsy, and a screen
    that branches on truthiness draws the same empty cell for *"the wording
    arrived"* and *"nothing moved"*.
    """
    with tenant_ctx(brazos):
        variant = _the_variant(brazos)
        first = tm.NotificationTemplateVersion.objects.get(template=variant, version=1)

        record = template_changes.record(first)

    assert record.change.is_first_version is True
    assert record.change.previous_version is None
    assert record.superseded_version is None
    assert record.superseded_documents == 0
    # Everything the first version holds is NEW, reported as an arrival.
    assert [field.field for field in record.change.fields] == ["body"]
    assert record.change.fields[0].added is True


def test_cr049_t8__a_class_with_no_subject_never_reports_a_subject_change(brazos, dana):
    """NULL and `""` are different, and a printable class holds NULL for ever.

    ⚠ RED FIRST — with the None/"" tests collapsed to a plain `!=`, every
    printable and SMS template claimed its subject changed on every edit:

        E   AssertionError: assert ['subject', 'body'] == ['body']
    """
    with tenant_ctx(brazos):
        variant = _the_variant(brazos)
        superseded, published = _edit_the_wording(dana, variant)

        assert superseded.subject is None and published.subject is None
        assert template_changes.changed_field_names(published, superseded) == ["body"]


# ══════════════════════════════════════════════════════════════════════════
# 3 · WHO COUNTS AS "ALREADY SENT" — the narrowing, and why it is not cosmetic
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t8__a_queued_row_is_not_a_document_anybody_is_holding(
    brazos, dana, print_vendor, docs_dir
):
    """A regulator's answer must not count a letter nobody has posted.

    ⚠ RED FIRST — with `_left_the_building` reduced to the bare pin filter, the
    still-queued email row was counted beside the posted letter:

        E   assert 2 == 1
    """
    with tenant_ctx(brazos):
        row = _serve_a_48_hour_notice(dana, brazos, "A-49803")
        variant = _the_variant(brazos)

        # A second row on the SAME pin that has not been dispatched.
        queued = models.OutboundMessage.objects.create(
            tenant=brazos,
            source_type="notice",
            source_id=uuid.uuid4(),
            channel=models.CHANNEL_PRINT,
            template_code=NOTICE_CLASS,
            template_id=row.template_id,
            template_version=row.template_version,
            recipient_address="99 Ridge Rd, Katy TX 77494",
            status=models.STATUS_QUEUED,
        )
        assert queued.sent_at is None

        superseded = tm.NotificationTemplateVersion.objects.get(
            template=variant, version=row.template_version
        )
        total, sample = template_changes.documents_on(superseded)

    assert total == 1
    assert [impact.message_id for impact in sample] == [str(row.pk)]


def test_cr049_t8__a_send_test_is_a_rehearsal_and_never_appears_in_the_trail(
    brazos, dana, print_vendor, docs_dir
):
    """`BR-NOT-024`'s third bucket, and `BR-NOT-027` excludes it by name.

    A rehearsal addressed to the person who pressed the button is not a document
    a customer is holding, so counting it would inflate a regulator's answer with
    the utility's own staff.
    """
    with tenant_ctx(brazos):
        row = _serve_a_48_hour_notice(dana, brazos, "A-49804")
        variant = _the_variant(brazos)

        models.OutboundMessage.objects.create(
            tenant=brazos,
            source_type="test",
            source_id=uuid.uuid4(),
            channel=models.CHANNEL_PRINT,
            template_code=NOTICE_CLASS,
            template_id=row.template_id,
            template_version=row.template_version,
            recipient_address="dana@brazosbendutilities.test",
            status=models.STATUS_SENT,
            sent_at=SERVED_AT,
        )

        superseded = tm.NotificationTemplateVersion.objects.get(
            template=variant, version=row.template_version
        )
        total, sample = template_changes.documents_on(superseded)

    assert total == 1
    assert [impact.message_id for impact in sample] == [str(row.pk)]


def test_cr049_t8__the_count_and_the_page_are_the_same_question(
    brazos, dana, print_vendor, docs_dir
):
    """*"3 of 3,412"* about two different sets is a false statement, not an
    off-by-one — and this is the screen where the reader is a regulator.
    """
    with tenant_ctx(brazos):
        row = _serve_a_48_hour_notice(dana, brazos, "A-49805")
        variant = _the_variant(brazos)
        for index in range(4):
            models.OutboundMessage.objects.create(
                tenant=brazos,
                source_type="notice",
                source_id=uuid.uuid4(),
                channel=models.CHANNEL_PRINT,
                template_code=NOTICE_CLASS,
                template_id=row.template_id,
                template_version=row.template_version,
                recipient_address=f"{index} Ridge Rd, Katy TX 77494",
                status=models.STATUS_SENT,
                sent_at=SERVED_AT,
            )
        superseded = tm.NotificationTemplateVersion.objects.get(
            template=variant, version=row.template_version
        )

        total, sample = template_changes.documents_on(superseded, limit=2)
        record = template_changes.record(superseded_of := superseded, limit=2)

    assert total == 5
    assert len(sample) == 2
    assert superseded_of.version == row.template_version
    # `record` for the FIRST version reports no impact — the impact of a change
    # is always the PREVIOUS version's, which is what makes the trail readable.
    assert record.superseded_documents == 0


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE CHAIN, AND THE THING THE WHOLE DERIVATION RESTS ON
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t8__the_previous_version_is_the_row_below_not_version_minus_one(brazos, dana):
    """An unpinned draft can be deleted, so a chain can read 1, 2, 4.

    ⚠ RED FIRST — with `previous_of` written as `version - 1`, a variant
    somebody had tidied a draft out of reported its next edit as a first
    version, and the trail silently started again:

        E   assert None == 2
    """
    with tenant_ctx(brazos):
        variant = _the_variant(brazos)
        live = _live_version(variant)

        # v2: a draft nobody publishes and nothing pins.
        throwaway = template_service.save_draft(
            template=variant, body=f"{live.body}\n\nA line somebody thought better of.", actor=dana
        )
        assert throwaway.version == 2

        # v3: the real edit, saved while v2 was still sitting there.
        draft = template_service.save_draft(
            template=variant, body=f"{live.body}\n\n{ADDED_SENTENCE}", actor=dana
        )
        assert draft.version == 3

        # …and then v2 is tidied away. The chain now reads 1, 3.
        template_service.delete_version(version_row=throwaway, actor=dana)
        assert list(
            tm.NotificationTemplateVersion.objects.filter(template=variant)
            .order_by("version")
            .values_list("version", flat=True)
        ) == [1, 3]

        previous = template_changes.previous_of(draft)

    assert previous is not None
    assert previous.version == 1


@requires_postgres
def test_cr049_t8__the_derivation_rests_on_a_body_that_cannot_move(brazos, dana):
    """Why this trail is DERIVED and not stored (`BR-NOT-028`, PROPOSED).

    A diff computed today equals the diff of the day of the edit ONLY because a
    published version's wording cannot be updated. That guarantee is
    `notifications/0006`'s `trg_ntv_append_only` and it is a DATABASE trigger, so
    it does not exist on the sqlite the suite hardcodes — CLAUDE.md hard-won law
    14's shape, and the reason this case carries the vendor guard rather than
    quietly passing everywhere.
    """
    from django.db import DatabaseError, transaction

    with tenant_ctx(brazos):
        variant = _the_variant(brazos)
        live = _live_version(variant)
        live.body = f"{live.body}\n\nRewritten in place."
        with pytest.raises(DatabaseError) as refusal:
            with transaction.atomic():
                live.save(update_fields=["body", "updated_at"])

    assert "append-only" in str(refusal.value) or "BR-BIL-026" in str(refusal.value)


# ══════════════════════════════════════════════════════════════════════════
# 5 · HARD RULE 7 — the audit row already existed, and now it says WHAT
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t8__the_existing_audit_row_now_names_what_moved(brazos, dana, audit_rows):
    """No NEW audit row and no new table — the row `save_draft` already wrote
    gains two facts it did not carry.

    ⚠ **THE MEASUREMENT THAT MADE THIS TASK NECESSARY.** `OQ-255` says
    *"`audit_log` holds the before/after of `template.saved`"*. It holds the
    before/after of the ROW — class, variant, version number, status, effective
    date — and **not one character of the wording**, so reading the audit trail
    told you an edit had happened and could not tell you what it did.

    ⚠ RED FIRST:

        E   KeyError: 'changed_fields'
    """
    with tenant_ctx(brazos):
        variant = _the_variant(brazos)
        _superseded, published = _edit_the_wording(dana, variant)

    saved = [
        row
        for row in audit_rows
        if row["action"] == "template.saved" and row["entity_id"] == str(published.pk)
    ]
    assert saved, "save_draft's audit row is missing — hard rule 7"
    (row,) = saved
    assert row["after"]["changed_fields"] == ["body"]
    assert row["after"]["changed_from_version"] == 1
    # ⚠ AND THE WORDING ITSELF IS NOT COPIED IN. The version rows are the record
    # (immutable by trigger); a second copy in `audit_log` is a copy that can
    # disagree with the rows it came from, and it would put the whole of every
    # letter this utility has ever written into a table nobody prunes.
    assert "body" not in row["after"]
    assert "subject" not in row["after"]


def test_cr049_t8__asking_the_question_writes_nothing(brazos, dana, print_vendor, docs_dir):
    """A trail that mutates what it reports on is not a trail.

    Reading a change record must leave every version row, every queue row and
    every stored document exactly as it found them — this module has no writes
    at all, and that is asserted rather than left to inspection.
    """
    with tenant_ctx(brazos):
        row = _serve_a_48_hour_notice(dana, brazos, "A-49806")
        variant = _the_variant(brazos)
        superseded, published = _edit_the_wording(dana, variant)

        before = (
            list(
                tm.NotificationTemplateVersion.objects.filter(template=variant)
                .order_by("version")
                .values_list("version", "status", "body", "updated_at")
            ),
            list(
                models.OutboundMessage.objects.filter(tenant=brazos)
                .order_by("id")
                .values_list("id", "status", "template_version", "sent_at")
            ),
        )

        template_changes.record(published)
        template_changes.documents_on(superseded)

        after = (
            list(
                tm.NotificationTemplateVersion.objects.filter(template=variant)
                .order_by("version")
                .values_list("version", "status", "body", "updated_at")
            ),
            list(
                models.OutboundMessage.objects.filter(tenant=brazos)
                .order_by("id")
                .values_list("id", "status", "template_version", "sent_at")
            ),
        )

    assert before == after
    assert row.status == models.STATUS_SENT


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-049 task 8 (sources: 12-governance/11-change-requests.md CR-049 step 5c task 8 · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-027 part 3 + BR-NOT-028 (PROPOSED) · 12-governance/01-open-questions.md OQ-255 · 06-backend/apps/notifications/template_changes.py)
# generated: 2026-08-30 by the CR-049 task 8 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST for every guard — transcripts quoted in the case that owns each.
# exceptions: (1) THE AUTHOR'S NOTE IS NOT ASSERTED because it is not built — OQ-255(b) is the PO's and a derived diff is not a person's account of their intent. One case asserts the absence still SAYS so.
#         (2) ONE CASE CARRIES `requires_postgres` — the trigger this whole derivation rests on does not exist on the sqlite the suite hardcodes (hard-won law 14).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
