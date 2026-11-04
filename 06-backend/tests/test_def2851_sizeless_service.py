# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2851 — `resolution_shadow.adapt` demanded a connection size for
#          EVERY metered service and blocked the whole account when one came
#          back None. `BR-RAT-015` rules SEWER to have no size class at all —
#          it is a share of the water usage charge — so no utility that bills
#          sewer could be shadowed on a single account. Measured 2026-08-31
#          over three utilities: 116 of 163 accounts NOT ATTEMPTED, every one
#          `service 'sewer' has no connection size`. R3 refused it too:
#          `resolve_served_size` raised `SizeNotServed` for a size that
#          correctly does not exist.
# Rules:   BR-RAT-015 (sewer carries no size class — it is a share of the water
#          usage charge) · BR-RAT-120 / PO 2026-08-28 (an unpriced size is
#          REFUSED and never substituted) · BR-RAT-088 (the charge code owns
#          the base) · DEF-514 (a size nobody recorded is a DATA GAP a human
#          fixes, and is NOT this)
# Tests:   this file. The same fix on real rows is
#          `10-scripts/cr052_r1r7_shadow_measure.py --tenant all`.
# Impacts: apps/rating/resolution.resolve_served_size 🔒 (rating math —
#          HUMAN-REVIEW-PENDING) · apps/billing/resolution_shadow.adapt
# ───────────────────────────────────────────────────────
"""A service RULED to have no size is not a service whose size is MISSING.

⚠ **THE WHOLE FILE IS ABOUT KEEPING TWO `None`s APART**, because collapsing
them is the expensive direction in both senses:

* **Treat "ruled to have none" as "missing"** and every utility that bills
  sewer is unpriceable — what `DEF-2851` measured.
* **Treat "missing" as "ruled to have none"** and a water connection whose
  ladder nobody has configured gets priced against a code with no size rows.
  That picks a tier ladder, which is money, on the strength of nothing.

`tenancy.service_size_classes` already keeps them apart and says so in its own
docstring — an EMPTY TUPLE for a service ruled to have none, a RAISE for one
whose bands the Product Owner never saw. Neither the adapter nor R3 asked it.
Both do now, and this file pins all three answers.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.rating import resolution


def _schedule(service: str, *, sizes: dict[str, Decimal | None] | None = None):
    return resolution.ScheduleVersion(
        version_id=f"v-{service}",
        service=service,
        size_rows=dict(sizes or {}),
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · RULED TO HAVE NONE — the case DEF-2851 could not price
# ══════════════════════════════════════════════════════════════════════════


def test_sewer_resolves_with_no_size_because_the_po_ruled_it_has_none():
    """R3 passes a sewer connection through. BEFORE THE FIX THIS RAISED.

    The schedule's `size_rows` is EMPTY and that is correct — `sample_size_rows`
    writes none for sewer because `service_size_classes` has none to write. The
    old `resolve_served_size` asked only *"is this size on the map"*, and `""`
    never is, so it refused a size that does not exist and never will.
    """
    served = resolution.resolve_served_size(
        _schedule("sewer"),
        resolution.MeterFacts(service="sewer", connection_size=resolution.NO_SIZE),
    )
    assert served == resolution.NO_SIZE


def test_a_flat_sewer_charge_code_prices_at_no_size():
    """R4's half: `NO_SIZE` narrows to a code with no size rows, and prices.

    This is the reason `""` is the right value rather than `None` — it is the
    SAME answer the unmetered branch has always given (`_size_key`: *"a code
    with no size rows matches, which is exactly right for a flat per-cart
    price"*), so sewer joins a path that already works.
    """
    code = resolution.ChargeCode(
        code="SEWER-BASE",
        service="sewer",
        flat_amount=Decimal("18.5000"),
    )
    assert resolution.charge_code_amount(code, resolution.NO_SIZE) == Decimal("18.5000")


def test_a_per_size_sewer_code_still_refuses():
    """A code claiming a size dimension sewer does not have is still a refusal.

    The fix opens R3, not R4. A sewer code with a per-size table is a
    configuration error, and `ChargeCodeAmountMissing` is the right answer to
    it — not a silently chosen row.
    """
    code = resolution.ChargeCode(
        code="SEWER-BAD",
        service="sewer",
        amounts={"W-58": Decimal("18.5000")},
    )
    with pytest.raises(resolution.ChargeCodeAmountMissing):
        resolution.charge_code_amount(code, resolution.NO_SIZE)


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE OTHER TWO ANSWERS — which the fix must NOT weaken
# ══════════════════════════════════════════════════════════════════════════


def test_a_service_with_a_ladder_still_refuses_an_empty_size():
    """DEF-514 is untouched: water HAS sizes, so an empty one is a data gap.

    ⚠ **THIS IS THE TEST THAT STOPS THE FIX BECOMING A DEFAULT.** If R3 accepted
    `""` for any service, a water connection whose size nobody recorded would
    narrow to a code with no size rows and bill. The refusal must name the
    ladder that exists, so the sentence a human reads is *"this service HAS
    sizes and none was recorded"* and not *"not served"*.
    """
    with pytest.raises(resolution.SizeNotServed) as raised:
        resolution.resolve_served_size(
            _schedule("water", sizes={"W-58": None}),
            resolution.MeterFacts(service="water", connection_size=resolution.NO_SIZE),
        )
    message = str(raised.value)
    assert "DOES" in message and "ratified size ladder" in message
    assert "W-58" in message


def test_a_service_whose_bands_were_never_ruled_refuses_and_carries_its_oq():
    """Battery's bands were never put to the PO, so R3 refuses and says which.

    `size_classes_for_service` RAISES for battery rather than returning `()` —
    *"an empty tuple means ruled to have none and a raise means nobody has
    said"* — and R3 must carry that distinction out as a refusal with the open
    question in it, never as a pass.
    """
    with pytest.raises(resolution.SizeNotServed) as raised:
        resolution.resolve_served_size(
            _schedule("battery"),
            resolution.MeterFacts(service="battery", connection_size=resolution.NO_SIZE),
        )
    assert "OQ-561" in str(raised.value)


def test_an_unknown_service_refuses_rather_than_crashing():
    """A service that is not one of the ten refuses by name, never `KeyError`.

    A chain whose refusals are its product (nine typed ones) must not let a
    bare `KeyError` out of R3 — a caller catching `SizeNotServed` would miss it
    and the run would die instead of reporting.
    """
    with pytest.raises(resolution.SizeNotServed):
        resolution.resolve_served_size(
            _schedule("teleportation"),
            resolution.MeterFacts(
                service="teleportation", connection_size=resolution.NO_SIZE
            ),
        )


def test_a_real_size_absent_from_the_schedule_still_refuses():
    """The original R3 refusal, unchanged. BR-RAT-120, ruled twice."""
    with pytest.raises(resolution.SizeNotServed) as raised:
        resolution.resolve_served_size(
            _schedule("water", sizes={"W-58": None}),
            resolution.MeterFacts(service="water", connection_size="W-2"),
        )
    assert "'W-2'" in str(raised.value)
