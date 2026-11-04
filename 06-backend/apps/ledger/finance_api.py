# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-015 (month close — the S42 checklist, the close, the reopen
#           and the closed-through banner) · US-LED-016 (S42/S43 export to
#           accounting — preview, recorded batch, history, drill-back, the
#           dimension extracts) · US-LED-014 (the WRITE half of S41: recording
#           a remittance drains the authority's liability)
#           Screens: S41 · S42 · S43
# Rules:    BR-LED-006 (Finance closes the month per fiscal settings; closed
#           periods lock; SysAdmin reopens; the five-item checklist) ·
#           BR-LED-018 (close = WARN + CONFIRM with an audited reason — never a
#           silent close, never a hard lockout) · BR-LED-017 (an export requires
#           the covered period CLOSED) · BR-LED-004 (one summary JE per period
#           per GL account; batches recorded + IDEMPOTENT; every figure drills
#           back) · BR-LED-007 (drift is a release blocker — no clean-looking
#           handover over broken books) · BR-LED-002 / BR-LED-013 (dual-basis
#           remittance; the remittance payment is a JE draining the liability) ·
#           BR-LED-019 (a remittance carries its filing confirmation ref) ·
#           BR-LED-015 (every finance action audits) · BR-TEN-038 (a late-dated
#           event auto-posts forward) · BR-TEN-043 (event time is an INPUT —
#           there is no clock in this file) · BR-TEN-042 (the tenant's currency
#           travels beside every amount) · BR-SHL-025 / BR-IDN-009 (RBAC is
#           server-enforced) · BR-TEN-003 / HR-1 (cross-tenant reads as absent) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money is a decimal
#           string + CHAR(3)) · rule 4 (nothing here edits a posted entry) ·
#           rule 5 (only the posting service writes journal lines — this file
#           writes none and asks `apps.ledger.journal` to) · rule 7 (audit)
# Tests:    06-backend/tests/test_us_led_016_finance_api.py
# Impacts:  config/urls.py inclusion (`urlpatterns` exported here) ·
#           06-backend/openapi/schema.json (the committed contract snapshot
#           moves with any endpoint added here — BE-11 TC05) ·
#           07-frontend/src/features/ledger/CloseExportPage.tsx (S42/S43) and
#           .../RemittancePage.tsx (S41), which are the first callers
# ───────────────────────────────────────────────────────
"""The S42/S43 finance WRITE surface — close, export, and the remittance record.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module is the only way a human can
shut an accounting period or hand a month to an ERP, and both acts are
irreversible in the sense that matters: a closed month's figures stop moving and
an exported batch has already been booked by somebody else's accountant.
AI-authored 2026-08-15 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. **Not on the G7 glob list** — adding a
glob is a process event (B12 r2, *"who watches the watchers"*), so it is
REPORTED for the daily batch rather than self-added, exactly as
`apps/ledger/close.py` reported itself.

════════════════════════════════════════════════════════════════════════════
WHAT DID NOT EXIST BEFORE THIS FILE — DEF-112, MEASURED IN A BROWSER
════════════════════════════════════════════════════════════════════════════
The J19 month-end-close journey booted a real stack, signed in, and went red at
STEP 1 — not on a wrong figure, on the absence of anything to click. The defect
row is exact about it:

    "close_checklist, close_period, reopen_period, the export batch and its four
     gates are built, unit-tested and correct — and no human can reach any of
     them … openapi/schema.json carries NO close path and NO accounting-export
     path, and the ledger API mounts exactly four GETs."

`apps/ledger/close.py` and `apps/ledger/exports.py` each said so in their own
trailers — `D=deferred(the S42 close endpoints are the API half — not built by
this lane)`. Every lane was honest and nothing added the honest notes up. This
file is the D half of both, and `10-scripts/gates/g22_surface_deferrals.py` is
the addition that counts them.

════════════════════════════════════════════════════════════════════════════
WHY THIS IS NOT IN `apps/ledger/api.py`
════════════════════════════════════════════════════════════════════════════
That file states a GUARANTEE, not a preference: *"NO WRITE VERB EXISTS ON ANY
PATH IN THIS FILE … so a forged POST, PUT, PATCH or DELETE is refused by the
ROUTER with a 405 before any view runs"* (hard rule 4 / BR-LED-003, on the four
paths that serve the books read-only). Adding a POST there would silently retire
that guarantee for the trial balance and the journal list as well. The reads keep
their 405; the writes live here, with their own role gates.

════════════════════════════════════════════════════════════════════════════
THE PERIOD IS A WINDOW, NOT AN ID — a stated deviation from 11b §2.10
════════════════════════════════════════════════════════════════════════════
11b §2.10 contracts `POST /finance/periods/{p}/close`. **There is no `{p}`.**
BR-TEN-022 makes fiscal periods COMPUTED from the tenant's settings and never
stored, so no row has an id to put in that path segment; `fiscal_period_closes`
is keyed on (tenant, period_start, period_end) precisely because the period is
its own identity. Minting a surrogate id here would create a second name for a
thing tenancy already names, and the first tenant to change their fiscal year
would have ids pointing at months that no longer exist.

So every path below takes `from` and `to` — the SAME two bare parameter names
`apps/ledger/api._window` and `apps/reports/api._required_window` already read.
**ONE SPELLING, and that is DEF-095's fix**: the frontend was sending `f.from` /
`f.to` under BR-SHL-011's LIST grammar at three endpoints that read the bare
names, so three screens asked for a window the server never saw. A period bound
is not a list filter. Nothing here accepts an `f.`-prefixed bound, because
accepting both spellings is how a contract stops being one.

════════════════════════════════════════════════════════════════════════════
EVERY MOMENT IS AN INPUT (BR-TEN-043) — there is no clock in this file
════════════════════════════════════════════════════════════════════════════
`closed_at`, `reopened_at`, `created_at` and `posted_at` all arrive on the body
and are all REQUIRED. This is the payments-lane pattern (`apps/payments/api.
_moment`, PO ruling 2026-08-11: *"posting and actual dates can differ; ask actual
date to user"*) and it is load-bearing here for a second reason: a retried close
or a retried send must stamp ONE moment, and a service that read the clock would
stamp a different one on the retry and record two different histories of the same
act.

════════════════════════════════════════════════════════════════════════════
HOW A SERVICE REFUSAL BECOMES AN ENVELOPE — by re-asking, never by string-match
════════════════════════════════════════════════════════════════════════════
`close.CloseError` and `exports.ExportError` are prose. Classifying them by
searching their message text would bind this file to another module's sentences,
and the first reworded refusal would silently downgrade a 409 to a 500.

Instead each write endpoint asks the PUBLISHED read that answers the same
question, first: `close.close_checklist()` says whether the period is already
closed and which items are incomplete; `exports.export_preview()` runs the same
four gates as `create_export_batch` and *writes nothing*. The catalog code comes
from that structured answer. The service is then called and is still the
enforcement — if it refuses anyway (the race the SELECT cannot see, which is what
`uq_export_batches_period_target` is for), the residual refusal is rendered under
its own key with the service's sentence carried in `params.detail` for the trail.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from django.http import HttpResponse, HttpResponseRedirect
from django.utils import timezone
from django.urls import path
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.ledger import close, export_files, exports, journal, models, tie_out, wire
from apps.tenancy import selectors as tenancy_selectors
from core import audit as core_audit
from core import errors
from core.permissions import AdminOrClerk, AnyTenantRole, SystemAdminOnly
from core import tenancy as core_tenancy
from core.tenancy import require_tenant

#: US-LED-004 §5's own audit code (*"`audit_log` `tieout.drift_detected`"*).
#: A code, never prose — a month-end reviewer greps for this exact string, and
#: it is the one event that says the books and the registers disagreed.
AUDIT_DRIFT_DETECTED = "tieout.drift_detected"

#: `P4.2` — who took a copy of a recorded hand-over, and which one. CLAUDE.md
#: rule 7: this is a money action, so it writes its row. A re-download is also
#: the one event that answers *"which file is the accountant holding?"* months
#: later, and it is the only trace of it that exists — nothing is stored.
AUDIT_BATCH_DOWNLOADED = "export.batch_downloaded"


# ═══════════════════════════════════════════════════════════════════════════
# Parameter and body reading — one shape, shared by every route below
# ═══════════════════════════════════════════════════════════════════════════
def _tenant_currency() -> str | None:
    """The tenant's declared CHAR(3), through tenancy's OWN published read.

    CLAUDE.md rule 2 is the PAIR — `NUMERIC(18,6)` **and** `CHAR(3)` — and
    DEF-099 is what the missing half costs: two payments endpoints served every
    amount with no currency member, the screen had to fetch one from a third
    request, and guessing `USD` prints a wrong symbol on a Canadian tenant's
    books. Every money-carrying body below therefore carries `currency`, read
    the way `apps/ledger/api._tenant_currency` reads it — through
    `apps.tenancy.selectors.regional_settings()`, never by reaching into
    `apps.tenancy.models` (B1 forbids it and G6 greps for it).
    """
    return tenancy_selectors.regional_settings().get("currency")


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="ledger.payload_not_object")
    return data


def _actor(request: Any) -> Any:
    """WHO is closing the month, from the SESSION — never from the body.

    `audit_log.actor_user_id` is hard rule 7's evidence half, so the one thing
    it must not be is client input.
    """
    return getattr(request, "user", None)


def _date_value(raw: Any, field: str) -> date:
    """One ISO calendar date, or a refusal naming the field.

    `date.fromisoformat` and nothing looser, for the reason
    `apps/ledger/api._date_param` gives: a period bound decides which month's
    money a finance officer is handing to an accountant, and a date parsed by
    guessing would put two different windows under one request in two regions.
    """
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.report.date_invalid",
            field_errors=[{"field": field, "code": errors.VAL_FORMAT}],
        ) from problem


def _window(source: Any, *, getter: str = "get") -> tuple[date, date]:
    """`from` + `to`, both REQUIRED, refusing an inverted range.

    Every route in this file needs a real window: a checklist, a close, an
    export and a remittance are each *for a period*, and BR-LED-017 makes the
    covered window the thing the closed-period gate is asked about. An open
    bound would make "the period" mean something different to every caller.
    """
    read = getattr(source, getter)
    raw_start, raw_end = read("from"), read("to")
    for field, raw in (("from", raw_start), ("to", raw_end)):
        if raw is None or str(raw).strip() == "":
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="ledger.report.period_required",
                field_errors=[{"field": field, "code": errors.VAL_REQUIRED}],
            )
    start = _date_value(raw_start, "from")
    end = _date_value(raw_end, "to")
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
    """A caller-supplied instant — BR-TEN-043, and REQUIRED (see the header).

    Two shapes, because two callers exist: a full ISO-8601 instant keeps its own
    offset, and a bare `YYYY-MM-DD` — which is what a date field collects — is
    anchored to UTC. **WHICH instant a user-entered calendar date should become,
    in whose timezone, is OQ-153**, raised by the payments lane and not answered
    here; the DATE is preserved either way and the date is what the close row and
    the audit trail read.

    `message_key` is passed as a LITERAL by every call site rather than composed,
    for G18's reason: a key built at runtime is a key no catalogue check can see.
    """
    raw = payload.get(name)
    if raw is None or (isinstance(raw, str) and str(raw).strip() == ""):
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


def _choice(
    payload: dict[str, Any],
    name: str,
    allowed: tuple[str, ...],
    *,
    default: str | None,
    message_key: str,
) -> str:
    """One value out of a CLOSED vocabulary the module publishes.

    The vocabularies are `apps.ledger.models.EXPORT_TARGETS` and
    `.EXPORT_GRANULARITIES` — imported, never retyped, so a fifth target added
    there reaches this surface without an edit here (BR-REP-006: filters
    enumerate the LIVE set).
    """
    raw = payload.get(name)
    if raw is None or str(raw).strip() == "":
        if default is not None:
            return default
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key=message_key,
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    value = str(raw).strip()
    if value not in allowed:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key=message_key,
            params={"value": value, "allowed": list(allowed)},
            field_errors=[{"field": name, "code": errors.VAL_UNKNOWN_LOOKUP}],
        )
    return value


def _reason(payload: dict[str, Any], name: str = "reason") -> str | None:
    raw = payload.get(name)
    cleaned = str(raw or "").strip()
    return cleaned or None


# ═══════════════════════════════════════════════════════════════════════════
# Serialization — decimal STRINGS + the tenant's CHAR(3), never a float
# ═══════════════════════════════════════════════════════════════════════════
def _checklist_item(item: close.ChecklistItem) -> dict[str, Any]:
    """One computed checklist row.

    `state` is served with THREE values, not two. `unknown` is not a synonym for
    `incomplete`: it means the register that would answer lives in billing or
    payments and no module publishes the read (`wanted_reads` names the exact
    callable). It COUNTS as incomplete — the close demands a reason over it —
    but a screen that rendered it as a plain ✗ would be claiming somebody
    checked, which is hard-won law 1 in a checklist.

    `detail` is the server's own English prose and no screen renders it (TD-16:
    the server sends keys, the UI renders language). It travels for the trail
    and for a developer reading the response.

    `outstanding` is that same figure AS DATA, added 2026-09-02 for CR-059
    CS-13's screen half: the two payments items compute now, and CS-13 asks S42
    to say *how many* batches or bank lines are left. The number was only ever
    inside `detail`'s sentence, which no screen may render — so a screen could
    not say it without parsing prose. `null` means nobody counted (an uncounted
    item, or a register that could not answer); `0` means it was read and there
    is nothing outstanding. Those are different facts (DEF-127).

    `amount` is `P5.10` of the Finance blueprint — **what this row is WORTH**,
    which is the other half of the same complaint `outstanding` answers. Four
    items now carry the figure they were already computing to decide done
    against not done: the two accruals' `preview.total`, the exposure behind an
    overdue accrual reversal, and the tax liability still held. It goes out as
    `wire.money`, so it is the exact decimal string and the SCREEN rounds to
    two (hard rule 2) — a server that pre-rounded would be a second rounding
    path, and B4 gives this product one.

    ⚠ **`null` IS NOT `0.00` HERE EITHER.** `null` means this row carries no
    money figure — it is a COUNTED item (bill runs, deposit batches, bank
    lines), or it is complete and has nothing outstanding. A `0.00` beside a
    tick reads as a measurement somebody took; the absence reads as nothing to
    measure, which is what is true.
    """
    return {
        "code": item.code,
        "state": item.state,
        "complete": item.complete,
        "detail": item.detail,
        "wanted_reads": list(item.wanted_reads),
        "outstanding": item.outstanding,
        "amount": wire.money(item.amount),
    }


def _checklist_dict(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "period": {"start": result["period"][0], "end": result["period"][1]},
        "items": [_checklist_item(item) for item in result["items"]],
        "incomplete": [item.code for item in result["incomplete"]],
        "ready": result["ready"],
        "closed": result["closed"],
        "unavailable": wire.gaps(result["unavailable"]),
        # `P5.10` — the currency the `amount` figures are in. `null` on an empty
        # or mixed book, which is why the screen renders no money rather than
        # money in a currency nobody chose.
        "currency": result["currency"],
    }


def _closed_period_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "period": {"start": row["period"][0], "end": row["period"][1]},
        "status": row["status"],
        "closed_at": wire.moment(row["closed_at"]),
        "reason": row["reason"],
        "incomplete_items": list(row["incomplete_items"] or ()),
        "reopened_at": wire.moment(row["reopened_at"]),
        "reopen_reason": row["reopen_reason"],
    }


def _summary_row(row: exports.SummaryRow, currency: str | None) -> dict[str, Any]:
    """One GL line of the handover — A14 §Accounting exports' own four columns
    (GL account · What it is · Debit · Credit) plus the target ref that addresses
    it in the ERP."""
    return {
        "code": row.code,
        "name": row.name,
        "type": row.type,
        "account_id": row.account_id,
        "target_ref": row.target_ref,
        "debit": wire.money(row.debit),
        "credit": wire.money(row.credit),
        "currency": currency,
        "window": {"start": row.window_start.isoformat(), "end": row.window_end.isoformat()},
    }


def _cost_section_dict(section: dict[str, Any], currency: str | None) -> dict[str, Any]:
    """BR-LED-039's payable side, carried SEPARATELY and never added in.

    US-LED-021 TC-7: the section is REGISTER-derived while OQ-200 is open, its
    total is not in `total_debits`/`total_credits`, and the trial balance does
    not contain it. Three markers ride the wire — `source`, `in_trial_balance`
    and the `problems` code — so a reader cannot add this figure to a footing it
    is not part of without stepping past all three.
    """
    return {
        "source": section["source"],
        "in_trial_balance": section["in_trial_balance"],
        "entries": section["entries"],
        "cost_total": wire.money(section["cost_total"]),
        "currency": section.get("currency") or currency,
        "rows": [
            {
                "code": row["code"],
                "name": row["name"],
                "account_id": row["account_id"],
                "target_ref": row["target_ref"],
                "amount": wire.money(row["amount"]),
                "purchase_count": row["purchase_count"],
                "currency": row["currency"],
                "unsigned": row["unsigned"],
                "source": row["source"],
            }
            for row in section["rows"]
        ],
        "missing_refs": list(section["missing_refs"]),
        # CR-060 T6c / DEF-3380 — what the section does NOT carry, on the wire
        # so the screen can SAY it. A settled purchase is inside the balanced
        # totals beside this section, and until 2026-09-02 it was in both.
        "settled": {
            "count": section["settled"]["count"],
            "total": wire.money(section["settled"]["total"]),
            "currency": section["settled"].get("currency") or currency,
            "source": section["settled"]["source"],
            "in_trial_balance": section["settled"]["in_trial_balance"],
            "label": section["settled"]["label"],
        },
        # `problems` is a tuple of stable CODE STRINGS, not of gap dicts — the
        # shape `apps/ledger/exports.COST_SHAPE_NOT_RULED` publishes. Lifted
        # into the `unavailable` shape every other finance body uses so a screen
        # has ONE renderer for an absence, and given the section's own label as
        # the detail rather than a second sentence written here.
        "unavailable": [
            {
                "code": code,
                "br_ref": "BR-LED-039 · OQ-200",
                "detail": section["label"],
                "wanted_reads": [],
            }
            for code in section["problems"]
        ],
    }


def _preview_dict(preview: dict[str, Any], currency: str | None) -> dict[str, Any]:
    """S43's balanced preview — *"entries count, total debits = credits"*.

    **`sendable` is the server's answer and the screen renders it; it is never
    re-derived in the browser.** Four gates decide it (BR-LED-017's closed
    period, BR-LED-004's idempotency, BR-LED-007's footing, BR-LED-014's export
    codes) and a client that re-computed them from the four booleans below would
    be a fifth opinion that drifts the first time a gate changes.
    """
    existing = preview["already_exported"]
    return {
        "period": {"start": preview["period"][0], "end": preview["period"][1]},
        "target": preview["target"],
        "granularity": preview["granularity"],
        "currency": currency,
        "entries": preview["entries"],
        "rows": [_summary_row(row, currency) for row in preview["rows"]],
        "total_debits": wire.money(preview["total_debits"]),
        "total_credits": wire.money(preview["total_credits"]),
        "period_total_debits": wire.money(preview["period_total_debits"]),
        "period_total_credits": wire.money(preview["period_total_credits"]),
        "balanced": preview["balanced"],
        "period_closed": preview["period_closed"],
        "missing_refs": list(preview["missing_refs"]),
        "already_exported": _batch_dict(existing) if existing is not None else None,
        "sendable": preview["sendable"],
        "cost_section": _cost_section_dict(preview["cost_section"], currency),
    }


def _batch_dict(batch: dict[str, Any]) -> dict[str, Any]:
    """One S42 export-history row — Sent · Period · Destination · Entries · By.

    `batch_no` is null until a tenant seeds the `export_batch` number series
    (BR-TEN-041), and the null is served rather than a composed number: the
    batch's identity in the database is (period, target), and a second allocator
    is how two batches end up as EXP-7.
    """
    return {
        "batch_id": batch["batch_id"],
        "batch_no": batch["batch_no"],
        "period": {"start": batch["period"][0], "end": batch["period"][1]},
        "target": batch["target"],
        "granularity": batch["granularity"],
        "entries": batch["entries"],
        "total_debits": wire.money(batch["total_debits"]),
        "total_credits": wire.money(batch["total_credits"]),
        "currency": batch["currency"],
        "content_hash": batch["content_hash"],
        "created_at": wire.moment(batch["created_at"]),
        "created_by_user_id": batch["created_by_user_id"],
        # ── `P5.4` · the handover's answer ────────────────────────────────
        # ⚠ **`null` MEANS NOBODY HAS SAID, AND THE SCREEN RENDERS THAT AS
        # ITSELF.** Not *pending*, not *failed*. There is no callback in a file
        # handover (`BR-LED-020` makes direct connect v2), so an unanswered
        # batch is the ordinary case until a clerk writes down what the
        # accountant told them. `DEF-127` is what it costs to spell *nobody
        # looked* and *the answer is no* the same way.
        "ack_state": batch["ack_state"],
        "ack_at": wire.moment(batch["ack_at"]),
        "ack_reference": batch["ack_reference"],
        "ack_note": batch["ack_note"],
        "ack_by_user_id": batch["ack_by_user_id"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# S42 — the close checklist (US-LED-015 TC-1)
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Finance = R for Staff/Clerk, CRUD for Executive
def close_checklist(request: Any) -> Response:
    """BR-LED-006's five items, computed live, plus every period ever closed.

    Params: `from` + `to`, both REQUIRED.

    The five items are the rule's own — runs issued · batches reconciled · bank
    rec current · accruals posted · remittance recorded — and **three of them
    answer `unknown`**, because billing and payments publish no count of
    unissued runs, unreconciled batches or unmatched bank lines. Each names the
    callable it wants. That is served as it is computed; an API layer that
    flattened `unknown` into `incomplete` would erase the distinction between
    *"we looked and it is not done"* and *"nobody can look"*, which is the whole
    reason the third state exists.

    The closed-period history rides along because the S42 banner needs it in the
    same paint (*"closed through July"*), and a second request for one date would
    be a second round trip for a card.
    """
    require_tenant(request)
    start, end = _window(request.query_params)
    result = close.close_checklist(period_start=start, period_end=end)
    body = _checklist_dict(result)
    body["closed_periods"] = [_closed_period_row(row) for row in close.closed_periods()]
    return Response(body)


# ═══════════════════════════════════════════════════════════════════════════
# S36 — the subledger tie-outs and the drift red flag (US-LED-004, BLOCKER)
# ═══════════════════════════════════════════════════════════════════════════
def _tie_out_row(row: tie_out.TieOutRow) -> dict[str, Any]:
    """One tie-out row on the wire, with BOTH figures and no substituted zero.

    `gl` / `register` / `drift` go out as `null` when the module could not read
    them — `wire.money(None)` is `None` — because a screen that received 0.00
    for an unreadable register would render *the customers register holds
    nothing*, which is a claim, over a book that might hold thousands.
    """
    return {
        "subledger": row.subledger,
        "state": row.state,
        "gl": wire.money(row.gl),
        "register": wire.money(row.register),
        "drift": wire.money(row.drift),
        # CLAUDE.md rule 2's CHAR(3) partner, DERIVED from the lines summed
        # (DEF-081) and falling back to the tenant's declared code only when the
        # window posted nothing at all.
        "currency": row.currency or _tenant_currency(),
        "basis": row.basis,
        "blocks_release": row.blocks_release,
        "causes": wire.gaps(row.causes),
    }


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Finance = R for Staff/Clerk
def tie_outs(request: Any) -> Response:
    """BR-LED-007's three control-vs-register comparisons — the release blocker.

    Params: `from` + `to`, both REQUIRED (they scope the TAX row; AR and
    deposits are cumulative control balances — see `tie_out.tie_outs`).

    **THE DRIFT AUDIT IS WRITTEN HERE AND ONLY ON DRIFT** (US-LED-004 §5's
    `audit_log tieout.drift_detected`; BR-LED-015). It is in the endpoint rather
    than in `apps/ledger/tie_out.py` for two reasons that both matter: that
    module has NO writes by design (a module that could write could also be made
    to store an acknowledgement, and TC-5 forbids one), and an actor only exists
    at the request. The row carries both figures and the delta, so a month-end
    reviewer can grep `tieout.drift_detected` and read what disagreed without
    re-running anything.

    ⚠ **THIS IS A GET THAT AUDITS, WHICH IS UNUSUAL AND IS DELIBERATE.** The
    volume objection — a clerk leaving S36 open writes a row per refresh — is
    real and is accepted: drift is a RELEASE BLOCKER, so on a correct book this
    writes nothing at all, and on a drifting one a repeated record of *how long
    the books disagreed and by how much* is exactly what an auditor asks for
    afterwards. A first-observation-only row would need state, and state here is
    one small step from the dismiss path TC-5 forbids.
    """
    require_tenant(request)
    start, end = _window(request.query_params)
    result = tie_out.tie_outs(period_start=start, period_end=end)
    rows = [_tie_out_row(row) for row in result["rows"]]

    for row, source in zip(rows, result["rows"]):
        if source.state != tie_out.STATE_DRIFTING:
            continue
        core_audit.money_action(
            _actor(request),
            AUDIT_DRIFT_DETECTED,
            "tie_out",
            # No `entity_id`: `audit_log.entity_id` is a UUID column and a
            # tie-out is a COMPARISON, not a row — it has no id to name. The
            # subledger travels in the payload, where a reviewer greps for it.
            None,
            after={
                "subledger": source.subledger,
                "gl": row["gl"],
                "register": row["register"],
                "drift": row["drift"],
                "currency": row["currency"],
                "basis": source.basis,
                "period": {"start": start.isoformat(), "end": end.isoformat()},
            },
        )

    return Response(
        {
            "basis": result["basis"],
            "period": {"start": wire.day(start), "end": wire.day(end)},
            "rows": rows,
            "drifting": list(result["drifting"]),
            "unverifiable": list(result["unverifiable"]),
            "release_blocked": result["release_blocked"],
            "dismissible": result["dismissible"],
        }
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def periods(request: Any) -> Response:
    """Every period this tenant has ever closed, newest first (US-LED-015 §5's
    *closed-through* card). No window: the question is "what is shut".

    Not paginated, and that is not an oversight of 11b G5. The row count is one
    per CLOSED period — twelve a year for a monthly tenant — not one per
    transaction, and the S42 banner reads the newest row of the whole set.
    """
    require_tenant(request)
    return Response({"rows": [_closed_period_row(row) for row in close.closed_periods()]})


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # RULED 2026-09-24 (BR-LED-006), see below
def close_period(request: Any) -> Response:
    """BR-LED-018 — WARN + CONFIRM. Never a silent close, never a hard lockout.

    Body: `from`, `to`, `closed_at` (REQUIRED — BR-TEN-043) and `reason`
    (required only when the checklist is not complete).

    **The 422 over an incomplete checklist is the WARN, not a lockout.** It names
    every incomplete item in `params.incomplete`, and the same request with a
    reason succeeds — that is what BR-LED-018 means by *close-anyway with an
    audited reason*. The items are SNAPSHOTTED beside the reason on the close row
    by `apps.ledger.close`, because recomputing them later answers a different
    question (J19 step 1's *"reason + incomplete-item snapshot recorded on the
    close"*).

    ⚠ **THE ROLE GATE IS RULED, NOT READ — AMENDED 2026-09-24. THIS PARAGRAPH
    SAID THE OPPOSITE.** PO ruling 2026-09-24, verbatim: *"system admin and
    clark"*. **So System Admin + Billing Clerk close a month by signed law
    (BR-LED-006, amended), and `POST /finance/periods/reopen` stays System Admin
    only — confirmed the same day, verbatim: *"yes correct - Reopening a month
    System Admin only"*.** The gate did NOT move; what moved is that it stopped
    describing itself as a guess. `close.ROLE_GATE_IS_A_READING` and its
    `unavailable` sentence are RETIRED, so this response's `unavailable` is now
    EMPTY where it used to carry one entry.

    Until that day the two roles were carried from OQ-175 (2026-08-12, *"System
    Admin, Billing Clerk"* — **about REVERSING a posted entry**) and EP-LED-05 §8
    flagged the carry. ⚠ **§8 FLAGS TWO CARRIES AND THIS RULING COVERS ONE: the
    REMITTANCE record below was never put to the PO and stays flagged.**

    The permission class here matches the service gate deliberately: a mismatch
    would answer 403 in one layer and 200 in the other.
    """
    require_tenant(request)
    payload = _payload(request)
    start, end = _window(payload)
    closed_at = _moment(payload, "closed_at", message_key="ledger.close.closed_at_required")
    reason = _reason(payload)

    # Ask the PUBLISHED read, never the exception text — see the module header.
    checklist = close.close_checklist(period_start=start, period_end=end)
    if checklist["closed"]:
        raise errors.BizError(
            errors.BIZ_LOCKED,
            br_ref="BR-LED-006",
            message_key="ledger.close.already_closed",
            params={"from": start.isoformat(), "to": end.isoformat()},
        )
    if checklist["incomplete"] and reason is None:
        raise errors.BizError(
            errors.BIZ_APPROVAL,
            br_ref="BR-LED-018",
            message_key="ledger.close.reason_required",
            params={
                "incomplete": [item.code for item in checklist["incomplete"]],
                "count": len(checklist["incomplete"]),
            },
        )
    try:
        result = close.close_period(
            _actor(request),
            period_start=start,
            period_end=end,
            closed_at=closed_at,
            reason=reason,
        )
    except close.CloseError as refusal:
        raise _close_refused(refusal) from refusal
    return Response(
        {
            "period": {"start": result["period"][0], "end": result["period"][1]},
            "status": result["status"],
            "closed_at": wire.moment(result["closed_at"]),
            "reason": result["reason"],
            "incomplete_items": [_checklist_item(item) for item in result["incomplete_items"]],
            "unavailable": wire.gaps(result["unavailable"]),
        },
        status=201,
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # RULED, unlike the close gate above
def reopen_period(request: Any) -> Response:
    """BR-LED-006 / BR-TEN-038 — *"SysAdmin reopens"*, with a reason, audited.

    Body: `from`, `to`, `reopened_at` (REQUIRED) and `reason` (REQUIRED).

    This is the one role gate in the close family that IS separately ruled rather
    than read across from OQ-175: both rules name the System Admin explicitly, so
    a Billing Clerk who may close a month may not reopen one (US-LED-015 TC-4).
    The permission class says so at the door and `close.reopen_period` says so
    again at the service, which BR-SHL-025 makes the enforcement either way.

    The reason is required BEFORE the door opens, not after: a reopened month can
    receive entries that change totals an ERP has already been handed
    (BR-LED-017), so the record of why has to exist first.
    """
    require_tenant(request)
    payload = _payload(request)
    start, end = _window(payload)
    reopened_at = _moment(payload, "reopened_at", message_key="ledger.reopen.reopened_at_required")
    reason = _reason(payload)
    if reason is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.reopen.reason_required",
            field_errors=[{"field": "reason", "code": errors.VAL_REQUIRED}],
        )
    try:
        result = close.reopen_period(
            _actor(request),
            period_start=start,
            period_end=end,
            reopened_at=reopened_at,
            reason=reason,
        )
    except close.CloseError as refusal:
        raise _close_refused(refusal) from refusal
    return Response(
        {
            "period": {"start": result["period"][0], "end": result["period"][1]},
            "status": result["status"],
            "reopened_at": wire.moment(result["reopened_at"]),
            "reason": result["reason"],
        }
    )


def _close_refused(refusal: close.CloseError) -> errors.ApiError:
    """The residual close refusal — everything the published reads did not
    already classify (a tenant with no fiscal settings, a window spanning more
    periods than anybody meant, a backwards period).

    Rendered under ONE key with the service's sentence in `params.detail`. The
    UI renders its own copy from the key (TD-16); the sentence is there for the
    trail and for whoever reads the response in a terminal.
    """
    return errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-LED-006 · BR-TEN-022",
        message_key="ledger.close.refused",
        params={"detail": str(refusal)},
    )


# ═══════════════════════════════════════════════════════════════════════════
# S42 / S43 — export to accounting (US-LED-016)
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def export_preview(request: Any) -> Response:
    """S43's balanced preview, and the four gates said out loud BEFORE a send.

    Params: `from` + `to` (REQUIRED), `target` (REQUIRED — one of
    `models.EXPORT_TARGETS`), `granularity` (default `summary`).

    Writes NOTHING. It runs the same gates `create_export_batch` runs and reports
    which ones would refuse, so the modal can say *"July is still open"* or
    *"6900 · Bad debt has no QBO ref"* before a clerk clicks send rather than
    after. That is the whole reason the preview exists as a separate read: a
    refusal a human meets on the confirm button is a refusal they meet with the
    modal already dismissed.
    """
    require_tenant(request)
    start, end = _window(request.query_params)
    target = _choice(
        request.query_params,
        "target",
        models.EXPORT_TARGETS,
        default=None,
        message_key="ledger.export.target_required",
    )
    granularity = _choice(
        request.query_params,
        "granularity",
        models.EXPORT_GRANULARITIES,
        default=models.EXPORT_SUMMARY,
        message_key="ledger.export.granularity_invalid",
    )
    try:
        preview = exports.export_preview(
            period_start=start, period_end=end, target=target, granularity=granularity
        )
    except exports.ExportError as refusal:
        raise _export_refused(refusal) from refusal
    return Response(_preview_dict(preview, _tenant_currency()))


@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])  # POST additionally gated below + at the service
def export_batches(request: Any) -> Response:
    """GET — S42's export history. POST — LE-5's recorded, idempotent handover.

    GET params: `target` (optional filter). POST body: `from`, `to`, `target`,
    `granularity` (default `summary`) and `created_at` (REQUIRED — BR-TEN-043; a
    retried send must stamp ONE moment).

    **THE FOUR REFUSALS ARE THE FEATURE, and each carries a different catalog
    code so a screen can act on them differently:**

        period still open        409 BIZ-LOCKED       BR-LED-017
        already handed over      409 BIZ-IDEMPOTENT   BR-LED-004 (+ the batch)
        the books do not foot    500 SYS-DRIFT        BR-LED-007
        an account has no ref    422 BIZ-COMPLETENESS BR-LED-014

    The idempotency refusal carries the EXISTING batch on `params`, because
    T5-07's whole recovery path is *re-DOWNLOAD, never re-export* and a refusal
    that did not carry the link would send a clerk hunting for it.

    **The drift refusal is a 500 on purpose.** SYS-DRIFT's law in the B12 §3
    catalog is BR-LED-007, and unbalanced books are not a thing the user did
    wrong: they mean a posting-service bypass happened. A 422 would invite the
    screen to render it as a field error a clerk could fix.

    Two clerks clicking send at once do not race past this: the SELECT above is
    checked first, and `uq_export_batches_period_target` catches what a SELECT
    cannot — the residual `ExportError` is re-classified through the same table.
    """
    require_tenant(request)
    currency = _tenant_currency()
    if request.method == "GET":
        target = request.query_params.get("target") or None
        if target is not None and target not in models.EXPORT_TARGETS:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="ledger.export.target_required",
                params={"value": target, "allowed": list(models.EXPORT_TARGETS)},
                field_errors=[{"field": "target", "code": errors.VAL_UNKNOWN_LOOKUP}],
            )
        rows = [_batch_dict(row) for row in exports.export_history(target=target)]
        return Response(
            {
                "rows": rows,
                "currency": currency,
                "count": len(rows),
                # `P1.6` — THE TARGET VOCABULARY, SERVED ONCE.
                #
                # ⚠ **IT WAS HAND-COPIED INTO THE FRONT END**, as
                # `EXPORT_TARGETS = ["qbo","xero","csv","iif"]` in
                # `07-frontend/src/api/endpoints.ts`, with a comment reading
                # *"`apps.ledger.models.EXPORT_TARGETS` verbatim"* — which is a
                # claim about another file that nothing re-checks. `BR-LED-004`
                # owns this list; a fifth target added here would leave the
                # picker offering four for ever, and `tsc` and every test would
                # pass. That is the service list's failure exactly (CLAUDE.md
                # law 12: never hand-type a list), one module over.
                #
                # It rides on THIS response rather than on a new endpoint
                # because this is the read the Close & export screen already
                # makes, and the screen that draws the picker is the screen that
                # draws this history.
                "targets": list(models.EXPORT_TARGETS),
            }
        )

    if not AdminOrClerk().has_permission(request, None):
        # A4 gives the Executive VIEW on this surface and not the send. Raised
        # as the catalog code rather than returned bare, so BR-AUD-018's attempt
        # row is written by the one handler that writes them all.
        raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-LED-004")

    payload = _payload(request)
    start, end = _window(payload)
    target = _choice(
        payload,
        "target",
        models.EXPORT_TARGETS,
        default=None,
        message_key="ledger.export.target_required",
    )
    granularity = _choice(
        payload,
        "granularity",
        models.EXPORT_GRANULARITIES,
        default=models.EXPORT_SUMMARY,
        message_key="ledger.export.granularity_invalid",
    )
    created_at = _moment(payload, "created_at", message_key="ledger.export.created_at_required")

    try:
        preview = exports.export_preview(
            period_start=start, period_end=end, target=target, granularity=granularity
        )
    except exports.ExportError as refusal:
        raise _export_refused(refusal) from refusal
    gate = _export_gate(preview, start, end, target)
    if gate is not None:
        raise gate
    try:
        batch = exports.create_export_batch(
            _actor(request),
            period_start=start,
            period_end=end,
            target=target,
            created_at=created_at,
            granularity=granularity,
        )
    except exports.ExportError as refusal:
        raise _export_refused(refusal) from refusal
    body = _batch_dict(batch)
    body["unavailable"] = wire.gaps(batch.get("unavailable") or ())
    return Response(body, status=201)


def _export_gate(preview: dict[str, Any], start: date, end: date, target: str):
    """The four BR gates, read off the PUBLISHED preview and never off a string.

    Order matters and is `create_export_batch`'s own: closed → idempotent →
    footing → refs. A month that is both open and unbalanced is reported as
    OPEN, because closing it is what a human does next and the footing may well
    change on the way.
    """
    if not preview["period_closed"]:
        return errors.BizError(
            errors.BIZ_LOCKED,
            br_ref="BR-LED-017",
            message_key="ledger.export.period_not_closed",
            params={"from": start.isoformat(), "to": end.isoformat()},
        )
    existing = preview["already_exported"]
    if existing is not None:
        return errors.BizError(
            errors.BIZ_IDEMPOTENT,
            br_ref="BR-LED-004",
            message_key="ledger.export.already_exported",
            params={
                "target": target,
                "batch_id": existing["batch_id"],
                "batch_no": existing["batch_no"],
                "from": existing["period"][0],
                "to": existing["period"][1],
            },
        )
    if not preview["balanced"]:
        return errors.SysError(
            errors.SYS_DRIFT,
            br_ref="BR-LED-007",
            message_key="ledger.export.does_not_foot",
            params={
                "debits": str(preview["period_total_debits"]),
                "credits": str(preview["period_total_credits"]),
            },
        )
    if preview["missing_refs"]:
        return errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-LED-014",
            message_key="ledger.export.missing_export_codes",
            params={"accounts": list(preview["missing_refs"]), "target": target},
        )
    return None


def _export_refused(refusal: exports.ExportError) -> errors.ApiError:
    """A residual export refusal — the race, and the argument checks the preview
    itself raises (an unknown target, a backwards window).

    `existing_batch` is carried through when the service attached one, because
    that is the link T5-07's recovery needs and losing it here would make the
    409 unactionable.
    """
    existing = getattr(refusal, "existing_batch", None)
    if existing:
        return errors.BizError(
            errors.BIZ_IDEMPOTENT,
            br_ref="BR-LED-004",
            message_key="ledger.export.already_exported",
            params={
                "target": existing["target"],
                "batch_id": existing["batch_id"],
                "batch_no": existing["batch_no"],
                "from": existing["period"][0],
                "to": existing["period"][1],
            },
        )
    return errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-LED-004 · BR-LED-017",
        message_key="ledger.export.refused",
        params={"detail": str(refusal)},
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def export_batch_acknowledge(request: Any, batch_id: str) -> Response:
    """`P5.4` — record what the accounting package's operator said.

    Body: `state` (one of `accepted` · `rejected` · `partial`),
    `acknowledged_at` (REQUIRED — `BR-TEN-043`; the import happened when it
    happened and this file reads no clock), and optionally `reference` — their
    id for it in their system — and `note`, which is what they said when the
    answer is `rejected` or `partial`.

    ⚠ **THE BLUEPRINT'S OWN SENTENCE IS THE TASK:** *"Nothing reports back
    whether the accounting package accepted it."* A handover recorded who sent
    what and when, and then ended; a finance officer asking *"did QuickBooks
    take July?"* got `finance.export.noAckStatus`, a stated absence the screen
    has rendered since it shipped.

    ⚠ **A RECORDED ANSWER, NOT A LIVE ONE.** `BR-LED-020` makes v1 a FILE/batch
    handover and direct connect v2, so there is nothing to poll. The person who
    closes the loop is the clerk the accountant replied to. A live status would
    be `DEF-007`'s three green *Connected* chips over nothing.

    ⚠ **THERE IS NO `pending`, AND AN UNANSWERED BATCH IS NOT IN A STATE.** It
    carries `ack_state: null`, which means NOBODY HAS SAID — a different fact
    from *the import is running* and from *it was refused*. `DEF-127` is what
    it costs to spell those the same way, and the CHECK constraint admits NULL
    for exactly that reason.

    A batch id from another tenant answers **404**, never 403: HR-1 makes
    existence itself non-leaking, and the service refuses it as an unknown batch
    under RLS — byte-identical to a batch that never existed.
    """
    require_tenant(request)
    payload = request.data if isinstance(request.data, dict) else {}
    state = str(payload.get("state") or "").strip()
    if state == "":
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.export.ack_state_required",
            field_errors=[{"field": "state", "code": errors.VAL_REQUIRED}],
        )
    acknowledged_at = _moment(
        payload, "acknowledged_at", message_key="ledger.export.ack_at_required"
    )
    try:
        row = exports.record_acknowledgement(
            request.user,
            batch_id=batch_id,
            state=state,
            acknowledged_at=acknowledged_at,
            reference=payload.get("reference"),
            note=payload.get("note"),
        )
    except exports.ExportError as refusal:
        # ⚠ **TWO DIFFERENT REFUSALS, TWO DIFFERENT CODES.** An unknown batch is
        # a 404 (existence does not leak); an unrecognised STATE is the caller's
        # field to fix and is a 422 naming it. Collapsing them would tell a
        # clerk who typed a wrong word that the batch does not exist.
        if "is not one of this tenant's batches" in str(refusal):
            raise errors.NotFoundError() from refusal
        raise errors.ValidationError(
            errors.VAL_INVALID,
            message_key="ledger.export.ack_state_unknown",
            field_errors=[{"field": "state", "code": errors.VAL_INVALID}],
            params={"detail": str(refusal)},
        ) from refusal
    return Response(_batch_dict(row))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def export_drill_back(request: Any, batch_id: str) -> Response:
    """US-LED-016 TC-3 — *"what is the 506.31?"* answered in dimensioned lines.

    Param: `code`, the GL account code of the exported figure.

    The figure is looked up in the STORED payload and the lines are read for the
    BATCH'S OWN window, so a drill-back proves what was HANDED OVER rather than
    what the books say now — which is exactly the question an auditor holding the
    ERP's copy is asking.

    A batch id from another tenant answers **404**, never 403: HR-1 makes
    existence itself non-leaking, and `exports.drill_back` refuses it as an
    unknown batch under RLS.
    """
    require_tenant(request)
    code = request.query_params.get("code")
    if code is None or str(code).strip() == "":
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.export.drill_code_required",
            field_errors=[{"field": "code", "code": errors.VAL_REQUIRED}],
        )
    currency = _tenant_currency()
    try:
        result = exports.drill_back(batch_id=batch_id, code=str(code).strip())
    except exports.ExportError as refusal:
        raise errors.NotFoundError() from refusal
    return Response(
        {
            "batch_id": result["batch_id"],
            "code": result["code"],
            "currency": currency,
            "exported": [
                {
                    "code": row.get("code"),
                    "name": row.get("name"),
                    "debit": row.get("debit"),
                    "credit": row.get("credit"),
                    "amount": row.get("amount"),
                    "source": row.get("source"),
                }
                for row in result["exported"]
            ],
            "lines": [
                {
                    "entry_id": line["entry_id"],
                    "je_number": line["je_number"],
                    "entry_date": wire.day(line["entry_date"]),
                    "side": line["side"],
                    "amount": wire.money(line["amount"]),
                    "currency": currency,
                    "service_id": line["service_id"],
                    "account_id": line["account_id"],
                    "premises_id": line["premises_id"],
                    "source_type": line["source_type"],
                    "source_id": line["source_id"],
                }
                for line in result["lines"]
            ],
        }
    )


#: `P4.9` — the accounting connection's *Keep files for*, in months.
def _retention_months() -> int | None:
    """The tenant's retention window, or `None` when they have not set one.

    ⚠ **IT FAILS OPEN, AND THAT IS THE WHOLE DESIGN.** Every way this read can
    go wrong — no integrations grid, no accounting card, a connection that was
    never set up, a settings read that raises — answers `None`, which means *no
    window* and therefore *serve the file*, which is what every tenant has had
    since hand-overs existed. **A finance download must not stop working
    because a settings read failed**, and that is the same reasoning
    `CloseExportPage.savedExportTarget` records about the picker it decorates.

    ⚠ **THIS GOVERNS THE DOWNLOAD AND NOT A DELETION.** The stored payload is
    kept; what expires is our willingness to re-serve the file. Purging a
    hand-over's payload is a records decision nobody has taken and a sweep
    nobody has built — `OQ-LED-12654` carries that half, and the manifest, this
    function and the screen all say the same thing, because a setting that
    implied a deletion it does not perform would be a privacy claim this
    product cannot keep.
    """
    try:
        from apps.integrations import selectors as integration_selectors  # noqa: PLC0415

        card = integration_selectors.provider_card(
            core_tenancy.current_tenant_id(), "accounting_file"
        )
    except Exception:  # noqa: BLE001 — every failure is "no window"; see above
        return None
    connection = (card or {}).get("connection") or {}
    raw = str((connection.get("settings") or {}).get("retention_months") or "").strip()
    if not raw.isdigit():
        return None
    months = int(raw)
    return months if months > 0 else None


def _refuse_past_retention(batch: Any) -> None:
    """Refuse a file the tenant asked us to stop serving, in their own number."""
    months = _retention_months()
    if months is None or batch.created_at is None:
        return
    # Months as 30 days is an APPROXIMATION and it is named rather than hidden:
    # the setting is a policy in months and the comparison is a date, so some
    # rounding is unavoidable. It rounds in the tenant's favour — a 12-month
    # window serves for 360 days rather than refusing early — because refusing
    # a file a day sooner than the policy says is the failure a clerk notices
    # and cannot act on.
    cutoff = timezone.now() - timedelta(days=30 * months)
    if batch.created_at >= cutoff:
        return
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-LED-004 · BR-INT-010",
        message_key="ledger.export.past_retention",
        params={"months": months},
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def export_batch_file(request: Any, batch_id: str) -> Any:
    """`P4.2` — the FILE of a recorded hand-over. The re-download door.

    `BR-LED-004`'s refusal of a second export says so in as many words: *"The
    ratified door is to RE-DOWNLOAD the recorded batch"*, and until today that
    door opened onto nothing — `apps/ledger/exports.py` said *"No file is
    written and nothing is sent"* and the hand-over history drew **Not
    written** in the File column.

    **The bytes are re-derived from the batch's FROZEN payload on every
    request** (`apps/ledger/export_files.render`), which is what makes `J19`
    step 7's hash-stability true by construction: there is one thing in the
    world the file comes from, so two downloads cannot differ, and
    `US-LED-006` TC-4's later ref edit cannot reach a batch already sent
    (`BR-TEN-020`, CLAUDE.md rule 4).

    **A batch id from another tenant answers 404**, never 403 — the lookup is
    an ordinary RLS-scoped query, so the row is not hidden from the answer, it
    is not in the set the answer is computed from (HR-1).

    ⚠ **`X-Cost-Rows-Omitted` IS NOT A DETAIL.** The three vendor targets carry
    the journal rows only, because an import file must foot and `BR-LED-039`'s
    cost section deliberately does not (`US-LED-021` TC-7). The header states
    how many rows were left out so *"seven rows"* and *"seven of nine rows"*
    can never read the same; it is `0` on CSV, which carries everything.

    ⚠ **IT HONOURS THE TENANT'S RETENTION WINDOW SINCE `P4.9`** — the *Keep
    files for* setting on the accounting connection. Past the window the file is
    refused with the tenant's own number in the sentence. **The payload is NOT
    purged**; see `_retention_months` for why that half is a question rather
    than a feature.
    """
    require_tenant(request)
    batch = models.ExportBatch.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), pk=batch_id
    ).first()
    if batch is None:
        raise errors.NotFoundError()
    _refuse_past_retention(batch)
    record = exports.batch_dict(batch)
    # `batch_dict` deliberately does NOT carry the payload — it is the row a
    # LIST renders, and a history of twelve batches must not ship twelve
    # payloads. The renderer needs it, so it is added here for this one call.
    record["payload"] = list(batch.payload or ())
    try:
        content = export_files.render(record)
    except export_files.ExportFileError as refusal:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-LED-004 · BR-LED-020",
            message_key="ledger.export.file_refused",
            params={"detail": str(refusal)},
        ) from refusal

    core_audit.money_action(
        _actor(request),
        AUDIT_BATCH_DOWNLOADED,
        "export_batch",
        str(batch.pk),
        after={
            "batch_no": record["batch_no"],
            "target": record["target"],
            "content_hash": record["content_hash"],
            "bytes": len(content),
        },
    )
    response = HttpResponse(content, content_type=export_files.media_type(record))
    response["Content-Disposition"] = f'attachment; filename="{export_files.filename(record)}"'
    response["X-Cost-Rows-Omitted"] = str(export_files.omitted_cost_rows(record))
    return response


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def export_extract(request: Any, kind: str) -> Response:
    """BR-LED-004's dimension extracts — by service · premises · authority.

    Params: `from` + `to` (REQUIRED).

    ⚠ **THIS SAID THE BY-PREMISES EXTRACT ANSWERS `available: false` UNTIL
    2026-09-03, AND IT HAS ANSWERED WITH REAL ROWS SINCE 2026-08-16
    (`DEF-2345`, completing `DEF-3382`).** It read: *"the by-premises extract
    answers `available: false` and says what it cannot attribute, because
    `journal_lines.premises_id` is NULL on every line in the product
    (US-LED-002 unbuilt) … an empty table would read as 'no activity this
    period' over 553.69 of billed money."* **US-LED-002 landed on 2026-08-16**:
    `posting._stamped` resolves account → unit → premises at posting time, and
    the extract now carries LE-6's three rows — **500 Main St 247.87 · Oak Grove
    16.42 · Marina Bay 289.40**, footing to the same **553.69** that used to be
    the refusal's measurement. The money did not move; it acquired an address.

    **WHAT IS STILL PASSED THROUGH UNCHANGED, because it is still right:** this
    endpoint derives nothing. `reporting.by_premises_summary` remains the single
    read, refusals and all — a tenant whose chart designates no AR account still
    gets `available: false`, and money that lawfully carries no premises is still
    reported beside the table as `unattributed_*` rather than dropped from the
    footer.
    """
    require_tenant(request)
    start, end = _window(request.query_params)
    try:
        result = exports.dimension_extract(kind=kind, period_start=start, period_end=end)
    except exports.ExportError as refusal:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="ledger.export.extract_unknown",
            params={"kind": kind, "detail": str(refusal)},
            field_errors=[{"field": "kind", "code": errors.VAL_UNKNOWN_LOOKUP}],
        ) from refusal
    currency = _tenant_currency()
    if kind == "service":
        return Response(
            {
                "kind": kind,
                "available": True,
                "currency": currency,
                "period": {"start": start.isoformat(), "end": end.isoformat()},
                "rows": [
                    {
                        "service_id": str(row.service_id) if row.service_id else None,
                        "service_code": row.service_code,
                        "usage": wire.money(row.usage),
                        "base_and_fees": wire.money(row.base_and_fees),
                        "total_billed": wire.money(row.total_billed),
                        "currency": currency,
                    }
                    for row in result["rows"]
                ],
            }
        )
    if kind == "authority":
        return Response(
            {"kind": kind, "available": True, **wire.remittance_dict(result, currency=currency)}
        )
    return Response({"kind": kind, **wire.by_premises_dict(result, currency=currency)})


# ═══════════════════════════════════════════════════════════════════════════
# S41 — the WRITE half of the remittance (US-LED-014 TC-3 / TC-5 / TC-6)
# ═══════════════════════════════════════════════════════════════════════════
#: `BR-SHL-031`'s two guards, IMPORTED FROM THE ONE PLACE THAT DECLARES THEM
#: rather than re-typed here. `customers.account_documents` owns the 10 MiB cap
#: and the PDF/PNG/JPG/CSV allowlist, and its own header says the tenant-
#: configurable half is not built — a second copy of two constants is how one of
#: them moves and the other does not.
#:
#: ⚠ **THEY ARE ENFORCED HERE BECAUSE `document_store.store()` DOES NOT ENFORCE
#: THEM.** Read at source rather than trusted (hard-won law 1): `store()`
#: refuses an empty payload, a missing content type and an unknown kind or
#: source, and it measures no bytes and checks no media type.
def _receipt_from(request: Any) -> journal.ReceiptUpload | None:
    """The attached receipt, checked, or `None` when none was attached.

    ⚠ **`None` IS NOT A REFUSAL ANY MORE.** `BR-LED-019` requires the receipt as
    the auditor artefact and this endpoint does NOT make it mandatory, because
    the rule's other half — the confirmation reference — already is, and a
    filing whose receipt arrives by post a week later is an ordinary one. What
    changed on 2026-09-24 is that a receipt can be KEPT; whether every filing
    must have one before it may be recorded was never put to anybody, and
    inventing that gate here would block a clerk from recording a payment they
    have genuinely made.
    """
    from apps.customers.account_documents import ALLOWED_CONTENT_TYPES  # noqa: PLC0415
    from apps.customers.account_documents import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES

    upload = request.FILES.get("receipt") if hasattr(request, "FILES") else None
    if upload is None:
        return None
    raw = str(getattr(upload, "content_type", "") or "").strip().lower()
    # ⚠ `image/jpeg; charset=binary` is a legal header. Compare the MEDIA TYPE,
    # never the whole header, or a browser that adds a parameter gets a 415 for
    # a file that is on the list.
    media_type = raw.split(";")[0].strip()
    if media_type not in ALLOWED_CONTENT_TYPES:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.remittance.receipt_type",
            br_ref="BR-SHL-031",
            params={"content_type": media_type or "unknown",
                    "allowed": ", ".join(ALLOWED_EXTENSIONS)},
            field_errors=[{"field": "receipt", "code": errors.VAL_FORMAT}],
        )
    payload = upload.read()
    if not payload:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.remittance.receipt_empty",
            br_ref="BR-SHL-031",
            field_errors=[{"field": "receipt", "code": errors.VAL_REQUIRED}],
        )
    if len(payload) > MAX_UPLOAD_BYTES:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.remittance.receipt_too_large",
            br_ref="BR-SHL-031",
            params={"bytes": str(len(payload)),
                    "max_mb": str(MAX_UPLOAD_BYTES // (1024 * 1024))},
            field_errors=[{"field": "receipt", "code": errors.VAL_FORMAT}],
        )
    return journal.ReceiptUpload(
        content_type=media_type,
        filename=str(getattr(upload, "name", "") or "receipt"),
        payload=payload,
    )


@api_view(["GET", "POST"])
@parser_classes([MultiPartParser, FormParser, JSONParser])
# ⚠ **THE CLASS ON THE DECORATOR IS THE *READ*'s, AND THE POST RE-CHECKS ITS
# OWN INSIDE** — the same shape `export_batches` uses on one path twenty lines
# up, and for the same reason: two methods on one path get ONE permission class
# and they do not need the same one. `AnyTenantRole` may READ the filing
# history; recording a payment is `AdminOrClerk`, re-checked below, and the
# service's own `@require_role` is still the enforcement.
@permission_classes([AnyTenantRole])
def record_remittance(request: Any) -> Response:
    """POST — record a filing. GET — `P4.11`'s filing history.

    US-LED-014 TC-3 — DR the authority's tax payable / CR cash, balanced.

    Body: `tax_account_id` (the authority's own 2200-nn account — BR-BIL-069
    makes the account the authority's identity in the books), `from`, `to`,
    `amount` (a decimal STRING), `basis` (`billed` or `collected`),
    `confirmation_ref` (REQUIRED — BR-LED-019), `entry_date` and `posted_at`.

    **The amount is the caller's and is never derived here.** It is the figure a
    human read off S41 and actually paid. Deriving it would make the payment
    agree with the report by construction, which is exactly the property that
    hides a wrong report.

    ⚠ **A `receipt` FILE IS ACCEPTED AND KEPT SINCE 2026-09-24 (`P4.3`).** This
    paragraph read *"a receipt file is refused BY NAME … `tax_remittances` is
    not in the schema, so accepting a file and dropping it would leave a clerk
    believing it was kept"* — which was true and is not now. `ledger/0020`
    builds the register and `tenancy/0052` makes `tax_remittance` a document
    source, so the file goes to `stored_documents` against the filing it proves.
    Send it as **multipart**, under the field name `receipt`; a JSON body with
    no file still works exactly as before.

    ⚠ **THE ROLE GATE HERE IS STILL A READING, AND THIS SENTENCE NO LONGER
    LEANS ON THE CLOSE (amended 2026-09-24).** It read *"same flagged role
    reading as the close"*, and the close's reading became a RULING that day
    (PO, *"system admin and clark"*, BR-LED-006 amended) — so a pointer saying
    *same as the close* would now read as *ratified*, which is exactly backwards.

    **Recording a remittance was never put to the PO.** OQ-175 (2026-08-12) was
    about REVERSING a posted entry; 2026-09-24 was about CLOSING A MONTH. Neither
    was about handing money to a tax authority, so `AdminOrClerk` is carried here
    as the reading EP-LED-05 §8 flags, and it **RETURNS TO THE AGENDA**. A
    signature covers only what was shown. `journal.ROLE_GATE_IS_THE_API_HALF` and
    this docstring carry it rather than treating it as ratified.
    """
    require_tenant(request)
    if request.method == "GET":
        return _filing_history(request)

    if not AdminOrClerk().has_permission(request, None):
        # A4 gives the Executive VIEW on this surface and not the payment.
        # Raised as the catalog code rather than returned bare, so BR-AUD-018's
        # attempt row is written by the one handler that writes them all.
        raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-LED-019")

    payload = _payload(request)
    start, end = _window(payload)
    tax_account_id = payload.get("tax_account_id")
    if tax_account_id is None or str(tax_account_id).strip() == "":
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.remittance.account_required",
            field_errors=[{"field": "tax_account_id", "code": errors.VAL_REQUIRED}],
        )
    raw_amount = payload.get("amount")
    if raw_amount is None or str(raw_amount).strip() == "":
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.remittance.amount_required",
            field_errors=[{"field": "amount", "code": errors.VAL_REQUIRED}],
        )
    if isinstance(raw_amount, float):
        # CLAUDE.md rule 2 at the door. A JSON float has ALREADY lost digits by
        # the time it reaches here, so it is refused rather than converted — a
        # conversion hides the place where money became binary.
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.remittance.amount_invalid",
            field_errors=[{"field": "amount", "code": errors.VAL_FORMAT}],
        )
    try:
        amount = Decimal(str(raw_amount))
    except (InvalidOperation, TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.remittance.amount_invalid",
            field_errors=[{"field": "amount", "code": errors.VAL_FORMAT}],
        ) from problem
    basis = _choice(
        payload,
        "basis",
        journal.REMITTING_BASES,
        default=None,
        message_key="ledger.remittance.basis_required",
    )
    confirmation_ref = payload.get("confirmation_ref")
    if confirmation_ref is None or str(confirmation_ref).strip() == "":
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.remittance.confirmation_required",
            field_errors=[{"field": "confirmation_ref", "code": errors.VAL_REQUIRED}],
        )
    entry_date = _date_value(payload.get("entry_date") or end.isoformat(), "entry_date")
    posted_at = _moment(payload, "posted_at", message_key="ledger.remittance.posted_at_required")

    try:
        result = journal.record_tax_remittance(
            tax_account_id=str(tax_account_id).strip(),
            period_start=start,
            period_end=end,
            amount=amount,
            basis=basis,
            confirmation_ref=str(confirmation_ref).strip(),
            entry_date=entry_date,
            posted_at=posted_at,
            actor=_actor(request),
            receipt=_receipt_from(request),
        )
    except journal.JournalActionError as refusal:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-LED-002 · BR-LED-019",
            message_key="ledger.remittance.refused",
            params={"detail": str(refusal)},
        ) from refusal
    return Response(
        {
            "entry_id": result.entry_id,
            "created": result.created,
            "tax_account_id": result.tax_account_id,
            "tax_account_code": result.tax_account_code,
            "amount": wire.money(result.amount),
            "currency": _tenant_currency(),
            "basis": result.basis,
            "confirmation_ref": result.confirmation_ref,
            "period": {
                "start": result.period[0].isoformat(),
                "end": result.period[1].isoformat(),
            },
            # `P4.4` / `P4.3` — the filing row, and the receipt if one came.
            "remittance_id": result.remittance_id,
            "receipt_document_id": result.receipt_document_id,
            # ⚠ **THIS USED TO CARRY TWO ENTRIES ON EVERY SINGLE RESPONSE** —
            # `remittance_receipt_attachment_has_no_column` and
            # `tax_remittances_register_not_built`. Both are DELETED rather than
            # emptied (B14 rule 33), and their keys are retired from all eleven
            # catalogues in the same commit.
            "unavailable": wire.gaps(result.unavailable),
        },
        status=201,
    )


# ═══════════════════════════════════════════════════════════════════════════
# `P4.11` — 4·1's SECOND PANEL: what you have already PAID each authority
# ═══════════════════════════════════════════════════════════════════════════
def _filing_history(request: Any) -> Response:
    """`P4.11` — the filing history — `tax_remittances`, newest first.

    Finance blueprint p058 records the gap this closes in one line: **"you can
    record a tax payment and never see it again."** `POST /finance/taxes/
    remittances` existed and there was **no GET and no table**, so a finance
    officer asked *"did we pay Bexar County in August?"* left Finance, opened
    the journal and filtered by source — *"which works, because the entry is
    stamped `SOURCE_REMITTANCE`, but only if you know"*. And **owed and paid
    never appeared on the same screen**, which is the one comparison tab 4
    exists to make.

    Params: `from` + `to` bound `paid_on` (optional — both or neither).

    ⚠ **FILINGS RECORDED BEFORE `ledger/0020` ARE NOT IN THIS TABLE AND THE
    RESPONSE SAYS SO WITH A NUMBER.** Every remittance this product recorded
    before 2026-09-24 posted a journal entry and nothing else, so it has no
    register row and cannot grow one: the confirmation reference survives only
    on the entry memo and in `audit_log`, which is pruned. `journal_only` counts
    those entries and the screen states the count rather than showing a shorter
    list that looks complete. **A declared blind spot with no number beside it
    is indistinguishable from an empty one** (hard-won law 7), and that is
    exactly what this column is for.

    ⚠ **THIS IS NOT WHERE `REMITTED` COMES FROM.** 4·1's own table reads that
    out of the BOOKS (`reporting.remittance_by_authority` sums
    remittance-sourced debits per 2200-nn account) and goes on doing so —
    `BR-REP-002` makes the books the number that has to be right. Two
    independent totals of one fact is how the two panels on this screen would
    come to disagree.
    """
    require_tenant(request)
    tenant_id = core_tenancy.current_tenant_id()
    rows = (
        models.TaxRemittance.objects.filter(tenant_id=tenant_id)
        .select_related("tax_account", "journal_entry")
        .order_by("-paid_on", "-created_at")
    )
    params = request.query_params
    if str(params.get("from") or "").strip() and str(params.get("to") or "").strip():
        start, end = _window(params)
        rows = rows.filter(paid_on__gte=start, paid_on__lte=end)

    # Every filing's receipts, in ONE read rather than one per row.
    from apps.tenancy import document_models, document_store  # noqa: PLC0415

    listed = list(rows)
    receipts: dict[str, list[dict[str, Any]]] = {}
    for record in listed:
        refs = document_store.for_source(
            source_type=document_models.SOURCE_TAX_REMITTANCE, source_id=record.pk
        )
        if refs:
            receipts[str(record.pk)] = [
                {"document_id": str(ref.id), "name": ref.display_name} for ref in refs
            ]

    # The pre-register filings, COUNTED. See the docstring.
    journal_only = (
        models.JournalEntry.objects.filter(
            tenant_id=tenant_id, source_type=journal.SOURCE_REMITTANCE
        )
        .exclude(pk__in=[record.journal_entry_id for record in listed])
        .count()
    )
    return Response(
        {
            "count": len(listed),
            "currency": _tenant_currency(),
            "rows": [
                {
                    # B14 rule 31 — no database id is ever the VISIBLE value of
                    # a field. `id` rides for the drill-back and the receipt
                    # link; what the screen draws is the authority's NAME and
                    # the entry's NUMBER.
                    "id": str(record.pk),
                    "authority_code": record.tax_account.code,
                    "authority": record.tax_account.name,
                    "period": {
                        "start": record.period_start.isoformat(),
                        "end": record.period_end.isoformat(),
                    },
                    "paid_on": record.paid_on.isoformat(),
                    "amount": wire.money(record.amount),
                    "currency": record.currency,
                    "basis": record.basis,
                    "confirmation_ref": record.confirmation_ref,
                    "entry_id": str(record.journal_entry_id),
                    # NULL until the tenant seeds the `journal_entry` series
                    # (BR-LED-021). Nothing composes one — the entry's identity
                    # is its id, not its printed name.
                    "entry_no": record.journal_entry.number,
                    "receipts": receipts.get(str(record.pk), []),
                }
                for record in listed
            ],
            "journal_only": journal_only,
        }
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def remittance_receipt(request: Any, remittance_id: str) -> Any:
    """`P4.3` — the filing receipt, followed as an ordinary link.

    ⚠ **IT REDIRECTS RATHER THAN RETURNING A URL IN A BODY, AND THAT IS THE
    WHOLE REASON THIS VIEW EXISTS.** `GET /accounts/{id}/documents/{docId}`
    answers `{url: …}` and has **no caller anywhere in the front end** — because
    a screen that fetches a link and then opens it is fighting the browser's
    popup blocker: the window has to be opened synchronously in the click, and
    the URL only arrives after an await. So this one answers **302** and the
    cell is a plain `<a download>`: the session cookie authorises the redirect,
    the browser saves the file, and no JavaScript is involved at all.

    ⚠ **THE ROW IS RESOLVED UNDER THIS TENANT FIRST AND THE URL IS MINTED
    SECOND.** The same order `account_documents.document_link` uses, for the
    same reason: a link is never issued for a document the caller could not have
    found. Another utility asking for this filing gets a 404 — the same answer
    as for one that never existed (HR-1, BR-TEN-003).

    ⚠ **THE LINK IT REDIRECTS TO IS A BEARER TOKEN**, minted at
    `document_storage.url_ttl_seconds()` and capped at four hours by the PO
    ruling of 2026-08-30. Whoever holds it reads this one file with no session
    until it expires; it cannot be used to find another.
    """
    require_tenant(request)
    tenant_id = core_tenancy.current_tenant_id()
    filing = models.TaxRemittance.objects.filter(
        tenant_id=tenant_id, pk=remittance_id
    ).first()
    if filing is None:
        raise errors.NotFoundError()

    from apps.tenancy import document_models, document_store  # noqa: PLC0415

    refs = document_store.for_source(
        source_type=document_models.SOURCE_TAX_REMITTANCE, source_id=filing.pk
    )
    if not refs:
        # A filing with no receipt is LAWFUL and common — the paper arrives a
        # week later. 404 rather than an empty 200, because the caller asked for
        # a file and there is none; the SCREEN already draws the absence with
        # its reason and never renders this link in that case.
        raise errors.NotFoundError()
    return HttpResponseRedirect(document_store.download_url(refs[0].id))


urlpatterns = [
    # The period is a WINDOW, not an id — see the module header for why 11b
    # §2.10's `{p}` segment cannot exist while BR-TEN-022 stores no period.
    path("finance/tie-outs", tie_outs),
    path("finance/close-checklist", close_checklist),
    path("finance/periods", periods),
    path("finance/periods/close", close_period),
    path("finance/periods/reopen", reopen_period),
    path("finance/export/preview", export_preview),
    path("finance/export/batches", export_batches),
    path("finance/export/batches/<str:batch_id>/acknowledge", export_batch_acknowledge),
    path("finance/export/batches/<str:batch_id>/drill-back", export_drill_back),
    path("finance/export/batches/<str:batch_id>/file", export_batch_file),
    path("finance/export/extracts/<str:kind>", export_extract),
    # ⚠ **ONE PATH, TWO METHODS, TWO VIEWS — and that is a Django routing
    # constraint rather than a choice.** `record_remittance` is POST-only and
    # `remittances` is GET-only, so the path resolves to whichever declares the
    # method; DRF answers 405 for the other. Written as two functions because
    # they have different permission classes: AnyTenantRole may READ the filing
    # history and only AdminOrClerk may record a payment.
    path("finance/taxes/remittances", record_remittance),
    path("finance/taxes/remittances/<str:remittance_id>/receipt", remittance_receipt),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-016@fdc54bf (sources this slice was authored from, in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-05-remittance-close-export.md — US-LED-014 §1-§8 + US-LED-015 §1-§8 + US-LED-016 §1-§8 — · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-002/004/006/013/014/017/018/019 · 08-qa/01-e2e/journeys/J19-month-end-close.md steps 1-7 · 04-docs/01-spec/11b-api-audit.md §2.10 · 12-governance/10-defect-log.csv DEF-112 + DEF-095 + DEF-099)
# generated: 2026-08-15 by story-coder (DEF-112 lane — the API half the close and export lanes each recorded as `D=deferred`)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended; G7 glob REPORTED, not self-added)
# gates: RED-PROVED FIRST — every path answered `django.urls.exceptions.Resolver404` before this file was included; the verbatim failures are in the lane report and in the human-review-ledger rows. ruff✔ black✔ · pytest tests/test_us_led_016_finance_api.py · pytest tests -m isolation✔ · run_gates✔ · openapi/schema.json REGENERATED (BE-11 TC05 diffs it)
# exceptions: (1) **the period is a WINDOW (`from`+`to`), not 11b §2.10's `{p}` path segment** — BR-TEN-022 computes periods and stores none, so there is no id; REPORTED as a deviation rather than a surrogate id minted · (2) `closed_at` / `reopened_at` / `created_at` / `posted_at` are REQUIRED body inputs (BR-TEN-043) — this file reads no clock, so a browser supplies the moment and a retry stamps the same one · (3) the CLOSE and REMITTANCE role gates are the OQ-175 READING (that ruling was put to the PO about REVERSING a posted entry); `close.ROLE_GATE_IS_A_READING` rides every close response and both docstrings say so. REOPEN's System-Admin gate IS separately ruled · (4) an unbalanced period refuses the export with **SYS-DRIFT (500)**, not a 422: the B12 §3 catalog puts BR-LED-007 on that code, and unbalanced books mean a posting-service bypass rather than a field a clerk can fix · (5) NO FILE IS WRITTEN and nothing is SENT — BR-LED-020 makes v1 a file/batch export and this serves the RECORDED BATCH and its stored payload, which is what a file renders from. The IS-11 streamed download and the S43 email are still other lanes' · (6) `POST /finance/export/batches` re-checks `AdminOrClerk` INSIDE the view because the route serves GET (any role) and POST (admin/clerk) on one path; the service `@require_role` is still the enforcement · (7) the drill-back answers 404 for an unknown or cross-tenant batch — HR-1 makes existence non-leaking, so a foreign batch and a missing one are byte-identical
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
