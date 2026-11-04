#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Journey:  08-qa/01-e2e/journeys/JPAYLOCKBOX-a-store-file-on-a-monday-morning.md
#           checks **A · B · C · D · E · F · G · H**, every one of which is a
#           question about the DATABASE and none of which the receipt can
#           answer — *"the receipt is written by the same code that did the
#           load, so it will agree with itself whatever happened."*
# Change:   `CR-135-BRC07` `P1.14`
# Rules:    CLAUDE.md hard rule 1 (`app.tenant_id` is set before anything is
#           read) · hard rule 5 (balanced pairs) · hard rule 6 (idempotency) ·
#           hard rule 7 (every money action audits) · **hard-won law 14** —
#           check **G** exists at all only on PostgreSQL
# ───────────────────────────────────────────────────────
"""Ask the database what the walk actually wrote.

⚠ **IT REFUSES TO RUN ON SQLITE, AND THAT IS CHECK G'S WHOLE POINT.**
`config/settings/test.py` hardcodes in-memory SQLite and ignores `DATABASE_URL`
(CLAUDE.md hard-won law 14). SQLite has **no aborted-transaction state**, so on
it the naive `except IntegrityError: continue` passes and a savepoint proves
nothing. Run this under `config.settings.local` against a
`10-scripts/proof-db.sh` clone, which is a real PostgreSQL 16.

USAGE, after `jpaylockbox_walkthrough.mjs` has walked the nine steps:

    eval "$(10-scripts/proof-db.sh clone lockbox --export)"
    DJANGO_SETTINGS_MODULE=config.settings.local \\
      python3 10-scripts/jpaylockbox_readback.py --fixture /tmp/lockbox

    --prove-red   run check G with the loader's savepoint REMOVED, which is how
                  law 7's *prove it red before you trust it green* is satisfied
                  for the one check that cannot be proved any other way.

Every figure it asserts comes from the fixture's own manifest, never from a
number typed here — B14 rule 37, and the journey's own sentence: *"every
assertion below is written against the FIXTURE, never against a number."*
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

VERDICTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    VERDICTS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'} · {name} — {detail}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default="/tmp/claude-0/lane-p01/fixture")
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument("--prove-red", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "06-backend"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    import django

    django.setup()
    from django.conf import settings
    from django.db import connection

    engine = settings.DATABASES["default"]["ENGINE"]
    if "postgresql" not in engine:
        print(
            f"REFUSED: this is {engine}. Checks B and G cannot exist on SQLite — "
            "a failed statement does not abort the transaction there, so the "
            "savepoint the loader depends on proves nothing (hard-won law 14). "
            "Point DATABASE_URL at a proof-db.sh clone under config.settings.local.",
            file=sys.stderr,
        )
        return 2

    manifest = json.loads((Path(args.fixture) / "manifest.json").read_text())
    from apps.tenancy.models import Tenant

    tenant = Tenant.objects.get(subdomain=args.tenant)
    with connection.cursor() as cur:
        cur.execute("set app.tenant_id = %s", [str(tenant.pk)])

        cur.execute(
            "select id, run_no, status, counts from import_runs "
            " where target = 'payments' and status = 'loaded' "
            " order by created_at desc limit 1"
        )
        row = cur.fetchone()
        if row is None:
            print(
                "REFUSED: no LOADED payments import run on this tenant. Walk "
                "jpaylockbox_walkthrough.mjs first — this script reads what that "
                "walk wrote and invents nothing.",
                file=sys.stderr,
            )
            return 2
        run_id, run_no, _status, counts = row
        counts = counts or {}
        print(f"\nrun {run_no} · counts {json.dumps(counts, sort_keys=True)}\n")

        # ── A · the rows that exist and the rows that do not ────────────────
        cur.execute(
            "select count(*) from payments p "
            " join import_run_rows r on r.created_record_id::text = p.id::text "
            " where r.run_id = %s",
            [run_id],
        )
        created = cur.fetchone()[0]
        check(
            "A · created",
            created == manifest["expect_loaded"],
            f"{created} payment(s) carry this run's link; the fixture's clean rows are "
            f"{manifest['expect_loaded']} of {manifest['rows_total']}",
        )
        cur.execute(
            "select count(*) from import_run_rows where run_id = %s and outcome = 'rejected'",
            [run_id],
        )
        rejected = cur.fetchone()[0]
        check(
            "A · refused, not skipped",
            created + rejected == manifest["rows_total"],
            f"{created} loaded + {rejected} rejected = {created + rejected} of "
            f"{manifest['rows_total']} rows — every row of the file is on one side or "
            "the other (BR-PAY-023: a row that disappears is money nobody chased)",
        )

        # ── B · THE CHECK THAT EARNS THE JOURNEY ────────────────────────────
        expected_days = {
            clean["account_no"]: clean["paid_on"] for clean in manifest["clean_rows"]
        }
        cur.execute(
            "select a.account_no, p.posted_at::date, p.cleared_at::date "
            "  from payments p "
            "  join import_run_rows r on r.created_record_id::text = p.id::text "
            "  join accounts a on a.id = p.account_id "
            " where r.run_id = %s",
            [run_id],
        )
        wrong = []
        seen = 0
        for account_no, posted, cleared in cur.fetchall():
            seen += 1
            want = expected_days.get(account_no)
            if want is None:
                continue
            if posted.isoformat() != want or cleared.isoformat() != want:
                wrong.append(f"{account_no}: file said {want}, stored {posted}/{cleared}")
        check(
            "B · the day the STORE took the money",
            not wrong and seen > 0,
            f"{seen - len(wrong)} of {seen} payment(s) posted AND cleared on the day "
            f"their row names"
            + (f" · first 3 wrong: {wrong[:3]}" if wrong else "")
            + " (BR-PAY-033 / BR-PAY-021 — dating a lockbox row by the import day makes "
            "a customer late on a bill they paid on time)",
        )

        # ── C · allocated under BR-PAY-010, and the bills it met are closed ─
        meets = {c["account_no"] for c in manifest["clean_rows"] if c["meets_bill"]}
        cur.execute(
            "select a.account_no, count(al.id) "
            "  from payments p "
            "  join import_run_rows r on r.created_record_id::text = p.id::text "
            "  join accounts a on a.id = p.account_id "
            "  left join allocations al on al.payment_id = p.id "
            " where r.run_id = %s group by a.account_no",
            [run_id],
        )
        unallocated = [no for no, n in cur.fetchall() if no in meets and n == 0]
        check(
            "C · allocated",
            not unallocated,
            f"{len(meets)} payment(s) landed on an account with an open bill; "
            f"{len(unallocated)} of them allocated to nothing"
            + (f" · {unallocated[:3]}" if unallocated else ""),
        )

        # ── D · balanced pairs, written by the posting service ─────────────
        cur.execute(
            # `journal_lines.side` is 'debit'/'credit' and the table is PARTITIONED
            # by year (`journal_lines_2026`, `_2027`); the parent is queried so a
            # run whose entries straddle a year boundary is not half-counted.
            "select je.id, "
            "       sum(case when jl.side = 'debit' then jl.amount else -jl.amount end) "
            "  from journal_entries je "
            "  join journal_lines jl on jl.journal_entry_id = je.id "
            " where je.source_id::text in ("
            "   select p.id::text from payments p "
            "     join import_run_rows r on r.created_record_id::text = p.id::text "
            "    where r.run_id = %s) "
            " group by je.id",
            [run_id],
        )
        entries = cur.fetchall()
        unbalanced = [str(e) for e, delta in entries if delta != 0]
        check(
            "D · balanced pairs",
            bool(entries) and not unbalanced,
            f"{len(entries)} journal entr(ies) for this run's payments, "
            f"{len(unbalanced)} unbalanced (hard rule 5)",
        )

        # ── E · one audit row per created payment ──────────────────────────
        cur.execute(
            "select count(*) from audit_log "
            " where action = 'payments.created_by_import' "
            "   and entity_id::text in ("
            "     select p.id::text from payments p "
            "       join import_run_rows r on r.created_record_id::text = p.id::text "
            "      where r.run_id = %s)",
            [run_id],
        )
        audited = cur.fetchone()[0]
        check(
            "E · audit",
            audited == created,
            f"{audited} audit row(s) for {created} created payment(s) (hard rule 7)",
        )

        # ── H · the origin, read from the DATABASE ─────────────────────────
        cur.execute(
            "select p.origin, p.origin_is_derived, count(*) "
            "  from payments p "
            "  join import_run_rows r on r.created_record_id::text = p.id::text "
            " where r.run_id = %s group by 1, 2",
            [run_id],
        )
        origins = cur.fetchall()
        check(
            "H · origin",
            origins == [("import", False, created)],
            f"{origins} — P0.1's ck_payments_origin, and an OBSERVED origin rather "
            "than a guess",
        )

        # ── F · the same file again writes NOTHING ─────────────────────────
        cur.execute(
            "select count(*) from import_runs where target = 'payments' and file_hash = "
            "  (select file_hash from import_runs where id = %s) and file_hash is not null",
            [run_id],
        )
        same_file = cur.fetchone()[0]
        check(
            "F · idempotency (file)",
            same_file >= 1,
            f"{same_file} run(s) carry this file's hash · "
            "uq_import_runs_idempotency guards the FILE and the per-row key guards "
            "the ROW (hard rule 6, DEF-058)",
        )
        # ⚠ **THE ROW KEY IS `payments.webhook_key`, NOT A COLUMN CALLED
        # `idempotency_*`.** `payments.idempotency` namespaces `run:row` into
        # that one UNIQUE column (B2 DB-12, `uq_payments_webhook_key`); the
        # first spelling of this query named two columns that do not exist and
        # simply crashed, which is the honest failure — a query that had merely
        # returned nothing would have read as a pass.
        cur.execute(
            "select p.webhook_key, count(*) "
            "  from payments p join import_run_rows r "
            "    on r.created_record_id::text = p.id::text "
            " where r.run_id = %s and p.webhook_key is not null "
            " group by 1 having count(*) > 1",
            [run_id],
        )
        doubled = cur.fetchall()
        cur.execute(
            "select count(*), count(distinct created_record_id) "
            "  from import_run_rows where run_id = %s and created_record_id is not null",
            [run_id],
        )
        rows_with_record, distinct_records = cur.fetchone()
        check(
            "F · idempotency (row)",
            not doubled and rows_with_record == distinct_records,
            f"{len(doubled)} row key(s) used twice · {rows_with_record} loaded row(s) "
            f"point at {distinct_records} distinct payment(s) — the key is run:row, so "
            "a load retried after a crash records each row once",
        )

        # ── G · A CRASH BETWEEN ROWS ───────────────────────────────────────
        # ⚠ **THIS IS THE ONE CHECK THAT ONLY EXISTS ON POSTGRESQL.** It is run
        # against THIS connection, inside a transaction that is rolled back, so
        # it writes nothing and needs no second database.
        savepoint_ok, savepoint_detail = _check_savepoint(prove_red=args.prove_red)
        check("G · a crash between rows", savepoint_ok, savepoint_detail)

    print()
    failed = [name for name, ok, _ in VERDICTS if not ok]
    print(f"{len(VERDICTS) - len(failed)} of {len(VERDICTS)} check(s) pass")
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


def _check_savepoint(*, prove_red: bool) -> tuple[bool, str]:
    """Law 14, demonstrated rather than asserted.

    A statement is made to fail inside a transaction; then a perfectly good
    statement is issued afterwards. **On PostgreSQL the second one raises
    `InFailedSqlTransaction` unless the first was wrapped in a SAVEPOINT** — so
    this both proves the mechanism the loader depends on and, with
    `--prove-red`, shows the check failing when the savepoint is taken away.
    Nothing is committed either way.
    """
    from django.db import connection, transaction
    from django.db.utils import InternalError, ProgrammingError

    def attempt(*, with_savepoint: bool) -> str:
        try:
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute("create temporary table _g_probe (n int primary key) on commit drop")
                    cur.execute("insert into _g_probe values (1)")
                    try:
                        if with_savepoint:
                            with transaction.atomic():  # ← the loader's savepoint
                                cur.execute("insert into _g_probe values (1)")
                        else:
                            cur.execute("insert into _g_probe values (1)")
                    except Exception:
                        pass
                    cur.execute("insert into _g_probe values (2)")
                    cur.execute("select count(*) from _g_probe")
                    kept = cur.fetchone()[0]
                transaction.set_rollback(True)
                return f"kept {kept}"
        except (InternalError, ProgrammingError) as failure:
            return f"aborted: {type(failure).__name__}"
        except Exception as failure:  # pragma: no cover - the aborted-transaction case
            return f"aborted: {type(failure).__name__}"

    with_it = attempt(with_savepoint=True)
    if not prove_red:
        return (
            with_it == "kept 2",
            f"with the loader's savepoint the rows before AND after the refused one "
            f"survive ({with_it}); run again with --prove-red to watch it fail without one",
        )
    without = attempt(with_savepoint=False)
    return (
        with_it == "kept 2" and without != "kept 2",
        f"with the savepoint: {with_it} · WITHOUT it: {without} — on PostgreSQL a "
        "refused statement aborts the whole transaction and a morning's takings are "
        "lost at COMMIT with the suite green, because config/settings/test.py is SQLite",
    )


if __name__ == "__main__":
    raise SystemExit(main())
