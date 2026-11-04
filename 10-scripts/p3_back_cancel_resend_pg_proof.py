# ── Trace ──────────────────────────────────────────────
# Change:   CR-137-BRC07 · P3.2 (cancel) · P3.3 (resend)
# Story:    US-PAY-004 · US-PAY-025 · US-NOT-011 §5
# Rules:    CLAUDE.md hard rule 4 (financial immutability) · hard rule 6
#           (idempotency) · hard-won law 14 (prove it on PostgreSQL) ·
#           hard-won law 7 (prove the guard RED first) · BR-PAY-002 · BR-PAY-024
# Tests:    06-backend/tests/test_cr137_p3_detail_cancel_receipt.py — 25 cases,
#           all of them on SQLite, which is why this file exists
# ───────────────────────────────────────────────────────
"""`CR-137-BRC07` `P3.2`/`P3.3` — the transaction-shaped claims, PROVED ON POSTGRESQL.

CLAUDE.md hard-won law 14: *"any code that catches a database error and
continues MUST be proved on PostgreSQL, not on the default suite."*
`apps/payments/receipt_resend.py` catches one and carries on, per channel, and
`apps/payments/cancel.py` moves a status on a table carrying
`trg_payment_immutable`. **SQLite has neither an aborted-transaction state nor
that trigger**, so the 25 green cases in
`tests/test_cr137_p3_detail_cancel_receipt.py` say nothing about either. This
file is what says something about them.

RUN — against a CLONE of a real database at `payments/0037`, never a shared one:

    createdb -T <a migrated template> sbh_clone_p3back
    cd 06-backend
    DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p3back?sslmode=disable \
    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
      python3 ../10-scripts/p3_back_cancel_resend_pg_proof.py

It WRITES (a payment, a cancel, two queue rows), so give it a clone of its own.
`SBH_PROOF_TENANT` picks the tenant; it defaults to the sample utility's.

OBSERVED 2026-09-23, on PostgreSQL 16, role `smartbillhub`
**`rolsuper=False rolbypassrls=False`** — which matters: a superuser bypasses
RLS and every figure taken under one is vacuous (`config/settings/local.py`
says so at length). These were not.

  §2  `processing → cancelled` passes the trigger IN THE SERVICE'S OWN
      STATEMENT — `save(update_fields=["status", "updated_at"])`, not
      hand-written SQL. `P3-DB` proved the trigger permits the move; this proves
      the code that has to make it does.
  §3  the same row, one statement later, is append-only: the amount is refused
      BY THE DATABASE, quoting BR-PAY-002 back in a sentence a clerk could read.
  §4  the reversing row is real money — `-158.1000` under its own `PMT-` number
      — and the pair nets to `0.000000`, which is the whole reason cancel writes
      a row instead of only moving a status.
  §5  a repeated copy number is a REPLAY: `created: False`, no second row, and
      the other channel in the same call still gets its copy.
  §6  the savepoint, RED first: **without** the per-channel `atomic()` the same
      call dies on *"current transaction is aborted, commands ignored until end
      of transaction block"* — law 14's own symptom, verbatim — and **with** it
      the good channel's row survives.

TWO FINDINGS, BOTH WORTH MORE THAN THE GREEN
  1. **The ordinary double-click never reaches the savepoint at all.** §5 was
     written expecting a `UniqueViolation` on
     `(tenant, source_type, source_id, channel, copy_no)`; there is none.
     `notifications.services.queue_document` finds its own row and answers
     `created: False`, so hard rule 6 is satisfied one layer ABOVE the
     constraint. A reader of `resend_receipt`'s savepoint comment would
     reasonably assume the collision path is what exercises the guard. It is
     not — which is why §6 exercises it deliberately, with a writer that poisons
     the transaction the way a real `IntegrityError` does.
  2. **There is no `ATOMIC_REQUESTS` in any settings module and the view does
     not wrap**, so TODAY each channel's `atomic()` IS the transaction and a
     failure could not poison a caller that does not exist. The guard is what
     keeps the behaviour correct for the FIRST caller who wraps this call — a
     bulk action, a job, a future `ATOMIC_REQUESTS` — and §6 runs under exactly
     that outer `atomic()`, which is the only shape where the question has an
     answer."""

import os
import sys
from pathlib import Path
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import django

# Runnable from the repo root: `config` lives under 06-backend, and a script's
# own directory is what lands on sys.path, never the cwd.
_BACKEND = Path(__file__).resolve().parents[1] / "06-backend"
if _BACKEND.is_dir() and str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.db import connection, transaction  # noqa: E402

from apps.payments import cancel, models, receipt_resend, selectors, services  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


print(f"vendor: {connection.vendor}")
if connection.vendor != "postgresql":
    # Fail closed (hard-won law 3). A green run on SQLite would prove nothing
    # this script exists to prove — law 7's "incapable of failing" shape.
    sys.exit("REFUSED: this proof is meaningless on SQLite. Set DATABASE_URL.")

print("\n§1 · THE ROLE (a figure taken under a bypassing role is not an RLS claim)")
with connection.cursor() as cur:
    cur.execute("select current_user, rolsuper, rolbypassrls from pg_roles where rolname = current_user")
    who, is_super, bypasses = cur.fetchone()
print(f"  current_user={who} rolsuper={is_super} rolbypassrls={bypasses}")
print("  → constraints and TRIGGERS fire for every role, including this one. That is what §2–§5 test.")

TENANT = uuid.UUID(os.environ.get("SBH_PROOF_TENANT", "01a0cadb-b43d-7251-9796-8bddb3ba440f"))
NOW = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)

with core_tenancy.tenant_context(TENANT):
    from apps.identity import models as identity_models

    actor = identity_models.User.objects.filter(tenant_id=TENANT).order_by("created_at").first()
    account_id = (
        models.Payment.objects.filter(tenant_id=TENANT).values_list("account_id", flat=True).first()
    )
    print(f"\n  actor={actor.email}  account={account_id}")

    # ── §2 · THE PERMIT ────────────────────────────────────────────────────
    print("\n§2 · CANCEL, THE SERVICE'S OWN UPDATE, THROUGH trg_payment_immutable")
    recorded = services.record_payment(
        actor,
        account_id=account_id,
        amount=Decimal("158.1000"),
        posted_at=NOW,
        cleared_at=None,
        method_code="check",
        confirmation="PROOF-0001",
    )
    original = models.Payment.objects.get(pk=recorded.payment_id)
    check("a processing payment exists", original.status == "processing", original.status)

    result = cancel.cancel_payment(
        actor=actor,
        payment_id=original.pk,
        reason="wrong_amount",
        cancelled_on=NOW,
        note="proved on postgresql",
    )
    original.refresh_from_db()
    check(
        "processing → cancelled passed the trigger",
        original.status == cancel.CANCELLED,
        f"status={original.status}",
    )

    # ── §3 · THE FREEZE ────────────────────────────────────────────────────
    print("\n§3 · THE SAME ROW, ONE STATEMENT LATER, IS APPEND-ONLY")
    refused = ""
    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(
                    "update payments set amount = amount + 1 where id = %s", [str(original.pk)]
                )
    except Exception as exc:  # noqa: BLE001 — the refusal IS the result
        refused = str(exc).splitlines()[0]
    check("the amount of a cancelled payment is refused BY THE DATABASE", bool(refused), refused)

    # ── §4 · THE MONEY ─────────────────────────────────────────────────────
    print("\n§4 · THE REVERSING ROW IS REAL MONEY, AND THE DAY NETS TO ZERO")
    reversal = models.Payment.objects.get(pk=result.reversing_payment_id)
    check(
        "a negative row with its own number",
        reversal.amount == Decimal("-158.1000") and reversal.payment_no != original.payment_no,
        f"{reversal.payment_no} {reversal.amount}",
    )
    pair = models.Payment.objects.filter(pk__in=[original.pk, reversal.pk])
    net = sum((one.amount for one in pair), Decimal("0"))
    check("the pair nets to zero in the takings", net == Decimal("0"), f"net={net}")

    # ── §5 · THE SAVEPOINT — LAW 14's OWN CASE ─────────────────────────────
    print("\n§5 · A REPEATED COPY NUMBER IS A REPLAY (hard rule 6), NOT A SECOND ROW")
    with_receipts = None
    for candidate in models.Payment.objects.filter(tenant_id=TENANT).order_by("-created_at")[:200]:
        got = {d["channel"] for d in receipt_resend.receipt_deliveries(candidate)}
        if {"pdf_print", "email"} <= got:
            with_receipts = candidate
            break
    if with_receipts is None:
        check("a payment with a pdf_print AND an email receipt", False, "none in this database")
    else:
        copy_no = receipt_resend.next_copy_no(receipt_resend.receipt_deliveries(with_receipts))
        # Burn the pdf_print copy number first, so the second call asks for a
        # number that channel has already used — the clerk's double-click.
        receipt_resend.resend_receipt(
            actor=actor, payment=with_receipts, channels=("pdf_print",), copy_no=copy_no
        )
        before = len(receipt_resend.receipt_deliveries(with_receipts))
        out = receipt_resend.resend_receipt(
            actor=actor,
            payment=with_receipts,
            channels=("pdf_print", "email"),
            copy_no=copy_no,
        )
        after = receipt_resend.receipt_deliveries(with_receipts)
        emailed = [d for d in after if d["channel"] == "email" and d["copy_no"] == copy_no]
        print("    queued:", out.queued)
        # ⚠ **THE FINDING: THE ORDINARY DOUBLE-CLICK NEVER REACHES A SAVEPOINT.**
        # This section was written expecting a UniqueViolation on
        # (tenant, source, channel, copy_no). There is none — `queue_document`
        # finds its own row and answers `created: False`. That is hard rule 6
        # satisfied one layer ABOVE the constraint, and it is worth writing down,
        # because a reader of `resend_receipt`'s savepoint comment would
        # reasonably assume the collision path is what exercises it. §6 exercises
        # it on purpose instead.
        replayed = [q for q in out.queued if q["channel"] == "pdf_print"]
        check(
            "the second copy on the same channel is a REPLAY, not a second row",
            len(replayed) == 1 and replayed[0]["created"] is False,
            str(replayed),
        )
        check(
            "the other channel still got its own copy in the same call",
            len(emailed) == 1 and len(after) == before + 1,
            f"before={before} after={len(after)} email copies={len(emailed)}",
        )
        check("the connection is still usable afterwards", connection.is_usable())

    # ── §6 · THE SAVEPOINT, RED AND GREEN, ON THE DATABASE THAT HAS ONE ────
    #
    # §5 showed the ORDINARY collision never reaches the savepoint at all:
    # `queue_document` is idempotent on (source, channel, copy_no) and answers
    # `created: False`. So the guard is exercised here on purpose, with a writer
    # that poisons the transaction the way a real IntegrityError does — and with
    # an OUTER `atomic()` around the whole call, because that is the shape law 14
    # is about. (There is no ATOMIC_REQUESTS in any settings module and the view
    # does not wrap, so TODAY each channel's atomic() IS the transaction; the
    # guard is what keeps that true for the first caller who wraps it.)
    import contextlib

    from apps.notifications import services as notification_services

    real_write = notification_services.queue_document

    def poisoning_write(**kwargs):
        channel = (kwargs.get("channels") or ("?",))[0]
        if channel == "pdf_print":
            with connection.cursor() as cur:
                # a REAL database error, not a Python one: this is what aborts a
                # PostgreSQL transaction and what SQLite simply does not do.
                cur.execute("insert into payments (id) values (null)")
        return real_write(**kwargs)

    def run(with_savepoint: bool) -> str:
        copy = receipt_resend.next_copy_no(receipt_resend.receipt_deliveries(with_receipts))
        notification_services.queue_document = poisoning_write
        saved = receipt_resend.transaction
        if not with_savepoint:
            class _NoSavepoint:
                atomic = staticmethod(contextlib.nullcontext)
            receipt_resend.transaction = _NoSavepoint
        outcome = ""
        try:
            with transaction.atomic():
                receipt_resend.resend_receipt(
                    actor=actor,
                    payment=with_receipts,
                    channels=("pdf_print", "email"),
                    copy_no=copy,
                )
            landed = [
                d
                for d in receipt_resend.receipt_deliveries(with_receipts)
                if d["channel"] == "email" and d["copy_no"] == copy
            ]
            outcome = "the email copy survived" if landed else "THE EMAIL COPY WAS LOST"
        except Exception as exc:  # noqa: BLE001 — the raise IS the result
            outcome = f"{type(exc).__name__}: {str(exc).splitlines()[0][:110]}"
        finally:
            notification_services.queue_document = real_write
            receipt_resend.transaction = saved
        return outcome

    print("\n§6 · THE SAVEPOINT, PROVED RED FIRST (hard-won law 7 + law 14)")
    red = run(with_savepoint=False)
    print(f"    WITHOUT the per-channel atomic(): {red}")
    green = run(with_savepoint=True)
    print(f"    WITH    the per-channel atomic(): {green}")
    check(
        "removing the savepoint breaks it (the RED half)",
        "survived" not in red,
        red,
    )
    check("the savepoint keeps the good channel (the GREEN half)", "survived" in green, green)

print("\n" + ("ALL GREEN" if not FAILURES else f"{len(FAILURES)} FAILED: {FAILURES}"))
sys.exit(1 if FAILURES else 0)
