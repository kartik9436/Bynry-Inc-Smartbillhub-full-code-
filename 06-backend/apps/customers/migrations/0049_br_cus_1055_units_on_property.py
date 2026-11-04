"""customers 0047 — how many units the applicant says are on the property.
HUMAN-OWNED (migration ORDERING is a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-15 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human."*) Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

`CR-094-BRC01` wave 1 lane B · `BR-CUS-1055` · `DEF-CUS-5385`. PO ruling
2026-09-15, verbatim: *"we need to build this"*, on the Accounts blueprint's
`How many units are on this property? *` (p077, helped by *"What the applicant
says is there"*) and its `Units on the property · 6` on the request's own screen
(p082).

ONE NULLABLE COLUMN, AND THE THREE THAT ARE NOT HERE
──────────────────────────────────────────────────────────────────────────────
⛔ **THIS MIGRATION CARRIED `address_city_as_given`, `address_state_as_given`
AND `address_postal_code_as_given` FOR ABOUT AN HOUR ON 2026-09-15, AND THE
PRODUCT OWNER TOOK THEM OUT BEFORE IT WAS PUSHED.** Verbatim: *"if we have unit
or street address then we should take it from premises/Unit - it means its a
search and if not foudn them alow user to add them"*. The town, the state and
the postcode on the drawn address line are **the matched premises' facts, read
by walking to it** — `CLAUDE.md` hard rule 8 / `BR-MET-1161` — and three such
columns would have been the fourth address home `G85` exists to refuse. The
read model walks instead (`service_request_reads.resolved_place`), which is how
`DEF-CUS-3653` fixed the account header.

It is written down here because a migration is the one file a later lane reads
to find out what a table was *meant* to hold, and *"they were considered and
refused"* is a different fact from *"nobody thought of it"*.

NO BACKFILL, AND THE ABSENCE OF ONE IS THE POINT
──────────────────────────────────────────────────────────────────────────────
There is nothing to backfill FROM. The drawing's own annotation says where the
number went instead: *"the number lives only in whatever the clerk typed into
the notes, which no screen and no rule can read."* Free text is not a source;
parsing four hundred notes into an integer would be inventing the applicant's
words. Every existing row keeps NULL, which a screen renders as *not supplied*.

⚠ **AND THAT IS WHY THIS MIGRATION HAS NO `RunPython` AT ALL.** A data migration
runs as the APP role under RLS `FORCE` and sees NOTHING unless it sets
`app.tenant_id` per tenant — `DEF-BIL-5382`, on 2026-09-15: it reported OK and
changed nothing. A migration that writes no rows cannot fail that way, and one
with no rows to write should not pretend to.

THE RLS POLICY NEEDS NO CHANGE, AND IT IS CHECKED RATHER THAN ASSUMED
──────────────────────────────────────────────────────────────────────────────
`customers/0018` created the `service_requests` policy with no `FOR` clause,
which in PostgreSQL means `FOR ALL` — `USING (tenant_id = …)` and
`WITH CHECK (tenant_id = …)` already cover every statement against this table.
Adding a column changes nothing about which rows a role may see, so no second
policy is written here.

NO MAXIMUM, BY RULE
──────────────────────────────────────────────────────────────────────────────
`NFR-5` forbids a hard cap anywhere in this product and `CLAUDE.md` makes that
flexibility load-bearing rather than tidy, so no `CheckConstraint` bounds how
big a building may be. The service refuses a value that is not a whole number
and refuses a negative one; zero is accepted, because vacant land with a
connection request on it genuinely has none.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    # ⚠ **THIS WAS `0047`, THEN `0048`, AND A SIBLING TOOK BOTH BEFORE IT
    # PUSHED.** Three lanes of one wave each took the next free migration number
    # from their own checkout, correctly, and a sibling in its own worktree has
    # its file in NONE of the places a listing can see until it pushes
    # (`CLAUDE.md` law 11). It was caught twice by re-deriving from the pinned
    # tip at push time, which is the one moment the answer can be final.
    #
    # **It matters more here than for a register row.** Two leaves in the
    # migration graph make Django refuse **every test in the process** with
    # `Conflicting migrations detected; multiple leaf nodes in the migration
    # graph` — an error that names neither lane and looks like a broken tree.
    # That was reproduced deliberately before it was fixed.
    dependencies = [
        ("customers", "0048_cr094_request_raises_the_job"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicerequest",
            name="units_on_property",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
