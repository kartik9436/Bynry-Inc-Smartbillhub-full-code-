"""G16 — NFR-24 partition coverage. Added 2026-08-11 by Eng-Lead, from DEF-031.

NFR-24 names five tables that MUST be monthly-partitioned and ends the sentence
"No exceptions". `invoice_lines` shipped unpartitioned in W3 and `journal_lines`
in W5 and NOTHING CAUGHT EITHER — G1–G15 all passed on both, because no gate
reads NFR-24, and the partition guard
(06-backend/tests/test_us_aud_001_partition_rls.py) asks whether the partitions
that EXIST are RLS-guarded, not whether a table that SHOULD be partitioned IS
one. A performance and retention rule with real consequences at 3,000
connections had no machine reading it at all. DEF-031's `prevention` column
calls this gate the durable half of the fix: "Half (1) without half (2) leaves
the next table in the set free to ship flat again."

WHY THIS GATE HAS NO TABLE LIST IN IT
-------------------------------------
Same reasoning as the guard it complements, in its own words: "the failure mode
here is *forgetting a table*, so the guard must not have a table list in it."
That guard asks PostgreSQL; this one runs with no database, so it asks the two
authorities that live in the repo:

  * WHICH TABLES MUST BE PARTITIONED — parsed out of NFR-24 itself
    (04-docs/02-decisions/06-non-functional-requirements.md), from the clause
    after "applies to". A sixth table added to that sentence is enforced by this
    gate the moment the sentence is saved, with no edit here.
  * WHETHER A TABLE IS PARTITIONED — the migration DDL that creates it. A
    partitioned table is created by `CREATE TABLE <t> (…) PARTITION BY …`;
    `options={"db_table": "<t>"}` on a Django CreateModel is a plain table. The
    catalog would be a better witness, but the gate suite is stdlib-only with no
    database, and the migrations ARE what any database will be built from.
    `core.partitioning.ACTIVE_TABLES` is deliberately NOT used as the answer to
    this question: it is a claim made in code (hard-won law 1), and check C
    below exists precisely because such a claim can be wrong.

THREE CHECKS
------------
A. COVERAGE — every table NFR-24 names is created with `PARTITION BY`, or is
   named in `partition_exceptions.txt`. A table NFR-24 names that no migration
   or model declares yet has not landed; it is reported, not failed (you cannot
   partition a table that does not exist), and the day it lands flat, A fails.
B. EXCEPTION HYGIENE — the hard part, and the reason this gate can exist at all.
   Three of the five tables are unpartitioned RIGHT NOW, deliberately, with OPEN
   questions against them (OQ-107 for invoice_lines/journal_lines; OQ-108, where
   partitioning would switch CLAUDE.md hard rule 6 OFF, for outbound_messages).
   A gate that failed on those would block every merge and be switched off
   within a day; a gate that quietly tolerated them is the gate that let DEF-031
   happen. So the exception is made explicit, attributable and EXPIRING, exactly
   as G8 handles the same shape for `NotImplementedError("OQ-###")` stubs: an
   entry must cite an OQ that (a) exists in 12-governance/01-open-questions.md,
   (b) is NOT closed — a closed question means the exception's reason is gone
   and the ruling must be implemented — and (c) actually names the table in its
   registry row, so a table cannot be parked behind any convenient open OQ. It
   must also carry a date and a reason (attribution), name a table NFR-24
   actually covers, and be DELETED in the same diff that partitions the table:
   an entry for an already-partitioned table fails as stale, because a dead
   exception is a licence sitting there for whoever removes the partitioning
   next.
C. REGISTRY TIE-OUT — `core/partitioning.py` says "The registry below is the
   NFR-24 mandatory set" and "ACTIVE_TABLES: which of the five exist as
   partitioned parents today". Both are comments claiming a guarantee (law 1),
   so both are checked: REGISTRY must equal NFR-24's list, and ACTIVE_TABLES
   must equal the set the migrations really create partitioned. That second one
   is not theoretical — `meter_reads` landed partitioned in W2 and was left out
   of ACTIVE_TABLES, so the create-ahead job never renewed its 28-partition
   window and reads INSERTs would have started failing when it ran out. Nothing
   caught that either; a human noticed it while fixing DEF-027. If a sixth table
   is genuinely partitioned outside NFR-24's mandatory set, the honest fix is to
   change that docstring claim and this check together — not to loosen it here.

Fails closed. If NFR-24 cannot be read, or its table list cannot be parsed, the
gate FAILs: a gate whose contract has gone missing must block the merge, never
wave it through. Quietly deleting a table from NFR-24's sentence does not buy
silence either — check C goes RED unless core/partitioning.py is edited in the
same diff, and both are reviewable.

Proved RED before trusted green (law 7), each against a mutated copy of the repo:
  * `invoice_lines` unpartitioned with its exception line removed → FAIL
  * `PARTITION BY RANGE (created_at)` stripped from apps/audit/0001 → FAIL,
    which is what makes audit_log's and meter_reads' PASS non-vacuous
  * OQ-107 flipped to CLOSED in the registry → FAIL on both its entries
  * an entry re-pointed at OQ-999 (not in the registry) → FAIL

RATIFIED 2026-08-11 by the PO (option A, "keep all four blocking"): G1-G16 are
the confirmed merge-blocking set. G13-G16 were Eng-Lead additions made from
defects that reached the running product; they are now confirmed law, so a
loosening here - an allowlist entry, a skipped check, a widened pattern - is a
change to a ratified decision and belongs in the daily PO batch.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

import sys
import re
from datetime import date
from pathlib import Path

import common

NFR_DOC = common.REPO_ROOT / "04-docs" / "02-decisions" / "06-non-functional-requirements.md"
EXCEPTIONS_FILE = Path(__file__).resolve().parent / "partition_exceptions.txt"
PARTITIONING_MODULE = common.BACKEND_DIR / "core" / "partitioning.py"

# NFR-24's mandatory set is the clause after "applies to", up to the sentence end.
NFR24_LINE_RE = re.compile(r"^.*\bNFR-24\b.*$", re.M)
APPLIES_TO_RE = re.compile(r"applies to\s+([^.]+)\.", re.I)
TABLE_TOKEN_RE = re.compile(r"[a-z][a-z0-9_]*")

#: The one thing that is NOT an open question: a PO ruling that a table stays
#: unpartitioned permanently. OQ-108 forced this distinction into existence and
#: it is worth stating why the obvious alternatives are wrong.
#:
#: `outbound_messages` cannot be both monthly-partitioned and idempotent —
#: PostgreSQL requires the partition key inside every unique constraint, so
#: monthly RANGE puts `created_at` in the idempotency key and a bill re-released
#: next month lands in a different partition and sends the customer a SECOND
#: COPY. The PO ruled on 2026-08-11 that the no-duplicate guarantee wins
#: (CLAUDE.md hard rule 6 over NFR-24's "No exceptions").
#:
#: When that OQ closed, this gate FAILED the line — correctly, by its own logic:
#: a closed question means a parked exception's reason has expired. But this
#: exception's reason did not expire, it was RATIFIED. Two wrong fixes were
#: available and both were refused: deleting the line (which silently drops the
#: table out of the gate's sight, exactly the DEF-031 failure) and re-opening
#: the question (which falsifies the registry to keep a gate quiet). So a ruled
#: exemption gets its own token. It never expires, and it is deliberately NOT
#: an OQ-ID so that reading the file tells you which kind of exception you are
#: looking at.
#:
#: Every other hygiene check still applies to a RULED line: the table must be in
#: NFR-24's set, must not already be partitioned, must be dated, must carry a
#: reason, and must appear once.
RULED = "PO-RULED"

# `PartitionedTable("audit_log", ...)` / `ACTIVE_TABLES: frozenset[str] = frozenset({...})`
REGISTRY_ENTRY_RE = re.compile(r"PartitionedTable\(\s*[\"']([a-z_][a-z0-9_]*)[\"']")
ACTIVE_TABLES_RE = re.compile(r"ACTIVE_TABLES[^=]*=\s*frozenset\(\{([^}]*)\}\)")
QUOTED_RE = re.compile(r"[\"']([a-z_][a-z0-9_]*)[\"']")


# ── the rule: which tables NFR-24 requires ──────────────────────────────────
def nfr24_tables() -> tuple[set[str], str]:
    """The mandatory set, read out of NFR-24. Raises ValueError if unreadable."""
    if not NFR_DOC.is_file():
        raise ValueError(
            f"{common.rel(NFR_DOC)} is missing — NFR-24 is the contract this gate reads"
        )
    for line in NFR24_LINE_RE.findall(common.read_text(NFR_DOC)):
        match = APPLIES_TO_RE.search(line)
        if not match:
            continue
        tables = {
            chunk.strip()
            for chunk in re.split(r",|\band\b", match.group(1))
            if TABLE_TOKEN_RE.fullmatch(chunk.strip())
        }
        if tables:
            return tables, line.strip()
    raise ValueError(
        f"could not parse NFR-24's table list from {common.rel(NFR_DOC)} "
        "(expected a bullet naming NFR-24 with an 'applies to <tables>.' clause)"
    )


# ── the evidence: what the migrations actually create ───────────────────────
def evidence_files() -> list[Path]:
    """Every file that can create or name a table: migrations, models, raw SQL."""
    if not common.BACKEND_DIR.is_dir():
        return []
    files: list[Path] = []
    if common.BACKEND_APPS.is_dir():
        files += sorted(common.BACKEND_APPS.glob("*/migrations/*.py"))
        files += sorted(common.BACKEND_APPS.glob("*/models.py"))
    files += sorted((common.BACKEND_DIR / "db").glob("*.sql"))
    return files


def _create_statements(text: str, table: str) -> list[str]:
    """Each `CREATE TABLE [IF NOT EXISTS] [public.]<table>` statement, to its `;`."""
    pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?" + re.escape(table) + r"\b",
        re.I,
    )
    statements = []
    for match in pattern.finditer(text):
        end = text.find(";", match.end())
        statements.append(text[match.start() : end if end != -1 else match.end() + 4000])
    return statements


def partitioned_ddl(table: str, files: list[Path]) -> str | None:
    """Repo-relative path of the migration creating `table` PARTITIONED, or None."""
    for path in files:
        for statement in _create_statements(common.read_text(path), table):
            if re.search(r"PARTITION\s+BY", statement, re.I):
                return common.rel(path)
    return None


def declared_in(table: str, files: list[Path]) -> str | None:
    """Repo-relative path where `table` is declared at all (landed), or None."""
    db_table_re = re.compile(r"""db_table["'\s:=]+["']""" + re.escape(table) + r"""["']""")
    for path in files:
        text = common.read_text(path)
        if db_table_re.search(text) or _create_statements(text, table):
            return common.rel(path)
    return None


# ── the exceptions ──────────────────────────────────────────────────────────
def load_exceptions() -> tuple[list[tuple[str, str, str, str]], list[str]]:
    """(table, oq_id, added_on, reason) rows, plus malformed-line complaints."""
    rows: list[tuple[str, str, str, str]] = []
    problems: list[str] = []
    if not EXCEPTIONS_FILE.is_file():
        return rows, problems
    for lineno, raw in enumerate(common.read_text(EXCEPTIONS_FILE).splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split(maxsplit=3)
        where = f"{EXCEPTIONS_FILE.name}:{lineno}"
        if len(fields) < 4:
            problems.append(
                f"{where}: expected `<table> <OQ-### | {RULED}> <YYYY-MM-DD> <reason>`, got {line!r}"
            )
            continue
        table, oq_id, added_on, reason = fields
        if oq_id != RULED and not common.OQ_ID_RE.fullmatch(oq_id):
            problems.append(
                f"{where}: {oq_id!r} is neither an OQ-ID nor {RULED!r} — an exception is "
                f"either PARKED behind an open question or RATIFIED by a ruling, and the "
                f"line has to say which"
            )
            continue
        try:
            date.fromisoformat(added_on)
        except ValueError:
            problems.append(
                f"{where}: {added_on!r} is not a YYYY-MM-DD date — an exception must be dated"
            )
            continue
        if not reason.strip():
            problems.append(f"{where}: no reason given — an exception must be attributable")
            continue
        rows.append((table, oq_id, added_on, reason.strip()))
    return rows, problems


def oq_rows_by_id() -> dict[str, str]:
    """OQ-ID -> its whole registry row, for the 'does it name the table' check."""
    rows: dict[str, str] = {}
    if not common.OQ_REGISTRY.is_file():
        return rows
    for line in common.read_text(common.OQ_REGISTRY).splitlines():
        if not line.startswith("| OQ-"):
            continue
        first = line.strip().strip("|").split("|", 1)[0].strip()
        if common.OQ_ID_RE.fullmatch(first):
            rows[first] = line
    return rows


def _age_days(added_on: str) -> int:
    return (date.today() - date.fromisoformat(added_on)).days


# ── core/partitioning.py's two claims ───────────────────────────────────────
def module_claims() -> tuple[set[str] | None, set[str] | None]:
    """(REGISTRY tables, ACTIVE_TABLES) as core/partitioning.py declares them."""
    if not PARTITIONING_MODULE.is_file():
        return None, None
    text = common.read_text(PARTITIONING_MODULE)
    registry = set(REGISTRY_ENTRY_RE.findall(text)) or None
    active_match = ACTIVE_TABLES_RE.search(text)
    active = set(QUOTED_RE.findall(active_match.group(1))) if active_match else None
    return registry, active


def run() -> tuple[str, str]:
    try:
        required, _line = nfr24_tables()
    except ValueError as exc:
        return "FAIL", str(exc)

    files = evidence_files()
    if not files:
        return "SKIP", (
            f"no backend migrations/models exist yet — NFR-24 names {len(required)} table(s) "
            "and none of them can have landed"
        )

    exceptions, problems = load_exceptions()
    by_table: dict[str, tuple[str, str, str, str]] = {}
    for row in exceptions:
        if row[0] in by_table:
            problems.append(f"{row[0]} has more than one exception line — keep one")
        by_table[row[0]] = row
    oq_rows = oq_rows_by_id()
    oq_status = common.oq_status_by_id()

    partitioned: dict[str, str] = {}
    unlanded: list[str] = []
    excused: list[str] = []
    for table in sorted(required):
        ddl = partitioned_ddl(table, files)
        if ddl:
            partitioned[table] = ddl
            continue
        declared = declared_in(table, files)
        entry = by_table.get(table)
        if entry is None:
            if declared is None:
                unlanded.append(table)  # cannot partition a table that does not exist yet
                continue
            # CHECK A — the DEF-031 failure, exactly.
            problems.append(
                f"{table} is in NFR-24's mandatory monthly-partition set but is created "
                f"UNPARTITIONED ({declared} declares it with no `PARTITION BY`), and no "
                f"line in {EXCEPTIONS_FILE.name} accounts for it"
            )
            continue
        excused.append(table)

    # CHECK B — exception hygiene.
    for table, oq_id, added_on, _reason in exceptions:
        where = f"{EXCEPTIONS_FILE.name} entry {table}"
        if table not in required:
            problems.append(
                f"{where}: NFR-24 does not require {table} to be partitioned — remove this line"
            )
            continue
        if table in partitioned:
            problems.append(
                f"{where}: {table} IS partitioned now ({partitioned[table]}) — this exception is "
                "stale and must be deleted in the diff that partitioned it"
            )
            continue
        if oq_id == RULED:
            # A PO RULING, not a parked question. See RULED's own comment.
            continue
        row = oq_rows.get(oq_id)
        if row is None:
            problems.append(
                f"{where}: cites {oq_id}, which is not in 12-governance/01-open-questions.md"
            )
            continue
        status = oq_status.get(oq_id, "")
        if "CLOSED" in status.upper():
            problems.append(
                f"{where}: cites {oq_id}, which is CLOSED — the reason this table may be "
                f"unpartitioned has expired. If the ruling was to PARTITION it, implement "
                f"that and delete this line. If the ruling was that this table stays "
                f"unpartitioned, the exception is no longer parked and must be re-filed as "
                f"{RULED} with the ruling's date and words"
            )
            continue
        if table not in row:
            problems.append(
                f"{where}: {oq_id}'s registry row never names {table} — an exception must cite "
                "the question that is actually holding THIS table up"
            )

    # CHECK C — core/partitioning.py's two claims about itself.
    registry, active = module_claims()
    module = common.rel(PARTITIONING_MODULE)
    if registry is None or active is None:
        problems.append(
            f"{module}: could not read REGISTRY/ACTIVE_TABLES — the partition manager must "
            "declare both, and this gate must be able to tie them out against NFR-24"
        )
    else:
        for table in sorted(required - registry):
            problems.append(
                f"{module}: NFR-24 requires {table} but REGISTRY does not carry it — the "
                "create-ahead job would never mint a partition for it"
            )
        for table in sorted(registry - required):
            problems.append(f"{module}: REGISTRY carries {table}, which NFR-24 does not name")
        for table in sorted(active - set(partitioned)):
            problems.append(
                f"{module}: ACTIVE_TABLES claims {table} has a partitioned parent, but no "
                "migration creates it with PARTITION BY — the job will raise on this host"
            )
        for table in sorted(set(partitioned) - active):
            problems.append(
                f"{module}: {table} is created partitioned ({partitioned[table]}) but is missing "
                "from ACTIVE_TABLES — nothing renews its partitions, so INSERTs fail when the "
                "bootstrapped window runs out (the quiet half of DEF-027)"
            )

    if problems:
        return "FAIL", common.summarize(problems)

    excused_detail = ", ".join(
        f"{t}→{by_table[t][1]} ({_age_days(by_table[t][2])}d)" for t in sorted(excused)
    )
    detail = (
        f"NFR-24: {len(required)} mandatory table(s); {len(partitioned)} partitioned "
        f"({', '.join(sorted(partitioned))})"
    )
    if excused:
        detail += f"; {len(excused)} unpartitioned under live open questions: {excused_detail}"
    if unlanded:
        detail += f"; {len(unlanded)} not landed yet ({', '.join(sorted(unlanded))})"
    return "PASS", detail


def main() -> int:
    """Run this gate from the command line.

    ⚠ ADDED 2026-08-25 (DEF-672). Sixteen gate modules defined `run()` and NO
    main block, so `python3 10-scripts/gates/<gate>.py` imported the module,
    defined a function and exited **0 with no output** — indistinguishable from
    a gate that ran and passed, to the eye and to `$?`. Two commit messages on
    this branch claim a G7 PASS obtained exactly that way.

    `run_gates.py` was never affected: it imports `run()` directly, which is why
    the real stack stayed honest while every direct invocation lied.
    """
    status, message = run()
    print(f"{status}: {message}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
