# ── Trace ──────────────────────────────────────────────
# Change:   CR-049 tasks 2 + 7 — the dispatcher freezes what it sends, and a
#           row that reached `sent` without a frozen copy SAYS SO rather than
#           having a fresh render put in its place.
# Rules:    BR-NOT-027 (a sent legal document is frozen AS THE DOCUMENT; a
#           reprint serves THAT, never a fresh render — PO 2026-08-30) ·
#           BR-NOT-024 (a send test is a rehearsal, not a document) ·
#           BR-BIL-026 · BR-NOT-025 (the pinned template version — PROVENANCE,
#           still required, see the PIN section below) · NFR-33 · NFR-35 ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 4 (immutability) ·
#           hard-won law 1 (a guarantee with no visible failure mode) ·
#           law 3 (defaults fail closed) · B2 §2 (no cross-module writes)
# Tests:    06-backend/tests/test_cr049_t2_dispatch_freeze.py
#           06-backend/tests/test_cr049_t5_rights_clause_reprint.py
# Impacts:  apps/notifications/dispatcher.py (calls `freeze_for_dispatch`
#           BEFORE the provider hand-off and cannot mark a row `sent` without
#           its answer) · CR-049 task 3's reprint route, which reads
#           `reproduce()` and must never render in its place.
# ───────────────────────────────────────────────────────
"""What the customer actually received, kept — and named honestly when it is not.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides **whether a legal document
may be sent at all** and **what is kept as the copy the customer read**, which is
the same authority `notices.py` and `rights_footer.py` already carry one step
earlier. It refuses to send a document it cannot keep; it decides which template
classes are legal documents (`DOCUMENT_KIND_BY_TEMPLATE_CLASS`) and which two
kinds are exempt; and it decides how a reproduction is SERVED, which is the
difference between a regulator seeing the letter and a regulator seeing a
convincing re-render. AI-authored 2026-08-30 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*); row in
`12-governance/09-human-review-ledger.md`, glob in
`10-scripts/gates/human_owned.txt`.

PO, 2026-08-30, verbatim: *"any legal document when send - it is freezed - we
should keep all underline data, but actual leter and PDF should be freeze - any
changes to tempalte or any items hsould be noted as changed; that way it will
keep the santity of the legal documents; otherwie everytime we reproduce it
using data in table, we might change something about it and that is not
correct"*.

`outbound_messages` has 32 columns and not one of them holds what the customer
read. This module is the notifications half of closing that: it turns ONE
rendered artefact into ONE frozen document in tenancy's store, and it answers
the question a reprint has to ask first — *is there an original, or am I about
to show somebody a re-render?*

⚠ THE FREEZE IS A PRECONDITION OF SENDING, NOT A CUTOVER
----------------------------------------------------------
Verified rather than assumed: `provider_seam.PLATFORM_ADAPTERS` carries `in_app`
and nothing else — print, email and SMS have no adapter, so **no customer has
ever received anything from this product**. That fact, and only that fact, is
what lets the dispatcher REFUSE to mark a row `sent` unless the artefact was
stored first: a guarantee with no exceptions and no era before it. The option
expires at go-live, which is why it is taken now.

So the ordering is deliberate and is the whole design: **freeze, THEN hand over
to the provider.** Freezing after the hand-off would create the one state this
rule cannot describe — a letter in the post with no copy of it, and a row the
dispatcher must either mark `sent` (breaking the guarantee) or leave `queued`
(lying about a message the customer is holding).

⚠ THE PIN IS NOT SUPERSEDED AND IS STILL REQUIRED
---------------------------------------------------
`BR-BIL-026` and `BR-NOT-025` stand unchanged. The pinned template version
(`template_id` + `template_version` + `template_language` on the row) is now
**PROVENANCE — WHICH WORDING WAS IN FORCE** — rather than the input a
reproduction renders from. **The two answer different questions and a reader who
collapses them will delete one:**

  * *"What did the customer read?"* → the frozen artefact, here.
  * *"Which authored version of the wording was in force when they read it?"* →
    the pin, and the archived template version it names, which is why
    `BR-NOT-025` still forbids deleting a version any sent document points at.

A frozen artefact with no pin cannot tell a regulator which approved wording was
used; a pin with no artefact cannot tell them what the letter said. Keep both.

WHAT IS FROZEN, PER CHANNEL (CR-049 step 5d(c))
-------------------------------------------------
| Channel | Frozen | Media type |
|---|---|---|
| `pdf_print` | the letter body exactly as handed to the print vendor | `text/plain` today — see the PDF note below |
| `email` | the rendered subject and body as sent, as a minimal RFC 5322 message | `message/rfc822` |
| `sms` | the text as sent | `text/plain` |
| `in_app` | **nothing new** | — |

`in_app` is out of scope by PO ruling — *"we dont have to worry about in-app
message those are mostly FYI ; hence we dont have worry about them"* — and
`in_app_messages.subject`/`body` already store their render at delivery, so
nothing is lost. A **send test** does not freeze either: `BR-NOT-024`'s third
bucket, *"a rehearsal addressed to the signed-in user"*, is not a legal
document, and `rule_service.py` carries the same sentence beside the code that
queues one.

⚠ **PRINT FREEZES THE TEXT WE ACTUALLY HAND OVER, NOT A PDF, AND THAT IS NOT
CR-049 TASK 6's ANSWER.** `CR-049` step 5d(c) says *"Print → the PDF bytes"* and
there are none: this product has no page-render library (`OQ-149`), the
printable classes render TEXT, and `dispatcher._payload` hands a print vendor
that text. Rendering a PDF *here*, at freeze time, would freeze a document the
customer never received — the exact substitution `BR-NOT-027` exists to forbid.
So this module freezes the payload as handed over and lets the media type follow
it: the day a renderer lands and the dispatcher hands over a PDF,
`application/pdf` is what gets frozen, with no change to this file's rule.
**Whether a separate PDF rendition must ALSO be frozen for print is `CR-049`
task 6 and another lane's; this is not that decision.**

⚠ EVERY CUSTOMER DOCUMENT NOW FREEZES — OQ-1164 IS CLOSED
-----------------------------------------------------------
`document_store.store` takes a `kind` from a closed list.
`DOCUMENT_KIND_BY_TEMPLATE_CLASS` below maps the pinned template class onto it,
and **it is now COMPLETE for every customer-facing class this product has.**

It was not, until 2026-08-30. Measured that day: **41 template classes exist, 21
were named by `CR-049` step 5b's scope table and 20 were not**, and all twenty
HELD rather than being assigned a guessed kind. That refusal was correct and is
the pattern — the kind list is a CHECK constraint, so widening it is a migration
and a decision, not a configuration edit a lane makes on its own. The
recommendation was put to the PO in plain English (keep all of them: storage is
a few kilobytes a message, and the risk runs one way only — keeping a document
you did not need costs almost nothing, failing to keep one you did need loses it
permanently) and they ruled, verbatim: *"My recommendation is to keep all of
them. - OKY KEEP THEM"*.

⚠ **NINETEEN OF THE TWENTY. `staff_bulk_summary` STAYS OUT** — the in-app staff
summary, ruled out by CHANNEL by the same PO on 2026-08-26, and **a ruling on a
LIST does not overturn a ruling on a CHANNEL.** It is unreachable here anyway
(an in-app row exits as exempt above, before a kind is read), and its absence is
asserted by name in the test file so a tidy-up cannot restore it.

**THE HOLD ITSELF IS UNCHANGED AND IS STILL THE RIGHT ANSWER.** No catalogued
class can reach `FREEZE_KIND_UNRULED` today, but the code path stays: the next
class somebody adds has no kind, and holding it — a refusal per row rather than
an exception that ends the cycle for the other 499 — is the prime directive's
`raise NotImplementedError("OQ-###")` in the shape a batch dispatcher can carry.
Nineteen classes were ruled on; the freeze was not weakened.

⚠ THE MAP IS KEYED ON THE PINNED TEMPLATE CLASS, NOT ON `event_key`
---------------------------------------------------------------------
`outbound_messages.event_key` is the newer and more precise vocabulary, and it
is **NULL on every row this product writes today** — `notices.generate_disconnect
_notice` and `generate_reminder` both call `queue_document` without one, and
`queue_document`'s own docstring says *"every caller in the product still omits
it"*. A map keyed on it would answer "unruled" for the very document
(`DEF-2504`'s 48-hour certified notice) this rule was written for. The template
class is pinned on every row at queue time, never re-resolved, and names the
WORDING — which is what a document IS. When wave B finishes wiring event keys,
that is a second key for the same fact and one of the two should go; this
sentence is here so the next lane picks deliberately rather than adding a
fallback that lets the two disagree.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from apps.notifications import models
from apps.tenancy import document_store

# ═══════════════════════════════════════════════════════════════════════════
# WHAT FREEZES
# ═══════════════════════════════════════════════════════════════════════════

#: The three channels a customer document leaves on. `in_app` is absent by PO
#: ruling; see the module docstring.
FREEZE_CHANNELS: frozenset[str] = frozenset(
    {models.CHANNEL_PRINT, models.CHANNEL_EMAIL, models.CHANNEL_SMS}
)

#: `models.SOURCE_TYPES` kinds that are NOT legal documents. One value today.
#: A send test is a rehearsal addressed to the person who pressed the button
#: (`BR-NOT-024`, and `rule_service.py` says the same thing beside the code that
#: writes one), so it sends without freezing and reproduces as a re-render.
FREEZE_EXEMPT_SOURCE_TYPES: frozenset[str] = frozenset({"test"})

#: The store's `source_type` for a queue row. `source_id` is the ROW's id — one
#: message per document per channel, so the pair is already unique.
STORE_SOURCE_TYPE = "outbound_message"

#: The pinned template class → the store's document kind. **Every customer-facing
#: class, since `OQ-1164` closed on 2026-08-30** — the PO's `CR-049` step-5b
#: table (the first block) plus the nineteen they later ruled in ("OKY KEEP
#: THEM", the second block). Anything absent still HOLDS on `OQ-1164` rather than
#: being guessed; see the module docstring for why a guess is worse than a hold.
DOCUMENT_KIND_BY_TEMPLATE_CLASS: dict[str, str] = {
    # "The bill — including the final bill and any corrected/reissued copy."
    # The BILL ITSELF, which is the printable class. `email_bill_ready` and
    # `email_corrected_bill` are NOTIFICATIONS THAT a bill exists, not the bill,
    # and they are deliberately absent — see OQ-1164.
    "bill_residential": "bill",
    "bill_commercial": "bill",
    # "All three disconnection notice tiers, the 48-hour certified one first."
    "disconnect_notice": "disconnect_notice",
    "disconnect_notice_10_day": "disconnect_notice",
    "disconnect_notice_5_day": "disconnect_notice",
    "disconnect_notice_48_hour": "disconnect_notice",
    "sms_disconnect": "disconnect_notice",
    # "Past-due reminder / dunning letter."
    "dunning": "dunning_letter",
    "email_past_due": "dunning_letter",
    "sms_past_due": "dunning_letter",
    # "Payment receipt · failed-payment notice."
    "receipt": "payment_receipt",
    "email_payment_receipt": "payment_receipt",
    "sms_payment_received": "payment_receipt",
    "email_payment_failed": "failed_payment_notice",
    # ⚠ ADDED 2026-08-30 · DEF-2473, and it is the PO's existing scope line
    # APPLIED rather than a new ruling. Their table reads *"Payment receipt ·
    # failed-payment notice"*, and the printed returned-payment letter is that
    # same document on paper — exactly as `receipt`, `email_payment_receipt` and
    # `sms_payment_received` are one document on three channels and share the
    # one `payment_receipt` kind above. `channel` is its own column, so nothing
    # is lost by the two classes sharing a kind.
    #
    # **The alternative was worse and is why this line is not deferred.** Until
    # today the printed copy was pinned to `email_payment_failed`, so once print
    # is switched on it would have frozen an EMAIL body under this kind, for
    # seven years, write-once. A class with no kind HOLDS (`FREEZE_KIND_UNRULED`)
    # rather than freezing, which is safe — but it would hold every bounce letter
    # on a question the PO has already answered.
    "payment_failed_letter": "failed_payment_notice",
    # "Payment plan instalment due · missed · voided."
    "plan_notice_upcoming": "payment_plan_instalment_due",
    "plan_notice_missed": "payment_plan_instalment_missed",
    "plan_notice_void": "payment_plan_voided",
    # "The e-signed payment plan agreement — and every contract behind it."
    # The e-sign integration does not exist (`DEF-2505`); this entry covers the
    # agreement POSTED as a letter, which is a document either way.
    "contract_payment_plan": "payment_plan_agreement",
    # "Move-in welcome · move-out final-bill letter · plan-change confirmation."
    "email_welcome": "move_in_welcome",
    "email_move_out_final": "move_out_final_bill",
    "email_plan_change": "plan_change_confirmation",
    # ══════════════════════════════════════════════════════════════════════
    # OQ-1164, CLOSED 2026-08-30 — the other NINETEEN. "OKY KEEP THEM."
    # ══════════════════════════════════════════════════════════════════════
    # The twenty classes above this block's date held on `OQ-1164` because the
    # PO's scope table did not name them. It was put to them in plain English
    # with the recommendation stated first, and they ruled, verbatim:
    # *"My recommendation is to keep all of them. - OKY KEEP THEM"*.
    #
    # ⚠ `staff_bulk_summary` — the twentieth — IS DELIBERATELY ABSENT AND MUST
    # STAY ABSENT. The same PO ruled the in-app channel out four days earlier
    # (*"we dont have to worry about in-app message those are mostly FYI"*), and
    # a ruling on a LIST does not overturn a ruling on a CHANNEL. It is also
    # unreachable here — an in-app row exits `freeze_for_dispatch` as exempt
    # before a kind is read — so adding it would buy nothing and contradict a
    # live ruling. `test_oq1164_every_customer_document_freezes.py` asserts the
    # absence BY NAME so a later tidy-up cannot restore it quietly.
    #
    # Nineteen classes, seventeen kinds: `channel` is its own column, so the two
    # pairs below share one kind exactly as `email_past_due` and `sms_past_due`
    # already share `dunning_letter`.
    #
    # "Your bill is ready" and the statement — one document each, two channels.
    "email_bill_ready": "bill_ready_notice",
    "sms_bill_ready": "bill_ready_notice",
    "statement": "statement",
    "email_statement": "statement",
    "email_corrected_bill": "corrected_bill_notice",
    "bill_insert": "bill_insert",
    # Money the customer is told about in writing.
    "email_refund_issued": "refund_confirmation",
    "email_credit_issued": "credit_note_confirmation",
    "email_deposit": "deposit_notice",
    "writeoff_notice": "writeoff_notice",
    # Account lifecycle.
    "email_account_closed": "account_closed_letter",
    "email_autopay": "autopay_confirmation",
    # Signed instruments. ⚠ The LETTER about a deposit (`email_deposit` above)
    # and the signed DEPOSIT AGREEMENT are two different documents and keep two
    # different kinds; collapsing them would lose which one a regulator was shown.
    "contract_service_agreement": "service_agreement",
    "contract_deposit": "deposit_agreement",
    "contract_autopay_authorization": "autopay_authorization",
    # Field service. ⚠ **A KIND, AND NOTHING ELSE.** Nothing queues these four:
    # the work-order flow is R5 scope (`OQ-249`) and this ruling explicitly does
    # not authorise building it — it says only that when one of these is sent, it
    # is kept. Mapping the class was the whole of what that required, so no stub
    # was needed; if a later lane finds it needs more than a kind here, that is
    # the boundary to stop at and `raise NotImplementedError("OQ-249")`.
    "service_appointment": "service_appointment",
    "service_work_completed": "service_work_completed",
    "service_outage_notice": "service_outage_notice",
    "service_door_hanger": "service_door_hanger",
    # ══════════════════════════════════════════════════════════════════════
    # DEF-NOT-8450, FIXED 2026-09-30 — the twelve classes added 12–27 September.
    # ══════════════════════════════════════════════════════════════════════
    # They arrived with no kind, so from the moment a utility connected a
    # provider every one of them would have waited in the queue for ever. Kept
    # under the SAME ruling as the nineteen above — `OQ-1164`, *"keep all of
    # them … not judged one by one"* — as recorded by the coordinator in the
    # decision log on 2026-09-30, and not re-asked (law 13). The grouping, and
    # why twelve classes are ten new kinds plus one reused, is written beside
    # the kinds in `apps/tenancy/document_models.py`.
    "account_message": "account_message",
    "service_request_acknowledgement": "service_request_acknowledgement",
    "service_request_acknowledgement_fee": "service_request_acknowledgement",
    "service_request_more_info": "service_request_more_info",
    "service_request_approved": "service_request_approved",
    "service_request_refused": "service_request_refused",
    "new_connect_quote": "new_connection_quote",
    "new_connect_confirmed": "new_connection_confirmation",
    "transfer_to_buyer": "property_sale_buyer_letter",
    "transfer_to_seller": "property_sale_seller_letter",
    # A meter visit announced to the buyer IS an appointment notice, so it is
    # filed with them rather than under an eleventh kind of its own.
    "transfer_field_visit_sms": "service_appointment",
    # `CR-168-BRC10` P6.1 (2026-10-04, lane SRV-5, `2.517.0`) — ruling 3's visit
    # told on each channel the customer chose. All four are the appointment
    # notice in another state or on another channel, so they file with it
    # under `OQ-1164`'s *"keep all of them"*, never under a kind of their own;
    # without a kind each would wait in the queue for ever (`DEF-NOT-8450`).
    "service_visit_moved": "service_appointment",
    "sms_visit_booked": "service_appointment",
    "sms_visit_moved": "service_appointment",
    "sms_technician_on_the_way": "service_appointment",
    # DEF-WRK-10652 (2026-10-29) — *Work order logged*: the appointment notice
    # before its date is known, kept under the same `OQ-1164` ruling.
    "service_work_order_logged": "service_appointment",
    "sms_work_order_logged": "service_appointment",
    # Goes to STAFF. Kept anyway: the ruling's reason is that the risk is one-way.
    "email_scheduled_report": "scheduled_report_notice",
    # CR-182-BRC10 (2026-10-14) — the high consumption alert. Kept under the
    # same `OQ-1164` ruling (*"keep all of them"*), not re-asked (law 13).
    "email_high_usage_alert": "high_usage_alert",
    # CR-190-BRC10 (2026-10-22, lane AGREEMENT) — the agreement email and its
    # acceptance confirmation. Kept under the same `OQ-1164` ruling (*"keep all
    # of them"*), not re-asked (law 13); filed as CORRESPONDENCE about the
    # account, because one class serves every Contracts-group agreement and a
    # contract kind would mislabel a deposit agreement's email. The agreement
    # PDF itself is stored separately, as the file attached.
    "email_agreement_request": "account_message",
    "email_agreement_accepted": "account_message",
    # CR-188-BRC10 (2026-10-22) — a member of staff's own sign-in emails. KEPT
    # like every other document (OQ-1164), with the one-time link REDACTED in
    # the kept copy (`redact_credentials`; decision log 2026-10-22).
    "staff_user_invite": "account_access_email",
    "staff_password_reset_link": "account_access_email",
    # `DEF-CWP-10381` (2026-10-22) — the customer portal's reset link. KEPT,
    # under `OQ-1164`'s *"keep all of them"* (decision log 2026-10-22,
    # *"Account-access emails are KEPT … with the one-time link or code
    # REDACTED"*): without a kind it held here for ever and was never sent.
    # The kept copy carries `REDACTION_MARKER` where the link was
    # (`redact_credentials`); the live send carries the real link. ONE kind for
    # every account-access email (merge 2026-10-22: the lane's own
    # `account_access` kind folded into CR-188-BRC10's `account_access_email`).
    "portal_password_reset": "account_access_email",
    # CR-189-BRC10 (2026-10-22) — the portal's email-change code and the notice
    # to the old address. KEPT like every other document (OQ-1164), the code
    # redacted in the kept copy (decision log 2026-10-22). The kind is
    # CR-188's `account_access_email`, which its tenancy migration adds.
    "portal_enrolment_code": "account_access_email",
    "portal_email_change_code": "account_access_email",
    "portal_email_changed_notice": "account_access_email",
}

#: What one channel's artefact IS, as `(media type, filename extension)`.
#: ⚠ PRINT IS `text/plain` BECAUSE THAT IS WHAT WE HAND THE VENDOR — the module
#: docstring argues it, and `CR-049` task 6 owns the PDF question.
ARTEFACT_MEDIA: dict[str, tuple[str, str]] = {
    models.CHANNEL_PRINT: ("text/plain", "txt"),
    models.CHANNEL_EMAIL: ("message/rfc822", "eml"),
    models.CHANNEL_SMS: ("text/plain", "txt"),
}


# ═══════════════════════════════════════════════════════════════════════════
# WHY A FREEZE DID NOT HAPPEN — CODES, never prose
# ═══════════════════════════════════════════════════════════════════════════
# The dispatch home groups on these exactly as it groups on `provider_seam`'s
# and the dispatcher's own, and a screen cannot group on a sentence.

#: This document's template class is not on the PO's ruled scope list, so no
#: `kind` names it and nothing may guess one. HELD, never sent.
FREEZE_KIND_UNRULED = "document_kind_not_ruled"

#: The render produced nothing to freeze — an empty body. A blank letter must
#: not be posted, and "the letter exists" must not become true about an empty
#: file (`document_store.store` refuses it at the door as well).
FREEZE_ARTEFACT_EMPTY = "rendered_artefact_is_empty"

#: An email subject carrying a carriage return or a newline cannot be written
#: into an RFC 5322 header, and writing it anyway is header injection.
FREEZE_SUBJECT_NOT_A_HEADER = "email_subject_is_not_a_header"

#: ⚠ THE SHARPEST ONE. A frozen artefact ALREADY exists for this row and this
#: channel, and re-rendering the row now produces DIFFERENT bytes — the wording
#: moved under a message between two dispatch attempts (an edited rights clause
#: is exactly how). The frozen copy is the document; the fresh render is not.
#: The row holds for a human rather than either copy being sent silently.
FREEZE_ARTEFACT_DIFFERS = "frozen_artefact_differs_from_todays_render"

#: The store itself refused. Its own sentence travels on `detail`.
FREEZE_STORE_REFUSED = "document_store_refused"


class NotFrozen(RuntimeError):
    """A row was about to be marked `sent` with no frozen artefact behind it.

    ⚠ **THIS IS THE SECOND GUARANTEE, NOT THE FIRST.** The first is the ORDER in
    `dispatcher._dispatch_channel`: a row that did not freeze is released and is
    never handed to a provider, so this exception is unreachable through the
    shipped path. It exists because a guarantee whose only enforcement is the
    order of two statements is one line of refactoring away from being gone —
    hard-won law 1 — and because `_mark_sent` takes the freeze answer as a
    REQUIRED argument, so a future call site cannot silently omit it.
    """


# ═══════════════════════════════════════════════════════════════════════════
# THE ANSWER A FREEZE GIVES
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class FreezeOutcome:
    """Whether this row may now be sent, and what was kept — never ambiguous.

    `may_send` is a VALUE and not an inference from `document is None`, because
    the two exempt cases (in-app, a send test) may send with nothing stored and
    reading them off an empty `document` is how a caller ends up sending an
    unfrozen legal document (hard-won law 1, the same discipline
    `CycleResult.dispatched` and `document_store.DocumentLookup` follow).
    """

    may_send: bool
    document: Any = None
    #: True when this row is out of the freeze's scope entirely (in-app, a send
    #: test) — as opposed to a row that froze, or one that refused.
    exempt: bool = False
    #: True when the artefact was ALREADY frozen by an earlier attempt and this
    #: call re-used it. A retry never stores a second copy.
    reused: bool = False
    problem: dict[str, Any] | None = None


def _problem(code: str, *, row: Any, detail: str) -> dict[str, Any]:
    return {
        "code": code,
        "br_ref": "BR-NOT-027",
        "channel": row.channel,
        "message_id": str(row.pk),
        "detail": detail,
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE ARTEFACT — exactly what leaves the building, serialised once
# ═══════════════════════════════════════════════════════════════════════════


def document_kind(row: Any) -> str | None:
    """The store's document kind for this row, or None if nobody has ruled one.

    None is an ANSWER and not a failure to look. Since `OQ-1164` closed
    (2026-08-30, *"OKY KEEP THEM"*) the map covers every customer-facing class in
    the catalogue, so None means a class that did not exist when the PO ruled —
    a document whose freezing nobody has decided. It HOLDS. A signature covers
    only what was shown, and a forty-second class was not shown.
    """
    return DOCUMENT_KIND_BY_TEMPLATE_CLASS.get(row.template_code or "")


#: What a kept copy says where a one-time credential was (`CR-188-BRC10`).
REDACTION_MARKER = "[one-time link removed from the kept copy]"


def redact_credentials(row: Any, payload: bytes) -> bytes:
    """The KEPT copy of an account-access email, with every live credential
    replaced by `REDACTION_MARKER` — the email itself carries the real value.

    Decision log 2026-10-22, *"Account-access emails are KEPT like every other
    document, with the one-time link or code REDACTED in the kept copy"*: the
    record says what was sent, when and to whom, and holds no usable credential.
    Which tokens are credentials is the CATALOGUE's
    (`TemplateClass.credential_tokens`); the values are the row's own merge
    facts, so exactly the bytes that rendered are the bytes removed. A class
    with no credential tokens is returned unchanged. Applied before the store
    AND before the retry comparison, so both sides are the redacted form.
    """
    from apps.notifications import catalogs

    klass = catalogs.catalog_for(row.template_code or "")
    tokens = getattr(klass, "credential_tokens", frozenset()) if klass is not None else frozenset()
    if not tokens:
        return payload
    context = getattr(row, "render_context", None) or {}
    text = payload.decode("utf-8")
    for token in sorted(tokens):
        value = str(context.get(token) or "")
        if value:
            text = text.replace(value, REDACTION_MARKER)
    return text.encode("utf-8")


def artefact_bytes(row: Any, artifact: Any) -> tuple[bytes, str, str]:
    """One rendered artefact as the bytes that will be frozen.

    Returns `(payload, media type, filename extension)`.

    **PRINT and SMS** freeze the body exactly as `dispatcher._payload` hands it
    over — no wrapper, no re-encoding beyond UTF-8.

    **EMAIL** freezes a minimal RFC 5322 message: one `Subject:` header, a blank
    line, the body. That is a serialisation of what was sent and not an addition
    to it — subject and body are the two things the adapter receives, and this is
    the one representation of them that every mail client and every human already
    reads. It unpacks out of a bulk export as a `.eml` file rather than as a
    fragment nobody can open.

    Raises `ValueError` for a subject that cannot be a header; the caller turns
    that into a per-row refusal rather than an exception that ends the batch.
    """
    body = artifact.body or ""
    if row.channel == models.CHANNEL_EMAIL:
        subject = artifact.subject or ""
        if "\r" in subject or "\n" in subject:
            raise ValueError(
                "this email's rendered subject contains a line break, so it cannot be "
                "written as an RFC 5322 header — and writing it anyway is header "
                "injection, which would let a template author add headers to every "
                "message a utility sends. The template's subject line is where this is "
                "fixed."
            )
        payload = f"Subject: {subject}\r\n\r\n{body}".encode("utf-8")
    else:
        payload = body.encode("utf-8")
    media_type, extension = ARTEFACT_MEDIA[row.channel]
    return payload, media_type, extension


def display_name(row: Any, *, kind: str, extension: str, moment: dt.datetime) -> str:
    """The human name this document unpacks to in a bulk export.

    `document_store` refuses to compose one and says why: a usable name needs the
    account number, which lives in `customers`, and reading it from there is the
    cross-module read B2 §2 forbids. **The dispatcher is in the same position** —
    it holds `account_id`, not `account_no`.

    So this uses the account number the WRITER stamped into the recipient
    snapshot when it wrote the row, and falls back to the identifiers this module
    genuinely holds. ⚠ **REPORTED, not hidden: no writer stamps `account_no`
    today**, so a real export would currently unpack as
    `disconnect_notice/2026/08/MSG-0198f3c2-pdf_print.txt` — the row is named, the
    customer is not. The fix belongs to the writers (one key in the snapshot they
    already build), and it is a `CR-049` follow-up rather than a licence for this
    module to reach into another's tables.
    """
    snapshot = row.recipient_snapshot or {}
    label = str(snapshot.get("account_no") or "").strip()
    if not label and row.account_id:
        label = f"ACCT-{str(row.account_id)[:8]}"
    if not label:
        label = f"MSG-{str(row.pk)[:8]}"
    return f"{kind}/{moment:%Y}/{moment:%m}/{label}-{row.channel}.{extension}"


# ═══════════════════════════════════════════════════════════════════════════
# THE WRITE — called by the dispatcher BEFORE the provider hand-off
# ═══════════════════════════════════════════════════════════════════════════


def freeze_for_dispatch(
    row: Any,
    artifact: Any,
    *,
    moment: dt.datetime,
    actor: Any = None,
    job: str | None = None,
) -> FreezeOutcome:
    """Keep this message as the customer will read it — or refuse to send it.

    Called ONCE per row per dispatch attempt, **before the provider is
    contacted**. A `FreezeOutcome` whose `may_send` is False means the dispatcher
    releases the row: it is not handed over, its retry counter does not move, and
    the reason travels on the cycle result exactly as a missing template does.

    ⚠ **A RETRY RE-USES THE ARTEFACT AND NEVER STORES A SECOND COPY.** The store
    holds one artefact per (source, channel, content type) — a second store of
    the same three is a unique-constraint violation, not a second copy — so an
    attempt that already froze and then failed at the provider finds its own
    document here and passes.

    ⚠ **AND IF TODAY'S RENDER DISAGREES WITH THE FROZEN COPY, THE ROW HOLDS.**
    That is `DEF-2504` caught in flight: a System Admin edited a rights clause
    between two dispatch attempts and the letter is no longer the letter that was
    frozen. Sending the fresh render would break `BR-NOT-027`; silently sending
    the frozen bytes would hide a wording change from the person who made it. The
    row holds and says which of the two it is.
    """
    if row.channel not in FREEZE_CHANNELS:
        # in-app: `in_app_messages.body` already stores its render, and the PO
        # ruled the channel out of scope. Nothing to freeze, and sending is fine.
        return FreezeOutcome(may_send=True, exempt=True)
    if row.source_type in FREEZE_EXEMPT_SOURCE_TYPES:
        return FreezeOutcome(may_send=True, exempt=True)

    kind = document_kind(row)
    if kind is None:
        return FreezeOutcome(
            may_send=False,
            problem=_problem(
                FREEZE_KIND_UNRULED,
                row=row,
                detail=(
                    f"template class {row.template_code!r} is not on the ruled list of "
                    "documents that freeze when they are sent (the PO's CR-049 scope "
                    "table, 2026-08-30), so this module has no document kind to store it "
                    "under and will not invent one. The row HOLDS: nothing was handed to "
                    "a provider and no retry counter moved. Which of the unruled classes "
                    "are legal documents that must be kept as sent is OQ-1164, and it is "
                    "the Product Owner's to answer — a guess here would put a wrong "
                    "answer inside a seven-year legal record."
                ),
            ),
        )

    try:
        payload, media_type, extension = artefact_bytes(row, artifact)
    except ValueError as refused:
        return FreezeOutcome(
            may_send=False,
            problem=_problem(FREEZE_SUBJECT_NOT_A_HEADER, row=row, detail=str(refused)),
        )
    # CR-188-BRC10 — the kept copy never holds a live credential.
    payload = redact_credentials(row, payload)
    if not payload.strip():
        return FreezeOutcome(
            may_send=False,
            problem=_problem(
                FREEZE_ARTEFACT_EMPTY,
                row=row,
                detail=(
                    "this message rendered to an empty body, so there is nothing to keep "
                    "and nothing worth posting. A blank letter reaching a customer is "
                    "worse than one that has not gone out, and an empty frozen file would "
                    "make 'we kept the letter' true about nothing at all. The row HOLDS."
                ),
            ),
        )

    existing = document_store.for_source(
        source_type=STORE_SOURCE_TYPE,
        source_id=row.pk,
        channel=row.channel,
        content_type=media_type,
    )
    if existing.found:
        from apps.tenancy import document_storage  # local: the hash function only

        if document_storage.content_hash(payload) == existing.document.content_hash:
            return FreezeOutcome(may_send=True, document=existing.document, reused=True)
        return FreezeOutcome(
            may_send=False,
            document=existing.document,
            problem=_problem(
                FREEZE_ARTEFACT_DIFFERS,
                row=row,
                detail=(
                    "this message was already frozen on an earlier dispatch attempt and "
                    "rendering it again TODAY produces different bytes — the wording "
                    "moved underneath it, which an edited rights clause on a "
                    "disconnection notice does. Neither copy may be sent silently: the "
                    "frozen one is the document, and a fresh render is the thing "
                    "BR-NOT-027 forbids putting in its place. The row HOLDS for a person "
                    "to look at."
                ),
            ),
        )

    try:
        stored = document_store.store(
            kind=kind,
            source_type=STORE_SOURCE_TYPE,
            source_id=row.pk,
            channel=row.channel,
            content_type=media_type,
            display_name=display_name(row, kind=kind, extension=extension, moment=moment),
            payload=payload,
            actor_user_id=getattr(actor, "id", None),
            process=job or "notifications.dispatcher",
        )
    except document_store.DocumentStoreError as refused:
        return FreezeOutcome(
            may_send=False,
            problem=_problem(FREEZE_STORE_REFUSED, row=row, detail=str(refused)),
        )
    return FreezeOutcome(may_send=True, document=stored)


def require_frozen(row: Any, outcome: FreezeOutcome | None) -> None:
    """Refuse to advance a row to `sent` without the freeze that precedes it.

    The dispatcher calls this from `_mark_sent`, which takes the outcome as a
    REQUIRED argument — so a new call site cannot forget it, and a refactor that
    reorders the freeze past the hand-off goes RED here instead of shipping an
    unfrozen legal document. See `NotFrozen` for why a second guarantee exists at
    all when the ordering already provides one.
    """
    if outcome is not None and outcome.may_send:
        return
    raise NotFrozen(
        f"queue row {row.pk} ({row.channel}) was about to be marked `sent` with no frozen "
        "artefact behind it. BR-NOT-027 (PO 2026-08-30) makes keeping the letter a "
        "PRECONDITION of sending it, with no exceptions: nothing has ever been sent to a "
        "customer from this product, so there is no era before the rule and nothing to "
        "grandfather. Freeze it first (`freeze_for_dispatch`) or leave it queued."
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE READ — CR-049 task 7: say what is missing rather than substituting
# ═══════════════════════════════════════════════════════════════════════════

#: This IS the document the customer received, byte for byte.
PROVENANCE_ORIGINAL = "original"

#: This is NOT the document the customer received. It is a fresh render from the
#: stored data and today's wording, and it may differ from what was served.
#: ⚠ **NEVER SHOWN WITHOUT SAYING SO.** `BR-NOT-027`'s honest half, and the whole
#: point of `DEF-2504`: the five regulatory clauses on a disconnection notice are
#: a per-tenant map a System Admin edits, so a re-render of last year's notice
#: carries THIS YEAR's rights wording and looks exactly as authentic.
PROVENANCE_RE_RENDERED = "re_rendered_from_data_not_the_original"

#: i18n keys for the sentence a screen draws beside a reproduction. The copy
#: lives in `07-frontend/src/i18n/locales/*.json` (eleven catalogues); the KEY is
#: chosen here so the backend and the reprint screen cannot describe the same
#: state in two different ways.
I18N_ORIGINAL = "notifications.frozenDocument.original"
I18N_RE_RENDERED = "notifications.frozenDocument.reRendered"
I18N_EXEMPT_SEND_TEST = "notifications.frozenDocument.sendTest"
I18N_EXEMPT_IN_APP = "notifications.frozenDocument.inApp"


@dataclass(frozen=True)
class Reproduction:
    """How a reproduction of one sent message must be SERVED. Never ambiguous.

    ⚠ **`provenance` IS A VALUE A CALLER MUST BRANCH ON, AND THERE IS NO THIRD
    STATE THAT MEANS "PROBABLY".** Either this is the original or it is a
    re-render, and a caller that renders the second without drawing
    `i18n_key`'s sentence has produced the defect `BR-NOT-027` was written for —
    a fresh document presented as the letter that was served.

    `document` is set only for `PROVENANCE_ORIGINAL`. `unavailable_reason` is
    `document_store`'s own code (`document_not_stored`), passed through rather
    than re-spelled, so one vocabulary describes one fact.
    """

    message_id: str
    provenance: str
    document: Any = None
    unavailable_reason: str | None = None
    exempt: bool = False
    i18n_key: str = ""
    detail: str = ""

    @property
    def is_original(self) -> bool:
        return self.provenance == PROVENANCE_ORIGINAL


def reproduce(row: Any) -> Reproduction:
    """Is there an original for this message — or must a reproduction say it is not?

    This is `CR-049` task 7, and it is the half that keeps the rule honest. The
    precondition in `freeze_for_dispatch` should make `PROVENANCE_RE_RENDERED`
    unreachable for anything that reached `sent` on a customer channel. **It is
    kept anyway, because a guarantee with no visible failure mode is exactly the
    shape hard-won law 1 warns about** — and because a row that is still `queued`
    genuinely has no original, which a reprint screen has to be able to say.

    ⚠ **THIS DOES NOT RENDER ANYTHING.** It answers WHICH document a caller may
    serve. `CR-049` task 3 builds the route that serves it and is another lane's;
    if that route ever calls `rendering.render_for_dispatch` on a row this
    function called ORIGINAL, the rule is broken in the product while every test
    here still passes.
    """
    message_id = str(row.pk)
    if row.channel not in FREEZE_CHANNELS:
        return Reproduction(
            message_id=message_id,
            provenance=PROVENANCE_RE_RENDERED,
            exempt=True,
            i18n_key=I18N_EXEMPT_IN_APP,
            detail=(
                "an in-app alert keeps its own copy of what it said when it was "
                "delivered, and the Product Owner ruled the channel out of the document "
                "freeze — these are staff notices, not letters to a customer."
            ),
        )
    if row.source_type in FREEZE_EXEMPT_SOURCE_TYPES:
        return Reproduction(
            message_id=message_id,
            provenance=PROVENANCE_RE_RENDERED,
            exempt=True,
            i18n_key=I18N_EXEMPT_SEND_TEST,
            detail=(
                "this was a send test — a rehearsal addressed to the person who pressed "
                "the button, not a document sent to a customer — so no sealed copy was "
                "kept."
            ),
        )

    media_type, _extension = ARTEFACT_MEDIA[row.channel]
    lookup = document_store.for_source(
        source_type=STORE_SOURCE_TYPE,
        source_id=row.pk,
        channel=row.channel,
        content_type=media_type,
    )
    if lookup.found:
        return Reproduction(
            message_id=message_id,
            provenance=PROVENANCE_ORIGINAL,
            document=lookup.document,
            i18n_key=I18N_ORIGINAL,
            detail=(
                "this is the document as it was sent, kept at the moment it left the "
                "building and never re-rendered since."
            ),
        )
    return Reproduction(
        message_id=message_id,
        provenance=PROVENANCE_RE_RENDERED,
        unavailable_reason=lookup.unavailable_reason,
        i18n_key=I18N_RE_RENDERED,
        detail=(
            "no copy of this message was kept as it was sent, so anything shown here is "
            "REBUILT from the stored data and today's wording — it is not the document "
            "the customer received and it may differ from it. On a disconnection notice "
            "the difference is the rights clauses, which a System Admin can edit at any "
            "time."
        ),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-049 tasks 2 + 7 (sources: 12-governance/11-change-requests.md CR-049 steps 4, 5b, 5c and 5d(c)/(d) · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-027 · 12-governance/10-defect-log.csv DEF-2504/DEF-2506 · 06-backend/apps/tenancy/document_store.py, task 1's published service)
# generated: 2026-08-30 by the CR-049 tasks 2/5/7 lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the reprint route that serves a reproduction is CR-049 task 3 and another lane's) E=deferred(no-frontend-half — same task; the eleven locale strings this module's i18n keys name ARE written) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the rights-clause case (DEF-2504) was shown re-rendering a served notice with an EDITED clause before this module existed, and serving the original after; the precondition was shown marking a row `sent` with nothing stored before `require_frozen` and raising NotFrozen after. Verbatim transcripts in 06-backend/tests/test_cr049_t5_rights_clause_reprint.py and test_cr049_t2_dispatch_freeze.py.
# exceptions: (1) PRINT FREEZES TEXT, NOT A PDF — there is no page-render library (OQ-149) and freezing a PDF this module rendered itself would freeze a document the customer never received. CR-049 task 6 owns the PDF question. (2) A TEMPLATE CLASS THE PO's SCOPE TABLE DOES NOT NAME HOLDS ON OQ-1164 rather than being assigned a kind. (3) `display_name` CANNOT REACH THE ACCOUNT NUMBER — B2 §2 — so an export unpacks under the message id until a writer stamps `account_no` into the recipient snapshot. REPORTED. (4) THE MAP IS KEYED ON THE PINNED TEMPLATE CLASS because `event_key` is NULL on every row this product writes today.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
