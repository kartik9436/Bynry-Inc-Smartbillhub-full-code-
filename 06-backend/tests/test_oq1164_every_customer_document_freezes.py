# ── Trace ──────────────────────────────────────────────
# Question: OQ-1164 — CLOSED 2026-08-30. Twenty of the forty-one template
#           classes had no ruled document kind, so the dispatcher HELD every one
#           of them rather than guessing. The PO ruled, verbatim, answering the
#           recommendation put to them in plain English: *"My recommendation is
#           to keep all of them. - OKY KEEP THEM"*.
# Rules:    BR-NOT-027 (a sent legal document is FROZEN as the document — PO
#           2026-08-30) · the in-app channel ruling (PO 2026-08-26, verbatim:
#           *"we dont have to worry about in-app message those are mostly FYI ;
#           hence we dont have worry about them"*) · CLAUDE.md hard-won law 7
#           (prove a guard RED before trusting it green) · law 13 (never ask the
#           same thing twice — and never let a new ruling silently overturn a
#           live one)
# ───────────────────────────────────────────────────────
"""Nineteen more classes are kept at send. The twentieth is not, and it is named.

⚠ **THIS FILE'S REASON FOR EXISTING IS THE TWENTIETH.** The ruling is a sentence
about a LIST — *"keep all of them"* — and four days earlier the same Product
Owner ruled the in-app channel out of the freeze entirely. A lane that reads the
newer sentence and sweeps `staff_bulk_summary` in with the rest has not gained a
feature; it has produced two genuine PO answers that disagree, which is precisely
the failure hard-won law 13 describes. **So the exclusion is asserted BY NAME
below, not left as an absence** — an absence is what the next lane deletes.

THE COUNT, AND WHY IT IS ASSERTED RATHER THAN TRUSTED
──────────────────────────────────────────────────────
The PO's signature was given against a measured figure: **41 template classes
exist, 21 are named by `CR-049` step 5b's scope table, 20 are not, and 19 of
those 20 are customer-facing.** That arithmetic is re-derived here from the
catalogue itself rather than transcribed from prose, so a lane that adds a
forty-second class finds out that it is outside the PO's signature instead of
inheriting a freeze decision nobody made.

⚠ **NINETEEN CLASSES ARE NOT NINETEEN KINDS, AND THE DIFFERENCE IS DELIBERATE.**
A `kind` names the DOCUMENT and `channel` is its own column — which is why the
21 already-ruled classes collapse onto 12 kinds (`sms_disconnect` and
`disconnect_notice_48_hour` are both `disconnect_notice`; `email_past_due` and
`sms_past_due` are both `dunning_letter`). The same collapse applies twice here:
the printed statement and the statement email are one document (A19 rule 1 names
BOTH — *"both the printed statement and the statement email must say nothing is
due"*), and bill-ready on email and on SMS is one document. So **19 classes map
onto 17 new kinds, taking the store's list from 16 to 33.** Both figures are
asserted, because reconciling them silently is what would hide a mistake in
either.
"""

from __future__ import annotations

import uuid

import pytest

from apps.notifications import catalogs, frozen_documents, models
from apps.tenancy import document_models

from tests.isolation_helpers import requires_postgres
from tests.test_cr049_t2_dispatch_freeze import (  # noqa: F401 — shared fixtures
    _cycle,
    docs_dir,
    email_on,
    provider_connected,
    queue_row,
    stub_adapter,
    stub_templates,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The in-app staff summary — the TWENTIETH class, and the one that stays out.
IN_APP_CLASS = "staff_bulk_summary"

#: The TWELVE template classes the catalogue gained AFTER the PO signed against
#: 41, dated by `git log -S` on `apps/notifications/catalogs.py`. They arrived
#: with no document kind, so once a provider was connected every one of them
#: HELD for ever (`DEF-NOT-8450`). **Fixed 2026-09-30**: kept under the same
#: `OQ-1164` ruling as the nineteen (coordinator judgement in the decision log,
#: not re-asked — law 13), and section 3b asserts each is now sent AND kept.
#: The list stays because it is the record of which classes that fix covered.
#:
#:   `534d3c21b` 2026-09-12  account_message                       (email)
#:   `fcdcbf02d` 2026-09-15  service_request_acknowledgement       (email)
#:                           service_request_acknowledgement_fee   (email)
#:                           service_request_more_info             (email)
#:                           service_request_refused               (email)
#:   `e7a0bcb7b` 2026-09-15  service_request_approved              (email)
#:   `24f990e56` 2026-09-16  new_connect_quote                     (email)
#:                           new_connect_confirmed                 (email)
#:   `9fafd7c99` 2026-09-20  transfer_to_buyer                     (email)
#:                           transfer_to_seller                    (email)
#:                           transfer_field_visit_sms              (sms)
#:   `aff5f079d` 2026-09-27  email_scheduled_report                (email)
ADDED_AFTER_THE_RULING: frozenset[str] = frozenset(
    {
        "account_message",
        "service_request_acknowledgement",
        "service_request_acknowledgement_fee",
        "service_request_more_info",
        "service_request_refused",
        "service_request_approved",
        "new_connect_quote",
        "new_connect_confirmed",
        "transfer_to_buyer",
        "transfer_to_seller",
        "transfer_field_visit_sms",
        "email_scheduled_report",
        # ⚠ `staff_field_work` (FIELD-2, 2026-10-04) WAS LISTED HERE UNTIL
        # 2026-10-05 (`DEF-NOT-9670`, lane FIX-7) and is NOT a kept class: it
        # is IN-APP, to the utility's own staff (`catalogs.CATALOGS` gives it
        # `CHANNEL_IN_APP`), it has no document kind, and `in_app` is not a
        # freeze channel (PO 2026-08-26, *"those are mostly FYI"*). This list
        # is the late classes that are SENT AND KEPT, so it failed twice here —
        # `KeyError` in the 33-kind arithmetic and "still holds" in section 3b.
        # It belongs on `NOT_A_DOCUMENT` ALONE, which it already was, and
        # `LATE_NOT_A_DOCUMENT` below takes it out of the 41 by name.
        # 2026-10-04 · CR-168-BRC10 P6.1 (lane SRV-5, `2.517.0`) — the visit,
        # told to the customer: kept as `service_appointment`, the kind the
        # booked letter and `transfer_field_visit_sms` already file under.
        "service_visit_moved",
        "sms_visit_booked",
        "sms_visit_moved",
        "sms_technician_on_the_way",
    }
)

#: The ONLY template classes that are not a kept document — each with its
#: reason. The guard in section 1 allows a class to lack a kind ONLY if it is
#: here, so a new class added without a kind fails the moment it lands instead
#: of holding silently in production for a fortnight, which is what
#: `DEF-NOT-8450` was. ⚠ **ADDING A CLASS HERE IS A RULING, NOT A TIDY-UP:**
#: the PO's `OQ-1164` answer is that customer documents are kept, not judged one
#: by one, so a new entry needs a reason as strong as the one below.
NOT_A_DOCUMENT: dict[str, str] = {
    IN_APP_CLASS: (
        "in-app only — the PO ruled the in-app channel out of the freeze on "
        "2026-08-26 ('those are mostly FYI'), and in_app is not a freeze channel"
    ),
    # CR-168-BRC10 §F (FIELD-2, 2026-10-04) — the SAME reason, not a new one:
    # an in-app message to the utility's own staff, never a customer document.
    "staff_field_work": (
        "in-app only, to the utility's staff (a field job closed, its photos in, "
        "or items to review) — in_app is not a freeze channel (PO 2026-08-26)"
    ),
}


#: Classes added AFTER the ruling that are NOT documents — each on
#: `NOT_A_DOCUMENT` with its reason. Subtracted by name in section 1 so the 41
#: the PO signed against is still re-derived (`DEF-NOT-9670`).
LATE_NOT_A_DOCUMENT: frozenset[str] = frozenset({"staff_field_work"})

#: ⚠ **`CR-182-BRC10` (2026-10-14, lane HIGHUSE) — A LATE CLASS WITH A KIND OF
#: ITS OWN.** `email_high_usage_alert` (a reading flagged high) is SENT and
#: KEPT under the same `OQ-1164` ruling, as kind `high_usage_alert`
#: (`tenancy/0062`). Kept apart from `ADDED_AFTER_THE_RULING` because that set
#: is `DEF-NOT-8450`'s record and the ten kinds it added are asserted by number.
ADDED_BY_CR182: dict[str, str] = {
    "email_high_usage_alert": "high_usage_alert",
    # `CR-188-BRC10` + `DEF-CWP-10381` (2026-10-22) — the account-access
    # emails, kept with the link redacted (decision log 2026-10-22). Same shape:
    # late classes, ONE kind of their own (`tenancy/0065_cr188`).
    "staff_user_invite": "account_access_email",
    "staff_password_reset_link": "account_access_email",
    "portal_password_reset": "account_access_email",
}

#: `CR-189-BRC10` (2026-10-22) — three Account access emails, kept under the
#: same ruling with the one-time code redacted in the kept copy (decision log
#: 2026-10-22, *"Account-access emails are KEPT like every other document"*).
#: Their kind, `account_access_email`, is added to the store's CHECK by
#: `CR-188-BRC10`'s tenancy migration.
ADDED_BY_CR189: dict[str, str] = {
    "portal_enrolment_code": "account_access_email",
    "portal_email_change_code": "account_access_email",
    "portal_email_changed_notice": "account_access_email",
}

#: `CR-190-BRC10` (2026-10-22) — the click-to-accept agreement email and its
#: confirmation, kept under the same `OQ-1164` ruling as CORRESPONDENCE about
#: the account (`frozen_documents`, lane AGREEMENT). They REUSE an existing
#: kind, so the kind count below does not move. Added at the four-branch merge.
ADDED_BY_CR190: dict[str, str] = {
    "email_agreement_request": "account_message",
    "email_agreement_accepted": "account_message",
}


def all_template_classes() -> set[str]:
    """Every template class this product has, computed from the catalogue.

    Deliberately NOT a hand-written list: the PO's signature was given against a
    measurement, and a transcription cannot notice that the thing it measured
    has moved.
    """
    return (
        set(catalogs.CATALOGS) | set(catalogs.AUTHORED_CATALOGS) | set(catalogs.CONTRACT_CATALOGS)
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE ARITHMETIC THE PO SIGNED AGAINST
# ══════════════════════════════════════════════════════════════════════════
def test_oq1164__forty_one_classes_twenty_one_ruled_twenty_not_nineteen_frozen():
    """41 / 21 / 20 / 19 — re-derived, not transcribed.

    If this fails, the catalogue has moved since the ruling and the new class is
    OUTSIDE the PO's signature. That is a question to put to them, not a number
    to update here (hard-won law 13, and the standing rule that a signature
    covers only what was shown).
    """
    every = all_template_classes()
    # ⚠ AMENDED TWICE ON 2026-09-30. This line read `assert len(every) == 41`
    # and was red from 2026-09-12 (`534d3c21b`) — the twelve classes added
    # since, which nobody read and which became `DEF-NOT-8450`. The forward
    # protection that count was meant to give now lives in
    # `test_oq1164__every_template_class_is_kept_or_named_as_not_a_document`,
    # which fails on ANY class with no kind and no stated reason — a stronger
    # question than "did the number move", because it is the one that bit.
    # What stays here is the arithmetic the PO signed against, re-derived with
    # the twelve later classes (now kept too) taken back out by name.
    assert ADDED_AFTER_THE_RULING <= every, "a named late class left the catalogue — update the list"
    assert LATE_NOT_A_DOCUMENT <= set(NOT_A_DOCUMENT), "a late non-document needs its stated reason"
    every = (
        every
        - ADDED_AFTER_THE_RULING
        - LATE_NOT_A_DOCUMENT
        - set(ADDED_BY_CR182)
        - set(ADDED_BY_CR189)
        - set(ADDED_BY_CR190)
    )
    assert len(every) == 41, "the ruling was measured against 41 template classes"

    ruled_by_step_5b = {
        # The 21 classes `CR-049` step 5b's scope table already named, which had
        # kinds before this ruling. Written out so the split is visible.
        "bill_residential",
        "bill_commercial",
        "disconnect_notice",
        "disconnect_notice_10_day",
        "disconnect_notice_5_day",
        "disconnect_notice_48_hour",
        "sms_disconnect",
        "dunning",
        "email_past_due",
        "sms_past_due",
        "receipt",
        "email_payment_receipt",
        "sms_payment_received",
        "email_payment_failed",
        "plan_notice_upcoming",
        "plan_notice_missed",
        "plan_notice_void",
        "contract_payment_plan",
        "email_welcome",
        "email_move_out_final",
        "email_plan_change",
    }
    assert len(ruled_by_step_5b) == 21
    assert ruled_by_step_5b <= every

    unruled = every - ruled_by_step_5b
    assert len(unruled) == 20, "twenty classes were outside the PO's scope table"
    assert IN_APP_CLASS in unruled

    frozen_by_this_ruling = unruled - {IN_APP_CLASS}
    assert len(frozen_by_this_ruling) == 19, (
        "NINETEEN customer-facing classes are frozen at send. The twentieth is the "
        "in-app staff summary and it stays out by the channel ruling of 2026-08-26."
    )
    # Every one of the nineteen now has a kind, and it is a real kind.
    for code in frozen_by_this_ruling:
        kind = frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS.get(code)
        assert kind is not None, f"{code} is one of the nineteen and must have a kind"
        assert kind in document_models.DOCUMENT_KINDS


def test_oq1164__every_template_class_is_kept_or_named_as_not_a_document():
    """THE GUARD `DEF-NOT-8450` WAS MISSING (2026-09-30).

    Every class the catalogues define must EITHER map to a document kind the
    store accepts OR be named in `NOT_A_DOCUMENT` with a reason. A class that is
    neither is held by the dispatcher for ever on any tenant with a connected
    provider, and nothing on a screen says so — twelve classes did exactly that
    from 12 to 30 September.

    ⚠ **PROVED RED (hard-won law 7), IN THIS HARNESS:** with a dummy class
    `zz_dummy_unkept_notice` added to `catalogs.AUTHORED_CATALOGS` for one run,
    this case failed, verbatim:
        AssertionError: template classes with no kept-document kind and no
        stated reason: ['zz_dummy_unkept_notice']
    """
    kinds = frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS
    every = all_template_classes()

    unkept = sorted(code for code in every if code not in kinds and code not in NOT_A_DOCUMENT)
    assert unkept == [], (
        f"template classes with no kept-document kind and no stated reason: {unkept}"
    )
    for code in every & set(kinds):
        assert kinds[code] in document_models.DOCUMENT_KINDS, (
            f"{code} maps to {kinds[code]!r}, which the store's CHECK does not accept"
        )
    # A class cannot be both kept and declared not a document, and every
    # declared exception must still exist and still carry a reason.
    assert not set(NOT_A_DOCUMENT) & set(kinds)
    for code, reason in NOT_A_DOCUMENT.items():
        assert code in every, f"{code} is named as not a document but no longer exists"
        assert reason.strip()


def test_oq1164__the_store_gained_seventeen_kinds_taking_the_list_from_16_to_33():
    """19 classes → 17 kinds → a list of 33. All three figures, on the record.

    A `kind` names the document and `channel` is a separate column, so two pairs
    of the nineteen share a kind: the printed statement with the statement email,
    and bill-ready on email with bill-ready on SMS. **That is the same collapse
    the twelve already-ruled kinds use**, not a shortcut — and stating the two
    numbers separately is what stops a later reader "fixing" 17 up to 19 and
    encoding the channel into the kind.
    """
    # ⚠ AMENDED 2026-09-30 — THE STORE'S LIST IS 38, AND THE FIVE ADDED SINCE
    # ARE NOT MESSAGES. They are kinds for files a person UPLOADS into the
    # store, which no template class maps to and the dispatcher never freezes,
    # so they are subtracted by name and the ruling's 33 still stands. Dated by
    # `git log -S` on `apps/tenancy/document_models.py`; this assertion was red
    # from the first of them:
    #   `eac1f58bb` 2026-09-05  work_order_photo · work_order_signature ·
    #                           work_order_report   (CR-070 wave K, K1)
    #   `678c49738` 2026-09-19  service_request_document (a clerk's attachment)
    #   `6973e1d4c` 2026-09-24  supplier_invoice    (P5.11; kept seven years,
    #                           OQ-LED-12628 closed by the PO 2026-09-25)
    #   CR-168-BRC10 2026-10-04 work_template_help  (P3.14, a template's help
    #                           document — lane SRV-3, tenancy/0059)
    #   CR-168-BRC10 2026-10-04 work_certificate_proof (image 33, a technician's
    #                           certificate scan — lane SRV-4, tenancy/0060)
    uploaded_not_sent = {
        "work_order_photo",
        "work_order_signature",
        "work_order_report",
        "service_request_document",
        "supplier_invoice",
        "work_template_help",
        "work_certificate_proof",
        # CR-172-BRC10 2026-10-04 tenant_logo (the utility's uploaded logo,
        # tenancy/0061) — `DEF-GOV-10150`: never added here, so this count was
        # red from 9b6b8ae50 until 2026-10-14.
        "tenant_logo",
    }
    assert uploaded_not_sent <= set(document_models.DOCUMENT_KINDS)
    assert not uploaded_not_sent & set(frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS.values()), (
        "an uploaded-file kind is now the kind of a SENT message — it is no longer "
        "outside this ruling's count, and the 33 below must be re-derived"
    )
    assert len(set(document_models.DOCUMENT_KINDS)) == len(document_models.DOCUMENT_KINDS), (
        "no kind may be listed twice"
    )
    # ⚠ AND THE TEN KINDS `DEF-NOT-8450` ADDED ON 2026-09-30 for the twelve
    # late classes (38 → 48, `tenancy/0054`). They are SENT kinds, kept under
    # the same ruling, named here so the ruling's own 33 is still re-derived.
    kept_by_def_not_8450 = {
        frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS[code]
        for code in ADDED_AFTER_THE_RULING
    } - {"service_appointment"}  # the meter-visit SMS REUSES an existing kind
    assert len(kept_by_def_not_8450) == 10
    assert kept_by_def_not_8450 <= set(document_models.DOCUMENT_KINDS)
    for code, kind in (
        *ADDED_BY_CR182.items(),
        *ADDED_BY_CR189.items(),
        *ADDED_BY_CR190.items(),
    ):
        assert frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS[code] == kind
    # CR-189's three REUSE CR-188's kind; they add no kind of their own.
    assert set(ADDED_BY_CR189.values()) <= set(ADDED_BY_CR182.values())
    assert (
        len(
            set(document_models.DOCUMENT_KINDS)
            - uploaded_not_sent
            - kept_by_def_not_8450
            - set(ADDED_BY_CR182.values())
        )
        == 33
    )

    new_kinds = {
        "statement",
        "bill_ready_notice",
        "corrected_bill_notice",
        "bill_insert",
        "refund_confirmation",
        "credit_note_confirmation",
        "deposit_notice",
        "account_closed_letter",
        "autopay_confirmation",
        "writeoff_notice",
        "service_agreement",
        "deposit_agreement",
        "autopay_authorization",
        "service_appointment",
        "service_work_completed",
        "service_outage_notice",
        "service_door_hanger",
    }
    assert len(new_kinds) == 17
    assert new_kinds <= set(document_models.DOCUMENT_KINDS)

    # The two deliberate collapses, asserted so neither is split later.
    kinds = frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS
    assert kinds["statement"] == kinds["email_statement"] == "statement"
    assert kinds["email_bill_ready"] == kinds["sms_bill_ready"] == "bill_ready_notice"


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE TWENTIETH — ASSERTED BY NAME (law 13)
# ══════════════════════════════════════════════════════════════════════════
def test_oq1164__the_in_app_staff_summary_is_still_out_and_is_named_here():
    """A ruling on a LIST does not overturn a ruling on a CHANNEL.

    PO, 2026-08-26, verbatim: *"we dont have to worry about in-app message those
    are mostly FYI ; hence we dont have worry about them"*. `staff_bulk_summary`
    is the product talking to the utility's own clerk inside the product — not a
    letter to a customer — and `in_app_messages.body` already stores its render,
    so nothing is lost by leaving it out.

    ⚠ **DO NOT "COMPLETE" THE MAP BY ADDING THIS CLASS.** Its absence is the
    ruling, and this test is here so that removing it is a deliberate act with a
    PO ruling behind it rather than a tidy-up.
    """
    assert IN_APP_CLASS not in frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS
    assert catalogs.CATALOGS[IN_APP_CLASS].channel == models.CHANNEL_IN_APP
    # And the channel itself is out of the freeze, which is the deeper guarantee:
    # even if the class were mapped, an in-app row is exempt before a kind is read.
    assert models.CHANNEL_IN_APP not in frozen_documents.FREEZE_CHANNELS
    assert models.CHANNEL_IN_APP not in document_models.CHANNELS


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE BEHAVIOUR — UNSENDABLE BEFORE, SENDABLE AND FROZEN AFTER
# ══════════════════════════════════════════════════════════════════════════
#: One representative per document family among the nineteen, with the channel
#: it actually goes out on. These are the rows that HELD before this change.
NEWLY_SENDABLE = [
    ("statement", models.CHANNEL_PRINT),
    ("bill_insert", models.CHANNEL_PRINT),
    ("writeoff_notice", models.CHANNEL_PRINT),
    ("service_door_hanger", models.CHANNEL_PRINT),
    ("contract_deposit", models.CHANNEL_PRINT),
    ("contract_service_agreement", models.CHANNEL_PRINT),
    ("contract_autopay_authorization", models.CHANNEL_PRINT),
    ("email_bill_ready", models.CHANNEL_EMAIL),
    ("email_statement", models.CHANNEL_EMAIL),
    ("email_corrected_bill", models.CHANNEL_EMAIL),
    ("email_refund_issued", models.CHANNEL_EMAIL),
    ("email_credit_issued", models.CHANNEL_EMAIL),
    ("email_deposit", models.CHANNEL_EMAIL),
    ("email_account_closed", models.CHANNEL_EMAIL),
    ("email_autopay", models.CHANNEL_EMAIL),
    ("service_appointment", models.CHANNEL_EMAIL),
    ("service_work_completed", models.CHANNEL_EMAIL),
    ("service_outage_notice", models.CHANNEL_EMAIL),
    ("sms_bill_ready", models.CHANNEL_SMS),
]


def test_oq1164__the_representative_list_covers_all_nineteen():
    """The table above IS the nineteen — not a sample somebody trimmed."""
    assert len(NEWLY_SENDABLE) == 19
    assert len({code for code, _ in NEWLY_SENDABLE}) == 19


@pytest.mark.parametrize("template_code,channel", NEWLY_SENDABLE)
def test_oq1164__each_of_the_nineteen_now_sends_and_is_frozen(
    template_code, channel, brazos, stub_adapter, stub_templates, docs_dir, email_on
):
    """The shape that matters: HELD before this change, sent AND kept after.

    ⚠ **PROVED RED FIRST (hard-won law 7).** Before the nineteen kinds existed,
    every one of these nineteen rows held on `document_kind_not_ruled` and this
    case reported, verbatim:

        E   AssertionError: statement must now be SENT, not held
        E   assert 'queued' == 'sent'

    A row that sends without a frozen copy would be worse than one that holds, so
    both halves are asserted together: the row reached `sent`, the provider saw
    it, and `reproduce()` can hand back the ORIGINAL rather than a re-render.

    ⚠ **RED FROM 2026-09-04 TO 2026-09-30 WITH THAT SAME `'queued' == 'sent'`,
    AND IT WAS NOT THIS HOLD.** `d471e8680` (`CR-069` wave E) made the route ask
    whether the TENANT has connected a provider, separately from whether an
    adapter exists; this fixture stubbed only the adapter, so every row rested
    on `provider_not_connected` before the freeze was reached. Measured: all
    nineteen green at the parent `2d771c61d`, all nineteen red at `d471e8680`.
    The product was right — no connection, no send (A15 addendum) — and the
    harness now says the tenant IS connected (`provider_connected`, pulled in
    through `stub_adapter`). **The identical failure text for two different
    causes is why the hold check below reads the problem CODE, never the
    status alone.**
    """
    with tenant_ctx(brazos):
        row = queue_row(brazos, channel=channel, template_code=template_code)
        result = _cycle(channel)
        row.refresh_from_db()

        assert row.status == models.STATUS_SENT, f"{template_code} must now be SENT, not held"
        held = [p for p in result.problems if p["code"] == frozen_documents.FREEZE_KIND_UNRULED]
        assert held == [], f"{template_code} is ruled now and must not hold on OQ-1164"
        assert str(row.pk) in stub_adapter.handed_over

        # ...and the copy exists, which is the whole point of the ruling.
        reproduction = frozen_documents.reproduce(row)
        assert reproduction.is_original, (
            f"{template_code} reached `sent` with no frozen artefact — BR-NOT-027 makes "
            "keeping the letter a PRECONDITION of sending it"
        )
        assert reproduction.document.kind == (
            frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS[template_code]
        )


# ══════════════════════════════════════════════════════════════════════════
# 3b · THE TWELVE ADDED SINCE — SENT AND KEPT (DEF-NOT-8450, fixed 2026-09-30)
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("template_code", sorted(ADDED_AFTER_THE_RULING))
def test_oq1164__each_of_the_twelve_added_since_now_sends_and_is_kept(
    template_code, brazos, stub_adapter, stub_templates, docs_dir, email_on
):
    """The same shape as the nineteen: HELD before, sent AND kept after.

    ⚠ **UNTIL 2026-09-30 THIS CASE ASSERTED THE OPPOSITE — THAT EACH OF THE
    TWELVE HOLDS — AND THAT WAS DELIBERATE.** It was the test written with the
    hold (hard-won law 2) so that the day the hold ended it would go red and
    name the class. It ended with the coordinator's recorded judgement of
    2026-09-30 (decision log, `DEF-NOT-8450`): the twelve are the same question
    as `OQ-1164` with newer members, the PO answered that question on
    2026-08-30 — *"My recommendation is to keep all of them. - OKY KEEP THEM"*,
    under *"The twenty unmapped classes are kept, not judged one by one"* — so
    they are kept, and it was not put back to the PO (law 13).

    **PROVED RED FIRST:** flipped before any kind existed, all twelve failed,
    verbatim, `AssertionError: account_message still holds on an unruled kind`
    (and the same for the other eleven).

    The problem CODE is checked as well as the status, because a row can also
    rest `queued` on `provider_not_connected` — which this file once mistook
    for the hold it was looking for.
    """
    channel = catalogs.CATALOGS[template_code].channel
    assert channel in frozen_documents.FREEZE_CHANNELS
    with tenant_ctx(brazos):
        row = queue_row(brazos, channel=channel, template_code=template_code)
        result = _cycle(channel)
        row.refresh_from_db()

        held = [p for p in result.problems if p["code"] == frozen_documents.FREEZE_KIND_UNRULED]
        assert held == [], f"{template_code} still holds on an unruled kind"
        assert row.status == models.STATUS_SENT, result.problems
        assert str(row.pk) in stub_adapter.handed_over

        reproduction = frozen_documents.reproduce(row)
        assert reproduction.is_original, f"{template_code} was sent with no kept copy"
        assert reproduction.document.kind == (
            frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS[template_code]
        )


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE REFUSAL THAT MADE THIS SAFE IS UNCHANGED
# ══════════════════════════════════════════════════════════════════════════
class _FakeRow:
    """Just enough row to ask `document_kind` a question."""

    def __init__(self, template_code):
        self.template_code = template_code


def test_oq1164__an_unknown_template_class_still_holds_the_row():
    """Nineteen classes were ruled on. The HOLD itself was not weakened.

    ⚠ **THIS PATH IS NOW UNREACHABLE FROM THE CATALOGUE, AND IT IS KEPT ANYWAY.**
    After this ruling every one of the 41 classes either has a kind or is in-app
    (which exits as exempt before a kind is ever read), so no catalogued class
    can reach `document_kind_not_ruled` today. It stays because the NEXT class
    somebody adds has no kind, and the safe answer for it is the one that was
    correct here: hold and ask, never guess a value into a seven-year legal
    record.

    ⚠ **THE FIRST PARAGRAPH STOPPED BEING TRUE ON 2026-09-12** — the next class
    DID arrive, and eleven more after it: section 3b and `DEF-NOT-8450`. The
    second paragraph is exactly what happened to them.
    """
    assert frozen_documents.document_kind(_FakeRow("a_class_nobody_has_added_yet")) is None
    assert frozen_documents.document_kind(_FakeRow("")) is None
    assert frozen_documents.document_kind(_FakeRow(None)) is None


def test_oq1164__mark_sent_still_requires_the_freeze_answer():
    """Item 3 of the ruling's scope: the precondition is untouched.

    `_mark_sent` takes the freeze outcome as a REQUIRED argument. Widening WHICH
    classes may freeze must not become a licence to send one that did not.
    """
    import inspect

    from apps.notifications import dispatcher

    signature = inspect.signature(dispatcher._mark_sent)
    assert "freeze" in signature.parameters
    assert signature.parameters["freeze"].default is inspect.Parameter.empty, (
        "the freeze answer must stay REQUIRED — a default would let a future call "
        "site omit it and send an unfrozen legal document"
    )


# ══════════════════════════════════════════════════════════════════════════
# 5 · LAW 14 — THE CONSTRAINT PATH, PROVED ON REAL POSTGRESQL
# ══════════════════════════════════════════════════════════════════════════
# This migration widens a CHECK constraint, and a CHECK violation is exactly the
# case hard-won law 14 is about: it raises `IntegrityError` on both vendors, but
# only PostgreSQL ABORTS THE SURROUNDING TRANSACTION with it, and
# `config/settings/test.py` hardcodes in-memory SQLite, which has no aborted-
# transaction state. So a `try: … except IntegrityError: continue` over the
# nineteen new kinds would pass the entire default suite and lose a whole
# dispatch cycle's work the first time a real row was refused.
#
# ⚠ **THE FINDING, AND IT IS THE REASON THIS SECTION EXISTS:** the dispatcher
# DOES catch-and-continue per row — `freeze_for_dispatch` returns a hold and
# `_dispatch_channel` moves to the next row, all inside ONE outer
# `transaction.atomic()` covering the whole batch. What saves it is that the
# thing it catches is `DocumentStoreError`, a PYTHON refusal raised by
# `document_store.store`'s `_require_choice(kind, DOCUMENT_KINDS, "kind")`
# **before the database is touched at all**. The CHECK constraint is a floor
# that the shipped path never reaches.
#
# That makes the Python guard load-bearing in a way that is invisible from the
# code — it looks like belt-and-braces validation and it is actually the only
# reason a bad kind cannot poison a batch of 500. These cases pin that down so
# the next lane cannot "simplify" the guard away and discover it in production.

#: The sixteen kinds the constraint held before migration 0028.
KINDS_BEFORE_OQ1164 = (
    "bill",
    "disconnect_notice",
    "dunning_letter",
    "payment_receipt",
    "failed_payment_notice",
    "payment_plan_instalment_due",
    "payment_plan_instalment_missed",
    "payment_plan_voided",
    "move_in_welcome",
    "move_out_final_bill",
    "plan_change_confirmation",
    "payment_plan_agreement",
    "exemption_certificate",
    "remittance_receipt",
    "account_document",
    "import_source_file",
)


@requires_postgres
def test_oq1164__an_unruled_kind_is_refused_in_python_before_postgres_sees_it(brazos, docs_dir):
    """The shipped path never reaches the CHECK constraint — proved, not assumed.

    Run on live PostgreSQL 16. The refusal arrives as `DocumentStoreError` from
    `_require_choice`, the database is never asked, and **the surrounding
    transaction is still usable afterwards** — which is what lets the dispatcher
    hold one row and carry on with the other 499.
    """
    from django.db import transaction

    from apps.tenancy import document_store

    with tenant_ctx(brazos):
        with transaction.atomic():
            with pytest.raises(document_store.DocumentStoreError) as refused:
                document_store.store(
                    kind="not_a_ruled_kind",
                    source_type="outbound_message",
                    source_id=uuid.uuid4(),
                    channel=models.CHANNEL_PRINT,
                    content_type="text/plain",
                    display_name="probe/2026/08/probe.txt",
                    payload=b"probe",
                    process="tests.oq1164",
                )
            assert "kind" in str(refused.value)

            # THE POINT: the transaction is NOT poisoned, because no statement
            # ever failed. A query here is what would raise
            # `InFailedSqlTransaction` if the refusal had come from the database.
            assert document_models.StoredDocument.objects.count() >= 0


@requires_postgres
def test_oq1164__bypassing_the_python_guard_hits_the_constraint_on_postgres(brazos, docs_dir):
    """Why the Python guard is load-bearing, demonstrated rather than asserted.

    ⚠ **THIS CASE DELIBERATELY BYPASSES `document_store.store` TO REACH THE
    CONSTRAINT**, which is the only way to see what the database does.

    **MEASURED, NOT ASSUMED (hard-won law 1 — a comment claiming a guarantee is
    not the guarantee).** The same INSERT was run on live PostgreSQL 16 WITHOUT
    the savepoint below, in the exact `except IntegrityError: … continue` shape
    law 14 forbids, and it reported, verbatim, 2026-08-30:

        === CAUGHT (the naive `except IntegrityError: continue`) ===
        IntegrityError : new row for relation "stored_documents" violates check
        constraint "ck_stored_documents_kind"

        === NOW DOING THE NEXT ROW'S WORK ===
        POISONED: django.db.utils.InternalError
        current transaction is aborted, commands ignored until end of transaction
        block

    So the refusal is caught and the batch dies anyway — the dispatcher's outer
    `transaction.atomic()` would discard the WHOLE cycle rather than hold one
    row. ⚠ Note the class: Django surfaces it as `django.db.utils.InternalError`,
    not as a `psycopg` `InFailedSqlTransaction`, which is law 14's warning about
    reading the cause chain rather than the first exception you catch.

    ⚠ **AND THE DEFAULT SUITE CANNOT SEE ANY OF THIS.** Under
    `config/settings/test.py` this case does not fail — it is SKIPPED, because
    `requires_postgres` is the only honest thing to do on a vendor with no
    aborted-transaction state. A green default run is not evidence here.
    """
    from django.db import IntegrityError, connection, transaction

    with tenant_ctx(brazos):
        with transaction.atomic():
            # The nested atomic() IS the savepoint. It is not tidiness; it is the
            # only thing that lets the outer transaction survive to assert.
            with pytest.raises(IntegrityError) as refused:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO stored_documents "
                            "(id, tenant_id, kind, source_type, source_id, channel, "
                            " storage_key, storage_backend, content_hash, byte_length, "
                            " content_type, display_name, stored_at, stored_by_process) "
                            "VALUES (gen_random_uuid(), %s, 'not_a_ruled_kind', "
                            "'outbound_message', gen_random_uuid(), 'pdf_print', "
                            "'k', 'filesystem', 'h', 1, 'text/plain', 'n', now(), 'p')",
                            [str(brazos.id)],
                        )
            assert "ck_stored_documents_kind" in str(refused.value)

            # Usable again ONLY because of the savepoint above.
            assert document_models.StoredDocument.objects.count() >= 0


@requires_postgres
def test_oq1164__the_widened_constraint_accepts_all_seventeen_new_kinds_on_postgres(
    brazos, docs_dir
):
    """Migration 0028 really did widen the constraint in the database.

    The Python list and the CHECK constraint are two separate statements of the
    same rule (hard-won law 1: a comment claiming a guarantee is not the
    guarantee), so this writes one real row per new kind through the store and
    lets PostgreSQL be the judge.
    """
    from apps.tenancy import document_store

    # ⚠ AMENDED 2026-09-30. This read every kind not in `KINDS_BEFORE_OQ1164`
    # and asserted there were 17, so it has been red ON POSTGRES since
    # 2026-09-05 (`eac1f58bb`, the three work-order kinds) — and it runs only
    # on PostgreSQL, so the default suite skipped it and nobody saw. Every
    # kind added since is taken back out BY NAME, and the ten `DEF-NOT-8450`
    # kinds get their own PostgreSQL case below.
    later = {
        "work_order_photo",
        "work_order_signature",
        "work_order_report",
        "service_request_document",
        "supplier_invoice",
        *KINDS_ADDED_BY_DEF_NOT_8450,
        # `DEF-GOV-10150` (2026-10-14) — four kinds added after the 2026-09-30
        # amendment, each by name: uploaded files (work help, certificate
        # proof, the utility logo) and CR-182's sent high-usage alert.
        "work_template_help",
        "work_certificate_proof",
        "tenant_logo",
        "high_usage_alert",
        # `CR-188-BRC10` / `DEF-CWP-10381` (2026-10-22) — the account-access
        # email, kept with its link redacted; its PostgreSQL proof is the reset
        # test's freeze, which stores a real row of this kind through the CHECK.
        "account_access_email",
    }
    new_kinds = [
        k for k in document_models.DOCUMENT_KINDS if k not in KINDS_BEFORE_OQ1164 and k not in later
    ]
    assert len(new_kinds) == 17

    with tenant_ctx(brazos):
        for kind in new_kinds:
            stored = document_store.store(
                kind=kind,
                source_type="outbound_message",
                source_id=uuid.uuid4(),
                channel=models.CHANNEL_PRINT,
                content_type="text/plain",
                display_name=f"{kind}/2026/08/probe.txt",
                payload=f"probe for {kind}".encode("utf-8"),
                process="tests.oq1164",
            )
            assert stored.kind == kind


#: The ten kinds `tenancy/0054` added (`DEF-NOT-8450`, 2026-09-30).
KINDS_ADDED_BY_DEF_NOT_8450 = (
    "account_message",
    "service_request_acknowledgement",
    "service_request_more_info",
    "service_request_approved",
    "service_request_refused",
    "new_connection_quote",
    "new_connection_confirmation",
    "property_sale_buyer_letter",
    "property_sale_seller_letter",
    "scheduled_report_notice",
)


@requires_postgres
def test_def_not_8450__migration_0054_accepts_the_ten_new_kinds_on_postgres(brazos, docs_dir):
    """`tenancy/0054` really widened the CHECK — one real row per new kind.

    SQLite does not enforce `ck_stored_documents_kind`, so without this case the
    twelve classes would be green in the default suite and refused by the
    database the first time one was kept (`DEF-TEN-6425` is that exact shape).
    Also measured by hand on PostgreSQL 16 on 2026-09-30: an `account_message`
    row REFUSED at `0053`, ACCEPTED at `0054`, and a rollback to `0053` over it
    REFUSED with `ck_stored_documents_kind … is violated by some row`.
    """
    from apps.tenancy import document_store

    assert set(KINDS_ADDED_BY_DEF_NOT_8450) <= set(document_models.DOCUMENT_KINDS)
    with tenant_ctx(brazos):
        for kind in KINDS_ADDED_BY_DEF_NOT_8450:
            stored = document_store.store(
                kind=kind,
                source_type="outbound_message",
                source_id=uuid.uuid4(),
                channel=models.CHANNEL_EMAIL,
                content_type="message/rfc822",
                display_name=f"{kind}/2026/09/probe.eml",
                payload=f"Subject: probe\r\n\r\nprobe for {kind}".encode("utf-8"),
                process="tests.def_not_8450",
            )
            assert stored.kind == kind
