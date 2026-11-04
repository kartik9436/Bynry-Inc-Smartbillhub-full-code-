# ── Trace ──────────────────────────────────────────────
# Change:   CR-039 wave E task 20 — seed the ratified size-class bands. PO
#           verbatim 2026-08-27: *"Water (has 4) Pipe diameter keep the four;
#           add 1½" · 3" · 4" · 6" - you need 1 inch 2 inch also 5 inch also;
#           rest all are correct in this"*   Screens: S8 (Settings → Configure
#           → Reference data → Utility service size classes)
# Rules:    BR-TEN-171 (the forty ratified classes and the two unbanded
#           dimensions) · BR-TEN-170 (the list is the utility service size
#           class) · BR-TEN-071 (insert-if-absent, never DELETE) · BR-TEN-072
#           (renames forbidden in seed data) · BR-TEN-077 (a content change
#           needs a version bump, in the same commit) · BR-RAT-015 (sewer is a
#           share of the water usage charge — why it carries no size class)
# Tests:    this file
# Impacts:  apps/tenancy/service_size_classes.py · apps/tenancy/fixtures/
#           lookup_defaults.json · apps/tenancy/reference_sweep.py
#           (RATIFIED_FIXTURE_DIGESTS — TC8 no longer pins a serial at all, it
#           pins the version/content RELATIONSHIP; DEF-3104's prevention, done
#           2026-09-02 when the V2.48.0.5 bump made the literal stale a third time)
# ───────────────────────────────────────────────────────
"""BR-TEN-171 — the ratified figures, asserted so drift goes RED.

The sign-off rule of 2026-08-11 asks for two things and this file is the second:
the ruling is written into the record verbatim (decision log, BR-TEN-171,
`service_size_classes.py`) **and a test asserts the ratified figure**. Every
number below was shown to the Product Owner service by service and answered on.

⚠ **THE HARDEST THING THIS FILE PROTECTS IS A ZERO.** Three services seed no
size class and the reasons are NOT the same reason:

  * **sewer — RULED to have none.** It is priced as a share of the water usage
    charge (BR-RAT-015) and reads no register, so there is nothing to size.
  * **battery — RULED to have none since 2026-09-01 (`DEF-2408`).** The PO
    DISSOLVED `OQ-561` on 2026-08-27: *"(a) multiplier replaces bands for
    capacity services (solar, battery, thermal); bands stay for pipe/amp/CFH -
    this si corect"*. It was in the NOT-RULED group below until then, and for
    those five days **a battery account could not be billed at all** — the ruling
    had reached the register and not the code.
  * **thermal steam — NOT RULED (OQ-560).** The proposal said *"steam by
    thousand pounds per hour"*: a unit, and no boundary.

In the platform fixture all three look identical — a service with no rows. The
test that matters here is the one that proves they are NOT identical in code:
sewer and battery RETURN an empty tuple and steam RAISES. A lane that "finishes
the list" by giving steam three bands would be inventing which base charge a
customer pays; a lane that leaves a DISSOLVED question raising stops a whole
service billing, which is the other half of the same discipline and the more
expensive one.
"""

import json
from pathlib import Path

import pytest
from apps.tenancy import reference_sweep, service_size_classes

FIXTURE = Path(__file__).resolve().parents[1] / "apps/tenancy/fixtures/lookup_defaults.json"

#: BR-TEN-171 — the ratified count per service, exactly as put to the PO.
#: A figure changing here without a PO ruling is the drift this file exists for.
RATIFIED_COUNTS = {
    "electric": 6,
    "water": 9,
    "gas": 4,
    "sewer": 0,  # RULED to have none — BR-RAT-015
    "trash": 7,
    # CR-062 A3 — five property sizes, reversing four ERU bands; + `SW-FLAT`
    # "Flat" 2 ERU, PO ruling 2026-10-03 (option A: charged per unit).
    "storm_water": 6,
    "solar": 10,  # CR-062 A1/A4 — ten panel types, withdrawing four inverter bands
    "broadband": 3,
    # ⚠ **THERMAL WENT 3 → 8 ON 2026-09-07 AND THE THREE THAT LEFT WERE
    # BANDS.** `CR-080`, PO verbatim: *"connected tonnage - it is capacity not
    # metering; i will ahve 100 tonne or 200 tonne etc"*. The three `TH-CW-*`
    # rows were RANGES ("≤25 tons", "25–100", "100+") and a range has no single
    # value a capacity could be, so the ruling that makes thermal capacity-based
    # withdraws them by arithmetic rather than by preference. Eight connected
    # tonnages replace them, `TH-T5` through `TH-T800`.
    #
    # **This pays the debt the 2026-08-27 ruling left** — *"multiplier replaces
    # bands for capacity services (solar, battery, thermal)"* named thermal and
    # thermal was the one of the three never executed.
    #
    # ⚠ Still CHILLED WATER only. Steam is `OQ-560` and is untouched: the
    # ruling moved the service's BASIS and stated no steam boundary.
    "thermal_heat": 8,  # chilled water only; steam is still OQ-560
    "battery": 6,  # CR-062 A2/A5 — a CATALOGUE of capacities, not bands
    # ⚠ **FIRE WAS SEVEN UNTIL 2026-09-03 AND THE PRODUCT OWNER TOOK ONE OUT.**
    # PO verbatim: *"remove private hydrants from list"*. `HYD` "Private
    # hydrant", priced `$25.0000`, is withdrawn — a hydrant is an ASSET, not a
    # utility-service size — and fire's count is the six line diameters that
    # remain. **This is the one number on this table a PO ruling has MOVED
    # DOWNWARD**, and it superseded a worked figure signed the day before: the
    # warehouse with a 6" line and two hydrants was `$110.00` and is now
    # `$60.00`, `−$50.00` a month on that customer.
    #
    # ⚠ **THE SIX ARE STILL ROWS THE PRODUCT OWNER HAS NEVER RATIFIED AS A
    # PRICE LIST (`CR-063`, `OQ-1360` OPEN).** Every other count here traces to
    # the ruling of 2026-08-27 or to `CR-062`'s two reversals; fire's were
    # authored by the CR-063 lane as a seeded default a tenant edits on Settings,
    # because a real utility is being onboarded and the product needed a list
    # before the customer could give us theirs. **Removing a row is not
    # ratifying the rest**: `OQ-1360` stays OPEN. Asserted anyway — the point is
    # that the DEFAULT cannot drift silently, whatever the numbers turn out to
    # be, and the day the customer's own list arrives it lands here.
    "fire": 6,  # CR-063 as amended 2026-09-03 — six line diameters, no hydrant
}
#: 59 − thermal's three withdrawn RANGES + its eight connected tonnages = 64
#: (`CR-080`, PO 2026-09-07). It was 59 from 2026-09-03. + storm water's
#: `SW-FLAT` (PO 2026-10-03) = 65.
RATIFIED_TOTAL = 65


def test_br_ten_171_tc1__every_service_carries_its_ratified_count():
    for service, expected in RATIFIED_COUNTS.items():
        got = len(service_size_classes.size_classes_for_service(service))
        assert got == expected, f"{service}: ratified {expected}, found {got}"
    assert len(service_size_classes.seed_entries()) == RATIFIED_TOTAL


def test_br_ten_171_tc2__water_is_nine_and_the_five_inch_is_the_POs_own():
    """*"Pipe diameter keep the four; add 1½" · 3" · 4" · 6" - you need 1 inch
    2 inch also 5 inch also"*.

    The 5" is the single figure on the whole ratified table that came from the
    Product Owner rather than from an industry-convention list, so it is
    asserted by name: a later lane "tidying" the sequence back to a convention
    that never had it goes RED here.
    """
    water = dict(service_size_classes.size_classes_for_service("water"))
    assert list(water.values()) == [
        'Water 5/8"',
        'Water 3/4"',
        'Water 1"',
        'Water 1½"',
        'Water 2"',
        'Water 3"',
        'Water 4"',
        'Water 5"',
        'Water 6"',
    ]
    assert water["W-5"] == 'Water 5"'


def test_br_ten_171_tc3__the_four_codes_seeded_before_today_keep_their_codes():
    """BR-TEN-072: renames are forbidden in seed data — add the new code,
    deactivate the old. `W-1` and `W-2` are the two the PO said to keep, and
    `G-250` keeps its *"(residential)"* suffix although the ratified table reads
    a bare "250 CFH": tightening a shipped NAME reaches nobody (BR-TEN-071) and
    changing a shipped CODE inserts a duplicate beside the tenant's row.
    """
    rows = {r["code"]: r["name"] for r in service_size_classes.seed_entries()}
    assert rows["W-58"] == 'Water 5/8"'
    assert rows["W-1"] == 'Water 1"'
    assert rows["W-2"] == 'Water 2"'
    assert rows["G-250"] == "Gas 250 CFH (residential)"
    assert rows["CART-96"] == "Trash 96-gallon cart"


def test_br_ten_171_tc4__the_bare_three_phase_code_leaves_the_fixture():
    """`E-3P` "Electric 3φ" is not in the ratified electric list — that names 3φ
    **200A** and 3φ **400A**, and a bare 3φ is neither.

    Removing it from the platform fixture means no NEW tenant receives it.
    BR-TEN-071 deletes it from nobody: a tenant that already has the row keeps
    it, deactivatable on S8 and never resurrected by a later sweep.
    """
    codes = {r["code"] for r in service_size_classes.seed_entries()}
    assert "E-3P" not in codes
    assert {"E-3P-200", "E-3P-400"} <= codes


@pytest.mark.parametrize("service", ["sewer"])
def test_br_ten_171_tc5__a_ruled_empty_service_says_so_by_RETURNING(service):
    """The zeros that ARE decisions. They answer with an empty tuple, which is a
    different act from refusing to answer — see TC-6.

    ⚠ **BATTERY JOINED SEWER HERE ON 2026-09-01 (`DEF-2408`) AND CAME OUT OF
    TC-6.** It is `()` because the PO DISSOLVED `OQ-561` on 2026-08-27 —
    *"(a) multiplier replaces bands for capacity services (solar, battery,
    thermal); bands stay for pipe/amp/CFH - this si corect"* — so there are no
    boundaries to state, and no boundary was invented to put it here. Until the
    ruling reached the code a battery account could not be billed at all: the
    run stopped on `SizeClassNotRuled` at its first account.
    """
    assert service_size_classes.size_classes_for_service(service) == ()
    assert service not in service_size_classes.UNBANDED_SERVICE_DIMENSIONS


@pytest.mark.parametrize(
    ("call", "oq"),
    [
        (lambda: service_size_classes.steam_size_classes(), "OQ-560"),
    ],
)
def test_br_ten_171_tc6__an_unbanded_dimension_refuses_and_names_its_question(call, oq):
    """The zero that is NOT a decision.

    *"rest all are correct in this"* ratified the DIMENSION the PO was shown and
    not boundaries nobody wrote — a signature covers only what was shown (PO
    2026-08-11). The refusal carries the OQ-ID so the prime directive's rule
    holds in code, and G8 can read it.

    ⚠ **THIS LIST HELD TWO ENTRIES UNTIL 2026-09-01 AND NOW HOLDS ONE.** Battery
    moved to TC-5 above; thermal STEAM is the only dimension left that nobody has
    ruled. It is kept parametrized deliberately — the shape is what makes adding
    the next one a one-line change rather than a new test.
    """
    with pytest.raises(NotImplementedError) as caught:
        call()
    assert oq in str(caught.value)


def test_br_ten_171_tc7__the_fixture_is_a_MIRROR_of_the_ratified_law():
    """The whole reason the constant exists beside the fixture.

    A flat `{code, name}` fixture cannot say which SERVICE a row belongs to, nor
    which services have none for which reason. Those facts are the ruling, so
    they live in `service_size_classes.py` and the fixture mirrors it — and a
    row edited in one place and not the other fails here rather than shipping.
    """
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["service_size_classes"] == service_size_classes.seed_entries()


def test_br_ten_171_tc8__the_bump_and_the_content_landed_together():
    """BR-TEN-077. A fixture edited without a version bump reaches NOBODY and
    looks like it worked; the guard refuses rather than warns. Asserted here as
    well as in the sweep suite because THIS is the change that bumped it.

    ⚠ **THE SERIAL READ `V2.48.0.3` AND THIS CASE WAS RED FROM THE MERGE THAT
    CHANGED IT UNTIL 2026-09-02 (`DEF-3104`).** `lookup_defaults.json`'s own
    note records why: *"RENUMBERED FROM V2.48.0.3 AT MERGE … two lanes each took
    the next free FIXTURE SERIAL … the size-class lane merged first and keeps
    0.3"*. The fixture moved to `V2.48.0.4` — `BR-TEN-150`'s five
    `owner_categories`, PO 2026-08-27 — and this literal did not, so the size-
    class suite carried a permanent failure over a version STRING. **A gate that
    is permanently red is a gate that is off** (`DEF-490`), and the cost is that
    a lane running this suite sees red before its change and red after it.

    **Nothing is being hidden by moving the number:** the second assertion is
    the CONTENT check and it has passed throughout — the fixture and its
    ratified digest agree, and only this literal was stale.

    ⚠ **AND THE SERIAL IS NO LONGER PINNED HERE AT ALL — `DEF-3104`'s own
    prevention, DONE rather than reported, on 2026-09-02 by the lane that hit
    it (`DEF-3098` / CR-062's fixture handover).** That paragraph said a fixture
    serial is ALLOCATION and not law, that two lanes can each take the next free
    one, and that pinning it turns every merge-time renumber into a failure in
    an unrelated suite. The very next bump — `V2.48.0.4` -> `V2.48.0.5`, this
    CR's 40 -> 53 rows — made this case red for the third time over a version
    STRING, which is the point at which "reported" stops being enough.

    **WHAT IS ASSERTED INSTEAD IS THE RELATIONSHIP, WHICH IS THE WHOLE OF
    BR-TEN-077 AND IS STRICTLY STRONGER THAN THE LITERAL WAS.** The declared
    version must be well-formed under the current grammar, and the fixture's
    CONTENT must hash to the digest ratified for THAT version. A content change
    with no bump still fails, loudly, naming the rule — which is the defect this
    case exists to catch. A merge that renumbers the serial no longer fails,
    because nothing here claims to know which number was free.

    **Nothing is being hidden by dropping the number:** the second assertion
    below is the CONTENT check and it has passed throughout — the fixture and
    its ratified digest agree, and only the literal was ever stale.
    """
    version = reference_sweep.fixture_version()
    assert reference_sweep.FIXTURE_VERSION_RE.match(version), (
        f"the fixture declares {version!r}, which is not BR-TEN-077's grammar "
        "(a literal V and four numeric parts, PO ruling 2026-08-17)"
    )
    assert reference_sweep.assert_fixture_version_matches_content() == version


def test_br_ten_171_tc9__every_ratified_code_is_unique_and_none_is_blank():
    rows = service_size_classes.seed_entries()
    codes = [r["code"] for r in rows]
    assert len(set(codes)) == len(codes)
    assert all(r["code"].strip() and r["name"].strip() for r in rows)


def test_br_ten_171_tc10__every_service_is_accounted_for():
    """No service may be silently absent. Each of CLAUDE.md's ten is either in
    the ratified map (with bands, or ruled empty) or in the unbanded register
    (with an OQ) — never in neither, which is how a service would quietly seed
    nothing and nobody be told."""
    for service in service_size_classes.SERVICE_ORDER:
        ratified = service in service_size_classes.RATIFIED_SERVICE_SIZE_CLASSES
        unbanded = service in service_size_classes.UNBANDED_SERVICE_DIMENSIONS
        assert ratified != unbanded, f"{service} is in neither register or in both"
    # ELEVEN since CR-063 (BR-RAT-024 amended 2026-09-02, `fire` APPENDED at 11).
    assert len(service_size_classes.SERVICE_ORDER) == 11


def test_br_ten_171_tc11__an_unknown_service_is_a_KeyError_not_an_empty_answer():
    """A typo must not read as "this service has no size classes"."""
    with pytest.raises(KeyError):
        service_size_classes.size_classes_for_service("hydrogen")


def test_br_ten_171_tc12__every_key_is_a_REAL_service_code_from_the_platform_catalog():
    """The bug this case was written for, caught before it left the branch.

    `RATIFIED_SERVICE_SIZE_CLASSES` first keyed thermal as **`thermal`**. The
    platform catalog stores **`thermal_heat`** (`tenancy/migrations/0001_initial.py`
    `SERVICE_SEED`, BR-RAT-024) — CLAUDE.md's prose name is *Thermal/Heat* and the
    CODE is not the prose. So `size_classes_for_service("thermal_heat")` raised
    `KeyError`, the three ratified chilled-water classes were unreachable by their
    own service's name, and **every other case in this file still passed**: they
    all ask the module about itself, so a wrong key is self-consistently wrong.

    Only a comparison against the CATALOG can see it. This also catches the
    reverse — a service added to the platform and never given a size-class
    verdict, which would seed nothing with nobody told.

    The migrations are loaded by path because their module names start with a
    digit; reading the SEED lists themselves (rather than the `services` table)
    keeps this a pure unit test and pins the RATIFIED codes rather than whatever
    a fixture happens to hold.

    ⚠ **IT READ `0001_initial.py` ALONE UNTIL 2026-09-02 AND THAT DEFEATED ITS
    OWN ARGUMENT (`DEF-3092`, fourth site).** The paragraph above says only a
    comparison against the CATALOG can see a wrong key — and `0001` has run on
    every database that exists, so it can never gain a row and an ELEVENTH
    service has to arrive in its own migration (`CR-063` put `fire` in `0033`).
    Pointed at one file this case was comparing against ten elevenths of the
    catalogue: it would have passed on a `SERVICE_ORDER` that omitted fire
    entirely, which is precisely the *"a service added to the platform and never
    given a size-class verdict, which would seed nothing with nobody told"* case
    the docstring promises to catch. **Every tenancy migration is read now**, in
    migration-number order, so a twelfth needs no edit here.
    """
    import importlib.util

    migrations = Path(__file__).resolve().parents[1] / "apps/tenancy/migrations"
    catalog: list[str] = []
    for path in sorted(migrations.glob("[0-9][0-9][0-9][0-9]_*.py")):
        spec = importlib.util.spec_from_file_location(f"_tenancy_{path.stem}_tc12", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for attr in ("SERVICE_SEED", "FIRE_SEED"):
            catalog.extend(code for code, _name in getattr(module, attr, ()))

    assert catalog, f"no service seed found under {migrations} — the authority moved"
    assert list(service_size_classes.SERVICE_ORDER) == catalog
