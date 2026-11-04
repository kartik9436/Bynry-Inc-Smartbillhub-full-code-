# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-012 (the ad-hoc single bill — the run row it has never had)
#           · US-BIL-010 (first bill) · US-BIL-011 (final bill) · US-BIL-013
#           (back-bill) · US-BIL-014 (penalty/theft bill): all five engines take
#           a `bill_run` and none of them could lawfully be given one
#           Screens: S30 (One-time bill tab) · S31 (single-account mode)
# Rules:    BR-BIL-020 (ad-hoc single bill = the bulk wizard in single-account
#           mode) · BR-BIL-005 (a run is idempotent on tenant + scope + period)
#           · BR-BIL-018 (back-bills run "via the single-account flow") ·
#           BR-BIL-023 (a re-run REPLACES its draft — stage 6 keys that
#           replacement on `(tenant, account, bill_run)`, which is why the run
#           row is required rather than convenient) · B2 Addendum r10 #7
#           (`bill_runs` += … + scope) · r10 #12 (`bill_type`)
# ───────────────────────────────────────────────────────
"""billing 0021 — the two columns a ONE-TIME bill run needs, and a scope check.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-16 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*). Row in 12-governance/09-human-review-ledger.md.

WHAT IT IS
----------
Two column changes and one CHECK constraint on `bill_runs`:

    cycle_id          NOT NULL  →  NULL allowed
    scope_account_id  (new)        uuid NULL → customers.accounts
    ck_bill_runs_has_a_scope       CHECK (cycle_id IS NOT NULL
                                          OR scope_account_id IS NOT NULL)

WHY, AND IT IS NOT A TIDYING
----------------------------
Five complete, tested billing engines could not be reached by anybody, and this
is the reason. `first_bill.calculate_first_bill`, `final_bill.calculate_final_
bill`, `single.calculate_single_bill`, `backbill.calculate_back_bill` and
`penalty.calculate_penalty_bill` each take a `bill_run` — REQUIRED, because
stage 6 replaces an existing draft for `(tenant, account, bill_run)` and a
`None` there would make a January back-bill and a July interim bill collide, the
second silently deleting the first (`single.py`'s own trailer, exception 2).

`apps/billing/single.py` reported the blockage in its own words before this
migration existed:

    "Reported rather than worked around: `bill_runs.cycle_id` is NOT NULL and
     `runs.create_run` takes no `bill_type`, so an ad-hoc run row is typed
     `cycle` while the invoice it produces is typed `final`/`backbill`/
     `penalty`, and r10 #7's single-account SCOPE has no column at all. Both
     belong to the lane that owns `models.py` / `runs.py`."

This is that lane. Both gaps close here.

WHY NOT JUST POINT AN AD-HOC RUN AT SOME CYCLE
----------------------------------------------
It was the obvious alternative and it is wrong twice over, both times in a way
that costs money rather than tidiness:

  * **BR-BIL-005 would refuse it.** A run's idempotency key is
    `<cycle>|<period_start>|<period_end>`, so a one-off July bill for ONE
    account keys identically to July's real cycle run over five hundred. The
    unique index would refuse the second of them — and which one loses depends
    on which a clerk happened to start first.
  * **It would file the bill in a cycle it was never part of.**
    `selectors.invoice_list_queryset` filters S30 on `bill_run__cycle_id`, so a
    move-out final bill produced in August would appear inside the August cycle
    run's results, and that run's own count of what it billed would be wrong.

A one-time bill genuinely has no cycle. The column says so.

WHY `scope_account_id` IS A COLUMN AND NOT AN INFERENCE
------------------------------------------------------
It can be inferred today — one invoice hangs off the run and it names its
account — and an inference is not a scope. r10 #7 asks `bill_runs` for its
"scope"; `scope_services` carries the SERVICE half and nothing carried the
ACCOUNT half. The difference shows the moment a run produces NO invoice, which
is the ordinary outcome of a refused prepare: the row then records that a bill
was attempted for a named customer and did not happen, where an inference
records nothing at all.

WHY THE CHECK CONSTRAINT, AND WHY IT IS OR AND NOT XOR
------------------------------------------------------
Making `cycle_id` nullable creates a state that has never been legal and must
never become so: a run scoped to NEITHER a cycle nor an account. Such a row
names no population; the bills under it could not be explained by it.

The check is in POSTGRES rather than in `runs.py` because `runs.py` is not the
only writer this table will have — `pending.create_catch_up_run` writes it
today, and a future importer or fixture will too. A guarantee that lives in one
function is a guarantee until somebody writes a second function (hard-won law 1).

It is `OR`, not `XOR`, and that is a decision rather than a slip. A catch-up
sub-run (r10 #7, BR-BIL-015) is scoped to its parent's CYCLE *and* to the held
accounts it re-bills, so both-set is a shape the product already means. Ruling
it out here would decide US-BIL-006's future with no story asking. The
constraint forbids exactly the case that is certainly wrong.

BACKFILL: NONE, AND NONE IS NEEDED
----------------------------------
Every existing `bill_runs` row has a `cycle_id` — it was NOT NULL until this
migration — so every one of them satisfies the new check on the first branch.
`scope_account_id` is NULL on all of them, which is the correct reading: they
are cycle runs and are scoped to no single account.

Relaxing NOT NULL and adding a nullable column are both metadata-only in
Postgres. The CHECK is validated over the table once at ADD time; on a tenant
of this product's size (<3,000 connections, so runs in the hundreds) that is
not a lock worth planning around.

IMMUTABILITY AND RLS
--------------------
No immutability trigger is touched and none should be. Hard rule 4 freezes
ISSUED invoices, invoice lines, payments and journal lines; a run row moves
through five phases by design (BR-BIL-050) and `0002_rls_w3_and_immutability`
installs triggers on `invoices` and `invoice_lines` only — checked in that file
rather than assumed here.

RLS needs no new operation. `bill_runs` has carried `bill_runs_tenant_isolation`
under ENABLE + FORCE since `0002`, and a policy is per TABLE, not per column: a
column added to a protected table is protected. ⚠ The FK to `customers.accounts`
does NOT weaken that — but it does not strengthen it either, and the code is
where that is enforced: PostgreSQL evaluates referential integrity OUTSIDE row
level security, so a foreign key alone would not stop a run being pointed at
another tenant's account. `runs.create_one_time_run` resolves the account
through `single.billable_account` (customers' own tenant-scoped read) BEFORE it
writes the row, exactly as `create_run` verifies its cycle through metering's
`cycles_list` and for exactly the same reason.
"""

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0020_credit_note_sign"),
        # `scope_account_id` points at `customers.accounts`, so that table must
        # exist first. Named rather than left to Django's inference: migration
        # ORDERING is 🔒 and an implicit dependency is not a stated one.
        ("customers", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="billrun",
            name="cycle",
            field=models.ForeignKey(
                blank=True,
                null=True,
                db_column="cycle_id",
                on_delete=models.deletion.PROTECT,
                to="metering.cycle",
            ),
        ),
        migrations.AddField(
            model_name="billrun",
            name="scope_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                db_column="scope_account_id",
                on_delete=models.deletion.PROTECT,
                related_name="one_time_bill_runs",
                to="customers.account",
            ),
        ),
        migrations.AddConstraint(
            model_name="billrun",
            constraint=models.CheckConstraint(
                condition=Q(cycle__isnull=False) | Q(scope_account__isnull=False),
                name="ck_bill_runs_has_a_scope",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-012@f0a3c21 (this file's own sources, in order:
#         04-docs/02-decisions/02-database-design-brief.md Addendum r10 #7 +
#         #12 · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-020 +
#         BR-BIL-005 + BR-BIL-018 + BR-BIL-023 ·
#         04-docs/05-modules/07-billing/06-epics/EP-BIL-03-bill-types.md ·
#         06-backend/apps/billing/single.py's own reported gaps)
# generated: 2026-08-16 by Eng-Lead (S30 One-time bill tab lane — US-BIL-010..014)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI — the tab is this lane's frontend half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: `makemigrations --check` clean · pytest tests/test_us_bil_012_one_time.py · run_gates
# exceptions: (1) `cycle_id` GOES NULLABLE, which relaxes a signed B2 §2 column.
#         REPORTED as a deviation rather than taken silently: B2 §2 types it NOT
#         NULL and r10 #7 does not revisit it, but r10 #7 DOES require the run to
#         carry a scope and BR-BIL-020/018 both put one-time bills through a
#         single-account flow that has no cycle to name. The signed schema and
#         the signed rules disagree; the rules were followed and the deviation is
#         named. A reviewer should confirm — this is the same posture 0001 took
#         when it shipped `UNIQUE (tenant, invoice_no)` PARTIAL.
#         (2) The CHECK is `OR`, not `XOR` — both-set stays legal because a
#         catch-up sub-run is scoped to a cycle AND to accounts (r10 #7).
#         (3) NO BACKFILL, and none is possible to get wrong: every pre-existing
#         row has a cycle, so every one satisfies the check on its first branch.
#         (4) The FK to `customers.accounts` does NOT enforce tenancy — Postgres
#         evaluates referential integrity outside RLS — so the account is
#         resolved through customers' own tenant-scoped read before the row is
#         written. Same posture, same reason, as `create_run`'s cycle check.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
