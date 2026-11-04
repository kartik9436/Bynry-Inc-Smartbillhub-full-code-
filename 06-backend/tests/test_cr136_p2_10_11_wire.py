# ── Trace ──────────────────────────────────────────────
# Change:  CR-136-BRC07 tasks `P2.10` (*"Finance picks up the batch — a closed
#          till's batch appears on Deposits ready to match"*) and `P2.11`
#          (*"Notification: the unclosed till. Tells a supervisor; never
#          closes"*).
# Rules:   PO ruling 2026-09-23 §3.1 (NO auto-close) · PO ruling 2026-09-22
#          (`P0.6` — a batch is one till and one tender) · BR-PAY-004 (a
#          reconciled batch LOCKS) · BR-PAY-025 · BR-NOT-020 (one message per
#          bulk action) · BR-NOT-021 (the ruled staff audience) · BR-TEN-043 ·
#          CLAUDE.md hard rule 1 · rule 6 · hard-won law 7
# ───────────────────────────────────────────────────────
"""The two wiring tasks of phase 2: Finance picks it up, and a supervisor is told.

WHAT EACH OF THESE WOULD HAVE LET THROUGH, WHICH IS WHY IT IS HERE
-------------------------------------------------------------------
**`P2.10`.** Phase 0 re-keyed the deposit batch onto the till, so a batch now
exists from the moment the drawer OPENS. `bankrec_read.batch_queryset` filtered
on `tenant_id` alone, so Dana's batch appeared on Finance → Deposits at 08:55
with the status `in_transit` — *"cut, and the bank has not shown it yet"* —
counted into the In-transit tile and available to match and reconcile.
Reconciling LOCKS it (BR-PAY-004), after which `_recompute_total` refuses the
edit and **the money taken after 14:00 can never be accounted for**. Measured
before the fix: three batches served, one of them behind an open till.

**`P2.11`.** The blueprint drew a midnight auto-close and the PO struck it, so
an unclosed till now stays open until a System Admin seals it — and its owner
cannot open a second one, so **Dana cannot take money the next morning**.
Nothing told anybody.

THE FOUR POPULATIONS `P2.10` HAS TO KEEP APART, one case each
--------------------------------------------------------------
  legacy      `session_id IS NULL`       banked before tills existed  → SHOWS
  system      born closed                ACH, card, wire, lockbox     → SHOWS
  counted     a person closed it         the phase's own happy path   → SHOWS
  still open  `closed_at IS NULL`        a drawer taking money        → HELD

⚠ **THE HELD ONE IS COUNTED AND SERVED, NEVER SILENT.** Hard-won law 7: *"a
declared blind spot with no NUMBER attached is indistinguishable from an empty
one."* `still_open` on the body is that number and there is a case on it.

WHAT WOULD MAKE THESE CASES PASS WRONGLY
-----------------------------------------
  1. **An empty table.** *"No open-till batch is served"* is true of a database
     with no batches in it. Every `P2.10` case therefore asserts the three
     batches that SHOULD be served are served, in the same breath as the one
     that should not.
  2. **A sweep that entered no tenant.** *"0 counters left open"* is what a
     query with no `app.tenant_id` reports, truthfully, about nothing
     (hard rule 1). `test_sweep_reports_the_scope_beside_the_result` asserts
     `tenants_examined` moved, and a case drives a REAL open till through and
     watches the number reach the seam.
  3. **A test that proves the notice by calling the notifier.** The point of
     `P2.11` is that the SWEEP finds the till. The cases go in at
     `counter_watch.sweep` and read the outcome rows that come back out.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from apps.notifications import bulk_summary, rule_catalog
from apps.payments import bankrec_models as bankrec
from apps.payments import bankrec_read, counter_watch
from apps.payments import counter_session_models as tills
from apps.payments import models as pay
from apps.payments import reconciliation, run_alert_seam
from apps.payments.exceptions import PaymentRuleError
from apps.tenancy import models as tenancy_models
from apps.tenancy import published_content_models as published

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: BR-TEN-043 — every moment here is NAMED. Nothing in these cases reads a clock.
MONDAY = dt.date(2026, 9, 21)
TUESDAY = dt.date(2026, 9, 22)
MONDAY_0855 = dt.datetime(2026, 9, 21, 8, 55, tzinfo=dt.UTC)
MONDAY_1730 = dt.datetime(2026, 9, 21, 17, 30, tzinfo=dt.UTC)
TUESDAY_MIDNIGHT = dt.datetime(2026, 9, 22, 0, 0, tzinfo=dt.UTC)
TUESDAY_0700 = dt.datetime(2026, 9, 22, 7, 0, tzinfo=dt.UTC)


# ── fixtures ───────────────────────────────────────────────────────────────
def a_method(tenant, code):
    return tenancy_models.PaymentMethod.objects.filter(tenant=tenant, code=code).first()


def a_counter(tenant):
    """The walk-in counter a person's till must name.

    ⚠ REQUIRED, and the first draft of this file left it out and was REFUSED by
    `ck_counter_sessions_system_is_nobodys` — *"a till with no owner may not
    pretend to be a person's"*, read in the other direction: a person's till
    carries an owner AND a service centre AND no `system_day`, all three or
    none. Phase 0's constraint caught a test fixture before it could catch a
    service, which is the constraint working.
    """
    centre, _ = published.ServiceCentre.objects.get_or_create(
        tenant_id=tenant.id,
        slug="main-counter",
        defaults={"name": "Main counter", "address": "1 Bend Road, Needville TX"},
    )
    return centre


def _user_id(actor):
    return getattr(actor, "user_id", None) or actor.id


def an_open_till(tenant, owner, *, opened_at=MONDAY_0855):
    """A person's till, opened and never closed. `uq_counter_sessions_open_owner`
    permits exactly one of these per person, which is why each case that wants
    two uses two owners."""
    return tills.CounterSession.objects.create(
        tenant_id=tenant.id,
        owner_id=_user_id(owner),
        service_centre=a_counter(tenant),
        opening_float=Decimal("200.0000"),
        currency="USD",
        opened_at=opened_at,
    )


def a_closed_till(tenant, owner, *, opened_at=MONDAY_0855, closed_at=MONDAY_1730):
    """A till a person counted and sealed — `close_kind='counted'`."""
    return tills.CounterSession.objects.create(
        tenant_id=tenant.id,
        owner_id=_user_id(owner),
        service_centre=a_counter(tenant),
        opening_float=Decimal("200.0000"),
        currency="USD",
        opened_at=opened_at,
        closed_at=closed_at,
        closed_by_id=_user_id(owner),
        close_kind=pay.COUNTER_CLOSE_COUNTED,
        difference=Decimal("0.0000"),
    )


def a_legacy_batch(tenant, *, method, code, total):
    """A batch from BEFORE tills existed: `session_id IS NULL`.

    ⚠ **ON POSTGRESQL THIS POPULATION CANNOT BE CREATED AT ALL, BY DESIGN, AND
    THE FIRST TWO DRAFTS OF THIS FIXTURE EACH FOUND ONE OF THE TWO DOORS SHUT.**
    Both were green on the default in-memory SQLite suite and red on the
    database the product runs on, which is hard-won law 7's *incapable of
    passing* shape and hard-won law 14's whole reason for existing:

      * `create(session=None)` — refused by `trg_deposit_batch_needs_session`
        (`BEFORE INSERT`, `payments/0033`). A `NOT NULL` would have validated
        every existing row and refused to apply, so phase 0 used a trigger
        instead; the effect is that **no NEW row may join this population.**
      * `update ... set session_id = null` — refused BY NAME by
        `payments_deposit_batch_lock()`: *"deposit batch … is identified by its
        tenant, TILL, day, method and code — none of them may change."*

    **That is not an obstacle to work around, it is the fact this file is
    testing.** The population is historical and frozen: rows written before
    2026-09-22 are in it, and nothing may enter or leave it. So the fixture
    reaches it the only way anything can — the way
    `10-scripts/p2_10_11_seed_tills.py` does — by disabling the INSERT guard for
    the length of this test. **It is never re-enabled here on purpose:** the
    test runs inside a transaction, `ALTER TABLE` is transactional on
    PostgreSQL, and the rollback at teardown restores the trigger without this
    fixture having to remember to. Re-enabling it by hand would also risk
    *"cannot ALTER TABLE … it has pending trigger events"*.

    On SQLite neither trigger exists, so the plain create is the whole of it.
    """
    from django.db import connection

    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "alter table deposit_batches disable trigger trg_deposit_batch_needs_session"
            )
    return bankrec.DepositBatch.objects.create(
        tenant_id=tenant.id,
        code=code,
        session=None,
        method=method,
        deposited_on=dt.date(2026, 8, 8),
        recorded_total=Decimal(total),
        status=bankrec.BATCH_IN_TRANSIT,
    )


def test_no_new_batch_may_join_the_legacy_population(brazos, dana):
    """Phase 0 closed that door and this asserts it is still shut.

    It is the other half of `a_legacy_batch`'s docstring, as a CASE rather than
    prose — because the fixture above disables a guard, and a fixture that
    disables a guard should be sitting next to the test that proves the guard
    exists. **PostgreSQL only**: neither trigger exists on SQLite, so there is
    nothing here to assert and the case says so rather than passing silently.
    """
    from django.db import connection

    if connection.vendor != "postgresql":
        pytest.skip(
            "trg_deposit_batch_needs_session and payments_deposit_batch_lock() are "
            "PostgreSQL triggers; the default suite is SQLite and has neither, so this "
            "guarantee is UNCHECKED on the default suite (CLAUDE.md hard-won law 14)"
        )
    from django.db import transaction

    with tenant_ctx(brazos):
        cash = a_method(brazos, "cash")
        # ⚠ **THE SAVEPOINT IS LOAD-BEARING AND THE FIRST DRAFT OF THIS CASE
        # DID NOT HAVE ONE** — hard-won law 14, met head-on while writing a case
        # ABOUT law 14. A refused statement ABORTS the whole PostgreSQL
        # transaction, so without a nested `atomic()` every query after it —
        # including the one `tenant_ctx` runs on the way out — dies with
        # `InFailedSqlTransaction`, and the case fails for a reason that has
        # nothing to do with what it is asserting. SQLite has no aborted-
        # transaction state, so this line is invisible on the default suite.
        with pytest.raises(Exception) as refusal:  # noqa: PT011 - psycopg RaiseException
            with transaction.atomic():
                bankrec.DepositBatch.objects.create(
                    tenant_id=brazos.id,
                    code="DEP-T-0030",
                    session=None,
                    method=cash,
                    deposited_on=dt.date(2026, 8, 8),
                    recorded_total=Decimal("1.0000"),
                    status=bankrec.BATCH_IN_TRANSIT,
                )
    assert "session" in str(refusal.value).lower()


def a_batch(tenant, *, session, method, code, total):
    return bankrec.DepositBatch.objects.create(
        tenant_id=tenant.id,
        code=code,
        session=session,
        method=method,
        deposited_on=MONDAY,
        recorded_total=Decimal(total),
        status=bankrec.BATCH_IN_TRANSIT,
    )


# ══════════════════════════════════════════════════════════════════════════
# `P2.10` — FINANCE PICKS UP THE BATCH
# ══════════════════════════════════════════════════════════════════════════
def test_a_closed_tills_batch_reaches_finance_deposits(brazos, dana, marcus):
    """The task's own sentence: a CLOSED counter batch IS the deposit batch.

    And the open one beside it is NOT — asserted together, because *"the open
    one is absent"* is also true of a list that is broken and serves nothing.
    """
    with tenant_ctx(brazos):
        cash = a_method(brazos, "cash")
        closed = a_closed_till(brazos, dana)
        still_open = an_open_till(brazos, marcus)
        a_batch(brazos, session=closed, method=cash, code="DEP-T-0001", total="884.0000")
        a_batch(brazos, session=still_open, method=cash, code="DEP-T-0002", total="612.5000")

        body = bankrec_read.batch_list()
        served = {row["code"] for row in body["rows"]}

    assert "DEP-T-0001" in served, "a closed till's batch must reach Finance → Deposits"
    assert "DEP-T-0002" not in served, "a drawer still taking money is not bankable"


def test_the_legacy_and_system_populations_still_show(brazos, dana):
    """`session_id IS NULL` and the SYSTEM till are both bankable, and must stay so.

    The legacy row is how every batch banked before 2026-09-22 looks; the system
    till is every ACH, card, wire and lockbox deposit the product will ever cut.
    A filter that took either out would empty Finance → Deposits for a real
    utility, which is a far worse failure than the one `P2.10` fixes.
    """
    with tenant_ctx(brazos):
        cash = a_method(brazos, "cash")
        check = a_method(brazos, "check")
        # ⚠ **THE LEGACY ROW GOES IN FIRST, AND THE ORDER IS LOAD-BEARING.**
        # `a_legacy_batch` issues an `ALTER TABLE … DISABLE TRIGGER`, and
        # PostgreSQL refuses that with *"cannot ALTER TABLE … because it has
        # pending trigger events"* once rows of that table have already been
        # written in the same transaction. The seeder script this fixture
        # follows records the same trap in its own docstring.
        a_legacy_batch(brazos, method=cash, code="DEP-260808-CHK", total="4400.0000")
        system = reconciliation._system_session(tenant_id=brazos.id, day=MONDAY)
        a_batch(brazos, session=system, method=check, code="DEP-T-0003", total="1284.6000")
        served = {row["code"] for row in bankrec_read.batch_list()["rows"]}

    assert served == {"DEP-T-0003", "DEP-260808-CHK"}, (
        "the system till is born CLOSED and a session-less batch was banked the old "
        "way — both are bankable and both must show"
    )


def test_the_held_back_money_is_a_number_and_not_a_silence(brazos, dana, marcus):
    """Hard-won law 7 — the blind spot is DECLARED, with its figure.

    Without this the Deposits list would simply be short by `$612.50` and
    nothing on the screen or the wire would say so.
    """
    with tenant_ctx(brazos):
        cash = a_method(brazos, "cash")
        closed = a_closed_till(brazos, dana)
        still_open = an_open_till(brazos, marcus)
        a_batch(brazos, session=closed, method=cash, code="DEP-T-0004", total="884.0000")
        a_batch(brazos, session=still_open, method=cash, code="DEP-T-0005", total="612.5000")

        body = bankrec_read.batch_list()

    assert body["still_open"]["batch_count"] == 1
    assert Decimal(body["still_open"]["recorded_total"]) == Decimal("612.5000")
    assert body["still_open"]["currency"] == "USD"
    # And the tiles fold only what the rows carry, so the two cannot be added
    # into one confident wrong number.
    assert Decimal(body["kpis"]["in_transit_total"]) == Decimal("884.0000")


def test_the_held_back_figure_is_absent_when_no_till_is_open(brazos, dana):
    """A utility with every drawer closed reports zero, and the SCREEN draws nothing.

    Asked because the opposite failure is a line reading *"$0.00 at 0 open
    counters"* on every Finance screen, every day of the year (B14 rule 32 — a
    stated absence is CLOSED by default).
    """
    with tenant_ctx(brazos):
        cash = a_method(brazos, "cash")
        closed = a_closed_till(brazos, dana)
        a_batch(brazos, session=closed, method=cash, code="DEP-T-0006", total="884.0000")
        body = bankrec_read.batch_list()

    assert body["still_open"]["batch_count"] == 0
    assert len(body["rows"]) == 1, "the closed till's batch is still served"


def test_reconcile_and_match_refuse_an_open_tills_batch(brazos, dana, marcus):
    """BR-SHL-025 — at the ENDPOINT, not by hiding a button.

    `P2.10` takes the row off the list, which is a rendering decision. This is
    the money rule, and the two must not be the same sentence: reconciling would
    LOCK the batch while the clerk goes on taking money into it.
    """
    with tenant_ctx(brazos):
        cash = a_method(brazos, "cash")
        still_open = an_open_till(brazos, marcus)
        closed = a_closed_till(brazos, dana)
        open_batch = a_batch(
            brazos, session=still_open, method=cash, code="DEP-T-0007", total="612.5000"
        )
        closed_batch = a_batch(
            brazos, session=closed, method=cash, code="DEP-T-0008", total="884.0000"
        )

        with pytest.raises(PaymentRuleError) as refusal:
            reconciliation._refuse_if_the_till_is_open(open_batch)
        # The clerk-facing half: two short sentences, no rule id, no rationale
        # (B14 rule 33). The BR-ID travels in `br_ref`.
        assert "DEP-T-0007" in str(refusal.value)
        assert "Close the counter first" in str(refusal.value)
        assert refusal.value.br_ref == "BR-PAY-025"

        # …and the closed one is NOT refused. Without this the case would pass
        # on a guard that refuses everything.
        reconciliation._refuse_if_the_till_is_open(closed_batch)


def test_auto_match_never_ties_a_bank_line_to_an_open_drawer(brazos, dana, marcus):
    """`status` cannot answer this, which is why the candidate scan is guarded too.

    A counter batch is `in_transit` from the moment its till opens — the same
    status a sealed, unbanked batch carries — so an unattended statement import
    would have had no way to tell them apart.
    """
    with tenant_ctx(brazos):
        cash = a_method(brazos, "cash")
        still_open = an_open_till(brazos, marcus)
        closed = a_closed_till(brazos, dana)
        a_batch(brazos, session=still_open, method=cash, code="DEP-T-0009", total="612.5000")
        a_batch(brazos, session=closed, method=cash, code="DEP-T-0010", total="884.0000")

        candidates = bankrec.bankable(
            bankrec.DepositBatch.objects.filter(
                tenant_id=brazos.id,
                status__in=(bankrec.BATCH_IN_TRANSIT, bankrec.BATCH_UNMATCHED),
            )
        )
        codes = {row.code for row in candidates}

    assert codes == {"DEP-T-0010"}, "only the sealed till is a candidate for a bank line"


def a_statement(tenant, *, period_end=MONDAY):
    """A bank statement import, and the account it came from.

    Only the columns S38's reads actually touch are set; nothing here exercises
    `import_bank_statement`, because these cases are about which BATCHES a read
    offers, not about parsing a file.
    """
    account, _ = bankrec.BankAccount.objects.get_or_create(
        tenant_id=tenant.id, name="Chase Operating", defaults={"mask": "4021"}
    )
    return bankrec.BankStatementImport.objects.create(
        tenant_id=tenant.id,
        bank_account=account,
        period_start=dt.date(2026, 9, 1),
        period_end=period_end,
        file_name="sept.csv",
        file_hash="f" * 64,
        tag_fingerprint="t" * 16,
        line_count=1,
        imported_by_id=None,
        imported_at=MONDAY_1730,
    )


# ── `P2.10` · THE THREE READERS THE FIRST DRAFT OF THIS TASK MISSED ─────────
#
# ⚠ **"ONE EXPRESSION, FOUR READERS" IS ONLY TRUE IF ALL FOUR READ IT.** The
# draft narrowed the Deposits list and `auto_match` and guarded the two write
# paths, and left three further reads of the same population filtering on
# `status` alone — which is the field this whole task exists to say cannot
# answer the question. Each case below is one of them, and each fails on the
# draft.
def test_s38_does_not_offer_a_human_a_batch_the_service_will_refuse(brazos, dana, marcus):
    """S38 step 2's manual-match picker. This module's own header, verbatim:
    *"this read says so on every row so a screen never offers a control the
    service refuses"* — and `match_bank_line` refuses an open till's batch by
    name. An offered control that refuses is hard-won law 2's mirror.
    """
    with tenant_ctx(brazos):
        cash = a_method(brazos, "cash")
        a_batch(
            brazos,
            session=an_open_till(brazos, marcus),
            method=cash,
            code="DEP-T-0020",
            total="612.5000",
        )
        a_batch(
            brazos,
            session=a_closed_till(brazos, dana),
            method=cash,
            code="DEP-T-0021",
            total="884.0000",
        )
        body = bankrec_read.statement_review(a_statement(brazos).pk)
        offered = {row["code"] for row in body["open_batches"]}

    assert "DEP-T-0021" in offered, "a sealed till's batch is a lawful hand-match"
    assert "DEP-T-0020" not in offered, "the picker must not offer what the endpoint refuses"


def test_a_line_whose_only_near_match_is_an_open_drawer_is_not_a_needs_a_look(brazos, dana, marcus):
    """`_has_near_candidate` decides a WORD on S38 — `needs_a_look` against
    `not_in_our_system`. With only an open drawer nearby, *needs a look* sends a
    clerk to match a batch the service refuses, so the truthful answer until
    that till closes is that nothing of ours is close.
    """
    with tenant_ctx(brazos):
        cash = a_method(brazos, "cash")
        statement = a_statement(brazos)
        line = bankrec.BankLine.objects.create(
            tenant_id=brazos.id,
            statement_import=statement,
            posted_on=MONDAY,
            reference="CHECK DEPOSIT 4410",
            amount=Decimal("612.5000"),
            line_no=1,
        )
        a_batch(
            brazos,
            session=an_open_till(brazos, marcus),
            method=cash,
            code="DEP-T-0022",
            total="612.5000",
        )
        only_an_open_drawer = bankrec_read._has_near_candidate(line)

        # …and the SAME line becomes a candidate the moment a sealed till's
        # batch matches it. Without this half the case would pass just as
        # happily on a function that always answers False.
        a_batch(
            brazos,
            session=a_closed_till(brazos, dana),
            method=cash,
            code="DEP-T-0023",
            total="612.5000",
        )
        with_a_sealed_one = bankrec_read._has_near_candidate(line)

    assert only_an_open_drawer is False
    assert with_a_sealed_one is True


def test_the_reconciliation_statement_does_not_call_a_drawer_deposits_in_transit(
    brazos, dana, marcus
):
    """CS-14. The figure's own words are *"money WE banked that the bank has not
    shown"*, and money in a clerk's drawer was never banked. It cites the S37
    tile as its definition, and that tile now folds bankable rows alone — so
    without this the statement disagrees with the screen it sits beside, which
    its own docstring forbids in as many words.
    """
    with tenant_ctx(brazos):
        cash = a_method(brazos, "cash")
        a_batch(
            brazos,
            session=an_open_till(brazos, marcus),
            method=cash,
            code="DEP-T-0024",
            total="612.5000",
        )
        a_batch(
            brazos,
            session=a_closed_till(brazos, dana),
            method=cash,
            code="DEP-T-0025",
            total="884.0000",
        )
        body = bankrec_read.reconciliation_statement(a_statement(brazos).pk)

    item = next(i for i in body["reconciling_items"] if i["code"] == "deposits_in_transit")
    figure = Decimal(item["amount"])
    assert figure == Decimal("884.0000"), (
        f"the sealed till's money is in transit and the open drawer's is not; served {figure}"
    )
    # The ROWS behind the figure move with it — a total that agrees while the
    # list beside it still names the drawer would be the same defect, one
    # layer down, and S40 draws that list.
    assert {row["code"] for row in item["rows"]} == {"DEP-T-0025"}


def test_bankable_and_is_bankable_are_the_same_expression(brazos, dana, marcus):
    """The queryset form and the single-row form may never disagree.

    They are one `Q` used two ways (`bankrec_models.BANKABLE`). This case is
    what would go red if somebody "simplified" `is_bankable` into a Python
    mirror — which is the drift `CR-136-BRC07` §3.2 forbids for its sibling
    expression, in the same words.
    """
    with tenant_ctx(brazos):
        cash = a_method(brazos, "cash")
        check = a_method(brazos, "check")
        rows = [
            a_batch(
                brazos,
                session=an_open_till(brazos, marcus),
                method=cash,
                code="DEP-T-0011",
                total="1.0000",
            ),
            a_batch(
                brazos,
                session=a_closed_till(brazos, dana),
                method=cash,
                code="DEP-T-0012",
                total="2.0000",
            ),
            a_batch(
                brazos,
                session=reconciliation._system_session(tenant_id=brazos.id, day=MONDAY),
                method=check,
                code="DEP-T-0013",
                total="3.0000",
            ),
        ]
        from_queryset = {
            row.code
            for row in bankrec.bankable(bankrec.DepositBatch.objects.filter(tenant_id=brazos.id))
        }
        from_single_row = {row.code for row in rows if bankrec.is_bankable(row)}

    assert from_queryset == from_single_row == {"DEP-T-0012", "DEP-T-0013"}


# ══════════════════════════════════════════════════════════════════════════
# `P2.11` — THE UNCLOSED TILL
# ══════════════════════════════════════════════════════════════════════════
def test_the_event_is_on_set_12_with_a_live_writer(brazos):
    """BR-NOT-017 — every notification rule has ONE home, and this is its row.

    It carries no `trigger_blocked_by`, which is a claim about the world: it
    says something in this codebase can fire it. The second assertion is what
    makes that claim checkable rather than a comment (hard-won law 1).
    """
    row = next((one for one in rule_catalog.EVENTS if one.key == "counter_left_open"), None)
    assert row is not None, "P2.11's event must be on SET-12, not in a private catalogue"
    assert row.audience == rule_catalog.AUDIENCE_STAFF
    assert row.trigger_blocked_by is None, "it has a writer — counter_watch.sweep"
    assert callable(run_alert_seam.counter_watch_entry_point()), (
        "the seam must reach a REAL function; a docstring saying so is not the guarantee"
    )
    assert bulk_summary.EVENT_COUNTER_LEFT_OPEN == row.key


def test_a_till_left_open_overnight_tells_a_supervisor(brazos, dana, marcus):
    """The headline. Monday's drawer, never closed, found on Tuesday morning."""
    with tenant_ctx(brazos):
        an_open_till(brazos, marcus, opened_at=MONDAY_0855)
        result = counter_watch.sweep(
            [(brazos.id, TUESDAY_MIDNIGHT, TUESDAY)],
            finished_at=TUESDAY_0700,
            actor=dana,
        )

    assert result.tenants_examined == 1, "the sweep must actually enter the tenant"
    assert result.tills_left_open == 1
    codes = {out.get("code") for row in result.by_tenant for out in row.outcomes}
    assert run_alert_seam.COUNTER_WATCH_QUEUED in codes, (
        f"a supervisor was not told; outcomes were {codes}"
    )


def test_the_sweep_closes_nothing(brazos, dana, marcus):
    """PO ruling 2026-09-23 §3.1 — *"no auto-close. A System Admin closes it."*

    ⚠ **THE ABSENCE OF A WRITE IS THE DELIVERABLE HERE, NOT AN OMISSION**, and
    an absence is invisible to every other check this repo has. The till is read
    back field by field: a future lane that "helpfully" seals it goes red.
    """
    with tenant_ctx(brazos):
        till = an_open_till(brazos, marcus, opened_at=MONDAY_0855)
        counter_watch.sweep(
            [(brazos.id, TUESDAY_MIDNIGHT, TUESDAY)], finished_at=TUESDAY_0700, actor=dana
        )
        till.refresh_from_db()

    # EVERY column, not the five a reader would think of. A sweep that sealed a
    # till by writing `note` or `declared_at` would be just as much an
    # auto-close, and §3.2's two new columns are the ones a future lane is
    # likeliest to reach for.
    assert till.closed_at is None
    assert till.closed_by_id is None
    assert till.close_kind is None
    assert till.counted_totals is None
    assert till.difference is None
    assert till.note is None
    assert till.declared_at is None
    assert till.declared_by_id is None
    # …and it did not quietly move the till's own facts either.
    assert till.opened_at == MONDAY_0855
    assert till.opening_float == Decimal("200.0000")


def test_the_counter_watch_module_contains_no_write_to_a_till_at_all():
    """§3.1 as a SOURCE-LEVEL claim, because the case above can only cover the
    paths it walks.

    PO ruling 2026-09-23: *"no auto-close. A System Admin closes it."* The rule
    is not *this sweep does not currently close one* — it is that **no scheduled
    job may close a till**, so the module that finds them must contain no write
    to `counter_sessions` at all. A future lane adding one down a branch this
    file does not exercise would pass every behavioural case here.

    ⚠ It asserts the ABSENCE of an ORM write, and an absence is what nothing
    else in this repo can see. `SELECT`s are what this module is for; `.save(`,
    `.update(`, `.delete(`, `.create(` and a raw cursor are not.
    """
    import pathlib

    from apps.payments import counter_watch as module

    source = pathlib.Path(module.__file__).read_text()
    forbidden = (".save(", ".update(", ".delete(", ".create(", ".bulk_update(", "cursor()")
    found = sorted({token for token in forbidden if token in source})
    assert found == [], (
        f"`counter_watch.py` must not write: it TELLS and it never closes "
        f"(PO ruling 2026-09-23 §3.1). Found {found}"
    )


def test_a_till_opened_this_morning_is_not_reported(brazos, dana, marcus):
    """A clerk at work is not a problem. The cut-off is the START of the day.

    Without this the sweep would tell a supervisor about every drawer currently
    taking money, every morning — the notification nobody can bear to leave on.
    """
    with tenant_ctx(brazos):
        an_open_till(brazos, marcus, opened_at=TUESDAY_0700)
        result = counter_watch.sweep(
            [(brazos.id, TUESDAY_MIDNIGHT, TUESDAY)],
            finished_at=dt.datetime(2026, 9, 22, 9, 0, tzinfo=dt.UTC),
            actor=dana,
        )

    assert result.tenants_examined == 1
    assert result.tills_left_open == 0


def test_a_system_till_is_never_reported(brazos, dana):
    """It is born CLOSED, so `closed_at IS NULL` never matches — no exception list.

    Asserted because the alternative implementation (an exception list for
    system tills) is the one a future lane will reach for, and it is a thing
    somebody has to remember.
    """
    with tenant_ctx(brazos):
        system = reconciliation._system_session(tenant_id=brazos.id, day=MONDAY)
        assert system.closed_at is not None, "phase 0's guarantee, re-checked here"
        result = counter_watch.sweep(
            [(brazos.id, TUESDAY_MIDNIGHT, TUESDAY)], finished_at=TUESDAY_0700, actor=dana
        )

    assert result.tills_left_open == 0


def test_a_late_close_counts_as_open_at_cutoff_but_not_as_a_failure(brazos, dana, marcus):
    """Somebody who closed at 07:00 this morning is not a supervisor's problem.

    `total_count` and `failed_count` come from the SAME queryset, so the pair a
    supervisor reads — *"2 processed · 1 failed"* — describes one set of tills.
    """
    with tenant_ctx(brazos):
        # Opened Monday, closed Tuesday 06:00 — after the cut-off, before the sweep.
        tills.CounterSession.objects.create(
            tenant_id=brazos.id,
            owner_id=_user_id(dana),
            service_centre=a_counter(brazos),
            opening_float=Decimal("200.0000"),
            currency="USD",
            opened_at=MONDAY_0855,
            closed_at=dt.datetime(2026, 9, 22, 6, 0, tzinfo=dt.UTC),
            closed_by_id=_user_id(dana),
            close_kind=pay.COUNTER_CLOSE_COUNTED,
            difference=Decimal("0.0000"),
        )
        an_open_till(brazos, marcus, opened_at=MONDAY_0855)
        open_at_cutoff, still = counter_watch.find_open_tills(
            tenant_id=brazos.id, cutoff=TUESDAY_MIDNIGHT
        )

    assert (open_at_cutoff, still) == (2, 1)


def test_sweep_reports_the_scope_beside_the_result(brazos, dana):
    """A zero is only readable next to the number of tenants it is a zero OVER.

    ⚠ This is the case that would have caught the RLS trap: a sweep that never
    entered a tenant reports *"0 counters left open"*, truthfully, about
    nothing (CLAUDE.md hard rule 1).
    """
    with tenant_ctx(brazos):
        result = counter_watch.sweep(
            [(brazos.id, TUESDAY_MIDNIGHT, TUESDAY)], finished_at=TUESDAY_0700, actor=dana
        )
    assert result.tenants_examined == 1
    assert "across 1 tenant(s) examined" in result.sentence()

    empty = counter_watch.sweep([], finished_at=TUESDAY_0700, actor=dana)
    assert empty.tenants_examined == 0
    assert "across 0 tenant(s) examined" in empty.sentence(), (
        "a sweep that examined nothing must not read like a clean night"
    )


def test_a_re_run_that_morning_says_it_once(brazos, dana, marcus):
    """CLAUDE.md rule 6 — `sweep_id` is derived from (tenant, day), never random."""
    with tenant_ctx(brazos):
        an_open_till(brazos, marcus, opened_at=MONDAY_0855)
        first = counter_watch.sweep(
            [(brazos.id, TUESDAY_MIDNIGHT, TUESDAY)], finished_at=TUESDAY_0700, actor=dana
        )
        second = counter_watch.sweep(
            [(brazos.id, TUESDAY_MIDNIGHT, TUESDAY)], finished_at=TUESDAY_0700, actor=dana
        )

    first_codes = {out.get("code") for row in first.by_tenant for out in row.outcomes}
    second_codes = {out.get("code") for row in second.by_tenant for out in row.outcomes}
    assert run_alert_seam.COUNTER_WATCH_QUEUED in first_codes
    assert run_alert_seam.COUNTER_WATCH_ALREADY_QUEUED in second_codes, (
        f"the second sweep wrote a second message; outcomes were {second_codes}"
    )
    assert counter_watch.sweep_id(brazos.id, TUESDAY) == counter_watch.sweep_id(brazos.id, TUESDAY)
    assert counter_watch.sweep_id(brazos.id, TUESDAY) != counter_watch.sweep_id(
        brazos.id, MONDAY
    ), "tomorrow's sweep must be able to say it again"


def test_still_open_is_not_not_counted(brazos, dana, marcus):
    """The two states of this phase, kept apart on purpose.

    A forced close is SEALED — it is *Not counted*, `P2.3`'s expression and
    screen 3·1's filter chip — and it is emphatically NOT what `P2.11` fires
    on. The blueprint's acts table gives it a different message to a different
    person: on a force close *"the owner is told"* (p059).
    """
    with tenant_ctx(brazos):
        forced = tills.CounterSession.objects.create(
            tenant_id=brazos.id,
            owner_id=_user_id(marcus),
            service_centre=a_counter(brazos),
            opening_float=Decimal("200.0000"),
            currency="USD",
            opened_at=MONDAY_0855,
            closed_at=MONDAY_1730,
            closed_by_id=_user_id(dana),
            close_kind=pay.COUNTER_CLOSE_FORCED,
        )
        assert forced.closed_at is not None
        still = tills.still_open(tills.CounterSession.objects.filter(tenant_id=brazos.id))
        assert list(still) == [], "a forced close is sealed — it is not STILL OPEN"

        result = counter_watch.sweep(
            [(brazos.id, TUESDAY_MIDNIGHT, TUESDAY)], finished_at=TUESDAY_0700, actor=dana
        )
    assert result.tills_left_open == 0


def test_one_tenants_failure_does_not_stop_the_rest(brazos, dana, marcus):
    """BR-TEN-074 — the tenant AFTER the one that blew up is still swept.

    ⚠ **THE FIRST VERSION OF THIS CASE USED A RANDOM `uuid4()` AS THE BAD
    TENANT AND IT WAS THE WRONG PROBE — recorded rather than quietly
    replaced.** On PostgreSQL that id resolves to nothing and the foreign key
    refuses; on SQLite, which is what the default suite runs
    (`config/settings/test.py`, hard-won law 14), there is no RLS and the FK is
    only checked at the END of the transaction — so the sweep cheerfully
    QUEUED a message against a tenant that does not exist and the suite
    reported it as an ERROR AT TEARDOWN, in another fixture, naming
    `outbound_messages`. The case proved nothing about isolation and blamed the
    wrong code.

    A bad `cutoff` raises INSIDE the iteration, which is the thing being
    tested, and writes nothing at all.
    """
    with tenant_ctx(brazos):
        an_open_till(brazos, marcus, opened_at=MONDAY_0855)

    result = counter_watch.sweep(
        [
            (brazos.id, "not-a-moment", TUESDAY),  # raises inside the query
            (brazos.id, TUESDAY_MIDNIGHT, TUESDAY),
        ],
        finished_at=TUESDAY_0700,
        actor=dana,
    )

    assert len(result.failed) == 1, f"the bad triple must be recorded: {result.failed}"
    assert result.tenants_examined == 1, "the good pass must still have run"
    assert result.tills_left_open == 1
    assert "1 tenant(s) failed" in result.sentence(), (
        "the failure must be VISIBLE in the one line a reader gets"
    )
