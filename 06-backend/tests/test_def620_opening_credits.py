# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-021 (opening balances as AGED BUCKETS) · US-CUS-022 (the
#           balanced AR↔clearing handoff) · US-PAY-007 (the carried credit)
#           Screens: S68 (the import wizard) · S81 (the Imports tab) · S21
# Change:   DEF-620 — an opening CREDIT balance was REFUSED by an importer
#           citing OQ-065 as OPEN. OQ-065 closed on 2026-08-08 (BR-CUS-061).
# Rules:    BR-CUS-061 (CONFIRMED, PO OQ-065 option (b), 2026-08-08 — opening
#           CREDIT balances import as a carried ACCOUNT CREDIT, BR-PAY-010
#           pattern; aging buckets stay DEBIT-ONLY) · BR-CUS-077 (CONFIRMED,
#           PO 2026-08-24 — credit and aged debt are carried BOTH, SEPARATELY,
#           NEVER netted) · BR-CUS-048 (four aged buckets) · BR-CUS-049
#           (balanced opening JEs, AR ↔ clearing) · BR-PAY-010 (overpayment →
#           account credit, auto-applies to the next bill) · CLAUDE.md rule 1
#           (tenant scoping) · rule 2 (money 4 dp, never float) · rule 4
#           (immutability) · rule 5 (only the posting service writes journal
#           lines) · rule 7 (audit)
# Golden:   GT-16 — B5 ❄️ FROZEN, finance-signed 2026-08-08. Its worked position
#           is ALL-DEBIT (84.20 / 62.10 / 0.00 / 121.00 = 267.30, batch
#           $184,320.55) and NOTHING here may move it.
# ───────────────────────────────────────────────────────
"""DEF-620 — the credit customer a migration used to throw away.

**The defect, in one sentence.** `apps/customers/import_writer._amount` refused
any negative opening-bucket cell with `params["oq"] = "OQ-065"` under a docstring
banner reading *"It is OPEN."* — and OQ-065 has read **CLOSED(→BR-CUS-061)** in
`12-governance/01-open-questions.md` since **2026-08-08**, sixteen days before
that code was written. A utility migrating a base in which some accounts are in
credit had those rows REJECTED and had to settle them by hand in the system it
was leaving, which is option **(c)**, the option the PO did not choose.

**The two halves of BR-CUS-061, and the code implemented one:**

  1. ✅ *"aging buckets stay debit-only"* — no negative row is ever written to
        `account_opening_buckets`. That half was right and it stays right.
  2. ❌ *"import as a carried **account credit** (BR-PAY-010 overpayment
        pattern) … the credit auto-applies to the account's first bills;
        refundable on request"* — **the row LOADS.** That half was inverted
        into a refusal.

**BR-CUS-077 (PO 2026-08-24) settles the row that carries BOTH** — $45.00 of
credit in the current period and $121.00 owed from over ninety days ago. The
account shows **$121.00 in the over-90 band** and separately holds a **$45.00
credit**. **Netting to $76.00 was REJECTED** because netting loses the AGE of
the debt, and everything that keys off ageing — collections, disconnection
notices, the `PAST DUE 60+` tile, BR-CUS-016's derived display — would then
understate a real delinquent account.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.customers import import_writer, models as customers_models
from apps.metering import import_runs
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
from tests.test_cr030_w1_accounts_import import (  # noqa: F401,E402
    ALL_OFF,
    MAPPING,
    _run,
    _two_units,
)

#: GT-16's row with its Current band turned into a CREDIT (84.20 → −45.00), and
#: a second row with no opening position at all. ⚠ **The account numbers are
#: DEF-620's own, not GT-16's `A-12103`** — that number belongs to the demo seed
#: (`customers.sample_data.GT16_ACCOUNT_NO`), so a fixture that reused it would
#: collide on `ux_accounts_no` wherever sample data is provisioned and would be
#: testing the seed rather than the import.
CREDIT_CSV = (
    "UNIT_REF,ACCT,NAME,CUST_ID,TYPE,OPENED,CURRENT,31-60,61-90,90+,DEPOSIT,DEPOSIT_DATE\n"
    '{u1},A-620001,"Harmon, Luis",CUST-620001,residential,2024-02-12,-45.00,62.10,0.00,121.00,,\n'
    '{u2},A-620002,"Alvarez, Rosa",CUST-620002,residential,2025-06-01,,,,,,\n'
)

pytestmark = pytest.mark.django_db

#: ❄️ GT-16, verbatim, typed once. A second literal would be a second source of
#: truth for a FROZEN figure.
GT16 = {"ob_current": "84.20", "ob_31_60": "62.10", "ob_61_90": "0.00", "ob_90_plus": "121.00"}
GT16_TOTAL = Decimal("267.30")
GT16_OVERDUE = Decimal("183.10")

#: BR-CUS-077's worked row, verbatim: *"$45.00 credit in the current period and
#: $121.00 owed from over 90 days ago"*.
MIXED = {"ob_current": "-45.00", "ob_90_plus": "121.00"}
MIXED_DEBIT = Decimal("121.00")
MIXED_CREDIT = Decimal("45.00")
#: The answer the PO REJECTED. Named so the assertion below reads as the ruling.
NETTED_AND_REJECTED = Decimal("76.00")

CUTOVER = date(2026, 8, 31)


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE ROW LOADS — BR-CUS-061's second half
# ═══════════════════════════════════════════════════════════════════════════


def test_def620_tc1__a_pure_credit_row_no_longer_refuses():
    """⛔ **THE DEFECT.** US-CUS-021 TC-4's fixture is CivicCIS customer
    CUST-204 at **−45.00**, and the shipped code raised `VAL_RANGE` on it.

    BR-CUS-061 ruled it LOADS. It carries **45.00** of credit and writes no
    bucket row for it."""
    position = import_writer.opening_position({"ob_current": "-45.00"}, account_ref="CUST-204")
    assert position["credit"] == MIXED_CREDIT
    assert position["has_credit"] is True
    assert position["total"] == Decimal("0")
    # BR-CUS-061 — buckets stay DEBIT-ONLY, so a credit-only row has no bucket
    # position at all and therefore no opening JE (US-CUS-021 TC-5's shape).
    assert position["empty"] is True
    assert all(amount >= Decimal("0") for _bucket, amount in position["buckets"])


def test_def620_tc2__br_cus_077__both_carried_separately_and_never_netted(brazos, marcus):
    """**BR-CUS-077, PO 2026-08-24, on its own worked figure.**

    *"the account shows $121.00 in the over-90 ageing band and separately holds
    a $45.00 credit that applies to the next bill"* — and **$76.00 is the answer
    the PO rejected**, because netting loses the AGE of the debt."""
    position = import_writer.opening_position(MIXED, account_ref="A-12103")
    assert position["total"] == MIXED_DEBIT
    assert position["total"] != NETTED_AND_REJECTED
    assert position["credit"] == MIXED_CREDIT
    by_bucket = dict(position["buckets"])
    assert by_bucket[customers_models.AccountOpeningBucket.BUCKET_90_PLUS] == MIXED_DEBIT
    # The credit did NOT land in the band it was typed in. BR-CUS-061.
    assert by_bucket[customers_models.AccountOpeningBucket.BUCKET_CURRENT] == Decimal("0")
    # ...and the ageing still says 121.00 is over ninety days old, which is the
    # entire reason netting was rejected.
    assert position["overdue"] == MIXED_DEBIT


def test_def620_tc3__the_frozen_gt16_case_is_untouched():
    """❄️ **GT-16, finance-signed 2026-08-08.** 84.20 + 62.10 + 0.00 + 121.00 =
    **267.30**, day-one overdue **183.10**. An all-debit row carries NO credit,
    so nothing on this path can move a frozen figure."""
    position = import_writer.opening_position(GT16, account_ref="A-12103")
    assert position["total"] == GT16_TOTAL
    assert position["overdue"] == GT16_OVERDUE
    assert position["credit"] == Decimal("0")
    assert position["has_credit"] is False
    assert position["empty"] is False
    assert [bucket for bucket, _amount in position["buckets"]] == list(
        customers_models.AccountOpeningBucket.BUCKETS
    )


def test_def620_tc4__a_non_numeric_bucket_is_still_a_refusal():
    """The two refusals were always DIFFERENT and only one of them was wrong. A
    clerk fixes `abc` by retyping it; nobody fixes −45.00, because it is not
    wrong."""
    with pytest.raises(errors.ValidationError) as caught:
        import_writer.opening_position({"ob_current": "abc"}, account_ref="A-1")
    assert caught.value.params["value"] == "abc"
    assert "oq" not in caught.value.params


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE DATABASE — buckets stay debit-only (BR-CUS-061 half one)
# ═══════════════════════════════════════════════════════════════════════════


def test_def620_tc5__the_mixed_row_writes_debit_buckets_only(brazos, marcus):
    """BR-CUS-077 at the database. Four bucket rows, **not one of them
    negative**, summing to the 121.00 the account really owes."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="DEF620 A")
        position = import_writer.write_opening_buckets(
            account_id=account["id"],
            account_ref=account.get("account_no"),
            mapped=MIXED,
            as_of=CUTOVER,
            currency="USD",
        )
        rows = list(customers_models.AccountOpeningBucket.objects.filter(account_id=account["id"]))
        assert len(rows) == 4
        assert all(row.amount >= Decimal("0") for row in rows)
        assert sum((row.amount for row in rows), Decimal("0")) == MIXED_DEBIT
        assert position["credit"] == MIXED_CREDIT


def test_def620_tc6__a_credit_only_row_writes_no_bucket_row_at_all(brazos, marcus):
    """BR-CUS-061 — *"aging buckets stay debit-only"*. A credit has no band, so
    it has no row, and with no bucket position there is no opening JE either
    (a zero JE says nothing and can never be corrected away — hard rule 4)."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="DEF620 B")
        position = import_writer.write_opening_buckets(
            account_id=account["id"],
            account_ref=account.get("account_no"),
            mapped={"ob_current": "-45.00"},
            as_of=CUTOVER,
            currency="USD",
        )
        assert not customers_models.AccountOpeningBucket.objects.filter(
            account_id=account["id"]
        ).exists()
        assert position["empty"] is True
        assert position["credit"] == MIXED_CREDIT


def test_def620_tc7__nothing_on_this_path_is_a_float(brazos, marcus):
    """CLAUDE.md rule 2. `Decimal` end to end: a float would turn the mixed
    row's arithmetic into 120.99999999999999 and the batch would fail its own
    tie-out — which is the good outcome; the bad one is a rounding step that
    'fixes' it and hides a real imbalance."""
    position = import_writer.opening_position(MIXED, account_ref="A-12103")
    assert isinstance(position["credit"], Decimal)
    assert isinstance(position["total"], Decimal)
    assert str(position["credit"]) == "45.00"
    assert str(position["total"]) == "121.00"


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE LEDGER — what a credit position posts is NOT signed
# ═══════════════════════════════════════════════════════════════════════════


def test_def620_tc8__the_credit_entry_refuses_by_name_and_never_guesses():
    """⛔ **BR-CUS-049 names ONE shape — AR ↔ opening-balance clearing — and
    BR-CUS-061 takes a credit OUT of AR.** No signed document states the GL pair
    a carried opening credit books to, nor whether it joins GT-16's batch
    tie-out. The prime directive: never resolve an open question by choosing a
    value."""
    with pytest.raises(NotImplementedError) as caught:
        import_writer.post_opening_credit_entry(
            batch_id="b", cutover_on=CUTOVER, currency="USD", accounts=[]
        )
    assert import_writer.OQ_OPENING_CREDIT_LANDING in str(caught.value)


def test_def620_tc9__a_credit_only_account_never_reaches_the_opening_batch(brazos, marcus):
    """❄️ GT-16's batch line — *"Σ clearing credits = Σ imported buckets"* — is
    an ALL-DEBIT statement. A credit-only account has an empty bucket position,
    so it is absent from the batch by construction and the frozen tie-out is
    arithmetically untouched.

    ⚠ **AMENDED 2026-08-30 — THE RECEIPT GAINED TWO KEYS AND THIS CASE ASSERTED
    THE WHOLE DICT.** `DEF-1713` added `deposits` as the SECOND money column of
    the same handoff — a migrated deposit posts DR opening clearing / CR deposit
    liability (BR-CUS-670) — so `post_opening_batch_from_import` now reports
    `deposits_posted` and `deposit_credits` beside the AR pair. The two batches
    are deliberately kept apart: ❄️ GT-16 is finance-signed as *Σ opening JEs =
    Σ imported BUCKETS*, and folding a deposit into it would move a frozen
    figure. So the AR half of this receipt is unchanged, which is what this case
    is actually about.

    **The three AR keys are asserted individually rather than as a whole-dict
    equality**, because whole-dict equality is what made a correct addition look
    like a regression, and it says nothing more than the three lines below do.
    The deposit pair is asserted at zero for the same reason the AR pair is: an
    empty run posts nothing on either side.
    """
    result = import_writer.post_opening_batch_from_import(
        batch_id="b", cutover_on=CUTOVER, imported_at=None, currency="USD", accounts=[]
    )
    assert result["posted"] == 0
    assert result["ar_debits"] == "0"
    assert result["clearing_credits"] == "0"
    assert result["deposits_posted"] == 0
    assert result["deposit_credits"] == "0"


def test_def620_tc10__an_unlanded_credit_is_audited_never_dropped(
    brazos, marcus, audit_rows  # noqa: F811
):
    """**CLAUDE.md rule 7 — every money action writes `audit_log`**, and money
    the product cannot yet place is exactly the money an operator must be able
    to find. The row loads (BR-CUS-061); the credit's landing is reported by
    name, in the trail, so nothing about it is silent."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="DEF620 C")
        import_writer.write_opening_buckets(
            account_id=account["id"],
            account_ref=account.get("account_no"),
            mapped=MIXED,
            as_of=CUTOVER,
            currency="USD",
        )
    written = [row for row in audit_rows if row["action"] == import_writer.AUDIT_OPENING_CREDIT]
    assert len(written) == 1
    after = written[0]["after"]
    assert after["credit"] == "45.00"  # not 76.00, and not absent
    assert after["oq"] == import_writer.OQ_OPENING_CREDIT_LANDING
    assert after["carried"] is False  # law 1 — the row does not claim what it did not do
    assert after["cells"] == [["ob_current", "45.00"]]


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE RUNNER — stage 2 carries the cell instead of refusing the row
# ═══════════════════════════════════════════════════════════════════════════


def _mapped(target_key, source_header, value, target=import_runs.TARGET_ACCOUNTS):
    offered = {
        column["target"]: column for column in import_runs.EXPLICIT_COLUMNS_BY_TARGET[target]
    }
    resolved = {source_header: {"target": target_key}}
    return import_runs._map_row({source_header: value}, resolved, offered, {})


def test_def620_tc11__stage_2_carries_a_negative_bucket_instead_of_refusing_it():
    """The matching half of the defect: the runner's `KIND_DECIMAL` branch
    refused the cell before `import_writer` ever saw it, so fixing only the
    writer would have fixed nothing an operator can see."""
    mapped, problems = _mapped("ob_current", "CURRENT", "-45.00")
    assert problems == {}
    assert mapped["ob_current"] == "-45.00"


def test_def620_tc12__a_negative_that_is_NOT_an_opening_bucket_still_refuses():
    """BR-CUS-061 rules OPENING BALANCES. A meter that cost minus $164 is still
    a typo, and widening the credit reading to every decimal column would make
    it one."""
    _mapped_out, problems = _mapped(
        "purchase_cost", "COST", "-164.00", target=import_runs.TARGET_ASSETS_METERS
    )
    assert "parse" in problems
    assert problems["parse"]["problem"] == "-164.00 is negative."
    assert "below zero" in problems["parse"]["fix_hint"]


def test_def620_tc13__end_to_end__the_credit_customer_migrates(brazos, marcus):
    """★ **THE POINT.** A utility migrating a base in which one account is in
    credit gets that account, with the right ageing on the debt it does owe.

    Before this fix the run rejected the row at stage 3 and the account was
    never created — *"and must settle them by hand in the system it is
    leaving"*."""
    with tenant_ctx(brazos):
        units = _two_units(marcus, brazos)
        # 62.10 / 0.00 / 121.00 of aged debt, and −45.00 of credit where GT-16's
        # frozen row carries 84.20 of Current debit.
        content = CREDIT_CSV.format(u1=units[0]["unit_no"], u2=units[1]["unit_no"])
        run_id = _run(marcus, content, options={"cutover_on": "2026-08-31"})
        from apps.metering import models as metering_models

        run = metering_models.ImportRun.objects.get(pk=run_id)
        assert import_runs.rejects(run) == []

        receipt = import_runs.load(marcus, run_id, {"write_mode": "insert", "approved": True})
        assert receipt["counts"]["created"] == 2
        # ⚠ Resolved by UNIT, not by account number. The demo seed carries
        # GT-16's own `A-12103` (`customers.sample_data.GT16_ACCOUNT_NO`), so on
        # a settings profile that provisions sample data the number is ambiguous
        # and the unit is not — BR-CUS-017 puts at most one live account on it.
        account = customers_models.Account.objects.get(tenant_id=brazos.id, unit_id=units[0]["id"])
        # BR-CUS-077 — the debt keeps its age, the credit is not netted into it.
        buckets = {
            row.bucket: row.amount
            for row in customers_models.AccountOpeningBucket.objects.filter(account_id=account.id)
        }
        assert buckets[customers_models.AccountOpeningBucket.BUCKET_CURRENT] == Decimal("0")
        assert buckets[customers_models.AccountOpeningBucket.BUCKET_90_PLUS] == Decimal("121.00")
        assert account.balance == Decimal("183.10")  # 62.10 + 0.00 + 121.00


# ═══════════════════════════════════════════════════════════════════════════
# 5 · TENANT ISOLATION (CLAUDE.md rule 1) — through a role RLS applies to
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.isolation
@requires_postgres
def test_def620_tc14__a_credit_customers_position_is_not_visible_next_door(
    rls, brazos, lonestar, marcus
):  # noqa: F811
    """⚠ A plain ORM query under `tenant_ctx` runs as a SUPERUSER and BYPASSES
    RLS, so that assertion would be VACUOUS. This uses the non-superuser probe
    role, which is the only thing that proves the boundary."""
    with live_tenant_context(brazos.id):
        account = _account_for(marcus, brazos, label="DEF620 D")
        import_writer.write_opening_buckets(
            account_id=account["id"],
            account_ref=account.get("account_no"),
            mapped=MIXED,
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
    assert_no_foreign_rows_anywhere(rls, lonestar, ("account_opening_buckets", "audit_log"))
