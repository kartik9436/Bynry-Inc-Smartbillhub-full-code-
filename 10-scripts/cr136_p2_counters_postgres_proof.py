#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-136-BRC07 phase 2 — `P2.1`'s outcome, verbatim: *"The database
#           refuses a second open till — not a service check that a second
#           caller can skip."* And `P2.2`/`P2.22` on a real money path.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE; `app.tenant_id` before anything
#           is counted) · hard rule 5 · hard rule 6 · hard-won law 14 (a failed
#           statement poisons the whole PostgreSQL transaction; SQLite has no
#           such state) · hard-won law 7 (prove the guard RED first, and ask
#           what would make it pass wrongly)
# Tests:    06-backend/tests/test_cr136_p2_counters.py is the SHAPE half and
#           runs on SQLite; this is the half that cannot.
# ───────────────────────────────────────────────────────
"""The three things SQLite cannot answer about a till, on PostgreSQL 16.

    10-scripts/proof-db.sh clone p2api --stale-ok
    cd 06-backend && DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local \
        python3 manage.py migrate
    DATABASE_URL=… python3 ../10-scripts/cr136_p2_counters_postgres_proof.py

⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A clone is private by
construction; a mid-run reseed looks exactly like a broken till.

WHY EACH PART IS HERE RATHER THAN IN THE SUITE
-----------------------------------------------
**A** — **THE RACE.** `uq_counter_sessions_open_owner` is what makes `P2.1`'s
outcome true, and the suite cannot show it: SQLite serialises writers, so two
"concurrent" opens there are two sequential ones and the service's own
`SELECT … then INSERT` passes the case on its own. This opens **two real
connections**, holds both inside a transaction, and makes the second INSERT
race the first — which is what two terminals at one counter actually do.

  ⚠ **AND IT IS PROVED RED FIRST.** Part A1 drops the index, runs the same
  race, and shows **two open tills for one person** — the state the product
  would carry without it. Then it recreates the index and shows the refusal. A
  guard shown only green is a guard nobody has tested.

**A3** — **THE SAME RACE, THROUGH `open_counter`** (`P2.12`, added 2026-09-23
by LANE P2-TESTS). Part A races two raw `INSERT`s, which proves the INDEX and
never reaches the SERVICE — and the service is what a clerk's button calls.
Run through `open_counter`, the race is RED without the index (both calls win,
two open tills) and leaves exactly one till and one batch with it. **What the
LOSER receives is `DEF-PAY-6262`**: a raw `IntegrityError`, which travels past
`counters_api`'s `except PaymentRuleError` and reaches a clerk as a 500. The
money is not at risk — the atomic block holds — and the words are.

**B** — **THE POISONED TRANSACTION** (law 14). Once any statement errors inside
a PostgreSQL transaction, every later query raises `InFailedSqlTransaction` and
the work is lost at COMMIT. `open_counter` writes the session and then the
batch inside ONE `transaction.atomic()`, so a refused batch must take the
session with it — and on SQLite that rollback looks identical whether the code
is right or wrong, because there is no aborted state to get wrong.

**C** — **RLS.** `app.tenant_id` unset matches **zero rows** under `FORCE` and
reports success. This sets one tenant, opens a till, then sets the OTHER tenant
and counts: the answer must be zero, and the till must still be there when the
first tenant looks again. A count with no tenant set is the false zero that
once stamped 0 of 74 payments and said it had.

**D2** — **THE OTHER DIRECTION AND THE OTHER MOMENT** (`P2.15`, added
2026-09-23). An OVER posts the mirror (`DR 1010 / CR 6850`), which part D can
never catch because it only ever counts a short; and a forced close posts
NOTHING while its late DECLARE posts the pair — §3.3's *"at close on a counted
close, at declare on a forced one"*. Both the amount's `CHECK (amount >= 0)`
and `ck_counter_sessions_declared_together` are raw DDL that exists on this
database and on no SQLite table.

**D** — **THE LEDGER PAIR.** `$12.0000` short posts `DR 6850 / CR 1010` and the
trial balance still ties. Proved against real `journal_lines`, and it needs
`P2.21`'s seeded `cash_over_short` designation — which this names rather than
skipping past, because a skip is a check that cannot fail.
"""

from __future__ import annotations

import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import connection, connections, transaction  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.payments import counters, ledger_seam  # noqa: E402
from apps.payments import bankrec_models as bankrec  # noqa: E402
from apps.payments.counter_session_models import CounterSession  # noqa: E402
from apps.payments.exceptions import PaymentRuleError  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.tenancy import published_content_models as content_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


def _guc(cursor, tenant_id) -> None:
    """Hard rule 1 — the GUC, on THIS connection, before anything is counted.

    ⚠ **ITS PARTNER WAS SPELLED `core_tenancy.set_current_tenant_id` IN FIVE
    PLACES AND THAT FUNCTION DOES NOT EXIST** (`DEF-PAY-6239`). The name is
    `set_current_tenant`. Parts B, C and D each raised `AttributeError` on
    their first line — a THIRD independent reason this file could not run,
    on top of the zero-users precondition and the `user.role` that is not a
    field. All three would have surfaced in the first thirty seconds of a
    single run, and none of them could surface without one.
    """
    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _tenant():
    row = tenancy_models.Tenant.objects.order_by("created_at").first()
    if row is None:
        raise SystemExit("no tenant in this database — run seed_demo first")
    return row


def _second_tenant(first):
    """The isolation tenant part C probes across — CREATED if there is none.

    ⚠ **IT USED TO RETURN `None` AND LET PART C REPORT A FAILURE AGAINST
    ITSELF** (`DEF-PAY-6239`). Every database `10-scripts/proof-db.sh` builds
    holds exactly ONE tenant, so *"C needs a second tenant"* was the only
    verdict this proof could ever have reached about row-level security — a
    red line that says nothing about the product. A bare `tenants` row is all
    part C needs: it sets that tenant's GUC and counts, and the answer must be
    zero.
    """
    existing = tenancy_models.Tenant.objects.exclude(pk=first.pk).order_by("created_at").first()
    if existing is not None:
        return existing
    return tenancy_models.Tenant.objects.create(
        name="Proof Isolation Utility", subdomain=f"proof-{uuid.uuid4().hex[:8]}"
    )


def _users(tenant):
    """Two staff of this tenant — CREATED if the database has fewer.

    ⚠ **THIS RAISED `SystemExit("run seed_demo first")` AND KILLED THE WHOLE
    PROOF BEFORE PART A, ON EVERY DATABASE THIS REPO CAN BUILD**
    (`DEF-PAY-6239`, found 2026-09-23 by the first lane that actually ran the
    file). Measured across five proof-db templates and clones on this
    machine: **one tenant, ZERO users, every one of them.** So the
    precondition was not merely unmet, it was **unmeetable** — hard-won law
    7's *incapable of passing*, in a file whose own docstring argues that a
    skip is a check that cannot fail.

    A till needs an OWNER and nothing else about the person, so this creates
    what it needs exactly as `_centre` below already creates a service centre
    — the pattern this file had on one precondition and not the other.
    """
    from apps.identity import models as identity_models

    with connection.cursor() as cur:
        _guc(cur, tenant.pk)
    core_tenancy.set_current_tenant(tenant.pk)
    rows = list(identity_models.User.objects.filter(tenant=tenant).order_by("created_at")[:2])
    while len(rows) < 2:
        rows.append(
            identity_models.User.objects.create(
                tenant=tenant,
                email=f"proof-till-{uuid.uuid4().hex[:8]}@example.test",
                full_name="Proof Counter Clerk",
            )
        )
    return rows


def _actor(user):
    """The B12 §6a actor shape, with a ROLE the guard will accept.

    ⚠ **THIS READ `role=user.role` AND `identity.User` HAS NO `role` FIELD**
    (`DEF-PAY-6239`). Role lives on the MEMBERSHIP row, `identity.TenantUser`,
    because one person can be a clerk at one utility and nothing at another.
    So every part of this proof that opens a till — B, C and D, three of the
    four — raised `AttributeError: 'User' object has no attribute 'role'`
    before `@require_role` was ever reached. A second reason the file could
    not run, independent of the first, and both invisible while nobody ran it.
    """
    from types import SimpleNamespace

    from apps.identity import models as identity_models

    membership = (
        identity_models.TenantMembership.objects.filter(user=user)
        .select_related("role")
        .first()
    )
    role = getattr(getattr(membership, "role", None), "code", None) or "system_admin"
    return SimpleNamespace(id=user.pk, pk=user.pk, user=user, role=role)


def _clear_open_tills(tenant, owner) -> None:
    """Leave this person with no OPEN till — by CLOSING, never by deleting.

    ⚠ **EVERY TEARDOWN IN THIS FILE SAID `.delete()` AND A TILL THAT HAS
    TAKEN ANY MONEY CANNOT BE DELETED** (`DEF-PAY-6239`). `open_counter`
    opens the till's cash batch in the same transaction (`BR-PAY-1184`), and
    `DepositBatch.session` is `on_delete=PROTECT`, so Django refuses:

        ProtectedError: Cannot delete some instances of model
        'CounterSession' because they are referenced through protected
        foreign keys: 'DepositBatch.session'.

    Deleting the batch first is not the way out either — `trg_deposit_batch_
    lock` REFUSES a DELETE on `deposit_batches` BY NAME, because *"a batch is
    the record of what physically went to the bank on a day"*. **So this
    teardown could never succeed once any part had opened a real till**, and
    part D — the ledger pair, the only part about money — sat behind it.

    Closing is enough and is what the product does: the partial index
    `uq_counter_sessions_open_owner` asks `closed_at IS NULL`, so a CLOSED
    till lets the next one open. The three closing facts move together or
    `ck_counter_sessions_closed_together` refuses the row.
    """
    CounterSession.objects.filter(
        tenant=tenant, owner=owner, closed_at__isnull=True
    ).update(closed_at=timezone.now(), closed_by=owner, close_kind="forced")


def _centre(tenant):
    centre = content_models.ServiceCentre.objects.filter(tenant=tenant).first()
    if centre is not None:
        return centre
    return content_models.ServiceCentre.objects.create(
        tenant=tenant, slug=f"proof-{uuid.uuid4().hex[:6]}", name="Proof counter", address="1 Road"
    )


# ═══════════════════════════════════════════════════════════════════════════
def part_a(tenant, owner, centre) -> None:
    """THE RACE — two real connections, and the index proved RED first."""
    print("\nPART A — two terminals, one person, one open till")

    def _race() -> tuple[int, str | None]:
        """Both connections INSERT an open till for `owner`. Returns (rows, error)."""
        _clear_open_tills(tenant, owner)
        left = connections.create_connection("default")
        right = connections.create_connection("default")
        error = None
        try:
            for conn in (left, right):
                with conn.cursor() as cur:
                    _guc(cur, tenant.pk)
            left.set_autocommit(False)
            right.set_autocommit(False)
            # ⚠ **WITHOUT THIS THE RACE PROVES NOTHING AND LOOKS LIKE A PASS**
            # (`DEF-PAY-6239`, and it is hard-won law 7 habit 2 in one line).
            # A Django `DatabaseWrapper` refuses use from another thread —
            # *"created in thread id X and this is thread id Y"* — which
            # arrives as an EXCEPTION on the second terminal and is
            # indistinguishable, to the check below, from the unique index
            # refusing it. Measured: A2 reported **PASS** on exactly that
            # error while the index was never consulted at all, and A1 then
            # reported FAIL for the same reason, which is the only thing that
            # gave it away. The second terminal must really reach PostgreSQL.
            right.inc_thread_sharing()
            sql = (
                "INSERT INTO counter_sessions "
                "(id, tenant_id, owner_id, service_centre_id, opening_float, currency, "
                " opened_at, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, 200.0000, 'USD', now(), now(), now())"
            )
            with left.cursor() as cur:
                cur.execute(sql, [str(uuid.uuid4()), str(tenant.pk), str(owner.pk),
                                  str(centre.pk)])
            # ── THE SECOND TERMINAL RUNS ON ITS OWN THREAD, AND IT HAS TO ──
            # ⚠ **IT WAS SEQUENTIAL AND IT HUNG FOR EVER** (`DEF-PAY-6239`).
            # The comment here was right about the mechanism and the code
            # could not express it: a unique index makes the second INSERT
            # **BLOCK** until the first commits or rolls back, and
            # `left.commit()` sat on the next line of the SAME thread — after
            # the statement that can never return until it runs. Measured on
            # PostgreSQL 16.13: `pg_stat_activity` showed `active / Lock` on
            # the second INSERT and `idle in transaction` on the first, for as
            # long as the process was left alive. **So the file could never
            # have reached parts B, C or D**, whatever else was repaired.
            #
            # Two terminals are two PROCESSES, so the proof needs two threads.
            # The second INSERT blocks on its own thread; the main thread then
            # commits the first, which is what turns that block into the
            # unique violation the index exists to raise.
            import threading

            outcome: dict = {}

            def _second_terminal() -> None:
                try:
                    with right.cursor() as cur:
                        cur.execute(sql, [str(uuid.uuid4()), str(tenant.pk), str(owner.pk),
                                          str(centre.pk)])
                    outcome["ok"] = True
                except Exception as exc:  # the index refusing the second terminal
                    outcome["error"] = f"{type(exc).__name__}: {str(exc).splitlines()[0]}"

            thread = threading.Thread(target=_second_terminal, daemon=True)
            thread.start()
            # Give the second terminal time to reach the lock before the first
            # commits, so this is a RACE and not two sequential inserts. With
            # no index it finishes here; with one it is parked on the lock.
            thread.join(timeout=2.0)
            left.commit()
            # ⚠ **A BOUNDED JOIN, because an unbounded one is how this hung.**
            # If the second terminal is still blocked ten seconds after the
            # first committed, something other than the index is holding it and
            # the proof says so rather than waiting.
            thread.join(timeout=10.0)
            if thread.is_alive():
                error = "TimeoutError: the second terminal never returned"
            elif "error" in outcome:
                error = outcome["error"]
                try:
                    right.rollback()
                except Exception:
                    pass
            else:
                right.commit()
        finally:
            for conn in (left, right):
                try:
                    conn.close()
                except Exception:
                    pass
        with connection.cursor() as cur:
            _guc(cur, tenant.pk)
        return (
            CounterSession.objects.filter(
                tenant=tenant, owner=owner, closed_at__isnull=True
            ).count(),
            error,
        )

    # ── A1 · RED. Without the index, the product carries TWO open tills. ────
    with connection.cursor() as cur:
        _guc(cur, tenant.pk)
        cur.execute("DROP INDEX IF EXISTS uq_counter_sessions_open_owner")
    rows, error = _race()
    check("A1 RED: with the index dropped, two terminals both win", rows == 2,
          f"open tills for one person = {rows}, error={error}")

    # ── A2 · GREEN. The index back, and the second terminal loses. ──────────
    # ⚠ **A1's TWO ROWS ARE CLEARED FIRST, AND THAT LINE WAS MISSING**
    # (`DEF-PAY-6239`). `_race()` clears the owner's tills at its START, so
    # after A1 the database is holding exactly the duplicate pair A1 exists to
    # produce — and `CREATE UNIQUE INDEX` over them raises
    # `could not create unique index "uq_counter_sessions_open_owner" DETAIL:
    # Duplicate keys exist.` **A1 proving the index red is what stops A2
    # restoring it**, so this file could never have reached part B even with
    # its three other faults repaired. It is the shape the header warns about
    # one level up: a guard nobody has run is a claim, not a check.
    _clear_open_tills(tenant, owner)
    with connection.cursor() as cur:
        _guc(cur, tenant.pk)
        cur.execute(
            "CREATE UNIQUE INDEX uq_counter_sessions_open_owner "
            "ON counter_sessions (tenant_id, owner_id) WHERE closed_at IS NULL"
        )
    rows, error = _race()
    # ⚠ **`error is not None` IS NOT ENOUGH AND THAT IS NOT PEDANTRY** — ANY
    # exception on the second terminal satisfied it, including Django refusing
    # a cross-thread connection, which is how this reported PASS over a race
    # that never happened (`DEF-PAY-6239`). The refusal must NAME the index.
    check("A2 GREEN: the database refuses the second terminal BY NAME",
          rows == 1 and error is not None
          and "uq_counter_sessions_open_owner" in error,
          f"open tills = {rows}, error={error}")
    _clear_open_tills(tenant, owner)


def part_a3(tenant, owner, centre) -> None:
    """THE RACE THROUGH THE SERVICE — `P2.12`, and part A does not reach it.

    ⚠ **PART A RACES TWO RAW `INSERT` STATEMENTS.** That proves the INDEX, and
    the index is the guarantee. It says nothing at all about `open_counter`,
    which is the function a clerk's button actually calls — and `open_counter`
    carries a `SELECT … then INSERT` whose own docstring claims the loser
    *"reads a sentence naming their open till instead of a constraint name"*.
    **A comment claiming a guarantee is not the guarantee** (hard-won law 1),
    and the only way to find out is to run two real presses through the real
    function.

    Three things are asserted and they are deliberately separate:

      * **A3-1 RED** — with the index dropped, BOTH service calls succeed and
        the person ends the race with **two open tills**. That is what the
        `SELECT` alone is worth: neither transaction can see the other's
        uncommitted row, so the check passes twice. Proving it red here is what
        stops a later reader concluding the service check was ever the barrier.
      * **A3-2** — with the index back, the race leaves **exactly one open till
        and exactly one new batch**. This is the half of `P2.12` that is about
        MONEY, and it holds: `open_counter` writes the session and the batch
        inside one `transaction.atomic()`, so the loser's batch goes back with
        the loser's session. No orphan `DEP-` row, on the one database that can
        actually poison a transaction.
      * **A3-3 `DEF-PAY-6262`** — what the LOSER receives. Today it is a raw
        `django.db.utils.IntegrityError` naming the index, which travels
        straight past `counters_api`'s `except PaymentRuleError` and reaches the
        clerk as a **500**. This branches on reality and asserts a specific,
        falsifiable fact on each side — **never a skip**, because a skip is a
        check that cannot fail. The day the defect is fixed it takes the other
        branch and asserts the SENTENCE instead.

    ⚠ **TWO THREADS, NOT TWO SEQUENTIAL CALLS** — part A's own hard-won note,
    for the same reason: a unique index makes the second INSERT *block* until
    the first commits, so a sequential version hangs for ever rather than
    racing. Each thread gets its own Django connection (they are thread-local),
    sets the GUC on it, and both are released at a barrier.
    """
    import threading

    from django.db import IntegrityError

    print("\nPART A3 — the same race, through `open_counter` itself")

    def _race_the_service() -> tuple[int, int, list[BaseException]]:
        """Returns (open tills, batches created, the losers' exceptions)."""
        with connection.cursor() as cur:
            _guc(cur, tenant.pk)
        core_tenancy.set_current_tenant(tenant.pk)
        _clear_open_tills(tenant, owner)
        batches_before = bankrec.DepositBatch.objects.filter(tenant=tenant).count()
        errors: list[BaseException] = []
        gate = threading.Barrier(2, timeout=20)

        def terminal() -> None:
            try:
                with connections["default"].cursor() as cur:
                    _guc(cur, tenant.pk)
                core_tenancy.set_current_tenant(tenant.pk)
                gate.wait()
                counters.open_counter(
                    _actor(owner),
                    service_centre_id=centre.pk,
                    opening_float=Decimal("200.0000"),
                    opened_at=timezone.now(),
                )
            except BaseException as exc:  # noqa: BLE001 — the outcome IS the measurement
                errors.append(exc)
            finally:
                connections["default"].close()

        threads = [threading.Thread(target=terminal, daemon=True) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        with connection.cursor() as cur:
            _guc(cur, tenant.pk)
        core_tenancy.set_current_tenant(tenant.pk)
        return (
            CounterSession.objects.filter(
                tenant=tenant, owner=owner, closed_at__isnull=True
            ).count(),
            bankrec.DepositBatch.objects.filter(tenant=tenant).count() - batches_before,
            errors,
        )

    # ── A3-1 · RED. The service's own SELECT stops nothing. ────────────────
    with connection.cursor() as cur:
        _guc(cur, tenant.pk)
        cur.execute("DROP INDEX IF EXISTS uq_counter_sessions_open_owner")
    tills, batches, errors = _race_the_service()
    check(
        "A3-1 RED: without the index BOTH service calls win — the SELECT is not the barrier",
        tills == 2 and not errors,
        f"open tills = {tills}, batches opened = {batches}, errors={[type(e).__name__ for e in errors]}",
    )

    # A1/A3-1's duplicates must go before the index can be recreated over them.
    _clear_open_tills(tenant, owner)
    with connection.cursor() as cur:
        _guc(cur, tenant.pk)
        cur.execute(
            "CREATE UNIQUE INDEX uq_counter_sessions_open_owner "
            "ON counter_sessions (tenant_id, owner_id) WHERE closed_at IS NULL"
        )

    # ── A3-2 · the money half: one till, one batch, no orphan. ─────────────
    tills, batches, errors = _race_the_service()
    check(
        "A3-2 the race leaves ONE open till and ONE new batch — the loser's batch went back with it",
        tills == 1 and batches == 1 and len(errors) == 1,
        f"open tills = {tills}, batches opened = {batches}, losers = {len(errors)}",
    )

    # ── A3-3 · `DEF-PAY-6262` — what the loser is handed. ──────────────────
    loser = errors[0] if errors else None
    if isinstance(loser, PaymentRuleError):
        check(
            "A3-3 the loser reads a SENTENCE naming their open till (DEF-PAY-6262 is FIXED)",
            "already have a counter open" in str(loser),
            str(loser)[:100],
        )
    else:
        check(
            "A3-3 DEF-PAY-6262 is OPEN: the loser gets a raw IntegrityError, so a clerk gets a 500",
            isinstance(loser, IntegrityError)
            and "uq_counter_sessions_open_owner" in str(loser),
            f"{type(loser).__name__}: {str(loser).splitlines()[0][:110]}",
        )
    _clear_open_tills(tenant, owner)


def part_b(tenant, owner, centre) -> None:
    """THE POISONED TRANSACTION — the session goes back with the batch."""
    print("\nPART B — one transaction, on a database that poisons them")
    with connection.cursor() as cur:
        _guc(cur, tenant.pk)
    core_tenancy.set_current_tenant(tenant.pk)
    _clear_open_tills(tenant, owner)
    before = CounterSession.objects.filter(tenant=tenant).count()

    tenancy_models.PaymentMethod.objects.filter(
        tenant=tenant, code=counters.DRAWER_TENDER
    ).update(active=False)
    try:
        counters.open_counter(
            _actor(owner),
            service_centre_id=centre.pk,
            opening_float=Decimal("200.0000"),
            opened_at=timezone.now(),
        )
        check("B refuses when the drawer tender is gone", False, "it did not refuse")
    except PaymentRuleError as refusal:
        check("B refuses when the drawer tender is gone", True, str(refusal)[:60])
    finally:
        tenancy_models.PaymentMethod.objects.filter(
            tenant=tenant, code=counters.DRAWER_TENDER
        ).update(active=True)

    after = CounterSession.objects.filter(tenant=tenant).count()
    check("B the SESSION rolled back with the batch", after == before,
          f"{before} before, {after} after")
    # ⚠ The connection must still be USABLE. Law 14's real question: a service
    # that swallowed the error without a savepoint would leave this raising
    # `InFailedSqlTransaction` and every later statement would be lost.
    try:
        CounterSession.objects.filter(tenant=tenant).count()
        check("B the connection is usable afterwards", True)
    except Exception as exc:
        check("B the connection is usable afterwards", False, type(exc).__name__)


def part_c(tenant, other, owner, centre) -> None:
    """RLS — the other tenant sees nothing, and an unset GUC sees nothing either."""
    print("\nPART C — row-level security, which SQLite cannot have")
    if other is None:
        check("C needs a second tenant", False, "only one tenant in this database")
        return
    with connection.cursor() as cur:
        _guc(cur, tenant.pk)
    core_tenancy.set_current_tenant(tenant.pk)
    _clear_open_tills(tenant, owner)
    opened = counters.open_counter(
        _actor(owner),
        service_centre_id=centre.pk,
        opening_float=Decimal("200.0000"),
        opened_at=timezone.now(),
    )
    mine = CounterSession.objects.filter(pk=opened.session.pk).count()
    check("C the till is visible to its own tenant", mine == 1)

    with connection.cursor() as cur:
        _guc(cur, other.pk)
    core_tenancy.set_current_tenant(other.pk)
    theirs = CounterSession.objects.filter(pk=opened.session.pk).count()
    check("C the other tenant sees NOTHING", theirs == 0, f"rows = {theirs}")
    batches = bankrec.DepositBatch.objects.filter(pk=opened.batch.pk).count()
    check("C the other tenant sees no batch either", batches == 0, f"rows = {batches}")

    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', '', false)")
    unset = CounterSession.objects.filter(pk=opened.session.pk).count()
    check("C an UNSET tenant matches zero rows (the false zero)", unset == 0,
          "this is the shape that once stamped 0 of 74 payments and reported success")

    with connection.cursor() as cur:
        _guc(cur, tenant.pk)
    core_tenancy.set_current_tenant(tenant.pk)
    check("C and the till is still there when its own tenant looks again",
          CounterSession.objects.filter(pk=opened.session.pk).count() == 1)
    _clear_open_tills(tenant, owner)


def part_d(tenant, owner, centre) -> None:
    """THE LEDGER PAIR — $12.0000 short, DR 6850 / CR 1010, and it balances."""
    print("\nPART D — the drawer difference in the books")
    from apps.ledger import models as ledger_models
    from apps.ledger import selectors as ledger_selectors

    with connection.cursor() as cur:
        _guc(cur, tenant.pk)
    core_tenancy.set_current_tenant(tenant.pk)
    try:
        over_short = ledger_selectors.gl_account_id_for_designation(
            ledger_seam.GL_CASH_OVER_SHORT
        )
    except Exception as exc:
        check("D `cash_over_short` is on this tenant's chart", False,
              f"{type(exc).__name__} — `P2.21` has not seeded it yet")
        return
    undeposited = ledger_selectors.gl_account_id_for_designation("undeposited_funds")

    _clear_open_tills(tenant, owner)
    opened = counters.open_counter(
        _actor(owner),
        service_centre_id=centre.pk,
        opening_float=Decimal("200.0000"),
        opened_at=timezone.now(),
    )
    sealed = counters.close_counter(
        _actor(owner),
        session_id=opened.session.pk,
        counted_totals={"cash": "188.00"},  # $12.00 short of the $200.00 float
        closed_at=timezone.now(),
        note="cheque stuck to the bag",
    )
    check("D the difference is -12.0000", sealed.difference == Decimal("-12.0000"),
          str(sealed.difference))
    lines = list(
        ledger_models.JournalLine.objects.filter(
            tenant=tenant,
            source_type=ledger_seam.SOURCE_COUNTER_SESSION,
            source_id=opened.session.pk,
        )
    )
    check("D two lines, one entry", len(lines) == 2, f"{len(lines)} line(s)")
    if len(lines) == 2:
        debit = next((row for row in lines if row.side == "debit"), None)
        credit = next((row for row in lines if row.side == "credit"), None)
        # ⚠ **COMPARED AS STRINGS, AND `==` ON THE RAW VALUES COULD NEVER BE
        # TRUE** (`DEF-PAY-6239`). `JournalLine.ledger_account_id` is a
        # `uuid.UUID`; `ledger.selectors.gl_account_id_for_designation`
        # returns a **`str`**. `UUID(...) == "01a0cc9f-..."` is `False` in
        # Python for every value there has ever been, so both of these checks
        # were **structurally incapable of passing** — hard-won law 7's own
        # phrase — and the product was right all along. Measured on
        # PostgreSQL 16.13: the debit really does name `cash_over_short` and
        # the credit really does name `undeposited_funds`; only the assertion
        # was looking at the wrong thing.
        check("D DR 6850 Cash over and short 12.0000",
              debit is not None and str(debit.ledger_account_id) == str(over_short)
              and debit.amount == Decimal("12.0000"),
              f"account={getattr(debit, 'ledger_account_id', None)} amount="
              f"{getattr(debit, 'amount', None)}")
        check("D CR 1010 Undeposited funds 12.0000",
              credit is not None and str(credit.ledger_account_id) == str(undeposited)
              and credit.amount == Decimal("12.0000"),
              f"account={getattr(credit, 'ledger_account_id', None)} amount="
              f"{getattr(credit, 'amount', None)}")
        check("D debits equal credits", debit.amount == credit.amount)

    # Hard rule 6 — a replay writes nothing. The key is one per TILL.
    entries_before = ledger_models.JournalEntry.objects.filter(
        tenant=tenant, source_type=ledger_seam.SOURCE_COUNTER_SESSION
    ).count()
    with transaction.atomic():
        ledger_seam.post_counter_difference(
            session=CounterSession.objects.get(pk=opened.session.pk),
            difference=Decimal("-12.0000"),
            entry_date=timezone.now().date(),
            posted_at=timezone.now(),
            actor=_actor(owner),
        )
    entries_after = ledger_models.JournalEntry.objects.filter(
        tenant=tenant, source_type=ledger_seam.SOURCE_COUNTER_SESSION
    ).count()
    check("D a replay writes NO second entry (hard rule 6)", entries_after == entries_before,
          f"{entries_before} -> {entries_after}")
    _clear_open_tills(tenant, owner)


def part_d2(tenant, owner, centre) -> None:
    """THE OTHER DIRECTION, AND THE OTHER MOMENT — `P2.15`, on real journal rows.

    Part D proves a **short** drawer at a **counted close**. Both of those are
    one half of a pair, and neither half's assertion can fail for the other's
    reason:

      * **AN OVER.** `$12.0000` over posts the MIRROR — DR `1010 Undeposited
        funds` / CR `6850 Cash over and short`. A seam that put `6850` on the
        debit whatever the sign satisfies part D exactly, for ever, because
        part D only ever counts a short. **The sign is read in one place** and
        this is the only check that reads it back.
        ⚠ **AND IT IS WORTH DOING ON PostgreSQL RATHER THAN ONLY ON SQLite**:
        B2 puts `CHECK (amount >= 0)` on a journal line, and that constraint is
        RAW DDL — it is not on the SQLite suite's tables at all. A seam that
        passed a negative through would be refused here and silently stored
        there.
      * **AT DECLARE.** §3.3: *"It posts when the money is COUNTED — at close on
        a counted close, at declare on a forced one."* A forced close counts
        nothing and must post NOTHING; the late count is what posts. The declare
        also has to satisfy `ck_counter_sessions_declared_together`, which is a
        real CHECK on this database and on no SQLite table, so this is the only
        place the two facts can be proved together.
    """
    print("\nPART D2 — the drawer difference in the OTHER direction, and at DECLARE")
    from apps.ledger import models as ledger_models
    from apps.ledger import selectors as ledger_selectors

    with connection.cursor() as cur:
        _guc(cur, tenant.pk)
    core_tenancy.set_current_tenant(tenant.pk)
    try:
        over_short = ledger_selectors.gl_account_id_for_designation(
            ledger_seam.GL_CASH_OVER_SHORT
        )
    except Exception as exc:
        check("D2 `cash_over_short` is on this tenant's chart", False,
              f"{type(exc).__name__} — `P2.21` has not seeded it here")
        return
    undeposited = ledger_selectors.gl_account_id_for_designation("undeposited_funds")

    # ── AN OVER, at a counted close ────────────────────────────────────────
    _clear_open_tills(tenant, owner)
    opened = counters.open_counter(
        _actor(owner),
        service_centre_id=centre.pk,
        opening_float=Decimal("200.0000"),
        opened_at=timezone.now(),
    )
    sealed = counters.close_counter(
        _actor(owner),
        session_id=opened.session.pk,
        counted_totals={"cash": "212.00"},  # $12.00 MORE than the float
        closed_at=timezone.now(),
        note="found a twenty under the tray",
    )
    check("D2 the difference is +12.0000 (counted minus expected)",
          sealed.difference == Decimal("12.0000"), str(sealed.difference))
    lines = list(
        ledger_models.JournalLine.objects.filter(
            tenant=tenant,
            source_type=ledger_seam.SOURCE_COUNTER_SESSION,
            source_id=opened.session.pk,
        )
    )
    check("D2 two lines, one entry", len(lines) == 2, f"{len(lines)} line(s)")
    if len(lines) == 2:
        debit = next((row for row in lines if row.side == "debit"), None)
        credit = next((row for row in lines if row.side == "credit"), None)
        check("D2 DR 1010 Undeposited funds 12.0000 — the MIRROR of a short",
              debit is not None and str(debit.ledger_account_id) == str(undeposited)
              and debit.amount == Decimal("12.0000"),
              f"account={getattr(debit, 'ledger_account_id', None)} amount="
              f"{getattr(debit, 'amount', None)}")
        check("D2 CR 6850 Cash over and short 12.0000",
              credit is not None and str(credit.ledger_account_id) == str(over_short)
              and credit.amount == Decimal("12.0000"),
              f"account={getattr(credit, 'ledger_account_id', None)} amount="
              f"{getattr(credit, 'amount', None)}")
        # B2's `CHECK (amount >= 0)` is raw DDL and is on THIS database only.
        check("D2 neither amount is signed — the DIRECTION is the side",
              all(row.amount >= Decimal("0") for row in lines))

    # ── AND AT DECLARE, on a till a supervisor sealed uncounted ────────────
    _clear_open_tills(tenant, owner)
    forced = counters.open_counter(
        _actor(owner),
        service_centre_id=centre.pk,
        opening_float=Decimal("200.0000"),
        opened_at=timezone.now(),
    )
    supervisor = _actor(owner)
    supervisor.role = "system_admin"  # force-close is System Admin only
    counters.force_close_counter(
        supervisor,
        session_id=forced.session.pk,
        reason="went home without closing",
        closed_at=timezone.now(),
    )
    at_force = ledger_models.JournalLine.objects.filter(
        tenant=tenant,
        source_type=ledger_seam.SOURCE_COUNTER_SESSION,
        source_id=forced.session.pk,
    ).count()
    check("D2 a forced close counted nothing and posted NOTHING", at_force == 0,
          f"{at_force} line(s)")
    declared = counters.declare_counter(
        _actor(owner),
        session_id=forced.session.pk,
        counted_totals={"cash": "188.00"},  # $12.00 short
        declared_at=timezone.now(),
        note="cheque stuck to the bag",
    )
    at_declare = list(
        ledger_models.JournalLine.objects.filter(
            tenant=tenant,
            source_type=ledger_seam.SOURCE_COUNTER_SESSION,
            source_id=forced.session.pk,
        )
    )
    check("D2 the LATE COUNT is what posts — DR 6850 / CR 1010",
          len(at_declare) == 2
          and str(next(r for r in at_declare if r.side == "debit").ledger_account_id)
          == str(over_short),
          f"{len(at_declare)} line(s), difference={declared.difference}")
    # §3.2 — and the forced close still STANDS. `ck_counter_sessions_declared_
    # together` is a real CHECK here and on no SQLite table, so a declare that
    # left `close_kind` alone can only be proved lawful on this database.
    row = CounterSession.objects.get(pk=forced.session.pk)
    check("D2 the row says BOTH: force-closed, and declared",
          row.close_kind == "forced" and row.declared_at is not None,
          f"close_kind={row.close_kind} declared_at={row.declared_at}")
    _clear_open_tills(tenant, owner)


def main() -> int:
    if connection.vendor != "postgresql":
        raise SystemExit(
            f"this proof is about PostgreSQL and the connection is {connection.vendor!r}. "
            "Set DATABASE_URL and DJANGO_SETTINGS_MODULE=config.settings.local — the test "
            "settings hardcode in-memory SQLite and would pass every part of this by vacuum "
            "(CLAUDE.md hard-won law 14)."
        )
    tenant = _tenant()
    other = _second_tenant(tenant)
    owner, _second = _users(tenant)
    centre = _centre(tenant)
    print(f"tenant {tenant.subdomain} · owner {owner.email} · centre {centre.name}")
    part_a(tenant, owner, centre)
    part_a3(tenant, owner, centre)
    part_b(tenant, owner, centre)
    part_c(tenant, other, owner, centre)
    part_d(tenant, owner, centre)
    part_d2(tenant, owner, centre)
    print("\n" + ("ALL PARTS PASSED" if not FAILURES else f"FAILED: {FAILURES}"))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
