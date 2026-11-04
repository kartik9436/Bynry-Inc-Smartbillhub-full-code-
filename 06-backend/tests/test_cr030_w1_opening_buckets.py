# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-021 (opening balances as AGED BUCKETS) · US-CUS-022 (the
#           balanced AR↔clearing handoff)   Screens: S68, S81
# Change:   CR-030 W1 — accounts become the sixth ETL target
# Rules:    BR-CUS-048 (four aged buckets; lump-sum REJECTED) · BR-CUS-049
#           (balanced opening JEs at cutover) · CLAUDE.md rule 1 · rule 2
# Golden:   GT-16 — B5 ❄️ FROZEN, finance-signed 2026-08-08
# ───────────────────────────────────────────────────────
"""CR-030 W1 — the opening position, and the four buckets it is made of.

**The PO asked for this on 2026-08-24** (*"you will need trial balance field -
opening balance for that account"*) and the answer was that BR-CUS-048 has been
CONFIRMED since 2026-08-08, GT-16 has been ❄️ frozen since the same day, and
`apps/ledger/opening_balances.py` has had a writer with **no caller** since
2026-08-16 — its own docstring saying *"a utility migrating in from another
system still cannot bring its receivables across"*.

Every figure below is GT-16's, not this lane's.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.customers import import_writer, models as customers_models
from core import errors

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

pytestmark = pytest.mark.django_db

#: GT-16, verbatim. Typed once, here, and read everywhere below — a second
#: literal would be a second source of truth for a FROZEN figure.
GT16 = {"ob_current": "84.20", "ob_31_60": "62.10", "ob_61_90": "0.00", "ob_90_plus": "121.00"}
GT16_TOTAL = Decimal("267.30")
GT16_OVERDUE = Decimal("183.10")
CUTOVER = date(2026, 8, 31)


def test_w1_tc1__the_frozen_worked_case_reproduces_exactly():
    """GT-16: 84.20 + 62.10 + 0.00 + 121.00 = **267.30**, and the day-one
    overdue portion is 62.10 + 0.00 + 121.00 = **183.10** (the GT-8 late-fee
    base). *"Σ buckets, exact — no recompute."*"""
    position = import_writer.opening_position(GT16, account_ref="A-12103")
    assert position["total"] == GT16_TOTAL
    assert position["overdue"] == GT16_OVERDUE
    assert position["empty"] is False
    assert [bucket for bucket, _amount in position["buckets"]] == list(
        customers_models.AccountOpeningBucket.BUCKETS
    )


def test_w1_tc2__nothing_in_this_path_is_a_float():
    """A float would make 84.20 + 62.10 + 121.00 read 267.29999999999995 and the
    batch would fail its own tie-out. That is the GOOD outcome; the bad one is a
    rounding step that 'fixes' it and hides a real imbalance."""
    position = import_writer.opening_position(GT16, account_ref="A-12103")
    assert isinstance(position["total"], Decimal)
    for _bucket, amount in position["buckets"]:
        assert isinstance(amount, Decimal)
    assert str(position["total"]) == "267.30"  # exact, not 267.3 and not 267.2999…


def test_w1_tc3__all_four_blank_is_a_position_of_nothing_not_a_zero_position():
    """US-CUS-021 TC-5 — balance 0.00, **no bucket rows and no opening JE**. A
    zero JE is a journal entry that says nothing and can never be corrected away
    (hard rule 4)."""
    position = import_writer.opening_position({}, account_ref="A-12140")
    assert position["total"] == Decimal("0")
    assert position["empty"] is True


def test_w1_tc4__a_negative_bucket_CARRIES_A_CREDIT_and_never_refuses():
    """⛔ **THIS TEST ASSERTED THE OPPOSITE UNTIL 2026-08-24, AND THAT WAS
    DEF-620 — a money-path defect against a rule signed sixteen days before the
    code was written.**

    It used to read `test_w1_tc4__a_negative_bucket_refuses_and_names_OQ_065`
    and assert `caught.value.params["oq"] == "OQ-065"`, on the belief that an
    opening CREDIT balance had no ruled handling. **OQ-065 closed on 2026-08-08**
    → **BR-CUS-061, CONFIRMED**:

        Opening CREDIT balances at cutover import as a carried ACCOUNT CREDIT
        (BR-PAY-010 overpayment pattern) — aging buckets stay debit-only; the
        credit auto-applies to the account's first bills; refundable on request.

    So the old test was pinning option (c) — exclude and settle in the legacy
    system — which is the option the PO did NOT choose. A utility migrating
    customers who were in credit had those rows rejected.

    The history is left in this docstring rather than erased, because the
    escape is the useful part: nothing joins an `OQ-###` cited in code to that
    question's live status, so a grep finds the code and the registry and
    cannot tell you they disagree.

    US-CUS-021 TC-4's fixture is still CivicCIS customer CUST-204 at −45.00.
    What it now proves is the ruled behaviour: the money is CARRIED, the band
    stays debit-only, and nothing is silently kept.
    """
    position = import_writer.opening_position(
        {"ob_current": "-45.00"}, account_ref="CUST-204"
    )
    # ⚠ `buckets` is a LIST of (bucket, amount) pairs in ageing order, not a
    # dict — the order is the fact, so a caller cannot render the bands out of
    # sequence by iterating it.
    bands = dict(position["buckets"])
    # BR-CUS-061's debit-only half: the band takes NOTHING, not −45.00.
    assert bands[customers_models.AccountOpeningBucket.BUCKET_CURRENT] == Decimal("0.00")
    assert position["total"] == Decimal("0.00")
    # …and the money is not lost: it is carried as a credit on the account.
    assert position["credit"] == Decimal("45.00")
    assert position["has_credit"] is True


def test_w1_tc5__a_non_numeric_bucket_is_a_DIFFERENT_refusal():
    """US-CUS-021 TC-4's other half. A clerk fixes 'abc' by retyping it and
    fixes −45.00 by asking us what we do about credits, so the two refusals must
    not collapse into one message."""
    with pytest.raises(errors.ValidationError) as caught:
        import_writer.opening_position({"ob_current": "abc"}, account_ref="A-1")
    assert "oq" not in caught.value.params
    assert caught.value.params["value"] == "abc"


def test_w1_tc6__thousands_separators_survive_a_spreadsheet_export():
    """`1,213.45` is what Excel hands a utility, and refusing it would fail the
    migration on formatting rather than on money."""
    position = import_writer.opening_position({"ob_90_plus": "1,213.45"}, account_ref="A-2")
    assert position["total"] == Decimal("1213.45")


def test_w1_tc7__buckets_are_written_and_the_balance_is_their_exact_sum(brazos, marcus):
    """The write half, against real rows: four buckets, the cached balance, and
    the UNIQUE (account, bucket) constraint that stops a double-count."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W1 A")
        position = import_writer.write_opening_buckets(
            account_id=account["id"],
            account_ref=account.get("account_no"),
            mapped=GT16,
            as_of=CUTOVER,
            currency="USD",
        )
        assert position["total"] == GT16_TOTAL
        rows = customers_models.AccountOpeningBucket.objects.filter(account_id=account["id"])
        assert rows.count() == 4
        assert sum((row.amount for row in rows), Decimal("0")) == GT16_TOTAL
        assert {row.as_of for row in rows} == {CUTOVER}
        assert {row.currency for row in rows} == {"USD"}


def test_w1_tc8__an_empty_position_writes_no_rows_at_all(brazos, marcus):
    """The other side of TC-3, at the database."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W1 B")
        import_writer.write_opening_buckets(
            account_id=account["id"],
            account_ref=account.get("account_no"),
            mapped={},
            as_of=CUTOVER,
            currency="USD",
        )
        assert not customers_models.AccountOpeningBucket.objects.filter(
            account_id=account["id"]
        ).exists()


def test_w1_tc9__the_ledger_seam_resolves_to_the_real_writer():
    """⚠ hard-won law 2 and DEF-075 together. `opening_balances.py` has been
    complete since 2026-08-16 with NO caller; this asserts the caller now
    reaches it, because a seam that resolves to None would make the import
    report a migration whose books do not exist."""
    from apps.customers import seams

    assert seams.resolve("ledger", "post_opening_batch", kind="opening_balances") is not None


def test_w1_tc10__an_empty_batch_posts_nothing_and_says_so():
    """A run where every account had a blank position is not an error and is not
    a zero-value journal entry either."""
    result = import_writer.post_opening_batch_from_import(
        batch_id="b", cutover_on=CUTOVER, imported_at=None, currency="USD", accounts=[]
    )
    assert result == {"posted": 0, "ar_debits": "0", "clearing_credits": "0"}


@pytest.mark.isolation
@requires_postgres
def test_w1_tc11__a_tenants_whole_receivables_book_is_not_visible_next_door(
    rls, brazos, lonestar, marcus
):  # noqa: F811
    """CLAUDE.md rule 1, through the DATABASE under a role RLS applies to.

    This table is not scratch space: it holds what every migrated customer owed
    on cutover day — the GT-16 fixture is 1,213 rows summing to **$184,320.55**.
    A tenant's entire receivables position, in four numbers a row."""
    with live_tenant_context(brazos.id):
        account = _account_for(marcus, brazos, label="W1 C")
        import_writer.write_opening_buckets(
            account_id=account["id"],
            account_ref=account.get("account_no"),
            mapped=GT16,
            as_of=CUTOVER,
            currency="USD",
        )
        owned = {
            str(row.id)
            for row in customers_models.AccountOpeningBucket.objects.filter(
                account_id=account["id"]
            )
        }
    assert_rls_scoped(
        rls, "account_opening_buckets", owner=brazos, intruder=lonestar, owner_ids=owned
    )
    assert_no_foreign_rows_anywhere(rls, lonestar, ("account_opening_buckets",))
