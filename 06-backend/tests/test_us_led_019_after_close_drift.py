# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-019 (the captured-cost register — TC-8's after-close path,
#           RULED 2026-08-16) · US-LED-021 (the export section the correction
#           silently invalidates)   Screens: S73 · S42
# Rules:    BR-LED-034 (editable while the period is open; the AFTER-CLOSE half
#           ruled by the PO on 2026-08-16, OQ-203) · BR-LED-035 (void, never
#           delete) · BR-LED-036 (every edit and void audits, before/after) ·
#           BR-LED-004 (the export batch is recorded and IDEMPOTENT — a re-run
#           is blocked, which is the whole reason this warning has to exist) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money carries its
#           currency) · rule 7 (every money action audits)
# Tests:    this file
# Impacts:  apps/ledger/cost_capture.edit_supplier_invoice /
#           .void_supplier_invoice (the correction) · apps/ledger/exports.
#           stale_batches (the warning S42 renders)
# ───────────────────────────────────────────────────────
"""OQ-203's PRICE: the exported batch that no longer matches, named.

The PO closed OQ-203 on 2026-08-16 with **"Yes it can be corrected"** — a
captured supplier invoice is editable after its period closes, with a reason and
an audit row, rather than frozen.

**The consequence was accepted, not waved away.** The accounting export is
idempotent and a re-run is blocked (BR-LED-004), because a utility must never
receive one month twice. So a correction made AFTER a batch has left changes a
reconciliation the ERP already holds, with no second handover possible. The
registry row states the condition in as many words:

    "That drift must therefore be a NAMED, VISIBLE problem on the export screen
     — the utility has to be told which exported batch no longer matches, so a
     human can fix it at the ERP end. Building the edit without that warning
     would be worse than freezing it."

This file is the test of that sentence. It asserts the warning EXISTS, that it
names the batch, that it quotes **both** figures with their currency so the
person at the ERP end knows what to post, and — the case that would otherwise
turn the whole screen into noise — that a batch nobody corrected stays silent.

**Worked, on LE-14's own July:** batch `EXP-2607-QBO` carries a cost section of
**$51,902.50 USD**. Norma voids RS-2607-0192 (**$155.00**) in August as a
duplicate. The register now totals **$51,747.50 USD**, and S42 must say so
against that batch by name — a difference of **−$155.00 USD**.
"""

from decimal import Decimal

import pytest

from apps.ledger import cost_capture, exports
from apps.ledger import models as ledger_models

from tests.cost_of_service_fixtures import (
    EXPORTED_AT,
    JULY_END,
    JULY_START,
    VOIDED_AT,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    marcus,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_led_021_cost_export import july_captured_and_closed

pytestmark = pytest.mark.django_db

#: LE-14's cost section, and what it becomes when CI-4 is withdrawn.
JULY_COST_TOTAL = Decimal("51902.50")
CI4_AMOUNT = Decimal("155.00")
JULY_COST_AFTER_VOID = JULY_COST_TOTAL - CI4_AMOUNT  # 51,747.50


def _july_batch(tenant, clerk):
    """Nine captures, a closed July, and ONE handover to QuickBooks."""
    captured, admin = july_captured_and_closed(tenant, clerk)
    batch = exports.create_export_batch(
        admin,
        period_start=JULY_START,
        period_end=JULY_END,
        target=ledger_models.EXPORT_QBO,
        created_at=EXPORTED_AT,
    )
    return captured, admin, batch


def test_a_handed_over_month_nobody_corrected_raises_no_warning(brazos, marcus):
    """The case that decides whether this screen is usable at all.

    A warning that fires on every historical batch is a warning a finance
    officer learns to scroll past, and then the one that mattered scrolls past
    too. So: July exported, nothing touched afterwards, **no drift reported**.
    """
    with tenant_ctx(brazos):
        _july_batch(brazos, marcus)
        assert exports.stale_batches() == ()


def test_a_void_after_the_handover_names_the_batch_and_both_figures(brazos, marcus):
    """LE-14 → LE-13: **EXP-2607-QBO carried 51,902.50; the register now says
    51,747.50.** Both numbers, their currency, and the batch by name.

    Why both numbers and not a flag: the person who receives this warning has to
    go and post the difference by hand in QuickBooks. "This batch is stale"
    sends them hunting for a figure this product already knows.
    """
    with tenant_ctx(brazos):
        captured, _admin, batch = _july_batch(brazos, marcus)

        voided = cost_capture.void_supplier_invoice(
            marcus,
            captured["RS-2607-0192"]["id"],
            reason="duplicate of RS-2607-0175",
            voided_at=VOIDED_AT,
        )
        # The clerk is told at the point of correction, too — not only later on
        # a screen they may never open.
        assert voided["after_close"]["problem"] == cost_capture.EXPORT_ALREADY_HANDED_OVER
        assert [b["batch_id"] for b in voided["after_close"]["exported_batches"]] == [
            batch["batch_id"]
        ]

        (drift,) = exports.stale_batches()

    assert drift["problem"] == exports.BATCH_NO_LONGER_MATCHES
    assert drift["batch_id"] == batch["batch_id"]
    assert drift["target"] == ledger_models.EXPORT_QBO
    assert drift["period"] == [JULY_START.isoformat(), JULY_END.isoformat()]
    # Money, with its currency, on every figure (CLAUDE.md rule 2).
    assert drift["carried"] == JULY_COST_TOTAL
    assert drift["register_now"] == JULY_COST_AFTER_VOID
    assert drift["difference"] == -CI4_AMOUNT
    assert drift["currency"] == "USD"
    assert "cannot be re-run" in drift["detail"]
    assert "OQ-203" in drift["detail"]


def test_an_edit_after_the_handover_drifts_by_exactly_the_edit(brazos, marcus):
    """LE-13's first bullet, one month late: CI-3's **310.00 → 312.40** after
    July has already gone to the accountant is a **+2.40** difference the ERP
    does not have.

    The volume side does not move, which is the point of keeping the two
    columns apart — water still reads 9.00%.
    """
    with tenant_ctx(brazos):
        captured, _admin, batch = _july_batch(brazos, marcus)

        cost_capture.edit_supplier_invoice(
            marcus,
            captured["RS-2607-0175"]["id"],
            correction_reason="supplier re-issued RS-2607-0175 at 312.40",
            amount=Decimal("312.40"),
        )
        (drift,) = exports.stale_batches()

    assert drift["batch_no"] == batch["batch_no"]
    assert drift["carried"] == JULY_COST_TOTAL
    assert drift["register_now"] == JULY_COST_TOTAL + Decimal("2.40")
    assert drift["difference"] == Decimal("2.40")
    assert drift["currency"] == "USD"


def test_the_correction_is_in_the_append_only_trail_not_only_on_the_screen(
    brazos, marcus, audit_rows
):
    """CLAUDE.md rule 7 and BR-LED-036, at the one moment they matter most.

    A screen can be closed and forgotten. The audit row is the only artifact
    that can explain, six months later, why the ERP's July and this register's
    July disagree — so the reason and the batch it invalidated are written into
    it, not merely returned.
    """
    with tenant_ctx(brazos):
        captured, _admin, batch = _july_batch(brazos, marcus)
        audit_rows.clear()
        cost_capture.edit_supplier_invoice(
            marcus,
            captured["RS-2607-0141"]["id"],
            correction_reason="City of Rosenberg re-issued at the metered volume",
            amount=Decimal("1250.00"),
        )
        (row,) = [r for r in audit_rows if r["action"] == cost_capture.AUDIT_UPDATED]

    correction = row["after"]["after_close_correction"]
    assert correction["correction"] == cost_capture.AFTER_CLOSE_CORRECTION
    assert correction["reason"] == "City of Rosenberg re-issued at the metered volume"
    assert correction["problem"] == cost_capture.EXPORT_ALREADY_HANDED_OVER
    assert [b["batch_no"] for b in correction["exported_batches"]] == [batch["batch_no"]]


def test_a_correction_in_a_month_that_never_left_warns_about_no_batch(brazos, marcus):
    """Closed but never exported: the correction is still lawful and still
    audited, and there is **no batch to name**.

    The distinction is the whole value of the warning. "You corrected a closed
    month" is routine; "you corrected a month the accountant already has" is a
    job for a person, and the two must not read the same.
    """
    with tenant_ctx(brazos):
        captured, _admin = july_captured_and_closed(brazos, marcus)  # no export
        edited = cost_capture.edit_supplier_invoice(
            marcus,
            captured["RS-2607-0141"]["id"],
            correction_reason="keyed from the wrong invoice",
            amount=Decimal("1250.00"),
        )

    assert edited["after_close"]["correction"] == cost_capture.AFTER_CLOSE_CORRECTION
    assert edited["after_close"]["exported_batches"] == ()
    assert "problem" not in edited["after_close"]
    assert cost_capture.EXPORT_ALREADY_HANDED_OVER not in edited["problems"]


def test_isolation__one_tenants_drift_is_invisible_to_another(brazos, lonestar, marcus):
    """CLAUDE.md rule 1. Lone Star Ridge's export screen shows Lone Star Ridge's
    batches; Brazos Bend's corrected July is not one of them."""
    with tenant_ctx(brazos):
        captured, _admin, _batch = _july_batch(brazos, marcus)
        cost_capture.void_supplier_invoice(
            marcus,
            captured["RS-2607-0192"]["id"],
            reason="duplicate of RS-2607-0175",
            voided_at=VOIDED_AT,
        )
        assert len(exports.stale_batches()) == 1

    with tenant_ctx(lonestar):
        assert exports.stale_batches() == ()
        assert (
            exports.batches_covering(period_start=JULY_START, period_end=JULY_END) == ()
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-019@d744841 (the same sources cost_capture.py was authored
#          from, plus 12-governance/01-open-questions.md OQ-203 as CLOSED
#          2026-08-16 and 12-governance/02-decision-log.md's entry for it)
# generated: 2026-08-16 by the surface-debt tails lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — the ledger rows in
#            12-governance/09-human-review-ledger.md are the PO's to write)
# gates: PROVED RED BEFORE GREEN. With `stale_batches` returning `()` the two
#         drift tests failed on the unpack — `ValueError: not enough values to
#         unpack (expected 1, got 0)` — which is the exact defect the PO's
#         condition names: the correction happens and nothing tells anybody.
# ───────────────────────────────────────────────────────
