# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10140 — the PO opened, closed and re-opened a counter on one
#           day (CTR-261013-BS 06:24–06:44, then 13:04) and could neither open
#           the second till nor have it force-closed: both tills composed ONE
#           code and the resolver refused a code that matched two.
# Ruling:   decision log 2026-10-14 *"G1–G4 APPROVED"* item 2 (G2), PO
#           verbatim *"g1-g4 - go"*: the code is STORED at open and unique per
#           tenant; a second till on one base gets `-2`, `-3`; existing clashes
#           are repaired oldest-first, CTR-261013-BS keeps its number and the
#           13:04 session becomes CTR-261013-BS-2.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE on `counter_sessions` since
#           `payments/0032` — the backfill walks tenants with `app.tenant_id`
#           set, or it matches zero rows and prints OK, `DEF-PAY-6166`) · hard
#           rule 4 (NOT engaged: `counter_sessions` is not one of its frozen
#           tables) · hard-won law 14 (the race is proved on PostgreSQL)
# Tests:    06-backend/tests/test_def_pay_10140_counter_code_stored.py
# Impacts:  apps/payments/counter_session_models.CounterSession.code ·
#           apps/payments/counters.open_counter (the only writer) ·
#           apps/payments/counters.counter_code / _session_by_ref (the readers)
# ───────────────────────────────────────────────────────
"""payments 0050 — `counter_sessions.code`, filled for every person's till, then made unique.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-14 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*); row in 12-governance/09-human-review-ledger.md.

WHAT CHANGES, IN ONE SENTENCE
-----------------------------
A counter's code — `CTR-261013-BS` — stops being recomposed on every read and
becomes a stored column, so two tills can never share one.

THE THREE STEPS, IN THIS ORDER ON PURPOSE
-----------------------------------------
1. **Add the column, nullable.** A system till (`system_day` set, nobody sat at
   it) keeps NULL and `counters.counter_code()` composes `CTR-{day}-SYS` for it
   exactly as before — one per tenant per day, so it cannot clash.
2. **Fill it, per tenant, OLDEST FIRST** — by `opened_at`, then `created_at`,
   then `id`, so the order is total. The first till on a base takes the plain
   base, which is the code every screen has printed for it until today; the
   next takes `-2`, then `-3`. **So no code anyone has already seen moves**,
   and only the till that was unreachable gets a new one. Idempotent: a row
   that already carries a code is never touched, and is counted as taken.
3. **Make it unique per tenant** (`uq_counter_sessions_code`), only after the
   fill — the index would refuse the clash the fill is repairing.

THE RULE IS FROZEN HERE, NOT IMPORTED
-------------------------------------
`_compose_base` is a copy of `counters.composed_code_base` as it stood when
this was written. A migration that imported the live function would re-run
with whatever the rule says on the day a fresh database is built. The test file
asserts the two agree today.

THE ROLLBACK, STATED BEFORE SHIPPING
------------------------------------
The reverse drops the index and the column. What is lost is the `-2` on a
repaired till — the defect comes back with it: two tills one label, the second
unreachable by its code. The service must be backed out together with this.
"""

from django.db import migrations, models

#: The nil sentinel, never `''` — OQ-354: an empty marker poisons the deferred
#: FK validation at the end of a migration. Castable, matches no row.
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _compose_base(opened_at, full_name, email):
    """FROZEN copy of `counters.composed_code_base` (2026-10-14)."""
    from datetime import UTC

    moment = opened_at
    if moment is not None and moment.tzinfo is not None:
        moment = moment.astimezone(UTC)
    day = moment.date().strftime("%y%m%d") if moment else "------"
    parts = [word for word in (full_name or "").split() if word]
    initials = "".join(word[0] for word in parts[:2]).upper()
    if not initials:
        initials = (email or "")[:2].upper()
    return f"CTR-{day}-{initials or 'SYS'}"


def _next_free(base, taken):
    highest = 0
    for code in taken:
        if code == base:
            highest = max(highest, 1)
        elif code.startswith(f"{base}-") and code[len(base) + 1 :].isdigit():
            highest = max(highest, int(code[len(base) + 1 :]))
    return base if highest == 0 else f"{base}-{highest + 1}"


def _set_tenant(connection, tenant_id):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant_id)])


def store_existing_codes(apps, schema_editor):
    """Step 2 — every person's till gets the code it has always been shown, oldest first."""
    connection = schema_editor.connection
    Tenant = apps.get_model("tenancy", "Tenant")
    Session = apps.get_model("payments", "CounterSession")
    for tenant_id in list(Tenant.objects.values_list("id", flat=True)):
        _set_tenant(connection, tenant_id)
        rows = Session.objects.filter(tenant_id=tenant_id, system_day__isnull=True)
        taken = set(rows.exclude(code__isnull=True).values_list("code", flat=True))
        for row in (
            rows.filter(code__isnull=True)
            .select_related("owner")
            .order_by("opened_at", "created_at", "id")
        ):
            owner = row.owner
            base = _compose_base(
                row.opened_at,
                getattr(owner, "full_name", "") if owner else "",
                getattr(owner, "email", "") if owner else "",
            )
            code = _next_free(base, [value for value in taken if value.startswith(base)])
            Session.objects.filter(pk=row.pk).update(code=code)
            taken.add(code)
    _set_tenant(connection, NO_TENANT)


def leave_the_codes(apps, schema_editor):
    """Reverse of step 2 — nothing to undo; the column itself is dropped next."""


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0049_cr174_us_payments_agent_origin_return_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="countersession",
            name="code",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RunPython(store_existing_codes, leave_the_codes),
        migrations.AddConstraint(
            model_name="countersession",
            constraint=models.UniqueConstraint(
                condition=models.Q(code__isnull=False),
                fields=("tenant", "code"),
                name="uq_counter_sessions_code",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-PAY-10140 · decision log 2026-10-14 "G1–G4 APPROVED" item 2 ·
#   payments/0031 (counter_sessions) · payments/0032 (its RLS) ·
#   payments/0030 (the walk-tenants worked example)
# generated: 2026-10-14 by LANE COUNTER-CODE
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=pending(🔒 HUMAN-REVIEW-PENDING)
# gates: makemigrations --check · forwards, backwards, forwards on PostgreSQL 16
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
