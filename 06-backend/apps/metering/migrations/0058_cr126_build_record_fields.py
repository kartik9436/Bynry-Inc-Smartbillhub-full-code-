"""metering 0058 — the four facts the build record draws and nothing stored
(2026-09-21, `CR-126-BRC07`).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-21 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

FOUR COLUMNS ON ONE TABLE. THREE ARE ANSWERS A CLERK ALREADY TYPED AND THE
PRODUCT DISCARDED; THE FOURTH IS THE BILL THIS BUILD ITSELF RAISED.

──────────────────────────────────────────────────────────────────────────────
WHAT WAS MEASURED FIRST, BECAUSE ONLY A QUARTER OF WHAT WAS REPORTED MISSING
IS ACTUALLY MISSING
──────────────────────────────────────────────────────────────────────────────
Blueprint pages 98–107 were RENDERED AS IMAGES and read that way (`B14` rule
42). Every drawn element was then traced to a source in the running code before
a single column was proposed. **Of the eight elements reported as having no
source anywhere, five already have one:**

  * the customer-class chip (`Apartment block`) is `premises.premises_type`,
    which the drawing itself proves — `THE PREMISE · STEP 2`'s first row is
    *Premise type · Apartment block*, the same words as the chip. **No column.**
  * `Approved by` is `service_requests.decided_by`, written by
    `service_request_service.approve` alongside `decided_at`. It is the
    provenance block's own field and is legitimately absent on a build nobody
    approved. **No column.**
  * `Activated at` is `connections.activated_at`, a column since W6 and written
    by `refresh_connection_state()` the moment a build reaches `activated`.
    **No column.**
  * `Owner or developer` is the payer account's customer display name.
    Blueprint p106 rules it there in as many words: *"the name belongs to the
    account that pays."* **No column — derived by walking.**
  * `External system reference` is that same customer's legacy id
    (`customers.external_ref`, `BR-CUS-054`). **No column — derived by
    walking.**

Adding a column for any of those five would have created a second, drifting
copy of a fact this product already holds. That is the `DEF-127` shape, and on
`Owner or developer` it would have been the address rule's shape too: one
record, one home.

──────────────────────────────────────────────────────────────────────────────
1 · `owner_type` · `units_prefix` · `scope` — COLLECTED, THEN THROWN AWAY
──────────────────────────────────────────────────────────────────────────────
All three are on step 1 of the New Connect wizard today and none of them
survives the commit.

  * `scope` and `units_prefix` ARRIVE on `POST /connections/commit` and
    `commit_new_connect` answers with a stated absence saying so, verbatim:
    *"Step 1's scope and unit prefix arrive on this payload and nothing reads
    them: connections has no column for either."* (`DEF-CUS-5435`.)
  * `owner.kind` — the drawn **Owner type**, one of *builder or developer ·
    property owner · landlord · occupier* — is deleted from the payload by
    `_owner_block_in_the_doors_language` before it reaches the accounts door,
    correctly, because `customers.kind` is `person`/`company` and refuses all
    four by name (`DEF-MET-5438`). It is mapped nowhere and stored nowhere.

**WHY THE BUILD AND NOT THE CUSTOMER.** `owner_type` classifies a
RELATIONSHIP, not a party: one company is a developer on the estate it is
building and a landlord on the block it already owns. Putting it on
`customers` means the second build silently rewrites the first build's answer.

**WHY THE BUILD AND NOT THE PREMISES.** `units_prefix` and `scope` describe how
THIS build was shaped — how many units the pattern made and whether a common
area was included. A second build at the same address may be shaped differently.

⚠ **`scope` IS FREE TEXT AND CARRIES NO CHECK CONSTRAINT, DELIBERATELY.** The
screen validates a vocabulary the server has never seen (the conformance
measurement records this as *"a business rule living in a browser"*), and
which words are lawful is not a question this migration may settle by writing
one of them into a constraint. The column accepts what the wizard sends; the
vocabulary is a ruling somebody still owes.

──────────────────────────────────────────────────────────────────────────────
2 · `quote_invoice_id` — THE BILL THE BUILD RAISED, AND COULD NOT FIND AGAIN
──────────────────────────────────────────────────────────────────────────────
Since 2026-09-16 `_post_connection_quote` raises this build's quote as a real
receivable through `billing.fee_bill.raise_and_issue_quote_bill`, and hands the
invoice's id and number back **on the commit response only**. Nothing wrote
either down. The single durable record is a stamp on `service_request_fees`,
written through `seams.mark_request_quote_invoiced` — and that hangs off the
REQUEST.

⚠ **PO RULING 2026-09-21 IS WHY THAT IS NOT GOOD ENOUGH.** Verbatim: an
approved application *"may create a new conenct request - as draft request -
this request is new work and recognized seperately from applcaition and hence
we should not make it dependent on applciation #"*. A build raised directly has
no request at all, so with the invoice recorded only against the request, such a
build can never name its own bill — and the record's fifth tile, **OUTSTANDING**,
is underivable for ever.

With the id on the row, `Quoted`, `Taken`, `Clearing date` and `Outstanding`
are all DERIVED: billing owns the total, payments owns what has been allocated
against it (`payments.billing_seam.allocated_so_far`, payments' own read of
payments' own table). **No figure is stored twice and no balance is cached** —
`accounts.balance` being a cache that nothing here reads is `BR-CUS-015`, and
`DEF-127` is what a second copy of a money figure costs.

**A PLAIN UUID, NOT A FOREIGN KEY.** `invoices` belongs to BILLING. The B11 F-3
deferred-FK convention already governs this exact case one class down —
`connection_services.gate_order_id` names a work order the same way and says so
— and B2 §2's reviewed cross-module FK set is not widened on a read lane's
authority.

──────────────────────────────────────────────────────────────────────────────
NULLABLE THROUGHOUT · NO DATA MIGRATION · NO RLS LOOP, AND WHY
──────────────────────────────────────────────────────────────────────────────
Every one of the four is NULL on every existing row and stays that way.

**THERE IS NO BACKFILL AND THERE MUST NOT BE.** NULL here means *nobody was
asked*, which is the literal truth: the three step-1 answers were typed and
discarded, and no record of them survives anywhere to recover. Writing a
default — `scope='premise'`, say — would be this migration answering, on behalf
of a clerk, a question they were actually asked. That is hard-won law 3's shape
for data: the unsafe reading is the one somebody has to type.

`quote_invoice_id` is likewise not backfilled. It *could* be recovered for
builds that have a request, by reading `service_request_fees`' stamp — and it
could NOT be for any build without one, which is precisely the population the
ruling above is about. A backfill that silently covers half a table and leaves
the interesting half empty is worse than an honest NULL, because the empty half
then reads as *this build raised no bill*.

⚠ **SO THIS MIGRATION WRITES NO ROWS AND THEREFORE SETS NO `app.tenant_id`.**
That is stated rather than left to be inferred, because `DEF-BIL-5382` is the
opposite case: a data migration on a tenant table under RLS `FORCE` that does
not set `app.tenant_id` per tenant sees **zero rows**, changes nothing, and
reports success. `rating/0039` and `rating/0042` carry the per-tenant loop for
any lane that needs one. This one needs none: `AddField` is DDL, it is not
subject to row-level security, and there is no `RunPython` here at all.

⚠ **LEAF CHECKED BEFORE NUMBERING** (`DEF-CUS-6041`). `metering`'s leaf at the
moment this was written is `0057_cr112_gis_keys`, and it is the sole dependency
below. Two leaf nodes kill every test in the process before collection, with an
error that names neither lane.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0057_cr112_gis_keys"),
    ]

    operations = [
        migrations.AddField(
            model_name="connection",
            name="owner_type",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="connection",
            name="units_prefix",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="connection",
            name="scope",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="connection",
            name="quote_invoice_id",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
