# ── Trace ──────────────────────────────────────────────
# Change:   CR-126-BRC07 lane NCD-1 — `GET /connections/{id}/record`, the one
#           door that fills the property's Build tab (OQ-MET-12520 CLOSED
#           2026-09-21 on option C: the six drawn tabs land there AS SECTIONS).
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — a cross-tenant read is a
#           404) · hard rule 2 (money 4 dp stored, served as a STRING, 2 dp
#           displayed) · hard rule 8 (an address lives on `premises` and
#           NOWHERE else) · `NFR-3` (every list server-paginated) · `B14` rule
#           31 (no database id is the visible value of a field)
# Rulings:  PO 2026-09-21 (1) the request is PROVENANCE, never a dependency
# ───────────────────────────────────────────────────────
"""The build record, asserted the way it can actually go wrong.

⚠ **THE FAILURE THIS ENDPOINT CAN HAVE IS NOT A CRASH.** It is a screen that
renders and draws a number nobody computed, or a `$0.00` over a real debt. So
these cases assert what each figure MEANS and not merely that a key is present:
that `Outstanding` is null — never zero — on a build with no bill; that the nine
premise rows come from `premises` and NOT from a column on the build; that step
1's three answers survive the commit; and that no list on the payload is
unpaginated.

⚠ **EACH CASE WAS PROVED RED BEFORE IT WAS TRUSTED GREEN, AND THROUGH PYTEST —
the harness that will actually run it** (hard-won law 7, and its 2026-09-04
clause: a guard proved through an entry point nobody uses is no proof of the
thing that matters). The break used for each proof is named in that case's own
docstring, so the next reader can repeat it in one edit.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.metering import api as metering_api
from apps.metering import connection_record as record
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    api_call,
    brazos,
    dana,
    erin,
    lonestar,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


#: The blocks the Build tab's sections read. Asserted as a SET, for
#: `test_w6_connection_detail`'s reason one file over: a key the screen reads
#: and the server does not send is `undefined` in a browser and a blank cell on
#: a page, and neither side can see that alone.
RECORD_KEYS = {
    "id",
    "connection_no",
    "header",
    "tiles",
    "live_state",
    "owner_and_scope",
    "premise",
    "where_it_came_from",
    "plan",
    "money",
    "sections",
    "messages_are_never_sent",
    # `CR-163-BRC10` item 26 — who a clerk may send a letter to.
    "message_recipients",
    "unavailable",
}

#: `THE PREMISE · STEP 2`'s nine rows, blueprint p98-p99. Every one of them is
#: WALKED to `premises` (hard rule 8) and not one is a column on the build.
PREMISE_KEYS = {
    "premise_type",
    "premise_type_code",
    "address_line",
    "unit_label",
    "city",
    "state",
    "postal_code",
    "parcel_or_gis_ref",
    "external_ref",
    "routes",
    "premise_no",
}

SECTION_NAMES = {
    "units",
    "charges",
    "work_orders",
    "communication",
    "audit",
    "outstanding",
}


def _build(actor, *, no="CON-26-0210", address="212 Balcones Drive", units=2):
    """One build through the REAL write paths — no ORM shortcuts.

    Two units on electric and water, which is the multi-unit shape the drawing
    heads: seven units, three services, `3 of 7` activated.
    """
    premises = make_premises(
        actor,
        address_line=address,
        city="Austin",
        state="TX",
        postal_code="78704",
        premises_type="single_family",
    )
    unit_ids = [
        make_unit(actor, premises["id"], label=f"{no} unit {n + 1}")["id"] for n in range(units)
    ]
    created = w6.create_connection(
        actor,
        {
            "premises_id": premises["id"],
            "target_activation": date(2026, 5, 26),
            # Step 1's three answers, which had nowhere to land until
            # `metering/0058`.
            "owner_type": "builder_developer",
            "units_prefix": "BAL",
            "scope": "multi_unit",
        },
    )
    connection = work_tables.Connection.objects.get(pk=created["id"])
    work_tables.Connection.objects.filter(pk=connection.id).update(connection_no=no)
    for unit_id in unit_ids:
        w6.add_connection_service(actor, connection.id, service_code="electric", unit_id=unit_id)
        w6.add_connection_service(actor, connection.id, service_code="water", unit_id=unit_id)
    w6.submit_connection(actor, connection.id)
    connection.refresh_from_db()
    return connection, premises, unit_ids


def _wizard_plan(**over):
    """**The payload `commitPlanOf` actually emits** — keys and spellings both.

    Copied from `tests/test_def_met_5441_the_commit_door.py`, which copied it
    from `NewConnectWizard.tsx`, and NOT from `commit_new_connect`'s parameter
    list. That difference is the whole point: three defects in a row on this one
    call (`DEF-MET-5428`, `DEF-MET-5093`, `DEF-MET-5437`) were the payload and
    the reader disagreeing about a key, with both sides tested on their own half.
    """
    plan = {
        "premises": {
            "id": None,
            "address": "212 Balcones Drive",
            "premise_type": None,
            "parcel_ref": "R-0044-1189",
            "read_route": None,
            # `DEF-MET-5465` — step 4's ticks. Without them the property is
            # created with `services_available` NULL and `BR-MET-003`'s inner
            # bound refuses EVERY meter.
            "services_available": ["electric"],
        },
        "mode": "our_crew",
        "scope": "new_premise",
        "units_prefix": "Apt",
        "target_activation": None,
        "service_request_id": None,
        "units": [{"label": "Apt 1", "is_common_area": False}],
        "meters": [],
        "plan_assignments": [],
        "create_owner_account": False,
        "owner": {},
        "quote_total": None,
        "occupancy": "vacant_service_off",
        "work_orders": [],
    }
    plan.update(over)
    return plan


# ════════════════════════════════════════════════════════════════════════════
# THE CONTRACT
# ════════════════════════════════════════════════════════════════════════════
def test_record_serves_every_block_the_build_tab_reads(dana, brazos):
    """The thirteen blocks, no more and no fewer.

    RED PROVED: delete `"plan"` from the returned dict in
    `connection_record.build_record` — `AssertionError: assert {...} == {...}`
    naming `plan` as missing from the left set.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)
        payload = record.build_record(connection.id)

    assert set(payload) == RECORD_KEYS
    assert set(payload["premise"]) == PREMISE_KEYS
    assert set(payload["sections"]) == SECTION_NAMES
    # `B14` rule 31 — what a clerk sees is the NUMBER.
    assert payload["connection_no"] == "CON-26-0210"


# ════════════════════════════════════════════════════════════════════════════
# STEP 1's THREE ANSWERS — collected since the wizard was built, stored today
# ════════════════════════════════════════════════════════════════════════════
def test_step_one_answers_survive_the_commit(dana, brazos):
    """`owner_type`, `units_prefix` and `scope` reach the row and come back.

    Until `metering/0058` all three were typed by a clerk and discarded:
    `commit_new_connect` answered a stated absence saying *"connections has no
    column for either"* and `_owner_block_in_the_doors_language` deleted the
    owner's classification before the payload reached the accounts door.

    RED PROVED: drop the three keyword arguments from
    `Connection.objects.create` in `connections.create_connection` —
    `AssertionError: assert None == 'builder_developer'`.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)
        payload = record.build_record(connection.id)

    block = payload["owner_and_scope"]
    assert block["owner_type"] == "builder_developer"
    assert block["units_prefix"] == "BAL"
    assert block["scope"] == "multi_unit"
    # ⚠ **THE OTHER TWO ROWS ARE THE OWNER'S AND ARE WALKED, NOT STORED.**
    # p106: *"the name belongs to the account that pays."* This build names no
    # payer, so both are NULL rather than falling back to the applicant — *who
    # applied* and *who pays* are two questions and answering one with the other
    # is how a bill reaches the wrong company.
    assert block["owner_or_developer"] is None
    assert block["external_system_reference"] is None


def test_owner_type_is_not_the_party_kind(dana, brazos):
    """`owner.kind` is the CLASSIFICATION and never `person`/`company`.

    `DEF-MET-5438`: `OWNER_KINDS` is *builder or developer · property owner ·
    landlord · occupier*, and `customers.kind` refuses all four BY NAME. A lane
    that mapped one onto the other would trade a missing-kind refusal for an
    unknown-lookup one, on a customer's permanent record.

    RED PROVED: change `create_connection`'s writer to
    `owner_type=(data.get("party_kind") or None)` — the commit then stores
    `company` and this case fails on the assertion below.
    """
    with tenant_ctx(brazos):
        made = w6.commit_new_connect(
            dana,
            _wizard_plan(
                scope="multi_unit",
                units_prefix="BAL",
                owner={
                    "name": "Balcones Development LLC",
                    # The drawn *Owner type* …
                    "kind": "builder_developer",
                    # … and the accounts door's own question, beside it.
                    "party_kind": "company",
                },
            ),
        )
        connection = work_tables.Connection.objects.get(pk=made["id"])

    assert connection.owner_type == "builder_developer"
    assert connection.owner_type not in {"person", "company"}
    assert connection.scope == "multi_unit"
    assert connection.units_prefix == "BAL"


def test_the_scope_absence_is_gone_rather_than_reworded(dana, brazos):
    """`no_column_for_the_scope_or_the_prefix` no longer travels.

    A stated absence that outlives its cause is a lie the product tells about
    itself (hard-won law 1). `metering/0058` gives all three a column, so the
    sentence is deleted and this case is what stops it coming back.

    RED PROVED: restore the `absences.append({... "field": "scope" ...})` block
    in `commit_new_connect` — the code appears in `unavailable` and this fails.
    """
    with tenant_ctx(brazos):
        made = w6.commit_new_connect(dana, _wizard_plan(scope="multi_unit"))

    codes = {entry.get("code") for entry in (made.get("unavailable") or [])}
    assert "no_column_for_the_scope_or_the_prefix" not in codes
    # …and the answer it used to say was unreadable IS on the row.
    assert work_tables.Connection.objects.get(pk=made["id"]).scope == "multi_unit"


# ════════════════════════════════════════════════════════════════════════════
# HARD RULE 8 — the premise block is WALKED, never a column on the build
# ════════════════════════════════════════════════════════════════════════════
def test_the_premise_block_is_walked_to_premises(dana, brazos):
    """Nine rows, every one of them read off `premises`.

    `BR-MET-1161`: *"we are having addresses at one place now - Premises and
    Units -> then they flow to {Meters, Sub meter, assets} + {accounts}"*. The
    build declares no address column and this case proves the screen still gets
    an address — which is the half `DEF-CUS-3653` shows is invisible otherwise,
    where a header composed a locality from a retired value and would have
    returned null for ever with every test green.

    RED PROVED: move the PREMISES' own `city` and re-read — the record follows
    it. A build carrying its own copy would not, and that is the defect this
    case exists to make visible.

    ⚠ **THE MOVE IS MADE ON THE `premises` ROW DIRECTLY, ON PURPOSE.** Every
    other write in this file goes through the real service; here the subject is
    the READ, and routing the move through `update_premises` would put that
    function's own validation between the assertion and the thing it asserts. A
    failure there would read as *the build does not walk*, which is the one
    sentence this case must never say wrongly.
    """
    from apps.metering import models as metering_models

    with tenant_ctx(brazos):
        connection, premises, _units = _build(dana)
        first = record.build_record(connection.id)["premise"]

        metering_models.Premises.objects.filter(pk=premises["id"]).update(city="Katy")
        second = record.build_record(connection.id)["premise"]

    assert first["city"] == "Austin"
    assert first["address_line"] == "212 Balcones Drive"
    assert first["state"] == "TX"
    assert first["postal_code"] == "78704"
    # THE WALK, proved by movement: the property moved and the build followed.
    assert second["city"] == "Katy"
    # ⚠ **NO `connections` COLUMN HOLDS ANY OF IT (hard rule 8, and `G85`
    # enforces the same list by NAME).** `state` is deliberately NOT in this
    # set: `connections.state` is the BUILD's lifecycle — draft, in progress,
    # activated — and has nothing to do with Texas. A guard that refused it
    # would be the gate reading a name instead of a fact, which is the failure
    # `G85`'s own field-scoped allow list exists to avoid.
    columns = {field.name for field in work_tables.Connection._meta.get_fields()}
    assert columns.isdisjoint(
        {"city", "postal_code", "address_line", "address", "premise_type", "lat", "lng"}
    )


def test_the_customer_class_chip_is_the_premise_type(dana, brazos):
    """The chip is `premises.premises_type` and gets NO column of its own.

    The drawing proves they are one fact: `THE PREMISE · STEP 2`'s first row and
    the header chip both read *Apartment block*. So the header carries no chip
    key at all and the screen reads `premise.premise_type` — one source, views
    derived (hard-won law 5).

    RED PROVED: add `"premise_type": None` back to the header block — the second
    assertion fails on a key that must not exist.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)
        payload = record.build_record(connection.id)

    assert payload["premise"]["premise_type_code"] == "single_family"
    assert "premise_type" not in payload["header"]


# ════════════════════════════════════════════════════════════════════════════
# THE MONEY — null is never zero, and every figure is a STRING
# ════════════════════════════════════════════════════════════════════════════
def test_a_build_with_no_bill_owes_null_and_never_zero(dana, brazos):
    """`OUTSTANDING` is `{None, None}` with a stated code, not `$0.00`.

    ⚠ **A ZERO HERE READS AS *SETTLED* AND THE TRUTH IS *NEVER PRICED*.** That
    substitution is `DEF-127`, and on the one tile a clerk chases money from it
    is the whole reason this case exists.

    RED PROVED: return `reads._pair(Decimal("0"))` instead of the empty pair in
    `_money`'s no-bill branch — `assert {'stored': '0.0000', 'display': '0.00'}
    == {'stored': None, 'display': None}`.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)
        payload = record.build_record(connection.id)

    assert connection.quote_invoice_id is None
    money = payload["money"]
    assert money["outstanding"] == {"stored": None, "display": None}
    assert money["quoted"] == {"stored": None, "display": None}
    assert money["taken"] == {"stored": None, "display": None}
    assert payload["tiles"]["outstanding"] == {"stored": None, "display": None}
    codes = {entry["code"] for entry in money["unavailable"]}
    assert record.ABSENCE_NO_BILL in codes
    # PO ruling 1 of 2026-09-21 — this build has no request and the commit path
    # does not yet price it itself. Named on the payload rather than left to
    # look like this particular build's data.
    assert record.ABSENCE_DIRECT_BUILD_PRICES_NOTHING in codes


def test_outstanding_is_quoted_minus_taken_and_is_derived(dana, brazos, monkeypatch):
    """`$3,030.00 − $1,500.00 = $1,530.00`, and not one of the three is stored.

    The bill's total is BILLING's immutable column; what has been paid against
    it is PAYMENTS' own arithmetic over its append-only allocations; the
    subtraction is the only arithmetic this module does. `connections
    .quote_total` is served BESIDE the bill's total as `quote_total_recorded`
    rather than instead of it, so a disagreement is visible rather than
    silently resolved.

    ⚠ **THE FIGURES ARE THE BLUEPRINT'S AND THEY ARE ILLUSTRATIONS** (`B14` rule
    37). What is asserted is the ARITHMETIC and the SHAPE, and they would hold
    for any three numbers.

    RED PROVED: make `_money` return `reads._pair(quoted)` for `outstanding` —
    `assert {'stored': '3030.0000', ...} == {'stored': '1530.0000', ...}`.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)
        work_tables.Connection.objects.filter(pk=connection.id).update(
            quote_invoice_id="0199a1d2-0000-7000-8000-00000000cafe",
            quote_total=Decimal("3030.0000"),
        )
        monkeypatch.setattr(
            record.seams,
            "quote_bill",
            lambda invoice_id: {
                "invoice_no": "BL-2605-000091",
                "account_no": "A-10088",
                "total": Decimal("3030.0000"),
                "lines": [
                    {
                        "charge_code": "CONN-FEE",
                        "description": "Connection fee",
                        "quantity": "6.000000",
                        "unit_price": "325.0000",
                        "amount": "1950.0000",
                    }
                ],
            },
        )
        monkeypatch.setattr(
            record.seams,
            "settled_against_bills",
            lambda ids: {str(list(ids)[0]): Decimal("1500.0000")},
        )
        payload = record.build_record(connection.id)

    money = payload["money"]
    # Hard rule 2 — stored to 4, displayed to 2, both STRINGS, never a float.
    assert money["quoted"] == {"stored": "3030.0000", "display": "3030.00"}
    assert money["taken"] == {"stored": "1500.0000", "display": "1500.00"}
    assert money["outstanding"] == {"stored": "1530.0000", "display": "1530.00"}
    assert isinstance(money["outstanding"]["display"], str)
    # `B14` rule 31 — the bill NUMBER travels, never the invoice's row id.
    assert money["invoice_no"] == "BL-2605-000091"
    assert money["billed_to"] == "A-10088"
    # The row's own copy is served beside the bill's, never instead of it.
    assert money["quote_total_recorded"] == {"stored": "3030.0000", "display": "3030.00"}
    # The tiles read the same answer as the money block — one derivation.
    assert payload["tiles"]["outstanding"] == money["outstanding"]
    assert payload["tiles"]["quoted"] == money["quoted"]
    # The charge table is the bill's own lines.
    assert payload["sections"]["charges"]["results"][0]["charge_code"] == "CONN-FEE"


def test_nothing_paid_is_zero_and_nobody_asked_is_null(dana, brazos, monkeypatch):
    """The two absences payments can hand back are DIFFERENT answers.

    A bill with no allocation row is ABSENT from payments' map, which means
    *nothing has been paid against it* — a true answer over an append-only
    table, so `taken` is `0.0000`. Payments publishing NO read at all means
    *nobody could be asked*, and `taken` is null with its own code. Collapsing
    the second into the first would report a debt as unpaid-in-full on the
    evidence that nobody looked.

    RED PROVED: make `seams.settled_against_bills` return `{}` instead of `None`
    on an unpublished read — the second half then reads `0.0000` and fails.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)
        work_tables.Connection.objects.filter(pk=connection.id).update(
            quote_invoice_id="0199a1d2-0000-7000-8000-00000000beef"
        )
        bill = {
            "invoice_no": "BL-2605-000092",
            "account_no": "A-10088",
            "total": Decimal("800.0000"),
            "lines": [],
        }
        monkeypatch.setattr(record.seams, "quote_bill", lambda invoice_id: bill)

        monkeypatch.setattr(record.seams, "settled_against_bills", lambda ids: {})
        nothing_paid = record.build_record(connection.id)["money"]

        monkeypatch.setattr(record.seams, "settled_against_bills", lambda ids: None)
        nobody_asked = record.build_record(connection.id)["money"]

    assert nothing_paid["taken"] == {"stored": "0.0000", "display": "0.00"}
    assert nothing_paid["outstanding"] == {"stored": "800.0000", "display": "800.00"}

    assert nobody_asked["taken"] == {"stored": None, "display": None}
    assert nobody_asked["outstanding"] == {"stored": None, "display": None}
    assert record.ABSENCE_SETTLEMENT_UNPUBLISHED in {
        entry["code"] for entry in nobody_asked["unavailable"]
    }


def test_the_tender_and_the_clearing_date_are_reported_absent(dana, brazos, monkeypatch):
    """Drawn, not served, and SAID so — never filled in with a plausible word.

    The drawing's *"$1,500.00 · cheque CHQ 118420 · 05/04/2026"* needs the
    PAYMENTS behind the allocations, and payments publishes an allocated sum and
    no per-bill payment list. It is payments' to publish, not this module's to
    author (B1).

    RED PROVED: drop the `ABSENCE_TENDER_NOT_PUBLISHED` append from `_money` —
    a null tender then travels with no reason beside it and this fails.

    ⚠ **NARROWED 2026-10-02 (`CR-163-BRC10` item 20).** Payments now publishes
    one row per payment (`selectors.payments_for_bills`), so the absence is
    stated only where THAT read is unpublished — which this case now arranges.
    The rows themselves are asserted in `test_cr163_build_charges_tab.py`.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)
        work_tables.Connection.objects.filter(pk=connection.id).update(
            quote_invoice_id="0199a1d2-0000-7000-8000-0000000000aa"
        )
        monkeypatch.setattr(
            record.seams,
            "quote_bill",
            lambda invoice_id: {
                "invoice_no": "BL-1",
                "account_no": "A-1",
                "total": Decimal("10.0000"),
                "lines": [],
            },
        )
        monkeypatch.setattr(record.seams, "payments_for_bills", lambda ids, **kw: None)
        money = record.build_record(connection.id)["money"]

    assert money["tender"] is None
    assert money["clearing_date"] is None
    assert record.ABSENCE_TENDER_NOT_PUBLISHED in {e["code"] for e in money["unavailable"]}


def test_the_record_does_not_forward_a_false_absence_onto_a_money_screen(
    dana, brazos, monkeypatch
):
    """`quote_recorded_not_posted` must not travel beside the bill's own lines.

    `connection_detail` still publishes *"The lines behind it were never raised
    as bills, so there is nothing to list here"*, and that stopped being true on
    2026-09-16 when `_post_connection_quote` began raising a real receivable.
    Nobody has ever seen it because nothing called the read — and this record is
    the first thing that WOULD, on the `CHARGES · STEP 6` table, contradicting
    the lines printed next to it. `DEF-MET-6057`.

    ⚠ **AND THE OTHER HALF IS ASSERTED TOO:** on a build with NO bill the
    sentence is still true of that build and travels untouched. Suppressing a
    true sentence to hide a stale code would be the worse of the two.

    RED PROVED: forward `detail["unavailable"]` unfiltered — the code then
    appears on the build that has a bill and the first assertion fails.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)
        no_bill = record.build_record(connection.id)

        work_tables.Connection.objects.filter(pk=connection.id).update(
            quote_invoice_id="0199a1d2-0000-7000-8000-0000000000bb"
        )
        monkeypatch.setattr(
            record.seams,
            "quote_bill",
            lambda invoice_id: {
                "invoice_no": "BL-2",
                "account_no": "A-2",
                "total": Decimal("1.0000"),
                "lines": [{"charge_code": "CONN-FEE", "description": None,
                           "quantity": "1", "unit_price": "1.0000", "amount": "1.0000"}],
            },
        )
        with_bill = record.build_record(connection.id)

    assert record.STALE_QUOTE_ABSENCE not in {e["code"] for e in with_bill["unavailable"]}
    assert with_bill["sections"]["charges"]["count"] == 1
    # The build with no bill keeps it: the sentence is true OF THAT BUILD.
    assert record.STALE_QUOTE_ABSENCE in {e["code"] for e in no_bill["unavailable"]}


# ════════════════════════════════════════════════════════════════════════════
# THE TILES
# ════════════════════════════════════════════════════════════════════════════
def test_a_unit_counts_as_activated_only_when_all_its_services_are(dana, brazos):
    """`3 of 7` units beside `8 of 20 service points live`.

    ⚠ **IF A UNIT COUNTED ON ITS FIRST LIVE SERVICE**, a build with 8 of 20
    points live could report every unit done, which is the opposite of what the
    screen is for. Both tiles are drawn together precisely so a clerk can see
    the gap between them.

    RED PROVED: change `_units_activated`'s `all(...)` to `any(...)` —
    `assert 1 == 0` on the half-activated unit below.
    """
    with tenant_ctx(brazos):
        connection, _premises, unit_ids = _build(dana)
        rows = list(
            work_tables.ConnectionService.objects.filter(
                tenant_id=connection.tenant_id, connection_id=connection.id
            ).order_by("created_at")
        )
        # Unit one: electric live, water still pending. Unit two: untouched.
        first = next(r for r in rows if str(r.unit_id) == str(unit_ids[0]))
        work_tables.ConnectionService.objects.filter(pk=first.pk).update(state=work_tables.SVC_ACTIVATED)
        payload = record.build_record(connection.id)

    assert payload["tiles"]["service_points"] == {"done": 1, "total": 4}
    # ONE of four points is live and NO unit is finished.
    assert payload["tiles"]["activated"] == {"done": 0, "total": 2}
    assert payload["live_state"]["units_activated"] == payload["tiles"]["activated"]

    with tenant_ctx(brazos):
        second = next(
            r for r in rows if str(r.unit_id) == str(unit_ids[0]) and r.pk != first.pk
        )
        work_tables.ConnectionService.objects.filter(pk=second.pk).update(state=work_tables.SVC_ACTIVATED)
        after = record.build_record(connection.id)

    assert after["tiles"]["service_points"] == {"done": 2, "total": 4}
    assert after["tiles"]["activated"] == {"done": 1, "total": 2}


def test_activated_at_is_a_column_and_is_served(dana, brazos):
    """Reported as having no source; it has been a column since W6.

    `refresh_connection_state()` writes it the moment a build reaches
    `activated`, and it was simply never served. Serving a stored column is
    hard-won law 2's other half — `DEF-CUS-3653` is the cautionary tale one
    module over.

    RED PROVED: serve `"activated_at": None` — `assert None is not None`.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)
        assert record.build_record(connection.id)["live_state"]["activated_at"] is None
        work_tables.ConnectionService.objects.filter(
            tenant_id=connection.tenant_id, connection_id=connection.id
        ).update(state=work_tables.SVC_ACTIVATED)
        w6.refresh_connection_state(connection)
        payload = record.build_record(connection.id)

    assert payload["live_state"]["activated_at"] is not None
    assert payload["live_state"]["state"] == work_tables.ACTIVATED


# ════════════════════════════════════════════════════════════════════════════
# WHERE IT CAME FROM — provenance, and PO ruling 1
# ════════════════════════════════════════════════════════════════════════════
def test_a_build_with_no_request_still_reads_and_says_so(dana, brazos):
    """PO 2026-09-21: the request is PROVENANCE, never a dependency.

    Verbatim: *"this request is new work and recognized seperately from
    applcaition and hence we should not make it dependent on applciation #"*. So
    every row under `WHERE IT CAME FROM` is null on a build raised directly —
    and **the rest of the record is complete**, which is the half that proves
    the ruling is obeyed rather than merely quoted.

    RED PROVED: make `_approved_by` raise on `request is None` — the read then
    500s for every directly-raised build, which is what a dependency looks like.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)
        payload = record.build_record(connection.id)

    assert connection.service_request_id is None
    came_from = payload["where_it_came_from"]
    assert came_from["request_no"] is None
    assert came_from["approved"] == {"by": None, "at": None}
    assert came_from["fee_outstanding"] == {"stored": None, "display": None}
    # Nothing else on the record depends on the request.
    assert came_from["created_at"] is not None
    assert payload["premise"]["address_line"] == "212 Balcones Drive"
    assert payload["tiles"]["units"] == 2


# ════════════════════════════════════════════════════════════════════════════
# NFR-3 — every list on this payload is server-paginated
# ════════════════════════════════════════════════════════════════════════════
def test_every_section_is_paginated_and_none_is_a_bare_array(dana, brazos):
    """Six sections, four envelope keys each, and no unpaginated list anywhere.

    `NFR-3` is universal server pagination and `NFR-5` is no hard cap anywhere.
    A build is not small — a 500-unit block on three services is 1,500 service
    rows before a single work order — so a bare array here is the shape that is
    correct at T7 and 13× short at T5.

    RED PROVED: return `unit_rows` directly instead of `paged("units", ...)` —
    `assert ['...'] is a list, not a dict` on the first `set(...)` below.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)
        payload = record.build_record(connection.id)

    for name, block in payload["sections"].items():
        assert set(block) == {"count", "page", "per", "results"}, name
        assert isinstance(block["results"], list), name
        assert block["page"] == 1, name
        assert block["per"] == 50, name


def test_one_section_pages_deeper_and_the_others_stay_on_page_one(dana, brazos):
    """`?section=` names the ONE list `page`/`per` apply to.

    One call fills the whole tab — the point of `OQ-MET-12520`'s ruling is that
    a clerk stops hopping between three places, and three round trips to fill
    one tab is that problem wearing a different hat.

    RED PROVED: pass `paged=True` for every section in `build_record` — page 2
    then empties the other five and this fails on `communication`.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)
        payload = record.build_record(connection.id, section="communication", page=2, per=50)
        first = record.build_record(connection.id, section="communication", page=1, per=50)

    comms = payload["sections"]["communication"]
    # Seven rows fit one 50-row page, so page 2 CLAMPS back to 1 rather than
    # erroring or emptying — `BR-SHL-011`, and it is the same clamp the whole
    # product's list plumbing makes.
    assert comms["page"] == 1
    assert comms["count"] == first["sections"]["communication"]["count"]
    # The other five are untouched and complete.
    for name in SECTION_NAMES - {"communication"}:
        assert payload["sections"][name]["page"] == 1, name


def test_page_and_per_clamp_and_never_error(dana, brazos):
    """`BR-SHL-011` — a list URL can never 4xx over its own params.

    `per=75` clamps DOWN to 50 (never granting more rows than asked for) and a
    nonsense page falls back to 1.

    RED PROVED: replace `clamp_page_size(per)` with `int(per)` — `ValueError:
    invalid literal for int()` on the `"banana"` case.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)
        clamped = record.build_record(connection.id, section="units", page="banana", per=75)
        big = record.build_record(connection.id, section="units", page=1, per=100000)

    assert clamped["sections"]["units"]["per"] == 50
    assert clamped["sections"]["units"]["page"] == 1
    assert big["sections"]["units"]["per"] == 1000


def test_an_unknown_section_is_ignored_and_not_refused(dana, brazos):
    """An unrecognised name pages nothing and is NOT an error (`BR-SHL-011`).

    RED PROVED: raise on `section not in SECTIONS` — the call then 4xxs and this
    fails with that error instead of a payload.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)
        payload = record.build_record(connection.id, section="not-a-section", page=9)

    assert set(payload) == RECORD_KEYS
    for block in payload["sections"].values():
        assert block["page"] == 1


# ════════════════════════════════════════════════════════════════════════════
# COMMUNICATION — queued is not sent, and nothing has ever been filed
# ════════════════════════════════════════════════════════════════════════════
def test_no_connection_letter_can_be_filed_and_the_payload_says_so(dana, brazos):
    """`OQ-NOT-12521` is OPEN and the state is `not_sent`, never `queued`.

    `connection` is not one of the fourteen things an outbound message may be
    about, so all three letters are refused BY NAME. The drawing's own red line
    — *"Queued is not sent"* — is optimistic by one step today, and
    `nothing_is_sent()`'s fact travels so no screen can claim otherwise.

    RED PROVED: set each row's `state` to `messages.STATE_QUEUED` — the first
    assertion fails, which is the screen claiming a letter that does not exist.
    """
    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)
        payload = record.build_record(connection.id)

    rows = payload["sections"]["communication"]["results"]
    assert rows, "the drawn rows are a fixed vocabulary and must always travel"
    assert {row["state"] for row in rows} <= {"not_sent", "not_asked"}
    assert payload["messages_are_never_sent"] == {
        "queued_only": True,
        "delivers": False,
        "br_ref": "BR-NOT-013",
    }
    # NO ENGLISH TRAVELS — the words are the front end's eleven catalogues
    # (`B14` rule 35). What crosses the wire is the occasion CODE.
    assert all(row["code"] and " " not in row["code"] for row in rows)


# ════════════════════════════════════════════════════════════════════════════
# HARD RULE 1 — a cross-tenant read is a 404, never a 403
# ════════════════════════════════════════════════════════════════════════════
def test_another_tenants_build_is_not_found(dana, brazos, erin, lonestar):
    """`HR-1`/`G4`: *no such build* and *not yours* are the same answer.

    A 403 would confirm the row exists, which is the probe the indistinguishable
    404 exists to refuse.

    RED PROVED: drop the `tenant_id` filter from `reads._connection_or_404` —
    the read then returns Lone Star's own payload to Brazos Bend.
    """
    from core import errors

    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)

    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            record.build_record(connection.id)


# ════════════════════════════════════════════════════════════════════════════
# THE DOOR — built is not wired (hard-won law 2)
# ════════════════════════════════════════════════════════════════════════════
def test_the_record_has_a_door_and_the_view_returns_it_verbatim(dana, brazos):
    """A read nothing can call is not a feature.

    `GET /connections/{id}/record` is REGISTERED and the view returns the read
    model's payload unchanged — no figure derived in the view, no absence
    defaulted. `connection_detail` next door spent three weeks as a screen
    calling an endpoint that did not exist; this is the assertion that would
    have caught it.

    RED PROVED: remove the `path(...)` line from `api.urlpatterns` — the route
    lookup below finds nothing and fails before any payload is compared.
    """
    from django.urls import ResolverMatch  # noqa: F401 — documents the intent

    routes = {
        str(entry.pattern): entry.callback
        for entry in metering_api.urlpatterns
        if hasattr(entry, "callback")
    }
    assert "connections/<uuid:connection_id>/record" in routes
    assert routes["connections/<uuid:connection_id>/record"] is (
        metering_api.connection_build_record
    )
    # ⚠ **ORDERING IS LOAD-BEARING** — the literal sub-path must be registered
    # ABOVE the bare id route, which is the habit the thirteen doors beside it
    # follow and what stops the next literal being swallowed.
    ordered = [str(entry.pattern) for entry in metering_api.urlpatterns]
    assert ordered.index("connections/<uuid:connection_id>/record") < ordered.index(
        "connections/<uuid:connection_id>"
    )

    with tenant_ctx(brazos):
        connection, _premises, _units = _build(dana)
        expected = record.build_record(connection.id)

    # ⚠ **THROUGH `api_call`, WHICH IS THE WIRED STACK** — authenticated user,
    # server-attached role, BE-01 tenant context entered around the view, which
    # is the middleware's job in production. Calling the view with a hand-made
    # request would prove the function and not the DOOR (hard-won law 7's
    # 2026-09-04 clause: a proof through an entry point nobody uses).
    #
    # NO QUERY PARAMS, on purpose: a caller that names nothing must get page one
    # of every list, which is the Build tab's own first paint.
    served = api_call(
        metering_api.connection_build_record,
        "get",
        "/api/brazosbend/connections/x/record",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        connection_id=connection.id,
    )

    assert served.status_code == 200
    assert served.data == expected


# ════════════════════════════════════════════════════════════════════════════
# THE COMMIT AND THE RECORD AGREE — `DEF-MET-6108`
# ════════════════════════════════════════════════════════════════════════════
def test_every_tile_on_a_committed_build_equals_the_rows_behind_it(dana, brazos):
    """**A tile is a door: its number is the rows behind it.**

    `DEF-MET-6108`, 2026-09-21: `CON-26-0139` — eight units, sixteen meters and
    a real `$315.00` invoice — printed `UNITS 0 · ACTIVATED 0 of 0 · 0 of 0
    points live` on its own record. **The units, the plans and the service
    points were all REAL.** What no commit had ever written was the row that
    says *this BUILD provides this SERVICE at this UNIT*, and every one of those
    figures counts exactly that table.

    ⚠ **WHY NO CASE IN THIS FILE COULD SEE IT.** `_build` above calls
    `add_connection_service` by hand, twice per unit, because that is the only
    way the rows have ever existed — so twenty-one record cases asserted tiles
    over a fixture that wrote what the product does not. This case drives
    `commit_new_connect` with the payload the BROWSER sends and asks the record
    what it reads back, which is the one question nobody was asking.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (hard-won law 7, habit 2): counting
    the same rows twice. So every figure is taken from the MODEL on one side —
    `Unit` and `ConnectionService` objects, queried directly — and from the
    SERVED payload on the other, and the fixture's own arithmetic is asserted
    first so a green run over a build that made nothing cannot read as a pass.

    RED PROVED (through `pytest`, the harness that runs it): make step 2b's loop
    in `commit_connection` `continue` unconditionally —
    `AssertionError: the commit wrote no connection_services row —
    DEF-MET-6108; got 0` / `assert 0 == 6`. Break the TILE instead (serve
    `"units": 0`) and the next assertion fires by name: *the record says 0 units
    over the 3 the database holds for this build*.
    """
    labels = ["Apt 1", "Apt 2", "Common area"]
    with tenant_ctx(brazos):
        built = w6.commit_new_connect(
            dana,
            _wizard_plan(
                premises={
                    "id": None,
                    "address": "77 Cypress Bend",
                    "premise_type": None,
                    "parcel_ref": None,
                    "read_route": None,
                    "services_available": ["electric", "water"],
                },
                units=[
                    {"label": "Apt 1", "is_common_area": False},
                    {"label": "Apt 2", "is_common_area": False},
                    {"label": "Common area", "is_common_area": True},
                ],
                # Step 4's grid, as `commitPlanOf` emits it: one meter per unit
                # per METERED service, the common area included.
                meters=[
                    {"unit_label": label, "service": service, "asset_no": None}
                    for label in labels
                    for service in ("electric", "water")
                ],
            ),
        )
        connection = work_tables.Connection.objects.get(pk=built["id"])

        # ── THE MODEL SIDE ───────────────────────────────────────────────────
        service_rows = list(
            work_tables.ConnectionService.objects.filter(
                tenant_id=connection.tenant_id, connection_id=connection.id
            ).select_related("service", "unit")
        )
        units_in_the_database = {
            unit.label
            for unit in metering_models.Unit.objects.filter(
                tenant_id=connection.tenant_id, premises_id=connection.premises_id
            )
        }
        payload = record.build_record(connection.id)

    # The fixture's own arithmetic, stated before anything is compared: three
    # units, two services each, six service points and none of them live.
    assert units_in_the_database == set(labels)
    assert len(service_rows) == 6, (
        "the commit wrote no connection_services row — DEF-MET-6108; "
        f"got {len(service_rows)}"
    )
    assert {(row.unit.label, row.service.code) for row in service_rows} == {
        (label, service) for label in labels for service in ("electric", "water")
    }

    tiles = payload["tiles"]
    units_behind_the_door = len({row.unit_id for row in service_rows if row.unit_id})
    assert tiles["units"] == units_behind_the_door == 3, (
        f"the record says {tiles['units']} units over the {units_behind_the_door} "
        "the database holds for this build — DEF-MET-6108"
    )
    assert tiles["service_points"] == {"done": 0, "total": len(service_rows)}, (
        f"the points tile says {tiles['service_points']} over {len(service_rows)} rows"
    )
    # Nothing is live on a fresh build, and an empty set is NOT a satisfied one
    # — `_units_activated`'s own rule, which is why `done` is 0 and not 3.
    assert tiles["activated"] == {"done": 0, "total": units_behind_the_door}

    # ⚠ **THE COMMIT'S OWN MANIFEST AND THE READBACK, CROSSED.** The manifest
    # said `Units 3` on the defect too, and was right; the record said 0. A test
    # that asked only one of them would have passed on it.
    assert built["manifest"]["units"] == tiles["units"]
    assert built["manifest"]["meters"] == len(service_rows)

    # The service tags under the address line, and the units section, both read
    # the same rows — so a build that records nothing loses its whole tab.
    assert payload["header"]["services"] == ["electric", "water"]
    unit_section = payload["sections"]["units"]
    assert unit_section["count"] == units_behind_the_door
    assert {row["label"] for row in unit_section["results"]} == set(labels)
    for row in unit_section["results"]:
        assert row["services"] == ["electric", "water"], row["label"]


def test_a_committed_build_is_no_longer_a_reading_of_nothing(dana, brazos):
    """**The STATE is derived from these rows too, which is the half a tile does
    not show.**

    `derive_connection_state` tallies `connection_services`; with none, a
    submitted build fell through every branch to the same word for ever,
    however much work was done on it. So this asserts the state MOVES when a
    service does — on a build made by the commit and by nothing else.

    RED PROVED: the same `continue` as the case above —
    `AssertionError: no row to activate — DEF-MET-6108` / `assert None is not
    None`, because with no row there is nothing to activate and the state can
    never move.
    """
    with tenant_ctx(brazos):
        built = w6.commit_new_connect(
            dana,
            _wizard_plan(
                premises={
                    "id": None,
                    "address": "9 Cypress Bend",
                    "premise_type": None,
                    "parcel_ref": None,
                    "read_route": None,
                    "services_available": ["electric", "water"],
                },
                units=[{"label": "Apt 1", "is_common_area": False}],
                meters=[
                    {"unit_label": "Apt 1", "service": "electric", "asset_no": None},
                    {"unit_label": "Apt 1", "service": "water", "asset_no": None},
                ],
            ),
        )
        connection = work_tables.Connection.objects.get(pk=built["id"])
        one = work_tables.ConnectionService.objects.filter(
            tenant_id=connection.tenant_id, connection_id=connection.id, service__code="electric"
        ).first()
        assert one is not None, "no row to activate — DEF-MET-6108"
        work_tables.ConnectionService.objects.filter(pk=one.pk).update(state=work_tables.SVC_ACTIVATED)
        w6.refresh_connection_state(connection)
        payload = record.build_record(connection.id)

    assert payload["tiles"]["service_points"] == {"done": 1, "total": 2}
    assert payload["live_state"]["state"] == work_tables.PARTLY_ACTIVATED


def test_a_service_that_takes_no_meter_is_reported_missing_rather_than_invented(
    dana, brazos
):
    """**`DEF-MET-6119` — the half this commit cannot record, said out loud.**

    `commitPlanOf` emits a `meters` row only where `takesAMeter(service)` is
    true, so trash, fire, storm water, broadband and thermal heat reach the
    commit on no key at all. Pairing the address's service list with every unit
    would write a row for a unit the clerk unticked, which is `BR-MET-112`'s own
    prohibition — so the gap travels as an ABSENCE on the response and the
    screen can read it in words.

    ⚠ The tenant here sells electric and water, both metered, so the ordinary
    build reports NO absence. That negative is asserted first: an absence that
    fires on every commit is noise nobody reads.

    RED PROVED: return `[]` from `_services_without_a_meter` — the second half
    fails with `[] == ['trash']`.
    """
    with tenant_ctx(brazos):
        ordinary = w6.commit_new_connect(
            dana,
            _wizard_plan(
                premises={
                    "id": None,
                    "address": "11 Cypress Bend",
                    "premise_type": None,
                    "parcel_ref": None,
                    "read_route": None,
                    "services_available": ["electric"],
                },
                units=[{"label": "Apt 1", "is_common_area": False}],
                meters=[{"unit_label": "Apt 1", "service": "electric", "asset_no": None}],
            ),
        )
    assert [
        absence
        for absence in ordinary["unavailable"]
        if absence["field"] == "connection_services"
    ] == []

    # The same build with a service the wizard maps and never sends.
    assert w6._services_without_a_meter(
        {
            "premises": {"services_available": ["electric", "trash"]},
            "meters": [{"unit_label": "Apt 1", "service": "electric"}],
        }
    ) == ["trash"]
    # A picked address sends no list, so there is nothing to subtract from and
    # the absence stays silent rather than naming the wrong services.
    assert w6._services_without_a_meter(
        {"premises": {"services_available": None}, "meters": []}
    ) == []
