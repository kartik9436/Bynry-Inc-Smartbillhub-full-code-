# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 5 tasks `P5.1`
#          (definition CRUD, copy on write) and `P5.2` (the four reserved
#          names refused BY NAME; a definition validated against its dataset).
#          Outcomes, verbatim: *"Editing a built-in creates a tenant copy; the
#          platform row is untouched"* and *"A definition naming an unknown
#          column is refused with the column named"*.
# Rules:   CLAUDE.md hard rule 1 · hard-won law 7 (prove a guard RED first, and
#          ask what would make it pass WRONGLY) · B14 rule 31
# Tests:   this file. ⚠ The ISOLATION and PRIVATE-BY-DEFAULT halves are NOT
#          here — they are `test_rep_p5_postgres_isolation.py`, which is
#          PostgreSQL only, because SQLite has no row-level security and a
#          probe there proves nothing and passes (`P5.6`/`P5.7`, law 14).
# ───────────────────────────────────────────────────────
"""Saving, changing and removing a report a utility wrote.

⚠ **NOT ONE `pytest.skip` IN THIS FILE, DELIBERATELY.** A skip that fires when
a fixture lacks something is a false pass: a sibling's case skipped silently
and its file reported green over the one assertion that mattered. Every case
here either runs or fails by name.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY**, asked of each before it was written:

  · the reserved-name case would pass over a builder that refuses EVERY name,
    so it saves a legal name in the same case and asserts that one worked;
  · the unknown-column case would pass over a refusal that names nothing, so it
    asserts the COLUMN is in `params` and not merely that a refusal happened —
    the outcome row says *"with the column named"* and a sentence a clerk reads
    interpolates `{{column}}` from `params`, so a name only in `detail` reaches
    nobody;
  · the copy-on-write case would pass over a builder that never wrote anything,
    so it asserts the NEW row exists, carries the tenant, and that the platform
    row's `updated_at` and name are unchanged.
"""

from __future__ import annotations

import pytest

from apps.reports import definitions as reports_definitions
from apps.reports.models import ReportDefinition

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _a_platform_report(key="ar_aging"):
    """One of the forty-six, read as the panel reads it. Seeded by `0003`."""
    row = ReportDefinition.objects.filter(tenant_id=None, key=key).first()
    assert row is not None, (
        f"the seed has no platform row {key!r} — reports/0003_seed_catalogue is "
        "what this whole phase copies FROM, so this is a red that names its own cause"
    )
    return row


# ═══════════════════════════════════════════════════════════════════════════
# P5.2 · THE FOUR RESERVED NAMES, REFUSED BY NAME
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("word", ["custom", "dashboard", "scheduled", "history"])
def test_a_reserved_name_is_refused_and_the_word_reaches_the_screen(brazos, dana, word):
    """⚠ **THE LITERAL WORD, NEVER AN INVENTED ONE.**

    An invented word proves nothing: it would pass over a builder that refuses
    any name containing an *h*. `history` is the case that bites — a utility
    naming a report *History* shadows the History tab and **the tab stops
    opening**, which is invisible until a real customer does it and then the
    product looks broken.
    """
    with tenant_ctx(brazos):
        with pytest.raises(reports_definitions.DefinitionRefused) as refused:
            reports_definitions.save(
                name=word.capitalize(),
                dataset="invoices",
                group_code="billing",
                owner_user_id=dana.id,
            )
    assert refused.value.message_key == "reports.definition.reserved_name"
    # The word reaches the clerk as a PARAMETER. `{{name}}` is what the
    # catalogue entry interpolates; a word only in the exception's text is a
    # word nobody ever sees (PO ruling 2026-08-19).
    assert refused.value.params["name"] == word
    assert ReportDefinition.objects.filter(tenant=brazos, key=word).count() == 0


def test_a_name_that_is_not_reserved_saves(brazos, dana):
    """The other direction, in the same breath — a refusal of everything is a
    refusal of nothing, and the parametrised case above cannot see that."""
    with tenant_ctx(brazos):
        saved = reports_definitions.save(
            name="Overdue 60+",
            dataset="invoices",
            group_code="billing",
            owner_user_id=dana.id,
        )
    assert saved.key == "overdue-60"
    assert saved.created is True


def test_the_tab_still_opens_after_a_utility_tries_to_name_a_report_history(brazos, dana):
    """`P5.2`'s real outcome, stated as the thing a clerk experiences.

    The refusal above is the mechanism; THIS is what it buys. After the attempt,
    no row holds the key `history`, so `/reports/history` is still the History
    tab's address and the tab still opens. Asserted as the absence of a row on
    that key rather than by mounting a router, because the router half is
    `reportsReservedSegments.test.tsx` and two checks asserting the same thing
    in two languages is how they come to disagree.
    """
    with tenant_ctx(brazos):
        with pytest.raises(reports_definitions.DefinitionRefused):
            reports_definitions.save(
                name="History", dataset="invoices", group_code="billing",
                owner_user_id=dana.id,
            )
        from apps.reports import runner

        assert not ReportDefinition.objects.filter(tenant=brazos, key="history").exists()
        # And no PLATFORM row holds it either, so `resolve` refuses the word
        # outright rather than serving something at the tab's address.
        with pytest.raises(runner.DefinitionNotFound):
            runner.resolve("history")


def test_the_reserved_list_matches_the_router(brazos):
    """The list lives in two languages and cannot be imported across.

    ⚠ This is the `fire` defect one size down (CLAUDE.md, B14 rule 2's worked
    case): a list typed by hand in two places does not fail loudly when they
    drift — the row exists, the API serves it, `tsc` passes, and the tab simply
    stops opening. So the two are asserted EQUAL here, against the front end's
    file read as text, which is the only link between them.
    """
    import pathlib
    import re

    source = (
        pathlib.Path(__file__).resolve().parents[2]
        / "07-frontend/src/features/reports/ReportsTabRoute.tsx"
    ).read_text(encoding="utf-8")
    declared = re.search(
        r"RESERVED_REPORT_SEGMENTS\s*=\s*\[([^\]]*)\]", source
    )
    assert declared, "the router no longer declares RESERVED_REPORT_SEGMENTS as a literal list"
    router_words = tuple(re.findall(r'"([a-z]+)"', declared.group(1)))
    assert router_words == reports_definitions.RESERVED_KEYS


# ═══════════════════════════════════════════════════════════════════════════
# P5.2 · A DEFINITION NAMES COLUMNS, NEVER SQL
# ═══════════════════════════════════════════════════════════════════════════
def test_an_unknown_column_is_refused_with_the_column_named(brazos, dana):
    """The outcome row, word for word: *"refused with the column named"*."""
    with tenant_ctx(brazos):
        with pytest.raises(reports_definitions.DefinitionRefused) as refused:
            reports_definitions.save(
                name="Bad columns",
                dataset="invoices",
                group_code="billing",
                columns=("invoice_no", "ballance"),
                owner_user_id=dana.id,
            )
    assert refused.value.message_key == "reports.definition.unknown_column"
    # NAMED. Not "a column is unknown" — the one a clerk typed.
    assert refused.value.params["column"] == "ballance"


def test_a_column_the_dataset_does_produce_is_accepted(brazos, dana):
    """The other direction — a validator that refuses every column would pass
    the case above and make the builder useless."""
    from apps.reports import datasets

    real = datasets.BY_CODE["invoices"].columns[0].name
    with tenant_ctx(brazos):
        saved = reports_definitions.save(
            name="Just one column",
            dataset="invoices",
            group_code="billing",
            columns=(real,),
            owner_user_id=dana.id,
        )
    assert saved.created is True


def test_an_unknown_filter_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(reports_definitions.DefinitionRefused) as refused:
            reports_definitions.save(
                name="Bad filter",
                dataset="invoices",
                group_code="billing",
                filters={"nonexistent_parameter": "x"},
                owner_user_id=dana.id,
            )
    assert refused.value.message_key == "reports.definition.unknown_column"


def test_an_unknown_dataset_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(reports_definitions.DefinitionRefused) as refused:
            reports_definitions.save(
                name="Nowhere", dataset="not_a_dataset", group_code="billing",
                owner_user_id=dana.id,
            )
    assert refused.value.message_key == "reports.definition.unknown_dataset"


# ═══════════════════════════════════════════════════════════════════════════
# THE UNLAWFUL TOTAL — THE BUILDER ROUTES *THROUGH* THE SIBLING'S REFUSAL
# ═══════════════════════════════════════════════════════════════════════════
def test_a_clerk_cannot_build_a_report_that_sums_a_balance_across_time(brazos, dana):
    """⚠ **THE ONE PLACE A UTILITY CAN REACH THE DEFECT A SIBLING SHIPPED THE
    REFUSAL FOR.**

    Three months' receivables of $41,220.00, $44,118.50 and $48,221.14 total
    $133,559.64 — a figure nobody owes, because a balance is a photograph and
    three photographs of the same debt are not three debts. The refusal exists
    on the render path; this asserts the BUILDER cannot express the thing in
    the first place, at SAVE, with the measure named.

    ⚠ It would have passed wrongly over a builder that refuses every grouping,
    so the next case groups the same dataset by something lawful and asserts it
    saves.
    """
    from apps.reports import datasets

    # A semi-additive measure — one that does not sum across TIME — on a
    # dataset that declares the time dimension. Found by asking the
    # declaration rather than by naming a column this test hopes still exists.
    candidates = [
        (ds.code, m.name)
        for ds in datasets.DATASETS
        for m in ds.measures
        if m.additivity == datasets.ADD_SEMI and datasets.DIM_TIME in m.forbidden_across
    ]
    assert candidates, (
        "no dataset declares a semi-additive measure any more — P0.16's whole "
        "subject has gone, and this case is a red that names its own cause"
    )
    dataset_code, measure_name = candidates[0]

    with tenant_ctx(brazos):
        with pytest.raises(reports_definitions.DefinitionRefused) as refused:
            reports_definitions.save(
                name="Debt by month",
                dataset=dataset_code,
                group_code="receivables",
                columns=(measure_name,),
                group_by=("accounting_period",),
                owner_user_id=dana.id,
            )
    assert refused.value.message_key == "reports.definition.unlawful_total"
    # NAMED, for the reason the unknown column is named.
    assert refused.value.params["measure"] == measure_name


# ═══════════════════════════════════════════════════════════════════════════
# P5.1 · COPY ON WRITE
# ═══════════════════════════════════════════════════════════════════════════
def test_saving_over_a_built_in_creates_a_tenant_row_and_leaves_ours_alone(brazos, dana):
    """`P5.1`'s outcome: *"Editing a built-in creates a tenant copy; the
    platform row is untouched."*"""
    platform = _a_platform_report()
    before_name, before_updated = platform.name, platform.updated_at

    with tenant_ctx(brazos):
        saved = reports_definitions.save(
            name="90+ on route R-01",
            dataset=platform.dataset,
            group_code=platform.group_code,
            sub_group_code=platform.sub_group_code,
            columns=tuple(platform.columns or ()),
            filters=dict(platform.filters or {}),
            owner_user_id=dana.id,
            based_on=platform.key,
        )

    copy = ReportDefinition.objects.get(id=saved.id)
    assert copy.tenant_id == brazos.id
    assert copy.key != platform.key
    assert saved.based_on == platform.key

    platform.refresh_from_db()
    assert platform.name == before_name
    assert platform.updated_at == before_updated
    assert platform.tenant_id is None


def test_a_platform_row_is_never_updated_in_place(brazos, dana):
    """The PATCH path, asked the question the POST path answers by copying.

    ⚠ It is refused rather than quietly redirected into a copy: the policy
    would make the UPDATE a silent no-op, and a screen that reaches here has a
    bug worth seeing.
    """
    platform = _a_platform_report()
    with tenant_ctx(brazos):
        with pytest.raises(reports_definitions.DefinitionRefused) as refused:
            reports_definitions.update(platform.id, name="Ours now", actor_user_id=dana.id)
    assert refused.value.message_key == "reports.definition.built_in_is_copied"
    platform.refresh_from_db()
    assert platform.name != "Ours now"


def test_a_platform_row_is_never_deleted(brazos, dana):
    platform = _a_platform_report()
    with tenant_ctx(brazos):
        with pytest.raises(reports_definitions.DefinitionRefused) as refused:
            reports_definitions.delete(platform.id, actor_user_id=dana.id)
    assert refused.value.message_key == "reports.definition.built_in_is_kept"
    assert ReportDefinition.objects.filter(id=platform.id).exists()


# ═══════════════════════════════════════════════════════════════════════════
# P5.1 · UPDATE AND DELETE OF A ROW THIS TENANT OWNS
# ═══════════════════════════════════════════════════════════════════════════
def test_a_tenant_row_updates_renames_and_deletes(brazos, dana):
    with tenant_ctx(brazos):
        saved = reports_definitions.save(
            name="Mine to change", dataset="invoices", group_code="billing",
            owner_user_id=dana.id,
        )
        renamed = reports_definitions.update(
            saved.id, name="Renamed", actor_user_id=dana.id
        )
        assert renamed.name == "Renamed"
        # ⚠ THE KEY DOES NOT MOVE. A colleague's bookmark still opens it —
        # the NAME is what a person reads and the key is the address.
        assert renamed.key == saved.key

        removed = reports_definitions.delete(saved.id, actor_user_id=dana.id)
        assert removed == saved.key
        assert not ReportDefinition.objects.filter(id=saved.id).exists()


def test_two_saves_of_one_name_get_two_addresses(brazos, dana):
    """A clerk saving *Overdue 60+* twice gets two reports, not a refusal.

    The second key is the server's to compute, which is why the reply carries
    the key: a screen that guessed the address from the name would navigate to
    the FIRST report after saving the second (p23's DOORS row — *"a save that
    gives no sign of where the thing went is how a clerk saves the same report
    three times"*).
    """
    with tenant_ctx(brazos):
        first = reports_definitions.save(
            name="Overdue 60+", dataset="invoices", group_code="billing",
            owner_user_id=dana.id,
        )
        second = reports_definitions.save(
            name="Overdue 60+", dataset="invoices", group_code="billing",
            owner_user_id=dana.id,
        )
    assert first.key == "overdue-60"
    assert second.key == "overdue-60-2"


def test_an_empty_name_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(reports_definitions.DefinitionRefused) as refused:
            reports_definitions.save(
                name="   ", dataset="invoices", group_code="billing",
                owner_user_id=dana.id,
            )
    assert refused.value.message_key == "reports.definition.name_required"


def test_a_name_that_folds_to_nothing_is_refused_rather_than_colliding(brazos, dana):
    """⚠ Every Korean or Japanese name would otherwise slug to the empty
    string, and every such report at a utility would collide on one key."""
    with tenant_ctx(brazos):
        with pytest.raises(reports_definitions.DefinitionRefused) as refused:
            reports_definitions.save(
                name="연체", dataset="invoices", group_code="billing",
                owner_user_id=dana.id,
            )
    assert refused.value.message_key == "reports.definition.name_unusable"


# ═══════════════════════════════════════════════════════════════════════════
# P5.7 · PRIVATE BY DEFAULT — the VALUE half. The VISIBILITY half is Postgres.
# ═══════════════════════════════════════════════════════════════════════════
def test_a_saved_report_is_private_unless_the_clerk_says_otherwise(brazos, dana):
    """`BR-REP-019`. ⚠ The COLUMN defaults to `shared`, which is right for the
    forty-six rows we ship and wrong for a person's own save — so this asserts
    the SERVICE's default and would go red the day somebody "simplifies" it
    down to the column's."""
    with tenant_ctx(brazos):
        saved = reports_definitions.save(
            name="Half finished", dataset="invoices", group_code="billing",
            owner_user_id=dana.id,
        )
    assert saved.visibility == "private"
    assert ReportDefinition.objects.get(id=saved.id).visibility == "private"


def test_sharing_is_an_explicit_act(brazos, dana):
    with tenant_ctx(brazos):
        saved = reports_definitions.save(
            name="Board arrears pack", dataset="invoices", group_code="billing",
            owner_user_id=dana.id,
        )
        shared = reports_definitions.update(
            saved.id, visibility="shared", actor_user_id=dana.id
        )
    assert shared.visibility == "shared"


def test_an_unknown_visibility_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(reports_definitions.DefinitionRefused) as refused:
            reports_definitions.save(
                name="Odd", dataset="invoices", group_code="billing",
                visibility="everyone_everywhere", owner_user_id=dana.id,
            )
    assert refused.value.message_key == "reports.definition.unknown_visibility"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 5 `P5.1`/`P5.2` (05-prototype/09 Reports Build Brief.pdf p16-p17, p31-p33, p35, read as IMAGES per B14 rule 42)
# screens: 2·2 · 2·4
# generated: 2026-09-27 by lane REP-P5
# gates: RED PROVED FIRST — every case in this file was run against the branch BEFORE `apps/reports/definitions.py` existed and every one failed at collection with `ModuleNotFoundError: No module named 'apps.reports.definitions'`, quoted in the lane report
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
