#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: the THREE `P6.11` joining reads, measured on REAL PostgreSQL 16 —
#            `apps/identity/access_review.py` (R36),
#            `apps/metering/read_import_log.py` (R32) and
#            `apps/customers/account_activity.py` (R23). The test suite runs on
#            in-memory SQLite (`config/settings/test.py` hardcodes it and
#            ignores `DATABASE_URL`) and cannot answer a question about
#            LIMIT/OFFSET, a query plan or RLS (CLAUDE.md hard-won law 14).
# Rules:     `NFR-3` (universal server pagination — in SQL, never in Python) ·
#            `NFR-5` (no hard caps anywhere) · hard rule 1 (tenant scoping;
#            RLS FORCE, and the app role is neither superuser nor BYPASSRLS) ·
#            hard rule 4 (this script READS; only the fixture writes) ·
#            hard-won law 7 (a check that cannot cover its whole subject prints
#            what it SKIPPED beside what it checked).
# ───────────────────────────────────────────────────────
"""WHAT ONE PAGE OF EACH JOINING READ COSTS — three instruments, never one.

**A wall clock alone cannot answer an `NFR-3` question** — at a small tenant
every figure is dominated by fixed overhead. **And a statement count alone
cannot either**, because a read can hold its statement count flat while the
ROWS those statements build grow with the tenant.

  **statements**   round trips. An N+1 shows here and nowhere else.
  **rows served**  what the caller got back — the PAGE on a paged read.
  **seconds**      median of `--repeat`, after a discarded warm-up.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY — each answered, never assumed:**

  * **Measuring nothing.** RLS FORCE is on and the app role is neither
    superuser nor BYPASSRLS, so with `app.tenant_id` unset every query returns
    zero rows in about a millisecond and every timing would look wonderful.
    Every measurement runs inside `tenant_context` and **prints the row count
    it served**; a zero FAILS.
  * **Timing a page that is not the expensive one.** The LAST page is measured
    too, which is where an in-Python slice shows: a SQL `OFFSET` walk is flat,
    a Python slice that materialised everything first is not.
  * **A query that ignores `per`.** Page 1 serving more than `per` FAILS.
  * **A sort applied in Python after the page.** Two directions over the same
    window must reverse at the ends; **equal firsts mean `direction` was
    ignored**, so the comparison is `!=` and never `<=`.
  * **An export that inherited a page.** Each stream is counted against its own
    filtered set and a short file FAILS.
  * **An N+1 hiding behind a small page.** Every label read on all three paths
    is batched per page, so the statement count must NOT move with `per`. Page
    1 is measured at two page sizes and a count that scales FAILS.
  * **A fixture too small to distinguish anything.** Every leg prints its row
    count and refuses below a stated floor.

⚠ **WHAT THIS SCRIPT DOES NOT MEASURE, STATED RATHER THAN LEFT BLANK**
(hard-won law 7's fifth shape — a number over a scope it silently excludes):

  * **RLS** → `10-scripts/p6_join_rls_proof.py`, which runs as a role that is
    neither superuser nor BYPASSRLS and plants the neighbour's rows first.
  * **`BR-REP-023`'s restriction on R36** → NOTHING ENFORCES IT. `P5.9` is open.
  * **A 40,000-ACCOUNT TENANT.** The provisioner seeds a sample utility with
    tens of accounts, and this script grows the FACT tables — memberships,
    batches, rows, moves — to volume on that base, which is the same shape
    `ds_small_datasets_cost.py` uses for work orders. So `40,000 move records`
    means 40,000 EVENTS, which is R23's grain and the number that decides its
    cost; it does NOT mean 40,000 distinct accounts, and the printed line says
    how many accounts there actually are so no reader has to assume.
  * **R36 AT A REALISTIC STAFF COUNT.** The ICP is 10–20 staff, so a real
    tenant has ONE page and no deep offset exists to measure. The fixture seeds
    far more **on purpose**, because `NFR-5` asks whether the read has a
    ceiling and the honest way to answer that is to go past the tier. The
    small-tenant figure is printed beside it so both are visible.

USAGE
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p6join \\
      python3 ../10-scripts/p6_join_cost.py --staff 40000 --batches 4000 --moves 40000 --repeat 3
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection, reset_queries  # noqa: E402

from apps.customers import account_activity  # noqa: E402
from apps.customers import models as customer_models  # noqa: E402
from apps.customers.moves import KIND_MOVE_IN, KIND_MOVE_OUT, MoveRecord  # noqa: E402
from apps.customers.transfers import Transfer  # noqa: E402
from apps.identity import access_review  # noqa: E402
from apps.identity import models as identity_models  # noqa: E402
from apps.metering import models as metering_models  # noqa: E402
from apps.metering import read_import_log  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

import cr051_provision_utilities as provisioner  # noqa: E402

PAGE = 50
BIG_PAGE = 200
#: `docker-entrypoint.sh`, `GUNICORN_TIMEOUT:-60`. A read slower than this is
#: not slow — it is KILLED BEFORE IT ANSWERS, which is what `CR-138` `P4`
#: measured on `/outstandings` at the top of the ICP.
WORKER_TIMEOUT = 60.0
MARKER = "P6JOIN"


def _measure(label: str, call, *, repeat: int, rows_of=None) -> dict:
    """(statements, rows, median seconds) for one call, warm-up discarded."""
    rows_of = rows_of or (lambda answer: len(answer["rows"]))
    previous = settings.DEBUG
    settings.DEBUG = True
    try:
        call()  # discarded warm-up — the first run pays for the connection
        timings: list[float] = []
        statements = 0
        rows = 0
        answer = None
        for _ in range(repeat):
            reset_queries()
            began = time.perf_counter()
            answer = call()
            timings.append(time.perf_counter() - began)
            statements = len(connection.queries)
            rows = rows_of(answer)
        return {
            "label": label,
            "statements": statements,
            "rows": rows,
            "seconds": statistics.median(timings),
            "answer": answer,
        }
    finally:
        settings.DEBUG = previous


def _say(result: dict) -> None:
    print(
        f"  {result['label']:<44} {result['seconds']:>8.3f}s  "
        f"{result['statements']:>4} statements  {result['rows']:>7} rows"
    )


# ── the fixtures ────────────────────────────────────────────────────────────


def seed_staff(tenant, *, staff: int) -> int:
    """`staff` memberships, ONE IN TEN NEVER SIGNED IN and one in five invited.

    ⚠ **THE DORMANT TENTH IS THE POINT OF THE FIXTURE, NOT DECORATION.** R36
    exists to find the account nobody uses, and a fixture in which everybody has
    signed in cannot tell a working `never_signed_in` tile from one hardcoded to
    zero — which is the `audit_log` grain's exact failure, reproduced in a
    benchmark.
    """
    roles = {}
    for code, name in (
        ("system_admin", "Administrator"),
        ("billing_clerk", "Billing clerk"),
        ("executive", "Executive"),
    ):
        roles[code] = identity_models.Role.objects.get_or_create(
            code=code, defaults={"name": name}
        )[0]
    codes = list(roles)
    existing = identity_models.User.objects.filter(email__startswith=f"{MARKER}-").count()
    now = datetime.now(timezone.utc)
    users: list[identity_models.User] = []
    made = 0
    for index in range(existing, staff):
        users.append(
            identity_models.User(
                tenant=tenant,
                email=f"{MARKER}-{index:07d}@example.invalid",
                full_name=f"{MARKER} Staff {index:07d}",
            )
        )
        if len(users) >= 2_000:
            identity_models.User.objects.bulk_create(users)
            made += len(users)
            users = []
    if users:
        identity_models.User.objects.bulk_create(users)
        made += len(users)

    have = set(
        identity_models.TenantMembership.objects.filter(
            tenant=tenant, user__email__startswith=f"{MARKER}-"
        ).values_list("user_id", flat=True)
    )
    memberships: list[identity_models.TenantMembership] = []
    for index, user in enumerate(
        identity_models.User.objects.filter(
            tenant=tenant, email__startswith=f"{MARKER}-"
        ).order_by("email")
    ):
        if user.id in have:
            continue
        memberships.append(
            identity_models.TenantMembership(
                tenant=tenant,
                user=user,
                role=roles[codes[index % 3]],
                status="invited" if index % 5 == 4 else "active",
                # ⚠ SPREAD ACROSS 400 DAYS. With every row sharing an
                # `invited_at`, the default sort collapses onto its `id`
                # tiebreak and the last page becomes a walk through one equal
                # run — a fixture that measures the wrong thing. The same trap
                # `ds_small_datasets_cost.py`'s own guard caught on its author.
                invited_at=now - timedelta(days=index % 400),
                last_active_at=None if index % 10 == 9 else now - timedelta(days=index % 30),
            )
        )
        if len(memberships) >= 2_000:
            identity_models.TenantMembership.objects.bulk_create(memberships)
            memberships = []
    if memberships:
        identity_models.TenantMembership.objects.bulk_create(memberships)
    return made


def seed_batches(tenant, actor, *, batches: int, rows_each: int) -> int:
    """`batches` read-import batches, each with `rows_each` rows, MIXED severity.

    ⚠ **ONE BATCH IN THREE HOLDS BOTH ACCEPTED AND REJECTED ROWS**, because
    that mixture is what p065's savepoint warning is evidence OF, and because a
    fixture where every batch is clean cannot distinguish a working `rejected`
    aggregate from a column of zeros.
    """
    existing = metering_models.ReadImportBatch.objects.filter(
        file_name__startswith=f"{MARKER}-"
    ).count()
    now = datetime.now(timezone.utc)
    made = 0
    for index in range(existing, batches):
        batch = metering_models.ReadImportBatch.objects.create(
            tenant=tenant,
            file_name=f"{MARKER}-{index:07d}.csv",
            source_kind=("csv", "ami_replay", "manual")[index % 3],
            uploaded_by=actor,
            uploaded_at=now - timedelta(days=index % 365, minutes=index % 1440),
            status="posted",
            counts={"in": rows_each},
        )
        rejected = rows_each // 4 if index % 3 == 1 else 0
        warned = 1 if index % 3 == 1 else 0
        rows = []
        for row_no in range(1, rows_each + 1):
            if row_no <= rejected:
                severity = "error"
            elif row_no == rejected + 1 and warned:
                severity = "warning"
            else:
                severity = "ok"
            rows.append(
                metering_models.ReadImportRow(
                    tenant=tenant, batch=batch, row_no=row_no, severity=severity
                )
            )
        metering_models.ReadImportRow.objects.bulk_create(rows)
        made += 1
    return made


def seed_transfers(tenant, *, transfers: int) -> int:
    """`transfers` committed transfers — the UNION's SECOND LEG.

    ⚠ **THIS FIXTURE EXISTS BECAUSE THE FIRST RUN OF THIS SCRIPT PRINTED
    `transferred 0` AND STILL SAID PASS.** Every R23 figure above it was
    therefore measuring ONE leg of a two-leg union: the `transfers` leg could
    have been deleted outright and the timings would not have moved. That is
    hard-won law 7's fifth shape exactly — a number over a scope the check
    silently excludes — and the answer is to cover the scope, not to add a
    disclaimer.
    """
    accounts = list(
        customer_models.Account.objects.order_by("account_no").values_list("id", flat=True)
    )
    if len(accounts) < 2:
        sys.exit("REFUSED: fewer than two accounts — a transfer needs a from and a to")
    # ⚠ **THE DATABASE CAPS THIS AND THE SCRIPT SAYS SO RATHER THAN CRASHING.**
    # `uq_transfers_opened_account` is UNIQUE on (tenant_id, to_account_id)
    # wherever the two accounts differ — one open transfer per receiving
    # account — so a tenant with N accounts can hold at most N transfers. The
    # first draft looped past that and died on an IntegrityError, which reads
    # like a broken read model rather than a fixture asking for the impossible.
    ceiling = len(accounts)
    wanted = transfers
    transfers = min(transfers, ceiling)
    if transfers < wanted:
        print(
            f"  note: asked for {wanted} transfers and this tenant holds {ceiling} accounts; "
            f"`uq_transfers_opened_account` permits one per receiving account, so {transfers} "
            "were seeded. The cap is the database's, not this script's."
        )
    existing = Transfer.objects.filter(transfer_no__startswith=f"{MARKER}-").count()
    now = datetime.now(timezone.utc)
    made = 0
    taken = set(
        Transfer.objects.exclude(to_account_id=None).values_list("to_account_id", flat=True)
    )
    for index in range(existing, transfers):
        to_id = accounts[index % ceiling]
        from_id = accounts[(index + 1) % ceiling]
        if from_id == to_id or to_id in taken:
            continue
        taken.add(to_id)
        when = now - timedelta(days=index % 400, minutes=index % 1440)
        Transfer.objects.create(
            tenant=tenant,
            transfer_no=f"{MARKER}-{index:07d}",
            from_account_id=from_id,
            to_account_id=to_id,
            state="done",
            step=5,
            committed_at=when,
            in_date=when.date(),
            out_date=when.date(),
        )
        made += 1
    return made


def seed_moves(tenant, actor, *, moves: int) -> int:
    """`moves` lifecycle events over the tenant's accounts, move-in and move-out.

    ⚠ **THEY ARE SPREAD OVER 400 DAYS AND OVER MANY ACCOUNTS**, and roughly a
    third of the accounts get TWO events. One account, two rows is the case
    that separates this grain from the `accounts` dataset's, and a fixture
    without it would let an account-grain query pass every assertion.
    """
    account_ids = list(
        customer_models.Account.objects.order_by("account_no").values_list("id", flat=True)[
            : max(1, moves)
        ]
    )
    if not account_ids:
        sys.exit("REFUSED: this tenant has no accounts — a move record would have no anchor")
    existing = MoveRecord.objects.filter(move_no__startswith=f"{MARKER}-").count()
    now = datetime.now(timezone.utc)
    batch: list[MoveRecord] = []
    made = 0
    for index in range(existing, moves):
        account_id = account_ids[index % len(account_ids)]
        when = now - timedelta(days=index % 400, minutes=index % 1440)
        batch.append(
            MoveRecord(
                tenant=tenant,
                account_id=account_id,
                move_no=f"{MARKER}-{index:07d}",
                kind=KIND_MOVE_IN if index % 3 else KIND_MOVE_OUT,
                effective_on=when.date() + timedelta(days=1),
                performed_by=actor,
                performed_at=when,
            )
        )
        if len(batch) >= 2_000:
            MoveRecord.objects.bulk_create(batch)
            made += len(batch)
            batch = []
    if batch:
        MoveRecord.objects.bulk_create(batch)
        made += len(batch)
    return made


# ── the guards ──────────────────────────────────────────────────────────────


def _page_guards(name, first, last, streamed, *, page_size=PAGE, floor=1) -> None:
    """The guards, per report. Each names the false pass it closes."""
    if first["rows"] == 0:
        sys.exit(
            f"FAIL — {name}: page 1 served ZERO rows. A read that answers nothing reads as "
            "'no error' and this script would have measured a tenant context that was never "
            "set (hard rule 1, RLS FORCE)."
        )
    if first["rows"] > page_size:
        sys.exit(f"FAIL — {name}: page 1 served {first['rows']} rows against per={page_size}")
    filtered = first["answer"]["total"]
    if filtered < floor:
        sys.exit(
            f"FAIL — {name}: the filtered set holds {filtered} rows and this measurement "
            f"needs at least {floor} to distinguish a SQL page from a Python slice. A "
            "benchmark on a fixture too small to fail is not a benchmark."
        )
    ratio = last["seconds"] / first["seconds"] if first["seconds"] else 0
    print(
        f"  {name}: last page / first page = {ratio:.2f}×  "
        f"({last['seconds']:.3f}s vs {first['seconds']:.3f}s) · "
        f"last page against the {WORKER_TIMEOUT}s worker timeout"
    )
    # ⚠ **THE RATIO IS REPORTED AND IS NOT THE GUARD.** A deep `OFFSET` is a
    # walk however good the index is, so a ratio threshold goes red when the
    # read IMPROVES — `ds_small_datasets_cost.py` measured exactly that and
    # recorded it. What matters is whether the last page ANSWERS at all, and the
    # threshold that means something is the one a real deployment enforces.
    if last["seconds"] > WORKER_TIMEOUT:
        sys.exit(
            f"FAIL — {name}: the last page took {last['seconds']:.3f}s and a web worker is "
            f"given {WORKER_TIMEOUT}s (docker-entrypoint.sh, GUNICORN_TIMEOUT). It would not "
            "be slow in production, it would be killed before it answered."
        )
    print(f"  {name}: stream {streamed['rows']} · filtered set {filtered}")
    if streamed["rows"] != filtered:
        sys.exit(
            f"FAIL — {name}: the stream served {streamed['rows']} of the {filtered} rows in "
            "its own filtered set. NFR-5 forbids a ceiling on the export branch."
        )


def _statement_guard(name, small, big) -> None:
    """The statement count must NOT move with `per` — the batched-label check."""
    if small["statements"] != big["statements"]:
        sys.exit(
            f"FAIL — {name}: page 1 cost {small['statements']} statements at per={PAGE} and "
            f"{big['statements']} at per={BIG_PAGE}. A count that scales with the page is an "
            "N+1 in the label read, which is the one defect a wall clock hides at this size."
        )
    print(f"  {name}: {small['statements']} statements at per={PAGE} AND at per={BIG_PAGE}")


def _direction_guard(name, ascending, descending, key) -> None:
    """Two directions must REVERSE. Equal firsts mean `direction` was ignored."""
    low = key(ascending["answer"]["rows"][0])
    high = key(descending["answer"]["rows"][0])
    if low == high:
        sys.exit(
            f"FAIL — {name}: both directions opened at {low!r}. They must reverse; equal "
            "firsts mean the sort was applied in Python after the page, or not at all."
        )
    print(f"  {name}: asc opens at {low!r} · desc opens at {high!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staff", type=int, default=40_000)
    parser.add_argument("--batches", type=int, default=4_000)
    parser.add_argument("--rows-each", type=int, default=20)
    parser.add_argument("--moves", type=int, default=40_000)
    parser.add_argument("--transfers", type=int, default=400)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--index", type=int, default=94, help="perf tenant index")
    args = parser.parse_args()

    tenant = provisioner.provision(args.index)
    print(f"tenant {tenant.subdomain} ({tenant.id})")

    with core_tenancy.tenant_context(str(tenant.id)):
        actor = identity_models.User.objects.filter(tenant=tenant).order_by("created_at").first()
        if actor is None:
            sys.exit("REFUSED: this tenant has no user to act as an uploader")
        print(f"seeded {seed_staff(tenant, staff=args.staff)} new staff")
        print(
            f"seeded {seed_batches(tenant, actor, batches=args.batches, rows_each=args.rows_each)}"
            " new import batches"
        )
        print(f"seeded {seed_moves(tenant, actor, moves=args.moves)} new move records")
        print(f"seeded {seed_transfers(tenant, transfers=args.transfers)} new transfers")

        staff_total = identity_models.TenantMembership.objects.count()
        batch_total = metering_models.ReadImportBatch.objects.count()
        row_total = metering_models.ReadImportRow.objects.count()
        move_total = MoveRecord.objects.count()
        transfer_total = Transfer.objects.filter(state="done").count()
        dormant = identity_models.TenantMembership.objects.filter(
            last_active_at__isnull=True
        ).count()
        print(
            f"tenant holds {staff_total} memberships ({dormant} never signed in) · "
            f"{batch_total} batches over {row_total} file rows · {move_total} move records · "
            f"{transfer_total} committed transfers over "
            f"{customer_models.Account.objects.count()} accounts"
        )
        # ⚠ **THE UNION HAS TWO LEGS AND A FIXTURE WITH ONE MEASURES HALF OF
        # IT.** The first run of this script printed `transferred 0` and still
        # said PASS: the `transfers` leg could have been deleted and no figure
        # would have moved. Law 7's fifth shape, refused rather than disclaimed.
        if transfer_total == 0:
            sys.exit(
                "FAIL — no committed transfer in the fixture. R23 is a UNION of two tables and "
                "every figure below would be measuring one leg of it."
            )
        if dormant == 0:
            sys.exit(
                "FAIL — no dormant membership in the fixture. R36 exists to find exactly that "
                "row, and a fixture without one cannot tell a working tile from a hardcoded 0."
            )

        # ── R36 ACCESS REVIEW ───────────────────────────────────────────────
        print("\nR36 Access Review — one row per user of this tenant")
        pages = max(1, -(-staff_total // PAGE))
        first = _measure(
            "page 1 of 50", lambda: access_review.access_review(per=PAGE, page=1),
            repeat=args.repeat,
        )
        last = _measure(
            f"page {pages} (the last) of 50",
            lambda: access_review.access_review(per=PAGE, page=pages),
            repeat=args.repeat,
        )
        big = _measure(
            "page 1 of 200", lambda: access_review.access_review(per=BIG_PAGE, page=1),
            repeat=args.repeat,
        )
        ascending = _measure(
            "sort=last_active asc",
            lambda: access_review.access_review(per=PAGE, sort="last_active", direction="asc"),
            repeat=args.repeat,
        )
        descending = _measure(
            "sort=last_active desc",
            lambda: access_review.access_review(per=PAGE, sort="last_active", direction="desc"),
            repeat=args.repeat,
        )
        streamed = _measure(
            "export — the WHOLE filtered set",
            lambda: {"rows": list(access_review.access_review_stream())},
            repeat=1,
        )
        streamed["answer"] = first["answer"]
        for result in (first, last, big, ascending, descending, streamed):
            _say(result)
        _page_guards("R36", first, last, streamed, floor=1_000)
        _statement_guard("R36", first, big)
        _direction_guard("R36", ascending, descending, lambda row: row.user_name)
        tiles = first["answer"]["totals"]
        print(
            f"  R36 tiles over the WHOLE set: users {tiles['users']} · active "
            f"{tiles['active']} · never signed in {tiles['never_signed_in']} · "
            f"can approve money {tiles['can_approve_money']}"
        )
        if tiles["users"] != staff_total:
            sys.exit(
                f"FAIL — R36: the tile says {tiles['users']} and the table holds "
                f"{staff_total}. A tile struck over the page rather than the filtered set is "
                "the footing failure §7.2 exists to prevent."
            )
        # ⚠ AND THE SMALL-TENANT FIGURE, printed because it is the REAL one.
        small = _measure(
            "page 1 of 50 filtered to one role (ICP shape)",
            lambda: access_review.access_review(per=PAGE, page=1, role="executive"),
            repeat=args.repeat,
        )
        _say(small)

        # ── R32 READ IMPORT LOG ─────────────────────────────────────────────
        print("\nR32 Read Import Log — one row per read-import batch")
        pages = max(1, -(-batch_total // PAGE))
        first = _measure(
            "page 1 of 50", lambda: read_import_log.read_import_log(per=PAGE, page=1),
            repeat=args.repeat,
        )
        last = _measure(
            f"page {pages} (the last) of 50",
            lambda: read_import_log.read_import_log(per=PAGE, page=pages),
            repeat=args.repeat,
        )
        big = _measure(
            "page 1 of 200", lambda: read_import_log.read_import_log(per=BIG_PAGE, page=1),
            repeat=args.repeat,
        )
        ascending = _measure(
            "sort=rejected asc",
            lambda: read_import_log.read_import_log(per=PAGE, sort="rejected", direction="asc"),
            repeat=args.repeat,
        )
        descending = _measure(
            "sort=rejected desc",
            lambda: read_import_log.read_import_log(per=PAGE, sort="rejected", direction="desc"),
            repeat=args.repeat,
        )
        streamed = _measure(
            "export — the WHOLE filtered set",
            lambda: {"rows": list(read_import_log.read_import_log_stream())},
            repeat=1,
        )
        streamed["answer"] = first["answer"]
        for result in (first, last, big, ascending, descending, streamed):
            _say(result)
        _page_guards("R32", first, last, streamed, floor=500)
        _statement_guard("R32", first, big)
        _direction_guard("R32", ascending, descending, lambda row: row.rejected)
        tiles = first["answer"]["totals"]
        print(
            f"  R32 tiles over the WHOLE set: imports {tiles['imports']} · rows "
            f"{tiles['rows']} · accepted {tiles['accepted']} · rejected {tiles['rejected']} · "
            f"accepted share {tiles['accepted_pct']}"
        )
        # ⚠ THE FOOTING IDENTITY, on real data rather than on a fixture of three.
        if tiles["accepted"] + tiles["rejected"] != tiles["rows"]:
            sys.exit(
                f"FAIL — R32: accepted {tiles['accepted']} + rejected {tiles['rejected']} is "
                f"not rows {tiles['rows']}. The drawn footer would not foot."
            )
        if tiles["rejected"] == 0:
            sys.exit(
                "FAIL — R32: no rejected rows in the fixture. p065's savepoint warning has no "
                "evidence and a column of zeros would pass every assertion above."
            )

        # ── R23 ACCOUNT ACTIVITY ────────────────────────────────────────────
        print("\nR23 Account Activity — one row per account-lifecycle event")
        activity_total = account_activity.account_activity(per=PAGE, page=1)["total"]
        pages = max(1, -(-activity_total // PAGE))
        first = _measure(
            "page 1 of 50", lambda: account_activity.account_activity(per=PAGE, page=1),
            repeat=args.repeat,
        )
        last = _measure(
            f"page {pages} (the last) of 50",
            lambda: account_activity.account_activity(per=PAGE, page=pages),
            repeat=args.repeat,
        )
        big = _measure(
            "page 1 of 200", lambda: account_activity.account_activity(per=BIG_PAGE, page=1),
            repeat=args.repeat,
        )
        ascending = _measure(
            "sort=occurred_at asc",
            lambda: account_activity.account_activity(
                per=PAGE, sort="occurred_at", direction="asc"
            ),
            repeat=args.repeat,
        )
        descending = _measure(
            "sort=occurred_at desc",
            lambda: account_activity.account_activity(
                per=PAGE, sort="occurred_at", direction="desc"
            ),
            repeat=args.repeat,
        )
        streamed = _measure(
            "export — the WHOLE filtered set",
            lambda: {"rows": list(account_activity.account_activity_stream())},
            repeat=1,
        )
        streamed["answer"] = first["answer"]
        for result in (first, last, big, ascending, descending, streamed):
            _say(result)
        _page_guards("R23", first, last, streamed, floor=1_000)
        _statement_guard("R23", first, big)
        _direction_guard("R23", ascending, descending, lambda row: row.occurred_at)
        tiles = first["answer"]["totals"]
        print(
            f"  R23 tiles over the WHOLE set: opened {tiles['opened']} · closed "
            f"{tiles['closed']} · transferred {tiles['transferred']} · net {tiles['net']}"
        )
        if tiles["net"] != tiles["opened"] - tiles["closed"]:
            sys.exit("FAIL — R23: `net` is not `opened − closed`.")
        if tiles["opened"] == 0 or tiles["closed"] == 0:
            sys.exit(
                "FAIL — R23: the fixture holds only one kind of event, so `net` equals a tile "
                "and the subtraction is untested."
            )
        # ⚠ A TRANSFER IS COUNTED IN NEITHER `opened` NOR `closed`, measured on
        # real data rather than asserted in a docstring.
        if tiles["transferred"] == 0:
            sys.exit("FAIL — R23: `transferred` is 0, so the union's second leg is untested.")
        if tiles["events"] != tiles["opened"] + tiles["closed"] + tiles["transferred"]:
            sys.exit(
                f"FAIL — R23: events {tiles['events']} is not opened {tiles['opened']} + closed "
                f"{tiles['closed']} + transferred {tiles['transferred']} — a transfer has been "
                "folded into one of the other two."
            )
        # ⚠ **ONE ACCOUNT, TWO ROWS — the case the `accounts` dataset refuses
        # this report for.** Asserted on real data, because a fixture where
        # every account has exactly one event cannot tell the two grains apart.
        whole = account_activity.account_activity(per=None)
        per_account: dict[str, int] = {}
        for row in whole["rows"]:
            if row.account_no:
                per_account[row.account_no] = per_account.get(row.account_no, 0) + 1
        repeated = sum(1 for count in per_account.values() if count > 1)
        print(f"  R23: {repeated} accounts carry MORE THAN ONE event in this window")
        if repeated == 0:
            sys.exit(
                "FAIL — R23: no account produced two events, so this measurement cannot "
                "distinguish an event grain from an account grain — which is the whole reason "
                "the `accounts` dataset refuses this report."
            )

    print()
    print("NOT MEASURED HERE, and each has its own check:")
    print("  · RLS and tenant isolation → 10-scripts/p6_join_rls_proof.py")
    print("  · BR-REP-023's restriction on R36 → NOTHING ENFORCES IT (P5.9 is open)")
    print("  · the rendered screen → scratchpad/po-shots/joining-reads/")
    print()
    print("PASS — every guard above held.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
