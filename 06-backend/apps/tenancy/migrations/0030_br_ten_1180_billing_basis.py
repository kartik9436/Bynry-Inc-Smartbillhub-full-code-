# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2409 (2026-09-01, PO) — "everything is metered that is not
#           curent even if utility service is not started". Two faults: the
#           column was never named at signup, and it is a BOOLEAN where the
#           product has THREE pricing types. This closes the second, which
#           DEF-2409's own prevention line calls "the blocker".
#           DEF-3230 (2026-09-02) — seven of the ten services also ship a unit
#           that cannot produce a bill; the seed map is fixed in the same commit.
# Rules:    BR-TEN-1180 (MINTED with this change — a service declares ONE of
#           three billing bases) · SUPERSEDES BR-RAT-081's two-state declaration
#           (PO 2026-08-20) · BR-RAT-015 (sewer is a percentage of the water
#           usage charge — the case that proves two values were not enough) ·
#           BR-RAT-090 (an unmetered service's quantity is a COUNT of its assets
#           — what the `capacity` value means) ·
#           CLAUDE.md rule 1 (tenant scoping — `tenant_services` is tenant-scoped
#           under RLS FORCE; this adds and drops a column and touches no policy)
# Tests:    06-backend/tests/test_br_ten_1180_billing_basis.py
# ───────────────────────────────────────────────────────
"""tenancy 0030 — `tenant_services.billing_basis` replaces `metered`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-02 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md; not RATIFIED
without a recorded human sign-off.

WHAT THIS IS, IN ONE SENTENCE
------------------------------
One TEXT column saying whether a service is **metered**, a **share** of another
service's money, or **capacity**-based — replacing a boolean that could say only
two of those three things.

⚠ **THIS MIGRATION ADDS THE COLUMN AND DOES NOTHING ELSE — THE BACKFILL IS
`0031` AND THE DROP OF `metered` IS `0032`, AND SPLITTING THEM IS NOT TIDINESS.**

The first draft did all three in one atomic migration: `AddField` → `RunPython`
→ `RemoveField`. **It passed the whole test suite.** On a real PostgreSQL 16.13
with three rows planted in `tenant_services` it failed:

    django.db.utils.OperationalError: cannot ALTER TABLE "tenant_services"
    because it has pending trigger events

`tenant_services` carries FOREIGN KEYs declared `DEFERRABLE INITIALLY DEFERRED`
(tenant, service, three UoMs, two ledger accounts). Updating those rows queues
deferred trigger events that are not flushed until COMMIT, and PostgreSQL refuses
to ALTER a table while any are outstanding. **A migration that writes rows and
then alters the same table cannot work on PostgreSQL, in either direction** —
and `config/settings/test.py` hardcodes in-memory SQLite, which has no such
state, so the suite is blind to it (CLAUDE.md law 14).

⚠ **AND THE FIRST ATTEMPT TO PROVE IT REPORTED "Applying… OK", WHICH IS THE MORE
USEFUL HALF OF THIS NOTE.** The proof script's planting SQL was refused — it
named a `tenants.status` column that does not exist — `psql` was not run with
`ON_ERROR_STOP`, and the migration therefore ran over **zero rows**: no writes,
no pending triggers, green. **A green run over an empty table is not evidence
about a backfill.** The proof now asserts the planted row count BEFORE it
migrates and refuses rather than passing.

**THE RULE THE SPLIT ENCODES:** a migration is EITHER schema or data, never both,
on any table whose rows it touches. `0030` adds, `0031` fills, `0032` drops.

WHY A BOOLEAN COULD NOT CARRY IT, AND SEWER IS THE PROOF
---------------------------------------------------------
`metered=False` MEANS *priced from a COUNT of the unit's assets* — `BR-RAT-090`,
option A, which `resolution.counted_quantity` implements (3 carts × $15.00 =
$45.00). Sewer reads no register either, so on the boolean it had to be `False`.
But a sewer connection **has no assets**, so the count is 0, and sewer is in fact
a percentage of the water usage charge (`BR-RAT-015`). **Neither value of the
boolean was true for it.** Flipping it to unmetered to make the Settings screen
honest would have told the engine to price sewer by counting carts.

The backfill that follows from that — including `sewer → 'share'` keyed on the
SERVICE CODE rather than on the old boolean, because sewer was wrong in both
directions — lives in `0031` with its own reasoning.

WHY NO CHECK CONSTRAINT
------------------------
The vocabulary is validated in the service against `models.BILLING_BASES`, which
is this table's own convention — `organisation_type`, `accounting_method`,
`close_cadence`, `first_day_of_week` and `number_format` are every one a TEXT
column checked in Python. A CHECK here would be a second, weaker statement of the
same rule in a place whose error message cannot reach a screen.
"""

from django.db import migrations, models

# ⚠ The value is RE-DECLARED here rather than imported from `apps.tenancy.
# models`. A migration must keep running when the model moves on — importing the
# live constant would make this file's behaviour change under it, which is the
# opposite of what a migration is for.
BILLING_BASIS_METERED = "metered"


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        # `0029` is the real leaf. ⚠ `0023` and `0024` are deliberately NOT
        # taken — `0025` already depends on `0022`, so a second child of `0022`
        # would make two leaves and Django would demand a merge migration.
        ("tenancy", "0029_cr060_t2_organisation_type"),
    ]

    operations = [
        # SCHEMA ONLY. The backfill is `0031` and the drop of `metered` is
        # `0032`; putting either of them here reproduces `cannot ALTER TABLE …
        # because it has pending trigger events` on PostgreSQL while passing
        # every test on SQLite. The docstring above is the measurement.
        migrations.AddField(
            model_name="tenantservice",
            name="billing_basis",
            field=models.TextField(default=BILLING_BASIS_METERED),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2409@billing-basis (the authorities this slice was authored from:
#         12-governance/10-defect-log.csv — the DEF-2409 row, whose prevention
#         line names the vocabulary question as the blocker and says it is NOT to
#         be resolved by choosing · 12-governance/02-decision-log.md — the PO's
#         2026-09-02 ruling and its ten-row table ·
#         04-docs/05-modules/01-tenancy/02-business-rules.md — BR-TEN-1180,
#         minted with this change · 04-docs/05-modules/06-rating/02-business-
#         rules.md — BR-RAT-081, stamped SUPERSEDED at its own sentence, and
#         BR-RAT-015/BR-RAT-090, which are what the three values MEAN ·
#         apps/tenancy/models.py TenantService, read from the model)
# generated: 2026-09-02 by the billing-basis lane (DEF-2409)
# checklist: A✔ B✔ C✔ D✔(PATCH /settings/services/<code> carries billing_basis) E=deferred(the S8 control is a sibling lane's, built against the same contract) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: applied FORWARD and REVERSE against a REAL PostgreSQL 16.13 as part of
#         the 0030→0031→0032 sequence, over three planted rows (water
#         metered=true, trash metered=false, sewer metered=true) with the planted
#         count ASSERTED before the run · the single-migration form of this change
#         was measured FAILING on the same database with `cannot ALTER TABLE
#         "tenant_services" because it has pending trigger events`, which is why
#         there are three migrations and not one · proved RED first: the companion
#         test reports "7 of 10 services are not seeded the way the PO signed
#         them" on the pre-change map
# exceptions: NO CHECK CONSTRAINT — the vocabulary is validated in the service
#         against `models.BILLING_BASES`, this table's own convention for all
#         six comparable columns · THE REVERSE IS LOSSY and says so in its own
#         docstring rather than pretending otherwise
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
