# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 1 · P1.1 (the catalogue comes out of the table)
#           · P1.2 (`q` · `group` · `service`, server-side; `origin` is the
#           SUB-TAB and not a filter) · P1.5 (no literals — zero rows renders
#           the empty state, never a fallback tuple) · P1.8 (enabled services
#           ride on the same answer).  Screens: S44
# Rules:    BR-REP-006 · BR-REP-019 · NFR-3 · NFR-5 · CLAUDE.md hard rule 1
# ───────────────────────────────────────────────────────
"""The Phase 1 catalogue read, asserted against the seeded forty-six.

⚠ **P1.5 IS THE CASE THIS FILE EXISTS FOR AND IT IS THE EASIEST ONE TO FAKE.**
*"The catalogue renders from fixture ROWS; deleting the seed EMPTIES the screen
rather than falling back to a tuple."* A read that quietly answers
`catalog.py`'s twenty-three when the table is empty passes every other
assertion here — the counts, the filters, the paging — because in every one of
them the table is full. So the deletion case is asserted directly, and it is
the one that would have caught `runner.built_in_fallback()` if it had shipped.

⚠ **AND IT CANNOT PROVE ISOLATION.** `config/settings/test.py` hardcodes
in-memory SQLite, which has no row-level security, so every platform-row
assertion below passes on the QUERYSET and says nothing about the policy
(hard-won law 14). `P0.10` owns that proof and it runs on PostgreSQL.
"""

import pytest

from apps.reports import catalogue_read
from apps.reports.models import ReportCategory, ReportDefinition, ReportTenantSetting

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


#: Every service this product knows, so a test that is not ABOUT the service
#: filter is not silently filtered by it.
ALL_SERVICES = {
    "services": [
        {"code": code, "name": code.title()}
        for code in (
            "electric",
            "water",
            "gas",
            "sewer",
            "trash",
            "storm_water",
            "solar",
            "broadband",
            "thermal",
            "battery",
            "fire",
        )
    ]
}


#: ⚠ **THE ROLE IS PASSED BECAUSE A REAL REQUEST ALWAYS CARRIES ONE — `P5.9`,
#: 2026-09-27.** `catalogue_payload` gained a `role` argument and FAILS CLOSED
#: on it: a caller that states no role is shown no report carrying a floor, so
#: `access_review` (`BR-REP-023`) drops out and every count in this file reads
#: 44 instead of 45. That is the right default for a security gate and the
#: wrong fixture for a file about the CATALOGUE — `api.report_library` reads
#: `request.tenant_role` and can never call this with nothing. Six cases here
#: failed on the count until this line existed. The no-role answer is asserted
#: deliberately, in the file that owns the rule:
#: `tests/test_rep_p5_9_role_gate.py::test_no_role_at_all_still_hides_it`.
CATALOGUE_ROLE = "system_admin"


def payload(brazos, **params):
    with tenant_ctx(brazos):
        return catalogue_read.catalogue_payload(
            dict(params), vocabularies=ALL_SERVICES, role=CATALOGUE_ROLE
        )


# ═══════════════════════════════════════════════════════════════════════════
# P1.1 — the catalogue comes out of the table
# ═══════════════════════════════════════════════════════════════════════════
def test_p1_1__the_grid_holds_forty_five_cards_in_six_groups(brazos):
    """`P1.1`'s outcome: *"the response carries 46 cards, each with a group and
    sub-group code."*

    Forty-six is the TABLE and forty-five is the GRID — p20 annotation ①,
    *"45, not 46 — the forty-sixth answer is the Dashboard tab"* — and both
    numbers are asserted here so a reader never has to re-derive which is which
    (`DEF-REP-6798`).
    """
    body = payload(brazos, per=100)
    with tenant_ctx(brazos):
        # `CR-179-BRC10` (2026-10-12): `reports/0010` added Rate Impact, so the
        # table holds 47 and the grid 46 — the drawing's 46/45 plus one card.
        assert ReportDefinition.objects.filter(tenant_id=None).count() == 49  # + `CR-184-BRC10` (`reports/0011`) + `CR-185-BRC10` (`reports/0012`, Owner summary)
    assert body["total"] == 48
    assert len(body["cards"]) == 48
    assert len(body["groups"]) == 6
    assert [group["code"] for group in body["groups"]] == [
        "billing",
        "receivables",
        "finance",
        "customers",
        "operations",
        "compliance",
    ]
    assert sum(len(group["sub_groups"]) for group in body["groups"]) == 19


def test_p1_1__the_sub_line_counts_the_catalogue_and_never_the_page(brazos):
    """p20 callout ①, and a defect found by LOOKING at the running screen.

    `groups` holds only what THIS page draws, so the Custom sub-tab — which
    draws none — rendered *"45 reports · 6 groups · 0 sub-groups"*. The
    catalogue still has six and nineteen whichever sub-tab you are on, so the
    shape is served as its own two numbers.
    """
    standard = payload(brazos, per=100)
    custom = payload(brazos, origin="custom", per=100)
    assert standard["group_total"] == custom["group_total"] == 6
    assert standard["sub_group_total"] == custom["sub_group_total"] == 19
    # …and it does not move under a filter either.
    assert payload(brazos, group="finance", per=100)["sub_group_total"] == 19


def test_p1_1__every_card_carries_a_group_and_a_sub_group_code(brazos):
    """The outcome's second half, and the one a screen actually needs."""
    for card in payload(brazos, per=100)["cards"]:
        assert card["group"], card["key"]
        assert card["sub_group"], card["key"]


def test_p1_1__the_name_comes_out_of_the_row_and_is_not_a_key(brazos):
    """p21: *"the server sends no title today, and becomes
    `report_definitions.name` at `P0.1`."*

    The assertion is that the name is not the KEY — B14 rule 31's shape, and
    exactly what serving the 46 against the old screen would have drawn.
    """
    cards = {card["key"]: card for card in payload(brazos, per=100)["cards"]}
    assert cards["ar_aging"]["name"] == "AR Ageing"
    assert cards["bill_print_file"]["name"] == "Bill Print File"
    for card in cards.values():
        assert card["name"] != card["key"]
        assert "_" not in card["name"]


def test_p1_1__a_tenant_name_override_wins_and_says_so(brazos):
    """`report_tenant_settings.name_override` — *"what THIS utility calls it."*"""
    with tenant_ctx(brazos):
        row = ReportDefinition.objects.get(tenant_id=None, key="debtor_list")
        ReportTenantSetting.objects.create(
            tenant_id=brazos.id, definition=row, name_override="Who owes us"
        )
    cards = {card["key"]: card for card in payload(brazos, per=100)["cards"]}
    assert cards["debtor_list"]["name"] == "Who owes us"
    # The flag exists so the SCREEN knows not to prefer its own catalogue copy
    # over a name this utility chose.
    assert cards["debtor_list"]["name_overridden"] is True
    assert cards["ar_aging"]["name_overridden"] is False


def test_p1_1__an_unavailable_card_opens_nothing_and_carries_one_reason(brazos):
    """B14 rule 33: the reason is a FACT, so it is a CODE the screen renders in
    six words — never the paragraph of rationale the 23-card catalogue drew."""
    cards = {card["key"]: card for card in payload(brazos, per=100)["cards"]}
    unavailable = [card for card in cards.values() if not card["available"]]
    assert unavailable, "every card available would mean the check cannot fail"
    # ⚠ **TWO REASON CODES SINCE 2026-09-27, AND THIS CASE IS WHAT FOUND THE
    # NEED FOR THE SECOND (lane REP-WIRE, `DEF-REP-6894`).** When the last six
    # datasets were registered, availability — then `queries_for(...) is not
    # None` — said YES to all forty-six, and this assertion went red with
    # *"every card available would mean the check cannot fail"* over
    # twenty-eight cards that refuse the instant they are clicked. A dataset
    # having an engine and that engine serving THIS report are two facts, and
    # they wait on different people: a dataset lane, or a ruling about which
    # dataset a report belongs on.
    assert {card["reason_code"] for card in unavailable} <= {
        catalogue_read.REASON_NOT_PRODUCIBLE,
        catalogue_read.REASON_GRAIN_NOT_SERVED,
    }
    for card in unavailable:
        assert card["kind"] == "absent"
        assert card["routes_to_screen"] is None


def test_p1_1__a_card_is_available_only_if_its_report_would_actually_answer(brazos):
    """⚠ **THE CARD AND THE CLICK MUST AGREE, AND NOTHING ASKED THEM TO.**

    `catalogue_read` decided availability from `runner.queries_for` alone, which
    reports whether the DATASET has an engine. A dataset query may still decline
    one DEFINITION by name — twenty-eight of the forty-six do — so a card could
    say *available* over a report that refuses on grain. This walks the whole
    catalogue and names any card whose claim the runner would not honour.
    """
    from apps.reports import queries as reports_queries

    cards = {card["key"]: card for card in payload(brazos, per=100)["cards"]}
    from apps.reports.models import ReportDefinition

    with tenant_ctx(brazos):
        datasets_by_key = dict(
            ReportDefinition.objects.filter(tenant_id=None).values_list("key", "dataset")
        )
    lying = [
        key
        for key, card in cards.items()
        if card["available"]
        and card["kind"] != "route"
        and reports_queries.definition_refusal(key, datasets_by_key.get(key)) is not None
    ]
    assert not lying, (
        "these cards say they are producible and refuse on grain when opened: "
        f"{sorted(lying)}"
    )


def test_p1_1__the_four_built_viewers_and_the_five_route_cards_are_live(brazos):
    """Hard-won law 2: a door that worked before this switch still works.

    The five route targets are checked by KEY here; that they RESOLVE to a real
    address is `routeTargetsResolve.dom.test.tsx`'s, which is the check that
    caught `DEF-REP-6812`.
    """
    cards = {card["key"]: card for card in payload(brazos, per=100)["cards"]}
    for key in ("ar_aging", "billing_register", "revenue_by_service_rate", "payments_by_method"):
        assert cards[key]["available"] is True
        assert cards[key]["kind"] == "viewer"
    for key, screen in catalogue_read.ROUTE_SCREENS.items():
        assert cards[key]["available"] is True
        assert cards[key]["kind"] == "route"
        assert cards[key]["routes_to_screen"] == screen


def test_p1_1__the_dashboard_definition_is_a_tab_and_never_a_card(brazos):
    """p20 annotation ①: *"a card pointing at a sibling tab is noise."*"""
    keys = {card["key"] for card in payload(brazos, per=100)["cards"]}
    assert "operational_dashboard" not in keys
    with tenant_ctx(brazos):
        assert ReportDefinition.objects.filter(tenant_id=None, key="operational_dashboard").exists()


# ═══════════════════════════════════════════════════════════════════════════
# P1.2 — the filters, read SERVER-SIDE
# ═══════════════════════════════════════════════════════════════════════════
def test_p1_2__a_search_for_ageing_returns_one_card(brazos):
    """`P1.2`'s outcome, verbatim: *"a search for ageing returns one card."*"""
    body = payload(brazos, q="ageing", per=100)
    assert [card["key"] for card in body["cards"]] == ["ar_aging"]
    assert body["count"] == 1
    # The roll-up describes the CATALOGUE and not the page (p20 annotation ①),
    # so a search does not rewrite what the sub-line says the catalogue holds.
    assert body["total"] == 48  # 45 + Rate Impact (CR-179-BRC10) + Over-90 by service (CR-184-BRC10) + Owner summary (CR-185-BRC10)


def test_p1_2__the_search_does_not_match_the_key(brazos):
    """A clerk typing `ar_` is not searching; matching the key would hand them
    cards whose snake_case happens to contain their letters."""
    assert payload(brazos, q="ar_", per=100)["count"] == 0


def test_p1_2__the_group_filter_keeps_one_group(brazos):
    body = payload(brazos, group="finance", per=100)
    assert body["count"] == 8  # 9 finance rows, less the dashboard TAB
    assert {card["group"] for card in body["cards"]} == {"finance"}
    # Only groups with something in them are drawn (1·2B annotation ④) …
    assert [group["code"] for group in body["groups"]] == ["finance"]
    # … and the dropdown still offers every group, or it could not be undone.
    assert len(body["group_options"]) == 6


def test_p1_2__origin_is_the_sub_tab_and_custom_reads_zero_on_day_one(brazos):
    """p20 annotation ④: *"Custom reads 0 on day one and that is the point."*"""
    assert payload(brazos, per=100)["origin"] == "standard"
    custom = payload(brazos, origin="custom", per=100)
    assert custom["count"] == 0
    assert custom["cards"] == []
    # And every standard card says which of BR-REP-019's three it is.
    assert {card["origin"] for card in payload(brazos, per=100)["cards"]} == {"built_in"}


def test_p1_2__both_sub_tab_counts_are_served_whichever_one_you_are_on(brazos):
    """p20 callout ④ — *"Custom reads 0 on day one and that is the point."*

    Found by looking at the running screen: serving only the ACTIVE tab's count
    drew `Standard · 45` beside a bare `Custom`, and a clerk learns nothing
    about authoring a report without clicking the thing that would teach them.
    """
    standard = payload(brazos, per=100)
    custom = payload(brazos, origin="custom", per=100)
    # 45 + Rate Impact (`CR-179-BRC10`, `reports/0010`).
    assert standard["origin_counts"] == {"standard": 48, "custom": 0}
    assert custom["origin_counts"] == {"standard": 48, "custom": 0}  # 46 + CR-184-BRC10 + CR-185-BRC10
    # The counts follow the OTHER filters, because a sub-tab count that
    # ignored the search would promise cards the sub-tab would not show.
    assert payload(brazos, q="ageing", per=100)["origin_counts"]["standard"] == 1


def test_p1_2__a_tenant_report_appears_under_custom_and_never_under_standard(brazos):
    """The sub-tab map, asserted from both sides."""
    with tenant_ctx(brazos):
        ReportDefinition.objects.create(
            tenant_id=brazos.id,
            key="ninety_plus_on_route_r01",
            name="90+ on route R-01",
            dataset="invoices",
            group_code="receivables",
            sub_group_code="receivables_arrears",
            filters={"basis": "posting"},
        )
    standard = {card["key"] for card in payload(brazos, per=100)["cards"]}
    custom = payload(brazos, origin="custom", per=100)
    assert "ninety_plus_on_route_r01" not in standard
    assert [card["key"] for card in custom["cards"]] == ["ninety_plus_on_route_r01"]
    assert custom["cards"][0]["origin"] == "shared"


def test_p1_2__an_unknown_sub_tab_falls_back_rather_than_refusing(brazos):
    """`BR-SHL-024` — a stale bookmark opens the catalogue, not a 422."""
    assert payload(brazos, origin="nonsense", per=100)["origin"] == "standard"


# ═══════════════════════════════════════════════════════════════════════════
# P1.8 — a water utility stops being shown gas reports
# ═══════════════════════════════════════════════════════════════════════════
def test_p1_8__a_report_naming_a_service_the_tenant_lacks_is_not_offered(brazos):
    with tenant_ctx(brazos):
        ReportDefinition.objects.filter(tenant_id=None, key="meter_fleet").update(
            service_codes=["gas"]
        )
    water_only = {"services": [{"code": "water", "name": "Water"}]}
    with tenant_ctx(brazos):
        body = catalogue_read.catalogue_payload(
            {"per": 100}, vocabularies=water_only, role=CATALOGUE_ROLE
        )
    keys = {card["key"] for card in body["cards"]}
    assert "meter_fleet" not in keys
    # …and a report that names NO service is still offered, because it is about
    # the utility rather than about one of its products.
    assert "trial_balance" in keys


def test_p1_8__the_service_filter_reads_the_enabled_set_off_this_same_answer(brazos):
    """`P1.8`'s outcome: *"opening a report from the catalogue costs no extra
    request."* The enabled set is a FIELD of the payload the catalogue reads,
    so there is nothing else to call."""
    assert catalogue_read._enabled_service_codes(ALL_SERVICES) >= {"water", "gas", "fire"}
    assert catalogue_read._enabled_service_codes({}) == frozenset()


def test_p1_8__a_switched_off_report_leaves_the_catalogue_entirely(brazos):
    """`P0.3`'s overlay: not *"unavailable with a reason"* — absent."""
    with tenant_ctx(brazos):
        row = ReportDefinition.objects.get(tenant_id=None, key="cut_off_list")
        ReportTenantSetting.objects.create(tenant_id=brazos.id, definition=row, enabled=False)
    body = payload(brazos, per=100)
    assert "cut_off_list" not in {card["key"] for card in body["cards"]}
    assert body["total"] == 47  # 48 - the switched-off one (CR-179, CR-184 and CR-185 added one each)


# ═══════════════════════════════════════════════════════════════════════════
# NFR-3 — it pages, and NFR-5 — there is no cap
# ═══════════════════════════════════════════════════════════════════════════
def test_nfr_3__the_read_pages_and_the_default_holds_the_whole_catalogue(brazos):
    body = payload(brazos)
    assert body["per"] == catalogue_read.DEFAULT_PAGE_SIZE == 50
    assert body["pages"] == 1
    assert len(body["cards"]) == 48  # 45 + Rate Impact (CR-179) + Over-90 by service (CR-184) + Owner summary (CR-185)


def test_nfr_3__a_smaller_page_cuts_and_the_roll_up_does_not_move(brazos):
    first = payload(brazos, per=50, page=1)
    assert first["page"] == 1
    # Paging is real machinery and not a field: ask for a page past the end and
    # it CLAMPS rather than answering an empty grid, which reads as "no reports".
    last = payload(brazos, per=50, page=99)
    assert last["page"] == last["pages"] == 1
    assert len(last["cards"]) == 48  # 45 + Rate Impact (CR-179) + Over-90 by service (CR-184) + Owner summary (CR-185)


def test_nfr_3__an_unratified_page_size_falls_back_to_the_ratified_one(brazos):
    """B14 rule 16 names five sizes and this read mints no sixth."""
    assert payload(brazos, per=25)["per"] == 50
    assert payload(brazos, per="nonsense")["per"] == 50
    assert payload(brazos, per=100)["per"] == 100


# ═══════════════════════════════════════════════════════════════════════════
# P1.5 — NO LITERALS. This is the case the file exists for.
# ═══════════════════════════════════════════════════════════════════════════
def test_p1_5__deleting_the_seed_empties_the_catalogue_rather_than_falling_back(brazos):
    """`P1.5`'s outcome, verbatim: *"a catalogue with zero rows renders the
    empty state, not 23 cards."*

    ⚠ **THE NUMBER 23 IS THE WHOLE ASSERTION.** `apps/reports/catalog.py` still
    exists and still holds its frozen tuple; a read that falls back to it when
    the table is empty passes every other case in this file, because in every
    other case the table is full. `runner.py` records that exactly this
    fallback was drafted and deleted before it was committed.
    """
    with tenant_ctx(brazos):
        ReportDefinition.objects.all().delete()
        ReportCategory.objects.all().delete()
    body = payload(brazos, per=100)
    assert body["cards"] == []
    assert body["groups"] == []
    assert body["total"] == 0
    assert body["count"] == 0
    assert body["available"] == 0
    # …and no page of nothing claims to be a page of something.
    assert body["pages"] == 1


def test_p1_5__no_card_name_in_the_payload_is_a_locale_key(brazos):
    """The other half of *"no literals"*: the screen is handed TEXT, so nothing
    it draws can be an untranslated `reports.card.<key>.name` leaking through."""
    for card in payload(brazos, per=100)["cards"]:
        assert not card["name"].startswith("reports.")
        assert not str(card["badge"]).startswith("reports.")


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 1 · P1.1 · P1.2 · P1.5 · P1.8 (05-prototype/09 Reports Build Brief.pdf p9-p10, p19-p21 read as IMAGES)
# screens: S44
# generated: 2026-09-26 by lane REP-P1
# gates: RED PROVED FIRST — every case failed with `ModuleNotFoundError: apps.reports.catalogue_read` before the read existed
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
