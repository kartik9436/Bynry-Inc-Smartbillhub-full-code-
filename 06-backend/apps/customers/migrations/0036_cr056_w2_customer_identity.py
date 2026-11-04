"""customers 0036 — identity ON THE CUSTOMER, and how a link came to be made.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering AND app-layer field
encryption are both on CLAUDE.md's sensitive-paths list, and this migration is
on both. The ledger row is in `12-governance/09-human-review-ledger.md`. The
marker is here because the PATH is the category, not because the body is large
(DEF-808).

WHAT THIS BUILDS, AND WHICH RULING ASKED FOR IT
===============================================
`CR-056` wave 2, tasks 11 and 15. Until today the `customers` row held a
number, a name, a person-or-company flag and a legacy reference — and **nothing
that identifies a human being**. CR-056 §4, verbatim: *"What makes an owner one
person today is his NAME, unique per utility, case-insensitive. A. Kulkarni and
Ajinkya Kulkarni are two landlords and nothing objects."*

WHY THESE THREE COLUMNS ARE ENCRYPTED AND THE FOURTH IS NOT
============================================================
**It is signed law and not this lane's taste.** `OQ-016` is CLOSED — *"app-layer
encryption for high-sensitivity columns, disk for rest (PO R6)"*, B2 §6 — and
`BR-CUS-092` (PO 2026-08-24, settling `DEF-632`, verbatim *"we have to take SSn
and Driver lience and follow PII rules"*) makes it specific: the Social Security
number and the driving licence are **captured, encrypted at the application
layer, and shown as the last four digits only**. `core.crypto` is that
encryptor, built 2026-08-27 for `service_requests.ssn`: AES-256-GCM, a fresh
96-bit nonce per write, and additional authenticated data binding a ciphertext
to the column it was written for — so a value lifted out of `customers.ssn` and
dropped into `service_requests.ssn` RAISES rather than decrypting.

`phone` joins them because CR-056's R3 names it as identity evidence and a
telephone number is the single most re-used handle on a person a small utility
holds; it costs nothing to encrypt (reads decrypt transparently) and the blind
index keeps it matchable.

**`date_of_birth` is a plain `date` and that is deliberate.** It is the second
of `BR-CUS-089`'s three signed criteria, so it has to be COMPARABLE, and
`contacts.dob` — the one place this product already holds a date of birth — is
a plain `date` too. Encrypting one of the two would mean the reconciliation in
CR-056 task 12 could not compare them at all. A date of birth is also not one
of the two identifiers `BR-CUS-092` legislates, and widening a signed
encryption rule to a column it does not name would be inventing law.

WHY EACH ENCRYPTED COLUMN HAS A `*_bidx` TWIN
=============================================
The scheme is RANDOMISED — the same SSN encrypts differently every time — which
is the correct choice for a nine-digit secret typed into a public form, and it
costs exactly one thing: **the column cannot be searched, joined or uniquely
indexed.** `core.crypto.EncryptedTextField.get_lookup` refuses every lookup but
`__isnull`, loudly, because a silently-empty queryset on an identity match is
the failure `BR-CUS-089` can least afford.

So matching runs on a BLIND INDEX beside the ciphertext — `bix1:<kid>:<b64u
HMAC-SHA256(index_key, normalised_value)>` — which is deterministic,
equality-searchable, and leaks equality and nothing else. It is KEYED, not
hashed: a bare SHA-256 of a nine-digit number falls to an afternoon of brute
force against a database dump, and the HMAC key is not in the database.

`BR-CUS-092`'s own row records the gap this closes, verbatim: *"NO BLIND INDEX,
so BR-CUS-089's matcher is still unbuilt and the column cannot be searched"*,
and `service_requests.ssn`'s docstring says the index *"is added by the lane
that builds the matcher, which is the only lane that can prove it works"*.
This is that lane; `apps/customers/identity_match.py` is that matcher.

NO UNIQUE CONSTRAINT ON `ssn_bidx`, AND THE REASON IS A RULING'S FORM
=====================================================================
It is tempting: one Social Security number, one person, enforced by the
database. **CR-056's ruling R3 — *"the Customer # is keyed on IDENTITY and
reused, never allocated twice to one person"* — is RECONSTRUCTED, not verbatim**
(CR-056 §0's own table stamps it so, and §0 says a reconstructed ruling *"must
be confirmed before anything in W1–W6 is built on them"*). A unique index is a
one-way door: it refuses a write in production, at the counter, on evidence a
clerk may have typed wrong, and it cannot be relaxed without a migration.

So R3's BEHAVIOUR is built in the service layer, where it is reversible — a
presented identity that strongly matches an existing customer LINKS to them
rather than making a second person — and the constraint is not. Recorded in
`12-governance/02-decision-log.md` rather than left for the next lane to
rediscover.

`customer_accounts` GAINS THE FOUR COLUMNS `service_requests` ALREADY HAS
=========================================================================
`BR-CUS-089` requires the tier and its confirmer to be STORED, and until today
the only place they could be stored was a service request:
`apps/customers/discounts._stored_match` reads `service_requests.match_tier` and
nothing else, and says in its own docstring that *"a move-in that did not come
from a service request has no stored tier at all, and is refused rather than
defaulted"*. An account opened at the counter could therefore never carry a
returning customer's **$153.50** (WE-7/GT-23 ❄️), however well the clerk had
identified them. These four columns are the second store.

NO NEW RLS POLICY, AND THE REASON IS STATED RATHER THAN ASSUMED
===============================================================
RLS in this product is a TABLE policy, not a column one. The customers
migrations already put `FORCE` row-level security on `customers` and
`customer_accounts` against `app.tenant_id`; new columns on an existing table
inherit it with nothing to add. Adding a policy here would create a SECOND
policy on the same table, which is how a permissive OR-ed policy silently
widens access — the reasoning `0031` states for `service_requests`, repeated
here rather than assumed.

NO BACKFILL, AND NO KEY IS NEEDED TO RUN THIS
==============================================
Every existing row carries NULL in all seven columns, because no row has ever
held any of these facts. So unlike the `tenancy.ein` migration there is nothing
to encrypt in place and `migrate` needs no `SBH_FIELD_ENCRYPTION_KEYS` — the
key is required the first time a value is WRITTEN, which is where hard-won law
3 wants the failure. `EncryptedTextField` subclasses `TextField`, so the column
type is plain `text` and the ciphertext envelope lives inside it.

⚠ `DEF-892`: A MIGRATION NUMBER IS ALLOCATED TO A LANE, NEVER TAKEN FROM THE
WATERMARK. `customers 0036` is this lane's reservation, recorded in
`12-governance/14-id-reservations.md`. It depends on `0035_cr052_w0_disconnect_
at_the_cut`, the real leaf. ⚠ `0029` is STILL deliberately not taken — `0030`
already depends on `0028`, so a second child of `0028` would make two leaves and
Django would demand a merge migration.

Reversible: every operation is an `AddField` of a nullable column plus three
`AddIndex`, so a rollback drops ciphertext and index tokens and loses no fact
that existed before this migration ran.
"""

import django.db.models.deletion
from django.db import migrations, models

import core.crypto


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0035_cr052_w0_disconnect_at_the_cut"),
        ("identity", "0001_initial"),
    ]

    operations = [
        # ── the customer becomes a person (task 11) ────────────────────────
        migrations.AddField(
            model_name="customer",
            name="date_of_birth",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="ssn",
            field=core.crypto.EncryptedTextField(
                blank=True, crypto_context="customers.ssn", null=True
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="ssn_bidx",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="driving_licence",
            field=core.crypto.EncryptedTextField(
                blank=True, crypto_context="customers.driving_licence", null=True
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="driving_licence_bidx",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="phone",
            field=core.crypto.EncryptedTextField(
                blank=True, crypto_context="customers.phone", null=True
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="phone_bidx",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="customer",
            index=models.Index(fields=["tenant", "ssn_bidx"], name="ix_customers_ssn_bidx"),
        ),
        migrations.AddIndex(
            model_name="customer",
            index=models.Index(
                fields=["tenant", "driving_licence_bidx"], name="ix_customers_dl_bidx"
            ),
        ),
        migrations.AddIndex(
            model_name="customer",
            index=models.Index(fields=["tenant", "phone_bidx"], name="ix_customers_phone_bidx"),
        ),
        # ── how a link came to be made (task 15) ───────────────────────────
        migrations.AddField(
            model_name="customeraccount",
            name="match_tier",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customeraccount",
            name="match_basis",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customeraccount",
            name="match_confirmed_by",
            field=models.ForeignKey(
                blank=True,
                db_column="match_confirmed_by",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="identity.user",
            ),
        ),
        migrations.AddField(
            model_name="customeraccount",
            name="match_confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
