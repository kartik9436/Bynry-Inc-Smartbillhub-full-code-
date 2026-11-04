# ── Trace ──────────────────────────────────────────────
# Change:  CR-077 (PO 2026-09-07) — a tax-jurisdiction set for every state the
#          sign-up form offers, named but NOT priced.
# Story:   US-TEN-002 (reference-data seeding) · US-TEN-006 (S8 Regional)
#          Screens: S8 Regional · S13 Taxes & fees · PLN-03 step 5
# Rules:   BR-TEN-012 (versioned fixture, per-list idempotent, tenant-touched
#          rows never overwritten) · BR-TEN-013/031 (the OWNING module seeds) ·
#          BR-TEN-037 (a tenant's own jurisdiction registry) · BR-TEN-077 (the
#          fixture's content and its declared version must agree) · CR-010's
#          tax ruling (PO 2026-08-17, the County/City/Special-district
#          scaffold) · DEF-444 (a state recorded AFTER sign-up must still be
#          delivered) · DEF-127 (blank is not zero)
# Tests:   this file
# Impacts: apps/tenancy/fixtures/lookup_defaults.json · apps/tenancy/services
#          .tax_jurisdiction_entries · apps/rating.services.seed_reference_list
# ───────────────────────────────────────────────────────
"""CR-077 — fifty states of tax jurisdictions, and not one tax rate.

**THE REQUEST, PO 2026-09-07, verbatim:** *"Can you have Tax jurisdictions -
for all states - atleast 1 - you seed based on customer selection - if they
select Iowa you seed in Iowa, but you ahve to ahve a list for all 50 states"*,
and on the shape — *"the right jurisdictions and the right authority names for
all 50 states, and the rates left blank for the utility to fill in"* — *"yes
this is good - you can have 0 filled in"*.

⚠ **THE HARD PART IS THE HALF THAT IS ABSENT, SO THAT IS WHAT MOST OF THIS FILE
ASSERTS.** The Texas set this grew out of carries five worked figures — 6.25 %,
2.00 %, $0.85 per bill, 1.50 %, $0.25/kgal — and a named county (Bexar), none
of which was ever checked against a real utility. Fifty states of that is fifty
states of invented tax computing plausible, wrong bills wearing the authority of
something the product shipped. So every new jurisdiction carries its name, its
level and its authority and **no rate at all**, and `test_not_one_new_state_
carries_a_figure_of_any_kind` is the assertion that says so about the catalogue
rather than about one worked example.

⚠ **AND BLANK IS NOT ZERO (`DEF-127`).** A NULL rate means nobody has answered
yet and the screen can refuse to bill on it. A `0.00` rate means the answer is
*none*, which is a real tax position: it bills silently at nothing and looks
deliberate. Nothing here seeds a zero.

RED-FIRST PROOF (r11 step 2d), quoted from `pytest` — the harness that runs
these — against the tree BEFORE the fixture change, `7 failed, 7 passed`:

    E  AssertionError: 51 of the 52 states the sign-up form offers have no tax
       jurisdictions of their own: ['AK', 'AL', 'AR', 'AZ', 'CA', 'CO', 'CT',
       'DC', 'DE', 'FL', 'GA', 'HI', 'IA', 'ID', 'IL', 'IN', 'KS', 'KY', 'LA',
       'MA', 'MD', 'ME', 'MI', 'MN', 'MO', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH',
       'NJ', 'NM', 'NV', 'NY', 'OH', 'OK', 'OR', 'PA', 'PR', 'RI', 'SC', 'SD',
       'TN', 'UT', 'VA', 'VT', 'WA', 'WI', 'WV', 'WY']

    E  AssertionError: AK has 0 own jurisdiction(s), expected at least 2

    E  AssertionError: set()
       assert set() == {'Iowa Depart...s Commission'}
       Extra items in the right set:
       'Iowa Utilities Commission'
       'Iowa Department of Revenue'

and, on the database side, `test_a_tenant_that_names_iowa_holds_iowas_
authorities`, `test_recording_iowa_later_still_delivers_them` (DEF-444, fifty
times over), `test_the_repair_door_delivers_a_late_recorded_iowa` and
`test_a_tenant_that_declined_reference_defaults_still_gets_nothing`.

⚠ **THE SEVEN THAT PASSED IN THAT RUN ARE NOT DECORATION AND ONE OF THEM WAS
WRONG.** `test_a_tenant_that_declined…` failed on the sentence
`'the tenant records no US state'` rather than on the opt-in refusal it is
named for: the payload said `state=None`, and `deliver_state_tax_jurisdictions`
checks the state BEFORE the seed-run row. It was red for the right test and the
wrong reason, which reads identically in a summary line. The payload now names
Iowa.
"""

import pytest

from apps.rating import models as rating_models
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    audit_actions,
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: CR-010's rate-less scaffold (PO 2026-08-17) — merged into EVERY state's set
#: by `tax_jurisdiction_entries`, so it is subtracted before this file counts a
#: state's own rows.
SCAFFOLD = {"County", "City", "Special district"}

#: The one state whose rows the Product Owner ruled and priced (DEF-254 /
#: DEF-273, 2026-08-18, from prototype r10's own tax table). CR-077 does not
#: touch it, and several assertions below exclude it BY NAME so that "no rate
#: anywhere" cannot be read as "the ruled Texas rates were quietly dropped".
PRICED_STATE = "TX"

#: The two Iowa authorities the PO's own example asks for.
#:
#: ⚠ **IT IS THE IOWA UTILITIES *COMMISSION*, NOT THE IOWA UTILITIES BOARD, AND
#: THE DIFFERENCE IS THE WHOLE REASON A NAME MAY NOT BE RECALLED FROM MEMORY.**
#: The agency was the Iowa Utilities Board for 38 years and was renamed on
#: 2024-07-01 under Iowa's government reorganisation (Senate File 2385); board
#: members became commissioners and the site moved to iuc.iowa.gov. Seeding the
#: old name would put a body that no longer exists on a remittance screen.
IOWA = {"Iowa Department of Revenue", "Iowa Utilities Commission"}

#: Every key on a fixture `taxes` entry that states MONEY. A new state's entry
#: may carry none of them, and it may not carry a `taxes` block at all.
MONEY_KEYS = ("rate", "flat_amount", "per_unit_amount", "per_meter_amount")


def _fixture():
    return services._load_seed_fixture()


def _own_rows(state_code: str) -> list[dict]:
    """A state's OWN entries — the shared scaffold subtracted."""
    entries = services.tax_jurisdiction_entries(_fixture(), state_code)
    return [row for row in entries if str(row.get("name", "")) not in SCAFFOLD]


def _jurisdictions(tenant) -> set[str]:
    with tenant_ctx(tenant):
        return set(
            rating_models.TaxJurisdiction.objects.filter(tenant_id=tenant.id).values_list(
                "name", flat=True
            )
        )


def _tax_count(tenant) -> int:
    with tenant_ctx(tenant):
        return rating_models.Tax.objects.filter(tenant_id=tenant.id).count()


def _admin(tenant):
    from types import SimpleNamespace

    from apps.tenancy import models as tenancy_models

    owner = tenancy_models.Tenant.objects.get(pk=tenant.pk)
    return SimpleNamespace(id=None, role="system_admin", tenant=owner)


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE CATALOGUE — read off the fixture, no database needed
# ══════════════════════════════════════════════════════════════════════════


def test_every_state_the_signup_form_offers_has_its_own_jurisdictions():
    """*"you ahve to ahve a list for all 50 states"* — measured against the
    platform's OWN state vocabulary rather than against a list typed here.

    `tenancy.selectors.US_STATES` is what the sign-up form accepts: the fifty
    states plus DC and Puerto Rico, and nothing else. A state a utility can
    select and cannot be seeded for is the DEF-444 shape one layer up, so the
    two lists are pinned to each other and a future state added to one without
    the other fails HERE, by name.
    """
    offered = sorted(set(tenancy_selectors.US_STATES.values()))
    missing = [code for code in offered if not _own_rows(code)]
    assert not missing, (
        f"{len(missing)} of the {len(offered)} states the sign-up form offers have no tax "
        f"jurisdictions of their own: {missing}"
    )


def test_every_state_names_a_revenue_authority_and_a_utility_commission():
    """The minimum CR-077 promises per state, and both halves are named rather
    than counted: two rows is not the same fact as *the right two*."""
    for code in sorted(set(tenancy_selectors.US_STATES.values())):
        rows = _own_rows(code)
        assert len(rows) >= 2, f"{code} has {len(rows)} own jurisdiction(s), expected at least 2"
        for row in rows:
            assert str(row.get("name", "")).strip(), f"{code} has a nameless jurisdiction"
            assert row.get("level"), f"{code}: {row.get('name')} states no level"
        if code == PRICED_STATE:
            continue  # r10's own transcription, ruled separately — see below
        authorities = {str(row.get("authority") or "") for row in rows}
        assert all(authorities), f"{code} has a jurisdiction with no authority: {rows}"
        # A revenue body and a regulator, told apart by the words they use for
        # themselves — the two things a utility remits to and answers to.
        #
        # ⚠ `Finance` IS IN THIS LIST BECAUSE OF ARKANSAS, AND THAT IS THE CHECK
        # EARNING ITS KEEP RATHER THAN A LOOSENING. This assertion went red on
        # `AR names no revenue authority: ['Arkansas Department of Finance and
        # Administration', ...]` — which is the right body: Arkansas collects
        # through DFA's Revenue Division and has no "Department of Revenue" to
        # name. The word was added after checking the state, not to make a red
        # go away.
        assert any(
            word in name
            for name in authorities
            for word in (
                "Revenue",
                "Taxation",
                "Tax",
                "Treasury",
                "Comptroller",
                "Hacienda",
                "Finance",
            )
        ), f"{code} names no revenue authority: {sorted(authorities)}"
        # ⚠ `Bureau` IS HERE BECAUSE OF PUERTO RICO — the same shape as
        # Arkansas above, found the same way. It went red on `PR names no
        # utility commission: [..., 'Puerto Rico Energy Bureau']`, and the
        # Energy Bureau IS Puerto Rico's regulator; it simply calls itself a
        # bureau. Stated rather than absorbed silently: PR's regulator covers
        # ENERGY, so a water utility on the island answers elsewhere and the
        # operator edits the row, which is what an editable seeded name is for.
        assert any(
            word in name
            for name in authorities
            for word in ("Commission", "Authority", "Board", "Bureau", "Utilities", "Utility")
        ), f"{code} names no utility commission: {sorted(authorities)}"


def test_not_one_new_state_carries_a_figure_of_any_kind():
    """⚠ **THE POINT OF THE WHOLE CHANGE, ASSERTED OVER THE CATALOGUE RATHER
    THAN OVER ONE EXAMPLE.**

    A rate nobody checked is worse than no rate: it computes a plausible,
    wrong bill and never asks anybody to look. So every state CR-077 added
    carries a name, a level and an authority and states NO `taxes` block —
    which is stronger than "no figure", because the rating seeder can only mint
    a `taxes` row from a `taxes` entry.
    """
    keyed = _fixture()["tax_jurisdictions"]
    offenders = []
    for state_code, rows in sorted(keyed.items()):
        if state_code in (PRICED_STATE, "ALL"):
            continue
        for row in rows:
            for tax in row.get("taxes") or []:
                offenders.append(f"{state_code} · {row.get('name')} · {tax.get('name')}")
            for key in MONEY_KEYS:
                if row.get(key) is not None:
                    offenders.append(f"{state_code} · {row.get('name')} · {key}")
    assert not offenders, (
        "CR-077 seeds NAMES, never figures — a seeded rate nobody checked bills real "
        f"customers real money: {offenders}"
    )


def test_the_ruled_texas_rates_are_still_there():
    """The mirror of the assertion above, and it is not decoration.

    "No rate anywhere" is one wrong grep away from "the five figures the PO
    ruled on 2026-08-18 were deleted". Texas keeps them.
    """
    rows = _fixture()["tax_jurisdictions"][PRICED_STATE]
    rates = [tax.get("rate") for row in rows for tax in row.get("taxes") or []]
    assert "6.25" in rates and "2.00" in rates and "1.50" in rates


def test_iowa_gets_its_own_two_authorities_by_name():
    """The Product Owner's own worked example, spelled out so it cannot drift
    into a placeholder."""
    names = {str(row["name"]) for row in _own_rows("IA")}
    assert names == IOWA, names
    for row in _own_rows("IA"):
        assert row["authority"] == row["name"]
        assert row["level"] == "state"


def test_the_scaffold_still_reaches_every_state():
    """CR-010's 2026-08-17 ruling (*"a and B - default available"*) is not
    reversed by CR-077: County · City · Special district still arrive beside a
    state's own rows, so the LEVELS are visible on S13 with no figure at all."""
    for code in ("IA", "CA", "PR", "DC", PRICED_STATE):
        names = {str(row["name"]) for row in services.tax_jurisdiction_entries(_fixture(), code)}
        assert SCAFFOLD <= names, code


def test_a_tenant_that_named_no_state_still_gets_the_scaffold_and_nothing_else():
    """`ALL` remains the fallback, unchanged — a fixture that guessed a state
    would be inventing where money is remitted."""
    names = {str(row["name"]) for row in services.tax_jurisdiction_entries(_fixture(), None)}
    assert names == SCAFFOLD


# ══════════════════════════════════════════════════════════════════════════
# 2 · WHAT A UTILITY ACTUALLY RECEIVES
# ══════════════════════════════════════════════════════════════════════════


def test_a_tenant_that_names_iowa_holds_iowas_authorities(
    growth_plan, identity_seam, audit_rows
):
    """Provisioning, end to end: *"if they select Iowa you seed in Iowa"*."""
    tenant, _ = provisioned_tenant(brazosbend_payload(state="Iowa", subdomain="iowaco"))
    held = _jurisdictions(tenant)
    assert IOWA <= held, held
    assert SCAFFOLD <= held
    assert held == IOWA | SCAFFOLD, "an Iowa tenant holds five jurisdictions and no others"


def test_an_iowa_tenant_is_given_no_tax_rate_at_all(growth_plan, identity_seam, audit_rows):
    """⚠ **BLANK, NOT ZERO — `DEF-127`.** The rows arrive; not one `taxes` row
    does, so PLN-03 step 5 has authorities to offer and no figure to bill on,
    and a human is asked for the number. A seeded `0.00` would have looked
    deliberate and billed silently at nothing."""
    tenant, _ = provisioned_tenant(brazosbend_payload(state="Iowa", subdomain="iowarates"))
    assert _tax_count(tenant) == 0


def test_a_texas_tenant_is_unchanged(growth_plan, identity_seam, audit_rows):
    """The ruled state keeps its seven jurisdictions and its priced rows, so
    this change is provably additive."""
    tenant, _ = provisioned_tenant()
    assert len(_jurisdictions(tenant)) == 7
    assert _tax_count(tenant) > 0


# ══════════════════════════════════════════════════════════════════════════
# 3 · DEF-444, NOW FIFTY TIMES OVER
# ══════════════════════════════════════════════════════════════════════════
# The sign-up form does not require a state. A tenant provisioned without one
# gets the `ALL` scaffold and a seed-run row at the current fixture version, and
# before DEF-444's fix it could then NEVER receive its own state's rows — not
# from a re-run, not from a version bump, not from the `--tenant` repair door.
# That fix is `tax_jurisdictions` being exempt from the run-row latch
# (`services.RERUN_REFERENCE_LISTS`), and it was only ever asserted for Texas.
# Fifty more states now depend on it, and the failure is SILENT: the symptom is
# "No tax jurisdictions exist yet" at plan wizard step 5 and nobody billable.


def test_recording_iowa_later_still_delivers_them(growth_plan, identity_seam, audit_rows):
    """The DEF-444 path, on a state that is not the one it was fixed for."""
    tenant, _ = provisioned_tenant(brazosbend_payload(state=None, subdomain="lateiowa"))
    assert _jurisdictions(tenant) == SCAFFOLD  # the premise: Iowa's are absent

    with tenant_ctx(tenant):
        services.save_regional_settings(_admin(tenant), {"state": "Iowa"})

    held = _jurisdictions(tenant)
    assert IOWA <= held, f"DEF-444: Iowa's own authorities never arrived — {held}"
    assert _tax_count(tenant) == 0, "and still not one rate"
    assert "reference.seeded" in audit_actions(audit_rows)


def test_the_repair_door_delivers_a_late_recorded_iowa(growth_plan, identity_seam, audit_rows):
    """`manage.py seed_demo --tenant <sub>` — the operator's door for a tenant
    that already exists. It read the seed-run row and skipped until DEF-444."""
    tenant, _ = provisioned_tenant(brazosbend_payload(state=None, subdomain="repairiowa"))
    tenant.state = "Iowa"
    tenant.save(update_fields=["state"])

    with tenant_ctx(tenant):
        summary = services.seed_reference_data_for_tenant(
            tenant, _admin(tenant), structural_only=False
        )

    assert IOWA <= _jurisdictions(tenant)
    assert summary["seeded"].get("tax_jurisdictions", 0) > 0


def test_a_replay_on_an_iowa_tenant_writes_nothing(growth_plan, identity_seam, audit_rows):
    """BR-TEN-010. Re-offering this one list on every run is only safe while a
    run that changes nothing LOOKS like a run that changed nothing."""
    tenant, _ = provisioned_tenant(brazosbend_payload(state="Iowa", subdomain="iowareplay"))
    before = _jurisdictions(tenant)
    with tenant_ctx(tenant):
        summary = services.seed_reference_data_for_tenant(
            tenant, _admin(tenant), structural_only=False
        )
    assert _jurisdictions(tenant) == before
    assert "tax_jurisdictions" not in summary["seeded"]


def test_a_tenant_that_declined_reference_defaults_still_gets_nothing(
    growth_plan, identity_seam, audit_rows
):
    """OQ-088's rule survives the fifty-fold growth: until
    `reference_defaults_opted_in` exists, *"declined"* and *"did not exist
    yet"* are the same absence, so a tenant with no seed-run row for this list
    receives nothing however many states the catalogue now holds."""
    tenant, _ = provisioned_tenant(
        # The state IS named, so the refusal below is the OPT-IN one and not the
        # no-state one — `deliver_state_tax_jurisdictions` checks the state
        # first, and a `state=None` payload would have this test passing on the
        # wrong sentence (found by reading its RED output rather than its
        # summary line).
        brazosbend_payload(load_defaults=False, state="Iowa", subdomain="noiowadefaults")
    )
    assert _jurisdictions(tenant) == set()
    with tenant_ctx(tenant):
        result = services.deliver_state_tax_jurisdictions(tenant, _admin(tenant))
    assert result["delivered"] == 0
    assert "opted in" in result["reason"]
    assert _jurisdictions(tenant) == set()


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-077 (12-governance/11-change-requests.md) + the decision log of
#         2026-09-07 + BR-TEN-012/013/031/037/077 + DEF-444 + DEF-127 +
#         CLAUDE.md hard rules 1, 2 and 7
# generated: 2026-09-07 by the tenant-provisioning lane
# checklist: A✔ B✔ C✔ D=deferred(no API half — provisioning and the S8 Regional
#            save are both already served) E=deferred(no frontend half — the
#            screens that were empty now have input) F✔ G✔ H=deferred(PO
#            2026-08-09)
# gates: pytest tests/test_cr077_fifty_state_tax_jurisdictions.py
# exceptions: the sign-up form still does not REQUIRE a state (DEF-444's own
#             stated exception, unchanged) · Texas keeps r10's naming (`Texas
#             State`, `Local`) while the fifty-one new sets name their
#             authorities directly — a ruled transcription is not restyled by a
#             lane
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
