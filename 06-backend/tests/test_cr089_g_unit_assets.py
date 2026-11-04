# ── Trace ──────────────────────────────────────────────
# Story:    US-AST-001 (S49 registry read) · US-MET-002 (S15 unit detail)
#           Change: CR-089 wave G (`PUJ-30`, `PUJ-31`, `PUJ-32`)
# Rules:    BR-AST-005 (status semantics; Unassigned = no current assignment) ·
#           BR-AST-006 (the row's action set is the SERVER's) ·
#           BR-AST-020 (a status transition is legal FROM the current stage
#           only; retire is terminal and reachable only through its own
#           service) · BR-AST-041 (the registry's capability row) ·
#           BR-AST-500 (`assets.size_class` is TEXT holding a ratified code) ·
#           BR-TEN-171 (the ratified size-class ladders) · B14 rule 31 (a
#           catalogue CODE is a filter value and never a visible one)
# Defects:  DEF-AST-4734 (`f.assigned=false` was accepted and ignored) ·
#           DEF-AST-4735 (no seeded inventory spare says what size it is)
# ───────────────────────────────────────────────────────
"""`?terms=` — reading a clerk's own words as registry filters.

**WHY THE RESOLVER AND THE LIST ARE ONE ANSWER, TESTED TOGETHER.** `G1`'s whole
claim to a person is *"these chips are what I searched for"*. If the chips came
from one call and the rows from another, the two could disagree forever and no
assertion anywhere would notice — `BR-MET-1165`'s lesson one module over. So
every case here reads `resolved` OUT OF THE LIST ANSWER and then checks the rows
it arrived with.

⚠ **THE VOCABULARY IS THE TENANT'S OWN AND THE TESTS SPELL IT OUT.** Nothing
below types an English synonym: every word asserted is a row a tenant can rename
on Settings — `Meter`, `Inventory`, `Water 5/8"`, `AMI`. A test that matched on
words this repo invented would pass over a resolver that had stopped reading the
catalogue at all.
"""

import pytest

from apps.assets import api as assets_api
from apps.assets import selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    FakeUser,
    api_call,
    make_asset,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _labels(resolution):
    return [chip["label"] for chip in resolution["chips"]]


def _unit(actor, label="Unit A", address="1408 Bluestem Ln"):
    premise = make_premises(actor, address_line=address)
    return make_unit(actor, premise["id"], label=label, services=["electric", "water"])


class TestG1TheWordsAClerkIsHolding:
    def test_size_and_service_are_one_chip_because_the_size_class_is_named_for_both(
        self, brazos, dana
    ):
        """*5/8 water* is the whole of exactly one ratified row and not two."""
        with tenant_ctx(brazos):
            resolution = selectors.resolve_search_terms("5/8 water")
        assert _labels(resolution) == ['Water 5/8"']
        assert resolution["filters"] == {"size_class": "W-58"}
        assert resolution["unmatched"] == []

    def test_four_families_resolve_together_and_nothing_is_left_over(self, brazos, dana):
        with tenant_ctx(brazos):
            resolution = selectors.resolve_search_terms("5/8 water meter inventory")
        assert set(_labels(resolution)) == {'Water 5/8"', "Meter", "Inventory"}
        assert resolution["filters"] == {
            "size_class": "W-58",
            "type": "meter",
            "status": "inventory",
        }
        assert resolution["unmatched"] == []

    def test_a_word_the_catalogues_do_not_hold_comes_back_unmatched_rather_than_dropped(
        self, brazos, dana
    ):
        """*depot* is not this tenant's word for the shelf; *Inventory* is.

        ⚠ **AND THAT IS THE ANSWER TO CR-089 §6's OWN EXAMPLE.** The done-when
        sentence reads *"chips Water × and In the depot ×"*. No tenant anywhere
        in this product names a lifecycle stage *depot*, and inventing an
        English synonym table would be this repo's language exported to ten
        other catalogues (B14 rule 35). The word is reported back instead.
        """
        with tenant_ctx(brazos):
            resolution = selectors.resolve_search_terms("5/8 water depot")
        assert _labels(resolution) == ['Water 5/8"']
        assert resolution["unmatched"] == ["depot"]

    def test_a_prefix_of_three_letters_or_more_finds_the_stage(self, brazos, dana):
        with tenant_ctx(brazos):
            assert _labels(selectors.resolve_search_terms("invent")) == ["Inventory"]
            # Two letters is not enough: "in" would otherwise claim Inventory,
            # In repair and Installed at once and one of them would win by
            # alphabet rather than by meaning.
            assert selectors.resolve_search_terms("in")["unmatched"] == ["in"]

    def test_the_hyphen_is_a_separator_and_the_slash_is_not(self):
        """The tokenising regression, pinned at the level it happened.

        With `-` kept inside a token, `CART-35` was ONE word that *cart*
        prefix-matched, so typing **96 gallon cart** answered *Trash 35-gallon
        cart* — a more specific question giving a WRONGER answer, which is the
        opposite of what this feature is for. The slash must NOT split, because
        `5/8` is a size and not two numbers.

        ⚠ Asserted on the tokeniser rather than through a tenant, because the
        `brazos` fixture sells electricity and water and **no trash**, so its
        catalogue holds no cart at all. A test written against a service this
        tenant does not run would be red for a reason that has nothing to do
        with the rule.
        """
        assert selectors._term_tokens("CART-96") == ["cart", "96"]
        assert selectors._term_tokens("Trash 96-gallon cart") == ["trash", "96", "gallon", "cart"]
        assert selectors._term_tokens('Water 5/8"') == ["water", "5/8"]

    def test_a_code_that_shares_a_prefix_with_its_neighbours_still_resolves(
        self, brazos, dana
    ):
        """`W-1`, `W-112`, `W-2` … nine water bands, one shared prefix.

        The same fault, reachable on a tenant that exists: with `-` kept, every
        one of these was a single token that no typed word could reach.
        """
        with tenant_ctx(brazos):
            resolution = selectors.resolve_search_terms("112 w")
        assert _labels(resolution) == ['Water 1½"']

    def test_one_value_per_filter_key(self, brazos, dana):
        """Two stage words cannot both win, and the loser is reported."""
        with tenant_ctx(brazos):
            resolution = selectors.resolve_search_terms("inventory retired")
        assert len(resolution["chips"]) == 1
        assert list(resolution["filters"]) == ["status"]
        assert resolution["unmatched"] in (["inventory"], ["retired"])

    def test_empty_text_resolves_to_nothing_and_filters_nothing(self, brazos, dana):
        with tenant_ctx(brazos):
            assert selectors.resolve_search_terms("   ") == {
                "filters": {},
                "chips": [],
                "unmatched": [],
            }

    def test_the_list_answers_with_the_reading_it_filtered_by(self, brazos, dana):
        """`GET /assets?terms=` — the chips and the rows are ONE answer."""
        with tenant_ctx(brazos):
            make_asset(dana, asset_no="W-SPARE-1", service="water", unit="kgal")
            make_asset(dana, asset_no="E-SPARE-1", service="electric", unit="kWh")
            response = api_call(
                assets_api.assets,
                "get",
                user=FakeUser(),
                role="system_admin",
                tenant=brazos,
                query={"terms": "5/8 water", "per": "50"},
            )
        assert response.status_code == 200
        resolved = response.data["resolved"]
        assert _labels(resolved) == ['Water 5/8"']
        assert resolved["filters"] == {"size_class": "W-58"}
        numbers = [row["asset_no"] for row in response.data["results"]]
        assert "W-SPARE-1" in numbers
        # The electric spare carries electric's own smallest band, so the water
        # filter is doing work rather than passing everything through.
        assert "E-SPARE-1" not in numbers

    def test_a_route_asked_without_terms_answers_exactly_as_before(self, brazos, dana):
        """The parameter is ADDITIVE: no `terms`, no `resolved` key at all."""
        with tenant_ctx(brazos):
            make_asset(dana, asset_no="W-SPARE-2", service="water", unit="kgal")
            response = api_call(
                assets_api.assets, "get", user=FakeUser(), role="system_admin", tenant=brazos
            )
        assert response.status_code == 200
        assert "resolved" not in response.data

    def test_an_explicit_filter_beats_a_typed_word(self, brazos, dana):
        """A decision wins over a guess: `f.type` overrides the word *meter*."""
        with tenant_ctx(brazos):
            make_asset(dana, asset_no="W-SPARE-3", service="water", unit="kgal")
            services.create_asset(
                dana, {"type": "backflow", "asset_no": "BF-SPARE-3"}
            )
            response = api_call(
                assets_api.assets,
                "get",
                user=FakeUser(),
                role="system_admin",
                tenant=brazos,
                query={"terms": "meter", "f.type": "backflow", "per": "50"},
            )
        numbers = [row["asset_no"] for row in response.data["results"]]
        assert numbers == ["BF-SPARE-3"]
        # The chip is still SERVED, so the screen can say the word was read and
        # overruled rather than silently ignoring it.
        assert _labels(response.data["resolved"]) == ["Meter"]


class TestSizeClassFilter:
    def test_f_size_class_narrows_and_none_finds_the_unrecorded(self, brazos, dana):
        with tenant_ctx(brazos):
            make_asset(dana, asset_no="W-SIZED", service="water", unit="kgal")
            make_asset(
                dana, asset_no="W-UNSIZED", service="water", unit="kgal", size_class=None
            )
            sized = [a.asset_no for a in selectors.asset_list(filters={"size_class": "W-58"})]
            unsized = [a.asset_no for a in selectors.asset_list(filters={"size_class": "none"})]
        assert "W-SIZED" in sized and "W-UNSIZED" not in sized
        assert "W-UNSIZED" in unsized and "W-SIZED" not in unsized


class TestG2AssignedFromTheUnit:
    def test_assigned_false_is_the_complement_of_assigned_true(self, brazos, dana):
        """`DEF-AST-4734` — it was accepted, ignored, and answered EVERYTHING.

        A filter that only works one way is a check that cannot fail wearing a
        filter's clothes: a caller asking for the unattached rows got every row
        in the registry and no error anywhere.
        """
        with tenant_ctx(brazos):
            unit = _unit(dana, label="G2", address="1 G2 Way")
            spare = make_asset(dana, asset_no="W-SHELF", service="water", unit="kgal")
            fitted = make_asset(dana, asset_no="W-FITTED", service="water", unit="kgal")
            services.reassign_asset(dana, fitted["id"], {"unit_id": unit["id"]})

            free = [a.asset_no for a in selectors.asset_list(filters={"assigned": "false"})]
            taken = [a.asset_no for a in selectors.asset_list(filters={"assigned": "true"})]
        assert "W-SHELF" in free and "W-FITTED" not in free
        assert "W-FITTED" in taken and "W-SHELF" not in taken
        assert spare["asset_no"] == "W-SHELF"

    def test_a_stage_word_and_the_standing_narrowing_compose(self, brazos, dana):
        """The reason the picker sends `f.assigned=false` and not a status.

        Both narrowings apply at once, which two values of one key could never
        do — and if they could not, a chip would be drawn over rows it did not
        filter.
        """
        with tenant_ctx(brazos):
            unit = _unit(dana, label="G2B", address="2 G2 Way")
            make_asset(dana, asset_no="W-SHELF-2", service="water", unit="kgal")
            fitted = make_asset(dana, asset_no="W-FITTED-2", service="water", unit="kgal")
            services.reassign_asset(dana, fitted["id"], {"unit_id": unit["id"]})
            response = api_call(
                assets_api.assets,
                "get",
                user=FakeUser(),
                role="system_admin",
                tenant=brazos,
                query={"terms": "inventory", "f.assigned": "false", "per": "50"},
            )
        assert response.data["resolved"]["filters"] == {"status": "inventory"}
        numbers = [row["asset_no"] for row in response.data["results"]]
        assert "W-SHELF-2" in numbers
        assert "W-FITTED-2" not in numbers

    def test_the_row_says_whether_it_may_be_assigned(self, brazos, dana):
        """BR-AST-006 — the button reads this rather than repeating the rule."""
        with tenant_ctx(brazos):
            unit = _unit(dana, label="G2D", address="5 G2 Way")
            spare = make_asset(dana, asset_no="W-SHELF-3", service="water", unit="kgal")
            assert "assign" in spare["actions"]
            # ⚠ **BR-AST-020 HAS NO EDGE OUT OF `inventory` EXCEPT AN ASSIGN**,
            # so a spare cannot be marked faulty on the shelf — it has to be
            # fitted first. That is the rule and not a limitation of this test;
            # it is also why `G3`'s pencil lives on the ATTACHED table.
            services.reassign_asset(dana, spare["id"], {"unit_id": unit["id"]})
            services.log_maintenance(
                dana,
                spare["id"],
                {"kind": "repair", "detail": "seized", "status": "needs_repair"},
            )
            after = selectors.asset_detail(spare["id"])
        assert "assign" not in after["actions"]

    def test_the_assign_puts_the_meter_on_the_unit(self, brazos, dana):
        """`G2` end to end, through the very service the button calls."""
        with tenant_ctx(brazos):
            unit = _unit(dana, label="G2C", address="3 G2 Way")
            spare = make_asset(dana, asset_no="W-SHELF-4", service="water", unit="kgal")
            services.reassign_asset(
                dana, spare["id"], {"unit_id": unit["id"], "record_final_read": False}
            )
            landed = selectors.asset_detail(spare["id"])
        assert landed["assigned_unit_id"] == str(unit["id"])
        # BR-AST-020: inventory →(assign)→ active, so the unit's table shows it
        # as installed rather than as a spare that happens to be here.
        assert landed["behavior_class"] == "in_service"


class TestG3StatusFromTheUnit:
    def test_the_entry_carries_the_stage_the_date_and_the_reason(self, brazos, dana):
        with tenant_ctx(brazos):
            unit = _unit(dana, label="G3", address="4 G3 Way")
            asset = make_asset(dana, asset_no="W-G3", service="water", unit="kgal")
            services.reassign_asset(dana, asset["id"], {"unit_id": unit["id"]})
            result = services.log_maintenance(
                dana,
                asset["id"],
                {
                    "kind": "repair",
                    "detail": "Register glass cracked",
                    "date": "2026-09-08",
                    "status": "needs_repair",
                },
            )
            after = selectors.asset_detail(asset["id"])
        assert result["resulting_status"] == "needs_repair"
        assert after["status"] == "needs_repair"
        # ⚠ The asset stays ON the unit: a status change is not a removal, and
        # a clerk marking a meter faulty has not detached it.
        assert after["assigned_unit_id"] == str(unit["id"])

    def test_an_illegal_target_is_refused_whatever_a_screen_offered(self, brazos, dana):
        """BR-AST-020 — the client mirror is convenience; this is the law."""
        from core import errors

        with tenant_ctx(brazos):
            asset = make_asset(dana, asset_no="W-G3B", service="water", unit="kgal")
            with pytest.raises(errors.BizError) as caught:
                services.log_maintenance(
                    dana,
                    asset["id"],
                    {"kind": "repair", "detail": "x", "status": "in_repair"},
                )
        assert caught.value.br_ref == "BR-AST-020"

    def test_retire_is_not_reachable_through_this_door(self, brazos, dana):
        """BR-AST-030 — terminal, and only the retire service may reach it."""
        from core import errors

        with tenant_ctx(brazos):
            asset = make_asset(dana, asset_no="W-G3C", service="water", unit="kgal")
            with pytest.raises(errors.BizError):
                services.log_maintenance(
                    dana,
                    asset["id"],
                    {"kind": "repair", "detail": "x", "status": "retired"},
                )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-089 §6 wave G (G1 `PUJ-30` · G2 `PUJ-31` · G3 `PUJ-32`)
# generated: 2026-09-09 by the CR-089 wave G lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: E3 the done-when's word *depot* is asserted as UNMATCHED rather than as a chip — no tenant names a lifecycle stage that, and a synonym table would be English exported to ten catalogues (B14 rule 35). The stage's own name, `Inventory`, is what matches
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
