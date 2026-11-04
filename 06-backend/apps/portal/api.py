# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-016 · US-CWP-017 · US-CWP-018 · US-CWP-019 · US-CWP-020 ·
#           US-CWP-021 (🔒) · US-CWP-023 · US-CWP-024 (EP-CWP-03/04)
#           Screens: CWP-015 · CWP-016 · CWP-017 · CWP-018 · CWP-019 · CWP-022
# Rules:    BR-CWP-011 (a SEPARATE FILE and a separate middleware from the
#           guest edge and from the staff app) · BR-CWP-005 (tenant from the
#           path first) · BR-CWP-010 (every query filtered on BOTH halves —
#           tenant and account set — IN THE QUERY, never in the screen) ·
#           BR-CWP-032 (matched discloses nothing) · BR-CWP-033/034 (the code
#           goes only to a stored contact; no contact dead-ends) · BR-CWP-036
#           (three tries) · BR-CWP-038 (identical reset responses) ·
#           BR-CWP-047 (never cached)
# Tests:    06-backend/tests/test_us_cwp_016_find_account.py ·
#           _017_prove_it.py · _018_password.py · _019_forgotten.py ·
#           _020_session.py · _023_account_set.py · _024_balance.py ·
#           _021_pg.py (PostgreSQL)
# Impacts:  config/urls.py (the third portal include) ·
#           07-frontend/src/portal/api/portalClient.ts
# ───────────────────────────────────────────────────────
"""THE SIGNED-IN CUSTOMER'S EDGE. Eleven routes in wave E.

Mounted at `/api/{tenant}/portal/…`. **A separate file, a separate
authentication class and a separate cookie from both other edges**
(`BR-CWP-011`); `07-endpoints.md` says why in one sentence — *"One router with
a per-route check is one missing decorator away from a customer reading the
staff API."*

⚠ **THE FOUR ENROLMENT ROUTES ARE UNAUTHENTICATED AND THAT IS NOT A HOLE.**
`find-account`, `verify-code`, `set-password` and the two reset routes are how
somebody who has never signed in gets a login; they carry
`authentication_classes([])` for the same reason the guest edge does — **a
stale staff cookie must not 401 a visitor and must not enter any context** —
and each is guarded by what it actually needs: the enrolment lockout
(`BR-CWP-036`), a proven one-time code, or a single-use link.

⚠ **`set-password` IS GUARDED ON THE ENDPOINT AND NOT ON THE WIZARD**
(`US-CWP-019` TC-4). Posting straight to it without a consumed code for that
account is refused, so a screen order is not the security.

WHAT IS DELIBERATELY NOT HERE
-----------------------------
* **No `GET` on any of the four enrolment routes.** They are all `POST`, so a
  matched account cannot end up in a browser history or a proxy log.
* **No route that takes an account id from the body and trusts it.** Every
  account-scoped read below intersects the id with `request.user.account_ids`
  IN THE QUERY (`BR-CWP-010`); an id outside the set answers 404 — the same
  body an id that does not exist gets, so the set cannot be enumerated.
* **No `Cache-Control` that would let a balance be stored** (`BR-CWP-047`).
  Every response from the two balance routes carries `no-store`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.conf import settings
from django.http import HttpResponse
from django.urls import path
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.customers import models as customers_models
from apps.portal import (
    credentials,
    lockout,
    models,
    paging,
    paying,
    premises_statement,
    selectors,
    services,
    session as portal_session,
)
from apps.portal.guards import (
    PortalSignedInThrottle,
    PortalTenantThrottle,
    portal_admission,
)
from apps.portal.seams import customers_seam, metering_seam, payments_seam
from apps.tenancy.api import PublicOnboardingThrottle
from core import errors
from core.tenancy import require_tenant

#: ⚠ **ONE REFUSAL SENTENCE FOR THREE DIFFERENT FAILURES, AND THAT IS THE
#: FEATURE** (`BR-CWP-032`, `BR-CWP-038`). An unknown account number, a wrong
#: surname and a postcode that does not match the service address are all
#: `not_matched`. A code the caller reads back is a message KEY, never a
#: sentence: eleven catalogues write the sentence in their own language
#: (B14 rule 35) and each is five or six words (rule 33).
NOT_MATCHED = "not_matched"
LOCKED = "locked"


def _no_store(response: Response) -> Response:
    """`BR-CWP-047` — *"no portal screen caches a balance or a credit"*, said to
    the browser as well as honoured on the server. A credit that was real on
    Tuesday can be spent by Thursday."""
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    return response


def _principal(request: Any):
    return getattr(request, "user", None)


def _account_in_set(request: Any, account_id: Any):
    """The account, **intersected with the session's set in the query**, or a 404.

    ⚠ **`BR-CWP-010` LIVES IN THIS FUNCTION AND NOWHERE ELSE ON THIS EDGE.**
    Both halves are in the `filter`: `tenant_id` and `pk__in=<the set>`. An id
    belonging to another customer of the same utility, and an id belonging to
    no account at all, produce the SAME 404 — so a landlord cannot ask whether
    a particular account exists by watching which refusal comes back
    (`US-CWP-026`'s step 3, proved a wave early because the read is here).
    """
    principal = _principal(request)
    ids = list(getattr(principal, "account_ids", ()) or ())
    row = customers_models.Account.objects.filter(
        tenant_id=principal.tenant_id, pk__in=ids, pk=account_id
    ).first()
    if row is None:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    return row


def _scope(request: Any) -> list[Any]:
    """The accounts a whole-set list runs over: the session's set, or the ONE
    the switcher names.

    ⚠ **THIS IS WHAT MAKES THE SWITCHER RE-SCOPE A TAB** (`BR-CWP-010`,
    `US-CWP-023` TC-2). `GET bills` and `GET payments` were written against the
    whole set and took no account, so a landlord who chose *22 Palm Ct* in the
    header went on reading four accounts' bills underneath it — a screen and
    its own header disagreeing about which account is being read, which is the
    one thing `US-CWP-023` exists to prevent.

    ⚠ **THE PARAMETER IS OPTIONAL AND ITS ABSENCE IS THE OLD BEHAVIOUR**, so
    nothing already calling these two routes changes. `CWP-022` (home) and
    `CWP-023` (all my accounts) deliberately do NOT pass it: those two are the
    whole set BY DEFINITION — four rows and a total that is information and
    never an invoice (`BR-CWP-015`).

    ⚠ **THE GUARD IS `_account_in_set`, NOT THIS FUNCTION.** An id outside the
    session's set answers the same 404 as an id that does not exist, in the
    query, because it goes through the one place `BR-CWP-010` lives
    (`US-CWP-023` TC-3: *the switcher is a convenience; the guard is the
    query*).
    """
    principal = _principal(request)
    named = request.query_params.get("account_id")
    if not named:
        return list(principal.account_ids)
    return [_account_in_set(request, named).pk]


# ═══════════════════════════════════════════════════════════════════════════
# 1 · Enrolment — the four unauthenticated routes (07-endpoints.md §2)
# ═══════════════════════════════════════════════════════════════════════════


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def find_account(request: Any) -> Response:
    """`POST enrol/find-account` — matched or not matched, **and nothing else**.

    `BR-CWP-030`'s three facts, all printed on the paper bill: account number,
    the postcode of the SERVICE address, and last name or company name.
    `BR-CWP-031`: never date of birth, never the last four of an SSN — there is
    no field for either and there must never be.

    ⚠ **THE BODY CARRIES NO NAME, NO BALANCE AND NO ADDRESS** (`BR-CWP-032`).
    Between *matched* and *proven* the portal knows which account is meant and
    has told the visitor nothing. What it returns on a match is a masked
    destination — *"we sent it to ••• ••• 4218"* — which is the least that lets
    a person know which phone to pick up.

    ⚠ **AN ALREADY-ENROLLED ACCOUNT IS ROUTED TO RESET WITHOUT CONFIRMING A
    LOGIN EXISTS.** `already_enrolled` is true, `matched` is false, and the
    reason is `use_reset` — the same route a person with no login would be
    offered if they asked for one. Answering *"this account already has a
    login"* would make this form a register of who banks online.
    """
    tenant_id = require_tenant(request)
    address = lockout.address_of(request)
    if credentials.enrolment_locked(tenant_id, address):
        return Response({"matched": False, "reason": LOCKED})

    body = request.data if isinstance(request.data, dict) else {}
    account = credentials.find_account(
        tenant_id,
        account_no=body.get("account_number"),
        postcode=body.get("postcode"),
        name=body.get("last_name"),
    )
    if account is None:
        tries = credentials.record_enrolment_miss(tenant_id, address)
        return Response(
            {
                "matched": False,
                "reason": LOCKED if tries >= models.ENROLMENT_MAX_TRIES else NOT_MATCHED,
            }
        )
    if credentials.already_enrolled(tenant_id, account):
        return Response({"matched": False, "reason": "use_reset"})

    channel, destination, masked = credentials.contact_for(tenant_id, account)
    if channel is None:
        # BR-CWP-034 — the dead end, by name. It must NEVER fall back to
        # something weaker, so there is no branch below this one.
        return Response({"matched": True, "reason": "no_contact_on_file", "account_ref": None})

    issued = credentials.issue_code(
        tenant_id,
        purpose=models.PURPOSE_ENROL,
        account=account,
        channel=channel,
        masked=masked,
    )
    credentials.queue_code(tenant_id, account=account, issued=issued, destination=destination)
    credentials.clear_enrolment(tenant_id, address)
    return Response(
        {
            "matched": True,
            #: ⚠ The one-time code row's id, NOT the account's. It is the
            #: capability the next screen presents and it dies with the code —
            #: an account id here would be an account id in a browser and B14
            #: rule 31's reason applies to a wire as well as to a field.
            "account_ref": issued.row_id,
            "sent_to": masked,
            "channel": channel,
            "expires_in_minutes": models.CODE_TTL_MINUTES,
        }
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def verify_code(request: Any) -> Response:
    """`POST enrol/verify-code` — ten minutes, single use, six wrong tries.

    Answers one of `ok`, `wrong`, `expired`, `locked`. **`expired` is its own
    answer** (`BR-CWP-035`): a person who waited eleven minutes is offered a
    resend, not sent round the loop guessing at a code that was right.
    """
    tenant_id = require_tenant(request)
    body = request.data if isinstance(request.data, dict) else {}
    row = credentials.code_row(tenant_id, body.get("account_ref"))
    if row is None or row.account_id is None:
        return Response({"result": credentials.CODE_WRONG})
    verdict = credentials.verify_code(
        tenant_id,
        purpose=models.PURPOSE_ENROL,
        code=body.get("code"),
        account=row.account,
    )
    return Response({"result": verdict})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def enrol_consequences(request: Any) -> Response:
    """`POST enrol/consequences` — what `CWP-018`'s consequence panel states.

    ⚠ **THE FIRST SCREEN IN THE FLOW THAT MAY SHOW A BALANCE** (`BR-CWP-039`,
    `08-screen-layouts.md` `CWP-018`), and it may only because the code has
    already been consumed — the person has proved they hold the contact on
    file. Called with a code row whose `consumed_at` is set and nothing else;
    an unconsumed ref answers 404, so the panel cannot be fetched by somebody
    who merely matched the account.

    ⚠ **NOT ONE OF THE SEVEN AUTH ENDPOINTS** — it is the read behind the panel
    `BR-CWP-039` mandates, and it is written down here rather than folded into
    `verify-code`'s body so that the disclosure has its own guard and its own
    test (`US-CWP-018` TC-5).
    """
    tenant_id = require_tenant(request)
    body = request.data if isinstance(request.data, dict) else {}
    row = credentials.code_row(tenant_id, body.get("account_ref"))
    if row is None or row.consumed_at is None or row.account_id is None:
        raise errors.deny_as_not_found(br_ref="BR-CWP-032")
    account = row.account
    balance = payments_seam.account_balance(account.pk)
    return _no_store(
        Response(
            {
                "account_no": account.account_no,
                "service_address": _service_address(account),
                "services": _services_of(account),
                "balance": balance["owing"],
                "currency": balance["currency"],
                "policy_min_length": credentials.check_password_policy(tenant_id, "").min_length,
                #: What the new login CANNOT do. Served as keys so each of the
                #: eleven catalogues writes its own sentence (B14 rule 35).
                "cannot": ["close_account", "change_owner", "move_out"],
            }
        )
    )


#: ⚠ **MOVED TO `selectors.py` BY WAVE F — hard rule 8 wants ONE place that
#: composes a service address, and two files walking to `premises` themselves
#: is how a retired column silently emptied an account header (`DEF-CUS-3653`).
#: The names stay so the three call sites below read the same; the walk does
#: not live here any more.
_service_address = selectors.service_address
_services_of = selectors.services_of


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def set_password(request: Any) -> Response:
    """`POST enrol/set-password` — creates the credential and signs the person in.

    ⚠ **GUARDED HERE AND NOT IN THE WIZARD** (`US-CWP-019` TC-4). The guard is
    a CONSUMED enrolment code for this account: post straight to this route
    with no code and it 404s. A screen order is not a security control.

    Refuses a password the TENANT's own policy refuses (`BR-CWP-037`) — eight
    characters on a tenant whose `pw_min_length` is twelve — and answers with
    the failed rules as keys plus the number, so the helper line under the
    field states the utility's own minimum rather than a constant.
    """
    tenant_id = require_tenant(request)
    body = request.data if isinstance(request.data, dict) else {}
    row = credentials.code_row(tenant_id, body.get("account_ref"))
    if row is None or row.consumed_at is None or row.account_id is None:
        raise errors.deny_as_not_found(br_ref="BR-CWP-032")

    verdict = credentials.check_password_policy(tenant_id, body.get("password") or "")
    if not verdict.ok:
        return Response(
            {"ok": False, "failures": list(verdict.failures), "min_length": verdict.min_length},
            status=422,
        )
    email = credentials.normalise_email(body.get("email"))
    if not email or credentials.credential_by_email(tenant_id, email) is not None:
        return Response({"ok": False, "failures": ["email_unavailable"]}, status=422)

    credential = credentials.create_credential(
        tenant_id,
        account=row.account,
        email=email,
        password=body.get("password"),
        otp_channel=body.get("otp_channel") or models.CHANNEL_SMS,
    )
    return _sign_in_response(tenant_id, credential)


# ═══════════════════════════════════════════════════════════════════════════
# 2 · Sign in, sign out, reset (07-endpoints.md §2 — the other three)
# ═══════════════════════════════════════════════════════════════════════════


def _sign_in_response(tenant_id: Any, credential: Any) -> Response:
    row = portal_session.issue(tenant_id, credential)
    response = Response({"ok": True, "session": {"issued_at": row.issued_at.isoformat()}})
    # CR-144-BRC07 (X3) — `Secure`. Same one setting as the two staff
    # sign-in cookies; see apps/identity/api.py. ⚠ The portal cookie NAME
    # does not move either — renaming it signs out every customer at once.
    # ⚠ **`CR-145-BRC08` — THE EXPIRY IS STATED, AND FOR THIS COOKIE IT IS
    # `None`.** All three `set_cookie` calls in this product passed no expiry
    # at all until 2026-09-28, which is a browser-session cookie. For the two
    # STAFF cookies that was a live bug — it killed *"Keep me signed in"* when
    # the browser closed — and they now pass
    # `apps/identity/auth.session_cookie_max_age`.
    #
    # **This one is different and stays a browser-session cookie.** The portal
    # has no *"Keep me signed in"* tick box and `portal_session` carries no
    # `persistent` column to hold the answer, so there is no setting to read
    # and nothing for `max_age` to be. `keep_signed_in_days` is a STAFF
    # setting; applying it here would keep a customer signed in on a shared or
    # public machine for up to a month on a choice they were never offered.
    #
    # ⚠ **IT IS WRITTEN OUT RATHER THAN OMITTED**, because an absent argument
    # and a deliberate `None` render identically in the response and read very
    # differently in the source — which is precisely how the staff bug
    # survived: nobody could tell the missing expiry from a chosen one.
    #
    # ⚠ **AND THE PORTAL'S HARD LIMIT IS STILL THE UTILITY'S** — that half of
    # `CR-145` is `portal/session.issue()`, through the declared seam. The
    # session row expires when the utility says; the cookie naming it lives
    # until the browser closes.
    response.set_cookie(
        portal_session.PORTAL_SESSION_COOKIE,
        str(row.pk),
        max_age=None,
        httponly=True,
        samesite="Lax",
        secure=settings.AUTH_COOKIE_SECURE,
    )
    return _no_store(response)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def sign_in(request: Any) -> Response:
    """`POST auth/sign-in`. **A staff email and password get the ordinary failure.**

    There is no branch in this view or in `credentials.sign_in` that consults
    `identity`. Pine Hill's System Admin types their office credentials and the
    answer is `wrong`, because `portal_credential` has never heard of them —
    and **no session row is written**, which is what `US-CWP-020` TC-1 asserts.
    """
    tenant_id = require_tenant(request)
    body = request.data if isinstance(request.data, dict) else {}
    verdict, credential = credentials.sign_in(
        tenant_id, email=body.get("email"), password=body.get("password")
    )
    if verdict != credentials.SIGN_IN_OK or credential is None:
        return Response({"ok": False, "reason": verdict}, status=401)
    return _sign_in_response(tenant_id, credential)


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def sign_out(request: Any) -> Response:
    """`POST auth/sign-out` — this device only."""
    row = getattr(request, "auth", None)
    if row is not None:
        portal_session.revoke(row)
    response = Response({"ok": True})
    response.delete_cookie(portal_session.PORTAL_SESSION_COOKIE)
    return response


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def revoke_all_sessions(request: Any) -> Response:
    """`POST sessions/revoke-all` — *sign out everywhere* (`CWP-024`)."""
    principal = _principal(request)
    count = portal_session.revoke_all(principal.tenant_id, principal.credential_id)
    response = Response({"ok": True, "revoked": count})
    response.delete_cookie(portal_session.PORTAL_SESSION_COOKIE)
    return response


#: ⚠ **ONE OBJECT, BUILT ONCE, RETURNED BY BOTH RESET BRANCHES.** `BR-CWP-038`
#: says the response is the SAME whether or not the address has a login, and
#: the surest way to keep two bodies byte-identical is for there to be one
#: body. `US-CWP-019` TC-2 compares them as strings.
_RESET_ANSWER: dict[str, Any] = {"ok": True, "reason": "check_your_email"}


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def forgot_password(request: Any) -> Response:
    """`POST auth/forgot-password` — **the same body, the same timing, either way**.

    ⚠ **THE STAFF STORE IS NOT CONSULTED** (`BR-CWP-038`), so a staff address
    typed here cannot be distinguished from any other unknown address. If it
    were consulted, this endpoint would answer *"is this address a member of
    staff at this utility?"* to anybody who asked.

    ⚠ **AND NO EMAIL IS QUEUED FOR AN ADDRESS WITH NO LOGIN** — the response is
    identical, the side effect is not. `US-CWP-019` TC-3 asserts the outbound
    queue is unchanged for the unknown address, which is the half a byte
    comparison cannot see.
    """
    tenant_id = require_tenant(request)
    body = request.data if isinstance(request.data, dict) else {}
    # ⚠ **`DEF-CWP-10380` — A BLANK OR MALFORMED ADDRESS IS REFUSED, AND THAT
    # DISCLOSES NOTHING.** `BR-CWP-038`'s one answer is about an ADDRESS: whether
    # one has a login. A blank box or `not-an-email` is not an address, so the
    # 400 depends only on what was typed — never on what is stored — and the
    # stored set is not read before it. The reason is a KEY (B14 rule 35).
    refused = credentials.email_refusal(body.get("email"))
    if refused is not None:
        return Response(
            {"ok": False, "reason": refused, "message_key": f"portal.reset.{refused}"},
            status=400,
        )
    credential = credentials.credential_by_email(tenant_id, body.get("email"))
    if credential is None:
        return _reset_answer_for_unknown_address()
    credentials.send_reset(tenant_id, credential=credential)
    return Response(dict(_RESET_ANSWER))


def _reset_answer_for_unknown_address() -> Response:
    """What a WELL-FORMED address with no login gets — today `BR-CWP-038`'s
    identical answer, the same timing, and NO side effect.

    ⚠ **ONE SMALL PLACE ON PURPOSE.** The PO is reconsidering this answer
    (2026-10-22: a message asking the customer to have their registered email
    updated, instead of the identical *check your inbox*). Until that ruling
    lands nothing here changes; when it does, this function and `US-CWP-019`
    TC-2's byte comparison are the two things that move.
    """
    credentials.equalise_timing()
    return Response(dict(_RESET_ANSWER))


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def reset_password(request: Any) -> Response:
    """`POST auth/reset-password` — a seven-day, single-use link.

    Single use is `consumed_at`; seven days is `expires_at`. A used link and an
    expired one both answer `wrong`, because telling somebody holding a stale
    link WHICH of the two it was tells them a live link once existed.
    """
    tenant_id = require_tenant(request)
    body = request.data if isinstance(request.data, dict) else {}
    row = credentials.code_row(tenant_id, body.get("ref"))
    if row is None or row.portal_credential_id is None or row.purpose != models.PURPOSE_RESET:
        return _reset_refused(credentials.CODE_WRONG)
    # ⚠ **THE POLICY IS CHECKED BEFORE THE LINK IS SPENT (`DEF-CWP-10381`).**
    # `verify_code` CONSUMES the code on a match, and this view used to call it
    # first — so a customer whose new password was one character short lost
    # their link along with the refusal, and had to ask for another email. The
    # tenant's policy is no secret (the screen prints its minimum), so reading
    # it before the token is checked discloses nothing.
    policy = credentials.check_password_policy(tenant_id, body.get("password") or "")
    if not policy.ok:
        return Response(
            {
                "ok": False,
                "failures": list(policy.failures),
                "min_length": policy.min_length,
                # The client's refusal envelope reads `message_key`/`params`
                # (`api/client.ts` `asEnvelope`); without them a 422 body
                # reaches the screen as *something went wrong*.
                "message_key": "portal.reset.policy",
                "params": {"failures": list(policy.failures), "min_length": policy.min_length},
            },
            status=422,
        )
    verdict = credentials.verify_code(
        tenant_id,
        purpose=models.PURPOSE_RESET,
        code=body.get("token"),
        credential=row.portal_credential,
    )
    if verdict != credentials.CODE_OK:
        return _reset_refused(verdict)
    credentials.set_password(row.portal_credential, body.get("password"))
    return Response({"ok": True})


def _reset_refused(verdict: str) -> Response:
    """A link that cannot be used. `expired` and `locked` keep their own words;
    a used, unknown or foreign link is `wrong` (see the docstring above)."""
    return Response(
        {"ok": False, "reason": verdict, "message_key": f"portal.reset.link.{verdict}"},
        status=422,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3 · Session and the account set · 4 · Balance
# ═══════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def session_view(request: Any) -> Response:
    """`GET session` — who is signed in, and the shell's own facts.

    ⚠ **THE SWITCHER IS A LABEL WHEN THE SET HAS ONE ENTRY** and the SERVER
    says which (`09-component-inventory.md` §1): `account_count` is the fact,
    and the screen draws a `<select>` or a label from it rather than each
    screen deciding. B14 rule 31 — the visible value is the address, never an id.

    ⚠ **`language` IS SERVED HERE AND ON NO GUEST ROUTE, AND THAT IS THE WHOLE
    REASON IT IS ON THIS PAYLOAD** (`DEF-CWP-4440`, `BR-CWP-105`). **PO ruling
    2026-09-07, verbatim:** *"a signed-in customer will get their account's own
    preferred language - Signed customer should get their own references."* The
    TENANT's language rides on `GET portal/public/front` because the guest half
    has no other payload; the CUSTOMER's own language cannot follow it there.
    That route is `authentication_classes([])` — anyone on the internet may
    call it with a tenant slug — and *the account at this address prefers
    Spanish* is a fact about a person (`BR-CWP-021`, never a person on the
    guest surface). So the two travel through different doors on purpose, and
    the front end applies whichever it holds in `BR-CWP-105`'s order.

    ⚠ **THE VALUE IS `selectors.account_language`, WHICH IS THE FUNCTION THAT
    ALREADY OPENS THE PICKER ON `CWP-024`** — one fold over
    `accounts.preferred_language`, not two. A second one written for the shell
    is precisely how the language a customer CHOOSES and the language they READ
    would drift apart (hard-won law 5). It answers `None` when the login's
    accounts disagree, and the chain then falls to the utility's own setting
    rather than to whichever of four an ordering happened to put first.

    ⚠ **IT IS NOT A FOURTH QUERY DRESSED AS A FIELD:** `account_language` is
    one indexed `values_list(... ).distinct()` over the session's own account
    ids, which is the same set `_account_rows` below is already reading — the
    endpoint goes from two reads to three, asserted in
    `tests/test_def_cwp_4440_portal_language.py` so a fourth is a red test.
    """
    principal = _principal(request)
    return _no_store(
        Response(
            {
                "customer": {"display_name": _display_name(principal)},
                "accounts": _account_rows(principal),
                "account_count": len(principal.accounts),
                "language": selectors.account_language(principal),
            }
        )
    )


def _display_name(principal: Any) -> str | None:
    row = (
        customers_models.Customer.objects.filter(
            tenant_id=principal.tenant_id, pk=principal.customer_id
        )
        .only("display_name")
        .first()
    )
    return getattr(row, "display_name", None)


def _account_rows(principal: Any) -> list[dict[str, Any]]:
    """The set, FLAT (`BR-CWP-013`), each entry carrying what it may be used for.

    ⚠ **A MASTER ACCOUNT IS ONE MORE ENTRY.** There is no `children` key here
    and there must never be: `BR-CWP-014` says what makes a master different is
    that it is BILLED TO THE LANDLORD, which is a billing fact, not a permission.
    `is_master` is served so the row can read *Billed to you as owner*.

    ⚠ **`is_master` READS `kind`, AND READ A PROXY FOR IT UNTIL 2026-09-04
    (`DEF-CWP-3765`).** Wave E wrote `unit_id is None and premises_id is not
    None`, which is what `BR-CUS-068`'s ORIGINAL anchoring implied — and that
    clause was superseded on 2026-09-01 (`CR-056` W1, `BR-CUS-1010`): a master
    now writes `premises_id` and leaves `unit_id` NULL. **The proxy therefore
    agreed with the truth by coincidence**, and only for rows created after
    migration `customers/0036`; the same ruling says *"Accounts created before
    migration 0036 keep the anchor they were created with"*, so a master from
    before it has a unit and the proxy calls it a tenant's home. `kind` is the
    column `create_master_account` actually writes and is the only door to the
    value (`services.REFUSED_FIELDS` refuses it everywhere else).
    """
    rows = {
        str(row.pk): row
        for row in customers_models.Account.objects.filter(
            tenant_id=principal.tenant_id, pk__in=list(principal.account_ids)
        ).select_related("unit")
    }
    out: list[dict[str, Any]] = []
    for entry in principal.accounts:
        account = rows.get(entry.account_id)
        if account is None:
            continue
        out.append(
            {
                "id": entry.account_id,
                "account_no": account.account_no,
                "label": _service_address(account) or account.account_no,
                "permissions": list(entry.permissions),
                "source": entry.source,
                "is_master": account.kind == customers_seam.ACCOUNT_KIND_MASTER,
            }
        )
    return out


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def accounts_view(request: Any) -> Response:
    """`GET accounts` — the same flat set, on its own, for the switcher."""
    principal = _principal(request)
    return _no_store(Response({"accounts": _account_rows(principal)}))


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def account_balance(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/balance` — one account, **never cached** (`BR-CWP-047`).

    The id is intersected with the session's set IN THE QUERY (`BR-CWP-010`);
    an id outside it answers the same 404 an id that does not exist answers.
    """
    account = _account_in_set(request, account_id)
    return _no_store(Response(payments_seam.account_balance(account.pk)))


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def bills(request: Any) -> Response:
    """`GET bills` — `CWP-027`, every bill this login may see.

    ⚠ **AMOUNT AND OWING ARE TWO COLUMNS AND THE SCREEN NEVER SUBTRACTS**
    (`BR-CWP-043`); a corrected bill is LISTED and names its replacement
    (`BR-CWP-042`). Both are the server's facts, so two screens cannot disagree
    about what a customer still owes.

    ⚠ **`no-store`** — every row carries a live owing figure.

    ⚠ **`?account_id=` NARROWS THE LIST TO THE ACCOUNT THE SWITCHER NAMES**
    (`BR-CWP-010`, `US-CWP-023` TC-2); omitted, the answer is the whole set,
    exactly as before. The id is intersected with the set IN THE QUERY, so one
    outside it answers 404.

    ⚠ **ONE PAGE, SEARCHED AND SORTED BY THE SERVER, SINCE 2026-09-19**
    (`NFR-3`, `DEF-CWP-5747`). This route served an unbounded array and the
    browser searched, chipped, sorted and sliced it. `?q=`, `?sort=`, `?dir=`,
    `?page=`, `?per=` and `?f.<name>=` are the house grammar (`BR-SHL-011`) and
    the body carries `count` for the footer. **All four moved together on
    purpose**: a server page under a browser search would tell a customer that
    a row on page 7 does not exist. `apps/portal/paging.SQL_PAGED` records that
    this list takes its page on the server rather than in SQL, and why.
    """
    params = paging.portal_params(
        request,
        allowed_sorts=tuple(selectors.BILL_SORTS),
        default_sort=selectors.BILL_DEFAULT_SORT,
        allowed_filters=selectors.BILL_FILTER_NAMES,
    )
    scope = _scope(request)
    # ⚠ **THE THREE WHOLE-SET FACTS RIDE AS `extra`** — the oldest bill, whether
    # anything is owed at all, and whether this customer has any bills. The
    # screen read all three off the array it used to hold; over a page the
    # first would say *since Aug 2026* on page 1 of eleven years and the second
    # would hide the *Pay* control from somebody whose only unpaid bill is on
    # page 2.
    rest: dict[str, Any] = {}

    def page(window: Any) -> tuple[list[dict[str, Any]], int]:
        body, total = selectors.bills_page(scope, today=date.today(), params=window)
        rest.update({key: value for key, value in body.items() if key != "bills"})
        return body["bills"], total

    body = paging.windowed("bills", params, page)
    body.update(rest)
    return _no_store(Response(body))


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def home(request: Any) -> Response:
    """`GET home` — `CWP-022`, everything the first screen draws, in one read.

    ⚠ **ONE ROUND TRIP, DELIBERATELY.** The home page is the screen a customer
    opens four to twelve times a year and leaves in thirty seconds; six
    parallel calls would each pay the tenant resolution and the session read,
    and the slowest would set the page's speed.

    ⚠ **`no-store`** (`BR-CWP-047`) — the body carries a live balance.
    """
    principal = _principal(request)
    return _no_store(Response(selectors.home(principal, today=date.today())))


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def account_summary(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/summary` — `CWP-065`, the facts that are not on a bill.

    The id is intersected with the session's set IN THE QUERY (`BR-CWP-010`), so
    an account outside it answers the same 404 an account that does not exist
    answers — the master confers nothing here either.

    ⚠ **`no-store` LIKE THE BALANCE READS, AND FOR A NARROWER REASON.** This body
    carries a held deposit and its accrued interest: a customer who closes their
    account should not see yesterday's interest figure on a cached page and then
    a different one on their final bill.
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    return _no_store(
        Response(
            selectors.account_summary(principal.tenant_id, account, as_of=date.today())
        )
    )


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def my_accounts(request: Any) -> Response:
    """`GET my-accounts` — `CWP-023`, the whole set with a total (`US-CWP-026`).

    ⚠ **THE TENANTS' ACCOUNTS ARE ABSENT BY CONSTRUCTION, NOT BY A FILTER.**
    Every row is built from `principal.accounts`, so there is no query here for
    a `?include=` or a widened scope to reach. `OQ-1397` was ruled **no** on
    2026-09-04 (`BR-CWP-016`) and this read was already drawn that way.

    ⚠ **`no-store` LIKE THE OTHER TWO BALANCE READS** (`BR-CWP-047`): this body
    carries four live balances, and a screen that showed Tuesday's figures on
    Thursday is the defect the rule exists for.

    ⚠ **ONE PAGE, SEARCHED AND SORTED BY THE SERVER, SINCE 2026-09-19**
    (`NFR-3`, `DEF-CWP-5747`). This route served an unbounded array and the
    browser searched, chipped, sorted and sliced it. `?q=`, `?sort=`, `?dir=`,
    `?page=`, `?per=` and `?f.<name>=` are the house grammar (`BR-SHL-011`) and
    the body carries `count` for the footer. **All four moved together on
    purpose**: a server page under a browser search would tell a customer that
    a row on page 7 does not exist. `apps/portal/paging.SQL_PAGED` records that
    this list takes its page on the server rather than in SQL, and why.
    """
    principal = _principal(request)
    params = paging.portal_params(
        request,
        allowed_sorts=tuple(selectors.MY_ACCOUNT_SORTS),
        allowed_filters=tuple(selectors.MY_ACCOUNT_FILTERS),
    )
    # ⚠ **THE ROLL-UP IS THE WHOLE SET'S AND RIDES AS `extra`** (`BR-CWP-015`):
    # `total_owing` is four accounts' `$872.82` whichever page is open, because
    # a total of the PAGE would be a different number on page 2 and a customer
    # could reasonably believe it and try to pay it.
    roll_up: dict[str, Any] = {}

    def page(window: Any) -> tuple[list[dict[str, Any]], int]:
        body, total = selectors.my_accounts_page(
            principal, today=date.today(), params=window
        )
        # Captured on every ask, including the one `windowed` re-issues when a
        # person types `?page=999`, so the roll-up beside the last page is the
        # roll-up that read was taken with rather than an earlier one's.
        roll_up.update({key: value for key, value in body.items() if key != "accounts"})
        return body["accounts"], total

    body = paging.windowed("accounts", params, page)
    body.update(roll_up)
    return _no_store(Response(body))


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def balance_summary(request: Any) -> Response:
    """`GET balance/summary` — every account **separately**, and a total.

    ⚠ **`BR-CWP-015`: TOTALLED, NEVER MERGED.** Four rows and `total_owing`;
    there is no field in this body that could be paid as one amount. The
    landlord's four accounts total `$872.82` and the `$0.00` row is one of the
    four rather than an absence.
    """
    principal = _principal(request)
    return _no_store(
        Response(
            payments_seam.balance_summary(list(principal.account_ids), as_of=date.today())
        )
    )


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def my_details(request: Any) -> Response:
    """`GET my-details` — `CWP-024`, what a customer may fix and what they may not.

    ⚠ **THE UNEDITABLE FIELDS ARE IN THIS BODY ON PURPOSE** (`BR-CWP-026`). The
    legal name is returned so the screen can SHOW it beside *ask us to change
    this*; a field left out reads as an oversight, and a customer who cannot
    find their name assumes the product lost it.

    ⚠ **`no-store`** — the body carries the customer's own contact details.
    """
    principal = _principal(request)
    return _no_store(
        Response(selectors.my_details(principal, today=date.today()))
    )


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def save_my_details(request: Any) -> Response:
    """`POST my-details` — the `contact_detail` write (`BR-CWP-001` kind ⑤).

    ⚠ **THE ACCOUNTS COME FROM THE SESSION AND NEVER FROM THE BODY**
    (`BR-CWP-010`). There is no `account_ids` field to send; the set is
    `principal.account_ids`, re-derived on this request, so a body cannot name
    whose contact row gets written.

    ⚠ **A FIELD OUTSIDE THE THREE IS REFUSED BY NAME AND BEFORE ANYTHING IS
    WRITTEN** (`BR-CWP-026`, `US-CWP-028` TC-2). Posting a new legal name
    straight to this endpoint leaves the stored name byte-identical — the
    refusal is on the endpoint, so a read-only input on the screen is not the
    security.

    ⚠ **AND THERE IS NO SECOND PASSWORD PROMPT, WHICH IS `BR-CWP-103` AND NOT
    AN OVERSIGHT.** PO ruling 2026-09-04: the defence is at the door.
    """
    principal = _principal(request)
    body = dict(request.data) if isinstance(request.data, dict) else {}
    # ⚠ **THE EMAIL NO LONGER MOVES HERE** (PO 2026-10-22, Q2 option A;
    # `DEF-CWP-10401`): a new email is confirmed by a code to it, through
    # `my-details/email/start` + `/confirm`, and then the sign-in moves too.
    # The email the screen shows is dropped, so a phone or address save still
    # works; a different one is refused by name, before anything is written.
    if "email" in body:
        shown = selectors.my_details(principal, today=date.today()).get("email")
        if credentials.normalise_email(body["email"]) != credentials.normalise_email(shown):
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CWP-026",
                message_key="portal.myDetails.emailNeedsCode",
                params={"field": "email"},
            )
        body.pop("email")
    result = services.update_own_contact_details(
        principal.tenant_id,
        actor=principal,
        account_ids=list(principal.account_ids),
        payload=body,
    )
    return _no_store(Response(result))


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def preferences(request: Any) -> Response:
    """`GET my-details/preferences` — `CWP-025`, the grid and the consent.

    ⚠ **`no-store`** — the body says how a named customer is contacted and when
    they agreed to it.
    """
    principal = _principal(request)
    return _no_store(Response(selectors.contact_preferences(principal, today=date.today())))


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def save_preferences(request: Any) -> Response:
    """`POST my-details/preferences` — the `preference` write.

    ⚠ **POST IS REFUSED BY NAME AND NOT IGNORED** (`US-CWP-028` TC-3). A body
    carrying `post_on` is told that print is the floor, in the reader's own
    language, rather than being accepted into a screen that says *saved* over a
    value that went nowhere. The grid draws `ALWAYS` and offers no control; this
    is the half that holds when somebody calls the endpoint directly
    (`BR-CWP-002`: the refusal is at the edge, never at the screen).

    ⚠ **THE ACCOUNTS COME FROM THE SESSION** (`BR-CWP-010`) — there is no
    `account_ids` field to send, and one save reaches every account this login
    holds.
    """
    principal = _principal(request)
    body = request.data if isinstance(request.data, dict) else {}
    result = services.record_preference(
        principal.tenant_id,
        shape=services.SHAPE_DELIVERY,
        payload={
            "actor": principal,
            "account_ids": list(principal.account_ids),
            "fields": body,
        },
    )
    return _no_store(Response(result))


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def withdraw_paperless(request: Any) -> Response:
    """`POST my-details/paperless/withdraw` — `US-CWP-028` TC-5.

    ⚠ **THE CONSENT ROW GAINS `withdrawn_on` AND IS NEVER DELETED.** A consent
    that was given and then withdrawn is a different fact from no consent at
    all, and the wording version — the only evidence of what the person was
    shown — lives on that row. `BR-CWP-087` and the model's own docstring.
    """
    principal = _principal(request)
    result = services.record_preference(
        principal.tenant_id,
        shape=services.SHAPE_WITHDRAW_PAPERLESS,
        payload={"account_ids": list(principal.account_ids)},
    )
    return _no_store(Response(result))


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def add_account_find(request: Any) -> Response:
    """`POST accounts/add/find` — `CWP-020` step one (`US-CWP-027`).

    ⚠ **A WRONG POSTCODE AND AN UNKNOWN NUMBER ANSWER THE SAME SENTENCE**
    (TC-2). One reason string, `not_matched`, for both — otherwise a signed-in
    customer could walk the account-number space of their own utility.

    ⚠ **THE CODE GOES TO THE CONTACT ON THE ACCOUNT BEING ADDED** (TC-3,
    `BR-CWP-033`), and the masked destination that comes back is all this
    endpoint discloses about it. That is the whole guard: matching gives you
    nothing you did not already type.

    ⚠ **AN ACCOUNT WITH NO CONTACT DEAD-ENDS INTO *RING THE OFFICE*** (TC-5,
    `BR-CWP-034`) — it must NEVER fall back to something weaker, so there is no
    branch below that one.
    """
    principal = _principal(request)
    body = request.data if isinstance(request.data, dict) else {}
    tenant_id = principal.tenant_id
    account = customers_seam.account_by_number_and_postcode(
        tenant_id,
        account_no=body.get("account_number"),
        postcode=body.get("postcode"),
    )
    if account is None:
        return _no_store(Response({"matched": False, "reason": "not_matched"}))
    if str(account.pk) in {str(one) for one in principal.account_ids}:
        # TC-4 — already in the set. Saying so discloses nothing the asker does
        # not already hold: they can see this account on their own list.
        return _no_store(Response({"matched": False, "reason": "already_held"}))

    channel, destination, masked = credentials.contact_for(tenant_id, account)
    if channel is None:
        return _no_store(
            Response({"matched": True, "reason": "no_contact_on_file", "account_ref": None})
        )
    issued = credentials.issue_code(
        tenant_id,
        purpose=models.PURPOSE_ADD_ACCOUNT,
        account=account,
        channel=channel,
        masked=masked,
    )
    credentials.queue_code(tenant_id, account=account, issued=issued, destination=destination)
    return _no_store(
        Response(
            {
                "matched": True,
                #: The one-time code row's id, never the account's (B14 rule 31
                #: and `find_account`'s own reasoning — an account id here would
                #: be an account id in a browser).
                "account_ref": issued.row_id,
                "sent_to": masked,
                "channel": channel,
                "expires_in_minutes": models.CODE_TTL_MINUTES,
            }
        )
    )


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def add_account_verify(request: Any) -> Response:
    """`POST accounts/add/verify` — the `account_link` write (kind ⑥).

    ⚠ **THE CODE IS CONSUMED HERE AND THE LINK IS WRITTEN ONLY AFTER IT IS.**
    `services.add_account_to_login` cannot check the code — its signature has no
    way to — so this endpoint is where `BR-CWP-033` is actually enforced, and
    the service's docstring says so rather than implying the check happens
    somewhere safe.

    ⚠ **NOTHING IS COMBINED** (`BR-CWP-015`, TC-7). One `customer_accounts` row.
    The account set is re-derived on the next request, so the switcher lists
    five without anything being merged.
    """
    principal = _principal(request)
    body = request.data if isinstance(request.data, dict) else {}
    tenant_id = principal.tenant_id
    row = credentials.code_row(tenant_id, body.get("account_ref"))
    account = getattr(row, "account", None)
    if account is None:
        return _no_store(Response({"linked": False, "reason": credentials.CODE_EXPIRED}))
    verdict = credentials.verify_code(
        tenant_id,
        purpose=models.PURPOSE_ADD_ACCOUNT,
        code=str(body.get("code") or ""),
        account=account,
    )
    if verdict != credentials.CODE_OK:
        return _no_store(Response({"linked": False, "reason": verdict}))

    # ⚠ **THE CUSTOMER IS THE CREDENTIAL'S, NOT A LOOKUP FROM THE ACCOUNTS.**
    # `PortalCredential` points at exactly one `customers.Customer`, so who is
    # adding this account is never in doubt. Deriving it from the account set
    # instead would ask "which of these accounts' customers did you mean" on a
    # jointly-held account and have no way to answer.
    result = services.add_account_to_login(
        tenant_id,
        actor=principal,
        customer_id=principal.customer_id,
        account_id=account.pk,
    )
    return _no_store(Response({"linked": True, "created": result["created"]}))



# ═══════════════════════════════════════════════════════════════════════════
# CR-068 · CWP-031 · CWP-063 · CWP-044 — three reads, no writes
# ═══════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave H · §2 *Usage and readings* — three of the five (US-CWP-040/041/043)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **SUPERSEDED 2026-10-17 (`DEF-CWP-10175`) — THE WRITE IS BUILT, AS
# `accounts/{id}/readings/send` (`send_reading`, below).** This read
# *"`POST accounts/{id}/readings` IS NOT HERE, AND ITS ABSENCE IS THE
# WAVE ORDER RATHER THAN AN OVERSIGHT."*, and its reasoning still holds —
# which is why the write landed WITH its screen: sending a reading is
# `US-CWP-042` — wave 3, and the ONE portal switch that is OFF for a new tenant (`CR-068` R8).
# A live endpoint with no screen is surface with no caller (`DEF-CWP-3704`), and
# a WRITE with no screen is worse: it is a route into billing nobody clicked.
#
# ⚠ **ALL THREE ARE `no-store`.** None of them carries money, and the reason is
# the other one `BR-CWP-047` gives: a reading a customer disputes today may be
# superseded tomorrow, and a cached page would keep showing the figure they rang
# up about after we corrected it.


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def documents(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/documents` — `CWP-031`, what we sent and how.

    ⚠ **THIS BODY SAYS WHAT WAS SENT AND NEVER THAT IT ARRIVED** (`BR-CWP-083`,
    and `OQ-1399` closed 2026-09-04 with the portal as a convenience copy). No
    provider reports delivery on any channel, so every row carries
    `delivery_reported: false` with the reason, and the four states are *sent ·
    queued · held · could not send*.

    ⚠ **`documents: null` IS NOT AN EMPTY LIST.** Null means the queue could not
    be asked; `[]` means it was asked and this account has nothing. A screen
    that drew one empty state over both would tell a customer of eleven months
    that we never wrote to them.

    ⚠ **`no-store`**: the list carries what a customer was sent and when.

    ⚠ **ONE PAGE, SEARCHED AND SORTED BY THE SERVER, SINCE 2026-09-19**
    (`NFR-3`, `DEF-CWP-5747`). This route served an unbounded array and the
    browser searched, chipped, sorted and sliced it. `?q=`, `?sort=`, `?dir=`,
    `?page=`, `?per=` and `?f.<name>=` are the house grammar (`BR-SHL-011`) and
    the body carries `count` for the footer. **All four moved together on
    purpose**: a server page under a browser search would tell a customer that
    a row on page 7 does not exist. `apps/portal/paging.SQL_PAGED` records that
    this list takes its page on the server rather than in SQL, and why.
    """
    account = _account_in_set(request, account_id)
    params = paging.portal_params(
        request,
        allowed_sorts=tuple(selectors.DOCUMENT_SORTS),
        allowed_filters=tuple(selectors.DOCUMENT_FILTERS),
    )
    # ⚠ **`groups` AND `unavailable` ARE NOT ROWS AND RIDE AS `extra`.** The
    # null case above is the reason this list cannot simply be a page: an
    # unreachable queue answers `documents: null` with a sentence, and a page
    # of nothing answers `[]`.
    rest: dict[str, Any] = {}

    def page(window: Any) -> tuple[list[dict[str, Any]], int]:
        body, total = selectors.documents_page(account, params=window)
        rest.update({key: value for key, value in body.items() if key != "documents"})
        return body["documents"], total

    body = paging.windowed("documents", params, page)
    body.update(rest)
    if rest.get("unavailable"):
        # The queue could not be asked. `null` and `[]` are different answers
        # and the screen branches on both; a `count` of zero beside `null`
        # would read as *asked, and there is nothing*.
        body["documents"] = None
    return _no_store(Response(body))


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def account_usage(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/usage` — `CWP-033`, a year of usage per service.

    The figures are `metering`'s own stored months (`BR-MET-106`), the same
    read the staff Account details Usage tab draws — **not a second
    arithmetic** (PO ruling 2026-09-04; `12-reuse-map.md`).

    ⚠ **`?months=` TAKES 12 OR 24 AND FALLS BACK RATHER THAN REFUSING**
    (`BR-SHL-011`): a list URL never 4xxs over a parameter it does not know. The
    portal's default is **12**, which is the Product Owner's own window.

    The id is intersected with the session's set IN THE QUERY (`BR-CWP-010`).

    ⚠ **IT ALSO CARRIES `attached_answer` NOW (`DEF-CWP-3945`, 2026-09-11).**
    `published_content.ALSO_SHOW_SCREENS` has named `usage` since the feature
    shipped and nothing on this route ever asked for it, so a clerk who ticked
    *also show this on the Usage screen* published into nothing. It rides along
    exactly as it does on `bill_detail` and `account_arrears` — one screen, one
    read — and `null` is the ordinary answer, which the screen closes up
    (`BR-CWP-093`).
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    try:
        months = int(request.query_params.get("months", ""))
    except (TypeError, ValueError):
        months = selectors.USAGE_DEFAULT_MONTHS
    # The reader's language, the way `bill_detail` and `guest_api.help_answer`
    # already take it. `None` is English (`BR-CWP-094`).
    locale = request.query_params.get("locale") or None
    return _no_store(
        Response(
            selectors.account_usage(
                principal, account, months=months, today=date.today(), locale=locale
            )
        )
    )


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def plan_offer(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/plans/offer` — `CWP-063`, a plan offered, unsigned.

    ⚠ **NOTHING HERE ACCEPTS ANYTHING.** `BR-CWP-065` says a plan activates on
    the CUSTOMER's signature alone, and the portal may write rows of exactly six
    kinds — a payment, a service request, a meter reading, a preference, a
    contact detail, an account link (`BR-CWP-001`, `write_points.py`, G81). A
    signature is none of them, so this route READS the offer and the screen's
    three controls render VISIBLY HELD with their reason. Widening that list is
    a Product Owner ruling and is asked as `OQ-CWP-1568`.

    ⚠ **`no-store`**: the body carries the customer's arrears and a schedule.
    """
    account = _account_in_set(request, account_id)
    return _no_store(Response(selectors.plan_offer(account, today=date.today())))


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def plan_agreement_document(request: Any, account_id: str) -> Any:
    """`GET accounts/{id}/plans/offer/agreement` — the kept agreement itself.

    ⚠ **`CR-085` `CPB-03`. THE HOLD IT REPLACES WAS A HOLD ON NOTHING.**
    `CWP-063`'s *The agreement ↓* read *Downloads are not ready yet* over a
    document this product had already frozen and could already serve:
    `bill_document_pdf` has streamed the same kind of bytes, out of the same
    store, behind the same permission, since `US-CWP-034`. Nothing new was
    needed except somebody asking the question.

    ⚠ **DOWNLOAD IS A PERMISSION AND IT IS CHECKED HERE**, exactly as it is on a
    bill (`US-CWP-034` TC-7). A delegate invited with *See* may READ the offer —
    the figures, the schedule, what accepting does — and taking away a COPY of
    the agreement is a separate grant. An account holder always has it.

    ⚠ **`attachment`, AND NO `?view=1` BRANCH.** The bill route grew one because
    `CWP-029` frames the issued page ON SCREEN and had no other way to do it.
    Nothing draws an agreement inline, so the parameter would be a code path
    with no caller — hard-won law 2, in the direction nobody watches.

    ⚠ **NOT A 500 AND NOT A RE-RENDER** (`BR-CWP-045`, `BR-NOT-027`). No kept
    copy is refused BY NAME with the wording the screen already carries, and a
    re-render would hand the customer a document that is not the one they were
    sent.
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    if not principal.may(account.pk, "download"):
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    from apps.portal.seams import notifications_seam, payments_seam

    offer = payments_seam.plan_offer_for([account.pk], as_of=date.today())
    if offer is None:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    # ⚠ **THE VERDICT, NOT A `None` (`CR-085` `CPB-19`).** `CPB-03` shipped
    # this route reading `plan_agreement_bytes`, which cannot tell *we no
    # longer have it* from *what we have is not what you received* — and the
    # second was not merely unnamed here, it was a raw **500**, because
    # `ContentHashMismatch` was deliberately left uncaught. It is a REFUSAL
    # now, with its own sentence; `BR-NOT-027` never asked for a stack trace.
    verdict, page, content_type, name = notifications_seam.stored_document_service(
        source_type="plan", source_id=offer["id"]
    )
    if verdict == notifications_seam.DOCUMENT_NOT_TRUSTED:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-NOT-027",
            message_key="portal.document.notTrusted",
        )
    if verdict != notifications_seam.DOCUMENT_OK or page is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-045",
            message_key="portal.planOffer.agreementNotKept",
        )
    content_type = content_type or "application/pdf"
    filename = "payment-plan-agreement.pdf"
    response = HttpResponse(page, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return _no_store(response)


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def account_readings(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/readings` — `CWP-034`, every reading with its method.

    ⚠ **THE METHOD TRAVELS AS A CODE AND THE CATALOGUE WRITES THE WORDS**
    (`BR-CWP-071`, B14 rule 35). *Read by a meter reader* in eleven languages is
    eleven catalogue lines; one English sentence from a server is ten screens
    that cannot be translated.

    ⚠ **AND A READING NOBODY HAS BILLED CARRIES AN EMPTY `on_bill`** — never the
    nearest bill, which would tell a customer they were charged for it
    (`US-CWP-041` TC-4).

    ⚠ **`today` IS PASSED IN** (`BR-TEN-043`) because the payload now carries
    `next_read` and its countdown (`CR-085` `CPB-09`). A read model that asked
    the clock itself would serve a figure no test could pin.

    ⚠ **ONE PAGE, SEARCHED AND SORTED IN THE DATABASE, SINCE 2026-09-19**
    (`NFR-3`, `DEF-CWP-5747`). This route was handed `limit=None` and served
    EVERY reading the account had ever taken so that a browser could search,
    sort and slice them — on an AMI deployment, an interval reading per meter
    per hour. `?q=`, `?sort=`, `?dir=`, `?page=`, `?per=` and `?f.service=` are
    the house grammar (`BR-SHL-011`), the body carries `count` for the footer,
    and `services` is the tab list over the WHOLE account rather than over the
    page. **All three moved together on purpose**: a server page under a
    browser search would tell a customer a reading on page 7 does not exist.
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    params = paging.portal_params(
        request,
        allowed_sorts=tuple(metering_seam.READING_SORTS),
        default_sort=metering_seam.READING_DEFAULT_SORT,
        default_dir=metering_seam.READING_DEFAULT_DIR,
        allowed_filters=("service",),
    )
    return _no_store(
        Response(
            paging.windowed(
                "readings",
                params,
                lambda window: selectors.account_readings_page(
                    principal, account, params=window
                ),
                extra=selectors.account_readings_frame(
                    principal, account, today=date.today()
                ),
            )
        )
    )


@api_view(["GET", "POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def send_reading(request: Any, account_id: str) -> Response:
    """`accounts/{id}/readings/send` — `CWP-035`, *Send us your reading*
    (`US-CWP-042`, `DEF-CWP-10175`).

    `GET` is the form's frame: each meter on this account's unit by SERIAL,
    each register's last reading and date, and the read window. `POST` is the
    `meter_reading` write point (`BR-CWP-001` kind ③) — body
    `{meter, register, value, read_on}` — and answers `{received, flagged,
    checks, used, unit, times_usual, read_on, reading}`.

    ⚠ **THE ACCOUNT COMES OFF THE SESSION, IN THE QUERY** (`BR-CWP-010`,
    `_account_in_set`) — an account outside the set is the same 404 as one that
    does not exist. ⚠ **SWITCHED OFF, BOTH VERBS REFUSE** (`US-CWP-042` TC-7,
    `BR-CWP-002`): the screen is unreachable AND the write is refused.

    ⚠ **`today` IS PASSED IN** (`BR-TEN-043`) — the date default and the
    *future* refusal are a fact a test can pin.

    ⚠ **NO PHOTO** — consumer upload is a signed deferral (PO 2026-08-08, DF-4;
    `DEF-CWP-3611`). A posted file is not read.

    ⚠ **`no-store`** — the frame carries the customer's own readings.
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    if request.method == "GET":
        return _no_store(
            Response(selectors.self_read_frame(principal, account, today=date.today()))
        )
    body = request.data if isinstance(request.data, dict) else {}
    result = services.submit_meter_reading(
        principal.tenant_id,
        actor=principal,
        account=account,
        payload={key: body.get(key) for key in ("meter", "register", "value", "read_on")},
        today=date.today(),
    )
    return _no_store(Response(result, status=201))


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def level_pay(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/level-pay` — `CWP-044`, the same amount every month.

    ⚠ **THE LEVEL IS READ, NEVER RECOMPUTED HERE.** `US-CWP-054` §7 says so in
    as many words — *"existing, configured arithmetic; read, not recomputed"* —
    and the arithmetic is `apps.billing.budget.compute_level`, which is ❄️
    GT-24's own function. The rounding and the averaging window are the
    TENANT's settings, so a utility that rounds differently gets its own figure
    and not this screen's.

    ⚠ **`no-store`**: the body carries twelve months of billed totals.
    """
    account = _account_in_set(request, account_id)
    return _no_store(Response(selectors.level_pay(account)))


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def account_equipment(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/equipment` — `CWP-037`, what is fitted at the property.

    ⚠ **BY SERIAL, NEVER BY A ROW ID** (B14 rule 31, `US-CWP-043` TC-5) — and
    not by eight characters of one either, which `DEF-3158` records as the same
    breach as a whole uuid. The payload carries no `asset_id` at all.

    ⚠ **ONLY THIS UNIT'S EQUIPMENT** (TC-4). A sub-meter on the flat next door
    was never assigned here, so it is absent by construction.
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    return _no_store(
        Response(selectors.account_equipment(principal, account, today=date.today()))
    )



urlpatterns = [
    # 07-endpoints.md §2 *Authentication and enrolment* — the seven.
    path("portal/auth/sign-in", sign_in),
    path("portal/auth/sign-out", sign_out),
    path("portal/enrol/find-account", find_account),
    path("portal/enrol/verify-code", verify_code),
    path("portal/enrol/set-password", set_password),
    path("portal/auth/forgot-password", forgot_password),
    path("portal/auth/reset-password", reset_password),
    # The read behind CWP-018's consequence panel (BR-CWP-039) — guarded on a
    # CONSUMED code, which is why it is not one of the seven.
    path("portal/enrol/consequences", enrol_consequences),
    # §2 *Session and the account set* — three of the four; `accounts/add` is
    # wave F's, with the screen that calls it (`CWP-020`).
    path("portal/session", session_view),
    path("portal/accounts", accounts_view),
    path("portal/sessions/revoke-all", revoke_all_sessions),
    # §2 *Balance* — both.
    path("portal/accounts/<uuid:account_id>/balance", account_balance),
    path("portal/balance/summary", balance_summary),
    # CR-068 wave F — CWP-023, the landlord's four rows and their total.
    path("portal/my-accounts", my_accounts),
    # CR-068 wave F — CWP-022, the whole home page in one read.
    path("portal/home", home),
    # CR-068 wave G — CWP-027, every bill with owing beside amount.
    path("portal/bills", bills),
    # CR-068 wave G — CWP-024, the details a customer may fix. The POST is the
    # `contact_detail` write point (BR-CWP-001 kind ⑤, PO ruling OQ-CWP-1562).
    path("portal/my-details", my_details),
    path("portal/my-details/save", save_my_details),
    # CR-068 wave G — CWP-025, the PREFERENCES half of US-CWP-028.
    # ⚠ `07-endpoints.md` §2 names these `GET`/`PUT details/preferences` and
    # `POST details/paperless/withdraw`; they are mounted under
    # `my-details/` beside `CWP-024`'s pair because that is where the
    # existing routes live, and PUT is a POST for the same reason
    # `my-details/save` is — this edge has one verb for a write and the
    # doc row is stamped with what was built.
    path("portal/my-details/preferences", preferences),
    path("portal/my-details/preferences/save", save_preferences),
    path("portal/my-details/paperless/withdraw", withdraw_paperless),
    # CR-068 wave G — CWP-020, add another account. Two steps, because the code
    # goes to the contact on the account being ADDED (BR-CWP-033).
    path("portal/accounts/add/find", add_account_find),
    path("portal/accounts/add/verify", add_account_verify),
    # CR-068 wave F — CWP-065, the deposit and the exemption.
    path("portal/accounts/<uuid:account_id>/summary", account_summary),
    # CR-068 wave H — CWP-031 · CWP-063 · CWP-044, in the ACCOUNT-SCOPED shape
    # `07-endpoints.md` allocates. All three are per-account facts: a plan
    # spreads ONE account's arrears, budget billing is enrolled per account
    # (`account_budget_status`), and post is addressed to an account. The id is
    # intersected with the session's set IN THE QUERY by `_account_in_set`
    # (BR-CWP-010), so an account outside it answers the same 404 an account
    # that does not exist answers — the switcher names which one is open.
    path("portal/accounts/<uuid:account_id>/documents", documents),
    path("portal/accounts/<uuid:account_id>/plans/offer", plan_offer),
    #: `CR-085` `CPB-03` — the kept agreement, behind the `download` permission.
    path(
        "portal/accounts/<uuid:account_id>/plans/offer/agreement",
        plan_agreement_document,
    ),
    path("portal/accounts/<uuid:account_id>/level-pay", level_pay),
    # CR-068 wave H — CWP-033, CWP-034, CWP-037. Three of `07-endpoints.md`
    # §2 *Usage and readings*' five; `GET readings/{id}` is not built because
    # `CWP-034` opens a row in place rather than at its own address, and
    # `POST accounts/{id}/readings` is US-CWP-042's (wave 3).
    path("portal/accounts/<uuid:account_id>/usage", account_usage),
    path("portal/accounts/<uuid:account_id>/readings", account_readings),
    # US-CWP-042 · DEF-CWP-10175 — CWP-035, *Send us your reading*: GET the
    # form's frame, POST the `meter_reading` write point (BR-CWP-074).
    path("portal/accounts/<uuid:account_id>/readings/send", send_reading),
    path("portal/accounts/<uuid:account_id>/equipment", account_equipment),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-016..021@c05e4dd4 · US-CWP-023@c05e4dd4 · US-CWP-024@c05e4dd4 (EP-CWP-03/04 stories + BR-CWP-004..047 verbatim)
# generated: 2026-09-04 by the CR-068 wave E build lane
# checklist: A✔ B✔ C✔ D✔(config/urls.py) E✔(CWP-015..019 · PortalShell · Home's tile) F✔ G✔ H=n/a(this file holds no 🔒 path; credentials.py and session.py do)
# gates: G91 (no apps.identity import) · G92 (no field outside the guest allow-list on a guest serialiser) · G81 (no ORM write in this file — every write goes through credentials.py/session.py) · pytest tests/test_us_cwp_016..024
# exceptions: (1) `accounts/add` is wave F's — the screen that calls it is CWP-020 and a live endpoint with no screen is surface without a caller (DEF-CWP-3704's lesson). (2) `enrol/consequences` is a TWELFTH route the endpoints table does not list; it is the read BR-CWP-039's panel needs and it is stamped into 07-endpoints.md §2.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave H — one bill (`CWP-028`), the bill as printed (`CWP-029`) and
# why it moved (`CWP-030`).
#
# ⚠ **THE PATH SEGMENT IS THE BILL NUMBER, NOT AN ID** (B14 rule 31, PO
# 2026-08-30: *"no Databse ID on screen - that is a rule"*). `/portal/bills/
# BL-2608-0141` is the reference printed on the paper the customer is holding,
# and it is what they would quote on the telephone. `accountDetailTabs.tsx`
# records that even EIGHT CHARACTERS of a uuid used as link text is the same
# breach as the whole of it, so a truncated id was never an option either.
#
# ⚠ **`BR-CWP-010`'S INTERSECTION IS IN `billing_seam.bill_in_set`**, which is
# the one query every route below goes through. A bill outside this login's
# accounts is never fetched, and an unknown number, another login's bill and a
# DRAFT all answer the same 404 — so the bill space cannot be walked.
# ═══════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def bill_detail(request: Any, number: str) -> Response:
    """`GET bills/{number}` — `CWP-028`, one bill line by line.

    ⚠ **THE SAME READ THE STAFF BILL DETAIL USES** (PO 2026-09-04). Everything
    in the body is `billing.selectors.invoice_detail`'s, projected into a
    customer's words and stripped of every database id; nothing here adds up a
    money figure the server has not already resolved.

    ⚠ **`no-store`** — `account.owing` is a live figure (`BR-CWP-047`).

    ⚠ **`attached_answer` RIDES ALONG RATHER THAN TAKING A ROUTE OF ITS OWN
    (`CWP-061`, `DEF-CWP-3985`, added 2026-09-05).** It is the same shape the
    home and usage screens already use for their tip — one screen, one read —
    and it saves a second round trip on the screen a customer opens most. It
    is composed HERE and not inside `billing_seam`, because the answer is
    `tenancy`'s content and a billing seam that reached into it would be a
    cross-module read wearing billing's name.

    ⚠ **`None` WHEN NOTHING IS ATTACHED, AND THE KEY IS STILL PRESENT.** The
    screen closes the slot up (`BR-CWP-093`); a MISSING key would read as
    *"this build does not have the feature"* rather than *"nothing is
    attached"*, and those need to look different to the next lane.
    """
    principal = _principal(request)
    from apps.portal.seams import billing_seam, tenancy_seam

    found = billing_seam.bill_detail_for(
        list(principal.account_ids), number=number, today=date.today()
    )
    if found is None:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    body = dict(found)
    # The reader's language comes from `?locale=`, exactly as the help route
    # reads it — the browser's own setting fills it in.
    body["attached_answer"] = tenancy_seam.attached_answer(
        principal.tenant_id, "bill", locale=request.query_params.get("locale") or None
    )
    return _no_store(Response(body))


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def bill_document(request: Any, number: str) -> Response:
    """`GET bills/{number}/document` — `CWP-029`, can we serve what we posted?

    ⚠ **THIS ROUTE RENDERS NOTHING AND NEVER WILL** (`BR-CWP-045`). It reports
    whether the artefact frozen at issue is available, and the PDF route below
    streams it. A bill with no kept copy answers `available: false` with its
    reason, which `US-CWP-034` TC-4 asks for in as many words — *"a plain
    sentence and a route to ask, not a re-render and not a 500"*.
    """
    principal = _principal(request)
    from apps.portal.seams import billing_seam

    found = billing_seam.printed_bill_for(list(principal.account_ids), number=number)
    if found is None:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    return _no_store(Response(found))


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def bill_document_pdf(request: Any, number: str) -> Any:
    """`GET bills/{number}/document.pdf` — the kept page itself.

    ⚠ **DOWNLOAD IS A PERMISSION AND IT IS CHECKED HERE** (`US-CWP-034` TC-7).
    A delegate invited with *See* may open `CWP-028` and read what the bill
    charged; taking away a COPY of the legal document is a separate grant, and
    `PortalPrincipal.may(account_id, "download")` is where the account holder's
    own `see · download · pay` and an invitee's narrower set meet. An account
    holder always has it.

    ⚠ **`attachment`, NOT `inline` — UNLESS `?view=1` (added 2026-09-05,
    `DEF-CWP-3983`).** The staff route serves inline because a clerk wants the
    page beside the account while answering a call; a customer who pressed
    *Download* means it, and that is still what the bare URL does.

    ⚠ **`?view=1` STREAMS THE SAME BYTES AND CHANGES ONE HEADER.** `CWP-029`
    is drawn as the issued page FRAMED ON SCREEN, letter-shaped and centred,
    and it shipped as one sentence and a link — 22 words on the whole page —
    because there was no way to put the document in front of the customer
    without `inline`. There is no second document and no re-render: this
    branch calls the same `printed_bill_bytes`, so a bill with no kept file
    refuses here exactly as it refuses below (`BR-CWP-045`, `BR-NOT-027`).

    ⚠ **IT IS THE SAME `download` PERMISSION AND THAT IS NOT A FORMALITY.**
    Viewing a PDF inline hands over the bytes — the browser's own viewer has a
    save button in it — so gating a preview any more loosely than the download
    would be `US-CWP-034` TC-7 defeated by a query parameter. The check above
    runs before this branch is reached.
    """
    principal = _principal(request)
    from apps.portal.seams import billing_seam

    invoice = billing_seam.bill_in_set(list(principal.account_ids), number=number)
    if invoice is None:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    if not principal.may(invoice.account_id, "download"):
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    verdict, page, content_type, filename = billing_seam.printed_bill_service(
        list(principal.account_ids), number=number
    )
    if verdict == notifications_seam_verdicts().DOCUMENT_NOT_TRUSTED:
        # ⚠ **THE THIRD ANSWER, AND IT IS WHY THIS ROUTE USED TO 500**
        # (`CR-085` `CPB-19`, `DEF-CWP-4699`). The bytes in the store no longer hash to the
        # record, so they are NOT the document this customer received.
        # `BR-NOT-027` forbids serving them and forbids a re-render; it never
        # asked for a Django error page, which is what a customer pressing
        # *view my bill* actually got. A refusal by name keeps the rule and
        # loses the stack trace, and it deliberately does NOT say *no copy was
        # kept* — that would be the softening the same rule forbids.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-NOT-027",
            message_key="portal.document.notTrusted",
            params={"number": number},
        )
    if verdict != notifications_seam_verdicts().DOCUMENT_OK or page is None:
        # ⚠ NOT A 500 AND NOT A RE-RENDER (`US-CWP-034` TC-4). The bill exists
        # and the customer is looking at it; what is missing is the kept file.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-045",
            message_key="portal.billDocument.notKept",
            params={"number": number},
        )
    content_type = content_type or "application/pdf"
    filename = filename or f"{number}.pdf"
    response = HttpResponse(page, content_type=content_type)
    # ⚠ The filename is declared either way, so a save from the browser's own
    # viewer keeps the bill number rather than a uuid — the staff route's note.
    inline = str(request.query_params.get("view", "")).lower() in {"1", "true", "yes"}
    disposition = "inline" if inline else "attachment"
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return _no_store(response)


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def bill_comparison(request: Any, number: str) -> Response:
    """`GET bills/{number}/comparison` — `CWP-030`, why this bill is different.

    ⚠ **THE BREAKDOWN *IS* SERVED, AND HAS BEEN SINCE 2026-09-05
    (`DEF-CWP-4207`).** This docstring said the opposite for five days. The PO
    closed `OQ-CWP-1563`/`OQ-CWP-1569` in the words *"(a) list every reason
    with its share"*, `billing_seam.COMPONENTS_SIGNED` is `True`, and the body
    carries `components` with `components_available: true` — one share per
    `(service, kind)` bucket, summing EXACTLY to the difference.

    ⚠ **`components_available: false` IS STILL REACHABLE AND IS NOT DEAD.** It
    now means `BR-CWP-046` refused the decomposition — the shares did not tie
    out to the headline — and `components_blocked_by` carries that rule id
    rather than a question id. Four numbers that do not add up to the figure a
    customer is reading explain nothing, so they are not served at all.

    The DIFFERENCE, its direction and the year-on-year usage are confirmed
    arithmetic and all served.
    """
    principal = _principal(request)
    from apps.portal.seams import billing_seam

    found = billing_seam.bill_comparison_for(list(principal.account_ids), number=number)
    if found is None:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    return _no_store(Response(found))


# ⚠ **APPENDED WITH `+=` RATHER THAN EDITED INTO THE LIST ABOVE**, and the
# reason is hard-won law 11: six lanes push to this branch and a whole-file
# blob written over a shared `urlpatterns` literal is how one lane's route
# silently reverts another's. An append at the END of the file merges.
#
# ⚠ **`document.pdf` IS DECLARED BEFORE `document`**, the same order
# `billing/documents_api.py` states is load-bearing there: both patterns are
# the same depth and Django matches in order, so the static one has to come
# first or `<str:number>` swallows it.
urlpatterns += [
    # CR-068 wave H — CWP-028, one bill line by line (US-CWP-033).
    path("portal/bills/<str:number>", bill_detail),
    # CR-068 wave H — CWP-029, the bill as it was printed (US-CWP-034).
    path("portal/bills/<str:number>/document.pdf", bill_document_pdf),
    path("portal/bills/<str:number>/document", bill_document),
    # CR-068 wave H — CWP-030, why this bill is different (US-CWP-035).
    path("portal/bills/<str:number>/comparison", bill_comparison),
]


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave G · `CWP-041` — the money list (US-CWP-048)
# CR-068 wave M · `CWP-042` · `CWP-043` — payment plans (US-CWP-051 · 052)
#
# ⚠ **APPENDED AT THE END OF THE FILE, WITH `urlpatterns += [...]`, AND THAT IS
# HARD-WON LAW 11 RATHER THAN A STYLE CHOICE.** Six lanes push to this branch
# and this file moved TWICE while this slice was being built — a whole-file blob
# written over a shared `urlpatterns` literal is how one lane's route silently
# reverts another's, and every post-push check in law 11 passes on it. An append
# merges. The wave-H lane below reached the same conclusion independently.
# ═══════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def payments(request: Any) -> Response:
    """`GET payments` — `CWP-041`, everything that moved money on this login.

    ⚠ **A BOUNCE IS TWO ROWS** (`BR-CWP-061`): the reversal reading *returned by
    the bank* at `−$129.02`, directly above the `$129.02` it undoes. **Nothing
    edits a payment** (hard rule 4), so the second row's *reversed* is DERIVED
    from the existence of the first and is not a status anybody wrote.

    ⚠ **NO UPDATE AND NO DELETE ROUTE FOR A PAYMENT EXISTS ON THIS EDGE**
    (`US-CWP-048` TC-3), and `urlpatterns` below is the whole of what this edge
    serves — so the absence is checkable rather than promised.

    ⚠ **THE WRITE-OFF REASON IS NOT IN THIS BODY** (`BR-CWP-051`). *Bankruptcy*
    and *deceased, no estate* are the utility's judgment about a person; the
    amount is the person's own money.

    ⚠ **`no-store`** — an amount can move between two loads (`BR-CWP-047`).

    ⚠ **`?account_id=` NARROWS THE LIST TO THE ACCOUNT THE SWITCHER NAMES**
    (`BR-CWP-010`, `US-CWP-023` TC-2); omitted, the answer is the whole set.

    ⚠ **THIS SCREEN IS NOT A PERMANENT RECORD OF A CORRECTED REFERENCE.** A
    payment's cheque number may be corrected in place (hard rule 4 as narrowed,
    PO 2026-09-02) and the value it replaced then lives only in `audit_log`,
    which is pruned. Whether such a row is exempt is **`OQ-1340`** and is OPEN,
    so nothing here — screen, body or docstring — may say otherwise. (`CLAUDE.md`
    hard rule 4 and `US-CWP-048` §8 both cited this as `OQ-1330` until
    2026-09-14, when `DEF-GOV-5229` corrected both on the PO's ruling; `OQ-1330`
    is a real and different question about a meter reading's unit.)

    ⚠ **ONE PAGE, SEARCHED AND SORTED BY THE SERVER, SINCE 2026-09-19**
    (`NFR-3`, `DEF-CWP-5747`). This route served an unbounded array and the
    browser searched, chipped, sorted and sliced it. `?q=`, `?sort=`, `?dir=`,
    `?page=`, `?per=` and `?f.<name>=` are the house grammar (`BR-SHL-011`) and
    the body carries `count` for the footer. **All four moved together on
    purpose**: a server page under a browser search would tell a customer that
    a row on page 7 does not exist. `apps/portal/paging.SQL_PAGED` records that
    this list takes its page on the server rather than in SQL, and why.
    """
    year = request.query_params.get("year")
    params = paging.portal_params(
        request,
        allowed_sorts=tuple(selectors.MONEY_SORTS),
        allowed_filters=tuple(selectors.MONEY_FILTERS),
    )
    scope = _scope(request)
    chosen_year = int(year) if year and str(year).isdigit() else None
    # ⚠ **`CR-085` `CPB-20` — WHETHER THE RECEIPT CAN ACTUALLY BE HANDED OVER,
    # ASKED HERE AND NOT GUESSED BY THE SCREEN.** `payments` knows a payment
    # has a number; only `notifications` knows whether a copy of its receipt
    # was kept. Walked in a browser: without this the row offered a live
    # download for a receipt this deployment never froze, and pressing it
    # answered a refusal — hard-won law 2's mirror, a dead thing behind a live
    # control, on the wave whose whole subject is that they must agree.
    rest: dict[str, Any] = {}

    def page(window: Any) -> tuple[list[dict[str, Any]], int]:
        body, total = selectors.money_page(scope, year=chosen_year, params=window)
        rest.update({key: value for key, value in body.items() if key != "money"})
        return body["money"], total

    body = paging.windowed("money", params, page)
    body.update(rest)
    return _no_store(Response(body))


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave M · `CWP-042` and `CWP-043` — payment plans (US-CWP-051/052)
# ═══════════════════════════════════════════════════════════════════════════


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def plan_preview(request: Any, account_id: str) -> Response:
    """`POST accounts/{id}/plans/preview` — `CWP-042` step 2. **Writes nothing.**

    ⚠ **A POST THAT WRITES NOTHING, FOR THE REASON `POST /accounts/{id}/plan-
    changes/preview` ALREADY ESTABLISHED:** the proposal travels in a body, and
    a pending arrangement does not belong in a cacheable URL. `writes: []` is on
    the response so a caller can tell a preview from a commit without knowing
    which route it called.

    ⚠ **THE ARITHMETIC IS `payments`'/`customers`' AND NOT THIS EDGE'S.** The
    seam calls `payment_plan_service.preview`, the same function the clerk's S24
    wizard calls — ❄️ GT-47, `BR-CUS-043`, **remainder on the final instalment**.

    ⚠ **THE ACCOUNT IS INTERSECTED WITH THE SESSION'S SET IN THE QUERY**
    (`BR-CWP-010`), so an account outside it answers the same 404 an account
    that does not exist answers.
    """
    account = _account_in_set(request, account_id)
    body = request.data if isinstance(request.data, dict) else {}
    return _no_store(
        Response(
            payments_seam.plan_preview(
                account.pk,
                months=_plan_months(body),
                first_due_on=_plan_date(body),
                down_payment=body.get("down_payment") or "0",
                as_of=date.today(),
            )
        )
    )


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def plan_request(request: Any, account_id: str) -> Response:
    """`POST accounts/{id}/plans/request` — the customer ASKS. `BR-CWP-066`.

    ⚠ **THIS CREATES A SERVICE REQUEST AND NOT A PLAN.** PO 2026-09-04
    (`OQ-1391`, option (a)): *"Utility Clark will di it for Consumer; COnsumer
    cannot do it by themself; these are special cases"*. The response says
    `plan_created: false` on its face so no screen can imply otherwise.

    ⚠ **THE SCHEDULE IS RE-PREVIEWED HERE FROM THE SAME INPUTS RATHER THAN
    TAKEN FROM THE BODY**, and that is the guard: a browser that could name the
    instalments would put a customer's own figures on a clerk's worklist. The
    preview is a pure read and re-running it costs one call.

    ⚠ **NO SELF-SERVE ACTIVATION PATH EXISTS TO REACH** (`US-CWP-051` TC-10).
    `J41` step 5 expected a `NotImplementedError("OQ-1391")` and was written
    while the question was open; it closed on 2026-09-04 and the answer is that
    the path does not exist. A stub would be a door.
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    body = request.data if isinstance(request.data, dict) else {}
    preview = payments_seam.plan_preview(
        account.pk,
        months=_plan_months(body),
        first_due_on=_plan_date(body),
        down_payment=body.get("down_payment") or "0",
        as_of=date.today(),
    )
    contact = customers_seam.contact_details(principal.tenant_id, [str(account.pk)])
    if not contact.get("phone"):
        # ⚠ **REFUSED BY NAME RATHER THAN SENT WITHOUT ONE.**
        # `create_from_portal` requires a phone because the form's own promise
        # is *"we ring you only if we need to"*, and a plan is the one ask a
        # clerk will certainly ring about. The customer can add one on
        # `CWP-024` — which is a route, not a dead end.
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref="BR-CWP-066",
            message_key="portal.plan.phoneNeeded",
            field_errors=[{"field": "phone", "code": errors.VAL_REQUIRED}],
        )
    return _no_store(
        Response(
            services.raise_service_request(
                principal.tenant_id,
                shape=services.SHAPE_PLAN_REQUEST,
                payload={
                    #: ⚠ **THE NUMBER ON THE PAPER BILL, NEVER THE ROW ID**
                    #: (B14 rule 31) — and it is read off the account the query
                    #: already proved is in this session's set.
                    "account_no": account.account_no,
                    #: `create_from_portal` requires one — *"there is no such
                    #: thing as a service request about nowhere"* — and it is
                    #: the premises' own address, walked to rather than stored
                    #: (hard rule 8). The preview already read it.
                    "address": preview.get("service_address"),
                    "name": contact.get("legal_name"),
                    "email": contact.get("email"),
                    #: `create_from_portal` REQUIRES a phone — its own promise is
                    #: *"we ring you only if we need to"*, and a promise to ring
                    #: needs a way to ring.
                    "phone": contact.get("phone"),
                    "note": str(body.get("note") or ""),
                    **{
                        key: preview[key]
                        for key in (
                            "balance",
                            "down_payment",
                            "spread",
                            "term_months",
                            "first_due_on",
                            "base_instalment_count",
                            "base_amount",
                            "final_amount",
                        )
                    },
                },
            ),
            status=201,
        )
    )


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def plans_current(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/plans/current` — `CWP-043`, the WHOLE plan.

    ⚠ **A CLOSED PLAN IS SERVED** (`US-CWP-052` TC-8) — *"a finished plan
    disappears from the portal today. It must not."*

    ⚠ **`no-store`**: an instalment's state moves with the calendar, and
    yesterday's *due in 9 days* is wrong today.
    """
    account = _account_in_set(request, account_id)
    return _no_store(
        Response(payments_seam.current_plans(account.pk, as_of=date.today()))
    )


def _plan_months(body: dict[str, Any]) -> int:
    """`term_months`, or a refusal naming the field. Never a default.

    A missing term silently becoming six would put a customer on a schedule they
    did not choose, which is the shape of every *defaults fail closed* defect
    (hard-won law 3).
    """
    raw = body.get("term_months")
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref="BR-CWP-062",
            message_key="portal.plan.termRequired",
            field_errors=[{"field": "term_months", "code": errors.VAL_REQUIRED}],
        ) from None


def _plan_date(body: dict[str, Any]) -> date:
    """`first_due_on`, or a refusal naming the field. Never `today`.

    ⚠ **NO CLOCK STANDS IN FOR A CUSTOMER'S CHOICE.** The engine refuses a first
    instalment on or before the business date anyway (`US-CUS-018` §5 — *"a
    schedule whose first row is already due is one the customer is late on
    before they sign it"*), and defaulting here would hide that refusal behind a
    date nobody picked.
    """
    raw = body.get("first_due_on")
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            br_ref="BR-CWP-062",
            message_key="portal.plan.firstDueRequired",
            field_errors=[{"field": "first_due_on", "code": errors.VAL_FORMAT}],
        ) from None


# ⚠ **`+=`, NOT AN EDIT INTO THE LIST ABOVE** — law 11, and the wave-H block
# beside this one says the same thing for the same reason.
#
# ⚠ **`portal/payments` CARRIES NO ACCOUNT ID AND THE THREE PLAN ROUTES DO,
# AND THE DIFFERENCE IS THE QUESTION EACH ANSWERS.** The money list is one
# person reconciling one bank statement across every account they hold —
# the shape `portal/bills` and `portal/documents` already take. A PLAN
# spreads the arrears of ONE account, so the account has to be named; the
# switcher names it, `_account_in_set` intersects it with the session's set
# IN THE QUERY (`BR-CWP-010`), and the FRONT-END route carries no id at all,
# exactly as `/account` does for `accounts/{id}/summary` (B14 rule 31).
#
# ⚠ **THERE IS NO PUT, PATCH OR DELETE ON A PAYMENT ANYWHERE ON THIS EDGE,
# AND THE ROUTE TABLE IS THE PROOF** (`US-CWP-048` TC-3).
@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def request_hub(request: Any) -> Response:
    """`GET portal/requests` — `CWP-046`, the six cards and what is open.

    ⚠ **NO ACCOUNT ID, AND NOT BECAUSE THE SWITCHER KNOWS ONE.** A portal
    service request carries no account BY RULE (`BR-CWP-026`: *"a public form
    may create work and may never change an account"*), so this list is the
    LOGIN's and could not be narrowed to one account even if the address said
    so. The body says as much in `lists_only_portal_requests`.

    ⚠ **A UTILITY WITH REQUESTS SWITCHED OFF IS REFUSED HERE AND NOT MERELY
    SERVED AN EMPTY HUB** (`US-CWP-060` TC-5). `selectors.request_errands`
    answers `[]` for that tenant, and a screen behind a route that answers
    happily is a screen a customer can still reach and read as *this utility
    takes no requests online* — which is a different sentence from *this page
    is not here*.

    ⚠ **`no-store`**: the body names what this customer has asked the utility
    for, which is theirs and nobody else's.
    """
    principal = _principal(request)
    if not selectors.request_errands(principal.tenant_id):
        raise errors.deny_as_not_found(br_ref="BR-CWP-093")
    return _no_store(Response(selectors.request_hub(principal)))


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def level_pay_standing(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/level-pay/standing` — `CWP-066`.

    ⚠ **NOTHING IS RECOMPUTED HERE AND NOTHING IS RECOMPUTED IN THE SEAM.** The
    level is `budget_service.effective_level`, the variance is the running total
    of the append-only `account_budget_events` that
    `budget_service.recompute_balance` exists to prove correct, and each
    re-levelling is an event row read out. `CWP-044` one route along answers the
    OFFER; this answers the POSITION, and neither carries the other's figures.

    ⚠ **A CUSTOMER WHO IS NOT ENROLLED IS ROUTED, NOT REFUSED** (`US-CWP-055`
    TC-5). A 404 would be indistinguishable from a broken page; the body says
    `standing: null` and names where to join.

    ⚠ **`no-store`**: the body carries what this customer pays a month and how
    far ahead or behind they are.
    """
    account = _account_in_set(request, account_id)
    return _no_store(Response(selectors.level_pay_standing(account)))


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def final_bill(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/final-bill` — `CWP-032`, and where the deposit goes.

    ⚠ **EVERY FIGURE IS `apps.billing.final_bill.settle_final_bill`'s.** That is
    the same function that settles the account for a clerk, and the interest
    inside it is `apps.customers.deposit_interest` — finance-signed against ❄️
    `GT-61`. A second arithmetic here is how a customer and a counter clerk come
    to quote different closing figures, which is exactly what `US-CWP-037` §7
    says this story exists to prevent.

    ⚠ **AND A NEGATIVE REMAINDER IS A REFUND, NOT A CREDIT** (`BR-CWP-048`).
    The engine names the path; nothing on this edge reads the sign and decides.

    ⚠ **`no-store`**: the body carries a deposit, a settlement and a closing
    meter reading.
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    return _no_store(
        Response(selectors.final_bill(principal, account, today=date.today()))
    )


def _stop_restart_dates(request: Any) -> tuple[date, date | None]:
    """`stop_from` and `start_again`, or a refusal a customer can act on.

    ⚠ **A RESTART BEFORE THE STOP IS REFUSED HERE** (`US-CWP-062` TC-5), with a
    field error rather than a page error, because the screen has to say WHICH
    box is wrong. `services._stop_restart` refuses it again on the write, so a
    caller that skipped the screen cannot put a row on a clerk's worklist that
    the clerk has to work out is impossible.
    """
    raw_stop = request.GET.get("stop_from") or (request.data or {}).get("stop_from")
    raw_start = request.GET.get("start_again") or (request.data or {}).get("start_again")
    try:
        stop_from = date.fromisoformat(str(raw_stop))
    except (TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            br_ref="BR-CWP-080",
            message_key="portal.stopRestart.stopFromRequired",
            field_errors=[{"field": "stop_from", "code": errors.VAL_FORMAT}],
        ) from None
    if not raw_start:
        return stop_from, None
    try:
        start_again = date.fromisoformat(str(raw_start))
    except (TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            br_ref="BR-CWP-080",
            message_key="portal.stopRestart.restartFormat",
            field_errors=[{"field": "start_again", "code": errors.VAL_FORMAT}],
        ) from None
    if start_again <= stop_from:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            br_ref="BR-CWP-080",
            message_key="portal.stopRestart.restartBeforeStop",
            field_errors=[{"field": "start_again", "code": errors.VAL_RANGE}],
        )
    return stop_from, start_again


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def stop_or_restart(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/stop-or-restart` — `CWP-052`, and which is cheaper.

    ⚠ **EVERY FIGURE IS READ AND THE VERDICT IS COMPUTED FROM THEM**
    (`US-CWP-062` §7: *"a screen that always says stopping is cheaper is wrong
    for a long absence"*). The standing charge comes from the PLAN through
    `apps.rating.seams.base_charge_for` — the one implementation of
    `BR-RAT-088`'s precedence — and the connection fee and deposit from the
    same `rating_seam` reads `CWP-008` has quoted to strangers since wave C.

    ⚠ **`no-store`**: the body carries what this customer pays a month.
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    stop_from, start_again = _stop_restart_dates(request)
    return _no_store(
        Response(
            selectors.stop_or_restart(
                principal,
                account,
                stop_from=stop_from,
                start_again=start_again,
                today=date.today(),
            )
        )
    )


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def ask_to_stop_or_restart(request: Any, account_id: str) -> Response:
    """`POST accounts/{id}/stop-or-restart` — the customer ASKS; a clerk acts.

    ⚠ **NOTHING IS DISCONNECTED HERE AND NOTHING IS SCHEDULED.** This is the
    FIFTH SHAPE of the existing `service_request` write point — not a seventh
    write point — so `write_points.py` is untouched and G81 still sees exactly
    one public function per declared kind. `BR-CWP-080`: the account STAYS OPEN
    and standing charges keep running, and the response says so rather than
    letting a confirmation screen imply the bill has stopped.
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    stop_from, start_again = _stop_restart_dates(request)
    body = request.data or {}
    return Response(
        services.raise_service_request(
            principal.tenant_id,
            shape=services.SHAPE_STOP_RESTART,
            payload={
                "account_no": account.account_no,
                # ⊕ `CR-183-BRC10` T1 — the account the ask is ABOUT, so the
                # customers module can store it with the request (its id stays
                # on the server; the clerk's sentence names the NUMBER).
                "account_id": account.id,
                "stop_from": stop_from.isoformat(),
                "start_again": start_again.isoformat() if start_again else None,
                "reason": body.get("reason"),
                "name": body.get("name"),
                "email": body.get("email"),
                "phone": body.get("phone"),
                # ⚠ **DERIVED BY WALKING TO THE PREMISES** (hard rule 8,
                # `BR-MET-1161`): the account declares no address column, and
                # `create_from_portal` requires one (`BR-CUS-070`).
                "address": selectors.service_address(account),
            },
        )
    )


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def temporary_stop_status(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/temporary-stop` — `CR-183-BRC10` T8.

    *Service paused 13 Oct – 26 Oct · restarts 26 Oct*, or the ask still waiting
    for a clerk — and whether *Restart my service now* may be pressed (B4).
    Read through `customers_seam`; no id, no work-order number and no clerk's
    note reaches the body.
    """
    account = _account_in_set(request, account_id)
    return _no_store(Response(customers_seam.temporary_stop_view(account.id)))


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def ask_to_restart_now(request: Any, account_id: str) -> Response:
    """`POST accounts/{id}/temporary-stop/restart` — B4, *Restart my service now*.

    The customer ASKS; a clerk approves; the account is active from that day.
    A SHAPE of the existing `service_request` write point, like the stop ask.
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    body = request.data or {}
    # ONE button, no form: the clerk still needs somebody to call, so the
    # contact facts this login already has on file fill whatever was not sent
    # (the stop ask's check step prefills the same read, `contact_details`).
    on_file = customers_seam.contact_details(principal.tenant_id, [str(account.pk)])
    return Response(
        services.raise_service_request(
            principal.tenant_id,
            shape=services.SHAPE_RESTART_NOW,
            payload={
                "account_no": account.account_no,
                "account_id": account.id,
                "name": body.get("name") or on_file.get("legal_name"),
                "email": body.get("email") or on_file.get("email"),
                "phone": body.get("phone") or on_file.get("phone"),
                "address": selectors.service_address(account),
            },
        )
    )


urlpatterns += [
    # CR-068 wave G — CWP-041, the money list (US-CWP-048).
    path("portal/payments", payments),
    # CR-068 — CWP-046, the request hub (US-CWP-060). ⚠ NO account id: a portal
    # request carries no account at all (BR-CWP-026), so this read is the
    # LOGIN's set and there is nothing narrower it could be.
    path("portal/requests", request_hub),
    # CR-068 — CWP-052 (US-CWP-062). ⚠ THIS ONE DOES name the account, and the
    # reason is the money: the standing charge and the connection fee are the
    # ACCOUNT's own plan's, and a landlord holding four accounts has four
    # different answers. `_account_in_set` intersects it with the session's set
    # IN THE QUERY (BR-CWP-010); the front-end route carries no id at all.
    # CR-068 — CWP-032, the final bill (US-CWP-037). ⚠ It NAMES the account for
    # the same reason the two above do: a deposit belongs to one account, and a
    # landlord closing one property is not closing the other three.
    path("portal/accounts/<uuid:account_id>/final-bill", final_bill),
    # CR-068 — CWP-066, where level pay stands (US-CWP-055). ⚠ It sits UNDER
    # the existing `…/level-pay` read rather than beside it, because it is the
    # same subject asked a different question: `/level-pay` is *what would I
    # pay if I joined*, `/level-pay/standing` is *what am I paying and where do
    # I stand*.
    path("portal/accounts/<uuid:account_id>/level-pay/standing", level_pay_standing),
    path("portal/accounts/<uuid:account_id>/stop-or-restart", stop_or_restart),
    path("portal/accounts/<uuid:account_id>/stop-or-restart/ask", ask_to_stop_or_restart),
    # CR-183-BRC10 T8 — the hold's status on the account, and B4's restart ask.
    path("portal/accounts/<uuid:account_id>/temporary-stop", temporary_stop_status),
    path("portal/accounts/<uuid:account_id>/temporary-stop/restart", ask_to_restart_now),
    # CR-068 wave M — CWP-042 and CWP-043 (US-CWP-051 · US-CWP-052).
    path("portal/accounts/<uuid:account_id>/plans/preview", plan_preview),
    path("portal/accounts/<uuid:account_id>/plans/request", plan_request),
    path("portal/accounts/<uuid:account_id>/plans/current", plans_current),
]


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave L1 · `CWP-057` · `CWP-056` · `CWP-064` · `CWP-045`
# (US-CWP-057 · US-CWP-058 · US-CWP-059 · US-CWP-056)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **ALL FOUR ARE `no-store`, AND ON THESE FOUR IT MATTERS MOST.** A credit
# real on Tuesday can be spent by Thursday (`BR-CWP-047`); a tier reached this
# morning changes the date a customer thinks they have. A cached arrears screen
# is a screen that tells somebody they have longer than they do.
#
# ⚠ **EVERY ONE NAMES ITS ACCOUNT AND `_account_in_set` INTERSECTS IT WITH THE
# SESSION'S SET IN THE QUERY** (`BR-CWP-010`, `G96`). An account belonging to
# another customer of the same utility answers the same 404 an account that does
# not exist answers.


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def account_arrears(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/arrears` — `CWP-057`, the ladder and what it would cost.

    ⚠ **IT READS THIS ACCOUNT'S OWN DISCONNECTION CASE, NOT THE TENANT'S
    CADENCE** (`US-CWP-057` TC-4). Two accounts at different tiers answer
    different dates because they ARE different records.

    ⚠ **AN UNMAPPED TIER IS AN ABSENCE ON THE WIRE** (`BR-CWP-092`):
    `tier: null` with `tier_unmapped: true`. Rounding it to a neighbour would
    move the date a customer thinks they have, and would misstate to a regulator
    what that household was told.

    ⚠ **IT ALSO CARRIES `attached_answer`** — the one published help answer a
    clerk pinned to this screen (`CWP-060`'s second placement, `DEF-CWP-3945`).
    `null` is the ordinary case and closes the slot up (`BR-CWP-093`). The
    reader's language comes from `?locale=`, exactly as `guest_api.help_answer`
    takes it; a locale with no variant gets English with a line saying so
    rather than a blank (`BR-CWP-094`).

    ⚠ **NO REASON CODE FOR A WRITE-OFF IS IN THIS BODY** (`BR-CWP-051`).

    ⚠ **AND NO DEPOSIT FIGURE IS IN IT EITHER** — `OQ-CWP-1600`. The case
    records WHETHER a new deposit will be required and no rule in this product
    prices one, so `cost.subtotal` is the sum of the parts that exist and
    `cost.parts_missing` names the one that does not.
    """
    account = _account_in_set(request, account_id)
    # The reader's language, the way `guest_api.help_answer` already takes it —
    # the browser's own setting fills it in. `None` is English (`BR-CWP-094`).
    locale = request.query_params.get("locale") or None
    return _no_store(
        Response(selectors.arrears_position(account, as_of=date.today(), locale=locale))
    )


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def account_protections(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/protections` — `CWP-064`, three lifetimes (`BR-CWP-090`).

    ⚠ **THE PLAN HOLD CARRIES NO END DATE AND NONE IS INVENTED** (`US-CWP-059`
    TC-2): `ends_on: null` with `lifetime: derived_from_the_plan`. It lifts the
    day an instalment is missed and the plan itself stays active — nobody is
    dropped (PO 2026-08-11).

    ⚠ **A LIFTED PROTECTION IS SERVED, MARKED LIFTED** (TC-7).
    """
    account = _account_in_set(request, account_id)
    return _no_store(Response(selectors.protections_view(account, as_of=date.today())))


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def help_paying(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/help-paying` — `CWP-056`, three doors (`US-CWP-058`).

    ⚠ **THE MORATORIUM IS A FACT WITH `apply: false` ON IT** (TC-2) — the
    regulator sets the window and nobody applies for it, so there is nothing for
    a control to do.

    ⚠ **THE PLAN ROUTE IS ABSENT WHERE THE TENANT HAS PLANS OFF** (TC-6) and the
    other two remain: a customer who cannot have a plan can still send a
    certificate.
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    return _no_store(
        Response(selectors.help_paying(principal.tenant_id, account, as_of=date.today()))
    )


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def help_paying_ask(request: Any, account_id: str) -> Response:
    """`POST accounts/{id}/help-paying/ask` — the customer ASKS. `BR-CWP-089`.

    ⚠ **THIS CREATES A SERVICE REQUEST AND NOT A PROTECTION** (`US-CWP-058`
    TC-4). *"The portal may never grant a protection itself — every one needs a
    person and a document."* The response says `protection_created: false` on
    its face so no screen can imply otherwise.

    ⚠ **AND IT ACCEPTS NO FILE** (TC-5). Consumer upload is a signed deferral
    (`DF-4`, PO 2026-08-08); `bring_the_document: true` comes back so the
    confirmation ends at the counter rather than at a spinner.
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    body = request.data if isinstance(request.data, dict) else {}
    contact = customers_seam.contact_details(principal.tenant_id, [str(account.pk)])
    if not contact.get("phone"):
        # ⚠ **REFUSED BY NAME RATHER THAN SENT WITHOUT ONE**, exactly as the plan
        # ask is: `create_from_portal` requires a phone because the form's own
        # promise is *"we ring you only if we need to"*, and somebody who cannot
        # pay is the one a clerk will certainly ring. `CWP-024` is a route, not
        # a dead end.
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref="BR-CWP-089",
            message_key="portal.helpPaying.phoneNeeded",
            field_errors=[{"field": "phone", "code": errors.VAL_REQUIRED}],
        )
    return _no_store(
        Response(
            services.raise_service_request(
                principal.tenant_id,
                shape=services.SHAPE_HARDSHIP_ASK,
                payload={
                    #: ⚠ **THE NUMBER ON THE PAPER BILL, NEVER THE ROW ID**
                    #: (B14 rule 31).
                    "account_no": account.account_no,
                    "address": selectors.service_address(account),
                    "name": contact.get("legal_name"),
                    "email": contact.get("email"),
                    "phone": contact.get("phone"),
                    "route": body.get("route"),
                    "note": str(body.get("note") or ""),
                },
            ),
            status=201,
        )
    )


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def money_back(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/money-back` — `CWP-045` (`US-CWP-056`).

    ⚠ **ONE ROUTE, TWO HALVES, AND THEY ARE DIFFERENT THINGS.**
    `07-endpoints.md` §"Credits, refunds and adjustments" names
    `GET accounts/{id}/credits` and `GET accounts/{id}/refunds` separately;
    ONE screen reads both and the whole point of it is that they are shown
    TOGETHER and told apart (*"a credit comes off your next bill. A refund is
    money sent back."*). Two round trips for one screen would let the two halves
    be read a second apart, which on a figure `BR-CWP-047` forbids caching is
    exactly the wrong shape. **Decision logged 2026-09-04**; the body carries
    both under their own names, so the contract's two reads are both answered
    and neither is a second arithmetic.

    ⚠ **`no-store`, AND THE CREDIT IS RE-READ EVERY LOAD** (`BR-CWP-047`,
    TC-3): a credit real on Tuesday can be spent by Thursday.

    ⚠ **A VOIDED REFUND IS IN THE LIST** (TC-4), and `void_reason` is not.
    """
    account = _account_in_set(request, account_id)
    return _no_store(Response(selectors.money_back(account)))


# ⚠ **`+=`, NOT AN EDIT INTO A LIST ABOVE** — law 11, for the reason the two
# blocks above this one give.
urlpatterns += [
    # CR-068 wave L1 — CWP-057 · CWP-056 · CWP-064 · CWP-045.
    # ⚠ EVERY ONE CARRIES AN ACCOUNT ID IN THE REQUEST AND NONE OF THE FRONT-END
    # ROUTES DOES: the switcher names the account and a database id in an
    # address is a database id on screen (B14 rule 31) — `/account`'s reading,
    # and the plan routes' above.
    path("portal/accounts/<uuid:account_id>/arrears", account_arrears),
    path("portal/accounts/<uuid:account_id>/protections", account_protections),
    path("portal/accounts/<uuid:account_id>/help-paying", help_paying),
    path("portal/accounts/<uuid:account_id>/help-paying/ask", help_paying_ask),
    path("portal/accounts/<uuid:account_id>/money-back", money_back),
]


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave R — REQUESTS, QUERIES AND QUESTIONS
# `CWP-051` (US-CWP-063) · `CWP-055` (US-CWP-065) · `CWP-054` (US-CWP-066)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **FIVE ROUTES AND EVERY ONE OF THEM IS A SERVICE REQUEST.** `CR-072`, PO
# 2026-09-04, verbatim: *"all the request coming from portal should go in
# Service request"*. Querying a bill and asking a question are two SHAPES of the
# `service_request` write point that already exists (`write_points.py` is
# untouched, six kinds); adding a note is one of the THREE transitions
# `BR-CWP-075` signs the customer may make.
#
# ⚠ **WITHDRAWING WAS THE FOURTH AND IS RETIRED (PO ruling 2026-09-19,
# `OQ-CUS-12486`).** `BR-CWP-079` is SUPERSEDED, `BR-CWP-075` is AMENDED, the
# `withdraw` move left `service_request.TRANSITIONS`, and the route below
# stays only so a bookmarked tab or a replayed post reads a refusal rather
# than a 404. **It has no caller.**
#
# ⚠ **AND NOT ONE OF THEM CHANGES A BILL, A READING OR AN ACCOUNT**
# (CLAUDE.md hard rule 4, `BR-CWP-026`, `BR-CWP-042`).


def _request_of_mine(request: Any, reference: str) -> Any:
    """The request behind `CWP-051`, or a 404 — **one answer for three
    failures** (unknown, another customer's, another tenant's), so the refusal
    cannot be used to learn that a reference exists (`US-CWP-063` TC-7)."""
    row = selectors.my_request_row(_principal(request), reference=reference)
    if row is None:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    return row


def _required_text(body: dict[str, Any], field: str, *, br_ref: str, key: str) -> str:
    """A required sentence, or a refusal NAMING the field. Never a default —
    hard-won law 3, and a query with no reason tells the clerk who must judge it
    nothing at all (`metering.services.dispute_read` refuses for the same
    reason)."""
    text = str(body.get(field) or "").strip()
    if not text:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref=br_ref,
            message_key=key,
            field_errors=[{"field": field, "code": errors.VAL_REQUIRED}],
        )
    return text


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def request_detail(request: Any, reference: str) -> Response:
    """`GET requests/{reference}` — `CWP-051`, the customer-visible half.

    ⚠ **THE INTERNAL ROUTING NOTE IS NOT FILTERED BY THE SCREEN, IT NEVER
    LEAVES THE SERVER** (`BR-CWP-078`, `US-CWP-063` TC-2). The projection lives
    in `customers_seam._customer_visible_events`, which names what it drops and
    why; the test asserts the RESPONSE BODY, not the rendered page, because a
    field that is served and merely not drawn is still served.

    ⚠ **`no-store`**: *open for* moves with the calendar and *waiting on* moves
    when a clerk touches the row, so yesterday's copy is wrong today.
    """
    found = selectors.my_request_detail(
        _principal(request), reference=reference, today=date.today()
    )
    if found is None:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    return _no_store(Response(found))


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def request_withdraw(request: Any, reference: str) -> Response:
    """`POST requests/{reference}/withdraw` — ⚠ **IT REFUSES FROM EVERY STATE
    NOW, AND IT IS KEPT ON PURPOSE.**

    ⚠ **`BR-CWP-079` IS SUPERSEDED (PO ruling 2026-09-19, `OQ-CUS-12486`).**
    Verbatim: *"if customer dont want it - they will call and clark will refuse
    it. thats'it . keep it simple"*. The `withdraw` move left
    `service_request.TRANSITIONS` the same day, so there is no state a customer
    may withdraw from. `may_withdraw` reads that table, is false everywhere,
    and `TrackRequest` draws no control — **this route has no caller.**

    **WHY IT STAYS RATHER THAN BEING DELETED, stated because it is a choice and
    not an oversight.** A URL that has been live is not only called by our own
    screen: a bookmarked tab open since this morning, a retried request, a
    replayed form post. Deleting the route turns each of those into a 404 with
    nothing to say; keeping it turns them into the refusal the rule now makes,
    **in words a customer can read**. The same argument is why this edge still
    keeps no state list of its own.

    ⚠ **AND IT CANNOT 500 — THAT WAS CHECKED RATHER THAN ASSUMED.** `_apply`
    catches `ServiceRequestRuleError` from `next_state` and re-raises
    `BizError(BIZ_STATE, message_key="customers.serviceRequest.
    transitionNotAllowed")`, which is an ordinary refusal response. An unknown
    action and a disallowed one come back through the identical path, so
    removing the row from the table changed the REASON and not the shape.

    **What a customer who changes their mind does instead:** they ring the
    utility, and a clerk refuses the request with `Applicant withdrew` — one of
    the five reasons the Refuse dialog draws (blueprint p084).
    """
    row = _request_of_mine(request, reference)
    principal = _principal(request)
    return _no_store(
        Response(
            services.raise_service_request(
                principal.tenant_id,
                shape=services.SHAPE_WITHDRAW,
                payload={"request_id": row.pk},
            )
        )
    )


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def request_note(request: Any, reference: str) -> Response:
    """`POST requests/{reference}/notes` — the customer answers the clerk.

    ⚠ **THIS IS THE FIRST ROW IN THIS PRODUCT WITH `internal=False`.** The flag
    has existed since `service_request_events` was created and nothing has ever
    written it, because — in the column's own comment — *"there is no portal"*.
    There is one now (`BR-CWP-078`, `BR-CWP-075`).
    """
    row = _request_of_mine(request, reference)
    principal = _principal(request)
    body = request.data if isinstance(request.data, dict) else {}
    note = _required_text(
        body, "note", br_ref="BR-CWP-075", key="portal.request.noteNeeded"
    )
    return _no_store(
        Response(
            services.raise_service_request(
                principal.tenant_id,
                shape=services.SHAPE_NOTE,
                payload={"request_id": row.pk, "note": note},
            ),
            status=201,
        )
    )


def _two_decimals(amount: Any) -> str:
    """A stored 4-decimal money string as the 2 decimals a person reads.

    ⚠ **CLAUDE.md hard rule 2** — *"stored to 4 decimals … both DISPLAY 2"*.
    `ROUND_HALF_UP` is the product's own rounding (`core.money.finalize`), so a
    figure a customer reads here and the same figure on their bill cannot
    disagree in the last cent. A value that is not a number is returned
    untouched rather than crashing a request a customer is trying to send.
    """
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

    try:
        return str(Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError):
        return str(amount)


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def bill_dispute(request: Any, number: str) -> Response:
    """`POST bills/{number}/dispute` — `CWP-055`. **A MARKER, NEVER AN EDIT.**

    ⚠ **THE INVOICE IS READ AND NEVER WRITTEN.** `bill_facts` is
    `bill_in_set` — the same lookup every bill screen goes through, with both
    halves of `BR-CWP-010` in the query — and the row is used for three strings
    on a clerk's worklist. `US-CWP-065` TC-2 asserts the invoice is
    byte-identical afterwards: hard rule 4 says an issued invoice takes no
    UPDATE, and a query is a claim ABOUT a number rather than a change OF one.

    ⚠ **A SECOND QUERY ON THE SAME BILL IS REFUSED, WITH THE FIRST ONE'S
    REFERENCE** (TC-9) — the same posture `metering.services.dispute_read` takes
    on a read already carrying an uncleared marker: *"the second dispute would
    silently overwrite the first one's reason and actor … there is nothing to
    gain and a trail to lose."*

    ⚠ **THE CUSTOMER'S OWN READING IS EVIDENCE ON THE QUERY AND NOT A METER
    READ** (TC-8). It goes into the sentence a clerk reads; nothing writes a
    `meter_reads` row, which would put an unvalidated number where the bill run
    looks.
    """
    principal = _principal(request)
    from apps.portal.seams import billing_seam

    bill = billing_seam.bill_facts(list(principal.account_ids), number=number)
    if bill is None:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")

    body = request.data if isinstance(request.data, dict) else {}
    what = _required_text(body, "what", br_ref="BR-CWP-042", key="portal.dispute.whatNeeded")
    reason = _required_text(
        body, "reason", br_ref="BR-CWP-042", key="portal.dispute.reasonNeeded"
    )

    already = selectors.open_query_on(principal, bill_number=bill["number"])
    if already is not None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-042",
            message_key="portal.dispute.alreadyOpen",
            params={"reference": already.request_no},
        )

    account = _account_in_set(request, bill["account_id"])
    contact = customers_seam.contact_details(principal.tenant_id, [str(account.pk)])
    if not contact.get("phone"):
        # `create_from_portal` requires one — *"we ring you only if we need
        # to"*, and a queried bill is the one thing a clerk will certainly ring
        # about. `CWP-024` is a route, not a dead end.
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref="BR-CWP-042",
            message_key="portal.request.phoneNeeded",
            field_errors=[{"field": "phone", "code": errors.VAL_REQUIRED}],
        )
    return _no_store(
        Response(
            services.raise_service_request(
                principal.tenant_id,
                shape=services.SHAPE_DISPUTE,
                payload={
                    "bill_number": bill["number"],
                    "period": f"{bill['period_start']} to {bill['period_end']}",
                    # ⚠ **TWO DECIMALS, BECAUSE THIS STRING IS DISPLAYED**
                    # (`DEF-CWP-4198`, CLAUDE.md hard rule 2 — money is STORED
                    # to four decimals and DISPLAYS at two). It reads as a note
                    # for the clerk's worklist, and it is: but it is written
                    # into `what_they_said`, and `CWP-046` renders that column
                    # to the CUSTOMER as their own words. So a customer's own
                    # requests list was printing `142.1800 USD`. The rest of
                    # that sentence still reaches them — the marker, the ISO
                    # period and *"Their reason:"* — and that half is the open
                    # part of the same row, recorded as a known gap in
                    # `cr068-i-requests-and-disputes.mjs` rather than fixed
                    # here, because what this column should SHOW a customer is
                    # a design decision and not a formatting one.
                    "total": f"{_two_decimals(bill['total'])} {bill['currency']}",
                    "what": what,
                    "reason": reason,
                    "own_reading": str(body.get("own_reading") or "").strip(),
                    "address": selectors.service_address(account),
                    "name": contact.get("legal_name"),
                    "email": contact.get("email"),
                    "phone": contact.get("phone"),
                },
            ),
            status=201,
        )
    )


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def ask_a_question(request: Any) -> Response:
    """`POST questions` — `CWP-054`, and the bill travels with it.

    ⚠ **A QUESTION WITH NO BILL IS ACCEPTED** (`US-CWP-066` TC-5) — a general
    question routed by its topic. Refusing it would send somebody to the
    telephone for not knowing which bill they meant, which is the outcome this
    whole screen exists to avoid.

    ⚠ **A BILL NAMED HERE IS STILL INTERSECTED WITH THE SESSION'S SET IN THE
    QUERY** (`BR-CWP-010`): an unknown number and another login's bill answer
    the same 404, so this form cannot be used to learn which bills exist.

    ⚠ **THE SIGNED-IN VERSION KNOWS THE ACCOUNT ALREADY** (TC-2) — nobody
    retypes an address. When a bill is named the address is that bill's
    account's; otherwise it is the first account of the session's set, which is
    the account the switcher opens on.
    """
    principal = _principal(request)
    body = request.data if isinstance(request.data, dict) else {}
    what = _required_text(body, "what", br_ref="BR-CWP-076", key="portal.question.whatNeeded")
    topic = str(body.get("topic") or "").strip()

    bill_number = str(body.get("bill_number") or "").strip()
    account_id = None
    if bill_number:
        from apps.portal.seams import billing_seam

        bill = billing_seam.bill_facts(list(principal.account_ids), number=bill_number)
        if bill is None:
            raise errors.deny_as_not_found(br_ref="BR-CWP-010")
        bill_number = bill["number"]
        account_id = bill["account_id"]
    if account_id is None:
        ids = list(getattr(principal, "account_ids", ()) or ())
        if not ids:
            raise errors.deny_as_not_found(br_ref="BR-CWP-010")
        account_id = ids[0]

    account = _account_in_set(request, account_id)
    contact = customers_seam.contact_details(principal.tenant_id, [str(account.pk)])
    if not contact.get("phone"):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref="BR-CWP-076",
            message_key="portal.request.phoneNeeded",
            field_errors=[{"field": "phone", "code": errors.VAL_REQUIRED}],
        )
    return _no_store(
        Response(
            services.raise_service_request(
                principal.tenant_id,
                shape=services.SHAPE_QUESTION,
                payload={
                    "topic": topic or "something else",
                    "what": what,
                    "bill_number": bill_number,
                    "address": selectors.service_address(account),
                    "name": contact.get("legal_name"),
                    "email": contact.get("email"),
                    "phone": contact.get("phone"),
                },
            ),
            status=201,
        )
    )


# ⚠ **`+=`, NOT AN EDIT INTO EITHER LIST ABOVE** — law 11, the same reason the
# wave-G and wave-M blocks give.
#
# ⚠ **`{reference}` IS AN `SR-` NUMBER AND `{number}` IS A `BL-` NUMBER — NOT
# ONE DATABASE ID BETWEEN THEM** (B14 rule 31, PO 2026-08-30: *"no Databse ID on
# screen - that is a rule"*). Both are printed on paper the customer is holding
# and are what they would read out on the telephone.
urlpatterns += [
    # CR-068 wave R — CWP-051 (US-CWP-063).
    path("portal/requests/<str:reference>", request_detail),
    path("portal/requests/<str:reference>/withdraw", request_withdraw),
    path("portal/requests/<str:reference>/notes", request_note),
    # CR-068 wave R — CWP-055 (US-CWP-065). ⚠ It hangs off the BILL because
    # that is what is being questioned, and the bill lookup is the one every
    # other bill route goes through.
    path("portal/bills/<str:number>/dispute", bill_dispute),
    # CR-068 wave R — CWP-054 (US-CWP-066). ⚠ NO bill in the path: a question
    # with no bill is a normal question (TC-5), so the bill travels in the body
    # where it can be absent.
    path("portal/questions", ask_a_question),
]


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 phase 5 · CWP-039 — YOUR PAYMENT METHODS (US-CWP-046 · US-CWP-022)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THESE THREE VIEWS PERFORM NO ORM WRITE AND THAT IS DELIBERATE.** The rows
# live in `stored_payment_instruments`, which is a PAYMENTS table, so the write
# belongs to `apps.payments.instruments` — the same shape the contact-detail and
# account-link writes take through `apps.customers.portal_self_service`. What
# this edge owns is the authentication, the step-up proof and the refusal.
#
# ⚠ **AND A SEVENTH PORTAL WRITE POINT IS OWED FOR IT.** `write_points.py`
# declares six kinds and a saved instrument is none of them; its `payment` row
# lands in `payments`, which is the money movement rather than the instrument.
# It is not a `companion` either, by that file's own test — a companion has **no
# independent door**, and a customer saves a card without paying anything. The
# row is REPORTED for a ruling rather than taken, because that file says in as
# many words that one more kind is a ruling and not an edit.
#
# ⚠ **THE STEP-UP CODE HAS ITS OWN PURPOSE AND THAT IS THE WHOLE STORY**
# (`US-CWP-022` TC-3, `BR-CWP-040`). `PURPOSE_STEP_UP` is a fourth value in
# `models.CODE_PURPOSES`; `verify_code` filters on it, so the enrolment code
# that got somebody in does not match a row here and is refused without any
# check having to remember to look for it.


#: What the two write routes answer when no code was presented at all. A KEY —
#: eleven catalogues write the sentence (B14 rule 35) at five or six words
#: (rule 33).
CODE_NEEDED = "code_needed"


def _step_up_contact(principal: Any):
    """Where a step-up code goes: the contact already on file for this login.

    ⚠ **NOT AN ADDRESS FROM THE REQUEST.** A hijacked session that could nominate
    its own destination would defeat the entire step-up — so the destination
    comes from the account the switcher opens on, which is the account set's
    first entry, exactly as `ask_a_question` derives its address.
    """
    ids = list(getattr(principal, "account_ids", ()) or ())
    if not ids:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    account = customers_models.Account.objects.filter(
        tenant_id=principal.tenant_id, pk__in=ids
    ).first()
    if account is None:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    return account


def _credential_row(principal: Any):
    """The signed-in login's own `portal_credential` ROW, not its id.

    ⚠ **`issue_code` NEEDS THE OBJECT AND FAILS SILENTLY WITHOUT IT.** It writes
    `portal_credential_id=getattr(credential, "pk", None)`, so an id string
    lands as **NULL** — the code row is created, the response looks perfect, and
    `verify_code` can never find it again because it filters on that column.
    Nothing raises. (`issue_code`'s supersede filter and `verify_code` both use
    `getattr(x, "pk", x)` and accept either, which is exactly why the asymmetry
    is easy to miss.)
    """
    row = models.PortalCredential.objects.filter(
        tenant_id=principal.tenant_id, pk=principal.credential_id
    ).first()
    if row is None:  # pragma: no cover - the session authenticated against it
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    return row


def _prove_step_up(request: Any, body: dict) -> Response | None:
    """`None` when the code is good; the refusal Response when it is not.

    ⚠ **THE CODE IS CHECKED HERE AND THE WRITE HAPPENS ONLY AFTER IT IS.**
    `save_instrument` and `remove_instrument` have no way to check a code —
    their signatures carry none — and their docstrings say so rather than
    implying the check happened somewhere safe.
    """
    principal = _principal(request)
    given = str(body.get("code") or "").strip()
    if not given:
        return _no_store(Response({"saved": False, "reason": CODE_NEEDED}, status=400))
    verdict = credentials.verify_code(
        principal.tenant_id,
        purpose=models.PURPOSE_STEP_UP,
        code=given,
        credential=principal.credential_id,
    )
    if verdict != credentials.CODE_OK:
        return _no_store(Response({"saved": False, "reason": verdict}, status=400))
    return None


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def payment_method_step_up(request: Any) -> Response:
    """`POST payment-methods/step-up` — mint the code that lets a method change.

    ⚠ **THE RESPONSE CARRIES THE MASKED DESTINATION AND NOTHING MORE**
    (`BR-CWP-033`'s posture, one door along). Naming the contact would hand a
    hijacked session the address it needs to intercept the very code that is
    supposed to stop it.

    ⚠ **AN ACCOUNT WITH NO CONTACT DEAD-ENDS** (`BR-CWP-034`) — it must never
    fall back to something weaker, so there is no branch below that one.
    """
    principal = _principal(request)
    account = _step_up_contact(principal)
    channel, destination, masked = credentials.contact_for(principal.tenant_id, account)
    if channel is None:
        return _no_store(Response({"sent": False, "reason": "no_contact_on_file"}))
    issued = credentials.issue_code(
        principal.tenant_id,
        purpose=models.PURPOSE_STEP_UP,
        #: ⚠ THE CREDENTIAL, NOT THE ACCOUNT. An instrument hangs off the
        #: CUSTOMER — a landlord saves one card for four accounts — so the code
        #: that changes one is anchored to the LOGIN, which is what
        #: `verify_code` then filters on.
        credential=_credential_row(principal),
        channel=channel,
        masked=masked,
    )
    #: ⚠ **THE QUEUED ROW NAMES THE ENROLMENT TEMPLATE, BECAUSE IT IS THE ONLY
    #: CODE TEMPLATE PIN THIS PRODUCT HAS** — no template BODY exists for any of
    #: them yet (`notifications_seam.template_pin` says so, and the row holds at
    #: dispatch with that reason). A `portal_step_up_code` pin is owed by the
    #: wave that turns sending on; stating the absence here beats a second
    #: unwritten pin nobody can find.
    credentials.queue_code(
        principal.tenant_id, account=account, issued=issued, destination=destination
    )
    return _no_store(
        Response(
            {
                "sent": True,
                "sent_to": masked,
                "channel": channel,
                "expires_in_minutes": models.CODE_TTL_MINUTES,
            }
        )
    )


@api_view(["GET", "POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def payment_methods(request: Any) -> Response:
    """`GET` the list · `POST` a new method — `CWP-039` (`US-CWP-046`).

    ⚠ **THE LIST IS THE CUSTOMER'S, NOT AN ACCOUNT'S** (`03-field-map.md`
    §payments). A landlord holding four accounts saves one card and pays any of
    them with it, which is why there is no account id in this address and why
    `BR-CWP-010`'s intersection here is tenant AND *this login's customer*.

    ⚠ **NO `gateway_token` LEAVES THIS EDGE.** The served row's keys are a
    closed set and `US-CWP-046` TC-2 asserts exactly that set, so a serialiser
    that grew a field fails rather than shipping what the model gained.
    """
    from apps.payments import instruments

    principal = _principal(request)
    if request.method == "POST":
        body = request.data if isinstance(request.data, dict) else {}
        refusal = _prove_step_up(request, body)
        if refusal is not None:
            return refusal
        try:
            saved = instruments.save_instrument(
                principal,
                tenant_id=principal.tenant_id,
                customer_id=principal.customer_id,
                reference=str(body.get("reference") or ""),
                used_for=body.get("used_for") or None,
            )
        except instruments.LooksLikeACardNumber:
            # ⚠ THE REASON IS A KEY AND CARRIES NOTHING THAT WAS SENT. A refusal
            # that echoed the field would put a card number in a browser, a
            # proxy log and an error tracker (`BR-CWP-057`).
            return _no_store(Response({"saved": False, "reason": "not_a_reference"}, status=400))
        except ValueError:
            return _no_store(Response({"saved": False, "reason": "reference_needed"}, status=400))
        return _no_store(Response({"saved": True, "method": saved}, status=201))

    return _no_store(
        Response(
            {
                "methods": instruments.list_for_customer(
                    principal.tenant_id, customer_id=principal.customer_id
                ),
                #: `BR-CWP-056` — the refusal travels WITH the list so the
                #: screen can disable the control and write the reason on it,
                #: rather than hiding a control the customer went looking for.
                "autopay": instruments.autopay_stance(
                    principal.tenant_id, list(principal.account_ids)
                ),
                #: `OQ-1394` CLOSED 2026-09-04 — the tenant's stance, and no
                #: figure, because there is no processor to price one from.
                "card_fee": instruments.card_fee_stance(),
            }
        )
    )


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def payment_method_remove(request: Any, instrument_id: str) -> Response:
    """`POST payment-methods/{ref}/remove` — off the list, softly.

    ⚠ **A `POST` AND NOT A `DELETE`, BECAUSE THE STEP-UP CODE TRAVELS IN THE
    BODY** — the same shape `requests/{reference}/withdraw` already takes. A
    code in a query string is a code in a browser history and a proxy log.

    ⚠ **SOMEBODY ELSE'S METHOD ANSWERS THE SAME 404 AS ONE THAT DOES NOT
    EXIST** (`BR-CWP-010`), so the id space cannot be walked to learn what the
    utility holds.
    """
    from apps.payments import instruments

    principal = _principal(request)
    refusal = _prove_step_up(request, request.data if isinstance(request.data, dict) else {})
    if refusal is not None:
        return refusal
    try:
        instruments.remove_instrument(
            principal,
            tenant_id=principal.tenant_id,
            customer_id=principal.customer_id,
            instrument_id=instrument_id,
        )
    except instruments.NotYours:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010") from None
    return _no_store(Response({"removed": True}))


# ⚠ **`+=`, NOT AN EDIT INTO ANY LIST ABOVE** — law 11, and phase 5 has four
# lanes committing this one file at once.
#
# ⚠ **`{ref}` IS A ROW ID IN A URL AND NEVER A VALUE ON A SCREEN.** B14 rule 31
# forbids a database id as the visible value of a field; it says nothing about
# an address, and `Methods.dom.test.tsx` asserts the id never renders. There is
# no customer-facing number for a saved card — the brand and four digits are
# what a person recognises, and neither is unique.
urlpatterns += [
    # CR-068 phase 5 — CWP-039 (US-CWP-046 · US-CWP-022).
    path("portal/payment-methods", payment_methods),
    path("portal/payment-methods/step-up", payment_method_step_up),
    path("portal/payment-methods/<str:instrument_id>/remove", payment_method_remove),
]


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 phase 5 · lane D — `CWP-040` autopay (US-CWP-047) · `CWP-050` fees
# (US-CWP-050). The refund half of `CWP-045` needs NO new route: it rides
# `accounts/{id}/money-back`, which already exists, because a customer reads
# credits and refunds on ONE screen and a second round trip would let the two
# halves be a second apart on a figure `BR-CWP-047` forbids caching.
# ═══════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def autopay_position(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/autopay` — `CWP-040` (`US-CWP-047`).

    ⚠ **A GET AND NOTHING ELSE, AND THAT IS THE STORY.** `US-PAY-024` TC-5 is
    *"any v1 code path attempts to charge the stored method → Impossible — no
    charging path exists before rails"*, and it is enforced by there being
    nothing to call. This edge does not become the exception: there is no POST
    on this route, no *Turn autopay on*, no *Retry autopay* and no body a screen
    could send. The control on the screen is visible, disabled and carries its
    reason (`BR-CWP-056` / `CR-068` R3).

    ⚠ **`no-store`** (`BR-CWP-047`) — the scheduled figure is money.
    """
    account = _account_in_set(request, account_id)
    from apps.payments import autopay as payments_autopay

    return _no_store(Response(payments_autopay.portal_position(account_id=account.pk)))


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def fees_due(request: Any) -> Response:
    """`GET fees` — `CWP-050` (`US-CWP-050`).

    ⚠ **NO REFERENCE IN THE ADDRESS AND NONE ACCEPTED FROM THE CALLER.** The
    request is found through `my_requests`, which matches on the tenant AND on a
    telephone number one of this login's own accounts holds (`BR-CWP-010`) — so
    a stranger cannot ask what `SR-26-0061` costs, and `SR-26-0061` never
    appears in a browser history either.

    ⚠ **NO ACCOUNT ID EITHER**, and for a different reason from the other
    account-less routes: an APPLICANT may not have an account yet. The fees
    belong to the REQUEST, and the request belongs to the person.

    ⚠ **A REQUEST NOT YET APPROVED ANSWERS `any: false`** (`US-CWP-050` TC-8):
    fees are quoted after approval, and the SERVER is what decides that rather
    than a screen choosing not to draw a table it was sent.
    """
    principal = _principal(request)
    phones = customers_seam.contact_phones(
        principal.tenant_id, list(getattr(principal, "account_ids", ()) or ())
    )
    return _no_store(Response(paying.fees_position(principal.tenant_id, phones=phones)))


# ⚠ **`+=`, AND AT THE END OF THE FILE** — law 11, the same reason every block
# above this one gives: a blob written over a shared `urlpatterns` literal is how
# one lane's route silently replaces another's, with a correct file count.
urlpatterns += [
    # CR-068 phase 5 — CWP-040 (US-CWP-047). ⚠ The ACCOUNT is in the request and
    # not in the front-end address: the switcher names it, and a database id in
    # a URL is a database id on screen (B14 rule 31).
    path("portal/accounts/<uuid:account_id>/autopay", autopay_position),
    # CR-068 phase 5 — CWP-050 (US-CWP-050). ⚠ NO id and NO reference: see the
    # view's own docstring. The fees belong to a request, the request belongs to
    # a person, and the person is the session.
    path("portal/fees", fees_due),
]


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 phase 5 · lane B — `CWP-038` Pay now (`US-CWP-045`) and the inbound
# settlement door (`US-CWP-006`)
#
# ⚠ **A NEW SECTION AND A NEW `urlpatterns +=`, NOT AN EDIT INTO ANY LIST
# ABOVE** — hard-won law 11, the same reason the wave-G, wave-M and wave-R
# blocks give. Four lanes are appending to this file in four worktrees at once,
# and a pathspec commit takes the whole working-tree content of every path it
# names: the second lane to commit would silently revert the first, with a
# correct file count, its own hunks present and nothing anywhere looking wrong.
#
# ⚠ **THE IMPORTS ARE HERE RATHER THAN IN THE HEADER, FOR THE SAME REASON.**
# The import block at the top of this file is four lines every lane wants to
# widen at once; these five are in this lane's own region, where a merge can see
# them. Python binds a module-level import wherever it appears.
# ═══════════════════════════════════════════════════════════════════════════
from decimal import Decimal, InvalidOperation  # noqa: E402

from django.utils import timezone  # noqa: E402

from apps.payments import webhooks  # noqa: E402
from apps.portal.seams import pay_now_seam  # noqa: E402


def _pay_now_amount(body: dict[str, Any]) -> Decimal:
    """The figure the customer typed, as a Decimal — **never a float**.

    CLAUDE.md hard rule 2 at the edge. A browser sends a string; turning it into
    a `float` on the way in is how `$292.87` becomes `$292.87000000000003`, and
    a payment is immutable the instant it commits (hard rule 4).
    """
    raw = body.get("amount")
    if isinstance(raw, float):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            br_ref="BR-PAY-002",
            message_key="portal.payNow.amountNotAFigure",
            field_errors=[{"field": "amount", "code": errors.VAL_FORMAT}],
        )
    try:
        amount = Decimal(str(raw).strip())
    except (InvalidOperation, AttributeError, TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            br_ref="BR-PAY-002",
            message_key="portal.payNow.amountNotAFigure",
            field_errors=[{"field": "amount", "code": errors.VAL_FORMAT}],
        ) from None
    if amount <= Decimal("0"):
        raise errors.ValidationError(
            errors.VAL_RANGE,
            br_ref="BR-PAY-002",
            message_key="portal.payNow.amountMustBePositive",
            field_errors=[{"field": "amount", "code": errors.VAL_RANGE}],
        )
    return amount


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def pay_now(request: Any, account_id: str) -> Response:
    """`GET accounts/{id}/pay-now` — everything `CWP-038` draws before anything
    is typed: the balance, the open bills, the saved methods, and **whether the
    Pay control may be pressed and why not**.

    ⚠ **THE REFUSAL IS SERVED, NOT INFERRED BY THE SCREEN** (`BR-CWP-056`).
    Whether this utility has connected a processor, whether the account is
    cash-only and whether this login holds `pay` are all facts the server has and
    the browser does not. A screen that guessed would be one deploy away from
    offering a live-looking button over nothing at all — which is
    `DEF-CWP-3925`, the defect this product paid for on the morning this was
    written.
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    return _no_store(
        Response(
            pay_now_seam.pay_now(
                account.pk,
                customer_id=principal.customer_id,
                may_pay=principal.may(account.pk, "pay"),
            )
        )
    )


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def pay_now_preview(request: Any, account_id: str) -> Response:
    """`POST accounts/{id}/pay-now/preview` — **where it will land, before it
    commits** (`BR-CWP-058`). Writes nothing.

    ⚠ **A POST THAT WRITES NOTHING, FOR `plan_preview`'S OWN REASON:** the
    amount travels in a body, and a figure somebody is still thinking about does
    not belong in a cacheable URL. `writes: []` is on the response so a caller
    can tell a preview from a commit without knowing which route it called.

    ⚠ **AND IT MINTS THE IDEMPOTENCY KEY** (`US-CWP-045` TC-7). The key has to
    exist *before the first request leaves*, and the first request leaves on the
    commit below — so a key minted there could never cover the one case it is
    for. The screen keeps what comes back and presents the same string on the
    commit and on every retry of it.
    """
    account = _account_in_set(request, account_id)
    body = request.data if isinstance(request.data, dict) else {}
    return _no_store(
        Response(
            pay_now_seam.preview(
                account.pk,
                amount=_pay_now_amount(body),
                key=str(body.get("idempotency_key") or "").strip() or None,
            )
        )
    )


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def pay_now_commit(request: Any, account_id: str) -> Response:
    """`POST accounts/{id}/pay-now/commit` — ask the tenant's provider for the debit.

    THE ORDER, and every step of it is a rule rather than a preference:

      1. **The account is intersected with the session's set IN THE QUERY**
         (`BR-CWP-010`, `US-CWP-045` TC-8) — refused before any money moves, with
         the same 404 an account that does not exist gets.
      2. **The held reason is re-checked on the SERVER** (TC-2, TC-9). Forcing
         the disabled control writes no payment row, no audit row and makes no
         gateway call, because a screen order is not the security — the posture
         `set-password` already takes on this edge.
      3. **The charge**, with the key the preview minted.
         `apps/payments/gateway.py` is the only place in this product that asks
         for a debit, and which provider answers is the tenant's integration
         connection (PO ruling 2026-09-05).
      4. **On an approval only**, the settlement is recorded through the SAME
         door a real processor's callback comes through — so the payment row, the
         oldest-bill-first allocation, the balanced ledger pair and the audit row
         are the existing tested ones and not a second set.

    ⚠ **A TIMEOUT RETURNS AT STEP 3 AND WRITES NOTHING** (TC-6). The response
    says so and carries the same key back, so the retry presents it again and the
    debit is never taken twice. *A zero is a claim nobody can make.*
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    body = request.data if isinstance(request.data, dict) else {}
    return _no_store(
        Response(
            pay_now_seam.pay(
                account.pk,
                customer_id=principal.customer_id,
                may_pay=principal.may(account.pk, "pay"),
                amount=_pay_now_amount(body),
                instrument_id=str(body.get("instrument_id") or "").strip() or None,
                key=str(body.get("idempotency_key") or "").strip() or None,
                portal_actor={
                    "portal_customer_id": str(principal.customer_id),
                    "portal_session_id": str(principal.session_id),
                    "channel": "customer_portal",
                },
            )
        )
    )


def _webhook_event_id(request: Any) -> str:
    """The provider's own event id, out of the body it signed.

    ⚠ **NOT OUT OF THE PATH OR A HEADER.** It is what guard 1 dedupes on
    (`uq_payment_webhook_events_event`), so it has to be a field the SIGNATURE
    covers — a retry identified by something outside the signed bytes could be
    forged into a fresh delivery.
    """
    body = request.data if isinstance(request.data, dict) else {}
    return str(body.get("id") or body.get("event_id") or "").strip()


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PortalTenantThrottle])
@portal_admission
def payments_webhook(request: Any, provider: str) -> Response:
    """`POST portal/webhooks/payments/{provider}` — the gateway's own callback.

    ⚠ **UNAUTHENTICATED BY CONSTRUCTION AND THAT IS NOT A HOLE.** A payment
    processor holds no login here. What guards it is an HMAC-SHA256 signature
    over the RAW BODY BYTES against a secret only this deployment and that
    provider hold, and **a deployment with no configured secret refuses every
    delivery** (hard-won law 3 — the unsafe option must be the one you type).
    `authentication_classes([])` is deliberate for the enrolment routes' reason
    too: a stale staff cookie must not 401 a provider and must not enter any
    context.

    ⚠ **THE TENANT COMES FROM THE PATH AND NEVER FROM THE PAYLOAD**
    (`US-CWP-006` TC-6, `BR-TEN-003`). `TenantMiddleware` reads
    `/api/{tenant}/…` and sets `app.tenant_id` from it; a provider is configured
    with one callback URL per utility. A body naming its own tenant would be a
    way to put money on any account of any utility.

    ⚠ **THIS MOUNTS WORK THAT WAS ALREADY BUILT AND COULD NOT BE REACHED.**
    `apps/payments/webhooks.py` has been 577 lines with 15 tests since
    2026-09-03 and its own lifecycle block records the gap by name: *"the
    endpoint that calls this is NOT mounted by this lane … `ingest` is written,
    tested and callable; mounting it is REPORTED as the remaining half. Hard-won
    law 2 in the open: the service exists and no gateway can reach it yet."*
    This is that half.

    ⚠ **THE ADDRESS DIVERGES FROM `07-endpoints.md` §4 BY ONE PREFIX, AND THE
    DIVERGENCE IS DELIBERATE.** The contract writes it
    `POST /webhooks/payments/{provider}` with no tenant segment — and a route
    with no tenant segment can resolve a tenant only from the body, which is the
    one input `BR-TEN-003` forbids reading. Mounted here it is
    `/api/{tenant}/portal/webhooks/payments/{provider}`: the same shape, one
    prefix along, with the tenant where the middleware can see it.

    **A refused delivery still answers 200.** A provider retrying a 500 forever
    over a bad account number helps nobody; the refusal is in the body with its
    reason and the delivery row records it either way.
    """
    require_tenant(request)
    return _no_store(
        Response(
            _webhook_view(
                webhooks.ingest(
                    provider=provider,
                    event_id=_webhook_event_id(request),
                    raw_body=request.body,
                    signature=(
                        request.headers.get("X-Signature")
                        or request.headers.get("X-Webhook-Signature")
                    ),
                    received_at=timezone.now(),
                )
            )
        )
    )


def _webhook_view(result: Any) -> dict[str, Any]:
    """What a provider is told back — **and it is deliberately almost nothing**.

    ⚠ `US-CWP-006` TC-4: *"a settlement for an unknown reference is refused and
    recorded, and the response does not reveal whether the reference exists."*
    So the body carries the delivery's own status and no account fact, no
    balance, no name and no payment number.

    ⚠ **AND `problems[].detail` IS DROPPED, WHICH THE TEST FOUND RATHER THAN THE
    AUTHOR.** The first draft served the whole problem dict, and `payments`'
    refusal for an unknown account reads *"account
    '10490b14-078e-45fe-adc5-f91aee40eb28' is not an account of this tenant"* —
    which echoes the caller's own id back at them, names the rule, and answers
    the exact question TC-4 says must not be answered. It is `DEF-CWP-3926`'s
    lesson on a different surface: **`detail` is a sentence addressed to a
    DEVELOPER**, and a diagnostic channel that grows a code whenever a module
    finds a gap is a standing promise that the next one is published too.
    **The CODE travels and the sentence does not.** A support engineer reads the
    delivery row (`payment_webhook_event.outcome` holds the whole sentence);
    the response goes to a machine.
    """
    return {
        "status": result.status,
        "created": result.created,
        "signature_verified": result.signature_verified,
        "problems": [
            {"code": one.get("code"), "br_ref": one.get("br_ref")} for one in result.problems
        ],
    }


urlpatterns += [
    # CR-068 phase 5 — CWP-038 (US-CWP-045). ⚠ The account is in the PATH and is
    # intersected with the session's set in the query (`BR-CWP-010`); it is never
    # a visible value on the screen (B14 rule 31).
    #
    # ⚠ THE COMMIT IS `…/pay-now/commit` AND NOT A `POST` ON `…/pay-now`, which
    # was checked rather than assumed: Django matches whole patterns, so the
    # GET read and a POST commit could share one address — but the three routes
    # then differ only by verb, and the one that takes a customer's money would
    # be the one that is hardest to see in this list. The address says what it
    # does.
    path("portal/accounts/<str:account_id>/pay-now", pay_now),
    path("portal/accounts/<str:account_id>/pay-now/preview", pay_now_preview),
    path("portal/accounts/<str:account_id>/pay-now/commit", pay_now_commit),
    # CR-068 phase 5 — US-CWP-006. ⚠ UNAUTHENTICATED, SIGNED, AND THE TENANT
    # COMES FROM THE PATH. See `payments_webhook`.
    #
    # ⚠ ORDER IS SAFE AND WAS CHECKED RATHER THAN ASSUMED: `portal/webhooks/…`
    # is claimed by no other include (`apps.payments.api` declares `payments`
    # and `payments/summary`; `reversal_api` and `amendments_api` declare
    # three-segment `payments/<id>/…` patterns), and nothing else in this file
    # declares a `portal/webhooks` prefix.
    path("portal/webhooks/payments/<str:provider>", payments_webhook),
]


def notifications_seam_verdicts() -> Any:
    """The three document verdicts, resolved rather than imported at module load.

    `apps/portal` imports its seams inside function bodies everywhere (`G81`
    reads this file), and the two document routes above need the same constants
    the seam publishes. One accessor, so the vocabulary has ONE home.
    """
    from apps.portal.seams import notifications_seam

    return notifications_seam


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def document_file(request: Any, reference: str) -> Any:
    """`GET documents/{reference}/file` — `CWP-031`/`CWP-041`, a copy of it.

    ⚠ **`CR-085` `CPB-14`. THE LIST HAS NAMED EVERY DOCUMENT SINCE
    `US-CWP-036` AND WOULD OPEN ONLY A BILL.** A receipt and a letter carried
    the row control disabled with the words *"We kept no copy of this."* — a
    sentence that is FALSE about every one of them whose copy we did keep, and
    the only way a customer could tell was to be told the truth by somebody on
    the telephone.

    ⚠ **IT IS THE SAME `download` PERMISSION AS THE BILL** (`US-CWP-034`
    TC-7). A delegate invited with *See* may read the list — knowing a letter
    was sent is part of seeing an account — and taking away a COPY of it is a
    separate grant. An account holder always has it.

    ⚠ **`attachment` UNLESS `?view=1`**, exactly as `bill_document_pdf` does,
    and for its reason: a customer who pressed *Download* means it, and the
    inline branch exists so a screen can frame the document rather than
    handing over a file the browser then hides in a folder.

    ⚠ **A NUMBER THAT IS NOT THIS ACCOUNT'S IS THE SAME 404 AS A NUMBER THAT
    NEVER EXISTED** (`BR-CWP-041`) — one answer, so nobody can probe.
    """
    principal = _principal(request)
    served = selectors.document_file(list(principal.account_ids), reference=reference)
    verdict = served["verdict"]
    if verdict == "not_found":
        raise errors.deny_as_not_found(br_ref="BR-CWP-041")
    # ⚠ **THE `download` GRANT IS PER ACCOUNT AND IS CHECKED AGAINST THE
    # DOCUMENT'S OWN ACCOUNT** (`US-CWP-034` TC-7), never against the screen the
    # customer happened to be on. A delegate invited with *See* over one of a
    # landlord's three properties may read that account's list and may not take
    # a copy; the other two are not theirs at all and never reached this line.
    if served["account_id"] is not None and not principal.may(served["account_id"], "download"):
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    if verdict == "unavailable":
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-083",
            message_key="portal.documents.queueUnavailable",
        )
    if verdict == notifications_seam_verdicts().DOCUMENT_NOT_TRUSTED:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-NOT-027",
            message_key="portal.document.notTrusted",
        )
    if verdict != notifications_seam_verdicts().DOCUMENT_OK or served["payload"] is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-045",
            message_key="portal.documents.noCopyKeptRefusal",
            params={"reference": reference},
        )
    response = HttpResponse(
        served["payload"], content_type=served["content_type"] or "application/pdf"
    )
    inline = str(request.query_params.get("view", "")).lower() in {"1", "true", "yes"}
    disposition = "inline" if inline else "attachment"
    response["Content-Disposition"] = f'{disposition}; filename="{served["filename"]}"'
    return _no_store(response)


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def account_documents_bundle(request: Any, account_id: str) -> Any:
    """`GET accounts/{id}/documents/year.zip` — `CWP-031`'s *Download a year*.

    ⚠ **`CR-085` `CPB-15`, AND THE HOLD IT REPLACES WAS A HOLD ON NOTHING NEW.**
    The control read *"Downloads are not ready yet"* and its row in `holds.ts`
    said *"No file-serving path exists in apps/portal at all"* — which stopped
    being true on the day `US-CWP-034` shipped `bill_document_pdf`, and the note
    was never re-read. Same store, same permission, same bytes; what was
    actually missing was somebody asking for more than one at a time.

    ⚠ **THE ARCHIVE CARRIES THE FROZEN FILES AND NOTHING ELSE** — no cover
    page, no index, no merge. Anything composed here would be a document the
    customer was never sent (`BR-CWP-045`).

    ⚠ **THE COUNT TRAVELS ON A HEADER SO THE SHORTFALL IS VISIBLE**
    (`X-Documents-Kept` of `X-Documents-Listed`). A year in which three letters
    were never frozen is a SHORTER archive, and an archive that quietly dropped
    them would be the check that cannot fail.
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    if not principal.may(account.pk, "download"):
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    bundle = selectors.documents_bundle(account, today=date.today())
    if bundle["verdict"] == "unavailable":
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-083",
            message_key="portal.documents.queueUnavailable",
        )
    if bundle["verdict"] != "ok" or bundle["payload"] is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-045",
            message_key="portal.documents.yearEmpty",
        )
    response = HttpResponse(bundle["payload"], content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{bundle["filename"]}"'
    response["X-Documents-Kept"] = str(bundle["kept"])
    response["X-Documents-Listed"] = str(bundle["listed"])
    return _no_store(response)


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def plan_agreement_current(request: Any, account_id: str) -> Any:
    """`GET accounts/{id}/plans/current/agreement` — `CWP-043`'s *↓ Agreement*.

    ⚠ **`CR-085` `CPB-14`, AND IT IS `CPB-03`'S HOLD FOUND A SECOND TIME.**
    Wave 1 released the agreement on `CWP-063`, the screen that shows an OFFER,
    and left `portal.yourPlan.agreementHeld` standing on `CWP-043`, the screen
    that shows the plan a customer is actually ON — reading *"Downloads arrive
    later this year"* over the same document class, out of the same store,
    behind the same permission. Both rows were `unwatched`, which is the kind of
    hold `G103` says in as many words it cannot see.

    ⚠ **ADDRESSED AS *THIS ACCOUNT'S LIVE PLAN*, NOT BY A PLAN ID** (B14 rule
    31, and `current_plans`' own note: a customer holds at most one live plan).
    Two live plans would be a data fault rather than a shape this address has to
    carry, and the newest is served with the same posture the screen draws.

    ⚠ **`download` IS ITS OWN GRANT** (`US-CWP-034` TC-7), exactly as on the
    offer route: a delegate invited with *See* may read the schedule and may not
    take a copy of the agreement.
    """
    account = _account_in_set(request, account_id)
    principal = _principal(request)
    if not principal.may(account.pk, "download"):
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    from apps.portal.seams import notifications_seam, payments_seam

    plan_id = payments_seam.live_plan_id(account.pk, as_of=date.today())
    if plan_id is None:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    verdict, page, content_type, _name = notifications_seam.stored_document_service(
        source_type="plan", source_id=plan_id
    )
    if verdict == notifications_seam.DOCUMENT_NOT_TRUSTED:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-NOT-027",
            message_key="portal.document.notTrusted",
        )
    if verdict != notifications_seam.DOCUMENT_OK or page is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-045",
            message_key="portal.planOffer.agreementNotKept",
        )
    response = HttpResponse(page, content_type=content_type or "application/pdf")
    # A NAME, never a row id — the same filename the offer route serves, because
    # a customer meets one name for one thing.
    response["Content-Disposition"] = 'attachment; filename="payment-plan-agreement.pdf"'
    return _no_store(response)


urlpatterns += [
    # ⚠ **`CR-085` `CPB-14`/`CPB-15`. `year.zip` IS DECLARED BEFORE
    # `<str:reference>/file`** — the same order `bill_document_pdf` states is
    # load-bearing for `document.pdf`: both patterns sit under the same prefix
    # and Django matches in order, so the static one has to come first or a
    # reference called `year.zip` would swallow it. Checked rather than
    # assumed: `year.zip` is not a lawful `invoice_no` or `payment_no` in any
    # series this product mints, so nothing real is shadowed either way.
    path("portal/accounts/<str:account_id>/documents/year.zip", account_documents_bundle),
    # ⚠ **THE SINGLE DOCUMENT IS ADDRESSED BY ITS OWN NUMBER AND NOT UNDER AN
    # ACCOUNT**, the same shape `portal/bills/<number>/document.pdf` already
    # has: a number identifies one document across everything this login holds,
    # and `CWP-041` lists a landlord's payments across three accounts on one
    # screen. The BUNDLE stays account-scoped because *a year of documents* is
    # a question about one account, which is what `CWP-031` is showing.
    path("portal/documents/<str:reference>/file", document_file),
    # CR-085 CPB-14 — CWP-043's own agreement, beside CWP-063's.
    path(
        "portal/accounts/<str:account_id>/plans/current/agreement",
        plan_agreement_current,
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# `CR-142-BRC07` Phase 4 · `P4.15` — THE PROPERTY STATEMENT, SCOPED
# ═══════════════════════════════════════════════════════════════════════════
# ⚠ **A NEW SECTION AND A NEW `urlpatterns +=`, NOT AN EDIT INTO ANY LIST
# ABOVE** — the note at line ~3064 says why, and it is CLAUDE.md law 11's
# whole-file hazard one file down: a blob written over a shared `urlpatterns`
# literal is how a sibling's route leaves the branch with every check green.
#
# WHAT THIS ROUTE IS, IN ONE SENTENCE: report `R24c` *Statement · by premises*
# as the customer portal is allowed to serve it — **the signed-in person's own
# accounts at one property and nobody else's** (`P4.15`, ruled option (a)).
# The scoping is in `apps/portal/premises_statement.py`, which explains at
# length why it is not a filter over the staff report.


@api_view(["GET"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])  # NFR-39 · DEF-CWP-3931
@portal_admission
def premises_statement_view(request: Any, account_id: str) -> Response:
    """`GET portal/accounts/{id}/premises-statement` — `CWP-078`.

    ⚠ **`from`/`to` ARE REQUIRED AND ARE NOT DEFAULTED TO *THIS MONTH*.** A
    statement is a document about a stated period; a route that quietly chose
    one would put a window on the page that the reader did not ask for and
    would answer a bookmark differently next month. `BR-TEN-043` also forbids
    reading the wall clock where the caller holds the date, and the caller
    here is the screen.

    ⚠ **THE SUBJECT IS AN ACCOUNT, NOT A PREMISES, AND NO UUID REACHES THE
    BROWSER'S ADDRESS BAR** (B14 rule 31, as `portalRoutes.tsx` reads it): the
    screen is served at `/portal/property` with nothing in the path, the
    shell's switcher says which account, and what the page prints is the
    ADDRESS, walked to `premises` (hard rule 8). `premises_statement.py`'s
    docstring records the whole of why.
    """
    principal = _principal(request)
    params = paging.portal_params(
        request,
        allowed_sorts=("unit", "balance"),
        default_sort="unit",
        default_dir="asc",
    )

    def read(window: Any) -> tuple[list[dict[str, Any]], int]:
        body, total = premises_statement.premises_statement(
            principal,
            account_id,
            start=_required_date(request, "from"),
            end=_required_date(request, "to"),
            params=window,
        )
        roll_up.update({key: value for key, value in body.items() if key != "rows"})
        return body["rows"], total

    roll_up: dict[str, Any] = {}
    body = paging.windowed("rows", params, read)
    body.update(roll_up)
    return _no_store(Response(body))


def _required_date(request: Any, name: str):
    """`?from=2026-09-01` → a date, and anything else refused BY NAME.

    A missing or malformed bound is a validation error naming the field, never
    a silently substituted default — see the note on the view above.
    """
    raw = request.query_params.get(name)
    if not raw:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="portal.statement.period_required",
            params={"field": name},
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="portal.statement.period_malformed",
            params={"field": name, "value": str(raw)},
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from None


urlpatterns += [
    path(
        "portal/accounts/<uuid:account_id>/premises-statement",
        premises_statement_view,
    ),
]
