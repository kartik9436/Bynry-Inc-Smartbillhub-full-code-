"""customers 0048 — every job a request raises NAMES THE REQUEST.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list and the ledger row for this file is in
`12-governance/09-human-review-ledger.md`. The marker is here because the PATH
is the category, not because the body is large (DEF-808).

`CR-094-BRC01`, PO ruling 2026-09-15, verbatim: *"pass all information to create
the new connect requets or move -in request based on selction"*. Drawn on p083–
p084 of `05-prototype/02 Accounts Menu Blueprint.pdf`, read AS IMAGES at scale 2
(B14 rule 42): *"A build is raised on the New connects tab, **naming this
request**"*.

════════════════════════════════════════════════════════════════════════════
WHAT THIS ADDS, AND WHY ONLY THREE TABLES
════════════════════════════════════════════════════════════════════════════
`BR-CUS-080` (PO 2026-08-24) has two halves. The SR's half —
`outcome` + `outcome_kind` + `outcome_ref` — has been built since `CR-031`.
**The CHILD's half has never existed anywhere except `connections`**, whose
`request_id` landed with `CR-030` W6 and which nothing has ever filled
(`DEF-MET-5397`). `service_request_service.link_child`'s own docstring records
why: *"the child tables are not built (W5/W6/W7) … when the child lands it
carries `origin_service_request_id` pointing back, which is the half BR-CUS-080
actually names."* **All three have since landed and none of them carries it.**

So: `move_records`, `transfers` and `disconnect_cases` each gain a nullable
`request_id`. `connections` gains nothing — metering already has it.

════════════════════════════════════════════════════════════════════════════
NULLABLE, AND THE NULL IS A REAL ANSWER RATHER THAN A MIGRATION SHORTCUT
════════════════════════════════════════════════════════════════════════════
`connections.request_id`'s own note says it for all four: *"NULL is legitimate
and common: B18 §2.1's six channels include builds a developer starts without a
request record."* A move-out a clerk starts from the account page, a transfer
begun at the counter and a disconnect opened by the collections ladder each have
no application behind them and never will.

⛔ **THERE IS NO BACK-FILL, AND THAT IS DELIBERATE — NOT AN OMISSION.** Nothing
in this database can say which existing job came from which request: the link
did not exist, and `link_child` has written `outcome_ref` on exactly one seeded
row. A back-fill would have to GUESS the pairing from a date and an address,
and a guessed link on a record a regulator may read is worse than no link.
⚠ **AND HAD ONE BEEN WRITTEN IT WOULD HAVE REPORTED SUCCESS AND CHANGED
NOTHING** — a data migration runs as the APP role under RLS `FORCE`, sees zero
rows unless it sets `app.tenant_id` per tenant, and says so to nobody. That was
`DEF-BIL-5382`, the same day. Stated here so the next lane that wants a
back-fill on this column knows both halves before it writes one.

════════════════════════════════════════════════════════════════════════════
THREE TABLES, TWO MECHANISMS — MIGRATION 0028's SPLIT, FOR ITS REASONS
════════════════════════════════════════════════════════════════════════════
`transfers` is `managed = False` (its DDL is 0021's raw SQL), so Django's schema
editor keeps neither model nor table in step for it. Both halves are therefore
explicit, exactly as 0028 does for `transfer_no`:

  · `RunPython(add_transfer_request_id, drop_transfer_request_id)` issues the
    real `ALTER TABLE`;
  · `AddField` puts the field into migration STATE and, because
    `Meta.managed = False` makes `can_migrate()` False, emits no DDL of its own.

`move_records` and `disconnect_cases` are ordinary managed models, so their
`AddField` IS the DDL.

⚠ **NO FOREIGN KEY, ON ANY OF THE THREE, AND IT IS THE SAME CALL `transfers
.to_unit_id` ALREADY MADE.** A plain `UUIDField`. Two reasons, and the second is
the one that decides it:

  1. `transfers` is unmanaged, so an FK would have to be hand-written DDL that
     the model cannot express and the introspection test would then police by
     name — three spellings of one constraint.
  2. **A `PROTECT` FK from a job to a request would make a request undeletable
     and a job's tenant boundary depend on another module's row.** The link is
     evidence, not integrity: `connections.request_id` is a real FK because
     metering chose one and B2 §2's reviewed interface set carries that edge;
     these three are inside customers and the same argument does not apply, so
     the cheaper column is the honest one. Stated rather than left to look like
     an oversight.

No RLS operation is needed: `move_records` got ENABLE + FORCE and its policy in
0030, `transfers` in 0021 and `disconnect_cases` in 0022 — **a policy covers a
table's rows, not its columns.**
"""

from django.db import migrations, models

#: The `ALTER TABLE` for the UNMANAGED `transfers`. Frozen text, never derived
#: from the live model — 0021's docstring records why: DDL that reaches into the
#: current model class silently changes what it builds every time somebody edits
#: the model, which is how a fresh database and an upgraded one come to disagree.
#: `uuid` on Postgres, `char(32)` on sqlite — the two vendors spell Django's
#: `UUIDField` differently and 0021's own frozen pair already does this.
ADD_TRANSFER_REQUEST_ID_PG = "ALTER TABLE transfers ADD COLUMN request_id uuid NULL;"
ADD_TRANSFER_REQUEST_ID_SQLITE = "ALTER TABLE transfers ADD COLUMN request_id char(32) NULL;"

#: The job queues are read by request far less often than by account, so this is
#: a plain index rather than a unique one: **one request raises one job**
#: (`ux_service_requests_outcome_ref` on the SR side already guarantees that),
#: and duplicating the uniqueness here would be a second place for one rule.
ADD_TRANSFER_REQUEST_INDEX = (
    "CREATE INDEX ix_transfers_request ON transfers (tenant_id, request_id) "
    "WHERE request_id IS NOT NULL;"
)
DROP_TRANSFER_REQUEST_INDEX = "DROP INDEX IF EXISTS ix_transfers_request;"
DROP_TRANSFER_REQUEST_ID = "ALTER TABLE transfers DROP COLUMN request_id;"


def add_transfer_request_id(apps, schema_editor):  # type: ignore[no-untyped-def]
    """The column and its index on the unmanaged `transfers` table."""
    vendor = schema_editor.connection.vendor
    schema_editor.execute(
        ADD_TRANSFER_REQUEST_ID_PG if vendor == "postgresql" else ADD_TRANSFER_REQUEST_ID_SQLITE
    )
    schema_editor.execute(ADD_TRANSFER_REQUEST_INDEX)


def drop_transfer_request_id(apps, schema_editor):  # type: ignore[no-untyped-def]
    schema_editor.execute(DROP_TRANSFER_REQUEST_INDEX)
    schema_editor.execute(DROP_TRANSFER_REQUEST_ID)


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0047_cr094_service_request_applicant_messages"),
    ]

    operations = [
        # ── transfers (unmanaged): the DDL, then the state ──────────────────
        migrations.RunPython(add_transfer_request_id, drop_transfer_request_id),
        migrations.AddField(
            model_name="transfer",
            name="request_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        # ── move_records + disconnect_cases (managed): AddField IS the DDL ──
        migrations.AddField(
            model_name="moverecord",
            name="request_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="disconnectcase",
            name="request_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="disconnectcase",
            index=models.Index(fields=["tenant", "request_id"], name="ix_dsc_case_request"),
        ),
        migrations.AddIndex(
            model_name="moverecord",
            index=models.Index(fields=["tenant", "request_id"], name="ix_move_records_request"),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-094-BRC01 (12-governance/11-change-requests.md) + the decision-log
#         row of 2026-09-15. ⚠ G1 wants `US-XXX-###@<hex>` and no story owns a
#         CR wave task — DEF-810 records that the packet grammar has no form for
#         CR- or DEF-driven work.
# generated: 2026-09-15 by the CR-094-BRC01 wave 1 lane A
# checklist: A✔ B✔(request_jobs.py fills all three) C=n/a D=n/a E=n/a(no screen
#         in this lane) F✔ G✔ H=PENDING(🔒 migration ordering — ledger row
#         written before review, per r11 step 4)
# gates: `makemigrations --check --dry-run` → "No changes detected" with this
#         file present. The unmanaged `transfers` half is caught by
#         `tests/test_w7_transfers.py::
#         test_tc_trf_12_the_model_and_the_live_table_agree_column_for_column`
#         and NOT by the autodetector — 0028's docstring records why.
