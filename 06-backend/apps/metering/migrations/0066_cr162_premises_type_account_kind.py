"""metering 0066 — every premises type names the ACCOUNT TYPE its premises take,
master or regular (`CR-162-BRC10`, Q1).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path, and the data half writes
under per-tenant RLS context).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-02 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

PO 2026-10-02 (decision log, *"NEW CONNECTION — THE PO'S SCREEN-BY-SCREEN
REVIEW BECOMES ONE PROGRAMME"*, Q1): an apartment complex, commercial building,
mixed-use or any type able to hold several units gets an owner's master account
even with one unit entered; a single-family home gets none. Reframed the same
day, verbatim: *"when we say premises type has account type - master or
regular attached … then when you create account dont you want to use this field
when you are creating accounts"* — so the setting lives on each row of the
tenant's own list and a type a utility adds itself is answered by the utility.

SCHEMA: `premises_types.account_kind TEXT NULL` — `master` or `regular`, the
same two words as `accounts.kind`. Not `account_type`: that name is already the
account CLASS lookup. No default: a row a utility adds must be answered (the
Settings door refuses a blank).

DATA, PER TENANT: every SEEDED row (`is_system`) whose code is one of the six
`BR-MET-034` codes gets its seeded answer — apartment_complex, commercial_
building, mixed_use, mobile_home_park, government_building → `master`;
single_family → `regular`. The six answers are MIRRORED below rather than
imported from `apps.metering.premises_capacity`, so this migration stays
runnable against the code of any later day;
`tests/test_cr162_new_connection_lifecycle.py` asserts the mirror equals
`SEED_ACCOUNT_KIND`. A utility's OWN rows are
left NULL — nobody may answer for them — and the rule falls back to counting
homes there until someone does.

NOTHING ELSE MOVES. No master account is created or removed; the answer is
read only when a NEW owner's master account is opened.

ROLLBACK: `manage.py migrate metering 0065` drops the column; the master rule
then reads every type as unanswered and falls back to counting homes.
"""

from django.db import migrations, models

#: Mirror of `apps.metering.premises_capacity.SEED_ACCOUNT_KIND`.
SEEDED = {
    "apartment_complex": "master",
    "commercial_building": "master",
    "mixed_use": "master",
    "mobile_home_park": "master",
    "government_building": "master",
    "single_family": "regular",
}


def answer_the_seeded_rows(apps, schema_editor):  # type: ignore[no-untyped-def]
    from django.db import connection

    premises_type = apps.get_model("metering", "PremisesType")
    tenant_model = apps.get_model("tenancy", "Tenant")
    on_postgres = schema_editor.connection.vendor == "postgresql"
    tenant_ids = list(tenant_model.objects.values_list("id", flat=True).order_by("id"))
    answered = 0
    for tenant_id in tenant_ids:
        if on_postgres:
            # LOCAL: scoped to this migration's transaction (CLAUDE.md hard
            # rule 1 — premises_types is under FORCE row-level security, and an
            # unscoped UPDATE would match nothing and report success).
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL app.tenant_id = %s", [str(tenant_id)])
        for code, answer in SEEDED.items():
            answered += premises_type.objects.filter(
                tenant_id=tenant_id,
                is_system=True,
                code__iexact=code,
                account_kind__isnull=True,
            ).update(account_kind=answer)
    # Hard-won law 7, habit 3: a count a reader can tell a pass from a fail by.
    print(f"  premises_types.account_kind: {len(tenant_ids)} tenant(s), {answered} row(s) answered")


def forget_the_answers(apps, schema_editor):  # type: ignore[no-untyped-def]
    """Nothing to undo row by row — the reverse of AddField drops the column."""


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0065_cr162_connection_todo_kind"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="premisestype",
            name="account_kind",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RunPython(answer_the_seeded_rows, forget_the_answers),
    ]
