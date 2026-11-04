# ── Trace ──────────────────────────────────────────────
# Change:  CR-072 (2026-09-04) — *"all the request coming from portal should go
#          in Service request. if we have to icnrease the defination of Service
#          request we should do it"* (PO, on the live deployment). Screens:
#          CWP-006 · CWP-007 · CWP-012 · the Interruption section of REQ-02
# Rules:   BR-CWP-100 · BR-CWP-101 (added by this build) · BR-CWP-024 (one
#          reference, and it is theirs — it now points at the `SR-` number) ·
#          BR-CWP-026 (no guest write changes an account; widening the request
#          record does not weaken it) · CLAUDE.md hard rule 1 (tenant scoping;
#          `service_requests` already carries RLS FORCE from customers/0018) ·
#          hard rule 4 (nothing issued is rewritten — no invoice, line, payment
#          or journal row is touched)
# Tests:   06-backend/tests/test_cr072_report_is_a_request.py ·
#          06-backend/tests/test_cr072_pg.py (the live-PostgreSQL half)
# Impacts: apps/customers/models.ServiceRequest · service_request_service ·
#          apps/portal/services._report · apps/metering/interruption_service
# ───────────────────────────────────────────────────────
"""customers 0040 — `service_requests` widens by TWO nullable columns, and
NOTHING is dropped, backfilled or rewritten.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list. AI-authored under the PO ruling of 2026-08-09 (*"AI will
do it; we will review it later as human"*). The row in
`12-governance/09-human-review-ledger.md` states in plain English, with the
figure, what a reviewer is being asked to agree to.

════════════════════════════════════════════════════════════════════════════
WHAT THE PRODUCT DID BEFORE THIS, MEASURED
════════════════════════════════════════════════════════════════════════════
One press of *Send* on the report form wrote **TWO rows**: a `service_requests`
row a clerk works, and an `interruptions` row carrying the network fact — and
handed the passer-by the INTERRUPTION's reference, `RP-26-0412`, while the
`SR-26-0049` the same call created was deliberately withheld.

**So a clerk had two rows and the customer held the number of the one that is
not the request.** The Product Owner objected to precisely that on the live
deployment, and pre-authorised the expensive answer in their second sentence.

════════════════════════════════════════════════════════════════════════════
THE TWO COLUMNS, AND WHY EACH IS THE SMALLEST THING THAT WORKS
════════════════════════════════════════════════════════════════════════════
**`problem_kind`** — what sort of problem. The report's other three facts
already had columns and were already being written to them: the reporter's name
and phone are `applicant_name` / `applicant_phone`, where they were free text
described (`BR-CWP-027`), their own words are `what_they_said`, and the place
is `address_as_given`, which `BR-CUS-070` keeps verbatim. **Only the KIND had
nowhere to go**, so this is a one-column widening and not a new shape.

**`interruption_id`** — the confirmed interruption this report is about, once a
clerk has decided the reports are real. NULL until then, which is the normal
state of a report nobody has looked at yet.

════════════════════════════════════════════════════════════════════════════
THE FOREIGN KEY REVERSES DIRECTION, AND THE OLD COLUMN STAYS WHERE IT IS
════════════════════════════════════════════════════════════════════════════
`interruptions.service_request_id` pointed one-to-one at the request, which is
what FORCED a second interruption per report: twelve people ringing about one
burst main produced twelve "interruptions". `CR-072` §4 reverses it — **one
report is one request; many requests may point at one interruption** — and that
is what `service_requests.interruption_id` is.

⚠ **`interruptions.service_request_id` IS NOT DROPPED BY THIS MIGRATION, AND
THAT IS DELIBERATE.** `CR-072` §7 states the rollback as *"the FK reversal is a
new nullable column beside the old one, so the previous behaviour is a code
revert with no data loss"*. From this commit the new code neither reads nor
writes the old column; it is a one-release rollback affordance and the wave
that removes it is named in `apps/metering/interruptions.py`'s own docstring so
its removal is a plan and not a discovery.

════════════════════════════════════════════════════════════════════════════
WHY NOTHING IS BACKFILLED
════════════════════════════════════════════════════════════════════════════
**There is nothing to backfill.** `CR-072` §5, verified on this branch before
the migration was written: the only `interruptions` rows in existence are the
sample utility's and the browser walkthrough's. No production tenant has run a
report through this path.

A backfill would also have to invent `problem_kind` for every request that is
not a report, and the honest value there is NULL — *nobody said, because
nothing asked*.

════════════════════════════════════════════════════════════════════════════
WHAT THIS DELIBERATELY DOES NOT DO
════════════════════════════════════════════════════════════════════════════
* **It adds no CHECK constraint on `problem_kind`.** The vocabulary lives in
  `metering.interruptions.STORABLE_KINDS` and the service refuses an unknown
  value BY NAME (`customers.serviceRequest.problemKindUnknown`). A database
  enum here would put a second copy of a metering vocabulary in a customers
  migration, where it could not be changed without one.
* **It touches no issued row.** Hard rule 4 — no invoice, invoice line, payment
  or journal line is read or written by this change at all.
* **It changes no RLS policy.** `service_requests` has carried ENABLE + FORCE
  since `customers/0018`; a new column on an existing table inherits it, which
  `tests/test_cr072_pg.py` proves under the non-superuser probe role rather
  than assuming.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0039_def2847_mailing_address_line2_country"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicerequest",
            name="problem_kind",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="interruption_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="servicerequest",
            index=models.Index(
                fields=["tenant", "interruption_id"], name="ix_sr_interruption"
            ),
        ),
    ]
