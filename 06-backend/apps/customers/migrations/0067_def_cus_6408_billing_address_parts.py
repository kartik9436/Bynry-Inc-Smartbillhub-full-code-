# ── Trace ──────────────────────────────────────────────
# Change:   PO report 2026-09-23 on `New request` step 3 — *"if customer want
#           put billing address then it should full address line, unit, city,
#           zip it shoould be match how address taken in USA ;do'nt make it
#           mandatory"*. `DEF-CUS-6408`.
# Rules:    CLAUDE.md hard rule 8 (its FIRST named exception — where the BILL
#           goes) · `BR-CUS-070` (what the applicant said is kept as said) ·
#           `BR-NOT-029` clause (a) (an address is never split out of a blob)
#           · `DEF-2703` (the recommendation this builds)
# ───────────────────────────────────────────────────────
"""`service_requests` takes the BILLING address in parts, as the applicant gave it.

**NULLABLE, NO BACKFILL, NO DEFAULT.** `billing_address_as_given` stays and is
not touched: every request captured before today keeps its one string exactly as
typed, and nothing parses it into these columns — `DEF-2703` said so first:
*"splitting billing_address_as_given into discrete columns is straightforward for
new rows and is GUESSWORK for every existing one"*.

⚠ **`G85` DOES NOT SEE THESE, BY NAME, AND ITS DECLARED BLIND SPOT MOVES FROM 6
TO 11 IN THE SAME COMMIT** — the posture `0065` took for the service address's
parts, for the same reason.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0066_def_cus_6370_deposit_waiver"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicerequest",
            name="billing_line1_as_given",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="billing_line2_as_given",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="billing_city_as_given",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="billing_state_as_given",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="billing_postal_code_as_given",
            field=models.TextField(blank=True, null=True),
        ),
    ]
