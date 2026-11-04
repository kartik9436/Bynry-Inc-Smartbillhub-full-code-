# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-007 (Settings → Services: the tenant's per-service row this
#           adds two columns to)   Screens: S8 · S56
# Rules:    BR-BIL-010 (service → revenue GL with an OPTIONAL usage/base
#           split — CONFIRMED) · CLAUDE.md rule 1 (tenant scoping; RLS FORCE)
# ───────────────────────────────────────────────────────
"""tenancy 0006 — `tenant_services.revenue_account` / `.base_revenue_account`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path, and these two columns
decide which revenue bucket a billed line lands in). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-11 under the PO ruling of 2026-08-09, implementing the PO
ruling of 2026-08-11 closing OQ-106: *"using attributes on accounts and Utility
services - we can derive how it sum up at Ledger."* Row in
12-governance/09-human-review-ledger.md.

THE SERVICE HALF OF A TWO-HALF RULING. `ledger/0003` adds the designation
attribute to `ledger_accounts`; this adds the revenue attributes to the
TENANT'S service. Two attribute homes, one derivation, and the derivation is
`apps/ledger/selectors.py`'s.

**WHY THESE COLUMNS ARE ON A TENANCY TABLE.** `tenant_services` is the tenant's
service enablement and it is tenancy's — the platform `services` catalog is a
different table, RLS-EXEMPT per B2 §3, shared by every tenant, and a revenue
account written there would be one tenant's chart visible to all of them. That
distinction is the reason these columns are here and not one table over. B2
r10 #2 names a ledger-owned `service_gl_map` table for the same fact; the PO's
"a field, not a table" ruling of the same day is what makes it two columns
instead, and the divergence is recorded in `12-governance/02-decision-log.md`
(2026-08-11) and in the `TenantService` docstring rather than left to be
noticed.

────────────────────────────────────────────────────────────────────────────
RLS: NOTHING NEW IS NEEDED, AND HERE IS WHY THAT IS TRUE RATHER THAN HOPED
────────────────────────────────────────────────────────────────────────────
No table is created. `tenant_services` is already ENABLE + FORCE under
`tenant_services_tenant_isolation`, applied verbatim from
`06-backend/db/rls_tenancy_w0.sql` by `0003_rls_w0_policies`; the policy gates
the ROW, so columns added to a gated row are gated. Writing a second policy for
the same table would shadow the signed one. The claim is backed by a test, not
by this paragraph: `tests/test_us_led_005_gl_designations.py` carries an
`-m isolation` case that reads a service's GL attributes across tenants under
the NOSUPERUSER probe role and requires row-level security to be the thing that
refuses.

────────────────────────────────────────────────────────────────────────────
ORDERING (🔒) AND THE FK DIRECTION
────────────────────────────────────────────────────────────────────────────
Depends on `ledger/0003`, so `ledger_accounts` exists — and exists already
under RLS FORCE (`ledger/0002`) — before anything points at it. The reverse
edge already exists (`ledger/0001` depends on `tenancy/0005` for its
`tenant_id` / `service_id` FKs), and the two do not form a cycle because
Django resolves dependencies per MIGRATION, not per app: 0001(ledger) →
0005(tenancy), 0006(tenancy) → 0003(ledger). `migrate` from an empty database
is the check that this is true rather than argued, and it is in the trailer.

Both columns are NULLABLE and `on_delete=PROTECT`. **The original reason has
been overtaken and is corrected here rather than left standing** (hard-won law
1): nullable was written because `storm_water` and `thermal_heat` had no
account in the finance-signed chart, and the PO closed OQ-115 on 2026-08-11 by
creating 4160/4170, so that reason is gone. Nullable is still right for two
reasons that outlive it — a tenant may CLEAR a mapping on the GL settings
screen (the same ruling: *"allow tenant user to override it"*), and a tenant
that does not sell a service is no longer seeded its revenue account at all, so
a row can legitimately exist with nothing mapped. BR-BIL-010's "required" is
enforced where it can be enforced honestly: at issue, where an unmapped line
refuses its whole bill rather than posting to a guessed bucket. PROTECT because
an account a service points at is an account IN USE, and IS-1 says a referenced
account deactivates but never deletes. These FKs are ADDITIONS to B2 §2's reviewed cross-module
interface set and are registered per r16 #7 "at DDL time" — this is that time.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0003_gl_designations"),
        ("tenancy", "0005_seed_subscription_plans"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantservice",
            name="base_revenue_account",
            field=models.ForeignKey(
                blank=True,
                db_column="base_revenue_account_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="services_billing_base_here",
                to="ledger.ledgeraccount",
            ),
        ),
        migrations.AddField(
            model_name="tenantservice",
            name="revenue_account",
            field=models.ForeignKey(
                blank=True,
                db_column="revenue_account_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="services_billing_usage_here",
                to="ledger.ledgeraccount",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-005@663369d (sources: 12-governance/02-decision-log.md 2026-08-11 "OQ-106 IS CLOSED" · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-010 · 04-docs/02-decisions/05-golden-tests.md line 74 ❄️ seed chart · 04-docs/02-decisions/02-database-design-brief.md r10 #2 and r16 #6/#7)
# generated: 2026-08-11 by Eng-Lead (W5 ledger GL-designation lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI — the GL mapping page is a Settings story in another lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: `migrate` from an EMPTY database and `makemigrations --check` — see the
#         report and the human-review ledger row
# exceptions: NO new RLS policy and no new db/rls_*.sql file — no table is
#         created and `tenant_services` is already ENABLE+FORCE under the signed
#         B2 §3 policy from 0003_rls_w0_policies; stated rather than left as a
#         silent absence, and backed by an -m isolation case · these columns
#         realise B2 r10 #2's `service_gl_map` as ATTRIBUTES rather than as a
#         separate ledger table, which is the PO's "a field, not a table"
#         ruling applied to the service half — an Eng-Lead reading of a PO
#         shape, flagged in the human-review ledger, NOT a PO-stated table
#         choice · both nullable — the ORIGINAL reason (`storm_water` and
#         `thermal_heat` had no account in the signed chart) was overtaken when
#         the PO closed OQ-115 on 2026-08-11, and the docstring is corrected
#         rather than left claiming it: nullable now carries a tenant CLEARING
#         a mapping and a service enabled with none seeded. BR-BIL-010's
#         "required" is still enforced at issue, where an unmapped line refuses
#         its bill rather than posting to a guessed bucket
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
