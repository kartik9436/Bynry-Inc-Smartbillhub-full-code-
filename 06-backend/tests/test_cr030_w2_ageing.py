# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-001 / US-CUS-002 (the S17 register and its segments)
#           Screens: S17 (the `AGEING` column CR-030 §5.1.2 splits off `STATUS`)
# Change:   CR-030 W2 — task 2.3 (backend half) + task 2.4
#           (`GET /accounts?ageing=<segment>`)
# Rules:    BR-CUS-016 (ageing is DERIVED from the receivable position and NEVER
#           stored) · BR-CUS-048 (the four aged bands, and forward aging by
#           CALENDAR DAYS from the cutover as-of date) · BR-CUS-061 (opening
#           CREDIT balances are a carried account credit — buckets stay
#           DEBIT-ONLY) · BR-SHL-011 (a list URL never 4xx's over its params) ·
#           BR-TEN-043 (as-of is an argument, never a clock) ·
#           CLAUDE.md rule 1 (tenant scoping, RLS FORCE)
# Golden:   GT-16 — the ❄️ frozen opening position 84.20 / 62.10 / 0.00 / 121.00
# ───────────────────────────────────────────────────────
"""CR-030 W2 — the AGEING column, and the segment filter behind it.

**The defect this column exists to fix is on the PO's own screenshot.** S17
today draws ONE `Status` cell that "mixes two things" (CR-030 §5.1.2) — it puts
`Pending` where an ageing state belongs — so a clerk cannot see that a *Pending
activation* account is also *30d past*. The prototype draws two columns, and
TC-ACC-2 is exactly that row: `STATUS` = `Pending activation` **and** `AGEING` =
past due, "two cells, never one".

Every band edge below is asserted through the ONE table that declares them
(`selectors.AGEING_BAND_EDGES`) and every band NAME through the model's own
constants, so this file cannot pass while a second copy of the vocabulary
exists somewhere else.
"""

from datetime import timedelta
from decimal import Decimal

import pytest

from apps.customers import import_writer, models as customers_models, seams, selectors
from apps.customers import api as customers_api

from tests.isolation_helpers import (  # noqa: F401
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)
from tests.test_cr030_w0_customer_no import _account_for  # noqa: F401,E402
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

BUCKETS = customers_models.AccountOpeningBucket
CURRENT = BUCKETS.BUCKET_CURRENT
D31_60 = BUCKETS.BUCKET_31_60
D61_90 = BUCKETS.BUCKET_61_90
D90_PLUS = BUCKETS.BUCKET_90_PLUS

#: GT-16, verbatim (the same four figures `test_cr030_w1_opening_buckets` uses).
GT16 = {"ob_current": "84.20", "ob_31_60": "62.10", "ob_61_90": "0.00", "ob_90_plus": "121.00"}


class FakeUser:
    """A signed-in staff user, as `api_call` attaches one."""

    is_authenticated = True
    id = None
    pk = None
    role = "system_admin"


def _write_position(account, mapped, *, days_ago: int):
    """Give an account an opening position whose cutover was `days_ago` days
    back — the only way to make a bucket AGE, since nothing stores the answer."""
    import_writer.write_opening_buckets(
        account_id=account["id"],
        account_ref=account.get("account_no"),
        mapped=mapped,
        as_of=seams.tenant_today() - timedelta(days=days_ago),
        currency="USD",
    )


def _segment(account) -> str | None:
    return selectors.ageing_segments_for([account["id"]]).get(str(account["id"]), (None, None))[0]


def _list(tenant, **query):
    response = api_call(
        customers_api.accounts,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        query=query,
    )
    assert response.status_code == 200, f"GET /accounts answered {response.status_code}"
    return response.data


# ═══════════════════════════════════════════════════════════════════════════
# The vocabulary — one declaration, no second copy
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_tc1__the_segments_are_the_models_four_bands_and_nothing_else():
    """BR-CUS-048's vocabulary lives on `AccountOpeningBucket`. If the read path
    kept its own list, the two would agree today and disagree the first time a
    band is added — which is the whole reason the constants exist."""
    assert selectors.AGEING_SEGMENTS is BUCKETS.BUCKETS
    assert tuple(bucket for bucket, _edge in selectors.AGEING_BAND_EDGES) == BUCKETS.BUCKETS
    assert set(selectors.AGEING_BAND_FLOORS) == set(BUCKETS.BUCKETS)


def test_w2_tc2__the_three_overdue_bands_are_the_models_own_overdue_set():
    """`current` is not overdue and the other three are — `OVERDUE_BUCKETS` says
    so once, and a segment outside `current` must be exactly that set."""
    assert tuple(b for b in selectors.AGEING_SEGMENTS if b != CURRENT) == BUCKETS.OVERDUE_BUCKETS


# ═══════════════════════════════════════════════════════════════════════════
# The band edges — each boundary, from both sides
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    ("days", "band"),
    [
        (0, CURRENT),
        (30, CURRENT),  # ← the boundary the CR names: 30 is Current …
        (31, D31_60),  # ← … and 31 is not. Opposite sides, one day apart.
        (60, D31_60),
        (61, D61_90),
        (90, D61_90),  # `61–90` is read literally: it CONTAINS 90 …
        (91, D90_PLUS),  # … and `90+` means MORE than 90.
        (400, D90_PLUS),
    ],
)
def test_w2_tc3__every_band_boundary_from_both_sides(days, band):
    assert selectors.ageing_band_for_days(days) == band


def test_w2_tc4__an_age_that_is_not_past_due_is_current_never_the_worst_band():
    """A negative age is a due date in the future, not a 90+ debt. The same
    disposition `apps/payments/outstandings.bucket_for` takes on `None`."""
    assert selectors.ageing_band_for_days(-5) == CURRENT


# ═══════════════════════════════════════════════════════════════════════════
# BR-CUS-048 forward aging — the money gets older, nothing is re-stored
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_tc5__on_cutover_day_the_derived_band_is_the_imported_band(brazos, marcus):
    """Elapsed = 0 ⇒ each band reports itself. If this failed, the import and
    the screen would disagree on day one about what a utility brought across."""
    with tenant_ctx(brazos):
        for index, (column, band) in enumerate(
            (
                ("ob_current", CURRENT),
                ("ob_31_60", D31_60),
                ("ob_61_90", D61_90),
                ("ob_90_plus", D90_PLUS),
            )
        ):
            account = _account_for(marcus, brazos, label=f"W2 cutover {index}")
            _write_position(account, {column: "100.00"}, days_ago=0)
            assert _segment(account) == band


def test_w2_tc6__a_current_bucket_becomes_31_60_on_the_thirty_first_day(brazos, marcus):
    """The boundary again, but through real rows and calendar days rather than
    through the band function — 30 days after cutover the money is still
    Current, and one day later it is not."""
    with tenant_ctx(brazos):
        thirty = _account_for(marcus, brazos, label="W2 30d")
        _write_position(thirty, {"ob_current": "100.00"}, days_ago=30)
        thirty_one = _account_for(marcus, brazos, label="W2 31d")
        _write_position(thirty_one, {"ob_current": "100.00"}, days_ago=31)
        assert _segment(thirty) == CURRENT
        assert _segment(thirty_one) == D31_60


def test_w2_tc7__an_imported_31_60_bucket_ages_forward_into_61_90(brazos, marcus):
    """BR-CUS-048 verbatim: *"an amount imported 45 days past due is 75 days past
    due 30 days later"*. A BUCKET is a band, not the point `45`, and this lane
    ages it from the band's FLOOR (31) — the least age the data supports — so it
    reaches `61–90` on the thirtieth day and never earlier. **That floor reading
    is this lane's judgment inside a PROPOSED clause and is REPORTED, not
    ratified**; this test is what goes red if anyone changes it silently."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 fwd")
        _write_position(account, {"ob_31_60": "62.10"}, days_ago=30)
        segment, days = selectors.ageing_segments_for([account["id"]])[str(account["id"])]
        assert (segment, days) == (D61_90, 61)


def test_w2_tc8__nothing_is_stored_the_answer_moves_with_the_as_of(brazos, marcus):
    """BR-CUS-016: *"never stored"*. Asked for two different days WITHOUT a
    single write between them, the same rows answer two different bands — which
    is only possible because no column holds this."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 asof")
        _write_position(account, {"ob_current": "100.00"}, days_ago=0)
        today = seams.tenant_today()
        key = str(account["id"])
        assert selectors.ageing_segments_for([account["id"]], as_of=today)[key][0] == CURRENT
        later = today + timedelta(days=95)
        assert selectors.ageing_segments_for([account["id"]], as_of=later)[key][0] == D90_PLUS
        # and the row count is unchanged — the derivation wrote nothing.
        assert BUCKETS.objects.filter(account_id=account["id"]).count() == 4


def test_w2_tc9__a_cutover_dated_in_the_future_never_makes_money_younger(brazos, marcus):
    """A date typo must not un-age an imported 90+ into Current."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 future")
        _write_position(account, {"ob_90_plus": "121.00"}, days_ago=-40)
        assert _segment(account) == D90_PLUS


# ═══════════════════════════════════════════════════════════════════════════
# The account's whole position — the oldest band wins, zeros age nothing
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_tc10__gt16s_frozen_position_ages_to_90_plus(brazos, marcus):
    """84.20 / 62.10 / 0.00 / 121.00 on cutover day. The segment is `90+`
    because 121.00 of it is: `PAST DUE 60+ · 18` counts accounts with SOMETHING
    at 60+, not accounts whose whole balance is."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 gt16")
        _write_position(account, GT16, days_ago=0)
        assert _segment(account) == D90_PLUS


def test_w2_tc11__a_band_holding_zero_ages_nothing(brazos, marcus):
    """GT-16's `61–90` is 0.00. An empty band must not drag an account into it —
    a 0.00 row is a fact about a band, not a debt in it."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 zero")
        _write_position(account, {"ob_current": "84.20", "ob_61_90": "0.00"}, days_ago=0)
        assert _segment(account) == CURRENT


def test_w2_tc12__an_account_with_no_receivable_ages_to_nothing(brazos, marcus):
    """⚠ THE DEF-127 SHAPE, IN A DIFFERENT CELL — still never `Current`.

    ⚠ AMENDED 2026-10-17 (`DEF-CUS-10181`, PO ruling *"AGING … IS FIXED TO READ
    BILLS"*). This asserted a reason, `invoice_ageing_needs_due_dates`, because
    billing's due dates were then unread and a null meant "not worked out". The
    bill half is read now, so a null is an ANSWER — this account owes nothing
    that ages — and carries no reason. The reason survives only for a
    deployment where payments publishes no debtor read
    (`AGEING_BILL_HALF_UNAVAILABLE`)."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 none")
        cells = selectors.ageing_cells(account["id"])
        assert cells["ageing_segment"] is None
        assert cells["ageing_days_past_due"] is None
        assert cells["ageing_source"] is None
        assert cells["ageing_unavailable"] is None


def test_w2_tc13__an_all_blank_import_leaves_the_account_ageless(brazos, marcus):
    """US-CUS-021 TC-5 writes NO bucket rows for a blank position, so the cell
    is the `—` the prototype draws, not a zero-valued Current."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 blank")
        _write_position(account, {}, days_ago=10)
        assert _segment(account) is None


def test_w2_tc14__a_negative_bucket_refuses_by_name_and_never_ages(brazos, marcus):
    """⛔ BR-CUS-061 ruled that opening CREDIT balances import as a carried
    account credit and that *"aging buckets stay debit-only"* — so a negative
    bucket cannot lawfully exist (`import_writer` refuses to write one, citing
    BR-CUS-061) and this refuses to READ one into a band. What a credit balance
    AGES as was never ruled, and this lane does not decide it."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 credit")
        BUCKETS.objects.create(
            tenant_id=brazos.id,
            account_id=account["id"],
            as_of=seams.tenant_today(),
            bucket=CURRENT,
            amount=Decimal("-45.00"),
            currency="USD",
        )
        with pytest.raises(NotImplementedError) as caught:
            selectors.ageing_segments_for([account["id"]])
        # DEF-620: the guard names the RULE that closed OQ-065, not the
        # question. A closed id in a live message sends the next reader
        # to wait for a ruling that already happened.
        assert "BR-CUS-061" in str(caught.value)


# ═══════════════════════════════════════════════════════════════════════════
# GET /accounts?ageing=<segment> — task 2.4
# ═══════════════════════════════════════════════════════════════════════════
def _two_segmented_accounts(brazos, marcus):
    current = _account_for(marcus, brazos, label="W2 seg current")
    _write_position(current, {"ob_current": "10.00"}, days_ago=0)
    ninety = _account_for(marcus, brazos, label="W2 seg 90")
    _write_position(ninety, {"ob_90_plus": "121.00"}, days_ago=0)
    return current, ninety


def test_w2_tc15__every_row_carries_its_segment_so_the_column_can_render(brazos, marcus):
    """Task 2.3's backend half: the frontend cannot draw a column the payload
    does not carry (hard-won law 2 — built is not wired)."""
    with tenant_ctx(brazos):
        current, ninety = _two_segmented_accounts(brazos, marcus)
        body = _list(brazos)
        by_id = {row["id"]: row for row in body["results"]}
        assert by_id[str(current["id"])]["ageing_segment"] == CURRENT
        assert by_id[str(ninety["id"])]["ageing_segment"] == D90_PLUS
        assert by_id[str(ninety["id"])]["ageing_source"] == "opening_buckets"
        # …and the STORED status is still its own cell. Two cells, never one
        # (TC-ACC-2) — this is the split the CR asks for.
        assert by_id[str(ninety["id"])]["status"] == "pending_activation"


def test_w2_tc16__the_bare_ageing_param_narrows_the_list(brazos, marcus):
    """CR-030 §5.1.3 writes the endpoint as `GET /accounts?ageing=`."""
    with tenant_ctx(brazos):
        current, ninety = _two_segmented_accounts(brazos, marcus)
        ids = [row["id"] for row in _list(brazos, ageing=D90_PLUS)["results"]]
        assert str(ninety["id"]) in ids
        assert str(current["id"]) not in ids


def test_w2_tc17__the_platform_f_grammar_narrows_it_identically(brazos, marcus):
    """BR-SHL-011's `f.<name>` is how the segment travels with the rest of the
    list state, which is what makes a reload restore it (TC-ACC-5)."""
    with tenant_ctx(brazos):
        current, ninety = _two_segmented_accounts(brazos, marcus)
        ids = [row["id"] for row in _list(brazos, **{"f.ageing": D90_PLUS})["results"]]
        assert ids == [str(ninety["id"])]
        assert str(current["id"]) not in ids


def test_w2_tc18__the_screens_own_label_is_accepted_as_a_segment(brazos, marcus):
    """`90+` is what the chip says and what `apps/payments/outstandings` already
    takes on its own bucket param. One segment string, both endpoints."""
    with tenant_ctx(brazos):
        _current, ninety = _two_segmented_accounts(brazos, marcus)
        ids = [row["id"] for row in _list(brazos, ageing="90+")["results"]]
        assert ids == [str(ninety["id"])]


def test_w2_tc19__all_is_the_registers_default_segment_and_filters_nothing(brazos, marcus):
    """CR-030 §5.1: the Accounts tab is a REGISTER, "which is why its default
    segment is `All`, not `Open`"."""
    with tenant_ctx(brazos):
        current, ninety = _two_segmented_accounts(brazos, marcus)
        ids = {row["id"] for row in _list(brazos, ageing="all")["results"]}
        assert {str(current["id"]), str(ninety["id"])} <= ids


def test_w2_tc20__a_nonsense_segment_never_4xxs_the_list(brazos, marcus):
    """BR-SHL-011: invalid values fall back, NEVER error. A URL a user pasted
    wrong must not blank the product's busiest screen."""
    with tenant_ctx(brazos):
        current, ninety = _two_segmented_accounts(brazos, marcus)
        ids = {row["id"] for row in _list(brazos, ageing="d45_50")["results"]}
        assert {str(current["id"]), str(ninety["id"])} <= ids


def test_w2_tc21__an_account_with_no_position_is_not_in_any_segment(brazos, marcus):
    """Absence is not a band. It must not fall into `Current` just because that
    is the first one."""
    with tenant_ctx(brazos):
        ageless = _account_for(marcus, brazos, label="W2 ageless")
        ids = {row["id"] for row in _list(brazos, ageing=CURRENT)["results"]}
        assert str(ageless["id"]) not in ids


# ═══════════════════════════════════════════════════════════════════════════
# CLAUDE.md rule 1 — proved at the DATABASE, under a role RLS applies to
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
@requires_postgres
def test_w2_tc22__one_tenants_ageing_position_is_invisible_next_door(
    rls, brazos, lonestar, marcus
):  # noqa: F811
    """The segment is derived from `account_opening_buckets`, which holds what
    every migrated customer owed on cutover day. A plain ORM read under
    `tenant_ctx` runs as a SUPERUSER and would prove NOTHING (superusers bypass
    RLS unconditionally), so the assertion runs under the non-superuser probe
    role — `rls.assert_is_a_real_proof()` fails, never skips, if that role could
    bypass."""
    with live_tenant_context(brazos.id):
        account = _account_for(marcus, brazos, label="W2 iso")
        _write_position(account, GT16, days_ago=0)
        owned = {str(row.id) for row in BUCKETS.objects.filter(account_id=account["id"])}
        assert owned, "the fixture wrote no buckets, so this case would prove nothing"
    assert_rls_scoped(
        rls, "account_opening_buckets", owner=brazos, intruder=lonestar, owner_ids=owned
    )
    assert_no_foreign_rows_anywhere(rls, lonestar, ("account_opening_buckets",))


def test_w2_tc23__the_derivation_never_reads_another_tenants_position(brazos, lonestar, marcus):
    """The app-layer half of rule 1, on the selector itself: asked under Lone
    Star's context for a Brazos account id, it answers NOTHING rather than that
    account's ageing. A cross-tenant queryset here would leak a customer's
    delinquency to another utility."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 xtenant")
        _write_position(account, GT16, days_ago=0)
        assert _segment(account) == D90_PLUS
    with tenant_ctx(lonestar):
        assert selectors.ageing_segments_for([account["id"]]) == {}
        assert selectors.ageing_cells(account["id"])["ageing_segment"] is None
