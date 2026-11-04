# ── Trace ──────────────────────────────────────────────
# Story:    US-AST-011 (capture and store consumption + export read records on
#           net-meter reads) · US-AST-012 (surface typed read records and hand
#           them to rating — quantities only)   Screens: S28 · S50 · S25 · S29
# Rules:    BR-AST-029 (net-meter reads are TWO records with a reading type;
#           export only on net assets; a missing export → 0-value record +
#           review flag; corrections are new rows) · BR-AST-010 (only
#           net_metering assets carry export) · BR-AST-025 (reads feed rating as
#           INPUTS ONLY — no credit is computed, stored or displayed here) ·
#           BR-MET-059 / B2 r8 (the channel model that GENERALIZED r7's
#           read_type) · CLAUDE.md rule 3 (every quantity carries its unit)
# ───────────────────────────────────────────────────────
"""US-AST-011/012, test case by test case.

READ THIS BEFORE CHANGING AN EXPECTATION. EP-AST-05 describes the export record
as `meter_reads.read_type = 'export'` (B2 addendum r7). **r8 supersedes r7** —
the database brief says so in its own words ("`read_type` (r7) GENERALIZES to
`channel`") and BR-MET-059 says it from the rules side — so the two-RECORD model
BR-AST-029 requires is implemented on `channel`, and `read_type` is served as a
DERIVED field so the US-AST-012 TC-3 contract keeps its pinned name. Every
behaviour BR-AST-029 states is asserted below; only the column it would have
lived in differs, and that difference is signed law, not a choice made here.
See apps/metering/models.py CHANNEL_EXPORT for the full reasoning.

NET-METERING CREDIT MATH IS NOT IN THIS FILE AND IS NOT MISSING FROM IT. The
netting method, bank unit, true-up month and avoided-cost rate are rating's
EP-RAT-06, gated by OQ-001, and v1 bills solar/battery as CAPACITY CHARGES.
These stories are capture, storage and hand-off, which BR-AST-029/025 say
outright are not blocked by that question. TC-4 asserts the absence of money
rather than leaving it to be noticed.
"""

from decimal import Decimal

import pytest

from apps.assets import services as asset_services
from apps.metering import models, selectors, services
from core import errors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    api_call,
    at,
    accept_warnings,
    commit_read,
    csv_body,
    seed_config,
    stage,
    tenant_ctx,
)

# §4 fixture: M-4021 (net, kWh) — Aug 3 register 42,864 / consumption 684 /
# export 120; Sep 3 CSV 702 / 141. M-4022 is water and NOT net (TC-4).
NET_HEADER = "meter_id,read_date,reading,read_type,service,flags\n"


def net_meter(actor, asset_no="M-4021", **kw):
    """A meter with `net_metering` on (BR-AST-010)."""
    asset = a_meter(actor, asset_no=asset_no, **kw)
    asset_services.update_asset(actor, asset["id"], {"net_metering": True})
    return asset


def net_csv(*rows: str) -> str:
    return NET_HEADER + "".join(row if row.endswith("\n") else row + "\n" for row in rows)


def post(actor, content):
    batch = stage(actor, content)
    services.validate_read_batch(actor, batch["id"])
    accept_warnings(actor, batch["id"])
    return services.commit_read_batch(actor, batch["id"], {"certified": True})


# ── US-AST-011 TC-2 — the S28 upload carries both records ───────────────────
@pytest.mark.django_db
def test_us_ast_011_tc2__a_read_type_column_posts_one_consumption_and_one_export_record(
    brazos, marcus
):
    """§4's Sep cycle: 702 delivered / 141 exported, same read_at.

    The file spells the column `read_type` and its values in B2 r7's vocabulary
    — which is exactly what a net-metering feed produces — and both land as the
    r8 channels they generalized into.
    """
    with tenant_ctx(brazos):
        seed_config()
        asset = net_meter(marcus)
        commit_read(marcus, asset["id"], day="2026-08-03", value="42864", consumption="684")
        post(
            marcus,
            net_csv(
                "M-4021,2026-09-03,43566,consumption,electric,",
                "M-4021,2026-09-03,141,export,electric,",
            ),
        )
        rows = {
            row.channel: row
            for row in models.MeterRead.objects.filter(
                asset_id=asset["id"], read_at=at("2026-09-03"), superseded_by_id__isnull=True
            )
        }
        assert set(rows) == {"total", "export"}  # TWO records, one read_at
        # 43,566 − 42,864 = 702.000000 kWh delivered (§4's figure).
        assert rows["total"].consumption == Decimal("702.000000")
        assert rows["export"].current_value == Decimal("141.000000")
        # Rule 3: EACH record carries its unit explicitly.
        assert rows["total"].unit == "kWh" and rows["export"].unit == "kWh"
        # ...and the derived record kind both stories name.
        assert selectors.read_type_of(rows["total"].channel) == "consumption"
        assert selectors.read_type_of(rows["export"].channel) == "export"


# ── US-AST-011 TC-4 (negative) — export on a non-net asset is refused ───────
@pytest.mark.django_db
def test_us_ast_011_tc4__an_export_record_on_a_non_net_asset_is_a_row_error(brazos, marcus):
    """BR-AST-029/BR-AST-010: never silently stored. M-4022 is a water meter
    with `net_metering` off, so the export row errors and is excluded."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, asset_no="M-4022", service="water", uom="kgal", unit_label="Unit W")
        batch = stage(marcus, net_csv("M-4022,2026-09-03,55,export,water,"))
        services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
        rules = {outcome["rule"]: outcome for outcome in (row.rule_outcomes or [])}
        assert "export_not_net" in rules
        assert rules["export_not_net"]["severity"] == "error"
        assert rules["export_not_net"]["detail"]["reason"] == "asset_is_not_net_metering"
        assert row.severity == "error"  # excluded by the wizard's per-row pattern


@pytest.mark.django_db
def test_us_ast_011_tc4b__the_error_holds_the_row_rather_than_posting_it(brazos, marcus):
    """BR-AST-010: an export figure on a meter that is not net-metered does not
    become a reading.

    ⚠ **AMENDED 2026-08-30 — BR-MET-940 (CR-054 task 14), IN PLACE.** The test
    was named `…blocks_the_commit_rather_than_posting_the_row` and asserted the
    batch-wide refusal:

        with pytest.raises(errors.BizError) as raised:
            services.commit_read_batch(marcus, batch["id"], {"certified": True})
        assert raised.value.message_key == "metering.read_batch.errors_need_resolution"

    The PO ruled that out (*"all or nothing will not work"*). The claim TC-4b
    actually makes — that the export row does not land — is unchanged, and it
    is the assertion that was already here and still is.
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, asset_no="M-4022", service="water", uom="kgal", unit_label="Unit W")
        batch = stage(marcus, net_csv("M-4022,2026-09-03,55,export,water,"))
        services.validate_read_batch(marcus, batch["id"])
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        assert result["posted_reads"] == 0 and result["held_reads"] == 1
        assert result["held_rows"][0]["reason"] == "unresolved_error"
        assert models.MeterRead.objects.filter(channel="export").count() == 0


# ── US-AST-011 TC-6 — a net cycle with no export record ─────────────────────
@pytest.mark.django_db
def test_us_ast_011_tc6__a_missing_export_becomes_a_zero_record_flagged_for_review(
    brazos, marcus, audit_rows
):
    """Not silence. A 0-value EXPORT record exists and says it is missing, so a
    net meter with no export feed is visible instead of reading as "exported
    nothing" downstream (BR-AST-029)."""
    with tenant_ctx(brazos):
        seed_config()
        asset = net_meter(marcus)
        commit_read(marcus, asset["id"], day="2026-08-03", value="42864", consumption="684")
        post(marcus, net_csv("M-4021,2026-09-03,43566,consumption,electric,"))
        export = models.MeterRead.objects.get(
            asset_id=asset["id"], read_at=at("2026-09-03"), channel="export"
        )
        assert export.consumption == Decimal("0.000000")
        assert export.current_value is None  # no register was supplied — none invented
        assert export.unit == "kWh"  # rule 3 even at zero
        assert export.status == "missing"  # the review flag
        assert export.rule_outcomes[0]["detail"]["br_ref"] == "BR-AST-029"
        assert "read.export_record_missing" in [row["action"] for row in audit_rows]


@pytest.mark.django_db
def test_us_ast_011_tc6b__a_non_net_meter_gets_no_phantom_export_record(brazos, marcus):
    """The complement — the 0-value record is a NET-METER rule, not a default."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        post(marcus, csv_body("M-7001,2026-09-03,43566,total,electric,"))
        assert models.MeterRead.objects.filter(channel="export").count() == 0


# ── US-AST-011 TC-8 (negative) — one export record per (asset, read_at) ─────
@pytest.mark.django_db
def test_us_ast_011_tc8__a_second_export_record_at_the_same_read_at_is_a_duplicate(brazos, marcus):
    """B2 r8's UNIQUE (asset, read_at, channel) over lineage heads. The
    correction path is a superseding row, never a second record."""
    with tenant_ctx(brazos):
        seed_config()
        asset = net_meter(marcus)
        commit_read(marcus, asset["id"], day="2026-08-03", value="42864", consumption="684")
        post(marcus, net_csv("M-4021,2026-09-03,141,export,electric,"))
        batch = stage(marcus, net_csv("M-4021,2026-09-03,155,export,electric,"))
        services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
        rules = {outcome["rule"] for outcome in (row.rule_outcomes or [])}
        assert "duplicate" in rules


# ── US-AST-012 TC-1/TC-2 — both records surface, as quantities ──────────────
@pytest.mark.django_db
def test_us_ast_012_tc1__the_reads_list_shows_two_typed_rows_and_the_drawer_links_the_pair(
    brazos, marcus
):
    with tenant_ctx(brazos):
        seed_config()
        asset = net_meter(marcus)
        commit_read(marcus, asset["id"], day="2026-08-03", value="42864", consumption="684")
        post(
            marcus,
            net_csv(
                "M-4021,2026-09-03,43566,consumption,electric,",
                "M-4021,2026-09-03,141,export,electric,",
            ),
        )
        listed = [
            selectors.read_dict(row)
            for row in selectors.read_list()
            if row.read_at == at("2026-09-03")
        ]
        kinds = {row["read_type"]: row for row in listed}
        assert set(kinds) == {"consumption", "export"}
        # Each row renders as a quantity WITH its unit — never money.
        assert kinds["consumption"]["usage_display"] == "702 kWh"
        assert kinds["export"]["unit"] == "kWh"
        # The drawer links a record to its pair (same asset, same read_at).
        export_row = models.MeterRead.objects.get(
            asset_id=asset["id"], read_at=at("2026-09-03"), channel="export"
        )
        assert selectors.paired_read_id(export_row) == kinds["consumption"]["id"]


# ── US-AST-012 TC-3 — the interface rating consumes ─────────────────────────
@pytest.mark.django_db
def test_us_ast_012_tc3__rating_receives_both_record_kinds_with_pinned_field_names(brazos, marcus):
    """The contract test the story asks for: field names pinned, `read_type`
    included, both kinds present, quantities carrying their unit."""
    with tenant_ctx(brazos):
        seed_config()
        asset = net_meter(marcus)
        commit_read(marcus, asset["id"], day="2026-08-03", value="42864", consumption="684")
        post(
            marcus,
            net_csv(
                "M-4021,2026-09-03,43566,consumption,electric,",
                "M-4021,2026-09-03,141,export,electric,",
            ),
        )
        rows = selectors.typed_reads_for_asset(
            asset["id"], period_start="2026-09-01", period_end="2026-09-30"
        )
        by_kind = {row["read_type"]: row for row in rows}
        assert set(by_kind) == {"consumption", "export"}
        assert by_kind["consumption"]["consumption"] == Decimal("702.000000")
        assert by_kind["consumption"]["unit"] == "kWh"
        assert by_kind["export"]["unit"] == "kWh"
        # The pinned field set — a rename downstream breaks here, on purpose.
        for row in rows:
            assert {"read_id", "read_type", "channel", "consumption", "unit"} <= set(row)


# ── US-AST-012 TC-4 (negative) — quantities only, no money anywhere ─────────
@pytest.mark.django_db
def test_us_ast_012_tc4__no_credit_amount_exists_on_any_surface_or_payload(brazos, marcus):
    """BR-AST-025: export renders as quantity + unit everywhere, never money.
    The credit math is EP-RAT-06 behind OQ-001 and v1 bills solar/battery as
    capacity charges — so there is nothing to display, and nothing pretends
    otherwise."""
    with tenant_ctx(brazos):
        seed_config()
        asset = net_meter(marcus)
        commit_read(marcus, asset["id"], day="2026-08-03", value="42864", consumption="684")
        post(marcus, net_csv("M-4021,2026-09-03,141,export,electric,"))
        payloads = selectors.typed_reads_for_asset(asset["id"]) + [
            selectors.read_dict(row) for row in selectors.read_list()
        ]
        for payload in payloads:
            for key in payload:
                assert key not in ("amount", "currency", "credit", "credit_amount", "rate")
        # ...and the module's read surfaces name no currency field at all.
        assert "currency" not in str(payloads).lower()


# ── US-AST-012 TC-5 (isolation) — records never cross tenants ───────────────
@pytest.mark.isolation
@pytest.mark.django_db
def test_us_ast_012_tc5__another_tenants_m4021_is_invisible_to_the_interface(
    brazos, marcus, lonestar, erin
):
    """§4: both tenants have an M-4021. Rating running for one must never see
    the other's records (US-AST-011 TC-7 is the same guarantee on ingest)."""
    with tenant_ctx(brazos):
        seed_config()
        theirs = net_meter(marcus)
        commit_read(marcus, theirs["id"], day="2026-08-03", value="42864", consumption="684")
        commit_read(
            marcus, theirs["id"], day="2026-08-03", value="120", channel="export", consumption="120"
        )
    with tenant_ctx(lonestar):
        seed_config()
        ours = net_meter(erin, asset_no="M-4021", service="water", uom="kgal", unit_label="Unit L")
        commit_read(erin, ours["id"], day="2026-08-03", value="312", consumption="312", unit="kgal")
        # Their asset id resolves to NOTHING under this scope, not to their rows.
        assert selectors.typed_reads_for_asset(theirs["id"]) == []
        mine = selectors.typed_reads_for_asset(ours["id"])
        assert [row["unit"] for row in mine] == ["kgal"]


# ── US-AST-011/012 — THE PAIR, as one payload a screen can draw ─────────────
#
# The surface-debt register named this exact gap on 2026-08-16: *"US-AST-011's
# net-metering import/export read PAIR — `apps/metering/validation.py` enforces
# the rule and `models.py` carries the channel, and no screen shows the two
# channels AS A PAIR, which is the whole point of the story."* The rule was
# enforced and invisible. These pin the read half of the surface that closes it.
@pytest.mark.django_db
def test_us_ast_012_tc1__net_meter_pair_returns_BOTH_sides_with_their_units(brazos, marcus):
    """§4's Aug cycle: 684 kWh delivered against 120 kWh exported, one read_at.

    Both sides, each carrying its own unit, and **no money and no netting**:
    subtracting one from the other IS the credit math, which is rating's
    EP-RAT-06 gated by OQ-001 (BR-AST-025).
    """
    with tenant_ctx(brazos):
        seed_config()
        asset = net_meter(marcus)
        imported = commit_read(
            marcus, asset["id"], day="2026-08-03", value="42864", consumption="684"
        )
        commit_read(
            marcus,
            asset["id"],
            day="2026-08-03",
            value="120",
            channel="export",
            consumption="120",
        )

        pair = selectors.net_meter_pair(imported)

        assert pair["is_net_meter"] is True
        assert pair["absent_reason"] is None
        # Rule 3 — each side is a quantity WITH its unit, composed by the server
        # so no screen has to invent a rendering (DEF-060).
        assert pair["consumption"]["usage_display"] == "684 kWh"
        assert pair["export"]["usage_display"] == "120 kWh"
        assert pair["consumption"]["read_type"] == "consumption"
        assert pair["export"]["read_type"] == "export"
        # BR-AST-025: no currency field of any kind, and no netted figure.
        flat = str(pair)
        for forbidden in ("currency", "amount", "credit", "USD", "564"):
            assert forbidden not in flat


@pytest.mark.django_db
def test_us_ast_012_tc1__the_pair_is_reachable_from_EITHER_side(brazos, marcus):
    """A clerk who opens the export row must see the same pair as one who opens
    the import row — otherwise "as a pair" depends on which row was clicked."""
    with tenant_ctx(brazos):
        seed_config()
        asset = net_meter(marcus)
        commit_read(marcus, asset["id"], day="2026-08-03", value="42864", consumption="684")
        exported = commit_read(
            marcus,
            asset["id"],
            day="2026-08-03",
            value="120",
            channel="export",
            consumption="120",
        )
        pair = selectors.net_meter_pair(exported)
        assert pair["consumption"]["usage_display"] == "684 kWh"
        assert pair["export"]["usage_display"] == "120 kWh"


@pytest.mark.django_db
def test_us_ast_012_tc4__a_flat_meter_gets_NO_pair_rather_than_a_zero_export(brazos, marcus):
    """The failure this avoids: every ordinary meter growing an "Export: 0" line
    that is not a measurement of anything (BR-AST-010 — only net assets carry
    export records)."""
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus, asset_no="M-7001")
        read = commit_read(marcus, asset["id"], day="2026-08-03", value="42864", consumption="684")
        pair = selectors.net_meter_pair(read)
        assert pair["is_net_meter"] is False
        assert pair["absent_reason"] == selectors.PAIR_NOT_NET_METER
        assert pair["export"] is None
        assert pair["consumption"] is None


@pytest.mark.django_db
def test_us_ast_012_tc1__a_net_cycle_with_no_export_record_SAYS_SO(brazos, marcus):
    """A net meter whose cycle carries no export record reports the ABSENCE by
    name. A 0 here would claim the customer exported nothing, which is a
    measurement nobody took (BR-RAT-021's discipline, applied to a display)."""
    with tenant_ctx(brazos):
        seed_config()
        asset = net_meter(marcus)
        read = commit_read(marcus, asset["id"], day="2026-08-03", value="42864", consumption="684")
        pair = selectors.net_meter_pair(read)
        assert pair["is_net_meter"] is True
        assert pair["absent_reason"] == selectors.PAIR_NO_EXPORT_RECORD
        assert pair["export"] is None
        assert pair["consumption"]["usage_display"] == "684 kWh"


@pytest.mark.django_db
def test_us_ast_012_tc1__the_read_endpoint_payload_carries_the_pair(brazos, marcus):
    """`GET /reads/{id}` is what the drawer fetches; the pair rides on it, so
    opening a solar customer's reading costs no second round trip."""
    from apps.metering import api as metering_api

    with tenant_ctx(brazos):
        seed_config()
        asset = net_meter(marcus)
        imported = commit_read(
            marcus, asset["id"], day="2026-08-03", value="42864", consumption="684"
        )
        commit_read(
            marcus,
            asset["id"],
            day="2026-08-03",
            value="120",
            channel="export",
            consumption="120",
        )
    response = api_call(
        metering_api.read_detail,
        "get",
        user=marcus.user,
        role="billing_clerk",
        tenant=brazos,
        read_id=str(imported.id),
    )
    assert response.status_code == 200
    assert response.data["net_pair"]["export"]["usage_display"] == "120 kWh"
    assert response.data["net_pair"]["consumption"]["usage_display"] == "684 kWh"
