# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 Amendment 2 · W9 tasks 1 and 3–8 — EVENT READS: the metering
#           write door (`services.commit_event_reads`), the five wizard events
#           that carry readings through it, and the estimated fallback.
# Story:    US-CUS-004 (move-in) · US-CUS-005 (move-out) · US-CUS-030 (the
#           disconnect wizard) · US-MET-014 (estimation) · ⚠ NO STORY OWNS the
#           transfer and new-connect read capture (hard-won law 8) — OWED, and
#           REPORTED rather than invented here.
# Rules:    **BR-MET-128** (PO 2026-08-26, verbatim: *"it will be as per event -
#           bascially we will ahve to create an record in reading that such
#           reading ahs been colelcted - and it is generated due to that event;
#           + plus the user"* — the event AND the user on the read, ONE read
#           serving both sides of a transfer) · **BR-MET-129** (PO 2026-08-26,
#           verbatim: *"No if reading are colelcted we have to store the
#           reading, we can give the warning, but we cannot reject the reading
#           … there can be fraud also by people"* — warnings POST flagged, only
#           ERRORS refuse) · **BR-CUS-021** (reads commit through metering's own
#           append-only service) · **BR-MET-110** (*"utility staff will review
#           these work order, accept them and use data from them to activate
#           these services"*) · BR-MET-026/027/028/058 (estimation: method,
#           consecutive cap, that channel's OWN history, no register value) ·
#           BR-MET-016/017/053 (append-only) · BR-CUS-030 (`closed_at` IS the
#           move-out date) · BR-SHL-019 (ONE transactional commit) ·
#           CLAUDE.md hard rule 3 (an explicit unit, always) · rule 4 · rule 7
# Design:   12-governance/11-change-requests.md CR-038 Amendment 2 — "W9 — event
#           reads (8 tasks)"; each task's own sentence is quoted in the case
#           that proves it.
# Tests:    this file. RED-first proofs are quoted VERBATIM in the docstrings
#           (hard-won law 7).
# Impacts:  apps/metering/models.py (EVENT_CONTEXTS · meter_reads.event_context
#           · read_import_batches.event_context — migration 0032) ·
#           apps/metering/services.py (commit_event_reads · _post_row's stamp ·
#           estimate_missing_read's event path) · apps/metering/selectors.py
#           (read_dict serves event_context + imported_by) ·
#           apps/metering/connections.py (accept_field_result posts set_reads) ·
#           apps/customers/seams.py (commit_event_reads — B2 §2 row OWED) ·
#           apps/customers/services.py (move_in · move_out · _final_read_state ·
#           accounts.final_read_state — migration 0026) ·
#           apps/customers/transfers.py (ONE read) · apps/customers/disconnects.py
# ───────────────────────────────────────────────────────
"""CR-038 W9 — event reads, end to end.

The principle CR-038 Amendment 2 states for this whole wave, verbatim:
*"an event read is an ORDINARY committed read — same pipeline, same 16 rules,
plus a context it carries."*

§1 proves the DOOR (the stamp, the shared pipeline, BR-MET-129's two halves,
the estimated fallback and what it refuses). §2 proves the FIVE EVENTS that
carry readings through it.
"""

from datetime import date
from decimal import Decimal

import pytest

from tests.test_us_met_helpers import field_close  # CR-168 P1.34 — close as the field

from apps.customers import disconnects
from apps.customers import models as customers_models
from apps.customers import move_reads
from apps.customers import seams as customers_seams
from apps.customers import services as customers_services
from apps.customers import transfers
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors
from apps.metering import services as metering_services
from core import errors

from tests import identity_fixtures
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    commit_read,
    make_premises,
    make_unit,
    seed_config,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: The W5/W9 worklist clock, reused so all three files read one calendar.
TODAY = date(2026, 8, 25)


# ════════════════════════════════════════════════════════════════════════════
# FIXTURE PLUMBING — real rows through real services (DEF-658). Committed
# HISTORY alone is written directly, for the reason `commit_read`'s own
# docstring gives: those rows are the past a case starts from.
# ════════════════════════════════════════════════════════════════════════════
def _plan(tenant, service_code="electric"):
    """A published plan so an ACTIVE account can exist (BR-MET-040)."""
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant, name="W9 Events", defaults={"code": "w9-events", "status": "published"}
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"W9 Events — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _metered_unit(admin, tenant, *, label="Unit A", meters=(("M-9101", "electric", "kWh"),)):
    """One unit holding real meters, through the real services."""
    services = sorted({service for _no, service, _uom in meters}) or ["electric"]
    premises = make_premises(admin, services_available=services)
    unit = make_unit(admin, premises["id"], label=label, services=services)
    metering_services.assign_unit_plan(admin, unit["id"], {"tariff_id": str(_plan(tenant).id)})
    for asset_no, service, uom in meters:
        a_meter(admin, asset_no, unit_id=unit["id"], service=service, uom=uom)
    return unit


def _asset_id(unit, asset_no):
    """The fixture's meter id, read back through the published assets seam so
    the test never touches the assets ORM either (the W9-seam file's helper)."""
    from apps.metering import seams as metering_seams

    for row in metering_seams.assets_on_unit(unit["id"]):
        if row["asset_no"] == asset_no:
            return row["id"]
    raise AssertionError(f"{asset_no} is not assigned to this unit")


def _account_on(clerk, unit_id, *, name, opened_at="2026-07-01"):
    """One account through `services.create_account` — the one door."""
    return customers_services.create_account(
        clerk,
        {
            "unit_id": str(unit_id),
            "account_type": "residential",
            "status": "active",
            "opened_at": opened_at,
            "contact": {"full_name": name},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
        },
    )


def _head(asset_id, channel="total"):
    """The committed lineage HEAD for one register (BR-MET-016/053)."""
    return (
        metering_models.MeterRead.objects.filter(
            asset_id=asset_id, channel=channel, superseded_by_id__isnull=True
        )
        .order_by("-read_at")
        .first()
    )


def _scheduled_cut(actor, account_id, monkeypatch):
    """A disconnect case SCHEDULED for the cut.

    `commit_cut` re-runs four preconditions that are W7's own subject and not
    this lane's (still running · cut reachable · service proved · a priced
    reconnection fee — DEF-700: no seed creates `CC-RECON`, so on every tenant
    in this tree the fee genuinely is absent). Each is stubbed by NAME so a
    reader can see exactly which guard was set aside and that none of them is
    about reads.
    """
    monkeypatch.setattr(disconnects, "_require_running", lambda *_a, **_k: None)
    monkeypatch.setattr(disconnects, "assert_cut_reachable", lambda *_a, **_k: None)
    monkeypatch.setattr(disconnects, "assert_service_proved", lambda *_a, **_k: None)
    monkeypatch.setattr(
        disconnects,
        "reconnection_terms",
        lambda *_a, **_k: {"fee": {"stored": "75.0000", "display": "75.00"}, "fee_absence": None},
    )
    return disconnects.DisconnectCase.objects.create(
        tenant_id=disconnects._tenant_id(),
        account_id=account_id,
        state=disconnects.STATE_SCHEDULED,
        opened_on=date(2026, 8, 1),
        cut_scheduled_for=date(2026, 8, 24),
        services_cut=["electric"],
        amount_owed_at_open=Decimal("612.7500"),
        currency="USD",
    )


# ════════════════════════════════════════════════════════════════════════════
# 1 · THE DOOR — `apps.metering.services.commit_event_reads` (task 1)
# ════════════════════════════════════════════════════════════════════════════
def test_w9_door__the_read_carries_its_event_and_its_user(brazos, dana):
    """**BR-MET-128, both halves, on the committed row.**

    PO 2026-08-26, verbatim: *"it will be as per event - bascially we will ahve
    to create an record in reading that such reading ahs been colelcted - and it
    is generated due to that event; + plus the user"*.

    So `event_context` is the event, `imported_by` is the person who collected
    it, both are on the COMMITTED read — not on a batch a consumer would have
    to join to — and both render on the read detail (`selectors.read_dict`),
    which is where the rule says they must appear.
    """
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        asset_id = _asset_id(unit, "M-9101")
        _account_on(dana, unit["id"], name="Rivera, Ana")

        answer = metering_services.commit_event_reads(
            dana,
            {
                "event": "move_in",
                "reads": [{"meter_no": "M-9101", "read_at": "2026-08-20", "value": "43566"}],
            },
        )

        read = _head(asset_id)
        detail = metering_selectors.read_dict(read)

    assert answer["posted_reads"] == 1
    assert answer["event"] == "move_in"
    # (a) THE EVENT, on the read itself.
    assert read.event_context == "move_in"
    # (b) THE USER — the person who committed the wizard.
    assert read.imported_by_id == dana.id
    # Both on the DETAIL, which is what the rule requires.
    assert detail["event_context"] == "move_in"
    assert detail["imported_by"] == str(dana.id)


def test_w9_door__an_event_read_is_an_ordinary_read_through_the_same_pipeline(brazos, dana):
    """**CR-038 Amendment 2's W9 principle, verbatim:** *"an event read is an
    ORDINARY committed read — same pipeline, same 16 rules, plus a context it
    carries."*

    The proof is that nothing about the row is special: `source="manual"` (the
    S28 typed-entry shape, not a new source word), `lifecycle="committed"`, the
    consumption came off the SAME validation engine against the same prior
    head, and it carries its explicit unit (hard rule 3). Only the context is
    new.

    EP-MET-03's Brazos Bend figure: 42,864 − 42,180 = **684.000000 kWh**.
    """
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        asset_id = _asset_id(unit, "M-9101")
        _account_on(dana, unit["id"], name="Booth, Clara")
        commit_read(dana, asset_id, day="2026-06-30", value="42180")

        metering_services.commit_event_reads(
            dana,
            {
                "event": "move_out",
                "reads": [{"meter_no": "M-9101", "read_at": "2026-07-31", "value": "42864"}],
            },
        )
        read = _head(asset_id)

    assert read.source == "manual"  # the typed-entry shape, not a new source
    assert read.lifecycle == "committed"
    assert read.current_value == Decimal("42864")
    assert read.prior_value == Decimal("42180")
    assert read.consumption == Decimal("684.000000")  # the engine's, not the door's
    assert read.unit == "kWh"  # rule 3 — never separated from the number
    assert read.import_batch_id is not None, "a real batch, not a shortcut around the pipeline"


def test_w9_door__a_warned_reading_posts_with_its_flags(brazos, dana):
    """**BR-MET-129 (1) — A WARNED READING POSTS.**

    PO 2026-08-26, verbatim: *"No if reading are colelcted we have to store the
    reading, we can give the warning, but we cannot reject the reading, when
    reading are colelcted then only we will know whether there is usage or not;
    otherwise, just tagging vacant and customer using utility services - never
    will be captured - there can be fraud also by people"*.

    The vacant-unit case IS the PO's own example, and it is the case here: no
    account occupies this unit, so BR-MET-052 warns `vacant_unit` — and the
    reading LANDS, with its flag attached to the committed row, for a person to
    work afterwards. Under BR-MET-015's superseded half this read would have
    been held out of the product until somebody dispositioned it.
    """
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        asset_id = _asset_id(unit, "M-9101")  # NO account — the unit is vacant

        answer = metering_services.commit_event_reads(
            dana,
            {
                "event": "new_connect",
                "reads": [{"meter_no": "M-9101", "read_at": "2026-08-20", "value": "100"}],
            },
        )
        read = _head(asset_id)

    assert answer["posted_reads"] == 1, "a warning NEVER holds a collected reading out"
    assert read.event_context == "new_connect"
    # The flags travel ONTO the committed read — worked after commit, not before.
    flagged = [o for o in (read.rule_outcomes or []) if o.get("severity") == "warning"]
    assert any(o["rule"] == "vacant_unit" for o in flagged), read.rule_outcomes
    # And the door reports them, so a caller can show what posted flagged.
    assert answer["warnings"][0]["meter_no"] == "M-9101"
    assert any(r["rule"] == "vacant_unit" for r in answer["warnings"][0]["rules"])


def test_w9_door__an_error_refuses_with_named_rows_and_nothing_persists(brazos, dana):
    """**BR-MET-129 (2) — ERRORS still refuse, and the refusal NAMES the rows.**

    BR-MET-015's error half stands unchanged. The second claim earns its own
    assertions: the whole door runs in ONE transaction, so a refused batch
    leaves **no debris** — no `read_import_batches` row, no staged rows, no
    reads. A door that left a half-staged batch behind would put a phantom into
    the Reads wizard that nobody could explain and nothing would clean up.
    """
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        _account_on(dana, unit["id"], name="Nkemelu, Ify")
        batches_before = metering_models.ReadImportBatch.objects.count()
        reads_before = metering_models.MeterRead.objects.count()

        with pytest.raises(errors.BizError) as raised:
            metering_services.commit_event_reads(
                dana,
                {
                    "event": "move_in",
                    "reads": [
                        {"meter_no": "M-9101", "read_at": "2026-08-20", "value": "500"},
                        {"meter_no": "M-NOPE", "read_at": "2026-08-20", "value": "700"},
                    ],
                },
            )

        assert metering_models.ReadImportBatch.objects.count() == batches_before
        assert metering_models.MeterRead.objects.count() == reads_before

    assert raised.value.br_ref == "BR-MET-129"
    named = raised.value.params["rows"]
    assert [row["meter_no"] for row in named] == ["M-NOPE"], "the FAILING row is named"
    assert any(rule["rule"] == "unknown_meter" for rule in named[0]["rules"])


def test_w9_door__the_event_vocabulary_is_the_five_and_a_sixth_is_refused(brazos, dana):
    """**BR-MET-128's vocabulary is CLOSED: one context per wizard event** —
    move_in · move_out · transfer · disconnect · new_connect — **plus three
    appended 2026-10-17** (`DEF-WRK-10184`, PO: field readings are saved with
    *"the job's real event type"*): reconnect · meter_read · exchange.
    Still closed: `meter_change` is not one of them and is refused.

    A word outside that set is refused rather than stored: an unrecognised
    context is a read whose provenance nothing downstream can group, and the
    prime directive forbids answering an unruled question by choosing a value.
    """
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        _account_on(dana, unit["id"], name="Halvorsen, Nils")

        with pytest.raises(errors.ValidationError) as raised:
            metering_services.commit_event_reads(
                dana,
                {
                    "event": "meter_change",  # a real job — and NOT one of the eight
                    "reads": [{"meter_no": "M-9101", "read_at": "2026-08-20", "value": "9"}],
                },
            )

    assert metering_models.EVENT_CONTEXTS == (
        "move_in",
        "move_out",
        "transfer",
        "disconnect",
        "new_connect",
        "reconnect",
        "meter_read",
        "exchange",
    )
    assert raised.value.field_errors[0]["field"] == "event"


def test_w9_door__task_8_a_missing_read_is_estimated_disclosed_and_capped(brazos, dana):
    """**TASK 8, verbatim:** *"Estimated-final path: a missing event read routes
    through F6 estimation, disclosed, capped — never a silent zero."*

    A meter that cannot be read carries `estimate: true` INSTEAD of a value and
    the existing US-MET-014 engine answers: the trailing-3 daily average over
    that channel's OWN actual history (BR-MET-058), the method and the
    consecutive number DISCLOSED on the row, `current_value` NULL because
    BR-MET-028 says an estimate carries no register reading — and the event
    stamped, because an estimated event read was still generated by its event.

    The figure: 300 kWh over 30 days and 300 over 31 = 600 ÷ 61 = 9.836065573…
    kWh/day, and the 31 days to 2026-08-31 estimate **304.918033 kWh**. Not a
    round number, and that is the point: it is the engine's arithmetic, not a
    figure this door chose.

    ⚠ **THE PINNED FIGURE WAS AMENDED 2026-08-26, AND THE ENGINE WAS RIGHT.**
    This case first pinned `304.918015`, which is 600 ÷ 61 rounded to six places
    (9.836065) and THEN multiplied by 31. `estimation.estimate` keeps the daily
    average at full Decimal precision and quantizes only the PRODUCT — the same
    order GT-9's fixture uses — so the answer is 9.836065573770491803… × 31 =
    304.9180327868… → `304.918033`. RED-FIRST PROOF, verbatim, before the
    expectation moved:

        AssertionError: assert Decimal('304.918033') == Decimal('304.918015')

    The assertion moved because the TEST's arithmetic was wrong, never the
    engine's: nothing in `apps/metering/estimation.py` changed for this line,
    and rounding a rate before multiplying it would be the round-early error
    B4 forbids on the money side for exactly this reason.
    """
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        asset_id = _asset_id(unit, "M-9101")
        _account_on(dana, unit["id"], name="Osei, Kwame")
        commit_read(
            dana, asset_id, day="2026-06-30", value="1000",
            consumption="300.000000", days_since_prior=30,
        )
        commit_read(
            dana, asset_id, day="2026-07-31", value="1300", prior_value="1000",
            consumption="300.000000", days_since_prior=31,
        )

        answer = metering_services.commit_event_reads(
            dana,
            {
                "event": "move_out",
                "reads": [{"meter_no": "M-9101", "read_at": "2026-08-31", "estimate": True}],
            },
        )
        estimated = _head(asset_id)

    assert answer["posted_reads"] == 0, "an estimate is not a keyed reading"
    row = answer["estimates"][0]
    assert row["estimated"] is True
    assert row["meter_no"] == "M-9101"
    # DISCLOSED — which method, and which consecutive estimate this is.
    assert estimated.estimation_method is not None
    assert estimated.consecutive_estimate_no == 1
    # NEVER A SILENT ZERO, and the quantity carries its unit (rule 3).
    assert estimated.consumption == Decimal("304.918033")
    assert estimated.unit == "kWh"
    assert estimated.current_value is None  # BR-MET-028 — no register value
    assert estimated.status == "estimated"
    assert estimated.event_context == "move_out"  # the event that generated it
    assert estimated.imported_by_id == dana.id  # …and the person who asked for it


def test_w9_door__task_8_no_history_is_a_refusal_as_data_never_a_zero(brazos, dana):
    """**The other half of task 8: *"never a silent zero"* also means never a
    silent NOTHING.**

    US-MET-014 TC-5's *"no history — field visit"* is a legitimate answer a
    clerk must SEE beside the meter, so the engine returns it as DATA and the
    door carries it back on the row rather than raising or quietly skipping.
    Nothing is committed for that register — and a register with no head is
    ABSENT, which is a different fact from a measured zero.

    ⚠ **THIS CASE FOUND A REAL DEFECT AND `estimation.estimate` MOVED FOR IT
    (2026-08-26).** RED-FIRST PROOF, verbatim, against the code as it stood:

        AssertionError: assert 'period_days_missing' == 'no_history'
        - no_history
        + period_days_missing

    `days_in_period` is DERIVED from the prior actual head, so a meter with no
    history has no days either — and the days check ran first, so the clerk was
    told a date was missing (a symptom) instead of *"no history — field visit"*
    (the cause), with no `forced_disposition` on the refusal to send anyone out.
    The two checks were reordered to match BR-MET-026's own wording; the
    assertion here did NOT move.
    """
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        asset_id = _asset_id(unit, "M-9101")  # no history at all
        _account_on(dana, unit["id"], name="Farrow, Jean")

        answer = metering_services.commit_event_reads(
            dana,
            {
                "event": "disconnect",
                "reads": [{"meter_no": "M-9101", "read_at": "2026-08-31", "estimate": True}],
            },
        )
        still_absent = _head(asset_id)

    row = answer["estimates"][0]
    assert row["estimated"] is False
    assert row["reason"] == "no_history"
    assert row["detail"]["forced_disposition"] == "field_visit"
    assert still_absent is None, "nothing was committed — an absence, not a zero"


def test_w9_door__a_value_and_an_estimate_on_one_row_is_refused(brazos, dana):
    """A row asking for BOTH a keyed value and an estimate is a contradiction,
    and the door refuses it rather than picking one. Choosing would silently
    discard something a clerk typed, and which half to keep is a question no
    rule answers (the prime directive's shape, applied to a payload)."""
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        _account_on(dana, unit["id"], name="Baptiste, Yves")

        with pytest.raises(errors.ValidationError) as raised:
            metering_services.commit_event_reads(
                dana,
                {
                    "event": "move_in",
                    "reads": [
                        {
                            "meter_no": "M-9101",
                            "read_at": "2026-08-20",
                            "value": "10",
                            "estimate": True,
                        }
                    ],
                },
            )

    assert raised.value.field_errors[0]["field"] == "reads[1].estimate"


def test_w9_door__the_same_reading_twice_is_refused_as_a_duplicate(brazos, dana):
    """An event batch carries no FILE, so BR-MET-018's file-hash idempotency
    block cannot fire — and BR-MET-016's committed-duplicate rule is what
    stands in its place, so a second commit cannot silently double a
    customer's opening read.

    ⚠ **AMENDED 2026-10-04 (`BR-MET-1189`, `DEF-WRK-9642`).** This case used
    to assert the re-submission RAISED. PO ruling of that day: *"take the
    reading records in register and use date and highest consumption reading
    if it is apprved and validated"* — a second reading of a register on one
    date is stored, never refused. The SAME value again is not a second
    reading, it is the one already on file, so the door now answers it as
    `already_recorded`: no refusal (a field job reading what the office read
    must not fail Accept forever), and still no second row. The name is kept
    so the history of the case reads in one place."""
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        asset_id = _asset_id(unit, "M-9101")
        _account_on(dana, unit["id"], name="Ferreira, Tomás")
        payload = {
            "event": "move_in",
            "reads": [{"meter_no": "M-9101", "read_at": "2026-08-20", "value": "77"}],
        }
        first = metering_services.commit_event_reads(dana, payload)

        again = metering_services.commit_event_reads(dana, payload)

        heads = metering_models.MeterRead.objects.filter(
            asset_id=asset_id, superseded_by_id__isnull=True
        ).count()

    assert heads == 1, "the re-submission added nothing"
    assert again["posted_reads"] == 0
    assert [row["existing_read_id"] for row in again["already_recorded"]] == [
        first["posted"][0]["id"]
    ]


def test_w9_door__the_customers_seam_resolves_it_by_name(brazos, dana):
    """B1/B8 — customers NEVER writes `meter_reads`; it asks through the ONE
    late-bound seam. `reads_for_unit`'s pattern on the WRITE side, and the kind
    is named explicitly (`services`) for DEF-035's reason: two words wrong
    there and the wiring "passes" without ever having run.

    ⚠ **B2 §2 INTERFACE ROW OWED** for this seam — `04-docs/` is not this
    worktree's to edit; FLAGGED in the lane report."""
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        _account_on(dana, unit["id"], name="Sandoval, Pia")

        answer = customers_seams.commit_event_reads(
            dana,
            {
                "event": "move_in",
                "reads": [{"meter_no": "M-9101", "read_at": "2026-08-20", "value": "12"}],
            },
        )

    assert answer["posted_reads"] == 1
    assert answer["event"] == "move_in"


def test_w9_door__an_unwired_door_refuses_rather_than_dropping_the_readings(
    brazos, dana, monkeypatch
):
    """**DEF-075/DEF-127 applied to a WRITE, which is the harsher direction.**

    On a READ an unwired seam means "cannot answer" and the screen states it.
    On a WRITE, silently doing nothing would mean a clerk keyed four readings,
    saw a green commit, and the utility holds none of them. So `None` from the
    seam REFUSES the payload with `event_read_door_unwired` — and because the
    move-in wraps both in one transaction (BR-SHL-019), the account does not
    open either. A refusal a clerk can retry beats a success that lost data."""
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        outgoing = _account_on(dana, unit["id"], name="Peralta, Lucía")
        customers_services.move_out(dana, outgoing["id"], {"moved_out_on": "2026-08-19"})
        accounts_before = customers_models.Account.objects.count()

        monkeypatch.setattr(customers_services.seams, "commit_event_reads", lambda *_a, **_k: None)

        with pytest.raises(errors.BizError) as raised:
            customers_services.move_in(
                dana,
                outgoing["id"],
                {
                    "account_type": "residential",
                    "opened_at": "2026-08-20",
                    "contact": {"full_name": "Ito, Hana"},
                    # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
                    # customer identifies nobody, and this fixture's own name went in above.
                    # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
                    "customer": identity_fixtures.customer_block(
                        "Ito, Hana", account_type="residential"
                    ),
                    "initial_reads": [{"meter_no": "M-9101", "value": "43566"}],
                },
            )

        assert customers_models.Account.objects.count() == accounts_before, "no half-commit"
    assert raised.value.br_ref == "BR-CUS-021"
    assert raised.value.params["code"] == "event_read_door_unwired"


# ════════════════════════════════════════════════════════════════════════════
# 2 · THE FIVE EVENTS (tasks 3–7)
# ════════════════════════════════════════════════════════════════════════════
def test_w9_move_in__task_3_captures_the_opening_reads(brazos, dana):
    """**TASK 3, verbatim:** *"Move-in wizard: capture opening reads per meter
    (BR-CUS-021 built for real); unread registers stay visible, nothing
    invented."*

    Two meters, ONE read keyed: the reading that was taken lands with event
    `move_in` dated the move-in day, and the meter the clerk left blank is
    simply NOT READ — no row, no zero, no prior-final invented for it. The
    move-in's `initial_reads_not_committed` warning is GONE, because it would
    now be a false claim (hard-won law 1 runs in both directions).
    """
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(
            dana, brazos, meters=(("M-9101", "electric", "kWh"), ("M-9102", "water", "kgal"))
        )
        outgoing = _account_on(dana, unit["id"], name="Duarte, Rui")
        customers_services.move_out(dana, outgoing["id"], {"moved_out_on": "2026-08-19"})

        moved = customers_services.move_in(
            dana,
            outgoing["id"],
            {
                "account_type": "residential",
                "opened_at": "2026-08-20",
                "contact": {"full_name": "Alvarez, Rosa"},
                # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
                # customer identifies nobody, and this fixture's own name went in above.
                # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
                "customer": identity_fixtures.customer_block(
                    "Alvarez, Rosa", account_type="residential"
                ),
                "initial_reads": [{"meter_no": "M-9101", "value": "43566"}],
            },
        )

        electric = _head(_asset_id(unit, "M-9101"))
        water = _head(_asset_id(unit, "M-9102"))

    assert moved["event_reads"]["posted_reads"] == 1
    assert electric.event_context == "move_in"
    assert electric.read_at.date().isoformat() == "2026-08-20", "dated the move-in, not a clock"
    assert electric.imported_by_id == dana.id
    # NOTHING IS INVENTED for the register nobody read.
    assert water is None
    assert "initial_reads_not_committed" not in {w["code"] for w in moved["warnings"]}


def test_w9_move_in__without_reads_the_warning_still_rides(brazos, dana):
    """The mirror of the case above, and the reason it matters: a move-in that
    captured NOTHING must still say so. The warning was made CONDITIONAL, not
    deleted — a flow that commits no reads is exactly the state BR-CUS-021's
    absence describes, and deleting the sentence would hide it."""
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        outgoing = _account_on(dana, unit["id"], name="Kaur, Simran")
        customers_services.move_out(dana, outgoing["id"], {"moved_out_on": "2026-08-19"})

        moved = customers_services.move_in(
            dana,
            outgoing["id"],
            {
                "account_type": "residential",
                "opened_at": "2026-08-20",
                "contact": {"full_name": "Nowak, Ewa"},
                # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
                # customer identifies nobody, and this fixture's own name went in above.
                # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
                "customer": identity_fixtures.customer_block(
                    "Nowak, Ewa", account_type="residential"
                ),
            },
        )

    assert "initial_reads_not_committed" in {w["code"] for w in moved["warnings"]}
    assert "event_reads" not in moved


def test_w9_move_out__task_4_the_settlement_consumes_the_final_read(brazos, dana):
    """**TASK 4, verbatim:** *"Move-out wizard: capture final reads; settlement
    consumes them; the `FINAL READS DUE` KPI becomes a real number; the
    how-obtained flag (taken / due / estimated) lands on `move_out_settlement`
    (B18 draws it, no column carries it)."*

    All four halves in one commit: the read posts with event `move_out`, the
    BR-CUS-031 handoff SERVES its `final_reads` element instead of the
    BR-CUS-021 rule id, `accounts.final_read_state` records HOW it was obtained
    (`taken` — a keyed reading), and the FINAL READS DUE tile does not count
    this move-out, because its meter IS read.
    """
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        account = _account_on(dana, unit["id"], name="Whitfield, Marcus")

        closed = customers_services.move_out(
            dana,
            account["id"],
            {
                "moved_out_on": "2026-08-20",
                "final_reads": [{"meter_no": "M-9101", "value": "43566"}],
            },
        )
        read = _head(_asset_id(unit, "M-9101"))
        row = customers_models.Account.objects.get(id=account["id"])
        kpis = move_reads.move_out_kpis(as_of=TODAY)

    assert closed["event_reads"]["posted_reads"] == 1
    assert read.event_context == "move_out"
    assert read.read_at.date().isoformat() == "2026-08-20", "dated the move-out (BR-CUS-030)"
    # The handoff's own element, SERVED — no longer a rule id standing in for it.
    handoff = closed["final_bill_handoff"]
    assert handoff["final_reads_unavailable"] is None
    assert handoff["final_read_state"] == "taken"
    assert handoff["final_reads"]["meters"][0]["asset_no"] == "M-9101"
    # The stored flag, and the tile that counts against it.
    assert row.final_read_state == "taken"
    assert kpis["final_reads_due"] == 0
    assert "final_reads_not_committed" not in {w["code"] for w in closed["warnings"]}


def test_w9_move_out__an_estimated_final_read_flags_the_settlement_estimated(brazos, dana):
    """Task 4 meets task 8: the meter could not be read, so the final read is an
    ESTIMATE — and the settlement records that it consumed one.
    `accounts.final_read_state == "estimated"` is B18 §5.6.2's amber cell, and
    it is a claim about the SETTLEMENT rather than about history, which is
    exactly why it needed a column of its own rather than a derivation."""
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        asset_id = _asset_id(unit, "M-9101")
        account = _account_on(dana, unit["id"], name="Reyes, Marisol")
        commit_read(
            dana, asset_id, day="2026-06-30", value="1000",
            consumption="300.000000", days_since_prior=30,
        )
        commit_read(
            dana, asset_id, day="2026-07-31", value="1300", prior_value="1000",
            consumption="300.000000", days_since_prior=31,
        )

        closed = customers_services.move_out(
            dana,
            account["id"],
            {
                "moved_out_on": "2026-08-20",
                "final_reads": [{"meter_no": "M-9101", "estimate": True}],
            },
        )
        row = customers_models.Account.objects.get(id=account["id"])
        cell = next(
            entry
            for entry in move_reads.move_outs_list(as_of=TODAY)["rows"]
            if entry["account_no"] == row.account_no
        )["final_read"]

    assert closed["event_reads"]["estimates"][0]["estimated"] is True
    assert row.final_read_state == "estimated"
    assert cell["state"] == "estimated"  # the amber word, off the stored flag
    assert cell["unavailable"] is None


def test_w9_move_out__a_refused_reading_refuses_the_whole_close(brazos, dana):
    """**BR-SHL-019 — ONE transactional commit**, and this is where it bites.

    An ERROR from the door raises inside `move_out`'s own transaction, so the
    account is NOT closed, the agreements are NOT ended and no flag is stored.
    A move-out that closed an account while rejecting its final read would
    strand the closing consumption behind a close hard rule 4 forbids editing
    away."""
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        account = _account_on(dana, unit["id"], name="Bergström, Elin")

        with pytest.raises(errors.BizError):
            customers_services.move_out(
                dana,
                account["id"],
                {
                    "moved_out_on": "2026-08-20",
                    "final_reads": [{"meter_no": "M-NOPE", "value": "1"}],
                },
            )

        row = customers_models.Account.objects.get(id=account["id"])

    assert row.closed_at is None, "the close rolled back with the reading"
    assert row.final_read_state is None


def test_w9_transfer__task_5_one_read_serves_both_accounts(brazos, dana):
    """**TASK 5, verbatim:** *"Transfer: ONE read closes the old account and
    opens the new — the same value, never keyed twice."* And BR-MET-128's own
    clause: *"The transfer case stores ONE read serving both accounts, its
    event `transfer`"*.

    So exactly ONE `meter_reads` row exists for that meter, its event is
    `transfer`, and it is dated the OUT date — B18 §5.7.4's same-day rule,
    *"outgoing pays the move day, incoming starts the next day **from the same
    reading**"*. Both halves reference that one row; there is no second row for
    the first to disagree with.
    """
    with tenant_ctx(brazos):
        seed_config()
        from_unit = _metered_unit(dana, brazos, label="Unit A")
        to_unit = _metered_unit(
            dana, brazos, label="Unit B", meters=(("M-9201", "electric", "kWh"),)
        )
        account = _account_on(dana, from_unit["id"], name="Iversen, Britt")
        # ⚠ FIXTURE, not the subject: `transfers.start_transfer` refuses an
        # account with no `customer_accounts` link (BR-CUS-054 — B18 §2.5
        # records name matching as the failure the customer entity exists to
        # end), so a transfer cannot begin without one. Added 2026-08-26; the
        # case first failed
        #   core.errors.BizError: BIZ-STATE
        #   (customers.transfer.from_account_has_no_customer)
        # in the W7 helper's own way of doing it (`link_customer`, the one door).
        customers_services.link_customer(
            account_id=account["id"], display_name="Iversen, Britt"
        )

        started = transfers.start_transfer(dana, {"from_account_id": account["id"]})
        transfers.set_target_unit(dana, started["id"], {"to_unit_id": str(to_unit["id"])})
        transfers.set_dates(
            dana, started["id"], {"out_date": "2026-08-20", "in_date": "2026-08-21"}
        )
        transfers.elect_money(dana, started["id"], {})
        done = transfers.commit_transfer(
            dana,
            started["id"],
            {"reads": [{"meter_no": "M-9101", "value": "43566"}]},
        )

        rows = list(
            metering_models.MeterRead.objects.filter(asset_id=_asset_id(from_unit, "M-9101"))
        )

    assert done["event_reads"]["posted_reads"] == 1
    assert len(rows) == 1, "ONE read, never keyed twice — one row IS the rule"
    assert rows[0].event_context == "transfer"
    assert rows[0].read_at.date().isoformat() == "2026-08-20", "the OUT date, both sides"
    # The outgoing half's own settlement consumed exactly that row.
    assert done["outgoing"]["final_bill_handoff"]["final_read_state"] == "taken"


def test_w9_disconnect__task_6_the_final_read_is_captured_at_the_cut(brazos, dana, monkeypatch):
    """**TASK 6, verbatim:** *"Disconnect: final read captured or estimated,
    same door."*

    The crew reads the meter as the service goes dark, and that reading commits
    with event `disconnect`, dated `cut_on` — the cut's own date, never a wall
    clock (BR-TEN-043). `DSC-02.4`'s three prohibitions stay intact: this is
    not a move-out, so nothing here writes `accounts`."""
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        account = _account_on(dana, unit["id"], name="Achebe, Ngozi")
        _scheduled_cut(dana, account["id"], monkeypatch)

        cut = disconnects.commit_cut(
            dana,
            account["id"],
            cut_on=date(2026, 8, 24),
            as_of=date(2026, 8, 24),
            final_reads=[{"meter_no": "M-9101", "value": "43566"}],
        )
        read = _head(_asset_id(unit, "M-9101"))
        row = customers_models.Account.objects.get(id=account["id"])

    assert cut["event_reads"]["posted_reads"] == 1
    assert read.event_context == "disconnect"
    assert read.read_at.date() == date(2026, 8, 24), "dated the cut"
    assert read.imported_by_id == dana.id
    # `DSC-02.4`: a cut is not a move-out. Nothing wrote `accounts`.
    assert row.closed_at is None


def test_w9_new_connect__task_7_the_set_read_posts_when_a_person_accepts(brazos, dana):
    """**TASK 7, verbatim:** *"New connect: the set read at energisation,
    accepted by a person (BR-MET-110)."*

    BR-MET-110, PO 2026-08-25: *"Work order will send the data and confirm from
    field; utility staff will review these work order, accept them and use data
    from them to activate these services or confirm the installation is
    completed."* The middle step IS the rule, so the reading the crew sent sits
    in `field_data` and posts NOTHING; the human acceptance is what commits it,
    with the ACCEPTER — not the crew — as the read's user."""
    with tenant_ctx(brazos):
        seed_config()
        premises = make_premises(dana, services_available=["water"])
        unit = make_unit(dana, premises["id"], services=["water"])
        metering_services.assign_unit_plan(
            dana, unit["id"], {"tariff_id": str(_plan(brazos, "water").id)}
        )
        a_meter(dana, "W-88214", unit_id=unit["id"], service="water", uom="kgal")
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        w6.add_connection_service(dana, created["id"], service_code="water", unit_id=unit["id"])
        w6.submit_connection(dana, created["id"])
        order_id = w6.create_work_order(
            dana, created["id"], {"type": "meter set", "service": "water"}
        )["id"]

        field_close(
            dana,
            order_id,
            field_data={
                "meter_serial": "W-88214",
                "set_reads": [{"meter_no": "W-88214", "value": "0", "read_at": "2026-08-20"}],
            },
            outcome=work_tables.OUTCOME_PASSED,
        )
        # THE FIELD REPORTED. Nothing is accepted and nothing is committed.
        assert _head(_asset_id(unit, "W-88214")) is None

        accepted = w6.accept_field_result(dana, order_id)
        read = _head(_asset_id(unit, "W-88214"))

    assert accepted["event_reads"]["posted_reads"] == 1
    assert read.event_context == "new_connect"
    assert read.imported_by_id == dana.id, "the ACCEPTER, not the crew"
    assert read.unit == "kgal"  # rule 3, and the water meter's own UoM


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 Amendment 2 W9 tasks 1, 3–8 (BR-MET-128 · BR-MET-129 ·
#         BR-CUS-021 · BR-MET-110 · BR-MET-026/027/028/058 · BR-SHL-019)
# generated: 2026-08-26 by the CR-038 W9 event-reads lane
# checklist: A✔ B=n/a(tests) C✔ D=deferred(no API half — the door is a seam) E=deferred(the wizard screens are this lane's frontend commits) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: E3 the disconnect case is built directly and four W7 preconditions
#         are stubbed BY NAME (`_require_running`, `assert_cut_reachable`,
#         `assert_service_proved`, `reconnection_terms`) — none is about reads,
#         and DEF-700 means no tenant in this tree can price a reconnection ·
#         E3 no story owns the transfer/new-connect read capture (law 8) — OWED
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
