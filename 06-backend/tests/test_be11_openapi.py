# ── Trace ──────────────────────────────────────────────
# Component: BE-11 tests (OpenAPI publisher) — settings wiring, deterministic
#            export command, AND (from 2026-08-10, TC05) the committed-snapshot
#            diff itself. That last one used to say "runs in the gates/CI lane";
#            it did not run anywhere, so it runs here now. The `OpenAPI contract
#            diff` step in .github/workflows/ci-backend.yml also ran it —
#            ⚠ NOT ANY MORE — every workflow was disabled on 2026-09-04 (PO: Actions minutes exhausted); see .github/workflows/README.md. Run it by hand.
#            Baseline = A11 + 11b per A11 Addendum r2.
# ───────────────────────────────────────────────────────
"""BE-11 unit tests: drf-spectacular is wired, and `manage.py export_openapi`
emits deterministic JSON (same input ⇒ same bytes — the CI diff must only ever
show real contract drift)."""

import io
import json

from django.conf import settings
from django.core.management import call_command


def _export_to_string() -> str:
    out = io.StringIO()
    call_command("export_openapi", "--out", "-", stdout=out)
    return out.getvalue()


def test_be11_tc01_spectacular_wired_in_settings():
    assert "drf_spectacular" in settings.INSTALLED_APPS
    assert settings.REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] == "drf_spectacular.openapi.AutoSchema"
    # The CI-diff clause names its baseline where every reader will look.
    assert "A11" in settings.SPECTACULAR_SETTINGS["DESCRIPTION"]


def test_be11_tc02_export_emits_valid_openapi_document():
    schema = json.loads(_export_to_string())
    assert schema["info"]["title"] == "SMART360 Next API"
    assert schema["openapi"].startswith("3.")
    # Endpoint stories are landing (identity first, 2026-08-09): the schema
    # now carries the ratified identity paths — the committed-snapshot CI diff
    # is the follow-up flagged in the identity lane's build report.
    paths = schema.get("paths", {})
    # PO ruling 2026-08-10: tenant-scoped routes publish under /api/{tenant}/…
    assert "/api/{tenant}/auth/session" in paths
    assert "/api/{tenant}/users" in paths
    assert "/api/{tenant}/settings/security-policy" in paths


def test_be11_tc03_export_is_deterministic():
    assert _export_to_string() == _export_to_string()


#: Every operation the contract may honestly publish as needing NO credential.
#:
#: ⚠ **A ROUTE IS ADDED HERE BY NAME, DELIBERATELY, AND THE ASSERTION IS NEVER
#: WIDENED** — `apps/integrations/partner_api.py`'s own docstring instructs
#: exactly this of its sibling test, and `DEF-INT-4256` records what the one
#: departure from it cost. Each line says what makes that address public.
PUBLISHES_AS_NEEDING_NO_CREDENTIAL = [
    # ── onboarding: there is no tenant yet, so there can be no session ──────
    "get /api/public/pricing-plans",  # S1/S112 catalogue
    "get /api/public/subdomain-check",  # S110 slug availability
    "post /api/tenants",  # S114 provisioning
    # ── the utility's own content-security policy ───────────────────────────
    # A document is served before anybody signs in and the SPA does not reload
    # after, so a policy computed from a session would be computed once on the
    # login page with no hosts in it. It discloses the hosts the browser is
    # about to be told to fetch from and no credential, count, name or row —
    # `apps/integrations/page_policy.py` carries the reasoning in full.
    "get /api/{tenant}/integrations/page-policy",
    # ── capabilities and public assets (added 2026-10-11; this case was red
    # since `9c38ade5f` without either line) ─────────────────────────────────
    # The scheduled-delivery link a BI tool redeems: the SIGNED TOKEN is the
    # credential and names the tenant (`apps/reports/delivery_api.py`, one 404
    # for every no), as `applications/{token}` below is.
    "get /api/reports/delivery/{token}",
    # The utility's logo, drawn on the PUBLIC portal and on documents before
    # anybody signs in (`tenancy/api.py` `company_logo_file`): an image the
    # utility publishes, no row, name or count.
    "get /api/{tenant}/settings/company/logo/file",
    # ── the customer portal's GUEST edge (CR-068 wave A, 2026-09-03) ────────
    # Public BY RULE (BR-CWP-022 — behind the anonymous throttle, per address
    # and per tenant): a customer reads a bill, reports a fault or tracks a
    # request without an account. ⚠ **THIS LIST HELD ONLY `front` UNTIL
    # 2026-09-24 AND THE OTHER TWENTY-THREE WERE NEVER ADDED** — the comment
    # above it already said *"every route added there must appear here, by
    # name"*, and no wave did. That is why this assertion has been red since
    # the guest edge landed, and it is HALF of how `DEF-INT-6529` hid: a
    # sentence instructing a future lane is not a mechanism.
    "get /api/{tenant}/portal/public/applications/{token}",
    # ⚠ **THE APPLICANT'S FILES — four guest doors, each opened by the draft
    # TOKEN (the capability) and never by a session.** Three were added without
    # this list moving — `5ac17a0e9` (CR-158-BRC10, attach and remove) and
    # `89f8cd698` (DEF-CWP-9049, a reply from Track), both 2026-10-02 — so this
    # case was red from those commits; the fourth is `DEF-CWP-9166`, the
    # applicant VIEWING their own file, added in the commit that lists all four.
    "delete /api/{tenant}/portal/public/applications/{token}/documents/{document_id}",
    "get /api/{tenant}/portal/public/applications/{token}/documents/{document_id}/content",
    "post /api/{tenant}/portal/public/applications/{token}/documents",
    "post /api/{tenant}/portal/public/track/documents",
    "get /api/{tenant}/portal/public/front",
    "get /api/{tenant}/portal/public/help",
    "get /api/{tenant}/portal/public/help/{slug}",
    "get /api/{tenant}/portal/public/premises/availability",
    # CR-200-BRC10 S7 — address suggestions while typing (PO 1A): street,
    # town, state and ZIP only, behind the same two throttles.
    "get /api/{tenant}/portal/public/premises/suggestions",
    "get /api/{tenant}/portal/public/quick-services",
    "get /api/{tenant}/portal/public/service-centres",
    "get /api/{tenant}/portal/public/service-centres/{slug}",
    "get /api/{tenant}/portal/public/tips",
    "post /api/{tenant}/portal/public/applications/{token}/submit",
    "post /api/{tenant}/portal/public/bills/lookup",
    "post /api/{tenant}/portal/public/bills/{number}/pay",
    "post /api/{tenant}/portal/public/help/{slug}/feedback",
    "post /api/{tenant}/portal/public/reports",
    "post /api/{tenant}/portal/public/requests",
    "post /api/{tenant}/portal/public/track",
    "put /api/{tenant}/portal/public/applications/{token}",
    # ── the portal's own sign-in and enrolment ──────────────────────────────
    # A caller who could already authenticate would not be signing in, and a
    # stale staff cookie must not 401 a customer enrolling.
    "post /api/{tenant}/portal/auth/forgot-password",
    "post /api/{tenant}/portal/auth/reset-password",
    "post /api/{tenant}/portal/auth/sign-in",
    "post /api/{tenant}/portal/enrol/consequences",
    "post /api/{tenant}/portal/enrol/find-account",
    "post /api/{tenant}/portal/enrol/set-password",
    "post /api/{tenant}/portal/enrol/verify-code",
]

#: ⚠ **THESE TWO ARE NOT PUBLIC AND THE CONTRACT SAYS THEY ARE. THE NUMBER IS
#: BESIDE THEM ON PURPOSE (`DEF-INT-6540`).**
#:
#: Both prove a credential before they do anything: the kiosk door reads
#: whatever its manifest declares — a key in a header, HTTP Basic, or an HMAC
#: over the raw body — and the payment webhook verifies an HMAC-SHA256 over the
#: body against a secret only this deployment and that gateway hold. Neither
#: carries a DRF authenticator, so drf-spectacular emits `security: [{}]` for
#: them exactly as it did for the partner surface.
#:
#: **They are listed apart from the list above rather than inside it**, because
#: a credentialled door written into a constant named *needing no credential*
#: is the same lie `DEF-INT-6529` is about, one layer further in. The partner
#: surface's own fix does not reach them: a partner always presents
#: `Authorization: Bearer`, so one scheme describes all 23 of its operations,
#: while the kiosk door's credential is PER MANIFEST and the webhook's arrives
#: under either of two header spellings — one `partnerKey`-shaped scheme would
#: be a different inaccuracy rather than the truth. `DEF-INT-6540` owns them.
#:
#: **A declared blind spot with no number beside it is indistinguishable from
#: an empty one** (CLAUDE.md, hard-won law 7, fifth shape). This is the number.
CREDENTIALLED_BUT_PUBLISHED_AS_PUBLIC = [
    "post /api/{tenant}/integrations/inbound/{key}/{operation}",  # US-INT-044 kiosk
    # The same kiosk door answers GET for a manifest whose operation is a read
    # (`inbound_api.inbound_door`, `@api_view(["GET", "POST"])`) and proves the
    # same per-manifest credential first; added 2026-10-11 when the snapshot
    # was regenerated and this case was found red since `4710e3275`.
    "get /api/{tenant}/integrations/inbound/{key}/{operation}",
    "post /api/{tenant}/portal/webhooks/payments/{provider}",  # US-CWP-006 gateway
]


def test_be11_tc02_the_schema_declares_the_credentials_it_actually_wants():
    """ADDED 2026-08-10 with the platform-wide authentication default; the
    partner half is `DEF-INT-6529`, 2026-09-24.

    Before the default, most views inherited DRF's own authenticators and the
    published contract advertised `basicAuth` + a `cookieAuth` named
    `sessionid` — two schemes this product has never had. The default removes
    both, and an authenticator with no drf-spectacular extension would have
    published no security at all on 120 operations that require a session. The
    extension lives beside the class it describes (`apps/identity/auth.py`) so
    that loading the class registers it; this asserts that actually happened.

    ⚠⚠ **AND THE SAME MECHANISM PUBLISHED THE PARTNER API AS PUBLIC FOR
    EIGHTEEN DAYS — `DEF-INT-6529`.** drf-spectacular resolves a security
    scheme from a view's AUTHENTICATORS. Every partner view deliberately has
    none (`authentication_classes = []`, because a partner presents a KEY and
    never a session cookie), so the generator saw an empty authenticator list
    plus `AllowAny` — *exactly the shape a genuinely public route has* — and
    emitted `security: [{}]` on 23 operations. In OpenAPI that means **this
    endpoint needs no credentials**, and one of the 23 is
    `POST /api/partner/v1/make-payment/`, which takes money.

    **THE DOOR WAS NEVER OPEN AND THIS TEST NEVER SAID IT WAS.** `_admit`'s
    checks 1–8 refuse a caller with no key: measured on PostgreSQL 16 through
    the real router on 2026-09-24, all ten phase-2 addresses answer
    `404 {"error": "We cannot serve this request.", "code": "REFUSED"}` with
    cause `KEY_UNKNOWN` to a request carrying no `Authorization` header, and
    `tests/test_def_int_6529_partner_key_scheme.py` holds that proof. What was
    wrong was the SIGN on the door, and a partner's engineer — or a client
    generated from our contract — read the sign.

    WHAT WOULD MAKE THIS CHECK PASS WRONGLY — asked first, per law 7
    ------------------------------------------------------------------
    **1 · The scheme is named and never defined.** An operation may name
    `partnerKey` while `components.securitySchemes` does not define it. That
    is invalid OpenAPI, every generator treats it differently, and counting
    operations would not notice — so the definition is asserted, and so is the
    general invariant that EVERY name any operation references is defined.

    **2 · The list of partner operations is hand-written here.** A fourteenth
    partner door would then be undocumented and this file would stay green. So
    the expected set is DERIVED from `partner_urls.PARTNER_ROUTES` and from the
    views that opt out of the authenticator in `partner_api`, never typed.

    **3 · `sorted(public) == [...]` is satisfied by an EMPTY partner surface.**
    If every partner path vanished from the schema, the public list would be
    correct and this test would pass over a contract with no partner API in it
    at all. So the count of `partnerKey` operations is asserted to be exactly
    what the route table implies.

    ⚠ **THIS RUNS BEFORE `tc05`, AND THE ORDER IS THE OTHER HALF OF THE
    DEFECT.** `tc05` — the snapshot matches the code — was failing first, so in
    a `-x` run this case never completed and its failure was invisible for as
    long as the snapshot was stale. The two are independent in substance: this
    one exports the schema itself and never reads the snapshot. Under `-x` the
    file now surfaces *the contract is lying about a money endpoint* before *the
    snapshot needs regenerating*, which is the right way round. **Running this
    file WITHOUT `-x` is still what actually fixes it**, and that is a proposal
    in the decision log rather than a change made here to everybody's suite.
    """
    from apps.integrations import partner_api, partner_urls

    schema = json.loads(_export_to_string())
    schemes = schema["components"]["securitySchemes"]

    # ── the session cookie, unchanged since 2026-08-10 ──────────────────────
    assert schemes["sessionCookie"]["in"] == "cookie"  # not basicAuth, not `sessionid`
    assert schemes["sessionCookie"]["name"] == "sbh_session"

    # ── the partner key, DEF-INT-6529 ───────────────────────────────────────
    partner_scheme = schemes[partner_api.PARTNER_KEY_SCHEME_NAME]
    assert partner_scheme["type"] == "http" and partner_scheme["scheme"] == "bearer", (
        "the partner surface reads `Authorization: Bearer …` and nothing else "
        f"(partner_api._presented_key): {partner_scheme}"
    )
    # ── `DEF-INT-10020` — the inbound doors published on the partner surface
    # (US Payments: `password`), one scheme per header, DERIVED from the
    # manifests by `inbound_api.published_key_schemes()`.
    from apps.integrations import inbound_api

    published = inbound_api.published_key_schemes()
    assert set(published) == {"passwordHeader"}, published
    assert schemes["passwordHeader"] == {**published["passwordHeader"]}
    assert schemes["passwordHeader"]["type"] == "apiKey" and schemes["passwordHeader"]["in"] == "header"
    assert set(schemes) == {
        "sessionCookie",
        "nativeBearer",  # CR-187-BRC10 — apps/identity/native_auth.py
        partner_api.PARTNER_KEY_SCHEME_NAME,
        *published,
    }
    # `CR-187-BRC10` — the native bearer is published on the field routes and
    # on nothing else.
    native_ops = {
        path
        for path, operations in schema["paths"].items()
        for operation in operations.values()
        if {"nativeBearer": []} in (operation.get("security") or [])
    }
    assert native_ops and all(
        p.startswith("/api/{tenant}/work/mobile/") for p in native_ops
    ), native_ops

    keyed_inbound = sorted(
        f"{method} {path}"
        for path, operations in schema["paths"].items()
        for method, operation in operations.items()
        if operation.get("security") == [{"passwordHeader": []}]
    )
    assert keyed_inbound == sorted(
        f"{method} /api/partner/v1/{name}{slash}"
        for name, method in (("account-lookup", "get"), ("add-payment", "post"), ("add-return", "post"))
        for slash in ("", "/")
    ), keyed_inbound

    secured, partner, public = [], [], []
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            security = operation.get("security")
            if security == [{"sessionCookie": []}]:
                secured.append(f"{method} {path}")
            elif security == [{partner_api.PARTNER_KEY_SCHEME_NAME: []}]:
                partner.append(f"{method} {path}")
            elif security == [{}]:
                public.append(f"{method} {path}")

    # ⚠ DERIVED, NEVER TYPED (false pass 2). `PARTNER_ROUTES` is the authority
    # for the phase-2 addresses and each is registered twice, with and without
    # a trailing slash; the three `/api/{tenant}/v1/…` addresses are the
    # retired pair plus the published specification, and `partner_api`'s own
    # docstrings record that all three authenticate by key like the rest.
    # ⚠ **THE VERB COMES FROM THE VIEW, NOT FROM THE NAME.** A first draft read
    # `'post' if name == 'make-payment' else 'get'`, which is a second place
    # that has to be edited the day a door changes verb or a second write
    # lands — and it would have been edited by nobody. `@api_view(["POST"])`
    # puts exactly that list on the wrapped view, so the route table already
    # knows.
    # `options` is DRF's own automatic verb and is not published, so it is
    # dropped here exactly as the generator drops it.
    expected_partner = {
        f"{method} /api/partner/v1/{name}{slash}"
        for name, view in partner_urls.PARTNER_ROUTES.items()
        for method in view.cls.http_method_names
        if method not in ("options", "head", "trace")
        for slash in ("", "/")
    } | {
        "get /api/{tenant}/v1/payments",
        "get /api/{tenant}/v1/billing",
        "get /api/{tenant}/v1/openapi.json",
    }
    assert set(partner) == expected_partner, (
        "a partner address is published without naming the key it demands, or "
        f"an address left the route table: {set(partner) ^ expected_partner}"
    )
    # …and it is not vacuous (false pass 3): ten addresses, two spellings each,
    # plus the three tenant-path ones.
    assert len(partner) == 2 * len(partner_urls.PARTNER_ROUTES) + 3 == 23

    # ── what may honestly say "no credential" ───────────────────────────────
    assert sorted(public) == sorted(
        PUBLISHES_AS_NEEDING_NO_CREDENTIAL + CREDENTIALLED_BUT_PUBLISHED_AS_PUBLIC
    ), "the world-readable surface changed — add the address by name, never widen this"
    assert len(secured) > 100 and all("/api/public/" not in op for op in secured)

    # ── false pass 1: a name nobody defines is an invalid document ──────────
    referenced = {
        name
        for operations in schema["paths"].values()
        for operation in operations.values()
        for requirement in (operation.get("security") or [])
        for name in requirement
    }
    assert referenced <= set(schemes), (
        "an operation names a security scheme `components.securitySchemes` does "
        f"not define — the document is invalid OpenAPI: {referenced - set(schemes)}"
    )


def test_be11_tc05_the_committed_snapshot_matches_what_the_code_exports():
    """ADDED 2026-08-10 — the CI-diff clause, enforced where people can see it.

    The clause was described in three places (SPECTACULAR_SETTINGS, the command
    docstring, this file's own trace header) and implemented in none: no
    workflow ran the export and openapi/schema.json did not exist. A CI step now
    does it, but a check that only exists in a workflow is invisible to anyone
    running the suite — and the drift it catches is cheapest to fix before the
    push. So the snapshot is asserted here as well.

    Red means the API changed shape. Update A11 + 11b and the FI-01 client in
    the same review, then `python manage.py export_openapi` and commit.
    """
    from apps.tenancy.management.commands.export_openapi import DEFAULT_OUT

    assert DEFAULT_OUT.exists(), f"the committed OpenAPI snapshot is missing: {DEFAULT_OUT}"
    assert DEFAULT_OUT.read_text(encoding="utf-8") == _export_to_string(), (
        "06-backend/openapi/schema.json is stale — the API changed shape without the "
        "contract snapshot moving with it. Run: python manage.py export_openapi"
    )


def test_be11_tc04_the_no_tenant_surface_publishes_without_a_tenant_segment():
    """The public + platform routes are the OTHER half of the 2026-08-10
    contract, and FI-01 has to see them as tenant-less or it will build a
    client that cannot call them before a tenant exists."""
    from core import openapi

    paths = json.loads(_export_to_string()).get("paths", {})
    assert "/api/public/pricing-plans" in paths
    assert "/api/public/subdomain-check" in paths
    assert "/api/tenants" in paths  # provisioning: no tenant exists yet
    assert "/api/jobs/{job_id}" in paths
    assert "/api/exports" in paths
    assert "/api/exports/{job_id}/file" in paths
    # …and NOTHING publishes the raw router literal: if config/urls.py changes
    # its tenant mount without updating core.openapi, this goes red instead of
    # shipping an unusable path to the generated client.
    assert not [p for p in paths if openapi.TENANT_MOUNT_LITERAL in p]
    assert any(p.startswith("/api/{tenant}/") for p in paths)
