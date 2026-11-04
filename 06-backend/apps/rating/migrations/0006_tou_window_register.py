"""rating 0006 — `time_of_use_windows.channel`: the utility says which register is which.

HUMAN-OWNED 🔒 · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md sensitive
path, AI-authored under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md; not RATIFIED without a
recorded human sign-off.

WHAT THIS COLUMN ENDS
---------------------
PO ruling 2026-08-16, verbatim: *"make the rate wizard say which register is which"*
(OQ-236 CLOSED → BR-RAT-067; BR-RAT-064 SUPERSEDED).

A customer's electric meter reports three numbers a month — on-peak, mid-peak, off-peak.
A time-of-use tariff prices three windows. Until this migration NOTHING IN THE SCHEMA
RECORDED WHICH NUMBER BELONGED TO WHICH WINDOW, so the pricing engine matched them BY
PRICE RANK, on the signed rule that a holiday bills at *"the off-peak (lowest-price)
window"* (BR-RAT-033). That was a defensible READING, not a guess — and a reading that
decides a customer's bill.

    stated correctly   120 x 0.22 + 200 x 0.14 + 380 x 0.09  =  88.60   <- B5 GT-17 ❄
    paired backwards   380 x 0.22 + 200 x 0.14 + 120 x 0.09  = 122.40   <- a 38 pct
                                                                          overcharge with
                                                                          nothing on the
                                                                          bill looking odd

After this migration the mapping is DATA the utility stated on S11, and
`apps/rating/selectors.pricing_inputs` reads it. The price-rank resolver
(`selectors._window_channels`) is DELETED, not disabled: there is no code path left that
can rank prices to place a kWh.

WHY THERE IS NO BACKFILL, STATED HERE BECAUSE IT IS THE DECISION A REVIEWER WILL LOOK FOR
-----------------------------------------------------------------------------------------
Windows configured before today have no register, and there were exactly two honest ways
to leave them: backfill by the old price rank and record that the machine chose, or leave
them NULL and refuse until a human states one.

**They are left NULL.** A backfilled value is INDISTINGUISHABLE from a stated one to
every reader — the engine, the screen, the auditor — so it would read as the utility's
choice when it was the machine's, which is the exact inference the PO's ruling ends.
CLAUDE.md hard-won law 3: defaults fail closed, and the unsafe option must be the one you
type. The cost is real and is not hidden: a TOU schedule configured before today prices
NOTHING until somebody opens S11 and says which register each window reads. That refusal
names the window and the schedule (BR-RAT-067 clause 1), so it is a task with an address
rather than a silent wrong number.

The alternative was rejected for a second reason too: price rank cannot decide a season
whose windows are equally priced, so a backfill would have covered some rows and not
others, and the ones it covered would have looked settled.

**The count below is the whole point of not backfilling.** An operator running this
migration is told how many windows now have no register, so the gap is work on a list
rather than a surprise on run day.

RLS: the count runs inside its own savepoint. `time_of_use_windows` is ENABLE + FORCE row
level security (rating 0003 / db/rls_rating_w1.sql) and its policy reads
`current_setting('app.tenant_id')`, which RAISES when the setting was never made — which
is exactly the state a migration connection is in. A REPORT must never be able to fail a
deploy, so an unreadable count is reported as unreadable and the migration proceeds.
"""

from django.db import migrations, models, transaction


def report_windows_without_a_register(apps, schema_editor):
    """Say out loud how many configured windows now price nothing, and why.

    Read-only. Deliberately raises nothing: see the RLS note in the module
    docstring — a migration that fails because it could not print a number would
    be a worse defect than the one this column fixes.
    """
    connection = schema_editor.connection
    try:
        with transaction.atomic(using=connection.alias):
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM time_of_use_windows WHERE channel IS NULL")
                unset = cursor.fetchone()[0]
    except Exception as exc:  # noqa: BLE001 — reported, never raised (see docstring)
        print(
            "  rating 0006: could not count the time-of-use windows left without a "
            f"register ({exc.__class__.__name__}). This is expected where row-level "
            "security is FORCEd and the migration connection has no app.tenant_id. "
            "Nothing was written and nothing was backfilled; every window configured "
            "before today still has NO register and will refuse by name at the next "
            "bill run until a human states one on S11."
        )
        return
    if unset:
        print(
            f"  rating 0006: {unset} time-of-use window(s) have NO register and were "
            "NOT backfilled (BR-RAT-067). Each one refuses BY NAME at pricing rather "
            "than being matched by price rank or billed at 0.00 — open the rate "
            "schedule on S11 and say which register each window reads. Until then "
            "those tariffs bill nothing."
        )


class Migration(migrations.Migration):

    # ⚠ STACKED ON ANOTHER LANE'S MIGRATION. `0005_br_ten_057_is_sample` (the BR-TEN-057
    # sample-data flag) was already on disk, uncommitted, when this lane started; two
    # leaves on 0004 would make `migrate` refuse with "multiple leaf nodes". Depending on
    # it is the correct linearisation and is recorded here rather than discovered later.
    dependencies = [
        ("rating", "0005_br_ten_057_is_sample"),
    ]

    operations = [
        migrations.AddField(
            model_name="timeofusewindow",
            name="channel",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="timeofusewindow",
            constraint=models.CheckConstraint(
                condition=models.Q(("channel__isnull", True))
                | models.Q(("channel__in", ("tou_on", "tou_mid", "tou_off"))),
                name="ck_time_of_use_windows_channel",
            ),
        ),
        migrations.RunPython(
            report_windows_without_a_register, migrations.RunPython.noop, elidable=True
        ),
    ]
