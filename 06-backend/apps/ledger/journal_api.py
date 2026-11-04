# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-011 (manual JE: draft → post lifecycle, three types,
#           balanced at post — TC-1 the draft, TC-2 the post, TC-4 the
#           unbalanced entry and the empty memo, TC-6 the deleted draft,
#           TC-7 another tenant's entry) ·
#           US-LED-012 (accrual auto-reverse: day 1 of the next period, linked
#           both ways — TC-1 the mirror, TC-3 the Links column, TC-5 no
#           suppress path) ·
#           US-LED-013 (the posted-JE "edit" = one-click reverse + repost)
#           Screens: S57 · S56
# Rules:    BR-LED-003 (drafts freely editable/deletable before post; BALANCED
#           required at post; a memo required; posted = immutable forever;
#           System Admin or Billing Clerk per the PO's closure of OQ-175 on
#           2026-08-12 — Executive may not) · BR-LED-005 (an accrual
#           auto-reverses on day 1 of the next period, linked BOTH ways) ·
#           BR-LED-021 (the `JE-` series, stamped AT POST) · BR-LED-001
#           (source_type `manual_je` on every line) · BR-LED-012 (the journal
#           list's capability row, which these actions are the Row actions of) ·
#           BR-LED-015 (draft / post / delete all audit) · BR-TEN-038 (a date
#           in a closed period auto-forwards) · BR-TEN-043 (event time is an
#           INPUT — there is no clock in this file) · CLAUDE.md rule 1 (tenant
#           scoping) · rule 2 (money is a decimal string + CHAR(3), never a
#           float) · rule 4 (a posted entry is never updated or deleted) ·
#           rule 5 (only the posting service writes journal lines — nothing
#           here writes one) · rule 7 (every money action audits)
# Golden:   LE-4 — a Sep 30 accrual DR 1210 500.00 / CR 4100 500.00 takes an
#           Oct 1 mirror DR 4100 500.00 / CR 1210 500.00, linked both ways
# Tests:    06-backend/tests/test_us_led_011_journal_api.py
# Impacts:  config/urls.py inclusion (`urlpatterns` exported here) ·
#           apps/ledger/manual_je.py + apps/ledger/journal.py (the engines this
#           surface calls; neither is modified) ·
#           07-frontend/src/features/ledger/JournalEntryModal.tsx (S57) and
#           GeneralLedgerPage.tsx (S56's journal list, whose Row actions these
#           are) · 06-backend/openapi/schema.json (BE-11 TC05)
# ───────────────────────────────────────────────────────
"""S57 — the manual journal entry, and the accrual that reverses itself, as HTTP.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this is the surface through which a human
puts money into the books by hand, which is the 🔒 sensitive path CLAUDE.md
names (ledger posting). AI-authored 2026-08-16 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

════════════════════════════════════════════════════════════════════════════
THIS FILE WRITES NO JOURNAL ROW, AND NEITHER DOES THE MODULE BELOW IT
════════════════════════════════════════════════════════════════════════════
`apps/ledger/manual_je.py` says it in capitals and it is true one layer up too:
every insert goes through `apps/ledger/posting.py`, the sole writer (CLAUDE.md
rule 5), and `ledger/0004`'s trigger makes that structural rather than a
promise. There is no ORM here at all (G6 greps every `*_api.py` for a model
manager), no arithmetic on a money value, and no clock.

════════════════════════════════════════════════════════════════════════════
WHY THE PATHS ARE NOT THE ONES 11b §2.10 NAMES — and it is not a preference
════════════════════════════════════════════════════════════════════════════
11b §2.10 names `POST /ledger/journal-entries`. **That exact path is already
registered by `apps/ledger/api.py` as a GET-only route**, and Django's resolver
matches on URL and NOT on method: registering it a second time here would
shadow the S56 journal list with a POST-only view, and registering it first
would do the same in the other direction. `apps/ledger/api.py`'s own docstring
turns that collision into a guarantee it relies on — *"NO WRITE VERB EXISTS ON
ANY PATH IN THIS FILE … a forged POST, PUT, PATCH or DELETE is refused by the
ROUTER with a 405 before any view runs"* — and taking the path back would retire
that guarantee silently.

So the draft write lands one segment deeper, at `POST /ledger/journal-entries/
drafts`, and every id-scoped route is unaffected because `/ledger/journal-entries
/{id}` never collided with `/ledger/journal-entries` in the first place. The
deviation is REPORTED in the trailer, not hidden. This is the same shape
`apps/ledger/finance_api.py` already uses for `POST /finance/taxes/remittances`
beside the GET-only `finance/taxes`.

════════════════════════════════════════════════════════════════════════════
WHAT IS SERVED
════════════════════════════════════════════════════════════════════════════
    POST   /ledger/journal-entries/drafts        save (create or update) a draft
    DELETE /ledger/journal-entries/{id}          delete a draft — never a post
    POST   /ledger/journal-entries/{id}/post     BR-LED-003's Post entry ✓
    POST   /ledger/journal-entries/{id}/reverse  US-LED-013's one-click edit
    GET    /ledger/accruals                      US-LED-012's overdue mirrors
    POST   /ledger/accruals/auto-reverse         the idempotent day-1 sweep

════════════════════════════════════════════════════════════════════════════
THE BALANCE RULE LIVES IN THREE PLACES AND THE SCREEN IS THE WEAKEST OF THEM
════════════════════════════════════════════════════════════════════════════
S57's *Post entry ✓* is disabled while the entry does not foot — which is what
US-LED-011 asks for, and which is a COURTESY. The enforcement is here and
below: `manual_je.post_manual_je` asserts the balance against the lines that
actually exist, and `ledger/0002`'s DEFERRED trigger asserts it again at COMMIT
inside the database. A forged request that skips the screen is refused by the
second and, if that were ever wrong, by the third. Nothing about the rule
depends on a button being grey.

Drafts are the deliberate exception and BR-LED-003 is explicit about it: a
draft may be saved unbalanced, because a clerk building a six-line reclass is
unbalanced between every keystroke. `gap` comes back on every save and is the
figure S57's *Must balance* footer renders.

════════════════════════════════════════════════════════════════════════════
A POSTED ENTRY IS NEVER EDITED, AND THE SURFACE SAYS SO IN ITS SHAPE
════════════════════════════════════════════════════════════════════════════
There is no PATCH on an entry anywhere in this file, for the same reason
`apps/ledger/api.py` serves no write at all: hard rule 4 makes a posted entry
immutable forever, and offering an edit that will be refused teaches a clerk
that the product is unreliable rather than that the books are. The ONLY "edit"
is `POST .../reverse`, which writes two new entries and hands back the prefilled
correction (LE-8: 250.00 − 250.00 + 205.00 = **205.00**, three entries standing).
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.ledger import journal, manual_je, models, posting, reporting, wire
from apps.tenancy import selectors as tenancy_selectors
from core import errors
from core.pagination import parse_list_params, prepaged
from core.permissions import (
    AdminOrClerk,
    AnyTenantRole,
    JournalEntryReadAnyDeleteAdminOrClerk,
)
from core.tenancy import require_tenant


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="ledger.payload_not_object")
    return data


def _actor(request: Any) -> Any:
    """WHO typed the entry, from the SESSION — never from the body (rule 7)."""
    return getattr(request, "user", None)


def _date_value(raw: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.report.date_invalid",
            field_errors=[{"field": field, "code": errors.VAL_FORMAT}],
        ) from problem


def _required_date(payload: dict[str, Any], field: str) -> date:
    raw = payload.get(field)
    if raw is None or str(raw).strip() == "":
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.je.date_required",
            field_errors=[{"field": field, "code": errors.VAL_REQUIRED}],
        )
    return _date_value(raw, field)


def _moment(payload: dict[str, Any], name: str = "posted_at") -> datetime:
    """The instant the entry entered the books — an INPUT (BR-TEN-043, G6).

    A double-submitted *Post entry ✓* must stamp ONE moment. A server reading
    its own clock would stamp two and record two different histories of one act,
    which is the whole reason `posted_at` is a parameter of `post_manual_je`
    rather than a `now()` inside it.
    """
    raw = payload.get(name)
    if raw is None or str(raw).strip() == "":
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.je.posted_at_required",
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


def _amount(raw: Any, index: int) -> Decimal:
    """One typed money value → `Decimal`, or a refusal naming the row.

    `Decimal(str(...))` and never `float(...)`: CLAUDE.md rule 2, and the one
    place a float looks harmless is exactly where it gets in. A JSON number
    reaching here as a Python float would already have lost the value before
    this line ran, which is why the wire contract is a decimal STRING and why
    a non-string is refused rather than coerced.
    """
    if isinstance(raw, float):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.je.amount_must_be_string",
            params={"line": index + 1},
            field_errors=[{"field": f"lines[{index}].amount", "code": errors.VAL_FORMAT}],
        )
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.je.amount_invalid",
            params={"line": index + 1},
            field_errors=[{"field": f"lines[{index}].amount", "code": errors.VAL_FORMAT}],
        ) from problem
    if value < 0:
        # A NEGATIVE DEBIT IS A CREDIT WEARING THE WRONG WORD. `journal_lines`
        # carries `amount >= 0` and the SIDE says which way the money went; a
        # negative here would balance a pair arithmetically while making the
        # trial balance's own Debit column meaningless.
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="ledger.je.amount_negative",
            params={"line": index + 1},
            field_errors=[{"field": f"lines[{index}].amount", "code": errors.VAL_RANGE}],
        )
    return value


def _lines(payload: dict[str, Any]) -> tuple[manual_je.ManualLine, ...]:
    """S57's GL rows. Every one carries an account, a side and an amount.

    A row with neither a debit nor a credit typed is DROPPED rather than
    refused: S57 opens with two empty rows and a *+ Add line* button, so a
    three-line entry always arrives with blank rows behind it and refusing them
    would make the modal unusable. A row with an ACCOUNT and no amount is a
    different thing — somebody chose the account and has not finished — and it
    is refused by name.
    """
    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, list):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.je.lines_required",
            field_errors=[{"field": "lines", "code": errors.VAL_REQUIRED}],
        )
    rows: list[manual_je.ManualLine] = []
    for index, raw in enumerate(raw_lines):
        if not isinstance(raw, dict):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="ledger.je.line_not_object",
                params={"line": index + 1},
                field_errors=[{"field": f"lines[{index}]", "code": errors.VAL_FORMAT}],
            )
        account_id = str(raw.get("ledger_account_id") or "").strip()
        amount_raw = raw.get("amount")
        blank_amount = amount_raw is None or str(amount_raw).strip() == ""
        if not account_id and blank_amount:
            continue  # an untouched row of the modal
        if not account_id:
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="ledger.je.line_account_required",
                params={"line": index + 1},
                field_errors=[
                    {"field": f"lines[{index}].ledger_account_id", "code": errors.VAL_REQUIRED}
                ],
            )
        if blank_amount:
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="ledger.je.line_amount_required",
                params={"line": index + 1},
                field_errors=[{"field": f"lines[{index}].amount", "code": errors.VAL_REQUIRED}],
            )
        side = str(raw.get("side") or "").strip()
        if side not in models.JOURNAL_SIDES:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="ledger.je.side_unknown",
                params={"line": index + 1, "sides": ", ".join(models.JOURNAL_SIDES)},
                field_errors=[{"field": f"lines[{index}].side", "code": errors.VAL_UNKNOWN_LOOKUP}],
            )
        rows.append(
            manual_je.ManualLine(
                ledger_account_id=account_id, side=side, amount=_amount(amount_raw, index)
            )
        )
    if not rows:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.je.lines_required",
            field_errors=[{"field": "lines", "code": errors.VAL_REQUIRED}],
        )
    return tuple(rows)


def _refused(problem: Exception) -> errors.ApiError:
    """A ledger refusal → the catalog envelope, with the service's sentence.

    `ManualJournalError` and `PostingError` are PROSE. Classifying them by
    searching their text would bind this file to another module's sentences and
    the first reworded refusal would silently change a 409 into a 500 — the
    reasoning `apps/ledger/finance_api._close_refused` records. Here there is no
    published read that re-answers the same question (the balance is a property
    of rows the request just supplied), so the class itself is the classifier:
    every refusal from either engine is a BUSINESS-STATE refusal, 409, with the
    engine's own sentence carried in `params.detail` for the trail.
    """
    return errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-LED-003",
        message_key="ledger.je.refused",
        params={"detail": str(problem)},
    )


def _draft_dict(result: manual_je.ManualDraftResult, currency: str | None) -> dict[str, Any]:
    return {
        "entry_id": result.entry_id,
        "created": result.created,
        "entry_date": wire.day(result.entry_date),
        "type": result.entry_type,
        "status": models.JE_DRAFT,
        "currency": currency,
        "debits": wire.money(result.debits),
        "credits": wire.money(result.credits),
        "balanced": result.balanced,
        # S57's *Must balance* footer renders THIS. It is the server's figure,
        # not a subtraction the screen performed (BR-SHL-023 / rule 2).
        "gap": wire.money(result.gap),
        "line_count": result.line_count,
        # BR-TEN-038 — a date inside a closed period is FORWARDED, and the note
        # rides back so the modal can say so while it is still open rather than
        # letting the clerk discover it after confirming.
        "date_note": result.date_note,
        "unavailable": wire.gaps(result.unavailable),
    }


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-011 — the draft lifecycle
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["POST"])
@permission_classes([AdminOrClerk])  # PO 2026-08-12 closing OQ-175 — Executive may not
def journal_entry_drafts(request: Any) -> Response:
    """S57's *Save draft* — create, or update the one named by `entry_id`.

    ONE route for both because BR-LED-003 makes them one act: a draft is
    editable until it posts, so "save" is what the modal does every time, and
    two routes would mean a screen deciding which verb its own state deserves.
    """
    require_tenant(request)
    body = _payload(request)
    currency = tenancy_selectors.regional_settings().get("currency")
    try:
        result = manual_je.save_manual_je(
            _actor(request),
            entry_date=_required_date(body, "entry_date"),
            entry_type=str(body.get("type") or models.JE_STANDARD).strip(),
            memo=body.get("memo"),
            lines=_lines(body),
            currency=str(body.get("currency") or currency or "USD"),
            entry_id=body.get("entry_id") or None,
        )
    except (manual_je.ManualJournalError, posting.PostingError) as problem:
        raise _refused(problem) from problem
    return Response(_draft_dict(result, currency), status=201 if result.created else 200)


@api_view(["GET", "DELETE"])
@permission_classes([JournalEntryReadAnyDeleteAdminOrClerk])
def journal_entry_item(request: Any, entry_id: str) -> Response:
    """One entry: OPEN it (GET) or delete a draft (DELETE). Two verbs, one path.

    ════════════════════════════════════════════════════════════════════════
    WHY THE GET IS HERE AND NOT IN `apps/ledger/api.py` WITH THE OTHER READS
    ════════════════════════════════════════════════════════════════════════
    **Django resolves by URL and NOT by method.** `ledger/journal-entries/
    <uuid:entry_id>` is registered in this file, so a second registration of
    the same path in `api.py` would shadow one of the two views entirely —
    the identical constraint that put the draft WRITE at `…/drafts` rather
    than at `11b` §2.10's `POST /ledger/journal-entries`, recorded in this
    module's docstring. The read therefore joins the verb that already owns
    the path, and the ROLE split moves onto a permission class
    (`JournalEntryReadAnyDeleteAdminOrClerk`) so neither verb's gate is
    changed by the other's arrival. `ConnectionsReadAnyWriteAdminOrClerk` is
    the precedent and says so in its own docstring.

    ⚠ **`apps/ledger/api.py`'S "NO WRITE VERB ON ANY PATH IN THIS FILE"
    GUARANTEE IS UNTOUCHED.** It is a statement about THAT file and this is
    not that file; `api.py` already carries writes' neighbours the same way.

    ════════════════════════════════════════════════════════════════════════
    GET — `DEF-LED-6723`, the eye on Finance blueprint p020 item 7
    ════════════════════════════════════════════════════════════════════════
    `11b` §2.10 / A1 S56 name this route and call the screen *"Journal list +
    detail"* with *"lines expand to dimensions"*. It was never served, so the
    Journal's `👁` shipped VISIBLE AND DISABLED with its reason (BR-SHL-025),
    which was the honest build of a true refusal and is no longer true. The
    Product Owner reported it on **v2.351.84**: *"on this screen user is
    unable to see detail screen of Journal entry - we cannot click on eye."*

    **READ-ONLY, AND THE ABSENCE OF AN EDIT IS THE RULE RATHER THAN A GAP.**
    Hard rule 4 makes a posted entry immutable for ever; BR-LED-003 makes the
    one correction a reverse + repost, which writes two NEW entries through the
    posting service. There is no PATCH on this path and there must never be
    one — this file's exception (2) already records why.

    **THE LINES PAGE (`NFR-3`).** `?page` / `?per` slice in SQL and the
    envelope is the one every other list in the product serves. The entry's
    own `debit`, `credit` and `balanced` are over ALL its lines and not over
    the page — computed in the read model, before the slice, for the reason
    stated there.

    ════════════════════════════════════════════════════════════════════════
    DELETE — US-LED-011 TC-6, unchanged
    ════════════════════════════════════════════════════════════════════════
    *"gone without trace in the books"*, audit row kept.

    **A POSTED ENTRY IS NOT DELETABLE AND THIS ROUTE DOES NOT TRY.** The refusal
    comes from `posting.delete_draft`, which checks the status, and from
    `ledger/0007`'s trigger underneath it. Hard rule 4 has no exception for a
    posted entry and needs none for a draft: BR-LED-003 calls a draft
    *worthless* — it sums into no report — so deleting one leaves the books
    byte-identical.
    """
    require_tenant(request)
    if request.method == "GET":
        return _journal_entry_detail(request, entry_id)
    try:
        return Response(manual_je.delete_manual_je(_actor(request), entry_id=entry_id))
    except (manual_je.ManualJournalError, posting.PostingError) as problem:
        raise _refused(problem) from problem


# ⚠ **THE PAGE SIZE IS `core.pagination.clamp_page_size`'S AND IS NOT RESTATED
# HERE.** A11 r2 item 1 owns the `PAGE_SIZES` set; a constant in this file
# naming 50 would be a second copy of a number that lives somewhere else, and
# `CLAUDE.md`'s own lesson is that where a rule restates what a tool does, you
# name the tool. `NFR-5`: it is a DEFAULT and never a maximum.


def _journal_entry_detail(request: Any, entry_id: str) -> Response:
    """The GET half, kept out of the dispatcher so each verb reads as itself."""
    listing = parse_list_params(
        request.query_params,
        allowed_sorts=(),
        default_sort=None,
        default_dir="asc",
    )
    captured: dict[str, Any] = {}
    currency = tenancy_selectors.regional_settings().get("currency")

    def fetch(page_params: Any) -> tuple[list[dict[str, Any]], int]:
        result = reporting.journal_entry_detail(
            entry_id,
            offset=max(page_params.page - 1, 0) * page_params.per,
            limit=page_params.per,
        )
        captured.update(result)
        body = wire.journal_entry_detail_dict(result, currency=currency)
        captured["body"] = body
        return (body["lines"], result["line_total"])

    response = prepaged(request, listing, fetch)
    # Beside the DRF envelope, exactly as `GET /ledger/journal-entries` carries
    # its basis and `GET /payments` its totals. `entry` is the HEADER and its
    # debit/credit/balanced are over the whole entry, NOT over `results`.
    response.data["entry"] = captured["body"]["entry"]
    response.data["currency"] = currency
    response.data["unavailable"] = captured["body"]["unavailable"]
    return response


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def journal_entry_post(request: Any, entry_id: str) -> Response:
    """BR-LED-003's *Post entry ✓* — balanced, memo'd, role-gated, immutable after.

    All three demands are enforced BELOW this line whatever the modal did, and
    the balance is enforced a third time by the database at COMMIT. `posted_at`
    is REQUIRED and is the caller's (BR-TEN-043).

    The response carries the `JE-` number BR-LED-021 stamps at post — **or a
    named reason there is none**. No tenant has the `journal_entry` number
    series seeded yet (`apps.tenancy.services.SERIES_DEFAULTS` has five and this
    is not among them), so an entry posts unnumbered and says
    `JOURNAL_NUMBER_SERIES_NOT_SEEDED` rather than composing a number a second
    allocator would collide with. It is never faked and never blank.
    """
    require_tenant(request)
    body = _payload(request)
    currency = tenancy_selectors.regional_settings().get("currency")
    try:
        result = manual_je.post_manual_je(
            _actor(request), entry_id=entry_id, posted_at=_moment(body)
        )
    except (manual_je.ManualJournalError, posting.PostingError) as problem:
        raise _refused(problem) from problem
    return Response(
        {
            "entry_id": result.entry_id,
            "je_number": result.number,
            "posting_key": result.posting_key,
            "created": result.created,
            "entry_date": wire.day(result.entry_date),
            "status": models.JE_POSTED,
            "currency": currency,
            "debits": wire.money(result.debits),
            "credits": wire.money(result.credits),
            "line_count": result.line_count,
            "date_note": result.date_note,
            "unavailable": wire.gaps(result.unavailable),
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-013 — the ONE lawful "edit" of a posted entry
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["POST"])
@permission_classes([AdminOrClerk])
def journal_entry_reverse(request: Any, entry_id: str) -> Response:
    """LE-8's one click: post the linked mirror, hand back the prefilled draft.

    **THE PREFILLED CORRECTION IS RETURNED, NOT WRITTEN**, and the response says
    so by name (`repost_draft_is_not_persisted`). The screen loads it into S57,
    the clerk corrects the figure, and *Save draft* is what makes it a row —
    which keeps the draft lifecycle in exactly one place.

    A second click returns the FIRST mirror with `mirror_created: false`. That
    is the correct outcome of a double-submitted form, not an error: the
    posting key is one string per original, forever.
    """
    require_tenant(request)
    body = _payload(request)
    reason = str(body.get("reason") or "").strip()
    if not reason:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.je.reverse_reason_required",
            field_errors=[{"field": "reason", "code": errors.VAL_REQUIRED}],
        )
    currency = tenancy_selectors.regional_settings().get("currency")
    try:
        result = journal.reverse_and_repost(
            entry_id,
            reason=reason,
            entry_date=_required_date(body, "entry_date"),
            posted_at=_moment(body),
            actor=_actor(request),
        )
    except (journal.JournalActionError, posting.PostingError) as problem:
        raise _refused(problem) from problem
    return Response(
        {
            "original_entry_id": result.original_entry_id,
            "mirror_entry_id": result.mirror_entry_id,
            "mirror_created": result.mirror_created,
            "reason": result.reason,
            "currency": currency,
            "debits": wire.money(result.debits),
            "credits": wire.money(result.credits),
            "repost_draft": [
                {
                    "ledger_account_id": line.ledger_account_id,
                    "side": line.side,
                    "amount": wire.money(line.amount),
                }
                for line in result.repost_draft
            ],
            "unavailable": wire.gaps(result.unavailable),
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-012 — the accrual auto-reversal (BR-LED-005)
# ═══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def accruals(request: Any) -> Response:
    """Which accruals owe a day-1 mirror as of `as_of`, and when each is due.

    **`as_of` IS REQUIRED AND IS THE CALLER'S** (BR-TEN-043 / gate G6). A read
    that took "today" from the server clock could not be asked about a day the
    host was down, and a catch-up run is the normal case after one was.

    This is the same question `close._accruals_item` asks the month-close
    checklist, through the same function, so the checklist and this panel can
    never disagree about whether October is safe to bill.
    """
    require_tenant(request)
    raw = request.query_params.get("as_of")
    if raw is None or str(raw).strip() == "":
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.accruals.as_of_required",
            field_errors=[{"field": "as_of", "code": errors.VAL_REQUIRED}],
        )
    as_of = _date_value(raw, "as_of")
    currency = tenancy_selectors.regional_settings().get("currency")
    pending = manual_je.pending_accrual_reversals(as_of=as_of)
    return Response(
        {
            "as_of": as_of.isoformat(),
            "currency": currency,
            "rows": [
                {
                    "entry_id": str(entry.pk),
                    "je_number": entry.number,
                    "entry_date": wire.day(entry.entry_date),
                    "memo": entry.memo,
                    # BR-LED-005's own date, from the tenant's fiscal calendar
                    # and never "the first of the next calendar month": a tenant
                    # closing quarterly accrues into a quarter.
                    "reversal_due_on": manual_je.accrual_reversal_due_on(
                        entry.entry_date
                    ).isoformat(),
                    "overdue": True,
                }
                for entry in pending
            ],
            "count": len(pending),
        }
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def accruals_auto_reverse(request: Any) -> Response:
    """BR-LED-005's sweep, run because a human asked. Idempotent by construction.

    A replay writes nothing: the posting key is
    `journal_entry|<accrual id>|auto_reversed`, one string per accrual forever,
    so pressing the button twice produces the same books. Every accrual it
    CONSIDERED comes back, including the ones it skipped — an accrual a human
    already reversed by hand cannot take a second mirror, and reporting that is
    more useful than silently doing nothing (US-LED-012's own posture).

    Both `as_of` and `posted_at` are the caller's (BR-TEN-043).
    """
    require_tenant(request)
    body = _payload(request)
    as_of = _required_date(body, "as_of")
    posted_at = _moment(body)
    currency = tenancy_selectors.regional_settings().get("currency")
    try:
        results = manual_je.run_accrual_auto_reversals(
            as_of=as_of, posted_at=posted_at, actor=_actor(request)
        )
    except (manual_je.ManualJournalError, posting.PostingError) as problem:
        raise _refused(problem) from problem
    return Response(
        {
            "as_of": as_of.isoformat(),
            "currency": currency,
            "rows": [
                {
                    "accrual_entry_id": row.accrual_entry_id,
                    "mirror_entry_id": row.mirror_entry_id,
                    "created": row.created,
                    "due_on": row.due_on.isoformat(),
                    "entry_date": wire.day(row.entry_date),
                    "amount": wire.money(row.amount),
                    "skipped": row.skipped,
                    "date_note": row.date_note,
                }
                for row in results
            ],
            "created": sum(1 for row in results if row.created),
            "considered": len(results),
        }
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def journal_entries_post_batch(request: Any) -> Response:
    """BR-LED-798 — post a whole batch, in full or not at all (`P1.22`).

    PO ruling 2026-09-24 closing `OQ-LED-12630`, option (c): all-or-nothing,
    **and** the batch is checked in full before the first entry is attempted.

    ⚠ **THIS ROUTE EXISTS BECAUSE A CLIENT LOOP CANNOT BE A TRANSACTION, AND
    THAT IS WHAT THE QUESTION DECIDED.** `POST /ledger/journal-entries/{id}/post`
    posts exactly one entry; five of those from a browser are five transactions,
    and the fifth failing leaves the first four irreversibly in the books (hard
    rule 4). The register row said *"doing nothing is choosing (b)"* for exactly
    this reason, and (b) is the option the PO rejected.

    **THE REFUSAL NAMES THE ENTRY.** A batch refused with *"something was
    wrong"* leaves a finance officer opening five drafts to find out which; the
    pre-check reports EVERY problem in one answer, each with its entry id and
    its reason, which is what makes the round trip worth taking.

    ⚠ **A REFUSAL IS A 409 AND NOT A 422**, the same classification
    `journal_entry_post` already makes through `_refused`: the request is
    well-formed and the BOOKS' STATE refuses it.

    `posted_at` is REQUIRED and is the caller's (BR-TEN-043) — one moment for
    the whole batch, so five entries posted together carry one timestamp rather
    than five moments a re-read would have to reconcile.
    """
    require_tenant(request)
    body = _payload(request)
    currency = tenancy_selectors.regional_settings().get("currency")
    raw = body.get("entry_ids")
    if not isinstance(raw, (list, tuple)):
        raw = ()
    try:
        result = manual_je.post_manual_je_batch(
            _actor(request), entry_ids=raw, posted_at=_moment(body)
        )
    except (manual_je.ManualJournalError, posting.PostingError) as problem:
        raise _refused(problem) from problem
    return Response(
        {
            "entry_count": result.entry_count,
            "currency": currency,
            "results": [
                {
                    "entry_id": row.entry_id,
                    "je_number": row.number,
                    "posting_key": row.posting_key,
                    "created": row.created,
                    "entry_date": wire.day(row.entry_date),
                    "status": models.JE_POSTED,
                    "debits": wire.money(row.debits),
                    "credits": wire.money(row.credits),
                    "line_count": row.line_count,
                    "date_note": row.date_note,
                }
                for row in result.results
            ],
            "unavailable": wire.gaps(result.unavailable),
        }
    )


urlpatterns = [
    # `drafts` is one segment deeper than 11b §2.10's `POST /ledger/journal-
    # entries` — see the module docstring. Django resolves by URL, not by
    # method, so the GET-only list route in `apps/ledger/api.py` owns that exact
    # path and its router-level 405 on every write verb is a guarantee that file
    # states in its own docstring.
    path("ledger/journal-entries/drafts", journal_entry_drafts),
    # ⚠ ABOVE the `<uuid:entry_id>` route. The uuid converter would not match
    # `post-batch` today, but a lane widening it to `<str:…>` should not have to
    # discover this ordering by watching a 404 — the DEF-520 shape.
    path("ledger/journal-entries/post-batch", journal_entries_post_batch),
    path("ledger/journal-entries/<uuid:entry_id>", journal_entry_item),
    path("ledger/journal-entries/<uuid:entry_id>/post", journal_entry_post),
    path("ledger/journal-entries/<uuid:entry_id>/reverse", journal_entry_reverse),
    path("ledger/accruals", accruals),
    path("ledger/accruals/auto-reverse", accruals_auto_reverse),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-011@eec4f0e (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-04-manual-je.md — US-LED-011 + US-LED-012 + US-LED-013 — · 04-docs/05-modules/09-ledger/02-business-rules.md · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-4 + LE-8 · 04-docs/01-spec/11b-api-audit.md §2.10; co-packets US-LED-012/US-LED-013, same four sources)
# generated: 2026-08-16 by story-coder (the ledger surface lane — `apps/ledger/manual_je.py` shipped complete on 2026-08-15 with `D=deferred(the S57 endpoints are the API half)` and no human could post a journal entry)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, row in 12-governance/09-human-review-ledger.md)
# gates: RED PROVED FIRST — every path answered `django.urls.exceptions.Resolver404` before this file was included, and the unbalanced post was proved refused on live Postgres; verbatim in the lane report. pytest tests/test_us_led_011_journal_api.py · ruff · black · run_gates · golden 33/33 unmoved
# exceptions: (1) **THE DRAFT WRITE IS AT `POST /ledger/journal-entries/drafts`, NOT 11b §2.10's `POST /ledger/journal-entries`** — Django resolves by URL and not by method, `apps/ledger/api.py` already owns that exact path as a GET-only route, and its docstring makes the router-level 405 on every write verb a guarantee. Registering the path twice would shadow the S56 journal list. Same shape as `POST /finance/taxes/remittances` beside the GET-only `finance/taxes`. REPORTED · (2) there is NO PATCH on an entry anywhere in this file: hard rule 4 makes a posted entry immutable and offering an edit that will be refused teaches a clerk the product is unreliable rather than that the books are. The one "edit" is `POST .../reverse`, two new entries · (3) a manual line carries NO service / premises / account dimension — US-LED-011 §5 maps four modal fields and none is a dimension; `source_type='manual_je'` + `source_id` ARE carried, which is what BR-LED-001 requires unconditionally · (4) the role gate is `AdminOrClerk`, which is the PO's closure of OQ-175 (2026-08-12, *"System Admin and Billing Clerk … Executive may not"*) applied to the manual-JE lifecycle; `manual_je.py` carries that reading as `manual_je_role_gate_is_a_reading_not_a_ruling` on every result and this surface passes it through rather than dropping it · (5) an entry posts with `je_number: null` on every host today — `apps.tenancy.services.SERIES_DEFAULTS` seeds no `journal_entry` series — and the response names the gap rather than composing a number a second allocator would collide with · (6) `POST /ledger/accruals/auto-reverse` is a HUMAN-triggered sweep because this deployment has no job runner (TD-17); it is idempotent by posting key, so the button and a future scheduler cannot double-post
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
