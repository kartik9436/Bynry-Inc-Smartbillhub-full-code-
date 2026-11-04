# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2032 — MONEY GOING OUT HAS NO DOOR. `approve_refund` and
#           `void_refund` are both `@permissions.require_role(SYSTEM_ADMIN,
#           br_ref="BR-PAY-014")`, 114 lines between them, and the only refund
#           route in the whole tree was `accounts/{id}/refund` in
#           `apps/customers/api.py`, which reaches neither. Found by G52 and
#           named in `g52_no_door_baseline.txt`, whose two lines this file
#           deletes.
# Story:    US-PAY-011 (refunds) · J15 steps 2–3 (the approval queue)
#           Screens: S58
# Rules:    BR-PAY-014 (CONFIRMED — *"Refunds only from a real credit balance;
#           Admin approval; check/ACH v1; DR customer-credit / CR cash;
#           immutable row + receipt"*) · BR-PAY-037 (one user MAY initiate and
#           approve in v1, as long as both acts are recorded separately) ·
#           BR-SHL-025 (server-enforced RBAC) · CLAUDE.md hard rule 4
#           (financial immutability — a void is a status move plus a REVERSING
#           posting, never a removal) · hard rule 5 (only the ledger posting
#           service writes journal lines) · hard rule 7 (every money action
#           writes `audit_log` — written by the service)
# Change:   CR-059 · CS-6 · task 17 (2026-09-01) — the three MISSING refund
#           routes (raise · issue · clear) and, because CS-6 found it, the role
#           gate added IN THE SERVICE for issue and clear (BR-PAY-1071). The
#           CR's own words: *"A refund can be approved and voided from a screen
#           but not raised, paid out or cleared. The services are complete; only
#           the demo seeder calls them. So the approval queue that IS routed can
#           never have anything in it."*
# Ruling:   decision log 2026-08-28 §6, "REFUNDS: THE APPROVAL QUEUE IS A READ
#           THE MODEL ALREADY REQUIRED" · decision log 2026-09-01, CR-059 W3 ·
#           decision log 2026-09-03, PO: "q6 yes Clark can issue refund" —
#           BR-PAY-1071 AMENDED, `refund_issue` widens from SystemAdminOnly to
#           AdminOrClerk, and NOTHING else on this file's five gates moves.
# Tests:    06-backend/tests/test_def2032_refund_doors.py ·
#           06-backend/tests/test_cr059_cs6_refund_doors.py
# Impacts:  config/urls.py inclusion · g52_no_door_baseline.txt ·
#           apps/payments/refunds.py (two new `@require_role` gates) ·
#           apps/payments/selectors.py (`refund_step_dict`, `payment_account_id`)
# ───────────────────────────────────────────────────────
"""The doors on `refunds` — raise, the queue, approve, issue, clear and void.

⚠ **THIS FILE OPENED WITH *"the three doors"* UNTIL 2026-09-01 AND THERE ARE NOW
SIX** (CR-059 CS-6, task 17). The original three and their reasoning are below,
unchanged; the three CS-6 added have their own section further down.

Its own module rather than more lines in `apps/payments/api.py`, on the
`apps.billing.corrections_api` precedent and for hard-won law 11's reason: a
1,000-line file several lanes edit is where a pathspec commit eats somebody's
work. ~~**`apps/payments/refunds.py` is NOT touched by this lane** — it is on
`10-scripts/gates/human_owned.txt` and needs nothing changed: the two actions
already exist, already carry their own server-enforced Admin gate, and were
simply unreachable.~~ **TRUE OF THE `DEF-2032` LANE, AND NOT OF THE CS-6 ONE:**
CS-6's finding is that `issue_refund` and `clear_refund` carried **no gate at
all**, which is a change to the SERVICE and cannot be honoured from a route.
That file was edited — two decorators and the docstrings that state them — with
a row in `12-governance/09-human-review-ledger.md`.

THIN by law: the writes go through `refunds.py` (sole writer), the read through
`selectors.refund_queue`. **No ORM, no figure and no rounding in this file.**

═══════════════════════════════════════════════════════════════════════════════
WHY A LIST HAD TO COME WITH THE TWO WRITES
═══════════════════════════════════════════════════════════════════════════════

Mounting `approve` and `void` alone would have produced two doors nobody can
walk through, because **no route in this product listed a refund id.** That is
`DEF-100`'s mechanism one table over, in its own words: *"the only write-off id
a browser could hold was the one the requester's own screen had just minted, so
the Approve control had nowhere to live except beside the request."*

It is not this lane inventing a screen either. `apps/payments/models.Refund`'s
docstring records it as a requirement, verbatim — *"J15 steps 2–3 require the
row to be VISIBLE in an approval queue between the request and the execution"* —
and `selectors.refund_row` was written for S58 and reached no route either.

═══════════════════════════════════════════════════════════════════════════════
`AdminOnly`, NOT `AdminOrClerk` — THE LAYER BELOW IS MIRRORED, NEVER WIDENED
═══════════════════════════════════════════════════════════════════════════════

`BR-PAY-014` says *Admin approval* and both services carry
`@require_role(SYSTEM_ADMIN)`. So both writes mount `SystemAdminOnly` here: a
wider gate would promise a Billing Clerk a reach the service denies, and the
clerk would meet it as a 403 from a layer they cannot see. The precedent is
`transfers_list`, mounted narrower than A4's Executive VIEW for exactly this
reason.

The QUEUE is `AdminOrClerk`: a clerk who raised a refund may see where it stands.
Seeing a queue is not approving from it, and the two writes above are what
`BR-PAY-014` gates.

═══════════════════════════════════════════════════════════════════════════════
2026-09-01 · CR-059 CS-6 · TASK 17 — THE OTHER THREE STEPS, AND THE TWO GATES
═══════════════════════════════════════════════════════════════════════════════

⚠ **THE `E3` EXCEPTION AT THE FOOT OF THIS FILE HAS BEEN PAID OFF AND ITS TEXT
IS NOW WRONG WHERE IT IS NOT UPDATED — hard-won law 1.** It read: *"`issue_refund`
and `clear_refund` get NO doors. They are not role-gated, so G52 does not see
them, and they are equally unreachable."* Both halves were true and both are
now closed, in the packet that sentence asked for.

**Why it mattered more than a missing route.** `refund_approve` above has been
mounted since 2026-08-28 and **the queue it approves from could never have
anything in it**, because nothing in the product could RAISE a refund: only the
demo seeder called `request_refund`. So the whole outbound half of the module —
the approval queue, the credit tested twice, the DR `2400` / CR `1000` posting,
the cheque clearing the bank — existed and was reachable by nobody.

**Three routes, three different gates, and each is a rule rather than a
habit** (CS-6, verbatim):

  * `POST /accounts/{id}/refunds` — **raise. Admin or Clerk**; *"the credit test
    runs in the service"*. A clerk may ask; only an Admin may approve.
  * `POST /refunds/{id}/issue` — **Admin or Clerk** (see the amendment below).
    This is where the money leaves.
  * `POST /refunds/{id}/clear` — **Admin or Executive**, because *"it is a bank
    fact, not an approval"*.

⚠ **THE ISSUE GATE READ *"Admin"* IN THIS FILE UNTIL 2026-09-03 AND THE THIRD
BULLET ABOVE HAS BEEN CORRECTED, NOT REWRITTEN OVER.** The Product Owner widened
it that day, verbatim: *"q6 yes Clark can issue refund"*. `BR-PAY-1071` is
AMENDED with its supersedes chain, and the reading that makes it coherent is the
PO's own — **the APPROVAL is the control.** `refund_approve` is still
`SystemAdminOnly` in this file and `approve_refund` is still
`@require_role(SYSTEM_ADMIN)` in the service: nothing about who AUTHORISES money
leaving has moved. Issuing is the clerical act carrying out a decision an Admin
already made, and in a two-person utility the person at the counter writing the
cheque is usually not the person who approved it. **Voiding stays Admin and
clearing stays Admin or Executive.** ⚠ It also closed `DEF-3421`: a ratified NSF
case had been red on the branch since 2026-09-01 because the 2026-09-01 gate
landed and one call site in its own test still passed the CLERK. The lane that
found it filed it rather than "fixing" it by changing the actor, on the ground
that the question belonged to the rule's owner. It did — and the answer makes
the TEST right and the GATE wrong.

**AND THE GATES WENT ON THE SERVICES FIRST (`BR-PAY-1071`).** `issue_refund` and
`clear_refund` carried no role gate of any kind, which is exactly why G52 never
listed them beside `approve_refund` and `void_refund`: that gate's universe IS
the `@require_role` declarations, so an ungated money-out function is invisible
to the check written to find doorless money-out functions. Mounting a
`SystemAdminOnly` route over an ungated service would have left the same hole
one layer down for any job, shell or second endpoint (BR-SHL-025).

**`request_refund` is gated at the ROUTE and not in the service, and that is
deliberate rather than an omission.** CS-6 asks for the service gate *"for issue
and clear"* by name; raising is the one step that moves nothing, posts nothing
and can be refused on its merits — `_credit_or_refuse` already refuses a request
no credit funds, at request AND again at issue. Adding an unasked-for
`@require_role` to a 🔒 human-owned money file would be this lane widening a
signed rule set. **REPORTED here rather than taken.**
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.payments import billing_seam, models, refunds, refunds_and_credits, selectors
from apps.payments.exceptions import PaymentRuleError
from core import errors
from core.permissions import AdminOrClerk, AdminOrExecutive, SystemAdminOnly
from core.pagination import clamp_page_size
from core.tenancy import require_tenant

# `_payload` and `_required_moment` are imported rather than restated:
# `_required_moment` is the G6 no-clock helper (BR-TEN-043 — *"posting and actual
# dates can differ; ask actual date to user"*) and a second copy of a rule that
# bans reading the server clock is a second place for it to drift back in.
#
# ⚠ **`_actor` IS *NOT* IMPORTED, AND THE REASON IS WORTH RECORDING.**
# `apps/payments/api._actor` returns `request.user` — the raw identity row — and
# that has always been enough there because **no service it calls is
# `@require_role`-gated.** ~~These two are the only role-gated functions in the
# whole payments module~~ — **THAT CLAUSE STOPPED BEING TRUE ON 2026-09-01
# (CR-059 CS-5 + CS-6) and is struck rather than deleted, because the next
# reader will meet its shape in `g52_no_door_baseline.txt`.** There are now
# FIVE: `approve_refund`, `void_refund`, `issue_refund`, `clear_refund` and
# `reversal.reverse_payment`; `writeoffs.approve_write_off` was always a sixth
# and is reached from `apps/payments/api.py`, which is why THAT file's `_actor`
# works at all — `IdentitySessionAuthentication` assigns `user.role` on the way
# past (`apps/identity/auth.py:179`), which is a property of the request's
# journey and not of the `User` row. `require_role` reads `actor.role`, an
# identity `User` row declares no such field, and reading the wrong one is a
# silent AUTH-002 on every call: the door mounted, reachable, and refusing every
# Admin who used it. Found by this lane's own test, not by reading the code.
from apps.payments.api import _payload, _query_date, _required_moment


def _actor(request: Any) -> Any:
    """The acting user in the B12 §6a service shape — id AND role.

    The role is server-attached by the identity layer (BE-04) and is never
    client input (BR-TEN-003). `refunds.approve_refund` and `void_refund` both
    carry `@require_role(SYSTEM_ADMIN)`, which reads `actor.role`; see the
    import block above for why this cannot be `apps/payments/api._actor`.

    `audit_log.actor_user_id` is hard rule 7's evidence half, so `id` comes from
    the session user and from nowhere else.
    """
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
        user=user,
    )


def _as_catalog_refusal(refusal: PaymentRuleError) -> errors.BizError:
    """A `PaymentRuleError`, as the ONE catalog exception G9 allows.

    Identical in shape and reasoning to `apps/payments/api._as_catalog_refusal`
    and deliberately a separate function rather than an import of it: this
    module's refusals are `BR-PAY-014`'s, so the fallback `br_ref` differs. One
    code (422 `BIZ_COMPLETENESS`) for all of them, because every refusal that
    arrives here has the same shape and picking among the nine BIZ codes per
    refusal would be this layer interpreting rules it does not own.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-014",
        message_key="payments.record.refused",
        params={"detail": str(refusal)},
    )


def _entry_date(value: Any) -> date | None:
    """The ledger date for the REVERSING entry, or absent.

    Optional by the service's own signature, and parsed rather than passed
    through as text because it reaches a ledger posting: `void_refund` types it
    `date | None`, and a string arriving where a `date` is declared is the shape
    that fails inside a transaction rather than at the door.
    """
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.bankrec.moment_required",
            field_errors=[{"field": "entry_date", "code": errors.VAL_FORMAT}],
        ) from bad


@api_view(["GET"])
@permission_classes([AdminOrClerk])  # seeing a queue is not approving from it
def refunds_queue(request: Any) -> Response:
    """`GET /refunds` — J15 step 2's approval queue, and the refund history.

    `?f.status=requested` is what an Admin approves from; no filter is the
    reported history. An unknown status is refused with the closed set rather
    than answering an empty queue — **an empty queue and an unanswerable one
    look identical on a screen** (`write_off_queue`'s own words, and the same
    trap).

    ⚠ **IT PAGES IN SQL SINCE 2026-09-24 (`DEF-PAY-6555` · `NFR-3` · `P1.3`),
    AND THIS DOCSTRING CARRIED THE OPPOSITE AS A DECISION.** It read
    *"Unpaginated, deliberately: a page of an approval queue is a queue that
    lies about what is pending."* The argument is good and the ceiling under it
    moved to 40,000 accounts on 2026-09-06. It is ANSWERED rather than
    overruled: `count` is the total over the FILTERED set and rides on every
    page, so the screen always knows what is pending. Full reasoning in
    `selectors.refund_queue`; the judgment is in
    `12-governance/02-decision-log.md` under 2026-09-24.

    ⚠ **BOTH APPROVAL ACTS ARE RENDERED SEPARATELY** and neither is folded into
    a boolean — `BR-PAY-037` lets one user initiate and approve in v1 *"as long
    as both acts are recorded separately"*, so a row showing only "approved"
    would erase the control the rule leans on.

    A READ — no audit row.
    """
    from core.pagination import parse_list_params, prepaged

    require_tenant(request)
    params = request.query_params
    # No `allowed_sorts`: the read orders `-requested_at, -created_at, -id` and
    # accepts no sort, so declaring one would put a control on screen that
    # changes nothing (`BR-SHL-010` — the config is what a screen DECLARES it
    # can do, and `DataTable` renders exactly that).
    listing = parse_list_params(params)
    captured: dict[str, Any] = {}

    def fetch(page: Any) -> tuple[list[dict[str, Any]], int]:
        body = selectors.refund_queue(
            status=params.get("f.status"),
            # Finance blueprint `P2.19`. p041's criteria table marked **State**
            # SERVED and these three NOT SERVED, over a toolbar the drawing puts
            # on the screen — *"only the state filter is supported today"*.
            q=params.get("q"),
            method=params.get("f.method"),
            requested_from=_query_date(request, "from"),
            requested_to=_query_date(request, "to"),
            offset=max(page.page - 1, 0) * page.per,
            limit=page.per,
        )
        captured.update(body)
        return [dict(row) for row in body["rows"]], body["total"]

    response = prepaged(request, listing, fetch)
    # ⚠ **`P2.19`'s HALF THAT IS NOT A FILTER, AND IT IS NOT `count`.** The
    # docstring above objects to paging an approval queue and the objection is
    # real; the 3,000-connection ceiling it rests on is not, since 2026-09-06.
    # The blueprint's answer is the TRUE total beside the list, so the badge in
    # the Revenue & AR view label cannot be made to lie by a filter or by a
    # page. **`count` and `pending` are different numbers on purpose:** `count`
    # is the FILTERED set and is what the pager states (*1–50 of 120*);
    # `pending` ignores every parameter above and is what the badge states. Ask
    # one number to be both and narrowing to `f.method=ach` shrinks *"what is
    # waiting"* over refunds that are still waiting.
    response.data["pending"] = selectors.refund_pending_count()
    # `P1.5` — the chips, so a sixth status added server-side appears on screen
    # without a front-end change (`DEF-PAY-6557`).
    response.data["statuses"] = captured["statuses"]
    response.data["methods"] = captured["methods"]
    return response


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # BR-PAY-014 — the service's own gate, mirrored
def refund_approve(request: Any, refund_id: str) -> Response:
    """`POST /refunds/{id}/approve` — J15 step 3. `BR-PAY-014`'s Admin approval.

    **Approval gates the money exactly once**: only a `requested` refund can be
    approved and the service refuses every other status by name. It moves no
    money — `issue_refund` is the step that draws the customer-credit account
    down, and it is a different act.

    `approved_at` is the caller's business moment and is **not defaulted to
    now**: approval is the control `BR-PAY-014` rests on, and a timestamp the
    server invented is a control nobody can reconstruct in a year (hard rule 7).

    ⚠ **`BR-PAY-037` IS EXERCISED, NOT WORKED AROUND.** The same user holding
    the approver role MAY approve their own request in v1 — J15 step 3 is
    exactly that — and the control is that BOTH acts are recorded distinctly,
    which is why `requested_by_id` and `approved_by_id` are separate columns
    rather than a flag. Enforced separation of duties is v2 and nothing here
    pre-empts it.
    """
    require_tenant(request)
    body = _payload(request)
    try:
        result = refunds.approve_refund(
            _actor(request),
            refund_id=refund_id,
            approved_at=_required_moment(body, "approved_at"),
            memo=body.get("memo"),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(selectors.refund_detail(result.refund_id))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # BR-PAY-014 — the service's own gate, mirrored
def refund_void(request: Any, refund_id: str) -> Response:
    """`POST /refunds/{id}/void` — a cheque lost in the post (US-PAY-011 TC-4).

    *"Status → Void with reversing posting (credit restored 57.13); new refund
    issuable; no row deleted."* Three things follow and the service asserts each:

      * **No row is deleted.** The trigger refuses DELETE in every status; the
        void is a status move plus a NEW mirror entry (hard rule 4).
      * **The credit comes back by exactly what left.** `reverse_refund_entry`
        hands the ledger its own entry with the sides swapped — **nothing
        recomputes the figure**, here or below (hard rule 5).
      * **A new refund is then issuable**, because the credit position is
        computed from rows and a voided refund is excluded from it.

    `void_reason` is REQUIRED and is not defaulted: *"a cheque that left the
    building and came back is a fact somebody has to be able to reconstruct in a
    year"* (the service's own words, hard rule 7). The service refuses a blank.
    """
    require_tenant(request)
    body = _payload(request)
    try:
        result = refunds.void_refund(
            _actor(request),
            refund_id=refund_id,
            voided_at=_required_moment(body, "voided_at"),
            void_reason=body.get("void_reason") or "",
            entry_date=_entry_date(body.get("entry_date")),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(selectors.refund_detail(result.refund_id))


# ══════════════════════════════════════════════════════════════════════════
# CR-059 CS-6 · TASK 17 — RAISE · ISSUE · CLEAR
# ══════════════════════════════════════════════════════════════════════════


def _required(payload: dict[str, Any], name: str, *, message_key: str) -> Any:
    """A field the body must carry, refused with the copy the CALLER names.

    `message_key` is a LITERAL at every call site rather than composed from
    `name`, and that is not a style choice: G18 asserts that every key has a
    call site and every call site resolves, and it reads literals — a composed
    key would pass the gate by being invisible to it and then render as its own
    raw text to a clerk. `apps/payments/api._required` says the same in full.
    """
    value = payload.get(name)
    if value is None or (isinstance(value, str) and value.strip() == ""):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key=message_key,
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    return value


def _amount(payload: dict[str, Any]) -> Decimal:
    """The refund amount as `Decimal`, from the STRING the form submits.

    CLAUDE.md rule 2 — never a float, at any point. The service refuses a float
    outright rather than converting one, and so does this: a JSON number that
    arrived as a float has already lost the digits the clerk typed, and a
    conversion here would hide the place money became binary.
    """
    raw = _required(payload, "amount", message_key="payments.record.amount_required")
    if isinstance(raw, float):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.record.amount_invalid",
            field_errors=[{"field": "amount", "code": errors.VAL_FORMAT}],
        )
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.record.amount_invalid",
            field_errors=[{"field": "amount", "code": errors.VAL_FORMAT}],
        ) from bad


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # CS-6 — "raise: Admin or Clerk"
def account_refunds(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/refunds` — RAISE one. J15 step 1 (CR-059 CS-6).

    The body is S58's Record-refund form:

        payment_id       the overpayment this draws back — REQUIRED (see below)
        amount           decimal STRING, > 0
        method           `check` or `ach`; `card` is refused with its rails note
        requested_at     the clerk's business moment — REQUIRED, never a clock
        reference        the cheque number — the service REQUIRES it for cheques
        reason           optional
        memo             optional
        idempotency_key  the form's submit token — REQUIRED

    **NO MONEY MOVES HERE** (`BR-PAY-014`). The row exists so J15 step 2's
    approval queue has something to show and so `BR-PAY-037`'s *"both acts
    recorded distinctly"* has somewhere to record the first one. 201 on a new
    request, **200 on a replay** with the original — the `account_payments`
    argument, applied to the same clerk and the same double click.

    ⚠ **`payment_id` IS NOW OPTIONAL — CS-7 LANDED 2026-09-03, AND THIS
    PARAGRAPH USED TO SAY THE OPPOSITE.** It read: *"`payment_id` … REQUIRED"*,
    and that a refund could name only one payment because `refunds.payment_id`
    was `NOT NULL` with no `account_id` beside it. **Both halves are now
    false.** `payments/0018` carries the PO's ruling of 2026-09-01 (`OQ-195`,
    option (a)): the column is nullable and `refunds.account_id` is NOT NULL.
    Corrected in place rather than deleted, because hard-won law 1 is what a
    stale guarantee in a docstring costs.

    **So the ACCOUNT in the path is the address, and it always was** — this
    route was built for this ruling on 2026-09-01, before the schema could hold
    it. What changed is only that the body field is now genuinely optional:

      * **`payment_id` given** — the credit came from ONE overpayment and the
        refund says so. PE-9's **$350.00 → $57.13** is unchanged.
      * **`payment_id` omitted** — **the case CS-7 exists for.** The credit was
        built from several payments; the refund is against the account's credit
        balance and names none of them. The PO's own worked figure: **$40.00 in
        June plus $17.13 in July refunded as one $57.13 cheque.**
        `GET /accounts/{id}/credit-sources` is what lists the payments behind
        it, because listing them is evidence and not a link.

    **SO THE PATH SEGMENT IS ENFORCED RATHER THAN DECORATIVE.** A `payment_id`
    naming another account's payment is refused here, by name. Without that
    check the account in the URL would be a label — a clerk on account A's
    screen could raise a refund funded by account B's overpayment, and every
    downstream figure (the credit test, the offset, the ledger) would be
    account B's while the screen said A.

    ⚠ **`cross_account_check` IS ALWAYS TRUE AND IS NOT A CLIENT CHOICE.**
    *"Offset first"* is CONFIRMED law (PO 2026-08-12, `OQ-135` CLOSED): a
    customer holding a credit on one account and an arrear on another has the
    credit applied to the debt before any refund is paid. Letting the form send
    `false` would let a screen switch a ruling off. On the repo fixture the
    refusal is **$57.13** of credit against **$948.20** overdue on a sibling
    account with a final notice already sent — the refund does not go out, and
    the clerk is told which account and roughly how much.

    **What that refusal is NOT is the offset being APPLIED.** Moving the credit
    is a balance TRANSFER between two financial records with one reviewed writer
    (CS-8, task 31), and `offset_before_refund` computes both figures and moves
    nothing. Until CS-8 lands, a customer owing elsewhere cannot be refunded
    here at all — which is the ruled behaviour, and is stated so the screen lane
    renders the refusal rather than a spinner.
    """
    require_tenant(request)
    body = _payload(request)
    _required(body, "idempotency_key", message_key="payments.record.idempotency_key_required")
    # ⚠ AN ABSENT `payment_id` IS LEFT TO THE SERVICE, DELIBERATELY — and since
    # CS-7 (2026-09-03) an absent one is LAWFUL rather than merely unrefused
    # here. The first draft refused it under `payments.record.amount_required`,
    # whose copy reads *"Give the amount received"* — a sentence about the wrong
    # field, in eleven languages, and G18 cannot see it because the key
    # resolves. The service is where the address rule lives (`refunds._address`)
    # and it refuses a request with NEITHER a payment nor an account, in the
    # sentence that rule owns. One refusal, from the rule's owner.
    payment_id = body.get("payment_id")
    _refuse_a_payment_on_another_account(account_id, payment_id)
    _refuse_a_cheque_number_before_the_cheque(body)
    try:
        result = refunds.request_refund(
            _actor(request),
            payment_id=payment_id,
            # CR-059 CS-7 — the address, always, and the ONLY link when the
            # credit came from more than one payment. The path segment stops
            # being a label and becomes the row's own column.
            account_id=account_id,
            amount=_amount(body),
            method=body.get("method") or models.REFUND_METHOD_CHECK,
            requested_at=_required_moment(body, "requested_at"),
            reason=body.get("reason"),
            # ⚠ **NO `reference` — DEF-PAY-6331, 2026-09-23.** It used to read
            # `reference=body.get("reference")` and that is the defect: a
            # cheque number cannot be known when a refund is REQUESTED, and the
            # column was frozen from row creation, so the number a clerk typed
            # here was the only one the product would ever hold. It is
            # collected at `POST /refunds/{id}/issue` now, where the cheque is
            # actually written. A body that still carries one is refused by
            # name above rather than dropped in silence.
            memo=body.get("memo"),
            cross_account_check=True,
            idempotency_key=body["idempotency_key"],
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(selectors.refund_step_dict(result), status=201 if result.created else 200)


@api_view(["GET"])
@permission_classes([AdminOrClerk])  # the same reach as raising one
def account_credit_sources(request: Any, account_id: str) -> Response:
    """`GET /accounts/{id}/credit-sources` — CR-059 CS-7's evidence half (S58).

    CS-7's acceptance line is *"a credit built from two overpayments can be
    refunded, **listing the payments behind it**"*, and this is the second
    clause. A GET: it writes nothing and may be taken twice with no consequence.

    Answers what the account holds on account, and which payments built it —
    each with the part of itself that no bill absorbed, because a $350.00 cheque
    that left $57.13 behind CONTRIBUTED $57.13 and a screen listing $350.00
    would offer a clerk money that is not there.

    ⚠ **THE ROWS AND THE REFUNDABLE FIGURE DIVERGE AFTER THE FIRST REFUND, ON
    PURPOSE.** Nothing records which payments a past refund drew on — the PO's
    ruling of 2026-09-01 is that a refund names the ACCOUNT and not a payment —
    so `refundable` is the position and the rows are evidence. `problems[]` says
    so on every response rather than leaving a screen to add them up and be
    refused by the refund path.

    `AdminOrClerk`, matching `POST /accounts/{id}/refunds`: this is what a clerk
    reads immediately before raising the refund, and a role that may raise one
    must be able to see what it is drawing on.
    """
    require_tenant(request)
    return Response(selectors.account_credit_sources(account_id))


def _refuse_a_cheque_number_before_the_cheque(body: dict[str, Any]) -> None:
    """DEF-PAY-6331 — a raise carries no cheque number, and says so out loud.

    ⚠ **REFUSED BY NAME RATHER THAN IGNORED, AND THAT IS THE WHOLE POINT.** A
    key this door quietly dropped would be a cheque number a caller believed it
    had recorded, stored nowhere, discovered by nobody — which is the exact
    shape of the defect this change exists to fix, rebuilt one layer down. An
    absence is invisible to every check this repo has (`DEF-CUS-3653`).

    **AND IT PREVENTS A LOCKOUT, not only a silence.** `refunds.reference` is
    WRITE-ONCE from `payments/0041`. A number accepted here would sit on the
    row, and the clerk who later types the real cheque number at issue would be
    refused for trying to change it — a refund that can never be issued
    through its own screen.

    The service keeps its `reference` argument for the one caller that
    legitimately knows the number up front (a back-dated import, the demo
    fixture recording PE-9's #10241). **This door is not that caller**, so it
    is the door that closes rather than the argument that goes.
    """
    if (body.get("reference") or "") == "":
        return
    raise errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref="BR-PAY-014",
        message_key="payments.record.refused",
        params={
            "detail": (
                "a refund request carries no cheque number, because no cheque has been "
                "written yet — it is recorded when the refund is issued, which is the act "
                "that writes it. Nothing was saved. Raise the refund without one and give "
                "the number on Issue."
            )
        },
    )


def _refuse_a_payment_on_another_account(account_id: str, payment_id: Any) -> None:
    """The path segment is a CONSTRAINT, not a label (see `account_refunds`).

    Tenant-scoped through the same `payment_row_account` read the rest of this
    module uses, so a payment belonging to ANOTHER TENANT is simply not found
    and the refusal is the ordinary one — a cross-tenant id resolves to nothing,
    never to somebody else's row (CLAUDE.md rule 1, HR-1).

    A missing payment is left to `refunds._source_payment`, which already
    refuses it with the sentence a clerk can act on; this only answers the one
    question that function cannot, because it never sees the URL.
    """
    owner = selectors.payment_account_id(payment_id)
    if owner is not None and str(owner) != str(account_id):
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-PAY-014",
            message_key="payments.record.refused",
            params={
                "detail": (
                    "that payment belongs to a different account, so a refund raised here "
                    "would be funded by another customer's overpayment while this screen "
                    "named this one. Open the account the payment was taken on."
                )
            },
        )


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # BR-PAY-1071 as AMENDED — the service's gate, mirrored
def refund_issue(request: Any, refund_id: str) -> Response:
    """`POST /refunds/{id}/issue` — J15 step 4. **THE MONEY LEAVES HERE.**

    `BR-PAY-014`'s posting, and the only step in the refund lifecycle that
    moves a cent: DR **2400 Customer credit** / CR **1000 Cash**, composed by
    `ledger_seam.post_refund_executed` and written by the ledger posting service
    alone (hard rule 5). `PE-9`, exactly: a credit of **57.13** on `ACC-1042`
    refunded by cheque **#10241** takes the credit to **0.00**.

    **THE CREDIT IS TESTED AGAIN HERE, AND THAT IS THE WHOLE POINT OF A SEPARATE
    STEP.** `_credit_or_refuse` ran at request and runs again at issue, because
    an approval given on Tuesday must not pay out a credit that a Wednesday
    bounce pulled back — *"a credit real on Tuesday can be gone by Thursday, and
    the money moves on Thursday"* (CS-6). The response therefore carries
    `credit_position_after` on every step, so the screen never has to remember a
    figure it was shown earlier.

    `issued_at` is the caller's business moment and is **not defaulted to now**
    (BR-TEN-043, gate G6): the day a refund left decides which accounting period
    it left in, and a server that read its own clock would let request latency
    make that choice.

    ⚠ **`reference` — THE CHEQUE NUMBER — IS COLLECTED HERE FROM 2026-09-23
    (`DEF-PAY-6331`).** It used to be collected on the RAISE form, days before
    Finance approves anything and before a cheque exists, and the column was
    frozen from row creation — so when the real cheque was written there was
    **nowhere in the product to record its number**. The blueprint draws it on
    this act and says why in four words: *"the only record of which cheque this
    was"* (`06 Payments Page Blueprint.pdf` p078, annotation ②).

    It is written in the SAME statement as the status move, inside the same
    transaction as the posting and the audit row. ~~and never patched
    afterwards~~ — **amended 2026-09-23 (`CR-141-BRC07`, PO ruling
    `OQ-PAY-12614`):** issuing still never overwrites a number the row already
    holds, and `payments/0041` + `payments/0043` refuse every other rewrite at
    the database; a number KEYED wrongly is replaced only through
    `POST /refunds/{id}/correct-reference` below. `issue_refund` refuses an
    overwrite in Python as well, because the test database is SQLite and has no
    triggers (hard-won law 14). `POST /accounts/{id}/refunds` now **refuses** a
    `reference` by name rather than storing one.

    ⚠ **ADMIN OR BILLING CLERK, at the door AND in the service** — `BR-PAY-1071`
    as AMENDED by the Product Owner on 2026-09-03, verbatim: *"q6 yes Clark can
    issue refund"*. **This route read `SystemAdminOnly` for two days** and the
    sentence is corrected rather than left to rot (hard-won law 1). The logic is
    the PO's own: **the APPROVAL is the control** — `POST /refunds/{id}/approve`
    above is still `SystemAdminOnly` and nothing about who authorises money
    leaving has moved — and issuing is the clerical act carrying out a decision
    an Admin already made. `POST /refunds/{id}/clear` below is untouched at
    `AdminOrExecutive`, and voiding stays Admin.

    The door still MIRRORS the service and never widens it (BR-SHL-025): an
    Executive is refused at both, so a role that cannot issue is never promised
    a reach the service denies. See the module docstring for what the gate's
    total absence cost before 2026-09-01.
    """
    require_tenant(request)
    body = _payload(request)
    try:
        result = refunds.issue_refund(
            _actor(request),
            refund_id=refund_id,
            issued_at=_required_moment(body, "issued_at"),
            # ⚠ **THE CHEQUE NUMBER, COLLECTED HERE FROM 2026-09-23
            # (DEF-PAY-6331).** It is not `_required` at this door even though
            # 6·3b draws it with an asterisk: the requirement is *"required for
            # CHECK"* (US-PAY-011 §5) and this door cannot see the method
            # without reading the row. `refunds.issue_refund` can, and refuses
            # a cheque refund with no number in the sentence that rule owns —
            # one refusal, from the rule's owner, which is the same reasoning
            # the absent `payment_id` above is left to the service for.
            reference=body.get("reference"),
            entry_date=_entry_date(body.get("entry_date")),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(selectors.refund_step_dict(result))


@api_view(["POST"])
@permission_classes([AdminOrExecutive])  # CS-6 — "a bank fact, not an approval"
def refund_clear(request: Any, refund_id: str) -> Response:
    """`POST /refunds/{id}/clear` — the cheque cleared the bank (TC-3).

    **A status move and a date. It posts NOTHING.** The money left the books at
    issue, and posting again on clearing would take it out twice — the service
    asserts that and so does `test_us_pay_011_tc3_tc4`, by counting journal
    entries either side. What clearing gives is the date bank reconciliation
    matches the outgoing item on.

    **Admin or Executive** (`BR-PAY-1071`), because CS-6 puts it in one line:
    *"it is a bank fact, not an approval"*. A4 gives the finance/reconcile
    column to the Executive, and every deposit-batch and bank-statement route in
    this module is already `AdminOrExecutive`; gating this one to Admin alone
    would mean the person reconciling the bank cannot record that a cheque they
    can see on the statement has cleared. A **Billing Clerk is refused**, which
    is narrower than yesterday, when this service accepted anybody at all.

    ⚠ **CS-15 (task 47) IS WHAT LINKS THIS TO ITS BANK LINE**, and it is not
    built: outgoing items are not matched against a statement yet, so this
    records the fact a person read off the bank's own statement. CS-6's screen
    note says the same — the control lives on **S39 beside the bank line** when
    CS-15 exists, and on **S58** until then.
    """
    require_tenant(request)
    body = _payload(request)
    try:
        result = refunds.clear_refund(
            _actor(request),
            refund_id=refund_id,
            cleared_at=_required_moment(body, "cleared_at"),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(selectors.refund_step_dict(result))


# ══════════════════════════════════════════════════════════════════════════
# CR-141-BRC07 — A MISTYPED CHECK NUMBER, CORRECTED (OQ-PAY-12614)
# ══════════════════════════════════════════════════════════════════════════


def _as_correction_refusal(refusal: PaymentRuleError) -> errors.BizError:
    """A correction refusal, as the ONE catalog exception G9 allows.

    `BIZ_IMMUTABLE` and not this file's `BIZ_COMPLETENESS`, for the payment
    door's reason (`amendments_api._as_catalog_refusal`): every refusal on this
    path is *"that field is money that has left"* or *"that refund is closed"*,
    which is what `BIZ-IMMUTABLE` names — a completeness code would tell the
    screen the clerk left something out. Its own `message_key`, because the
    payment door's sentence speaks of a banked TENDER, which a refund does not
    have.
    """
    return errors.BizError(
        errors.BIZ_IMMUTABLE,
        br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-014",
        message_key="payments.refunds.correct.refused",
        params={"detail": str(refusal)},
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # BR-PAY-1071 as AMENDED — who issues, corrects
def refund_correct_reference(request: Any, refund_id: str) -> Response:
    """`POST /refunds/{id}/correct-reference` — S58's *Correct check number*.

    **THE ROUTE IS THE SPEC, as it is for the payment door it mirrors**
    (`POST /payments/{id}/correct-reference`, `OQ-1322`): one named verb, and
    no PATCH, PUT or DELETE added to any refund path. What may be corrected is
    visible here — the body is the whole of it:

        reference   the check number printed on the check — REQUIRED
        note        why it is being corrected — REQUIRED

    **Anything else is refused BY NAME** — `amount`, `account_id`, `method`,
    and also `memo` and `tender_id`, which the PAYMENT door accepts: the PO was
    shown a refund's CHECK NUMBER and nothing else (`OQ-PAY-12614`, PO
    2026-09-23, *"(b) Allow a correction, the same way you allowed it for
    payments on 2 September"*), so nothing else is signed.

    **Admin or Billing Clerk**, mirroring `refunds.correct_refund_reference`'s
    service gate and never widening it (BR-SHL-025): the person who writes the
    check corrects its number (`BR-PAY-1071` as amended 2026-09-03). An
    Executive is refused at both layers.

    ⚠ **THE ANSWER CARRIES THE STORED ROW, NOT THE SENT VALUE,** and an
    `unavailable[]` entry saying the replaced number lives only in `audit_log`,
    which is pruned on its one schedule (`OQ-1340`). That entry is a machine
    fact for a caller and never copy for a screen — B14 rule 33.
    """
    require_tenant(request)
    body = _payload(request)
    try:
        result = refunds.correct_refund_reference(
            _actor(request),
            refund_id=refund_id,
            reference=body.get("reference"),
            note=body.get("note") or "",
            body=body,
        )
    except PaymentRuleError as refusal:
        raise _as_correction_refusal(refusal) from refusal
    return Response(result)


# ── the routes ─────────────────────────────────────────────────────────────
# `refunds` is a bare literal and the writes are three-segment paths, so
# nothing here can shadow anything in `apps/payments/api.py` — which registers
# no `refunds` pattern of any kind, which is the defect.
#
# ⚠ `accounts/<id>/refunds` IS NEW AND ITS ORDER WAS CHECKED RATHER THAN
# ASSUMED. `apps/customers/api.py` owns the `accounts/…` family and is included
# FIRST by `config/urls.py`; it declares `accounts/<id>/refund` — SINGULAR, the
# move-out settlement instruction — and no plural pattern, so the two cannot
# collide. `apps/payments/api.py` declares `accounts/<id>/payments`,
# `/collections` and `/open-bills` and no `refunds`.

# ══════════════════════════════════════════════════════════════════════════
# CR-138-BRC07 · P4.4 — THE DETAIL VIEW BETWEEN A RAISE MODAL AND AN ACT MODAL
# ══════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([AdminOrClerk])  # the same reach as the queue that lists it
def refund_item(request: Any, refund_id: str) -> Response:
    """`GET /refunds/{id}` — **the answer to *"where is my money?"*** (P4.4).

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  A RAISE MODAL AND AN ACT MODAL, AND NOTHING BETWEEN THEM.           ║
    ╚══════════════════════════════════════════════════════════════════════╝
    `RefundsPage.tsx` could open a form to CREATE a refund and a form to ACT on
    one, and there was no way to open a refund and simply LOOK at it. So the
    question a customer actually asks on the telephone — *"you said you were
    sending my $57.13, where is it?"* — had no screen and no endpoint behind
    one. The four act routes below each return the row as a by-product of
    changing it; **none of them could be called to find out.**

    **THIN BY LAW, AND THE ROW IS THE SAME ROW.** The read is
    `selectors.refund_detail`, which already existed and which the approve,
    issue, clear and void routes all answer with. No second serialisation of a
    money row is added here — `DEF-014`'s exact shape — so a refund cannot look
    like one thing after an act and another when opened.

    **WHY `AdminOrClerk` AND NOT NARROWER.** `GET /refunds` lists this very row
    to the same audience, and `POST /accounts/{id}/refunds` lets that audience
    raise one. **A door must not deny a reach its siblings grant** — the
    argument `credit_notes_api` records in the other direction — and hiding the
    detail of a row already on the clerk's list would be a gate that protects
    nothing and teaches the clerk the screen is broken.

    ⚠ **404-NEVER-403 FOR ANOTHER TENANT'S REFUND.** The selector filters on
    the tenant id and a miss is a miss (hard rule 1, `BR-TEN-003`, HR-1). A 403
    would confirm the row exists, which is the one thing a stranger must not
    learn from a refusal.

    **BOTH APPROVAL ACTS STAY SEPARATE ON THE ROW** — `requested_by` and
    `approved_by` are distinct members and neither is folded into a boolean,
    because `BR-PAY-037` lets one user initiate AND approve in v1 *"as long as
    both acts are recorded separately"*, and a detail view showing only
    *approved* would erase the control the rule leans on.

    A READ. No clock, no money arithmetic, no write, no audit row.
    """
    require_tenant(request)
    return Response(selectors.refund_detail(refund_id))


# ══════════════════════════════════════════════════════════════════════════
# CR-138-BRC07 · P4.25 — ONE LIST, TWO LIFECYCLES, TWO MODULES
# ══════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([AdminOrClerk])  # the same reach as the refunds queue
def refunds_and_credits_list(request: Any) -> Response:
    """`GET /refunds-and-credits` — everything this utility has given back.

    Screen 6·1's question: *"what have we given back, and can I still tell a
    cheque from a credit?"* A clerk closing an account in credit chooses
    between a refund and a credit note, and until now the two lived in two
    modules with no list that showed both.

    ⚠ **IT IS A SECOND ROUTE AND NOT A WIDENING OF `GET /refunds`, DELIBERATELY.**
    That route is the APPROVAL QUEUE. Its own docstring says it is unpaginated
    *because* *"a page of an approval queue is a queue that lies about what is
    pending"* — so putting credit notes into it would page it, or would build
    every refund the tenant has, and the two questions are different anyway:
    one asks *what needs my signature*, this asks *what have we given back*.

    **PAGED, `?page` AND `?per`** — `NFR-3`. The page is taken in SQL on BOTH
    sides of the module boundary; see `refunds_and_credits.page` for why a
    federated page is what a `UNION` cannot be when one table belongs to
    billing (B1, B2 §2).

    `?f.kind=refund|credit_note` narrows to one source and an unknown value is
    REFUSED with the closed set rather than answering an empty list — **an
    empty list and an unanswerable one look identical on a screen**
    (`refund_queue`'s own recorded trap).

    ⚠ **`count` IS A TOTAL AND SAYS WHEN IT IS NOT.** If billing publishes no
    credit-note read, the envelope carries `credit_notes_read_unavailable` and
    the count counts refunds only, in words. A short list with no number
    attached to what it left out is `G32`'s defect: a true zero over a scope it
    silently excluded.

    A READ. No clock, no write, no audit row.
    """
    require_tenant(request)
    per = clamp_page_size(request.query_params.get("per"))
    try:
        page_number = max(int(str(request.query_params.get("page"))), 1)
    except (TypeError, ValueError):
        # BR-SHL-011 "never error": a garbage page clamps to the first rather
        # than 404-ing, the same answer `StandardPagination` gives.
        page_number = 1
    body = refunds_and_credits.page(
        offset=(page_number - 1) * per,
        limit=per,
        kind=request.query_params.get("f.kind"),
    )
    body["page"] = page_number
    return Response(body)


# ══════════════════════════════════════════════════════════════════════════
# CR-138-BRC07 · P4.12 — THE DOOR TO THE CREDIT PATH. **NOT A COPY OF IT.**
# ══════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([AdminOrClerk])  # the same reach as raising a refund
def account_credit_path(request: Any, account_id: str) -> Response:
    """`GET /accounts/{id}/credit-path` — *"can I give them a credit instead?"*

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  PO, 2026-09-22: "we can not have two path for 1 capabilities wew     ║
    ║  will confuse user." SO THIS MINTS NO WRITE VERB AT ALL.              ║
    ╚══════════════════════════════════════════════════════════════════════╝
    A clerk closing an account in credit has two ways out — a cheque or a
    credit note — and **only one of them is visible from where the choice is
    made.** `POST /accounts/{id}/refunds` is one click away on this tab; the
    credit path lives in billing and a payments screen has no way to find it.

    **THIS IS A SIGNPOST, NOT A SECOND IMPLEMENTATION.** It answers *is the
    credit path available on this account, and against which bill*, and hands
    back the addresses of **billing's own mounted routes** so the browser calls
    billing directly. The write stays exactly where it has always been:
    `corrections.execute_credit_only`, reached through `POST /corrections`,
    `…/approve` and `…/execute`. Nothing is proxied and nothing is re-derived.

    ⚠ **THE FACT A PAYMENTS SCREEN CANNOT KNOW BY ITSELF IS THAT A CREDIT IS
    RAISED AGAINST A BILL AND A REFUND AGAINST AN ACCOUNT.** So *"credit them
    instead"* is not symmetrical with *"refund them"*: the clerk must name a
    bill, and this serves the ones they may name.

    **`available: false` MEANS THIS ACCOUNT HAS NOTHING TO CREDIT TODAY** — not
    that the feature is unbuilt. The reason travels on `problems` so the screen
    prints a sentence rather than greying a control and leaving the clerk with
    *"why not?"* (`BR-SHL-025`).

    A READ. No clock, no money arithmetic, no write, no audit row.
    """
    require_tenant(request)
    try:
        body = billing_seam.credit_path_for_account(account_id)
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(body)


urlpatterns = [
    # ORDER IS LOAD-BEARING. `refunds-and-credits` is a DIFFERENT literal from
    # `refunds`, so nothing collides today — it is declared first anyway,
    # because the `deposits/import` shape this module's siblings record is what
    # happens when a static word starts resolving as somebody's id.
    path("refunds-and-credits", refunds_and_credits_list),
    path("refunds", refunds_queue),
    # P4.4 — the detail view. Two segments, and every act below is three,
    # so it can never swallow one of them.
    path("refunds/<str:refund_id>", refund_item),
    path("refunds/<str:refund_id>/approve", refund_approve),
    path("refunds/<str:refund_id>/issue", refund_issue),
    path("refunds/<str:refund_id>/clear", refund_clear),
    path("refunds/<str:refund_id>/void", refund_void),
    # CR-141-BRC07 — the fourth three-segment act beside approve/issue/clear/
    # void; a literal last segment, so it can neither shadow nor be shadowed.
    path("refunds/<str:refund_id>/correct-reference", refund_correct_reference),
    path("accounts/<str:account_id>/refunds", account_refunds),
    # CR-059 CS-7. A literal last segment beside `refunds`, `payments`,
    # `collections`, `open-bills`, `transfers` and `transfer-preview`; none of
    # them can shadow another and no `accounts/<id>/<something>` catch-all may
    # ever be added above them.
    path("accounts/<str:account_id>/credit-sources", account_credit_sources),
    # CR-138-BRC07 · P4.12 — a literal last segment beside the six above;
    # none can shadow another. A READ ONLY: the credit WRITE is billing's
    # `POST /corrections…` and is not mirrored here (PO 2026-09-22).
    path("accounts/<str:account_id>/credit-path", account_credit_path),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2032 · G52 `g52_no_door_baseline.txt` · apps/payments/refunds.py ·
#         apps/payments/models.py (Refund) · BR-PAY-014 · BR-PAY-037 ·
#         DEF-100 (the same mechanism on `write_offs`) · decision log 2026-08-28
# generated: 2026-08-28 by lane DOORS
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 `GET /refunds` is ADDED — no screen names it. Mounted because the two
#      Admin-gated writes are unreachable without an id and nothing in this
#      product listed one; `models.Refund`'s docstring already required the
#      queue. REPORTED.
#   E2 `apps/payments/refunds.py` is on `human_owned.txt` and is NOT modified.
#      The queue read went to `selectors.py`, which is where this module's own
#      law puts a read.
#   E3 ~~`issue_refund` and `clear_refund` get NO doors. They are not
#      role-gated, so G52 does not see them, and they are equally unreachable —
#      REPORTED as the remaining half of the refund lifecycle rather than
#      mounted here on a lane's own initiative, because issuing money is
#      `BR-PAY-014`'s DR/CR pair and wants its own packet.~~
#      **CLOSED 2026-09-01 (CR-059 CS-6, task 17), in exactly the packet that
#      sentence asked for.** Both are mounted, both are gated in the SERVICE
#      first (`BR-PAY-1071`), and `POST /accounts/{id}/refunds` came with them
#      because until it existed nothing but the demo seeder could raise a
#      refund, so the approval queue this file mounts could never hold a row.
#      The struck text stays because the next reader meets its shape in
#      `g52_no_door_baseline.txt`.
#   E4 `request_refund` is gated at the ROUTE (`AdminOrClerk`) and NOT in the
#      service. CS-6 asks for the service gate *"for issue and clear"* by name,
#      and adding an unasked-for one to a 🔒 human-owned money file would be
#      this lane widening a signed rule set. REPORTED, not taken.
#   E5 `POST /accounts/{id}/refunds` takes `payment_id` in the BODY while the
#      ACCOUNT is the address. That disagreement is CS-7 (task 60, contracts):
#      the PO ruled 2026-09-01 that a refund belongs to the account, and
#      `refunds.payment_id` is still NOT NULL with no `account_id` beside it.
#      The route is shaped for the ruling; the body field goes when CS-7 lands.
#      The path segment is ENFORCED meanwhile, not decorative.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
