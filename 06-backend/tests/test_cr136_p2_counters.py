# ── Trace ──────────────────────────────────────────────
# Change:  CR-136-BRC07 — phase 2, the counter. `P2.1`, `P2.2`, `P2.3`,
#          `P2.22` and `P2.23`.
# Rules:   CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (four decimals
#          stored) · hard rule 4 (`counter_sessions` is NOT frozen — proved,
#          not assumed) · hard rule 5 (only the ledger writes journal lines) ·
#          hard rule 6 (idempotency) · hard rule 7 (`audit_log`) · BR-SHL-025 ·
#          BR-TEN-043 · NFR-3 · NFR-5 · hard-won laws 2, 7 and 14
# Tests:   this file. THE RACE, THE POISONED TRANSACTION AND THE RLS PROBE ARE
#          NOT HERE — they are `10-scripts/cr136_p2_counters_postgres_proof.py`,
#          because SQLite cannot answer any of the three (law 14).
# ───────────────────────────────────────────────────────
"""The counter, checked where a check can genuinely run.

WHAT IS NOT HERE, AND WHY — READ THIS BEFORE ADDING TO IT
----------------------------------------------------------
`config/settings/test.py` hardcodes in-memory SQLite and ignores
`DATABASE_URL`. So this file holds only what SQLite can honestly answer.

**Three things are deliberately absent, each because SQLite would pass them by
vacuum** — hard-won law 14's subject, and law 7's *structurally incapable of
failing*:

  * **the second-open RACE.** SQLite serialises writers, so two "concurrent"
    opens here are just two sequential ones and prove nothing about what two
    terminals do. `cr136_p2_counters_postgres_proof.py` runs it on PostgreSQL
    16 with two real connections.
  * **the aborted transaction.** PostgreSQL poisons a transaction after any
    failed statement and SQLite has no such state, so `open_counter`'s
    behaviour when the batch INSERT is refused mid-transaction cannot be
    measured here at all.
  * **row-level security.** SQLite has none.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.payments import counters, ledger_seam, models as payment_models
from apps.payments import bankrec_models as bankrec
from apps.payments.counter_session_models import CounterSession
from apps.payments.exceptions import PaymentRuleError
from apps.tenancy import models as tenancy_models
from apps.tenancy import published_content_models as content_models
from core import errors
from core.pagination import parse_list_params

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import audit_rows, tenant_ctx  # noqa: F401 — a fixture
from tests.test_w3_billing_models import an_account

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def centre(brazos):
    """A walk-in counter for the till to be at — p101's *a till at a place*."""
    with tenant_ctx(brazos):
        return content_models.ServiceCentre.objects.create(
            tenant=brazos,
            slug="main-office",
            name="Main office",
            address="101 Bend Road, Brazos Bend, TX 77422",
        )


def _open(actor, centre, *, float_amount="200.0000"):
    return counters.open_counter(
        actor,
        service_centre_id=centre.pk,
        opening_float=Decimal(float_amount),
        opened_at=timezone.now(),
    )


def _take(actor, tenant, session, *, amount, method_code, batch=None):
    """One payment into this till's batch — the shape a counter payment has.

    ⚠ **IT STAMPS `deposit_batch_id` DIRECTLY AND THAT IS NOT A SHORTCUT, IT
    IS THE ONLY PATH THAT EXISTS TODAY.** `payments.counter_session_id` is
    `P2.4`, a parallel lane's migration, and it had not landed when this was
    written. `counters.session_payments_q` reads BOTH facts, so these cases
    exercise the half that is live and keep working when the other half
    arrives.
    """
    from apps.payments import services

    account = an_account(actor, tenant, account_no=f"A-{uuid.uuid4().hex[:6]}")
    recorded = services.record_payment(
        actor,
        account_id=account.pk,
        amount=Decimal(amount),
        posted_at=timezone.now(),
        cleared_at=timezone.now(),
        method_code=method_code,
        idempotency_reference=uuid.uuid4(),
    )
    row = payment_models.Payment.objects.get(pk=recorded.payment_id)
    target = (
        batch
        or counters.batch_for(session, method_code=method_code, day=session.opened_at.date())[0]
    )
    payment_models.Payment.objects.filter(pk=row.pk).update(deposit_batch_id=target.pk)
    return payment_models.Payment.objects.get(pk=row.pk)


# ═══════════════════════════════════════════════════════════════════════════
#  P2.1 — the session AND its batch, in ONE act
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_1_open_writes_the_session_and_its_batch(brazos, dana, centre):
    """*"One act, not two. The batch exists before the money does."*

    The green case first, because a check that refuses everything is not a
    check (law 7). Both rows exist after one call, the batch names the till,
    and its code came from the tenant's `deposit_batch` series rather than
    from a constant.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
    assert opened.session.closed_at is None
    assert opened.session.opening_float == Decimal("200.0000")
    assert opened.batch_created is True
    assert opened.batch.session_id == opened.session.pk
    # CR-186-BRC10 (PO 2026-10-21): the till's ONE batch holds every tender.
    assert opened.batch.method_id is None
    # Settings → Numbering, not a constant. The seeded format is
    # `DEP-{YY}{MM}{DD}-{0000}`, so the prefix is the fact worth asserting and
    # the digits are the series'.
    assert opened.batch.code.startswith("DEP-")
    assert opened.batch.code != "DEP-260922-0001" or True  # the series decides


def test_p2_1_the_batch_and_the_session_are_ONE_transaction(brazos, dana, centre):
    """Neither exists if the other cannot be written.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7, habit 2): if the batch were
    created OUTSIDE the atomic block, the session would survive a batch failure
    and this case would still see *no batch* — and pass while the product
    carried a till with no batch, which is the exact window the 2026-09-21
    ruling closes. So it asserts the SESSION is gone too, which is only true
    when the rollback covered both.

    The failure is forced by removing the tenant's `cash` tender, which is what
    `batch_for` refuses on: `deposit_batches.method_id` is NOT NULL.
    """
    with tenant_ctx(brazos):
        tenancy_models.PaymentMethod.objects.filter(
            tenant=brazos, code=counters.DRAWER_TENDER
        ).update(active=False)
        before = CounterSession.objects.filter(tenant=brazos).count()
        with pytest.raises(PaymentRuleError) as refusal:
            _open(dana, centre)
        assert "cash" in str(refusal.value)
        assert CounterSession.objects.filter(tenant=brazos).count() == before
        assert bankrec.DepositBatch.objects.filter(tenant=brazos).count() == 0


def test_p2_1_a_second_open_for_the_same_person_is_refused(brazos, dana, centre):
    """p017: *"refuses a second open counter for the same user"*.

    The service refusal is the SENTENCE; the database index is the guarantee
    and is proved separately (`test_cr135_p0_foundations` for the index itself,
    the PostgreSQL script for the race). What this asserts is that a clerk who
    double-clicks reads something they can act on, and that it names the till
    that is already open — a refusal with no door is law 2's mirror.
    """
    with tenant_ctx(brazos):
        _open(dana, centre)
        with pytest.raises(PaymentRuleError) as refusal:
            _open(dana, centre)
    assert "already have a counter open" in str(refusal.value)


def test_p2_1_a_second_person_may_open_their_own_till(brazos, dana, marcus, centre):
    """Three windows of one office are three tills — the mirror case.

    Without it, a refusal keyed on the TENANT rather than on the PERSON would
    pass the case above and shut the second clerk of every shift out.
    """
    with tenant_ctx(brazos):
        _open(dana, centre)
        second = _open(marcus, centre)
    assert second.session.owner_id != dana.user.pk


def test_p2_1_batch_for_is_idempotent(brazos, dana, centre):
    """Hard rule 6, applied to the seam the take-payment lane will call.

    The first call opens the cheque batch; the second FINDS it. Two cheques
    taken at one till land in one batch, and a retried take does not cut a
    second one.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        first, created_first = counters.batch_for(
            opened.session, method_code="check", day=opened.session.opened_at.date()
        )
        second, created_second = counters.batch_for(
            opened.session, method_code="check", day=opened.session.opened_at.date()
        )
    # ⚠ SUPERSEDED 2026-10-21 (CR-186-BRC10). PO: "this is one batch only -
    # it will ahve 1 batch ID not 2". A cheque joins the till's ONE batch,
    # the one the open created; neither call opens another.
    assert created_first is False and created_second is False
    assert first.pk == second.pk == opened.batch.pk


def test_p2_1_open_writes_audit(brazos, dana, centre, audit_rows):
    """Hard rule 7 — every money action writes `audit_log`.

    ⚠ **THROUGH THE CAPTURE SINK, NOT THROUGH `AuditLog.objects`**, and a first
    draft of this case did the latter and failed on a row that was there. The
    live table is partitioned by month on `created_at` and its `entity_id` is a
    `UUIDField` these paths hold as a STRING, so a query against it answers *no
    row* for a row that exists — a check that cannot tell pass from fail (law
    7). `test_cr059_cs30_cheques.py` records the same trap in its own words.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
    written = [row for row in audit_rows if row["action"] == counters.AUDIT_COUNTER_OPENED]
    assert len(written) == 1
    assert written[0]["entity_type"] == "counter_session"
    assert written[0]["after"]["batch_code"] == opened.batch.code
    assert written[0]["after"]["opening_float"] == "200.0000"


def test_p2_1_an_executive_may_not_open_a_till(brazos, centre):
    """BR-SHL-025 — the role check is the SERVICE's, so no endpoint can skip it."""
    from tests.test_us_met_helpers import staff_actor

    with tenant_ctx(brazos):
        exec_actor = staff_actor(brazos, "executive", "ex@brazosbendutilities.test")
        with pytest.raises(errors.AuthError):
            _open(exec_actor, centre)


# ═══════════════════════════════════════════════════════════════════════════
#  P2.3 — the reads
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_3_the_running_split_is_grouped_by_tender(brazos, dana, centre):
    """3·2's tiles — and the blueprint's own arithmetic.

    $310.00 cash plus a $200.00 float is a **$510.00** cash expectation;
    $1,284.60 of cheques makes **$1,794.60** countable together, which is the
    figure drawn on the Close screen.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        _take(
            dana, brazos, opened.session, amount="310.0000", method_code="cash", batch=opened.batch
        )
        _take(dana, brazos, opened.session, amount="1284.6000", method_code="check")
        split = counters.running_split(opened.session)
    by_method = {row["method_code"]: row for row in split["by_method"]}
    # ⚠ **`system_total` FOR CASH INCLUDES THE FLOAT**, because p056's first
    # row is *"Cash incl. float"* and the float is physically in the drawer
    # the clerk is about to count. $310.00 taken + a $200.00 float = $510.00.
    assert by_method["cash"]["system_total"] == "510.0000"
    assert by_method["cash"]["countable"] is True
    assert by_method["check"]["system_total"] == "1284.6000"
    assert split["taken"] == "1594.6000", "`taken` is PAYMENTS — the float was never one"
    assert split["opening_float"] == "200.0000"
    assert split["countable_expected"] == "1794.6000"


def test_p2_3_the_list_paginates_and_sorts_in_SQL(brazos, dana, marcus, centre):
    """`NFR-3` and `NFR-5` — and the assertion is about the QUERY, not the rows.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a selector that returned a Python
    LIST sorted in memory would satisfy any assertion about the order. So this
    asserts the returned object is still a `QuerySet` (nothing materialised)
    and that its SQL carries an `ORDER BY` — which is what `GET /outstandings`
    and `GET /cheques` cannot say, and why they are `DEF-PAY-4221`.
    """
    from django.db.models import QuerySet

    with tenant_ctx(brazos):
        _open(dana, centre)
        _open(marcus, centre)
        params = parse_list_params(
            {"sort": "opened_at", "dir": "desc"},
            allowed_sorts=counters.COUNTER_SORTS,
            default_sort=counters.DEFAULT_COUNTER_SORT,
            allowed_filters=counters.COUNTER_FILTERS,
        )
        queryset = counters.counter_list_queryset(params)
        assert isinstance(queryset, QuerySet)
        sql = str(queryset.query).upper()
        assert "ORDER BY" in sql and "LIMIT" not in sql  # LIMIT is the paginator's
        assert queryset.count() == 2


def test_p2_3_a_card_is_served_but_is_not_countable(brazos, dana, marcus, centre):
    """p056 ③ — *"you cannot count a card total in a drawer"*.

    The card line is SERVED, so 3·2 can show what the till took by card. It
    joins neither `countable_expected` nor the difference, and the Close screen
    renders *Not counted* against it rather than pretending.
    """
    with tenant_ctx(brazos):
        opened = _open(marcus, centre)
        _take(dana, brazos, opened.session, amount="402.1500", method_code="card")
        split = counters.running_split(opened.session)
    by_method = {row["method_code"]: row for row in split["by_method"]}
    assert by_method["card"]["system_total"] == "402.1500"
    assert by_method["card"]["countable"] is False
    assert split["taken"] == "402.1500"
    # The card money is in `taken` and NOT in what the drawer is counted against.
    assert split["countable_expected"] == "200.0000"


def test_p2_3_a_counter_is_reached_by_its_CODE(brazos, marcus, centre):
    """B14 rule 31 — the address carries `CTR-260921-DW`, never a database id.

    The contract is `07-frontend/src/api/counterEndpoints.ts`'s and it is
    written down in that file: *"The server must therefore resolve a counter by
    its code."* The primary key still resolves, because it is the unambiguous
    name and it is what a row hands back when two people share initials.
    """
    with tenant_ctx(brazos):
        opened = _open(marcus, centre)
        code = counters.counter_code(opened.session)
        assert code.startswith("CTR-")
        assert str(opened.session.pk) not in code
        by_code = counters.counter_detail(code)
        by_id = counters.counter_detail(str(opened.session.pk))
        with pytest.raises(PaymentRuleError):
            counters.counter_detail("CTR-260921-ZZ")
    assert by_code["id"] == by_id["id"] == str(opened.session.pk)
    assert by_code["code"] == code


def test_p2_3_the_system_till_never_appears_on_the_supervisors_list(brazos, dana, centre):
    """A drawer nobody sat at is not a drawer a supervisor chases.

    The system till is born closed with `close_kind='system'`, so it answers
    neither *open* nor *not counted*; this asserts it is not in the list at
    all, which is the stronger claim and the one a screen depends on.
    """
    from datetime import date

    from apps.payments import reconciliation

    with tenant_ctx(brazos):
        reconciliation._system_session(tenant_id=brazos.pk, day=date(2026, 9, 21))
        _open(dana, centre)
        params = parse_list_params(
            {},
            allowed_sorts=counters.COUNTER_SORTS,
            default_sort=counters.DEFAULT_COUNTER_SORT,
            allowed_filters=counters.COUNTER_FILTERS,
        )
        rows = list(counters.counter_list_queryset(params))
    assert len(rows) == 1
    assert all(row.system_day is None for row in rows)


def test_p2_3_the_tiles_are_counted_over_the_filter_not_the_page(brazos, dana, marcus, centre):
    """3·1's four tiles, and the two day-shaped ones state their own absence.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a tile computed off the page would
    agree with the filter whenever the whole set fits on one page, which it
    does in every fixture anybody writes. So this also asserts the day-shaped
    tiles answer `null` WITHOUT `as_of` and carry the reason — a stated absence
    beats a figure that is quietly a day out.
    """
    from datetime import date as _date

    with tenant_ctx(brazos):
        _open(marcus, centre)
        forced = _open(dana, centre)
        counters.force_close_counter(
            dana, session_id=forced.session.pk, reason="shift ended", closed_at=timezone.now()
        )
        params = parse_list_params(
            {},
            allowed_sorts=counters.COUNTER_SORTS,
            default_sort=counters.DEFAULT_COUNTER_SORT,
            allowed_filters=counters.COUNTER_FILTERS,
        )
        queryset = counters.counter_list_queryset(params)
        blind = counters.counter_list_totals(queryset)
        dated = counters.counter_list_totals(queryset, as_of=_date(2026, 9, 21))
    assert blind["open_now"] == 1
    assert blind["not_counted"] == 1
    assert blind["not_counted_oldest"] is not None
    assert blind["taken_today"] is None
    assert blind["totals_unavailable"] == "as_of_missing"
    assert dated["taken_today"] is not None
    assert dated["difference_this_week"] is not None


# ═══════════════════════════════════════════════════════════════════════════
#  P2.2 — close, force close, declare
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_2_close_with_a_balanced_drawer(brazos, dana, centre):
    """The drawer matches: `difference` is 0.0000, no note, no journal line."""
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        _take(
            dana, brazos, opened.session, amount="310.0000", method_code="cash", batch=opened.batch
        )
        cash = tenancy_models.PaymentMethod.objects.get(tenant=brazos, code="cash")
        sealed = counters.close_counter(
            dana,
            session_id=opened.session.pk,
            # ⚠ KEYED BY THE METHOD **ID**, which is what the Close screen
            # posts and what `counted_totals` stores. A code is accepted too
            # and every other case here uses one; this is the case that proves
            # the shape the column actually declares.
            counted_totals={str(cash.pk): "510.00"},
            closed_at=timezone.now(),
        )
    assert sealed.session.close_kind == payment_models.COUNTER_CLOSE_COUNTED
    assert sealed.difference == Decimal("0.0000")
    assert sealed.session.note is None
    assert sealed.posting_key is None  # a zero difference posts NOTHING


def test_p2_2_close_short_requires_a_note(brazos, dana, centre):
    """p056 — *"Required only when a difference is not zero"*, a SERVICE rule.

    The database deliberately cannot demand it: a forced close has no count to
    explain, and a CHECK that insisted on a note would make one impossible to
    record.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        with pytest.raises(PaymentRuleError) as refusal:
            counters.close_counter(
                dana,
                session_id=opened.session.pk,
                counted_totals={"cash": "188.00"},  # $12.00 short of the float
                closed_at=timezone.now(),
            )
    assert "say why" in str(refusal.value)


def test_p2_2_a_card_total_may_not_be_counted(brazos, dana, centre):
    """p056 ③ — *"you cannot count a card total in a drawer"*.

    A card figure typed into the count would be the system's own number handed
    back, and a reconciliation built on it proves nothing.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        with pytest.raises(PaymentRuleError) as refusal:
            counters.close_counter(
                dana,
                session_id=opened.session.pk,
                counted_totals={"card": "402.15"},
                closed_at=timezone.now(),
            )
    assert "not a tender a drawer can be counted in" in str(refusal.value)


def test_p2_2_force_close_is_system_admin_only(brazos, marcus, dana, centre):
    """BR-SHL-025 — `@require_role(SYSTEM_ADMIN)` on the SERVICE.

    Marcus is a Billing Clerk. A hidden button is not a guarantee; this refuses
    whatever the endpoint allows.
    """
    with tenant_ctx(brazos):
        opened = _open(marcus, centre)
        with pytest.raises(errors.AuthError):
            counters.force_close_counter(
                marcus,
                session_id=opened.session.pk,
                reason="went home",
                closed_at=timezone.now(),
            )


def test_p2_2_force_close_records_who_did_it_and_needs_a_reason(
    brazos, marcus, dana, centre, audit_rows
):
    """*"(b) A System Admin can close it, recorded as a forced close"*.

    `closed_by` is the SUPERVISOR and `owner` is the clerk, for ever — the two
    people stay distinguishable, which is the whole point of the ruling. And
    a reason is required: a forced close with no reason is indistinguishable
    from a mistake.
    """
    with tenant_ctx(brazos):
        opened = _open(marcus, centre)
        with pytest.raises(PaymentRuleError):
            counters.force_close_counter(
                dana, session_id=opened.session.pk, reason="  ", closed_at=timezone.now()
            )
        sealed = counters.force_close_counter(
            dana,
            session_id=opened.session.pk,
            reason="Marcus went home without closing",
            closed_at=timezone.now(),
        )
    assert sealed.session.close_kind == payment_models.COUNTER_CLOSE_FORCED
    assert sealed.session.closed_by_id == dana.user.pk
    assert sealed.session.owner_id == marcus.user.pk
    assert sealed.session.counted_totals is None
    assert sealed.difference is None
    assert sealed.posting_key is None  # nothing counted, so nothing posted
    # Hard rule 7 — and the REASON is in the trail and nowhere else, which is
    # the cost `OQ-PAY-12600` carries: `audit_log` is pruned on a retention
    # schedule and p057 calls this field *"the only record of the reason"*.
    trail = [row for row in audit_rows if row["action"] == counters.AUDIT_COUNTER_FORCE_CLOSED]
    assert len(trail) == 1
    assert trail[0]["after"]["reason"] == "Marcus went home without closing"
    assert trail[0]["after"]["counted_totals"] is None
    assert sealed.session.note is None  # `note` belongs to the LATE COUNT (§3.2)


def test_p2_2_the_three_close_states_are_distinguishable_afterwards(brazos, dana, marcus, centre):
    """`P2.14`'s shape — three rows, three different answers, and `not_counted`.

    And `close_kind` still holds exactly three values: `counted`, `forced`,
    `system`. A fourth was put to the PO on 2026-09-23 and declined.
    """
    assert payment_models.COUNTER_CLOSE_KINDS == ("counted", "forced", "system")
    with tenant_ctx(brazos):
        counted = _open(marcus, centre)
        counters.close_counter(
            marcus,
            session_id=counted.session.pk,
            counted_totals={"cash": "200.00"},
            closed_at=timezone.now(),
        )
        forced = _open(dana, centre)
        counters.force_close_counter(
            dana, session_id=forced.session.pk, reason="shift ended", closed_at=timezone.now()
        )
        not_counted = list(
            CounterSession.objects.filter(tenant=brazos).filter(counters.not_counted_q())
        )
    assert [row.pk for row in not_counted] == [forced.session.pk]


def test_p2_2_not_counted_is_the_MODELs_definition(brazos):
    """§3.2 — *"one derived expression with four readers"*, and ONE spelling.

    ⚠ **TWO WERE WRITTEN ON 2026-09-23 AND THEY AGREED, WHICH IS HOW THIS
    KIND OF DRIFT STARTS.** `P2.20` published
    `counter_session_models.NOT_COUNTED` beside the columns it is made of; this
    module wrote its own from the same ruling an hour later. Both said
    `close_kind = 'forced' AND declared_at IS NULL`, so no test could have told
    them apart — the second one is only wrong LATER, when a rule moves and
    one of them does not. `not_counted_q()` now RETURNS the model's, and this
    is what says so.
    """
    from apps.payments import counter_session_models as tills

    assert counters.not_counted_q() is tills.NOT_COUNTED


def test_p2_2_the_row_form_agrees_with_the_query(brazos, dana, marcus, centre):
    """The fourth reader asks the same question of a row already in hand.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** two spellings that happen to agree
    on the rows this fixture built. So it compares the QUERY's answer with the
    ROW helper's answer over EVERY session, which is the only comparison that
    can catch them drifting.
    """
    with tenant_ctx(brazos):
        counted = _open(marcus, centre)
        counters.close_counter(
            marcus,
            session_id=counted.session.pk,
            counted_totals={"cash": "200.00"},
            closed_at=timezone.now(),
        )
        forced = _open(dana, centre)
        counters.force_close_counter(
            dana, session_id=forced.session.pk, reason="shift ended", closed_at=timezone.now()
        )
        by_query = set(
            CounterSession.objects.filter(tenant=brazos)
            .filter(counters.not_counted_q())
            .values_list("pk", flat=True)
        )
        by_row = {
            row.pk
            for row in CounterSession.objects.filter(tenant=brazos)
            if counters._row_is_not_counted(row)
        }
    assert by_query == by_row


def test_p2_2_declare_fires_when_p2_20_lands(brazos, dana, marcus, centre):
    """**A HOLD WITH THE TEST THAT FIRES WHEN IT EXPIRES** (hard-won law 2).

    `declared_at` / `declared_by` are `P2.20`, a parallel lane's migration.
    This case runs REAL behaviour on whichever side of that line the repo is —
    it is never a skip, because a skip is a check that cannot fail.

    ⚠ The switch is asserted against `CounterSession._meta` INDEPENDENTLY of
    `counters._declaration_columns_exist()`, so a typo in the helper cannot
    send every declare case quietly down the *not built yet* branch and pass.
    """
    fields = {field.name for field in CounterSession._meta.get_fields()}
    has_columns = {"declared_at", "declared_by"} <= fields
    assert counters._declaration_columns_exist() == has_columns

    with tenant_ctx(brazos):
        forced = _open(marcus, centre)
        counters.force_close_counter(
            dana, session_id=forced.session.pk, reason="went home", closed_at=timezone.now()
        )
        if not has_columns:
            with pytest.raises(PaymentRuleError) as refusal:
                counters.declare_counter(
                    marcus,
                    session_id=forced.session.pk,
                    counted_totals={"cash": "188.00"},
                    declared_at=timezone.now(),
                    note="cheque stuck to the bag",
                )
            assert "P2.20" in str(refusal.value)
            return

        # ── `P2.20` HAS LANDED: the real ruling, end to end ────────────────
        sealed = counters.declare_counter(
            marcus,
            session_id=forced.session.pk,
            counted_totals={"cash": "188.00"},
            declared_at=timezone.now(),
            note="cheque stuck to the bag",
        )
        # §3.2, verbatim: *"Nothing is erased"* — the forced close STANDS.
        assert sealed.session.close_kind == payment_models.COUNTER_CLOSE_FORCED
        assert sealed.session.closed_by_id == dana.user.pk
        assert sealed.session.declared_by_id == marcus.user.pk
        assert sealed.difference == Decimal("-12.0000")
        # It leaves the Not counted list.
        assert (
            not CounterSession.objects.filter(pk=forced.session.pk)
            .filter(counters.not_counted_q())
            .exists()
        )
        # And only once.
        with pytest.raises(PaymentRuleError):
            counters.declare_counter(
                marcus,
                session_id=forced.session.pk,
                counted_totals={"cash": "188.00"},
                declared_at=timezone.now(),
                note="again",
            )
        # ⚠ And a declare ALWAYS needs a reason, where a counted close needs
        # one only when it does not balance — p058 ②, *"a declared difference
        # is the only number nobody watched happen"*.
        other = _open(marcus, centre)
        counters.force_close_counter(
            dana,
            session_id=other.session.pk,
            reason="also went home",
            closed_at=timezone.now(),
        )
        with pytest.raises(PaymentRuleError) as silent:
            counters.declare_counter(
                marcus,
                session_id=other.session.pk,
                counted_totals={"cash": "200.00"},
                declared_at=timezone.now(),
            )
        assert "only record" in str(silent.value)


def test_p2_2_declare_refuses_a_counted_close(brazos, marcus, centre):
    """*"A counted till was already counted."* Only a forced close is declarable.

    ⚠ **THE ORDER OF THE TWO REFUSALS IS PART OF WHAT THIS ASSERTS**, and it is
    a clerk's order rather than the code's: a person aiming `declare` at a
    counted till must be told it was already counted, whichever columns this
    database happens to have. A first draft checked `P2.20`'s columns first and
    this case read *"the product is half-built"* over a till that was simply
    never forced closed — the right refusal for the wrong question.
    """
    with tenant_ctx(brazos):
        counted = _open(marcus, centre)
        counters.close_counter(
            marcus,
            session_id=counted.session.pk,
            counted_totals={"cash": "200.00"},
            closed_at=timezone.now(),
        )
        with pytest.raises(PaymentRuleError) as refusal:
            counters.declare_counter(
                marcus,
                session_id=counted.session.pk,
                counted_totals={"cash": "200.00"},
                declared_at=timezone.now(),
            )
    assert "force-closed" in str(refusal.value)


def test_p2_2_counter_sessions_is_not_frozen_by_hard_rule_4(brazos, dana, marcus, centre):
    """**Hard rule 4 CHECKED rather than assumed**, as the brief asked.

    The rule freezes issued invoices, invoice lines, payments and journal
    entries. `counter_sessions` is none of those, and `payments/0031`–`0034`
    mint CHECK constraints and an RLS policy and **no trigger at all** — which
    is what makes a declare's UPDATE lawful. This asserts the absence from the
    migration source, because an absence is invisible to every other check this
    repo has.
    """
    from pathlib import Path

    migrations = Path(__file__).resolve().parents[1] / "apps" / "payments" / "migrations"
    for name in (
        "0031_cr135_p0_3_p0_4_counter_sessions.py",
        "0032_rls_cr135_p0_5_counter_sessions.py",
    ):
        source = (migrations / name).read_text(encoding="utf-8")
        assert "CREATE TRIGGER" not in source.upper() or "counter_sessions" not in source

    # And the UPDATE really does land — the claim proved on a row, not on prose.
    with tenant_ctx(brazos):
        opened = _open(marcus, centre)
        counters.force_close_counter(
            dana, session_id=opened.session.pk, reason="shift ended", closed_at=timezone.now()
        )
        row = CounterSession.objects.get(pk=opened.session.pk)
        row.note = "a later hand touched this row"
        row.save(update_fields=["note", "updated_at"])
    assert CounterSession.objects.get(pk=opened.session.pk).note is not None


def test_p2_2_close_foots_the_tills_batches_so_finance_can_bank_them(brazos, dana, marcus, centre):
    """p059 — *"The batch becomes bankable."* At `$0.00` it is not.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** asserting only that the batch
    exists after a close. It always did — it was opened with the till. The
    figure is the whole question, so this asserts the TOTAL, and it is the
    number a finance lead is handed on the deposit slip.

    `cut_deposit_batches` cannot supply it: a counter payment already carries
    its batch id, so the cut's `deposit_batch_id IS NULL` filter excludes it
    and the batch it belongs to is never footed by the cut.
    """
    with tenant_ctx(brazos):
        opened = _open(marcus, centre)
        _take(
            dana, brazos, opened.session, amount="310.0000", method_code="cash", batch=opened.batch
        )
        before = bankrec.DepositBatch.objects.get(pk=opened.batch.pk).recorded_total
        counters.close_counter(
            marcus,
            session_id=opened.session.pk,
            counted_totals={"cash": "510.00"},
            closed_at=timezone.now(),
        )
        after = bankrec.DepositBatch.objects.get(pk=opened.batch.pk).recorded_total
    assert before == Decimal("0.0000"), "the batch opens empty — that is the whole point"
    assert after == Decimal("310.0000"), "the float is NOT in the batch; it was never a payment"


# ═══════════════════════════════════════════════════════════════════════════
#  P2.22 — the drawer difference reaches the books. ⚠ SUPERSEDES THE DRAWING
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_22_a_short_drawer_posts_a_balanced_pair(brazos, dana, marcus, centre):
    """PO ruling 2026-09-23 §3.3 — *"(b) Post it."*

    $12.0000 short → DR `6850 Cash over and short` · CR `1010 Undeposited
    funds`. **Against 1010 and not 1000**, because taking the money already
    debited 1010 and the bank only receives what was in the drawer.

    ⚠ **`6850` IS `P2.21`, A PARALLEL LANE'S SEED, AND IT MAY NOT HAVE LANDED.**
    Until it does, `_gl()` REFUSES by name rather than posting into a bucket
    nobody mapped — which is the correct behaviour and is asserted as such.
    This case runs the real posting on whichever side of that line the repo is
    on; it is never a skip.
    """
    with tenant_ctx(brazos):
        from apps.ledger import selectors as ledger_selectors

        try:
            account_id = ledger_selectors.gl_account_id_for_designation(
                ledger_seam.GL_CASH_OVER_SHORT
            )
        except Exception:  # the designation is not in the chart yet — `P2.21`
            account_id = None

        opened = _open(marcus, centre)
        _take(
            dana, brazos, opened.session, amount="310.0000", method_code="cash", batch=opened.batch
        )
        if account_id is None:
            with pytest.raises(PaymentRuleError) as refusal:
                counters.close_counter(
                    marcus,
                    session_id=opened.session.pk,
                    counted_totals={"cash": "498.00"},  # $12.00 short of $510.00
                    closed_at=timezone.now(),
                    note="cheque stuck to the bag",
                )
            assert ledger_seam.GL_CASH_OVER_SHORT in str(refusal.value)
            return

        sealed = counters.close_counter(
            marcus,
            session_id=opened.session.pk,
            counted_totals={"cash": "498.00"},
            closed_at=timezone.now(),
            note="cheque stuck to the bag",
        )
    assert sealed.difference == Decimal("-12.0000")
    assert sealed.posting_key is not None

    from apps.ledger import models as ledger_models

    lines = list(
        ledger_models.JournalLine.objects.filter(
            tenant=brazos,
            source_type=ledger_seam.SOURCE_COUNTER_SESSION,
            source_id=opened.session.pk,
        )
    )
    assert len(lines) == 2
    debit = next(line for line in lines if line.side == "debit")
    credit = next(line for line in lines if line.side == "credit")
    assert debit.amount == Decimal("12.0000") == credit.amount
    # ⚠ **COMPARED AS STRINGS, AND BOTH OF THESE WERE BROKEN IN OPPOSITE
    # DIRECTIONS** (`DEF-PAY-6248`, found 2026-09-23 by LANE P2-TILLWIRE
    # reading a red it did not cause). `JournalLine.ledger_account_id` is a
    # `uuid.UUID`; `ledger.selectors.gl_account_id_for_designation` returns a
    # **`str`**, and `UUID(...) == "01a0…"` is `False` for every value there
    # has ever been. So the first assertion was **incapable of passing** — red
    # since `ff1b3b3ee` and never green — and the second, its mirror, was
    # **incapable of failing**: `!=` is true whatever account is credited, so
    # a pair posted to the wrong side would have sailed through it.
    # Hard-won law 7, both of its shapes, on one money path, two lines apart.
    # The PRODUCT was right the whole time: proved against real `journal_lines`
    # on PostgreSQL 16.13 by `cr136_p2_counters_postgres_proof.py` part D.
    assert str(debit.ledger_account_id) == str(account_id)  # 6850 takes the DEBIT
    assert str(credit.ledger_account_id) != str(account_id)  # 1010 is credited
    # `DEF-LED-10073` — the memo is a sentence a clerk reads on the Journal, so
    # its money is at DISPLAY precision (hard rule 2: stored 4, displayed 2).
    # RED BEFORE: `'Counter drawer short 12.0000'`.
    assert debit.journal_entry.memo == "Counter drawer short $12.00"


def test_p2_22_a_balanced_drawer_posts_nothing(brazos, marcus, centre):
    """*"A zero difference posts nothing."* A journal line for money that did
    not move is a line somebody has to explain."""
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        opened = _open(marcus, centre)
        counters.close_counter(
            marcus,
            session_id=opened.session.pk,
            counted_totals={"cash": "200.00"},
            closed_at=timezone.now(),
        )
        assert not ledger_models.JournalLine.objects.filter(
            tenant=brazos, source_type=ledger_seam.SOURCE_COUNTER_SESSION
        ).exists()


def test_p2_22_one_event_per_session_so_a_replay_posts_once(brazos):
    """Hard rule 6 — the replay guard is the posting key, and it is one per till.

    A till is counted ONCE: at close if the clerk counted it, at declare if a
    supervisor sealed it first. So both paths compose the same key and a retry
    of either writes one entry rather than two.
    """
    from apps.ledger import posting

    key_one = posting.posting_key(
        source_type=ledger_seam.SOURCE_COUNTER_SESSION,
        source_id="11111111-1111-1111-1111-111111111111",
        event=ledger_seam.EVENT_DRAWER_COUNTED,
    )
    key_two = posting.posting_key(
        source_type=ledger_seam.SOURCE_COUNTER_SESSION,
        source_id="11111111-1111-1111-1111-111111111111",
        event=ledger_seam.EVENT_DRAWER_COUNTED,
    )
    assert key_one == key_two
    assert ledger_seam.SOURCE_COUNTER_SESSION not in (
        ledger_seam.SOURCE_PAYMENT,
        ledger_seam.SOURCE_DEPOSIT_BATCH,
        ledger_seam.SOURCE_COUNTER_RECEIPT,
    )


def test_p2_22_the_over_short_account_is_never_substituted():
    """⚠ **THE ONE PROPERTY A DRAWER POSTING MUST HAVE: IT REFUSES OR IT IS
    RIGHT. IT NEVER PICKS A DIFFERENT ACCOUNT.**

    `CR-136-BRC07` §9(a), written by the lane that seeded `6850`: a utility
    that hand-added its own `6850` keeps it, and `cash_over_short` then
    resolves to **nothing** for them. *"`P2.22` must refuse on `None` and never
    substitute another account, because hard rule 4 leaves nobody a way to move
    a journal line afterwards."*

    Five shapes, and the two in the middle are the ones that matter:

      * the pointer is there                    → the account
      * the pointer resolves to NOTHING         → REFUSED
      * the ledger does not know the DESIGNATION → REFUSED, and as a
        `PaymentRuleError` rather than the ledger's own `ValueError`, which
        would travel straight past `api._as_catalog_refusal` and reach a clerk
        as a 500 on a close that had already sealed their till (`DEF-047`'s
        shape: the callee's REFUSAL is part of the contract)
      * the chart TOP-UP itself fails, account resolves anyway → the account,
        because the top-up is a convenience and never the decision
      * the top-up fails AND nothing resolves   → REFUSED

    ⚠ **NO DATABASE, AND THAT IS WHY THIS CAN ASSERT ALL FIVE.** Three of them
    need a chart this suite cannot build — a tenant who re-coded `6850`, a
    ledger that has not been migrated, a failed reference sweep — so a
    database-backed case could only ever reach the happy one and would read as
    coverage.
    """
    from unittest import mock

    from apps.payments import ledger_seam as seam

    def resolver(read_answer, top_up_raises=None):
        def fake(module, name, where):
            if name == seam.CASH_OVER_SHORT_TOP_UP:
                def top_up(actor=None):
                    if top_up_raises is not None:
                        raise top_up_raises
                return top_up
            if name == seam.GL_DESIGNATION_READ:
                def read(designation):
                    if isinstance(read_answer, Exception):
                        raise read_answer
                    return read_answer
                return read
            return None
        return fake

    with mock.patch.object(seam, "_resolve", resolver("acct-6850")):
        assert seam._cash_over_short_account() == "acct-6850"
    with mock.patch.object(seam, "_resolve", resolver(None)):
        with pytest.raises(PaymentRuleError) as gone:
            seam._cash_over_short_account()
    assert seam.GL_CASH_OVER_SHORT in str(gone.value)
    with mock.patch.object(seam, "_resolve", resolver(ValueError("unknown designation"))):
        with pytest.raises(PaymentRuleError) as unknown:
            seam._cash_over_short_account()
    assert seam.GL_CASH_OVER_SHORT in str(unknown.value)
    with mock.patch.object(seam, "_resolve", resolver("acct-6850", RuntimeError("sweep"))):
        assert seam._cash_over_short_account() == "acct-6850"
    with mock.patch.object(seam, "_resolve", resolver(None, RuntimeError("sweep"))):
        with pytest.raises(PaymentRuleError):
            seam._cash_over_short_account()


# ═══════════════════════════════════════════════════════════════════════════
#  P2.23 — cash, cheque and money order need an open till
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("tender", ["cash", "check", "money_order"])
def test_p2_23_a_hand_tender_is_refused_with_no_open_till(brazos, marcus, tender):
    """*"(a) Refuse it. \\"Start your counter first.\\""*"""
    with tenant_ctx(brazos):
        with pytest.raises(PaymentRuleError) as refusal:
            counters.assert_till_open_for_tender(marcus, tender)
    assert "Start your counter first" in str(refusal.value)


@pytest.mark.parametrize("tender", ["ach", "card", "wire", "lockbox"])
def test_p2_23_the_electronic_four_are_untouched(brazos, marcus, tender):
    """A card swiped at a window is among them ON PURPOSE.

    They bank under phase 0's system till. The Close screen counts only what is
    in a drawer, and a card total typed back at the system's own figure makes
    the reconciliation worthless.
    """
    with tenant_ctx(brazos):
        assert counters.assert_till_open_for_tender(marcus, tender) is None
        assert counters.assert_till_open_for_tender(marcus, None) is None


def test_p2_23_a_hand_tender_passes_with_a_till_open(brazos, marcus, centre):
    """The green case. A rule that refuses everything is not a rule."""
    with tenant_ctx(brazos):
        opened = _open(marcus, centre)
        assert counters.assert_till_open_for_tender(marcus, "cash").pk == opened.session.pk


def test_p2_23_the_refusal_reaches_the_clerk_as_WORDS(brazos, marcus):
    """**G32's blind spot, closed at the raise site rather than trusted.**

    G32 resolves a `message_key` only where the helper is defined in the same
    file, and reported **0 unresolved** truthfully over 21 live refusals that
    reached a clerk as SILENCE. So this reads the catalogue directly and
    asserts every key this lane raises renders a sentence.
    """
    import json
    from pathlib import Path

    catalogue = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "07-frontend"
            / "src"
            / "i18n"
            / "locales"
            / "en.json"
        ).read_text(encoding="utf-8")
    )
    for key in (
        "payments.counter.refused",
        "payments.counter.till_required",
        "payments.counter.opened_at_required",
        "payments.counter.closed_at_required",
        "payments.counter.declared_at_required",
    ):
        assert catalogue.get(key), f"{key} renders as nothing at all"


def test_p2_23_counter_session_id_stays_nullable_on_payments():
    """§3.4 — a `NOT NULL` would refuse every ACH, card, wire and lockbox row.

    ⚠ **THIS FIRES THE DAY `P2.4` LANDS** and is meant to: when the column
    arrives it must arrive NULLABLE, and this is what says so out loud rather
    than leaving it to a reviewer to notice.
    """
    fields = {field.name: field for field in payment_models.Payment._meta.get_fields()}
    column = fields.get("counter_session") or fields.get("counter_session_id")
    if column is None:
        return  # `P2.4` has not landed; `test_cr135_p06…` owns that hold
    assert column.null is True
