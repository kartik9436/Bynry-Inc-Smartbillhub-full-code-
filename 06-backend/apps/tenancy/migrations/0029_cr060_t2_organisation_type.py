# ── Trace ──────────────────────────────────────────────
# Change:   CR-060 T2 / C7 (12-governance/11-change-requests.md) — "Organisation
#           type — column, seed, settings field". T3 and T4 cannot start without
#           it; C8 and C9 are the only things that read it.
# Story:    US-TEN-005 (S8 Company profile)   Screens: S8
# Rules:    BR-TEN-1050 (MINTED with this change — the type, its three values,
#           its seeded default) · BR-LED-028 (the PO named the three customer
#           kinds: Utility · sub-metering company · HOA) ·
#           CLAUDE.md rule 1 (tenant scoping — `tenant_settings` is a
#           tenant-scoped table under RLS FORCE; this adds a column and touches
#           no policy)
# Tests:    06-backend/tests/test_cr060_t2_organisation_type.py
# ───────────────────────────────────────────────────────
"""tenancy 0029 — `tenant_settings.organisation_type`, seeded `utility`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-01 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md; not RATIFIED
without a recorded human sign-off.

WHAT THIS IS, IN ONE SENTENCE
------------------------------
One TEXT column saying whether this tenant is a **utility**, a **sub-metering
company** or an **HOA** — the fact the product has always named in its rules
and has never been able to read.

WHY IT IS A SETTING AND NOT A SIGNUP QUESTION
----------------------------------------------
CR-060 C7's own argument, kept because it is the reason the column is shaped
this way: *"A setting also has one advantage over a signup question that
matters here: every existing tenant can fix it in one click. Asked only at
signup, the answer would be missing for everyone already on the platform and
would need a backfill."*

WHY THE DEFAULT IS ON THE COLUMN AND NOT ONLY IN THE PROVISIONING SERVICE
-------------------------------------------------------------------------
**Hard-won law 4 — a template change never reaches a host that already has
data.** Seeding `utility` in `services.provision_tenant` reaches the NEXT
tenant and no existing one. `AddField` with a `default` writes that default
into every row that already exists, in this same migration, so C7's proof
reads *"Default is `utility` for a new tenant AND for an existing one"* rather
than *"for a new tenant"*.

Measured on the live development database, PostgreSQL 16.13, 2026-09-01:
**15 `tenant_settings` rows existed before this migration and all 15 read
`utility` after it.** Nothing else on any of those rows changed — the whole
`tenant_settings` md5 row digest was taken before and after with
`organisation_type` excluded from the projection, and it is identical.

The default is kept ON THE FIELD rather than dropped after the backfill
(Django's usual `preserve_default=False` habit) because it is a REAL default,
not a migration device: a `TenantSettings` row created by any path — the
provisioning service, the settings-family save that creates a missing row,
a test factory — must land on `utility` rather than on a NULL nobody reads.

WHY THERE IS NO CHECK CONSTRAINT
---------------------------------
It was considered and NOT taken. Every comparable column on this table —
`accounting_method`, `close_cadence`, `first_day_of_week`, `number_format`,
`date_format`, `time_format` — is a bare TEXT column validated in
`apps/tenancy/services.py` against a tuple in `apps/tenancy/models.py`. One
convention on a table is worth more than a stronger guard on one column of it,
and the reader falls back rather than erroring on an unrecognised value, which
is CR-060 C8's stated proof (*"an unknown value falls back rather than
erroring"*). A CHECK would turn that stated fallback into a 500 on a row a
future migration or an import wrote.

WHAT THIS MIGRATION DELIBERATELY DOES NOT DO
---------------------------------------------
**IT DOES NOT RETIRE `accounting_method`.** CR-060 §9's table asks for the two
to travel together (C6 rides C7's migration), and CR-060 §0c FINDING 1 is the
reason they must not here: that column is NOT dead data at 2.123.0 —
`apps/tenancy/selectors.py:470` reads it for the `fiscal_billing`
onboarding-checklist item while `services.py:879` deliberately never seeds it,
so the item can never complete for any tenant provisioned since CR-008 and no
screen can set it. Dropping the column in this migration would delete a column
something depends on and would close that defect by accident rather than by
decision. **C6 is not this task** — CR-060 §12 gives the defect its own row
(T0) and C6 has no task row at all — so the column stays, untouched, and the
finding is named here so the next lane does not read the §9 table alone and
take it out.

WHAT AN OPERATOR MUST KNOW BEFORE DEPLOYING THIS
-------------------------------------------------
`ALTER TABLE … ADD COLUMN … DEFAULT 'utility' NOT NULL` on PostgreSQL 11+ does
NOT rewrite the table: the default is stored in the catalog and existing rows
read it without being touched. It takes a brief ACCESS EXCLUSIVE lock to update
the catalog. `tenant_settings` holds one row per tenant — 15 on the development
database — so this is instantaneous at any size this product reaches.

**NO ROW IS UPDATED, DELETED OR RE-WRITTEN.** Hard rule 4 lists issued
invoices, invoice lines, payments and journal entries; `tenant_settings` is on
none of those lists, and nothing here touches a money table at all.
"""

from django.db import migrations, models

from apps.tenancy.models import ORGANISATION_TYPE_UTILITY


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("tenancy", "0028_oq1164_every_customer_document_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantsettings",
            name="organisation_type",
            field=models.TextField(default=ORGANISATION_TYPE_UTILITY),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060-T2@organisation-type (the authorities this slice was authored
#         from: 12-governance/11-change-requests.md — CR-060 §7 C7, §9's table
#         row for `tenant_settings`, §0c finding 1 and the T2 row in §12 ·
#         04-docs/05-modules/01-tenancy/02-business-rules.md — BR-TEN-1050,
#         minted with this change · 04-docs/05-modules/09-ledger/02-business-
#         rules.md BR-LED-028, which is where the three customer kinds are
#         named · apps/tenancy/models.py TenantSettings, read from the model)
# generated: 2026-09-01 by the CR-060 T2/T3/T4 lane
# checklist: A✔ B✔ C✔ D✔(PUT /settings/company carries the field) E✔(S8 Company profile) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: G16 partition coverage PASS before and after (`tenant_settings` is not in NFR-24's set; the run is recorded because a migration is a 🔒 sensitive path) · applied FORWARD and REVERSE against a REAL PostgreSQL 16.13 holding 15 tenant_settings rows; all 15 read `utility` forward, the column is gone in reverse, and the md5 digest over every other column is identical at both ends · proved RED first: the companion test asserts the seeded default and fails on this migration's parent, tenancy/0028
# exceptions: NO CHECK CONSTRAINT — the vocabulary is validated in the service
#         against `models.ORGANISATION_TYPES`, which is this table's own
#         convention for all six comparable columns, and a CHECK would turn
#         C8's ruled fallback-on-unknown into a database error ·
#         `accounting_method` IS NOT RETIRED HERE even though CR-060 §9 asks
#         for it in this migration: §0c finding 1 shows it has a live reader and
#         a latent defect underneath it, and C6 has no task row in §12 — see the
#         docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
