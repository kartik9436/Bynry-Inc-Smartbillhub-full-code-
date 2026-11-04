# ── Trace ──────────────────────────────────────────────
# Component: BE-03 tests (core/audit.py) — write contract, loud failure, refusal rows.
#            Sink is a capturing fake; the real single-INSERT sink lands with apps.audit
#            (US-AUD-001..003, whose TCs run against the live table).
# ───────────────────────────────────────────────────────
"""BE-03 unit tests: the one write path assembles the BR-AUD-003 standard row,
refuses to lose rows (rule 7), stamps tenant from context only (BR-AUD-007),
and exposes no mutation API (BR-AUD-002)."""

import uuid

import pytest

from core import audit

TENANT = uuid.UUID("00000000-0000-0000-0000-00000000000a")


class FakeActor:
    def __init__(self, user_id):
        self.id = user_id


@pytest.fixture(autouse=True)
def clean_sink():
    audit.set_audit_sink(None)
    yield
    audit.set_audit_sink(None)


@pytest.fixture()
def in_tenant(monkeypatch):
    monkeypatch.setattr(audit, "current_tenant_id", lambda: TENANT)


@pytest.fixture()
def rows(in_tenant):
    captured = []
    audit.set_audit_sink(captured.append)
    return captured


# ── the standard row (BR-AUD-003) ───────────────────────────────────────────
def test_be03_tc01_row_carries_who_what_entity_before_after(rows):
    returned = audit.write_row(
        action="billing_settings.updated",
        entity_type="billing_settings",
        entity_id="brazosbend",
        actor_user_id=7,
        before={"late_grace_days": 10},
        after={"late_grace_days": 15},
    )
    assert rows == [returned]
    assert returned == {
        "tenant_id": TENANT,  # from context, never a parameter
        "actor_user_id": 7,
        "action": "billing_settings.updated",
        "entity_type": "billing_settings",
        "entity_id": "brazosbend",
        "before": {"late_grace_days": 10},
        "after": {"late_grace_days": 15},
        # ⚠ ADDED 2026-09-06 (US-AUD-010). A person's row carries all three as
        # NULL, and the WHOLE KEY SET is still asserted rather than a subset —
        # deliberately, because that is what makes this case notice a fourth key
        # arriving one day. What the three mean is in `core/audit.py`; that they
        # are None HERE is the point: a person acted, so no automation named
        # itself, and BR-AUD-003's reading of this row does not move.
        "actor_kind": None,
        "actor_label": None,
        "actor_version": None,
    }


def test_be03_tc02_tenant_is_context_only_never_a_parameter(rows):
    # BR-AUD-007: a caller cannot address another tenant's trail.
    with pytest.raises(TypeError):
        audit.write_row(  # type: ignore[call-arg]
            action="x.y", entity_type="x", entity_id=1, tenant_id=uuid.uuid4()
        )


def test_be03_tc03_system_job_rows_use_null_actor(rows):
    row = audit.write_row(
        action="invoice.issued",
        entity_type="invoice",
        entity_id="BL-2608-018410",
        actor_user_id=None,  # BR-AUD-003: NULL actor = system job, named in payload
        after={"job": "bill_run:08-A"},
    )
    assert row["actor_user_id"] is None
    assert row["after"]["job"] == "bill_run:08-A"


def test_be03_tc04_money_action_helper_uses_actor_id(rows):
    audit.money_action(FakeActor(42), "payment.recorded", "payment", "PMT-1")
    assert rows[0]["actor_user_id"] == 42
    assert rows[0]["action"] == "payment.recorded"


# ── loud failure (rule 7: no silent loss) ───────────────────────────────────
def test_be03_tc05_no_tenant_context_refuses_loudly(monkeypatch):
    monkeypatch.setattr(audit, "current_tenant_id", lambda: None)
    audit.set_audit_sink(lambda row: None)
    with pytest.raises(audit.AuditWriteError):
        audit.write_row(action="invoice.issued", entity_type="invoice", entity_id=1)


def test_be03_tc06_no_sink_refuses_loudly(in_tenant):
    with pytest.raises(audit.AuditWriteError):
        audit.write_row(action="invoice.issued", entity_type="invoice", entity_id=1)


def test_be03_tc07_empty_action_or_entity_refused(rows):
    with pytest.raises(audit.AuditWriteError):
        audit.write_row(action="", entity_type="invoice", entity_id=1)
    with pytest.raises(audit.AuditWriteError):
        audit.write_row(action="invoice.issued", entity_type="", entity_id=1)
    assert rows == []


# ── refusal attempt rows (BR-AUD-018) ───────────────────────────────────────
def test_be03_tc08_refusal_attempt_records_who_what_rule(rows):
    row = audit.refusal_attempt(
        actor_user_id=7,
        code="BIZ-IMMUTABLE",
        br_ref="BR-BIL-004",
        method="PATCH",
        path="/api/invoices/BL-1",
        trace_id="abc123",
    )
    assert row is not None and rows == [row]
    assert row["action"] == audit.REFUSAL_ATTEMPT_ACTION
    assert row["actor_user_id"] == 7  # who
    assert row["after"]["method"] == "PATCH" and row["after"]["path"] == "/api/invoices/BL-1"
    assert row["after"]["br_ref"] == "BR-BIL-004"  # rule
    assert row["before"] is None  # terminal event


def test_be03_tc09_refusal_attempt_degrades_quietly_not_loudly(monkeypatch):
    # Raising here would turn a lawful 403/409 into a 500 — log-and-None instead.
    monkeypatch.setattr(audit, "current_tenant_id", lambda: None)
    assert (
        audit.refusal_attempt(
            actor_user_id=None, code="AUTH-002", br_ref=None, method="GET", path="/x"
        )
        is None
    )
    monkeypatch.setattr(audit, "current_tenant_id", lambda: TENANT)
    audit.set_audit_sink(None)  # tenant context but no store yet (W0)
    assert (
        audit.refusal_attempt(
            actor_user_id=None, code="AUTH-002", br_ref=None, method="GET", path="/x"
        )
        is None
    )


# ── append-only surface (BR-AUD-002) ────────────────────────────────────────
def test_be03_tc10_module_exposes_no_mutation_api():
    mutating = [
        name
        for name in dir(audit)
        if any(verb in name.lower() for verb in ("update", "delete", "amend", "edit"))
    ]
    assert mutating == []  # corrections are NEW rows; no amend path exists


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-03@87ece49 (component packet — B13 §3 row + signed contracts; hash = sha256/7 of B12)
# generated: 2026-08-09 by story-coder v1 (W0 kernel lane, B13 rows BE-01..BE-05)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-08)
# gates: ruff✔ black✔ pytest 10/10✔ (this file) · suite 92/92✔ · run_gates 10-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines
# exceptions: none stubbed; E2-candidates reported to the PO batch via the build report (404/40x codes absent from the B12 §3 catalog · BR-AUD-018 attempt-row event code pending SC-3 · G7 guard list lacks core/tenancy.py)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
