# ── Trace ──────────────────────────────────────────────
# Epics:    EP-BIL-01 (late-fee assessment) · EP-MET-04 (the dispute marker)
#           Screens: S29 (the dispute banner states clause 4)
# Change:   CR-038 — BR-MET-133, the disputed amount does not age
# Rules:    BR-MET-133 (CONFIRMED, PO 2026-08-26, closes OQ-245) · BR-BIL-001
#           (max($5, 1.5% × overdue portion); AMENDED 2026-08-11 — no fee while
#           the overdue balance is under $25.00) · BR-BIL-008/002 (grace) ·
#           BR-MET-024 + the OQ-043 closure (the marker and the run hold) ·
#           CLAUDE.md hard rule 4 (issued money stays) · rule 2 (4dp storage,
#           2dp display, never float)
# ───────────────────────────────────────────────────────
"""BR-MET-133 — the bill stands, and the disputed amount does not age.

THE RULE, VERBATIM (04-docs/05-modules/04-metering/02-business-rules.md,
CONFIRMED, PO 2026-08-26, closing OQ-245):

  *"Bill stands, resolution through the billed-correction door, and the
  disputed amount doesn't age into late fees while open"*. Clause 4 in full:
  *"while the dispute is open, the **disputed amount is excluded from ageing
  and from late-fee assessment** — a customer is not penalised for the days we
  investigate. The undisputed remainder of the bill ages normally."*

**FOUR CLAUSES, ONE OF THEM NEW.** Clauses 1–3 are existing behaviour and are
CONFIRMED here rather than rebuilt — the issued invoice is untouched (hard rule
4), the marker holds the account out of the NEXT run, and resolution goes
through `correct_billed_read`. Clause 4 is the new work and is where the
arithmetic lives.

**IT IS A PARTIAL EXCLUSION, NOT A HELD BILL**, and that is the distinction a
careless build loses: Sarah's July bill is $184.20 and she disputes $47.00, so
**$137.20 ages on the normal ladder and $47.00 does not**.

═══════════════════════════════════════════════════════════════════════════
RED PROOF — MEASURED, NOT ASSERTED (hard-won law 7)
═══════════════════════════════════════════════════════════════════════════
The single line that applies the rule —
`overdue_amount = ageable_portion(overdue_amount=overdue_amount,
dispute=dispute)` — was DELETED from `assess_late_fee`, which is exactly the
shape of shipping clause 4 as a dataclass nothing consumes:

    $ python3 -m pytest tests/test_br_met_133_dispute_ageing.py -q
    4 failed, 14 passed in 0.15s

    FAILED test_clause4__the_percentage_is_charged_on_the_remainder
      AssertionError: BR-MET-133 clause 4: $400.00 of a $1,000.00 bill is
      disputed, so 1.5% is charged on the $600.00 remainder and not on the
      whole bill
      assert Decimal('15.00') == Decimal('9.00')
    FAILED test_clause4__the_remainder_can_fall_under_the_25_dollar_floor
      AssertionError: the undisputed remainder is $20.00, under BR-BIL-001's
      $25.00 balance floor - a customer under investigation must not be
      charged $5.00 for a balance we would not chase
      assert Decimal('5.00') == Decimal('0.00')
    FAILED test_clause4__the_whole_bill_disputed_ages_nothing
      assert Decimal('5.00') == Decimal('0.00')
       + where Decimal('5.00') = fee(Decimal('184.20'),
         DisputeExclusion(open=True, amount=Decimal('184.20')))
    FAILED test_clause4__an_open_dispute_with_no_amount_refuses_rather_than_charging
      Failed: DID NOT RAISE NotImplementedError

The second failure is the customer-visible one in a line: a $5.00 penalty on
somebody whose entire undisputed balance is $20.00, while we investigate. The
third is worse and quieter — a customer disputing the WHOLE bill still charged
the minimum. And the fourth is the shape the prime directive warns about: with
the line gone, the OQ-420 refusal is unreachable through `assess_late_fee`, so
the stub is present, correct and never executed. Restoring the line:
`18 passed in 0.10s`.

The fourteen that stayed green under the revert are `ageable_portion` itself
and the resolver — which is exactly the point of the proof: **every part of
this rule can be built, tested and green while the one line that applies it is
missing** (hard-won law 2, in money).

**GT-8 IS UNAFFECTED AND THAT WAS VERIFIED, NOT ASSUMED.** `dispute` defaults
to `NO_DISPUTE`, so every existing caller is byte-for-byte unchanged; `pytest
tests -m golden` and `10-scripts/03-golden-verify.py` were both re-run.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import dispute_ageing
from apps.billing.late_fee import (
    GRACE_CALENDAR,
    LATE_FEE_BALANCE_FLOOR,
    NO_DISPUTE,
    DisputeExclusion,
    ageable_portion,
    assess_late_fee,
)

#: B4.1 / BR-BIL-001's terms, as the frozen golden uses them. Arguments, never
#: constants of the engine (BR-RAT-035) — stated here so every case below reads
#: as one bill under one tenant's settings.
PERCENT = Decimal("0.015")
MINIMUM = Decimal("5.00")
DUE = date(2026, 8, 22)
WELL_PAST_GRACE = date(2026, 9, 30)
GRACE_DAYS = 5

#: The rule's own worked bill.
SARAHS_BILL = Decimal("184.20")
SARAHS_DISPUTE = Decimal("47.00")
SARAHS_REMAINDER = Decimal("137.20")


def fee(overdue: Decimal, dispute: DisputeExclusion = NO_DISPUTE) -> Decimal:
    """One bill, one tenant's settings, assessed well past grace."""
    return assess_late_fee(
        overdue_amount=overdue,
        percent=PERCENT,
        minimum=MINIMUM,
        due_date=DUE,
        as_of=WELL_PAST_GRACE,
        grace_days=GRACE_DAYS,
        grace_mode=GRACE_CALENDAR,
        dispute=dispute,
    )


def disputed(amount: str) -> DisputeExclusion:
    return DisputeExclusion(open=True, amount=Decimal(amount))


# ── clause 4 · the arithmetic ───────────────────────────────────────────────


def test_clause4__sarahs_bill_ages_the_remainder_and_not_the_disputed_part():
    """The rule's own figures. $184.20 billed, $47.00 disputed → $137.20 ages.

    Stated as the SUBTRACTION rather than as a fee, because the fee on this
    particular bill is $5.00 either way (the minimum wins at both sizes) — this
    case fixes the arithmetic and the two below prove it is wired.
    """
    assert (
        ageable_portion(overdue_amount=SARAHS_BILL, dispute=disputed("47.00")) == SARAHS_REMAINDER
    )


def test_clause4__the_percentage_is_charged_on_the_remainder():
    """*"The undisputed remainder of the bill ages normally."* $1,000.00 owed,
    $400.00 disputed: 1.5% of $600.00 is $9.00, where the un-excluded bill
    earns $15.00. Six dollars, on one bill, for the days we investigate."""
    assert fee(Decimal("1000.00")) == Decimal("15.00")
    assert fee(Decimal("1000.00"), disputed("400.00")) == Decimal("9.00"), (
        "BR-MET-133 clause 4: $400.00 of a $1,000.00 bill is disputed, so 1.5% is "
        "charged on the $600.00 remainder and not on the whole bill"
    )


def test_clause4__the_remainder_can_fall_under_the_25_dollar_floor():
    """⚠ THE LANE READING, ASSERTED SO IT CANNOT DRIFT SILENTLY.

    BR-BIL-001's base is *the overdue portion*; clause 4 makes that the
    undisputed remainder, so the $25.00 balance floor (PO 2026-08-11) tests the
    remainder. $60.00 owed with $40.00 disputed leaves $20.00 — under the floor,
    so NO fee — where the un-excluded $60.00 earns the $5.00 minimum.

    The combination was never put to the PO. It is recorded in
    12-governance/02-decision-log.md; if the PO reads it the other way, this
    test is what goes red.
    """
    assert LATE_FEE_BALANCE_FLOOR == Decimal("25.00")
    assert fee(Decimal("60.00")) == Decimal("5.00")
    assert fee(Decimal("60.00"), disputed("40.00")) == Decimal("0.00"), (
        "the undisputed remainder is $20.00, under BR-BIL-001's $25.00 balance floor - "
        "a customer under investigation must not be charged $5.00 for a balance we "
        "would not chase"
    )


def test_clause4__the_whole_bill_disputed_ages_nothing():
    """A customer disputing the entire bill has nothing left to age. The
    subtraction floors at zero rather than going negative — a negative
    "overdue portion" handed to `max($5, …)` would become a real charge."""
    assert ageable_portion(overdue_amount=SARAHS_BILL, dispute=disputed("184.20")) == Decimal(
        "0.00"
    )
    assert fee(SARAHS_BILL, disputed("184.20")) == Decimal("0.00")
    # More disputed than billed is nonsense, and it is floored rather than
    # trusted: it must never come back as a credit.
    assert ageable_portion(overdue_amount=SARAHS_BILL, dispute=disputed("500.00")) == Decimal(
        "0.00"
    )


def test_clause4__no_dispute_leaves_every_existing_caller_untouched():
    """The default is `NO_DISPUTE`, so a caller that never heard of this rule
    computes exactly what it computed before — which is why GT-8 does not move.
    """
    assert ageable_portion(overdue_amount=Decimal("542.10")) == Decimal("542.10")
    assert fee(Decimal("542.10")) == Decimal("8.13")  # GT-8's own figure
    assert fee(Decimal("542.10"), NO_DISPUTE) == Decimal("8.13")


@pytest.mark.parametrize(
    ("billed", "disputed_amount", "ages"),
    [
        ("184.2000", "47.0000", "137.20"),  # 4dp storage in, 2dp display out
        ("100.0050", "0.0050", "100.00"),
        ("25.00", "0.01", "24.99"),  # and 24.99 is under the floor
    ],
)
def test_clause4__money_is_decimal_at_four_places_and_finalized_to_two(
    billed, disputed_amount, ages
):
    """CLAUDE.md hard rule 2: stored to 4 decimals, DISPLAYED at 2, never a
    float. The subtraction runs on `Decimal` and is finalized once
    (BR-RAT-003/B4.4), so a 4dp figure in produces a 2dp figure out."""
    result = ageable_portion(overdue_amount=Decimal(billed), dispute=disputed(disputed_amount))
    assert result == Decimal(ages)
    assert result.as_tuple().exponent == -2
    assert isinstance(result, Decimal)


# ── clause 4 · the gap, refused rather than defaulted (OQ-420) ──────────────


def test_clause4__an_open_dispute_with_no_amount_refuses_rather_than_charging():
    """OQ-420, and the prime directive's stub in its intended shape.

    NOTHING in this repository records a disputed AMOUNT (measured 2026-08-26;
    the same measurement `customers/move_out_settlement.py` recorded for
    BR-CUS-096). The two defensible fallbacks — age nothing, age everything —
    are $137.20 apart on Sarah's bill alone, so neither is chosen.
    """
    with pytest.raises(NotImplementedError) as refusal:
        ageable_portion(overdue_amount=SARAHS_BILL, dispute=DisputeExclusion.unreadable())
    assert "OQ-420" in str(refusal.value)

    with pytest.raises(NotImplementedError):
        fee(SARAHS_BILL, DisputeExclusion.unreadable())


def test_clause4__the_quantity_on_the_marker_is_never_read_as_an_amount():
    """⚠ CLAUDE.md rule 3, in the most expensive direction.

    `meter_reads.disputed_at` sits beside a CONSUMPTION — 684.000000 kWh on the
    rule's own worked read. That is a quantity in dispute, not a sum of money,
    and wiring it in as an amount would silently price a dispute at 684 dollars.
    The resolver reports `amount=None` for exactly that reason.
    """
    exclusion = DisputeExclusion.unreadable()
    assert exclusion.open is True
    assert exclusion.amount is None
    gap = dispute_ageing.dispute_ageing_gap(exclusion)
    assert gap is not None
    assert gap["code"] == dispute_ageing.GAP_DISPUTED_AMOUNT_UNREADABLE
    assert gap["open_question"] == "OQ-420"
    assert gap["br_ref"] == "BR-MET-133"
    # A bill with no dispute states no gap — an absence is reported only where
    # it applies, never as a permanent banner.
    assert dispute_ageing.dispute_ageing_gap(NO_DISPUTE) is None
    assert dispute_ageing.dispute_ageing_gap(disputed("47.00")) is None


# ── the resolver: is a dispute open on this bill? ───────────────────────────


class _Account:
    def __init__(self, unit_id="unit-1"):
        self.unit_id = unit_id


def test_resolver__a_clean_account_ages_the_whole_bill(monkeypatch):
    """No marker → `NO_DISPUTE` → the ordinary bill, unchanged."""
    monkeypatch.setattr(dispute_ageing, "_dispute_holds", lambda: (lambda unit_id: []))
    assert dispute_ageing.open_dispute_for_account(_Account()) is NO_DISPUTE


def test_resolver__an_uncleared_marker_is_an_open_dispute(monkeypatch):
    """BR-MET-024's predicate — set and not cleared — is metering's, read
    through its published selector and never re-derived here (B1)."""
    monkeypatch.setattr(
        dispute_ageing,
        "_dispute_holds",
        lambda: (lambda unit_id: [{"read_id": "r1", "usage_display": "684.000000 kWh"}]),
    )
    exclusion = dispute_ageing.open_dispute_for_account(_Account())
    assert exclusion.open is True
    assert exclusion.amount is None  # readable that it exists, not how much


def test_resolver__every_unit_the_bill_covers_is_checked(monkeypatch):
    """BR-CUS-068: a disputed read on the shared-irrigation meter is priced
    onto the same bill as one on the hallway meter, so both are looked at —
    the same `unit_ids` contract `runs._dispute_hold_for` takes."""
    monkeypatch.setattr(
        dispute_ageing,
        "_dispute_holds",
        lambda: (lambda unit_id: [{"read_id": "r1"}] if unit_id == "unit-2" else []),
    )
    assert dispute_ageing.open_dispute_for_account(_Account()) is NO_DISPUTE
    covered = dispute_ageing.open_dispute_for_account(_Account(), unit_ids=("unit-1", "unit-2"))
    assert covered.open is True


def test_resolver__an_unpublished_seam_refuses_and_does_not_read_as_no_dispute(monkeypatch):
    """*"We could not tell"* and *"there is no dispute"* are different facts and
    only one of them is safe to charge a late fee on — `runs._dispute_hold_for`'s
    own posture, and DEF-046's lesson that a silent zero reads as good news.

    So an absent seam produces the SAME shape as a real open dispute and the
    assessment refuses, rather than billing a penalty to a customer who may be
    under investigation.
    """
    monkeypatch.setattr(dispute_ageing, "_dispute_holds", lambda: None)
    exclusion = dispute_ageing.open_dispute_for_account(_Account())
    assert exclusion.open is True
    assert exclusion.amount is None
    with pytest.raises(NotImplementedError):
        ageable_portion(overdue_amount=SARAHS_BILL, dispute=exclusion)


def test_resolver__the_real_metering_selector_is_the_one_resolved():
    """The seam is resolved BY NAME at call time (B1/G6 — no import statement
    binds billing to metering's internals), and the name is the one metering
    actually publishes. A rename on either side must break here, loudly, rather
    than silently start answering "no dispute" for every account."""
    from apps.metering import selectors as metering_selectors

    assert dispute_ageing.METERING_DISPUTE_SEAM == "dispute_holds_for_unit"
    assert callable(getattr(metering_selectors, dispute_ageing.METERING_DISPUTE_SEAM))
    assert dispute_ageing._dispute_holds() is metering_selectors.dispute_holds_for_unit


# ── clauses 1–3 · CONFIRMED, not rebuilt ────────────────────────────────────


def test_clause1__nothing_here_can_touch_an_issued_invoice():
    """Clause 1 / hard rule 4: the issued invoice is NOT voided and NOT held —
    it stays issued and stays due. This module computes a fee and holds no
    reference to an invoice at all, which is the strongest form that guarantee
    can take: there is nothing to write through.

    Asserted structurally rather than by prose (hard-won law 1: a comment
    claiming a guarantee is not the guarantee).
    """
    import inspect

    source = inspect.getsource(dispute_ageing)
    assert ".save(" not in source
    assert ".update(" not in source
    assert ".delete(" not in source
    assert "Invoice" not in source.split('"""', 2)[2]  # not below the docstring


def test_clause2__the_marker_still_holds_the_account_out_of_the_next_run():
    """Clause 2 is EXISTING behaviour (BR-MET-024 / the OQ-043 closure) and
    lives in `runs._dispute_hold_for`. Confirmed here, not rebuilt: nothing in
    this change weakened it, and both readers use the same seam name."""
    from apps.billing import runs

    assert runs.RUN_ACCOUNT_HELD_BY_DISPUTE
    assert callable(runs._dispute_hold_for)
    # One seam name, two readers. A rename that missed one would silently
    # release the hold on one path and not the other.
    assert dispute_ageing.METERING_DISPUTE_SEAM in inspect_source(runs)


def inspect_source(module) -> str:
    import inspect

    return inspect.getsource(module)


def test_clause3__the_billed_correction_door_is_still_the_only_one():
    """Clause 3: *"resolution goes through the billed-correction door"*. That
    door is `correct_billed_read` (BR-MET-053/US-MET-016) and it is untouched by
    this change — a dispute does not open a correction and this module does not
    reach for one."""
    from apps.metering import services as metering_services

    assert callable(metering_services.correct_billed_read)
    import inspect

    assert "correct_billed_read" not in inspect.getsource(dispute_ageing.open_dispute_for_account)


# ── Lifecycle ─────────────────────────────────────────────
# packet: BR-MET-133 (CONFIRMED 2026-08-26) + OQ-245's closure row + BR-BIL-001
#         as amended 2026-08-11 (the $25.00 floor) + B4.1 + BR-MET-024
# generated: 2026-08-26 by the CR-038 BR-MET-132/133 lane
# checklist: A✔ B✔(S29's dispute banner) C✔ D=deferred(no API half — no route
#            serves a late fee; S31.2/US-BIL-002 unbuilt) E✔ F✔ G✔ H=PENDING
#            (🔒 money math — HUMAN-REVIEW-PENDING row filed)
# exceptions: (1) OQ-420 is MINTED and the unreadable-amount case RAISES.
#            (2) the $25.00 floor applying to the undisputed REMAINDER is a lane
#            reading, asserted above so it cannot drift silently.
#            (3) the AGEING half of clause 4 has no implementation to exclude
#            from — billing publishes no `account_aging_state` — so only the
#            late-fee half is built; REPORTED.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
