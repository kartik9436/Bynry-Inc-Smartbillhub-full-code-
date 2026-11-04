# ── Trace ──────────────────────────────────────────────
# Story:    CR-013 (Plans & Rates) · CR-019 (trash is billed per cart)
# Rules:    BR-RAT-080 (the rate schedule prices a QUANTITY, the charge code
#           prices a THING — PO ruling 2026-08-20, RATIFIED) ·
#           BR-RAT-081 (a service declares metered or unmetered — PO ruling
#           2026-08-20; the DECLARATION is ruled, the quantity source is OQ-283)
# Tests:    this file
# Impacts:  apps.rating.models · apps.rating.discounts · apps.tenancy.models
# ───────────────────────────────────────────────────────
"""The ratified figures, asserted so drift goes RED.

CLAUDE.md's sign-off protocol has two halves and this file is the second: *"the
ruling is written into the ledger row verbatim with its date and the exact
statements shown, **and a test asserts the ratified figure so drift goes RED**."*
The first half is `12-governance/02-decision-log.md` (2026-08-20, two rows).

WHY A TEST CAN GUARD THIS AT ALL
--------------------------------
BR-RAT-080 is a rule about WHERE an amount may live, and design §A3 already
recorded why no ordinary test sees a breach: *"no test catches it, because both
rows are individually correct and only the rule makes the total wrong."* So this
file does not check arithmetic. It checks the SHAPE the rule requires — which
fields exist, on which model — because that is the thing a later lane can quietly
undo. Four amounts were found expressible by both objects, two at the same stored
figure ($12.00 base, $18.00 minimum bill).

THE HOMONYM GUARD IS THE POINT OF HALF THIS FILE
------------------------------------------------
BR-RAT-080 names two pairs that LOOK like the duplication it forbids and are not:

    TariffVersion.minimum_bill   a floor on the whole service line
    Charge.min_amount            the floor on a PERCENT code (LATE · 1.5% · $5 min)

    TariffVersion cap            a cap on a usage calculation
    Charge.max_amount            a cap on a percentage fee

The predictable failure of this ruling is a tidy-up lane reading "no amount may
be expressible by both" and deleting one of each pair. These assertions make that
fail by name.
"""

from __future__ import annotations

import pytest

from apps.rating.models import Charge, TariffVersion
from apps.tenancy.models import TenantService


def _fields(model) -> set[str]:
    return {f.name for f in model._meta.get_fields()}


# ── BR-RAT-080 · the schedule owns the floor on its own result ──────────────


def test_the_schedule_owns_the_minimum_bill() -> None:
    """A minimum bill is neither a quantity nor a thing — it is a FLOOR on the
    schedule's own computed result, so BR-RAT-080 leaves it on the schedule."""
    assert "minimum_bill" in _fields(TariffVersion)


def test_the_charge_code_owns_no_minimum_bill_of_its_own() -> None:
    """DEF-362: `MIN-W · Minimum bill · water · $18.00 · per size` is drawn in
    r10 alongside `TariffVersion.minimum_bill`, which reads $18.00 for the same
    5/8" row. BR-RAT-080 says one of them must not exist, and it is MIN-W.

    A charge code carries `min_amount` (a percent floor — see the homonym test)
    and must never gain a field that means "the minimum bill for this service"."""
    assert "minimum_bill" not in _fields(Charge)
    assert "min_bill" not in _fields(Charge)


# ── BR-RAT-080 · the homonyms, which are NOT the duplication ────────────────


def test_min_amount_and_minimum_bill_are_different_fields_and_both_survive() -> None:
    """Same word, unrelated rules. Deleting either is the predictable misreading
    of BR-RAT-080, so it fails here by name."""
    assert "min_amount" in _fields(Charge), (
        "Charge.min_amount is the floor on a PERCENT charge code (LATE · 1.5% · "
        "$5 min). It is NOT the schedule's minimum bill and BR-RAT-080 keeps both."
    )
    assert "minimum_bill" in _fields(TariffVersion)


def test_max_amount_survives_beside_the_schedules_cap() -> None:
    assert "max_amount" in _fields(Charge), (
        "Charge.max_amount caps a percentage fee; the schedule's optional cap "
        "caps a usage calculation. BR-RAT-080 keeps both."
    )


# ── BR-RAT-080 · the base, which §A3 ruled and DEF-359 has not implemented ──


@pytest.mark.xfail(
    reason=(
        "DEF-359 — §A3 ruled the charge code owns the base and the engine still "
        "takes it from ScheduleVersion.size_rows. Until that lands, "
        "TariffVersion.base_charge is still the writable source. This xfail is "
        "the marker: it turns GREEN-unexpectedly the day DEF-359 is fixed, and "
        "that is the signal to delete it."
    ),
    strict=True,
)
def test_the_schedule_carries_no_base_charge() -> None:
    """§A3, generalised by BR-RAT-080: the base is a THING, so the charge code
    owns it and the matrix only DISPLAYS it, attributed."""
    assert "base_charge" not in _fields(TariffVersion)


# ── BR-RAT-081 · the metered/unmetered declaration ──────────────────────────


def test_a_service_declares_whether_it_is_metered() -> None:
    """CR-019's worked case: three carts at $15.00 must bill $45.00, and the run
    must stop demanding a meter before any of that is reachable.

    ⚠ **THE `xfail(strict=True)` IS REMOVED (DEF-488, closed here).** It said
    *"BR-RAT-081 is RULED and not yet built"*, and `tenant_services.metered` has
    since been built — so a marker written to turn green-unexpectedly did
    exactly that, and a strict XPASS **fails the suite**. It had been RED on the
    branch, which is a gate carrying no information: red before the change and
    red after it. DEF-488's own prevention column prescribes this fix — *"drop
    the xfail marker and keep the assertion — it passes, and it is now a real
    guard that the declaration stays on tenant_services."*

    ⚠ **AND THE MARKER'S SCOPE NOTE WAS ALSO STALE, WHICH THE DEFECT DID NOT
    CATCH.** It said *"where an unmetered service's quantity comes from is
    OQ-283 and is NOT ruled"*. **OQ-283 CLOSED on 2026-08-20** — BR-RAT-090,
    option A: *"an unmetered service's quantity is a COUNT OF ITS ASSETS ON THE
    UNIT"*, observed and never typed — and `resolution.counted_quantity`
    implements it. Kept here as a comment rather than deleted, because the
    reason a test exists outlives the marker that once carried it.

    ⚠ **WHAT IS STILL NOT TRUE: nothing in the product READS this column**
    (DEF-495). The declaration exists and cannot reach a bill, so DEF-161's
    *"a plan carrying any non-metered service cannot be billed at all"* still
    holds in the running product. This assertion covers the COLUMN, which is all
    it ever covered; the reader is the cutover's half (DEF-438).

    ⚠ **THE COLUMN IS NOW `billing_basis` AND CARRIES THREE VALUES — BR-TEN-1180,
    PO ruling 2026-09-02, closing DEF-2409.** BR-RAT-081's question was right and
    its vocabulary was one value short: sewer reads no register AND is not priced
    by a count, so neither side of the boolean was true for it. The rule this case
    guards is unchanged — the declaration lives on the SERVICE — so the case is
    amended rather than retired, and `TenantService.metered` survives beside it as
    a read-only property for the ~30 readers that ask BR-RAT-081's question.
    """
    assert "billing_basis" in _fields(TenantService)
    assert "metered" not in _fields(TenantService), (
        "the boolean is gone from the database; `metered` is a derived property now"
    )
    assert TenantService(billing_basis="metered").metered is True
    assert TenantService(billing_basis="share").metered is False


def test_the_declaration_belongs_on_the_service_not_the_plan_or_the_premise() -> None:
    """BR-RAT-081 places it on the SERVICE. This asserts the negative half, which
    is the part a later lane could get wrong without noticing: it must not appear
    on the tariff version, where it would become per-schedule instead of
    per-service."""
    assert "metered" not in _fields(TariffVersion)
    assert "billing_basis" not in _fields(TariffVersion)
