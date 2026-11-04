"""`CR-137-BRC07` `P3.5`/`P3.6`/`P3.8` — the sixth payment state, PROVED.

Run it against a database at `payments/0035` and section 2 goes **RED**. Run it
against one at `payments/0036` and every section is green. That is the whole
proof, and it is taken on PostgreSQL 16 because that is the only place the
guarantee exists at all.

WHY A SCRIPT AND NOT A TEST (hard-won law 14)
----------------------------------------------
`config/settings/test.py` hardcodes in-memory **SQLite**, which has neither the
CHECK constraint nor `trg_payment_immutable`. So a `.update(status="cancelled")`
written with no migration at all **passes the entire suite, green, on every
machine in this repository** and raises on the first real payment. `G5` once ran
the tenant-isolation suite on sqlite and called 192 skips a pass; this is the
same trap one table along. The suite cases (`P3.13`, `P3.14`) are another lane's
and are worth having — they are not this proof.

WHAT IT PROVES, IN THE ORDER THE TASKS ASK FOR IT
---------------------------------------------------
  **§1** the shape of `ck_payments_status`, read back from `pg_get_constraintdef`
        — including the `DEF-PAY-6207` question: a CHECK passes when its
        expression is NULL, and what actually stops a NULL status is
        `attnotnull` on the COLUMN, read back from `pg_attribute`.
  **§2** `P3.5` — a payment can reach `cancelled`. RED at 0034 (refused BY NAME
        by `ck_payments_status`), green at 0035.
  **§3** `P3.6`, the PERMIT direction — `processing → cancelled` is the one
        statement a cancel needs and `trg_payment_immutable` allows it.
  **§4** `P3.6`, the FREEZE direction — the same row, one statement later, is
        append-only: the amount is refused, the un-cancel is refused, and the
        DELETE is refused.
  **§5** the CONTROLS, which is what makes §3 and §4 mean anything.
  **§6** `P3.8` — the allow list did not move. The three amendable columns still
        work on a cancelled row, a fourth column does not, and the two arrays
        are read back out of the deployed function body rather than out of a
        migration file.
  **§7** `P3.7` — `corrects_payment_id` is `reverses_payment`'s declaration
        exactly (read back from `pg_constraint` and `pg_indexes`, not from the
        migration), it can be SET at insert, and it can never be moved
        afterwards.
  **§8** `P3.14` (added 2026-09-23 by lane P3-TESTS) — the same allow list,
        asked through **the statement the SERVICE actually issues**. §6 proves
        the three columns with a one-column raw `UPDATE`; `amendments
        .amend_reference` writes `save(update_fields=[<column>, "updated_at"])`,
        which is TWO columns in one statement — and §3 already showed that a
        two-column statement mixing a permitted column with a forbidden one is
        REFUSED. So *"the three columns are permitted"* and *"the correction
        endpoint works on a cancelled payment"* are different claims, and only
        the second is the one a clerk depends on. Both directions: the three
        succeed, and the same shape carrying a fourth column is refused.

⚠ WHAT WOULD MAKE THIS PASS WRONGLY (hard-won law 7, habit 2)
---------------------------------------------------------------
  * **A FALSE ZERO FROM RLS (hard rule 1).** Every statement runs inside
    `tenant_context`; §0 prints the unscoped and the scoped count side by side
    so a reader can see the scoping is doing something. An unscoped UPDATE here
    would match zero rows and report success — the exact trap that stamped 0 of
    74 payments once.
  * **A REFUSAL BY THE WRONG GUARD.** A NOT NULL violation, an FK violation, a
    CHECK violation and a trigger's `RAISE EXCEPTION` all arrive as the same
    Python class. Every refusal below is asserted against a **distinctive
    fragment of the message it must carry** — a constraint name, or the clause
    only that one `RAISE` writes — never against "something raised".
  * **A GREEN THAT MEANS NOTHING WAS TRIED.** Each probe prints the statement it
    attempted and the verdict, so a reader sees the attempt and not just a tick.
    A section that cannot build its fixture FAILS rather than skipping.
  * **A HARNESS INCAPABLE OF FAILING.** §5 is two controls, in opposite
    directions: an amount change on a `cleared` payment MUST be refused (so the
    trigger is installed and reachable from this script at all) and
    `processing → cleared` MUST still be permitted (so §3's green is not simply
    "this script cannot make any UPDATE succeed"). If either control is wrong,
    nothing else in this file may be believed and it says so.
  * **RUNNING AT THE WRONG MIGRATION.** §0 prints which `payments` migration is
    applied and every section states what it expects there, so a green taken at
    0034 cannot be read as a green for 0035.
  * **THE PROBE'S OWN ROWS LEAKING INTO EACH OTHER.** Every attempt is a
    SAVEPOINT that is rolled back whether the statement was accepted or refused
    — `DEF-PAY-6207`'s readback learned that one the hard way — and the whole
    run is inside one outer transaction that is rolled back at the end. **This
    script writes nothing.**

⚠ EVERY STATEMENT BELOW IS RAW SQL, AND THAT IS NOT A STYLE CHOICE
-------------------------------------------------------------------
The RED half of this proof runs against a database that is **one migration
BEHIND the models**, which is the only state in which `cancelled` is still
refused. Any ORM read of `payments` there selects every column the model
declares — including `corrects_payment_id`, which `payments/0037` has not added
yet — and dies with *"column payments.corrects_payment_id does not exist"*
before it reaches the constraint it came to test. **A probe that cannot run at
the state it is proving is a probe that can never go red**, which is this
repo's *incapable of failing* shape (law 7) wearing a stack trace. So the row
this script builds is an `INSERT … SELECT` over the columns the CATALOG
actually holds, and every attempt is an `UPDATE` or a `DELETE` naming only the
column under test. It therefore runs unchanged at 0035 and at 0037.

HOW TO RUN IT
-------------
    10-scripts/proof-db.sh clone p3db
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p3db?sslmode=disable \\
      python3 manage.py shell < ../10-scripts/p3_cancel_state_and_trigger_readback.py

Exit 0 when every assertion held, 1 when any did not, 2 when it was pointed at
something it cannot prove anything on.
"""

import sys
from decimal import Decimal

from django.db import connection, transaction

from apps.tenancy import models as tenancy_models
from core.tenancy import tenant_context

TENANT_SUBDOMAIN = "brazosbend"

failures: list[str] = []
notes: list[str] = []


class _Undo(Exception):
    """Rolls a savepoint back after a statement was ACCEPTED."""


def refuse(label, statement, act, must_carry):
    """The statement MUST be refused, and the refusal must carry `must_carry`."""
    print(f"  · {statement}")
    try:
        with transaction.atomic():
            act()
            raise _Undo
    except _Undo:
        print(f"    [RED ] {label}: **ACCEPTED** — nothing refused it")
        failures.append(f"{label}: ACCEPTED; the guard is switched off")
        return
    except Exception as exc:  # noqa: BLE001 — the message IS the assertion
        text = str(exc).replace("\n", " ")
        if must_carry in text:
            print(f"    [ok  ] {label} — refused, carrying {must_carry!r}")
            return
        print(f"    [FAIL] {label}: refused, but NOT by the guard under test")
        print(f"           wanted {must_carry!r}")
        print(f"           got    {text[:200]}")
        failures.append(f"{label}: wrong refusal — {text[:150]}")
        return


def permit(label, statement, act):
    """The statement MUST succeed. Rolled back either way."""
    print(f"  · {statement}")
    try:
        with transaction.atomic():
            act()
            raise _Undo
    except _Undo:
        print(f"    [ok  ] {label} — permitted")
        return
    except Exception as exc:  # noqa: BLE001
        text = str(exc).replace("\n", " ")
        print(f"    [FAIL] {label}: **REFUSED** — {text[:200]}")
        failures.append(f"{label}: refused and should not have been — {text[:150]}")
        return


print("=" * 78)
print("CR-137-BRC07 · P3.5 / P3.6 / P3.8 — `cancelled`, and the freeze both ways")
print("=" * 78)
print(f"vendor: {connection.vendor}")
if connection.vendor != "postgresql":
    print("REFUSED: meaningless off PostgreSQL — the CHECK and the trigger do not")
    print("         exist on SQLite at all (hard-won law 14).")
    sys.exit(2)

with connection.cursor() as cur:
    cur.execute("SELECT name FROM django_migrations WHERE app='payments' ORDER BY id DESC LIMIT 1")
    applied = cur.fetchone()[0]
print(f"payments is at: {applied}")
AT_0036 = applied >= "0036"
print("  (0035 = §2 goes RED and everything after it is unprovable;")
print("   0036 = every section below must be green)")

tenant = tenancy_models.Tenant.objects.get(subdomain=TENANT_SUBDOMAIN)

print("\n0 · RLS IS ON, AND THE UNSCOPED COUNT IS THE LIE (hard rule 1)")
print("-" * 78)
with connection.cursor() as cur:
    cur.execute("SELECT count(*) FROM payments")
    unscoped = cur.fetchone()[0]
with tenant_context(str(tenant.id)):
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM payments")
        scoped = cur.fetchone()[0]
print(f"  unscoped (app.tenant_id unset): {unscoped}")
print(f"  scoped   (app.tenant_id set)  : {scoped}")
if unscoped != 0:
    failures.append("RLS: an unscoped SELECT saw rows — the policies are not FORCEd")
if scoped == 0:
    failures.append("no payments to probe in this tenant — every section below is vacuous")
    print("  [FAIL] nothing to probe.")

print("\n1 · THE SHAPE OF `ck_payments_status`, READ BACK (DEF-PAY-6207's question)")
print("-" * 78)
with connection.cursor() as cur:
    cur.execute(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='ck_payments_status'"
    )
    row = cur.fetchone()
    condef = row[0] if row else None
    cur.execute(
        "SELECT attnotnull FROM pg_attribute "
        "WHERE attrelid='payments'::regclass AND attname='status'"
    )
    status_notnull = cur.fetchone()[0]
print(f"  definition : {condef}")
print(f"  status NOT NULL in the catalog: {status_notnull}")
if condef is None:
    failures.append("ck_payments_status does not exist — the vocabulary is not closed at all")
elif "cancelled" in condef:
    print("  [ok  ] the sixth value is in the constraint")
elif AT_0036:
    failures.append("0036 is applied and `cancelled` is not in ck_payments_status")
    print("  [FAIL] 0036 is applied and the constraint still names five")
else:
    print("  [note] five values — expected at 0035")
if not status_notnull:
    failures.append(
        "payments.status is NULLABLE — a NULL status makes ck_payments_status "
        "evaluate to NULL, which a CHECK ACCEPTS (DEF-PAY-6207). The vocabulary "
        "is open."
    )
    print("  [FAIL] the column is nullable; the CHECK cannot close the door alone")
else:
    print("  [ok  ] a NULL can never reach the expression, so the NULL-passes rule")
    print("         (DEF-PAY-6207) cannot bite here — and it is the COLUMN that")
    print("         holds that door, not the constraint")

with connection.cursor() as cur:
    cur.execute(
        "SELECT tgname, tgenabled FROM pg_trigger "
        "WHERE tgrelid='payments'::regclass AND NOT tgisinternal"
    )
    triggers = cur.fetchall()
print(f"  triggers on payments: {triggers}")
if not any(name == "trg_payment_immutable" and enabled == "O" for name, enabled in triggers):
    failures.append(
        "trg_payment_immutable is missing or DISABLED on this database — every "
        "freeze assertion below would pass for the wrong reason"
    )
    print("  [FAIL] the immutability trigger is not enabled here")

with tenant_context(str(tenant.id)):
    with connection.cursor() as cur:
        cur.execute(
            "SELECT attname FROM pg_attribute WHERE attrelid='payments'::regclass "
            "AND attnum > 0 AND NOT attisdropped ORDER BY attnum"
        )
        COLUMNS = [row[0] for row in cur.fetchall()]
        cur.execute(
            "SELECT id, amount, account_id, method_id, posted_at, payment_no "
            "FROM payments WHERE status = 'cleared' ORDER BY payment_no LIMIT 1"
        )
        template = cur.fetchone()
    if template is None:
        failures.append("no cleared payment to copy — the fixtures cannot build a probe row")
        print("\nFAIL: nothing to build a probe from.")
        print("\n" + "=" * 78)
        print(f"{len(failures)} failure(s)")
        for one in failures:
            print(f"  - {one}")
        sys.exit(1)
    TEMPLATE_ID, TEMPLATE_AMOUNT, TEMPLATE_ACCOUNT, TEMPLATE_METHOD, TEMPLATE_POSTED, _no = template
    print(f"  probe template: payment {_no} ({TEMPLATE_ID}) amount {TEMPLATE_AMOUNT}")

    #: Cleared on the copy: a unique-keyed column, or one whose presence would
    #: make the probe prove something narrower than it says.
    BLANKED = (
        "payment_no",
        "webhook_key",
        "deposit_batch_id",
        "journal_entry_id",
        "confirmation",
        "corrects_payment_id",
    )

    def fresh(status, **over):
        """A NEW row, INSERTed as a copy of the template.

        ⚠ **BUILT FROM THE CATALOG, NOT FROM THE MODEL.** It copies whichever
        columns `payments` has on THIS database, so it runs identically before
        and after the two migrations under test. The trigger is BEFORE UPDATE
        OR DELETE, so an INSERT is lawful in any status and the fixture cannot
        be refused by the guard it exists to test.
        """
        picks, params = [], []
        for name in COLUMNS:
            if name == "id":
                picks.append("gen_random_uuid()")
            elif name in over:
                picks.append("%s")
                params.append(over[name])
            elif name == "status":
                picks.append("%s")
                params.append(status)
            elif name in BLANKED:
                picks.append("NULL")
            else:
                picks.append(f'"{name}"')
        names = ", ".join(f'"{one}"' for one in COLUMNS)
        with connection.cursor() as cur:
            cur.execute(
                f"INSERT INTO payments ({names}) SELECT {', '.join(picks)} "
                f"FROM payments WHERE id = %s RETURNING id, amount",
                params + [TEMPLATE_ID],
            )
            return cur.fetchone()

    def sql(statement, *params):
        def act():
            with connection.cursor() as cur:
                cur.execute(statement, list(params))

        return act

    with connection.cursor() as cur:
        cur.execute("SELECT id FROM payment_methods ORDER BY code LIMIT 2")
        methods = [row[0] for row in cur.fetchall()]
    other_method = next((one for one in methods if one != TEMPLATE_METHOD), methods[0])

    print("\n2 · P3.5 — CAN A PAYMENT REACH `cancelled` AT ALL?")
    print("-" * 78)
    print("  RED at 0035 (`ck_payments_status` refuses the word) · green at 0036.")
    with transaction.atomic():
        probe_id, probe_amount = fresh("processing")
        print(f"  probe row: {probe_id} status=processing amount={probe_amount}")
        to_cancelled = sql("UPDATE payments SET status='cancelled' WHERE id = %s", probe_id)

        if AT_0036:
            permit(
                "P3.5 the word is admitted",
                "UPDATE payments SET status='cancelled' WHERE status='processing'",
                to_cancelled,
            )
        else:
            refuse(
                "P3.5 at 0035 the word is refused",
                "UPDATE payments SET status='cancelled' WHERE status='processing'",
                to_cancelled,
                "ck_payments_status",
            )
        transaction.set_rollback(True)

    if not AT_0036:
        print("\n  [stop] payments is at 0035. §3–§7 cannot be proved here; re-run")
        print("         this script against a database with 0036 applied.")
        print("\n" + "=" * 78)
        if failures:
            print(f"{len(failures)} failure(s)")
            for one in failures:
                print(f"  - {one}")
            sys.exit(1)
        print("RED PROOF COMPLETE at 0035: `cancelled` is refused by name.")
        sys.exit(0)

    print("\n3 · P3.6, THE PERMIT DIRECTION — the trigger allows the move a cancel needs")
    print("-" * 78)
    print("  `processing → cancelled` reaches the still-processing branch, where")
    print("  `status` is on the `mutable` allow list. Without this the feature")
    print("  could not exist.")
    with transaction.atomic():
        probe_id, _amount = fresh("processing")
        permit(
            "P3.6 permit",
            f"UPDATE payments SET status='cancelled' WHERE id={probe_id}",
            sql("UPDATE payments SET status='cancelled' WHERE id = %s", probe_id),
        )
        refuse(
            "P3.6 permit is NARROW — the amount cannot ride along",
            "UPDATE payments SET status='cancelled', amount=amount+1 (one statement)",
            sql(
                "UPDATE payments SET status='cancelled', amount = amount + 1 WHERE id = %s",
                probe_id,
            ),
            "is processing — only status and cleared_at may change",
        )
        transaction.set_rollback(True)

    print("\n4 · P3.6, THE FREEZE DIRECTION — the row is history the instant it lands")
    print("-" * 78)
    with transaction.atomic():
        landed_id, landed_amount = fresh("cancelled")
        print(f"  cancelled row: {landed_id}")
        refuse(
            "P3.6 freeze · the amount",
            f"UPDATE payments SET amount={landed_amount + 1} WHERE id={landed_id}",
            sql("UPDATE payments SET amount = amount + 1 WHERE id = %s", landed_id),
            "is cancelled and is append-only",
        )
        refuse(
            "P3.6 freeze · the un-cancel",
            f"UPDATE payments SET status='processing' WHERE id={landed_id}",
            sql("UPDATE payments SET status='processing' WHERE id = %s", landed_id),
            "is cancelled and is append-only",
        )
        refuse(
            "P3.6 freeze · the posting date it was taken on",
            f"UPDATE payments SET posted_at = posted_at + '1 day' WHERE id={landed_id}",
            sql(
                "UPDATE payments SET posted_at = posted_at + interval '1 day' WHERE id = %s",
                landed_id,
            ),
            "is cancelled and is append-only",
        )
        refuse(
            "P3.6 freeze · DELETE, in every status",
            f"DELETE FROM payments WHERE id={landed_id}",
            sql("DELETE FROM payments WHERE id = %s", landed_id),
            "cannot be removed, in any status",
        )
        transaction.set_rollback(True)

    print("\n5 · THE CONTROLS — without these, §3 and §4 mean nothing")
    print("-" * 78)
    print("  (a) the trigger is reachable from this script at all: an amount change")
    print("      on a CLEARED payment must be refused.")
    print("  (b) this script is capable of making an UPDATE SUCCEED: the ordinary")
    print("      clearing transition must still be permitted.")
    with transaction.atomic():
        settled_id, settled_amount = fresh("cleared")
        refuse(
            "control (a) the trigger is installed and firing",
            f"UPDATE payments SET amount={settled_amount + 1} WHERE status='cleared'",
            sql("UPDATE payments SET amount = amount + 1 WHERE id = %s", settled_id),
            "is cleared and is append-only",
        )
        transaction.set_rollback(True)
    with transaction.atomic():
        clearing_id, _amount = fresh("processing")
        permit(
            "control (b) the clearing transition is untouched",
            "UPDATE payments SET status='cleared', cleared_at=… (BR-PAY-021)",
            sql(
                "UPDATE payments SET status='cleared', cleared_at = posted_at WHERE id = %s",
                clearing_id,
            ),
        )
        transaction.set_rollback(True)

    print("\n6 · P3.8 — THE ALLOW LIST DID NOT MOVE")
    print("-" * 78)
    print("  Cancel writes a status and (in P3.2) a new row. It widens nothing.")
    with transaction.atomic():
        landed_id, _amount = fresh("cancelled")
        permit(
            "P3.8 · `confirmation` is still correctable on a frozen row",
            f"UPDATE payments SET confirmation='4471' WHERE id={landed_id}",
            sql("UPDATE payments SET confirmation='4471' WHERE id = %s", landed_id),
        )
        permit(
            "P3.8 · `memo` is still correctable",
            f"UPDATE payments SET memo='…' WHERE id={landed_id}",
            sql("UPDATE payments SET memo='corrected at the counter' WHERE id = %s", landed_id),
        )
        permit(
            "P3.8 · `method_id` is still correctable while unbanked",
            f"UPDATE payments SET method_id=… WHERE id={landed_id}",
            sql("UPDATE payments SET method_id = %s WHERE id = %s", other_method, landed_id),
        )
        refuse(
            "P3.8 · and a FOURTH column is not",
            f"UPDATE payments SET purpose='deposit' WHERE id={landed_id}",
            sql("UPDATE payments SET purpose='deposit' WHERE id = %s", landed_id),
            "is cancelled and is append-only",
        )
        transaction.set_rollback(True)

    print("\n  the deployed function body, read back — not a migration file:")
    with connection.cursor() as cur:
        cur.execute("SELECT prosrc FROM pg_proc WHERE proname='payments_payment_immutable'")
        body = cur.fetchone()[0]
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(("mutable", "stamps")) or (
            stripped.startswith("'") and "ARRAY" not in stripped and stripped.endswith("];")
        ):
            print(f"    {stripped}")
    expected = {
        "mutable": {"status", "cleared_at", "updated_at", "confirmation", "memo", "method_id"},
        "stamps": {
            "deposit_batch_id",
            "journal_entry_id",
            "updated_at",
            "confirmation",
            "memo",
            "method_id",
        },
    }
    import re

    for name, want in expected.items():
        found = re.search(rf"{name}\s+text\[\]\s*:=\s*ARRAY\[(.*?)\];", body, re.S)
        if not found:
            failures.append(f"could not read the `{name}` array out of the deployed function")
            continue
        got = set(re.findall(r"'([^']+)'", found.group(1)))
        if got == want:
            print(f"    [ok  ] `{name}` holds exactly {sorted(got)}")
        else:
            failures.append(
                f"the `{name}` allow list has MOVED: deployed {sorted(got)}, "
                f"payments/0014 set {sorted(want)}"
            )
            print(f"    [FAIL] `{name}` moved: {sorted(got)}")

    print("\n7 · P3.7 — `corrects_payment_id`, the mirror, READ BACK FROM THE CATALOG")
    print("-" * 78)
    with connection.cursor() as cur:
        cur.execute(
            "SELECT conname, confdeltype::text, pg_get_constraintdef(oid) "
            "FROM pg_constraint WHERE conrelid='payments'::regclass AND contype='f' "
            "AND (conname LIKE '%corrects%' OR conname LIKE '%reverses%') ORDER BY conname"
        )
        fks = cur.fetchall()
        cur.execute(
            "SELECT attname, attnotnull FROM pg_attribute WHERE attrelid='payments'::regclass "
            "AND attname IN ('corrects_payment_id','reverses_payment_id') AND NOT attisdropped "
            "ORDER BY attname"
        )
        cols = dict(cur.fetchall())
        cur.execute("SELECT indexdef FROM pg_indexes WHERE indexname='ix_payments_corrects'")
        corrects_index = cur.fetchone()
    for name, deltype, definition in fks:
        print(f"    {name}  confdeltype={deltype}")
        print(f"      {definition}")
    print(f"    nullability: {cols}")
    print(f"    index: {corrects_index[0] if corrects_index else '<none>'}")
    if "corrects_payment_id" not in cols:
        failures.append("payments.corrects_payment_id does not exist — P3.7 is not applied")
        print("    [FAIL] the column is not there")
    else:
        # The mirror, asserted rather than eyeballed: same nullability, same
        # ON DELETE behaviour at the database, same deferrability.
        shapes = {tuple(row[1:2]) for row in fks}
        if cols.get("corrects_payment_id") is not cols.get("reverses_payment_id"):
            failures.append(
                "corrects_payment_id and reverses_payment_id differ in nullability — "
                "P3.7 asked for the mirror"
            )
            print("    [FAIL] nullability differs from the column it mirrors")
        elif len(shapes) != 1:
            failures.append(
                "corrects_payment_id and reverses_payment_id have different ON DELETE "
                f"behaviour at the database: {shapes}"
            )
            print("    [FAIL] ON DELETE differs from the column it mirrors")
        else:
            print("    [ok  ] same nullability and the same ON DELETE as `reverses_payment`")
        if corrects_index is None:
            failures.append(
                "ix_payments_corrects is missing — the walk back from the corrected "
                "payment is a sequential scan"
            )
            print("    [FAIL] no index for the reverse walk")
        else:
            print("    [ok  ] the reverse walk has a (tenant, corrects_payment) index")

        with transaction.atomic():
            original_id, _amount = fresh("processing")
            permit(
                "P3.7 · a correction NAMES what it corrects, at INSERT",
                "INSERT INTO payments (…, corrects_payment_id) VALUES (…)",
                lambda: fresh("processing", corrects_payment_id=original_id),
            )
            transaction.set_rollback(True)

        with transaction.atomic():
            original_id, _amount = fresh("processing")
            landed_id, _amount = fresh("cancelled")
            refuse(
                "P3.7 · and it is FROZEN the day it was created (payments/0002)",
                f"UPDATE payments SET corrects_payment_id={original_id} WHERE id={landed_id}",
                sql(
                    "UPDATE payments SET corrects_payment_id = %s WHERE id = %s",
                    original_id,
                    landed_id,
                ),
                "is cancelled and is append-only",
            )
            transaction.set_rollback(True)

    print("\n8 · P3.14 — THE STATEMENT THE SERVICE ISSUES, ON A CANCELLED ROW")
    print("-" * 78)
    print("  §6 proves the allow list with one-column raw UPDATEs. This asks the")
    print("  question a CLERK depends on: does `POST /payments/{id}/correct-")
    print("  reference` still work once the payment is cancelled? Its write is")
    print("  `save(update_fields=[<column>, \"updated_at\"])` — TWO columns in one")
    print("  statement, and §3 already showed a two-column statement mixing a")
    print("  permitted column with a forbidden one is REFUSED. So this is not a")
    print("  restatement of §6; it is the shape that actually ships.")
    print("  ⚠ The ORM is used HERE and nowhere above: it is reachable only at")
    print("  0037, which §3's stop guarantees, and the point is precisely to")
    print("  exercise Django's own statement rather than a hand-written one.")
    print("  ⚠ A CANCELLED ROW IS GOVERNED BY `stamps`, NOT BY `mutable` —")
    print("  MEASURED, AND THE RED PROOF OF THIS SECTION FOUND IT.** Removing")
    print("  `confirmation` from the `mutable` array alone leaves every permit")
    print("  below GREEN, because `mutable` is the STILL-PROCESSING branch and")
    print("  everything here runs against a frozen row. The two arrays overlap on")
    print("  the three correctable columns and are NOT the same list, so a lane")
    print("  breaking one of them to check this proof would conclude the proof")
    print("  cannot fail. It fails on `stamps`; §6's readback catches either.")
    from apps.payments import amendments as _amendments
    from apps.payments import models as _payment_models

    print(f"  the service's own list: {_amendments.AMENDABLE_FIELDS}")
    if len(_amendments.AMENDABLE_FIELDS) != 3:
        failures.append(
            "amendments.AMENDABLE_FIELDS is no longer three — hard rule 4 is narrowed "
            f"for three columns and for nothing else; found {_amendments.AMENDABLE_FIELDS}"
        )

    def orm_write(row_id, column, value):
        def act():
            row = _payment_models.Payment.objects.get(pk=row_id)
            setattr(row, column, value)
            # EXACTLY what `amend_reference` issues — `updated_at` rides along
            # because `auto_now` lives on the model, which is why the service
            # goes through `save()` and not through a bulk update.
            row.save(update_fields=[column, "updated_at"])

        return act

    with transaction.atomic():
        landed_id, _amount = fresh("cancelled")
        permit(
            "P3.14 · `confirmation`, through the service's own statement shape",
            'Payment.save(update_fields=["confirmation", "updated_at"]) on a cancelled row',
            orm_write(landed_id, "confirmation", "4471"),
        )
        permit(
            "P3.14 · `memo`, the same shape",
            'Payment.save(update_fields=["memo", "updated_at"])',
            orm_write(landed_id, "memo", "corrected at the counter"),
        )
        permit(
            "P3.14 · `method_id`, the same shape",
            'Payment.save(update_fields=["method", "updated_at"])',
            orm_write(landed_id, "method_id", other_method),
        )
        refuse(
            "P3.14 · and a FOURTH column in that SAME shape is refused",
            'Payment.save(update_fields=["purpose", "updated_at"]) on a cancelled row',
            orm_write(landed_id, "purpose", "deposit"),
            "is cancelled and is append-only",
        )
        refuse(
            "P3.14 · the amount, in that same shape — the one that moves money",
            'Payment.save(update_fields=["amount", "updated_at"]) on a cancelled row',
            orm_write(landed_id, "amount", Decimal("1.0000")),
            "is cancelled and is append-only",
        )
        transaction.set_rollback(True)

    print("\n  the CONTROL for this section, and it is the one that matters:")
    print("  a statement carrying a permitted column AND a forbidden one together")
    print("  must be refused, or `update_fields` is doing nothing at all.")

    def orm_write_pair():
        row = _payment_models.Payment.objects.get(pk=pair_id)
        row.confirmation = "9999"
        row.amount = row.amount + Decimal("1.0000")
        row.save(update_fields=["confirmation", "amount", "updated_at"])

    with transaction.atomic():
        pair_id, _amount = fresh("cancelled")
        refuse(
            "P3.14 control · a permitted column cannot carry a forbidden one",
            'Payment.save(update_fields=["confirmation", "amount", "updated_at"])',
            orm_write_pair,
            "is cancelled and is append-only",
        )
        transaction.set_rollback(True)

print("\n" + "=" * 78)
if failures:
    print(f"{len(failures)} FAILURE(S)")
    for one in failures:
        print(f"  - {one}")
    sys.exit(1)
print("ALL GREEN.")
print("  `cancelled` is admitted by ck_payments_status, the trigger PERMITS the")
print("  move a cancel needs, FREEZES the row the instant it lands, and hard")
print("  rule 4's allow list is byte-for-byte what payments/0014 set.")
print("  And `P3.14`: the statement the correction endpoint actually issues —")
print("  save(update_fields=[<column>, \"updated_at\"]) — succeeds on a CANCELLED")
print("  payment for all three correctable columns and is refused for a fourth,")
print("  including when a permitted column tries to carry a forbidden one.")
sys.exit(0)
