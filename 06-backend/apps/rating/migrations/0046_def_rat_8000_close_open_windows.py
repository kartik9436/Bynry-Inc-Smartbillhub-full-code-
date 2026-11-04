# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-8000 — several versions of one rate schedule in force on one
#          date. Ottumwa Water Works: four versions of one sewer schedule in
#          force on 2026-10-29, and its one-time and move-out final bills refuse
#          with `AmbiguousSchedule`.
# Rules:   B2 §2 (the signed no-overlap constraint) · BR-RAT-007 (a period
#          prices on the version in force AT THE SERVICE DATE) · BR-RAT-031 (a
#          NULL `effective_from` IS the draft) · BR-RAT-104 / BR-RAT-1016 verb
#          2 (a CORRECTION restates the SAME window; the corrected row carries
#          `superseded_by`) · CLAUDE.md hard rule 1 (tenant scoping) · hard
#          rule 4 (no issued financial row is updated here — this touches
#          `tariff_versions` only) · hard-won law 14 (a failed statement
#          poisons the whole PostgreSQL transaction; SQLite cannot show it)
# Tests:   06-backend/tests/test_def_rat_8000_no_overlap_pg.py
# Census:  10-scripts/rat_schedule_overlap_census.py — run it BEFORE and AFTER.
# ───────────────────────────────────────────────────────
"""rating 0046 — **close the windows that were left open, and REFUSE the rest.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — this is the only step of the chain that
touches rows a bill was priced from. Row in
`12-governance/09-human-review-ledger.md`.

THREE CASES, AND THEY ARE NOT THE SAME
--------------------------------------
**1 · A CORRECTION — `superseded_by` is set. NOTHING IS DONE.**
`BR-RAT-104` / `BR-RAT-1016` verb 2: a correction restates the SAME window
deliberately, because the figure recorded for that period was wrong. The live
bill run already excludes the corrected row (`selectors.in_force_version`'s
`.filter(superseded_by__isnull=True)`), so the two rows sharing one window are
not a defect — they are the feature. Touching either would rewrite a filing
history a regulator reads.

**2 · GENUINE SUCCESSION — every row live, every `effective_from` DISTINCT, an
older window left OPEN. REPAIRED.** Sorted oldest first, each row whose
`effective_to` IS NULL and which is followed by a later start gets
`effective_to = next.effective_from − 1 day`. **The newest stays open.**
⚠ **ONLY A NULL END IS FILLED. AN END DATE THAT ALREADY EXISTS IS NEVER
MOVED** — somebody typed it, it is what a bill was reproduced against, and
moving it changes which version a past service date resolves to.

**3 · ANYTHING ELSE — REFUSED, LOUDLY, WITH THE ROWS NAMED.**
Two live rows sharing one `effective_from`; two live rows whose STATED end
dates overlap; a stated end that touches the next start. `selectors
.in_force_version`'s own words about the first of those: *"the order-by decides
which one prices — by `effective_from`, which is IDENTICAL on both … That is
not a tie-break, it is a coin toss on a money path."* **A migration that picked
would put a price on a bill on the strength of a guess**, which the prime
directive forbids. So this raises, names every row a person must look at, and
the deploy stops. That is the intended outcome, not a failure of this file.

⚠ **WHAT CASE 3 TOLD ITS OPERATOR TO DO WAS UNDOABLE, AND IT WAS FOUND ON A
REAL STOPPED DEPLOY THE SAME DAY THIS FILE LANDED (`DEF-RAT-8070`).** The refusal named two remedies and
**neither could be carried out**:
  · **CORRECTION** — `services.correct_rate_schedule_version` COPIES the window
    onto the replacement row (`version_fields["effective_from"/"effective_to"]`
    are read off the original, deliberately, because that is what BR-RAT-104
    verb 2 MEANS). So the correction lands on the same window as the row it
    restates and the overlap survives it. Measured on PostgreSQL 16 against the
    reported estate: following the remedy produced **the identical refusal**,
    naming the correction row instead of the corrected one.
  · **CHANGE** — *"give the earlier row the end date it should have had"* — has
    no door. There is no `PATCH /rate-schedules/{id}/versions/{vid}`;
    `services.update_rate_schedule` classes `effective_to` as price content and
    refuses it once a version is activated (BR-RAT-037); and filing a new
    version does not reach the pair either, because
    `_close_open_windows_before` excludes every row whose stated end already
    precedes the new start.
  · And the census it pointed at is **not in the image** — `docker-compose.yml`
    builds this service with `context: ./06-backend`, so the container holding
    the `manage.py` that raised has no `10-scripts/` at all.
**So a real deploy stopped with an instruction nobody could follow**, which is
hard-won law 2's mirror at deploy scale: a live refusal pointing at doors that
are not there. `manage.py rat_resolve_schedule_overlap` is the door, it lives
beside this migration where the operator already is, and it refuses to choose a
date exactly as this file does.

WHY THE REFUSAL IS HERE AND NOT LEFT TO THE CONSTRAINT
------------------------------------------------------
`0047` would also fail on those rows — with PostgreSQL's own message, which
names a constraint and one conflicting key and explains nothing. This refusal
names the tenant, the schedule, every row, its window and its id, and says what
the decision is. A deploy that stops must stop with an answerable question.

⚠ **EVERY TENANT IS ITS OWN SAVEPOINT (hard-won law 14).** On PostgreSQL one
failed statement aborts the whole transaction, so without the nested
`atomic()` one tenant's bad row would roll back every other tenant's repair —
and the suite, on SQLite, which has no aborted-transaction state, would be
green either way. The savepoint is not the tidy option; it is the only one.
⚠ The refusal in case 3 is raised AFTER the walk, deliberately, so one estate's
report lists every schedule a person has to decide about rather than the first.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta

from django.db import migrations, transaction

logger = logging.getLogger(__name__)

NO_TENANT = "00000000-0000-0000-0000-000000000000"


class OverlappingScheduleVersions(RuntimeError):
    """Raised instead of guessing which of two versions prices a date."""


def _enter_tenant(connection, tenant_id):
    """CLAUDE.md hard rule 1: never touch a tenant table without
    `app.tenant_id` set. SQLite has no RLS and no `set_config` — skipped
    honestly, and the same ORM path runs."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _leave_tenant(connection):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NO_TENANT])


def _window(row):
    """The row's in-force window as `[lo, hi)`, with `hi` EXCLUSIVE.

    ⚠ `effective_to` is INCLUSIVE everywhere in this codebase —
    `selectors.in_force_version` asks `effective_to >= service_date`, and every
    writer closes a window with `next_from - 1 day`. So the exclusive upper
    bound is `effective_to + 1`, and a row ending on the day another starts is
    an OVERLAP of one day, not a clean handover. B2 §2's signed expression
    (`daterange(effective_from, coalesce(effective_to,'infinity'))`) is
    half-open and therefore misses exactly that case; `0047` carries the `+ 1`
    and says why.
    """
    if row.effective_to is None:
        return row.effective_from, None
    return row.effective_from, row.effective_to + timedelta(days=1)


def _overlap(a, b):
    a_lo, a_hi = _window(a)
    b_lo, b_hi = _window(b)
    return (a_hi is None or b_lo < a_hi) and (b_hi is None or a_lo < b_hi)


def close_open_windows(apps, schema_editor):
    connection = schema_editor.connection
    Tenant = apps.get_model("tenancy", "Tenant")
    TariffVersion = apps.get_model("rating", "TariffVersion")

    filled = 0
    examined = 0
    corrections_left_alone = 0
    refusals: list[str] = []
    malformed: list[str] = []

    for tenant_id in list(Tenant.objects.values_list("id", flat=True)):
        _enter_tenant(connection, tenant_id)
        by_tariff = defaultdict(list)
        # Drafts are excluded by BR-RAT-031: a NULL `effective_from` has no
        # window, has never priced anything, and `daterange(NULL, …)` would be
        # unbounded below and overlap every dated row of the schedule.
        rows = TariffVersion.objects.filter(
            tenant_id=tenant_id, effective_from__isnull=False
        ).order_by("effective_from", "created_at")
        for row in rows:
            examined += 1
            if row.superseded_by_id is not None:
                corrections_left_alone += 1
                continue
            # ── CASE 4 · A WINDOW THAT ENDS BEFORE IT STARTS ─────────────────
            # ⚠ **THIS FILE VALIDATED OVERLAPS AND NEVER VALIDATED THAT A
            # WINDOW IS WELL-FORMED, SO `0047` FAILED WITH POSTGRESQL'S OWN
            # MESSAGE AFTER THIS ONE REPORTED A CLEAN ESTATE (`DEF-RAT-8074`).**
            # `0047` builds `daterange(effective_from, COALESCE(effective_to +
            # 1, 'infinity'))`, and `daterange` REFUSES a lower bound above its
            # upper bound — so a row whose `effective_to` is two or more days
            # before its `effective_from` raises
            # `DataException: range lower bound must be less than or equal to
            # range upper bound` at `ADD CONSTRAINT`, naming no row, no tenant
            # and no column. That is the exact outcome this file's own docstring
            # says it exists to prevent: *"a deploy that must stop must stop
            # with an answerable question."*
            # It happened on a real deploy: `0046` logged `0 overlap(s) need a
            # person`, was marked applied, and `0047` then died on that message.
            #
            # ⚠ **`effective_to == effective_from - 1` IS LAWFUL AND IS NOT
            # REPORTED.** It yields an EMPTY range, which `daterange` accepts
            # and which overlaps nothing — that is what a window closed on the
            # day before it opened MEANS, and `_close_open_windows_before` can
            # legitimately write it when a new version opens the day after an
            # older one. The predicate is therefore
            # `effective_from > effective_to + 1`, matching `0047`'s expression
            # exactly rather than the looser `effective_to < effective_from`.
            #
            # These rows are held OUT of the overlap walk below: `_window` on an
            # inverted row returns a backwards interval, so `_overlap` would
            # answer about an interval that cannot exist and the report would
            # name the wrong pairs beside the real fault.
            if (
                row.effective_to is not None
                and row.effective_from > row.effective_to + timedelta(days=1)
            ):
                malformed.append(
                    f"tenant {tenant_id} · schedule {row.tariff_id}: version {row.id} "
                    f"[{row.effective_from} → {row.effective_to}] ENDS BEFORE IT STARTS. "
                    "No date range can be built from it, so `0047` cannot even be applied."
                )
                continue
            by_tariff[row.tariff_id].append(row)

        for tariff_id, versions in by_tariff.items():
            try:
                with transaction.atomic():
                    # ── PASS 1 · FILL, and only ever a NULL end ──────────────
                    for earlier, later in zip(versions, versions[1:]):
                        if earlier.effective_to is not None:
                            continue
                        if earlier.effective_from >= later.effective_from:
                            continue  # a same-date tie — pass 2 refuses it
                        earlier.effective_to = later.effective_from - timedelta(days=1)
                        earlier.save(update_fields=["effective_to", "updated_at"])
                        filled += 1
                    # ── PASS 2 · RE-CHECK EVERY PAIR, NOT ONLY NEIGHBOURS ────
                    # ⚠ A pairwise-neighbours-only check is law 7's "looking at
                    # the wrong thing": one row with a stated end date spanning
                    # several later windows overlaps rows that are not adjacent
                    # to it, and the neighbour walk reports one of those and is
                    # silent about the rest. The constraint in 0047 will refuse
                    # them all, so the report must list them all.
                    for i, earlier in enumerate(versions):
                        for later in versions[i + 1 :]:
                            if not _overlap(earlier, later):
                                continue
                            refusals.append(
                                f"tenant {tenant_id} · schedule {tariff_id}: "
                                f"version {earlier.id} [{earlier.effective_from} → "
                                f"{earlier.effective_to or 'open'}] and version "
                                f"{later.id} [{later.effective_from} → "
                                f"{later.effective_to or 'open'}] are both in force on "
                                "at least one date, and no NULL end date remains for "
                                "this migration to fill."
                            )
            except Exception:  # pragma: no cover — reported, never swallowed
                logger.exception(
                    "rating 0046: tenant %s schedule %s could not be repaired; every "
                    "other tenant is unaffected (per-tenant savepoint, law 14)",
                    tenant_id,
                    tariff_id,
                )
                raise

    _leave_tenant(connection)
    logger.info(
        "rating 0046: examined %d dated version(s); filled %d open window(s); "
        "left %d corrected row(s) alone; %d overlap(s) and %d malformed window(s) "
        "need a person",
        examined,
        filled,
        corrections_left_alone,
        len(refusals),
        len(malformed),
    )
    if malformed:
        raise OverlappingScheduleVersions(
            "DEF-RAT-8074 · rating/0046 REFUSES: A WINDOW THAT ENDS BEFORE IT STARTS.\n"
            "`rating/0047` builds a date range from every version's window and a range "
            "cannot start after it ends, so these rows do not merely break the no-overlap "
            "guarantee \u2014 they make the constraint impossible to create at all. Left to "
            "`0047` this is `DataException: range lower bound must be less than or equal to "
            "range upper bound`, which names no tenant, no schedule and no row.\n"
            "\n"
            "A person decides what each window SHOULD say \u2014 this migration will not invent "
            "a date. Do it with the same `manage.py` that printed this:\n"
            "\n"
            "    python manage.py rat_resolve_schedule_overlap\n"
            "\n"
            "It lists these rows, says whether an issued bill was priced on any of them, and "
            "takes the end date you name. Then run `migrate` again.\n"
            + "\n".join(malformed)
            + ("\n\nThere are ALSO overlapping windows on this database, listed after the "
               "malformed ones are fixed." if refusals else "")
        )
    if refusals:
        raise OverlappingScheduleVersions(
            "DEF-RAT-8000 · rating/0046 REFUSES TO GUESS.\n"
            "These rate-schedule versions are in force on the same date and this "
            "migration may not choose which one prices — that is a coin toss on a money "
            "path (`selectors.in_force_version`). A person decides, per row, which of "
            "the two dates was written wrongly.\n"
            "\n"
            "DO THAT HERE, with the same `manage.py` that printed this:\n"
            "\n"
            "    python manage.py rat_resolve_schedule_overlap\n"
            "\n"
            "It lists every row below with the days both versions price, says whether "
            "an issued bill was priced on either, and prints the command for each "
            "reading. It never picks one. Then run `migrate` again.\n\n"
            + "\n".join(refusals)
        )


def reopen_windows(apps, schema_editor):
    """Reverse: a no-op, on purpose, and that is not laziness.

    This migration only ever FILLS a NULL end date, and it cannot know which of
    the end dates now present it wrote — the repair is indistinguishable from a
    clerk having closed the window correctly a month earlier. Re-opening every
    window would manufacture the very defect the chain exists to remove, and on
    a database where `0047`'s constraint is still applied it would be refused
    row by row anyway. The reverse of `0047` removes the guarantee; nothing
    re-creates the overlap.
    """
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0045_def_rat_8000_btree_gist"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(close_open_windows, reopen_windows),
    ]
