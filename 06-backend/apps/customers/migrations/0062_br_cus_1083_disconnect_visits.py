"""customers 0062 — `disconnect_visits`, the row a failed crew visit never had.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering AND RLS policies are
both on CLAUDE.md's sensitive-paths list, and this file carries one of each. The
ledger row is in `12-governance/09-human-review-ledger.md`; AI-authored under the
PO ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*) and
not RATIFIED without a recorded sign-off.

PO ruling 2026-09-20, verbatim: *"The register reflects reality. Today a failed
visit is invisible and the case looks untouched."* The four outcomes are the
PO's own words — **locked gate, paid at the door, disputed, access refused** —
and so is *"each must move the case somewhere, not merely annotate it"*. The
rule is `BR-CUS-1083` and the reasoning for every column, and for where each
outcome sends the case, is in `apps/customers/disconnect_visits.py`'s docstring
beside the thing it governs rather than restated here.

It closes `OQ-383`, open since 2026-08-25: *"A CREW ATTENDS, AND DOES NOT CUT —
WHAT IS RECORDED?"*

════════════════════════════════════════════════════════════════════════════
THE TABLE AND ITS POLICY ARE ONE MIGRATION, DELIBERATELY
════════════════════════════════════════════════════════════════════════════
`0053`'s form, for the two reasons it gives. **One leaf instead of two**: every
extra migration in a tree several lanes are pushing to is another chance of the
two-leaf refusal that names neither lane (`DEF-2872`, CLAUDE.md law 12). And
**hard rule 1 is not a follow-up**: a tenant table that exists for even one
deploy without FORCE on it is a table that can be read across tenants, so the
`ENABLE`/`FORCE`/`CREATE POLICY` runs in the same transaction that creates it.

The reason of its own: each row says that a named utility sent a crew to a named
household's meter and what they found there — a locked gate, a refusal at the
door, a dispute. A tenant able to read another tenant's rows would learn who is
about to lose supply and why they have not yet.

════════════════════════════════════════════════════════════════════════════
WHAT THE CONSTRAINT IS FOR
════════════════════════════════════════════════════════════════════════════
`ck_disconnect_visit_outcome` pins the four-value vocabulary at the database
layer as well as in `disconnect_visits.VISIT_OUTCOMES`, so an import or a
fixture cannot introduce a fifth — the shape `ck_disconnect_case_state` has one
table over, and for the same reason: each of these four ends with a household
either keeping or losing supply, and a fifth way to arrive there is a decision,
not a string.

There is **no unique constraint**, and that is a decision rather than an
omission. A crew can attend the same case twice — a padlock on Tuesday and a
refusal on Thursday — and both are true. Nothing here is idempotent on purpose:
an act that happened twice is recorded twice.

════════════════════════════════════════════════════════════════════════════
NO IMMUTABILITY TRIGGER, AND THAT IS STATED
════════════════════════════════════════════════════════════════════════════
`disconnect_visits.record_outcome` only ever INSERTs and offers no other door.
There is no database trigger refusing an UPDATE here, because hard rule 4's
trigger covers issued invoices, invoice lines, payments and journal entries and
widening that list is a ruling rather than a lane's choice (the trigger's allow
list moved exactly once, in `payments/0014`, and only under a PO ruling). The
append-only property of this table is held by its service and by nothing else —
written down here so the next reader does not mistake it for a guarantee the
database is making.

**NO BACK-FILL, AND THAT IS A DECISION.** Cases that stayed `scheduled` with a
date in the past get no row: nobody recorded what happened at those meters, and
a row written now would invent a crew's finding. Those cases keep their stale
date until a clerk records a visit or re-schedules the cut, and that is the
honest state.

════════════════════════════════════════════════════════════════════════════
ORDERING
════════════════════════════════════════════════════════════════════════════
Depends on `0061_cr125_brc07_disconnect_stopped_note`, the leaf on
`origin/claude/laughing-thompson-kpmwih` when this was written. It creates one
new table and touches no existing one, so it can reorder nothing; if a sibling
lands another `0062` this file re-points to it, exactly as `0061` re-pointed
from `0059` within the hour.

**Rollback (change-process step 8):** this reverses cleanly. The policy drops,
FORCE comes off, and the `CreateModel` reverses to a `DROP TABLE`. What is lost
is every recorded crew finding — evidence, not money: no invoice, ledger row,
payment or account depends on this table, and the case moves it made stay made
(they are writes to `disconnect_cases`, which this migration does not own).
Reversing puts the product back to the behaviour
`disconnects.CREW_OUTCOME_UNRECORDABLE` described for its first 26 days, which
is the sentence to read before running it.
"""

import core.dbfields
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

#: `0022_cr030_w7_disconnect_ladder`'s form, character for character. DEF-639:
#: the bare cast raises on the empty string an unset GUC leaves behind.
TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

TABLE = "disconnect_visits"

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

#: `disconnect_visits.VISIT_OUTCOMES`, re-typed here because a migration must
#: freeze the vocabulary as it was on the day it ran — importing the live tuple
#: would silently re-write history the day a fifth outcome is ruled.
OUTCOMES = ("locked_gate", "access_refused", "paid_at_door", "disputed")


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0061_cr125_brc07_disconnect_stopped_note"),
        ("identity", "0004_rls_security_policies"),
        ("tenancy", "0044_cr094_i_account_document_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="DisconnectVisit",
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
                ("visited_on", models.DateField()),
                ("outcome", models.TextField()),
                ("note", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "case",
                    models.ForeignKey(
                        db_column="case_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="customers.disconnectcase",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="recorded_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
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
                "db_table": "disconnect_visits",
                "indexes": [
                    models.Index(fields=["tenant", "case", "-visited_on"], name="ix_dsc_visit_case")
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("outcome__in", OUTCOMES)),
                        name="ck_disconnect_visit_outcome",
                    )
                ],
            },
        ),
        # THE POLICY — after the CreateModel, which is what makes FORCE apply to
        # a table that exists and is still empty.
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE),
    ]
