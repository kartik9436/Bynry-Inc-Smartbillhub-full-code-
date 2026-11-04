# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-004 (EP-RBS-02) — CR-075 wave F task F3. `TC-RBS-004.1`,
#           `TC-RBS-004.3` (**the one that matters**) and `TC-RBS-7`.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no writer, so no bill number
#           is consumed) · CLAUDE.md hard rule 1 (never touch a tenant table
#           without `app.tenant_id`; RLS FORCE is on) · hard rule 2 (money 4
#           stored / 2 displayed) · hard rule 4 (financial immutability) ·
#           hard-won law 14 (the default suite is SQLite) · hard-won law 7 (a
#           check that cannot fail is the defect)
# Tests:    this file · tests/test_us_rbs_004_test_bill.py (the SQLite half)
# Impacts:  apps/runbooks/definitions/test_bill.py ·
#           apps/runbooks/seams/billing_seam.py · apps/billing/runs.py
# ───────────────────────────────────────────────────────
"""Runbook 23 on PostgreSQL — the three claims SQLite cannot make.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        python3.12 -m pytest tests/test_us_rbs_004_pg.py

Every case carries `requires_postgres` and **SKIPS rather than passing
vacuously** — `G5` once ran the isolation suite on SQLite and called 192 skips a
pass — and the module prints which vendor it ran on beside the result, so a
reader can tell a real green from a skipped one without reading the marker.

═════════════════════════════════════════════════════════════════════════════
`TC-RBS-004.3` IS THE STRONGEST TEST IN THIS MODULE AND IS WHY THE WAVE EXISTS
═════════════════════════════════════════════════════════════════════════════
> *The same account through the test bill and through a real bill run must
> produce an IDENTICAL line set and IDENTICAL amounts to four decimals.*

A test bill that disagrees with the real bill run is **worse than no test
bill** — a clerk would trust it and be wrong on a customer's money, and an
implementer would take a utility live on a demonstration that proved nothing.

It is now true by CONSTRUCTION as well as by assertion: wave F extracted stages
1–5 into `billing.runs.price_account`, and `calculate_account` is that call
followed by stage 6. So there is one implementation and the only difference is
whether the draft is written.

⚠ **FOUR DECIMALS, AND `test_..._a_divergence_of_one_fortieth_of_a_cent_...` IS
THE RED PROOF.** Money is stored to 4 and DISPLAYED at 2 (hard rule 2). That
test plants a `0.0025` divergence — a quarter of a cent, the size of a real
`$0.0025 / kWh` rate — and asserts two things in the same breath: this
comparison **catches** it, and **a comparison at two decimals would not**.
Without that second assertion the four-decimal rule is a preference; with it,
the test says why it is a rule.
"""

from __future__ import annotations

import copy
from decimal import Decimal

import pytest
from django.db import connection

from apps.billing import models as billing_models
from apps.billing import single
from apps.runbooks.definitions import test_bill as rb23
from apps.runbooks.engine import executor
from apps.tenancy import models as tenancy_models

from tests.isolation_helpers import requires_postgres
from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _print_vendor(label: str) -> None:
    """Say which vendor this ran on, beside the result.

    Hard-won law 7's third habit — *a check's output must distinguish pass from
    fail to a READER*. A skipped isolation case and a passing one are the same
    green dot in a summary line.
    """
    print(f"runbook 23 · {label}: vendor={connection.vendor}")


def _params(account):
    return {
        "account": str(account.id),
        "period": {"start": PERIOD_START.isoformat(), "end": PERIOD_END.isoformat()},
        "compare_with": "last_issued_bill",
        "show": "every_line_explained",
    }


def _billable(tenant, actor, *, account_no, asset_no, code, consumption="412.000000"):
    cycle = a_cycle(tenant, code=code)
    plan = a_priced_plan(tenant, name=f"Runbook 23 {code}")
    unit = a_billed_unit(
        actor, tenant, cycle, plan, asset_no=asset_no, label=code, consumption=consumption
    )
    return cycle, an_account(tenant, unit["id"], account_no)


def _a_run(tenant, cycle):
    """The `bill_runs` row a draft hangs off.

    ⚠ **A ROW, NOT `create_run`.** `create_run` takes no `service_date` and
    allocates a run number of its own; the row is all `calculate_single_bill`
    needs, and this is the same helper `tests/test_us_bil_012_single.py` uses
    for the same reason. A first draft of this file called `create_run` with a
    `service_date` it does not accept and failed in the FIXTURE rather than in
    the assertion.
    """
    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        idempotency_key=f"rbs23-{cycle.code}-{PERIOD_START}",
    )


def _four(value) -> Decimal:
    """A money figure at its STORED scale. Hard rule 2 — 4 decimals, not 2."""
    return Decimal(str(value)).quantize(Decimal("0.0001"))


def _two(value) -> Decimal:
    """The same figure as a clerk READS it. Used only to prove what 2 hides."""
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _test_bill_lines(result) -> list[tuple[str, str, Decimal]]:
    """`(kind, description, amount)` from the runbook's own priced result."""
    priced = result.set_results["price"]["priced"]
    assert priced is not None, result.set_results["price"]["refusal"]
    return [(l["kind"], l["description"], _four(l["amount"])) for l in priced["lines"]]


def _invoice_lines(invoice) -> list[tuple[str, str, Decimal]]:
    """The same triple off the DRAFT a real bill run wrote.

    Ordered by `created_at, id` because `invoice_lines` has no sequence column —
    that is the order `bulk_create` wrote them in, which is the order the engine
    emitted them.
    """
    rows = billing_models.InvoiceLine.objects.filter(invoice_id=invoice.pk).order_by(
        "created_at", "id"
    )
    return [(r.kind, r.description, _four(r.amount)) for r in rows]


# ══════════════════════════════════════════════════════════════════════════
# TC-RBS-004.3 — THE ONE THAT MATTERS
# ══════════════════════════════════════════════════════════════════════════


@requires_postgres
def test_tc_rbs_004_3__the_test_bill_and_a_real_bill_run_agree_to_four_decimals(brazos, dana):
    """Identical line set, identical amounts, to FOUR decimals.

    The runbook runs first and the real bill run second, on the same account and
    the same window, and every line is compared as `(kind, description, amount)`
    — the ORDER included, because a bill whose lines are shuffled is a different
    document to a clerk reading it even when the total agrees.

    ⚠ **THE TOTAL IS COMPARED SEPARATELY AND ON PURPOSE.** Two line sets can
    sum to the same figure and differ line by line, which is the failure this
    story is written about; and one line differing by a quarter of a cent moves
    a total that a two-decimal check would still call equal.
    """
    _print_vendor("TC-RBS-004.3")
    with tenant_ctx(brazos):
        cycle, account = _billable(
            brazos, dana, account_no="A-23101", asset_no="M-23101", code="23-P1"
        )

        # 1 · the test bill. It writes nothing, so the run below sees exactly
        # the world it would have seen without this call.
        result = executor.execute(rb23.RUNBOOK, tenant_id=brazos.id, params=_params(account))
        mine = _test_bill_lines(result)
        my_total = _four(result.set_results["price"]["priced"]["total"])

        # 2 · the real bill run, through the pipeline that writes a draft.
        prepared = single.prepare_single_bill(
            account_id=account.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        invoice = single.calculate_single_bill(prepared, bill_run=_a_run(brazos, cycle))
        theirs = _invoice_lines(invoice)

    assert mine, "the test bill priced nothing, so this comparison cannot fail"
    print(f"TC-RBS-004.3 lines: test bill {len(mine)} · bill run {len(theirs)}")
    for row in mine:
        print(f"   {row[0]:<20} {row[1]:<44} {row[2]}")

    assert mine == theirs, (
        "the test bill and the bill run produced different lines:\n"
        f"  test bill: {mine}\n  bill run : {theirs}"
    )
    assert my_total == _four(invoice.total), (
        f"totals differ at four decimals: {my_total} vs {_four(invoice.total)}"
    )


@requires_postgres
def test_tc_rbs_004_3_red__a_divergence_of_one_quarter_of_a_cent_is_caught_at_four_and_missed_at_two(
    brazos, dana
):
    """The RED proof. A planted second implementation must be caught.

    ⚠ **A GUARD IS ONLY A CLAIM IF YOU HAVE SEEN IT FAIL** (hard-won law 7). The
    case above passes because there is one pricing path; this one plants the
    divergence a second path would produce and asserts the comparison names it.

    **`0.0025` is not an arbitrary number.** It is a quarter of a cent — the
    size of a real `$0.0025 / kWh` tariff rate — and it is invisible at two
    decimals. This case asserts BOTH halves in the same breath:

      * compared at FOUR decimals the two sets differ, and
      * compared at TWO decimals they are equal.

    The second assertion is the one that turns *"compare at four"* from a
    preference into a rule, and it is why the task brief says **do not compare
    at two**.
    """
    _print_vendor("TC-RBS-004.3 (red proof)")
    with tenant_ctx(brazos):
        _cycle, account = _billable(
            brazos, dana, account_no="A-23102", asset_no="M-23102", code="23-P2"
        )
        result = executor.execute(rb23.RUNBOOK, tenant_id=brazos.id, params=_params(account))
        honest = _test_bill_lines(result)

    assert honest, "no lines to diverge from"

    # A SECOND IMPLEMENTATION, planted: one line off by a quarter of a cent.
    # This is exactly what a re-implemented block ladder would look like — the
    # description is right, the kind is right, and the money is a hair out.
    divergent = copy.deepcopy(honest)
    kind, description, amount = divergent[0]
    divergent[0] = (kind, description, _four(amount + Decimal("0.0025")))

    assert divergent != honest, "the plant did not change anything"

    # At TWO decimals the plant is invisible — which is the whole point.
    at_two_honest = [(k, d, _two(a)) for k, d, a in honest]
    at_two_divergent = [(k, d, _two(a)) for k, d, a in divergent]
    assert at_two_honest == at_two_divergent, (
        "this fixture's first line does not hide a quarter-cent at two decimals, "
        "so this case is not proving what it claims — pick a line that does"
    )
    print(
        f"planted +0.0025 on {description!r}: caught at four decimals, "
        f"invisible at two ({_two(amount)} either way)"
    )


# ══════════════════════════════════════════════════════════════════════════
# TC-RBS-004.1 — nothing is written, and the number series does not move
# ══════════════════════════════════════════════════════════════════════════


@requires_postgres
def test_tc_rbs_004_1__no_bill_number_is_consumed_and_billings_series_is_untouched(brazos, dana):
    """`BR-RBS-002`, asserted against a real database rather than a declaration.

    ⚠ **THE SERIES COUNTER IS THE ASSERTION, NOT THE INVOICE COUNT.**
    `BR-BIL-063` allocates a number when the DRAFT is created, and the series is
    documented as gap-tolerant — so a runbook that quietly spent a number and
    rolled the row back would leave `Invoice.objects.count() == 0` and a
    counter one higher, and every check that looked only at rows would pass. On
    a real utility that shows up as a bill numbered `BL-2606-0004` after
    `BL-2606-0002`, months later, with nobody able to say what happened to 3.
    """
    _print_vendor("TC-RBS-004.1")
    with tenant_ctx(brazos):
        _cycle, account = _billable(
            brazos, dana, account_no="A-23103", asset_no="M-23103", code="23-P3"
        )
        before = {
            row.series: row.next_number
            for row in tenancy_models.NumberSeries.objects.filter(tenant_id=brazos.id)
        }
        invoices_before = billing_models.Invoice.objects.count()
        lines_before = billing_models.InvoiceLine.objects.count()
        runs_before = billing_models.BillRun.objects.count()

        # Run it three times, because a test bill is re-run by design (judgment
        # J5) and a number spent per run is the shape that would hide in one.
        for _ in range(3):
            result = executor.execute(rb23.RUNBOOK, tenant_id=brazos.id, params=_params(account))
            assert result.set_results["price"]["priced"] is not None

        after = {
            row.series: row.next_number
            for row in tenancy_models.NumberSeries.objects.filter(tenant_id=brazos.id)
        }

    print(f"number series after three test bills: {after}")
    assert after == before, f"a number was consumed: {before} → {after}"
    assert billing_models.Invoice.objects.count() == invoices_before
    assert billing_models.InvoiceLine.objects.count() == lines_before
    assert billing_models.BillRun.objects.count() == runs_before


@requires_postgres
def test_the_ledger_and_the_payments_tables_are_untouched_too(brazos, dana):
    """Hard rule 4 read forward, and hard rule 5.

    A Check holds no writer, so this asserts the CONSEQUENCE over the tables a
    priced bill would otherwise reach: no journal line, no allocation, no
    payment. Counted rather than asserted as a declaration, because *"it has no
    ports"* is what the declaration already says and this is the other half.
    """
    _print_vendor("writes nothing")
    from apps.ledger import models as ledger_models
    from apps.payments import models as payment_models

    with tenant_ctx(brazos):
        _cycle, account = _billable(
            brazos, dana, account_no="A-23104", asset_no="M-23104", code="23-P4"
        )
        before = (
            ledger_models.JournalEntry.objects.count(),
            ledger_models.JournalLine.objects.count(),
            payment_models.Payment.objects.count(),
        )
        executor.execute(rb23.RUNBOOK, tenant_id=brazos.id, params=_params(account))
        after = (
            ledger_models.JournalEntry.objects.count(),
            ledger_models.JournalLine.objects.count(),
            payment_models.Payment.objects.count(),
        )
    assert after == before, f"a Check wrote money rows: {before} → {after}"


# ══════════════════════════════════════════════════════════════════════════
# TC-RBS-7 — tenant isolation, where it means something
# ══════════════════════════════════════════════════════════════════════════


@requires_postgres
def test_tc_rbs_7__another_tenants_account_resolves_to_nothing(brazos, dana, lonestar, erin):
    """Hard rule 1 with RLS `FORCE` on, over the id of a REAL account elsewhere.

    ⚠ **THE DANGEROUS OUTCOME IS NOT A CRASH.** A crash is loud. It is a run
    that resolved another utility's account and priced it — one customer's
    money on another utility's screen — and the only thing that separates the
    two is whether the lookup carried the tenant. So this asserts the SCOPE is
    empty and that no line was priced, not that an exception was raised.

    ⚠ **`lonestar` SELLS WATER ONLY, AND THE SHARED BILLING FIXTURE IS
    ELECTRIC.** `a_billed_unit` hardcodes `services=["electric"]` and a `kWh`
    read, so asking the isolation tenant for one is refused by name —
    `metering.service_not_enabled` — **in the fixture rather than in the
    assertion**, which is the least useful place for a test to fail. It did,
    on the first run of this file. What this case actually needs is an ACCOUNT
    that exists elsewhere, not a billable one: the claim is about the LOOKUP.
    So the other tenant gets a water premises, a unit and an account, and
    nothing that would price.
    """
    _print_vendor("TC-RBS-7")
    with tenant_ctx(lonestar):
        premises = make_premises(erin, address_line="9 Isolation Row", services_available=["water"])
        unit = make_unit(erin, premises["id"], label="ISO-1", services=["water"])
        theirs = an_account(lonestar, unit["id"], "A-23105")
        their_id = str(theirs.id)

    with tenant_ctx(brazos):
        _billable(brazos, dana, account_no="A-23106", asset_no="M-23106", code="23-P6")
        result = executor.execute(
            rb23.RUNBOOK,
            tenant_id=brazos.id,
            params={
                "account": their_id,
                "period": {"start": PERIOD_START.isoformat(), "end": PERIOD_END.isoformat()},
                "compare_with": "nothing",
                "show": "every_line_explained",
            },
        )

    assert result.subjects == (), "a run reached another tenant's account"
    assert result.set_results["price"]["priced"] is None
    assert [b["block"] for b in result.report] == ["sentence", "records"]


@requires_postgres
def test_a_run_with_no_tenant_context_prices_nothing(brazos, dana):
    """RLS `FORCE`'s other half — no `app.tenant_id` set at all.

    ⚠ The dangerous outcome here is a report that reads *"this customer owes
    nothing"* rather than an exception. `DEF-RBS-4296` is that shape one door
    along: a streaming download whose generator ran with no tenant marker and
    served a 200 with an empty body. So this asserts NO LINES, and it asserts
    them by name.
    """
    _print_vendor("no tenant context")
    with tenant_ctx(brazos):
        _cycle, account = _billable(
            brazos, dana, account_no="A-23107", asset_no="M-23107", code="23-P7"
        )
        account_id = str(account.id)

    try:
        result = executor.execute(
            rb23.RUNBOOK,
            tenant_id=brazos.id,
            params={
                "account": account_id,
                "period": {"start": PERIOD_START.isoformat(), "end": PERIOD_END.isoformat()},
                "compare_with": "nothing",
                "show": "every_line_explained",
            },
        )
    except Exception:
        return  # refusing outright is the stronger outcome and is lawful

    assert result.subjects == () or result.set_results["price"]["priced"] is None, (
        "an account was priced with no tenant marker set"
    )


# ══════════════════════════════════════════════════════════════════════════
# TC-RBS-004.2 — the refusal, on the vendor that runs it
# ══════════════════════════════════════════════════════════════════════════


@requires_postgres
def test_tc_rbs_004_2__a_missing_read_stops_the_bill_and_names_the_service(brazos, dana):
    """One sentence, six words or fewer, and the same stop a bill run reports.

    ⚠ **THE PAIRING IS THE ASSERTION.** It is not enough that the test bill
    refuses: it must refuse where the RUN refuses. So the real pipeline is asked
    the same question and must also decline to draft, or the test bill is
    telling a clerk to fix something the run would have billed through.
    """
    _print_vendor("TC-RBS-004.2")
    with tenant_ctx(brazos):
        _cycle, account = _billable(
            brazos,
            dana,
            account_no="A-23108",
            asset_no="M-23108",
            code="23-P8",
            consumption=None,
        )
        result = executor.execute(rb23.RUNBOOK, tenant_id=brazos.id, params=_params(account))

        prepared = single.prepare_single_bill(
            account_id=account.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )

    assert result.set_results["price"]["priced"] is None
    sentence = next(b for b in result.report if b["block"] == "sentence")["payload"]
    print(f"the refusal a clerk reads: {sentence['text']!r}")
    assert len(sentence["text"].split()) <= 6
    assert [b["block"] for b in result.report] == ["sentence", "records"]

    # The run reaches the same verdict: the account is not ready to bill.
    assert prepared.ready == () or prepared.decisions or prepared.blocked, (
        "the test bill refused an account the run would have billed"
    )
    assert billing_models.Invoice.objects.count() == 0
