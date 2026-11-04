"""customers 0003 — seeds the PLATFORM `account_types` catalog.
HUMAN-OWNED · HUMAN-REVIEW-PENDING (migration ordering is a CLAUDE.md 🔒 path,
as amended by PO 2026-08-09: AI authors it, a human reviews it later). Row
recorded in 12-governance/09-human-review-ledger.md.

WHY A MIGRATION AND NOT THE TENANT SEEDER. r5 #12 [D5] reads "account_types
(platform-seeded: residential/commercial/industrial/government) +
account_subtypes (tenant-defined, RLS)", and r5's closing line excludes
`account_types` from RLS as a platform table. Platform rows are identical for
every tenant and must exist BEFORE the first tenant does — there is then no
tenant, no session and no actor to route a write through a service, which is
exactly the posture tenancy 0001 takes for the 10-service catalog and tenancy
0005 for the subscription-plan SKUs. Seeding it from the per-tenant reference
fixture instead would make four global rows appear as a side effect of one
tenant signing up.

VALUE PROVENANCE — every row is QUOTED, none is chosen:
  · The four codes and their order are B2 Addendum r5 "New tables (15)" #12
    [D5], verbatim.
  · `government` (not the S8 prototype card's "Municipal") is the PO ruling of
    2026-08-10. B2 governs DATA, the prototype governs layout/copy
    (CLAUDE.md); the divergence was recorded in
    apps/tenancy/services.UNSEEDABLE_REFERENCE_LISTS before this lane and is
    settled by that ruling, not by this file.
  · Display names are the plain title-case of each ratified code. No source
    states a different label, and the S8 card is tenant-visible copy, so a
    label had to exist; it is the only thing here not lifted word-for-word,
    and it is stated rather than passed over.

⚠ FOR THE REVIEWER — three notes:

1. **INSERT-MISSING, never UPDATE.** A row that already exists is left exactly
   as it is, timestamps included — the same rule tenancy 0005 demonstrated
   against real data. Re-applying is a no-op.

2. **No tenant context is set or needed.** `account_types` has no `tenant_id`
   and carries no RLS policy (migration 0002 covers the five tenant tables
   only), so this data step touches no tenant table and CLAUDE.md rule 1 has
   nothing to bite on. Contrast assets 0003, which had to enumerate tenants
   and `set_config('app.tenant_id')` per tenant because its catalogs ARE
   tenant tables.

3. **The reverse deliberately deletes nothing.** `accounts.account_type_id` is
   a PROTECTed NOT NULL FK; removing a platform category during a rollback
   would either fail loudly against live accounts or quietly strand a
   vocabulary other tenants depend on. Inert-when-unreferenced reference data
   is left in place, exactly as tenancy 0005 leaves the subscription plans.

The seed set is duplicated from apps/customers/services.SEED_ACCOUNT_TYPES on
purpose: a migration must keep working when a service constant later changes.
Both copies carry the SAME ratified values; if they ever diverge, B2 r5 #12
[D5] is the tiebreaker, not either copy. tests/test_us_cus_schema_and_seed.py
pins the two equal so the divergence cannot happen silently.
"""

from django.db import migrations

# B2 Addendum r5 #12 [D5], verbatim (+ PO 2026-08-10 on `government`).
SEED_ACCOUNT_TYPES = (
    ("residential", "Residential"),
    ("commercial", "Commercial"),
    ("industrial", "Industrial"),
    ("government", "Government"),
)


def seed_account_types(apps, schema_editor):
    """Insert-missing the four PLATFORM consumer categories."""
    AccountType = apps.get_model("customers", "AccountType")
    for code, name in SEED_ACCOUNT_TYPES:
        AccountType.objects.get_or_create(
            code=code,
            defaults={"name": name, "is_system": True, "active": True},
        )


def unseed_account_types(apps, schema_editor):
    """Reverse: a deliberate no-op (see reviewer note 3)."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0002_rls_w2_policies"),
    ]

    operations = [
        migrations.RunPython(seed_account_types, unseed_account_types),
    ]
