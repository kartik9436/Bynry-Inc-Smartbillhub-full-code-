#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-8000 — B2 §2 signs an `EXCLUDE USING gist` no-overlap
#          constraint on `tariff_versions`; migration `rating/0001` never
#          materialised it (`btree_gist` was not installed) and `rating/0004`
#          reported that and left it "for the human review of this row", which
#          never happened. A schedule can therefore hold several versions in
#          force on one date, and billing then either refuses
#          (`AmbiguousSchedule`) or silently picks.
# Rules:   B2 §2 (the signed constraint) · BR-RAT-007 (a period prices on the
#          version in force AT THE SERVICE DATE) · BR-RAT-031 (a NULL
#          `effective_from` IS the draft) · BR-RAT-104 / BR-RAT-1016 verb 2 (a
#          CORRECTION restates the SAME window and the corrected row carries
#          `superseded_by_version_id`) · CLAUDE.md hard rule 1 (tenant
#          scoping) · hard-won law 7's fifth shape (print what you SKIPPED
#          beside what you counted — a blind spot with no number beside it is
#          indistinguishable from an empty one).
# ───────────────────────────────────────────────────────
"""COUNT THE OVERLAPPING RATE-SCHEDULE WINDOWS BEFORE ANYTHING TOUCHES A ROW.

READ-ONLY. It opens a read-only transaction and writes nothing, ever — this is
the step that runs BEFORE the repair migration, and its whole job is to say how
much there is to repair and of which of four KINDS.

    python3 10-scripts/rat_schedule_overlap_census.py                 # $DATABASE_URL
    python3 10-scripts/rat_schedule_overlap_census.py --dsn postgres://…
    python3 10-scripts/rat_schedule_overlap_census.py --plant-proof   # see below
    python3 10-scripts/rat_schedule_overlap_census.py --reprice-check  # see below
    python3 10-scripts/rat_schedule_overlap_census.py --corrected-open # see below
    python3 10-scripts/rat_schedule_overlap_census.py --discounts      # DEF-RAT-8050

⚠ **IT COVERS TWO TABLES AND THE NAME SAYS ONE.** `--discounts` runs the same
census over `discount_versions` (`DEF-RAT-8050`), and it is HERE rather than in
a second script because two census tools would be two definitions of the word
"overlap" — and the whole reason this one exists is that B2's definition and
the billing code's disagreed by one day. The discount half differs in three
stated ways; they are written out beside `discount_census` rather than left to
be inferred. The FILE is not renamed because every citation of it in the
decision log, the review ledger and `rating/0046` would move at once.

── WHAT "OVERLAP" MEANS HERE, EXACTLY, AND WHY IT IS NOT B2's EXPRESSION ─────
`selectors.in_force_version` is the live bill run's read and it is INCLUSIVE at
both ends:

    effective_from <= d AND (effective_to IS NULL OR effective_to >= d)

so two rows are in force on one date when

    daterange(a.effective_from, coalesce(a.effective_to + 1, 'infinity'))
      && daterange(b.effective_from, coalesce(b.effective_to + 1, 'infinity'))

⚠ **THE `+ 1` IS LOAD-BEARING AND B2 §2's SIGNED EXPRESSION DOES NOT HAVE IT.**
B2 writes `daterange(effective_from, coalesce(effective_to,'infinity'))`, and
`daterange` is half-open `[lower, upper)`. Against an INCLUSIVE `effective_to`
that is off by one day in the permissive direction: a version ending
`2026-03-31` and a version starting `2026-03-31` do NOT overlap by B2's
expression, and they ARE both in force on 2026-03-31 for `in_force_version`,
which is a one-day coin toss on a money path. This census counts what the
BILLING CODE would see, because that is the thing that is going wrong.

── THE FOUR KINDS, WHICH ARE NOT THE SAME AND ARE NOT REPAIRED THE SAME ──────
  **CORRECTION**  — some row in the group carries `superseded_by_version_id`.
                    `BR-RAT-104` / `BR-RAT-1016` verb 2: a correction restates
                    the SAME window on purpose, and the live run already
                    excludes the corrected row. NOTHING TO REPAIR.
  **SUCCESSION**  — every row is non-superseded, every `effective_from` is
                    DISTINCT, and the older row's `effective_to` **IS NULL**.
                    Somebody opened a new window without closing the old one.
                    Repairable mechanically, and `rating/0046` DOES repair it:
                    oldest first, each `effective_to` becomes the next row's
                    `effective_from` minus one day, the newest stays open.
  **STATED-END**  — every row is non-superseded, every `effective_from` is
                    DISTINCT, and the older row's `effective_to` **IS STATED**
                    and runs into the next row's start.
                    ⚠ **REFUSED, AND THIS KIND EXISTS BECAUSE ITS ABSENCE SENT
                    AN OPERATOR ROUND A LOOP WITH NO EXIT (`DEF-RAT-8070`).**
                    It was counted as `SUCCESSION` — three lines up, this file
                    calls that *"repairable mechanically"* — while
                    `rating/0046` refuses it by name: *"ONLY A NULL END IS
                    FILLED. AN END DATE THAT ALREADY EXISTS IS NEVER MOVED."*
                    So the migration stopped a deploy and said *re-run the
                    census and migrate again*; the census said the overlap was
                    mechanically repairable; and the next migrate printed the
                    identical refusal. **Neither tool was lying and the two
                    could not both be acted on** — which is hard-won law 7's
                    *looking at the wrong thing*, across two files rather than
                    inside one. Both now name the same shape by the same word.
                    **A person decides, and `manage.py
                    rat_resolve_schedule_overlap` is the only thing in this repo
                    that can carry out the decision** — no endpoint moves a
                    stated end, and a correction COPIES the window, so neither
                    clears it. It lives in `06-backend/` rather than beside this
                    file because `10-scripts/` is not in the deployed image
                    (`DEF-RAT-8071`), so the operator of a stopped deploy can
                    reach it and cannot reach this.
  **SAME-DATE**   — two non-superseded rows share one `effective_from`.
                    ⚠ **REFUSED.** `selectors.in_force_version`'s own comment:
                    *"the order-by decides which one prices — by
                    `effective_from`, which is IDENTICAL on both … That is not
                    a tie-break, it is a coin toss on a money path."* A person
                    decides which one is right; no migration may pick.

── `--reprice-check` · DID CLOSING A WINDOW MOVE AN ISSUED BILL? ─────────────
Hard rule 4: an issued invoice is immutable, and BR-RAT-007/017 say a past
period is reproduced from the version in force AT ITS SERVICE DATE. **Closing
an open window changes what would be chosen for a past date** — a version that
used to run to infinity now ends, and every date after that end resolves to
the next version instead. So the repair CAN move an already-issued bill's
basis, and nothing else in this repo would notice.

`--reprice-check` reads every `invoice_lines` row that carries the `DEF-276`
stamp (`tariff_version_id`) on an ISSUED invoice, re-resolves the version for
that invoice's service-period end date exactly as `selectors.in_force_version`
does, and prints every line where the answer is no longer the version the bill
was billed on. **Run it BEFORE and AFTER the repair and compare the two
numbers.** A line that moves is not something a migration may fix — that needs
a person, and the run says so.

⚠ It prints the number of stamped lines it COULD check beside the number of
issued lines that carry NO stamp, because a bill with no stamp cannot be
checked at all and an estate of them would otherwise report a reassuring zero
(law 7's fifth shape).

── WHAT WOULD MAKE THIS PASS WRONGLY, ANSWERED RATHER THAN ASSUMED ───────────
  * **An empty database reads exactly like a clean one.** So the footer prints
    the tenants, schedules and versions it COUNTED and the drafts and
    single-version schedules it SKIPPED, with a number beside each, and says in
    one sentence whether it found anything at all. A run that finds zero
    overlaps on demo data proves the counter runs; it proves nothing whatever
    about production, and the footer says so in those words.
  * **A counter that cannot find an overlap would also print zero.**
    `--plant-proof` plants a synthetic three-row overlap of each kind in a
    SAVEPOINT, counts, prints, and ROLLS BACK — so the zero above is a measured
    zero rather than an untested code path. It writes nothing that survives.
  * **RLS.** The census reads ACROSS tenants deliberately (it is an operator
    tool, not a request path), so it must be run as a role that can see every
    row; it prints `rolsuper`/`rolbypassrls` and the row total beside every
    figure, because a census run under an unset `app.tenant_id` on a
    FORCE-protected table returns zero rows and looks identical to a clean
    estate. If it sees zero `tariff_versions` rows AT ALL it says so loudly
    rather than reporting "no overlaps".
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
from collections import defaultdict
from datetime import date, timedelta

try:
    import psycopg
except ModuleNotFoundError:  # pragma: no cover - environment statement, not logic
    print("psycopg (v3) is required: pip install 'psycopg[binary]'", file=sys.stderr)
    raise

CENSUS_SQL = """
SELECT v.tenant_id,
       t.name                AS tenant_name,
       v.tariff_id,
       tf.name               AS tariff_name,
       v.id,
       v.effective_from,
       v.effective_to,
       v.superseded_by_version_id
  FROM tariff_versions v
  JOIN tariffs tf ON tf.id = v.tariff_id
  LEFT JOIN tenants t ON t.id = v.tenant_id
 WHERE v.effective_from IS NOT NULL
 ORDER BY v.tenant_id, v.tariff_id, v.effective_from, v.created_at
"""


#: Every kind `_classify` can return, in the order the roll-call prints them.
#: ⚠ **DECLARED ONCE, AND THE ROLL-CALL READS IT RATHER THAN A SECOND LITERAL
#: LIST** (`DEF-RAT-8070`). The printed tally was its own hardcoded tuple, so a
#: kind added to the classifier would have been COUNTED and never SHOWN — a
#: number missing from a report reads exactly like a zero, which is hard-won
#: law 7's fifth shape. `_kinds_are_declared()` asserts the two agree.
KINDS = ("CORRECTION", "SUCCESSION", "STATED-END", "SUCCESSION+CORRECTION", "SAME-DATE")


def _upper(row_to: date | None) -> date:
    """The EXCLUSIVE upper bound of an inclusive `effective_to`."""
    return date.max if row_to is None else row_to + timedelta(days=1)


def _overlaps(a: tuple[date, date], b: tuple[date, date]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _groups(rows: list[dict]) -> list[list[dict]]:
    """Every maximal set of rows of ONE schedule that pairwise-chain by overlap.

    Chaining rather than pairwise-only: three rows where 1–2 and 2–3 overlap
    are ONE repair, not two, and the succession fix has to see all three at
    once to sort them.
    """
    out: list[list[dict]] = []
    current: list[dict] = []
    reach: date | None = None
    for row in sorted(rows, key=lambda r: (r["lo"], r["hi"])):
        if current and reach is not None and row["lo"] < reach:
            current.append(row)
            reach = max(reach, row["hi"])
            continue
        if len(current) > 1:
            out.append(current)
        current = [row]
        reach = row["hi"]
    if len(current) > 1:
        out.append(current)
    return out


def _classify(group: list[dict]) -> str:
    """The kind, which is the same question `rating/0046` asks of the same rows.

    ⚠ **`SUCCESSION` AND `STATED-END` ARE ONE CLASS TO B2's CONSTRAINT AND TWO
    CLASSES TO THE REPAIR, AND COLLAPSING THEM IS `DEF-RAT-8070`.** Both are
    live rows with distinct starts; they differ only in whether the older row's
    `effective_to` is NULL. `rating/0046` pass 1 fills a NULL end and **never
    moves a stated one** — *"somebody typed it, it is what a bill was
    reproduced against"* — so one kind is repaired by migrating and the other
    is refused by it. Reporting both as `SUCCESSION`, which this file's own
    header calls *"repairable mechanically"*, told an operator to migrate again
    and meet the identical refusal, for ever.

    ⚠ **IT IS THE OLDER ROW OF EACH OVERLAPPING PAIR THAT DECIDES, NOT THE
    OLDEST ROW OF THE GROUP.** A group of three can hold one NULL-ended
    overlap and one stated-ended one; `0046` repairs the first and refuses the
    second, so the group as a whole is refused and must say so. Any stated end
    running into a later start makes the whole group `STATED-END`.
    """
    live = [r for r in group if r["superseded_by_version_id"] is None]
    if len(live) < 2:
        return "CORRECTION"
    froms = [r["effective_from"] for r in live]
    if len(set(froms)) < len(froms):
        return "SAME-DATE"
    if any(r["superseded_by_version_id"] is not None for r in group):
        return "SUCCESSION+CORRECTION"
    ordered = sorted(live, key=lambda r: (r["effective_from"], r["hi"]))
    for i, earlier in enumerate(ordered):
        for later in ordered[i + 1 :]:
            if earlier["effective_to"] is not None and _overlaps(
                (earlier["lo"], earlier["hi"]), (later["lo"], later["hi"])
            ):
                return "STATED-END"
    return "SUCCESSION"


def _kinds_are_declared() -> None:
    """Every kind `_classify` can return is in `KINDS`, read off the code.

    ⚠ **THE CHECK IS AGAINST THE CLASSIFIER'S OWN SOURCE, NOT AGAINST A LIST
    SOMEBODY MAINTAINS BESIDE IT** — otherwise this is a second copy of the
    thing it is meant to keep honest, and hard-won law 5 already says what two
    copies do. It parses this module and collects the string literals returned
    from `_classify` and `_discount_classify`, so a kind minted in either and
    not added to `KINDS` fails here rather than being tallied invisibly.

    Proved RED by adding a `return "NEW-KIND"` to `_classify`: it names the
    kind and exits 2 before a single row is read.
    """
    import ast

    tree = ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
    returned: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in (
            "_classify",
            "_discount_classify",
        ):
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Return)
                and isinstance(inner.value, ast.Constant)
                and isinstance(inner.value.value, str)
            ):
                returned.add(inner.value.value)
    undeclared = sorted(returned - set(KINDS))
    if undeclared:
        print(
            f"\n⚠ KIND(S) {undeclared} CAN BE RETURNED AND ARE NOT IN `KINDS`, so they "
            "would be counted and never printed. A missing number reads as a zero.",
            file=sys.stderr,
        )
        sys.exit(2)


def census(conn, label: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM tariff_versions")
        total_versions = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM tariff_versions WHERE effective_from IS NULL")
        drafts = cur.fetchone()[0]
        cur.execute(CENSUS_SQL)
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    for row in rows:
        row["lo"] = row["effective_from"]
        row["hi"] = _upper(row["effective_to"])

    by_schedule: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        by_schedule[(row["tenant_id"], row["tariff_id"])].append(row)

    findings = []
    for (tenant_id, tariff_id), scheduled in sorted(by_schedule.items(), key=lambda kv: str(kv[0])):
        for group in _groups(scheduled):
            findings.append(
                {
                    "tenant_id": tenant_id,
                    "tenant_name": group[0]["tenant_name"],
                    "tariff_id": tariff_id,
                    "tariff_name": group[0]["tariff_name"],
                    "kind": _classify(group),
                    "rows": group,
                }
            )

    kinds = defaultdict(int)
    rows_in_overlap = 0
    superseded_rows = 0
    for finding in findings:
        kinds[finding["kind"]] += 1
        rows_in_overlap += len(finding["rows"])
        superseded_rows += sum(
            1 for r in finding["rows"] if r["superseded_by_version_id"] is not None
        )

    print(f"\n══ {label} ══")
    for finding in findings:
        print(
            f"  {finding['kind']:<22} tenant {finding['tenant_name'] or finding['tenant_id']} · "
            f"schedule {finding['tariff_name']} ({finding['tariff_id']}) · "
            f"{len(finding['rows'])} rows"
        )
        for row in finding["rows"]:
            mark = "superseded" if row["superseded_by_version_id"] else "live      "
            print(
                f"      {mark}  {row['effective_from']} → "
                f"{row['effective_to'] or '(open)'}   {row['id']}"
            )
    if not findings:
        print("  no overlapping window found")

    print("  ── counted ──")
    print(f"    tenants with at least one dated version : {len({r['tenant_id'] for r in rows})}")
    print(f"    schedules with at least one dated version: {len(by_schedule)}")
    print(f"    dated versions examined                  : {len(rows)}")
    print("  ── skipped, with a number beside each (law 7) ──")
    print(f"    draft versions (NULL effective_from)     : {drafts}")
    print(
        "    schedules with exactly one dated version : "
        f"{sum(1 for v in by_schedule.values() if len(v) == 1)}"
    )
    print(f"    rows in `tariff_versions` in total       : {total_versions}")
    print("  ── the answer ──")
    print(f"    overlapping GROUPS                       : {len(findings)}")
    for kind in KINDS:
        print(f"      {kind:<22}                 : {kinds[kind]}")
    print(f"    version rows inside an overlap           : {rows_in_overlap}")
    print(f"    of those, carrying superseded_by         : {superseded_rows}")
    print(
        f"    distinct tenants affected                : "
        f"{len({f['tenant_id'] for f in findings})}"
    )
    if total_versions == 0:
        print(
            "  ⚠ THIS DATABASE HOLDS NO `tariff_versions` ROWS AT ALL. The zero above is "
            "an EMPTY estate, not a clean one — and an unset `app.tenant_id` under RLS "
            "FORCE would look exactly the same. Nothing is proved about production."
        )
    elif not findings:
        print(
            "  ⚠ ZERO OVERLAPS ON THIS DATABASE. That proves the census RUNS; it proves "
            "NOTHING about production. Run the same command against the real database "
            "before believing the repair had nothing to do."
        )
    return {"findings": findings, "kinds": dict(kinds), "versions": len(rows)}


PLANT_SQL = """
SELECT v.id, v.tenant_id, v.tariff_id, tf.service_id, v.model, v.currency, v.percent_basis
  FROM tariff_versions v JOIN tariffs tf ON tf.id = v.tariff_id
 WHERE v.effective_from IS NOT NULL LIMIT 1
"""


def plant_proof(conn) -> None:
    """Plant one overlap of each kind in a SAVEPOINT, count, and ROLL BACK.

    Law 7: a counter that CANNOT find an overlap prints the same zero as a
    clean estate. This is the red proof, run in the harness that will run it.

    ⚠ **EACH KIND GETS ITS OWN SYNTHETIC SCHEDULE, AND THE FIRST DRAFT OF THIS
    FUNCTION DID NOT — WHICH IS WHY THE PROOF IS WORTH RUNNING.** Planted onto
    an EXISTING schedule, the fixture's own open-ended `2026-08-01 → (open)`
    row chained all six planted rows plus itself into ONE group of seven, and
    the classifier then reported a single `SAME-DATE` and missed the other two
    kinds. The chaining was right (an open window really does overlap 2099);
    the FIXTURE was wrong, and a proof that cannot separate its own cases
    cannot tell you the counter works.
    """
    with conn.cursor() as cur:
        cur.execute(PLANT_SQL)
        seed = cur.fetchone()
        if seed is None:
            print(
                "\n⚠ --plant-proof needs one existing dated version to copy a tenant and "
                "service from, and this database has none. The counter is UNPROVEN here."
            )
            return
        version_id, tenant_id, _tariff_id, service_id, model, currency, basis = seed
        cur.execute("SAVEPOINT plant")
        mk_tariff = (
            "INSERT INTO tariffs (id, tenant_id, service_id, name, is_sample, "
            "created_at, updated_at) VALUES (gen_random_uuid(), %s, %s, %s, false, "
            "now(), now()) RETURNING id"
        )
        mk_version = (
            "INSERT INTO tariff_versions (id, tenant_id, tariff_id, model, currency, "
            "percent_basis, notify_customers, publish_public, created_at, updated_at, "
            "effective_from, effective_to, superseded_by_version_id) VALUES "
            "(gen_random_uuid(), %s, %s, %s, %s, %s, false, false, now(), now(), %s, %s, %s) "
            "RETURNING id"
        )

        def tariff(name: str):
            cur.execute(mk_tariff, (tenant_id, service_id, name))
            return cur.fetchone()[0]

        def version(tid, lo, hi, superseded=None):
            cur.execute(mk_version, (tenant_id, tid, model, currency, basis, lo, hi, superseded))
            return cur.fetchone()[0]

        # SUCCESSION: two live rows, distinct starts, the older left open.
        succession = tariff("PLANTED · succession")
        version(succession, date(2099, 1, 1), None)
        version(succession, date(2099, 6, 1), None)
        # SAME-DATE: two live rows sharing one start — the coin toss.
        tie = tariff("PLANTED · same-date tie")
        version(tie, date(2098, 1, 1), date(2098, 12, 31))
        version(tie, date(2098, 1, 1), date(2098, 12, 31))
        # CORRECTION: a superseded row restated by a live one over one window.
        corrected_schedule = tariff("PLANTED · correction")
        old = version(corrected_schedule, date(2097, 1, 1), date(2097, 12, 31))
        version(corrected_schedule, date(2097, 1, 1), date(2097, 12, 31))
        cur.execute(
            "UPDATE tariff_versions SET superseded_by_version_id = %s WHERE id = %s",
            (version_id, old),
        )
        # ⚠ THE OFF-BY-ONE B2's SIGNED EXPRESSION MISSES: `effective_to` is
        # INCLUSIVE in `selectors.in_force_version`, so these two ARE both in
        # force on 2096-06-30 and B2's half-open `daterange(from, to)` says
        # they do not overlap.
        touching = tariff("PLANTED · inclusive-end touch")
        version(touching, date(2096, 1, 1), date(2096, 6, 30))
        version(touching, date(2096, 6, 30), None)

        result = census(conn, "PLANTED OVERLAPS (synthetic, rolled back)")
        with conn.cursor() as c2:
            c2.execute("ROLLBACK TO SAVEPOINT plant")
        kinds = result["kinds"]
        # ⚠ `STATED-END` IS HERE BECAUSE THE `touching` SCHEDULE BELOW HAS ALWAYS
        # BEEN ONE — `2096-01-01 → 2096-06-30` beside `2096-06-30 → (open)` is
        # the inclusive-end touch, and it was counted as `SUCCESSION` until
        # `DEF-RAT-8070`. Naming it here is what makes this the red proof for the
        # kind rather than a run that would pass either way.
        expected = {"SUCCESSION", "SAME-DATE", "CORRECTION", "STATED-END"}
        found = {k for k, n in kinds.items() if n}
        missing = expected - found
        planted_names = {
            f["tariff_name"] for f in result["findings"] if f["tariff_name"].startswith("PLANTED")
        }
        print(
            f"\n  plant-proof: expected kinds {sorted(expected)}; "
            f"found {sorted(found)}; MISSING {sorted(missing) or 'none'}"
        )
        print(f"  plant-proof: planted schedules seen: {sorted(planted_names)}")
        if missing or len(planted_names) != 4:
            print("  ⚠ THE COUNTER CANNOT FIND EVERY KIND IT CLAIMS TO COUNT.")
            sys.exit(1)
        print("  plant-proof: the counter finds a planted overlap. Everything was rolled back.")


REPRICE_SQL = """
SELECT l.id                AS line_id,
       l.tariff_version_id AS billed_on,
       l.tenant_id,
       v.tariff_id,
       i.period_end,
       i.invoice_no
  FROM invoice_lines l
  JOIN invoices i        ON i.id = l.invoice_id
  JOIN tariff_versions v ON v.id = l.tariff_version_id
 WHERE l.tariff_version_id IS NOT NULL
   AND i.status NOT IN ('draft', 'void')
"""

UNSTAMPED_SQL = """
SELECT count(*) FROM invoice_lines l JOIN invoices i ON i.id = l.invoice_id
 WHERE l.tariff_version_id IS NULL AND i.status NOT IN ('draft', 'void')
"""

RESOLVE_SQL = """
SELECT id FROM tariff_versions
 WHERE tenant_id = %s AND tariff_id = %s
   AND effective_from IS NOT NULL AND superseded_by_version_id IS NULL
   AND effective_from <= %s
   AND (effective_to IS NULL OR effective_to >= %s)
 ORDER BY effective_from DESC
 LIMIT 1
"""


def reprice_check(conn) -> None:
    """Hard rule 4 — has any ISSUED bill's basis moved?

    The resolution is `selectors.in_force_version` written in SQL, on purpose:
    reading it through the ORM would need a tenant context per row and would
    then be answering with whatever that selector does TODAY, which is the
    thing under test after a change to it. The two must agree and this is the
    place that would show they do not.
    """
    with conn.cursor() as cur:
        cur.execute(UNSTAMPED_SQL)
        unstamped = cur.fetchone()[0]
        cur.execute(REPRICE_SQL)
        cols = [c.name for c in cur.description]
        lines = [dict(zip(cols, r)) for r in cur.fetchall()]

        moved = []
        for line in lines:
            end = line["period_end"]
            cur.execute(
                RESOLVE_SQL, (line["tenant_id"], line["tariff_id"], end, end)
            )
            now = cur.fetchone()
            now_id = now[0] if now else None
            if str(now_id) != str(line["billed_on"]):
                moved.append((line, now_id))

    print("\n══ REPRICE CHECK (hard rule 4 — an issued bill's basis may not move) ══")
    for line, now_id in moved:
        print(
            f"  ⚠ invoice {line['invoice_no']} line {line['line_id']} was billed on "
            f"{line['billed_on']} and {line['period_end']} now resolves to {now_id}"
        )
    print(f"  issued lines CHECKED (they carry the DEF-276 stamp) : {len(lines)}")
    print(f"  issued lines NOT checkable (no stamp at all)        : {unstamped}")
    print(f"  issued lines whose basis MOVED                      : {len(moved)}")
    if moved:
        print(
            "  ⚠ STOP. An already-issued bill would now re-price on a different "
            "version. Hard rule 4 forbids a migration fixing this; a person must "
            "decide, per bill."
        )
    elif not lines:
        print(
            "  ⚠ NOTHING WAS CHECKED. No issued invoice line carries a version "
            "stamp on this database, so this zero says nothing at all."
        )


def plant_reprice_proof(conn) -> None:
    """Law 7 again: prove `--reprice-check` can FIND a moved bill.

    A zero from `--reprice-check` on a database with no issued invoices is the
    same zero it would print if the comparison were broken. So this plants ONE
    issued invoice line, stamped with a version whose window it then closes in
    the same SAVEPOINT, runs the check, and ROLLS BACK. Nothing survives.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT v.id, v.tenant_id, v.tariff_id, v.model, v.currency, v.percent_basis, "
            "(SELECT a.id FROM accounts a WHERE a.tenant_id = v.tenant_id LIMIT 1) "
            "FROM tariff_versions v WHERE v.effective_from IS NOT NULL LIMIT 1"
        )
        seed = cur.fetchone()
        if seed is None or seed[6] is None:
            print(
                "\n⚠ --plant-reprice needs one dated version and one account to build a "
                "synthetic issued bill from, and this database has none. "
                "**`--reprice-check` IS THEREFORE UNPROVEN HERE.**"
            )
            return
        old_version, tenant_id, tariff_id, model, currency, basis, account_id = seed
        cur.execute("SAVEPOINT reprice")
        # A LATER version, so closing the older one moves the answer.
        cur.execute(
            "INSERT INTO tariff_versions (id, tenant_id, tariff_id, model, currency, "
            "percent_basis, notify_customers, publish_public, created_at, updated_at, "
            "effective_from, effective_to) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, "
            "false, false, now(), now(), %s, NULL) RETURNING id",
            (tenant_id, tariff_id, model, currency, basis, date(2095, 1, 1)),
        )
        newer = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO invoices (id, tenant_id, account_id, bill_type, service_date, "
            "period_start, period_end, status, subtotal, tax_total, total, currency, "
            "payload_version, created_at, updated_at) VALUES (gen_random_uuid(), %s, %s, "
            "'cycle', %s, %s, %s, 'issued', 0, 0, 0, %s, 1, now(), now()) RETURNING id",
            (tenant_id, account_id, date(2095, 6, 30), date(2095, 6, 1),
             date(2095, 6, 30), currency),
        )
        invoice = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO invoice_lines (id, tenant_id, invoice_id, account_id, kind, "
            "description, amount, taxable, tariff_version_id, created_at, updated_at) "
            "VALUES (gen_random_uuid(), %s, %s, %s, 'usage', 'planted', 0, false, %s, "
            "now(), now())",
            (tenant_id, invoice, account_id, old_version),
        )
        print(
            "\n  plant-reprice: an ISSUED line stamped with the OLD version, over a "
            f"period ending 2095-06-30 that now resolves to {newer}"
        )
        reprice_check(conn)
        with conn.cursor() as c2:
            c2.execute("ROLLBACK TO SAVEPOINT reprice")
        print("  plant-reprice: rolled back — nothing planted survives.")


CORRECTED_OPEN_SQL = """
SELECT v.tenant_id,
       coalesce(t.name, '(unnamed tenant)')  AS tenant_name,
       count(*)                              AS corrected_open
  FROM tariff_versions v
  LEFT JOIN tenants t ON t.id = v.tenant_id
 WHERE v.superseded_by_version_id IS NOT NULL
   AND v.effective_from IS NOT NULL
   AND v.effective_to   IS NULL
 GROUP BY v.tenant_id, t.name
 ORDER BY count(*) DESC, v.tenant_id
"""


def corrected_open(conn) -> int:
    """`BR-RAT-1044` — **HOW MANY ROWS A BACKFILL WOULD HAVE TO TOUCH.**

    The PO ruled on 2026-09-29 that a corrected row records the day it stopped
    being used, and the change is **FORWARD-ONLY**: rows corrected before that
    date keep their open `effective_to`. Whether those are left, migrated, or
    made a change of their own is a SECOND ruling, and this number is what the
    PO needs before taking it — a handful is a migration, thousands is a
    project.

    ⚠ **IT COUNTS ONLY WHAT IT CAN SEE, AND PRINTS THE ROLE THAT SAW IT**
    (hard-won law 7's fifth shape). `tariff_versions` carries RLS FORCE, so a
    non-superuser without `BYPASSRLS` and without `app.tenant_id` set reads
    ZERO rows and this reports a clean estate truthfully and uselessly. The
    caller's role line is printed above every census for exactly this reason.
    **A zero here is only an answer if the role line says the reader could
    have seen a row.**

    ⚠ It is NOT the same question as the overlap census above. An overlap
    needs two rows whose windows meet; this is one column on one row, and a
    corrected row can carry an open end with no overlap at all — for instance
    when its correction was itself later closed by a rate change.
    """
    with conn.cursor() as cur:
        cur.execute(CORRECTED_OPEN_SQL)
        rows = cur.fetchall()
        cur.execute(
            "SELECT count(*) FROM tariff_versions WHERE superseded_by_version_id IS NOT NULL"
        )
        corrected_total = cur.fetchone()[0]

    print("\n══ BR-RAT-1044 · CORRECTED ROWS WITH NO END DATE ══")
    for tenant_id, tenant_name, count in rows:
        print(f"  {count:>6}  {tenant_name} ({tenant_id})")
    total = sum(r[2] for r in rows)
    if not rows:
        print("  none — no corrected row on this database carries an open end date")
    print("  ── counted ──")
    print(f"    corrected rows with a NULL effective_to  : {total}")
    print(f"    tenants holding at least one             : {len(rows)}")
    print(f"    corrected rows in total (any end date)   : {corrected_total}")
    print(
        "  ── the answer ── "
        f"a backfill would touch {total} row(s) across {len(rows)} tenant(s)"
    )
    return total


# ══ DISCOUNTS ═══════════════════════════════════════════════════════════════
#
# `DEF-RAT-8050`. The same class of fault, one priced object over, and it is
# EXTENDED HERE rather than written as a second script on purpose: two census
# tools would be two definitions of "overlap", and the whole reason this one
# exists is that B2's definition and the billing code's disagreed by a day.
#
# ⚠ **THREE THINGS ARE GENUINELY DIFFERENT AND ARE NOT COPIED ACROSS.**
#
# 1 · **Supersession is a STATUS, not a foreign key.** `discount_versions`
#     carries `status = 'superseded'` and `discounts.py` says that is the
#     fact: *"`superseded` is what a later version does to an earlier one"*.
#     Every reader that prices filters `status = 'active'`; none filters
#     `superseded_by_version_id`. So **`active` is the only status counted**,
#     and there is no `CORRECTION` kind here — a settled correction has
#     already flipped the original to `superseded` and is simply not in scope.
#     (`rating/0049`'s predicate is the same sentence in DDL.)
#
# 2 · **`scheduled` and `pending_approval` are NOT counted, deliberately.**
#     A live discount's `effective_to` stays NULL until its successor is
#     activated, so every approved successor overlaps the incumbent's open
#     window BY DESIGN. Counting them would report a clean estate as
#     catastrophic.
#
# 3 · **The reprice question is asked of `discount_grants`, not
#     `invoice_lines`.** ⚠ `invoice_lines` carries `tariff_version_id` and
#     **NO discount version column at all** — so the schedule reprice check
#     has no mirror on the invoice line, and the stamp that does exist is
#     `discount_grants.discount_version_id` (NOT NULL). That is the row a
#     subsidy was actually granted on, and it is what this compares.

DISCOUNT_CENSUS_SQL = """
SELECT v.tenant_id,
       coalesce(t.name, '(unnamed tenant)') AS tenant_name,
       v.discount_id,
       d.code                                AS discount_code,
       v.id,
       v.version_no,
       v.effective_from,
       v.effective_to
  FROM discount_versions v
  JOIN discounts d  ON d.id = v.discount_id
  LEFT JOIN tenants t ON t.id = v.tenant_id
 WHERE v.effective_from IS NOT NULL
   AND v.status = 'active'
 ORDER BY v.tenant_id, v.discount_id, v.effective_from, v.version_no
"""


def _discount_classify(group: list[dict]) -> str:
    """The discount half of `_classify`, and it collapsed the same two kinds.

    ⚠ **`rating/0048` CARRIES THE IDENTICAL RULE TO `0046`** — its pass 1 reads
    `if earlier.effective_to is not None: continue` and its pass 2 then refuses
    the pair — so a stated end running into a later start is refused there too,
    and reporting it as `SUCCESSION` here sent the same operator round the same
    loop (`DEF-RAT-8070`). The kind is separated for the same reason.

    ⚠ **WHAT IS NOT FIXED HERE, STATED RATHER THAN LEFT TO BE FOUND:**
    `0048`'s refusal TEXT still names the two remedies `0046`'s named, and
    `manage.py rat_resolve_schedule_overlap` covers `tariff_versions` ONLY.
    That is `DEF-RAT-8071`'s DISCOUNT REMAINDER — filed, and deliberately NOT
    built: the kind is separated here so the census stops mis-reporting it,
    and a discount overlap still stops a deploy with advice that cannot be
    followed.
    """
    froms = [r["effective_from"] for r in group]
    if len(set(froms)) < len(froms):
        return "SAME-DATE"
    ordered = sorted(group, key=lambda r: (r["effective_from"], r["hi"]))
    for i, earlier in enumerate(ordered):
        for later in ordered[i + 1 :]:
            if earlier["effective_to"] is not None and _overlaps(
                (earlier["lo"], earlier["hi"]), (later["lo"], later["hi"])
            ):
                return "STATED-END"
    return "SUCCESSION"


def discount_census(conn, label: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM discount_versions")
        total_versions = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM discounts")
        total_discounts = cur.fetchone()[0]
        cur.execute(
            "SELECT status, count(*) FROM discount_versions GROUP BY status ORDER BY status"
        )
        by_status = cur.fetchall()
        cur.execute(
            "SELECT count(*) FROM discount_versions WHERE effective_from IS NULL"
        )
        dateless = cur.fetchone()[0]
        cur.execute(DISCOUNT_CENSUS_SQL)
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    for row in rows:
        row["lo"] = row["effective_from"]
        row["hi"] = _upper(row["effective_to"])

    by_discount: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        by_discount[(row["tenant_id"], row["discount_id"])].append(row)

    findings = []
    for (tenant_id, discount_id), versions in sorted(
        by_discount.items(), key=lambda kv: str(kv[0])
    ):
        for group in _groups(versions):
            findings.append(
                {
                    "tenant_id": tenant_id,
                    "tenant_name": group[0]["tenant_name"],
                    "discount_id": discount_id,
                    "discount_code": group[0]["discount_code"],
                    "kind": _discount_classify(group),
                    "rows": group,
                }
            )

    kinds = defaultdict(int)
    rows_in_overlap = 0
    for finding in findings:
        kinds[finding["kind"]] += 1
        rows_in_overlap += len(finding["rows"])

    print(f"\n══ {label} ══")
    for finding in findings:
        print(
            f"  {finding['kind']:<22} tenant {finding['tenant_name']} · "
            f"discount {finding['discount_code']} ({finding['discount_id']}) · "
            f"{len(finding['rows'])} rows"
        )
        for row in finding["rows"]:
            print(
                f"      active  v{row['version_no']}  {row['effective_from']} → "
                f"{row['effective_to'] or '(open)'}   {row['id']}"
            )
    if not findings:
        print("  no overlapping window found")

    print("  ── counted ──")
    print(f"    tenants with at least one active version : {len({r['tenant_id'] for r in rows})}")
    print(f"    discounts with at least one active dated version: {len(by_discount)}")
    print(f"    ACTIVE dated versions examined           : {len(rows)}")
    print("  ── skipped, with a number beside each (law 7) ──")
    print(f"    versions with NULL effective_from        : {dateless}")
    for status, count in by_status:
        mark = "COUNTED" if status == "active" else "skipped"
        print(f"    status {status:<18} : {count:>6}  ({mark})")
    print(
        "    discounts with exactly one active version: "
        f"{sum(1 for v in by_discount.values() if len(v) == 1)}"
    )
    print(f"    rows in `discounts` in total             : {total_discounts}")
    print(f"    rows in `discount_versions` in total     : {total_versions}")
    print("  ── the answer ──")
    print(f"    overlapping GROUPS                       : {len(findings)}")
    for kind in ("SUCCESSION", "STATED-END", "SAME-DATE"):
        print(f"      {kind:<22}                 : {kinds[kind]}")
    print(f"    version rows inside an overlap           : {rows_in_overlap}")
    print(
        "    distinct tenants affected                : "
        f"{len({f['tenant_id'] for f in findings})}"
    )
    if total_versions == 0:
        print(
            "  ⚠ THIS DATABASE HOLDS NO `discount_versions` ROWS AT ALL. The zero above "
            "is an EMPTY estate, not a clean one — and an unset `app.tenant_id` under "
            "RLS FORCE would look exactly the same. Nothing is proved about production."
        )
    elif not findings:
        print(
            "  ⚠ ZERO OVERLAPS ON THIS DATABASE. That proves the census RUNS; it proves "
            "NOTHING about production. Run the same command against the real database "
            "before believing the repair had nothing to do."
        )
    return {"findings": findings, "kinds": dict(kinds), "versions": len(rows)}


DISCOUNT_PLANT_SQL = "SELECT tenant_id FROM discounts LIMIT 1"
DISCOUNT_PLANT_FALLBACK = "SELECT id FROM tenants LIMIT 1"

MK_DISCOUNT = """
INSERT INTO discounts (id, tenant_id, code, name, status, report_in_assistance_filing,
                       is_sample, created_at, updated_at)
VALUES (gen_random_uuid(), %s, %s, %s, 'active', false, false, now(), now())
RETURNING id
"""

MK_DISCOUNT_VERSION = """
INSERT INTO discount_versions (
  id, tenant_id, discount_id, version_no, status, discount_type, value, currency,
  applies_to, bill_floor_amount, stacking_precedence, stacks_with_others,
  enrolment_mode, verification_method, proof_required, proof_before_first_reduction,
  recertification_notice_days, recertification_grace_days, lapse_behaviour,
  budget_period, exhaustion_behaviour, second_approval_required, self_approved,
  is_sample, created_at, updated_at, effective_from, effective_to
) VALUES (
  gen_random_uuid(), %s, %s, %s, %s, 'percentage', 15, 'USD',
  'whole_bill', 0, 0, true, 'automatic', 'automatic', false, false,
  60, 30, 'never_expires', 'annual', 'suspend', false, false,
  false, now(), now(), %s, %s
) RETURNING id
"""


def discount_plant_proof(conn) -> None:
    """Plant one discount overlap of each kind in a SAVEPOINT, count, ROLL BACK.

    Law 7: a counter that CANNOT find an overlap prints the same zero as a
    clean estate, and on **this** object the zero is the expected reading —
    the demo database holds no discounts at all. So the zero above means
    nothing until this has run.

    ⚠ **EACH KIND GETS ITS OWN SYNTHETIC DISCOUNT**, which is the mistake the
    schedule half of this file records making: planted onto an existing row,
    an open-ended incumbent chains every planted row into one group and the
    classifier reports one kind and misses the rest.

    ⚠ **IT ALSO PLANTS THE THREE STATUSES THAT MUST NOT BE COUNTED** —
    `scheduled`, `pending_approval` and `superseded` — over the incumbent's
    open window. If any of them shows up in the census the filter is wrong in
    the direction that would report every healthy tenant as broken.
    """
    with conn.cursor() as cur:
        cur.execute(DISCOUNT_PLANT_SQL)
        seed = cur.fetchone()
        if seed is None:
            cur.execute(DISCOUNT_PLANT_FALLBACK)
            seed = cur.fetchone()
        if seed is None:
            print(
                "\n⚠ --plant-proof (discounts) needs one tenant to hang a synthetic "
                "discount on, and this database has none. **THE DISCOUNT COUNTER IS "
                "UNPROVEN HERE.**"
            )
            return
        tenant_id = seed[0]
        cur.execute("SAVEPOINT plantdisc")

        def discount(code: str):
            cur.execute(MK_DISCOUNT, (tenant_id, code, code))
            return cur.fetchone()[0]

        def version(did, no, status, lo, hi):
            cur.execute(MK_DISCOUNT_VERSION, (tenant_id, did, no, status, lo, hi))
            return cur.fetchone()[0]

        # SUCCESSION: two ACTIVE rows, distinct starts, the older left open.
        succession = discount("PLANTED-SUCCESSION")
        version(succession, 1, "active", date(2099, 1, 1), None)
        version(succession, 2, "active", date(2099, 6, 1), None)
        # SAME-DATE: two ACTIVE rows sharing one start — the coin toss.
        tie = discount("PLANTED-SAME-DATE")
        version(tie, 1, "active", date(2098, 1, 1), date(2098, 12, 31))
        version(tie, 2, "active", date(2098, 1, 1), date(2098, 12, 31))
        # THE OFF-BY-ONE: `effective_to` is inclusive, `daterange` is not.
        touching = discount("PLANTED-TOUCHING")
        version(touching, 1, "active", date(2096, 1, 1), date(2096, 6, 30))
        version(touching, 2, "active", date(2096, 6, 30), None)
        # MUST NOT BE COUNTED: an incumbent with three non-active siblings all
        # overlapping its open window — the ordinary shape of a live discount
        # with a successor in the approval queue and a history behind it.
        healthy = discount("PLANTED-HEALTHY")
        version(healthy, 1, "active", date(2097, 1, 1), None)
        version(healthy, 2, "scheduled", date(2097, 6, 1), None)
        version(healthy, 3, "pending_approval", date(2097, 6, 1), None)
        version(healthy, 4, "superseded", date(2097, 1, 1), None)
        version(healthy, 5, "draft", None, None)

        result = discount_census(conn, "PLANTED DISCOUNT OVERLAPS (synthetic, rolled back)")
        with conn.cursor() as c2:
            c2.execute("ROLLBACK TO SAVEPOINT plantdisc")
        kinds = result["kinds"]
        # ⚠ `STATED-END` IS NAMED HERE FOR THE REASON THE SCHEDULE HALF NAMES IT
        # (`DEF-RAT-8070`): `PLANTED-TOUCHING` above is `2096-01-01 → 2096-06-30`
        # beside `2096-06-30 → (open)`, which IS the inclusive-end touch, and it
        # was counted as `SUCCESSION` until this defect. Leaving it out of
        # `expected` let the proof PASS either way — `missing` is `expected -
        # found`, so a kind that quietly stopped being returned would not be
        # missed by anything. That is law 7's *structurally incapable of
        # failing*, and it was caught by running this proof rather than by
        # reading it.
        expected = {"SUCCESSION", "SAME-DATE", "STATED-END"}
        found = {k for k, n in kinds.items() if n}
        missing = expected - found
        planted = {
            f["discount_code"]
            for f in result["findings"]
            if str(f["discount_code"]).startswith("PLANTED")
        }
        print(
            f"\n  plant-proof (discounts): expected kinds {sorted(expected)}; "
            f"found {sorted(found)}; MISSING {sorted(missing) or 'none'}"
        )
        print(f"  plant-proof (discounts): planted discounts seen: {sorted(planted)}")
        failed = False
        if missing:
            print("  ⚠ THE COUNTER CANNOT FIND EVERY KIND IT CLAIMS TO COUNT.")
            failed = True
        if "PLANTED-TOUCHING" not in planted:
            print(
                "  ⚠ THE INCLUSIVE-END TOUCH WAS MISSED — the `+ 1` is not being applied "
                "and a one-day coin toss reads as a clean handover."
            )
            failed = True
        if "PLANTED-HEALTHY" in planted:
            print(
                "  ⚠ A HEALTHY DISCOUNT WAS REPORTED AS AN OVERLAP. The status filter is "
                "counting `scheduled`, `pending_approval` or `superseded`, which would "
                "report every live tenant as broken."
            )
            failed = True
        if failed:
            sys.exit(1)
        print(
            "  plant-proof (discounts): the counter finds each planted overlap and "
            "leaves the healthy discount alone. Everything was rolled back."
        )


DISCOUNT_REPRICE_SQL = """
SELECT g.id                  AS grant_id,
       g.discount_version_id AS granted_on,
       g.tenant_id,
       g.discount_id,
       g.period_end,
       i.invoice_no
  FROM discount_grants g
  JOIN invoices i ON i.id = g.invoice_id
 WHERE g.invoice_id IS NOT NULL
   AND i.status NOT IN ('draft', 'void')
"""

DISCOUNT_UNSTAMPED_SQL = """
SELECT count(*) FROM discount_grants WHERE invoice_id IS NULL
"""

DISCOUNT_RESOLVE_SQL = """
SELECT id FROM discount_versions
 WHERE tenant_id = %s AND discount_id = %s
   AND status = 'active' AND effective_from IS NOT NULL
   AND effective_from <= %s
   AND (effective_to IS NULL OR effective_to >= %s)
 ORDER BY effective_from DESC, version_no DESC
 LIMIT 1
"""


def discount_reprice_check(conn) -> None:
    """Hard rule 4 — has any ISSUED bill's DISCOUNT basis moved?

    ⚠ **THE STAMP IS ON THE GRANT AND NOT ON THE INVOICE LINE, AND THE
    DIFFERENCE IS WORTH A NUMBER.** `invoice_lines` carries
    `tariff_version_id` and **no discount version column at all**, so the
    schedule check's exact mirror does not exist. What does exist is
    `discount_grants.discount_version_id`, NOT NULL, one row per subsidy
    actually granted — a stronger stamp than the schedule side has, because
    it cannot be null.

    The resolution below is `discount_services.active_version` written in SQL
    on purpose: reading it through the ORM would answer with whatever that
    selector does TODAY, which is the thing under test after a change to it.
    """
    with conn.cursor() as cur:
        cur.execute(DISCOUNT_UNSTAMPED_SQL)
        no_invoice = cur.fetchone()[0]
        cur.execute(DISCOUNT_REPRICE_SQL)
        cols = [c.name for c in cur.description]
        grants = [dict(zip(cols, r)) for r in cur.fetchall()]

        moved = []
        for grant in grants:
            end = grant["period_end"]
            cur.execute(
                DISCOUNT_RESOLVE_SQL, (grant["tenant_id"], grant["discount_id"], end, end)
            )
            now = cur.fetchone()
            now_id = now[0] if now else None
            if str(now_id) != str(grant["granted_on"]):
                moved.append((grant, now_id))

    print("\n══ DISCOUNT REPRICE CHECK (hard rule 4) ══")
    for grant, now_id in moved:
        print(
            f"  ⚠ invoice {grant['invoice_no']} grant {grant['grant_id']} was granted on "
            f"{grant['granted_on']} and {grant['period_end']} now resolves to {now_id}"
        )
    print(f"  grants on an ISSUED invoice, CHECKED          : {len(grants)}")
    print(f"  grants with no invoice (not checkable here)   : {no_invoice}")
    print(f"  grants whose basis MOVED                      : {len(moved)}")
    print(
        "  ⚠ `invoice_lines` carries NO discount version column — 0 of the discount "
        "lines on an invoice are stamped there, so this check reads `discount_grants` "
        "and nothing else can be checked."
    )
    if moved:
        print(
            "  ⚠ STOP. An already-issued bill's subsidy would now resolve to a "
            "different version. Hard rule 4 forbids a migration fixing this."
        )
    elif not grants:
        print(
            "  ⚠ NOTHING WAS CHECKED. No `discount_grants` row on this database sits on "
            "an issued invoice, so this zero says nothing at all."
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--plant-proof", action="store_true")
    ap.add_argument("--reprice-check", action="store_true")
    ap.add_argument(
        "--corrected-open",
        action="store_true",
        help=(
            "BR-RAT-1044 — count corrected rows that still carry a NULL "
            "effective_to, per tenant. The figure the PO needs before ruling "
            "on a backfill."
        ),
    )
    ap.add_argument("--plant-reprice", action="store_true")
    ap.add_argument(
        "--discounts",
        action="store_true",
        help=(
            "DEF-RAT-8050 — run the same census over `discount_versions`. "
            "`--plant-proof` and `--reprice-check` then cover the discount "
            "half too."
        ),
    )
    args = ap.parse_args()
    _kinds_are_declared()
    if not args.dsn:
        print("no --dsn and no DATABASE_URL", file=sys.stderr)
        sys.exit(2)

    with psycopg.connect(args.dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles "
                "WHERE rolname = current_user"
            )
            who = cur.fetchone()
        print(
            f"role {who[0]} · rolsuper={who[1]} · rolbypassrls={who[2]} — "
            "a census that cannot see every tenant's rows reports a clean estate"
        )
        census(conn, "LIVE ROWS")
        if args.discounts:
            discount_census(conn, "LIVE DISCOUNT ROWS")
        if args.corrected_open:
            corrected_open(conn)
        if args.reprice_check:
            reprice_check(conn)
            if args.discounts:
                discount_reprice_check(conn)
        if args.plant_reprice:
            plant_reprice_proof(conn)
        if args.plant_proof:
            plant_proof(conn)
            if args.discounts:
                discount_plant_proof(conn)
        conn.rollback()


if __name__ == "__main__":
    main()
