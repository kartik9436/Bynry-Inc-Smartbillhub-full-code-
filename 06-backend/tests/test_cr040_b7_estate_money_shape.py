# ── Trace ──────────────────────────────────────────────
# Change:   CR-040 wave B, task B7 — "Guards: the `Master` pill has children;
#           the ageing report has more than one opening row."
# Defects:  DEF-940 (the packet says ONE opening balance; the seed carries
#           FOURTEEN) · DEF-941 (the packet's census is two waves stale: 118
#           units on 70 premises, not 62) · DEF-942 (`connections.
#           owner_account_id` is unstampable on the seeded master) ·
#           DEF-828 / DEF-466 (a guard must assert the interesting set is
#           NON-EMPTY as well as correct)
# OQs:      OQ-530 (not one account a bill run touches carries an opening
#           balance — should one?) · OQ-531 (what links a sub-account to its
#           master?) · OQ-366 (whose door the ladder knocks on after a
#           sub-account closes owing — untouched here, deliberately)
# Rules:    BR-CUS-048 (four aged bands, aged FORWARD from cutover) ·
#           BR-CUS-016 (the AGEING cell is DERIVED, never typed) ·
#           BR-CUS-017 (one occupying account per unit, ever) ·
#           BR-CUS-068 / BR-MET-101 (a master account covers COMMON-AREA units
#           through the same account–unit linkage every account uses) ·
#           BR-MET-116 (`Units 26` = 25 apartments + 1 common area) ·
#           BR-TEN-063 (a replay writes nothing)
# Tests:    this file
# Impacts:  core/sample_fixture.py · apps/metering/sample_data.py ·
#           apps/customers/sample_data.py
# ───────────────────────────────────────────────────────
"""CR-040 B7 — **what the seeded estate's MONEY SHAPE actually is.**

Every number asserted here was MEASURED off a full plant on 2026-08-27, and
three of them contradict the packet this task was written from. That is the
whole reason the file exists: CR-040 sized B4 as *"the estate must GROW"* from
a sentence reading *"ONE account of 48"*, and the seed carries **fourteen**
opening positions. Nothing in this repository asked the estate, so nothing
noticed — the suite that pins a fixture count
(`tests/test_us_ten_019_sample_records.py`) pins the **base** plan on purpose
and stays green while the estate grows underneath it.

**Every assertion runs against the estate the REAL seeders plant, through those
seeders' own entry points** — `test_def709_seeded_master_account.py`'s own
posture, and for its reason: a test that builds its own accounts here would
prove the feature and reproduce the defect.

**NON-VACUOUS IN DEF-828's SHAPE.** Each guard asserts the interesting set is
NON-EMPTY *before* it asserts anything is true of it. A guard that walks an
empty set and reports success is the failure mode DEF-466 and DEF-828 were both
filed for, and three of the sets below (accounts with an opening position, the
master's premises-mates, the master's covered units) would each be empty on a
tenant whose estate did not load.

**TWO GUARDS ASSERT A GAP RATHER THAN A GUARANTEE, AND SAY SO BY NAME** — the
posture OQ-424's own note describes (*"the figure is asserted … so the day the
PO rules B, that test is what goes red and names the place to build it"*).
`test_no_account_with_an_opening_position_is_in_a_billing_cycle` states
**OQ-530** and `test_the_developer_connection_still_has_no_payer` states
**DEF-942**. Neither is a claim that the state is right. Both go RED the moment
somebody changes it, which is when the question has to be answered.
"""

from decimal import Decimal

import pytest

from apps.customers import models as customers_models
from apps.customers import sample_data as customers_sample
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.metering import sample_data as metering_sample
from apps.rating import sample_data as rating_sample
from core import sample_fixture as fixture

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import tenant_ctx
from tests.test_us_met_helpers import (  # noqa: F401 — brazos/dana are fixtures
    brazos,
    dana,
)

pytestmark = pytest.mark.django_db

#: MEASURED 2026-08-27 on a full plant, and the figure DEF-940 exists for. The
#: packet said ONE. Asserted as a FLOOR, never an equality: another lane may
#: lawfully migrate more accounts, and this guard's job is to catch the estate
#: dropping BACK to one, not to freeze the fixture.
OPENING_POSITION_ACCOUNTS_MEASURED = 14

#: DEF-941 — the packet's census. Asserted as the number this file refuses to
#: agree with rather than as a target.
PACKET_UNIT_CENSUS = 62

#: BR-CUS-083 / BR-MET-116's own worked case: the build whose payer the master
#: account is supposed to be.
DEVELOPER_CONNECTION_NO = "CON-26-0117"


@pytest.fixture()
def seeded(brazos, dana):
    """The plant in the orchestrator's own order (`apps.tenancy.sample_data.
    SAMPLE_MODULES`): rating — the plans a unit must carry before an account may
    activate (BR-MET-040) — then metering (the places), then customers (the
    accounts)."""
    with tenant_ctx(brazos):
        rating_sample.seed_sample_records(dana)
        metering_sample.seed_sample_records(dana)
        customers_sample.seed_sample_records(dana)
    return brazos, dana


def _positive_opening_accounts(tenant):
    """`{account_no: {bucket: amount}}` for every account holding a POSITIVE
    opening amount. A 0.00 band ages nothing (`ageing_segments_for` skips it),
    so a row of four zeroes is not an opening position and is not counted."""
    out: dict[str, dict[str, Decimal]] = {}
    rows = customers_models.AccountOpeningBucket.objects.filter(tenant_id=tenant.id).select_related(
        "account"
    )
    for row in rows:
        if row.amount is None or row.amount <= 0:
            continue
        out.setdefault(row.account.account_no, {})[row.bucket] = row.amount
    return out


# ══════════════════════════════════════════════════════════════════════════
# 1 · B4 — "opening balances on SEVERAL accounts, not one"
# ══════════════════════════════════════════════════════════════════════════


def test_the_estate_carries_opening_positions_on_more_than_one_account(seeded):
    """**DEF-940, as the one assertion that would have caught it.**

    CR-040 step 3: *"⚠ **ONE account of 48.** `A-12103` … The other 47 start at
    zero"*, and B4 built on it: *"more opening balances means more MIGRATED
    accounts"*. Measured on a full plant: **fourteen** accounts carry a positive
    opening position, thirteen of them planted through the very door B4 names
    (`services.create_from_import`).

    RED BEFORE THE CR-030 ESTATE LANDED: `assert 1 >= 2`.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        positions = _positive_opening_accounts(tenant)
        # NON-VACUOUS (DEF-828): the set is asserted non-empty before anything
        # is asserted about it, so an estate that failed to load cannot pass by
        # walking nothing.
        assert positions, (
            "no account in the seeded estate carries an opening position at all — "
            "the customers block did not load"
        )
        assert len(positions) >= 2, (
            "DEF-940 / CR-040 B4: the seeded estate must carry opening balances on "
            f"MORE THAN ONE account and carries {len(positions)}: {sorted(positions)}"
        )
        assert len(positions) >= OPENING_POSITION_ACCOUNTS_MEASURED, (
            f"the estate carried {OPENING_POSITION_ACCOUNTS_MEASURED} opening positions "
            f"when this guard was written (2026-08-27) and now carries {len(positions)}: "
            f"{sorted(positions)}. A DROP is the regression this floor exists for — "
            "growing past it is lawful and this assertion is a floor, not an equality."
        )


def test_every_fixture_declared_opening_balance_is_actually_on_file(seeded):
    """The figures are DERIVED from the fixture, never re-typed here.

    `CR030_ACCOUNT_SHAPES` declares each shape's buckets and
    `_seed_cr030_account_shapes` plants them through `create_from_import`; a
    shape that is silently refused (a missing seat, a missing plan) logs a line
    nobody reads and leaves the register a row short. This asserts the whole
    declared set landed, so a silent refusal is RED.

    ⚠ **THE FIXTURE'S COLUMN NAMES AND THE TABLE'S BAND CODES ARE NOT THE SAME
    STRINGS**, and the translation is the product's own: the fixture declares
    `ob_current` / `ob_31_60` / `ob_61_90` / `ob_90_plus` (an import FILE's
    columns, US-CUS-021) and `account_opening_buckets.bucket` holds `current` /
    `d31_60` / `d61_90` / `d90_plus`. This reads `import_writer.BUCKET_FIELDS`
    rather than restating the pairs, so a second copy of the mapping cannot
    drift from the one the writer uses. *(The first draft of this guard compared
    the two vocabularies directly and went RED on a correct fixture — caught by
    running it, which is the whole argument for running a new guard before
    trusting it.)*
    """
    from apps.customers import import_writer

    band_of = dict(import_writer.BUCKET_FIELDS)
    tenant, _ = seeded
    with tenant_ctx(tenant):
        declared = {
            shape["account_no"]: {
                band_of[column]: Decimal(amount)
                for column, amount in (shape.get("buckets") or {}).items()
                if Decimal(amount) > 0
            }
            for shape in fixture.CR030_ACCOUNT_SHAPES
        }
        declared = {no: buckets for no, buckets in declared.items() if buckets}
        assert declared, "the fixture declares no opening balance at all — read the plan"
        on_file = _positive_opening_accounts(tenant)
        for account_no, buckets in sorted(declared.items()):
            assert account_no in on_file, (
                f"{account_no} declares an opening balance in core/sample_fixture."
                "CR030_ACCOUNT_SHAPES and carries none on the tenant — the shape was "
                "refused and the refusal is a log line, not a failure"
            )
            assert on_file[account_no] == buckets, (
                f"{account_no}: fixture declares {buckets} and the product produced "
                f"{on_file[account_no]}"
            )


def test_all_four_aged_bands_are_demonstrated_by_distinct_accounts(seeded):
    """BR-CUS-048's four bands, each with an account a reader can point at.

    The AGEING cell is DERIVED (BR-CUS-016 → BR-CUS-048) through
    `selectors.ageing_segments_for`, which reports the OLDEST band any POSITIVE
    amount of an account's position sits in. ❄️ GT-16's `A-12103` holds all four
    bands at once and therefore demonstrates exactly ONE of them (`d90_plus`),
    which is why "one migrated account" was never the same statement as "the
    four bands are visible".
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        account_ids = list(
            customers_models.Account.objects.filter(tenant_id=tenant.id).values_list(
                "id", flat=True
            )
        )
        assert account_ids, "no accounts on the tenant — the customers block did not load"
        segments = customers_selectors.ageing_segments_for(account_ids)
        assert segments, (
            "no account derives an ageing segment at all — the AGEING column is empty "
            "on every row of S17"
        )
        bands = {band for band, _days in segments.values()}
        expected = set(customers_selectors.AGEING_SEGMENTS)
        assert bands == expected, (
            f"BR-CUS-048's four bands must each be demonstrated; the estate shows "
            f"{sorted(bands)} and is missing {sorted(expected - bands)}"
        )
        # DISTINCT accounts — four bands on one account is one row, not four.
        assert len(segments) >= len(expected), (
            f"{len(segments)} account(s) derive an ageing segment for {len(expected)} bands"
        )


def test_no_account_with_an_opening_position_is_in_a_billing_cycle(seeded):
    """⛔ **OQ-530 — THIS ASSERTS A GAP, NOT A GUARANTEE.**

    The PO asked, verbatim 2026-08-27: *"before you run billing process - you
    need opening balances for accounts"*. MEASURED: every one of the fourteen
    opening positions sits on a seat that joins **no route and no cycle** — the
    CR-030 estate is planted after `_ensure_cycle_and_route` (*"THE ESTATE JOINS
    NO ROUTE, AND THAT IS LOAD-BEARING"*) and ❄️ GT-16's `SCW-U-101` carries no
    service point at all. So `service_points.cycle_id` is NULL on all of them
    and **no bill run in this product's history has met an account with a
    migrated past.**

    That is the real content of the PO's sentence, and closing it is **not a
    lane's decision**: there is no door that gives an EXISTING account an
    opening balance, and seating a migrated account inside the route moves the
    ready-to-run batch off its signed 48 rows. **OQ-530 is open.**

    This test goes RED the day somebody changes it — which is exactly when the
    question has to be answered rather than assumed.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        opening_account_nos = set(_positive_opening_accounts(tenant))
        assert opening_account_nos, "nothing to measure — no opening positions on file"
        unit_ids = set(
            customers_models.Account.objects.filter(
                tenant_id=tenant.id, account_no__in=opening_account_nos
            )
            .exclude(unit_id=None)
            .values_list("unit_id", flat=True)
        )
        assert unit_ids, (
            "every account carrying an opening position is unit-less, which "
            "BR-CUS-017 does not allow — read the plant, not this assertion"
        )
        in_a_cycle = sorted(
            metering_models.ServicePoint.objects.filter(tenant_id=tenant.id, unit_id__in=unit_ids)
            .exclude(cycle_id=None)
            .values_list("unit__unit_no", "cycle__code")
        )
        assert in_a_cycle == [], (
            "⛔ OQ-530 IS OPEN AND THIS STATE JUST CHANGED. An account carrying a "
            f"migrated opening balance is now in a billing cycle: {in_a_cycle}. "
            "Whether a bill run should meet one — and what that does to the "
            "ready-to-run batch's signed 48 rows — is the open question, not a "
            "detail. Answer OQ-530 before making this green again."
        )


# ══════════════════════════════════════════════════════════════════════════
# 2 · B5 / B6 — the `Master` pill, and what actually hangs off it
# ══════════════════════════════════════════════════════════════════════════


def _developer_master(tenant):
    return customers_models.Account.objects.get(
        tenant_id=tenant.id, kind=customers_services.ACCOUNT_KIND_MASTER
    )


def test_the_masters_premises_carries_occupying_accounts_and_none_owes_on_closure(seeded):
    """B5 — *"the `Master` pill has children"*, under the ONLY reading the
    product can express today, and **OQ-531 is why that sentence needs a
    footnote.**

    `accounts` has no parent column; BR-CUS-068 defines a master's coverage over
    COMMON-AREA units and refuses every ordinary unit by name. So the nearest
    thing to a child is reading **(A)** of OQ-531 — an occupying account on the
    premises whose common areas the master covers — and on the seeded estate
    that set is **already non-empty**: `500 Main St` carries `A-11720` and
    `Ridge Coffee Co.`'s four suites beside the master.

    ⚠ **AND THE HALF THAT MATTERS IS THAT NONE OF THEM ANSWERS `OQ-366`.**
    BR-CUS-097 moves a **closed** sub-account's unpayable residue to its master,
    and nobody has ruled whom the ladder then chases. A seeded account that was
    closed still owing would answer that by existing. This asserts every
    premises-mate is OPEN — so the estate carries the STRUCTURE and none of the
    RESIDUE, which is CR-040's own instruction: *"the unruled part is the
    arrears, not the structure"*.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        master = _developer_master(tenant)
        anchor = metering_models.Unit.objects.get(tenant_id=tenant.id, pk=master.unit_id)
        mates = list(
            customers_models.Account.objects.filter(
                tenant_id=tenant.id, unit__premises_id=anchor.premises_id
            )
            .exclude(pk=master.pk)
            .select_related("status", "unit")
        )
        # NON-VACUOUS: the pill must have something under it before anything is
        # asserted about what that something owes.
        assert mates, (
            "OQ-531 reading (A): the master account's premises carries no other "
            "account at all, so the `Master` pill stands over nothing"
        )
        assert all(row.kind == customers_services.ACCOUNT_KIND_REGULAR for row in mates), (
            "a second master account on one premises is not a child of the first"
        )
        closed_owing = [
            (row.account_no, str(row.balance))
            for row in mates
            if row.status.behavior_class not in customers_services.OCCUPYING_BEHAVIOR_CLASSES
            and (row.balance or Decimal("0")) > 0
        ]
        assert closed_owing == [], (
            "⛔ OQ-366 IS OPEN: a seeded account on the master's premises is closed "
            f"and still owes {closed_owing}. BR-CUS-097 moves that residue to the "
            "master and nothing rules whom the dunning ladder then chases, so a "
            "fixture in this state answers an open question by existing."
        )


def test_the_master_covers_its_common_area_and_that_coverage_is_in_no_cycle(seeded):
    """B6 — *"one consolidated master bill"*, and the measured reason there is
    none.

    The MECHANISM is signed and proved end to end: `gather.covered_units` prices
    every covered common area onto ONE document and
    `tests/test_br_cus_068_master_bill.py` pins BR-MET-101's **$41.20 + $28.40 =
    $69.60**. What the seeded estate is missing is not the mechanism — it is the
    inputs. `500 Main St` is planted after `_ensure_cycle_and_route`, so the
    master's covered units have **no cycle**, and a unit in no cycle is in no
    bill run.

    So this asserts both halves: the coverage is REAL (or the pill bills nothing
    and DEF-709's fix is hollow), and it is in no cycle — the same OQ-530
    boundary the opening balances sit behind, reached from the other side.

    ⚠ **"`covered_unit_ids` IS NON-EMPTY" IS NOT AN ASSERTION — IT IS
    UNFALSIFIABLE, AND THIS GUARD SAID IT UNTIL IT WAS PROVED RED.** That
    selector's own docstring reads *"The anchor is always first and always
    present"*, and `accounts.unit_id` is NOT NULL, so a master account can never
    answer an empty list and a test demanding a non-empty one can never fail.
    It is exactly the vacuity DEF-828 and DEF-466 are about, written into the
    guard that cites them — caught only by breaking it. **The falsifiable
    statement is the one that carries the meaning:** coverage rides OPEN
    `service_agreements` (BR-CUS-068), and with none open the master covers
    nothing a bill run can find, whatever the anchor says.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        master = _developer_master(tenant)
        agreements = customers_models.ServiceAgreement.objects.filter(
            tenant_id=tenant.id, account=master, ended_on__isnull=True
        )
        assert agreements.count() >= 1, (
            "coverage rides OPEN `service_agreements` (BR-CUS-068); with none open the "
            "master covers nothing the bill run can find — the `Master` pill over an "
            "empty document, which is DEF-709's defect one layer in"
        )
        covered = customers_selectors.covered_unit_ids(master)
        anchor = metering_models.Unit.objects.get(tenant_id=tenant.id, pk=master.unit_id)
        assert anchor.is_common_area is True, (
            "BR-CUS-068 / BR-MET-101: a master account anchors on a COMMON AREA, and "
            f"{anchor.unit_no} is not flagged as one"
        )
        assert str(anchor.id) in covered, (
            "the anchor must be inside the coverage the bill run prices "
            "(gather.covered_units), or DEF-571 is back"
        )
        billable = sorted(
            metering_models.ServicePoint.objects.filter(tenant_id=tenant.id, unit_id__in=covered)
            .exclude(cycle_id=None)
            .values_list("unit__unit_no", "cycle__code")
        )
        assert billable == [], (
            "⛔ OQ-530: the master's covered units have joined a billing cycle "
            f"({billable}). The demo's ready-to-run batch is a signed shape and a "
            "consolidated master bill is CR-040 task B6 — answer OQ-530 rather than "
            "letting the estate drift into the run."
        )


def test_the_developer_connection_still_has_no_payer(seeded):
    """⛔ **DEF-942 — THIS ASSERTS A GAP, NOT A GUARANTEE.**

    BR-CUS-083 invoices a multi-unit build's connection charges — `CON-26-0117`,
    25 units, **$14,390.00** — to the developer *"via a master account"*. The
    master account exists (DEF-709 planted it) and `connections.owner_account_id`
    is **NULL**, so the build has no payer and the $14,390.00 has nobody to
    invoice.

    MEASURED, and it is why DEF-709's residue is still open: the column's one
    lawful writer (`connections.create_owner_account`, BR-MET-116's door) also
    **creates** the account and has no attach-only form, so the already-seeded
    master cannot be handed to it; and re-routing creation through it would drop
    the account's sub-type (DEF-257) and its mailing address and widen coverage
    from a named unit to *every* common area of the premises. An attach-only
    door is new product behaviour under a set-once column (BR-MET-113) and needs
    a rule, not a lane's judgment.

    RED the day it is stamped — which is the day DEF-942 closes.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        connection = work_tables.Connection.objects.filter(
            tenant_id=tenant.id, connection_no=DEVELOPER_CONNECTION_NO
        ).first()
        assert connection is not None, (
            f"{DEVELOPER_CONNECTION_NO} is not seeded — BR-CUS-083's worked case has "
            "no build, and this guard has nothing to measure"
        )
        # NON-VACUOUS: the master must EXIST for its absence from the connection
        # to mean anything at all.
        master = _developer_master(tenant)
        assert master.unit.premises_id == connection.premises_id, (
            "the seeded master and the seeded build are at different premises, so "
            "DEF-942 is not what this tenant has"
        )
        assert connection.owner_account_id is None, (
            "⛔ DEF-942 JUST CLOSED (or something else stamped the column): "
            f"{DEVELOPER_CONNECTION_NO}.owner_account_id is "
            f"{connection.owner_account_id}. Close the defect row and delete this "
            "assertion — do not weaken it."
        )


# ══════════════════════════════════════════════════════════════════════════
# 3 · DEF-941 — the census, counted where it is PLANTED
# ══════════════════════════════════════════════════════════════════════════


def test_the_forty_eight_are_untouched_and_the_estate_is_bigger_than_the_packet_says(seeded):
    """**Acceptance item 2 (*"Open Accounts and see 48"*) protected from both
    sides, and DEF-941 with it.**

    CR-040's B4 note calls the fixture *"62 units"* with *"every seat taken"*
    and sizes a growth task from it. A full plant holds **118 units on 70
    premises**: CR-030 W6's build seats and its twenty-five apartments and W7's
    twelve transfer/disconnect seats are all missing from that count, and most
    of them carry no account. The 62 is not a floor to grow from; it is a
    census that stopped being true two waves ago.

    What must NOT move is the base plan: 48 units, one occupying account each —
    and `SCW-U-207` vacant, because that is what makes `SR-26-0039` resolve
    *served but vacant*.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        base_unit_nos = [unit["unit_no"] for unit in fixture.units_flat()]
        # ⚠ **48 → 50 ON 2026-09-02 (`CR-062` addendum J3/J4).** The base plan
        # gained the two customer kinds the demo had never held — a municipal
        # building and an industrial plant — and both are APPENDED, so every
        # existing `unit_index` and every ❄️ frozen figure is where it was.
        # Restated rather than loosened, for this test's own stated reason:
        # a band would absorb a seat being silently DROPPED.
        assert len(base_unit_nos) == fixture.UNIT_COUNT == 50
        planted = set(
            metering_models.Unit.objects.filter(
                tenant_id=tenant.id, unit_no__in=base_unit_nos
            ).values_list("unit_no", flat=True)
        )
        assert planted == set(base_unit_nos), (
            f"the base 48 are not all on file — missing {sorted(set(base_unit_nos) - planted)}"
        )
        occupying = customers_models.Account.objects.filter(
            tenant_id=tenant.id,
            unit__unit_no__in=base_unit_nos,
            status__behavior_class__in=customers_services.OCCUPYING_BEHAVIOR_CLASSES,
        ).count()
        assert occupying == fixture.UNIT_COUNT, (
            f"acceptance item 2: the base plan must seat exactly {fixture.UNIT_COUNT} "
            f"occupying accounts and seats {occupying}"
        )
        # `SCW-U-207` — served, and deliberately vacant.
        vacant = metering_models.Unit.objects.get(tenant_id=tenant.id, unit_no="SCW-U-207")
        assert (
            customers_models.Account.objects.filter(tenant_id=tenant.id, unit=vacant).count() == 0
        ), (
            "SCW-U-207 must stay VACANT — it is what makes SR-26-0039 resolve "
            "`served_vacant`, and an account here changes a drawn decision panel"
        )
        total_units = metering_models.Unit.objects.filter(tenant_id=tenant.id).count()
        assert total_units > PACKET_UNIT_CENSUS, (
            f"DEF-941: the estate holds {total_units} units. CR-040's B4 note calls it "
            f"{PACKET_UNIT_CENSUS} with 'every seat taken' and sizes a growth task from "
            "that; a lane reading the census by hand from three modules' constants "
            "assembles the part it was pointed at"
        )
