"""CR-089 wave H `H3` (`PUJ-35`) — **a base charge of `0.00` is not "free", and
the row says what the service IS priced on** (`BR-MET-1166`).

── Trace ──────────────────────────────────────────────
Change:   CR-089 §6 wave H `H3`
Rules:    BR-MET-1166 · BR-RAT-024 (eleven services, `fire` at 11) ·
          CR-063 (fire: the size class picks the price, the COUNT multiplies
          it) · the prime directive (an unruled boundary is stubbed, never
          answered by choosing a value)
🔒 NOT a money path: `_service_priced_on` reads no price, no plan and no
   database. B4/B5 are ❄️ FROZEN and untouched.
───────────────────────────────────────────────────────

**WHAT THIS PINS THAT NOTHING ELSE DOES.** The screen's sentence is chosen from
a SHAPE, and the shape is `apps/tenancy`'s ratified size classes read through
`apps.rating.resolution.service_prices_by_size_class`. If a service silently
changed sides — the exact failure `DEF-3098` records, where four capacity
services were read as banded and *no battery or solar customer could be
billed* — the Plan tab would print a confident wrong sentence beside a `$0.00`
and nothing else in this repository would notice.

**RED PROVED FIRST**, through `pytest` — the harness that runs it — by swapping
`service_prices_by_size_class` for `DEF-3098`'s old proxy question
(`bool(size_classes_for_service(code))`) and watching four cases break:

    E  AssertionError: battery would print the wrong sentence beside its base charge
    E  assert ('size_bands', 'kW') == ('capacity', 'kW')
    E    At index 0 diff: 'size_bands' != 'capacity'

    …and the same for broadband, solar and storm_water — every capacity service.

⚠ **AND THE FIRST TIME THAT PROOF WAS RUN IT STAYED GREEN, WHICH IS WHY THE
IMPLEMENTATION MOVED RATHER THAN THE CLAIM.** `_service_priced_on` originally
tested `capacity_uom is not None` FIRST and only fell through to the ruled
question, so the ruled question was unreachable for exactly the four services it
exists to protect and the swap changed nothing. The branch order is now the
guard, and this file is what holds it there. Asserting a red proof is not the
same as running one (hard-won law 7).

It runs on the default sqlite suite because nothing here touches a row.
"""

from __future__ import annotations

import pytest

from apps.metering.selectors import _service_priced_on

#: The eleven, in `BR-RAT-024`'s seed order, each with the shape its own
#: ratified rows put it on. **No service is named in the implementation** — this
#: table is the assertion, not the source.
EXPECTED = {
    "electric": ("size_bands", None),
    "water": ("size_bands", None),
    "gas": ("size_bands", None),
    "sewer": ("no_size_axis", None),
    "trash": ("size_bands", None),
    "storm_water": ("capacity", "ERU"),
    "solar": ("capacity", "kW"),
    "broadband": ("capacity", "Mbps"),
    "thermal_heat": ("capacity", "ton"),
    "battery": ("capacity", "kW"),
    "fire": ("size_bands", None),
}


@pytest.mark.parametrize("service,expected", sorted(EXPECTED.items()))
def test_every_service_lands_on_its_ruled_shape(service: str, expected: tuple[str, str | None]):
    answer = _service_priced_on(service)
    assert (answer["shape"], answer["capacity_uom"]) == expected, (
        f"{service} would print the wrong sentence beside its base charge"
    )


def test_fire_is_banded_and_carries_its_six_sizes():
    """`CR-063`, and the PO's removal of the private hydrant on 2026-09-03.

    Fire is trash's arithmetic and not solar's: the size class picks the price
    and the COUNT multiplies it. A `$0.00` fire base is therefore CORRECT, which
    is the whole reason the column exists. **Six**, not seven — `HYD` at
    `$25.0000` left the list by PO ruling (*"remove private hydrants from
    list"*), and a seventh here would mean the ladder had grown back.
    """
    answer = _service_priced_on("fire")
    assert answer["shape"] == "size_bands"
    assert answer["size_count"] == 6


def test_a_capacity_service_names_the_unit_it_sums_in():
    """*"By capacity"* alone does not say what a clerk needs; *"the kW
    installed"* does. Hard rule 3 — a consumption is always with its unit."""
    assert _service_priced_on("solar")["capacity_uom"] == "kW"
    assert _service_priced_on("broadband")["capacity_uom"] == "Mbps"


def test_an_unrecognised_code_is_an_absence_and_never_a_guess():
    """A code that is not one of the eleven raises `KeyError` downstream, and
    this read is on a SCREEN. It answers `not_ruled` — the screen then says the
    axis is not decided — rather than raising a 500 or picking a shape."""
    answer = _service_priced_on("moon_dust")
    assert answer == {"shape": "not_ruled", "capacity_uom": None, "size_count": None}
    assert _service_priced_on(None) == {
        "shape": "not_ruled",
        "capacity_uom": None,
        "size_count": None,
    }


def test_it_reads_no_price_and_no_plan():
    """The guarantee this file exists to keep: the answer depends on the SERVICE
    CODE and on nothing else — no tenant, no plan, no amount, no database row.
    A second call with the same code cannot differ, and a money column moving
    cannot move this."""
    first = _service_priced_on("fire")
    second = _service_priced_on("fire")
    assert first == second
    assert "amount" not in first and "price" not in first


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-089 §6 wave H (H3) · BR-MET-1166 · CR-063 · DEF-3098
# generated: 2026-09-09 by the CR-089 wave H lane
# gates: RED PROVED FIRST through pytest — quoted in this module's docstring.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
