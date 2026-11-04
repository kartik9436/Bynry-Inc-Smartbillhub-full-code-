"""customers 0054 — `account_types` stops being a PLATFORM table and becomes the
utility's own, per the PO ruling of 2026-09-17.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒 path,
AI-authored under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*). Row in `12-governance/09-human-review-ledger.md`; not RATIFIED
without a sign-off.

THE RULING, VERBATIM
────────────────────
> *"utility can get their own account types"*

asked as a straight either/or — *do utilities get their own account types, or do
the seven stay the signed vocabulary and the screen simply stops pretending
they're editable?* — and answered the first way. **It supersedes `BR-CUS-094`'s
platform posture** (the PO's own earlier *"Expand the signed list to seven"*),
which made this the one customers table with no `tenant_id`, no RLS policy and a
GLOBAL `UniqueConstraint(Lower("code"))`. The seven stop being the vocabulary and
become the SEED.

WHAT THIS FILE DOES, IN ORDER, AND WHY THE ORDER IS THE WHOLE RISK
───────────────────────────────────────────────────────────────────
1. **DROP the global unique constraint FIRST.** Eight rows fanned out across N
   tenants means N copies of `residential`, and the constraint that is being
   replaced would refuse the second one. Dropping it before the data moves is
   not tidiness — the fan-out cannot run underneath it.
2. **ADD `tenant_id` NULLABLE and `sort_order`.** Nullable is a scaffold and
   lasts exactly as long as step 3: step 4 closes it.
3. **FAN OUT, THEN REPOINT, THEN DELETE — in that order, and the order is the
   safety property.** Every existing row is cloned once per tenant; every
   `account_type_id` on `accounts`, `account_subtypes` and `service_requests` is
   moved to **ITS OWN TENANT's clone**, matched by `tenant_id`; and only then are
   the old platform rows removed. ⚠ **GET THAT WRONG AND AN ACCOUNT SILENTLY
   REFERENCES ANOTHER UTILITY'S VOCABULARY** — so the repoint is keyed on the
   referencing row's `tenant_id` and never on the code alone, and step 3 REFUSES
   (raises, before deleting anything) if a single referencing row is left
   pointing at a platform id. A `ProtectedError` from the delete would say the
   same thing far less clearly, and on PostgreSQL it would poison the whole
   transaction (CLAUDE.md law 14).
4. **`tenant_id` NOT NULL**, exactly like `account_statuses` and
   `account_subtypes`: after step 3 there is no such thing as a platform row, and
   a row with no tenant would be a row no RLS policy can reach.
5. **ADD the per-tenant unique constraint.** Two utilities may now lawfully use
   one code for different things; that is what tenant scoping means.

**RLS is `customers.0055`, deliberately a separate file.** The policy cannot be
created before `tenant_id` exists and must not be created before the data moves —
`FORCE ROW LEVEL SECURITY` applies to the table owner too, so a policy in place
during step 3 would hide from this very migration the rows it is trying to clone.

`sort_order` answers the one question the ruling opens: **where does a row a
tenant ADDS go in a picker the PO drew?** The seeded seven carry `BR-CUS-094`'s
ruled order as 10..70, `government` (legacy) sits at 900 behind them, and a
tenant-added row is appended at `max + 10`. The S8 reference-data card still
sorts by `code` like every other card (IS-2); this column is the PICKER's order.

**Arithmetic, and it is the thing to check after this runs:** `8 rows × N
tenants` exist afterwards where 8 existed before (7 selectable + `government`
legacy — a fresh install with no tenants ends at 0 and the first tenant's
provisioning seeds its own eight), and **every `accounts.account_type_id`,
`account_subtypes.account_type_id` and `service_requests.account_type_id` still
resolves — to a row of its own tenant.**

**REVERSIBLE, and honestly so.** The reverse collapses the per-tenant rows back
onto one platform row per code, repointing every FK first. It keeps the FIRST
tenant's name for a code and DISCARDS any type a tenant added that no other
tenant has — which is data loss and is the reason this is documented rather than
silent. It exists so a failed deploy can roll back, not so the ruling can be
undone.
"""

from django.db import IntegrityError, migrations, models, transaction
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Lower

import django.db.models.deletion

#: `BR-CUS-094`'s ruled order — the order the PO drew the picker in. Mirrors
#: `apps.customers.models.AccountType.SEVEN_CATEGORIES`; a migration is frozen
#: history and never imports a live constant.
RULED_ORDER: tuple[str, ...] = (
    "residential",
    "commercial",
    "industrial",
    "agricultural",
    "institutional",
    "municipal",
    "builder_developer",
)
SORT_ORDER_STEP = 10
LEGACY_SORT_ORDER = 900

#: The three referencing tables. Each carries its own `tenant_id`, which is what
#: makes "repoint to ITS OWN tenant's row" a join rather than a guess.
REFERENCING = ("Account", "AccountSubtype", "ServiceRequest")

#: One opening for both refusals, so a reader who meets either one recognises it.
_REFUSAL = "customers.0054 refuses to delete the platform account_types rows: "

#: `db/001_tenant_context_default.sql`'s nil UUID — "no tenant", which matches no
#: row and is what the GUC is reset to between tenants.
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _enter_tenant(connection, tenant_id):
    """CLAUDE.md hard rule 1: never touch a tenant table without `app.tenant_id`
    set. All three referencing tables are RLS `FORCE`-scoped and the migration
    role is not a superuser, so an UPDATE with the GUC unset does not quietly
    match nothing — it RAISES. On sqlite there is no RLS and no `set_config`, so
    this is skipped honestly and the same ORM path runs."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _leave_tenant(connection):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NO_TENANT])


def _settle_deferred_constraints(connection):
    """⚠ **WITHOUT THIS THE NEXT `AlterField` DIES, AND THE MESSAGE NAMES NOTHING
    USEFUL:** `cannot ALTER TABLE "account_types" because it has pending trigger
    events`. Every FK in this schema is `DEFERRABLE INITIALLY DEFERRED`, so the
    repoint above leaves three tables' worth of constraint checks queued for
    COMMIT — and PostgreSQL refuses to alter a table with events pending against
    it. Firing them HERE also means a bad repoint is caught inside the RunPython
    that caused it rather than at the end of the migration."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def _sort_order_for(code: str) -> int:
    try:
        return (RULED_ORDER.index(code) + 1) * SORT_ORDER_STEP
    except ValueError:
        return LEGACY_SORT_ORDER


def fan_out_per_tenant(apps, schema_editor):
    """Clone each platform row once per tenant, repoint every FK at its own
    tenant's clone, then remove the platform rows — refusing if anything is
    left behind."""
    AccountType = apps.get_model("customers", "AccountType")
    Tenant = apps.get_model("tenancy", "Tenant")

    platform_rows = list(AccountType.objects.filter(tenant_id__isnull=True).order_by("code"))
    if not platform_rows:
        # A database that has never held a platform row — a brand-new install,
        # or a re-run. Nothing to fan out; provisioning seeds each tenant's own.
        return

    tenant_ids = list(Tenant.objects.values_list("id", flat=True))
    models_by_name = {name: apps.get_model("customers", name) for name in REFERENCING}
    connection = schema_editor.connection

    # ⚠ **NO PER-TENANT SAVEPOINT HERE, DELIBERATELY, AND IT IS THE OPPOSITE OF
    # `assets.0013`'s choice.** Law 14's savepoint exists for code that CATCHES a
    # database error and carries on to the next row; this catches nothing. A
    # fan-out that half-succeeded would leave some accounts on a platform row
    # that the next line deletes, so the correct outcome for one bad tenant is
    # that the WHOLE migration rolls back — which is what Django's
    # transaction-per-migration already gives us on PostgreSQL.
    try:
        for tenant_id in tenant_ids:
            _enter_tenant(connection, tenant_id)
            remap: dict[object, object] = {}
            for row in platform_rows:
                clone = AccountType.objects.create(
                    tenant_id=tenant_id,
                    code=row.code,
                    name=row.name,
                    is_system=row.is_system,
                    active=row.active,
                    legacy=row.legacy,
                    sort_order=_sort_order_for(row.code),
                )
                remap[row.id] = clone.id
            for model in models_by_name.values():
                for old_id, new_id in remap.items():
                    # ⚠ SCOPED BY `tenant_id`: this is the line that stops an
                    # account from ending up on another utility's vocabulary.
                    # Under RLS the GUC scopes it a second time; the explicit
                    # filter is kept because sqlite has no RLS and the test suite
                    # runs there (CLAUDE.md law 14's other half).
                    model.objects.filter(tenant_id=tenant_id, account_type_id=old_id).update(
                        account_type_id=new_id
                    )

        platform_ids = [row.id for row in platform_rows]
        stranded = []
        for name, model in models_by_name.items():
            # Counted per tenant, because RLS hides the other tenants' rows from
            # any single context — a count with no context would be 0 and would
            # read exactly like "nothing stranded".
            left = 0
            for tenant_id in tenant_ids:
                _enter_tenant(connection, tenant_id)
                left += model.objects.filter(
                    tenant_id=tenant_id, account_type_id__in=platform_ids
                ).count()
            if left:
                stranded.append(f"{name}={left}")
    finally:
        _leave_tenant(connection)
    if stranded:
        raise RuntimeError(
            _REFUSAL
            + ", ".join(stranded)
            + " row(s) still reference one. That means a referencing row carries a "
            "tenant_id no tenants row matches, so there was no clone to move it to. "
            "Fix the orphaned tenant_id and re-run — deleting now would either fail "
            "on the PROTECTed FK or, worse, leave the row pointing at nothing."
        )

    # ⚠ **THE COUNT ABOVE HAS A BLIND SPOT AND THIS IS THE CHECK THAT COVERS
    # IT — FOUND BY PROVING THE GUARD RED (CLAUDE.md law 7).** It walks the
    # tenants that EXIST, and the state it is written for is a referencing row
    # whose `tenant_id` matches no `tenants` row: there is no context to enter
    # for such a row, and RLS hides it from every other one, so the loop counts
    # ZERO over it and reads exactly like "nothing stranded". A probe that built
    # that state watched the delete fall through to the PROTECTed FK instead —
    # `IntegrityError: … is still referenced from table "accounts"`, which names
    # neither the cause nor the fix. **A declared blind spot with no second
    # check behind it is indistinguishable from an empty one.**
    #
    # ⚠ **THE SAVEPOINT IS NOT TIDINESS (law 14).** On PostgreSQL a failed
    # statement aborts the whole transaction, so without a nested `atomic()`
    # nothing after the `except` could run a single further query and the
    # migration would die on `InFailedSqlTransaction` rather than on the
    # sentence below.
    #
    # ⚠ **THE SETTLE IS INSIDE THE `try`, AND THAT IS THE WHOLE POINT.** Every
    # FK in this schema is `DEFERRABLE INITIALLY DEFERRED`, so the DELETE itself
    # succeeds and the violation surfaces only when the checks are fired. A
    # `try` around the delete alone catches nothing — the first draft of this
    # guard did exactly that, and the probe watched the raw `IntegrityError`
    # come out of the NEXT statement instead.
    try:
        with transaction.atomic():
            AccountType.objects.filter(tenant_id__isnull=True).delete()
            _settle_deferred_constraints(connection)
    except (IntegrityError, ProtectedError) as exc:
        raise RuntimeError(
            _REFUSAL + "the database refused the delete, which means a referencing row "
            "is invisible to the count above — its tenant_id matches no tenants row, so "
            "RLS hides it from every context there is. Find it with a superuser "
            "connection and give it a real tenant before re-running. "
            f"The database said: {exc}"
        ) from exc


def collapse_to_platform(apps, schema_editor):
    """Reverse: one platform row per code, every FK repointed first.

    ⚠ LOSSY BY CONSTRUCTION — a type ONE tenant added becomes every tenant's, and
    the first-seen tenant's `name` wins for a code two tenants spell differently.
    Documented rather than silent; it is a rollback path, not an undo of the
    ruling."""
    AccountType = apps.get_model("customers", "AccountType")
    models_by_name = {name: apps.get_model("customers", name) for name in REFERENCING}

    connection = schema_editor.connection
    platform_by_code: dict[str, object] = {}
    try:
        for row in list(AccountType.objects.order_by("tenant_id", "code")):
            key = row.code.lower()
            if key not in platform_by_code:
                platform_by_code[key] = AccountType.objects.create(
                    tenant_id=None,
                    code=row.code,
                    name=row.name,
                    is_system=row.is_system,
                    active=row.active,
                    legacy=row.legacy,
                    sort_order=row.sort_order,
                ).id
            _enter_tenant(connection, row.tenant_id)
            for model in models_by_name.values():
                model.objects.filter(account_type_id=row.id).update(
                    account_type_id=platform_by_code[key]
                )
            _leave_tenant(connection)
    finally:
        _leave_tenant(connection)
    AccountType.objects.filter(tenant_id__isnull=False).delete()
    _settle_deferred_constraints(connection)


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0053_br_cus_1077_move_in_jobs"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        # 1 · the global constraint goes FIRST — the fan-out cannot run under it.
        migrations.RemoveConstraint(
            model_name="accounttype",
            name="uq_account_types_code_ci",
        ),
        # 2 · the scaffold columns.
        migrations.AddField(
            model_name="accounttype",
            name="tenant",
            field=models.ForeignKey(
                db_column="tenant_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.tenant",
            ),
        ),
        migrations.AddField(
            model_name="accounttype",
            name="sort_order",
            field=models.IntegerField(default=LEGACY_SORT_ORDER),
        ),
        # 3 · fan out · repoint · delete, in that order.
        migrations.RunPython(fan_out_per_tenant, collapse_to_platform),
        # 4 · close the scaffold.
        migrations.AlterField(
            model_name="accounttype",
            name="tenant",
            field=models.ForeignKey(
                db_column="tenant_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.tenant",
            ),
        ),
        # 5 · the code is unique WITHIN one utility, and only there.
        migrations.AddConstraint(
            model_name="accounttype",
            constraint=models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_account_types_tenant_code_ci"
            ),
        ),
    ]
