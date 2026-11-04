# ── Trace ──────────────────────────────────────────────
# Change:  CR-136-BRC07 — phase 2, the counter. `P2.12` (open and its batch in
#          ONE transaction, a second open refused), `P2.14` (close with and
#          without a difference — three states from three ENDPOINTS, each
#          distinguishable afterwards) and `P2.15` (the ledger pair, and the
#          absence of one).
# Ruling:  PO 2026-09-23 §3.3, verbatim: *"(b) Post it. A short writes a
#          balanced pair to a cash over/short account the day it is declared.
#          Needs one new account added to the chart"* — which SUPERSEDES the
#          blueprint's own p018 line for `P2.15`, *"Balanced at take; closing
#          writes no journal line. Counting is not a posting."*
#          PO 2026-09-23 §3.2: *"(a) Keep it as a forced close and add the late
#          count beside it"* — which is why `P2.14` has FOUR states to tell
#          apart and `close_kind` still has three values.
# Rules:   CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money to four
#          decimals) · hard rule 5 (only the ledger posting service writes
#          journal lines) · hard rule 6 (idempotency) · hard rule 7
#          (`audit_log`) · BR-SHL-025 · hard-won law 2 (built is not wired —
#          a service with no endpoint behind it is not a thing a clerk can do)
#          · hard-won law 7 (the five shapes of a check that does not check) ·
#          hard-won law 14 (SQLite cannot answer three of these)
# Tests:   this file, plus `10-scripts/cr136_p2_counters_postgres_proof.py`
#          parts A/B/C/D for everything SQLite cannot reach.
# ───────────────────────────────────────────────────────
"""The counter's three test tasks, written against the layer a clerk meets.

WHY THIS FILE EXISTS BESIDE `test_cr136_p2_counters.py`
-------------------------------------------------------
`LANE P2-API` wrote that file with the endpoints, and it is thorough. It
drives the **services**: `counters.open_counter`, `counters.close_counter`,
`counters.force_close_counter`, `counters.declare_counter`. Every case here
asks a question that one cannot, and the three tasks name the difference
themselves:

  * `P2.12` — the task says *"open and its batch in ONE transaction"* and the
    service cases prove exactly that. What nothing asked is whether a clerk
    pressing the button twice **reads a sentence or meets a 500**: the refusal
    has to survive `counters_api._as_catalog_refusal`, and a service test
    cannot see that layer at all. That is hard-won law 2 — built is not wired.
  * `P2.14` — the task says *"three states from three ENDPOINTS"*. The existing
    case is named `P2.14`'s shape and drives three SERVICES, over **two** of
    the states. `system` is never built there and the fourth — a late count
    sitting BESIDE a forced close (§3.2) — is not a state it counts at all.
  * `P2.15` — the task says *"the ledger pair, and the absence of one"*. The
    `P2.22` cases cover a SHORT drawer and a balanced one. **Nothing anywhere
    covers an OVER**, and nothing covers the posting happening at DECLARE,
    which is the half of §3.3 that makes *"the day it is declared"* true of a
    forced close.

WHAT IS DELIBERATELY NOT HERE (hard-won law 14)
------------------------------------------------
`config/settings/test.py` hardcodes in-memory SQLite and ignores
`DATABASE_URL`. So **the race, the aborted transaction and row-level security
are not in this file and cannot be**: SQLite serialises its writers, has no
aborted-transaction state and has no RLS, and all three would pass here by
vacuum. They are `10-scripts/cr136_p2_counters_postgres_proof.py`, run on
PostgreSQL 16, and part A is proved RED first by dropping the index.

⚠ **AND THE PostgreSQL PROOF FOUND SOMETHING THIS FILE CANNOT SEE**
(`DEF-PAY-6262`). `open_counter`'s `SELECT … then INSERT` turns a second open
into a sentence **only when the two presses are sequential**. Under a real
race the loser's INSERT dies on `uq_counter_sessions_open_owner` and the
`IntegrityError` travels straight past `counters_api`'s `except
PaymentRuleError`, so the clerk gets a 500 carrying a constraint name. The
atomic block still holds — one till, no orphan batch — which is why every
case below is TRUE and the defect is about the words, not the money.
"""

from __future__ import annotations

import uuid
from collections import Counter as _Counter
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.payments import counters, counters_api, ledger_seam, reconciliation, services
from apps.payments import bankrec_models as bankrec
from apps.payments import models as payment_models
from apps.payments.counter_session_models import CounterSession
from apps.tenancy import models as tenancy_models
from apps.tenancy import published_content_models as content_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401 — a fixture
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = [pytest.mark.django_db]

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent


@pytest.fixture()
def centre(brazos):
    """A walk-in counter for the till to be at."""
    with tenant_ctx(brazos):
        return content_models.ServiceCentre.objects.create(
            tenant=brazos,
            slug="counter-window-1",
            name="Main office",
            address="101 Bend Road, Brazos Bend, TX 77422",
        )


# ── the ENDPOINTS, called the way the wired stack calls them ────────────────
def _signed_in(actor):
    """The `request.user` a wired request carries, and it needs THREE things.

    ⚠ **A `users` ROW IS NOT ENOUGH AND THE WAY IT FAILS IS MISLEADING**
    (`test_cr136_p2_13` records the same trap in its own words). `identity.User`
    is a plain `models.Model` with no `is_authenticated`, so
    `core.permissions._role_of` answers `None` and the request is **403
    AUTH-002 before the view is ever entered** — which reads exactly like a
    permission bug in the endpoint under test.

    ⚠ **AND `role` HAS TO BE ON THE USER TOO, NOT ONLY ON THE REQUEST.**
    `api_call` sets `request.tenant_role`, which satisfies the DRF permission
    class; `payments.api._actor` then hands `request.user` STRAIGHT to the
    service, and `@require_role` reads `actor.role` off that object. A namespace
    with `is_authenticated` and no `role` clears the endpoint and is refused by
    the service — the same 403, one layer further in, and indistinguishable in
    the response.

    The id must still be the real person's: it becomes `counter_sessions.owner`,
    a foreign key into `users`.
    """
    return SimpleNamespace(
        id=actor.user.pk,
        pk=actor.user.pk,
        is_authenticated=True,
        role=actor.role,
    )


def _refusal(response):
    """The catalogue refusal a clerk actually meets, unwrapped.

    ⚠ **`pytest.raises` IS THE WRONG TOOL AT THIS LAYER AND IT WOULD HAVE BEEN
    A FALSE RED.** `@api_view` installs DRF's exception handler, so a `BizError`
    raised inside the view never leaves it: it is RENDERED, into a 422 carrying
    the catalogue code and the sentence. Asserting a raise would fail on a
    product that is behaving correctly, and asserting only `status_code != 201`
    would pass on a 500. So this asserts the code AND returns the sentence.
    """
    assert response.status_code == 422, response.data
    assert response.data["code"] == errors.BIZ_COMPLETENESS, response.data
    return response.data["params"]["detail"]


def _post_open(actor, tenant, centre, *, float_amount="200.0000"):
    """`POST /counters` — the route, the permission class and the refusal path.

    ⚠ **`counters_root` DISPATCHES ON THE VERB**, because `/counters` is one
    `path()` serving GET and POST (two entries with one pattern would leave the
    second unreachable for ever). So a test of the OPEN endpoint has to post to
    the root view, not to a view of its own — and if that dispatch ever broke,
    every case below would fail on a LIST body rather than on a session.
    """
    return api_call(
        counters_api.counters_root,
        "post",
        path="/api/counters",
        user=_signed_in(actor),
        role=actor.role,
        tenant=tenant,
        data={
            "service_centre_id": str(centre.pk),
            "opening_float": float_amount,
            "opened_at": timezone.now().isoformat(),
        },
    )


def _post(view, actor, tenant, session, payload):
    return api_call(
        view,
        "post",
        path="/api/counters/x",
        user=_signed_in(actor),
        role=actor.role,
        tenant=tenant,
        data=payload,
        counter_id=str(session.pk),
    )


def _open(actor, centre, *, float_amount="200.0000"):
    return counters.open_counter(
        actor,
        service_centre_id=centre.pk,
        opening_float=Decimal(float_amount),
        opened_at=timezone.now(),
    )


def _take(actor, tenant, *, amount, method_code, till=None):
    """A payment through the real write path — `P2.24`'s, never a direct stamp."""
    account = an_account(actor, tenant, account_no=f"A-{uuid.uuid4().hex[:6]}")
    recorded = services.record_payment(
        actor,
        account_id=account.pk,
        amount=Decimal(amount),
        posted_at=timezone.now(),
        cleared_at=timezone.now(),
        method_code=method_code,
        idempotency_reference=uuid.uuid4(),
        counter_session_id=None if till is None else till.pk,
    )
    return payment_models.Payment.objects.get(pk=recorded.payment_id)


def _lines(tenant, *, source_type, source_id):
    from apps.ledger import models as ledger_models

    return list(
        ledger_models.JournalLine.objects.filter(
            tenant=tenant, source_type=source_type, source_id=source_id
        )
    )


def _over_short_account():
    """`6850`'s id, or None when `P2.21`'s seed is not on this tenant's chart.

    Returned rather than skipped: a skip is a check that cannot fail, and every
    case that uses this asserts REAL behaviour on whichever side of that line
    the repository is (the shape `test_p2_2_declare_fires_when_p2_20_lands`
    established for `P2.20`).
    """
    from apps.ledger import selectors as ledger_selectors

    try:
        return ledger_selectors.gl_account_id_for_designation(ledger_seam.GL_CASH_OVER_SHORT)
    except Exception:  # the designation is not in the chart — `P2.21` has not run
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  `P2.12` — open and its batch in ONE transaction, and a second open refused
#
#  *"The ruling holds in code."* The ruling is the database's, and the half
#  that lives HERE is whether a person on the other side of the endpoint can
#  act on the answer.
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_12_the_open_endpoint_writes_the_session_AND_its_batch(brazos, dana, centre):
    """One request, two rows, and the batch belongs to THIS till.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7, habit 2): asserting that
    *a* deposit batch exists after the call. One nearly always does — phase 0's
    system till cuts them, and before `P0.6`'s re-key a batch was a DAY × tender
    row that any other lane's payment would have opened. So the assertion is
    `batch.session_id == session.pk`: the batch is this drawer's or the case
    fails, whatever else the tenant is holding.
    """
    with tenant_ctx(brazos):
        response = _post_open(dana, brazos, centre)
    assert response.status_code == 201, response.data
    body = response.data
    session = CounterSession.objects.get(pk=body["id"])
    batch = bankrec.DepositBatch.objects.get(session_id=session.pk)
    assert session.closed_at is None
    assert session.opening_float == Decimal("200.0000")
    # CR-186-BRC10 (PO 2026-10-21): the till's ONE batch holds every tender.
    assert batch.method_id is None
    # B14 rule 31 — the screen navigates by the CODE, and the code is served.
    assert body["code"]
    assert body["code"] != str(session.pk)


def test_p2_12_a_second_open_reaches_the_clerk_as_WORDS_not_a_500(brazos, dana, centre):
    """p017: *"refuses a second open counter for the same user"* — at the door.

    ⚠ **THIS IS THE CASE THE SERVICE SUITE CANNOT WRITE, AND IT IS HARD-WON LAW
    2.** `counters.open_counter` raising `PaymentRuleError` proves the rule; it
    proves nothing about what a clerk sees, because that depends on
    `counters_api._as_catalog_refusal` converting it. An uncaught exception out
    of a DRF view is a **500 with no sentence in it**, and a service-level test
    passes identically either way.

    ⚠ **AND *ANYTHING BUT A 201* WOULD BE THE FALSE PASS.** A 500 is not a 201
    either, and a 500 is exactly what `DEF-PAY-6262` records on the racing path.
    So `_refusal` names the STATUS, the catalogue CODE and the SENTENCE — three
    facts, of which only the third is the one a clerk reads.
    """
    with tenant_ctx(brazos):
        first = _post_open(dana, brazos, centre)
        assert first.status_code == 201
        detail = _refusal(_post_open(dana, brazos, centre))
    assert "already have a counter open" in detail
    # A refusal with no door is hard-won law 2's mirror: it names the till that
    # is in the way, so the screen can point at it.
    assert timezone.now().date().isoformat() in detail


def test_p2_12_a_refused_open_leaves_NEITHER_row_behind(brazos, dana, centre):
    """The transaction is one act at the endpoint too.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** asserting only *no batch*. If the
    batch were opened OUTSIDE the atomic block, a failed batch would leave the
    SESSION standing — a till with no drawer, which is the window the
    2026-09-21 ruling exists to close — and a *no batch* assertion would be
    green over it. So both counts are taken before and compared after.

    The failure is forced by deactivating the tenant's `cash` tender, which is
    what `batch_for` refuses on (`deposit_batches.method_id` is NOT NULL).
    """
    with tenant_ctx(brazos):
        sessions_before = CounterSession.objects.filter(tenant=brazos).count()
        batches_before = bankrec.DepositBatch.objects.filter(tenant=brazos).count()
        tenancy_models.PaymentMethod.objects.filter(
            tenant=brazos, code=counters.DRAWER_TENDER
        ).update(active=False)
        try:
            detail = _refusal(_post_open(dana, brazos, centre))
        finally:
            tenancy_models.PaymentMethod.objects.filter(
                tenant=brazos, code=counters.DRAWER_TENDER
            ).update(active=True)
        assert counters.DRAWER_TENDER in detail
        assert CounterSession.objects.filter(tenant=brazos).count() == sessions_before
        assert bankrec.DepositBatch.objects.filter(tenant=brazos).count() == batches_before


def test_p2_12_a_colleague_opens_their_own_till_through_the_same_endpoint(
    brazos, dana, marcus, centre
):
    """Three windows of one office are three tills — the mirror of the refusal.

    Without this, a refusal keyed on the TENANT rather than on the PERSON
    passes the case above and shuts the second clerk of every shift out. It is
    the whole reason `uq_counter_sessions_open_owner` carries `owner_id`.
    """
    with tenant_ctx(brazos):
        assert _post_open(dana, brazos, centre).status_code == 201
        second = _post_open(marcus, brazos, centre)
    assert second.status_code == 201
    assert second.data["id"] != str(
        CounterSession.objects.get(tenant=brazos, owner=dana.user, closed_at__isnull=True).pk
    )
    assert (
        CounterSession.objects.filter(tenant=brazos, closed_at__isnull=True).count() == 2
    )


def test_p2_12_the_race_is_proved_where_it_can_be_and_this_file_says_where(brazos):
    """⚠ **A DECLARED BLIND SPOT WITH NO POINTER IS INDISTINGUISHABLE FROM AN
    EMPTY ONE** (hard-won law 7, the `G32` shape).

    The four cases above are the SEQUENTIAL second open. The RACE — two
    terminals pressing *Start counter* in the same millisecond — cannot be run
    here at all: SQLite serialises its writers, so two "concurrent" opens are
    two sequential ones and `open_counter`'s own `SELECT … then INSERT` passes
    them on its own, with the index never consulted.

    This asserts that the file which DOES run it exists and still names the
    index, so the absence above cannot quietly become an absence everywhere.
    A test suite that silently stopped having a PostgreSQL proof would read
    exactly like one that never needed it.
    """
    proof = REPO / "10-scripts" / "cr136_p2_counters_postgres_proof.py"
    assert proof.is_file(), "the PostgreSQL half of `P2.12` has gone missing"
    source = proof.read_text(encoding="utf-8")
    assert "uq_counter_sessions_open_owner" in source
    assert "DROP INDEX" in source.upper(), "part A must still prove the index RED first"
    assert "def part_a3" in source, "the race through the SERVICE is `P2.12`'s own half"


# ═══════════════════════════════════════════════════════════════════════════
#  `P2.14` — close with and without a difference: three states from THREE
#  ENDPOINTS, each distinguishable afterwards
# ═══════════════════════════════════════════════════════════════════════════
def _four_states(brazos, dana, marcus, centre):
    """Build one of each, through the three ENDPOINTS plus the system path.

    Returns (counted, forced, declared, system). `dana` is a System Admin and
    is the supervisor; `marcus` is the Billing Clerk whose drawers these are.

    ⚠ **THE TENANT CONTEXT IS RE-ENTERED AROUND EVERY DIRECT CALL, AND A
    SINGLE OUTER `with` DOES NOT WORK.** `core.tenancy.tenant_context` CLEARS
    the context on exit rather than restoring what it replaced — correct for a
    background job, which must never carry one tenant into the next loop
    iteration — so `tests.test_us_ten_helpers.api_call` leaves the context
    **unset** when the view returns. A test that wraps endpoint calls and ORM
    reads in one outer block therefore loses its tenant at the FIRST endpoint
    and every later statement refuses with `AUTH-003 BR-TEN-003`, from a line
    that has nothing to do with the cause. That is worth the paragraph: the
    failure names `counters._tenant_id`, which reads like a product bug.
    """

    def served(response):
        """⚠ **EVERY ONE OF THESE IS CHECKED, BECAUSE A 403 IS SILENT HERE.**
        `api_call` returns a Response rather than raising, so an unasserted
        force-close that answered 403 would leave the till OPEN and the tally
        below would fail three states later with no sign of where. Asserting at
        the call site is what makes the failure name the act."""
        assert response.status_code in (200, 201), response.data
        return response

    with tenant_ctx(brazos):
        counted = _open(marcus, centre)
    served(
        _post(
            counters_api.counter_close,
            marcus,
            brazos,
            counted.session,
            {"counted_totals": {"cash": "200.00"}, "closed_at": timezone.now().isoformat()},
        )
    )
    with tenant_ctx(brazos):
        forced = _open(marcus, centre)
    served(
        _post(
            counters_api.counter_force_close,
            dana,
            brazos,
            forced.session,
            {"note": "went home without closing", "closed_at": timezone.now().isoformat()},
        )
    )
    with tenant_ctx(brazos):
        declared = _open(marcus, centre)
    served(
        _post(
            counters_api.counter_force_close,
            dana,
            brazos,
            declared.session,
            {"note": "shift ended", "closed_at": timezone.now().isoformat()},
        )
    )
    served(
        _post(
            counters_api.counter_declare,
            marcus,
            brazos,
            declared.session,
            {
                "counted_totals": {"cash": "200.00"},
                "declared_at": timezone.now().isoformat(),
                "note": "counted it Tuesday morning",
            },
        )
    )
    with tenant_ctx(brazos):
        system = reconciliation._system_session(tenant_id=brazos.pk, day=timezone.now().date())
        return (
            CounterSession.objects.get(pk=counted.session.pk),
            CounterSession.objects.get(pk=forced.session.pk),
            CounterSession.objects.get(pk=declared.session.pk),
            CounterSession.objects.get(pk=system.pk),
        )


def _signature(row):
    """What tells one closed till from another, read off the row itself.

    Four facts and no derived helper, deliberately: this is the comparison a
    supervisor's eye makes on 3·1, and if `not_counted_q()` and this ever
    disagree the case below is what says so.
    """
    return (
        row.close_kind,
        getattr(row, "declared_at", None) is not None,
        row.counted_totals is not None,
        row.owner_id is not None,
    )


def test_p2_14_the_three_endpoints_write_three_different_rows(brazos, dana, marcus, centre):
    """*"Three states from three endpoints."* Driven through all three.

    ⚠ **THE ENDPOINTS AND NOT THE SERVICES, AND THAT IS THE TASK'S OWN WORD.**
    Each carries a different permission class — `AdminOrClerk`, `SystemAdminOnly`,
    `AdminOrClerk` — and each composes its own body through `_sealed_body`. A
    service-level case cannot see a decorator, a payload key or a serialised
    field, and all three are what a screen actually consumes.
    """
    counted, forced, declared, system = _four_states(brazos, dana, marcus, centre)
    assert counted.close_kind == payment_models.COUNTER_CLOSE_COUNTED
    assert forced.close_kind == payment_models.COUNTER_CLOSE_FORCED
    # §3.2, verbatim: *"Keep it as a forced close and add the late count beside
    # it"*. A fourth `close_kind` was put to the PO the same day and DECLINED.
    assert declared.close_kind == payment_models.COUNTER_CLOSE_FORCED
    assert system.close_kind == payment_models.COUNTER_CLOSE_SYSTEM
    assert payment_models.COUNTER_CLOSE_KINDS == ("counted", "forced", "system")
    # The supervisor closed the forced one; the clerk owns it. Both survive.
    assert forced.closed_by_id == dana.user.pk
    assert forced.owner_id == marcus.user.pk


def test_p2_14_the_four_states_are_TOLD_APART_and_it_is_counted_not_looped(
    brazos, dana, marcus, centre
):
    """*"Each close kind is distinguishable afterwards."* Four, by a COUNT.

    ⚠ **A COUNT BEATS A LOOP ON A LIST.** `for row in rows: assert …` is green
    when the list silently shrinks — and it shrinks the moment a filter, a
    fixture or an RLS policy quietly drops a row, which is precisely the way
    this repository has lost coverage before. So the four signatures are
    tallied and the tally is asserted whole: a missing state fails, a doubled
    state fails, and a fifth state nobody meant to create fails.

    ⚠ **AND THE POINT IS THE PAIR THAT WOULD COLLAPSE.** If `declared_at` were
    dropped from the signature — or never written — `forced` and `declared`
    become one value and this reads `{forced: 2}`. That is the exact failure
    §3.2 exists to prevent: a till that was counted late becoming
    indistinguishable from one nobody ever counted.
    """
    rows = _four_states(brazos, dana, marcus, centre)
    tally = _Counter(_signature(row) for row in rows)
    assert tally == {
        ("counted", False, True, True): 1,   # counted at close, by its owner
        ("forced", False, False, True): 1,   # sealed by a supervisor, never counted
        ("forced", True, True, True): 1,     # the late count, BESIDE the forced close
        ("system", False, False, False): 1,  # nobody's, and born closed
    }
    assert len(tally) == 4, "two states share a signature — one of them is unreachable"


def test_p2_14_not_counted_holds_exactly_the_one_nobody_counted(brazos, dana, marcus, centre):
    """The derived expression over all four — §3.2's *"one expression, four readers"*.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** asserting that the forced till IS
    in the list. It is, under any spelling that mentions `close_kind`. The
    assertion that bites is that the DECLARED one is NOT, because that is the
    only clause `declared_at` contributes — and an expression that forgot it
    would leave Dana's Tuesday count on the supervisor's *Not counted* list for
    ever, which is the screen telling her she has work she has already done.
    """
    counted, forced, declared, system = _four_states(brazos, dana, marcus, centre)
    with tenant_ctx(brazos):
        not_counted = set(
            CounterSession.objects.filter(tenant=brazos)
            .filter(counters.not_counted_q())
            .values_list("pk", flat=True)
        )
    assert forced.pk in not_counted
    assert declared.pk not in not_counted
    assert counted.pk not in not_counted
    assert system.pk not in not_counted
    assert len(not_counted) == 1


def test_p2_14_a_close_with_and_without_a_difference_are_both_readable_after(
    brazos, dana, marcus, centre
):
    """*"Close with and without a difference"*, both served back from the row.

    The balanced drawer records `0.0000` and no note; the short one records the
    figure AND the reason. **`difference` on a forced close is NULL and not
    zero**, because nobody counted — an absence and a zero are different facts
    and a screen that rendered them alike would report every unclosed till as
    balanced.

    (The tenant context is re-entered per step for the reason `_four_states`
    sets out: an endpoint call clears it on the way out.)
    """
    with tenant_ctx(brazos):
        balanced = _open(marcus, centre)
    flat = _post(
        counters_api.counter_close,
        marcus,
        brazos,
        balanced.session,
        {"counted_totals": {"cash": "200.00"}, "closed_at": timezone.now().isoformat()},
    )
    with tenant_ctx(brazos):
        short = _open(marcus, centre)
    off = _post(
        counters_api.counter_close,
        marcus,
        brazos,
        short.session,
        {
            "counted_totals": {"cash": "188.00"},
            "closed_at": timezone.now().isoformat(),
            "note": "cheque stuck to the bag",
        },
    )
    with tenant_ctx(brazos):
        never = _open(marcus, centre)
    blind = _post(
        counters_api.counter_force_close,
        dana,
        brazos,
        never.session,
        {"note": "went home", "closed_at": timezone.now().isoformat()},
    )
    assert flat.status_code == 200, flat.data
    assert off.status_code == 200, off.data
    assert blind.status_code == 200, blind.data
    assert Decimal(flat.data["difference"]) == Decimal("0.0000")
    assert Decimal(off.data["difference"]) == Decimal("-12.0000")
    assert blind.data["difference"] is None, "nobody counted — that is an absence, not a zero"
    assert flat.data["posted"] is False
    assert blind.data["posted"] is False
    # And the short one DID reach the books — §3.3, and the body says so, which
    # is the field p059's drawing promised would always be "nothing happened".
    assert off.data["posted"] is True


# ═══════════════════════════════════════════════════════════════════════════
#  `P2.15` — the ledger pair, and the absence of one
#
#  ⚠ **THE BLUEPRINT IS WRONG HERE AND THE RULING IS WHY.** p018 commits this
#  task as *"Balanced at take; closing writes no journal line. Counting is not
#  a posting."* PO ruling 2026-09-23 §3.3 supersedes the second half:
#  *"(b) Post it."* So a non-zero difference DOES post, and the only sentence
#  of the drawing that survives is the FIRST one — which is asserted below,
#  because a superseded task still has a half that is true.
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_15_taking_money_writes_a_balanced_pair(brazos, dana, centre):
    """*"Balanced at take"* — the half of the drawing the ruling did NOT move.

    A cash payment into an open till posts its own entry the moment it is
    taken, and debits equal credits. This is asserted here rather than left to
    the payments suite because `P2.15`'s task line is a statement about BOTH
    events, and a file that proved only the drawer difference would leave the
    sentence half-checked.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        payment = _take(dana, brazos, amount="310.0000", method_code="cash", till=opened.session)
        lines = _lines(brazos, source_type=ledger_seam.SOURCE_PAYMENT, source_id=payment.pk)
    assert len(lines) >= 2, "taking money wrote no journal line"
    debits = sum(line.amount for line in lines if line.side == "debit")
    credits = sum(line.amount for line in lines if line.side == "credit")
    assert debits == credits == Decimal("310.000000")


def test_p2_15_an_OVER_drawer_posts_the_MIRROR_pair(brazos, dana, marcus, centre):
    """⚠ **NOTHING IN THIS REPOSITORY TESTED AN OVER UNTIL THIS CASE.**

    §3.3: *"$12.0000 over → the mirror. One account, both directions."* —
    DR `1010 Undeposited funds` · CR `6850 Cash over and short`.

    ⚠ **THIS IS THE FALSE PASS THE SHORT CASE CARRIES, NAMED.** A posting that
    put `6850` on the DEBIT side whatever the sign would satisfy
    `test_p2_22_a_short_drawer_posts_a_balanced_pair` exactly, for ever: it
    only ever counts a short. The direction is a column (`side`) and the
    amount is unsigned, so **the sign is expressed in precisely one place** and
    precisely one case can catch it being read backwards. This is it.

    ⚠ **AND THE AMOUNT MUST STILL BE POSITIVE.** B2 puts `CHECK (amount >= 0)`
    on a journal line, so a seam that passed `difference` through unsigned-but-
    negative would be refused by the database — but on a drawer that is OVER
    the raw difference is already positive, and an `abs()` that was never
    applied would pass this case silently. The short case is what covers that
    direction, and the two together cover both.
    """
    with tenant_ctx(brazos):
        # ⚠ **RESOLVED INSIDE THE TENANT CONTEXT, AND THE FIRST DRAFT OF THIS
        # FILE RESOLVED IT OUTSIDE.** `gl_account_id_for_designation` reads the
        # tenant's own chart, so with no tenant set it answered nothing, this
        # case took the *`P2.21` has not landed* branch, and the branch then
        # failed with `DID NOT RAISE` — over a product that had posted the pair
        # perfectly. A fixture looking at the wrong thing is hard-won law 7's
        # fourth shape, and it cost a red before it cost anything else.
        account_id = _over_short_account()
        opened = _open(marcus, centre)
        if account_id is None:
            # `P2.21` has not seeded `6850` on this chart. The product REFUSES
            # rather than posting into a bucket nobody mapped, and that is the
            # behaviour asserted — never a skip (law 7).
            from apps.payments.exceptions import PaymentRuleError

            with pytest.raises(PaymentRuleError) as refusal:
                counters.close_counter(
                    marcus,
                    session_id=opened.session.pk,
                    counted_totals={"cash": "212.00"},
                    closed_at=timezone.now(),
                    note="found a twenty under the tray",
                )
            assert ledger_seam.GL_CASH_OVER_SHORT in str(refusal.value)
            return
        sealed = counters.close_counter(
            marcus,
            session_id=opened.session.pk,
            counted_totals={"cash": "212.00"},  # $12.00 MORE than the $200.00 float
            closed_at=timezone.now(),
            note="found a twenty under the tray",
        )
        lines = _lines(
            brazos,
            source_type=ledger_seam.SOURCE_COUNTER_SESSION,
            source_id=opened.session.pk,
        )
    assert sealed.difference == Decimal("12.0000"), "counted minus expected — positive is OVER"
    assert sealed.posting_key is not None
    assert len(lines) == 2
    debit = next(line for line in lines if line.side == "debit")
    credit = next(line for line in lines if line.side == "credit")
    # ⚠ **COMPARED AS STRINGS.** `JournalLine.ledger_account_id` is a
    # `uuid.UUID` and `gl_account_id_for_designation` returns a `str`, so
    # `UUID(...) == "01a0…"` is `False` for every value there has ever been —
    # `DEF-PAY-6248`, where exactly that comparison was incapable of passing on
    # one line and incapable of failing on the line below it.
    assert str(credit.ledger_account_id) == str(account_id), "6850 takes the CREDIT on an over"
    assert str(debit.ledger_account_id) != str(account_id)
    assert debit.amount == credit.amount == Decimal("12.000000")
    # And the debit is 1010, the same account the take already debited — §3.3's
    # load-bearing half, asserted by NAME rather than by elimination. (Inside
    # the tenant context again: a chart read with no tenant set refuses.)
    with tenant_ctx(brazos):
        from apps.ledger import selectors as ledger_selectors

        undeposited = ledger_selectors.gl_account_id_for_designation("undeposited_funds")
    assert str(debit.ledger_account_id) == str(undeposited)


def test_p2_15_a_forced_close_posts_at_DECLARE_and_not_before(brazos, dana, marcus, centre):
    """*"It posts when the money is COUNTED"* — §3.3, and on a forced close that
    moment is the DECLARE.

    ⚠ **THE ABSENCE IS HALF THE TASK AND IT IS ASSERTED FIRST.** A forced close
    counts nothing, so it must write no line at all; only the late count does.
    A posting that fired at force-close would be a `$12.00` entry dated the
    night a supervisor swept the office, against a figure nobody had yet
    produced. The two assertions are in one case on purpose: separately, either
    one is satisfiable by a posting that never happens.
    """
    with tenant_ctx(brazos):
        account_id = _over_short_account()  # inside the context — see the OVER case
        opened = _open(marcus, centre)
        sealed = counters.force_close_counter(
            dana,
            session_id=opened.session.pk,
            reason="went home without closing",
            closed_at=timezone.now(),
        )
        after_force = _lines(
            brazos,
            source_type=ledger_seam.SOURCE_COUNTER_SESSION,
            source_id=opened.session.pk,
        )
        assert sealed.posting_key is None
        assert after_force == [], "a forced close counted nothing and must post nothing"

        if not counters._declaration_columns_exist():
            pytest.fail("`P2.20` has landed on this branch; this branch cannot be reached")
        if account_id is None:
            from apps.payments.exceptions import PaymentRuleError

            with pytest.raises(PaymentRuleError):
                counters.declare_counter(
                    marcus,
                    session_id=opened.session.pk,
                    counted_totals={"cash": "188.00"},
                    declared_at=timezone.now(),
                    note="cheque stuck to the bag",
                )
            return
        declared = counters.declare_counter(
            marcus,
            session_id=opened.session.pk,
            counted_totals={"cash": "188.00"},
            declared_at=timezone.now(),
            note="cheque stuck to the bag",
        )
        after_declare = _lines(
            brazos,
            source_type=ledger_seam.SOURCE_COUNTER_SESSION,
            source_id=opened.session.pk,
        )
    assert declared.difference == Decimal("-12.0000")
    assert declared.posting_key is not None
    assert len(after_declare) == 2
    debit = next(line for line in after_declare if line.side == "debit")
    assert str(debit.ledger_account_id) == str(account_id), "6850 takes the DEBIT on a short"


def test_p2_15_a_zero_difference_posts_NOTHING_on_either_path(brazos, dana, marcus, centre):
    """*"A zero difference posts nothing."* At close, and at declare.

    The declare half is the one nothing covered: §3.3's sentence is about the
    moment the money is counted, and a drawer that was force-closed and then
    counted EXACTLY right is a real Tuesday morning. A journal line for money
    that did not move is a line somebody has to explain.
    """
    with tenant_ctx(brazos):
        counted = _open(marcus, centre)
        flat = counters.close_counter(
            marcus,
            session_id=counted.session.pk,
            counted_totals={"cash": "200.00"},
            closed_at=timezone.now(),
        )
        forced = _open(marcus, centre)
        counters.force_close_counter(
            dana, session_id=forced.session.pk, reason="went home", closed_at=timezone.now()
        )
        late = counters.declare_counter(
            marcus,
            session_id=forced.session.pk,
            counted_totals={"cash": "200.00"},
            declared_at=timezone.now(),
            note="counted Tuesday, it was right",
        )
        written = _lines(
            brazos, source_type=ledger_seam.SOURCE_COUNTER_SESSION, source_id=counted.session.pk
        ) + _lines(
            brazos, source_type=ledger_seam.SOURCE_COUNTER_SESSION, source_id=forced.session.pk
        )
    assert flat.difference == Decimal("0.0000")
    assert late.difference == Decimal("0.0000")
    assert flat.posting_key is None
    assert late.posting_key is None
    assert written == []


def test_p2_15_payments_never_writes_a_journal_line_itself(brazos):
    """**Hard rule 5**, checked in the module rather than assumed in a docstring.

    *"Only the ledger posting service writes journal lines."* Every drawer
    posting in this phase goes `counters._post_difference` →
    `payments.ledger_seam` → the ledger's own `posting` module. This asserts
    the absence of the shortcut, because **an absence is invisible to every
    other check this repository has** (`DEF-CUS-3653`'s lesson, and the reason
    `test_p2_2_counter_sessions_is_not_frozen_by_hard_rule_4` reads its
    migration source the same way).

    ⚠ **IT READS SOURCE AND SAYS SO.** A grep is a weak check and this one is
    deliberately narrow: it looks for a payments module CREATING a journal row,
    which is the one spelling that would breach the rule without any import of
    `apps.ledger.models` being obvious in review.
    """
    forbidden = ("JournalLine.objects.create", "JournalEntry.objects.create")
    offenders = []
    for path in sorted((BACKEND / "apps" / "payments").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for spelling in forbidden:
            if spelling in source:
                offenders.append(f"{path.name}: {spelling}")
    assert offenders == [], (
        "payments is writing the books directly — hard rule 5 puts that in the ledger "
        "posting service and nowhere else"
    )
    # And the seam a drawer difference actually travels is the one that is there.
    assert hasattr(ledger_seam, "post_counter_difference")
    assert ledger_seam.SOURCE_COUNTER_SESSION == "counter_session"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-136-BRC07 §3.2 · §3.3 · §4 rows `P2.12`, `P2.14`, `P2.15` · blueprint p018 (the task table) read as text and superseded where §3 says so
# generated: 2026-09-23 by LANE P2-TESTS
# checklist: A✔ B=n/a(no new endpoint) C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: JOBS_EAGER=false pytest tests/test_cr136_p2_12_14_15_the_counter_contract.py --reuse-db · 10-scripts/cr136_p2_counters_postgres_proof.py on PostgreSQL 16
# exceptions: E3 the race, the aborted transaction and RLS are NOT here and cannot be — SQLite (hard-won law 14); the PostgreSQL proof is asserted to exist by `test_p2_12_the_race_is_proved_where_it_can_be_and_this_file_says_where`
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
