# ── Trace ──────────────────────────────────────────────
# Story:    CR-010 ("Part-10 confirmations" 10.0, PO 2026-08-17: "add them" —
#           the ratified two-level account-type tree)   Screens: S8 · S18
# Rules:    BR-CUS-067 (sub-types are a two-level tree under the platform
#           account_types; tenant-scoped, tenant-extensible, 12 seeded rows) ·
#           r5 #12 [D5] (tenant-defined, RLS — the RLS half landed in 0002 and
#           is untouched here) · CLAUDE.md rule 1
# ───────────────────────────────────────────────────────
"""customers 0011 — the CR-010 parent FK: `account_subtypes.account_type_id`.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-18 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

ONE nullable column, nothing else. The table itself has existed since 0001 and
carries RLS ENABLE+FORCE from 0002 (`account_subtypes` is in that migration's
table list), so no policy work belongs here — adding a column never detaches a
policy.

NULLABLE, DELIBERATELY. The models.py exceptions line reported for a week that
"nothing states whether a sub-type belongs to a type"; the PO answered on
2026-08-17 ("add them" — the tree as drawn). But the table has been WRITABLE
since W2 and a tenant may hold rows that predate the ruling; a NOT NULL with a
backfilled parent would be this migration INVENTING which of four types each
existing row belongs to. Nullable says "not yet answered" for old rows, and the
lookup handler requires a parent on every row created or edited from here on —
the same posture metering 0009 took for `premises.area_id`.

PROTECT, because the parent is a PLATFORM row (no tenant_id): deleting an
`account_types` row out from under any tenant's sub-types must refuse. The
platform card is read-only anyway (AccountTypeLookupHandler refuses every
write), so this is a second lock on a door that is already locked.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0010_br_ten_057_is_sample"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountsubtype",
            name="account_type",
            field=models.ForeignKey(
                blank=True,
                db_column="account_type_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="subtypes",
                to="customers.accounttype",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-010 "Part-10 confirmations" 10.0 (12-governance/02-decision-log.md
#         2026-08-17) + "the PO confirms the A-section seed sets" item 1
# generated: 2026-08-18 by the CR-010 account-subtypes/unit-types lane
# checklist: A✔ B✔ C✔(tests/test_cr010_subtypes_unit_types.py) D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: makemigrations --check clean · migrate from empty proven
# exceptions: nullable parent — see the docstring; pre-ruling rows keep NULL and the handler requires a parent on new/edited rows
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
