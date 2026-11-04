"""customers 0060 — **the seller's link is ENDED, not destroyed.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list, so the marker is here because the PATH is the category,
not because the body is large (DEF-808). Ledger row:
`12-governance/09-human-review-ledger.md`.

`BR-CUS-1030` · PO ruling 2026-09-20, verbatim: *"we cannot override customer
id - seller and buyer cstmer id are unique those does not change"*. Keystone
`seller_link_ended_not_deleted` in `06-backend/tests/test_transfer_scenarios.py`,
which holds up **40 checks** across 19 of the 25 property-sale scenarios.

════════════════════════════════════════════════════════════════════════════
WHAT WAS WRONG
════════════════════════════════════════════════════════════════════════════
`transfers.reassign_account` did two destructive things when a property sold:

  1. `removed.delete()` — the SELLER's `customer_accounts` row was DESTROYED;
  2. `transfer.customer_id = buyer_id` — the transfer row's only customer
     column was OVERWRITTEN with the buyer's id.

Between them, **after a sale nothing in the database answers *who sold this
property*.** The account's history, the meters, the invoices and the payments
all survive in the seller's name — but the LINK saying this person ever held
this account is gone, and so is the transfer row's memory of them. The only
surviving trace is `audit_log`, which is pruned on a retention schedule.

⚠ **THAT IS A REAL LOSS AND NOT A TIDINESS COMPLAINT.** `BR-CUS-1030` makes a
transfer a REASSIGNMENT — one account, never closed, the customer changes — so
the account row itself carries no history of the change. A utility asked *"who
owned 114 Cypress before the Ndiayes"* has, today, no answer once the audit
retention window closes.

════════════════════════════════════════════════════════════════════════════
WHAT THIS ADDS — THREE COLUMNS AND ONE CONSTRAINT SWAP
════════════════════════════════════════════════════════════════════════════
**`customer_accounts.ended_at`** (nullable timestamptz). NULL means *this
person holds this account now*; a timestamp means *they held it until then*.

**`customer_accounts.ended_by_transfer_id`** (nullable uuid, NO foreign key).
WHICH sale ended it. Without this, an account sold twice has two ended rows and
nothing says which sale ended which — and the answer is not derivable from the
timestamps alone once a sale is back-dated, which `BR-CUS-1030` permits.

⚠ **NO FK, AND IT IS THE CALL 0048 ALREADY MADE FOR `transfers.request_id`, FOR
ITS REASONS**: `transfers` is `managed = False`, so an FK would be hand-written
DDL the model cannot express, and the link here is EVIDENCE rather than
integrity. A `PROTECT` FK would additionally make a transfer row undeletable
from the link side, which is backwards.

**`transfers.buyer_customer_id`** (nullable uuid, no FK, same reasoning). The
transfer row names the person who BOUGHT it, beside a `customer_id` that now
keeps naming the person who SOLD it.

⚠ **AND THAT IS A REVERSAL OF THIS FILE'S FIRST DRAFT, RECORDED RATHER THAN
QUIETLY CORRECTED.** The first version added `seller_customer_id` and left
`reassign_account` overwriting `customer_id` with the buyer, on the reasoning
that about forty call sites already read it as the buyer. **That was wrong, and
the property-sale suite says so in code rather than in prose:**
`_transfer_names_the_seller` asks

    Transfer.objects.filter(from_account_id=…, customer_id=seller_id).exists()

— so the contract is that **`customer_id` GOES ON NAMING THE SELLER**, and the
overwrite is itself the defect. Reading the suite's observation before building
to it is what caught this; the first design would have shipped, left the check
red, and made weakening the check the obvious next move.

⚠ **SO THE OVERWRITE IS REMOVED AND NOTHING IS RE-TAUGHT.** `transfer.customer`
means the same thing before and after commit — the account's customer when the
sale was raised, which is the seller — which is also how `reassign_account`
itself already read it one line earlier (`seller = transfer.customer`). The
BUYER gets a column of their own rather than borrowing one, so a record page can
render *sold by → bought by* from the row alone, permanently.

════════════════════════════════════════════════════════════════════════════
THE CONSTRAINT SWAP, WHICH IS THE PART THAT NEEDED THOUGHT
════════════════════════════════════════════════════════════════════════════
`uq_customer_accounts_pair` is UNIQUE on `(customer, account)`. Leaving it
alone would make this change **silently unable to represent a buy-back**: a
seller who later repurchases the same property cannot have a second row,
because their ended row already occupies the pair. The sale would fail on a
constraint violation with a message about uniqueness, naming neither person.

So the constraint becomes PARTIAL — unique on `(customer, account)` **WHERE
`ended_at IS NULL`**. One LIVE link per person per account, any number of
ended ones. The database still refuses the thing the original constraint
existed to refuse: the same person linked twice, live, to one account.

⚠ **THIS IS WHY THE CHANGE COULD NOT BE DONE IN PYTHON.** Filtering ended rows
out in the service layer and leaving `delete()` behind would keep the row count
right and lose the history anyway; keeping the row and filtering it in Python
leaves the uniqueness on the whole pair, so the buy-back still cannot be
written. The guarantee has to move in the database or it has not moved.

════════════════════════════════════════════════════════════════════════════
NO BACK-FILL, AND THE NULL IS A REAL ANSWER
════════════════════════════════════════════════════════════════════════════
⛔ **NOTHING IS BACK-FILLED, DELIBERATELY.** Every existing row reads
`ended_at = NULL`, which is exactly right: every link that exists today IS a
live link, because the old code deleted them the moment they stopped being one.
There is no set of rows needing a timestamp.

⚠ **AND THE SELLERS ALREADY DESTROYED CANNOT BE RECOVERED BY THIS MIGRATION.**
Sales committed before today deleted their seller's row; that information is in
`audit_log` if it has not yet been pruned, and nowhere else. A back-fill would
have to GUESS from a date and an account, and a guessed ownership record on a
row a regulator may read is worse than an honest absence. Stated here so the
next lane that wants one knows both halves before writing it.

⚠ **AND HAD A BACK-FILL BEEN WRITTEN IT WOULD HAVE REPORTED SUCCESS AND
CHANGED NOTHING** — a data migration runs as the APP role under RLS `FORCE`,
sees zero rows unless it sets `app.tenant_id` per tenant, and says so to
nobody. That was `DEF-BIL-5382`. 0048 records the same trap for the same
reason.

════════════════════════════════════════════════════════════════════════════
TWO MECHANISMS, BECAUSE ONE TABLE IS UNMANAGED — 0028 AND 0048's SPLIT
════════════════════════════════════════════════════════════════════════════
`customer_accounts` is an ordinary managed model, so `AddField` IS the DDL.

`transfers` is `managed = False` (its DDL is 0021's raw SQL), so Django's
schema editor keeps neither model nor table in step for it. Both halves are
therefore explicit:

  · `RunPython(add_transfer_buyer, drop_transfer_buyer)` issues the real
    `ALTER TABLE`;
  · `AddField` puts the field into migration STATE and, because
    `Meta.managed = False` makes `can_migrate()` False, emits no DDL of its own.

The `ALTER TABLE` text is FROZEN here and never derived from the live model —
0021's docstring records why: DDL that reaches into the current model class
silently changes what it builds every time somebody edits the model, which is
how a fresh database and an upgraded one come to disagree.

⚠ **SQLITE SPELLING IS CARRIED BECAUSE THE DEFAULT TEST SUITE RUNS ON SQLITE**
(`config/settings/test.py` hardcodes it — CLAUDE.md hard-won law 14). A `uuid`
column there is `char(32)`.

════════════════════════════════════════════════════════════════════════════
NO RLS OPERATION IS NEEDED
════════════════════════════════════════════════════════════════════════════
A policy covers a TABLE, not a column list: `customer_accounts` got ENABLE +
FORCE and its policy with the table, and `transfers` in 0021. New columns are
inside the existing policy from the moment they exist.

════════════════════════════════════════════════════════════════════════════
REVERSIBLE, AND WHAT REVERSING COSTS
════════════════════════════════════════════════════════════════════════════
Every operation reverses. **Reversing DESTROYS the ownership history this
migration exists to keep** — `ended_at`, the sale that ended each link, and
every `buyer_customer_id` — and restores a unique constraint that a buy-back
row would then violate, so a reverse on a database that has taken one will
fail on the constraint rather than silently truncating. That is the safer
direction and is left deliberate.
"""

from django.db import migrations, models
from django.db.models import Q

#: The `ALTER TABLE` for the UNMANAGED `transfers`. Frozen text, never derived
#: from the live model — see the docstring.
ADD_TRANSFER_BUYER_PG = "ALTER TABLE transfers ADD COLUMN buyer_customer_id uuid NULL;"
ADD_TRANSFER_BUYER_SQLITE = (
    "ALTER TABLE transfers ADD COLUMN buyer_customer_id char(32) NULL;"
)
DROP_TRANSFER_BUYER = "ALTER TABLE transfers DROP COLUMN buyer_customer_id;"

#: ⚠ **NO INDEX ON `buyer_customer_id`, AND THAT IS A CHOICE.** Nothing pages
#: or filters transfers BY SELLER today: the record page reads one transfer by
#: its reference, and the Transfers tab pages by account and date. An index
#: costs every commit a write and buys a read nobody performs. `NFR-3`'s
#: pagination duty is unaffected — this column is not a sort key.
#: The day a *"properties this person has sold"* list is built, it needs one.


def add_transfer_buyer(apps, schema_editor):  # type: ignore[no-untyped-def]
    """The seller column on the unmanaged `transfers` table."""
    vendor = schema_editor.connection.vendor
    schema_editor.execute(
        ADD_TRANSFER_BUYER_SQLITE if vendor == "sqlite" else ADD_TRANSFER_BUYER_PG
    )


def drop_transfer_buyer(apps, schema_editor):  # type: ignore[no-untyped-def]
    schema_editor.execute(DROP_TRANSFER_BUYER)


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0059_br_cus_1050_deposit_assessed"),
    ]

    operations = [
        # ── customer_accounts (managed): AddField IS the DDL ─────────────────
        migrations.AddField(
            model_name="customeraccount",
            name="ended_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customeraccount",
            name="ended_by_transfer_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        # ── the constraint swap — drop the whole-pair rule, add the live one ─
        # Order matters: the old constraint must go before the new one is
        # added, or a database already holding a buy-back could not satisfy
        # both at once during the transition.
        migrations.RemoveConstraint(
            model_name="customeraccount",
            name="uq_customer_accounts_pair",
        ),
        migrations.AddConstraint(
            model_name="customeraccount",
            constraint=models.UniqueConstraint(
                fields=["customer", "account"],
                condition=Q(ended_at__isnull=True),
                name="uq_customer_accounts_pair_live",
            ),
        ),
        # ── transfers (unmanaged): the DDL, then the state ───────────────────
        migrations.RunPython(add_transfer_buyer, drop_transfer_buyer),
        migrations.AddField(
            model_name="transfer",
            name="buyer_customer_id",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
