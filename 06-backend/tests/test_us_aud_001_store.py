# ── Trace ──────────────────────────────────────────────
# Story:    US-AUD-001 (EP-AUD-01 — platform audit-write contract, STORE half)
# Rules:    BR-AUD-001 · BR-AUD-002 (append-only) · BR-AUD-003 (row shape) ·
#           BR-AUD-007 (tenant from context) · HR-7
# ───────────────────────────────────────────────────────
import uuid

import pytest
from django.db import connection as db_connection
from django.test import TestCase

from apps.audit import services as audit_store
from apps.audit.models import AuditLog
from core import audit as audit_kernel
from core import tenancy as core_tenancy
from tests.test_us_ten_helpers import FakeGucConnection


class AuditStore(TestCase):
    """The GUC is a Postgres feature; on the sqlite test DB the ContextVar mirror is
    real and the SET statements go to the recording fake (established test pattern).
    The live-GUC + RLS halves run in the G5 isolation suite."""

    def setUp(self):
        self.tenant_id = uuid.uuid4()
        self._real_connection = core_tenancy.connection
        # ⚠ VENDOR-GUARDED SINCE DEF-2761 (2026-08-31). `setUp` runs before every
        # case in this class, so a substitution here is IMPLICIT — no line in any
        # test says the kernel was replaced. On PostgreSQL the recorder would
        # swallow the `set_config` that BR-AUD-007's "tenant from context"
        # assertion below exists to prove, and the case would pass having proved
        # nothing. On sqlite it is still required: there is no `set_config()`.
        # G57 enforces this shape across the suite.
        if db_connection.vendor != "postgresql":
            core_tenancy.connection = FakeGucConnection()
            self.addCleanup(setattr, core_tenancy, "connection", self._real_connection)
        self.addCleanup(core_tenancy._current_tenant.set, None)

    def tenant_context(self, tenant_id):
        return core_tenancy.tenant_context(tenant_id)

    def test_us_aud_001_tc3__money_action_lands_a_row_through_the_registered_sink(self):
        payment_id = uuid.uuid4()  # entity_id is the row's uuid (B2), not its display number
        with self.tenant_context(self.tenant_id):
            audit_kernel.money_action(
                None, "payment.record", "payment", payment_id, after={"amount": "292.87"}
            )
        row = AuditLog.objects.get(action="payment.record")
        self.assertEqual(str(row.tenant_id), str(self.tenant_id), "BR-AUD-007 tenant from context")
        self.assertEqual(row.entity_type, "payment")
        self.assertEqual(row.after["amount"], "292.87")
        self.assertIsNotNone(row.created_at, "the store stamps when")

    def test_us_aud_001_tc4__the_sink_is_registered_at_startup(self):
        # Without this wiring every money action would raise AuditWriteError (rule 7):
        # the failure the demo seed correctly refused to run into.
        self.assertIsNotNone(audit_kernel._sink)
        self.assertIs(audit_kernel._sink, audit_store.store_row)

    def test_us_aud_001_tc5__no_write_without_tenant_context(self):
        with pytest.raises(audit_kernel.AuditWriteError):
            audit_kernel.write_row(
                action="payment.record", entity_type="payment", entity_id=uuid.uuid4()
            )
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_us_aud_001_tc6__store_exposes_no_update_or_delete_path(self):
        # BR-AUD-002: append-only is a design property of this module, not a convention.
        exported = {name for name in dir(audit_store) if not name.startswith("_")}
        for forbidden in ("update_row", "delete_row", "purge", "edit_row"):
            self.assertNotIn(forbidden, exported)
