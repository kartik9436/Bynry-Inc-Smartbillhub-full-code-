# ── Trace ──────────────────────────────────────────────
# Change:   CR-008 ruling 9 (PO 2026-08-17, *"make it separate"*) — adjustment
#           reasons get their own GL mapping section on Settings → Accounting.
#           Screens: SET-11 GL mapping (section 5) · S8 → Configure → Reference
#           data → Reason codes (the same rows, listed)
# Rules:    US-TEN-010 §5 (the column this list was specified with) ·
#           BR-BIL-069 / BR-BIL-010 (a money line names the account it lands in)
#           · BR-TEN-013 + B1 (the ledger validates the ledger's own row) ·
#           B11 F-3 (deferred FK: a uuid column, no cross-module constraint) ·
#           CLAUDE.md rule 1 (tenant scoping)
# ───────────────────────────────────────────────────────
"""tenancy 0014 — `reason_codes.default_gl_account_id`, nullable.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-17 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*), implementing the PO's CR-008 ruling 9 of
2026-08-17: *"9 **make it separate**"*, asked as *"should a 'billing error'
credit and a 'goodwill' credit be able to post to different accounts?"*.

────────────────────────────────────────────────────────────────────────────
WHY IT IS A UUID AND NOT A FOREIGN KEY
────────────────────────────────────────────────────────────────────────────
`ledger_accounts` is another module's table. B2 §2 makes cross-module FKs *the
reviewed interface set* — a list, not a thing a lane extends on its own — so
this follows the two columns that already point the same way and were built the
same way: `rating.taxes.liability_gl_account_id` and
`rating.charges.gl_account_id`, both plain `uuid` (B11 F-3).

The validation is not weaker for it; it is stronger. An FK proves the row
EXISTS and never proves it is THIS TENANT's, which in a money path is the only
question that matters. `apps.tenancy.services.ReasonCodeLookupHandler` asks the
ledger through `seams.ledger_account_is_live`, which answers ownership AND
liveness in one read — so a deactivated account (IS-1) is refused too, and a
crafted id belonging to another utility's chart is refused by the same branch.

────────────────────────────────────────────────────────────────────────────
RLS: NOTHING NEW, AND THAT IS CHECKED RATHER THAN ASSUMED
────────────────────────────────────────────────────────────────────────────
**No table is created — this adds ONE COLUMN.** `reason_codes` is already
ENABLE + FORCE under `reason_codes_tenant_isolation` from
`db/rls_tenancy_w0.sql`, applied by `0003_rls_w0_policies`. The policy gates the
ROW, so a column on a gated row is gated; writing a second policy here would
shadow the signed original. Same posture, and deliberately the same words, as
`0011_uom_service_scope` and `0006_service_gl_attributes`.

The claim is backed by the sweep and not by this paragraph:
`tests/test_tenant_isolation.py` walks every tenant-scoped table rather than a
hand-kept list. PostgreSQL only — the sqlite test database cannot exercise RLS
and says so.

────────────────────────────────────────────────────────────────────────────
NOTHING POSTS DIFFERENTLY BECAUSE OF THIS MIGRATION
────────────────────────────────────────────────────────────────────────────
Stated because a column named `default_gl_account_id` reads like a posting
change and is not one: no writer in `apps/ledger` or `apps/billing` reads this
column today. It is CONFIGURATION a utility can now record and see — the
consuming half is a separate act, on a separate review, and pretending
otherwise would be the "comment claiming a guarantee" of hard-won law 1.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0013_cr006_routes_cycles"),
    ]

    operations = [
        migrations.AddField(
            model_name="reasoncode",
            name="default_gl_account_id",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
