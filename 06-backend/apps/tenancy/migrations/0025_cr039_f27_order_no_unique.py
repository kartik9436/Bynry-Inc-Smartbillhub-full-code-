"""tenancy 0025 — CR-039 wave F task 27: the implementation order's number is UNIQUE.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — **migration ordering** is on CLAUDE.md's
sensitive-paths list, and the ledger row for this file is in
`12-governance/09-human-review-ledger.md`. The marker is here because the PATH is
the category, not because the body is large (DEF-808): this migration is one
`AddConstraint` and it still had to choose a parent, and choosing `0022` over the
watermark is exactly the judgment that category exists to have reviewed.

⚠ **THE PARENT IS `0022` AND `0023`/`0024` DO NOT EXIST — DELIBERATELY.**
Migration numbers in this repo are ALLOCATED TO A LANE and never taken from a
watermark (`DEF-892`). `0024` is recorded in `12-governance/11-change-requests.md`
as the CR-039 wave E lane's reservation, which it did not need; `0023` is
unclaimed. `0025` is this lane's, recorded in `12-governance/14-id-reservations.md`.
The graph does not depend on the digits — this depends on `0022`, the real leaf —
and a later `0023` on the same parent produces two leaves and an ordinary merge
request rather than a silent collision.

`0021` shipped `implementation_orders.order_no` as a nullable column with **no
writer** — the good "column ahead of its format" pattern this repo uses twice in
CR-039 wave D, and the same pattern `DEF-920` warns about the moment somebody
finishes it. Task 27 says the commercial model sits *"on the platform side of the
boundary with its own numbering"*, and the model's own docstring already names
the number it should hold: **`IMPL-26-0001`**.

This adds the one thing that makes "no two orders share a number" TRUE rather
than hoped.

⚠ **WHY A CONSTRAINT AND NOT JUST A CAREFUL ALLOCATOR.** The allocator reads the
highest number of the year and adds one. Two signups running at the same instant
read the same maximum, and without this index they both write `IMPL-26-0001` and
nothing anywhere objects — a duplicate reference on two different utilities'
paperwork, discovered by a human, later. With it, the second write raises and the
allocator retries; the retry has something to catch. **The index is not the
belt-and-braces half — it is the half that works.**

⚠ **UNIQUE ACROSS THE PLATFORM, NOT PER TENANT, AND THE DIFFERENCE IS TASK 27's
WHOLE POINT.** `customers 0028` made `transfers.transfer_no` unique **per
tenant**, correctly: that number is the tenant's, two utilities may both have a
`TRF-26-0001`, and a tenant configures its own format on Settings → Numbering.
This number is **Bynry's**. There is one Bynry, so there is one series, and two
implementation orders may never share a reference no matter whose utility they
are for.

**`WHERE order_no IS NOT NULL`**, because every one of the orders `0021` could
already have created carries NULL and several NULLs are not a collision. In
practice there are none — nothing ever wrote this table — but a partial index is
the honest shape for a column whose absence is lawful, and it is what lets this
migration apply to a database that has been running since `0021`.

**Reversal:** `DROP INDEX`. No data is lost, because an index holds none.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0022_cr039_c12_owner_categories"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="implementationorder",
            constraint=models.UniqueConstraint(
                fields=["order_no"],
                condition=models.Q(order_no__isnull=False),
                name="uq_implementation_orders_order_no",
            ),
        ),
    ]
