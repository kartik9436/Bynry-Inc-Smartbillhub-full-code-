# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-RAT-5768 — a plan could hold only ONE customer class, so a
#           utility pricing Residential and Municipal alike had to write the
#           plan twice.
# Ruling:   PO 2026-09-19, verbatim: *"your understanding is correct - we have
#           all option anyway in drop down list - that is default"*, answering
#           the reading put to them: one class becomes a list of one, NULL
#           becomes the empty list, and the empty list means EVERY class.
# Rules:    DEF-273 / BR-RAT-108 (`charges.applies_to_customer_classes` — a
#           JSON list where NULL or [] means EVERY class; the sibling shape
#           this matches) · B14 rule 9 (chips + an add control) ·
#           CLAUDE.md 🔒 migration ordering
# Tests:    07-frontend/src/features/rating/planWizardBetaWalk.dom.test.tsx
#           06-backend/tests/test_def_rat_5768_plan_customer_classes.py
# ───────────────────────────────────────────────────────
"""rating 0038 — `rate_plans.account_type_id` becomes `account_type_ids`, a
JSON list, where NULL or `[]` means EVERY customer class.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-19 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md.

⚠ **THE BACKFILL IS THE RULING, WRITTEN OUT, AND IT IS NOT A GUESS.** The PO
was shown what widening the column costs — that every plan already written has
to mean something under the new rule — and ruled the three cases in one
sentence. So:

    account_type_id = <a uuid>   ->  account_type_ids = ["<that uuid>"]
    account_type_id = NULL       ->  account_type_ids = []          (every class)

**THE ARITHMETIC ON THE SEEDED ESTATE, counted before the column moved:**

    rate_plans rows                                   4
    rows with a class stated (account_type_id NOT NULL) 0
    rows with NULL                                     4   -> []  (every class)
    rows whose MEANING changes                         0

Zero, and that is the whole safety argument: every seeded plan carries NULL
(`DEF-452` — `_plan_payloads` never set the column although the endpoint has
accepted it since US-RAT-005), NULL already meant *not targeted at one class*,
and `[]` means the same thing said in the new vocabulary. A tenant that HAD
stated a class gets a list of exactly that class, which is the same set.

⚠ **NOTHING PRICES A BILL FROM THIS COLUMN, AND THAT WAS MEASURED RATHER THAN
ASSUMED.** `apps/rating/resolution.py` and `apps/rating/resolution_catalogue.py`
— the R1..R7 chain — name no class column on `rate_plans` at all; R1 resolves
the plan in force from the ACCOUNT's own assignment. The readers are
`selectors.plan_queryset` (the S9 list's `customer_class` filter),
`selectors.plan_detail` (what the wizard reads back), `services` (the write
path) and the one-shot `migrate_base_to_charge_codes` command. **So this
migration cannot move one cent on one bill, either way.**

⚠ **THE LIST FILTER NOW MATCHES THE EVERY-CLASS PLANS TOO, AND THAT IS A REAL
BEHAVIOUR CHANGE RATHER THAN A PORT.** `qs.filter(account_type_id=<uuid>)`
answered *plans stated to be for this class*. A plan for EVERY class is for
this class, so the filter answers `named-this-class OR names-none`. Under the
old column the second arm did not exist as a concept, and leaving it out would
hide, from a clerk filtering on Residential, every plan that serves them.

⚠ **THE FILTER IS NOT `__contains`, AND THAT IS NOT STYLE.** Django's JSONField
`contains` lookup **raises `NotSupportedError` on SQLite**, and
`config/settings/test.py` hardcodes in-memory SQLite (CLAUDE.md hard-won law
14). A `__contains` filter would therefore pass review, pass PostgreSQL, and
take the entire plan list down on every test run — the mirror of law 14's
own trap. `selectors.py` casts the column to text and matches the 36-character
uuid, which is exact (no uuid is a substring of another) and is valid SQL on
both backends.

⚠ **REVERSIBLE, AND THE REVERSE IS LOSSY IN EXACTLY ONE DIRECTION, STATED
BEFORE IT SHIPS (the change process' step 8).** Going back writes the FIRST id
of the list into the restored scalar and drops the rest. On the estate this
migration runs against that loses nothing — every list is empty — but on a
tenant that has since named two classes it narrows the plan to the first. It
under-narrows nothing and misprices nothing, because no bill reads the column;
a rollback would leave a plan looking narrower on screen than it is.
"""

from django.db import migrations, models


def _widen(apps, schema_editor):
    """One class becomes a list of one; NULL becomes `[]` — every class."""
    RatePlan = apps.get_model("rating", "RatePlan")
    for plan in RatePlan.objects.all().iterator():
        old = getattr(plan, "account_type_id", None)
        plan.account_type_ids = [str(old)] if old else []
        plan.save(update_fields=["account_type_ids"])


def _narrow(apps, schema_editor):
    """The reverse, and it is lossy past the first id — see the docstring."""
    RatePlan = apps.get_model("rating", "RatePlan")
    for plan in RatePlan.objects.all().iterator():
        ids = plan.account_type_ids or []
        plan.account_type_id = ids[0] if ids else None
        plan.save(update_fields=["account_type_id"])


class Migration(migrations.Migration):
    dependencies = [("rating", "0037_cr120_schedule_base_charge_code")]

    operations = [
        # ADD, BACKFILL, then REMOVE — in that order, in one migration, so
        # there is no window in which a row's class is readable from neither
        # column. `default=list` is the model's; the column itself is nullable
        # because an unmigrated row read through an older process must not
        # crash, and NULL reads as `[]` everywhere it is read.
        migrations.AddField(
            model_name="rateplan",
            name="account_type_ids",
            field=models.JSONField(blank=True, default=list, null=True),
        ),
        migrations.RunPython(_widen, _narrow),
        migrations.RemoveField(model_name="rateplan", name="account_type_id"),
    ]
