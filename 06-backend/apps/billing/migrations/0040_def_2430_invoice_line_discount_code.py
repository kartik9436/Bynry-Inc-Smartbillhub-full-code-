"""billing 0040 — `invoice_lines.discount_code`: which programme a discount line spent.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list. AI-authored 2026-10-03 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`
(*"2026-10-03 · DISCOUNT GRANTS RECORDED AT ISSUE"*).

WHAT IT IS. One nullable text column (`DEF-2430` / `DEF-BIL-5341`, PO ruling
2026-10-03 *"A · Yearly caps don't count down - a"*). Stage 6 writes the
programme CODE (`CAP`) on every `discount` line the engine produced; issue
hands `{code: amount}` to rating, which records one `discount_grants` row per
enrolment so a yearly cap, a lifetime cap and a budget count down. Worked: a
CAP credit of $25.00 a month under a $300.00 yearly cap reaches $300.00 on its
twelfth bill of the year and gives $0.00 after it.

⚠ **`invoice_lines` IS A PARTITIONED PARENT** (`billing/0016`). `ADD COLUMN`
on the parent propagates to every partition; a nullable column with no default
is a catalogue-only change, so no row is rewritten and hard rule 4's trigger
never fires — the shape `billing/0031` and `0039` used. NULL on every line
already written: new bills only, no backfill.

DOWN PATH. `RemoveField` — Django reverses `AddField` by dropping the column.
Dropping it after bills have issued loses which programme each issued discount
line spent; the grant rows rating wrote are unaffected (they live in
`discount_grants`), so a rollback costs the line's label and no money.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0039_invoice_line_pricing_trace"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoiceline",
            name="discount_code",
            field=models.TextField(blank=True, null=True),
        ),
    ]
