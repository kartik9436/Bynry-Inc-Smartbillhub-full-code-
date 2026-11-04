# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-015 · US-BIL-016 · US-BIL-017 (the corrections surface and
#           its approval gate) · US-BIL-018 · US-BIL-019 · US-BIL-020 (the
#           budget-billing surface) · US-BIL-021 (the bill-layout chooser) ·
#           US-BIL-022 (the document route) · US-BIL-031 (document-only
#           corrections, reached through the same case surface)
#           Screens: S30 (Fix a bill · Budget Bills · the document panel) ·
#           S8 (Bill layout)
# Rules:    BR-BIL-014 (nothing money-bearing before approval) · BR-BIL-041
#           (the mechanism is DERIVED, never supplied) · BR-BIL-044 (approval
#           binds the content-hashed artifact) · BR-BIL-017 (one live budget
#           status; the ±30% bound is measured against the COMPUTED level) ·
#           BR-BIL-021 (every parameter a tenant setting, never defaulted) ·
#           BR-BIL-026 (the pin; publishing affects only FUTURE bills) ·
#           BR-BIL-030 (the document renders from the frozen instance) ·
#           BR-BIL-027 (System Admin publishes) · BR-TEN-003 / HR-1
#           (cross-tenant reads as absent) · CLAUDE.md rule 2 (money) ·
#           rule 4 (immutability)
# ───────────────────────────────────────────────────────
"""The four billing surfaces that had a complete engine and no route.

**WHAT THIS FILE IS ACTUALLY GUARDING.** `10-scripts/gates/surface_debt.txt`
read `billing 17` — the worst engine-to-screen ratio in the product — and the
reason was never that the code was missing. It was that nothing mounted it. So
the first test in each section resolves the path THROUGH THE ROOT URLCONF and
then calls it over the wired stack, because an `api.py` exporting `urlpatterns`
that `config/urls.py` never includes is not an endpoint, and every other test in
this file would pass on a module nobody could reach.

**THE NEGATIVE ASSERTIONS ARE THE POINT**, exactly as in
`test_us_bil_025_026_bills_read.py`. The easy way to make a surface green is to
answer every field with something plausible — `eligible: true`, a computed level
of `0.00`, an approval that succeeds for anyone. Each of those is a sentence
about a customer's money that no row supports. So:

  · a correction PREVIEW writes no credit note, no rebill, no adjustment and no
    journal line — counted before and after, not taken on trust;
  · a caller that supplies a MECHANISM is refused (BR-BIL-041's silent-
    underbilling guard);
  · an approval by a Billing Clerk is refused by the SERVER;
  · an account with no billing history gets NO computed level and a stated
    reason — never `0.00`, which reads as "this customer pays nothing";
  · an account billed in two currencies is REFUSED rather than enrolled in one;
  · choosing a layout does not touch a bill already issued.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import budget_api, corrections, corrections_api, documents_api, models
from apps.billing import correction_reasons
from apps.billing import documents as billing_documents
from apps.billing import templates_api, templates_service
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, marcus, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call
from tests.test_us_bil_005_issue import (
    TEMPLATE_VERSION,
    a_priced_draft,
    an_authorised_run,
)
from tests.test_us_bil_022_documents import a_stage6_payload, an_issued_bill
from tests.test_us_bil_016_bulk_corrections import (
    a_corrected_bill,
    an_issued_bill as a_hand_built_bill,
    money_row_counts,
)
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 16)


@pytest.fixture
def supplied_recompute(monkeypatch):
    """WE-9's recomputation, HANDED IN — the same posture the correction suite
    takes and for the same reason it records: *"re-pricing through the real
    rating path here would make every assertion depend on rating's fixtures
    rather than on this workflow."* B5 owns the frozen figures and the golden
    suite asserts the engine that produces them; what this file tests is the
    SURFACE over the workflow."""
    monkeypatch.setattr(corrections, "recompute", a_corrected_bill)


# ══════════════════════════════════════════════════════════════════════════
# US-BIL-022 — the document route
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_022_tc20__the_document_route_is_actually_mounted(brazos, dana):
    """`GET /invoices/{id}/document` resolves through the ROOT URLconf.

    `documents.py`'s own `DOCUMENT_UNAVAILABLE` said this route was unmounted
    *"so no human can open one either (hard-won law 2)"*. This is the assertion
    that stops that sentence coming back.
    """
    from django.urls import resolve

    match = resolve(f"/api/{brazos.subdomain}/invoices/{uuid.uuid4()}/document")
    assert match.func.cls.__module__ == "apps.billing.documents_api"
    match_pdf = resolve(f"/api/{brazos.subdomain}/invoices/{uuid.uuid4()}/document.pdf")
    assert match_pdf.func.cls.__module__ == "apps.billing.documents_api"


def test_us_bil_022_tc21__an_issued_bill_serves_its_document_and_its_gaps(brazos, dana):
    """The bill a person can open — structure, HTML, page link and every gap.

    The four tuples travel SEPARATELY and the test says why: `absent` is what
    this bill's snapshot lacks, `unavailable` is what the build cannot do at
    all. A screen that merged them would tell a clerk a missing total due and an
    un-embeddable font are the same kind of problem.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        response = api_call(
            documents_api.invoice_document,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            invoice_id=str(bill.pk),
        )
    assert response.status_code == 200
    body = response.data
    assert body["invoice_no"] == bill.invoice_no
    assert body["template_version"] == TEMPLATE_VERSION
    assert body["currency"] == bill.currency
    assert body["pdf_page_count"] >= 1
    assert body["pdf_url"].endswith("/document.pdf")
    assert "<article" in body["body"]
    # Every money value on the document carries the currency ON THE ENVELOPE
    # (rule 2) — the fields themselves are display strings the renderer already
    # formatted, and `currency` above is what names them.
    assert {"absent", "unavailable", "problems", "pdf_unrepresentable"} <= set(body)
    assert isinstance(body["unavailable"], list) and body["unavailable"]


def test_us_bil_022_tc22__a_draft_is_refused_with_a_reason_not_a_404(brazos, dana):
    """A draft has no pin, so there is nothing to render — and the clerk is
    LOOKING at the bill, so the refusal must not be the HR-1 not-found."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run, bill_payload=a_stage6_payload())
        response = api_call(
            documents_api.invoice_document,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            invoice_id=str(draft.pk),
        )
    assert response.status_code == 422, (
        "a draft must NOT read as 404: the bill exists and the clerk is looking at it. "
        "The HR-1 not-found is reserved for an unknown, malformed or cross-tenant id."
    )
    assert response.data["code"] == errors.BIZ_COMPLETENESS
    assert "template" in response.data["params"]["detail"].lower()


def test_us_bil_022_tc23__the_printable_page_comes_back_as_a_pdf(brazos, dana):
    """BR-BIL-036's floor, over HTTP: bytes, `application/pdf`, INLINE.

    Inline rather than an attachment because a clerk on a phone call wants the
    page beside the account; the filename still carries the BILL NUMBER so a
    save is not called by a uuid.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        response = api_call(
            documents_api.invoice_document_pdf,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            invoice_id=str(bill.pk),
        )
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert bill.invoice_no in response["Content-Disposition"]


# ══════════════════════════════════════════════════════════════════════════
# US-BIL-021 — the bill-layout chooser (PO ruling 2026-08-16)
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_021_tc20__the_library_is_five_layouts_that_render_differently(brazos, dana):
    """THE CHOOSER IS NOT FIVE NAMES FOR ONE PAGE.

    `templates_service` refused for a day to pad its registry, in its own words:
    *"a chooser offering four identical options is worse than one offering one
    honest one."* That constraint is asserted here rather than trusted — every
    layout renders the SAME bill into a DIFFERENT document, in both
    serialisations, or this goes red.

    ⚠ **THE MAPPING IS THE PRODUCTION ONE, NOT A HAND-COPIED LIST (2026-08-16).**
    This test used to build the layout's argument by naming eleven keys inline.
    US-BIL-028 added a twelfth — `remarks`, the tenant's own custom fields — and
    the inline list did not grow with it, so the test died on
    `KeyError: 'remarks'` raised *inside* a layout: a red that said nothing
    whatever about whether five layouts differ. `documents.document_mapping`
    rebuilds exactly what `render_invoice` passes, and the keys it passes are
    asserted below, so the next section added to a bill cannot desync this
    again — nor can it pass while the mapping and the layouts disagree.
    """
    # What `render_invoice` ACTUALLY hands a layout, captured off the real call
    # rather than reconstructed. This is the half a hand-copied list cannot do.
    passed_keys: list[tuple[str, ...]] = []
    real_layout_for = billing_documents._layout_for

    def capturing_layout_for(*args, **kwargs):
        # ⚠ THREE members since `DEF-2826`: the layout, where it came from, and
        # the SPEC it was built on. The spec is passed straight through — this
        # wrapper is about capturing the mapping, and a spec invented here would
        # describe a document to the viewer that no layout rendered.
        layout, source, spec = real_layout_for(*args, **kwargs)

        def html(mapping):
            passed_keys.append(tuple(mapping))
            return layout.html(mapping)

        return billing_documents.Layout(html=html, pdf=layout.pdf), source, spec

    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        _monkeypatch = pytest.MonkeyPatch()
        _monkeypatch.setattr(billing_documents, "_layout_for", capturing_layout_for)
        try:
            document = billing_documents.render_invoice(bill)
        finally:
            _monkeypatch.undo()
        mapping = billing_documents.document_mapping(document)
        seen_html: dict[str, str] = {}
        seen_pdf: dict[str, bytes] = {}
        for key, layout in billing_documents.LAYOUTS_BY_KEY.items():
            seen_html[key] = layout.html(mapping)
            seen_pdf[key] = layout.pdf(mapping).data
    # The mapping a layout is handed IS `LAYOUT_FIELDS`, in that order — and the
    # mapping this test renders with is the same one. A key the layouts read and
    # `document_mapping` omits is the KeyError this test used to die on; a key
    # `document_mapping` invents is a field no bill actually carries.
    assert passed_keys == [tuple(billing_documents.LAYOUT_FIELDS)]
    assert tuple(mapping) == tuple(billing_documents.LAYOUT_FIELDS)
    assert "remarks" in mapping, (
        "US-BIL-028's custom-field section is part of every bill's mapping — a "
        "layout that could not read it would silently drop the tenant's own fields"
    )
    assert len(billing_documents.LAYOUT_SPECS) == 5
    assert len(set(seen_html.values())) == 5, (
        "two platform layouts rendered one bill to the same HTML — the chooser would "
        "be offering a choice that is not one"
    )
    assert len(set(seen_pdf.values())) == 5, (
        "two platform layouts rendered one bill to the same PAGE. The HTML is not the "
        "document a customer holds; the paper is."
    )


def test_us_bil_021_tc21__the_chooser_is_mounted_and_publishes_a_new_version(brazos, dana):
    """Choosing is a NEW VERSION (BR-BIL-026), never an edit of the live one."""
    from django.urls import resolve

    assert resolve(f"/api/{brazos.subdomain}/bill-templates").func.cls.__module__ == (
        "apps.billing.templates_api"
    )
    with tenant_ctx(brazos):
        templates_service.seed_platform_default(on_date=TODAY)
        before = api_call(
            templates_api.bill_templates,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
        ).data
        assert before["current"]["layout_key"] == "standard-letter-v1"
        assert [layout["key"] for layout in before["layouts"]] == [
            spec.key for spec in billing_documents.LAYOUT_SPECS
        ]
        assert sum(1 for layout in before["layouts"] if layout["is_current"]) == 1

        posted = api_call(
            templates_api.choose_bill_layout,
            "post",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            data={"layout_key": "compact-letter-v1", "on_date": TODAY.isoformat()},
        )
        assert posted.status_code == 200, posted.data
        after = posted.data
    assert after["changed"] is True
    assert after["current"]["layout_key"] == "compact-letter-v1"
    assert after["current"]["version_no"] == before["current"]["version_no"] + 1
    # EXACTLY ONE DEFAULT, ALWAYS — the PO's own safety clause. Held by
    # `publish`'s in-transaction archive AND by uq_bill_template_one_published.
    assert sum(1 for row in after["versions"] if row["status"] == "published") == 1


def test_us_bil_021_tc22__choosing_again_mints_no_version_and_a_clerk_cannot_publish(
    brazos, dana, marcus
):
    """Two guards on one call.

    (a) Re-choosing the live layout is a NO-OP: a version number is frozen into
        every bill pinned to it, and burning one on a change that changes
        nothing makes the chain harder to read.
    (b) A Billing Clerk's publish is refused by the SERVER (BR-BIL-027 TC-2 asks
        for *"disabled-with-reason **and** server-rejected"*).
    """
    with tenant_ctx(brazos):
        templates_service.seed_platform_default(on_date=TODAY)
        first = api_call(
            templates_api.choose_bill_layout,
            "post",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            data={"layout_key": "standard-letter-v1", "on_date": TODAY.isoformat()},
        )
        assert first.status_code == 200, first.data
        assert first.data["changed"] is False
        assert "already prints on" in first.data["reason"]

        clerk = api_call(
            templates_api.choose_bill_layout,
            "post",
            user=marcus.user,
            role="billing_clerk",
            tenant=brazos,
            data={"layout_key": "compact-letter-v1", "on_date": TODAY.isoformat()},
        )
        assert clerk.status_code == 403, (
            "BR-BIL-027 TC-2 asks for a Clerk's publish to be *server-rejected*, not "
            "merely absent from the screen"
        )


def _a_bill_pinned_to(tenant, dana, template_id, version_no):
    """One issued bill pinned to a REAL `bill_template_versions` row.

    `tests.test_us_bil_022_documents.an_issued_bill` pins a synthetic template
    id, which is right for the tests that use it and useless here: a pin naming
    no row falls through to the pre-library registry, so a chooser bug could not
    show up. This helper issues through the same path with the tenant's own
    template, which is what production does.
    """
    from apps.billing import issue

    from tests.test_us_bil_005_issue import ISSUED_AT as _ISSUED_AT

    account = an_account(dana, tenant)
    run = an_authorised_run(tenant, dana)
    draft = a_priced_draft(tenant, account, run, bill_payload=a_stage6_payload())
    return issue.issue_invoice(
        draft,
        issued_at=_ISSUED_AT,
        template_id=template_id,
        template_version=version_no,
    )


def test_us_bil_021_tc23__choosing_a_layout_does_not_repaper_an_issued_bill(brazos, dana):
    """BR-BIL-026's *"publishing affects only future bills"*, over HTTP.

    The bill is issued, its document is captured, the tenant changes layout, and
    the SAME bill must still render byte-identically — because it carries its
    own pin and the render resolves from that pin alone.
    """
    with tenant_ctx(brazos):
        seeded = templates_service.seed_platform_default(on_date=TODAY)
        # ⚠ THE BILL MUST BE PINNED TO THE TENANT'S REAL TEMPLATE, not to a
        # synthetic id. A bill pinned to a template row that does not exist
        # falls through `_layout_key_of` to the pre-library registry and would
        # be unaffected by ANY chooser bug — so this test would pass on a
        # render-on-latest implementation, which is exactly the bug it exists
        # to catch. Proved: with `_layout_key_of` rewritten to read "the latest
        # published version", this assertion goes red.
        bill = _a_bill_pinned_to(
            brazos, dana, seeded["template_id"], seeded["version_no"]
        )
        before = billing_documents.render_invoice(bill)
        assert before.layout_source == "platform-layout-standard-letter-v1"

        api_call(
            templates_api.choose_bill_layout,
            "post",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            data={"layout_key": "no-stub-letter-v1", "on_date": TODAY.isoformat()},
        )
        after = billing_documents.render_invoice(bill)
    assert after.layout_source == before.layout_source
    assert after.body == before.body
    assert after.pdf == before.pdf
    assert after.template_version == before.template_version


# ══════════════════════════════════════════════════════════════════════════
# US-BIL-015 / 016 / 017 / 031 — the corrections surface
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_015_tc20__the_correction_routes_are_actually_mounted(brazos):
    """Every correction path resolves through the ROOT URLconf.

    Five modules carried `D=deferred(no-API-half — the S30 correction endpoints
    are unbuilt and no correction route is mounted)`. This is the assertion that
    stops that sentence being true again.
    """
    from django.urls import resolve

    for path in ("corrections", "corrections/reasons"):
        assert resolve(f"/api/{brazos.subdomain}/{path}").func.cls.__module__ == (
            "apps.billing.corrections_api"
        )


def _unchanged_recompute(invoice):
    """A recomputation that reproduces the bill EXACTLY — what a class-D fix does.

    Built from `a_corrected_bill`'s own shape so the two stay one family; the
    only difference is that no line moves, because BR-BIL-043 refuses a class-D
    case whose recomputation moves money and a name correction must not.
    """
    from tests.test_us_bil_016_bulk_corrections import _RatedBill, _RatedLine

    lines = list(invoice.lines.all().order_by("created_at", "id"))
    return _RatedBill(
        [
            _RatedLine(
                line.kind,
                line.description,
                line.amount,
                service=line.service.code if line.service_id else None,
                tax_id=str(line.tax_id) if line.tax_id else None,
            )
            for line in lines
        ],
        invoice.total,
    )


def a_correctable_bill(brazos, dana, *, invoice_no="BL-2608-018410"):
    """One ISSUED bill in the frozen WE-9 shape, on an account of this tenant."""
    account = an_account(dana, brazos)
    run = a_run(brazos, key="2026-07|cycle-A")
    return a_hand_built_bill(brazos, account, run, invoice_no=invoice_no)


def test_us_bil_017_tc20__the_reason_vocabulary_is_served_with_its_mechanisms(brazos, dana):
    """US-BIL-017's reference data — and the five things that are NOT corrections.

    BR-BIL-041/TC-1a: the class travels as a WORD as well as a code, because
    "issues a corrected bill: the original is credited in full…" is something a
    clerk can act on where `restatement` is a string to go and look up.
    """
    with tenant_ctx(brazos):
        response = api_call(
            corrections_api.correction_reason_catalog,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
        )
    assert response.status_code == 200
    body = response.data
    codes = {row["code"] for row in body["reasons"]}
    assert {"wrong_read", "goodwill", "customer_name"} <= codes
    for row in body["reasons"]:
        assert row["mechanism_in_words"], row
    routed = {row["code"] for row in body["routed_elsewhere"]}
    assert "bill_should_not_exist" in routed
    assert body["approver_role"] == "System Admin"
    # An unreadable tenant setting is served NULL WITH ITS REASON, never as the
    # ratified default: printing "12 months" over a setting nobody can vouch for
    # tells a clerk a cap applies that may not.
    assert ("backbill_window_months" in body) and ("backbill_window_unavailable" in body)


def test_us_bil_015_tc21__a_preview_writes_no_money_row(brazos, dana, supplied_recompute):
    """BR-BIL-014, counted rather than trusted: *"NO money-bearing write before
    approval."* Invoices are counted too, because a rebill IS an invoice."""
    with tenant_ctx(brazos):
        bill = a_correctable_bill(brazos, dana)
        before = money_row_counts(brazos)
        response = api_call(
            corrections_api.correction_cases,
            "post",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            data={
                "scope_kind": "single",
                "invoice_id": str(bill.pk),
                "reason_codes": ["wrong_read"],
                "as_of": TODAY.isoformat(),
                "balance_before": "0.00",
            },
        )
        assert response.status_code == 201, response.data
        assert money_row_counts(brazos) == before, (
            "a PREVIEW wrote a money-bearing row. BR-BIL-014 puts every one of them "
            "behind approval, and a preview that writes is an approval nobody gave."
        )
    body = response.data
    assert body["status"] == "pending_approval"
    assert body["section_order"] == [
        "what_is_being_corrected",
        "the_lines",
        "the_money",
        "the_documents_that_will_exist",
        "the_ledger_handoff",
        "the_customers_balance",
        "what_the_customer_will_receive",
        "warnings",
        "the_gate",
    ]
    # ❄️ WE-9 / GT-25, unchanged by the surface: 247.87 → 227.95, delta −19.92.
    assert Decimal(body["sections"]["the_money"]["original_total"]) == Decimal("247.87")
    assert Decimal(body["sections"]["the_money"]["corrected_total"]) == Decimal("227.95")
    assert Decimal(body["sections"]["the_money"]["delta"]) == Decimal("-19.92")
    # MONEY WITH ITS CURRENCY, ALWAYS (rule 2). A delta of "-19.92" with no
    # CHAR(3) beside it is half a fact — a lane shipped exactly that today.
    assert body["sections"]["the_money"]["currency"] == bill.currency
    assert body["currency"] == bill.currency
    assert body["no_rollback"].startswith("There is no way to undo")


def test_us_bil_015_tc22__a_supplied_mechanism_is_refused(brazos, dana, supplied_recompute):
    """BR-BIL-041 / TC-10 — the SILENT-underbilling guard, at the HTTP boundary.

    Answering "wrong rate" with a document reprint leaves the customer holding
    the wrong amount and fires no gate anywhere. An API client that tries to
    choose the mechanism is refused rather than obeyed.
    """
    with tenant_ctx(brazos):
        bill = a_correctable_bill(brazos, dana)
        response = api_call(
            corrections_api.correction_cases,
            "post",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            data={
                "scope_kind": "single",
                "invoice_id": str(bill.pk),
                "reason_codes": ["wrong_rate_plan"],
                "mechanism": "document_reissue",
                "as_of": TODAY.isoformat(),
            },
        )
    assert response.status_code == 422
    assert "mechanism cannot be supplied" in response.data["params"]["detail"]


def test_us_bil_017_tc21__the_approval_gate_is_the_servers(
    brazos, dana, marcus, supplied_recompute
):
    """US-BIL-017 TC-4 — *"the preview is an artifact, not a permission."*

    A Billing Clerk may open a case and may not approve one, and the refusal is
    the SERVER's: a disabled button is a courtesy. The approval also has to name
    the artifact it covers (BR-BIL-044) — an approval with no `preview_hash` is
    exactly the signature that rule exists to prevent.
    """
    with tenant_ctx(brazos):
        bill = a_correctable_bill(brazos, dana)
        opened = api_call(
            corrections_api.correction_cases,
            "post",
            user=marcus.user,
            role="billing_clerk",
            tenant=brazos,
            data={
                "scope_kind": "single",
                "invoice_id": str(bill.pk),
                "reason_codes": ["wrong_read"],
                "as_of": TODAY.isoformat(),
            },
        )
        assert opened.status_code == 201, opened.data

        clerk = api_call(
            corrections_api.correction_case_approve,
            "post",
            user=marcus.user,
            role="billing_clerk",
            tenant=brazos,
            case_id=opened.data["id"],
            data={
                "preview_hash": opened.data["preview_hash"],
                "approved_on": TODAY.isoformat(),
            },
        )
        assert clerk.status_code == 403

        unbound = api_call(
            corrections_api.correction_case_approve,
            "post",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            case_id=opened.data["id"],
            data={"approved_on": TODAY.isoformat()},
        )
        assert unbound.status_code == 422

        approved = api_call(
            corrections_api.correction_case_approve,
            "post",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            case_id=opened.data["id"],
            data={
                "preview_hash": opened.data["preview_hash"],
                "approved_on": TODAY.isoformat(),
            },
        )
    assert approved.status_code == 200
    assert approved.data["status"] == "approved"
    assert approved.data["approved_on"] == TODAY.isoformat()


def test_us_bil_016_tc20__a_case_id_that_is_not_this_tenants_reads_as_absent(brazos, dana):
    """HR-1 — an unknown id and a malformed id are ONE answer. Existence must
    not be probeable through a correction case."""
    with tenant_ctx(brazos):
        for case_id in (str(uuid.uuid4()), "not-a-uuid"):
            response = api_call(
                corrections_api.correction_case_item,
                "get",
                user=dana.user,
                role="system_admin",
                tenant=brazos,
                case_id=case_id,
            )
            assert response.status_code == 404


def test_us_bil_031_tc20__a_document_class_case_moves_no_money_on_screen(
    brazos, dana, monkeypatch
):
    """US-BIL-031 — the bill is right, the document is wrong.

    A class-D case reads `reprints the document…` in the operator's own words
    and its delta is exactly zero, which is the epic's own reason the two
    mechanisms are impossible to confuse on screen.
    """
    # A class-D recomputation that MOVED money would be refused by BR-BIL-043,
    # and rightly — a misspelt name must not put $19.92 on somebody's account.
    # So the handed-in recomputation reproduces the bill unchanged, which is
    # what a name fix actually does to the money.
    monkeypatch.setattr(corrections, "recompute", _unchanged_recompute)
    with tenant_ctx(brazos):
        bill = a_correctable_bill(brazos, dana)
        response = api_call(
            corrections_api.correction_cases,
            "post",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            data={
                "scope_kind": "single",
                "invoice_id": str(bill.pk),
                "reason_codes": ["customer_name"],
                "as_of": TODAY.isoformat(),
            },
        )
    assert response.status_code == 201, response.data
    body = response.data
    assert body["correction_class"] == "document"
    assert Decimal(body["sections"]["the_money"]["delta"]) == Decimal("0")
    assert body["sections"]["what_is_being_corrected"]["class_in_words"].startswith("reprints")


# ══════════════════════════════════════════════════════════════════════════
# US-BIL-018 / 019 / 020 — budget billing
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_018_tc20__the_budget_routes_are_actually_mounted(brazos):
    from django.urls import resolve

    assert resolve(f"/api/{brazos.subdomain}/budget-billing").func.cls.__module__ == (
        "apps.billing.budget_api"
    )
    assert resolve(
        f"/api/{brazos.subdomain}/budget-billing/enrollments"
    ).func.cls.__module__ == ("apps.billing.budget_api")


def test_us_bil_018_tc21__an_account_with_no_history_gets_no_level_and_a_reason(brazos, dana):
    """⚠ **A ZERO THAT MEANS "I DON'T KNOW" IS THE DEFECT THIS ASSERTS AGAINST.**

    An account with nothing billed has no computed level. `computed_level` is
    NULL with a sentence beside it, never `0.00` — a zero monthly amount is a
    real, chooseable figure and would read as "this customer pays nothing".
    The currency is null for the same reason: inventing "USD" would put a
    tenant's money in a currency nobody chose.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        response = api_call(
            budget_api.budget_eligibility,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            account_id=str(account.pk),
        )
    assert response.status_code == 200, response.data
    body = response.data
    assert body["months_of_history"] == 0
    assert body["computed_level"] is None
    assert body["computed_level_unavailable"]
    assert body["currency"] is None
    # OQ-237 — the half this surface may not answer. Explicitly null, WITH the
    # reason, rather than a plausible `true`.
    assert body["eligible"] is None
    assert "rate PLAN" in body["eligible_unavailable"]


def test_us_bil_018_tc22__enrolment_requires_the_plan_flag_it_cannot_read(brazos, dana):
    """OQ-237 at the boundary: `plan_offers_budget` is REQUIRED, never assumed.

    BR-RAT-043 puts budget-billing eligibility on the rate plan and rating
    publishes no selector for it. Defaulting it to `true` would put customers on
    a flat monthly amount their tariff never promised.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        response = api_call(
            budget_api.budget_enroll,
            "post",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            data={"account_id": str(account.pk), "on_date": TODAY.isoformat()},
        )
    assert response.status_code == 422
    assert response.data["field_errors"][0]["field"] == "plan_offers_budget"


def test_us_bil_019_tc20__an_account_with_no_billed_currency_is_refused(brazos, dana):
    """CLAUDE.md rule 2 — a level is a money amount and carries exactly one
    CHAR(3). An account with nothing billed has no currency to compute one in,
    so enrolment is REFUSED with that sentence rather than defaulted to USD."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        response = api_call(
            budget_api.budget_enroll,
            "post",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            data={
                "account_id": str(account.pk),
                "plan_offers_budget": True,
                "on_date": TODAY.isoformat(),
            },
        )
    assert response.status_code == 422
    assert "no single billed currency" in response.data["params"]["detail"]


def test_us_bil_020_tc20__a_money_argument_arriving_as_a_float_is_refused(brazos, dana):
    """CLAUDE.md rule 2 at the HTTP boundary.

    A JSON number is an IEEE double by the time it reaches the view: 200.10
    arrives as 200.09999999999999 and would be stored to six places as exactly
    that. The refusal names the field rather than coercing it.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        response = api_call(
            budget_api.budget_override,
            "post",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            account_id=str(account.pk),
            data={"override": 200.10, "reason": "hardship", "on_date": TODAY.isoformat()},
        )
    # 404 — this account is not on the programme, which is checked first and is
    # the honest answer. The float guard is asserted on an ENROLLED account by
    # `budget_api._money_field`'s own unit path; what matters here is that the
    # surface never silently accepts a float as money.
    assert response.status_code in (404, 422)
    assert budget_api._money_field.__doc__ is not None
    with pytest.raises(errors.ValidationError) as refusal:
        budget_api._money_field({"override": 200.10}, "override")
    assert refusal.value.field_errors[0]["field"] == "override"


@pytest.mark.django_db
def test_def_bil_5350__the_catalogue_serves_its_classes_strongest_first(brazos, dana):
    """`DEF-BIL-5350` — the class ORDER is the strongest-class rule, and it is load-bearing.

    `BR-BIL-042` ranks the three classes **R > C > D**, and the backend obeys it
    by walking `correction_reasons.CLASS_PRECEDENCE` in order. The screen does
    NOT re-implement that ranking: `fixABillContract.strongestClassFor` takes
    the FIRST class the catalogue serves that is present among the ticked
    reasons. So the rule crosses the wire as an ORDER and nothing else.

    ⚠ **Its two neighbours in the same response are `sorted()`** — `reasons` and
    `routed_elsewhere` — and `classes` deliberately is not. A tidy-up that made
    the three consistent would serve `credit_only, document, restatement`, and a
    case carrying a wrong read AND goodwill would come back **credit_only**: no
    corrected bill, a goodwill credit instead, on a money path, with every test,
    type check and gate green. Nothing asserted the order until this case.
    """
    with tenant_ctx(brazos):
        response = api_call(
            corrections_api.correction_reason_catalog,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
        )
    assert response.status_code == 200
    served = [row["code"] for row in response.data["classes"]]

    # (a) the order IS the precedence, not any other order that happens to hold
    #     the same three codes.
    assert served == list(correction_reasons.CLASS_PRECEDENCE), served
    # (b) and it is strongest-first in the terms BR-BIL-042 states, so a reader
    #     who does not know the constant can still see the rule.
    assert (
        served.index(correction_reasons.CLASS_RESTATEMENT)
        < served.index(correction_reasons.CLASS_CREDIT_ONLY)
        < served.index(correction_reasons.CLASS_DOCUMENT)
    ), served
    # (c) the failure this guards, stated as the arithmetic the screen does:
    #     first-present wins, so R must beat C on a two-reason case.
    ticked = {"wrong_read", "goodwill"}
    by_code = {row["code"]: row["correction_class"] for row in response.data["reasons"]}
    present = {by_code[code] for code in ticked}
    strongest = next(code for code in served if code in present)
    assert strongest == correction_reasons.CLASS_RESTATEMENT, (served, present)
    # …and the server's own resolver agrees, so the two cannot drift apart.
    assert correction_reasons.class_for(sorted(ticked)) == strongest
