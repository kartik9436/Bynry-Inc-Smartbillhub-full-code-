"""customers 0058 — **the move-out reason finally has somewhere to go.**

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-09-20 under the PO ruling of 2026-08-09 (*"AI will do it; we will review
it later as human"*). Ledger row: `12-governance/09-human-review-ledger.md`.

PO ruling 2026-09-20, **option A**, decision log *"TEN MOVE-OUT RULINGS IN ONE
SITTING"* item 3: **the move-out reason gets a column.** `BR-CUS-030`.

WHAT WAS WRONG, IN THE BLUEPRINT'S OWN WORDS (p110's dashed panel)
------------------------------------------------------------------
*"Five options are named on screen and none of them is stored. There is no
column for it, so the wizard asks and forgets - which is worse than not
asking."*

`accounts.close_reason` has been PROPOSED-SCHEMA in B2 since 2026-08-08 with no
migration behind it, so `reason` was a REFUSED field on every door. A utility
that cannot say why forty accounts closed last quarter cannot answer its own
board — which is the reporting gap `OQ-830` states and this column closes for
the move-out half of it.

WHAT THIS DOES
--------------
ONE nullable TEXT column and ONE check. Nothing else: no index (nothing sorts
or pages on it — a closure report GROUPS, and the table is bounded by the
tenant's account count), no default, no backfill, no data migration of any
kind.

⚠ **AND THE ABSENCE OF A BACKFILL IS THE RULING, NOT AN OMISSION.** The PO
ruled it in the same sitting, verbatim: *"what happens to move-outs already
closed with no reason recorded — **no migration may write one, hard rule 4**;
report the count and leave them."* Inventing a reason for a historical close
would be falsifying a record. Every account closed before today reads NULL, and
NULL means *nobody was asked* — never *no reason*, and never `other`.

⚠ **THE CHECK PERMITS NULL ON PURPOSE.** `ck_accounts_close_reason` allows NULL
or one of the five codes. A check demanding a value would be unsatisfiable on
every already-closed row the moment it was added, so the migration would not
apply at all — and a check that cannot be added is a check that gets quietly
dropped. The five codes are `models.CLOSE_REASONS` and they are CODES, never
the words a clerk reads (B14 rule 35 gives each catalogue its own language).

REVERSIBLE, AND WHAT REVERSING COSTS
------------------------------------
`AddField` + `AddConstraint` both reverse cleanly, and Django's own
`RemoveField` is the rollback. **Reversing DROPS the recorded reasons**, which
is real data loss rather than a schema change — so the rollback note in the
change record says to take a dump of `accounts (id, close_reason)` first. It
is safe on day one, when no row has a value yet.

ORDERING
--------
Depends on `0057_cr122_brc06_discount_claim`, the current leaf. It touches only
`accounts`, a table this module owns outright (B1/B8), and no other module's
migration references the column — so there is no cross-module ordering hazard
to state.
"""

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0057_cr122_brc06_discount_claim"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="close_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="account",
            constraint=models.CheckConstraint(
                condition=Q(close_reason__isnull=True)
                | Q(
                    close_reason__in=(
                        "lease_ended",
                        "owner_sold",
                        "downgrade_or_hardship",
                        "deceased",
                        "other",
                    )
                ),
                name="ck_accounts_close_reason",
            ),
        ),
    ]
