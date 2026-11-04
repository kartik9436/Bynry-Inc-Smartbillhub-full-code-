# ── Trace ──────────────────────────────────────────────
# Change:  **PO drawings of 2026-09-25** — `Reconnect1` · `Reconnect2` ·
#          `MasterReconnect1` · `MasterReconnect2`. Putting service back on
#          stops being one dialog and becomes a SCREEN of two steps, at an
#          address of its own. `DEF-CUS-6743`.
# Story:   `US-CUS-032` (`S148`) — *Put service back on*.
# Drawing: The four PNGs above, read AS IMAGES (B14 rule 42). ⚠ **The Accounts
#          blueprint draws NOTHING here**: `05-prototype/02 Accounts Menu
#          Blueprint.pdf` is 283 pages and the word *reconnect* appears on five
#          of them — p143 (the case record's fee row), p146, p248, p249, p250 —
#          every one of them a FEE, a JOB TYPE or prose. p143 was read as an
#          image and draws three case actions: `Hold the case`, `Open the
#          account`, `Mark as cut`. There is no reconnection screen in it.
# Rules:   `BR-CUS-1097` (the balance need NOT be clear to reconnect — the
#          figure is SHOWN, nothing refuses) · `BR-CUS-104` (the fee lands AT
#          the cut and is a real receivable — untouched) · `BR-CUS-1098` (a
#          master's reconnect may need a visit PER AFFECTED SERVICE POINT, one
#          work order per point, and residue transferred up is shown SEPARATELY
#          from the owner's own debt) · `BR-CUS-097` (the residue) ·
#          `BR-CUS-171` (an occupying account is a master's child) ·
#          `BR-CUS-1100` (the block is on the ACCOUNT and the CUSTOMER) ·
#          `BR-WRK-055` (the flow does not wait for the visit) · hard rule 8
#          (an address lives on `premises`; this module declares none) · hard
#          rule 2 (money 4dp stored, 2dp displayed, never a float) · hard rule 7
#          (every money act writes `audit_log` — through the existing writers) ·
#          B14 rules 31, 33.
# Tests:   `06-backend/tests/test_reconnect_read.py`
# ───────────────────────────────────────────────────────
"""`GET /disconnects/{ref}/reconnect` — everything the two steps draw, once.

════════════════════════════════════════════════════════════════════════════
WHY THIS IS ITS OWN MODULE AND NOT A SECTION OF `disconnect_record.py`
════════════════════════════════════════════════════════════════════════════
`disconnect_record` answers *what is this case* for a page that previews a CUT.
This answers *what goes back on, and what is still owed* for a page that
restores one. They share an account and a case and nothing else: the record's
panels are notices, protections and the cut preview; these are service points,
work orders and a money table. Assembling both in one file would give one read
two audiences, and the second one always loses.

**IT WRITES NOTHING OF ITS OWN.** ⚠ Since 2026-10-29 (`DEF-CUS-10657`, PO C1
*"Restore = Reconnect request"*) it mounts the screen's COMMIT too — `/request`
calls `disconnects.mark_reconnecting` and `/complete` calls
`disconnects.restore_service`, the existing role-gated, audited writers; see
*THE COMMIT* at the foot of this file. The row's write mounted here —
`POST /disconnects/{ref}/reconnect/work-orders` — calls
`customers.services._raise_flow_work`, which is the NAMED door this module
already uses to ask Work for a job (`disconnects.mark_reconnecting` calls the
same one). Work's tables are Work's; nothing here touches them (`G78`).

════════════════════════════════════════════════════════════════════════════
⚠ THE BALANCE IS A FACT ON THIS SCREEN AND NEVER A GATE
════════════════════════════════════════════════════════════════════════════
`BR-CUS-1097`, PO 2026-09-25, verbatim: *"Show what's still owed and let the
clerk proceed"*. So `owed` below is a TABLE a clerk reads, and `warning` is one
sentence stating the figure. **Neither is a refusal and neither may become
one.**

⛔ **THE PARAGRAPH BELOW IS HISTORY — `not_settled` WENT ON 2026-09-25
(`BR-CUS-1097`) AND THE SCREEN'S HOLD ON IT WAS RELEASED ON 2026-10-29
(`DEF-CUS-10657`).** `commit_refused_by` still asks the engine, and now answers
`None` on every readable balance. Kept so a reader of the old screen can follow.

⛔ **AND THE PRODUCT STILL REFUSES, WHICH THIS FILE CANNOT FIX.**
`disconnects.reconnect_blockers` appends `not_settled` whenever `balance >
ZERO`, and `mark_reconnecting` raises the first blocker it is handed. That file
belongs to another lane; `DEF-CUS-6742` is the row. **So `commit_refused_by`
below reports the live refusal rather than hiding it** — a screen that offers a
button the server will refuse is worse than one that says so
(`BR-SHL-025`). The day that clause goes, this field answers `None` with nobody
editing it, because it asks the engine rather than restating it (hard-won law
1).

════════════════════════════════════════════════════════════════════════════
⚠ WHAT IS DERIVED AND WHAT IS STATED AS ABSENT
════════════════════════════════════════════════════════════════════════════
Every figure here is read from a place that owns it, and an absence is a
sentence rather than a zero (`DEF-127`). In particular:

  * **the meter on a service point** is frequently unknown on this fixture and
    is answered `None`, never invented;
  * **`paid_since`** is the arithmetic the ledger already supports — what was
    outstanding at the cut, less what is outstanding now, less the fee where it
    posted — and it is `None` when the live balance cannot be read, because a
    payment total derived from a failed reading is a fabricated receipt;
  * **`transferred_up`** is `BR-CUS-097`'s residue and is drawn ONLY for a
    master account, as its own line, which is what `BR-CUS-1098` signs.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.customers import disconnect_record, disconnects, seams, selectors
from core import errors

#: The three ways a service can come back on, in the order the drawing lists
#: them. **CODES, never sentences** — all eleven catalogues own the words
#: (B14 rule 35).
#:
#: ⚠ **`remote` IS THIS REPO'S PROPOSAL AND NOT A PO RULING.** It was drawn by
#: the coordinator on 2026-09-25 and handed over as *a proposal, not law*: a
#: service point that needs nobody to attend. Nothing signed contradicts it —
#: `BR-WRK-055` already makes *No visit needed* a RECORDED CHOICE rather than an
#: absence — so it is built and recorded in the decision log, reversible for the
#: cost of one line.
HOW_WORK_ORDER = "work_order"
HOW_REMOTE = "remote"
HOW_NO_VISIT = "no_visit"
HOW_ALL_UNITS = "all_units_together"
HOW_OPTIONS: tuple[str, ...] = (HOW_WORK_ORDER, HOW_REMOTE, HOW_NO_VISIT)

#: The master's second row — every unit meter, and the clerk cannot split it.
#: `BR-CUS-1098`: a master's reconnect is a BUILDING's reconnect.
HOW_OPTIONS_MASTER_UNITS: tuple[str, ...] = (HOW_ALL_UNITS,)

#: What the second step promises, as codes. `master` rows are added for a master.
CONSEQUENCES: tuple[str, ...] = (
    "supply_back_on",
    "base_charges_restart",
    "the_mark_clears",
    "work_orders_go_to_the_crew",
    "the_case_closes",
)
CONSEQUENCES_MASTER: tuple[str, ...] = (
    "common_supply_back_on",
    "all_units_together",
    "owner_charges_restart",
    "the_mark_clears",
    "work_orders_go_to_the_crew",
    "the_case_closes",
)

#: Why a figure is not on the screen. Each is a SENTENCE and a code, in the
#: shape every absence in this product carries.
BALANCE_UNREADABLE: dict[str, Any] = {
    "code": "balance_unreadable",
    "br_ref": "BR-PAY-032",
    "detail": (
        "what this account owes could not be read from the ledger. Nothing on this screen "
        "substitutes a zero for it: a restoration recorded against a fabricated balance is a "
        "receipt for a payment nobody made."
    ),
}

METER_NOT_RECORDED: dict[str, Any] = {
    "code": "meter_not_recorded",
    "br_ref": "BR-MET-110",
    "detail": (
        "no meter is recorded against this service point. The point is real and the service is "
        "real; the asset behind it is not on file, and one is not guessed onto a work order a "
        "crew will be sent out on."
    ),
}

NO_SERVICE_POINTS: dict[str, Any] = {
    "code": "no_service_points_recorded",
    "br_ref": "BR-MET-110",
    "detail": (
        "this account's unit has no service point on file, so the services this case cut cannot "
        "be placed at a point a crew could be sent to. The services themselves are on the case "
        "and are listed; the point each one comes back on is not known."
    ),
}

AT_CUT_NOT_RECORDED: dict[str, Any] = {
    "code": "arrears_at_the_cut_not_separable",
    "br_ref": "BR-CUS-104",
    "detail": (
        "what this account owed at the cut is recorded WITH the reconnection fee inside it, and "
        "the fee itself cannot be read from the tenant's charge code — so the two cannot be told "
        "apart. The still-owed total below is the ledger's and is unaffected."
    ),
}

TRANSFERRED_UP_NOT_SEPARABLE: dict[str, Any] = {
    "code": "transferred_up_not_separable",
    "br_ref": "BR-CUS-097",
    "detail": (
        "residue transferred up from the occupying accounts is inside this account's position "
        "and cannot be told apart from the owner's own debt by any read this product has. "
        "`BR-CUS-1098` requires it on its own line; the figure is owed."
    ),
}

#: ⚠ **THE FEE IS ALREADY INSIDE THE BALANCE AND IS NOT ADDED TO IT** —
#: `DEF-708` (PO 2026-08-27) made the cut raise it as a real charge, so the
#: position IS arrears plus fee. The money table therefore draws the fee as a
#: LINE and the still-owed total as the BALANCE, never as a sum of the lines
#: above it. Adding them would be `BR-CUS-104`'s $8,390.00 — the figure the PO
#: explicitly did not confirm.
FEE_IS_IN_THE_BALANCE: dict[str, Any] = {
    "code": "fee_is_already_in_the_balance",
    "br_ref": "BR-CUS-104",
    "detail": (
        "the cut raised the reconnection fee as a real charge, so the still-owed figure already "
        "includes it. The lines above are where the debt came from; the total is what the ledger "
        "says, read once."
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# THE ASSEMBLY
# ═══════════════════════════════════════════════════════════════════════════
def reconnect_detail(ref: str, *, as_of: Any = None) -> dict[str, Any]:
    """Everything `S148`'s two steps draw, from the places that own it."""
    case = _case_or_404(ref)
    account = disconnects._account(case.account_id)
    terms = disconnects.reconnection_terms(case.account_id, case=case)
    readiness = disconnects.reconnection_readiness(case.account_id, case=case)
    balance = disconnects._balance_for(case.account_id)
    is_master = _is_master(account)

    return {
        "case_no": case.case_no,
        "account": _account_panel(case, account, balance=balance, is_master=is_master),
        "master": _master_panel(account, is_master=is_master),
        "services": _services(case, account, is_master=is_master),
        "owed": _owed(case, account, terms=terms, balance=balance, is_master=is_master),
        "deposit": _deposit(terms),
        "consequences": [
            {"code": code} for code in (CONSEQUENCES_MASTER if is_master else CONSEQUENCES)
        ],
        # ⚠ **THE WARNING, AND IT IS THE WHOLE OF `BR-CUS-1097` ON SCREEN.**
        # A figure and four words. No rationale, no rule, no retention note
        # (B14 rule 33 — rationale is ZERO WORDS and is REMOVED, not shortened).
        "warning": _warning(balance),
        # What the engine would refuse TODAY, asked rather than restated.
        "commit_refused_by": _commit_refusal(readiness),
        "step": readiness.get("step"),
        "restore_on": str(disconnect_record._as_of(as_of)),
    }


def _case_or_404(ref: str) -> Any:
    """The case this address names, or a 404 — never a 500 and never a 403.

    `disconnect_record._case_by_reference` answers `None` for a number this
    tenant does not hold; every view here dereferenced it, so a foreign or
    mistyped `DSC-` number answered 500 (`AttributeError`). HR-1: absent and
    cross-tenant are the same 404 (found writing DEF-CUS-10657's isolation test).
    """
    case = disconnect_record._case_by_reference(ref)
    if case is None:
        raise errors.deny_as_not_found("BR-CUS-039")
    return case


def _is_master(account: Any) -> bool:
    """`BR-CUS-1010` — a master account is an ordinary account with a kind."""
    try:
        return account.kind == selectors.services_master_kind()
    except Exception:  # noqa: BLE001 — a tenant with no master kind seeded has none
        return False


def _account_panel(case: Any, account: Any, *, balance: Any, is_master: bool) -> dict[str, Any]:
    """The drawn account card: who, where, WHAT KIND, when it was cut, what it owes.

    ⚠ **`account_type` IS TWO FACTS AND THE DRAWING SHOWS BOTH** — *Regular ·
    Residential* and *Master · Commercial*. The first is the account's KIND and
    was on no reconnect surface before this screen; the second is the tenant's
    own `account_types` row by NAME (B14 rule 31). A clerk restoring a building
    needs to know it is a building before they press anything.
    """
    return {
        # B14 rule 31 — the account NUMBER and never its id.
        "account_no": account.account_no,
        "customer_name": selectors.primary_contact_name(account),
        # Hard rule 8 — WALKED to the premises. This module declares no address
        # column and copies none onto the case.
        "address": disconnect_record._premise_line(account),
        "account_kind": "master" if is_master else "regular",
        "account_class": disconnect_record._customer_class(account),
        "cut_on": str(case.cut_on) if case.cut_on else None,
        "balance": _money_or_absence(balance, account),
    }


def _master_panel(account: Any, *, is_master: bool) -> dict[str, Any]:
    """`BR-CUS-1098` — *"all 25 units come back on together"*, as a COUNT.

    ⚠ **UNITS CANNOT BE RESTORED ONE AT A TIME, AND THAT IS A FACT THE SCREEN
    STATES RATHER THAN A CONTROL IT DISABLES.** The drawing offers the clerk no
    per-unit choice at all, which is the honest shape: a disabled tick-box per
    unit would be twenty-five dead controls claiming a decision nobody may make
    (hard-won law 2, the live-control-that-means-nothing face of it).
    """
    if not is_master:
        return {"is_master": False, "units": None, "unit_accounts": None}
    units = None
    unit_accounts = None
    try:
        # `BR-CUS-068` — every unit this one bill must cover, anchor first.
        units = len(selectors.covered_unit_ids(account))
        # `BR-CUS-171` — the occupying accounts under it. The two differ: a
        # vacant unit is covered and occupies nobody, and the drawing's
        # *"25 occupying accounts"* is the second figure, not the first.
        unit_accounts = len(selectors.sub_accounts_for_master(account))
    except Exception:  # noqa: BLE001 — the count is a fact, never a guess
        units = None
    return {"is_master": True, "units": units, "unit_accounts": unit_accounts}


def _services(case: Any, account: Any, *, is_master: bool) -> dict[str, Any]:
    """One row per thing that goes back on, with WHERE and HOW.

    **The services are the ones this case CUT** (`disconnect_cases.services_cut`)
    — never the account's whole list, because a case that cut water and left
    electric on must not offer to restore electric.

    **The point each one comes back on is metering's**, read through the
    published seam. `BR-CUS-1098` makes a master's rows PER SERVICE POINT rather
    than per service; on a regular account the two are the same thing, which is
    why one loop serves both.
    """
    codes = tuple(case.services_cut or ())
    points = []
    try:
        points = list(seams.service_points_for(account.unit_id)) if account.unit_id else []
    except Exception:  # noqa: BLE001 — metering absent is an absence, not a crash
        points = []
    by_service: dict[str, list[dict[str, Any]]] = {}
    for point in points:
        by_service.setdefault(str(point.get("service") or ""), []).append(point)

    address = disconnect_record._premise_line(account)
    raised_by_service = _raised_jobs(case)
    rows: list[dict[str, Any]] = []
    for code in codes:
        matched = by_service.get(code) or [None]
        for point in matched:
            rows.append(
                {
                    "service": code,
                    # Hard rule 8 — the point is NAMED by the address it is at,
                    # walked; it carries no address of its own.
                    "service_point": address,
                    "point_known": point is not None,
                    # ⚠ **NEVER INVENTED** — `None` with its reason beside it.
                    "meter": None,
                    "meter_absence": dict(METER_NOT_RECORDED),
                    "how_options": list(HOW_OPTIONS),
                    "how_default": HOW_WORK_ORDER,
                    # The instruction is the CLERK's to type; it is a row field
                    # and not a sentence this module writes for them.
                    "instruction": None,
                    # `DEF-CUS-9630` — the job already raised for this service,
                    # read back on every load (it was `None` on every row, so a
                    # visit raised from this page vanished on the reload).
                    "work_order": raised_by_service.get(code),
                    # ⚠ **A SCOPE, NOT A SECOND SERVICE CODE.** The drawing
                    # reads *"Water — common supply"* and *"Water — unit
                    # meters"*: ONE service, two places it is restored. A
                    # pseudo-code like `unit_meters` would be a twelfth service
                    # in a product that has eleven, and `serviceLabel` — the
                    # one label per code product-wide — would print it raw
                    # (`DEF-763`'s shape). The screen composes the two.
                    "scope": "common_supply" if is_master else None,
                    "reaches": "all_occupants" if is_master else None,
                }
            )
    if is_master:
        # `BR-CUS-1098`'s second drawn row — the unit meters, all of them, and
        # the clerk may not split them.
        rows.append(
            {
                "service": codes[0] if codes else None,
                "scope": "unit_meters",
                "service_point": address,
                "point_known": bool(points),
                "meter": None,
                "meter_absence": dict(METER_NOT_RECORDED),
                "how_options": list(HOW_OPTIONS_MASTER_UNITS),
                "how_default": HOW_ALL_UNITS,
                "instruction": None,
                "work_order": None,
                "reaches": "each_unit",
            }
        )
    return {
        "rows": rows,
        "unavailable": None if rows else dict(NO_SERVICE_POINTS),
        # What `+ Add a service` may offer: a point this case did not cut.
        "addable": [
            {"service": str(point.get("service") or ""), "service_point": address}
            for code, group in by_service.items()
            for point in group
            if code not in codes
        ],
    }


def _raised_jobs(case: Any) -> dict[str, dict[str, Any]]:
    """The reconnect jobs this case raised, one per service — `DEF-CUS-9630`.

    Read through `seams.flow_work_visits` by the case's `DSC-` number, which is
    what `from_flows._resolve_reconnect` stamps on the job. Where a service has
    more than one job the latest number wins (a re-raise after a cancel).
    Work unreadable, or a case with no number, answers nothing — every row then
    offers the raise, which is what it did before.
    """
    case_no = getattr(case, "case_no", None)
    if not case_no:
        return {}
    answer = seams.flow_work_visits(flow_kind="reconnect", source_ref=case_no)
    by_service: dict[str, dict[str, Any]] = {}
    for order in (answer or {}).get("orders") or ():
        by_service[str(order.get("service") or "")] = {
            "reference": order["order_no"],
            "assignee": order.get("assignee"),
            "done": bool(order.get("done")),
            "accepted": bool(order.get("accepted")),
        }
    return by_service


def _reconnect_template_for(account_id: Any, service: str) -> list[str]:
    """The ROW's raise names a SERVICE; Work's offer names the template — `DEF-CUS-9630`.

    The screen sent `template_ids: [<service code>]`, which is no template, so
    every press from the row answered *not raised* and the row offered the raise
    again. The utility's own offer for a reconnect (`from_flows.propose`, which
    prefers a *Disconnection/Reconnection* template — `DEF-WRK-9626`) is read
    through the seam and the first one for this service is raised. None found
    is the existing refusal, by name.
    """
    offer = seams.propose_flow_work_orders("reconnect", str(account_id)) or {}
    of_service = []
    for row in offer.get("proposed") or ():
        code = (row.get("service") or {}).get("code") if isinstance(row.get("service"), dict) else row.get("service")
        if str(code or "") == service:
            of_service.append(row)
    # `CR-168-BRC10` P3.42 — a Work rule on *a paid account awaits
    # reconnection* that names a template of this service is the one raised
    # (Work marks it `preselected_by`; `raise_for` then applies the rule's
    # priority and holder). Otherwise the first, exactly as before.
    chosen = next((row for row in of_service if row.get("preselected_by")), None) or (
        of_service[0] if of_service else None
    )
    return [str(chosen["template_id"])] if chosen is not None else []


def _owed(
    case: Any, account: Any, *, terms: Any, balance: Any, is_master: bool
) -> dict[str, Any]:
    """The drawn money TABLE — four lines in a box become a table with a total.

    ⚠ **THE TOTAL IS THE LEDGER'S, NOT A SUM OF THE ROWS.** `DEF-CUS-6050`: the
    figure a clerk states and the figure the books hold must be one read. The
    lines say where the debt came from; `still_owed` is `_balance_for`, once.
    Summing the rows here would be money arithmetic in a screen assembler, and
    it is how `BR-CUS-104`'s $8,390.00 gets onto a page the PO never confirmed.
    """
    lines: list[dict[str, Any]] = []
    fee = terms.get("fee")
    # ⚠ **THE FEE IS INSIDE `outstanding_at_cut` AND IS TAKEN BACK OUT HERE.**
    # The column's own docstring says what it holds: *"the final metered bill
    # raised at the cut, the reconnection fee, and everything that was already
    # outstanding"*. The drawing shows the arrears and the fee as TWO lines, so
    # the arrears line is the recorded position LESS the fee — never the whole
    # figure, which would print the fee twice and make the table foot to more
    # than the ledger. Measured on `DSC-26-0005`: recorded $139.80, fee $75.00,
    # arrears $64.80 — and $64.80 is what that account owed before it was cut.
    arrears = _at_cut_less_fee(case, fee)
    lines.append(
        {
            "code": "own_debt_at_the_cut" if is_master else "arrears_at_the_cut",
            "from_code": "the_owners_account" if is_master else "the_account",
            "amount": disconnects._money(arrears) if arrears is not None else None,
            "unavailable": None if arrears is not None else dict(AT_CUT_NOT_RECORDED),
            "when": str(case.cut_on) if case.cut_on else None,
            "negative": False,
        }
    )
    if is_master:
        # `BR-CUS-1098` — residue transferred up, ON ITS OWN LINE.
        lines.append(
            {
                "code": "transferred_up_from_units",
                "from_code": "occupying_accounts",
                "amount": None,
                "unavailable": dict(TRANSFERRED_UP_NOT_SEPARABLE),
                "when": str(case.cut_on) if case.cut_on else None,
                "negative": False,
            }
        )
    lines.append(
        {
            "code": "reconnection_fee",
            "from_code": "the_tenants_charge_code",
            "amount": dict(fee) if fee else None,
            "unavailable": None if fee else dict(terms.get("fee_absence") or {}),
            "when": "at_the_cut",
            "negative": False,
        }
    )
    deposit = terms.get("deposit") or {}
    if case.deposit_disposition == disconnects.DEPOSIT_APPLIED and deposit.get("on_file"):
        lines.append(
            {
                "code": "deposit_applied",
                "from_code": "held_before_the_cut",
                "amount": dict(deposit["on_file"]),
                "when": str(case.cut_on) if case.cut_on else None,
                "negative": True,
            }
        )
    lines.append(_paid_since(case, balance=balance, fee=fee))
    return {
        "lines": lines,
        "still_owed": _money_or_absence(balance, account),
        "total_is_the_ledger": dict(FEE_IS_IN_THE_BALANCE),
        "plan_label": disconnect_record._customer_class(account),
    }


def _at_cut_less_fee(case: Any, fee: Any) -> Decimal | None:
    """The arrears WITHOUT the reconnection fee, or `None` when it cannot be split.

    `None` rather than the whole figure when the fee is unreadable: printing
    the recorded position on a line labelled *arrears* beside a fee line would
    state the fee twice, and a clerk reading a money table has no way to see it.
    """
    at_cut = case.outstanding_at_cut
    if at_cut is None:
        return None
    if not fee:
        return None
    return Decimal(str(at_cut)) - Decimal(str(fee["stored"]))


def _paid_since(case: Any, *, balance: Any, fee: Any) -> dict[str, Any]:
    """What has been paid against the debt since the cut — DERIVED, and honestly.

    ⚠ **IT IS ARITHMETIC OVER TWO FIGURES THE PRODUCT ALREADY HOLDS**, and it is
    `None` when either is missing. `outstanding_at_cut` is what was owed the day
    the supply went off; the fee landed at the cut on top of it (`BR-CUS-104`);
    `_balance_for` is what is owed now. The difference is what arrived. It is
    NOT a payments query: a total assembled from payment rows and a total
    implied by the ledger would be two answers to one question, and this screen
    already promises that the still-owed figure is the ledger's.

    **`None` rather than `0.00` when it cannot be worked out** — `DEF-127`: a
    zero is a figure somebody measured, and *"no payments"* and *"we could not
    tell"* must never render as the same cell.
    """
    at_cut = case.outstanding_at_cut
    if balance is None or at_cut is None:
        return {
            "code": "paid_since",
            "from_code": "payments",
            "amount": None,
            "unavailable": dict(BALANCE_UNREADABLE),
            "when": None,
            "negative": True,
        }
    # ⚠ **THE FEE IS NOT ADDED HERE AND THE FIRST DRAFT ADDED IT.** It is
    # already inside `outstanding_at_cut`, so adding it again reported
    # **$75.00 paid on an account nobody had paid a cent against** — a receipt
    # for a payment that never happened, on the screen whose whole job is to
    # state what is owed. Found by reading the live payload on `DSC-26-0005`,
    # not by a test. Whatever changes here, the test that pins it is
    # `test_paid_since_is_zero_when_nothing_has_been_paid`.
    paid = Decimal(str(at_cut)) - Decimal(str(balance))
    return {
        "code": "paid_since",
        "from_code": "payments",
        "amount": disconnects._money(paid if paid > Decimal("0") else Decimal("0")),
        "when": None,
        "negative": True,
    }


def _deposit(terms: Any) -> dict[str, Any]:
    """What was held, what happened to it, and what `DSC-02.4` says comes next.

    ⚠ **THE NEW DEPOSIT IS DRAWN AS A LINE THE CLERK SEES AND NOT AS A FIELD.**
    That is this repo's existing posture rather than a new decision: nothing in
    this product COLLECTS a deposit on this path, and a field that writes
    nowhere is dead UI (hard-won law 2). `ReconnectDialog` already drew it as a
    fact; the drawing of 2026-09-25 draws the same thing with its amount beside
    it, which is strictly more honest and nothing new.

    ⚠ **THE AMOUNT IS WHAT WAS HELD, AND THAT IS A STATEMENT WITH A LIMIT.**
    `DSC-02.4` says a new deposit is REQUIRED and says nothing about how much;
    nothing in this product prices one. So the figure carried here is the OLD
    one, labelled as the old one, and the screen says *due before service
    returns* rather than quoting a price nobody set.
    """
    deposit = terms.get("deposit") or {}
    return {
        "held_before_the_cut": deposit.get("on_file"),
        "disposition": deposit.get("election"),
        "new_deposit_required": deposit.get("new_deposit_required"),
    }


def _warning(balance: Any) -> dict[str, Any] | None:
    """`BR-CUS-1097` on screen: a figure, then four words. Nothing else.

    `None` when nothing is owed — a warning that says *$0.00 still owed* is a
    sentence with no reader.
    """
    if balance is None or balance <= Decimal("0"):
        return None
    return {"code": "still_owed_you_may_continue", "amount": disconnects._money(balance)}


def _commit_refusal(readiness: Any) -> dict[str, Any] | None:
    """What the engine would refuse TODAY, ASKED and never restated.

    ⛔ **`not_settled` IS THE ONE THAT SHOULD NOT BE THERE** (`BR-CUS-1097`,
    `DEF-CUS-6742`). It is reported rather than filtered out, because a screen
    that hides a refusal the server will make offers a button that does not
    work — and hiding it is exactly how a rule stays unbuilt while every screen
    looks finished. When `disconnects.reconnect_blockers` drops the clause this
    answers `None` with nobody editing this file.
    """
    blockers = list(readiness.get("blockers") or ())
    if not blockers:
        return None
    first = blockers[0]
    return {"code": str(first["code"]), "br_ref": str(first["br_ref"])}


def _money_or_absence(amount: Any, account: Any) -> dict[str, Any]:
    """Rule 2's two strings and a currency, or the reason there are none."""
    if amount is None:
        return {
            "stored": None,
            "display": None,
            "currency": account.currency,
            "unavailable": dict(BALANCE_UNREADABLE),
        }
    money = disconnects._money(Decimal(str(amount)))
    return {
        "stored": money["stored"],
        "display": money["display"],
        "currency": account.currency,
        "unavailable": None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE ROUTES
# ═══════════════════════════════════════════════════════════════════════════
from django.urls import path  # noqa: E402
from rest_framework.decorators import api_view, permission_classes  # noqa: E402
from rest_framework.response import Response  # noqa: E402

from core.permissions import AdminOrClerk  # noqa: E402
from core.tenancy import require_tenant  # noqa: E402


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def reconnect_read(request: Any, ref: str) -> Response:
    """`GET /disconnects/{ref}/reconnect` — `S148`, both steps, one read.

    ⚠ **`ref` IS THE CASE NUMBER, NEVER A UUID** (B14 rule 31), and the address
    is the case record's own plus one segment — `/disconnects/dsc-26-0005` is
    where a clerk comes FROM, so `/disconnects/dsc-26-0005/reconnect` is where
    they go, and the back link writes itself.

    ⚠ **`AdminOrClerk`, NOT `AnyTenantRole`** — the same reasoning
    `disconnect_record` states: every write this screen can reach is gated to
    those two roles, and a page that shows an Executive the whole restoration
    and then refuses every button is the mismatch that rule prevents.
    """
    require_tenant(request)
    return Response(reconnect_detail(ref, as_of=disconnect_record._query_as_of(request)))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def reconnect_raise_work_order(request: Any, ref: str) -> Response:
    """`POST /disconnects/{ref}/reconnect/work-orders` — raise ONE row's visit.

    ⚠ **THE CLERK RAISES IT FROM THE ROW, WHICH IS THE WHOLE POINT OF 4.5.**
    Before this, a work order was IMPLIED: `mark_reconnecting` raised whatever
    templates a clerk had ticked, at commit, and the row showed a word. A word
    is not a job — hard-won law 2 read from the screen end — so the row now
    carries the act, and a raised one shows its reference and who it is with.

    ⚠ **IT GOES THROUGH `services._raise_flow_work` AND NOWHERE ELSE.** That is
    the named door customers already uses to ask Work for a job, and `G78` fails
    a foreign write from Work's first commit. This endpoint adds an address; it
    adds no new way into Work's tables.

    ⚠ **IT NEVER FAILS THE SCREEN** (`BR-WRK-055`). `_raise_flow_work` returns
    the sentence rather than raising, so a deactivated template or an absent
    seam comes back as a warning on a row and the clerk carries on. A field
    module able to stop a restoration because a template was retired would be
    this product refusing to put somebody's water back on over a catalogue row.
    """
    from apps.customers import services as customer_services

    require_tenant(request)
    case = _case_or_404(ref)
    payload = request.data if isinstance(request.data, dict) else {}
    template_ids = customer_services._field_visit_templates(payload)
    if not template_ids and payload.get("service"):
        template_ids = _reconnect_template_for(case.account_id, str(payload["service"]))
    if not template_ids:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.reconnect.workOrder.noTemplate",
            params={},
        )
    raised = customer_services._raise_flow_work(
        request.user,
        flow_kind="reconnect",
        flow_id=str(case.account_id),
        template_ids=template_ids,
    )
    return Response(raised)


# ═══════════════════════════════════════════════════════════════════════════
# THE COMMIT — C1, *"Restore = Reconnect request"* (PO 2026-10-29) · DEF-CUS-10657
# ═══════════════════════════════════════════════════════════════════════════
# The screen's Confirm refused on both of its steps with *"This step is not
# built yet"*, held on a refusal (`not_settled`) the engine dropped on
# 2026-09-25. The reading is the decision log's of 2026-10-29 (*"C1 'Restore =
# Reconnect request': what it maps to"*), in two acts:
#
#   * on a CUT case, Confirm is the RECONNECT REQUEST — `mark_reconnecting`,
#     with one reconnect job per row the clerk left on *Work order*;
#   * on a RECONNECTING case, Confirm COMPLETES it — `restore_service`, which
#     restores the account and queues *Service restored* (DEF-NOT-10649).
#
# ⚠ **TWO ADDRESSES AND NOT ONE THAT PICKS BY STATE.** A press that means
# *request* must never become *restore* because the case moved between the
# screen being drawn and the button being pressed; each door asks the engine for
# exactly one act and the engine refuses the wrong state by name.
#
# ⚠ **NO NEW WRITE PATH.** Both call the existing, role-gated, audited writers
# in `disconnects`; the jobs go through `services._raise_flow_work` (the named
# door into Work, `G78`). This file adds addresses keyed by the CASE NUMBER
# (B14 rule 31) and nothing else.
def _request_templates(account_id: Any, services: Any) -> list[str]:
    """The utility's reconnect template for each service the clerk left on *Work order*."""
    ids: list[str] = []
    for service in services or ():
        for template in _reconnect_template_for(account_id, str(service)):
            if template not in ids:
                ids.append(template)
    return ids


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def reconnect_request(request: Any, ref: str) -> Response:
    """`POST /disconnects/{ref}/reconnect/request` — S148's Confirm on a CUT case.

    Body: `{"on_date": "YYYY-MM-DD", "services": ["water", …]}` — `services`
    are the rows still to be raised on *Work order*; rows on *Remote* or *No
    visit*, and rows the clerk already raised from the row, are not sent. An
    unpaid balance never refuses (`BR-CUS-1097`); the request is recorded with
    what was owed, who and when (`mark_reconnecting`'s audit row).
    """
    from apps.customers import transfer_disconnect_api as doors

    require_tenant(request)
    case = _case_or_404(ref)
    body = doors._payload(request)
    on_date = doors._required_date(body.get("on_date"), "on_date")
    services = body.get("services") or []
    if not isinstance(services, list):
        services = []
    templates = _request_templates(case.account_id, services)
    return Response(
        doors._laddered(
            lambda: disconnects.mark_reconnecting(
                doors._actor(request),
                case.account_id,
                on_date=on_date,
                template_ids={"template_ids": templates},
            )
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def reconnect_complete(request: Any, ref: str) -> Response:
    """`POST /disconnects/{ref}/reconnect/complete` — the request is done; service is back.

    ⚠ **A STAFF ACT, NEVER A FIELD SIDE-EFFECT** (`BR-PAY-036`). The reconnect
    job's state is SHOWN on the screen and on the case; closing it in the field
    restores nothing by itself. Refused by name before the request
    (`not_reconnecting`) and after the restoration (`no_open_case`), so the
    *Service restored* message is queued exactly once.
    """
    from apps.customers import transfer_disconnect_api as doors

    require_tenant(request)
    case = _case_or_404(ref)
    body = doors._payload(request)
    on_date = doors._required_date(body.get("on_date"), "on_date")
    return Response(
        doors._laddered(
            lambda: disconnects.restore_service(
                doors._actor(request), case.account_id, on_date=on_date
            )
        )
    )


urlpatterns = [
    path("disconnects/<str:ref>/reconnect", reconnect_read),
    path("disconnects/<str:ref>/reconnect/work-orders", reconnect_raise_work_order),
    path("disconnects/<str:ref>/reconnect/request", reconnect_request),
    path("disconnects/<str:ref>/reconnect/complete", reconnect_complete),
]
