"""customers 0057 — **a move-in can record a discount claim.**

`CR-122-BRC06` · PO ruling 2026-09-19, answering *"please evaluate whther we
have to take any disount related field - based on what plans says becuase you
ahev plan details now"*.

Six discounts are seeded. Three are AUTOMATIC and need nothing new — paperless
and autopay are step 4's own ticks, and `MUNICIPAL` reads step 2's category.
Three need a PERSON to apply, and had nowhere to be said on a move-in:

  * `SENIOR`   — Age 65+, proof required, recertified every 12 months
  * `CAP`      — programme enrolment, proof required, monthly agency file
  * `MILITARY` — a veteran id, proof required, one-time

⚠ **THIS RECORDS A CLAIM AND CREATES NO DISCOUNT.** `proof_before_first_
reduction` defaults to true, so an unverified enrolment reduces nothing, and
`DiscountVersion.eligibility_rule` is advisory with no evaluator behind it —
its own docstring names automatic evaluation as `EP-RAT-12`'s remainder.
Enrolment remains a staff act through `discount_services.enrol_account`. These
columns are read by no pricing path.

⚠ **AND IT NEVER GATES SERVICE** — B18 §5.3.4, *"never blocks service — only
the discount"*. No guard, validator or refusal reads them.

The two names MIRROR `service_requests.eligibility_claimed` /
`eligibility_note` exactly, because a claim made on an application and the same
claim made at the counter are one fact.

Additive and nullable: every existing account reads `False` / `NULL`, which is
the true answer for an account nobody ever asked.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).
"""


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0056_service_request_document_original_size"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="eligibility_claimed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="account",
            name="eligibility_note",
            field=models.TextField(blank=True, null=True),
        ),
    ]
