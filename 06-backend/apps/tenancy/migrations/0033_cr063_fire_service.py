# ── Trace ──────────────────────────────────────────────
# Change:   CR-063 task A1 — Fire becomes the ELEVENTH utility service, because
#           a real utility is being onboarded and it sells fire protection.
#           PO 2026-09-02, verbatim: *"We will need Fire as utility Service -
#           Capacity based - this will behave exactly like trash"*, and the
#           clause that sets the priority: *"we have to do it ; curenlty we need
#           it for one of the customer we want to go live"*.
# Rules:    BR-RAT-024 (CONFIRMED-AS-AMENDED 2026-09-02 — the catalogue is
#           ELEVEN services, `fire` APPENDED at position 11, nothing renumbered)
#           · BR-TEN-012 (upsert by code) · BR-TEN-071 (seed data never deletes)
#           · BR-TEN-072 (a rename is forbidden in seed data)
# Tests:    06-backend/tests/test_cr063_fire_service.py
# ───────────────────────────────────────────────────────
"""tenancy 0033 — one row: ``("fire", "Fire")``, sort 11.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-02 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md; not RATIFIED
without a recorded human sign-off.

⚠ **INSERT-IF-ABSENT ONLY, AND THAT IS A HARDER RULE HERE THAN IT WAS LAST
WEEK.** Every previous catalogue change in this repo was written under the PO's
beta posture — *"I will delete the DB and relaunch"* — and this one is NOT.
`CR-063` exists because **a live customer is being onboarded on it**, so an
additive row is safe and anything that rewrites or re-scopes an existing row is
not. `update_or_create` over the whole list would silently reset a name or a
sort that a tenant's own operator had changed, so this migration touches exactly
one code and reads the other ten not at all.

⚠ **APPENDED AT SORT 11 — NOTHING IS RENUMBERED, AND THE SEED ORDER IS ITSELF
THE RULING.** `0001_initial.SERVICE_SEED` numbers electric 1 … battery 10 and
`BR-RAT-024` names that order as law. Re-deriving the sort from a rewritten list
would rewrite ten rows to change one, which is the exact act the paragraph above
refuses. **11 is a literal here for that reason**, and a test pins it against
`SERVICE_SEED`'s length so the day somebody INSERTS a service rather than
appending one the run goes red instead of the numbers going quiet.

⚠ **THE MIGRATION IS THE SMALLER HALF OF MAKING FIRE EXIST.** The catalogue row
is what the API serves; it is NOT what a clerk sees. `SignupWizard.tsx` and
`ratingShared.tsx` type the service list out BY HAND, so this row alone gives a
product where Fire is in the database, served over the wire, green on `tsc` and
on every test — **and absent from the sign-up screen.** That is CLAUDE.md
hard-won law 2 (*built is not wired*) and it is the shape of four defects in one
day on this project. `SignupWizard.test.tsx` asserts ELEVEN for exactly that
reason.

REVERSIBILITY
--------------
The reverse deletes ONLY `fire`, and only the platform catalogue row. It does
not touch `tenant_services`: `BR-TEN-071` says seed data never deletes from a
tenant that already has it, and a utility that has begun billing fire has issued
invoices that hard rule 4 makes immutable. **The real point of no return is that
customer's first issued fire bill, not this migration** (`CR-063` §8).
"""

from django.db import migrations

#: The eleventh service. A list of one, shaped like `SERVICE_SEED`, so a twelfth
#: can be appended without re-reading this file's argument.
FIRE_SEED = [("fire", "Fire")]

#: Position 11 in `BR-RAT-024`'s ruled order — see the docstring for why this is
#: a literal and not `len(SERVICE_SEED) + 1`.
FIRE_SORT = 11


def seed_fire(apps_registry, schema_editor):
    """Insert `fire` if it is absent. Never UPDATE — see the docstring."""
    service_model = apps_registry.get_model("tenancy", "Service")
    for code, name in FIRE_SEED:
        service_model.objects.get_or_create(
            code=code,
            defaults={"name": name, "sort": FIRE_SORT, "active": True},
        )


def unseed_fire(apps_registry, schema_editor):
    service_model = apps_registry.get_model("tenancy", "Service")
    service_model.objects.filter(code__in=[code for code, _ in FIRE_SEED]).delete()


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("tenancy", "0032_br_ten_1180_drop_metered"),
    ]

    operations = [
        migrations.RunPython(seed_fire, unseed_fire),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-063 group A task A1
# generated: 2026-09-02 by the CR-063 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: applied FORWARD and REVERSE against a REAL PostgreSQL 16 (CLAUDE.md law 14)
# exceptions: `get_or_create`, never `update_or_create` — a live customer is
#         being onboarded on this catalogue, so the beta "delete the DB and
#         relaunch" posture every earlier catalogue change was written under
#         does not hold here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
