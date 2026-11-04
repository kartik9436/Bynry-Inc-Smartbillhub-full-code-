"""tenancy 0005 — seed the PLATFORM subscription-plan catalog (Starter/Growth/Scale).
HUMAN-OWNED (migration ordering is a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-10 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), transcribing RATIFIED
commercial values only (sources cited per row below). Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

WHY IT EXISTS — this was the last hard deploy blocker (09-infra/02 §10.3).
`subscription_plans` was created empty by migration 0001 and nothing ever filled
it. `apps.tenancy.services._validate_signup` looks the requested plan up in that
table and appends `signup.plan_unknown` when it is absent, so on a fresh
production database **every signup failed and `GET /api/public/pricing-plans`
returned `[]`** — no customer, not even the internal demo tenant, could self-serve
onto the environment. The only writer in the repo was
`seed_demo._ensure_plans()`, which creates ONE plan and refuses to run under
production settings by design (it is a demo-fixture command, not a bootstrap).

WHY A MIGRATION, AND WHY THIS APP. These are PLATFORM rows, not tenant rows:
`subscription_plans` is RLS-EXEMPT per B2 §3 (the same exemption `tenants` and
`services` carry), identical for every tenant, and it must already exist before
the FIRST signup — there is no tenant, no session and no actor at that moment to
route a write through a service. Migration 0001 seeds the 10-service platform
catalog for exactly these reasons; this is the same posture for the same class
of data, in the app that owns the table (B2 module map). CLAUDE.md rule 1 is
satisfied by the exemption, not bypassed: no tenant table is touched, so no
`app.tenant_id` is required or set.

⚠ FOR THE REVIEWER — four things worth your eyes:

1. EVERY NUMBER IS QUOTED, NONE IS INVENTED. The three SKUs, their monthly
   prices and their connection bands are ratified in four places that agree:
     · A10 `04-docs/01-spec/10-mock-vs-real.md` — lists them under **"Real
       business constants (preserve)"**: "package prices Starter $1,000 /
       Growth $5,000 / Scale $8,000 per month; size tiers ≤300 / 300–1,000 /
       1,000–3,000 accounts".
     · A13 `04-docs/01-spec/13-copy-and-microcopy.md` — "Addendum — Final
       pricing-card feature bullets (2026-08-07)": "Starter — $1,000/mo — up to
       300 connections", "Growth — $5,000/mo — 300–1,000 connections",
       "Scale — $8,000/mo — 1,000–3,000 connections".
     · A1 `04-docs/01-spec/01-screen-inventory.md` §S112 — the wizard's plan
       cards, with Growth pre-selected.
     · B2 `04-docs/02-decisions/02-database-design-brief.md` — the
       `plans.price_month` column comment: "1000 / 5000 / 8000 (real constants)".
   A previous lane recorded that "starter/scale have no signed values"
   (seed_demo.py). Re-checked against the four sources above: they do, and have
   since the A13 addendum of 2026-08-07. Growth's row is unchanged from the one
   `seed_demo._ensure_plans()` and `tests/test_us_ten_helpers.growth_plan`
   already used, so nothing an existing database holds is contradicted.

2. THE ONE FIGURE NOBODY WROTE DOWN, AND WHAT WAS DONE WITH IT. Starter's band
   is stated only as an upper bound — "up to 300", "Under 300", "≤300" — so
   `min_accounts` has no quoted value. It is set to **0**, which is what "up to
   300" means and the only value that leaves no gap below the band; it is NOT a
   price and it is NOT enforced anywhere. BR-TEN-002 (CONFIRMED): "Connection
   counts are commercial tiers, NEVER enforced technically" — `max_accounts`
   carries that warning in the model itself, and `selectors.pricing_plans()`
   repeats it ("ADVISORY, never enforced"). Recorded here rather than passed
   over in silence; if the PO wants 1, it is a one-line follow-up migration.

3. WHAT THIS MIGRATION WILL NOT DO. It INSERTS missing codes and never UPDATES
   an existing row. A price already in a live catalog is a commercial fact that
   a schema migration has no business rewriting — if a figure here ever
   disagrees with a deployed row, that is a conversation, not a silent
   overwrite. Consequence: the migration is idempotent (BR-TEN-010 posture) and
   safe on the databases that already hold `growth` from `seed_demo`.

4. THE REVERSE DELIBERATELY REMOVES NOTHING, and that is the safe answer rather
   than the tidy one. `subscriptions.plan_id` is `on_delete=PROTECT`, so a
   blanket delete would either raise mid-rollback or take away the plan a live
   tenant is subscribed to. Finding out which rows are referenced is not a
   one-liner either: `subscriptions` is RLS + FORCE (db/rls_tenancy_w0.sql), so
   the question can only be asked one tenant at a time under
   `app.tenant_id` — a per-tenant walk inside a rollback, to delete platform
   reference data that is inert when nothing points at it. The rows stay. This
   is the posture the RLS migrations already take with `reverse_sql=noop`
   ("never rolled back silently"), and re-applying the migration is a no-op
   because the seed only inserts what is missing (note 3).

No RLS work: the table is platform, exempt, and unpolicied by design (see the
inline exemption note in db/rls_tenancy_w0.sql). Runs identically on sqlite and
Postgres — there is no vendor-specific statement here.
"""

import logging
from decimal import Decimal

from django.db import migrations

logger = logging.getLogger("smartbillhub.tenancy")

# The ratified catalog. Sources per reviewer note 1; money as Decimal, never
# float (CLAUDE.md rule 2 — the column is NUMERIC(18,6) + CHAR(3)).
#   code, name, price_month, currency, min_accounts, max_accounts
SUBSCRIPTION_PLANS = (
    ("starter", "Starter", Decimal("1000"), "USD", 0, 300),  # A10/A13: $1,000, ≤300
    ("growth", "Growth", Decimal("5000"), "USD", 300, 1000),  # A10/A13: $5,000, 300–1,000
    ("scale", "Scale", Decimal("8000"), "USD", 1000, 3000),  # A10/A13: $8,000, 1,000–3,000
)


def seed_subscription_plans(apps, schema_editor):
    """Insert the missing SKUs. Existing codes are left exactly as they are
    (reviewer note 3)."""
    SubscriptionPlan = apps.get_model("tenancy", "SubscriptionPlan")
    for code, name, price_month, currency, min_accounts, max_accounts in SUBSCRIPTION_PLANS:
        _row, created = SubscriptionPlan.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "price_month": price_month,
                "currency": currency,
                "min_accounts": min_accounts,
                "max_accounts": max_accounts,
            },
        )
        if not created:
            logger.info("subscription plan %s already present — left untouched", code)


def keep_subscription_plans(apps, schema_editor):
    """Reverse: the catalog stays (reviewer note 4). Not a forgotten reverse —
    a deliberate one, so `migrate tenancy 0004` cannot pull a plan out from
    under a live subscription."""
    logger.info(
        "reverse of tenancy 0005: subscription_plans left in place on purpose "
        "(PROTECTed by subscriptions; re-applying the migration is a no-op)"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0004_settings_families_logo_and_hosted_lists"),
    ]

    operations = [
        migrations.RunPython(seed_subscription_plans, keep_subscription_plans),
    ]
