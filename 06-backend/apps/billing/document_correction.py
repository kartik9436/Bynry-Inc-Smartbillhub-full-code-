# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-031 (document-only correction: the bill is right, the
#           document is wrong)   Screens: S30
# Rules:    BR-BIL-041 (class D: no credit note, no rebill, no posting handoff;
#           balance delta exactly $0.00; the artifact is a reissued document
#           instance) · BR-BIL-043 (a D-class case whose computed money delta is
#           non-zero is REFUSED) · BR-BIL-049 (a correction never edits master
#           data and a master-data edit is never a correction; the case RECORDS
#           which master-data change it reflects) · BR-BIL-030 (the bill is
#           LOCKED at issue and its payload frozen — which is exactly why a
#           document fix must produce a NEW instance) · BR-BIL-026/031
#           (template + version pinned at issue; a template change never
#           re-renders history) · BR-CUS-040 (a reprint renders the issued
#           document and never recomputes) · BR-BIL-033 (a failed render
#           refuses) · BR-TEN-043 (event time is an argument) · CLAUDE.md
#           rule 4 (immutability) · rule 7 (audit)
# Tests:    06-backend/tests/test_us_bil_031_document_correction.py
# Impacts:  apps/billing/bulk_corrections.py (routes class-D cases here) ·
#           apps/billing/correction_models.InvoiceDocumentInstance ·
#           apps/billing/documents.py (renders the instance — READ, not edited)
# ───────────────────────────────────────────────────────
"""A misspelt name is not a credit note.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file's whole job is to make sure a
correction path does NOT move money, which is a 🔒 concern from the other
direction. AI-authored 2026-08-11 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

════════════════════════════════════════════════════════════════════════════
WHAT A DOCUMENT-ONLY CORRECTION ACTUALLY IS — worked out from two rules
════════════════════════════════════════════════════════════════════════════
The bill went out with the customer's name misspelt, or the wrong service
address, or in the wrong language. **The money is right.** Two CONFIRMED rules
decide between them what the fix can possibly be, and neither leaves any room:

* **BR-BIL-030** — the bill is LOCKED at issue and `invoices.bill_payload` is
  frozen by the `0006` immutability trigger. The database refuses the UPDATE
  outright. So the sent document can never be rewritten in place, and any
  design that "just fixes the name on the bill" is unimplementable by
  construction, not by policy.
* **BR-CUS-040** — a reprint renders the ISSUED document and never recomputes.
  So the fix cannot be "print it again from live data": that is precisely the
  re-join the locked payload exists to prevent, and it would silently rewrite
  history for every other field too.

Between them: the only lawful output is a **NEW document instance** carrying its
own corrected copy of the payload, attached to the original invoice, with the
original retained. That is what the PO ruled on 2026-08-11 closing OQ-103 —
option **(a) REISSUE** — and it is what `InvoiceDocumentInstance` is.

**The MONEY does not move and this module has no way to move it.** There is no
credit note here, no invoice, no adjustment, no posting call and no import that
could reach one. US-BIL-031 TC-2 asserts it by counting rows before and after
rather than by reading this docstring, which is the only kind of assertion
hard-won law 1 accepts.

════════════════════════════════════════════════════════════════════════════
WHAT THIS DOES NOT DO — and both absences are rules
════════════════════════════════════════════════════════════════════════════
**It does not fix the customer's record** (BR-BIL-049). That is a
customers-module edit governing FUTURE documents; this case decides only what
the already-sent document says. Two transactions, two audit trails. The case
RECORDS which master-data change it reflects (`master_data_ref`) and performs
none of it — `apps/customers` is another module's table and B1 forbids the write
in any case.

**It does not move the original to `corrected`** (TC-3). Nothing about what is
owed was corrected. The original stays `issued` or `paid`, its money columns and
its payload byte-identical — the trigger would refuse otherwise, and a test
proves that refusal RED.

════════════════════════════════════════════════════════════════════════════
THE HALF THE RULING LEFT OPEN — OQ-169, CLOSED BY THE PO ON 2026-08-12
════════════════════════════════════════════════════════════════════════════
OQ-103's closure carried a warning in the registry, in its own words: *"⚠ THE
SUB-QUESTION IS STILL OPEN and returns to the agenda: with two instances on
file, which does a later reprint/re-send/dispute copy render by default?
BR-CUS-040 says 'the issued document', which is no longer unambiguous."* It had
no live OQ id — it was flagged inside a CLOSED row — so it was minted here as
**OQ-169**, and `default_document_for_reprint` RAISED rather than picking.

**The PO answered it on 2026-08-12: _"Reissue a corrected copy"_.** A later
reprint, re-send or dispute copy renders **the corrected one**, *because that is
the document the customer is entitled to*. So `default_document_for_reprint`
returns the newest reissued instance, and returns the ORIGINAL only while there
is no reissue at all.

The reasoning that made this hard is not discarded, it is ruled on: the original
is still what the customer actually received and is still the honest record of
what happened, so it is RETAINED, never overwritten, and still reachable by id
for anyone who needs that specific fact. What changed is the DEFAULT — the
question was never which document exists, only which one comes back when nobody
names one.

════════════════════════════════════════════════════════════════════════════
CORRECTIONS ACCUMULATE — DEF-084, CLOSED BY THE PO ON 2026-08-12
════════════════════════════════════════════════════════════════════════════
**PO verbatim: _"Accumilate"_.** Each reissue is composed from the instance
BEFORE it. The invoice's frozen payload is the base for the FIRST reissue only.

The defect this closed, worked through: July's bill went out with the name
misspelt *Sara Whitfield*. A clerk fixed the name → instance 1 read *Sarah
Whitfield*. A week later somebody fixed the service address → instance 2 was
composed from the INVOICE again, so it carried the corrected address **and the
misspelt name back**. `execute_document_correction` did that on every reissue,
so corrections did not accumulate, they REPLACED. Nothing caught it for as long
as `default_document_for_reprint` raised — nothing consumed the chain, so no test
ever compared instance N to instance N-1 — and the reprint ruling of the same day
is what made it bite: the newest instance is the document the customer receives,
so the second correction silently undid the first on the paper they hold.

**THE RISK THE PO ACCEPTED, STATED PLAINLY RATHER THAN LEFT TO BE REDISCOVERED:**
accumulating carries forward a correction somebody later decides was wrong.
There is no revert — undoing a correction means a FURTHER correction restating
the right value, and the superseded instances stay on file as the record of what
each page actually said.

**IT IS BOUGHT WITH A NEW ROW, NEVER AN EDIT.** Composing from instance N-1 reads
that row; nothing on the chain, and nothing on the invoice, is ever written a
second time (hard rule 4 · BR-BIL-030). Money keys can never enter a payload
here — `CORRECTABLE_PAYLOAD_KEYS` is an allow-list — so every figure in instance
N is still the one the frozen original carried, inherited unchanged down the
whole chain.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db import transaction

from apps.billing import corrections, documents, models
from apps.billing.correction_models import CLASS_DOCUMENT, InvoiceDocumentInstance
from apps.billing.exceptions import BillingRuleError
from core import audit
from core import tenancy as core_tenancy

#: The payload keys a document correction may touch. **An allow-list, not a
#: deny-list**, and that direction is the guard: a caller handing over a
#: corrected payload with `total` or `lines` in it is refused rather than
#: trusted, because the frozen original is the only thing standing between a
#: "document correction" and a silent re-statement of the money.
#:
#: ⚠ **AN ALLOW-LIST IS CHECKED IN THE REFUSING DIRECTION ONLY, SO A NAME THE
#: RENDERER NEVER READS PASSES EVERY CHECK THERE IS (`DEF-2880`, 2026-09-01).**
#: This tuple named `bill_message` until today. That is the **TEMPLATE OPTION's**
#: name — `issue.TEMPLATE_OPTION_BILL_MESSAGE`, the key a tenant's words are
#: stored under on `bill_template_versions.options` — and `issue.BILL_COPY_KEYS`
#: maps it onto the PAYLOAD under `message`, which is the only name
#: `documents._footer` reads. So a Class-D correction of the bill message was
#: accepted, wrote an audit row, reissued a document instance **and changed
#: nothing on the page**: the corrected value sat on the payload under a key no
#: field consumes. Two allow-lists for one value, and nothing compared them.
#:
#: **THE NAMES HERE ARE PAYLOAD KEYS.** Where a template option and a payload
#: key differ, this list carries the payload key, because this list is checked
#: against a payload.
CORRECTABLE_PAYLOAD_KEYS: tuple[str, ...] = (
    "customer_name",
    "customer_names",
    "service_address",
    "mailing_address",
    "premises_label",
    "unit_label",
    "meter_number",
    "meter_numbers",
    "read_dates",
    "utility_name",
    "utility_address",
    # `issue.BILL_COPY_KEYS` stamps the template option `bill_message` onto the
    # payload under THIS name, and `documents._footer` reads THIS name. DEF-2880.
    "message",
    "language",
)

#: The correctable keys **no document field reads today**, each with the reason,
#: so the walking guard in `tests/test_def2880_correctable_keys_reach_the_page.py`
#: can tell a stated absence from `DEF-2880`'s silent one.
#:
#: These are not a second allow-list and they widen nothing: they are already in
#: the tuple above and a correction of one is already accepted. What they are is
#: the honest statement that the page does not carry them **yet** — A19 §1.4 asks
#: for meter number, prior read and current read per service and `_services`
#: records only WHETHER a service was measured (its own `AbsentField` says so);
#: `mailing_address`, `premises_label` and `language` are delivery and addressing
#: facts A19 does not draw. The difference from `DEF-2880` is that each of these
#: has a document gap behind it, and `bill_message` had a **typo** behind it: the
#: value would never have reached the page under any future layout, because
#: nothing anywhere writes that name onto a payload.
KEYS_WITH_NO_DOCUMENT_FIELD_YET: frozenset[str] = frozenset(
    {
        "customer_names",
        "mailing_address",
        "premises_label",
        "meter_number",
        "meter_numbers",
        "read_dates",
        "language",
    }
)


def refuse_uncorrectable_keys(corrected_payload: dict[str, Any]) -> None:
    """BR-BIL-041/043 at the field level.

    The money-bearing keys of a payload — totals, lines, taxes, dates that
    drive a due date — are not "document" facts, and a case that changed one
    would have moved money through a path with no credit note and no ledger
    entry. That is worse than the failure BR-BIL-043 guards, because there
    would be no delta for it to notice.
    """
    unknown = [key for key in corrected_payload if key not in CORRECTABLE_PAYLOAD_KEYS]
    if unknown:
        raise BillingRuleError(
            f"a document correction may not change {', '.join(sorted(unknown))}. Class D "
            "reissues the PAGE (name, address, labels, meter numbers, read dates, "
            "wording, language) and moves $0.00 — a change to what the bill charges is a "
            "restatement and goes through a credit note and a rebill, where somebody "
            "approves the money (BR-BIL-041/043).",
            br_ref="BR-BIL-043",
        )
    if not corrected_payload:
        raise BillingRuleError(
            "a document correction that changes nothing on the page would issue a second "
            "identical document — two copies of the same bill on file, and no way to say "
            "which one anybody meant.",
            br_ref="BR-BIL-041",
        )


#: Where the document a reprint renders came from. Two values, because there are
#: exactly two places one can live: a reissued row, or the invoice's own frozen
#: payload. A caller that must branch on this reads a CODE, never a null.
REPRINT_SOURCE_REISSUE = "reissued_instance"
REPRINT_SOURCE_ORIGINAL = "original_invoice"

#: The PO's words closing OQ-169, 2026-08-12, kept as a value so the code quotes
#: the ruling instead of paraphrasing it — a paraphrase is what drifts.
REPRINT_RULING = "Reissue a corrected copy"
REPRINT_RULING_DATE = "2026-08-12"


@dataclass(frozen=True)
class ReprintDocument:
    """WHICH document a reprint renders, and everything needed to render it.

    ONE shape for both answers, and never a None meaning "the original": a
    caller that forgot that branch would render an empty page and pass its
    tests. `instance_no` is 0 for the original — the number the model's own
    comment already reserves for it (*"instance 0 is not stored: it is the
    ORIGINAL, which lives on the invoice"*) — and `instance_id` is None there
    because there is no row, which is a fact rather than a fallback.

    The template pin travels with the payload. BR-BIL-026/031: a document
    renders on the version its bill was issued on, and a template published
    since then never re-renders history.
    """

    source: str
    instance_no: int
    instance_id: str | None
    payload: dict[str, Any]
    payload_version: int
    template_id: Any
    template_version: int | None


def default_document_for_reprint(invoice: models.Invoice) -> ReprintDocument:
    """Which document a later reprint / re-send / dispute copy renders.

    **RULED — OQ-169, PO 2026-08-12, verbatim: _"Reissue a corrected copy"_.**
    The reprint renders **the corrected one**, *because that is the document the
    customer is entitled to*. This function used to be a stub against that
    question, because BR-CUS-040's *"the issued document"* stops being
    unambiguous the moment there are two; the PO removed the ambiguity rather
    than the second document.

    So: the NEWEST reissued instance if there is one, and the invoice's own
    frozen payload if there is not. `instance_no` orders them — it counts up per
    invoice under a unique constraint, so "newest" is a fact and not a race with
    `created_at`.

    WITH TWO REISSUES the latest wins, which is the ruling read one step past
    the case the PO was shown: instance 1 is a copy the utility has itself
    superseded, and the entitlement runs to the current corrected copy. Stated
    here as a reading so it can be disagreed with.

    THE ORIGINAL IS NEVER DESTROYED AND NEVER RETURNED BY SURPRISE. It stays on
    the invoice, byte-identical (hard rule 4 · BR-BIL-030), and anyone who needs
    the document the customer ACTUALLY received — a dispute hearing asking what
    was in the envelope — asks for instance 0 by name. What the ruling settled is
    only the default.

    Refuses a bill with no locked payload and no reissue: BR-CUS-040 says a
    reprint renders the issued document and never recomputes, so rebuilding one
    from today's customer and premises rows would print today's facts over a
    historical period. Same refusal, same rule, as the execute path.
    """
    latest = (
        InvoiceDocumentInstance.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), invoice=invoice
        )
        .order_by("-instance_no")
        .first()
    )
    if latest is not None:
        return ReprintDocument(
            source=REPRINT_SOURCE_REISSUE,
            instance_no=latest.instance_no,
            instance_id=str(latest.pk),
            payload=dict(latest.payload or {}),
            payload_version=latest.payload_version,
            template_id=latest.template_id,
            template_version=latest.template_version,
        )
    if not invoice.bill_payload:
        raise BillingRuleError(
            f"bill {invoice.invoice_no or invoice.pk} carries no locked document instance "
            "and no reissue, so there is no issued document to reprint (BR-BIL-030). "
            "Rendering one from live customer and premises rows would print today's facts "
            "over a historical period — the exact failure the locked payload prevents, and "
            "what BR-CUS-040 means by 'never recomputes'.",
            br_ref="BR-CUS-040",
        )
    return ReprintDocument(
        source=REPRINT_SOURCE_ORIGINAL,
        instance_no=0,
        instance_id=None,
        payload=dict(invoice.bill_payload),
        payload_version=invoice.payload_version,
        template_id=invoice.template_id,
        template_version=invoice.template_version,
    )


@transaction.atomic
def execute_document_correction(
    invoice: models.Invoice,
    *,
    impact: corrections.BillImpact,
    case: Any = None,
    corrected_payload: dict[str, Any],
    master_data_ref: str | None = None,
    on_date: date,
    actor: Any = None,
) -> corrections.ExecutedBill:
    """Reissue ONE document. No money rows of any kind. One transaction.

    OQ-103 option (a), the PO's ruling of 2026-08-11: a corrected document
    instance is rendered from a corrected COPY of the payload, attached to the
    original invoice, and the original is retained.

    **CORRECTIONS ACCUMULATE — DEF-084, PO 2026-08-12, verbatim: _"Accumilate"_.**
    Each reissue is composed from the instance BEFORE it; the invoice's frozen
    payload is the base only for the FIRST reissue. So fixing the name and then
    the address leaves instance 2 carrying both.

    This function USED TO compose every reissue from the invoice's frozen payload
    (`{**original_payload, **corrected_payload}`) and never from the instance
    before it, so a second correction REVERTED the first: the name fix went back
    to the misspelling the moment somebody corrected the address. The reprint
    ruling of the same day makes the newest instance the document the customer
    receives, so that revert reached the paper in the envelope. It does not any
    more, and `tests/…tc6d/tc6e` measure two corrections and three.

    **THE RISK THE PO ACCEPTED WITH THE RULING**, kept here because it is the
    thing a future reader will be surprised by: accumulating carries forward a
    correction somebody later decides was wrong. Undoing one is a FURTHER
    correction restating the right value, not a revert to an earlier instance.

    Refuses before writing anything: a case that is not class D · a
    recomputation that moved money (BR-BIL-043) · a payload key that is not a
    document fact · a render the layout cannot produce (BR-BIL-033).

    Reports rather than refuses one thing, deliberately: a corrected name the
    PAGE cannot spell. `documents.render_invoice` substitutes and names the
    substitution (`pdf_unrepresentable`, OQ-150) because the Base-14 fonts
    encode WinAnsi and nothing else — so a reissue that fixes `Zofia Nowalczyk`
    to `Zofia Nowałczyk` produces a page reading `Zofia Nowa?czyk`. That is the
    reading the renderer ships and this module carries it through instead of
    inventing a second answer: the substitution comes back on the result and is
    audited, so a ruling of "refuse instead" needs no re-discovery of which
    documents it affects.
    """
    if impact.correction_class != CLASS_DOCUMENT:
        raise BillingRuleError(
            f"this case is class {impact.correction_class!r} and a document reissue is "
            "class D only (BR-BIL-041). The mechanism is derived from the reason — a "
            "money reason can never be discharged by a reprint, which is the silent "
            "underbilling this guard exists for.",
            br_ref="BR-BIL-041",
        )
    corrections.refuse_unless_class_matches_money(impact)
    refuse_uncorrectable_keys(corrected_payload)

    if invoice.status not in (models.INVOICE_ISSUED, models.INVOICE_PAID):
        raise BillingRuleError(
            f"bill {invoice.invoice_no or invoice.pk} is {invoice.status}: only a bill "
            "that was actually sent has a document worth reissuing (BR-BIL-030).",
            br_ref="BR-BIL-030",
        )
    original_payload = dict(invoice.bill_payload or {})
    if not original_payload:
        raise BillingRuleError(
            f"bill {invoice.invoice_no or invoice.pk} carries no locked document instance "
            "(BR-BIL-030), so there is nothing to correct a COPY of. Rendering a reissue "
            "from live customer and premises rows would print today's facts over a "
            "historical period — the exact failure the locked payload prevents.",
            br_ref="BR-BIL-030",
        )

    tenant_id = core_tenancy.current_tenant_id()
    # DEF-084 · PO 2026-08-12, *"Accumilate"*. THE BASE IS THE DOCUMENT BEFORE
    # THIS ONE, and the invoice's frozen payload only when there is no reissue
    # yet. Ordered by `instance_no` for the reason `default_document_for_reprint`
    # gives: it counts up under a unique constraint, so "the one before this" is
    # a fact rather than a race with `created_at`. The invoice row is READ here
    # and nowhere written — accumulation is bought with a new row, never with an
    # edit to the frozen payload (hard rule 4 · BR-BIL-030).
    previous = (
        InvoiceDocumentInstance.objects.filter(tenant_id=tenant_id, invoice=invoice)
        .order_by("-instance_no")
        .first()
    )
    base_payload = original_payload if previous is None else dict(previous.payload or {})
    next_no = 1 if previous is None else previous.instance_no + 1

    # BOTH the diff and the nothing-changed refusal read the BASE, not the
    # invoice, and they must agree on which document they mean. Against the
    # invoice, re-supplying a fix the previous instance already made would still
    # differ from the ORIGINAL, pass this guard, and write a byte-identical twin
    # of instance N-1 — two documents on file, no way to say which anybody meant,
    # which is the ambiguity BR-BIL-041 refuses. `changed_fields` is likewise
    # what THIS correction changed on the document it supersedes: instance 2 did
    # not touch a name instance 1 fixed and must not claim to.
    changed = {
        key: [base_payload.get(key), value]
        for key, value in corrected_payload.items()
        if base_payload.get(key) != value
    }
    if not changed:
        raise BillingRuleError(
            "every value supplied already matches the document this correction would "
            "supersede, so there is nothing to reissue. A second identical instance would "
            "leave two documents on file and no way to say which one anybody meant.",
            br_ref="BR-BIL-041",
        )

    # CORRECTIONS ACCUMULATE (PO 2026-08-12, *"Accumilate"*). Instance N carries
    # every earlier fix plus its own. This used to compose from
    # `{**original_payload, **corrected_payload}` — from the INVOICE every time —
    # so a second correction reverted the first, and the reprint ruling of the
    # same day put that reverted page in the customer's envelope (DEF-084).
    #
    # THE RISK THE PO ACCEPTED, RECORDED HERE RATHER THAN FORGOTTEN: accumulating
    # carries forward a correction somebody later decides was wrong. Undoing one
    # is a FURTHER correction restating the right value, never a revert — there
    # is no path back to an earlier instance's version of a field except by
    # correcting it again, and the superseded instances stay on file as the
    # record of what each page said.
    reissued_payload = {**base_payload, **corrected_payload}

    # THE ORIGINAL ROW IS NEVER SAVED. `copy.copy` gives an in-memory twin whose
    # payload is the corrected one, purely so the renderer — which reads the
    # invoice it is handed and that invoice's own lines, and nothing else — can
    # produce the page. Nothing calls `.save()` on it and nothing may: the
    # trigger would refuse, and the refusal is asserted by test.
    preview_row = copy.copy(invoice)
    preview_row.bill_payload = reissued_payload
    rendered = documents.render_invoice(
        preview_row,
        template_id=invoice.template_id,
        template_version=invoice.template_version,
    )

    # `next_no` is the PREVIOUS instance's number plus one, taken above from the
    # same row the payload was composed from. It used to be a `count() + 1`,
    # which agrees only while nothing is ever removed; `max + 1` is the value the
    # unique constraint on (tenant, invoice, instance_no) can never collide with,
    # and it is the number `default_document_for_reprint` orders by.
    instance = InvoiceDocumentInstance.objects.create(
        tenant_id=tenant_id,
        invoice=invoice,
        case=case,
        instance_no=next_no,
        payload=reissued_payload,
        payload_version=invoice.payload_version,
        template_id=invoice.template_id,
        template_version=invoice.template_version,
        reason_codes=list(impact.reason_codes),
        master_data_ref=master_data_ref,
        changed_fields=changed,
        created_by_id=getattr(actor, "id", None),
        reissued_on=on_date,
    )

    problems: list[dict[str, Any]] = []
    if getattr(rendered, "pdf_unrepresentable", ()):  # OQ-150 — reported, never guessed
        problems.append(
            {
                "code": "pdf_unrepresentable",
                "br_ref": "BR-BIL-033 · OQ-150",
                "detail": "the reissued page cannot show every character of the corrected "
                f"value ({', '.join(str(item) for item in rendered.pdf_unrepresentable)}): "
                "the PDF uses the Base-14 fonts without embedding, so its repertoire is "
                "WinAnsi. The value is correct in the payload and in the HTML; the PAGE "
                "substitutes. Whether that should REFUSE the reissue is OQ-150 and is not "
                "decided here.",
            }
        )

    audit.money_action(
        actor,
        "correction.document_reissued",
        "invoice_document_instances",
        str(instance.pk),
        after={
            "invoice_id": str(invoice.pk),
            "invoice_no": invoice.invoice_no,
            "instance_no": next_no,
            "changed_fields": sorted(changed),
            "money_delta": "0.00",
            "credit_note": "none",
            "rebill": "none",
            "journal_entries": "none",
            "invoice_status_unchanged": invoice.status,
            "master_data_ref": master_data_ref,
            "reissued_on": on_date.isoformat(),
        },
    )
    return corrections.ExecutedBill(
        invoice_id=str(invoice.pk),
        document_instance_id=str(instance.pk),
        problems=tuple(problems),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-031@c41f9a2 (ships with apps/billing/correction_models.py — the same four sources)
# generated: 2026-08-11 by story-coder (W5 corrections + notices lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — no S30 correction endpoint exists) E=deferred(no-frontend-half — S30's Fix-a-bill tab is unbuilt) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report for the verbatim RED transcript — the D-class
#         money guard was broken deliberately, RUN, and the measured failure
#         quoted before it was trusted green (hard-won law 7). AMENDED
#         2026-08-15 (correction-rulings lane): tc6/tc6b/tc6c were written first
#         and run against the pre-ruling build, where all three failed
#         `NotImplementedError: bill BL-2608-018411 has a reissued document
#         instance as well as the one that was originally sent, and no rule says
#         which a later reprint, re-send or dispute copy renders by default
#         (OQ-169 …)` at apps/billing/document_correction.py:160.
#         AMENDED AGAIN 2026-08-15 (DEF-084 accumulate lane): tc6d/tc6e/tc6f
#         were written first and RUN against the unfixed build — 3 failed, the
#         first of them `AssertionError: DEF-084: the name fix instance 1 made
#         is CARRIED FORWARD, not reverted — corrections accumulate
#         (PO 2026-08-12) / assert 'Sara Whitfield' == 'Sarah Whitfield'`, the
#         misspelt name coming back on the page the reprint ruling delivers.
#         MEASURED GREEN after the fix: ruff✔ · black✔ · this story's file 15/15
#         · backend suite 2061 passed, 132 skipped, 1 xfailed · run_gates
#         17-PASS/3-FAIL, none of the three in this file or this module's
#         document path (G1+G11: the timezone lane's untrailered
#         07-frontend/.../SettingsTimezone.test.tsx; G8: the back-bill lane's
#         apps/billing/backbill.py:89, which turned FAIL mid-session).
# exceptions: (1) US-BIL-031's FRONTMATTER SAYS `status: blocked` ON OQ-103 AND
#         THAT IS STALE: the PO closed OQ-103 on 2026-08-11 with option (a)
#         REISSUE, and the registry records the closure. The artifact is built
#         to the RULING. REPORTED — the story file is not this lane's to edit
#         without the same sweep updating its `blocked_by`.
#         (2) OQ-169 IS CLOSED — PO 2026-08-12, *"Reissue a corrected copy"*
#         (AMENDED 2026-08-15). This line used to say the sub-question was
#         MINTED as OQ-169 and that `default_document_for_reprint` raised on it.
#         It does not raise any more: a later reprint, re-send or dispute copy
#         renders the newest reissued instance, *"because that is the document
#         the customer is entitled to"*, and the ORIGINAL only while no reissue
#         exists. The original is retained, byte-identical, and reachable by id
#         — the ruling settled the DEFAULT, not which documents exist.
#         (2b) LATEST-WINS WITH TWO REISSUES IS THIS LANE'S READING, not the
#         PO's words: they were shown one reissue. Instance 1 is a copy the
#         utility has itself superseded, so the entitlement runs to the current
#         one. Stated so it can be disagreed with.
#         (2c) DEF-084 IS FIXED HERE — PO 2026-08-12, *"Accumilate"*
#         (AMENDED 2026-08-15). This line used to REPORT the defect and decline
#         it: `execute_document_correction` composed EVERY reissue from the
#         INVOICE's frozen payload (`{**original_payload, **corrected_payload}`)
#         and never from the instance before it, so a second document correction
#         REVERTED the first — fix the name, then fix the address, and the
#         reissue a reprint rendered carried the misspelt name again. Each
#         reissue is now composed from the instance BEFORE it and the invoice's
#         frozen payload is the base for the FIRST reissue only. Proved RED
#         first (hard-won law 7): tc6d/tc6e/tc6f were written against the
#         unfixed build and failed `AssertionError: DEF-084: the name fix
#         instance 1 made is CARRIED FORWARD, not reverted — corrections
#         accumulate (PO 2026-08-12) / assert 'Sara Whitfield' == 'Sarah
#         Whitfield'` — the misspelt name coming back, measured. tc6b's
#         defect-pinning assertion was flipped in the same change.
#         (2c-i) THE RISK THE PO ACCEPTED, ON THE RECORD: accumulating carries
#         forward a correction somebody later decides was wrong, so undoing one
#         is a further correction and never a revert. Carried in the module
#         docstring and beside the compose line, not only here.
#         (2c-ii) THE DIFF BASE AND THE NOTHING-CHANGED REFUSAL MOVED WITH THE
#         COMPOSE BASE, and that is this lane's reading rather than the PO's
#         words: `changed_fields` records what THIS correction changed on the
#         document it SUPERSEDES, and a value the previous instance already
#         carries is refused as "nothing to reissue" (tc6f). Against the invoice
#         instead, instance 3 would claim to have changed a name instance 1
#         fixed, and re-submitting an existing fix would write a byte-identical
#         twin — the ambiguity BR-BIL-041 refuses. ⚠ REPORTED, NOT EDITED:
#         `correction_models.InvoiceDocumentInstance.changed_fields` still
#         comments *"the FIELDS that differ from the original payload"*; that
#         file is another lane's and belongs to the same 🔒 set.
#         (2d) NOTHING CALLS `default_document_for_reprint` YET (hard-won law 2,
#         stated rather than implied): `GET /invoices/{id}/document` is not
#         mounted and S30's reprint control is unbuilt, so this is a published
#         answer waiting for its caller, not a wired feature.
#         (2e) THIS FILE IS ON THE G7 LIST — 10-scripts/gates/human_owned.txt
#         line 118, *"Keeps a corrected document and the books saying the same
#         thing — hard rule 4"*. Its HUMAN-OWNED · HUMAN-REVIEW-PENDING markers
#         are KEPT and its ledger row still stands: a ruling implemented is not
#         a human review recorded.
#         (3) A NAME THE PAGE CANNOT SPELL IS REPORTED, NOT REFUSED (OQ-150,
#         still open). The renderer's shipped reading (B) is carried through
#         rather than a second answer being invented here.
#         (4) NO MASTER-DATA WRITE. BR-BIL-049 — the case records the reference
#         and performs nothing; `apps/customers` belongs to another module and
#         another lane.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
