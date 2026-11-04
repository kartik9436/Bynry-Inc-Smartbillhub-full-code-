# ── Trace ──────────────────────────────────────────────
# Story: Finance blueprint `P5.11` (p018, p064) — attach a document to a
#        purchase. ⚠ **THE BLUEPRINT SIZES THIS AS A SPIKE ON A FALSE PREMISE**
#        (`DEF-LED-6527`): *"the platform has no general attachment store at
#        all"*. It has had one since `CR-049`.
# Rules: CLAUDE.md prime directive (implement to the boundary; stub the gap as
#        `NotImplementedError("OQ-###")`; NEVER resolve an open question by
#        choosing a value) · `OQ-LED-12628` (the retention schedule — CLOSED 2026-09-25, `BR-LED-799`: seven years) ·
#        hard rule 1 (tenant scoping) · hard-won law 1 (a comment claiming a
#        guarantee is not the guarantee — so the store's claims are MEASURED
#        here rather than quoted)
# ───────────────────────────────────────────────────────
"""WHAT `P5.11` ACTUALLY COSTS, MEASURED AT SOURCE.

The brief told this lane the store already exists. CLAUDE.md hard-won law 1 says
a claim in a document is not the thing it claims, so this file CHECKS it: the
kind is storable, a document is findable from the purchase it belongs to, and a
cross-tenant read answers *not stored*.

WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first, per law 7
------------------------------------------------------------------
**(a) ASSERTING THE CONSTANT EXISTS.** `KIND_SUPPLIER_INVOICE == "supplier_
invoice"` is a tautology about a line this lane wrote. What matters is whether
the DATABASE takes it, so the storable case goes through `document_store.store`
and reads the row back.

**(b) A STUB TEST THAT ONLY CHECKS IT RAISES.** Any bug raises. The case asserts
the message is the OPEN QUESTION'S ID, because a stub that raises something else
is a stub nobody can trace to a decision.
"""

from __future__ import annotations

import uuid

import pytest

from apps.ledger import cost_capture
from apps.tenancy import document_models, document_store
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx


@pytest.mark.django_db
def test_the_write_door_is_lit_now_that_its_question_is_closed(brazos, marcus) -> None:
    """The door this case used to hold shut is open, because its question closed.

    ⚠ **UNTIL 2026-09-30 THIS CASE WAS
    `test_the_write_door_refuses_and_names_the_open_question`** and asserted that
    `attach_supplier_invoice_document` raised `NotImplementedError("OQ-LED-12628")`.
    Its own docstring said what it was for: *"the day `OQ-LED-12628` is ruled,
    this case goes red and names the file to change."* That day was
    **2026-09-25**: the PO ruled *"Seven years, same as tax receipts"*
    (`BR-LED-799`, decision log of that date, `ad936e8bb`), and `23a093318`
    (`DEF-LED-6708`, `P5.11`) removed the stub and lit the door the same morning
    — with a new required `content_type` argument. This case went red on that
    commit, doing exactly its job, with
    `TypeError: … missing 1 required keyword-only argument: 'content_type'`,
    and nobody moved it for five days.

    **What it asserts now is the other side of the same boundary:** the call
    that used to raise the question's id now STORES — on a real captured
    purchase, through the real store — and the document is findable from the
    purchase it belongs to. The constant still names the closed question,
    because the refusal it once carried cites it (`cost_capture.py` explains
    why the name is left for the lane that renames it).
    """
    from datetime import date
    from decimal import Decimal

    from tests.test_us_led_018_capture import brazos_ready

    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = cost_capture.capture_supplier_invoice(
            marcus,
            invoice_date=date(2026, 9, 1),
            service="electric",
            supplier_name="Brazos Valley Power Cooperative",
            amount=Decimal("28222.00"),
            currency="USD",
            reference="BVPC-090026",
        )
        documents = cost_capture.attach_supplier_invoice_document(
            marcus,
            supplier_invoice_id=captured["id"],
            filename="wholesale-sept.pdf",
            content_type="application/pdf",
            content=b"%PDF-1.4 the invoice that settles the argument",
        )
        found = document_store.for_source(
            source_type=document_models.SOURCE_SUPPLIER_INVOICE, source_id=captured["id"]
        )

    assert len(documents) == 1, documents
    assert found.unavailable_reason is None, found.unavailable_reason
    assert found.document.kind == document_models.KIND_SUPPLIER_INVOICE
    assert found.document.display_name.endswith("BVPC-090026-wholesale-sept.pdf")
    assert cost_capture.DOCUMENT_RETENTION_UNRULED == "OQ-LED-12628"


def test_the_kind_and_the_source_are_in_the_published_vocabularies() -> None:
    """The two names `P5.11` actually costs. They are what `document_store`
    validates against, so a value absent from these tuples is refused by
    `_require_choice` before the database is reached."""
    assert document_models.KIND_SUPPLIER_INVOICE in document_models.DOCUMENT_KINDS
    assert document_models.SOURCE_SUPPLIER_INVOICE in document_models.SOURCE_TYPES


@pytest.mark.django_db
def test_a_supplier_invoice_document_is_storable_and_findable_from_its_purchase(
    brazos, dana
) -> None:
    """⚠ **THIS IS THE CHECK THAT ANSWERS THE BLUEPRINT'S CLAIM**, and it goes
    through the real store rather than asserting a constant — per (a).

    It also demonstrates the design decision `supplier_invoices` gains no
    column for: a document is found by WHAT IT BELONGS TO, and a purchase can
    have several without a second place the same fact lives.
    """
    purchase = uuid.uuid4()
    with tenant_ctx(brazos):
        stored = document_store.store(
            kind=document_models.KIND_SUPPLIER_INVOICE,
            source_type=document_models.SOURCE_SUPPLIER_INVOICE,
            source_id=purchase,
            display_name="Wholesale power, September.pdf",
            payload=b"%PDF-1.4 the invoice that settles the argument",
            content_type="application/pdf",
            actor_user_id=dana.id,
        )
        assert stored is not None
        found = document_store.for_source(
            source_type=document_models.SOURCE_SUPPLIER_INVOICE, source_id=purchase
        )
    # ⚠ `for_source` RETURNS A WRAPPER, NOT A LIST, and the store's own
    # docstring says why: *"NEVER RETURNS AN EMPTY SUCCESS … a caller cannot
    # mistake absence for a document"*. Reading `.document` is how a caller is
    # forced past that distinction.
    assert found.unavailable_reason is None, found.unavailable_reason
    assert found.document.display_name == "Wholesale power, September.pdf"


@pytest.mark.django_db
def test_another_utility_cannot_tell_whether_this_document_exists(
    brazos, lonestar, dana
) -> None:
    """Hard rule 1, and the store's own posture: a cross-tenant read answers
    *not stored* — **the same answer as never existed** — so existence does not
    leak. Measured rather than quoted."""
    purchase = uuid.uuid4()
    with tenant_ctx(brazos):
        document_store.store(
            kind=document_models.KIND_SUPPLIER_INVOICE,
            source_type=document_models.SOURCE_SUPPLIER_INVOICE,
            source_id=purchase,
            display_name="Wholesale power, September.pdf",
            payload=b"%PDF-1.4",
            content_type="application/pdf",
            actor_user_id=dana.id,
        )
    with tenant_ctx(lonestar):
        blind = document_store.for_source(
            source_type=document_models.SOURCE_SUPPLIER_INVOICE, source_id=purchase
        )
    assert blind.document is None
    assert blind.unavailable_reason == document_store.DOCUMENT_NOT_STORED, (
        "the answer to another utility must be the SAME answer as never existed — "
        "a distinct 'you may not see this' leaks that it exists"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: Finance blueprint p018/p064 `P5.11` · `OQ-LED-12628` (OPEN) · `DEF-LED-6527`
# generated: 2026-09-24 by lane FIN-P5
# checklist: A✔ B✔ C✔ D✔ E=deferred(the screen half waits on the ruling) F✔ G✔ H=n/a
# gates: pytest tests/test_fin_p5_11_supplier_document.py — the storable case PROVED RED first by running it before tenancy/0051 existed, where the CHECK constraint refuses the value
# exceptions: (1) the WRITE DOOR is a stub and that is the deliverable, not a gap — `OQ-LED-12628` decides whether a supplier's PDF may be written under a seven-year write-once lock, and that choice is irreversible per file
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
