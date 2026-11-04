"""metering 0059 — a DRAFT build may exist before its address does
(2026-09-21, `DEF-CUS-6109`).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-21 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

ONE COLUMN LOSES ITS `NOT NULL`, AND ONE CHECK CONSTRAINT PUTS THE GUARANTEE
BACK WHERE IT IS ACTUALLY TRUE.

──────────────────────────────────────────────────────────────────────────────
WHAT THE PO RULED, AND WHY THE SCHEMA HAD TO MOVE FOR IT
──────────────────────────────────────────────────────────────────────────────
**PO ruling 2026-09-21, verbatim:** *"then approve applciation may create a new
conenct request - as draft request - this request is new work and recognized
seperately from applcaition and hence we should not make it dependent on
applciation #"*.

So approving an application into a new connection **creates a DRAFT build and
opens the wizard**. The clerk then supplies what the wizard asks for — the
owner, the units, the services, the plans, the charges — and `BR-MET-112` says
**nothing is written until the last button**.

`connections.premises_id` was `NOT NULL`, so the only way to raise that draft
was to create the address first. That is exactly what `BR-MET-112` forbids: a
clerk who abandons the wizard would leave a brand-new premises standing with no
units, no meters and no plan behind it, **and no screen in this product can
find that wreckage** (`commit_new_connect`'s own docstring says so).

⚠ **THE OLD REFUSAL'S STATED REASON WAS FALSE AND IS `DEF-MET-6117`.**
`request_jobs._raise_connection` said *"creating the premise here would need
the mandatory owner `BR-MET-1010` requires and the application does not
carry"*. Measured against this schema on 2026-09-21: **`premises.owner_id` is
NULLABLE**, the owner refusal was itself reversed on 2026-08-27 (`DEF-650`), and
`metering/services.py::create_premises` creates the owner's master account LAST,
in its own savepoint, whose own comment reads *"a refused account leaves the
address standing"*. Nothing was missing. The refusal was a choice.

──────────────────────────────────────────────────────────────────────────────
WHY A CHECK CONSTRAINT AND NOT JUST A NULLABLE COLUMN
──────────────────────────────────────────────────────────────────────────────
Dropping `NOT NULL` on its own would let a **submitted** build — one with units,
meters, plans and an owner account behind it — exist with no address at all,
which is a worse fault than the one being fixed and is unreachable today only
by convention. The invariant that is actually true is narrower:

    a build that has been SUBMITTED has an address.

`submitted_at` is the fact and not the `state` cache: `derive_connection_state`
returns `draft` exactly while `submitted_at IS NULL`, and `state` is rewritten
by `refresh_connection_state()`, so a constraint keyed on `state` could be
defeated by a cancel (`cancelled` outranks everything) while one keyed on
`submitted_at` cannot.

⚠ **IT IS WRITTEN AS `submitted_at IS NULL OR premises_id IS NOT NULL`** rather
than the equivalent `NOT (submitted AND no premises)`, because that is the
sentence a reader can check against the rule above without negating anything.

⚠ **NO ROW IS TOUCHED AND THE CONSTRAINT IS SATISFIED BY EVERY EXISTING ROW**,
because every one of them has a premises — the column was `NOT NULL` until this
migration. So there is nothing to backfill and nothing to repair, and this
migration therefore writes no rows and sets no `app.tenant_id` (`DEF-BIL-5382`
is the opposite case: a `RunPython` on a tenant table under RLS `FORCE` that
does not set it sees zero rows and reports success). `AlterField` and
`AddConstraint` are DDL and are not subject to row-level security.

⚠ **LEAF CHECKED BEFORE NUMBERING** (`DEF-CUS-6041`). `metering`'s leaf at the
moment this was written is `0058_cr126_build_record_fields`, and it is the sole
dependency below. Two leaf nodes kill every test in the process before
collection, with an error that names neither lane.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0058_cr126_build_record_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="connection",
            name="premises",
            field=models.ForeignKey(
                blank=True,
                db_column="premises_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="metering.premises",
            ),
        ),
        migrations.AddConstraint(
            model_name="connection",
            constraint=models.CheckConstraint(
                check=models.Q(submitted_at__isnull=True)
                | models.Q(premises__isnull=False),
                name="ck_connections_premises_once_submitted",
            ),
        ),
    ]
