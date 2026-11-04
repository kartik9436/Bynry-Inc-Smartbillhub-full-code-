# ── Trace ──────────────────────────────────────────────
# Change:   CR-049 task 4 — "The bill: store the PDF and HTML at issue". Closes
#           DEF-2553 (the page titled *view the bill as sent* rebuilt the bill
#           on every open).
# Rules:    BR-NOT-027 (a legal document is FROZEN AS THE DOCUMENT when it is
#           sent, and a reproduction serves THAT — never a fresh render; PO
#           2026-08-30, and the rule reaches the BILL) · BR-BIL-030 (the bill's
#           INPUTS are frozen — a different rule, see below) · BR-BIL-026 /
#           BR-NOT-025 (the pin is PROVENANCE, not the rendering input) ·
#           BR-BIL-033 (a bill that cannot become a document does not issue —
#           extended here to one that cannot be KEPT) · BR-BIL-036 (print is
#           the primary channel and the document must be STORED) · NFR-33 /
#           NFR-35 (write-once, seven years) · BR-TEN-043 (the event time is
#           named by the caller, never a clock) · CLAUDE.md rule 1 (tenant
#           scoping) · rule 4 (financial immutability) · rule 7 (audit) ·
#           hard-won law 1 (a guarantee with no visible failure mode) ·
#           B2 §2 (no cross-module writes)
# Tests:    06-backend/tests/test_cr049_t4_bill_freeze.py
# Impacts:  apps/billing/issue.py (calls `freeze_at_issue` and cannot move a
#           bill to `issued` without its answer) · apps/billing/documents_api.py
#           (serves `reproduce()` and must never render in its place) ·
#           07-frontend BillDocumentPage (the two states, drawn)
# ───────────────────────────────────────────────────────
"""The bill, kept as the bill — and named honestly when it was not.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides **whether a bill may be
issued at all** and **what is kept as the document the customer received**, which
is the same authority `apps/billing/documents.py` and `issue.py` already carry
either side of it. AI-authored 2026-08-30 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*); row in
`12-governance/09-human-review-ledger.md`, glob in
`10-scripts/gates/human_owned.txt`.

PO, 2026-08-30, verbatim: *"any legal document when send - it is freezed - we
should keep all underline data, but actual leter and PDF should be freeze - any
changes to tempalte or any items hsould be noted as changed; that way it will
keep the santity of the legal documents; otherwie everytime we reproduce it
using data in table, we might change something about it and that is not
correct"*.

⚠ WHY A BILL NEEDED THIS AT ALL — THE MISTAKE THIS FILE EXISTS TO CORRECT
--------------------------------------------------------------------------
`BR-BIL-030` freezes the bill's INPUTS: `bill_payload` and `custom_snapshot`,
held immutable by `billing/migrations/0006`'s trigger. It was read twice — in
`CR-049` itself and out loud to the PO — as freezing the DOCUMENT, and it does
not. `documents.RenderedDocument` is a dataclass, not a model; `_pdf()` re-ran on
every request; **no stored HTML or PDF existed for any bill anywhere in this
product.**

The gap that leaves is narrow and real. Every figure, name and date on a
re-rendered bill IS correct, because the data is frozen. What is not frozen is
the PRESENTATION — **and the boundary is worth stating precisely, because half
of it turned out to be protected already:**

| | Protected, and by what |
|---|---|
| the bill's DATA | `billing/0006`'s immutability trigger on `bill_payload` |
| the tenant's chosen template ROW | `billing_template_version_frozen` (billing `0019`) — *"only status may change once a version leaves draft"* |
| **the CODE that draws the page** | ⛔ **NOTHING.** A layout is Python. The day somebody improves `_html_for` — a heading, a column, an escape — every historical bill re-renders differently and **no row anywhere records that it happened.** |
| **the platform's LIBRARY of layouts** | ⛔ **NOTHING.** A build that no longer publishes a key a pinned row names sends `_layout_for` down its stand-in door, and the bill prints on a different layout. That is a rollback, and `_layout_for`'s own docstring names it. |

⚠ **THE FIRST DRAFT OF THIS FILE PUT THE TEMPLATE-ROW EDIT IN THE FIRST ROW OF
THAT TABLE AND IT WAS WRONG.** The test that proved it passed on SQLite, which
the suite hardcodes and which has no triggers; a real PostgreSQL refused the same
edit with the trigger's own sentence — *"changing it here would rewrite what
those customers were sent without touching a single invoice row."* Corrected
rather than left standing (hard-won law 1), and it is law 14's shape in a second
costume: green on the suite's database, wrong about production.

The two rows that remain are `DEF-2504`'s rights-clause defect one domain over,
and both are the PO's *"we might change something about it"* exactly.

WHAT IS FROZEN, AND WHY BOTH — SAID PLAINLY BECAUSE IT IS EASY TO OVERSTATE
-----------------------------------------------------------------------------
| Artefact | Media type | Where it comes from |
|---|---|---|
| the bill as HTML | `text/html; charset=utf-8` | `RenderedDocument.body` |
| the printable page | `application/pdf` | `RenderedDocument.pdf` |

**Both are artefacts of the shipped path and neither is rendered specially for
the store.** They are the two serialisations of the ONE structure
`documents.render_invoice` has produced since 2026-08-11, from the same call
`issue.py` has always made to satisfy `BR-BIL-033` and used to throw away.

⚠ **AND THAT IS THE WHOLE DIFFERENCE FROM THE NOTIFICATION SIDE, WHICH FREEZES
TEXT AND NOT A PDF.** `notifications/frozen_documents.py` argues, correctly, that
rendering a PDF at freeze time would freeze a document the customer never
received — the substitution `BR-NOT-027` exists to forbid. That argument holds
there because the print channel hands the vendor TEXT. It does not apply here:
the bill's PDF is not made for the freeze, it is what
`GET /invoices/{id}/document.pdf` already serves and what `BR-BIL-036` calls the
print floor. **`OQ-149` is still OPEN and nothing here closes it** — the page is
the Base-14 floor, not a designed bill with a logo, a usage graph or a barcode,
and the day a real HTML/CSS engine lands, what is frozen becomes that page with
no change to this file's rule.

⚠ THE FREEZE IS A PRECONDITION OF ISSUING, NOT A CUTOVER
----------------------------------------------------------
`CR-049` step 4, verified rather than assumed: nothing has been sent to a
customer (`provider_seam.PLATFORM_ADAPTERS` carries `in_app` and nothing else),
so there is no era before the rule and nothing to grandfather. `issue.py`
therefore REFUSES to move a bill to `issued` unless both artefacts were kept —
one atomic act, so a bill that cannot be kept stays a correctable DRAFT rather
than becoming an immutable record of a document nobody has.

**This option expires at go-live**, which is why it is taken now: after the first
real bill run, a refusal here would leave a customer holding a bill the product
will not admit to.

⚠ NOTHING ON THE INVOICE IS WRITTEN, AND THAT IS DELIBERATE (hard rule 4)
--------------------------------------------------------------------------
There is no `document_id` column on `invoices` and this file adds none. The
pointer runs the other way: `stored_documents.source_type = 'invoice'` and
`source_id = <the bill>`, indexed as `(tenant, source_type, source_id)`. So
storing an artefact touches no issued financial row at all — no UPDATE, nothing
for the immutability trigger to refuse, and nothing that could be got wrong on a
correction, because a corrected bill is a NEW invoice and therefore a new
document.

⚠ THE HONEST HALF IS NOT OPTIONAL
-----------------------------------
`reproduce()` answers `original` or `re_rendered_from_data_not_the_original` and
never an empty success. The precondition above should make the second
unreachable for anything issued from `v2.88.0` onwards. **It stays anyway**,
because a guarantee with no visible failure mode is the shape hard-won law 1
warns about — and because every bill issued BEFORE this shipped genuinely has no
original, and a clerk opening one must be told that rather than shown a
convincing rebuild.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Any

from apps.tenancy import document_storage, document_store

# ═══════════════════════════════════════════════════════════════════════════
# WHAT A BILL FREEZES
# ═══════════════════════════════════════════════════════════════════════════

#: The store's `source_type` for a bill. `source_id` is the invoice's own id, so
#: the pair is unique without anything else being invented.
STORE_SOURCE_TYPE = "invoice"

#: The store's document kind. One kind covers the bill, the final bill and a
#: corrected/reissued copy — the PO's `CR-049` step-5b scope table names all
#: three as *"the bill"*, and each is a separate INVOICE, so each gets its own
#: row under the same kind.
DOCUMENT_KIND = "bill"

#: ⚠ `channel` IS `None` ON BOTH ARTEFACTS, AND IT IS NOT AN OVERSIGHT.
#: `document_store.store` says a channel is `None` when a document is frozen at
#: CREATION rather than at SEND. A bill is frozen when it is ISSUED; the letter
#: that ANNOUNCES it (`bill_ready_notice`) is a different document that leaves on
#: a channel and is frozen by the dispatcher. Giving the bill a channel here
#: would make the two look like one document sent twice.
STORE_CHANNEL = None

#: `(attribute on RenderedDocument, media type, filename extension)`.
#: **The order is the order they are stored in**, and the HTML is first because
#: it is what a screen shows; nothing depends on the order beyond the trail
#: reading in the sequence a person would expect.
ARTEFACTS: tuple[tuple[str, str, str], ...] = (
    ("body", "text/html; charset=utf-8", "html"),
    ("pdf", "application/pdf", "pdf"),
)

#: The media type a screen asks for when it wants the document a person reads.
HTML_CONTENT_TYPE = ARTEFACTS[0][1]

#: The media type the printable page is stored under.
PDF_CONTENT_TYPE = ARTEFACTS[1][1]

#: Anything outside this is replaced in a human filename. An export unpacks these
#: onto a filesystem, and an account number carrying a slash would write into a
#: directory nobody asked for — `document_store` refuses such a name outright, so
#: this is what stops a lawful account number becoming an unstorable bill.
_UNSAFE_IN_A_NAME = re.compile(r"[^A-Za-z0-9._-]+")


# ═══════════════════════════════════════════════════════════════════════════
# WHY A FREEZE DID NOT HAPPEN — CODES, never prose
# ═══════════════════════════════════════════════════════════════════════════
# The bill run groups on these exactly as it groups on the renderer's own, and a
# run summary cannot group on a sentence.

#: A serialisation came back empty. A blank bill must not become immutable, and
#: "the document exists" must not become true about an empty file.
FREEZE_ARTEFACT_EMPTY = "rendered_artefact_is_empty"

#: The store itself refused — an unreachable bucket, a name it will not take, a
#: kind nobody ruled. Its own sentence travels on `detail`.
FREEZE_STORE_REFUSED = "document_store_refused"

#: ⚠ An artefact ALREADY exists for this bill and this media type, and rendering
#: it again produces DIFFERENT bytes. On a bill this should be unreachable — a
#: bill issues once — so reaching it means something re-issued an issued bill
#: after the wording moved underneath it. Neither copy may be used silently.
FREEZE_ARTEFACT_DIFFERS = "frozen_artefact_differs_from_todays_render"


class NotFrozen(RuntimeError):
    """A bill was about to be marked `issued` with no kept copy behind it.

    ⚠ **THIS IS THE SECOND GUARANTEE, NOT THE FIRST.** The first is the ORDER in
    `issue._do_issue`: the freeze happens before the status moves and a refusal
    raises inside the same transaction, so the draft is still a draft. This
    exists because a guarantee whose only enforcement is the order of two
    statements is one refactor away from being gone (hard-won law 1), and because
    `_mark_issued` takes the freeze answer as a REQUIRED argument, so a future
    call site cannot silently omit it.
    """


# ═══════════════════════════════════════════════════════════════════════════
# THE ANSWER A FREEZE GIVES
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class FreezeOutcome:
    """Whether this bill may now be issued, and what was kept — never ambiguous.

    `may_issue` is a VALUE and not an inference, for the same reason
    `document_store.DocumentLookup` and `notifications.FreezeOutcome` are: a
    caller that read it off an empty list would eventually read a DIFFERENT empty
    list the same way. `require_frozen` checks both — the value AND the
    artefacts — because on a bill there is no exempt case: every bill freezes,
    every time, so an outcome that says yes and kept nothing is a bug and not a
    state.
    """

    may_issue: bool
    documents: tuple[Any, ...] = ()
    #: True when the artefacts were already kept by an earlier attempt and this
    #: call re-used them. Nothing stores a second copy.
    reused: bool = False
    problem: dict[str, Any] | None = None
    #: The artefacts by media type, for a caller that wants one of them by name
    #: rather than by position.
    by_content_type: dict[str, Any] = field(default_factory=dict)


def _problem(code: str, *, invoice: Any, content_type: str, detail: str) -> dict[str, Any]:
    return {
        "code": code,
        "br_ref": "BR-NOT-027",
        "invoice_id": str(invoice.pk),
        "invoice_no": invoice.invoice_no,
        "content_type": content_type,
        "detail": detail,
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE HUMAN NAME
# ═══════════════════════════════════════════════════════════════════════════


def display_name(invoice: Any, *, extension: str, moment: dt.datetime) -> str:
    """The name this bill unpacks to in a bulk export — `bill/2026/07/A-10432-BL-…`.

    `document_store` refuses to compose one and says why: a usable name needs the
    account number, which lives in `customers`, and reading it from there is the
    cross-module read B2 §2 forbids.

    ⚠ **BILLING IS IN A BETTER POSITION THAN THE DISPATCHER HERE, AND IT IS WORTH
    SAYING WHY.** `CR-049` records a follow-up: the dispatcher holds `account_id`
    and not `account_no`, so a notification currently exports as
    `disconnect_notice/2026/08/MSG-0198f3c2-pdf_print.txt` — the row is named and
    the customer is not. **A bill has no such problem**: `bill_payload.account_no`
    is stamped at draft by billing's own stage 6 and frozen with the bill, so the
    name is both correct and historical, and no cross-module read is involved.
    A bill whose payload carries no account number falls back to the invoice
    number alone, which is still a name a person can act on.
    """
    account_no = str((invoice.bill_payload or {}).get("account_no") or "").strip()
    invoice_no = str(invoice.invoice_no or "").strip()
    parts = [p for p in (_safe(account_no), _safe(invoice_no)) if p]
    label = "-".join(parts) or f"INV-{str(invoice.pk)[:8]}"
    return f"{DOCUMENT_KIND}/{moment:%Y}/{moment:%m}/{label}.{extension}"


def _safe(value: str) -> str:
    return _UNSAFE_IN_A_NAME.sub("-", value).strip("-")


# ═══════════════════════════════════════════════════════════════════════════
# THE WRITE — called by `issue.py` BEFORE the status moves
# ═══════════════════════════════════════════════════════════════════════════


def freeze_at_issue(
    invoice: Any,
    rendered: Any,
    *,
    moment: dt.datetime,
    actor: Any = None,
    job: str | None = None,
) -> FreezeOutcome:
    """Keep this bill as the customer will read it — or refuse to issue it.

    Called ONCE per bill, **inside the issue transaction and before the status
    moves**. A `FreezeOutcome` whose `may_issue` is False means the caller raises:
    the bill does not issue, it stays a correctable draft, and the reason is one
    named break on one bill exactly as a failed render is (`BR-BIL-055`).

    ⚠ **`moment` IS PASSED IN, NEVER READ FROM A CLOCK** (`BR-TEN-043`, and G6
    greps this module for one). It is the bill's own `issued_at`, so the key and
    the human name land in the month the bill was issued rather than the month
    the job happened to run.

    ⚠ **THE BYTES ARE WRITTEN BEFORE THE ROW** — `document_store.store` argues
    it, and it matters here because this runs inside a transaction: a rollback
    removes the row and leaves an object no row names, which nothing lists and a
    lifecycle rule sweeps. The opposite order would leave a permanent record of a
    document that does not exist, and the row can never be deleted.
    """
    kept: list[Any] = []
    by_type: dict[str, Any] = {}
    reused = False

    for attribute, content_type, extension in ARTEFACTS:
        payload = getattr(rendered, attribute, None)
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        if not payload:
            return FreezeOutcome(
                may_issue=False,
                problem=_problem(
                    FREEZE_ARTEFACT_EMPTY,
                    invoice=invoice,
                    content_type=content_type,
                    detail=(
                        f"this bill's {content_type} serialisation came back empty, so "
                        "there is nothing to keep and nothing worth sending. A blank bill "
                        "reaching a customer is worse than one that has not gone out, and "
                        "an empty frozen file would make 'we kept the bill' true about "
                        "nothing at all. The bill stays a DRAFT and is still correctable."
                    ),
                ),
            )

        existing = document_store.for_source(
            source_type=STORE_SOURCE_TYPE,
            source_id=invoice.pk,
            channel=STORE_CHANNEL,
            content_type=content_type,
        )
        if existing.found:
            # A bill issues once, so this is unreachable through the shipped
            # path. It is kept because the alternative — storing a second copy —
            # would mean "serve the frozen copy" had to CHOOSE one, and a chooser
            # is a re-render wearing a different coat.
            if document_storage.content_hash(payload) == existing.document.content_hash:
                kept.append(existing.document)
                by_type[content_type] = existing.document
                reused = True
                continue
            return FreezeOutcome(
                may_issue=False,
                problem=_problem(
                    FREEZE_ARTEFACT_DIFFERS,
                    invoice=invoice,
                    content_type=content_type,
                    detail=(
                        "this bill was already kept once and rendering it again TODAY "
                        "produces different bytes — the presentation moved underneath an "
                        "issued document, which an edited template version does. Neither "
                        "copy may be used silently: the frozen one is the bill, and a "
                        "fresh render is the thing BR-NOT-027 forbids putting in its "
                        "place. This HOLDS for a person to look at."
                    ),
                ),
            )

        try:
            stored = document_store.store(
                kind=DOCUMENT_KIND,
                source_type=STORE_SOURCE_TYPE,
                source_id=invoice.pk,
                channel=STORE_CHANNEL,
                content_type=content_type,
                display_name=display_name(invoice, extension=extension, moment=moment),
                payload=payload,
                actor_user_id=getattr(actor, "id", None),
                process=job or "billing.issue",
            )
        except document_store.DocumentStoreError as refused:
            return FreezeOutcome(
                may_issue=False,
                problem=_problem(
                    FREEZE_STORE_REFUSED,
                    invoice=invoice,
                    content_type=content_type,
                    detail=str(refused),
                ),
            )
        kept.append(stored)
        by_type[content_type] = stored

    return FreezeOutcome(
        may_issue=True, documents=tuple(kept), reused=reused, by_content_type=by_type
    )


def require_frozen(invoice: Any, outcome: FreezeOutcome | None) -> None:
    """Refuse to advance a bill to `issued` without the freeze that precedes it.

    `issue._mark_issued` takes the outcome as a REQUIRED argument, so a new call
    site cannot forget it and a refactor that reorders the freeze past the status
    move goes RED here instead of shipping an unkept bill.

    ⚠ **IT CHECKS THE ARTEFACTS AS WELL AS THE VERDICT.** On a notification there
    are exempt cases — an in-app alert, a send test — so its equivalent must read
    the verdict alone. **A bill has none: every bill freezes, every time.** So an
    outcome that says yes and kept nothing is a bug, and this is where it stops.
    """
    if outcome is not None and outcome.may_issue and len(outcome.documents) == len(ARTEFACTS):
        return
    # ⚠ THE SENTENCE NAMES NO RULE ID (G28) — the rule is quoted at the top of
    # this module, which is where anybody reading this traceback already is.
    raise NotFrozen(
        f"bill {invoice.invoice_no or invoice.pk} was about to be marked `issued` with no "
        "kept copy of it behind it. Keeping the document is a PRECONDITION of issuing it, "
        "with no exceptions: nothing has ever been sent to a customer from this product, so "
        "there is no era before the rule and nothing to grandfather. Freeze it first, or "
        "leave it a draft."
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE READ — CR-049 task 7's sentence, for the bill
# ═══════════════════════════════════════════════════════════════════════════

#: This IS the document that was issued, byte for byte.
PROVENANCE_ORIGINAL = "original"

#: This is NOT it. It is a fresh render from the frozen data and today's
#: presentation, and it may differ from what the customer holds.
#: ⚠ **NEVER SHOWN WITHOUT SAYING SO.** That is the whole of `BR-NOT-027`'s
#: honest half: the figures will be right and the document can still be a
#: different document.
PROVENANCE_RE_RENDERED = "re_rendered_from_data_not_the_original"

#: i18n keys for the sentence a screen draws beside a reproduction. The copy
#: lives in `07-frontend/src/i18n/locales/*.json`; the KEY is chosen here so the
#: backend and the S30 page cannot describe the same state in two different ways.
I18N_ORIGINAL = "billing.document.original"
I18N_RE_RENDERED = "billing.document.reRendered"


@dataclass(frozen=True)
class Reproduction:
    """How a reproduction of one issued bill must be SERVED. Never ambiguous.

    ⚠ **`provenance` IS A VALUE A CALLER MUST BRANCH ON, AND THERE IS NO THIRD
    STATE THAT MEANS "PROBABLY".** A caller that draws a re-render without
    drawing `i18n_key`'s sentence has produced the defect `BR-NOT-027` was
    written for: a fresh document presented as the bill that was issued.

    `html` and `pdf` are set only for `PROVENANCE_ORIGINAL`. `unavailable_reason`
    is `document_store`'s own code (`document_not_stored`), passed through rather
    than re-spelled, so one vocabulary describes one fact.
    """

    invoice_id: str
    provenance: str
    html: Any = None
    pdf: Any = None
    unavailable_reason: str | None = None
    i18n_key: str = ""
    detail: str = ""

    @property
    def is_original(self) -> bool:
        return self.provenance == PROVENANCE_ORIGINAL


def reproduce(invoice: Any) -> Reproduction:
    """Is there an original for this bill — or must a reproduction say it is not?

    ⚠ **THIS DOES NOT RENDER ANYTHING.** It answers WHICH document a caller may
    serve. `documents_api` serves it; if that module ever renders over a bill this
    function called ORIGINAL, the rule is broken in the product while every test
    here still passes.

    A DRAFT has no original and never will until it issues, which is a true and
    useful answer rather than an error: the reproduction says the bill has not
    been issued, and the route's own refusal says the rest.
    """
    invoice_id = str(invoice.pk)
    html = document_store.for_source(
        source_type=STORE_SOURCE_TYPE,
        source_id=invoice.pk,
        channel=STORE_CHANNEL,
        content_type=HTML_CONTENT_TYPE,
    )
    if html.found:
        pdf = document_store.for_source(
            source_type=STORE_SOURCE_TYPE,
            source_id=invoice.pk,
            channel=STORE_CHANNEL,
            content_type=PDF_CONTENT_TYPE,
        )
        return Reproduction(
            invoice_id=invoice_id,
            provenance=PROVENANCE_ORIGINAL,
            html=html.document,
            pdf=pdf.document,
            i18n_key=I18N_ORIGINAL,
            detail=(
                "this is the bill as it was issued, kept at the moment it was made and "
                "never re-rendered since."
            ),
        )
    return Reproduction(
        invoice_id=invoice_id,
        provenance=PROVENANCE_RE_RENDERED,
        unavailable_reason=html.unavailable_reason,
        i18n_key=I18N_RE_RENDERED,
        detail=(
            "no copy of this bill was kept as it was issued, so anything shown here is "
            "REBUILT from the frozen data and today's page design — it is not the document "
            "the customer received and it may differ from it. The figures are right, "
            "because BR-BIL-030 freezes them; what can differ is the page they are printed "
            "on, which a change to the chosen layout moves."
        ),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-049 task 4 (sources: 12-governance/11-change-requests.md CR-049 steps 5b/5c/5d(c)/(d) and step 6-bis · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-027 · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-030/033/036 · 12-governance/10-defect-log.csv DEF-2553 · 06-backend/apps/tenancy/document_store.py, task 1's published service · 06-backend/apps/notifications/frozen_documents.py, the shape this follows)
# generated: 2026-08-30 by the CR-049 task 4 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the S30 route was shown serving `platform-layout-compact-letter-v1` for a bill issued on `platform-layout-standard-letter-v1` after a template edit, with the "Services this period" band gone from the document a customer was sent; and the store answered `document_not_stored` for every bill in the product. Verbatim transcripts in 06-backend/tests/test_cr049_t4_bill_freeze.py and the lane report.
# exceptions: (1) BOTH SERIALISATIONS FREEZE, INCLUDING A PDF — unlike the notification side, which freezes text. The bill's PDF is not rendered for the freeze: it is what `GET /invoices/{id}/document.pdf` already serves and what BR-BIL-036 calls the print floor. OQ-149 is untouched and still OPEN. (2) NOTHING IS WRITTEN ON THE INVOICE — the pointer is `stored_documents.source_id`, so hard rule 4 is not approached. (3) `require_frozen` checks the ARTEFACTS as well as the verdict, which its notifications counterpart cannot, because a bill has no exempt case. (4) `channel` is None on both rows: a bill freezes at CREATION, not at SEND.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
