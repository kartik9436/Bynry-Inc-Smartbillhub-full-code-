# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-013 (S29 read detail drawer — override & DISPUTE) ·
#           US-MET-019 (S25 Needs-attention landing — the Disputed chip and its
#           TC-4 drill-in)   Screens: S25 · S29
# Rules:    BR-MET-024 (Dispute records a marker + reason on the read and feeds
#           the S25 disputes count; v1 flow per the OQ-043 closure — record +
#           flag, and the account is HELD from the bill run until a System Admin
#           clears the dispute) · BR-MET-016 (consumers resolve lineage HEADS) ·
#           BR-MET-053 (a BILLED read is locked; corrections SUPERSEDE and the
#           dispute marker is an ORTHOGONAL marker in that same rule) ·
#           BR-MET-035 (server-enforced roles) · CLAUDE.md rule 3 (a quantity
#           carries its unit) · rule 7 (every action writes audit_log)
# Journeys: J2 (reads → billing handoff — a held account never reaches the run)
# ───────────────────────────────────────────────────────
"""US-MET-013 TC-3 and US-MET-019 TC-4, test case by test case.

WHAT WAS BROKEN AND WHAT THESE TESTS PIN. DEF-046's first finding, verbatim:
*"meter_reads carries disputed_at/dispute_reason/disputed_by,
needs_attention_counts COUNTS disputes, and NO service or route ever sets one --
the chip can only ever read zero."* Three columns, a counter and a KPI chip, and
no way for any human to raise one. The tests below are written against the three
acts OQ-043's closure signs — **record**, **hold**, **clear** — and the
load-bearing one is the hold: `test_..._tc3c` asserts that a disputed read stops
the account being billed, because a disputed read that bills as though it were
agreed is the actual cost of the gap, not the empty chip.

✅ **WHAT A DISPUTE DOES TO A BILL THE READ ALREADY PRICED IS RULED —
BR-MET-133, PO 2026-08-26, CLOSING OQ-245.** This paragraph used to say the
question was open and that the tests deliberately asserted nothing about it.
Verbatim: *"Bill stands, resolution through the billed-correction door, and the
disputed amount doesn't age into late fees while open"*. The tests here still
assert only metering's half — the marker, the hold, the untouched invoice and
the SENTENCE the product now says (`billed_bill_effect` =
`issued_bill_stands_br_met_133`). Clause 4's arithmetic is billing's and is
proven in `tests/test_br_met_133_dispute_ageing.py`; the disputed AMOUNT it
needs is recorded nowhere and is **OQ-420**, refused rather than defaulted.
"""

from decimal import Decimal

import pytest

from apps.metering import selectors, services
from core import errors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    at,
    commit_read,
    seed_config,
    tenant_ctx,
)

# US-MET-019 §4's own fixture: M-7333 · Aug 2 · "customer reports vacant since
# July" — the one disputed read the Needs-attention seed carries, and the one
# the demo-tenant spec asks for so the chip renders a 1 rather than a 0.
DISPUTED_METER = "M-7333"
DISPUTE_REASON = "customer reports vacant since July"


def a_committed_read(actor, *, asset_no=DISPUTED_METER, channel="total", value="42864"):
    """One committed head with a real prior, so `usage_display` is a real
    quantity with a real unit rather than a None the assertions could not see.

    Returns the meter's own UNIT id alongside, because the hold billing reads is
    keyed on the unit (`dispute_holds_for_unit`) — the asset payload serves it
    as `assigned_unit_id`, which is the assignment's answer rather than a field
    on the asset."""
    seed_config()
    asset = a_meter(actor, asset_no=asset_no)
    commit_read(actor, asset["id"], day="2026-07-03", value="42180", channel=channel)
    read = commit_read(
        actor,
        asset["id"],
        day="2026-08-02",
        value=value,
        channel=channel,
        prior_value="42180",
        consumption="684.000000",
        days_since_prior=30,
    )
    return asset, read


def unit_of(asset):
    return asset["assigned_unit_id"]


def _audit_actions(rows, action: str) -> int:
    return len([row for row in rows if row["action"] == action])


# ── TC-3 — the dispute is RECORDED, and nothing else moves ──────────────────
@pytest.mark.django_db
def test_us_met_013_tc3__dispute_stores_marker_reason_and_actor_and_changes_no_value(
    brazos, marcus, audit_rows
):
    """TC-3, verbatim: *"Dispute marker + reason stored; S25 header dispute count
    and the Disputed KPI chip (US-MET-019) increment; audit row; no value
    change"*."""
    with tenant_ctx(brazos):
        _asset, read = a_committed_read(marcus)
        assert selectors.needs_attention_counts()["disputed"] == 0  # DEF-046's zero

        result = services.dispute_read(marcus, read.id, {"reason": DISPUTE_REASON})

        read.refresh_from_db()
        assert read.disputed_at is not None
        assert read.dispute_reason == DISPUTE_REASON
        assert str(read.disputed_by_id) == str(marcus.id)
        assert read.dispute_cleared_at is None
        # "no value change" — the measurement is exactly what the meter said.
        assert read.current_value == Decimal("42864")
        assert read.consumption == Decimal("684.000000")
        assert read.unit == "kWh"
        assert read.status == "ok"
        # The chip can now read something other than zero (DEF-046 closed).
        assert selectors.needs_attention_counts()["disputed"] == 1
        # The payload a screen renders.
        assert result["dispute"]["disputed"] is True
        assert result["dispute"]["holds_bill_run"] is True
        assert result["dispute"]["dispute_reason"] == DISPUTE_REASON
        # rule 7 — the money-adjacent action wrote its trail.
        assert _audit_actions(audit_rows, "read.disputed") == 1
        trail = [row for row in audit_rows if row["action"] == "read.disputed"][0]
        # rule 3: the trail records WHAT was disputed, never a bare number.
        assert trail["after"]["usage_display"] == "684 kWh"


@pytest.mark.django_db
def test_us_met_013_tc3b__a_dispute_without_a_reason_is_refused_and_writes_nothing(
    brazos, marcus, audit_rows
):
    """BR-MET-024 stores a REASON. A marker with none tells the System Admin who
    has to clear it nothing at all, so it is refused rather than stored blank."""
    with tenant_ctx(brazos):
        _asset, read = a_committed_read(marcus)
        with pytest.raises(errors.ValidationError):
            services.dispute_read(marcus, read.id, {"reason": "   "})
        read.refresh_from_db()
        assert read.disputed_at is None
        assert _audit_actions(audit_rows, "read.disputed") == 0


@pytest.mark.django_db
def test_us_met_013_tc3c__a_disputed_read_holds_the_account_out_of_the_bill_run(brazos, marcus):
    """THE POINT OF THE WHOLE STORY (OQ-043 closure): *"the account is HELD from
    the bill run until a System Admin clears the dispute"*.

    Asserted at metering's own seam — `dispute_holds_for_unit` is what billing
    reads, and `apps/billing/runs.prepare_run` blocks on it (proved from the
    billing side in tests/test_us_bil_001_prepare.py's companion case)."""
    with tenant_ctx(brazos):
        asset, read = a_committed_read(marcus)
        unit_id = unit_of(asset)
        assert selectors.dispute_holds_for_unit(unit_id) == []

        services.dispute_read(marcus, read.id, {"reason": DISPUTE_REASON})

        holds = selectors.dispute_holds_for_unit(unit_id)
        assert len(holds) == 1
        assert holds[0]["meter"] == DISPUTED_METER
        assert holds[0]["dispute_reason"] == DISPUTE_REASON
        # rule 3 — the exception screen shows the quantity being argued about.
        assert holds[0]["usage_display"] == "684 kWh"


@pytest.mark.django_db
def test_us_met_013_tc3d__a_second_dispute_on_the_same_read_is_refused(brazos, marcus):
    """The account is already held and the first reason and actor are already
    recorded; a second marker could only overwrite them."""
    with tenant_ctx(brazos):
        _asset, read = a_committed_read(marcus)
        services.dispute_read(marcus, read.id, {"reason": DISPUTE_REASON})
        with pytest.raises(errors.BizError) as raised:
            services.dispute_read(marcus, read.id, {"reason": "second thoughts"})
        assert raised.value.code == errors.BIZ_STATE
        read.refresh_from_db()
        assert read.dispute_reason == DISPUTE_REASON  # the FIRST one survives


@pytest.mark.django_db
def test_us_met_013_tc3e__a_superseded_read_cannot_be_disputed(brazos, marcus):
    """BR-MET-016: consumers resolve HEADS. A marker on a closed version would
    hang a hold off a row no consumer ever looks at."""
    with tenant_ctx(brazos):
        _asset, v1 = a_committed_read(marcus)
        services.supersede_read(marcus, v1.id, {"value": "42876", "reason": "keying error"})
        with pytest.raises(errors.BizError) as raised:
            services.dispute_read(marcus, v1.id, {"reason": DISPUTE_REASON})
        assert raised.value.code == errors.BIZ_STATE


# ── The BILLED read: recorded, held, and BR-MET-133 named on the response ──
@pytest.mark.django_db
def test_us_met_013_tc3f__disputing_a_billed_read_records_and_names_br_met_133(
    brazos, marcus, audit_rows
):
    """The ORDINARY case — a customer disputes a reading because they got the
    bill. The signed half happens (marker + hold). The unsigned half is stated
    by name and nothing else: no credit, no late-fee pause, no correction."""
    with tenant_ctx(brazos):
        _asset, read = a_committed_read(marcus)
        assert services.mark_read_billed(read.id) is True
        read.refresh_from_db()
        assert read.lifecycle == "billed"

        result = services.dispute_read(marcus, read.id, {"reason": DISPUTE_REASON})

        read.refresh_from_db()
        # The BILLED lock is NOT weakened — the read is still billed and still
        # corrects only through the J6 door (BR-MET-053).
        assert read.lifecycle == "billed"
        with pytest.raises(errors.BizError) as raised:
            services.supersede_read(marcus, read.id, {"value": "42876", "reason": "x"})
        assert raised.value.code == errors.BIZ_LOCKED
        # The dispute is recorded and holds the NEXT run…
        assert result["dispute"]["disputed"] is True
        assert result["dispute"]["holds_bill_run"] is True
        # …and the product says, by name, what happens to the bill already
        # issued.
        #
        # ⚠ AMENDED 2026-08-26, with the supersession stamped rather than the
        # assertion deleted. This read `== services.DISPUTE_BILLED_UNRULED` and
        # `assert "oq_245" in …`, which was correct while OQ-245 was open — the
        # product's honest answer was "nobody has decided". BR-MET-133 decided
        # it, so a code still carrying `oq_245` would now be the product citing
        # a closed question at a clerk.
        assert result["dispute"]["billed_bill_effect"] == services.DISPUTE_BILLED_STANDS
        assert services.DISPUTE_BILLED_STANDS == "issued_bill_stands_br_met_133"
        assert "oq_245" not in services.DISPUTE_BILLED_STANDS
        trail = [row for row in audit_rows if row["action"] == "read.disputed"][0]
        assert trail["after"]["br_ref"] == "BR-MET-133"  # DEF-2377 — a machine field
        assert "open_question" not in trail["after"]


@pytest.mark.django_db
def test_us_met_013_tc3g__an_unbilled_dispute_states_no_billed_effect(brazos, marcus):
    """The BR-MET-133 sentence must not appear on a read no bill has used — it
    would be a statement about a bill that does not exist."""
    with tenant_ctx(brazos):
        _asset, read = a_committed_read(marcus)
        result = services.dispute_read(marcus, read.id, {"reason": DISPUTE_REASON})
        assert result["dispute"]["billed_bill_effect"] is None


# ── Clearing: System Admin only, and it releases the run ────────────────────
@pytest.mark.django_db
def test_us_met_013_tc3h__only_a_system_admin_clears_and_clearing_releases_the_hold(
    brazos, marcus, dana, audit_rows
):
    """OQ-043's closure names the role: *"hold account from run until SysAdmin
    clears"*. The clerk who raised it cannot lift it."""
    with tenant_ctx(brazos):
        asset, read = a_committed_read(marcus)
        services.dispute_read(marcus, read.id, {"reason": DISPUTE_REASON})

        with pytest.raises(errors.AuthError):
            services.clear_read_dispute(marcus, read.id, {})
        read.refresh_from_db()
        assert read.dispute_cleared_at is None
        assert selectors.dispute_holds_for_unit(unit_of(asset)) != []

        result = services.clear_read_dispute(
            dana, read.id, {"resolution": "field visit confirmed the register"}
        )
        read.refresh_from_db()
        assert read.dispute_cleared_at is not None
        assert str(read.dispute_cleared_by_id) == str(dana.id)
        assert result["dispute"]["disputed"] is False
        assert result["dispute"]["holds_bill_run"] is False
        # The account is back in the run.
        assert selectors.dispute_holds_for_unit(unit_of(asset)) == []
        assert selectors.needs_attention_counts()["disputed"] == 0
        assert _audit_actions(audit_rows, "read.dispute_cleared") == 1
        trail = [row for row in audit_rows if row["action"] == "read.dispute_cleared"][0]
        # The note has nowhere on the read to live (B2 r8 has no column), so it
        # lives in the trail — and the OUTCOME is `reading_stands`.
        #
        # ⚠ AMENDED 2026-08-26. This asserted `outcome is None` "because
        # OQ-245(c) has not said whether 'cleared' means upheld or rejected".
        # BR-MET-133 clause 3 says which: *"she is right → supersede + the money
        # correction it opens; she is wrong → clear the marker, the bill was
        # always correct"*. Clearing IS the second one. A null verdict now would
        # be the trail withholding a fact the rule states.
        assert trail["after"]["resolution"] == "field visit confirmed the register"
        assert trail["after"]["outcome"] == "reading_stands"
        assert trail["after"]["br_ref"] == "BR-MET-133"  # DEF-2377 — a machine field


@pytest.mark.django_db
def test_us_met_013_tc3i__clearing_a_read_with_no_active_dispute_is_refused(brazos, marcus, dana):
    with tenant_ctx(brazos):
        _asset, read = a_committed_read(marcus)
        with pytest.raises(errors.BizError) as raised:
            services.clear_read_dispute(dana, read.id, {})
        assert raised.value.code == errors.BIZ_STATE


# ── US-MET-019 TC-4 — the Disputed chip drills in ───────────────────────────
@pytest.mark.django_db
def test_us_met_019_tc4__the_disputed_chip_count_and_its_slice_reconcile(brazos, marcus, dana):
    """TC-4: *"Click Disputed → the 1 disputed read (M-7333) with reason, actor
    and hold state"*. The chip counted and had no slice until the `disputed`
    filter was declared — an undeclared `f.` param is IGNORED by BE-05, so the
    drill-in would have returned the WHOLE list looking like a filtered one."""
    with tenant_ctx(brazos):
        _asset, disputed = a_committed_read(marcus, asset_no=DISPUTED_METER)
        _asset2, quiet = a_committed_read(marcus, asset_no="M-7001")
        services.dispute_read(marcus, disputed.id, {"reason": DISPUTE_REASON})

        counts = selectors.needs_attention_counts()
        slice_ids = [str(row.id) for row in selectors.read_list(filters={"disputed": "true"})]
        assert counts["disputed"] == len(slice_ids) == 1
        assert slice_ids == [str(disputed.id)]
        assert str(quiet.id) not in slice_ids
        # `disputed` is in the declared vocabulary, so the endpoint passes it
        # through rather than dropping it on the floor.
        assert "disputed" in selectors.READ_FILTERS

        # A CLEARED dispute leaves the slice and the count together.
        services.clear_read_dispute(dana, disputed.id, {})
        assert selectors.needs_attention_counts()["disputed"] == 0
        assert list(selectors.read_list(filters={"disputed": "true"})) == []


@pytest.mark.django_db
def test_us_met_013_tc7__a_dispute_never_crosses_a_tenant(brazos, lonestar, marcus, erin):
    """TC-7's shape for this write: another tenant's read is NOT FOUND, and its
    holds and counts never mix (HR-1 — absent and forbidden read alike)."""
    with tenant_ctx(brazos):
        _asset, read = a_committed_read(marcus)
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            services.dispute_read(erin, read.id, {"reason": DISPUTE_REASON})
        assert selectors.needs_attention_counts()["disputed"] == 0
    with tenant_ctx(brazos):
        read.refresh_from_db()
        assert read.disputed_at is None
