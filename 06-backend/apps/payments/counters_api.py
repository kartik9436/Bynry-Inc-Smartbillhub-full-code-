# ── Trace ──────────────────────────────────────────────
# Change:   CR-136-BRC07 — phase 2, the counter. `P2.1` (POST /counters),
#           `P2.2` (close · force-close · declare) and `P2.3` (the two reads).
#           Drawing: `05-prototype/06 Payments Page Blueprint.pdf` p054–p059,
#           on the DEFAULT branch and not on this one.
# Story:    no story — the six Counter screens are `S-NEW · PAY-N`.
# Rules:    CLAUDE.md hard rule 1 · hard rule 7 · BR-SHL-011 (list grammar:
#           q/sort/dir/page/per/f.<name>) · BR-SHL-025 / BR-IDN-009 (the role
#           check is the SERVICE's; this mounts it a second time) · BR-TEN-043
#           (the caller names the moment) · NFR-3 (server pagination on every
#           list) · NFR-5 (no hard caps)
# Tests:    06-backend/tests/test_cr136_p2_counters.py
# Impacts:  apps/payments/api.py's urlpatterns (one `include`) ·
#           apps/payments/counters.py (the writer and the reads; no logic here)
#           · 06-backend/openapi/schema.json (the committed contract snapshot)
# ───────────────────────────────────────────────────────
"""The counter surface — five doors onto one till.

    POST /counters                     3·3a  Start
    GET  /counters                     3·1   Counters (the supervisor's list)
    GET  /counters/{id}                3·2   My counter, with the running split
    POST /counters/{id}/close          3·3b  Close — a count
    POST /counters/{id}/force-close    3·3c  Force close — no count, a reason
    POST /counters/{id}/declare        3·3d  Declare — the count, late

**THIN BY LAW** (B8 / LAW 0): parse → call a service → serialize. There is no
ORM here, no money arithmetic and no clock; every refusal leaves this file as a
`core.errors` catalog exception (gate G9).

⚠ **THE ROLE CHECK ON `force-close` IS IN THE SERVICE AND IS MOUNTED HERE
TOO.** `counters.force_close_counter` carries `@require_role(SYSTEM_ADMIN)`, so
it refuses no matter which endpoint, job or shell forgot to gate — `BR-SHL-025`,
and the reason `counter_session_models.py` has been naming since phase 0.
`SystemAdminOnly` below is the second lock, not the only one: a wrong role is
refused twice, and removing either one leaves the other standing.

⚠ **EVERY MOMENT IS AN INPUT.** `opened_at`, `closed_at` and `declared_at` are
REQUIRED in the body and this module reads no clock (BR-TEN-043, gate G6). A
till opened at 08:55 local would otherwise be stamped with the server's day.

⚠ **AND EVERY MOMENT IS BOUNDED TO THE UTILITY'S OWN BUSINESS DAY** —
`BR-PAY-1191`, PO ruling 2026-09-23, *"(b) Backdate within the same day"*. The
four screens draw a prefilled date-and-time picker (the same ruling) and bound
it with `min`/`max`; `_refuse_a_moment_off_today` is the half that is a RULE
rather than a suggestion. The day is read through `settings_seam.tenant_now()`,
which resolves tenancy's clock by name — one clock, one zone, one place, so the
day this refuses against is the day the picker rendered in.
"""

from datetime import date, datetime
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.payments import counters
from apps.payments.exceptions import PaymentRuleError
from core import errors
from core.pagination import StandardPagination, parse_list_params
from core.permissions import AdminOrClerk, AnyTenantRole, SystemAdminOnly
from core.tenancy import require_tenant

from apps.payments.api import _actor, _moment, _payload


def _as_catalog_refusal(refusal: PaymentRuleError) -> errors.BizError:
    """A `PaymentRuleError`, as the ONE catalog exception G9 allows.

    ⚠ **`message_key` IS A LITERAL AT EVERY RAISE SITE IN THIS FILE, AND THAT
    IS `G32`'s BLIND SPOT BEING AVOIDED RATHER THAN INHERITED.** `G32` resolves
    a key only where the helper is defined in the SAME file — two modules that
    imported theirs from a sibling reported **0 unresolved** truthfully over 21
    live refusals that reach a clerk as silence. So this helper is defined here,
    the key is written out, and `test_p2_refusal_keys_resolve` asserts the
    sentence renders from `en.json` at the RAISE SITE rather than trusting the
    gate's number.

    ⚠ **TWO REFUSALS CARRY THEIR OWN KEY (`DEF-PAY-10140`)**, because the
    screen now renders the server's key and *"That counter action was
    refused."* told the PO nothing about a counter the server could not find.
    Each key is still a literal, for the reason above.
    """
    if isinstance(refusal, counters.CounterCodeUnknown):
        return errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref=getattr(refusal, "br_ref", None) or "BR-TEN-003",
            message_key="payments.counter.not_found",
            params={"detail": str(refusal)},
        )
    if isinstance(refusal, counters.CounterCodeAmbiguous):
        return errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-1160",
            message_key="payments.counter.ambiguous",
            params={"detail": str(refusal)},
        )
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-1160",
        message_key="payments.counter.refused",
        params={"detail": str(refusal)},
    )


def _required_moment(payload: dict[str, Any], name: str, *, message_key: str) -> datetime:
    """A moment the body must carry, on the utility's own business day.

    Absent is REFUSED, never defaulted to now. Present and on another day is
    refused too — see `_refuse_a_moment_off_today`.
    """
    moment = _moment(payload, name, message_key=message_key)
    if moment is None:  # pragma: no cover - `_moment` raises when the key is named
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key=message_key,
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    _refuse_a_moment_off_today(moment, name)
    return moment


def _refuse_a_moment_off_today(moment: datetime, name: str) -> None:
    """**BACKDATE WITHIN THE SAME DAY, AND NO FURTHER** (`BR-PAY-1191`).

    PO ruling 2026-09-23, verbatim: *"(b) Backdate within the same day"*. The
    worked case put to them: *Dana opens the counter at 09:00, forgets to start
    it, notices at 11:00 and sets it back to 09:00* — which is the correction
    the picker exists for. Setting it to YESTERDAY is not, because it moves a
    shift's takings into a business day that is already reported, and a future
    time is not either: this is for correcting a forgotten start, never for
    scheduling one.

    ⚠ **IT IS HERE AND NOT ONLY IN THE FORM, AND THAT IS THE POINT.** The
    screens bound their pickers with `min`/`max` from the same definition, but a
    bound a screen applies is a suggestion — `curl` is not a screen, and this is
    a money path. Server-side enforcement is THE enforcement (`BR-SHL-025`'s
    reasoning, applied to a value rather than a role).

    ⚠ **THE DAY IS THE UTILITY'S, ON THE UTILITY'S CLOCK, AND IT IS READ ONCE.**
    `settings_seam.tenant_now()` resolves `apps.tenancy.selectors.tenant_now` by
    name — the same clock `tenant_today()` and `tenant_timezone()` read, which
    is why the day this refuses against and the day the picker renders in cannot
    drift apart (`DEF-094`'s whole lesson). Gate G6 forbids a wall clock
    anywhere under `apps/payments/` (BR-TEN-043) and nothing here reads one.

    ⚠ **A NAIVE MOMENT IS ALREADY ANCHORED BY THE TIME IT ARRIVES.** `_moment`
    puts a value carrying no offset into the tenant's own zone (BR-TEN-081 /
    OQ-153), which is exactly what the Start-counter picker posts — a wall clock
    the clerk read off their own screen. Comparing before that anchoring would
    read a Houston 08:55 as a UTC one.
    """
    from apps.payments import settings_seam

    now = settings_seam.tenant_now()
    local = moment.astimezone(now.tzinfo)
    if local.date() == now.date() and local <= now:
        return
    raise errors.ValidationError(
        errors.VAL_RANGE,
        # A LITERAL key at the RAISE SITE — `G32` can only resolve one defined
        # in the same file, and reported 0 unresolved over 21 live refusals.
        # Its sentence is five words in all eleven catalogues (B14 rule 33: an
        # INSTRUCTION is six words per sentence, and RATIONALE — *why* a till
        # cannot be backdated to yesterday — is ZERO words on screen).
        message_key="payments.counter.moment_not_today",
        field_errors=[{"field": name, "code": errors.VAL_RANGE}],
    )


# ════════════════════════════════════════════════════════════════════════════
# `P2.1` · POST /counters — the session AND its batch, in one act
# ════════════════════════════════════════════════════════════════════════════
def _counters_open(request: Any) -> Response:
    """`POST /counters` — *"I am opening the counter for my shift."* (3·3a)

        service_centre_id   REQUIRED — where you are taking money
        opening_float       REQUIRED — cash in the drawer before you start
        opened_at           REQUIRED — the moment, from the caller
        currency            optional; the tenant's own when absent

    **201, and the body carries the batch**, because the whole point of the
    2026-09-21 ruling is that the batch exists before the money does — a
    response that did not name it would leave the screen unable to say so.

    A second open for the same person is **REFUSED**, not replayed: p017 says
    *"refuses a second open counter for the same user"*, and the refusal names
    the till that is already open so the screen has a door to offer.
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        opened = counters.open_counter(
            _actor(request),
            service_centre_id=payload.get("service_centre_id"),
            opening_float=payload.get("opening_float"),
            opened_at=_required_moment(
                payload, "opened_at", message_key="payments.counter.opened_at_required"
            ),
            currency=payload.get("currency"),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    body = counters.counter_detail(opened.session.pk)
    body["batch"] = {
        "id": str(opened.batch.pk),
        "code": opened.batch.code,
        "created": opened.batch_created,
    }
    return Response(body, status=201)


# ════════════════════════════════════════════════════════════════════════════
# `P2.3` · THE READS
# ════════════════════════════════════════════════════════════════════════════
def _counters_list(request: Any) -> Response:
    """`GET /counters` — 3·1, *"Whose till is open, and whose did not get counted?"*

    BR-SHL-011's grammar, and all four table controls on the SERVER:

        q            the person, or the centre
        sort         opened_at | closed_at | owner | centre     (SQL ORDER BY)
        dir          asc | desc
        page / per   50 · 100 · 200 · 500 · 1000
        f.state      open | closed | not_counted
        f.owner_id · f.centre_id
        f.mine       1 — only the AUTHENTICATED caller's tills

    ⚠ **`f.mine` IS RESOLVED SERVER-SIDE AND AN UNKNOWN `f.*` IS REFUSED HERE**
    (`DEF-PAY-6235`). Both halves are one defect. The page head asked for
    `f.mine=1` with `per: 1`; the filter did not exist, `parse_list_params`
    **ignores an undeclared filter name**, and this endpoint answered the
    SUPERVISOR's list of everyone's open tills. The slot then announced a
    colleague's drawer as *"Your counter"* beside a button that takes money —
    a read that succeeds, renders correctly in both states, and is attached to
    the wrong person. The silent drop is the ROOT CAUSE rather than a detail,
    so this endpoint refuses an `f.` name it does not serve.

    ⚠ **PAGINATED AND SORTED IN SQL. `NFR-3` AND `NFR-5` ARE THE DELIVERABLE.**
    `GET /outstandings` and `GET /cheques` are unpaginated and sort in Python,
    naming a 3,000-connection utility as the excuse — correct at T7 and 13×
    short of T5 (`DEF-PAY-4221`). This is not a fifth breach, and the count
    below is the database's `COUNT(*)`, not `len()` of a materialised list.

    `not_counted` is `counters.not_counted_q()` and nothing else — the same
    expression the chip, `P2.11`'s notice and the phase's done-when read (§3.2).
    """
    require_tenant(request)
    _refuse_an_unknown_filter(request)
    params = parse_list_params(
        request.query_params,
        allowed_sorts=counters.COUNTER_SORTS,
        default_sort=counters.DEFAULT_COUNTER_SORT,
        default_dir="desc",
        allowed_filters=counters.COUNTER_FILTERS,
    )
    paginator = StandardPagination()
    # The CALLER travels, because `f.mine` is a question about identity and
    # the identity is here. A queryset function cannot ask who is calling.
    queryset = counters.counter_list_queryset(params, actor=_actor(request))
    page = paginator.paginate_queryset(queryset, request)
    response = paginator.get_paginated_response(counters.counter_rows(page or []))
    # ⚠ **`rows`, NOT DRF's `results`, AND THE SCREEN LANE'S NAME WINS.**
    # `07-frontend/src/api/counterEndpoints.ts` declares
    # `CountersResponse { rows, count, totals }` and the six screens are built
    # against it. `results` is kept beside it rather than removed, because
    # every other list in this product answers that member and a shared client
    # reads it — one name added, none taken away.
    response.data["rows"] = response.data["results"]
    # 3·1's four tiles, folded over the WHOLE filtered set and never over the
    # page. A count that described a page is the defect `payments_totals`
    # records one module along.
    response.data["totals"] = counters.counter_list_totals(queryset, as_of=_as_of_or_none(request))
    return response


def _refuse_an_unknown_filter(request: Any) -> None:
    """An `f.<name>` this endpoint does not serve is REFUSED, never dropped.

    ⚠ **THIS IS `DEF-PAY-6235`'s ROOT CAUSE, FIXED ON ONE ENDPOINT RATHER
    THAN EVERYWHERE, AND THE NARROWNESS IS DELIBERATE.**
    `core.pagination.parse_list_params` says it in its own code — *"undeclared
    filter names are ignored"* — and that is BE-05's behaviour for **every
    list in this product**. Making it refuse globally would change the answer
    of dozens of endpoints in one commit, on the authority of one screen, so
    it is raised as its own defect rather than taken here — `DEF-PAY-6246`,
    which carries the measurement that would settle it: count how many `f.*`
    names the front end sends today that no endpoint declares. If that number
    is zero, refusing everywhere costs nothing.

    **Why it matters more than the missing filter did:** a dropped filter
    turns *"show me a narrower set"* into *"show me everything"*, and a caller
    that trusted the narrowing reads the first row as though it were theirs.
    `per: 1` then makes the wrong answer arrive faster. Every layer is
    behaving exactly as designed and the result is a clerk's name on somebody
    else's drawer.

    Refused rather than corrected: a typo'd filter is a client bug, and a
    server that guesses what was meant is how the next one hides too.
    """
    unknown = sorted(
        key[len("f.") :]
        for key in request.query_params
        if key.startswith("f.") and key[len("f.") :] not in counters.COUNTER_FILTERS
    )
    if not unknown:
        return
    raise errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref="BR-SHL-011",
        # A LITERAL key at the RAISE SITE — `G32` can only resolve one defined
        # in the same file, and reported 0 unresolved over 21 live refusals.
        #
        # ⚠ **THE EXISTING COUNTER KEY, NOT A NEW ONE, AND THAT IS A CHOICE.**
        # Every refusal in this file already renders through
        # `payments.counter.refused` with its specifics in `detail` — open,
        # close, force-close and declare all do. A new key would have to be
        # written into **eleven catalogues in eleven languages** (B14 rule 35:
        # a catalogue is written in its own language, never translated from
        # English), for a refusal only a mis-built client can ever provoke.
        # An unresolved key is `G32`'s exact defect — a refusal reaching a
        # clerk as silence — so it resolves, today, in all eleven.
        message_key="payments.counter.refused",
        params={
            "detail": (
                f"this list does not serve the filter(s) {', '.join(unknown)}. It serves "
                f"{', '.join(counters.COUNTER_FILTERS)}. Refused rather than ignored: a "
                "filter that is silently dropped turns a narrowed question into the whole "
                "list, and the caller reads the answer as though it had been narrowed."
            )
        },
    )


def _as_of_or_none(request: Any) -> Any:
    """`?as_of=YYYY-MM-DD` — the business day the tiles are read FOR.

    ⚠ **THIS MODULE READS NO CLOCK** (BR-TEN-043, gate G6 rule 3, which bans a
    wall clock anywhere under `apps/payments/`). *Taken today* and *difference
    this week* are claims about a DAY, and a server clock decides a business
    day in the SERVER's timezone — a till opened at 08:55 in Texas would be
    counted into somebody else's Tuesday. The same requirement
    `GET /outstandings` and `GET /cheques` already impose.

    Absent is LAWFUL and is not an error: the two day-shaped tiles then answer
    `null` with `as_of_missing` beside them, which a screen renders as an
    absence rather than as a wrong figure.
    """
    raw = request.query_params.get("as_of")
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.date_invalid",
            field_errors=[{"field": "as_of", "code": errors.VAL_FORMAT}],
        ) from bad


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def counter_detail(request: Any, counter_id: str) -> Response:
    """`GET /counters/{id}` — 3·2 My counter, with the running split by method.

    The split is a `GROUP BY` in the database. The reference the task names,
    `counter_receipts.list_totals`, materialises its rows and sums in Python —
    right for a screen that lists what it sums, wrong here, where a shift holds
    any number of payments and `NFR-5` forbids a cap on it.
    """
    require_tenant(request)
    try:
        return Response(counters.counter_detail(counter_id))
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal


@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])
def counters_root(request: Any) -> Response:
    """`/counters` — ONE route, two verbs, and they are not two views.

    ⚠ **DJANGO RESOLVES THE PATH FIRST AND THE METHOD SECOND**, so two `path()`
    entries with the same pattern would leave the second unreachable: the POST
    view would answer 405 for ever and every test of it would have to call the
    wrong URL to pass. One view, dispatched on the verb.

    ⚠ **THE TWO VERBS NEED DIFFERENT ROLES AND `permission_classes` IS PER
    VIEW, SO THE WRITE ROLE IS ON THE SERVICE** — which is where `BR-SHL-025`
    puts it anyway. `AnyTenantRole` lets an Executive READ the supervisor's
    list (A4: payments is VIEW for them), and
    `counters.open_counter` carries `@require_role(SYSTEM_ADMIN,
    BILLING_CLERK)`, so an Executive pressing *Start counter* is refused by the
    service with AUTH-002 no matter what any endpoint allows.
    """
    if request.method == "POST":
        return _counters_open(request)
    return _counters_list(request)


# ════════════════════════════════════════════════════════════════════════════
# `P2.2` · THREE ENDPOINTS, THREE DIFFERENT ROWS
# ════════════════════════════════════════════════════════════════════════════
@api_view(["POST"])
@permission_classes([AdminOrClerk])
def counter_close(request: Any, counter_id: str) -> Response:
    """`POST /counters/{id}/close` — 3·3b, *"does the drawer match?"*

        counted_totals   REQUIRED — {"cash": "510.00", "check": "1284.60"}
        closed_at        REQUIRED — the moment, from the caller
        note             required ONLY when the difference is not zero

    **200, not 201.** Nothing is created; the till the screen already had is
    sealed. The body is the sealed row, so the screen can show the difference
    it just recorded without a second read.
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        sealed = counters.close_counter(
            _actor(request),
            session_id=counter_id,
            counted_totals=payload.get("counted_totals"),
            closed_at=_required_moment(
                payload, "closed_at", message_key="payments.counter.closed_at_required"
            ),
            note=payload.get("note"),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(_sealed_body(sealed))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # the SECOND lock; the service holds the first
def counter_force_close(request: Any, counter_id: str) -> Response:
    """`POST /counters/{id}/force-close` — 3·3c, supervisor only.

        reason      REQUIRED — a forced close with no reason is a mistake
        closed_at   REQUIRED — the moment, from the caller

    ⚠ **`SystemAdminOnly` HERE IS NOT THE GUARANTEE.**
    `counters.force_close_counter` carries `@require_role(SYSTEM_ADMIN)` and is
    what actually enforces it (BR-SHL-025). Deleting this decorator would leave
    the rule standing; deleting the service's would not.
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        sealed = counters.force_close_counter(
            _actor(request),
            session_id=counter_id,
            # `note` is what `ForceCloseCounterBody` declares and what the
            # screen posts; `reason` is accepted beside it because it is the
            # word the drawing puts on the field (p057 ②, *"Why *"*) and a
            # script or a support call would reach for it.
            reason=payload.get("note") or payload.get("reason"),
            closed_at=_required_moment(
                payload, "closed_at", message_key="payments.counter.closed_at_required"
            ),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(_sealed_body(sealed))


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # "The person whose till it was, or a supervisor"
def counter_declare(request: Any, counter_id: str) -> Response:
    """`POST /counters/{id}/declare` — 3·3d, the count, late.

        counted_totals   REQUIRED
        declared_at      REQUIRED — the moment, from the caller
        note             required ONLY when the difference is not zero

    ⚠ **THE FORCED CLOSE STANDS.** `close_kind` does not move — PO ruling
    2026-09-23 §3.2, *"Nothing is erased"*. The row then says both: force-closed
    Monday by the supervisor, declared Tuesday by Dana, $12 short.
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        sealed = counters.declare_counter(
            _actor(request),
            session_id=counter_id,
            counted_totals=payload.get("counted_totals"),
            declared_at=_required_moment(
                payload, "declared_at", message_key="payments.counter.declared_at_required"
            ),
            note=payload.get("note"),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(_sealed_body(sealed))


def _sealed_body(sealed: Any) -> dict[str, Any]:
    """The sealed till, plus whether a journal entry was written.

    `posted` is served because `P2.22` reversed the drawing: p059 promised the
    ledger nothing happened, and a screen built from that drawing would say so
    on a shift that has just posted `$12.00` to cash over and short.
    """
    body = counters.counter_detail(sealed.session.pk)
    body["posted"] = sealed.posting_key is not None
    return body


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def counter_centres(request: Any) -> Response:
    """`GET /counters/service-centres` — the places a till can be opened at.

    ⚠ **`DEF-PAY-10768` (L1-11, 2026-10-30) — WHY THIS IS NOT THE SETTINGS
    READ.** *Start counter* read `GET /settings/reference-data/service-centres`,
    which A4's `settings_lookups` row closes to a Billing Clerk (403, and that
    matrix is signed — `SettingsReadAnyWriteSystemAdmin`). The clerk is the
    person who runs a till, so the list came back empty and *Main office*
    could never be chosen. This is the payments-owned read of the same rows:
    each centre's `slug` (what `counters._service_centre` resolves) and its
    `name`, and nothing else — no hours, actions or portal settings, which
    remain Settings' to show.

    Every centre, hidden ones too: hidden is a PORTAL state, and a depot a
    customer cannot see is still a window a clerk sits at.
    """
    from apps.tenancy import published_content_models as places

    tenant_id = require_tenant(request)
    rows = places.ServiceCentre.objects.filter(tenant_id=tenant_id).order_by("name", "slug")
    return Response({"centres": [{"slug": row.slug, "name": row.name} for row in rows]})


# ── the routes ─────────────────────────────────────────────────────────────
# `counters` is a new literal FIRST segment. Nothing in `apps.payments.api`,
# `cheques_api`, `refunds_api`, `reversal_api`, `amendments_api`,
# `writeoffs_api`, `transfer_api`, `reapply_api` or `tenders_api` declares
# one, and no `<something>` catch-all exists at
# that level in any of them — so nothing can shadow these and they can shadow
# nothing. `counter-receipts` is a DIFFERENT literal and Django resolves whole
# patterns rather than prefixes.
urlpatterns = [
    path("counters", counters_root),
    # Static, so declared above `<counter_id>` (DEF-PAY-10768).
    path("counters/service-centres", counter_centres),
    path("counters/<str:counter_id>", counter_detail),
    path("counters/<str:counter_id>/close", counter_close),
    path("counters/<str:counter_id>/force-close", counter_force_close),
    path("counters/<str:counter_id>/declare", counter_declare),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: 12-governance/change-requests/CR-136-BRC07-payments-phase-2-the-counter.md §3.1–§3.4 ·
#         12-governance/02-decision-log.md 2026-09-21 / 2026-09-22 / 2026-09-23 ·
#         05-prototype/06 Payments Page Blueprint.pdf p016–p018, p051–p059 (DEFAULT branch) ·
#         CLAUDE.md hard rules 1, 2, 4, 5, 6, 7 · hard-won laws 2, 7, 11, 12, 14 ·
#         NFR-3 · NFR-5 · BR-SHL-011 · BR-SHL-025 · BR-TEN-043
# generated: 2026-09-23 by LANE P2-API
# checklist: A✔ B=deferred(`P2.6` is the screen lane) C✔ D✔ E=deferred(same) F✔ G✔
#            H=deferred(PO 2026-08-09)
# exceptions:
#   E1 `POST /counters` and `GET /counters` share one route and dispatch on the
#      verb — see the note above the urlpatterns.
#   E2 `declare` refuses until `P2.20` lands its two columns, with a sentence
#      naming the task rather than a stack trace. The refusal is a HOLD and it
#      has the test that fires when it expires (hard-won law 2).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
