"""customers 0038 — a COMPANY's identity: its Tax ID, encrypted, with a blind index.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering AND app-layer field
encryption are both on CLAUDE.md's sensitive-paths list, and this migration is
on both. The ledger row is in `12-governance/09-human-review-ledger.md`. The
marker is here because the PATH is the category, not because the body is large
(DEF-808).

WHICH RULING ASKED FOR THIS, AND WHAT IT COLLIDED WITH
======================================================
`CR-056` wave 6. **PO ruling 2026-09-01, verbatim:** *"Customer can be person or
company - in case of person , if we have SSN, or DL or Phone number, we create
the Customer ID and attached these to custoemr ID ; if it is Company then we ask
for Tax ID"*.

`customers 0036` built the PERSON half of that sentence a day earlier — a date
of birth plus an app-layer-encrypted Social Security number, driving licence and
phone. **The company half did not exist at all**, and the rule that was supposed
to recognise one could not: `BR-CUS-089` is signed and verbatim — *a strong match
is NAME + DATE OF BIRTH + ONE GOVERNMENT ID* (PO 2026-08-25, closing `OQ-364`) —
and **a company has no date of birth.** Read literally the signed rule made every
company permanently unmatchable, which nobody intended.

**The decision log of 2026-09-01 narrows rather than reverses it.** `BR-CUS-089`
is a rule about PERSONS and stands unchanged for them; a company is matched on
its Tax ID (`BR-CUS-1022`). This column is that identifier, and
`apps/customers/identity_match.py` is where the narrowing becomes a branch
instead of a paragraph.

⚠ `tenancy.ein` IS NOT THIS COLUMN AND MUST NOT BE REUSED AS IT
===============================================================
`tenancy.ein` is the **UTILITY's own** federal tax number, on another module's
table, written when the tenant was provisioned. A customer's Tax ID is a
different fact about a different party; reading the tenant's to identify a
customer would be a cross-module read of the wrong row, and B2 §2 keeps each
module's tables its own.

⚠ AND `tenancy.ein` IS THE COUNTER-EXAMPLE, NOT THE PRECEDENT. It holds nine
digits **in plaintext** against a closed ruling, and says so in its own words —
`apps/tenancy/services.py`: *"ein stored as plain 9 digits for now — the OQ-016
ruling (app-layer encryption)"*. `BR-CUS-092`'s own row names that as the reason
an SSN had to be done properly: *"A tax identifier is ALREADY stored in
plaintext against a closed ruling; an SSN is the same shape with worse
consequences."* This column does not repeat it.

WHY IT IS ENCRYPTED — SIGNED LAW, NOT THIS LANE'S TASTE
=======================================================
`OQ-016` is **CLOSED**: *"app-layer encryption for high-sensitivity columns,
disk for rest (PO R6)"*, B2 §6. `BR-CUS-092` (PO 2026-08-24, settling `DEF-632`,
verbatim *"we have to take SSn and Driver lience and follow PII rules"*) makes
the shape specific for a person's two identifiers: captured, encrypted at the
application layer, **last four only on every read path.** A company's tax
identifier is the same shape — a government-issued number that identifies one
party and is worth stealing — so it is written through the same encryptor under
the same closed ruling rather than under a new rule this lane invented.

`core.crypto` is that encryptor, built 2026-08-27 for `service_requests.ssn`:
AES-256-GCM, a fresh 96-bit nonce per write, and additional authenticated data
binding a ciphertext to the column it was written for — so a value lifted out of
`customers.tax_id` and dropped into `customers.ssn` RAISES rather than
decrypting. `crypto_context="customers.tax_id"` is what binds it.

WHY THERE IS A `tax_id_bidx` TWIN
=================================
The scheme is RANDOMISED — the same Tax ID encrypts differently every time —
which costs exactly one thing: **the column cannot be searched, joined or
uniquely indexed.** `core.crypto.EncryptedTextField.get_lookup` refuses every
lookup but `__isnull`, loudly, because a silently-empty queryset on an identity
match is a wrong answer that looks like *"no such customer"* on the one path
that can move somebody else's money.

So matching runs on a BLIND INDEX beside the ciphertext —
`bix1:<kid>:<b64u HMAC-SHA256(index_key, normalised_value)>` — deterministic,
equality-searchable, leaking equality and nothing else. It is KEYED, not hashed:
a bare SHA-256 of a nine-digit number falls to an afternoon of brute force
against a database dump, and the HMAC key is not in the database.
`crypto.normalise_identifier` folds `12-3456789` and `123456789` to one token, so
a clerk who types the hyphen on Tuesday and omits it on Thursday still matches.

NO UNIQUE CONSTRAINT ON `tax_id_bidx`, AND THIS TIME IT IS A RULING
===================================================================
`0036` left the SSN index non-unique because the ruling that would have licensed
one (`CR-056` R3) was **reconstructed** rather than quoted. That reasoning has
since been replaced by something stronger: **the PO ruled it directly on
2026-09-01** — *a duplicate identifier refuses to LINK, and never refuses to
SAVE.* A database uniqueness rule is a one-way door: a clerk who mistypes one
digit of a real customer's number is stopped at the counter and cannot open the
account at all, and undoing the rule later means finding and merging whatever was
created while it stood. **The stricter rule can still be added once real data
shows how often a duplicate happens; the reverse is not true.**

What is enforced instead is not nothing: the match is computed, the collision is
visible, and the LINK — the thing that would carry a deposit — is refused by
name, showing **no figure at all**.

NO NEW RLS POLICY, AND THE REASON IS STATED RATHER THAN ASSUMED
===============================================================
RLS in this product is a TABLE policy, not a column one. The customers
migrations already put `FORCE` row-level security on `customers` against
`app.tenant_id`; a new column on an existing table inherits it with nothing to
add. Adding a policy here would create a SECOND policy on the same table, which
is how a permissive OR-ed policy silently widens access — the reasoning `0031`
states for `service_requests` and `0036` repeats for these columns' siblings.

NO BACKFILL, AND NO KEY IS NEEDED TO RUN THIS
=============================================
Every existing row carries NULL in both columns, because no row has ever held
this fact — the column did not exist. So there is nothing to encrypt in place and
`migrate` needs no `SBH_FIELD_ENCRYPTION_KEYS`; the key is required the first
time a value is WRITTEN, which is where hard-won law 3 wants the failure.
`EncryptedTextField` subclasses `TextField`, so the column type is plain `text`
and the ciphertext envelope lives inside it.

⚠ `DEF-892`: A MIGRATION NUMBER IS ALLOCATED TO A LANE, NEVER TAKEN FROM THE
WATERMARK. `customers 0038` is this lane's reservation, recorded in
`12-governance/14-id-reservations.md`, and it was RE-DERIVED from the branch tip
at push time (law 11 — `DEF-1787`: two lanes in separate worktrees compute
`max + 1` correctly and get the same number). It depends on
`0037_cr056_w1_account_on_the_premises`, the real leaf. ⚠ `0029` is STILL
deliberately not taken — `0030` already depends on `0028`, so a second child of
`0028` would make two leaves and Django would demand a merge migration.

Reversible: every operation is an `AddField` of a nullable column plus one
`AddIndex`, so a rollback drops ciphertext and index tokens and loses no fact
that existed before this migration ran.
"""

from django.db import migrations, models

import core.crypto


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0037_cr056_w1_account_on_the_premises"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="tax_id",
            field=core.crypto.EncryptedTextField(
                blank=True, crypto_context="customers.tax_id", null=True
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="tax_id_bidx",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="customer",
            index=models.Index(fields=["tenant", "tax_id_bidx"], name="ix_customers_tax_id_bidx"),
        ),
    ]
