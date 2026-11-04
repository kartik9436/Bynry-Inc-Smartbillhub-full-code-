# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-8070 — `rating/0046` stops a deploy on a rate-schedule
#          overlap it may not resolve, and names two remedies: a CORRECTION
#          through `POST /rate-schedules/{id}/versions/{vid}/corrections`, and
#          a CHANGE — *"give the earlier row the end date it should have had"*.
#          **NEITHER CAN BE DONE.** A correction COPIES the window
#          (`services.correct_rate_schedule_version`, the two lines that set
#          `version_fields["effective_from"/"effective_to"]` from the original),
#          so the overlap survives it — measured on PostgreSQL 16: following
#          that remedy left the identical refusal, naming the correction row.
#          And nothing in the product moves a stated `effective_to`: there is no
#          `PATCH …/versions/{vid}`, `update_rate_schedule` classes
#          `effective_to` as price content and refuses it once a version is
#          activated (BR-RAT-037), and no management command touched it. So the
#          deploy had no exit at all. This is that exit.
# Rules:   B2 §2 (the signed no-overlap constraint, built as `rating/0047`) ·
#          BR-RAT-007 (a period prices on the version in force AT THE SERVICE
#          DATE) · BR-RAT-031 (a NULL `effective_from` IS the draft) ·
#          BR-RAT-104 / BR-RAT-1016 verb 2 + BR-RAT-1044 (a corrected row's
#          window is settled and is never moved) · CLAUDE.md hard rule 1
#          (tenant scoping) · hard rule 4 (an issued bill is reproduced from
#          the version in force at its service date) · hard rule 7 (every money
#          action writes `audit_log`)
# Tests:   06-backend/tests/test_def_rat_8070_stated_end_overlap_pg.py
# Census:  the report below is the same question
#          `10-scripts/rat_schedule_overlap_census.py` asks — run that one when
#          you have the repo; this one when you have only the container.
# ───────────────────────────────────────────────────────
"""**CARRY OUT A PERSON'S DECISION ABOUT AN OVERLAPPING RATE-SCHEDULE WINDOW.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — it writes a column that decides which stored version
prices a service date, which is money. Row in
`12-governance/09-human-review-ledger.md`.

⚠ **IT NEVER CHOOSES A DATE, AND THAT IS THE WHOLE DESIGN.** `rating/0046`
refuses to guess which of two versions prices a date because that is a coin toss
on a money path; a repair tool that guessed on its behalf would be the same coin
toss wearing a different hat. So the end date is an ARGUMENT. Run with no
arguments and it reports what is owed and prints the command for each option;
run with a version and a date and it writes exactly that, or refuses and says
why.

⚠ **IT LIVES IN `06-backend/` BECAUSE `10-scripts/` IS NOT IN THE IMAGE.**
`docker-compose.yml` builds this service with `context: ./06-backend` and the
Dockerfile's last line is `COPY . .`, so the container that just failed
`manage.py migrate` has **no `10-scripts/` directory at all** — and `0046`'s
refusal told its operator to run a tool from it. A remedy an operator cannot
reach is hard-won law 2's mirror: a live refusal pointing at a door that is not
there. This is reachable by the same `manage.py` that raised.

    python manage.py rat_resolve_schedule_overlap
    python manage.py rat_resolve_schedule_overlap --version-id <vid> --end-on 2026-07-30
    python manage.py rat_resolve_schedule_overlap --version-id <vid> --end-on 2026-07-30 --apply

── WHAT THE OVERLAP QUESTION IS, AND WHY IT IS ASKED IN SQL ──────────────────
`effective_to` is INCLUSIVE everywhere in this codebase —
`selectors.in_force_version` asks `effective_to >= service_date` — and
`daterange` is half-open, so the window is `[effective_from, effective_to + 1)`.
That `+ 1` is the whole of `DEF-RAT-8000`: without it a version ending
`2026-07-31` and a version starting `2026-07-31` do not look like an overlap and
both ARE in force on `2026-07-31`.

⚠ **THE PREDICATE BELOW IS `rating/0047`'s CONSTRAINT EXPRESSION, ASKED OF THE
DATABASE, RATHER THAN A THIRD PYTHON COPY OF IT.** `0046` has one copy and the
census has another; hard-won law 5 says what a third would be worth. The
authority on whether this database will accept `ADD CONSTRAINT` is the
constraint's own expression, so that is what is evaluated — which also means a
clean report here and a refused `ADD CONSTRAINT` cannot disagree.

── WHAT IT REFUSES, EACH FOR A NAMED RULE ────────────────────────────────────
  · a version id that is not in an overlapping group — this is the overlap
    door, not a general window editor, and BR-RAT-037 keeps an in-force window
    out of everything else's reach;
  · a SUPERSEDED row — BR-RAT-1044: a corrected row's window is settled at the
    moment it is corrected, `0046` says the same in its own words, and
    `0047`'s predicate excludes it, so moving it fixes nothing and falsifies a
    filing history a regulator reads;
  · a DRAFT (NULL `effective_from`) — BR-RAT-031: it has no window;
  · an end before the start — the inverted window
    `_validate_version_fields` refuses by name as `window_inverted`;
  · a date that would leave the row still overlapping a live sibling — a repair
    that does not repair is worse than a refusal, because the operator learns
    it failed on the next `migrate` rather than here;
  · a row an ISSUED bill was priced from for a date the new window would drop —
    hard rule 4 with BR-RAT-007: the bill itself is immutable and its lines
    carry their `tariff_version_id` stamp, but re-deriving that period would
    then resolve to a different version, and nobody gets to decide that here.

⚠ **THE REPORT NAMES BOTH READINGS AND RECOMMENDS NEITHER.** Two live rows
whose windows touch disagree about one day, and there are exactly two ways to
read that: the earlier row's end was written one day long, or the later row's
start was written one day early. Both are ordinary; only the utility knows
which price it filed. Printing the two commands is the plain-English-with-a-
figure presentation this repo asks for — it is not a recommendation, and this
file must never acquire one.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from core import audit
from core.tenancy import tenant_context

#: ⚠ **A ROW MUST BE WELL-FORMED BEFORE A RANGE IS BUILT FROM IT, AND THE FIRST
#: VERSION OF THIS FILE DID NOT SAY SO (`DEF-RAT-8074`).** `daterange` RAISES
#: `DataException: range lower bound must be less than or equal to range upper
#: bound` on a row whose end precedes its start — so the overlap query itself
#: died on the very row the report exists to name, and the operator got a
#: traceback instead of a list. Measured: the report crashed while `--apply` on
#: the same row worked, which is the report failing at its one job.
#: Malformed rows are reported by `MALFORMED_SQL` instead, which compares DATES
#: and builds no range.
_WELL_FORMED = "(%(col)s.effective_to IS NULL OR %(col)s.effective_from <= %(col)s.effective_to + 1)"

#: `rating/0047`'s own expression, and the `+ 1` is load-bearing (see above).
_WINDOW = "daterange(%(col)s.effective_from, COALESCE(%(col)s.effective_to + 1, 'infinity'::date))"

#: Every live, dated row of one schedule whose window overlaps another's. The
#: predicates are `0047`'s: dated, not superseded.
OVERLAP_SQL = f"""
SELECT v.tenant_id, v.tariff_id, tf.name AS tariff_name, v.id,
       v.effective_from, v.effective_to
  FROM tariff_versions v
  JOIN tariffs tf ON tf.id = v.tariff_id
 WHERE v.tenant_id = %s
   AND v.effective_from IS NOT NULL
   AND v.superseded_by_version_id IS NULL
   AND {_WELL_FORMED % {"col": "v"}}
   AND EXISTS (
         SELECT 1 FROM tariff_versions w
          WHERE w.tenant_id = v.tenant_id
            AND w.tariff_id = v.tariff_id
            AND w.id <> v.id
            AND w.effective_from IS NOT NULL
            AND w.superseded_by_version_id IS NULL
            AND {_WELL_FORMED % {"col": "w"}}
            AND {_WINDOW % {"col": "w"}} && {_WINDOW % {"col": "v"}}
       )
 ORDER BY v.tenant_id, v.tariff_id, v.effective_from, v.created_at
"""

#: One row's live siblings, for the "does this date actually clear it" question.
SIBLINGS_SQL = """
SELECT id, effective_from, effective_to
  FROM tariff_versions
 WHERE tenant_id = %s AND tariff_id = %s AND id <> %s
   AND effective_from IS NOT NULL AND superseded_by_version_id IS NULL
 ORDER BY effective_from
"""

#: ISSUED bills priced on one version, and the latest period they cover. The
#: seam (`seams.tariff_version_issued_bills`) answers the COUNT and cannot
#: answer the DATE, and the date is what decides the refusal, so this reads the
#: two billing tables directly — a READ, which is what
#: `10-scripts/rat_schedule_overlap_census.py --reprice-check` already does
#: across the same join. Cross-module WRITES are what B2 §2 forbids.
ISSUED_SQL = """
SELECT count(*), max(i.period_end)
  FROM invoice_lines l
  JOIN invoices i ON i.id = l.invoice_id
 WHERE l.tariff_version_id = %s
   AND l.tenant_id = %s
   AND i.status NOT IN ('draft', 'void')
"""

#: Rows `0047` cannot even build a range from. The predicate is `0047`'s own
#: (`effective_from > effective_to + 1`), NOT the looser `effective_to <
#: effective_from`: an end exactly one day before the start yields an EMPTY
#: range, which `daterange` accepts and which overlaps nothing.
MALFORMED_SQL = """
SELECT v.tenant_id, v.tariff_id, tf.name AS tariff_name, v.id,
       v.effective_from, v.effective_to
  FROM tariff_versions v
  JOIN tariffs tf ON tf.id = v.tariff_id
 WHERE v.tenant_id = %s
   AND v.effective_from IS NOT NULL
   AND v.effective_to IS NOT NULL
   AND v.superseded_by_version_id IS NULL
   AND v.effective_from > v.effective_to + 1
 ORDER BY v.tariff_id, v.effective_from
"""

ROW_SQL = """
SELECT tenant_id, tariff_id, effective_from, effective_to, superseded_by_version_id
  FROM tariff_versions WHERE id = %s AND tenant_id = %s
"""

#: The tenants to walk. `tenants` carries no RLS (checked: `relrowsecurity` and
#: `relforcerowsecurity` are both false), which is why `rating/0046` can read it
#: the same way before it sets any context.
TENANTS_SQL = "SELECT id FROM tenants ORDER BY id"

#: CLAUDE.md hard rule 1's sentinel, the same one `rating/0046` leaves behind.
NO_TENANT = "00000000-0000-0000-0000-000000000000"


#: The inclusive→exclusive conversion, in one place. `effective_to` is the LAST
#: DAY a version prices, so the half-open upper bound is one day later.
_ONE_DAY = timedelta(days=1)


def _upper(effective_to: date | None) -> date:
    """The EXCLUSIVE upper bound of an INCLUSIVE `effective_to`."""
    return date.max if effective_to is None else effective_to + _ONE_DAY


def _overlaps(a_lo: date, a_hi: date, b_lo: date, b_hi: date) -> bool:
    return a_lo < b_hi and b_lo < a_hi


def _fetch_all(sql: str, params: tuple = ()) -> list[tuple]:
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return list(cursor.fetchall())


def _enter_tenant(tenant_id) -> None:
    """CLAUDE.md hard rule 1, and here it is also the difference between seeing
    the rows and being told there are none.

    ⚠ **WITHOUT THIS THE WHOLE COMMAND REPORTS A CLEAN ESTATE OVER A LIVE
    OVERLAP (`DEF-RAT-8073`).** `tariff_versions` carries
    `tariff_versions_tenant_isolation`, `tenant_id = NULLIF(current_setting(
    'app.tenant_id', true), '')::uuid`, with RLS **ENABLED AND FORCED** — forced
    means it applies to the table owner too, so there is no role a deployment
    actually uses that is exempt. With the setting unset the predicate is NULL
    and **every row is invisible**. Measured on PostgreSQL 16.13 against the
    reported estate, as a `NOSUPERUSER NOBYPASSRLS` role: `select count(*) from
    tariff_versions` returns **0** with the setting unset and **4** with it set,
    and the first version of this command printed *"No overlapping
    rate-schedule window on this database"* over the very pair `rating/0046`
    was refusing to migrate past.
    ⚠ **IT WAS PROVED ON A SUPERUSER, WHICH IS WHY IT SHIPPED.** The proof ran
    as `postgres` (`rolsuper=t`, `rolbypassrls=t`), where policies are skipped
    — and Django's own system check SAID SO on every run of it: *"RLS IS NOT
    ENFORCED on this connection … every tenant policy is skipped."* That notice
    was read and passed over. A guard proved in a world where the guard cannot
    apply is hard-won law 7's *structurally incapable of failing*, one layer
    below the code.
    ⚠ And the reads name their tenant in SQL as well, so a `rolbypassrls` role —
    where RLS would NOT scope them — does not silently fold every tenant's rows
    into one report. Two mechanisms, because they fail in opposite directions.
    """
    if connection.vendor != "postgresql":
        # SQLite has no RLS and no `set_config` — skipped honestly, and the same
        # reads run. `rating/0046`'s own `_enter_tenant` says this in the same
        # words for the same reason.
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _leave_tenant() -> None:
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NO_TENANT])


def _tenant_ids() -> list:
    return [row[0] for row in _fetch_all(TENANTS_SQL)]


class Command(BaseCommand):
    help = (
        "Report overlapping rate-schedule windows, or write ONE end date a person has "
        "decided on. It never chooses a date (DEF-RAT-8070)."
    )

    def add_arguments(self, parser) -> None:
        # ⚠ `--version-id` AND NOT `--version`: Django's own `BaseCommand` already
        # owns `--version` (it prints the Django version), and adding it here
        # raises `argparse.ArgumentError` at PARSER CONSTRUCTION — so the command
        # cannot even be listed, let alone run. Do not rename it back.
        parser.add_argument(
            "--version-id",
            dest="version_id",
            help="the tariff_versions row whose effective_to a person has decided to move",
        )
        parser.add_argument(
            "--end-on",
            dest="end_on",
            help=(
                "the new INCLUSIVE last day of that version, YYYY-MM-DD — the LAST DAY "
                "IT PRICES. Required with --version-id; never defaulted or computed."
            ),
        )
        parser.add_argument(
            "--clear-end",
            action="store_true",
            dest="clear_end",
            help=(
                "instead of --end-on: the version has NO end date — it runs until further "
                "notice. Use it when the row is the newest version of its schedule, which "
                "is the ordinary case for a window that was typed backwards."
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="write it. Without this the command reports what it WOULD write and stops.",
        )

    # ── REPORT ────────────────────────────────────────────────────────────
    def handle(self, *args, **options) -> None:
        if options.get("end_on") and options.get("clear_end"):
            raise CommandError(
                "--end-on and --clear-end say two different things about the same row. "
                "Pass one."
            )
        if options.get("clear_end") and not options.get("version_id"):
            raise CommandError("--clear-end needs the --version-id it belongs to.")
        if options.get("version_id") and not (options.get("end_on") or options.get("clear_end")):
            raise CommandError(
                "--end-on is required with --version-id (or --clear-end, if the version has "
                "no end date at all). This command does not work out which "
                "date you meant: two live windows that touch disagree about one day, and "
                "which of the two rows is wrong is a decision about which price you filed "
                "(BR-RAT-007). Run with no arguments to see both readings."
            )
        if options.get("end_on") and not options.get("version_id"):
            raise CommandError("--end-on needs the --version-id it belongs to.")
        if options.get("version_id"):
            self._resolve(
                options["version_id"],
                options["end_on"],
                clear_end=options["clear_end"],
                apply=options["apply"],
            )
            return
        self._report()

    def _report(self) -> None:
        tenants = _tenant_ids()
        rows: list[tuple] = []
        broken: list[tuple] = []
        try:
            for tenant_id in tenants:
                _enter_tenant(tenant_id)
                rows.extend(_fetch_all(OVERLAP_SQL, (str(tenant_id),)))
                broken.extend(_fetch_all(MALFORMED_SQL, (str(tenant_id),)))
        finally:
            _leave_tenant()
        if broken:
            # ⚠ FIRST, because `0047` cannot be created AT ALL while one of these
            # exists — it is not a worse overlap, it is a different fault
            # (`DEF-RAT-8074`). An overlap makes the constraint refuse the rows;
            # a backwards window makes `daterange` refuse to be built.
            self.stdout.write(
                f"{len(broken)} version(s) have a window that ENDS BEFORE IT STARTS. "
                "`rating/0047` cannot be created while any of these exists, whatever the "
                "overlaps say:\n"
            )
            for tenant_id, tariff_id, tariff_name, version_id, lo, hi in broken:
                _enter_tenant(tenant_id)
                state, issued, latest = self._issued(version_id, tenant_id)
                _leave_tenant()
                bills = (
                    f"{issued} issued bill(s), latest period ends {latest}"
                    if state == "counted" and issued
                    else "no issued bill priced on it"
                    if state == "counted"
                    else "\u26a0 COULD NOT ASK BILLING"
                    if state == "unanswerable"
                    else "no invoice exists on this database yet"
                )
                self.stdout.write(
                    f"  tenant {tenant_id} · schedule {tariff_name} ({tariff_id})\n"
                    f"    {lo} → {hi}   {version_id}  ·  {bills}\n"
                    f"    ── give it the end date it should have had (on or after {lo}, "
                    f"and it must not run into the next version):\n"
                    f"       manage.py rat_resolve_schedule_overlap --version-id {version_id} "
                    f"--end-on <YYYY-MM-DD> --apply"
                )
            self.stdout.write("")
        if not rows and not broken:
            self.stdout.write(
                f"No overlapping rate-schedule window across {len(tenants)} tenant(s).\n"
                "Each one was read with `app.tenant_id` set to it, which is what makes "
                "this a real zero rather than an RLS-shaped one (DEF-RAT-8073)."
            )
            return
        by_schedule: dict[tuple, list[tuple]] = {}
        for row in rows:
            by_schedule.setdefault((row[0], row[1], row[2]), []).append(row)

        self.stdout.write(
            f"{len(by_schedule)} rate schedule(s) hold windows that are in force on one "
            f"date. `rating/0047` will refuse ADD CONSTRAINT until every one is resolved.\n"
        )
        for (tenant_id, tariff_id, tariff_name), versions in by_schedule.items():
            self.stdout.write(f"\ntenant {tenant_id} · schedule {tariff_name} ({tariff_id})")
            # ⚠ **THE TENANT GOES BACK ON BEFORE THE BILL COUNT, AND THE FIRST FIX
            # FOR `DEF-RAT-8073` FORGOT IT.** `invoices`, `invoice_lines` AND
            # `audit_log` all carry RLS enabled and FORCED, so reading the issued
            # count with the setting cleared answers **0 bills** — on the one
            # question that decides whether a window may be moved at all (hard
            # rule 4 with `BR-RAT-007`). Scoping the overlap read and leaving this
            # one unscoped would have been the same defect surviving its own fix,
            # in the more dangerous direction: an overlap correctly listed beside
            # *"no issued bill priced on it"* about a version that had been billed.
            _enter_tenant(tenant_id)
            for _t, _s, _n, version_id, lo, hi in versions:
                state, issued, latest = self._issued(version_id, _t)
                if state == "unanswerable":
                    billed = "  ·  ⚠ COULD NOT ASK BILLING — this is not 'no bills'"
                elif state == "no-billing-tables":
                    billed = "  ·  no invoice exists on this database yet"
                elif issued:
                    billed = f"  ·  {issued} issued bill(s), latest period ends {latest}"
                else:
                    billed = "  ·  no issued bill priced on it"
                self.stdout.write(f"    {lo} → {hi or '(open)'}   {version_id}{billed}")
            _leave_tenant()
            self._decisions(versions)

    def _decisions(self, versions: list[tuple]) -> None:
        """Both readings of each touching pair, and the command for each."""
        for i, earlier in enumerate(versions):
            for later in versions[i + 1 :]:
                e_lo, e_hi = earlier[4], earlier[5]
                l_lo = later[4]
                if e_hi is None or not _overlaps(e_lo, _upper(e_hi), l_lo, _upper(later[5])):
                    continue
                days = (min(_upper(e_hi), _upper(later[5])) - max(e_lo, l_lo)).days
                self.stdout.write(
                    f"    ── {days} day(s) are priced by both rows, from {max(e_lo, l_lo)}. "
                    "One of these two dates was written wrongly and only you know which:"
                )
                self.stdout.write(
                    f"       (a) the earlier row's end is one window too long — it should "
                    f"stop the day before the next one starts:\n"
                    f"           manage.py rat_resolve_schedule_overlap --version-id {earlier[3]} "
                    f"--end-on {l_lo - _ONE_DAY} --apply"
                )
                self.stdout.write(
                    f"       (b) the earlier row is right and the LATER row starts too "
                    f"early. This command cannot move a start date; file the later row's "
                    f"correct window as a new version, or say so and it will be built."
                )

    # ── WRITE ONE DECISION ────────────────────────────────────────────────
    def _resolve(
        self, version_id: str, end_on: str | None, *, clear_end: bool = False, apply: bool
    ) -> None:
        try:
            target = uuid.UUID(str(version_id))
        except (TypeError, ValueError) as exc:
            raise CommandError(f"--version-id {version_id!r} is not a uuid") from exc
        # ⚠ **`--clear-end` EXISTS BECAUSE THE ALTERNATIVE WAS TO MAKE THE OPERATOR
        # INVENT A DATE.** A window typed backwards is usually the NEWEST version of
        # its schedule — that is how it reaches a deploy without overlapping
        # anything and without being noticed — and the newest version's honest end
        # is NO end: it runs until further notice, which is what a NULL
        # `effective_to` means everywhere in this codebase. With only `--end-on`,
        # fixing such a row meant typing some far-future date that nobody had
        # decided, on a column that decides which version prices a service date.
        # Inventing a figure on a money path is the thing this whole chain refuses
        # to do; forcing the operator to do it is the same fault in their hand.
        new_end = None
        if not clear_end:
            try:
                new_end = datetime.strptime(end_on, "%Y-%m-%d").date()
            except ValueError as exc:
                raise CommandError(f"--end-on {end_on!r} is not a date (YYYY-MM-DD)") from exc

        # ⚠ **THE ROW CANNOT BE READ UNTIL ITS TENANT IS SET, AND ITS TENANT IS
        # ON THE ROW** — so the tenants are walked until one of them can see it
        # (`DEF-RAT-8073`). A single unscoped read returned nothing at all under
        # RLS FORCE and this command answered `no tariff_versions row <id>`
        # about a row that was sitting right there in `0046`'s refusal.
        tenants = _tenant_ids()
        found: list[tuple] = []
        for candidate in tenants:
            _enter_tenant(candidate)
            found = _fetch_all(ROW_SQL, (str(target), str(candidate)))
            if found:
                break
        if not found:
            _leave_tenant()
            raise CommandError(
                f"no tariff_versions row {target} in any of {len(tenants)} tenant(s). "
                "Each was searched with `app.tenant_id` set to it, so this is the row "
                "being absent rather than RLS hiding it."
            )
        tenant_id, tariff_id, old_from, old_to, superseded_by = found[0]
        # Every read below runs with this row's tenant set, which the walk above
        # has already left in place.

        if superseded_by is not None:
            raise CommandError(
                f"version {target} is SUPERSEDED. A corrected row's window is settled at "
                "the moment it is corrected and is never moved (BR-RAT-1044, and "
                "`rating/0046` in its own words); `rating/0047`'s predicate excludes it, "
                "so moving it clears no overlap and rewrites a filing history."
            )
        if old_from is None:
            raise CommandError(
                f"version {target} is a DRAFT — a NULL `effective_from` IS the draft "
                "(BR-RAT-031). It has no window, it has never priced anything, and "
                "`rating/0046` does not look at it."
            )
        if new_end is not None and new_end < old_from:
            raise CommandError(
                f"--end-on {new_end} is before this version's start {old_from}. That is "
                "the inverted window `_validate_version_fields` refuses by name as "
                "`window_inverted`."
            )

        siblings = _fetch_all(SIBLINGS_SQL, (str(tenant_id), str(tariff_id), str(target)))
        overlapping_now = [
            s
            for s in siblings
            if _overlaps(old_from, _upper(old_to), s[1], _upper(s[2]))
        ]
        # ⚠ **A BACKWARDS WINDOW OVERLAPS NOTHING AND IS STILL THIS COMMAND'S JOB
        # (`DEF-RAT-8074`).** `_overlap` on `[2026-09-01 → 2026-08-01]` compares a
        # backwards interval and answers False against everything, so the guard
        # below refused the one row `0047` could not build a range from — the
        # command declined to fix the very thing it was being run for.
        inverted = old_to is not None and old_from > old_to + _ONE_DAY
        if not overlapping_now and not inverted:
            raise CommandError(
                f"version {target} does not overlap any live version of its schedule, so "
                "there is nothing here for this command to resolve. It is the overlap "
                "door, not a general window editor: changing an in-force window for any "
                "other reason is a new version (BR-RAT-037)."
            )
        # `_upper(None)` is `date.max`, so a cleared end is compared as the OPEN
        # window it is — and a row that would then run into a later version is
        # refused here rather than at the next `migrate`.
        still_overlapping = [
            s for s in siblings if _overlaps(old_from, _upper(new_end), s[1], _upper(s[2]))
        ]
        if still_overlapping:
            rows = ", ".join(f"{s[0]} [{s[1]} → {s[2] or 'open'}]" for s in still_overlapping)
            asked = f"--end-on {new_end}" if new_end is not None else "--clear-end"
            raise CommandError(
                f"{asked} would leave version {target} still in force on the "
                f"same date as {rows}. Nothing was written: a repair that does not repair "
                "is worse than a refusal, because the next `migrate` is where you would "
                "have found out."
            )

        state, issued, latest_period = self._issued(target, tenant_id)
        if state == "unanswerable":
            raise CommandError(
                f"could not find out whether any issued bill was priced on version "
                f"{target}: the billing tables are present and the question could not be "
                "answered. That is an UNKNOWN and not a zero (DEF-079), and moving a "
                "price boundary blind is the one thing this command must not do. Fix the "
                "read, or resolve this row once billing can answer."
            )
        # ⚠ A CLEARED END CANNOT DROP A BILLED DATE — it only ever EXTENDS the
        # window — so hard rule 4's refusal has nothing to bite on and is skipped
        # rather than compared against a `None`.
        if (
            new_end is not None
            and issued
            and latest_period is not None
            and latest_period > new_end
        ):
            raise CommandError(
                f"{issued} issued bill(s) were priced on version {target}, and the latest "
                f"covers a period ending {latest_period} — after the {new_end} you asked "
                "for. The bills themselves are immutable and keep their stamped version "
                "(hard rule 4), but re-deriving that period would then resolve to a "
                "different version, which BR-RAT-007 says decides money. Nobody gets to "
                "choose that here: if the end date really is wrong, the bills priced past "
                "it are a correction for a person to rule on."
            )

        # ⚠ **HARD RULE 7 IS CHECKED BEFORE THE WRITE, NOT DISCOVERED DURING IT.**
        # Every money action writes `audit_log`, and `audit.write_row` raises if
        # it cannot — so the UPDATE and the trail either both happen or neither
        # does, which the `atomic()` below guarantees. What that does NOT give
        # is an answerable message: this command's home is a deploy stopped at
        # `rating/0046`, where the `audit` app's own migrations have very often
        # not run yet, and the operator's reward for doing everything right was
        # `ProgrammingError: relation "audit_log" does not exist` out of the
        # middle of a traceback. Measured on PostgreSQL 16: nothing was written
        # and nothing said what to do. `0046`'s docstring already states the
        # principle this repairs — *"a deploy that must stop must stop with an
        # answerable question"* — and that applies to the repair as much as to
        # the refusal.
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('audit_log')")
            if cursor.fetchone()[0] is None:
                raise CommandError(
                    "`audit_log` does not exist on this database yet, so this change "
                    "cannot be recorded — and hard rule 7 says every money action writes "
                    "the trail, so it is not made without it. Nothing was written. This "
                    "is the ordinary state of a deploy stopped at `rating/0046`: create "
                    "the trail first, then resolve, then finish the deploy.\n"
                    "    python manage.py migrate audit\n"
                    "    python manage.py rat_resolve_schedule_overlap "
                    f"--version-id {target} --end-on {new_end} --apply"
                )

        if not apply:
            self.stdout.write(
                f"WOULD WRITE  version {target}\n"
                f"  window   {old_from} → {old_to or '(open)'}\n"
                f"  becomes  {old_from} → {new_end or '(open — until further notice)'}\n"
                f"  clears   {len(overlapping_now)} overlap(s) on this schedule"
                f"{' AND the backwards window that stops 0047 being created' if inverted else ''}\n"
                f"  bills    {issued} issued, priced on this version"
                f"{' (no invoice exists on this database yet)' if state == 'no-billing-tables' else ''}\n"
                "Nothing was written. Re-run with --apply."
            )
            return

        # Hard rule 1: never touch a tenant table without `app.tenant_id` set.
        # Hard rule 7: the same transaction writes the trail, or neither happens.
        with tenant_context(tenant_id):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    # CR-157-BRC10 · DEF-RAT-8750 — the schedule row FIRST, the
                    # same order every save path in `rating.services` takes
                    # (`_lock_schedule`), so this repair and a clerk's save on
                    # the same schedule queue behind each other instead of
                    # deadlocking or both believing they saw the last word.
                    cursor.execute(
                        "SELECT t.id FROM tariffs t WHERE t.tenant_id = %s AND t.id = "
                        "(SELECT v.tariff_id FROM tariff_versions v WHERE v.id = %s) "
                        "FOR UPDATE",
                        (str(tenant_id), str(target)),
                    )
                    cursor.execute(
                        "UPDATE tariff_versions SET effective_to = %s, updated_at = now() "
                        "WHERE id = %s AND tenant_id = %s",
                        (new_end, str(target), str(tenant_id)),
                    )
                    if cursor.rowcount != 1:
                        raise CommandError(
                            f"expected to update exactly 1 row, updated {cursor.rowcount}. "
                            "Rolled back."
                        )
                audit.write_row(
                    action="tariff.version_window_resolved",
                    entity_type="tariff_version",
                    entity_id=target,
                    automation=audit.AutomationActor(
                        kind="job",
                        name="Rate schedule overlap resolution",
                        version="DEF-RAT-8070",
                    ),
                    before={"effective_from": old_from, "effective_to": old_to},
                    after={"effective_from": old_from, "effective_to": new_end},
                )
        self.stdout.write(
            f"WROTE  version {target}: {old_from} → "
            f"{new_end or '(open)'} "
            f"(was {old_from} → {old_to or '(open)'}).\n"
            "Re-run this command with no arguments to see what is left, then migrate."
        )

    def _issued(self, version_id, tenant_id) -> tuple[str, int | None, date | None]:
        """ISSUED bills priced on one version: `(state, count, latest period end)`.

        ⚠ **THREE STATES, NOT TWO, AND THE FIRST DRAFT OF THIS COMMAND HAD TWO
        — WHICH MADE IT PRINT A SENTENCE THAT WAS NOT TRUE.** It returned
        `(None, None)` when the query failed and the caller rendered anything
        falsy as *"no issued bill priced on it"*. That is exactly the
        distinction `DEF-079` cost and that `seams.tariff_version_issued_bills`
        exists to preserve: **`None` means BILLING COULD NOT ANSWER, never "no
        bills"** — and *"nobody has been billed"* is the one sentence an
        operator must not be told wrongly before they move a price boundary.
        It was found by running the command, not by reading it: this command's
        own home is a STOPPED DEPLOY, where `rating/0046` raises before
        billing's tables are created, so the unanswerable case is not the rare
        one here — **it is the default one.**

        The two unanswerable cases are then separated, because they are not the
        same fact:
          · **no billing tables on this database** — `invoices` does not exist,
            so no invoice has ever been issued here. That is a definitive ZERO,
            not an unknown, and it is the ordinary state of a deploy stopped at
            `rating/0046`.
          · **the tables exist and the question could not be answered** — a
            genuine unknown, and `--apply` refuses on it rather than moving a
            boundary blind.

        ⚠ The savepoint is hard-won law 14: on PostgreSQL one failed statement
        aborts the whole transaction, so without a nested `atomic()` a failure
        here would poison the UPDATE and the audit write that follow. The suite
        runs SQLite, which has no aborted-transaction state, so the version
        without it passes every test and loses the repair on a real server.
        """
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('invoices'), to_regclass('invoice_lines')")
            invoices, lines = cursor.fetchone()
        if invoices is None or lines is None:
            return "no-billing-tables", 0, None
        try:
            with transaction.atomic():
                rows = _fetch_all(ISSUED_SQL, (str(version_id), str(tenant_id)))
        except Exception:  # pragma: no cover — reported, never flattened to 0
            return "unanswerable", None, None
        count, latest = rows[0]
        return "counted", int(count or 0), latest
