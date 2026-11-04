"""work 0005 — the builder's step 7 gets somewhere to put its three answers.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Its row is in
`12-governance/09-human-review-ledger.md`; it does not reach RATIFIED without a
recorded sign-off.

CR-070 wave E, task `E1` (`US-WRK-016`). `08-screen-layouts.md` §13.1 names the
builder's seventh step *Signature*, and `wireframes/Work-017.png` counts it in
the review panel as **Signature · 3 · Customer signature required; refusal
recorded with a reason**. Wave D built the seven `wot_*` tables and none of
them holds any of those three facts, so step 7 would have rendered and
forgotten — which is hard-won law 2 in its second shape, a control with nothing
behind it.

WHY `wot_details` AND NOT A TABLE OF ITS OWN
────────────────────────────────────────────
`wot_details` is already *"ONE row per template — what the technician is shown
on the job"*, enforced one-to-one by `uq_wot_details_template`. What a
technician must BRING BACK is the same class of fact about the same job, and a
second one-row-per-template table would be a second answer to *"what does this
template ask of the visit"* (the 2026-09-05 ruling, *"Work is NOT an isolated
module"*: only a genuinely new fact earns a new table).

WHY THESE THREE NAMES
─────────────────────
They are read off `work_order_signatures`' own column list in
`03-field-map.md` §3 — `refused`, `decline_reason`, `door_hanger_document_id` —
so the template's ASK and the phone's ANSWER (`US-WRK-036`, phase 2) are one
vocabulary. Nothing here is invented for the sake of a form.

⚠ **IT IS A 🔒 PATH AND THE FIRST DRAFT OF THIS DOCSTRING SAID IT WAS NOT.**
That draft argued *"three booleans with defaults; no RLS policy, no rating
maths, no money, no numbering, no idempotency key"* — all true, and all beside
the point: **CLAUDE.md's sensitive list names MIGRATION ORDERING**, so every
migration in this repository is guarded whatever it carries. `G7` said so by
name the first time the whole suite ran over it, and `work/0003` two files
along has carried the marker since the day it landed. Corrected rather than
argued with.

What IS genuinely small about it is worth keeping: `work/0004` already put
ENABLE + FORCE on `wot_details`, and a column added to a table under RLS
inherits it — `test_us_wrk_rls_pg.py` re-reads `pg_class` for all fourteen Work
tables and would say otherwise.

DEFAULTS ARE THE SAFE ANSWER, NOT THE COMMON ONE (hard-won law 3). All three
default TRUE: a template that says nothing about signatures asks for one,
records why it was refused, and leaves a card. The unsafe option — *do not
bother getting a signature* — is the one a person has to type.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("work", "0004_rls_force_bundle"),
    ]

    operations = [
        migrations.AddField(
            model_name="workordertemplatedetail",
            name="signature_required",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="workordertemplatedetail",
            name="refusal_reason_required",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="workordertemplatedetail",
            name="door_hanger_on_no_answer",
            field=models.BooleanField(default=True),
        ),
    ]
