# ── Trace ──────────────────────────────────────────────
# Change:   CR-091-BRC01 — *"when we create discount - we will ahve to take 1 or
#           more utility services - currently it is not available"* (the PO, in
#           the working chat session, 2026-09-10). Built inside CR-087 by the
#           PO's own ruling of the same day: *"CR-091-BRC01. - implemnt it
#           during the CR 87 itself - not sperately"*.
# Rules:    BR-RAT-068 (a discount is an OVERLAY, never an edit to the rate) ·
#           the TAX's `applies_to_services` precedent (models.py:913 — *"a JSON
#           list of catalog codes"*, validated against the tenant's enabled
#           services) · BR-RAT-024 (a service must be in the platform catalog
#           AND enabled for this tenant) · hard rule 4 (a version is a new row)
# Tests:    06-backend/tests/test_cr091_discount_names_its_services.py
# ───────────────────────────────────────────────────────
"""rating 0033 — `discount_versions.applies_to_services`, and the scope pair.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-10 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md.

⚠ **ADDITIVE AND NULLABLE, SO IT REINTERPRETS NOTHING.** That is the ruling's
own requirement rather than a convenience: PO 2026-09-10, *"The existing
`one_service` scope is NOT widened — every discount already saved keeps the
meaning it had, and no migration has to reinterpret stored rows."* Every row
written before today has `applies_to_services` NULL and keeps whichever of the
five original scopes it carries; the two new scope values are TEXT in an
existing column and need no schema change at all.

⚠ **THE COLUMN IS A COPY OF THE TAX'S, DELIBERATELY.** `taxes.
applies_to_services` is a JSON list of service codes, validated on the way in
and served as a list. CR-091 §2 names it as the precedent and says why: the
product already knows how to hold this shape for a sibling object, and a second
spelling of one idea is how four screens acquire four different chips.

⚠ **AN EMPTY LIST DOES NOT MEAN *EVERY SERVICE* HERE, AND ON A TAX IT DOES.**
The two must not be harmonised. A tax has no `All services` choice on screen, so
`NULL or []` is the only way it can say *everywhere*; a discount now HAS that
choice, so `specific_services` with an empty list is an UNFINISHED FORM and is
refused at save (PO ruling 2026-09-10). The refusal lives in
`discount_services._validate_version`, not in a constraint, because the same
column is legitimately NULL on every other scope.

**REVERSIBLE, AND THE REVERSE COSTS DATA NOTHING ELSE HOLDS.** Dropping the
column loses which services each `specific_services` discount named — nothing
else records it — so reverting the CODE alone is the documented rollback
(`22-product-maintenance-process.md` §7) and leaves the column in place, unread.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0032_tax_corrected_by"),
    ]

    operations = [
        migrations.AddField(
            model_name="discountversion",
            name="applies_to_services",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
