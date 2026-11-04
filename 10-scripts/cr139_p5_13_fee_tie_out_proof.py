#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-139-BRC07 — the payments blueprint's phase 5, task `P5.13`
#          *"the fee tie-out — the balanced pair, with the gross intact. hard
#          rule 5"*.
# Rules:   CLAUDE.md hard rule 4 (financial immutability — a posted journal
#          line and a cleared payment's money are frozen) · hard rule 5 (only
#          the ledger posting service writes journal lines) · hard-won law 14
#          (the suite runs on in-memory SQLite, which has neither the triggers
#          nor the CHECK constraints below) · hard-won law 7 (every probe here
#          carries a CONTROL, because a refusal with no control proves only
#          that something refused)
# Tests:   the arithmetic half is
#          06-backend/tests/test_cr139_p5_12_to_p5_15.py. THIS is the half that
#          suite structurally cannot run.
# ───────────────────────────────────────────────────────
"""**THE FEE TIE-OUT, PROVED WHERE ITS GUARANTEES ACTUALLY EXIST.**

`P5.13`'s sentence has two halves and the suite can only reach one of them.

**The half the suite reaches** — `stated_processor_fee()` → `reconcile_batch`
posts `DR 1000 4,972.90 · DR 6800 147.50 · CR 1010 5,120.40`, it balances, and
the payments' own amounts still add to the gross. That is arithmetic and
`tests/test_cr139_p5_12_to_p5_15.py` asserts it on every machine.

**The half it cannot reach**, because `config/settings/test.py` hardcodes
in-memory SQLite and ignores `DATABASE_URL`:

  1. **HARD RULE 5 IS A TRIGGER.** An INSERT into `journal_entries` that did
     not come through `apps/ledger/posting.py::post()` is refused BY NAME,
     quoting `BR-LED-007`. So *only the ledger posting service writes journal
     lines* is something the database enforces, not something the code merely
     agrees to — a settlement that composed its own balanced pair could not
     write it. **On SQLite that INSERT is ordinary.**
  2. **A POSTED ENTRY IS FROZEN** (hard rule 4). The append-only trigger is
     installed by a `RunPython` that returns early on any non-PostgreSQL
     vendor, so on the suite a later "correction" of a posted line is a
     perfectly ordinary UPDATE.
  3. **THE GROSS CANNOT BE NETTED DOWN EVEN BY A BUG.** `payments/0005`'s
     trigger freezes `payments.amount` in every status. This is the database
     saying what CR-139 §2.3 says in prose: *a $100.00 card payment with a
     $2.90 fee is a $100.00 payment and a $2.90 expense, never a $97.10
     payment.*

⚠ **`ck_journal_lines_amount_ge0` IS STATED AND NOT PROBED, AND THE REASON IS
WORTH READING.** B2 puts `CHECK (amount >= 0)` on `journal_lines` so that a
line's sign lives in `side`, and this file set out to provoke it. **It cannot
be reached**: point 1's trigger refuses the hand-written entry first, and the
posting service refuses a negative amount before that. A probe that cannot
reach its subject is not a weak probe, it is no probe — so part A asserts the
constraint's PRESENCE and proves the guard that actually stands in front of it.

⚠ **EVERY REFUSAL PROBE CARRIES A CONTROL, AND WITHOUT ONE IT PROVES NOTHING.**
A table nobody may write at all refuses identically to a table with a
discriminating trigger. So each refusal is paired with a write that must
SUCCEED on the same row or the same table — `cr139_p5_6_pointer_freeze_proof.py`
made the same argument for `settlement_id` and its third probe is why the first
two mean anything.

⚠ **AND EVERY PROBE RUNS INSIDE ITS OWN SAVEPOINT, WHICH IS THIS PHASE'S OWN
NAMED RISK TURNED ON THE PROOF ITSELF** (hard-won law 14). A provoked error
aborts the whole PostgreSQL transaction; without a nested `atomic()` the first
refusal below would poison every probe after it and the script would report a
cascade of failures that say nothing.

    10-scripts/proof-db.sh clone p5tests
    export PGPASSWORD=smartbillhub
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
    export DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p5tests?sslmode=disable"
    python3 10-scripts/cr139_p5_13_fee_tie_out_proof.py

Everything runs inside a transaction that is rolled back. No row is kept.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import DatabaseError, connection, transaction  # noqa: E402

from apps.ledger import models as ledger_models  # noqa: E402
from apps.payments import models as payment_models  # noqa: E402
from apps.payments import settlement_models, settlements  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

FAILURES: list[str] = []

#: The PO's card day, and the figures every phase-5 document quotes.
RECORDED = Decimal("5120.40")
BANKED = Decimal("4972.90")
FEE = Decimal("147.50")
PAID_OUT_AT = datetime(2026, 8, 7, 9, 0, tzinfo=UTC)


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


def _guc(tenant_id) -> None:
    """Hard rule 1 — the GUC on THIS connection before anything is read.

    Without it every tenant table below reads ZERO rows and every probe would
    report a truthful, useless pass over an empty scope (hard-won law 7's
    *reporting zero over a scope it silently excludes*). Measured on a fresh
    clone: `select count(*) from ledger_accounts` is **0** with no GUC and
    **129** with it.
    """
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])
    core_tenancy.set_current_tenant(tenant_id)


def _tenant():
    row = tenancy_models.Tenant.objects.order_by("created_at").first()
    if row is None:
        raise SystemExit("no tenant in this database — clone a seeded template")
    return row


def _gl(tenant, designation: str):
    row = ledger_models.LedgerAccount.objects.filter(tenant=tenant, designation=designation).first()
    if row is None:
        raise SystemExit(
            f"this tenant's chart has no account designated {designation!r}. The fee account "
            "is resolved by DESIGNATION and never by number (reconciliation refuses a GL that "
            "is not on the tenant's own live chart), so the probe cannot be run without it."
        )
    return row


# ═══════════════════════════════════════════════════════════════════════════
#  PART A — the SHAPE of the balanced pair is a DATABASE fact, not a habit
# ═══════════════════════════════════════════════════════════════════════════
def part_a(tenant) -> None:
    """**HARD RULE 5 IS A DATABASE GUARANTEE HERE, NOT A CODE CONVENTION.**

    `P5.13`'s task row ends *"hard rule 5"* — *only the ledger posting service
    writes journal lines* — and on PostgreSQL that sentence is enforced by a
    trigger: an INSERT into `journal_entries` that did not come through
    `apps/ledger/posting.py::post()` is refused BY NAME, quoting `BR-LED-007`.
    So a settlement that composed its own balanced pair could not write it even
    if somebody made it try. **On SQLite that trigger is not installed and the
    INSERT is ordinary**, which is the whole reason this file exists.

    ⚠ **THIS PART WAS WRITTEN TWICE AND THE FIRST TWO DRAFTS BOTH PASSED OR
    FAILED FOR THE WRONG REASON — the controls are what found both.**
      * **Draft 1** probed `ck_journal_lines_amount_ge0` by inserting a
        negative line into a POSTED entry. It was refused, and the probe went
        green — but the refusal said *"its lines are frozen (attempted
        insert)"*, which is hard rule 4 answering a question about hard rule
        2's arithmetic. **The CONTROL caught it: the POSITIVE line was refused
        identically**, and a refusal both ways proves nothing about the
        constraint under test.
      * **Draft 2** moved to a DRAFT entry of its own and was refused again,
        this time as a posting-service bypass — which is the finding above and
        is worth more than the constraint was.
    **The CHECK is therefore unreachable by any path a bug could take**, and
    the honest thing is to say so and assert the guard that actually stands in
    front of it rather than to keep reaching for the one this file set out to
    probe.
    """
    constraint = "ck_journal_lines_amount_ge0"
    with connection.cursor() as cur:
        cur.execute(
            "select count(*) from pg_constraint where conrelid='journal_lines'::regclass "
            "and conname = %s",
            [constraint],
        )
        installed = cur.fetchone()[0] == 1
    check(
        f"A `{constraint}` is installed — a journal line's sign lives in `side`",
        installed,
        "so 'the fee is its own DEBIT line' is a schema fact; it is unreachable by any "
        "path because of the guard below, and it is stated rather than probed",
    )

    # ── THE GUARD ITSELF ────────────────────────────────────────────────────
    refused = False
    detail = "the database ACCEPTED a hand-written journal entry — hard rule 5 is unguarded"
    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(
                    "INSERT INTO journal_entries (id, tenant_id, entry_date, status, type, "
                    "currency, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, 'USD', now(), now())",
                    [
                        uuid.uuid4(),
                        tenant.pk,
                        PAID_OUT_AT.date(),
                        ledger_models.JE_DRAFT,
                        ledger_models.JE_STANDARD,
                    ],
                )
    except DatabaseError as exc:
        refused = "posting service" in str(exc)
        detail = str(exc).splitlines()[0][:200]
    check(
        "A a journal entry NOT written through post() is REFUSED BY NAME (hard rule 5)",
        refused,
        detail,
    )

    # ⚠ **THE CONTROL, AND IT IS THE POINT OF THE WHOLE PART.** Raw SQL must
    # WORK in this session against a table the ledger does not own, or the
    # refusal above is just "this connection cannot write anything" and says
    # nothing about hard rule 5.
    control_ok = False
    control_detail = ""
    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(
                    "INSERT INTO settlements (id, tenant_id, code, provider, paid_out_at, "
                    "gross, fees, net, currency, status, created_at, updated_at) "
                    "VALUES (%s, %s, %s, 'payments_sandbox', %s, %s, %s, %s, 'USD', "
                    "'received', now(), now())",
                    [
                        uuid.uuid4(),
                        tenant.pk,
                        f"po_ctl_{uuid.uuid4().hex[:8]}",
                        PAID_OUT_AT,
                        RECORDED,
                        FEE,
                        BANKED,
                    ],
                )
            control_ok = True
            raise _Rollback
    except _Rollback:
        pass
    except DatabaseError as exc:
        control_detail = str(exc).splitlines()[0][:200]
    check(
        "A CONTROL raw SQL DOES write a table the ledger does not own",
        control_ok,
        control_detail or "so the refusal above is the ledger's guard, not a dead connection",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  PART B — a posted entry is FROZEN (hard rule 4)
# ═══════════════════════════════════════════════════════════════════════════
def part_b(tenant) -> None:
    """*"No UPDATE/DELETE on … journal entries — corrections are new rows."*

    The tie-out's three legs are worth nothing if a later hand can move one of
    them. On PostgreSQL the append-only trigger refuses it; on the suite the
    trigger is not installed at all.
    """
    line = ledger_models.JournalLine.objects.filter(
        tenant=tenant, journal_entry__status=ledger_models.JE_POSTED
    ).first()
    if line is None:
        check("B a posted journal line exists to probe", False, "none in this tenant")
        return

    refused = False
    detail = "the database ACCEPTED an UPDATE of a posted journal line's amount"
    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("UPDATE journal_lines SET amount = amount + 1 WHERE id = %s", [line.pk])
    except DatabaseError as exc:
        refused = True
        detail = str(exc).splitlines()[0]
    check("B a posted journal line cannot be UPDATEd (hard rule 4)", refused, detail)

    refused_delete = False
    detail_delete = "the database ACCEPTED a DELETE of a posted journal line"
    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("DELETE FROM journal_lines WHERE id = %s", [line.pk])
    except DatabaseError as exc:
        refused_delete = True
        detail_delete = str(exc).splitlines()[0]
    check("B a posted journal line cannot be DELETEd", refused_delete, detail_delete)


# ═══════════════════════════════════════════════════════════════════════════
#  PART C — THE GROSS IS INTACT, AND THE DATABASE IS WHAT KEEPS IT SO
# ═══════════════════════════════════════════════════════════════════════════
def part_c(tenant) -> None:
    """`P5.13`'s *with the gross intact*, as a refusal rather than as a habit.

    ⚠ **THIS IS THE PROBE THE WHOLE PHASE'S MONEY ARGUMENT RESTS ON.** CR-139
    §2.3: *a $100.00 card payment with a $2.90 processor fee is a $100.00
    payment and a $2.90 expense — never a $97.10 payment. Netting it down would
    make the customer's account short by $2.90 and the trial balance tie to the
    wrong number.* `payments/0005` freezes `amount` in every status, so a build
    that netted a payment down is refused BY THE DATABASE.

    ⚠ **AND THE CONTROL IS WHAT MAKES IT MEAN SOMETHING.** `payments/0014`
    widened the allow list for exactly three columns (PO ruling 2026-09-02,
    `OQ-1322`): `confirmation`, `memo` and `method_id`. So a `memo` UPDATE on
    the SAME ROW must SUCCEED. Without that control a payments table nobody may
    write at all would pass this part identically.
    """
    payment = (
        payment_models.Payment.objects.filter(tenant=tenant, status=payment_models.PAYMENT_CLEARED)
        .order_by("created_at")
        .first()
    )
    if payment is None:
        check("C a cleared payment exists to probe", False, "none in this tenant")
        return
    before = payment.amount

    refused = False
    detail = f"the database ACCEPTED netting {before} down by the fee"
    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(
                    "UPDATE payments SET amount = amount - %s WHERE id = %s",
                    [Decimal("2.90"), payment.pk],
                )
    except DatabaseError as exc:
        refused = True
        detail = str(exc).splitlines()[0]
    check("C a cleared payment's AMOUNT cannot be netted down (hard rule 4)", refused, detail)

    control_ok = False
    control_detail = ""
    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(
                    "UPDATE payments SET memo = %s WHERE id = %s",
                    [f"p5.13 control {uuid.uuid4().hex[:6]}", payment.pk],
                )
            control_ok = True
            raise _Rollback
    except _Rollback:
        pass
    except DatabaseError as exc:
        control_detail = str(exc).splitlines()[0]
    check(
        "C CONTROL `memo` IS writable on the same row (payments/0014's allow list)",
        control_ok,
        control_detail or "the trigger discriminates; it does not refuse everything",
    )

    payment.refresh_from_db()
    check(
        "C and the amount is unchanged after both probes",
        payment.amount == before,
        f"{before} -> {payment.amount}",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  PART D — the STATED fee reaches the books as a DEBIT of its own
# ═══════════════════════════════════════════════════════════════════════════
def part_d(tenant) -> None:
    """`stated_processor_fee()` on real PostgreSQL, on the PO's own figures.

    The arithmetic is asserted in the suite; what this adds is that the
    resolution is computed **against real `NUMERIC(18,4)` columns** rather than
    against SQLite's decimal shim, and that the refusal half — a chargeback
    hiding inside the gap — is refused there too.

    ⚠ **NOTHING IS POSTED HERE AND THAT IS THE POINT** (hard rule 5). The
    balanced pair is `reconcile_batch` → `ledger_seam.post_batch_reconciled`'s
    to write; `settlements.py` imports no ledger at all and a structural test
    asserts that absence. A settlement that posted cash of its own would post
    the same money twice.
    """
    entries_before = ledger_models.JournalEntry.objects.filter(tenant=tenant).count()
    payout = settlement_models.Settlement(
        tenant=tenant,
        provider="payments_sandbox",
        code=f"po_proof_{uuid.uuid4().hex[:8]}",
        paid_out_at=PAID_OUT_AT,
        gross=RECORDED,
        fees=FEE,
        net=BANKED,
    )
    # An UNSAVED instance: `stated_processor_fee` reads `fees`, `gross` and
    # `code` off it and writes nothing, so the probe needs no row and leaves
    # none. That it works on an unsaved object IS the hard-rule-5 evidence.
    resolution = settlements.stated_processor_fee(
        payout,
        recorded_total=RECORDED,
        bank_total=BANKED,
        gl_account_id=_gl(tenant, "bank_fees").pk,
    )
    check(
        "D the STATED fee becomes a resolution of exactly -147.50",
        resolution.amount == -FEE,
        f"amount={resolution.amount}",
    )
    check(
        "D and it carries the tenant's own `processor_fee` reason",
        resolution.reason_code == "processor_fee",
        f"reason_code={resolution.reason_code!r}",
    )
    check(
        "D and it points at the chart's `bank_fees` account, resolved by DESIGNATION",
        str(resolution.gl_account_id) == str(_gl(tenant, "bank_fees").pk),
    )

    # The refusal half, on the PO's chargeback figures: provider states 137.50,
    # the bank is 147.50 short, 10.00 is a CUSTOMER and not a fee.
    from apps.payments.exceptions import PaymentRuleError

    payout.fees = Decimal("137.50")
    refused = False
    detail = "a 10.00 chargeback reconciled clean — OQ-160's recorded hazard, live"
    try:
        settlements.stated_processor_fee(
            payout,
            recorded_total=RECORDED,
            bank_total=BANKED,
            gl_account_id=_gl(tenant, "bank_fees").pk,
        )
    except PaymentRuleError as exc:
        refused = "10.00 is unexplained" in str(exc)
        detail = str(exc).splitlines()[0][:140]
    check("D a chargeback hiding inside the gap is REFUSED BY NAME", refused, detail)

    entries_after = ledger_models.JournalEntry.objects.filter(tenant=tenant).count()
    check(
        "D and NOT ONE journal entry was written by any of it (hard rule 5)",
        entries_after == entries_before,
        f"{entries_before} -> {entries_after}. `settlements.py` imports no ledger at all; "
        "the balanced pair is reconcile_batch's to write and a second writer posts twice",
    )


class _Rollback(Exception):
    """Unwind a savepoint whose write must NOT be kept. Never escapes a probe."""


def main() -> int:
    if connection.vendor != "postgresql":
        raise SystemExit(
            f"this proof is about PostgreSQL and the connection is {connection.vendor!r}. "
            "config/settings/test.py hardcodes in-memory SQLite and ignores DATABASE_URL, and "
            "SQLite has neither the CHECK constraints nor the triggers every part below "
            "probes — so it would pass all of them by vacuum (CLAUDE.md hard-won law 14). "
            'Set DJANGO_SETTINGS_MODULE=config.settings.local and DATABASE_URL="postgres://…".'
        )
    tenant = _tenant()
    _guc(tenant.pk)
    print(f"tenant {tenant.subdomain} · PostgreSQL {connection.pg_version}")
    try:
        with transaction.atomic():
            part_a(tenant)
            part_b(tenant)
            part_c(tenant)
            part_d(tenant)
            raise _Rollback
    except _Rollback:
        print("  (everything above ran inside one transaction, now rolled back)")
    print("\n" + ("ALL PARTS PASSED" if not FAILURES else f"FAILED: {FAILURES}"))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
