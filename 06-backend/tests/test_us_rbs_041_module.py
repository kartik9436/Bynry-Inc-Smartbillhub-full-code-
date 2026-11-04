# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A7: the module exists,
#           owns seven tables, and cannot reach past its own seams.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no ports) · BR-RBS-022 (a
#           write is a named port; work items and audit rows are the ENGINE's) ·
#           BR-RBS-024 (one category, from the fixed sixteen) · BR-RBS-039 (a
#           read goes through a seam this module owns) · CLAUDE.md hard rule 2
#           (money 4 decimals with a CHAR(3) partner) · hard rule 6 (idempotency
#           by a UNIQUE index)
# Tests:    this file (SQLite — shapes and declarations) ·
#           06-backend/tests/test_us_rbs_041_pg.py (PostgreSQL — TC-RBS-7, the
#           guarantees SQLite cannot hold)
# Impacts:  apps/runbooks/** · 10-scripts/gates/g115_runbooks_import_census.py
# ───────────────────────────────────────────────────────
"""US-RBS-041 on SQLite — the seven tables, the nine seams, the fourteen ports.

⚠ **WHAT THIS FILE CANNOT PROVE, STATED RATHER THAN IMPLIED.** It runs on the
default suite, which is in-memory SQLite, where **there is no row-level security
at all**. Every tenant-isolation claim this module makes is therefore proved in
`test_us_rbs_041_pg.py` and **skipped** here, never faked — `G5` once ran the
isolation suite on SQLite and called **192 skips a pass**, which is the failure
this note exists to keep out of the record.
"""

import pytest
from django.apps import apps as django_apps
from django.db import IntegrityError, transaction

from apps.runbooks import interfaces, models
from apps.runbooks.boundary import PortDeclaration, PortNotBound, SeamDeclaration
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin

# ── the module and its seven tables ───────────────────────────────────────


def test_us_rbs_041_tc1_the_module_is_installed_as_the_twelfth():
    """`apps.runbooks` is in DOMAIN_APPS and Django knows it by its label."""
    config = django_apps.get_app_config("runbooks")
    assert config.name == "apps.runbooks"


def test_us_rbs_041_tc2_seven_tables_and_their_db_names():
    """The seven B2 §2 names, exactly — no eighth, no rename.

    Read from the model registry rather than from a list, so a table added
    without a row in the schema brief fails here and not in review.
    """
    tables = {m._meta.db_table for m in django_apps.get_app_config("runbooks").get_models()}
    assert tables == set(models.TENANT_TABLES), tables ^ set(models.TENANT_TABLES)
    assert len(tables) == 7


def test_us_rbs_041_tc3_every_table_carries_a_tenant():
    """Hard rule 1 begins here: a tenant table without `tenant_id` cannot be scoped."""
    for model in django_apps.get_app_config("runbooks").get_models():
        names = {f.name for f in model._meta.get_fields()}
        assert "tenant" in names, f"{model._meta.db_table} has no tenant column"


def test_us_rbs_041_tc4_money_is_four_places_with_a_currency_partner():
    """Hard rule 2, and the D-2 gap the schema brief's r24 closed.

    The amount is `NUMERIC(18,4)`; `currency` is `CHAR(3)` beside it. Both are
    nullable because most record rows carry no amount at all — a missing-read
    finding has nothing to denominate — and the rule the column pair encodes is
    *where `amount` is not null, `currency` is not null either*.
    """
    amount = models.RunbookRunRecord._meta.get_field("amount")
    currency = models.RunbookRunRecord._meta.get_field("currency")
    assert (amount.max_digits, amount.decimal_places) == (18, 4)
    assert currency.max_length == 3
    assert amount.null and currency.null


def test_us_rbs_041_tc5_the_two_indexes_that_do_the_work_exist():
    """Hard rule 6 and `BR-RBS-017`, asserted as CONSTRAINTS rather than as prose.

    ⚠ This asserts the index is THERE. It deliberately asserts nothing about how
    the key is COMPOSED: that contradicts itself across our own documents
    (`DEF-RBS-4246`) and is `OQ-RBS-1737`, open. **The index is correct under
    every candidate answer**, which is exactly why it is laid in wave A and the
    composition is not.
    """
    record_constraints = {c.name for c in models.RunbookRunRecord._meta.constraints}
    item_constraints = {c.name for c in models.WorkItem._meta.constraints}
    assert "uq_runbook_run_records_idem" in record_constraints
    assert "uq_work_items_fingerprint" in item_constraints


def test_us_rbs_041_tc6_the_key_is_composed_in_exactly_ONE_place():
    """`OQ-RBS-1737` — **CLOSED 2026-09-06**, and the guard is RE-AIMED, not removed.

    ⚠ **THIS CASE ASSERTED THAT NOBODY COMPOSES A KEY AT ALL, WHICH WAS RIGHT
    WHILE THE QUESTION WAS OPEN AND IS WRONG NOW.** The Product Owner closed it
    by moving the duplicate check from the RECORD to the RUN, and `CR-075` wave
    L task `L5` composes the per-record key in
    `apps/runbooks/engine/acts.py::idempotency_key` — one 🔒 file, `HUMAN-OWNED`,
    with a row in the review ledger. Leaving the old assertion in place would
    have made it a guard that passes because nothing changed rather than because
    something is true (`DEF-WRK-4030`'s shape: a body that goes on describing the
    open world after its status has moved).

    **What it guards now is the thing that still matters:** the key is composed
    in ONE place and nowhere else. A second `_key(...)` helper in `services.py`,
    `selectors.py` or `models.py` would be a second composition that can disagree
    with the first — and the cost of a disagreement is the field map's own
    figure, *496 notices instead of 248, and no test that can see it*.
    """
    import inspect

    from apps.runbooks import models as runbooks_models
    from apps.runbooks import selectors, services
    from apps.runbooks.engine import acts

    assert "def idempotency_key" in inspect.getsource(acts), (
        "the per-record key is composed in engine/acts.py — if it moved, this "
        "case must move with it rather than quietly passing over an absence"
    )
    for module in (services, selectors, runbooks_models):
        source = inspect.getsource(module)
        for needle in ("def idempotency_key", "def _idempotency_key", "def build_key"):
            assert needle not in source, (
                f"{module.__name__} composes an idempotency key too. There is exactly ONE "
                "composition, in apps/runbooks/engine/acts.py, and a second one that can "
                "disagree with it sends 496 notices where 248 were meant."
            )


@pytest.mark.django_db
def test_us_rbs_041_tc7_the_idempotency_index_refuses_a_repeat(brazos, dana):
    """The index bites on SQLite too — the CONSTRAINT, not the composition.

    A second row with the same `(tenant, idempotency_key)` is refused by the
    database. That is what makes a retry safe, and it is a UNIQUE INDEX rather
    than application code on purpose: a retry arrives concurrently, and two
    workers each finding no row and each writing one is exactly the race an
    index refuses and a `SELECT`-then-`INSERT` does not.
    """
    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(brazos.id):
        runbook = models.Runbook.objects.create(
            tenant=brazos,
            key="can-we-bill",
            name="Can we bill?",
            kind=models.KIND_CHECK,
            category="platform",
            subject_type="tenant",
            unit_of_work="tenant",
            timezone="America/Chicago",
            gate_mode="approve_each_run",
        )
        run = models.RunbookRun.objects.create(
            tenant=brazos, runbook=runbook, version=1, status=models.RUN_STATUS_DONE
        )
        models.RunbookRunRecord.objects.create(
            tenant=brazos,
            run=run,
            subject_type="account",
            planned_action="report",
            idempotency_key="a-key-whose-shape-is-not-decided-here",
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                models.RunbookRunRecord.objects.create(
                    tenant=brazos,
                    run=run,
                    subject_type="account",
                    planned_action="report",
                    idempotency_key="a-key-whose-shape-is-not-decided-here",
                )


# ── the boundary: nine seams, fourteen ports, no writer ───────────────────


def test_us_rbs_041_tc8_nine_read_seams_named_for_the_far_side():
    """One file per module read, and every one of them declares READ."""
    assert set(interfaces.SEAMS) == {
        "customers",
        "metering",
        "rating",
        "billing",
        "payments",
        "ledger",
        "notifications",
        "tenancy",
        "integrations",
    }
    assert len(interfaces.SEAMS) == 9
    for module, seam in interfaces.SEAMS.items():
        assert isinstance(seam, SeamDeclaration)
        assert seam.direction == "read", f"{module} seam declares a direction other than read"
        assert seam.pair == f"operations → {module}"


def test_us_rbs_041_tc9_a_seam_cannot_declare_a_write():
    """A seam that writes is a seam in name only, refused at construction."""
    with pytest.raises(ValueError, match="a seam READS"):
        SeamDeclaration(
            module="customers", pair="operations → customers", crosses="x", direction="write"
        )


def test_us_rbs_041_tc10_fourteen_ports_and_raise_work_item_is_not_one():
    """`BR-RBS-022`, and the membership matters more than the count.

    The source says a runbook writes through *"four named calls"* in seven
    places and lists *raise a work item* among them; the contract lists thirteen
    and says raising work items and writing audit rows are ENGINE acts. If
    raising a work item were a port, **every Check would need a writer and
    `BR-RBS-002` would be gone** — so this assertion is the design, not
    bookkeeping.
    ⚠ **FOURTEEN FROM 2026-09-07, NOT THIRTEEN, AND THE COUNT MOVED
    DELIBERATELY.** `CR-075` wave `N` added `step_ladder` (payments) because a
    collections step also moves `notice_history` and `account_collection_state`
    — payments' own tables under `BR-PAY-017` — and `queue_notice` writes
    neither, so **the ladder never climbed** (`DEF-RBS-4347`). `12-the-contract.md`
    §6 anticipates exactly this: *"a new runbook that needs a new port is adding
    a reviewed interface, not a custom write."* This assertion is what made the
    addition visible, which is why the registry is written out by hand.
    """
    # ⚠ FIFTEEN FROM 2026-10-07 (`CR-173-BRC10`): `send_partner_file`, owned by
    # integrations, joined as a reviewed interface — the New World receipt file.
    assert len(interfaces.PORTS) == 15
    assert "raise_work_item" not in interfaces.PORTS
    assert "write_audit_row" not in interfaces.PORTS
    assert set(interfaces.PORTS) == {
        "queue_notice",
        "queue_receipt",
        "apply_payment",
        "post_credit",
        "raise_refund",
        "step_ladder",
        "record_match",
        "schedule_retry",
        "apply_fee",
        "write_read",
        "apply_premise_change",
        "flag_meter",
        "suppress_channel",
        "flag_account",
        "send_partner_file",
    }


#: ⚠ **THIS SET WAS EMPTY UNTIL `CR-075` WAVE L (2026-09-06), AND THE CHANGE IS
#: THE WAVE RATHER THAN A REGRESSION.** Phase 1's launch sentence — *"nothing
#: can be written: no writer is bound"* — was asserted here as
#: `bound_ports() == ()`, and wave L task `L2` is the task that binds them. What
#: replaces it is a STRICTER assertion, not a weaker one: the exact membership
#: of both sets, by name, so binding an eleventh or silently unbinding a working
#: one is a red test that names the port. The four that bind nothing are
#: `DEF-RBS-4331`. ⚠ **`step_ladder` IS THE TENTH, ADDED 2026-09-07** by wave
#: `N` (`DEF-RBS-4347`) — the set is no longer wave `L`'s alone and the name is
#: kept only because renaming it would move every citation.
BOUND_IN_WAVE_L = frozenset(
    {
        "queue_notice",
        "queue_receipt",
        "apply_payment",
        "post_credit",
        "raise_refund",
        "record_match",
        "schedule_retry",
        "apply_fee",
        "apply_premise_change",
        "step_ladder",
        # CR-173-BRC10 — bound from its first commit.
        "send_partner_file",
    }
)
STILL_UNBOUND = frozenset({"write_read", "flag_meter", "suppress_channel", "flag_account"})


def test_us_rbs_041_tc11_exactly_ten_ports_have_a_writer_and_four_do_not():
    """Wave L's replacement for phase 1's *nothing can be written*.

    ⚠ **NOTHING CAN STILL BE WRITTEN, AND IT IS NOW A DIFFERENT MECHANISM.** The
    declarations carry writers; `executor.build_context` hands every step a
    writer-LESS copy unless the runbook is on
    `engine.acts.LIVE_ENABLED_RUNBOOKS`, **which is empty for the whole
    catalogue** (`BR-RBS-003`). `tests/test_us_rbs_010_port_writers.py` asserts
    that in both directions — including by turning it on for one runbook, so the
    check cannot pass by unbinding everything unconditionally.
    """
    assert {port.name for port in interfaces.bound_ports()} == BOUND_IN_WAVE_L
    assert {
        name for name, port in interfaces.PORTS.items() if not port.is_bound
    } == STILL_UNBOUND
    assert BOUND_IN_WAVE_L | STILL_UNBOUND == set(interfaces.PORTS)


def test_us_rbs_041_tc12_a_check_holds_no_ports_at_all():
    """`BR-RBS-002` — the capability is ABSENT for a Check, not merely unused."""
    assert interfaces.ports_for("check") == ()
    assert len(interfaces.ports_for("action")) == 15


def test_us_rbs_041_tc13_an_unbound_port_refuses_and_names_the_wave():
    """The refusal still names the wave — asserted on a port that still HAS none.

    ⚠ **THIS CASE READ `queue_notice` UNTIL `CR-075` WAVE L BOUND IT
    (2026-09-06).** It is pointed at `flag_meter`, which binds nothing because no
    column in the product holds *"told about a leak on <date>"* and `Asset` is
    not metering's row to write (`DEF-RBS-4331`) — so the case goes on testing
    the refusal rather than quietly testing nothing.
    """
    with pytest.raises(PortNotBound) as refused:
        interfaces.PORTS["flag_meter"].call(asset_id="x")
    assert "no writer bound" in str(refused.value)
    assert "wave L" in str(refused.value)


def test_us_rbs_041_tc14_a_port_in_a_module_that_owns_none_is_refused():
    """A fourteenth port in a new module is a reviewed interface, not a line."""
    with pytest.raises(ValueError, match="reviewed interface"):
        PortDeclaration(name="post_journal", owning_module="ledger", what_it_does="x")


def test_us_rbs_041_tc15_the_sixteen_categories_name_an_owning_module_each():
    """`BR-RBS-024` — the category names whose ports a runbook may call.

    ⚠ The category is **`premises`**, not `service_points`: category names use
    the product's own existing word wherever it has one (decision log
    2026-09-06), because a second name for a thing the product has already named
    is how a clerk learns two vocabularies for one screen.
    """
    assert len(models.CATEGORIES) == 16
    assert "premises" in models.CATEGORIES
    assert "service_points" not in models.CATEGORIES
    assert set(models.CATEGORY_OWNING_MODULE) == set(models.CATEGORIES)


def test_us_rbs_041_tc16_twelve_subjects_and_the_premises_word():
    """The twelve subjects, and `premise` is the product's one address home."""
    assert len(models.SUBJECT_TYPES) == 12
    assert "premise" in models.SUBJECT_TYPES


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-041 (EP-RBS-01; CR-075 wave A task A7)
# generated: 2026-09-06 by the CR-075 wave A build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_rbs_041_module.py · G115 through run_gates.py
# exceptions: every tenant-isolation claim is in test_us_rbs_041_pg.py, which
#             SKIPS on this suite rather than passing vacuously (law 14)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
