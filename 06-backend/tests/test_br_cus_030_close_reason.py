# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-005 (the move-out flow) · US-SHL-0xx (wizard parks, CR-035)
#           Screens: S20 (the move-out wizard, step 2) · the move record page
# Change:   PO ruling 2026-09-20, decision log *"TEN MOVE-OUT RULINGS IN ONE
#           SITTING"* — **item 3** (the move-out reason gets a column, option A)
#           and **item 9** (a parked move-out is allocated a reference, option A)
# Rules:    BR-CUS-030 (what a move-out writes) · BR-TEN-035 (a number is
#           allocated in the issuing transaction) · BR-SHL-048 (a parked wizard
#           changes NOTHING until it is executed) · BR-CUS-150 (the record is of
#           the JOB) · CLAUDE.md hard rule 4 (financial immutability — no
#           migration invents a reason for a close already made)
# Defect:   DEF-CUS-5922 — a parked move-out cannot be opened from its own
#           record at all, because `/moves/{ref}` matches on a reference and
#           NULL matches nothing
# Tests:    this file
# Impacts:  apps/customers/migrations/0058 · apps/customers/models.Account
#           .close_reason · services.move_out · services._clean_close_reason ·
#           services._adopt_wizard_draft · selectors.account_row ·
#           move_record_reads._completed/_in_flight · move_reads (the tab row) ·
#           tenancy/wizard_parks.DRAFT_REFERENCE_SERIES
# ───────────────────────────────────────────────────────
"""Two rulings of 2026-09-20, asserted at the door rather than at the model.

⚠ **EVERY CASE HERE DRIVES `services.move_out` OR `wizard_parks.park`.** A test
that set `account.close_reason = "lease_ended"` and read it back would assert
that Django can write a column, which nobody doubted. What was actually broken
is the PATH: five options drawn on a screen with nothing behind them, and a
draft with no number that a route keyed on numbers could never find.

NON-VACUOUS
-----------
Each assertion is paired with the thing that stops it passing over an empty
world — an account that really closed, a park row that really exists, a
reference read back out of the database rather than off the response.
"""

import pytest

from apps.customers import models as customers_models
from apps.customers import move_reads as customers_move_reads
from apps.customers import move_record_reads
from apps.customers import moves as customers_moves
from apps.customers import services as customers_services
from apps.tenancy import models as tenancy_models
from apps.tenancy import wizard_parks
from core import errors, tenancy as core_tenancy

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)
from tests.test_us_cus_004_005_move_in_out import (  # noqa: F401
    MOVE_OUT_DAY,
    _occupant,
    _unit_with_plan,
)

pytestmark = pytest.mark.django_db


def _seed_move_series(series: str, fmt: str) -> None:
    """The row a real host gets from `manage.py seed_demo`.

    ⚠ **SEEDED EXPLICITLY RATHER THAN ASSUMED**, for the reason
    `test_cr035_wizard_parks._seed_move_series` records: a test that assumed it
    would pass for the wrong reason on a fixture that happens to carry one, and
    go quietly green on a fixture that does not.
    """
    tenant_id = core_tenancy.current_tenant_id()
    tenancy_models.NumberSeries.objects.get_or_create(
        tenant_id=tenant_id, series=series, defaults={"format": fmt, "next_number": 1}
    )


# ══════════════════════════════════════════════════════════════════════════
# ITEM 3 · THE MOVE-OUT REASON GETS A COLUMN
# ══════════════════════════════════════════════════════════════════════════
def test_item3__the_reason_a_clerk_chooses_is_stored_on_the_account(marcus, brazos):
    """p110's dashed panel, closed: *"the wizard asks and forgets."*"""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        closed = customers_services.move_out(
            marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY, "reason": "lease_ended"}
        )

        # ⚠ READ BACK OUT OF THE DATABASE, never off the response — a service
        # that echoed the payload and wrote nothing would pass the other half.
        row = customers_models.Account.objects.get(pk=account["id"])
        assert row.close_reason == "lease_ended"
        # NON-VACUOUS: the account really closed, so this is a reason ON a
        # move-out rather than a column set on an untouched row.
        assert row.closed_at is not None

        # …and it is SERVED, which is the half `DEF-CUS-5927`'s family keeps
        # teaching: a value a clerk types that no screen returns is the shape
        # that produced three defects on this surface in one day.
        assert closed["close_reason"] == "lease_ended"


def test_item3__an_omitted_reason_leaves_null_and_never_writes_other(marcus, brazos):
    """**NULL means *nobody was asked*; `other` means *asked, none fitted*.**

    Folding the two together would over-count `other` by every close made
    before the column existed, and a utility's closure report would be wrong in
    a way nobody could see.
    """
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        customers_services.move_out(marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY})

        row = customers_models.Account.objects.get(pk=account["id"])
        assert row.close_reason is None
        assert row.closed_at is not None  # NON-VACUOUS: it really closed


def test_item3__an_unknown_reason_is_refused_by_name_and_never_coerced(marcus, brazos):
    """⚠ **NEVER MAPPED ONTO `other`.** Silently coercing a typo is how a count
    becomes a lie: `other` would grow by every client bug and nobody reading the
    report could tell."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)

        with pytest.raises(errors.ValidationError) as excinfo:
            customers_services.move_out(
                marcus,
                account["id"],
                {"moved_out_on": MOVE_OUT_DAY, "reason": "landlord_evicted"},
            )
        assert excinfo.value.field_errors[0]["field"] == "reason"
        assert excinfo.value.field_errors[0]["params"]["br_ref"] == "BR-CUS-030"

        # ⚠ **AND NOTHING WAS WRITTEN.** The refusal happens before the
        # transaction opens, so a bad code costs the clerk nothing else. An
        # account left half-closed by a rejected reason would be far worse than
        # the reason being lost.
        assert customers_models.Account.objects.get(pk=account["id"]).closed_at is None


def test_item3__close_reason_the_column_name_is_refused_on_this_door_too(marcus, brazos):
    """ONE spelling in. `reason` is the field; `close_reason` is the column, and
    accepting both would let a caller set one fact two ways."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        with pytest.raises(errors.ValidationError) as excinfo:
            customers_services.move_out(
                marcus,
                account["id"],
                {"moved_out_on": MOVE_OUT_DAY, "close_reason": "lease_ended"},
            )
        assert excinfo.value.field_errors[0]["field"] == "close_reason"


def test_item3__every_one_of_the_five_survives_the_round_trip(marcus, brazos):
    """⚠ **ALL FIVE, NOT ONE.** Asserting a single code would pass over a
    service that hardcoded it — the *"what would make this check pass
    WRONGLY"* question, answered."""
    with tenant_ctx(brazos):
        for index, code in enumerate(customers_models.CLOSE_REASONS):
            unit = _unit_with_plan(marcus, brazos, label=f"Unit R{index}")
            account = _occupant(marcus, brazos, unit)
            customers_services.move_out(
                marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY, "reason": code}
            )
            assert customers_models.Account.objects.get(pk=account["id"]).close_reason == code
        # NON-VACUOUS: five distinct codes were actually exercised.
        assert len(customers_models.CLOSE_REASONS) == 5


def test_item3__the_reason_reads_back_on_the_move_record(marcus, brazos):
    """The ruling's other half: *readable on the move record too, not merely
    stored.* Read by WALKING to the account — BR-CUS-150 keeps the record a
    record of the JOB, so nothing the close wrote is copied into it."""
    with tenant_ctx(brazos):
        _seed_move_series("move_out", "MVO-{YY}-{0000}")
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        closed = customers_services.move_out(
            marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY, "reason": "deceased"}
        )

        record = move_record_reads.record_detail(closed["move_no"])
        assert record["what_happened"]["close_reason"]["value"] == "deceased"
        assert record["what_happened"]["close_reason"]["unavailable"] is None
        # NON-VACUOUS: it is the right record.
        assert record["state"] == "completed"
        assert record["kind"] == "move_out"


def test_item3__a_close_with_no_reason_states_WHICH_silence_it_is(marcus, brazos):
    """**Two silences, and they are different facts about the utility's own
    record.** *Nobody was asked* (the close predates the column) and *they did
    not say* (asked, skipped) would be wrong half the time under one sentence.
    """
    with tenant_ctx(brazos):
        _seed_move_series("move_out", "MVO-{YY}-{0000}")
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        closed = customers_services.move_out(
            marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY}
        )
        record = move_record_reads.record_detail(closed["move_no"])
        absence = record["what_happened"]["close_reason"]["unavailable"]
        # `MOVE_OUT_DAY` is 2026-08-14, before the column shipped on 2026-09-20,
        # so this close is on the *not asked* side of the line.
        assert absence["code"] == "close_reason_was_not_asked"
        assert record["what_happened"]["close_reason"]["value"] is None


def test_item3__the_stale_warning_is_gone_from_every_response(marcus, brazos):
    """`close_reason_not_recorded` said the column *"is PROPOSED-SCHEMA and not
    built"*. Hard-won law 1: a stale warning is a stale claim, and this list is
    the one place a caller learns what a move-out did NOT do."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        closed = customers_services.move_out(marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY})
        codes = {warning["code"] for warning in closed["warnings"]}
        assert "close_reason_not_recorded" not in codes
        # NON-VACUOUS: the warning list is real and still carries its siblings.
        assert "dunning_not_stopped" in codes


# ══════════════════════════════════════════════════════════════════════════
# ITEM 9 · A PARKED MOVE-OUT IS ALLOCATED A REFERENCE  (DEF-CUS-5922)
# ══════════════════════════════════════════════════════════════════════════
def test_item9__a_parked_move_out_can_be_opened_from_its_own_record(marcus, brazos):
    """⚠ **THE DEFECT ITSELF, END TO END.** `/moves/{ref}` is keyed on a
    reference and `_park_by_reference` filters `reference__iexact`, which NULL
    can never match — so before this ruling a parked move-out could not be
    opened from its own record AT ALL, and the `Resume` door built on
    2026-09-19 was unreachable for it.
    """
    with tenant_ctx(brazos):
        _seed_move_series("move_out", "MVO-{YY}-{0000}")
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        park = wizard_parks.park(
            marcus,
            {
                "flow": "move_out",
                "step": 3,
                "subject_label": "Unit A, 1408 Elm Street",
                "subject_ref": {"account_id": str(account["id"])},
                "values": {"moved_out_on": MOVE_OUT_DAY, "account_id": str(account["id"])},
            },
        )

        assert park.reference, "a parked move-out must carry a reference"
        assert park.reference.startswith("MVO-"), park.reference

        # THE DOOR OPENS — the whole point of the ruling.
        record = move_record_reads.record_detail(park.reference)
        assert record["state"] == "in_flight"
        assert record["move_no"] == park.reference
        # The RESUME handle, without which the record could name the draft and
        # not open it (PO 2026-09-19, *"Close or complete it"*).
        assert record["park_id"] == str(park.id)
        # ⚠ **AND THE DATE THE CLERK TYPED IS ON IT.** `_in_flight` read
        # `moved_in_on`/`effective_on` and never `moved_out_on`, so the day this
        # became openable it would have opened saying *"not chosen yet"* about a
        # date the clerk had keyed themselves.
        assert record["effective_on"] == MOVE_OUT_DAY

        # ⚠ **LOWERCASE TOO** — the blueprint's own URL is
        # `/brazosbend/moves/mvo-26-0088` while the number a clerk quotes is
        # upper, and the match is case-insensitive for exactly that reason.
        assert move_record_reads.record_detail(park.reference.lower())["park_id"] == str(park.id)


def test_item9__the_number_the_draft_quoted_is_the_number_it_is_filed_under(marcus, brazos):
    """**ADOPTED, NOT RE-ALLOCATED.** A second number here would file the
    finished job under one nobody was told — and would burn the counter twice
    for one move-out."""
    with tenant_ctx(brazos):
        _seed_move_series("move_out", "MVO-{YY}-{0000}")
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        park = wizard_parks.park(
            marcus,
            {
                "flow": "move_out",
                "step": 3,
                "subject_label": "Unit A, 1408 Elm Street",
                "subject_ref": {"account_id": str(account["id"])},
                "values": {"moved_out_on": MOVE_OUT_DAY},
            },
        )
        drafted = park.reference

        closed = customers_services.move_out(
            marcus,
            account["id"],
            {"moved_out_on": MOVE_OUT_DAY, "wizard_park_id": str(park.id)},
        )

        assert closed["move_no"] == drafted
        # …read back off the RECORD, not the response.
        assert customers_moves.MoveRecord.objects.get(
            tenant_id=core_tenancy.current_tenant_id(), kind="move_out", account_id=account["id"]
        ).move_no == drafted
        # ⚠ **AND THE DRAFT IS GONE**, so the reference is never live on two
        # rows at once — `uq_wizard_parks_tenant_reference_ci`'s whole point.
        assert not tenancy_models.WizardPark.objects.filter(pk=park.id).exists()
        # NON-VACUOUS: exactly one move-out record exists for this account.
        assert (
            customers_moves.MoveRecord.objects.filter(
                tenant_id=core_tenancy.current_tenant_id(), account_id=account["id"]
            ).count()
            == 1
        )


def test_item9__a_move_in_draft_may_not_be_consumed_by_a_move_out(marcus, brazos):
    """The `flow` argument's reason for existing: a move-out adopting a move-in's
    number would file a departure under an arrival's reference."""
    with tenant_ctx(brazos):
        _seed_move_series("move_in", "MVI-{YY}-{0000}")
        _seed_move_series("move_out", "MVO-{YY}-{0000}")
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        foreign = wizard_parks.park(
            marcus,
            {"flow": "move_in", "step": 2, "subject_label": "Unit A", "values": {}},
        )
        assert foreign.reference.startswith("MVI-")

        closed = customers_services.move_out(
            marcus,
            account["id"],
            {"moved_out_on": MOVE_OUT_DAY, "wizard_park_id": str(foreign.id)},
        )
        # It allocated its OWN number and left the move-in draft alone.
        assert closed["move_no"].startswith("MVO-")
        assert tenancy_models.WizardPark.objects.filter(pk=foreign.id).exists()


def test_item9__the_move_outs_tab_prints_the_number_rather_than_an_absence(marcus, brazos):
    """⚠ **THE HALF A LANE FIXING ONLY THE ALLOCATOR WOULD HAVE LEFT.** The
    draft would be numbered, `/moves/{ref}` would open it, and the LIST — the
    one screen a clerk reads it off — would still say *"no number yet"*."""
    with tenant_ctx(brazos):
        _seed_move_series("move_out", "MVO-{YY}-{0000}")
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        park = wizard_parks.park(
            marcus,
            {
                "flow": "move_out",
                "step": 3,
                "subject_label": "Unit A, 1408 Elm Street",
                "subject_ref": {"account_id": str(account["id"])},
                "values": {"moved_out_on": MOVE_OUT_DAY},
            },
        )
        rows = customers_move_reads.move_outs_list(per=50)["rows"]
        parked = [row for row in rows if row.get("park_id") == str(park.id)]
        assert len(parked) == 1, "the unfinished move-out must be in the list"
        assert parked[0]["move_no"] == park.reference
        assert parked[0]["move_no_unavailable"] is None


def test_item9__a_tenant_with_no_move_out_series_still_parks(marcus, brazos):
    """⚠ **A MISSING SERIES COSTS THE REFERENCE, NEVER THE DRAFT** —
    `moves._allocate_move_no`'s posture, in its own words: *"the move is the
    regulated act; its reference is not."* Losing an afternoon's typing because
    a lookup table is empty would be the original defect wearing a new hat."""
    with tenant_ctx(brazos):
        tenancy_models.NumberSeries.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), series="move_out"
        ).delete()
        park = wizard_parks.park(
            marcus,
            {"flow": "move_out", "step": 2, "subject_label": "Unit A", "values": {}},
        )
        assert park.reference is None
        assert park.id is not None  # the DRAFT survived, which is the point

        # …and the list says so in a sentence a clerk can act on, rather than
        # printing a dash it invented.
        rows = customers_move_reads.move_outs_list(per=50)["rows"]
        parked = [row for row in rows if row.get("park_id") == str(park.id)]
        assert len(parked) == 1
        assert parked[0]["move_no"] is None
        assert parked[0]["move_no_unavailable"]["code"] == "parked_move_out_has_no_reference"


def test_item9__the_three_remaining_flows_still_take_no_number(marcus, brazos):
    """The ORIGINAL reasoning, still holding: a number minted for a flow whose
    drafts appear only in the parked-drafts panel — which draws no reference
    column — is spent where nobody can read it. A lane widening the allocator
    again comes through this test rather than past it."""
    with tenant_ctx(brazos):
        for series, fmt in (("transfer", "TRF-{YY}-{0000}"), ("disconnect", "DSC-{YY}-{0000}")):
            _seed_move_series(series, fmt)
        for flow in ("transfer", "disconnect", "new_connect"):
            park = wizard_parks.park(
                marcus, {"flow": flow, "step": 1, "subject_label": "Unit A", "values": {}}
            )
            assert park.reference is None, f"{flow} must take no reference"


# ── Lifecycle ─────────────────────────────────────────────
# packet: the decision log of 2026-09-20, *"TEN MOVE-OUT RULINGS IN ONE SITTING"*,
#   items 3 and 9 (both option A) + DEF-CUS-5922 + OQ-CUS-12489 (CLOSED)
# generated: 2026-09-20 by the move-out rulings lane (MAINTENANCE — both
#   surfaces are live; `12-governance/22-product-maintenance-process.md`)
# checklist: A✔ B✔ C✔ D✔ E✔ (the screen halves are asserted in
#   MoveOutWizard.test.tsx and MoveRecordPage.test.tsx) F✔ G✔
#   H=HUMAN-REVIEW-PENDING (migration 0058 is a 🔒 migration-ordering path;
#   the ledger row is 12-governance/09-human-review-ledger.md)
# gates: every case proved RED before green by reverting the change it guards —
#   see the lane report for the verbatim failures
# exceptions: the reason's DISPLAY strings are not asserted here (they are the
#   eleven catalogues' and are asserted in the frontend suite) · whether a
#   mistyped reason may be CORRECTED after the close is OQ-CUS-12513 and is
#   OPEN — nothing here implies it can · whether the list becomes
#   tenant-extensible is OQ-CUS-12512 and is OPEN · no case asserts anything
#   about accounts closed BEFORE the column existed beyond the absence they
#   serve, because hard rule 4 forbids writing one and this suite may not
#   manufacture history to test against
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
