# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — the field app signs in by work EMAIL or PHONE NUMBER
#           (PO ruling 2026-10-21, relayed by the coordinator; there is no
#           Technician ID)
# Rules:    BR-IDN-001 (tenant-first: unique inside ONE utility, never across) ·
#           BR-IDN-029 (per-tenant uniqueness) · CLAUDE.md hard rule 1 (RLS
#           FORCE stays on; the backfill visits each tenant under its own
#           `app.tenant_id`) · hard-won law 14 (a migration that fails on live
#           data is a failed deploy)
# Tests:    06-backend/tests/test_cr187_phone_sign_in.py ·
#           06-backend/tests/test_cr187_phone_sign_in_pg.py
# ───────────────────────────────────────────────────────
"""identity 0013 — `users.phone_e164`, the phone number as a sign-in name.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — 🔒 identity/credentials, AI-authored 2026-10-21 under
the PO ruling of 2026-08-09 (*"AI will do it; we will review it later as
human"*). Not RATIFIED without a recorded sign-off.

1. `users.phone_e164` — nullable text, the E.164 form of `users.phone`
   (`(512) 555-0104` → `+15125550104`, North American default).
2. BACKFILL, PER TENANT. ⚠ **TWO PEOPLE AT ONE UTILITY MAY ALREADY SHARE A
   NUMBER** — `phone` has never been unique, and a crew phone or a couple on one
   line is ordinary. Adding the unique index over such data would fail the
   deploy. So a number is written ONLY when exactly one login at that utility
   holds it; every holder of a shared number is left NULL. A NULL number signs
   in nobody — those people sign in by email — and
   `manage.py phone_sign_in_duplicates` lists them (named, number masked) so
   the office can give each a number of their own. Nothing in `phone` (as
   typed) is changed by this migration.
3. `uq_users_tenant_phone_e164` — UNIQUE (tenant_id, phone_e164) WHERE
   phone_e164 IS NOT NULL. Added AFTER the backfill, so it can never meet a
   duplicate.

RLS: `users` carries ENABLE + FORCE (`identity/0002`). The backfill sets
`app.tenant_id` to each tenant in turn and restores the arrival value
(`work/0045`'s shape). An ADD COLUMN and a CREATE UNIQUE INDEX touch neither
the policy nor FORCE; the PostgreSQL test asserts both afterwards.
"""

from collections import defaultdict

from django.db import migrations, models

_STRIP = str.maketrans("", "", " -.()\t")


def _normalise(raw):
    """PINNED COPY of `apps.identity.phones.normalise_phone` as of this
    migration, so a later change to the rule never re-applies under this name."""
    text = str(raw or "").strip()
    if not text or "@" in text:
        return None
    compact = text.translate(_STRIP)
    plus = compact.startswith("+")
    digits = compact[1:] if plus else compact
    if not digits or not digits.isascii() or not digits.isdigit():
        return None
    if plus:
        return f"+{digits}" if 8 <= len(digits) <= 15 else None
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return None


def _apply_tenant(apps_registry, tenant_id):
    User = apps_registry.get_model("identity", "User")
    holders = defaultdict(list)
    for user_id, phone in User.objects.filter(tenant_id=tenant_id).exclude(
        phone__isnull=True
    ).values_list("id", "phone"):
        number = _normalise(phone)
        if number is not None:
            holders[number].append(user_id)
    written = shared = 0
    for number, ids in holders.items():
        if len(ids) == 1:
            written += User.objects.filter(pk=ids[0]).update(phone_e164=number)
        else:
            shared += len(ids)
    return written, shared


def backfill(apps_registry, schema_editor):
    Tenant = apps_registry.get_model("tenancy", "Tenant")
    connection = schema_editor.connection
    is_postgres = connection.vendor == "postgresql"

    arrival = None
    if is_postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            arrival = cursor.fetchone()[0]

    written = shared = tenants = 0
    try:
        for tenant_id in Tenant.objects.values_list("id", flat=True):
            if is_postgres:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)]
                    )
            tenants += 1
            w, s = _apply_tenant(apps_registry, tenant_id)
            written += w
            shared += s
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                if arrival is None:
                    cursor.execute("RESET app.tenant_id")
                else:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [arrival])

    if tenants:
        print(
            f"cr187 phone sign-in: {tenants} tenant(s) — {written} number(s) written; "
            f"{shared} login(s) share a number and were left NULL "
            "(run `manage.py phone_sign_in_duplicates`)"
        )


def undo(apps_registry, schema_editor):
    """Nothing to undo row by row: reversing the AddField drops the column."""
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0012_field_capture_hours"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="phone_e164",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RunPython(backfill, undo),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                condition=models.Q(("phone_e164__isnull", False)),
                fields=("tenant", "phone_e164"),
                name="uq_users_tenant_phone_e164",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: coordinator scope change 2026-10-21 (PO: sign in by email or phone) · BR-IDN-001/029
# generated: 2026-10-21 by the CR-187-BRC10 lane TECH-ID (phone sign-in)
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H✔(🔒 migration ordering — HUMAN-REVIEW-PENDING)
# gates: makemigrations --check · pytest tests/test_cr187_phone_sign_in*.py on SQLite and PostgreSQL 16
# exceptions: none
# status: AI-AUTHORED
# ──────────────────────────────────────────────────────────
