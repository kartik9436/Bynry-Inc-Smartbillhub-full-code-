# ── Trace ──────────────────────────────────────────────
# Change:   CR-014 round 3 — the two group-3 journeys the round-2 record called
#           *"honest remaining work"* (T4-19, T7-14) and the one group-4 journey
#           it left open (T5-04). Builders in tests/journey_cohort_fixtures.py,
#           registered in 08-qa/01-e2e/stack/seed_journey_fixture.py.
# Rules:    DEF-556 / OQ-218 (no ISSUED bill may post a journal entry into the
#           finance-signed 2026-06-30 → 2026-07-31 window) · BR-BIL-004 (a draft
#           is not money, so a DRAFT's months are unconstrained) · BR-BIL-024
#           (due date = bill date + the cycle's due-days — never typed) ·
#           BR-IDN-029 (one address, one user row PER TENANT) · BR-TEN-042
#           (currency locks at the first financial record) · CLAUDE.md rule 1
#           (RLS FORCE — tenant B's rows are unreachable from tenant A).
# Golden:   The only typed money figures are the journeys' own dataset rows, and
#           the back-bill total is READ from
#           08-qa/01-e2e/expected/money-triples.csv rather than copied here.
# Red-proof: every case below was shown RED before it was made green; the
#           mutations and their verbatim failures are in the commit message and
#           the W11 lane report, 2026-08-22.
# ───────────────────────────────────────────────────────
"""Three cohorts, and the property each one exists to make true.

**T4-19** is a fixture about a WEEKDAY. Five calendar days and five business
days from the same due date only differ visibly when the due date is a Friday,
so a fixture whose bill B fell on a Tuesday would render, run, pass and prove
nothing — DEF-108's shape with a calendar instead of an empty table. The test
therefore asserts the weekday of an engine-produced due date, not the date.

**T7-14** is a fixture about a RATIO. Its trailing average must be BILLED (an
average nobody billed is a number this file made up) and its draft must sit
above 200% and below 350% of it, or the journey's threshold move from 200 to
350 changes nothing observable.

**T5-04** is a fixture about an ABSENCE ACROSS A BOUNDARY. The sweep asserts
that tenant B's rows cannot be reached from tenant A, and that assertion is
vacuous unless tenant B's rows EXIST. So the test both seeds them and proves
they are unreachable — the second half is what makes the first half worth
having.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from tests import journey_cohort_fixtures as cohort
from tests.isolation_helpers import rls, rls_probe_role  # noqa: F401 — fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The finance-signed window LE-1 books into. Nothing this round issues may
#: post a journal entry inside it (DEF-556).
SIGNED_START = date(2026, 6, 30)
SIGNED_END = date(2026, 7, 31)


def _signed_window_entries(tenant) -> int:
    from apps.ledger import models as ledger_models

    return ledger_models.JournalEntry.objects.filter(
        tenant=tenant,
        status=ledger_models.JE_POSTED,
        entry_date__gte=SIGNED_START,
        entry_date__lte=SIGNED_END,
    ).count()


# ── T4-19 · the two due dates, and the weekday that is the whole subject ────


def test_round3_t4_19__the_two_due_dates_are_a_monday_and_a_friday(brazos, dana):
    """*"bill A due Jul 20 … bill B due **Fri Aug 14** (the WE-15e weekday
    shape)"*, moved +70 days by this lane so neither issue lands in the signed
    window — ten whole weeks, which is the only shift that keeps a weekday.

    The due dates are asserted as WEEKDAYS because that is what the journey
    is about, and they are read off the ISSUED invoices because BR-BIL-024
    produces them; a fixture that wrote a due date would be asserting its own
    arithmetic rather than the engine's.
    """
    from apps.billing import models as billing_models

    with tenant_ctx(brazos):
        result = cohort.ensure_grace_pre_state(brazos, dana)

        due_dates = {}
        for label, invoice_no in (("A", result["bill_a"]), ("B", result["bill_b"])):
            invoice = billing_models.Invoice.objects.get(tenant=brazos, invoice_no=invoice_no)
            assert invoice.status == "issued", f"bill {label} is {invoice.status}, not issued"
            due_dates[label] = invoice.due_date

    assert due_dates["A"] == cohort.T419_A_DUE
    assert due_dates["A"].strftime("%A") == "Monday"
    assert due_dates["B"] == cohort.T419_B_DUE, (
        "bill B's due date is what makes calendar-grace and business-grace differ; the "
        "journey's WE-15e shape needs a FRIDAY"
    )
    assert due_dates["B"].strftime("%A") == "Friday"
    # The shift preserved the weekday of the paragraph's own dates, which is the
    # justification for having moved them at all.
    assert (due_dates["A"] - date(2026, 7, 20)).days == cohort.T419_SHIFT_DAYS
    assert (due_dates["B"] - date(2026, 8, 14)).days == cohort.T419_SHIFT_DAYS


def test_round3_t4_19__the_pre_change_grace_config_is_written_not_assumed(brazos, dana):
    """5 days, CALENDAR — the state before the journey's step 2 switch.

    They are BR-BIL-008's defaults, and they are written anyway: another
    journey's seeder may have edited the same settings page on the same stack,
    and a fixture that assumed a default it never wrote would start this
    journey in business mode with nothing saying so.
    """
    from apps.tenancy import selectors as tenancy_selectors

    with tenant_ctx(brazos):
        cohort.ensure_grace_pre_state(brazos, dana)
        family = tenancy_selectors.settings_family("billing-defaults")

    assert family["late_grace_days"] == cohort.T419_GRACE_DAYS
    assert family["late_grace_mode"] == cohort.T419_GRACE_MODE


# ── T7-14 · the trailing average, and the draft that clears it ──────────────


def test_round3_t7_14__the_trailing_average_is_billed_not_typed(brazos, dana):
    """Three ISSUED cycles at the money-triples `flat,cycle` figure.

    The guardrail compares a draft against what the account HAS been billed. A
    fixture that wrote 97.41 into a column would be comparing the engine's
    draft against this file's opinion, and would pass whatever the engine did.
    """
    from apps.billing import models as billing_models

    with tenant_ctx(brazos):
        result = cohort.ensure_guardrail_cohort(brazos, dana)
        issued = list(
            billing_models.Invoice.objects.filter(
                tenant=brazos,
                account__account_no=cohort.T714_ACCOUNT,
                status="issued",
            ).order_by("period_start")
        )

    assert len(issued) == len(cohort.T714_CYCLE_MONTHS)
    assert [invoice.period_start for invoice in issued] == [
        month[0] for month in cohort.T714_CYCLE_MONTHS
    ]
    for invoice in issued:
        assert Decimal(invoice.total).quantize(Decimal("0.01")) == cohort.FLAT_TOTAL
    assert result["trailing_average"] == str(cohort.FLAT_TOTAL)


def test_round3_t7_14__the_draft_sits_between_the_old_and_new_thresholds(brazos, dana):
    """*"above 200%, below 350% (both figures from money-triples)"*.

    This is the entire observable of T7-14: the threshold moves from 200 to 350
    and the SAME ratio stops being flagged. A draft below 200% or above 350%
    makes both runs agree and the journey proves nothing.
    """
    with tenant_ctx(brazos):
        result = cohort.ensure_guardrail_cohort(brazos, dana)

    expected = cohort.money_triples_row("flat", "backbill", "full")
    assert result["draft_total"] == expected["total"]
    ratio = Decimal(result["draft_total"]) / cohort.FLAT_TOTAL * 100
    assert ratio > Decimal("200"), f"{ratio}% is not above the old 200% threshold"
    assert ratio < Decimal("350"), f"{ratio}% is not below the new 350% threshold"
    assert result["guardrail_pct"] == cohort.T714_GUARDRAIL_PCT


def test_round3_t7_14__the_draft_is_a_draft_and_the_sibling_has_none(brazos, dana):
    """Two properties a journey cannot see, and both are load-bearing.

    **The draft is a DRAFT** — status `draft`, and no journal entry anywhere
    for its months. That is why its back-billed months may sit in the first
    half of 2026 while every ISSUED bill in this cohort had to move to August:
    BR-BIL-004 says a draft is not money, and DEF-556 constrains money.

    **The sibling has no draft.** T7-14 runs ACC-1131 *after* the settings
    change; a pre-seeded draft would have performed the journey's step 4 and
    the "not flagged under 350%" assertion would be about a stale evaluation.
    """
    from apps.billing import models as billing_models
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        result = cohort.ensure_guardrail_cohort(brazos, dana)
        draft = billing_models.Invoice.objects.get(
            tenant=brazos, invoice_no=result["draft_no"]
        )
        sibling_issued = billing_models.Invoice.objects.filter(
            tenant=brazos, account__account_no=cohort.T714_SIBLING, status="issued"
        ).count()
        sibling_drafts = billing_models.Invoice.objects.filter(
            tenant=brazos, account__account_no=cohort.T714_SIBLING, status="draft"
        ).count()
        posted_in_backbilled_months = ledger_models.JournalEntry.objects.filter(
            tenant=brazos,
            status=ledger_models.JE_POSTED,
            entry_date__gte=cohort.T714_BACKBILL_MONTHS[0][0],
            entry_date__lte=cohort.T714_BACKBILL_MONTHS[-1][1],
        ).count()

    assert draft.status == "draft"
    assert sibling_issued == len(cohort.T714_CYCLE_MONTHS), (
        "the sibling's situation is *identical* per the paragraph, which means the same "
        "billed trailing average — not an empty account"
    )
    assert sibling_drafts == 0, (
        "the sibling account already carries a DRAFT — T7-14 runs it AFTER the settings "
        "change, so seeding one performs the journey's own step 4 and the 'not flagged "
        "under 350%' assertion would be about a stale evaluation"
    )
    assert posted_in_backbilled_months == 0, (
        "something posted a journal entry into the back-billed months; a DRAFT must post "
        "nothing, and if it did, DEF-556 would apply to it"
    )


def test_round3_the_signed_july_window_is_untouched_by_this_round(brazos, dana):
    """The invariant no journey asserts and only a fixture test can hold.

    Building every cohort this round adds leaves the finance-signed window
    exactly as it was found. On a fresh test tenant that is zero entries; the
    assertion is written as a DELTA so it stays true on a stack where LE-1's
    book is already posted (DEF-568's lesson: an invariant over a SHARED
    window is a delta, never a total).
    """
    with tenant_ctx(brazos):
        before = _signed_window_entries(brazos)
        cohort.ensure_grace_pre_state(brazos, dana)
        cohort.ensure_guardrail_cohort(brazos, dana)
        after = _signed_window_entries(brazos)

    assert after == before, (
        f"this round's cohorts posted {after - before} journal entries into "
        f"{SIGNED_START} → {SIGNED_END}, the window LE-1's signed 553.69 lives in "
        "(DEF-556). A fixture may never restate a signed figure."
    )


# ── T5-04 · tenant B exists, and is unreachable ─────────────────────────────
#
# ⚠ REQUESTS ONLY `db` — DEF-566, exactly as tests/test_cr014_group4_tenants.py
# explains at length: `test_us_ten_helpers.identity_seam` stubs
# `apps.identity.services.provision_owner`, so under the `brazos` fixture no
# provisioned tenant has an owner or a membership and nothing about
# provisioning's real output can be asserted. This cohort needs BOTH tenants to
# have real owners, because its subject is one email address owning two
# different user rows.


def test_round3_t5_04__tenant_b_carries_a_named_issued_cad_bill(db):
    """The sweep needs foreign rows that EXIST.

    An empty tenant B would let every probe in T5-04 answer *not found* for the
    honest reason that nothing is there, and the journey would report green
    over a database with RLS switched off entirely. So the first assertion of
    this fixture is that tenant B is not empty.
    """
    from apps.billing import models as billing_models
    from apps.tenancy import models as tenancy_models

    cohort.ensure_second_tenant(
        subdomain="brazosbend",
        name="Brazos Bend Utilities",
        owner_email="dana@brazosbendutilities.com",
        owner_name="Dana Whitfield",
    )
    result = cohort.ensure_maple_ridge_cohort(None)

    tenant_b = tenancy_models.Tenant.objects.get(subdomain=cohort.MAPLE_RIDGE_SUBDOMAIN)
    assert tenant_b.currency == cohort.MAPLE_RIDGE_CURRENCY
    with cohort._in_tenant(tenant_b.id):
        invoice = billing_models.Invoice.objects.get(pk=result["invoice_id"])
    assert invoice.status == "issued"
    assert invoice.currency == cohort.MAPLE_RIDGE_CURRENCY
    assert result["account_no"] == cohort.MAPLE_RIDGE_ACCOUNT


def test_round3_t5_04__one_address_is_two_user_rows(db):
    """BR-IDN-029, and T5-04's step 6.

    Dana's address exists in both tenants as DIFFERENT users, so her tenant-A
    password fails on tenant B's subdomain. If provisioning had refused the
    duplicate address, or reused one row, step 6 would be untestable — and a
    shared row would mean a session on A is a session on B, which is the leak
    the sweep exists to look for.
    """
    from apps.identity import models as identity_models

    cohort.ensure_second_tenant(
        subdomain="brazosbend",
        name="Brazos Bend Utilities",
        owner_email="dana@brazosbendutilities.com",
        owner_name="Dana Whitfield",
    )
    result = cohort.ensure_maple_ridge_cohort(None)

    rows = identity_models.User.objects.filter(email=result["shared_email"])
    assert rows.count() == 2, (
        f"{rows.count()} user row(s) hold {result['shared_email']}; BR-IDN-029 requires one "
        "per tenant, and T5-04 step 6 is exactly that"
    )
    assert {str(row.tenant_id) for row in rows} == {result["user_a_tenant"], result["tenant_id"]}
    assert result["user_a"] != result["user_b"]


@pytest.mark.isolation
def test_round3_t5_04__tenant_b_is_unreachable_from_tenant_a(db, rls):  # noqa: F811
    """The property the whole journey sweeps for, asserted at fixture time.

    Reading tenant B's account and bill from tenant A's context must answer
    ZERO ROWS — not a permission error, not a 403, zero rows, because RLS FORCE
    makes them invisible rather than forbidden (IS-7's empty posture).

    ⚠ **IT RUNS UNDER `sbh_rls_probe`, AND THE FIRST DRAFT OF THIS TEST DID
    NOT — which is why it is worth the extra fixture.** The role this suite
    connects as is a SUPERUSER, and PostgreSQL exempts superusers from row-level
    security unconditionally, FORCE or not. Written with the ORM it read tenant
    B's account from tenant A's context and failed with
    `assert 1 == 0` — not because the product leaks, but because the policy was
    never consulted. `tests/isolation_helpers` exists for exactly this and says
    so at length: *"a green suite that proves nothing is worse than a red one"*.
    A version of this test that had been written the other way round — expecting
    to SEE the row — would have gone green and certified a leak.
    """
    tenant_a = cohort.ensure_second_tenant(
        subdomain="brazosbend",
        name="Brazos Bend Utilities",
        owner_email="dana@brazosbendutilities.com",
        owner_name="Dana Whitfield",
    )
    result = cohort.ensure_maple_ridge_cohort(None)

    with rls.under(result["tenant_id"]):
        assert rls.count("accounts", "id = %s", [result["account_id"]]) == 1
        assert rls.count("invoices", "id = %s", [result["invoice_id"]]) == 1

    with rls.under(tenant_a.id):
        assert rls.count("accounts", "id = %s", [result["account_id"]]) == 0, (
            "tenant A can read tenant B's account by direct id — this is the leak T5-04 "
            "sweeps for, and hard rule 1 says it cannot happen"
        )
        assert rls.count("invoices", "id = %s", [result["invoice_id"]]) == 0
        assert rls.count("accounts", "account_no = %s", [cohort.MAPLE_RIDGE_ACCOUNT]) == 0
