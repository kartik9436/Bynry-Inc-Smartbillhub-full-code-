# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-041 (EP-INT-11) — the partner surface (S1), the access log
#           S142 reads (S2), the inward register row (TC-8) and the audited
#           grant (S5, unblocked by OQ-INT-1481 option (a) on 2026-09-04).
# Rules:    BR-INT-035 · BR-INT-044 · BR-INT-045 (the status numbers are the
#           manifest's, never typed here) · BR-INT-054 (the payload's meaning
#           is Runbooks') · BR-TEN-003 (the tenant is the path) · CLAUDE.md
#           hard rule 1 · hard rule 7 (the grant writes audit_log) ·
#           B14 rule 33 (five or six words) · B8/LAW 0 (thin views)
# Tests:    06-backend/tests/test_us_int_041_partner_surface.py (TC-1..TC-9)
# Impacts:  config/urls.py (one include line, inside the tenant list) ·
#           07-frontend/src/features/integrations/AccessLogPanel.tsx ·
#           07-frontend/src/api/integrationsEndpoints.ts
# ───────────────────────────────────────────────────────
"""The partner's door and the manager's window onto it — two audiences, one wave.

    THE PARTNER (no session, a key, a machine)
    GET  /api/partner/v1/reference             every code we emit, with its word
    GET  /api/partner/v1/accounts              their accounts
    GET  /api/partner/v1/consumer-info         one account, by its number
    GET  /api/partner/v1/bills                 the nested bill, a GL code a line
    GET  /api/partner/v1/payments              the payment, its tender, its GL
    GET  /api/partner/v1/ledger                the books
    GET  /api/partner/v1/bill-download/        one bill as a printed page
    POST /api/partner/v1/make-payment/         ⚠ THE ONE WRITE — money in
    GET  /api/{utility}/v1/openapi.json        what those will do
    GET  /api/partner/v1/customers             RETIRED `410` → partner/v1/accounts
    GET  /api/{utility}/v1/payments            RETIRED `410` → partner/v1/…
    GET  /api/{utility}/v1/billing             RETIRED `410` → partner/v1/bills

    THE MANAGER (signed in, on S142)
    GET  /api/{utility}/integrations/{key}/access-log     who has been reading
    GET  /api/{utility}/integrations/subprocessors        the register, derived
    POST /api/{utility}/integrations/{key}/grant          the audited grant

⚠ **THE TENANT IS IN THE PATH ON THE RETIRED PAIR AND IN NONE OF THE FIVE**
(`DEF-INT-5546`, PO ruling 2026-09-16). The two `v1/…` addresses above still carry it
and resolve it through `TenantContextMiddleware`; the isolation cases (TC-5,
TC-7) are properties of the database there rather than lines of code somebody
keeps writing. **The five phase-2 addresses resolve it from the KEY instead** —
the same database property, arrived at through `integration_key_directory`
rather than through a URL segment — and they are registered in
`partner_urls.py`, mounted OUTSIDE the tenant include, which carries the
argument and the PO's own words.

⚠ **EVERY PARTNER VIEW IN THIS MODULE OPTS OUT OF THE DEFAULT AUTHENTICATOR**,
and each does it explicitly with `authentication_classes = []`, because a
partner presents a KEY and never a session cookie. That is the same opt-out the
four genuinely public routes use, and `tests/test_be_default_authentication.py`
asserts the opt-out list EXACTLY, so one more cannot appear unnoticed — if that
test goes red naming this file, the answer is to add the new address to its list
deliberately, never to widen the assertion.

⚠ **THIS SAID *THESE THREE* UNTIL 2026-09-17 AND THERE WERE ELEVEN.** It was
written when there were three and it was never amended as waves 2–5,
`CR-111-BRC04` and `DEF-INT-5623`'s retirement each added one; the count was a
claim nothing re-checked, which is this repository's own commonest rot (a rule
that restates what a tool does — name the tool and let a reader run it). The
TEST is the authority: `PUBLIC_ROUTES` in that file is the list, and it is
exact.

⚠ **THE REFUSAL IS BUILT IN EXACTLY ONE PLACE** (`_refused()`), and every path
that will not serve goes through it. An address off the allowlist, a wrong key
and a revoked key are the same bytes with the same status — see
`runners/serve.py` for why, and `test_us_int_041_partner_surface.py` for the
three of them printed side by side.

⚠⚠ **THIS SURFACE WAS READ-ONLY UNTIL 2026-09-24 AND IT IS NOT ANY MORE.**
`POST /api/partner/v1/make-payment/` lets Invoice Cloud post us a payment a
customer made on their portal — PO 2026-09-18, *"they post to us daily"*, with
the whole design walked and confirmed on 2026-09-24 (decision log, *"THE
INVOICE CLOUD *MAKE PAYMENT* API, CONFIRMED BEFORE A LINE IS WRITTEN"*). Three
things a lane reading this file should know before touching that route:

  * **It shares `_admit` and adds no authorisation of its own.** Checks 1–8 are
    one function for nine addresses, and the one that creates money is the
    worst possible place for a second answer to *may this caller act*.
  * **What makes it a write is a SCOPE, not a flag.** `record_payment` is an
    operation only `pay_invoicecloud_partner` declares; a key that does not
    name it is refused by check 5, in the same bytes an unknown key gets. No
    ERP key can reach it, and no key issued before that operation existed holds
    it — so nothing became able to create money by the route landing.
  * **`BR-INT-071` still SAYS `make-payment` is not built, under a dated clause
    that reverses it.** That rule was CONFIRMED on 2026-09-17 and superseded
    the next day. `BR-INT-083` is the rule this address implements; read the
    status column, not the body (CLAUDE.md, the prime directive's own warning).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from django.http import HttpResponse, JsonResponse
from django.urls import path
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    renderer_classes,
)
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.integrations import models, newworld, partner_csv, reference, shapes, subprocessors
from apps.integrations.registry import REGISTRY
from apps.integrations.runners import serve
from apps.integrations.seams import billing as billing_seam
from apps.integrations.seams import customers as customers_seam
from apps.integrations.seams import ledger as ledger_seam
from apps.integrations.seams import payments as payments_seam
from core import audit as core_audit
from core import errors
from core.permissions import SettingsReadAnyWriteSystemAdmin
from core.tenancy import require_tenant

# ════════════════════════════════════════════════════════════════════════
# WHAT THE PUBLISHED CONTRACT SAYS THIS DOOR WANTS (`DEF-INT-6529`)
# ════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE DOOR WAS NEVER OPEN. THE SIGN ON IT WAS WRONG, AND ONLY THE SIGN.**
# Every view below opts out of the session authenticator with
# `authentication_classes = []` — deliberately, because a partner presents a
# KEY and never a cookie — and then calls `_admit`, whose checks 1–8 refuse a
# caller with no key at all. Measured on PostgreSQL 16 through the real router
# on 2026-09-24: all ten phase-2 addresses, `POST make-payment` among them,
# answer `404 {"error": "We cannot serve this request.", "code": "REFUSED"}`
# to a request carrying no `Authorization` header, cause `KEY_UNKNOWN`.
#
# **What was wrong is what we PUBLISHED.** drf-spectacular reads security off
# a view's AUTHENTICATORS, and an empty list plus `AllowAny` is exactly the
# shape a genuinely public route has — so it emitted `security: [{}]` on 23
# partner operations, which in OpenAPI means *this endpoint needs no
# credentials*. A partner's engineer reading our contract, or a generated
# client built from it, was told the payment endpoint takes no key. That is a
# lie about a money path, and it is what `DEF-INT-6529` is.
#
# ⚠ **THE FIX IS DOCUMENTATION AND TOUCHES NO RUNTIME PATH.**
# `extend_schema(auth=…)` overrides only what the schema generator emits;
# `authentication_classes` does not move, so `tests/test_be_default_
# authentication.py`'s exact `PUBLIC_ROUTES` list needs no widening — which is
# the property that proves the two halves are independent.

#: The name this surface's credential publishes under. ⚠ **ONE SPELLING, AND
#: `core/openapi.py` IMPORTS IT RATHER THAN RETYPING IT.** An operation that
#: names a scheme `components.securitySchemes` does not declare is an INVALID
#: OpenAPI document that every generator reads differently and no test in this
#: repository would have noticed — the same reasoning
#: `serve.ISSUED_KEY_BLIND_INDEX_CONTEXT` is imported under, one layer up.
PARTNER_KEY_SCHEME_NAME = "partnerKey"

#: What that scheme IS. `http`/`bearer` because `_presented_key` reads
#: `Authorization: Bearer …` and nothing else — the placement each manifest
#: declares (`Auth(mode="they_hold_ours", placement="bearer")`).
PARTNER_KEY_SECURITY_SCHEME = {
    "type": "http",
    "scheme": "bearer",
    "description": (
        "A key we issued to this partner, presented as `Authorization: Bearer "
        "sbh_live_…`. It is the ONLY credential this surface accepts: there is no "
        "session, no cookie and no utility in any path — the key names its own "
        "connection, which names the utility, and every read is scoped by it. "
        "A request with no key, an unknown key, a revoked or expired key, a key "
        "presented from an address the connection does not allow, a key whose "
        "scope does not name the operation, and a disabled connector are all "
        "refused with the SAME 404 and the same body, in the same time "
        "(BR-INT-044): the refusal is deliberately not a diagnosis."
    ),
}

#: ⚠ **EVERY PARTNER VIEW IN THIS FILE CARRIES THIS, AND THE TEST CHECKS THE
#: RULE RATHER THAN A LIST.** `tests/test_def_int_6529_partner_key_scheme.py`
#: asserts it of *every view here that opts out of the authenticator*, so a
#: fourteenth partner door cannot arrive documented as public — the same shape
#: as `tests/test_be_default_authentication.py`'s exact list, and for the
#: reason `DEF-INT-4256` records: a list somebody must remember to extend is a
#: list that will be forgotten.
partner_key_required = extend_schema(auth=[{PARTNER_KEY_SCHEME_NAME: []}])

#: The manifests a partner reading from us connects through — **DERIVED, not
#: typed.** Data, not a branch (`G77` fails a gate on `provider_key`
#: branching): the mode `they_hold_ours` is declared on each manifest and read
#: here, never switched on.
#:
#: ⚠ **THIS WAS THE SINGLE STRING `"gl_partner"` UNTIL `CR-110-BRC04`**, when
#: the blueprint replaced one generic finance card with five named ERPs
#: (p162). Deriving the set rather than listing it is what makes a SIXTH ERP
#: one manifest file and no line of code, which is `BR-INT-037` — and it is
#: also what stops this constant becoming the next thing that goes stale when
#: a connector is added: there is nothing here to forget to update.
def partner_provider_keys() -> tuple[str, ...]:
    """Every connector a partner READS FROM US through, from the registry.

    `they_hold_ours` is the one relationship in this product where we never
    dial: they present a key we issued. Read at call time rather than at
    import so a manifest registered later still counts.
    """
    return tuple(
        manifest.key
        for manifest in REGISTRY.all()
        if manifest.auth.mode == "they_hold_ours"
        and manifest.operations
        # ⚠ **THE QUADRANT, NOT THE AUTH MODE — AND GETTING THAT WRONG COST A
        # 500 IN PLACE OF A REFUSAL.** The first draft asked only for
        # `they_hold_ours` and `we_never_dial`, which is TRUE OF THE PAYMENT
        # KIOSK TOO: the kiosk also holds a key we issued and we never dial it.
        # But the kiosk is the INBOUND door — they SEND us payments — and it
        # declares `refused: 401` where an ERP declares `404`. So `_status_for`
        # saw two numbers, could not choose, and raised: every refusal on this
        # surface came back **500 instead of 404**, which is the enumeration
        # oracle `BR-INT-044` exists to close, opened by a tidier-looking
        # predicate. Six tests caught it.
        #
        # `direction == "out" and initiative == "them"` is the SERVE quadrant —
        # the pair `runners.runner_for()` reads on the server and the same test
        # `AccessLogPanel.tsx` makes on the client, whose own comment predicted
        # this day: *"it would go quietly wrong the day a second partner
        # manifest is registered."* It did not go quietly, because the quadrant
        # is the question that actually decides it.
        #
        # ⚠⚠ **AND THIS READ `all(one.direction == "out" and one.initiative ==
        # "them" …)` UNTIL 2026-09-24, WHEN IT DROPPED INVOICE CLOUD ENTIRELY.**
        # The paragraph above is right about WHY the kiosk must be excluded and
        # wrong about the TEST, and the difference did not show until a partner
        # connector gained a write: `pay_invoicecloud_partner` now declares
        # `record_payment` (`in · them`), **so `all(out …)` answered False and
        # the whole connector fell out of this set** — every one of its six
        # LIVE read addresses would have refused its own customer's key with
        # the five words, on the day a real utility is being onboarded. The
        # comment two paragraphs up predicted the shape of this
        # (*"it would go quietly wrong the day a second partner manifest is
        # registered"*); it did not go quietly either time, because
        # `test_the_partner_connector_resolves_to_its_own_dialect` names the
        # connector and went RED.
        #
        # **The question this predicate is actually asking is *does this
        # connector publish an address on THIS surface*,** and the honest way
        # to ask it is to look for one. The kiosk declares no `served_path` at
        # all — it is reached at `/integrations/inbound/{key}/{operation}`,
        # a different door with a different authenticator — so it is still
        # excluded, by the fact that decides it rather than by a proxy for it.
        # The quadrant was that proxy: true of every door on this surface right
        # up until one of them started taking money.
        # ⚠⚠ **AND THE FIRST ATTEMPT AT THIS FIX WAS ALSO WRONG, IN THE
        # OPPOSITE DIRECTION, AND IS RECORDED RATHER THAN QUIETLY CORRECTED.**
        # It read `any(op.served_path.startswith("/partner/v1/"))`, which
        # DROPPED FOUR LIVE ERP CONNECTORS — `erp_workday`, `erp_sap`,
        # `erp_infor` and `erp_msgp` declare no `served_path` at all (they
        # inherit the phase-1 pair; `partner_openapi`'s own fallback map says
        # so), so the set went from six connectors to three. **That is the
        # exact failure being fixed, moved onto four other partners.**
        #
        # **The question is not what a manifest DRAWS; it is whether this DOOR
        # SERVES anything it declares.** `SERVED_ROUTES` is that list — it is
        # what binds an address to the operation `_admit` checks a key's scope
        # against — so a connector belongs here when it declares an operation
        # this door actually serves. Derived, exact, and it answers all four
        # cases without a branch: the five ERPs qualify on `serve_customer`
        # and friends, Invoice Cloud on those plus `record_payment`, and the
        # payment KIOSK does not qualify at all, because `payments`,
        # `account_lookup` and its siblings are not addresses on this surface —
        # they are reached at `/integrations/inbound/{key}/{operation}`, a
        # different door with a different authenticator.
        and any(one.name in _SERVED_OPERATIONS() for one in manifest.operations)
    )


def _SERVED_OPERATIONS() -> frozenset[str]:
    """Every operation THIS DOOR serves, from the route table itself.

    Read at call time, like `partner_provider_keys` above and for the same
    reason: a route added to `SERVED_ROUTES` counts immediately, and there is
    nothing here to forget to update.
    """
    return frozenset(name for name, _label in SERVED_ROUTES.values())

#: `partner_paged` — the partner's declared envelope, NOT the DRF `{count,
#: next}` shape (TC-6). Declared per operation in the manifest; the four key
#: names are the partner's and are spelled here once.
#
# ⚠ **THE DEFAULT IS 1,000 SINCE `CR-110-BRC04` PHASE 2 AND THE CEILING HAS
# NOT MOVED.** PO 2026-09-16, verbatim: *"make this as 1000 per page"*. A
# month-end walk of the largest utility this product models — 40,000 accounts,
# the top of T5 — is then **40 calls** rather than 80, which finishes inside
# forty seconds at the manifest's sixty a minute. `MAX_PAGE_SIZE` was already
# 1,000, so a partner asking for more is still clamped and not refused.
#
# ⚠ **WE PUBLISH `page_size` AND THE VENDOR'S DOCUMENT SAYS `limit`** — a
# recorded divergence (`CR-110-BRC04` phase 2). One partner's spelling is not a
# reason to rename a parameter on a surface every partner shares, and a second
# accepted spelling would be two names for one value, which is `DEF-014`.
DEFAULT_PAGE_SIZE = 1000
MAX_PAGE_SIZE = 1000


# ════════════════════════════════════════════════════════════════════════
# CR-110-BRC04 PHASE 2 · THE FIVE ADDRESSES, DECLARED ONCE
# ════════════════════════════════════════════════════════════════════════
#
# ⚠ **`partner`, NEVER `aclarian`.** PO 2026-09-16: *"why aclarian in it - we
# cna make it generic - saying partner - so that we can give it to anyone who
# needs bills for any csutomer if autherised"*. The supplied specification
# wrote `/api/ix/aclarian/…`; building that would have made one vendor a URL
# segment and broken *one base URL for every partner*. Aclarian is a KEY.
#
# ⚠⚠ **AND THE UTILITY IS NOT IN THE PATH — THIS NOTE SAID THE OPPOSITE UNTIL
# 2026-09-16 AND THAT WAS `DEF-INT-5546`.** It read: *"what is mounted is
# `/api/<utility>/partner/v1/…`, because these routes sit inside the tenant
# include and cannot leave it: BR-TEN-003 reads the tenant from the PATH and
# from nothing else, and with no tenant context RLS FORCE returns zero rows for
# the credential lookup — for a VALID key as much as an invalid one, so the door
# would be incapable of passing."* **The premise is true and the conclusion does
# not follow.** It is true of a TENANT table, and it forces the utility into the
# URL only if the FIRST lookup has to be against one. Blueprint p159, *WHY NOT
# PUT IT IN THE PATH*, answers it in order: `key ──► connection ──► tenant ──►
# app.tenant_id set ──► RLS does the isolating`. `integration_key_directory`
# (migration `0011`) is that first arrow and is NOT a tenant table.
#
# PO 2026-09-16, verbatim: *"we agreed not to use utility names in partner apis
# that was our rule - so these urls are not corect - we will resolve utility
# name using keys"*.
#
# The five addresses are `/api/partner/v1/…` and they are registered in
# `apps/integrations/partner_urls.py`, not in this file's `urlpatterns`. One
# base URL, the same for every partner and every utility.
#
# ⚠ **ALL FIVE ARE DECLARED NOW AND ONLY TWO ARE BUILT, DELIBERATELY.** Three
# sibling lanes fill in customers, bills+payments and the ledger, each in its
# own SEAM file; declaring the table here once means none of them edits this
# module and no two of them edit it at the same time (law 11). An address that
# is not built yet answers `501` and NAMES ITS WAVE — never a silent 404, which
# is this surface's refusal and would read as *wrong key*, and never an empty
# list, which would read to a finance system as *this utility has no bills* and
# be posted as such.
PARTNER_PREFIX = "partner/v1"

#: `{route segment: (operation name, the word a manager's run row uses)}`.
#: The operation names are the manifest's — `services.start_run` refuses
#: anything else, which is how a route and a manifest cannot drift apart.
SERVED_ROUTES = {
    # ── `DEF-INT-5623` — `customers` WAS THE SEGMENT UNTIL 2026-09-17 ───────
    # PO, looking at the Invoice Cloud connector on the live deployment: *"it
    # should be account and not customer - theya re lookung for details for
    # accounts not customer id"*. Every VALUE this route serves was already the
    # account's — PO 2026-09-16, *"Customers = accounts"* — so no test could
    # have caught it: what was wrong was the NAME, on the screen row, in this
    # address and in the payload's keys, and nothing compares a ruling's
    # vocabulary against the surface that carries it.
    #
    # ⚠ **THE OLD ADDRESS IS RETIRED, NOT DELETED.** `RETIRED_FOR` below gives
    # it a `410` that names this one. It was one day old (`DEF-INT-5546` moved
    # it out of the tenant path on 2026-09-16) and the connector the PO looked
    # at reads *Not set up* with KEYS IN USE 0 — but Aclarian and four other
    # ERP manifests share this one route table and are all `live`, and a `404`
    # here is this surface's REFUSAL, so a partner who had the old address
    # would read *your key is bad* and go looking at their credentials.
    "accounts": ("serve_customer", "Accounts"),
    "bills": ("serve_bill", "Bills"),
    "payments": ("serve_payment", "Payments"),
    "ledger": ("serve_ledger", "Ledger"),
    # ── `CR-111-BRC04`, AMENDED BY `DEF-INT-5622` ──────────────────────────
    # ⚠ **THIS READ `("serve_customer", "Customers")` UNTIL 2026-09-17 AND THE
    # REASONING FOR THE CHANGE IS IN `manifests/pay_invoicecloud_partner.py`.**
    # The old note said a second address onto one door was safer than a second
    # tick, because a clerk who switched accounts off switched this off too.
    # The cost of that safety was that the address could not be SEEN — an
    # operation with no `served_path` draws no row, so the screen showed four
    # APIs where five existed and the PO reported it (`DEF-INT-5622`).
    #
    # Its own operation gives the clerk the same control in a stronger form —
    # two rows, two ticks, each saying what it opens — instead of one tick
    # silently governing two addresses.
    "consumer-info": ("serve_consumer_info", "One account"),
    "bill-download": ("serve_document", "Bill document"),
    # ── `CR-132-BRC07` — NEW WORLD / LOGOS ────────────────────────────────
    # ⚠ **A SEPARATE ADDRESS, NOT A PARAMETER ON `payments`, AND THE REASON
    # IS THE SHAPE RATHER THAN THE FORMAT.** PO 2026-09-22: *"i think we
    # shoudl create seperate enpoint - you can se the same components that
    # you use, dont write completely new code"*. XML is already a supported
    # codec, so *parameterise it* was the first answer offered and it was
    # wrong: our Payment is one flat row and their Receipt is four levels
    # with a balancing rule across two of them. Bending `/payments` into that
    # would change a contract four ERP manifests already consume.
    #
    # **Everything beneath this address is shared** — the door, the payments
    # seam, the ledger seam's GL resolution. What is new is one view.
    "receipts": ("serve_receipt", "Receipts"),
    # ── 2026-09-24 · THE FIRST WRITE ON THIS SURFACE ──────────────────────
    # ⚠ **EVERY OTHER ROW IN THIS TABLE IS A `GET` AND THIS ONE IS A `POST`
    # THAT CREATES MONEY.** It is here rather than in a table of its own for
    # one reason and it is the important one: `SERVED_ROUTES` is what binds an
    # address to the operation `_admit` checks the key's scope against, and a
    # write registered beside this table instead of in it would be a write that
    # never met check 5. The operation is `record_payment`, declared ONLY by
    # `pay_invoicecloud_partner`, so no ERP key can reach this address at all.
    #
    # The address keeps Invoice Cloud's own word and their own trailing slash,
    # the way `bill-download/` does: `make-payment` is the name in THEIR
    # document, and `partner_urls` registers both spellings anyway.
    "make-payment": ("record_payment", "Make payment"),
}

#: Which wave lands each one. Read by `_not_yet_served` so the sentence a
#: partner gets and the plan in the CR cannot disagree, and asserted by
#: `test_cr110_phase2_partner_reference.py` against `SERVED_ROUTES`.
ROUTE_WAVE = {
    # ⚠ **EMPTY, AND EVERY ROW LEFT IN ITS OWN WAVE'S COMMIT.** `customers`
    # (wave 2), `ledger` (wave 5) and now `bills` and `payments` (waves 3 and
    # 4) all serve, so no address answers *not built yet* any more. Removing
    # the row is the SECOND of the two acts a wave is made of — landing the
    # payload is the first, and only the first feels like the work; it is
    # `test_the_unbuilt_routes_go_red_the_day_their_wave_lands` that makes the
    # second a failure rather than a thing to remember, and it went red on
    # these two rows before they moved.
    #
    # ⚠ **THE DICT STAYS RATHER THAN BEING DELETED WITH ITS LAST ROW.** A sixth
    # address arrives declared-before-built exactly as these four did, and the
    # hold, its `501`, and the case that fires the day it expires are the
    # mechanism that worked four times in one day. `_not_yet_served` and
    # `_partner_route` are unreachable while this is empty; removing them is
    # the phase-2 closing lane's, with `SERVED_ROUTES` in front of it.
}

#: `CR-110-BRC04` phase 2 · the reference endpoint's own window.
#:
#: ⚠ **IT IS NOT AN OPERATION AND THEREFORE NOT A ROW ON THE SCREEN.** The PO
#: ruled FOUR API rows; a fifth operation would put a fifth tick beside *What
#: they may read* for a document that carries no utility's records and that
#: every valid key may read. So it is metered under its own window key, which
#: `rate_limit_for` resolves to `DEFAULT_RATE_LIMIT_PER_MINUTE` — 100 a minute,
#: the product default, for a document a partner is meant to pull once and
#: cache. A ceiling it cannot reach is still a ceiling (hard-won law 3).
REFERENCE_WINDOW = "partner_reference"


# ═══════════════════════════════════════════════════════════════════════════
# The one refusal
# ═══════════════════════════════════════════════════════════════════════════


def _status_for(outcome: str) -> int:
    """BR-INT-045 — the numbers are the manifest's and this file holds none.

    Every partner manifest declares `envelope_status = {"ok": 200, "refused":
    404}` on every operation, so a refusal is a `404`: indistinguishable from
    a route that does not exist, which is the strongest thing it can be.

    ⚠ **THE FIVE ERPs HAVE TO AGREE, AND THAT IS ASSERTED RATHER THAN
    ASSUMED** (`CR-110-BRC04`). One surface answers all five; if two of them
    ever declared different numbers, the number a partner got would depend on
    which manifest happened to be read first — a difference nothing downstream
    could see. A disagreement raises here instead.
    """
    seen = {
        int(status)
        for key in partner_provider_keys()
        for operation in REGISTRY.require(key).operations
        if (status := (operation.envelope_status or {}).get(outcome))
    }
    if len(seen) == 1:
        return seen.pop()
    raise errors.SysError(code="SYS-001")  # pragma: no cover — the registry validates this


def _refused() -> JsonResponse:
    """The ONE body. Five words (B14 rule 33), ONE code, no trace id, no field
    that could differ between the six reasons.

    ⚠ **THE `code` IS A CONSTANT AND CARRIES NOTHING (`CR-110-BRC04`).** The PO
    asked for a refusal code in the API response and got one on every refusal —
    but the six auth causes share `serve.SHARED_REFUSAL_CODE`, because a code
    that named the cause would tell a caller holding a stolen key that the key
    is real and only the address was wrong. **This function takes no argument,
    deliberately**: there is no parameter for a later lane to thread a cause
    through, and `_serve` below could not vary the body if it wanted to.

    ⚠ A `JsonResponse` rather than a DRF `Response` on purpose: DRF's renderer
    negotiates content and can vary the body with an `Accept` header, and a
    refusal that changes shape with a header is a refusal that carries
    information. This one is the same bytes every time.
    """
    return JsonResponse(
        {"error": serve.REFUSAL_SENTENCE, "code": serve.SHARED_REFUSAL_CODE},
        status=_status_for("refused"),
    )


def _rate_limited(exc: serve.PartnerRateLimited) -> JsonResponse:
    """`429` with `Retry-After` (TC-4). Reachable only by a caller who already
    authenticated, so the extra information it carries is information they
    already have.

    ⚠ **THE ONE PLACE A CAUSE REACHES A PARTNER (`CR-110-BRC04`).** `exc.code`
    is `RATE_LIMIT_REACHED` or `COUNTER_UNAVAILABLE` — rows 1 and 2 of the PO's
    table, the two they ruled distinct on the wire. A partner that has been
    calling us for an hour can now tell *you have had your hundred* from *we
    could not count, come back* and stop retrying into an outage, and neither
    sentence tells them anything about a key. The `error` text is the same five
    words as every other refusal, so nothing a clerk or a log-scraper reads
    changes shape."""
    response = JsonResponse(
        {"error": serve.REFUSAL_SENTENCE, "code": exc.code}, status=429
    )
    response["Retry-After"] = str(exc.retry_after_s)
    return response


# ═══════════════════════════════════════════════════════════════════════════
# The partner surface
# ═══════════════════════════════════════════════════════════════════════════


def _refusal_schema() -> dict[str, Any]:
    """What a partner is told a refusal looks like (`CR-110-BRC04`).

    ⚠ **THE ENUM HAS EXACTLY ONE VALUE AND THAT IS THE DOCUMENT BEING HONEST.**
    A partner reading this learns that every refusal carries a code and that the
    code is always the same one — which is true, and is the whole of what
    `BR-INT-044` lets us say. **The six causes are NOT listed here**, and a lane
    adding them to be helpful would publish the enumeration map this module
    exists to withhold, in the one place a caller is invited to read.
    """
    return {
        "type": "object",
        "properties": {
            "error": {"type": "string", "example": serve.REFUSAL_SENTENCE},
            "code": {"type": "string", "enum": [serve.SHARED_REFUSAL_CODE]},
        },
    }


def _rate_limited_schema() -> dict[str, Any]:
    """The `429`, which DOES name which of two things happened.

    Safe for one stated reason and no other: a `429` is only reachable by a
    caller who has already authenticated. `COUNTER_UNAVAILABLE` is the one the
    PO asked for — a partner can stop retrying into an outage of ours instead of
    reading *rate limit reached* and slowing itself down for an hour.
    """
    return {
        "type": "object",
        "properties": {
            "error": {"type": "string", "example": serve.REFUSAL_SENTENCE},
            "code": {"type": "string", "enum": list(serve.WIRE_CODES)},
        },
    }


def _make_payment_schema() -> dict[str, Any]:
    """What a partner is told a payment looks like (2026-09-24).

    ⚠ **IT IS DERIVED FROM THE READER'S OWN FIELD CONSTANTS, NOT RETYPED.**
    `invoice_cloud_payment` refuses a body by those names; a second hand-written
    list here would be a specification that could disagree with the endpoint it
    describes, and the disagreement would present to a partner as *your request
    is malformed* about a request built from our own document (`DEF-014`'s
    shape, on the one surface where being wrong costs a support cycle at both
    ends).

    ⚠ **`tenant_id` AND `company_id` ARE PUBLISHED AS ACCEPTED, WHICH IS THE
    HONEST THING TO SAY.** They are read, put on the run row and compared
    against nothing (PO 2026-09-17). Omitting them from the document would tell
    a partner whose integration already sends them that they are unrecognised;
    marking them required would be a check we do not make.
    """
    from apps.integrations import invoice_cloud_payment as ic

    text = {"type": "string"}
    return {
        "type": "object",
        "required": [
            ic.FIELD_ACCOUNT,
            ic.FIELD_BILL,
            ic.FIELD_REFERENCE,
            ic.FIELD_DATE,
            ic.FIELD_AMOUNT,
            ic.FIELD_METHOD,
        ],
        "properties": {
            ic.FIELD_ACCOUNT: {**text, "description": "The account number, exactly as /partner/v1/accounts returned it."},
            ic.FIELD_BILL: {**text, "description": "The bill number, exactly as /partner/v1/bills returned it."},
            ic.FIELD_REFERENCE: {**text, "description": "Your own immutable id for this payment. The same value twice is one payment."},
            ic.FIELD_DATE: {**text, "description": "DD-MM-YYYY or YYYY-MM-DD."},
            ic.FIELD_AMOUNT: {**text, "description": "Greater than zero. A string keeps the exact figure."},
            ic.FIELD_CURRENCY: {**text, "description": "Three letters. Omit for the account's own."},
            ic.FIELD_METHOD: {**text, "description": "How it was paid. Cash, cheques and money orders are not taken here."},
            ic.FIELD_MEMO: text,
            ic.FIELD_TENANT: {**text, "description": "Accepted and recorded; it selects nothing."},
            ic.FIELD_COMPANY: {**text, "description": "Accepted and recorded; it selects nothing."},
        },
    }


def _presented_key(request: Any) -> str | None:
    """`Authorization: Bearer …` — the placement the manifest declares
    (`Auth(mode="they_hold_ours", placement="bearer")`). Read as data."""
    header = request.META.get("HTTP_AUTHORIZATION") or ""
    prefix = "bearer "
    if header.lower().startswith(prefix):
        return header[len(prefix) :].strip() or None
    return None


def _source_address(request: Any) -> str | None:
    """Imported from identity rather than re-derived.

    ⚠ THE ALLOWLIST IS ONLY AS GOOD AS THIS ANSWER, so it must not be a second
    implementation. `identity.auth.client_ip` honours `X-Forwarded-For` only to
    the depth of `settings.TRUSTED_PROXY_COUNT` (default 0), which means a
    caller cannot spoof its own source address by sending the header. A private
    copy here would be one deploy away from disagreeing with that, and the
    disagreement would open the allowlist rather than close it.
    """
    from apps.identity.auth import client_ip

    return client_ip(request)


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _page_params(request: Any) -> tuple[int, int]:
    def _int(name: str, fallback: int) -> int:
        try:
            return int(request.GET.get(name, fallback))
        except (TypeError, ValueError):
            return fallback

    page = max(1, _int("page", 1))
    # ⚠ **`limit` IS ACCEPTED AS A SYNONYM FOR `page_size` (`CR-111-BRC04`), AND
    # THIS IS A RECORDED REVERSAL.** `CR-110-BRC04` phase 2 declined it in as
    # many words — *"one partner's spelling is not a reason to rename a parameter
    # on a surface every partner shares, and a second accepted spelling would be
    # two names for one value, which is `DEF-014`"*. That reasoning held while
    # the choice was RENAME-OR-NOT. It is now ACCEPT-OR-BREAK: Invoice Cloud's
    # document sends `limit`, a real utility is being onboarded on it, and a
    # partner whose page size is silently ignored does not fail — it pages
    # through 40,000 accounts a thousand at a time believing it asked for ten,
    # which is the kind of wrong that shows up as a timeout six weeks later.
    #
    # **`DEF-014` is answered rather than waved at.** What it forbids is two
    # names for one value in what we PUBLISH. We publish `page_size` and only
    # `page_size` — in the envelope, in the OpenAPI document and in the CSV
    # headers — and `limit` is accepted on the way IN and named nowhere on the
    # way out. ⚠ **`page_size` WINS WHEN BOTH ARE SENT**, because it is the one
    # we document; a caller sending both has a configuration error and the
    # published name is the one it meant.
    size = _int("page_size", _int("limit", DEFAULT_PAGE_SIZE))
    size = min(MAX_PAGE_SIZE, max(1, size))
    return page, size


#: `CR-111-BRC04` · the request parameter whose value we hand straight back.
#:
#: ⚠ **PO RULING 2026-09-17, ASKED WHOSE NUMBER `remote_utility_id` CARRIES:**
#: *"a) echo back whatever they sent"*. **Nothing of ours goes into it** — not
#: the tenant id, not the slug, not the utility's name — and when they send
#: nothing the key is OMITTED rather than served null. A null would read to
#: their parser as *we have no id for you*, which is a statement; an absent key
#: is the absence of one.
REMOTE_UTILITY_ID_PARAM = "remote_utility_id"


def _echoed_utility_id(request: Any) -> dict[str, Any]:
    """`{"remote_utility_id": "…"}` or `{}`. Trimmed and bounded for
    `_company_named`'s reason — this is a value a stranger typed and it is about
    to be written into a response body."""
    raw = str(request.GET.get(REMOTE_UTILITY_ID_PARAM) or "").strip()
    return {REMOTE_UTILITY_ID_PARAM: raw[:64]} if raw else {}


class PartnerCsvRenderer(BaseRenderer):
    """Registers `csv` with DRF's content negotiation. **It renders nothing.**

    ⚠⚠ **THIS EXISTS BECAUSE `format` IS DRF's OWN RESERVED PARAMETER, AND
    WITHOUT IT `?format=csv` IS A `404` — THE SAME `404` THAT IS THIS SURFACE'S
    REFUSAL (`DEF-INT-5585`).** `api_settings.URL_FORMAT_OVERRIDE` is `"format"`,
    so DRF reads that query parameter as a request for a RENDERER before the view
    runs. Only `JSONRenderer` and `BrowsableAPIRenderer` are registered, `csv`
    matches neither, and DRF raises `NotFound`.

    **What that would have shipped as, and why the unit tests could not see it.**
    `partner_csv.render` is correct and its twelve cases pass; the view's own
    branch is correct. Over the wire the framework answered first, and a partner
    asking for CSV would have received the five-word refusal — reading *your key
    is bad* — and gone to look at their credentials for a parameter that works.
    It was found only by calling the route (hard-won law 6: no gate reads
    rendered output, and nothing here reads a framework default either).

    ⚠ **THE VIEW STILL RETURNS A PLAIN `HttpResponse`, SO `render` IS NEVER
    CALLED**, and that is deliberate rather than an oversight: the body is built
    by `partner_csv.render` from the SAME shaped records the JSON branch would
    have serialised, which is the property that keeps the two from drifting. This
    class is a negotiation entry and nothing more, and `render` returning the
    bytes unchanged is the only honest thing for it to do if it ever were called.
    """

    media_type = partner_csv.CONTENT_TYPE.split(";")[0]
    format = partner_csv.FORMAT_CSV
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):  # noqa: A003
        return data if isinstance(data, (bytes, str)) else str(data)


#: What every partner view negotiates over. ⚠ **JSON FIRST**, so a caller that
#: asks for nothing gets what this surface has always served; `csv` is reachable
#: only by asking for it by name.
PARTNER_RENDERERS = [JSONRenderer, PartnerCsvRenderer]


def _page_url(request: Any, page: int, total_pages: int) -> str | None:
    """This request's own address with `page` moved, or `None` past either end.

    ⚠ **COMPUTED HERE AND NEVER IN A SHAPE, WHICH IS THE BOUNDARY ITSELF.** A
    shape may rename a field and may not compute one; a page URL needs the
    request, the current page and the total, none of which a shape may see. So
    the door computes both and each shape declares whether to publish them and
    under what names — `shapes.NATIVE` names neither, so what this surface has
    served since `CR-110-BRC04` does not move by one byte.
    """
    if page < 1 or page > total_pages:
        return None
    query = request.GET.copy()
    query["page"] = str(page)
    return f"{request.build_absolute_uri(request.path)}?{query.urlencode()}"


def _page_response(
    request: Any,
    *,
    caller: serve.PartnerCaller,
    resource: str,
    records: list[dict[str, Any]],
    total: int,
    page: int,
    size: int,
    total_pages: int,
    extra: dict[str, Any] | None = None,
) -> Any:
    """One page, in this caller's dialect, as JSON or as CSV.

    ⚠ **THE SHAPE COMES FROM THE CONNECTOR, WHICH CAME FROM THE KEY.** Never
    from a query parameter, a header or a version in the path — see
    `shapes.resolve`, which has no overload that takes a request. A partner's
    integration document stays valid with nothing added to it, and **no caller
    can choose another partner's dialect**, which would be an input that changes
    a response (`BR-TEN-003`).

    ⚠ **CSV IS THE SAME RECORDS, NOT A SECOND QUERY.** The list handed to
    `partner_csv.render` is the identical shaped list that would have been
    serialised into `records`, so the two serialisations cannot disagree about
    what is on page 3. `NFR-3`: the CSV is paged exactly as the JSON is, at any
    size, and there is no *download everything* here — see `partner_csv`'s
    docstring for `DEF-PAY-4221`, which is what that costs.
    """
    shape = shapes.resolve(getattr(caller.connection, "provider_key", None))
    shaped = shapes.apply_records(records, shape, resource=resource)

    if partner_csv.wants_csv(request.GET.get("format")):
        body = partner_csv.render(shaped, rows=request.GET.get("rows"))
        response = HttpResponse(
            body, content_type=partner_csv.CONTENT_TYPE, status=_status_for("ok")
        )
        for name, value in partner_csv.paging_headers(
            total_records=total, page=page, total_pages=total_pages
        ).items():
            response[name] = value
        return response

    facts: dict[str, Any] = {
        "total_records": total,
        "page": page,
        "page_size": size,
        "total_pages": total_pages,
        "next": _page_url(request, page + 1, total_pages),
        "previous": _page_url(request, page - 1, total_pages),
        "records": shaped,
        **_echoed_utility_id(request),
        **(extra or {}),
    }
    return JsonResponse(shapes.apply_envelope(facts, shape), status=_status_for("ok"))


def _window_text(since: date | None, until: date | None) -> str:
    """What the manager sees in the *What they took* column — *Payments, 1–30
    Sep*, *Payments, 2 years*. Words, because the column is read by a person."""
    if since and until:
        # ⚠ *2–2 Sep* IS WHAT THE FIRST DRAFT PRINTED FOR A SINGLE DAY, and it
        # was found by reading the rows a real run wrote rather than by any
        # test (hard-won law 6). A manager reading *Payments, 2–2 Sep* stops
        # and re-reads; a range whose ends are the same day is one day.
        if since == until:
            return since.strftime("%-d %b")
        if since.year == until.year and since.month == until.month:
            return f"{since.day}–{until.day} {until.strftime('%b')}"
        if since.year == until.year:
            return f"{since.strftime('%-d %b')} – {until.strftime('%-d %b')}"
        span = (until - since).days
        if span >= 365:
            return f"{span // 365} years" if span // 365 > 1 else "1 year"
        return f"{since.isoformat()} – {until.isoformat()}"
    if since:
        return f"since {since.isoformat()}"
    if until:
        return f"up to {until.isoformat()}"
    return "everything"


# ════════════════════════════════════════════════════════════════════════
# CR-110-BRC04 PHASE 2 · THE PHASE-1 PAIR, RETIRED
# ════════════════════════════════════════════════════════════════════════
#
# ⚠ **`GET /v1/payments` AND `GET /v1/billing` SERVED A FLAT FOUR-FIELD RECORD
# AND THEY STOPPED ON 2026-09-16, WHEN WAVES 3 AND 4 LANDED.** The CR named the
# day and lane A left them for this lane: *"Retire the phase-1 flat routes
# `v1/payments` and `v1/billing` when your nested shape lands."*
#
# **WHY THEY COULD NOT SIMPLY BE UPGRADED IN PLACE, which was the tempting move
# and is the one that would have cost money.** On the flat record `amount` was
# THE BILL'S OWN TOTAL. On the nested record `amount` is **the account's balance
# NOW** and the bill's total is `bill_amount` — the PO's own payload says so.
# One key, two meanings, and **a finance system cannot see the difference**: it
# would go on posting a receivable from a field that had quietly started
# answering a different question. Serving the nested payload here would have
# been that, and serving the flat payload at the new address would have been the
# mirror of it — which is the sentence the CR already carries.
#
# **`410` AND NOT `404`.** A `404` on this surface is the REFUSAL — the same
# five words a wrong key gets — so a partner would read *your key is bad* and go
# looking at its credentials for an address that is simply finished. `410 Gone`
# is the one honest answer and it NAMES THE REPLACEMENT, so the engineer on the
# far end has somewhere to go.
#
# ⚠ **IT AUTHENTICATES FIRST, EXACTLY AS EVERY OTHER ROUTE DOES.** A retirement
# notice handed to an unauthenticated caller answers *this utility exists* to
# anybody who asks, which is the enumeration oracle `BR-INT-044` exists to
# close, arriving through the one door nobody thinks to lock. A bad key still
# gets the refusal here and learns nothing.
#
# ⚠ **AND ONE CONSEQUENCE IS RECORDED RATHER THAN SWEPT UP:** `erp_workday`,
# `erp_sap`, `erp_infor` and `erp_msgp` declare `serve_payment` / `serve_bill` /
# `serve_customer` with **no `served_path`**, so this pair was the only address
# their keys had. Giving each of them the phase-2 paths is one line per manifest
# and belongs to whoever owns those manifests, not to a lane passing through
# (`DEF-INT-5545`).
#
# ── `DEF-INT-5623` — AND A THIRD ADDRESS JOINED THEM ON 2026-09-17 ─────────
# `/partner/v1/customers` became `/partner/v1/accounts` because the PO ruled
# the surface must call an account an account. **The mechanism below is reused
# rather than re-invented**, which is this repository's own rule (law 11's
# closing clause: read `10-scripts/`'s listing — and, here, the file's own —
# before writing a helper), and it is the right shape for the same reason it
# was the right shape for the phase-1 pair: `410` NAMES THE REPLACEMENT where
# this surface's `404` would say only *refused*, in the same five words a
# stolen key gets.
#
# ⚠ **IT IS NOT A SECOND SPELLING OF A LIVE ADDRESS.** `/partner/v1/customers`
# serves NOTHING after this commit — no manifest declares it, no page of
# accounts comes back from it, and the published specification stops naming it
# because the specification is built from the operations and none of them
# points there any more. It answers one sentence and a `410`, forever or until
# somebody decides a year has passed.
RETIRED_FOR = {
    "payments": "/partner/v1/payments",
    "billing": "/partner/v1/bills",
    "customers": "/partner/v1/accounts",
}


#: The published address → the word `RETIRED_FOR` is keyed by. THREE entries and
#: one direction, so the specification and the view cannot name different
#: replacements for one retired address.
_RETIRED_PATH_FOR = {
    "/v1/payments": "payments",
    "/v1/billing": "billing",
    "/partner/v1/customers": "customers",
}

#: Which operation a retired address authenticates against. ⚠ **IT IS STILL
#: CHECKED, AND THAT IS NOT CEREMONY:** a retirement notice handed to anyone who
#: asks answers *this utility exists* to a stranger, which is the enumeration
#: oracle `BR-INT-044` closes — arriving through the one door nobody thinks to
#: lock. It was a two-branch conditional until `DEF-INT-5623` added the third
#: address; a map is what stops the fourth being an `else`.
_RETIRED_OPERATION = {
    "payments": "serve_payment",
    "billing": "serve_bill",
    "customers": "serve_customer",
}


def _retired(what: str) -> JsonResponse:
    """The phase-1 address, answering for itself."""
    return JsonResponse(
        {
            "error": f"This address has been replaced by {RETIRED_FOR[what]}.",
            "code": "RETIRED",
            "resource": what,
            "replaced_by": RETIRED_FOR[what],
        },
        status=410,
    )


def _serve_retired(request: Any, *, what: str) -> Any:
    """Authenticate, record the call, then say the address is finished."""
    operation = _RETIRED_OPERATION[what]
    try:
        caller = serve.resolve_caller(
            provider_key=partner_provider_keys(),
            presented_key=_presented_key(request),
            source_address=_source_address(request),
            operation=operation,
        )
    except serve.PartnerRefused:
        return _refused()
    # A row on S142, because a partner still calling a retired address every
    # night is exactly the thing a manager should be able to see in words.
    serve.record_read(
        caller=caller,
        operation=operation,
        rows=0,
        window=f"{what.capitalize()}, retired address",
        refused=True,
    )
    return _retired(what)


@partner_key_required
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@renderer_classes(PARTNER_RENDERERS)
def partner_payments(request):
    """`GET /api/{utility}/v1/payments` — RETIRED, see `/partner/v1/payments`."""
    return _serve_retired(request, what="payments")


@partner_key_required
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@renderer_classes(PARTNER_RENDERERS)
def partner_billing(request):
    """`GET /api/{utility}/v1/billing` — RETIRED, see `/partner/v1/bills`."""
    return _serve_retired(request, what="billing")


@partner_key_required
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@renderer_classes(PARTNER_RENDERERS)
def partner_customers_retired(request):
    """`GET /api/partner/v1/customers` — RETIRED, see `/partner/v1/accounts`.

    ⚠ **IT IS REGISTERED IN `PARTNER_ROUTES` LIKE EVERY OTHER PARTNER ADDRESS
    AND NOT BESIDE THE LOOP**, so `_with_utility_from_key` opens the utility
    from the key before this runs. A retirement notice still has to
    authenticate — see `_serve_retired` — and authenticating means reading a
    tenant table, which without that first arrow returns zero rows for a VALID
    key and would refuse every caller while looking exactly like a bad key.

    ⚠ **THE SCOPE IT CHECKS IS `serve_customer`, WHICH IS WHAT THE KEY THAT
    USED THIS ADDRESS WAS GRANTED.** A key that never could call it still
    cannot, and learns nothing new.
    """
    return _serve_retired(request, what="customers")


# ════════════════════════════════════════════════════════════════════════
# CR-110-BRC04 PHASE 2 · THE NINE CHECKS, IN ONE PLACE
# ════════════════════════════════════════════════════════════════════════


class _Stop(Exception):
    """A response the door produced instead of a payload — carried rather than
    returned, so `_admit` reads as one sequence of checks and every caller
    handles the refusal the same way. It never reaches a partner as itself."""

    def __init__(self, response: Any) -> None:
        super().__init__("partner request stopped at the door")
        self.response = response


#: `CR-111-BRC04` · the parameter every Invoice Cloud call carries and that
#: NOTHING reads. See `_admit` for the ruling that emptied it.
COMPANY_ID_PARAM = "company_id"


def _company_named(request: Any) -> str:
    """What this caller told us their utility id is — **for the record row and
    for nothing else** (`CR-111-BRC04`, PO ruling 2026-09-17).

    Trimmed, and truncated at 64 characters. ⚠ **THE TRUNCATION IS NOT
    TIDINESS.** This value is whatever an outside caller typed, and it lands in
    a run row's summary, which a manager reads on S142. An untrimmed field is a
    place to put a megabyte, or a newline and a forged second log line.

    Returns `""` when they sent nothing, which is the ordinary case for every
    partner but this one and which the caller renders as nothing at all rather
    than as *named nothing*.
    """
    raw = str(request.GET.get(COMPANY_ID_PARAM) or "").strip()
    return raw[:64].replace("\n", " ").replace("\r", " ")


def _named_suffix(request: Any) -> str:
    """*" · they named 302"*, or nothing. Appended to the run row's window text
    so a manager can see a partner pointed at the wrong utility **without it
    being a refusal of their key** — which is the whole of what `company_id`
    now does."""
    named = _company_named(request)
    return f" · they named {named}" if named else ""


def _admit(
    request: Any,
    *,
    operation: str | None,
    window: str,
    direction: str = models.RUN_DIRECTION_INBOUND_READ,
) -> serve.PartnerCaller:
    """Checks 1–8 for every partner route, in the order that is the security
    argument — and the reason there is exactly one of these functions.

    ⚠ **`direction` IS AN ARGUMENT SINCE 2026-09-24 AND CHANGES NOTHING THE
    DOOR DOES.** It decides only which direction the ONE row this function can
    write — the rate-limit refusal — is filed under, so a `429` on
    `make-payment` does not appear on a manager's access log as *they read from
    us*. Every one of the eight checks, the single refusal, the shared body and
    the padded floor are identical for a read and a write: **the door does not
    know or care which it is guarding, and a lane must not make it care.** The
    first address on this surface that creates money is exactly the wrong place
    for a second authorisation path.

      1 key real and active · 2 connector enabled · 3 utility active ·
      4 address on the allowlist · 5 key holds this scope
          → `resolve_caller`, ONE refusal, `404`, five words, padded to the
            floor. All five are computed together with no early return; see
            `runners/serve.py`. Rows 2 and 3 were added by PO ruling of
            2026-09-16 and neither added a branch.
      6 the tenant context
          → already open before this function runs, and WHICH mechanism opened
            it depends on the address. On `/api/partner/v1/…` it is the KEY,
            through `key_directory.open_utility_for` in `partner_urls.py`
            (`DEF-INT-5546`, PO 2026-09-16); on the retired `v1/…` pair it is still
            `TenantContextMiddleware` reading the path. Either way RLS then
            hides every other utility, which is why checks 1–5 could find this
            key at all — and neither mechanism reads a tenant a CALLER asserts,
            which is what `BR-TEN-003` actually forbids.
      7 — **GONE.** See below.
      8 count against the operation's limit
          → `429` with `Retry-After`, and a run row naming which of the two
            rate causes it was.

    Check 9 — select, order, page — is the caller's own and is not here,
    because it is the only one that differs between the five routes.

    ⚠⚠ **CHECK 7 IS GONE. `company_id` IS ACCEPTED, IGNORED AND RECORDED —
    PO RULING 2026-09-17, VERBATIM:** *"you will ahve to remove company ID
    filter from all Apis - we cannot tell tenant ID outside our system"*.

    **THE SUPERSESSION CHAIN, WRITTEN OUT SO THE NEXT LANE DOES NOT "RESTORE"
    IT.** Three statements, in order, each superseding the one before:

      1 · PO 2026-09-16, *"company_id = tenant id"* — which is the sentence
          `runners/serve.company_id_matches` was built on and still quotes.
      2 · PO 2026-09-17, *"company_id = Keys will esnure it map to tenant ID"*
          — already a narrowing: the KEY maps to the tenant, so the parameter
          is confirmation rather than identification.
      3 · PO 2026-09-17, later the same day, the ruling above. **The parameter
          is not a filter, is not a check, and is not a refusal.**

    ⚠ **ISOLATION DOES NOT MOVE BY ONE INCH, AND THIS IS THE PARAGRAPH THAT
    SAYS WHY.** `company_id` never selected anything. It was VERIFIED and thrown
    away — `company_id_matches`'s own docstring says so, and `BR-TEN-003` is why:
    *"the ONLY input consulted is the request path; tenant_id in a header/param/
    body is never read"*. What isolates a partner is, and always was:

        key ─► credential ─► connection ─► tenant ─► app.tenant_id ─► RLS FORCE

    — `key_directory.open_utility_for` in `partner_urls.py` is the first arrow
    and nothing a caller sends touches any of them. Removing check 7 removes a
    comparison, not a boundary. **Measured, not asserted:** on 2026-09-17 the
    `DEF-INT-5568` lane read all four unscoped integrations querysets on
    PostgreSQL 16 under the application's non-superuser role and **none of them
    leaked** — RLS `FORCE` was doing the work, and
    `unguarded_partitions('integration_run')` answered `[]` over both partitions.

    ⚠ **WHY THE PARAMETER IS STILL ACCEPTED RATHER THAN REFUSED AS UNKNOWN.**
    Invoice Cloud's integration document sends it on every call. A surface that
    refused an unrecognised parameter would break a live partner to enforce a
    tidiness nobody asked for, on the day we told them to stop sending it — and
    their document would have to be reissued before a single call worked.

    ⚠ **AND IT IS RECORDED, WHICH IS THE HALF THAT IS EASY TO DROP.** A partner
    configured against the wrong utility used to find out on its first call, with
    a `403`. It now finds out never. So what they named goes on the run row's
    window text — *"Bills, 1–30 Sep · they named 302"* — where a manager reads
    it on S142 and can ring them, and where it is information rather than a
    refusal. **Nothing compares it to anything.**
    """
    try:
        caller = serve.resolve_caller(
            provider_key=partner_provider_keys(),
            presented_key=_presented_key(request),
            source_address=_source_address(request),
            operation=operation,
        )
    except serve.PartnerRefused as exc:
        raise _Stop(_refused()) from exc

    # ⚠ **NOTHING HERE READS `company_id`.** It was check 7 until 2026-09-17;
    # see this function's docstring for the ruling and the supersession chain.
    # What the caller named is picked up by each route's `_named_suffix` and put
    # on the run row, and it is compared against nothing.

    try:
        serve.check_rate_limit(caller, operation=operation or REFERENCE_WINDOW)
    except serve.PartnerRateLimited as exc:
        serve.record_read(
            caller=caller,
            operation=operation or SERVED_ROUTES["bills"][0],
            rows=0,
            window=exc.window_text,
            refused=True,
            items=serve.refusal_items((exc.code,)),
            direction=direction,
        )
        raise _Stop(_rate_limited(exc)) from exc

    return caller


def _not_yet_served(what: str) -> JsonResponse:
    """A declared address whose payload its wave has not built yet.

    ⚠ **NEVER A 404 AND NEVER AN EMPTY LIST, AND BOTH WOULD HAVE BEEN
    EASIER.** A `404` on this surface is the refusal — the same five words a
    wrong key gets — so a partner would read *your key is bad* and go looking
    at their credentials. An empty `records: []` with `total_records: 0` reads
    to a finance system as **this utility issued no bills**, and it would post
    that: a missing bill is a missing GL entry, and nothing on either side
    would raise.

    `501` is the one honest answer: the address is real, the method is right,
    and this server does not implement it YET. The sentence names the wave so a
    partner's engineer can ask for a date rather than a diagnosis.
    """
    return JsonResponse(
        {
            # `.get`, because `ROUTE_WAVE` is EMPTY while every address serves
            # (see the dict). A `KeyError` here would turn a declared-but-held
            # address into a `500` the day a sixth one is added — which is the
            # one thing this function exists to prevent.
            "error": f"Not built yet — {ROUTE_WAVE.get(what, 'a later wave')}.",
            "code": "NOT_YET_SERVED",
            "resource": what,
        },
        status=501,
    )


def _partner_route(request: Any, *, what: str) -> Any:
    """One of the declared payload routes. The door, then its wave."""
    operation, label = SERVED_ROUTES[what]
    try:
        caller = _admit(request, operation=operation, window=label)
    except _Stop as stop:
        return stop.response
    # ⓘ **THE SEAM THE THREE SIBLING LANES FILL IN.** Each replaces its own
    # line here with a call into its own seam file, so no two of them touch the
    # same hunk. Until then the address is honest about itself, and
    # `test_cr110_phase2_partner_reference.py` goes RED the day one of them
    # starts serving without this record moving — which is hard-won law 2's
    # *write the test that fires when the hold expires*, in the commit that
    # writes the hold.
    serve.record_read(
        caller=caller,
        operation=operation,
        rows=0,
        window=f"{label}, not built yet",
        refused=True,
    )
    return _not_yet_served(what)


def _serve_accounts(
    request: Any,
    *,
    route: str = "accounts",
    with_detail: bool = False,
    only_numbers: list[str] | None = None,
) -> Any:
    """`CR-110-BRC04` phase 2 wave 2 — the door, then one page of accounts.

    ⚠ **THIS WAS `_serve_customers` AND THE SURFACE SAID *CUSTOMER* IN THREE
    PLACES UNTIL 2026-09-17 (`DEF-INT-5623`).** The values were always the
    account's — PO 2026-09-16, *"Customers = accounts"* — so every test passed
    over it: what was wrong was the word, and nothing compares a ruling's
    vocabulary against the surface that carries it. `seams/customers.py` keeps
    its own name because it is the seam onto the `customers` MODULE, which is
    a different thing again and still holds the landlord who has fourteen of
    these.

    ⚠ **`route` IS AN ARGUMENT AND NOT A CONSTANT SINCE `DEF-INT-5622`.** Two
    addresses share this implementation and they no longer share an operation:
    `/partner/v1/accounts` is `serve_customer` and `/partner/v1/consumer-info`
    is `serve_consumer_info`, each with its own tick on the set-up screen and
    its own row on S142. Reading `SERVED_ROUTES["accounts"]` unconditionally —
    which is what this did — would have admitted a `consumer-info` call
    against the LIST's permission, so a clerk granting *read the account list*
    would silently have granted *look one account up* with its rate plan and
    its opening balance. One line, and no test could have seen it, because
    both names resolved to the same operation until today.

    ⚠ **NO `from` / `to`, UNLIKE THE OTHER THREE ROUTES.** A date window exists
    on this surface to stop a MOVING set skipping rows between pages; accounts
    are ordered by an account number that is unique per tenant and allocated
    from a monotonic series, so a new one lands after any cursor a partner has
    passed. The seam's docstring states the one case that can still insert
    mid-order and why `total_records` is the answer to it. Both parameters are
    simply not read here, rather than accepted and ignored.
    """
    operation, label = SERVED_ROUTES[route]
    try:
        caller = _admit(request, operation=operation, window=label)
    except _Stop as stop:
        return stop.response

    page, size = _page_params(request)
    queryset = customers_seam.collectable()
    if only_numbers is not None:
        # ⚠ **NARROWED IN SQL, AFTER the tenant filter `collectable()` already
        # applied and UNDER the RLS context `partner_urls` opened from the key.**
        # A number that is not this utility's simply matches nothing, which is
        # the same structural non-answer `bill-download` relies on — there is no
        # cross-tenant read to refuse because there is no cross-tenant read.
        queryset = queryset.filter(account_no__in=only_numbers)
    # ⚠ **COUNTED AND SLICED IN SQL** (`NFR-3`, and B6's rule that no code path
    # may enforce a maximum account count per tenant). 40,000 accounts — the
    # top of T5 and the largest utility this product models — is 40 calls of
    # 1,000, and not one of them reads more than its own page.
    total = queryset.count()
    total_pages = max(1, -(-total // size))
    # ⚠ **ONE CALL FOR THE WHOLE PAGE, NOT ONE PER ROW.** `as_records` resolves
    # the address walk and the primary contact once each; `as_record` refuses
    # to resolve its own, so the per-row version cannot be written by accident
    # (`DEF-2723`'s shape, which is invisible on a demo tenant with twelve).
    records = customers_seam.as_records(
        queryset[(page - 1) * size : page * size], with_detail=with_detail
    )
    for record in records:
        # BR-INT-054: the partner's own words for our values are Runbooks'.
        # This returns {} today and the sibling test asserts it does.
        record.update(serve.partner_fields(record))

    serve.record_read(
        caller=caller,
        operation=operation,
        rows=len(records),
        window=f"{label}, {_window_text(None, None)}{_named_suffix(request)}",
        page=page,
        total_pages=total_pages,
    )

    return _page_response(
        request,
        caller=caller,
        # ⚠ **THE SHAPE'S RESOURCE KEY, WHICH IS INTERNAL AND IS THE ONE
        # PLACE `DEF-INT-5623` DELIBERATELY LEFT SAYING *customers*.** It
        # never reaches a partner or a screen: it selects
        # `shapes.<dialect>.resources["customers"]`, and renaming it would move
        # a key in every Shape for no reader's benefit. The FIELD names inside
        # that resource are what the partner reads, and those moved.
        resource="customers",
        records=records,
        total=total,
        page=page,
        size=size,
        total_pages=total_pages,
    )


@partner_key_required
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@renderer_classes(PARTNER_RENDERERS)
def partner_accounts(request):
    """`GET /api/partner/v1/accounts` — wave 2 (`seams/customers.py`).

    BUILT 2026-09-16. It no longer routes through `_partner_route`, which is
    the three remaining waves' shared hold; `ROUTE_WAVE` lost its row in the
    same commit, which is what the hold-expiry case checks.

    ⚠ **THE ADDRESS WAS `/partner/v1/customers` UNTIL 2026-09-17**
    (`DEF-INT-5623`). The old one answers `410` and names this one —
    `partner_customers_retired` above.

    **A COMPANY ACCOUNT IS NAMED BY ITS LEGAL NAME FROM 2.553.0**
    (`DEF-INT-9796`, PO ruling 2026-10-06 D3 (a)). For an account held by a
    company: `customer_name` is the company's legal name, `first_name` is the
    whole legal name, `last_name` is `null`, and `organization_name` (a field
    added in 2.553.0) is the legal name. For a person `organization_name` is
    `null` and every other field is unchanged. `email` and `phone` are the
    account's primary contact in both cases. Example — before: `customer_name`
    *"Ruth Okafor"*, `first_name` *"Ruth"*, `last_name` *"Okafor"*; after:
    `customer_name` and `first_name` *"Grace Fellowship of Cedar Ford"*,
    `last_name` `null`, `organization_name` *"Grace Fellowship of Cedar Ford"*.
    `consumer-info` carries the same fields.
    """
    return _serve_accounts(request)


# ════════════════════════════════════════════════════════════════════════
# CR-110-BRC04 PHASE 2 · WAVES 3 AND 4 — THE TWO SERVED PAYLOADS
# ════════════════════════════════════════════════════════════════════════
#
# ⚠ **CHECK 9 — SELECT, ORDER, PAGE — IS THE ONLY ONE THAT DIFFERS BETWEEN THE
# ROUTES, WHICH IS WHY IT IS HERE AND NOT IN `_admit`.** Checks 1–8 are the
# door and are one function for all five addresses; this is the part each wave
# fills in, and it composes NOTHING itself: the record is the seam's, so a
# partner's page and a one-bill spot check come out of the same code.
#
# ⚠ **THE PAGING TRAP, AND IT LOSES MONEY SILENTLY** (`CR-110-BRC04` phase 2).
# Page numbers over a moving table SKIP rows: pull page 1 of *newest first*, let
# three bills issue, and three fall off the end unseen — **a missed bill is a
# missed GL posting** and nothing on either side raises. Three things answer it
# and all three are needed:
#   1 · the window is applied BEFORE the page, so the set has stopped moving;
#   2 · the sort ends in a column that never repeats (`id`), so no two rows can
#       swap places between two calls — both in the seams' own `collectable`;
#   3 · the envelope carries `total_records`, so the partner's job can CHECK it
#       pulled what we said existed rather than trusting it reached the end.


def _bad_request(sentence: str, code: str) -> JsonResponse:
    """A `400` for a caller that got PAST the door and asked wrongly.

    Safe to be specific for the same reason `_company_mismatch` is: it is
    reachable only by a caller holding a live key for a live utility, so it
    learns nothing it did not already know.
    """
    return JsonResponse({"error": sentence, "code": code}, status=400)


#: `CR-111-BRC04` · `{the published name: the spelling a partner may also send}`.
#:
#: ⚠ **BILLS PUBLISH `since`/`until` AND INVOICE CLOUD'S DOCUMENT SENDS
#: `start_date`/`end_date`**, which are the names PAYMENTS and the LEDGER
#: already publish on this same surface. So one product publishes two spellings
#: for one idea across four routes, and that is ours rather than theirs — it is
#: what made a second spelling necessary at all.
#:
#: ⚠ **THE ALIAS RUNS ONE WAY.** `start_date` is accepted on bills; `since` is
#: NOT accepted on payments or the ledger, where both dates are REQUIRED and
#: quietly reading an alias could turn a refusal into an unbounded walk. The map
#: below is therefore keyed on the published name and holds exactly one row.
#:
#: ⚠ **THE RIGHT FIX IS TO PUBLISH ONE PAIR EVERYWHERE, AND IT IS NOT DONE
#: HERE.** Renaming `since`/`until` would break every partner already calling
#: bills, which is a change to a live contract and belongs in its own CR with
#: its own deprecation window — not in a wave that is adding a connector.
#: Recorded as a recommendation in this lane's report.
WINDOW_ALIASES = {"since": "start_date", "until": "end_date"}


class _BadWindow(Exception):
    """A date parameter this server could not read, carried like `_Stop`."""


def _window_param(request: Any, name: str) -> date | None:
    """One date parameter — absent, or a date, or a refusal.

    ⚠ **UNREADABLE IS NOT ABSENT, AND THE DIFFERENCE IS A WHOLE LEDGER.**
    `_parse_date` answers `None` to both, so `since=2026-13-45` read as *no
    lower bound* and handed back every bill the utility has ever issued — a
    forty-thousand-account pull nobody asked for, silently, because one digit
    was wrong. This refuses it by name instead.
    """
    raw = request.GET.get(name)
    if raw in (None, "") and name in WINDOW_ALIASES:
        # ⚠ **THE ALIAS IS READ ONLY WHEN THE PUBLISHED NAME IS ABSENT**, so a
        # caller sending both gets the documented one and a caller sending
        # neither still gets *absent* rather than a silently-preferred alias.
        raw = request.GET.get(WINDOW_ALIASES[name])
        name = WINDOW_ALIASES[name] if raw not in (None, "") else name
    if raw in (None, ""):
        return None
    parsed = _parse_date(raw)
    if parsed is None:
        raise _BadWindow(name)
    return parsed


def _served_page(
    request: Any,
    *,
    what: str,
    queryset_for: Any,
    records_for: Any,
    window: tuple[str, str],
    window_required: bool,
) -> Any:
    """Checks 1–8, then this route's own select · order · page.

    ⚠ **THE WINDOW IS READ AFTER THE DOOR AND NOT BEFORE IT, AND A TEST OF
    LANE A'S CAUGHT THE FIRST DRAFT DOING IT THE OTHER WAY ROUND.** The order
    in `_admit` is the whole security argument — *authenticate before anything
    else is touched* — and a `400` for a missing `start_date` handed out ahead
    of it tells an unauthenticated caller that the address is real and that its
    parameters are named such-and-such. `test_a_key_holding_one_tick_reads_the_
    reference_and_is_refused_elsewhere` went red on exactly that: a key without
    the payments tick got `400 DATES_REQUIRED` where it must get the same
    refusal as every other stranger.
    """
    operation, label = SERVED_ROUTES[what]
    try:
        caller = _admit(request, operation=operation, window=label)
    except _Stop as stop:
        return stop.response

    first, last = window
    try:
        since = _window_param(request, first)
        until = _window_param(request, last)
    except _BadWindow as bad:
        return _bad_request(f"Cannot read {bad.args[0]}.", "BAD_DATE")
    if window_required and (since is None or until is None):
        # ⚠ **THE LEDGER'S OWN SENTENCE AND THE LEDGER'S OWN CODE, REUSED
        # RATHER THAN RE-WORDED.** Wave 5 got here first with
        # `LEDGER_WINDOW_REQUIRED`, and two codes for one fact on one surface is
        # `DEF-014` — a partner writing one branch for *you forgot the window*
        # would meet the other on the other route. The constant's NAME is now
        # narrower than its use and is left alone on purpose: renaming it moves
        # a sibling's citations for no behaviour.
        serve.record_read(
            caller=caller,
            operation=operation,
            rows=0,
            window=f"{label}, no window given{_named_suffix(request)}",
            refused=True,
        )
        return JsonResponse(LEDGER_WINDOW_REQUIRED, status=400)

    page, size = _page_params(request)
    queryset = queryset_for(since=since, until=until)
    total = queryset.count()
    total_pages = max(1, -(-total // size))
    records = records_for(list(queryset[(page - 1) * size : page * size]))

    serve.record_read(
        caller=caller,
        operation=operation,
        rows=len(records),
        window=f"{label}, {_window_text(since, until)}{_named_suffix(request)}",
        page=page,
        total_pages=total_pages,
    )
    return _page_response(
        request,
        caller=caller,
        resource=what,
        records=records,
        total=total,
        page=page,
        size=size,
        total_pages=total_pages,
    )


@partner_key_required
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@renderer_classes(PARTNER_RENDERERS)
def partner_bills(request):
    """`GET /api/partner/v1/bills` — wave 3, the NESTED bill.

    `company_id` (verified, never used to select) · `since` · `until` · `page` ·
    `page_size`. One record per bill, one row per LINE, each line carrying the
    GL account it posted to — PO 2026-09-16, verbatim: *"we save bills as a
    multiple line items with gl code map so for bill we will need nasted json
    with multiple records with gl code mapped"*.

    ⚠ **THE WINDOW IS OPTIONAL HERE AND REQUIRED ON PAYMENTS**, because the
    supplied specification writes it that way. A bills pull with no window is a
    partner's FIRST pull — every bill the utility has ever issued, which is what
    a new integration actually wants — and the envelope's `total_records` is how
    they know they got all of it.
    """
    return _served_page(
        request,
        what="bills",
        queryset_for=billing_seam.page_queryset,
        records_for=billing_seam.records_for,
        window=("since", "until"),
        window_required=False,
    )


@partner_key_required
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@renderer_classes(PARTNER_RENDERERS)
def partner_v1_payments(request):
    """`GET /api/partner/v1/payments` — wave 4.

    `company_id` · **`start_date` and `end_date`, both REQUIRED** · `page` ·
    `page_size`. The four coded fields ship as `{code, label}` in OUR
    vocabulary; the partner maps at THEIR end from the reference endpoint, which
    is the PO's ruling that struck the clerk mapping screen — *"this will not be
    required in case of they read cases - we just need to actiavte connectors
    and issue a key thats all"*.

    ⚠ **BOTH DATES ARE REQUIRED AND AN UNBOUNDED PULL IS REFUSED, NOT SERVED
    EMPTY.** The supplied specification declares them required; a partner that
    omitted one and got every payment the utility has ever taken would page
    through a set that is still moving underneath it, which is the trap above.
    """
    return _served_page(
        request,
        what="payments",
        queryset_for=payments_seam.page_queryset,
        records_for=payments_seam.records_for,
        window=("start_date", "end_date"),
        window_required=True,
    )


#: `CR-110-BRC04` phase 2 wave 5 · what a caller is told when the ledger window
#: is missing. **Reached only AFTER all nine checks**, so it discloses nothing a
#: caller does not already hold — which is why it may be specific where
#: `_refused()` may not.
LEDGER_WINDOW_REQUIRED = {
    "error": "Send start_date and end_date.",
    "code": "DATE_RANGE_REQUIRED",
}

#: Why `id` and `transactionId` come back null on SOME rows, said ONCE in the
#: envelope rather than on every row.
#:
#: ⚠ **RENAMED 2026-09-24 (`DEF-INT-6601`, Finance blueprint `P5.1`). IT READ
#: `journal_entry_number_not_stamped_at_post`, AND THAT CAUSE WAS FIXED THAT
#: MORNING.** `posting.post()` allocates a `JE-` number now (`P0.3`, commit
#: `b813394a6`), so an entry posted since carries one. What is still null is
#: HISTORY — entries written before the change, which nothing backfills;
#: measured on the demo tenant, PostgreSQL 16.13: **167 posted entries, 0
#: numbered**. A code naming a cause that has been fixed tells a partner the
#: product cannot number its books, which is false and unfixable-looking; this
#: one tells them the window reaches back past the change, which is true and
#: ages out on its own. **Renamed rather than reworded** — a key that says one
#: thing while its sentence says another is the rot CLAUDE.md hard rule 4
#: records on `amendment_history_is_not_a_permanent_record`.
LEDGER_NUMBER_GAP = "some_entries_pre_date_journal_numbering"


@partner_key_required
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@renderer_classes(PARTNER_RENDERERS)
def partner_ledger(request):
    """`GET /api/partner/v1/ledger` — a page of the books.

    Wave 5 of `CR-110-BRC04` phase 2. The nine checks are `_admit`'s and are
    shared with the other four addresses; everything below is check 9 — select,
    order, page — which is the only one that differs per route.

    ⚠ **`start_date` AND `end_date` ARE REQUIRED HERE AND OPTIONAL ON THE
    OTHERS, AND THE DIFFERENCE IS DELIBERATE.** The ledger is the largest set
    this product can hand over — every bill line and every payment writes
    journal lines, so a month at the top of T5 is around 200,000 rows. An
    unbounded pull is the paging trap with nothing to bound it: the table moves
    under the walk, page numbers skip, and **a missed journal entry is a missed
    posting** that neither side can see. A caller that forgets the window is
    told so in six words rather than served a walk that quietly loses rows.

    ⚠ **THE ENVELOPE CARRIES TWO TOTALS BECAUSE TWO THINGS ARE BEING COUNTED
    (`CR-110-BRC04` phase 2 wave 5).** `total_records` counts what `records`
    holds — partner ROWS — on this route exactly as on the other four, so a
    partner's job can add up what it received and compare. `total_entries` is
    the paged unit, and `total_pages` is derived from IT, because **the page is
    a page of ENTRIES**: pairing a debit with its credit reads a whole entry,
    so a page boundary may never fall inside one. `seams/ledger.collectable`
    carries the argument.
    """
    operation, label = SERVED_ROUTES["ledger"]
    try:
        caller = _admit(request, operation=operation, window=label)
    except _Stop as stop:
        return stop.response

    since = _parse_date(request.GET.get("start_date"))
    until = _parse_date(request.GET.get("end_date"))
    if since is None or until is None:
        serve.record_read(
            caller=caller,
            operation=operation,
            rows=0,
            window=f"{label}, no window given",
            refused=True,
        )
        return JsonResponse(LEDGER_WINDOW_REQUIRED, status=400)

    page, size = _page_params(request)
    queryset = ledger_seam.collectable(since=since, until=until)
    total_entries = queryset.count()
    total_rows = ledger_seam.row_total(queryset)
    total_pages = max(1, -(-total_entries // size))

    # ⚠ **ONE CONTEXT FOR THE WHOLE PAGE, NOT ONE PER ENTRY (`P5.2` · `P5.3`).**
    # The tax authority behind a line and the printed document number behind an
    # entry are two queries here and two queries PER ROW if `as_record` is left
    # to resolve them itself — which on a month at the top of T5 (~200,000
    # journal lines) is the difference between a constant and a cost paid on
    # every row, and it would look perfectly fast on a demo tenant with 167
    # entries. Same shape and same argument as `seams/billing.page_context`.
    page_entries = list(queryset[(page - 1) * size : page * size])
    context = ledger_seam.page_context(page_entries)

    records: list[dict[str, Any]] = []
    for entry in page_entries:
        for record in ledger_seam.as_record(entry, context):
            # BR-INT-054: a partner's own words for an account are Runbooks'.
            # This returns {} today and the test asserts it does.
            record.update(serve.partner_fields(record))
            records.append(record)

    serve.record_read(
        caller=caller,
        operation=operation,
        rows=len(records),
        window=f"{label}, {_window_text(since, until)}",
        page=page,
        total_pages=total_pages,
    )

    return JsonResponse(
        {
            "total_records": total_rows,
            "total_entries": total_entries,
            "page": page,
            "page_size": size,
            "total_pages": total_pages,
            # ⚠ **THE GAP IS NAMED, NOT HIDDEN — AND SINCE `P0.3` IT IS A GAP
            # IN HISTORY RATHER THAN IN THE PRODUCT.** `posting.post()` stamps
            # `BR-LED-021`'s `JE-` number on every entry it posts, so a window
            # of new work carries no note at all. A window reaching back before
            # 2026-09-24 still meets unnumbered entries, nothing backfills them,
            # and a partner reading a null key needs to know it is our history
            # and not their request. See `LEDGER_NUMBER_GAP` for the rename.
            **({"records_note": LEDGER_NUMBER_GAP} if any(
                one["id"] is None for one in records
            ) else {}),
            "records": records,
        },
        status=_status_for("ok"),
    )


# ═════════════════════════════════════════════════════════════════════════
# CR-132-BRC07 · NEW WORLD / LOGOS — THE RECEIPT
# ═════════════════════════════════════════════════════════════════════════


#: What a caller is told when the receipt window is missing. Reached only
#: AFTER all the door's checks, so it may be specific where `_refused()` may
#: not — the same posture as `LEDGER_WINDOW_REQUIRED` above.
RECEIPTS_WINDOW_REQUIRED = {
    "error": "Send start_date and end_date.",
    "code": "DATE_RANGE_REQUIRED",
}

#: A page whose XML failed `newworld.validate` (DEF-INT-10304). Our fault,
#: hence a 500, and reachable only past every check of the door.
RECEIPTS_INVALID = {
    "error": "The receipts failed their format check.",
    "code": "RECEIPTS_INVALID",
}

#: The media type their importer takes. Declared here rather than composed, so
#: the header and the fixture cannot drift.
RECEIPTS_CONTENT_TYPE = "application/xml; charset=utf-8"


@partner_key_required
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def partner_receipts(request):
    """`GET /api/partner/v1/receipts` — our payments as New World Receipts.

    ⚠ **`authentication_classes = []` IS THE DOOR BEING THE DOOR, AND IT IS
    NAMED IN `tests/test_be_default_authentication.py` RATHER THAN THE
    ASSERTION BEING WIDENED.** Every partner route opts out explicitly and
    presents a key at `serve.resolve_caller` before it does anything at all; a
    caller who could already authenticate would not be one. That test asserts
    the opt-out list EXACTLY, so it goes red the day this address lands and the
    address is added deliberately — which is what `DEF-INT-4256` records
    happening the one time it was not.

    ⚠ **NO `PARTNER_RENDERERS` ON THIS ONE, DELIBERATELY.** The other routes
    negotiate JSON and CSV; this address serves exactly one media type and
    returns a plain `HttpResponse`, so there is nothing for DRF to negotiate
    over. Registering `JSONRenderer` here would make `?format=json` answer a
    shape their importer has never seen, from an address whose whole purpose is
    one vendor's file.

    THE THREE SELECTORS, AND WHY THE ORIGIN IS NOT ONE OF THEM
    -----------------------------------------------------------
    `start_date` and `end_date` are REQUIRED, as on the ledger and for the same
    reason: an unbounded pull walks a table that is moving underneath it and
    **a missed receipt is a missed posting** neither side can see. `page` and
    `page_size` are the surface's own.

    **The origin is NOT a parameter.** The feed is `webhook` only — PO ruling
    2026-09-22, and it is New World's own requirement rather than our narrowing
    — so it is a property of this address, not a choice a caller makes. A
    partner that could ask for `origin=entry` could quietly double-count every
    counter receipt their cashier system already posted.

    ⚠ **THE ENVELOPE OF EXCEPTIONS IS IN THE HEADERS, NOT THE BODY.**
    The body is their XML and must stay exactly what their importer parses, so
    what went wrong on our side travels as response headers and on the run row:
    how many receipts did not balance, by how much, how many distributions
    carried no GL account, and which tenders went out unmapped. **That is the
    half that makes *send it even if it is not balance* safe** — an unbalanced
    receipt nobody counted is the silent failure the ruling was protecting
    against, one step further along.
    """
    operation, label = SERVED_ROUTES["receipts"]
    try:
        caller = _admit(request, operation=operation, window=label)
    except _Stop as stop:
        return stop.response

    since = _parse_date(request.GET.get("start_date"))
    until = _parse_date(request.GET.get("end_date"))
    if since is None or until is None:
        serve.record_read(
            caller=caller,
            operation=operation,
            rows=0,
            window=f"{label}, no window given",
            refused=True,
        )
        return JsonResponse(RECEIPTS_WINDOW_REQUIRED, status=400)

    page, size = _page_params(request)
    queryset = payments_seam.page_queryset(
        since=since,
        until=until,
        origin=payments_seam.ORIGIN_ONLINE,
    ).prefetch_related("allocations__invoice")
    total = queryset.count()
    total_pages = max(1, -(-total // size))
    rows = list(queryset[(page - 1) * size : page * size])

    emission = newworld.emit(rows)

    # ⚠ **FAIL CLOSED: A PAGE THAT FAILS NEW WORLD'S TEMPLATE IS NOT SERVED**
    # (PO 2026-10-21, answer 4 — one builder, one correct shape — and point 6,
    # validate before it leaves; DEF-INT-10304). The access log records the
    # refusal and what was wrong; the partner gets a 500, never a bad file.
    problems = newworld.validate(emission.body)
    if problems:
        serve.record_read(
            caller=caller,
            operation=operation,
            rows=0,
            window=f"{label}, failed the format check: " + "; ".join(problems[:5]),
            refused=True,
        )
        return JsonResponse(RECEIPTS_INVALID, status=500)

    # ⚠ **THE RUN ROW CARRIES THE EXCEPTIONS, BECAUSE IT IS WHAT A MANAGER
    # READS ON S142.** A count in a response header is seen by the partner's
    # job and by nobody here; this is the half of *never silently* that lands
    # on our side of the wire.
    window = f"{label}, {_window_text(since, until)}{_named_suffix(request)}"
    if emission.short_count:
        window += (
            f" · {emission.short_count} did not balance, by {emission.short_total}"
        )
    if emission.unresolved_gl_count:
        window += f" · {emission.unresolved_gl_count} with no GL account"
    for tender in emission.unmapped_tenders():
        window += f" · tender {tender} unmapped"

    serve.record_read(
        caller=caller,
        operation=operation,
        rows=len(emission.receipts),
        window=window,
        page=page,
        total_pages=total_pages,
    )

    response = HttpResponse(
        emission.body,
        status=_status_for("ok"),
        content_type=RECEIPTS_CONTENT_TYPE,
    )
    response["X-Receipts-Total"] = str(total)
    response["X-Receipts-Page"] = str(page)
    response["X-Receipts-Total-Pages"] = str(total_pages)
    # ⚠ **STATED EVEN WHEN THEY ARE ZERO.** A header that appears only when
    # something is wrong is a header a partner's job never learns to read, and
    # its absence is indistinguishable from an older build that never sent it.
    response["X-Receipts-Unbalanced"] = str(emission.short_count)
    response["X-Receipts-Unbalanced-Total"] = str(emission.short_total)
    response["X-Receipts-Unresolved-GL"] = str(emission.unresolved_gl_count)
    return response


# ═════════════════════════════════════════════════════════════════════════
# CR-111-BRC04 · THE TWO NEW ADDRESSES
# ═════════════════════════════════════════════════════════════════════════


#: `consumer-info`'s two selectors. Exactly one of them, never both, never
#: neither — see `_consumer_selection`.
CONSUMER_NUMBERS_PARAM = "consumer_numbers"
CONSUMER_ID_PARAM = "consumer_id"

CONSUMER_SELECTOR_REQUIRED = {
    "error": "Send consumer_numbers or consumer_id.",
    "code": "CONSUMER_SELECTOR_REQUIRED",
}
CONSUMER_SELECTOR_AMBIGUOUS = {
    "error": "Send only one of the two.",
    "code": "CONSUMER_SELECTOR_AMBIGUOUS",
}


class _BadSelection(Exception):
    """A `400` body carried the way `_Stop` carries a refusal."""

    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(payload["code"])
        self.payload = payload


def _consumer_selection(request: Any) -> list[str]:
    """Which accounts this call is about — **one selector, never two.**

    `consumer_numbers=A-10432,A-10433` (many) or `consumer_id=A-10432` (one).
    **Both together, or neither, is a `400`**, and the two refusals are
    different sentences because they are different mistakes: one caller sent
    nothing and the other sent too much, and telling them apart is the whole
    value of the `400`.

    ⚠ **NEITHER IS A NO-OP AND THAT IS WHY IT IS REFUSED RATHER THAN SERVED.**
    The obvious alternative — no selector means every customer, exactly like
    `/accounts` — is the dangerous one: `consumer-info` is the address a
    partner calls for ONE account, usually while a person waits, and a typo in
    the parameter name would silently walk 40,000 accounts instead of raising.
    A caller that wants all of them has `/accounts`, which is the same
    implementation behind a different tick since `DEF-INT-5622`.

    ⚠ **SAFE TO BE SPECIFIC HERE FOR `_bad_request`'s REASON**: this is
    reachable only after all eight checks, so the caller already holds a live
    key for a live utility and learns nothing from the sentence.

    ⚠ **THE LIST IS BOUNDED BY THE PAGE, NOT BY A CAP** (`NFR-5` — no hard caps
    anywhere). A caller naming 5,000 numbers gets them a page at a time with
    `total_records` saying 5,000, exactly as every other list on this surface
    behaves. Blanks and duplicates are dropped, and order is OURS
    (`ORDER_BY`), not the order they were named in — a partner that needs
    their own order has the numbers it sent.
    """
    many = str(request.GET.get(CONSUMER_NUMBERS_PARAM) or "").strip()
    one = str(request.GET.get(CONSUMER_ID_PARAM) or "").strip()
    if many and one:
        raise _BadSelection(CONSUMER_SELECTOR_AMBIGUOUS)
    if not many and not one:
        raise _BadSelection(CONSUMER_SELECTOR_REQUIRED)
    raw = many or one
    seen: dict[str, None] = {}
    for part in raw.split(","):
        value = part.strip()
        if value:
            seen.setdefault(value, None)
    if not seen:
        # A parameter that was present and held only commas and spaces. It named
        # nothing, so it is the *neither* case rather than a zero-row answer —
        # an empty `records` here would read as *this utility has no such
        # account* about a question nobody actually asked.
        raise _BadSelection(CONSUMER_SELECTOR_REQUIRED)
    return list(seen)


@partner_key_required
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@renderer_classes(PARTNER_RENDERERS)
def partner_consumer_info(request):
    """`GET /api/partner/v1/consumer-info` — the customer record, by number.

    **ONE IMPLEMENTATION, TWO ADDRESSES.** This is `_serve_accounts` with a
    selector in front of it: the same door (`_admit`), the same seam, the same
    composer, the same shape and the same envelope. ⚠ **AND SINCE
    `DEF-INT-5622` IT IS ITS OWN OPERATION — `serve_consumer_info` — SO THE
    DOOR AND THE RATE WINDOW ARE ITS OWN AND NOT THE LIST'S.** That is what
    gives it a row on the connector screen, which is the whole defect: it was
    built, routed, tested and INVISIBLE. ⚠ **A second
    implementation is the thing this route most invites and is exactly what it
    must not be** — the day a field was added to one and not the other, a
    partner reading a customer at two addresses would get two different answers
    from one utility and nothing on either side could see it.

    ⚠ **`remote_plan_id` IS SERVED HERE AND NOWHERE ELSE**, by PO ruling
    2026-09-17. Asked what it should carry: *"this rate plan ID for that
    account"*; asked in which APIs it is required, the answer is this one — it
    appears in no other payload of their document. `seams/customers.as_record`
    takes `with_detail`, so they are declared fields on one composer rather than a
    second record type.

    ⚠ **`additional_data.payment_received` IS NOT SERVED AND IS NOT GUESSED**
    (`OQ-INT-12399`, OPEN). Their document carries it on this payload and what
    it MEANS was put to the PO and is the one question of the six they did not
    answer. It is a money field: the candidate readings — the last payment's
    amount, the total ever received, what was received this cycle — are three
    different numbers, and a finance system reconciling against the wrong one
    balances to nothing. **The key is absent rather than null**, for
    `_echoed_utility_id`'s reason: an absent key is the absence of an answer and
    a null is an answer.
    """
    try:
        numbers = _consumer_selection(request)
    except _BadSelection as bad:
        # ⚠ **AFTER THE DOOR, NEVER BEFORE IT.** `_serve_accounts` runs
        # `_admit` first, so this refusal cannot be reached by a stranger — but
        # this function is a view, so the selector has to be read here. The
        # order is preserved by doing the door's work inside `_serve_accounts`
        # and refusing only once it has returned something: see below.
        return _admit_then(request, bad)
    return _serve_accounts(
        request, route="consumer-info", with_detail=True, only_numbers=numbers
    )


def _admit_then(request: Any, bad: _BadSelection) -> Any:
    """Run the door, and only then hand back the selector's `400`.

    ⚠ **THIS EXISTS BECAUSE A `400` HANDED OUT BEFORE `_admit` IS AN
    ENUMERATION ORACLE, AND LANE A'S TEST CAUGHT EXACTLY THAT ONCE BEFORE.**
    `test_a_key_holding_one_tick_reads_the_reference_and_is_refused_elsewhere`
    went red on a `400 DATES_REQUIRED` reaching a caller who should have got the
    same five words as every other stranger. A malformed-parameter reply tells
    an unauthenticated caller that the address is real and that its parameters
    are named such-and-such; the refusal must come first and must be
    indistinguishable.
    """
    operation, label = SERVED_ROUTES["consumer-info"]
    try:
        caller = _admit(request, operation=operation, window=label)
    except _Stop as stop:
        return stop.response
    serve.record_read(
        caller=caller,
        operation=operation,
        rows=0,
        window=f"{label}, no account named{_named_suffix(request)}",
        refused=True,
    )
    return JsonResponse(bad.payload, status=400)


# ── the bill document ────────────────────────────────────────────

BILL_ID_PARAM = "bill_id"

BILL_ID_REQUIRED = {"error": "Send bill_id.", "code": "BILL_ID_REQUIRED"}


@partner_key_required
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@renderer_classes(PARTNER_RENDERERS)
def partner_bill_download(request):
    """`GET /api/partner/v1/bill-download/?bill_id=…` — one bill, as the page
    we print.

    ⚠ **200 IS PDF BYTES AND EVERY OTHER CODE IS A JSON SENTENCE
    (`BR-INT-044`).** You cannot put a refusal inside a PDF — a partner's
    reader would open it and show a human a document that says nothing useful,
    or fail to open it at all — and the refusal has to be the same bytes every
    time. So this route answers exactly one content type on success and
    `_refused()`'s single body on failure, which is the same object every other
    address on this surface returns and takes no argument by design.

    ⚠⚠ **A BILL THAT IS NOT THIS UTILITY'S ANSWERS THE SAME SENTENCE AS A
    REFUSED KEY, AND THAT IS THE WHOLE SECURITY ARGUMENT OF THIS ROUTE.** *No
    such bill* and *not yours* must be one answer, because a partner that could
    tell them apart could walk our invoice numbers and learn which ones exist —
    an enumeration oracle on a money document. **It is not a comparison we make
    and then hide; it is structural**: the lookup goes through
    `billing_seam.collectable()`, which filters on `tenant_id` AND on the
    collectable statuses, so an unknown number, another utility's bill and a
    draft all return `None` from the same `.first()` and leave through the same
    line. There is no branch here that knows which of the three it was.

    ⚠ **THE PDF IS THE ONE WE ALREADY RENDER — `documents.render_invoice` and
    `frozen_bill.reproduce`, which is what `GET /invoices/{id}/document.pdf`
    serves to our own screens.** A second renderer would be a second bill: the
    same run, the same account, two documents, and the customer's copy and the
    partner's copy disagreeing about a total is the kind of thing that is found
    by a customer. `X-Document-Provenance` travels too, for `BR-NOT-027`'s
    reason — a PDF has nowhere to carry a caption, so a re-rendered bill says
    so in a header rather than pretending to be the kept original.

    ⚠ **THE FILENAME IS THE INVOICE NUMBER**, and `inline` rather than
    `attachment`: a partner showing a bill to a customer in a browser wants the
    page, and their own client decides whether to save it.

    ⚠ **NO `format=csv` HERE.** A CSV of one PDF is not a thing, and a
    `format` parameter that is silently ignored on one route of a surface where
    it works on three others is `DEF-014`'s cousin — so it is not accepted and
    not mentioned; the route serves one representation.
    """
    operation, label = SERVED_ROUTES["bill-download"]
    try:
        caller = _admit(request, operation=operation, window=label)
    except _Stop as stop:
        return stop.response

    bill_id = str(request.GET.get(BILL_ID_PARAM) or "").strip()
    if not bill_id:
        # Specific, and safe to be: reachable only past all eight checks. It is
        # NOT the refusal — a caller that forgot a parameter has a bug, and
        # handing it the same five words a stolen key gets would send an
        # engineer to look at their credentials.
        serve.record_read(
            caller=caller,
            operation=operation,
            rows=0,
            window=f"{label}, no bill named{_named_suffix(request)}",
            refused=True,
        )
        return JsonResponse(BILL_ID_REQUIRED, status=400)

    invoice = (
        billing_seam.page_queryset().filter(invoice_no=bill_id).first()
    )
    if invoice is None:
        serve.record_read(
            caller=caller,
            operation=operation,
            rows=0,
            window=f"{label}, not ours{_named_suffix(request)}",
            refused=True,
        )
        return _refused()

    from apps.billing import documents as billing_documents
    from apps.billing import frozen_bill
    from apps.billing.documents_api import PROVENANCE_HEADER, _verified
    from apps.billing.exceptions import BillingRuleError

    try:
        reproduction = frozen_bill.reproduce(invoice)
        if reproduction.is_original and reproduction.pdf is not None:
            page = _verified(reproduction.pdf)
            content_type = reproduction.pdf.content_type
            provenance = frozen_bill.PROVENANCE_ORIGINAL
        else:
            rendered = billing_documents.render_invoice(invoice)
            page = rendered.pdf
            content_type = rendered.pdf_content_type
            provenance = frozen_bill.PROVENANCE_RE_RENDERED
    except BillingRuleError:
        # ⚠ **A BILL WE CANNOT RENDER IS THE REFUSAL, NOT A 422.** Our own
        # screens answer `422` here with the renderer's sentence, because a
        # clerk is looking at the bill and needs to know what is wrong with it.
        # A partner is not: telling it *this bill exists but will not render*
        # distinguishes a real invoice number from an invented one, which is the
        # oracle this whole route is built to close.
        serve.record_read(
            caller=caller,
            operation=operation,
            rows=0,
            window=f"{label}, would not render{_named_suffix(request)}",
            refused=True,
        )
        return _refused()

    serve.record_read(
        caller=caller,
        operation=operation,
        rows=1,
        window=f"{label}, {bill_id}{_named_suffix(request)}",
    )
    response = HttpResponse(page, content_type=content_type, status=_status_for("ok"))
    response["Content-Disposition"] = f'inline; filename="{bill_id}.pdf"'
    response[PROVENANCE_HEADER] = provenance
    return response


# ════════════════════════════════════════════════════════════════════════
# 2026-09-24 · THE MAKE PAYMENT API — THE FIRST WRITE ON THIS DOOR
# ════════════════════════════════════════════════════════════════════════


@partner_key_required
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@renderer_classes([JSONRenderer])
def partner_make_payment(request):
    """`POST /api/partner/v1/make-payment/` — Invoice Cloud posts us a payment.

    **Confirmed with the Product Owner before a line was written** — decision
    log 2026-09-24, *"THE INVOICE CLOUD *MAKE PAYMENT* API, CONFIRMED BEFORE A
    LINE IS WRITTEN"*, which is this endpoint's specification and names the
    eight authorisation checks, the date mapping, the status correction, the
    till-and-batch answer, the audit actor and five mismatches between the
    partner's document and this product.

    ⚠ **THIS VIEW IS THIN AND MUST STAY THIN (B8/LAW 0).** It runs the door,
    reads the payload, hands over, writes the run row and answers. Every rule
    it obeys belongs to somebody else: checks 1–8 to `_admit`, steps 9–19 to
    `invoice_cloud_payment`, and the payment itself to
    `payments.services.record_payment`, which is the only thing in this product
    that may write a payment row, an allocation or a journal line (hard rules
    4, 5 and 7).

    ⚠ **THE REVERSAL THIS BUILDS, STATED AND NOT ASSUMED.** `BR-INT-071` is
    CONFIRMED and says in as many words *"`POST /api/partner/v1/make-payment/`
    IS NOT BUILT"* and *"A PARTNER DOES NOT POST A PAYMENT TO US"* (PO
    2026-09-17). **It was reversed by the PO on 2026-09-18 in four words —
    *"they post to us daily"* — and the whole design was then walked with them
    and confirmed on 2026-09-24.** The supersession chain is written into
    `BR-INT-071`'s own row and into `BR-INT-083`, which is the rule this
    address implements. A lane that meets the old sentence first must read the
    dated clause under it.

    ⚠ **THE SCOPE IS THE SECURITY PROPERTY AND IT IS NOT IN THIS FILE.** A key
    may call this only if its own `scope` names `record_payment`, which only
    `pay_invoicecloud_partner` declares. A key without it is refused by
    `_admit`'s check 5 — the SAME bytes, the SAME `404` and the SAME padded
    floor an unknown key gets — so a read-only key cannot create money and
    cannot learn that a write door exists.

    ⚠ **`_admit` FIRST, BEFORE THE BODY IS TOUCHED.** `BR-INT-021`, and
    `_admit_then`'s own docstring records the case that caught it once
    already: a `400` about a field name handed to an unauthenticated caller
    tells them the address is real and what its parameters are called. Every
    payload refusal below is reachable only past all eight checks, which is
    what makes it safe for them to be specific.

    ⚠ **`JSONRenderer` ALONE, NOT `PARTNER_RENDERERS`.** A CSV of one payment
    receipt is not a thing, and a `format=csv` that is silently ignored here
    while it works on three sibling routes is `DEF-014`'s cousin. One
    representation, and it is the one their document posts and parses.
    """
    from apps.integrations import invoice_cloud_payment as ic

    operation, label = SERVED_ROUTES["make-payment"]
    try:
        caller = _admit(
            request,
            operation=operation,
            window=label,
            direction=models.RUN_DIRECTION_INBOUND,
        )
    except _Stop as stop:
        return stop.response

    # ── 9 · the payload ────────────────────────────────────────────────────
    try:
        parsed = ic.read_request(request.data)
    except ic.PayloadRefused as bad:
        serve.record_write(
            caller=caller,
            operation=operation,
            rows=0,
            window=ic.window_text(None, outcome=f"refused · {bad.code}"),
            refused=True,
        )
        return JsonResponse({"error": bad.detail, "code": bad.code}, status=400)

    # ── 10–19 · resolve, hand over, and answer a replay as a replay ────────
    #
    # ⚠ **`PaymentRuleError` IS A `422` AND NEVER A `500`, AND THE RUN ROW IS
    # WRITTEN EITHER WAY.** `record_payment` raises it for everything a human
    # can act on — a deactivated tender, a currency the account does not hold,
    # a cheque fact that does not hold together. A partner whose payment we
    # would not take has to be told, because the money is real at their end and
    # they cannot un-take it; and a manager has to be able to SEE it, because
    # the alternative is a payment nobody on either side knows was refused.
    from apps.payments.exceptions import PaymentRuleError

    try:
        made = ic.record(caller_label=_caller_label(caller), request=parsed)
    except ic.PayloadRefused as bad:
        serve.record_write(
            caller=caller,
            operation=operation,
            rows=0,
            window=ic.window_text(parsed, outcome=f"refused · {bad.code}"),
            refused=True,
        )
        return JsonResponse({"error": bad.detail, "code": bad.code}, status=400)
    except PaymentRuleError as refusal:
        serve.record_write(
            caller=caller,
            operation=operation,
            rows=0,
            window=ic.window_text(parsed, outcome="refused · the payment rules"),
            refused=True,
        )
        return JsonResponse(
            {"error": str(refusal), "code": ic.CODE_PAYMENT_REFUSED},
            status=422,
        )

    outcome = (
        f"already recorded as {made.payment_no}"
        if made.duplicate
        else f"recorded {made.payment_no}"
    )
    serve.record_write(
        caller=caller,
        operation=operation,
        # ⚠ **ONE, INCLUDING A REPLAY.** A retried delivery is a call this
        # utility handled and answered; recording it as zero would make a
        # partner's retry storm invisible on the access log, which is one of
        # the few things a manager can actually act on.
        rows=1,
        window=ic.window_text(parsed, outcome=outcome),
    )

    # ── 20 · the answer ────────────────────────────────────────────────────
    #
    # ⚠ **OUR NUMBER, OUR STATUS, OUR AMOUNT, THEIR REFERENCE ECHOED.** The
    # amount is a STRING to two decimals — hard rule 2, money DISPLAYED to two,
    # and a JSON number would be a float on the far end (`seams/payments.py`
    # carries the same paragraph for the read direction).
    #
    # ⚠ **`status` IS OURS AND IS NEVER TRANSLATED.** It is the row's own
    # status, and since `CR-186-BRC10` (PO 2026-10-21, `OQ-PAY-12627` answered
    # `posted`) that is `posted`: the payment is applied to its bill at posting
    # and the balance has moved. Until 2026-10-21 this read `processing` and
    # the comment here said serving `posted` would be a false claim; the
    # ruling is what made it true, not a mapping. A replay answers the
    # ORIGINAL row's status, which may by then be `cleared`.
    return JsonResponse(
        {
            "payment_no": made.payment_no,
            "status": made.status,
            "amount": payments_seam.display_amount(made.amount),
            "currency": made.currency,
            "payment_reference": made.reference,
            "duplicate": made.duplicate,
            # `CR-186-BRC10` — the day's Invoice Cloud deposit batch (one per
            # provider per day), null when payments stamped none.
            "deposit_batch_id": made.deposit_batch_id,
            "deposit_batch_code": made.deposit_batch_code,
            # Honest absences, for a machine. See `invoice_cloud_payment.
            # _UNAVAILABLE`.
            "unavailable": list(made.unavailable),
        },
        status=_status_for("ok"),
    )


def _caller_label(caller: serve.PartnerCaller) -> str:
    """What `audit_log.actor_label` says for a partner payment.

    ⚠ **THE CONNECTOR, NOT A USER AND NOT A BLANK.** `actor_user_id` is NULL
    and `actor_kind` is `integration` — *"a partner system acting through a
    connector"*, which is `core.audit`'s own definition of the kind. The label
    is the connection's own name, so a manager reading the trail sees
    *InvoiceCloud (reads from us)* rather than a blank or a meaningless system
    user; the KEY that was used is already on the run row, and the two together
    answer *which partner, which key, which call*.

    **The connection's clerk-given label wins over the manifest's display
    name**, because a utility with two Invoice Cloud connections has named them
    for a reason and the trail should use the word they chose. The manifest is
    the fallback and the provider key is the floor, so this can never return an
    empty string — `AutomationActor` refuses one at construction, and a
    refusal there would lose the audit row and take the payment with it (hard
    rule 7).
    """
    connection = caller.connection
    manifest = REGISTRY.get(connection.provider_key)
    return (
        (connection.label or "").strip()
        or (manifest.display_name if manifest is not None else "")
        or connection.provider_key
    )


@partner_key_required
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@renderer_classes(PARTNER_RENDERERS)
def partner_reference(request):
    """`GET /api/partner/v1/reference?company_id=…` — every code
    this product can put on a partner payload, with its meaning.

    PO 2026-09-16, verbatim: *"you ahve to extend the defination of codes so
    that partner can resolve all codes at there end otherwise they will ahve an
    issues"*. A partner pulls it once, caches it, and never meets an unknown
    value.

    ⚠ **NO SCOPE TICK — ANY VALID KEY MAY READ IT** (`operation=None`). The
    scope guard still bites: `scope_permits` answers `False` for a key with
    NOTHING granted, so a key that may call none of the four may not read the
    description of what it may call either. What it may not do is single out
    one of the four ticks, because a partner that may read bills needs the bill
    vocabulary and a partner that may read the ledger needs most of the same
    one — a per-tick reference would be four documents that overlap, and the
    first code a partner met outside its own slice would be the failure this
    endpoint exists to prevent.

    ⚠ **IT CARRIES NO UTILITY RECORDS, WHICH IS WHY IT IS NOT AN OPERATION.**
    Four of the seven lists are closed vocabularies of the product; three are
    the tenant's own LOOKUPS — the services they sell, the tenders they take,
    the account statuses they use — which is configuration a clerk edits on
    Settings, not a customer, a bill or a payment. So it is metered
    (`REFERENCE_WINDOW`) and recorded like every other partner read, and it
    adds no row to the connection screen.
    """
    try:
        caller = _admit(request, operation=None, window="Reference")
    except _Stop as stop:
        return stop.response

    body = reference.payload(caller.tenant_id)
    serve.record_read(
        caller=caller,
        # The run row hangs on an operation the manifest declares
        # (`services.start_run` refuses anything else) and `serve_bill` is the
        # one whose vocabulary dominates this document. ⚠ The WINDOW is what a
        # manager actually reads, and it says *Reference* — so the row is not
        # mistaken for a bill collection.
        operation=SERVED_ROUTES["bills"][0],
        rows=sum(len(one) for one in body.values()),
        window="Reference, every code",
    )
    return JsonResponse(body, status=_status_for("ok"))


@partner_key_required
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@renderer_classes(PARTNER_RENDERERS)
def partner_openapi(request):
    """The published specification, *"rather than a bespoke document"* (§1).

    ⚠ **AUTHENTICATED LIKE THE OTHER TWO.** A specification is not a secret,
    but an unauthenticated one at a tenant's own address answers *does this
    utility exist* to anybody who asks, which is the enumeration oracle
    `BR-INT-044` exists to close, arriving through the one door nobody thinks
    to lock. It refuses with the same five words as everything else.

    It is DERIVED FROM THE MANIFEST, so it cannot describe an operation this
    product does not serve, and a field added to a seam without being added
    here shows up as a difference rather than as a silent extra.
    """
    try:
        # ⚠ `operation=None` — READING THE SPECIFICATION IS NOT CALLING AN
        # OPERATION (`CR-110-BRC04`). The scope guard still applies: a key with
        # nothing granted may not read the description of what it may call,
        # because a key that may call nothing has no business here at all. A
        # key that may call one of the two may read the whole document, which
        # describes only what this connector serves and no utility's data.
        caller = serve.resolve_caller(
            provider_key=partner_provider_keys(),
            presented_key=_presented_key(request),
            source_address=_source_address(request),
            operation=None,
        )
    except serve.PartnerRefused:
        return _refused()

    # ⚠ **THE CALLER'S OWN CONNECTOR, AND IT WAS *ANY OF THE FIVE* UNTIL
    # `CR-110-BRC04` PHASE 2.** This read `partner_provider_keys()[0]` on the
    # reasoning that the five ERPs are one drawing repeated — true of their
    # SCREENS, which is what was measured, and never a claim about their
    # operations. Aclarian has four reads and declared addresses where the other
    # four have three and none, so *any of the five* became **a partner holding
    # a Workday key reading Aclarian's specification**: an offer of two
    # endpoints their key may not call, and silence about the ones it may.
    #
    # The caller's key names its own connection, which names its own connector.
    # Nothing is left to alphabetical order, and the day a sixth ERP is added
    # this line needs no thought at all.
    manifest = REGISTRY.require(caller.connection.provider_key)
    served = {"payments": "/v1/payments", "billing": "/v1/billing"}
    paths: dict[str, Any] = {}
    for operation in manifest.operations:
        # ⚠ **THE MANIFEST'S OWN ADDRESS WINS (`CR-110-BRC04` phase 2).** Until
        # this wave the route was derived by string surgery on the operation
        # NAME against a two-entry map, so an operation the map did not know
        # was silently SKIPPED — `serve_customer` has been declared since wave C
        # and appeared in no published specification, and `serve_ledger` would
        # have joined it. A partner reads this document to learn what it may
        # call; an operation missing from it is a capability nobody can
        # discover, and nothing anywhere went red (hard-won law 1).
        #
        # The fallback is kept for the four ERP manifests that have not declared
        # their paths yet: they behave exactly as before rather than vanishing.
        route = operation.served_path or served.get(
            operation.name.replace("serve_", "").replace("bill", "billing").replace("payment", "payments")
        )
        if route is None:
            continue
        # An address whose wave has not landed says so HERE too, or the
        # specification promises a payload the server answers `501` to.
        held = next(
            (what for what, (name, _label) in SERVED_ROUTES.items() if name == operation.name),
            None,
        )
        wave = ROUTE_WAVE.get(held or "") if operation.served_path else None
        # ⚠ **A RETIRED ADDRESS SAYS SO IN THE DOCUMENT TOO** (`CR-110-BRC04`
        # phase 2 wave 4). The four ERP manifests that declare no `served_path`
        # still fall back to the phase-1 pair above, and that pair now answers
        # `410`. A specification that promised a payload where the server
        # answers *gone* is the same fault as one that promised a payload where
        # it answers `501`, which the line above already refuses.
        retired = RETIRED_FOR.get(_RETIRED_PATH_FOR.get(route, ""))
        # ⚠⚠ **THE METHOD IS READ OFF THE OPERATION, NOT ASSUMED (2026-09-24).**
        # This block emitted `"get"` with `from`/`to`/`page`/`page_size` for
        # EVERY operation that declared an address, which was true of every
        # address on this surface until `record_payment` landed — and would
        # then have published **`GET /partner/v1/make-payment/` with four query
        # parameters** for a route that is a POST taking a JSON body. A partner
        # builds their client from this document; they would have built the
        # wrong call and met our five-word refusal, and gone looking at their
        # key. That is hard-won law 1 with the DOCUMENT as the culprit, and it
        # is `DEF-INT-5586`'s shape — a published capability nobody can
        # actually reach — arriving from the opposite direction.
        #
        # `direction == "in"` is *the data moves IN*, which on a door we
        # publish means they SEND it. The same property `record_write` files
        # the run row under, read once, in both places, from the manifest.
        writes = operation.direction == "in"
        method = "post" if writes else "get"
        paths[route] = {
            method: {
                "summary": operation.description,
                # A write takes no window and no paging; it takes a body. The
                # FIELD NAMES are the partner's own and are named here because
                # a specification that says "send a payment" and does not say
                # what a payment looks like is a document nobody can build
                # from — and because an absent or unknown tender is REFUSED
                # rather than defaulted (`OQ-PAY-12632`).
                **(
                    {
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {"schema": _make_payment_schema()}
                            },
                        }
                    }
                    if writes
                    else {
                        "parameters": [
                            {"name": "from", "in": "query", "schema": {"type": "string", "format": "date"}},
                            {"name": "to", "in": "query", "schema": {"type": "string", "format": "date"}},
                            {"name": "page", "in": "query", "schema": {"type": "integer"}},
                            {"name": "page_size", "in": "query", "schema": {"type": "integer"}},
                        ]
                    }
                ),
                "responses": {
                    str(_status_for("ok")): {
                        "description": (
                            "The payment, recorded. `duplicate: true` means this reference "
                            "was already recorded and the payment named is the original."
                            if writes
                            else "One page, in the partner envelope."
                        )
                    },
                    str(_status_for("refused")): {
                        "description": serve.REFUSAL_SENTENCE,
                        "content": {"application/json": {"schema": _refusal_schema()}},
                    },
                    "429": {
                        "description": "Too many requests this minute.",
                        "content": {"application/json": {"schema": _rate_limited_schema()}},
                    },
                    **(
                        {"501": {"description": f"Not built yet — {wave}."}}
                        if wave
                        else {}
                    ),
                    **(
                        {"410": {"description": f"Retired — use {retired}."}}
                        if retired
                        else {}
                    ),
                },
            }
        }
    return JsonResponse(
        {
            "openapi": "3.0.3",
            "info": {"title": manifest.display_name, "version": "1"},
            "paths": paths,
            "components": {
                "schemas": {
                    "partner_paged": {
                        "type": "object",
                        "properties": {
                            "total_records": {"type": "integer"},
                            "page": {"type": "integer"},
                            "page_size": {"type": "integer"},
                            "total_pages": {"type": "integer"},
                        },
                    }
                }
            },
        },
        status=_status_for("ok"),
    )


# ═══════════════════════════════════════════════════════════════════════════
# The manager's window — S142
# ═══════════════════════════════════════════════════════════════════════════

def _hint_of(run) -> str | None:
    """The masked hint the run was recorded under — `••••7Q2F`.

    Read off the END of the summary, which `serve.record_read` composes, and
    validated as a MASK before it is served: anything that is not `••••` plus
    four characters is dropped rather than passed through. A hint field that
    would render an arbitrary tail of a sentence is one bad summary away from
    showing something it should not.
    """
    tail = (run.summary or "").rsplit(" · ", 1)[-1].strip()
    return tail if tail.startswith("••••") and len(tail) == 8 else None


#: A read of more than this many records in one page is drawn in the amber
#: emphasis on S142 (frame 46.2's fourth row: *Payments, 2 years · 98,204*).
#: It is a DISPLAY judgment, not a rule — nothing is refused because of it.
UNUSUAL_ROWS = 10_000

#: How many ordinary rows the list carries, and how many unusual ones are
#: pulled in from beyond it. The second number exists so a partner cannot bury
#: one big collection under a hundred small ones — see `access_log`.
RECENT_ROWS = 100
UNUSUAL_ROWS_SHOWN = 25


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def access_log(request, key: str):
    """`GET /integrations/{key}/access-log` — *Who has been reading* (S142).

    One row per page a partner took: when, what they took, how many, and the
    key's HINT. Never the key — `IntegrationRun` never held one, because
    `PartnerCaller` never carried one out of `resolve_caller()`.

    ⚠ **THIS IS NOT A SECOND RECORD.** Wave C's `IntegrationRun` is the record,
    filtered to `direction = inbound_read`; the plan says so and inventing an
    `AccessLog` table would have put the same fact in two places and let them
    disagree. The screen's name is *Who has been reading*; the storage is runs.
    """
    tenant_id = require_tenant(request)
    REGISTRY.require(key)  # an unknown provider key is a server-side refusal
    # ⚠ **`tenant_id` IS BELT AND BRACES AND IT IS NOT OPTIONAL (`DEF-INT-5568`).**
    # RLS `FORCE` scopes this read on PostgreSQL, so the keyword changes nothing
    # on a healthy database — measured, both ways, 2026-09-17. It is here for the
    # reason `runners/serve.py::_connection_for` gives in the same words: the
    # suite runs on SQLite, **which has no RLS at all**
    # (`config/settings/test.py` hardcodes it), so this query leaking every
    # utility's reads onto one manager's screen passed the ENTIRE suite. It did.
    #
    # ⚠ AND `connection__provider_key` IS WHY IT READ AS SCOPED. A connection is
    # a row that carries its tenant; a PROVIDER KEY is a string every utility on
    # that connector shares — two utilities both on Aclarian is the ordinary
    # case, not the edge one, and `erp_aclarian` narrows the query by nothing at
    # all. `G126` refuses the next one of these by name.
    reads = models.IntegrationRun.objects.filter(
        tenant_id=tenant_id,
        connection__provider_key=key,
        direction=models.RUN_DIRECTION_INBOUND_READ,
    )
    # ⚠ **THE UNUSUAL READS ARE FETCHED SEPARATELY, AND THAT IS THE WHOLE
    # POINT OF THE SCREEN.** The first draft took the newest hundred rows and
    # nothing else. This lane's own walkthrough then made a hundred ordinary
    # requests and the 48,000-row collection — the row S142 exists to show —
    # was pushed off the list. **That is failure 13 arriving through the fix
    # for failure 13:** a partner that wanted its big collection unnoticed
    # would only have to make a hundred small ones afterwards, and the screen
    # would agree.
    #
    # So the list is the newest hundred UNION every unusual read, merged and
    # ordered by time. A big collection cannot be buried under small ones.
    recent = list(reads.order_by("-started_at")[:RECENT_ROWS])
    unusual = list(
        reads.filter(attempted__gte=UNUSUAL_ROWS).order_by("-started_at")[:UNUSUAL_ROWS_SHOWN]
    )
    merged = {one.id: one for one in recent}
    merged.update({one.id: one for one in unusual})
    rows = sorted(merged.values(), key=lambda one: one.started_at, reverse=True)
    items = [
        {
            "when": row.started_at,
            "what": (row.summary or "").split(" · ")[0],
            "rows": row.attempted,
            "detail": row.summary,
            # ⚠ ITS OWN FIELD, NOT SOMETHING THE SCREEN SPLITS OUT OF
            # `detail`. `BR-INT-035` records a read *"under which key"* and the
            # first draft put the hint only inside the summary string, which
            # nothing rendered — so the one field that answers *who has been
            # reading* was missing from the screen of that name. A client that
            # parsed it out of the summary would break the first time somebody
            # rewrote the sentence, silently, and in the direction of showing
            # nothing at all.
            "hint": _hint_of(row),
            "unusual": row.attempted >= UNUSUAL_ROWS,
            "outcome": row.outcome,
        }
        for row in rows
    ]
    return Response(
        {
            "items": items,
            "total_records": sum(one["rows"] for one in items),
            "unusual_rows_at": UNUSUAL_ROWS,
            # A COUNT, not a flag. Law 7's fifth shape: a declared blind spot
            # with no number attached is indistinguishable from an empty one,
            # so the header can say *2 unusual reads* rather than leaving a
            # reader to notice or not notice a heavier row.
            "unusual_reads": reads.filter(attempted__gte=UNUSUAL_ROWS).count(),
        }
    )


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def subprocessor_register(request):
    """`GET /integrations/subprocessors` — the register, derived (TC-8)."""
    require_tenant(request)
    return Response({"items": subprocessors.as_payload()})


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def grant_authority(request, key: str):
    """`POST /integrations/{key}/grant` — the audited grant (S5).

    `OQ-INT-1481` was ruled on 2026-09-04 to option (a): **the System Admin**
    authorises an outside system to read this utility's payments and bills, and
    the authorisation is *"an audited grant on the connection, plus a
    subprocessor-register row pointing inward"*. Both halves are here: the
    grant is written to the connection's non-secret config and to `audit_log`,
    and the register row is DERIVED from it on the next read — so the two can
    never disagree, because there is only one of them.

    ⚠ **NOT (c).** A signed data-processing-agreement reference is NOT a
    precondition. The PO did not require one and gating on a document reference
    would refuse a lawful connection. Nothing here asks for one.

    The permission class is the gate: `SettingsReadAnyWriteSystemAdmin` writes
    only for a System Admin, which is the ruling expressed as a class rather
    than as an `if` somebody could delete.
    """
    tenant_id = require_tenant(request)
    REGISTRY.require(key)
    # ⚠ **THE TENANT IS STATED HERE TOO, AND THIS SITE IS WORSE THAN THE ACCESS
    # LOG (`DEF-INT-5568`).** *The oldest connection with this provider key* is
    # the utility's own under RLS and **whichever utility connected first**
    # without it — so one System Admin's click would have authorised an outside
    # system to read ANOTHER utility's payments and bills, and written hard rule
    # 7's audit row against their connection. The screen would have said it
    # worked.
    #
    # ⚠ **`.order_by("created_at").first()` IS STILL ARBITRARY WITHIN ONE
    # UTILITY AND THAT IS A SEPARATE, OPEN QUESTION — `OQ-INT-12395`.**
    # `BR-INT-026`'s UNIQUE is (tenant, provider_key, environment), so a utility
    # may lawfully hold a SANDBOX and a PRODUCTION Aclarian connection, and this
    # picks whichever was made first. `_credential_matching` records the same
    # trap one door along and inverted it — the key names the connection. There
    # is no key here (a System Admin is clicking, not a partner), so which
    # connection a grant attaches to is a product decision and is NOT guessed.
    connection = (
        models.IntegrationConnection.objects.filter(tenant_id=tenant_id, provider_key=key)
        .order_by("created_at")
        .first()
    )
    if connection is None:
        raise errors.deny_as_not_found("BR-INT-035")

    actor = getattr(request, "user", None)
    name = (
        getattr(actor, "display_name", None)
        or getattr(actor, "full_name", None)
        or getattr(actor, "email", None)
        or "System Admin"
    )
    granted_at = datetime.now().astimezone()
    before = dict(connection.config or {}).get(serve.GRANT_CONFIG_KEY)
    config = dict(connection.config or {})
    config[serve.GRANT_CONFIG_KEY] = {
        "granted_by_name": str(name),
        "granted_at": granted_at.isoformat(),
    }
    connection.config = config
    connection.save(update_fields=["config", "updated_at"])

    # Hard rule 7's shape, applied to an authorisation rather than to money:
    # letting an outside system read a utility's whole payment history is at
    # least as consequential as one receipt, and the register row above is a
    # DERIVED view — the audit row is the durable record of who allowed it.
    core_audit.write_row(
        action="integration.partner.authorised",
        entity_type="integration_connection",
        entity_id=connection.id,
        actor_user_id=getattr(actor, "id", None),
        before={"authority_grant": before} if before else None,
        after={"authority_grant": config[serve.GRANT_CONFIG_KEY]},
    )
    return Response({"granted_by": str(name), "granted_at": granted_at})


urlpatterns = [
    # The partner's three. Registered before the staff routes for readability
    # only — they share no first segment, so order cannot matter.
    # ── phase 1 · the two that serve the FLAT `US-INT-041` payload ──────
    # Kept while waves 3 and 4 build the nested one at the addresses below;
    # see `partner_v1_payments` for why serving the flat shape at the new
    # address would be worse than refusing.
    path("v1/payments", partner_payments),
    path("v1/billing", partner_billing),
    path("v1/openapi.json", partner_openapi),
    # ── CR-110-BRC04 phase 2 · THE FIVE ARE NOT HERE ANY MORE ──────────
    # ⚠ **THEY LEFT THE TENANT INCLUDE ENTIRELY ON 2026-09-16** (`DEF-INT-5546`, PO
    # ruling of that date). They are `/api/partner/v1/…` now — no utility in the
    # path at all — and they are registered in
    # `apps/integrations/partner_urls.py`, which mounts them at `api/` and opens
    # the utility from the KEY before each view runs. **The five VIEWS are still
    # here and are unchanged**; only where they are registered moved, so a lane
    # editing a payload never has to think about it.
    #
    # Nothing is registered under `{PARTNER_PREFIX}` from inside this list, and
    # that absence is the fix: a second registration here would put the old
    # address back BESIDE the new one, every existing test would still pass, and
    # a partner could reach a utility by naming it in a URL again.
    # `test_partner_api_registers_none_of_the_five_itself` is what notices.
    # The manager's three.
    # ⚠ THREE SEGMENTS, AND THE TWO-SEGMENT SPELLING DID NOT WORK.
    # `integrations/subprocessors` collides with `api.py`'s
    # `integrations/<str:key>`, which is registered earlier and matched first —
    # so the register was read as a PROVIDER KEY and answered `405 Method Not
    # Allowed`. This lane's own comment in `config/urls.py` asserted the
    # collision could not happen; it was reasoning about the three-segment
    # routes and forgot this one. Found by clicking it, not by any check.
    path("integrations/register/subprocessors", subprocessor_register),
    path("integrations/<str:key>/access-log", access_log),
    path("integrations/<str:key>/grant", grant_authority),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-041@wave-S (EP-INT-11); OQ-INT-1481 CLOSED option (a), OQ-INT-1480 CLOSED-held
# generated: 2026-09-06 by the CR-069 wave S build lane (integrations half)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a(the guarded logic is runners/serve.py)
# gates: pytest tests/test_us_int_041_partner_surface.py · tests/test_be_default_authentication.py (the opt-out list grows by three, deliberately)
# exceptions: the partner routes opt out of the default authenticator and do their own door (runners/serve.py); the path carries the tenant and the plan said it would not — decision log 2026-09-06
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
