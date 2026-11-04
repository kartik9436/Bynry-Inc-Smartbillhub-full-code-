# ── Trace ──────────────────────────────────────────────
# Change:   CR-049 task 3 — "A reprint and a regulator request serve the stored
#           copy and never re-render", marked in the CR itself as *"The
#           behaviour the PO actually asked for"*.
# Rules:    BR-NOT-027 (a sent legal document is frozen AS THE DOCUMENT, and a
#           reprint serves THAT — PO 2026-08-30) · BR-NOT-025 / BR-BIL-026 (the
#           pin is PROVENANCE, not the rendering input) · BR-TEN-003 / HR-1
#           (existence must not leak) · CLAUDE.md rule 1 (tenant scoping) ·
#           rule 7 (audit) · hard-won law 2 (built is not wired) · law 7 (prove
#           a guard RED first)
# ───────────────────────────────────────────────────────
"""The route that decides whether any of `CR-049` is worth anything.

**WHY THIS FILE EXISTS, in the previous lane's own closing sentence:** *"no
endpoint serves a frozen document yet, so a screen could still re-render one and
nothing I wrote would notice. The guarantee is worth only what the route
eventually does with it."* Tasks 1, 2, 5 and 7 built a write-once store, made the
dispatcher freeze into it before every hand-off, and proved that editing a rights
clause cannot change a served notice **at the storage layer**. Nothing served it.

⚠ **PROVED RED FIRST (hard-won law 7).** Every case here was run before
`apps/notifications/reprint_api.py` existed and before `config/urls.py` included
it. The verbatim failures are quoted in the case that owns them.

THE FOUR THINGS THIS FILE IS FOR
----------------------------------
  1. **The edit-then-reprint case, end to end through the ROUTE** — serve a
     notice, edit its wording, ask the route to show it again, and read the
     ORIGINAL out of the response. Task 5 proved this through the store; a store
     nothing calls is the defect, not the fix.
  2. **A cross-tenant read is byte-identical to a missing document.** Asserted as
     equal RESPONSE BODIES, not merely as two refusals — a 403 where a 404
     belongs is itself a disclosure that the document exists.
  3. **A tampered object refuses, loudly.** The bytes are corrupted underneath a
     stored row and the route must fail rather than serve them.
  4. **NO RE-RENDER PATH EXISTS.** Asserted STRUCTURALLY — the module must not
     import or reference the renderer at all — because "it does not call it
     today" is a property of today's code and this is a property of the module.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone as dt_timezone

import pytest

from apps.notifications import models
from apps.tenancy import document_storage, document_store
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_cr049_t2_dispatch_freeze import provider_connected  # noqa: F401 — shared fixture
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: Inside Brazos Bend's seeded 08:00–21:00 send window. Named, never read from a
#: clock (BR-TEN-043, and G6 greps for it).
SERVED_AT = datetime(2026, 8, 30, 15, 0, tzinfo=dt_timezone.utc)

#: The correction a System Admin makes AFTER the notice has gone out — the same
#: edit `test_cr049_t5_rights_clause_reprint.py` makes, driven through the route
#: here rather than through the store.
CORRECTED_DISPUTE_CLAUSE = (
    "Call us within 10 days of the date on this notice if you believe this bill is "
    "wrong. We will not disconnect while a dispute is open."
)

#: A token-free sentence from the platform's default dispute-rights clause — the
#: wording that WAS in force when the letter was served.
SERVED_DISPUTE_SENTENCE = (
    "If you believe the amount on this notice is wrong, contact us before the date "
    "shown above — not after it."
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


def _an_account(actor, tenant, account_no, service="electric"):
    from apps.customers import models as customer_models

    premises = make_premises(
        actor, address_line=f"{account_no} Ridge Rd", services_available=[service]
    )
    unit = make_unit(actor, premises["id"], label=account_no, services=[service])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=account_no,
    )


def _serve_a_48_hour_notice(actor, tenant, account_no="A-49301", service="electric"):
    """Generate the 48-hour certified notice and actually DISPATCH it.

    Nothing is faked: the tenant is provisioned through the real service, the
    notice resolves the seeded `disconnect_notice_48_hour` template, and the
    dispatcher runs its ordinary cycle — which, since `CR-049` task 2, freezes
    the artefact before the provider hand-off.
    """
    from decimal import Decimal

    from apps.notifications import dispatcher, notices, rights_footer

    account = _an_account(actor, tenant, account_no, service=service)
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
    served_wording = rights_footer.footer_text()
    dispatcher.dispatch_cycle(
        now=SERVED_AT, channels=(models.CHANNEL_PRINT,), actor=actor, job="test"
    )
    row.refresh_from_db()
    return row, served_wording


def _call(view, actor, tenant, role="system_admin", **kwargs):
    return api_call(view, "get", user=actor.user, role=role, tenant=tenant, **kwargs)


def _body(response):
    """A refusal body WITHOUT `trace_id`, for the indistinguishability comparison.

    ⚠ **`trace_id` IS THE ONE FIELD THAT MAY LEGITIMATELY DIFFER, and dropping it
    is not a weakening of this assertion.** It is a fresh correlation id minted
    per REQUEST for log tracing; it is derived from nothing about the document,
    it differs between two calls for the SAME missing id, and it therefore
    carries no signal about whether the thing asked for exists. Everything that
    could carry such a signal — `code`, `message_key`, `params`, `field_errors`,
    `br_ref` — is compared, and must be equal.

    This was found by the assertion itself: the first run compared whole bodies
    and reported `trace_id` as the ONLY difference, which is the evidence that
    the guarantee holds rather than a reason to relax the check.
    """
    return {key: value for key, value in response.data.items() if key != "trace_id"}


# ══════════════════════════════════════════════════════════════════════════
# 0 · IS IT WIRED AT ALL? — hard-won law 2 at the routing layer
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t3__the_reprint_routes_are_actually_mounted(brazos):
    """A module exporting `urlpatterns` is not an endpoint until `config/urls.py`
    includes it. Resolved through the REAL root URLconf.

    ⚠ RED FIRST, before the module and the include existed:

        E   ModuleNotFoundError: No module named 'apps.notifications.reprint_api'
    """
    from django.urls import resolve

    from apps.notifications import reprint_api

    message_id = uuid.uuid4()
    document_id = uuid.uuid4()
    expected = {
        f"/api/brazosbend/outbound/{message_id}/document": reprint_api.outbound_document,
        f"/api/brazosbend/documents/{document_id}": reprint_api.stored_document,
        "/api/brazosbend/documents/register": reprint_api.document_register,
    }
    for path, view in expected.items():
        assert resolve(path).func is view, f"{path} does not resolve to its view"


def test_cr049_t3__the_reprint_routes_are_reachable_through_the_whole_stack(brazos):
    """`resolve()` proves the URLconf knows the path; it does not prove a request
    can GET there. **401 = the route exists and asked for a sign-in; 404 = there
    is no route**, which is what all three answered before this lane.
    """
    from django.test import Client

    probes = (
        f"/api/{brazos.subdomain}/outbound/{uuid.uuid4()}/document",
        f"/api/{brazos.subdomain}/documents/{uuid.uuid4()}",
        f"/api/{brazos.subdomain}/documents/register",
    )
    for path in probes:
        response = Client().get(path)
        assert response.status_code == 401, (
            f"GET {path} answered {response.status_code}: a 404 here means the route is "
            "still not reachable, whatever the URLconf says"
        )
        assert response.json()["code"] == errors.AUTH_UNAUTHENTICATED


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE CASE THAT DECIDES THIS TASK — end to end THROUGH THE ROUTE
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t3__serve_edit_reprint__the_route_returns_the_ORIGINAL(
    brazos, dana, print_vendor, docs_dir
):
    """**Serve a notice, edit its wording, ask the route to show it again — the
    response carries the ORIGINAL.**

    `test_cr049_t5` proved this through `document_store.fetch`. This proves it
    through the thing a screen actually calls, which is the only place the
    guarantee can be broken now.

    ⚠ RED FIRST, before `reprint_api` existed:

        E   ModuleNotFoundError: No module named 'apps.notifications.reprint_api'
    """
    from apps.notifications import reprint_api, rights_footer

    with tenant_ctx(brazos):
        row, served_wording = _serve_a_48_hour_notice(dana, brazos)
        assert row.status == models.STATUS_SENT
        assert SERVED_DISPUTE_SENTENCE in served_wording

        # THE EDIT — audited, legitimate, forward-looking.
        rights_footer.update_clauses(actor=dana, dispute_rights={"text": CORRECTED_DISPUTE_CLAUSE})
        assert CORRECTED_DISPUTE_CLAUSE in rights_footer.footer_text()

        # THE REPRINT, over the route.
        response = _call(
            reprint_api.outbound_document, dana, brazos, role="billing_clerk", message_id=str(row.pk)
        )

    assert response.status_code == 200, response.data
    body = response.data
    assert body["provenance"] == "original", body
    assert body["is_original"] is True
    assert body["unavailable_reason"] is None
    assert body["message_key"] == "notifications.frozenDocument.original"

    # THE WHOLE POINT: the letter in the response is the one that was served.
    served = body["document"]["text"]
    assert CORRECTED_DISPUTE_CLAUSE not in served, (
        "the reprint route served TODAY's rights clause — this is DEF-2504 reopened "
        "one layer up, and it is exactly what BR-NOT-027 forbids"
    )
    assert SERVED_DISPUTE_SENTENCE in served


def test_cr049_t3__a_queued_row_is_served_as_re_rendered_not_as_the_original(
    brazos, dana, docs_dir
):
    """Task 7's honest half, carried all the way to the response.

    A row that never dispatched has no sealed copy, and the route must SAY so
    rather than producing a fresh render dressed as the letter. The person
    looking at the screen has to be able to tell the two apart.
    """
    from decimal import Decimal

    from apps.notifications import notices, reprint_api

    with tenant_ctx(brazos):
        account = _an_account(dana, brazos, "A-49302")
        notices.generate_disconnect_notice(
            account_id=account.pk,
            tier=notices.TIER_FINAL_48_HOUR,
            balance=Decimal("100.000000"),
            cut_date=date(2026, 9, 3),
            reconnect_fee=Decimal("45.000000"),
            state_puc_ref="TX PUC Substantive Rule 25.29",
            on_date=date(2026, 8, 30),
            actor=dana,
        )
        row = models.OutboundMessage.objects.get(
            source_type="notice", source_id=account.pk, channel=models.CHANNEL_PRINT
        )
        response = _call(
            reprint_api.outbound_document, dana, brazos, role="billing_clerk", message_id=str(row.pk)
        )

    body = response.data
    assert body["provenance"] == "re_rendered_from_data_not_the_original"
    assert body["is_original"] is False
    assert body["unavailable_reason"] == "document_not_stored"
    assert body["message_key"] == "notifications.frozenDocument.reRendered"
    assert body["document"] is None, (
        "a re-rendered answer must carry NO document — a screen that reads "
        "`document` without branching would print a reconstruction as the original"
    )


# ══════════════════════════════════════════════════════════════════════════
# 2 · A CROSS-TENANT READ IS INDISTINGUISHABLE FROM A MISSING DOCUMENT
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t3__another_tenants_document_answers_EXACTLY_as_a_missing_one(
    brazos, lonestar, dana, erin, print_vendor, docs_dir
):
    """⚠ **THE BODIES MUST BE EQUAL, not merely both refusals.**

    A 403 where a 404 belongs tells the caller the document exists, which is the
    disclosure `CR-049` step 5d decision 4 and HR-1 both forbid. So this asserts
    the two response bodies are EQUAL, between a real document belonging to
    somebody else and an id that never existed anywhere.
    """
    from apps.notifications import reprint_api

    with tenant_ctx(brazos):
        row, _ = _serve_a_48_hour_notice(dana, brazos, account_no="A-49303")
        lookup = document_store.for_source(
            source_type="outbound_message", source_id=row.pk, channel=row.channel
        )
        assert lookup.found, "the fixture did not freeze anything to read across a tenant"
        brazos_document_id = str(lookup.document.id)
        brazos_message_id = str(row.pk)

    # Sam, in Silver Creek, asks for Brazos Bend's document — and for one that
    # has never existed in any tenant.
    with tenant_ctx(lonestar):
        real_but_foreign = _call(
            reprint_api.stored_document, erin, lonestar, document_id=brazos_document_id
        )
        never_existed = _call(
            reprint_api.stored_document, erin, lonestar, document_id=str(uuid.uuid4())
        )

    assert real_but_foreign.status_code == never_existed.status_code == 404
    assert _body(real_but_foreign) == _body(never_existed), (
        "another tenant's document answered differently from a document that does not "
        "exist — the difference IS the disclosure"
    )

    # The same, one layer up: the message id itself must not be probeable.
    with tenant_ctx(lonestar):
        foreign_message = _call(
            reprint_api.outbound_document,
            erin,
            lonestar,
            role="billing_clerk",
            message_id=brazos_message_id,
        )
        unknown_message = _call(
            reprint_api.outbound_document,
            erin,
            lonestar,
            role="billing_clerk",
            message_id=str(uuid.uuid4()),
        )
    assert foreign_message.status_code == unknown_message.status_code == 404
    assert _body(foreign_message) == _body(unknown_message)


# ══════════════════════════════════════════════════════════════════════════
# 3 · A TAMPERED OBJECT REFUSES — LOUDLY, never a warning
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t3__corrupting_the_stored_bytes_makes_the_route_REFUSE(
    brazos, dana, print_vendor, docs_dir
):
    """A silent byte change is precisely what this store exists to prevent
    (`CR-049` step 5d(e) decision 7). The route must FAIL rather than serve.

    The bytes are corrupted through the filesystem backend, underneath a row that
    still says the old hash — which is the shape of the real hazard: a document
    quietly replaced years after it was written.
    """
    from apps.notifications import reprint_api

    with tenant_ctx(brazos):
        row, _ = _serve_a_48_hour_notice(dana, brazos, account_no="A-49304")
        lookup = document_store.for_source(
            source_type="outbound_message", source_id=row.pk, channel=row.channel
        )
        assert lookup.found
        # It reads fine BEFORE the tamper — otherwise this case could pass for
        # the wrong reason.
        good = _call(
            reprint_api.stored_document, dana, brazos, document_id=str(lookup.document.id)
        )
        assert good.status_code == 200, good.data

        # ⚠ THE PAYLOAD, NAMED — NOT `next(rglob(...))`, WHICH IS WHAT MADE THIS
        # CASE FLAKY (found by the merge lane, 2026-08-30: RED on its stack and
        # GREEN here, from the same commit). The filesystem backend writes TWO
        # files per document — the payload at `<key>` and a `.meta` sidecar
        # carrying the content type and digest — so taking the first file the
        # directory yields corrupts whichever one the operating system felt like
        # returning. When that was the sidecar the letter was intact, the route
        # correctly served it, and the assertion failed over CORRECT behaviour.
        # A check whose output cannot distinguish pass from fail is worse than no
        # check, because it is trusted (hard-won law 1).
        # `test_cr049_t3_tamper_diagnostic.py` pins both directions separately.
        payloads = [p for p in docs_dir.rglob("*") if p.is_file() and p.suffix != ".meta"]
        assert len(payloads) == 1, f"expected exactly one stored payload, found {payloads}"
        payloads[0].write_bytes(b"this is not the letter that was sent")

        tampered = _call(
            reprint_api.stored_document, dana, brazos, document_id=str(lookup.document.id)
        )

    assert tampered.status_code >= 400, (
        "the route served bytes whose hash does not match the record — a silent byte "
        "change is the one thing BR-NOT-027's store exists to catch"
    )
    assert tampered.data["code"] == errors.BIZ_STATE
    assert tampered.data["message_key"] == "notifications.frozenDocument.hashMismatch"
    assert "this is not the letter" not in str(tampered.data)


def test_cr049_t3__the_reprint_route_reports_a_tampered_document_rather_than_re_rendering(
    brazos, dana, print_vendor, docs_dir
):
    """⚠ THE SUBTLE HALF OF THE TAMPER CASE, and the one worth stating.

    A tampered document must NOT quietly degrade into
    `re_rendered_from_data_not_the_original`. That would look like the honest
    state while actually hiding a corrupted legal record behind a reassuring
    sentence — the row says a document was frozen, and it was; the bytes are
    wrong, and somebody has to be told that specific thing.
    """
    from apps.notifications import reprint_api

    with tenant_ctx(brazos):
        row, _ = _serve_a_48_hour_notice(dana, brazos, account_no="A-49305")
        # EVERY stored file, not the first one `rglob` happens to yield. This
        # backend writes a payload AND a `.meta` sidecar per document, so taking
        # one by directory order is a coin toss — the flaw that made the case
        # above flaky. Corrupting all of them is deterministic and includes the
        # payload by construction.
        corrupted = [p for p in docs_dir.rglob("*") if p.is_file()]
        assert corrupted, "nothing was frozen, so there is nothing to corrupt"
        for stored_file in corrupted:
            stored_file.write_bytes(b"tampered")
        response = _call(
            reprint_api.outbound_document, dana, brazos, role="billing_clerk", message_id=str(row.pk)
        )

    assert response.status_code >= 400, response.data
    assert response.data["message_key"] == "notifications.frozenDocument.hashMismatch"


# ══════════════════════════════════════════════════════════════════════════
# 4 · THERE IS NO RE-RENDER PATH — asserted STRUCTURALLY
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t3__the_reprint_module_cannot_reach_the_renderer_at_all():
    """⚠ **A PROPERTY OF THE MODULE, not of today's control flow.**

    "It does not call the renderer today" is true of code that imports it and
    happens not to reach the branch. `BR-NOT-027` needs the stronger statement:
    **there is no path through this module to a render**, so a lane adding a
    sensible-looking fallback (*"if nothing is stored, show them something"*)
    breaks a test rather than the rule.

    Read from the SOURCE, because an import-graph check that reads the module
    object cannot see a function-local import.
    """
    import ast
    import pathlib

    source = pathlib.Path(__file__).resolve().parents[1] / "apps/notifications/reprint_api.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            imported += [f"{base}.{alias.name}" for alias in node.names]

    forbidden = [name for name in imported if "rendering" in name or "template_preview" in name]
    assert not forbidden, (
        f"{source} imports {forbidden}. A reprint that can reach a renderer is one "
        "refactor from re-rendering a legal document, which is the whole of BR-NOT-027."
    )

    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "render_for_dispatch" not in called
    assert "render" not in called


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE REGULATOR REQUEST — a date range, from the DATABASE, never the bucket
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t3__the_regulator_register_lists_a_date_range_and_only_this_tenants(
    brazos, lonestar, dana, erin, print_vendor, docs_dir
):
    """*"a regulator asking to see the exact disconnection letter a customer was
    sent last July"* — `CR-048`'s E9 example, which is where this CR started.

    The register enumerates from the metadata table (`CR-049` step 5d: *"Listing
    is ALWAYS a database query and never a bucket listing"*) and answers only
    this tenant's rows.
    """
    from apps.notifications import reprint_api

    with tenant_ctx(brazos):
        _serve_a_48_hour_notice(dana, brazos, account_no="A-49306")
    with tenant_ctx(lonestar):
        _serve_a_48_hour_notice(erin, lonestar, account_no="L-49306", service="water")

    with tenant_ctx(brazos):
        inside = _call(
            reprint_api.document_register,
            dana,
            brazos,
            query={"from": "2026-08-01", "to": "2026-09-30"},
        )
        outside = _call(
            reprint_api.document_register,
            dana,
            brazos,
            query={"from": "2025-01-01", "to": "2025-12-31"},
        )

    assert inside.status_code == 200, inside.data
    names = [r["display_name"] for r in inside.data["results"]]
    assert any("A-49306" in n for n in names), names
    assert not any("L-49306" in n for n in names), (
        "the register returned another tenant's document — the enumeration is not "
        "tenant-scoped"
    )
    assert outside.data["results"] == [], "a range with no documents returned rows"


def test_cr049_t3__the_register_refuses_a_range_it_cannot_read(brazos, dana):
    """A malformed date is a 422 naming the field, never an empty list — an empty
    list would say *"this utility sent nothing in July"* about a question we did
    not understand (DEF-075's shape)."""
    from apps.notifications import reprint_api

    with tenant_ctx(brazos):
        response = _call(
            reprint_api.document_register, dana, brazos, query={"from": "last-july", "to": "now"}
        )
    assert response.status_code == 422
    assert response.data["code"] in (errors.VAL_FORMAT, errors.VAL_REQUIRED)


def test_cr049_t3__the_register_is_system_admin_only(brazos, dana):
    """Every document a utility ever sent, in one list. `CR-049` step 5f: *"the
    MOST SENSITIVE OPERATION IN THE PRODUCT — System Admin only, audited"*."""
    from apps.notifications import reprint_api

    with tenant_ctx(brazos):
        response = _call(
            reprint_api.document_register,
            dana,
            brazos,
            role="billing_clerk",
            query={"from": "2026-08-01", "to": "2026-09-30"},
        )
    assert response.status_code == 403


# ══════════════════════════════════════════════════════════════════════════
# 6 · DELIVERY — a four-hour pre-signed URL for print, the text for email/SMS
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t3__a_print_document_is_delivered_as_a_four_hour_link(
    brazos, dana, print_vendor, docs_dir
):
    """PO ruling 2026-08-30: *"dont expire it in minutes - exprise it in 3 or 4
    hours"*. The TTL is a setting, and the response states it rather than leaving
    a screen to hardcode a number that can be changed without a deploy."""
    from apps.notifications import reprint_api

    with tenant_ctx(brazos):
        row, _ = _serve_a_48_hour_notice(dana, brazos, account_no="A-49307")
        response = _call(
            reprint_api.outbound_document, dana, brazos, role="billing_clerk", message_id=str(row.pk)
        )

    document = response.data["document"]
    assert document["download_url"], "no temporary link was issued for a print document"
    assert document["url_expires_in_seconds"] == document_storage.url_ttl_seconds() == 4 * 60 * 60
    assert "storage_key" not in document, (
        "a storage key reached a caller — a caller that can name a key can name one it "
        "composed, which is the one thing CR-049 step 5d decision 4 forbids"
    )


def test_cr049_t3__the_response_never_carries_a_storage_key_on_any_route(
    brazos, dana, print_vendor, docs_dir
):
    """Decision 4, asserted over every route rather than trusted per handler."""
    from apps.notifications import reprint_api

    with tenant_ctx(brazos):
        row, _ = _serve_a_48_hour_notice(dana, brazos, account_no="A-49308")
        lookup = document_store.for_source(
            source_type="outbound_message", source_id=row.pk, channel=row.channel
        )
        bodies = [
            _call(
                reprint_api.outbound_document, dana, brazos, role="billing_clerk", message_id=str(row.pk)
            ).data,
            _call(
                reprint_api.stored_document, dana, brazos, document_id=str(lookup.document.id)
            ).data,
            _call(
                reprint_api.document_register,
                dana,
                brazos,
                query={"from": "2026-08-01", "to": "2026-09-30"},
            ).data,
        ]
    for body in bodies:
        assert "storage_key" not in str(body), body
