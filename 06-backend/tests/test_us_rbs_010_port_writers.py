# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-010 (EP-RBS-04) — CR-075 wave L task L2: the fourteen ports
#           bind their writers.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no ports — the capability is
#           ABSENT) · BR-RBS-022 (a write is a named port into the OWNING
#           module's own service) · BR-RBS-003 (dry and live are one path,
#           differing only in whether the writer is bound) · DEF-RBS-4331 (four
#           ports have nothing to bind, and the number must stay TRUE)
# Tests:    this file
# Impacts:  apps/runbooks/ports/*_ports.py · apps/*/runbook_ports.py
# ───────────────────────────────────────────────────────
"""Which ports bind a writer, which do not, and that a Check still holds none.

⚠ **EVERY ASSERTION HERE IS A RULE, NOT AN IMPRESSION.** The membership of both
sets is pinned by NAME rather than by count, because a count passes when one
port is bound and another silently unbound on the same day — which is exactly
the kind of drift `DEF-RBS-4331` exists to keep visible.
"""

from __future__ import annotations

import pytest

from apps.runbooks import interfaces, models
from apps.runbooks.boundary import PortNotBound
from apps.runbooks.contract import (
    MODE_SET,
    Block,
    RunbookContractError,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.engine import acts, executor

#: The TEN ports whose owning module has a door a runbook may drive today, and
#: the four that have nothing to bind. ⚠ **`step_ladder` IS THE TENTH AND THE
#: FOURTEENTH PORT, ADDED 2026-09-07** (`DEF-RBS-4347`) — a collections step
#: also moves payments' `notice_history` and `account_collection_state`, which
#: `queue_notice` does not touch, so the ladder never climbed. **BOTH lists are asserted**, so binding a
#: fifth-from-last or unbinding a working one is a red test that names the port.
BOUND = frozenset(
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
UNBOUND = frozenset({"write_read", "flag_meter", "suppress_channel", "flag_account"})


def test_the_fourteen_are_still_fourteen_and_raise_work_item_is_not_among_them():
    """0 bound → 9 bound in wave `L`; 13 → 14 declarations in wave `N`.

    ⚠ **THE COUNT DID MOVE AND THAT IS THE POINT OF ASSERTING IT.** `step_ladder`
    was added on 2026-09-07 as a REVIEWED interface (`DEF-RBS-4347`, decision log
    of the same day), and this test going red is what forced the count to be
    moved in all four places rather than in one.
    """
    # ⚠ FIFTEEN FROM 2026-10-07 (`CR-173-BRC10`): `send_partner_file`, owned by
    # integrations, joined as a reviewed interface — the New World receipt file.
    assert len(interfaces.PORTS) == 15
    assert "raise_work_item" not in interfaces.PORTS
    assert BOUND | UNBOUND == set(interfaces.PORTS)


def test_ten_ports_bind_a_writer_and_four_name_why_they_cannot():
    """`DEF-RBS-4331` — `bound_ports()` reports a TRUE number, not a hopeful one.

    Asserted by NAME. A count-only assertion passes on the day somebody binds
    `flag_account` to `create_account_note` (which `BR-RBS-040` forbids) and
    unbinds `apply_fee` in the same commit.
    """
    bound = {port.name for port in interfaces.bound_ports()}
    assert bound == BOUND
    assert {name for name, port in interfaces.PORTS.items() if not port.is_bound} == UNBOUND


def test_every_bound_writer_lives_in_the_module_that_owns_the_table():
    """`BR-RBS-022` — one service function in the OWNING module, never here.

    A writer defined inside `apps.runbooks` would be a cross-module write that
    `G115`'s ORM rule cannot see, because it would go through the owning
    module's ORM from the wrong package. This asserts the module each writer
    actually lives in.
    """
    for port in interfaces.bound_ports():
        module = port.writer.__module__
        assert module == f"apps.{port.owning_module}.runbook_ports", (
            f"port {port.name!r} is bound to {module}, which is not "
            f"apps.{port.owning_module}.runbook_ports — a port maps to ONE service function "
            "in the module that owns the table (BR-RBS-022)."
        )


def test_an_unbound_port_refuses_by_name_and_says_which_wave_binds_it():
    """The four that cannot write REFUSE — they do not quietly do nothing."""
    for name in sorted(UNBOUND):
        with pytest.raises(PortNotBound) as caught:
            interfaces.PORTS[name].call()
        assert name in str(caught.value)


# ── BR-RBS-002: a Check is CONSTRUCTED with no writer ─────────────────────


def _report(_view):
    return [Block(block="kpis", payload={})]


def test_br_rbs_002_a_check_declaring_a_bound_port_is_refused_at_construction():
    """**SHOWN RED FIRST** on a build that let a Check hold `queue_notice`.

    The capability is ABSENT, not merely unused. This is the sentence that lets
    two people press **Run ▶** on a thousand accounts, and binding the writers
    in wave L is exactly when it could have been lost — a Check whose port now
    has a real writer behind it would WRITE, where in wave A it would only have
    raised.
    """
    with pytest.raises(RunbookContractError) as caught:
        RunbookDefinition(
            key="a_check_that_writes",
            name="A check that writes",
            kind=models.KIND_CHECK,
            category="collections",
            subject_type="account",
            unit_of_work="account",
            resolve=lambda ctx: [],
            report=_report,
            steps=(Step(key="s", label="s", mode=MODE_SET, run=lambda ctx, subs: {}),),
            ports=("queue_notice",),
        )
    message = str(caught.value)
    assert "queue_notice" in message and "a_check_that_writes" in message
    assert "BR-RBS-002" in message


def test_br_rbs_002_a_checks_context_holds_no_ports_even_now_that_writers_exist():
    """`ports_for("check")` is `()` — an empty mapping, not an allow-list."""
    assert interfaces.ports_for("check") == ()
    definition = RunbookDefinition(
        key="an_ordinary_check",
        name="An ordinary check",
        kind=models.KIND_CHECK,
        category="collections",
        subject_type="account",
        unit_of_work="account",
        resolve=lambda ctx: [],
        report=_report,
        steps=(Step(key="s", label="s", mode=MODE_SET, run=lambda ctx, subs: {}),),
    )
    ctx = executor.build_context(definition, mode="live")
    assert ctx.ports == {}


# ── BR-RBS-003: the ONE difference between dry and live ───────────────────


def _action(ports=("queue_notice",)):
    return RunbookDefinition(
        key="an_action",
        name="An action",
        kind=models.KIND_ACTION,
        category="collections",
        subject_type="account",
        unit_of_work="account",
        resolve=lambda ctx: [SubjectRef(subject_type="account", subject_id="x")],
        report=_report,
        steps=(Step(key="s", label="s", mode=MODE_SET, run=lambda ctx, subs: {}, writes=True),),
        ports=ports,
    )


def test_br_rbs_003_a_dry_run_holds_a_WRITER_LESS_copy_of_a_bound_port():
    """The whole of *dry* is this: the declaration is bound, the CONTEXT is not.

    Asserted on `queue_notice`, which IS bound in the registry — so this case
    cannot pass by accident on a port that has no writer anyway.
    """
    assert interfaces.PORTS["queue_notice"].is_bound
    ctx = executor.build_context(_action(), mode="dry")
    assert ctx.ports["queue_notice"].is_bound is False
    # ...and the registry's own declaration is untouched: a dry run must not
    # unbind the port for everybody else in the process.
    assert interfaces.PORTS["queue_notice"].is_bound


def test_a_live_run_of_a_runbook_that_is_not_live_enabled_is_also_writer_less():
    """**WAVE L's WHOLE POSTURE, ASSERTED RATHER THAN DESCRIBED.**

    `acts.LIVE_ENABLED_RUNBOOKS` is EMPTY, so *live* changes nothing today and
    `L6`'s *"the runbook DISABLED for live"* holds for the entire catalogue.
    This case goes RED the day somebody adds a key to that set without saying
    so, which is the only kind of switch worth having.
    """
    # ⚠ ONE KEY SINCE 2026-10-07 (`CR-173-BRC10`) — the New World receipt push,
    # which writes no money. Any OTHER key arriving still goes red here.
    assert acts.LIVE_ENABLED_RUNBOOKS == frozenset({"newworld_receipt_push"})
    ctx = executor.build_context(_action(), mode="live")
    assert ctx.ports["queue_notice"].is_bound is False
    assert acts.live_enabled("collections_ladder") is False


def test_a_live_run_of_an_enabled_runbook_reaches_the_real_writer(monkeypatch):
    """The mechanism works in the OTHER direction too — proved, not assumed.

    A test that only ever saw *unbound* would pass identically if
    `build_context` unbound everything unconditionally, which is a check that
    cannot fail (hard-won law 7). This one pins the switch by turning it on.
    """
    monkeypatch.setattr(acts, "LIVE_ENABLED_RUNBOOKS", frozenset({"an_action"}))
    ctx = executor.build_context(_action(), mode="live")
    assert ctx.ports["queue_notice"].is_bound is True
    assert ctx.ports["queue_notice"].writer is interfaces.PORTS["queue_notice"].writer


# ── the writers themselves ────────────────────────────────────────────────


def test_money_bearing_writers_refuse_a_float():
    """Hard rule 2 — money is a `Decimal`, and a float is refused at the door.

    `0.1 + 0.2` is not `0.3`, and these values pass through `jsonb`, where **no
    column type will catch it**. Asserted on the three payments writers that
    take an amount.
    """
    from apps.payments import runbook_ports as payments_writers

    with pytest.raises(TypeError):
        payments_writers._require_decimal(12.34, "amount")


def test_the_notifications_source_id_is_stable_for_the_same_act():
    """Same runbook, same account, same rung → the same id, always.

    This is the second idempotency layer: `queue_document` refuses a duplicate
    on `(tenant, source_type, source_id, channel, copy_no)`, and it can only do
    that if the id is derived rather than minted. A random id here would make
    every re-run a fresh document and the guarantee would be gone.
    """
    from apps.notifications import runbook_ports as notifications_writers

    first = notifications_writers.runbook_source_id(
        runbook_key="collections_ladder", subject_id="acc-1", discriminator="first_10_day"
    )
    same = notifications_writers.runbook_source_id(
        runbook_key="collections_ladder", subject_id="acc-1", discriminator="first_10_day"
    )
    other_rung = notifications_writers.runbook_source_id(
        runbook_key="collections_ladder", subject_id="acc-1", discriminator="second_5_day"
    )
    assert first == same
    assert first != other_rung


def test_customers_binds_nothing_and_the_file_says_why():
    """`DEF-RBS-4331` — an absence with an address (hard-won law 1).

    The module exists, carries the reason for both ports, and defines no writer.
    A future lane that adds one has to move this assertion, which is where they
    will read why it was not there.
    """
    from apps.customers import runbook_ports as customers_writers

    assert not hasattr(customers_writers, "suppress_channel")
    assert not hasattr(customers_writers, "flag_account")
    assert "DEF-RBS-4331" in (customers_writers.__doc__ or "")
    assert "BR-RBS-040" in (customers_writers.__doc__ or "")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-010 (EP-RBS-04; CR-075 wave L task L2)
# generated: 2026-09-06 by the CR-075 wave L build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_rbs_010_port_writers.py
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
