# ── Trace ──────────────────────────────────────────────
# Change:   CR-087 · D4/D5 — the plan's review and its page become one banded
#           card, and the plan's second tab LISTS the units it prices.
# Commits:  PRB-19 (the combined tax rate is stated by the SERVER) ·
#           PRB-21 (the units on a plan can be listed, paged from the server)
# Rules:    NFR-3 (universal server pagination; no unpaginated list anywhere) ·
#           NFR-5 (no hard caps) · B2 §2 (rating reads metering and customers
#           through a seam and writes neither) · CLAUDE.md hard rule 8 (an
#           address lives on `premises`; everything else WALKS to it) ·
#           BR-RAT-087 (a percent reaches a screen as the server's display
#           string; the browser performs no money arithmetic).
# Tests:    this file
# Impacts:  apps/rating/selectors (plan_detail · plan_units_queryset ·
#           plan_unit_rows) · apps/rating/seams (plan_unit_facts) ·
#           apps/rating/api (GET /plans/{id}/units)
# ───────────────────────────────────────────────────────
"""CR-087 — what the plan's card and its Units tab need from the server.

TWO THINGS, AND BOTH WERE SUMS OR LISTS SOMEBODY WAS DOING BY HAND.

**PRB-19 — the combined rate.** A plan bound to Texas State (6.25%) and Bexar
County (1.00%) charges 7.25%, and a clerk was adding those two in their head on
every call. The card's Taxes band carries the total in its own label, and the
figure comes from the SAME response as the rows under it — one read serves the
row and its cells, which is the defect the blueprint names on three tabs at
once (a column that could print *"this was not in the list this page read"*).

**PRB-21 — the units.** The plan showed a count of 74 and nothing said 74 of
WHAT, nor listed them. A plan attaches to a UNIT, so the count is units — and
the vacant unit is the row that matters, because it has no account, no customer
and a base charge that still reaches the owner's bill. A clerk reading a blank
Account cell concludes nothing is billed, which is the opposite of the truth.

⚠ **THE PAGING IS THE POINT AND NOT THE PLUMBING.** `NFR-3` is breached in at
least four places that name the old 3,000-connection ceiling as their excuse,
and CLAUDE.md names them. This list is served as a QUERYSET so the count is a
SQL `COUNT` over the whole set and the page is a SQL `LIMIT`/`OFFSET` — the
total is the whole set rather than the page, or the tile and the table disagree
the moment a plan passes one page.
"""

from datetime import date

import pytest

from apps.rating import models as rating_models
from apps.rating import selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, make_premises, make_unit

pytestmark = pytest.mark.django_db


def _assign(tenant, plan, unit_id, when=date(2026, 6, 1)):
    """One CURRENT unit→plan assignment, written the way the history stores it."""
    return rating_models.UnitPlanAssignment.objects.create(
        tenant=tenant,
        unit_id=unit_id,
        rate_plan=plan,
        plan_version=plan.version,
        assigned_from=when,
        assigned_to=None,
        source="import",
    )


@pytest.fixture()
def plan_with_units(brazos, dana):
    """One premises, two units, one plan. Unit 1 has an account; Unit 2 is
    VACANT — which is the row the whole tab exists for."""
    with tenant_ctx(brazos):  # noqa: F405 — metering writes are tenant-scoped
        premises = make_premises(dana, address_line="101 Silver Creek Rd")
        one = make_unit(dana, premises["id"], label="Unit 1")
        two = make_unit(dana, premises["id"], label="Unit 2")
    plan = make_plan(brazos, name="Residential Standard", code="SCW-RES")
    with tenant_ctx(brazos):  # noqa: F405
        _assign(brazos, plan, one["id"])
        _assign(brazos, plan, two["id"])
    return {"tenant": brazos, "actor": dana, "plan": plan, "premises": premises,
            "occupied": one, "vacant": two}


class TestPRB21UnitsCanBeListed:
    def test_the_units_on_a_plan_are_listed_at_all(self, plan_with_units):
        with tenant_ctx(plan_with_units["tenant"]):  # noqa: F405
            rows = selectors.plan_unit_rows(
                list(selectors.plan_units_queryset(plan_with_units["plan"].id))
            )
        assert [row["unit_label"] for row in rows] == ["Unit 1", "Unit 2"]

    def test_every_row_WALKS_to_the_premises_for_its_address(self, plan_with_units):
        """CLAUDE.md hard rule 8 — an address is stored on `premises` and
        nowhere else, so a unit's address is the premises' own."""
        with tenant_ctx(plan_with_units["tenant"]):  # noqa: F405
            rows = selectors.plan_unit_rows(
                list(selectors.plan_units_queryset(plan_with_units["plan"].id))
            )
        assert {row["premises_address"] for row in rows} == {"101 Silver Creek Rd"}

    def test_a_vacant_unit_says_so_rather_than_serving_a_blank_account(self, plan_with_units):
        with tenant_ctx(plan_with_units["tenant"]):  # noqa: F405
            rows = selectors.plan_unit_rows(
                list(selectors.plan_units_queryset(plan_with_units["plan"].id))
            )
        vacant = [row for row in rows if row["unit_label"] == "Unit 2"][0]
        assert vacant["account_no"] is None
        assert vacant["vacant"] is True

    def test_def_rat_9353__a_row_carries_what_its_premises_and_account_LINK_to(self, plan_with_units):
        """`DEF-RAT-9353` (CR-167 r3 task 7, ruling 13: every name is a link) —
        image 31 draws Premises and Account as links, so each row carries their
        references beside the words. Keys for an address, never shown."""
        with tenant_ctx(plan_with_units["tenant"]):  # noqa: F405
            rows = selectors.plan_unit_rows(
                list(selectors.plan_units_queryset(plan_with_units["plan"].id))
            )
        assert {row["premises_id"] for row in rows} == {str(plan_with_units["premises"]["id"])}
        vacant = [row for row in rows if row["unit_label"] == "Unit 2"][0]
        assert "account_id" in vacant and vacant["account_id"] is None

    def test_def_rat_9353__an_occupied_row_carries_its_ACCOUNT_reference(self, plan_with_units):
        """The browser walk found the first fix passing over a blank: the seam
        POPPED its private account id before the row could read it, so every
        account read as plain text. An occupied unit must carry its account."""
        from apps.customers import models as customer_models

        tenant = plan_with_units["tenant"]
        with tenant_ctx(tenant):  # noqa: F405
            status = customer_models.AccountStatus.objects.filter(tenant=tenant).first()
            account = customer_models.Account.objects.create(
                tenant=tenant,
                unit_id=plan_with_units["occupied"]["id"],
                account_no="AC-9353",
                status=status,
                account_type=customer_models.AccountType.objects.first(),
            )
            rows = selectors.plan_unit_rows(
                list(selectors.plan_units_queryset(plan_with_units["plan"].id))
            )
        occupied = [row for row in rows if row["unit_label"] == "Unit 1"][0]
        assert occupied["account_no"] == "AC-9353"
        assert occupied["account_id"] == str(account.id)

    def test_the_count_is_the_WHOLE_set_and_the_page_is_a_page(self, plan_with_units):
        """NFR-3 — the total must be the whole set, not the page, or the tile
        and the table disagree the moment a plan passes one page."""
        with tenant_ctx(plan_with_units["tenant"]):  # noqa: F405
            qs = selectors.plan_units_queryset(plan_with_units["plan"].id)
            assert qs.count() == 2
            # A QuerySet, so the API's paginator slices in SQL. A LIST here
            # would mean every unit of a 40,000-account tenant materialised on
            # every request — the breach CLAUDE.md names on four endpoints.
            assert hasattr(qs, "count") and hasattr(qs, "order_by")
            first_page = selectors.plan_unit_rows(list(qs[:1]))
        assert len(first_page) == 1

    def test_it_puts_no_database_id_where_a_screen_would_show_one(self, plan_with_units):
        """B14 rule 31 — a unit is named by its LABEL and its premises, never
        by a uuid. The id is served for keying and the row carries a name for
        every visible column."""
        with tenant_ctx(plan_with_units["tenant"]):  # noqa: F405
            rows = selectors.plan_unit_rows(
                list(selectors.plan_units_queryset(plan_with_units["plan"].id))
            )
        for row in rows:
            assert row["unit_label"]
            assert row["premises_address"]

    def test_an_endpoint_serves_it(self):
        """PRB-21's own sentence: *the count exists and the list does not*."""
        from apps.rating import api

        routes = {str(entry.pattern) for entry in api.urlpatterns}
        assert "plans/<str:plan_id>/units" in routes


class TestPRB19CombinedTaxRate:
    def test_the_server_states_the_combined_rate(self, brazos, dana):
        plan = make_plan(brazos, name="Residential Standard", code="SCW-RES")
        with tenant_ctx(brazos):  # noqa: F405
            state = rating_models.TaxJurisdiction.objects.create(
                tenant=brazos, name="Texas State", authority="Texas Comptroller", level="state"
            )
            county = rating_models.TaxJurisdiction.objects.create(
                tenant=brazos, name="Bexar County", authority="Bexar County", level="county"
            )
            for jurisdiction, rate in ((state, "0.062500"), (county, "0.010000")):
                rating_models.Tax.objects.create(
                    tenant=brazos,
                    jurisdiction=jurisdiction,
                    name=f"{jurisdiction.name} utility tax",
                    kind="percent",
                    rate=rate,
                    # No `status` kwarg exists: DEF-387 made the lifecycle a
                    # DERIVED value (`tax_status`) rather than a column, and a
                    # row with no window and no draft flag is `active`.
                )
                rating_models.PlanTaxRule.objects.create(
                    tenant=brazos, rate_plan=plan, jurisdiction=jurisdiction
                )
            detail = selectors.plan_detail(plan.id)
        # 6.25% + 1.00% = 7.25%, worked by the SERVER. A browser summing two
        # decimal strings is what CLAUDE.md rule 2 forbids.
        assert detail["combined_tax_rate_display"] == "7.25%"

    def test_one_read_serves_the_row_AND_its_cells(self, brazos, dana):
        """The blueprint's complaint, in one assertion: three tabs had a column
        that could print *"this was not in the list this page read"*, because
        the row came from the plan and its cells from a separate scan."""
        plan = make_plan(brazos, name="Residential Standard", code="SCW-RES")
        with tenant_ctx(brazos):  # noqa: F405
            state = rating_models.TaxJurisdiction.objects.create(
                tenant=brazos, name="Texas State", authority="Texas Comptroller", level="state"
            )
            rating_models.Tax.objects.create(
                tenant=brazos, jurisdiction=state, name="TX State Utility Tax",
                kind="percent", rate="0.062500",
            )
            rating_models.PlanTaxRule.objects.create(
                tenant=brazos, rate_plan=plan, jurisdiction=state
            )
            detail = selectors.plan_detail(plan.id)
        line = detail["tax_lines"][0]
        assert line["level"] == "state"
        assert line["authority"] == "Texas Comptroller"
        assert line["name"] == "TX State Utility Tax"
        assert line["rate_display"] == "6.25%"

    def test_a_plan_with_no_tax_states_no_combined_rate_rather_than_zero(self, brazos):
        """*not set* and *zero* are different facts — E2's whole ruling, one
        layer down. A plan nobody has bound a tax to has NO combined rate; a
        served `"0.00%"` would read as a tax of zero."""
        plan = make_plan(brazos, name="Bare", code="BARE")
        with tenant_ctx(brazos):  # noqa: F405
            detail = selectors.plan_detail(plan.id)
        assert detail["combined_tax_rate_display"] is None
        assert detail["tax_lines"] == []


# ── DEF-RAT-9359 · the CSV is served through the VIEW, not only the reader ────
@pytest.mark.parametrize("tail", ["units", "audit"])
def test_def_rat_9359__format_csv_reaches_the_view(plan_with_units, tail):
    """`?format=csv` is DRF's own format override: with no renderer whose
    format is `csv`, content negotiation answers 404 before the view runs —
    which is what the browser walk met on 2026-10-03 (CR-167 r3 task 7)."""
    from rest_framework.test import APIRequestFactory, force_authenticate

    from apps.rating import api as rating_api

    plan = plan_with_units["plan"]
    request = APIRequestFactory().get(f"/api/brazosbend/plans/{plan.id}/{tail}", {"format": "csv"})
    force_authenticate(request, user=plan_with_units["actor"].user)
    request.tenant_role = "system_admin"
    request.tenant_id = plan_with_units["tenant"].id
    view = rating_api.plan_units if tail == "units" else rating_api.plan_audit
    with tenant_ctx(plan_with_units["tenant"]):  # noqa: F405
        response = view(request, str(plan.id))
        assert response.status_code == 200, getattr(response, "data", None)
        body = b"".join(response.streaming_content).decode()
    assert body.splitlines()[0].startswith("Unit," if tail == "units" else "When,")


class TestDefRat9361OneDefinitionOfOccupied:
    """`DEF-RAT-9361` (CR-167-BRC10 follow-up) — with *Vacant* on, Apt 102 was
    listed AND its row read *Occupied*: the filter asked customers for units
    with an account that is not closed, the row called a unit occupied when it
    had ANY account. One definition now, served once: a unit is occupied when
    it has an account that is not closed — the filter, the row and the CSV."""

    def _account(self, tenant, unit_id, number, behavior):
        from apps.customers import models as customer_models

        status = customer_models.AccountStatus.objects.filter(tenant=tenant, behavior_class=behavior).first()
        assert status is not None, f"seed has no {behavior} account status"
        return customer_models.Account.objects.create(
            tenant=tenant,
            unit_id=unit_id,
            account_no=number,
            status=status,
            account_type=customer_models.AccountType.objects.first(),
        )

    def _rows(self, plan_id, occupancy):
        from apps.rating import plan_reads

        return {
            row["unit_label"]: row
            for row in selectors.plan_unit_rows(list(plan_reads.plan_units_filtered(plan_id, "", occupancy)))
        }

    def test_a_unit_whose_only_account_is_CLOSED_is_vacant_in_the_filter_AND_the_row(self, plan_with_units):
        tenant = plan_with_units["tenant"]
        plan_id = plan_with_units["plan"].id
        with tenant_ctx(tenant):  # noqa: F405
            self._account(tenant, plan_with_units["occupied"]["id"], "AC-9361", "terminal")
            vacant = self._rows(plan_id, "vacant")
            occupied = self._rows(plan_id, "occupied")
            every = self._rows(plan_id, None)
        assert set(vacant) == {"Unit 1", "Unit 2"}
        assert occupied == {}
        # The row agrees with the filter that listed it — and still names the
        # closed account (closed and never-had-one are different facts).
        assert vacant["Unit 1"]["vacant"] is True
        assert vacant["Unit 1"]["account_no"] == "AC-9361"
        assert vacant["Unit 1"]["account_closed"] is True
        assert every["Unit 1"]["vacant"] is True

    def test_an_open_account_is_occupied_in_both_and_wins_over_a_newer_closed_one(self, plan_with_units):
        tenant = plan_with_units["tenant"]
        plan_id = plan_with_units["plan"].id
        with tenant_ctx(tenant):  # noqa: F405
            self._account(tenant, plan_with_units["occupied"]["id"], "AC-OPEN", "billable")
            self._account(tenant, plan_with_units["occupied"]["id"], "AC-CLOSED", "terminal")
            occupied = self._rows(plan_id, "occupied")
            vacant = self._rows(plan_id, "vacant")
        assert set(occupied) == {"Unit 1"} and set(vacant) == {"Unit 2"}
        assert occupied["Unit 1"]["vacant"] is False
        assert occupied["Unit 1"]["account_no"] == "AC-OPEN"
        assert occupied["Unit 1"]["account_closed"] is False

    def test_the_csv_says_what_the_row_says(self, plan_with_units):
        from apps.rating import plan_reads

        tenant = plan_with_units["tenant"]
        with tenant_ctx(tenant):  # noqa: F405
            self._account(tenant, plan_with_units["occupied"]["id"], "AC-9361", "terminal")
            text = "".join(plan_reads.plan_units_csv(plan_with_units["plan"].id, "", "vacant"))
        lines = [line for line in text.splitlines()[1:] if line]
        assert len(lines) == 2
        assert all(",Vacant," in line for line in lines), lines
