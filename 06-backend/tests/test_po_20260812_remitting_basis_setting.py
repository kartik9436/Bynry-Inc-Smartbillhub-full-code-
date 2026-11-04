# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-014 (S41 dual-basis remittance — TC-2, the per-authority
#           basis) · US-TEN-009 (the S71 rule-page card it lives on)
#           Screens: S71 (Settings → Configure → Finance controls, where the
#           tenant picks) · S41 (where the choice is stated)
# Rules:    BR-LED-002 (BOTH bases always computed; a per-authority setting
#           picks the remitting basis) · BR-LED-013 (billed · collected ·
#           remitted · outstanding per authority) · BR-BIL-069 (each authority
#           has its OWN 2200-nn account — so the account IS the authority) ·
#           BR-TEN-024 · CLAUDE.md rule 1
# Golden:   LE-3 — 47.38 billed / 20.97 collected; State 13.87 · County 2.22 ·
#           City 4.44 · PUC 0.44. US-LED-014 TC-2: *"State = collected; County
#           = billed"*.
# ───────────────────────────────────────────────────────
"""The per-authority remitting basis has somewhere to live (PO 2026-08-12).

**PO verbatim:** *"E Remit on what you BILLED, not what you collected - this is
also correct"* — said after ruling that the allocation sequence becomes a tenant
setting. Read together: BOTH bases are legitimate and WHICH applies is the
customer's to set, per authority, exactly as BR-LED-002 already said.

What was missing was never the computation. `apps/ledger/reporting.py` computed
both columns and carried a live problem code —
`per_authority_remitting_basis_is_not_stored` — because the report could show a
utility both figures and could not record which one they file on.

This file asserts the storage, its refusals, and the thing that makes it real:
**the report STATES the tenant's choice.** LE-3's own shape is the case, because
it is the one a default gets wrong — State on collected, County on billed, in
the same month, for the same tenant.
"""

from decimal import Decimal

import pytest

from apps.ledger import journal, reporting
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from core import errors

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    LE3_AUTHORITIES,
    ensure_authority_accounts,
    make_accounts,
    post_le3_authorities,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

FINANCE_CONTROLS = "finance-controls"
KEY = "tax_remitting_basis_by_authority"

STATE = "2200-01"
COUNTY = "2200-02"
CITY = "2200-03"
PUC = "2200-04"

#: US-LED-014 TC-2 verbatim: *"State = collected → remit-now figure 13.87;
#: County = billed"*.
TC2_CHOICE = {STATE: "collected", COUNTY: "billed"}
LE3_STATE_BILLED = Decimal("13.87")
LE3_COUNTY_BILLED = Decimal("2.22")


def the_four_authorities(tenant, actor):
    accounts = make_accounts(actor, tenant, {})
    authorities = ensure_authority_accounts(tenant, actor)
    post_le3_authorities(tenant, accounts, authorities)
    return accounts, authorities


# ═══════════════════════════════════════════════════════════════════════════
# 1 — the choice has somewhere to live, and NOTHING is chosen for the tenant
# ═══════════════════════════════════════════════════════════════════════════
def test_po_20260812__the_remitting_basis_map_is_a_tenant_setting_on_s71(brazos):
    """S71 Finance controls carries the per-authority map, and it ships EMPTY.

    Empty, never seeded with a basis: LE-3 puts State on collected and County
    on billed in the same month, so any shipped default is wrong for one of
    them in its first month. Unset means unset (hard-won law 3).
    """
    with tenant_ctx(brazos):
        page = tenancy_selectors.settings_family(FINANCE_CONTROLS)
    assert page[KEY] == {}


def test_po_20260812__the_two_bases_are_the_ledgers_own_vocabulary(brazos):
    """`billed` / `collected` are `apps.ledger.journal.REMITTING_BASES` — the
    same two strings `record_tax_remittance` already accepts. A second spelling
    of a basis is a filing on the wrong one."""
    from apps.tenancy import settings_families

    assert tuple(settings_families.REMITTING_BASES) == journal.REMITTING_BASES


@pytest.mark.parametrize(
    "bad,why",
    [
        ({STATE: "accrual"}, "a basis no rule names"),
        ({STATE: "Billed"}, "the vocabulary is exact, not case-folded"),
        ({STATE: None}, "unset is expressed by absence, never by a null value"),
        ({"": "billed"}, "an authority with no account code"),
        ({STATE: ["billed"]}, "a basis is one string"),
        ([STATE, "billed"], "the setting is a map, not a list"),
    ],
)
def test_po_20260812__a_basis_outside_the_signed_pair_is_refused(brazos, dana, bad, why):
    """BR-LED-002 names two bases and the ledger accepts two. A third value
    stored here would reach a filing screen as a basis nothing can compute."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            tenancy_services.save_settings_family(dana, FINANCE_CONTROLS, {KEY: bad})
        assert tenancy_selectors.settings_family(FINANCE_CONTROLS)[KEY] == {}


def test_po_20260812__a_tenant_picks_a_basis_per_authority(brazos, dana):
    """US-LED-014 TC-2's own pair, stored: State collected, County billed."""
    with tenant_ctx(brazos):
        saved = tenancy_services.save_settings_family(dana, FINANCE_CONTROLS, {KEY: TC2_CHOICE})
        assert saved[KEY] == TC2_CHOICE
        assert tenancy_selectors.settings_family(FINANCE_CONTROLS)[KEY] == TC2_CHOICE


# ═══════════════════════════════════════════════════════════════════════════
# 2 — THE ONE THAT MATTERS: the REPORT states the chosen basis
# ═══════════════════════════════════════════════════════════════════════════
def test_po_20260812__the_report_states_each_authoritys_chosen_basis(brazos, dana):
    """**THE WIRING TEST.** US-LED-014 TC-2: *"State = collected → remit-now
    figure 13.87; County = billed"*.

    Before this lane every row came back `remitting_basis=None` and the report
    declared `per_authority_remitting_basis_is_not_stored`. Now the row states
    what the tenant filed under, per authority, in the same month — which is the
    case a single default gets wrong.
    """
    with tenant_ctx(brazos):
        the_four_authorities(brazos, dana)
        tenancy_services.save_settings_family(dana, FINANCE_CONTROLS, {KEY: TC2_CHOICE})

        report = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)
        by_code = {row.code: row for row in report["rows"]}

        assert by_code[STATE].remitting_basis == journal.BASIS_COLLECTED
        assert by_code[COUNTY].remitting_basis == journal.BASIS_BILLED
        # The figures are untouched — the basis says which column they FILE on.
        assert by_code[STATE].billed == LE3_STATE_BILLED
        assert by_code[COUNTY].billed == LE3_COUNTY_BILLED
        # …and the two nobody has ruled on stay honestly unset.
        assert by_code[CITY].remitting_basis is None
        assert by_code[PUC].remitting_basis is None


def test_po_20260812__the_problem_code_names_only_the_authorities_still_unset(brazos, dana):
    """The report keeps declaring the gap while any authority has no basis —
    and stops when every one of them does.

    A code that never cleared would be noise; a code that cleared on the first
    save would hide the two authorities nobody had ruled on. So it names them.
    """
    with tenant_ctx(brazos):
        the_four_authorities(brazos, dana)

        report = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)
        gap = next(
            item
            for item in report["unavailable"]
            if item["code"] == "per_authority_remitting_basis_is_not_stored"
        )
        assert gap["authorities"] == (STATE, COUNTY, CITY, PUC)

        tenancy_services.save_settings_family(dana, FINANCE_CONTROLS, {KEY: TC2_CHOICE})
        partial = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)
        gap = next(
            item
            for item in partial["unavailable"]
            if item["code"] == "per_authority_remitting_basis_is_not_stored"
        )
        assert gap["authorities"] == (CITY, PUC)

        every = {code: journal.BASIS_BILLED for code, _name, _amount in LE3_AUTHORITIES}
        tenancy_services.save_settings_family(dana, FINANCE_CONTROLS, {KEY: every})
        settled = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)
        codes = {item["code"] for item in settled["unavailable"]}
        assert "per_authority_remitting_basis_is_not_stored" not in codes
        assert all(row.remitting_basis == journal.BASIS_BILLED for row in settled["rows"])


def test_po_20260812__an_unreadable_setting_reports_unset_rather_than_a_basis(
    brazos, dana, monkeypatch
):
    """The report's refusal direction, asserted rather than described (law 1).

    This is the OPPOSITE direction from `payments.tenant_class_order`, which
    raises — and the asymmetry is deliberate, so it is pinned here. A report is
    read-only and its whole contract is that a figure it cannot stand behind is
    reported as unavailable WITH A REASON. "the tenant has not chosen" and "we
    could not read the choice" both mean the same thing to a finance officer
    looking at S41: do not file on a basis this screen made up.
    """
    from apps.tenancy import selectors as tenancy_selectors

    with tenant_ctx(brazos):
        the_four_authorities(brazos, dana)
        tenancy_services.save_settings_family(dana, FINANCE_CONTROLS, {KEY: TC2_CHOICE})
        monkeypatch.setattr(tenancy_selectors, "settings_family", None, raising=False)

        report = reporting.remittance_by_authority(start=JULY_START, end=JULY_END)

        assert all(row.remitting_basis is None for row in report["rows"])
        gap = next(
            item
            for item in report["unavailable"]
            if item["code"] == "per_authority_remitting_basis_is_not_stored"
        )
        assert gap["authorities"] == (STATE, COUNTY, CITY, PUC)
        # …and the money is untouched: an unreadable SETTING is not an
        # unreadable LEDGER.
        assert {row.code: row.billed for row in report["rows"]}[STATE] == LE3_STATE_BILLED


def test_po_20260812__one_tenants_choice_never_reaches_another(brazos, lonestar, dana, erin):
    """CLAUDE.md rule 1. The map is a tenant setting on the tenant's own row —
    Brazos filing on collected must not put Lone Star Ridge on collected."""
    with tenant_ctx(brazos):
        tenancy_services.save_settings_family(dana, FINANCE_CONTROLS, {KEY: TC2_CHOICE})
        assert tenancy_selectors.settings_family(FINANCE_CONTROLS)[KEY] == TC2_CHOICE
    with tenant_ctx(lonestar):
        assert tenancy_selectors.settings_family(FINANCE_CONTROLS)[KEY] == {}
