# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data) · US-CUS-021 (opening
#           balances as AGED BUCKETS) · US-CUS-022 (the balanced AR↔clearing
#           handoff)   Screens: S81 (the Imports tab) · S17 (the Accounts KPI
#           strip) · S56 (the entries this posts)
# Change:   CR-030 W1 task 1.23 — the demo seed for the account import
#           (B18 §5.9.6 + §5.9.3a)
# Rules:    BR-TEN-057 (`is_sample` on the owning row) · BR-TEN-063 (idempotent)
#           · BR-CUS-048 (four aged buckets) · BR-CUS-049 (balanced opening JEs
#           at cutover, immutable) · BR-MET-096 (the ONE ETL runner) ·
#           CLAUDE.md rule 2 (money, never float) · rule 5 (balanced pairs, the
#           posting service is the sole writer) · rule 6 (idempotency)
# Golden:   GT-16 — B5 ❄️ FROZEN, finance-signed 2026-08-08
# Tests:    this file
# Impacts:  apps/metering/sample_data.py · apps/customers/sample_data.py
# ───────────────────────────────────────────────────────
"""CR-030 W1 T1.23 — the three `[shot]` import runs and ❄️ GT-16's opening books.

WHAT THIS FILE ASSERTS, AND WHY EACH FIGURE IS WHERE IT IS
-----------------------------------------------------------
Every number below is COPIED from a signed document with the line quoted beside
it. Nothing here recomputes a frozen figure, and if the product ever produces a
different one the CODE is wrong — a B5 figure moves only by a finance re-sign
through HUMAN-GUIDE §6 (CLAUDE.md).

  * **B18 §5.9.6** — the three runs the prototype draws on Accounts → Imports:
    `RUN-2801` (88 rows, clean), `RUN-2814` (**1,251 in / 1,247 loaded / 4
    rejected** — the migration), `RUN-2822` (312 / 310 / 2, rejects open).
    §5.9.6's own sentence: *"`RUN-2814` loads 1,247 — the exact figure the
    Accounts KPI strip reports. The two must be the same number in the fixture
    or the demo contradicts itself."*
  * **B5 GT-16 line 55** ❄️ — `A-12103`, cutover **2026-08-31**, buckets
    **84.20 / 62.10 / 0.00 / 121.00**.
  * **B5 GT-16 line 56** ❄️ — balance **267.30** (Σ buckets, exact), ONE opening
    JE dated 2026-08-31, **DR AR 267.30 / CR opening-balance clearing 267.30**,
    written only by the posting service, idempotent per (batch, account).
  * **B18 §5.9.3a** — day-one overdue **183.10**, and the batch tie-out
    **1,213 accounts → $184,320.55**, which is the Accounts tab's
    `OUTSTANDING $184,320` tile (§5.1.1).

⚠ **THE 1,213-ACCOUNT BATCH IS NOT POSTED, AND THAT IS A RULING, NOT A GAP.**
The Product Owner ruled on 2026-08-11 (decision log): *"The opening-balance
import verifies a single account only; the 1,213-account batch total stays
illustrative."* `10-scripts/03-golden-verify.py` says the same in its own
words — *"the batch tie-out ($184,320.55 across 1,213 accounts) states no
per-account fixture, so that sum cannot be recomputed"* — and
`tests/golden/test_gt16_opening_journal_entry.py` records that inventing 1,212
figures to make the total come out *"would be a fixture that proves the
fixture"*. So this file asserts the tie-out TWO ways, which together are the
whole of what the frozen line claims:

  1. the figure is RECORDED, verbatim, on the run that declared it, so the
     Imports tab and the `OUTSTANDING` tile read one number and not two;
  2. the PROPERTY it rests on — Σ AR debits = Σ opening-clearing credits — is
     proved against the entry that IS posted, on GT-16's own account, from the
     real ledger rows.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.customers import models as customers_models
from apps.customers import sample_data as customers_sample
from apps.ledger import chart, models as ledger_models, selectors as ledger_selectors
from apps.metering import import_runs
from apps.metering import models as metering_models
from apps.metering import sample_data as metering_sample
from apps.rating import sample_data as rating_sample

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import tenant_ctx
from tests.test_us_met_helpers import (  # noqa: F401 — brazos/dana are fixtures
    brazos,
    dana,
)

pytestmark = pytest.mark.django_db

# ── B18 §5.9.6, the three `[shot]` rows ─────────────────────────────────────
SHOT_RUNS = {"RUN-2801", "RUN-2814", "RUN-2822"}
MIGRATION_RUN_NO = "RUN-2814"
MIGRATION_ROWS_IN = 1251
MIGRATION_LOADED = 1247  # "RUN-2814 loads 1,247 — the exact figure the KPI reports"
MIGRATION_REJECTED = 4

# ── B5 GT-16 lines 55–56, ❄️ FROZEN, finance-signed 2026-08-08 ──────────────
GT16_ACCOUNT_NO = "A-12103"
GT16_CUTOVER = date(2026, 8, 31)
GT16_FOUR_BUCKETS = {
    "current": Decimal("84.20"),
    "31_60": Decimal("62.10"),
    "61_90": Decimal("0.00"),
    "90_plus": Decimal("121.00"),
}
GT16_BALANCE = Decimal("267.30")
GT16_OVERDUE_DAY_ONE = Decimal("183.10")  # B18 §5.9.3a: 62.10 + 0.00 + 121.00
GT16_SOURCE_TYPE = "opening_balance"

# ── B18 §5.9.3a / B5 GT-16 line 56 — the batch tie-out ──────────────────────
BATCH_ACCOUNTS = 1213
BATCH_MIGRATED_AR = Decimal("184320.55")


@pytest.fixture()
def seeded(brazos, dana):
    """The sample plant in the orchestrator's own order — rating (the plans a
    unit must carry before an account may activate, BR-MET-040), then metering
    (the places and the import history), then customers (the accounts).

    Through each module's REAL seam, never a reimplementation, so this test
    cannot drift from what a tenant actually receives.
    """
    with tenant_ctx(brazos):
        rating_sample.seed_sample_records(dana)
        metering_sample.seed_sample_records(dana)
        customers_sample.seed_sample_records(dana)
    return brazos, dana


def _runs(tenant):
    return metering_models.ImportRun.objects.filter(
        tenant_id=tenant.id, target=import_runs.TARGET_ACCOUNTS
    )


def _gt16_account(tenant):
    return customers_models.Account.objects.get(tenant_id=tenant.id, account_no=GT16_ACCOUNT_NO)


def _opening_entry(tenant):
    """❄️ GT-16's OWN opening entry, read from the ledger's own rows.

    ⚠ **NARROWED 2026-08-24 (CR-030 W2 task 2.10), and the figures below are
    UNCHANGED.** This read `objects.get(source_type=...)` — *the* one opening
    entry — which was true while `A-12103` was the only migrated account on the
    tenant. The PO authorised B18 §5.1.5's eight `[shot]` account shapes that
    day (*"so add them"*) and nine of them carry opening buckets, so the tenant
    now holds ten opening entries and a bare `get()` raises
    `MultipleObjectsReturned` before it can assert anything.
    **`source_id` IS the account id** (`ledger.opening_balances._request_for`),
    so naming GT-16's account is how this file keeps asserting about GT-16 and
    nothing else — the frozen 267.30 / 84.20 / 62.10 / 0.00 / 121.00 and the
    2026-08-31 cutover are untouched.
    """
    return ledger_models.JournalEntry.objects.get(
        tenant_id=tenant.id,
        source_type=GT16_SOURCE_TYPE,
        source_id=_gt16_account(tenant).id,
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · B18 §5.9.6 — the three runs the Imports tab draws
# ══════════════════════════════════════════════════════════════════════════


def test_the_three_shot_runs_are_seeded_on_the_accounts_target(seeded):
    """§5.9.4's KPI strip opens with `RUNS 3 · since migration`.

    RED before this lane: `assert set() == {'RUN-2801', 'RUN-2814', 'RUN-2822'}`
    — no seeder in the repository had ever written an `import_runs` row, so the
    Imports tab of a freshly seeded demo was empty on every tenant.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        runs = _runs(tenant)
        assert set(runs.values_list("run_no", flat=True)) == SHOT_RUNS
        assert runs.count() == 3, "§5.9.4's `RUNS 3` tile counts these rows"
        # BR-TEN-057 — the tag on the OWNING row, so BR-TEN-061 can take them
        # away again (B15 §15 requires exactly this of the seeded runs).
        assert runs.filter(is_sample=False).count() == 0


def test_run_2814_loads_the_1247_the_accounts_kpi_strip_reports(seeded):
    """B18 §5.9.6: *"RUN-2814 loads 1,247 — the exact figure the Accounts KPI
    strip reports. The two must be the same number in the fixture or the demo
    contradicts itself."* §5.1.1's `ACCOUNTS 1,247` is that number."""
    tenant, _ = seeded
    with tenant_ctx(tenant):
        run = _runs(tenant).get(run_no=MIGRATION_RUN_NO)
        assert run.counts["loaded"] == MIGRATION_LOADED == 1247
        assert run.counts["in"] == MIGRATION_ROWS_IN == 1251
        assert run.counts["rejected"] == MIGRATION_REJECTED == 4
        assert run.file_name == "customer_accounts_migration.csv"
        assert run.status == "loaded"


def test_every_seeded_run_reconciles_its_own_counts(seeded):
    """`ImportRun.counts`'s own TC-3 discipline: *"in − duplicates_dropped −
    skipped = forward"*, and loaded + rejected = forward. A denormalised count
    that cannot be checked against its addends is a number nobody can defend."""
    tenant, _ = seeded
    with tenant_ctx(tenant):
        for run in _runs(tenant):
            counts = run.counts
            assert (
                counts["in"] - counts["duplicates_dropped"] - counts["skipped"] == counts["forward"]
            ), run.run_no
            assert counts["loaded"] + counts["rejected"] == counts["forward"], run.run_no


def test_the_rejects_open_run_carries_rows_the_fix_action_can_act_on(seeded):
    """§5.9.4: `REJECTED 6 · 2 still open`, and the row action `🔧 fix on a run
    with open rejects`. A row action with nothing to act on is dead UI —
    hard-won law 2, which is why the two open rejects are real rows."""
    tenant, _ = seeded
    with tenant_ctx(tenant):
        run = _runs(tenant).get(run_no="RUN-2822")
        rejects = metering_models.ImportRunRow.objects.filter(run=run, outcome="rejected")
        assert rejects.count() == 2
        assert all(row.problem and row.fix_hint for row in rejects), (
            "a reject the operator cannot act on is DEF-016's silent drop with a "
            "row number attached"
        )
        assert rejects.filter(is_sample=False).count() == 0  # BR-TEN-057


# ══════════════════════════════════════════════════════════════════════════
# 2 · ❄️ GT-16 — the four aged buckets and the 267.30
# ══════════════════════════════════════════════════════════════════════════


def test_gt16_account_carries_the_four_frozen_buckets(seeded):
    """❄️ B5 GT-16 line 55: *"imported account A-12103 opening buckets Current
    84.20 / 31–60 62.10 / 61–90 0.00 / 90+ 121.00 (USD)"*, as of cutover
    **2026-08-31**.

    BR-CUS-048 (PO AC-3, option B): FOUR AGED BANDS, because one figure has no
    age — lump-sum and invoice-level were explicitly rejected. All four are
    written, including the 0.00: a band that is genuinely nil is a different
    fact from a row with no position at all.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        account = _gt16_account(tenant)
        buckets = customers_models.AccountOpeningBucket.objects.filter(account=account)
        assert buckets.count() == 4
        assert {row.bucket: row.amount for row in buckets} == {
            customers_models.AccountOpeningBucket.BUCKET_CURRENT: GT16_FOUR_BUCKETS["current"],
            customers_models.AccountOpeningBucket.BUCKET_31_60: GT16_FOUR_BUCKETS["31_60"],
            customers_models.AccountOpeningBucket.BUCKET_61_90: GT16_FOUR_BUCKETS["61_90"],
            customers_models.AccountOpeningBucket.BUCKET_90_PLUS: GT16_FOUR_BUCKETS["90_plus"],
        }
        assert {row.as_of for row in buckets} == {GT16_CUTOVER}
        # Money is Decimal on every hop (CLAUDE.md rule 2) — a float here would
        # make 84.20 + 62.10 + 121.00 read 267.29999999999995.
        assert all(isinstance(row.amount, Decimal) for row in buckets)
        assert buckets.filter(is_sample=False).count() == 0  # BR-TEN-057


def test_gt16_buckets_sum_to_the_frozen_267_30_and_so_does_the_cached_balance(seeded):
    """❄️ B5 GT-16 line 56: *"`accounts.balance` = **267.30** (Σ buckets, exact
    — no recompute)"*.

    Both halves are asserted because they are two different claims: the SUM of
    the four rows, and the CACHE `create_from_import` wrote from the same
    position object. Two derivations of one number is how they come to disagree.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        account = _gt16_account(tenant)
        buckets = customers_models.AccountOpeningBucket.objects.filter(account=account)
        assert (
            sum((row.amount for row in buckets), Decimal("0")) == GT16_BALANCE == Decimal("267.30")
        )
        assert account.balance == GT16_BALANCE


def test_gt16_day_one_overdue_is_the_183_10_late_fees_are_based_on(seeded):
    """B18 §5.9.3a: *"overdue day one = 62.10 + 0.00 + 121.00 = 183.10 ← the
    late-fee base (GT-8)"*. A lump-sum import would land all of it at `Current`
    and this figure would be 0.00 for a quarter."""
    tenant, _ = seeded
    with tenant_ctx(tenant):
        account = _gt16_account(tenant)
        overdue = sum(
            (
                row.amount
                for row in customers_models.AccountOpeningBucket.objects.filter(account=account)
                if row.bucket in customers_models.AccountOpeningBucket.OVERDUE_BUCKETS
            ),
            Decimal("0"),
        )
        assert overdue == GT16_OVERDUE_DAY_ONE == Decimal("183.10")


def test_the_migrated_account_is_attributed_to_the_migration_run(seeded):
    """The buckets cite the run that brought them in, and it is `RUN-2814` —
    the same batch the opening entry is keyed to. One id, not two spellings."""
    tenant, _ = seeded
    with tenant_ctx(tenant):
        run = _runs(tenant).get(run_no=MIGRATION_RUN_NO)
        buckets = customers_models.AccountOpeningBucket.objects.filter(
            account=_gt16_account(tenant)
        )
        assert {str(row.import_run_id) for row in buckets} == {str(run.id)}


# ══════════════════════════════════════════════════════════════════════════
# 3 · ❄️ GT-16 — the balanced opening entry, and the batch tie-out
# ══════════════════════════════════════════════════════════════════════════


def test_the_opening_entry_is_dr_ar_267_30_cr_clearing_267_30_at_cutover(seeded):
    """❄️ B5 GT-16 line 56: *"one opening JE dated **2026-08-31**, source_type
    `opening_balance`: **DR AR 267.30 / CR opening-balance clearing 267.30** —
    balanced pair written ONLY by the ledger posting service"*.

    Both GL accounts are resolved BY DESIGNATION and never by the literals 1200
    and 3000 (US-LED-005 / OQ-106 — a tenant may renumber their chart).
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        entry = _opening_entry(tenant)
        assert entry.entry_date == GT16_CUTOVER == date(2026, 8, 31)
        lines = list(ledger_models.JournalLine.objects.filter(journal_entry=entry))
        assert len(lines) == 2, "a balanced PAIR, never a plugged single line"

        ar_id = str(ledger_selectors.gl_account_id_for_designation(chart.AR))
        clearing_id = str(ledger_selectors.gl_account_id_for_designation(chart.OPENING_CLEARING))
        by_side = {line.side: line for line in lines}
        assert str(by_side[ledger_models.SIDE_DEBIT].ledger_account_id) == ar_id
        assert str(by_side[ledger_models.SIDE_CREDIT].ledger_account_id) == clearing_id
        assert by_side[ledger_models.SIDE_DEBIT].amount == GT16_BALANCE
        assert by_side[ledger_models.SIDE_CREDIT].amount == GT16_BALANCE


def test_the_batch_ties_out_debits_equal_credits(seeded):
    """❄️ B5 GT-16 line 56's batch check — *"Σ of all opening JEs = Σ of all
    imported buckets"* — read off the real journal lines.

    THIS IS THE PROPERTY THE $184,320.55 LINE ACTUALLY CLAIMS. Applied to
    1,213 real accounts it IS that number; applied to the one account whose
    per-account figures B5 states, it is 267.30. The seed does not manufacture
    the other 1,212 (PO ruling 2026-08-11 — the batch total *"stays
    illustrative"*), so the property is what is proved.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        # ⚠ **SCOPED TO ❄️ GT-16's OWN ENTRY 2026-08-24 (CR-030 W2 task 2.10).**
        # The property under test is *"Σ opening JEs = Σ imported buckets"* for
        # the account B5 states per-account figures for. Since B18 §5.1.5's
        # eight `[shot]` shapes were authorised (PO: *"so add them"*) the
        # tenant's `opening_balance` lines also carry THEIR opening positions,
        # and a tenant-wide sum would assert 10,368.45 == 267.30 — a broken
        # test, not a broken tie-out. **The frozen figure is unchanged**, and
        # the balanced-pair property still holds line by line for every entry:
        # `post_opening_batch` refuses a batch that does not tie.
        lines = ledger_models.JournalLine.objects.filter(
            tenant_id=tenant.id,
            source_type=GT16_SOURCE_TYPE,
            journal_entry__source_id=_gt16_account(tenant).id,
        )
        debits = sum(
            (line.amount for line in lines if line.side == ledger_models.SIDE_DEBIT),
            Decimal("0"),
        )
        credits = sum(
            (line.amount for line in lines if line.side == ledger_models.SIDE_CREDIT),
            Decimal("0"),
        )
        assert debits == credits, "the batch refuses success unless the two sides agree"
        assert debits == GT16_BALANCE


def test_the_migration_run_records_the_frozen_184320_55_tie_out(seeded):
    """❄️ B5 GT-16 line 56 / B18 §5.9.3a: *"BATCH TIE-OUT: 1,213 accounts → Σ =
    $184,320.55"*, and *"the Accounts tab's `OUTSTANDING` tile reads $184,320
    … the prototype figure and the finance-signed golden are the same number."*

    Recorded on the run that declared it, in the SAME two count keys a real
    accounts load writes (`_load_accounts_rows`), so the Imports tab, the
    receipt and the KPI tile read one number rather than three.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        counts = _runs(tenant).get(run_no=MIGRATION_RUN_NO).counts
        assert counts["with_opening_balance"] == BATCH_ACCOUNTS == 1213
        assert Decimal(counts["opening_ar"]) == BATCH_MIGRATED_AR == Decimal("184320.55")
        # The tile is displayed at 2dp and rounds to the shot's $184,320
        # (CLAUDE.md rule 2 — stored 4, displayed 2).
        assert int(BATCH_MIGRATED_AR) == 184320


# ══════════════════════════════════════════════════════════════════════════
# 4 · BR-TEN-063 / hard rule 6 — a replay writes nothing
# ══════════════════════════════════════════════════════════════════════════


def test_the_seed_is_idempotent_and_a_replay_doubles_nothing(seeded):
    """BR-TEN-063 and ❄️ GT-16's own *"re-posting the same batch is idempotent
    (no second JE set)"*.

    Two guards, and both matter: the run rows and the account are skipped on
    their stable keys, and the ledger's posting key
    (`opening_balance|<account>|cutover:<batch>`) makes a re-post a no-op. A
    seeder that doubled a utility's opening receivables could not be repaired —
    a posted entry cannot be edited (hard rule 4).
    """
    tenant, actor = seeded
    with tenant_ctx(tenant):
        before = {
            "runs": _runs(tenant).count(),
            "rows": metering_models.ImportRunRow.objects.filter(
                tenant_id=tenant.id, is_sample=True
            ).count(),
            "accounts": customers_models.Account.objects.filter(tenant_id=tenant.id).count(),
            "buckets": customers_models.AccountOpeningBucket.objects.filter(
                tenant_id=tenant.id
            ).count(),
            "entries": ledger_models.JournalEntry.objects.filter(
                tenant_id=tenant.id, source_type=GT16_SOURCE_TYPE
            ).count(),
            "lines": ledger_models.JournalLine.objects.filter(
                tenant_id=tenant.id, source_type=GT16_SOURCE_TYPE
            ).count(),
        }
        metering_sample.seed_sample_records(actor)
        customers_sample.seed_sample_records(actor)
        after = {
            "runs": _runs(tenant).count(),
            "rows": metering_models.ImportRunRow.objects.filter(
                tenant_id=tenant.id, is_sample=True
            ).count(),
            "accounts": customers_models.Account.objects.filter(tenant_id=tenant.id).count(),
            "buckets": customers_models.AccountOpeningBucket.objects.filter(
                tenant_id=tenant.id
            ).count(),
            "entries": ledger_models.JournalEntry.objects.filter(
                tenant_id=tenant.id, source_type=GT16_SOURCE_TYPE
            ).count(),
            "lines": ledger_models.JournalLine.objects.filter(
                tenant_id=tenant.id, source_type=GT16_SOURCE_TYPE
            ).count(),
        }
        assert before == after
        # ⚠ **AMENDED 2026-08-24 (CR-030 W2 task 2.10): `== 1` BECAME "GT-16's
        # OWN, AND EXACTLY ONE".** The claim being made is ❄️ GT-16's — *"no
        # second JE set"* — and it was expressed as a tenant-wide count only
        # because `A-12103` was the tenant's only migrated account. B18 §5.1.5's
        # eight `[shot]` shapes (PO 2026-08-24, *"so add them"*) carry opening
        # balances of their own, keyed to their own batch
        # (`sample_fixture.CR030_OPENING_BATCH_KEY`) so a replay of one can
        # never touch the other. A count of ten proves nothing about GT-16;
        # this does.
        assert (
            ledger_models.JournalEntry.objects.filter(
                tenant_id=tenant.id,
                source_type=GT16_SOURCE_TYPE,
                source_id=_gt16_account(tenant).id,
            ).count()
            == 1
        ), "❄️ GT-16: no second JE set"
        assert _gt16_account(tenant).balance == GT16_BALANCE


def test_the_cutover_seat_adds_no_phantom_missing_read_to_the_ready_month(seeded):
    """The migrated account's unit carries NO service point, deliberately.

    A 49th unit with a service point and no read behind it is a phantom
    missing-read in the READY-TO-RUN July batch, which is the acceptance test
    the fixture spec exists to protect (`apps/assets/sample_data.py` makes the
    same argument for leaving the net meter in inventory). It is also the
    truthful shape: BR-CUS-047's migration order ends *"→ Accounts → opening
    reads"*, and this account's first read has not been taken.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        unit = metering_models.Unit.objects.get(
            tenant_id=tenant.id, unit_no=metering_sample.CUTOVER_UNIT_NO
        )
        assert (
            metering_models.ServicePoint.objects.filter(unit=unit).count() == 0
        ), "the cutover seat must stay out of the read/bill scope until its opening read"
        assert _gt16_account(tenant).unit_id == unit.id


# ── Lifecycle ─────────────────────────────────────────────
# packet: 04-docs/02-decisions/18-cr030-onboarding-design.md §5.9.3a/§5.9.4/§5.9.6 +
#         04-docs/02-decisions/05-golden-tests.md GT-16 ❄️ +
#         12-governance/02-decision-log.md 2026-08-11 (the batch total stays illustrative)
# generated: 2026-08-24 by story-coder (CR-030 W1 T1.23 demo-seed lane)
# checklist: A✔ B=n/a(a seed + its test; the S81 tab that renders it is task 1.10) C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff · black · this file
# exceptions: the 1,213-account / $184,320.55 batch is RECORDED on RUN-2814 and NOT posted as
#         1,213 journal entries — PO ruling 2026-08-11 ("the opening-balance import verifies a
#         single account only; the 1,213-account batch total stays illustrative") and
#         10-scripts/03-golden-verify.py reports the same line NOT-CHECKABLE. What is proved from
#         real rows is the PROPERTY that total rests on: Σ AR debits = Σ clearing credits.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
