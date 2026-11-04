#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-RAT-7980 (2026-09-29) — B2 §2 signs an `EXCLUDE USING gist`
#           no-overlap constraint on `tariff_versions`; migration 0001 never
#           materialized it (`btree_gist` is absent from
#           `06-backend/db/000_extensions.sql`); migration 0004 REPORTED that
#           in its own header and left it "for the human review of this row";
#           that review never happened; and `rating/services.py:7623` was then
#           written as though the constraint existed — *"two open-ended windows
#           would collide with the B2 EXCLUDE constraint on Postgres"*. Four
#           versions of one sewer schedule went in force on the same date at a
#           live tenant, one-time bills and move-out final bills refuse, and
#           the ordinary bill run silently picks one of the four.
# Rules:    CLAUDE.md hard-won law 1 (a comment claiming a guarantee is not the
#           guarantee — three docstrings and one ledger row described this
#           constraint; none of them was it) · law 7, all five shapes, and in
#           particular *"reporting zero over a scope it silently excludes"* —
#           hence every count this gate prints of what it did NOT check · law
#           14 (the default suite is in-memory SQLite, which has no gist
#           constraints at all, so no test on that harness can ever see this)
# Tests:    _selftest() below, run as part 0 of EVERY run() — the detector is
#           shown red on a synthetic schema with the constraint removed and
#           green with it present, on every invocation rather than once at
#           birth (law 7's *"proved red, then never read"*).
# Impacts:  10-scripts/gates/run_gates.py ·
#           10-scripts/gates/g137_declared_constraints_baseline.txt
# ───────────────────────────────────────────────────────
"""G137 — a constraint the SIGNED SCHEMA declares is a constraint the DATABASE HAS.

WHY THIS GATE EXISTS
====================
B2 (`04-docs/02-decisions/02-database-design-brief.md`) is named by
`04-docs/03-contracts/README.md` as *"the authoritative Postgres 16 DDL, RLS,
indexes, partitioning"*. It is a CONTRACT. Nothing in this repository has ever
asked whether a line of that contract was built.

The cost of that, once, end to end: B2 §2 signs a no-overlap exclusion
constraint on `tariff_versions`. It was never created. A migration header said
so honestly and deferred it to a human review that never happened. Application
code was then written citing the constraint as the reason it was safe. A live
tenant ended up with four versions of one sewer schedule in force on the same
date; one-time bills and move-out final bills refuse outright, and the ordinary
bill run silently picks one of the four.

Every symptom descends from ONE signed guarantee that nothing checked was
built. This gate is the check.

WHAT IT CHECKS — AND READ THE NEXT SECTION BEFORE TRUSTING THIS ONE
====================================================================
It parses the `sql` fenced blocks of B2 into statements, and takes from them
every **table-level** `UNIQUE (...)`, `PRIMARY KEY (...)` and `EXCLUDE USING
... (...)` declaration, plus every `CREATE UNIQUE INDEX`. For each one it asks
a real PostgreSQL what that table actually has, and sorts the answer into three
buckets:

  * **MATCHED** — a constraint or unique index of the same kind over the same
    column set exists. (Column names are compared with a trailing `_id`
    stripped, because the ORM spells a foreign key `tariff_id` where B2 may
    spell it `tariff`; this is a deliberate loosening and it is the only one.)
  * **DIVERGED** — the table HAS a constraint of that kind touching at least
    one of the declared columns, but not the same set: a partial unique, a
    wider key, a renamed column. That is design drift, not an unbuilt
    guarantee, and each one must be written into
    `g137_declared_constraints_baseline.txt` **with a reason**. An
    un-baselined divergence FAILS, because a reason nobody wrote down is a
    reason nobody can check.
  * **NOT BUILT** — the table exists and has NOTHING of that kind over those
    columns, not even a divergent one. That is the `tariff_versions` case, and
    it is a FAIL with no baseline available to it.

WHAT IT CANNOT CHECK, WITH THE NUMBER BESIDE IT (law 7, fifth shape)
=====================================================================
`G32` once reported `0 unresolved` truthfully over 21 live refusals it could
not see. So this gate prints, on every run, how much of B2 it did not look at:

  * **`CHECK` expressions** — declared and never compared. Matching an
    arbitrary SQL predicate against `pg_get_constraintdef` output is a
    normalisation problem this gate does not pretend to have solved.
  * **Column-level `UNIQUE` / `PRIMARY KEY` / `REFERENCES`** — Django builds
    these mechanically from the model field, so they are not where a signed
    guarantee goes missing; they are counted and skipped.
  * **Plain `CREATE INDEX`** — performance, not a guarantee.
  * **Tables B2 declares that the database does not have** — renamed, merged
    or never built. Counted and named, never failed: this gate cannot tell a
    rename from an absence, and guessing would make it the kind of check that
    everybody learns to ignore.

THE TWO MODES, AND WHY THE WEAKER ONE STILL RUNS
=================================================
**DATABASE MODE** — `DATABASE_URL` (or `SBH_SCHEMA_DB_URL`) names a PostgreSQL
that has been migrated. Everything above applies; the verdict is a statement
about what the database HAS.

**SOURCE MODE** — no PostgreSQL is reachable. ⚠ **CLAUDE.md law 14: the test
suite runs on in-memory SQLite, which has no gist constraints at all**, so a
gate that only ever ran there could never see the truth. Rather than skip —
`G134`'s SKIP is honest because vitest is genuinely absent, but a gate that
skips in CI is a gate that never checks — source mode answers the ONE question
it can answer soundly: **for each declared `EXCLUDE`, does any migration or
`06-backend/db/*.sql` file actually create an exclusion constraint on that
table?** It reads EXECUTABLE text only — docstrings and comments are stripped
with `ast` and `tokenize` — because the single most misleading string in this
repository is `rating/0004`'s own header, which contains the exact text
`EXCLUDE USING gist (tenant_id WITH =, tariff_id WITH =, ...)` in a docstring
explaining that it was NOT built. A substring search over raw source passes
green on the defect this gate was written for.

Source mode decides EXCLUDE declarations and **reports every other declaration
as UNDECIDED with a count**. It does not guess.

HOW IT WAS PROVED RED (law 7, and in the harness `run_gates` uses)
===================================================================
`_selftest()` runs as part 0 of every `run()`. It puts the matcher on a
synthetic two-table schema and asserts all three verdicts: the exclusion
present → MATCHED, the exclusion removed → NOT BUILT, a partial unique in place
of a full one → DIVERGED. If any of those three does not come out, the gate
FAILS before it looks at anything real — a detector that cannot be shown to
fail is not a detector.

The live red proof, 2026-09-29, PostgreSQL 16.13, `sbh_tpl_c561df3f` (449
migrations applied):

    G137 FAIL: 1 signed constraint is NOT BUILT — tariff_versions EXCLUDE over
    (tenant_id, tariff_id, daterange(effective_from, coalesce(effective_to,
    'infinity'::date))): the table has no exclusion constraint at all.

and through `run_gates.py` rather than `python3 g137_...py`, because `G85` and
`G87` were both announced green while the suite reported `gate crashed:
AttributeError: module has no attribute 'run'` (DEF-GOV-3733).
"""
from __future__ import annotations

import ast
import io
import os
import re
import subprocess
import tokenize
from pathlib import Path
from urllib.parse import urlparse, unquote

import common

B2 = common.REPO_ROOT / "04-docs" / "02-decisions" / "02-database-design-brief.md"
BASELINE = Path(__file__).resolve().parent / "g137_declared_constraints_baseline.txt"
MIGRATION_DIRS = sorted((common.BACKEND_APPS).glob("*/migrations")) if common.BACKEND_APPS.is_dir() else []
RAW_SQL_DIR = common.BACKEND_DIR / "db"

#: The environment variables that may name the migrated PostgreSQL to compare
#: against, in order. `SBH_SCHEMA_DB_URL` exists so a lane can point this gate
#: at a template database (`10-scripts/proof-db.sh clone`) without disturbing
#: whatever `DATABASE_URL` its other tooling is using.
URL_VARS = ("SBH_SCHEMA_DB_URL", "DATABASE_URL")

PSQL_TIMEOUT = 60


# ── parsing B2 ──────────────────────────────────────────────────────────────

def _sql_blocks(markdown: str) -> str:
    return "\n".join(re.findall(r"```sql\n(.*?)```", markdown, re.S))


def _statements(sql: str) -> list[str]:
    """Split on `;` at paren depth zero, honouring `'` strings and `--` comments.

    ⚠ The naive version of this — strip `--` to end of line, then count parens
    — goes WRONG on B2 line 292, whose `COMMENT ON TABLE tariff_versions IS
    '… [effective_from,effective_to) …'` carries an unmatched `)` inside a
    string literal. Depth then goes negative and every statement after it is
    swallowed: the first draft of this parser found 24 of B2's 61 tables and
    reported confidently on the 24. That is law 7's fifth shape in the parser
    itself, which is why the table count is printed in the verdict.
    """
    out: list[str] = []
    cur: list[str] = []
    depth = 0
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'":
            j = sql.find("'", i + 1)
            j = n - 1 if j < 0 else j
            cur.append(sql[i:j + 1])
            i = j + 1
            continue
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j < 0 else j
            cur.append(" ")
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == ";" and depth == 0:
            out.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    if "".join(cur).strip():
        out.append("".join(cur))
    return out


def _split_top(body: str) -> list[str]:
    """Split a parenthesised body on top-level commas (strings honoured)."""
    items: list[str] = []
    cur: list[str] = []
    depth = 0
    i, n = 0, len(body)
    while i < n:
        ch = body[i]
        if ch == "'":
            j = body.find("'", i + 1)
            j = n - 1 if j < 0 else j
            cur.append(body[i:j + 1])
            i = j + 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            items.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    if "".join(cur).strip():
        items.append("".join(cur))
    return [x.strip() for x in items if x.strip()]


def _balanced(body: str) -> str:
    """The text up to the paren that closes the one already opened."""
    depth = 1
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if c == "'":
            j = body.find("'", i + 1)
            i = (n - 1 if j < 0 else j) + 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return body[:i]
        i += 1
    return body


def _inner_cols(expr: str) -> list[str]:
    return [c.strip().strip('"') for c in _split_top(expr[expr.find("(") + 1:expr.rfind(")")])]


def norm(col: str) -> str:
    """Compare column names with a trailing `_id` stripped — the ORM spells a
    foreign key `tariff_id` where B2 may spell it `tariff`. The ONLY loosening
    in this gate, and it is stated in the verdict so nobody has to find it."""
    c = col.lower().strip().strip('"')
    return c[:-3] if c.endswith("_id") else c


class Declared:
    __slots__ = ("table", "kind", "cols", "raw")

    def __init__(self, table: str, kind: str, cols: list[str], raw: str):
        self.table, self.kind, self.cols, self.raw = table, kind, cols, raw

    @property
    def key(self) -> str:
        return f"{self.table}|{self.kind}|{','.join(self.cols)}"

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return self.key


def parse_declarations(markdown: str) -> tuple[list[Declared], dict[str, int], set[str]]:
    """(checkable declarations, counts of what was NOT taken, table names in B2)."""
    unchecked = {
        "check-expressions": 0,
        "column-level-unique": 0,
        "column-level-primary-key": 0,
        "column-level-foreign-key": 0,
        "table-level-foreign-key": 0,
        "plain-indexes": 0,
    }
    declarations: list[Declared] = []
    tables: set[str] = set()

    for stmt in _statements(_sql_blocks(markdown)):
        idx = re.search(
            r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_0-9]+)\s+ON\s+([a-zA-Z_0-9]+)\s*(?:USING\s+\w+\s*)?\(",
            stmt, re.I)
        if idx:
            if re.search(r"CREATE\s+UNIQUE\s+INDEX", stmt, re.I):
                body = _balanced(stmt[idx.end():])
                declarations.append(
                    Declared(idx.group(2), "u", [c.strip() for c in _split_top(body)], stmt.strip()))
            else:
                unchecked["plain-indexes"] += 1
            continue

        # ⚠ **`ALTER TABLE … ADD CONSTRAINT` WAS INVISIBLE TO THIS GATE UNTIL
        # 2026-09-29 (`DEF-RAT-8052`), AND A DECLARATION NOTHING READS IS
        # WORSE THAN NO DECLARATION** — it looks signed and is not checked,
        # which is the exact shape (`hard-won law 1`) that let B2 §2's
        # `tariff_versions` EXCLUDE go unbuilt for seven weeks. B2 addendum
        # r26 signs `discount_versions`' no-overlap constraint in that form
        # on purpose: restating forty columns of a table the ORM owns would
        # create a second source of truth for all of them. So the gate reads
        # the form the document uses.
        #
        # ⚠ The table is NOT added to `tables` here. `tables` is *"the tables
        # B2 declares"*, used to report a declared table the database does
        # not have; an ALTER names a table declared somewhere else — possibly
        # only in the ORM — and counting it would turn an honest
        # not-a-table-in-B2 into a phantom.
        alt = re.search(
            r"ALTER\s+TABLE\s+(?:ONLY\s+)?([a-zA-Z_0-9]+)\s+ADD\s+CONSTRAINT\s+\S+\s+"
            r"(EXCLUDE|UNIQUE|PRIMARY\s+KEY)\b",
            stmt, re.I)
        if alt:
            alter_table = alt.group(1)
            kind = {"e": "x", "u": "u", "p": "p"}[alt.group(2)[0].lower()]
            rest = stmt[alt.end():]
            open_paren = rest.find("(")
            if open_paren < 0:
                continue
            body = _balanced(rest[open_paren + 1:])
            cols = [c.split(" WITH")[0].strip() for c in _split_top(body)]
            declarations.append(Declared(alter_table, kind, cols, stmt.strip()))
            continue

        m = re.search(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_0-9]+)\s*\(", stmt, re.I)
        if not m:
            continue
        table = m.group(1)
        tables.add(table)
        for item in _split_top(_balanced(stmt[m.end():])):
            head = item.upper().lstrip()
            if head.startswith("CONSTRAINT"):
                head = re.sub(r"^CONSTRAINT\s+\S+\s*", "", head)
                item = re.sub(r"^\s*CONSTRAINT\s+\S+\s*", "", item)
            if head.startswith("UNIQUE"):
                declarations.append(Declared(table, "u", _inner_cols(item), item))
            elif head.startswith("EXCLUDE"):
                cols = [c.split(" WITH")[0].strip() for c in _inner_cols(item)]
                declarations.append(Declared(table, "x", cols, item))
            elif head.startswith("PRIMARY KEY"):
                declarations.append(Declared(table, "p", _inner_cols(item), item))
            elif head.startswith("CHECK"):
                unchecked["check-expressions"] += 1
            elif head.startswith("FOREIGN KEY"):
                unchecked["table-level-foreign-key"] += 1
            else:
                if re.search(r"\bUNIQUE\b", head):
                    unchecked["column-level-unique"] += 1
                if re.search(r"\bPRIMARY KEY\b", head):
                    unchecked["column-level-primary-key"] += 1
                if re.search(r"\bCHECK\b", head):
                    unchecked["check-expressions"] += 1
                if re.search(r"\bREFERENCES\b", head):
                    unchecked["column-level-foreign-key"] += 1
    return declarations, unchecked, tables


# ── the database's side ─────────────────────────────────────────────────────

CONSTRAINT_QUERY = """
select c.relname, con.contype, pg_get_constraintdef(con.oid)
  from pg_constraint con
  join pg_class c on c.oid = con.conrelid
  join pg_namespace n on n.oid = c.relnamespace
 where n.nspname = 'public' and con.contype in ('u','x','p')
union all
select tablename, 'i', indexdef
  from pg_indexes
 where schemaname = 'public' and indexdef like 'CREATE UNIQUE%'
union all
select tablename, 't', ''
  from pg_tables
 where schemaname = 'public'
"""


def _psql(url: str, sql: str) -> tuple[bool, str]:
    parts = urlparse(url)
    env = dict(os.environ)
    if parts.password:
        env["PGPASSWORD"] = unquote(parts.password)
    cmd = ["psql", "-tAF", "|", "-v", "ON_ERROR_STOP=1",
           "-h", parts.hostname or "127.0.0.1",
           "-p", str(parts.port or 5432),
           "-d", (parts.path or "/").lstrip("/"),
           "-c", sql]
    if parts.username:
        cmd[len(cmd) - 2:len(cmd) - 2] = ["-U", unquote(parts.username)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=PSQL_TIMEOUT)
    except FileNotFoundError:
        return False, "the `psql` client is not installed on this machine"
    except subprocess.TimeoutExpired:
        return False, f"`psql` did not answer within {PSQL_TIMEOUT}s"
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip().splitlines()[-1:][0] if (proc.stderr or proc.stdout).strip() else "psql failed"
    return True, proc.stdout


def db_snapshot(url: str) -> tuple[dict[str, list[tuple[str, str]]], set[str]] | str:
    ok, out = _psql(url, CONSTRAINT_QUERY)
    if not ok:
        return out
    by_table: dict[str, list[tuple[str, str]]] = {}
    tables: set[str] = set()
    for line in out.splitlines():
        if not line.strip():
            continue
        table, contype, definition = (line.split("|", 2) + ["", ""])[:3]
        if contype == "t":
            tables.add(table)
            continue
        tables.add(table)
        by_table.setdefault(table, []).append((contype, definition))
    return by_table, tables


def _def_columns(contype: str, definition: str) -> list[str]:
    """The key columns of a constraint or index definition, normalised."""
    if contype == "x":
        return sorted({norm(c) for c in re.findall(r"([a-z_0-9]+)\s+WITH", definition)})
    if contype == "i":
        m = re.search(r"USING\s+\w+\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)", definition)
    else:
        m = re.search(r"\(([^()]*(?:\([^()]*\)[^()]*)*)\)", definition)
    if not m:
        return []
    return sorted(norm(c) for c in m.group(1).split(","))


def classify(decl: Declared, rows: list[tuple[str, str]]) -> tuple[str, str]:
    """MATCHED / DIVERGED / NOT-BUILT for one declaration against one table."""
    want = sorted(norm(c) for c in decl.cols)
    same_kind = {
        "x": ("x",),
        "p": ("p",),
        "u": ("u", "i", "p"),
    }[decl.kind]
    touching = ""
    exact_partial = ""
    for contype, definition in rows:
        if contype not in same_kind:
            continue
        got = _def_columns(contype, definition)
        if decl.kind == "x":
            # A gist window constraint's third "column" is an expression —
            # `daterange(effective_from, coalesce(...)) WITH &&` — and
            # `pg_get_constraintdef` does not print it as a bare identifier, so
            # the database side yields only (tenant_id, tariff_id) where B2
            # declares three. An exact set comparison would call the built
            # constraint missing. Containment either way is therefore the test,
            # and the cost of that is stated rather than hidden: an exclusion
            # constraint over a SUBSET of the declared keys reads as MATCHED
            # here. This gate answers "is there one" and not "is it the right
            # one"; any exclusion constraint whose keys merely OVERLAP is
            # DIVERGED and needs a written reason.
            if set(want) & set(got) or not got:
                if set(want) <= set(got) or set(got) <= set(want):
                    return "MATCHED", definition
            touching = touching or definition
            continue
        if got == want:
            if re.search(r"\bWHERE\b", definition, re.I):
                # A partial unique over exactly the declared columns is the most
                # informative witness there is, so it WINS the witness slot over
                # a merely overlapping key — otherwise the verdict quotes an
                # unrelated constraint and reads like a parser bug.
                exact_partial = definition
                continue
            return "MATCHED", definition
        if set(got) & set(want):
            touching = touching or definition
    if exact_partial:
        return "DIVERGED", exact_partial
    if touching:
        return "DIVERGED", touching
    return "NOT-BUILT", ""


# ── source mode: executable text only ───────────────────────────────────────

def executable_text(path: Path) -> str:
    """A Python file's code with comments and docstrings REMOVED.

    ⚠ This function is the difference between this gate working and this gate
    reporting a confident PASS on the very defect it was written for.
    `apps/rating/migrations/0004_...py` carries the full text `EXCLUDE USING
    gist (tenant_id WITH =, tariff_id WITH =, ...)` **in its module docstring**,
    in a paragraph explaining that the constraint was NOT built. A grep of raw
    source finds it and calls the constraint present.
    """
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    prose_lines: set[int] = set()
    try:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant) \
                        and isinstance(child.value.value, str):
                    prose_lines.update(range(child.lineno, (child.end_lineno or child.lineno) + 1))
    except SyntaxError:
        return ""
    pieces: list[str] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                continue
            if tok.type == tokenize.STRING and tok.start[0] in prose_lines:
                continue
            pieces.append(tok.string)
    except (tokenize.TokenError, IndentationError):
        return ""
    return "\n".join(pieces)


def exclusion_evidence() -> dict[str, list[str]]:
    """table -> files whose EXECUTABLE text creates an exclusion constraint on it."""
    found: dict[str, list[str]] = {}
    sources: list[tuple[Path, str]] = []
    for directory in MIGRATION_DIRS:
        for path in sorted(directory.glob("*.py")):
            sources.append((path, executable_text(path)))
    if RAW_SQL_DIR.is_dir():
        for path in sorted(RAW_SQL_DIR.glob("*.sql")):
            sources.append((path, path.read_text(encoding="utf-8", errors="replace")))
    # ⚠ THE WINDOW IS THE POINT. A file-wide search would mark EVERY identifier
    # in a file that creates one exclusion constraint as having one of its own —
    # `integrations/0001` alone would vouch for a hundred table names. So only
    # the text around each `EXCLUDE USING` / `ExclusionConstraint` counts, and
    # the window is deliberately generous (a Django `AddConstraint` names its
    # model some lines above the constraint): this mode is allowed to be
    # approximate ACROSS tables, never approximate about a table having none.
    window = 600
    for path, text in sources:
        spans = [m.start() for m in re.finditer(r"ExclusionConstraint|EXCLUDE\s+USING", text, re.I)]
        if not spans:
            continue
        for start in spans:
            around = text[max(0, start - window):start + window]
            for table in re.findall(r"[a-z][a-z_0-9]{2,}", around):
                found.setdefault(table, [])
                if common.rel(path) not in found[table]:
                    found[table].append(common.rel(path))
    return found


# ── the baseline of accepted divergences ────────────────────────────────────

def read_baseline() -> dict[str, str]:
    accepted: dict[str, str] = {}
    if not BASELINE.is_file():
        return accepted
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 4:
            continue
        accepted["|".join(parts[:3])] = parts[3].strip()
    return accepted


# ── part 0: the red proof, on every run ─────────────────────────────────────

SELFTEST_B2 = """```sql
CREATE TABLE tariff_versions (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  tariff_id uuid NOT NULL,
  effective_from date NOT NULL,
  effective_to date,
  UNIQUE (tenant_id, code),
  EXCLUDE USING gist (
    tenant_id WITH =, tariff_id WITH =,
    daterange(effective_from, coalesce(effective_to,'infinity'::date)) WITH &&
  )
);
COMMENT ON TABLE tariff_versions IS 'a string with an unmatched ) paren in it';
CREATE TABLE later_table (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  code text NOT NULL,
  CHECK (code <> ''),
  UNIQUE (tenant_id, code)
);
ALTER TABLE altered_table
  ADD CONSTRAINT ex_altered_no_overlap
  EXCLUDE USING gist (
    tenant_id WITH =, owner_id WITH =,
    daterange(effective_from, coalesce(effective_to + 1,'infinity'::date)) WITH &&
  )
  WHERE (status = 'active' AND effective_from IS NOT NULL)
  DEFERRABLE INITIALLY DEFERRED;
```"""


def _selftest() -> list[str]:
    """Show the detector red before trusting it green — every invocation."""
    problems: list[str] = []
    decls, unchecked, tables = parse_declarations(SELFTEST_B2)

    if "later_table" not in tables:
        problems.append(
            "the statement splitter lost the table after a string literal holding an "
            "unmatched paren — the exact fault that made the first draft read 24 of "
            "B2's 61 tables")
    if unchecked["check-expressions"] != 1:
        problems.append("a CHECK expression was not counted as unchecked")
    kinds = sorted(f"{d.table}:{d.kind}" for d in decls)
    if kinds != ["altered_table:x", "later_table:u", "tariff_versions:u", "tariff_versions:x"]:
        problems.append(f"declaration parse is wrong: {kinds}")
    # `DEF-RAT-8052` — the ALTER form, shown parsed on every run. Without this
    # the gate reads B2 addendum r26 as saying nothing at all and reports a
    # clean verdict over a constraint it never looked for (law 7, fifth
    # shape). The columns matter as much as the kind: `WITH =` must be
    # stripped and the `daterange(...)` expression kept whole.
    altered = next((d for d in decls if d.table == "altered_table"), None)
    if altered is None or altered.cols[:2] != ["tenant_id", "owner_id"]:
        problems.append(
            "an ALTER TABLE ... ADD CONSTRAINT ... EXCLUDE was not parsed into a "
            "checkable declaration — B2 addendum r26 would be invisible")
    if altered is not None and "altered_table" in tables:
        problems.append(
            "an ALTER's table was counted as a table B2 DECLARES — it is not, and "
            "counting it turns an honest absence into a phantom missing table")

    excl = next((d for d in decls if d.kind == "x"), None)
    uniq = next((d for d in decls if d.kind == "u" and d.table == "tariff_versions"), None)
    if excl is None or uniq is None:
        return problems + ["the synthetic schema did not yield its two declarations"]

    present = [("x", "EXCLUDE USING gist (tenant_id WITH =, tariff_id WITH =, "
                     "daterange(effective_from, COALESCE(effective_to, 'infinity'::date)) WITH &&)"),
               ("u", "UNIQUE (tenant_id, code)")]
    absent = [("u", "UNIQUE (tenant_id, code)")]
    partial = [("i", "CREATE UNIQUE INDEX uq ON public.tariff_versions USING btree "
                     "(tenant_id, code) WHERE (code IS NOT NULL)")]

    for label, rows, decl, want in (
        ("constraint present", present, excl, "MATCHED"),
        ("constraint removed", absent, excl, "NOT-BUILT"),
        ("full unique present", present, uniq, "MATCHED"),
        ("only a partial unique", partial, uniq, "DIVERGED"),
    ):
        got, _ = classify(decl, rows)
        if got != want:
            problems.append(f"synthetic case '{label}' returned {got}, expected {want}")
    return problems


# ── the gate ────────────────────────────────────────────────────────────────

def _database_url() -> tuple[str, str] | None:
    for var in URL_VARS:
        url = os.environ.get(var, "").strip()
        if not url:
            continue
        scheme = (urlparse(url).scheme or "").split("+")[0].lower()
        if scheme in ("postgres", "postgresql"):
            return var, url
    return None


def _unchecked_sentence(unchecked: dict[str, int], absent_tables: list[str], b2_tables: int) -> str:
    parts = ", ".join(f"{n} {name}" for name, n in unchecked.items() if n)
    extra = ""
    if absent_tables:
        extra = (f"; {len(absent_tables)} declaration(s) name a table this database does not "
                 f"have ({', '.join(sorted(set(absent_tables))[:4])}"
                 f"{' …' if len(set(absent_tables)) > 4 else ''}) — renamed or never built, "
                 f"and this gate cannot tell which")
    return f"NOT CHECKED: {parts} across B2's {b2_tables} declared tables{extra}"


def run() -> tuple[str, str]:
    problems = _selftest()
    if problems:
        return "FAIL", (
            "the detector failed its own synthetic cases before looking at anything real "
            f"({len(problems)}): {problems[0]}"
        )

    if not B2.is_file():
        return "FAIL", (
            f"{common.rel(B2)} is missing — B2 is the signed schema contract this gate "
            "reads. A sweep of nothing passes cleanly, so its absence is a FAIL by "
            "construction, not a skip.")

    declarations, unchecked, b2_tables = parse_declarations(B2.read_text(encoding="utf-8"))
    if len(declarations) < 20 or len(b2_tables) < 50:
        return "FAIL", (
            f"parsed only {len(declarations)} constraint declaration(s) across "
            f"{len(b2_tables)} table(s) of B2. B2 held 33 declarations across 61 tables "
            "when this gate was written; a collapse means the document's shape moved "
            "under the parser, and a shrinking scope reporting PASS is law 7's fifth "
            "shape.")

    baseline = read_baseline()
    chosen = _database_url()

    # ── SOURCE MODE ─────────────────────────────────────────────────────────
    if chosen is None:
        evidence = exclusion_evidence()
        exclusions = [d for d in declarations if d.kind == "x"]
        missing = [d for d in exclusions if not evidence.get(d.table)]
        undecided = len(declarations) - len(exclusions)
        where = (f"Point it at a migrated PostgreSQL for the full check: "
                 f"SBH_SCHEMA_DB_URL=postgres://user:pass@host:5432/db "
                 f"(10-scripts/proof-db.sh clone <label> --export prints one)")
        if missing:
            first = missing[0]
            return "FAIL", (
                f"SOURCE MODE (no PostgreSQL named by {' or '.join(URL_VARS)}): "
                f"{len(missing)} of {len(exclusions)} EXCLUDE constraint(s) signed by B2 are "
                f"created by no migration and no db/*.sql file — "
                f"{first.table} over ({', '.join(first.cols)})"
                + (f" (+{len(missing) - 1} more)" if len(missing) > 1 else "")
                + f". Docstrings and comments were stripped before searching, because "
                  f"rating/0004's header quotes the missing constraint in full. "
                  f"{undecided} UNIQUE/PRIMARY KEY declaration(s) are UNDECIDED here — this "
                  f"mode does not guess. {_unchecked_sentence(unchecked, [], len(b2_tables))}. "
                  f"{where}")
        return "PASS", (
            f"SOURCE MODE (no PostgreSQL named by {' or '.join(URL_VARS)}): all "
            f"{len(exclusions)} EXCLUDE constraint(s) B2 signs are created by some migration "
            f"or db/*.sql file, read as executable text only. ⚠ {undecided} UNIQUE/PRIMARY KEY "
            f"declaration(s) are UNDECIDED in this mode and are NOT part of this PASS. "
            f"{_unchecked_sentence(unchecked, [], len(b2_tables))}. {where}")

    # ── DATABASE MODE ───────────────────────────────────────────────────────
    var, url = chosen
    snapshot = db_snapshot(url)
    if isinstance(snapshot, str):
        return "FAIL", (
            f"{var} names a PostgreSQL this gate could not read: {snapshot}. A database "
            "that was named and could not be introspected is a FAIL, not a skip — the "
            "silent version of this is a gate that checks nothing and says PASS.")
    by_table, db_tables = snapshot
    if "django_migrations" not in db_tables:
        return "FAIL", (
            f"{var} names a database with no `django_migrations` table, so it has never "
            f"been migrated; every declaration would read as NOT BUILT and the verdict "
            f"would be noise. Migrate it, or point {var} at a template built by "
            f"10-scripts/proof-db.sh.")

    matched: list[Declared] = []
    diverged: list[tuple[Declared, str]] = []
    not_built: list[Declared] = []
    absent_tables: list[str] = []
    stale_baseline = list(baseline)

    for decl in declarations:
        if decl.table not in db_tables:
            absent_tables.append(decl.table)
            continue
        verdict, definition = classify(decl, by_table.get(decl.table, []))
        if verdict == "MATCHED":
            matched.append(decl)
        elif verdict == "DIVERGED":
            if decl.key in baseline:
                if decl.key in stale_baseline:
                    stale_baseline.remove(decl.key)
                matched.append(decl)
            else:
                diverged.append((decl, definition))
        else:
            not_built.append(decl)

    checked = len(matched) + len(diverged) + len(not_built)
    tail = (f"{checked} of {len(declarations)} declaration(s) compared against {var}; "
            f"{len(matched)} built (incl. {len(baseline) - len(stale_baseline)} baselined "
            f"divergence(s)); column names compared with a trailing `_id` stripped. "
            f"{_unchecked_sentence(unchecked, absent_tables, len(b2_tables))}")

    if not_built:
        first = not_built[0]
        kind = {"x": "EXCLUDE", "u": "UNIQUE", "p": "PRIMARY KEY"}[first.kind]
        return "FAIL", (
            f"{len(not_built)} signed constraint(s) are NOT BUILT — {first.table} {kind} over "
            f"({', '.join(first.cols)}): the table has no constraint of that kind over those "
            f"columns at all"
            + (f"; also " + "; ".join(f"{d.table} {d.kind.upper()} ({','.join(d.cols)})"
                                      for d in not_built[1:4]) if len(not_built) > 1 else "")
            + f". B2 is the signed schema contract; a line of it that no migration built is "
              f"a guarantee the application code is entitled to rely on and cannot. {tail}")

    if diverged:
        first, definition = diverged[0]
        return "FAIL", (
            f"{len(diverged)} declaration(s) are built DIFFERENTLY from what B2 signs and no "
            f"reason is recorded — {first.table} {first.kind.upper()} ({', '.join(first.cols)}) "
            f"is built as `{definition[:110]}`. Drift may be right; an UNWRITTEN reason never "
            f"is. Add a line to {common.rel(BASELINE)} stating why, or make the schema match. "
            f"{tail}")

    if stale_baseline:
        return "FAIL", (
            f"{len(stale_baseline)} baselined divergence(s) no longer exist and the baseline "
            f"still excuses them: {stale_baseline[0]}. A baseline that outlives its subject is "
            f"a check that has stopped checking. Remove the line from "
            f"{common.rel(BASELINE)}. {tail}")

    return "PASS", f"every constraint B2 signs and this gate can read is built. {tail}"


def report() -> int:
    """Every bucket, named, for a human deciding what to build or baseline.

    The verdict line names the FIRST failure and counts the rest, which is the
    right shape for a merge gate and the wrong shape for someone about to write
    a baseline line. `--report` is that second reader's view; it changes
    nothing and decides nothing.
    """
    declarations, unchecked, b2_tables = parse_declarations(B2.read_text(encoding="utf-8"))
    baseline = read_baseline()
    chosen = _database_url()
    print(f"B2 declares {len(declarations)} checkable constraint(s) across {len(b2_tables)} table(s).")
    print(_unchecked_sentence(unchecked, [], len(b2_tables)))
    if chosen is None:
        evidence = exclusion_evidence()
        for decl in declarations:
            if decl.kind != "x":
                print(f"  UNDECIDED (source mode)  {decl.key}")
                continue
            where = evidence.get(decl.table)
            print(f"  {'BUILT   ' if where else 'NOT BUILT'}  {decl.key}"
                  + (f"  <- {', '.join(where)}" if where else ""))
        return 0
    var, url = chosen
    snapshot = db_snapshot(url)
    if isinstance(snapshot, str):
        print(f"could not read {var}: {snapshot}")
        return 1
    by_table, db_tables = snapshot
    for decl in declarations:
        if decl.table not in db_tables:
            print(f"  TABLE ABSENT  {decl.key}")
            continue
        verdict, definition = classify(decl, by_table.get(decl.table, []))
        note = " [baselined]" if verdict == "DIVERGED" and decl.key in baseline else ""
        print(f"  {verdict:<10}{note}  {decl.key}" + (f"\n{'':>14}built as: {definition}" if definition and verdict != "MATCHED" else ""))
    return 0


def main() -> int:
    import sys
    if "--report" in sys.argv[1:]:
        return report()
    status, detail = run()
    print(f"G137 {status}: {detail}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
