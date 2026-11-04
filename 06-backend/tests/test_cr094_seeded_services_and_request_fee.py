# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CUS-5423 (no seeded request had any service) · DEF-RAT-5424
#          (`CC-REQFEE` existed in no tenant's catalogue and had no GL
#          mapping) · DEF-CUS-5426 (the cross-wiring took the whole state
#          chain down on a fresh tenant)
# Change:  the Product Owner, 2026-09-16: *"can you add this in seeder data"*
# Rules:   BR-CUS-1070 (each service carries its OWN requested start, and an
#          unset one means NOT GIVEN in either direction) · BR-CUS-090 (the
#          counter takes what is handed over; $25.00 of a $130.00 quote) ·
#          the PO ruling of 2026-09-15 (*"payemnt should show in payments, in
#          ledge and in fiannce books"*) · BR-RAT-024 / G47 (never a literal
#          list of the eleven services) · CLAUDE.md hard rules 1, 2, 5, 7
# ───────────────────────────────────────────────────────
"""**The demo utility's sample data can now exercise two things it could not.**

Measured on the demo tenant on 2026-09-16, before any of this moved:

  * **8 seeded service requests and ZERO rows in `service_request_services`.**
    `_drive_cr030_request` drove every other step of a request through the
    product's own service calls and never called `set_services`, so capture
    step 2 and the request's own services panel had never had anything to show.
  * **28 charge codes on the tenant and `CC-REQFEE` not one of them**, so the
    `$25.00` the counter takes against it could be held and could never be
    earned.

⚠ **THE COUNT IS THE ASSERTION, BECAUSE AN ABSENCE IS INVISIBLE TO EVERY OTHER
CHECK THIS REPO HAS.** The seeder reports every failure by name and reports
nothing at all for a call it never makes, so the log was clean, `tsc` and every
suite passed, and the screens rendered an empty panel that looks exactly like a
panel with nothing to show. That is why these cases count rows rather than
assert that the seeder ran.

PROVED RED FIRST (hard-won law 7), through `pytest`, which is the harness that
runs them. Each failure below is QUOTED from the run that produced it, with the
named thing broken and nothing else:

  1. the `sr.set_services(...)` call removed from `_drive_cr030_request` →
        E  AssertionError: the seeder wrote NO service rows at all — this is
           DEF-CUS-5423 exactly
        E  assert 0 > 0
        FAILED ...::test_the_seeder_records_services_on_the_sample_requests
  2. `_cr030_services_for` sending `"requested_start": None` instead of
     omitting the key — the fallback `BR-CUS-1070` removed →
        E  AssertionError: assert [{'code': 'wa...start': None}] ==
           [{'code': 'water'}]
        FAILED ...::test_a_service_with_no_date_sends_no_key_at_all
  3. the enabled filter dropped, so a utility is asked for services it does not
     sell →
        E  AssertionError: Brazos Bend sells electric and water; sewer and fire
           must be dropped rather than switched on to make the data look richer
        E  assert ['electric', 'sewer', 'fire'] == ['electric']
        FAILED ...::test_only_the_services_this_utility_sells_are_seeded
  4. `seed_sample_request_fee_charge_code` never called by the loader — BUILT
     AND NOT WIRED, which seeds exactly as many rows as no block at all →
        E  AssertionError: the sample loader does not create CC-REQFEE —
           DEF-RAT-5424 exactly
        FAILED ...::test_the_sample_loader_creates_the_application_fee_code_and_maps_it
  5. `CHARGE_CODE_ACCOUNTS["CC-REQFEE"]` deleted — the code is still created and
     is left pointing nowhere, which is the same hole one layer down →
        E  KeyError: 'CC-REQFEE'
        E  AssertionError: the code was created and left pointing nowhere
        E  assert None is not None  +  where None = <Charge …>.gl_account_id
        FAILED ...::test_the_application_fee_code_starts_at_connection_revenue
        FAILED ...::test_the_sample_loader_creates_the_application_fee_code_and_maps_it
  6. the fixture's two different days made one day →
        E  AssertionError: the two dates are less than a week apart, which reads
           as a typo rather than as two services genuinely wanted at different
           times
        FAILED ...::test_one_request_asks_for_two_services_on_two_different_days
        FAILED ...::test_the_seeder_records_services_on_the_sample_requests

  7. the replay's reconcile removed, so a second run walks past a request it
     already created — which is every tenant seeded before 2026-09-16 →
        E  AssertionError: a second run of the seeder left the requests it had
           already created with no services — which is exactly the state every
           tenant seeded before 2026-09-16 is in
        E  assert 0 > 0
        FAILED ...::test_a_replay_reaches_a_request_seeded_before_the_services_step
  8. that reconcile made unconditional, so it REPLACES a set that is already
     there — `set_services` deletes and recreates, so the row a person's date
     was on simply stops existing →
        E  ServiceRequestService.DoesNotExist: matching query does not exist
        FAILED ...::test_a_replay_never_replaces_services_that_are_already_there

Green over the same thirteen cases, before and after each break.

⚠ **WHAT THIS FILE CANNOT PROVE, SAID WITH A NUMBER RATHER THAN LEFT TO BE
FOUND.** `config/settings/test.py` hardcodes in-memory SQLite. The BALANCED PAIR
at the two ends of the counter fee's life is asserted by
`test_cr094_counter_receipt_posts.py`; what was walked for THIS change is the
seeded tenant end to end on real PostgreSQL 16, on a lane-owned tenant
(`laneseed-fix`) and never on the demo tenant:

    taking the cash    DR 1010 Undeposited funds          25.000000
                       CR 2400 Customer credit balances   25.000000
    approving it       DR 2400 Customer credit balances   25.000000
                       CR 4600 Connection & new-service fees 25.000000

debits equal credits at both moments, `release_error` None. The conformance
file quotes the whole run.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.customers import models as customers_models
from apps.customers import sample_data as customers_sample
from apps.ledger import chart as ledger_chart
from apps.rating import models as rating_models
from apps.rating import sample_data as rating_sample
from core import sample_fixture as fixture
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
)
from tests.test_us_met_helpers import tenant_ctx
from apps.rating.charge_prices import flat_amount as _flat  # CR-156-BRC10: the amount is a dated row

pytestmark = pytest.mark.django_db

#: The figure the PO ruled on — `BR-CUS-090`'s worked case, quoted `$130.00`,
#: `$25.00` taken at the counter on receipt `RCP-26-4471`.
APPLICATION_FEE = "25"

#: Where an application to take service starts posting. Beside `CONN`, `TAP`,
#: `TEMP-SVC` and `TRANSFER` — the category the chart already has.
CONNECTION_REVENUE = "4600"


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE FIXTURE ITSELF — read without a database, because these are claims
#     about what the demo is FOR and they must not need one
# ══════════════════════════════════════════════════════════════════════════
def test_one_request_asks_for_two_services_on_two_different_days():
    """`p076`'s own argument, and the ONLY case that proves the column is real.

    *"A block that needs electric on the 12th and sewer a fortnight later is one
    request and not two, so the date sits per service rather than once on the
    form."* Until 2026-09-15 `set_services` copied the job's date onto every
    row, so no clerk could say this and no fixture could show it.
    """
    with_two_dates = [
        entry
        for entry in fixture.CR030_SERVICE_REQUESTS
        if len({row.get("start_days") for row in (entry.get("services") or ())}) > 1
    ]
    assert with_two_dates, (
        "no seeded request asks for two services on two different days — the one "
        "case BR-CUS-1070 exists for has no example in the demo data"
    )
    offsets = sorted(
        row["start_days"]
        for row in with_two_dates[0]["services"]
        if row.get("start_days") is not None
    )
    assert offsets[-1] - offsets[0] >= 7, (
        "the two dates are less than a week apart, which reads as a typo rather "
        "than as two services genuinely wanted at different times"
    )


def test_one_request_reaches_step_two_with_no_services_at_all():
    """`count: 0` is a REAL answer and a screen has to render it.

    A request that never reached step 2 carries no services, and nothing may
    divide by that count. One of the eight is deliberately empty so the case is
    in front of whoever builds the panel.
    """
    without = [
        entry for entry in fixture.CR030_SERVICE_REQUESTS if not entry.get("services")
    ]
    assert len(without) == 1, (
        "exactly one of the eight sample requests should have no services — "
        f"found {len(without)}"
    )


def test_every_declared_service_is_a_real_catalogue_code():
    """A typo in the fixture would be reported by the seeder and seeded as
    nothing, which is the shape of absence this whole file is about."""
    from apps.tenancy import models as tenancy_models

    catalogue = set(tenancy_models.Service.objects.values_list("code", flat=True))
    declared = {
        row["code"]
        for entry in fixture.CR030_SERVICE_REQUESTS
        for row in (entry.get("services") or ())
    }
    assert declared, "no sample request declares any service"
    assert declared <= catalogue, f"not in the platform catalogue: {declared - catalogue}"


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE NARROWING — what the tenant sells, and what a missing date means
# ══════════════════════════════════════════════════════════════════════════
def _received(days_ago: int = 0) -> datetime:
    return datetime(2026, 9, 1, 9, 30, tzinfo=dt_timezone.utc) - timedelta(days=days_ago)


def test_a_service_with_no_date_sends_no_key_at_all(brazos):
    """`BR-CUS-1070`: an unset `requested_start` means *the clerk gave none*.

    It is NOT the job's `Connection date` under another name and it never falls
    back to it, in either direction — so a payload that spelled *no date* as an
    explicit `None` would be encoding the very fallback the rule removed. The
    endpoint's bare-code form means exactly this, and so does an absent key.
    """
    with tenant_ctx(brazos):
        payload = customers_sample._cr030_services_for(
            {"services": ({"code": "water"},)}, _received()
        )
    assert payload == [{"code": "water"}]
    assert "requested_start" not in payload[0]


def test_a_dated_service_counts_forward_from_the_day_it_came_in(brazos):
    """Relative, like `age_days` and `remind_on_days` beside it.

    A demo planted in March and a demo planted in November both show a
    connection date in the future; an absolute date would have rotted into the
    past and demonstrated the opposite of what the row is there to show.
    """
    received = _received()
    with tenant_ctx(brazos):
        payload = customers_sample._cr030_services_for(
            {"services": ({"code": "electric", "start_days": 21},)}, received
        )
    assert payload == [
        {
            "code": "electric",
            "requested_start": (received.date() + timedelta(days=21)).isoformat(),
        }
    ]


def test_only_the_services_this_utility_sells_are_seeded(brazos):
    """`set_services` validates against the PLATFORM catalogue — all eleven —
    so nothing in the product would have stopped the seeder asking a utility
    for a service it does not run. The narrowing is the seeder's own, read from
    `tenant_services` and never from a list of names (`BR-RAT-024`, `G47`)."""
    with tenant_ctx(brazos):
        payload = customers_sample._cr030_services_for(
            {
                "services": (
                    {"code": "electric", "start_days": 3},
                    {"code": "sewer", "start_days": 3},
                    {"code": "fire"},
                )
            },
            _received(),
        )
    assert [row["code"] for row in payload] == ["electric"], (
        "Brazos Bend sells electric and water; sewer and fire must be dropped "
        "rather than switched on to make the data look richer"
    )


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE SEEDER, RUN — the count is the assertion
# ══════════════════════════════════════════════════════════════════════════
def test_the_seeder_records_services_on_the_sample_requests(brazos, dana):
    """DEF-CUS-5423, stated as the number that was wrong.

    Before this change: 8 requests, **0** rows. The join table had never held a
    row on any tenant, which is also why `DEF-CUS-5412` — a wrong attribute name
    in the detail read — could sit there unfalsifiable for a day.
    """
    with tenant_ctx(brazos):
        customers_sample._seed_cr030_service_requests(dana)
        rows = list(
            customers_models.ServiceRequestService.objects.select_related(
                "request", "service"
            )
        )
    assert len(rows) > 0, (
        "the seeder wrote NO service rows at all — this is DEF-CUS-5423 exactly"
    )
    by_request: dict[str, list] = {}
    for row in rows:
        by_request.setdefault(str(row.request_id), []).append(row)

    # The case the rule exists for: one request, two services, two dates.
    differing = [
        rows_for
        for rows_for in by_request.values()
        if len({r.requested_start for r in rows_for}) > 1
    ]
    assert differing, (
        "every seeded request has one date across all its services — the "
        "different-dates case BR-CUS-1070 was written for is still unseeded"
    )
    dates = sorted(r.requested_start for r in differing[0] if r.requested_start)
    assert (dates[-1] - dates[0]).days >= 7

    # And the other half of p080's pair: a request whose services carry NO
    # date. All-unset must never be storable only as *agreed on nothing*.
    assert any(
        all(r.requested_start is None for r in rows_for)
        for rows_for in by_request.values()
    ), "no seeded request leaves every service undated"

    # REQ-03.3's CHECK callout: availability is settled at review, so every
    # seeded row is *not yet asked* and never *no*.
    assert {row.available for row in rows} == {None}


def test_the_seeder_asks_for_nothing_the_tenant_does_not_sell(brazos, dana):
    """The narrowing, asserted against what actually landed rather than against
    the helper — a filter that is correct and unwired seeds the same rows as no
    filter at all (hard-won law 2)."""
    with tenant_ctx(brazos):
        customers_sample._seed_cr030_service_requests(dana)
        seeded = set(
            customers_models.ServiceRequestService.objects.values_list(
                "service__code", flat=True
            )
        )
        from apps.customers import seams

        enabled = set(seams.enabled_service_codes())
    assert seeded <= enabled, f"seeded a service this utility does not run: {seeded - enabled}"


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE APPLICATION FEE — a code, and somewhere for its money to go
# ══════════════════════════════════════════════════════════════════════════
def test_the_application_fee_code_starts_at_connection_revenue():
    """DEF-RAT-5424's other half, and it is checked without a database on
    purpose: a code with a row and no mapping leaves the identical hole one
    layer down, and the mapping lives in exactly one place."""
    assert ledger_chart.CHARGE_CODE_ACCOUNTS["CC-REQFEE"] == CONNECTION_REVENUE
    seeded = {row.code for row in ledger_chart.SEED_CHART}
    assert CONNECTION_REVENUE in seeded, (
        "the map points at an account nobody seeds, which reads exactly like a "
        "correct mapping and produces exactly the same NULL column"
    )


def test_the_sample_loader_creates_the_application_fee_code_and_maps_it(
    brazos, dana
):
    """**THE WHOLE LOADER IS RUN, NOT THE ONE FUNCTION — built is not wired.**

    A block that exists and is never called seeds exactly as many rows as no
    block at all (hard-won law 2), and the mapping is a SECOND thing that can be
    missing: a code with a row and a NULL `gl_account_id` leaves the identical
    hole one layer down. So this asks the question the tenant asks — *after
    somebody presses Load sample data, can the $25.00 be earned?* — and the
    answer is a charge code pointing at a real revenue account.
    """
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        rating_sample.seed_sample_records(dana)
        row = rating_models.Charge.objects.filter(code="CC-REQFEE").first()
        assert row is not None, (
            "the sample loader does not create CC-REQFEE — DEF-RAT-5424 exactly"
        )
        assert _flat(row) == Decimal(APPLICATION_FEE)
        assert row.charge_type == "one_time"
        # `BR-RAT-117` puts a recurring auto-applied code on every ordinary
        # bill. This one is quoted on a service REQUEST and must never land on
        # a customer's monthly bill.
        assert row.auto_apply is False
        assert row.gl_account_id is not None, (
            "the code was created and left pointing nowhere, which is the same "
            "hole one layer down"
        )
        account = ledger_models.LedgerAccount.objects.get(pk=row.gl_account_id)
    assert account.code == CONNECTION_REVENUE
    assert account.type == "revenue"


def test_the_application_fee_is_created_once_and_never_overwritten(brazos, dana):
    """`BR-TEN-012` — a tenant that already has the code, because they made it
    themselves, is left entirely alone. Idempotent by natural key, like every
    other block in that module."""
    with tenant_ctx(brazos):
        assert rating_sample.seed_sample_request_fee_charge_code(dana) == 1
        assert rating_sample.seed_sample_request_fee_charge_code(dana) == 0
        assert rating_models.Charge.objects.filter(code="CC-REQFEE").count() == 1


def test_a_replay_reaches_a_request_seeded_before_the_services_step(brazos, dana):
    """The replay half of `DEF-CUS-5423`, and it is the half the demo tenant
    actually needs.

    Every tenant planted before 2026-09-16 holds eight sample requests with an
    empty services panel, and `_seed_cr030_service_requests` is idempotent PER
    REQUEST — so without a reconcile, pressing *Load sample data* again walks
    straight past them and the demo the Product Owner reviews screens on never
    shows the thing they asked for. `DEF-1250` is the same shape one module
    over.
    """
    with tenant_ctx(brazos):
        customers_sample._seed_cr030_service_requests(dana)
        customers_models.ServiceRequestService.objects.all().delete()
        assert customers_models.ServiceRequestService.objects.count() == 0

        customers_sample._seed_cr030_service_requests(dana)
        after = customers_models.ServiceRequestService.objects.count()
    assert after > 0, (
        "a second run of the seeder left the requests it had already created "
        "with no services — which is exactly the state every tenant seeded "
        "before 2026-09-16 is in"
    )


def test_a_replay_never_replaces_services_that_are_already_there(brazos, dana):
    """`set_services` REPLACES the set, so a reconcile that ran unconditionally
    would overwrite a date somebody typed while demonstrating the screen. The
    only state it acts on is *no rows at all* — `apply_default_gl_accounts`'
    rule one module over: fill an absence, never replace an answer."""
    from datetime import date

    with tenant_ctx(brazos):
        customers_sample._seed_cr030_service_requests(dana)
        row = customers_models.ServiceRequestService.objects.first()
        assert row is not None
        typed = date(2027, 3, 9)
        customers_models.ServiceRequestService.objects.filter(pk=row.pk).update(
            requested_start=typed
        )

        customers_sample._seed_cr030_service_requests(dana)
        row.refresh_from_db()
    assert row.requested_start == typed, (
        "the seeder overwrote a date already on the request — a fixture must "
        "never undo a person"
    )
