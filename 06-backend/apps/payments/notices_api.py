# ── Trace ──────────────────────────────────────────────
# Change:   CR-138-BRC07 · P4.13 — `POST /collections/notices`. The blueprint's
#           own gap line on 7·1: *"Send a reminder and Send a disconnection
#           notice both need `POST /collections/notices` — which is not
#           mounted; only `collections/run` and `collections/ladder` are."*
#           Screens: S34 (two of six bulk buttons) · 7·3d Send notice
# Rules:    BR-PAY-017 · BR-PAY-029 (reminder/notice are S34 bulk actions) ·
#           BR-PAY-035 / BR-NOT-008 (the tone table) · BR-SHL-025 (who may act,
#           server-enforced) · BR-TEN-043 (the business date is an argument) ·
#           CLAUDE.md hard rule 1 · hard rule 6 · hard rule 7
# Tests:    06-backend/tests/test_cr138_p4_13_collections_notices.py
# Impacts:  config/urls.py inclusion · apps/payments/notices_by_hand.py (the
#           service) · g52_no_door_baseline.txt
# ───────────────────────────────────────────────────────
"""The door on `collections/notices` — the one S34 has been pointing at.

ITS OWN MODULE rather than more lines in `apps/payments/api.py`, on the
`refunds_api` / `reversal_api` / `writeoffs_api` precedent and for hard-won law
11's reason: **a file several lanes edit is where a pathspec commit eats
somebody's work**, and `api.py` is 1,778 lines that `P4.1` is editing in
parallel right now.

THIN BY LAW. The whole of the rule lives in `notices_by_hand.send`; this parses
a body, gates a role and translates a refusal. **No ORM, no figure, no rounding
and no vocabulary in this file.**

═══════════════════════════════════════════════════════════════════════════════
`AdminOrClerk`, AND WHY IT IS NEITHER WIDER NOR NARROWER
═══════════════════════════════════════════════════════════════════════════════
`POST /collections/run` — which advances the SAME ladder over the SAME
selection and posts the SAME letters — is `AdminOrClerk`. A hand send is the
same act with the rung chosen by a person instead of by `decide`, so a
different gate here would mean one of the two doors is wrong. An Executive has
VIEW on payments (A4) and may read the board; they may not post a letter.

Server-enforced, because a screen that hides a control is not an authorisation
(`BR-SHL-025`).
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.payments import notices_by_hand
from apps.payments.exceptions import PaymentRuleError
from core import errors
from core.permissions import AdminOrClerk
from core.tenancy import require_tenant

# The two helpers `apps/payments/api.py` already owns. Imported rather than
# re-implemented: a second `_payload` is a second answer to "what is a body",
# and `_actor` carries US-AUD-010's three-kinds-of-actor rule.
from apps.payments.api import _actor, _payload


def _business_date(payload: dict[str, Any], name: str) -> date:
    """A business date the CALLER names — `BR-TEN-043`, gate `G6`, never a clock.

    REQUIRED. `apps/payments/api._business_date` says the same in full: a
    notice dated by the server is dated in the server's timezone, and the cut
    date printed on a disconnection letter is a date a regulator reads.
    """
    raw = payload.get(name)
    if raw in (None, ""):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.as_of_required",
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError) as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.date_invalid",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


def _optional_date(payload: dict[str, Any], name: str) -> date | None:
    raw = payload.get(name)
    if raw in (None, ""):
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError) as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.date_invalid",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


def _optional_money(payload: dict[str, Any], name: str) -> Decimal | None:
    """A money argument as a Decimal, or absent — **a JSON float is REFUSED.**

    Hard rule 2: money is `NUMERIC(18,6)`, never a binary fraction. Coercing a
    float here would hide the place where money became binary, which is the one
    thing that rule exists to prevent.
    """
    raw = payload.get(name)
    if raw in (None, ""):
        return None
    if isinstance(raw, float):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.amount_invalid",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        )
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.amount_invalid",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


def _as_catalog_refusal(refusal: PaymentRuleError) -> errors.BizError:
    """A service refusal as the SENTENCE a clerk can act on, never a 500.

    ⚠ **ONE CODE — 422 `BIZ_COMPLETENESS` — AND IT IS THE MODULE'S OWN**
    (`apps/payments/api._as_catalog_refusal`, `refunds_api`'s twin). Picking
    among the nine BIZ codes per refusal would be this layer INTERPRETING
    rules it does not own. ⚠ A first draft reached for a `BIZ_RULE_VIOLATION`
    that **does not exist in `core/errors.py`** — so every refusal on this
    door answered **500 SYS-INTERNAL** instead of the sentence, which is the
    exact shape `G32` exists for. Found by running the tests, not by reading.

    The same translation every payments door performs at its own boundary:
    `PaymentRuleError` is not a catalog exception, and an untranslated one
    leaves the router with a 500 where the caller needs the words.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-017",
        message_key="payments.record.refused",
        params={"detail": str(refusal)},
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # the same gate `POST /collections/run` carries
def collections_notices(request: Any) -> Response:
    """`POST /collections/notices` — send ONE rung, by hand, over a selection.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE ROUTE TWO LIVE BUTTONS HAVE BEEN POINTING AT AND NOT REACHING.  ║
    ╚══════════════════════════════════════════════════════════════════════╝
    `OutstandingsTab.tsx` renders *Send a reminder* and *Send a disconnection
    notice* DISABLED with their reason, and the reason names this address. The
    services behind them — `notices.send_reminders`, `send_disconnect_notices`
    and `ladder.step_one` — have been complete and tested since 2026-08-11 and
    2026-09-07; **only the door was missing**, which is the `G25` shape this
    repo has now met four times.

    THE BODY::

        account_ids       the S34 selection — REQUIRED, non-empty
        tone              friendly | firm | final     ─┐ exactly one
        rung              one of BR-PAY-017's four    ─┘ of these two
        as_of             the clerk's business day — REQUIRED, never a clock
        cut_date          optional; defaults inside `step_one` to as_of + 10d
        channels          optional; defaults to ("pdf_print",) — DISCONNECT
                          rungs only. The friendly reminder's channels are
                          the Settings rule's and the customer's
                          (`DEF-PAY-10651`, PO 2026-10-29 ruling 1A)
        balance_floor     optional; the tenant's, passed as `collections/run`
        partial_pause_percent   optional, same
        medical_hold_account_ids  optional — a clinical fact customers owns
        idempotency_key   the form's submit token — REQUIRED (hard rule 6)

    **IT SHARES ONE VOCABULARY WITH THE AUTOMATIC LADDER**, which is the whole
    point and is `BR-PAY-017` in one sentence: *"manual sends use the same tier
    ladder, channels and exclusions as the sequence engine, and advance the same
    state."* The stop conditions are `ladder.decide`'s, the send is
    `ladder.step_one`, the state row is the one shared row, and every skip is
    written to `notice_history`. See `notices_by_hand`'s docstring for why each
    of those is borrowed rather than minted.

    **A PER-ACCOUNT REFUSAL IS NOT A REQUEST FAILURE.** 200 with `sent` and
    `skipped` beside each other: a selection of twelve where one is on a medical
    hold sends eleven and says why the twelfth did not. A 4xx would make one
    hold cancel a morning's chase.

    **NOTHING IS SENT HERE OR ANYWHERE** (`BR-NOT-005`). Every notice is a write
    to `outbound_messages`; the dispatcher sends. There is no SMTP call on this
    path and there must not be one.
    """
    require_tenant(request)
    payload = _payload(request)
    account_ids = tuple(payload.get("account_ids") or ())
    if not account_ids:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="payments.collections.no_selection"
        )
    channels = tuple(payload.get("channels") or ("pdf_print",))
    try:
        body = notices_by_hand.send(
            account_ids=account_ids,
            as_of=_business_date(payload, "as_of"),
            tone=payload.get("tone"),
            rung=payload.get("rung"),
            cut_date=_optional_date(payload, "cut_date"),
            channels=channels,
            balance_floor=_optional_money(payload, "balance_floor"),
            partial_pause_percent=_optional_money(payload, "partial_pause_percent"),
            medical_hold_account_ids=tuple(payload.get("medical_hold_account_ids") or ()),
            idempotency_key=str(payload.get("idempotency_key") or ""),
            actor=_actor(request),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(body)


urlpatterns = [
    # ⚠ ORDER AND OWNERSHIP, both checked rather than assumed. `config/urls.py`
    # already records that **payments owns `collections/notices`** — its own
    # comment, written when `apps.notifications.api` was mounted and deliberately
    # did NOT mint this door: *"minting a second door here would be this module
    # deciding where an account stands on a ladder it does not own."*
    # `apps.payments.api` declares `collections/run` and `collections/ladder`,
    # both literal two-segment paths; this is a third literal and can collide
    # with neither.
    path("collections/notices", collections_notices),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-138-BRC07 §3 P4.13 · 05-prototype/06 Payments Page Blueprint.pdf
#         p22 + screen 7·3d · apps/payments/notices_by_hand.py · api.py
#         (`collections_run`, the sibling door) · config/urls.py:544 ·
#         BR-PAY-017 · BR-PAY-029 · BR-PAY-035 · BR-NOT-005 · BR-SHL-025
# generated: 2026-09-23 by the CR-138 lane P4-READS
# checklist: A✔ B=deferred(P4.14/P4.27 own screen 7·3d, HELD to wave 2) C✔ D✔
#            E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the route answered `Resolver404` before this file
#        was included; quoted verbatim in the test file's header.
# exceptions:
#   (1) 200 WITH `skipped` RATHER THAN A 4xx ON A PER-ACCOUNT REFUSAL. A bulk
#       act reports per row; one medical hold must not cancel a morning's chase.
#   (2) A JSON FLOAT ON A MONEY ARGUMENT IS REFUSED RATHER THAN COERCED
#       (hard rule 2), the same posture every other payments door takes.
#   (3) NO GET. *"Which notices went out"* is `GET /notices` (notifications) and
#       `GET /accounts/{id}/collections` (payments) — both already mounted. A
#       third read here would be a second answer to a question two doors
#       already answer.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
