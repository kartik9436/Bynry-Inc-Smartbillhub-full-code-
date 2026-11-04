# ── Trace ──────────────────────────────────────────────
# Change:   CR-161-BRC10 wave W1 — Settings honesty for tenant custom fields
# Defects:  DEF-TEN-9153 (placement offered screens that draw nothing) ·
#           DEF-TEN-9155 (a shown field nobody collects saved) ·
#           DEF-TEN-9157 (a required field placed nowhere blocked New Account) ·
#           DEF-CUS-9158 (Account detail offered Input and had no control)
# Rules:    BR-TEN-046 (as amended 2026-10-02 — the NEVER list) · BR-TEN-052
#           (as amended — one served slot list, rendered slots only, an input
#           route for every shown field, required only where typed in) ·
#           BR-TEN-048 · CLAUDE.md hard-won laws 2 and 5
# ───────────────────────────────────────────────────────
"""W1's guards. The two that matter most are structural rather than behavioural:

* **THE PAIRING TEST** reads every `<CustomFieldsInput|CustomFieldsView
  entity=… screen=…>` in `07-frontend/src` and holds it against
  `custom_fields.SLOTS`. A slot marked rendered with no component drawing it is
  exactly `DEF-TEN-9153` (Settings offered nine screens; two drew anything); a
  component drawing a slot the list calls not-rendered is the mirror — a screen
  that would show a field Settings cannot place. **A later wave flips a slot in
  the same commit as its screen, and this test fails if either half lands
  alone.** It also counts every caller it could NOT parse and fails on any, so
  it cannot report zero over a shape it silently skipped (hard-won law 7).
* **THE NEVER TEST** refuses every record type the PO put out of scope
  (plans, rate schedules, invoices, invoice lines, journal entries and lines,
  the chart of accounts) and asserts no slot sits on a money screen.
"""

import dataclasses
import json
import pathlib
import re

import pytest

from apps.customers import models as customers_models
from apps.customers import seams as customer_seams
from apps.customers import services as customers_services
from apps.tenancy import custom_fields as cf_law
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from core import errors
from tests.test_us_cus_003_account_write import _create_payload, _unit_with_plan
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, lonestar, marcus, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

REPO = pathlib.Path(__file__).resolve().parents[2]
FRONTEND = REPO / "07-frontend" / "src"
EN = REPO / "07-frontend" / "src" / "i18n" / "locales" / "en.json"

CALLER_RE = re.compile(
    r'<(CustomFieldsInput|CustomFieldsView)\s+entity="([a-z_]+)"\s+screen="([A-Z0-9_]+)"'
)
OPEN_RE = re.compile(r"<(CustomFieldsInput|CustomFieldsView)\b")
#: `CR-161-BRC10` W3 — a TABLE column per field (the premises and assets lists,
#: the Premise page's Units tab) is drawn by the hook, not a tag; it is paired
#: the same way and counted the same way.
COLUMNS_RE = re.compile(
    r'useCustomFieldColumns(?:<\w+>)?\(\{\s*entity:\s*"([a-z_]+)",\s*screen:\s*"([A-Z0-9_]+)"'
)
COLUMNS_OPEN_RE = re.compile(r"useCustomFieldColumns(?:<\w+>)?\(")
#: `CR-161-BRC10` W7 — the customer portal draws its questions with its OWN
#: kit (`portal/guest/ApplicationCustomFields.tsx`), because the staff
#: renderer reads an authenticated registry a stranger may not call. It is
#: paired the same way: an input tag per record type, entity and screen
#: written literally.
PORTAL_CALLER_RE = re.compile(
    r'<ApplicationCustomFields\s+entity="([a-z_]+)"\s+screen="([A-Z0-9_]+)"'
)
PORTAL_OPEN_RE = re.compile(r"<ApplicationCustomFields\b")


def _callers() -> tuple[set[tuple[str, str, str]], list[str]]:
    """(entity, slot key, mode) for every live caller, and every caller this
    parse could not read — reported, never skipped."""
    found: set[tuple[str, str, str]] = set()
    unparsed: list[str] = []
    for path in FRONTEND.rglob("*.tsx"):
        if ".test." in path.name or path.name == "CustomFields.tsx":
            continue
        text = path.read_text(encoding="utf-8")
        if "./ApplicationCustomFields" in text and path.name != "ApplicationCustomFields.tsx":
            portal_opens = len(PORTAL_OPEN_RE.findall(text))
            portal = PORTAL_CALLER_RE.findall(text)
            if portal_opens != len(portal):
                unparsed.append(
                    f"{path.relative_to(REPO)} ({portal_opens} portal blocks, {len(portal)} read)"
                )
            for entity, screen in portal:
                found.add((entity, screen, "input"))
        # `SettingsCustomFields.tsx` exports a MANAGEMENT view that is also
        # called `CustomFieldsView`; only the renderer's own import counts.
        if "@/components/CustomFields" not in text:
            continue
        opens = len(OPEN_RE.findall(text))
        parsed = CALLER_RE.findall(text)
        if opens != len(parsed):
            unparsed.append(f"{path.relative_to(REPO)} ({opens} opened, {len(parsed)} read)")
        for component, entity, screen in parsed:
            found.add((entity, screen, "input" if component == "CustomFieldsInput" else "view"))
        column_opens = len(COLUMNS_OPEN_RE.findall(text))
        columns = COLUMNS_RE.findall(text)
        if column_opens != len(columns):
            unparsed.append(
                f"{path.relative_to(REPO)} ({column_opens} column hooks, {len(columns)} read)"
            )
        for entity, screen in columns:
            found.add((entity, screen, "view"))
    return found, unparsed


def _field(actor, **over):
    payload = {"label": "Visit window", "entity": "accounts", "data_type": "text"}
    payload.update(over)
    return tenancy_services.create_custom_field(actor, payload)


# ── 1 · the one list and the screens that draw it (DEF-TEN-9153) ────────────
def test_def_ten_9153__every_rendered_slot_has_a_screen_and_every_screen_a_rendered_slot():
    callers, unparsed = _callers()
    assert unparsed == [], f"callers this pairing could not read: {unparsed}"
    assert callers, "no <CustomFields…> caller found at all — the scan is broken"
    # `CR-161-BRC10` W3 — list slots are paired too, through the column hook.
    rendered = {
        (slot.entity, slot.key, mode)
        for slot in cf_law.SLOTS
        if slot.rendered
        for mode in slot.modes
    }
    # A slot Settings offers that no component draws: the field shows nowhere.
    assert rendered - callers == set()
    # A component drawing a slot the list does not offer: Settings cannot place it.
    assert callers - rendered == set()


def test_def_ten_9153__w1_renders_exactly_the_two_account_screens():
    """The honest W1 state, pinned: New account (S18, input) and Account detail
    (S21, input and view). Every other declared slot waits for its wave."""
    rendered = sorted((s.entity, s.key) for s in cf_law.SLOTS if s.rendered and s.wave == "W1")
    assert rendered == [("accounts", "S18"), ("accounts", "S21")]
    waiting = {s.wave for s in cf_law.SLOTS if not s.rendered}
    # W3 is complete since 2.459.0 (metering lane 2.458.0, customers lane
    # 2.459.0). W4's last slot, New Connection Step 1's customer (owner)
    # block, is drawn since `CR-164-BRC10` wave 2
    # (`tests/test_cr164_owner_custom_fields.py`), and the request screens
    # (Staff New Request, Request detail) since W6
    # (`tests/test_cr161_w6_request_custom_fields.py`), and the portal
    # new-service form since W7 (`tests/test_cr161_w7_portal_custom_fields.py`):
    # nothing waits.
    assert waiting == set()


def test_cr161_w3b__every_metering_and_assets_screen_is_rendered():
    """`CR-161-BRC10` W3 (lane CF-W3b) — premises, units, service points and
    assets: every W3 row of the PO's Part 2 is drawn by a screen today."""
    mine = {
        (s.entity, s.key, s.rendered)
        for s in cf_law.SLOTS
        if s.entity in ("premises", "units", "service_points", "assets") and s.wave == "W3"
    }
    assert mine == {
        ("premises", "NEW_CONNECTION_PREMISE", True),
        ("premises", "S16", True),
        ("premises", "PREMISE_EDIT", True),
        ("premises", "PREMISE_PAGE", True),
        ("premises", "S14", True),
        ("units", "S16", True),
        ("units", "UNIT_ADD", True),
        ("units", "UNIT_EDIT", True),
        ("units", "PREMISE_UNITS", True),
        ("service_points", "S16", True),
        ("service_points", "UNIT_ADD", True),
        ("service_points", "PREMISE_UNITS", True),
        ("assets", "S51", True),
        ("assets", "ASSET_EDIT", True),
        ("assets", "S50", True),
        ("assets", "S49", True),
    }


def test_def_ten_9154__every_rendered_slot_and_route_has_a_name_in_the_catalogue():
    catalogue = json.loads(EN.read_text(encoding="utf-8"))
    for slot in cf_law.SLOTS:
        assert slot.route in cf_law.ROUTES
        assert set(slot.modes) <= {"input", "view"}
        if slot.rendered:
            assert f"settings.customFields.screen.{slot.screen}" in catalogue, slot
    for route in cf_law.ROUTES:
        assert f"settings.customFields.route.{route}" in catalogue


def test_def_ten_9153__the_import_list_agrees_with_the_importer():
    """`IMPORT_FED_ENTITIES` is checked, not imported (tenancy may not import
    metering): it must be exactly the targets whose columns carry custom fields."""
    from apps.metering import import_runs, read_import

    derived = {
        target
        for target, columns in import_runs.DECLARED_COLUMNS_BY_TARGET.items()
        if "custom_data" in columns
    }
    # `CR-161-BRC10` W3 — the asset sheets DECLARE theirs and add the `assets`
    # fields; the map names the record type of every target carrying them.
    assert derived <= set(import_runs.CUSTOM_FIELD_ENTITY_BY_TARGET)
    fed = set(import_runs.CUSTOM_FIELD_ENTITY_BY_TARGET.values())
    # CR-161-BRC10 W4 — the S28 reading upload is the second importer that
    # carries one column per field (`read_import.custom_field_mapping`).
    if hasattr(read_import, "custom_field_mapping"):
        fed.add("meter_reads")
    assert fed == set(cf_law.IMPORT_FED_ENTITIES)


def test_def_ten_9153__the_slot_list_is_served_and_says_what_is_offered(brazos, dana):
    with tenant_ctx(brazos):
        rows = {row["entity"]: row for row in cf_law.slot_catalogue()}
    assert set(rows) == set(cf_law.ENTITIES)
    assert rows["accounts"]["offered"] is True
    assert rows["premises"]["offered"] is True and rows["premises"]["import_columns"] is True
    # W3 (`DEF-CUS-9168`) drew the contact edit, so a NEW contact field is
    # offered now. The rule itself, for every record type whichever wave has
    # reached it: offered exactly when a rendered screen or an import collects it.
    assert rows["contacts"]["offered"] is True
    for entity, row in rows.items():
        collects = any(s["rendered"] and "input" in s["modes"] for s in row["slots"])
        assert row["offered"] is (collects or row["import_columns"]), entity
    assert [s["key"] for s in rows["premises"]["slots"]][:3] == [
        "PORTAL_NEW_SERVICE",
        "REQUEST_NEW",
        "NEW_CONNECTION_PREMISE",
    ]


def _portal_waiting(monkeypatch):
    """⚠ AMENDED `CR-161-BRC10` W7 — every declared screen draws its fields
    now, so there is no real waiting screen left to ask about. The RULE still
    matters for the next wave that declares one, so it is exercised on the
    portal slot put back to not-rendered for the length of the test."""
    import dataclasses

    monkeypatch.setattr(
        cf_law,
        "SLOTS",
        tuple(
            dataclasses.replace(s, rendered=False) if s.key == "PORTAL_NEW_SERVICE" else s
            for s in cf_law.SLOTS
        ),
    )


def test_def_ten_9153__a_new_placement_on_a_screen_that_draws_nothing_is_refused(
    brazos, dana, monkeypatch
):
    # ⚠ AMENDED `CR-161-BRC10` W3: S16 and S14 are drawn now, so the waiting
    # screens this asks about were the W6 ones (Staff New Request, Request
    # detail). ⚠ AMENDED W6: those are drawn now too, so the waiting screen is
    # the portal new-service form (W7). ⚠ AMENDED W7: that is drawn too —
    # `_portal_waiting` stands it back up as a waiting screen.
    _portal_waiting(monkeypatch)
    with tenant_ctx(brazos):
        roof = _field(dana, label="Roof Material", entity="premises", data_type="text")
        with pytest.raises(errors.ValidationError) as caught:
            tenancy_services.save_custom_field_placement(
                dana, roof["id"], {"PORTAL_NEW_SERVICE": "input"}
            )
    keys = {fe["message_key"] for fe in caught.value.field_errors}
    assert keys == {"settings.customFields.slot_not_rendered"}


def test_def_ten_9153__a_stored_choice_on_a_waiting_screen_is_kept_and_not_counted(
    brazos, dana, monkeypatch
):
    """Roof Material placed on S14 · S15 · S16 under R2 read *Screens = 3*. W3
    honoured the two this list still declares the day those screens landed:
    ⚠ AMENDED `CR-161-BRC10` W3 — S16 (Add Premises) and S14 (the premises list)
    are drawn now, so they COUNT (2) and the field is collected on a screen;
    S15 is not a premises slot and is dropped on the next save. A stored choice
    on a screen still waiting (the portal form, W7 — it was Staff New Request
    until W6 drew it) is kept and not counted. ⚠ AMENDED W7: the portal form is
    drawn now too, so `_portal_waiting` stands it back up as the waiting
    screen."""
    _portal_waiting(monkeypatch)
    with tenant_ctx(brazos):
        roof = _field(dana, label="Roof Material", entity="premises", data_type="text")
        from apps.tenancy import models as tenancy_models

        tenancy_models.CustomField.objects.filter(pk=roof["id"]).update(
            placement={"S16": "input", "S14": "view", "S15": "view", "PORTAL_NEW_SERVICE": "input"}
        )
        row = tenancy_selectors.custom_field_row(roof["id"])
        assert row["placement_count"] == 2
        assert row["input_route"] == "screen"
        saved = tenancy_services.save_custom_field_placement(
            dana, roof["id"], {"S16": "input", "S14": "view"}
        )
    assert saved["placement"] == {"S16": "input", "S14": "view", "PORTAL_NEW_SERVICE": "input"}


# ── 2 · R4: every shown field has an input route (DEF-TEN-9155) ─────────────
def test_def_ten_9155__a_shown_field_nobody_collects_is_refused(brazos, dana):
    """⚠ `customers`, not `accounts`, since 2026-10-03 (`DEF-MET-9239`): the
    accounts import now carries one column per Accounts field, so a view-only
    Accounts field is *Filled by import* — the next case's rule — and no longer
    the example of a field nobody collects. A customer field still is: no
    import writes a customer's answers."""
    with tenant_ctx(brazos):
        note = _field(dana, label="Access note", entity="customers")
        with pytest.raises(errors.ValidationError) as caught:
            tenancy_services.save_custom_field_placement(dana, note["id"], {"S21": "view"})
        # …and the same field collected on New account saves.
        ok = tenancy_services.save_custom_field_placement(
            dana, note["id"], {"S18": "input", "S21": "view"}
        )
    assert caught.value.message_key == "settings.customFields.no_input_route"
    assert ok["placement"] == {"S18": "input", "S21": "view"}
    assert ok["input_route"] == "screen"


def test_def_ten_9155__an_import_fed_type_may_be_view_only_and_says_so(
    brazos, dana, monkeypatch
):
    """The other way round. No premises screen renders in W1, so this stands in
    for W3 by rendering the Premise page: a view-only Premises field saves,
    because the premises import carries it as a column."""
    monkeypatch.setattr(
        cf_law,
        "SLOTS",
        tuple(
            dataclasses.replace(s, rendered=True)
            if (s.entity, s.key) == ("premises", "PREMISE_PAGE")
            else s
            for s in cf_law.SLOTS
        ),
    )
    with tenant_ctx(brazos):
        roof = _field(dana, label="Roof Material", entity="premises")
        saved = tenancy_services.save_custom_field_placement(
            dana, roof["id"], {"PREMISE_PAGE": "view"}
        )
    assert saved["placement"] == {"PREMISE_PAGE": "view"}
    assert saved["input_route"] == "import"


# ── 3 · required only where typed in (DEF-TEN-9157) ─────────────────────────
def test_def_ten_9157__a_required_field_placed_nowhere_does_not_block_new_account(
    brazos, dana, marcus
):
    """The reproduction, exactly: *Gate code* required and placed on no screen,
    *Visit window* optional on New account. Until 2026-10-02 the create answered
    422 `custom_data.gate_code required` for a box the wizard never drew."""
    with tenant_ctx(brazos):
        _field(dana, label="Gate code", is_required=True)
        window = _field(dana, label="Visit window")
        tenancy_services.save_custom_field_placement(dana, window["id"], {"S18": "input"})
        unit = _unit_with_plan(marcus, brazos)
        payload = _create_payload(unit["id"])
        payload["custom_data"] = {"visit_window": "Mornings"}
        created = customers_services.create_account(marcus, payload)
    assert created["custom_data"] == {"visit_window": "Mornings"}


def test_def_ten_9157__a_required_field_typed_on_new_account_still_blocks_it(brazos, dana, marcus):
    with tenant_ctx(brazos):
        gate = _field(dana, label="Gate code", is_required=True)
        tenancy_services.save_custom_field_placement(dana, gate["id"], {"S18": "input"})
        unit = _unit_with_plan(marcus, brazos)
        payload = _create_payload(unit["id"])
        payload["custom_data"] = {}
        with pytest.raises(errors.ValidationError) as caught:
            customers_services.create_account(marcus, payload)
    assert caught.value.field_errors[0]["field"] == "custom_data.gate_code"
    # The clerk reads the VALUE path's sentence, not Settings' own.
    assert caught.value.message_key == "customFields.invalid"


def test_def_ten_9157__a_door_must_name_its_screen():
    import inspect

    sig = inspect.signature(customer_seams.validate_custom_data)
    assert sig.parameters["screen"].default is inspect.Parameter.empty


# ── 4 · Account detail edits the fields placed there (DEF-CUS-9158) ─────────
def test_def_cus_9158__an_edit_on_account_detail_merges_and_clears(brazos, dana, marcus):
    with tenant_ctx(brazos):
        window = _field(dana, label="Visit window")
        tenancy_services.save_custom_field_placement(dana, window["id"], {"S18": "input"})
        note = _field(dana, label="Access note")
        tenancy_services.save_custom_field_placement(dana, note["id"], {"S21": "input"})
        unit = _unit_with_plan(marcus, brazos)
        payload = _create_payload(unit["id"])
        payload["custom_data"] = {"visit_window": "Mornings"}
        created = customers_services.create_account(marcus, payload)

        edited = customers_services.update_account(
            marcus, created["id"], {"custom_data": {"access_note": "Dog in yard"}}
        )
        # The answer typed on New account survives an edit on Account detail.
        assert edited["custom_data"] == {"visit_window": "Mornings", "access_note": "Dog in yard"}
        cleared = customers_services.update_account(
            marcus, created["id"], {"custom_data": {"access_note": None}}
        )
        stored = customers_models.Account.objects.get(pk=created["id"]).custom_data
    assert cleared["custom_data"] == {"visit_window": "Mornings"}
    assert stored == {"visit_window": "Mornings"}


def test_def_cus_9158__required_on_account_detail_counts_a_stored_answer(brazos, dana, marcus):
    with tenant_ctx(brazos):
        gate = _field(dana, label="Gate code", is_required=True)
        tenancy_services.save_custom_field_placement(
            dana, gate["id"], {"S18": "input", "S21": "input"}
        )
        note = _field(dana, label="Access note")
        tenancy_services.save_custom_field_placement(dana, note["id"], {"S21": "input"})
        unit = _unit_with_plan(marcus, brazos)
        payload = _create_payload(unit["id"])
        payload["custom_data"] = {"gate_code": "4471"}
        created = customers_services.create_account(marcus, payload)
        # The stored gate code answers the requirement; the edit names only the note.
        edited = customers_services.update_account(
            marcus, created["id"], {"custom_data": {"access_note": "Side gate"}}
        )
        assert edited["custom_data"] == {"gate_code": "4471", "access_note": "Side gate"}
        # Blanking it on the screen it is typed in on is refused.
        with pytest.raises(errors.ValidationError) as caught:
            customers_services.update_account(marcus, created["id"], {"custom_data": {"gate_code": ""}})
    assert caught.value.field_errors[0]["field"] == "custom_data.gate_code"


# ── 5 · the exclusions (R2 + R3) ─────────────────────────────────────────────
MONEY_SCREENS = {"S12", "S13", "S31"}
MONEY_WORDS = ("invoice", "bill_run", "payment", "journal", "ledger", "rate", "plan_", "chart")


@pytest.mark.parametrize("entity", cf_law.NEVER_ENTITIES)
def test_cr161_never__a_ruled_out_record_type_is_refused(brazos, dana, entity):
    assert entity not in cf_law.ENTITIES
    assert all(slot.entity != entity for slot in cf_law.SLOTS)
    with tenant_ctx(brazos), pytest.raises(errors.ValidationError) as caught:
        _field(dana, label="Anything", entity=entity)
    assert caught.value.field_errors[0]["message_key"] == "settings.customFields.entity_not_covered"


def test_cr161_never__the_list_holds_exactly_the_pos_seven():
    assert set(cf_law.NEVER_ENTITIES) == {
        "plans",
        "rate_schedules",
        "invoices",
        "invoice_lines",
        "journal_entries",
        "journal_lines",
        "chart_of_accounts",
    }


def test_cr161_never__no_slot_sits_on_a_money_screen():
    for slot in cf_law.SLOTS:
        assert slot.key not in MONEY_SCREENS, slot
        # `change_plan` is the service-agreement form (never priced, BR-TEN-048)
        # and is the one name allowed to mention a plan. The two PAYMENTS slots
        # are W5's, ruled in by the PO on 2026-10-02 (R3, *"Payments IN as
        # capture-at-entry only"*) — capture and view only, never allocation;
        # `tests/test_cr161_w5_payment_custom_fields.py` pins exactly those two.
        if slot.entity == "payments":
            assert (slot.key, slot.screen) in {
                ("S35", "record_payment"),
                ("S33", "payment_detail"),
            }, slot
            continue
        name = slot.screen if slot.screen != "change_plan" else ""
        assert not any(word in name for word in MONEY_WORDS), slot


# ── 6 · one utility only ─────────────────────────────────────────────────────
@pytest.mark.isolation
def test_cr161_isolation__another_utility_sees_no_definition_and_no_cached_registry(
    brazos, lonestar, dana
):
    with tenant_ctx(brazos):
        window = _field(dana, label="Visit window")
        tenancy_services.save_custom_field_placement(dana, window["id"], {"S18": "input"})
        brazos_key = tenancy_selectors.custom_field_cache_key("accounts", 1)
        assert tenancy_selectors.custom_field_registry("accounts", screen="S18", mode="input")
    with tenant_ctx(lonestar):
        assert tenancy_selectors.custom_field_registry("accounts", screen="S18", mode="input") == []
        assert tenancy_selectors.custom_field_rows() == []
        lonestar_key = tenancy_selectors.custom_field_cache_key("accounts", 1)
    # BR-TEN-053: the tenant is part of every cache key.
    assert brazos_key != lonestar_key
    assert str(brazos.id) in brazos_key and str(lonestar.id) in lonestar_key
