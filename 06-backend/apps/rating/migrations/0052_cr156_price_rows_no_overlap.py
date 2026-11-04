# ── Trace ──────────────────────────────────────────────
# Change:  CR-156-BRC10 — PO 2026-10-01: *"19 read places must return exactly
#          one price row … guaranteed by three locks — a database rule refusing
#          overlapping live rows, ONE shared lookup … and a repo gate"*. This is
#          the first lock.
# Rules:   BR-RAT-1049 · BR-RAT-1050 · B2 §2's no-overlap shape (`rating/0047`)
# Tests:   06-backend/tests/test_cr156_charge_prices_pg.py
# ───────────────────────────────────────────────────────
"""rating 0052 — `effective_from` becomes required; a price window may not end
more than a day before it starts; and **no two rows for one (code, size, class)
may be in force on the same day** — the exclusion constraint.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (migration ordering). Row in
`12-governance/09-human-review-ledger.md`.

⚠ **THE EXCLUSION COVERS EVERY ROW, KILLED ONES INCLUDED — STRICTER THAN *"two
live rows"*, ON PURPOSE.** A killed row still prices its own dates (*"A past
bill reads the row in force on its dates"*), so a killed row overlapping a live
one would make the lookup's answer for those days depend on which row it read
first. The writer (`charge_prices.save_prices`) closes every row of a changed
(size, class) that reaches the new start BEFORE it inserts, so a well-formed
save never meets this constraint; it exists for the write that is not.

⚠ **`COALESCE(customer_class, '')` IS THE EQUALITY KEY, AND THAT IS RULE 1, NOT
A SHORTCUT.** NULL is *every class*, and an every-class row and a residential
row for the same size legitimately coexist (the residential row beats it for a
residential account). So an every-class row may only collide with another
every-class row — exactly what comparing `''` with `''` and never with
`'residential'` does. Without the COALESCE, NULL ≠ NULL in an exclusion and two
every-class rows would both be accepted.

⚠ **THE RANGE IS `[effective_from, effective_to + 1)`** — `rating/0047`'s form —
so an end exactly one day before the start is an EMPTY range that overlaps
nothing (the shape the writer leaves when a price is superseded before it ever
began), and the CHECK refuses anything earlier, because `daterange` would raise
on it rather than refuse it by name.

⚠ **SQLITE GETS THE CHECK AND NOT THE EXCLUSION** — it has no range type. The
live assertion is `tests/test_cr156_charge_prices_pg.py`, which skips by name
on any other vendor (hard-won law 14).
"""

from datetime import date, timedelta

from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

ADD = """
ALTER TABLE charge_code_amounts
  ADD CONSTRAINT ex_charge_code_amounts_no_overlap
  EXCLUDE USING gist (
    tenant_id WITH =,
    charge_id WITH =,
    size_class WITH =,
    (COALESCE(customer_class, '')) WITH =,
    daterange(effective_from, COALESCE(effective_to + 1, 'infinity'::date)) WITH &&
  );
"""

DROP = "ALTER TABLE charge_code_amounts DROP CONSTRAINT IF EXISTS ex_charge_code_amounts_no_overlap;"


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0051_cr156_move_flat_amounts_into_rows"),
    ]

    operations = [
        migrations.AlterField(
            model_name="chargecodeamount",
            name="effective_from",
            field=models.DateField(default=date(2000, 1, 1)),
        ),
        migrations.AddConstraint(
            model_name="chargecodeamount",
            constraint=models.CheckConstraint(
                condition=models.Q(("effective_to__isnull", True))
                | models.Q(
                    ("effective_to__gte", models.F("effective_from") - timedelta(days=1))
                ),
                name="ck_charge_code_amounts_window",
            ),
        ),
        PostgresOnlySQL(sql=ADD, reverse_sql=DROP),
    ]
