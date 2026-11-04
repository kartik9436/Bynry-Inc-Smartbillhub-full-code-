# ── Trace ──────────────────────────────────────────────
# Change:   CR-039 wave E task 21 — rename the list. PO verbatim 2026-08-27:
#           *"Question 2 — is it a meter size class, or a service size class?
#           it is utility service size class"*   Screens: S8 (Settings →
#           Configure → Reference data)
# Rules:    BR-TEN-170 (the list is the UTILITY SERVICE size class, and where
#           the rename stops) · BR-TEN-078 (this list is NOT service-scoped) ·
#           BR-TEN-031 (the owning module validates; tenancy hosts)
# Tests:    this file
# Impacts:  apps/tenancy/services.py (SEED_LIST_OWNERS · LOOKUP_LISTS ·
#           ServiceSizeClassLookupHandler · HOSTED_LOOKUP_HANDLERS) ·
#           apps/tenancy/fixtures/lookup_defaults.json ·
#           07-frontend/src/features/tenancy/referenceDataConfig.ts
# ───────────────────────────────────────────────────────
"""BR-TEN-170 — the rename, pinned in every registry that carries the list code.

**WHY A RENAME NEEDED A TEST AT ALL.** The list code is a string repeated in four
backend registries, a fixture key, a frontend config entry, two i18n keys and an
API path, and NOTHING type-checks the agreement between them. The read-method
vocabulary went 5 → 8 the same week and needed eighteen files where its task
named five, two of which were found only by running the suite. So the four places
a stale `meter_size_classes` would still work — and quietly serve an empty card,
or seed a list nobody reads — are asserted here by name.

**AND THE TEST STATES WHERE THE RENAME DELIBERATELY STOPS.** The hosted TABLE is
still `meter_size_classes` and the model is still `MeterSizeClass` (DEF-970): a
table rename is a B2 schema change with a migration, four RLS policy renames and
its own review, and it is invisible to every user. TC-4 asserts that split
on purpose, so the next reader meets it as a recorded decision rather than as a
half-finished job.
"""

import json
from pathlib import Path

import pytest

from apps.tenancy import models, selectors, services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx

# CR-065's inverted TC-5 is the first case in this file that needs a real tenant
# (it asks the LIST what a fire schedule is offered). The marker is module-wide
# because pytest-django refuses a per-test opt-in from a plain function, and the
# other cases read registries and the fixture file and are unaffected by it.
pytestmark = pytest.mark.django_db

FIXTURE = Path(__file__).resolve().parents[1] / "apps/tenancy/fixtures/lookup_defaults.json"

LIST_CODE = "service_size_classes"
OLD_LIST_CODE = "meter_size_classes"


def test_br_ten_170_tc1__every_backend_registry_carries_the_new_code_and_not_the_old():
    """Four registries, and a stale entry in any one of them is a different
    silent failure: SEED_LIST_OWNERS decides whether the list is seeded at all,
    LOOKUP_LISTS whether `/lookups/{list}` resolves, HOSTED_LOOKUP_HANDLERS
    where the rows land, and the handler's `list_code` what the seed-run ledger
    and the audit row record."""
    owners = dict(services.SEED_LIST_OWNERS)
    assert owners.get(LIST_CODE) == "metering"
    assert OLD_LIST_CODE not in owners

    assert LIST_CODE in services.LOOKUP_LISTS
    assert OLD_LIST_CODE not in services.LOOKUP_LISTS
    assert services.LOOKUP_LISTS[LIST_CODE].owner == "metering"

    assert LIST_CODE in services.HOSTED_LOOKUP_HANDLERS
    assert OLD_LIST_CODE not in services.HOSTED_LOOKUP_HANDLERS

    handler = services.HOSTED_LOOKUP_HANDLERS[LIST_CODE]
    assert handler.list_code == LIST_CODE


def test_br_ten_170_tc2__the_fixture_key_moved_with_the_registries():
    """The registry and the fixture must agree or the list seeds NOTHING and
    reports success: `_seed_reference_data` reads `fixture.get(list_code, [])`,
    so a renamed registry over a stale fixture key is an empty list with a
    seed-run row saying it was done.

    ⚠ **THE COUNT IS A DELIBERATE LITERAL AND IS NOT THE SAME CHECK AS TC-7.**
    `test_br_ten_171_tc7` asserts the fixture EQUALS `seed_entries()`, which is
    the drift guard between the delivery and the law — and it passes happily
    when BOTH move together. This literal is the independent anchor: a row that
    leaves the ratified list takes a deliberate edit HERE to ship, which is what
    makes a withdrawal reviewable rather than incidental.

    **64 as of 2026-09-07.** `CR-080` withdrew thermal chilled water's three
    `TH-CW-*` BANDS — each a RANGE, and a range has no single value a capacity
    could be — and added EIGHT connected-tonnage capacities in their place, on
    the PO's ruling that thermal is capacity-based (*"connected tonnage - it is
    capacity not metering; i will ahve 100 tonne or 200 tonne etc"*). 59 − 3 + 8
    = 64. It is the last of the 2026-08-27 supersession debt.

    **59 as of 2026-09-03.** It moved twice on 2026-09-02 — `CR-062` group A
    took 40 to 53 (eight bands withdrawn, twenty-one capacities added) and
    `CR-063` took 53 to 60 (fire's seven bands, appended as the eleventh
    service) — and once on 2026-09-03, **the first time a PO ruling has moved it
    DOWN**: *"remove private hydrants from list"* withdrew `HYD` "Private
    hydrant", so fire went 7 → 6 and this literal went 60 → 59. Nothing else
    left, and no price on the six diameters moved.
    """
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert LIST_CODE in fixture
    assert OLD_LIST_CODE not in fixture
    # 65 from 2026-10-03: storm water's `SW-FLAT` "Flat" (PO, option A).
    assert len(fixture[LIST_CODE]) == 65


def test_br_ten_170_tc3__the_list_is_still_sample_content_under_the_S111_toggle():
    """The rename changed the NAME, not the seed classification. BR-TEN-067's
    six structural catalogues are unchanged, so a tenant that declined the
    defaults still gets no size classes — which is why V2.48.0.3 ships no
    migration (the `areas` reasoning, not the `account_statuses` one)."""
    assert LIST_CODE not in services.STRUCTURAL_REFERENCE_LISTS
    assert OLD_LIST_CODE not in services.STRUCTURAL_REFERENCE_LISTS


def test_br_ten_170_tc4__the_hosted_table_deliberately_keeps_the_OLD_name():
    """DEF-970, asserted rather than left to be discovered.

    BR-TEN-170 says the rename stops at storage: `list_code` is the name a
    person meets — the API path, the S8 card, the seed-run ledger — and the
    physical table is invisible to every user. If a later lane DOES rename the
    table, this assertion is the one that fails, which is the correct place for
    that conversation to start.
    """
    handler = services.HOSTED_LOOKUP_HANDLERS[LIST_CODE]
    assert handler.model is models.MeterSizeClass
    assert models.MeterSizeClass._meta.db_table == OLD_LIST_CODE


def test_br_ten_170_tc5__the_list_IS_now_scoped_and_the_ruling_that_did_it(
    growth_plan, identity_seam
):
    """⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-02 AND IT WAS RIGHT TO
    (CR-065).** It read *"the rename did not scope the list to a service"*, and
    the sentence under it — *"a service column would be BR-TEN-078 reopened
    without a ruling"* — is exactly the guard this repository wanted: `BR-TEN-078`
    named this list unscoped TWICE, deliberately, because size classes read as
    the strongest candidate for scoping, and a lane must not reopen that on its
    own judgement.

    **A RULING ARRIVED.** PO, 2026-09-02, verbatim, sent with a screenshot of the
    Fire rate schedule's minimum-bill step listing *Electric 3φ 400A*, *Electric
    CT-metered*, *Gas 250 CFH (residential)* and *Gas 1,000+ CFH* among the seven
    fire lines:

        "This is where we are setting rates for fire  you should show only
         capacity for fire . in Setting a capacity needs to tags to utility
         services ."

    Same list, same question, opposite answer, from the same person, later. So
    the case is INVERTED rather than deleted, and it keeps the same job pointing
    the other way: it now fails if the column or the tag ever quietly goes away.

    **BR-TEN-170's OTHER HALF IS UNTOUCHED AND IS RE-ASSERTED HERE**: a row still
    NAMES its service in its own display name (TC-6), which is now belt and
    braces rather than the only signal — and `uoms` is still scoped, because this
    ruling adds a second scoped list and reverses nothing about the first.
    """
    assert services.LOOKUP_LISTS["uoms"].code == "uoms"
    assert any(
        f.name == "service" for f in models.MeterSizeClass._meta.get_fields()
    ), "PO ruling 2026-09-02 — the size class names its utility service"
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        fire = [
            row["code"] for row in selectors.lookup_page(LIST_CODE, None, "fire")
        ]
    # SIX, not seven — PO 2026-09-03, *"remove private hydrants from list"*.
    # The screenshot that raised CR-065 showed seven fire rows; the seventh was
    # `HYD` "Private hydrant" and the PO has since withdrawn it. What this case
    # is FOR is unchanged: it fails if the service column or the tag ever
    # quietly goes away, and the number simply follows the ratified list.
    assert len(fire) == 6, "the PO's own screenshot: fire's schedule shows fire's sizes"
    assert "E-CT" not in fire and "G-250" not in fire


#: BR-TEN-078 leaves this list UNSCOPED, so a row's own name is the only thing
#: that says which service it belongs to. `Battery` and `Fire` joined the tuple on
#: 2026-09-02 — neither service had a single seeded row before that day, and both
#: name themselves exactly as the convention asks.
SERVICE_NAME_PREFIXES = (
    "Water",
    "Electric",
    "Gas",
    "Trash",
    "Storm water",
    "Solar",
    "Broadband",
    "Thermal",
    "Battery",
    "Fire",
)

#: The rows that legitimately do NOT name their service, each with the reason it
#: is exempt. **A code is here or the assertion fails** — that is what stops an
#: exemption becoming a hole, and it is why this is a dict rather than a skip.
UNPREFIXED_BY_RECORD = {
    # CR-062 group A, PO-approved 2026-09-02. The PO was shown these five names
    # AS THEY READ and approved them; they name the PROPERTY a clerk is looking
    # at, which is how storm water is actually sized. The cost — five rows among
    # sixty that do not say "Storm water" — is stated in full in
    # `apps/tenancy/service_size_classes.py`'s docstring and its exceptions line.
    # Reversing it is a one-line change per row and needs the PO, because the
    # names are theirs.
    "SW-SF": "storm water — the PO's own name, approved as it reads",
    "SW-DUP": "storm water — the PO's own name, approved as it reads",
    # PO 2026-10-03, verbatim: *"add a size for a single flat, e.g. "Flat" = 2 ERU"*.
    "SW-FLAT": "storm water — the PO's own name, ruled 2026-10-03",
    "SW-APT": "storm water — the PO's own name, approved as it reads",
    "SW-COM-S": "storm water — the PO's own name, approved as it reads",
    "SW-COM-L": "storm water — the PO's own name, approved as it reads",
    # ⚠ **`HYD` "Private hydrant" WAS THE LAST ENTRY HERE AND IS GONE, BECAUSE
    # THE ROW IT DESCRIBED IS GONE — PO 2026-09-03, *"remove private hydrants
    # from list"*.** It was carried by defect id (`DEF-3090`) rather than by
    # approval: fire's other six read `Fire line 2"` and name themselves, that
    # one read "Private hydrant" and said nothing about fire, and the rename
    # was parked on `OQ-1360` because renaming a seeded row is what `BR-TEN-072`
    # forbids. The PO removed the row instead, which discharges `DEF-3090`.
    # **Do NOT re-add it**: a register of divergences that lists a code the
    # product does not seed is a register that cannot fail on the real thing.
}


def test_br_ten_170_tc6__every_seeded_row_names_its_service_in_its_own_name():
    """The consequence of TC-5, and the thing that makes the unscoped list
    usable: with FIFTY-NINE rows across ten services on one card (sewer is ruled
    to have none), a row whose name did not say its service would be unreadable.
    It was sixty until 2026-09-03, when the PO removed `HYD` "Private hydrant"
    from fire's list — **and that row was the one entry in the exemption
    register below that was there by DEFECT rather than by approval, so the
    register shrank with it.**

    ⚠ **THIS CASE WAS BLIND FOR AS LONG AS THE DELIVERY WAS BEHIND, WHICH IS THE
    LESSON WORTH KEEPING (`DEF-3090`).** It reads the FIXTURE — the delivered
    copy — so while that file held the pre-CR-062 forty rows it was checking a
    list containing no storm-water property size and no fire row at all, and it
    passed. It went red the moment the mirror was regenerated on 2026-09-02, and
    it found two different things wearing the same shape: five names the PO
    approved themselves, and one nobody had ever looked at.

    **They were exempt for different reasons and only one was a decision**, which
    is exactly why they are listed by CODE with a reason rather than skipped by
    pattern — and the distinction paid off on 2026-09-03, when the PO deleted the
    row that was there by defect and left the five that were theirs. A NEW
    unprefixed row still fails here, because it is in neither list.
    """
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for row in fixture[LIST_CODE]:
        if row["code"] in UNPREFIXED_BY_RECORD:
            assert not row["name"].startswith(SERVICE_NAME_PREFIXES), (
                f"{row['code']} now names its service, so its exemption is stale — "
                f"remove it from UNPREFIXED_BY_RECORD "
                f"({UNPREFIXED_BY_RECORD[row['code']]})"
            )
            continue
        assert row["name"].startswith(SERVICE_NAME_PREFIXES), (
            f"{row} does not name its service, and BR-TEN-078 leaves this list "
            "unscoped so the name is the only thing that can. Either name it, or "
            "add it to UNPREFIXED_BY_RECORD with the ruling or defect that "
            "exempts it — never a bare skip."
        )
