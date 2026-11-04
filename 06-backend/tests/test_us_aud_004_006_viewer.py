# ── Trace ──────────────────────────────────────────────
# Story:    US-AUD-004 (S61 viewer list · GET /audit-log) · US-AUD-005 (detail
#           drawer · GET /audit-log/{id} · the entity-scoped read service) ·
#           US-AUD-006 (CSV export · POST /audit-log/export)   Screens: S61
# Rules:    BR-AUD-002 (read-only — no write verb exists) · BR-AUD-007 (tenant-
#           scoped only) · BR-AUD-009 (roles + filter vocabulary + columns) ·
#           BR-AUD-010 (entity tabs are windows into the same store) ·
#           BR-AUD-013 (pagination · 2-yr hot window · explicit archive) ·
#           BR-AUD-014 (50k cap → 422 BIZ-CAP; the export self-audits) ·
#           BR-SHL-011 (invalid list params fall back, never error)
# Tests:    per-TC below. Every isolation TC here is the APP-FILTER half; the
#           RLS half (live Postgres, app.tenant_id) stays with the G5 suite.
# ───────────────────────────────────────────────────────
"""US-AUD-004/005/006 TCs — the 11b §2.13 audit read API.

Rides the identity helper plumbing because S61's law is role law: these tests
sign in as the real fixture actors (Alex Reed = System Admin, Diana Chen =
Executive, Priya Menon = Billing Clerk) and let the server decide.

Two fixture mechanics, stated rather than hidden:
- `created_at` is stamped at INSERT (auto_now_add), so a row that must look old
  is backdated with a direct UPDATE. That is a TEST-ONLY act on the sqlite tier,
  where the append-only trigger does not exist; on Postgres the BR-AUD-002
  trigger refuses it, which is exactly what the G5 suite asserts. Nothing in the
  application ever updates an audit row — TC-7 below proves the API has no verb.
- core.jobs has no registered store on this deployment (the adapter lands with
  the /jobs/{id} story), so the export TCs supply a duck-typed one rather than
  letting a 202 promise a poll URL with no record behind it.
"""

import uuid
from contextlib import contextmanager
from datetime import timedelta

import pytest
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.audit import selectors as audit_selectors
from apps.audit import services as audit_services
from apps.audit.models import AuditLog
from core import jobs as core_jobs
from core import partitioning
from tests.isolation_helpers import (  # noqa: F401 (fixture import)
    assert_denied_without_context,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
    writing_as_tenant,
)
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    api_delete,
    api_get,
    api_patch,
    api_post,
    api_put,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db


# ── fixture plumbing ────────────────────────────────────────────────────────
class FakeJobStore:
    """BE-07 duck-typed store (same shape tests/test_us_rat_helpers.py uses —
    kept local so this file has no cross-lane import)."""

    def __init__(self):
        self.records: dict[str, dict] = {}

    def save(self, record):
        self.records[record["id"]] = record

    def get(self, job_id):
        return self.records.get(job_id)

    def find_active(self, tenant_id, kind, scope_key):
        for record in self.records.values():
            if (
                record["tenant_id"] == tenant_id
                and record["kind"] == kind
                and record["scope_key"] == scope_key
                and record["status"] in core_jobs.ACTIVE_STATUSES
            ):
                return record
        return None


@pytest.fixture()
def job_store():
    """Save-and-restore: apps.tenancy registers the REAL store at startup
    (BE-07), so handing back None would leave later tests without one."""
    previous = core_jobs._store
    store = FakeJobStore()
    core_jobs.set_job_store(store)
    yield store
    core_jobs.set_job_store(previous)


@contextmanager
def _created_at_is_settable():
    """Let the fixture choose `created_at` on the INSERT (see write_row)."""
    field = AuditLog._meta.get_field("created_at")
    field.auto_now_add = False
    try:
        yield
    finally:
        field.auto_now_add = True


def write_row(
    tenant,
    *,
    action,
    entity_type="invoice",
    entity_id=None,
    actor=None,
    before=None,
    after=None,
    age_days=0,
):
    """One trail row, stamped at its intended age ON THE INSERT.

    An older row is written old — never inserted and then UPDATEd. The UPDATE
    form only ever worked on the sqlite tier: on Postgres BR-AUD-002's
    append-only trigger refuses it (asserted in the G5 case below), and it is
    the one mutation the writer contract forbids. A single INSERT with an
    explicit `created_at` is what BE-03 does anyway, so the fixture now matches
    production instead of working around it.
    """
    created_at = timezone.now() - timedelta(days=age_days)
    if age_days and connection.vendor == "postgresql":
        # NFR-24: the row must land in a real monthly partition. Production has
        # one because the create-ahead job ran; the test makes its own, with the
        # partition manager's own DDL, inside the test transaction.
        with connection.cursor() as cursor:
            cursor.execute(partitioning.create_partition_sql("audit_log", created_at.date()))
    # ⚠ INSIDE THE TENANT'S OWN CONTEXT (DEF-GOV-4024/4036, 2026-09-05).
    # `audit_log` carries FORCE ROW LEVEL SECURITY on the partitioned PARENT
    # (BR-AUD-007), so the policy's WITH CHECK applies to the table owner too
    # and refuses an INSERT made with no `app.tenant_id`. This create ran
    # contextless and was accepted only because the test connection was a
    # SUPERUSER — the refusal is the guarantee, and it is the same one this
    # file's TC-8 case asserts against a FORGED cross-tenant insert below.
    with writing_as_tenant(tenant), _created_at_is_settable():
        return AuditLog.objects.create(
            tenant_id=tenant.id,
            actor_user_id=getattr(actor, "id", None),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id or uuid.uuid4(),
            before=before,
            after=after,
            created_at=created_at,
        )


def seed_trail(idn, users):
    """The EP-AUD-02 §4 fixture shape, scaled down: a settings edit, a money
    row from a system job, and an approval chain — plus Blue Mesa's own rows."""
    rows = {
        "settings": write_row(
            idn.silvercreek,
            action="billing_settings.updated",
            entity_type="tenant_settings",
            actor=users.alex,
            before={"late_grace_days": 10},
            after={"late_grace_days": 15},
            age_days=3,
        ),
        "issued": write_row(
            idn.silvercreek,
            action="invoice.issued",
            entity_type="invoice",
            actor=None,  # BR-AUD-003: null actor = system job (bill_run 08-A)
            after={"number": "BL-2608-018410", "job": "bill_run:08-A", "total": "247.30"},
            age_days=2,
        ),
        "approved": write_row(
            idn.silvercreek,
            action="correction.approved",
            entity_type="credit_note",
            actor=users.diana,
            after={"case": "CC-2608-007", "approver": "Evan Ruiz"},
            age_days=1,
        ),
    }
    rows["archived"] = write_row(  # older than the 2-year hot window
        idn.silvercreek,
        action="period.closed",
        entity_type="period",
        actor=users.alex,
        after={"period": "2023-07"},
        age_days=900,
    )
    return rows


# ── US-AUD-004 — the S61 list ───────────────────────────────────────────────
def test_us_aud_004_tc1__newest_first_paginated_rows_with_the_six_s61_columns(idn):
    users = idn.seed_silvercreek()
    rows = seed_trail(idn, users)
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_get(alex, "/audit-log")
    assert response.status_code == 200
    body = response.json()
    # Server pagination is mandatory (BR-AUD-013 / checklist D).
    assert set(body) == {"count", "next", "previous", "results"}
    assert body["count"] == 3  # the 900-day row is outside the hot window
    actions = [row["action"] for row in body["results"]]
    assert actions == ["correction.approved", "invoice.issued", "billing_settings.updated"]
    first = body["results"][0]
    assert set(first) == {
        "id",
        "created_at",
        "actor",
        "action",
        "entity_type",
        "entity_id",
        "summary",
        "source",
    }
    assert first["actor"] == {"id": str(users.diana.id), "name": "Diana Chen"}
    assert first["source"] is None  # GAP AUD-D2 — present, honestly empty
    # A system-job row names no actor (BR-AUD-003) — never a fake user.
    system_row = next(r for r in body["results"] if r["action"] == "invoice.issued")
    assert system_row["actor"] is None
    # Summary is the one-line before → after of the settings edit.
    settings_row = next(r for r in body["results"] if r["id"] == str(rows["settings"].id))
    assert settings_row["summary"] == "late_grace_days: 10 → 15"
    # The window that answered is stated, not inferred (BR-AUD-013).
    assert response["X-Audit-Window"] == "hot"


def test_us_aud_004_tc2__filters_are_and_combined_over_action_and_date_range(idn):
    users = idn.seed_silvercreek()
    seed_trail(idn, users)
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    today = timezone.now().date()
    window = f"f.from={today - timedelta(days=2)}&f.to={today}"
    both = api_get(alex, f"/audit-log?f.action=invoice.issued&{window}").json()
    assert [row["action"] for row in both["results"]] == ["invoice.issued"]
    # AND-combined: the same action outside the range returns nothing.
    narrowed = api_get(
        alex, f"/audit-log?f.action=invoice.issued&f.from={today}&f.to={today}"
    ).json()
    assert narrowed["count"] == 0
    # The actor filter (BR-AUD-009), including the system-job half.
    assert api_get(alex, f"/audit-log?f.actor={users.alex.id}").json()["count"] == 1
    assert api_get(alex, "/audit-log?f.actor=system").json()["count"] == 1


def test_us_aud_004_tc3__entity_filter_by_type_and_id_and_the_shorthand(idn):
    users = idn.seed_silvercreek()
    rows = seed_trail(idn, users)
    target = rows["approved"].entity_id
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    spelled = api_get(alex, f"/audit-log?f.entity_type=credit_note&f.entity_id={target}").json()
    assert [row["id"] for row in spelled["results"]] == [str(rows["approved"].id)]
    # The 11b §2.12 `f.entity=type:id` shorthand resolves to the same rows.
    shorthand = api_get(alex, f"/audit-log?f.entity=credit_note:{target}").json()
    assert shorthand["results"] == spelled["results"]
    # An entity id that belongs to no row is empty, never an error.
    assert api_get(alex, f"/audit-log?f.entity=credit_note:{uuid.uuid4()}").json()["count"] == 0


def test_us_aud_004_tc4__an_executive_has_full_read_access(idn):
    users = idn.seed_silvercreek()
    seed_trail(idn, users)
    diana = signed_in_client("diana@silvercreek.example", "Vista2026peak")
    listing = api_get(diana, "/audit-log")
    assert listing.status_code == 200
    assert listing.json()["count"] == 3
    row_id = listing.json()["results"][0]["id"]
    assert api_get(diana, f"/audit-log/{row_id}").status_code == 200


def test_us_aud_004_tc5__a_billing_clerk_is_denied_server_side(idn):
    users = idn.seed_silvercreek()
    rows = seed_trail(idn, users)
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    denied = api_get(priya, "/audit-log")
    assert denied.status_code == 403  # A4/BR-AUD-009 — UI gating is convenience
    assert denied.json()["code"] == "AUTH-002"
    assert api_get(priya, f"/audit-log/{rows['issued'].id}").status_code == 403
    assert api_post(priya, "/audit-log/export").status_code == 403


def test_us_aud_004_tc6__impossible_and_garbage_params_fall_back_never_error(idn):
    users = idn.seed_silvercreek()
    seed_trail(idn, users)
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    today = timezone.now().date()
    # From > To (hand-edited URL): the pair falls back (BR-SHL-011), no 4xx.
    reversed_range = api_get(alex, f"/audit-log?f.from={today}&f.to={today - timedelta(days=9)}")
    assert reversed_range.status_code == 200
    assert reversed_range.json()["count"] == 3
    # Unparseable date, unknown sort, garbage page/per: fall back or clamp.
    junk = api_get(alex, "/audit-log?f.from=yesterday&sort=colour&dir=sideways&page=zero&per=7")
    assert junk.status_code == 200
    assert junk.json()["count"] == 3
    # An undeclared filter name is ignored, never a column a client picked.
    assert api_get(alex, "/audit-log?f.tenant_id=nope").json()["count"] == 3


def test_us_aud_004_tc7__no_write_verb_exists_on_the_audit_resource(idn):
    """BR-AUD-002 / HR-4 / 11b G8: read-only BY CONSTRUCTION. The refusal is
    structural — the views define no write handler — so it cannot rot."""
    users = idn.seed_silvercreek()
    rows = seed_trail(idn, users)
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    row_id = rows["settings"].id
    for call, path in (
        (lambda p: api_post(alex, p, {"action": "forged"}), "/audit-log"),
        (lambda p: api_put(alex, p, {"action": "forged"}), "/audit-log"),
        (lambda p: api_patch(alex, p, {"action": "forged"}), "/audit-log"),
        (lambda p: api_delete(alex, p), "/audit-log"),
        (lambda p: api_post(alex, p, {"after": {}}), f"/audit-log/{row_id}"),
        (lambda p: api_put(alex, p, {"after": {}}), f"/audit-log/{row_id}"),
        (lambda p: api_patch(alex, p, {"after": {}}), f"/audit-log/{row_id}"),
        (lambda p: api_delete(alex, p), f"/audit-log/{row_id}"),
    ):
        assert call(path).status_code == 405, path
    # Nothing moved: the row is exactly as it was written.
    rows["settings"].refresh_from_db()
    assert rows["settings"].after == {"late_grace_days": 15}
    assert AuditLog.objects.filter(tenant_id=idn.silvercreek.id).count() == 4


def test_us_aud_004_tc8__another_tenants_rows_are_never_visible(idn):
    """The zero-tolerance case (BR-AUD-007/OQ-029). App-filter half; the RLS
    half is the G5 suite's."""
    users = idn.seed_silvercreek()
    rows = seed_trail(idn, users)
    jordan, _ = idn.seed_bluemesa_admin()
    write_row(idn.bluemesa, action="premises.created", entity_type="premises", actor=jordan)
    okafor = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    listing = api_get(okafor, "/audit-log", tenant=BM).json()
    assert [row["action"] for row in listing["results"]] == ["premises.created"]
    # A forged request naming a Silver Creek row id is a plain 404 (HR-1/G4),
    # byte-identical to a genuinely absent row.
    forged = api_get(okafor, f"/audit-log/{rows['issued'].id}", tenant=BM)
    absent = api_get(okafor, f"/audit-log/{uuid.uuid4()}", tenant=BM)
    assert forged.status_code == absent.status_code == 404
    assert forged.json()["code"] == absent.json()["code"] is None
    assert forged.json()["message_key"] == absent.json()["message_key"]
    # A forged entity filter leaks nothing either.
    probe = api_get(
        okafor, f"/audit-log?f.entity=invoice:{rows['issued'].entity_id}", tenant=BM
    ).json()
    assert probe["count"] == 0


def test_us_aud_004_br013__hot_window_is_the_default_and_archive_is_explicit(idn):
    """BR-AUD-013: 2-year hot window by default, archive only on an explicit
    opt-in, and never an unbounded query."""
    users = idn.seed_silvercreek()
    rows = seed_trail(idn, users)
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    hot = api_get(alex, "/audit-log")
    assert rows["archived"].id not in {uuid.UUID(r["id"]) for r in hot.json()["results"]}
    archived = api_get(alex, "/audit-log?archive=true")
    assert archived.json()["count"] == 4
    assert archived["X-Audit-Window"] == "archive"
    # A typo never widens the window silently.
    assert api_get(alex, "/audit-log?archive=maybe").json()["count"] == 3
    # Both windows are bounded by a floor — 2 yrs hot, the BR-AUD-012 7-yr
    # retention horizon for archive.
    now = timezone.now()
    hot_floor = audit_selectors.window_floor(archive=False, now=now)
    archive_floor = audit_selectors.window_floor(archive=True, now=now)
    assert (now - hot_floor).days == audit_selectors.HOT_WINDOW_DAYS
    assert (now - archive_floor).days == audit_selectors.RETENTION_DAYS
    # A filter cannot reach BELOW the floor — the window is law, the filter a wish.
    ancient = api_get(alex, "/audit-log?f.from=2019-01-01")
    assert ancient.json()["count"] == 3


# ── US-AUD-005 — the drawer + the entity-scoped read service ────────────────
def test_us_aud_005_tc1__the_drawer_carries_who_what_when_entity_before_after(idn):
    users = idn.seed_silvercreek()
    rows = seed_trail(idn, users)
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_get(alex, f"/audit-log/{rows['settings'].id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(rows["settings"].id)
    assert body["actor"] == {"id": str(users.alex.id), "name": "Alex Reed"}
    assert body["action"] == "billing_settings.updated"
    assert body["entity_type"] == "tenant_settings"
    assert body["entity_id"] == str(rows["settings"].entity_id)
    assert body["created_at"].startswith(str(rows["settings"].created_at.year))
    # The JSON diff: the changed field only, exactly as stored (BR-AUD-003/006).
    assert body["before"] == {"late_grace_days": 10}
    assert body["after"] == {"late_grace_days": 15}
    assert body["request_metadata"] is None  # GAP AUD-D2 — honest-empty


def test_us_aud_005_tc5__masked_values_render_exactly_as_stored(idn):
    """BR-AUD-006/BR-CUS-045: the drawer never unmasks — it cannot, because the
    unmasked value never entered the trail."""
    users = idn.seed_silvercreek()
    row = write_row(
        idn.silvercreek,
        action="contact.updated",
        entity_type="contact",
        actor=users.alex,
        before={"dob": "06/****"},
        after={"dob": "11/****"},
    )
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    body = api_get(alex, f"/audit-log/{row.id}").json()
    assert body["before"]["dob"] == "06/****"
    assert body["summary"] == "dob: 06/**** → 11/****"
    assert "1978" not in api_get(alex, f"/audit-log/{row.id}").content.decode()


def test_us_aud_005_tc6__a_deleted_entitys_history_still_renders(idn):
    """IS-1 hard delete at used_by 0 leaves its audit row behind: the drawer
    renders from the payload alone — history never 404s."""
    users = idn.seed_silvercreek()
    row = write_row(
        idn.silvercreek,
        action="charge.deleted",
        entity_type="charge",
        actor=users.alex,
        before={"code": "GATE", "name": "Gate remote fee"},
    )
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    body = api_get(alex, f"/audit-log/{row.id}").json()
    assert body["before"] == {"code": "GATE", "name": "Gate remote fee"}
    assert body["after"] is None
    assert body["summary"] == "code: GATE → —; name: Gate remote fee → —"


def test_us_aud_005_tc3__the_entity_service_and_the_filtered_list_are_one_store(idn):
    """BR-AUD-010: a per-entity Audit tab is a WINDOW into audit_log, never a
    copy — its rows equal S61 filtered to that entity, count for count."""
    users = idn.seed_silvercreek()
    account_id = uuid.uuid4()
    for index in range(3):
        write_row(
            idn.silvercreek,
            action=f"account.updated.{index}",
            entity_type="account",
            entity_id=account_id,
            actor=users.priya,
        )
    write_row(idn.silvercreek, action="account.updated.other", entity_type="account")
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    listed = api_get(alex, f"/audit-log?f.entity_type=account&f.entity_id={account_id}").json()
    trail = audit_selectors.entity_trail(idn.silvercreek.id, "account", account_id)
    assert listed["count"] == trail.count() == 3
    assert [row["id"] for row in listed["results"]] == [str(row.id) for row in trail]


# ── US-AUD-006 — the export ─────────────────────────────────────────────────
def test_us_aud_006_tc2__an_accepted_export_returns_202_and_audits_itself(idn, job_store):
    users = idn.seed_silvercreek()
    seed_trail(idn, users)
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_post(alex, "/audit-log/export?f.action=invoice.issued")
    assert response.status_code == 202  # B12 r1: 202 + job_id for every async op
    body = response.json()
    assert set(body) == {"job_id", "status_url"}
    assert body["status_url"] == f"/api/jobs/{body['job_id']}"
    record = job_store.get(body["job_id"])
    assert record["kind"] == "audit_export"
    assert record["payload"]["filters"] == {"action": "invoice.issued"}
    assert record["payload"]["row_count"] == 1  # the export carries its filters
    # BR-AUD-014: the export writes its OWN audit row (who / filters / count).
    (exported,) = idn.rows_for("audit.exported")
    assert exported["actor_user_id"] == users.alex.id
    assert exported["after"]["row_count"] == 1
    assert exported["after"]["filters"] == {"action": "invoice.issued"}
    assert exported["after"]["job_id"] == body["job_id"]


def test_us_aud_006_tc5__an_oversize_export_is_refused_with_no_job_and_no_file(
    idn, job_store, monkeypatch
):
    """BR-AUD-014's 50,000-row cap. The cap constant is lowered here rather than
    seeding 50k rows — the guard under test is the comparison and its refusal,
    not sqlite's insert throughput."""
    users = idn.seed_silvercreek()
    seed_trail(idn, users)
    monkeypatch.setattr(audit_services, "EXPORT_ROW_CAP", 2)
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    refused = api_post(alex, "/audit-log/export")
    assert refused.status_code == 422
    body = refused.json()
    assert body["code"] == "BIZ-CAP"
    assert body["br_ref"] == "BR-AUD-014"
    assert body["params"] == {"rows": 3, "cap": 2}
    assert job_store.records == {}  # no job, no partial file
    assert idn.rows_for("audit.exported") == []
    # Narrowing the filters lets the same export through (the message's advice).
    accepted = api_post(alex, "/audit-log/export?f.action=invoice.issued")
    assert accepted.status_code == 202
    assert len(idn.rows_for("audit.exported")) == 1


def test_us_aud_006_tc8__an_export_runs_under_the_callers_own_tenant(idn, job_store):
    """BR-SHL-016/BR-AUD-007: the job carries the caller's filters, and its row
    count is measured under the caller's tenant — a forged filter naming another
    tenant's rows counts zero of them."""
    users = idn.seed_silvercreek()
    rows = seed_trail(idn, users)
    jordan, _ = idn.seed_bluemesa_admin()
    write_row(idn.bluemesa, action="premises.created", entity_type="premises", actor=jordan)
    okafor = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    response = api_post(
        okafor,
        f"/audit-log/export?f.entity=invoice:{rows['issued'].entity_id}",
        tenant=BM,
    )
    assert response.status_code == 202
    record = job_store.get(response.json()["job_id"])
    assert record["tenant_id"] == idn.bluemesa.id
    assert record["payload"]["row_count"] == 0  # zero Silver Creek rows, ever


def test_us_aud_006_br014__the_export_body_may_carry_the_filters(idn, job_store):
    users = idn.seed_silvercreek()
    seed_trail(idn, users)
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_post(
        alex,
        "/audit-log/export",
        {"filters": {"action": "correction.approved"}, "archive": True},
    )
    assert response.status_code == 202
    record = job_store.get(response.json()["job_id"])
    assert record["payload"]["filters"] == {"action": "correction.approved"}
    assert record["payload"]["archive"] is True


@pytest.mark.isolation
@requires_postgres
def test_us_aud_004_tc8_rls__audit_rows_never_cross_tenants(idn, rls):
    """US-AUD-004/005 TC-8, RLS half + BR-AUD-002, on the real partitioned table.

    Three separate guarantees, all of them invisible to sqlite:

    * BR-AUD-007 — the policy sits on the PARTITIONED PARENT, so a read through
      `audit_log` is tenant-scoped no matter which monthly partition answers it.
    * BR-AUD-007 WITH CHECK — a forged INSERT carrying Silver Creek's tenant_id
      from inside Blue Mesa's context is refused outright.
    * BR-AUD-002 — the append-only trigger refuses UPDATE and DELETE for
      EVERYONE, including the app's own (superuser) role. This is also the
      trigger that makes the backdating trick this file used to rely on
      impossible in production; `write_row` now inserts `created_at` directly,
      exactly as the writer contract (BE-03, single INSERT) allows.
    """
    users = idn.seed_silvercreek()
    rows = seed_trail(idn, users)
    jordan, _ = idn.seed_bluemesa_admin()
    bm_row = write_row(
        idn.bluemesa, action="premises.created", entity_type="premises", actor=jordan
    )

    silvercreek_ids = {str(row.id) for row in rows.values()}
    assert_rls_scoped(
        rls, "audit_log", owner=idn.silvercreek, intruder=idn.bluemesa, owner_ids=silvercreek_ids
    )
    with live_tenant_context(idn.bluemesa.id):
        assert rls.ids("audit_log") == {str(bm_row.id)}
        # id-guessing across the tenant line, including the archived row that
        # lives in a DIFFERENT monthly partition than Blue Mesa's own.
        assert rls.count("audit_log", "id = %s", [str(rows["archived"].id)]) == 0

        # WITH CHECK: Blue Mesa cannot forge a Silver Creek trail row.
        forged = rls.refused(
            "INSERT INTO audit_log (id, tenant_id, action, entity_type, created_at) "
            "VALUES (gen_random_uuid(), %s, 'invoice.issued', 'invoice', now())",
            [str(idn.silvercreek.id)],
        )
        assert "row-level security" in forged

    # BR-AUD-002 — append-only, for every role. Asserted on the app's own
    # connection precisely because that role is a superuser: the trigger is not
    # a permission, it is the table's law.
    with live_tenant_context(idn.silvercreek.id):
        for statement, params in (
            ("UPDATE audit_log SET action = 'tampered' WHERE id = %s", [str(rows["issued"].id)]),
            (
                "UPDATE audit_log SET created_at = now() - interval '900 days' WHERE id = %s",
                [str(rows["issued"].id)],
            ),
            ("DELETE FROM audit_log WHERE id = %s", [str(rows["issued"].id)]),
        ):
            with pytest.raises(DatabaseError) as excinfo:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(statement, params)
            assert "append-only" in str(excinfo.value)
            assert "BR-AUD-002" in str(excinfo.value)
    # Nothing moved, nothing vanished — counted UNDER SILVER CREEK's context,
    # because a `filter(tenant_id=…)` with the GUC cleared now matches zero
    # rows on its own. `assert_denied_without_context` below is the case that
    # asserts exactly that, deliberately, so it stays outside.
    with live_tenant_context(idn.silvercreek.id):
        assert AuditLog.objects.filter(tenant_id=idn.silvercreek.id).count() == len(
            silvercreek_ids
        )
        assert AuditLog.objects.get(
            tenant_id=idn.silvercreek.id, id=rows["issued"].id
        ).action == ("invoice.issued")
    assert_denied_without_context(rls, "audit_log")
