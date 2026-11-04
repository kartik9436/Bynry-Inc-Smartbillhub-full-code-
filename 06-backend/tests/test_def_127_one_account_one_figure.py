# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-127 (2026-08-15, CRITICAL) — *"NO SURFACE IN THE PRODUCT CAN
#           TELL A CUSTOMER WHAT THEY OWE — the account reads $0.00 and 'Awaits
#           billing' while the ledger holds an issued, unpaid $108.88."*
#           Screens: S17 (accounts list + header) · S21 (account) · S30 (the
#           bill) · S36 (Revenue & AR)
# Rules:    BR-REP-002 (read-models over journal-line dimensions — NEVER a
#           side-maintained number) · BR-CUS-015 (`accounts.balance` is a CACHE;
#           the ledger is the source of truth) · BR-BIL-035 (the balance-forward
#           block is STAMPED at issue) · BR-LED-007 (AR GL = Σ account balances;
#           ANY drift is a red flag) · BR-REP-001 (every money figure labels its
#           basis) · BR-TEN-042 / DEF-099 (a money figure never travels without
#           its CHAR(3)) · CLAUDE.md rule 1 (tenant scoping) · rule 2 (money)
# Golden:   GT-1 ❄️ FROZEN, finance-signed 2026-08-08 — 684 kWh × $0.12 = 82.08
#           usage + 18.50 base = 100.58, tax 8.25 % = 8.30, **total 108.88**.
#           Imported from tests/test_us_bil_029_assemble.py, never retyped.
# ───────────────────────────────────────────────────────
"""ONE ACCOUNT, ONE FIGURE — every surface that states it must state the same one.

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS, AND IT IS THE TRANSFERABLE HALF OF DEF-127
════════════════════════════════════════════════════════════════════════════
DEF-127's escape route, verbatim from the register: *"the two halves were each
logged separately and NEITHER was wrong on its own. Backend tests assert the
LEDGER; frontend tests assert against MOCKS. **Nothing in this repository
compares two surfaces against each other for ONE account**, so a gap composed of
two individually-known gaps belonged to nobody."*

Four components were each correct against their own fixture and together they
produced one wrong answer, in a browser, about the single most important number
this product holds. `apps/ledger/reporting.py` summed the books correctly.
`apps/customers/selectors.py` served `accounts.balance` correctly — a column
nothing writes. `apps/billing/selectors.py` returned `total_due: None`
correctly, against a docstring that had been true when it was written.
`07-frontend` rendered every one of those faithfully. Every test passed.

**SO THIS TEST IS NOT ABOUT A NUMBER BEING RIGHT. IT IS ABOUT FOUR NUMBERS
BEING THE SAME NUMBER.** It seeds ONE account with ONE issued, unpaid bill and
then asks every surface in the product that claims to state what that customer
owes. **Any surface that disagrees fails**, and the failure names the surface,
the figure it gave and the figure everyone else gave.

════════════════════════════════════════════════════════════════════════════
HOW TO ADD A SURFACE — one row in `SURFACES`, and that is the whole job
════════════════════════════════════════════════════════════════════════════
A `Surface` is a name, a reader and what it is a claim ABOUT. The reader is
handed the seeded world and returns `(amount, currency)` — a Decimal and a
CHAR(3), because a money figure with no currency beside it is a known open
defect in this repo and this check refuses to accept one. Anything that renders
a balance, an amount due or an outstanding total belongs here the day it is
built: a payments outstandings tab, a customer portal, a dunning letter, a
statement PDF. The point is that the list is ONE list.

Two claims are deliberately kept apart, because they are genuinely different
questions and forcing them together would make this check lie:

  * **WHAT THIS ACCOUNT OWES** — the S17 row, the S21 header, the S59 account
    ledger's closing balance, the account's slice of the AR control.
  * **WHAT THIS BILL ASKS FOR** — the bill document's TOTAL DUE (BR-BIL-035).

On the world below they are the same 108.88 and every surface must say so: the
account has exactly one bill and has paid nothing, so "what the bill asks for"
and "what the customer owes" cannot differ without something being wrong. A
second bill or a partial payment would separate them lawfully — see
`test_def_127_tc4` for the case that pins WHY they are allowed to differ and
what still has to hold when they do.

════════════════════════════════════════════════════════════════════════════
PROVED RED BEFORE IT WAS TRUSTED GREEN (hard-won law 7)
════════════════════════════════════════════════════════════════════════════
Each surface was made to disagree BY ONE CENT and this check was watched fail,
naming it. The failures are quoted in the lane report. A check that has only
ever been green is a check nobody has tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Callable

import pytest

from apps.billing import api as billing_api
from apps.billing import issue
from apps.customers import api as customers_api
from apps.customers import services as customer_services
from apps.ledger import api as ledger_api
from apps.ledger import models as ledger_models
from apps.ledger import reporting
from apps.ledger import services as ledger_services
from apps.rating import models as rating_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call
from tests.test_us_bil_005_issue import ISSUED_AT, TEMPLATE_ID, TEMPLATE_VERSION, an_authorised_run
from tests.test_us_bil_029_assemble import GT1_TOTAL, assemble, billing_data
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: ❄️ GT-1's frozen total, imported and never retyped — 108.88. It is also the
#: exact figure DEF-127 was measured on, because `08-qa/01-e2e/stack/
#: seed_e2e_fixture.py` bills GT-1 and the browser read `E2E-10001`.
OWED = GT1_TOTAL

#: The tenant's own two authorities, at the rates `seed_demo` seeds Brazos Bend
#: with from [F] `lookup_defaults.json`. Under B4.4's per-line half-up rounding
#: they reproduce GT-1's signed 8.30 to the cent on GT-1's own 100.58 base:
#:
#:     100.58 × 0.0625 = 6.28625 → 6.29
#:     100.58 × 0.0200 = 2.01160 → 2.01
#:                                 ─────
#:                                  8.30   ← GT-1's frozen tax, B5 line 12
#:
#: Two authorities and not one, because BR-BIL-069 (PO 2026-08-11) makes every
#: tax line resolve its OWN 2200-series liability account and a rule naming no
#: tax refuses at issue. Nothing here rounds; the engine does.
AUTHORITIES = (
    ("State of Texas", Decimal("0.0625"), "2200-01"),
    ("Local", Decimal("0.0200"), "2200-02"),
)

#: The window every period-scoped surface is asked over. Wide enough to contain
#: the bill's book date and stated ONCE, so two surfaces cannot be asked about
#: two different months and appear to disagree for a reason that is not a defect.
WINDOW_START = date(2026, 1, 1)
WINDOW_END = date(2026, 12, 31)

#: What a surface is a claim ABOUT. Kept as data rather than as two functions so
#: a new surface declares which question it answers instead of being filed by
#: whoever adds it.
CLAIM_ACCOUNT_OWES = "what this account owes"
CLAIM_BILL_ASKS = "what this bill asks the customer to pay"


class FakeUser:
    """A signed-in staff user, as `api_call` attaches one."""

    is_authenticated = True
    id = None
    pk = None
    role = "system_admin"


@dataclass(frozen=True)
class World:
    """The one seeded account, its one issued bill, and the tenant they are in."""

    tenant: Any
    actor: Any
    account: Any
    invoice: Any


@dataclass(frozen=True)
class Surface:
    """One place in the product that states a money figure to a human.

    `read` is handed the `World` and returns `(amount, currency)`. Returning the
    currency is not optional: DEF-099 is the standing defect for a money figure
    that leaves the server without its CHAR(3), and a check that accepted a bare
    Decimal would let a surface re-open it while passing.
    """

    name: str
    claim: str
    read: Callable[[World], tuple[Decimal | None, str | None]]


# ═══════════════════════════════════════════════════════════════════════════
# THE WORLD — one account, one bill, issued through the real chain
# ═══════════════════════════════════════════════════════════════════════════
def _tenant_id() -> Any:
    from core import tenancy as core_tenancy

    return core_tenancy.current_tenant_id()


def _an_authority(name: str, rate: Decimal, code: str, actor: Any) -> Any:
    """One tenant-entered authority, its tax and its own 2200-series account.

    The three steps a real tenant's accountant takes on S13, in that order
    (BR-TEN-037 · B5 line 74 ❄️ *"tenant authorities mint their own"* ·
    BR-BIL-069). Nothing in the product does any of them on a tenant's behalf,
    which is why the fixture has to.
    """
    jurisdiction = rating_models.TaxJurisdiction.objects.create(
        tenant_id=_tenant_id(), name=name, authority=name
    )
    account = ledger_models.LedgerAccount.objects.filter(
        tenant_id=_tenant_id(), code=code
    ).first()
    if account is None:
        account = ledger_services.create_tax_authority_account(
            code=code, name=f"Tax payable — {name}", actor=actor
        )
    return rating_models.Tax.objects.create(
        tenant_id=_tenant_id(),
        jurisdiction=jurisdiction,
        name=f"{name} sales tax",
        kind="percent",
        rate=rate,
        liability_gl_account_id=account.id,
    )


def a_billed_account(tenant, actor, *, account_no="E2E-10001", run_key="2026-06|cycle-1") -> World:
    """GT-1 priced by the real engine and ISSUED — the browser's own fixture.

    Deliberately the SAME shape as `08-qa/01-e2e/stack/seed_e2e_fixture.py`:
    stage 1 → stage 2 → rating's priced pass → stage 6 → `issue.issue_invoice`,
    which passes the release gate, allocates the number, derives the due date,
    stamps every line's GL account, stamps BR-BIL-035's balance-forward block
    and posts the balanced journal entry. **No total is typed anywhere in this
    file** — if the engine mis-prices GT-1 the assertion below goes red quoting
    both figures, which is the point of importing `GT1_TOTAL` rather than
    writing 108.88.
    """
    from apps.billing import rating_seam

    taxes = tuple(
        rating_seam.TaxRule(code=name, rate=rate, tax_id=str(_an_authority(name, rate, code, actor).id))
        for name, rate, code in AUTHORITIES
    )
    account = an_account(actor, tenant, account_no=account_no)
    run = an_authorised_run(tenant, actor, key=run_key)
    draft = assemble(tenant, account, run, billing_data(account, taxes=taxes))
    invoice = issue.issue_invoice(
        draft,
        issued_at=ISSUED_AT,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
        actor=actor,
    )
    return World(tenant=tenant, actor=actor, account=account, invoice=invoice)


def _call(view, world: World, **kwargs) -> Any:
    """A real HTTP-shaped call through the view, as the browser reaches it."""
    response = api_call(
        view, "get", user=FakeUser(), role="system_admin", tenant=world.tenant, **kwargs
    )
    assert response.status_code == 200, f"{view.__name__} answered {response.status_code}"
    return response.data


def _decimal(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


# ═══════════════════════════════════════════════════════════════════════════
# THE SURFACES — add a row here the day a new one is built
# ═══════════════════════════════════════════════════════════════════════════
def _s17_row(world: World) -> tuple[Decimal | None, str | None]:
    """S17's Balance cell — `GET /accounts`, the row for this account.

    THE CELL DEF-127 WAS MEASURED ON. It read `$0.00` beside an account holding
    an issued, unpaid 108.88, because it served `accounts.balance` — a cache
    nothing writes.
    """
    body = _call(customers_api.accounts, world, query={"q": world.account.account_no})
    rows = [row for row in body["results"] if row["id"] == str(world.account.id)]
    assert rows, "the account this test seeded is not in its own tenant's list"
    return _decimal(rows[0]["balance"]), rows[0]["balance_currency"]


def _s17_header(world: World) -> tuple[Decimal | None, str | None]:
    """S17's header KPI — `GET /accounts` roll-up, *"$X outstanding"*.

    A TENANT total, not an account one. It belongs in the ACCOUNT-OWES list
    because on a tenant of one account the two are the same claim and the
    header is one of the two places DEF-127 was seen; TC-1 asserts the tenant
    really does hold one account before comparing, and TC-4 is the case where
    they separate.
    """
    body = _call(customers_api.accounts, world)
    rollup = body["rollup"]
    return _decimal(rollup["outstanding"]), rollup["currency"]


def _s21_detail(world: World) -> tuple[Decimal | None, str | None]:
    """S21's account header — `GET /accounts/{id}`, the same figure one screen on."""
    body = _call(customers_api.account_item, world, account_id=str(world.account.id))
    return _decimal(body["balance"]), body["balance_currency"]


def _bill_document(world: World) -> tuple[Decimal | None, str | None]:
    """A19 §1.3's TOTAL DUE — `GET /invoices/{id}`, the bill S30 renders.

    THE SECOND HALF OF DEF-127. It answered `total_due: null` and the screen
    printed an em-dash where the largest number on a utility bill belongs, off a
    payload that was carrying 108.880000 all along.
    """
    body = _call(billing_api.invoice_item, world, invoice_id=str(world.invoice.pk))
    summary = body["summary"]
    return _decimal(summary["total_due"]), summary["currency"]


def _bill_amount_due(world: World) -> tuple[Decimal | None, str | None]:
    """What the bill ASKS FOR — `summary.amount_due` (PO 2026-08-11, *"Level is
    due"*). The total on an ordinary bill, the LEVEL on a budget one; this bill
    is ordinary, so it must equal the total due beside it."""
    body = _call(billing_api.invoice_item, world, invoice_id=str(world.invoice.pk))
    return _decimal(body["summary"]["amount_due"]), body["summary"]["currency"]


def _finance_report(world: World) -> tuple[Decimal | None, str | None]:
    """S36's *Still owed* KPI — `GET /finance/revenue-ar`, the AR control total.

    The only surface of the four that was RIGHT when DEF-127 was measured, and
    it is in this list precisely because being right alone is what let the other
    three be wrong.
    """
    body = _call(
        ledger_api.revenue_ar,
        world,
        query={"from": WINDOW_START.isoformat(), "to": WINDOW_END.isoformat()},
    )
    return _decimal(body["kpis"]["still_owed"]), body["currency"]


def _account_ledger_report(world: World) -> tuple[Decimal | None, str | None]:
    """S59's account ledger — the running balance's CLOSING figure.

    Read through `apps.ledger.reporting` rather than the report endpoint,
    because the closing balance is the figure and the endpoint is a wrapper the
    reports lane owns. It is the one surface that arrives at the number by
    WALKING the movements rather than summing them, so it fails differently.
    """
    with tenant_ctx(world.tenant):
        ledger = reporting.account_ledger(
            world.account.id, start=WINDOW_START, end=WINDOW_END
        )
    return ledger["totals"]["closing_balance"], ledger["currency"]


def _unit_deactivation_guard(world: World) -> tuple[Decimal | None, str | None]:
    """BR-MET-047's money blocker — **DEF-138's surface, added by its own fix.**

    `metering.deactivate_unit` refuses a unit with money outstanding, and the
    figure it refuses ON is a claim about THIS account. It belongs in this list
    for exactly the reason the file exists: it was written, correct and tested,
    and it had never been asked about real money. It read the CACHED
    `accounts.balance` column — which nothing writes — so it answered "no debt"
    for every unit in the product, this one included, and the refusal had never
    once fired. Reading `108.88` here is the whole fix, measured from outside.

    The state form is read rather than the boolean, because a boolean cannot
    state a figure and this check refuses a money claim with no CHAR(3) beside
    it (DEF-099).
    """
    with tenant_ctx(world.tenant):
        state = customer_services.unpaid_balance_state(world.account.unit_id)
    assert state["state"] != "balance_unreadable", (
        "the BR-MET-047 deactivation guard could not read the books on a tree "
        f"where every other surface can: {state.get('unavailable')}"
    )
    return _decimal(state["amount"]), state["currency"]


SURFACES: tuple[Surface, ...] = (
    Surface("S17 account row · Balance", CLAIM_ACCOUNT_OWES, _s17_row),
    Surface(
        "BR-MET-047 unit deactivation guard · blocking balance",
        CLAIM_ACCOUNT_OWES,
        _unit_deactivation_guard,
    ),
    Surface("S17 header KPI · Outstanding", CLAIM_ACCOUNT_OWES, _s17_header),
    Surface("S21 account detail · Balance", CLAIM_ACCOUNT_OWES, _s21_detail),
    Surface("S59 account ledger · closing balance", CLAIM_ACCOUNT_OWES, _account_ledger_report),
    Surface("S36 Revenue & AR · Still owed", CLAIM_ACCOUNT_OWES, _finance_report),
    Surface("S30 bill document · Total due", CLAIM_BILL_ASKS, _bill_document),
    Surface("S30 bill document · Amount due", CLAIM_BILL_ASKS, _bill_amount_due),
)


def _survey(world: World) -> dict[str, tuple[Decimal | None, str | None]]:
    """Every surface's claim, collected before anything is asserted.

    Collected FIRST and asserted after, so a failure reports the whole
    disagreement rather than stopping at the first surface out of step — which
    is the difference between "the bill screen is wrong" and "three screens
    agree and the bill screen does not".
    """
    return {surface.name: surface.read(world) for surface in SURFACES}


def _report(readings: dict[str, tuple[Decimal | None, str | None]]) -> str:
    return "\n".join(
        f"    {name:44s} {'—' if amount is None else amount} {currency or '(no currency!)'}"
        for name, (amount, currency) in readings.items()
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — THE CHECK THE DEFECT ASKS FOR
# ═══════════════════════════════════════════════════════════════════════════
def test_def_127_tc1__every_surface_states_the_same_figure(brazos, dana):
    """ONE account owing GT-1's ❄️ 108.88, and seven surfaces asked in one run.

    **ANY SURFACE THAT DISAGREES FAILS.** The assertion is on the SET of
    distinct answers, not on each answer against a constant, because the defect
    was never a wrong constant — it was four right-looking answers that were not
    the same answer.

    The figure is also checked against GT-1 itself, so a world where every
    surface agreed on the WRONG number cannot pass quietly.
    """
    with tenant_ctx(brazos):
        world = a_billed_account(brazos, dana)
        # The header is a TENANT total. Comparing it with a per-account figure
        # is only sound on a tenant of one account, so that is checked and not
        # assumed — TC-4 is the case where the two legitimately separate.
        assert _call(customers_api.accounts, world)["rollup"]["accounts"] == 1

    readings = _survey(world)

    distinct = {amount for amount, _currency in readings.values()}
    assert distinct == {OWED}, (
        "SURFACES DISAGREE ABOUT ONE ACCOUNT'S MONEY (DEF-127).\n"
        f"  expected every surface to state {OWED} (GT-1 ❄️), and they said:\n"
        f"{_report(readings)}"
    )

    currencies = {currency for _amount, currency in readings.values()}
    assert currencies == {"USD"}, (
        "a money figure left the server without its CHAR(3), or with the wrong one "
        f"(DEF-099 / CLAUDE.md rule 2):\n{_report(readings)}"
    )


def test_def_127_tc2__the_row_reads_the_books_and_not_the_cache(brazos, dana):
    """THE CAUSE, pinned so it cannot come back by a different route.

    `accounts.balance` stays **0.000000** through all of this — nothing writes
    it and this fix deliberately did not start. So a row serving the cache reads
    zero and a row serving the ledger reads 108.88, and the two are asserted
    side by side: the test would go red the day somebody "helpfully" points
    `balance` back at the column, even if a migration had begun filling it,
    because `balance_source` names where the figure came from.

    BR-REP-002 is the rule: *read-models over journal-line dimensions … never a
    side-maintained number*. A side-maintained number nobody maintains is its
    worst case, and it is what a customer read as "$0.00 owed".
    """
    with tenant_ctx(brazos):
        world = a_billed_account(brazos, dana)
        world.account.refresh_from_db()
        assert world.account.balance == Decimal("0"), (
            "the CACHE is still unwritten — if this ever changes, the row must still "
            "derive from the books (BR-CUS-015: the ledger is the source of truth)"
        )
        body = _call(customers_api.accounts, world, query={"q": world.account.account_no})

    row = next(r for r in body["results"] if r["id"] == str(world.account.id))
    assert Decimal(row["balance"]) == OWED
    assert row["balance_source"] == "ledger"
    assert row["balance_basis"] == "posting"  # BR-REP-001 — the basis is DATA
    assert row["balance_cached"] == "0.000000"  # served as what it is, read by nobody
    # US-CUS-001 §5 "Last bill": the row said "Awaits billing" about a billed
    # account until 2026-08-15, because the seam resolved the wrong module
    # attribute (DEF-035's shape, one function along).
    assert row["last_bill_at"] == ISSUED_AT.date().isoformat()


def test_def_127_tc3__the_bill_prints_its_total_due_from_the_stamp(brazos, dana):
    """BR-BIL-035's block, stamped at issue and READ on the way out.

    The four figures foot — `previous balance − payments received + current
    charges = total due` — and nothing recomputes them here or in the read
    model: the arithmetic happened once, inside the issue transaction, over an
    immutable record.

    ❄️ Worked on THIS bill: `0.00 − 0.00 + 108.88 = 108.88`. The account has no
    earlier bill, so the two middle lines are zero — and OQ-217 is exactly the
    question of which window they are read over. The bill says which one it was
    written under, which is why `basis` is asserted rather than assumed.
    """
    with tenant_ctx(brazos):
        world = a_billed_account(brazos, dana)
        body = _call(billing_api.invoice_item, world, invoice_id=str(world.invoice.pk))

    summary = body["summary"]
    previous = Decimal(summary["previous_balance"])
    payments = Decimal(summary["payments_credits"])
    current = Decimal(summary["current_charges"])
    assert current == OWED
    assert previous - payments + current == Decimal(summary["total_due"]), (
        "BR-BIL-035's own arithmetic does not foot on the stamped block: "
        f"{previous} − {payments} + {current} ≠ {summary['total_due']}"
    )
    assert summary["currency"] == "USD"
    # OQ-217 was ruled 2026-10-01 (BR-BIL-1065) — the bill RECORDS which
    # reading the bill was written under, so the PO's ruling can be applied to
    # future bills without guessing at the history of past ones.
    assert summary["basis"] == issue.BALANCE_FORWARD_BASIS
    assert summary["basis_oq"] == "OQ-217"


def test_def_127_tc4__a_bill_and_a_balance_are_allowed_to_differ_and_still_tie(brazos, dana):
    """WHEN the two claims separate — and what must STILL hold when they do.

    A second issued bill makes *what this bill asks for* (108.88) and *what this
    account owes* (217.76) different numbers, lawfully. This case exists so that
    TC-1's equality is understood as a property of a one-bill world and not as a
    rule somebody might later "fix" by making the bill screen show the account
    balance — which would be a new defect wearing this one's clothes.

    What must still hold, and is asserted: every ACCOUNT-OWES surface agrees
    with every other, the account's own total is the SUM of its issued bills,
    and each bill still states its own.
    """
    with tenant_ctx(brazos):
        world = a_billed_account(brazos, dana)
        second = a_billed_account(
            brazos, dana, account_no="E2E-10002", run_key="2026-07|cycle-1"
        )
        assert second.account.id != world.account.id

    readings = _survey(world)
    owed = {
        name: amount
        for name, (amount, _currency) in readings.items()
        if name in {s.name for s in SURFACES if s.claim == CLAIM_ACCOUNT_OWES}
    }
    # This account's own position is untouched by the other account's bill …
    per_account = {
        name: amount
        for name, amount in owed.items()
        if not name.startswith("S17 header") and not name.startswith("S36")
    }
    assert set(per_account.values()) == {OWED}, (
        "a second account's bill moved this account's balance:\n" f"{_report(readings)}"
    )
    # … and the TENANT-WIDE figures are the sum of both, on both surfaces.
    assert readings["S17 header KPI · Outstanding"][0] == OWED * 2
    assert readings["S36 Revenue & AR · Still owed"][0] == OWED * 2


def test_def_127_tc5__a_book_that_cannot_answer_says_so_and_never_says_zero(brazos, dana):
    """THE RULE THE WHOLE DEFECT TURNS ON: absent is not spelled like zero.

    A tenant whose ledger publishes no per-account read is a real deployment
    state (a partial rollout), and it is simulated the way every seam test in
    this repo simulates one — by making the by-name resolution answer None,
    which is precisely what an unbuilt lane looks like at call time.

    The row must then say it CANNOT TELL, with a reason. It must not say
    `0.000000`, because `$0.00` on an account screen is a claim a customer acts
    on and a clerk repeats on the phone.
    """
    from apps.customers import seams as customers_seams

    with tenant_ctx(brazos):
        world = a_billed_account(brazos, dana)

    original = customers_seams.resolve
    try:
        customers_seams.resolve = lambda module, attribute, kind="services": (
            None
            if attribute == customers_seams.AR_POSITIONS_READ
            else original(module, attribute, kind)
        )
        with tenant_ctx(brazos):
            body = _call(customers_api.accounts, world, query={"q": world.account.account_no})
    finally:
        customers_seams.resolve = original

    row = next(r for r in body["results"] if r["id"] == str(world.account.id))
    assert row["balance"] is None, "an unreadable book answered a figure"
    assert row["balance_source"] is None
    codes = [gap["code"] for gap in row["balance_unavailable"]]
    assert codes == ["ledger_publishes_no_per_account_ar_position"]
    assert body["rollup"]["outstanding"] is None
    assert body["rollup"]["outstanding_unavailable"], "the header claimed nothing was owed"


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-127 (12-governance/10-defect-log.csv) — the PREVENT half, verbatim:
#   "a check that takes ONE seeded account and asserts the same money figure on
#    every surface that claims to state it - the account row, the account header,
#    the bill document and the finance report. Any surface that disagrees fails."
# generated: 2026-08-16 by the balance lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(the browser half is 07-frontend/e2e/DEF-127-one-figure.spec.ts) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: live Postgres (config.settings.local) — every surface driven RED by a
#   one-cent disagreement before being trusted green; failures quoted in the lane report
# exceptions: `apps/payments/outstandings.py` computes a balance FROM BILLS rather
#   than from the books and is a fifth surface this list does not yet carry — it is
#   a different derivation of the same figure (BR-REP-002's exact hazard) and
#   wiring it here without first ruling on which derivation wins would make this
#   check enforce a choice nobody has made. REPORTED as its own defect row, not
#   worked around · `aging` stays null: BR-CUS-016's buckets need open-invoice due
#   dates that no module publishes (apps/ledger/reporting.GAP_AGING_NEEDS_DUE_DATES)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
