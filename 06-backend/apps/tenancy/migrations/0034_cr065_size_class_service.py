# ── Trace ──────────────────────────────────────────────
# Change:   CR-065 task A1 — a size class names the utility service it belongs
#           to, so the Fire rate schedule stops offering Electric CT-metered.
#           PO 2026-09-02, verbatim, sent with a screenshot of that screen:
#           *"This is where we are setting rates for fire  you should show only
#           capacity for fire . in Setting a capacity needs to tags to utility
#           services ."*
# Rules:    BR-TEN-078 (SUPERSEDED for this one list by the ruling above — it
#           had named `service_size_classes` among the unscoped, twice) ·
#           BR-TEN-170 (same clause, same supersession) · BR-TEN-071 (seed data
#           never deletes, which is why the column is NULLABLE) · BR-TEN-025
#           (the service catalogue is closed, hence PROTECT)
# Tests:    06-backend/tests/test_cr065_size_class_service.py
# ───────────────────────────────────────────────────────
"""tenancy 0034 — one nullable column: ``meter_size_classes.service_id``.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-02 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md; not RATIFIED
without a recorded human sign-off.

⚠ **SCHEMA ONLY. THE BACKFILL IS `0035` AND MERGING THE TWO WILL BREAK
PRODUCTION WHILE PASSING EVERY TEST.** `0031_br_ten_1180_backfill.py` measured
this on a real PostgreSQL 16.13 and its docstring is the full account: an UPDATE
against rows whose table carries `DEFERRABLE INITIALLY DEFERRED` foreign keys
queues trigger events that are not flushed until COMMIT, and PostgreSQL then
refuses to ALTER that table —

    django.db.utils.OperationalError: cannot ALTER TABLE "meter_size_classes"
    because it has pending trigger events

The rule that split encodes, and it is the thing to keep: **a migration is
EITHER schema or data, never both, on any table whose rows it touches.**

⚠ **NULLABLE, AND THE NULL IS A VALUE RATHER THAN A GAP.** `BR-TEN-071` forbids
deleting a tenant's own row, so a size class a tenant added before today must
keep working — and it does: an untagged row lists on EVERY service's picker,
exactly as all sixty rows did yesterday. A `NOT NULL` column would have had to
invent a service for it. This is the same reading `uoms.service_id` has carried
since CR-004, where NULL is the value *"All services"*.

⚠ **PROTECT, NOT CASCADE.** The service catalogue is closed (`BR-TEN-025`) and a
service is never deleted; PROTECT states that rather than trusting it — the same
choice `uoms.service_id` made.

**THE FK CROSSES TO PLATFORM REFERENCE DATA AND LEAKS NOTHING.** `services` is
RLS-exempt (B2 §3) and identical for every tenant; the ROW stays gated by
`meter_size_classes_tenant_isolation`, which this migration does not touch.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("tenancy", "0033_cr063_fire_service"),
    ]

    operations = [
        # SCHEMA ONLY. Adding a `RunPython` beside this is what the module
        # docstring exists to prevent — the backfill is 0035.
        migrations.AddField(
            model_name="metersizeclass",
            name="service",
            field=models.ForeignKey(
                blank=True,
                db_column="service_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="size_classes",
                to="tenancy.service",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-065 task A1
# generated: 2026-09-02 by the CR-065 lane
# checklist: A✔ B✔ (BR-TEN-078 as superseded 2026-09-02 → one nullable column; 18 cases in test_cr065_size_class_service.py, the untagged-row case and the tenant-row case among them, every one shown RED before the code) C✔ (the row stays tenant-scoped by the existing RLS policy, which this migration does not touch; the FK crosses only to RLS-exempt platform reference data, no money column is added and nothing append-only is written) D=deferred(no-API-half — this migration adds a column; the endpoint that serves and filters on it is apps/tenancy/services.py and apps/tenancy/selectors.py in the same change) E=deferred(no-screen-half — the screens are the same change's frontend slice) F✔ (see gates:) G✔ (the supersession of BR-TEN-078 and BR-TEN-170 is written into 04-docs/05-modules/01-tenancy/02-business-rules.md and 12-governance/02-decision-log.md with the ruling quoted verbatim and dated, and OQ-1380 is minted rather than assumed shut) H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: applied FORWARD and REVERSE against a REAL PostgreSQL 16 (CLAUDE.md law 14)
# exceptions: none — the column is additive, nullable, and reverses cleanly
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
