"""G5 - tenant-isolation suite (B12 r2 / HR-1): cross-tenant access is impossible.

Three halves now, and the THIRD one is why this file grew a second time
(DEF-GOV-4024, 2026-09-05):

  1. RUN IT, ON A DATABASE WHERE THE GUARANTEE CAN EXIST. `pytest -m isolation`
     in 06-backend against **real PostgreSQL**. Red = merge-blocked, no override
     (B8). When no PostgreSQL is reachable the gate SKIPs with an honest detail —
     it must never report PASS for a suite it did not actually run.
  2. READ IT FIRST. A static scan that refuses an UNCONDITIONAL
     `@pytest.mark.skip` on an isolation-marked test.
  3. COUNT THE VENDOR SKIPS AND REFUSE THEM. A case that skipped because the
     database was the wrong kind is a case that did not run, and this gate
     exists to notice that.

WHY HALF 2 EXISTS
------------------
A SKIPPED TEST IS GREEN. Nothing anywhere distinguished a test that ran from a
test that was skipped, so an isolation guarantee could silently not exist while
this gate reported PASS — and one did, for as long as the marks had existed
(DEF-101, 2026-08-15).

Running `-m isolation` against real Postgres that day gave **129 passed, 12
skipped**. The 12 read *"live Postgres must prove a batch cannot reach another
tenant's tariffs…"* — **and they were skipping ON live Postgres.** They were
`@pytest.mark.skip`: unconditional, not the `skipif` the rest of the suite uses.
All 12 were RATING, so the module holding the PRICING tables had **no
cross-tenant read proof on any database**, under a helper module whose own
docstring stated *"No test in this suite is unconditionally skipped."* Hard-won
law 1, inside the file whose entire job is to guarantee tenant isolation.

The 12 were written out and now RUN. This clause is what stops the 13th.

⚠ WHY HALF 3 EXISTS, AND IT IS THE SAME BUG ONE LEVEL UP
---------------------------------------------------------
Half 1 said *run it*, and did not say **where**. So it ran
`pytest -m isolation -q` with no settings override, which picks up the
`DJANGO_SETTINGS_MODULE = "config.settings.test"` pinned in `pyproject.toml`,
which hardcodes **in-memory SQLite** (hard-won law 14). SQLite has no row-level
security, no `FORCE ROW LEVEL SECURITY` and no `BR-AUD-002` append-only trigger,
so every case that needs one of those skips itself with `requires_postgres`.

Measured on this branch on 2026-09-05: **46 passed, 192 skipped, exit 0 — and
the gate reported PASS.** Four fifths of the tenant-isolation suite had not run,
and the gate whose entire subject is tenant isolation called that a pass.

DEF-101 taught that a skipped TEST is green. This is a skipped SUITE being
green, and the docstring above had actually written the cure down —
*"a rise in the skip count is a regression"* — as a sentence, with nothing
reading it. Hard-won law 1 again, in the same file, thirteen days later.

So the skip count is no longer merely PRINTED, it is JUDGED:
  * a skip carrying the vendor reason means the run was on the wrong database
    and the gate FAILs, naming the count;
  * with no PostgreSQL reachable the gate SKIPs and says so — it does not fall
    back to SQLite and call it a pass.

FINDING THE DATABASE, AND WHY A HARDCODED FALLBACK IS SAFE HERE
----------------------------------------------------------------
`SBH_GATE_DATABASE_URL`, then `DATABASE_URL`, then the local development DSN
this repo's own environment uses. There is no CI: every workflow under
`.github/workflows/` is `.disabled`, so a lane running the gate suite on its own
machine is the only enforcement there is, and a gate that demanded an
environment variable nobody sets would simply never run.

DEF-524 is the standing warning about a hardcoded path outliving what it names —
G14's did, and reported PASS through six UI defects. The difference is the
failure direction: if the DSN here stops resolving, this gate **SKIPs**, which
is visible and honest. It cannot pass by being wrong. The candidate is probed
before use and the detail line always names the database that proved the suite,
so nobody has to guess which one did.

⚠ AND POSTGRESQL IS NOT ENOUGH — THE ROLE HAS TO BE SUBJECT TO RLS
-------------------------------------------------------------------
Pointing the suite at PostgreSQL and pointing it at a role that BYPASSES
row-level security are two different things, and the second one looks exactly
like the first from here. **A SUPERUSER bypasses every policy**, so the deny is
never evaluated, every "another tenant cannot see this" case reads its
neighbour's rows, and the suite goes red for a reason that has nothing to do
with the code under test.

Measured on 2026-09-05 against the local development database, whose
`smartbillhub` role is `rolsuper = t`: **36 failed, 201 passed, 1 skipped** in
twenty minutes — and among the 36 is the suite's own canary,
`test_the_role_this_suite_runs_as_is_genuinely_subject_to_rls`. Thirty-six red
tests that say nothing about the product, handed to whichever lane ran the gate
next.

So the probe asks `pg_roles` two questions before anything runs, and a role
holding `rolsuper` or `rolbypassrls` is treated the same as no database at all:
the gate **SKIPs and names the role**, because the environment cannot prove the
guarantee and a lane cannot fix a cluster role from inside a merge.
`10-scripts/13-provision-database.sh` is what builds a role that can — the PO
ruled out granting bypass even for one `migrate` (OQ-354, 2026-08-24), so there
is no flag here that turns this check off.
"""
import ast
import hashlib
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit

import common

TESTS_DIR = common.BACKEND_DIR / "tests"
HELPERS = TESTS_DIR / "isolation_helpers.py"

#: The distinctive opening of `tests/isolation_helpers.py::VENDOR_SKIP_REASON`.
#: A skip line carrying it is a case that did not run because the database was
#: the wrong kind. It is matched as text rather than imported because the gate
#: suite is stdlib-only and must not import Django app code — and because that
#: makes it a string that could silently stop matching, `_vendor_phrase_live()`
#: below asserts it is still the wording the helper uses. A check that cannot
#: fail is worse than no check.
VENDOR_PHRASE = "isolation suite needs live PostgreSQL"

#: The other skip that means "this environment cannot prove it", from the same
#: helper. The RLS probe works by `SET ROLE` into a role that row-level security
#: applies to, which needs that role to exist AND the connection to be a member
#: of it — and granting either needs privileges an ordinary app role does not
#: have. Where it cannot, the case skips saying so, and that is an environment
#: refusal rather than a failure of the code (`DEF-GOV-4036`).
UNPROVEN_PHRASE = "RLS HALF NOT EXERCISED"

#: Where to look for a PostgreSQL to prove the suite on, in order.
DSN_ENV_KEYS = ("SBH_GATE_DATABASE_URL", "DATABASE_URL")

#: Local development fallbacks, tried in order and PROBED rather than assumed.
#: The first is a role that exists to be **subject** to row-level security, which
#: is what this suite needs and what an ordinary development superuser is not.
#: It is not magic and nothing here creates it — on a cluster that lacks it the
#: probe simply refuses it and moves on. To make one (localhost development
#: only; `10-scripts/13-provision-database.sh --create-role` is the production
#: path and deliberately grants no CREATEDB):
#:
#:   CREATE ROLE sbh_gate_iso LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEROLE
#:     NOREPLICATION CREATEDB PASSWORD 'sbh_gate_iso';
#:
#: CREATEDB is there because pytest-django builds its own `test_…` database as
#: the connecting role. It grants no ability to see another tenant's rows, which
#: is the only thing this suite is measuring.
FALLBACK_DSNS = (
    "postgres://sbh_gate_iso:sbh_gate_iso@localhost:5432/sbh_gate",
    "postgres://smartbillhub:smartbillhub@localhost:5432/sbh_dev",
)

#: A dedicated database, named for a digest of every migration file — the
#: pattern `config/settings/test.py` already proves (DEF-GOV-3778).
#:
#: Two things it buys, and the second one is not optional. It cannot collide
#: with a lane running `-m isolation` by hand against the development database.
#: And `--reuse-db` becomes SAFE: on PostgreSQL, unlike sqlite's in-memory
#: database, a reused test database persists across runs and would happily serve
#: a schema three migrations out of date. With the digest in the name, adding a
#: migration simply names a database that does not exist yet, so it is built
#: once and reused until the next migration lands. Nobody has to remember
#: `--create-db`, and nothing can be proved against a stale schema.
#:
#: Without reuse this gate costs every lane several minutes on every run, and a
#: gate too slow to run is a gate that does not run.
#:
#: ⚠ AND IT IS SET THROUGH `SBH_TEST_DB_NAME`, NOT THROUGH THE DSN, BECAUSE THE
#: DSN DOES NOT DECIDE THIS. `config/settings/base.py:616` names the test
#: database `test_sbh_<checkout>_<lane>` (DEF-054 — a worktree does not isolate
#: the database) and Django ignores whatever database the DSN points at when it
#: builds one. A first draft of this file put the digest in the DSN and it did
#: nothing at all: the run built `test_sbh_smartbillhub_12794361`, the drop of
#: superseded databases matched none, and the docstring above would have been a
#: comment claiming a guarantee — hard-won law 1, in the file where this very
#: commit is about law 1. `SBH_TEST_DB_NAME` is the override base.py documents.
GATE_DB_PREFIX = "test_sbh_gate_iso_"


def _migration_digest() -> str:
    files = sorted(common.BACKEND_DIR.glob("apps/*/migrations/*.py"))
    blob = b"".join(f.read_bytes() for f in files)
    return hashlib.sha256(blob).hexdigest()[:16]


def gate_db_name() -> str:
    return f"{GATE_DB_PREFIX}{_migration_digest()}"


def _decorator_name(node: ast.expr) -> str:
    """`@pytest.mark.skip(reason=…)` -> 'pytest.mark.skip'. Call args dropped."""
    if isinstance(node, ast.Call):
        node = node.func
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _test_files() -> list:
    if not common.BACKEND_DIR.is_dir():
        return []
    tests = list(common.BACKEND_DIR.rglob("test_*.py"))
    tests += list(common.BACKEND_DIR.rglob("tests.py"))
    return sorted(tests)


def unconditionally_skipped_isolation_tests() -> list[str]:
    """Every isolation-marked test that also carries a bare `pytest.mark.skip`.

    AST, not text. The first version of this check read a fixed window of lines
    above each `def` and immediately produced a false positive: the window ran
    back over a PRECEDING test's decorator stack and charged one test with
    another's skip mark. A decorator stack has an exact definition and Python
    already knows it, so the check asks Python rather than guessing at
    indentation. `pytest.mark.skipif` is conditional and is the APPROVED form —
    only the bare `skip` counts.
    """
    offenders = []
    if not TESTS_DIR.is_dir():
        return offenders
    for path in sorted(TESTS_DIR.rglob("test_*.py")):
        try:
            tree = ast.parse(common.read_text(path), filename=str(path))
        except SyntaxError as exc:  # a test file that will not parse is its own failure
            offenders.append(f"{common.rel(path)}: cannot parse ({exc})")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            names = {_decorator_name(d) for d in node.decorator_list}
            if "pytest.mark.isolation" in names and "pytest.mark.skip" in names:
                offenders.append(f"{common.rel(path)}:{node.lineno} {node.name}")
    return offenders


def _interpreter_with_pytest() -> tuple[str | None, list[str]]:
    """The first interpreter on this machine that can import BOTH pytest and Django.

    ⚠ **`sys.executable` IS THE WRONG QUESTION AND IT COST THIS GATE ITS WHOLE
    JOB (`DEF-GOV-4441`).** On this machine bare `python3` has neither pytest
    nor Django and `python3.12` has both, so this gate reported **SKIP —
    "pytest is not installed in this interpreter"** while **264 isolation tests
    sat there able to run**. A gate that guards *one utility cannot see
    another's data* reported neither pass nor fail, for weeks, on a
    multi-tenant product about to go live with two customers.

    That is law 7's *incapable of passing* shape, and it is the SECOND time
    this exact mistake was made in this repo: `G120` was written with
    `sys.executable`, announced that the application would not start over a
    branch that boots perfectly, and was corrected the same way. The lesson did
    not travel between two gates written days apart, which is why it is written
    out here rather than referenced.

    Returns the interpreter and what was tried, so a genuine SKIP can say what
    it looked for rather than shrugging.
    """
    # ⚠ **THIS IS NOW ONE LINE, AND THAT IS THE WHOLE POINT — `DEF-GOV-7813`,
    # completing `DEF-GOV-6698` item (c).** What stood here was a LITERAL COPY
    # of the candidate list in `g120_the_application_starts.py`, comment block
    # and all, and `common.interpreter_with()` already existed with the same
    # logic and a docstring saying so: *"the candidate list belongs in
    # gates/common.py as ONE helper — a paragraph in two files is the shape
    # that produced this"*. It was left undone because both files were live
    # under another lane.
    #
    # Leaving it undone cost the fifth occurrence. The copies were widened
    # three times and every widening answered *where would a Python project put
    # its venv?*; none of them found `/root/.venvs/sbh312/bin/python`, which is
    # where THIS machine keeps the only interpreter with pytest and Django. Six
    # gates skipped at once, this one among them — and this one is HARD RULE 1.
    #
    # Now there is one list. Widening it fixes every gate that asks, which is
    # the property two copies can never have.
    return common.interpreter_with("pytest", "django")


def _phrases_live() -> bool:
    """Are both skip phrases still the wording `isolation_helpers.py` uses?

    Half 3 classifies skips by matching text. Reword either reason in the helper
    and the count silently becomes zero and the gate silently starts passing on
    a run that proved nothing — the exact failure this gate was rewritten to
    end. So both phrases are checked against the file that defines them, and a
    miss is reported rather than assumed away.
    """
    if not HELPERS.is_file():
        return False
    text = common.read_text(HELPERS)
    return VENDOR_PHRASE in text and UNPROVEN_PHRASE in text


def _dsn_candidates() -> list[str]:
    seen, out = set(), []
    for key in DSN_ENV_KEYS:
        value = (os.environ.get(key) or "").strip()
        if value.startswith(("postgres://", "postgresql://")) and value not in seen:
            seen.add(value)
            out.append(value)
    for dsn in FALLBACK_DSNS:
        if dsn not in seen:
            seen.add(dsn)
            out.append(dsn)
    return out


def _usable(dsn: str) -> tuple[bool, str]:
    """Can this DSN prove tenant isolation? `(True, role)` or `(False, why not)`.

    Two questions, and the second is the one that was missing. The DSN's own
    database need not exist — Django builds `test_<name>` through the
    maintenance database — so the probe asks for `postgres`. Then it asks
    `pg_roles` whether the role it just connected as is actually subject to
    row-level security, because a SUPERUSER is not, and a suite run as one is
    36 red tests about nothing.

    Without psycopg a plain socket proves only that something is listening. The
    role cannot be checked at all then, so that path says so rather than
    claiming a database it cannot vouch for.
    """
    parts = urlsplit(dsn)
    host, port = parts.hostname or "localhost", parts.port or 5432
    try:
        import psycopg  # noqa: PLC0415 - optional, and only ever a better probe
    except ImportError:
        try:
            with socket.create_connection((host, port), timeout=3):
                return False, (f"something is listening on {host}:{port} but psycopg is not "
                               f"installed here, so this gate cannot check whether the role "
                               f"bypasses row-level security — and a run as a bypassing role "
                               f"proves nothing")
        except OSError:
            return False, f"nothing is listening on {host}:{port}"
    try:
        with psycopg.connect(parts._replace(path="/postgres").geturl(),
                             connect_timeout=3) as conn:
            row = conn.execute(
                "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles "
                "WHERE rolname = current_user"
            ).fetchone()
    except Exception as exc:
        return False, f"cannot open a session on {host}:{port} ({type(exc).__name__})"
    if row is None:
        return False, f"{host}:{port} would not say whether the connecting role bypasses RLS"
    role, is_super, bypasses = row
    if is_super or bypasses:
        held = " and ".join(w for w, on in (("SUPERUSER", is_super), ("BYPASSRLS", bypasses)) if on)
        return False, (f"the role {role!r} on {host}:{port} holds {held}, so row-level security "
                       f"is never evaluated for it and the suite would go red for a reason that "
                       f"is not the code (36 failed, 201 passed, 1 skipped when this was measured "
                       f"on 2026-09-05). Provision a NOSUPERUSER NOBYPASSRLS role with "
                       f"10-scripts/13-provision-database.sh and point SBH_GATE_DATABASE_URL at it")
    return True, str(role)


def _clean(dsn: str) -> str:
    """The candidate DSN with any query string dropped.

    The DSN's own database is left exactly as given: Django never runs the suite
    against it. It creates and uses `SBH_TEST_DB_NAME`, and it reaches that
    through the maintenance database, so what this points at only has to be
    connectable.
    """
    return urlsplit(dsn)._replace(query="", fragment="").geturl()


def _drop_superseded(dsn: str, keep: str) -> None:
    """Remove this gate's own test databases from earlier migration digests.

    A digest in the name is what makes `--reuse-db` safe, and its cost is that
    every migration that lands leaves a database behind. They are this gate's
    own, named by its own prefix, and nothing else reads them. A drop refused
    because another run still holds a connection is not an error worth having —
    the next run will collect it.
    """
    try:
        import psycopg  # noqa: PLC0415
    except ImportError:
        return
    try:
        with psycopg.connect(urlsplit(dsn)._replace(path="/postgres", query="", fragment="").geturl(),
                             connect_timeout=3, autocommit=True) as conn:
            rows = conn.execute(
                "SELECT datname FROM pg_database WHERE datname LIKE %s", (f"{GATE_DB_PREFIX}%",)
            ).fetchall()
            for (name,) in rows:
                if name == keep:
                    continue
                try:
                    conn.execute(f'DROP DATABASE "{name}"')
                except Exception:
                    pass  # in use by a concurrent run; the next run collects it
    except Exception:
        return


#: Where a proof is recorded once it has been made.
#:
#: ⚠ THE GATE READS THIS RATHER THAN RUNNING THE SUITE, AND THAT IS A DELIBERATE
#: TRADE MADE WITH ITS COST IN VIEW. Running `-m isolation` on real PostgreSQL
#: takes about **fourteen minutes** with the test database reused and twenty
#: without. `run_gates.py` is what a lane runs before every merge, several times
#: an hour, on a machine carrying eight of them — and a gate that costs a
#: quarter of an hour is a gate lanes stop running. That is not a smaller
#: version of the problem this file was rewritten for (`DEF-GOV-4024`), it is
#: the same problem: a check nobody runs and a check that cannot fail are worth
#: the same.
#:
#: So the proof is an EXPLICIT ACT with a durable record — `10-scripts/prove_isolation.py`
#: runs the suite and writes what happened — and the gate's job is to say
#: whether a current one exists. The receipt names the migration digest it was
#: taken against, so a proof cannot outlive the schema it proved: add a
#: migration and the receipt is stale by definition, the gate says so, and
#: nobody has to remember.
#:
#: This is the shape `G12` already uses for the browser suite, for the same
#: reason, and its weakness is the same one: a receipt is written by whoever ran
#: the thing. It is a record, not an attestation. What it CANNOT do is report a
#: pass over a suite that never ran, which is the failure that was actually live.
RECEIPT = common.REPO_ROOT / "12-governance" / "isolation-receipt.json"


def read_receipt() -> dict | None:
    try:
        return json.loads(common.read_text(RECEIPT))
    except (OSError, ValueError):
        return None


def errored_cases(receipt: dict) -> list[str]:
    """The recorded cases that ERRORED, split back out of `failing_cases`.

    ⚠ **AN ERROR IS NOT A FAILURE AND MUST NOT BE REPORTED AS ONE
    (`DEF-SHL-6714`, 2026-09-25).** A case that dies in a FIXTURE is reported by
    pytest as an ERROR: it is in no FAILED list, and its count appears only as a
    separate word in the very last line of the run. On PostgreSQL one failed
    statement poisons the whole transaction (CLAUDE.md law 14), so a single
    broken fixture turns a whole file into a double-figure error count.

    On 2026-09-25 that count was **16**, and **fourteen of them were one file** —
    `tests/test_us_shl_003_search_isolation.py`, the only proof in this repo
    that a search inside one utility cannot return another utility's accounts,
    assets, contacts, customers, invoices, payments, premises, service requests
    or units. It had never run at all. Three lanes read that run and reported
    *"no leaks"*, truthfully, about everything they could see — hard-won law 7's
    *reporting zero over a scope it silently excludes*.

    A FAILURE says the guarantee is broken. An ERROR says **nobody knows**, and
    those are different news that were being printed as one sentence.
    """
    return [ln for ln in (receipt.get("failing_cases") or []) if ln.startswith("ERROR")]


def _first_few(cases: list[str], limit: int = 6) -> str:
    """Name them, and SAY how many were not named rather than trailing off."""
    shown = "; ".join(cases[:limit])
    rest = len(cases) - limit
    return f"{shown} (and {rest} more)" if rest > 0 else shown


def _counts(tail: str) -> dict[str, int]:
    """`46 passed, 192 skipped in 3.10s` -> {'passed': 46, 'skipped': 192}."""
    return {word: int(n) for n, word in re.findall(r"(\d+) (passed|failed|skipped|errors?)", tail)}


def run() -> tuple[str, str]:
    tests = _test_files()
    if not tests:
        return "SKIP", "no backend tests exist yet — activates with the first tenant-scoped endpoint"

    # ── half 2 first: a static read is free and says something a run cannot ──
    offenders = unconditionally_skipped_isolation_tests()
    if offenders:
        return "FAIL", (
            f"{len(offenders)} isolation-marked test(s) carry an UNCONDITIONAL "
            f"pytest.mark.skip — a skipped test is GREEN, so this is a tenant-isolation "
            f"guarantee that is advertised and not performed (DEF-101). Use "
            f"`requires_postgres` from tests/isolation_helpers.py. "
            + common.summarize(offenders)
        )

    if not _phrases_live():
        return "FAIL", (
            f"tests/isolation_helpers.py no longer contains both phrases this gate classifies "
            f"skips by ({VENDOR_PHRASE!r}, {UNPROVEN_PHRASE!r}). Half 3 would report zero "
            f"skips whatever the run did, which is how DEF-GOV-4024 passed on SQLite for "
            f"weeks. Update them in this file to match the helper's wording."
        )

    python, tried = _interpreter_with_pytest()
    if python is None:
        return "SKIP", (
            f"no interpreter on this machine can import both pytest and Django, so the "
            f"isolation suite cannot be run at all. Tried: {', '.join(tried)}. "
            f"({len(tests)} backend test file(s) present.) ⚠ This is the ONLY honest skip "
            f"for this gate — it used to skip whenever the RUNNER's own interpreter lacked "
            f"pytest, which reported nothing over 264 runnable isolation tests (DEF-GOV-4441)."
        )

    # ── half 1: is there a CURRENT proof, taken on a database where the
    #    guarantee can exist? The run itself is prove_isolation.py's job. ──
    digest = _migration_digest()
    receipt = read_receipt()
    if receipt is None:
        return "SKIP", (
            "no isolation proof has been recorded. The suite is NOT run on sqlite and called a "
            "pass: sqlite has no row-level security, so four fifths of it skips itself "
            "(46 passed, 192 skipped on 2026-09-05 — DEF-GOV-4024). Take a proof with "
            "`10-scripts/prove_isolation.py`, which needs a NOSUPERUSER NOBYPASSRLS role that "
            "is a member of sbh_rls_probe. 0 isolation-marked tests are unconditionally skipped."
        )
    if receipt.get("migration_digest") != digest:
        # ⚠ ON A BUSY BRANCH THIS IS THE NORMAL STATE, AND THAT IS THE INTENDED
        # POSTURE RATHER THAN A FAULT (decided 2026-09-05, after the first real
        # proof went stale mid-run — a sibling landed `tenancy/0040` during the
        # twenty minutes the suite took, which is exactly when a proof SHOULD be
        # invalidated).
        #
        # The alternative was to invalidate more narrowly: digest only the
        # migrations that can move the policy surface, and let the rest through.
        # That was refused. Deciding mechanically that a migration "cannot
        # affect isolation" is a judgment made in a regex, and a wrong one keeps
        # a dead proof alive silently — the check-that-cannot-fail shape this
        # very gate exists because of (`DEF-GOV-4024`). A conservative digest is
        # occasionally annoying; a clever one is occasionally a lie.
        #
        # So the proof is a WAVE-CLOSE artefact, like `G12`'s browser run: taken
        # when a wave is finished, not maintained continuously against a branch
        # eight lanes are landing migrations on. In between, this gate says what
        # is true — that no current proof exists — and says it in five seconds.
        # ⚠ **A STALE GREEN AND A STALE RED ARE NOT THE SAME THING, AND THIS
        # MESSAGE USED TO SAY THEM IDENTICALLY (`DEF-GOV-4408`, 2026-09-07).**
        # The verdict stays SKIP — a proof taken against another schema says
        # nothing about this one, in EITHER direction, so FAIL would be a claim
        # this gate cannot make. But the two states carry very different news:
        # a stale green means *we do not know*, while a stale red means *the
        # last time anybody looked, N tenant-isolation tests failed, and
        # nothing since can have fixed them except by accident.* That is hard
        # rule 1 — RLS FORCE, no cross-tenant queryset.
        # The failure count used to sit mid-sentence inside the pytest summary
        # line, behind the word STALE, in a suite with thirty-odd other red
        # lines in it. A check's output must distinguish pass from fail TO A
        # READER, not merely to an exit code (`DEF-182`), so when the stale
        # proof recorded failures the message now LEADS with them.
        stale_failed = int(receipt.get("failed", 0) or 0) + int(receipt.get("errors", 0) or 0)
        verdict = (
            f"⚠ AND IT WAS RED WHEN IT WAS TAKEN — {stale_failed} isolation test(s) failed. "
            "A stale red is not a stale green: nothing since can have fixed them except by "
            "accident, and this is hard rule 1. "
            if stale_failed
            else "It was green when it was taken. "
        )
        return "SKIP", (
            f"the recorded isolation proof is STALE — it was taken against migrations "
            f"{str(receipt.get('migration_digest'))[:12]}… and the tree is now {digest[:12]}…, so it "
            f"says nothing about this schema. {verdict}"
            f"It read {receipt.get('summary', 'no summary')} on "
            f"{receipt.get('taken_on', 'an unrecorded date')} as {receipt.get('role', 'an unrecorded role')}. "
            f"Staleness is expected while a branch is taking migrations: the proof is a WAVE-CLOSE act, "
            f"not a continuous one. Re-take it with `10-scripts/prove_isolation.py` (about 20 minutes)."
        )
    failed = int(receipt.get("failed", 0) or 0)
    errors = int(receipt.get("errors", 0) or 0)
    skipped = int(receipt.get("skipped", 0))
    role = receipt.get("role", "an unrecorded role")
    when = receipt.get("taken_on", "an unrecorded date")
    # ⚠ **ERRORS ARE ANSWERED BEFORE FAILURES AND IN THEIR OWN SENTENCE
    # (`DEF-SHL-6714`).** This gate already ADDED the two counts together, so an
    # errored proof was never read past — but it said the word *failed* for
    # both, and a reader learned only that some red existed. See
    # `errored_cases()` above for what that cost on 2026-09-25.
    if errors:
        named = errored_cases(receipt)
        which = (_first_few(named) if named else
                 "the receipt names none of them — it predates DEF-GOV-6704's "
                 "short-summary capture; re-take the proof")
        return "FAIL", (
            f"{errors} isolation case(s) ERRORED in the proof taken on {when} as {role} — an "
            f"error is a case that NEVER RAN. It appears in no FAILED list, and on PostgreSQL "
            f"one poisoned transaction takes every later case in its file with it (law 14), so "
            f"one broken fixture reads as a double-figure count. Nothing at all is known about "
            f"what these were written to prove: {which}. {receipt.get('summary', '')}"
        )
    if failed:
        return "FAIL", (
            f"the isolation proof taken on {when} as {role} reports "
            f"{receipt.get('summary', f'{failed} failed')}"
            + (" — " + "; ".join(receipt.get("failing_cases") or [])
               if receipt.get("failing_cases")
               else " — AND THE RECEIPT NAMES NO CASE, so there is nothing to trace: it was taken "
                    "before the receipt recorded pytest's short test summary (DEF-GOV-6704). "
                    "Re-take it")
            + f". Tenant isolation is hard rule 1 and it "
            f"is not holding on every case. Re-run with `10-scripts/prove_isolation.py` after a fix."
        )
    if skipped:
        return "FAIL", (
            f"{skipped} isolation case(s) SKIPPED in the proof taken on {when} as {role} — a skip "
            f"is a case that did not run, and on a database where the guarantee can exist the "
            f"standing figure is 0. {receipt.get('summary', '')}"
        )
    return "PASS", (
        f"isolation proved on {when} as {role}, a role genuinely subject to RLS, against these "
        f"exact migrations: {receipt.get('summary', 'no summary')} (0 skipped, 0 unconditional "
        f"skips on isolation tests)"
    )


def prove() -> tuple[str, str]:
    """Run the suite for real and return `(status, detail, receipt | None)`.

    Only `10-scripts/prove_isolation.py` calls this. `run()` above never does —
    it reads the receipt this produces. The receipt is None wherever no run
    happened, so a refusal can never be recorded as a proof.
    """
    reachable, refusals = None, []
    for candidate in _dsn_candidates():
        ok, detail = _usable(candidate)
        if ok:
            reachable, role = candidate, detail
            break
        refusals.append(detail)
    if reachable is None:
        return "SKIP", (
            "no database that could prove tenant isolation was found, so the suite is NOT run "
            "on sqlite and called a pass: sqlite has no row-level security, so four fifths of "
            "the suite skips itself (46 passed, 192 skipped on 2026-09-05 — DEF-GOV-4024). "
            "0 isolation-marked tests are unconditionally skipped. "
            + common.summarize(refusals)
        ), None

    name = gate_db_name()
    dsn = _clean(reachable)
    _drop_superseded(reachable, name)
    where = urlsplit(dsn).hostname or "localhost"
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.local",
        "DATABASE_URL": dsn,
        # base.py:616 decides the test database name; this is its documented
        # override, and without it the digest above is decoration.
        "SBH_TEST_DB_NAME": name,
        # law 14's footnote: JOBS_EAGER is True under `local`, and a dispatched
        # job running inline breaks cases that assert on a queued one.
        "JOBS_EAGER": "false",
    }
    # ⚠ `prove()` IS ITS OWN ENTRY POINT and resolves its own interpreter.
    # `run()` resolving one for itself does NOT help here — I made exactly that
    # mistake fixing `DEF-GOV-4441` and `prove_isolation.py` died on
    # `NameError: name 'python' is not defined`, caught by running it rather
    # than by reading the diff.
    python, _tried = _interpreter_with_pytest()
    if python is None:
        python = sys.executable
    # `-rfEs`, not `-rs`: the receipt must NAME a failing case. The 2026-09-07
    # receipt said *"1 failed"* and named nothing, so nobody could say whether
    # that case was still failing, and it went unanswered for eighteen days.
    # A count with no name is not traceable to anything.
    pt = subprocess.run([python, "-m", "pytest", "-m", "isolation", "-q", "-rfEs",
                         "--reuse-db", "-p", "no:randomly"],
                        capture_output=True, text=True, cwd=common.BACKEND_DIR, env=env)
    out = pt.stdout.strip()
    tail = out.splitlines()[-1] if out else "no output"
    if pt.returncode == 5:  # pytest: no tests collected
        return "PASS", "no isolation-marked tests collected yet", None
    lines = out.splitlines()
    unproven = [ln for ln in lines if ln.startswith("SKIPPED") and UNPROVEN_PHRASE in ln]
    if unproven:
        # Before any verdict on the code: this environment could not put the
        # probe in place, so the RLS half never ran and the failures that follow
        # from it are about the cluster, not the product (DEF-GOV-4036).
        return "SKIP", (
            f"{len(unproven)} case(s) report {UNPROVEN_PHRASE!r}: the probe role could not be "
            f"put in place on {where}, so the row-level-security half never ran and nothing "
            f"here is a verdict on the code. The connecting role needs the probe role to exist "
            f"and to be a MEMBER of it — an administrator does it once: "
            f"CREATE ROLE sbh_rls_probe NOLOGIN NOSUPERUSER NOBYPASSRLS; "
            f"GRANT sbh_rls_probe TO <app role> WITH ADMIN OPTION. {tail}"
        ), None

    # ── DID THE RUN HAPPEN AT ALL? (DEF-GOV-6704) ──────────────────────────
    # A container that kills lanes mid-run — this one restarted three times in
    # a few hours on 2026-09-25 — turns an interrupted proof into a GREEN LIE,
    # on hard rule 1, which is the guarantee this whole product rests on.
    # Reproduced before it was fixed: start this, `kill -9` the child pytest a
    # minute later, and the old code wrote `"summary": "no output"` with
    # `passed 0, failed 0, skipped 0`, DATED TODAY and at the CURRENT migration
    # digest, over a real 272-passed receipt. `run()` then read 0 failures and
    # 0 skips and answered, verbatim:
    #     PASS: isolation proved on 2026-09-25 09:30 UTC ... : no output
    # So a killed run did not merely fail to prove anything — it DESTROYED the
    # last real proof and reported the destruction as a pass.
    #
    # The cure is the refusal this module already makes when no database is
    # found: return the reason with NO receipt, and `prove_isolation.py` leaves
    # the old one exactly as it was. Its own docstring already promised this —
    # *"a proof that did not happen must not overwrite one that did"* — and the
    # promise simply did not cover interruption (hard-won law 1: a comment
    # claiming a guarantee is not the guarantee).
    #
    # TWO TESTS, AND THEY CATCH DIFFERENT KILLS:
    #   * empty counts — a SIGKILLed pytest prints NOTHING, so the tail is
    #     `no output` and `_counts()` is `{}`. That is the reproduced case.
    #   * a return code that is not a pytest VERDICT. pytest answers 0 (all
    #     passed), 1 (tests failed) and 5 (nothing collected) as verdicts; 2 is
    #     INTERRUPTED, 3 internal error, 4 usage, and a signal arrives negative
    #     or above 128. An interrupt is the dangerous one, because pytest may
    #     still print a partial summary line with real counts — `40 passed` and
    #     no failures reads exactly like a proof, and it is a third of a suite.
    #
    # WHAT WOULD MAKE THIS PASS WRONGLY: a run that finishes properly and
    # genuinely proves nothing. `returncode 5` is answered above as PASS with
    # no receipt at all, and a finished run with `0 passed` is refused below
    # for the same reason a `no output` run is — a proof with nothing proved in
    # it is not a record worth overwriting a real one with.
    counts = _counts(tail)
    verdict_codes = (0, 1, 5)
    if not counts or pt.returncode not in verdict_codes or counts.get("passed", 0) == 0:
        why = ("printed no test counts at all" if not counts
               else f"exited {pt.returncode}, which is not a pytest verdict (0, 1 or 5)"
               if pt.returncode not in verdict_codes
               else "finished with 0 passing cases")
        return ("FAIL", (
            f"the isolation run on PostgreSQL ({where}, {name}) {why}, so it proved nothing and "
            f"NOTHING IS RECORDED — the receipt of the last real proof is left exactly as it was "
            f"(DEF-GOV-6704). A run killed mid-flight used to write a receipt saying 0 passed, "
            f"0 failed, 0 skipped, dated today and at today's migration digest, and this gate read "
            f"that as a PASS. Re-run it when the machine will survive ninety minutes. "
            f"Last line of the run: {tail!r}"),
            None,
        )

    # ── the run happened; whatever it says is recordable ──
    # `failing_cases` is why the receipt is worth reading a fortnight later: a
    # bare *"1 failed"* names nothing and traces to nothing.
    failing_cases = [ln.strip() for ln in lines
                     if ln.startswith(("FAILED", "ERROR"))]
    receipt = {
        "failing_cases": failing_cases,
        "migration_digest": _migration_digest(),
        "taken_on": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "role": role,
        "database": f"{where}, {name}",
        "summary": tail,
        "passed": counts.get("passed", 0),
        "failed": counts.get("failed", 0),
        "errors": counts.get("errors", counts.get("error", 0)),
        "skipped": counts.get("skipped", 0),
        "vendor_skips": len([ln for ln in lines
                             if ln.startswith("SKIPPED") and VENDOR_PHRASE in ln]),
    }
    errored = [ln for ln in failing_cases if ln.startswith("ERROR")]
    if errored:
        # Said separately and FIRST, for the reason `errored_cases()` gives: a
        # run reported as "failed: 8 failed, 273 passed, 1 skipped, 16 errors"
        # reads as a run with some red in it, and it is a run with fourteen
        # cross-tenant search cases that never executed.
        return "FAIL", (
            f"{len(errored)} isolation case(s) ERRORED on PostgreSQL ({where}, {name}) — an error "
            f"is a case that NEVER RAN, it is in no FAILED list, and one poisoned transaction "
            f"takes every later case in its file with it (law 14). Nothing is known about what "
            f"these prove: {_first_few(errored)}. {tail}"
        ), receipt
    if pt.returncode != 0:
        return "FAIL", f"pytest -m isolation on PostgreSQL ({where}, {name}) failed: {tail}", receipt

    # ── half 3: a skip is a case that did not run ──
    vendor = [ln.strip() for ln in lines if ln.startswith("SKIPPED") and VENDOR_PHRASE in ln]
    if vendor:
        return "FAIL", (
            f"{len(vendor)} isolation case(s) skipped with the VENDOR reason while the run was "
            f"pointed at PostgreSQL ({where}, {name}) — a vendor skip means the case did not "
            f"run, so the guarantee is advertised and not performed (DEF-GOV-4024). {tail}"
        ), receipt
    skipped = counts.get("skipped", 0)
    if skipped:
        return "FAIL", (
            f"{skipped} isolation case(s) skipped on PostgreSQL ({where}, {name}) for a reason "
            f"other than the database vendor. On PostgreSQL the whole suite runs — the standing "
            f"figure is 0 skipped — so a skip here is a case that stopped being proved. {tail}"
        ), receipt
    return ("PASS",
            f"pytest -m isolation on PostgreSQL ({where}, {name}) as {role}, a role genuinely "
            f"subject to RLS: {tail} (0 skipped, 0 unconditional skips)",
            receipt)


def main() -> int:
    """Run this gate from the command line.

    ⚠ ADDED 2026-08-25 (DEF-672). Sixteen gate modules defined `run()` and NO
    main block, so `python3 10-scripts/gates/<gate>.py` imported the module,
    defined a function and exited **0 with no output** — indistinguishable from
    a gate that ran and passed, to the eye and to `$?`. Two commit messages on
    this branch claim a G7 PASS obtained exactly that way.

    `run_gates.py` was never affected: it imports `run()` directly, which is why
    the real stack stayed honest while every direct invocation lied.

    ⚠ AND A RED PROOF OBTAINED THROUGH HERE IS NOT A PROOF OF THE THING THAT
    MATTERS (DEF-GOV-3733, 2026-09-04). Two gates were shown red and then green
    this way while the suite was reporting `gate crashed` on both. Prove a
    change to this file through `run_gates.py`, which is the harness that will
    run it.
    """
    status, message = run()
    print(f"{status}: {message}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
