# ── Trace ──────────────────────────────────────────────
# Change:   `CR-122-BRC06` — the move-in wizard's step 3 `READ DATE` column and
#           its step 4 DISCOUNT CLAIM, both ruled by the PO on 2026-09-19.
#           Screens: S19 move-in — step 3 (Start & read), step 4 (Account
#           preferences).
# Rules:    BR-CUS-021 (reads commit through metering, never from customers) ·
#           BR-MET-128 (the read carries its EVENT and its USER) ·
#           BR-TEN-043 (a flow's date is the flow's own, never a wall clock) ·
#           B18 §5.3.4 (*"never blocks service — only the discount"*) ·
#           BR-SHL-019 (one transactional commit).
# Tests:    this file. `10-scripts/po20260919_move_in_wizard_walkthrough.mjs`
#           is the browser half — it proves the COLUMNS are on screen; this
#           proves what reaches the database when they are filled in.
# ───────────────────────────────────────────────────────
"""**What a move-in WRITES when step 3's dates and step 4's claim are used.**

THE GAP THIS FILE CLOSES
------------------------
`CR-122-BRC06` added two things a clerk can now type that nothing asserted:

1. **A PER-ROW READ DATE.** `test_w9_event_reads.py::test_w9_move_in__task_3_*`
   already proves a keyed reading lands with event `move_in` dated the MOVE-IN
   DAY — but every row it sends omits `read_at`, so it exercises the default
   and never the column. The blueprint's whole argument for the column is the
   case it does not cover, and p068 draws it: the move-in is 05/02/2026 and the
   **water meter was read on 04/29/2026**, three days earlier, because a
   walk-by round takes more than a day. Nothing asserted that the earlier date
   survives to the committed row.

2. **A DISCOUNT CLAIM** — `accounts.eligibility_claimed` / `eligibility_note`,
   added by `customers/0057`. Nothing in the suite named either column.

⚠ **AND THE DEFERRED-DATE RULE IS ASSERTED ALONGSIDE IT, DELIBERATELY.**
`moveReadsCapture.tsx` keeps `readAt` as `""` until a clerk edits it, so an
untouched row sends NO `read_at` and takes the flow's event date server-side.
That is the behaviour every row had before this column existed, and the reason
the front end does not send the event date explicitly: doing so would look
identical on screen and would silently freeze a date the clerk later changed on
this same step. Both halves are proved here — the row that says nothing follows
the move, the row that names a date keeps it — because a regression in either
direction is invisible on screen.

⚠ **THE CLAIM IS PROVED NOT TO GATE, WHICH IS THE POINT OF B18 §5.3.4.** The
second claim test does not merely assert the columns; it asserts the move-in
returns the SAME account status and the SAME warning set as one with no claim.
A validator added later that refused a claim without proof would pass a
columns-only test and fail this one.

⚠ **AND A CLAIM IS NOT A GRANT.** `proof_before_first_reduction` defaults to
true and `DiscountVersion.eligibility_rule` has no evaluator behind it, so
nothing here should create, enrol or price a discount. The last test asserts
that NOTHING was enrolled — the mirror of hard-won law 1, which runs in this
direction too: a column that stored a claim and quietly started a reduction
would satisfy every other assertion in this file.
"""

import pytest

from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests import identity_fixtures
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    brazos,
    dana,
    make_premises,
    make_unit,
    seed_config,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: The blueprint's own figures, p068. The move happens on the 2nd; the water
#: meter was walked on the 29th of the month before. Using the DRAWN dates
#: keeps this test readable beside the page it comes from.
MOVE_IN_DAY = "2026-05-02"
WATER_READ_DAY = "2026-04-29"


def _plan(tenant, service_code="electric"):
    """A PUBLISHED plan the unit can stand on (BR-RAT-030 — a draft is not
    assignable, and would fail to resolve as an unrelated-looking bug)."""
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=f"CR122 {service_code}",
        defaults={"code": f"cr122-{service_code}", "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"CR122 — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _metered_unit(admin, tenant, *, meters=(("M-4021", "electric", "kWh"),)):
    """One unit holding real meters, built through the real services."""
    services = sorted({service for _no, service, _uom in meters})
    premises = make_premises(admin, services_available=services)
    unit = make_unit(admin, premises["id"], label="Unit 4B", services=services)
    metering_services.assign_unit_plan(admin, unit["id"], {"tariff_id": str(_plan(tenant).id)})
    for asset_no, service, uom in meters:
        a_meter(admin, asset_no, unit_id=unit["id"], service=service, uom=uom)
    return unit


def _asset_id(unit, asset_no):
    """The meter's id through the PUBLISHED seam, so this test never reaches
    into the assets ORM (the W9-seam file's helper, same reasoning)."""
    from apps.metering import seams as metering_seams

    for row in metering_seams.assets_on_unit(unit["id"]):
        if row["asset_no"] == asset_no:
            return row["id"]
    raise AssertionError(f"{asset_no} is not assigned to this unit")


def _head(asset_id, channel="total"):
    """The committed lineage HEAD for one register (BR-MET-016/053)."""
    return (
        metering_models.MeterRead.objects.filter(
            asset_id=asset_id, channel=channel, superseded_by_id__isnull=True
        )
        .order_by("-read_at")
        .first()
    )


def _occupant(clerk, unit_id, *, name, opened_at="2026-03-01"):
    """An ACTIVE account holding the unit — the state a move-in starts from."""
    return customers_services.create_account(
        clerk,
        {
            "unit_id": str(unit_id),
            "account_type": "residential",
            "status": "active",
            "opened_at": opened_at,
            "contact": {"full_name": name},
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
        },
    )


def _move_in_payload(name, **overrides):
    payload = {
        "account_type": "residential",
        "opened_at": MOVE_IN_DAY,
        "contact": {"full_name": name},
        "customer": identity_fixtures.customer_block(name, account_type="residential"),
    }
    payload.update(overrides)
    return payload


def _freed_unit(dana, brazos, *, meters, outgoing_name="Duarte, Rui"):
    """A unit whose previous occupant has moved out — a move-in's precondition."""
    unit = _metered_unit(dana, brazos, meters=meters)
    outgoing = _occupant(dana, unit["id"], name=outgoing_name)
    customers_services.move_out(dana, outgoing["id"], {"moved_out_on": "2026-05-01"})
    return unit, outgoing


# ════════════════════════════════════════════════════════════════════════════
# 1 · STEP 3 — THE READ DATE COLUMN
# ════════════════════════════════════════════════════════════════════════════
def test_cr122__a_row_that_names_its_own_read_date_keeps_it(brazos, dana):
    """**THE COLUMN'S WHOLE REASON, in the blueprint's own figures.**

    p068 draws the move-in on 05/02/2026 with the water meter read on
    04/29/2026 and argues for it in its caption: *"The water meter was read
    three days before the tenant moved in, and now it can say so."*

    So the two rows travel together and land on DIFFERENT dates: the electric
    row says nothing and follows the move, the water row names the 29th and
    keeps it. A regression that dropped `read_at` on the way through would put
    both on the move day and every other assertion here would still pass.
    """
    with tenant_ctx(brazos):
        seed_config()
        unit, outgoing = _freed_unit(
            dana,
            brazos,
            meters=(("M-4021", "electric", "kWh"), ("M-4022", "water", "kgal")),
        )

        moved = customers_services.move_in(
            dana,
            outgoing["id"],
            _move_in_payload(
                "Miller, Sarah",
                initial_reads=[
                    # No `read_at` — the deferred date. Follows the move.
                    {"meter_no": "M-4021", "value": "41680"},
                    # The clerk typed the day this register was actually walked.
                    {"meter_no": "M-4022", "value": "8902", "read_at": WATER_READ_DAY},
                ],
            ),
        )

        electric = _head(_asset_id(unit, "M-4021"))
        water = _head(_asset_id(unit, "M-4022"))

    assert moved["event_reads"]["posted_reads"] == 2
    # (a) THE DEFERRED DATE — an untouched row still follows the flow.
    assert electric.read_at.date().isoformat() == MOVE_IN_DAY
    # (b) THE COLUMN — the row that named a date kept it, THREE DAYS EARLIER.
    assert water.read_at.date().isoformat() == WATER_READ_DAY
    # (c) And the two genuinely differ, which is the thing that was impossible
    #     before this column existed.
    assert electric.read_at.date() != water.read_at.date()
    # (d) BR-MET-128 still rides both rows — the column changed the DATE and
    #     nothing else about what a committed event read carries.
    assert electric.event_context == "move_in"
    assert water.event_context == "move_in"
    assert water.imported_by_id == dana.id


def test_cr122__could_not_be_read_invents_nothing_and_forces_a_visit(brazos, dana):
    """**The fourth drawn column — `COULD NOT BE READ`, p068 — and what it
    really costs.**

    The drawing ticks it on the demand register, draws that row's reading as
    `—`, and states the consequence in red: *"The demand register could not be
    read, and could not be estimated either. A demand peak is never estimated,
    because the charge it drives would be disputed."*

    ⚠ **THIS ASSERTS THE REFUSAL, NOT A POST, AND THE DIFFERENCE WAS MEASURED
    RATHER THAN ASSUMED.** A first draft of this test asserted
    `posted_reads >= 1`, reasoning that *"a register nobody could read is a
    fact the next clerk needs"*. It is — but that fact is not carried by a
    committed read. The door answers `posted_reads: 0` with the register named
    in `estimates`, `estimated: false`, `reason: "no_history"`, and a
    `forced_disposition` of **`field_visit`**: nothing is invented, and
    somebody is sent back.

    That is the better guarantee and the one worth guarding. A later change
    that quietly posted a ZERO here, or that dropped the row silently, would
    look like success on every other assertion in this file.
    """
    with tenant_ctx(brazos):
        seed_config()
        unit, outgoing = _freed_unit(
            dana,
            brazos,
            meters=(("M-4021", "electric", "kWh"),),
            outgoing_name="Kaur, Simran",
        )
        # The outgoing account's final — the ONLY history this register has.
        metering_services.commit_event_reads(
            dana,
            {
                "event": "move_out",
                "reads": [{"meter_no": "M-4021", "read_at": "2026-05-01", "value": "41000"}],
            },
        )
        before = metering_models.MeterRead.objects.count()

        moved = customers_services.move_in(
            dana,
            outgoing["id"],
            _move_in_payload(
                "Nowak, Ewa",
                initial_reads=[{"meter_no": "M-4021", "estimate": True}],
            ),
        )

        after = metering_models.MeterRead.objects.count()
        head = _head(_asset_id(unit, "M-4021"))

    answer = moved["event_reads"]
    # (a) ⛔ NOTHING WAS INVENTED — no row, and certainly no zero.
    assert answer["posted_reads"] == 0
    assert after == before
    # (b) The register is NAMED rather than dropped. A clerk who ticked the box
    #     learns what happened to that meter.
    assert len(answer["estimates"]) == 1
    outcome = answer["estimates"][0]
    assert outcome["meter_no"] == "M-4021"
    # (c) And it says so plainly: no figure was worked out, and why.
    assert outcome["estimated"] is False
    assert outcome["reason"] == "no_history"
    # (d) THE CONSEQUENCE THE DRAWING CARES ABOUT — somebody has to go back.
    assert outcome["detail"]["forced_disposition"] == "field_visit"
    # (e) The previous occupant's final read is untouched: an unreadable
    #     register does not supersede the last real reading anybody took.
    assert head is not None
    assert head.read_at.date().isoformat() == "2026-05-01"
    assert str(head.current_value) == "41000.000000"


# ════════════════════════════════════════════════════════════════════════════
# 2 · STEP 4 — THE DISCOUNT CLAIM
# ════════════════════════════════════════════════════════════════════════════
def test_cr122__the_claim_lands_on_the_account(brazos, dana):
    """**`customers/0057`'s two columns, written by the move-in door.**

    The claim a clerk ticks at the counter and the claim an applicant makes on
    a service request are ONE FACT, which is why these two names mirror
    `service_requests.eligibility_claimed` / `eligibility_note` exactly.
    """
    with tenant_ctx(brazos):
        seed_config()
        _unit, outgoing = _freed_unit(
            dana,
            brazos,
            meters=(("M-4021", "electric", "kWh"),),
            outgoing_name="Ito, Hana",
        )

        moved = customers_services.move_in(
            dana,
            outgoing["id"],
            _move_in_payload(
                "Alvarez, Rosa",
                eligibility_claimed=True,
                eligibility_note="SENIOR, CAP",
            ),
        )

        account = customers_models.Account.objects.get(id=moved["id"])

    assert account.eligibility_claimed is True
    assert account.eligibility_note == "SENIOR, CAP"


def test_cr122__a_claim_never_gates_the_move_in(brazos, dana):
    """**B18 §5.3.4, verbatim: *"never blocks service — only the discount"*.**

    ⚠ **THIS IS NOT A COLUMNS TEST AND MUST NOT BE SIMPLIFIED INTO ONE.** It
    runs the SAME move-in twice — once claiming, once not — and asserts the two
    commits are indistinguishable in everything except the two claim columns:
    same status, same warning set, an account either way.

    A validator added later that refused an unproved claim, or that held the
    account in some pending state until somebody verified it, would satisfy the
    test above and fail this one. That is the whole point of writing it this
    way: the rule being defended is an ABSENCE, and an absence is invisible to
    a test that only looks at what was written.
    """
    with tenant_ctx(brazos):
        seed_config()

        _u1, plain_out = _freed_unit(
            dana,
            brazos,
            meters=(("M-4021", "electric", "kWh"),),
            outgoing_name="Silva, Ana",
        )
        plain = customers_services.move_in(dana, plain_out["id"], _move_in_payload("Bell, Ruth"))

        _u2, claim_out = _freed_unit(
            dana,
            brazos,
            meters=(("M-4023", "electric", "kWh"),),
            outgoing_name="Silva, Rui",
        )
        claiming = customers_services.move_in(
            dana,
            claim_out["id"],
            _move_in_payload(
                "Bell, Mary",
                eligibility_claimed=True,
                eligibility_note="Veteran — proof at the counter",
            ),
        )

        claimed_account = customers_models.Account.objects.get(id=claiming["id"])

    # (a) It committed at all — no refusal, no exception.
    assert claiming["id"] is not None
    # (b) The SAME status. A claim does not hold an account pending.
    assert claiming["status"] == plain["status"]
    # (c) The SAME warnings. A claim adds no new thing to chase.
    assert {w["code"] for w in claiming["warnings"]} == {w["code"] for w in plain["warnings"]}
    # (d) And the claim is on the row, so (b) and (c) are not passing because
    #     the claim was quietly discarded.
    assert claimed_account.eligibility_claimed is True


def test_cr122__a_claim_is_not_a_grant(brazos, dana):
    """**A CLAIM ENROLS NOBODY, and nothing on the screen may imply it does.**

    `proof_before_first_reduction` defaults to true and
    `DiscountVersion.eligibility_rule` is advisory with no evaluator behind it
    — its own docstring names automatic evaluation as `EP-RAT-12`'s remainder.
    Enrolment is a staff act through `discount_services.enrol_account`.

    ⚠ **SO THE ASSERTION IS THAT NOTHING HAPPENED**, which is the one shape of
    claim this file could otherwise get wrong in a way no other test would see:
    a later lane wiring the claim to an enrolment would make every assertion
    above pass and would start reducing bills for customers nobody verified.
    """
    from apps.rating import discounts as discount_models

    with tenant_ctx(brazos):
        seed_config()
        _unit, outgoing = _freed_unit(
            dana,
            brazos,
            meters=(("M-4021", "electric", "kWh"),),
            outgoing_name="Ortiz, Sam",
        )
        before = discount_models.DiscountEnrolment.objects.count()

        moved = customers_services.move_in(
            dana,
            outgoing["id"],
            _move_in_payload(
                "Reyes, Lila",
                eligibility_claimed=True,
                eligibility_note="SENIOR",
            ),
        )

        after = discount_models.DiscountEnrolment.objects.count()
        account = customers_models.Account.objects.get(id=moved["id"])

    # The claim is recorded …
    assert account.eligibility_claimed is True
    # … and NOT ONE enrolment was created by recording it.
    assert after == before
