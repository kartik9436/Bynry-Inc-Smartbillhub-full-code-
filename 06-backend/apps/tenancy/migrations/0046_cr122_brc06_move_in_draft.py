"""tenancy 0046 — **a parked wizard may now be a DRAFT, and a move-in draft
carries the reference it will be filed under.**

`CR-122-BRC06` · PO ruling 2026-09-19. The wizard's `Save & exit` wrote NOTHING
— the file said so in its own words — so a clerk who keyed five steps and a
$150.00 deposit with its receipt number started again from scratch, unwarned.
This migration is the half of the fix that the database owns.

═══════════════════════════════════════════════════════════════════════════
1 · WHY `ck_wizard_parks_waiting_on` IS DROPPED RATHER THAN KEPT
═══════════════════════════════════════════════════════════════════════════
The check refused `waiting_on = ''`, and its own comment gave the reason:
*"`Save & exit` leaves quietly and writes no row at all, so a row with no
reason is a park that forgot the only thing it is for."* **That reasoning was
correct and its premise has been overruled.** `Save & exit` now writes a row,
and that row legitimately has no reason — the clerk is not waiting on anybody,
they are coming back after lunch.

⚠ **B19 §12.2's TWO CONTROLS ARE UNCHANGED AND STILL TWO.** `Park` still asks
*what are you waiting for?* and still fills `waiting_on`; `Save & exit` still
does not ask. What changed is only that the quiet one now keeps the typing.
**An empty `waiting_on` IS the draft state** — deliberately, rather than a
separate `is_draft` flag, because two columns that must agree are two columns
free to disagree, and this file has watched that happen elsewhere.

═══════════════════════════════════════════════════════════════════════════
2 · WHY THE REFERENCE LIVES HERE AND NOT ONLY ON `move_records`
═══════════════════════════════════════════════════════════════════════════
`move_records` is written by a flow that has ALREADY committed — its own
docstring is explicit (*"there is no in-flight moment for it to describe"*,
BR-CUS-152 *nothing updates a row of this table*). So it cannot hold the
reference of a job still in a clerk's hands, and the Move-ins tab draws a
`REFERENCE` column over an `OPEN` counter that counts exactly those jobs
(blueprint p073).

The number is `MVI-{YY}-{0000}` from the **same `move_in` series** the finished
record draws from, and `services.move_in` ADOPTS it instead of allocating a
second one. One job, one number, from the moment the wizard opens to the
moment it is filed.

⚠ **A DRAFT THAT IS ABANDONED LEAVES A GAP IN THE COUNTER, AND THAT IS
LAWFUL.** BR-TEN-035: gaps are permitted and preferred to a number issued
twice.

═══════════════════════════════════════════════════════════════════════════
3 · WHAT THIS MIGRATION DELIBERATELY DOES NOT CARRY
═══════════════════════════════════════════════════════════════════════════
⚠ `makemigrations` also offered to drop and recreate **`ck_stored_documents_kind`**
on `tenancy.StoredDocument`. That is a PRE-EXISTING model/schema drift owned by
another lane (`cd73c1963`), it has nothing to do with this change, and carrying
it here would publish a sibling's schema edit under this CR's name — CLAUDE.md
law 11's mechanism five, one table over. It is stripped out. (This note first
said it was *"filed as `DEF-TEN-5880`"*; that id was never issued. The drift
was filed as `DEF-TEN-6107` and `DEF-TEN-6425` and is fixed by `0047`.)

RLS: `wizard_parks` already carries its policy from `tenancy/0019`, and
neither a new column nor a dropped CHECK changes it. Nothing here is
tenant-scoped that was not tenant-scoped before.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).
"""

import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0045_service_request_document_source"),
    ]

    operations = [
        # §1 — the premise this refused is the one the PO overruled.
        migrations.RemoveConstraint(
            model_name="wizardpark",
            name="ck_wizard_parks_waiting_on",
        ),
        migrations.AlterField(
            model_name="wizardpark",
            name="waiting_on",
            field=models.TextField(blank=True, default=""),
        ),
        # §2 — nullable, because a tenant with no `move_in` series row must get
        # a draft with no reference rather than no draft at all.
        migrations.AddField(
            model_name="wizardpark",
            name="reference",
            field=models.TextField(blank=True, null=True),
        ),
        # One number to a human is one number to the index: per tenant,
        # case-insensitive, and only where a reference exists — so the NULLs of
        # the four flows that allocate nothing cannot collide with each other.
        migrations.AddConstraint(
            model_name="wizardpark",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("reference"),
                condition=models.Q(("reference__isnull", False)),
                name="uq_wizard_parks_tenant_reference_ci",
            ),
        ),
    ]
