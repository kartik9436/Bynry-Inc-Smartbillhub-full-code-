# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-8050 — nothing in the database stops two versions of one
#          discount being in force on one date, and both readers of the table
#          resolved the tie by `.first()`.
# Rules:   B2 §2 — ⚠ **THIS CONSTRAINT IS NOT IN B2. THE SIGNED SCHEMA
#          DECLARES NOTHING WHATEVER FOR `discounts` OR `discount_versions`**
#          (zero occurrences of the word "discount" in
#          `04-docs/02-decisions/02-database-design-brief.md`). It is added by
#          the B2 amendment that rides with this commit, with a row in
#          `12-governance/09-human-review-ledger.md`, because a constraint
#          nobody signed is a constraint nobody can check — and `G137` reads
#          B2 to decide what must exist. · BR-RAT-1016 verb 2 (a CORRECTION
#          restates the SAME window) · CLAUDE.md 🔒 migration ordering ·
#          hard-won law 7 (prove it RED in the harness that runs it) · law 14
# Tests:   06-backend/tests/test_def_rat_8050_discount_overlap_pg.py
# ───────────────────────────────────────────────────────
"""rating 0049 — **one in-force discount version per discount per day, in the
database.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering and a money path.
Row in `12-governance/09-human-review-ledger.md`.

    ALTER TABLE discount_versions
      ADD CONSTRAINT ex_discount_versions_no_overlap
      EXCLUDE USING gist (
        tenant_id WITH =, discount_id WITH =,
        daterange(effective_from,
                  COALESCE(effective_to + 1, 'infinity'::date)) WITH &&
      )
      WHERE (status = 'active' AND effective_from IS NOT NULL)
      DEFERRABLE INITIALLY DEFERRED;

`btree_gist` is already installed by `rating/0045`, which is what makes an
`EXCLUDE` mixing equality columns with a range operator possible at all. This
migration adds no extension; it depends on `0048`, which depends on `0047`,
which depends on `0045`.

THE FOUR DEVIATIONS FROM `rating/0047`, EACH CHECKED RATHER THAN COPIED
========================================================================

**1 · THE PREDICATE IS `status = 'active'`, NOT A NULL CHECK ON A FOREIGN
KEY.** `tariff_versions` records supersession as `superseded_by_version_id`
and `0047` keys off it. **`discount_versions` records it as a STATUS** —
`discounts.py`: *"`superseded` is what a later version does to an earlier
one"* — and the column `superseded_by` exists beside it. Only ONE of those is
the fact, and it is the status: every reader that prices filters
`status='active'` and NONE filters `superseded_by`. Adding `AND superseded_by
IS NULL` here would be a second representation of one fact, which is the
thing that let the two readers of this table come apart in the first place.

**WHICH STATUSES MAY PRICE — ESTABLISHED FROM THE CODE.** There are exactly
three readers of `discount_versions` that feed money or a money screen, and
all three ask for `active` and nothing else:
  * `discount_services.active_version` → `price_account_discounts` (R6);
  * `resolution_catalogue._discount_facts` (R6's catalogue half);
  * `discount_enrolments_read`.
So `draft`, `pending_approval`, `scheduled`, `rejected` and `superseded` price
nothing, on any date.

⚠ **`scheduled` IS THE ONE THAT LOOKS LIKE IT BELONGS INSIDE AND DOES NOT.**
It reads as *approved, holds a real future window*. But
`activate_discount_version` supersedes by STATUS, so the incumbent's
`effective_to` is NULL — an OPEN window — until its successor is activated.
Put `scheduled` inside this predicate and **approving any successor to any
live discount is refused**, because the incumbent's open window contains every
future date. That is a shipped flow, and the constraint would have broken it.

⚠ **AND THE ANSWER TO *"can a `pending_approval` version collide with the
`active` one"* IS YES, DELIBERATELY.** A version awaiting approval is a
PROPOSAL. Proposing a window that overlaps the incumbent's is the ordinary
shape of every rate change there is; refusing it would mean a utility could
never draft next year's discount while this year's is running.

**2 · `AND effective_from IS NOT NULL`.** A `draft` may be dateless
(`BR-RAT-031`'s shape, and `uq_discount_versions_one_draft` is partial for the
same reason), and `daterange(NULL, …)` is unbounded BELOW. `activate_discount_
version` already refuses a NULL `effective_from`, so on today's data the
clause is redundant — it is written because a redundant predicate costs
nothing and a missing one makes every draft collide with every dated row.

**3 · `DEFERRABLE INITIALLY DEFERRED`, AND WITHOUT IT EVERY CORRECTION
BREAKS.** `correct_discount_version` creates the correction row **`active`,
carrying the corrected row's `effective_from` and `effective_to` VERBATIM**
— that identical window is the whole definition of a correction (BR-RAT-1016
verb 2) — and only THEN flips the original to `superseded`. For the instant
between those two statements there are two `active` rows on one window. An
immediate constraint refuses the INSERT; a deferred one is checked at COMMIT,
by which time the flip is done.
⚠ `activate_discount_version` writes in the safe order (supersede the others,
then activate this one) and would survive an immediate constraint. **The
correction would not**, and it is the commoner act.
⚠ Deferral means a violation surfaces at COMMIT, so the whole transaction is
then aborted (law 14). Anything catching `IntegrityError` around a discount
version write must use a SAVEPOINT — `create_discount_version` already does.

**4 · `effective_to + 1` — THE COLUMN IS INCLUSIVE AND `daterange` IS NOT.**
`active_version` asks `effective_to >= when`, and `_close_open_windows_before`
closes a window with `next_from - 1 day`. A half-open `daterange(from, to)`
would let a version ending `2026-03-31` and one starting `2026-03-31` both
price 2026-03-31 while the constraint said they did not overlap — a one-day
coin toss on a money path, and precisely the case `rating/0047` had to correct
in B2's own signed expression.

⚠ **SQLITE GETS NOTHING, STATED RATHER THAN FAKED.** SQLite has no range type
and no exclusion constraint, so the whole test suite runs WITHOUT this
guarantee (hard-won law 14) and
`tests/test_def_rat_8050_discount_overlap_pg.py` skips itself by name on any
vendor but PostgreSQL rather than passing vacuously. **The application-side
refusals added in the same commit — `active_version` and
`_discount_facts` — are the layer that still answers there**, and that is why
they raise rather than pick.

⚠ **THE CONSTRAINT IS NOT DECLARED IN `models.Meta`**, for the reason
`rating/0047` gives: a `django.contrib.postgres` constraint emits DDL SQLite
cannot parse and `django.contrib.postgres` is not in `INSTALLED_APPS`.
`DiscountVersion`'s docstring names this constraint and this migration.

⚠ **0048 MUST HAVE RUN.** `ADD CONSTRAINT` validates every existing row, so on
an estate holding an overlap this statement fails with PostgreSQL's own
message. `0048` exists to reach that same stop with a report a person can act
on.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

ADD = """
ALTER TABLE discount_versions
  ADD CONSTRAINT ex_discount_versions_no_overlap
  EXCLUDE USING gist (
    tenant_id WITH =,
    discount_id WITH =,
    daterange(effective_from, COALESCE(effective_to + 1, 'infinity'::date)) WITH &&
  )
  WHERE (status = 'active' AND effective_from IS NOT NULL)
  DEFERRABLE INITIALLY DEFERRED;
"""

DROP = "ALTER TABLE discount_versions DROP CONSTRAINT IF EXISTS ex_discount_versions_no_overlap;"


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0048_def_rat_8050_close_discount_windows"),
    ]

    operations = [
        PostgresOnlySQL(sql=ADD, reverse_sql=DROP),
    ]
