# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-001 (source-event posting contracts — TC-1 the LE-1 month
#           foots 598.69 = 598.69 · TC-2 the WE-1 issue handoff · TC-5 the
#           sole-writer and unbalanced refusals · TC-6 the replay guard ·
#           TC-7 isolation) · US-LED-003 (reversal pairs — TC-1 the mirror,
#           TC-3 the links, TC-5 no edit path)
#           Screens: S56 · S36
# Rules:    CLAUDE.md rule 1 (tenant scoping) · rule 2 (money NUMERIC(18,6) +
#           CHAR(3), never float) · rule 4 (financial immutability) · rule 5
#           (balanced pairs; the posting service is the sole writer) · rule 6
#           (idempotency) · rule 7 (every money action writes audit_log) ·
#           BR-LED-001 (dimension set incl. source_type + source_id on every
#           line) · BR-LED-003 (posted immutable; balanced AT POST) ·
#           BR-LED-007 (drift is only possible via a posting-service bypass) ·
#           BR-TEN-043 (event time is named by the caller, never a clock)
# Golden:   LE-1 / LE-2 (09-ledger/08-worked-examples.md, machine-computed) ·
#           US-LED-001 §7 Finance Calculation, CONFIRMED
# ───────────────────────────────────────────────────────
"""The ledger posting service: every money event becomes ONE balanced entry.

**THE TEST THIS FILE EXISTS FOR** is
`test_us_led_001_tc1__the_le1_month_foots_598_69`. US-LED-001 §7 states the
whole month's trial balance as a CONFIRMED finance calculation — 1000 Cash DR
442.87 · 1200 AR DR 152.32 · deposit interest expense DR 3.50 · revenue CR
506.31 · tax payable CR 47.38 · deposit liability CR 0.00 · opening equity CR
45.00 → **598.69 = 598.69**. That month is posted here through `post()` and no
other way, entry by entry, and the trial balance is summed back out of
`journal_lines`. If any future change to the posting service moves a figure,
that test says which GL and by how much.

WHAT RUNS WHERE, because it changes what a green run is worth:

  * The SERVICE-LAYER refusals (unbalanced, float, foreign account, missing
    source document, no key) run everywhere. They are what protects the SQLite
    developer database, which has no triggers at all.
  * The DATABASE laws — the sole-writer fence (ledger/0004), the posting-key
    unique index, the frozen `posting_key` on a posted entry — carry
    `requires_postgres` and SKIP on SQLite rather than passing vacuously.
  * The deferred balance trigger only fires at COMMIT, and pytest-django never
    commits, so the cases that assert it call `reach_commit()`
    (`SET CONSTRAINTS ALL IMMEDIATE`). Without that call those tests pass while
    the trigger never runs once — see the helper's own docstring in
    tests/test_us_led_journal_core.py, where the same trap is documented.

EVERY FIGURE IN THIS FILE IS COPIED, NEVER COMPUTED. LE-1, LE-2 and
US-LED-001 TC-2 are machine-computed workbook fixtures; the numbers below are
transcribed with the line they came from quoted beside them, and nothing here
re-derives one. A test that recomputed the expected value would agree with a
broken implementation.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction

from core import errors

from apps.ledger import chart, models, posting, selectors

from tests.isolation_helpers import (
    assert_denied_without_context,
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: BR-TEN-043 / the PO's OQ-107 ruling — the caller names the moment. A module
#: constant rather than a clock read, so every entry in a fixture month stamps
#: the same `posted_at` and G6's "no clock in a money path" holds in the tests
#: as well as in the code.
POSTED_AT = datetime(2026, 8, 3, 9, 15, tzinfo=dt_timezone.utc)

JOURNAL_TABLES = ("journal_entries", "journal_lines")


# ── raw-write helpers, for the cases that must BYPASS the service ───────────
# Copied rather than imported from tests/test_us_led_journal_core.py on purpose:
# importing one test module into another makes pytest register the same
# fixtures twice and every test in this file errors with
# `assert not self._finalizers` before it runs. Three short helpers duplicated
# is cheaper than a suite that cannot collect.
def reach_commit():
    """Fire the DEFERRED balance triggers without leaving the transaction.

    LOAD-BEARING. The balance triggers are DEFERRABLE INITIALLY DEFERRED so they
    run at COMMIT — and pytest-django wraps every test in a transaction it ROLLS
    BACK, so a real COMMIT never happens. Written the obvious way, a case
    asserting the trigger passes while the trigger never fires once.
    """
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def open_raw_write_window():
    """Let the next raw INSERT past the sole-writer fence (ledger/0004).

    Used ONLY by the two cases below that must reach the tables without going
    through `post()` — because what they assert is the DATABASE's own law, and
    a check that could only be made through the service would be asserting that
    the service behaves. Every other case in this file goes through `post()`,
    and the fence itself is proved by the two cases that never call this.
    """
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.ledger_posting', 'on', true)")


def shut_raw_write_window():
    """Close it again. `set_config(..., true)` is transaction-local and pytest
    keeps one transaction per test, so a window opened by a raw helper stays
    open for the rest of the test — which would silently license the very
    INSERT the sole-writer case is trying to have refused."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.ledger_posting', 'off', true)")


def raw_entry(tenant, **overrides):
    """A journal entry written AROUND the posting service, for the cases that
    prove the database refuses one.

    ⚠ **`currency` BECAME REQUIRED HERE ON 2026-09-24 (`P0.7`), AND WHY IS
    WORTH THE LINES.** `JournalEntry.currency` carried `default="USD"` until
    then, so this helper never named one and Django filled it in — which is
    exactly the defect `P0.7` removes: *a caller that forgets the currency
    silently gets US dollars*, and for a CAD utility that is its books becoming
    American one entry at a time.

    **Removing a Django `default` does not make the write FAIL — it makes it
    write `""`.** A `CharField` with no default is the empty string, not an
    error. So the empty value went in, and `tenancy/0050`'s foreign key into
    `currencies` refused it at COMMIT, inside Django's teardown
    `check_constraints`, naming `fk_journal_entries_currency` and NEITHER test.
    **That is the safety net working** — and a teardown traceback is a poor
    place to learn the lesson, so the helper names the currency instead.
    """
    values = dict(
        tenant=tenant,
        entry_date=date(2026, 7, 31),
        source_type="invoice",
        currency="USD",
    )
    values.update(overrides)
    open_raw_write_window()
    return models.JournalEntry.objects.create(**values)


def raw_line(tenant, entry, account, side, amount):
    open_raw_write_window()
    return models.JournalLine.objects.create(
        tenant=tenant,
        journal_entry=entry,
        ledger_account=account,
        side=side,
        amount=Decimal(amount),
    )


def raw_post(entry):
    entry.status = models.JE_POSTED
    entry.save(update_fields=["status", "posted_at", "updated_at"])


# ── the smallest chart these cases need ─────────────────────────────────────
def gl(tenant, code, type_="revenue", name=None):
    """The tenant's account for `code`, seeded or created.

    Provisioning seeds the finance-signed shared chart (B5 line 74), so 1000,
    1200, 2300, 3000, 6950 and the fee-revenue rows already exist. The
    per-service revenue accounts exist only for the services the tenant sells
    (PO ruling 2026-08-11, OQ-115) and `2200-03` never does — the signed chart
    says tenant authorities mint their own — so those are created here.
    """
    row, _made = models.LedgerAccount.objects.get_or_create(
        tenant=tenant, code=code, defaults={"name": name or f"GL {code}", "type": type_}
    )
    return row


def line(account, side, amount, **overrides):
    """One posting line with BR-LED-001's two mandatory dimensions filled in.

    `source_type` / `source_id` are required on every line by BR-LED-001 (*"every
    journal line carries source_type + source_id"*), so the helper supplies a
    default pair rather than letting each case repeat it; a case that is ABOUT
    the missing pair overrides it explicitly.
    """
    values = dict(source_type="invoice_line", source_id=uuid_for(account.code))
    values.update(overrides)
    return posting.PostingLine(
        ledger_account_id=account.id,
        side=side,
        amount=Decimal(amount),
        **values,
    )


def uuid_for(seed):
    """A stable uuid per fixture string, so a replayed fixture keys the same."""
    import uuid as _uuid

    return _uuid.uuid5(_uuid.NAMESPACE_URL, f"smartbillhub-test/{seed}")


def a_request(lines, *, key="invoice|fixture|issued", entry_date=date(2026, 7, 31), **overrides):
    values = dict(
        posting_key=key,
        entry_date=entry_date,
        posted_at=POSTED_AT,
        currency="USD",
        lines=tuple(lines),
        source_type="invoice",
        source_id=uuid_for(key),
        memo="fixture",
    )
    values.update(overrides)
    return posting.PostingRequest(**values)


def trial_balance(tenant):
    """Σ per GL account out of `journal_lines` — the S56 read, done by hand.

    Deliberately NOT a selector: US-LED-008 builds the trial balance and this
    file must not assert against the same code that would be wrong. Summing the
    raw rows is what makes this a check on what LANDED rather than on what a
    reporting layer says landed (BR-REP-002's principle turned into a test).
    """
    totals: dict[str, dict[str, Decimal]] = {}
    rows = models.JournalLine.objects.filter(
        tenant=tenant, journal_entry__status=models.JE_POSTED
    ).values_list("ledger_account__code", "side", "amount")
    for code, side, amount in rows:
        bucket = totals.setdefault(code, {"debit": Decimal("0"), "credit": Decimal("0")})
        bucket[side] += amount
    return totals


def net_debit(totals, code):
    bucket = totals.get(code, {"debit": Decimal("0"), "credit": Decimal("0")})
    return bucket["debit"] - bucket["credit"]


def net_credit(totals, code):
    return -net_debit(totals, code)


def gross(totals, code, side):
    """The un-netted side total — the only way to see that a same-account
    transfer wrote TWO rows rather than none."""
    return totals.get(code, {"debit": Decimal("0"), "credit": Decimal("0")})[side]


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-001 TC-2 — the WE-1 issue handoff, bucket for bucket
# ═══════════════════════════════════════════════════════════════════════════
#: US-LED-001 TC-2 verbatim: *"One JE: DR 1200 AR 247.87 / CR 4100 88.60 ·
#: 4105 12.00 · 4110 39.50 · 4115 8.00 · 4120 15.80 · 4130 18.00 · 4150 40.00 ·
#: 2200–03 20.97 · 4200 5.00"*. Copied, not computed.
WE1_AR = Decimal("247.87")
WE1_BUCKETS = (
    ("4100", Decimal("88.60")),
    ("4105", Decimal("12.00")),
    ("4110", Decimal("39.50")),
    ("4115", Decimal("8.00")),
    ("4120", Decimal("15.80")),
    ("4130", Decimal("18.00")),
    ("4150", Decimal("40.00")),
    ("2200-03", Decimal("20.97")),
    ("4200", Decimal("5.00")),
)
#: LE-2 verbatim: *"Electric 100.60 (usage 88.60 + base 12.00) · Water 47.50 ·
#: Sewer 15.80 · Trash 18.00 · Solar capacity 40.00 · Late fee 5.00 = 226.90"*
#: — the revenue slice of the same entry, i.e. everything above except the tax.
WE1_REVENUE = Decimal("226.90")
WE1_TAX = Decimal("20.97")


def we1_lines(tenant):
    debit = line(gl(tenant, "1200", "asset"), models.SIDE_DEBIT, WE1_AR, source_type="invoice")
    credits = [
        line(
            gl(tenant, code, "liability" if code.startswith("2") else "revenue"),
            models.SIDE_CREDIT,
            amount,
        )
        for code, amount in WE1_BUCKETS
    ]
    return [debit, *credits]


def test_us_led_001_tc2__the_we1_issue_handoff_posts_as_one_balanced_entry(brazos, dana):
    """US-LED-001's contract row for *"Invoice issued"*: DR AR the invoice
    total, CR the per-GL buckets from the stamped lines (BR-BIL-011).

    Every figure is TC-2's own. The point of the test is that the service
    writes what it is handed — nine credit buckets and one debit, none of them
    merged, netted or re-rounded, because *"posting asserts, never recomputes"*.
    """
    with tenant_ctx(brazos):
        result = posting.post(a_request(we1_lines(brazos), key="invoice|WE-1|issued"))

        assert result.created is True
        assert (result.debits, result.credits) == (WE1_AR, WE1_AR)
        assert result.line_count == 10

        totals = trial_balance(brazos)
        assert net_debit(totals, "1200") == WE1_AR
        for code, amount in WE1_BUCKETS:
            assert net_credit(totals, code) == amount, f"{code} did not land at {amount}"

        # LE-2's slice: the revenue lines of this one entry sum to 226.90 and
        # the tax to 20.97 — 226.90 + 20.97 = 247.87 to the cent.
        revenue = sum(amount for code, amount in WE1_BUCKETS if not code.startswith("2200"))
        assert revenue == WE1_REVENUE
        assert net_credit(totals, "2200-03") == WE1_TAX
        assert revenue + WE1_TAX == WE1_AR


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-001 TC-1 — the LE-1 month, end to end, footing 598.69 = 598.69
# ═══════════════════════════════════════════════════════════════════════════
#: LE-1 verbatim (09-ledger/08-worked-examples.md), and US-LED-001 §7 restates
#: every one of these as a CONFIRMED finance calculation. Transcribed.
LE1_OPENING_AR = Decimal("45.00")
LE1_DEPOSIT_HELD = Decimal("150.00")
LE1_DEPOSIT_INTEREST = Decimal("3.50")
LE1_WE3_BILL = Decimal("16.42")  # minimum bill: 15.00 revenue + 1.42 tax
LE1_WE3_REVENUE = Decimal("15.00")
LE1_WE3_TAX = Decimal("1.42")
LE1_WE7B_BILL = Decimal("289.40")  # taxable 264.41 + tax 24.99
LE1_WE7B_REVENUE = Decimal("264.41")
LE1_WE7B_TAX = Decimal("24.99")
LE1_DEPOSIT_APPLIED = Decimal("153.50")
LE1_MASTER_TRANSFER = Decimal("135.90")
LE1_PAYMENT = Decimal("292.87")

#: LE-1's trial-balance table, verbatim.
LE1_CASH = Decimal("442.87")  # "1000 Cash (150.00 + 292.87) | 442.87"
LE1_AR = Decimal("152.32")  # "1200 AR | 152.32"
LE1_INTEREST_EXPENSE = Decimal("3.50")  # "6xxx Deposit interest expense | 3.50"
LE1_REVENUE = Decimal("506.31")  # "4xxx Revenue (226.90 + 15.00 + 264.41) | 506.31"
LE1_TAX_PAYABLE = Decimal("47.38")  # "2200-03 Tax payable (20.97 + 1.42 + 24.99) | 47.38"
LE1_DEPOSIT_LIABILITY = Decimal("0.00")  # "2300 (150.00 + 3.50 - 153.50) | 0.00"
LE1_OPENING_EQUITY = Decimal("45.00")  # "3000 Opening balance equity | 45.00"
LE1_FOOTING = Decimal("598.69")  # "Totals | 598.69 | 598.69 ✔"


def post_le1_month(tenant):
    """Every posting LE-1 names, in the workbook's own order, through post().

    LE-1 §Postings verbatim: *"opening AR 45.00 · deposit held 150.00 (cash DR /
    liability CR) · interest accrual 3.50 (DR interest exp / CR liability) ·
    three bills (AR DR 553.69 / revenue CR 506.31 / tax CR 47.38) · deposit
    application (liability DR 153.50 / AR CR) · master transfer (AR ACC-1055 CR
    135.90 / AR ACC-0009 DR 135.90 — AR total unchanged) · payment (cash DR
    292.87 / AR CR)."*
    """
    cash = gl(tenant, "1000", "asset")
    ar = gl(tenant, "1200", "asset")
    tax = gl(tenant, "2200-03", "liability")
    deposit = gl(tenant, "2300", "liability")
    opening = gl(tenant, "3000", "equity")
    interest = gl(tenant, "6950", "expense")
    revenue = gl(tenant, "4100", "revenue")

    def post_pair(key, debit_gl, credit_gl, amount, source_type, entry_date):
        return posting.post(
            a_request(
                [
                    line(debit_gl, models.SIDE_DEBIT, amount, source_type=source_type),
                    line(credit_gl, models.SIDE_CREDIT, amount, source_type=source_type),
                ],
                key=key,
                entry_date=entry_date,
                source_type=source_type,
            )
        )

    # Opening balance (BR-CUS-049) — the only entry dated before the month.
    post_pair(
        "opening_balance|ACC-1042|cutover",
        ar,
        opening,
        LE1_OPENING_AR,
        "opening_balance",
        date(2026, 6, 30),
    )
    # Cash deposit taken (BR-PAY-012) and its interest accrual (BR-CUS-050/057).
    post_pair(
        "payment|DEP-1042|deposit_taken",
        cash,
        deposit,
        LE1_DEPOSIT_HELD,
        "payment",
        date(2026, 7, 1),
    )
    post_pair(
        "deposit|DEP-1042|interest_accrued",
        interest,
        deposit,
        LE1_DEPOSIT_INTEREST,
        "deposit",
        date(2026, 7, 31),
    )
    # The three bills. WE-1 posts its nine real buckets (TC-2); WE-3 and WE-7B
    # are stated by LE-1 only as revenue + tax totals, so that is exactly what
    # is posted — a per-service split for them would be invented.
    posting.post(a_request(we1_lines(tenant), key="invoice|WE-1|issued"))
    posting.post(
        a_request(
            [
                line(ar, models.SIDE_DEBIT, LE1_WE3_BILL, source_type="invoice"),
                line(revenue, models.SIDE_CREDIT, LE1_WE3_REVENUE),
                line(tax, models.SIDE_CREDIT, LE1_WE3_TAX),
            ],
            key="invoice|WE-3|issued",
        )
    )
    posting.post(
        a_request(
            [
                line(ar, models.SIDE_DEBIT, LE1_WE7B_BILL, source_type="invoice"),
                line(revenue, models.SIDE_CREDIT, LE1_WE7B_REVENUE),
                line(tax, models.SIDE_CREDIT, LE1_WE7B_TAX),
            ],
            key="invoice|WE-7B|issued",
        )
    )
    # Deposit application at final bill (BR-BIL-013) and the master transfer,
    # which moves AR between two accounts and leaves the AR TOTAL unchanged.
    post_pair(
        "invoice|WE-7B|deposit_applied",
        deposit,
        ar,
        LE1_DEPOSIT_APPLIED,
        "invoice",
        date(2026, 7, 31),
    )
    posting.post(
        a_request(
            [
                line(
                    ar,
                    models.SIDE_DEBIT,
                    LE1_MASTER_TRANSFER,
                    source_type="transfer",
                    source_id=uuid_for("ACC-0009"),
                    account_id=None,
                ),
                line(
                    ar,
                    models.SIDE_CREDIT,
                    LE1_MASTER_TRANSFER,
                    source_type="transfer",
                    source_id=uuid_for("ACC-1055"),
                ),
            ],
            key="transfer|ACC-1055|to_master",
            source_type="transfer",
        )
    )
    # Payment cleared (payments §12).
    post_pair("payment|PAY-1042|cleared", cash, ar, LE1_PAYMENT, "payment", date(2026, 7, 31))


def test_us_led_001_tc1__the_le1_month_foots_598_69(brazos, dana):
    """US-LED-001 TC-1 and §7, verbatim: the LE-1 month posted end to end,
    *"every entry balanced; period trial balance totals 598.69 = 598.69 ✔;
    AR total unchanged by the transfer"*.

    THE POINT: every one of those figures is summed back out of `journal_lines`
    rather than out of anything the posting service returned. A service that
    quietly dropped a line, merged two, or wrote a credit as a debit would
    still report success and would fail here, naming the GL.
    """
    with tenant_ctx(brazos):
        post_le1_month(brazos)
        totals = trial_balance(brazos)

        assert net_debit(totals, "1000") == LE1_CASH
        assert net_debit(totals, "1200") == LE1_AR
        assert net_debit(totals, "6950") == LE1_INTEREST_EXPENSE
        assert net_credit(totals, "2200-03") == LE1_TAX_PAYABLE
        assert net_credit(totals, "2300") == LE1_DEPOSIT_LIABILITY
        assert net_credit(totals, "3000") == LE1_OPENING_EQUITY

        revenue = sum(net_credit(totals, code) for code in totals if code.startswith("4"))
        assert revenue == LE1_REVENUE

        # The footing itself: net debits and net credits across the whole chart.
        debits = sum(v for v in (net_debit(totals, c) for c in totals) if v > 0)
        credits = sum(v for v in (net_credit(totals, c) for c in totals) if v > 0)
        assert debits == LE1_FOOTING, f"trial balance debits {debits} != {LE1_FOOTING}"
        assert credits == LE1_FOOTING, f"trial balance credits {credits} != {LE1_FOOTING}"

        # And every single entry balances on its own, which is the property the
        # footing hides: a month of two equal-and-opposite errors also foots.
        for entry in models.JournalEntry.objects.filter(tenant=brazos):
            sides = {"debit": Decimal("0"), "credit": Decimal("0")}
            for side, amount in entry.lines.values_list("side", "amount"):
                sides[side] += amount
            assert sides["debit"] == sides["credit"], f"entry {entry.pk} is unbalanced"


def test_us_led_001_tc1__the_master_transfer_leaves_the_ar_total_unchanged(brazos, dana):
    """LE-1: *"master transfer (AR ACC-1055 CR 135.90 / AR ACC-0009 DR 135.90 —
    AR total unchanged)"*.

    The one entry in the month whose two sides hit the SAME GL account. A
    posting service that collapsed same-account lines, or netted them to zero
    and wrote nothing, would leave the trial balance identical and the account
    ledgers wrong — so this asserts both rows exist.
    """
    with tenant_ctx(brazos):
        ar = gl(brazos, "1200", "asset")
        before = trial_balance(brazos)
        posting.post(
            a_request(
                [
                    line(ar, models.SIDE_DEBIT, LE1_MASTER_TRANSFER, source_type="transfer"),
                    line(
                        ar,
                        models.SIDE_CREDIT,
                        LE1_MASTER_TRANSFER,
                        source_type="transfer",
                        source_id=uuid_for("ACC-1055"),
                    ),
                ],
                key="transfer|ACC-1055|to_master",
                source_type="transfer",
            )
        )
        after = trial_balance(brazos)
        assert net_debit(after, "1200") == net_debit(before, "1200")
        assert (
            gross(after, "1200", models.SIDE_DEBIT) - gross(before, "1200", models.SIDE_DEBIT)
            == LE1_MASTER_TRANSFER
        )
        assert (
            gross(after, "1200", models.SIDE_CREDIT) - gross(before, "1200", models.SIDE_CREDIT)
            == LE1_MASTER_TRANSFER
        )
        assert models.JournalLine.objects.filter(tenant=brazos, ledger_account=ar).count() == 2


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-001 TC-5 — nothing unbalanced, and nothing partial
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_001_tc5__an_unbalanced_request_is_refused_and_writes_nothing(brazos, dana):
    """CLAUDE.md rule 5. 100.00 debit against 60.00 credit.

    Refused in the service so the caller reads a sentence naming the delta
    instead of a commit-time trigger message — and, crucially, NOTHING is
    written: not the draft entry, not the first line. *"Nothing partial
    lands"* is TC-5's own wording.
    """
    with tenant_ctx(brazos):
        before = models.JournalEntry.objects.filter(tenant=brazos).count()
        with pytest.raises(posting.PostingError) as raised:
            posting.post(
                a_request(
                    [
                        line(gl(brazos, "1200", "asset"), models.SIDE_DEBIT, "100.00"),
                        line(gl(brazos, "4100"), models.SIDE_CREDIT, "60.00"),
                    ],
                    key="invoice|unbalanced|issued",
                )
            )
        assert "UNBALANCED" in str(raised.value)
        assert "100.00" in str(raised.value) and "60.00" in str(raised.value)
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == before


@requires_postgres
def test_us_led_001_tc5__the_database_refuses_an_unbalanced_entry_even_so(brazos, dana):
    """The other half of the same law, and the half that matters: the fence is
    the DATABASE (ledger/0002), not this service's arithmetic.

    The service check is bypassed here on purpose — the lines are written raw,
    inside the posting window — so what is proved is that an unbalanced entry
    cannot reach the books by ANY route, including a future bug in `post()`.
    """
    with tenant_ctx(brazos):
        with pytest.raises(DatabaseError) as raised:
            with transaction.atomic():
                entry = raw_entry(brazos)
                raw_line(brazos, entry, gl(brazos, "1200", "asset"), models.SIDE_DEBIT, "100.00")
                raw_line(brazos, entry, gl(brazos, "4100"), models.SIDE_CREDIT, "60.00")
                raw_post(entry)
                reach_commit()
        assert "UNBALANCED" in str(raised.value)


def test_us_led_001__an_entry_with_no_lines_is_refused(brazos, dana):
    """B2 §1: *journal_entry 1:N journal_lines (balanced)*. An empty entry
    balances vacuously (0 = 0) and is not a journal entry."""
    with tenant_ctx(brazos):
        with pytest.raises(posting.PostingError) as raised:
            posting.post(a_request([], key="invoice|empty|issued"))
        assert "no lines" in str(raised.value)


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-001 TC-5 (first half) — the SOLE WRITER
# ═══════════════════════════════════════════════════════════════════════════
@requires_postgres
def test_us_led_001_tc5__a_journal_line_written_outside_the_service_is_refused(brazos, dana):
    """TC-5 verbatim: *"a billing/payments code path INSERTs into
    `journal_lines` directly … insert forbidden (sole writer)"*.

    Until ledger/0004 this was enforced by nothing — CLAUDE.md rule 5 was a
    sentence and any module could have written the books. BR-LED-007 names that
    bypass as the ONLY way a subledger tie-out can drift, which means the S36
    drift panel was a detector for a hole nothing was closing.

    The parent here is a DRAFT, deliberately. A line inserted against a POSTED
    entry is refused by 0002's append-only trigger, which fires first and would
    make this case pass for the wrong reason — it would prove hard rule 4 all
    over again and say nothing about the sole-writer fence. On a draft, the
    append-only trigger lets the row through and only the fence stops it.
    """
    with tenant_ctx(brazos):
        draft = raw_entry(brazos)  # opens the window
        shut_raw_write_window()  # and closes it again — see the helper
        with pytest.raises(DatabaseError) as raised, transaction.atomic():
            models.JournalLine.objects.create(
                tenant=brazos,
                journal_entry=draft,
                ledger_account=gl(brazos, "4200"),
                side=models.SIDE_CREDIT,
                amount=Decimal("5.00"),
            )
        assert "rule 5" in str(raised.value)
        assert "posting service" in str(raised.value)
        assert "journal_lines" in str(raised.value)


@requires_postgres
def test_us_led_001_tc5__a_journal_entry_written_outside_the_service_is_refused(brazos, dana):
    """Same fence on the header. A draft written outside `post()` would be a
    door into the books: nothing else could insert its lines, but the entry
    would exist un-keyed, un-audited and invisible to the replay guard."""
    with tenant_ctx(brazos):
        with pytest.raises(DatabaseError) as raised, transaction.atomic():
            models.JournalEntry.objects.create(
                tenant=brazos, entry_date=date(2026, 7, 31), source_type="invoice"
            )
        assert "rule 5" in str(raised.value)


@requires_postgres
def test_us_led_001_tc5__the_write_window_is_shut_again_before_post_returns(brazos, dana):
    """The fence would be worthless if `post()` left the window open: the first
    posting of a request would silently license every raw write after it, for
    the rest of the transaction.

    So the GUC is read back after a successful post and must be `off`.
    """
    with tenant_ctx(brazos):
        posting.post(
            a_request(
                [
                    line(gl(brazos, "1200", "asset"), models.SIDE_DEBIT, "10.00"),
                    line(gl(brazos, "4100"), models.SIDE_CREDIT, "10.00"),
                ],
                key="invoice|window|issued",
            )
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting(%s, true)", [posting.WRITE_WINDOW_GUC])
            assert cursor.fetchone()[0] == posting.WRITE_WINDOW_SHUT


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-001 TC-6 — the replay guard (hard rule 6)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_001_tc6__replaying_a_handoff_writes_nothing_and_returns_the_first_entry(
    brazos, dana
):
    """TC-6 verbatim: *"the same issue handoff replayed twice → second replay
    no-ops on the per-source posting guard — one entry, ever"*.

    A resumed bill run replaying yesterday's handoff is doing the RIGHT thing,
    so the second call returns a result rather than raising, and it returns the
    FIRST entry's id so the caller can still link to the books.
    """
    with tenant_ctx(brazos):
        request = a_request(we1_lines(brazos), key="invoice|WE-1|issued")
        first = posting.post(request)
        second = posting.post(request)

        assert first.created is True and second.created is False
        assert second.entry_id == first.entry_id
        assert (second.debits, second.credits) == (WE1_AR, WE1_AR)
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == 1
        assert models.JournalLine.objects.filter(tenant=brazos).count() == 10


def test_us_led_001_tc6__a_different_event_on_the_same_document_is_a_different_entry(brazos, dana):
    """The reason the key has THREE parts. A payment's clearing entry and its
    later NSF reversal both name the same payment; if the key were the document
    alone, the NSF would be swallowed as a replay and the books would never
    learn the payment bounced.
    """
    with tenant_ctx(brazos):
        payment_id = uuid_for("PAY-1042")
        cleared = posting.posting_key(source_type="payment", source_id=payment_id, event="cleared")
        bounced = posting.posting_key(
            source_type="payment", source_id=payment_id, event="nsf_reversed"
        )
        assert cleared != bounced
        cash, ar = gl(brazos, "1000", "asset"), gl(brazos, "1200", "asset")
        first = posting.post(
            a_request(
                [
                    line(cash, models.SIDE_DEBIT, LE1_PAYMENT, source_type="payment"),
                    line(ar, models.SIDE_CREDIT, LE1_PAYMENT, source_type="payment"),
                ],
                key=cleared,
            )
        )
        second = posting.post(
            a_request(
                [
                    line(ar, models.SIDE_DEBIT, LE1_PAYMENT, source_type="payment"),
                    line(cash, models.SIDE_CREDIT, LE1_PAYMENT, source_type="payment"),
                ],
                key=bounced,
            )
        )
        assert first.created and second.created
        assert first.entry_id != second.entry_id


def test_us_led_001_tc6__a_request_with_no_posting_key_is_refused(brazos, dana):
    """Hard rule 6. Without a key a replay cannot be recognised, so the same
    money event lands twice and nothing in the books says which is which."""
    with tenant_ctx(brazos):
        with pytest.raises(posting.PostingError) as raised:
            posting.post(
                a_request(
                    [
                        line(gl(brazos, "1200", "asset"), models.SIDE_DEBIT, "10.00"),
                        line(gl(brazos, "4100"), models.SIDE_CREDIT, "10.00"),
                    ],
                    key="   ",
                )
            )
        assert "posting_key" in str(raised.value)


def test_us_led_001_tc6__the_key_refuses_to_be_composed_with_a_part_missing(brazos):
    """`core.idempotency`'s discipline, applied here: a short key collides
    across different documents, which is the double-posting it exists to
    prevent."""
    assert (
        posting.posting_key(source_type="invoice", source_id="abc", event="issued")
        == "invoice|abc|issued"
    )
    for bad in (
        dict(source_type="", source_id="abc", event="issued"),
        dict(source_type="invoice", source_id=None, event="issued"),
        dict(source_type="invoice", source_id="abc", event="  "),
    ):
        with pytest.raises(posting.PostingError):
            posting.posting_key(**bad)


@requires_postgres
def test_us_led_001_tc6__a_lost_race_is_answered_with_the_winners_entry(brazos, dana, monkeypatch):
    """The half a look-before-insert cannot give: two workers racing the SAME
    handoff.

    Simulated by blinding the pre-check — exactly what a worker sees when the
    other one commits between its SELECT and its INSERT — so the second call
    reaches the INSERT and is refused by `uq_journal_entries_posting_key`. A
    lost race and a replay are the same fact: one entry exists, ours is not it.
    """
    with tenant_ctx(brazos):
        request = a_request(we1_lines(brazos), key="invoice|WE-1|issued")
        first = posting.post(request)

        real = posting._existing_entry
        calls = {"n": 0}

        def blind_once(tenant_id, key):
            calls["n"] += 1
            return None if calls["n"] == 1 else real(tenant_id, key)

        monkeypatch.setattr(posting, "_existing_entry", blind_once)
        second = posting.post(request)

        assert second.created is False
        assert second.entry_id == first.entry_id
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == 1


# ═══════════════════════════════════════════════════════════════════════════
# CLAUDE.md rule 2 — money, and the shapes that are not money
# ═══════════════════════════════════════════════════════════════════════════
def test_hard_rule_2__a_float_amount_is_refused_rather_than_converted(brazos, dana):
    """*"never float/cents"*. Converting `247.87` from a float would hide the
    place where money became binary; the refusal names it instead."""
    with tenant_ctx(brazos):
        with pytest.raises(posting.PostingError) as raised:
            posting.post(
                a_request(
                    [
                        posting.PostingLine(
                            ledger_account_id=gl(brazos, "1200", "asset").id,
                            side=models.SIDE_DEBIT,
                            amount=247.87,  # a float, deliberately — see the docstring
                            source_type="invoice",
                            source_id=uuid_for("WE-1"),
                        ),
                        line(gl(brazos, "4100"), models.SIDE_CREDIT, "247.87"),
                    ],
                    key="invoice|float|issued",
                )
            )
        assert "float" in str(raised.value) and "rule 2" in str(raised.value)


def test_hard_rule_2__a_negative_amount_is_refused(brazos, dana):
    """B2 §2 `CHECK (amount >= 0)` — direction is the SIDE. A negative amount is
    a second, invisible way to express a credit."""
    with tenant_ctx(brazos):
        with pytest.raises(posting.PostingError) as raised:
            posting.post(
                a_request(
                    [
                        line(gl(brazos, "1200", "asset"), models.SIDE_DEBIT, "-10.00"),
                        line(gl(brazos, "4100"), models.SIDE_CREDIT, "-10.00"),
                    ],
                    key="invoice|negative|issued",
                )
            )
        assert "negative" in str(raised.value)


def test_hard_rule_2__currency_is_the_entrys_char3_partner(brazos, dana):
    """One currency per entry, because a mixed-currency entry cannot balance in
    any meaningful sense. No default: a defaulted currency is how a CAD
    tenant's books quietly become USD."""
    with tenant_ctx(brazos):
        with pytest.raises(posting.PostingError) as raised:
            posting.post(
                a_request(
                    [
                        line(gl(brazos, "1200", "asset"), models.SIDE_DEBIT, "10.00"),
                        line(gl(brazos, "4100"), models.SIDE_CREDIT, "10.00"),
                    ],
                    key="invoice|currency|issued",
                    currency="DOLLARS",
                )
            )
        assert "CHAR(3)" in str(raised.value)


def test_hard_rule_5__an_unreadable_side_is_refused(brazos, dana):
    """`side='dbit'` falls into NEITHER balance filter, so its money vanishes
    from both totals while the entry computes 0 = 0 and looks balanced."""
    with tenant_ctx(brazos):
        with pytest.raises(posting.PostingError) as raised:
            posting.post(
                a_request(
                    [
                        line(gl(brazos, "1200", "asset"), "dbit", "10.00"),
                        line(gl(brazos, "4100"), models.SIDE_CREDIT, "10.00"),
                    ],
                    key="invoice|side|issued",
                )
            )
        assert "dbit" in str(raised.value)


# ═══════════════════════════════════════════════════════════════════════════
# BR-LED-001 — dimensions
# ═══════════════════════════════════════════════════════════════════════════
def test_br_led_001__a_line_that_names_no_source_document_is_refused(brazos, dana):
    """*"Every journal line carries source_type + source_id"* — it is what makes
    LE-5's auditor question *"what is the 506.31?"* answerable at all."""
    with tenant_ctx(brazos):
        with pytest.raises(posting.PostingError) as raised:
            posting.post(
                a_request(
                    [
                        line(gl(brazos, "1200", "asset"), models.SIDE_DEBIT, "10.00"),
                        line(
                            gl(brazos, "4100"),
                            models.SIDE_CREDIT,
                            "10.00",
                            source_type=None,
                            source_id=None,
                        ),
                    ],
                    key="invoice|undimensioned|issued",
                )
            )
        assert "source document" in str(raised.value)


def test_br_led_001__every_dimension_the_caller_supplies_is_stamped_on_the_line(brazos, dana):
    """r13 #1's seven columns, carried through unchanged.

    NOTE what this does NOT assert, because US-LED-002 owns it: the premises /
    unit chain is not RESOLVED here from the account — customers publishes no
    account → unit read and metering no unit → premises read. The caller
    supplies what it knows and the service stamps exactly that.
    """
    with tenant_ctx(brazos):
        service_id = uuid_for("service")
        result = posting.post(
            a_request(
                [
                    line(
                        gl(brazos, "1200", "asset"),
                        models.SIDE_DEBIT,
                        "10.00",
                        source_type="invoice",
                        source_id=uuid_for("INV-1"),
                    ),
                    line(
                        gl(brazos, "4100"),
                        models.SIDE_CREDIT,
                        "10.00",
                        source_type="invoice_line",
                        source_id=uuid_for("INV-1-L1"),
                    ),
                ],
                key="invoice|dimensions|issued",
            )
        )
        stamped = models.JournalLine.objects.filter(
            tenant=brazos, journal_entry_id=result.entry_id
        ).order_by("side")
        by_side = {row.side: row for row in stamped}
        assert by_side[models.SIDE_DEBIT].source_type == "invoice"
        assert by_side[models.SIDE_CREDIT].source_type == "invoice_line"
        assert by_side[models.SIDE_CREDIT].source_id == uuid_for("INV-1-L1")
        # The five conditional dimensions are lawfully empty on this entry.
        for field_name in ("service_id", "account_id", "premises_id", "unit_id"):
            assert getattr(by_side[models.SIDE_DEBIT], field_name) is None
        assert service_id is not None  # the fixture id exists; nothing invented it


# ═══════════════════════════════════════════════════════════════════════════
# CLAUDE.md rule 1 + US-LED-001 TC-7 — tenant scoping
# ═══════════════════════════════════════════════════════════════════════════
def test_hard_rule_1__posting_with_no_tenant_context_is_refused(brazos):
    """*"Never touch a tenant table without `app.tenant_id` set"*. Refused
    before a query is built, so the SQLite developer database is protected by
    the same law RLS gives Postgres."""
    with pytest.raises(errors.AuthError) as raised:
        posting.post(
            a_request(
                [
                    posting.PostingLine(
                        ledger_account_id=uuid_for("x"),
                        side=models.SIDE_DEBIT,
                        amount=Decimal("1.00"),
                        source_type="invoice",
                        source_id=uuid_for("x"),
                    )
                ],
                key="invoice|no-tenant|issued",
            )
        )
    assert raised.value.code == errors.AUTH_TENANT_UNRESOLVABLE


def test_us_led_001_tc7__an_account_of_another_tenant_posts_nothing(brazos, lonestar, dana):
    """TC-7: *"a forged source_id from the other tenant posts nothing"*, applied
    to the sharpest case — the GL ACCOUNT itself.

    Lone Star Ridge's `1200` is a real row with a real uuid. Handed to Brazos
    Bend's posting call it must be refused, and the refusal must not distinguish
    "not yours" from "not real": that would answer a question the asker has no
    right to.
    """
    with tenant_ctx(lonestar):
        theirs = gl(lonestar, "1200", "asset")
    with tenant_ctx(brazos):
        with pytest.raises(posting.PostingError) as raised:
            posting.post(
                a_request(
                    [
                        posting.PostingLine(
                            ledger_account_id=theirs.id,
                            side=models.SIDE_DEBIT,
                            amount=Decimal("10.00"),
                            source_type="invoice",
                            source_id=uuid_for("forged"),
                        ),
                        line(gl(brazos, "4100"), models.SIDE_CREDIT, "10.00"),
                    ],
                    key="invoice|forged|issued",
                )
            )
        assert "LIVE account of this tenant" in str(raised.value)
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == 0


def test_us_led_001__a_deactivated_account_cannot_receive_a_posting(brazos, dana):
    """IS-1 deactivate-first. An account the tenant has retired is one they have
    said stop using; posting to it would put money in a bucket the trial balance
    already treats as gone."""
    with tenant_ctx(brazos):
        from django.utils import timezone as dj_timezone

        retired = gl(brazos, "6805", "expense")
        retired.deleted_at = dj_timezone.now()
        retired.save(update_fields=["deleted_at"])
        with pytest.raises(posting.PostingError) as raised:
            posting.post(
                a_request(
                    [
                        line(retired, models.SIDE_DEBIT, "10.00"),
                        line(gl(brazos, "4100"), models.SIDE_CREDIT, "10.00"),
                    ],
                    key="invoice|retired|issued",
                )
            )
        assert "deactivated" in str(raised.value)


# ═══════════════════════════════════════════════════════════════════════════
# CLAUDE.md rule 7 — the trail
# ═══════════════════════════════════════════════════════════════════════════
def test_hard_rule_7__one_audit_row_per_posting_and_none_on_a_replay(brazos, dana, audit_rows):
    """*"Every money action writes `audit_log`"*, and EP-LED-01 §5 names the
    code: `journal.posted`, carrying the source ref.

    The replay half matters as much: a resumed batch that re-audited every
    handoff would fill the trail with events that did not happen, and a human
    reading it could not tell a real second posting from a retry.
    """
    with tenant_ctx(brazos):
        request = a_request(we1_lines(brazos), key="invoice|WE-1|issued")
        posting.post(request)
        rows = [row for row in audit_rows if row["action"] == posting.AUDIT_POSTED]
        assert len(rows) == 1
        after = rows[0]["after"]
        assert after["posting_key"] == "invoice|WE-1|issued"
        assert after["debits"] == str(WE1_AR) and after["credits"] == str(WE1_AR)
        assert after["entry_date"] == "2026-07-31"
        assert after["posted_at"] == POSTED_AT.isoformat()
        assert after["job"] == "ledger.posting"  # no actor = a system job

        posting.post(request)
        assert len([r for r in audit_rows if r["action"] == posting.AUDIT_POSTED]) == 1


def test_hard_rule_7__a_failed_audit_write_takes_the_posting_with_it(brazos, dana):
    """Rule 7 is not "audit if you can". `core.audit` raises when the trail
    cannot be written, and because that call is INSIDE the transaction the
    entry rolls back with it — money in the books with no record of who put it
    there is the state this ordering exists to prevent."""
    from core import audit as core_audit

    with tenant_ctx(brazos):
        previous = core_audit._sink
        core_audit.set_audit_sink(None)
        try:
            with pytest.raises(core_audit.AuditWriteError):
                posting.post(
                    a_request(
                        [
                            line(gl(brazos, "1200", "asset"), models.SIDE_DEBIT, "10.00"),
                            line(gl(brazos, "4100"), models.SIDE_CREDIT, "10.00"),
                        ],
                        key="invoice|no-audit|issued",
                    )
                )
        finally:
            core_audit.set_audit_sink(previous)
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# The dates are INPUTS — PO ruling 2026-08-11 (OQ-107), BR-TEN-043, gate G6
# ═══════════════════════════════════════════════════════════════════════════
def test_oq107__the_book_date_is_the_one_the_caller_named(brazos, dana):
    """PO 2026-08-11, verbatim: *"posting and actual dates can differ; ask
    actual date to user."*

    LE-9's shape: an event that HAPPENED on 30 July is posted on 3 August. Both
    facts survive — `entry_date` is what the trial balance groups by,
    `posted_at` is when the row became immutable — and neither is read from a
    clock.
    """
    with tenant_ctx(brazos):
        result = posting.post(
            a_request(
                [
                    line(gl(brazos, "1000", "asset"), models.SIDE_DEBIT, "292.87"),
                    line(gl(brazos, "1200", "asset"), models.SIDE_CREDIT, "292.87"),
                ],
                key="payment|PAY-1042|cleared",
                entry_date=date(2026, 7, 30),
            )
        )
        entry = models.JournalEntry.objects.get(pk=result.entry_id)
        assert entry.entry_date == date(2026, 7, 30)
        assert entry.posted_at == POSTED_AT
        assert entry.entry_date != entry.posted_at.date()


def test_oq107__a_datetime_is_not_a_book_date(brazos, dana):
    """A `datetime` slipped in where the book date belongs would silently carry
    a time zone into the one column the trial balance groups by — and on a
    tenant east of UTC that moves entries between months."""
    with tenant_ctx(brazos):
        with pytest.raises(posting.PostingError) as raised:
            posting.post(
                a_request(
                    [
                        line(gl(brazos, "1200", "asset"), models.SIDE_DEBIT, "10.00"),
                        line(gl(brazos, "4100"), models.SIDE_CREDIT, "10.00"),
                    ],
                    key="invoice|datetime|issued",
                    entry_date=POSTED_AT,
                )
            )
        assert "entry_date must be a date" in str(raised.value)


def test_g6__the_posting_service_reads_no_clock(brazos):
    """Gate G6 greps every money path for a wall-clock read; this is the same
    check aimed at one file, so the reason travels with the code.

    Comment-only lines are skipped for the same reason G6 skips them: the
    module docstring quotes the PO ruling that CREATED this law and says the
    words "reads a clock".
    """
    import inspect

    source = inspect.getsource(posting)
    body = [
        stripped
        for stripped in (raw.strip() for raw in source.splitlines())
        if stripped and not stripped.startswith("#")
    ]
    offenders = [
        stmt
        for stmt in body
        if "datetime.now(" in stmt or "timezone.now(" in stmt or "date.today(" in stmt
    ]
    assert not offenders, f"a clock read reached the posting service: {offenders}"


# ═══════════════════════════════════════════════════════════════════════════
# CLAUDE.md rule 4 — posted is forever
# ═══════════════════════════════════════════════════════════════════════════
@requires_postgres
def test_hard_rule_4__the_posting_key_of_a_posted_entry_is_frozen(brazos, dana):
    """The hole ledger/0004 had to close on its way past.

    0002's immutability trigger freezes a posted entry by NAMING each column,
    so a column it does not name stays writable. `posting_key` unnamed would
    have been a door straight back into double-posting: clear the key, replay
    the handoff, get a second entry. This proves the door is shut.
    """
    with tenant_ctx(brazos):
        result = posting.post(
            a_request(
                [
                    line(gl(brazos, "1200", "asset"), models.SIDE_DEBIT, "10.00"),
                    line(gl(brazos, "4100"), models.SIDE_CREDIT, "10.00"),
                ],
                key="invoice|frozen-key|issued",
            )
        )
        with pytest.raises(DatabaseError) as raised, transaction.atomic():
            models.JournalEntry.objects.filter(pk=result.entry_id).update(posting_key=None)
        assert "POSTED and immutable" in str(raised.value)
        entry = models.JournalEntry.objects.get(pk=result.entry_id)
        assert entry.posting_key == "invoice|frozen-key|issued"


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-003 — a correction is a NEW linked mirror, never an edit
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_003_tc1__a_reversal_mirrors_every_line_with_the_sides_swapped(brazos, dana):
    """US-LED-003 §5: *"`journal_entries` + `journal_lines` (same GLs, sides
    swapped)"*, and TC-1: the credit note *"mirrors the original in full"* while
    *"the original entry is byte-identical after"*.

    Nine buckets go out and nine come back the other way. Nothing is netted
    (LE-8's whole point is that all the entries survive and the NET effect is
    right), and the mirror's amounts are COPIED from the original rather than
    recomputed — a reversal that disagreed with what it reverses is the one
    thing it may never be.
    """
    with tenant_ctx(brazos):
        original = posting.post(a_request(we1_lines(brazos), key="invoice|WE-1|issued"))
        before = {
            (row.ledger_account_id, row.side, row.amount)
            for row in models.JournalLine.objects.filter(journal_entry_id=original.entry_id)
        }

        mirror = posting.reverse_entry(
            original.entry_id,
            posting_key="credit_note|WE-1|reversed",
            entry_date=date(2026, 8, 12),
            posted_at=POSTED_AT,
        )
        assert mirror.created is True
        assert (mirror.debits, mirror.credits) == (WE1_AR, WE1_AR)
        assert mirror.line_count == 10

        after = {
            (row.ledger_account_id, row.side, row.amount)
            for row in models.JournalLine.objects.filter(journal_entry_id=mirror.entry_id)
        }
        flipped = {
            (
                account,
                models.SIDE_CREDIT if side == models.SIDE_DEBIT else models.SIDE_DEBIT,
                amount,
            )
            for account, side, amount in before
        }
        assert after == flipped

        # The original is untouched, and the two together net to nothing.
        still = {
            (row.ledger_account_id, row.side, row.amount)
            for row in models.JournalLine.objects.filter(journal_entry_id=original.entry_id)
        }
        assert still == before
        totals = trial_balance(brazos)
        assert net_debit(totals, "1200") == Decimal("0")
        assert net_credit(totals, "4100") == Decimal("0")


def test_us_led_003_tc3__the_mirror_links_back_and_carries_its_own_dates(brazos, dana):
    """TC-3: *"each mirror entry carries `reversal_of` → original; original
    resolves forward to its mirror"*.

    The mirror's `entry_date` is the CALLER's, not the original's: LE-9 is the
    case where July has closed and an August-arriving correction must land in
    August. BR-TEN-038's auto-forward is not implemented (no fiscal-period
    record exists anywhere in the schema), so the date named is the date
    written — which is also the PO's OQ-107 ruling.
    """
    with tenant_ctx(brazos):
        original = posting.post(
            a_request(
                [
                    line(gl(brazos, "1200", "asset"), models.SIDE_DEBIT, "247.87"),
                    line(gl(brazos, "4100"), models.SIDE_CREDIT, "247.87"),
                ],
                key="invoice|WE-1|issued",
                entry_date=date(2026, 7, 31),
            )
        )
        mirror = posting.reverse_entry(
            original.entry_id,
            posting_key="credit_note|WE-1|reversed",
            entry_date=date(2026, 8, 12),
            posted_at=POSTED_AT,
        )
        mirror_row = models.JournalEntry.objects.get(pk=mirror.entry_id)
        original_row = models.JournalEntry.objects.get(pk=original.entry_id)

        assert str(mirror_row.reversal_of_id) == original.entry_id
        assert mirror_row.type == models.JE_REVERSING
        assert mirror_row.entry_date == date(2026, 8, 12)
        assert original_row.entry_date == date(2026, 7, 31)
        assert original_row.reversed_by.get().pk == mirror_row.pk


def test_us_led_003_tc3__an_entry_can_be_reversed_only_once(brazos, dana):
    """*"once per entry"* (ledger field map, r13 #2). Two mirrors of one entry
    is the correction counted twice, and `uq_journal_entries_reversal` refuses
    the second even under a brand-new posting key."""
    with tenant_ctx(brazos):
        original = posting.post(
            a_request(
                [
                    line(gl(brazos, "1200", "asset"), models.SIDE_DEBIT, "10.00"),
                    line(gl(brazos, "4100"), models.SIDE_CREDIT, "10.00"),
                ],
                key="invoice|once|issued",
            )
        )
        posting.reverse_entry(
            original.entry_id,
            posting_key="credit_note|once|reversed",
            entry_date=date(2026, 8, 12),
            posted_at=POSTED_AT,
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            posting.reverse_entry(
                original.entry_id,
                posting_key="credit_note|once|reversed-again",
                entry_date=date(2026, 8, 13),
                posted_at=POSTED_AT,
            )


def test_us_led_003_tc5__a_draft_has_no_reversal_path(brazos, dana):
    """BR-LED-003 gives drafts full freedom — they are edited or deleted
    directly. Mirroring one would put an entry in the books to cancel an entry
    that never entered them."""
    with tenant_ctx(brazos):
        entry = raw_entry(brazos)
        raw_line(brazos, entry, gl(brazos, "1200", "asset"), models.SIDE_DEBIT, "10.00")
        with pytest.raises(posting.PostingError) as raised:
            posting.reverse_entry(
                entry.pk,
                posting_key="credit_note|draft|reversed",
                entry_date=date(2026, 8, 12),
                posted_at=POSTED_AT,
            )
        assert "not posted" in str(raised.value)


def test_us_led_003_tc7__another_tenants_entry_cannot_be_reversed(brazos, lonestar, dana):
    """TC-7: *"a Brazos Bend entry id in the handoff posts nothing"*."""
    with tenant_ctx(lonestar):
        theirs = posting.post(
            a_request(
                [
                    line(gl(lonestar, "1200", "asset"), models.SIDE_DEBIT, "10.00"),
                    line(gl(lonestar, "4100"), models.SIDE_CREDIT, "10.00"),
                ],
                key="invoice|theirs|issued",
            )
        )
    with tenant_ctx(brazos):
        with pytest.raises(posting.PostingError) as raised:
            posting.reverse_entry(
                theirs.entry_id,
                posting_key="credit_note|theirs|reversed",
                entry_date=date(2026, 8, 12),
                posted_at=POSTED_AT,
            )
        assert "not one of this tenant's entries" in str(raised.value)
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == 0


def test_us_led_003__a_reversal_audits_both_the_posting_and_the_reversal(brazos, dana, audit_rows):
    """Two rows, because they answer different questions: `journal.posted` says
    an entry entered the books, `journal.reversed` says an EARLIER entry was
    corrected — and S56 renders the linkage both ways."""
    with tenant_ctx(brazos):
        original = posting.post(
            a_request(
                [
                    line(gl(brazos, "1200", "asset"), models.SIDE_DEBIT, "10.00"),
                    line(gl(brazos, "4100"), models.SIDE_CREDIT, "10.00"),
                ],
                key="invoice|audited|issued",
            )
        )
        audit_rows.clear()
        mirror = posting.reverse_entry(
            original.entry_id,
            posting_key="credit_note|audited|reversed",
            entry_date=date(2026, 8, 12),
            posted_at=POSTED_AT,
        )
        actions = [row["action"] for row in audit_rows]
        assert actions == [posting.AUDIT_POSTED, posting.AUDIT_REVERSED]
        reversed_row = audit_rows[-1]
        assert reversed_row["entity_id"] == original.entry_id
        assert reversed_row["after"]["reversed_by_entry_id"] == mirror.entry_id


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-001 TC-7 (isolation) — the books never cross
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
@requires_postgres
def test_us_led_001_tc7__posted_journal_rows_are_rls_scoped(
    rls, brazos, lonestar, dana
):  # noqa: F811
    """TC-7 at the DATABASE, with the app-layer filters deliberately out of the
    path: *"its entries only; Brazos Bend journal rows invisible under RLS"*.

    Reading another tenant's journal is reading their entire business. The
    guarantee is `journal_entries_tenant_isolation` / `journal_lines_tenant_
    isolation` (ledger/0002), and a claim that a policy covers rows a new
    service writes is worth nothing until it is probed under a NOSUPERUSER role.
    """
    with tenant_ctx(brazos):
        mine = posting.post(
            a_request(
                [
                    line(gl(brazos, "1200", "asset"), models.SIDE_DEBIT, "10.00"),
                    line(gl(brazos, "4100"), models.SIDE_CREDIT, "10.00"),
                ],
                key="invoice|brazos|issued",
            )
        )
    with tenant_ctx(lonestar):
        posting.post(
            a_request(
                [
                    line(gl(lonestar, "1200", "asset"), models.SIDE_DEBIT, "20.00"),
                    line(gl(lonestar, "4100"), models.SIDE_CREDIT, "20.00"),
                ],
                key="invoice|lonestar|issued",
            )
        )

    assert_rls_scoped(
        rls, "journal_entries", owner=brazos, intruder=lonestar, owner_ids={mine.entry_id}
    )
    assert_rls_scoped(rls, "journal_lines", owner=brazos, intruder=lonestar)
    with live_tenant_context(lonestar.id):
        assert rls.count("journal_entries", "id = %s", [mine.entry_id]) == 0
    assert_no_foreign_rows_anywhere(rls, lonestar, JOURNAL_TABLES)


@pytest.mark.isolation
@requires_postgres
def test_us_led_001_tc7__journal_rows_are_denied_outright_with_no_context(
    rls, brazos
):  # noqa: F811
    """Deny-by-default, both halves: with `app.tenant_id` unset the policy's
    `::uuid` cast of '' fails and NO row is visible, and `post()` refuses before
    a query is ever built."""
    assert_denied_without_context(rls, *JOURNAL_TABLES)
    with pytest.raises(errors.AuthError):
        posting.post(
            a_request(
                [
                    posting.PostingLine(
                        ledger_account_id=uuid_for("x"),
                        side=models.SIDE_DEBIT,
                        amount=Decimal("1.00"),
                        source_type="invoice",
                        source_id=uuid_for("x"),
                    )
                ],
                key="invoice|no-context|issued",
            )
        )


def test_the_posting_service_resolves_accounts_by_designation_not_by_code(brazos, dana):
    """The property OQ-106 was raised for, asserted from the POSTING side.

    GT-16's entry is *"DR AR / CR opening-balance clearing"*. Neither `1200`
    nor `3000` appears in `apps/ledger/posting.py` — the caller resolves both by
    DESIGNATION through `apps/ledger/selectors.py`, so a tenant who renumbers AR
    to 1150 still posts to the right account.
    """
    import inspect

    source = inspect.getsource(posting)
    for code in ("1200", "3000", "4100", "2300", "6900"):
        assert f'"{code}"' not in source, f"the posting service hardcodes GL code {code}"
    with tenant_ctx(brazos):
        assert selectors.gl_account_for_designation(chart.AR).code == "1200"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-001@c7a1f30 (sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-01-posting-consumption.md US-LED-001 (TC-1..TC-7 + §7 Finance Calculation) and US-LED-003 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-1/LE-2/LE-8/LE-9 · 04-docs/02-decisions/02-database-design-brief.md §2/§3 + r13 #8 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-001/003/007/015 · 12-governance/02-decision-log.md 2026-08-11 OQ-107 "posting and actual dates can differ; ask actual date to user")
# generated: 2026-08-11 by Eng-Lead (W5 ledger posting-service lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S56/S57 endpoints are EP-LED-03/04) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: every guard here was PROVED RED FIRST on a live Postgres cluster —
#         mutations quoted verbatim in 12-governance/09-human-review-ledger.md
# exceptions: LE-1's WE-3 and WE-7B are posted as revenue + tax TOTALS because
#         that is all the workbook states for them; WE-1 alone has its nine
#         signed buckets (US-LED-001 TC-2) and they are asserted individually ·
#         `2200-03 Tax payable` is created by the fixture rather than seeded —
#         the signed chart says tenant authorities mint their own (BR-TEN-037),
#         so seeding one would invent an authority · the deferred balance
#         trigger only fires at COMMIT and pytest never commits, so the case
#         that asserts it calls `reach_commit()`; the rest rely on the service
#         check, which is the half that protects the sqlite developer database ·
#         US-LED-002's premises/unit RESOLUTION is NOT asserted here because it
#         is NOT built (no published customers account→unit read) — the
#         dimension test says so in as many words rather than leaving silence
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
