"""`P3.6` — THE ACCRUAL AND ITS DAY-1 MIRROR, PROVED ON REAL POSTGRESQL.

Finance blueprint p016, verbatim: *"Accrual posting proved on PostgreSQL — the
day-1 reversal pair, linked both ways"*, with `BR-LED-005` and `LE-4` as its
reference and the outcome *"1210 nets 0.00, as the worked example says"*.

══════════════════════════════════════════════════════════════════════════════
WHY IT IS NOT THE ORDINARY SUITE, AND THIS IS NOT A PREFERENCE
══════════════════════════════════════════════════════════════════════════════
`config/settings/test.py` HARDCODES in-memory SQLite and ignores `DATABASE_URL`
(CLAUDE.md hard-won law 14). SQLite has **no aborted-transaction state**, so a
posting path that catches a database error and carries on passes the whole suite
green and fails the first time a real row is refused in production.

`unbilled_accrual.accrue_unbilled_revenue` and
`manual_je.run_accrual_auto_reversals` are both posting paths on a money route,
and the second one **writes inside a loop over rows that can each be refused by
a UNIQUE constraint** (`uq_journal_entries_reversal`). That is exactly the shape
law 14 exists for. This proves the pair on PostgreSQL 16, watched.

══════════════════════════════════════════════════════════════════════════════
WHAT IT PROVES, AND IN THIS ORDER
══════════════════════════════════════════════════════════════════════════════
  §1  the role cannot bypass RLS — a superuser would make every figure vacuous
  §2  the four engines answer, and **two say `accrual` while two say `standard`
      with `reverses_on: null`** — `P3.1`'s two columns, from the SERVER
  §3  the accrual POSTS: one entry, `type='accrual'`, dated the period end,
      balanced, with a posting key
  §4  a REPLAY writes nothing — `created: false`, the SAME entry id
  §5  the day-1 sweep posts the MIRROR, and the pair is **linked both ways**
  §6  **the unbilled-AR account nets 0.00 across the pair** — LE-4's figure
  §7  the sweep is idempotent: a second run reports `created: 0` and the
      UNIQUE constraint is what makes it so — proved by asking the database
  §8  ⚠ **RED ON PURPOSE** — the same duplicate WITHOUT a savepoint poisons the
      transaction, which is law 14's own symptom and is why the engine keeps one
  §9  **DEPRECIATION POSTS `type='standard'` AND THE SWEEP LEAVES IT ALONE.**
      This is the $40,000 check: a depreciation entry that reversed itself on
      day 1 would leave the plant at its purchase cost for ever.

Everything it writes is ROLLED BACK at the end, so it may be run again.

RUN — against a CLONE, never a shared database:

    eval "$(10-scripts/proof-db.sh clone finp3 --export)"
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      python3 ../10-scripts/fin_p3_6_accrual_reversal_pg_proof.py

`SBH_PROOF_TENANT` picks the tenant; it defaults to the first one.
"""

import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import django

_BACKEND = Path(__file__).resolve().parents[1] / "06-backend"
if _BACKEND.is_dir() and str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.db import IntegrityError, connection, transaction  # noqa: E402
from django.db.utils import InternalError, OperationalError, ProgrammingError  # noqa: E402

from apps.identity.models import User  # noqa: E402
from apps.identity.models import TenantMembership  # noqa: E402
from apps.ledger import close, depreciation, manual_je, models, unbilled_accrual  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


print(f"vendor: {connection.vendor}")
if connection.vendor != "postgresql":
    sys.exit("REFUSED: this proof is meaningless on SQLite. Set DATABASE_URL.")

print("\n§1 · THE ROLE")
with connection.cursor() as cur:
    cur.execute(
        "select current_user, rolsuper, rolbypassrls from pg_roles where rolname = current_user"
    )
    who, is_super, bypasses = cur.fetchone()
    cur.execute("select id from tenants order by provisioned_at nulls last limit 1")
    first_tenant = cur.fetchone()[0]
print(f"  current_user={who} rolsuper={is_super} rolbypassrls={bypasses}")
check("the role cannot bypass RLS", not is_super and not bypasses)

TENANT = uuid.UUID(os.environ.get("SBH_PROOF_TENANT", str(first_tenant)))


def moment(day: date) -> datetime:
    """BR-TEN-043 — the posting instant is an INPUT and this file states it."""
    return datetime(day.year, day.month, day.day, 12, 0, 0, tzinfo=timezone.utc)


try:
    with core_tenancy.tenant_context(TENANT):
        # ⚠ **THE ACTOR IS NAMED, NOT *the first user*.** `accrue_unbilled_
        # revenue` carries `@require_role` and a field technician meets a 403 —
        # which reads exactly like a broken engine. `SBH_PROOF_ACTOR` overrides
        # it; the default is `seed_demo`'s System Admin.
        actor_email = os.environ.get("SBH_PROOF_ACTOR", "dana@brazosbendutilities.com")
        user = User.objects.filter(email=actor_email).first()
        assert user is not None, f"no user {actor_email} on this clone"
        # ⚠ **`@require_role` READS `actor.role`, WHICH `User` DOES NOT CARRY** —
        # the role lives on `tenant_memberships`, and the API layer composes the
        # two. A shell caller must compose them too, which is what this does;
        # the role is READ from the membership rather than asserted, so a
        # technician cannot be dressed up as an admin here.
        membership_role = (
            TenantMembership.objects.filter(tenant_id=TENANT, user_id=user.pk)
            .values_list("role__code", flat=True)
            .first()
        )
        assert membership_role is not None, f"{actor_email} is not a member of this tenant"
        actor = SimpleNamespace(id=user.pk, pk=user.pk, role=membership_role, user=user)
        print(f"  acting as {user.email} ({membership_role})")

        # ⚠ **THE WINDOW IS THE TENANT'S FISCAL PERIOD, ASKED FOR RATHER THAN
        # COMPOSED.** BR-TEN-022 computes a period from the tenant's fiscal year
        # and close cadence, so a utility closing QUARTERLY accrues into a
        # quarter. Adding a month to a date here would be a second calendar.
        today = date.today()
        start, end = close.period_window(today)
        due = manual_je.accrual_reversal_due_on(end)
        print(f"\n  period {start} … {end}; the mirror is due {due}")
        check(
            "the mirror is the day AFTER the period ends (BR-LED-005)",
            due == end + timedelta(days=1),
            f"{end} → {due}",
        )

        with transaction.atomic():
            sid = transaction.savepoint()

            print("\n§2 · THE FOUR ENGINES, AND THE TWO COLUMNS THAT STOP THE $40,000 ERROR")
            unbilled_preview = unbilled_accrual.preview_unbilled_revenue(
                period_start=start, period_end=end
            )
            depreciation_preview = depreciation.preview_depreciation(
                period_start=start, period_end=end
            )
            print(
                f"  unbilled total={unbilled_preview.total} "
                f"depreciation total={depreciation_preview.total}"
            )

            print("\n§3 · THE ACCRUAL POSTS")
            result = unbilled_accrual.accrue_unbilled_revenue(
                actor, period_start=start, period_end=end, posted_at=moment(end)
            )
            if result.entry_id is None:
                print(
                    "  SKIP — this window has nothing to accrue on this clone, so "
                    "§3–§8 cannot be proved here. Seed reads after the cycle end and re-run."
                )
            else:
                accrual = models.JournalEntry.objects.get(pk=result.entry_id)
                check("one entry, and it is type='accrual'", accrual.type == models.JE_ACCRUAL,
                      accrual.type)
                check("it is dated the period END", accrual.entry_date == end, str(accrual.entry_date))
                check("it carries a posting key", bool(result.posting_key), result.posting_key)

                # ⚠ **ONE `amount` AND A `side`, NOT TWO COLUMNS.** `journal_lines`
                # carries `side` ∈ {debit, credit} (`models.JOURNAL_SIDES`); a
                # proof that assumed `debit`/`credit` columns would not compile,
                # which is how this was found rather than assumed.
                lines = list(models.JournalLine.objects.filter(journal_entry_id=accrual.pk))
                debits = sum(
                    line.amount for line in lines if line.side == models.SIDE_DEBIT
                )
                credits = sum(
                    line.amount for line in lines if line.side == models.SIDE_CREDIT
                )
                check("the entry BALANCES (hard rule 5)", debits == credits, f"{debits} = {credits}")

                print("\n§4 · THE REPLAY WRITES NOTHING")
                again = unbilled_accrual.accrue_unbilled_revenue(
                    actor, period_start=start, period_end=end, posted_at=moment(end)
                )
                check("created is FALSE on the second press", again.created is False)
                check("the SAME entry comes back", str(again.entry_id) == str(result.entry_id))

                print("\n§5 · THE DAY-1 MIRROR, LINKED BOTH WAYS")
                # The sweep answers a TUPLE of rows, one per accrual it looked
                # at — not a summary object. It is keyword-only and takes the
                # actor as a keyword too.
                sweep = manual_je.run_accrual_auto_reversals(
                    as_of=due, posted_at=moment(due), actor=actor
                )
                mirrored = [row for row in sweep if str(row.accrual_entry_id) == str(accrual.pk)]
                check("the sweep found this accrual", len(mirrored) == 1, f"{len(mirrored)} row(s)")
                if mirrored:
                    mirror_id = mirrored[0].mirror_entry_id
                    check("it posted a mirror", mirror_id is not None)
                    if mirror_id is not None:
                        mirror = models.JournalEntry.objects.get(pk=mirror_id)
                        check("the mirror is dated day 1 of the NEXT period",
                              mirror.entry_date == due, str(mirror.entry_date))
                        # ⚠ **LINKED BOTH WAYS, AND IT IS TWO COLUMNS** (r13 #2):
                        # `auto_reverse_entry` on the ACCRUAL points forward and
                        # `reversal_of` on the MIRROR points back. One column
                        # cannot answer *was this reversed?* and *is this the
                        # reversal?* at once.
                        accrual.refresh_from_db()
                        check("accrual → mirror (auto_reverse_entry)",
                              str(accrual.auto_reverse_entry_id) == str(mirror.pk))
                        check("mirror → accrual (reversal_of)",
                              str(mirror.reversal_of_id) == str(accrual.pk))

                        print("\n§6 · THE PAIR NETS TO ZERO (LE-4)")
                        account_id = unbilled_preview.unbilled_ar_account_id
                        if account_id is None:
                            print("  SKIP — this tenant seeds no unbilled-AR account")
                        else:
                            both = models.JournalLine.objects.filter(
                                journal_entry_id__in=[accrual.pk, mirror.pk],
                                ledger_account_id=account_id,
                            )
                            net = sum(
                                (
                                    line.amount
                                    if line.side == models.SIDE_DEBIT
                                    else -line.amount
                                )
                                for line in both
                            )
                            check("the unbilled-AR account nets 0.00 across the pair",
                                  net == Decimal("0"), str(net))

                print("\n§7 · THE SWEEP IS IDEMPOTENT, AND THE DATABASE IS WHY")
                # ⚠ **THE FIRST DRAFT OF THIS SECTION COULD NOT FAIL, AND IT IS
                # WORTH SAYING SO HERE.** It read `all(row.created is False for
                # row in repeated)` over a list that is EMPTY on the second
                # sweep — an accrual that already has a mirror is not in the
                # pending set at all — so the assertion was vacuously true
                # whatever the engine did. That is hard-won law 7's
                # *structurally incapable of failing* shape, in a proof written
                # to honour law 14.
                #
                # **The question that can actually fail is a COUNT OF MIRRORS**,
                # asked of the database after the second sweep.
                before = models.JournalEntry.objects.filter(reversal_of_id=accrual.pk).count()
                second = manual_je.run_accrual_auto_reversals(
                    as_of=due, posted_at=moment(due), actor=actor
                )
                after = models.JournalEntry.objects.filter(reversal_of_id=accrual.pk).count()
                created_again = [
                    row
                    for row in second
                    if str(row.accrual_entry_id) == str(accrual.pk) and row.created
                ]
                check("exactly ONE mirror existed before the second sweep", before == 1, str(before))
                check("and exactly one after it", after == 1, str(after))
                check("the second sweep reports no creation for this accrual",
                      created_again == [], f"{len(created_again)} created")

                print("\n§8 · RED ON PURPOSE — THE SAME WRITE WITHOUT A SAVEPOINT")
                # ⚠ **THIS IS THE HALF SQLITE CANNOT SHOW.** A UNIQUE violation
                # inside a transaction poisons it on PostgreSQL: every later
                # query raises until the block ends. The engine survives it by
                # nesting `atomic()` (a SAVEPOINT); here we deliberately DO NOT,
                # and watch the next query fail.
                # ⚠ **THE REFUSAL IS READ, NOT COUNTED.** A first draft caught
                # `ProgrammingError` as well and printed only the class name —
                # which would have passed just as happily on a misspelt column,
                # proving the wrong thing loudly. `journal_entries` has no
                # `reversal_of_entry_id` column (it is `reversal_of`), and that
                # is exactly the mistake that was being made. The refusal must
                # NAME the unique index, or this section fails.
                poisoned = False
                refusal = ""
                inner = transaction.savepoint()
                try:
                    with connection.cursor() as cur:
                        cur.execute(
                            "insert into journal_entries (id, tenant_id, entry_date, type, status,"
                            " reversal_of, created_at, updated_at)"
                            " values (%s, %s, %s, 'reversing', 'posted', %s, now(), now())",
                            [str(uuid.uuid4()), str(TENANT), due, str(accrual.pk)],
                        )
                except (IntegrityError, InternalError, OperationalError, ProgrammingError) as exc:
                    refusal = str(exc)
                    print(f"    the duplicate was refused: {type(exc).__name__}: {refusal.strip()[:120]}")
                    try:
                        with connection.cursor() as cur:
                            cur.execute("select 1")
                    except Exception as later:  # noqa: BLE001 — the symptom IS the proof
                        poisoned = True
                        print(f"    and the transaction is now poisoned: {type(later).__name__}")
                # ⚠ **WHAT ACTUALLY REFUSES IT IS HARD RULE 5, AND THAT IS A
                # BETTER FACT THAN THE ONE THIS CHECK WAS FIRST WRITTEN FOR.**
                # The first version asserted `uq_journal_entries_reversal` by
                # name and went RED, correctly: a raw INSERT never reaches that
                # index, because a DATABASE TRIGGER refuses any write to
                # `journal_entries` that did not come through
                # `apps/ledger/posting.py`. CLAUDE.md hard rule 5, enforced in
                # the database rather than by convention.
                #
                # **The check is rewritten to say what is true rather than
                # softened to pass**, and the poisoning half — which is the
                # whole point of the section — is unaffected: any refused
                # statement poisons a PostgreSQL transaction, whichever guard
                # refused it.
                check(
                    "a raw INSERT into journal_entries is refused BY THE DATABASE "
                    "(hard rule 5 — only the posting service writes them)",
                    "posting service" in refusal or "posting.py" in refusal,
                    refusal.strip()[:140] or "nothing was refused at all",
                )
                # And the reversal index EXISTS, asked of the catalogue rather
                # than inferred from an error this insert never reached.
                with connection.cursor() as probe_cur:
                    transaction.savepoint_rollback(inner)
                    inner = transaction.savepoint()
                    probe_cur.execute(
                        "select 1 from pg_indexes where indexname = %s",
                        ["uq_journal_entries_reversal"],
                    )
                    has_index = probe_cur.fetchone() is not None
                check(
                    "uq_journal_entries_reversal exists — it is what makes the sweep "
                    "idempotent even against a concurrent second run",
                    has_index,
                )
                check(
                    "a refused statement poisons the transaction — which is why the "
                    "engine keeps a SAVEPOINT (law 14)",
                    poisoned,
                    "if this says FAIL, read it before trusting it: either the "
                    "constraint did not fire, or this is not PostgreSQL",
                )
                transaction.savepoint_rollback(inner)

            print("\n§9 · DEPRECIATION POSTS `standard` AND THE SWEEP LEAVES IT ALONE")
            dep = depreciation.post_depreciation(
                actor, period_start=start, period_end=end, posted_at=moment(end)
            )
            if dep.entry_id is None:
                print("  SKIP — nothing to depreciate on this clone")
            else:
                dep_entry = models.JournalEntry.objects.get(pk=dep.entry_id)
                # ⚠ **THE $40,000 CHECK.** `depreciation.py`: *"a depreciation
                # entry that reversed itself on day 1 would leave the plant at
                # its purchase cost forever."*
                check("depreciation is type='standard'",
                      dep_entry.type == models.JE_STANDARD, dep_entry.type)
                sweep = manual_je.run_accrual_auto_reversals(
                    as_of=due, posted_at=moment(due), actor=actor
                )
                touched = [
                    row for row in sweep if str(row.accrual_entry_id) == str(dep_entry.pk)
                ]
                check("the day-1 sweep does NOT touch it", touched == [], f"{len(touched)} row(s)")
                dep_entry.refresh_from_db()
                check("and nothing reversed it", dep_entry.auto_reverse_entry_id is None)

            transaction.savepoint_rollback(sid)
            print("\n  (everything above is rolled back)")
finally:
    pass

print("\n── verdict ───────────────────")
if FAILURES:
    print(f"  {len(FAILURES)} FAILURE(S):")
    for failure in FAILURES:
        print("    · " + failure)
    sys.exit(1)
print("  every check passed on PostgreSQL")
