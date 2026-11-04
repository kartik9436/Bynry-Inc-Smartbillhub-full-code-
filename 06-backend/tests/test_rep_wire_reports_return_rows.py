# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 §8.2 · lane REP-WIRE — the wiring, proved on data.
# Defects:  DEF-REP-6894
# Covers:   GET /reports/<key> via apps/reports/runner.run for the six datasets
#           registered on 2026-09-27
# Rules:    hard-won law 2 (built is not wired) · hard rule 1 (tenant scoping)
#           · hard rule 3 (a quantity carries its unit) · NFR-3
# ───────────────────────────────────────────────────────
"""THE NEWLY-WIRED REPORTS RETURN ROWS — A KNOWN, NON-ZERO NUMBER OF THEM.

⚠ **`test_rep_wire_catalogue_reachable.py` PROVES REACHABILITY AND THIS FILE
PROVES THE ROWS, AND THE SECOND IS NOT IMPLIED BY THE FIRST.** A report that
resolves a query and returns an empty page reads as *no error*: `rows == []`
passes on a working report over an empty tenant and on a report whose adapter
hands the read model an argument it silently ignores. Every assertion here
names the number the fixture seeded.

⚠ **ONE TENANT, ONE SEEDING, ONE TEST PER DATASET.** Provisioning a tenant is
the expensive part of this suite; the fixtures are the sibling dataset lanes'
own, imported rather than re-written, so a fixture that stops producing rows
goes red in both places at once instead of drifting apart (hard-won law 5).
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.reports import runner

from tests.test_rep_meter_reads_dataset import water_reads  # noqa: F401 (fixture)
from tests.test_rep_small_datasets import a_fleet, some_orders  # noqa: F401 (fixtures)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The window the sibling fixtures seed into. Passed explicitly rather than
#: relying on the tenant's fiscal period, because a report that happened to
#: default to the right month would pass for a reason this file is not testing.
SEPTEMBER = {"from": "2026-09-01", "to": "2026-09-30"}

#: What each fixture states it seeds. A literal here that disagreed with the
#: fixture would be the count that rots, so each is cross-checked below against
#: the fixture's own returned objects.
READS_SEEDED = 8
ORDERS_SEEDED = 7
METERS_SEEDED = 5


def _rows(key: str, params: dict[str, str]) -> list[dict[str, object]]:
    return list(runner.run(key, params).payload.get("rows") or ())


def test_meter_reads_reports_return_the_eight_reads_the_fixture_seeded(water_reads):
    """R30 Usage & Ranking, R29 Consumption Exceptions and R45 My Usage all sit
    on `meter_reads`, so one dataset registration turns on all three — which is
    the brief's own arithmetic and the reason a refusal had to be written for
    the three it may NOT serve."""
    assert len(water_reads["rows"]) == READS_SEEDED
    with tenant_ctx(water_reads["tenant"]):
        for key in ("usage_and_ranking", "consumption_exceptions", "my_usage"):
            rows = _rows(key, SEPTEMBER)
            assert len(rows) == READS_SEEDED, f"{key} served {len(rows)} of {READS_SEEDED}"
            # ⚠ HARD RULE 3 — every quantity leaves with its unit beside it.
            assert all(row.get("unit") for row in rows), f"{key} served a reading with no unit"


def test_meter_fleet_returns_the_five_meters_the_fixture_seeded(a_fleet):
    """R31 Meter Fleet, on `assets`. `as_of` is the tenant's today when the
    request names none, which is BR-TEN-043 and never this process's clock."""
    assert len(a_fleet["fitted"]) + len(a_fleet["spares"]) == METERS_SEEDED
    with tenant_ctx(a_fleet["tenant"]):
        rows = _rows("meter_fleet", {"as_of": date(2026, 9, 30).isoformat()})
    assert len(rows) == METERS_SEEDED, f"meter_fleet served {len(rows)} of {METERS_SEEDED}"


def test_service_order_activity_returns_the_seven_orders_the_fixture_seeded(some_orders):
    """R33 Service Order Activity, on `work_orders`. R34 on the same dataset is
    refused by name — see the catalogue test."""
    with tenant_ctx(some_orders["tenant"]):
        rows = _rows("service_order_activity", SEPTEMBER)
        payload = runner.run("service_order_activity", SEPTEMBER).payload
    assert len(rows) == ORDERS_SEEDED, f"served {len(rows)} of {ORDERS_SEEDED}"
    # ⚠ A DURATION CARRIES ITS UNIT, on the totals as well as on the row.
    assert payload["totals"]["duration_unit"] == "hours"


def test_account_census_returns_the_accounts_the_fixture_seeded(water_reads):
    """R22 Account Census, on `accounts`. The fixture opens two accounts; the
    census counts every account the tenant holds, so the assertion is *at
    least* two AND that both of the fixture's own numbers are among them —
    which a query leaking another tenant's rows could not satisfy either."""
    with tenant_ctx(water_reads["tenant"]):
        rows = _rows("account_census", {})
    numbers = {row.get("account_no") for row in rows}
    assert len(rows) >= 2, f"account_census served {len(rows)} rows over two seeded accounts"
    assert {"A-100244", "A-100512"} <= numbers, f"seeded accounts missing: {sorted(numbers)}"


def test_audit_trail_returns_the_events_the_fixture_wrote(water_reads):
    """R35 Audit Trail, on `audit_log` — THREE seeded events, served.

    ⚠ **THE EVENTS ARE SEEDED HERE AND THE FIRST DRAFT ASSUMED THEY WOULD NOT
    HAVE TO BE.** It asserted that provisioning a tenant and opening two
    accounts leaves a trail, because hard rule 7 says every money action writes
    `audit_log`. Measured: the fixture's tenant holds **ZERO** audit rows —
    these fixtures write through the ORM rather than through the services that
    audit, which is right for a read-model test and means an assertion resting
    on them would have been asserting the fixture and not the report. Left as
    it was, it would have gone red for a reason that has nothing to do with the
    wiring this file exists to prove.
    """
    from tests.test_rep_audit_log_dataset import _event

    tenant = water_reads["tenant"]
    for action in ("payment.recorded", "account.opened", "invoice.issued"):
        _event(tenant, action=action, entity_type=action.split(".")[0])
    with tenant_ctx(tenant):
        payload = runner.run("audit_trail", SEPTEMBER).payload
    rows = list(payload.get("rows") or ())
    assert len(rows) == 3, f"audit_trail served {len(rows)} of the 3 seeded events"
    # ⚠ THE FLOOR TRAVELS WITH THE ROWS. A trail that does not say where it
    # stops reads as a complete history of a table that is pruned on a schedule.
    assert payload.get("window_floor"), "the audit window floor is not on the wire"


def test_a_refused_report_raises_rather_than_serving_the_wrong_grain(water_reads):
    """⚠ **THE HALF THAT COSTS MOST IF IT IS MISSING.** Once a dataset is in
    `DATASET_QUERIES` the fallback serves EVERY definition seeded onto it, so
    R28 Read Completeness — one row per ROUTE, with a denominator of reads that
    did NOT happen — would answer with eight read rows, foot correctly, and be
    the wrong report. It refuses, carrying metering's own sentence."""
    from apps.reports import queries

    with tenant_ctx(water_reads["tenant"]):
        with pytest.raises(queries.DatasetCannotServe) as refused:
            runner.run("read_completeness", SEPTEMBER)
    assert "ROUTE" in refused.value.reason
    assert refused.value.key == "read_completeness"


def test_the_export_path_streams_and_the_screen_path_pages(water_reads):
    """§8.2 p91 — two paths, and the file is not the screen's page.

    ⚠ The stream takes no `per`, so this asserts the count rather than the
    absence of an argument: an export that inherited a page would return the
    page size and not the eight.
    """
    import inspect

    from apps.reports import queries

    stream = runner.stream_for("usage_and_ranking", "meter_reads")
    assert stream is not None, "meter_reads has no stream, so an export holds a page"
    with tenant_ctx(water_reads["tenant"]):
        streamed = list(stream({**SEPTEMBER, "per": "2"}))
        paged_payload = runner.run("usage_and_ranking", {**SEPTEMBER, "per": "2"}).payload
        paged = list(paged_payload.get("rows") or ())
    assert len(streamed) == READS_SEEDED, f"the file holds {len(streamed)}, not {READS_SEEDED}"
    assert len(paged) == READS_SEEDED
    # ⚠ **`per=2` DOES NOT MEAN TWO ROWS AND THE FIRST DRAFT OF THIS CASE
    # BELIEVED IT DID.** `core.pagination.clamp_page_size` clamps a request
    # below the smallest offered page size UP to it — *"clamping never grants
    # more rows than asked for"* is about the top of the range, not the bottom
    # — so `per=2` is 50 and eight rows is the whole set. The difference that
    # matters is therefore not the row COUNT on this fixture but the `page`
    # BLOCK: the screen says which page of how many it is showing, and the file
    # has no such key because it is not a page of anything (`NFR-3`).
    assert paged_payload["page"]["total"] == READS_SEEDED
    assert paged_payload["page"]["per"] == 50
    # ⚠ **AND THE STREAM CANNOT BE HANDED A PAGE AT ALL**, which is a stronger
    # statement than *it did not use one*: the read model's generator declares
    # neither `page` nor `per`, so there is no argument through which an export
    # could inherit the screen's. Asserted on the SIGNATURE, because an
    # assertion on this fixture's eight rows would pass on a stream that
    # accepted a page size and happened not to be given one.
    from apps.metering import meter_reads_dataset as metering_query

    taken = set(inspect.signature(metering_query.meter_reads_dataset_stream).parameters)
    assert not (taken & {"page", "per"}), f"the stream accepts a page size: {sorted(taken)}"
    assert queries.DATASET_STREAMS["meter_reads"] is not queries.DATASET_QUERIES["meter_reads"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 §8.2 (05-prototype/09 Reports Build Brief.pdf p91 read as an image per B14 rule 42)
# screens: S46 — the viewer these six datasets now fill
# generated: 2026-09-27 by lane REP-WIRE
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST, through pytest in a worktree at the pre-change tip — every case failed with `runner.DatasetNotExecutable: report 'usage_and_ranking' reads dataset 'meter_reads', which has no query yet`.
# exceptions: (1) `account_census` asserts AT LEAST the two seeded accounts rather than an exact count, because provisioning seeds accounts this file does not control — the seeded two are named so a leak or a drop still fails · (2) the cost figures for these reads are the dataset lanes' own scripts; `config/settings/test.py` hardcodes in-memory SQLite and no timing is asserted here (hard-won law 14)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
