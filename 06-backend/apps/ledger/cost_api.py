# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-018 (capture a supplier invoice — S73's Capture modal) ·
#           US-LED-019 (the register: list · search · filter · edit · void —
#           and TC-8's after-close correction, RULED 2026-08-16) ·
#           US-LED-020 (bought vs billed — S74) ·
#           US-LED-021 (the cost section the export already carries — this file
#           serves the DRIFT warning its after-close correction creates)
#           Screens: S73 · S74 · S42
# Rules:    BR-LED-028 (capture, hold, reconcile, export — and process NOTHING) ·
#           BR-LED-029 (what a captured invoice holds) · BR-LED-030 (the volume
#           is OPTIONAL) · BR-LED-031 (the unaccounted-for figure is
#           ALL-OR-NOTHING per service per period) · BR-LED-032 (the volume
#           ratio) · BR-LED-033 (a volume carries its explicit unit) ·
#           BR-LED-034 (editable while the period is OPEN; after close with a
#           REASON — OQ-203, PO 2026-08-16) · BR-LED-035 (void, never delete) ·
#           BR-LED-036 (every capture, edit and void audits) · BR-LED-004 (the
#           export batch is idempotent, which is why the drift warning exists) ·
#           BR-REP-001 (every figure labels its basis) · BR-REP-006 (pickers
#           enumerate the LIVE vocabulary) · BR-SHL-011 (list grammar q /
#           f.<name>) · BR-TEN-043 (event time is an INPUT — no clock here) ·
#           BR-TEN-042 (the currency travels beside every amount) ·
#           BR-IDN-009 (RBAC is server-enforced) · BR-TEN-003 / HR-1 (a
#           cross-tenant id reads as absent) · CLAUDE.md rule 1 · rule 2 ·
#           rule 3 · rule 7
# Tests:    06-backend/tests/test_us_led_018_cost_api.py
# Impacts:  config/urls.py inclusion (`urlpatterns` exported here) ·
#           07-frontend/src/features/ledger/CostOfServicePage.tsx (S73/S74, the
#           first and only caller) · .../CloseExportPage.tsx (S42 renders the
#           drift warning served on `finance/export/preview`'s sibling here) ·
#           06-backend/openapi/schema.json (BE-11 TC05 diffs the snapshot)
# ───────────────────────────────────────────────────────
"""The payable side as HTTP — capture, register, correct, reconcile.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — every route below writes or reads money
rows and decides which accounting period they land in. AI-authored 2026-08-16
under the PO ruling of 2026-08-09; the ledger rows in
12-governance/09-human-review-ledger.md are the Product Owner's to write and are
NAMED in the lane report rather than opened on their behalf.

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS — 1,700 TESTED LINES AND NO DOOR
════════════════════════════════════════════════════════════════════════════
`apps/ledger/cost_capture.py` (1,187 lines) and `apps/ledger/cost_reconciliation
.py` (500) shipped on 2026-08-15 complete, LE-11/LE-12/LE-13-verified and
G7-guarded, carrying `D=deferred(no-API-half — S73's endpoints wait on OQ-204)`
in their own trailers. So a utility could capture nothing, see no register, and
never learn what fraction of the water it bought it failed to bill — the one
figure the PO said the accounting package cannot produce and this product can.
Hard-won law 2, for the fifth time in this module.

**Why the deferral is no longer right.** It named OQ-204, which asks (a) whether
S73/S74 are ratified into A1 and (b) whether the reconciliation is a Finance
sub-view or a report beside S59/S60. Neither half blocks the CAPTURE, the
REGISTER, the CORRECTION or the COMPUTATION — the registry row itself scopes
OQ-204 to *"Navigation and the download contract only"*. What is genuinely
blocked is served as blocked: see the two refusals below.

════════════════════════════════════════════════════════════════════════════
THE TWO OPEN QUESTIONS THIS FILE REFUSES BY NAME RATHER THAN ANSWERING
════════════════════════════════════════════════════════════════════════════
**OQ-204 — the DOWNLOAD.** The S74 capability row promises *"CSV + PDF per
IS-11 (basis labeled, filters echoed)"*, and IS-11's download pipeline is the
REPORTS module's (S44 catalog · S46 viewer). Whether this reconciliation is a
Finance sub-view or a report beside S59/S60 decides which pipeline it registers
with and under which key — so `GET …/reconciliation/download` raises
`NotImplementedError("OQ-204")`, and the screen renders its Download control
DISABLED with that reason (BR-SHL-025: a forbidden control renders disabled WITH
its reason, never absent). The S73 register's CSV rides the platform
`POST /api/exports` and is unaffected.

**OQ-201 — the PURCHASE UNIT VOCABULARY.** Gas bought in **MMBtu** against gas
billed in **ccf** produces NO figure, by name, rather than a ratio of two
different quantities (BR-LED-033). That suppression is already built in
`cost_reconciliation`; what is NOT built and must not be invented is a
conversion factor. `volume_unit` is therefore accepted as FREE TEXT that must
match the billed unit exactly, and the capture form offers no unit picker — a
picker would be a vocabulary, and the vocabulary is the question.

════════════════════════════════════════════════════════════════════════════
THIS FILE COMPUTES NOTHING AND POSTS NOTHING
════════════════════════════════════════════════════════════════════════════
No arithmetic, no ORM (G6 greps every `*_api.py` for a model manager), and — the
one that matters for this capability — **no journal write of any kind**. A
capture posts NOTHING to the books in R2 (OQ-200, PO 2026-08-16: *"(b) for R2,
(a) once supplier payments exist"*), and every capture response says so in a
sentence the screen prints. **Any surface implying the books moved is a
defect**, which is why the sentence is served rather than left to a screen to
compose.
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.ledger import chart, cost_capture, cost_reconciliation, exports
from apps.ledger import billing_seam, dimension_seam
from apps.tenancy import selectors as tenancy_selectors
from core import errors
from core.permissions import AdminOrClerk, AnyTenantRole
from core.tenancy import require_tenant

#: The five actions BR-LED-028 forbids, published on the register read so the
#: SCREEN can state them as rule rather than leaving five empty spaces where a
#: clerk expects buttons. `cost_capture.FORBIDDEN_ACTIONS` is the one list.
FORBIDDEN_ACTIONS = cost_capture.FORBIDDEN_ACTIONS


def _sort_key(sort: Any, direction: Any) -> str:
    """`?sort=amount&dir=desc` → `"-amount"`, the register's own grammar.

    The register has always taken ONE signed string. Every other list in the
    product — and `serializeTableParams`, which every screen built on the shared
    table uses — writes a COLUMN and a DIRECTION. Rather than give this one
    screen a second grammar (`DEF-LED-6710` is a defect about exactly that kind
    of divergence), both are accepted here and the signed form is what the
    service sees. A signed `sort` with no `dir` is passed through untouched, so
    every link written before 2026-09-25 still means what it meant.
    """
    key = str(sort or "").strip()
    if key == "":
        return cost_capture.DEFAULT_SORT
    if key.startswith("-"):
        return key
    return f"-{key}" if str(direction or "").strip().lower() == "desc" else key


def _page_number(raw: Any) -> int:
    """`?page` as an int, never an error — `BR-SHL-011` clamps.

    A non-numeric page is read as page one rather than refused: a clerk never
    types this parameter, so a 400 here can only ever be a link that went stale.
    The LAST-page clamp is the service's, because only it has counted.
    """
    try:
        return max(1, int(str(raw).strip()))
    except (TypeError, ValueError):
        return 1


def _page_size(raw: Any) -> int:
    """`?page_size` as an int, clamped by the service to `MAX_PAGE_SIZE`."""
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return cost_capture.DEFAULT_PAGE_SIZE


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="ledger.payload_not_object")
    return data


def _actor(request: Any) -> Any:
    """WHO captured or corrected, from the SESSION — never from the body.

    `audit_log.actor_user_id` is hard rule 7's evidence half (BR-LED-036 makes
    every capture, edit and void audited), so the one thing it must not be is
    client input.
    """
    return getattr(request, "user", None)


def _date_value(raw: Any, field: str) -> date:
    """One ISO calendar date, or a refusal naming the field.

    `date.fromisoformat` and nothing looser: the invoice date decides which
    accounting period a purchase lands in (BR-LED-034), and a date parsed by
    guessing would put one invoice in two different months in two regions.
    """
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.report.date_invalid",
            field_errors=[{"field": field, "code": errors.VAL_FORMAT}],
        ) from problem


def _window(params: Any) -> tuple[date, date]:
    """`from` + `to`, both REQUIRED. A reconciliation is always *for a period*."""
    raw_start, raw_end = params.get("from"), params.get("to")
    for field, raw in (("from", raw_start), ("to", raw_end)):
        if raw is None or str(raw).strip() == "":
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="ledger.report.period_required",
                field_errors=[{"field": field, "code": errors.VAL_REQUIRED}],
            )
    start, end = _date_value(raw_start, "from"), _date_value(raw_end, "to")
    if start > end:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="ledger.report.range_inverted",
            params={"from": start.isoformat(), "to": end.isoformat()},
            field_errors=[
                {"field": "from", "code": errors.VAL_RANGE},
                {"field": "to", "code": errors.VAL_RANGE},
            ],
        )
    return start, end


def _moment(payload: dict[str, Any], name: str, *, message_key: str) -> datetime:
    """A caller-supplied instant — BR-TEN-043. There is no clock in this file.

    A double-submitted Void must stamp ONE moment; a server reading its own
    clock would stamp two and record two different histories of one act.
    """
    raw = payload.get(name)
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key=message_key,
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    text = str(raw).strip()
    try:
        moment = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        try:
            moment = datetime.combine(date.fromisoformat(text), datetime.min.time())
        except (TypeError, ValueError) as problem:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="ledger.report.date_invalid",
                field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
            ) from problem
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt_timezone.utc)
    return moment


def _decimal(raw: Any, field: str) -> Decimal:
    """A money or volume figure, as a DECIMAL, from a STRING.

    ⚠ **A float never reaches `Decimal` here.** `Decimal(0.1)` is
    0.1000000000000000055511151231257827…, and CLAUDE.md rule 2 forbids float
    money for exactly that reason. A JSON number arriving as a Python float is
    routed through `repr` — which round-trips the literal the client typed —
    and the service's own `_clean_amount` performs the real validation.
    """
    if isinstance(raw, Decimal):
        return raw
    text = repr(raw) if isinstance(raw, float) else str(raw).strip()
    try:
        return Decimal(text)
    except (InvalidOperation, TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.cost.amount_invalid",
            field_errors=[{"field": field, "code": errors.VAL_FORMAT}],
        ) from problem


def _refused(problem: cost_capture.CostCaptureError) -> errors.ApiError:
    """One prose refusal → one catalog code, classified on what it MEANS.

    `CostCaptureError` is prose by design: the refusals are long because they
    quote the rule that forbids the act, which is how a later lane reads
    BR-LED-028 as law rather than as an unbuilt feature. B12 §3 still needs a
    code, so the classification happens once, here, on the `br_ref` the service
    attached — never by matching on message text, which would break the first
    time a sentence was reworded.
    """
    ref = getattr(problem, "br_ref", None) or "BR-LED-028"
    code = {
        # "Approve / schedule / pay this" — there is no such state and never
        # will be. BIZ_STATE, because the state does not exist.
        "BR-LED-028": errors.BIZ_STATE,
        # A void is the only disposition; a delete has no path at any layer.
        "BR-LED-035": errors.BIZ_IMMUTABLE,
        # The after-close correction with no reason, and the closed-period
        # dating rules.
        "BR-LED-034": errors.BIZ_WINDOW,
        # A missing supplier, a bad currency, a volume with no unit.
        "BR-LED-029": errors.BIZ_COMPLETENESS,
        "BR-LED-033": errors.BIZ_COMPLETENESS,
        # ⚠ CR-060 C1 / T6 (2026-09-02) — the settlement's own refusals.
        # Clearing or moving a paid-on date whose entry is already POSTED is an
        # IMMUTABLE refusal and not a window one: the window is irrelevant, the
        # journal entry is what cannot move (hard rule 4).
        "BR-LED-034 · CR-060 C1": errors.BIZ_IMMUTABLE,
        # The ledger refused the posting — an amount carrying three decimals
        # (BR-LED-025), or a cost account the tenant has deactivated. The
        # ledger's own sentence rides on `detail`.
        "BR-LED-025": errors.BIZ_STATE,
        # No account carries the `cash` designation, so there is nowhere to
        # credit. A completeness gap in the tenant's own chart, fixed on the GL
        # mapping page — not a state this invoice is in.
        "BR-LED-037": errors.BIZ_COMPLETENESS,
        # A cross-tenant or unknown id never reaches here — see `_not_found`.
        "BR-TEN-003": errors.BIZ_STATE,
    }.get(ref, errors.BIZ_STATE)
    return errors.BizError(
        code, br_ref=ref, message_key="ledger.cost.refused", params={"detail": str(problem)}
    )


def _guard(problem: cost_capture.CostCaptureError) -> errors.ApiError:
    """A refusal about an id becomes a **404**, never a 403 (HR-1).

    `cost_capture._get_or_refuse` is tenant-scoped by construction, so a foreign
    invoice id and a missing one raise the same error — and they must answer the
    same, byte for byte. Confirming that a row exists somewhere is itself a leak.
    """
    if getattr(problem, "br_ref", None) == "BR-TEN-003":
        return errors.deny_as_not_found("BR-TEN-003")
    return _refused(problem)


def _money(value: Any) -> str | None:
    """Money and volumes on the wire as STRINGS, never as JSON numbers.

    OQ-186 rules that the API serves the stored scale and the SCREEN rounds to
    two. A JSON number would hand the browser a float and lose the sixth decimal
    on the way — the same defect rule 2 forbids in a column, one layer out.
    """
    return None if value is None else str(value)


def _row(row: dict[str, Any]) -> dict[str, Any]:
    """One S73 register row on the wire, dates and decimals serialised."""
    out = dict(row)
    for key in ("amount", "volume"):
        out[key] = _money(out.get(key))
    # `paid_on` joins the date list rather than the money list — CR-060 C1 / T6.
    for key in ("invoice_date", "captured_at", "voided_at", "paid_on"):
        value = out.get(key)
        out[key] = value.isoformat() if hasattr(value, "isoformat") else value
    return out


# ═══════════════════════════════════════════════════════════════════════════
# GET / POST /finance/cost-of-service — S73's register and its Capture modal
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])  # the WRITE re-gates below; A4 gives every role R
def cost_of_service(request: Any) -> Response:
    """The captured-cost register (US-LED-019) and a capture (US-LED-018).

    **GET** serves ONE PAGE of the filtered set, with a footer and counts that
    are still the WHOLE filtered set. `?page` and `?page_size` are the grammar
    every other list in the product uses.

    ⚠ **THIS ENDPOINT WAS UNPAGINATED UNTIL 2026-09-25 (`DEF-LED-6710`)** and
    said so in this docstring, on the old 3,000-connection ceiling's reasoning.
    `NFR-3` makes server pagination universal and load-bearing; the Finance
    blueprint p062 already listed *"no pager"* against this screen and named
    `NFR-3` as the rule it breaks. The footer did not have to move to get one —
    see `cost_capture.register`, where it is a SQL aggregate over the filtered
    set and never over the rows served.

    **POST** captures one supplier invoice. The response carries `posting`, a
    sentence stating that the books did not move and why, because OQ-200's
    closure text is explicit that *"any screen implying otherwise is a defect"*.

    Query grammar is BR-SHL-011's: `q` for the free-text search (supplier,
    reference, memo — at least two characters, IS-3) and `f.<name>` for the
    filters, including `f.volume_captured=no`, the filter that decides whether
    an unaccounted-for percentage can be produced at all.
    """
    require_tenant(request)
    if request.method == "POST":
        # A4 gives Executive full read on Finance; a capture is a System Admin /
        # Billing Clerk act (US-LED-018 TC-9). The service's own `@require_role`
        # is still the enforcement — this is the router-level half so a
        # forbidden request never reaches the write path at all.
        if not AdminOrClerk().has_permission(request, None):
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-LED-003")
        body = _payload(request)
        volume = body.get("volume")
        try:
            captured = cost_capture.capture_supplier_invoice(
                _actor(request),
                invoice_date=_date_value(body.get("invoice_date"), "invoice_date"),
                service=body.get("service"),
                supplier_name=body.get("supplier_name"),
                amount=_decimal(body.get("amount"), "amount"),
                currency=body.get("currency"),
                # BR-LED-030: the volume is OPTIONAL, and `None` is the ruled
                # value rather than a missing one. `""` from an untouched form
                # field means the same thing and must not become `Decimal("")`.
                volume=(
                    None
                    if volume is None or str(volume).strip() == ""
                    else _decimal(volume, "volume")
                ),
                volume_unit=body.get("volume_unit"),
                ledger_account_id=body.get("ledger_account_id"),
                # CR-060 C3 / task T4 — OPTIONAL, and `""` from an untouched
                # picker means the same thing as absent. The service refuses a
                # building that is not this tenant's; it never silently drops
                # one (CLAUDE.md rule 1).
                premises_id=body.get("premises_id"),
                reference=body.get("reference"),
                memo=body.get("memo"),
            )
        except cost_capture.CostCaptureError as problem:
            raise _refused(problem) from problem
        return Response(
            {
                **_row(captured),
                "problems": list(captured.get("problems") or ()),
                "period_auto_forwarded": captured.get("period_auto_forwarded"),
                "posting": captured["posting"],
            },
            status=201,
        )

    params = request.query_params
    raw_volume = params.get("f.volume_captured")
    volume_captured = (
        None
        if raw_volume is None or str(raw_volume).strip() == ""
        else str(raw_volume).strip().lower() in {"1", "true", "yes"}
    )
    period_from, period_to = params.get("f.from"), params.get("f.to")
    try:
        result = cost_capture.register(
            period_start=_date_value(period_from, "f.from") if period_from else None,
            period_end=_date_value(period_to, "f.to") if period_to else None,
            service=params.get("f.service") or None,
            status=params.get("f.status") or None,
            volume_captured=volume_captured,
            gl_account_id=params.get("f.gl_account_id") or None,
            q=params.get("q") or None,
            sort=_sort_key(params.get("sort"), params.get("dir")),
            # `NFR-3` — `DEF-LED-6710`. Both are CLAMPED by the service rather
            # than validated here: `BR-SHL-011` says a list clamps and never
            # errors, so `?page=999` on a three-page register serves page three.
            page=_page_number(params.get("page")),
            # `per` is the product's own grammar for a page size (`BR-SHL-011`,
            # and what `serializeTableParams` writes); `page_size` is accepted
            # beside it so a link written against the wire name still works.
            page_size=_page_size(params.get("per") or params.get("page_size")),
        )
    except cost_capture.CostCaptureError as problem:
        raise _refused(problem) from problem

    return Response(
        {
            "rows": [_row(row) for row in result["rows"]],
            "total_amount": _money(result["total_amount"]),
            "currency": result.get("currency") or tenancy_selectors.regional_settings().get(
                "currency"
            ),
            "count": result["count"],
            # The pager's contract. `total` is the WHOLE FILTERED SET, so the
            # footer above and the pager here describe the same set and cannot
            # disagree — which is the thing an unpaginated read was defended on.
            "page": result["page"],
            "sort": result["sort"],
            # S73's bulk-actions cell is EMPTY BY RULE: a bulk action over
            # captured payables is a payment run or an approval queue
            # (BR-LED-028). ⚠ `bulk_actions_reason` rode beside it until
            # 2026-09-25 and is DELETED (`DEF-LED-6642`) — the screen printed
            # the rule id and 38 words of our reasoning to a clerk, and B14
            # rule 33 puts rationale at zero words on screen. The empty list is
            # the whole statement.
            "bulk_actions": list(result["bulk_actions"]),
            "categories": list(cost_capture.cost_category_vocabulary()),
            # ⚠ CR-060 C3 / task T4 — the S73 capture form's BUILDING picker,
            # served beside the category vocabulary and for the same reason: a
            # screen holding its own copy of another module's list is a second
            # vocabulary to keep in step (B14 rule 31 also forbids the screen
            # showing the id, so it needs the LABEL from somewhere). The list
            # itself is metering's and is tenant-scoped at source.
            "premises_options": [
                dict(option) for option in dimension_seam.premises_options()
            ],
            # ⚠ CR-060 C15 · task T5 — SERVED BESIDE the flat list, never
            # instead of it. The flat `categories` key is the existing contract
            # and every current caller reads it; this carries the grouping, the
            # labels and the recovery flag a widened picker needs, so a screen
            # does not have to hold a copy of the vocabulary to group it.
            "category_catalog": [dict(row) for row in cost_capture.cost_category_catalog()],
            # ⚠ The capital names this tab REFUSES, each with the sentence that
            # says where the money goes instead. Published rather than merely
            # enforced: a refusal a clerk only meets after typing a whole
            # invoice has taught them nothing, and a missing option reads as a
            # feature nobody thought of (BR-LED-028's posture, applied to C15).
            "refused_categories": [
                dict(row) for row in cost_capture.refused_category_catalog()
            ],
            "forbidden_actions": list(FORBIDDEN_ACTIONS),
            # US-LED-017 TC-5: no surface may present an unsigned code as
            # signed, so the register of unsigned codes is SERVED rather than
            # hardcoded by a screen. ⚠ AMENDED 2026-08-18: it named "the eight
            # PROPOSED cost codes"; the PO finance re-signed all eight that day
            # (codes and names, no figure attached), so this comes back EMPTY —
            # and it is still published, because an absent key and an empty one
            # say different things to the screen reading them.
            "pending_finance_re_sign_cost": list(chart.PENDING_FINANCE_RE_SIGN_COST),
            "cost_section_source": chart.COST_SECTION_RE_SIGN_SOURCE,
            # OQ-200, ruled: a CAPTURE posts nothing, and that is unchanged.
            # ⚠ AMENDED 2026-09-02 (CR-060 C1 / T6) — `expires_when` is GONE and
            # `settlement` replaces it. The old key named a condition that never
            # fired and cannot: it said the ruling would flip *"the day a
            # supplier-payment path ships"*, and BR-LED-028 still forbids one.
            # What actually happened is that the PO ruled a cost posts DR cost /
            # CR cash when a clerk RECORDS it was settled. Served as a sentence
            # so the screen prints the ledger's words rather than composing one
            # that drifts from them.
            "posting": {
                "posted": False,
                "reason": cost_capture.POSTING_RULED_NONE,
                "settlement": cost_capture.SETTLEMENT_RULING,
            },
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# PATCH /finance/cost-of-service/{id} — the edit, open period or corrected
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["PATCH"])
@permission_classes([AdminOrClerk])
def cost_of_service_item(request: Any, invoice_id: str) -> Response:
    """US-LED-019's edit — OQ-203's after-close correction — and, since
    2026-09-02, **the route that records a settlement and moves the books**.

    ⚠ **A BODY CARRYING `paid_on` GOES TO `_record_settlement` AND NOWHERE
    ELSE** (CR-060 C1 / task T6, PO ruling 2026-09-02: *"why cant to add the
    check that whether this is paid or unpaid and allow clark to udpaet it"*).
    Setting the date posts `DR cost / CR cash` through the one posting service;
    clearing it is lawful while nothing has posted and refused once it has.
    Everything below this line is the ordinary edit of a captured fact, which
    posts nothing and never has.

    While the period is OPEN this is BR-LED-034's ordinary edit. After it has
    CLOSED the edit is still lawful (PO 2026-08-16: *"Yes it can be
    corrected"*) and `correction_reason` becomes REQUIRED; the response then
    carries `after_close`, naming every export batch whose window contains this
    purchase. Those batches no longer match the register and the difference has
    to be posted by hand at the accounting system's end, because the export is
    idempotent and cannot be re-run (BR-LED-004).

    **Re-dating a closed-period purchase is refused by name** — moving it is not
    correcting it. ⚠ **OQ-227 CLOSED 2026-08-16** and this sentence used to end
    *"the two available behaviours each move a different month's
    reconciliation"*, i.e. it described an OPEN question. The PO ruled, on the
    option as put to them: *"Stay in July (what ships now) — a correction is a
    correction. July's register keeps its $310.00; both months' totals are
    unchanged. Re-dating is refused by name as a move, not a correction. - this
    is correct"*. The behaviour is unchanged; it is now LAW rather than a
    placeholder, and the refusal says so to the clerk who hits it.
    """
    require_tenant(request)
    body = _payload(request)
    if "paid_on" in body:
        return _record_settlement(request, invoice_id, body)
    changes: dict[str, Any] = {}
    if "invoice_date" in body:
        changes["invoice_date"] = _date_value(body["invoice_date"], "invoice_date")
    for field in ("service", "supplier_name", "currency", "volume_unit", "reference", "memo"):
        if field in body:
            changes[field] = body[field]
    if "ledger_account_id" in body:
        changes["ledger_account_id"] = body["ledger_account_id"]
    if "amount" in body:
        changes["amount"] = _decimal(body["amount"], "amount")
    if "volume" in body:
        raw = body["volume"]
        changes["volume"] = (
            None if raw is None or str(raw).strip() == "" else _decimal(raw, "volume")
        )
    try:
        edited = cost_capture.edit_supplier_invoice(
            _actor(request),
            invoice_id,
            correction_reason=body.get("correction_reason"),
            **changes,
        )
    except cost_capture.CostCaptureError as problem:
        # ⚠ THE RE-DATING BRANCH USED TO BE `except NotImplementedError` here,
        # carrying `params={"oq": "OQ-227"}` and a message key ending
        # `_unruled`. OQ-227 CLOSED on 2026-08-16 and the service now refuses
        # by RULE, so a response still naming an open question would tell a
        # clerk to go and ask about a decision that has been made (G8's shape,
        # one layer out). Same 409, same sentence to the user, different
        # standing — and the ruling is cited where the refusal is composed.
        if (getattr(problem, "br_ref", "") or "").startswith("BR-LED-035 · OQ-227"):
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-LED-034 · OQ-227 (PO 2026-08-16)",
                message_key="ledger.cost.redate_after_close_refused",
                params={"ruling": "OQ-227"},
            ) from problem
        raise _guard(problem) from problem
    except NotImplementedError as unruled:
        # ⚠ CR-060 C1 / T6, OQ-1350 — MINTED, NOT ANSWERED. Correcting one of
        # the four facts a POSTED settlement entry copied would move a figure
        # the trial balance already carries, and what a settlement should do
        # when its purchase is corrected is not ruled. The shape is the one the
        # OQ-227 branch above used while THAT question was open: same 409, the
        # question named in `params` so the screen can say which decision is
        # outstanding rather than reporting a server fault.
        raise _unruled_settled_change(unruled) from unruled
    return Response(
        {
            **_row(edited),
            "problems": list(edited.get("problems") or ()),
            "after_close": edited.get("after_close"),
        }
    )


def _unruled_settled_change(problem: Exception) -> errors.ApiError:
    """OQ-1350's refusal, composed once for the edit and the void.

    A `NotImplementedError` reaching a view is a 500 by default, and a 500 tells
    a clerk the product is broken when what is actually true is that a decision
    has not been made. G8's own posture, one layer out: a stub is honest, and so
    is the sentence it produces.
    """
    return errors.BizError(
        errors.BIZ_STATE,
        br_ref=f"CR-060 C1 · {cost_capture.SETTLED_CHANGE_UNRULED}",
        message_key="ledger.cost.settled_change_unruled",
        params={"oq": cost_capture.SETTLED_CHANGE_UNRULED, "detail": str(problem)},
    )


def _record_settlement(request: Any, invoice_id: str, body: dict[str, Any]) -> Response:
    """**CR-060 C1 / task T6 — `paid_on` arrives and the books move.**

    ⚠ **A BODY CARRYING `paid_on` MAY CARRY NOTHING ELSE, AND THE REFUSAL IS
    DELIBERATE.** Recording a settlement POSTS `DR cost / CR cash` and writes its
    own audit action; correcting a captured fact writes a different one. Applying
    both from one request would leave a half-done state if the second half were
    refused — the amount corrected and the settlement not recorded, or worse the
    reverse — and would put one audit trail where two acts happened. They are two
    saves on the screen because they are two acts in the books.

    `settled_at` is a body input, exactly as `voided_at` is on the void route and
    for the same reason (BR-TEN-043): a double-submitted Save must stamp ONE
    moment. It is required only when a date is being recorded — clearing a
    paid-on that never posted stamps nothing.

    `paid_on: null` CLEARS the date, and that is lawful while nothing has posted.
    Once the settlement is in the books it is refused by name (hard rule 4 — no
    UPDATE reaches a posted journal entry), which is what C1 asks for.
    """
    raw = body.get("paid_on")
    other = sorted(set(body) - {"paid_on", "settled_at"})
    if other:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.cost.settlement_alone",
            params={"fields": ", ".join(other)},
            field_errors=[{"field": field, "code": errors.VAL_FORMAT} for field in other],
        )
    paid_on = (
        None
        if raw is None or (isinstance(raw, str) and not raw.strip())
        else _date_value(raw, "paid_on")
    )
    settled_at = _moment(body, "settled_at", message_key="ledger.cost.settled_at_required")
    try:
        settled = cost_capture.record_settlement(
            _actor(request), invoice_id, paid_on=paid_on, settled_at=settled_at
        )
    except cost_capture.CostCaptureError as problem:
        raise _guard(problem) from problem
    return Response(
        {
            **_row(settled),
            "problems": list(settled.get("problems") or ()),
            "settlement": settled.get("settlement"),
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# POST /finance/cost-of-service/{id}/void — never a DELETE (BR-LED-035)
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["POST"])
@permission_classes([AdminOrClerk])
def cost_of_service_void(request: Any, invoice_id: str) -> Response:
    """*"Void, never delete"* — BR-LED-035, and **there is no DELETE route at
    all**, at any layer. The reason is REQUIRED and is the point of the feature:
    the row stays visible in the register precisely so a clerk reconciling
    against a supplier statement can see WHY a line was withdrawn.

    `voided_at` is a body input (BR-TEN-043) so a retried void stamps one moment.
    """
    require_tenant(request)
    body = _payload(request)
    try:
        voided = cost_capture.void_supplier_invoice(
            _actor(request),
            invoice_id,
            reason=body.get("reason"),
            voided_at=_moment(body, "voided_at", message_key="ledger.cost.voided_at_required"),
        )
    except cost_capture.CostCaptureError as problem:
        raise _guard(problem) from problem
    except NotImplementedError as unruled:
        # OQ-1350 — a void drops the row out of every aggregate, and a SETTLED
        # row's cost is also in the trial balance, which a void does not touch.
        # Unposting is a reversal and whether a void should reverse is not ruled.
        raise _unruled_settled_change(unruled) from unruled
    return Response(
        {
            **_row(voided),
            "problems": list(voided.get("problems") or ()),
            "after_close": voided.get("after_close"),
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# GET /finance/cost-of-service/reconciliation — S74, bought vs billed
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def cost_reconciliation_view(request: Any) -> Response:
    """S74 — the reconciliation the accounting package cannot produce.

    Per service, per period: the volume BOUGHT beside the volume BILLED, and the
    unaccounted-for percentage between them — leak, meter under-registration or
    theft, in one number, computable only here because only this product holds
    the billed volumes.

    **A ZERO IS NEVER AN ANSWER ON THIS SCREEN.** Every row either carries a
    percentage or carries the REASON it cannot, with its count: *"no volume
    captured for 1 of 5 water purchases this period"*, *"MMBtu vs ccf"*, *"the
    billed volume could not be read"*. The suppressed case is the whole point of
    BR-LED-031: against a partial denominator July reads **−13.75%**, a utility
    that delivered more than it bought, and that number never reaches a screen,
    a CSV, a PDF or this payload.

    `basis` defaults to the RULED service period (OQ-202, PO 2026-08-16). The
    issued basis is still served — an accountant asking a REVENUE question wants
    it — and it labels itself as not the ruled one.
    """
    require_tenant(request)
    start, end = _window(request.query_params)
    basis = str(request.query_params.get("basis") or billing_seam.BASIS_SERVICE_PERIOD)
    if basis not in billing_seam.PERIOD_BASES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="ledger.cost.basis_unknown",
            params={"basis": basis, "known": list(billing_seam.PERIOD_BASES)},
            field_errors=[{"field": "basis", "code": errors.VAL_UNKNOWN_LOOKUP}],
        )
    # ⚠ CR-060 C9 / task T4 — the SECOND grain, and the sub-metering company's
    # whole reason for opening this screen. Defaulting to `service` keeps every
    # existing caller on the contract it already reads.
    group_by = str(
        request.query_params.get("group_by") or cost_reconciliation.GROUP_BY_SERVICE
    )
    if group_by not in cost_reconciliation.GROUP_BYS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="ledger.cost.group_by_unknown",
            params={"group_by": group_by, "known": list(cost_reconciliation.GROUP_BYS)},
            field_errors=[{"field": "group_by", "code": errors.VAL_UNKNOWN_LOOKUP}],
        )
    if group_by == cost_reconciliation.GROUP_BY_PREMISES:
        result = cost_reconciliation.by_premises(
            period_start=start, period_end=end, basis=basis
        )
    else:
        result = cost_reconciliation.reconciliation(
            period_start=start, period_end=end, basis=basis
        )
    rows = []
    for row in result["rows"]:
        out = dict(row)
        for key in ("bought_volume", "bought_cost", "billed_volume", "unaccounted_for_pct"):
            out[key] = _money(out.get(key))
        out["problems"] = list(out.get("problems") or ())
        rows.append(out)
    return Response(
        {
            "period": result["period"],
            "group_by": result.get("group_by", cost_reconciliation.GROUP_BY_SERVICE),
            "rows": rows,
            "total_bought_cost": _money(result["total_bought_cost"]),
            "currency": result["currency"],
            # ⚠ **`basis_label` AND `formula` STOOD HERE UNTIL 2026-09-25 AND
            # ARE DELETED (`DEF-LED-6669`).** `basis_label` was a 90-word
            # English PARAGRAPH composed in `cost_reconciliation._basis_label`,
            # quoting `OQ-202` and a PO ruling verbatim, and the screen printed
            # it above the table. `formula` was the literal expression
            # `(bought_volume - billed_volume) / bought_volume` — our own field
            # names, rendered to a clerk.
            #
            # **Three rules at once.** B14 rule 33: rationale is ZERO words on
            # screen, and it is REMOVED rather than shortened. Rule 32: no rule
            # id or internal code in clerk-facing copy. And **TD-16 / B8**: the
            # server was sending LANGUAGE on a product with eleven catalogues,
            # so ten of them showed English.
            #
            # **BR-REP-001 IS STILL HONOURED — the basis still rides with the
            # figures.** `basis` below is the CODE, and the screen renders
            # `finance.cost.basis.<code>` from the catalogue in the drawing's
            # own words (Finance blueprint p063: *Service period · Issued*).
            # And the "this is not the ruled basis" warning was never carried
            # by this paragraph anyway: `problems` already publishes it as the
            # code `billed_volume_basis_is_not_the_ruled_service_period`, which
            # the eleven catalogues already have a sentence for.
            "basis": result["basis"],
            "problems": list(result["problems"]),
            # ⚠ **THE REASON WAS FALSE FROM 2026-09-03 UNTIL 2026-09-24 AND THE
            # CONTROL IS STILL CORRECTLY DISABLED — `P2.5`, Finance blueprint
            # p014.** It read *"WHERE this view lives has not been ruled"*, and
            # where it lives WAS ruled: `OQ-204`'s first half closed on
            # 2026-09-03 (`CR-060` C27), ratifying `S73` into A1 as **Finance →
            # Cost of service** and `S74` as its **Bought-vs-billed sub-view**.
            # The register row says so in terms, and this sentence went on
            # naming the settled half as the blocker.
            #
            # **WHAT IS STILL OPEN IS NARROWER AND IS WHAT NOW STANDS:** which
            # download PIPELINE this view registers with — the platform export
            # registry or the IS-11 report pipeline under a report key. That is
            # a build contract, not a place, and `OQ-204` remains
            # `PARTIALLY CLOSED` over exactly it.
            #
            # ⚠ **THE STATE IS UNCHANGED ON PURPOSE.** `P2.5`: *"Four of the
            # controls stay disabled and correctly so — it is the stated CAUSE
            # that is false, not the state."* The control still renders DISABLED
            # with its reason (BR-SHL-025) rather than hidden: a missing control
            # reads as a feature nobody thought of, and a person who needs the
            # CSV needs to know it is a decision and not a bug.
            #
            # ⚠ **THE PROSE `reason` IS DELETED AND A KEY STANDS IN ITS PLACE
            # (`DEF-LED-6669`, 2026-09-25).** `P2.5` corrected what the sentence
            # SAID on 2026-09-24 and left what it WAS: 55 words of undecided
            # engineering — *"the platform export registry, or the IS-11 report
            # pipeline under a report key. The two are different contracts…"* —
            # read by a finance officer who can act on none of it. That is B14
            # rule 33's zero, and it is English on the wire besides.
            #
            # **The disabled state and the `oq` are untouched.** BR-SHL-025
            # still wants the control present and refusing rather than hidden,
            # and `OQ-204`'s remaining half is still the download contract —
            # that fact simply lives here and in the register, not on a screen.
            # The sentence a clerk now reads is the product's own existing one
            # for this exact absence (`billing.runs.gap`), six words.
            "download": {
                "available": False,
                "oq": "OQ-204",
                "reason_key": "finance.cost.downloadGap",
            },
        }
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def cost_reconciliation_download(request: Any) -> Response:
    """**NOT BUILT — OQ-204 is OPEN.** Served as a named refusal rather than a
    404, because a 404 reads as a typo and this is a decision nobody has taken.

    See the module header. The screen never calls this: its Download control is
    disabled with the same reason, carried on the reconciliation payload. The
    route exists so that a client which calls it anyway is told WHY.
    """
    require_tenant(request)
    raise NotImplementedError("OQ-204")


# ═══════════════════════════════════════════════════════════════════════════
# GET /finance/export/drift — OQ-203's condition, on the export screen
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def export_drift(request: Any) -> Response:
    """The batches whose cost section no longer matches the register.

    **This route is the CONDITION the Product Owner attached to OQ-203.** They
    permitted the after-close correction — *"Yes it can be corrected"* — on the
    stated basis that the utility is told **which exported batch no longer
    matches**, so a human can fix it at the ERP end. The registry row is blunt
    about the alternative: *"Building the edit without that warning would be
    worse than freezing it."*

    Every figure carries its currency and both sides are quoted — *"carried
    51,902.50 USD, the register now totals 51,747.50 USD"* — because the person
    receiving this warning has to go and post the difference by hand.
    """
    require_tenant(request)
    rows = []
    for row in exports.stale_batches():
        out = dict(row)
        for key in ("carried", "register_now", "difference"):
            out[key] = _money(out.get(key))
        rows.append(out)
    return Response({"rows": rows, "count": len(rows)})


# ═══════════════════════════════════════════════════════════════════════════
# GET / POST /finance/cost-of-service/{id}/documents — `P5.11`, `DEF-LED-6708`
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET", "POST"])
@parser_classes([MultiPartParser, FormParser, JSONParser])
@permission_classes([AnyTenantRole])  # the WRITE re-gates below; A4 gives every role R
def cost_of_service_documents(request: Any, invoice_id: str) -> Response:
    """The supplier's own invoice, attached to the purchase it settles.

    The Finance blueprint draws this on 5·3a — *"Attach the invoice · drag or
    choose the supplier's PDF"* — and the product had nowhere to put it: the PO
    reported it on 2026-09-25 as *"in capture invoice User cannot attach invoice
    copy digital copy pdf"*.

    ⚠ **IT IS A LIST AND NOT ONE FIELD.** A purchase can carry several — the
    invoice, the delivery note, the credit — which is exactly why
    `tenancy/0051` put the link on `stored_documents.source_type`/`source_id`
    and gave `supplier_invoices` no column.

    ⚠ **RETENTION IS RULED AND IS NOT THIS ENDPOINT'S TO RESTATE.** PO
    2026-09-25, *"Seven years, same as tax receipts"* (`BR-LED-799`). The store
    holds that schedule; nothing here writes one. And B14 rule 33 keeps it off
    the screen: rationale is zero words, so the form says nothing about how long
    a document is kept.

    ⚠ **NO SECOND STORE AND NO SECOND UPLOADER.** `apps.tenancy.document_store`
    is the one door in, with six calling modules before this one; the screen
    mounts the shared `DocumentCapture` (B14 rule 43).
    """
    require_tenant(request)
    if request.method == "POST":
        # A capture is a System Admin / Billing Clerk act and so is attaching
        # its evidence — the same gate, for the same reason (BR-LED-003).
        if not AdminOrClerk().has_permission(request, None):
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-LED-003")
        upload = request.FILES.get("file") if hasattr(request, "FILES") else None
        if upload is None:
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="finance.cost.document_required",
                br_ref="BR-SHL-031",
                field_errors=[{"field": "file", "code": errors.VAL_REQUIRED}],
            )
        try:
            result = cost_capture.attach_supplier_invoice_document(
                _actor(request),
                supplier_invoice_id=invoice_id,
                filename=str(getattr(upload, "name", "") or ""),
                content_type=str(getattr(upload, "content_type", "") or ""),
                content=upload.read(),
            )
        except cost_capture.CostCaptureError as problem:
            raise _refused(problem) from problem
        return Response(result, status=201)

    try:
        return Response(cost_capture.supplier_invoice_documents(invoice_id))
    except cost_capture.CostCaptureError as problem:
        raise _refused(problem) from problem


urlpatterns = [
    # ORDER MATTERS: `reconciliation` and its `download` are all-static and are
    # declared ABOVE `<str:invoice_id>`, or the word "reconciliation" resolves
    # as a supplier-invoice id and answers 404 on a row that never existed.
    path("finance/cost-of-service", cost_of_service),
    path("finance/cost-of-service/reconciliation", cost_reconciliation_view),
    path("finance/cost-of-service/reconciliation/download", cost_reconciliation_download),
    path("finance/cost-of-service/<str:invoice_id>", cost_of_service_item),
    path("finance/cost-of-service/<str:invoice_id>/void", cost_of_service_void),
    path(
        "finance/cost-of-service/<str:invoice_id>/documents",
        cost_of_service_documents,
    ),
    path("finance/export/drift", export_drift),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-018@d744841 (US-LED-019/020/021 ship in this file too — the authorities this slice was authored from, in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-06-cost-of-service-capture.md US-LED-018/019/020/021 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-028..039 · 04-docs/01-spec/11b-api-audit.md §2.10 · 08-qa/01-e2e/journeys/J25-cost-of-service-month.md · 12-governance/01-open-questions.md OQ-200 CLOSED · OQ-202 CLOSED · OQ-203 CLOSED · OQ-201 OPEN · OQ-204 OPEN · OQ-227 minted)
# generated: 2026-08-16 by the surface-debt tails lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING; the ledger rows in 12-governance/09-human-review-ledger.md are the PO's to write and are named in the lane report)
# gates: RED-PROVED FIRST — every path answered `django.urls.exceptions.Resolver404` before this file was included in config/urls.py; the verbatim failure is quoted in the lane report. The OQ-203 drift warning was red-proved by returning `()` from `exports.stale_batches` (`assert 0 == 1`, four tests).
# exceptions: (1) the DOWNLOAD of S74 raises `NotImplementedError("OQ-204")` and the screen disables its control with the reason — where this view lives decides which download pipeline it registers with · (2) `volume_unit` is FREE TEXT with no picker, because a picker would be the vocabulary OQ-201 asks for · (3) an after-close RE-DATING is refused as OQ-227, minted by this lane · (4) ⚠ **CORRECTED 2026-09-25 — THE REGISTER IS PAGED** (`DEF-LED-6710`, `NFR-3`). This read *"the register is UNPAGINATED, matching `cost_capture.register`'s own reported limit rather than inventing a second contract"*; both sides of that have moved, and the footer stayed whole-set because it is a SQL aggregate over the FILTER, never over the rows served · (5) `voided_at` is a REQUIRED body input (BR-TEN-043) — this file reads no clock
# status: VERIFIED-UNRATIFIED
# ───────────────────────────────────────────────────────
