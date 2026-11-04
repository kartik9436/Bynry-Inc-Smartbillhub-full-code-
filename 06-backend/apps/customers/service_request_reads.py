# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-024 (REQ-03, the applicant's form) · US-CUS-025 (REQ-01, the
#           list) · US-CUS-026 (REQ-02, the detail and its decision) — EP-CUS-09,
#           written 2026-08-25 by CR-030 W4 task 4.16 · CR-031 · B19
#           Screens: REQ-01 (list) · REQ-02 (detail) · REQ-03 (capture)
#           ⚠ **THE CITATION ARRIVED ON 2026-08-25 AND IT IS THE THING THAT
#           ACTIVATES J26.** EP-CUS-09 was written AFTER the code (hard-won law
#           8) and deliberately left these three ids out of every Trace header,
#           because `10-scripts/07-e2e-wiring-index.py` counts a story as BUILT
#           only when one is present — and gate **G12 check 5** refuses a spec
#           claiming a journey whose stories the index says are unbuilt. So
#           `J26.spec.ts` could not exist while this line said `CR-031 · B19`.
#           G10 demands `test_us_cus_0nn_tc*` the moment an id is cited; those
#           aliases land in the SAME change, in
#           `06-backend/tests/test_cr031_service_request.py` §14, exactly as the
#           epic said they must — *"adding the citation alone would make a
#           failing gate fail wider"*.
#           ⛔ **THE FRONTEND HALF IS OWED AND IS NOT HERE.** The three page
#           components (`ServiceRequestCapturePage` · `ServiceRequestsListPage`
#           · `ServiceRequestDetailPage`) still cite no US-ID, so G10's frontend
#           territory asks nothing of them. This backend citation is enough for
#           the wiring index (it unions both territories), and the asymmetry is
#           stated rather than left to be found: citing a story in a `.tsx`
#           obliges a `*.test.tsx` mention of the same id, and that is a change
#           in three other lanes' files. REPORTED, not done.
# Rules:    BR-CUS-070 (`address_as_given` served beside the resolved record,
#           never instead of it) · BR-CUS-079 (the acknowledgement's ABSENCE is
#           served, never a `sent` state) · BR-CUS-080 (outcome + outcome_ref
#           answer *"what happened to this application"* from one row) ·
#           B18 §4.6 (fees are a quote) · CLAUDE.md rule 2 (display 2 dp)
#           ── PO rulings 2026-08-24 ── BR-CUS-090 (quoted · collected ·
#           outstanding) · BR-CUS-091 (a disconnect may be decided) ·
#           BR-CUS-093 (numbered at creation) · BR-CUS-094 (seven categories) ·
#           BR-CUS-095 (the tenant's document checklist)
#           ── 2026-08-25, PO ── BR-CUS-106 (the `AGE` accent is SEVEN DAYS,
#           inclusive — decision D4 CLOSED; `list_row` serves `age_is_accented`
#           where it refused to before)
#           ── 2026-08-25, B18 task 4.12 ── BR-CUS-067 (the two-level sub-type
#           tree, served WITH its parent) · BR-CUS-094 again (`legacy` /
#           `selectable` travel with the code, so a legacy category reads as
#           picked-and-not-pickable rather than being re-labelled by omission)
# Questions: OQ-355 · OQ-356 (STILL OPEN) · OQ-357 ✅ CLOSED 2026-09-23 · OQ-351 ✅ CLOSED
# Defects:  DEF-632 (ruled → BR-CUS-092, encryptor not this lane's) ·
#           DEF-634 ✅ · DEF-635 ✅ · DEF-637 ✅ · DEF-638 12.a ✅
# Tests:    06-backend/tests/test_cr031_service_request.py
# ───────────────────────────────────────────────────────
"""CR-031 — the READ MODEL the three request screens are built against.

READ-ONLY by law (B8/LAW 0): no writes, no ORM outside this module's own five
tables, and every absence served as an absence.

────────────────────────────────────────────────────────────────────────────
THREE ABSENCES CAME OFF THIS PAYLOAD ON 2026-08-24, AND TWO STAYED
────────────────────────────────────────────────────────────────────────────
The discipline G38 enforces on the frontend — *a stated absence cites the row
that will kill it* — cuts both ways: **when the row closes, the absence must go**,
or the screen keeps apologising for something that has been fixed.

**GONE, each with the ruling that killed it:**
  * `number_absence` (DEF-634) → **BR-CUS-093**, numbered at creation. It is
    still served for a row that predates the ruling, because those genuinely
    carry no number and nothing back-fills them — but it is now the exception,
    and it names the RULE rather than an open defect.
  * `fees.total_absence` (DEF-637) → **BR-CUS-090**. The payload carries
    `quoted`, `collected` and `outstanding` as real money.
  * `documents.checklist_absence` (OQ-351) → **BR-CUS-095**. The payload carries
    the tenant's ticked list and what is unmet.
  * `decision.disconnect_absence` (DEF-638 12.a) → **BR-CUS-091**. The option is
    decidable and carries no special badge.

**STAYED, and each is still an open question:**
  * `conditions.count_differs_from_design.tracks = "OQ-355"` — the screen prints
    *"4 of 5"* and four are identifiable. Nothing prints a `5` it cannot itemise.
  * `decision.undrawn_verdict_absence.tracks = "OQ-356"`.
  * `applicant.acting_for_absence.tracks = "DEF-638"` — still no column, no
    vocabulary and no ruling.

**WENT, BECAUSE THE FACT ARRIVED (2026-09-15, BR-CUS-092(a) finished):**
  * `applicant.identifier_absence` → the SSN landed 2026-08-27 and is served as
    `identifier.ssn_last4`.
  * `applicant.drivers_licence_absence` and `applicant.date_of_birth_absence` →
    both landed 2026-09-15 on the PO's ruling of that date. The licence is
    served as `identifier.drivers_licence_last4`; the date of birth is served in
    full, because nothing signed masks it (`BR-CUS-1020`).

────────────────────────────────────────────────────────────────────────────
MONEY IS SERVED AT FOUR PLACES AND DISPLAYED AT TWO
────────────────────────────────────────────────────────────────────────────
Amounts leave here as strings at their stored precision plus a `_display` at
two, with the CHAR(3) currency beside them (PO re-sign 2026-08-22). Rounding for
a human happens once, here, and never inside the maths.

────────────────────────────────────────────────────────────────────────────
ONE COLUMN WAS WRITTEN AND NEVER READ BACK — CLOSED 2026-08-25 (B18 task 4.12)
────────────────────────────────────────────────────────────────────────────
`set_customer_category` has written `account_type_id` / `account_subtype_id`
since the capture wizard landed, and **no tab served either of them**. The
symptom is the one hard-won law 2 names from the other side: not dead UI over a
missing endpoint, but a live WRITE with no READ, which every test passes over
because nothing ever asks the payload for it. `customer_category()` below is
that read, on the Applicant tab beside `person_or_company` for B19 §14.3's
reason, and `test_the_detail_serves_the_category_it_was_given` is what stops it
going quiet again.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from core import crypto
from core import errors
from core.money import finalize
from core.pagination import order_terms

from apps.customers import applicant_messages
from apps.customers import models, seams, service_request as rules
from apps.customers import service_request_documents as doc_files
from apps.customers import service_request_service as writes
from apps.customers import request_jobs
from apps.customers import request_custom_fields

_SR = models.ServiceRequest


def _tenant_id() -> Any:
    from core import tenancy as core_tenancy

    return core_tenancy.current_tenant_id()


def _money(value: Any, currency: str | None) -> dict[str, Any]:
    amount = Decimal(str(value or "0"))
    return {
        "amount": str(amount),  # stored precision — 4 dp
        "display": str(finalize(amount)),  # CLAUDE.md rule 2: display 2
        "currency": currency,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CONDITIONS — assembled here because it needs four tables and a ledger seam
# ═══════════════════════════════════════════════════════════════════════════
def _category_to_be_set(request: models.ServiceRequest) -> bool:
    from apps.customers import service_request_service

    return service_request_service.category_to_be_set(request)


def conditions_for(
    request: models.ServiceRequest,
    *,
    outcome: str | None = None,
    address_is_new: bool = False,
) -> list[rules.Condition]:
    """The FOUR approval conditions, evaluated against this request.

    ⚠ The screen renders *"4 of 5 conditions clear"* and **four are
    identifiable** — see `service_request.CONDITION_KEYS` and **OQ-355**.

    ⚠ **`outcome` ASKS A DIFFERENT QUESTION — *what would stand if this were
    the pick* — AND IT EXISTS BECAUSE THE OLD ONE COULD NOT BE ANSWERED IN TIME
    (`DEF-CUS-5427`).** The document checklist is keyed on the OUTCOME
    (`BR-CUS-095`, `required_document_types`), and until 2026-09-16 every caller
    read the STORED outcome — which is empty while the clerk is still choosing.
    So the Approve dialog could only ever be told about conditions that did not
    yet depend on the thing it was about to write, the commit went live with
    nothing beside it, and the refusal arrived after the outcome had been saved.
    **Measured on `SR-26-0003`, 2026-09-16: no stored outcome → all four clear;
    the same request considered as `move_in` → two required documents
    outstanding.** Default `None` keeps every existing caller reading the stored
    pick, byte for byte.

    ⊕ **AND SINCE 2026-09-23 THE PLACE COMES FIRST (`DEF-CUS-6350`).** A move-in
    carries four more conditions and a new connection two — see
    `_placement_conditions` — AHEAD of the four above, because *is the unit
    free* is the question the window leads with. `address_is_new` is the
    clerk's *It's a new address* answer to a near match, and it travels only
    with the approval that relies on it.
    """
    fees = writes.fee_total_to_collect(request.id)
    placement = _placement_conditions(
        request, outcome or request.outcome, address_is_new=address_is_new
    )
    return placement + [
        _arrears_condition(request),
        rules.eligibility_condition(claimed=request.eligibility_claimed),
        _documents_condition(request, outcome=outcome),
        # BR-CUS-090 — the review step reads the OUTSTANDING FIGURE. The line
        # count rides along as the fallback for a request whose money was never
        # totalled; see `service_request.fee_condition`.
        rules.fee_condition(
            outstanding_lines=writes.outstanding_fee_lines(request.id),
            outstanding_amount=fees["outstanding"],
            currency=fees["currency"],
        ),
    ]


def _conditions_considering(
    request: models.ServiceRequest,
    conditions: list[rules.Condition],
    outcome: str,
) -> list[rules.Condition]:
    """`conditions` re-answered as if `outcome` were the pick.

    ⚠ **ONLY THE DOCUMENTS CONDITION IS RE-EVALUATED, AND THAT IS A FACT ABOUT
    THE RULES RATHER THAN AN OPTIMISATION.** Arrears, eligibility and the fee
    are facts about the APPLICANT and the MONEY; none of them reads the outcome.
    The checklist does, and it is the only one (`BR-CUS-095`). So calling
    `conditions_for` five times would ask the ledger seam for the same arrears
    answer five times and re-total the same fee five times to get five identical
    rows — **one AR read and one fee read, five document reads**, which is what
    this does.

    ⚠ **IF A FIFTH CONDITION EVER READS THE OUTCOME, IT MUST BE ADDED HERE OR
    IT WILL SILENTLY ANSWER FOR THE STORED PICK.** That is this function's one
    hazard and there is no check for it; `conditions_for(request,
    outcome=outcome)` is the slower, always-correct form if that day comes.

    ⊕ **THAT DAY CAME ON 2026-09-23 (`DEF-CUS-6350`) AND IT WAS HANDLED HERE, AS
    THE PARAGRAPH ABOVE SAYS IT MUST BE.** The place conditions read the outcome
    — a move-in asks four questions about the unit and a new connection two
    about the address — so they are dropped from `conditions` (which answered
    for the STORED pick) and asked again for `outcome`. The arrears, eligibility
    and fee answers are still reused, so this is still one AR read.
    """
    placement_keys = set(rules.MOVE_IN_PLACE_KEYS) | set(rules.NEW_CONNECTION_PLACE_KEYS)
    return _placement_conditions(request, outcome) + [
        _documents_condition(request, outcome=outcome) if c.key == "documents_verified" else c
        for c in conditions
        if c.key not in placement_keys
    ]


# ═══════════════════════════════════════════════════════════════════════════
# THE PLACE — DEF-CUS-6350, PO rulings of 2026-09-23
# ═══════════════════════════════════════════════════════════════════════════
def _placement_conditions(
    request: models.ServiceRequest, outcome: str | None, *, address_is_new: bool = False
) -> list[rules.Condition]:
    """The conditions about WHERE the service goes, for one outcome.

    Only two outcomes open service at an address and only they carry any:
    a MOVE-IN asks four questions about the unit, a NEW CONNECTION two about
    the address. The pure halves are in `service_request.py`; this is the read.
    """
    if outcome == _SR.OUTCOME_MOVE_IN:
        return _move_in_place(request)
    if outcome == _SR.OUTCOME_NEW_CONNECTION:
        return _new_connection_place(request, address_is_new=address_is_new)
    return []


def _resolved_unit(request: models.ServiceRequest) -> dict[str, Any] | None:
    """The unit the request resolved to — its NUMBER and label — or `None`.

    A resolved id can outlive the unit it named (metering's 404-never-403), and
    a deactivated unit cannot take an account (`BR-CUS-020`); both read as *no
    unit chosen*, which sends the clerk to pick one rather than approving onto
    something that will refuse on move day. `NotFoundError` is a DOMAIN refusal
    from a lookup that found nothing — no statement failed — so catching it does
    not carry on inside a poisoned PostgreSQL transaction (hard-won law 14).
    """
    if not request.resolved_unit_id:
        return None
    try:
        row = seams.unit_row(request.resolved_unit_id)
    except errors.NotFoundError:
        return None
    if getattr(row, "deleted_at", None) is not None:
        return None
    return {
        "id": str(row.id),
        "unit_no": getattr(row, "unit_no", None),
        "label": getattr(row, "label", None),
        "premises_id": str(getattr(row, "premises_id", "") or ""),
    }


def _move_in_place(request: models.ServiceRequest) -> list[rules.Condition]:
    """**The move-in four** — property on file, a unit chosen, the unit free,
    and no other move-in waiting for it — each BLOCKING, each NAMED.

    ⚠ **THE OCCUPANCY READ IS THE ONE `occupying_accounts_for_unit`**, through
    `selectors.active_account_for_unit` exactly as `_evidence_for` already reads
    it — never a second query. It is read WITHOUT the lock: this is the decision
    a clerk takes today, and the move-day lock in `services._refuse_if_unit_
    occupied` stays exactly as it was, the backstop for a unit taken between
    approval and move day.

    ⚠ **A RACE IS LEFT, NAMED.** Two clerks approving two move-ins for one unit
    in the same instant both read no waiting job, because `raise_job` runs after
    the approval commits (`BR-WRK-055`). The window is milliseconds and the
    move-day lock refuses the second account; closing it fully would mean
    raising the job inside the approval's transaction, which `BR-WRK-055`
    forbids for the other outcomes and which is not this defect's to change.
    """
    from apps.customers import move_in_jobs, selectors

    unit = _resolved_unit(request)
    premises_id = request.resolved_premises_id or (unit or {}).get("premises_id") or None
    place = seams.premises_label(premises_id) if premises_id else None
    found = place is not None
    if unit is not None and place is not None and unit["premises_id"] != str(place.get("id")):
        # The two resolved columns disagree about where the request is. The
        # unit's building wins, because the unit is the more specific pick and
        # the account opens on the unit — and it is what `_resolution_from_pick`
        # would have written had the pick arrived through it.
        place = seams.premises_label(unit["premises_id"])
        found = place is not None
    units_here = seams.units_at_premises_count(place.get("id")) if found and unit is None else None
    unit_known = found and unit is not None
    occupier = selectors.active_account_for_unit(unit["id"]) if unit_known else None
    waiting: list[dict[str, Any]] = []
    if unit_known:
        waiting = [
            {"request_no": row.request.request_no, "move_no": row.move_no}
            for row in move_in_jobs.pending_queryset()
            .filter(request__resolved_unit_id=unit["id"])
            .exclude(request_id=request.id)
            .order_by("raised_at", "id")
        ]
    return [
        rules.premises_on_file_condition(place=place),
        rules.unit_chosen_condition(
            premises_found=found, unit=unit if found else None, units_at_premises=units_here
        ),
        rules.unit_free_condition(unit_known=unit_known, occupier=occupier),
        rules.no_other_move_in_condition(unit_known=unit_known, waiting=waiting),
    ]


def _new_connection_place(
    request: models.ServiceRequest, *, address_is_new: bool = False
) -> list[rules.Condition]:
    """**The new-connection two** — the address is NOT in Premises (in any
    status), and no other open application is about to create it.

    PO ruling 2026-09-23 (`OQ-CUS-12615` CLOSED): *"this si correct
    understanding"* and *"we dont allow these status - dont create new request
    even if property is in draft, pending or inactive"*. So a request that
    RESOLVED to a premises is refused outright; one that did not is compared
    against Premises by metering (`address_match`), and a near match is put to
    the clerk before anything can be created.
    """
    resolved = None
    if request.resolved_premises_id or request.resolved_unit_id:
        unit = _resolved_unit(request)
        premises_id = request.resolved_premises_id or (unit or {}).get("premises_id") or None
        resolved = seams.premises_label(premises_id) if premises_id else None
    as_given = (request.address_as_given or "").strip()
    match = None
    if resolved is None:
        match = seams.premises_matching_address(
            as_given,
            city=request.address_city_as_given,
            postal_code=request.address_postal_code_as_given,
        )
    address = rules.address_not_in_premises_condition(
        resolved=resolved, match=match, as_given=as_given, declared_new=address_is_new
    )
    # The open-application check is only meaningful for an address that is NOT
    # on file: one that is on file is already refused above, by name.
    address_reached = address.key == rules.ADDRESS_NOT_IN_PREMISES and address.state in (
        rules.CONDITION_CLEAR,
        rules.CONDITION_CHOOSE,
    )
    open_elsewhere = _open_new_connections_here(request) if address_reached else []
    return [
        address,
        rules.no_open_request_condition(
            address_reached=address_reached, open_elsewhere=open_elsewhere
        ),
    ]


def _open_new_connections_here(request: models.ServiceRequest) -> list[dict[str, Any]] | None:
    """Every OTHER approved new-connection application for this same new
    address whose build is still open — or `None` when metering cannot answer.

    ⚠ **APPROVED ONLY, AND THAT IS WHAT MAKES IT *THE SECOND* THAT IS
    REFUSED.** Two unapproved applications for one address would otherwise each
    refuse the other and neither could ever be approved. The first to be
    approved raised a build; that build creates the premises at its last button;
    this refuses the second until it has, after which the address check above
    takes over — or until it is cancelled, after which nothing refuses.

    **The comparison is metering's** (`address_match.same_place`) — case,
    spacing, `St`/`Street` and the other street words, and the first five digits
    of a ZIP — so this and the Premises check cannot disagree about whether two
    spellings are one place. Only an `exact` verdict counts here: a near pair is
    a question for a person, and refusing one application because another is
    SIMILAR would block an honest neighbour.
    """
    candidates = list(
        _SR.objects.filter(
            tenant_id=request.tenant_id,
            outcome=_SR.OUTCOME_NEW_CONNECTION,
            state=_SR.APPROVED,
            resolved_premises_id__isnull=True,
        )
        .exclude(pk=request.id)
        .only(
            "id",
            "request_no",
            "address_as_given",
            "address_city_as_given",
            "address_postal_code_as_given",
        )
        .order_by("decided_at", "id")
    )
    same: list[models.ServiceRequest] = []
    for other in candidates:
        verdict = seams.same_place(
            request.address_as_given,
            other.address_as_given,
            postcode_a=request.address_postal_code_as_given,
            postcode_b=other.address_postal_code_as_given,
            city_a=request.address_city_as_given,
            city_b=other.address_city_as_given,
        )
        if verdict is None:
            return None
        if verdict == "exact":
            same.append(other)
    if not same:
        return []
    builds = seams.open_builds_for_requests([str(other.id) for other in same])
    if builds is None:
        return None
    return [
        {
            "request_no": other.request_no,
            "connection_no": builds[str(other.id)].get("connection_no"),
        }
        for other in same
        if str(other.id) in builds
    ]


def _arrears_condition(request: models.ServiceRequest) -> rules.Condition:
    """*"We search for any account you have held before, and check for anything
    outstanding on it."* (REQ-03.sent), rendered as `CLEAR` on the Decision tab.

    `match_confirmed_at` is what carries *somebody looked*: `link_customer`
    stamps it whether a customer was found or not, so a genuine first-time
    applicant clears this condition through the same control as a returning one.
    """
    searched = request.match_confirmed_at is not None
    if not searched:
        return rules.arrears_condition(
            search_done=False, amount_owed=None, books_unavailable_reason=None
        )
    account_ids = writes.customer_account_ids(request.matched_customer_id)
    if not account_ids:
        # Searched, and there is no prior account. Nothing to owe on.
        return rules.arrears_condition(
            search_done=True, amount_owed=Decimal("0"), books_unavailable_reason=None
        )
    positions = seams.ar_positions(account_ids)
    if not positions.available:
        reason = positions.unavailable[0].get("code") if positions.unavailable else None
        return rules.arrears_condition(
            search_done=True, amount_owed=None, books_unavailable_reason=reason or "unavailable"
        )
    owed = sum((positions.amount_for(a) or Decimal("0")) for a in account_ids)
    return rules.arrears_condition(
        search_done=True, amount_owed=Decimal(owed), books_unavailable_reason=None
    )


def _documents_condition(
    request: models.ServiceRequest, *, outcome: str | None = None
) -> rules.Condition:
    """The two gates, plus BR-CUS-095's checklist.

    `checklist_unmet` is what the TENANT ticked for this request's outcome and
    has not been given; the other three counts are what is ON the request. An
    unconfigured tenant contributes an empty tuple and blocks nothing, which is
    the ruling's own default and is not softened anywhere.
    """
    rows = list(models.ServiceRequestDocument.objects.filter(request=request))
    with_file = [d for d in rows if d.storage_ref]
    return rules.documents_condition(
        total=len(with_file),
        verified=sum(1 for d in with_file if d.verification_state == d.VERIFIED),
        rejected=sum(1 for d in with_file if d.verification_state == d.REJECTED),
        awaiting_file=sum(1 for d in rows if d.required_flag and not d.storage_ref),
        # `outcome` is the CONSIDERED pick, not the stored one — see
        # `conditions_for`. `None` reads the stored pick, as it always did.
        checklist_unmet=writes.unmet_required_documents(request, outcome=outcome),
    )


# ═══════════════════════════════════════════════════════════════════════════
# REQ-01 — the list
# ═══════════════════════════════════════════════════════════════════════════
#: ── REQ-01's SORT VOCABULARY (`BR-CUS-1046`, PO 2026-09-12) ────────────────
#: A sort name → the ORDER BY it means, written ascending. `order_terms` flips
#: it for `desc`, so the two directions cannot drift apart.
#:
#: ⚠ **EVERY TUPLE ENDS IN `id`** — a page is a window over an ORDER, and an
#: order that is not total lets two rows swap between page 1 and page 2, so a
#: clerk sees one twice and another never.
#: ⚠ **EVERY NAME HERE IS THE SCREEN'S EXISTING COLUMN KEY, NOT A NEW ONE.**
#: `DataTable` stores a clerk's show/hide/reorder preference keyed by
#: `screenId` + column key (`BR-SHL-013`, `DEF-647`), so renaming a column to
#: match a tidier server name would silently discard every saved column set on
#: this screen. The server name moved instead; it is the cheaper half.
SORTS: dict[str, tuple[Any, ...]] = {
    #: ⚠ **WRITTEN ASCENDING, LIKE EVERY TERM IN THIS MAP — `order_terms` FLIPS
    #: IT AND `DEFAULT_DIR` IS `desc`.** The first draft of this pass stored
    #: `-created_at` here AND defaulted to `desc`, so the flip cancelled the
    #: minus and every list opened on the OLDEST row: the exact inversion of
    #: the ruling, shipped as a working feature. Nothing raised — it was found
    #: by curling the endpoint and reading the first three rows.
    "created": ("created_at", "id"),
    #: The ordering this tab OPENED ON until 2026-09-12, kept as a column a
    #: clerk clicks. B18 §5.2.2's footnote was *"the oldest thing waiting is
    #: the thing to look at"*, and that is still true — it is now a choice
    #: rather than the only possibility, and the choice survives a refresh.
    "received_at": ("received_at", "id"),
    "request_no": ("request_no", "id"),
    "applicant": ("applicant_name", "id"),
    "state": ("state", "id"),
}
DEFAULT_SORT = "created"
DEFAULT_DIR = "desc"


def list_queryset(
    *, segment: str = "open", q: str | None = None, sort: str | None = None, dir: str = DEFAULT_DIR
):
    """REQ-01's five segments, its search, and its ORDER BY.

    ⚠ **IT OPENS ON THE CREATION ORDER SINCE 2026-09-12 (`BR-CUS-1046`,
    `DEF-CUS-5060`), AND THE FOOTNOTE ON SCREEN CHANGED WITH IT.** This
    docstring used to read *"Sorted by age, oldest first — the oldest thing
    waiting is the thing to look at"*, quoting the sentence the tab printed
    under its pager. The PO ruled (2026-09-10, extended 2026-09-12): *"It should
    always sort it by the creation order. The new newly created entries should
    always show on the top … (c) All eight open newest-first and the six gain a
    sort control."*

    ⚠ **THE URGENCY ORDERING IS NOT LOST, AND THAT IS WHY THE RULING COULD BE
    OPTION (c) RATHER THAN (a).** `sort="received"` is the old ordering exactly,
    it is a clickable column, and `?sort=received&dir=asc` survives a refresh —
    which is what `BR-CUS-1046`'s own second clause requires of all eight lists.
    """
    from django.db.models import Q

    qs = models.ServiceRequest.objects.filter(tenant_id=_tenant_id())
    states = rules.SEGMENT_STATES.get(segment)
    if states is not None and segment != "all":
        qs = qs.filter(state__in=states)
    if q:
        # *"Request #, name, address, phone, or email…"*
        qs = qs.filter(
            Q(request_no__icontains=q)
            | Q(applicant_name__icontains=q)
            | Q(address_as_given__icontains=q)
            | Q(applicant_phone__icontains=q)
            | Q(applicant_email__icontains=q)
        )
    return qs.order_by(*order_terms(sort, dir, columns=SORTS, default=DEFAULT_SORT))


def list_row(
    request: models.ServiceRequest,
    *,
    as_of: Any = None,
    zone: Any = None,
    kinds: dict[str, str] | None = None,
) -> dict[str, Any]:
    """One REQ-01 row: `REQUEST · TYPE · APPLICANT · ADDRESS · RECEIVED ·
    CHANNEL · AGE · WAITING ON · STATE`.

    ⚠ **`channel` JOINED THE ROW ON 2026-09-04 (CR-068 wave B, `BR-CWP-076`).**
    The column has existed on `service_requests` since B18 and nothing had ever
    written it; the portal writes `customer_portal` and `US-CWP-007` TC-1 asks
    for the row to appear *"on a clerk's worklist with channel Customer
    portal"*. It was served on the DETAIL header only, so the list could not
    show it — which made a rule about where work comes from invisible on the
    one screen a clerk actually reads.

    ✅ **`age_is_accented` IS SERVED — BR-CUS-106, PO ruling 2026-08-25, closing
    decision D4.** This docstring said the opposite until that ruling, and the
    refusal was the point: B18 §5.3.2 and B19 §12.1 both say the `AGE` threshold
    is **not derivable from a picture** — `15d` and `11d` render in the accent,
    `5d` and below do not, so it is *between 6 and 11 days* — B18 *proposed* 7
    without authority to confirm it, and serving a flag would have meant a lane
    picking the number. **The PO chose 7, one week, and the boundary is
    INCLUSIVE.** The threshold lives in one place (`service_request.
    age_is_accented`) so this row and any later caller cannot drift apart, and
    the screen now asks this payload where the line is instead of deriving it —
    a rule belongs on the server (B8).

    ⚠ **THE AGE IS COUNTED IN THE UTILITY'S OWN DAY, AND IT WAS COUNTED IN THE
    SERVER'S UNTIL 2026-09-24 (`DEF-CUS-6433`).** Both halves of the
    subtraction took the **UTC** date, so from 19:00 in Brazos Bend until
    midnight UTC — five hours of every evening — every request on this list
    read **one day older than it is**, and `BR-CUS-106`'s seven-day accent came
    on a day early with it: a request filed six days ago is accented from 19:00.
    It stayed invisible because every lane that ran the suite ran it in
    daylight. `BR-TEN-043` is the rule — the utility's own clock decides what
    day it is for every date the product derives — and an age is TWO dates, so
    both halves are converted. This is `DEF-094`'s shape one module over: a read
    and a write, each correct on its own terms, disagreeing by a day.

    `zone` is the same answer, resolved ONCE by a caller rendering a page of
    rows — `tenant_timezone()` is a query, and fifty rows would otherwise ask
    the same question fifty times. Left out, this row asks for itself.
    """
    from django.utils import timezone

    zone = zone or seams.tenant_timezone()
    now = as_of or timezone.now()
    today = now.astimezone(zone).date() if hasattr(now, "astimezone") else now
    age_days = (
        (today - request.received_at.astimezone(zone).date()).days
        if request.received_at
        else None
    )
    return {
        "id": str(request.id),
        # BR-CUS-093 — numbered at creation, so this is populated on every row
        # created from 2026-08-24. A row that predates the ruling carries NULL
        # forever (consequence (a): nothing back-fills, gaps are normal), and
        # THAT is what the absence names now.
        "request_no": request.request_no,
        "number_absence": None if request.request_no else {"tracks": "BR-CUS-093"},
        # ⊕ `CR-183-BRC10` — a temporary-stop or restart ask is TYPED from the
        # moment it arrives (its own row says what it is), approved or not.
        "type": _type_of(request, kinds),
        "type_absence": None
        if _type_of(request, kinds)
        else {"reason": "not_yet_classified"},
        "applicant": request.applicant_name,
        "address": request.address_as_given,
        "address_unit": request.address_unit_as_given,
        "received_at": request.received_at.isoformat() if request.received_at else None,
        # `BR-CWP-076` — free text against a service-side vocabulary
        # (`customers/models.py`, the `channel` comment); the screen translates
        # a KNOWN value and prints an unknown one as it stands.
        "channel": request.channel,
        "age_days": age_days,
        # BR-CUS-106 — 7 days or more, inclusive. `None` where `age_days` is
        # None: no `received_at` means no age, and that is not "not old".
        "age_is_accented": rules.age_is_accented(age_days),
        "waiting_on": request.waiting_on,
        "state": request.state,
    }


def _type_of(request: models.ServiceRequest, kinds: dict[str, str] | None = None) -> str | None:
    """The request's TYPE: the clerk's committed outcome, or — for a temporary
    stop or its restart ask (`CR-183-BRC10`) — the kind its own row records.
    `kinds` is a page's answers read once (`temporary_stop.kinds_for`)."""
    from apps.customers import temporary_stop

    if request.outcome in _SR.JOB_OUTCOMES or request.outcome in temporary_stop.KINDS:
        return request.outcome
    if kinds is not None:
        return kinds.get(str(request.id))
    return temporary_stop.kind_of(request)


def kpi_strip() -> dict[str, Any]:
    """REQ-01's five tiles, exactly as B18 §5.3.1 designs them and B19 §12.1
    confirms them.

    `APPROVED, NOT STARTED` is the one that earns the tab — *"decided, and
    nobody has begun"* — and it is why `outcome_ref` being NULL is a queue and
    not a gap: an approved request with no child linked is somebody's next job.
    """
    from django.utils import timezone

    base = models.ServiceRequest.objects.filter(tenant_id=_tenant_id())
    open_states = rules.SEGMENT_STATES["open"]
    oldest = (
        base.filter(state__in=open_states, waiting_on__isnull=False).order_by("received_at").first()
    )
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return {
        "open": base.filter(state__in=open_states).count(),
        # ⚠⚠ **THIS KPI AND THE SEGMENT OF THE SAME NAME DO NOT ASK THE SAME
        #     QUESTION, AND THEY CAN DISAGREE ON ONE REQUEST** — found while
        #     reading `DEF-CUS-5906` and written here because the row does not
        #     say it and the next lane will reach for the one-line fix.
        #
        #     This COUNT is keyed on the `waiting_on` COLUMN being set. The
        #     SEGMENT a clerk clicks is keyed on STATE:
        #     `rules.SEGMENT_STATES["waiting_on_customer"] == (MORE_INFO,)`.
        #     So a request that has been asked for more sits IN the segment and
        #     OUT of this count, because `ask_for_more` writes no `waiting_on`
        #     while `park` does — which is `DEF-CUS-5906`.
        #
        #     ⚠ **SO THE FIX IS A DECISION, NOT A LINE.** Making `ask_for_more`
        #     set `waiting_on` would make the two agree BY ACCIDENT and leave
        #     two definitions of one phrase in the product — the shape that has
        #     already cost this module three defects in one day (a seam's copy
        #     of a rule, a hand-typed guard, eleven catalogues). Whoever takes
        #     `DEF-CUS-5906` should say which definition is canonical and make
        #     the other read it. The blueprint has an opinion: p089 of the
        #     281-page Accounts drawing lists *"Waiting on changes from
        #     documents to the applicant"* as a consequence of asking for more,
        #     which argues for the COLUMN — and that needs a `waitingOn.applicant`
        #     word in all eleven catalogues, which is why it was not done on the
        #     way past.
        "waiting_on_customer": base.filter(state__in=open_states, waiting_on__isnull=False).count(),
        "oldest_waiting": {
            "days": (
                (now.date() - oldest.received_at.date()).days
                if oldest and oldest.received_at
                else None
            ),
            "request_no": oldest.request_no if oldest else None,
            "waiting_on": oldest.waiting_on if oldest else None,
        },
        "approved_not_started": base.filter(state=_SR.APPROVED, outcome_ref__isnull=True).count(),
        "refused_this_month": base.filter(state=_SR.REFUSED, closed_at__gte=month_start).count(),
        # A month boundary is a tenant-timezone fact and this uses the server's.
        # Named rather than hidden: BR-TEN-043's event-time law is about writes,
        # and no rule states which clock a KPI window uses.
        "period_basis": "server_month_to_date",
    }


# ═══════════════════════════════════════════════════════════════════════════
# REQ-02 — the detail, tab by tab
# ═══════════════════════════════════════════════════════════════════════════
def _application_tax_id(request: Any) -> dict[str, Any]:
    """`tax_id_last4` / `tax_id_present` for a request a business sent from the
    portal (`DEF-CWP-9045`, `OQ-CWP-1560` (b)); both empty otherwise."""
    from apps.customers import portal_seam

    # Lane CF-1 (`DEF-CUS-10223`) — the staff request now keeps the number a
    # clerk typed on the request itself; it wins over the portal draft's.
    number = getattr(request, "tax_id", None) or portal_seam.application_tax_id(request)
    return {"tax_id_last4": crypto.last_four(number), "tax_id_present": bool(number)}


def _mailing_parts(request: Any) -> dict[str, Any]:
    """Lane CF-1 — WHERE THE BILL GOES, under its one name.

    The `mailing_*` columns, or — for a request whose mailing parts are all
    empty (written before `customers/0087`, by a caller sending the old
    spelling) — the `billing_*` parts, and failing those the one-box value
    pre-`DEF-CUS-6408` requests hold, as `line1`. Never composed into a line
    here; the screen writes the sentence.
    """
    parts = {
        "line1": request.mailing_line1,
        "line2": request.mailing_line2,
        "city": request.mailing_city,
        "state": request.mailing_state,
        "postal_code": request.mailing_postal_code,
    }
    if any(str(value or "").strip() for value in parts.values()):
        return {"same": bool(request.mailing_same), **parts}
    old = {
        "line1": request.billing_line1_as_given or request.billing_address_as_given,
        "line2": request.billing_line2_as_given,
        "city": request.billing_city_as_given,
        "state": request.billing_state_as_given,
        "postal_code": request.billing_postal_code_as_given,
    }
    return {"same": bool(request.billing_address_same), **old}


def _application_mailing_address(request: Any) -> dict[str, Any] | None:
    """The portal applicant's mailing address, if they gave one
    (`DEF-CWP-9163`); `None` otherwise."""
    from apps.customers import portal_seam

    return portal_seam.application_mailing_address(request)


def detail(request_id: Any) -> dict[str, Any]:
    """REQ-02: the header, the three metric columns, the actions and six tabs."""
    request = writes.request_row(request_id)
    conditions = conditions_for(request)
    evidence = writes.evidence_for(request)
    # ONE walk to the matched premises, shared by the head and the tab. Both
    # draw the locality (the head's address line, the tab's matched rows) and
    # `resolved_place` costs a cross-module read, so it is computed once here
    # rather than twice a request.
    place = resolved_place(request)
    # Built ONCE and handed to the card below, which needs the same two facts:
    # the open fee balance and how many required documents are unmet. Reading
    # them again there would be two more queries on the hottest read this
    # module has, for figures already in hand.
    documents = documents_tab(request)
    fees = fees_tab(request)
    return {
        "header": _header(request, place),
        "actions": _actions(request, conditions),
        "applicant": applicant_tab(request),
        "location_and_services": location_tab(request, evidence, place),
        "documents": documents,
        "fees": fees,
        "decision": decision_tab(request, evidence, conditions),
        # ⊕ `CR-183-BRC10` — the temporary stop this request asks for (or the
        # hold its *Restart now* would end): account, dates, the limits and
        # every reason it cannot be approved. `None` on every other request.
        "temporary_stop": _temporary_stop_for(request),
        "history": history_tab(request),
        # ⊕ `CR-161-BRC10` W6 — the REQUEST'S OWN COPY of the utility's fields
        # typed on Staff New Request (gap 2: *"Request detail always shows the
        # request's copy of every intake field"*), and what approving would do
        # with each answer (gap 3 / R5: *"Existing: Metal · Requested: Tile
        # side by side; the EXISTING value is pre-selected"*). Keys and the
        # tenant's own values only; every word around them is the catalogue's.
        "custom_data": request_custom_fields.stored(request),
        "custom_field_copy": request_custom_fields.copy_preview(request),
        # ⚠ **`What the customer is told` — REQ-03 step 4's new card**, and
        # the ONE genuinely new capability in the four-step redraw of
        # 2026-09-29. MESSAGE · CHANNEL · TO · WHEN, for this request, on
        # submit — and a message that will NOT be sent still gets a row saying
        # so, because an absent row and a withheld one look identical.
        #
        # ⚠ **THE WORDS ARE NOT HERE.** Keys and parameters travel; the eleven
        # catalogues compose the sentences (`BR-SHL-020` r2). The `to` value is
        # an email ADDRESS — data, not prose — so it travels as itself.
        #
        # Served on the detail rather than on a route of its own because the
        # review step already reads this payload and a second call would make
        # the card's rows and the fee figures they quote two reads that can
        # disagree. `applicant_messages.on_submit_card` writes nothing.
        "told_on_submit": applicant_messages.on_submit_card(
            request,
            outstanding_money=Decimal(fees["outstanding"]["amount"]),
            currency=fees["outstanding"]["currency"],
            outstanding_documents=len(documents["checklist_unmet"]),
        ),
    }


def _temporary_stop_for(request: models.ServiceRequest) -> dict[str, Any] | None:
    from apps.customers import temporary_stop

    return temporary_stop.for_request(request)


def _header(
    request: models.ServiceRequest, place: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The head of the request's own screen — p082, under the applicant's name.

    ⚠ **THE ADDRESS LINE IS DRAWN IN FULL AND THE HEAD COULD ONLY SERVE A
    STREET.** The blueprint draws `212 Balcones Drive · Unit 3 · Austin, TX
    78704` on one line beneath the meta row, and this payload carried
    `address_as_given` alone — so the head would have rendered a street with no
    unit and no town however the screen was written.

    Two different facts make that line and they are served as two:
    `address_unit_as_given` is **what the applicant said** (`BR-CUS-070`), and
    `premise_locality` is **the matched premises' own**, walked to through
    metering (`BR-MET-1161`, and the PO ruling of 2026-09-15 — *"we should take
    it from premises/Unit"*). They travel here as well as on the location tab
    because the head is drawn ABOVE the tabs and must not read one to draw
    itself.
    """
    place = resolved_place(request) if place is None else place
    return {
        "id": str(request.id),
        "request_no": request.request_no,
        "number_absence": None if request.request_no else {"tracks": "BR-CUS-093"},
        "state": request.state,
        # `NOT YET CLASSIFIED` — the chip the detail draws beside the state.
        # ⊕ `CR-183-BRC10` — or *Temporary stop* / *Restart now*, from the row
        # the portal ask wrote, before anybody decides anything.
        "classification": request.outcome or _type_of(request) or "not_yet_classified",
        "applicant": request.applicant_name,
        "address_as_given": request.address_as_given,
        "address_unit_as_given": request.address_unit_as_given,
        "premise_locality": place["premise_locality"],
        "lookup_found": request.lookup_found,
        "received_at": request.received_at.isoformat() if request.received_at else None,
        "received_by": str(request.received_by_id) if request.received_by_id else None,
        "channel": request.channel,
        "waiting_on": request.waiting_on,
        "waiting_since": request.parked_at.isoformat() if request.parked_at else None,
        "requested_start": request.requested_start.isoformat() if request.requested_start else None,
        # ── §8 · WHERE THE BACK CONTROL EXITS TO ───────────────────────────
        # See `_queue_for`. `None` on every request that is not approved.
        "queue": _queue_for(request),
        # ⊕ `DEF-CUS-6350` — WHERE IT WENT: the job approval raised, by its
        # NUMBER. See `_job_for`.
        "job": _job_for(request),
    }


def _job_for(request: models.ServiceRequest) -> dict[str, Any] | None:
    """**The job this approved request raised, named by its number** — what the
    request page shows as *Approved → Move-in MVI-26-0115*, linking to it.

    PO, 2026-09-23 (`OQ-CUS-12616` CLOSED, decision log *"RULED: THE MOVE-IN
    APPROVAL FLOW, SIX STEPS"*): after approval the clerk lands on the job, and
    the request says where it went. **Read back through the link on every call**
    — the job names the request (`move_in_jobs.request_id`,
    `connections.request_id`), never the other way round for a move-in — so a
    page opened next week says the same thing the approval said.

    ⚠ **THE NUMBER, NEVER THE ID, IS WHAT A SCREEN PRINTS** (B14 rule 31). The
    id rides so a draft build can be reopened; `number` is `None` where the
    tenant keeps no series, and the screen says so in words.
    """
    if request.state != rules.APPROVED:
        return None
    if request.outcome == _SR.OUTCOME_MOVE_IN:
        job = (
            move_in_jobs_model()
            .objects.filter(tenant_id=request.tenant_id, request_id=request.id)
            .only("id", "move_no", "state")
            .first()
        )
        if job is None:
            return None
        return {"kind": "move_in", "id": str(job.id), "number": job.move_no, "state": job.state}
    if request.outcome == _SR.OUTCOME_NEW_CONNECTION:
        build = seams.builds_for_requests([str(request.id)]).get(str(request.id))
        if build is None:
            return None
        return {
            "kind": "connection",
            "id": build.get("id"),
            "number": build.get("connection_no"),
            "state": build.get("state"),
        }
    return None


def move_in_jobs_model() -> Any:
    from apps.customers import move_in_jobs

    return move_in_jobs.MoveInJob


def _queue_for(request: models.ServiceRequest) -> str | None:
    """The register tab an APPROVED request's work now lives on, or `None`.

    ⚠ **`The register` NAMED FOUR DIFFERENT PLACES** (decision log 2026-09-20
    §8). The PO pressed the back control on an approved MOVE-IN request and
    landed on the requests list: *"when i lick on register - it shoudl take me
    to movein list page - instead it takes me to request list page"*. B14 rule 1
    decides it — a page header's `←` NAMES WHERE IT EXITS TO — and a control
    that names its destination cannot send a clerk to the wrong tab.

    ⚠ **THE MAP IS `request_jobs.JOB_SHAPES` AND A SECOND ONE IS NOT WRITTEN.**
    That table already answers *which queue does this outcome land on* for the
    approval itself, which is why the header can be served from it rather than
    from a copy: the decision log is explicit that *"that map is the single
    source; a second one is how two screens come to disagree"*. The screen turns
    the queue's name into its tab slug and refuses anything its own tab list
    does not know — a derivation with a guard, not a second map.

    ⚠ **IT IS `None` UNTIL THE REQUEST IS APPROVED, DELIBERATELY.** Before that
    the outcome is a PROPOSAL — `decision.commit.outcome` can be written and
    rewritten while a clerk thinks — and no job exists on any queue to go and
    look at. An unapproved request belongs to the requests list, which is where
    it was raised and where it is findable.

    `None` again for an approved request whose outcome names no shape, which is
    a stated absence rather than a guess: every outcome in `OUTCOME_CHILD_KINDS`
    has a row in `JOB_SHAPES`, so this branch is reached only by a value that
    predates one, and sending a clerk to a tab chosen at random would be worse
    than sending them back where they came from.
    """
    if request.state != rules.APPROVED:
        return None
    shape = request_jobs.JOB_SHAPES.get(request.outcome or "")
    if shape is None:
        return None
    queue = shape["queue"]
    return str(queue) if queue else None


def _actions(request: models.ServiceRequest, conditions: list[rules.Condition]) -> dict[str, Any]:
    """`Decide what this is →` · `Ask for more` · `Refuse` (danger), plus
    `Save & exit` and `Park — waiting on ▾` beneath them.

    An action is offered when the STATE allows it. Approval additionally needs
    an outcome and clear conditions, and that is reported as a REASON rather
    than by hiding the button: *"Nothing is refused — it simply cannot be
    approved yet."*

    ⚠ **THAT SENTENCE WAS A CLAIM AND NOT A GUARANTEE UNTIL 2026-09-16 — THE
    SCREEN GREYED THE BUTTON AND PRINTED NO REASON, AND WORSE, IT SOMETIMES DID
    NOT GREY IT AT ALL (`DEF-CUS-5427`, hard-won law 1).** Both halves are fixed
    in the dialog, not here.

    ⚠ **AND THIS LIST CANNOT ANSWER THE DIALOG'S QUESTION, WHICH IS WHY IT IS NO
    LONGER THE ONLY THING IT READS.** `approve_blocked_by` is computed from the
    STORED outcome. The document checklist is keyed on the outcome
    (`BR-CUS-095`), so a request with nothing decided reports every condition
    clear and this list says `["outcome"]` — accurately — over a request that
    will refuse the moment `move_in` is written to it. **The per-outcome answer
    lives on the decision tab** (`what_approving_will_do[<outcome>].conditions`)
    and is what the modal reads once a radio has moved. This stays as it is: it
    is the REQUEST's state, which is what the header and the queue want.
    """
    available = rules.actions_available(request.state)
    blocking = rules.blocking_conditions(conditions)
    return {
        "available": list(available),
        "can_approve": bool(request.outcome) and not blocking,
        "approve_blocked_by": [c.key for c in blocking] or ([] if request.outcome else ["outcome"]),
        # ── PARK IS OFFERED FROM `submitted` AND NOWHERE ELSE ──────────────
        #
        # PO ratification 2026-09-20 §1, in the words *"this is correct - fix
        # it"*. This read answered `not is_terminal(state)`, which is a
        # DIFFERENT QUESTION from the one the screen asks, and it was wrong on
        # four states out of six:
        #
        #   * `draft`, `under_review`, `more_info` — park was offered and
        #     MOVES NOTHING from any of them. `park` writes `waiting_on` and
        #     changes state on exactly one pair, `submitted` → `under_review`;
        #     its own note says so.
        #   * `approved` — **not a terminal state.** `TERMINAL_STATES` is
        #     `(completed, refused, withdrawn, closed)`, so `is_terminal` said
        #     False and the screen offered park on an approved request, which
        #     the ratified table crosses out.
        #
        # ⚠ **PARK STAYS OUT OF `TRANSITIONS`, WHICH IS WHY THIS FIELD EXISTS
        # AT ALL.** `service_request_service.park`'s docstring: *"Putting it in
        # the table would make it appear in `actions_available` and therefore
        # offerable from states where it must move nothing."* That reasoning is
        # untouched — park is still not a lifecycle move a clerk picks off a
        # list. What changed is that the field answering *may the screen offer
        # it* now answers that question instead of a neighbouring one.
        #
        # ⚠ **THE WRITE PATH IS DELIBERATELY NOT NARROWED.** `park()` still
        # accepts any non-terminal state and still refuses a terminal one. The
        # ratification is about what the SCREEN OFFERS; tightening the write
        # would retire a behaviour the PO was not asked about, and the wider
        # refusal is a second line of defence under this one.
        "can_park": request.state == rules.SUBMITTED,
    }


def customer_category(request: models.ServiceRequest) -> dict[str, Any]:
    """REQ-03.2's `Customer category` + `Sub-category`, **READ BACK**.

    ────────────────────────────────────────────────────────────────────────
    THE COLUMN WAS WRITTEN AND NEVER SERVED — the 4.12 read-model gap, closed
    ────────────────────────────────────────────────────────────────────────
    `set_customer_category` has written `account_type_id` / `account_subtype_id`
    since W4 landed and **no tab served either one**, which cost two things a
    clerk actually does: REQ-02 could not say what a request had been
    categorised as, and a half-finished draft reopened from the list could not
    restore the chip the clerk picked — so a returning clerk saw seven blank
    chips over a row that already held `builder_developer`, and re-picking it
    fired the write again. (That second write is DEF-657's 500 until its `str()`
    fix lands, so the absence had teeth.)

    **WHY THE APPLICANT TAB, when B19 §12.3 draws it on neither tab.** It is
    drawn on the CAPTURE form (REQ-03.2) and on no detail tab at all, so a home
    had to be chosen and this is a lane judgment, recorded rather than left to
    be discovered. It sits beside `person_or_company` because B19 §14.3 settles
    that those two are the **two axes of the same question** — `applicant_kind`
    is the LEGAL-PERSON axis (`customers.kind`) and this is the ACCOUNT
    CATEGORY axis (`accounts.account_type_id`), one legal person, one place or
    use, both true at once. Putting them anywhere but side by side is how the
    third vocabulary in §14.3 got confused for the first.

    ⚠ **`legacy` IS SERVED AND IS NOT COSMETIC.** BR-CUS-094 keeps `government`
    lawful on every row that already carries it and unselectable on a new one.
    A restore that read only the code would find it missing from the picker and
    silently drop it — re-labelling by omission, which is precisely the human
    act the ruling reserves (*"no row is re-labelled by guess"*). So the payload
    says the code is legacy and the screen shows it as picked-and-not-pickable.

    ⚠ **NOT AN ABSENCE BLOCK.** An uncategorised request is not waiting on a
    ruling or a defect — the clerk has not reached step 2 yet — so this carries
    `not_yet_categorised: true` and no `_absence`/`tracks` pair. G38's
    discipline is that a stated absence cites the row that will kill it, and
    there is no such row here.

    ⚠ **AND IT IS NOT THE HEADER'S `classification`.** That field is the
    OUTCOME chip (`NOT YET CLASSIFIED` — new connection · move-in · move-out ·
    transfer · disconnect, decided on the Decision tab). Two different words
    for two different columns, kept apart on purpose.
    """
    if request.account_type_id is None:
        return {
            "account_type": None,
            "account_subtype": None,
            "not_yet_categorised": True,
        }
    kind = request.account_type
    subtype = request.account_subtype
    return {
        "account_type": {
            "id": str(kind.id),
            "code": kind.code,
            "name": kind.name,
            # BR-CUS-094 — picked, lawful, and NOT in the picker.
            "legacy": kind.legacy,
            "selectable": bool(kind.active) and not kind.legacy,
        },
        "account_subtype": (
            {
                "id": str(subtype.id),
                "code": subtype.code,
                "name": subtype.name,
                # BR-CUS-067's two-level tree. NULL on a row written before
                # migration 0011 and nothing invents a parent for one.
                "parent_account_type_id": (
                    str(subtype.account_type_id) if subtype.account_type_id else None
                ),
            }
            if subtype is not None
            else None
        ),
        "not_yet_categorised": False,
    }


def applicant_tab(request: models.ServiceRequest) -> dict[str, Any]:
    """`Name · Phone · Email · ID · Language · Acting for · Date of birth · …`

    ✅ **`ID` IS A VALUE NOW, NOT AN ABSENCE** — BR-CUS-092(c), PO ruling
    2026-08-27 closing DEF-632. It carries the LAST FOUR of the Social Security
    number and never the number. TWO rows remain absences with a defect behind
    them (`date_of_birth`, `acting_for`) plus the driving licence, which
    BR-CUS-092(a) names and this ruling did not reach.
    """
    return {
        "name": request.applicant_name,
        "phone": request.applicant_phone,
        "email": request.applicant_email,
        "language": request.preferred_language,
        "person_or_company": request.applicant_kind,
        # ── the SECOND axis, B19 §14.3 ──────────────────────────────────────
        # `person_or_company` is the legal person; this is what the account is
        # priced as. See `customer_category` for why they are neighbours.
        "customer_category": customer_category(request),
        "co_applicant": {
            "name": request.co_applicant_name,
            "email": request.co_applicant_email,
            "phone": request.co_applicant_phone,
        },
        # ⊕ **LANE CF-1 (2026-10-18) — THE SHARED CUSTOMER FORM'S OTHER
        # VALUES, READ BACK.** Every value the request asks is served so the
        # capture wizard reopens on it and the move-in / new connect it leads
        # to opens filled in (decision log 2026-10-18, *"every field arrives
        # filled in"*). The co-applicant cards' SSN and licence travel as their
        # LAST FOUR only (BR-CUS-092(c)); the government ID is stored as four.
        "co_applicants": writes.co_applicant_rows(request),
        "contact_by": request.contact_by,
        "gov_id_last4": request.gov_id_last4,
        "preferences": {
            "paperless": bool(request.paperless),
            "sms_reminders": bool(request.sms_reminders),
        },
        "mailing_address": _mailing_parts(request),
        # ⊕ DEF-CUS-10251 — a portal request with no category yet: the Approve
        # window draws *Category to be set* and holds Approve until it is.
        "category_to_be_set": _category_to_be_set(request),
        # ✅ **THE SOCIAL SECURITY NUMBER — LAST FOUR AND NOTHING ELSE.**
        # BR-CUS-092(c), verbatim: *"every read path renders **last four only**
        # and the full value is never in a list response, an export, a log line
        # or an audit `details` blob"*. PO ruling 2026-08-27 closing DEF-632.
        #
        # ⚠ **`crypto.last_four()` IS CALLED HERE, ON THE SERVER, AND THE FULL
        # VALUE NEVER ENTERS THE PAYLOAD.** The temptation is to serve `ssn` and
        # let the screen mask it — that is what "shown as the last four" sounds
        # like, and it is a leak: the number is then in the JSON, in the browser
        # devtools, in any proxy log and in a HAR file a support engineer
        # attaches to a ticket, masked in exactly one place. Masking is a SERVER
        # projection (B8: a rule belongs on the server).
        #
        # `stored_encrypted` is the claim BR-CUS-092(d) held off the screen
        # until the encryptor was live. It is served as a FACT ABOUT THIS ROW —
        # true when there is a value, `False` when the column is empty — so the
        # screen can never print "stored encrypted" over a blank.
        "identifier": {
            # ⊕ DEF-CUS-10225 — a portal applicant gives the LAST FOUR and no
            # more (PO 2026-10-18), stored encrypted in `applicant_ssn_last4`;
            # served the same way, so the clerk reads one row either way.
            "ssn_last4": crypto.last_four(request.ssn)
            or crypto.last_four(request.applicant_ssn_last4),
            "ssn_present": bool(request.ssn),
            # ⚠ **THIS KEY IS THE SSN's, AND ITS NAME DOES NOT SAY SO.** It
            # predates the driving licence by three weeks and one consumer and
            # one signed proof file read it, so it keeps its name and its
            # meaning; the licence's own flag is spelled out below. If a THIRD
            # encrypted identifier ever arrives, rename this one then — two
            # flags with different naming conventions is survivable, three is
            # DEF-638 12.c wearing a different hat.
            "stored_encrypted": bool(request.ssn),
            # ✅ **THE DRIVING LICENCE — LAST FOUR AND NOTHING ELSE, THE SAME
            # PROJECTION AND FOR THE SAME REASON (BR-CUS-092(c), PO ruling
            # 2026-09-15 finishing clause (a)).** `crypto.last_four()` is called
            # HERE, on the server, and the full value never enters the payload:
            # a number that reaches the browser is in devtools, in a proxy log
            # and in the HAR file a support engineer attaches to a ticket,
            # masked in exactly one place.
            "drivers_licence_last4": crypto.last_four(request.drivers_licence),
            "drivers_licence_present": bool(request.drivers_licence),
            # BR-CUS-092(d) — a FACT ABOUT THIS ROW, so the screen can never
            # print "stored encrypted" over a blank.
            "drivers_licence_stored_encrypted": bool(request.drivers_licence),
            # ⊕ **`DEF-CWP-9045` — A BUSINESS'S TAX ID, AS TYPED ONLINE, LAST FOUR
            # ONLY.** `OQ-CWP-1560` closed (b) on 2026-09-04: the number *"stays
            # on the draft and the clerk reads it from there"* — stored ONCE —
            # and nothing read it. It is read through the customers → portal
            # seam and projected HERE, the same way the SSN is: the full value
            # never enters the payload.
            **_application_tax_id(request),
        },
        # ✅ **THE DATE OF BIRTH IS A VALUE NOW, NOT A STATED ABSENCE** — PO
        # ruling 2026-09-15, and it is the middle clause of `BR-CUS-089`'s
        # *name + date of birth + one government ID*. It is NOT under
        # `identifier`, deliberately: `BR-CUS-1020` says *"`BR-CUS-092` names two
        # identifiers of which it is not one"*, and it is served in FULL because
        # nothing signed masks it.
        #
        # ⚠ **THE TWO ABSENCE KEYS THAT STOOD HERE ARE GONE IN THE SAME COMMIT
        # AS THE COLUMNS** — `drivers_licence_absence` tracking BR-CUS-092 and
        # `date_of_birth_absence` tracking DEF-638 12.b. Landing a column and
        # retiring the sentence that said it did not exist are two acts, and only
        # the first one feels like the work (CLAUDE.md hard-won law 2's mirror: a
        # live column behind a dead refusal). `ServiceRequestDetailPage` moved
        # from `StatedFact` to `Field` in the same commit.
        "date_of_birth": (request.date_of_birth.isoformat() if request.date_of_birth else None),
        # ⊕ **`DEF-CWP-9163` — WHERE THE APPLICANT ASKED FOR THE BILL TO GO.**
        # Typed on the portal's start-service form and stored once, on the
        # draft; read through the seam so the clerk sees it before opening the
        # account that will carry it. `None` = the bill goes to the service
        # address (the applicant left *Same as the service address* ticked).
        "application_mailing_address": _application_mailing_address(request),
        # ⚠ **`acting_for` IS STILL ABSENT AND STAYS STATED.** DEF-638 12.b named
        # two fields and the ruling of 2026-09-15 named one of them; the other
        # has no column, no vocabulary and no ruling. Deleting this row would
        # convert an unbuilt half into a silent one.
        "acting_for_absence": {"tracks": "DEF-638"},
        "customer_match": {
            "customer_id": (
                str(request.matched_customer_id) if request.matched_customer_id else None
            ),
            "tier": request.match_tier,
            "basis": request.match_basis,
            "confirmed_at": (
                request.match_confirmed_at.isoformat() if request.match_confirmed_at else None
            ),
            # BR-CUS-089: only a strong match may move money.
            "may_move_money": request.match_tier == "strong",
            # ⊕ **`DEF-CUS-9043` — WHO, BY THE TENANT'S OWN NUMBER.** The row
            # printed tier and basis and never the customer, so after *Record
            # that I searched* it was blank and after a link it named nobody.
            # The number and the name are what a clerk reads (B14 rule 31 —
            # never the id); `None` with `confirmed_at` set is *searched, none
            # on file*.
            "customer_no": (
                request.matched_customer.customer_no if request.matched_customer_id else None
            ),
            "display_name": (
                request.matched_customer.display_name if request.matched_customer_id else None
            ),
        },
    }


#: What the resolver did to find the place — served beside the ids so a screen
#: can draw the blueprint's `Matched premises P-00074 · exact` (p083).
#:
#: ⚠ **IT IS DERIVED, NOT STORED, AND IT IS A STATEMENT ABOUT THE MECHANISM
#: RATHER THAN A CONFIDENCE SCORE WE INVENTED.** The blueprint prints a word
#: after each number and the request holds no column for one. What it holds is
#: the match itself, made by exactly one matcher: `seams.unit_id_for_reference`
#: resolves a unit by **exact reference only** — a `unit_no`, a
#: `"premise · label"` pair or a uuid (`BR-CUS-047`) — and the premises comes
#: from that unit. So a match this product made IS an exact-reference match, and
#: saying so is reporting what the code does.
#:
#: ⚠ **WHAT IT IS NOT: A TIER.** `service_requests.match_tier` and `match_basis`
#: are `BR-CUS-089`'s CUSTOMER match — *is this applicant the Sarah Miller we
#: already bill* — and have nothing to do with the address. Reading one for the
#: other is `DEF-2804`'s shape: a real field read for a different real field.
#:
#: The screen maps this code to a catalogue sentence, exactly as it already maps
#: `resolution_kind`. A fuzzy matcher, if one is ever built, adds a second value
#: here rather than changing what this one means.
MATCH_BY_EXACT_REFERENCE = "exact_reference"


def resolved_place(request: models.ServiceRequest) -> dict[str, Any]:
    """The matched premises and unit **named**, not keyed — `DEF-CUS-5386` —
    and the town, state and postcode **walked to**, never copied.

    ⚠ **THE LOCALITY IS THE PREMISES', AND THAT IS A PO RULING OF 2026-09-15,
    NOT A STYLE CHOICE.** Verbatim: *"if we have unit or street address then we
    should take it from premises/Unit - it means its a search and if not foudn
    them alow user to add them"*. The blueprint draws `Austin TX 78704` on the
    request's address line (p083) and the request holds no such columns —
    **deliberately**, because `CLAUDE.md` hard rule 8 / `BR-MET-1161` puts an
    address on `premises` and makes everything else derive it by walking. Three
    columns here would have been the fourth home `G85` exists to refuse.

    This is `DEF-CUS-3653`'s fix applied to a second screen: the account header
    composed its locality from a retired `customers.addresses` row and reads
    `premise_locality` now, through this same seam.

    ⚠ **IT IS SERVED UNDER A NAME THAT SAYS WHOSE IT IS.** `premise_locality`,
    never `city`/`state`/`zip` at the top level, so no screen and no later
    payload can mistake it for something the applicant typed. What the applicant
    typed is `address_as_given` and `address_unit_as_given`, beside it, kept
    verbatim (`BR-CUS-070`) — the blueprint's own footnote on p083: *"What they
    typed is kept beside what we matched, never replaced by it."*

    ⚠ **NULL UNTIL THE ADDRESS RESOLVES, WHICH IS A REAL STATE.** A request for
    a connection at a field with no premises on record — *"exactly the job this
    wizard exists for"*, p077 — has no locality to walk to, and the screen says
    so rather than showing a blank town.

    ── THE NUMBERS ────────────────────────────────────────────────────────────
    The Accounts blueprint p083 draws this fact twice and names it both times:
    `Matched premises PR-0731 · exact` and `Matched unit U-001884 · exact`. The
    product served the raw `resolved_premises_id` and the screen printed
    `01a0a444-5ad2-7e88-be8a-bdb8aa86c05e` in front of a clerk — **B14 rule 31,
    ratified by the PO on 2026-08-31 in the words *"no Databse ID on screen -
    that is a rule"***.

    ⚠ **THE DRAWN NUMBERS ARE ILLUSTRATIONS (B14 rule 37).** Ours are `P-00074`
    and `U-00101-A`; the format is NOT changed to match the picture.

    ⚠ **THE IDS STAY IN THE PAYLOAD.** Rule 31 forbids a database id as the
    VISIBLE VALUE of a field, not in the response — `DEF-2716`'s proved fix
    keeps it on `title=`, and a screen that lost the id could not link anywhere.

    ⚠ **A NUMBER CAN BE NULL WHILE THE ID IS NOT, AND THAT IS A REAL STATE, NOT
    A FAULT.** `premises.premise_no` and `units.unit_no` are both nullable —
    a tenant that has never turned on its numbering series has rows without
    them — so the screen needs the premises' ADDRESS as the fallback a person
    can actually read, and `premise_address` travels for exactly that. A screen
    that fell back to the id would reintroduce the defect.

    ⚠ **AND METERING MAY REFUSE.** `seams.unit_row` raises the same
    404-never-403 refusal metering raises for an id this tenant cannot see, and
    a resolved id can outlive the unit it named. That is served as *the number
    is not known*, never as an exception on a read of the whole request.
    """
    place: dict[str, Any] = {
        "resolved_premises_no": None,
        "resolved_unit_no": None,
        # DEF-CUS-10705 — the unit's LABEL ("B", "Unit 3"), a refinement of the
        # premises by label (hard rule 8): the request head draws it after the
        # street at a building with several units (p082 `· Unit 3 ·`).
        "resolved_unit_label": None,
        "resolved_premise_address": None,
        "premise_locality": None,
        "resolved_match": None,
    }
    if request.resolved_unit_id:
        try:
            unit = seams.unit_dict(seams.unit_row(request.resolved_unit_id))
        except errors.NotFoundError:
            return place
        place["resolved_unit_no"] = unit.get("unit_no") or unit.get("label")
        place["resolved_unit_label"] = unit.get("label") or None
        place["resolved_premises_no"] = unit.get("premise_no")
        place["resolved_premise_address"] = unit.get("premise_address")
        place["resolved_match"] = MATCH_BY_EXACT_REFERENCE
        premises_id = request.resolved_premises_id or unit.get("premises_id")
    elif request.resolved_premises_id:
        # No unit, a premises: unreachable through today's resolver, which only
        # ever fills the premises FROM the unit. Served rather than assumed
        # away, because a request whose unit was later merged or removed would
        # land here and a `KeyError` on a detail read is worse than a null.
        try:
            premises = seams.premises_ref(request.resolved_premises_id)
        except errors.NotFoundError:
            return place
        place["resolved_premises_no"] = premises.get("premise_no")
        place["resolved_premise_address"] = premises.get("address_line")
        place["resolved_match"] = MATCH_BY_EXACT_REFERENCE
        premises_id = request.resolved_premises_id
    else:
        return place
    # THE WALK — `BR-MET-1161`. Three columns of the premises row, through the
    # module that owns them, exactly as `_premise_locality` reaches an account's.
    # `None` while metering cannot answer, which reads as *nobody recorded it*.
    #
    # The STORED id is preferred over the unit's own, because it is the evidence
    # the clerk decided on; the unit's is the fallback for a row resolved before
    # `resolved_premises_id` was being filled.
    place["premise_locality"] = seams.premises_locality(premises_id)
    return place


def _requested_start_agreement(service_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Three facts about the per-service starts — and NOT a sentence.

    **BR-CUS-1070.** Step 6's review block draws `Requested start → 05/12/2026,
    all three` when every service wants the same day and lists them when they do
    not (`p080`). A screen cannot say *all three* from the list alone without
    deciding what *agree* means, and two screens deciding that separately is how
    they come to disagree — so it is decided here, once.

      * `count` — how many services are on the request. Zero is a real answer:
        a request that has not reached step 2 yet, which is every one of the
        demo tenant's eight.
      * `agreed` — the one ISO date when EVERY service carries the same non-null
        date, and `null` otherwise.
      * `unset` — how many carry none. This is what separates *nobody gave a
        date* (`agreed` null, `unset` == `count`) from *they disagree*
        (`agreed` null, `unset` 0), which a single null could not.

    ⚠ **ALL-UNSET IS NOT AN AGREEMENT.** Three services all saying *not given*
    must never read as three services agreeing on a date; `agreed` is a date or
    it is nothing.
    """
    starts = [row["requested_start"] for row in service_rows]
    given = [start for start in starts if start]
    agreed = given[0] if given and len(given) == len(starts) and len(set(given)) == 1 else None
    return {"count": len(starts), "agreed": agreed, "unset": len(starts) - len(given)}


def location_tab(
    request: models.ServiceRequest,
    evidence: rules.Evidence,
    place: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """`Address as given · Resolved to · Consequence · Plot reference · …`

    **BR-CUS-070 is the shape of this payload**: `address_as_given` and the
    resolved record are two fields, side by side, and the resolved one never
    replaces the given one. The detail draws the footnote in as many words:
    *"The address as the applicant gave it is kept verbatim and never
    overwritten by the resolved record."* The blueprint says the same thing on
    p083: *"What they typed is kept beside what we matched, never replaced by
    it. The resolver is evidence; if the two ever disagree, the clerk can see
    both."*

    ⚠ **BOTH ADDRESSES ALREADY TRAVEL, AND THAT IS STATED HERE BECAUSE IT WAS
    CHECKED RATHER THAN ASSUMED (`CR-094-BRC01` wave 1, 2026-09-15).** The PO
    ruled *"we have to show service address and also allow to take billing
    address"*; `billing_address_same` and `billing_address_as_given` have been
    in this payload since W4 and the capture step has collected them since
    REQ-03.3. **Nothing was changed for that half of the ruling** — the gap was
    on the screen, which draws neither, and the screen is wave 2's.

    ⚠ **THE ADDRESS IS NEVER COMPOSED HERE.** What the applicant said and what
    the premises holds travel as separate fields and the SCREEN writes the
    sentence — `_premise_locality`'s own rule next door: *"three columns travel,
    and the screen writes the sentence."* The blueprint punctuates the line two
    different ways on two frames (`Austin TX 78704` on p083, `Austin, TX 78704`
    on p082's head), so the punctuation is an illustration (B14 rule 37) and
    composing it on a server would be choosing between two drawings.
    """
    place = resolved_place(request) if place is None else place
    service_rows = [
        {
            "code": row.service.code,
            "requested_start": row.requested_start.isoformat() if row.requested_start else None,
            # NULL is *not yet asked* — REQ-03.3's CHECK callout.
            "available": row.available,
        }
        for row in models.ServiceRequestService.objects.filter(request=request)
        .select_related("service")
        .order_by("service__sort", "service__code")
    ]
    return {
        "address_as_given": request.address_as_given,
        "address_unit_as_given": request.address_unit_as_given,
        # ⚠ **THE PARTS THE APPLICANT GAVE — PO ruling 2026-09-22.** Served so
        # the capture wizard can read its own draft back; **not the service
        # address**, which is the matched premises' and is
        # `resolved_premise_address` / `premise_locality` below. The names say
        # so, and the decision log of that date says nothing downstream may
        # read them otherwise.
        "address_city_as_given": request.address_city_as_given,
        "address_state_as_given": request.address_state_as_given,
        "address_postal_code_as_given": request.address_postal_code_as_given,
        # ⊕ `BR-CUS-1055` — `Units on the property · 6`, drawn on the request's
        # own screen (p082) and captured on step 3 (p077). A CLAIM: what the
        # applicant says is there, which the register may agree with or not.
        "units_on_property": request.units_on_property,
        "billing_address_same": request.billing_address_same,
        # ⚠ The one-box value every request captured before 2026-09-23 holds,
        # served exactly as typed and never parsed (`DEF-CUS-6408`, `DEF-2703`).
        "billing_address_as_given": request.billing_address_as_given,
        # ✅ The PARTS, as the applicant gave them (`DEF-CUS-6408`). The screen
        # writes the line from them; nothing here composes one.
        "billing_line1_as_given": request.billing_line1_as_given,
        "billing_line2_as_given": request.billing_line2_as_given,
        "billing_city_as_given": request.billing_city_as_given,
        "billing_state_as_given": request.billing_state_as_given,
        "billing_postal_code_as_given": request.billing_postal_code_as_given,
        "resolved_premises_id": (
            str(request.resolved_premises_id) if request.resolved_premises_id else None
        ),
        "resolved_unit_id": str(request.resolved_unit_id) if request.resolved_unit_id else None,
        # ⊕ `BR-CUS-1114` (PO 2026-10-02) — how many live DWELLING units (common
        # areas not counted) the resolved premises HOLDS — the register's count,
        # not the applicant's claim above — so the *Owner's master account* door
        # can close on a single unit with its reason. `None` = none resolved.
        "resolved_premises_units": (
            _dwelling_units(request.resolved_premises_id)
            if request.resolved_premises_id
            else None
        ),
        # ⊕ `CR-162-BRC10` (Q1) — the SERVER's own answer to *may this address
        # have an owner's master account?*, read off the premises type's
        # *Account type* setting (count fallback for an unanswered type), so
        # the door and the guard cannot disagree. `None` = none resolved.
        "resolved_premises_master_allowed": (
            _master_allowed(request.resolved_premises_id)
            if request.resolved_premises_id
            else None
        ),
        # ⊕ `DEF-CUS-5386` — the two ids NAMED, beside the ids themselves, and
        # the premises' own town/state/postcode WALKED TO. See `resolved_place`:
        # B14 rule 31 forbids a database id as the visible value of a field and
        # this tab printed one, and hard rule 8 says where a locality comes from.
        **place,
        "resolution_kind": request.resolution_kind,
        # STORED, not recomputed (B19 §7) — the sentence a clerk decided on.
        "lookup_found": request.lookup_found,
        "plot_or_parcel": request.plot_or_parcel,
        "what_is_being_built": request.what_is_being_built,
        "property_type": request.property_type,
        "no_premise_flag": request.no_premise_flag,
        "services": service_rows,
        # ✅ **BR-CUS-1070 — DERIVED ONCE, ON THE SERVER.** Step 6's review block
        # draws `Requested start → 05/12/2026, all three` when the dates agree
        # and lists them when they do not (`p080`), and the request detail draws
        # the same fact. Two screens computing *do these agree* from the list
        # above would eventually disagree, so the answer is a served fact and
        # the WORDING is the screen's (B14 rule 33 caps a fact at six words).
        "requested_start_agreement": _requested_start_agreement(service_rows),
        "evidence": {
            "premise_exists": evidence.premise_exists,
            "unit_is_served": evidence.unit_is_served,
            "unit_is_vacant": evidence.unit_is_vacant,
        },
    }


def _actor_display_name(user: Any) -> str | None:
    """Who acted, as a PERSON — never as a database id (B14 rule 31).

    The same shape as `_uploader_name` below and deliberately not shared with
    it: one reads a document's uploader and one reads a timeline row's actor,
    and folding them into a generic `_name(obj)` would make the next change to
    either of them a change to both.
    """
    if user is None:
        return None
    name = (getattr(user, "full_name", "") or "").strip()
    return name or None


def _uploader_name(row: Any) -> str | None:
    """Who attached it, as a PERSON — never as a database id (B14 rule 31).

    ⚠ **THIS EXISTS BECAUSE `uploaded_by` IS A UUID AND THE BLUEPRINT DRAWS A
    NAME.** p078's `UPLOADED BY` column reads `S. Ortiz · 05/04/2026`, and the
    only thing this payload carried was `str(d.uploaded_by_id)` — which a screen
    obeying the drawing would have printed straight into the cell. Rule 31 is
    ruled in the PO's own words (*"no Databse ID on screen - that is a rule"*),
    so the name is served and the id stays where it is useful.

    `None` rather than a placeholder: a row seeded by `CR-030` or written by a
    background process has no user, and the SCREEN decides what an absence looks
    like — the drawing says an em dash, and a server that returned "—" would have
    chosen a glyph for every future caller.
    """
    user = getattr(row, "uploaded_by", None)
    if user is None:
        return None
    name = (getattr(user, "full_name", "") or "").strip()
    return name or None


def _brought_by_applicant(request: models.ServiceRequest, rows: list[Any]) -> set[Any]:
    """⊕ `DEF-CUS-9834` — the cards whose file the PORTAL stored, i.e. the
    applicant brought it (`attach_from_portal` is the only writer under
    `PORTAL_STORE_PROCESS`, for the application and for a reply to *Ask for
    more*). One query for the whole tab, never one per row (`NFR-3`)."""
    from uuid import UUID

    from apps.customers.service_request_documents import PORTAL_STORE_PROCESS
    from apps.tenancy.document_models import StoredDocument

    refs: dict[Any, Any] = {}
    for d in rows:
        if d.uploaded_by_id or not d.storage_ref:
            continue
        try:
            refs[d.pk] = UUID(str(d.storage_ref))
        except ValueError:
            continue
    if not refs:
        return set()
    portal = set(
        StoredDocument.objects.filter(
            tenant_id=request.tenant_id,
            pk__in=list(refs.values()),
            stored_by_process=PORTAL_STORE_PROCESS,
        ).values_list("pk", flat=True)
    )
    return {card for card, ref in refs.items() if ref in portal}


def documents_tab(request: models.ServiceRequest) -> dict[str, Any]:
    """*"2 of 3 verified"* — and the `BLOCKING` callout beneath it.

    ✅ **THE CHECKLIST IS SERVED — BR-CUS-095 (PO 2026-08-24), closing OQ-351.**
    *"Settings grows a checklist — for each request type, tick which documents
    are required. We ship with nothing ticked, and a utility that configures
    nothing blocks nothing."*

    Three fields carry it, and they are deliberately three rather than one:
    `checklist_required` is what the TENANT ticked for this request's outcome,
    `checklist_unmet` is what of that is not both attached and verified, and
    `required_flag` per ROW is still what a CLERK marked on this one request.
    A screen that collapsed them would be unable to tell a utility-wide rule
    from one clerk's note.

    ⚠ **An empty `checklist_required` is the shipped state and is not an
    absence** — it needs no `_absence` block and gets none. Nothing is waiting
    to be ruled; the tenant simply has not ticked anything, which the ruling
    calls the correct default.
    """
    # ⚠ `select_related` IS NOT A TIDY-UP — `_uploader_name` walks the FK on
    # every row, so without it a request with ten documents costs ten extra
    # queries on a screen a clerk opens all day (`NFR-3`'s neighbourhood).
    rows = list(
        models.ServiceRequestDocument.objects.filter(request=request)
        .select_related("uploaded_by")
        .order_by("created_at", "id")
    )
    with_file = [d for d in rows if d.storage_ref]
    unmet = writes.unmet_required_documents(request)
    by_applicant = _brought_by_applicant(request, rows)
    return {
        "documents": [
            {
                "id": str(d.id),
                "doc_type": d.doc_type,
                "what_it_proves": d.what_it_proves,
                # PO ruling 2026-09-22 — the SCREEN masks it to four. It is
                # served whole because a clerk correcting a typo needs to see
                # what is stored, and because masking on the server would make
                # the field unreadable to the form that writes it.
                "document_number": d.document_number,
                "name": d.name,
                # ⚠ **TWO SIZES, AND `original_size_bytes` IS `None` FOR ALMOST
                # EVERY ROW ON PURPOSE.** `size_bytes` is what is on disk;
                # `original_size_bytes` is what the clerk chose, and it is set
                # ONLY when `core.document_shrink` losslessly re-deflated an
                # oversized image on the way in. A PDF is stored byte for byte
                # and carries `None`. A clerk told a file is 3.1 MB who finds
                # 400 KB on disk needs the record to say why — and a field that
                # always echoed `size_bytes` would answer that wrongly rather
                # than not at all.
                #
                # ⚠ **NUMBERS, NOT FORMATTED STRINGS.** The screen formats them
                # with the shared kit's one formatter; a server returning
                # "1.2 MB" has decided a locale's decimal separator on the
                # server, which is the mistake `BR-SHL-034` records for dates.
                "size_bytes": d.size,
                "original_size_bytes": d.original_size,
                "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
                "uploaded_by": str(d.uploaded_by_id) if d.uploaded_by_id else None,
                # ⊕ `DEF-CUS-9834` — a file the APPLICANT brought through the
                # portal has no staff uploader by design; it is named as the
                # applicant (`uploaded_by_role`), so the cell reads *Kyle Mark
                # (applicant)* and never a bare date.
                "uploaded_by_name": (
                    _uploader_name(d)
                    if d.uploaded_by_id or d.pk not in by_applicant
                    else ((request.applicant_name or "").strip() or None)
                ),
                "uploaded_by_role": (
                    "applicant" if not d.uploaded_by_id and d.pk in by_applicant else None
                ),
                "attached": bool(d.storage_ref),
                # ⚠ **`attached` ANSWERS "IS THE COLUMN SET" AND `file_present`
                # ANSWERS "IS THERE A FILE". THEY DISAGREE ON SIX LIVE ROWS
                # (`DEF-CUS-5872`).** Every `service_request_documents` row on
                # the beta carries a ref shaped `sample-data://cr030/…`, none of
                # the six resolves to a `stored_documents` row, every `size` is
                # NULL and four read `verified`. So `bool(storage_ref)` is True
                # for all six and a screen reading it shows a file that cannot
                # be opened — which is the lie one level up from the one
                # `service_request_documents.document_dict` already refuses.
                #
                # ⚠ **`attached` IS NOT CHANGED, AND THAT IS DELIBERATE.** It
                # drives `verified`/`attached` below, which a live screen prints
                # as *"2 of 3 verified"*; moving it is a maintenance fix with its
                # own reproduce step and blast radius, and it is named in
                # `DEF-CUS-5872`'s prevention column. This is the ADDITIVE half:
                # a new, honest field that no existing caller reads, computed by
                # the same test the write path uses, so the two cannot drift.
                "file_present": doc_files.has_real_file(d),
                # CR-158-BRC10 — the TYPE the store recorded the bytes to be,
                # so the clerk reads `PDF` rather than trusting a file's name.
                "content_type": doc_files.stored_content_type(d),
                "required": d.required_flag,
                "verification_state": d.verification_state,
                "verified_at": d.verified_at.isoformat() if d.verified_at else None,
                "reject_reason": d.reject_reason,
            }
            for d in rows
        ],
        "verified": sum(1 for d in with_file if d.verification_state == d.VERIFIED),
        "attached": len(with_file),
        # THE TWO GATES, served as two fields so a screen cannot conflate them.
        "blocks_creation": False,
        # ⚠ **AND THE SECOND GATE IS NO LONGER A GATE — PO ruling 2026-09-16,
        # verbatim: *"lets not make it mandetory"*.** This field held the
        # expression now on `outstanding` below, and a screen that went on
        # printing *"cannot be approved until every required document is
        # checked"* over a product that approves is hard-won law 1 wearing a
        # translation. **It is served as a literal False rather than removed**,
        # so a caller that still reads it gets the truth instead of a KeyError,
        # and the next reader meets the ruling rather than an absence.
        "blocks_approval": False,
        # What the clerk is TOLD — the other half of the same ruling, *"if you
        # want ywe can show the messge documents will be required"*. Exactly the
        # expression `blocks_approval` used to carry.
        "outstanding": bool(unmet)
        or any(d.verification_state != d.VERIFIED for d in with_file)
        or any(d.required_flag and not d.storage_ref for d in rows),
        # BR-CUS-095 — the tenant's own ticks for THIS request's job type.
        "checklist_request_type": request.outcome,
        "checklist_required": list(writes.required_document_types(request.outcome)),
        "checklist_unmet": list(unmet),
    }


def _waive_reason_names(rows: list[models.ServiceRequestFee]) -> dict[str, str]:
    """The utility's own NAME for each waive reason CODE on these lines.

    `DEF-CUS-6423`: a waived fee read *"Application fee $0.00 waived. BILLERR"*
    — the reason's CODE where its name belongs (B14 rules 31/32). The waive
    form offers the tenant's reason list (`GET /payments/reason-codes`, name
    shown, code sent), so what `waive_reason` stores is a code, and the name is
    Settings' to answer: `BILLERR` → *Billing error correction*.

    Read from tenancy's own selector, the same rows the picker offered — the
    shape `disconnect_reads` and `move_record_reads` already take for a
    read-only lookup. One query, and only when a line IS waived. A reason that
    matches no active code is served as typed (an older free-text waive is
    already words); a code a utility has since switched off reads as typed too,
    which is the stored truth rather than an invention.
    """
    if not any(f.waived and f.waive_reason for f in rows):
        return {}
    from apps.tenancy import selectors as tenancy_selectors

    return {row["code"].upper(): row["name"] for row in tenancy_selectors.active_reason_codes()}


def _waive_reason_name(reason: str | None, names: dict[str, str]) -> str | None:
    text = (reason or "").strip()
    if text == "":
        return None
    return names.get(text.upper(), text)


def fees_tab(request: models.ServiceRequest) -> dict[str, Any]:
    """`Application fees` + `Connection quote`, and the `SEPARATE` callout that
    keeps them apart: *"settling one does not settle the other."*

    ✅ **THE TOTALS ARE SERVED — BR-CUS-090 (PO 2026-08-24), closing DEF-637.**
    The capture totalled $130.00 and the receipt said $25.00 for the same cash,
    and the ruling is that **both were right about their own half**: *"we acept
    it and in finance we will reconcile ; here segregation of responsibilitys,
    accept it and mark it as cash"*.

    So the panel gets four figures rather than one: `quoted`, `settled`,
    `collected` and `outstanding`, each with its stored 4-dp amount, a
    2-dp `display` for the screen and the `CHAR(3)` currency beside it
    (CLAUDE.md rule 2 — rounding for a human happens once, here).

    **Worked, on the screen that raised the defect:** quoted **$130.00**,
    collected **$25.00**, receipt `RCP-26-4471` → outstanding **$105.00**, which
    is the figure the review step reads and the sentence the request shows.
    """
    rows = list(models.ServiceRequestFee.objects.filter(request=request).order_by("line_no"))
    totals = writes.fee_total_to_collect(request.id)
    currency = totals["currency"]
    reason_names = _waive_reason_names(rows)
    counter_receipt = totals.get("counter_receipt") or {}
    return {
        "lines": [
            {
                # ⚠ **THE ROW'S OWN ID, AND SERVING IT IS THE WHOLE OF
                # `DEF-CUS-6096` (2026-09-21).** `POST .../fees/{fee_id}/waive`
                # addresses the row by PRIMARY KEY — a uuid7 — and this payload
                # served `line_no` and nothing else, so the screen had no id to
                # send and sent the LINE NUMBER. `"1"` is not a uuid, so the
                # lookup raised before any rule was reached and the waive was a
                # 500 on every press, with nothing on screen to say so.
                # `line_no` stays: it is what the clerk reads and what
                # `data-fee-line` is keyed on. **The two are not
                # interchangeable** — one names a row to a person, the other
                # names it to an endpoint.
                "id": str(f.id),
                "line_no": f.line_no,
                "charge_code": f.charge_code,
                "description": f.description,
                "basis": f.basis,
                "quantity": str(f.quantity),
                "unit_amount": _money(f.unit_amount, f.currency),
                "amount": _money(f.amount, f.currency),
                "waived": f.waived,
                # The stored CODE stays served for any caller that sends it
                # back; a screen prints `waive_reason_name` (`DEF-CUS-6423`).
                "waive_reason": f.waive_reason,
                "waive_reason_name": _waive_reason_name(f.waive_reason, reason_names),
                "settled_at": f.settled_at.isoformat() if f.settled_at else None,
                "invoice_ref": f.invoice_ref,
            }
            for f in rows
        ],
        # ⚠ **THE DRAWN `Total` ROW, COMPUTED HERE AND PRINTED THERE.**
        # `03-service-1440.png` and `04-review-1440.png` both draw a `Total`
        # beneath the fee table, and hard rule 2 says the browser may not
        # arrive at it: `DEF-088` and `DEF-127` are what multiplying and
        # summing money in a screen has already cost this product. It is
        # served as the `_money` pair every other figure here uses — the
        # stored 4-dp `amount`, the 2-dp `display` the screen prints, and the
        # `CHAR(3)` currency beside it, which `DEF-CUS-7806` is the defect for
        # omitting.
        #
        # ⚠ **IT IS NOT `Σ lines[].amount` AND A SCREEN THAT SUMMED THE COLUMN
        # WOULD DISAGREE WITH IT.** A waived line keeps its own `amount` and
        # its `waived: true` (`DEF-CUS-6423` — `quoted` alone read $0.00 as
        # the waived figure and the panel printed that), so the column adds up
        # to more than the total whenever anything is waived. Which is exactly
        # why the total is the server's answer and not the browser's.
        #
        # It is the same figure as `quoted` by construction rather than by
        # coincidence, and both are served: `quoted` is BR-CUS-090's word in a
        # four-figure money panel, `total` is the drawn table's last row.
        "total": _money(totals["quoted"], currency),
        "outstanding_lines": sum(1 for f in rows if not f.waived and f.settled_at is None),
        # BR-CUS-090 — the quote, what the counter took, and the open balance.
        "quoted": _money(totals["quoted"], currency),
        # What was WAIVED, which `quoted` cannot say: `quoted` sums the
        # UNWAIVED lines, so after a waive it reads 0.00 — and the panel
        # printed exactly that as the waived amount (`DEF-CUS-6423`).
        "waived": _money(sum((f.amount for f in rows if f.waived), Decimal("0")), currency),
        "settled": _money(totals["settled"], currency),
        "collected": _money(totals["collected"], currency),
        "outstanding": _money(totals["outstanding"], currency),
        # ⚠ A SHORTFALL IS NOT A WAIVER AND NOT A REFUSAL. Stated in the payload
        # so a screen cannot draw it as either (BR-CUS-073 owns waivers).
        "shortfall_is_open_balance": totals["outstanding"] > 0,
        "receipt_no": totals["receipt_no"],
        "collected_at": (totals["collected_at"].isoformat() if totals["collected_at"] else None),
        "quoted_at_collection": (
            _money(totals["quoted_at_collection"], currency)
            if totals["quoted_at_collection"] is not None
            else None
        ),
        "fee_timing": request.fee_timing,
        "fee_due_by": request.fee_due_by.isoformat() if request.fee_due_by else None,
        "fee_method": request.fee_method,
        # ⚠ **DERIVED FROM THE POSTING THAT EXISTS, NOT STATED (`DEF-CUS-6381`).**
        # This read a literal `False` under B18 §4.6's *"the fees are a
        # quote"*, and that stopped being true on 2026-09-15: money taken at
        # the counter posts `DR 1010 · CR 2400` through payments
        # (`record_counter_receipt`). So it is True exactly when payments holds
        # a counter receipt for this request with a collection journal entry,
        # and False for a quote nobody has paid — which is most requests.
        "posts_to_ledger": bool(counter_receipt.get("collection_entry_id")),
        "connection_quote": {"raised": False, "reason": "raised_after_review"},
    }


#: The fact line the Approve window already prints for this refusal.
_IN_PREMISES_KEY = "customers.serviceRequest.checkFact.addressInPremises"


def _refuse_new_connection_in_premises(
    verdicts: list[dict[str, Any]], what_approving_will_do: dict[str, Any]
) -> list[dict[str, Any]]:
    """PO 2026-10-11 (option A): at an address ALREADY in Premises, *New
    connection* is graded `not_possible` WITH its reason, so the window greys it
    out before the click instead of refusing after it.

    It reads the new connection's own `address_not_in_premises` condition — the
    one `_refuse_unless_approvable` refuses on (2026-09-23, *"A NEW CONNECTION
    ONLY WHERE THE ADDRESS IS NOT IN PREMISES"*) — so the grade and the refusal
    are one fact. Only `blocked` counts: a NEAR match is `choose` and stays
    pickable, because the clerk may still answer *it's a new address*.
    """
    preview = what_approving_will_do.get(_SR.OUTCOME_NEW_CONNECTION) or {}
    rows = (preview.get("conditions") or {}).get("conditions") or []
    in_premises = any(
        row.get("key") == rules.ADDRESS_NOT_IN_PREMISES
        and row.get("state") == rules.CONDITION_BLOCKED
        for row in rows
    )
    if not in_premises:
        return verdicts
    return [
        {**row, "verdict": rules.NOT_POSSIBLE, "message_key": _IN_PREMISES_KEY}
        if row.get("outcome") == _SR.OUTCOME_NEW_CONNECTION
        else row
        for row in verdicts
    ]


def decision_tab(
    request: models.ServiceRequest, evidence: rules.Evidence, conditions: list[rules.Condition]
) -> dict[str, Any]:
    """`WHAT SHOULD THIS BECOME?` — five options, **nothing preselected**.

    Every `not_possible` badge carries the message key of the PO's own sentence;
    `possible` carries none, because *the evidence does not rule this out and
    nothing rules it in* is **OQ-356** and not a sentence to invent.
    """
    what_approving_will_do = {
        option: {
            **request_jobs.approval_preview(request, option),
            "conditions": rules.conditions_summary(
                _conditions_considering(request, conditions, option)
            ),
        }
        for option in _SR.JOB_OUTCOMES
    }
    verdicts = _refuse_new_connection_in_premises(
        rules.outcome_verdicts(evidence), what_approving_will_do
    )
    return {
        "what_they_said": request.what_they_said,
        "what_the_lookup_found": request.lookup_found,
        "options": verdicts,
        "preselected": None,  # *"Nothing is preselected."*
        "undrawn_verdict_absence": {"tracks": "OQ-356"},
        "conditions": rules.conditions_summary(conditions),
        "commit": {
            "outcome": request.outcome,
            "decided_by": str(request.decided_by_id) if request.decided_by_id else None,
            "decided_at": request.decided_at.isoformat() if request.decided_at else None,
            "decided_against_evidence": request.decided_against_evidence,
            "outcome_kind": request.outcome_kind,
            "outcome_ref": request.outcome_ref,
        },
        # ── DEF-CUS-5389 — WHAT WAS SAID, AND TO WHOM ───────────────────────
        # ⚠ **THREE FIELDS, THREE AUDIENCES, AND THE SCREEN MUST NOT MERGE
        # THEM.** `reason_code` is what the utility FILES the refusal under and
        # is one of five (`service_request.REFUSAL_REASONS`) — a CODE, so the
        # screen renders it through its own catalogue and never prints the
        # value (B14 rule 31). `decision_reason` is the clerk's internal note.
        # `message` is the blueprint's `What to tell them`, which is the body of
        # the letter the applicant receives — the only one of the three they
        # ever see.
        "refusal": {
            "reason_code": request.reason_code,
            "reason": request.decision_reason,
            "message": request.refusal_message,
        },
        # The Ask-for-more dialog's two controls. `needed` is a list of CODES
        # from `service_request.INFO_NEEDED_KINDS`, in the drawing's own order,
        # and it is the clerk's checklist rather than something the applicant is
        # sent — the drawing attaches *Sent to them* to the message alone.
        "more_info": {
            "needed": list(request.info_needed or []),
            "message": request.info_message,
        },
        # ✅ BR-CUS-091 — the list drew a DISCONNECT request and this panel said
        # one could not exist. The PO ruled the list was right, the panel's
        # reason is withdrawn, and the option now decides like any other. It
        # carries NO badge and no special absence.
        #
        # ⚠ What survives the withdrawal, and the screen must keep saying it: a
        # disconnect leaves the account OPEN AND ACCRUING (BR-MET-105) where a
        # move-out CLOSES it and settles the deposit (BR-CUS-030). The clerk is
        # picking between two different things, not two names for one.
        "disconnect_is_not_a_move_out": {
            "rule": "BR-CUS-091",
            "move_out": "closes_the_account_and_settles_the_deposit",
            "disconnect": "leaves_the_account_open_and_accruing",
        },
        # ── CR-094-BRC01 — `WHAT APPROVING WILL DO`, drawn p083–p084 ─────────
        # One preview per OPTION, keyed by outcome, so the modal can redraw the
        # table the instant a radio moves without a round trip — and so it
        # computes nothing itself. The drawing's own consequence line rides on
        # each, because *"Raises a build on the New connects tab"* is the
        # drawing's sentence and not a screen's invention.
        #
        # ⚠ It is the SAME function the approve preview endpoint serves, so the
        # sentence a clerk reads before pressing the button and the row the tab
        # shows afterwards cannot disagree.
        #
        # ⚠ **AND SINCE 2026-09-16 EACH ONE ALSO CARRIES THAT OUTCOME'S OWN
        # CONDITIONS (`DEF-CUS-5427`).** `actions.approve_blocked_by` is
        # computed from the STORED outcome, so it cannot move with a radio and
        # cannot see a blocker the clerk's own pick is about to create — which
        # is what let the commit go live on `SR-26-0003` with nothing beside it.
        # The modal reads THIS, keyed by the radio it just drew, and works none
        # of it out for itself.
        "what_approving_will_do": what_approving_will_do,
        "acknowledgement": {
            "state": request.acknowledgement_state,
            "reason": request.acknowledgement_absence_reason,
            "ref": request.acknowledgement_ref,
            # BR-CUS-079 — never a fabricated `sent`.
            "sent": False,
            # BR-CUS-090 clause (3) — the acknowledgement may not print
            # "Nothing is charged" over a panel confirming cash was taken.
            "fee_statement": writes.fee_statement(request),
        },
    }


#: The `note_type` families only the CUSTOMER writes — their own note
#: (`portal.services._note`, `_keep_their_own_words`) and their reply to *Ask
#: for more* from Track (`DEF-CWP-9049`). Both arrive through
#: `note_from_portal` with no staff actor and `customer_visible=True`.
CUSTOMER_AUTHORED_EVENT_TYPES: tuple[str, ...] = ("customer_note", "customer_replied")


def _customer_wrote(event: Any) -> bool:
    """`DEF-CUS-9091` — did the CUSTOMER write this row?

    Until 2026-10-02 every row with no staff actor printed *System* in WHO —
    the word the screen keeps for *nobody was signed in* — so a clerk reading
    the history of a request the applicant had just answered saw the answer
    credited to the machine. The test is the row's own act (its `note_type`
    family), never merely the absence of an actor: numbering, the move to
    Submitted and a background job have no actor either and stay `system`.
    """
    family = (event.note_type or "").split(":")[0]
    return event.actor_id is None and family in CUSTOMER_AUTHORED_EVENT_TYPES


def history_tab(request: models.ServiceRequest) -> list[dict[str, Any]]:
    """*"This request only · newest first"*, mixing `Note` and `System` rows,
    each stamped date · time · actor. Append-only — nothing edits one.

    ⚠⚠ **`actor_name` EXISTS BECAUSE THE DRAWING HAS A `WHO` COLUMN AND THIS
    PAYLOAD COULD NOT FILL IT (2026-09-19).** p083 letters the history table
    `WHEN · WHAT · WHO` and prints `S. Ortiz` and `A. Whitfield` in the third
    column. All `actor` has ever carried is `str(e.actor_id)` — a UUID — and
    **B14 rule 31 forbids a database id being the visible value of a field**
    (the PO's own words: *"no Databse ID on screen - that is a rule"*). So the
    screen drew the column EMPTY under a note reading *"Who acted is not named
    yet"*, which is a stated absence over a fact the server was holding all
    along and simply not resolving.

    **The name is resolved HERE and not on the screen**, because the screen has
    no way to turn a user id into a person and a second round trip per row is
    how a timeline becomes a query storm.

    ⚠ **`None` RATHER THAN A PLACEHOLDER.** A row written by a background job
    or planted by the sample seed has no user, and the SCREEN decides what an
    absence looks like — the drawing says an em dash, and a server returning
    "—" would have chosen a glyph for every future caller.

    ⚠ **`actor` STAYS AND IS STILL THE ID.** It is read by support and by
    `_customer_visible_events` one module over; removing it would be a change
    to a shape this lane was not asked about. What is new is an honest field
    beside it — the same additive shape `file_present` took beside `attached`.
    """
    return [history_row(e, request) for e in timeline_queryset(request)]


def timeline_queryset(request: models.ServiceRequest, *, kind: str = "all") -> Any:
    """The request's timeline, newest first, as a QUERYSET — so a paged reader
    takes the page in SQL (`NFR-3`) and `history_tab` above reads the same rows.

    ⊕ **`kind` — image 29's *All · Changes · Messages*** (`CR-171-BRC10`
    P1.07). `messages` is every row recording a letter to the applicant
    (`move_in_request.MESSAGE_EVENT_PREFIXES`); `changes` is everything else.
    An unknown value reads as `all`, because a list URL never errors over its
    params (`BR-SHL-011`).

    ⚠ `select_related` IS NOT A TIDY-UP — `_actor_display_name` walks the FK on
    every row, so a request with forty timeline rows would cost forty extra
    queries on a tab a clerk opens all day.
    """
    from django.db.models import Q

    from apps.customers import move_in_request

    rows = (
        models.ServiceRequestEvent.objects.filter(request=request)
        .select_related("actor")
        .order_by("-at", "-id")
    )
    is_message = Q()
    for prefix in move_in_request.MESSAGE_EVENT_PREFIXES:
        is_message |= Q(note_type__startswith=prefix)
    if kind == "messages":
        return rows.filter(is_message)
    if kind == "changes":
        return rows.exclude(is_message)
    return rows


def history_row(e: Any, request: models.ServiceRequest) -> dict[str, Any]:
    """One timeline row — `history_tab`'s shape, and the request Audit tab's
    (image 23: When · Who · What). See `history_tab` for every field."""
    return {
        "id": str(e.id),
        "at": e.at.isoformat(),
        "actor": str(e.actor_id) if e.actor_id else None,
        "actor_name": (
            _actor_display_name(e.actor)
            if e.actor_id
            else (request.applicant_name or None)
            if _customer_wrote(e)
            else None
        ),
        # ⊕ `DEF-CUS-9091` — WHO acted, as a KIND: a clerk (`staff`), the
        # applicant through the portal (`customer`), or nobody signed in
        # (`system`). See `_customer_wrote`.
        "actor_kind": "staff" if e.actor_id else ("customer" if _customer_wrote(e) else "system"),
        "kind": e.kind,
        "from_state": e.from_state,
        "to_state": e.to_state,
        "note": e.note,
        "note_type": e.note_type,
        "internal": e.internal,
    }


def message_source_ids(request: models.ServiceRequest) -> list[str]:
    """Every id a letter to this applicant can be queued under — the request
    itself (the acknowledgement) and each of its timeline rows (refusal, ask,
    approval: `service_request_events` keys those on the occasion row). Read in
    one statement; a request's own timeline is the bound, not the tenant."""
    return [str(request.id)] + [
        str(one)
        for one in models.ServiceRequestEvent.objects.filter(request=request).values_list(
            "id", flat=True
        )
    ]


def message_row(row: dict[str, Any]) -> dict[str, Any]:
    """One *Messages* tab row (image 22: Message · To · Channel · When · State).

    `template_code` is the MESSAGE — the catalogue names it (`BR-SHL-020`), so
    no sentence travels. `to_name` is the name on the envelope; `to_address`
    where it went. `status` is the queue's own word, and a screen reading it
    must not say *sent* for `queued` (`BR-NOT-013`).
    """
    return {
        "id": row["id"],
        "template_code": row.get("template_code"),
        "to_name": row.get("recipient_display_name"),
        "to_address": row.get("recipient_address"),
        "channel": row.get("channel"),
        "status": row.get("status"),
        "queued_at": row.get("queued_at"),
        "sent_at": row.get("sent_at"),
    }


def _master_allowed(premises_id: Any) -> bool:
    """`CR-162-BRC10` — `services.master_account_allowed_at_premises`, the one
    decision the master guard itself reads."""
    from apps.customers import services

    return bool(services.master_account_allowed_at_premises(premises_id)["allowed"])


def _dwelling_units(premises_id: Any) -> int | None:
    """`BR-CUS-1114` — the same count the master door refuses on, read from the
    one function that defines it so the screen and the refusal cannot differ."""
    from apps.customers import services

    return services.dwelling_units_at_premises(premises_id)
