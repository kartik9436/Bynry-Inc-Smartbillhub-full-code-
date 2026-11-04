"""customers 0031 — `service_requests.ssn`, the column the screen has been promising.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering AND app-layer
encryption are both on CLAUDE.md's sensitive-paths list. The ledger row for this
work is in `12-governance/09-human-review-ledger.md`. The marker is here because
the PATH is the category, not because the body is large (DEF-808).

WHAT THIS CLOSES
================
`DEF-632` (critical). PO ruling 2026-08-27, verbatim: *"We tell customers their
Social Security number is stored encrypted - Verify and keep the promise -
Confirm SSN is genuinely encrypted at rest and only the last four are shown, then
the sentence stays. We need to capture SSN and encript it; we have to ensure it
is working"*. The rule is `BR-CUS-092`, CONFIRMED 2026-08-24 — **no new rule is
minted here.**

Before this migration the product stored no SSN at all:
`service_request_service._clean_capture` refused fourteen identifier field names
outright with `customers.serviceRequest.identifierNotStorable`. That was the
correct interim state — refusing is safer than plaintext under a promise of
encryption — and the ruling supersedes it.

════════════════════════════════════════════════════════════════════════════
⚠ THIS IS `0031` AND `0029` IS STILL FREE. THAT IS DELIBERATE.
════════════════════════════════════════════════════════════════════════════
`DEF-892`: a migration number is ALLOCATED TO A LANE, never taken from the
watermark. `customers 0031` is this lane's reservation and is recorded in
`12-governance/14-id-reservations.md`.

`0029` is unclaimed and this migration does NOT take it, for the reason `0030`'s
own header states: `0030` already depends on `0028`, so a second child of `0028`
would make two leaves and Django would demand a merge migration. This depends on
`0030`, the real leaf, and the graph stays linear.

════════════════════════════════════════════════════════════════════════════
NO NEW RLS POLICY, AND THE REASON IS STATED RATHER THAN ASSUMED
════════════════════════════════════════════════════════════════════════════
RLS in this product is a TABLE policy, not a column one. `0018_rls_cr031_service_
requests` already puts `FORCE` row-level security on `service_requests` against
`app.tenant_id`; a new column on an existing table inherits it with nothing to
add. Adding a policy here would create a second policy on the same table, which
is how a permissive OR-ed policy silently widens access.

════════════════════════════════════════════════════════════════════════════
NO DDL BEYOND ONE NULLABLE `text`, AND NO BACKFILL
════════════════════════════════════════════════════════════════════════════
`core.crypto.EncryptedTextField` subclasses `TextField`, so the column type is
plain `text` and the ciphertext envelope lives inside it —
`sbh1:<kid>:<b64u nonce>:<b64u ciphertext||tag>`. Nothing to convert: every
existing row carries NULL because no row has ever held an SSN, so unlike the
`tenancy.ein` migration there is nothing to encrypt in place and this migration
needs no key to run.

Reversible with no data loss risk beyond the obvious: `RemoveField` drops the
ciphertext, which is the correct behaviour for a rollback of a column that should
never have existed if the ruling were reversed.
"""

from django.db import migrations

import core.crypto


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0030_cr039_wd_move_records"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicerequest",
            name="ssn",
            field=core.crypto.EncryptedTextField(
                blank=True,
                crypto_context="service_requests.ssn",
                null=True,
            ),
        ),
    ]
