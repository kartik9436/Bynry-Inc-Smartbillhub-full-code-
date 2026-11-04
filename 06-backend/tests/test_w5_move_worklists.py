# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-004 (move-in) · US-CUS-005 (move-out).
#           Screens: the Accounts screen's `Move-ins` and `Move-outs` tabs.
#           ⚠ **NEITHER TAB HAS A STORY.** Hard-won law 8; both are OWED, the
#           same finding S86/S89/S90 each filed.
# Change:   CR-030 W5 — the two move worklists, BACKEND cases.
# Rules:    BR-CUS-015 / DEF-127 (`accounts.balance` is a CACHE and an absence
#           is never spelled `0.00`) · BR-CUS-018 (the draft window) ·
#           BR-CUS-022 (an occupying account without a start date could never be
#           billed) · BR-CUS-023 (the deposit is a lookup) · BR-CUS-030 (the
#           move-out closes the account) · BR-CUS-055 (the behaviour CLASS,
#           never the label) · BR-CUS-057 (deposit interest — CONFIRMED, NOT
#           BUILT) · BR-CUS-080 (the SR→child link is TEXT) · BR-SHL-046 (a
#           move-out is SIX steps) · CLAUDE.md hard rules 1, 2
# Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.5 · §5.6 ·
#           §5.7.3 (the counting contract this file is the other half of)
# ───────────────────────────────────────────────────────
"""W5 · the Move-ins and Move-outs worklists — `apps/customers/move_reads.py`.

**THE FOUR CASES THIS FILE EXISTS FOR** are the four places these two tabs
could tell a utility something untrue:

  1. `test_a_committed_transfer_never_appears_as_a_move_out` — B18 §5.7.3's
     counting contract, and it is not a formality here.
     `transfers.commit_transfer` closes its outgoing half *through*
     `services.move_out`, so **every committed transfer sets a `closed_at` and
     a terminal status** and an unfiltered list shows all of them. §5.7.3:
     *"the same job listed three times would be counted three times."*
  2. `test_the_deposit_cell_never_says_waived` — B18 draws `waived` as one of
     five DEPOSIT sentences and no column records a disposition. A deposit
     nobody recorded and a deposit deliberately waived are different facts and
     would render as the same word.
  3. `test_the_outstanding_figure_is_the_ledgers_and_never_the_cached_balance`
     — DEF-127, exactly: `accounts.balance` is a cache nothing writes, and
     serving it once told a customer owing $108.88 that they owed nothing.
  4. `test_the_three_undecidable_tiles_are_null_and_never_zero` — DEF-127
     pointed at a KPI strip. `SHORTFALLS TO DECIDE · 0` says every closing
     account is square; `FINAL READS DUE · 0` says every meter has been read.
     Both read as good news to the one person paid to act on the bad kind.
     (⚠ Since 2026-08-26 — CR-038 W9 task 2 — `FINAL READS DUE` is a DERIVED
     count through `seams.reads_for_unit`, its meterless blind spot counted
     beside it; the case's docstring carries the amendment. The other two
     tiles still hold the null-never-zero line.)

⚠ **TWO ASSERTIONS HERE ARE DELIBERATELY NEGATIVE AND MUST STAY THAT WAY.**

  1. `test_a_move_out_in_flight_has_no_store` asserts that THREE of B18
     §5.6.2's four state segments REFUSE. They refuse because
     `services.move_out` writes `closed_at`, the terminal status and the
     agreement end dates in ONE commit and nothing records a move-out before
     that. If a later lane makes this green, it must be because a column was
     added — not because the refusal was inconvenient.
  2. `test_no_settlement_landing_is_ever_stated_on_the_list` asserts
     `landing is None` on every row. `MoveOutSettlement.landing`'s own rule is
     that *"any gap → no landing … one of those two directions posts a
     cheque"*, and both gaps are open on every row of this tab.

**RED PROVED FIRST for every guard** (hard-won law 7). Each was broken under a
mutation, run, the failure quoted in the lane report, and the mutation
reverted — no `# BREAK:` marker survives in this file (DEF-666).
"""

from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from apps.customers import models as customers_models
from apps.customers import move_out_settlement, move_reads, moves
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from apps.customers import transfers
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 25)

# ── ❄️ WE-7 / GT-23, frozen: $150.00 held at the tenant's rate = $3.50 ──────
DEPOSIT_HELD = D("150.00")

#: DEF-127's own figure — the account that owed $108.88 and was rendered $0.00.
LEDGER_OWES = D("108.88")
#: A DECOY written into the cache `accounts.balance`, deliberately different
#: from the ledger's figure, so a test cannot pass by reading the wrong column.
CACHED_DECOY = D("999.99")


# ════════════════════════════════════════════════════════════════════════════
# FIXTURE PLUMBING — real rows through real services (DEF-658), except the two
# MONEY columns every service door deliberately refuses (`REFUSED_FIELDS`:
# BR-CUS-023 the deposit, BR-CUS-015 the balance). A fixture that could set
# them through a door would mean the product had one.
# ════════════════════════════════════════════════════════════════════════════
def _plan(tenant, service_code="electric"):
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant, name="W5 Moves", defaults={"code": "w5-moves", "status": "published"}
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"W5 Moves — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _unit(actor, tenant, *, label="Unit A"):
    premises = make_premises(actor, services_available=["electric", "water"])
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(_plan(tenant).id)})
    metering_services.ensure_service_point(unit["id"], "electric")
    return unit


def _account(actor, tenant, *, label, name, status="active", opened_at="2026-07-01"):
    """One account through `services.create_account` — the ONE door into
    `_open_account`, so BR-CUS-017 and BR-CUS-056 apply to the fixture exactly
    as they apply to a hand-typed account."""
    unit = _unit(actor, tenant, label=label)
    payload = {
        "unit_id": str(unit["id"]),
        "account_type": "residential",
        "status": status,
        "contact": {"full_name": name},
        # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
        # customer identifies nobody, and this fixture's own name went in above.
        # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
        "customer": identity_fixtures.customer_block(name, account_type="residential"),
    }
    if opened_at is not None:
        payload["opened_at"] = opened_at
    return customers_services.create_account(actor, payload)


def _booked_in(actor, tenant, *, label="88 Pine Vista", name="Kwan, Michael", opened_at=None):
    """§1's window, opened: a BR-CUS-018 draft.

    `services.create_account`'s default status is `pending_activation`
    (behaviour class `non_billable`) — *"it is never billed, derives no
    occupancy and does not block the unit"* — which IS a move-in booked in and
    not yet open. `core/sample_fixture.py` plants B18 §5.5.7's `A-12048 · Kwan,
    Michael` in exactly this state.
    """
    return _account(
        actor, tenant, label=label, name=name, status="pending_activation", opened_at=opened_at
    )


def _moved_out(actor, tenant, *, label="17 Brambling Ct", name="Fitzgerald, Sean", on="2026-08-20"):
    """§2's window, opened: a real `services.move_out`, never a status UPDATE.

    A `closed_at` written by hand would prove that a column can hold a date. The
    thing under test is that the CLOSE — the signed BR-CUS-030 path — is what
    puts a row on this tab.
    """
    account = _account(actor, tenant, label=label, name=name)
    customers_services.move_out(actor, account["id"], {"moved_out_on": on})
    return customers_models.Account.objects.get(id=account["id"])


def _parked_move_out(
    actor,
    tenant,
    *,
    account=None,
    step=2,
    waiting_on="the customer",
    moved_out_on="2026-08-28",
    label="17 Brambling Ct",
    name="Ncube, Thandiwe",
):
    """§2's OTHER window, opened: a real parked MOVE-OUT wizard.

    ⚠ **THROUGH THE OWNING MODULE'S DOOR, NEVER `WizardPark.objects.create`.**
    `wizard_parks` is tenancy-hosted and `seams.park_wizard_draft` is the route
    customers is allowed to take (B1 / BR-TEN-013). A fixture that wrote the row
    directly would prove that a table can hold a step — the thing under test is
    that PARKING, the path a clerk actually walks, puts a row on this tab.

    The payload is the one `MoveOutWizard` sends: the account in `subject_ref`
    as a COPIED id (BR-SHL-048 (a) — there is no FK), the account headline in
    `subject_label`, and `moved_out_on` among the typed `values`.
    """
    from apps.customers import seams as customers_seams

    if account is None:
        account = _account(actor, tenant, label=label, name=name)
    account_id = str(account["id"] if isinstance(account, dict) else account.id)
    return customers_seams.park_wizard_draft(
        actor,
        {
            "flow": "move_out",
            "step": step,
            "subject_label": name,
            "subject_ref": {"account_id": account_id},
            "values": {"account_id": account_id, "moved_out_on": moved_out_on},
            "waiting_on": waiting_on,
        },
    )


def _with_deposit(account_id, amount):
    """BR-CUS-023 refuses `deposit_on_file` on both account doors, so the
    fixture writes it directly — and that refusal is itself the reason B18's
    DEPOSIT sentence has no store."""
    customers_models.Account.objects.filter(id=account_id).update(deposit_on_file=amount)
    return customers_models.Account.objects.get(id=account_id)


def _cache_says(account_id, amount):
    """Poison `accounts.balance` with a figure the LEDGER does not say.

    BR-CUS-015 — it is a cache and nothing in this product writes it. A test
    that seeded the same number in both places could not tell which column was
    read (DEF-127).
    """
    customers_models.Account.objects.filter(id=account_id).update(balance=amount)


class _EveryAccount(dict):
    """A `positions` map answering one figure for any account id.

    The real `seams.ArPositions` wraps it, so `available`, `amount_for` and
    DEF-127's *"an unwired seam reports, it never answers 0"* distinction are
    the product's own and not a fake of them.
    """

    def __init__(self, amount):
        super().__init__()
        self._amount = amount

    def get(self, _key, _default=None):
        return self._amount


def _ledger_says(monkeypatch, amount, *, available=True):
    """`available=False` is the UNREADABLE case and is a first-class fixture."""
    seams = move_reads.seams
    positions = (
        seams.ArPositions(positions=None, unavailable=seams.AR_POSITIONS_UNWIRED)
        if not available
        else seams.ArPositions(positions=_EveryAccount(amount), currency="USD")
    )
    monkeypatch.setattr(seams, "ar_positions", lambda *_a, **_k: positions)


def _committed_transfer(actor, tenant, *, name="Park, Jenna"):
    """B18 §5.7.6's shape, committed — the row that must appear on NEITHER tab."""
    account = _account(actor, tenant, label="901 Hillside Ave", name=name)
    customers_services.link_customer(account_id=account["id"], display_name=name)
    target = _unit(actor, tenant, label="26 Meadowbank Rise")
    started = transfers.start_transfer(actor, {"from_account_id": str(account["id"])})
    transfers.set_target_unit(actor, started["id"], {"to_unit_id": str(target["id"])})
    transfers.set_dates(actor, started["id"], {"out_date": "2026-08-28", "in_date": "2026-09-03"})
    transfers.elect_money(actor, started["id"], {})
    done = transfers.commit_transfer(actor, started["id"])
    return customers_models.Account.objects.get(id=account["id"]), done


def _linked_request(actor, tenant, account_no, *, name="Kwan, Michael"):
    """BR-CUS-080's link, written by the real `link_child`.

    `core/sample_fixture.py` seeds `SR-26-0045 → outcome_ref: "A-12048"` — the
    ACCOUNT NUMBER, because a move-in has no child table for a ref of its own.
    That is the whole reason the move-in tab can offer a `request #` search leg
    while `transfer_reads` had to give one up.
    """
    tenancy_models.NumberSeries.objects.update_or_create(
        tenant=tenant,
        series="service_request",
        defaults={"format": "SR-{YY}-{0000}", "next_number": 45},
    )
    request = sr.create_request(
        actor,
        {
            "channel": "portal",
            "applicant_kind": "person",
            "applicant_name": name,
            "applicant_email": "michael.kwan@example.invalid",
            "applicant_phone": "555-2048",
            "address_as_given": "88 Pine Vista",
            "property_type": "rental_tenant_applying",
            "what_they_said": "I'm taking over the lease",
        },
    )
    sr.submit(actor, request.id)
    # ⚠ **`pick_up` WAS HERE AND IS RETIRED (PO ruling 2026-09-19).** The
    # request keeps five states and a decision is taken straight from
    # `submitted`; there is no step in between left to walk.
    sr.decide_outcome(actor, request.id, outcome=customers_models.ServiceRequest.OUTCOME_MOVE_IN)
    sr.link_child(actor, request.id, child_ref=account_no, child_kind="account")
    return customers_models.ServiceRequest.objects.get(id=request.id)


def _row_for(payload, account_no):
    return next(row for row in payload["rows"] if row["account_no"] == account_no)


def _codes(entries):
    return [entry["code"] for entry in entries]


def _data_only(value):
    """A payload with every stated absence's `detail` prose stripped out.

    ⚠ **THIS HELPER EXISTS BECAUSE THE NAIVE VERSION FAILED, AND THE FAILURE WAS
    THE USEFUL KIND.** `test_the_deposit_cell_never_says_waived` first searched
    `str(cell)` for `"waived"` and went RED — on
    `DEPOSIT_SENTENCE_HAS_NO_STORE`'s own sentence, which quotes B18's five
    drawn outcomes in order to say that none of them can be printed. A test that
    cannot tell a word being SERVED from a word being EXPLAINED is not testing
    the thing it names. `test_w7_worklists.py` hit the identical trap on
    BR-CUS-097 and wrote the identical helper.
    """
    if isinstance(value, dict):
        return {key: _data_only(item) for key, item in value.items() if key != "detail"}
    if isinstance(value, (list, tuple)):
        return [_data_only(item) for item in value]
    return value


# ════════════════════════════════════════════════════════════════════════════
# 1 · WHAT A MOVE-IN IS IN THE DATA (§1 of `move_reads`)
# ════════════════════════════════════════════════════════════════════════════
def test_a_move_in_is_the_life_of_a_draft_account_and_ends_when_it_opens(brazos, marcus):
    """The tab's own copy: *"from the day a new occupant is booked in to the day
    their account opens"* — and that sentence is `create_account` and
    `activate_account` in this schema.

    `services.create_account`: *"Default status is BR-CUS-018's draft
    (`pending_activation`): it is never billed, derives no occupancy and does
    not block the unit."*
    `services.activate_account`: *"the pending account becomes the unit's
    occupant."*

    So the window OPENS when the row is created and CLOSES on activation. This
    asserts both edges, because a list that only proved the first would keep
    every account it ever showed.
    """
    with tenant_ctx(brazos):
        booked = _booked_in(marcus, brazos, opened_at="2026-09-01")

        payload = move_reads.move_ins_list(as_of=TODAY)
        assert payload["total"] == 1
        row = _row_for(payload, booked["account_no"])
        assert row["state"] == move_reads.MOVE_IN_STATE_SCHEDULED
        assert row["move_in_date"] == "2026-09-01"

        # ── the CLOSING edge — the account opens and the move-in is over ──
        customers_services.activate_account(marcus, booked["id"])
        after = move_reads.move_ins_list(as_of=TODAY)
        assert after["total"] == 0
        # …and the completed row is not silently kept under another state.
        assert after["rows"] == []


def test_the_three_move_in_states_are_derived_from_the_start_date(brazos, marcus):
    """§1's mapping, and `waiting` is a MEASURED blockage rather than a label.

    `services._make_occupying` raises `BIZ_COMPLETENESS` on BR-CUS-022 for an
    account with no `opened_at`, because *"an occupying account without one
    could never be billed"* — so a row with no start date genuinely cannot move
    until a human supplies one, which is what §5.5.2's `Waiting` means.
    """
    with tenant_ctx(brazos):
        waiting = _booked_in(marcus, brazos, label="500 Main · 210", name="Osei, Grace")
        scheduled = _booked_in(
            marcus, brazos, label="88 Pine Vista", name="Kwan, Michael", opened_at="2026-09-01"
        )
        due = _booked_in(
            marcus, brazos, label="12 Harbour View", name="Reyes, Antonio", opened_at="2026-08-20"
        )

        payload = move_reads.move_ins_list(as_of=TODAY)
        states = {row["account_no"]: row["state"] for row in payload["rows"]}
        assert states[waiting["account_no"]] == move_reads.MOVE_IN_STATE_WAITING
        assert states[scheduled["account_no"]] == move_reads.MOVE_IN_STATE_SCHEDULED
        assert states[due["account_no"]] == move_reads.MOVE_IN_STATE_DUE

        # The absence NAMES the rule that makes it a blockage, not a blank cell.
        blocked = _row_for(payload, waiting["account_no"])
        assert blocked["move_in_date"] is None
        assert blocked["move_in_date_absence"]["br_ref"] == "BR-CUS-022"

        # ⚠ **THIS ASSERTED THAT THE BLOCKED ROW SORTS FIRST AND HAS BEEN RED
        # SINCE 2026-09-13**, when `2db4d169` landed `BR-CUS-1046`'s default:
        # *"All eight open newest-first"*. §5.5.2's *"sorted by move-in date,
        # soonest first"* is SUPERSEDED as the DEFAULT and survives as a
        # clickable column, so the row with no date is one click away rather
        # than at the top. The case is rewritten rather than re-pointed, because
        # its old sentence stated a rule this product no longer has.
        #
        # What the ruling actually guarantees, and what is asserted instead:
        # the newest row opens the list, and the `move_in_date` ordering is
        # still reachable — with the dateless row first, which is the half of
        # §5.5.2 that did not move.
        assert payload["rows"][0]["account_no"] == due["account_no"]
        soonest = move_reads.move_ins_list(as_of=TODAY, sort="move_in_date", dir="asc")
        assert soonest["rows"][0]["account_no"] == waiting["account_no"]

        # `due` is MINTED and declares itself so — B18 draws no such segment.
        due_segment = next(
            s for s in payload["states"] if s["code"] == move_reads.MOVE_IN_STATE_DUE
        )
        assert due_segment["drawn"] is False
        assert due_segment["supported"] is True


def test_the_deposit_cell_never_says_waived(brazos, marcus):
    """**CASE 2 OF THE FOUR.** B18 §5.5.2 draws DEPOSIT as *"a sentence, not a
    number alone"* — `waived` · `on first bill` · `carried $153.50` ·
    `collected $150.00` · `—`.

    Which of those applies is a DISPOSITION and **no column records one.**
    `accounts.deposit_on_file` holds an amount and is a REFUSED field on both
    doors that edit an account, because BR-CUS-023 makes it a lookup. So a
    deposit nobody recorded and a deposit deliberately waived hold the same
    value, and printing `waived` for a zero states a decision nobody made.

    Both money shapes per CLAUDE.md hard rule 2 — stored at 4 dp, DISPLAY at 2,
    rounded once, server-side.
    """
    with tenant_ctx(brazos):
        none_held = _booked_in(marcus, brazos, label="500 Main · 210", name="Osei, Grace")
        holding = _booked_in(
            marcus, brazos, label="88 Pine Vista", name="Kwan, Michael", opened_at="2026-09-01"
        )
        _with_deposit(holding["id"], DEPOSIT_HELD)

        payload = move_reads.move_ins_list(as_of=TODAY)
        empty = _row_for(payload, none_held["account_no"])["deposit"]
        full = _row_for(payload, holding["account_no"])["deposit"]

        # ⛔ THE WRONG ANSWER, on both rows.
        assert empty["sentence"] is None
        assert full["sentence"] is None
        # ⚠ `_data_only` strips the absence's own PROSE — that sentence quotes
        # all five drawn outcomes in order to say none can be printed, so a
        # naive `str(cell)` search finds `waived` inside the refusal itself.
        for cell in (empty, full):
            assert "waived" not in str(_data_only(cell))
            assert "on first bill" not in str(_data_only(cell))
            assert cell["unavailable"][0]["code"] == "deposit_disposition_has_no_column"

        # A zero is a zero and says so through `recorded`, which is the fact a
        # screen branches on instead of guessing from the number.
        assert empty["recorded"] is False
        assert empty["amount"]["display"] == "0.00"
        # ❄️ WE-7's principal, 4 dp stored / 2 dp displayed, rounded ONCE here.
        assert full["recorded"] is True
        assert full["amount"] == {"stored": "150.0000", "display": "150.00"}


def test_step_and_reads_state_their_absence_and_never_default(brazos, marcus):
    """§4 row 1 (STEP) — and READS' absence, which CHANGED on 2026-08-26.

    The DENOMINATOR is served and the numerator is not, deliberately: a screen
    that knows the bar has five segments can draw it empty and say why, which is
    a truer thing than an invented `1 of 5`.

    ⚠ **AMENDED 2026-08-26 (CR-038 W9 task 2), the W2 reads-lane precedent —
    a pinned null posture amended WITH the reason.** This test pinned READS to
    `unit_reads_not_readable_from_customers` because customers published no
    metering read seam. `seams.reads_for_unit` exists now and the cell DERIVES
    `taken`/`due` — the wired path is proved in tests/test_w9_reads_seam.py —
    so on THIS fixture, whose `_unit` deliberately holds no meter, the absence
    narrows to `unit_has_no_meters`: the seam resolved, answered, and a verdict
    over zero meters is refused rather than defaulted. Still `state: None`,
    still never a default — the claim this test exists for.
    """
    with tenant_ctx(brazos):
        booked = _booked_in(marcus, brazos, opened_at="2026-09-01")
        row = _row_for(move_reads.move_ins_list(as_of=TODAY), booked["account_no"])

        # ⚠ **SIX, CORRECTED 2026-09-19 (`DEF-CUS-5886`).** This read `5` and the
        # move-in wizard has declared SIX steps since 2026-09-13; the Accounts
        # blueprint draws `6 of 6`. The parity test that compares the two sides
        # had been RED for six days and every lane ran past it.
        # ⚠ **FOUR SINCE 2026-10-05 (`CR-171-BRC10` P1.02, `DEF-CUS-9703`)** —
        # the redesign's Unit · Customer · Billing · Review, declared on the
        # server as `MOVE_IN_STEP_IDS`.
        assert row["step"]["of"] == move_reads.MOVE_IN_STEP_COUNT == 4
        assert row["step"]["reached"] is None
        assert row["step"]["unavailable"]["code"] == "move_step_has_no_store"
        # …and the reason names the thing that is missing, not "coming soon".
        #
        # ⚠⚠ **THIS ASSERTION USED TO PIN THE WORDS `no wizard store`, AND THAT
        # IS WHY THE FALSE SENTENCE SURVIVED (`DEF-CUS-5888`).** `wizard_parks`
        # has carried a `step` column since `CR-035`, and the Move-ins tab's own
        # parked panel renders `Step 1 of 6` off that row — directly above the
        # table whose cell said no such store existed. A test that asserts a
        # REASON word-for-word turns that reason into something nobody may
        # correct without going red, which is the opposite of what it was for.
        #
        # **The ABSENCE is what this test is about, and it still holds for THIS
        # ROW**: a draft account records no step and `reached` is None on it.
        #
        # ⚠⚠ **AMENDED 2026-09-20 (`DEF-CUS-5994`) — AND THE PIN HAD TO MOVE
        # AGAIN, WHICH IS THE POINT.** It pinned *"not readable HERE"* or
        # *"not a row of this list"*, and the PO removed the panel that second
        # clause pointed at: *"remove it - it is anyway in the list so we dont
        # need it sepretely - if it is not in list add it"*. A parked draft IS
        # a row of this list now, with a real step, so the old sentence was
        # false and the pin on it went red — correctly.
        #
        # **This is the SECOND time this assertion has been re-pointed and the
        # lesson is the same both times: pinning PROSE pins whatever the prose
        # happened to say.** What is durable is the CLAIM about this row —
        # `reached` is None and the row says why — and the two negatives below
        # are the two sentences that have been falsified by a ruling, kept as
        # tripwires so neither can come back.
        detail = row["step"]["unavailable"]["detail"]
        assert "no step to put in it" in detail
        assert "no wizard store" not in detail
        assert "panel above this table" not in detail

        assert row["reads"]["state"] is None
        assert row["reads"]["unavailable"]["code"] == "unit_has_no_meters"
        # The seam answered — this is a RESOLVED configuration fact, not the
        # old cannot-ask absence, and the reason says which meters exist: none.
        assert row["reads"]["meters_total"] == 0

        # B18's `Done` rows and the move-ins this list cannot show are named at
        # LIST level: a cell cannot state the absence of a row that is not there.
        #
        # ⚠ **`parked_draft_has_no_account_row` LEFT THIS SET ON 2026-09-16**
        # (PO ruling, *"it should do B"*, `BR-CUS-1077`). This list CAN show a
        # `— draft` row now — it is the pending job an approval raises — so a
        # sentence saying it cannot would be worse than none. What replaced it
        # is the half that is still true (an UNAPPROVED move-in is a request, on
        # the Requests tab) plus the new list-level fact: what leaves a pending
        # job stranded on this tab.
        #
        # ⚠ **TWO MORE LEFT ON 2026-10-05 (`CR-171-BRC10` §2 S3/S4).** A request
        # that suggests a move-in IS a row of this list now, and so is a
        # finished move-in, so neither sentence is true; the stranded-job one is.
        assert set(_codes(move_reads.move_ins_list(as_of=TODAY)["unavailable"])) == {
            "pending_job_closes_on_the_recorded_move",
        }


def test_the_request_leg_resolves_through_the_br_cus_080_link(brazos, marcus):
    """§5.5.2's fourth search leg — *"Customer, unit, address, account #, or
    request #…"* — and the one `transfer_reads` had to give up (BR-CUS-099).

    It works here for a reason worth asserting rather than asserting around:
    BR-CUS-080's `outcome_ref` is TEXT, and for a move-in the child IS the
    account, so `link_child` writes the ACCOUNT NUMBER. `core/sample_fixture.py`
    seeds `SR-26-0045 → "A-12048"`.
    """
    with tenant_ctx(brazos):
        booked = _booked_in(marcus, brazos, opened_at="2026-09-01")
        request = _linked_request(marcus, brazos, booked["account_no"])

        row = _row_for(move_reads.move_ins_list(as_of=TODAY), booked["account_no"])
        assert row["request"]["request_no"] == request.request_no
        assert row["request_absence"] is None

        # The leg itself, through the search box.
        by_request = move_reads.move_ins_list(q=request.request_no, as_of=TODAY)
        assert by_request["total"] == 1
        assert by_request["rows"][0]["account_no"] == booked["account_no"]

        # …and the limit that the TEXT column buys is STATED, not hidden.
        # ⚠ **A SECOND LIMIT JOINED IT ON 2026-09-16 (`BR-CUS-1077`):** a
        # pending job has no account number, so the `account #` leg cannot find
        # one — said, rather than left to a clerk who types one and gets nothing.
        # ⚠ **A THIRD JOINED THEM ON 2026-09-20 (`DEF-CUS-5994`):** a parked
        # DRAFT has no account number either — it joins to nothing at all
        # (BR-SHL-048 (a)) — so the same leg cannot reach one, and the same
        # posture applies: say it rather than leave a clerk typing an account
        # number and getting silence.
        assert _codes(by_request["search"]["unavailable"]) == [
            "request_leg_matches_only_linked_refs",
            "pending_job_has_no_account_number_to_search",
            "parked_move_in_has_no_account_number_to_search",
        ]


def test_the_move_in_search_covers_customer_unit_and_account(brazos, marcus):
    """BR-CUS-053's legs, each proved separately so a passing OR-group cannot
    hide a leg that never matches."""
    with tenant_ctx(brazos):
        booked = _booked_in(
            marcus, brazos, label="88 Pine Vista", name="Kwan, Michael", opened_at="2026-09-01"
        )
        customers_services.link_customer(account_id=booked["id"], display_name="Kwan, Michael")
        _booked_in(marcus, brazos, label="12 Harbour View", name="Reyes, Antonio")

        assert move_reads.move_ins_list(q="Kwan", as_of=TODAY)["total"] == 1
        assert move_reads.move_ins_list(q="Pine Vista", as_of=TODAY)["total"] == 1
        assert move_reads.move_ins_list(q=booked["account_no"], as_of=TODAY)["total"] == 1
        assert move_reads.move_ins_list(q="Nothing At All", as_of=TODAY)["total"] == 0
        # IS-3 — a one-character term does not return the whole tenant.
        assert move_reads.move_ins_list(q="K", as_of=TODAY)["total"] == 2


def test_the_move_in_tiles_count_what_they_can_and_state_what_they_cannot(brazos, marcus):
    """B18 §5.5.1's five tiles, worked.

    ⚠ **`DEPOSITS TO CARRY OVER` IS `null` AND NEVER `0`.** It counts an
    ELECTION — *"money moving from a closed account"* — and `accounts` has no
    column for one. `transfers.deposit_carry_elected` is exactly that column on
    the transfer table, and the transfer lane's own reason for storing it was
    that an election makes the tile *"countable without inventing a figure to
    count"*.

    ⚠ **`OLDEST` IS `null` WHEN THERE ARE NONE, NEVER `{days: 0}`** — *"0 days"
    is a different claim from "there is none"*.
    """
    with tenant_ctx(brazos):
        empty = move_reads.move_in_kpis(as_of=TODAY)
        assert empty["open"] == 0
        assert empty["oldest"] is None

        this_week = _booked_in(
            marcus, brazos, label="88 Pine Vista", name="Kwan, Michael", opened_at="2026-08-28"
        )
        later = _booked_in(
            marcus, brazos, label="12 Harbour View", name="Reyes, Antonio", opened_at="2026-09-30"
        )
        _with_deposit(this_week["id"], DEPOSIT_HELD)

        kpis = move_reads.move_in_kpis(as_of=TODAY)
        assert kpis["open"] == 2
        # *"within 7 days of today"* — Aug 28 counts, Sep 30 does not.
        assert kpis["starting_this_week"] == 1
        # ⚠ AMENDED 2026-08-26 (the W9-seam lane, in passing — NOT a reads
        # change): `assert days >= 0` was WALL-CLOCK-COUPLED. `booked_in_on`
        # is `created_at` (auto_now_add — the real clock) while `as_of` is
        # pinned at 2026-08-25, so from 2026-08-26 the served age went
        # negative and this suite failed on any tree, wired or not —
        # BR-TEN-043's own hazard, reproduced in a fixture. Pinned to the
        # DERIVATION the module states (`age = as_of − booked_in_on`) so the
        # case tests the math and not the day it is run. ⚠ A defect row for
        # the escape is OWED (this lane may not edit 12-governance/).
        oldest = kpis["oldest"]
        assert oldest["days"] == (TODAY - date.fromisoformat(oldest["booked_in_on"])).days
        assert oldest["account_no"] in {this_week["account_no"], later["account_no"]}
        # ⛔ NOT ZERO. A deposit HELD is not a deposit ELECTED to carry.
        assert kpis["deposits_to_carry_over"] is None
        assert (
            kpis["deposits_to_carry_over_unavailable"]["code"]
            == "deposit_carry_election_has_no_column"
        )
        # The `WAITING ON DOCUMENTS` tile counts a WIDER set and says so.
        assert kpis["waiting_on"]["count"] == 0
        assert kpis["waiting_on"]["drawn_as"] == "documents"
        assert _codes(kpis["waiting_on"]["unavailable"]) == ["waiting_on_has_no_vocabulary"]
        # No rule states which clock a KPI window reads; the basis is DATA.
        assert kpis["period_basis"] == "tenant_today"


# ════════════════════════════════════════════════════════════════════════════
# 2 · WHAT A MOVE-OUT IS IN THE DATA (§2 of `move_reads`)
# ════════════════════════════════════════════════════════════════════════════
def test_a_move_out_is_a_closed_account_and_a_live_one_is_not_on_the_tab(brazos, marcus):
    """`services.move_out`: *"`closed_at` = the move-out date, status → the
    terminal status."* That commit IS the move-out, and there is no second
    column. A live account has not moved out and is not listed."""
    with tenant_ctx(brazos):
        _account(marcus, brazos, label="1408 Elm St · A", name="Sandoval, Rita")
        gone = _moved_out(marcus, brazos, on="2026-08-20")

        payload = move_reads.move_outs_list(as_of=TODAY)
        assert payload["total"] == 1
        row = _row_for(payload, gone.account_no)
        assert row["move_out_date"] == "2026-08-20"
        assert row["state"] == move_reads.MOVE_OUT_STATE_CLOSED


def test_only_a_move_out_nobody_started_has_no_store(brazos, marcus):
    """⚠ **AMENDED 2026-09-19 BY PO RULING, AND THE OLD ASSERTION WAS THE BUG.**

    This case was `test_a_move_out_in_flight_has_no_store` and it pinned THREE
    refusals: `Scheduled`, `In progress` and `Waiting` all served
    `supported: False` over the sentence *"a move-out that has not committed yet
    is not recorded anywhere"*. **That sentence had been false since `CR-035`**
    — `wizard_parks` carries `flow='move_out'` with a real `step` — and this
    test is why nobody noticed: it asserted the refusal as a guarantee, so the
    product and its guard agreed with each other and neither agreed with the
    schema. The PO ruled on 2026-09-19, verbatim **`yes`**, asked whether the
    Move-outs list should show move-outs that have not finished yet.

    The file header says *"if a later lane makes this green it must be because a
    column was added — not because the refusal was inconvenient"*. Neither
    happened: the column was there all along and the LIST could not see it. The
    negative is kept for the one state that is genuinely unholdable.

    ⛔ **`scheduled` STAYS REFUSED AND MUST.** It is a move-out somebody intends
    and nobody has started — no wizard, no draft, nothing written — and
    `accounts` has no `scheduled_move_out_on` to park a date on.
    """
    with tenant_ctx(brazos):
        payload = move_reads.move_outs_list(as_of=TODAY)
        by_code = {segment["code"]: segment for segment in payload["states"]}

        # The one that is still nothing at all.
        assert by_code["scheduled"]["drawn"] is True
        assert by_code["scheduled"]["supported"] is False
        reason = by_code["scheduled"]["unavailable"]
        assert reason["code"] == "move_out_before_close_has_no_store"
        assert "accounts.scheduled_move_out_on" in reason["wanted_columns"]
        # …and the narrowed sentence no longer claims the GENERAL case. The old
        # one opened *"A move-out that has not committed yet is not recorded
        # anywhere"*; the phrase `is not recorded anywhere` survives on its own
        # and is still true of the narrowed subject, so this pins the CLAIM —
        # which of the two subjects the sentence is about — rather than a word.
        assert "has not committed yet" not in reason["detail"]
        assert "somebody intends but has not started" in reason["detail"]
        assert "parked IS listed here" in reason["detail"]

        # The two the ruling opened — real rows, no reason attached.
        for code in (move_reads.MOVE_OUT_STATE_IN_PROGRESS, move_reads.MOVE_OUT_STATE_WAITING):
            assert by_code[code]["drawn"] is True
            assert by_code[code]["supported"] is True
            assert by_code[code]["unavailable"] is None

        # The finished one, and it does not borrow B18's `Done`: that word means
        # *the wizard finished* and this means *the account closed*. p117 draws
        # `Completed`, which is the label this segment now carries.
        assert by_code[move_reads.MOVE_OUT_STATE_CLOSED]["supported"] is True
        assert by_code[move_reads.MOVE_OUT_STATE_CLOSED]["drawn"] is False
        assert by_code[move_reads.MOVE_OUT_STATE_CLOSED]["label"] == "Completed"

        # …and the window has no closing edge either, for its own reason.
        assert set(_codes(payload["unavailable"])) == {
            "move_out_before_close_has_no_store",
            "move_out_window_has_no_closing_edge",
        }


def test_an_unfinished_move_out_is_a_row_with_a_real_step(brazos, marcus):
    """**PO ruling 2026-09-19, verbatim `yes`** — the Move-outs list shows the
    move-outs that have not finished yet.

    This is the Accounts blueprint p117's drawn second row, `MVO-26-0087 ·
    2 of 6 · In progress`, with REAL data behind it rather than an invented
    shape: the step is the draft's own column, the account is the one the clerk
    picked, and the state is derived from whether they recorded what they are
    waiting for.
    """
    with tenant_ctx(brazos):
        gone = _moved_out(marcus, brazos, on="2026-08-20")
        _parked_move_out(marcus, brazos, step=2, waiting_on="the customer")

        payload = move_reads.move_outs_list(as_of=TODAY)
        assert payload["total"] == 2

        kinds = {row["row_kind"] for row in payload["rows"]}
        assert kinds == {move_reads.ROW_KIND_ACCOUNT, move_reads.ROW_KIND_PARKED_MOVE_OUT}

        park = next(
            row
            for row in payload["rows"]
            if row["row_kind"] == move_reads.ROW_KIND_PARKED_MOVE_OUT
        )
        # THE STEP — a real numerator over BR-SHL-046's six, and no absence.
        assert park["step"] == {"reached": 2, "of": 6, "unavailable": None}
        # THE STATE — `waiting_on` is recorded, so it is `waiting`; a draft left
        # by `Save & exit` would be `in_progress`. ONE column decides.
        assert park["state"] == move_reads.MOVE_OUT_STATE_WAITING
        assert park["waiting_on"] == "the customer"
        # THE ACCOUNT — the fact that makes this a ROW rather than a panel. The
        # customer and the unit come off it the same way a finished row's do.
        assert park["account_no"] is not None
        assert park["account_absence"] is None
        assert park["customer"] is not None
        assert park["unit"] is not None
        # THE DATE the clerk typed. It commits nothing; the STATE says so.
        assert park["move_out_date"] == "2026-08-28"
        assert park["move_out_date_absence"] is None
        # …and the finished row is untouched beside it.
        closed = _row_for(payload, gone.account_no)
        assert closed["state"] == move_reads.MOVE_OUT_STATE_CLOSED
        assert closed["row_kind"] == move_reads.ROW_KIND_ACCOUNT


def test_a_draft_left_without_a_reason_is_in_progress_not_waiting(brazos, marcus):
    """`Save & exit` writes a row with an EMPTY `waiting_on` (`CR-122-BRC06`,
    PO 2026-09-19) and `Park` records what is awaited. **EMPTY MEANS *A DRAFT*,
    NOT *A PARK WITH NO REASON*** — `WizardPark.waiting_on`'s own words — and
    this list has to read the same column the panel reads, or one surface calls
    a row `Waiting` while the other calls it a draft.
    """
    with tenant_ctx(brazos):
        _parked_move_out(marcus, brazos, step=4, waiting_on="")

        rows = move_reads.move_outs_list(as_of=TODAY)["rows"]
        park = next(r for r in rows if r["row_kind"] == move_reads.ROW_KIND_PARKED_MOVE_OUT)
        assert park["state"] == move_reads.MOVE_OUT_STATE_IN_PROGRESS
        assert park["waiting_on"] is None
        assert park["step"]["reached"] == 4


def test_the_closed_row_keeps_its_step_absence_and_is_never_derived(brazos, marcus):
    """⛔ **THE TWO ANSWERS COEXIST, AND THIS IS THE HALF THAT MUST NOT MOVE.**

    A parked move-out prints `2 of 6` because a step is stored. A CLOSED one
    prints an absence, because **four code paths write `accounts.closed_at` and
    only one is the wizard** — `services.move_out`, against the disconnect
    close-out, the account import and the import rollback. `6 of 6` on the other
    three would claim a clerk walked six steps they never saw.

    **If a later lane makes this green it must be because the close started
    recording a step — never because the neighbouring row has one.**
    """
    with tenant_ctx(brazos):
        gone = _moved_out(marcus, brazos)
        _parked_move_out(marcus, brazos, step=5)

        payload = move_reads.move_outs_list(as_of=TODAY)
        closed = _row_for(payload, gone.account_no)
        assert closed["step"]["reached"] is None
        assert closed["step"]["of"] == 6
        assert closed["step"]["unavailable"]["code"] == "closed_move_out_has_no_step"
        # …while the draft beside it, on the same page, carries a real one.
        park = next(
            r for r in payload["rows"] if r["row_kind"] == move_reads.ROW_KIND_PARKED_MOVE_OUT
        )
        assert park["step"]["reached"] == 5


def test_an_unfinished_row_states_every_absence_and_invents_nothing(brazos, marcus):
    """Where a value genuinely does not exist yet, the row SAYS SO — it never
    reaches for a placeholder, and it never derives a figure nobody computed.

    Two cells, two different reasons, and neither is a missing column:

      · **REFERENCE.** Only a move-IN draft is numbered while it is in hand
        (`CR-122-BRC06` — *"minting numbers for four other flows that nothing
        displays would be a series burning through its counter"*). There IS a
        screen now, which is what `OQ-CUS-12489` asks; nothing is minted here.
      · **SETTLEMENT.** Nothing is settled until the account closes, and there
        is not even a gap to name — unlike a closed row, where the engine's
        *any gap → no landing* is what withholds the verdict.
    """
    with tenant_ctx(brazos):
        _parked_move_out(marcus, brazos)

        rows = move_reads.move_outs_list(as_of=TODAY)["rows"]
        park = next(r for r in rows if r["row_kind"] == move_reads.ROW_KIND_PARKED_MOVE_OUT)

        assert park["move_no"] is None
        assert park["move_no_unavailable"]["code"] == "parked_move_out_has_no_reference"

        settlement = park["settlement"]
        assert settlement["landing"] is None
        assert settlement["complete"] is False
        # ⛔ NEVER `0.00` on either term — DEF-127's rule, and on this column a
        # zero would read as *this customer is square and owed nothing back*.
        assert settlement["deposit_held"]["display"] is None
        assert settlement["outstanding"]["display"] is None
        assert _codes(settlement["unavailable"]) == ["parked_move_out_has_no_settlement"]

        # And the narrower search legs are declared, never left to be discovered
        # by a clerk getting no hit (BR-SHL-010 / BR-CUS-099).
        payload = move_reads.move_outs_list(as_of=TODAY)
        assert "parked_move_out_has_no_account_number_to_search" in _codes(
            payload["search"]["unavailable"]
        )


def test_a_draft_with_no_date_says_so_rather_than_printing_a_dash(brazos, marcus):
    """The move-out date is asked for inside the wizard, so a draft parked
    before that step has none. A blank cell and an absent fact are
    indistinguishable once drawn (`DEF-127`), so the reason rides with it — and
    a draft with no date is not *leaving this week*, because it is not leaving
    on any stated day at all.
    """
    with tenant_ctx(brazos):
        _parked_move_out(marcus, brazos, step=1, moved_out_on="")

        rows = move_reads.move_outs_list(as_of=TODAY)["rows"]
        park = next(r for r in rows if r["row_kind"] == move_reads.ROW_KIND_PARKED_MOVE_OUT)
        assert park["move_out_date"] is None
        assert park["move_out_date_absence"]["code"] == "parked_move_out_date_not_chosen_yet"
        assert park["leaving_this_week"] is False


def test_the_closed_window_filter_excludes_every_unfinished_row(brazos, marcus):
    """`f.closed` is a window on `accounts.closed_at`, and a draft has closed
    nothing. A clerk asking for *closed in the last 7 days* must get none of
    them — not all of them, which is what an unguarded second source does.
    """
    with tenant_ctx(brazos):
        gone = _moved_out(marcus, brazos, on=TODAY.isoformat())
        _parked_move_out(marcus, brazos)

        unfiltered = move_reads.move_outs_list(as_of=TODAY)
        assert unfiltered["total"] == 2

        filtered = move_reads.move_outs_list(as_of=TODAY, filters={"closed": "last7"})
        assert filtered["total"] == 1
        assert {r["row_kind"] for r in filtered["rows"]} == {move_reads.ROW_KIND_ACCOUNT}
        assert _row_for(filtered, gone.account_no) is not None


def test_the_page_is_one_order_over_both_kinds_and_never_two_lists(brazos, marcus):
    """`NFR-3` — the page is a `LIMIT`/`OFFSET` over ONE order across both
    sources (`_move_out_page_keys`), never two materialised lists spliced in
    Python. `total` counts both kinds, and a row appears on exactly one page.

    The default order is `created`, which is the one column BOTH sides hold, so
    the list a clerk opens is ordered properly over the two kinds rather than
    blocking the drafts at one end.
    """
    with tenant_ctx(brazos):
        _moved_out(marcus, brazos, label="17 Brambling Ct", name="Fitzgerald, Sean")
        _moved_out(marcus, brazos, label="2 Kestrel Way", name="Okafor, Dayo", on="2026-08-21")
        _parked_move_out(marcus, brazos, label="9 Larkspur", name="Ncube, Thandiwe")

        first = move_reads.move_outs_list(as_of=TODAY, page=1, per=2)
        second = move_reads.move_outs_list(as_of=TODAY, page=2, per=2)
        assert first["total"] == 3 and second["total"] == 3
        assert first["pages"] == 2
        assert len(first["rows"]) == 2 and len(second["rows"]) == 1

        seen = [r["account_no"] or r["park_id"] for r in first["rows"] + second["rows"]]
        assert len(seen) == len(set(seen)), "a row appeared on two pages"


def test_the_move_out_step_denominator_is_the_wizards_own_and_never_a_drawn_one(brazos, marcus):
    """**The list's denominator is the WIZARD's count, whatever that count is.**

    ⚠ **THIS CASE WAS NAMED `…_is_six_and_never_four` UNTIL 2026-09-24, AND THE
    RENAME IS THE POINT.** It was written to close `DEF-648`, where B18
    §5.6.2's `STEP (of 4)` column stood over a six-step wizard — so it pinned
    SIX and forbade FOUR by name. The PO has since ruled the wizard's shape
    **four** (*"i okay with these steps"*), merging old steps 3+4 and 5+6, and
    a case whose NAME forbids the ruled number is a check that has to be
    deleted to obey a ruling.

    **So it asserts the PROPERTY instead of the number**: the list's `of` is
    whatever `MOVE_OUT_STEP_COUNT` says, and that constant is held against the
    wizard's declared list by `test_def_648_step_count_parity.py`, which also
    pins the ruled figure. One place pins the number; this one pins that the
    list reads it. Pinning it in two places is what made this case a chore the
    day the number moved.

    ⚠ **THE OLD FOUR AND THE NEW FOUR ARE NOT THE SAME FOUR.** B18's was a
    DRAWN count that never matched the wizard; this one IS the wizard. A lane
    reading only *"it went back to 4"* will reopen a closed defect.
    """
    with tenant_ctx(brazos):
        gone = _moved_out(marcus, brazos)
        row = _row_for(move_reads.move_outs_list(as_of=TODAY), gone.account_no)
        assert row["step"]["of"] == move_reads.MOVE_OUT_STEP_COUNT
        assert row["step"]["reached"] is None
        # ⚠ **ITS OWN CODE SINCE 2026-09-19.** A closed move-out and a draft
        # move-in have no step for two DIFFERENT reasons, and one sentence
        # stretched over both was what let the move-outs half go stale.
        assert row["step"]["unavailable"]["code"] == "closed_move_out_has_no_step"


def test_no_settlement_landing_is_ever_stated_on_the_list(brazos, marcus, monkeypatch):
    """⛔ **ASSERTED AS A NEGATIVE, ON PURPOSE.** B18 §5.6.2 draws SETTLEMENT as
    `refunded $88.40` · `refund $11.20` · `settles exactly` · `SHORT $175.20`,
    and every one is a landing from `move_out_settlement.MONEY_LANDINGS`.

    `MoveOutSettlement.landing`, verbatim: *"any gap → **no landing**. Not a
    sixth outcome: a missing deposit interest understates `applied`, biasing the
    answer toward `short`; a missing final bill understates `outstanding`,
    biasing it toward `refund_due`. **One of those two directions posts a
    cheque.**"*

    **Both gaps are open on every row of this tab** — billing publishes no
    per-account final bill and BR-CUS-057's accrual is unbuilt — so the verdict
    is the engine's own `None` and not a shortcut taken to keep a list cheap.
    """
    with tenant_ctx(brazos):
        _ledger_says(monkeypatch, LEDGER_OWES)
        gone = _moved_out(marcus, brazos)
        _with_deposit(gone.id, DEPOSIT_HELD)

        row = _row_for(move_reads.move_outs_list(as_of=TODAY), gone.account_no)
        cell = row["settlement"]
        assert cell["landing"] is None
        assert cell["complete"] is False
        assert cell["sentence"] is None
        # The engine's own vocabulary is published so a screen cannot invent one.
        assert cell["landings"] == list(move_out_settlement.MONEY_LANDINGS)
        # …and the two gaps are the engine's own sentences, carried verbatim.
        codes = _codes(cell["unavailable"])
        assert move_out_settlement.GAP_FINAL_BILL in codes
        assert move_out_settlement.GAP_DEPOSIT_INTEREST in codes
        assert "settlement_terms_not_read_on_a_list" in codes
        # ⛔ NO COMPOSED TOTAL. A sum of the terms this list read is a figure a
        # clerk would act on and nobody derived.
        assert "what_is_applied" not in cell
        assert "verdict" not in cell


def test_the_outstanding_figure_is_the_ledgers_and_never_the_cached_balance(
    brazos, marcus, monkeypatch
):
    """**CASE 3 OF THE FOUR — DEF-127, exactly.**

    `accounts.balance` is a CACHE (BR-CUS-015, and B2's own column comment says
    the ledger is the source of truth) and **nothing in this product has ever
    written it**. Customers served it anyway, so on 2026-08-15 a browser found
    `E2E-10001` holding an ISSUED, UNPAID **108.88** while S17 rendered the row
    as **$0.00**.

    The cache is poisoned here with a DIFFERENT figure from the ledger's, so the
    test can tell which column was read — seeding both with one number could not.
    """
    with tenant_ctx(brazos):
        _ledger_says(monkeypatch, LEDGER_OWES)
        gone = _moved_out(marcus, brazos)
        _cache_says(gone.id, CACHED_DECOY)

        cell = _row_for(move_reads.move_outs_list(as_of=TODAY), gone.account_no)["settlement"]
        assert cell["outstanding"] == {"stored": "108.8800", "display": "108.88"}
        assert cell["outstanding_source"] == "ledger"
        # ⛔ THE CACHE, IN BOTH ITS SHAPES.
        assert "999.99" not in str(cell)


def test_an_unreadable_ledger_is_an_absence_and_never_a_zero(brazos, marcus, monkeypatch):
    """DEF-127's other half, and the one that is easy to get wrong.

    `seams.ArPositions.amount_for` returns **None** — not `Decimal("0")` —
    whenever the books could not be asked, *"and every surface built on it
    renders an absence with a reason instead of a figure a customer would act
    on."* On a move-out column, `$0.00` reads as *this customer is square and
    owed nothing back*.
    """
    with tenant_ctx(brazos):
        _ledger_says(monkeypatch, None, available=False)
        gone = _moved_out(marcus, brazos)
        _cache_says(gone.id, CACHED_DECOY)

        cell = _row_for(move_reads.move_outs_list(as_of=TODAY), gone.account_no)["settlement"]
        assert cell["outstanding"] == {"stored": None, "display": None}
        assert cell["outstanding_source"] is None
        # The seam's own refusal travels through rather than being swallowed.
        assert "ledger_publishes_no_per_account_ar_position" in _codes(cell["unavailable"])
        # ⛔ NEITHER WRONG ANSWER.
        assert "0.00" not in str(cell["outstanding"])
        assert "999.99" not in str(cell)


def test_the_three_undecidable_tiles_are_null_and_never_zero(brazos, marcus):
    """**CASE 4 OF THE FOUR.** B18 §5.6.1's five tiles.

    `SHORTFALLS TO DECIDE · 0` says every closing account is square. `REFUNDS
    TO PAY · 0` says nobody is owed their deposit back. Both read as good news
    to the one person paid to act on the bad kind, and neither is derivable:
    both need a LANDING, and a landing needs the final bill.

    ⚠ **AMENDED 2026-08-26 (CR-038 W9 task 2): THE THREE BECAME TWO** — the
    name keeps its history. `FINAL READS DUE` needed *"a read seam customers
    does not have"*; `seams.reads_for_unit` exists now and the tile is a REAL
    count (tests/test_w9_reads_seam.py proves the counting on read fixtures).
    On THIS fixture — whose units deliberately hold no meters — the served `0`
    is a DERIVED answer, and DEF-127's worry ("0 says every meter has been
    read") is answered with data rather than a null:
    `final_reads_due_meterless == 2` says both move-outs could not be measured
    AT ALL, which is a different sentence from "all read".

    ⚠ **`OPEN` DOES NOT MEAN WHAT §5.6.1 DRAWS IT MEANING**, so the tile carries
    `open_means` rather than letting five be read as five people still packing.
    """
    with tenant_ctx(brazos):
        _moved_out(marcus, brazos, on="2026-08-28")
        _moved_out(marcus, brazos, label="220 Sable Court", name="Delgado, Pilar", on="2026-09-30")

        kpis = move_reads.move_out_kpis(as_of=TODAY)
        assert kpis["open"] == 2
        assert kpis["open_means"] == "closed_and_not_yet_finally_billed"
        assert kpis["open_unavailable"]["code"] == "move_out_before_close_has_no_store"
        # *"within 7 days of today"* — Aug 28 counts, Sep 30 does not.
        assert kpis["leaving_this_week"] == 1
        # ✔ THE WIRED TILE: a derived count, its meaning named, its blind spot
        # counted beside it — never a null with a reason that is no longer true.
        assert kpis["final_reads_due"] == 0
        assert kpis["final_reads_due_unavailable"] is None
        assert kpis["final_reads_due_means"] == "closed_move_outs_with_a_meter_unread_since_close"
        assert kpis["final_reads_due_meterless"] == 2
        # ⛔ THE TWO. `is None`, not falsy: `0` is falsy and is the bug.
        assert kpis["shortfalls_to_decide"] is None
        assert kpis["refunds_to_pay"] is None
        assert kpis["shortfalls_to_decide_unavailable"]["code"] == move_out_settlement.GAP_FINAL_BILL
        assert kpis["refunds_to_pay_unavailable"]["code"] == move_out_settlement.GAP_FINAL_BILL


def test_the_move_out_search_finds_a_row_by_the_reference_it_prints_first(brazos, marcus):
    """`DEF-CUS-5896` — the REFERENCE leg, PO-approved 2026-09-19.

    The Accounts blueprint p117 draws this box as *"Search by reference,
    account, customer or unit"* and draws `REFERENCE` as the FIRST column. A
    clerk reads `MVO-26-0001` off the row, off a letter or off the phone and
    types it back in; until this leg landed the box answered **nothing**, on the
    one column of this table a person says out loud.

    ⚠ **RED PROOF (hard-won law 7), run in pytest before the leg existed:**
    `assert 0 == 1` on the first assertion below — *"the list serves
    MVO-26-0001 in its first column and its own search box cannot find it"*.
    Reproduced the same way on the seeded `brazosbend` database:
    `move_outs_list(q="MVO-26-0001")["total"]` was `0` while
    `move_outs_list(q="AC-2026-00042")["total"]` was `1` over the same row.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY**, and each is closed by an assertion
    here rather than by a comment:

      * **a leg that matches everything.** `_noise` is a SECOND move-out with
        its own reference; a predicate that ignored the term would return 2.
      * **a leg answered by another leg.** `MVO-` is in no account number, no
        customer name and no unit label in this fixture, so only the reference
        column can answer it — and the partial case pins that the match is on
        the move number and not on a coincidence.
      * **the WRONG KIND of record.** Every one of these accounts also carries a
        `move_in` record, so a leg that forgot `kind=move_out` would match a
        `MVI-…` term and put a row on screen whose printed reference is a
        different number from the one that was typed.
      * **a leg that reaches another tenant's records.** Covered by
        `test_the_move_out_reference_leg_is_tenant_scoped` below.
    """
    with tenant_ctx(brazos):
        gone = _moved_out(marcus, brazos, label="17 Brambling Ct", name="Fitzgerald, Sean")
        _noise = _moved_out(marcus, brazos, label="220 Sable Court", name="Delgado, Pilar")

        listed = _row_for(move_reads.move_outs_list(as_of=TODAY), gone.account_no)
        reference = listed["move_no"]
        assert reference is not None, (
            "this fixture must actually issue a move number, or the case below "
            "proves nothing. A tenant with no `move_out` series row serves "
            "`move_no: None` and `MOVE_NUMBER_UNAVAILABLE` beside it."
        )
        assert reference.startswith("MVO-")

        found = move_reads.move_outs_list(q=reference, as_of=TODAY)
        assert found["total"] == 1, (
            f"the list prints {reference} in its first column and its own search "
            "box cannot find it — DEF-CUS-5896."
        )
        assert found["rows"][0]["account_no"] == gone.account_no

        # A PARTIAL, the same `icontains` shape every other leg on this box has.
        # `MVO-26-000` is the prefix BOTH references share here, so it finds
        # BOTH — which is `icontains` doing its job and is also the proof that
        # the second row carries a reference of its own rather than none.
        assert move_reads.move_outs_list(q=reference[:-1], as_of=TODAY)["total"] == 2
        # …and the whole number NARROWS it back to one (asserted above), while a
        # number no record carries selects neither.
        assert move_reads.move_outs_list(as_of=TODAY)["total"] == 2
        assert move_reads.move_outs_list(q="MVO-99-9999", as_of=TODAY)["total"] == 0

        # ⛔ THE KIND, ASKED WHERE IT BITES. An account that moved in and later
        # moved out carries a record of BOTH kinds, so a leg that dropped
        # `kind` would put a move-OUT row on screen under a move-IN number the
        # row does not print. Asked of the helper rather than of the list,
        # because this fixture's accounts are created rather than moved in and
        # a list-level assertion would therefore pass over a dropped filter —
        # hard-won law 7's *looking at the wrong thing*. Drop `kind=` from
        # `account_ids_for_move_reference` and this line goes red.
        assert (
            move_reads.account_ids_for_move_reference(reference, kind=moves.KIND_MOVE_IN) == []
        )
        assert move_reads.account_ids_for_move_reference(
            reference, kind=moves.KIND_MOVE_OUT
        ) == [str(gone.id)]

        # BR-SHL-010 — the leg is DECLARED beside the rows, so the screen cannot
        # offer a box the server will not answer (and the reverse, which is the
        # half this defect was).
        payload = move_reads.move_outs_list(as_of=TODAY)
        assert "reference" in payload["search"]["legs"]
        assert "reference" in payload["search"]["hint"].lower()


def test_the_move_out_reference_leg_is_tenant_scoped(brazos, marcus, lonestar):
    """CLAUDE.md hard rule 1 — *"No cross-tenant queryset."*

    The new leg reads a SECOND table, `move_records`, and a reference is a
    number a stranger could guess at. It is filtered on `tenant_id` where it is
    BUILT — the same predicate `move_records_by_account` has always used —
    rather than left to the account window above it.

    ⚠ **THE ROW-LEVEL ASSERTION ALONE WOULD PASS ON THE BROKEN VERSION, WHICH
    IS WHY THE HELPER IS CALLED DIRECTLY HERE.** `move_outs_queryset` is already
    tenant-scoped on `accounts`, so an unscoped record lookup would hand it
    another tenant's account ids and the `id__in` would simply match nothing —
    `total == 0`, green, over a queryset that had read another utility's table.
    That is hard-won law 7's *looking at the wrong thing*, so the check is put
    at the lookup rather than at the list.

    RED PROOF: dropping `tenant_id=_tenant_id()` from
    `account_ids_for_move_reference` makes the first assertion below fail with a
    one-element list where `[]` is asserted.
    """
    with tenant_ctx(brazos):
        ours = _moved_out(marcus, brazos)
        our_ref = _row_for(move_reads.move_outs_list(as_of=TODAY), ours.account_no)["move_no"]
        assert our_ref and our_ref.startswith("MVO-")
        assert move_reads.move_outs_list(q=our_ref, as_of=TODAY)["total"] == 1
        # …and the helper answers under the tenant that owns the record, so the
        # `[]` below is scoping and not a leg that never matches.
        assert move_reads.account_ids_for_move_reference(
            our_ref, kind=moves.KIND_MOVE_OUT
        ) == [str(ours.id)]

    with tenant_ctx(lonestar):
        assert (
            move_reads.account_ids_for_move_reference(our_ref, kind=moves.KIND_MOVE_OUT) == []
        )
        answered = move_reads.move_outs_list(q=our_ref, as_of=TODAY)
        assert answered["total"] == 0
        assert answered["rows"] == []


def test_the_move_out_box_does_not_offer_a_search_it_cannot_answer(brazos, marcus):
    """B18 §5.6.2 offers `request #`. A move-out creates no child, so
    `link_child` has no reference to write and every move-out request in this
    tree carries `outcome_ref: None` — `SR-26-0046 · Thompson, R.` is the drawn
    one.

    A box that offered the leg and silently found nothing is BR-CUS-099's own
    complaint about the transfers box, in the other direction. So the leg is not
    offered, and the absence names the column it would take.
    """
    with tenant_ctx(brazos):
        payload = move_reads.move_outs_list(as_of=TODAY)
        assert "request #" not in payload["search"]["hint"]
        assert "request_no" not in payload["search"]["legs"]
        absence = payload["search"]["unavailable"][0]
        assert absence["code"] == "move_out_has_no_request_link"
        assert absence["wanted_columns"] == ("service_requests.outcome_ref = the closing account_no",)


# ════════════════════════════════════════════════════════════════════════════
# 3 · THE EXCLUSION CONTRACT (B18 §5.7.3) — the case that matters most
# ════════════════════════════════════════════════════════════════════════════
def test_a_committed_transfer_never_appears_as_a_move_out(brazos, marcus):
    """**CASE 1 OF THE FOUR, AND THE ONE §5.7.3 SAYS NOTHING ELSE WILL CATCH.**

    B18 §5.7.3, verbatim: *"A transfer appears only here. Its two halves are
    deliberately kept out of Move-ins and Move-outs — **the same job listed
    three times would be counted three times.**"*

    ⚠ **THIS IS NOT A FORMALITY ON THIS TAB.** `transfers.commit_transfer` runs
    its outgoing half *through* `services.move_out` — *"the signed BR-CUS-030
    path, not a copy of it"* — so a committed transfer sets a `closed_at` and a
    terminal status and is INDISTINGUISHABLE from a move-out by the window
    §2 defines. `exclude_transfer_halves` is the only thing keeping it off.

    The fixture therefore carries a real committed transfer AND a real move-out,
    so the test proves the filter subtracts the right one rather than emptying
    the list.
    """
    with tenant_ctx(brazos):
        left_by_transfer, done = _committed_transfer(marcus, brazos)
        genuinely_gone = _moved_out(marcus, brazos)

        # The transfer really did close its outgoing half — the precondition
        # that makes this test meaningful rather than vacuous.
        left_by_transfer.refresh_from_db()
        assert left_by_transfer.closed_at is not None
        assert left_by_transfer.status.behavior_class == customers_services.CLASS_TERMINAL

        payload = move_reads.move_outs_list(as_of=TODAY)
        listed = {row["account_no"] for row in payload["rows"]}
        assert genuinely_gone.account_no in listed
        # ⛔ THE JOB COUNTED TWICE.
        assert left_by_transfer.account_no not in listed
        assert payload["total"] == 1

        # …and the contract is CALLED, never re-derived: the set this list
        # subtracts is the same set `transfer_reads` publishes.
        published = set(payload["exclusion"]["half_account_ids"])
        assert published == transfers.transfer_half_account_ids()
        assert payload["exclusion"]["contract"] == list(transfers.EXCLUSION_CONTRACT)
        assert str(left_by_transfer.id) in published
        assert str(done["to_account_id"]) in published
        # No listed row is a transfer half — the property, not just the fixture.
        for row in payload["rows"]:
            assert row["account_id"] not in published


def test_a_transfers_incoming_half_never_appears_as_a_move_in(brazos, marcus):
    """The other half of §5.7.3, and it is REACHABLE rather than theoretical.

    `commit_transfer` opens the incoming account through
    `services.create_account` with `data.get("status") or from_account.status.code`
    — so a caller who passes `pending_activation` lands the new half in exactly
    the BR-CUS-018 draft class the move-in window selects. Without the exclusion
    the same job would be on the Transfers tab AND the Move-ins tab.
    """
    with tenant_ctx(brazos):
        name = "Haddad, Nour"
        account = _account(marcus, brazos, label="901 Hillside Ave", name=name)
        customers_services.link_customer(account_id=account["id"], display_name=name)
        target = _unit(marcus, brazos, label="26 Meadowbank Rise")
        started = transfers.start_transfer(marcus, {"from_account_id": str(account["id"])})
        transfers.set_target_unit(marcus, started["id"], {"to_unit_id": str(target["id"])})
        transfers.set_dates(
            marcus, started["id"], {"out_date": "2026-08-28", "in_date": "2026-09-03"}
        )
        transfers.elect_money(marcus, started["id"], {})
        done = transfers.commit_transfer(
            marcus, started["id"], {"status": "pending_activation"}
        )

        arriving = customers_models.Account.objects.get(id=done["to_account_id"])
        # The precondition: the incoming half really IS in the move-in window's
        # class. Without this the test would pass for the wrong reason.
        assert arriving.status.behavior_class == customers_services.CLASS_NON_BILLABLE

        # A genuine booked-in move-in, so the list is not merely empty.
        booked = _booked_in(marcus, brazos, opened_at="2026-09-01")

        payload = move_reads.move_ins_list(as_of=TODAY)
        listed = {row["account_no"] for row in payload["rows"]}
        assert booked["account_no"] in listed
        # ⛔ THE SAME JOB ON TWO TABS.
        assert arriving.account_no not in listed
        assert payload["total"] == 1

        published = set(payload["exclusion"]["half_account_ids"])
        assert published == transfers.transfer_half_account_ids()
        for row in payload["rows"]:
            assert row["account_id"] not in published


def test_an_open_transfer_is_excluded_too_not_only_a_committed_one(brazos, marcus):
    """`transfer_half_account_ids`' own docstring: *"a transfer at step 3 has
    ALREADY taken its outgoing account out of the Move-outs count — the callout
    says 'a transfer appears only here', not 'a COMMITTED transfer appears only
    here'."*

    This is the case a re-implemented contract loses: filtering on
    `committed_at__isnull=False` leaves a committed-only fixture completely
    green. So the fixture stops a job at step 2 and asserts its account is in
    the published set even though nothing has closed yet.
    """
    with tenant_ctx(brazos):
        name = "Osei, Grace"
        account = _account(marcus, brazos, label="12 Harbour View", name=name)
        customers_services.link_customer(account_id=account["id"], display_name=name)
        target = _unit(marcus, brazos, label="500 Main · 210")
        started = transfers.start_transfer(marcus, {"from_account_id": str(account["id"])})
        transfers.set_target_unit(marcus, started["id"], {"to_unit_id": str(target["id"])})

        published = set(move_reads.move_outs_list(as_of=TODAY)["exclusion"]["half_account_ids"])
        assert str(account["id"]) in published
        assert transfers.is_transfer_half(account["id"]) is True


# ════════════════════════════════════════════════════════════════════════════
# 4 · TENANT SCOPING (CLAUDE.md hard rule 1) AND PAGING (11b G5)
# ════════════════════════════════════════════════════════════════════════════
def test_neither_list_crosses_a_tenant(brazos, marcus, lonestar):
    """Hard rule 1 — *"never touch a tenant table without `app.tenant_id` set …
    No cross-tenant queryset."*

    Both lists filter on `_tenant_id()`, which is `transfers._tenant_id` and
    raises `AUTH_TENANT_UNRESOLVABLE` when no tenant is set. A second tenant's
    rows are invisible, and so is a second tenant's KPI count — the tile is the
    half a scoping bug hides behind, because a leaked row is visible and a
    leaked COUNT is just a bigger number.
    """
    with tenant_ctx(brazos):
        _booked_in(marcus, brazos, opened_at="2026-09-01")
        _moved_out(marcus, brazos)
        assert move_reads.move_ins_list(as_of=TODAY)["total"] == 1
        assert move_reads.move_outs_list(as_of=TODAY)["total"] == 1

    # `lonestar` is the repo's own isolation tenant, provisioned exactly as
    # `brazos` is — a hand-built `Tenant()` row would prove isolation against a
    # world that provisioning never made.
    with tenant_ctx(lonestar):
        assert move_reads.move_ins_list(as_of=TODAY)["total"] == 0
        assert move_reads.move_outs_list(as_of=TODAY)["total"] == 0
        assert move_reads.move_in_kpis(as_of=TODAY)["open"] == 0
        assert move_reads.move_out_kpis(as_of=TODAY)["open"] == 0


def test_both_lists_page_and_carry_the_same_envelope(brazos, marcus):
    """11b G5 — pagination is mandatory on every list, and both tabs answer the
    same envelope so one screen component can read either."""
    with tenant_ctx(brazos):
        for index in range(3):
            _booked_in(
                marcus,
                brazos,
                label=f"Unit {index}",
                name=f"Mover {index}",
                opened_at=f"2026-09-0{index + 1}",
            )
        first = move_reads.move_ins_list(page=1, per=2, as_of=TODAY)
        assert first["total"] == 3
        assert first["pages"] == 2
        assert len(first["rows"]) == 2
        second = move_reads.move_ins_list(page=2, per=2, as_of=TODAY)
        assert len(second["rows"]) == 1
        # No row appears on both pages — the sort is stable (IS-2).
        assert not {row["account_id"] for row in first["rows"]} & {
            row["account_id"] for row in second["rows"]
        }

        envelope = {
            "rows", "kpis", "page", "per", "total", "pages",
            "columns", "states", "search", "exclusion", "unavailable", "as_of",
        }
        assert envelope <= set(first)
        assert envelope <= set(move_reads.move_outs_list(as_of=TODAY))
        assert first["columns"] == list(move_reads.MOVE_IN_COLUMNS)
        assert move_reads.move_outs_list(as_of=TODAY)["columns"] == list(
            move_reads.MOVE_OUT_COLUMNS
        )


def test_the_week_window_is_the_same_seven_days_the_transfers_tab_uses(brazos, marcus):
    """§5.5.1 / §5.6.1 / §5.7.1 all caption their second tile *"within 7 days of
    today"*. Three tabs on ONE screen counting "this week" two different ways is
    a KPI strip that lies, so the boundary is asserted rather than assumed:
    inclusive at both ends, and it does not reach backwards."""
    with tenant_ctx(brazos):
        assert move_reads._within_the_week(TODAY, TODAY) is True
        assert move_reads._within_the_week(TODAY + timedelta(days=7), TODAY) is True
        assert move_reads._within_the_week(TODAY + timedelta(days=8), TODAY) is False
        # A date that has passed is not "this week".
        assert move_reads._within_the_week(TODAY - timedelta(days=1), TODAY) is False
        assert move_reads._within_the_week(None, TODAY) is False
