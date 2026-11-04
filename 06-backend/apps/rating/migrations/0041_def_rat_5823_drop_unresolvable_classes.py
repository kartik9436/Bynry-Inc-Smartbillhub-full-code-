# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-5823 — `rating/0039` restored three plans' customer classes
#          from snapshots whose `account_type_id` no longer resolves, so the
#          repair put back a class that points at nothing. Its visible faces are
#          `DEF-RAT-5822`: the raw 36-character UUID renders as the plan's class
#          chip (B14 rule 31), and `PlanWizard.addableCharges` DROPS an
#          unresolved id, switching that plan's whole class narrowing off.
# Cause:   `customers/0054` fanned `account_types` out per tenant and repointed
#          `Account`, `AccountSubtype` and `ServiceRequest` — it did not list
#          `rate_plans`, which held a plain `UUIDField` with NO foreign key, so
#          nothing refused and nothing was repointed.
# Rules:   CLAUDE.md hard rule 1 (never touch a tenant table without
#          `app.tenant_id` set) · `BR-MET-151` clause 3 (a name is not proof) ·
#          B14 rule 31 (no database id is ever the visible value of a field) ·
#          CLAUDE.md hard-won law 7 (ask what makes a check pass WRONGLY) ·
#          CLAUDE.md hard-won law 14 (the suite's sqlite cannot express this) ·
#          CLAUDE.md 🔒 migration ordering
# Tests:   06-backend/tests/test_def_rat_5823_unresolvable_classes_pg.py
# ───────────────────────────────────────────────────────
"""rating 0041 — an `account_type_ids` entry that resolves to nothing is
REMOVED, and nothing is invented to replace it.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-19 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md.

════════════════════════════════════════════════════════════════════════════
WHAT WAS ACTUALLY WRONG, AND IT IS NOT `0039`
════════════════════════════════════════════════════════════════════════════
`0039` is the messenger. It read `plan_versions.snapshot`, found exactly the
three plans that had stated a class, and wrote exactly those three values —
its arithmetic and its docstring's count are both correct. **The values were
already dangling before it ran**, and they were dangling because of this:

`customers/0054` (2026-09-17 16:15:26 on the beta) turned `account_types` from
a PLATFORM table into a per-tenant one. It cloned every platform row once per
tenant **keyed on `code`**, repointed every referencing row to its own tenant's
clone, and then deleted the platform rows. Its referencing list is

    REFERENCING = ("Account", "AccountSubtype", "ServiceRequest")

**`rate_plans` is not in it.** `rate_plans.account_type_id` was a bare
`models.UUIDField(null=True)` with **no foreign key at all**, so deleting the
platform rows out from under it raised nothing, `0054`'s own "stranded"
refusal could not see it, and the column was left pointing at rows that no
longer exist. `0038` then moved that already-dead value into
`account_type_ids`, and `0039` restored it from the snapshots. Three
migrations carried a corpse forward and every one of them was internally
correct.

**MEASURED ON THE BETA, 2026-09-19, inside a tenant context:** three plans —
`SCW-RES`, `SCW-COM`, `SCW-IND` — each hold exactly one id, and **zero of the
three resolve against the nine `account_types` rows brazosbend now has**. The
stored ids all carry the prefix `01a0afa2-` (the deleted platform generation);
every live row carries `01a0b026-` (8) or `01a0b7cc-` (1). The overlap is
empty. Every other holder was checked and is CLEAN: `accounts` 0 dangling,
`account_subtypes` 0, `service_requests` 0, `plan_deposit_rules` 0, `tariffs`
0 of 54 rows (none carries a type at all). `rate_plans.account_type_ids` is
the only survivor of `0054`'s miss.

════════════════════════════════════════════════════════════════════════════
⚠ THE SECOND UNRECOVERABLE CASE — `0039`'s *"Full recovery there"* IS NOW FALSE
════════════════════════════════════════════════════════════════════════════
`0039`'s docstring names ONE unrecoverable case — *"A DRAFT PLAN THAT NAMED A
CLASS AND HAS NEVER FILED A VERSION CANNOT BE RECOVERED"* — and says of the
snapshot route *"Full recovery there."* **That sentence is superseded by this
file.** There is a SECOND unrecoverable case it did not anticipate and which
is the one this estate actually has:

    **A FILED SNAPSHOT WHOSE `account_type_id` NO LONGER RESOLVES.**

The snapshot is intact, append-only and exactly as `BR-RAT-111` promises — and
it is still unrecoverable, because what it preserved is a POINTER and the row
it pointed at was deleted by a migration in another module. A snapshot
preserves the value; it cannot preserve the world the value referred to.

⚠ **`0039` IS NOT EDITED AND THIS IS DELIBERATE, FOR TWO REASONS.** The first
is `0039`'s own: committed migrations are append-only and repairing forward is
the honest record. The second is stronger and is specific to this estate —
**`0039` HAS ALREADY RUN HERE.** `django_migrations` carries
`0039_def_rat_5800_class_backfill_under_rls`, applied 2026-09-19 04:59:17,
while the file on disk is `0039_def_rat_5799_…`; the authoring lane renumbered
the defect id at push time (`DEF-RAT-5800` had been taken by a sibling for an
unrelated front-end row) and the database kept the name it ran under. Editing a
migration that has already executed is how history stops being a record.

════════════════════════════════════════════════════════════════════════════
WHY THE ID IS NOT RESOLVED, AND WHAT IS HANDED TO A HUMAN INSTEAD
════════════════════════════════════════════════════════════════════════════
The snapshot carries **only** `account_type_id` and a NULL
`account_subtype_id`; `eligibility` is `{}`. No code, no name — checked key by
key across all 8 `plan_versions` rows. So there is nothing IN THE SNAPSHOT to
resolve from.

⚠ **AND THE PLAN CODE IS NOT EVIDENCE.** `SCW-RES`, `SCW-COM` and `SCW-IND`
read like residential, commercial and industrial, and that is precisely the
inference `BR-MET-151` clause 3 forbids in its own domain — *"Whitfield
Rentals LLC is not proof of a landlord"*. A plan code is a string a clerk
typed.

⚠ **A RECOVERY ROUTE DOES EXIST ON THIS ESTATE, AND IT IS DELIBERATELY NOT
AUTOMATED HERE.** Because `0054`'s repoint is code-preserving by construction,
what an old platform id MEANT can be read back out of the rows it repointed:
76 accounts whose creation audit payload records one of the three ids today
carry exactly one current type each, unanimously —

    01a0afa2-8ba0-7452-b43e-9d5154a8eedd  ->  residential   (63 accounts)
    01a0afa2-8ba2-7dee-9ddb-313f91788323  ->  commercial    (12 accounts)
    01a0afa2-8ba3-747c-bab6-2197d9d64126  ->  industrial     (1 account)

— all 76 created before `0054` ran, and no account's `account_type_id` was
ever changed afterwards (0 type-changing `account.updated` rows). **This
migration does not use it, for two reasons that both matter.** It rests on
`audit_log`, which is PRUNED on a retention schedule, so a migration built on
it would silently do nothing — or something different — on the next host and
would be a check incapable of failing visibly. And restoring a customer class
changes which charge codes a clerk is offered, which is a judgment the PO
makes once, not one a migration makes quietly on every estate. The mapping is
written into the decision log and put to the PO in plain English instead.

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE DOES — IT ONLY EVER SHRINKS A LIST
════════════════════════════════════════════════════════════════════════════
Per tenant, under that tenant's `app.tenant_id`: read the ids `account_types`
actually holds, then drop from every plan's `account_type_ids` any entry not
among them, preserving the order of the entries that survive.

* **It never writes an id.** The only values it can produce are values already
  present, so it cannot invent a class and cannot put a new database id on a
  screen.
* **A plan left with nothing keeps `[]`,** which under `DEF-RAT-5768` means
  EVERY class. ⚠ **That is WRONG TOO and is not pretended otherwise** — those
  three plans named ONE class. It is not a REGRESSION: an unresolved id was
  already read as *names none* by every consumer (`addableCharges` drops it and
  `classCodes.size === 0` turns narrowing off), so behaviour is unchanged and
  what changes is that the wrongness becomes honest, visible, and legal on
  screen. The three plans go back to a human to re-state, by name.
* **A plan whose ids all resolve is not touched at all** — no save, no
  `updated_at` move.
* **It is idempotent.** A second run finds nothing to drop.
* **It is general, not estate-specific.** It hardcodes no id and no tenant; it
  asks the database what resolves. It therefore also repairs a host where
  `0039` has not yet run, because it runs AFTER `0039` in the graph.

`reverse` is a deliberate no-op: putting a dangling id BACK would be
re-applying the defect, and there is nothing to put it back FROM.

════════════════════════════════════════════════════════════════════════════
WHAT WOULD MAKE THE PROOF PASS WRONGLY — asked first, per hard-won law 7
════════════════════════════════════════════════════════════════════════════
*"No plan holds a dangling id afterwards"* is true of a migration that empties
**every** list, and true of a plan that had no ids to begin with. So the test
beside this file does not assert an absence. It asserts that a RESOLVABLE id
SURVIVES — alone, and mixed in a list beside a dangling one, where only the
dangling entry may go — and that a plan whose list is already clean is not
written at all. The sqlite suite cannot see any of it (hard-won law 14):
`account_types` is RLS `FORCE`-scoped on PostgreSQL and not on sqlite, so the
proof is PostgreSQL-only and says so in its marker.
"""

from django.db import migrations

#: `db/001_tenant_context_default.sql`'s nil UUID — "no tenant", which matches
#: no row. `0039` and `customers/0054` reset the GUC to the same value, and
#: `assets/0003` records why it is not `''`: `set_config(..., false)` is SESSION
#: level and outlives the migration, and an empty string makes a later `::uuid`
#: cast raise. A real uuid matching no row keeps deny-by-default intact.
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _tenant_ids(apps):
    """`tenants` is an RLS-exempt platform table, so it enumerates with no
    context — the same door `0039` and `customers/0054` use."""
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _enter_tenant(connection, tenant_id):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _leave_tenant(connection):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NO_TENANT])


def resolvable(stated, known) -> list:
    """The whole rule, as a pure function so it can be read and tested alone.

    `stated` is what the column holds, `known` the ids `account_types` actually
    has for this tenant, as strings. Order is preserved; anything that is not a
    known id — a dangling uuid, a duplicate of one, `None`, a stray number — is
    dropped. A non-list (a NULL column read through an older process) reads as
    empty, which is what `0038` says NULL means.
    """
    if not isinstance(stated, list):
        return []
    return [entry for entry in stated if isinstance(entry, str) and entry in known]


def _drop_unresolvable(apps, schema_editor):
    RatePlan = apps.get_model("rating", "RatePlan")
    AccountType = apps.get_model("customers", "AccountType")
    connection = schema_editor.connection

    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        # ⚠ FILTERED BY `tenant_id` AS WELL AS BY THE GUC, and the belt is not
        # redundant: sqlite has no RLS and the default suite runs there
        # (`customers/0054` keeps the same explicit filter for the same
        # reason). Without it, a plan on sqlite would be checked against every
        # tenant's vocabulary and a cross-tenant id would read as resolvable.
        known = {
            str(row_id)
            for row_id in AccountType.objects.filter(tenant_id=tenant_id).values_list(
                "id", flat=True
            )
        }
        for plan in RatePlan.objects.filter(tenant_id=tenant_id).iterator():
            stated = plan.account_type_ids
            kept = resolvable(stated, known)
            if kept == stated:
                continue  # already clean — not written, so `updated_at` stays put
            plan.account_type_ids = kept
            plan.save(update_fields=["account_type_ids"])
    _leave_tenant(connection)


def _noop(apps, schema_editor):
    """Reversing this does NOT put the dangling ids back. There is nothing to
    put them back from, and a value that resolves to nothing is the defect
    rather than a state worth restoring. `0039`'s reverse makes the same choice
    for the same reason."""


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0040_def_rat_5814_widen_discount_scope"),
        # `account_types` must already be per-tenant (`0054`) and RLS-scoped
        # (`0055`) before this reads it, or "what resolves for this tenant" is
        # not yet a question the table can answer.
        ("customers", "0055_rls_br_cus_1079_account_types"),
        ("tenancy", "0001_initial"),
    ]

    operations = [migrations.RunPython(_drop_unresolvable, _noop)]
