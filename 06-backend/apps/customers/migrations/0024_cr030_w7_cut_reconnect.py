"""customers 0024 — CR-030 W7 tasks 7.8/7.9: what the CUT records, and the price of coming back.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-25 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*). ⚠ **A ROW IN
`12-governance/09-human-review-ledger.md` IS OWED AND THIS LANE DOES NOT OWN
THAT FILE.** G7 globs `06-backend/apps/*/migrations/0*.py`, so **G7 FAILS on
this file until the row exists** — reported with this exact path rather than
smoothed over. Not RATIFIED without a recorded human sign-off.

WHAT IT ADDS, AND THE SENTENCES THAT ASKED FOR IT
─────────────────────────────────────────────────
`DSC-02.4`'s `What this will do` column is the specification for the cut, and
three of its four lines need somewhere to live that migration 0022 did not
build:

  * *"Cut the services chosen at step 1 …"* → `services_cut`, the codes FULLY
    DISCONNECTED. `DSC-02.1`: *"One decision per service, not all or nothing."*
    ⚠ A service marked `restrictor` never reaches this column — the schema
    holds cut and not-cut, a restrictor is a third state, and
    `disconnects.assert_treatments_expressible` refuses it by name rather than
    rounding it to either neighbour.
  * *"Add $75.00 to the balance as the price of getting service back"* →
    `reconnection_fee_amount` + `reconnection_fee_code`. **`NUMERIC(18,4)`** —
    CLAUDE.md rule 2 as re-signed 2026-08-22, *"MOney 4 decimal, percentage 6
    decimal, display both 2 decimal"*. The code is stored beside the amount so
    the figure traces back to the tenant's own catalogue row (BR-BIL-007:
    *"NSF/reconnect fees are tenant-configured charge codes, never
    hardcoded"*). ⚠ **Nothing posts it to AR** — `customers` writes no
    financial table (BR-CUS-037) and `apps.billing.services` publishes no
    ad-hoc charge service; the column records what was QUOTED.
  * `DSC-02.4`'s deposit radio → `deposit_disposition`, `held` or
    `applied_against_arrear`. The ELECTION only: applying a deposit against an
    arrear is a balance-sheet posting (*"A liability, not revenue"*) and rule 5
    leaves journal lines to the ledger posting service.

And `cut_reason` — `DSC-02.1`'s five reason cards. **Recorded and read by
nothing**, deliberately: B18 §5.8.7 notes that four of the five reasons are
operational and *"must not require a dunning ladder at all"*, and making a cut
behave differently by reason is a ruling this lane may not take. The column
exists so the record can NAME the reason a household was cut.

THREE CHECK CONSTRAINTS, AND THE THIRD IS THE ONE THAT MATTERS
──────────────────────────────────────────────────────────────
`ck_disconnect_case_cut_reason` and `ck_disconnect_case_deposit_disposition`
hold the two vocabularies. `ck_cut_records_the_price_of_coming_back` is the
all-or-nothing: **a row with `cut_on` set carries the fee, its code and the
deposit election, or it does not exist.** `DSC-02.4` quotes the reconnection fee
before the cut *"so the customer is told what it will cost to get service back
before it is taken away"* — a row saying service was cut with no price beside it
cannot answer the first question the customer will ask. `commit_cut` refuses
before it writes; this is what makes the guarantee true of the DATA rather than
only of the service layer (hard-won law 1).

EVERY COLUMN IS NULLABLE (or defaulted) AND NO BACKFILL RUNS
─────────────────────────────────────────────────────────────
`services_cut` defaults to `[]` and the rest are NULL. A case already in this
table was opened before any of this existed and nobody elected anything on it —
which is exactly what NULL means. Manufacturing a deposit election or a fee for
a row nobody decided would write an invented history into the record a regulator
reads. No case in this tree carries `cut_on` today, so the third constraint is
satisfiable on existing data without touching a single row.

⚠ **NO DATA STEP, DELIBERATELY** — DEF-622's hazard (a data step clearing tenant
context inside a migration, poisoning the deferred-FK validation at the
migration's exit) cannot arise here because there is nothing to seed.

NO RLS POLICY IS ADDED HERE, AND THAT IS NOT AN OMISSION
─────────────────────────────────────────────────────────
These are COLUMNS on `disconnect_cases`, a table that already carries `ENABLE
ROW LEVEL SECURITY` + `FORCE` and the `NULLIF` policy form (DEF-639) from
migration 0022. **A policy is a table-level object**: it governs every column of
the table, including ones added afterwards, so a second policy here would
duplicate the one already standing — and two policies over one table is the
drift hard-won law 5 is about. `tests/test_w7_cut_reconnect.py` asserts the
tenant scoping at the service layer; the isolation tier asserts the policy
itself against live Postgres, unchanged from 0022.

⚠ **THE AUTODETECTOR PROPOSES `Create model Transfer` ON THIS TREE, AND IT IS
NOT THIS MIGRATION'S — DEF-699.** Measured 2026-08-25 BEFORE this lane wrote
anything: `makemigrations --check --dry-run` already answered `0024_transfer +
Create model Transfer`. It is the same pre-existing drift migration 0023 records
in its own docstring: `transfers.Transfer` is `managed = False` with no model
state, and `apps/customers/api.py` imports it at startup, so the gap is visible
to the autodetector. **It has been REMOVED from this file** — a lane may not
carry another lane's model in its own migration — and the one-line fix belongs
to the transfers lane.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0023_cr030_w7_proof_of_service"),
    ]

    operations = [
        migrations.AddField(
            model_name="disconnectcase",
            name="cut_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="disconnectcase",
            name="services_cut",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="disconnectcase",
            name="reconnection_fee_amount",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="disconnectcase",
            name="reconnection_fee_code",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="disconnectcase",
            name="deposit_disposition",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="disconnectcase",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("cut_reason__isnull", True),
                    (
                        "cut_reason__in",
                        (
                            "non_payment",
                            "unsafe_installation",
                            "tampering_or_theft",
                            "premises_abandoned",
                            "customer_asked",
                        ),
                    ),
                    _connector="OR",
                ),
                name="ck_disconnect_case_cut_reason",
            ),
        ),
        migrations.AddConstraint(
            model_name="disconnectcase",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("deposit_disposition__isnull", True),
                    ("deposit_disposition__in", ("held", "applied_against_arrear")),
                    _connector="OR",
                ),
                name="ck_disconnect_case_deposit_disposition",
            ),
        ),
        migrations.AddConstraint(
            model_name="disconnectcase",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("cut_on__isnull", True),
                    models.Q(
                        ("deposit_disposition__isnull", False),
                        ("reconnection_fee_amount__isnull", False),
                        ("reconnection_fee_code__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="ck_cut_records_the_price_of_coming_back",
            ),
        ),
    ]
