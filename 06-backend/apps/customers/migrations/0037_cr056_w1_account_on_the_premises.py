# ── Trace ──────────────────────────────────────────────
# Change:  CR-056 W1 task 5 + task 6 — the owner's account moves from a
#          common-area UNIT to the ADDRESS. `accounts.premises_id` is added,
#          `accounts.unit_id` becomes NULLABLE, and every existing row is
#          backfilled so that not one bill moves.
#          Screens: S17 Accounts · S21 account detail · PRM-02 Common areas
# Rules:   BR-CUS-1010 (a Master Account is the owner's account AT AN ADDRESS —
#          `CR-056` R1, PO verbatim, plus R2 as ratified in substance by the PO
#          ruling of 2026-08-31) · BR-CUS-1011 (one owner account per address) ·
#          BR-CUS-1012 (an account that names no unit neither occupies nor
#          blocks one; a `regular` account must still name one) ·
#          BR-CUS-068 (SUPERSEDED in its anchoring, CONFIRMED in its shape) ·
#          BR-CUS-017 / OQ-092 (the enforcement posture the checks respect) ·
#          BR-MET-101 (the worked figure: 1408 Elm, $41.20 + $28.40 = $69.60) ·
#          CLAUDE.md rule 1 (tenant scoping) · hard rule 4 (nothing issued is
#          rewritten — this touches no invoice, line, payment or journal row)
# Tests:   06-backend/tests/test_cr056_w1_account_on_the_address.py ·
#          06-backend/tests/test_br_cus_068_master_bill.py (the $69.60 pin)
# Impacts: apps/customers/models.py · services.py (`create_master_account`,
#          `_refuse_if_unit_occupied`, `lock_unit_scope`) · selectors.py
#          (`accounts_for_bill_run`, `account_row`, the BR-CUS-170/171 reads) ·
#          apps/metering/premises_owners.py (`ensure_owner_master_account`)
# ───────────────────────────────────────────────────────
"""customers 0037 — `accounts.premises_id`, a nullable `unit_id`, and a
backfill that moves no money.

⚠ **THIS WAS ALLOCATED AS `0036` AND HAD TO RENUMBER AT PUSH TIME — the same
mechanism as `DEF-1787`/`DEF-2711`.** The `CR-056` W2/W3 lane took `0036` for
`0036_cr056_w2_customer_identity` from its own worktree while this one was
working, so both lanes were correct and invisible to each other. Re-derived from
the branch tip at push time (law 11: re-derive the CONTENT and the IDS in one
act) and moved to `0037`, depending on `0036_cr056_w2_customer_identity`, the
real leaf. Three rule ids moved with it for the same reason — `BR-CUS-1000/1001`
and `BR-MET-1000` were taken by that lane, so this one carries
`BR-CUS-1010/1011/1012` and `BR-MET-1010/1011`.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list, and this one also relaxes a NOT NULL on the column the
bill run resolves scope by. AI-authored under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). The row in
`12-governance/09-human-review-ledger.md` states in plain English, with the
figures, what a reviewer is being asked to agree to.

════════════════════════════════════════════════════════════════════════════
WHAT CHANGED, AND WHOSE RULING CHANGED IT
════════════════════════════════════════════════════════════════════════════
Until now a Master Account was **the bill for shared space**: it anchored on the
premises' first common-area unit and reached the others through service
agreements. From `CR-056` it is **the owner's account at an address**. The PO
ruled on 2026-08-31 that *every address gets its owner a Master Account, whether
or not anything is shared, and whether or not the owner lives there* — and an
account that must exist for an address with nothing shared cannot hang off a
shared unit, because there is not one.

So `accounts` gains the address and loses the requirement to name a unit.

════════════════════════════════════════════════════════════════════════════
WHY `premises_id` IS A PLAIN UUID AND NOT A ForeignKey
════════════════════════════════════════════════════════════════════════════
B2 §2's cross-module FK set is REVIEWED, and `accounts.unit_id` is in it.
`accounts.premises_id` is not. Minting a second cross-module FK is a schema
review, not a side effect of a wave — which is the reasoning already recorded on
`accounts.template_override_id` (*"A PLAIN UUID, NOT a ForeignKey, AND THAT IS
THE ESTABLISHED SHAPE"*) and on `service_requests.resolved_premises_id`. The
same posture, a third time, for the same reason.

════════════════════════════════════════════════════════════════════════════
THE BACKFILL — AND WHY IT DELIBERATELY DOES NOT RE-ANCHOR ANYTHING
════════════════════════════════════════════════════════════════════════════
`CR-056` task 6 is one sentence: **every existing Master Account bills exactly
what it bills today.** So the backfill only fills `premises_id` IN, from each
account's own unit's premises. It moves no `unit_id`, closes no service
agreement and writes no other column.

That leaves two shapes in one table on purpose:

    before 2026-09-01   unit_id = the anchor common area   premises_id = filled in here
    after  2026-09-01   unit_id = NULL                     premises_id = the address

and every read that matters (`covered_unit_ids`, `base_charge_only_coverage`,
`master_account_for`) answers identically on both, because coverage has ridden
`service_agreements` since 2026-08-22 and still does. **1408 Elm Street bills
`$41.20` + `$28.40` = `$69.60` on either shape** — same figure, different
plumbing, which is the whole of `CR-056` §2.

Re-anchoring live accounts would change what a money path reads in order to
tidy a column, and nothing asked for that.

⚠ **IT IS TENANT-SCOPED EVEN THOUGH A MIGRATION IS NOT RLS-BOUND** (CLAUDE.md
rule 1). The update is driven one tenant at a time from the tenant ids that
actually hold accounts, which is the shape migration 0014's backfill already
uses, so a partial failure cannot cross a tenant boundary and the work is
readable per tenant in a log.

⚠ **NO `try/except IntegrityError: continue` ANYWHERE IN HERE** (CLAUDE.md law
14). There is nothing to skip: the write sets a nullable column from a lookup
that either resolves or leaves NULL, so no row can be refused and there is no
aborted-transaction state to recover from. If a later lane adds a per-row
refusal here, it needs a SAVEPOINT and it needs proving on real PostgreSQL —
the suite is in-memory SQLite and the broken version passes it green.

════════════════════════════════════════════════════════════════════════════
THE TWO CHECK CONSTRAINTS THAT REPLACE THE `NOT NULL`
════════════════════════════════════════════════════════════════════════════
* `ck_accounts_anchored` — a row names a unit or a premises. An account at no
  address is one nothing can bill, show, or find an owner for.
* `ck_accounts_regular_has_unit` — a `regular` account still names a unit
  (`BR-CUS-1012`). The nullability exists for the owner's account and for
  nothing else; an occupying account with no unit would produce a bill with
  nothing to price, and `covered_unit_ids` would answer `[]` in silence.

Both are satisfied by every row in the product **before** this migration runs,
because every row has a unit today. They are added AFTER the backfill so the
column they read is already populated.

⚠ `BR-CUS-017`'s one-active-account-per-unit index is still NOT here and still
cannot be (`OQ-092`, option (a): service-layer only, because the predicate needs
`status = 'active'` and `status` is a lookup FK). These two are different
constraints over columns that are not lookups — that is why they can exist where
that one could not, and adding them does not reopen `OQ-092`.

════════════════════════════════════════════════════════════════════════════
REVERSIBILITY
════════════════════════════════════════════════════════════════════════════
Reverse drops both constraints, drops the column and restores the `NOT NULL`.
⚠ **The reverse REFUSES rather than deleting** if any account has a NULL
`unit_id` by then — those are `BR-CUS-1010` owner accounts, and restoring a
`NOT NULL` over them would mean either destroying real accounts or inventing a
unit for them. A refusal with a count in it is the honest answer; the operator
decides what happens to those rows.
"""

from django.db import migrations, models
from django.db.models import Q


def fill_premises_from_unit(apps, schema_editor):
    """`accounts.premises_id` := the premises the account's own unit sits on.

    Driven one tenant at a time. `unit_id` is untouched, so no bill moves.
    """
    Account = apps.get_model("customers", "Account")
    Unit = apps.get_model("metering", "Unit")

    tenant_ids = list(
        Account.objects.order_by("tenant_id").values_list("tenant_id", flat=True).distinct()
    )
    for tenant_id in tenant_ids:
        rows = list(
            Account.objects.filter(tenant_id=tenant_id, unit_id__isnull=False).values_list(
                "id", "unit_id"
            )
        )
        if not rows:
            continue
        premises_by_unit = dict(
            Unit.objects.filter(
                tenant_id=tenant_id, id__in={unit_id for _pk, unit_id in rows}
            ).values_list("id", "premises_id")
        )
        by_premises: dict[object, list[object]] = {}
        for pk, unit_id in rows:
            premises_id = premises_by_unit.get(unit_id)
            if premises_id is None:
                # An honest absence, never a fabricated address: the unit is not
                # this tenant's, or metering has nothing for it. The row keeps
                # NULL and `_premises_id_for_unit` goes on answering for it
                # exactly as it did before this column existed.
                continue
            by_premises.setdefault(premises_id, []).append(pk)
        for premises_id, pks in by_premises.items():
            Account.objects.filter(tenant_id=tenant_id, id__in=pks).update(
                premises_id=premises_id
            )


def clear_premises(apps, schema_editor):
    """Reverse of the backfill — and it REFUSES rather than destroying."""
    Account = apps.get_model("customers", "Account")
    orphans = Account.objects.filter(unit_id__isnull=True).count()
    if orphans:
        raise RuntimeError(
            f"{orphans} account(s) name a premises and no unit (BR-CUS-1010 owner "
            "accounts). Reversing would either delete real accounts or invent a "
            "unit for them. Decide what happens to those rows first."
        )
    Account.objects.update(premises_id=None)


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0036_cr056_w2_customer_identity"),
        # The backfill reads `metering.Unit.premises_id`; the leaf pins the
        # state the historical model is built from.
        ("metering", "0043_cr054_w1_row_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="premises_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="account",
            name="unit",
            field=models.ForeignKey(
                blank=True,
                db_column="unit_id",
                null=True,
                on_delete=models.deletion.PROTECT,
                to="metering.unit",
            ),
        ),
        migrations.RunPython(fill_premises_from_unit, clear_premises),
        migrations.AddIndex(
            model_name="account",
            index=models.Index(
                fields=["tenant", "premises_id"], name="ix_accounts_tenant_premises"
            ),
        ),
        migrations.AddConstraint(
            model_name="account",
            constraint=models.CheckConstraint(
                condition=Q(unit__isnull=False) | Q(premises_id__isnull=False),
                name="ck_accounts_anchored",
            ),
        ),
        migrations.AddConstraint(
            model_name="account",
            constraint=models.CheckConstraint(
                condition=~Q(kind="regular") | Q(unit__isnull=False),
                name="ck_accounts_regular_has_unit",
            ),
        ),
    ]
