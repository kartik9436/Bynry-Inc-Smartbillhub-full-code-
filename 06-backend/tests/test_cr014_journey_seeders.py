# ── Trace ──────────────────────────────────────────────
# Change:   CR-014 — every journey must have a working fixture. This file holds
#           the SEEDER's own cases: the code in
#           08-qa/01-e2e/stack/seed_journey_fixture.py that a booted stack runs,
#           exercised here so a refusal or a wrong month is caught by pytest
#           rather than by a person reading boot output.
# Rules:    OQ-333 CLOSED 2026-08-22 — PO verbatim: *"Chang the month if
#           required"*: the LE-1 fixture book's MONTH moves when (and only when)
#           July is already taken, and no signed figure moves with it ·
#           OQ-218/OQ-219 CLOSED 2026-08-16 · CLAUDE.md rule 6 (a re-boot
#           re-runs every seeder and must write nothing twice) · DEF-108 (a
#           seeder that cannot honestly satisfy its journey REFUSES by name).
# Red-proof: every case here was shown RED before it was made green — the
#           quotations are in the W11 lane report, 2026-08-22.
# ───────────────────────────────────────────────────────
"""The journey seeders themselves — the month they choose, and the refusals.

CR-014's danger is a green run over the wrong cohort, and `seed_journey_fixture`
is the only thing standing between a booted stack and that. Its two decisions
that no journey assertion can see are tested here:

  · **which month the LE-1 book lands in** (OQ-333), and that the signed
    footing is identical whichever month that is — the whole justification for
    the PO's ruling being cheap;
  · **that a second pass reads the month off the book** rather than deciding
    again, because deciding twice would post two books and a trial balance
    carrying two months of a one-month fixture still balances, still renders,
    and is still wrong.
"""

from __future__ import annotations

import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from tests import ledger_le_fixtures as le
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The script a booted stack runs. Loaded by PATH rather than by import so the
#: test exercises the FILE `boot_stack.sh` executes — a copy under `tests/`
#: would be the second source hard-won law 5 forbids.
SEEDER_PATH = (
    Path(__file__).resolve().parents[2] / "08-qa" / "01-e2e" / "stack" / "seed_journey_fixture.py"
)


def _seeder():
    spec = importlib.util.spec_from_file_location("seed_journey_fixture_under_test", SEEDER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _a_foreign_july(tenant):
    """One posted entry dated Jul 2 that is NOT the LE-1 book — the shape of the
    demo transactional sample slice (47 invoice JEs dated 2026-07-02, DEF-558).

    The amount is deliberately not a workbook figure: this stands for *somebody
    else's July*, and what matters is only that the month is occupied.
    """
    from apps.ledger import posting

    ar = le.gl(tenant, "1200", "asset")
    revenue = le.gl(tenant, "4100", "revenue")
    amount = Decimal("10.00")
    posting.post(
        le.a_request(
            [
                le.line(ar, le.models.SIDE_DEBIT, amount, source_type="invoice"),
                le.line(revenue, le.models.SIDE_CREDIT, amount, source_type="invoice"),
            ],
            key="invoice|DEMO-SAMPLE-SLICE|issued",
            entry_date=date(2026, 7, 2),
        )
    )


def _we1_entry(tenant):
    from apps.ledger import models as ledger_models

    return ledger_models.JournalEntry.objects.filter(
        tenant=tenant, posting_key="invoice|WE-1|issued"
    ).first()


def test_cr014_tc5__july_is_kept_when_nothing_collides(brazos, dana):
    """OQ-333's *"if required"*, literally: an empty July keeps J19's own month.

    The ruling repairs a collision. A stack with no collision must be seeded
    exactly as J19 states it, or the ruling would have quietly re-dated every
    fixture on every stack — which is the option the PO did NOT take.
    """
    seeder = _seeder()
    with tenant_ctx(brazos):
        notes = seeder.seed_j19(brazos, dana)
        entry = _we1_entry(brazos)

        from apps.ledger import reporting

        july = reporting.trial_balance(start=le.JULY_START, end=le.JULY_END)

    assert entry is not None
    assert entry.entry_date == date(2026, 7, 15)  # LE-1's own WE-1 bill date
    assert Decimal(str(july["total_debit"])) == Decimal("553.69")
    assert any("July is EMPTY on this stack" in note for note in notes)


def test_cr014_tc6__oq333_moves_the_month_off_a_taken_july(brazos, dana):
    """PO 2026-08-22: *"Chang the month if required"*.

    July already holds somebody else's entries, so the FIXTURE's month moves.
    Three things are asserted together, because any one of them alone would let
    the failure through: the seeder does not refuse, the book lands OUTSIDE
    July, and the signed footing is byte-for-byte what LE-1 signed. The last is
    the reason this option was the cheap one.
    """
    seeder = _seeder()
    with tenant_ctx(brazos):
        _a_foreign_july(brazos)
        notes = seeder.seed_j19(brazos, dana)
        entry = _we1_entry(brazos)

        from apps.ledger import reporting

        moved_start = seeder._shift_month(le.JULY_START, seeder.FIXTURE_MONTH_SHIFT)
        moved_end = seeder._shift_month(le.JULY_END, seeder.FIXTURE_MONTH_SHIFT)
        book_start = seeder._shift_month(le.CUTOVER, seeder.FIXTURE_MONTH_SHIFT)
        moved = reporting.trial_balance(start=moved_start, end=moved_end)
        whole = reporting.trial_balance(start=book_start, end=moved_end)
        july = reporting.trial_balance(start=le.JULY_START, end=le.JULY_END)

    assert entry is not None
    assert (entry.entry_date.year, entry.entry_date.month) == (moved_start.year, moved_start.month)
    # The signed figures, unmoved: the month changed and the money did not.
    assert Decimal(str(whole["total_debit"])) == Decimal(str(le.LE1_FOOTING))  # 598.69
    assert Decimal(str(moved["total_debit"])) == Decimal("553.69")
    # And July still holds ONLY the foreign entry — the two books never mixed,
    # which is the entire content of DEF-558.
    assert Decimal(str(july["total_debit"])) == Decimal("10.00")
    assert any("OQ-333" in note or "Chang the month" in note for note in notes)


def test_cr014_tc7__a_re_boot_reads_the_month_off_the_book(brazos, dana):
    """CLAUDE.md rule 6, and the ONE ordering that breaks a naive shift.

    The book is seeded FIRST, into a clear July — and only afterwards does the
    demo sample slice arrive and take July. That is not a hypothetical: a stack
    is booted, journeys are seeded, and the transactional sample is loaded on
    top. A seeder that decides the month by asking *"is July taken?"* answers
    YES on the second pass and posts a SECOND book into the moved month, and a
    trial balance carrying two months of a one-month fixture still balances,
    still renders and is still wrong — no journey assertion can see it.

    So the month is read off the book (`invoice|WE-1|issued`, the posting key
    LE-1's own bill carries), never re-decided.
    """
    from apps.ledger import models as ledger_models
    from apps.ledger import reporting

    seeder = _seeder()
    with tenant_ctx(brazos):
        seeder.seed_j19(brazos, dana)
        first = _we1_entry(brazos).entry_date
        _a_foreign_july(brazos)  # the sample slice lands afterwards
        seeder.seed_j19(brazos, dana)
        entries = ledger_models.JournalEntry.objects.filter(
            tenant=brazos, posting_key="invoice|WE-1|issued"
        ).count()
        second = _we1_entry(brazos).entry_date
        moved = reporting.trial_balance(
            start=seeder._shift_month(le.JULY_START, seeder.FIXTURE_MONTH_SHIFT),
            end=seeder._shift_month(le.JULY_END, seeder.FIXTURE_MONTH_SHIFT),
        )

    assert entries == 1
    assert first == second == date(2026, 7, 15)
    # One book, not two: the month the shift WOULD have used holds nothing.
    # (`rows` comes back as a tuple when empty — compare emptiness, not type.)
    assert not moved["rows"]


def test_cr014_tc9__an_unrelated_entry_in_the_book_window_is_not_a_restated_book(brazos, dana):
    """The signed-footing check is a DELTA, not an equality — and this is the
    case that proves it has to be.

    `seed_e2e_fixture.py` posts its one bill's journal entry dated **30 June**,
    which is LE-1's own opening cutover and therefore inside the book's window.
    That entry restates nothing: it is simply another entry in the same date
    range. A check comparing the WINDOW's total to 598.69 refuses this honest
    world; a check comparing what the SEEDER ADDED accepts it and still catches
    a book that changed.

    The first version of the guard got this wrong and was caught by tc7 — this
    case exists so it cannot come back.
    """
    from apps.ledger import posting

    seeder = _seeder()
    with tenant_ctx(brazos):
        ar = le.gl(brazos, "1200", "asset")
        revenue = le.gl(brazos, "4100", "revenue")
        posting.post(
            le.a_request(
                [
                    le.line(ar, le.models.SIDE_DEBIT, Decimal("25.00"), source_type="invoice"),
                    le.line(revenue, le.models.SIDE_CREDIT, Decimal("25.00"), source_type="invoice"),
                ],
                key="invoice|SOMEBODY-ELSES-JUNE|issued",
                entry_date=le.CUTOVER,  # inside the book window, outside July
            )
        )
        notes = seeder.seed_j19(brazos, dana)  # must NOT refuse
        entry = _we1_entry(brazos)

        from apps.ledger import reporting

        whole = reporting.trial_balance(start=le.CUTOVER, end=le.JULY_END)

    assert entry is not None and entry.entry_date == date(2026, 7, 15)  # July kept
    # The window legitimately holds the book PLUS the unrelated 25.00.
    assert Decimal(str(whole["total_debit"])) == Decimal(str(le.LE1_FOOTING)) + Decimal("25.00")
    assert any("signed footing HELD" in note for note in notes)


def test_cr014_tc8__a_taken_destination_month_refuses_by_name(brazos, dana):
    """DEF-108's rule, applied to the ruling itself: if the month the fixture
    moves TO is also occupied, this refuses and names OQ-333 — it does not go
    looking for a third month on its own authority, and it never prints ✔ over
    a month it did not seed."""
    from apps.ledger import posting

    seeder = _seeder()
    with tenant_ctx(brazos):
        _a_foreign_july(brazos)
        # Somebody else's book in the destination month, too.
        ar = le.gl(brazos, "1200", "asset")
        revenue = le.gl(brazos, "4100", "revenue")
        posting.post(
            le.a_request(
                [
                    le.line(ar, le.models.SIDE_DEBIT, Decimal("7.00"), source_type="invoice"),
                    le.line(revenue, le.models.SIDE_CREDIT, Decimal("7.00"), source_type="invoice"),
                ],
                key="invoice|SOMEBODY-ELSE|issued",
                entry_date=seeder._shift_month(le.JULY_START, seeder.FIXTURE_MONTH_SHIFT),
            )
        )
        with pytest.raises(seeder.CannotSeed) as refusal:
            seeder.seed_j19(brazos, dana)

    assert "OQ-333" in str(refusal.value)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-014 · OQ-333 ruling 2026-08-22 · W11 lane
# generated: 2026-08-22
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
# gates: pytest (this file) · seed_journey_fixture.py --check · golden 33/33
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
