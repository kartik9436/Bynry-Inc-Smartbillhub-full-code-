# ── Trace ──────────────────────────────────────────────
# Rules:    BR-MET-106 (a month's usage is Σ consumption per ACCOUNT per
#           service) · B2 §2 (meter_reads.account_id, a reviewed cross-module
#           FK) · B1 module map (metering reaches customers only via seams)
# ───────────────────────────────────────────────────────
"""DEF-658 — a committed read must carry the account it was taken for.

WHAT WAS WRONG, AND IT WAS AN ABSENCE RATHER THAN A BUG. `meter_reads.
account_id` has existed since the table did, and NOTHING EVER WROTE IT. Every
read in every seeded database carried NULL. `monthly_usage_service._read_facts`
filters on exactly that column, so BR-MET-106's Usage tab — ruled by the PO on
the morning of 2026-08-24 and built the same day — could never populate for any
account, seeded or real. Measured on four seeded databases: `0 with account_id`
in every one.

Hard-won law 2, in its purest form: *"a component with an optional prop that
nothing passes is dead UI: it renders nothing, every test passes, and the
feature does not exist."* The column is nullable, so nothing complained; the
chart drew its empty state, which is indistinguishable from an account that has
no reads.

⚠ WHY EVERY EXISTING TEST PASSED OVER IT, WHICH IS THE PART WORTH REMEMBERING.
`tests/test_br_met_106_monthly_usage._read` and
`tests/test_us_met_reads_helpers.commit_read` both write the row DIRECTLY, each
with a docstring that reasonably explains why (*"building each row through the
five-step import wizard would make the fixture, not the behaviour, the thing
under test"*). That is a fair call for testing the GROUPING, and both helpers
pass `account_id=` by hand. So every test of BR-MET-106 supplied the one value
production never supplied at all: a green suite proved the arithmetic and said
nothing whatever about whether its input existed.

SO THIS FILE DELIBERATELY USES NEITHER HELPER. It drives the real S28 pipeline
— stage → validate → commit — and then asks the committed row what it carries.
That is the only question the other suites could not ask.
"""

import pytest

from apps.customers import services as customers_services
from apps.metering import models, services
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests import identity_fixtures
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    accept_warnings,
    csv_body,
    make_premises,
    make_unit,
    seed_config,
    stage,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _published_plan(tenant, service_code="electric", name="Small Commercial"):
    """A published plan for the service — activation refuses without one.

    Same shape as `tests/test_br_met_106_monthly_usage._plan`, and it is here
    for a reason worth stating: `activate_account` raises
    `customers.account.plan_required_at_activation`, so an account cannot BE
    the unit's occupant until the unit is priced. That is a real ordering
    constraint in the product, not fixture noise, and a test that skipped it
    would be testing a state a utility can never reach.
    """
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"{name} — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _account_on_a_unit(actor, tenant, *, service="electric", label="Unit A"):
    """One real account on one real unit, through the real services.

    Copied in shape from `tests/test_br_met_106_monthly_usage._account_on` — the
    same state J2 leaves behind — because this file must build its fixture the
    long way round. The whole point of DEF-658 is that the SHORT way (writing
    `account_id=` on the row) is what hid the defect.
    """
    premises = make_premises(actor)
    unit = make_unit(actor, premises["id"], label=label, services=[service])
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_published_plan(tenant, service).id)}
    )
    metering_services.ensure_service_point(unit["id"], service)
    account = customers_services.create_account(
        actor,
        {
            "unit_id": unit["id"],
            "account_type": "residential",
            "opened_at": "2024-01-05",
            "contact": {"full_name": "Elena Rivera", "email": "elena@example.test"},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(
                "Elena Rivera", account_type="residential"
            ),
        },
    )
    # ⚠ ACTIVATION IS NOT OPTIONAL HERE, AND FINDING OUT WHY IS HALF THE POINT.
    # `create_account` opens at `pending_activation`, whose behaviour class is
    # `non_billable`, and BR-CUS-018 (CONFIRMED) says a draft/pending account
    # "never derives occupancy and does not block the unit for other move-ins".
    # So `active_account_for_unit` correctly returns None for it, and a read
    # taken then is a read on a unit nobody is on supply at.
    #
    # That is the RIGHT answer and it is why the stamp uses the OCCUPYING
    # account rather than any account on the unit: the read is stamped with who
    # is on supply, which is the same boundary billing keys off (BR-CUS-055 —
    # the CLASS, never the label).
    customers_services.activate_account(actor, account["id"])
    return account, unit["id"]


def _commit_one(actor, asset_no="M-7001", day="2026-08-03", value="42864"):
    """Stage → validate → accept warnings → commit. The REAL S28 pipeline.

    ⚠ `accept_warnings` is not incidental. A first read on a meter warns, and a
    read on a unit with no active account warns `vacant_unit` (BR-MET-052), and
    BR-MET-015 refuses to post a warned row without an explicit, reasoned
    disposition. Skipping this step makes `commit_read_batch` report the batch
    `posted` with `posted_reads: 0`, which is how this file first failed.
    """
    batch = stage(actor, csv_body(f"{asset_no},{day},{value},total,E,"))
    services.validate_read_batch(actor, batch["id"])
    accept_warnings(actor, batch["id"])
    result = services.commit_read_batch(actor, batch["id"], {"certified": True})
    assert result["posted_reads"] == 1, result
    return models.MeterRead.objects.filter(lifecycle="committed").order_by("-read_at").first()


def test_def658__a_read_on_an_occupied_unit_carries_that_unit_s_account(brazos, marcus):
    """THE REGRESSION GUARD. Before the fix this read committed with account_id
    NULL and BR-MET-106 had nothing to group."""
    with tenant_ctx(brazos):
        seed_config()
        account, unit_id = _account_on_a_unit(marcus, brazos)
        a_meter(marcus, "M-7001", unit_id=unit_id)
        read = _commit_one(marcus)

    assert read is not None
    assert read.account_id is not None, (
        "DEF-658: the committed read carries no account, so BR-MET-106's Usage "
        "tab can never group it"
    )
    assert str(read.account_id) == str(account["id"])


def test_def658__the_usage_read_model_can_now_actually_see_it(brazos, marcus):
    """The end the defect was reported from: the read reaches `_read_facts`.

    Asserting the column is set is not enough — the column exists to be
    FILTERED ON, and the filter lives in another module's read model. This asks
    the question the Usage tab asks.
    """
    with tenant_ctx(brazos):
        seed_config()
        account, unit_id = _account_on_a_unit(marcus, brazos)
        a_meter(marcus, "M-7001", unit_id=unit_id)
        _commit_one(marcus)
        visible = models.MeterRead.objects.filter(
            tenant_id=brazos.id, account_id=account["id"]
        ).count()

    assert visible == 1, "the read is invisible to every query BR-MET-106 makes"


def test_def658__a_vacant_unit_still_commits_its_read_with_no_account(brazos, marcus):
    """⚠ NULL IS LAWFUL AND MUST STAY LAWFUL — this is not "always resolve".

    A meter on a unit nobody has taken service at genuinely has no account. The
    read still COMMITS: refusing one because the unit is empty would stop a
    utility recording a vacancy read, which BR-MET-036's derived occupancy
    depends on. The column is nullable for exactly this case.
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")  # its own premise and unit, no account
        read = _commit_one(marcus)

    assert read is not None
    assert read.account_id is None


def test_def658__the_stamp_is_STORED_on_the_row_and_not_joined_at_read_time(brazos, marcus):
    """The semantic, and the reason it mirrors `collection_route_id`.

    A read belongs to whoever was on supply the day it was taken. A later
    move-out must not retroactively reassign a year of history to nobody, and a
    new occupant must not inherit the previous one's consumption — which is what
    a JOIN-at-read-time would do, and what the `(tenant, account, read_at)`
    index is shaped against.
    """
    with tenant_ctx(brazos):
        seed_config()
        account, unit_id = _account_on_a_unit(marcus, brazos)
        a_meter(marcus, "M-7001", unit_id=unit_id)
        read = _commit_one(marcus)
        stamped = read.account_id
        stored = (
            models.MeterRead.objects.filter(id=read.id).values_list("account_id", flat=True).first()
        )

    assert stamped is not None
    assert str(stored) == str(account["id"]), (
        "the account must be a COLUMN on the row, not a join resolved when the "
        "chart is drawn — a later move-out would otherwise reassign a year of "
        "history to whoever holds the unit next"
    )
