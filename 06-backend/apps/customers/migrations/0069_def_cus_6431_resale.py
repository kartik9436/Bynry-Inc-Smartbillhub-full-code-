# ── Trace ──────────────────────────────────────────────
# Change:   `DEF-CUS-6431` (2026-09-24) — selling an account a SECOND time
#           failed with a server error: `uq_transfers_to_account` let an account
#           be the incoming half of one transfer, EVER.
# Rules:    `BR-CUS-1030` (a sale reassigns ONE account, so the commit writes
#           `to_account_id = from_account_id`) · CLAUDE.md hard rule 1 (the RLS
#           policy on `transfers` is untouched) · hard rule 4 (no row is edited
#           or deleted — this changes an index and nothing else)
# Tests:    06-backend/tests/test_def_cus_6431_resale.py
# ───────────────────────────────────────────────────────
"""customers 0069 — **a property can be sold more than once.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list, so the marker is here because the PATH is the category.
Ledger row: `12-governance/09-human-review-ledger.md`, *"A property can be sold
more than once"*.

WHAT WAS WRONG
--------------
0021 wrote, for the transfer as it was THEN — a customer moving, which OPENED a
new account at the new address:

    -- An account may be the INCOMING half of exactly one transfer, ever. Two
    -- transfers pointing at one new account would each claim to have opened it.
    CREATE UNIQUE INDEX uq_transfers_to_account
        ON transfers (tenant_id, to_account_id) WHERE to_account_id IS NOT NULL;

`BR-CUS-1030` (PO, 2026-09-01) turned a transfer into a SALE that reassigns the
account it started from, and `reassign_account` writes `to_account_id =
from_account_id`. From then on the index meant *an account may be SOLD once,
ever*: the second sale of A-11512 died on a duplicate key inside the commit and
reached the clerk as *"Something went wrong on our side."*

WHAT THIS DOES — ONE INDEX NARROWED, NOTHING ELSE
-------------------------------------------------
The index is replaced by `uq_transfers_opened_account`, the same columns with
one more clause in the predicate:

    WHERE to_account_id IS NOT NULL AND to_account_id <> from_account_id

* **A SALE (`to = from`) is outside it**, so an account can be sold any number
  of times, one after another.
* **The old invariant is KEPT where it meant something.** A transfer that
  OPENED a different account (the pre-`BR-CUS-1030` shape, which rows written
  between 2026-08-25 and 2026-09-01 may carry) still cannot share that account
  with a second transfer claiming to have opened it.
* **ONE OPEN SALE AT A TIME is NOT this index's job and never was.** That is
  `uq_transfers_open_from` (0021), untouched here, and `transfers.sale_refusal`
  asks it by name before any write (`from_account_already_being_sold`).

It is RENAMED rather than re-created under the old name, so an error or a query
plan naming the index tells a reader which rule refused.

Frozen DDL text, identical on both vendors (SQLite supports a partial index
with a column comparison), never derived from the live model — 0021's
reasoning. The `Transfer` model is `managed = False` and holds no index in
migration state, so there is no state operation.

REVERSIBLE, WITH ONE CONDITION STATED
-------------------------------------
The reverse re-creates the once-ever index, and PostgreSQL refuses it with a
unique violation the moment any account has been sold twice. That is the right
answer: the only way to satisfy it is to delete a real sale, which hard rule 4
forbids. **Once a resale exists, roll FORWARD, not back.**
"""

from django.db import migrations

FORWARD = (
    "DROP INDEX IF EXISTS uq_transfers_to_account;",
    """
    CREATE UNIQUE INDEX uq_transfers_opened_account
        ON transfers (tenant_id, to_account_id)
        WHERE to_account_id IS NOT NULL AND to_account_id <> from_account_id;
    """,
)

REVERSE = (
    "DROP INDEX IF EXISTS uq_transfers_opened_account;",
    """
    CREATE UNIQUE INDEX uq_transfers_to_account
        ON transfers (tenant_id, to_account_id)
        WHERE to_account_id IS NOT NULL;
    """,
)


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0068_br_cus_1081_seller_recorded_by_name"),
    ]

    operations = [
        migrations.RunSQL(sql=list(FORWARD), reverse_sql=list(REVERSE)),
    ]
