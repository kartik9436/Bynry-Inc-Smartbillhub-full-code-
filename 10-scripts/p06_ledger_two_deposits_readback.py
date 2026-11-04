"""`P0.6` — CAN THE LEDGER ALREADY HOLD **TWO** DEPOSITS FOR ONE DAY?

PO ruling 2026-09-22 (decision log, *"PHASE 0 INCLUDES THE LEDGER CHANGE…"*),
verbatim: *"(a) Payments and ledger together — The re-key, and the ledger
accepting two deposits where it expected one"*.

The worked case it was signed on, and the figure a test must assert:

    Dana's Tuesday session holds  $1,240  of cheques
    Sam's   Tuesday session holds  $  880  of cheques
    ------------------------------------------------
    the day must still tie to     $2,120   exactly

WHAT THIS ANSWERS, AND WHY IT HAD TO BE RUN RATHER THAN READ
------------------------------------------------------------
The blueprint (`05-prototype/06 Payments Page Blueprint.pdf` p11) says a
counter close *"has nowhere valid to write until that constraint is
replaced — phase 0, task 6, **and a ledger change**"*. Reading
`apps/ledger/` suggests the ledger needs no change at all: the posting key is
`deposit_batch|<batch uuid>|reconciled` — per BATCH, not per day — and every
ledger report sums journal lines by `source_type`, which is additive. But a
reading is a claim, and the document's own header says every as-built
statement *"must be re-verified before it is trusted"*. So this RUNS it.

⚠ **IT GOES THROUGH `apps.ledger.posting.post()` AND NOTHING ELSE.** Hard rule
5 — only the ledger posting service writes journal lines — is enforced IN THE
DATABASE by `ledger_sole_writer_guard()` (`ledger/0004`): a hand-written
INSERT into `journal_entries` raises

    CLAUDE.md rule 5: journal_entries is written ONLY by the ledger posting
    service (apps/ledger/posting.py). This INSERT did not come through post()

which is how the first draft of this proof was caught. The guard is right and
the draft was wrong.

⚠ **IT WRITES NOTHING.** Both posts happen inside a `transaction.atomic()`
that is rolled back by raising, so the database is exactly as it was found.
The last section re-reads the day to show it.

⚠ **ON POSTGRESQL, NOT THE SUITE** (hard-won law 14 · `P0.14`): the suite
hardcodes in-memory SQLite, where `ledger_sole_writer_guard`, RLS FORCE and a
partial index do not exist as they will in production.

HOW TO RUN IT
-------------
    10-scripts/proof-db.sh clone p06led
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p06led?sslmode=disable \
      python3 manage.py shell < ../10-scripts/p06_ledger_two_deposits_readback.py

WHAT WOULD MAKE THIS CHECK PASS WRONGLY (law 7, habit 2)
---------------------------------------------------------
  * **A FALSE ZERO FROM RLS.** Every count here is taken with
    `app.tenant_id` SET. Unscoped, `deposit_batches` and `journal_entries`
    answer 0 under RLS FORCE and a reader would call that "clean". Section 0
    prints the unscoped and the scoped count SIDE BY SIDE so the difference
    is visible rather than assumed.
  * **A REPLAY READING AS A SECOND DEPOSIT.** `post()` returns
    `created=False` for a replayed key. If both calls replayed one entry the
    count would still be 2 on a re-run of a dirty database. So the run
    asserts `created is True` on BOTH, and rolls back.
  * **"TWO ENTRIES" WITHOUT "BALANCED".** Two entries could exist and one be
    lopsided. Section 3 checks each pair's debits == credits separately from
    the count.
  * **THE DAY TOTAL TIED BY ACCIDENT.** 1240 + 880 = 2120 is also
    2120 + 0. So section 4 prints the two entries' amounts individually as
    well as the sum.
"""

import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from django.db import connection, transaction

from apps.ledger import chart, models as ledger_models, posting
from core.tenancy import tenant_context

TENANT_SUBDOMAIN = os.environ.get("P06_TENANT", "brazosbend")
DAY = date(2026, 9, 22)
DANA = Decimal("1240.000000")
SAM = Decimal("880.000000")
EXPECTED = Decimal("2120.000000")

failures: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: got {got!r}, want {want!r}")
    if not ok:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def scoped_count(sql: str, params=()) -> int:
    with connection.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()[0]


# ── 0 · the tenant, and the RLS false zero, side by side ───────────────────
from apps.tenancy.models import Tenant  # noqa: E402

with connection.cursor() as cur:
    cur.execute("SELECT set_config('app.tenant_id', '', true)")
unscoped = scoped_count("SELECT count(*) FROM journal_entries")

tenant = Tenant.objects.filter(subdomain=TENANT_SUBDOMAIN).first()
if tenant is None:
    print(f"no tenant {TENANT_SUBDOMAIN!r} in this database — nothing proved")
    sys.exit(1)

print("── 0 · THE RLS FALSE ZERO, SO IT CANNOT BE MISTAKEN FOR A CLEAN DATABASE ──")
with tenant_context(str(tenant.id)):
    scoped = scoped_count("SELECT count(*) FROM journal_entries")
print(f"  journal_entries, app.tenant_id UNSET : {unscoped}")
print(f"  journal_entries, app.tenant_id SET   : {scoped}")
print(f"  tenant: {tenant.subdomain} {tenant.id}")

cash_designation = chart.CASH
undeposited_designation = chart.UNDEPOSITED_FUNDS


def designated(code: str):
    row = ledger_models.LedgerAccount.objects.filter(
        tenant_id=tenant.id, designation=code
    ).first()
    return None if row is None else row.id


print()
print("── 1 · THE TWO GL ACCOUNTS THE DEPOSIT POSTING USES ──")
with tenant_context(str(tenant.id)):
    cash_id = designated(cash_designation)
    undeposited_id = designated(undeposited_designation)
    print(f"  cash              ({cash_designation}): {cash_id}")
    print(f"  undeposited funds ({undeposited_designation}): {undeposited_id}")
    if cash_id is None or undeposited_id is None:
        print("  a designation is unmapped in this database — nothing proved")
        sys.exit(1)

# ── 2 · post TWO deposits for ONE day, through the posting service ─────────
print()
print("── 2 · TWO DEPOSITS, ONE DAY, ONE TENDER, TWO SESSIONS ──")
print("  Each is exactly what apps/payments/ledger_seam.post_batch_reconciled")
print("  composes: DR cash / CR undeposited funds, source_type 'deposit_batch',")
print("  keyed 'deposit_batch|<batch uuid>|reconciled'.")

dana_batch, sam_batch = uuid4(), uuid4()
now = datetime(2026, 9, 22, 17, 30, tzinfo=timezone.utc)


def request_for(batch_id, amount: Decimal, who: str) -> posting.PostingRequest:
    dimensions = {"source_type": "deposit_batch", "source_id": batch_id}
    return posting.PostingRequest(
        posting_key=posting.posting_key(
            source_type="deposit_batch", source_id=batch_id, event="reconciled"
        ),
        entry_date=DAY,
        posted_at=now,
        currency=str(tenant.currency),
        source_type="deposit_batch",
        source_id=batch_id,
        memo=f"{who}'s counter session banked",
        lines=(
            posting.PostingLine(
                ledger_account_id=cash_id, side="debit", amount=amount, **dimensions
            ),
            posting.PostingLine(
                ledger_account_id=undeposited_id, side="credit", amount=amount, **dimensions
            ),
        ),
    )


class RollBack(Exception):
    pass


try:
    with transaction.atomic():
        with tenant_context(str(tenant.id)):
            dana = posting.post(request_for(dana_batch, DANA, "Dana"))
            sam = posting.post(request_for(sam_batch, SAM, "Sam"))

            print(f"  Dana: entry {dana.entry_id}  created={dana.created}  "
                  f"debits={dana.debits} credits={dana.credits}")
            print(f"  Sam : entry {sam.entry_id}  created={sam.created}  "
                  f"debits={sam.debits} credits={sam.credits}")

            check("Dana's deposit was CREATED, not replayed", dana.created, True)
            check("Sam's deposit was CREATED, not replayed", sam.created, True)
            check("the two deposits are two DIFFERENT entries",
                  dana.entry_id != sam.entry_id, True)

            print()
            print("── 3 · HOW MANY DEPOSITS DOES THE LEDGER SEE ON 22 SEPTEMBER? ──")
            on_the_day = ledger_models.JournalEntry.objects.filter(
                tenant_id=tenant.id, entry_date=DAY, source_type="deposit_batch",
                id__in=[dana.entry_id, sam.entry_id],
            ).count()
            check("deposits posted for 2026-09-22", on_the_day, 2)

            print()
            print("── 4 · IS EVERY PAIR BALANCED? (hard rule 5) ──")
            for who, result in (("Dana", dana), ("Sam", sam)):
                lines = ledger_models.JournalLine.objects.filter(
                    tenant_id=tenant.id, journal_entry_id=result.entry_id
                )
                debits = sum(
                    (line.amount for line in lines if line.side == ledger_models.SIDE_DEBIT),
                    Decimal("0"),
                )
                credits = sum(
                    (line.amount for line in lines if line.side == ledger_models.SIDE_CREDIT),
                    Decimal("0"),
                )
                print(f"  {who}: debits {debits}  credits {credits}")
                check(f"{who}'s pair balances", debits, credits)

            print()
            print("── 5 · DOES THE DAY STILL TIE TO $2,120.00? ──")
            day_cash = Decimal("0")
            per_entry = []
            for entry_id in (dana.entry_id, sam.entry_id):
                amount = sum(
                    (
                        line.amount
                        for line in ledger_models.JournalLine.objects.filter(
                            tenant_id=tenant.id,
                            journal_entry_id=entry_id,
                            ledger_account_id=cash_id,
                            side=ledger_models.SIDE_DEBIT,
                        )
                    ),
                    Decimal("0"),
                )
                per_entry.append(amount)
                day_cash += amount
            # printed individually as well as summed: 1240 + 880 = 2120 is also
            # 2120 + 0, and a sum alone cannot tell those apart.
            print(f"  the two deposits, separately: {per_entry[0]} and {per_entry[1]}")
            print(f"  the day's cash debits       : {day_cash}")
            check("Dana's deposit", per_entry[0], DANA)
            check("Sam's deposit", per_entry[1], SAM)
            check("$1,240 + $880 = $2,120, the figure the ruling was signed on",
                  day_cash, EXPECTED)

            raise RollBack
except RollBack:
    pass

# ── 6 · nothing was written ───────────────────────────────────────────────
print()
print("── 6 · THE DATABASE IS AS IT WAS FOUND ──")
with tenant_context(str(tenant.id)):
    left = ledger_models.JournalEntry.objects.filter(
        tenant_id=tenant.id, source_id__in=[dana_batch, sam_batch]
    ).count()
check("entries left behind by this proof", left, 0)

print()
if failures:
    print(f"RESULT: {len(failures)} FAILED —")
    for line in failures:
        print(f"  - {line}")
    sys.exit(1)
print("RESULT: every check PASSED — the ledger already accepts two deposits for one")
print("        day, each balanced, and the day ties to $2,120.00 exactly.")
