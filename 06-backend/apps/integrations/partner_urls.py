# ── Trace ──────────────────────────────────────────────
# Story:    CR-110-BRC04 phase 2 — `DEF-INT-5546`. ONE BASE URL FOR EVERY
#           PARTNER AND EVERY UTILITY. PO 2026-09-16, verbatim: *"we agreed not
#           to use utility names in partner apis that was our rule - so these
#           urls are not corect - we will resolve utility name using keys"*.
# Rules:    BR-TEN-003 (narrowed 2026-09-16: a key is proof, not a claim) ·
#           CLAUDE.md hard rule 1 (RLS FORCE does the isolating) ·
#           BR-INT-044 (the refusals are one refusal, in words AND in timing) ·
#           BR-INT-045 (the status numbers are the manifest's)
# Tests:    06-backend/tests/test_cr110_partner_tenant_from_key.py
# Impacts:  config/urls.py (mounted at `api/`, OUTSIDE the tenant include) ·
#           apps/integrations/partner_api.py (the five views; its own
#           `urlpatterns` no longer carries them) ·
#           core/tenancy.py (`partner` is a NON_TENANT_SEGMENT)
# ───────────────────────────────────────────────────────
"""The partner's addresses, with no utility in any of them — and since
2026-09-24 one of them is a WRITE.

    GET  /api/partner/v1/reference
    GET  /api/partner/v1/accounts
    GET  /api/partner/v1/consumer-info
    GET  /api/partner/v1/bills
    GET  /api/partner/v1/payments
    GET  /api/partner/v1/ledger
    GET  /api/partner/v1/bill-download/
    GET  /api/partner/v1/receipts         CR-132-BRC07 — New World's XML
    POST /api/partner/v1/make-payment/    Invoice Cloud posts us a payment
    GET  /api/partner/v1/customers        RETIRED `410` -> /partner/v1/accounts
    GET  /api/partner/v1/account-lookup   US Payments asks what is owed   } built from
    POST /api/partner/v1/add-payment      US Payments posts a payment     } the manifest's
    POST /api/partner/v1/add-return       US Payments posts a return      } `served_path`

⚠ **THE LAST THREE ARRIVED 2026-10-07 (`DEF-INT-10020`) AND THEIR KEY IS NOT A
BEARER TOKEN.** PO, verbatim: *"go - for USPayments partner API URL Fix"* — US
Payments sends no utility and no connector name in any URL, only the key we
issued, in a `password` header. So they are not typed into `PARTNER_ROUTES`:
`_published_inbound_routes` reads them off every manifest operation that
declares a `served_path` under this prefix AND is an inbound door that applies
(`Operation.applies`), mounts `inbound_api.partner_door_for` at each, and gives
the wrapper the manifest's own key reader (`inbound.presented_key`). Every
other route here still reads `Authorization: Bearer` exactly as before. The
door behind them is `inbound.receive`, unchanged — every check, every status.

⚠ **THE COUNT IS DELIBERATELY NOT WRITTEN HERE ANY MORE.** This line read
*"EIGHT since `DEF-INT-5623`"*, and `partner_api.py`'s own docstring records
what that habit costs three paragraphs from here: it said *these three* until
2026-09-17 and there were eleven, because a number in prose is a claim nothing
re-checks. **`PARTNER_ROUTES` below is the list and it is the only authority**;
`tests/test_be_default_authentication.py` asserts the served set EXACTLY.

⚠ **ONE OF THESE CREATES MONEY AND THE OTHERS DO NOT.** `make-payment` is
Invoice Cloud's door for a payment a customer made on their portal — PO
2026-09-18, *"they post to us daily"*, with the whole design confirmed
2026-09-24. It goes through the identical eight checks as every read; what
makes it a WRITE is that a key's scope has to name `record_payment`, which
only `pay_invoicecloud_partner` declares. No ERP key can reach it and no key
issued before that operation existed holds it.

⚠ **THESE WERE `/api/{utility}/partner/v1/…` UNTIL 2026-09-16 AND THAT WAS
`DEF-INT-5546`.** The lane that built the route table deviated from the
blueprint deliberately and recorded the deviation, reasoning that `BR-TEN-003`
reads the tenant from the path and that with no tenant context RLS `FORCE`
returns zero rows for the credential lookup — for a valid key as much as an
invalid one — so the door would be incapable of passing. **The first half of
that is true and the conclusion does not follow.** Blueprint p159 is titled *WHY
NOT PUT IT IN THE PATH* and answers it in order:

    key ──► connection ──► tenant ──► app.tenant_id set ──► RLS does the isolating

Resolve the key FIRST, from a table that is not a tenant table, open the utility
it names, and every one of this product's existing guarantees then applies
unchanged. The deviation was reviewed and its reasoning was never checked
against the page that answers it, which is the durable lesson in the defect row:
when a lane records a deviation from a drawing, the review question is not
whether its reasoning is sound but whether the drawing already answers it.

⚠ **WHY THE SEGMENT HAD TO GO, IN THE BLUEPRINT'S OWN WORDS.** *"A path segment
is a claim; a key is proof. If both exist, somebody must compare them on every
endpoint — that is a line of code on every handler, and the day it is missed a
partner reads another utility's bills. Deriving it means there is nothing to
check, because there is nothing that can disagree."* The utility in the URL was
not merely untidy: it was a standing invitation to set `app.tenant_id` from
something a caller typed, which is the one thing `BR-TEN-003` exists to prevent.

⚠ **THE DOOR IS OPENED IN ONE PLACE AND EVERY ROUTE GOES THROUGH IT.** The nine
checks are `partner_api._admit`'s and are untouched by this file; all this layer
adds is the first arrow of the diagram, and it adds it to every one of the five
by construction — there is no route here that can be registered without it,
because `_with_utility_from_key` is applied in the list below and a bare view
would have no way to reach a tenant table at all.

⚠ **THE PHASE-1 PAIR IS NOT HERE AND HAS NOT MOVED.** `/api/{utility}/v1/payments`
and `/v1/billing` still serve the flat `US-INT-041` payload from inside the
tenant include, and `partner_api.py` still owns them. They are a different
address with a different payload shape and they retire on their own schedule;
moving them in the same commit would have made one change look like two.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from django.core.exceptions import ImproperlyConfigured
from django.urls import path

from apps.integrations import inbound, inbound_api, key_directory
from apps.integrations.registry import REGISTRY
from apps.integrations.partner_api import (
    PARTNER_PREFIX,
    _presented_key,
    partner_accounts,
    partner_bill_download,
    partner_bills,
    partner_consumer_info,
    partner_customers_retired,
    partner_ledger,
    partner_make_payment,
    partner_receipts,
    partner_reference,
    partner_v1_payments,
)


def _with_utility_from_key(view: Callable, key_of: Callable[[Any], str | None] = _presented_key) -> Callable:
    """The first arrow: open the utility this key names, then run the view.

    ⚠ **IT RESOLVES AND IT NEVER REFUSES.** A key we do not recognise leaves the
    request with no utility open, and the view's own door then refuses it in the
    ordinary way — one sentence, one code, one status, padded to
    `serve.REFUSAL_FLOOR_S`. A refusal raised HERE would be a faster one, and a
    faster refusal on this surface tells a caller holding a stolen key that the
    key is at least real (`BR-INT-044`). `key_directory.open_utility_for` spends
    the same two statements either way for the same reason.

    ⚠ **IT WRAPS THE ALREADY-DECORATED VIEW, WHICH IS THE ONLY ORDER THAT
    WORKS.** `partner_reference` and its four siblings are `@api_view`-wrapped
    functions, so the wrapper below runs before DRF dispatches — and therefore
    before anything the view does can touch a tenant table. Applied the other way
    round the context would be opened after the first query that needed it.

    ⚠ **`key_of` IS WHERE THE KEY IS READ, AND IT IS DECLARED PER ROUTE, NEVER
    BRANCHED ON (`DEF-INT-10020`).** Every route in `PARTNER_ROUTES` keeps the
    default, `partner_api._presented_key` — `Authorization: Bearer …`, exactly
    as before. A route built from a manifest's published inbound operation
    (`_published_inbound_routes` below) reads the header THAT MANIFEST declares
    through `inbound.presented_key` — US Payments' `password`, value as given,
    no `Bearer`. The same reader the door itself then authenticates with, so
    the key that opened the utility is the key that is checked under it.
    """

    @wraps(view)
    def door(request: Any, *args: Any, **kwargs: Any) -> Any:
        key_directory.open_utility_for(request, key_of(request))
        return view(request, *args, **kwargs)

    return door


#: `{the address: its view}` — EIGHT since `DEF-INT-5623`.
#:
#: ⚠ **EVERY ONE IS REGISTERED TWICE, WITH AND WITHOUT A TRAILING SLASH
#: (`CR-111-BRC04`).** Invoice Cloud's document writes `/bill-download/` with a
#: slash and the other addresses without one, which is an ordinary thing for a
#: vendor's document to do and is not worth a support call either way.
#:
#: **Django's `APPEND_SLASH` does not solve this and would have made it worse.**
#: It answers a `301` to the slashed form, and a partner's HTTP client that does
#: not follow redirects sees a `301` with no body where it expected a document;
#: one that DOES follow it may drop the `Authorization` header on the hop, which
#: turns a working call into our own five-word refusal and sends their engineer
#: to look at the key. Registering both spellings makes both addresses real, so
#: neither is a redirect and both carry the bearer token they arrived with.
#:
#: ⚠ **IT IS NOT A THIRD SPELLING** — no `.json` suffix, no upper case, no
#: version alias. Two forms of one path, because a trailing slash is punctuation
#: rather than a name (`DEF-014` is about two NAMES for one value).
PARTNER_ROUTES = {
    "reference": partner_reference,
    # ── `DEF-INT-5623` — `customers` BECAME `accounts` ON 2026-09-17 ───────
    # PO, on the live deployment: *"it should be account and not customer -
    # theya re lookung for details for accounts not customer id"*. Every value
    # this address has ever served was the account's (PO 2026-09-16,
    # *"Customers = accounts"*); only the name was wrong, so nothing could go
    # red.
    #
    # ⚠ **THE OLD SPELLING IS STILL REGISTERED AND ANSWERS `410`, NAMING THIS
    # ONE.** It is not a second spelling of a live address — `bill-download`
    # with and without a slash is that, and this is not: nothing is served
    # here. On this surface a missing route and a stolen key are the same
    # `404` (`BR-INT-044`), so simply deleting the address would have told a
    # partner holding yesterday's document that their KEY was bad and sent
    # their engineer to look at their credentials. Five `live` manifests share
    # this one route table.
    "accounts": partner_accounts,
    "customers": partner_customers_retired,
    "bills": partner_bills,
    "payments": partner_v1_payments,
    "ledger": partner_ledger,
    # ── `CR-111-BRC04` ─────────────────────────────────────────
    # ⚠ **`consumer-info` IS A SECOND ADDRESS ONTO THE CUSTOMERS DOOR** — same
    # operation, same tick on the set-up screen, same rate window, same seam,
    # same composer. See `partner_api.partner_consumer_info`.
    "consumer-info": partner_consumer_info,
    "bill-download": partner_bill_download,
    # ── `CR-132-BRC07` — NEW WORLD / LOGOS ────────────────────────────────
    # ⚠ **IT GETS THE FIRST ARROW BY BEING IN THIS DICT, WHICH IS THE WHOLE
    # POINT OF THE LOOP BELOW.** key ─► connection ─► tenant ─► `app.tenant_id`
    # ─► RLS. A ninth view registered by hand beside this list would have no
    # tenant context and would read ZERO rows for a VALID key — which looks
    # exactly like a bad key and would be debugged as one.
    #
    # The address is `receipts` and not `newworld`: **one base URL for every
    # partner**, no vendor in any path (PO 2026-09-16, *"why aclarian in it -
    # we cna make it generic"*). New World is a KEY, not a path — and the
    # manifest's own operation switch is what opens this door for them.
    "receipts": partner_receipts,
    # ── 2026-09-24 · THE FIRST WRITE ON THIS DOOR ─────────────────────────
    # ⚠ **A `POST` IN A DICT OF `GET`s, AND IT NEEDS THE FIRST ARROW MORE THAN
    # ANY OF THEM.** key ─► credential ─► connection ─► tenant ─► `app.tenant_id`
    # ─► RLS. Registered by hand beside this list it would have no tenant
    # context, read zero rows for a VALID key, look exactly like a bad key —
    # and, being a WRITE, the one thing worse than that is the version where it
    # does not: a payment landing under no tenant, or the wrong one, is
    # somebody else's money in somebody else's book (`inbound_api.py`'s own
    # docstring makes the same point about its door).
    #
    # The loop below gives it both spellings, and the slashed one is the
    # address their document writes.
    "make-payment": partner_make_payment,
}

def _manifest_key_reader(manifest: Any) -> Callable[[Any], str | None]:
    """The key, read from the header `manifest` declares (`BR-INT-037`).

    A manifest that declares no readable header fails CLOSED to `None` — no
    utility opens and the door refuses in the ordinary way — rather than
    falling back to a guess at which header carries a key.
    """

    def read(request: Any) -> str | None:
        try:
            return inbound.presented_key(manifest, request.META)
        except inbound.DoorMisconfigured:
            return None

    return read


def _published_inbound_routes() -> list[tuple[str, Callable, Callable[[Any], str | None]]]:
    """`DEF-INT-10020` — `(name, view, key reader)` for every inbound operation
    a manifest PUBLISHES on this surface, read off the registry.

    PO ruling 2026-10-07: US Payments is served at
    `/api/partner/v1/account-lookup`, `/add-payment` and `/add-return`, with the
    utility from the key in its `password` header. Those three addresses are
    declared on `manifests/pay_uspayments.py` as each operation's
    `served_path`, and this builds them — **no provider key is named in this
    file** (`G77`): an operation qualifies because it is THEIR call that our
    door APPLIES (`applies`) and it declares an address under this prefix.
    The generic kiosk declares none and so is not here; it stays at its
    per-utility address.

    ⚠ **A NAME THAT COLLIDES WITH A ROUTE ALREADY ON THIS SURFACE STOPS THE
    PROCESS AT IMPORT.** Two views behind one address would let whichever was
    registered first answer the other's partner — with the other's key
    reader — and nothing would go red.
    """
    prefix = f"/{PARTNER_PREFIX}/"
    built: list[tuple[str, Callable, Callable[[Any], str | None]]] = []
    seen: set[str] = set(PARTNER_ROUTES)
    for manifest in REGISTRY.all():
        for operation in manifest.operations:
            served = operation.served_path or ""
            if operation.applies is None or not served.startswith(prefix):
                continue
            name = served[len(prefix) :].strip("/")
            if not name or "/" in name or name in seen:
                raise ImproperlyConfigured(
                    f"{manifest.key} · {operation.name} publishes {served!r}, which is "
                    "empty, nested or already an address on the partner surface "
                    "(DEF-INT-10020)."
                )
            seen.add(name)
            built.append(
                (
                    name,
                    inbound_api.partner_door_for(manifest.key, operation.name, served),
                    _manifest_key_reader(manifest),
                )
            )
    return built


#: `DEF-INT-10020` — built once, when the URL table is first imported (after
#: `apps.py` has registered every manifest).
PUBLISHED_INBOUND_ROUTES = _published_inbound_routes()

urlpatterns = [
    # ⚠ NO `{utility}` IN ANY OF THESE, AND THAT IS THE POINT OF THE FILE.
    # `core.tenancy.NON_TENANT_SEGMENTS` carries `partner` so the middleware
    # reads no slug here, and `RESERVED_SUBDOMAINS` carries it so no utility can
    # ever be named `partner` and be shadowed by this mount.
    #
    # ⚠ **`_with_utility_from_key` IS APPLIED BY THE LOOP, WHICH IS WHY IT
    # CANNOT BE FORGOTTEN.** A route added to `PARTNER_ROUTES` gets the first
    # arrow — key ─► connection ─► tenant ─► `app.tenant_id` ─► RLS — by
    # construction. A view registered by hand beside this list would have no
    # tenant context at all and would read zero rows for a VALID key, which
    # looks exactly like a bad key and would be debugged as one.
    route
    for name, view, key_of in (
        *((name, view, _presented_key) for name, view in PARTNER_ROUTES.items()),
        *PUBLISHED_INBOUND_ROUTES,
    )
    for route in (
        path(f"{PARTNER_PREFIX}/{name}", _with_utility_from_key(view, key_of)),
        path(f"{PARTNER_PREFIX}/{name}/", _with_utility_from_key(view, key_of)),
    )
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-110-BRC04 phase 2 (DEF-INT-5546)
# generated: 2026-09-16 by the DEF-INT-5546 lane
# checklist: A✔ B=n/a(no screen) C✔ D✔ E=n/a F✔ G✔ H=n/a(the guarded logic is runners/serve.py)
# gates: pytest tests/test_cr110_partner_tenant_from_key.py · tests/test_us_int_041_partner_surface.py · tests/test_be_default_authentication.py
# exceptions: mounted OUTSIDE the tenant include — the utility comes from the key, per PO ruling 2026-09-16 and BR-TEN-003 as narrowed the same day
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
