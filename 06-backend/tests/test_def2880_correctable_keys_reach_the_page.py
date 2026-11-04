# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2880 (2026-08-31) — a Class-D document correction was allowed to
#           edit `bill_message`, and the renderer reads `message`. The correction
#           succeeded, wrote an audit row, reissued a document instance and
#           changed nothing on the page.
# Story:    US-BIL-031 (document corrections)   Screens: S33
# Rules:    BR-BIL-041 / BR-BIL-043 (a document correction reissues the PAGE and
#           moves $0.00) · BR-BIL-021 (the bill message is the tenant's own copy)
#           · BR-BIL-030 (a bill carries what it was worth on the day it was sent)
# ───────────────────────────────────────────────────────
"""The allow-list is checked in the REFUSING direction only — so nothing sees a
key that is allowed and read by nobody.

`document_correction.CORRECTABLE_PAYLOAD_KEYS` refuses an unknown key. It has
never asked the opposite question, and that is the whole of `DEF-2880`: a name
in the list that no document field consumes passes every check there is. The
value lands on the reissued payload, the instance is written, the audit row is
written, and the customer's page is byte-for-byte what it was.

**WHY A WALKING TEST AND NOT A COMMENT.** Two allow-lists exist for one value —
`issue.BILL_COPY_KEYS` maps the TEMPLATE OPTION `bill_message` onto the PAYLOAD
key `message`, and `documents._footer` reads `message` — and nothing compared
them. Hard-won law 1: a comment saying they agree is not the agreement.

**HOW "THE RENDERER READS IT" IS MEASURED HERE: BY RUNNING THE RENDERER.** The
payload handed to the four field builders is a `dict` subclass that records every
key asked for, so the set below is what the code actually consults on this build
rather than what a constant claims. No database is needed and nothing is grepped.
"""

from __future__ import annotations

from types import SimpleNamespace

from apps.billing import document_correction, documents, issue


class RecordingPayload(dict):
    """A payload that remembers which keys the renderer asked it for.

    `dict.get` is a C method and does NOT route through `__getitem__`, so both
    doors are overridden — a subclass that only overrides `__getitem__` would
    record nothing at all here, because every reader in `documents.py` uses
    `.get`. That is the same class of silent-no-op this file exists to catch.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.asked: set[str] = set()

    def get(self, key, default=None):  # noqa: A003 - dict's own name
        self.asked.add(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self.asked.add(key)
        return super().__getitem__(key)


def _keys_the_renderer_reads() -> set[str]:
    """Every payload key the four payload-reading field builders consult.

    `_masthead`, `_meta`, `_services` and `_footer` are the whole of the bill's
    identity band, its per-service header and its message footer — which is
    every band a Class-D correction can touch. The money bands (`_groups`,
    `_summary`, `_stub`) are deliberately not walked: no correctable key is a
    money key, and `refuse_uncorrectable_keys` exists to keep it that way.
    """
    payload = RecordingPayload()
    invoice = SimpleNamespace(
        invoice_no=None, due_date=None, period_start=None, period_end=None
    )
    documents._masthead(payload)
    documents._meta(invoice, payload)
    documents._services(payload)
    documents._footer(payload)
    return set(payload.asked)


def test_def2880__every_correctable_key_is_read_by_a_document_field_or_named_as_absent():
    """THE GUARD. A correctable name is either drawn on the page or listed as
    a gap with a reason — never silently neither.

    RED on the branch tip before this fix: `bill_message` was in the allow-list,
    is read by nothing, and is not one of the named gaps, so the difference below
    was `{'bill_message'}` against an expected empty remainder.
    """
    read = _keys_the_renderer_reads()
    allowed = set(document_correction.CORRECTABLE_PAYLOAD_KEYS)

    unread = allowed - read
    assert unread == set(document_correction.KEYS_WITH_NO_DOCUMENT_FIELD_YET), (
        "a document correction may write "
        f"{sorted(unread - set(document_correction.KEYS_WITH_NO_DOCUMENT_FIELD_YET))} "
        "and no document field reads it — the correction would succeed, write an "
        "audit row, reissue an instance and change nothing on the customer's page "
        "(DEF-2880). Either point the name at the payload key the renderer reads, "
        "or state it in KEYS_WITH_NO_DOCUMENT_FIELD_YET with its reason."
    )


def test_def2880__the_named_gaps_are_all_actually_correctable_keys():
    """The documented-gap list may not drift into naming keys nobody can correct.

    A gap list that outlived its entries would quietly shrink the guard above:
    every stale name in it is one more name the first assertion would forgive.
    """
    extra = set(document_correction.KEYS_WITH_NO_DOCUMENT_FIELD_YET) - set(
        document_correction.CORRECTABLE_PAYLOAD_KEYS
    )
    assert extra == set(), (
        f"{sorted(extra)} is named as a document gap and is not a correctable key at "
        "all, so it forgives nothing and hides the guard's real subject."
    )


def test_def2880__the_bill_message_travels_under_the_name_the_renderer_reads():
    """The two allow-lists, compared — which is what nothing did.

    `issue.BILL_COPY_KEYS` is the ONE map from a template option to a payload
    key. Whatever it says the bill message lands under is the name a correction
    must be allowed to write, and it is asserted here rather than restated.
    """
    payload_key = dict(issue.BILL_COPY_KEYS)[issue.TEMPLATE_OPTION_BILL_MESSAGE]
    assert payload_key in document_correction.CORRECTABLE_PAYLOAD_KEYS, (
        f"issue stamps the tenant's bill message onto the payload as {payload_key!r} "
        "and a document correction cannot write that name, so the message on a "
        "customer's page can never be corrected."
    )
    assert issue.TEMPLATE_OPTION_BILL_MESSAGE not in (
        document_correction.CORRECTABLE_PAYLOAD_KEYS
    ), (
        "the TEMPLATE OPTION's name is in the payload allow-list. That is DEF-2880: "
        "a correction under that name is accepted and reaches no field."
    )


def test_def2880__a_corrected_message_reaches_the_footer_field_the_page_draws():
    """End of the chain, on the value itself: corrected words in, corrected
    words on the field `documents._footer` renders.

    No database: `_footer` is a pure function of the payload, and the payload is
    exactly what `default_document_for_reprint` hands a reprint. What this pins
    is the join the defect broke — that the key a correction writes is the key
    the field reads.
    """
    corrected = {"message": "Pay by 12 September to avoid a late fee."}
    document_correction.refuse_uncorrectable_keys(corrected)

    fields, absent = documents._footer(corrected)
    values = {field.label: field.value for field in fields}
    assert values["Message"] == "Pay by 12 September to avoid a late fee."
    assert "message" not in {gap.field for gap in absent}


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2880 (12-governance/10-defect-log.csv) + apps/billing/issue.py
#         BILL_COPY_KEYS + apps/billing/documents.py _footer
# generated: 2026-09-01 by the billing defect lane
# checklist: A✔ B=deferred(no API half — this is a guard over two module constants) C✔ D=deferred(same) E=deferred(no screen half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — with `bill_message` restored in CORRECTABLE_PAYLOAD_KEYS
#        the first case fails with `unread == {'bill_message'}` and the third
#        fails on both of its assertions. Verbatim in the lane report.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
