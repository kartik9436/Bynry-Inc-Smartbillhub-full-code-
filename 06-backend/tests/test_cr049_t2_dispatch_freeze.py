# ── Trace ──────────────────────────────────────────────
# Change:   CR-049 task 2 (the dispatcher stores the artefact at SEND and
#           refuses to mark `sent` without it) and task 7 (a row that reached
#           `sent` with no artefact is served as "re-rendered from data, not
#           the original", never as though it were the letter).
# Rules:    BR-NOT-027 (PO 2026-08-30) · BR-NOT-024 (a send test is a
#           rehearsal) · BR-NOT-005 (the forward-only lifecycle) · BR-BIL-026 /
#           BR-NOT-025 (the pin — PROVENANCE, still required) · NFR-33/NFR-35 ·
#           CLAUDE.md rule 1 · hard-won law 1 · law 3 · law 7
# ───────────────────────────────────────────────────────
"""Nothing leaves this building without a copy of it being kept.

`outbound_messages` has 32 columns and not one of them holds what the customer
read (`DEF-2506`). This file is the guarantee that closes it, asserted from the
dispatcher's own cycle rather than from the store: **the artefact is stored
BEFORE the provider is contacted, and a row cannot reach `sent` without one.**

⚠ **IT IS A PRECONDITION AND NOT A CUTOVER, AND THAT IS ONLY AVAILABLE ONCE.**
`provider_seam.PLATFORM_ADAPTERS` carries `in_app` and nothing else — print,
email and SMS have no adapter at all — so no customer has ever received anything
from this product and there is no era before the rule to grandfather. The option
expires at go-live, which is why `CR-049` took it now.

⚠ **PROVED RED FIRST (hard-won law 7).** Two guards, both shown failing before
they were trusted. Verbatim, 2026-08-30:

  * **The precondition.** Patching `freeze_for_dispatch` to answer *"exempt, may
    send"* IS the dispatcher that shipped before this change — the row reaches
    `sent` and nothing is stored:

        E   AssertionError: a row reached `sent` with no frozen artefact behind it
        E   assert False
        E    +  where False = Reproduction(…, provenance=
        E       're_rendered_from_data_not_the_original', …).is_original

  * **The second guarantee.** `_mark_sent` takes the freeze answer as a REQUIRED
    argument; called with none it raises rather than advancing the row. With
    `require_frozen` neutered — i.e. `_mark_sent` before this change — the case
    below reports:

        E   Failed: DID NOT RAISE NotFrozen

    which is what makes a future refactor that reorders the freeze past the
    hand-off go red here instead of shipping an unfrozen legal document.

WHAT IS **NOT** ASSERTED HERE
-------------------------------
The store's own guarantees — RLS, the write-once trigger, the read-time hash
check, the refusal to run on unguaranteed storage — are
`test_cr049_t1_document_store.py`'s and are not re-proved. The rights-clause case
(`DEF-2504`) has its own file because it is the sharpest one and deserves to be
read on its own.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as dt_timezone

import pytest

from apps.notifications import dispatcher, frozen_documents, models, rendering
from apps.tenancy import document_store

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: 15:00 UTC = 10:00 America/Chicago, inside Brazos Bend's seeded 08:00–21:00
#: window, so email and SMS are not held by quiet hours (BR-NOT-009). Named
#: rather than read from a clock (BR-TEN-043).
INSIDE_WINDOW = datetime(2026, 8, 30, 15, 0, tzinfo=dt_timezone.utc)

LETTER = "FINAL NOTICE. Service will be disconnected on 3 September 2026."
SUBJECT = "Your water service — final notice"


class StubAdapter:
    """The provider adapter integrations has not published, for one test."""

    def __init__(self, *, outcome="sent"):
        self.calls: list[tuple[str, tuple]] = []
        self.outcome = outcome

    def __call__(self, channel, messages):
        self.calls.append((channel, messages))
        if self.outcome == "sent":
            return {
                m["id"]: {"provider_reference": f"p-{m['id'][:8]}", "status": "sent"}
                for m in messages
            }
        return {
            m["id"]: {"status": "failed", "error": "provider timeout", "retryable": True}
            for m in messages
        }

    @property
    def handed_over(self):
        return [m["id"] for _channel, messages in self.calls for m in messages]


@pytest.fixture()
def provider_connected(monkeypatch):
    """This tenant HAS connected a provider for every channel — the other half
    of the stand-in a `StubAdapter` is.

    ⚠ **ADDED 2026-09-30, AND EVERY SEND-PATH CASE IN THIS FILE AND IN
    `test_oq1164_every_customer_document_freezes.py` WAS RED WITHOUT IT FROM
    2026-09-04 (`d471e8680`, `CR-069` wave E) UNTIL THEN.** That commit split
    one question into two in `provider_seam.channel_route`: *has the platform
    built an adapter?* and *has THIS tenant connected a provider?* Before it,
    patching `dispatch_outbound_batch` answered both, because no adapter meant
    nobody could send. After it, a stubbed adapter with no connection is — in
    the product, correctly — a utility with no mail connection, and its rows
    rest `queued` on `provider_not_connected` (A15 addendum: never a shared
    sender). So the rows these cases expected to reach `sent` stopped at the
    route, before the freeze was ever asked, and `'queued' == 'sent'` read
    exactly like the pre-`OQ-1164` hold it was written to catch.

    **The PRODUCT did not regress: a tenant with a connected provider still
    sends and freezes every one of the nineteen** — which is what this fixture
    restores the harness to asking. Dated with the red at `d471e8680` and the
    green at its parent `2d771c61d`.
    """
    from apps.integrations import services as integrations_services

    def connected(channel):
        return {
            "channel": channel,
            "connected": True,
            "provider_key": "stub",
            "describe": None,
            "reports_feedback": False,
        }

    monkeypatch.setattr(
        integrations_services, "provider_connection_status", connected, raising=False
    )


@pytest.fixture()
def stub_adapter(monkeypatch, provider_connected):
    from apps.integrations import services as integrations_services

    adapter = StubAdapter()
    monkeypatch.setattr(integrations_services, "dispatch_outbound_batch", adapter, raising=False)
    return adapter


@pytest.fixture()
def stub_templates(monkeypatch):
    """Stand in for the template store, returning a body and a subject.

    The REAL behaviour without this double — dispatch holds on a missing
    published template — is `test_us_not_002_dispatcher.py`'s subject. Here it
    exists so the freeze has something definite to keep, and the letter's exact
    text is what the assertions compare against.
    """

    def render(row):
        return rendering.RenderedArtifact(
            template_code=row.template_code or "disconnect_notice_48_hour",
            template_version=row.template_version or 1,
            language=row.template_language,
            channel=row.channel,
            body=LETTER,
            subject=SUBJECT if row.channel == models.CHANNEL_EMAIL else None,
        )

    monkeypatch.setattr(rendering, "render_for_dispatch", render)


@pytest.fixture()
def docs_dir(tmp_path, settings):
    """A per-test document directory, so no case can read another's bytes."""
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    return tmp_path / "documents"


@pytest.fixture()
def email_on(brazos):
    """Switch email dispatch on for this tenant — it ships off (BR-NOT-010)."""
    from apps.notifications import models as notification_models

    with tenant_ctx(brazos):
        notification_models.NotificationSettings.objects.filter(tenant_id=brazos.id).update(
            email_dispatch_active=True, sms_dispatch_active=True
        )


def queue_row(tenant, *, channel=models.CHANNEL_PRINT, **overrides):
    """One queued row straight into the table.

    The WRITE path is `test_us_not_001_queue_write.py`'s subject; these cases are
    about what the dispatcher does with a row that already exists.
    """
    values = dict(
        tenant_id=tenant.id,
        source_type="notice",
        source_id=uuid.uuid4(),
        channel=channel,
        template_code="disconnect_notice_48_hour",
        template_id=uuid.uuid4(),
        template_version=3,
        template_language="en-US",
        recipient_address="1901 Bluestem Ln, Katy TX 77494",
        recipient_snapshot={"account_no": "ACC-1042"},
        status=models.STATUS_QUEUED,
    )
    values.update(overrides)
    return models.OutboundMessage.objects.create(**values)


def _cycle(channel, *, now=INSIDE_WINDOW):
    return dispatcher.dispatch_cycle(now=now, channels=(channel,), job="test")


# ══════════════════════════════════════════════════════════════════════════
# 1 · WHAT IS KEPT, PER CHANNEL (CR-049 step 5d(c))
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t2__a_printed_letter_is_kept_as_the_text_that_went_to_the_vendor(
    brazos, stub_adapter, stub_templates, docs_dir
):
    """Print keeps the body exactly as `dispatcher._payload` hands it over.

    ⚠ **NOT A PDF, AND THAT IS NOT `CR-049` TASK 6's ANSWER.** `CR-049` step
    5d(c) says *"Print → the PDF bytes"* and there are none: this product has no
    page-render library (`OQ-149`) and the printable classes render text.
    Rendering a PDF at freeze time would freeze a document the customer never
    received — the exact substitution `BR-NOT-027` forbids. So the media type
    follows the payload, and the day a renderer lands and the dispatcher hands
    over a PDF, `application/pdf` is what gets kept with no change to the rule.
    """
    with tenant_ctx(brazos):
        row = queue_row(brazos)
        result = _cycle(models.CHANNEL_PRINT)
        row.refresh_from_db()

        assert row.status == models.STATUS_SENT, result.problems
        reproduction = frozen_documents.reproduce(row)
        assert reproduction.is_original
        assert reproduction.document.content_type == "text/plain"
        assert reproduction.document.kind == "disconnect_notice"
        assert document_store.fetch(reproduction.document.id).decode("utf-8") == LETTER
        # The human name an export unpacks to, from the writer's own snapshot.
        assert reproduction.document.display_name.endswith("ACC-1042-pdf_print.txt")
        assert reproduction.document.display_name.startswith("disconnect_notice/2026/08/")


def test_cr049_t2__an_email_is_kept_as_its_subject_and_body(
    brazos, email_on, stub_adapter, stub_templates, docs_dir
):
    """Email keeps BOTH halves of what was sent, as a readable message.

    Subject and body are the two things the adapter receives, and a minimal
    RFC 5322 message is the one representation of them that every mail client
    and every human already reads — so a bulk export unpacks a `.eml` rather
    than a fragment nobody can open. It is a serialisation of what was sent, not
    an addition to it.
    """
    with tenant_ctx(brazos):
        row = queue_row(brazos, channel=models.CHANNEL_EMAIL, recipient_address="a@example.com")
        result = _cycle(models.CHANNEL_EMAIL)
        row.refresh_from_db()

        assert row.status == models.STATUS_SENT, result.problems
        reproduction = frozen_documents.reproduce(row)
        assert reproduction.document.content_type == "message/rfc822"
        kept = document_store.fetch(reproduction.document.id).decode("utf-8")

    assert kept == f"Subject: {SUBJECT}\r\n\r\n{LETTER}"


def test_cr049_t2__an_sms_is_kept_as_the_text_that_was_sent(
    brazos, email_on, stub_adapter, stub_templates, docs_dir
):
    with tenant_ctx(brazos):
        row = queue_row(brazos, channel=models.CHANNEL_SMS, recipient_address="+15125550142")
        result = _cycle(models.CHANNEL_SMS)
        row.refresh_from_db()

        assert row.status == models.STATUS_SENT, result.problems
        reproduction = frozen_documents.reproduce(row)
        assert reproduction.document.content_type == "text/plain"
        assert document_store.fetch(reproduction.document.id).decode("utf-8") == LETTER


# ══════════════════════════════════════════════════════════════════════════
# 2 · WHAT DOES **NOT** FREEZE, AND BOTH ARE RULED
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t2__an_in_app_alert_sends_and_stores_nothing_new(brazos, stub_templates, docs_dir):
    """PO 2026-08-30: *"we dont have to worry about in-app message those are
    mostly FYI ; hence we dont have worry about them"*.

    `in_app_messages.subject`/`body` already store the render at delivery, so
    nothing is lost — and in-app goes to the utility's OWN STAFF (BR-NOT-019),
    never to a customer. It sends with nothing frozen and says why on a
    reproduction rather than looking like a gap.
    """
    with tenant_ctx(brazos):
        row = queue_row(
            brazos,
            channel=models.CHANNEL_IN_APP,
            source_type="bulk_action",
            recipient_address="dana@brazosbendutilities.com",
        )
        _cycle(models.CHANNEL_IN_APP)
        row.refresh_from_db()

        reproduction = frozen_documents.reproduce(row)
        stored = document_store.manifest()

    assert reproduction.exempt
    assert reproduction.provenance == frozen_documents.PROVENANCE_RE_RENDERED
    assert reproduction.i18n_key == frozen_documents.I18N_EXEMPT_IN_APP
    assert stored == [], "in-app is out of scope; nothing new is kept for it"


def test_cr049_t2__a_send_test_is_a_rehearsal_and_does_not_freeze(
    brazos, email_on, stub_adapter, stub_templates, docs_dir
):
    """BR-NOT-024's third bucket — *"a rehearsal addressed to the signed-in
    user"* — is not a legal document.

    `rule_service.py` already carries that sentence beside the code that queues
    one, and this is the same rule held from the other end: a `test` row sends
    without a frozen copy, and a reproduction says it was a rehearsal rather than
    reporting a missing document.
    """
    with tenant_ctx(brazos):
        row = queue_row(
            brazos,
            channel=models.CHANNEL_EMAIL,
            source_type="test",
            recipient_address="dana@brazosbendutilities.com",
        )
        result = _cycle(models.CHANNEL_EMAIL)
        row.refresh_from_db()

        assert row.status == models.STATUS_SENT, result.problems
        reproduction = frozen_documents.reproduce(row)
        assert reproduction.exempt
        assert reproduction.i18n_key == frozen_documents.I18N_EXEMPT_SEND_TEST
        assert (
            document_store.for_source(
                source_type="outbound_message", source_id=row.pk
            ).unavailable_reason
            == "document_not_stored"
        )


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE REFUSALS — a row that cannot be kept is not sent
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t2__a_document_kind_nobody_has_ruled_on_holds_the_row(
    brazos, stub_adapter, stub_templates, docs_dir
):
    """A template class nobody has ruled on HOLDS. It is never guessed.

    ⚠ **THE EXAMPLE USED TO BE `statement`, AND IT IS NOT ANY MORE.** `OQ-1164`
    closed on 2026-08-30 — the PO ruled *"OKY KEEP THEM"* over the nineteen
    customer-facing classes their scope table had not named, statements among
    them, so a statement now has a kind and sends. The GUARANTEE this case exists
    for did not change: a class with no ruled kind still holds rather than being
    assigned a guess, because a guess goes into a seven-year legal record.

    So the case now uses a class that genuinely has no ruling — a code no
    catalogue contains — which is what the next class somebody adds will look
    like. `test_oq1164_every_customer_document_freezes.py` owns the other half:
    that the nineteen ruled classes now send AND are kept.
    """
    with tenant_ctx(brazos):
        row = queue_row(brazos, template_code="a_class_nobody_has_ruled_on_yet")
        result = _cycle(models.CHANNEL_PRINT)
        row.refresh_from_db()

    assert row.status == models.STATUS_QUEUED
    assert row.attempts == 0, "a held row must not spend one of its three provider attempts"
    assert stub_adapter.calls == [], "a row that cannot be kept must never reach a provider"
    problem = next(p for p in result.problems if p["code"] == frozen_documents.FREEZE_KIND_UNRULED)
    assert problem["br_ref"] == "BR-NOT-027"
    assert "OQ-1164" in problem["detail"]


def test_cr049_t2__an_empty_render_is_never_posted_and_never_kept(
    brazos, stub_adapter, monkeypatch, docs_dir
):
    """A blank letter reaching a customer is worse than one that has not gone out.

    And an empty frozen file would make *"we kept the letter"* true about nothing
    at all — `document_store.store` refuses zero bytes at the door for the same
    reason.
    """
    monkeypatch.setattr(
        rendering,
        "render_for_dispatch",
        lambda row: rendering.RenderedArtifact(
            template_code="disconnect_notice_48_hour",
            template_version=1,
            language=None,
            channel=row.channel,
            body="   ",
        ),
    )
    with tenant_ctx(brazos):
        row = queue_row(brazos)
        result = _cycle(models.CHANNEL_PRINT)
        row.refresh_from_db()

    assert row.status == models.STATUS_QUEUED
    assert stub_adapter.calls == []
    assert frozen_documents.FREEZE_ARTEFACT_EMPTY in [p["code"] for p in result.problems]


def test_cr049_t2__an_email_subject_with_a_line_break_is_refused(
    brazos, email_on, stub_adapter, monkeypatch, docs_dir
):
    """A subject carrying a newline cannot be an RFC 5322 header — and writing it
    anyway is header injection.

    It is caught at the freeze rather than at the provider because that is where
    the subject first has to become a header, and because a template author must
    not be able to add headers to every message a utility sends.
    """
    monkeypatch.setattr(
        rendering,
        "render_for_dispatch",
        lambda row: rendering.RenderedArtifact(
            template_code="disconnect_notice_48_hour",
            template_version=1,
            language=None,
            channel=row.channel,
            body=LETTER,
            subject="Final notice\r\nBcc: everyone@example.com",
        ),
    )
    with tenant_ctx(brazos):
        row = queue_row(brazos, channel=models.CHANNEL_EMAIL, recipient_address="a@example.com")
        result = _cycle(models.CHANNEL_EMAIL)
        row.refresh_from_db()

    assert row.status == models.STATUS_QUEUED
    assert stub_adapter.calls == []
    assert frozen_documents.FREEZE_SUBJECT_NOT_A_HEADER in [p["code"] for p in result.problems]


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE PRECONDITION ITSELF — the two guarantees
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t2__a_row_cannot_be_marked_sent_without_a_freeze(brazos):
    """**The second guarantee, and the reason it exists.**

    The FIRST is the ORDER in `_dispatch_channel`: a row that did not freeze is
    released and never handed to a provider. But a guarantee enforced only by the
    order of two statements is one refactor away from being gone (hard-won law
    1), so `_mark_sent` takes the freeze answer as a REQUIRED argument and
    refuses when it is not a pass. This case is what goes red if someone moves
    the freeze after the hand-off.
    """
    with tenant_ctx(brazos):
        row = queue_row(brazos)
        with pytest.raises(frozen_documents.NotFrozen) as refused:
            dispatcher._mark_sent(row, now=INSIDE_WINDOW, answer={"status": "sent"}, freeze=None)
        row.refresh_from_db()

    assert row.status == models.STATUS_QUEUED
    assert "PRECONDITION of sending" in str(refused.value)


def test_cr049_t2__a_retry_reuses_the_artefact_and_never_stores_a_second_copy(
    brazos, monkeypatch, docs_dir, stub_templates, provider_connected
):
    """A hand-off that failed at the provider does not re-freeze on the retry.

    The store holds one artefact per (source, channel, content type) — a second
    store of the same three is a unique-constraint violation, not a second copy —
    so the retry finds its own document, confirms the bytes still hash the same,
    and passes.
    """
    from apps.integrations import services as integrations_services

    failing = StubAdapter(outcome="failed")
    monkeypatch.setattr(integrations_services, "dispatch_outbound_batch", failing, raising=False)
    with tenant_ctx(brazos):
        row = queue_row(brazos)
        _cycle(models.CHANNEL_PRINT)
        row.refresh_from_db()
        assert row.status == models.STATUS_QUEUED
        first = frozen_documents.reproduce(row)
        assert first.is_original

        models.OutboundMessage.objects.filter(pk=row.pk).update(next_attempt_at=INSIDE_WINDOW)
        succeeding = StubAdapter()
        monkeypatch.setattr(
            integrations_services, "dispatch_outbound_batch", succeeding, raising=False
        )
        result = _cycle(models.CHANNEL_PRINT)
        row.refresh_from_db()

        assert row.status == models.STATUS_SENT, result.problems
        second = frozen_documents.reproduce(row)
        assert second.document.id == first.document.id, "a retry must not store a second copy"
        assert (
            len(document_store.list_for_kind(kind="disconnect_notice")) == 1
        ), "one message, one artefact"


# ══════════════════════════════════════════════════════════════════════════
# 5 · TASK 7 — say what is missing rather than substituting
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t7__a_sent_row_with_no_artefact_is_served_as_a_re_render(brazos, docs_dir):
    """**The half that keeps the rule honest.**

    The precondition should make this unreachable — a row cannot reach `sent`
    without a frozen copy. **It is asserted anyway**, because a guarantee with no
    visible failure mode is exactly the shape hard-won law 1 warns about, and
    because a caller must be able to READ this state rather than infer it from an
    empty document.

    The row here is written straight to `sent`, which nothing in the shipped path
    does, precisely so the honest answer can be proved to exist.
    """
    with tenant_ctx(brazos):
        row = queue_row(brazos, status=models.STATUS_SENT, sent_at=INSIDE_WINDOW)
        reproduction = frozen_documents.reproduce(row)

    assert not reproduction.is_original
    assert reproduction.provenance == frozen_documents.PROVENANCE_RE_RENDERED
    assert reproduction.unavailable_reason == "document_not_stored"
    assert reproduction.i18n_key == frozen_documents.I18N_RE_RENDERED
    assert not reproduction.exempt
    # The sentence says what it IS and what it is NOT — never "unavailable".
    assert "not the document the customer received" in reproduction.detail


def test_cr049_t7__the_answer_is_never_an_empty_success(brazos, docs_dir):
    """Exactly one of `document` / `unavailable_reason`, in both directions.

    `document_store.DocumentLookup` states this law for the store and this is the
    same law one layer up: a caller that reads `document` without checking gets
    `None` AND a reason it can print, so absence can never be mistaken for a
    document. That mistake is the defect `BR-NOT-027` exists to prevent.
    """
    with tenant_ctx(brazos):
        missing = frozen_documents.reproduce(queue_row(brazos, status=models.STATUS_SENT))

    assert missing.document is None and missing.unavailable_reason
    assert missing.i18n_key, "a state a screen must show needs a key, not only prose"


# ══════════════════════════════════════════════════════════════════════════
# 6 · THE PIN IS NOT SUPERSEDED
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t2__the_scope_map_is_the_po_scope_table_and_nothing_more(brazos):
    """Every mapped kind is a real kind — so widening the freeze stays a decision.

    ⚠ **A LANE THAT NEEDS A KIND THAT IS NOT HERE MUST NOT ADD ONE QUIETLY.** The
    map is the PO's `CR-049` step-5b scope table PLUS the nineteen classes they
    ruled in on 2026-08-30 (*"OKY KEEP THEM"*, closing `OQ-1164`), and every
    value in it is a `document_models.DOCUMENT_KINDS` member — which is a CHECK
    constraint, so a value that is not there is a migration, not an edit.

    ⚠ **THIS CASE ASSERTED `statement` AND `email_bill_ready` WERE ABSENT UNTIL
    2026-08-30.** They are present now, by ruling; the assertions were not
    deleted but INVERTED, so the file records that the two lines moved because a
    decision moved them rather than because a lane deleted an inconvenient test.
    The counts and the in-app exclusion live in
    `test_oq1164_every_customer_document_freezes.py`.
    """
    from apps.tenancy.document_models import DOCUMENT_KINDS

    mapped = set(frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS.values())
    assert mapped <= set(DOCUMENT_KINDS)
    assert frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS["statement"] == "statement"
    assert frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS["email_bill_ready"] == (
        "bill_ready_notice"
    )
    assert frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS["disconnect_notice_48_hour"] == (
        "disconnect_notice"
    )
    # The in-app staff summary stays OUT — a ruling on a list does not overturn
    # a ruling on a channel (PO 2026-08-26). Asserted by name, here and there.
    assert "staff_bulk_summary" not in frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS


def test_cr049_t2__a_frozen_message_still_carries_its_template_pin(
    brazos, stub_adapter, stub_templates, docs_dir
):
    """BR-BIL-026 / BR-NOT-025 are UNCHANGED and BOTH records are kept.

    ⚠ **THEY ANSWER DIFFERENT QUESTIONS AND A READER WHO COLLAPSES THEM WILL
    DELETE ONE.** The frozen artefact answers *"what did the customer read?"*; the
    pin answers *"which authored version of the wording was in force when they
    read it?"* — which is why `BR-NOT-025` still forbids deleting a template
    version any sent document points at.
    """
    with tenant_ctx(brazos):
        row = queue_row(brazos)
        _cycle(models.CHANNEL_PRINT)
        row.refresh_from_db()

        assert row.status == models.STATUS_SENT
        assert row.template_id is not None and row.template_version == 3
        assert frozen_documents.reproduce(row).is_original


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-049 tasks 2 + 7 (sources: 12-governance/11-change-requests.md CR-049 steps 4, 5b, 5c and 5d(c)/(d) · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-027 · 12-governance/10-defect-log.csv DEF-2506 · 06-backend/apps/tenancy/document_store.py)
# generated: 2026-08-30 by the CR-049 tasks 2/5/7 lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the precondition was shown marking a row `sent` with nothing stored (transcript in the module docstring), and `_mark_sent(freeze=None)` was shown advancing the row before `require_frozen` existed.
# exceptions: (1) `test_cr049_t7__a_sent_row_with_no_artefact_is_served_as_a_re_render` writes a row straight to `sent`, which nothing in the shipped path does — the state must be UNREACHABLE and still be provably describable. (2) Print freezes text, not a PDF; CR-049 task 6 owns that question.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
