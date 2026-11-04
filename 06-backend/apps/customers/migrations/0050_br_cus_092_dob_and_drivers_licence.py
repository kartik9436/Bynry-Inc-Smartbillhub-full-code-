"""customers 0050 — the date of birth and the driving licence on the REQUEST.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering AND app-layer field
encryption are both on CLAUDE.md's sensitive-paths list, and this migration is
on both. The ledger row naming what was shown to the PO in plain English with a
worked figure is in `12-governance/09-human-review-ledger.md`. The marker is
here because the PATH is the category, not because the body is large (DEF-808).

WHICH RULING ASKED FOR IT — AND WHY NOTHING IS BEING OVERRIDDEN
===============================================================
PO, 2026-09-15, shown the blueprint's step 1 beside the product's:

    "ensure user is able to inputs both these on step 1 - Date of birth and
     driver's licence on step 1 ... rewrite this rules if required"

⚠ **THE PERMISSION TO REWRITE IS RECORDED AND DECLINED AS UNNECESSARY, FOR THE
SECOND TIME ON THIS RULE.** The PO offered the same on 2026-08-24 (*"if you
ahve to override any law - please do Im permitting it"*) and `BR-CUS-092`
records why it was declined then: accepting it would misrepresent the position.
Clause (a) of that signed rule has read *"both identifiers are captured on the
service request"* since 2026-08-24, and the row's amendment of 2026-08-31 says
in capitals what was left: *"CLAUSE (a) IS HALF DONE. THE DRIVING LICENCE IS NOT
CAPTURED."* **This migration is that half landing. There is no superseded
statement to name.**

WHAT IT UNBLOCKS, WHICH IS WORTH MORE THAN TWO COLUMNS
=======================================================
`BR-CUS-089` (PO 2026-08-25, closing `OQ-364`) makes a STRONG identity match
**name + date of birth + one government ID**, and `BR-CUS-1020` records the cost
of the gap verbatim: *"until the request form captures a DOB, no match can be
assessed against them."* Signed criteria that **no service request could ever
satisfy**, for three weeks, with nothing red — because an absence is invisible to
every check this repo has (`DEF-CUS-3653`'s lesson, one table over). After this,
`identity_match.evidence_from_service_request` can present all three facts.

WHY ONE COLUMN IS ENCRYPTED AND THE OTHER IS A PLAIN DATE
==========================================================
It is signed law and not this lane's taste, and `customers 0036` made exactly
the same split for exactly the same reasons three weeks ago.

* **`drivers_licence` IS ENCRYPTED.** `OQ-016` is CLOSED (*"app-layer encryption
  for high-sensitivity columns, disk for rest"*, PO R6, B2 §6) and `BR-CUS-092`
  names the driving licence as one of its two identifiers. `core.crypto` is that
  encryptor — AES-256-GCM, a fresh 96-bit nonce per write, and additional
  authenticated data binding a ciphertext to the column it was written for, so a
  value lifted out of `customers.driving_licence` and dropped in here RAISES
  rather than decrypting. This is its THIRD caller, after `tenants.ein` and
  `service_requests.ssn`; no new capability is built.
* **`date_of_birth` IS A PLAIN `date`, AND `BR-CUS-1020` ALREADY SETTLED WHY:**
  *"it must be COMPARABLE, `contacts.dob` is a plain date too, and `BR-CUS-092`
  names two identifiers of which it is not one."* Encrypting one of the three
  places this product holds a date of birth would mean they could not be
  compared at all, which is the one thing `BR-CUS-089` needs them for.

WHY THE ENCRYPTED COLUMN HAS A `_bidx` TWIN AND NO `_last4` ONE
================================================================
The scheme is RANDOMISED — the same licence encrypts differently every time,
which is the correct choice for an identifier typed into a public-facing form —
and it costs exactly one thing: **the column cannot be searched, joined or
uniquely indexed.** So matching runs on a BLIND INDEX beside the ciphertext,
`bix1:<kid>:<b64u HMAC-SHA256(index_key, normalised_value)>`: deterministic,
equality-searchable, keyed rather than hashed, and leaking equality and nothing
else. `customers.driving_licence_bidx` is the same token under a different key
context.

⚠ **AND THERE IS NO `drivers_licence_last4` COLUMN.** `BR-CUS-092`(c) requires
last-four rendering, which is a READ PROJECTION — `service_request_reads`
computes it with `crypto.last_four()` at the moment it serves. Storing it would
put four characters of the identifier back in the clear beside the ciphertext
**while every test still passed**, which is the state the rule was written
about. The row says so three times; this is the fourth.

NO UNIQUE CONSTRAINT ON `drivers_licence_bidx`
===============================================
`customers 0036`'s reasoning, unchanged: a unique index is a one-way door that
refuses a write in production, at the counter, on evidence a clerk may have
typed wrong, and it cannot be relaxed without a migration. `BR-CUS-1022` rules
the behaviour the other way — *a duplicate identifier refuses to LINK and never
refuses to SAVE* — and behaviour belongs in the service layer, where it is
reversible.

NO NEW RLS POLICY, AND THE REASON IS STATED RATHER THAN ASSUMED
================================================================
RLS in this product is a TABLE policy, not a column one. `customers 0018` put
`FORCE` row-level security on `service_requests` against `app.tenant_id`, and
new columns on an existing table inherit it with nothing to add. Adding a policy
here would create a SECOND policy on the same table, which is how a permissive
OR-ed rule silently widens access — the reasoning `0031` stated for this same
table, repeated rather than assumed. `tests/test_br_cus_092_licence_and_dob_
capture.py` asserts `relforcerowsecurity` is still on and that both columns
exist, so the claim is checked rather than commented (hard-won law 1).

NO BACKFILL, AND NO KEY IS NEEDED TO RUN THIS
==============================================
Every existing row carries NULL in all three columns, because no row has ever
held any of these facts — `_clean_capture` refused `date_of_birth` by name and
refused every spelling of the licence as an unknown field. So there is nothing
to encrypt in place and `migrate` needs no `SBH_FIELD_ENCRYPTION_KEYS`; the key
is required the first time a value is WRITTEN, which is where hard-won law 3
wants the failure.

⚠ **THIS IS ALSO WHY THERE IS NO DATA MIGRATION AND WHY THAT MATTERS TODAY.**
`DEF-BIL-5382`, filed this morning: a migration runs as the APP role, so under
`FORCE` RLS it sees NO ROWS unless it sets `app.tenant_id` per tenant — and a
backfill that walks nothing reports success and does nothing. There is no data
to move here, so the trap is avoided by having no data step at all rather than
by remembering to set a GUC.

⚠ `DEF-892`: A MIGRATION NUMBER IS ALLOCATED TO A LANE, NEVER TAKEN FROM THE
WATERMARK — **AND THIS FILE IS THE WORKED EXAMPLE, BECAUSE IT WAS WRITTEN AS
`0047` AND THAT NUMBER WAS GONE BY THE TIME IT WAS PUSHED.** A sibling lane
landed `0047_cr094_service_request_applicant_messages` and `0048_cr094_request_
raises_the_job` while this one was being built. Two files numbered `0047`, both
depending on `0046`, is TWO LEAF NODES — and Django then refuses **every test in
the process** with *"Conflicting migrations detected; multiple leaf nodes in the
migration graph"*, which is not a test failure, names neither lane, and looks for
all the world like the tree is broken (hard-won law 12's `DEF-2872`). It was
caught by `makemigrations --check` at push time, after re-deriving from the
pinned tip; nothing else would have caught it, because the collision does not
exist in either lane's own checkout. Renumbered to `0049`, depending on `0048`,
the real leaf.

Reversible: three `AddField`s of nullable columns plus one `AddIndex`, so a
rollback drops ciphertext and index tokens and loses no fact that existed before
this migration ran.
"""

from django.db import migrations, models

import core.crypto


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0049_br_cus_1055_units_on_property"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicerequest",
            name="date_of_birth",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="drivers_licence",
            field=core.crypto.EncryptedTextField(
                blank=True, crypto_context="service_requests.drivers_licence", null=True
            ),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="drivers_licence_bidx",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="servicerequest",
            index=models.Index(
                fields=["tenant", "drivers_licence_bidx"], name="ix_sr_drivers_licence_bidx"
            ),
        ),
    ]
