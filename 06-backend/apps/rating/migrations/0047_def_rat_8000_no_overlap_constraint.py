# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-8000 — B2 §2's no-overlap constraint was signed and never
#          built, so a rate schedule can hold several versions in force on one
#          date and billing either refuses (`AmbiguousSchedule`) or picks.
# Rules:   B2 §2 (the signed `EXCLUDE USING gist`) · BR-RAT-007 · BR-RAT-031
#          (NULL `effective_from` IS the draft) · BR-RAT-104 / BR-RAT-1016 verb
#          2 (a CORRECTION restates the SAME window) · CLAUDE.md 🔒 migration
#          ordering · hard-won law 7 (prove it RED in the harness that runs it)
# Tests:   06-backend/tests/test_def_rat_8000_no_overlap_pg.py
# ───────────────────────────────────────────────────────
"""rating 0047 — **B2 §2's no-overlap guarantee, finally in the database.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering and a money path.
Row in `12-governance/09-human-review-ledger.md`.

    ALTER TABLE tariff_versions
      ADD CONSTRAINT ex_tariff_versions_no_overlap
      EXCLUDE USING gist (
        tenant_id WITH =, tariff_id WITH =,
        daterange(effective_from,
                  COALESCE(effective_to + 1, 'infinity'::date)) WITH &&
      )
      WHERE (effective_from IS NOT NULL AND superseded_by_version_id IS NULL)
      DEFERRABLE INITIALLY DEFERRED;

⚠⚠ **THREE THINGS DIFFER FROM B2 §2's LITERAL TEXT. EACH IS A LATER RATIFIED
RULE THAT DID NOT EXIST WHEN B2 WAS WRITTEN, AND THE LITERAL CONSTRAINT WOULD
BREAK A SHIPPED FEATURE.** They are written out here rather than left to be
inferred, and each is in the decision log with its worked figure.

**1 · `WHERE effective_from IS NOT NULL` — BR-RAT-031, the resumable draft.**
B2 declares `effective_from NOT NULL`. `rating/0004` made it NULLABLE because
**a NULL `effective_from` IS the draft**, and recorded that as a modification
of B2 in its own header. `daterange(NULL, …)` is unbounded BELOW, so without
this predicate a single saved draft would overlap every dated version of its
schedule and no tenant with a draft could be migrated at all.
`uq_tariff_versions_one_draft` is partial for exactly this reason; this
predicate is that precedent, one constraint along.

**2 · `AND superseded_by_version_id IS NULL` — BR-RAT-104 / BR-RAT-1016 verb 2,
the CORRECTION.** A correction **restates the SAME window** — PO, 2026-09-17,
*"it is not a new rate or it is not a change in rate - it is just an error
handling"* — so a corrected schedule ALWAYS holds two rows with identical
windows, by design. **The literal B2 constraint would refuse every correction
this product has ever taken**, on all five priced objects' shared verb. The
predicate makes the constraint guarantee exactly what the live bill run needs:
`selectors.in_force_version` filters `superseded_by__isnull=True` and then asks
for one row, and this is that same sentence enforced by the database.

**3 · `effective_to + 1` — the column is INCLUSIVE and `daterange` is not.**
`in_force_version` asks `effective_to >= service_date`, and every writer closes
a window with `next_from - 1 day`. B2's `daterange(effective_from,
COALESCE(effective_to,'infinity'))` is half-open `[lo, hi)`, so a version
ending `2026-03-31` and a version starting `2026-03-31` do **not** overlap by
B2's expression — and both ARE returned by `in_force_version` on 2026-03-31,
which is the coin toss the constraint exists to prevent. B2's expression is
off by one day in the permissive direction; the intent it states in its own
comment (*"no overlapping in-force windows per tariff"*) is what is built.

⚠ **`DEFERRABLE INITIALLY DEFERRED`, AND WITHOUT IT CORRECTIONS BREAK EVEN WITH
PREDICATE 2.** `services.correct_rate_schedule_version` writes the correction
row FIRST and stamps `superseded_by` on the original SECOND, inside one
`transaction.atomic()`. For the instant between those two statements there are
two live rows on one window. An immediate constraint refuses the INSERT; a
deferred one is checked at COMMIT, by which time the stamp is on. The same
deferral makes every other writer's ordering irrelevant, which is worth more
than the one case it was written for.
⚠ It also means a violation surfaces at COMMIT rather than at the statement —
hard-won law 14's world, where the whole transaction is then aborted. Anything
catching `IntegrityError` around a version write must use a SAVEPOINT.

⚠ **SQLITE GETS NOTHING, STATED RATHER THAN FAKED.** SQLite has no range type
and no exclusion constraint, so there is no *"same guarantee in the only form
this engine has"* to offer — unlike `integrations/0001`, which could fall back
to a partial UNIQUE index because its exclusion was on equality alone. The
whole test suite therefore runs WITHOUT this guarantee (hard-won law 14), and
`tests/test_def_rat_8000_no_overlap_pg.py` skips itself by name on any vendor
but PostgreSQL rather than passing vacuously.

⚠ **THE CONSTRAINT IS NOT DECLARED IN `models.Meta`.** The repo's one existing
exclusion constraint (`integrations/0001`, `ex_integration_credential_one_
active`) is raw vendor-branched DDL for the same reason: a
`django.contrib.postgres` constraint in `Meta` emits DDL SQLite cannot parse,
and `django.contrib.postgres` is not in `INSTALLED_APPS`. `TariffVersion`'s
docstring names this constraint and this migration, so the model still says
what the database does.

⚠ **0046 MUST HAVE RUN.** `ADD CONSTRAINT` validates every existing row, so on
an estate that still holds an overlap this statement fails with PostgreSQL's
own message, which names one conflicting key and explains nothing. 0046 exists
to reach that same stop with a report a person can act on.
"""

import logging
from datetime import timedelta

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

logger = logging.getLogger(__name__)

NO_TENANT = "00000000-0000-0000-0000-000000000000"


class MalformedWindow(RuntimeError):
    """Raised instead of letting `ADD CONSTRAINT` fail with PostgreSQL's message."""


def _refuse_malformed_windows(apps, schema_editor):
    """**REFUSE A WINDOW THAT ENDS BEFORE IT STARTS, HERE, WHERE IT ACTUALLY FIRES.**

    ⚠ **`0046` GAINED THIS CHECK FIRST AND THAT WAS THE WRONG FILE FOR EVERY
    DATABASE THAT HAD ALREADY APPLIED IT (`DEF-RAT-8074`).** Django never re-runs
    an applied migration, so on the estate this was found on — where `0046` had
    already run, silently, before the check existed — the guard could never
    execute and `ADD CONSTRAINT` below went on failing with

        DataException: range lower bound must be less than or equal to range
        upper bound

    which names no tenant, no schedule, no row and no column. `0046`'s copy
    protects a database that has not reached it yet; THIS copy protects the one
    that has, which is every database that ever got this far. Both are wanted:
    `0046` stops earlier and reports overlaps in the same breath.

    The predicate is this migration's OWN expression — `effective_from >
    effective_to + 1` — and not the looser `effective_to < effective_from`: an
    end exactly one day before the start is an EMPTY range, which `daterange`
    accepts, which overlaps nothing, and which `_close_open_windows_before`
    legitimately writes when a new version opens the day after an older one.

    ⚠ It is SQL over one table rather than the ORM, because the range must NOT
    be built to find these rows — building it is the thing that raises. Dates are
    compared instead. Hard rule 1: `app.tenant_id` is set per tenant, or RLS
    FORCE returns nothing and this guard reports a clean estate over the row that
    is about to stop the deploy.
    """
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM tenants ORDER BY id")
        tenants = [row[0] for row in cursor.fetchall()]
        bad = []
        for tenant_id in tenants:
            cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])
            cursor.execute(
                "SELECT v.tariff_id, v.id, v.effective_from, v.effective_to "
                "  FROM tariff_versions v "
                " WHERE v.tenant_id = %s AND v.effective_from IS NOT NULL "
                "   AND v.effective_to IS NOT NULL "
                "   AND v.superseded_by_version_id IS NULL "
                "   AND v.effective_from > v.effective_to + 1",
                [str(tenant_id)],
            )
            for tariff_id, version_id, lo, hi in cursor.fetchall():
                bad.append(
                    f"tenant {tenant_id} · schedule {tariff_id}: version {version_id} "
                    f"[{lo} → {hi}] ENDS BEFORE IT STARTS."
                )
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NO_TENANT])
    # ── AND THE OVERLAPS, FOR THE SAME REASON THE ROWS ABOVE ARE CHECKED HERE ──
    # ⚠ **`0046`'s OVERLAP WALK CANNOT RE-RUN EITHER.** The first version of this
    # pre-flight checked only malformed windows, which fixed the instance and left
    # the hole: an estate that applied `0046` before gaining an overlap reaches
    # `ADD CONSTRAINT` with no walk having seen it, and PostgreSQL answers
    # `ExclusionViolation: conflicting key value violates exclusion constraint`,
    # naming ONE conflicting key and no tenant, schedule or decision. `0046`'s own
    # docstring says it exists to *"reach that same stop with a report a person can
    # act on"* — and it cannot, for any database already past it. So both of its
    # checks live here too.
    # The range IS built for this one, which is safe because the malformed rows
    # were refused above and the predicate excludes any that remain.
    overlaps = []
    with connection.cursor() as cursor:
        for tenant_id in tenants:
            cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])
            cursor.execute(
                "SELECT v.tariff_id, v.id, v.effective_from, v.effective_to, "
                "       w.id, w.effective_from, w.effective_to "
                "  FROM tariff_versions v JOIN tariff_versions w "
                "    ON w.tenant_id = v.tenant_id AND w.tariff_id = v.tariff_id AND w.id > v.id "
                " WHERE v.tenant_id = %s "
                "   AND v.effective_from IS NOT NULL AND w.effective_from IS NOT NULL "
                "   AND v.superseded_by_version_id IS NULL "
                "   AND w.superseded_by_version_id IS NULL "
                "   AND (v.effective_to IS NULL OR v.effective_from <= v.effective_to + 1) "
                "   AND (w.effective_to IS NULL OR w.effective_from <= w.effective_to + 1) "
                "   AND daterange(v.effective_from, "
                "                 COALESCE(v.effective_to + 1, 'infinity'::date)) "
                "    && daterange(w.effective_from, "
                "                 COALESCE(w.effective_to + 1, 'infinity'::date))",
                [str(tenant_id)],
            )
            for tariff_id, a_id, a_lo, a_hi, b_id, b_lo, b_hi in cursor.fetchall():
                overlaps.append(
                    f"tenant {tenant_id} · schedule {tariff_id}: version {a_id} "
                    f"[{a_lo} → {a_hi or 'open'}] and version {b_id} "
                    f"[{b_lo} → {b_hi or 'open'}] are both in force on at least one date."
                )
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NO_TENANT])

    logger.info(
        "rating 0047: checked %d tenant(s); %d window(s) end before they start and "
        "%d overlapping pair(s) need a person",
        len(tenants),
        len(bad),
        len(overlaps),
    )
    if overlaps and not bad:
        raise MalformedWindow(
            "DEF-RAT-8074 · rating/0047 REFUSES: TWO VERSIONS IN FORCE ON ONE DATE.\n"
            "`rating/0046` walks for these, and on this database it has ALREADY BEEN "
            "APPLIED \u2014 Django never re-runs an applied migration, so its walk never saw "
            "these rows. Without this check the next line is PostgreSQL's own "
            "`ExclusionViolation`, which names one conflicting key and no decision.\n"
            "\n"
            "A person decides which of the two dates was written wrongly. Do it with the "
            "same `manage.py` that printed this:\n"
            "\n"
            "    python manage.py rat_resolve_schedule_overlap\n"
            "\n"
            "Then run `migrate` again.\n"
            + "\n".join(overlaps)
        )
    if bad:
        raise MalformedWindow(
            "DEF-RAT-8074 · rating/0047 REFUSES: A WINDOW THAT ENDS BEFORE IT STARTS.\n"
            "This constraint builds a date range from every version's window, and a range "
            "cannot start after it ends \u2014 so these rows do not merely break the "
            "no-overlap guarantee, they make the constraint impossible to create. Without "
            "this check the next line is PostgreSQL's own `DataException: range lower bound "
            "must be less than or equal to range upper bound`, which names nothing.\n"
            "\n"
            "A person decides what each window SHOULD say; no migration will invent a date. "
            "Do it with the same `manage.py` that printed this:\n"
            "\n"
            "    python manage.py rat_resolve_schedule_overlap\n"
            "\n"
            "It lists these rows with the bills counted, takes the end date you name, and "
            "takes `--clear-end` when the version has no end at all \u2014 which is the usual "
            "answer for the newest version of a schedule. Then run `migrate` again.\n"
            + "\n".join(bad)
            + (
                f"\n\nThere are ALSO {len(overlaps)} overlapping pair(s) on this database; "
                "they are listed once these are fixed."
                if overlaps
                else ""
            )
        )

ADD = """
ALTER TABLE tariff_versions
  ADD CONSTRAINT ex_tariff_versions_no_overlap
  EXCLUDE USING gist (
    tenant_id WITH =,
    tariff_id WITH =,
    daterange(effective_from, COALESCE(effective_to + 1, 'infinity'::date)) WITH &&
  )
  WHERE (effective_from IS NOT NULL AND superseded_by_version_id IS NULL)
  DEFERRABLE INITIALLY DEFERRED;
"""

DROP = "ALTER TABLE tariff_versions DROP CONSTRAINT IF EXISTS ex_tariff_versions_no_overlap;"


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0046_def_rat_8000_close_open_windows"),
    ]

    operations = [
        # ⚠ BEFORE the DDL, and that order is the whole point: `ADD CONSTRAINT`
        # cannot be reached with a malformed row present, so the refusal has to
        # come first or PostgreSQL's opaque message wins the race.
        migrations.RunPython(_refuse_malformed_windows, migrations.RunPython.noop),
        PostgresOnlySQL(sql=ADD, reverse_sql=DROP),
    ]
