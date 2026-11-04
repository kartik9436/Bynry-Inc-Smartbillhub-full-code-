# ── Trace ──────────────────────────────────────────────
# Change:   PO ruling 2026-09-22 — *"correct address will be on presmies but
#           first time you will ahve to take the details to match it"*.
# Rules:    `BR-MET-1161` (an address is stored on `premises` and NOWHERE
#           else) — NOT narrowed · `BR-CUS-070` (what the applicant said is
#           kept byte for byte) · `BR-CUS-1055` (the near-miss this reverses)
# Decision: 12-governance/02-decision-log.md, 2026-09-22 — *A REQUEST TAKES
#           THE ADDRESS IN PARTS SO IT CAN FIND THE PREMISES; THE PREMISES IS
#           STILL THE ONE ADDRESS*
# ───────────────────────────────────────────────────────
"""`service_requests` takes the address in PARTS, as the applicant gave them.

**WHAT THIS IS FOR: MATCHING.** A request that cannot take a city and a ZIP
cannot find the premises it is about, which is the one thing the capture
wizard's address step exists to do.

⚠⚠ **THIS IS NOT A FOURTH HOME FOR AN ADDRESS AND `BR-MET-1161` IS NOT
NARROWED — the decision log says so in as many words.** That rule governs where
an address is STORED AS THE TRUTH. These three are a record of **what a member
of the public said**, which is why every one of them carries `_as_given`: the
same posture `address_as_given` has had since it was written, and the same
posture `interruptions.location_text` has — *"what a stranger typed — a report,
not a record"*. Once `premises_id` is set, **the premises is what every screen
shows**, and that clause is part of the ruling rather than a nicety.

⛔ **THREE COLUMNS OF THESE EXACT NAMES WERE ADDED ON 2026-09-15 AND TAKEN OUT
THE SAME HOUR, AND THE CHAIN IS WRITTEN OUT HERE SO NOBODY HAS TO INFER IT.**
The PO ruled that day *"if we have unit or street address then we should take
it from premises/Unit - it means its a search and if not foudn them alow user
to add them"*, and `CAPTURE_FIELDS` carried *"Do not re-add them"* from then
until today. That refusal was correct under the ruling it cited. **The rule was
then quoted correctly and applied to the wrong act**: a lane read a rule about
STORAGE as a rule about CAPTURE and refused to let a clerk type a ZIP at all,
and the PO overturned it. `BR-CUS-1055` records the first near-miss; this
migration is the reversal, with the storage rule explicitly untouched.

**NULLABLE, NO BACKFILL, NO DEFAULT.** Nothing can derive these for a row
written before today — the street line is one free-text field and splitting a
town out of it is a guess — so existing requests carry NULL and every screen
renders that as the absence it is.

⚠ **`G85` DOES NOT SEE THESE AND IS DELIBERATELY NOT TAUGHT TO.** It matches by
NAME, so a `_as_given` spelling is invisible to it; teaching it that spelling
would make it refuse `address_as_given` itself, which `BR-CUS-070` requires.
What keeps the door shut is the name: a lane adding a bare `city` to this table
is still caught, because `city` IS in the gate's `ADDRESS_SHAPED`. The gate's
declared blind spot moves from 3 columns to 6 in the same commit — a number
that does not move when its subject does is worse than no number.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0064_br_cus_1090_move_in_job_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicerequest",
            name="address_city_as_given",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="address_state_as_given",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="address_postal_code_as_given",
            field=models.TextField(blank=True, null=True),
        ),
    ]
