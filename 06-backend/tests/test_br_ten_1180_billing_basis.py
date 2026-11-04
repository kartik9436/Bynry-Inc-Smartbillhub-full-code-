# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2409 (high, PO, 2026-09-01) — "everything is metered that is not
#           curent even if utility service is not started". Two faults: the
#           column was never named at signup, and it is a BOOLEAN where the
#           product has THREE pricing types.
#           DEF-3230 (high, PO, 2026-09-02) — seven of the ten services also ship
#           a unit of measure that cannot produce a bill.
# Rules:    BR-TEN-1180 (a service declares ONE of three billing bases; the
#           platform seeds the ruled default for all ELEVEN — fire appended
#           2026-09-02 by CR-063) · SUPERSEDES
#           BR-RAT-081 · BR-RAT-015 (sewer is a share of the water usage charge)
#           · BR-RAT-090 (a capacity service's quantity is a COUNT of assets)
# Story:    US-TEN-007 / US-TEN-008 (S8 Services & UoM)      Screens: S8 (SET-03)
# ───────────────────────────────────────────────────────
"""THE PO's SIGNED TABLE, ASSERTED SERVICE BY SERVICE, BY NAME.

⚠ **IT WAS TEN ROWS UNTIL 2026-09-02 AND IT IS ELEVEN.** `CR-063` appended
**fire** — capacity, billed in `connection`s — under a dated amendment to
`BR-RAT-024`, because a real utility is being onboarded and it sells fire
protection. Nothing above it moved and no service changed sides.

WHY THIS FILE EXISTS, AND IT IS `DEF-3230`'s ESCAPE REASON WORD FOR WORD
------------------------------------------------------------------------
**No check in this repo compared a service's seeded unit of measure against how
that service is actually priced.** Every existing check reads ONE side:

* `G47` asserts the SIGNUP SCREEN offers all ten services, and a vitest test
  pins that list to the migration seed — so a utility can buy any of the ten.
* `test_service_billing_coverage.py` provisions one tenant per service and
  counts issued bills, which is how `DEF-2396` and `DEF-2397` were both caught
  — **but a service that bills the WRONG UNIT still bills, so it reads as a
  pass.**
* `_derive_uom_service_scope` carries a careful docstring about which unit
  belongs to which service, and derives every word of it from a map whose
  entries had never been verified against a price.

So seven of the ten shipped with a unit that cannot produce a bill: gas priced
per `ccf` while its meter read `therm`, trash and broadband seeded `month` when
both are billed by a COUNT of capacity units, storm water seeded `kgal` when it
is billed per `ERU`, and sewer, solar and battery seeded nothing at all.

WHAT IT ASSERTS, AND WHY IT IS A TABLE AND NOT TEN CASES
---------------------------------------------------------
`SIGNED_TABLE` below is the PO's ruling transcribed. Every service is measured
BEFORE any assertion fires and the whole table is printed in the failure — a
loop that asserted per iteration would report the first divergence and hide the
other nine, which on a seed change is the difference between *"solar got a
unit"* and *"solar got a unit and water lost one"*. That is
`test_service_billing_coverage.py`'s own discipline and it is borrowed on
purpose.

RED PROVED FIRST (hard-won law 7)
----------------------------------
**MEASURED, NOT IMAGINED — and the number this file first CLAIMED was wrong.** The proof
provisions a real tenant with `SERVICE_DEFAULT_UOMS` monkeypatched back to the seven-entry
map this work replaced, and with the basis left to the model default the way
`_enable_signup_services` behaved before it named the column — i.e. the exact pre-change
seeding. `test_the_platform_seeds_the_signed_table_for_every_service` then says:

    AssertionError: 7 of 10 services are not seeded the way the PO signed them on 2026-09-02:
      gas            primary is 'therm', the table says 'ccf'
      gas            alt is 'ccf', the table says 'therm'
      sewer          basis is 'metered', the table says 'share'
      trash          basis is 'metered', the table says 'capacity'
      trash          primary is 'month', the table says 'cart'
      storm_water    basis is 'metered', the table says 'capacity'
      storm_water    primary is 'kgal', the table says 'ERU'
      solar          basis is 'metered', the table says 'capacity'
      solar          primary is None, the table says 'kW'
      broadband      basis is 'metered', the table says 'capacity'
      broadband      primary is 'month', the table says 'Mbps'
      battery        basis is 'metered', the table says 'capacity'
      battery        primary is None, the table says 'kW'

⚠ **THIS DOCSTRING FIRST CLAIMED "8 of 10" AND LISTED A LINE THAT CANNOT EXIST** — `sewer
primary is None, the table says None`, which is two equal values reported as a difference.
It was written from reasoning rather than from a run. **Seven is the right number** because
electric, water and thermal/heat were already correct and sewer differs on the basis alone.
The distance between the two is small and the lesson is not: a quoted failure nobody
produced is hard-won law 1 wearing a test's clothes.

⚠ **ONE CELL OF THAT MEASURED OUTPUT WAS EDITED AFTERWARDS AND IT IS SAID HERE RATHER THAN
LEFT TO BE SPOTTED:** the run happened while solar's signed unit was `panel`, so its line
read *"the table says 'panel'"*. `CR-062` statement (6) then changed solar to `kW` and the
line above is updated to match. **Nothing else moved** — the count is still seven, the other
twelve lines are byte-for-byte what the run printed, and solar was wrong before and after
(it was seeded no unit at all). The re-run confirms it.

and `test_no_unit_is_scoped_one_way_here_and_another_way_in_the_fixture` is
GREEN on the old map and on the new one, which is the point of it: it is the
drift guard, not the ruling.

⚠ **THE `basis` HALF ALONE WOULD HAVE BEEN RED FOR A SECOND REASON before
`_enable_signup_services` named the column** — every row took the model default,
so even `sewer` on a tenant that had been through Settings read `metered`. That
is `DEF-2409`'s FIRST fault and this file cannot tell the two apart, deliberately:
the PO reported one symptom and both causes produce it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.tenancy import models, selectors, services

# `import *` is how every module in this suite picks up the shared FIXTURES
# (`growth_plan`, `audit_rows`, …) — pytest resolves a fixture by name in the
# test module's own namespace, so an explicit import of the helper functions
# alone leaves `growth_plan` unresolved and every case that names it ERRORS
# rather than fails, which is what the first run of this file did.
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db

#: The PO's ruling of 2026-09-02, transcribed. `(basis, primary, alt)`.
#:
#: Verbatim, in the order it was said:
#:   *"Shall we consider Metered, % of service and Capacity based; Storm water -
#:   it is capacity based not unmetered , capaicyt is decided based on sizes of
#:   propoerty; Trash - it is capacity based and Cart sizes will decide price X
#:   how many Cart; Solar - is also capacity based - 1 panel capacity X # of
#:   Solar panels ; Broadband - It will be capacity based - ; Thermal/Heat -
#:   Metered; Battery - capacity based - you ahve to udpaet it - show me final
#:   table"*
#: and, on battery's `kW`: *"Im okay with it"*.
#:
#: ⚠ **SOLAR IS `kW` AND NOT `panel`, AND THAT IS A SUPERSESSION INSIDE ONE
#: SESSION (`CR-062` statements (4) → (6)).** The PO first approved `panel` — a
#: COUNT, exactly like carts — and then corrected it:
#:
#:   *"In solar youa re still not doing it correctly - For example We have 10
#:   Types of Solar panel with various capaity 1 Kw, 2Kw 3Kw 4Kw so and SO forth
#:   ; on given Unit we have installed 3 panels with 2Kw, 4Kw and 8 Kw , it means
#:   the totla capacity will be 14 Kw ; rate will be for 1 Kw = 14 $ per KW then
#:   bill should be 14 X 14 = 156 $"*
#:
#: Panels come in different sizes, so **counting them loses the thing being
#: sold**: 2 kW + 4 kW + 8 kW is **14 kW**, and a count says *"3"*. The unit is
#: therefore `kW`, the same one battery carries. ⚠ **The quote's arithmetic is
#: off by one product: 14 kW at `$14.00` is `$196.00`, not `$156`** — the PO was
#: told so in the same session and did not dispute it, and `CR-062` records the
#: correction rather than letting a wrong figure become a test's assertion.
#:
#: ⚠ **THIS TUPLE IS TYPED OUT RATHER THAN IMPORTED FROM
#: `services.SERVICE_DEFAULT_UOMS`, AND THAT IS THE WHOLE VALUE OF THE FILE.**
#: Importing the map would assert that the code equals itself, which is the
#: shape of a check that cannot fail. The ruling is the independent statement;
#: the map is the thing under test. When the two disagree, one of them is wrong
#: and a human decides which — a lane may not "fix" this constant to match the
#: code without a PO re-sign, because it IS the signature.
#:
#: The order is `BR-RAT-024`'s seed order, so the failure report reads like the
#: table the PO was shown.
SIGNED_TABLE: dict[str, tuple[str, str | None, str | None]] = {
    "electric": ("metered", "kWh", "kW"),
    "water": ("metered", "kgal", "ccf"),
    "gas": ("metered", "ccf", "therm"),
    # ── CR-081 · THIS ROW'S UNITS CHANGED ON 2026-09-08, BY A RE-SIGN ───────
    # ⚠ **A RULING, NOT A LANE "FIXING" THE SIGNATURE TO MATCH THE CODE** (the
    # note above is honoured, as CR-080's row below honours it). The PO
    # re-signed sewer's basis via HUMAN-GUIDE §6 on 2026-09-08 (`CR-081`,
    # `ace95d812`): sewer bills 90% of the water VOLUME, so it has a quantity
    # and, by hard rule 3, a unit — WATER'S, `kgal` / `ccf`. The basis stays
    # `share`. This row read `("share", None, None)` and was red from that
    # commit until the billing red triage of 2026-10-01.
    "sewer": ("share", "kgal", "ccf"),
    "trash": ("capacity", "cart", None),
    "storm_water": ("capacity", "ERU", None),
    "solar": ("capacity", "kW", None),
    "broadband": ("capacity", "Mbps", None),
    # ── CR-080 · THIS ROW CHANGED SIDES ON 2026-09-07, AND IT IS THE FIRST
    #    TIME A SERVICE HAS ─────────────────────────────────────────────────
    # ⚠ **A RULING, NOT A LANE "FIXING" THE SIGNATURE TO MATCH THE CODE.** The
    # note above this constant forbids exactly that, and it is honoured: this
    # row moves because the PRODUCT OWNER moved it, twice, in their own words.
    #
    # PO verbatim, 2026-09-07: *"connected tonnage - it is capacity not
    # metering; i will ahve 100 tonne or 200 tonne etc"*, and in the same
    # message *"it is capacity based - please make a note and figure out the
    # impact - if you ahve to write a CR to ahndle this please write"*.
    # Confirmed the same day in their eleven-service walk: *"Thermal — basis
    # disputed - this si correct"*.
    #
    # ⚠ **AND IT IS A DEBT BEING CALLED IN.** The PO ruled on **2026-08-27**:
    # *"(a) multiplier replaces bands for capacity services (solar, battery,
    # thermal); bands stay for pipe/amp/CFH - this si corect"*. Thermal was
    # named there and was the one of the three never executed —
    # `apps/tenancy/service_size_classes.py` recorded the omission against
    # itself for six days. **What this row reverses is a LANE judgment made
    # because the ruling had not reached the code.**
    #
    # **THE UNIT MOVES WITH THE BASIS, and that is not tidiness.** `ton-hr` is
    # an ENERGY — a ton of cooling delivered for an hour — and a capacity
    # service has no hours. Leaving it would quote a price per ton-hour against
    # a quantity in connected tons: `DEF-497`, one service over. `ton` is the
    # REFRIGERATION ton (12,000 BTU/hr), not the metric tonne.
    #
    # **`klb` STAYS IN THE ALT SLOT.** It is thermal STEAM's unit, `OQ-560` is
    # still open, and dropping it would make the map silent about steam.
    "thermal_heat": ("capacity", "ton", "klb"),
    "battery": ("capacity", "kW", None),
    # ── CR-063 · THE ELEVENTH ROW, APPENDED 2026-09-02 ──────────────────────
    # ⚠ **THIS ROW IS RULED AND IS NOT A LANE FILLING IN A GAP.** PO verbatim:
    # *"We will need Fire as utility Service - Capacity based - this will behave
    # exactly like trash - we will ahve to define sizes in settings"*, and
    # *"we have to do it ; curenlty we need it for one of the customer we want
    # to go live"*. `BR-RAT-024` is amended, dated, from ten services to ELEVEN
    # with fire APPENDED at position 11 and nothing renumbered.
    #
    # **`capacity` HERE IS TRASH'S ARITHMETIC AND NOT SOLAR'S**, which the
    # ruling settles in four words. This table records the BASIS and the UNITS;
    # which of the two capacity shapes a service uses is
    # `service_size_classes.capacity_uom_for_service`, and for fire it answers
    # `None` — the size PICKS the price and the COUNT multiplies it.
    #
    # The unit is `connection` and NOT `line`, because a private hydrant is not
    # a line and both are billed off this one tick (decision log 2026-09-02).
    "fire": ("capacity", "connection", None),
}

#: Four metered · one share · SIX capacity — the count the PO was shown, plus
#: fire (`CR-063`, 2026-09-02). ⚠ The split moved because a service was ADDED to
#: the catalogue under a dated amendment to `BR-RAT-024`, never because a
#: service changed sides: every one of the original ten reads exactly as it read
#: before. **A service moving from one basis to another is still a re-sign** and
#: this bump is not a precedent for one.
#: ⚠ **AND IT MOVED AGAIN ON 2026-09-07, THIS TIME BECAUSE A SERVICE DID
#: CHANGE SIDES — `CR-080`, thermal/heat from `metered` to `capacity`.** The
#: sentence above says *"A service moving from one basis to another is still a
#: re-sign and this bump is not a precedent for one"*, and that is honoured
#: rather than waived: this move has its own PO ruling, said twice on the day,
#: quoted verbatim on the row itself. `4/1/6` becomes `3/1/7`.
SIGNED_SHAPE = {"metered": 3, "share": 1, "capacity": 7}

FIXTURE = Path(__file__).resolve().parents[1] / "apps/tenancy/fixtures/lookup_defaults.json"


def _all_ten_tenant():
    """One tenant that sells every catalog service.

    ONE tenant rather than one per service, and the reason is that this file asks a question
    about the SEED and not about the estate: `_enable_signup_services` writes a
    row for EVERY catalogue service whichever ones are ticked (New mandate 4, PO
    2026-08-17), so one tenant per service would measure the same rows over and
    over and cost that many sample plants. `test_service_billing_coverage.py` is the file that
    legitimately needs one tenant per service, because it counts BILLS.
    """
    return provisioned_tenant(
        brazosbend_payload(
            subdomain="tenrowtable",
            name="Ten Row Table Utilities",
            services=sorted(SIGNED_TABLE),
            owner={
                "full_name": "Dana Whitfield",
                "email": "dana@tenrowtable.example.invalid",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )


def test_the_signed_table_covers_the_whole_catalogue_and_nothing_else():
    """The ruling and the platform catalogue name the SAME services.

    ⚠ **ELEVEN SINCE 2026-09-02** — `BR-RAT-024` amended, fire APPENDED at 11.

    This runs first and touches no database, because every other case in this
    file is meaningless if the table and the catalogue have drifted apart: a
    service in the catalogue and not in the table would be seeded by
    `_default_basis_for`'s fallback and never checked, which is exactly the gap
    `DEF-3230` was filed about (*"a service absent from this map is one the
    DESIGN has not named units for, not one we forgot"*).
    """
    catalogue = set(models.Service.objects.filter(active=True).values_list("code", flat=True))
    assert catalogue == set(SIGNED_TABLE), (
        "the PO's signed table and the active service catalogue disagree.\n"
        f"  in the catalogue and NOT signed: {sorted(catalogue - set(SIGNED_TABLE))}\n"
        f"  signed and NOT in the catalogue: {sorted(set(SIGNED_TABLE) - catalogue)}\n"
        "A service the ruling does not name is seeded by _default_basis_for's "
        "fallback and checked by nothing.\n"
        "⚠ THIS MESSAGE USED TO END 'take it to the PO, do not add a row here', "
        "FULL STOP, AND THAT NEARLY COST A LANE A DAY (CR-063). It is the right "
        "DEFAULT and it is wrong when the ruling already exists: read the "
        "module's 02-business-rules.md for this service FIRST. BR-RAT-024 is the "
        "row that names the catalogue, it is CONFIRMED-AS-AMENDED 2026-09-02 at "
        "ELEVEN services, and re-asking a question the repo has answered "
        "manufactures inconsistency rather than resolving it (CLAUDE.md law 13, "
        "the PO's own words). So: if BR-RAT-024 names this service, add its row "
        "here with the basis and units that rule states. If it does NOT, the "
        "ruling genuinely does not exist and only then does it go to the PO."
    )
    assert set(services.SERVICE_DEFAULT_UOMS) == set(SIGNED_TABLE), (
        "SERVICE_DEFAULT_UOMS and the signed table name different services. The map "
        "is what provisioning reads; the table is what the PO approved."
    )
    shape: dict[str, int] = {}
    for basis, _primary, _alt in SIGNED_TABLE.values():
        shape[basis] = shape.get(basis, 0) + 1
    assert shape == SIGNED_SHAPE, (
        f"the table now reads {shape} where the PO was shown {SIGNED_SHAPE} — four "
        "metered, one share, five capacity. A change to that split is a re-sign."
    )


def test_the_platform_seeds_the_signed_table_for_every_service(growth_plan, settings):
    """**THE ASSERTION `DEF-3230` ASKS FOR.** Ten services, one real signup, each
    row read back through the screen's own selector and compared with the ruling.

    ⚠ **READ THROUGH `selectors.service_row`, NOT THROUGH THE ORM.** That is the
    function S8 renders, so this asserts what a utility SEES on the screen the PO
    was looking at when they reported the defect — and it covers the read
    payload's contract (`billing_basis` present, `metered` gone) at the same time
    for free.
    """
    settings.JOBS_EAGER = False  # DEF-567 — no sample plant is needed to read a seed
    tenant, result = _all_ten_tenant()
    assert result["created"] is True

    found: dict[str, tuple[str, str | None, str | None]] = {}
    with tenant_ctx(tenant):
        for code in SIGNED_TABLE:
            row = selectors.service_row(code)
            found[code] = (row["billing_basis"], row["primary_uom"], row["alt_uom"])

    problems: list[str] = []
    for code, (basis, primary, alt) in SIGNED_TABLE.items():
        got_basis, got_primary, got_alt = found[code]
        if got_basis != basis:
            problems.append(f"{code:14} basis is {got_basis!r}, the table says {basis!r}")
        if got_primary != primary:
            problems.append(f"{code:14} primary is {got_primary!r}, the table says {primary!r}")
        if got_alt != alt:
            problems.append(f"{code:14} alt is {got_alt!r}, the table says {alt!r}")

    table = "\n  ".join(
        f"{code:14} {found[code][0]:9} {str(found[code][1]):8} {found[code][2]}"
        for code in SIGNED_TABLE
    )
    assert not problems, (
        f"{len({p.split()[0] for p in problems})} of {len(SIGNED_TABLE)} services are not "
        "seeded the way the PO signed them on 2026-09-02:\n  "
        + "\n  ".join(problems)
        + "\n\nwhat the tenant actually got:\n  "
        + table
    )


def test_the_read_payload_carries_billing_basis_and_no_longer_carries_metered(
    growth_plan, settings
):
    """The contract the S8 lane is building against — a CLEAN CUT, no shim.

    PO ruling 2026-09-02: *"we are in beta stage - so no real utility is actually
    onboarded yet - so there is no real data yet - hence you can fix it; I will
    delete the DB and relaunch"*. Serving both keys would let a screen keep asking
    the two-state question and get a confident answer for a service that is
    neither metered nor counted — `DEF-2409`, one layer up.
    """
    settings.JOBS_EAGER = False
    tenant, _ = _all_ten_tenant()
    with tenant_ctx(tenant):
        row = selectors.service_row("sewer")
    assert row["billing_basis"] == "share"
    assert "metered" not in row, (
        "the read payload still serves `metered`. It cannot: sewer is neither "
        "metered nor priced by a count, and a boolean answer for it is the defect."
    )


def test_the_write_path_takes_the_three_values_and_refuses_everything_else(
    growth_plan, settings
):
    """`PATCH /settings/services/<code>` — the contract, both halves.

    The refusal key is `settings.services.billing_basis_invalid` and it is named
    here rather than merely "some error", because the S8 lane renders THAT key
    and a test that accepts any refusal would pass while the screen showed a raw
    dotted key to a clerk (`G32`'s whole subject).
    """
    from core import errors

    from tests.test_us_met_helpers import staff_actor

    settings.JOBS_EAGER = False
    tenant, _ = _all_ten_tenant()
    with tenant_ctx(tenant):
        # A REAL identity row, not a synthetic uuid: `_audit` stamps
        # `actor_user_id`, which is a reviewed cross-module FK into `users`
        # (B2 §2). `staff_actor` reuses the address provisioning already wrote
        # rather than minting a second person at it — DEF-566 / DEF-2395.
        actor = staff_actor(tenant, "system_admin", "dana@tenrowtable.example.invalid")

        for value in ("metered", "share", "capacity"):
            saved = services.update_tenant_service(actor, "storm_water", {"billing_basis": value})
            assert saved["billing_basis"] == value, f"{value} was not stored"

        with pytest.raises(errors.ValidationError) as bad:
            services.update_tenant_service(actor, "storm_water", {"billing_basis": "unmetered"})
        keys = [f.get("message_key") for f in (bad.value.field_errors or [])]
        assert "settings.services.billing_basis_invalid" in keys, keys

        # The old field is not a synonym — it is unknown, and says so by name.
        with pytest.raises(errors.ValidationError) as gone:
            services.update_tenant_service(actor, "storm_water", {"metered": False})
        assert "settings.unknown_field" in [
            f.get("message_key") for f in (gone.value.field_errors or [])
        ]


def test_a_capacity_service_is_what_unmetered_service_codes_reports_and_share_is_not(
    growth_plan, settings
):
    """The one FILTER that had to choose between the three values.

    Being on this list means *no read is ever owed for this service*, which
    `BR-RAT-090` answers in exactly one way — a COUNT of the unit's assets. That
    is `capacity`. **`share` must NOT appear**: a sewer connection has no assets,
    so routing it here prices it at `$0.00` — which is the mispricing
    `DEF-2409` was filed to prevent, and the reason the boolean was widened.
    """
    settings.JOBS_EAGER = False
    tenant, _ = _all_ten_tenant()
    with tenant_ctx(tenant):
        reported = set(selectors.unmetered_service_codes())

    capacity = {c for c, (b, _p, _a) in SIGNED_TABLE.items() if b == "capacity"}
    assert reported == capacity, (
        f"unmetered_service_codes() reports {sorted(reported)}; the capacity services "
        f"are {sorted(capacity)}"
    )
    assert "sewer" not in reported, (
        "sewer is priced as a PERCENTAGE of the water usage charge (BR-RAT-015), not "
        "by counting anything. A sewer connection has no assets, so this list would "
        "price it at $0.00 — that is DEF-2409's exact mechanism."
    )


def test_no_unit_is_scoped_one_way_here_and_another_way_in_the_fixture():
    """THE DRIFT GUARD — the derived scope and the fixture must not contradict.

    `_seed_uoms` resolves a new row as `stated or SEEDED_UOM_SERVICE_SCOPE.get
    (code)`, so a fixture entry that CARRIES a `"service"` key silently overrides
    the derivation and one that does not is decided by it. **Both orders are
    correct today and neither is checked anywhere**, so the day somebody adds
    `"service": "storm_water"` to `kgal` — which the derivation now scopes to
    water — the two statements would disagree and the fixture would quietly win.

    No database: this compares two literals and must stay a millisecond, because
    that is what makes it cheap enough to sit in front of every seed change.
    """
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    derived = services.SEEDED_UOM_SERVICE_SCOPE

    problems: list[str] = []
    for entry in fixture["uoms"]:
        code = str(entry["code"])
        stated = entry.get("service")
        if stated is None:
            continue  # the derivation decides; there is nothing to contradict
        here = derived.get(code.lower())
        if here is not None and here != stated:
            problems.append(
                f"{code}: the fixture states {stated!r} and SERVICE_DEFAULT_UOMS derives "
                f"{here!r}. `_seed_uoms` would take the fixture's answer and the map "
                "would be silently wrong."
            )
    assert not problems, "\n  ".join(problems)

    # ⚠ **`panel` MUST NOT BE IN THE CATALOGUE — `CR-062` task B5.** It very
    # nearly was: the PO approved it as solar's unit (statement 4) and then
    # corrected the model (statement 6), because panels come in different sizes
    # and the billable quantity is the SUM of their capacities rather than a
    # count of them. This asserts the ABSENCE, so a lane re-reading the earlier
    # ruling and "finishing the job" goes red instead of shipping a unit no
    # service names.
    assert not [u for u in fixture["uoms"] if u["code"] == "panel"], (
        "`panel` is in the catalogue. CR-062 statement (6) superseded statement (4): "
        "solar is priced on the SUM of its panels' capacities in kW, not on how many "
        "panels there are, so `panel` is not a unit this product sells anything in."
    )
    assert "panel" not in derived

    # `kW` is named by THREE services now — electric's alt, battery's primary and
    # solar's primary — so it stays All-services. Asserted because the reason
    # changed even though the answer did not.
    assert derived.get("kw") is None, derived.get("kw")


def test_the_metered_property_answers_br_rat_081_from_the_new_column():
    """`row.metered` survives as a READ-ONLY derivation, and only `metered` is True.

    Thirty-odd call sites across ten backend files ask this question and keep
    working unchanged — that is what made the cut safe to land beside three lanes
    editing `apps/rating` and `apps/billing`. What must NOT survive is a write:
    `metered = False` was two answers wearing one word.
    """
    row = models.TenantService(billing_basis="metered")
    assert row.metered is True
    for basis in ("share", "capacity"):
        assert models.TenantService(billing_basis=basis).metered is False, basis

    with pytest.raises(AttributeError):
        models.TenantService(billing_basis="metered").metered = False
