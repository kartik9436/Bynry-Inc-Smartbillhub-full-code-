# ── Trace ──────────────────────────────────────────────
# Story:    US-AUD-010 (the audit actor that is not a person — an automation
#           names itself and its version, and never borrows a staff login)
#           Screens: S61 · every per-entity Audit tab (the account history is
#           the one the worked scenario names)
# Rules:    BR-AUD-019 (a non-person actor is NAMED and, where it has one,
#           VERSIONED; it carries no user id) · BR-AUD-003 (the payload
#           standard — an UNNAMED null actor still means "a system job", and
#           that meaning is unchanged) · BR-AUD-002 (append-only: the new
#           columns are nullable and NOTHING is backfilled) · BR-AUD-007
#           (tenant-scoped; RLS FORCE) · BR-RBS-015 (the runbook is the audit
#           actor, named and versioned; it never borrows a user identity) ·
#           B14 rule 31 (no database id is ever the visible value of a field) ·
#           CLAUDE.md hard rule 7
# Tests:    TC-RBS-12 (the runbooks case this platform gap held red) + the
#           US-AUD-010 TCs below. The RLS half runs only on live PostgreSQL and
#           SKIPS loudly on sqlite — CLAUDE.md law 7, "G5 once called 192 skips
#           a pass", so the skip names the guarantee it could not test.
# ───────────────────────────────────────────────────────
"""US-AUD-010 — an automated action can say what it is.

⚠ **WHY THIS FILE EXISTS AND WHAT IT COST NOT TO HAVE IT.** The returned-payments
runbook applies a $25 fee to 43 accounts overnight — $1,075 charged while nobody
is at the office. Six weeks later a customer disputes theirs and a clerk opens
the account history. Before this story she saw one of two things, and both are
wrong: a BLANK actor, indistinguishable from a bill run, an import or a bug, so
she can tell the customer nothing; or A STAFF MEMBER'S NAME, because the
automation borrowed the login of whoever set it up. It must read
"Returned payments, version 4", so she can look up what version 4 did.

`TC-RBS-12` below is the runbooks test case that names this. It was shown RED
against the platform as it stood before this story — the writer had no parameter
for it and the table had no column — and that failure is quoted in the story.
"""

import uuid

import pytest
from django.db import IntegrityError, transaction

from apps.audit.models import AuditLog
from core import audit as audit_kernel
from tests.isolation_helpers import (  # noqa: F401 (fixture import)
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
    writing_as_tenant,
)
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    api_get,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db


#: The worked scenario's own actor, verbatim from the epic and the handoff.
RETURNED_PAYMENTS = audit_kernel.AutomationActor(
    kind=audit_kernel.ACTOR_KIND_RUNBOOK,
    name="Returned payments",
    version="4",
)


@pytest.fixture()
def real_audit_sink(idn):
    """Put audit's OWN sink back for the duration.

    ⚠ WITHOUT THIS EVERY CASE BELOW IS RED FOR THE WRONG REASON, AND THE FIRST
    DRAFT OF THE RED PROOF WAS. The `idn` fixture swaps `core.audit`'s sink for
    a capture list, so a row written through the kernel under it never reaches
    the table: the assertions then fail on `StopIteration` rather than on the
    thing they are pointed at — a check red over the wrong subject, which law 7
    counts as no check at all. `tests/test_w6_connection_detail.py` already
    solves this exactly this way; this is that fixture, and it restores rather
    than clears so a later test still sees the sink it expects.
    """
    from apps.audit import services as audit_services

    previous = audit_kernel._sink
    audit_kernel.set_audit_sink(audit_services.store_row)
    yield
    audit_kernel.set_audit_sink(previous)


def _write(tenant, actor, *, action="payment.fee_applied", entity_type="payment"):
    """One row through the REAL writer — never `AuditLog.objects.create`.

    The point of this story is what `core.audit` will and will not assemble, so
    a fixture that inserted the model directly would be testing the column and
    not the contract (CLAUDE.md law 7, "looking at the wrong thing").
    """
    with writing_as_tenant(tenant):
        return audit_kernel.money_action(
            actor,
            action,
            entity_type,
            uuid.uuid4(),
            after={"fee": "25.0000", "reason": "returned payment"},
        )


# ── TC-RBS-12 — the case this platform gap held red ─────────────────────────
def test_tc_rbs_12__an_acted_record_names_the_runbook_and_its_version(idn, real_audit_sink):
    """TC-RBS-12: every acted record carries an audit row naming the runbook and
    its version, never a user (BR-RBS-015)."""
    users = idn.seed_silvercreek()
    _write(idn.silvercreek, RETURNED_PAYMENTS)

    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    body = api_get(alex, "/audit-log").json()
    row = next(r for r in body["results"] if r["action"] == "payment.fee_applied")

    # What the clerk's screen is handed: a NAME and a VERSION, and no id at all
    # (B14 rule 31 — no database id is ever the visible value of a field).
    assert row["actor"] == {
        "kind": "runbook",
        "name": "Returned payments",
        "version": "4",
    }
    assert "id" not in row["actor"]

    # BR-RBS-015's hard half: it never borrows a user identity. Nobody's login
    # is on this row, and `users.alex` is signed in while it is read.
    #
    # ⚠ THE READ IS INSIDE `writing_as_tenant` AND MUST BE — hard-won law 14's
    # shape exactly. On the sqlite tier there is no row-level security, so a
    # contextless `AuditLog.objects.get(...)` finds the row and this case is
    # green on every machine. On real PostgreSQL `audit_log` carries FORCE ROW
    # LEVEL SECURITY, the GUC is unset outside the block, nothing equals NULL,
    # and the same line raises `AuditLog.DoesNotExist`. It did, on the first
    # PostgreSQL run of this file, which is the only place it could have.
    with writing_as_tenant(idn.silvercreek):
        stored = AuditLog.objects.get(id=uuid.UUID(row["id"]), tenant_id=idn.silvercreek.id)
    assert stored.actor_user_id is None
    assert stored.actor_label == "Returned payments"
    assert str(users.alex.id) not in str(row)


# ── US-AUD-010 ──────────────────────────────────────────────────────────────
def test_us_aud_010_tc1__money_action_routes_an_automation_instead_of_blanking_it(
    idn, real_audit_sink
):
    """The silent-fallthrough trap, closed. `money_action` reads `actor.id`, so
    an object without one would become a blank system job WITHOUT COMPLAINT —
    the exact failure this story exists to remove, arriving through the fix."""
    idn.seed_silvercreek()
    row = _write(idn.silvercreek, RETURNED_PAYMENTS)
    assert row["actor_user_id"] is None
    assert row["actor_kind"] == "runbook"
    assert row["actor_label"] == "Returned payments"
    assert row["actor_version"] == "4"


def test_us_aud_010_tc2__a_named_actor_may_not_also_carry_a_user_id(idn, real_audit_sink):
    """BR-RBS-015: it never borrows a user identity. Asking for both is refused
    at the writer, loudly, rather than resolved by preferring one."""
    users = idn.seed_silvercreek()
    with writing_as_tenant(idn.silvercreek):
        with pytest.raises(audit_kernel.AuditWriteError) as refused:
            audit_kernel.write_row(
                action="payment.fee_applied",
                entity_type="payment",
                entity_id=uuid.uuid4(),
                actor_user_id=users.alex.id,
                automation=RETURNED_PAYMENTS,
            )
    assert "BR-RBS-015" in str(refused.value)


def test_us_aud_010_tc3__an_automation_with_no_name_or_an_unknown_kind_is_refused():
    """A kind with no name is the blank actor again, wearing a label. Refused at
    construction, so no call site can assemble one."""
    with pytest.raises(ValueError):
        audit_kernel.AutomationActor(kind=audit_kernel.ACTOR_KIND_RUNBOOK, name="  ")
    with pytest.raises(ValueError):
        audit_kernel.AutomationActor(kind="wizard", name="Returned payments")


def test_us_aud_010_tc4__a_person_and_an_unnamed_system_job_read_exactly_as_before(
    idn, real_audit_sink
):
    """BR-AUD-002 is why this matters: nothing is backfilled, so every row
    written before this story must read identically after it. A person keeps
    `{id, name}`; an unnamed job keeps `null` (BR-AUD-003)."""
    users = idn.seed_silvercreek()
    _write(idn.silvercreek, users.alex, action="invoice.issued", entity_type="invoice")
    _write(idn.silvercreek, None, action="period.closed", entity_type="period")

    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    body = api_get(alex, "/audit-log").json()
    person = next(r for r in body["results"] if r["action"] == "invoice.issued")
    unnamed = next(r for r in body["results"] if r["action"] == "period.closed")

    assert person["actor"] == {"id": str(users.alex.id), "name": "Alex Reed"}
    assert unnamed["actor"] is None


def test_us_aud_010_tc5__the_filter_tells_a_named_automation_from_a_system_job(
    idn, real_audit_sink
):
    """`f.actor=system` meant "actor_user_id IS NULL" and would now sweep up
    every named runbook with it — the indistinguishability this story removes,
    reintroduced by the filter. `system` is the UNNAMED half; `automation` is
    the named one."""
    idn.seed_silvercreek()
    _write(idn.silvercreek, RETURNED_PAYMENTS)
    _write(idn.silvercreek, None, action="period.closed", entity_type="period")

    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    assert api_get(alex, "/audit-log?f.actor=system").json()["count"] == 1
    assert api_get(alex, "/audit-log?f.actor=automation").json()["count"] == 1


def test_us_aud_010_tc6__the_entity_read_behind_an_account_history_names_it_too(
    idn, real_audit_sink
):
    """BR-AUD-010: a per-entity Audit tab is a WINDOW into the same store. The
    account history is the screen the worked scenario names, so the entity-scoped
    read must carry the same actor payload the viewer does."""
    idn.seed_silvercreek()
    account_id = uuid.uuid4()
    with writing_as_tenant(idn.silvercreek):
        audit_kernel.money_action(
            RETURNED_PAYMENTS,
            "payment.fee_applied",
            "account",
            account_id,
            after={"fee": "25.0000"},
        )
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    body = api_get(alex, f"/audit-log?f.entity=account:{account_id}").json()
    assert body["count"] == 1
    assert body["results"][0]["actor"]["name"] == "Returned payments"
    assert body["results"][0]["actor"]["version"] == "4"


def test_us_aud_010_tc7__a_named_actor_is_tenant_scoped_like_every_other_row(idn, real_audit_sink):
    """BR-AUD-007, the app-filter half. The RLS half is TC-8, on live Postgres."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    _write(idn.silvercreek, RETURNED_PAYMENTS)

    jordan = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    # ⚠ THE TENANT IS NAMED ON THE READ AS WELL AS ON THE SIGN-IN. `api_get`
    # defaults to Silver Creek, so a read without it would ask the RIGHT
    # question of the WRONG tenant and pass for a reason that proves nothing.
    body = api_get(jordan, "/audit-log?f.actor=automation", tenant=BM).json()
    assert body["count"] == 0, "Blue Mesa read Silver Creek's runbook row"


@requires_postgres
def test_us_aud_010_tc8__rls_refuses_the_named_row_across_tenants(idn, rls, real_audit_sink):
    """BR-AUD-007 under FORCE ROW LEVEL SECURITY, on a real PostgreSQL. Skipped
    on sqlite — and the skip says so rather than counting as a pass."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    _write(idn.silvercreek, RETURNED_PAYMENTS)
    # `live_tenant_context` takes the tenant's ID, not the Tenant — passing the
    # object raised `AttributeError: 'Tenant' object has no attribute 'replace'`
    # from `uuid.UUID()` on the first run that could reach this line at all.
    with live_tenant_context(idn.bluemesa.id):
        assert AuditLog.objects.filter(actor_kind="runbook").count() == 0
    with live_tenant_context(idn.silvercreek.id):
        assert AuditLog.objects.filter(actor_kind="runbook").count() == 1


@requires_postgres
def test_us_aud_010_tc9__the_database_refuses_a_named_actor_carrying_a_user_id(idn):
    """BR-RBS-015 at the last line of defence. The writer refuses it (TC-2); so
    does the table, so a future writer cannot reintroduce it."""
    users = idn.seed_silvercreek()
    with writing_as_tenant(idn.silvercreek):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                AuditLog.objects.create(
                    tenant_id=idn.silvercreek.id,
                    actor_user_id=users.alex.id,
                    actor_kind="runbook",
                    actor_label="Returned payments",
                    actor_version="4",
                    action="payment.fee_applied",
                    entity_type="payment",
                    entity_id=uuid.uuid4(),
                )


def test_us_aud_010_tc10__nothing_was_backfilled(idn):
    """BR-AUD-002 — append-only. The migration adds three NULLABLE columns and
    writes not one row, so every row already in the trail is untouched. Proved
    by inserting a pre-story row shape and reading it back unchanged."""
    idn.seed_silvercreek()
    with writing_as_tenant(idn.silvercreek):
        legacy = AuditLog.objects.create(
            tenant_id=idn.silvercreek.id,
            actor_user_id=None,
            action="invoice.issued",
            entity_type="invoice",
            entity_id=uuid.uuid4(),
            after={"job": "bill_run:08-A"},
        )
        stored = AuditLog.objects.get(id=legacy.id, tenant_id=idn.silvercreek.id)
    assert (stored.actor_kind, stored.actor_label, stored.actor_version) == (None, None, None)
