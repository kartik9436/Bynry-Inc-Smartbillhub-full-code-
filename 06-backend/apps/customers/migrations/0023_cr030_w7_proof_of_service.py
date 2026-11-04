"""customers 0023 — CR-030 W7: BR-CUS-100's PROOF OF SERVICE on `disconnect_notices`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-25 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*). ⚠ **A ROW IN
`12-governance/09-human-review-ledger.md` IS OWED AND THIS LANE DOES NOT OWN
THAT FILE.** G7 globs `06-backend/apps/*/migrations/0*.py`, so **G7 FAILS on
this file until the row exists** — reported with this exact path rather than
smoothed over. Not RATIFIED without a recorded human sign-off.

WHAT IT ADDS, AND THE SENTENCE THAT ASKED FOR IT
────────────────────────────────────────────────
BR-CUS-100 (PO 2026-08-25, closing DEF-692), verbatim: *"`disconnect_notices`
CANNOT HOLD THE PROOF TODAY. It carries `tier`, `delivery_state`,
`delivery_unavailable_reason`, `issued_on`, `actor` and `detail` — enough to say
a notice was raised, **not enough to say it was served, by what means, or that a
signature came back.** Owed: a proof reference, a served-at date and the serving
channel, entered by a human, on the same discipline `BR-MET-110` applies to a
field result — somebody decided, and the record must name them."*

Six nullable columns and two check constraints:

  `service_channel` · `proof_reference` · `served_on` · `signed_for_on` ·
  `proof_recorded_by` · `proof_recorded_at`

**EVERY ONE IS NULLABLE AND NO BACKFILL RUNS.** A notice already in this table
was RAISED and nobody has yet said how it was served — which is exactly what
all-NULL means, so the existing rows land in the queue rather than being given
an invented history. `ix_dsc_notice_unproved` is the partial index on that
queue. Manufacturing a `served_on` for a row nobody attested to would be the
fabricated delivery state BR-CUS-100 exists to forbid, written into history.

⚠ **NO DATA STEP, DELIBERATELY** — DEF-622's hazard (a data step clearing tenant
context inside a migration, poisoning the deferred-FK validation at the
migration's exit) cannot arise here because there is nothing to seed.

NO RLS POLICY IS ADDED HERE, AND THAT IS NOT AN OMISSION
─────────────────────────────────────────────────────────
These are COLUMNS on `disconnect_notices`, a table that already carries
`ENABLE ROW LEVEL SECURITY` + `FORCE` and the `NULLIF` policy form (DEF-639)
from migration 0022. **A policy is a table-level object**: it governs every
column of the table, including ones added afterwards, so a second policy here
would be a duplicate of the one already standing — and two policies over one
table is the drift hard-won law 5 is about. The new columns are protected the
moment they exist. `tests/test_w7_proof_of_service.py` asserts the tenant
scoping at the service layer; the isolation tier asserts the policy itself
against live Postgres, unchanged from 0022.

⚠ **THE `proof_recorded_by` FK CROSSES INTO `identity`.** It is the same
cross-module FK `disconnect_notices.actor` already carries to `identity.User`
(0022), which is in B2 §2's reviewed interface set. Nothing new is being
claimed — the second FK names the SECOND person in this row's story: `actor`
raised the notice, `proof_recorded_by` attested how it was served, and they are
routinely not the same member of staff.

⚠ **THE AUTODETECTOR PROPOSES `Create model Transfer` ON THIS TREE, AND IT IS
NOT THIS MIGRATION'S.** Measured 2026-08-25 on a clean checkout, BEFORE this
lane wrote anything: `makemigrations --check --dry-run` already answered
`0023_transfer + Create model Transfer`. Migration 0021 made `transfers.Transfer`
`managed = False` with no model state on the stated ground that *"a model Django
never imports at startup is invisible to the autodetector"* — but
`apps/customers/api.py` now imports `transfer_reads`, which imports `transfers`,
so Django DOES import it and the state gap became visible drift. `makemigrations`
therefore swept that `CreateModel` into this file; **it has been REMOVED**,
because a lane may not carry another lane's model in its own migration. The
drift is pre-existing, is REPORTED as a defect, and its one-line fix belongs to
the transfers lane.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0022_cr030_w7_disconnect_ladder"),
        ("identity", "0004_rls_security_policies"),
        ("tenancy", "0018_br_cus_092_ein_encrypted"),
    ]

    operations = [
        migrations.AddField(
            model_name="disconnectnotice",
            name="proof_recorded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="disconnectnotice",
            name="proof_recorded_by",
            field=models.ForeignKey(
                blank=True,
                db_column="proof_recorded_by",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="identity.user",
            ),
        ),
        migrations.AddField(
            model_name="disconnectnotice",
            name="proof_reference",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="disconnectnotice",
            name="served_on",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="disconnectnotice",
            name="service_channel",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="disconnectnotice",
            name="signed_for_on",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="disconnectnotice",
            index=models.Index(
                condition=models.Q(("proof_recorded_at__isnull", True)),
                fields=["tenant", "tier"],
                name="ix_dsc_notice_unproved",
            ),
        ),
        migrations.AddConstraint(
            model_name="disconnectnotice",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("service_channel__isnull", True),
                    (
                        "service_channel__in",
                        ("certified_mail", "posted", "email", "text_message", "door_hanger"),
                    ),
                    _connector="OR",
                ),
                name="ck_disconnect_notice_service_channel",
            ),
        ),
        migrations.AddConstraint(
            model_name="disconnectnotice",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("proof_recorded_at__isnull", True),
                        ("proof_reference__isnull", True),
                        ("served_on__isnull", True),
                        ("service_channel__isnull", True),
                        ("signed_for_on__isnull", True),
                    ),
                    models.Q(
                        ("proof_recorded_at__isnull", False),
                        ("proof_reference__isnull", False),
                        ("served_on__isnull", False),
                        ("service_channel__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="ck_disconnect_notice_proof_all_or_nothing",
            ),
        ),
    ]
