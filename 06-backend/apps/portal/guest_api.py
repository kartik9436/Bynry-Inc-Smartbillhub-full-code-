# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-001 (EP-CWP-01) — `GET /public/front`, the front page's data
#           source (07-endpoints.md §1 row 1). Screens: CWP-001
# Rules:    NFR-39 · NFR-41 (PO ruling 2026-09-03 — the portal's own rate limit
#           per tenant and its own connection budget, in guards.py) ·
#           BR-CWP-005 (the tenant is resolved from the first path segment,
#           `app.tenant_id` set and RLS forced, BEFORE the question "who is
#           this" is asked — here nobody is asked at all) · BR-CWP-007 (the
#           portal lives at `/{tenant}/portal/…`) · BR-CWP-011 (the guest edge
#           is its own file and its own middleware — anonymous, throttled) ·
#           BR-CWP-021 (never a person) · BR-CWP-022 (behind the anonymous
#           throttle at sixty a minute the product already applies — REUSED,
#           not copied) · BR-CWP-026 (no guest write can change an account —
#           this edge has no write at all)
# Tests:    06-backend/tests/test_us_cwp_001_front.py (TC-1..6) ·
#           test_us_cwp_007_report.py · test_us_cwp_010_track.py ·
#           test_us_cwp_002_lockout.py
# Impacts:  config/urls.py (the include under the tenant prefix) ·
#           07-frontend/src/portal/api/guestClient.ts
# ───────────────────────────────────────────────────────
"""THE GUEST EDGE — every unauthenticated portal route. Three in wave B.
Mounted at `/api/{tenant}/portal/public/…`. The signed-in customer's edge
(`api.py`) is a separate file that arrives with its first route, wave E.

THIN by law (B8 / LAW 0): resolve the tenant, ask the selector, answer. The
three decorators are the whole security story of this file and are stated
rather than inherited: no authentication (a stale staff cookie must not 401 a
visitor, and must not enter any context — `authentication_classes([])`),
anyone may call (`AllowAny`), and no more than sixty calls a minute from one
address (`PublicOnboardingThrottle`, `apps/tenancy/api.py:84-88` — the
throttle the three existing public endpoints already sit behind).

WHY `require_tenant` AND NOT A LOOKUP OF OUR OWN. BE-01 has already resolved
the slug and set `app.tenant_id` before this view runs; `require_tenant`
answers 404 for a slug that resolved to nothing — byte-identical for an
unknown utility and for a foreign one — which is US-CWP-001 TC-6: an address
whose first segment is a reserved word or a stranger's slug does not 500 and
tells nobody anything.
"""

from typing import Any

from django.urls import path
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.portal import applications, availability as availability_read
from apps.portal import lockout, selectors, services
from apps.portal.guards import PortalTenantThrottle, portal_admission
from apps.portal.seams import metering_seam, tenancy_seam
from apps.portal.seams.customers_seam import CHANNEL_CUSTOMER_PORTAL
from apps.metering import interruptions as interruption_models
from apps.tenancy.api import PublicOnboardingThrottle
from core import errors
from core.document_response import document_http_response
from core.tenancy import require_tenant


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])  # per address AND per tenant (NFR-39)
@portal_admission  # the connection budget — refused before the first query (NFR-39, NFR-41)
def front(request: Any) -> Response:
    """`GET /portal/public/front` — branding, ALL SIX errand cards with
    whether each may be used, and the five switches.

    ⚠ **`cards` USED TO BE THE FILTERED LIST OF KEYS A VISITOR COULD USE.**
    PO ruling 2026-09-05, verbatim: *"Yoi ahev these cards - may be disable
    them, but for completess have them on screen"*. It now carries all six, in
    `CARD_ORDER`, each `{key, available, reason_code}` — and `reason_code` is
    one of exactly three CATALOGUE KEYS, never a sentence: the screen says it
    in the reader's own language and no code reaches the glass (B14 rule 31).
    `selectors.cards_for` holds the reasoning.

    ⚠ **A DRAWN CARD IS NOT A MOUNTED DOOR.** The endpoint behind an
    unavailable card refuses exactly as it did when the card was hidden
    (`BR-CWP-002`, at the edge), and `links` is untouched — the *Help* and
    *Visit us* nav words still come and go with published content, because a
    nav word is a destination and not a catalogue.

    `is_live: false` answers with the holding page's data (name and colours
    only) and NO cards at all — a holding page has no grid to disable. Nothing
    here reads a customer, an account or a bill.

    COST (NFR-41): three point reads by primary key or by the tenant's own
    indexed foreign key — the tenant row, the settings row, the enabled
    services — and no join across anything a tenant accumulates. The count is
    asserted in tests/test_us_cwp_001_load.py, so a fourth query is a red test
    and not a slow afternoon.
    """
    tenant_id = require_tenant(request)
    return Response(selectors.front(tenant_id))


def _lock_key_tenant(tenant_id: Any) -> str:
    """What the lockout counts against — the tenant ID `require_tenant` has
    already resolved from the first path segment (`BR-CWP-005`), never the slug
    (see `lockout.py`: a slug is editable and a lock must not be)."""
    return str(tenant_id)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def reports(request: Any) -> Response:
    """`POST /portal/public/reports` — a passer-by reports a burst main.

    ⚠ **`gas_smell` IS ANSWERED HERE AND WRITES NOTHING** (`US-CWP-007` TC-3).
    The emergency panel is ROUTING, not a disclaimer: a form that quietly
    accepts *"smell of gas"* and queues it behind a missed collection is worse
    than no form. The response carries the utility's own emergency number and
    `created: false`, and **no service is called at all** — the test counts rows
    after this call and finds none.

    ⚠ **NO FILE IS ACCEPTED ON THIS ROUTE, IN ANY FIELD** (`US-CWP-007` TC-8).
    Consumer upload is a SIGNED DEFERRAL (PO 2026-08-08, `DF-4`; `CR-068` §2b)
    awaiting a re-sign, so the screen's photo picker is HELD with its reason and
    this edge refuses a payload naming one rather than dropping it silently — a
    dropped file is a screen that says *"attached"* over nothing.
    """
    tenant_id = require_tenant(request)
    body = request.data if isinstance(request.data, dict) else {}

    for forbidden in ("photo", "photos", "file", "files", "attachment", "attachments"):
        if forbidden in body:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="CR-068 §2b",
                message_key="portal.report.photoHeld",
                params={"field": forbidden},
            )

    kind = str(body.get("kind") or "").strip()
    if kind not in interruption_models.KINDS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="portal.report.kindUnknown",
            params={"value": kind},
        )

    if kind == interruption_models.KIND_GAS_SMELL:
        # ROUTING. Nothing is created — not a request, not an interruption.
        settings = selectors.settings_view(tenant_id)
        brand = tenancy_seam.branding(tenant_id)
        return Response(
            {
                "created": False,
                "emergency_phone": settings.get("emergency_phone"),
                "tenant_name": brand["trading_name"],
            }
        )

    # ⚠ **`report_a_problem` BECAME ONE SHAPE OF `raise_service_request` ON
    # 2026-09-04 (CR-068 wave C).** G81 allows exactly ONE public function per
    # declared write kind, and the application and the quick asks are the same
    # kind as the report, so the three share the entry point and the bodies stay
    # private. The report's own arguments are unchanged.
    result = services.raise_service_request(
        tenant_id,
        shape=services.SHAPE_REPORT,
        payload={
            "kind": kind,
            "location_text": body.get("location_text"),
            "notes": body.get("notes"),
            "reporter_name": body.get("reporter_name"),
            "reporter_phone": body.get("reporter_phone"),
        },
    )
    # ⚠ **`result["reference"]` IS THE `SR-` NUMBER SINCE `CR-072`, AND THIS
    # LINE USED TO STRIP IT.** It read `result.pop("request_no", None)` with the
    # comment *"the clerk's SR- number is a clerk's vocabulary"* — which was
    # true while the act wrote two rows and handed back the other one's number.
    # The report IS the request now, so the number of the record is the number
    # the person is given: `BR-CWP-024`, one reference and it is theirs.
    result["created"] = True
    return Response(result, status=201)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def track(request: Any) -> Response:
    """`POST /portal/public/track` — one box for every reference we hand out.

    **A POST rather than a GET, and it is not a mistake.** A reference and the
    postcode of somebody's home in a query string end up in access logs, in
    browser history and in a `Referer` header. Nothing here changes anything, so
    the verb is doing one job: keeping two facts out of places nobody meant to
    put them.

    **THREE ANSWERS AND ONLY THREE**, and two of them are deliberately the same:

      * **locked** — five wrong pairs from this address, this form, this
        utility (`BR-CWP-023`). A CORRECT pair inside the window is refused too,
        which is what makes it a lockout rather than a delay;
      * **not found** — for an unknown reference, another tenant's reference,
        and a real reference with the wrong second fact, **identically**
        (`TC-3`, `TC-6`);
      * **found** — progress and never data (`BR-CWP-024`).
    """
    tenant_id = require_tenant(request)
    body = request.data if isinstance(request.data, dict) else {}
    lock_tenant = _lock_key_tenant(tenant_id)
    address = lockout.address_of(request)

    if lockout.is_locked(lock_tenant, lockout.FORM_TRACK, address):
        raise errors.BizError(
            errors.BIZ_LOCKED,
            br_ref="BR-CWP-023",
            message_key="portal.track.locked",
            params={"minutes": lockout.LOCK_SECONDS // 60},
        )

    found = selectors.track(
        tenant_id,
        reference=body.get("reference"),
        second_fact=body.get("second_fact"),
    )
    if found is None:
        lockout.record_wrong(lock_tenant, lockout.FORM_TRACK, address)
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-024",
            message_key="portal.track.notFound",
        )
    lockout.clear(lock_tenant, lockout.FORM_TRACK, address)
    return Response(found)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@parser_classes([MultiPartParser])
@portal_admission
def track_document(request: Any) -> Response:
    """`POST /portal/public/track/documents` — **the applicant answers *Ask for
    more* with a file** (`DEF-CWP-9049`, 2026-10-02).

    A clerk could ask for a clearer ID and the applicant had nowhere to send
    it. Now the Track page, once a reference and its second fact have found a
    request in `more_info`, offers *Add a document*, and this is its door.

    **The same proof `track` asks for, under the same lockout** — five wrong
    pairs from this address lock both, because a door that accepts a file
    after a wrong pair would be the enumeration `BR-CWP-023` guards against
    with an upload attached. A miss is the same *not found* `track` gives.
    **The same file rules as the application** (`applications.read_upload`:
    PDF, JPG, PNG by their bytes, 10 MB), and the five-per-application figure
    and the state rule are customers' (`attach_reply_from_portal`). The answer
    is the request's progress again, so the screen redraws from one reply.
    """
    tenant_id = require_tenant(request)
    body = request.data
    lock_tenant = _lock_key_tenant(tenant_id)
    address = lockout.address_of(request)
    if lockout.is_locked(lock_tenant, lockout.FORM_TRACK, address):
        raise errors.BizError(
            errors.BIZ_LOCKED,
            br_ref="BR-CWP-023",
            message_key="portal.track.locked",
            params={"minutes": lockout.LOCK_SECONDS // 60},
        )
    reference = body.get("reference")
    second_fact = body.get("second_fact")
    request_id = selectors.tracked_request_id(
        tenant_id, reference=reference, second_fact=second_fact
    )
    if request_id is None:
        lockout.record_wrong(lock_tenant, lockout.FORM_TRACK, address)
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-024",
            message_key="portal.track.notFound",
        )
    upload = request.FILES.get("file") if hasattr(request, "FILES") else None
    try:
        name, media_type, payload = applications.read_upload(upload)
    except applications.DocumentRefused as refusal:
        return Response(
            errors.http_series_refusal_body(
                refusal.message_key, br_ref="DEF-CWP-9049", **refusal.params
            ),
            status=refusal.status,
        )
    services.raise_service_request(
        tenant_id,
        shape=services.SHAPE_REPLY_DOCUMENT,
        payload={
            "request_id": request_id,
            "name": name,
            "content_type": media_type,
            "payload": payload,
        },
    )
    return Response(
        selectors.track(tenant_id, reference=reference, second_fact=second_fact)
    )


# ══ CR-068 wave P (screen half) — QUICK PAY, STEP 1 (US-CWP-002 · US-CWP-003) ══
#
# ⚠ **THE LOOKUP SHIPS AND THE PAYMENT DOES NOT, AND THAT IS THE WAVE ORDER
# RATHER THAN HALF A FEATURE.** `EP-CWP-02` holds every screen in the epic
# before release 5 because no gateway exists (`CR-068` `R2`); what `R3` then
# requires is that the Pay control appear **in its normal place, disabled,
# carrying its reason** — never hidden and never live-but-inert. Finding the
# bill is a READ and has no such dependency, so it is built, and it is what
# `US-CWP-002`'s lockout is in front of.


def _quick_pay_is_on(tenant_id: Any) -> None:
    """`BR-CWP-002` for quick pay — the refusal is at the EDGE, not at the
    screen, exactly as `_requests_are_on` is for the ask cards.

    A utility that has switched quick pay off hides the *Pay a bill* card on
    `CWP-001`; a form nobody can see is still a form somebody can POST to.
    """
    settings = selectors.settings_view(tenant_id)
    if not settings["is_live"] or not settings["quick_pay_enabled"]:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-002",
            message_key="portal.quickPay.notOffered",
        )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def bill_lookup(request: Any) -> Response:
    """`POST /portal/public/bills/lookup` — `CWP-002`, step 1 of quick pay.

    **A POST, and for the reason `track` gives one line up:** a bill number and
    the postcode of somebody's home in a query string end up in access logs, in
    browser history and in a `Referer` header. Nothing here changes anything.

    **THREE ANSWERS AND ONLY THREE**, two of them deliberately identical:

      * **locked** — five wrong pairs from this address, this form, this
        utility (`BR-CWP-023`). A CORRECT pair inside the window is refused
        too, which is what makes it a lockout rather than a delay
        (`US-CWP-002` TC-3);
      * **not found** — an unknown number, a real number with the wrong
        postcode, a draft, and another utility's number, **byte-identical**
        (`US-CWP-003` TC-2, TC-3, TC-6). *"A different message would confirm
        the bill number exists."*;
      * **found** — `BR-CWP-019`'s narrow list and nothing else.

    ⚠ **THE LOCK IS PER FORM AND `FORM_QUICK_PAY` HAS BEEN RESERVED IN
    `lockout.py` SINCE WAVE B** for this exact moment. Locking track does not
    lock quick pay (`US-CWP-002` TC-5): they are different doors, and a person
    guessing references is not a person guessing bill numbers.

    ⚠ **A UTILITY THAT SWITCHED QUICK PAY OFF REFUSES THE ENDPOINT AS WELL AS
    HIDING THE CARD** (`BR-CWP-002`). A screen that merely does not draw the
    door is defeated by calling the door directly.
    """
    tenant_id = require_tenant(request)
    _quick_pay_is_on(tenant_id)
    body = request.data if isinstance(request.data, dict) else {}
    lock_tenant = _lock_key_tenant(tenant_id)
    address = lockout.address_of(request)

    if lockout.is_locked(lock_tenant, lockout.FORM_QUICK_PAY, address):
        raise errors.BizError(
            errors.BIZ_LOCKED,
            br_ref="BR-CWP-023",
            message_key="portal.quickPay.locked",
            params={"minutes": lockout.LOCK_SECONDS // 60},
        )

    found = selectors.bill_lookup(
        tenant_id,
        bill_number=body.get("bill_number"),
        postcode=body.get("postcode"),
    )
    if found is None:
        lockout.record_wrong(lock_tenant, lockout.FORM_QUICK_PAY, address)
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-019",
            message_key="portal.quickPay.notFound",
        )
    lockout.clear(lock_tenant, lockout.FORM_QUICK_PAY, address)
    return Response(found)


# ══ CR-068 wave D — published content, read (US-CWP-072 · 073 · 074) ═══════
#
# ⚠ **THE WRITE IS NOT HERE, AND ITS ABSENCE IS DELIBERATE.**
# `POST /public/help/{slug}/feedback` — the read count and the *did this help?*
# vote — is served by `apps/tenancy/published_content_api.py`, because
# `help_answer_feedback` is a **tenancy** table (`03-field-map.md` §2) and B2
# §2 forbids a cross-module write: `apps/portal` could not write that row
# wherever the route was mounted. `G81` holds that line file by file, and this
# file stays what it says it is — read-only. See the decision log 2026-09-04
# and `DEF-CWP-3646`.


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def help_answers(request: Any) -> Response:
    """`GET /portal/public/help` — `CWP-011`.

    ⚠ **`status = published` IS IN THE QUERY** (BR-CWP-094, and
    `07-endpoints.md` §1 row 11 says so in its own words). A draft and a
    not-shown answer never leave the back office; `US-CWP-071` TC-2 asserts the
    exclusion at query level, not at the template.

    ⚠ **AND THE CUSTOMER IS NEVER TOLD A COUNT OF WHAT IS HIDDEN** (TC-3). The
    body carries the published rows and their topics and nothing else — no
    total, no `hidden`, no *"6 of 8"*.
    """
    tenant_id = require_tenant(request)
    topic = request.query_params.get("topic") or None
    return Response(
        {
            "answers": tenancy_seam.published_help_answers(tenant_id, topic=topic),
            "topics": tenancy_seam.help_topics(tenant_id),
            "visit_link": tenancy_seam.shown_service_centre_count(tenant_id) > 0,
        }
    )


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def help_answer(request: Any, slug: str) -> Response:
    """`GET /portal/public/help/{slug}` — one answer.

    The reader's language comes from `?locale=`, which the browser's own
    setting fills in. ⚠ A locale with no variant gets **English with a line
    saying so** and never a blank (`BR-CWP-094`: *"a missing translation is
    better than a missing answer"*).
    """
    tenant_id = require_tenant(request)
    locale = request.query_params.get("locale") or None
    return Response(tenancy_seam.published_help_answer(tenant_id, slug, locale=locale))


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def service_centres(request: Any) -> Response:
    """`GET /portal/public/service-centres` — `CWP-013`.

    ⚠ Only `is_shown_to_customers`, and **404 when none is shown** — no empty
    page and no header link (`BR-CWP-093`, `US-CWP-074` TC-5). The depot is
    absent here and still in the clerk's list, which is the whole of
    `BR-CWP-096`.
    """
    tenant_id = require_tenant(request)
    return Response({"centres": tenancy_seam.shown_service_centres(tenant_id)})


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def service_centre(request: Any, slug: str) -> Response:
    """`GET /portal/public/service-centres/{slug}` — `CWP-014`.

    Today's state is **computed from the clock** and the week's hours; the
    holiday that closes it is read from the tenant's own calendar and typed by
    nobody (`BR-CWP-096`). ⚠ Facts travel, never a sentence — the screen writes
    *"Closed today · Opens Thursday at 9:00am"* in its own language (B14 rule
    35).
    """
    tenant_id = require_tenant(request)
    return Response(tenancy_seam.shown_service_centre(tenant_id, slug))


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def tips(request: Any) -> Response:
    """`GET /portal/public/tips?screen=` — at most ONE tip (`BR-CWP-095`).

    ⚠ **AN EMPTY RESPONSE IS A NORMAL RESPONSE**, not a 404 and not an error:
    `{"tip": null}` and the slot closes up so nobody can tell it was there
    (`US-CWP-073` TC-3). A screen asking for a tip on a quiet day is not asking
    for anything unusual.
    """
    tenant_id = require_tenant(request)
    screen = request.query_params.get("screen") or ""
    return Response({"tip": tenancy_seam.tip_for_screen(tenant_id, screen) if screen else None})


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave C — availability, the draft, the submit, and the quick asks
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THESE ARE THE FIRST GUEST ROUTES THAT WRITE SOMETHING A PERSON TYPED
# ABOUT THEMSELVES.** Each writes through exactly one declared path —
# `applications.save_draft` (the applicant's own unsent form) and
# `services.raise_service_request` (the write point, which also records the
# consent). G81 reads this file and fails it for any ORM write of its own: the
# edge resolves the tenant, validates the shape, calls one function and answers.


def _requests_are_on(tenant_id: Any) -> None:
    """`US-CWP-015` TC-4 — a utility that has switched requests off refuses the
    endpoint as well as hiding the cards.

    ⚠ **BR-CWP-002: THE REFUSAL IS AT THE EDGE, NOT AT THE SCREEN.** A screen
    that simply does not draw the cards is defeated by calling the endpoint
    directly, which is what the rule says in as many words.
    """
    settings = selectors.settings_view(tenant_id)
    if not settings["is_live"] or not settings["requests_enabled"]:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-002",
            message_key="portal.request.notOffered",
        )


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def availability(request: Any) -> Response:
    """`GET /portal/public/premises/availability?address=…` — `CWP-008`.

    ⚠ **AN ADDRESS NOBODY RECOGNISES IS A `200`, NOT A `404`** (`US-CWP-012`
    TC-2). The body says `matched: false` and the screen says *a person will
    look at it*, with the *Apply* route still open. A refusal here would lose an
    applicant at the first box — *"they may never become a customer if we refuse
    them"* (EP-CWP-04 §1) — and it would also tell a stranger which addresses
    this utility holds, one probe at a time.

    COST (NFR-41): one scan of the tenant's premises for the address, then four
    point reads. Nothing grows with how long the utility has been trading.
    """
    tenant_id = require_tenant(request)
    return Response(
        availability_read.availability(
            tenant_id,
            request.query_params.get("address"),
            # DEF-CWP-9817 — the town and ZIP step 1 now asks.
            city=request.query_params.get("city"),
            postal_code=request.query_params.get("postal_code"),
            # CR-200-BRC10 S8 — the apartment, as picked (a LABEL, never an id).
            unit=request.query_params.get("unit"),
        )
    )


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])  # per address AND per tenant
@portal_admission
def address_suggestions(request: Any) -> Response:
    """`GET /portal/public/premises/suggestions?q=…` — `CR-200-BRC10` S7.

    PO 2026-10-29 (1A): after **4** typed characters, at most **5** held
    addresses, **street + town + ZIP only** (and the state the ruled example
    prints) — never a name, never whether anyone lives there, never an id
    (`BR-CWP-021`, B14 rule 31). Under four characters the answer is an empty
    list, not a refusal. The same two throttles every public read sits behind
    (sixty a minute per address, and the tenant's budget). Metering's own
    matcher answers (`address_match.address_suggestions`), so the staff
    Approve window and this door never disagree about an address.

    ⚠ **IT WRITES NOTHING AND ANSWERS 200 FOR AN EMPTY LIST** — exactly as
    `availability` does for an unknown address, so a stranger learns nothing
    from a status code.
    """
    tenant_id = require_tenant(request)
    return Response(
        {"suggestions": metering_seam.address_suggestions(tenant_id, request.query_params.get("q"))}
    )


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def quick_services(request: Any) -> Response:
    """`GET /portal/public/quick-services` — the six cards `CWP-010` draws, from
    the utility's OWN list and never a hardcoded one (`US-CWP-015` TC-7). An
    empty list is the honest answer when requests are switched off."""
    tenant_id = require_tenant(request)
    return Response({"categories": selectors.quick_service_categories(tenant_id)})


@api_view(["GET", "PUT"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def application_draft(request: Any, token: str) -> Response:
    """`GET`/`PUT /portal/public/applications/{token}` — the draft that survives
    a closed tab (`US-CWP-013` TC-1), saved from the first keystroke and
    carrying **no reference** until it is sent.

    ⚠ **THE TOKEN IS THE ONLY THING THAT OPENS IT**, and a token from another
    utility opens nothing: the row is invisible under a different tenant's
    context (RLS, migration `portal/0004`), so TC-6 answers `404` — the same
    body a genuinely absent draft gets, because existence must not leak.
    """
    tenant_id = require_tenant(request)
    if request.method == "PUT":
        row = applications.save_draft(tenant_id, token, request.data)
        return Response(selectors.draft_view(row))
    # `open_draft`, not `draft_row`: opening the link is a VISIT and restarts
    # the 30 days an unsent draft is kept (PO ruling 2026-10-02). The stamp is
    # written in `applications.py`; this edge writes nothing (G81).
    row = applications.open_draft(tenant_id, token)
    if row is None:
        raise errors.NotFoundError()
    return Response(selectors.draft_view(row))


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@parser_classes([MultiPartParser])
@portal_admission
def application_documents(request: Any, token: str) -> Response:
    """`POST /portal/public/applications/{token}/documents` — attach ONE file
    to an unsent application (`CR-158-BRC10`, PO 2026-10-01; `DF-4` superseded
    for the new-service request ONLY — `reports` above still refuses a file).

    ⚠ **WHAT THIS EDGE DOES AND DOES NOT DECIDE.** It resolves the tenant,
    checks requests are switched on, takes the one `file` part and calls
    `applications.add_document`, which owns every guard: the type is read from
    the BYTES (PDF, JPG, PNG), the size is capped at 10 MB, five per
    application. A **415** or **413** answers the shared HTTP-series envelope,
    naming the file, exactly as the staff upload door does. G81 reads this file
    and fails it for any ORM write of its own.

    The answer is the whole draft again, its file list included, so the screen
    redraws from one reply.
    """
    tenant_id = require_tenant(request)
    _requests_are_on(tenant_id)
    upload = request.FILES.get("file") if hasattr(request, "FILES") else None
    # DEF-CWP-9167 — which required document this file is (`photo_id`,
    # `proof_of_address`), from the attach row it was chosen on.
    requirement = request.data.get("requirement") if hasattr(request, "data") else None
    try:
        applications.add_document(tenant_id, token, upload, requirement=requirement)
    except applications.DocumentRefused as refusal:
        return Response(
            errors.http_series_refusal_body(
                refusal.message_key, br_ref="CR-158-BRC10", **refusal.params
            ),
            status=refusal.status,
        )
    return Response(selectors.draft_view(applications.draft_row(tenant_id, token)))


@api_view(["DELETE"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def application_document(request: Any, token: str, document_id: str) -> Response:
    """`DELETE /portal/public/applications/{token}/documents/{id}` — the
    applicant takes a file back before sending. Answers the whole draft."""
    tenant_id = require_tenant(request)
    applications.remove_document(tenant_id, token, document_id)
    return Response(selectors.draft_view(applications.draft_row(tenant_id, token)))


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def application_document_content(request: Any, token: str, document_id: str) -> Any:
    """`GET /portal/public/applications/{token}/documents/{id}/content` — the
    applicant opens the file THEY attached (`DEF-CWP-9166`, PO 2026-10-02:
    *"user not able to view give view button"*).

    ⚠ **THE SAME SERVING CODE AS THE CLERK'S DOOR** (`core.document_response`,
    B14 rule 43): `inline` for the three types the bytes were sniffed as,
    `nosniff`, a policy that forbids any script inside the file, and
    `private, no-store`. A navigation, not a `fetch` — the screen opens it in a
    new tab.

    ⚠ **ONLY FROM ITS OWN DRAFT.** Found by token AND document AND tenant
    (`applications.document_file`); another draft's file, another utility's
    draft and a sent application's file all answer 404. G81 reads this file:
    the one write (an audit row) is `applications.py`'s.
    """
    tenant_id = require_tenant(request)
    served = applications.document_file(tenant_id, token, document_id)
    return document_http_response(
        payload=served["payload"],
        content_type=served["content_type"],
        name=served["name"],
        inline=served["inline"],
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def submit_application(request: Any, token: str) -> Response:
    """`POST /portal/public/applications/{token}/submit` — `CWP-009`'s commit,
    and ⚠ **the one place paperless consent is taken** (`BR-CWP-087`).

    Writes one service request with channel `customer_portal` and, when the box
    was ticked, one consent row carrying the version of the words. **No
    document and no account** (`US-CWP-014` §1).

    ⊕ 🔒 **AND, WHERE THE UTILITY CHARGES AN APPLICATION FEE ABOVE $0.00, THE
    CARD — `CR-191-BRC10` (PO 2026-10-23).** *"if there is a application or
    service fee then consumer will have to pay it online; they can't say pay
    later"*. The body then carries quick pay's own three: `instrument` (a
    token, a brand, a last four — `BR-CWP-057`; a card number is refused BY
    NAME, exactly as on `bill_pay`), `fee_amount` (the figure the applicant
    SAW, only ever compared) and `attempt_token` — ⛔ which is NO LONGER the
    key (`DEF-PAY-10554`, 2026-10-23): a reload minted a new one and so a new
    debit. The key is now the server's, kept on the draft
    (`services._fee_key`); the browser's token is passed and not read.
    The charge is `services._charge_the_application_fee`'s, through the same
    rails; a refusal from them is answered here through `_refusal_for`, so a
    declined card reads the same sentence on both guest forms. A fee of $0.00
    or none takes no card and these three are not read.
    """
    tenant_id = require_tenant(request)
    _requests_are_on(tenant_id)
    body = request.data if isinstance(request.data, dict) else {}
    payload: dict[str, Any] = {"token": token, "paperless": bool(body.get("paperless"))}
    given = body.get("instrument") if isinstance(body.get("instrument"), dict) else {}
    if any(field in body or field in given for field in CARD_FIELDS_NEVER_ACCEPTED) or given:
        # `_instrument` refuses a card number by name and a missing token.
        _no_surcharge_is_lawful_here(tenant_id)
        payload["instrument"] = _instrument(body)
    payload["fee_amount"] = body.get("fee_amount")
    payload["attempt_token"] = body.get("attempt_token")
    try:
        answer = services.raise_service_request(
            tenant_id, shape=services.SHAPE_APPLICATION, payload=payload
        )
    except errors.ApiError:
        raise
    except Exception as failure:  # noqa: BLE001 — mapped exactly as `bill_pay` maps it
        refusal = _refusal_for(failure)
        if refusal is not None:
            raise refusal from failure
        raise
    return Response(answer)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def quick_request(request: Any) -> Response:
    """`POST /portal/public/requests` — the quick asks (`CWP-010`).

    ⚠ **A CATEGORY THE UTILITY DOES NOT OFFER IS REFUSED HERE**, before anything
    is written: the six cards are the tenant's own list and a caller that names a
    seventh is naming something this utility does not do (`US-CWP-015` TC-6).
    """
    tenant_id = require_tenant(request)
    _requests_are_on(tenant_id)
    body = request.data if isinstance(request.data, dict) else {}
    category = selectors.quick_service_category(tenant_id, body.get("category"))
    if category is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="portal.request.categoryUnknown",
            params={"value": str(body.get("category") or "")},
        )
    # ⚠ **THE ADDRESS IS REQUIRED AND THAT IS `customers`' RULE SHOWING
    # THROUGH, NOT A CHOICE MADE HERE.** `_clean_capture` refuses a request with
    # no `address_as_given` on every channel — *"there is no such thing as a
    # service request about nowhere"* — and `BR-CUS-070` keeps it verbatim. A
    # form that let somebody ask for a re-read without saying where would be
    # accepted by the screen and refused by the service, which is the shape of
    # refusal a person cannot act on. So it is asked for, and marked required,
    # on the screen.
    for field in ("name", "phone", "address"):
        if not str(body.get(field) or "").strip():
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="portal.request.fieldRequired",
                params={"field": field},
            )
    if category["needs_bill_number"] and not str(body.get("bill_number") or "").strip():
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="portal.request.billNumberRequired",
            params={},
        )
    return Response(
        services.raise_service_request(
            tenant_id,
            shape=services.SHAPE_QUICK_ASK,
            payload={
                "category": category,
                "name": body.get("name"),
                "email": body.get("email"),
                "phone": body.get("phone"),
                "address": body.get("address"),
                # CR-200-BRC10 S9 — a picked suggestion's parts and the
                # apartment LABEL (never an id); re-matched by the service.
                "street": body.get("street"),
                "city": body.get("city"),
                "postal_code": body.get("postal_code"),
                "unit": body.get("unit"),
                "details": body.get("details"),
                "bill_number": body.get("bill_number"),
            },
        )
    )


urlpatterns = [
    path("portal/public/front", front),
    path("portal/public/reports", reports),
    path("portal/public/track", track),
    path("portal/public/track/documents", track_document),
    # CR-068 wave P (screen half) — `07-endpoints.md` §1 row 2. Row 3
    # (`POST /public/bills/{ref}/pay`) is NOT here: no rails exist, and a
    # live unauthenticated route that answers only "held" is surface with
    # nobody on the other side of it (`DEF-CWP-3704`'s finding). The held
    # reason is drawn by the SCREEN, where a person can read it.
    path("portal/public/bills/lookup", bill_lookup),
    # CR-068 wave D — the four published-content reads (07-endpoints.md §1
    # rows 11–14) plus the tip slot (§2 *Help, tips and feedback*). Every one
    # of them is a READ; the one write on this surface is tenancy's, above.
    path("portal/public/help", help_answers),
    path("portal/public/help/<str:slug>", help_answer),
    path("portal/public/service-centres", service_centres),
    path("portal/public/service-centres/<str:slug>", service_centre),
    path("portal/public/tips", tips),
    # CR-068 wave C — the journey that begins before identity exists
    # (07-endpoints.md §1 rows 4, 7, 8, 9). `GET /public/prices` (row 5) is
    # deliberately NOT here: no screen in wave C reads it — `CWP-008` is
    # answered whole by `availability` — and a live endpoint no screen reads
    # is surface without a caller (`DEF-CWP-3704`; the endpoints doc is
    # stamped, and the *What things cost* screen owns it).
    path("portal/public/premises/availability", availability),
    path("portal/public/premises/suggestions", address_suggestions),
    path("portal/public/quick-services", quick_services),
    path("portal/public/applications/<str:token>", application_draft),
    path("portal/public/applications/<str:token>/submit", submit_application),
    path("portal/public/applications/<str:token>/documents", application_documents),
    path(
        "portal/public/applications/<str:token>/documents/<str:document_id>",
        application_document,
    ),
    # DEF-CWP-9166 — the applicant's own file, opened from step 3 and step 4.
    path(
        "portal/public/applications/<str:token>/documents/<str:document_id>/content",
        application_document_content,
    ),
    path("portal/public/requests", quick_request),
]


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave R — QUICK PAY, STEP 2 AND STEP 3 (US-CWP-004 · US-CWP-005)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THIS IS THE FIRST GUEST ROUTE THAT MOVES MONEY, AND THE ONLY ONE ON THIS
# SURFACE WITH NOBODY SIGNED IN BEHIND IT.** Everything below is therefore
# stated rather than inherited.
#
# **THE PAIR IS RE-PROVED HERE AND STEP 1 IS NOT TRUSTED.** `US-CWP-002`'s
# five-tries lockout guards `bills/lookup`; a commit endpoint that accepted a
# client-held *"I already looked this up"* would be a SECOND DOOR onto the same
# secret with no counter on it, and a guesser would simply stop calling step 1.
# So `bill_pay` calls the same selector, burns a try on a miss, and answers the
# same sentence — `US-CWP-003` TC-2's *"a different message would confirm the
# bill number exists"* holds at step 2 exactly as it holds at step 1.
#
# **THE FIGURE IS RE-READ AND THE CLIENT'S IS ONLY EVER COMPARED.**
# `US-CWP-004` §7 is verbatim: *"the amount owing at the moment of commit,
# re-read rather than carried from step 1"*. What the browser sends is what the
# person SAW; if it disagrees with what is owed now the commit is refused rather
# than silently corrected, because hard rule 4 makes a payment row a thing that
# can be reversed and never edited — the cheap moment to be careful is before it
# exists (`BR-CWP-058`).
#
# **NO CARD NUMBER REACHES THIS PROCESS, EVER** (`US-CWP-004` §5, *"Never
# stored"*). What arrives is the gateway's token and its two visible facts
# (`BR-CWP-057`). A body naming a card number is REFUSED BY NAME rather than
# dropped — the posture `reports` takes for an attached photo above, and for the
# same reason: a field quietly ignored is a field some future serialiser starts
# logging.
#
# ⚠ **AND THERE IS NO FEE LINE ON THIS PATH.** `OQ-1394` is **CLOSED**
# (2026-09-04) and the answer was neither of the two the register offered: the
# Product Owner took BOTH — *"we have to give both the options so far some
# utilities abosrb it other pass it to customer ; so we have to flexible and
# create a flag somewhere to on and off it"*. The switch is a **payments**
# setting and not a portal one (the same fee applies at the counter), it does
# not exist yet, and beta ships defaulting to ABSORB. So nothing here computes,
# discloses or charges a surcharge — and `_no_surcharge_is_lawful_here` refuses
# rather than guessing on the day a tenant turns one on, because a surcharge
# undisclosed before the commit is the one thing the ruling forbids by name.


#: Hard rule 7's WHO, for a money action with no user behind it. ⚠ **A PAYMENT
#: ROW WITH NO ACTOR IS A ROW NOBODY CAN EXPLAIN A YEAR LATER**, so the guest
#: form names itself: this constant travels to the rails and into `audit_log`
#: beside the channel. It is not a user id and must never be resolved to one —
#: nobody is signed in, and inventing a person would be worse than the gap.
GUEST_PAID_BY = "portal_guest"

#: Field names this edge refuses outright. `US-CWP-004` §5: the card number, the
#: expiry and the security code go to the GATEWAY and are never stored, so they
#: may not appear in a request this process can see, log or trace.
CARD_FIELDS_NEVER_ACCEPTED: tuple[str, ...] = (
    "card_number",
    "cardnumber",
    "pan",
    "cvc",
    "cvv",
    "security_code",
    "expiry",
    "exp_month",
    "exp_year",
)

#: What `BR-CWP-057` says a stored instrument is, and the whole of it.
INSTRUMENT_FIELDS: tuple[str, ...] = ("token", "brand", "last_four")


def _no_surcharge_is_lawful_here(tenant_id: Any) -> None:
    """`OQ-1394` CLOSED 2026-09-04 — absorbed or surcharged, per tenant.

    ⚠ **THIS IS A GUARD, NOT A CALCULATION, AND THE DIFFERENCE IS THE RULING.**
    The Product Owner's answer obliges three things of the surcharged path: the
    fee is **computed** from the processor's schedule, **disclosed before the
    commit** — *"a customer paying `$142.18` must see the surcharge and the new
    total before they press, never after"* — and **checked against the
    customer's state**. None of the three is possible without a real processor,
    and the switch that would turn it on is a `payments` setting that does not
    exist yet. Beta therefore ships ABSORBED, and this function's only job is to
    keep that TRUE rather than assumed: the day the setting arrives, a tenant
    with surcharge on refuses here instead of a customer being charged a fee
    nobody showed them.
    """
    from apps.portal.seams import payments_seam

    surcharge_on = getattr(payments_seam, "card_surcharge_enabled", None)
    if surcharge_on is not None and surcharge_on(tenant_id):
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="OQ-1394",
            message_key="portal.quickPay.surchargeNotPriced",
        )


def _instrument(body: dict[str, Any]) -> dict[str, Any]:
    """The gateway token and its two visible facts, and nothing beside them."""
    given = body.get("instrument") if isinstance(body.get("instrument"), dict) else {}
    for forbidden in CARD_FIELDS_NEVER_ACCEPTED:
        if forbidden in body or forbidden in given:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CWP-057",
                message_key="portal.quickPay.cardNotAccepted",
                params={"field": forbidden},
            )
    if not str(given.get("token") or "").strip():
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="portal.quickPay.instrumentRequired",
            params={},
        )
    return {field: given.get(field) for field in INSTRUMENT_FIELDS}


def _squashed_money(value: Any) -> Any:
    """`"142.18"`, `"142.1800"` and `142.18` are one figure; `100.00` is not.

    ⚠ **COMPARED AS A DECIMAL AND NEVER AS A STRING.** The browser renders two
    places and the store keeps four, so a string comparison would refuse every
    honest commit — and a float comparison would eventually accept a dishonest
    one (hard rule 2: never float).
    """
    from decimal import Decimal, InvalidOperation

    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _attempt_key(tenant_id: Any, number: str, attempt_token: Any) -> str:
    """Hard rule 6 — the same attempt twice must leave ONE payment.

    The browser mints one token per visit to `CWP-003` (the reasoning
    `draftToken.ts` records one directory over), so a double press, a refreshed
    tab and a retried request all carry the SAME key and the rails collapse them.
    A caller that sends none gets a key that cannot collide with anything, which
    is the honest answer: we cannot make an idempotent promise about a request
    that never asked for one.
    """
    import uuid

    token = str(attempt_token or "").strip() or f"noattempt-{uuid.uuid4()}"
    return f"guestpay:{tenant_id}:{number}:{token}"


def _rails() -> Any:
    """`apps.payments.gateway`, resolved through `sys.modules` at the call.

    ⚠ **`from apps.payments import gateway` IS NOT THE SAME THING, AND THE
    DIFFERENCE COST TWO SUITES (found 2026-09-05).** Once any module has
    imported the submodule, the `apps.payments` PACKAGE carries `gateway` as an
    attribute, and `from … import …` reads that attribute — it consults
    `sys.modules` only when the attribute is missing. So a test that installs a
    stand-in with `monkeypatch.setitem(sys.modules, "apps.payments.gateway", …)`
    is **silently bypassed** the moment anything else has imported the real one
    first, and the fixture then asserts against the REAL rails while reading
    like it is asserting against its recorder.
    **It is order-dependent, so it hides:** `test_us_cwp_004_pay.py` passes
    alone and fails beside `test_us_cwp_045_pay_now.py`, which imports the
    module at collection — three cases, on the tip, before this lane existed.
    A recorder that is not called cannot say so.

    `import_module` reads `sys.modules` FIRST, so whatever is installed there is
    what runs. It is also the idiom every seam in this repo already uses
    (`billing_seam._resolve`, `apps/billing/tenancy_seam.py`), so this is the
    house style rather than an accommodation.
    """
    from importlib import import_module

    return import_module("apps.payments.gateway")


def _refusal_for(failure: Any) -> Any | None:
    """What a stranger reads when the rails would not take their money — **or
    `None` when this is not a refusal the rails made**, which keeps its old
    answer.

    **FOUR THINGS CAN GO WRONG AND THEY ARE NOT FOUR SENTENCES**, deliberately:

      * **no answer** — the provider was asked and said nothing, so whether the
        money moved is unknown. `503`, and the screen says so; `US-CWP-004`
        TC-7 is that *"a zero is a claim nobody can make"*, and nothing here
        turns *we do not know* into a receipt OR into a refusal.
      * **declined** — the provider answered and refused. A DIFFERENT sentence
        from the one above and that is `BR-INT-018` in practice: telling
        somebody *the card service did not answer* would send them to press
        again against a card that will refuse again.
      * **held** — no processor is connected, or the account is under
        `BR-PAY-013`'s cash-only sanction. ⚠ **ONE SENTENCE FOR BOTH, AND IT IS
        A DISCLOSURE DECISION RATHER THAN A SHORTCUT.** The second reason is a
        fact about the CUSTOMER — a sanction applied after bounced payments —
        and `BR-CWP-021` does not let a stranger holding the paper be told
        anything about the person. The specific code stays on the exception,
        for the log.
      * **no such bill** — answered with step 1's own sentence, byte-identical,
        because `US-CWP-003` TC-2 is that *"a different message would confirm
        the bill number exists"* and that stays true at step 2.

    ⚠ **`br_ref` IS THE NEUTRAL ONE ON A HELD REFUSAL.** It rides on the wire
    (the `G1` envelope carries all six keys), so a `BR-PAY-013` there would
    disclose in a machine field exactly what the sentence above is careful not
    to say. `BR-CWP-056` — *a control that may not be used is refused with its
    reason* — is true of both and discloses neither.
    """
    gateway = _rails()

    refused_type = getattr(gateway, "GuestChargeRefused", None)
    if refused_type is None or not isinstance(failure, refused_type):
        return None

    outcome = getattr(failure, "outcome", None)
    if outcome == gateway.NO_ANSWER:
        return errors.SysError(
            errors.SYS_PROVIDER,
            message_key="portal.quickPay.providerSilent",
            params={"detail": gateway.NO_ANSWER},
        )
    if outcome == gateway.DECLINED:
        return errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-INT-018",
            message_key="portal.quickPay.declined",
        )
    if outcome == gateway.NO_BILL:
        return errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-019",
            message_key="portal.quickPay.notFound",
        )
    if outcome == gateway.NOT_RECORDED:
        # ⛔ **OURS, NOT THEIRS — SO IT IS A 500 AND NOT A 503.** The provider
        # approved and we could not write the payment down. Saying *the card
        # service did not answer* would blame the one part of this that worked
        # and would send the person to press again against money already taken.
        return errors.SysError(
            errors.SYS_INTERNAL,
            message_key="portal.quickPay.notRecorded",
            params={"detail": gateway.NOT_RECORDED},
        )
    return errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-CWP-056",
        message_key="portal.quickPay.cannotPayHere",
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def bill_pay(request: Any, number: str) -> Response:
    """`POST /portal/public/bills/{number}/pay` — `CWP-003`'s commit and
    `CWP-004`'s answer (`07-endpoints.md` §1 row 3).

    **`{number}` IS THE BILL NUMBER OFF THE PAPER**, `BL-2608-0141`, and never a
    row id — B14 rule 31, and the only thing the person holding the bill has.

    **SIX GUARDS, IN THIS ORDER, AND THE ORDER IS THE SECURITY STORY:**

      1. the tenant, resolved from the first path segment before anything is
         read (`BR-CWP-005`) — which is what makes `US-CWP-004` TC-5 a refusal
         *before any customer row is read*;
      2. quick pay switched on for this utility (`BR-CWP-002` — a screen that
         merely does not draw the door is defeated by calling the door);
      3. no unpriced surcharge (`OQ-1394`, above);
      4. the lockout, on `FORM_QUICK_PAY` — **the same door as step 1**;
      5. the pair, re-proved through the same selector, burning a try on a miss
         and answering step 1's one sentence;
      6. the bill is actually payable, for the figure the person agreed to.

    ⚠ **NOTHING HERE WRITES A ROW.** The edge resolves, validates, calls ONE
    function and answers; the payment, its allocation, its balanced pair, its
    audit row and its receipt are `payments`' own, through the write point
    `write_points.py` declares for `kind="payment"` (`BR-CWP-001`). `G81` reads
    this file every run and fails it for an ORM write of its own.

    ⚠ **AN UNKNOWN OUTCOME IS NOT A RESULT** (`US-CWP-004` TC-7). A gateway that
    times out travels as a provider failure and the screen says so; nothing here
    turns *"we do not know"* into a receipt, because *"a zero is a claim nobody
    can make"* — and nothing here retries, because a retry on this path is the
    one place in the product that could take a payment twice.
    """
    tenant_id = require_tenant(request)
    _quick_pay_is_on(tenant_id)
    _no_surcharge_is_lawful_here(tenant_id)
    body = request.data if isinstance(request.data, dict) else {}
    lock_tenant = _lock_key_tenant(tenant_id)
    address = lockout.address_of(request)

    if lockout.is_locked(lock_tenant, lockout.FORM_QUICK_PAY, address):
        raise errors.BizError(
            errors.BIZ_LOCKED,
            br_ref="BR-CWP-023",
            message_key="portal.quickPay.locked",
            params={"minutes": lockout.LOCK_SECONDS // 60},
        )

    instrument = _instrument(body)

    # ⚠ THE PAIR AGAIN, THROUGH THE SAME SELECTOR AND THE SAME COUNTER. The
    # refusal below is byte-identical to `bill_lookup`'s, deliberately.
    found = selectors.bill_lookup(tenant_id, bill_number=number, postcode=body.get("postcode"))
    if found is None:
        lockout.record_wrong(lock_tenant, lockout.FORM_QUICK_PAY, address)
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-019",
            message_key="portal.quickPay.notFound",
        )
    lockout.clear(lock_tenant, lockout.FORM_QUICK_PAY, address)

    # Imported at the call, the idiom every seam in this package uses (`G81`).
    from apps.portal.seams import payments_seam

    attempt_key = _attempt_key(tenant_id, found["number"], body.get("attempt_token"))

    # ═══════════════════════════════════════════════════════════════════════
    # ⚠ **GUARD 5½ — THE ATTEMPT KEY IS LOOKED UP BEFORE THE PAYABILITY
    # RE-READ, AND THE ORDER IS THE WHOLE FIX** (`DEF-CWP-3950`).
    # ═══════════════════════════════════════════════════════════════════════
    # A guest pays `$142.18`, the payment commits, THE RESPONSE IS LOST, and
    # the browser resends the same request. Hard rule 6 was already satisfied
    # and stayed satisfied — the rails collapse both onto one payment — but the
    # retry never got that far: it stopped one line below, at `BR-CWP-058`,
    # because the bill it names is now settled. **The person was told "There is
    # nothing to pay" about the payment they had just made.** That is the worst
    # available wrong answer on a money path: it reads as *your money did not
    # arrive*, and the obvious thing to do about it is to pay again.
    #
    # ⚠ **EVERY CHECK IN THIS REPO ASKED HOW MANY PAYMENTS EXIST; NONE ASKED
    # WHAT THE PERSON SEES.** One payment, every way in — asserted by
    # `test_two_attempts_in_flight_at_once_settle_onto_one_payment`. The RECORD
    # was never wrong. The RESPONSE was.
    #
    # ⚠ **IT SITS AFTER GUARDS 1–5 AND NOT BEFORE THEM.** The pair has been
    # re-proved and the lockout cleared by the time this runs, so replaying a
    # receipt still costs a caller the bill number AND the postcode AND the
    # attempt token from that browser's own visit. Moving it any earlier would
    # turn `attempt_token` into a way of asking whether a payment exists.
    #
    # ⚠ **AND IT IS BEFORE THE AMOUNT CHECK TOO**, which is the same trap one
    # line further on: after a successful payment what is owed has MOVED, so a
    # retry would be refused with *"the amount has changed"* — a different
    # sentence and the same lie.
    already = payments_seam.settled_guest_charge(idempotency_key=attempt_key)
    if already is not None:
        return Response(
            selectors.guest_payment_receipt(
                {
                    **already,
                    # The card is the retry's own — the same request, the same
                    # instrument — so nothing is guessed and no stored card
                    # fact is read back.
                    "method_brand": instrument.get("brand"),
                    "method_last_four": instrument.get("last_four"),
                    # `BR-NOT-013` — nothing dispatches in this release, and a
                    # replay does not change that. FALSE here for the same
                    # reason it is FALSE on the original.
                    "receipt_sent": False,
                },
                bill_number=found["number"],
            ),
            # ⚠ **200 AND NOT 201.** Nothing was created: this is the receipt
            # for a payment that already existed. A 201 would tell a caller —
            # and any log reading status codes — that a second payment was
            # taken, which is the very thing that did not happen.
            status=200,
        )

    if found["status"] != selectors.BILL_PAYABLE:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-042",
            message_key="portal.quickPay.notPayable",
            params={"state": found["status"]},
        )

    owing = found["amount"]["amount"]
    if _squashed_money(body.get("amount")) != _squashed_money(owing):
        # `BR-CWP-058` — what the person agreed to is not what is owed now.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-058",
            message_key="portal.quickPay.amountMoved",
        )

    # ⚠ **THE RECEIPT ADDRESS IS NOT READ OFF THIS BODY** (`DEF-CWP-3951`).
    # It used to be: accepted, validated, handed to the rails — and DROPPED.
    # `record_payment` does queue a receipt, but to the ACCOUNT's own contacts
    # under the tenant's election, which is a different address; and
    # `BR-NOT-013` means nothing dispatches in this release at all. So the form
    # was collecting something the product never reads, under the sentence
    # *"Optional. We use it only for this receipt."* — a guarantee this product
    # does not provide, in a customer's own words (hard-won law 1).
    #
    # ⚠ **THE OTHER FIX NEEDS A RULING AND THIS ONE DOES NOT.** Writing an
    # unverified address supplied by an ANONYMOUS caller into a notification
    # row against somebody else's account is a disclosure decision and a
    # spam-relay surface — `US-CWP-004` §4 is explicit that a guest may be a
    # NEIGHBOUR — so it is not a lane's edit. Until it is ruled, the honest
    # thing is not to ask, and the form no longer does.
    #
    # ⚠ **THE PARAMETER STAYS ON THE RAILS AND THAT IS DELIBERATE.**
    # `charge_guest_bill(receipt_email=…)` is the door the address goes through
    # the day dispatch arrives; removing it would mean rebuilding it. What
    # changes is that this edge passes `None` rather than a stranger's typing.
    # `tests/test_def_cwp_3951_the_receipt_address_goes_nowhere.py` fires when
    # the hold expires.

    gateway = _rails()

    try:
        charged = gateway.charge_guest_bill(
            tenant_id,
            bill_number=found["number"],
            amount=owing,
            currency=found["amount"]["currency"],
            instrument=instrument,
            receipt_email=None,
            channel=CHANNEL_CUSTOMER_PORTAL,
            paid_by=GUEST_PAID_BY,
            # ⚠ THE SAME KEY GUARD 5½ LOOKED UP, computed ONCE above. Two
            # calls to `_attempt_key` would be two chances to compute it
            # differently, on the one path in the product that could take a
            # payment twice.
            idempotency_key=attempt_key,
        )
    except errors.ApiError:
        raise
    except Exception as failure:  # noqa: BLE001 — the outcome is UNKNOWN, see below
        # ⚠ **THE RAILS SAY WHAT HAPPENED; THIS SAYS WHAT THE PERSON READS.**
        # `apps/payments` carries no customer sentence — eleven catalogues write
        # those (B14 rule 35) — so what crosses the boundary is an outcome CODE
        # and the key is chosen here.
        #
        # ⚠ **THE TYPE IS TESTED INSIDE THE HANDLER AND NEVER NAMED IN THE
        # `except` CLAUSE.** `except gateway.GuestChargeRefused` looks tidier and
        # is a live 500 on this edge: the clause is an ATTRIBUTE LOOKUP evaluated
        # at exception time, so any build or fixture where the rails module does
        # not carry that name turns a handled refusal into an unhandled
        # `AttributeError`. It was found exactly that way — `US-CWP-004` TC-7
        # answered **500** instead of 503 the moment the clause was written.
        # Everything unrecognised keeps the answer it always had.
        refusal = _refusal_for(failure)
        if refusal is not None:
            raise refusal from failure
        raise errors.SysError(
            errors.SYS_PROVIDER,
            message_key="portal.quickPay.providerSilent",
            params={"detail": type(failure).__name__},
        ) from failure

    return Response(
        selectors.guest_payment_receipt(charged, bill_number=found["number"]), status=201
    )


urlpatterns += [
    # CR-068 wave R — `07-endpoints.md` §1 row 3, which read *"BLOCKED — no
    # rails"* until the gateway was built. ⚠ The `{ref}` of that row is the BILL
    # NUMBER, not a payment reference and not a row id (B14 rule 31): it is the
    # thing printed on the paper somebody is holding.
    path("portal/public/bills/<str:number>/pay", bill_pay),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-001@87b94265 (EP-CWP-01 story + BR-CWP-001..028 snapshot)
# generated: 2026-09-03 by the CR-068 wave A build lane
# checklist: A✔ B✔ C✔ D✔ E✔(portal/guest/FrontPage.tsx consumes this) F✔ G✔ H=n/a(read route; no 🔒 path)
# gates: pytest tests/test_us_cwp_001_front.py · openapi export re-run (one new path) · G81 (no write in this file) · G9 error envelope
# exceptions: the other eleven guest routes of 07-endpoints.md §1 belong to waves C, D and P — stated so their absence is a plan and not a gap · ⚠ THIS LINE SAID "`POST /public/track` does not yet reach the `PAY-` series" AND SINCE 7ac5d92c THAT IS THE OPPOSITE OF THE TRUTH (corrected 2026-09-05, handed over by the lane that changed it): `selectors.TRACKABLE_SERIES` is `("request", "payment")`, so a guest can look a payment up by its reference and postcode. A hold expires the day the thing it was waiting for lands, and releasing it is a SECOND act that only the first one feels like work — hard-won law 2's mirror, and the reason this correction is written out rather than deleted
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
