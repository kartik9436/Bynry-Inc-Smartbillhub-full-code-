# ── Trace ──────────────────────────────────────────────
# Story:    CR-060 C20 / task T7f — post depreciation from the asset's own
#           figures. Screens: S49 (the registry the figures come from) · S56
# Rules:    BR-LED-793 (how depreciation is posted — NEW 2026-09-02) ·
#           BR-AST-047 (straight-line book value — the ONE computation, in
#           assets, borrowed and never re-implemented) · BR-LED-025 (nothing
#           over 2 dp posts) · BR-TEN-038 (a closed period is never posted
#           into) · BR-TEN-043 (posted_at is an INPUT) · CLAUDE.md rules 1-7
# Golden:   CR-028 AST-W4's pinned straight-line figures — $164.00 · 20 years ·
#           installed 12 Mar 2024 → accumulated $19.8167 at 16 Aug 2026, the
#           figure `tests/test_cr028_valuation.py` already ratifies. Every
#           number below is a DIFFERENCE of two of those, never a new formula.
# ───────────────────────────────────────────────────────
"""The depreciation the screen has always shown, put into the books.

════════════════════════════════════════════════════════════════════════════
THE WORKED FIGURE THIS FILE PINS — the one a reviewer signs (CR-060 T19)
════════════════════════════════════════════════════════════════════════════
Brazos Bend owns four meters, each bought for **$164.00** on **12 March 2024**
with a **20-year** life. The assets module has computed their book value since
CR-028 and **nothing has ever posted it** (CR-060 §4).

  * **One meter, over August 2026.** Accumulated depreciation at **31 August**
    is 164.00 × 29 ÷ 240 = **$19.8167**; at **31 July** — the day before the
    period — it is 164.00 × 28 ÷ 240 = **$19.1333**. The month's charge is the
    difference: **$0.6834**.
  * **Four meters.** 4 × 0.6834 = 2.7336, rounded ONCE, half-up, on the sum:

        DR 5700 Depreciation expense              2.73
        CR 1730 Accumulated depreciation — meters       2.73

  * **AND IT DOES NOT COME BACK.** The entry is `type='standard'`, so the day-1
    accrual sweep leaves it alone. A depreciation entry that reversed itself
    would leave the plant at its purchase cost forever — CR-060 §5's **$40,000**
    truck error arriving from the other direction.

  * **A METER WITH NO PURCHASE COST IS COUNTED, NEVER CHARGED AT ZERO.** Assets
    answers `None` for it — *"never a fabricated $0.00"* — so a utility with
    fifty unpriced meters sees fifty in the count rather than a small charge
    that looks finished.

════════════════════════════════════════════════════════════════════════════
PROVED RED BEFORE GREEN — THREE GUARDS, EACH MEASURED, NO LIVE FILE MUTATED
════════════════════════════════════════════════════════════════════════════
Every sabotage was applied through `monkeypatch` so no shipped file was edited
to produce a failure (DEF-3101's discipline). Quoted as seen:

  **1 · The entry type changed from `standard` to `accrual`.** The existing
  day-1 sweep then reversed the charge on 1 September, `1730` netted to
  **0.00** and the plant sat at its full purchase cost with a depreciation
  expense that cancelled itself. Measured: after the sweep,
  `AssertionError: assert Decimal('0.00') == Decimal('-2.73')` on accumulated
  depreciation. **This is the single most important line in the module** and it
  is one word.

  **2 · The movement replaced by the closing accumulated figure** — i.e.
  posting `accumulated(period_end)` instead of
  `accumulated(end) − accumulated(start−1)`. August's charge became
  **$79.27** instead of **$2.73**, twenty-nine months of depreciation posted
  into one month. Measured:
  `AssertionError: assert Decimal('79.27') == Decimal('2.73')`.

  **3 · The period-scoped posting key replaced with a per-press one.** Pressing
  the trigger twice charged **$5.46** and left `1730` at twice the plant's real
  accumulated depreciation. Measured:
  `AssertionError: assert Decimal('5.46') == Decimal('2.73')`.

════════════════════════════════════════════════════════════════════════════
POSTGRESQL — CLAUDE.md hard-won law 14
════════════════════════════════════════════════════════════════════════════
The charge posts inside one transaction alongside a chart top-up that MINTS an
account (`5700`), and the replay guard leans on
`uq_journal_entries_posting_key`. SQLite has no aborted-transaction state, so a
green run there is not by itself the proof.

**RUN, AND MEASURED: 10 passed on PostgreSQL 16 with a database built from every
migration (`--create-db`)** — including the top-up that inserts `5700` inside the
posting transaction, which is the statement SQLite could never fail on:

    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL=postgres://... SBH_TEST_DB_NAME=test_sbh_cr060b \\
    JOBS_EAGER=false pytest tests/test_cr060_t7f_depreciation.py --create-db

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE DOES NOT TOUCH
════════════════════════════════════════════════════════════════════════════
**No ❄️ frozen figure moves and no new arithmetic is invented.** $19.8167 is
`tests/test_cr028_valuation.py`'s already-ratified figure and is transcribed
here; every charge below is a subtraction of two such figures. B4 and B5 are not
opened. `5700` is an UNSIGNED account (`chart.PENDING_FINANCE_RE_SIGN_MATCHING`)
and this file asserts that it says so.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.ledger import (
    chart,
    close,
    depreciation,
    manual_je,
    models as ledger_models,
    selectors,
    services as ledger_services,
)

from tests.cost_of_service_fixtures import (
    AUGUST_END,
    AUGUST_START,
    JULY_CLOSED_AT,
    JULY_END,
    JULY_START,
    with_monthly_fiscal_year,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    dana,
    lonestar,
    make_asset,
    marcus,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

# ── the worked month, transcribed ──────────────────────────────────────────
POSTED_AT = datetime(2026, 9, 1, 9, 0, tzinfo=dt_timezone.utc)
SWEPT_AT = datetime(2026, 9, 1, 9, 5, tzinfo=dt_timezone.utc)
SEPTEMBER_START = date(2026, 9, 1)
SEPTEMBER_END = date(2026, 9, 30)

#: CR-028 AST-W4's worked meter, verbatim.
METER_COST = "164.00"
METER_LIFE_YEARS = 20
METER_INSTALLED = "2024-03-12"

#: `tests/test_cr028_valuation.py`'s own ratified figure at 29 months, and the
#: 28-month figure the period opens at. TRANSCRIBED, not recomputed — a fixture
#: that re-derived them would agree with a broken implementation.
ACCUMULATED_AT_29_MONTHS = Decimal("19.8167")  # 164.00 × 29 / 240
ACCUMULATED_AT_28_MONTHS = Decimal("19.1333")  # 164.00 × 28 / 240
ONE_METER_AUGUST = ACCUMULATED_AT_29_MONTHS - ACCUMULATED_AT_28_MONTHS  # 0.6834

METER_COUNT = 4
#: 4 × 0.6834 = 2.7336, rounded ONCE on the sum, half-up, at this finalization.
AUGUST_CHARGE = Decimal("2.73")


def brazos_ready(tenant, actor):
    admin = (
        actor
        if getattr(actor, "role", None) == "system_admin"
        else staff_actor(tenant, "system_admin", f"setup-{tenant.subdomain}@brazosbendutilities.test")
    )
    with_monthly_fiscal_year(admin)
    return admin


def valued_meters(actor, count=METER_COUNT, **overrides):
    """`count` copies of CR-028's worked meter, through the REAL asset service."""
    made = []
    for index in range(count):
        payload = {
            "asset_no": f"M-40{21 + index}",
            "purchase_cost": METER_COST,
            "expected_life_years": METER_LIFE_YEARS,
            "install_date": METER_INSTALLED,
        }
        payload.update(overrides)
        made.append(make_asset(actor, **payload))
    return made


def _sides(entry):
    out = {}
    for line in entry.lines.select_related("ledger_account"):
        out[(line.ledger_account.code, line.side)] = line.amount
    return out


def _net_debit(code, *, upto):
    total = Decimal("0")
    for side, amount in ledger_models.JournalLine.objects.filter(
        journal_entry__status=ledger_models.JE_POSTED,
        journal_entry__entry_date__lte=upto,
        ledger_account__code=code,
    ).values_list("side", "amount"):
        total += amount if side == ledger_models.SIDE_DEBIT else -amount
    return total


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the entry: one month's movement, DR expense / CR accumulated
# ═══════════════════════════════════════════════════════════════════════════
def test_t7f_tc1__august_depreciation_posts_the_periods_movement(brazos, dana, audit_rows):
    """**DR 5700 2.73 / CR 1730 2.73** for four $164.00 meters over August 2026.

    The figure is `accumulated(31 Aug) − accumulated(31 Jul)` per asset, both
    from `apps.assets.selectors.asset_book_value` — BR-AST-047's single
    implementation. Nothing here multiplies a cost by a life.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, dana)
        valued_meters(dana)
        audit_rows.clear()

        result = depreciation.post_depreciation(
            dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=POSTED_AT
        )
        entry = ledger_models.JournalEntry.objects.get(pk=result.entry_id)
        sides = _sides(entry)

    assert result.created is True
    assert result.entry_date == AUGUST_END
    assert result.total == AUGUST_CHARGE
    assert result.asset_count == METER_COUNT

    # The arithmetic, spelled out so a reviewer can check it by hand.
    assert ONE_METER_AUGUST == Decimal("0.6834")
    assert (ONE_METER_AUGUST * METER_COUNT).quantize(Decimal("0.01")) == AUGUST_CHARGE

    assert sides[("5700", ledger_models.SIDE_DEBIT)] == AUGUST_CHARGE
    assert sides[("1730", ledger_models.SIDE_CREDIT)] == AUGUST_CHARGE
    assert len(sides) == 2
    assert result.line_count == 2

    # Hard rule 7, on the posting service's own row.
    trail = [
        row for row in audit_rows if (row.get("after") or {}).get("action") == "depreciation_charged"
    ]
    assert len(trail) == 1
    assert trail[0]["after"]["total"] == str(AUGUST_CHARGE)
    assert trail[0]["after"]["assets_charged"] == METER_COUNT


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — it is STANDARD, not an accrual, and it does NOT come back
# ═══════════════════════════════════════════════════════════════════════════
def test_t7f_tc2__depreciation_is_standard_and_never_auto_reverses(brazos, dana):
    """One word, and it is the most important one in the module.

    `JE_ACCRUAL` is what `manual_je.run_accrual_auto_reversals` sweeps. A
    depreciation entry of that type would be reversed on day 1 and the plant
    would sit at its purchase cost forever.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, dana)
        valued_meters(dana)
        result = depreciation.post_depreciation(
            dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=POSTED_AT
        )
        entry = ledger_models.JournalEntry.objects.get(pk=result.entry_id)

        swept = manual_je.run_accrual_auto_reversals(
            as_of=SEPTEMBER_START, posted_at=SWEPT_AT, actor=None
        )
        accumulated = _net_debit("1730", upto=SEPTEMBER_END)
        expense = _net_debit("5700", upto=SEPTEMBER_END)

    assert entry.type == ledger_models.JE_STANDARD
    # The sweep found nothing of ours to reverse.
    assert all(row.entry_id != result.entry_id for row in swept)
    # A credit balance, still standing in September. That is what accumulated
    # depreciation IS.
    assert accumulated == -AUGUST_CHARGE
    assert expense == AUGUST_CHARGE


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — a second press is a REPLAY, not a second month's charge
# ═══════════════════════════════════════════════════════════════════════════
def test_t7f_tc3__a_second_press_is_a_replay_no_op(brazos, dana):
    """Hard rule 6. Charging 2.73 twice would put the plant's book value below
    what the register says it is, in an entry nobody can edit."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, dana)
        valued_meters(dana)
        first = depreciation.post_depreciation(
            dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=POSTED_AT
        )
        second = depreciation.post_depreciation(
            dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=POSTED_AT
        )
        accumulated = _net_debit("1730", upto=AUGUST_END)
        entries = ledger_models.JournalEntry.objects.filter(
            tenant=brazos, source_type=depreciation.SOURCE_DEPRECIATION
        ).count()

    assert second.created is False
    assert second.entry_id == first.entry_id
    assert entries == 1
    assert accumulated == -AUGUST_CHARGE


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — each period posts ITS OWN movement, so two months are two slices
# ═══════════════════════════════════════════════════════════════════════════
def test_t7f_tc4__each_period_charges_only_its_own_movement(brazos, dana):
    """August then September: two entries, each one month's slice, and the
    cumulative accumulated depreciation is what the register says it is.

    This is why a first run does not post a catch-up — and why running the
    months in order builds the position correctly.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, dana)
        valued_meters(dana)
        august = depreciation.post_depreciation(
            dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=POSTED_AT
        )
        september = depreciation.post_depreciation(
            dana,
            period_start=SEPTEMBER_START,
            period_end=SEPTEMBER_END,
            posted_at=datetime(2026, 10, 1, 9, 0, tzinfo=dt_timezone.utc),
        )
        cumulative = _net_debit("1730", upto=SEPTEMBER_END)

    assert august.entry_id != september.entry_id
    assert august.total == AUGUST_CHARGE
    # September is the same shape — one month of the same four meters.
    assert september.total == AUGUST_CHARGE
    assert cumulative == -(AUGUST_CHARGE + september.total)


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — an asset with no cost or no life is EXCLUDED and COUNTED
# ═══════════════════════════════════════════════════════════════════════════
def test_t7f_tc5__an_asset_with_no_cost_is_counted_not_charged_at_zero(brazos, dana):
    """`asset_book_value` answers None — *"never a fabricated $0.00"* — so the
    asset is named in the count and the charge is unchanged."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, dana)
        valued_meters(dana)
        make_asset(dana, asset_no="M-7001", expected_life_years=20)  # no cost
        make_asset(dana, asset_no="M-7002", purchase_cost="99.00")  # no life

        preview = depreciation.preview_depreciation(
            period_start=AUGUST_START, period_end=AUGUST_END
        )

    assert preview.total == AUGUST_CHARGE  # unchanged by the two
    assert preview.asset_count == METER_COUNT
    assert preview.assets_considered == METER_COUNT + 2
    assert preview.excluded.get("asset_has_no_purchase_cost_or_expected_life") == 2


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — a CLOSED period is refused BY NAME, and stays byte-identical
# ═══════════════════════════════════════════════════════════════════════════
def test_t7f_tc6__a_closed_period_is_refused_not_forwarded(brazos, dana, marcus):
    """Forwarding would charge the later month twice and this one never — and
    unlike an accrual there is no day-1 mirror to take it back out."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        valued_meters(dana)
        close.close_period(
            marcus,
            period_start=JULY_START,
            period_end=JULY_END,
            closed_at=JULY_CLOSED_AT,
            reason="LE-9: July closed on the 5th with the checklist incomplete.",
        )
        before = ledger_models.JournalLine.objects.filter(
            journal_entry__entry_date__lte=JULY_END
        ).count()
        with pytest.raises(depreciation.DepreciationError) as refusal:
            depreciation.post_depreciation(
                dana, period_start=JULY_START, period_end=JULY_END, posted_at=POSTED_AT
            )
        after = ledger_models.JournalLine.objects.filter(
            journal_entry__entry_date__lte=JULY_END
        ).count()

    text = str(refusal.value)
    assert "CLOSED" in text
    assert "no day-1 mirror" in text
    assert before == after


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — the two accounts, by DESIGNATION, and 5700 says it is unsigned
# ═══════════════════════════════════════════════════════════════════════════
def test_t7f_tc7__the_accounts_are_resolved_by_designation(brazos, dana):
    """`5700 Depreciation expense` is MINTED by this change (`signed=False`,
    awaiting a HUMAN-GUIDE §6 re-sign) and `1730 Accumulated depreciation —
    meters` is a row the PO already ruled in, so nothing is minted beside it."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, dana)
        placed = ledger_services.ensure_period_matching_accounts(dana)
        again = ledger_services.ensure_period_matching_accounts(dana)
        expense = selectors.gl_account_for_designation(chart.DEPRECIATION_EXPENSE)
        accumulated = selectors.gl_account_for_designation(chart.ACCUMULATED_DEPRECIATION)
        duplicates = ledger_models.LedgerAccount.objects.filter(
            tenant=brazos, code="5700", deleted_at__isnull=True
        ).count()

    assert expense is not None and expense.code == "5700"
    assert expense.type == "expense"
    assert accumulated is not None and accumulated.code == "1730"
    assert accumulated.type == "asset"  # chart.py judgment 1 — not a seventh type
    assert placed == again  # idempotent
    assert duplicates == 1
    # The signature is OWED and the code says so, rather than a comment saying so.
    assert "5700" in chart.PENDING_FINANCE_RE_SIGN_MATCHING
    assert [row.code for row in chart.PERIOD_MATCHING_CHART if row.signed] == []


# ═══════════════════════════════════════════════════════════════════════════
# TC-8 — nothing to depreciate REFUSES rather than posting 0.00
# ═══════════════════════════════════════════════════════════════════════════
def test_t7f_tc8__no_depreciable_plant_refuses_rather_than_posting_zero(brazos, dana):
    """A 0.00 depreciation entry is a claim about a balance sheet."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, dana)
        with pytest.raises(depreciation.DepreciationError) as refusal:
            depreciation.post_depreciation(
                dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=POSTED_AT
            )
        posted = ledger_models.JournalEntry.objects.filter(
            tenant=brazos, source_type=depreciation.SOURCE_DEPRECIATION
        ).count()

    assert "nothing depreciated" in str(refusal.value)
    assert posted == 0


# ═══════════════════════════════════════════════════════════════════════════
# TC-9 — the no-catch-up limit rides on every answer, and no clock is read
# ═══════════════════════════════════════════════════════════════════════════
def test_t7f_tc9__the_opening_limit_is_named_on_every_answer(brazos, dana):
    """A first run posts one month, never two years — and every result says so,
    because a reader who took 2.73 for the plant's whole accumulated
    depreciation would be wrong by 29 months."""
    with tenant_ctx(brazos):
        brazos_ready(brazos, dana)
        valued_meters(dana)
        preview = depreciation.preview_depreciation(
            period_start=AUGUST_START, period_end=AUGUST_END
        )
        result = depreciation.post_depreciation(
            dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=POSTED_AT
        )
        with pytest.raises(depreciation.DepreciationError) as refusal:
            depreciation.post_depreciation(
                dana,
                period_start=SEPTEMBER_START,
                period_end=SEPTEMBER_END,
                posted_at=SEPTEMBER_END,  # a date, not a datetime
            )

    code = depreciation.OPENING_DEPRECIATION_NOT_POSTED["code"]
    assert code in {gap["code"] for gap in preview.unavailable}
    assert code in {gap["code"] for gap in result.unavailable}
    assert "posted_at must be a datetime" in str(refusal.value)
    # The charge really is one month's, not 29 — the difference the limit names.
    assert result.total == AUGUST_CHARGE
    assert result.total < ACCUMULATED_AT_29_MONTHS * METER_COUNT


# ═══════════════════════════════════════════════════════════════════════════
# TC-10 — hard rule 5, and BR-REP-002: no second depreciation formula
# ═══════════════════════════════════════════════════════════════════════════
def test_t7f_tc10__the_ledger_computes_no_depreciation_and_writes_no_journal_row():
    """Grepped rather than described. A `cost * months / life` anywhere in these
    two files would be the second implementation BR-REP-002 forbids, and it is
    how the S49 panel and the trial balance come to disagree about one meter."""
    import inspect

    from apps.ledger import assets_seam

    for module in (depreciation, assets_seam):
        source = inspect.getsource(module)
        for forbidden in ("JournalEntry.objects.create", "JournalLine.objects.create"):
            assert forbidden not in source
        # No life arithmetic: the seam SUBTRACTS two of assets' own answers.
        assert "expected_life_years" not in source
        assert "/ Decimal(life" not in source
    assert "posting.post(" in inspect.getsource(depreciation)
    assert "asset_book_value" in inspect.getsource(assets_seam)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060 C20 + task T7f (12-governance/11-change-requests.md §7 · §12) ·
#         04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-793 ·
#         04-docs/05-modules/03-assets/02-business-rules.md BR-AST-047 ·
#         tests/test_cr028_valuation.py (the ratified $19.8167) ·
#         CLAUDE.md hard rules 1-7 and hard-won laws 1, 2, 4, 5, 7, 14
# generated: 2026-09-02 by the CR-060 T7b/T7d/T7f lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no screen — C20 names none) F✔ G✔
#         H=deferred(🔒 HUMAN-REVIEW-PENDING, row under CR-060 T19)
# gates: THREE SABOTAGES, each through monkeypatch so no live file was mutated,
#         each failure quoted VERBATIM in the module docstring above
# exceptions: (1) the four meters are created through the REAL asset service,
#         not by ORM shortcut · (2) $19.8167 is transcribed from CR-028's
#         ratified test rather than recomputed — a fixture that re-derived it
#         would agree with a broken implementation · (3) the RETIRED-asset
#         exclusion is REPORTED and not asserted here: retiring an asset with a
#         book value requires a treatment decision (`write_off` ·
#         `warranty_claim` · `hold`, BR-AST-047) that belongs to the retire
#         story, and driving it from this file would test that story instead of
#         this one. The count is on every answer and `assets_seam` states the
#         rule
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
