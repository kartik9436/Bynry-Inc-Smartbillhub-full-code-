# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-8050 — `discount_versions` carries the same class of fault
#          `DEF-RAT-8000` found on `tariff_versions`: nothing in the database
#          stops two versions of one discount being in force on one date, no
#          writer has ever closed a predecessor's window, and the two readers
#          of the table disagreed about whether the window is even consulted.
# Rules:   B2 §2 (the signed schema — ⚠ **IT DECLARES NOTHING FOR DISCOUNTS AT
#          ALL**; the amendment that adds this constraint is the review-ledger
#          row for `DEF-RAT-8050`) · BR-RAT-1016 verb 2 (a CORRECTION restates
#          the SAME window) · BR-RAT-068/073 (a discount overlays a priced
#          bill) · CLAUDE.md hard rule 1 (tenant scoping) · hard rule 4 (no
#          issued bill's basis may move — see the repricing note below) ·
#          hard-won law 14 (a failed statement poisons the whole PostgreSQL
#          transaction; SQLite cannot show it)
# Tests:   06-backend/tests/test_def_rat_8050_discount_overlap_pg.py
# Census:  10-scripts/rat_schedule_overlap_census.py --discounts — BEFORE and
#          AFTER.
# ───────────────────────────────────────────────────────
"""rating 0048 — **close the discount windows that were left open, and REFUSE
the rest.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — rating math and migration ordering.
Row in `12-governance/09-human-review-ledger.md`.

⚠⚠ **THE ONE THING THAT IS NOT THE SAME AS `rating/0046`: SUPERSESSION HERE IS
A STATUS, NOT A FOREIGN KEY.** `discount_versions` has no `superseded_by_
version_id` in the sense `tariff_versions` does — it has `superseded_by` AND a
`status` of `superseded`, and `discounts.py` says which one is the fact:
*"`superseded` is what a later version does to an earlier one"*. Every reader
that prices asks for `status = 'active'` and nothing else, so **`active` is the
only status this migration and `0049` look at**. A `draft`, `pending_approval`,
`scheduled`, `rejected` or `superseded` row prices nothing, on any date, and is
left exactly where it is.

THAT IS ESTABLISHED FROM THE CODE, NOT INFERRED FROM THE NAMES
---------------------------------------------------------------
`scheduled` reads like *"approved, holds a real future window, therefore
belongs inside the constraint"*. **It does not, and including it would refuse a
shipped flow.** Two facts decide it:

  1 · **Nothing prices a `scheduled` row.** `discount_services.active_version`
      — the only read behind `price_account_discounts` — filters
      `status=VERSION_ACTIVE`. So does `resolution_catalogue._discount_facts`
      and so does `discount_enrolments_read`. There is no fourth reader.
  2 · **`activate_discount_version` supersedes by STATUS and always did**, so
      the incumbent's `effective_to` stays NULL — an OPEN window — right up
      until the successor is activated. Put `scheduled` inside the constraint
      and approving a successor to a live discount is refused, every time,
      because the incumbent's open window swallows every future date.

CASES, AND THEY ARE NOT THE SAME
---------------------------------
**1 · NOT `active`. NOTHING IS DONE.** See above.

**2 · A CORRECTION — two `active` rows on one window, one `corrects` the
other. THIS CANNOT REACH HERE, AND SAYING SO IS THE POINT.**
`correct_discount_version` mints the correction `active` and flips the
original to `superseded` in the same transaction, so a settled correction is
already case 1. A correction caught MID-TRANSACTION is what `0049`'s
`DEFERRABLE INITIALLY DEFERRED` exists for, and no committed row has that
shape.

**3 · GENUINE SUCCESSION — several `active` rows, every `effective_from`
DISTINCT, an older window left OPEN. REPAIRED.** Oldest first, each row whose
`effective_to` IS NULL and which is followed by a later start gets
`effective_to = next.effective_from − 1 day`. **The newest stays open.**
⚠ **ONLY A NULL END IS FILLED. A STATED END IS NEVER MOVED** — somebody typed
it, and moving it changes which version a past service date resolves to.

**4 · ANYTHING ELSE — REFUSED, LOUDLY, WITH THE ROWS NAMED.** Two `active`
rows sharing one `effective_from`; two whose STATED ends overlap; a stated end
that TOUCHES the next start. `active_version`'s repaired docstring on exactly
this: *"That is not a tie-break, it is a coin toss on a money path."* A
migration that picked would put a subsidy figure on a bill on the strength of
a guess. So this raises, names every row a person must look at, and the deploy
stops. **That is the intended outcome, not a failure of this file.**

⚠ **WHY THE REFUSAL IS HERE AND NOT LEFT TO `0049`.** `ADD CONSTRAINT`
validates every existing row and fails with PostgreSQL's own message, which
names one conflicting key and explains nothing. This names the tenant, the
discount, every row, its window and its id, and says what the decision is.

⚠ **HARD RULE 4, ANSWERED RATHER THAN ASSERTED.** Closing an open window
changes what a PAST date resolves to, so it *can* move an already-granted
subsidy's basis. Two things bound it on this object, and neither is true of
`tariff_versions`: a grant already made carries `discount_grants
.discount_version_id` (NOT NULL) and is never re-resolved; and every row this
migration closes is `active` alongside a LATER `active` row, which is a state
the application has never been able to produce — `activate_discount_version`
supersedes wholesale. The repricing question is measured rather than reasoned
about: `rat_schedule_overlap_census.py --discounts --reprice-check`.

⚠ **EVERY TENANT IS ITS OWN SAVEPOINT (hard-won law 14).** On PostgreSQL one
failed statement aborts the whole transaction, so without the nested
`atomic()` one tenant's bad row would roll back every other tenant's repair —
and the suite, on SQLite, which has no aborted-transaction state, would be
green either way.
⚠ The refusal is raised AFTER the walk so one estate's report lists every
discount a person has to decide about rather than the first.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta

from django.db import migrations, transaction

logger = logging.getLogger(__name__)

NO_TENANT = "00000000-0000-0000-0000-000000000000"

#: Read from `apps.rating.discounts.VERSION_ACTIVE` at write time and pinned
#: here as a literal on purpose: a migration is a statement about the database
#: as it was, and importing a live constant makes an applied migration change
#: meaning when somebody renames it.
ACTIVE = "active"


class OverlappingDiscountVersions(RuntimeError):
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
    `active_version` asks `effective_to >= when`, and the writer added by
    `DEF-RAT-8050` closes a window with `next_from - 1 day`. So the exclusive
    upper bound is `effective_to + 1`, and a row ending on the day another
    starts is an OVERLAP of one day, not a clean handover.
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
    DiscountVersion = apps.get_model("rating", "DiscountVersion")

    filled = 0
    examined = 0
    not_active_left_alone = 0
    refusals: list[str] = []

    for tenant_id in list(Tenant.objects.values_list("id", flat=True)):
        _enter_tenant(connection, tenant_id)
        by_discount = defaultdict(list)
        # A NULL `effective_from` has no window and has never priced anything;
        # `daterange(NULL, …)` would be unbounded below and overlap every
        # dated row of the discount. Same exclusion as `rating/0046`.
        rows = DiscountVersion.objects.filter(
            tenant_id=tenant_id, effective_from__isnull=False
        ).order_by("effective_from", "version_no")
        for row in rows:
            examined += 1
            if row.status != ACTIVE:
                not_active_left_alone += 1
                continue
            by_discount[row.discount_id].append(row)

        for discount_id, versions in by_discount.items():
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
                    # ⚠ A neighbours-only check is law 7's "looking at the
                    # wrong thing": one row with a stated end spanning several
                    # later windows overlaps rows that are not adjacent to it,
                    # and the neighbour walk reports one and is silent about
                    # the rest. `0049` refuses them all, so the report must
                    # list them all.
                    for i, earlier in enumerate(versions):
                        for later in versions[i + 1 :]:
                            if not _overlap(earlier, later):
                                continue
                            refusals.append(
                                f"tenant {tenant_id} · discount {discount_id}: "
                                f"version {earlier.version_no} ({earlier.id}) "
                                f"[{earlier.effective_from} → "
                                f"{earlier.effective_to or 'open'}] and version "
                                f"{later.version_no} ({later.id}) "
                                f"[{later.effective_from} → "
                                f"{later.effective_to or 'open'}] are both ACTIVE on at "
                                "least one date, and no NULL end date remains for this "
                                "migration to fill."
                            )
            except Exception:  # pragma: no cover — reported, never swallowed
                logger.exception(
                    "rating 0048: tenant %s discount %s could not be repaired; every "
                    "other tenant is unaffected (per-tenant savepoint, law 14)",
                    tenant_id,
                    discount_id,
                )
                raise

    _leave_tenant(connection)
    logger.info(
        "rating 0048: examined %d dated version(s); filled %d open window(s); "
        "left %d non-active row(s) alone; %d overlap(s) need a person",
        examined,
        filled,
        not_active_left_alone,
        len(refusals),
    )
    if refusals:
        raise OverlappingDiscountVersions(
            "DEF-RAT-8050 · rating/0048 REFUSES TO GUESS.\n"
            "These discount versions are ACTIVE on the same date and this migration may "
            "not choose which one prices — that is a coin toss on a money path "
            "(`discount_services.active_version`). A person must decide, per row, "
            "whether it is a CORRECTION (correct the right one through "
            "`POST /discounts/{id}/versions/{vid}/corrections`, which supersedes the "
            "other) or a CHANGE (give the earlier row the end date it should have "
            "had). Then re-run `10-scripts/rat_schedule_overlap_census.py --discounts` "
            "and migrate again.\n\n" + "\n".join(refusals)
        )


def reopen_windows(apps, schema_editor):
    """Reverse: a no-op, on purpose, and that is not laziness.

    This migration only ever FILLS a NULL end date, and it cannot know which of
    the end dates now present it wrote — the repair is indistinguishable from a
    clerk having closed the window correctly a month earlier. Re-opening every
    window would manufacture the very defect the chain exists to remove, and on
    a database where `0049`'s constraint is still applied it would be refused
    row by row anyway.
    """
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0047_def_rat_8000_no_overlap_constraint"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(close_open_windows, reopen_windows),
    ]
