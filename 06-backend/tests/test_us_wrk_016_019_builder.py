# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-016 (the eight-step builder and its packs) · US-WRK-017
#           (New Connect step 6 proposes from the utility's own templates) ·
#           US-WRK-019 (the 24 seeded starters become editable bundles).
#           Screens: Work-013 · Work-014 … 017 · Work-004
# Rules:    BR-WRK-011 (Publish is the ONE write) · BR-WRK-013 (the starters,
#           and gas gated on the LIGHT-UP) · BR-WRK-014 (every seeded starter
#           row has a reader) · BR-WRK-015 (a reading's unit is a column) ·
#           BR-WRK-016 (step 6 proposes PUBLISHED templates that hold a place
#           in the connection sequence) · BR-MET-109 · BR-MET-112 · BR-TEN-035
#           (`ST-{0000}`) · CLAUDE.md hard rule 1 · 3 · 7
# Tests:    this file — every TC named in its own test name
# ───────────────────────────────────────────────────────
"""US-WRK-016 · 017 · 019 — the builder, the proposal and the starters, by TC.

⚠ **WHAT IS ASSERTED HERE AND WHAT IS ASSERTED IN A BROWSER.** These are the
SERVER's halves: the packs' rows and their counts, the publish that is the one
write, the proposal's four conditions, and the seeded starters as published
bundles. The eight STEPS themselves are `TemplateBuilder.test.tsx` and
`cr070-e-eight-steps-and-step-six.mjs` — no gate in this repository reads
rendered output (hard-won law 6), so the screen's own proof is a browser.

⚠ **`US-WRK-016` TC-6's PACK ISOLATION IS A REAL CASE AND NOT A VACUOUS ONE.**
The three packs are PLATFORM constants and every tenant gets the same three;
what must never happen is a tenant's own template appearing as a fourth pack.
That is asserted by NAME rather than by counting to three, because a count of
three would pass on the day a fourth platform pack is added and a template
leaks in beside it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.work import connection_models as work_tables
from apps.metering import sample_data as metering_sample
from apps.work import models as work_models
from apps.work import packs as work_packs
from apps.work import selectors as work_selectors
from apps.work import templates_svc

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _part(tenant, part_no, name="A part"):
    return work_models.Part.objects.create(
        tenant_id=tenant.id,
        part_no=part_no,
        name=name,
        unit_of_measure="each",
        unit_cost=Decimal("92.4000"),
    )


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-016 — the builder's server half: the packs, and the ONE write
# ══════════════════════════════════════════════════════════════════════════
def test_tc1_the_meter_exchange_pack_prefills_the_rows_the_drawing_shows(brazos, dana):
    """TC-1 — *"Press New template, pick the Meter exchange pack → steps 2–6
    prefilled: 3 safety · 7 tasks · 3 materials · 3 readings · 3 help."*

    ⚠ The COUNTS are read off the rows rather than off a constant. A hand-typed
    count is what said *Inspection · 3 tasks* while three documents drew four,
    and a count beside nothing to count cannot be contradicted.
    """
    with tenant_ctx(brazos):
        for part_no in ("MTR-E1P", "SEAL-01", "GSKT-STD"):
            _part(brazos, part_no)
        packs = {pack["code"]: pack for pack in work_selectors.template_packs()}
    exchange = packs["METER_EXCHANGE"]
    assert exchange["safety"] == 3
    assert exchange["tasks"] == 7
    assert exchange["parts"] == 3
    assert exchange["readings"] == 3
    assert exchange["help"] == 3
    # `Work-015`'s own caption: TASKS — 7 STEPS · 45 MIN TOTAL.
    assert exchange["est_duration_minutes"] == 45
    assert len(exchange["bundle"]["tasks"]) == exchange["tasks"]


def test_the_inspection_pack_has_four_tasks_because_three_documents_draw_four(brazos, dana):
    """The defect this wave found and fixed.

    `wireframes/Work-014.png`, `08-screen-layouts.md` §13.1 and `US-WRK-016`
    §1 all draw *Inspection · 4 tasks · 0 parts · 2 readings*; the constant
    wave D shipped said **3 tasks** and there were no rows to disagree with it.
    """
    with tenant_ctx(brazos):
        packs = {pack["code"]: pack for pack in work_selectors.template_packs()}
    inspection = packs["INSPECTION"]
    assert (inspection["tasks"], inspection["parts"], inspection["readings"]) == (4, 0, 2)
    assert len(inspection["bundle"]["tasks"]) == 4


def test_every_pack_reading_carries_a_unit_because_the_column_refuses_a_blank(brazos):
    """`BR-WRK-015` and hard rule 3 — and this is the case that caught the
    drawing.

    `wireframes/Work-016.png` draws *New meter serial · — · — · —*: a reading
    with NO unit. `wot_readings.unit_of_measure` is NOT NULL and
    `US-WRK-014` TC-3 refuses a blank one by name, so the pack ships `serial`
    and the divergence is stamped. A pack that shipped the drawing literally
    would 400 on every clerk who picked it.
    """
    for pack in work_packs.PACKS:
        for reading in pack["bundle"]["readings"]:
            assert reading["unit_of_measure"].strip() != "", (pack["code"], reading["prompt"])


def test_a_pack_names_parts_by_number_and_says_which_ones_this_tenant_lacks(brazos, dana):
    """A pack is PLATFORM data and a part is the utility's own row, so the pack
    can only say *MTR-E1P*. A utility that has not entered it gets one material
    fewer AND the missing number by name — an absence nobody can see is what
    `DEF-CUS-3653` cost."""
    with tenant_ctx(brazos):
        _part(brazos, "MTR-E1P")
        packs = {pack["code"]: pack for pack in work_selectors.template_packs()}
    exchange = packs["METER_EXCHANGE"]
    assert [row["part_no"] for row in exchange["bundle"]["materials"]] == ["MTR-E1P"]
    assert sorted(exchange["unresolved_parts"]) == ["GSKT-STD", "SEAL-01"]
    # The COUNT stays the pack's own — what `Work-014`'s tile promises — while
    # the bundle is what this tenant will actually get.
    assert exchange["parts"] == 3


def test_tc2_a_draft_saved_at_step_5_publishes_nothing(brazos, dana):
    """TC-2 · negative — *"work through steps 1–7 and close the tab → NO row
    with `active = true`; a draft row only if Save draft was pressed."*"""
    with tenant_ctx(brazos):
        row = templates_svc.create_draft(dana, {"name": "Backflow test", "service": "water"})
        templates_svc.replace_collection(
            dana, row["id"], "tasks", [{"title": "Check the assembly", "est_minutes": 20}]
        )
        stored = work_tables.WorkOrderTemplate.objects.get(pk=row["id"])
        assert stored.version == 0, "a draft has no version — publish is the one write"
        assert stored.template_no is None, "BR-TEN-035: no number is issued to a draft"
        assert work_selectors.template_status(row) == "draft"


def test_tc4_publishing_twice_in_a_second_makes_one_version_and_one_number(brazos, dana):
    """TC-4 · negative — the load-bearing one. Two presses, one version, one
    `ST-` number: `publish` asks whether the BUNDLE changed rather than holding
    a lock or an idempotency key."""
    with tenant_ctx(brazos):
        row = templates_svc.create_draft(dana, {"name": "Site visit", "service": "water"})
        first = templates_svc.publish(dana, row["id"])
        second = templates_svc.publish(dana, row["id"])
    assert first["version"] == 1 and first["created"] is True
    assert second["version"] == 1 and second["created"] is False
    assert second["template_no"] == first["template_no"]


def test_the_builders_step_7_answers_are_stored_and_default_to_asking(brazos, dana):
    """`work/0005` — the three columns the builder's *Signature* step writes.

    Hard-won law 3: the SAFE option is the default. A template that says
    nothing asks for a signature, records why it was refused, and leaves a card;
    turning any of the three off is what a person has to type.
    """
    with tenant_ctx(brazos):
        row = templates_svc.create_draft(dana, {"name": "Pit inspection", "service": "water"})
        templates_svc.replace_collection(dana, row["id"], "details", {})
        detail = work_models.WorkOrderTemplateDetail.objects.get(template_id=row["id"])
        assert (
            detail.signature_required,
            detail.refusal_reason_required,
            detail.door_hanger_on_no_answer,
        ) == (True, True, True)
        templates_svc.replace_collection(
            dana, row["id"], "details", {"signature_required": False}
        )
        detail.refresh_from_db()
        assert detail.signature_required is False
        # And it reaches the screen's read, not just the row.
        served = work_selectors.template(row["id"])
        assert served["bundle"]["details"]["signature_required"] is False


def test_tc6_lone_stars_packs_are_the_platform_three_and_none_of_brazos_bends(
    brazos, lonestar, dana, erin
):
    """TC-6 · tenant isolation — *"the three platform packs, and none of Brazos
    Bend's templates as a pack."*

    Asserted BY NAME rather than by counting to three: a count would pass on
    the day a fourth platform pack is added and a tenant's template leaks in
    beside it.
    """
    with tenant_ctx(brazos):
        templates_svc.publish(
            dana,
            templates_svc.create_draft(
                dana, {"name": "Meter exchange — residential", "service": "electric"}
            )["id"],
        )
    with tenant_ctx(lonestar):
        codes = [pack["code"] for pack in work_selectors.template_packs()]
        names = [pack["name"] for pack in work_selectors.template_packs()]
    assert codes == ["METER_EXCHANGE", "NEW_CONNECTION", "INSPECTION"]
    assert "Meter exchange — residential" not in names


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-017 — what New Connect step 6 proposes
# ══════════════════════════════════════════════════════════════════════════
def _sells(actor, *codes):
    """Turn a service ON through the S65 toggle, so a template may name it.

    ⚠ **`BR-MET-003` REFUSES A TEMPLATE FOR A SERVICE THE TENANT DOES NOT
    SELL**, and the `brazos` fixture sells Electric and Water. That is correct
    product behaviour, so the gas case turns gas on the way a person would —
    `update_tenant_service`, which also seeds the service's UoMs — rather than
    flipping a column, because a `tenant_services` row with `enabled = true`
    and no unit of measure prices nothing and renders as though it did
    (`journey_cohort_fixtures` records the same reasoning).
    """
    from apps.tenancy import services as tenancy_services

    for code in codes:
        tenancy_services.update_tenant_service(actor, code, {"enabled": True})


def _sequenced(actor, name, service, sequence, *, is_gate=False, publish=True):
    row = templates_svc.create_draft(
        actor,
        {"name": name, "service": service, "sequence": sequence, "is_gate": is_gate},
    )
    if publish:
        templates_svc.publish(actor, row["id"])
    return row


def test_tc1_electric_and_water_propose_five_in_sequence_order(brazos, dana):
    """TC-1 — *"Electric: Service drop → Meter set; Water: Site inspection &
    mark-out → Tap and service line → Meter set"*, each carrying its gate flag,
    **five** in all."""
    with tenant_ctx(brazos):
        _sequenced(dana, "Service drop", "electric", 1)
        _sequenced(dana, "Meter set", "electric", 2, is_gate=True)
        _sequenced(dana, "Site inspection & mark-out", "water", 1)
        _sequenced(dana, "Tap and service line", "water", 2)
        _sequenced(dana, "Meter set", "water", 3, is_gate=True)
        answer = work_selectors.proposed_work_orders("electric,water")
    assert answer["count"] == 5
    assert [row["name"] for row in answer["proposed"]] == [
        "Service drop",
        "Meter set",
        "Site inspection & mark-out",
        "Tap and service line",
        "Meter set",
    ]
    assert [row["is_gate"] for row in answer["proposed"]] == [False, True, False, False, True]
    # `BR-WRK-008` — the version travels, because it is what says WHICH copy an
    # order was raised from.
    assert all(row["version"] == 1 for row in answer["proposed"])


def test_tc4_a_draft_template_is_not_proposed_and_neither_is_a_deactivated_one(brazos, dana):
    """TC-4 · negative — *"a Water template in draft is NOT proposed; only
    published versions are."*

    ⚠ And the DEACTIVATED case rides with it, because `BR-WRK-012` says
    deactivating stops NEW orders and this is where new orders come from.
    """
    with tenant_ctx(brazos):
        _sequenced(dana, "Tap and service line", "water", 1)
        _sequenced(dana, "Leak check", "water", 2, publish=False)
        retired = _sequenced(dana, "Old method", "water", 3)
        templates_svc.deactivate(dana, retired["id"])
        answer = work_selectors.proposed_work_orders("water")
    assert [row["name"] for row in answer["proposed"]] == ["Tap and service line"]


def test_the_sequence_clause_keeps_an_authored_template_out_of_the_proposal(brazos, dana):
    """`BR-WRK-016`'s clause of 2026-09-03 (`DEF-WRK-3573`), and `J60` step 11
    asserts the same absence by name.

    *Meter exchange — residential* is published, Electric, and holds NO place
    in the connection sequence — it is a job a utility does to a live service,
    not a step in building one. Without the `sequence >= 1` clause step 6 would
    propose six where the story and the journey both say five.
    """
    with tenant_ctx(brazos):
        _sequenced(dana, "Service drop", "electric", 1)
        _sequenced(dana, "Meter set", "electric", 2, is_gate=True)
        _sequenced(dana, "Meter exchange — residential", "electric", 0)
        answer = work_selectors.proposed_work_orders("electric")
    assert [row["name"] for row in answer["proposed"]] == ["Service drop", "Meter set"]
    assert "Meter exchange — residential" not in [row["name"] for row in answer["proposed"]]


def test_tc5_gas_proposes_four_and_the_gate_is_the_light_up(brazos, dana):
    """TC-5 — *"the four gas jobs proposed with the gate on Pressure test and
    light-up, not Meter set."*

    **The single most consequential row in the module.** A lane that copies
    electric's shape onto gas bills a customer for gas nobody has lit.
    """
    with tenant_ctx(brazos):
        _sells(dana, "gas")
        _sequenced(dana, "Inspection", "gas", 1)
        _sequenced(dana, "Service line and tap", "gas", 2)
        _sequenced(dana, "Meter set", "gas", 3)
        _sequenced(dana, "Pressure test and light-up", "gas", 4, is_gate=True)
        answer = work_selectors.proposed_work_orders("gas")
    assert answer["count"] == 4
    gates = [row["name"] for row in answer["proposed"] if row["is_gate"]]
    assert gates == ["Pressure test and light-up"]
    meter_set = next(row for row in answer["proposed"] if row["name"] == "Meter set")
    assert meter_set["is_gate"] is False


def test_tc6_lone_star_gets_its_own_templates_and_none_of_brazos_bends(
    brazos, lonestar, dana, erin
):
    """TC-6 · tenant isolation."""
    with tenant_ctx(brazos):
        _sequenced(dana, "Service drop", "electric", 1)
    with tenant_ctx(lonestar):
        answer = work_selectors.proposed_work_orders("electric")
    assert answer["proposed"] == []


def test_no_service_ticked_is_an_empty_proposal_and_not_an_error(brazos, dana):
    """Step 5 may simply not have been answered yet. An empty proposal is the
    truthful answer to that, and a 400 would refuse a clerk who is part-way
    through a form."""
    with tenant_ctx(brazos):
        assert work_selectors.proposed_work_orders("")["count"] == 0
        assert work_selectors.proposed_work_orders(None)["count"] == 0


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-019 — the 24 seeded starters, as published bundles
# ══════════════════════════════════════════════════════════════════════════
def test_the_seeder_writes_through_the_service_and_not_around_it(brazos):
    """`US-WRK-015` TC-4, in the form wave D said would land here.

    Wave D's own suite asserted only that the service EXISTS, because
    re-pointing the seeder was this wave's `E4`. This is the grep the story
    asks for: `sample_data.py` must not write the template model directly.
    """
    source = (
        metering_sample.__file__.replace(".pyc", ".py")
    )
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    for verb in ("create", "get_or_create", "update_or_create", "bulk_create"):
        assert f"WorkOrderTemplate.objects.{verb}(" not in text, verb
    assert "templates_svc" in text, "the seeder goes through Work's own write service"


def test_the_seeded_starters_are_published_bundles_with_numbers(brazos, dana):
    """`US-WRK-019` TC-1/TC-4 — *"24 rows; 8 with `is_gate`; the gas gate is
    Pressure test and light-up"*, and every one of them PUBLISHED.

    ⚠ **A DRAFTED STARTER IS A STARTER STEP 6 WOULD NEVER OFFER** (`BR-WRK-016`
    proposes only published templates), which is why `E4` republishes them
    rather than leaving them at version 0 as wave D's stamp recorded.
    """
    with tenant_ctx(brazos):
        metering_sample._seed_work_order_template_starters(dana)
        rows = list(work_tables.WorkOrderTemplate.objects.filter(tenant_id=brazos.id, is_sample=True))
        assert rows, "the seeder plants starters for the services this tenant sells"
        for row in rows:
            assert row.version >= 1, f"{row.name} is still a draft"
            assert row.template_no, f"{row.name} has no ST- number"
            assert work_models.WorkOrderTemplateDetail.objects.filter(
                template_id=row.id
            ).exists(), f"{row.name} has no wot_details row"


def test_a_replay_publishes_no_second_version(brazos, dana):
    """`BR-TEN-063` — idempotent, and the ORDER of the three calls is what makes
    it so: the `wot_details` row is written only when it is MISSING, because
    writing it moves the header's `updated_at` and `publish` reads that
    timestamp to tell a real second version from a double click."""
    with tenant_ctx(brazos):
        metering_sample._seed_work_order_template_starters(dana)
        before = {
            str(row.pk): row.version
            for row in work_tables.WorkOrderTemplate.objects.filter(tenant_id=brazos.id, is_sample=True)
        }
        metering_sample._seed_work_order_template_starters(dana)
        after = {
            str(row.pk): row.version
            for row in work_tables.WorkOrderTemplate.objects.filter(tenant_id=brazos.id, is_sample=True)
        }
    assert before == after, "a replay writes nothing and versions nothing"


def test_tc3_the_ungated_services_carry_a_reason_a_clerk_can_read(brazos, dana):
    """TC-3 — *"Sewer · Storm water · Solar: zero gates each, and a stored
    reason."*

    ⚠ **THE REASON IS STORED IN THE WORDS `US-WRK-019` TC-3 USES, NOT IN THE
    ENGINEERING ONES.** `W6_UNGATED_STARTERS` quotes B18 §8.1 and names
    `BR-MET-104`; `no_gate_reason` is SHOWN, and B14 rule 32 keeps a rule id
    out of clerk-facing copy. So the same fact is carried twice on purpose.

    ⚠ **STORM WATER'S REASON IS ON NO ROW AND CANNOT BE** — it seeds zero
    starters, so there is no template to put a column on. The declaration
    carries it and this test says so rather than leaving the absence to read as
    an omission.
    """
    with tenant_ctx(brazos):
        metering_sample._seed_work_order_template_starters(dana)
        for code in ("sewer", "solar"):
            rows = list(
                work_tables.WorkOrderTemplate.objects.filter(tenant_id=brazos.id, service__code=code)
            )
            if not rows:
                continue  # this fixture's tenant does not sell it (BR-MET-003)
            assert all(row.is_gate is False for row in rows), code
            assert all(
                row.no_gate_reason == metering_sample.W6_NO_GATE_REASON[code] for row in rows
            ), code
            for row in rows:
                assert "BR-" not in (row.no_gate_reason or ""), "B14 rule 32"
        assert (
            work_tables.WorkOrderTemplate.objects.filter(
                tenant_id=brazos.id, service__code="storm_water"
            ).count()
            == 0
        )
    assert metering_sample.W6_NO_GATE_REASON["storm_water"] == "assessed from records, no visit"


def test_tc6_every_seeded_starter_is_served_by_the_list_endpoint(brazos, dana):
    """TC-6 · the gate's own question, asserted at ROW level here because
    `G101` can only read the code.

    Every row the seeder plants must come back from the list the screen reads.
    `G101` catches the queryset being narrowed between test runs; this catches
    the rows themselves.
    """
    with tenant_ctx(brazos):
        metering_sample._seed_work_order_template_starters(dana)
        planted = {
            str(row.pk)
            for row in work_tables.WorkOrderTemplate.objects.filter(tenant_id=brazos.id, is_sample=True)
        }
        served = {
            row["id"] for row in work_selectors.templates_page(per=500)["rows"]
        }
    assert planted, "the seeder plants something on this fixture"
    assert planted <= served, sorted(planted - served)


def test_tc5_two_tenants_seeded_share_no_row(brazos, lonestar, dana, erin):
    """TC-5 · tenant isolation — each tenant's own starters, no shared row."""
    with tenant_ctx(brazos):
        metering_sample._seed_work_order_template_starters(dana)
        brazos_ids = {
            str(row.pk)
            for row in work_tables.WorkOrderTemplate.objects.filter(tenant_id=brazos.id, is_sample=True)
        }
    with tenant_ctx(lonestar):
        metering_sample._seed_work_order_template_starters(erin)
        lone_ids = {
            str(row.pk)
            for row in work_tables.WorkOrderTemplate.objects.filter(tenant_id=lonestar.id, is_sample=True)
        }
        assert work_selectors.templates_page(per=500)["total"] == len(lone_ids)
    assert brazos_ids and lone_ids
    assert brazos_ids.isdisjoint(lone_ids)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-016/017/019@6b4ae156 (EP-WRK-03) · 10-execution-plan.md wave E tasks E1–E6 · J60 steps 6–11
# generated: 2026-09-05 by the CR-070 wave E build lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_us_wrk_016_019_builder.py · G101 (the structural half of BR-WRK-014)
# exceptions: E3 US-WRK-016 TC-3 (the review panel's *7 SECTIONS · 26 ITEMS*), TC-5 (the replaced page) and TC-7 (the Tailwind rule) are SCREEN cases and live in `src/features/work/TemplateBuilder.test.tsx` and `templateBuilderModel.test.ts` — no gate here reads rendered output (law 6) · E3 US-WRK-017 TC-3 (refresh at step 7 issues no request) and TC-7 (*We schedule it* stays disabled) are the wizard's own, in `NewConnectWizard.test.tsx`
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
