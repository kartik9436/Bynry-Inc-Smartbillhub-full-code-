# ── Trace ──────────────────────────────────────────────
# Change:   CR-013 part 3 — the DISCOUNT READ API. `GET /discounts` (DIS-01,
#           `09-screen-inventory.md` §18 row 10) and `GET /discounts/{id}`
#           (CHG-01.discount, §18 row 11).
#           Screens: PLN-01.discounts · CHG-01.discount
# Rules:    BR-RAT-069 (available ≠ granted — `plans` and `enrolled` are two
#           different numbers and only one of them reduces a bill) ·
#           BR-RAT-072 (five statuses, including the one a BILL RUN sets) ·
#           BR-RAT-074 (a floor of zero MEANS a bill may reach zero) ·
#           BR-RAT-075 (caps and budget are nullable, and null is uncapped) ·
#           BR-RAT-079 (income and medical proof are restricted and excluded
#           from general lists — this read carries no document at all) ·
#           BR-RAT-087 (money and percent are served with a `*_display`
#           companion at two places) · BR-SHL-011 (q/sort/dir/page/per/f.<name>)
# Tests:    this file
# Impacts:  apps/rating/selectors.py (the discount selectors) ·
#           apps/rating/api.py (two handlers, GET only)
# ───────────────────────────────────────────────────────
"""CR-013 part 3 — the read half, proved.

⚠ **THE FIRST TEST ASSERTS THAT A ROUTE EXISTS**, which tests do not normally
do. It is the shape of the gap this slice closed: six discount tables shipped on
2026-08-19 with every write service and the R6 pricing door built and tested,
`apps/rating/api.py` served **18 handlers and not one of them was a discount**,
and a human could not see a single row. A test that goes RED when the route is
absent is the check that would have caught it — hard-won law 2, built is not
wired, asserted rather than described.

⚠ **AND THE PERCENT TEST IS THE ONE TO READ BEFORE CHANGING ANYTHING HERE.**
Two percent conventions live in `apps/rating/selectors.py` and both produce a
well-formed string, so choosing the wrong helper is invisible to every gate in
this repo. `charges.percent` and `taxes.rate` store a FRACTION OF ONE (`0.015`
is 1.5%); `discount_versions.value` stores PERCENTAGE POINTS (`15` is 15%, and
`discount_pricing._raw_reduction` divides by a hundred). Serving SENIOR through
the fraction helper reads **`1500.00%`**, which is DEF-364 in reverse and would
ship green. `::test_a_percentage_discount_displays_points_not_a_fraction` pins
it to the digit.
"""

from decimal import Decimal

import pytest

from apps.rating import api, discount_sample_data, discount_services, selectors
from apps.rating import discounts as discount_models
from core import errors
from core.pagination import ListParams

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import FakeUser, api_call, tenant_ctx

pytestmark = pytest.mark.django_db


def _params(sort="code", **kwargs):
    return ListParams(**{"sort": sort, "dir": "asc", **kwargs})


def _seed(env):
    """r10's own five discounts, through the audited sample loader — the same
    fixture `test_cr013_discounts.py` asserts, so this file adds a reader over
    data another file already pins rather than inventing a second fixture."""
    with tenant_ctx(env.tenant):
        return discount_sample_data.seed_sample_discounts(env.admin)


def _rows(env, params=None):
    with tenant_ctx(env.tenant):
        return selectors.discount_list(params or _params())


def _by_code(env, params=None):
    return {row["code"]: row for row in _rows(env, params)}


def _account(env, service="water"):
    """One real account, through metering's own premises/unit helpers — the same
    builder `test_cr013_discounts.py` uses, so the two files enrol identically."""
    from apps.customers import models as customer_models
    from tests.test_us_met_helpers import make_premises, make_unit

    with tenant_ctx(env.tenant):
        premises = make_premises(
            env.admin, address_line="1 Discount Way", services_available=[service]
        )
        unit = make_unit(env.admin, premises["id"], label="A", services=[service])
        account = customer_models.Account.objects.create(
            tenant=env.tenant,
            unit_id=unit["id"],
            account_no="ACC-DISC-READ-1",
            status=customer_models.AccountStatus.objects.get(tenant=env.tenant, code="active"),
            account_type=customer_models.AccountType.objects.first(),
        )
        # `CR-166-BRC10` ruling 2: the account's plan must carry what it enrols in.
        from tests.discount_plan_fixture import carry

        carry(env.tenant, unit["id"], discount_models.Discount.objects.filter(tenant=env.tenant))
        return account


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE ROUTE ITSELF — the gap this slice closed
# ══════════════════════════════════════════════════════════════════════════


def test_the_discount_routes_are_registered():
    """RED before this slice: `apps/rating/api.py` had 18 handlers and no
    discount among them, so six migrated tables were unreachable by anything
    with a URL. Asserted against the module's own `urlpatterns` rather than by
    calling a view, because a view that exists and is not routed is exactly as
    useful to a browser as no view at all."""
    routes = {str(entry.pattern) for entry in api.urlpatterns}
    assert "discounts" in routes
    assert "discounts/<str:discount_id>" in routes


def test_the_list_answers_200_for_a_read_only_role(env):
    """A4 gives Billing Clerk and Executive *View* on `plans_rates`, so the
    landing tab has to load for them. There is no write half on this route to
    forge, which is itself the decision recorded in the handler."""
    _seed(env)
    response = api_call(
        api.discounts, "get", user=FakeUser(env.owner.id), role="billing_clerk", tenant=env.tenant
    )
    assert response.status_code == 200
    assert response.data["count"] == 5
    assert {row["code"] for row in response.data["results"]} == {
        "SENIOR",
        "CAP",
        "PAPERLESS",
        "AUTOPAY",
        "MILITARY",
    }


def test_the_detail_answers_200_and_404_on_a_stranger(env, other_env):
    """Hard rule 1 at the route's own edge: a real id belonging to another
    tenant is a 404 here, not another tenant's discount."""
    _seed(env)
    with tenant_ctx(env.tenant):
        mine = discount_models.Discount.objects.get(tenant=env.tenant, code="SENIOR")
    user = FakeUser(env.owner.id)
    ok = api_call(
        api.discount_item,
        "get",
        user=user,
        role="system_admin",
        tenant=env.tenant,
        discount_id=str(mine.id),
    )
    assert ok.status_code == 200 and ok.data["code"] == "SENIOR"
    stranger = api_call(
        api.discount_item,
        "get",
        user=FakeUser(other_env.owner.id),
        role="system_admin",
        tenant=other_env.tenant,
        discount_id=str(mine.id),
    )
    assert stranger.status_code == 404


def test_a_malformed_id_is_a_404_and_never_a_500(env):
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.NotFoundError):
            selectors.discount_detail("not-a-uuid")


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE NINE COLUMNS OF DIS-01, IN r10's ORDER
# ══════════════════════════════════════════════════════════════════════════


def test_the_row_carries_r10s_nine_columns(env):
    """Code · Discount · Type · Value · Eligibility · Verification · Plans ·
    Enrolled · Status — the column list CR-013 part 3 gives DIS-01."""
    _seed(env)
    senior = _by_code(env)["SENIOR"]
    for key in (
        "code",
        "name",
        "type",
        "value",
        "value_display",
        "eligibility",
        "verification",
        "plans",
        "enrolled",
        "status",
    ):
        assert key in senior, key
    # `CR-166-BRC10` §9: `eligibility` is `{value, label, checked_by}` now, the
    # fixture's *Age 65+* mapped to the drawn value.
    assert (senior["name"], senior["eligibility"]["label"], senior["verification"]) == (
        "Senior discount",
        "Age 65 or over",
        "annual_recertification",
    )


def test_a_draft_discount_still_shows_its_type_and_value(env):
    """r10 draws MILITARY as a Draft pill with `—` plans and `—` enrolled — but
    it draws its VALUE. A row that resolved only ACTIVE versions would print
    em-dashes over a drafted −10%, describing a different object than the one on
    the screen."""
    _seed(env)
    military = _by_code(env)["MILITARY"]
    assert military["status"] == "draft"
    assert military["version_status"] == "draft"
    assert (military["type"], military["value_display"]) == ("percentage", "10.00%")
    assert (military["plans"], military["enrolled"]) == (0, 0)


def test_the_five_statuses_are_all_representable(env):
    """BR-RAT-072. The fifth — `suspended_funding_exhausted` — is the only
    status in the product a BILL RUN can set, and the landing tab has to be able
    to show it or a suspended programme looks active to the person deciding
    whether next month's bill is reduced."""
    _seed(env)
    with tenant_ctx(env.tenant):
        senior = discount_models.Discount.objects.get(tenant=env.tenant, code="SENIOR")
        discount_services.suspend_discount_for_funding(env.admin, senior.id)
    row = _by_code(env)["SENIOR"]
    # `CR-166-BRC10` §9: `status` is the DERIVED six-value status (a suspended
    # programme still has a version in force); the stored state is
    # `stored_status`, which is where the fifth status still shows.
    assert row["stored_status"] == discount_models.DISCOUNT_SUSPENDED_FUNDING
    with tenant_ctx(env.tenant):
        detail = selectors.discount_detail(str(senior.id))
    assert detail["funding_exhausted_at"] is not None


# ══════════════════════════════════════════════════════════════════════════
# 3 · BR-RAT-087 — the `*_display` companions, and the percent trap
# ══════════════════════════════════════════════════════════════════════════


def test_a_percentage_discount_displays_points_not_a_fraction(env):
    """⚠ THE TRAP THIS FILE EXISTS FOR. `charges.percent` is a FRACTION and
    `_display_percent` scales it up; `discount_versions.value` is PERCENTAGE
    POINTS and must not be scaled. SENIOR is −15% and AUTOPAY is −0.5% — the
    wrong helper renders them `1500.00%` and `50.00%`, both well-formed, both
    wrong, and no gate in this repo can see the difference."""
    _seed(env)
    rows = _by_code(env)
    assert rows["SENIOR"]["value_display"] == "15.00%"
    assert rows["AUTOPAY"]["value_display"] == "0.50%"
    # The stored six-place value is untouched beside it — anything that computes
    # still reads the column, exactly as `charge_row` serves both.
    assert Decimal(rows["SENIOR"]["value"]) == Decimal("15")
    assert rows["SENIOR"]["value"] == "15.000000"


def test_a_fixed_amount_discount_displays_money_at_two_places(env):
    _seed(env)
    rows = _by_code(env)
    # `CR-166` §9 / PO 2026-10-03 on the list: *"fixed values shown with $"*.
    assert (rows["CAP"]["type"], rows["CAP"]["value_display"]) == ("fixed_amount", "$25.00")
    assert rows["PAPERLESS"]["value_display"] == "$1.00"
    # Hard rule 2 — the amount travels with its currency.
    assert rows["CAP"]["currency"] == "USD"


def test_a_charge_waiver_has_no_value_and_is_served_null_not_zero(env):
    """⚠ THE DISCIPLINE OF THE WHOLE CHANGE, in one row. A waiver removes the
    WHOLE of what its scope selected — `discount_pricing._raw_reduction` returns
    the base and never reads `value` — so the stored value is not a figure.
    `0.00` on that screen would state that the utility waives nothing; an
    em-dash states that the number has no meaning for this type."""
    with tenant_ctx(env.tenant):
        created = discount_services.create_discount(
            env.admin,
            {
                # `create_discount` takes the identity fields and the FIRST
                # version's fields in one flat payload (DISCOUNT_FIELDS +
                # VERSION_FIELDS) — a discount with no version has nothing to
                # render in DIS-01's Value column.
                "code": "WAIVE-BASE",
                "name": "Base charge waived",
                "discount_type": discount_models.DISCOUNT_CHARGE_WAIVER,
                "value": "0",
                # ⚠ `base_only`, NOT `named_codes`, and the reason is DEF-388:
                # `applies_to_charge_codes` is accepted by `create_discount`,
                # listed in VERSION_FIELDS, and then dropped before validation,
                # so a `named_codes` scope is unreachable today. Filed; not
                # fixed here (`discount_services.py` is 🔒 HUMAN-REVIEW-PENDING
                # and belongs to the write lane). The assertion below is about
                # the VALUE column and holds on either scope.
                "applies_to": discount_models.SCOPE_BASE_ONLY,
                "effective_from": "2026-08-01",
            },
        )
        row = selectors.discount_detail(created["id"])
    assert row["type"] == "charge_waiver"
    assert row["value"] == "0.000000"  # stored, because the column is NOT NULL
    assert row["value_display"] is None  # and never rendered as a money figure


def test_every_money_field_on_the_detail_is_null_when_it_was_not_typed(env):
    """BR-RAT-075: the caps are nullable and null means UNCAPPED. MILITARY is
    seeded with no budget cap on purpose — PO ruling 5 of 2026-08-19 calls that
    case out by hand, because unbounded is the largest commitment there is. A
    `0.00` here would read as a programme that pays nothing."""
    _seed(env)
    with tenant_ctx(env.tenant):
        military = discount_models.Discount.objects.get(tenant=env.tenant, code="MILITARY")
        detail = selectors.discount_detail(str(military.id))
    for key in (
        "cap_per_bill",
        "cap_per_bill_display",
        "cap_per_year",
        "cap_per_year_display",
        "cap_lifetime",
        "cap_lifetime_display",
        "budget_cap",
        "budget_cap_display",
        "budget_remaining",
        "budget_remaining_display",
    ):
        assert detail[key] is None, key
    # BR-RAT-074's one deliberate exception: a floor of ZERO is a decision — the
    # bill may reach zero — so it is stored, served, and displayed as a figure.
    assert detail["bill_floor_amount_display"] == "0.00"


def test_a_typed_budget_cap_is_served_with_its_display_and_its_remainder(env):
    """SENIOR's cap is design §A8's own $12,312 figure. Nothing has been granted
    against it, so the remainder equals the cap — and `granted_to_date` is a
    true `0.00` rather than a null, because `discount_grants` is append-only and
    therefore complete: zero rows IS "no subsidy has been given"."""
    _seed(env)
    with tenant_ctx(env.tenant):
        senior = discount_models.Discount.objects.get(tenant=env.tenant, code="SENIOR")
        detail = selectors.discount_detail(str(senior.id))
    assert detail["budget_cap_display"] == "12312.00"
    assert detail["budget_remaining_display"] == "12312.00"
    assert detail["granted_to_date_display"] == "0.00"


# ══════════════════════════════════════════════════════════════════════════
# 4 · AVAILABLE ≠ GRANTED (BR-RAT-069) — the two counts, side by side
# ══════════════════════════════════════════════════════════════════════════


def test_plan_attachment_raises_plans_and_leaves_enrolled_at_zero(env):
    """⚠ THE RULE THAT COSTS THE MOST TO GET WRONG. Attaching SENIOR to a plan
    makes it AVAILABLE; it grants nothing. A landing tab that read one number
    for both would tell a utility that every account on Residential Standard is
    getting −15%, and an implementation that reduced on plan attachment would
    charge the wrong amount to all of them."""
    _seed(env)
    plan = env.plan(
        "Residential Standard", "RES-STD", [{"service": "electric", "base_charge": "18.50"}]
    )
    with tenant_ctx(env.tenant):
        senior = discount_models.Discount.objects.get(tenant=env.tenant, code="SENIOR")
        discount_services.attach_discount_to_plan(env.admin, plan["id"], senior.id)
    row = _by_code(env)["SENIOR"]
    assert row["plans"] == 1
    assert row["enrolled"] == 0


def test_an_ended_enrolment_stops_counting(env):
    """An account that enrolled and left is not enrolled. Counting it would
    overstate a subsidy programme's reach on the one screen a utility uses to
    judge whether the programme is affordable."""
    _seed(env)
    account = _account(env)
    with tenant_ctx(env.tenant):
        senior = discount_models.Discount.objects.get(tenant=env.tenant, code="SENIOR")
        enrolment = discount_services.enrol_account(env.admin, senior.id, account.id)
    assert _by_code(env)["SENIOR"]["enrolled"] == 1
    with tenant_ctx(env.tenant):
        discount_services.end_enrolment(env.admin, enrolment["id"], "moved_out")
    assert _by_code(env)["SENIOR"]["enrolled"] == 0


# ══════════════════════════════════════════════════════════════════════════
# 5 · BR-RAT-079 — the read carries no proof, so no list can leak one
# ══════════════════════════════════════════════════════════════════════════


def test_neither_read_serves_a_document_or_an_account_id(env):
    """Part 3: *"income and medical proof restricted by role and excluded from
    general document lists."* The role gate does not exist yet, so the read is
    built so that there is nothing to gate — counts only. A payload that carried
    an enrolment would be one forgotten filter away from putting a medical
    certification in a clerk's browse list."""
    _seed(env)
    account = _account(env)
    with tenant_ctx(env.tenant):
        senior = discount_models.Discount.objects.get(tenant=env.tenant, code="SENIOR")
        discount_services.enrol_account(env.admin, senior.id, account.id)
        detail = selectors.discount_detail(str(senior.id))
        row = _by_code(env)["SENIOR"]
    for payload in (detail, row):
        assert "enrolments" not in payload
        assert "documents" not in payload
        assert "accounts" not in payload
        assert str(account.id) not in repr(payload)
    # The POLICY list of acceptable proof KINDS is not a document and is served:
    # a screen has to say what proof the programme accepts.
    assert detail["accepted_proof_kinds"] == ["government_id", "birth_certificate"]


# ══════════════════════════════════════════════════════════════════════════
# 6 · BR-SHL-011 — the list grammar, exactly as the charge list implements it
# ══════════════════════════════════════════════════════════════════════════


def test_the_default_sort_is_code_ascending_and_desc_reverses_it(env):
    _seed(env)
    ascending = [row["code"] for row in _rows(env)]
    assert ascending == ["AUTOPAY", "CAP", "MILITARY", "PAPERLESS", "SENIOR"]
    assert [row["code"] for row in _rows(env, _params("code", dir="desc"))] == ascending[::-1]


def test_an_undeclared_sort_falls_back_and_never_errors(env):
    """BR-SHL-010: `value` is not in `DISCOUNT_SORTS` because it lives on the
    version, and BE-05 falls back rather than refusing. The fallback is asserted
    here so the tuple cannot quietly grow a sort the selector does not honour."""
    _seed(env)
    assert "value" not in selectors.DISCOUNT_SORTS
    with tenant_ctx(env.tenant):
        rows = selectors.discount_list(_params("value"))
    assert [row["code"] for row in rows] == ["AUTOPAY", "CAP", "MILITARY", "PAPERLESS", "SENIOR"]


def test_search_matches_the_code_or_the_bill_line_name_from_two_characters(env):
    _seed(env)
    assert [row["code"] for row in _rows(env, _params("code", q="pap"))] == ["PAPERLESS"]
    # The bill-line name, not just the code — "Veteran discount" is MILITARY.
    assert [row["code"] for row in _rows(env, _params("code", q="veteran"))] == ["MILITARY"]
    # One character is below IS-3's threshold and filters nothing.
    assert len(_rows(env, _params("code", q="p"))) == 5


def test_status_filters_in_the_database_and_type_filters_the_built_rows(env):
    """`status` is the discount's own column; `type` and `verification` live on
    the version this row resolved, so they filter the rows — the same split
    `tax_list` already makes for `service`."""
    _seed(env)
    drafts = _rows(env, _params("code", filters={"status": "draft"}))
    assert [row["code"] for row in drafts] == ["MILITARY"]
    percentages = _rows(env, _params("code", filters={"type": "percentage"}))
    assert [row["code"] for row in percentages] == ["AUTOPAY", "MILITARY", "SENIOR"]
    automatic = _rows(env, _params("code", filters={"verification": "automatic"}))
    assert [row["code"] for row in automatic] == ["AUTOPAY", "PAPERLESS"]


def test_lone_star_ridge_sees_only_its_own_discounts(env, other_env):
    """Hard rule 1 at the selector's own level. The live-RLS half is the G5
    isolation suite's; this is the APP-FILTER half."""
    _seed(env)
    with tenant_ctx(other_env.tenant):
        discount_sample_data.seed_sample_discounts(other_env.admin)
        rows = selectors.discount_list(_params())
    assert len(rows) == 5
    with tenant_ctx(env.tenant):
        mine = {row["id"] for row in selectors.discount_list(_params())}
    assert mine.isdisjoint({row["id"] for row in rows})


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-013 part 3 VERBATIM (12-governance/11-change-requests.md) · 09-screen-inventory.md §18 rows 10-12 + §1 · BR-RAT-069/072/074/075/079/087 · BR-SHL-011
# generated: 2026-08-21 by the CR-013 discounts read-API lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: no write endpoint is tested because none is authored — DIS-02 (§18 row 12) is a separate surface and its write services already exist and are covered by tests/test_cr013_discounts.py · the version LIST is not served and therefore not tested (§10, the Versions tab still states what it waits for)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
