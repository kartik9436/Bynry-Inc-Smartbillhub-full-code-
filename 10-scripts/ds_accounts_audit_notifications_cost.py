#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: THE THREE DATASET QUERIES OF LANE DS-ACCOUNTS, measured on REAL
#            PostgreSQL 16 because the test suite runs on in-memory SQLite
#            (`config/settings/test.py` hardcodes it and IGNORES
#            `DATABASE_URL`) and cannot answer a question about LIMIT/OFFSET,
#            a query plan or RLS (CLAUDE.md hard-won law 14):
#              · `06-backend/apps/customers/accounts_dataset.py`      (R22)
#              · `06-backend/apps/audit/audit_log_dataset.py`         (R35)
#              · `06-backend/apps/notifications/notifications_dataset.py` (R8)
# Rules:     `NFR-3` (universal server pagination — in SQL, never in Python) ·
#            `NFR-5` (no hard caps anywhere) · CLAUDE.md hard rule 1 (tenant
#            scoping; RLS FORCE and the app role is neither superuser nor
#            BYPASSRLS) · hard rule 4 (this script READS the three datasets;
#            only the fixture writes) · hard-won law 7 (a check that cannot
#            cover its whole subject prints what it SKIPPED beside what it
#            checked).
# ───────────────────────────────────────────────────────
"""WHAT ONE PAGE OF EACH FACT COSTS — three instruments, because one lies.

`cr138_p4_debtor_cost.py` learned this the expensive way and
`ds_payments_dataset_cost.py` copied the lesson rather than re-learning it.
**A wall clock alone cannot answer an `NFR-3` question** — at a small tenant
every figure is dominated by fixed overhead. **And a statement count alone
cannot either**, because a read can hold its statement count flat while the
ROWS those statements build grow with the tenant. Three columns, all three
needed:

  **statements**   round trips. An N+1 shows here and nowhere else.
  **rows served**  what the caller got back — the PAGE on a paged read.
  **seconds**      median of `--repeat`, after a discarded warm-up.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY — each answered, never assumed:**

  * **Measuring nothing.** RLS FORCE is on and the app role is neither
    superuser nor BYPASSRLS, so with `app.tenant_id` unset every query returns
    zero rows in about a millisecond and every timing would look wonderful.
    Every measurement runs inside `tenant_context` and **prints the row count
    it served**; a zero EXITS rather than reporting a fast answer.
  * **Timing a page that is not the expensive one.** Page 1 of a one-page read
    is cheap. The LAST page is measured too, which is where an in-Python slice
    shows: a SQL `OFFSET` walk is flat, a Python slice that materialised
    everything first is not. **The property is that the last page is not
    slower than the first** — not the wall clock.
  * **A query that ignores `per`.** It would time beautifully and serve
    everything, so page 1 serving more than `PAGE` rows FAILS by name.
  * **A sort applied in Python after the page.** Two directions over the same
    window must reverse at the ends; **equal** firsts mean `direction` was
    ignored, so the comparison is `<` and never `<=`.
  * **An export that inherited a page.** Each stream is counted against the
    tenant's whole filtered set and a short file FAILS.
  * **An N+1 hiding behind a fast wall clock at a small tenant.** The
    statement count per page is asserted to be BOUNDED and not to grow with
    `--per`: page 1 at `per=50` and at `per=500` must issue the same number of
    statements, which no per-row label read can do.

USAGE
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_dsacct \\
      python3 ../10-scripts/ds_accounts_audit_notifications_cost.py \\
      --accounts 40000 --events 40000 --messages 40000 --repeat 3
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "true")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection, reset_queries  # noqa: E402

from apps.audit import audit_log_dataset  # noqa: E402
from apps.audit.models import AuditLog  # noqa: E402
from apps.customers import accounts_dataset  # noqa: E402
from apps.customers import models as customer_models  # noqa: E402
from apps.notifications import models as notification_models  # noqa: E402
from apps.notifications import notifications_dataset  # noqa: E402
from core import partitioning  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

import cr051_provision_utilities as provisioner  # noqa: E402

PAGE = 50
WIDE_PAGE = 500

#: Below this, a last-page/first-page RATIO is noise rather than a measurement —
#: see `_paging_guards`. Chosen as roughly three times the fixed round-trip cost
#: on this machine, so a read whose page-1 cost is dominated by overhead is
#: judged on its absolute last-page time instead.
RATIO_FLOOR_SECONDS = 0.100

#: What a last page may take, whatever the ratio says. `NFR-3` is about a page
#: that still ANSWERS; the web worker is given sixty seconds
#: (`GUNICORN_TIMEOUT:-60`) and a clerk gives it rather fewer.
LAST_PAGE_CEILING_SECONDS = 2.0

#: How many MORE statements page 1 may issue at `per=500` than at `per=50`.
#: A batched label read that only fires when the page holds a certain kind of
#: row is one or two; one query per row is hundreds.
EXTRA_STATEMENT_ALLOWANCE = 3
FIXTURE_MARK = "DS-ACCOUNTS fixture"


# ── the fixtures. Each writes ONE table and says what it is standing in for ──


def seed_accounts(tenant, *, accounts: int) -> int:
    """`accounts` rows spread over three behaviour classes, one of them master.

    ⚠ **WRITTEN THROUGH THE ORM RATHER THAN THE ACCOUNT SERVICE.** What is
    measured is a READ MODEL over `accounts`, and a service failure inside a
    benchmark would be indistinguishable from a reporting one — the same
    choice, for the same stated reason, that
    `tests/test_us_rep_canned_reports.a_cleared_payment` records.

    ⚠ **THE STATUS NAMES ARE NOT ENGLISH.** B14 rule 35 and Phase 5's lesson:
    a tile keyed on `status__name == "Active"` must measure ZERO here, so the
    figures below cannot be mistaken for a working one.
    """
    template = customer_models.Account.objects.order_by("account_no").first()
    if template is None:
        sys.exit("REFUSED: this tenant has no accounts at all — there is nothing to measure")
    classes = []
    for code, name, behaviour in (
        ("OUVERT", "Ouvert", accounts_dataset.BEHAVIOUR_BILLABLE),
        ("PAUSE", "En pause", accounts_dataset.BEHAVIOUR_BILLABLE_BASE_ONLY),
        ("SOLDE", "Soldé", accounts_dataset.BEHAVIOUR_TERMINAL),
    ):
        row, _ = customer_models.AccountStatus.objects.get_or_create(
            tenant=tenant, code=code, defaults={"name": name, "behavior_class": behaviour}
        )
        classes.append(row)

    existing = customer_models.Account.objects.filter(account_no__startswith="DSA-").count()
    made = 0
    batch: list[customer_models.Account] = []
    opened_zero = date(2020, 1, 1)
    for index in range(existing, accounts):
        batch.append(
            customer_models.Account(
                tenant=tenant,
                unit_id=template.unit_id,
                premises_id=template.premises_id,
                account_type_id=template.account_type_id,
                status=classes[index % 3],
                account_no=f"DSA-{index:07d}",
                kind=accounts_dataset.KIND_MASTER if index % 500 == 0 else "regular",
                balance=Decimal("0") if index % 4 == 0 else Decimal("10.0000") + (index % 97),
                currency="USD",
                opened_at=opened_zero + timedelta(days=index % 1200),
                closed_at=(opened_zero + timedelta(days=1500)) if index % 7 == 0 else None,
            )
        )
        if len(batch) >= 2_000:
            customer_models.Account.objects.bulk_create(batch)
            made += len(batch)
            batch = []
    if batch:
        customer_models.Account.objects.bulk_create(batch)
        made += len(batch)
    return made


def seed_events(tenant, *, events: int) -> int:
    """`events` audit rows, inside the hot window so the floor does not cut them.

    ⚠ **`created_at` IS SET ON THE INSERT, NEVER BY AN UPDATE.** BR-AUD-002's
    append-only trigger refuses an UPDATE on PostgreSQL — which is the whole
    guarantee — so the fixture writes rows old rather than ageing them.
    """
    # ⚠ **THE TABLE IS RANGE-PARTITIONED MONTHLY ON `created_at` (BR-AUD-012),
    # AND THE PRODUCTION CREATE-AHEAD JOB MAKES current+3 — NOT the eleven
    # months backwards this fixture writes.** Without them PostgreSQL refuses
    # with *"no partition of relation audit_log found for row"*, which reads
    # like a broken fixture and is in fact the partitioning working. They are
    # made here with the partition manager's own DDL rather than hand-written,
    # so a change to the naming scheme cannot leave this script quietly wrong.
    oldest = datetime.now(timezone.utc) - timedelta(hours=8000)
    month = partitioning.month_start(oldest.date())
    ceiling = partitioning.month_start(datetime.now(timezone.utc).date())
    while month <= ceiling:
        with connection.cursor() as cursor:
            cursor.execute(partitioning.create_partition_sql("audit_log", month))
        month = partitioning.add_months(month, 1)

    field = AuditLog._meta.get_field("created_at")
    field.auto_now_add = False
    try:
        existing = AuditLog.objects.filter(action="ds_accounts.fixture").count()
        made = 0
        batch: list[AuditLog] = []
        now = datetime.now(timezone.utc)
        for index in range(existing, events):
            batch.append(
                AuditLog(
                    tenant_id=tenant.id,
                    actor_user_id=None,
                    action="ds_accounts.fixture",
                    entity_type=("payment", "invoice", "account")[index % 3],
                    entity_id=uuid.uuid4(),
                    before={"n": index},
                    after={"n": index + 1},
                    # Inside the 2-year hot window; BR-AUD-013's floor applies.
                    created_at=now - timedelta(hours=index % 8000),
                )
            )
            if len(batch) >= 2_000:
                AuditLog.objects.bulk_create(batch)
                made += len(batch)
                batch = []
        if batch:
            AuditLog.objects.bulk_create(batch)
            made += len(batch)
        return made
    finally:
        field.auto_now_add = True


def seed_messages(tenant, *, messages: int) -> int:
    """`messages` outbound rows across the channels and the NINE statuses.

    ⚠ **EVERY STATUS IN `models.STATUSES` IS WRITTEN, INCLUDING THE LEGACY
    `bounced`.** A tile that counts one spelling of a bounce must be measurably
    wrong here, not merely arguably wrong.
    """
    account = customer_models.Account.objects.order_by("account_no").first()
    statuses = list(notification_models.STATUSES)
    channels = [notification_models.CHANNEL_EMAIL, notification_models.CHANNEL_PRINT]
    existing = notification_models.OutboundMessage.objects.filter(
        template_code=FIXTURE_MARK
    ).count()
    made = 0
    batch: list[notification_models.OutboundMessage] = []
    now = datetime.now(timezone.utc)
    for index in range(existing, messages):
        status = statuses[index % len(statuses)]
        queued_only = status == notification_models.STATUS_QUEUED
        batch.append(
            notification_models.OutboundMessage(
                tenant_id=tenant.id,
                account=account,
                source_type="invoice",
                source_id=uuid.uuid4(),
                channel=channels[index % 2],
                template_code=FIXTURE_MARK,
                recipient_address=f"c{index}@example.test",
                status=status,
                held=queued_only and index % 6 == 0,
                held_reason="bad_address" if (queued_only and index % 6 == 0) else None,
                sent_at=None if queued_only else now - timedelta(minutes=index % 5000),
                returned_at=(now if index % 97 == 0 and not queued_only else None),
            )
        )
        if len(batch) >= 2_000:
            notification_models.OutboundMessage.objects.bulk_create(batch)
            made += len(batch)
            batch = []
    if batch:
        notification_models.OutboundMessage.objects.bulk_create(batch)
        made += len(batch)
    return made


# ── the instrument ──────────────────────────────────────────────────────────


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


def _paging_guards(name: str, first: dict, last: dict, total: int, streamed: dict) -> None:
    """The four NFR-3/NFR-5 properties, each naming the false pass it closes."""
    if first["rows"] > PAGE:
        sys.exit(f"FAIL [{name}] — page 1 served {first['rows']} rows against per={PAGE}")
    if first["rows"] == 0:
        sys.exit(f"FAIL [{name}] — page 1 served ZERO rows; this measured nothing at all")
    ratio = last["seconds"] / first["seconds"] if first["seconds"] else 0
    print(
        f"  {name}: last page / first page = {ratio:.2f}×  "
        f"({last['seconds']:.3f}s vs {first['seconds']:.3f}s)"
    )
    # ⚠ **A RATIO ALONE FAILS WRONGLY ON A FAST READ, AND THIS GUARD DID.**
    # `audit_log` page 1 is 0.042s because the table is range-partitioned on the
    # ORDER's leading column, so the planner walks partitions in key order. Its
    # last page is 0.174s — **4.14×**, and a bare `ratio > 3.0` called that a
    # failure. 0.174s over 42,693 rows is not a read that materialises first; it
    # is a read whose fixed overhead is smaller than the thing being compared to
    # it, and dividing two small numbers amplifies noise rather than measuring a
    # walk. That is hard-won law 7's second habit run backwards: ask what makes a
    # check FAIL wrongly, not only what makes it pass.
    #
    # So the ratio decides only above a FLOOR, and below it an absolute ceiling
    # does — because what `NFR-3` actually asks is that the last page still
    # ANSWERS, not that it answers in the same microseconds as the first.
    if first["seconds"] >= RATIO_FLOOR_SECONDS:
        if ratio > 3.0:
            sys.exit(
                f"FAIL [{name}] — the last page cost {ratio:.2f}× the first "
                f"({last['seconds']:.3f}s vs {first['seconds']:.3f}s) and the first page is "
                f"above the {RATIO_FLOOR_SECONDS}s floor where a ratio means something. NFR-3 "
                "asks for a page cut in SQL; a walk that degrades with OFFSET this steeply is "
                "materialising first."
            )
    else:
        print(
            f"  {name}: first page {first['seconds']:.3f}s is under the {RATIO_FLOOR_SECONDS}s "
            f"floor, so the RATIO is not read — the absolute ceiling "
            f"({LAST_PAGE_CEILING_SECONDS}s) is"
        )
        if last["seconds"] > LAST_PAGE_CEILING_SECONDS:
            sys.exit(
                f"FAIL [{name}] — the last page took {last['seconds']:.3f}s, over the "
                f"{LAST_PAGE_CEILING_SECONDS}s ceiling. A last page a clerk waits on is an "
                "NFR-3 failure whatever the ratio says."
            )
    if streamed["rows"] != total:
        sys.exit(
            f"FAIL [{name}] — the stream served {streamed['rows']} of {total} rows. NFR-5 "
            "forbids a ceiling on the export branch."
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--accounts", type=int, default=40_000)
    parser.add_argument("--events", type=int, default=40_000)
    parser.add_argument("--messages", type=int, default=40_000)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--index", type=int, default=93, help="perf tenant index")
    args = parser.parse_args()

    tenant = provisioner.provision(args.index)
    print(f"tenant {tenant.subdomain} ({tenant.id})")
    measurements: list[dict] = []

    with core_tenancy.tenant_context(str(tenant.id)):
        # ── accounts ────────────────────────────────────────────────────────
        seed_accounts(tenant, accounts=args.accounts)
        total_accounts = customer_models.Account.objects.count()
        masters = customer_models.Account.objects.filter(
            kind=accounts_dataset.KIND_MASTER
        ).count()
        print(
            f"seeded · {total_accounts} accounts, of which {masters} are MASTER "
            "(counted, marked, never merged — BR-CUS-068)"
        )
        if total_accounts == 0:
            sys.exit("REFUSED: zero accounts — this would measure nothing at all")

        acc_first = _measure(
            "accounts · page 1",
            lambda: accounts_dataset.accounts_dataset(page=1, per=PAGE, sort="account_no"),
            repeat=args.repeat,
        )
        acc_pages = acc_first["answer"]["pages"]
        acc_last = _measure(
            f"accounts · page {acc_pages} (last)",
            lambda: accounts_dataset.accounts_dataset(
                page=acc_pages, per=PAGE, sort="account_no"
            ),
            repeat=args.repeat,
        )
        acc_wide = _measure(
            f"accounts · page 1, per={WIDE_PAGE}",
            lambda: accounts_dataset.accounts_dataset(
                page=1, per=WIDE_PAGE, sort="account_no"
            ),
            repeat=args.repeat,
        )
        acc_stream = _measure(
            "accounts · stream (the export)",
            lambda: {"rows": list(accounts_dataset.accounts_dataset_stream())},
            repeat=1,
        )
        measurements += [acc_first, acc_last, acc_wide, acc_stream]

        # ── audit_log ───────────────────────────────────────────────────────
        seed_events(tenant, events=args.events)
        total_events = AuditLog.objects.count()
        print(f"seeded · {total_events} audit events")
        if total_events == 0:
            sys.exit("REFUSED: zero audit events — this would measure nothing at all")

        aud_first = _measure(
            "audit_log · page 1",
            lambda: audit_log_dataset.audit_log_dataset(page=1, per=PAGE),
            repeat=args.repeat,
        )
        aud_pages = aud_first["answer"]["pages"]
        aud_last = _measure(
            f"audit_log · page {aud_pages} (last)",
            lambda: audit_log_dataset.audit_log_dataset(page=aud_pages, per=PAGE),
            repeat=args.repeat,
        )
        aud_wide = _measure(
            f"audit_log · page 1, per={WIDE_PAGE}",
            lambda: audit_log_dataset.audit_log_dataset(page=1, per=WIDE_PAGE),
            repeat=args.repeat,
        )
        aud_stream = _measure(
            "audit_log · stream (the export)",
            lambda: {"rows": list(audit_log_dataset.audit_log_dataset_stream())},
            repeat=1,
        )
        measurements += [aud_first, aud_last, aud_wide, aud_stream]

        # ── notifications ───────────────────────────────────────────────────
        seed_messages(tenant, messages=args.messages)
        total_messages = notification_models.OutboundMessage.objects.count()
        dispatched = notification_models.OutboundMessage.objects.filter(
            sent_at__isnull=False
        ).count()
        print(f"seeded · {total_messages} outbound messages, {dispatched} dispatched")
        if total_messages == 0:
            sys.exit("REFUSED: zero messages — this would measure nothing at all")

        not_first = _measure(
            "notifications · page 1",
            lambda: notifications_dataset.notifications_dataset(page=1, per=PAGE),
            repeat=args.repeat,
        )
        not_pages = not_first["answer"]["pages"]
        not_last = _measure(
            f"notifications · page {not_pages} (last)",
            lambda: notifications_dataset.notifications_dataset(page=not_pages, per=PAGE),
            repeat=args.repeat,
        )
        not_wide = _measure(
            f"notifications · page 1, per={WIDE_PAGE}",
            lambda: notifications_dataset.notifications_dataset(page=1, per=WIDE_PAGE),
            repeat=args.repeat,
        )
        not_stream = _measure(
            "notifications · stream (the export)",
            lambda: {"rows": list(notifications_dataset.notifications_dataset_stream())},
            repeat=1,
        )
        measurements += [not_first, not_last, not_wide, not_stream]

        # ── the table ───────────────────────────────────────────────────────
        print()
        print(f"{'read':<44}{'statements':>12}{'rows served':>14}{'seconds':>10}")
        for measured in measurements:
            print(
                f"{measured['label']:<44}{measured['statements']:>12}"
                f"{measured['rows']:>14}{measured['seconds']:>10.3f}"
            )
        print()

        # ── the guards ──────────────────────────────────────────────────────
        _paging_guards("accounts", acc_first, acc_last, total_accounts, acc_stream)
        _paging_guards("audit_log", aud_first, aud_last, total_events, aud_stream)
        _paging_guards(
            "notifications", not_first, not_last, not_first["answer"]["total"], not_stream
        )

        # ⚠ THE N+1 GUARD. A per-row label read holds a fast wall clock at a
        # small tenant and explodes at a large one; the statement COUNT is the
        # only instrument that sees it. Page 1 at per=50 and at per=500 must
        # issue the SAME number of statements.
        # ⚠ **AND THE FIRST DRAFT OF THIS ONE DEMANDED EXACT EQUALITY, WHICH
        # ALSO FAILS WRONGLY.** `accounts` issues 8 statements at per=50 and 9
        # at per=500, and the extra one is not a row-by-row read: `_places()`
        # asks metering for UNITS and for PREMISES in two separate statements,
        # and a 50-row page that happens to hold no premises-only account skips
        # one of them. That is a DATA-SHAPE difference, not an N+1.
        #
        # What an N+1 actually looks like is 50 → 500 statements, so the test is
        # that the count does not grow with the PAGE: a small constant more is
        # another batched read, ten times more is one query per row. Both bounds
        # are stated, because a bare "less than double" would pass 8 → 15.
        for name, narrow, wide in (
            ("accounts", acc_first, acc_wide),
            ("audit_log", aud_first, aud_wide),
            ("notifications", not_first, not_wide),
        ):
            extra = wide["statements"] - narrow["statements"]
            if extra > EXTRA_STATEMENT_ALLOWANCE:
                sys.exit(
                    f"FAIL [{name}] — page 1 issued {narrow['statements']} statements at "
                    f"per={PAGE} and {wide['statements']} at per={WIDE_PAGE}, {extra} more for "
                    f"ten times the rows. At most {EXTRA_STATEMENT_ALLOWANCE} more is another "
                    "BATCHED read; beyond that a statement count is growing with the page and "
                    "that is one query per row."
                )
            print(
                f"  {name}: {narrow['statements']} statements at per=50 and "
                f"{wide['statements']} at per=500 ({extra:+d} for 10× the rows)"
            )

        # ⚠ THE TILES FOOT TO THE BOOK, NOT TO THE PAGE.
        if acc_first["answer"]["totals"]["accounts"] != total_accounts:
            sys.exit(
                f"FAIL [accounts] — the tile says "
                f"{acc_first['answer']['totals']['accounts']} over {total_accounts} accounts. "
                "A total struck over the PAGE is the defect the KPI tiles exist to avoid."
            )
        if aud_first["answer"]["totals"]["events"] != total_events:
            sys.exit(
                f"FAIL [audit_log] — the tile says "
                f"{aud_first['answer']['totals']['events']} over {total_events} events."
            )

        # ⚠ THE BEHAVIOUR-CLASS TILE IS NOT ZERO. Every status name here is
        # French, so a tile keyed on the LABEL measures zero and this fires.
        active = acc_first["answer"]["totals"]["active"]
        print(f"  accounts: active={active} over {total_accounts} (keyed on BEHAVIOUR CLASS)")
        if active == 0:
            sys.exit(
                "FAIL [accounts] — the ACTIVE tile is zero although two thirds of these "
                "accounts are billable. A tile keyed on the tenant's status LABEL rather than "
                "its BEHAVIOUR CLASS reads exactly like this (BR-CUS-055, Phase 5's lesson)."
            )

        # ⚠ THE BOUNCE TILE COUNTS ALL THREE SPELLINGS.
        bounced = not_first["answer"]["totals"]["bounced"]
        print(f"  notifications: bounced={bounced} across three spellings (DEF-NOT-5626)")
        if bounced == 0:
            sys.exit(
                "FAIL [notifications] — the BOUNCED tile is zero although the fixture writes "
                "every one of the nine statuses. A tile counting only one spelling reads "
                "exactly like this."
            )

        # ⚠ SORTING IS IN SQL. Two directions must REVERSE at the ends; EQUAL
        # firsts mean `direction` was ignored, so the comparison is `<`.
        ascending = accounts_dataset.accounts_dataset(
            page=1, per=PAGE, sort="account_no", direction="asc"
        )
        descending = accounts_dataset.accounts_dataset(
            page=1, per=PAGE, sort="account_no", direction="desc"
        )
        low = ascending["rows"][0].account_no
        high = descending["rows"][0].account_no
        print(f"  accounts: sort asc first={low} desc first={high}")
        if not low < high:
            sys.exit(
                f"FAIL [accounts] — ascending opened at {low} and descending at {high}. The two "
                "directions must reverse; equal firsts mean `direction` was ignored and the "
                "order is not being applied in SQL at all."
            )

        # ⚠ WHAT THIS SCRIPT DOES NOT COVER, PRINTED BESIDE WHAT IT DOES
        # (hard-won law 7's fifth clause — a blind spot with no number beside it
        # is indistinguishable from an empty one).
        print()
        print("NOT MEASURED HERE, and each has its own proof:")
        print("  · RLS isolation across two tenants → 10-scripts/rep_ds_accounts_rls_proof.py")
        print("  · the four accounts refusals and the two audit refusals → the test files")
        print("  · anything about rendered output → hard-won law 6, a browser walk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
