# ── Trace ──────────────────────────────────────────────
# Change:   CR-136-BRC07 §3.3 / task P2.21 — a drawer difference reaches the
#           books. PO ruling 2026-09-23, over the payments blueprint's own
#           "The ledger: Nothing — counting is not a posting".
# Story:    US-LED-005 (the chart and the GL designations)
#           Screens: S56 (the chart) · the six Counter screens (P2.6)
# Rules:    BR-LED-796 (NEW — ONE cash over/short account serves both
#           directions, seeded at 6850, resolved by DESIGNATION) ·
#           BR-LED-040 (code and type frozen; name and designation editable) ·
#           BR-LED-042 (one LIVE account per designation) · US-LED-005 rule 1
#           (the tenant's chart is the tenant's) · CLAUDE.md hard rules 1, 4, 5, 7
# Golden:   NONE. No figure here comes from B4 or B5 and none is edited. The
#           $12.0000 is the PO's own worked case of 2026-09-23 and is carried
#           here as ARITHMETIC ONLY — this file posts nothing (`P2.22` owns
#           that) and asserts no journal line.
# ───────────────────────────────────────────────────────
"""`6850 Cash over and short` exists, and every tenant can resolve it.

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE IS FOR, AND WHAT IT DELIBERATELY DOES NOT TEST
════════════════════════════════════════════════════════════════════════════
`P2.21` is the ACCOUNT. `P2.22` is the POSTING, in payments, through the ledger
posting service (hard rule 5). So nothing here writes a journal line, and the
PO's $12.0000 appears only as the arithmetic that explains why ONE account
serves both directions:

    $12.0000 SHORT                        $12.0000 OVER
    DR 6850 cash over and short 12.0000   DR 1010 undeposited funds 12.0000
    CR 1010 undeposited funds   12.0000   CR 6850 cash over and short 12.0000

Both directions name the SAME two designations, which is the whole reason there
is no second `cash_over` pointer — and `test_one_account_serves_both_directions`
is what stops one arriving later.

════════════════════════════════════════════════════════════════════════════
RED FIRST — every line below is real output, copied off the run
════════════════════════════════════════════════════════════════════════════
**1 · the constant without the migration**, which is the whole reason
`ledger/0016` exists. ⚠ **THIS ONE WAS NOT MEASURED THROUGH PYTEST AND THE
DIFFERENCE IS STATED RATHER THAN GLOSSED** (hard-won law 7): the harness drops
its test database at the end of a run, so there was none standing at the
`ledger/0015` constraint to point this file at. It was taken instead from a
clone of a seeded template whose CHECK lists seventeen designations and not
`cash_over_short`, running the INSERT the seed itself makes — PostgreSQL's own
refusal, which is the thing the migration exists to move::

    ERROR:  new row for relation "ledger_accounts" violates check constraint
            "ck_ledger_accounts_designation"

Applying this migration's own DDL — from `manage.py sqlmigrate ledger 0016`,
not hand-written — the same INSERT returns the row, and a typo
(`cash_over_shrot`) is still refused with the same message. **Widened, not
loosened**, which is what `test_cr136_p221__the_check_constraint_accepts_it_and_
still_refuses_a_typo` asks of the running database on every run from here.

**2 · the seed row absent from `SEED_CHART`** — the shape a lane that added the
designation and forgot the account would ship::

    E  AssertionError: cash_over_short resolves to nothing on a freshly
       provisioned tenant, so the first counted close of the product's life
       would refuse
    E  assert None is not None

**3 · the top-up missing** — the shape hard-won law 4 is about, proved by
deleting the row from a live tenant's chart and calling the posting's door::

    E  AttributeError: module 'apps.ledger.services' has no attribute
       'ensure_cash_over_short_account'

**4 · the top-up taking an account that is somebody else's**, which is the one
failure that would be SILENT — a drawer difference landing in a utility's own
`6850 Fleet fuel`::

    E  AssertionError: the top-up designated an account it did not create
    E  assert 'Fleet fuel' == 'Cash over and short'
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.ledger import chart, models as ledger_models
from apps.ledger import selectors as ledger_selectors
from apps.ledger import services as ledger_services
from apps.tenancy import services as tenancy_services
from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ════════════════════════════════════════════════════════════════════════════
# 1 · THE CHART ITSELF — no database, no tenant
# ════════════════════════════════════════════════════════════════════════════
def test_cr136_p221__6850_is_seated_between_the_two_signed_expense_codes():
    """The row, pinned field by field, in the PO's own words.

    Pinned rather than merely present because a rename is half of what a
    finance re-sign would cover (the same reason `4760`'s row is pinned one
    file over), and because `type` decides which side of a trial balance a
    drawer difference is printed on.
    """
    rows = {row.code: row for row in chart.SEED_CHART}
    assert "6850" in rows, "the account the 2026-09-23 ruling asked for is not on the chart"
    row = rows["6850"]
    assert (row.name, row.type, row.designation, row.category) == (
        "Cash over and short",
        "expense",
        chart.CASH_OVER_SHORT,
        chart.CAT_OPERATING_EXPENSES,
    )
    # ⚠ `signed=False` — the PO ruled that the POSTING needs a home, and a
    # posting ruling is not a finance signature on a chart row. B5 line 74 is
    # ❄️ FROZEN and was NOT edited; the re-sign route is HUMAN-GUIDE §6.
    assert row.signed is False
    assert "6850" in chart.PENDING_FINANCE_RE_SIGN
    assert "6850" in chart.PENDING_FINANCE_RE_SIGN_SOURCE, (
        "the greppable statement of where this signature has to come from does not "
        "mention the code it is owed for"
    )

    # SEATED, not merely present: the CR says "between 6800 Bank fees and 6900
    # Bad debt", and `_create_missing_accounts` inserts in this order, so the
    # order is what an audit reader scrolls.
    codes = [r.code for r in chart.SEED_CHART]
    assert codes[codes.index("6800") + 1] == "6850"
    assert codes[codes.index("6850") + 1] == "6900"


def test_cr136_p221__one_account_serves_both_directions():
    """*Cash over AND short* — one pointer, one account, both signs.

    An over on Monday and a short on Tuesday net against each other in the
    account a utility reads as *"how far out are my drawers"*. Split across two
    accounts neither figure answers that question, so a second designation is
    refused here rather than discovered after somebody has posted to both.
    """
    over_short = [d for d in chart.GL_DESIGNATIONS if "over" in d or "short" in d]
    assert over_short == [chart.CASH_OVER_SHORT], (
        "a second over/short designation arrived; the 2026-09-23 ruling is ONE account, "
        "both directions"
    )
    homes = [row.code for row in chart.SEED_CHART if row.designation == chart.CASH_OVER_SHORT]
    assert homes == ["6850"]

    # The other half of the pair is the account taking money already debits.
    # ⚠ `1010`, NOT `1000` — the bank only ever receives what was in the drawer,
    # so the difference must leave `1010` BEFORE the deposit clears it.
    undeposited = [
        row.code for row in chart.SEED_CHART if row.designation == chart.UNDEPOSITED_FUNDS
    ]
    assert undeposited == ["1010"]
    # Arithmetic, four decimals, from the PO's worked case (hard rule 2).
    assert Decimal("1240.0000") - Decimal("1228.0000") == Decimal("12.0000")
    assert Decimal("1252.0000") - Decimal("1240.0000") == Decimal("12.0000")


def test_cr136_p221__6850_collides_with_no_other_seeded_code():
    """Every code the product ever seeds, checked for a duplicate in one pass.

    The six seed tuples are written in six places and `_create_missing_accounts`
    skips a code the tenant already has — so a code claimed twice would not
    raise, it would silently hand the second row's designation to the first
    row's account. That is the failure this asks about, over the whole set
    rather than over `6850` alone.
    """
    every_row = (
        chart.SEED_CHART
        + chart.COST_OF_SERVICE_CHART
        + chart.WIDENED_COST_CHART
        + chart.UTILITY_BOOKS_CHART
        + chart.PERIOD_MATCHING_CHART
        + chart.ALLOWANCE_CHART
    )
    codes = [row.code for row in every_row]
    assert len(codes) == len(set(codes)), sorted({c for c in codes if codes.count(c) > 1})
    assert codes.count("6850") == 1
    # ⚠ **NO TOTAL IS PINNED HERE ON PURPOSE.** The chart grows whenever the PO
    # rules a new account in, and a count in THIS file would go red on every one
    # of them for a reason that has nothing to do with drawers — which is
    # `DEF-LED-6224` exactly, filed by this lane the same day. The chart's size
    # is `tests/test_us_led_005_gl_designations.py`'s to own; what this case
    # owns is that no two rows can claim one code.
    # The 2200 series is seeded to NOBODY (BR-BIL-069), so a minted tax
    # authority cannot collide with this either.
    assert not [c for c in codes if c.startswith("22")]


def test_cr136_p221__the_designation_is_in_the_closed_set_and_is_seeded():
    """The pointer is ruled, and it has a home at PROVISIONING rather than on
    first use — which is what makes it different from `1290`.

    `DESIGNATED_ON_FIRST_USE` names the three designations that legitimately do
    NOT resolve on a fresh tenant. `cash_over_short` must not join them: every
    utility that takes cash at a counter has drawers, so the account ships with
    the chart and the first-use door is a repair path, never the plan.
    """
    assert chart.CASH_OVER_SHORT in chart.GL_DESIGNATIONS
    assert chart.CASH_OVER_SHORT in chart.SEEDED_DESIGNATIONS
    assert chart.CASH_OVER_SHORT not in chart.DESIGNATED_ON_FIRST_USE
    assert [row.code for row in chart.CASH_OVER_SHORT_CHART] == ["6850"]


# ════════════════════════════════════════════════════════════════════════════
# 2 · A FRESH TENANT
# ════════════════════════════════════════════════════════════════════════════
def test_cr136_p221__a_freshly_provisioned_tenant_resolves_it(brazos):
    """Provisioned through the REAL signup path, so this fails if the row lives
    anywhere but in the product.

    The read is the one `apps/payments/bankrec_read.py` already uses for `cash`
    — `gl_account_id_for_designation(<name>)` — because that is the shape
    `P2.22` will resolve through and a different read here would prove nothing
    about it.
    """
    with tenant_ctx(brazos):
        account_id = ledger_selectors.gl_account_id_for_designation(chart.CASH_OVER_SHORT)
        assert account_id is not None, (
            "cash_over_short resolves to nothing on a freshly provisioned tenant, so the "
            "first counted close of the product's life would refuse"
        )
        row = ledger_models.LedgerAccount.objects.get(id=account_id)
        assert (row.code, row.name, row.type) == ("6850", "Cash over and short", "expense")

        # BOTH sides of the ruling's pair resolve, because a posting that can
        # find one account and not the other refuses just the same.
        assert ledger_selectors.gl_account_id_for_designation(chart.UNDEPOSITED_FUNDS) is not None

        # `designation_map` is what the GL-mapping settings surface renders, so
        # the new pointer is visible and re-pointable rather than invisible.
        assert ledger_selectors.designation_map()[chart.CASH_OVER_SHORT] == account_id


def test_cr136_p221__the_top_up_creates_nothing_on_a_fresh_tenant(brazos, dana, audit_rows):
    """Idempotent by the cheapest possible route: the pointer is already there,
    so the door reads one row and returns."""
    with tenant_ctx(brazos):
        before = ledger_models.LedgerAccount.objects.filter(tenant=brazos).count()
        audit_rows.clear()
        first = ledger_services.ensure_cash_over_short_account(dana)
        second = ledger_services.ensure_cash_over_short_account(dana)
        assert first == second is not None
        assert ledger_models.LedgerAccount.objects.filter(tenant=brazos).count() == before
        assert audit_rows == [], "a no-op top-up wrote an audit row"


# ════════════════════════════════════════════════════════════════════════════
# 3 · A TENANT THAT ALREADY EXISTS — hard-won law 4
# ════════════════════════════════════════════════════════════════════════════
def _make_it_a_pre_ruling_tenant(tenant):
    """The state every tenant on the host is in before this change ships: a
    chart with no `6850` on it."""
    with tenant_ctx(tenant):
        ledger_models.LedgerAccount.objects.filter(tenant=tenant, code="6850").delete()
        assert ledger_selectors.gl_account_id_for_designation(chart.CASH_OVER_SHORT) is None


def test_cr136_p221__an_existing_tenant_gets_it_from_the_post_migrate_sweep(brazos, dana):
    """⚠ **THE CLAIM THIS FILE EXISTS TO PROVE RATHER THAN ASSERT IN PROSE.**

    Three ledger docstrings said `seed_chart_of_accounts` runs *"at PROVISIONING
    and nowhere else"* and that *"nothing backfills"* (`DEF-LED-6223`). It is
    not true today: `tenancy.services.seed_reference_data_for_tenant` calls it
    unconditionally, and `tenancy.reference_sweep.sweep()` runs that door over
    `Tenant.objects.all()` from `06-backend/docker-entrypoint.sh` after every
    `migrate` (OQ-087, CLOSED 2026-08-10).

    So this walks the REAL door the sweep walks, with the REAL narrowing the
    sweep applies (`structural_only=True`), against a tenant whose chart is in
    the pre-ruling state. If somebody later moves the chart top-up behind that
    flag, this goes red and the live beta tenants stop getting new accounts —
    which is exactly the silence hard-won law 4 is about.
    """
    _make_it_a_pre_ruling_tenant(brazos)
    with tenant_ctx(brazos):
        tenancy_services.seed_reference_data_for_tenant(brazos, dana, structural_only=True)
        account_id = ledger_selectors.gl_account_id_for_designation(chart.CASH_OVER_SHORT)
        assert account_id is not None, (
            "the post-migrate reference sweep did not top this tenant's chart up, so every "
            "utility already on the host would count a drawer and post nothing"
        )
        assert ledger_models.LedgerAccount.objects.get(id=account_id).code == "6850"


def test_cr136_p221__the_first_use_door_mints_it_for_a_tenant_the_sweep_missed(
    brazos, dana, audit_rows
):
    """The window the sweep does not cover: a tenant whose sweep FAILED
    (BR-TEN-074 isolates a failure per tenant and carries on), and the gap
    between a code deploy and the sweep finishing.

    `P2.22` calls this at the top of the posting for the reason
    `ensure_allowance_account` names: a posting that refuses because a pointer
    is missing is a posting a clerk cannot fix from the screen they are on —
    and the screen they are on is the one where they have just counted a bag of
    cash.
    """
    _make_it_a_pre_ruling_tenant(brazos)
    with tenant_ctx(brazos):
        audit_rows.clear()
        account_id = ledger_services.ensure_cash_over_short_account(dana)
        assert account_id is not None
        row = ledger_models.LedgerAccount.objects.get(id=account_id)
        assert (row.code, row.name, row.designation) == (
            "6850",
            "Cash over and short",
            chart.CASH_OVER_SHORT,
        )
        # Hard rule 7 / BR-LED-015 — a chart change, seeded or typed, is audited,
        # and the SOURCE says which story the row appeared from.
        created = [r for r in audit_rows if r["action"] == "ledger_account.created"]
        assert [r["after"]["code"] for r in created] == ["6850"]
        assert created[0]["after"]["source"] == "cash_over_short_top_up"
        assert created[0]["after"]["finance_signed"] is False

        # Idempotent: the second call is a read.
        assert ledger_services.ensure_cash_over_short_account(dana) == account_id
        assert ledger_models.LedgerAccount.objects.filter(tenant=brazos, code="6850").count() == 1


def test_cr136_p221__a_re_seed_tops_it_up_and_touches_nothing_else(brazos, dana):
    """`seed_chart_of_accounts` is the repair run, and rule 1 still holds.

    A tenant that has renamed `1200 Accounts receivable` to `Trade debtors`
    keeps that name through a top-up — otherwise a repair run would quietly
    restate somebody's chart, which is the opposite of what a repair is.
    """
    with tenant_ctx(brazos):
        ar = ledger_models.LedgerAccount.objects.get(tenant=brazos, code="1200")
        ar.name = "Trade debtors"
        ar.save(update_fields=["name", "updated_at"])
    _make_it_a_pre_ruling_tenant(brazos)
    with tenant_ctx(brazos):
        summary = ledger_services.seed_chart_of_accounts(dana)
        assert summary["codes_created"] == ("6850",), (
            "the repair run created something other than the one missing account"
        )
        assert chart.CASH_OVER_SHORT in summary["designations_placed"]
        assert (
            ledger_models.LedgerAccount.objects.get(tenant=brazos, code="1200").name
            == "Trade debtors"
        )


# ════════════════════════════════════════════════════════════════════════════
# 4 · THE TENANT'S CHART IS THE TENANT'S — the two ways this must NOT act
# ════════════════════════════════════════════════════════════════════════════
def test_cr136_p221__the_top_up_never_takes_an_account_that_is_somebody_elses(brazos, dana):
    """A tenant's own re-coded chart can hold `6850` already, and the one
    failure that would be SILENT is a drawer difference landing in it.

    The answer is `None`, which is a REAL state and which `P2.22` must refuse
    on rather than substitute — `ensure_period_matching_accounts`'s rule, for
    the reason hard rule 4 gives: nobody can move a journal line afterwards.
    """
    _make_it_a_pre_ruling_tenant(brazos)
    with tenant_ctx(brazos):
        ledger_models.LedgerAccount.objects.create(
            tenant=brazos,
            code="6850",
            name="Fleet fuel",
            type="expense",
            category=chart.CAT_OPERATING_EXPENSES,
        )
        answer = ledger_services.ensure_cash_over_short_account(dana)
        assert answer is None, "the top-up designated an account it did not create"
        theirs = ledger_models.LedgerAccount.objects.get(tenant=brazos, code="6850")
        assert (theirs.name, theirs.designation) == ("Fleet fuel", None)


def test_cr136_p221__a_tenants_own_pointer_wins(brazos, dana):
    """US-LED-005 rule 2: a designation the tenant has claimed is never moved.

    A utility that files drawer differences in their own `6855` keeps it, and a
    repair run neither re-points them nor mints a rival — `P2.22` then posts to
    THEIR account, because it resolves the designation and never the number.
    """
    _make_it_a_pre_ruling_tenant(brazos)
    with tenant_ctx(brazos):
        theirs = ledger_models.LedgerAccount.objects.create(
            tenant=brazos,
            code="6855",
            name="Drawer differences",
            type="expense",
            designation=chart.CASH_OVER_SHORT,
            category=chart.CAT_OPERATING_EXPENSES,
        )
        summary = ledger_services.seed_chart_of_accounts(dana)
        assert chart.CASH_OVER_SHORT in summary["designations_already_placed"]
        assert ledger_selectors.gl_account_id_for_designation(chart.CASH_OVER_SHORT) == str(
            theirs.id
        )
        # The seed still planted the code — the tenant simply keeps the pointer.
        planted = ledger_models.LedgerAccount.objects.get(tenant=brazos, code="6850")
        assert planted.designation is None
        assert ledger_services.ensure_cash_over_short_account(dana) == str(theirs.id)


# ════════════════════════════════════════════════════════════════════════════
# 5 · THE DATABASE — `ledger/0016`, which is the whole reason a migration exists
# ════════════════════════════════════════════════════════════════════════════
@requires_postgres
def test_cr136_p221__the_check_constraint_accepts_it_and_still_refuses_a_typo(brazos):
    """The CHECK is INLINED by Django's serializer, so the database does not
    follow `chart.GL_DESIGNATIONS` — `ledger/0016` is what moves it.

    Both halves are asserted on purpose: that the eighteenth value is accepted
    (or the seed itself would fail at provisioning), and that the constraint
    still bites, so this migration cannot be read as having loosened it.
    """
    from django.db import IntegrityError, transaction

    with tenant_ctx(brazos):
        assert ledger_models.LedgerAccount.objects.filter(
            tenant=brazos, code="6850", designation=chart.CASH_OVER_SHORT
        ).exists()

        # ⚠ SAVEPOINT, not a bare try/except — hard-won law 14: on PostgreSQL a
        # failed statement poisons the whole transaction, and the naive version
        # of this passes on the suite's default sqlite and loses the rest of the
        # test on a real database.
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ledger_models.LedgerAccount.objects.create(
                    tenant=brazos,
                    code="6851",
                    name="Cash over and shrot",
                    type="expense",
                    designation="cash_over_shrot",
                )
        assert ledger_models.LedgerAccount.objects.filter(tenant=brazos, code="6850").exists()


def test_cr136_p221__the_selector_refuses_an_unruled_designation_by_name():
    """The guard that made the migration necessary rather than one bare
    constant: `gl_account_for_designation` refuses anything not in the ruled
    tuple, and its refusal now enumerates the tuple instead of claiming a count
    (`DEF-LED-6222`)."""
    with pytest.raises(ValueError) as caught:
        ledger_selectors.gl_account_for_designation("cash_over_shrot")
    message = str(caught.value)
    assert "cash_over_short" in message
    assert "thirteenth" not in message, (
        "the refusal quotes a count again; count the tuple, never a sentence about it"
    )
