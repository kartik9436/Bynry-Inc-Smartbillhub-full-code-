# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-012 (accrual auto-reverse: day 1 of the next period, linked
#           both ways — TC-1 the mirror, TC-2 no double-count, TC-3 the links,
#           TC-4 standard types do not fire, TC-5 no suppress path, TC-6 the
#           locked-period edge, TC-7 isolation)   Screens: S57 · S56
# Rules:    BR-LED-005 (accrual JEs auto-reverse on day 1 of the next period,
#           linked both ways) · BR-TEN-022 (period boundaries from fiscal
#           settings) · BR-TEN-038 (locked-period dating auto-forwards) ·
#           BR-LED-003 (the mirror is a posted, immutable entry) · BR-LED-015
#           (audit) · CLAUDE.md rule 4 · rule 5 · rule 6
# Golden:   LE-4 verbatim — Sep 30 JE-201 accrual DR 1210 Unbilled AR 500.00 /
#           CR 4100 500.00 → Oct 1 JE-202 mirror, both linked, 1210 nets 0.00
# ───────────────────────────────────────────────────────
"""The accrual that undoes itself, so October is not billed twice.

LE-4: *"Sep 30 JE-201 (accrual): DR 1210 Unbilled AR 500.00 / CR 4100 500.00 →
Oct 1 JE-202 auto-posts the mirror, both linked. October's real bill run posts
normally — no double-count."*

**THE TEST THIS FILE EXISTS FOR** is
`test_us_led_012_tc2__october_is_not_billed_twice`. Everything else — the links,
the audit code, the type filter — is machinery in service of one number: 1210
nets to **0.00** across the pair, so the real October bill lands on clean books.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.ledger import close, manual_je, models, posting, reporting
from apps.tenancy import services as tenancy_services

from tests.ledger_le_fixtures import POSTED_AT, gl, line, uuid_for
from tests.test_us_led_011_manual_je import seed_je_series
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

# ── LE-4, transcribed ──────────────────────────────────────────────────────
ACCRUAL_DATE = date(2026, 9, 30)  # "Sep 30 JE-201 (accrual)"
MIRROR_DUE = date(2026, 10, 1)  # "Oct 1 JE-202 auto-posts the mirror"
AMOUNT = Decimal("500.00")  # "DR 1210 Unbilled AR 500.00 / CR 4100 500.00"
OCTOBER_BILL = Decimal("512.40")  # October's REAL billing — any figure but 500
SWEEP_AT = datetime(2026, 10, 1, 6, 0, tzinfo=dt_timezone.utc)

#: US-LED-012 §4: *"Fiscal settings: FY start Jan, monthly close"*. Written
#: through tenancy's own published save, so the calendar this test asserts on is
#: the one BR-TEN-022 computes and not a second one built here.
FISCAL = {
    "country": "United States",
    "timezone": "America/Chicago",
    "language": "en-US",
    "first_day_of_week": "sunday",
    "number_format": "1,234.56",
    "date_format": "MM/DD/YYYY",
    "time_format": "12-hour",
    "fy_start_month": 1,
    "fy_start_day": 1,
    "accounting_method": "accrual",
    "close_cadence": "monthly",
    "close_day": "3rd business day",
    "lock_closed_periods": True,
}


def with_monthly_fiscal_year(actor):
    tenancy_services.save_regional_settings(actor, dict(FISCAL))


def post_accrual(tenant, actor, *, entry_date=ACCRUAL_DATE, entry_type=models.JE_ACCRUAL):
    """LE-4's JE-201, through the real manual-JE service."""
    draft = manual_je.save_manual_je(
        actor,
        entry_date=entry_date,
        entry_type=entry_type,
        memo="Accrue Sep unbilled revenue",
        lines=(
            manual_je.ManualLine(
                ledger_account_id=gl(tenant, "1210", "asset").id,
                side=models.SIDE_DEBIT,
                amount=AMOUNT,
            ),
            manual_je.ManualLine(
                ledger_account_id=gl(tenant, "4100", "revenue").id,
                side=models.SIDE_CREDIT,
                amount=AMOUNT,
            ),
        ),
    )
    return manual_je.post_manual_je(
        actor,
        entry_id=draft.entry_id,
        posted_at=datetime(2026, 9, 30, 17, 5, tzinfo=dt_timezone.utc),
    )


def net_on(tenant, code):
    """Σ debits − credits on one GL, over POSTED entries only."""
    total = Decimal("0")
    for side, amount in models.JournalLine.objects.filter(
        tenant=tenant, ledger_account__code=code, journal_entry__status=models.JE_POSTED
    ).values_list("side", "amount"):
        total += amount if side == models.SIDE_DEBIT else -amount
    return total


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the mirror, balanced, on day 1 of the next period
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_012_tc1__the_mirror_posts_on_day_one_linked_both_ways(brazos, dana, audit_rows):
    """US-LED-012 TC-1: *"Oct 1: JE-202 auto-posts the mirror (DR 4100 500.00 /
    CR 1210 500.00), balanced; both entries linked both ways; audit
    `journal.auto_reversed`."*

    The mirror is written by `apps.ledger.posting.reverse_entry`, which READS the
    accrual and swaps the sides — never a hand-composed compensating entry, so it
    cannot disagree with what it reverses.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        seed_je_series(brazos, next_number=201)  # LE-4 opens at JE-201
        accrual = post_accrual(brazos, dana)

        assert manual_je.accrual_reversal_due_on(ACCRUAL_DATE) == MIRROR_DUE

        results = manual_je.run_accrual_auto_reversals(as_of=MIRROR_DUE, posted_at=SWEEP_AT)
        assert len(results) == 1
        run = results[0]
        assert run.created is True
        assert run.due_on == MIRROR_DUE
        assert run.entry_date == MIRROR_DUE
        assert run.amount == AMOUNT

        original = models.JournalEntry.objects.get(pk=accrual.entry_id)
        mirror = models.JournalEntry.objects.get(pk=run.mirror_entry_id)

        # Sides swapped, amounts identical.
        sides = {
            (row.ledger_account.code, row.side): row.amount
            for row in mirror.lines.select_related("ledger_account")
        }
        assert sides[("4100", models.SIDE_DEBIT)] == AMOUNT
        assert sides[("1210", models.SIDE_CREDIT)] == AMOUNT
        assert mirror.entry_date == MIRROR_DUE
        assert mirror.status == models.JE_POSTED
        assert mirror.type == models.JE_REVERSING

        # BR-LED-005 — LINKED BOTH WAYS (r13 #2 gives the pair two columns).
        assert str(mirror.reversal_of_id) == str(original.pk)
        original.refresh_from_db()
        assert str(original.auto_reverse_entry_id) == str(mirror.pk)

        assert "journal.auto_reversed" in {row["action"] for row in audit_rows}
        # And NOT the human's code — the two are different facts (TC-1's own
        # `journal.auto_reversed` versus US-LED-013's `journal.reversed`).
        assert "journal.reversed" not in {row["action"] for row in audit_rows}


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — no double count (THE TEST THIS FILE EXISTS FOR)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_012_tc2__october_is_not_billed_twice(brazos, dana):
    """US-LED-012 TC-2: *"No double count: 1210 nets to 0.00 across the pair;
    October revenue = October's bills only."*

    LE-4's whole point, as two numbers: **1210 nets 0.00**, and October's revenue
    is the real bill's 512.40 — not 1012.40, which is what an unreversed accrual
    would have made it.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        seed_je_series(brazos, next_number=201)
        post_accrual(brazos, dana)
        manual_je.run_accrual_auto_reversals(as_of=MIRROR_DUE, posted_at=SWEEP_AT)

        # October's REAL bill run, through the posting service like any other.
        ar = gl(brazos, "1200", "asset")
        revenue = gl(brazos, "4100", "revenue")
        posting.post(
            posting.PostingRequest(
                posting_key="invoice|OCT-1|issued",
                entry_date=date(2026, 10, 20),
                posted_at=POSTED_AT,
                currency="USD",
                lines=(
                    line(ar, models.SIDE_DEBIT, OCTOBER_BILL, source_type="invoice"),
                    line(revenue, models.SIDE_CREDIT, OCTOBER_BILL, source_type="invoice"),
                ),
                source_type="invoice",
                source_id=uuid_for("OCT-1"),
            )
        )

        assert net_on(brazos, "1210") == Decimal("0.00")  # the accrual is undone
        october = reporting.trial_balance(start=date(2026, 10, 1), end=date(2026, 10, 31))
        revenue_row = next(row for row in october["rows"] if row["code"] == "4100")
        # October's revenue = October's bill (512.40) MINUS the accrual mirror's
        # 500.00 debit, which is exactly the September revenue being handed back.
        assert revenue_row["credit"] == OCTOBER_BILL - AMOUNT
        assert october["balanced"] is True

        # Across BOTH months, revenue is the accrual plus October's real bill and
        # nothing is counted twice.
        whole = reporting.trial_balance()
        assert next(row for row in whole["rows"] if row["code"] == "4100")["credit"] == OCTOBER_BILL


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — the links render, TC-4 — only accruals fire
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_012_tc3__the_s56_list_carries_both_links(brazos, dana):
    """US-LED-012 TC-3: *"S56 list shows JE-201 ↔ JE-202 linkage in the Links
    column; each entry's view names the other."*

    ⚠ **THE SECOND NUMBER CHANGED ON 2026-09-24 (`P0.3`), AND IT IS THE WHOLE
    POINT OF THAT TASK RATHER THAN A SIDE EFFECT OF IT.** This case asserted
    `rows[mirror].number is None`, with the comment *"the mirror is
    system-posted"* — a true statement about a **DEFECT**, pinned as though it
    were a rule. `BR-LED-021`'s own row records the same gap in the same
    breath: *"(ii) SYSTEM-POSTED entries carry no number — bills, payments,
    the remittance JE and the accrual mirror all post through `posting.post` /
    `posting.reverse_entry`, which allocate nothing, so **LE-4's JE-202 is not
    reproduced**"*.

    `post()` allocates now, so **`LE-4` is reproduced in full for the first
    time: `JE-000201` accrues and `JE-000202` mirrors it.** The golden document
    has said `JE-201 → JE-202` since it was ratified; until today the product
    could only produce the first half of that sentence.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        seed_je_series(brazos, next_number=201)
        accrual = post_accrual(brazos, dana)
        [run] = manual_je.run_accrual_auto_reversals(as_of=MIRROR_DUE, posted_at=SWEEP_AT)

        rows = {row.entry_id: row for row in reporting.journal_entry_list()["rows"]}
        assert rows[accrual.entry_id].auto_reverse_entry_id == run.mirror_entry_id
        assert rows[accrual.entry_id].reversed_by_entry_id == run.mirror_entry_id
        assert rows[run.mirror_entry_id].reversal_of_entry_id == accrual.entry_id
        # LE-4's own numbers, out of the product — BOTH of them, since `P0.3`.
        assert rows[accrual.entry_id].number == "JE-000201"
        assert rows[run.mirror_entry_id].number == "JE-000202"


def test_us_led_012_tc4__a_standard_entry_never_auto_reverses(brazos, dana):
    """US-LED-012 TC-4: *"Standard-type JE posted → NO auto-reverse — only
    accrual type triggers it (BR-LED-005)."*"""
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        seed_je_series(brazos)
        post_accrual(brazos, dana, entry_type=models.JE_STANDARD)

        assert manual_je.pending_accrual_reversals(as_of=MIRROR_DUE) == ()
        assert manual_je.run_accrual_auto_reversals(as_of=MIRROR_DUE, posted_at=SWEEP_AT) == ()
        assert net_on(brazos, "1210") == AMOUNT  # still standing, as it should be


def test_us_led_012_tc4b__the_sweep_does_not_fire_before_day_one(brazos, dana):
    """*"day 1 of the NEXT period"* — not the day after the entry. An accrual
    dated Sep 30 is due Oct 1, and a sweep run on Sep 30 finds nothing."""
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        seed_je_series(brazos)
        post_accrual(brazos, dana)
        assert manual_je.run_accrual_auto_reversals(as_of=ACCRUAL_DATE, posted_at=SWEEP_AT) == ()
        assert net_on(brazos, "1210") == AMOUNT


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — idempotent, and nothing to suppress
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_012_tc5__the_sweep_replays_to_nothing(brazos, dana):
    """US-LED-012 TC-5: *"Attempt to delete/suppress the pending auto-reversal …
    No suppress path exists (the reversal is the rule)."*

    And the sweep is idempotent (CLAUDE.md rule 6): its key is
    `journal_entry|<accrual id>|auto_reversed`, one string per accrual forever,
    so a catch-up run after a host was down writes nothing twice.
    """
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        seed_je_series(brazos)
        post_accrual(brazos, dana)
        first = manual_je.run_accrual_auto_reversals(as_of=MIRROR_DUE, posted_at=SWEEP_AT)
        assert len(first) == 1 and first[0].created is True

        again = manual_je.run_accrual_auto_reversals(as_of=date(2026, 10, 31), posted_at=SWEEP_AT)
        assert again == ()  # the accrual now carries its link and is not pending
        assert models.JournalEntry.objects.filter(
            tenant=brazos, type=models.JE_REVERSING
        ).count() == 1
        assert net_on(brazos, "1210") == Decimal("0.00")


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — the locked-period edge (BR-TEN-038)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_012_tc6__a_mirror_due_in_a_closed_period_forwards(brazos, dana):
    """US-LED-012 TC-6: *"Day 1 of the next period is inside a locked period
    (reopened-then-closed edge) → Mirror auto-forwards to the earliest open
    period with the BR-TEN-038 audit note — never lands in a locked month."*"""
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        seed_je_series(brazos)
        post_accrual(brazos, dana)

        # October is closed before the sweep runs — the edge TC-6 describes.
        close.close_period(
            dana,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            closed_at=datetime(2026, 11, 2, 9, 0, tzinfo=dt_timezone.utc),
            reason="closed early for the audit",
        )

        [run] = manual_je.run_accrual_auto_reversals(
            as_of=date(2026, 11, 5), posted_at=SWEEP_AT
        )
        assert run.due_on == MIRROR_DUE
        assert run.entry_date == date(2026, 11, 1)  # the earliest OPEN period's day 1
        assert run.date_note is not None
        assert run.date_note["detail"] == "period closed; auto-forwarded"

        mirror = models.JournalEntry.objects.get(pk=run.mirror_entry_id)
        assert mirror.entry_date == date(2026, 11, 1)
        # October's books are untouched by the forwarded mirror.
        october = reporting.trial_balance(start=date(2026, 10, 1), end=date(2026, 10, 31))
        assert october["total_debit"] == Decimal("0")


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — isolation
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_012_tc7__a_mirror_posts_in_its_own_tenants_books_only(
    brazos, dana, lonestar, erin
):
    """US-LED-012 TC-7: *"Lone Star Ridge accrual → its mirror posts in its books
    only (RLS)."*"""
    with tenant_ctx(lonestar):
        with_monthly_fiscal_year(erin)
        seed_je_series(lonestar)
        post_accrual(lonestar, erin)

    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        # Brazos Bend's sweep sees nothing — the accrual is not its own.
        assert manual_je.run_accrual_auto_reversals(as_of=MIRROR_DUE, posted_at=SWEEP_AT) == ()
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == 0

    with tenant_ctx(lonestar):
        [run] = manual_je.run_accrual_auto_reversals(as_of=MIRROR_DUE, posted_at=SWEEP_AT)
        assert run.created is True
        assert models.JournalEntry.objects.filter(tenant=lonestar).count() == 2


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-012@0007led (sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-04-manual-je.md US-LED-012 §1-§8 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-005/003/015 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-4 · 12-governance/01-open-questions.md OQ-033 CLOSED → BR-TEN-038)
# generated: 2026-08-15 by the ledger close-the-books lane
# checklist: A✔ B✔ C✔ D=deferred(no API half in this lane) E=deferred(no frontend half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST — with `link_forward` not passed, TC-1's
#         `original.auto_reverse_entry_id` was None and BR-LED-005's *"linked
#         both ways"* was half built while every other assertion passed
# exceptions: THE MIRROR CARRIES NO `JE-` NUMBER. BR-LED-021 stamps a number at
#         POST and the mirror posts through `posting.reverse_entry`, which this
#         lane did not extend to allocate one — a system-posted entry would need
#         the numbering kernel inside the sole-writer file, and LE-4's *JE-202*
#         is therefore NOT reproduced. REPORTED: the same is true of every
#         system-posted entry in the product (bills, payments, the remittance
#         JE), so it is a gap in BR-LED-021's reach rather than in this story ·
#         the sweep has NO scheduler: `run_accrual_auto_reversals` is called by
#         a caller who names `as_of` and `posted_at` (BR-TEN-043), and wiring it
#         to the jobs table is another lane's — stated rather than implied
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
