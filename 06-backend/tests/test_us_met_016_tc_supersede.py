# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-016 (supersede & correction flow — BILLED reads route to J6)
#           Screens: S25 · S29
# Rules:    BR-MET-053 (lifecycle staged → committed → BILLED(locked);
#           corrections = SUPERSEDE, never edit; billed-read error = supersede +
#           the automatic J6 correction path) · BR-MET-054 (update = supersede
#           only; delete = staged/rejected rows only) · BR-MET-056 (the drawer
#           shows the full chain) · CLAUDE.md rule 4 (financial immutability) ·
#           CLAUDE.md rule 1 (tenant scoping)
# Journeys: J6 (corrections — step 1's handoff starts from the row pair here)
# ───────────────────────────────────────────────────────
"""US-MET-016, test case by test case.

The load-bearing claim is TC-3/TC-4 together: a BILLED read has exactly ONE
door, and the plain supersede is not it. Everything else — the chain, the
channel scoping, the delete scope — is BR-MET-053/054 read literally.

TC-5 has two halves and they are proved in two places on purpose. The
SERVICE-layer half (no code path here edits a value) runs on any vendor; the
DATABASE half — metering 0007's `meter_reads_value_immutable` trigger — can only
run on Postgres, so it is marked @pytest.mark.isolation and skipped with a
vendor reason on the sqlite tier rather than faked.
"""

from decimal import Decimal

import pytest
from django.db import connection, transaction

from apps.metering import models, selectors, services
from core import errors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    at,
    commit_read,
    seed_config,
    tenant_ctx,
)

# §4 fixture: M-7001 · Aug 3 2026 · `total` · v1 42,864 (684.000000 kWh).
V1_REGISTER = "42864"
V2_REGISTER = "42876"  # "collector re-read — keying error"
V3_REGISTER = "42870"  # "field verification Aug 9"


def a_committed_read(actor, *, asset_no="M-7001", channel="total", value=V1_REGISTER, **kw):
    seed_config()
    asset = a_meter(actor, asset_no=asset_no, **kw)
    # The PRIOR cycle read the supersede recomputes against — §4's 42,180. A
    # supersede re-derives consumption from the asset's own history (BR-MET-022
    # re-runs the flag engine on the new head), so the history has to be real.
    commit_read(
        actor,
        asset["id"],
        day="2026-07-03",
        value="42180",
        channel=channel,
        consumption="0",
    )
    return asset, commit_read(
        actor,
        asset["id"],
        day="2026-08-03",
        value=value,
        channel=channel,
        prior_value="42180",
        consumption="684.000000",
        days_since_prior=30,
    )


def a_billed_read(actor, **kw):
    """The same read, after billing locked it (BR-MET-053 committed → BILLED).

    Set through the PUBLISHED service `mark_read_billed`, not by touching the
    column: that function is the seam billing will call, so exercising it here
    means the lock and the tests agree about how a read becomes billed.
    """
    asset, read = a_committed_read(actor, **kw)
    assert services.mark_read_billed(read.id) is True
    read.refresh_from_db()
    return asset, read


class _StubInvoice:
    """What billing's `invoice_or_404` + `invoice_row` hand back, in the shape
    the seam consumes. Billing's real selectors are wired (G20 resolves them);
    a stub is used only so this metering test does not have to build an issued
    invoice through the whole bill run to assert metering's own behaviour."""


@pytest.fixture()
def wired_invoice(monkeypatch):
    """Point the billing seam at a known invoice, and hand back its id."""
    invoice_id = "019f0000-0000-7000-8000-00000000b101"

    def _ref(_invoice_id):
        return {"id": str(_invoice_id), "invoice_no": "BL-2607-018201", "status": "issued"}

    monkeypatch.setattr(services.seams, "invoice_ref", _ref)
    return invoice_id


@pytest.fixture()
def dark_invoice_seam(monkeypatch):
    """Billing cannot answer — the seam REPORTS absence (never substitutes)."""
    monkeypatch.setattr(services.seams, "invoice_ref", lambda _id: None)


# ── TC-1 — supersede a committed (unbilled) read ────────────────────────────
@pytest.mark.django_db
def test_us_met_016_tc1__supersede_makes_a_new_head_and_keeps_the_original_visible(
    brazos, marcus, audit_rows
):
    with tenant_ctx(brazos):
        asset, v1 = a_committed_read(marcus)
        v2 = services.supersede_read(
            marcus, v1.id, {"value": V2_REGISTER, "reason": "collector re-read — keying error"}
        )
        v1.refresh_from_db()
        # The new row is the head; the old one is CLOSED, not edited away.
        assert str(v1.superseded_by_id) == v2["id"]
        assert v1.superseded_at is not None
        assert v1.current_value == Decimal(V1_REGISTER)  # untouched
        # 42,876 − 42,180 = 696.000000 kWh (§4's worked figure), with its unit.
        assert v2["consumption"] == "696.000000"
        assert v2["unit"] == "kWh"
        # The original is still fully readable in history (BR-MET-056).
        chain = selectors.read_chain(v2["id"])
        assert [Decimal(row["current_value"]) for row in chain] == [
            Decimal(V1_REGISTER),
            Decimal(V2_REGISTER),
        ]
        # ...and audited before → after.
        assert _audit_actions(audit_rows, "read.superseded") == 1


# ── TC-2 — v1 → v2 → v3, and consumers see only the head ────────────────────
@pytest.mark.django_db
def test_us_met_016_tc2__the_chain_renders_v1_v2_v3_and_consumers_see_the_head(brazos, marcus):
    with tenant_ctx(brazos):
        asset, v1 = a_committed_read(marcus)
        v2 = services.supersede_read(
            marcus, v1.id, {"value": V2_REGISTER, "reason": "collector re-read — keying error"}
        )
        v3 = services.supersede_read(
            marcus, v2["id"], {"value": V3_REGISTER, "reason": "field verification Aug 9"}
        )
        chain = selectors.read_chain(v1.id)
        assert [row["version"] for row in chain] == [1, 2, 3]
        assert [Decimal(row["current_value"]) for row in chain] == [
            Decimal(V1_REGISTER),
            Decimal(V2_REGISTER),
            Decimal(V3_REGISTER),
        ]
        # Every consumer resolves the head only — ONE row for that date, not
        # three (the Jul prior read is a separate lineage and still shows).
        heads = [row for row in selectors.read_list() if row.read_at == at("2026-08-03")]
        assert [str(row.id) for row in heads] == [v3["id"]]


# ── TC-3 — the BILLED read's correction, routed ─────────────────────────────
@pytest.mark.django_db
def test_us_met_016_tc3__a_billed_read_corrects_only_through_the_j6_flow(
    brazos, marcus, wired_invoice, audit_rows
):
    with tenant_ctx(brazos):
        asset, billed = a_billed_read(marcus, asset_no="M-7204")
        result = services.correct_billed_read(
            marcus,
            billed.id,
            {
                "value": V2_REGISTER,
                "reason": "meter tested — register misread",
                "invoice_id": wired_invoice,
            },
        )
        billed.refresh_from_db()
        # 1. the read half — a superseding row, the original closed and intact
        assert str(billed.superseded_by_id) == result["id"]
        assert billed.current_value == Decimal(V1_REGISTER)
        # 2. the money half — the linkage J6 step 1 consumes
        linkage = result["correction"]
        assert linkage["invoice_no"] == "BL-2607-018201"
        assert linkage["superseded_read_id"] == str(billed.id)
        assert linkage["superseding_read_id"] == result["id"]
        assert linkage["status"] == "open"
        # billing reads the same row by invoice (its J6 entry point)
        assert selectors.read_corrections_for_invoice(wired_invoice)[0]["id"] == linkage["id"]
        # 3. the trail links the pair to the invoice
        assert _audit_actions(audit_rows, "read.billed_correction_opened") == 1


@pytest.mark.django_db
def test_us_met_016_tc3b__metering_writes_no_invoice_and_no_money_field(
    brazos, marcus, wired_invoice
):
    """J6 step 1's contract: the original invoice is UNTOUCHED by metering."""
    with tenant_ctx(brazos):
        asset, billed = a_billed_read(marcus, asset_no="M-7204")
        result = services.correct_billed_read(
            marcus,
            billed.id,
            {"value": V2_REGISTER, "reason": "meter tested", "invoice_id": wired_invoice},
        )
    # No currency, no amount, nothing money-shaped anywhere in the payload.
    flat = str(result)
    for token in ("amount", "currency", "USD", "credit", "price"):
        assert token not in flat, f"metering payload names {token!r} — money is billing's (§7)"


# ── TC-4 (negative) — no bypass ─────────────────────────────────────────────
@pytest.mark.django_db
def test_us_met_016_tc4__plain_supersede_on_a_billed_read_is_refused(brazos, marcus):
    with tenant_ctx(brazos):
        asset, billed = a_billed_read(marcus, asset_no="M-7204")
        with pytest.raises(errors.BizError) as raised:
            services.supersede_read(marcus, billed.id, {"value": V2_REGISTER, "reason": "typo"})
    assert raised.value.br_ref == "BR-MET-053"
    assert raised.value.message_key == "metering.read.billed_correction_required"
    billed.refresh_from_db()
    assert billed.superseded_by_id is None  # nothing happened


@pytest.mark.django_db
def test_us_met_016_tc4b__the_correction_flow_refuses_an_unbilled_read(
    brazos, marcus, wired_invoice
):
    """The other half of the routing: an unbilled read has no money to fix, so
    opening a correction against an invoice would fabricate a money event."""
    with tenant_ctx(brazos):
        asset, committed = a_committed_read(marcus)
        with pytest.raises(errors.BizError) as raised:
            services.correct_billed_read(
                marcus,
                committed.id,
                {"value": V2_REGISTER, "reason": "typo", "invoice_id": wired_invoice},
            )
    assert raised.value.message_key == "metering.read.not_billed"
    assert models.ReadCorrection.objects.count() == 0


@pytest.mark.django_db
def test_us_met_016_tc4c__an_unresolvable_invoice_refuses_rather_than_linking_to_nothing(
    brazos, marcus, dark_invoice_seam
):
    """G20/DEF-075 posture: a seam that cannot answer must not be read as an
    answer. No linkage, no superseding row, nothing half-done."""
    with tenant_ctx(brazos):
        asset, billed = a_billed_read(marcus, asset_no="M-7204")
        with pytest.raises(errors.BizError) as raised:
            services.correct_billed_read(
                marcus,
                billed.id,
                {"value": V2_REGISTER, "reason": "meter tested", "invoice_id": "unknown"},
            )
        assert raised.value.message_key == "metering.read.invoice_unresolvable"
        assert models.ReadCorrection.objects.count() == 0
        billed.refresh_from_db()
        assert billed.superseded_by_id is None


# ── TC-5 (negative) — no edit, no delete ────────────────────────────────────
@pytest.mark.django_db
def test_us_met_016_tc5__no_service_path_edits_a_committed_value(brazos, marcus):
    """The service-layer half: every correction route produces a NEW row."""
    with tenant_ctx(brazos):
        asset, v1 = a_committed_read(marcus)
        before = models.MeterRead.objects.count()
        services.supersede_read(marcus, v1.id, {"value": V2_REGISTER, "reason": "re-read"})
        assert models.MeterRead.objects.count() == before + 1  # added, never replaced


@pytest.mark.isolation
@pytest.mark.django_db
def test_us_met_016_tc5b__the_database_itself_refuses_to_edit_a_committed_value(brazos, marcus):
    """The DATABASE half — metering 0007's trigger, which is what makes TC-5 a
    guarantee rather than a convention. Postgres only: the sqlite test tier has
    no trigger, and saying so is better than pretending."""
    if connection.vendor != "postgresql":
        pytest.skip("vendor sqlite — the immutability trigger is Postgres DDL (metering 0007)")
    with tenant_ctx(brazos):
        asset, v1 = a_committed_read(marcus)
        # Each probe runs in its OWN savepoint: a statement the trigger refuses
        # poisons the surrounding transaction, so without one the second probe
        # would report Django's "you can't execute queries" rather than the
        # refusal under test.
        assert "immutable" in _refused(
            lambda: models.MeterRead.objects.filter(id=v1.id, read_at=v1.read_at).update(
                current_value=Decimal("99999")
            )
        )
        assert "append-only" in _refused(
            lambda: models.MeterRead.objects.filter(id=v1.id, read_at=v1.read_at).delete()
        )


def _refused(operation) -> str:
    """Run `operation` in a savepoint, return the refusal text, leave the
    surrounding transaction usable."""
    try:
        with transaction.atomic():
            operation()
    except Exception as refusal:  # noqa: BLE001 - the message IS the assertion
        return str(refusal).lower()
    raise AssertionError("the database accepted a statement it must refuse")


@pytest.mark.isolation
@pytest.mark.django_db
def test_us_met_016_tc5c__the_trigger_still_allows_the_two_closure_columns(brazos, marcus):
    """The narrowing metering 0007 documents, asserted: the closure columns B2
    r8 names and the BILLED lifecycle transition must still move, or the rule
    that requires them could not be implemented at all."""
    if connection.vendor != "postgresql":
        pytest.skip("vendor sqlite — the immutability trigger is Postgres DDL (metering 0007)")
    with tenant_ctx(brazos):
        asset, v1 = a_committed_read(marcus)
        services.supersede_read(marcus, v1.id, {"value": V2_REGISTER, "reason": "re-read"})
        assert services.mark_read_billed(v1.id) is False  # already superseded head is closed
        head = selectors._read_heads().first()
        assert services.mark_read_billed(head.id) is True


# ── TC-6 — the delete scope, and only that ──────────────────────────────────
@pytest.mark.django_db
def test_us_met_016_tc6__delete_reaches_staged_rows_only(brazos, marcus, audit_rows):
    from tests.test_us_met_reads_helpers import csv_body, stage

    with tenant_ctx(brazos):
        asset, _ = a_committed_read(marcus, asset_no="M-7301")
        batch = stage(marcus, csv_body("M-7301,2026-09-03,43100,total,electric,"))
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
        result = services.delete_staged_read_row(marcus, row.id)
        assert result["deleted"] is True
        assert models.ReadImportRow.objects.filter(id=row.id).count() == 0
        # ...and the batch itself survives with its compliance stamp (BR-MET-012/017).
        assert models.ReadImportBatch.objects.filter(id=batch["id"]).count() == 1
        assert _audit_actions(audit_rows, "read_row.deleted") == 1


@pytest.mark.django_db
def test_us_met_016_tc6b__there_is_no_delete_path_for_a_committed_read(brazos, marcus):
    """Not "it is refused" — it does not EXIST. The module publishes no
    delete-a-read function and the API declares no such route."""
    assert not hasattr(services, "delete_read")
    from apps.metering import api

    routes = [str(entry.pattern) for entry in api.urlpatterns]
    assert not any(route.endswith("/delete") and "reads/" in route for route in routes)


# ── TC-7 (negative) — a reason is not optional ──────────────────────────────
@pytest.mark.django_db
def test_us_met_016_tc7__a_supersede_without_a_reason_writes_nothing(
    brazos, marcus, wired_invoice, audit_rows
):
    with tenant_ctx(brazos):
        asset, v1 = a_committed_read(marcus)
        before = models.MeterRead.objects.count()
        with pytest.raises(errors.ValidationError):
            services.supersede_read(marcus, v1.id, {"value": V2_REGISTER})
        assert models.MeterRead.objects.count() == before
        assert _audit_actions(audit_rows, "read.superseded") == 0
        asset2, billed = a_billed_read(marcus, asset_no="M-7205")
        with pytest.raises(errors.ValidationError):
            services.correct_billed_read(
                marcus, billed.id, {"value": V2_REGISTER, "invoice_id": wired_invoice}
            )
        assert models.ReadCorrection.objects.count() == 0


# ── TC-8 — one channel lineage, not four ────────────────────────────────────
@pytest.mark.django_db
def test_us_met_016_tc8__a_channel_scoped_supersede_touches_one_lineage(brazos, marcus):
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus, asset_no="M-7450")
        for channel, value in (("tou_on", "13210"), ("tou_mid", "8100"), ("tou_off", "5400")):
            commit_read(
                marcus,
                asset["id"],
                day="2026-08-03",
                value=value,
                channel=channel,
                prior_value="13009" if channel == "tou_on" else "8000",
                consumption="201.000000",
            )
        target = models.MeterRead.objects.get(channel="tou_on", superseded_by_id__isnull=True)
        services.supersede_read(marcus, target.id, {"value": "13201", "reason": "field verify"})
        closed = models.MeterRead.objects.filter(superseded_by_id__isnull=False)
        assert [row.channel for row in closed] == ["tou_on"]
        untouched = models.MeterRead.objects.filter(
            channel__in=("tou_mid", "tou_off"), superseded_by_id__isnull=True
        )
        assert untouched.count() == 2


# ── TC-9 (isolation) — chains and linkages never cross ──────────────────────
@pytest.mark.isolation
@pytest.mark.django_db
def test_us_met_016_tc9__another_tenant_cannot_see_or_supersede_the_chain(
    brazos, marcus, lonestar, erin
):
    with tenant_ctx(brazos):
        asset, v1 = a_committed_read(marcus)
        services.supersede_read(marcus, v1.id, {"value": V2_REGISTER, "reason": "re-read"})
    with tenant_ctx(lonestar):
        # The chain is not merely refused — it is ABSENT under this scope (HR-1).
        assert selectors.read_chain(v1.id) == []
        with pytest.raises(errors.NotFoundError):
            services.supersede_read(erin, v1.id, {"value": "1", "reason": "probe"})


@pytest.mark.isolation
@pytest.mark.django_db
def test_us_met_016_tc9b__correction_linkages_never_cross_tenants(
    brazos, marcus, lonestar, erin, wired_invoice
):
    with tenant_ctx(brazos):
        asset, billed = a_billed_read(marcus, asset_no="M-7204")
        services.correct_billed_read(
            marcus,
            billed.id,
            {"value": V2_REGISTER, "reason": "meter tested", "invoice_id": wired_invoice},
        )
    with tenant_ctx(lonestar):
        assert selectors.read_corrections_for_invoice(wired_invoice) == []
        assert selectors.read_corrections_for_read(billed.id) == []


# ── DEF-079: the assets delete gate can finally count reads ─────────────────
@pytest.mark.django_db
def test_us_met_016_def079__read_count_for_asset_answers_instead_of_substituting_zero(
    brazos, marcus
):
    """The seam `apps/assets/seams.py` documented and nobody wrote. While it was
    dark its caller substituted 0, so an asset carrying reads read as
    unreferenced to the BR-AST-013 delete gate."""
    from apps.assets import seams as asset_seams

    with tenant_ctx(brazos):
        asset, read = a_committed_read(marcus)  # a Jul read and an Aug read
        assert services.read_count_for_asset(asset["id"]) == 2
        assert asset_seams.read_count_for_asset(asset["id"]) == 2
        # a corrected read is still a read — every version counts for the gate
        services.supersede_read(marcus, read.id, {"value": V2_REGISTER, "reason": "re-read"})
        assert asset_seams.read_count_for_asset(asset["id"]) == 3


def _audit_actions(rows, action: str) -> int:
    """How many times the trail recorded `action`.

    Counted off the BE-03 capture sink the reads fixtures install (the autouse
    `audit_rows` fixture), not off `audit_log` — that sink IS the write path
    under test, so counting what reached it is counting what the service wrote.
    """
    return len([row for row in rows if row["action"] == action])
