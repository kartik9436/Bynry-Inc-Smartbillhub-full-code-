"""billing 0039 — `invoice_lines.pricing_trace`: the chain a line was priced from.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list. AI-authored 2026-10-01 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`
(*"2026-10-01 · CAPACITY BASE BY SIZE"*).

WHAT IT IS. One nullable `jsonb` column. PO ruling 2026-10-01, verbatim: *"i
want tracbility -> billing -> account -> unit -> plan -> rate schedule -> base
charge -> size and amount"*. Stage 6 (`stages/assemble_document.py`) writes, on
every usage, base and minimum line of a service, the VALUES that priced it:
account, unit, plan + version, rate schedule version, customer type, base
code, and per size the count, base each, base total and price each. Worked:
two 96-gallon carts, BASE-T at $3.00 a cart, carts $15.00 —
`{"sizes": [{"size": "CART-96", "count": 2, "base_each": "3.0000",
"base_total": "6.0000", "price_each": "15.0000"}], …}` on the $36.00 line.

WHY ONE JSON COLUMN, NOT NEW COLUMNS OR A CHILD TABLE (decision log
2026-10-01). A line can carry any number of sizes (a 6" fire line and two 2"
lines are ONE line since 2026-09-30), so flat columns cannot hold it; a child
table on a PARTITIONED parent needs the partition key in its foreign key and
its own immutability trigger, for data that is written once with the line and
never read without it. In the line's own row it is covered by the line's
immutability trigger (billing 0002) for free. And it stores VALUES, never ids
of `charge_code_amounts` rows — those are deleted and re-created on every
edit, and charges have no versions.

⚠ **`invoice_lines` IS A PARTITIONED PARENT** (`billing/0016`). `ADD COLUMN`
on the parent propagates to every partition and every future one; a nullable
column with no default is a catalogue-only change, so no row is rewritten and
hard rule 4's trigger never fires — the shape `billing/0031` used for
`asset_id`. NULL on every line already written: NEW bills only, no backfill.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0038_d8696_sign_off_snapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoiceline",
            name="pricing_trace",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
