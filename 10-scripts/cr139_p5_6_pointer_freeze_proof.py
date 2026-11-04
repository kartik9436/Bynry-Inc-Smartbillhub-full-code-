#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-139-BRC07 — the payments blueprint's phase 5, task `P5.6`.
#          The drawing: *"`payments.settlement_id` — nullable. Null is
#          Awaiting settlement. The third state the requirement never named,
#          made real."* It does not say the column cannot be WRITTEN.
# Rules:   CLAUDE.md hard rule 4 (financial immutability, and its PO-ruled
#          narrowing: *"`payments/0014` is the ONLY place the database's allow
#          list moves; widening it anywhere else is a new ruling"*) ·
#          hard-won law 7 (prove a guard RED, in the harness that runs it) ·
#          hard-won law 14 (the suite runs on SQLite, which has no trigger)
# Question: OQ-PAY-12608
# ───────────────────────────────────────────────────────
"""**PROVE, ON REAL POSTGRESQL, THAT `payments.settlement_id` CANNOT BE STAMPED —
AND, SINCE 2026-09-24, THAT IT IS GONE.**

⛔ **READ THIS FIRST: `OQ-PAY-12608` IS CLOSED AND THE COLUMN IS DROPPED
(`payments/0044`).** PO, verbatim: *"p7 (b) — nothing is lost, and the
payment-row lock stays exactly as it is"*. **This script is what produced that
ruling** — its three probes showed the pointer frozen in every status, so the
choice put to the PO was widen the lock, drop the column, or leave it frozen
and unwritten, and they dropped it.

So the script's VERDICT is inverted and its reasoning is kept whole: against a
database that has `payments/0044`, the column's ABSENCE is the pass and it
exits 0 without probing; against one that does not, the three probes run and
report the original finding. **It can still fail, on the thing that would
matter — the pointer coming back.** The guard that runs in every suite, on
every machine, is
`tests/test_cr139_p5_settlements.py::test_cr139_p5_6_the_pointer_column_is_gone_and_stays_gone`.

Everything below this banner is as it was written on 2026-09-23 and describes
the column in the present tense, deliberately: it is the measurement, not the
current schema.

WHY THIS SCRIPT EXISTS AND WHY A TEST COULD NOT DO ITS JOB
-----------------------------------------------------------
`payments/0005` installs `payments_payment_immutable()` through a `RunPython`
that **returns early on any non-PostgreSQL vendor**, and
`config/settings/test.py` hardcodes in-memory SQLite and ignores
`DATABASE_URL`. So a version of `settlements.ingest_payout` that stamped the
pointer would pass **every test on every machine, green**, and fail the first
real payout in production — hard-won law 14's exact shape, one table over from
the one law 14 is written about.

WHAT THE TRIGGER ACTUALLY SAYS, IN ITS OWN WORDS
-------------------------------------------------
    -- The ONLY column a payment that is already financial history may gain,
    -- and it may gain it ONCE: the deposit batch it was banked in.
    batch_stamp text[] := ARRAY['deposit_batch_id', 'updated_at'];
    ...
    -- Append-only, with ONE door: the batch stamp. Everything else is
    -- compared as a whole row, so **a column added later is frozen the day it
    -- is created.**

`settlement_id` is a column added later. A payout arrives days after its
payments cleared, so every stamp is an UPDATE on a row whose status is past
`processing`.

HOW TO RUN IT
-------------
    10-scripts/proof-db.sh clone p5db        # or any migrated database
    export PGPASSWORD=smartbillhub
    python3 10-scripts/cr139_p5_6_pointer_freeze_proof.py \\
        "postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p5db"

⚠ **AND THE TRIGGER IS STRICTER THAN `payments/0005` LEFT IT — THIS SCRIPT'S
FIRST DRAFT GOT THAT WRONG AND THE RUN IS WHAT CORRECTED IT.** The draft
expected a still-`processing` payment to ACCEPT the column, because
`payments/0005`'s processing branch was about the clearing transition. **It does
not.** The live function has been amended twice since (`US-PAY-009`'s journal
stamp and `CR-059` CS-34's three correction columns) and its processing branch
now names its mutable set explicitly:

    only status and cleared_at may change (the clearing transition,
    BR-PAY-021), plus the cheque number, memo and tender, which are
    corrections and carry no money (CR-059 CS-34).

So `settlement_id` is frozen **from the moment the row exists, in every
status** — a stronger fact than the one this script was written to show, and
one an argument from the migration file alone would have got wrong. *Reading
the code is not the same as running it* is the whole reason this is a script.

⚠ **IT PROVES THREE THINGS AND ALL THREE ARE NECESSARY** (law 7 habit 2 —
*what would make this pass wrongly?*):

  1. A `cleared` payment's `settlement_id` **CANNOT** be written. The finding.
  2. A `processing` payment's **CANNOT** either — so this is not about the
     clearing transition and there is no window in which a stamp would work.
  3. **THE CONTROL:** a `cleared` payment's `confirmation` **CAN** be written,
     because it is on `payments/0014`'s allow list (PO ruling 2026-09-02).
     Without this third half a database where the whole table happened to be
     unwritable would pass identically, and the finding would be about the
     wrong thing entirely.

It writes and rolls back inside one transaction, so it leaves no row behind.
"""

from __future__ import annotations

import sys
import uuid

try:
    import psycopg
except ImportError:  # pragma: no cover - the proof cannot run without a driver
    print("FAIL: psycopg is not installed. This proof needs a real PostgreSQL connection.")
    raise SystemExit(2)


TRIGGER = "payments_payment_immutable"


def _one(cur, sql: str, args: tuple = ()) -> object:
    cur.execute(sql, args)
    row = cur.fetchone()
    return None if row is None else row[0]


def main(url: str) -> int:
    failures: list[str] = []
    with psycopg.connect(url, autocommit=False) as conn:
        with conn.cursor() as cur:
            # ── 0 · IS THE THING WE ARE TESTING EVEN INSTALLED? ─────────────
            # A proof run against a database where the trigger never applied
            # would report "the UPDATE succeeded" and read as a refutation.
            # That is law 7's *structurally incapable of failing*, in reverse.
            installed = _one(
                cur,
                "select count(*) from pg_proc where proname = %s",
                (TRIGGER,),
            )
            if not installed:
                print(f"FAIL: {TRIGGER}() is not in this database. Nothing below proves anything.")
                return 2
            print(f"  · {TRIGGER}() is installed")

            # ── 0b · THE COLUMN IS GONE, AND THAT IS NOW THE PASS ──────────
            # ⛔ **INVERTED 2026-09-24 — `OQ-PAY-12608` CLOSED, OPTION (b).**
            # PO, verbatim: *"p7 (b) — nothing is lost, and the payment-row
            # lock stays exactly as it is"*. This script's three probes below
            # produced that ruling: they showed the pointer frozen in EVERY
            # status, so the PO dropped the column rather than widening hard
            # rule 4's allow list (`payments/0044`).
            #
            # This branch read:
            #
            #     if not has_column:
            #         print("FAIL: payments.settlement_id does not exist —
            #                run payments/0038 first.")
            #         return 2
            #
            # After `payments/0044` that was the ONLY line the script could
            # ever print — a check that can only fail, over a column the PO
            # ruled away. Hard-won law 7 calls that shape *incapable of
            # passing*, and this file's own docstring warns about its mirror.
            #
            # So the meaning is inverted rather than the file deleted: the
            # column's ABSENCE is the expected state and exit 0, and its
            # PRESENCE means the migration has not been applied to this
            # database — in which case the three probes below still run and
            # still report the finding, which is what a reviewer looking at a
            # pre-0044 server needs. **It can still fail, and it fails on the
            # thing that would matter: the pointer coming back.**
            has_column = _one(
                cur,
                "select count(*) from information_schema.columns "
                "where table_name = 'payments' and column_name = 'settlement_id'",
            )
            if not has_column:
                print("  · payments.settlement_id is ABSENT — payments/0044 has been applied")
                print(
                    "PASS: the pointer the blueprint asked for (P5.6, p024) is gone, on the "
                    "PO's ruling of 2026-09-24 (OQ-PAY-12608 option (b)). Nothing could ever "
                    "write it: the three probes below are what proved that, on PostgreSQL "
                    "16.13, and they are kept because they are the reasoning behind the "
                    "ruling. settlement_members is the record, and "
                    "settlements.awaiting_settlement_filter() reads it — as it always did."
                )
                print(
                    "  the standing guard against the column coming back runs in every suite: "
                    "tests/test_cr139_p5_settlements.py::"
                    "test_cr139_p5_6_the_pointer_column_is_gone_and_stays_gone"
                )
                return 0
            print(
                "  · payments.settlement_id EXISTS — this database predates payments/0044 "
                "(OQ-PAY-12608, 2026-09-24). The original three probes follow."
            )

            # ── a real payment row to test against ──────────────────────────
            # ⚠ **SET THE TENANT BEFORE READING A TENANT TABLE, AND THE FIRST
            # DRAFT OF THIS SCRIPT DID NOT.** It read `accounts` first and was
            # told there were none — truthfully, because with `app.tenant_id`
            # unset the policy matches ZERO ROWS AND REPORTS SUCCESS. That is
            # this branch's own finding (a lane stamped 0 of 74 payments and
            # was told it had worked) reproducing itself inside the proof
            # written to demonstrate a different guarantee. The two failures
            # below are therefore separate sentences: *no tenant at all* and
            # *a tenant with no account* are different problems.
            tenant_id = _one(cur, "select id from tenants limit 1")
            if tenant_id is None:
                print("FAIL: this database has no tenant. Run `manage.py seed_demo` first.")
                return 2
            cur.execute("select set_config('app.tenant_id', %s, true)", (str(tenant_id),))
            account_id = _one(cur, "select id from accounts where tenant_id = %s limit 1", (tenant_id,))
            if account_id is None:
                print(
                    "FAIL: tenant has no account. Run `manage.py load_sample_data --tenant <slug>`.\n"
                    "      ⚠ If you believe it HAS accounts, check `app.tenant_id` — an unset "
                    "one matches zero rows and reports success."
                )
                return 2

            payment_id = uuid.uuid4()
            cur.execute(
                # ⚠ EVERY NOT-NULL COLUMN WITH NO DEFAULT IS NAMED, and the
                # list is read off `information_schema` rather than remembered:
                # `is_partial_reversal` and `origin_is_derived` both arrived
                # after this table's first shape, and a proof that fails on an
                # INSERT proves nothing about the trigger it was written for.
                "insert into payments (id, tenant_id, account_id, amount, currency, status, "
                "type, purpose, posted_at, created_at, updated_at, is_partial_reversal, "
                "origin_is_derived) "
                "values (%s, %s, %s, 100.0, 'USD', 'processing', 'payment', 'bill', "
                "now(), now(), now(), false, false)",
                (payment_id, tenant_id, account_id),
            )

            def refuses(label: str, sql: str, args: tuple, *, expect_refusal: bool) -> None:
                """Run one UPDATE in a savepoint and record what the trigger did."""
                cur.execute("savepoint probe")
                try:
                    cur.execute(sql, args)
                except psycopg.errors.RaiseException as exc:
                    cur.execute("rollback to savepoint probe")
                    first = str(exc).strip().splitlines()[0]
                    if expect_refusal:
                        print(f"  \u2713 {label} \u2014 REFUSED")
                        print(f"        {first}")
                    else:
                        failures.append(f"{label} was REFUSED and should not have been: {first}")
                    return
                cur.execute("release savepoint probe")
                if expect_refusal:
                    failures.append(
                        f"{label} was ACCEPTED. The allow list has moved, or this database is "
                        "behind payments/0005. If it really moved, OQ-PAY-12608 has been "
                        "answered and this script and apps/payments/settlements.py must both "
                        "be amended."
                    )
                else:
                    print(f"  \u2713 {label} \u2014 accepted")

            # ── 1 · PROCESSING: refused. So there is no window. ──────────────
            refuses(
                "1 \u00b7 a PROCESSING payment refuses settlement_id",
                "update payments set settlement_id = %s where id = %s",
                (uuid.uuid4(), payment_id),
                expect_refusal=True,
            )

            # Move it to cleared, the way the clearing transition does. This
            # UPDATE is itself a check: if it were refused, every probe below
            # would be testing a row in the wrong state.
            cur.execute(
                "update payments set status = 'cleared', cleared_at = now() where id = %s",
                (payment_id,),
            )

            # ── 2 · CLEARED: refused. THE FINDING. ──────────────────────────
            refuses(
                "2 \u00b7 a CLEARED payment refuses settlement_id \u2014 THE FINDING",
                "update payments set settlement_id = %s where id = %s",
                (uuid.uuid4(), payment_id),
                expect_refusal=True,
            )

            # ── 3 · THE CONTROL — the allow list still works ─────────────────
            # Without this, a table that happened to be unwritable for any
            # reason at all would pass exactly as the finding does.
            refuses(
                "3 \u00b7 a CLEARED payment accepts `confirmation` (payments/0014's allow list)",
                "update payments set confirmation = %s where id = %s",
                ("TERM-4471", payment_id),
                expect_refusal=False,
            )

        # Nothing is kept. The proof is the refusal, not the row.
        conn.rollback()

    print()
    if failures:
        for line in failures:
            print(f"FAIL: {line}")
        return 1
    print("PROVED on PostgreSQL: payments.settlement_id is frozen IN EVERY STATUS, from the")
    print("moment the row exists — so a payout, which always arrives after the payment does,")
    print("cannot stamp it, and no earlier moment would work either.")
    print("Widening payments/0005's allow list is a PO ruling (CLAUDE.md hard rule 4).")
    print("OQ-PAY-12608 is OPEN and `apps/payments/settlements.py` stamps nothing.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
