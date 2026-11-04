# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-001 (source-event posting contracts — the "Opening balance
#           (cutover batch)" row of the DR/CR table, and TC-3) ·
#           US-CUS-022 (the cutover import that will call this — NOT built)
#           Screens: S56
# Rules:    BR-CUS-049 (opening balances post as balanced opening JEs, AR ↔
#           clearing, dated at cutover, immutable) · BR-LED-001 (dimensions) ·
#           CLAUDE.md rule 4 (immutability) · rule 5 (balanced pairs, sole
#           writer) · rule 6 (idempotency) · rule 7 (audit)
# Golden:   GT-16 — B5 ❄️ FROZEN, finance-signed 2026-08-08
#           (04-docs/02-decisions/05-golden-tests.md lines 54-56)
# Tests:    this file
# Impacts:  06-backend/apps/ledger/posting.py 🔒 (the interface under test)
# ───────────────────────────────────────────────────────
"""GT-16 — the opening-balance cutover JE: DR AR 267.30 / CR opening-balance
clearing 267.30, dated 2026-08-31, immutable, idempotent.

B5 GT-16 verbatim
-----------------
  line 55: "Input: cutover 2026-08-31; imported account A-12103 opening buckets
            Current 84.20 / 31-60 62.10 / 61-90 0.00 / 90+ 121.00 (USD)."
  line 56: "Expected: `accounts.balance` = **267.30** (Sum buckets, exact - no
            recompute); ... one opening JE dated **2026-08-31**, source_type
            `opening_balance`: **DR AR 267.30 / CR opening-balance clearing
            267.30** - balanced pair written ONLY by the ledger posting service,
            immutable (corrections via J6, never edits); batch check: Sum of all
            opening JEs = Sum of all imported buckets (fixture batch: 1,213
            accounts -> clearing credit = total migrated AR $184,320.55);
            re-posting the same batch is idempotent (no second JE set)."

WHY THIS FILE IS DIFFERENT FROM ITS NEIGHBOURS. Every other test in this
directory is pure arithmetic against `apps.billing.rating_seam`, with no
database at all. **GT-16 is not an arithmetic case — it is a POSTING case**, and
the only way to check it is to put the entry into a real database through the
real service and read the rows back. So this one carries `django_db` and the
shared tenant fixtures, and it is the first file here that does.

⚠ **IF THIS FILE ERRORS WITH `assert not self._finalizers` BEFORE ANY TEST
RUNS, THE CAUSE IS NOT THIS FILE.** That signature was seen while writing it and
chased into the wrong explanation first, so the real one is recorded here:
**two pytest runs sharing the Postgres test database `test_smartbillhub`**. The
second run drops and recreates it under the first, `django_db_setup` fails
mid-session, and every test in whatever file is executing errors in fixture
setup — including files that have nothing to do with the change under test.

⚠ **THIS PARAGRAPH USED TO END BY TELLING YOU TO TYPE A DATABASE NAME OF YOUR
OWN, AND THAT IS WHY IT HAPPENED AGAIN ON 2026-08-30** — two lanes, fifty
minutes, no result. A mitigation that needs remembering is not a mitigation
(hard-won law 3). **`config/settings/base.py` now derives the test database name
from the checkout's own path**, so every worktree already has its own and
`--reuse-db` still reuses. Nothing to type:

    DJANGO_SETTINGS_MODULE=config.settings.local \\
      python -m pytest tests/golden/test_gt16_opening_journal_entry.py -q

`SBH_TEST_DB_NAME=test_smartbillhub` puts two runs back on one database
deliberately, which is now something a person does on purpose.

Recorded as DEF-054 in 12-governance/10-defect-log.csv, because a lane that
believes that error is its own will revert correct code to make it go away.

WHAT IS ASSERTED, AND WHAT B5 DOES NOT STATE
--------------------------------------------
Asserted: the four buckets sum to 267.30 · the entry is DR AR / CR
opening-balance clearing for exactly that figure · it is dated 2026-08-31 ·
`source_type` is `opening_balance` · it is written through
`apps.ledger.posting.post` and by nothing else · re-posting the same batch
writes no second JE set · the posted entry cannot be edited.

**NOT asserted — the $184,320.55 batch tie-out.** `10-scripts/03-golden-
verify.py` reports it NOT-CHECKABLE in exactly these words: *"the batch tie-out
($184,320.55 across 1,213 accounts) states no per-account fixture, so that sum
cannot be recomputed; only the single-account opening JE is verified."* The same
limit applies here — 1,213 per-account figures do not exist anywhere, and
inventing 1,212 of them to make a total come out would be a fixture that proves
the fixture. What IS checked is the PROPERTY the batch total depends on: a batch
of opening entries credits the clearing account with exactly the sum of the
balances it debited to AR, whatever the balances are. That property, applied to
1,213 real accounts, IS the 184,320.55 line — asserted here over a three-account
batch whose figures are named.

**NOT asserted — `accounts.balance` = 267.30 and the day-one aging report.**
Those are US-CUS-021/022's half of GT-16 and belong to `apps/customers`;
`account_opening_buckets` (B2 r9 #2) is not built, so there is no importer to
drive them. The BUCKETS are stated here as data, and their sum is checked
against B5's own stated balance, because that arithmetic is the input to the
entry this file does assert.

⚠ **NOTHING IN THE PRODUCT CALLS THIS PATH YET** (hard-won law 2). The cutover
importer that would own the posting key's `cutover:<batch>` composition does not
exist. This test drives the service directly, which makes the frozen contract
exercised rather than described — but it is a test, not a wired feature, and the
posting service's own docstring says so first.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest
from django.db import DatabaseError, transaction

from apps.ledger import chart, models, opening_balances, posting, selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = [pytest.mark.golden, pytest.mark.django_db]

# ── B5 GT-16 line 55: the four imported buckets, copied ─────────────────────
GT16_BUCKET_CURRENT = Decimal("84.20")
GT16_BUCKET_31_60 = Decimal("62.10")
GT16_BUCKET_61_90 = Decimal("0.00")
GT16_BUCKET_90_PLUS = Decimal("121.00")
GT16_BUCKETS = (
    GT16_BUCKET_CURRENT,
    GT16_BUCKET_31_60,
    GT16_BUCKET_61_90,
    GT16_BUCKET_90_PLUS,
)

# ── B5 GT-16 line 56: the expected figures, copied ──────────────────────────
GT16_BALANCE = Decimal("267.30")  # "`accounts.balance` = **267.30**"
GT16_CUTOVER = date(2026, 8, 31)  # "one opening JE dated **2026-08-31**"
GT16_SOURCE_TYPE = "opening_balance"  # "source_type `opening_balance`"
GT16_CURRENCY = "USD"  # "(USD)" — GT-16 is the one GT that states one

# B5 GT-16 line 55 names ONE account, A-12103. The batch cases below need more
# than one, and B5 names no others — so the two extra figures are declared here
# as FIXTURE SCAFFOLDING, not frozen values, and nothing asserts them against
# B5. What they exist for is the PROPERTY: Sum(clearing credits) = Sum(AR debits)
# over a batch, which is what the un-checkable 184,320.55 line actually claims.
BATCH_OTHER_BALANCES = (Decimal("1450.75"), Decimal("38.09"))

# BR-TEN-043 / the PO's OQ-107 ruling — the caller names the wall-clock moment
# and the book date separately. The cutover BOOK date is B5's 2026-08-31; the
# import ran the following morning, which is exactly the pair the ruling exists
# to keep distinct.
IMPORTED_AT = datetime(2026, 9, 1, 8, 0, tzinfo=dt_timezone.utc)

BATCH_ID = "0192f0aa-0000-7000-8000-00000000b47c"


def opening_entry_request(tenant, *, account_ref, balance):
    """One account's opening JE, exactly as GT-16 describes it.

    ⚠ **THIS FUNCTION USED TO COMPOSE THE ENTRY ITSELF, AND THAT MADE THE
    FROZEN TEST PROVE THE TEST (amended 2026-08-16, the US-LED-001 lane).**
    Forty lines of `PostingRequest` / `PostingLine` construction lived here —
    the designation lookups, the two lines, the `cutover:<batch>` key — and
    **there was no function anywhere in the product that did the same thing**.
    So GT-16 asserted that this file's arithmetic reached the books correctly,
    which was true and was not the claim the golden test is for.
    `apps/ledger/posting.py` filed exactly that row as *"a MISSING WRITER, not
    a missing contract"*.

    The composition now lives in `apps/ledger/opening_balances.py` and this
    delegates to it, so every figure below is asserted against the code an
    importer will call (US-CUS-021/022 — still unbuilt; the module says so on
    every result rather than only in prose).

    **The two accounts are still resolved BY DESIGNATION** (`accounts_receivable`
    and `opening_clearing`), never by the numbers 1200 and 3000 — US-LED-005
    lets a tenant renumber either one, and OQ-106 was raised precisely so that
    nothing in a posting path holds a code. That resolution moved with the rest
    of the composition; the assertion below still proves it lands on the right
    two accounts.

    The posting key is `opening_balance|<account>|cutover:<batch>`, which is how
    GT-16's *"idempotent per (batch, account)"* is expressed in the three-part
    shape. That composition is the ledger's, under B2 r13 #8's delegation of
    posting-service mechanics.
    """
    ar = selectors.gl_account_id_for_designation(chart.AR)
    clearing = selectors.gl_account_id_for_designation(chart.OPENING_CLEARING)
    assert ar and clearing, "the seeded chart is missing GT-16's two designations"

    return opening_balances.opening_entry_request(
        opening_balances.OpeningAccount(
            account_id=_account_for(tenant, account_ref).id,
            balance=balance,
            account_ref=account_ref,
        ),
        batch_id=BATCH_ID,
        cutover_on=GT16_CUTOVER,
        imported_at=IMPORTED_AT,
        currency=GT16_CURRENCY,
    )


def _account_for(tenant, account_ref):
    """A REAL customer account for `account_ref`, created once per test.

    ⚠ **THE SYNTHETIC uuid5 THIS FILE USED TO PASS NO LONGER WORKS, AND THE
    REASON IS A RULE RATHER THAN A NUISANCE.** A cutover entry carries
    BR-LED-001's `account_id` dimension — without it a migrated utility's
    brought-forward receivables sit in the AR control total and on nobody's
    customer row, which is DEF-127's shape and what the reports lane already
    reports about day-one ageing. `apps/ledger/posting._stamped` resolves the
    account → unit → premises chain at posting time and REFUSES an account it
    cannot walk (US-LED-002 TC-5), so a made-up id would prove that refusal
    instead of GT-16.
    """
    from apps.customers import models as customer_models

    from tests.test_us_met_helpers import make_premises, make_unit, staff_actor

    # A distinct email per account: `staff_actor` derives one from the ROLE, so
    # the three-account batch case below collided on `uq_users_tenant_email_ci`
    # when this file first delegated (measured, not predicted).
    actor = staff_actor(tenant, email=f"cutover-{account_ref.lower()}@brazosbendutilities.test")
    premises = make_premises(
        actor, address_line=f"{account_ref} St", services_available=["electric"]
    )
    unit = make_unit(actor, premises["id"], label="1", services=["electric"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        account_no=account_ref,
        status=customer_models.AccountStatus.objects.get(tenant=tenant, code="active"),
        account_type=customer_models.AccountType.objects.first(),
    )


def gl_totals(tenant, designation):
    account_id = selectors.gl_account_id_for_designation(designation)
    rows = models.JournalLine.objects.filter(tenant=tenant, ledger_account_id=account_id)
    debits = sum((row.amount for row in rows if row.side == models.SIDE_DEBIT), Decimal("0"))
    credits = sum((row.amount for row in rows if row.side == models.SIDE_CREDIT), Decimal("0"))
    return debits, credits


def test_gt16__the_four_buckets_sum_to_the_stated_balance():
    """B5 line 56: *"`accounts.balance` = 267.30 (Σ buckets, exact — no
    recompute)"*.

    Pure arithmetic on B5's own stated inputs, and the only figure in this file
    that is derived at all — it is the input to the entry, so if the four
    buckets did not add up, the JE below would be asserting the wrong total.
    """
    assert sum(GT16_BUCKETS) == GT16_BALANCE


def test_gt16__the_opening_je_is_dr_ar_267_30_cr_clearing_267_30(brazos, dana):
    """B5 line 56 verbatim: *"one opening JE dated 2026-08-31, source_type
    `opening_balance`: DR AR 267.30 / CR opening-balance clearing 267.30 —
    balanced pair written ONLY by the ledger posting service"*.

    Every clause of that sentence is a separate assertion below, including the
    last one: the entry is written by `posting.post` and the rows are read back
    out of the database rather than taken from what `post()` returned.
    """
    with tenant_ctx(brazos):
        result = posting.post(
            opening_entry_request(brazos, account_ref="A-12103", balance=GT16_BALANCE)
        )
        assert result.created is True
        assert (result.debits, result.credits) == (GT16_BALANCE, GT16_BALANCE)

        entry = models.JournalEntry.objects.get(pk=result.entry_id)
        assert entry.entry_date == GT16_CUTOVER
        assert entry.source_type == GT16_SOURCE_TYPE
        assert entry.currency == GT16_CURRENCY
        assert entry.status == models.JE_POSTED

        ar_debits, ar_credits = gl_totals(brazos, chart.AR)
        clearing_debits, clearing_credits = gl_totals(brazos, chart.OPENING_CLEARING)
        assert (ar_debits, ar_credits) == (GT16_BALANCE, Decimal("0"))
        assert (clearing_debits, clearing_credits) == (Decimal("0"), GT16_BALANCE)


def test_gt16__re_posting_the_same_batch_is_idempotent(brazos, dana):
    """B5 line 56: *"re-posting the same batch is idempotent (no second JE
    set)"*, and US-LED-001 TC-3: *"re-posting the batch is idempotent — no
    second JE set (LE-10)"*.

    A cutover import is the most re-run thing in the product: it fails halfway,
    somebody fixes two rows in the source file and runs it again. A second JE
    set would double the migrated AR of an entire utility on day one.
    """
    with tenant_ctx(brazos):
        request = opening_entry_request(brazos, account_ref="A-12103", balance=GT16_BALANCE)
        first = posting.post(request)
        second = posting.post(request)

        assert first.created is True and second.created is False
        assert second.entry_id == first.entry_id
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == 1
        assert models.JournalLine.objects.filter(tenant=brazos).count() == 2
        ar_debits, _ = gl_totals(brazos, chart.AR)
        assert ar_debits == GT16_BALANCE  # not 534.60


def test_gt16__a_batch_credits_clearing_with_exactly_what_it_debited_to_ar(brazos, dana):
    """The property behind the un-checkable line.

    B5's *"Σ of all opening JEs = Σ of all imported buckets (1,213 accounts →
    clearing credit = 184,320.55)"* cannot be recomputed — the harness says so
    in as many words, because no per-account fixture exists. What can be
    checked, and is the whole content of that claim, is that a BATCH of opening
    entries leaves AR and clearing exactly equal whatever the balances are.

    Three accounts here: GT-16's own 267.30 plus two scaffolding figures that
    are named as scaffolding and asserted against nothing in B5.
    """
    balances = (GT16_BALANCE, *BATCH_OTHER_BALANCES)
    with tenant_ctx(brazos):
        for index, balance in enumerate(balances):
            posting.post(
                opening_entry_request(brazos, account_ref=f"A-1210{index}", balance=balance)
            )
        ar_debits, ar_credits = gl_totals(brazos, chart.AR)
        clearing_debits, clearing_credits = gl_totals(brazos, chart.OPENING_CLEARING)

        assert ar_debits == sum(balances)
        assert clearing_credits == ar_debits
        assert (ar_credits, clearing_debits) == (Decimal("0"), Decimal("0"))
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == len(balances)


def test_gt16__the_opening_entry_is_immutable_and_corrections_are_new_rows(brazos, dana):
    """B5 line 56: *"immutable (corrections via J6, never edits)"*.

    Two halves. The database refuses the edit outright (ledger/0002's
    append-only trigger — Postgres only, so on SQLite this half is skipped by
    the exception it does not raise). And the lawful correction path is a NEW
    linked mirror, which is asserted everywhere: the original survives, the
    mirror reverses it, and both are in the books forever.
    """
    with tenant_ctx(brazos):
        result = posting.post(
            opening_entry_request(brazos, account_ref="A-12103", balance=GT16_BALANCE)
        )
        from django.db import connection

        if connection.vendor == "postgresql":
            with pytest.raises(DatabaseError), transaction.atomic():
                models.JournalEntry.objects.filter(pk=result.entry_id).update(
                    entry_date=date(2026, 9, 30)
                )

        mirror = posting.reverse_entry(
            result.entry_id,
            posting_key="opening_balance|A-12103|cutover_reversed",
            entry_date=date(2026, 9, 1),
            posted_at=IMPORTED_AT,
        )
        assert mirror.created is True
        original = models.JournalEntry.objects.get(pk=result.entry_id)
        assert original.entry_date == GT16_CUTOVER  # untouched
        ar_debits, ar_credits = gl_totals(brazos, chart.AR)
        assert ar_debits == ar_credits == GT16_BALANCE  # net zero, both rows present


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-001@c7a1f30 (sources: 04-docs/02-decisions/05-golden-tests.md GT-16 lines 54-56 ❄️ finance-signed 2026-08-08 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-10 · 04-docs/05-modules/09-ledger/06-epics/EP-LED-01-posting-consumption.md US-LED-001 TC-3 · 04-docs/02-decisions/02-database-design-brief.md Addendum r9 #3 (source_type += 'opening_balance') · 10-scripts/03-golden-verify.py GT-16 spec + its NOT-CHECKABLE note)
# generated: 2026-08-11 by Eng-Lead (W5 ledger posting-service lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved RED before green — with the posting key removed from the
#         request the idempotency case wrote a second JE set and doubled AR to
#         534.60; quoted verbatim in 12-governance/09-human-review-ledger.md
# exceptions: this golden file touches the DATABASE, unlike every other file in
#         this directory — GT-16 is a POSTING case and there is no honest way to
#         check "one balanced JE dated 2026-08-31" without writing and reading
#         one · the $184,320.55 / 1,213-account batch tie-out is NOT asserted:
#         B5 states no per-account fixture and 10-scripts/03-golden-verify.py
#         already reports it NOT-CHECKABLE for that exact reason; the PROPERTY it
#         depends on (Σ clearing credits = Σ AR debits over a batch) is asserted
#         over a named three-account batch, two of whose balances are declared
#         fixture scaffolding · `accounts.balance` = 267.30 and the day-one aging
#         report are US-CUS-021/022's half and are NOT asserted — the buckets are
#         stated and their sum checked, because that sum is the input to the JE ·
#         the posting key's `cutover:<batch>` composition is this lane's, not a
#         ruling; the importer that will own it does not exist
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
