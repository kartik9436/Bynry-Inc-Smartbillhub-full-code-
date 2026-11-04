# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2734 (2026-08-31) — BOTH rejects downloads came back EMPTY on a
#           database that actually enforces RLS: a header row and nothing under
#           it, which a clerk reads as "nothing was rejected".
# Rules:    CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE) ·
#           BR-MET-941 (the rejects export on a read batch) ·
#           BR-CUS-051 / PO 2026-08-29 ("at the end we need 2 CsV file 1 for
#           success record and other for failed records") ·
#           hard-won law 7 (prove a guard RED before trusting it green) ·
#           hard-won law 14 (the suite's SQLite cannot see a Postgres truth).
# Tests:    this file. Postgres-only, and it FAILS rather than skips when the
#           connected role could bypass row-level security.
# Impacts:  06-backend/core/tenancy.py (stream_within_tenant_context) ·
#           06-backend/apps/metering/api.py (the two StreamingHttpResponse
#           call sites) · 10-scripts/gates/g58_streamed_tenant_context.py
# ───────────────────────────────────────────────────────
"""A STREAMED response body is consumed AFTER the tenant context is gone.

⛔ **THE DEFECT, IN ITS OWN NUMBERS.** A read batch whose screen said *"2 rows
will not post"* answered `GET /read-batches/{id}/results.csv?kind=failures`
with **200**, one header line and **zero** data rows. The account importer's
`GET /imports/{run_id}/results.csv?kind=failures` did the same, and worse — its
header came back as `why_it_failed,how_to_fix_it` alone, because
`_source_headers`' pre-`DEF-2513` fallback is a query inside the generator too,
so on a run whose column order has to be re-derived from its rows — which is
every run on the shared development database — the operator's own nine columns
were denied along with them. (A run that stored its order keeps its header,
because `run.mapping_spec` is already in memory; the ROWS are lost either way.
That boundary was measured, not assumed — see the two importer cases below.)

`StreamingHttpResponse` returns from the view with its body unconsumed.
`TenantContextMiddleware` clears `app.tenant_id` in a `finally` the moment the
view returns, and WSGI iterates the body afterwards — so the generator's first
query runs with no tenant marker, the policy's
`NULLIF(current_setting('app.tenant_id', true), '')::uuid` is NULL, and the
queryset yields nothing. Nothing raises. The download succeeds. The file is
empty.

⛔⛔ **WHY THIS FILE EXISTS AT ALL, AND WHY IT IS SHAPED THE WAY IT IS.**
Two existing tests cover these exact routes end to end —
`test_cr047_per_record_load.py::test_task13__the_endpoint_streams_csv_with_a_filename`
and `test_cr054_w24_backend.py::test_task16__the_route_is_mounted_and_streams` —
and **NEITHER COULD EVER HAVE FAILED ON THIS**, for two independent reasons:

  1. `config/settings/test.py` hardcodes in-memory SQLite and ignores
     `DATABASE_URL`. **SQLite has no row-level security at all**, so the late
     query simply succeeds there. (CLAUDE.md law 14, one module over.)
  2. Both assert on the CSV **header**, which is a Python constant every
     generator yields before it queries anything. `assert b"account_number" in
     b"".join(response.streaming_content)` is true over an empty file.

And on a real Postgres it was invisible for a third reason: a SUPERUSER or a
`BYPASSRLS` role skips RLS completely, FORCE included, while every table still
reports `relrowsecurity=t`. The render check that found this **passed twice on
this same database an hour earlier**, and the only thing that changed was a
sibling lane revoking the superuser bit it had granted itself (`DEF-2717`).

So this file:
  * runs **only on live PostgreSQL** (`requires_postgres`), and
  * **FAILS, never skips**, if the connected role could bypass RLS
    (`assert_connection_is_subject_to_rls` below — the canary), and
  * asserts **ROW COUNTS**, never the header alone.

⚠ **`api_call` IS THE FAITHFUL VEHICLE AND THAT IS NOT AN ACCIDENT.** It enters
`core_tenancy.tenant_context(tenant.id)` around the view and exits it when the
view **returns** — which is exactly what `TenantContextMiddleware.__call__`'s
`finally` does in production. Consuming `response.streaming_content` after it
returns therefore reproduces the WSGI sequence with no HTTP stack at all. That
is also precisely why the two tests above were written against it and still saw
nothing.

── PROVED RED FIRST (law 7), ON THE REAL CONDITION ─────────────────────────
With `stream_within_tenant_context` removed from `apps/metering/api.py` — the
code exactly as it stood when the defect was filed — against
`postgres://smartbillhub@localhost/…` under a role with
`rolsuper=f, rolbypassrls=f`:

    FAILED tests/test_def2734_streamed_tenant_context.py::
      test_the_read_batch_rejects_file_still_has_its_rows_after_the_request_ends
    E   AssertionError: the rejects file came back with 0 data row(s) where the
        batch holds 2 held row(s). That is DEF-2734: ...
    E   assert 0 == 2

    FAILED tests/test_def2734_streamed_tenant_context.py::
      test_the_account_importer_rejects_file_keeps_its_rows
    E   AssertionError: the importer's failures file came back with 0 data
        row(s) where the run holds 1 failed row(s). ...
    E   assert 0 == 1

    FAILED tests/test_def2734_streamed_tenant_context.py::
      test_the_importer_failures_file_keeps_the_operators_own_columns
    E   AssertionError: the operator's OWN columns are missing from the header
        ... Got: ['why_it_failed', 'how_to_fix_it']

FIVE of the eight cases failed that way; the other three are the canary, the
malformed-tenant refusal and the save-and-restore property, none of which the
route can break. With the wrapper restored: **8 passed**.

The same cases on the DEFAULT suite (SQLite) SKIP with a vendor reason rather
than passing — a check that cannot fail is worse than no check, and this repo
has recorded that five times.
"""

import csv
import io

import pytest
from django.db import connection

from apps.metering import api as metering_api
from apps.metering import import_runs, models, services
from core import tenancy as core_tenancy

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    csv_body,
    marcus,
    seed_config,
    stage,
    tenant_ctx,
)
from tests.test_us_met_helpers import seed_physical_series, staff_actor
from tests.test_us_ten_helpers import (
    FakeUser,
    api_call,
    brazosbend_payload,
    provisioned_tenant,
)

#: ⚠ **`isolation` IS THE POINT, NOT A LABEL.** `G5` runs `pytest -m isolation`,
#: and that is the ONE invocation in this repo that is documented to be pointed
#: at a real PostgreSQL (`isolation_helpers`' own instructions). A live-Postgres
#: RLS proof filed anywhere else runs only when a person remembers to name the
#: file — which is how `DEF-2734` reached two features. Every case here carries
#: `requires_postgres`, never a bare `skip`, so `G5`'s own no-unconditional-skip
#: clause holds. Under `-m isolation` with the default settings these skip with a
#: vendor reason; against Postgres they run (measured: 8 passed).
pytestmark = [pytest.mark.django_db, pytest.mark.isolation]


# ⚠ **THIS FILE ONCE CARRIED AN OVERRIDE OF `sqlite_guc`, AND IT NO LONGER NEEDS
# ONE — say so rather than leaving the next reader to wonder.** The shared
# `autouse` fixture in `tests/test_us_ten_helpers.py` used to monkeypatch
# `core.tenancy.connection` with a recorder UNCONDITIONALLY, which on Postgres
# meant the shipping kernel never marked the session and every assertion here
# would have measured zero rows **for the wrong reason** — indistinguishable
# from the defect. A sibling lane vendor-guarded that fixture the same day
# (`DEF-2761`, and `G57` now refuses an unguarded one), so the real GUC reaches
# the database on Postgres and the recorder survives only on sqlite, where it
# has to.


@pytest.fixture()
def brazos(growth_plan, identity_seam):  # noqa: F811 — deliberate override, see below
    """Brazos Bend, built the shared way but with its LAST step inside context.

    ⚠ **The shared `brazos` calls `seed_physical_series(tenant)` OUTSIDE any
    tenant context**, which is lawful everywhere it runs today — on SQLite there
    are no policies, and on Postgres the shared `sqlite_guc` fake means no
    session ever carries a marker, so `WITH CHECK` has nothing to refuse. With
    the real kernel in the path it is refused, loudly and correctly:

        psycopg.errors.InsufficientPrivilege: new row violates row-level
        security policy for table "number_series"

    That refusal is the product working. Rather than weaken it, this fixture
    puts the seed where a real caller would be — inside the tenant it is seeding
    (`core.tenancy.tenant_context`, the same door background jobs use). Nothing
    about the shared fixture is otherwise changed, and it is overridden here
    rather than edited because 30-odd files depend on its current shape.
    """
    tenant, _result = provisioned_tenant(brazosbend_payload())
    with core_tenancy.tenant_context(tenant.id):
        seed_physical_series(tenant)
    return tenant


@pytest.fixture()
def dana(brazos):  # noqa: F811 — deliberate override, same reason as `brazos`
    """Dana Whitfield, Brazos Bend System Admin — created INSIDE her tenant.

    `staff_actor` inserts a real `users` row, and `users` carries the same
    policy every other tenant table does:

        psycopg.errors.InsufficientPrivilege: new row violates row-level
        security policy for table "users"
    """
    with core_tenancy.tenant_context(brazos.id):
        return staff_actor(brazos, "system_admin", "dana@brazosbendutilities.test")


@pytest.fixture()
def marcus(brazos):  # noqa: F811 — deliberate override, same reason as `brazos`
    """Marcus Vega, Brazos Bend Billing Clerk — created INSIDE his tenant."""
    with core_tenancy.tenant_context(brazos.id):
        return staff_actor(brazos, "billing_clerk", "marcus@brazosbendutilities.test")


# ═══════════════════════════════════════════════════════════════════════════
# THE CANARY — is anything below a proof at all?
# ═══════════════════════════════════════════════════════════════════════════
def assert_connection_is_subject_to_rls() -> tuple[bool, bool]:
    """FAIL (never skip) if the role this suite connects as bypasses RLS.

    ⚠ **`isolation_helpers.RlsProbe.assert_is_a_real_proof` asks this of the
    `sbh_rls_probe` role. This file needs it of `current_user`**, because the
    whole defect is about a query the SHIPPING code makes on the SHIPPING
    connection — there is no probe role in the path and putting one there would
    test something other than the product.

    A superuser bypasses row-level security COMPLETELY, FORCE included, and
    nothing says so out loud: the tables still report `relrowsecurity=t`, the
    policies still exist, and every query still returns the right rows. That is
    how `DEF-2734` survived two features, and how `DEF-2717` published a whole
    benchmark measured against no tenant predicate at all.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        row = cursor.fetchone()
    assert row is not None, "current_user has no pg_roles row — cannot tell if RLS applies"
    rolsuper, rolbypassrls = bool(row[0]), bool(row[1])
    assert not rolsuper, (
        "this suite is connected as a SUPERUSER, which bypasses row-level security "
        "completely (FORCE included) while every table still reports "
        "relrowsecurity=t. Every assertion below would pass with the defect fully "
        "present — that is DEF-2734's own escape route and DEF-2717's. Connect as a "
        "role with rolsuper=false, rolbypassrls=false."
    )
    assert not rolbypassrls, (
        "this suite is connected as a role carrying BYPASSRLS — same vacuity as a "
        "superuser. Connect as a role with rolsuper=false, rolbypassrls=false."
    )
    return rolsuper, rolbypassrls


@requires_postgres
def test_the_role_this_suite_runs_as_is_genuinely_subject_to_rls():
    """The canary itself, asserted as its own case so a vacuous run is a NAMED
    failure rather than a silently green file.

    ⚠ It also checks that the two tables in the path really carry `FORCE` —
    the table OWNER bypasses a policy without it, and this app's role owns
    every table it reads.
    """
    assert_connection_is_subject_to_rls()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname IN ('read_import_rows', 'import_run_rows')"
        )
        found = {name: (rls, force) for name, rls, force in cursor.fetchall()}
    assert found, "neither read_import_rows nor import_run_rows exists in this database"
    for table, (rls, force) in sorted(found.items()):
        assert rls, f"{table} has row-level security DISABLED — nothing below proves anything"
        assert force, (
            f"{table} has RLS but not FORCE, and this connection's role OWNS it — "
            "an owner bypasses a non-FORCE policy, so the assertions below are vacuous"
        )


def _data_rows(text: str) -> list[list[str]]:
    """Every line of a CSV EXCEPT the header, parsed.

    ⚠ **Parsed with `csv`, not split on newlines.** A `how_to_fix_it` sentence
    is quoted and contains commas; one of them contains an em dash and a
    sentence break. Counting `\\n` would over-count and the assertion would be
    green for the wrong reason.
    """
    rows = list(csv.reader(io.StringIO(text)))
    return [row for row in rows[1:] if row]


def _header(text: str) -> list[str]:
    return next(iter(csv.reader(io.StringIO(text))), [])


# ═══════════════════════════════════════════════════════════════════════════
# THE READ BATCH'S REJECTS FILE — the file the PO asked about by name
# ═══════════════════════════════════════════════════════════════════════════
@requires_postgres
def test_the_read_batch_rejects_file_still_has_its_rows_after_the_request_ends(brazos, marcus):
    """**The headline.** 3 rows, 1 unknown meter and 1 more: the file the clerk
    downloads at the end names the rows that did not post.

    The body is consumed AFTER `api_call` has left the tenant context — the
    production sequence, because `TenantContextMiddleware` clears
    `app.tenant_id` the instant the view returns and WSGI iterates afterwards.
    """
    assert_connection_is_subject_to_rls()
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        batch = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-9999,2026-08-03,100,total,E,",  # no such meter — held
                "M-7002,2026-08-03,900,total,E,",
                "M-9998,2026-08-03,101,total,E,",  # no such meter — held
            ),
        )
        services.validate_read_batch(marcus, batch["id"])
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        held = result["held_reads"]

    # ⚠ The view is called INSIDE the context and the body is read OUTSIDE it.
    response = api_call(
        metering_api.read_batch_results_csv,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
        query={"kind": "failures"},
        batch_id=batch["id"],
    )
    assert core_tenancy.current_tenant_id() is None, (
        "api_call left tenant context standing, so this case is no longer "
        "reproducing what the middleware does and cannot see DEF-2734"
    )
    text = b"".join(response.streaming_content).decode("utf-8")

    rows = _data_rows(text)
    assert held == 2, f"the fixture should hold 2 rows, not {held}"
    assert len(rows) == held, (
        f"the rejects file came back with {len(rows)} data row(s) where the batch holds "
        f"{held} held row(s). That is DEF-2734: the generator behind "
        "StreamingHttpResponse is consumed after TenantContextMiddleware cleared "
        "app.tenant_id, RLS denies on an unset marker, and an EMPTY rejects file reads "
        "as 'nothing was rejected'."
    )
    meters = {row[1] for row in rows}
    assert meters == {"M-9999", "M-9998"}, f"the held meters are not in the file: {meters}"
    assert _header(text)[:2] == ["row_key", "meter_id"]
    # The rows that DID post are not handed back as rejects.
    assert "M-7001" not in text and "M-7002" not in text


@requires_postgres
def test_the_read_batch_successes_file_is_covered_by_the_same_fix(brazos, marcus):
    """The OTHER half of the same endpoint, which the defect row did not name
    and which had the identical fault: `?kind=successes` streams
    `_successes_csv`, whose FIRST statement after the header is a query."""
    assert_connection_is_subject_to_rls()
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        batch = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-7002,2026-08-03,900,total,E,",
            ),
        )
        services.validate_read_batch(marcus, batch["id"])
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        posted = result["posted_reads"]

    response = api_call(
        metering_api.read_batch_results_csv,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
        query={"kind": "successes"},
        batch_id=batch["id"],
    )
    rows = _data_rows(b"".join(response.streaming_content).decode("utf-8"))
    assert posted == 2
    assert len(rows) == posted, (
        f"the successes file came back with {len(rows)} row(s) where the batch posted "
        f"{posted}. Same mechanism as the failures half — DEF-2734."
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE ACCOUNT IMPORTER'S FILE — CR-047's half of the same defect
# ═══════════════════════════════════════════════════════════════════════════
def _importer_failures_csv(brazos, dana, *, forget_stored_headers: bool = False) -> tuple[str, int]:
    """A real 2-row accounts migration with exactly one bad row, downloaded the
    way a browser downloads it: the view called inside tenant context, the body
    read after that context is gone.

    `forget_stored_headers` reproduces a run extracted BEFORE `DEF-2513` stored
    the file's column order as a list — `_source_headers`' documented fallback,
    and the state every run on the shared development database is actually in
    (`mapping_spec IS NULL` on `RUN-2822`, measured 2026-08-31).

    Returns `(csv text, how many rows the run actually failed)`.
    """
    from tests.test_cr047_per_record_load import CUTOVER, HEADERS, _run, _units

    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=2)
        content = (
            f"{HEADERS}\n"
            # ⚠ TEN COLUMNS, NOT EIGHT. `HEADERS` gained `KIND` and `SSN`, and
            # these two rows still carried the old eight — so BOTH were rejected
            # with *"'Harmon' has a name and no way to identify them"* and the
            # run failed 2 rows where this case needs exactly 1. The refusal is
            # the product working: a customer with a name and no identifier
            # cannot be told apart from another, and the rule says so with the
            # clerk's own fix in the sentence. Row 2 still fails, and now it
            # fails for the reason this case is about — `NOT-A-UNIT`.
            f"{units[0]['unit_no']},A-D2734-1,Harmon,CUST-1,residential,active,"
            "2024-02-12,0.00,person,123-45-6789\n"
            "NOT-A-UNIT,A-D2734-2,Ellis,CUST-2,residential,active,"
            "2024-02-12,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        if forget_stored_headers:
            models.ImportRun.objects.filter(pk=run_id).update(mapping_spec=None)
        failed = models.ImportRunRow.objects.filter(
            run_id=run_id, outcome__in=import_runs.RESULT_KINDS["failures"]
        ).count()

    response = api_call(
        metering_api.import_results_csv,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
        query={"kind": "failures"},
        run_id=run_id,
    )
    return b"".join(response.streaming_content).decode("utf-8"), failed


@requires_postgres
def test_the_account_importer_rejects_file_keeps_its_rows(brazos, dana):
    """**The second feature — CR-047's half of the same defect.**

    PO 2026-08-29: *"at the end we need 2 CsV file 1 for success record and
    other for failed records"*. One row of the two names a unit that is not on
    file; that row is what the operator is promised back.
    """
    assert_connection_is_subject_to_rls()
    text, failed = _importer_failures_csv(brazos, dana)

    assert failed == 1, f"the fixture should fail exactly 1 row, not {failed}"
    rows = _data_rows(text)
    assert len(rows) == failed, (
        f"the importer's failures file came back with {len(rows)} data row(s) where the "
        f"run holds {failed} failed row(s) — DEF-2734, the same lazy generator consumed "
        "after the tenant context was cleared."
    )
    assert "NOT-A-UNIT" in text and "A-D2734-1" not in text


@requires_postgres
def test_the_importer_failures_file_keeps_the_operators_own_columns(brazos, dana):
    """**The HEADER half — and it is narrower than the first diagnosis said, so
    it is asserted on its own and the boundary is written down.**

    `_failures_csv` calls `_source_headers(run)` INSIDE the generator. That
    reads `run.mapping_spec["source_headers"]` — **already in memory**, because
    `results_csv` fetched the run inside the request — so on a MODERN run the
    header survives an empty body. It is the documented FALLBACK that is a
    query: a run extracted before `DEF-2513` stored the order as a list has to
    re-derive it from `ImportRunRow`, and on a context-less connection that
    returns nothing.

    ⚠ **That fallback is not a museum piece: it is the state of every run on the
    shared development database** (`mapping_spec IS NULL` on `RUN-2822`), which
    is why the file downloaded in a browser on 2026-08-31 came back as

        why_it_failed,how_to_fix_it

    with the operator's own nine columns gone. A two-column file is a different
    lie from an empty one — an empty one says *"nothing failed"*, this one says
    *"the export is broken"* — and `BR-CUS-673`'s "not re-ordered" exists so the
    operator can fix two cells in the spreadsheet they already know and upload
    it again.

    Proved RED against the pre-fix route:

        E   AssertionError: the operator's OWN columns are missing from the
            header ... Got: ['why_it_failed', 'how_to_fix_it']
    """
    from tests.test_cr047_per_record_load import HEADERS

    assert_connection_is_subject_to_rls()
    text, _failed = _importer_failures_csv(brazos, dana, forget_stored_headers=True)

    header = _header(text)
    expected = HEADERS.split(",")
    assert set(header[:-2]) == set(expected), (
        "the operator's OWN columns are missing from the header. `_source_headers(run)`'s "
        "pre-DEF-2513 fallback is a QUERY, so on a context-less connection it returned [] "
        "and the file came back as the two appended columns alone — DEF-2734's second "
        f"symptom, and the one a browser actually met. Got: {header}"
    )
    assert header[-2:] == ["why_it_failed", "how_to_fix_it"]
    # ⚠ **THE SET, NOT THE ORDER, AND ONLY ON THIS PATH.** `_source_headers`'
    # fallback re-derives the order from a jsonb object, which does not keep
    # one — that is `DEF-2513`, closed by storing the order as a LIST, and its
    # own docstring says a historical run's columns "may be re-sorted". Pinning
    # the order here would make this case fail on a defect it is not about.
    # Order for a MODERN run is `test_cr047_per_record_load`'s to assert, and it
    # does; what DEF-2734 broke, and what is asserted here, is whether the
    # columns arrive at all.


# ═══════════════════════════════════════════════════════════════════════════
# THE WRAPPER'S OWN CONTRACT — it must not become a leak of its own
# ═══════════════════════════════════════════════════════════════════════════
@requires_postgres
def test_the_tenant_marker_is_gone_again_once_the_body_is_finished(brazos, marcus):
    """The fix may not trade one hard-rule-1 problem for another.

    A pooled connection must never be handed back carrying a tenant marker, so
    the wrapper's `finally` is asserted here rather than assumed: after the last
    chunk, `app.tenant_id` is empty again on the real session.
    """
    assert_connection_is_subject_to_rls()
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        batch = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-9999,2026-08-03,100,total,E,",
            ),
        )
        services.validate_read_batch(marcus, batch["id"])
        services.commit_read_batch(marcus, batch["id"], {"certified": True})

    response = api_call(
        metering_api.read_batch_results_csv,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
        query={"kind": "failures"},
        batch_id=batch["id"],
    )
    assert _data_rows(b"".join(response.streaming_content).decode("utf-8"))

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.tenant_id', true)")
        left_behind = cursor.fetchone()[0] or ""
    assert left_behind == "", (
        f"the streamed body left app.tenant_id set to {left_behind!r} on the session. "
        "On a pooled connection that is the next request's tenant — CLAUDE.md hard "
        "rule 1, and the reason the wrapper restores rather than merely sets."
    )
    assert core_tenancy.current_tenant_id() is None


@requires_postgres
def test_a_marker_the_wrapper_found_is_put_back_and_not_cleared(brazos, marcus):
    """**Save-and-restore, not `tenant_context`** — the one design choice in
    `stream_within_tenant_context` that a reader would otherwise be tempted to
    simplify away.

    `tenant_context` CLEARS on exit. That is right for a background job which
    owns the connection and wrong for a body consumed while its caller is still
    inside its own context: the join would strip the caller's context out from
    under it, and every existing test of these two routes does exactly that.
    """
    assert_connection_is_subject_to_rls()
    with tenant_ctx(brazos) as tid:
        body = core_tenancy.stream_within_tenant_context(brazos.id, iter(["a", "b"]))
        assert list(body) == ["a", "b"]
        assert core_tenancy.current_tenant_id() == tid, (
            "the wrapper CLEARED a context it found instead of restoring it — a caller "
            "that consumes the body inside its own context would lose it"
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            assert cursor.fetchone()[0] == str(tid)


@requires_postgres
def test_the_wrapper_refuses_a_malformed_tenant_inside_the_request(brazos):
    """`_as_uuid` runs EAGERLY, so a malformed id fails where a person can see
    it rather than half-way down a file a clerk has already started saving."""
    assert_connection_is_subject_to_rls()
    with pytest.raises(ValueError):
        core_tenancy.stream_within_tenant_context("not-a-uuid", iter(["a"]))
