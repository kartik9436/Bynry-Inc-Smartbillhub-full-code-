# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-004 (Settings → Notifications tab: the delivery/dispatch home
#           — the CONFIG half)   Screens: S8
# Rules:    BR-TEN-041 (#8 the Notifications tab IS the dispatch home) ·
#           BR-NOT-005 (batch size/cadence tenant-config) · BR-BIL-016 (seeded
#           500) · BR-NOT-009 (quiet hours 08:00–21:00 tenant time) ·
#           BR-NOT-010 (email W6 · SMS v1.1 badges) · BR-TEN-016 (the edit is
#           audited before→after) · BR-IDN-009 (server-enforced role gating) ·
#           CLAUDE.md rule 7
# ───────────────────────────────────────────────────────
"""The dispatch home's config half: what it seeds, what it refuses, what it audits.

TC-5 and TC-6 are the two a passing suite could most easily fake — a role gate
that is only in the UI, and a validation that is only in the service — so the
role refusal is asserted at the SERVICE (which every endpoint, job and shell
goes through) and the batch-size floor is asserted twice, once in the service
and once at the database.

TC-3 (the provider-status readout) lives in
`test_us_not_003_channel_routing.py`, where the seam that answers it does; TC-7
(isolation) is `test_us_not_004_dispatch_config_isolation.py`.
"""

from __future__ import annotations

from datetime import time

import pytest
from django.db import IntegrityError, transaction

from apps.notifications import dispatch_config, models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


# ── the seeded defaults are the RATIFIED figures, in one place ──────────────
def test_us_not_004_tc2__a_tenant_that_never_opened_s8_has_the_ratified_defaults(brazos):
    """BR-BIL-016 (*"batch default 500"*) and BR-NOT-009 (*"default 08:00–21:00
    tenant time"*), with email and SMS OFF — US-NOT-004 TC-2's honest badges.

    The figures live on the model's columns and nowhere else: a `.get(key, 500)`
    anywhere would be a second copy of a ratified number, free to drift from
    what the tenant's own screen shows.
    """
    with tenant_ctx(brazos):
        settings = dispatch_config.dispatch_settings()

        assert settings.dispatch_batch_size == models.SEEDED_BATCH_SIZE == 500
        assert settings.quiet_hours_start == time(8, 0)
        assert settings.quiet_hours_end == time(21, 0)
        assert settings.email_dispatch_active is False  # "Ships W6"
        assert settings.sms_dispatch_active is False  # "v1.1"
        # BR-BIL-036: print is the FLOOR and has no flag to switch off.
        assert settings.channel_is_active(models.CHANNEL_PRINT) is True


# ── TC-1 · the edit, and its ONE audit row ──────────────────────────────────
def test_us_not_004_tc1__an_admin_edit_saves_and_audits_before_after(brazos, dana, audit_rows):
    """US-NOT-004 TC-1 · T7-17 step 2: *"Toast → ONE audit row
    `notification_settings.updated`, before/after `{batch_size: 500→200}`."*

    Only what MOVED is in the payload — a payload padded with unchanged fields
    makes the next reader hunt for the edit.
    """
    with tenant_ctx(brazos):
        result = dispatch_config.update_dispatch_settings(actor=dana, dispatch_batch_size=200)
        assert result.dispatch_batch_size == 200
        assert dispatch_config.dispatch_settings().dispatch_batch_size == 200

    rows = [row for row in audit_rows if row["action"] == dispatch_config.AUDIT_ACTION]
    assert len(rows) == 1
    assert rows[0]["before"] == {"dispatch_batch_size": 500}
    assert rows[0]["after"] == {"dispatch_batch_size": 200}


def test_us_not_004_tc1b__a_save_that_changes_nothing_writes_no_audit_row(brazos, dana, audit_rows):
    """The trail records CHANGES. A row saying before == after is noise a
    reviewer has to read, and T7-16/T7-17 both assert a specific row COUNT."""
    with tenant_ctx(brazos):
        dispatch_config.update_dispatch_settings(actor=dana, dispatch_batch_size=500)
    assert [row for row in audit_rows if row["action"] == dispatch_config.AUDIT_ACTION] == []


def test_us_not_004_the_quiet_hours_window_is_editable_in_both_directions(brazos, dana, audit_rows):
    """T7-16 turns the knob twice — widen at 23:00, narrow at 06:30 — and each
    save is its own audit row with the times in a form the payload can carry."""
    with tenant_ctx(brazos):
        dispatch_config.update_dispatch_settings(
            actor=dana, quiet_hours_start=time(6, 0), quiet_hours_end=time(21, 0)
        )
        dispatch_config.update_dispatch_settings(
            actor=dana, quiet_hours_start=time(9, 0), quiet_hours_end=time(20, 0)
        )
        settings = dispatch_config.dispatch_settings()

    assert (settings.quiet_hours_start, settings.quiet_hours_end) == (time(9, 0), time(20, 0))
    rows = [row for row in audit_rows if row["action"] == dispatch_config.AUDIT_ACTION]
    assert len(rows) == 2
    assert rows[0]["before"]["quiet_hours_start"] == "08:00:00"
    assert rows[1]["after"] == {"quiet_hours_start": "09:00:00", "quiet_hours_end": "20:00:00"}


# ── TC-5 · Admin-gated, server-side ─────────────────────────────────────────
def test_us_not_004_tc5__a_billing_clerk_cannot_edit_the_dispatch_config(brazos, marcus):
    """US-NOT-004 TC-5: *"Priya (Billing Clerk) attempts a batch-size edit →
    Absent/disabled + SERVER-REJECTED."*

    Asserted at the SERVICE, because that is what every endpoint, job and shell
    goes through (BR-SHL-025) — a gate that lives only in the UI is not a gate.

    PROVED RED by removing `@require_role`: the clerk's edit then saved and
    this failed with `Failed: DID NOT RAISE <class 'core.errors.AuthError'>`.
    """
    from core import errors

    with tenant_ctx(brazos):
        with pytest.raises(errors.AuthError):
            dispatch_config.update_dispatch_settings(actor=marcus, dispatch_batch_size=200)
        # …and nothing moved.
        assert dispatch_config.dispatch_settings().dispatch_batch_size == 500


# ── TC-6 · a batch size of zero ─────────────────────────────────────────────
def test_us_not_004_tc6__a_batch_size_of_zero_is_refused(brazos, dana):
    """US-NOT-004 TC-6: *"Batch size set to 0 → Rejected — dispatch requires a
    positive batch size; validation message, config unchanged."*

    A zero would make the dispatcher select nothing on every cycle and look,
    from every screen, exactly like a provider outage.
    """
    with tenant_ctx(brazos):
        with pytest.raises(dispatch_config.DispatchConfigRefused, match="hand the provider"):
            dispatch_config.update_dispatch_settings(actor=dana, dispatch_batch_size=0)
        with pytest.raises(dispatch_config.DispatchConfigRefused):
            dispatch_config.update_dispatch_settings(actor=dana, dispatch_batch_size=-5)
        assert dispatch_config.dispatch_settings().dispatch_batch_size == 500


def test_us_not_004_tc6b__the_database_refuses_a_zero_batch_size_too(brazos):
    """The same rule at the other end. The service is where a clerk gets a
    sentence they can act on; the CHECK constraint is what holds when a caller
    reaches the table another way.

    PROVED RED by dropping `ck_notification_settings_batch_size` from the
    migration: the INSERT was then accepted and this failed with
    `Failed: DID NOT RAISE IntegrityError`.
    """
    with tenant_ctx(brazos):
        # get_or_create, not create: CR-010 item 7 seeds this row AT
        # PROVISIONING, so a bare create() now collides with the seeded row on
        # the OneToOne — which is itself proof the seeding landed.
        row, _ = models.NotificationSettings.objects.get_or_create(tenant_id=brazos.id)
        with pytest.raises(IntegrityError), transaction.atomic():
            models.NotificationSettings.objects.filter(pk=row.pk).update(dispatch_batch_size=0)


def test_us_not_004_a_window_that_ends_before_it_starts_is_refused(brazos, dana):
    """Not a ruling — a refusal to invent one. Reading `21:00–08:00` as "wraps
    midnight" would turn one transposed pair of times into the 23:00 text
    message BR-NOT-009 exists to prevent, for every customer at once.

    PROVED RED by removing the pair check: the save was then accepted and the
    dispatcher's window test began holding at 10:00 in the morning.
    """
    with tenant_ctx(brazos):
        with pytest.raises(dispatch_config.DispatchConfigRefused, match="ends before it starts"):
            dispatch_config.update_dispatch_settings(
                actor=dana, quiet_hours_start=time(21, 0), quiet_hours_end=time(8, 0)
            )
        assert dispatch_config.dispatch_settings().quiet_hours_start == time(8, 0)


def test_us_not_004_a_two_field_window_move_is_validated_as_a_pair(brazos, dana):
    """09:00–20:00 arrives as two fields and is lawful. Validating each value
    against the OTHER END'S OLD VALUE would refuse it — the start (09:00) is
    past nothing, but a naive check against the old start would be."""
    with tenant_ctx(brazos):
        dispatch_config.update_dispatch_settings(
            actor=dana, quiet_hours_start=time(9, 0), quiet_hours_end=time(20, 0)
        )
        settings = dispatch_config.dispatch_settings()
    assert (settings.quiet_hours_start, settings.quiet_hours_end) == (time(9, 0), time(20, 0))


def test_us_not_004_an_unknown_setting_is_refused_and_names_the_editable_set(brazos, dana):
    """⚠ AMENDED 2026-08-18 (CR-009 C-13). This case used to prove
    `receipt_on_record_payment` was refused as unknown, because the four A15
    toggles were OQ-205 and deliberately NOT columns. The PO closed OQ-205
    (*"keep them default to start with Utility will amake them off"* →
    BR-NOT-022) and the four ARE editable settings now — so the unknown-field
    guard is proved on a field that is still genuinely unknown, and the old
    subject is asserted as ACCEPTED. NOT loosened: same guard, a truthful
    probe."""
    with tenant_ctx(brazos):
        with pytest.raises(dispatch_config.DispatchConfigRefused, match="not a dispatch setting"):
            dispatch_config.update_dispatch_settings(actor=dana, provider_status="connected")
        saved = dispatch_config.update_dispatch_settings(
            actor=dana, receipt_on_record_payment=True
        )
        assert saved.receipt_on_record_payment is True


def test_us_not_004_an_empty_save_is_refused(brazos, dana):
    """An empty save would write an audit row saying a System Admin changed the
    send window and leave no way to see that they did not."""
    with tenant_ctx(brazos):
        with pytest.raises(dispatch_config.DispatchConfigRefused, match="nothing to save"):
            dispatch_config.update_dispatch_settings(actor=dana)


def test_us_not_004_reading_the_config_without_a_tenant_context_is_refused():
    """CLAUDE.md rule 1 — refuse loudly rather than run an unscoped query and
    leave RLS as the only thing between one tenant's send window and another's."""
    from core import errors

    with pytest.raises(errors.AuthError):
        dispatch_config.dispatch_settings()
