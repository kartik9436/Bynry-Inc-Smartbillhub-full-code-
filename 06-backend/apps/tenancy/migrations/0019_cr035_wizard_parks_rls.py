# ── Trace ──────────────────────────────────────────────
# Story:    CR-035 step 6 part 1 — the store behind Park.
#           Screens: S19 move-in · S20 move-out · TRF-02 · DSC-02 · the
#           new-connect wizard — the five that carry the control and have
#           nowhere to park to.
# Rules:    BR-SHL-048 (a parked wizard changes nothing until it is executed —
#           PO 2026-08-26, verbatim "Option A - Unitl move in executed, no
#           records updates") · BR-SHL-047 (every wizard parks) · B19 §12.2
#           (Save & exit writes nothing; Park records what is awaited) ·
#           CLAUDE.md rule 1 (tenant scoping, RLS FORCE)
# Defect:   DEF-746 — the control is inert on five of six wizards while a
#           signed rule says every wizard parks.
# ───────────────────────────────────────────────────────
"""`wizard_parks` — the draft a clerk can come back to.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — this migration writes an RLS policy
(CLAUDE.md rule 1), so it is named to MATCH `human_owned.txt`'s
`06-backend/**/migrations/*rls*` glob and carries a row in
`12-governance/09-human-review-ledger.md`.

⚠ **THE FILENAME IS LOAD-BEARING AND THAT IS NOT A JOKE.** G7 guards sensitive
paths by GLOB, and `*rls*` matches a NAME. A migration that adds a policy and is
not named for it is invisible to the guard — the guard list's own comment
records that exact escape: *"the file already carried HUMAN-REVIEW-PENDING and a
ledger row and NO glob here matched it, so G7 reported conform over an unguarded
money path — hard-won law 1, in the guard list itself."* Adding a line to
`human_owned.txt` is a process event and the PO's call; naming my own file so
the existing glob catches it is not. Do not rename this file.

WHAT THE TABLE IS FOR, IN ONE LINE
----------------------------------
The Product Owner: *"in pratcicail life all these request does not close in  day,
hence user genrllay park them … help them to work on these request as per their
pace"*. Five wizards already render the park panel, its nine reasons, the note
and the reminder date; `wizardParkPort()` returns null and its own docstring says
*"Returning a port here is the whole switch"*. This is what the switch needs.

WHY THERE IS NO FOREIGN KEY TO A UNIT, AN ACCOUNT OR A PREMISES
--------------------------------------------------------------
BR-SHL-048 (a). An FK is a RELATIONSHIP and the ruling is that there is none
until the wizard is executed — so the ids live inside `subject_ref` as copied
values. The model's docstring carries the three consequences; the one that
matters to a reader of this file is that **no parked draft can hold a unit**, so
no parked wizard can block anything, which is how the open half of BR-SHL-047
gets settled by removing a mechanism rather than adding a rule.

⚠ **NO DATA IS WRITTEN BY THIS MIGRATION**, so reversing it loses nothing but
the drafts themselves.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
TABLE = "wizard_parks"


POLICY = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""

REVERSE = f"""
DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};
ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0004_rls_security_policies"),
        ("tenancy", "0018_br_cus_092_ein_encrypted"),
    ]

    operations = [
        migrations.CreateModel(
            name="WizardPark",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("flow", models.TextField()),
                ("subject_label", models.TextField(blank=True, default="")),
                ("subject_ref", models.JSONField(blank=True, default=dict)),
                ("step", models.PositiveSmallIntegerField(default=1)),
                ("values", models.JSONField(blank=True, default=dict)),
                ("waiting_on", models.TextField()),
                ("park_note", models.TextField(blank=True, null=True)),
                ("remind_on", models.DateField(blank=True, null=True)),
                ("parked_at", models.DateTimeField(auto_now_add=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "parked_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="parked_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "wizard_parks",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "flow__in",
                                ("move_in", "move_out", "transfer", "disconnect", "new_connect"),
                            )
                        ),
                        name="ck_wizard_parks_flow",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("step__gte", 1)), name="ck_wizard_parks_step"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("waiting_on", ""), _negated=True),
                        name="ck_wizard_parks_waiting_on",
                    ),
                ],
            },
        ),
        # ⚠ **THE POLICY RUNS AFTER `CreateModel`, WHICH IS THE POINT** — FORCE
        # applies to a table that already exists and is still empty, so there is
        # never a window in which a row can be written unguarded. DEF-639's
        # NULLIF form: an UNSET `app.tenant_id` matches nothing rather than
        # raising, so a query that forgot to scope returns zero rows instead of
        # a 500 that reads like a bug in the query.
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-035 step 6 part 1 (BR-SHL-048 + the PO ruling quoted verbatim in
#         12-governance/02-decision-log.md, 2026-08-26)
# generated: 2026-08-26 by the CR-035 park-store lane
# checklist: A✔ B=deferred(service + API are parts 2-3 of CR-035 step 6) C✔
#         D=deferred(no-API-half yet) E=deferred(the frontend half is ALREADY
#         built — five wizards render the panel and wizardParkPort() is the
#         switch) F✔ G✔ H=PENDING(🔒 RLS — human-review ledger row opened)
# gates: makemigrations --check --dry-run — see the commit; no Postgres in this
#         environment, so the POLICY IS NOT PROVEN AGAINST A LIVE DATABASE HERE
#         and that is stated rather than implied (hard-won law 1). The isolation
#         tier is what proves it.
# exceptions: `waiting_on` is FREE TEXT and not a closed vocabulary, matching
#         `customers.ServiceRequest.waiting_on` — the one flow where parking
#         already works got there first, and one "Waiting on" list cannot carry
#         two contracts for one column. The nine reasons are what the SCREEN
#         offers. · `subject_label` is denormalised with no FK to refresh it
#         from, which is BR-SHL-048 (a) and not an oversight.
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
