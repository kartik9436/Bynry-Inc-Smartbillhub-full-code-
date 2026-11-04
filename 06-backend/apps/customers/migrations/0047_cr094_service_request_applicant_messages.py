"""customers 0047 — what a service request TELLS THE APPLICANT (`DEF-CUS-5389`).
HUMAN-OWNED (migration ORDERING is a CLAUDE.md rule-1 🔒 path).

THREE COLUMNS, AND THEY ARE THE FIRST ON THIS TABLE WHOSE CONTENTS LEAVE THE
BUILDING.
─────────────────────────────────────────────────────────────────────────────
The Accounts blueprint's entry 06 draws a Refuse dialog with a `What to tell
them` box under the words *"Goes into the refusal letter."* and an Ask-for-more
dialog with a tick list and a `Message to the applicant` box under the words
*"Sent to them and kept on the request's history."* (p084-p086, read as
images). The product had nowhere to put any of the three: a refusal stored one
internal sentence, and asking for more sent the same fixed words to every
applicant in the product.

  * `refusal_message` — the clerk's own sentence, and the BODY of the refusal
    letter. Deliberately NOT `decision_reason`, which is the internal note and
    stays internal; one column serving both would put a clerk's shorthand in
    front of an applicant.
  * `info_needed` — the tick list, as a JSON list of codes from
    `service_request.INFO_NEEDED_KINDS`. A list rather than four booleans: the
    drawing ticks two of four in one act, and a fifth thing to wait for should
    be a vocabulary edit rather than another migration.
  * `info_message` — the message a clerk types when they ask for more.

⚠ **MIGRATION ORDERING IS A 🔒 SENSITIVE PATH (CLAUDE.md).** This is three
`AddField`s on an existing table with no data step and no backfill. All three
are NULLABLE or default to an empty list, so every existing row satisfies them
as it stands and no tenant walk is needed — which matters, because a data
migration runs as the APP role under RLS FORCE and one that does not set
`app.tenant_id` sees nothing and reports success (`DEF-BIL-5382`, 2026-09-15).
There is nothing here for such a step to do.

⚠ **NO NEW RLS POLICY IS NEEDED AND THAT IS NOT AN OMISSION.** `service_requests`
already carries its policy from `0017`; a policy is per TABLE, not per column,
so three added columns inherit it. A new table would need one in the same
commit and this is not one.

HUMAN-REVIEW-PENDING — AI-authored 2026-09-15 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0046_rls_br_cus_1047_unit_correction"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicerequest",
            name="refusal_message",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="info_needed",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="info_message",
            field=models.TextField(blank=True, null=True),
        ),
    ]
