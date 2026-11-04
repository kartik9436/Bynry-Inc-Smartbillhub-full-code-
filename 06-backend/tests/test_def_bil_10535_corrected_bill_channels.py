# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-BIL-10535 — a corrected bill lost its email channel (Daniel
#           Thomas, AC-2026-00071) · DEF-BIL-4454 — *What changed* had no
#           customer sentence
# Rulings:  PO 2026-10-22, decision log *"Corrected bills: the clerk picks the
#           channels; every bill also emails whenever an email is on file;
#           'What changed' gets one sentence per reason …"* Q1–Q3, and our
#           judgments in *"Building the corrected-bill rulings Q1–Q3"*
# Rules:    BR-BIL-036 (print is the floor) · BR-BIL-016 · BR-NOT-006 ·
#           hard-won law 14 (run the engine path on PostgreSQL too)
# ───────────────────────────────────────────────────────
"""The corrected bill: which channels it goes on, and what *What changed* says.

Daniel's case, rebuilt on real rows: paperless OFF, an email on file, the
original bill queued by post only, corrected for a wrong reading (373.00 →
213.00, the fixture ladder of `test_cr180_fix_a_bill_revamp`).

    Q1  the approval step offers Email · Paper · Both, starting from the
        original's channels (Paper for Daniel); Both queues print + email on
        `email_corrected_bill`; Email with no email on file is refused by name.
    Q2  every bill emails whenever an email is on file: paperless=False with an
        email → TWO rows (print + email), not one; no email → print alone.
    Q3  `{correction_reason}` is *"We corrected your meter reading."*, and a
        utility's own published sentence wins.

On PostgreSQL as well (law 14):

    cd 06-backend && JOBS_EAGER=false DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://… pytest -q tests/test_def_bil_10535_corrected_bill_channels.py
"""

from __future__ import annotations

import re

import pytest

from apps.billing import correction_reasons, delivery_seam
from apps.customers import models as customer_models
from apps.customers import selectors as customer_selectors
from apps.notifications import catalogs, correction_reason_wording, seed_templates
from apps.notifications import models as notification_models

from tests.test_cr180_fix_a_bill_revamp import (  # noqa: F401 — the autouse pin fixture
    CORRECTED_AT,
    CORRECTED_JULY,
    _call,
    _july_world,
    _one_customer,
    _sent_case,
    _the_rebill_template,
    _wrong_read,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

DANIEL_EMAIL = "daniel.thomas@yopmail.com"
LANGUAGES = ("en", "es", "es-MX", "de", "hi", "fr-FR", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR")


def _email_on_file(tenant, account, email=DANIEL_EMAIL):
    customer_models.Contact.objects.create(
        tenant=tenant, account=account, full_name="Daniel Thomas", email=email, is_primary=True
    )


def _approve(tenant, actor, case_id, preview_hash, **extra):
    from apps.billing import corrections_api

    return _call(
        corrections_api.correction_case_approve_and_issue,
        "post",
        tenant,
        actor,
        data={
            "preview_hash": preview_hash,
            "on_date": "2026-08-16",
            "issued_at": CORRECTED_AT.isoformat(),
            **extra,
        },
        case_id=case_id,
    )


def _case(tenant, actor, case_id):
    from apps.billing import corrections_api

    return _call(corrections_api.correction_case_item, "get", tenant, actor, case_id=case_id)


def _rows(invoice_pk):
    return {
        row.channel: row
        for row in notification_models.OutboundMessage.objects.filter(source_id=invoice_pk)
    }


def _sent_by(invoice_pk):
    """The channels a bill went on, without the portal copy — the portal is a
    floor of its own and is on every bill whatever the clerk picks."""
    return set(_rows(invoice_pk)) - {"portal"}


def _daniel(brazos, dana, *, email=True):
    """The original issues BEFORE the email is recorded, so it goes by post
    only — Daniel's original under the old rule."""
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
        assert _sent_by(world.invoice.pk) == {"pdf_print"}, "the original went by post"
        if email:
            _email_on_file(brazos, world.account)
    preview, sent = _sent_case(brazos, dana, _one_customer(world), [_wrong_read(world)])
    return world, preview, sent


def _rebill(world):
    from apps.billing import models

    return models.Invoice.objects.get(corrects_invoice_id=world.invoice.pk)


# ═══════════════════════════════════════════════════════════════════════════
# Q2 · every bill emails whenever an email is on file
# ═══════════════════════════════════════════════════════════════════════════
def test_q2_the_bill_election_emails_whenever_an_email_is_on_file(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
        account = world.account
        assert account.paperless is False
        assert customer_selectors.delivery_channel_election_for_account(account.pk) == ()
        _email_on_file(brazos, account)
        # Daniel: paperless off, email on file → email elected (was `()`).
        assert customer_selectors.delivery_channel_election_for_account(account.pk) == ("email",)
        account.sms_reminders = True
        account.save(update_fields=["sms_reminders", "updated_at"])
        assert customer_selectors.delivery_channel_election_for_account(account.pk) == (
            "email",
            "sms",
        )


def test_q2_the_customers_own_preference_is_unchanged_for_the_portal_and_work(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
        _email_on_file(brazos, world.account)
        assert customer_selectors.channel_preference_for_account(world.account.pk) == ()
        world.account.paperless = True
        world.account.save(update_fields=["paperless", "updated_at"])
        assert customer_selectors.channel_preference_for_account(world.account.pk) == ("email",)


def test_q2_an_ordinary_bill_to_daniel_queues_print_and_email(brazos, dana):
    from datetime import date

    from tests.test_cr180_fix_a_bill_revamp import JUL_1, JUL_31, _a_run, _an_account, _issue
    from tests.test_def_438_parity import _water_plan

    with tenant_ctx(brazos):
        account, _asset = _an_account(
            brazos,
            dana,
            _water_plan(brazos),
            n=7,
            reads=[("2026-06-28", "1100", "1150"), ("2026-07-28", "1150", "1200")],
        )
        _email_on_file(brazos, account)
        run = _a_run(brazos, dana, start=JUL_1, end=JUL_31, key="q2|7", bill_date=date(2026, 8, 1))
        bill = _issue(dana, account, run, start=JUL_1, end=JUL_31)
        rows = _rows(bill.pk)
        assert set(rows) - {"portal"} == {"pdf_print", "email"}, "TWO rows, not one (Q2)"
        assert rows["email"].template_code == "email_bill_ready"
        assert rows["email"].recipient_address == DANIEL_EMAIL


# ═══════════════════════════════════════════════════════════════════════════
# Q1 · the clerk picks the channels on the approval step
# ═══════════════════════════════════════════════════════════════════════════
def test_q1_the_case_offers_email_paper_both_starting_from_the_originals(brazos, dana):
    world, _preview, sent = _daniel(brazos, dana)
    case = _case(brazos, dana, sent["id"])
    assert case.status_code == 200, case.data
    assert case.data["delivery"] == {
        "choices": ["email", "paper", "email_and_paper"],
        "preselected": "paper",
        "email_on_file": True,
    }


def test_q1_both_queues_print_and_the_corrected_bill_email_with_what_changed(brazos, dana):
    world, preview, sent = _daniel(brazos, dana)
    done = _approve(brazos, dana, sent["id"], preview["preview_hash"], delivery="email_and_paper")
    assert done.status_code == 200, done.data
    assert done.data["result"]["delivery"] == "email_and_paper"
    with tenant_ctx(brazos):
        rebill = _rebill(world)
        assert rebill.total == CORRECTED_JULY
        rows = _rows(rebill.pk)
        assert set(rows) - {"portal"} == {"pdf_print", "email"}
        email = rows["email"]
        assert email.template_code == "email_corrected_bill"
        assert email.recipient_address == DANIEL_EMAIL
        assert email.render_context["correction_reason"] == "We corrected your meter reading."


def test_q1_no_choice_sent_takes_the_originals_channels(brazos, dana):
    world, preview, sent = _daniel(brazos, dana)
    done = _approve(brazos, dana, sent["id"], preview["preview_hash"])
    assert done.status_code == 200, done.data
    assert done.data["result"]["delivery"] == "paper"
    with tenant_ctx(brazos):
        assert _sent_by(_rebill(world).pk) == {"pdf_print"}, "Paper = the original's channels"


def test_q1_email_with_no_email_on_file_is_refused_by_name_and_nothing_issues(brazos, dana):
    world, preview, sent = _daniel(brazos, dana, email=False)
    case = _case(brazos, dana, sent["id"])
    assert case.data["delivery"]["email_on_file"] is False
    for choice in ("email", "email_and_paper"):
        refused = _approve(brazos, dana, sent["id"], preview["preview_hash"], delivery=choice)
        assert refused.status_code == 422, refused.data
        assert refused.data["message_key"] == "billing.correction.delivery_no_email"
    with tenant_ctx(brazos):
        from apps.billing import models

        assert not models.Invoice.objects.filter(corrects_invoice_id=world.invoice.pk).exists()


def test_q1_an_unknown_choice_is_refused_by_name(brazos, dana):
    _world, preview, sent = _daniel(brazos, dana)
    refused = _approve(brazos, dana, sent["id"], preview["preview_hash"], delivery="fax")
    assert refused.status_code == 422, refused.data
    assert refused.data["message_key"] == "billing.correction.delivery_unknown"


def test_q1_paper_is_the_floor_even_when_the_clerk_picks_email(brazos, dana):
    world, preview, sent = _daniel(brazos, dana)
    done = _approve(brazos, dana, sent["id"], preview["preview_hash"], delivery="email")
    assert done.status_code == 200, done.data
    with tenant_ctx(brazos):
        assert _sent_by(_rebill(world).pk) == {"pdf_print", "email"}


def test_q1_paper_on_an_account_with_an_email_queues_print_alone(brazos, dana):
    world, preview, sent = _daniel(brazos, dana)
    done = _approve(brazos, dana, sent["id"], preview["preview_hash"], delivery="paper")
    assert done.status_code == 200, done.data
    with tenant_ctx(brazos):
        assert _sent_by(_rebill(world).pk) == {"pdf_print"}, "the clerk's Paper governs"


# ═══════════════════════════════════════════════════════════════════════════
# Q3 · What changed — one sentence per reason, in every language
# ═══════════════════════════════════════════════════════════════════════════
def test_q3_every_seeded_reason_has_a_sentence_in_all_eleven_languages():
    assert set(correction_reason_wording.REASON_NAMES) == set(
        correction_reasons.SEEDED_REASON_CLASSES
    )
    for reason in correction_reasons.SEEDED_REASON_CLASSES:
        code = correction_reason_wording.class_code(reason)
        table = correction_reason_wording.WORDING[code]
        assert set(table) == set(LANGUAGES), code
        bodies = {table[language][1] for language in LANGUAGES}
        assert len(bodies) == len(LANGUAGES), f"{code}: a language copied another's words"
        assert all("{" not in body and body.strip() for body in bodies), code
        listing = catalogs.LISTINGS[code]
        assert listing.category == catalogs.CAT_BILLING
        assert listing.name.startswith("What changed · ")
        assert catalogs.catalog_for(code) is not None
        assert catalogs.used_by_state(code) == catalogs.used_by_state("email_corrected_bill")


def test_q3_the_sentences_are_planted_and_a_utilitys_edit_wins(brazos, dana):
    from apps.notifications import template_models as tm
    from apps.notifications import template_service

    code = correction_reason_wording.class_code("wrong_read")
    with tenant_ctx(brazos):
        seed_templates.ensure_seeded(code)
        languages = set(
            tm.NotificationTemplate.objects.filter(code=code).values_list("language", flat=True)
        )
        assert {"default", "es", "ja-JP"} <= languages
        assert (
            correction_reason_wording.sentences_for(["wrong_read", "wrong_tax"])
            == "We corrected your meter reading. We corrected the tax on your bill."
        )
        # The utility edits the sentence on Configure → Templates — the
        # variant its own default language resolves to (BR-NOT-006).
        from apps.notifications import tenancy_seam

        resolved = template_service.resolve(
            code=code, language=tenancy_seam.tenant_default_language()
        )
        template = tm.NotificationTemplate.objects.get(pk=resolved.template_id)
        draft = template_service.save_draft(
            template=template, body="We fixed the reading we took from your meter.", actor=dana
        )
        template_service.publish(version_row=draft, actor=dana)
        assert (
            correction_reason_wording.sentences_for(["wrong_read"])
            == "We fixed the reading we took from your meter."
        )


# ═══════════════════════════════════════════════════════════════════════════
# The token check — every token a bill wording declares has a source
# ═══════════════════════════════════════════════════════════════════════════
BILL_WORDINGS = ("email_bill_ready", "sms_bill_ready", "email_corrected_bill")
TOKEN = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


def test_every_token_a_seeded_bill_wording_declares_has_a_source():
    """`DEF-BIL-4454`'s general form: a token no source can fill prints `——`
    forever and nothing fails. A source is a key `bill_render_context` sets or a
    utility-identity token stamped at render. Scope said out loud (law 7)."""
    from types import SimpleNamespace

    invoice = SimpleNamespace(
        bill_payload={},
        corrects_invoice_id=None,
        invoice_no="B-1",
        period_start=None,
        period_end=None,
        due_date=None,
        total=None,
        tenant_id=None,
    )
    context, _problems = delivery_seam.bill_render_context(invoice)
    sources = set(context) | set(catalogs._UTILITY_IDENTITY) | {
        "support_phone",
        "support_email",
        "utility_website",
    }
    bodies = [
        (entry.code, "default", (entry.subject or "") + "\n" + entry.body)
        for entry in seed_templates.SEEDABLE
        if entry.code in BILL_WORDINGS
    ]
    for code in BILL_WORDINGS:
        module = seed_templates.LANGUAGE_WORDING.get(code)
        for language, (subject, body) in (getattr(module, "WORDING", {}).get(code) or {}).items():
            bodies.append((code, language, (subject or "") + "\n" + body))
    assert {code for code, _language, _text in bodies} == set(BILL_WORDINGS)
    missing = sorted(
        {
            (code, language, token)
            for code, language, text in bodies
            for token in TOKEN.findall(text)
            if token not in sources
        }
    )
    skipped = len({entry.code for entry in seed_templates.SEEDABLE} - set(BILL_WORDINGS))
    print(
        f"token check: {len(bodies)} bodies of {len(BILL_WORDINGS)} classes checked, "
        f"{skipped} seeded classes skipped (filled by other senders)"
    )
    assert missing == [], f"tokens with no source: {missing}"
    # And the one that had none now has one.
    assert "correction_reason" in context
