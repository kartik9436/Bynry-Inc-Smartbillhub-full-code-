# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2031 — every step of the transfer wizard has no door: seven
#           role-gated actions, 386 lines, and `customers/api.py` mounts
#           `path("transfers", transfers_list)`, a LIST.
#           DEF-2030 — the whole disconnect ladder has no door: eleven
#           role-gated actions, 930 lines, same shape one file over.
#           Both found by G52 (`10-scripts/gates/g52_role_gated_doors.py`) and
#           both named in `g52_no_door_baseline.txt`, whose lines this file
#           deletes.
# Story:    US-CUS-027 (S89 · TRF-02) · CR-030 W7 tasks 7.1–7.11 (S90 · DSC-02)
#           Screens: S89 · S90
# Rules:    BR-SHL-019 (ONE transactional commit per wizard) · BR-SHL-025
#           (server-enforced RBAC) · BR-CUS-039 (certified mail is REQUIRED on
#           the final tier) · BR-CUS-100 (a tier-3 cut must not be schedulable
#           on an unrecorded service) · BR-CUS-103/104/105 (the cut's money
#           rules, PO 2026-08-25) · BR-BIL-007 (the reconnection fee is the
#           tenant's own `CC-RECON` charge code, NEVER a literal) ·
#           CLAUDE.md hard rule 1 (tenant scoping — `require_tenant` on every
#           route below) · hard rule 2 (money 4 dp stored / 2 dp displayed —
#           this layer computes NO figure and rounds nothing) · hard rule 7
#           (every money action writes `audit_log` — written by the services)
# Ruling:   decision log 2026-08-28, "THREE WORKFLOWS GET THEIR DOORS — AND THE
#           TWO WIZARDS GET **OPPOSITE** ANSWERS TO THE SAME QUESTION".
# Questions: OQ-374 · OQ-382 · OQ-384 · OQ-385 — OPEN, all refused by the
#           services below, and NONE softened here. ✅ **`OQ-383` IS CLOSED**
#           (PO 2026-09-20, `BR-CUS-1083`) and this line named it as open
#           until that day — `record_visit` below is its door.
# Tests:    06-backend/tests/test_def2030_2031_wizard_doors.py
# Impacts:  config/urls.py inclusion · 07-frontend transferDisconnectEndpoints.ts
#           (its six addresses, unchanged) · g52_no_door_baseline.txt
# ───────────────────────────────────────────────────────
"""The doors for `TRF-02` (the transfer wizard) and `DSC-02` (the disconnect ladder).

Its own module rather than more lines in `apps/customers/api.py`, on the
`apps.customers.service_request_api` precedent: `api.py` is 1,283 lines and is
edited by several lanes at once, and hard-won law 11 is what a shared file costs.
Nothing here is imported by `api.py` and nothing there is imported by this;
`config/urls.py` includes both.

THIN by law (B8/LAW 0): every write goes through the service that owns it, every
read through that service's published read. **No ORM, no figure and no rounding
in this file.** Refusals are the services' own, translated (never softened) into
catalog exceptions the BE-02 handler renders.

═══════════════════════════════════════════════════════════════════════════════
THE TWO WIZARDS GET OPPOSITE ANSWERS TO THE SAME QUESTION, AND THAT IS THE POINT
═══════════════════════════════════════════════════════════════════════════════

Both wizards post ONE payload to ONE address, and both sit on a STAGED service
layer. So the same question falls out of each: does the one door run the stages
server-side in one transaction, or does each stage get a route?

**The transfer: orchestrated. The ladder: not.** The deciding test is not the
shape of the service layer — it is how much real-world time separates the stages,
and whether a precondition of a later stage is a document that arrives in the post.

`TRANSFER` — five writes, one clerk, ninety seconds, `POST /transfers/commit`
runs all five inside ONE `transaction.atomic()`. The reason is not tidiness:
`uq_transfers_open_from` allows ONE open transfer per outgoing account, and
`US-CUS-027 §8` records that **no screen shows a transfer in flight**. Five
routes means five transactions, so a failure at stage 4 strands an
`in_progress` row that blocks that account from ever being transferred again and
that nobody can see to cancel. One transaction rolls the whole thing back
instead, and the clerk retries. See the decision log for the worked race.

`LADDER` — eleven acts over three weeks, each its own route. `schedule_cut`
refuses unless the case is at `TIER 3` **and** `assert_service_proved` passes,
and that proof is a certified-mail receipt signed by the recipient. Collapsing
the ladder into one door would mean manufacturing that receipt inside one HTTP
request — which is precisely what BR-CUS-039 and BR-CUS-100 exist to prevent,
and it ends with a household losing water on a letter nobody posted.

**BR-SHL-019 is satisfied in both cases.** The disconnect WIZARD's one commit is
`schedule_cut` and that is the one address `DisconnectWizard.tsx` posts to. The
other ten actions are not wizard steps; the ladder is a case file, not a wizard.

═══════════════════════════════════════════════════════════════════════════════
WHAT THIS LAYER REFUSES TO DO
═══════════════════════════════════════════════════════════════════════════════

* **It resolves no open question.** `OQ-374` · `OQ-382` · `OQ-384` · `OQ-385`
  are OPEN. ✅ `OQ-383` was in this list until 2026-09-20 and is CLOSED — the PO
  named four crew outcomes and `record_visit` carries them (`BR-CUS-1083`). The services already refuse correctly on each; these routes
  carry those refusals to the client verbatim and soften none. Nothing here
  reads `new_service_block_for()` — `OQ-384` has no subject yet, and consuming a
  three-valued block with no ruled subject would be choosing one.
* **It substitutes no figure.** Every money value on every response is the
  service's own `{stored, display}` pair, `None` where the service says `None`.
  `BR-BIL-007`'s reconnection fee travels exactly as the service answers it.
  ⚠ **THIS READ *"absent on every tenant in this tree (`DEF-700`, no seed
  creates `CC-RECON`)"* UNTIL 2026-09-21 AND IS NO LONGER TRUE**
  (`DEF-CUS-6071`): the PO ruled *"reconnection fee is $75 - fix the code and
  seed"*, the code is `RECON`, and a provisioned tenant has it at `$75.00`. An
  absent row is still a real state and still travels as absent; it is simply
  not the default any more.
* **It computes no date.** `DSC-02.3`'s earliest lawful cut is the notice date
  plus the statutory period rolled past weekends and public holidays, and
  nothing in this product computes that roll. `cut_on` is the caller's, exactly
  as `ScheduleCutPlan` declares.
"""

from datetime import date
from types import SimpleNamespace
from typing import Any

from django.db import transaction
from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.customers import disconnect_reads, disconnect_visits, disconnects, selectors, services, transfers
from core import errors
from core.permissions import AdminOrClerk
from core.tenancy import require_tenant

# ── the shapes every view here shares ──────────────────────────────────────


def _actor(request: Any) -> Any:
    """The acting user for the B12 §6a service shape.

    Restated rather than imported from `apps/customers/api.py` for the reason
    `newConnectEndpoints.ts` gives about its own twin: no coupling between two
    files different lanes hold. The role is server-attached by the identity
    layer (BE-04) and is NEVER client input (BR-TEN-003).
    """
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
    )


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="customers.payload_not_object")
    return data


def _as_catalog_refusal(refusal: disconnects.DisconnectRuleError) -> errors.BizError:
    """A `DisconnectRuleError`, as the ONE catalog exception G9 allows.

    **This function is named in `disconnects.DisconnectRuleError`'s own
    docstring**, verbatim: *"the API boundary that mounts S90 translates this
    exception into one catalog code carrying `br_ref` and this sentence, exactly
    as `apps/payments/api._as_catalog_refusal` already does for its own."* This
    is that boundary. Without it every refusal in the ladder — a medical
    protection in force, a case below tier 3, a missing certified receipt —
    reaches a clerk as an HTTP 500 and a stack trace.

    ONE code for all of them (422 `BIZ_COMPLETENESS`), for the reason payments
    and billing both give: every refusal that arrives here has the same shape —
    *this cannot be done as asked, here is the rule, here is the sentence a
    clerk can act on* — and picking among the nine BIZ codes per refusal would
    be this layer INTERPRETING rules it does not own.

    ⚠ **The refusal's own sentence travels in `params.detail` and its rule in
    `br_ref`.** `G32` is a ratchet — no `message_key` may be raised that does not
    resolve — and `DisconnectRuleError` deliberately carries no key, so this
    layer mints none: it reuses one that already resolves and puts the service's
    words where `BR-SHL-020`'s modal renders them. The service's `code` rides
    alongside so a screen can branch without parsing English.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(refusal, "br_ref", None) or "BR-CUS-039",
        message_key="customers.disconnects.refused",
        params={"detail": str(refusal), "code": getattr(refusal, "code", None)},
    )


#: ⛔ **`CR-125-BRC07` — THE REFUSAL SAID *"Enter the cut_on."* TO A CLERK.**
#:
#: Measured by opening `?step=5` over an empty form and pressing the danger
#: button: the server refused with `customers.date_required`, and all eleven
#: catalogues interpolate `{{field}}` — which carried the PYTHON KEYWORD NAME.
#: So every locale rendered a function's parameter name at a billing clerk, on
#: the screen that cuts somebody's supply off. **B14 rule 32**: no internal code
#: in clerk-facing copy, and this was not even a product code.
#:
#: ⚠ **FIXED HERE AND NOT IN THE CATALOGUES, ON PURPOSE.** The catalogue string
#: is RIGHT — it names a field and asks for a date — and eleven translations of
#: it already exist. What was wrong is the VALUE we put into it. Rewording the
#: string would mean eleven re-translations to fix a bug that is one dictionary
#: deep, and every locale file belongs to another lane.
#:
#: ⚠ **THE MACHINE HANDLE STILL TRAVELS, UNDER `name`.** A client that wants to
#: focus the offending input needs the field's real name; a client rendering a
#: sentence needs the label. Two facts, two keys — rather than one key that
#: could only ever serve one of them.
#:
#: A field with no row here falls back to its own name, which is exactly the old
#: behaviour: a new date field is no worse off than before, and adding a row is
#: the whole of making it right.
DATE_FIELD_LABELS: dict[str, str] = {
    "cut_on": "cut date",
    "on_date": "date",
    "served_on": "date it was served",
    "signed_for_on": "date it was signed for",
    "as_of": "date",
}


def _required_date(value: Any, field: str) -> date:
    """An ISO date the caller MUST supply. Never defaulted to today.

    A disconnect act dated by the server is an act whose real date nobody can
    reconstruct — and every one of these is evidence in a dispute about somebody
    losing supply (hard rule 7). `as_of` is the one exception and it is
    documented at its own call sites.

    ⚠ The refusal names the field in WORDS and never in code —
    `DATE_FIELD_LABELS` above carries the whole reason.
    """
    label = DATE_FIELD_LABELS.get(field, field)
    if value in (None, ""):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.date_required",
            params={"field": label, "name": field},
        )
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.date_not_iso",
            params={"field": label, "name": field, "value": str(value)},
        ) from bad


def _optional_date(value: Any, field: str) -> date | None:
    return None if value in (None, "") else _required_date(value, field)


def _as_of(request: Any) -> date:
    """`as_of` — the day the ladder is being evaluated ON.

    Defaulted to the caller's `as_of` when given and to the tenant's today when
    not, because it is a QUERY parameter of the rules ("is this account
    protected today?") and not a record of when an act happened. Every field
    that records an act — `on_date`, `served_on`, `cut_on` — is required above.
    """
    supplied = request.data.get("as_of") if isinstance(getattr(request, "data", None), dict) else None
    supplied = supplied or request.query_params.get("as_of")
    return _optional_date(supplied, "as_of") or disconnects.seams.tenant_today()


# ══════════════════════════════════════════════════════════════════════════
# TRF-02 · THE TRANSFER — ONE DOOR, FIVE WRITES, ONE TRANSACTION
# ══════════════════════════════════════════════════════════════════════════


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # mirrors transfers.py's @require_role, never wider
def transfer_commit(request: Any) -> Response:
    """`POST /transfers/commit` — `TRF-02.5`'s `Complete the sale ✓`.

    ⛔ **REWRITTEN 2026-09-01 — `BR-CUS-1030`. THIS DOOR NOW REASSIGNS AN
    ACCOUNT; IT USED TO CREATE ONE.** PO ruling, verbatim: *"dont create new
    account - we reassing that account - bascailly I have sold my property - so
    account get transfer to new person or business"*.

    The wizard sends ONE `TransferCommitPlan` and this view runs the five staged
    writes inside ONE `transaction.atomic()`:

        start_transfer      from_account_id
        set_new_customer    customer{display_name · kind · identity}
        set_sale_date       sold_on
        acknowledge_money   (nothing to elect — the debt follows the property)
        reassign_account    customer{...}

    **Django nests `atomic()` as savepoints**, so each service keeping its own
    `transaction.atomic()` is correct and untouched — the outer block is what
    makes the run all-or-nothing.

    ⚠ **THE BUYER'S BLOCK IS SENT TWICE AND VALIDATED TWICE, ON PURPOSE.** Step
    2 validates it so the clerk is refused in front of the form they are typing
    into (`BR-CUS-1023`: name the missing thing at the door), and
    `reassign_account` validates it again because a service-layer caller — a
    management command, another module, the next lane — does not have to pass
    through step 2. `transfers` stores no identifier between the two, and that
    is deliberate: a government identifier belongs in customers' encrypted
    column and nowhere else (`BR-CUS-1020`).

    ⚠ **THE ROLLBACK IS THE FEATURE, NOT THE TIDINESS.** `uq_transfers_open_from`
    allows ONE open transfer per account and no screen shows a transfer in
    flight (`US-CUS-027 §8`). Without the outer block, a refusal at stage 5
    would strand an `in_progress` row that blocks that account from ever being
    sold again and that nobody can find to cancel. Here, zero rows survive and
    the clerk simply goes again.

    ⚖️ **NO MONEY MOVES, AND THAT IS NOW THE RULING RATHER THAN AN ABSENCE.** PO
    2026-09-01: *"money follow property - new owner boutght everything property
    + debt also"*. The account carries its own ledger, so **the balance never
    moves because the thing it sits on never moves** — and the response carries
    `reassignment.balance_at_sale` and `.deposit_at_sale`, the figures as they
    stood at the moment of sale, so what the buyer took on is on the record.

    ⛔ **AND NOTHING ALREADY ISSUED TO THE SELLER IS TOUCHED** — hard rule 4.
    Their invoices, payments and journal entries stay exactly as issued, in
    their name, for ever.

    ⚠ **`reads` IS GONE FROM THIS PAYLOAD.** It carried ONE meter read serving a
    closing account and an opening one (`BR-MET-128`'s transfer event). **A sale
    closes no account and opens none**, so there is no final read and no opening
    read: the meter keeps running on one unbroken account and the next ordinary
    read serves it. A lane that puts `reads` back is re-creating the second
    account this ruling removed.

    **200, not 201.** The old door created an account and answered `Created`.
    This one changes who an existing account belongs to; nothing was created.
    """
    require_tenant(request)
    plan = _payload(request)
    actor = _actor(request)
    # CR-070 wave P — the changeover read the clerk ticked on STEP 2 rides the
    # one plan, because this door is one transaction and there is no transfer
    # row for a second call to name (see `getTransferMoney`'s own docstring).
    buyer = {
        "customer": plan.get("customer"),
        "field_visit": plan.get("field_visit"),
        # ⊕ DEF-CUS-10255 — the buyer's own panels (image 07): co-buyers,
        # documents, Tax, Discounts and Preferences, in the move-in's shapes.
        "buyer_account": plan.get("buyer_account"),
    }
    # Refused BY NAME before any write, as the field visit is just below.
    transfers.buyer_account_extras(plan.get("buyer_account"))
    # ⊕ `DEF-CUS-6392` — the field-visit rows are refused BY NAME before any
    # write, exactly as the move-in does (`services._field_visit`): a row with
    # no job type must reach the clerk with everything still on screen, never
    # as a sale that rolled back five writes to say so.
    services._field_visit(plan.get("field_visit"))
    with transaction.atomic():
        started = transfers.start_transfer(actor, {"from_account_id": plan.get("from_account_id")})
        transfer_id = started["id"]
        transfers.set_new_customer(actor, transfer_id, buyer)
        transfers.set_sale_date(actor, transfer_id, {"sold_on": plan.get("sold_on")})
        # ⛔ **NOTHING IS ELECTED ANY MORE AND NO KEY IS READ FROM THE PLAN.**
        # `elect_money` took `deposit_carry` and `arrears_follow` from the clerk
        # because four signed rules disagreed and no open question covered it.
        # `OQ-1252` was raised and answered inside the hour — the debt follows
        # the property — so a box for the clerk to clear would be a control that
        # can reverse a PO ruling.
        transfers.acknowledge_money(actor, transfer_id)
        committed = transfers.reassign_account(actor, transfer_id, buyer)
    return Response(committed, status=200)


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # mirrors transfers.py's @require_role, never wider
def transfer_buyer_preview(request: Any) -> Response:
    """`POST /transfers/buyer-preview` — **`TRF-02.2`'s missing feedback line.**

    ⛔ **NEW 2026-09-20.** The conformance walk of that day, on step 2:
    *"feedback `Matched an existing customer. C-00902 · Vasquez, M., on the
    phone number.` — NOT BUILT: the match happens server-side at commit and the
    clerk is never told."* It is drawn on p126 and it is the step's whole
    premise — *"Matched first, created only on no match"* — stated back about
    the buyer actually being typed.

    ⚠ **A POST THAT WRITES NOTHING, WHICH IS UNUSUAL AND IS DELIBERATE.** It is
    a POST because a government identifier may not travel in a query string:
    a URL is logged by every proxy, appears in a browser's history and lands in
    the referer header of the next request. `BR-CUS-092`(c) — *"the full value
    is never in a list response, an export, a log line or an audit `details`
    blob"* — is about exactly that class of leak, and a `GET` would put an SSN
    in three of them at once. The idempotency this gives up is worth nothing
    here, because there is nothing to be idempotent about.

    ⚠ **IT CREATES NO TRANSFER ROW, AND THAT MATTERS MORE THAN IT LOOKS.**
    `uq_transfers_open_from` allows ONE open transfer per account and no screen
    lists a transfer in flight (`US-CUS-027 §8`), so a preview that started a
    job would leave an account that can never be sold again and that nobody can
    find to cancel. This takes no `from_account_id` at all.

    **200 always, or a refusal.** A buyer nobody has seen before is a real
    answer and not an error — `verdict: "none"` — which is the reading
    `identity_match.recognise` already takes of a search that found nothing.
    """
    require_tenant(request)
    return Response(transfers.preview_buyer(_actor(request), _payload(request)))


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # mirrors transfers.py's @require_role, never wider
def transfer_account_preview(request: Any) -> Response:
    """`POST /transfers/account-preview` — **step 1's answer, the moment the
    account is picked.** Writes nothing.

    ⊕ 2026-09-23 (`DEF-CUS-6395`, `DEF-CUS-5182`). It serves the refusal the
    commit WOULD raise (`transfers.sale_refusal`, one function for both doors),
    the seller as the account names them, whether the account is the premises'
    master account, and the billing cycle, current period, next bill and ledger
    start the wizard used to hard-code as *"Not available yet"*.

    A POST for `buyer-preview`'s reason and for consistency with it: it is a
    question put to the sale about to happen, not a resource read.
    """
    require_tenant(request)
    return Response(transfers.preview_account(_actor(request), _payload(request)))


@api_view(["GET"])
@permission_classes([AdminOrClerk])  # the money statement's own gate, mirrored
def transfer_money(request: Any, transfer_id: str) -> Response:
    """`GET /transfers/{id}/money` — `transfers.money_statement`, a pure read.

    No audit row: it moves nothing and decides nothing, exactly as
    `discounts.deposit_position` does.

    ⚠ **`deposit_carried` IS NULL WHENEVER `BR-CUS-057`'s INTEREST CANNOT BE
    READ, AND THAT IS THE FEATURE** — see the endpoint file's own block. The
    figure travels absent with its reason in `unavailable[]`; nothing here
    substitutes the principal.

    ⚠ **Keyed by a TRANSFER id, and under the one-door commit above there is no
    transfer row until the commit succeeds.** So this serves a transfer the
    seeder left behind or one already committed — `TRF-02.4`'s figures cannot be
    read before the thing they describe exists, and the step says so rather than
    printing a fixture.
    """
    require_tenant(request)
    return Response(transfers.money_statement(_actor(request), transfer_id))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def transfer_cancel(request: Any, transfer_id: str) -> Response:
    """`POST /transfers/{id}/cancel` — abandon an open transfer.

    NOT a stage, which is why it has a route while the five stages do not.
    `uq_transfers_open_from` allows ONE open transfer per outgoing account, so
    without this an account carrying an open row can never be transferred again
    — and open rows exist in this tree today, because the **demo seeder** calls
    `start_transfer`. The one-door commit above creates none of them and cannot
    clear them.

    A committed transfer cannot be cancelled: the accounts have already moved
    and hard rule 4's posture applies — a correction is a new job, never an edit
    of this one. The service refuses it.
    """
    require_tenant(request)
    return Response(transfers.cancel_transfer(_actor(request), transfer_id, _payload(request)))


# ══════════════════════════════════════════════════════════════════════════
# DSC-02 · THE LADDER — ELEVEN ACTS, ELEVEN DOORS, THREE WEEKS
# ══════════════════════════════════════════════════════════════════════════
#
# Every view below is wrapped in the same try/except: the services raise
# `DisconnectRuleError`, which is not a catalog exception, and a clerk must meet
# `BR-CUS-100` as a sentence rather than as a 500. See `_as_catalog_refusal`.


def _laddered(call: Any) -> Any:
    """Run a ladder call, translating its refusal at the boundary."""
    try:
        return call()
    except disconnects.DisconnectRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal


def _account_or_404(account_id: str) -> Any:
    """⛔ **DEF-2130 — RESOLVE THE ACCOUNT BEFORE ANSWERING ANYTHING ABOUT IT.**

    `ladder_state`, `protection_check` and `reconnection_terms` do no existence
    check of their own: they DERIVE an answer from queries that RLS correctly
    returns empty for. So without this line a Lonestar Ridge admin asking for a
    Brazos Bend account id got **HTTP 200** carrying `runs: false` and
    `halt_code: nothing_owed` — the same answer a real account owing nothing
    gives.

    Nothing leaked and existence was not disclosed, so this was never an
    isolation breach. It is the posture that was wrong: **HR-1 says a
    cross-tenant id is a 404, and 200 is neither 404 nor 403.** A door that
    computes an answer about a row it cannot see is a door that will one day
    compute one from a row it can.

    `selectors.account_or_404` is customers' own resolver and raises the 404
    that never distinguishes absent from foreign — this layer re-implements
    none of it.

    ⚠ **THE WRITES NEED IT TOO — THIS PARAGRAPH SAID THE OPPOSITE UNTIL
    DEF-CUS-9648 (2026-10-04).** It read *"every one of them goes through a
    service that resolves the account itself and refuses"*. Measured: the nine
    case writes handed the raw path segment to a query, so `None` answered
    **500** (`ValidationError: “None” is not a valid UUID`) and an absent uuid
    answered **422** *nothing owed* — DEF-2130's exact posture on the write
    side. Each write now calls this first.
    """
    return selectors.account_or_404(account_id)


# ── the reads `DSC-02` opens on ────────────────────────────────────────────


@api_view(["GET", "POST"])
@permission_classes([AdminOrClerk])
def account_protections(request: Any, account_id: str) -> Response:
    """`GET` the protection panel · `POST` a new hold. Two verbs, one resource.

    ONE view rather than two, on the `payments/api.write_offs` precedent, and
    for a reason worth writing down: **two `path()` entries on one pattern is a
    route the router can never reach.** Django resolves the FIRST match and
    stops, so a second view mounted at `accounts/<id>/protections` would be dead
    code that every test passes over — hard-won law 2 wearing a URL. This lane
    wrote exactly that bug and `G52` caught it, which is the check working.

    ── GET — `DSC-02.2`'s protection panel ──

    ⚠ **`all_clear` IS COMPUTED OVER THE THREE PROTECTIONS THAT EXIST**, not
    over `DSC-02.2`'s ten: six of the ten are unbuilt (`DEF-691` / `BR-CUS-101`).
    It is served under its own name and a screen must NOT render it as the drawn
    `All clear` chip — a green summary over six unasked questions is a fabricated
    clearance on the screen that authorises a cut. The three-valued `outcome`
    (`pass` · `fail` · **`unavailable`**) is what carries that honestly, and
    `unavailable` is NOT `pass`.

    ── POST — record a medical or weather hold (`BR-CUS-039`) ──

    **This is the act that stops a cut**, so its dates are the caller's and
    never the server's: `effective_from` is required, and `expires_on` is
    optional because a protection with no stated end is a real thing — the
    check payload's `lifetime` field is what says which.
    """
    require_tenant(request)
    _account_or_404(account_id)  # DEF-2130
    if request.method == "GET":
        return Response(
            _laddered(lambda: disconnects.protection_check(account_id, as_of=_as_of(request)))
        )
    body = _payload(request)
    return Response(
        _laddered(
            lambda: disconnects.record_protection(
                _actor(request),
                account_id,
                kind=body.get("kind"),
                effective_from=_required_date(body.get("effective_from"), "effective_from"),
                expires_on=_optional_date(body.get("expires_on"), "expires_on"),
                set_by=body.get("set_by"),
                reference_id=body.get("reference_id"),
                note=body.get("note"),
            )
        ),
        status=201,
    )


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def account_ladder(request: Any, account_id: str) -> Response:
    """`GET /accounts/{id}/ladder` — `DSC-02.3`'s ladder panel plus the open case.

    Two facts on one payload because the screen shows them together: where the
    ladder says this account stands, and the case row (if any) that records it.

    ⚠ **`scheduler` RIDES EVERY ANSWER AND IT SAYS NOTHING ADVANCES ITSELF**
    (`disconnects.NO_SCHEDULER`, `DEF-320`): nothing in this product reads a date
    and acts on it. A screen that hid that would imply a case walks its own
    ladder, and it does not — `advance` below is a person clicking.

    ⚠ **`tier` IS NULLABLE AND `TIER_UNMAPPED` IS A REAL VALUE.** Payments'
    `second_5_day` rung has no chip in B18 and `tier_for_rung` refuses to invent
    one: mapping it onto a tier would tell a regulator a certified letter went
    out.

    ⚠ **`cut_floor` JOINED THIS PAYLOAD ON 2026-09-12 — `OQ-CUS-1810` CLOSED.**
    The earliest date a cut may lawfully happen: the FINAL notice's SERVED date
    plus the tenant's own period from `BR-PAY-017` (`final_notice_hours`),
    counted in **business days** and rolled past that tenant's own
    `holiday_calendars` rows. It rides HERE rather than on a new route for two
    reasons: the ladder is the resource that owns notices, and step 3 of the
    wizard needs the tier, the served dates and the floor together — one call
    or three sentences saying *not served to this screen*.

    ⚠ **IT IS A WARNING AND NOT A GUARD, AND THE PAYLOAD SAYS SO.** PO,
    verbatim: *"(b) Floor it at the notice date itself now… - give a message but
    allow it"*. `enforced: False` travels with it, no validator reads it, and
    the date field gets NO `min` — a `min` would silently stop a clerk typing
    the date at all, which is the opposite of what was ruled.

    ⚠ **NO SERVED NOTICE MEANS NO FLOOR, STATED AS AN ABSENCE.** A notice is
    ISSUED by the ladder and SERVED by a person outside the product;
    `served_on` is null until somebody records the proof. A floor counted from
    an ISSUE date would be a legal claim about a letter nobody has confirmed
    arrived, so it answers `null` with a reason code and the screen says the
    period cannot be counted yet.
    """
    require_tenant(request)
    _account_or_404(account_id)  # DEF-2130
    as_of = _as_of(request)

    def read() -> dict[str, Any]:
        state = disconnects.ladder_state(account_id, as_of=as_of).as_dict()
        case = disconnects.open_case_for(account_id)
        state["case"] = None if case is None else disconnects.case_payload(case)
        # ⚠ **`DEF-CUS-6052` — THE CASE NUMBER, LIFTED TO THE TOP LEVEL, THE
        # WAY `disconnect_reads.list_row` ALREADY LIFTS IT, FOR THE SAME
        # REASON.** That row's own words: *"`case` is documented as an opaque
        # record that no screen reads a field from, and this is the one field a
        # screen must."* Until 2026-09-20 this payload carried the reference
        # only INSIDE `case`, so `DSC-02.1`'s drawn `Case reference` row had
        # nothing at the level it reads and was bound to `sequence` instead —
        # and printed the word **service** over `DSC-26-0001`, on a real case,
        # with `tsc` and every test green because both sides are strings.
        #
        # ⚠ **IT IS THE HUMAN REFERENCE AND NEVER `case_id`** (B14 rule 31: no
        # database id is ever the visible value of a field). `DSC-26-0001`, not
        # a uuid.
        state["case_no"] = None if case is None else case.case_no
        # The SAME decision function as the list row, so *"a case with no
        # number"* cannot come to mean two things on two screens. It is asked
        # only when a case EXISTS: `case_reference_absence(None)` answers
        # `NO_CASE_TO_NUMBER`, whose sentence opens *"This account is on the
        # list because a protection is in force"* — true of a row on S90 and a
        # false statement on a wizard. With no case the payload already says
        # `case: null`, which states that absence once and correctly.
        state["case_no_unavailable"] = (
            None if case is None else disconnect_reads.case_reference_absence(case)
        )
        state["cut_floor"] = _cut_floor_for(case)
        # ⚠ **`DEF-CUS-7680` — THE STEP-1 PRE-FLIGHT, AND IT RIDES HERE FOR THE
        # REASON `cut_floor` DOES.** Four of the reasons `POST
        # /disconnects/schedule` refuses for are decided by the CASE, and the
        # case is what this route is about; a route of its own would be a
        # second read of the same row and one more round trip on the step a
        # clerk is already waiting on. It is a PREVIEW — `schedule_cut` re-runs
        # all of it, and `disconnect_reads.schedule_readiness` says so at
        # length. Additive: every existing key is untouched.
        state["schedule_readiness"] = disconnect_reads.schedule_readiness(
            account_id, as_of=as_of
        )
        return state

    return Response(_laddered(read))


def _cut_floor_for(case: Any) -> dict[str, Any]:
    """The earliest lawful cut for one case, or the reason there is none.

    ⚠ **EVERY INPUT IS READ AND PASSED IN; NOTHING IS FETCHED INSIDE THE
    ARITHMETIC** — `BR-TEN-043`, and the same posture `late_fee` takes for the
    grace clock. `cut_date` is a pure module for that reason: it can be tested
    against a May 2026 holiday without seeding one, and it cannot behave
    differently between this screen's preview and the act it previews.
    """
    from apps.customers import cut_date, seams

    if case is None:
        return cut_date.as_dict(
            cut_date.cut_floor(
                notice_served_on=None,
                final_notice_hours=0,
                holidays=frozenset(),
                reason_when_absent="no_open_case",
            )
        )
    settings = seams.tenant_collections_settings()
    # `final_notice_hours` is the FINAL tier — the one the cut is measured from.
    # `notice_tier_days` ([10, 5]) governs the tiers ABOVE it and is not this
    # period; using it here would measure the cut from the wrong letter.
    hours = int(settings.get("final_notice_hours") or 0)
    proof = disconnects.service_proof_for(case, tier=disconnects.TIER_3)
    served = proof.get("served_on")
    floor = cut_date.cut_floor(
        notice_served_on=date.fromisoformat(served) if served else None,
        final_notice_hours=hours,
        holidays=seams.tenant_holidays(),
        # `True` once a tenant has saved its own number over the seeded default,
        # so a screen can say *your period* rather than implying ours is law.
        tenant_configured=_collections_saved(),
        reason_when_absent=(
            "notice_not_served" if proof.get("recorded") is not None else "no_notice_at_this_tier"
        ),
    )
    payload = cut_date.as_dict(floor)
    payload["final_notice_hours"] = hours
    return payload


def _collections_saved() -> bool:
    """Whether this tenant has SAVED its collections page, as opposed to running
    on the seeded defaults `settings_families.merge` fills in behind them. The
    row itself is seeded at migration and rewritten in full on every save, so
    the honest test is whether the stored document carries the key at all."""
    from apps.tenancy import models as tenancy_models
    from core import tenancy as core_tenancy

    row = tenancy_models.TenantSettings.objects.filter(
        tenant_id=core_tenancy.current_tenant_id()
    ).first()
    document = getattr(row, "collections", None) if row else None
    return isinstance(document, dict) and "final_notice_hours" in document


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def account_reconnection_terms(request: Any, account_id: str) -> Response:
    """`GET /accounts/{id}/reconnection-terms` — `DSC-02.4`'s quote.

    ⛔ **`fee` IS NULLABLE AND NOTHING HERE SUBSTITUTES A NUMBER FOR IT.**
    `BR-BIL-007`: the amount is the tenant's own charge code, and
    `reconnection_terms` answers `None` with a reason when that code is not
    configured or is not a flat amount. ⚠ **THIS READ *"`DEF-700` IS THE STATE
    OF THIS TREE — no seed creates `CC-RECON`"* UNTIL 2026-09-21, AND BOTH
    HALVES ARE NOW FALSE.** The PO ruled that day — *"reconnection fee is $75 -
    fix the code and seed"* — and the code is spelled **`RECON`**, seeded at
    **$75.00**, on every provisioned tenant. A tenant that deletes its row is
    still a real state, which is why the absence stays; it is no longer the
    DEFAULT one, and a literal here would still be quoting a price the product
    cannot charge.

    ⚠ **`timing` IS `BR-CUS-104` AND IT IS NOT DECORATION:** the fee becomes owed
    AT THE CUT, so what a customer must clear to be reconnected is their arrears
    PLUS the fee. ⚠ **AND THIS PARAGRAPH SAID `posting` REPORTS THAT THE FEE
    *"reaches AR through nothing today"* AND THAT THE GATE *"lets a customer
    through short by exactly the fee"* — BOTH WERE CLOSED ON 2026-08-27 AND THE
    SENTENCE OUTLIVED THEM BY THREE WEEKS (`DEF-CUS-6071`).** `DEF-708` is
    fixed: `commit_cut` raises and ISSUES the fee, so it is in AR from the
    moment of the cut and the gate that reads AR requires it.

    ⛔ **WHICH IS WHY `to_clear` IS NOT AN ADDITION ON A CUT ACCOUNT —
    `DEF-CUS-6050`.** Once the fee is issued the position ALREADY holds it, so
    `to_clear.total` is that position read ONCE and the fee is not added to it;
    before the cut it is still arrears + fee. `to_clear.basis.fee_in_arrears`
    says which of the two this answer is, and any caller building its own figure
    out of a balance and this fee must read it. Worked on `A-11340`:
    **$8,315.00** either side of the cut, never $8,390.00 and never $8,240.00.
    """
    require_tenant(request)
    _account_or_404(account_id)  # DEF-2130
    return Response(_laddered(lambda: disconnects.reconnection_terms(account_id)))


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def account_disconnect_notices(request: Any, account_id: str) -> Response:
    """`GET /accounts/{id}/disconnect-notices` — `DSC-02.3`'s own notice table.

    `DEF-CUS-5169`. Step 3 of the disconnect wizard draws **What has gone out
    already** over this account's letters and then attests to one of them, and
    neither half was reachable: the only notice read in this file is the
    TENANT-WIDE `awaiting-proof` queue, whose rows named no account, and the
    proof door is keyed by a notice id that nothing on any screen showed a
    clerk. So a step that said *"Record it first"* had nothing behind it and
    **no cut could be scheduled from that screen on any account here.**

    ⚠ **IT IS A READ AND IT DECIDES NOTHING.** `service_proof_for` still owns
    the answer that governs a cut and `assert_service_proved` still refuses
    without it; this route only lets a screen show the rows the table already
    holds. Nothing about what a lawful cut requires moves.

    ⚠ **NO DELIVERY CLAIM RIDES ON IT.** `proof_payload` carries the PROOF
    columns and never `delivery_state`, which stays NULL with
    `DELIVERY_UNAVAILABLE` beside it (`DEF-692`) — the drawn `DELIVERED?`
    column really is unknowable today, and the screen says so in its own words.
    """
    require_tenant(request)
    _account_or_404(account_id)  # DEF-2130
    return Response(
        {"notices": list(_laddered(lambda: disconnects.notices_for_account(account_id)))}
    )


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def account_disconnect_bills(request: Any, account_id: str) -> Response:
    """`GET /accounts/{id}/disconnect-bills` — *"the bills behind that figure"*.

    Blueprint p136 draws the unpaid bills that add up to the balance a cut is
    justified by, directly under that balance, with the caption *"Three unpaid
    bills reconcile to the balance exactly."* **Nothing called anything for this
    before `CR-125-BRC07`.** A clerk was shown a figure and no way to see what
    it was made of, on the step that decides whether to cut somebody off.

    ⚠ **SERVER-PAGED (`NFR-3`) AND UNCAPPED (`NFR-5`).** `?page=` and `?per=`
    are BR-SHL-011's own grammar and clamp rather than error. The nearest
    existing route — payments' `GET /accounts/{id}/open-bills` — serves no page,
    no due date and no state; it is untouched and this does not replace it.

    ⚠ **THE SUM IS STATED ONLY WHEN THE PAGE HOLDS EVERY ROW.** The drawn
    caption is a reconciliation CLAIM, and a total over one page of several is
    not one. `bills_behind_the_balance` carries the whole reasoning.

    Read-only: no clock (`as_of` is a parameter, `BR-TEN-043`), no write, and
    every amount is the owning module's own.
    """
    require_tenant(request)
    _account_or_404(account_id)  # DEF-2130
    return Response(
        _laddered(
            lambda: disconnect_reads.bills_behind_the_balance(
                account_id,
                as_of=_as_of(request),
                page=request.query_params.get("page") or 1,
                per=request.query_params.get("per") or None,
            )
        )
    )


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def account_disconnect_panel(request: Any, account_id: str) -> Response:
    """`GET /accounts/{id}/disconnect-panel` — step 1's customer and money panels.

    Blueprint p135–p136 put **fifteen** customer facts and **six** money facts
    in front of a clerk before they cut anybody off; the shipped screen showed
    six of the fifteen. Measured 2026-09-20, thirteen of the fifteen were
    already on `GET /accounts/{id}` and simply not rendered — so this route
    carries **only the six that were genuinely missing** and repeats none of the
    others. A second copy of a fact is a fact that can disagree with itself.

    ⚠ **IT IS ADDITIVE TO THE ACCOUNT PAYLOAD AND NOT A REPLACEMENT FOR IT.**
    The wizard fetches the account as it always did and this alongside; the
    alternative was widening `account_detail_dict`, which is another lane's
    file and is read by S17, S21 and eleven other surfaces that do not want a
    payments plan lookup on every render.

    Read-only.
    """
    require_tenant(request)
    _account_or_404(account_id)  # DEF-2130
    return Response(
        _laddered(
            lambda: disconnect_reads.wizard_account_panel(account_id, as_of=_as_of(request))
        )
    )


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def account_disconnect_review(request: Any, account_id: str) -> Response:
    """`GET /accounts/{id}/disconnect-review` — step 5's review, in ONE call.

    Blueprint p140–p141. The shipped review drew six of fourteen rows and
    omitted **eight notice-and-proof facts that the wizard had already fetched
    on step 3** — at the moment a person presses a danger-tier button.

    ⚠ **IT RE-READS RATHER THAN REMEMBERS, AND THAT IS THE POINT OF THE ROUTE.**
    The alternative is the front end carrying a legal fact forward across four
    steps. This calls `service_proof_for` — the SAME function
    `assert_service_proved` uses to decide whether a cut may be scheduled at
    all — so the summary a clerk confirms and the guard that lets them confirm
    it cannot drift apart.

    ⚠ **IT DECIDES NOTHING.** No write, no state change, no gate. `POST
    /disconnects/schedule` is still the one commit (`BR-SHL-019`) and still
    re-checks everything itself.

    Read-only.
    """
    require_tenant(request)
    _account_or_404(account_id)  # DEF-2130
    return Response(
        _laddered(lambda: disconnect_reads.wizard_review(account_id, as_of=_as_of(request)))
    )


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def notices_awaiting_proof(request: Any) -> Response:
    """`GET /disconnect-notices/awaiting-proof` — the work queue for `BR-CUS-100`.

    The certified letters that went out and whose signed receipt has not come
    back. Without this the proof door below is reachable only by a clerk who
    already knows a notice id, which nothing on any screen shows them —
    hard-won law 2 one level down: a door with no handle.

    Declared BEFORE `disconnect-notices/<notice_id>/proof` so the literal
    segment `awaiting-proof` cannot be read as a notice id.
    """
    require_tenant(request)
    tier = request.query_params.get("tier") or None
    return Response({"notices": list(_laddered(lambda: disconnects.notices_awaiting_proof(tier=tier)))})


# ── the acts, in ladder order ──────────────────────────────────────────────


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def lift_protection(request: Any, protection_id: str) -> Response:
    """`POST /protections/{id}/lift` — end a hold early, with a reason.

    The reason is required by the service and is not defaulted here: lifting the
    thing that stands between a household and a cut is a decision somebody has
    to be able to reconstruct in a year (hard rule 7).

    Keyed by PROTECTION id and not by account, because an account can carry more
    than one and lifting "the protection on this account" would be ambiguous on
    exactly the accounts where it matters most.
    """
    require_tenant(request)
    body = _payload(request)
    return Response(
        _laddered(
            lambda: disconnects.lift_protection(
                _actor(request),
                protection_id,
                on_date=_required_date(body.get("on_date"), "on_date"),
                reason=body.get("reason") or "",
            )
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def open_disconnect_case(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/disconnect-case` — start a case at TIER 1.

    Idempotent on the OPEN CASE rather than on a key — `open_case` returns the
    one already open — because `uq_one_open_disconnect_case_per_account` already
    makes a second impossible and a second call is an ordinary double-click.
    200 rather than 201 for that reason: this door cannot promise it created
    anything.

    `sequence` is `BR-CUS-082`'s closed pair — a SERVICE sequence that can end in
    a cut, and a COLLECTIONS sequence that cannot — and an unknown one is refused
    by the service with both names.
    """
    _account_or_404(account_id)  # DEF-CUS-9648
    require_tenant(request)
    body = _payload(request)
    kwargs: dict[str, Any] = {"as_of": _as_of(request)}
    if body.get("sequence"):
        kwargs["sequence"] = body["sequence"]
    return Response(
        _laddered(lambda: disconnects.open_case(_actor(request), account_id, **kwargs))
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def advance_disconnect_case(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/disconnect-case/advance` — move up one rung.

    ⚠ **A PERSON CLICKS THIS. NOTHING ADVANCES ITSELF** (`DEF-320`,
    `NO_SCHEDULER` on every ladder payload). That absence is the reason this
    route has to exist at all: a ladder nothing walks and nobody can walk is a
    ladder that never moves.

    The service refuses on a protection in force, on a payment that cleared the
    arrear, and on a plan pause — each by name, and each of those refusals
    reaches the clerk as a sentence through `_as_catalog_refusal`.
    """
    _account_or_404(account_id)  # DEF-CUS-9648
    require_tenant(request)
    return Response(
        _laddered(
            lambda: disconnects.advance(_actor(request), account_id, as_of=_as_of(request))
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def record_disconnect_notice(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/disconnect-case/notices` — the notice went out.

    `tier` and `on_date` are both required. **The date is the caller's**: a
    notice dated by the server is a statutory clock started on a day nobody can
    evidence, and `BR-CUS-039`'s waiting periods are counted from it.

    ⚠ **`DELIVERY_UNAVAILABLE` rides every case this module writes** (`DEF-692`):
    recording that a notice was SENT is not the same as the product having sent
    it, and nothing here claims delivery.
    """
    _account_or_404(account_id)  # DEF-CUS-9648
    require_tenant(request)
    body = _payload(request)
    return Response(
        _laddered(
            lambda: disconnects.record_notice(
                _actor(request),
                account_id,
                tier=body.get("tier"),
                on_date=_required_date(body.get("on_date"), "on_date"),
            )
        ),
        status=201,
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def record_proof_of_service(request: Any, notice_id: str) -> Response:
    """`POST /disconnect-notices/{id}/proof` — the signed receipt came back.

    `BR-CUS-100`, and **this is the door that makes a lawful cut possible at
    all**: `schedule_cut` calls `assert_service_proved` and refuses without it.
    Before this route existed, the ladder could reach tier 3 and stop there
    forever, because the only way to record a green card was a Python shell.

    Keyed by NOTICE id, not by account: the proof is a fact about one letter.
    `served_on` is required and `signed_for_on` is optional — a receipt can be
    returned unsigned, and pretending otherwise would put a signature in the
    record that nobody wrote.
    """
    require_tenant(request)
    body = _payload(request)
    return Response(
        _laddered(
            lambda: disconnects.record_proof_of_service(
                _actor(request),
                notice_id,
                channel=body.get("channel"),
                reference=body.get("reference"),
                served_on=_required_date(body.get("served_on"), "served_on"),
                signed_for_on=_optional_date(body.get("signed_for_on"), "signed_for_on"),
            )
        ),
        status=201,
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def schedule_cut(request: Any) -> Response:
    """`POST /disconnects/schedule` — `DSC-02.5`'s `Schedule the disconnection ✓`.

    **THE DISCONNECT WIZARD'S ONE COMMIT**, and `BR-SHL-019` is satisfied by
    this single call: one payload, one address, one transaction. The ten other
    ladder routes in this file are not steps of it.

    ⚠ **IT SCHEDULES; IT NEVER CUTS.** `DSC-02`'s footer is on all five steps —
    *"nothing is cut until the scheduled date"* — and the button says
    `Schedule the disconnection ✓` and not *Cut* for that reason. `commit_cut`
    below is a separate act on the day.

    ⚠ **`cut_on` IS THE CALLER'S AND IS NOT COMPUTED HERE.** The earliest lawful
    cut is the notice date plus the statutory period **rolled forward past
    weekends and public holidays**, and nothing in this product computes that
    roll. A layer that added 48 hours would be implementing *"+2 days"* — a
    different rule that agrees with B18's fixture by luck, because Aug 22 2026 is
    a Saturday and Aug 24 the Monday, so the drawn case needs no roll at all.

    ⚠ **`services` IS `{service_code: treatment}`**, never a bare list, *"so a
    caller cannot pass a bare list of services and leave the treatment
    implied"*. A `restrictor` value is refused BY NAME — `OQ-385` is open and
    what a restricted service is CHARGED is unsigned, so building one would
    invent a price.

    ⚠ **`reason` is recorded and NOTHING BRANCHES ON IT** — `OQ-382` asks which
    of the five drawn reasons may lawfully cut and on whose authority, and it is
    open. Four of the five have no path to a cut today because none reaches
    tier 3. This route does not widen that and does not pretend it has.
    """
    require_tenant(request)
    body = _payload(request)
    scheduled = _laddered(
        lambda: disconnects.schedule_cut(
            _actor(request),
            body.get("account_id"),
            cut_on=_required_date(body.get("cut_on"), "cut_on"),
            as_of=_as_of(request),
            reason=body.get("reason"),
            services=body.get("services"),
            deposit=body.get("deposit"),
        )
    )
    return Response(_with_cut_visits(_actor(request), body, scheduled))


def _with_cut_visits(actor: Any, body: dict[str, Any], scheduled: Any) -> Any:
    """Raise step 3's *Who goes: Work order* rows AFTER the schedule — `DEF-CUS-9631`.

    The wizard drew the rows and its confirm step counted them, and the commit
    sent none: *1 work orders will be raised*, 0 raised. Now `visits:
    [{service, instruction}]` rides the commit and each row becomes a job,
    through Work's own door (`seams.raise_cut_visits`).

    ⚠ **AFTER, AND NEVER ABLE TO UNDO IT (`BR-WRK-055`).** The schedule is the
    regulated act; a visit that could not be booked is reported on the answer
    (`work_order_warnings`) and the case stays scheduled. Work's raise is its
    own savepoint, so a refused row cannot poison anything here (law 14).
    """
    from apps.customers import seams

    visits = body.get("visits")
    if not visits or not isinstance(scheduled, dict):
        return scheduled
    raised: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    try:
        answer = seams.raise_cut_visits(actor, account_id=body.get("account_id"), visits=visits)
        raised = list(answer.get("raised", []))
    except Exception as exc:  # noqa: BLE001 — every failure is one fact: not raised
        warnings.append(seams.flow_work_not_raised(str(exc) or None))
    return {**scheduled, "work_orders": raised, "work_order_warnings": warnings}


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def commit_cut(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/disconnect-case/cut` — the crew attended; supply is off.

    The act itself, on the day, and the money rules `BR-CUS-103/104/105` land
    here — all three inside `commit_cut`, none of them re-implemented in this
    layer.

    ⚠ **`final_reads` GOES TO THE METERING EVENT DOOR, event `disconnect`** —
    carried through, never written here, exactly as the transfer's shared
    reading is.

    ✅ **`OQ-383` IS CLOSED AND THERE IS A VOCABULARY NOW (2026-09-20).** This
    paragraph read *"there is no vocabulary for a crew that attended and did NOT
    cut … this route does not invent that vocabulary; it carries the absence"* —
    correct on the day it was written and false since the PO named four
    outcomes: **locked gate, access refused, paid at the door, disputed**. Their
    door is `POST .../disconnect-case/visit` below, and `BR-CUS-1083` is the
    rule. This route is still the one that records a cut that HAPPENED, and
    `CREW_OUTCOME_UNRECORDABLE` still rides its payload — amended, pointing at
    the other door rather than saying there is none.
    """
    _account_or_404(account_id)  # DEF-CUS-9648
    require_tenant(request)
    body = _payload(request)
    return Response(
        _laddered(
            lambda: disconnects.commit_cut(
                _actor(request),
                account_id,
                cut_on=_required_date(body.get("cut_on"), "cut_on"),
                as_of=_as_of(request),
                final_reads=body.get("final_reads"),
            )
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def finish_cut(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/disconnect-case/finish` — the held bill, now raisable.

    **`DEF-CUS-6063`.** A cut whose final bill billing refused leaves the supply
    off and the account on its OLD status, and until this route existed nothing
    in the product could ever finish it: `commit_cut` refuses `already_cut` by
    name and BR-CUS-107's status is written from `commit_cut` and from nowhere
    else. This is the door the clerk who fixed the data presses.

    ⚠ **IT TAKES ONE FLAG AND NO DATES, AND THE DISTINCTION IS THE POINT.**
    This paragraph read *"IT TAKES NO BODY, ON PURPOSE"* until 2026-09-21, and
    the reason it gave still holds for every DATE and every FIGURE: the window
    comes from the case's own `cut_on`, the money comes from the engine, the
    status comes from BR-CUS-107, and a parameter for any of those would be a
    clerk choosing how many days a customer pays for. **`without_bill` is not
    one of those.** PO ruling 2026-09-21: *"in single bill we have final bill
    workflow - so if clark want to complete the bill he can do it from there -
    we will need to allow clark to complete the cut request later without
    bill."* It names WHICH OF TWO ACTS the clerk is performing, and only the
    clerk knows that.

    It is read STRICTLY as the boolean `true`. A missing, null or any other
    value is the ordinary path — the safe one, the one that asks billing first
    — because hard-won law 3 says the unsafe option is the one you type.

    ⚠ **A STILL-REFUSED BILL IS A 200 WITH `finished: false`, NOT AN ERROR** —
    `raise_and_issue_cut_bill`'s own posture, for its own reason: the refusal is
    a configuration problem a human fixes and the engine's sentence is the
    useful part of the answer. The `_laddered` error shape is kept for the three
    cases where the ACT itself is refused (no case, no cut, already finished).
    """
    _account_or_404(account_id)  # DEF-CUS-9648
    require_tenant(request)
    body = _payload(request)
    return Response(
        _laddered(
            lambda: disconnects.finish_cut(
                _actor(request),
                account_id,
                as_of=_as_of(request),
                without_bill=body.get("without_bill") is True,
            )
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def record_visit(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/disconnect-case/visit` — the crew attended and did not cut.

    **`BR-CUS-1083`, PO ruling 2026-09-20**, verbatim: *"The register reflects
    reality. Today a failed visit is invisible and the case looks untouched."*
    The four outcomes are the PO's own words and the set is closed;
    `apps/customers/disconnect_visits.py` holds every rule, including WHERE each
    outcome sends the case and why three of them share a destination.

    `on_date` and `outcome` are both required and neither is defaulted. A date
    defaulted to today would put a crew at a meter on a day nobody was there —
    a failed visit is usually recorded the next morning — and an outcome
    defaulted to anything is this route choosing what happened at somebody's
    house.

    ⚠ **`note` IS OPTIONAL, LIKE `stop_by_hand`'s.** A required note would
    refuse the recording, and a refused recording leaves the case advertising a
    cut date that has passed, which is the whole defect this door closes.
    """
    _account_or_404(account_id)  # DEF-CUS-9648
    require_tenant(request)
    body = _payload(request)
    return Response(
        _laddered(
            lambda: disconnect_visits.record_outcome(
                _actor(request),
                account_id,
                on_date=_required_date(body.get("on_date"), "on_date"),
                outcome=body.get("outcome") or "",
                note=body.get("note"),
            )
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def stop_by_hand(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/disconnect-case/stop` — a human stops the ladder.

    `on_date` and `reason` are both required and neither is defaulted. This is
    the manual override on a process that ends in a household losing supply, so
    the record of who stopped it, when, and why is the whole point of the act
    (hard rule 7).

    ⚠ **`note` IS THE DRAWING'S `What happened` AND IT JOINED THIS DOOR ON
    2026-09-20 (`CR-125-BRC07`).** Blueprint p137 draws a free-text line under
    the three reason radios, captioned *"Recorded with the act and with who did
    it"*, and **there was no parameter and no column for it** — so the wizard
    asked for a sentence and dropped it, which is worse than not asking.
    `disconnects.DisconnectCase.stopped_note` carries the decision to give it a
    column, including the two cheaper options that were refused.

    ⚠ **OPTIONAL, LIKE THE SERVICE IT CALLS.** A required note would refuse a
    stop, and a refused stop means a disconnection carries on because a clerk
    had nothing to type.
    """
    _account_or_404(account_id)  # DEF-CUS-9648
    require_tenant(request)
    body = _payload(request)
    return Response(
        _laddered(
            lambda: disconnects.stop_by_hand(
                _actor(request),
                account_id,
                on_date=_required_date(body.get("on_date"), "on_date"),
                reason=body.get("reason") or "",
                note=body.get("note"),
            )
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def mark_reconnecting(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/disconnect-case/reconnecting` — they paid; a crew is on the way.

    `BR-PAY-036`, and the gate here reads AR. ⚠ **`DEF-708`: the reconnection fee
    reaches AR through nothing today**, so this gate lets a customer through
    short by exactly the `CC-RECON` amount — which is absent on every tenant in
    this tree anyway (`DEF-700`). Both are stated on `reconnection-terms` above
    and neither is papered over here.
    """
    _account_or_404(account_id)  # DEF-CUS-9648
    require_tenant(request)
    body = _payload(request)
    return Response(
        _laddered(
            lambda: disconnects.mark_reconnecting(
                _actor(request),
                account_id,
                on_date=_required_date(body.get("on_date"), "on_date"),
                # CR-070 wave P — the reconnect visit the clerk ticked.
                # `{"template_ids": [...]}`, and an absent key means nobody was
                # sent, which is the answer this door gave for its whole life.
                template_ids=body.get("field_visit"),
            )
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def restore_service(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/disconnect-case/restore` — supply is back on.

    The last rung, and the one that closes the `service_off_windows` interval
    the cut opened. `on_date` is required for the same reason every other date
    here is: a billing consequence is counted from it.
    """
    _account_or_404(account_id)  # DEF-CUS-9648
    require_tenant(request)
    body = _payload(request)
    return Response(
        _laddered(
            lambda: disconnects.restore_service(
                _actor(request),
                account_id,
                on_date=_required_date(body.get("on_date"), "on_date"),
            )
        )
    )


# ── the routes ─────────────────────────────────────────────────────────────
#
# ORDERING. Nothing here can be swallowed by `apps/customers/api.py`'s
# `accounts/<str:account_id>` matcher: the `str` converter does not match `/`,
# so a two-segment pattern cannot take a three-segment path. Within this file
# the one real hazard is `disconnect-notices/awaiting-proof` against
# `disconnect-notices/<str:notice_id>/proof`, and they differ in segment count
# as well — the literal is declared first regardless, because the next lane to
# add `disconnect-notices/<id>` would otherwise create the collision silently.

urlpatterns = [
    # ── TRF-02 · one door, five writes, one transaction ──
    path("transfers/commit", transfer_commit),
    # ⚠ **A LITERAL SEGMENT, DECLARED WITH THE OTHER LITERAL AND BEFORE EVERY
    # WILDCARD ON THIS RESOURCE** — the note above this list. `buyer-preview` is
    # two segments like `commit`, so `transfers/<transfer_id>/money` could never
    # swallow it; it is placed here anyway, because the next lane to add
    # `transfers/<id>` would create that collision silently.
    path("transfers/buyer-preview", transfer_buyer_preview),
    path("transfers/account-preview", transfer_account_preview),
    path("transfers/<str:transfer_id>/money", transfer_money),
    path("transfers/<str:transfer_id>/cancel", transfer_cancel),
    # ── DSC-02 · the reads the wizard opens on ──
    path("accounts/<str:account_id>/protections", account_protections),
    path("accounts/<str:account_id>/ladder", account_ladder),
    path("accounts/<str:account_id>/reconnection-terms", account_reconnection_terms),
    # `DEF-CUS-5169` — step 3's notice table and the notice id its proof door needs.
    path("accounts/<str:account_id>/disconnect-notices", account_disconnect_notices),
    # ── `CR-125-BRC07` · the three reads the drawn wizard needed and lacked ──
    # Each is a LITERAL third segment on `accounts/<id>/…`, so none can collide
    # with another and none can be swallowed by `api.py`'s two-segment matcher
    # (the `str` converter does not match `/`) — the note above this list.
    path("accounts/<str:account_id>/disconnect-bills", account_disconnect_bills),
    path("accounts/<str:account_id>/disconnect-panel", account_disconnect_panel),
    path("accounts/<str:account_id>/disconnect-review", account_disconnect_review),
    # ── DSC-02 · the ladder, in order ──
    path("accounts/<str:account_id>/disconnect-case", open_disconnect_case),
    path("accounts/<str:account_id>/disconnect-case/advance", advance_disconnect_case),
    path("accounts/<str:account_id>/disconnect-case/notices", record_disconnect_notice),
    path("accounts/<str:account_id>/disconnect-case/cut", commit_cut),
    # `DEF-CUS-6063` — the way out of a cut whose final bill was refused.
    path("accounts/<str:account_id>/disconnect-case/finish", finish_cut),
    path("accounts/<str:account_id>/disconnect-case/stop", stop_by_hand),
    # `BR-CUS-1083` (PO 2026-09-20) — a literal third segment on
    # `disconnect-case/`, like its five neighbours, so it can collide with none
    # of them and none of them can swallow it.
    path("accounts/<str:account_id>/disconnect-case/visit", record_visit),
    path("accounts/<str:account_id>/disconnect-case/reconnecting", mark_reconnecting),
    path("accounts/<str:account_id>/disconnect-case/restore", restore_service),
    # A literal segment BEFORE any wildcard on the same resource — see above.
    path("disconnect-notices/awaiting-proof", notices_awaiting_proof),
    path("disconnect-notices/<str:notice_id>/proof", record_proof_of_service),
    path("protections/<str:protection_id>/lift", lift_protection),
    # The disconnect wizard's ONE commit (BR-SHL-019).
    path("disconnects/schedule", schedule_cut),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2030 · DEF-2031 · G52 `g52_no_door_baseline.txt` ·
#         apps/customers/transfers.py · apps/customers/disconnects.py ·
#         07-frontend/src/features/customers/transferDisconnectEndpoints.ts ·
#         BR-SHL-019 · BR-SHL-025 · BR-CUS-039 · BR-CUS-100 ·
#         BR-CUS-103/104/105 · BR-BIL-007 · decision log 2026-08-28
# generated: 2026-08-28 by lane DOORS
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 the five transfer STAGES get no routes of their own — the one door
#      orchestrates them in one transaction. Ruled, with the worked race, in the
#      decision log; `uq_transfers_open_from` + no detail screen is the reason.
#   E2 the ladder is NOT orchestrated and gets eleven routes, the opposite
#      answer to the same question. `schedule_cut` requires a certified-mail
#      receipt that arrives days later; one door would have to fabricate it.
#   E3 `notices_awaiting_proof` and `GET .../ladder`'s `case` key are ADDED —
#      no document names either. Both exist because the acts they feed are
#      otherwise reachable only by a clerk who already knows an id no screen
#      shows them. REPORTED.
#   E4 `OQ-374 · OQ-382 · OQ-384 · OQ-385` are OPEN and every one is carried
#      through as the service's own refusal or absence. `OQ-383` was here too
#      and is CLOSED (2026-09-20, `BR-CUS-1083`, `record_visit`). Nothing here
#      reads `new_service_block_for()`.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
