# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2722 (2026-08-31) — a newly signed-up utility got 70 premises,
#           118 units and 69 meters and **ZERO accounts and ZERO customers**,
#           while the sample-plant job record read `succeeded`.
# Rules:    CLAUDE.md hard-won law 14 (a failed statement poisons the whole
#           PostgreSQL transaction; a SAVEPOINT is the only option, and the
#           default suite runs on SQLite which cannot show you) · law 2 (built
#           is not wired — a count returned and never compared) · law 7 (prove
#           a new guard RED first) · rule 1 (tenant scoping, RLS FORCE) ·
#           rule 7 (every money action writes audit_log) · BR-TEN-063 (atomic
#           per module, idempotent) · BR-TEN-060 (a short block is NAMED)
# Tests:    this file. `06-backend/apps/customers/sample_data.py` is the code.
# ───────────────────────────────────────────────────────
"""DEF-2722 — the sample plant survives one row's refusal, and says when it did not.

⚠ **EVERY CASE HERE IS `@requires_postgres`, AND THAT IS THE POINT OF THE FILE
RATHER THAN A DETAIL OF IT.** `config/settings/test.py` hardcodes in-memory
SQLite and ignores `DATABASE_URL` (CLAUDE.md law 14 names that file by name),
and **SQLite has no aborted-transaction state**. So the broken version of
`apps/customers/sample_data.py` passes the entire default suite, green, on every
machine — which is exactly how this reached a running product. Run these under

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      DATABASE_URL=postgres://… pytest tests/test_def2722_sample_plant_survives.py \\
      --reuse-db

and under a role RLS actually applies to (`rolsuper=false`,
`rolbypassrls=false`) — `tc0` asserts that before anything else, so a run on a
superuser connection FAILS rather than proving nothing.

WHAT WAS MEASURED, and it is what these cases pin
--------------------------------------------------
One tenant provisioned through `tenancy.services.provision_tenant` plus the
sample-plant job it enqueues, on PostgreSQL 16, on a database one migration
behind so that `disconnect_cases.status_before_cut` did not exist:

    BEFORE   70 premises · 118 units · 69 meters ·  0 accounts ·  0 customers
    AFTER    70 premises · 118 units · 69 meters · 73 accounts · 65 customers

The 48 accounts HAD been created both times. `_seed_w7_disconnects` — a later,
unrelated sub-fixture in the same block — then hit the missing column, caught it
at INFO and continued into a dead transaction, and the block's own `atomic()`
rolled the accounts back. Eight of fourteen blocks failed; seven only as its
cascade.

EACH CASE'S RED PROOF IS QUOTED IN ITS OWN DOCSTRING (law 7), because a green
check that cannot fail is worse than no check. And **`0 == 0` satisfies every
relational assertion**, so no count here is checked by a relation alone: each is
asserted **greater than zero AND** against the number the fixture plans, which
is read from `fixture.account_plan()` rather than typed in — a hardcoded 48 that
drifts to 0 with the fixture would keep passing.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from django.db import connection

from apps.customers import models as customer_models
from apps.customers import sample_data as customer_sample_data
from apps.customers import services as customer_services
from apps.metering import models as metering_models
from apps.tenancy import sample_data as tenancy_sample_data
from core import sample_fixture as fixture

from tests.isolation_helpers import requires_postgres
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = [pytest.mark.django_db, requires_postgres]

#: The block whose loss is the defect. `SAMPLE_MODULES` is the orchestrator's
#: own list, so this cannot drift into naming a block that no longer exists.
ACCOUNTS_BLOCK = "customers:seed_sample_records"

#: A table no migration creates, so touching it is a genuine PostgreSQL
#: `ProgrammingError` — the SAME class the real defect produced — and not a
#: Python exception dressed up as one. A synthetic `raise ValueError` would
#: NOT abort the transaction and the guard would pass on the broken code.
NO_SUCH_TABLE = "def2722_no_such_table"


def _payload(slug: str) -> dict:
    """One signup payload per tenant, so cases cannot see each other's rows."""
    data = dict(brazosbend_payload())
    data["subdomain"] = slug
    data["name"] = f"DEF-2722 {slug}"
    owner = dict(data["owner"])
    owner["email"] = f"owner@{slug}.test"
    data["owner"] = owner
    return data


def _fresh_tenant():
    """A tenant AND the actor the production plant would use — its own owner.

    ⚠ **NOT `admin_actor()`, AND THE DIFFERENCE IS NOT COSMETIC.** That helper
    invents a uuid that no `users` row carries, and `apps.tenancy.sample_data
    ._attributed` then strips it, so `BR-BIL-058`'s release gate refuses to
    issue a bill (*"this sample load has no attributable user"*) and five money
    blocks fail for a reason that has nothing to do with this defect. The real
    job body builds `_PlantActor(record["payload"]["actor_user_id"])` from the
    provisioning owner; this is the same actor, so what the cases exercise is
    the path a signup actually walks.
    """
    tenant, result = provisioned_tenant(_payload(f"def2722-{uuid.uuid4().hex[:10]}"))
    owner_id = result["owner_user_id"]
    actor = SimpleNamespace(
        id=uuid.UUID(str(owner_id)),
        pk=uuid.UUID(str(owner_id)),
        role="system_admin",
        roles=("system_admin",),
        is_authenticated=True,
    )
    return tenant, actor


def _seed_up_to_accounts(actor) -> None:
    """Run every block BEFORE the Accounts block, through the orchestrator's own
    list, so the estate these cases seat accounts on is the real one.

    Deliberately not the whole plant: the money blocks downstream take minutes
    and this file's subject is what the Accounts block does when a row refuses.
    `tc1` runs the WHOLE plant and is what proves the end state.
    """
    from importlib import import_module

    for spec in tenancy_sample_data.SAMPLE_MODULES:
        if spec.key == ACCOUNTS_BLOCK:
            return
        services = import_module(f"apps.{spec.module}.services")
        seam = getattr(services, spec.seam, None)
        if seam is not None:
            seam(actor)


def _break_one_account(monkeypatch, *, unit_nos: set[str] | None) -> dict:
    """Make `create_account` hit a missing table for the named units.

    `unit_nos=None` breaks EVERY unit. The call goes through the real service
    for every other unit, so what the case measures is the plant surviving, not
    a fake.
    """
    real = customer_services.create_account
    broken: dict[str, int] = {"count": 0}

    def wrapper(actor, payload, *args, **kwargs):
        unit_id = payload.get("unit_id")
        unit_no = (
            metering_models.Unit.objects.filter(pk=unit_id).values_list("unit_no", flat=True).first()
            if unit_id
            else None
        )
        if unit_nos is None or unit_no in unit_nos:
            broken["count"] += 1
            with connection.cursor() as cur:
                cur.execute(f"SELECT 1 FROM {NO_SUCH_TABLE}")  # noqa: S608 — constant
        return real(actor, payload, *args, **kwargs)

    monkeypatch.setattr(customer_services, "create_account", wrapper)
    monkeypatch.setattr(customer_sample_data.services, "create_account", wrapper)
    return broken


def test_def2722_tc0__the_connection_is_actually_subject_to_rls():
    """The role these cases run as must NOT bypass row-level security.

    Copied from `tests/isolation_helpers.py`'s own reasoning: a superuser
    bypasses RLS unconditionally, so every tenant-scoped count below would be
    measuring the whole database and would pass having proven nothing. This
    FAILS rather than skips, because a silent downgrade is the failure mode the
    whole file exists to avoid.

    RED PROOF: run the suite as `postgres` and it reports
        AssertionError: DEF-2722's counts would be VACUOUS: role postgres has
        rolsuper=True rolbypassrls=True
    """
    with connection.cursor() as cur:
        cur.execute("SELECT current_user")
        who = cur.fetchone()[0]
        cur.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = %s", [who])
        rolsuper, bypass = cur.fetchone()
    assert not rolsuper and not bypass, (
        f"DEF-2722's counts would be VACUOUS: role {who} has "
        f"rolsuper={rolsuper} rolbypassrls={bypass}"
    )


def test_def2722_tc1__a_new_utility_ends_up_with_customers_and_accounts():
    """THE ASSERTION NO SUITE MADE BEFORE THIS ONE: provision a tenant, run the
    whole sample plant, and check the thing a new customer would actually look at.

    `manage.py seed_demo` hardcodes one subdomain whose data was seeded by a
    different path, so no suite had ever looked at a FRESHLY PROVISIONED
    tenant's sample set — and until CR-051 task 27 needed ten utilities, nothing
    in this repo had ever created a second one.

    Both halves matter and both are asserted: **every block reports success**,
    and **the counts are greater than zero** — because `0 == 0` satisfies every
    relational assertion and an all-zero plant would pass a bare equality.

    ⚠ **HOW THIS ONE WAS PROVED RED, STATED PLAINLY BECAUSE IT IS THE AWKWARD
    CASE.** On a HEALTHY schema this case passes on the broken code too — there
    is nothing for a savepoint to save. It is not therefore a check that cannot
    fail; it fails on any short plant, and it was made to fail twice:

    (a) MEASURED, outside pytest, on a PostgreSQL 16 database one migration
        behind (`customers.0035` unapplied), one tenant provisioned through the
        real signup path — `premises=70 units=118 meters=69 accounts=0
        customers=0 failing_blocks=8`, the first of them
            customers:seed_sample_records SD-DB-ERROR :: InternalError: current
            transaction is aborted, commands ignored until end of transaction
            block

    (b) IN THIS SUITE, on a healthy schema, by giving ONE unit the same fault
        `tc2` uses and running this case's body against the PRE-FIX module —
            AssertionError: sample blocks did not report success:
            customers:seed_sample_records — InternalError: current transaction
            is aborted…; billing:seed_sample_records — june: BillingRuleError:
            run … has no bills to release…; payments:seed_sample_records — no
            payment could be recorded…  [8 blocks]
        The same fault on the FIXED module: `1 passed`. That is the whole
        defect reproduced from a single row's refusal, and closed.
    """
    tenant, actor = _fresh_tenant()
    with tenant_ctx(tenant):
        tenancy_sample_data.seed_sample_data(actor)
        summary = tenancy_sample_data.run_summary()
        accounts = customer_models.Account.objects.count()
        customers = customer_models.Customer.objects.count()
        premises = metering_models.Premises.objects.count()
        units = metering_models.Unit.objects.count()

    short = [row for row in (summary.get("blocks") or ()) if row.get("outcome") != "seeded"]
    assert not short, "sample blocks did not report success: " + "; ".join(
        f"{row.get('module')}:{row.get('block')} — {row.get('detail')}" for row in short
    )
    assert summary["succeeded"] is True
    # Greater than zero AND the measured figure: either alone can be satisfied
    # by a plant that seeded nothing (the first by nothing, the second by 0==0
    # if the expectation ever drifts to 0).
    assert premises > 0 and units > 0, f"the estate is empty: {premises} premises, {units} units"
    assert accounts > 0, f"a signed-up utility has NO ACCOUNTS: {accounts}"
    assert customers > 0, f"a signed-up utility has NO CUSTOMERS: {customers}"
    assert accounts >= len(fixture.account_plan()), (
        f"{accounts} accounts is fewer than the {len(fixture.account_plan())} seats the "
        "fixture plans — the block came up short and nothing said so"
    )


def test_def2722_tc2__one_refusal_leaves_the_other_seats_standing(monkeypatch, audit_rows):
    """LAW 14, THE CASE THE NAIVE FIX GETS WRONG. One unit's `create_account`
    raises a real PostgreSQL error; every other seat must still be taken.

    Without the SAVEPOINT the first refusal aborts the transaction, every later
    statement in the block raises `InFailedSqlTransaction`, and the block's own
    `atomic()` discards the accounts that HAD been created — so the answer is 0,
    not 47.

    The shortfall is asserted too, because a fix that keeps the 47 and says
    nothing leaves the next refusal exactly as silent as this one was.

    RED PROOF, before the savepoints landed:
        django.db.utils.InternalError: current transaction is aborted, commands
        ignored until end of transaction block
    raised out of `seed_sample_records`, with 0 accounts on the tenant.
    """
    tenant, actor = _fresh_tenant()
    with tenant_ctx(tenant):
        _seed_up_to_accounts(actor)
        seats = {
            entry["unit_no"]
            for entry in fixture.account_plan()
            if metering_models.Unit.objects.filter(unit_no=entry["unit_no"]).exists()
        }
        assert len(seats) > 1, f"the estate seats {len(seats)} units — nothing to be partial about"
        victim = sorted(seats)[0]
        broken = _break_one_account(monkeypatch, unit_nos={victim})
        customer_sample_data.seed_sample_records(actor)
        seated = customer_models.Account.objects.filter(unit__isnull=False).count()
        victim_seated = customer_models.Account.objects.filter(unit__unit_no=victim).exists()

    assert broken["count"] > 0, "the refusal never fired — this case would prove nothing"
    assert seated > 0, f"one refusal took every other seat with it: {seated} accounts"
    assert not victim_seated, f"{victim} was supposed to refuse and did not"
    assert seated >= len(seats) - 1, (
        f"{seated} accounts landed where {len(seats) - 1} should have — one refusal cost more "
        "than one seat"
    )
    incomplete = [row for row in audit_rows if row["action"] == "sample.seed_incomplete"]
    assert incomplete, "the shortfall was not recorded anywhere a person or a query can see it"
    after = incomplete[-1]["after"]
    assert after["block"] == ACCOUNTS_BLOCK
    assert after["refused"] > 0 and after["delivered"] > 0
    assert after["delivered"] + after["refused"] == after["promised"]
    # BR-AUD-006 — the row names the unit and the exception TYPE and carries NO
    # driver message. `audit_log` is append-only (BR-AUD-002), so a message that
    # quoted a rejected field value could never be taken back out. The cause a
    # person reads is in the ERROR log, which tc2's own run shows carrying it.
    assert after["detail"] == [f"{victim}: ProgrammingError"], after["detail"]
    assert not any(NO_SUCH_TABLE in one for one in after["detail"]), (
        "the audit row is carrying the driver's free text: " + repr(after["detail"])
    )


def test_def2722_tc3__a_total_refusal_names_itself_instead_of_the_transaction(monkeypatch):
    """When NOT ONE seat can be taken the block must say so in a sentence a
    person can act on — never `InternalError: current transaction is aborted`,
    and never a silent 0.

    `fixture.BlockCannotRun` is the repo's own vehicle for this state (*"COULD
    NOT RUN — naming the reason … Never a 0"*), and the orchestrator puts its
    sentence straight into `sample_data_runs.blocks[].detail`, which S62 renders.

    RED PROOF, on the pre-fix module, VERBATIM — it never reached the assertion
    at all, because the first refusal had already killed the transaction:
        psycopg.errors.InFailedSqlTransaction: current transaction is aborted,
        commands ignored until end of transaction block
        django.db.utils.InternalError: current transaction is aborted, commands
        ignored until end of transaction block
    That string names no unit, no table and no cause, and it is what the S62
    panel showed an operator for this exact state.
    """
    tenant, actor = _fresh_tenant()
    with tenant_ctx(tenant):
        _seed_up_to_accounts(actor)
        seats = sum(
            1
            for entry in fixture.account_plan()
            if metering_models.Unit.objects.filter(unit_no=entry["unit_no"]).exists()
        )
        assert seats > 0, "no seats at all — this case would prove nothing"
        _break_one_account(monkeypatch, unit_nos=None)
        with pytest.raises(fixture.BlockCannotRun) as caught:
            customer_sample_data.seed_sample_records(actor)
        accounts = customer_models.Account.objects.count()

    said = str(caught.value.args[0])
    assert "no sample account was created" in said
    assert str(seats) in said, f"the sentence does not name how many seats refused: {said}"
    assert NO_SUCH_TABLE in said, f"the sentence does not carry the real cause: {said}"
    assert "current transaction is aborted" not in said, (
        "the block is still reporting the aborted transaction instead of the cause: " + said
    )
    assert accounts == 0


def test_def2722_tc4__the_promised_count_is_read_by_something():
    """LAW 2, ASSERTED STRUCTURALLY: the 48 the docstring promises must be
    COMPARED, not merely returned.

    `seed_sample_records` returned a count that NOTHING read for the whole life
    of the function. This pins the comparison itself, so a later lane that
    deletes `_report_short_accounts` as dead code goes red here rather than in
    production.

    RED PROOF on the pre-fix module, VERBATIM:
        AssertionError: assert False
         +  where False = hasattr(customer_sample_data, '_report_short_accounts')
    """
    assert hasattr(customer_sample_data, "_report_short_accounts")
    source = customer_sample_data.seed_sample_records.__doc__ or ""
    assert "48" in source, "the block no longer states the number it promises"
    body = customer_sample_data.__dict__["seed_sample_records"].__code__.co_names
    assert "_report_short_accounts" in body, (
        "seed_sample_records no longer calls the check — the count is returned and "
        "compared to nothing again (DEF-2722)"
    )


def test_def2722_tc5__no_units_at_all_is_reported_not_answered_with_zero():
    """A tenant whose estate never seeded must hear WHY, not a 0.

    A 0 with a reason nobody reads is indistinguishable from *"the fixture asked
    for none"* — `BlockCannotRun`'s own docstring, and DEF-166/DEF-167's lesson.

    RED PROOF on the pre-fix module, VERBATIM — the call returned `0`:
        Failed: DID NOT RAISE BlockCannotRun
    """
    tenant, actor = _fresh_tenant()
    with tenant_ctx(tenant):
        assert metering_models.Unit.objects.count() == 0, "the estate was seeded — wrong premise"
        with pytest.raises(fixture.BlockCannotRun) as caught:
            customer_sample_data.seed_sample_records(actor)
    assert "no units at all" in str(caught.value.args[0])


def test_def2722_tc6__every_catch_and_continue_in_the_seeder_opens_a_savepoint():
    """LAW 14, PINNED AS A RULE ABOUT THE FILE and not only about the two sites
    that happened to be observed.

    The measured cause was `_seed_w7_disconnects`, which has nothing to do with
    accounts; the defect report named `seed_sample_records`. Both were the same
    bug, and 23 other sites in the file were one row's refusal away from it. A
    test that pinned only the two observed sites would let the next one land
    exactly as silently — which is the *escape reason* on this defect's own row.

    RED PROOF on the module before this fix, VERBATIM — and the LIST is the
    useful half, because only two of those twenty-five had ever been observed:
        AssertionError: 25 catch-and-continue site(s) in apps/customers/
        sample_data.py have no SAVEPOINT (law 14): lines 230, 417, 562, 993,
        1357, 1464, 1541, 1615, 1656, 1687, 1699, 1728, 1748, 1769, 1801, 1823,
        1889, 2406, 3068, 3162, 3251, 3288, 3391, 3675, 3718
    """
    import inspect
    import re

    src = inspect.getsource(customer_sample_data).split("\n")
    unguarded: list[int] = []
    for index, line in enumerate(src):
        if not re.match(r"^\s*except\b", line):
            continue
        indent = len(line) - len(line.lstrip())
        back = index - 1
        while back >= 0:
            candidate = src[back]
            if candidate.strip() == "try:" and (len(candidate) - len(candidate.lstrip())) == indent:
                break
            back -= 1
        if back < 0:
            continue
        body = "\n".join(src[back + 1 : index])
        # A `try` that re-raises is not a catch-and-continue and needs nothing.
        following = src[index + 1 : index + 4]
        if any(one.strip() == "raise" for one in following):
            continue
        if "transaction.atomic()" not in body:
            unguarded.append(index + 1)
    assert not unguarded, (
        f"{len(unguarded)} catch-and-continue site(s) in apps/customers/sample_data.py have "
        f"no SAVEPOINT (law 14): lines {', '.join(str(one) for one in unguarded)}"
    )


def test_def2722_tc7__the_refusal_log_carries_the_message_not_only_the_type(monkeypatch, caplog):
    """The one trace that could have named the cause said `ProgrammingError` and
    stopped, because the line interpolated `type(exc).__name__` alone.

    RED PROOF on the pre-fix module, VERBATIM — the case could not even reach
    its assertion, because the swallowed refusal had killed the transaction and
    the block raised on its way out:
        psycopg.errors.InFailedSqlTransaction: current transaction is aborted,
        commands ignored until end of transaction block
    The line it WOULD have found, in the real reproduction, was
        sample data: unit SCW-U-001 took no account (ProgrammingError)
    — the type and nothing else, which is why the cause stayed invisible.
    """
    tenant, actor = _fresh_tenant()
    with tenant_ctx(tenant):
        _seed_up_to_accounts(actor)
        seats = sorted(
            entry["unit_no"]
            for entry in fixture.account_plan()
            if metering_models.Unit.objects.filter(unit_no=entry["unit_no"]).exists()
        )
        assert seats, "no seats — this case would prove nothing"
        _break_one_account(monkeypatch, unit_nos={seats[0]})
        with caplog.at_level("INFO", logger="smartbillhub.customers"):
            customer_sample_data.seed_sample_records(actor)

    said = [one.getMessage() for one in caplog.records if "took no account" in one.getMessage()]
    assert said, "the refusal was not logged at all"
    assert any(NO_SUCH_TABLE in one for one in said), (
        "the log names the exception TYPE and not what actually refused: " + " | ".join(said)
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2722 (12-governance/10-defect-log.csv) + CLAUDE.md hard-won laws 2, 7 and 14
# generated: 2026-08-31 by the DEF-2722 fix lane
# checklist: A✔ B=n/a(no frontend half — this is a provisioning job) C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff check .✔ · every case PROVED RED against the pre-fix module first, each failure quoted verbatim in its own docstring
# exceptions: the whole file is @requires_postgres and SKIPS on the default sqlite suite BY DESIGN — CLAUDE.md law 14: SQLite has no aborted-transaction state, so the broken code passes there. A run that reports these as skipped has proved nothing and the file says so at the top.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
