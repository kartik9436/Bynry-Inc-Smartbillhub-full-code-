# ── Trace ──────────────────────────────────────────────
# Story:    CR-115-BRC05 §7 — *"CUSTOM URLs ON A CONNECTOR"*, PO 2026-09-17.
#           R32 (the form) · R33 (the standard list) · R34 (a new KIND is a
#           Runbook) · R35 (no field mapping) · R36 (Edit; standard = switch
#           only).
# Rules:    BR-INT-078 (§7.5's five rules) · BR-INT-037 / G77 (data, never a
#           branch on a provider key) · CLAUDE.md hard rule 1 (tenant scoping)
#           · hard-won law 2's mirror (a switch that changes nothing) · law 7
#           (prove it RED first, in the harness that will run it; and name what
#           would make it pass wrongly).
# ───────────────────────────────────────────────────────
"""The per-API table and form — the server half, with no screen in the room.

⚠ **THE POINT OF THIS FILE IS THAT IT NEVER OPENS A BROWSER.** `CR-115-BRC05`
§7.5 rule 1: *"A form-only rule is a rule until someone calls the API
directly."* Every refusal below is asserted against the SERVICE or the ROUTE, so
a future screen that forgets to check — or a curl, or a Runbook — meets the same
answer a clerk does. The browser walk
(`10-scripts/cr115_custom_apis_walkthrough.mjs`) proves the other half, and §7.6
is explicit that it is the half that counts for the save path: *"Prove a save
works in a BROWSER, not with a passing test."*

── WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2) ──────────────────────
 1 **A REFUSAL THAT FIRES FOR THE WRONG REASON.** `pytest.raises(BizError)`
   passes on ANY business refusal — *not connected*, *sandbox only*, a typo in a
   provider key. So every refusal case below asserts the `message_key`, which is
   the thing a clerk actually reads and the only part that distinguishes one
   refusal from another.
 2 **A RULE PROVED ONLY IN THE DIRECTION THAT REFUSES.** A guard that refuses
   everything passes every refusal test ever written — hard-won law 7's
   *incapable of passing*. So each rule is asserted in BOTH directions: the
   second sync is refused AND the first one is accepted; a standard row cannot
   be edited AND a custom row can.
 3 **A MERGE THAT IS REALLY A CONCATENATION.** Two layers whose candidates
   happen to arrive in ranked order would pass a naive assertion on the merged
   list. So the merge case feeds the SECOND layer the better match and asserts
   it comes FIRST — an order that concatenation cannot produce.
 4 **A SWITCH THAT IS OBEYED BY THE SELECTOR AND NOT BY THE RUNNER.** Serving
   `enabled: false` and going on calling the layer is exactly law 2's mirror and
   would satisfy any assertion made against the payload. So the disabled-lookup
   case asserts on the URLS ACTUALLY DIALLED, recorded by a fake transport.
"""

from __future__ import annotations

import pytest

from apps.integrations import custom_apis, gis, models, selectors
from apps.integrations import api as integrations_api
from apps.integrations import services as integration_services
from core import errors
from core.permissions import SYSTEM_ADMIN
from core.tenancy import tenant_context
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: A reserved host `gis_fixtures.transport_for` answers from a recording. ⚠ It
#: is the ONE host that cannot fail to connect, so it is never used here to
#: stand in for an unreachable City — see `test_..._city_not_answering`.
LAYER = "https://gis.brazosbend.example/addr"
SECOND_LAYER = "https://points.brazosbend.example/addr"


def _connect(tenant, actor, *, environment=models.ENVIRONMENT_PRODUCTION, base_url=LAYER):
    """⚠ **INSIDE `tenant_context`** — `connect` writes an audit row and
    `core.audit` refuses one with no tenant set (`BR-AUD-007`)."""
    with tenant_context(tenant.id):
        return integration_services.connect(
            actor=actor,
            tenant_id=tenant.id,
            provider_key=gis.PROVIDER_KEY,
            environment=environment,
            config={"base_url": base_url},
            cadence=models.CADENCE_NIGHTLY,
        )


def _manifest():
    from apps.integrations.registry import REGISTRY

    return REGISTRY.get(gis.PROVIDER_KEY)


def _add(tenant, actor, connection, *, kind, name, url):
    with tenant_context(tenant.id):
        return custom_apis.add(
            actor=actor, connection=connection, kind=kind, name=name, url=url
        )


# ═══════════════════════════════════════════════════════════════════════════
# §7.2 — THE KIND IS OURS. THE NAME IS THEIRS.
# ═══════════════════════════════════════════════════════════════════════════


def test_the_closed_list_is_only_kinds_this_connector_has_code_for(brazos, dana):
    """*"Nothing addable can lack code behind it"* — as a fact, not a promise.

    ⚠ **THIS IS THE ASSERTION THAT MAKES §7.2 MECHANICAL.** A Kind reaches the
    form only where the operation that RUNS it is declared on the manifest, so
    the closed list cannot drift open by somebody adding a constant.
    """
    manifest = _manifest()
    assert custom_apis.kinds_for(manifest) == [
        custom_apis.KIND_ADDRESS_LOOKUP,
        custom_apis.KIND_SCHEDULED_SYNC,
        custom_apis.KIND_MAP_TILES,
    ]
    for kind in custom_apis.kinds_for(manifest):
        operation = custom_apis.operation_of_kind(manifest.key, kind)
        assert operation in {one.name for one in manifest.operations}


def test_a_connector_whose_every_api_is_bespoke_offers_no_kinds():
    """The half of the earlier, broader ruling that §7.2 KEEPS.

    `email_smtp` is not a protocol reader for a layer a customer can point at,
    so it offers nothing and its screen draws no form — which is the honest
    answer rather than an empty dropdown.
    """
    from apps.integrations.registry import REGISTRY

    assert custom_apis.kinds_for(REGISTRY.get("email_smtp")) == []


def test_a_kind_we_do_not_ship_is_refused_by_name(brazos, dana):
    """R34 — *"a genuinely new KIND of call is a Runbook, not a form field"*."""
    connection = _connect(brazos, dana)
    with pytest.raises(errors.ValidationError) as caught:
        _add(brazos, dana, connection, kind="zoning_layer", name="Zoning", url=LAYER)
    assert caught.value.message_key == custom_apis.REFUSAL_UNKNOWN_KIND


def test_add_takes_no_field_mapping_argument():
    """R35, PO verbatim: *"DOnt add field Mapping here - remove it"*.

    ⚠ **ASSERTED ON THE SIGNATURE, WHICH IS THE ONLY THING THAT CANNOT BE
    SATISFIED BY OMISSION.** A test that merely never passes a mapping would go
    on passing the day somebody adds the parameter back — the removal was BY
    NAME and it is the name this guards.
    """
    import inspect

    taken = set(inspect.signature(custom_apis.add).parameters)
    assert not {one for one in taken if "map" in one.lower()}, (
        "field mapping was removed by the PO by name (R35) and must not return"
    )


# ═══════════════════════════════════════════════════════════════════════════
# §7.4 — the table: ours and theirs in ONE list, ours marked as standard
# ═══════════════════════════════════════════════════════════════════════════


def test_ours_and_theirs_arrive_in_one_list_with_ours_marked(brazos, dana):
    connection = _connect(brazos, dana)
    _add(brazos, dana, connection, kind=custom_apis.KIND_ADDRESS_LOOKUP,
         name="Address points", url=SECOND_LAYER)
    with tenant_context(brazos.id):
        card = selectors.provider_card(brazos.id, gis.PROVIDER_KEY)
    rows = card["operations"]
    assert len(rows) == 4, "three of ours plus one of theirs, in one list"
    standard = [one for one in rows if one["is_standard"]]
    custom = [one for one in rows if not one["is_standard"]]
    assert len(standard) == 3 and len(custom) == 1
    assert custom[0]["custom_name"] == "Address points"
    assert custom[0]["api_kind"] == custom_apis.KIND_ADDRESS_LOOKUP
    # The clerk's row sits BESIDE the API it borrows, not at the bottom.
    assert rows[1] is custom[0]


def test_the_custom_row_carries_its_own_url_and_says_so(brazos, dana):
    """§7.7 — the provenance is required, and the screen must never re-derive it.

    ⚠ **BOTH HALVES.** The address is the clerk's AND `endpoint_source` names
    the rung that answered, so a screen can print *its own* against *using the
    connector's address* without looking at `host_field` and `settings` — which
    is what `DEF-INT-5613` was.
    """
    from apps.integrations import addressing

    connection = _connect(brazos, dana)
    _add(brazos, dana, connection, kind=custom_apis.KIND_ADDRESS_LOOKUP,
         name="Address points", url=SECOND_LAYER)
    with tenant_context(brazos.id):
        card = selectors.provider_card(brazos.id, gis.PROVIDER_KEY)
    theirs = [one for one in card["operations"] if not one["is_standard"]][0]
    ours = [one for one in card["operations"] if one["name"] == "address_search"
            and one["is_standard"]][0]
    assert theirs["endpoint"] == SECOND_LAYER
    assert theirs["endpoint_source"] == addressing.SOURCE_API_ROW
    assert ours["endpoint"] == LAYER
    # ⚠ **RUNG 1, NOT RUNG 2, AND THE FIRST DRAFT OF THIS LINE GUESSED WRONG.**
    # `address_search` declares no `host_field`, so it takes the default
    # `base_url` — and `gis_esri` really DOES declare a field of that name, so
    # the operation's own field answers. Fifteen of eighteen manifests name
    # `base_url` and never declare it (`DEF-INT-5488`), which is what makes
    # rung 2 necessary elsewhere and unreachable here. The ladder is right; the
    # expectation was wrong, and it is written down because the same guess will
    # be made again.
    assert ours["endpoint_source"] == addressing.SOURCE_OPERATION_FIELD


def test_a_configured_kind_drops_out_of_the_dropdown(brazos, dana):
    """§7.4 — *"one configuration per API, never two"*, in BOTH directions."""
    connection = _connect(brazos, dana)
    manifest = _manifest()
    before = {one["kind"] for one in custom_apis.addable_kinds(connection, manifest)}
    assert custom_apis.KIND_ADDRESS_LOOKUP in before
    _add(brazos, dana, connection, kind=custom_apis.KIND_ADDRESS_LOOKUP,
         name="Address points", url=SECOND_LAYER)
    after = {one["kind"] for one in custom_apis.addable_kinds(connection, manifest)}
    assert custom_apis.KIND_ADDRESS_LOOKUP not in after
    assert custom_apis.KIND_MAP_TILES in after, "only the configured one leaves"


def test_the_server_refuses_a_second_configuration_of_one_kind(brazos, dana):
    """The dropdown hides it; this is what answers a caller who did not look."""
    connection = _connect(brazos, dana)
    _add(brazos, dana, connection, kind=custom_apis.KIND_ADDRESS_LOOKUP,
         name="Address points", url=SECOND_LAYER)
    with pytest.raises(errors.BizError) as caught:
        _add(brazos, dana, connection, kind=custom_apis.KIND_ADDRESS_LOOKUP,
             name="Another layer", url="https://third.brazosbend.example/addr")
    assert caught.value.message_key == custom_apis.REFUSAL_ALREADY_CONFIGURED


# ═══════════════════════════════════════════════════════════════════════════
# §7.4 R36 — standard APIs switch, and do NOT edit or delete
# ═══════════════════════════════════════════════════════════════════════════


def test_a_standard_api_may_be_switched_but_not_edited_or_deleted(brazos, dana):
    """R36 verbatim: *"standard APis those will be availabel for enable diable
    but those will not be editable"*. All three directions asserted."""
    connection = _connect(brazos, dana)
    with tenant_context(brazos.id):
        row = custom_apis.switch(
            actor=dana, connection=connection,
            operation_name="address_search", enabled=False,
        )
        assert row.is_standard and row.enabled is False

        with pytest.raises(errors.BizError) as edited:
            custom_apis.edit(actor=dana, connection=connection, row_id=row.id,
                             name="My own name")
        assert edited.value.message_key == custom_apis.REFUSAL_STANDARD_LOCKED

        with pytest.raises(errors.BizError) as removed:
            custom_apis.remove(actor=dana, connection=connection, row_id=row.id)
        assert removed.value.message_key == custom_apis.REFUSAL_STANDARD_LOCKED


def test_a_custom_api_may_be_edited_and_deleted(brazos, dana):
    """The other direction, without which the test above proves only that
    everything is refused (law 7's *incapable of passing*)."""
    connection = _connect(brazos, dana)
    row = _add(brazos, dana, connection, kind=custom_apis.KIND_ADDRESS_LOOKUP,
               name="Address points", url=SECOND_LAYER)
    with tenant_context(brazos.id):
        edited = custom_apis.edit(
            actor=dana, connection=connection, row_id=row.id,
            name="Qualified addresses", url="https://q.brazosbend.example/addr",
        )
        assert edited.name == "Qualified addresses"
        assert edited.url == "https://q.brazosbend.example/addr"
        custom_apis.remove(actor=dana, connection=connection, row_id=row.id)
        assert custom_apis.custom_rows(connection) == []


# ═══════════════════════════════════════════════════════════════════════════
# §7.5 rule 1 — ONE scheduled sync per connector, at the form AND on the server
# ═══════════════════════════════════════════════════════════════════════════


def test_a_second_scheduled_sync_is_refused_because_a_sync_writes(brazos, dana):
    """Rule 1. The connector already ships one, so a custom one is the SECOND.

    ⚠ **THE REASON IS THE TEST'S NAME ON PURPOSE.** §7.5: *"Each reason belongs
    IN THE CODE, or the rule reads as arbitrary and the next lane simplifies it
    away."* Two syncs pointed at two layers both update the same premises and
    the last to run wins SILENTLY — nothing downstream can tell.
    """
    connection = _connect(brazos, dana)
    manifest = _manifest()
    assert custom_apis.active_sync_count(connection, manifest) == 1
    with pytest.raises(errors.BizError) as caught:
        _add(brazos, dana, connection, kind=custom_apis.KIND_SCHEDULED_SYNC,
             name="Parcels, second layer", url=SECOND_LAYER)
    assert caught.value.message_key == custom_apis.REFUSAL_SECOND_SYNC


def test_the_form_is_told_the_same_thing_the_server_would_answer(brazos, dana):
    """The form half of rule 1 — and it must AGREE with the server half.

    ⚠ **A FORM THAT REFUSES SOMETHING THE SERVER ALLOWS, OR ALLOWS SOMETHING THE
    SERVER REFUSES, IS TWO RULES.** This asserts the served `refusal` key is the
    SAME key `add` raises, so the sentence a clerk reads before typing is the
    sentence they would have got after.
    """
    connection = _connect(brazos, dana)
    offered = {one["kind"]: one["refusal"]
               for one in custom_apis.addable_kinds(connection, _manifest())}
    assert offered[custom_apis.KIND_SCHEDULED_SYNC] == custom_apis.REFUSAL_SECOND_SYNC
    assert offered[custom_apis.KIND_ADDRESS_LOOKUP] is None


def test_switching_the_standard_sync_off_makes_room_for_a_custom_one(brazos, dana):
    """Rule 1 in the direction that ACCEPTS, which is what stops it being a
    guard that refuses everything.

    It is also the whole reason the Kind stays in the dropdown rather than
    vanishing: the clerk has a real way through it.
    """
    connection = _connect(brazos, dana)
    with tenant_context(brazos.id):
        custom_apis.switch(actor=dana, connection=connection,
                           operation_name="reconcile_parcels", enabled=False)
    assert custom_apis.active_sync_count(connection, _manifest()) == 0
    row = _add(brazos, dana, connection, kind=custom_apis.KIND_SCHEDULED_SYNC,
               name="Parcels, our own layer", url=SECOND_LAYER)
    assert row.url == SECOND_LAYER


def test_the_standard_sync_cannot_be_switched_back_on_beside_a_custom_one(brazos, dana):
    """Rule 1 through the OTHER door.

    ⚠ **A RULE ENFORCED ONLY WHERE IT WAS FIRST WRITTEN IS A RULE WITH A HOLE IN
    IT.** Turning the shipped sync back on while a custom one runs produces the
    two writers rule 1 exists to prevent, without ever touching the Add form.
    """
    connection = _connect(brazos, dana)
    with tenant_context(brazos.id):
        custom_apis.switch(actor=dana, connection=connection,
                           operation_name="reconcile_parcels", enabled=False)
    _add(brazos, dana, connection, kind=custom_apis.KIND_SCHEDULED_SYNC,
         name="Parcels, our own layer", url=SECOND_LAYER)
    with tenant_context(brazos.id):
        with pytest.raises(errors.BizError) as caught:
            custom_apis.switch(actor=dana, connection=connection,
                               operation_name="reconcile_parcels", enabled=True)
    assert caught.value.message_key == custom_apis.REFUSAL_SECOND_SYNC


# ═══════════════════════════════════════════════════════════════════════════
# §7.5 rule 2 — Address lookup MERGES, and ranks together
# ═══════════════════════════════════════════════════════════════════════════


def test_two_enabled_lookups_are_both_searched_and_ranked_together(brazos, dana, monkeypatch):
    """Rule 2 — *"a city with a qualified-address layer AND an address-points
    layer just works"*.

    ⚠ **THE SECOND LAYER IS GIVEN THE BETTER MATCH ON PURPOSE.** If the merge
    were a concatenation, the first layer's rows would come first whatever a
    clerk typed and this assertion would fail — which is the point. The ranking
    is `gis_search.rank_key`, which already existed (§7.5: *"find it, do not
    rebuild it"*).
    """
    connection = _connect(brazos, dana)
    _add(brazos, dana, connection, kind=custom_apis.KIND_ADDRESS_LOOKUP,
         name="Address points", url=SECOND_LAYER)

    dialled: list[str] = []

    def fake(url, timeout_s):
        dialled.append(url)
        if url.startswith(SECOND_LAYER):
            # The EXACT street the clerk typed — rank_key's first tie-break.
            return {"candidates": [
                {"parcel": "P-2", "point_id": "PT-2", "address_line": "100 Maple St",
                 "city": "Brazos Bend", "state": "TX", "postal_code": "77001"},
            ]}
        return {"candidates": [
            {"parcel": "P-1", "point_id": "PT-1", "address_line": "100 Maple Street West",
             "city": "Brazos Bend", "state": "TX", "postal_code": "77001"},
        ]}

    monkeypatch.setattr("apps.integrations.gis_fixtures.transport_for", lambda url: fake)
    with tenant_context(brazos.id):
        found = gis.search(brazos.id, query="100 Maple St")

    assert len({one.split("?")[0] for one in dialled}) == 2, "both layers dialled"
    parcels = [one["parcel"] for one in found["candidates"]]
    assert parcels == ["P-2", "P-1"], "ranked together, not concatenated"


def test_the_merge_adds_no_second_ordering_of_its_own(brazos, dana, monkeypatch):
    """⚠ **THE HALF OF RULE 2 THAT IS ABOUT NOT ADDING A SECOND RANKER.**

    `_merged` merges and de-duplicates; `gis_search.rank_candidates`, which
    `search()` already calls, is the ONE ordering. *Ranked together* is then true
    by construction — two layers become one list, and one ranker sorts it.

    ⚠ **THE FIRST BUILD RANKED IN BOTH PLACES**, because `rank_candidates` did
    not exist when `_merged` was written and did by the time it was rebased onto
    the tip. Two orderings that agree today are two that can disagree tomorrow,
    and nothing goes red when they do. It also turned `test_us_int_042_gis.py`'s
    TC-1 red — **a sibling suite's red was the finding** (law 7 habit 1).

    So this asserts on `_merged` DIRECTLY: hand it one batch out of the City's
    order and get it back in the City's order, untouched.
    """
    out_of_order = [
        {"parcel": "P-9", "point_id": "PT-9", "address_line": "900 Zebra Way"},
        {"parcel": "P-1", "point_id": "PT-1", "address_line": "100 Maple St"},
    ]
    assert [one["parcel"] for one in gis._merged([out_of_order])] == ["P-9", "P-1"]


def test_the_merge_de_duplicates_without_collapsing_a_block_of_flats(brazos, dana):
    """Two layers legitimately share a parcel — one row per PARCEL from a
    qualified-address layer, one per DOOR from an address-points layer.

    ⚠ **DE-DUPLICATING ON THE PARCEL ALONE WOULD SILENTLY DROP EVERY UNIT BUT
    ONE**, which is the opposite of what merging two layers is for. The same
    row arriving from both layers IS dropped, which is the case the key is for.
    """
    parcels = [{"parcel": "P-1", "point_id": "", "address_line": "1 High St"}]
    points = [
        {"parcel": "P-1", "point_id": "A", "address_line": "1 High St", "unit": "A"},
        {"parcel": "P-1", "point_id": "B", "address_line": "1 High St", "unit": "B"},
        {"parcel": "P-1", "point_id": "", "address_line": "1 High St"},  # the same row twice
    ]
    merged = gis._merged([parcels, points])
    assert len(merged) == 3, "two doors and their building survive; the repeat does not"


def test_a_switched_off_lookup_is_not_called_at_all(brazos, dana, monkeypatch):
    """Rule 3, asserted on the URLS DIALLED and not on the payload.

    ⚠ **SERVING `enabled: false` AND GOING ON CALLING IT WOULD PASS ANY
    ASSERTION MADE AGAINST THE SCREEN'S DATA** — that is hard-won law 2's mirror
    exactly, a control that renders and changes nothing. So this records what
    the transport was actually asked for.
    """
    connection = _connect(brazos, dana)
    _add(brazos, dana, connection, kind=custom_apis.KIND_ADDRESS_LOOKUP,
         name="Address points", url=SECOND_LAYER)
    rows = custom_apis.custom_rows(connection)
    with tenant_context(brazos.id):
        custom_apis.switch(actor=dana, connection=connection,
                           row_id=rows[0].id, enabled=False)

    dialled: list[str] = []

    def fake(url, timeout_s):
        dialled.append(url)
        return {"candidates": []}

    monkeypatch.setattr("apps.integrations.gis_fixtures.transport_for", lambda url: fake)
    with tenant_context(brazos.id):
        gis.search(brazos.id, query="100 Maple St")

    assert dialled, "the enabled one is still called"
    assert not any(one.startswith(SECOND_LAYER) for one in dialled), (
        "a disabled API is NOT called — §7.5 rule 3"
    )


def test_every_lookup_switched_off_says_so_rather_than_answering_nothing(brazos, dana, monkeypatch):
    """Rule 3, and the honest sentence.

    *No matching address found* and *nobody is looking* are different facts. A
    clerk who has just used the switch must not read the first one, or they file
    a defect against correct behaviour.
    """
    connection = _connect(brazos, dana)
    with tenant_context(brazos.id):
        custom_apis.switch(actor=dana, connection=connection,
                           operation_name="address_search", enabled=False)

    dialled: list[str] = []
    monkeypatch.setattr(
        "apps.integrations.gis_fixtures.transport_for",
        lambda url: (lambda u, timeout_s: dialled.append(u) or {"candidates": []}),
    )
    with tenant_context(brazos.id):
        found = gis.search(brazos.id, query="100 Maple St")

    assert dialled == [], "nothing is dialled at all"
    assert found["candidates"] == []
    assert found["message_key"] == gis.REFUSAL_LOOKUP_OFF
    assert found["reachable"] is True, "the City is fine; we chose not to ask"


def test_a_switched_off_sync_does_not_run_and_leaves_no_run_row(brazos, dana):
    """Rule 3's other half — and it is checked BEFORE the run row is started.

    A run recorded and then refused would put a failure in RECENT ACTIVITY every
    night for a connector working exactly as its owner told it to.
    """
    connection = _connect(brazos, dana)
    with tenant_context(brazos.id):
        custom_apis.switch(actor=dana, connection=connection,
                           operation_name="reconcile_parcels", enabled=False)
        before = models.IntegrationRun.objects.filter(connection=connection).count()
        with pytest.raises(gis.GisRefusal) as caught:
            gis.reconcile(dana, brazos.id, mode="preview",
                          started_by="person", started_by_name="Dana Whitfield")
        after = models.IntegrationRun.objects.filter(connection=connection).count()
    assert caught.value.message_key == gis.REFUSAL_SYNC_OFF
    assert after == before, "no run row for a sync that never ran"


# ═══════════════════════════════════════════════════════════════════════════
# §7.5 rule 4 — the count, and rule 5 — DEF-INT-5597 stays fixed
# ═══════════════════════════════════════════════════════════════════════════


def test_the_state_word_is_still_the_connectors_and_not_an_api_average(brazos, dana):
    """Rule 5 — *"Do NOT undo `DEF-INT-5597`"*.

    ⚠ **THIS IS THE TRAP RULE 4 SETS.** A lane implementing *the State word
    counts only enabled APIs* by filtering operation states into `display_state`
    would rebuild the aggregate `DEF-INT-5597` removed. The State word counts NO
    APIs — it is `connection.status` — so switching one off cannot move it, and
    this asserts exactly that.
    """
    connection = _connect(brazos, dana)
    with tenant_context(brazos.id):
        before = selectors.provider_card(brazos.id, gis.PROVIDER_KEY)["display_state"]
        custom_apis.switch(actor=dana, connection=connection,
                           operation_name="address_search", enabled=False)
        after = selectors.provider_card(brazos.id, gis.PROVIDER_KEY)["display_state"]
    assert before == after == connection.status


def test_the_switch_travels_to_the_screen_so_the_count_can_obey_rule_4(brazos, dana):
    """Rule 4's input. The tile filters on this; serving it is the server half."""
    connection = _connect(brazos, dana)
    with tenant_context(brazos.id):
        custom_apis.switch(actor=dana, connection=connection,
                           operation_name="address_search", enabled=False)
        card = selectors.provider_card(brazos.id, gis.PROVIDER_KEY)
    by_name = {one["name"]: one for one in card["operations"] if one["is_standard"]}
    assert by_name["address_search"]["enabled"] is False
    assert by_name["map_tiles"]["enabled"] is True, "absence still means ON"


# ═══════════════════════════════════════════════════════════════════════════
# The routes, and hard rule 1
# ═══════════════════════════════════════════════════════════════════════════


def test_the_route_adds_a_custom_api_and_answers_the_refreshed_card(brazos, dana):
    """§7.6's regression risk: the new rows go through a route of their own,
    round `PATCH /integrations/{key}`, whose save path PRUNES unknown config
    names (`DEF-INT-5582`) and would have deleted them on the next Edit save."""
    _connect(brazos, dana)
    response = api_call(
        integrations_api.custom_api_list, "post",
        f"/api/{brazos.subdomain}/integrations/{gis.PROVIDER_KEY}/apis",
        user=dana.user, role=SYSTEM_ADMIN, tenant=brazos, key=gis.PROVIDER_KEY,
        data={"kind": custom_apis.KIND_ADDRESS_LOOKUP,
              "name": "Address points", "url": SECOND_LAYER},
    )
    assert response.status_code == 200, response.data
    rows = [one for one in response.data["operations"] if not one["is_standard"]]
    assert len(rows) == 1 and rows[0]["custom_name"] == "Address points"


def test_the_screens_own_payload_carries_the_closed_list_and_the_rows(brazos, dana):
    """⚠ **THIS CASE EXISTS BECAUSE A BROWSER FOUND WHAT THE SUITE COULD NOT.**

    S142 draws its whole self from `runs.list_view`, not from
    `provider_card` — and the first build served `custom_api_kinds` on the card
    only. Every check passed: `tsc`, the whole backend suite, the front-end
    suite. The field is OPTIONAL on the wire and an empty array is a legal
    answer, so nothing anywhere could tell *the connector offers no kinds* from
    *nobody plumbed it through*. The screen simply drew no `+ API` control and
    the entire feature was unreachable.

    That is hard-won law 2 with a SERVED FIELD in place of a prop, which is the
    shape this file's own neighbour records twice already: `G13` asks whether a
    prop has a caller, and **nothing asks whether a served field has a reader**.
    The lesson is the one CLAUDE.md law 6 states — no gate in this repo reads
    rendered output — so the assertion here is made against the payload THE
    SCREEN ACTUALLY FETCHES, by name.
    """
    from apps.integrations import runs
    from core.pagination import ListParams

    connection = _connect(brazos, dana)
    _add(brazos, dana, connection, kind=custom_apis.KIND_ADDRESS_LOOKUP,
         name="Address points", url=SECOND_LAYER)
    with tenant_context(brazos.id):
        payload = runs.list_view(brazos.id, gis.PROVIDER_KEY, params=ListParams())
    kinds = {one["kind"] for one in payload["custom_api_kinds"]}
    assert custom_apis.KIND_MAP_TILES in kinds, "the Add form has nothing to offer"
    assert custom_apis.KIND_ADDRESS_LOOKUP not in kinds, "one configuration per API"
    rows = payload["operations"]
    assert any(one["is_standard"] is False for one in rows), "theirs is in the screen's list"
    assert all("enabled" in one for one in rows), "the switch has nothing to draw from"


def test_an_edit_save_does_not_delete_the_custom_rows(brazos, dana):
    """`DEF-INT-5582`'s shape, asserted directly.

    ⚠ **THIS IS THE ONE THE CR NAMES AS RISK 1** and it is why the rows are a
    table rather than a `config` key: `update_connection` prunes `config` to
    what the manifest declares, so rows kept there would vanish on the next
    Edit save with every test green and nothing raised.
    """
    connection = _connect(brazos, dana)
    _add(brazos, dana, connection, kind=custom_apis.KIND_ADDRESS_LOOKUP,
         name="Address points", url=SECOND_LAYER)
    with tenant_context(brazos.id):
        integration_services.update_connection(
            actor=dana, tenant_id=brazos.id, provider_key=gis.PROVIDER_KEY,
            changes={"config": {"base_url": "https://moved.brazosbend.example/addr"}},
        )
        assert len(custom_apis.custom_rows(connection)) == 1


def test_one_utilitys_rows_are_invisible_to_another(brazos, lonestar, dana, erin):
    """CLAUDE.md hard rule 1, and §7.6 — *"Two utilities on the same connector
    configure it independently"*.

    ⚠ **SQLITE HAS NO RLS, SO THIS PROVES THE APPLICATION FILTER AND SAYS SO.**
    The database half — deny-by-default with no `app.tenant_id`, and FORCE for
    the owner too — is PostgreSQL-only and lives in
    `tests/test_cr115_custom_apis_pg.py`, which SKIPS here rather than passing
    vacuously (hard-won law 14).
    """
    ours = _connect(brazos, dana)
    theirs = _connect(lonestar, erin)
    _add(brazos, dana, ours, kind=custom_apis.KIND_ADDRESS_LOOKUP,
         name="Ours", url=SECOND_LAYER)
    assert [one.name for one in custom_apis.custom_rows(ours)] == ["Ours"]
    assert custom_apis.custom_rows(theirs) == []
    with tenant_context(lonestar.id):
        card = selectors.provider_card(lonestar.id, gis.PROVIDER_KEY)
    assert all(one["is_standard"] for one in card["operations"])


def test_a_url_that_is_not_one_is_refused_before_it_is_stored(brazos, dana):
    """A clerk typing a hostname with no scheme is `DEF-INT-5589`'s neighbour:
    the PATH is what names an ArcGIS layer, and a bare name answers nothing."""
    connection = _connect(brazos, dana)
    with pytest.raises(errors.ValidationError) as caught:
        _add(brazos, dana, connection, kind=custom_apis.KIND_ADDRESS_LOOKUP,
             name="Address points", url="gis.brazosbend.example")
    assert caught.value.message_key == custom_apis.REFUSAL_URL_SHAPE


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-115-BRC05 §7 (the 2026-09-17 rulings verbatim)
# generated: 2026-09-17 by the CR-115-BRC05 per-API lane
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr115_custom_apis.py · the PostgreSQL probe in tests/test_cr115_custom_apis_pg.py
# exceptions: per-API KEYS are deferred (DEF-INT-5680) so no case asserts one
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
