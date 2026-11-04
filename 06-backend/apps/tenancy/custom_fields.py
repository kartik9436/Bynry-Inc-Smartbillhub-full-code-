# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-015 (define a custom field) · US-TEN-016 (placement) ·
#           US-TEN-017 (lifecycle + the registry every screen reads) ·
#           US-TEN-014 (the card + management view this feeds) ·
#           US-SHL-015 (the value half: what a screen may submit)
#           Screens: S8 (definitions) · the slots are `SLOTS` below — AMENDED
#           2026-10-02 by CR-161-BRC10 W1 (BR-TEN-046 entity list + NEVER list,
#           BR-TEN-052 one served list / rendered only / input route /
#           required where typed in; DEF-TEN-9153..9157, DEF-CUS-9158)
# Rules:    BR-TEN-046 (tenant DATA, never DDL; RLS FORCE) · BR-TEN-047 (inside
#           the Reference-data framework) · BR-TEN-048 (never influences money) ·
#           BR-TEN-049 (`key` immutable after create) · BR-TEN-050 (deactivate
#           only — no delete at any layer) · BR-TEN-051 (cap 10 active per
#           entity per tenant) · BR-TEN-052 (placement is platform-bounded,
#           tenant-chosen) · BR-TEN-053 (the cached, tenant-keyed registry) ·
#           BR-SHL-036 (one control per data type) · BR-SHL-037 (the existing
#           error envelope, `custom_data.<key>`) · CLAUDE.md rule 1
# Tests:    06-backend/tests/test_us_ten_014_017_custom_fields.py ·
#           06-backend/tests/test_us_shl_015_016_custom_field_values.py ·
#           06-backend/tests/test_cr161_w1_custom_field_settings.py
# Impacts:  apps/tenancy/services.py (the four writes) · selectors.py (the two
#           reads) · api.py (the S8 + registry endpoints) · every module that
#           accepts `custom_data` on a write (US-SHL-015)
# ───────────────────────────────────────────────────────
"""The LAW of tenant-defined fields: what may be defined, where it may appear,
and what a screen may submit into it. No writes live here — `services.py` is
this module's sole writer (B8 LAW 0) and calls into these validators.

WHY A SEPARATE FILE AND NOT MORE OF services.py
------------------------------------------------
Three different callers need the same rules and only one of them is a write:
the S8 definition screens (services), the registry read every placed screen
performs (selectors), and the VALUE check every owning module runs before it
persists a `custom_data` blob (US-SHL-015). Putting the rules beside the write
would make the value check import the write path.

THE ONE CONSTRAINT THAT LETS THIS FEATURE EXIST AT ALL
-------------------------------------------------------
BR-TEN-048 (CONFIRMED, PO 2026-08-10 — *"we may not able to use it for
calculation"*). A custom field is captured, displayed, searched and exported and
it never reaches the rating engine, an invoice-line amount, tax determination, a
ledger posting or payment allocation. Nothing in this file returns a Decimal and
nothing here imports `core.money`. A `number` custom field is stored as the
STRING the operator typed, normalised only enough to prove it is a number — see
`_coerce_number`. That is deliberate: the moment this module hands back a
Decimal, a later caller can add it to something.

WHAT IS NOT DECIDED HERE, AND MUST NOT BE
------------------------------------------
* HOW a value PRINTS ON A BILL. That is BR-TEN-082 (PO 2026-08-12) and it lives
  in `apps/billing/custom_snapshot.py`, the single DB-17 allowlisted module.
  Two readings on that snapshot are recorded as UNRATIFIED and this lane
  deliberately settles NEITHER: (1) the format a `date` prints in — the bill
  stamps ISO `2026-03-04` to avoid an ambiguous `03/04/2026`, while a SCREEN
  renders the tenant's IS-8 regional format (**OQ-211**); (2) a `boolean` prints
  `Yes`/`No` in ENGLISH on a possibly-Spanish bill, while this lane's SCREEN
  renders the tenant's own catalogue, so the two disagree in Spanish
  (**OQ-212**). Both are ROUTED, and neither is chosen here.
* WHETHER A DEFINITION CARRIES A DEFAULT VALUE. OQ-075's closure grants it
  (*"the field may carry a DEFAULT VALUE"*) and migration 0007 deliberately did
  not mint the column, because a default is what a DOCUMENT renders for a
  deactivated field and document rendering is R3 (US-NOT-016). Unbuilt, stated.
* THE TEMPLATE-VARIABLE BINDING. US-NOT-016, a later release. See
  `template_reference_warning` below for why that makes OQ-075's warning list
  empty BY CONSTRUCTION today rather than by an unwired seam.
"""

import re
from dataclasses import dataclass
from typing import Any

from apps.tenancy import models
from core import errors

#: ══════════════════════════════════════════════════════════════════════════
#: BR-TEN-052 AS AMENDED 2026-10-02 (`CR-161-BRC10`) — THE ONE SHARED SLOT LIST
#: ══════════════════════════════════════════════════════════════════════════
#:
#: Every screen a custom field can appear on, declared ONCE, here. The server
#: validates a placement against it, `GET /settings/custom-fields/slots` serves
#: it to Settings, and Settings keeps NO copy (hard-won law 5 — one source, no
#: committed copy that can drift). Each row is one screen of the PO's Part 2 /
#: Roof Material tables, copied verbatim into the change request.
#:
#: ⚠ **`rendered` IS THE WHOLE POINT OF W1.** Until 2026-10-02 the allow-list
#: named nine A1 screens and Settings offered every one of them, while only two
#: (`accounts` on S18 and S21) had a screen that drew anything — so a Premises
#: field placed on S14 · S15 · S16 read *Screens = 3* and appeared nowhere. A
#: slot whose screen does not render it yet stays DECLARED — the later wave
#: needs it, and a tenant's stored choice on it is kept through every save —
#: but Settings does not offer it and the server refuses a NEW placement on it.
#: A wave flips `rendered=True` IN THE SAME COMMIT as the screen that renders
#: it; `tests/test_cr161_w1_custom_field_settings.py` reads every
#: `<CustomFields… entity=… screen=…>` in the front end and fails when either
#: half lands alone.
#:
#: `key` is what a placement map stores. It is the A1 id where the screen has
#: one (so every placement stored before this date still means what it meant)
#: and a plain code where it does not — the Premise page, Edit premise, the
#: staff New Request and the portal form have no A1 id. It is NEVER shown: the
#: screen's NAME is `settings.customFields.screen.<screen>` in the catalogues
#: (B14 rules 31–33).
#:
#: `route` is the PO's grouping — *Customer (portal) · Clerk input · Read-only
#: view* — and `presentation` picks the words for the choices: a `portal` slot
#: offers *Ask the customer / Don't ask*, a `list` slot *Show as column / Not
#: shown*, everything else *Input / View / Not shown* as its `modes` allow.
#: Stored values are still only `input` and `view`.
#:
#: The money screens are absent on purpose and that absence is load-bearing:
#: S31 (Run Bills), S12/S13 (charges/taxes), every invoice, payment-allocation
#: and ledger screen are not addressable at all, so BR-TEN-048 has a second,
#: structural line of defence behind the G6 gate.
ROUTE_PORTAL = "portal"
ROUTE_CLERK_INPUT = "clerk_input"
ROUTE_READ_ONLY = "read_only"
ROUTES = (ROUTE_PORTAL, ROUTE_CLERK_INPUT, ROUTE_READ_ONLY)


@dataclass(frozen=True)
class Slot:
    entity: str
    key: str
    screen: str
    route: str
    modes: tuple[str, ...]
    presentation: str  # "form" · "page" · "list" · "portal"
    rendered: bool
    wave: str


_IN = ("input",)
_VIEW = ("view",)
_BOTH = ("input", "view")
_CLERK = ROUTE_CLERK_INPUT
_READ = ROUTE_READ_ONLY

#: In the PO's own order per record type (Part 2; the Roof Material table for
#: Premises). `rendered=True` only where a screen draws it TODAY.
SLOTS: tuple[Slot, ...] = (
    # ── Accounts ── New Account wizard · New Connection Step 1 · Account detail.
    # ⚠ S18 is ONE slot for the two account-creation doors. The New Account
    # wizard posts what is typed; New Connection Step 1 renders the same fields
    # and, until W3 (`DEF-CUS-9159`), dropped them at commit — it now sends
    # them as the owner block's `custom_data`. The screen is named "New account".
    Slot("accounts", "S18", "new_account", _CLERK, _IN, "form", True, "W1"),
    Slot("accounts", "S21", "account_detail", _CLERK, _BOTH, "page", True, "W1"),
    # RENDERED W6 (`CR-161-BRC10`): Staff New Request step 1 (input) and the
    # request's Applicant tab (view). The approval copies the answers onto the
    # account the linked customer holds at the picked unit (`request_custom_fields`).
    Slot("accounts", "REQUEST_NEW", "staff_new_request", _CLERK, _IN, "form", True, "W6"),
    Slot("accounts", "REQUEST_DETAIL", "request_detail", _READ, _VIEW, "page", True, "W6"),
    # RENDERED W7 (`CR-161-BRC10`): the customer portal's new-service form,
    # step 3 (*About you*), only when the utility switched the field to *Ask
    # the customer*. The answers land on the request's own copy (W6) and travel
    # from there exactly as a clerk's do.
    Slot("accounts", "PORTAL_NEW_SERVICE", "portal_new_service", ROUTE_PORTAL, _IN, "portal", True, "W7"),
    # ── Contacts ── Add / edit contact (Account detail) · Account detail → Contacts
    # RENDERED W3 (`DEF-CUS-9168`): the contact edit (input) and the Customer
    # group (view) on Account detail.
    Slot("contacts", "S21", "account_contacts", _CLERK, _BOTH, "page", True, "W3"),
    # ── Addresses — MAILING only; a service address lives on the premise (hard rule 8)
    # RENDERED W3 (`DEF-CUS-9169`): New Account's mailing block (input) and
    # Account detail's mailing edit (input) and group (view).
    Slot("addresses", "S18", "new_account_mailing", _CLERK, _IN, "form", True, "W3"),
    Slot("addresses", "S21", "account_mailing", _CLERK, _BOTH, "page", True, "W3"),
    # ── Service agreements — never used in pricing (BR-TEN-048)
    # RENDERED W3 (`DEF-CUS-9170`): New Account's unit step, which lists the
    # unit's services (input, written on every agreement the account opens),
    # Change plan's confirm step (input, merged into every open agreement) and
    # Account detail's Services group (view, one block per agreement).
    Slot("service_agreements", "S18", "new_account_services", _CLERK, _IN, "form", True, "W3"),
    Slot("service_agreements", "S23", "change_plan", _CLERK, _IN, "form", True, "W3"),
    Slot("service_agreements", "S21", "account_services", _READ, _VIEW, "page", True, "W3"),
    # ── Premises — the Roof Material table, row for row. ⚠ `CR-161-BRC10` W3
    # (2026-10-02, `DEF-MET-9226` and siblings) flipped every W3 row below to
    # rendered IN THE SAME COMMIT as the screen that draws it — New Connection
    # Step 2, Add Premises Step 2 (+ its Step 3 recap), Edit premise, the
    # Premise page and the premises list column; the units' and service points'
    # Add Premises / Add units / Edit unit / Units-tab rows; and the four asset
    # screens. Staff New Request and Request detail are rendered since W6
    # (`CR-161-BRC10`, step 2 of New Request and the Applicant tab), and the
    # portal row since W7 — step 2 (*When*) of the portal form, where the
    # property is.
    Slot("premises", "PORTAL_NEW_SERVICE", "portal_new_service", ROUTE_PORTAL, _IN, "portal", True, "W7"),
    Slot("premises", "REQUEST_NEW", "staff_new_request", _CLERK, _IN, "form", True, "W6"),
    Slot("premises", "NEW_CONNECTION_PREMISE", "new_connection_premise", _CLERK, _BOTH, "form", True, "W3"),
    Slot("premises", "S16", "add_premises", _CLERK, _IN, "form", True, "W3"),
    Slot("premises", "PREMISE_EDIT", "edit_premise", _CLERK, _IN, "form", True, "W3"),
    Slot("premises", "PREMISE_PAGE", "premise_page", _READ, _VIEW, "page", True, "W3"),
    Slot("premises", "S14", "premises_list", _READ, _VIEW, "list", True, "W3"),
    Slot("premises", "REQUEST_DETAIL", "request_detail", _READ, _VIEW, "page", True, "W6"),
    # ── Units — Add Premises (first unit) · Add unit · Edit unit · Premise page → Units
    Slot("units", "S16", "add_premises_first_unit", _CLERK, _IN, "form", True, "W3"),
    Slot("units", "UNIT_ADD", "add_unit", _CLERK, _IN, "form", True, "W3"),
    Slot("units", "UNIT_EDIT", "edit_unit", _CLERK, _IN, "form", True, "W3"),
    Slot("units", "PREMISE_UNITS", "premise_units_tab", _READ, _VIEW, "page", True, "W3"),
    # ── Service points — Add Premises / Add unit (services) · Premise page → Units
    Slot("service_points", "S16", "add_premises_services", _CLERK, _IN, "form", True, "W3"),
    Slot("service_points", "UNIT_ADD", "add_unit_services", _CLERK, _IN, "form", True, "W3"),
    Slot("service_points", "PREMISE_UNITS", "premise_units_tab", _READ, _VIEW, "page", True, "W3"),
    # ── Assets — Add asset · Edit asset · Asset detail · Assets list
    Slot("assets", "S51", "add_asset", _CLERK, _IN, "form", True, "W3"),
    Slot("assets", "ASSET_EDIT", "edit_asset", _CLERK, _IN, "form", True, "W3"),
    Slot("assets", "S50", "asset_detail", _READ, _VIEW, "page", True, "W3"),
    Slot("assets", "S49", "assets_list", _READ, _VIEW, "list", True, "W3"),
    # ── Payments — CR-161-BRC10 W5. Part 2 row 14, verbatim: *"Record payment
    # (at entry only) · Payment detail · Can't be corrected afterwards; never
    # used to apply the payment to bills"*. Typed in ONCE on the Record payment
    # page (S35) and shown read-only on Payment detail (S33); there is no edit
    # slot because there is no edit — hard rule 4's trigger refuses an UPDATE
    # of the column (`payments/0046`). Neither is a money SCREEN in the sense
    # the NEVER list means: S35 is where money is taken, and the answers are
    # still never read by allocation (BR-TEN-048, G6 / DB-17).
    Slot("payments", "S35", "record_payment", _CLERK, _IN, "form", True, "W5"),
    Slot("payments", "S33", "payment_detail", _READ, _VIEW, "page", True, "W5"),
    # ── CR-161-BRC10 W4 — five record types, each in the PO's Part 2 order. ──
    # Customer — *"New Account wizard · New Connection Step 1 (owner) ·
    # Customer edit · Customer page · Account detail header"*. ⚠ THERE IS NO
    # CUSTOMER PAGE in the product (a customer is reached through an account;
    # `CustomersListPage` opens accounts), so no slot is declared for one — a
    # declared slot for a screen that does not exist would be a promise. The
    # Account detail header is the nearest page and is the view. New
    # Connection Step 1's owner block is RENDERED since `CR-164-BRC10` wave 2
    # (lane NC-C, 2026-10-02): its answers travel Step 1 → the build commit
    # (`metering.connections`, the owner block's `customer_custom_data`) → the
    # master-account door (`customers.create_master_account`, validated as
    # THIS slot so a required field binds where it is typed) → the owner's new
    # customer row. Until then it was declared and switched off, because a box
    # drawn without that plumbing would have been hard-won law 2.
    Slot("customers", "S18", "new_account_customer", _CLERK, _IN, "form", True, "W4"),
    Slot("customers", "NEW_CONNECTION_OWNER", "new_connection_owner", _CLERK, _IN, "form", True, "W4"),
    Slot("customers", "CUSTOMER_EDIT", "customer_edit", _CLERK, _IN, "form", True, "W4"),
    Slot("customers", "S21", "account_header_customer", _READ, _VIEW, "page", True, "W4"),
    # `CR-161-BRC10` W6 — *"account / customer / premises fields may also be
    # placed on Staff New Request"*. Step 1 draws the input; the request's
    # Applicant tab the view; approval copies onto the linked customer.
    Slot("customers", "REQUEST_NEW", "staff_new_request", _CLERK, _IN, "form", True, "W6"),
    Slot("customers", "REQUEST_DETAIL", "request_detail", _READ, _VIEW, "page", True, "W6"),
    # `CR-161-BRC10` W7 — *"account / customer / premises fields may also be
    # placed on … the Portal new-service form"*. Declared and rendered in the
    # same commit: step 3 (*About you*) of the portal form draws it.
    Slot("customers", "PORTAL_NEW_SERVICE", "portal_new_service", ROUTE_PORTAL, _IN, "portal", True, "W7"),
    # Work orders — *"New work order · Edit work order · Work order detail"*.
    # Plain codes: the three are Work-module screens (`WRK-12`, `Work-021`,
    # `Work-008`) with no A1 id, and a dash is not a placement key.
    Slot("work_orders", "WORK_NEW", "new_work_order", _CLERK, _IN, "form", True, "W4"),
    Slot("work_orders", "WORK_EDIT", "edit_work_order", _CLERK, _IN, "form", True, "W4"),
    Slot("work_orders", "WORK_DETAIL", "work_order_detail", _READ, _VIEW, "page", True, "W4"),
    # Readings — *"Manual reading entry · Reading import (column mapping) ·
    # Reading detail / reading history · Never used in the bill calculation"*.
    # The import is not a slot: it is a door that is not a screen, so it is
    # `IMPORT_FED_ENTITIES` below and nothing is REQUIRED of it (W1's rule).
    Slot("meter_reads", "READ_ENTRY", "manual_reading", _CLERK, _IN, "form", True, "W4"),
    Slot("meter_reads", "S29", "reading_detail", _READ, _VIEW, "page", True, "W4"),
    # Routes — *"Add / edit route · Route page"* (SET-06.1 wizard · SET-06D).
    Slot("routes", "ROUTE_FORM", "route_form", _CLERK, _IN, "form", True, "W4"),
    Slot("routes", "ROUTE_PAGE", "route_page", _READ, _VIEW, "page", True, "W4"),
    # Areas — *"Add / edit area · Area page"*. ⚠ THERE IS NO AREA PAGE: an area
    # is a row on Settings → Reference data → Areas. The nearest existing page
    # is that list, so the view is a COLUMN there (`list`, *Show as column*).
    Slot("areas", "AREA_FORM", "area_form", _CLERK, _IN, "form", True, "W4"),
    Slot("areas", "AREA_LIST", "areas_list", _READ, _VIEW, "list", True, "W4"),
)

#: The record types whose IMPORT carries one column per custom field TODAY —
#: `apps/metering/import_runs.CUSTOM_FIELD_ENTITY_BY_TARGET`'s values: premises
#: and units (derived columns) and, since `CR-161-BRC10` W3 (`DEF-AST-9171`),
#: assets (the three asset sheets add one column per field) — and, since W4,
#: the S28 reading upload (`apps/metering/read_import.custom_field_mapping`)
#: for `meter_reads` (*"Reading import (column mapping)"*). A test pins the
#: list to both importers (tenancy may not import metering, so the agreement is
#: checked rather than imported). R4's input-route rule lets a view-only field
#: stand on these: the import fills it. `accounts` joined on 2026-10-03
#: (`DEF-MET-9239`): the accounts sheet now carries one column per field.
IMPORT_FED_ENTITIES: tuple[str, ...] = ("premises", "units", "assets", "meter_reads", "accounts")

#: R2 + R3 (PO 2026-10-02): *"dont add on these - Plans / rate schedules …
#: Books (ledger / journal entries) … Invoices"* and *"dont inlcude charts of
#: acocunts"*. NEVER a custom-field entity, never a slot — refused by name.
NEVER_ENTITIES: tuple[str, ...] = (
    "plans",
    "rate_schedules",
    "invoices",
    "invoice_lines",
    "journal_entries",
    "journal_lines",
    "chart_of_accounts",
)


def declared_slots(entity: str) -> tuple[Slot, ...]:
    """Every slot declared for one record type, rendered or not."""
    return tuple(slot for slot in SLOTS if slot.entity == entity)


def rendered_slots(entity: str) -> tuple[Slot, ...]:
    """The slots Settings may OFFER — a screen draws each one today."""
    return tuple(slot for slot in declared_slots(entity) if slot.rendered)


def slot_for(entity: str, key: Any) -> Slot | None:
    wanted = str(key).strip().upper()
    for slot in declared_slots(entity):
        if slot.key == wanted:
            return slot
    return None


#: ══════════════════════════════════════════════════════════════════════════
#: `CR-161-BRC10` W7 — THE CUSTOMER PORTAL'S NEW-SERVICE FORM
#: ══════════════════════════════════════════════════════════════════════════
#:
#: PO, Part 2 row 16: *"Portal new-service form (applicant) · Staff Request
#: detail · Customer → clerk · Off by default per field; a utility turns each
#: one on"*, and the Rules table: *"Shown on the portal only when switched on —
#: 'Ask the customer' is off by default"*. A field is ON the portal exactly when
#: it is ACTIVE and its stored placement is `input` on this slot; nothing else
#: puts it there, and a new field's placement is empty, so the default is off.
PORTAL_SCREEN = "PORTAL_NEW_SERVICE"
#: The record types the portal form may ask about, in the order the request's
#: own copy keeps them (`customers.request_custom_fields.INTAKE_ENTITIES`).
PORTAL_ENTITIES: tuple[str, ...] = ("customers", "accounts", "premises")
#: ⚠ **WHAT A STRANGER IS TOLD ABOUT A FIELD, AND NOTHING ELSE.** The portal is
#: public: the form is served to anybody holding a draft link. So the field's
#: row id, its placement map (which names every INTERNAL screen it sits on),
#: its display order and its print flag never leave the server — only what
#: drawing the box needs. `tests/test_cr161_w7_portal_custom_fields.py` pins it.
PORTAL_PUBLIC_KEYS: tuple[str, ...] = (
    "key",
    "label",
    "help_text",
    "data_type",
    "options",
    "is_required",
)


def asked_on_portal(definition: dict[str, Any]) -> bool:
    """Is this definition switched to *Ask the customer*?"""
    return PORTAL_SCREEN in screens_for(definition.get("placement"), "input")


def portal_definitions(definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The registry rows the portal form asks — FULL rows, for the validator
    (it reads `placement` to know what is required here). Never serve these;
    serve `portal_public_view`."""
    return [d for d in definitions if asked_on_portal(d)]


def portal_public_view(definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What the portal form is told: `PORTAL_PUBLIC_KEYS` of each ACTIVE field
    the utility switched to *Ask the customer*, in the registry's own order."""
    return [
        {
            key: (list(d.get(key) or []) if key == "options" else d.get(key))
            for key in PORTAL_PUBLIC_KEYS
        }
        for d in portal_definitions(definitions)
    ]


def slot_dict(slot: Slot) -> dict[str, Any]:
    return {
        "key": slot.key,
        "screen": slot.screen,
        "route": slot.route,
        "modes": list(slot.modes),
        "presentation": slot.presentation,
        "rendered": slot.rendered,
        "wave": slot.wave,
    }


def has_input_route(entity: str, placement: Any) -> bool:
    """R4: does any RENDERED screen collect this field? Portal *Ask the
    customer* and a staff New Request placement are both stored `input`, so
    they count exactly as a clerk form does — the day their waves render them."""
    stored = placement if isinstance(placement, dict) else {}
    return any(stored.get(slot.key) == "input" for slot in rendered_slots(entity))


def input_route(entity: str, placement: Any) -> str:
    """`screen` · `import` · `none` — what collects this field today."""
    if has_input_route(entity, placement):
        return "screen"
    if entity in IMPORT_FED_ENTITIES:
        return "import"
    return "none"


def rendered_placement_count(entity: str, placement: Any) -> int:
    """How many screens actually SHOW the field. The R2 count read the stored
    map's length, which counted screens that draw nothing."""
    stored = placement if isinstance(placement, dict) else {}
    return sum(1 for slot in rendered_slots(entity) if stored.get(slot.key) in ("input", "view"))


def slot_catalogue() -> list[dict[str, Any]]:
    """`GET /settings/custom-fields/slots` — the whole list, per record type.

    `offered` says whether Settings' *Applies to* offers the record type for a
    NEW field: only when something collects it today — a rendered input slot or
    an import column. Fields already defined on another type stay listed and
    editable; nothing is hidden from the table.
    """
    out: list[dict[str, Any]] = []
    for entity in ENTITIES:
        slots = declared_slots(entity)
        rendered_input = any(s.rendered and "input" in s.modes for s in slots)
        out.append(
            {
                "entity": entity,
                "import_columns": entity in IMPORT_FED_ENTITIES,
                "offered": rendered_input or entity in IMPORT_FED_ENTITIES,
                "slots": [slot_dict(s) for s in slots],
            }
        )
    return out


#: BR-TEN-052: `input` implies `view` on that screen, so a screen set to input
#: renders the control and a screen set to view renders the stored value.
PLACEMENT_MODES = ("input", "view", "not_shown")

#: BR-TEN-051 (CONFIRMED, PO 2026-08-10 — *"10 are okay"*). Per entity, per
#: tenant, ACTIVE only: a deactivated definition frees headroom (US-TEN-017
#: TC-4) because it is retired vocabulary, not a live field on a form.
ACTIVE_CAP_PER_ENTITY = 10

#: US-TEN-014/015 §5. The key is the identity a stamped snapshot and a pinned
#: template both reference forever (BR-TEN-049), which is why its shape is
#: narrow enough to survive a CSV header, a jsonb key and a template variable.
KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
LABEL_MAX = 60
HELP_TEXT_MAX = 200
OPTION_MAX = 60
OPTIONS_MIN = 2
OPTIONS_MAX = 50

#: The two data types whose value space is the tenant's own option list.
SELECT_TYPES = ("select", "multi_select")

ENTITIES = models.CUSTOM_FIELD_ENTITIES
DATA_TYPES = models.CUSTOM_FIELD_DATA_TYPES


def _field_error(field: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": code, "message_key": message_key, "params": params}


def _refuse(field_errors: list[dict[str, Any]]) -> None:
    """BR-SHL-037: one envelope, the existing one. No second error path is
    invented for custom fields — FormModal highlights `custom_data.<key>`
    exactly as it highlights a platform field."""
    if field_errors:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="settings.customFields.invalid",
            field_errors=field_errors,
        )


# ── key derivation (US-TEN-015 TC-1) ────────────────────────────────────────
def derive_key(label: str) -> str:
    """ "Feeder Number" → `feeder_number`. Derived ONCE, at create, then locked.

    Deliberately ASCII-only and deliberately lossy: the key travels into a CSV
    header, a jsonb key and (in R3) a template variable, so a label a tenant
    writes in Spanish or Hindi must still produce a key those three can carry.
    A label that reduces to nothing produces an EMPTY key, and the caller
    refuses it by name rather than inventing `field_1` — a key nobody can read
    is a key nobody can maintain, and BR-TEN-049 makes it permanent.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", (label or "").strip().lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    if slug and not slug[0].isalpha():
        slug = f"f_{slug}"
    return slug[:40].rstrip("_")


# ── definition validation (US-TEN-015) ──────────────────────────────────────
def validate_definition(payload: Any, *, existing: models.CustomField | None = None) -> dict:
    """Validate a create (existing=None) or an edit, and return the changes.

    BR-TEN-049 is enforced HERE and not by the column: `key` and `entity` are
    absent from the editable set, and naming either on an edit is refused 422
    rather than ignored. Silently dropping the field would let a client believe
    a rename happened — the exact failure the rule exists to prevent.
    """
    if not isinstance(payload, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="settings.payload_not_object")

    creating = existing is None
    allowed = {"label", "help_text", "data_type", "options", "is_required", "display_order"}
    if creating:
        allowed |= {"entity", "key"}
    else:
        allowed |= {"is_document_safe"}

    fe: list[dict[str, Any]] = []
    for field in sorted(set(payload) - allowed):
        if field in ("key", "entity") and not creating:
            # BR-TEN-049 / US-TEN-015 TC-4 — named, never silently dropped.
            fe.append(
                _field_error(
                    field, errors.VAL_FORMAT, "settings.customFields.immutable_after_create"
                )
            )
        else:
            fe.append(_field_error(field, errors.VAL_FORMAT, "settings.unknown_field"))
    _refuse(fe)

    out: dict[str, Any] = {}

    # ── entity (create only) ────────────────────────────────────────────────
    if creating:
        entity = str(payload.get("entity") or "").strip()
        if not entity:
            fe.append(
                _field_error("entity", errors.VAL_REQUIRED, "settings.customFields.required_field")
            )
        elif entity not in ENTITIES:
            # US-TEN-015 TC-7: `invoices` is not one of the eight. The rating
            # and append-only tables are not addressable and never become so.
            fe.append(
                _field_error(
                    "entity",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "settings.customFields.entity_not_covered",
                    entity=entity,
                )
            )
        else:
            out["entity"] = entity

    # ── label (always) ──────────────────────────────────────────────────────
    if creating or "label" in payload:
        label = str(payload.get("label") or "").strip()
        if not label:
            fe.append(
                _field_error("label", errors.VAL_REQUIRED, "settings.customFields.required_field")
            )
        elif len(label) > LABEL_MAX:
            fe.append(
                _field_error(
                    "label", errors.VAL_RANGE, "settings.customFields.too_long", max=LABEL_MAX
                )
            )
        else:
            out["label"] = label

    # ── key (create only; derived from the label unless given) ──────────────
    if creating:
        raw_key = str(payload.get("key") or "").strip().lower()
        key = raw_key or derive_key(str(payload.get("label") or ""))
        if not key:
            fe.append(
                _field_error("key", errors.VAL_REQUIRED, "settings.customFields.key_underivable")
            )
        elif not KEY_RE.match(key):
            fe.append(_field_error("key", errors.VAL_FORMAT, "settings.customFields.key_shape"))
        else:
            out["key"] = key

    # ── data type ───────────────────────────────────────────────────────────
    data_type = existing.data_type if existing is not None else None
    if creating or "data_type" in payload:
        candidate = str(payload.get("data_type") or "").strip()
        if not candidate:
            fe.append(
                _field_error(
                    "data_type", errors.VAL_REQUIRED, "settings.customFields.required_field"
                )
            )
        elif candidate not in DATA_TYPES:
            fe.append(
                _field_error(
                    "data_type",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "settings.customFields.data_type_unknown",
                    data_type=candidate,
                )
            )
        else:
            out["data_type"] = candidate
            data_type = candidate

    # ── options (required ≥2 for the select types, ignored otherwise) ───────
    if data_type in SELECT_TYPES:
        options = payload.get("options", existing.options if existing is not None else None)
        cleaned = _clean_options(options, fe)
        if cleaned is not None:
            out["options"] = cleaned
    elif "options" in payload:
        # US-TEN-015 §5: "ignored otherwise". Stored as NULL so a later type
        # change cannot resurrect a stale option list.
        out["options"] = None

    # ── the plain booleans and the order ────────────────────────────────────
    if "is_required" in payload:
        out["is_required"] = bool(payload["is_required"])
    if "is_document_safe" in payload:
        # OQ-076 (PO 2026-08-10, *"Dont put SSN on invoices"*), mechanism
        # INVERTED: a field is not stamped onto a document unless the tenant
        # explicitly marks it safe. Editable only, never settable at create —
        # the unsafe option is the one you have to type (hard-won law 3).
        out["is_document_safe"] = bool(payload["is_document_safe"])
    if "display_order" in payload:
        try:
            order = int(payload["display_order"])
        except (TypeError, ValueError):
            fe.append(
                _field_error(
                    "display_order", errors.VAL_FORMAT, "settings.customFields.order_not_a_number"
                )
            )
        else:
            if order < 0 or order > 999:
                fe.append(
                    _field_error(
                        "display_order",
                        errors.VAL_RANGE,
                        "settings.customFields.order_out_of_range",
                    )
                )
            else:
                out["display_order"] = order

    # ── help text ───────────────────────────────────────────────────────────
    if "help_text" in payload:
        help_text = str(payload.get("help_text") or "").strip()
        if len(help_text) > HELP_TEXT_MAX:
            fe.append(
                _field_error(
                    "help_text",
                    errors.VAL_RANGE,
                    "settings.customFields.too_long",
                    max=HELP_TEXT_MAX,
                )
            )
        else:
            out["help_text"] = help_text or None

    _refuse(fe)
    return out


def _clean_options(options: Any, fe: list[dict[str, Any]]) -> list[str] | None:
    if not isinstance(options, (list, tuple)):
        fe.append(
            _field_error("options", errors.VAL_REQUIRED, "settings.customFields.options_required")
        )
        return None
    cleaned: list[str] = []
    for raw in options:
        value = str(raw or "").strip()
        if not value:
            continue
        if len(value) > OPTION_MAX:
            fe.append(
                _field_error(
                    "options", errors.VAL_RANGE, "settings.customFields.too_long", max=OPTION_MAX
                )
            )
            return None
        if value in cleaned:
            fe.append(
                _field_error(
                    "options",
                    errors.VAL_FORMAT,
                    "settings.customFields.option_duplicate",
                    option=value,
                )
            )
            return None
        cleaned.append(value)
    if len(cleaned) < OPTIONS_MIN:
        # US-TEN-015 §5: "required and ≥2 when type is select/multi_select".
        fe.append(
            _field_error(
                "options",
                errors.VAL_RANGE,
                "settings.customFields.options_min",
                min=OPTIONS_MIN,
            )
        )
        return None
    if len(cleaned) > OPTIONS_MAX:
        fe.append(
            _field_error(
                "options", errors.VAL_RANGE, "settings.customFields.too_long", max=OPTIONS_MAX
            )
        )
        return None
    # US-TEN-015 TC-2: "three options in the given order; order is preserved on
    # reload". The list is stored as given, never sorted.
    return cleaned


# ── placement validation (US-TEN-016) ───────────────────────────────────────
def eligible_slots(entity: str) -> dict[str, tuple[str, ...]]:
    """The RENDERED slots for one entity, in the R2 `{mode: keys}` shape —
    computed from `SLOTS` on every call, so a wave that flips a slot (or a test
    standing in for that wave) moves this too."""
    return {
        mode: tuple(s.key for s in rendered_slots(entity) if mode in s.modes)
        for mode in ("input", "view")
    }


def validate_placement(
    entity: str, placement: Any, *, existing: Any = None
) -> dict[str, str]:
    """`{"S18": "input", "S21": "view"}` — checked against the ONE slot list.

    Four refusals, all 422 and all named:

    * a screen that is not a slot for this record type at all — S31 Run Bills
      (the money screens are not addressable), or S50 for an `accounts` field
      (US-TEN-016 TC-4/TC-5);
    * a mode the slot does not offer (View on New account, Input on a list);
    * **a NEW placement on a slot no screen renders yet** (`CR-161-BRC10` W1) —
      the screen would draw nothing, which is exactly the lie W1 removes;
    * **R4: a field that is SHOWN somewhere and COLLECTED nowhere** — *"No
      screen collects this field"* — unless the record type's import carries it
      as a column (`IMPORT_FED_ENTITIES`), in which case it saves and the
      definition reads `input_route: "import"`.

    `not_shown` is stored by OMISSION, so the stored map only ever names live
    placements — TC-3's "the field disappears and the stored VALUES are
    untouched".

    ⚠ **A STORED CHOICE ON A NOT-YET-RENDERED SLOT IS CARRIED, NOT DROPPED.**
    `existing` is the map already stored. An entry on a slot that is declared
    and not rendered was chosen when Settings offered that screen; Settings no
    longer shows it, so the client cannot send it back, and dropping it on the
    next save would erase a choice the tenant made and W3 will honour the day
    its screen lands. A stored key the list no longer declares at all is
    dropped — no screen will ever read it.
    """
    if not isinstance(placement, dict):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="settings.customFields.placement_not_object"
        )
    stored = existing if isinstance(existing, dict) else {}
    fe: list[dict[str, Any]] = []
    out: dict[str, str] = {}
    mentioned: set[str] = set()
    for screen, raw_mode in placement.items():
        slot = slot_for(entity, screen)
        screen_id = slot.key if slot is not None else str(screen).strip().upper()
        mentioned.add(screen_id)
        mode = str(raw_mode or "").strip()
        if mode not in PLACEMENT_MODES:
            fe.append(
                _field_error(
                    f"placement.{screen_id}",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "settings.customFields.placement_mode_unknown",
                    mode=mode,
                )
            )
            continue
        if mode == "not_shown":
            continue
        if slot is None or mode not in slot.modes:
            fe.append(
                _field_error(
                    f"placement.{screen_id}",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "settings.customFields.slot_not_eligible",
                    screen=screen_id,
                    entity=entity,
                    mode=mode,
                )
            )
            continue
        if not slot.rendered and stored.get(slot.key) != mode:
            fe.append(
                _field_error(
                    f"placement.{screen_id}",
                    errors.VAL_UNKNOWN_LOOKUP,
                    "settings.customFields.slot_not_rendered",
                )
            )
            continue
        out[screen_id] = mode
    _refuse(fe)
    for key, mode in stored.items():
        slot = slot_for(entity, key)
        if slot is None or slot.rendered or slot.key in mentioned:
            continue
        if mode in slot.modes:
            out[slot.key] = mode
    shown = any(out.get(slot.key) in ("input", "view") for slot in rendered_slots(entity))
    if shown and not has_input_route(entity, out) and entity not in IMPORT_FED_ENTITIES:
        # R4 / gap 1 (PO 2026-10-02). A field a clerk can SEE and nobody can
        # FILL is a permanently empty box; the one exception is a record type
        # whose import carries the field as a column, because the import fills it.
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="settings.customFields.no_input_route"
        )
    return out


def screens_for(placement: Any, mode: str) -> tuple[str, ...]:
    """Which screens this definition renders on in `mode`.

    BR-TEN-052: `input` IMPLIES `view` on that screen, so a view query returns
    the input placements too. Without this line a field placed Input on S21
    would capture on the edit modal and vanish from the page behind it.
    """
    stored = placement if isinstance(placement, dict) else {}
    if mode == "view":
        return tuple(sorted(k for k, v in stored.items() if v in ("view", "input")))
    return tuple(sorted(k for k, v in stored.items() if v == mode))


# ── the value half (US-SHL-015) ─────────────────────────────────────────────
def _refuse_values(field_errors: list[dict[str, Any]]) -> None:
    """The VALUE path's own envelope (`DEF-TEN-9157`). It used to share
    `_refuse` with the definition path, so a clerk whose New Account was
    refused read Settings' sentence — *"Some of this field's settings need
    fixing"* — about a field they had never seen."""
    if field_errors:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customFields.invalid",
            field_errors=field_errors,
        )


def validate_custom_data(
    definitions: list[dict[str, Any]],
    submitted: Any,
    *,
    require_input: bool = True,
    screen: str | None = None,
    existing: Any = None,
) -> dict[str, Any]:
    """Type-check a `custom_data` blob against the ACTIVE registry for its entity.

    `definitions` is the registry list this module publishes — the caller passes
    it rather than this function reading it, so a module that already holds the
    registry does not fetch it twice inside one write.

    Three refusals, each a US-SHL-015 test case:
      TC-5  an unknown key is REJECTED, never persisted. A stale client cannot
            write shadow data that no screen will ever show and no export will
            ever carry.
      TC-6  a `select` value outside the defined options is refused by name.
      TC-3  a REQUIRED field left blank blocks save — **only on the screen it is
            typed in on** (below).

    ⚠ **REQUIRED BINDS WHERE THE FIELD IS TYPED IN, AND NOWHERE ELSE
    (`DEF-TEN-9157`; PO Rules table 2026-10-02: *"A required field never blocks
    a screen that doesn't show it"*).** `screen` is the slot the door's form
    is: a required field blocks the save only when its placement is `input` on
    that screen. Until 2026-10-02 `require_input=True` meant *"this is an input
    path"* and bound EVERY required definition, so an account field placed on
    no screen at all refused New Account with `custom_data.gate_code` — a box
    the wizard never drew. A door that is not a screen (an import, a move-in
    that renders no custom fields) passes `screen=None`, and nothing is required
    of it. `require_input=False` still switches the check off entirely.

    `existing` is the row's stored blob, for an EDIT (Account detail). Given,
    the return value is the MERGED blob — stored answers kept, submitted ones
    applied, a submitted blank clearing its key — and a required field typed
    in here counts as answered when the stored row already holds a value. That
    is what lets an edit name only what changed without wiping every answer
    placed on another screen, and it keeps the merge in the module that owns
    the rules rather than in each door.

    Every error is keyed `custom_data.<key>` (BR-SHL-037) so FormModal
    highlights the offending control through the path it already has.
    """
    if submitted is None:
        submitted = {}
    if not isinstance(submitted, dict):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="settings.customFields.values_not_object"
        )
    stored = dict(existing) if isinstance(existing, dict) else {}
    by_key = {d["key"]: d for d in definitions}
    wanted = (screen or "").strip().upper()
    typed_here = (
        {
            key
            for key, d in by_key.items()
            if d.get("is_required") and wanted in screens_for(d.get("placement"), "input")
        }
        if require_input and wanted
        else set()
    )
    fe: list[dict[str, Any]] = []
    out: dict[str, Any] = {}
    cleared: list[str] = []

    for key in sorted(set(submitted) - set(by_key)):
        fe.append(
            _field_error(
                f"custom_data.{key}",
                errors.VAL_UNKNOWN_LOOKUP,
                "customFields.unknown_key",
                key=key,
            )
        )

    for key, definition in by_key.items():
        present = key in submitted
        raw = submitted.get(key)
        blank = raw is None or (isinstance(raw, str) and not raw.strip()) or raw == []
        if not present:
            continue
        if blank:
            if key in typed_here:
                fe.append(
                    _field_error(
                        f"custom_data.{key}", errors.VAL_REQUIRED, "customFields.required", key=key
                    )
                )
            # A blank on a non-required field CLEARS it. Storing "" and storing
            # nothing must not be two different states in a jsonb column that a
            # CSV export flattens to the same empty cell (US-SHL-016 TC-4).
            cleared.append(key)
            continue
        value, problem = _coerce(definition, raw, f"custom_data.{key}")
        if problem is not None:
            fe.append(problem)
            continue
        out[key] = value

    for key in sorted(typed_here):
        if key in submitted:
            continue
        held = stored.get(key)
        if held is None or held == "" or held == []:
            fe.append(
                _field_error(
                    f"custom_data.{key}", errors.VAL_REQUIRED, "customFields.required", key=key
                )
            )

    _refuse_values(fe)
    if existing is None:
        return out
    merged = {**stored, **out}
    for key in cleared:
        merged.pop(key, None)
    return merged


def _coerce(definition: dict[str, Any], raw: Any, field: str) -> tuple[Any, dict[str, Any] | None]:
    """One value, checked against its data type. Returns (value, field_error).

    Every refusal is BUILT HERE with `_field_error`, not returned as a tuple for
    the caller to expand: G18 reads `message_key` positionally off this module's
    own helper, and a key that only ever appeared inside a returned tuple would
    read as a DEAD catalogue key while being very much alive on a user's screen.
    """
    data_type = definition.get("data_type")
    options = definition.get("options") or []
    if data_type == "text":
        text = str(raw).strip()
        if len(text) > 500:
            return None, _field_error(field, errors.VAL_RANGE, "customFields.too_long", max=500)
        return text, None
    if data_type == "number":
        return _coerce_number(raw, field)
    if data_type == "date":
        return _coerce_date(raw, field)
    if data_type == "boolean":
        if isinstance(raw, bool):
            return raw, None
        text = str(raw).strip().lower()
        if text in ("true", "1", "yes"):
            return True, None
        if text in ("false", "0", "no"):
            return False, None
        return None, _field_error(field, errors.VAL_FORMAT, "customFields.not_a_boolean")
    if data_type == "select":
        text = str(raw).strip()
        if text not in options:
            return None, _field_error(
                field, errors.VAL_UNKNOWN_LOOKUP, "customFields.option_unknown", value=text
            )
        return text, None
    if data_type == "multi_select":
        values = raw if isinstance(raw, (list, tuple)) else [raw]
        chosen: list[str] = []
        for item in values:
            text = str(item).strip()
            if text not in options:
                return None, _field_error(
                    field, errors.VAL_UNKNOWN_LOOKUP, "customFields.option_unknown", value=text
                )
            if text not in chosen:
                chosen.append(text)
        # US-TEN-016 §4 / BR-TEN-082: the tenant's STORED ORDER is the option
        # order, so a bill and a screen list the choices the same way.
        chosen.sort(key=options.index)
        return chosen, None
    return None, _field_error(field, errors.VAL_UNKNOWN_LOOKUP, "customFields.data_type_unknown")


def _coerce_number(raw: Any, field: str) -> tuple[Any, dict[str, Any] | None]:
    """A `number` custom field is stored as the NORMALISED STRING the operator
    typed — never a float, never a Decimal, never cents.

    This is BR-TEN-048 made structural rather than aspirational. Money is
    `NUMERIC(18,6)` + `CHAR(3)` and rounds only at finalization (CLAUDE.md rule
    2); a custom field has no currency column, no scale and no rounding rule, so
    the only safe thing it can be is a value nobody can arithmetic with by
    accident. `1.5` stays `"1.5"` and `10432` stays `"10432"` — which is also
    exactly what BR-TEN-082's ratified literals print (`10432`, not `10,432`).
    """
    text = str(raw).strip().replace(",", "")
    if not re.match(r"^-?\d{1,18}(\.\d{1,6})?$", text):
        return None, _field_error(field, errors.VAL_FORMAT, "customFields.not_a_number")
    if "." in text:
        text = text.rstrip("0").rstrip(".") or "0"
    return text, None


def _coerce_date(raw: Any, field: str) -> tuple[Any, dict[str, Any] | None]:
    """Stored ISO-8601 `YYYY-MM-DD`, always, whatever the UI renders.

    ⚠ THE DISPLAY FORMAT IS NOT SETTLED AND THIS LANE DOES NOT SETTLE IT.
    A bill deliberately prints ISO (BR-TEN-082: `2026-03-04`, never
    `03/04/2026`, which is 4 March in Madrid and 3 April in Houston); a SCREEN
    renders the tenant's IS-8 regional format; a CSV export uses ISO (IS-11).
    Those three can all be true at once because STORAGE is one thing and
    RENDERING is three — but that the bill and the screen deliberately differ is
    recorded as UNRATIFIED in BR-TEN-082, is raised as an open question by this
    lane, and is flagged rather than chosen here.
    """
    from datetime import date, datetime

    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw.isoformat(), None
    text = str(raw).strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat(), None
    except ValueError:
        return None, _field_error(field, errors.VAL_FORMAT, "customFields.not_a_date")


# ── OQ-075: deactivation and published templates ────────────────────────────
def template_reference_warning(field_key: str) -> dict[str, Any]:
    """The OQ-075 ruling, implemented — WARN, never block.

    PO 2026-08-10, verbatim closure: *"warn, do not block — and the field may
    carry a DEFAULT VALUE. Deactivation proceeds and lists every affected
    published template by name."* The epic's frontmatter still carries OQ-075 in
    `blocked_by`, and its TC-8 still asks for a stub of that question by name.
    The registry says CLOSED, the registry wins, and G8 fails any stub citing a
    closed question. The story text is stale and that is REPORTED.

    WHY THE LIST IS EMPTY TODAY AND WHY THAT IS NOT AN UNWIRED SEAM.
    A template can only "reference a custom field" once custom fields become
    TEMPLATE VARIABLES, which is **US-NOT-016 — a later release**, out of scope
    here by both epics' own §Scope. No binding exists in any published template
    version, so the affected set is empty BY CONSTRUCTION, not by a read that
    could not be answered. `basis` says which of the two it is, so the day
    US-NOT-016 lands and this stops being true, the caller is holding a sentence
    that has become false rather than a silent zero (DEF-075's shape).
    """
    return {
        "field_key": field_key,
        "affected_templates": [],
        "basis": "no_template_variable_binding_in_r2",
        "story": "US-NOT-016",
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-015@a1c9f04 (story+rules snapshot over EP-TEN-09-custom-fields.md +
#         EP-SHL-07-custom-field-rendering.md + 01-tenancy/02-business-rules.md
#         BR-TEN-046..053 + BR-TEN-082 + 00-platform-shell/02-business-rules.md
#         BR-SHL-036..039 + 12-governance/01-open-questions.md OQ-075/076/118/125)
# generated: 2026-08-15 by story-coder (tenant custom-fields lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — api.py carries it) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff --select E4,E7,E9,F✔ black✔ · pytest tests/test_us_ten_014_017_custom_fields.py + tests/test_us_shl_015_016_custom_field_values.py — see the lane report for counts and for the four checks proved RED first
# exceptions: (1) `default_value` is NOT implemented though OQ-075's closure grants it — the column was deliberately not minted by migration 0007 and nothing in R2 reads a default (rendering is R3/US-NOT-016); REPORTED, not silently skipped · (2) OQ-075's warning list is empty BY CONSTRUCTION (no template-variable binding exists in R2) and says so in `basis` rather than returning a bare empty list · (3) the DATE display format and the ENGLISH `Yes`/`No` boolean are UNRATIFIED readings on BR-TEN-082 and are FLAGGED here, not chosen · (4) a `number` is stored as a normalised STRING, never a Decimal — BR-TEN-048 made structural so no caller can arithmetic with it by accident
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
