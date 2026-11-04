# ── Trace ──────────────────────────────────────────────
# Change:   CR-067 tasks B2 and B3 — the two halves the A-lane could not build.
#           DEF-3321 (`error_diagnostics` is written and NOTHING reads it back)
#           and DEF-3322 (the audit list cannot be asked for failures).
#           PO 2026-09-02, verbatim, on the toolbar half: *"What I would add to
#           the toolbar is a "Errors only" filter, so you can jump straight to
#           the failures without scrolling past 800 rows of successful seeding.
#           - Yes this is required"*   Screens: S61
# Rules:    CLAUDE.md hard rule 1 (tenant scoping; another tenant's record is
#           ABSENT, never forbidden) · hard rule 7 (the trail attaches to a MONEY
#           action — a read writes no row) · BR-AUD-002 (read-only by
#           construction: no verb but `get` exists) · BR-AUD-009 (System Admin +
#           Executive read the TRAIL — and CR-067 §3 narrows the DIAGNOSTIC to
#           System Admin alone) · BR-SHL-011 (a list param never 4xx's, which is
#           exactly why an undeclared filter is the trap here) · BR-SHL-025 (the
#           server enforces; UI gating is convenience) · B14 rule 31 (no database
#           id is the visible value of a field) · hard-won law 2 (built is not
#           wired) · hard-won law 7 (prove the guard RED first)
# Tests:    this file IS the D1 half for CR-067 tasks B2's endpoint and B3's filter
# ───────────────────────────────────────────────────────
"""CR-067 — the diagnostic reaches a screen, and a failure can be found.

⚠ **EVERY CASE HERE WAS PROVED RED BEFORE IT WAS TRUSTED GREEN (hard-won law 7),
and the failure each one produced is quoted in its own docstring** — measured,
not paraphrased. The sabotages are replayable through
`07-frontend/scripts/cr067_red_proof.py` (the `be-*` names it grew for this
lane), which applies one edit, runs the file and puts the bytes back.

**THE TWO THINGS THIS FILE EXISTS TO STOP ARE BOTH SILENT.**

  1. A table written by the product and served by no route. `error_diagnostics`
     was exactly that for a day: written at the seeding seams, referenced from
     the permanent audit row, swept at ninety days, and unreachable. Every test
     over it passed, because they all wrote a record and read it back IN PROCESS
     through `by_reference()`. Nothing asked whether an HTTP caller could.

  2. A filter the server never declared. `parse_list_params` DROPS an
     `f.<name>` it does not recognise rather than refusing it (BR-SHL-011), so
     an "Errors only" toggle wired to an undeclared filter comes back with the
     WHOLE list and reads as a product with no errors in it. The reporting
     tenant's own log carries 809 rows. `test_cr067_b3__the_filter_is_declared`
     is the case that bites on it, and it bites by ARITHMETIC — a count that did
     not move is the whole symptom.
"""

import uuid
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

import pytest
from django.db import connection
from django.utils import timezone

from apps.audit import diagnostics as audit_diagnostics
from apps.audit import selectors as audit_selectors
from apps.audit.models import AuditLog
from core import diagnostics as diagnostics_kernel
from core import partitioning
from core import tenancy as core_tenancy

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

#: The 2 September deployment's own failure, and the two values a real runtime
#: message carries. Nothing stored or served may contain either (CR-067 §2).
BAIT_ACCOUNT = "A-10001"
BAIT_BALANCE = "181.9400"

#: The three people on the S61 role matrix, so a reader can tell at a glance
#: which door each case is knocking on.
ADMIN = ("alex@silvercreek.example", "Canyon2026rapids")
EXECUTIVE = ("diana@silvercreek.example", "Vista2026peak")
CLERK = ("priya@silvercreek.example", "Meadow2026sage")


class StorageNotConfiguredLikeItWas(RuntimeError):
    """The shape of the real one, with a message that carries customer data."""


def _storage_failure() -> StorageNotConfiguredLikeItWas:
    try:
        raise StorageNotConfiguredLikeItWas(
            f"account {BAIT_ACCOUNT} could not be filed: balance {BAIT_BALANCE}"
        )
    except StorageNotConfiguredLikeItWas as exc:
        return exc


@contextmanager
def _created_at_is_settable():
    """Let a fixture choose `created_at` on the INSERT — never an UPDATE, which
    BR-AUD-002's append-only trigger refuses on PostgreSQL."""
    field = AuditLog._meta.get_field("created_at")
    field.auto_now_add = False
    try:
        yield
    finally:
        field.auto_now_add = True


def write_row(tenant, *, action, after=None, actor=None, age_days=0, entity_type="tenant"):
    """One permanent trail row, stamped at its intended age ON THE INSERT."""
    created_at = timezone.now() - timedelta(days=age_days)
    if age_days and connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(partitioning.create_partition_sql("audit_log", created_at.date()))
    with _created_at_is_settable():
        return AuditLog.objects.create(
            tenant_id=tenant.id,
            actor_user_id=getattr(actor, "id", None),
            action=action,
            entity_type=entity_type,
            entity_id=uuid.uuid4(),
            before=None,
            after=after,
            created_at=created_at,
        )


def capture_diagnostic(tenant, **overrides):
    """Write one real diagnostic inside a tenant's context and return its reference.

    It goes through `core.diagnostics.capture()` rather than an ORM create, so
    every assertion below is about the record the PRODUCT writes — the redaction,
    the frames, the release and the settings snapshot included.
    """
    fields = {
        "error_code": "SD-PRECONDITION",
        "exception": _storage_failure(),
        "component": "tenancy:seed_sample_records",
        "settings_named": ["DIAGNOSTIC_RETENTION_DAYS"],
        "request_fields": ["subdomain", "company_name"],
        "job_kind": "sample_data_plant",
        "job_id": str(uuid.uuid4()),
        "step": 8,
        "step_total": 18,
        "audit_action": "sample.block_failed",
    }
    fields.update(overrides)
    with core_tenancy.tenant_context(tenant.id):
        return diagnostics_kernel.capture(**fields)


def failed_row_with_diagnostic(idn, users):
    """The pair CR-067 §3 describes: a permanent row and the record beside it,
    joined by the reference and by no foreign key."""
    reference = capture_diagnostic(idn.silvercreek)
    row = write_row(
        idn.silvercreek,
        action="sample.block_failed",
        actor=users.alex,
        after={
            "module": "tenancy",
            "block": "seed_sample_records",
            "label": "Documents",
            "error_code": "SD-PRECONDITION",
            "failure_class": "root",
            "meaning": "The block refused because something it needs was not in place.",
            "reference": reference,
        },
    )
    return row, reference


# ══ CR-067 B2 / DEF-3321 — the record reaches a caller ══════════════════════
def test_cr067_b2__a_system_admin_reads_the_six_facts_section_5_measures_this_change_against(idn):
    """CR-067 §5's bar, over HTTP: *"could somebody holding ONLY the diagnostic
    record write a failing test?"*

    Every assertion below reads a key off the SERVED payload and nothing else —
    no ORM, no second lookup. If this test ever has to reach past the response
    for a fact, the endpoint is incomplete and the endpoint is what gets fixed.

    RED-PROVED (measured, `be-no-endpoint`): with the route removed from
    `apps/audit/api.urlpatterns` — which is the state DEF-3321 records, a table
    written by the product and served by nothing — this failed with

        AssertionError: the diagnostic endpoint answered 404; DEF-3321 is that
        `error_diagnostics` is written and no route reads it back
        assert 404 == 200
    """
    users = idn.seed_silvercreek()
    row, reference = failed_row_with_diagnostic(idn, users)
    admin = signed_in_client(*ADMIN)

    response = api_get(admin, f"/audit-log/{row.id}/diagnostic")
    assert response.status_code == 200, (
        "the diagnostic endpoint answered "
        f"{response.status_code}; DEF-3321 is that `error_diagnostics` is "
        "written and no route reads it back"
    )
    body = response.json()
    assert body["held"] is True
    assert body["reason"] == audit_diagnostics.REASON_HELD
    assert body["reference"] == reference
    record = body["record"]

    # 1 · the exception, as CODE and never as a message.
    assert record["exception"]["type"] == "StorageNotConfiguredLikeItWas"
    assert record["exception"]["module"] == "tests.test_cr067_diagnostic_read"
    # 2 · where in the code.
    assert record["frames"], "a record with no frames cannot say where it broke"
    assert record["frames"][-1]["file"].startswith("06-backend/")
    assert record["frames"][-1]["line"] > 0
    # 3 · which step of which job.
    assert record["job"]["kind"] == "sample_data_plant"
    assert record["job"]["step"] == 8 and record["job"]["of"] == 18
    # 4 · which build.
    assert record["release"]
    # 5 · the settings in force — the six lines §5 prints are rebuilt from here.
    assert record["settings_in_force"]["DIAGNOSTIC_RETENTION_DAYS"] == 90
    # 6 · the request's field NAMES, never a value (task A2's signature guarantee).
    assert record["request_fields"] == ["subdomain", "company_name"]

    # The join, both ways, with no foreign key anywhere.
    assert record["audit_action"] == "sample.block_failed"
    assert body["audit_action"] == row.action


def test_cr067_b2__nothing_the_exception_said_reaches_the_wire(idn):
    """BR-AUD-002 / CR-067 §2 — the guarantee is the writer's SIGNATURE, and this
    is the check that it still holds at the far end of an HTTP response.

    The message this failure carried is *"account A-10001 could not be filed:
    balance 181.9400"*. Neither string may appear anywhere in the served bytes.

    ⚠ **THE SABOTAGE FOR THIS ONE CANNOT LIVE IN THE SERIALIZER, AND FINDING
    THAT OUT IS HALF THE VALUE OF PROVING IT RED.** `str(exc)` is stored by no
    column (task A2), so there is no message in the record for `payload()` to
    leak — the writer's SIGNATURE is the guarantee, not the read. The only way
    to put a customer's account number on this wire is to put it in the record
    first, so the sabotage goes where the mistake would really be made: the
    "helpful" exception label in the kernel.

    RED-PROVED (measured, `be-serve-the-message`): with `core.diagnostics.
    assemble()` writing `"exception_type": f"{type(exception).__name__}: {exception}"`
    — the exact slip `test_cr067_diagnostics.py` records one layer down — this
    failed with

        AssertionError: the served diagnostic carries 'A-10001'
        assert 'A-10001' not in '{"audit_act...691+00:00"}}'
            : account A-10001 could not be filed: balance 181.9400","module":
            "tests.test_cr067_diagnostic_read","chain":[]},"frames":[…
    """
    users = idn.seed_silvercreek()
    row, _ = failed_row_with_diagnostic(idn, users)
    admin = signed_in_client(*ADMIN)
    served = api_get(admin, f"/audit-log/{row.id}/diagnostic").content.decode()
    for bait in (BAIT_ACCOUNT, BAIT_BALANCE, "could not be filed"):
        assert bait not in served, f"the served diagnostic carries {bait!r}"


def test_cr067_b2__the_records_own_database_id_is_not_served(idn):
    """B14 rule 31 — PO 2026-08-31, *"no Databse ID on screen - that is a rule"*.

    A uuid that never leaves the server cannot be rendered by a later lane that
    did not read the comment above `payload()`. What a person reads instead is
    the eight-character reference, which is minted to be dictated.

    RED-PROVED (measured, `be-serve-the-row-id`): with `"id": str(record.id)`
    added to `payload()` this failed with

        AssertionError: the diagnostic's own row id is on the wire — B14 rule 31
        assert '01a06393-95...312a9f2c3ae7' not in '{"audit_act...694+00:00"}}'
    """
    users = idn.seed_silvercreek()
    row, reference = failed_row_with_diagnostic(idn, users)
    with core_tenancy.tenant_context(idn.silvercreek.id):
        stored = audit_diagnostics.by_reference(reference)
    admin = signed_in_client(*ADMIN)
    served = api_get(admin, f"/audit-log/{row.id}/diagnostic").content.decode()
    assert str(stored.id) not in served, (
        "the diagnostic's own row id is on the wire — B14 rule 31"
    )
    # And the value that IS meant to be read is there, in the dictatable form.
    assert reference in served
    assert reference == "-".join([reference[:4], reference[5:]])


# ══ The role gate, which is what makes this a boundary and not a CSS choice ══
def test_cr067_b2__an_executive_reads_s61_and_is_REFUSED_the_technical_record(idn):
    """**This is the case the whole endpoint exists for.**

    Before it, the S61 drawer's System-Admin panel was `BR-SHL-025` convenience:
    both halves came out of the ONE payload `GET /audit-log/{id}` serves, so
    `useTenantRole` decided what was DRAWN and an Executive held the bytes
    either way. The technical record now arrives on its own request, behind
    `SystemAdminOnly`, so the browser's opinion no longer decides anything.

    An Executive is proved to still read the TRAIL in the same test, because a
    gate that broke BR-AUD-009 would be a regression dressed as a fix.

    RED-PROVED (measured, `be-gate-is-admin-or-executive`): with the view's
    `permission_classes` set to `[AdminOrExecutive]` — the class every other
    route in this module carries, and therefore the copy-paste a lane makes —
    this failed with

        AssertionError: an Executive read the technical record; CR-067 §3 says
        System Admin only, and the frontend gate is convenience (BR-SHL-025)
        assert 200 == 403
    """
    users = idn.seed_silvercreek()
    row, _ = failed_row_with_diagnostic(idn, users)
    executive = signed_in_client(*EXECUTIVE)

    # BR-AUD-009 is untouched: the trail itself still reads.
    assert api_get(executive, "/audit-log").status_code == 200
    assert api_get(executive, f"/audit-log/{row.id}").status_code == 200

    refused = api_get(executive, f"/audit-log/{row.id}/diagnostic")
    assert refused.status_code == 403, (
        "an Executive read the technical record; CR-067 §3 says System Admin "
        "only, and the frontend gate is convenience (BR-SHL-025)"
    )
    assert refused.json()["code"] == "AUTH-002"
    # And the refusal carries no part of the record it refused.
    assert "StorageNotConfiguredLikeItWas" not in refused.content.decode()


def test_cr067_b2__a_billing_clerk_never_gets_near_it(idn):
    """A Billing Clerk cannot reach S61 at all (BR-AUD-009), so this door is
    shut twice over. Asserted rather than assumed — the nested route is a new
    URL and a new URL is a new chance to forget."""
    users = idn.seed_silvercreek()
    row, _ = failed_row_with_diagnostic(idn, users)
    clerk = signed_in_client(*CLERK)
    refused = api_get(clerk, f"/audit-log/{row.id}/diagnostic")
    assert refused.status_code == 403
    assert refused.json()["code"] == "AUTH-002"


def test_cr067_b2__another_tenants_row_is_a_PLAIN_404_and_existence_does_not_leak(idn):
    """CLAUDE.md hard rule 1 — absent under this scope, never forbidden.

    ⚠ **THE ASSERTION THAT MATTERS IS THE LAST ONE: the body for another
    tenant's row is byte-identical to the body for an id that never existed.**
    Two different refusals would tell a System Admin at Silver Creek that Blue
    Mesa has a failure with that id, which is the disclosure a 404 exists to
    prevent (HR-1/G4).

    ⚠ **THE FIRST SABOTAGE WRITTEN FOR THIS TEST DID NOT REPRODUCE THE LEAK,
    AND THAT IS WORTH RECORDING RATHER THAN QUIETLY REPLACING.** It answered a
    friendlier 404 body — and the suite stayed GREEN, correctly: that body is
    served for an absent id and a foreign one alike, so nothing is disclosed.
    `errors.NotFoundError` takes no message parameter at all (`core/errors.py`
    — *"keeping cross-tenant and plain-absent bodies byte-identical (no leak)"*),
    so the kernel had already made the tidy version of the mistake unwritable.
    **The leak is telling the two APART**, and the natural way to write it is to
    be helpful about a row that exists: *"it is there, you just cannot see it."*

    RED-PROVED (measured, `be-foreign-row-is-a-403`): with the view probing for
    the row and refusing 403 when it found one, this failed with

        assert (403 == 404)
    """
    users = idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    reference = capture_diagnostic(idn.bluemesa)
    foreign = write_row(
        idn.bluemesa,
        action="sample.block_failed",
        after={"error_code": "SD-PRECONDITION", "reference": reference},
    )
    admin = signed_in_client(*ADMIN)

    across = api_get(admin, f"/audit-log/{foreign.id}/diagnostic")
    absent = api_get(admin, f"/audit-log/{uuid.uuid4()}/diagnostic")
    assert across.status_code == 404 and absent.status_code == 404
    assert _body_without_trace(across) == _body_without_trace(absent), (
        "the two 404s differ, so a caller can tell a foreign row from an "
        "absent one"
    )
    # Belt and braces: nothing of Blue Mesa's record is in the refusal.
    assert reference not in across.content.decode()


def _body_without_trace(response) -> dict:
    """The refusal body with its per-request trace id removed — that field is
    minted fresh every time and comparing it would prove nothing."""
    body = dict(response.json())
    body.pop("trace_id", None)
    return body


# ══ The two absences, told apart on purpose ═════════════════════════════════
def test_cr067_b2__a_swept_record_answers_no_longer_held_rather_than_404(idn):
    """DEF-3321's own wording: *"answering 'no longer held' for a swept record
    rather than 404 with no explanation"*.

    An expired diagnostic is a NORMAL state — CR-067 struck that bargain
    deliberately, because the detail is what carries risk and so the detail is
    what expires. **And the permanent row is proved to still read correctly
    without it in the same test**, which is task A5's real acceptance criterion.

    RED-PROVED (measured, `be-expired-is-a-404`): with the view raising
    `NotFoundError()` when `held` is false — the obvious reading of "there is no
    record" — this failed with

        AssertionError: a swept record answered 404, so the screen cannot tell
        "expired" from "wrong tenant" and must show a fault for neither
        assert 404 == 200
    """
    users = idn.seed_silvercreek()
    row, reference = failed_row_with_diagnostic(idn, users)
    admin = signed_in_client(*ADMIN)
    assert api_get(admin, f"/audit-log/{row.id}/diagnostic").json()["held"] is True

    # Day 91. The sweep is task A5's, run exactly as `manage.py` runs it.
    audit_diagnostics.sweep_expired(
        [idn.silvercreek.id], now=timezone.now() + timedelta(days=91)
    )

    after_sweep = api_get(admin, f"/audit-log/{row.id}/diagnostic")
    assert after_sweep.status_code == 200, (
        "a swept record answered 404, so the screen cannot tell \"expired\" "
        "from \"wrong tenant\" and must show a fault for neither"
    )
    body = after_sweep.json()
    assert body["held"] is False
    assert body["reason"] == audit_diagnostics.REASON_NOT_HELD
    # The reference survives the record, because the PERMANENT row still carries it.
    assert body["reference"] == reference
    assert body["record"] is None

    # A5's acceptance criterion is about the row it does NOT touch.
    still_there = api_get(admin, f"/audit-log/{row.id}").json()
    assert still_there["after"]["error_code"] == "SD-PRECONDITION"
    assert still_there["after"]["reference"] == reference
    assert "not in place" in still_there["after"]["meaning"]


def test_cr067_b2__a_failure_from_before_the_reference_existed_says_so_differently(idn):
    """**The state the Product Owner meets FIRST**, because every row already in
    their log predates task A4.

    "this failure has no reference at all" and "the detail expired" are different
    facts about the world, and a screen that says the second when the first is
    true has invented a record that never existed. Two reason codes, told apart
    here so the drawer can tell them apart there.

    RED-PROVED (measured, `be-one-absence-code`): with `read_for_reference`
    returning `REASON_NOT_HELD` for a missing reference as well — one code for
    both, which is the tidier-looking version — this failed with

        AssertionError: a row that never had a reference reports the same state
        as one whose record expired
        assert 'not_held' == 'no_reference'
    """
    users = idn.seed_silvercreek()
    old = write_row(
        idn.silvercreek,
        action="sample.block_failed",
        actor=users.alex,
        # The pre-CR-067 payload: a code and a meaning, and no reference.
        after={"error_code": "SD-PRECONDITION", "meaning": "Something it needs was missing."},
    )
    admin = signed_in_client(*ADMIN)
    body = api_get(admin, f"/audit-log/{old.id}/diagnostic").json()
    assert body["held"] is False
    assert body["reason"] == audit_diagnostics.REASON_NO_REFERENCE, (
        "a row that never had a reference reports the same state as one whose "
        "record expired"
    )
    assert body["reference"] is None and body["record"] is None


def test_cr067_b2__the_route_is_read_only_by_construction(idn):
    """BR-AUD-002 / HR-4 — `get` is the only handler, so every other verb 405s
    from DRF's own dispatch. Structural, not a check somebody can forget."""
    users = idn.seed_silvercreek()
    row, _ = failed_row_with_diagnostic(idn, users)
    admin = signed_in_client(*ADMIN)
    path = f"/audit-log/{row.id}/diagnostic"
    assert api_post(admin, path).status_code == 405
    assert api_put(admin, path, {}).status_code == 405
    assert api_patch(admin, path, {}).status_code == 405
    assert api_delete(admin, path).status_code == 405


def test_cr067_b2__a_successful_read_writes_no_audit_row(idn):
    """CLAUDE.md hard rule 7 read as it is written: the trail attaches to a MONEY
    action, and no read on this screen writes one — `GET /audit-log/{id}` does
    not either. The half that IS audited is a REFUSAL, by the BE-02 handler's
    BR-AUD-018 attempt row, and that is the half a System-Admin-only door needs.
    """
    users = idn.seed_silvercreek()
    row, _ = failed_row_with_diagnostic(idn, users)
    admin = signed_in_client(*ADMIN)
    before = AuditLog.objects.filter(tenant_id=idn.silvercreek.id).count()
    assert api_get(admin, f"/audit-log/{row.id}/diagnostic").status_code == 200
    assert AuditLog.objects.filter(tenant_id=idn.silvercreek.id).count() == before


# ══ CR-067 B3 / DEF-3322 — "Errors only" ════════════════════════════════════
def seed_a_noisy_log(idn, users):
    """The shape of the reporting tenant's log: a great deal of successful
    seeding and a handful of failures buried in it.

    Twenty successes to four failures rather than 809 to a few — the ratio is
    what the assertion needs and a 809-row fixture would cost a minute per run
    for no extra proof. The 809 is real and is in `CR-067` §0; this is its shape.
    """
    for index in range(20):
        write_row(
            idn.silvercreek,
            action="sample.block_seeded" if index % 2 else "sample.block_retried",
            actor=users.alex,
            # ⚠ THE RETRY WRITES `error_code: null` WHEN IT SUCCEEDED. A filter
            # keyed on "is the key present" would call these failures.
            after={"block": f"block_{index}", "error_code": None, "outcome": "seeded"},
        )
    failures = [
        write_row(idn.silvercreek, action="sample.block_failed", actor=users.alex,
                  after={"error_code": "SD-PRECONDITION"}),
        write_row(idn.silvercreek, action="auth.lockout", actor=users.alex,
                  after={"attempts": 5}),
        write_row(idn.silvercreek, action="tenant.provision_failed", actor=None,
                  after={"step": "storage"}),
        write_row(idn.silvercreek, action="reference.sweep_failed", actor=None,
                  after={"table": "customers"}),
    ]
    return failures


def test_cr067_b3__the_filter_is_declared_and_therefore_actually_narrows(idn):
    """**THE CASE DEF-3322 IS ABOUT, AND IT BITES BY ARITHMETIC.**

    `parse_list_params` DROPS an `f.<name>` the endpoint does not declare rather
    than refusing it (BR-SHL-011 — a list param never 4xx's). So a toggle wired
    to an undeclared filter answers **200 with the whole list**, which on the
    reporting tenant's 809 rows reads as a product with no errors in it. There is
    no status code to assert on and no exception to catch: **the only symptom is
    a count that did not move.**

    RED-PROVED (measured, `be-filter-not-declared`): with `"outcome"` removed
    from `selectors.AUDIT_FILTERS` — leaving the queryset clause in place, which
    is exactly what a lane that added the clause and forgot the vocabulary would
    ship — this failed with

        AssertionError: `f.outcome=error` returned all 24 rows. An undeclared
        filter is DROPPED, not refused (BR-SHL-011), so the toggle reads as a
        product with no errors in it
        assert 24 == 4
    """
    users = idn.seed_silvercreek()
    failures = seed_a_noisy_log(idn, users)
    admin = signed_in_client(*ADMIN)

    everything = api_get(admin, "/audit-log").json()
    assert everything["count"] == 24

    narrowed = api_get(admin, "/audit-log?f.outcome=error").json()
    assert narrowed["count"] == len(failures), (
        f"`f.outcome=error` returned all {everything['count']} rows. An "
        "undeclared filter is DROPPED, not refused (BR-SHL-011), so the toggle "
        "reads as a product with no errors in it"
    )
    assert {row["id"] for row in narrowed["results"]} == {str(row.id) for row in failures}
    # The vocabulary itself, so the two halves cannot drift apart silently.
    assert "outcome" in audit_selectors.AUDIT_FILTERS


def test_cr067_b3__one_action_code_could_never_have_expressed_this(idn):
    """Why the filter is a LIST and not a value of `f.action`.

    `f.action` matches ONE code with `__iexact`. The four failures seeded here
    carry four different codes, so no single value of the filter that already
    existed finds them — which is DEF-3322's whole argument, asserted rather than
    described.
    """
    users = idn.seed_silvercreek()
    failures = seed_a_noisy_log(idn, users)
    admin = signed_in_client(*ADMIN)
    assert len({row.action for row in failures}) == 4
    for action in {row.action for row in failures}:
        found = api_get(admin, f"/audit-log?f.action={action}").json()
        assert found["count"] == 1, "one action code should reach exactly one of these"
    assert api_get(admin, "/audit-log?f.outcome=error").json()["count"] == 4


def test_cr067_b3__every_code_in_the_list_is_one_a_writer_actually_emits(idn):
    """**The check nothing in this repo had, and it is DEF-3322's escape reason.**

    *"Nothing compares a CR task against the API it would need."* A list of
    action codes copied out of a defect row and never checked against the
    writers is a filter that silently stops finding a failure the day somebody
    renames one — and the symptom is again a count that did not move.

    So each of the eight is grepped for in the backend source. One of them,
    `customer.not_created`, very nearly did not survive this check: the obvious
    grep finds `customer_not_created`, a payload KEY in two other modules, and
    the real writer is one line in `apps/customers/services.py`.
    """
    backend = Path(__file__).resolve().parents[1]
    sources = list((backend / "apps").rglob("*.py")) + list((backend / "core").rglob("*.py"))
    text = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    for action in audit_selectors.FAILURE_ACTIONS:
        assert f'"{action}"' in text, (
            f"{action!r} is in the Errors-only list and no writer in this "
            "codebase emits it — the filter would silently stop finding it"
        )
    assert len(set(audit_selectors.FAILURE_ACTIONS)) == 8


def test_cr067_b3__a_refusal_a_person_chose_is_not_an_error(idn):
    """`service_request.refused` is written when a member of staff turns an
    application DOWN. It worked exactly as designed, and putting it in a list
    labelled "Errors only" would make a clean log read as full of faults.

    The PO's ask names the other thing in as many words — *"errors will happen
    run time and it is very difficult to reproduce those"*. Pinned here so the
    next lane that notices the code does not helpfully add it.
    """
    assert "service_request.refused" not in audit_selectors.FAILURE_ACTIONS
    users = idn.seed_silvercreek()
    seed_a_noisy_log(idn, users)
    write_row(idn.silvercreek, action="service_request.refused", actor=users.alex,
              after={"reason_code": "arrears"})
    admin = signed_in_client(*ADMIN)
    assert api_get(admin, "/audit-log?f.outcome=error").json()["count"] == 4


def test_cr067_b3__an_unknown_outcome_value_falls_back_and_never_4xxs(idn):
    """BR-SHL-011 — an invalid value falls back, never errors, and the fallback
    is the WIDE list rather than an empty one.

    Same posture as `wants_archive`: only the recognised token acts, so a typo
    can never quietly change which rows a person is looking at. An empty result
    would be the worse failure here — it would read as "no errors" for a value
    nobody typed on purpose.
    """
    users = idn.seed_silvercreek()
    seed_a_noisy_log(idn, users)
    admin = signed_in_client(*ADMIN)
    for value in ("ERROR", "error", "  error  "):
        assert api_get(admin, f"/audit-log?f.outcome={value}").json()["count"] == 4
    for value in ("errors", "failure", "true", "1", ""):
        response = api_get(admin, f"/audit-log?f.outcome={value}")
        assert response.status_code == 200
        assert response.json()["count"] == 24, f"f.outcome={value!r} narrowed something"


def test_cr067_b3__errors_only_ANDs_with_the_filters_already_on_the_toolbar(idn):
    """Every filter on this screen narrows (BR-SHL-011). A person who has typed
    an action code and then ticks Errors only is asking for both, and when the
    two disagree an empty list is TRUE — a wider one would have quietly ignored
    the tick."""
    users = idn.seed_silvercreek()
    seed_a_noisy_log(idn, users)
    admin = signed_in_client(*ADMIN)
    both = api_get(admin, "/audit-log?f.outcome=error&f.action=auth.lockout").json()
    assert both["count"] == 1
    disagreeing = api_get(admin, "/audit-log?f.outcome=error&f.action=sample.block_retried").json()
    assert disagreeing["count"] == 0
    # The actor filter narrows inside it too — `tenant.provision_failed` and
    # `reference.sweep_failed` were written by a system job (BR-AUD-003).
    mine = api_get(admin, f"/audit-log?f.outcome=error&f.actor={users.alex.id}").json()
    assert mine["count"] == 2


def test_cr067_b3__the_export_carries_the_filter_the_person_was_looking_at(idn, job_store):
    """IS-9 / BR-AUD-014: the export covers the caller's CURRENT filters. A
    toggle the list honours and the export ignores would hand somebody a 809-row
    CSV when they asked for four rows."""
    users = idn.seed_silvercreek()
    seed_a_noisy_log(idn, users)
    admin = signed_in_client(*ADMIN)
    accepted = api_post(admin, "/audit-log/export?f.outcome=error")
    assert accepted.status_code == 202
    record = job_store.records[accepted.json()["job_id"]]
    assert record["payload"]["filters"]["outcome"] == "error"


@pytest.fixture()
def job_store():
    """BE-07 duck-typed store — save-and-restore, because apps.tenancy registers
    the REAL one at startup and handing back None would strand later tests."""
    from core import jobs as core_jobs

    class FakeJobStore:
        def __init__(self):
            self.records: dict[str, dict] = {}

        def save(self, record):
            self.records[record["id"]] = record

        def get(self, job_id):
            return self.records.get(job_id)

        def find_active(self, tenant_id, kind, scope_key):
            return None

    previous = core_jobs._store
    store = FakeJobStore()
    core_jobs.set_job_store(store)
    yield store
    core_jobs.set_job_store(previous)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-067 tasks B2 (the System-Admin diagnostic read) and B3 (the Errors-only filter) — 12-governance/11-change-requests.md §6; defects DEF-3321 and DEF-3322; shared law CLAUDE.md hard rules 1 and 7, hard-won laws 2 and 7, BR-AUD-002/007/009, BR-SHL-011/025, B14 rules 31 and 32
# generated: 2026-09-02 by the CR-067 B2/B3 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: (1) the 809-row figure from CR-067 §0 is represented by a 24-row fixture in the same SHAPE (20 successes, 4 failures across 4 different codes) — the assertion is about the ratio and the code spread, and a 809-row fixture would cost a minute a run for no extra proof. (2) the database half of the diagnostic's RLS is NOT proved here and is not claimed: `config/settings/test.py` hardcodes SQLite and the container's role is `rolsuper=True` (measured 2026-09-02), so the app-layer scope is what these cases bite on — the policy's own text is asserted by tests/test_be10_partitioning.py and the behavioural half is the G5 isolation suite's, under a NOSUPERUSER role, and is OWED.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
