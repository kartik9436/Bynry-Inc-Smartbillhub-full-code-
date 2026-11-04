# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-037 (EP-RBS-05) — CR-075 wave R′, runbook 27.
# Rules:    BR-RBS-003 · BR-RBS-006 · BR-RBS-011 · BR-RBS-012 · BR-RBS-018 ·
#           BR-RBS-020 · BR-RBS-021 · BR-RBS-027 · BR-RBS-035 · BR-CUS-025 ·
#           CLAUDE.md hard rule 2 · hard rule 4 · hard rule 8 ·
#           B14 rules 31, 32, 33
# Tests:    this file.
# Impacts:  apps/runbooks/definitions/move_outs.py
# ───────────────────────────────────────────────────────
"""Runbook 27, against the rules rather than against itself.

⚠ **THE SEAMS ARE REPLACED, AND WHAT THAT DOES AND DOES NOT PROVE IS STATED.**
These cases hand the runbook fixed answers so the DECISIONS can be exercised —
an account with no closing read, one with no forwarding address, one whose
settlement cannot be completed, one closed in March and never billed, a refund
without a second approval, a cap that refuses. **It proves the runbook's
reasoning and NOTHING about the seams.**

⚠ **AND IT PROVES NOTHING ABOUT THE MONEY ARITHMETIC EITHER, DELIBERATELY.**
The five landings are 🔒 human-owned in `apps/customers/move_out_settlement.py`
and are tested there, with the Product Owner's own figures. What these cases
assert is that this runbook READS that verdict and never computes a second one.
"""

from decimal import Decimal

import pytest

from apps.runbooks.contract import BLOCK_TYPES
from apps.runbooks.definitions import move_outs as mo
from apps.runbooks.engine import executor
from core import tenancy as core_tenancy

# ⚠ **THE STAR IMPORT IS LOAD-BEARING AND IS NOT LAZINESS** — the same sentence
# `test_us_rbs_001_configuration_check.py` carries, for the same reason.
# `test_us_ten_helpers` declares an `autouse` fixture, `sqlite_guc`, that sends
# `set_config('app.tenant_id', …)` to a recording fake on SQLite — which has no
# such function — while leaving the Python-side ContextVar mirror real. Without
# it every `tenant_context` here dies on `sqlite3.OperationalError: no such
# function: set_config`, which reads as a broken fixture rather than a missing
# import. This file's own names are defined BELOW the import and win.
from tests.test_us_met_helpers import *  # noqa: F401,F403,E402 — incl. the autouse sqlite_guc

pytestmark = pytest.mark.django_db

TODAY = "2026-09-07"

#: The tenant the runbook writes its record rows under, for the life of one case.
#: A dict rather than a global so the fixture below can clear it and `_run`
#: cannot silently reuse a previous case's tenant.
_TENANT: dict = {}


@pytest.fixture(autouse=True)
def a_real_tenant():
    """**A REAL `tenants` ROW, BECAUSE `acts.plan` WRITES ONE.**

    ⚠ **`_run` PASSED THE LITERAL STRING `"t"` AS THE TENANT ID UNTIL
    2026-09-24 AND SIX CASES WERE RED ON IT (`DEF-RBS-6457`)** —
    `django.core.exceptions.ValidationError: ['“t” is not a valid UUID.']`,
    raised inside `acts.plan`'s idempotency `SELECT` on
    `runbook_run_records.tenant_id`. A placeholder was harmless while every
    seam was stubbed and nothing touched the database; the moment
    `step_settle_the_deposit` began PLANNING an act — a row written before
    anything is acted on (`BR-RBS-004`) — it stopped being harmless. The six
    are exactly the cases that reach that step: an approved refund, a
    carry-forward, and the four that read a record's data back.

    ⚠ **AND IT IS A BARE ROW ON PURPOSE.** The file's own header says these
    cases prove *"the runbook's reasoning and NOTHING about the seams"* — every
    seam is monkeypatched — so a fully provisioned utility would be minutes of
    seeding to satisfy one foreign key. `tenants` is RLS-exempt (a platform
    table, `db/rls_tenancy_w0.sql`), so the row can be created outside a tenant
    context; the RECORD rows the runbook writes are not, which is why `_run`
    executes inside `tenant_context` below.
    """
    from apps.tenancy import models as tenancy_models

    tenant = tenancy_models.Tenant.objects.create(
        name="Brazos Bend Utilities",
        subdomain="brazosbend-rbs037",
    )
    _TENANT["id"] = tenant.id
    yield tenant
    _TENANT.clear()


def _account(
    account_no="A-1001",
    *,
    account_id=None,
    closed_at="2026-09-12",
    already_closed=False,
    read_state=mo.READ_TAKEN,
    deposit="150.0000",
    sample=False,
    premises_id=None,
):
    return {
        "account_id": account_id or f"acct-{account_no}",
        "account_no": account_no,
        "customer_name": "Alvarez, M.",
        "closed_at": closed_at,
        "already_closed": already_closed,
        "status_label": "Closed" if already_closed else "Marked disconnect",
        "final_read_state": read_state,
        "deposit_held": deposit,
        "currency": "USD",
        "premises_id": premises_id or f"prem-{account_no}",
        "unit_id": f"unit-{account_no}",
        "is_sample": sample,
    }


def _settlement(landing="refund_due", *, refund="296.4000", gaps=(), currency="USD"):
    """A settlement in the shape `customers` hands across — pairs, not floats."""

    def pair(value):
        return {
            "stored": value,
            "display": None if value is None else str(round(Decimal(value), 2)),
        }

    return {
        "currency": currency,
        "landing": None if gaps else landing,
        "complete": not gaps,
        "gaps": list(gaps),
        "verdict": {
            "net": pair("-296.4000"),
            "refund_amount": pair(refund),
            "shortfall": pair(None),
            "excess": pair(refund),
        },
        "everything_outstanding": {"total": pair("153.5000")},
        "what_is_applied": {"total": pair("449.9000")},
        "unavailable": [],
    }


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for every read runbook 27 makes.

    Defaults to *one account closing next week, read taken, address captured,
    a refund due* — the happy path — because the cases about each ABSENCE say so
    explicitly and a fixture that defaulted to broken would make them silent.
    """
    state = {
        "accounts": [],
        "issued": {},
        "premises": [],
        "forwarding": {},
        "settlements": {},
        "cap": None,
        "settlement_raises": set(),
        "approved": False,
    }

    monkeypatch.setattr(
        mo.customers_seam,
        "closing_accounts",
        lambda *, as_of, window_days=14: list(state["accounts"]),
    )
    monkeypatch.setattr(
        mo.billing_seam, "last_issued_bill_dates", lambda ids: dict(state["issued"])
    )
    monkeypatch.setattr(
        mo.metering_seam,
        "premises_for_reconciliation",
        lambda include_sample=False: list(state["premises"]),
    )
    monkeypatch.setattr(
        mo.customers_seam,
        "mailing_address_for_account",
        lambda account_id: state["forwarding"].get(
            str(account_id), {"line1": "9 Elm Rd", "city": "Katy", "missing": []}
        ),
    )

    def _settle(account_id, *, as_of, final_bill=None):
        if str(account_id) in state["settlement_raises"]:
            raise ValueError("the closing balance could not be read")
        return state["settlements"].get(str(account_id), _settlement())

    monkeypatch.setattr(mo.customers_seam, "move_out_settlement", _settle)
    monkeypatch.setattr(mo, "_cap", lambda ctx: state["cap"])

    # ⚠ **THE SECOND APPROVAL IS A FIXTURE SWITCH AND IT DEFAULTS TO *NOT
    # APPROVED*, WHICH IS THE SHIPPED STATE** (`BR-RBS-018`, `OQ-RBS-1732`
    # CLOSED 2026-09-06 — *"every money action, no threshold"*). A fixture that
    # defaulted to approved would make every case below assert on a path a real
    # run only reaches after a second person has pressed a button, and the
    # refusal — the thing that protects the customer — would be tested nowhere.
    monkeypatch.setattr(
        mo._money_gate,
        "second_approval",
        lambda ctx, *, planned: (
            {"approved": True, "reason": "", "approved_count": planned}
            if state["approved"]
            else {
                "approved": False,
                "reason": "Waiting for a second person to approve this run.",
                "approved_count": None,
            }
        ),
    )
    return state


def _premise(account_no, line="14 Cedar St"):
    return {"premises_id": f"prem-{account_no}", "address_line": line}


def _run(params=None):
    settings = {"as_of": TODAY}
    settings.update(params or {})
    definition = mo.RUNBOOK
    tenant_id = _TENANT["id"]
    ctx = executor.build_context(
        definition, tenant_id=tenant_id, run_id=None, params=settings
    )
    # `runbook_run_records` is tenant-scoped with RLS FORCE, so the INSERT
    # `acts.plan` makes needs `app.tenant_id` set — CLAUDE.md hard rule 1. It
    # is invisible on SQLite and refuses on PostgreSQL, which is the whole of
    # hard-won law 14.
    with core_tenancy.tenant_context(tenant_id):
        return executor.execute(definition, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _checked(result, step):
    return (result.set_results.get(step) or {}).get("checked") or {}


def _tiles(result):
    return {tile["id"]: tile for tile in _blocks(result)["kpis"]["tiles"]}


def _rows(result):
    return {
        row["cells"]["account"]["text"].split(" · ")[0]: row
        for row in _blocks(result)["records"]["rows"]
    }


# ── hard rule 4 · the bill this runbook may not issue ─────────────────────


def test_no_step_claims_to_write_a_bill_and_no_bill_port_is_held(seams):
    """`billing_ports.py`: *"THERE IS NO PORT THAT ISSUES A BILL, AND THERE WILL
    NOT BE. … the bill run is billing's own act."*

    That is hard rule 4 read forward — an issued invoice is append-only, and a
    module that could re-run one would be writing corrections nobody asked for.
    A step CLAIMING to write here would be a claim the capability contradicts.
    """
    assert "apply_fee" not in mo.RUNBOOK.ports
    assert mo.RUNBOOK.ports == ("raise_refund", "post_credit", "queue_notice")
    bill_step = next(one for one in mo.RUNBOOK.steps if one.key == mo.STEP_BILL)
    assert bill_step.writes is False


def test_step_four_hands_billing_a_scope_and_issues_nothing(seams):
    seams["accounts"] = [_account("A-1001")]
    seams["premises"] = [_premise("A-1001")]
    checked = _checked(_run(), mo.STEP_BILL)
    assert checked["ready_to_bill"] == 1
    assert checked["bills_issued_by_this_runbook"] == 0
    assert "billing's own act" in checked["why_not"]


def test_the_screen_says_no_bill_was_issued_rather_than_leaving_it_to_be_inferred(seams):
    """Hard-won law 7: a reader must see the absence WITHOUT knowing the rules."""
    seams["accounts"] = [_account("A-1001")]
    seams["premises"] = [_premise("A-1001")]
    facts = _blocks(_run())["facts"]["rows"]
    issued = next(one for one in facts if one["label"] == "Final bills issued by this run")
    assert issued["value"]["text"] == "0"
    assert "billing's own act" in issued["detail"]


# ── step 1 · the backwards window, which is the point ─────────────────────


def test_a_closed_account_with_no_final_bill_is_found_however_old(seams):
    """*"The gap E.ON Next paid £14.5 million for."* A move-out processed in
    March and never billed is off the ageing, off the bill run and off the
    ladder — this is the only thing in the product that looks for it."""
    seams["accounts"] = [
        _account("A-OLD", closed_at="2026-03-14", already_closed=True),
    ]
    seams["premises"] = [_premise("A-OLD")]
    result = _run()
    assert _checked(result, mo.STEP_GATHER)["already_closed_with_no_bill"] == 1
    assert _tiles(result)["old"]["value"]["text"] == "1"


def test_a_bill_issued_before_the_move_out_is_not_the_final_bill(seams):
    """A cycle bill from two months earlier settles nothing, and reading it as
    the final bill is how an account closes owing a fortnight nobody billed."""
    import datetime

    seams["accounts"] = [_account("A-OLD", closed_at="2026-03-14", already_closed=True)]
    seams["premises"] = [_premise("A-OLD")]
    seams["issued"] = {"acct-A-OLD": datetime.date(2026, 1, 31)}
    assert _checked(_run(), mo.STEP_GATHER)["already_closed_with_no_bill"] == 1


def test_a_bill_issued_on_the_move_out_date_counts_as_the_final_bill(seams):
    """The mirror — otherwise the case above might be finding everything."""
    import datetime

    seams["accounts"] = [_account("A-DONE", closed_at="2026-03-14", already_closed=True)]
    seams["premises"] = [_premise("A-DONE")]
    seams["issued"] = {"acct-A-DONE": datetime.date(2026, 3, 14)}
    assert _checked(_run(), mo.STEP_GATHER)["already_closed_with_no_bill"] == 0


# ── step 2 · the closing read, and its fourth fact ────────────────────────


def test_an_account_with_no_closing_read_is_not_ready_and_says_why(seams):
    """A final bill on an unread meter is a bill the customer will dispute."""
    seams["accounts"] = [_account("A-NOREAD", read_state=mo.READ_DUE)]
    seams["premises"] = [_premise("A-NOREAD")]
    result = _run()
    assert _checked(result, mo.STEP_READ)["closing_read_due"] == 1
    assert result.records[0].outcome == mo.OUTCOME_NOT_READY
    assert "No closing read" in result.records[0].reason


def test_a_read_state_of_none_is_its_own_number_and_not_counted_as_due(seams):
    """`Account.final_read_state` NULL means the close predates the column, or
    the seam could not answer, or the unit held no meters — three honest
    absences, and the column refuses to invent a fourth value for them."""
    seams["accounts"] = [_account("A-UNKNOWN", read_state=None)]
    seams["premises"] = [_premise("A-UNKNOWN")]
    checked = _checked(_run(), mo.STEP_READ)
    assert checked["closing_read_not_stated"] == 1
    assert checked["closing_read_due"] == 0


def test_an_estimated_read_is_flagged_and_still_processed(seams):
    """Holding every estimated close would stop the runbook whose whole job is
    to find the ones nobody finished."""
    seams["accounts"] = [_account("A-EST", read_state=mo.READ_ESTIMATED)]
    seams["premises"] = [_premise("A-EST")]
    result = _run()
    assert _checked(result, mo.STEP_READ)["closing_read_estimated"] == 1
    assert result.records[0].outcome != mo.OUTCOME_NOT_READY


# ── hard rule 8 · two addresses, and they are different facts ─────────────


def test_the_service_address_is_walked_to_from_the_premises(seams):
    """`BR-MET-1161`: an account declares no address column, so *14 Cedar St*
    is a walk to the premises and not a read off the account."""
    seams["accounts"] = [_account("A-1001")]
    seams["premises"] = [_premise("A-1001")]
    assert "14 Cedar St" in _rows(_run())["A-1001"]["cells"]["account"]["text"]


def test_a_missing_forwarding_address_is_reported_and_holds_the_letter(seams):
    """Hard rule 8's FIRST stated exception — where the BILL goes. Posting a
    final bill to the property somebody has just left is the most reliable way
    never to be paid."""
    seams["accounts"] = [_account("A-NOFWD")]
    seams["premises"] = [_premise("A-NOFWD")]
    seams["forwarding"] = {
        "acct-A-NOFWD": {"line1": None, "missing": ["line1", "city", "postal_code"]}
    }
    result = _run()
    assert _checked(result, mo.STEP_ADDRESS)["forwarding_address_missing"] == 1
    assert _checked(result, mo.STEP_NOTICE)["held_for_no_forwarding_address"] == 1
    assert _rows(result)["A-NOFWD"]["cells"]["forwarding"]["text"] == "Missing"


def test_a_premises_with_no_address_is_its_own_number(seams):
    """A property with no address line and a customer who gave no forwarding
    address are different problems, and one number cannot say both."""
    seams["accounts"] = [_account("A-1001")]
    seams["premises"] = []
    checked = _checked(_run(), mo.STEP_ADDRESS)
    assert checked["no_service_address_on_the_premises"] == 1
    assert checked["forwarding_address_missing"] == 0


# ── step 5 · the money, and the two rules it never re-derives ─────────────


def test_the_settlement_is_read_and_never_recomputed(seams):
    """`BR-CUS-025` and its four neighbours are 🔒 human-owned in `customers`.

    A second implementation of a money decision is two answers that eventually
    disagree about one customer, and the one in `customers` is what a clerk
    already sees on the move-out wizard.
    """
    seams["accounts"] = [_account("A-1001")]
    seams["premises"] = [_premise("A-1001")]
    seams["approved"] = True
    result = _run()
    assert result.records[0].outcome == mo.OUTCOME_TO_REFUND
    assert result.records[0].data["landing"] == "refund_due"
    assert result.records[0].data["amount"] == "296.40"


def test_a_settlement_with_a_gap_states_no_landing_and_holds_the_account(seams):
    """`DEF-127`'s shape on a money path: a zero here would refund a customer
    who still owes. Held, named and counted — never settled against a bill
    nobody read."""
    seams["accounts"] = [_account("A-GAP")]
    seams["premises"] = [_premise("A-GAP")]
    seams["settlements"] = {"acct-A-GAP": _settlement(gaps=["final_bill_not_stated"])}
    result = _run()
    assert result.records[0].outcome == mo.OUTCOME_HELD
    assert "cannot be settled" in result.records[0].reason


def test_a_refusal_from_the_owning_module_is_a_held_account_not_a_zero(seams):
    """`DEF-047`'s family — a caller that adapts the owner's RESULT but not its
    REFUSAL. The sentence the owner wrote is what a clerk reads."""
    seams["accounts"] = [_account("A-BOOM")]
    seams["premises"] = [_premise("A-BOOM")]
    seams["settlement_raises"] = {"acct-A-BOOM"}
    result = _run()
    assert result.records[0].outcome == mo.OUTCOME_HELD
    assert "could not be read" in result.records[0].decided_by_rule


def test_an_open_dispute_holds_the_money(seams):
    """`BR-CUS-096`: an open dispute HOLDS the excess until it closes."""
    seams["accounts"] = [_account("A-DISPUTE")]
    seams["premises"] = [_premise("A-DISPUTE")]
    seams["settlements"] = {"acct-A-DISPUTE": _settlement(landing="refused_excess")}
    result = _run()
    assert result.records[0].outcome == mo.OUTCOME_HELD
    assert "open dispute" in result.records[0].reason


def test_a_shortfall_is_still_chased_rather_than_written_off(seams):
    """`BR-CUS-082`: a debt surviving closure is still chased."""
    seams["accounts"] = [_account("A-SHORT")]
    seams["premises"] = [_premise("A-SHORT")]
    seams["settlements"] = {"acct-A-SHORT": _settlement(landing="short")}
    assert _run().records[0].outcome == mo.OUTCOME_STILL_OWES


# ── BR-RBS-018 · the second approval, with no threshold ───────────────────


def test_a_refund_is_held_until_a_second_person_approves_the_run(seams):
    """`OQ-RBS-1732` CLOSED 2026-09-06 — PO verbatim, *"every money action, no
    threshold"*. ⚠ **AND IT IS THE DEFAULT**: an unapproved run reaches the
    port for nothing at all, whatever the amount."""
    seams["accounts"] = [_account("A-1001")]
    seams["premises"] = [_premise("A-1001")]
    result = _run()
    assert result.records[0].outcome == mo.OUTCOME_HELD
    assert "second person" in result.records[0].reason
    assert result.records[0].data["issue"] == mo.ISSUE_AWAITING_APPROVAL


def test_an_approved_run_reaches_the_port_and_is_refused_there(seams):
    """The mirror — otherwise the case above might be refusing everything for
    some other reason entirely, and the approval gate would be untested.

    With the approval in hand the run reaches `raise_refund`, and the port's own
    refusal is what comes back: `LIVE_ENABLED_RUNBOOKS` is empty.
    """
    seams["accounts"] = [_account("A-1001")]
    seams["premises"] = [_premise("A-1001")]
    seams["approved"] = True
    result = _run()
    assert result.records[0].outcome == mo.OUTCOME_TO_REFUND
    assert result.records[0].data["amount"] == "296.40"


def test_a_carry_forward_does_not_wait_for_the_second_approval(seams):
    """`RB-127`'s guard, both halves: *"a refund sits behind the second
    approval; a carry-forward does not."* A test that only checked the refund
    would pass over a runbook that gated both — safer, and not what was ruled.
    """
    seams["accounts"] = [_account("A-SIB")]
    seams["premises"] = [_premise("A-SIB")]
    seams["settlements"] = {"acct-A-SIB": _settlement(landing="refused_other_debt")}
    assert seams["approved"] is False
    assert _run().records[0].outcome == mo.OUTCOME_TO_CARRY


def test_no_parameter_of_this_runbook_is_an_amount(seams):
    """A threshold added later would be this lane answering a question the
    Product Owner already answered in the safe direction — and the register says
    in as many words that one is not to be added without a new ruling.

    ⚠ **THIS ASSERTS THE DECLARATION AND NOT THE PROSE.** An earlier version
    grepped the source for the word *threshold* and went red on this file's own
    comments explaining why there is none — a check whose false failure is its
    own documentation is a check nobody keeps.
    """
    for parameter in mo.RUNBOOK.parameters:
        assert parameter.type not in ("money", "percent"), parameter.name
        assert "amount" not in parameter.name
        assert "threshold" not in parameter.name


# ── hard rule 2 · money, and the rounding that happens once ───────────────


def test_no_figure_is_ever_a_float(seams):
    """Hard rule 2. `float("296.40")` is where a utility's refunds stop tying
    out, which is why the seam hands money across as canonical strings."""
    seams["accounts"] = [_account("A-1001")]
    seams["premises"] = [_premise("A-1001")]
    data = _run().records[0].data
    assert isinstance(mo._decimal(data["amount_stored"]), Decimal)
    assert data["amount_stored"] == "296.4000"
    assert data["amount"] == "296.40"


def test_the_total_is_summed_at_four_decimals_and_shown_at_two(seams):
    """Summing the DISPLAY halves would round 48 times and then once more,
    which is the double-rounding B4 forbids by name."""
    seams["accounts"] = [_account("A-1"), _account("A-2")]
    seams["premises"] = [_premise("A-1"), _premise("A-2")]
    seams["settlements"] = {
        "acct-A-1": _settlement(refund="10.0050"),
        "acct-A-2": _settlement(refund="10.0050"),
    }
    seams["approved"] = True
    tile = _tiles(_run())["refund_total"]
    # 10.0050 + 10.0050 = 20.0100 → 20.01, not 10.01 + 10.01 = 20.02.
    assert tile["value"]["amount"] == "20.01"
    assert tile["value"]["currency"] == "USD"


def test_a_run_across_two_currencies_shows_no_total(seams):
    """A sum across two currencies is not an amount, and a tile that showed one
    would be labelled with whichever currency happened to sort first."""
    seams["accounts"] = [_account("A-1"), _account("A-2")]
    seams["premises"] = [_premise("A-1"), _premise("A-2")]
    seams["settlements"] = {
        "acct-A-1": _settlement(currency="USD"),
        "acct-A-2": _settlement(currency="CAD"),
    }
    seams["approved"] = True
    tile = _tiles(_run())["refund_total"]
    assert tile["value"]["amount"] is None
    assert "more than one currency" in tile["detail"]


def test_an_amount_without_a_currency_cannot_even_be_constructed():
    """Hard rule 2: `CHAR(3)` currency, always. A figure with no currency is a
    number nobody can pay."""
    with pytest.raises(ValueError) as caught:
        mo.Closing(
            account_id="a",
            account_no="A-1",
            customer_name=None,
            closed_at="2026-09-12",
            address=None,
            forwarding_missing=(),
            read_state=mo.READ_TAKEN,
            landing="refund_due",
            currency="",
            amount_stored=Decimal("296.4000"),
            amount="296.40",
            outcome=mo.OUTCOME_TO_REFUND,
            issue=None,
            reason="x",
            decided_by_rule="y",
            fix_route="accounts",
            fix_label="Open account →",
        )
    assert "CHAR(3) currency" in str(caught.value)


# ── BR-RBS-006 / 012 · the cap and the guard ──────────────────────────────


def test_the_cap_refuses_the_whole_run_and_never_truncates_it(seams):
    """Settling the first N deposits and dropping the rest is the failure that
    looks like success."""
    seams["accounts"] = [_account(f"A-{n}") for n in range(4)]
    seams["premises"] = [_premise(f"A-{n}") for n in range(4)]
    seams["cap"] = 2
    result = _run()
    stop = result.set_results[mo.STEP_BILL]["stop"]
    assert stop["headline"] == "Too many move-outs for one run."
    assert "4 accounts are ready to bill and the limit is 2" in stop["detail"]
    assert "Nothing has been settled." in stop["detail"]
    assert "kpis" not in _blocks(result)


def test_a_sample_account_is_guarded_and_still_counted(seams):
    """`BR-RBS-014`: a sample record is never acted on by an Action — and every
    act in this runbook moves money."""
    seams["accounts"] = [_account("A-REAL"), _account("A-SAMPLE", sample=True)]
    seams["premises"] = [_premise("A-REAL"), _premise("A-SAMPLE")]
    result = _run()
    assert len(result.subjects) == 2
    assert [one.label for one in result.guarded] == ["A-SAMPLE"]
    assert len(result.records) == 1
    assert _checked(result, mo.STEP_GATHER)["sample_accounts_guarded"] == 1


# ── the report ────────────────────────────────────────────────────────────


def test_every_block_is_one_of_the_twelve(seams):
    seams["accounts"] = [_account("A-1001")]
    seams["premises"] = [_premise("A-1001")]
    assert set(_blocks(_run())) <= set(BLOCK_TYPES)


def test_the_row_carries_the_five_facts_the_card_promises(seams):
    """`RB-127`'s *done looks like*: *"every closing account with its closing
    read due, its final bill issued or waiting, its deposit refunded or carried,
    and the forwarding address captured"*."""
    seams["accounts"] = [_account("A-1001")]
    seams["premises"] = [_premise("A-1001")]
    seams["approved"] = True
    cells = _rows(_run())["A-1001"]["cells"]
    assert cells["read"]["text"] == "Taken"
    assert cells["bill"]["text"] == "Ready to bill"
    assert cells["deposit"]["text"].startswith("To refund")
    assert cells["forwarding"]["text"] == "Captured"
    assert cells["fix"]["to"]


def test_no_rule_id_and_no_database_id_reaches_a_clerk(seams):
    """B14 rules 31 and 32."""
    seams["accounts"] = [_account("A-1001")]
    seams["premises"] = [_premise("A-1001")]
    rows = _blocks(_run())["records"]["rows"]
    drawn = repr([row["cells"] for row in rows])
    assert "BR-" not in drawn
    assert "acct-" not in drawn
    assert rows[0]["meta"]["decided_by_rule"]


def test_a_refusal_sentence_stays_within_six_words(seams):
    """B14 rule 33."""
    for label in mo.ISSUE_LABELS.values():
        assert len(label.split()) <= 6, label


def test_the_empty_state_says_what_was_examined(seams):
    """*No move-outs* over a fortnight and over nothing are different mornings."""
    empty = _blocks(_run())["records"]["empty"]
    assert "0 closing accounts over the next 14 days" in empty["helper"]
    assert empty["title"] == "No move-outs to finish."


def test_the_records_empty_payload_matches_what_the_renderer_reads(seams):
    """`DEF-RBS-4352` one level down: `RecordsBlock.tsx` reads `title` and
    `helper`, and `PAYLOAD_FIELDS` only checks the top-level key `empty`."""
    assert set(_blocks(_run())["records"]["empty"]) == {"title", "helper"}


def test_an_empty_window_is_a_result_and_never_a_stop(seams):
    """This runbook reads the utility's own accounts and can never fail for want
    of a connection. *No move-outs this fortnight* is a good morning."""
    result = _run()
    blocks = _blocks(result)
    assert "chain" not in blocks
    assert blocks["records"]["total"] == 0
    assert "failed" not in repr(result.report).lower()
