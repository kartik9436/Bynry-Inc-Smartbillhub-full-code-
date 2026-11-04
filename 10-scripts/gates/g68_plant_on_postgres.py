#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2395 (2026-09-01) — CLAUDE.md law 14 REQUIRES transaction-
#           sensitive code to be proved on real PostgreSQL, and on 2026-09-01
#           three lanes discovered independently that they could not get a
#           seeded tenant to prove anything ON. The row's prevention column
#           asks for this gate in its own words: *"a check that provisions one
#           tenant on PostgreSQL, so the day this breaks again it is a red gate
#           rather than three lanes each losing an hour to it."*
#           DEF-2722 (2026-08-31) — *"NO TEST PROVISIONS A TENANT AND THEN
#           ASSERTS THE SAMPLE PLANT IS COMPLETE."*
#           DEF-566  (2026-08-22) — the write-nothing identity stub underneath
#           both of them.
# Rules:    CLAUDE.md law 14 (config/settings/test.py hardcodes in-memory
#           SQLite, which has no aborted-transaction state) · law 7 (prove a
#           guard RED first) · law 2 (built is not wired) · BR-TEN-001 ·
#           BR-TEN-063
# ───────────────────────────────────────────────────────
"""G68 — a tenant can be provisioned and seeded, and SQLite does not count.

WHAT THIS GATE IS FOR, AND IT IS NOT THE OBVIOUS HALF
=====================================================
The obvious half is "run the sample-plant test". That is one subprocess and it
is the easy part.

**The half this gate exists for is refusing to report PASS for a run that
happened on SQLite.** DEF-2395 is not a defect about seeding; it is a defect
about a PROOF STANDARD that could not be met and did not say so. Its own words:

    *"a lane that obeys law 14 cannot get a fixture, and a lane that gives up
    and uses SQLite has proved nothing about the case the law exists for …
    Nothing could catch it: no gate asserts that a developer can seed a tenant
    on the database the law names."*

A gate that ran the test on whatever database happened to be configured and
printed PASS would be the thing DEF-2395 complains about, wearing a green
badge. So this one reports three different states and they mean three different
things:

  * **PASS**  — the plant test ran on PostgreSQL and every block seeded. This
    is the only outcome that is a law-14-grade statement.
  * **SKIP**  — no PostgreSQL is reachable. The detail says so in those words
    and names what would make it runnable. A SKIP is not a pass; `run_gates`
    prints the skip count beside the pass count for exactly this reason (G5's
    docstring is the precedent, and DEF-101 is what happens when nobody reads
    it as a number that matters).
  * **FAIL**  — PostgreSQL was reachable and the plant did not land complete.

⚠ **A SQLITE RUN IS A SKIP, NOT A PASS, EVEN THOUGH THE TEST PASSES ON
SQLITE.** The test really does run there and really does prove the wiring, and
that is worth having — it is simply not the thing this gate is asked to
certify. Reporting it as PASS would restate the confusion the defect is about.

HOW IT DECIDES THERE IS A POSTGRESQL
------------------------------------
`DATABASE_URL` naming a `postgres`/`postgresql` scheme, and a
`DJANGO_SETTINGS_MODULE` that does not throw the URL away. Law 14 names the
file that throws it away: `config/settings/test.py` replaces `DATABASES`
wholesale, so the URL applies only under `config.settings.local`. Checking the
URL alone would let a `config.settings.test` run masquerade as a PostgreSQL
one, which is the same class of mistake one level down.

PROVED RED BEFORE IT WAS TRUSTED GREEN (law 7)
----------------------------------------------
Four ways, on 2026-09-01/02, PostgreSQL 16.13, each output quoted rather than
described:

  1. GREEN, so the red proofs mean something:
     `PASS — one tenant provisioned on real PostgreSQL and all 17 sample-plant
     blocks seeded (3 passed, 4 warnings in 437.58s)`.
  2. RED. DEF-566's stub restored in `tests/test_us_ten_helpers.py` —
     `owner_id = uuid.uuid4()` in place of the delegation — and the gate went
     `FAIL … (1 failed, 2 passed, 4 warnings, 1 error in 288.72s)`.
     ⚠ **READ THAT 2-PASSED, BECAUSE IT IS THE DESIGN AND NOT A WEAKNESS.** Two
     of the three cases take `db` alone and never touch the harness, so the
     REAL `provision_owner` runs for them and they are right to pass; the case
     that caught the stub is the one that deliberately provisions THROUGH the
     harness. A guard built only the first way would have been green on the
     exact defect this row is about.
  3. SKIP. `DATABASE_URL` unset — detail names PostgreSQL and prints the
     command that would make it runnable.
  4. SKIP. `DJANGO_SETTINGS_MODULE=config.settings.test` with a PostgreSQL
     `DATABASE_URL` present, because that settings module discards the URL.
     This is case 3's mirror and it is the one a lane would hit by accident.

The measurement the whole thing rests on, also 2026-09-01: with the stub in
place a harness tenant planted **16 of 17 blocks — 1 failed, 0 skipped** — and
the failing line was `identity seed_sample_records`, refusing with *"no sample
staff user was created: this tenant has no ACTIVE System Admin"*. With the seam
real it is **17 of 17**.

⚠ **EVERY `17` ABOVE IS A MEASUREMENT OF 2026-09-01 AND THE ESTATE IS EIGHTEEN
(`DEF-3509`, 2026-09-03).** The numbers are left standing because they are
what was measured on the day, and the red proofs mean nothing if their
figures are edited afterwards. What is NOT left standing is the count in
the PASS sentence this gate prints: that one is read from the catalogue
now, because a success message cannot go red and had been reporting
seventeen at a tenant that got eighteen.

WHY IT SHELLS OUT INSTEAD OF IMPORTING DJANGO
---------------------------------------------
`run_gates.py` is Python 3.12 stdlib only and every other gate is a static
read; importing Django into the gate process would make one gate's failure a
crash for the suite. A subprocess keeps the blast radius at this row.
"""

import os
import subprocess
import sys
from urllib.parse import urlparse

import common

#: The test this gate runs. It lives in the suite (so a developer runs it the
#: ordinary way) rather than inside this file, because DEF-2722 asked for a
#: TEST and a gate that hid the assertion would leave the suite still unable to
#: answer the question on its own.
PLANT_TEST = "tests/test_def2395_sample_plant_on_postgres.py"

#: The settings modules under which `DATABASE_URL` is actually honoured. Law 14
#: names `config/settings/test.py` as the one that is not: it *"REPLACES
#: `DATABASES` WHOLESALE, SO IT IGNORES `DATABASE_URL`"*, in that file's own
#: words.
URL_HONOURING_SETTINGS = ("config.settings.local", "config.settings.production")

#: Provisioning a tenant and planting the whole catalogue is real work — it
#: measured about eight minutes on a shared container on 2026-09-01 at
#: seventeen blocks, and building the test database from scratch adds
#: roughly four more on top. Re-measured 2026-09-03 at eighteen blocks:
#: about three minutes against a warm --reuse-db, so the ceiling is
#: generous rather than tight and does not move with the estate.
TIMEOUT_SECONDS = 45 * 60

#: The module holding the block catalogue, and the name of the tuple in it.
#: Read as TEXT rather than imported, for the reason the docstring above gives:
#: importing Django into the gate process would make one gate's failure a crash
#: for the whole suite.
SAMPLE_DATA_SOURCE = "06-backend/apps/tenancy/sample_data.py"

#: The line the catalogue tuple opens on. The count is taken BETWEEN this and
#: the tuple's closing `\n)\n`, so a `SampleModule` mentioned in a type hint or
#: a docstring elsewhere in that 2,300-line module cannot inflate it.
TUPLE_OPENS = "SAMPLE_MODULES: tuple[SampleModule, ...] = ("


def _expected_blocks() -> str:
    """How many blocks the catalogue declares, for the PASS sentence.

    ⚠ `DEF-3509` — THIS USED TO BE THE LITERAL `17` INSIDE A SUCCESS MESSAGE.
    The estate became eighteen on 2026-09-02 and a PASS line cannot go red, so
    the gate went on reporting a number that was no longer true. Counting the
    `SampleModule(` constructor calls is the same instrument
    `provisioningSteps.test.ts` uses on the same tuple, and for the same reason:
    a check that carries its own copy of the answer agrees only with itself.

    Returns a STRING, and falls back to "every" rather than to a number: this
    is a sentence, and a gate that could not read its own authority should say
    less rather than guess.

    ⚠ IT COUNTS ONLY WHAT IS INSIDE THE TUPLE, and the first draft did not —
    it counted every `SampleModule(` in the file and then subtracted one for a
    class definition that is spelled `class SampleModule:` with no parenthesis
    at all. The subtraction was wrong and the answer came back 17 for an estate
    of 18, which is the very defect this helper exists to end, reproduced inside
    the fix for it. Slice the tuple first, then count.
    """
    try:
        source = (common.REPO_ROOT / SAMPLE_DATA_SOURCE).read_text(encoding="utf-8")
    except OSError:
        return "every"
    start = source.find(TUPLE_OPENS)
    if start == -1:
        return "every"
    end = source.find("\n)\n", start)
    if end == -1:
        return "every"
    count = source.count("SampleModule(", start, end)
    return str(count) if count > 1 else "every"


def _postgres_reason() -> str | None:
    """Why this cannot be a PostgreSQL run, or None when it can.

    Returns the SKIP detail rather than a bool so the caller never has to
    reconstruct which of the two conditions was missing — a gate that says
    "skipped" without saying what would un-skip it is a gate nobody ever turns
    on.
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "").strip()

    if not url:
        return (
            "DATABASE_URL is unset, so there is no PostgreSQL to prove anything on. "
            "This gate is DEF-2395's own prevention and it deliberately does NOT "
            "report PASS for a SQLite run: law 14 exists because SQLite has no "
            "aborted-transaction state, so a green run there is not the proof. "
            "Runnable with: DATABASE_URL=postgres://... "
            "DJANGO_SETTINGS_MODULE=config.settings.local"
        )

    scheme = (urlparse(url).scheme or "").split("+")[0].lower()
    if scheme not in ("postgres", "postgresql"):
        return (
            f"DATABASE_URL names a {scheme or 'schemeless'} database, not PostgreSQL. "
            "Law 14's proof requirement is specifically about PostgreSQL's "
            "aborted-transaction state, which no other vendor here has"
        )

    if settings_module not in URL_HONOURING_SETTINGS:
        return (
            f"DATABASE_URL is PostgreSQL but DJANGO_SETTINGS_MODULE is "
            f"{settings_module or 'unset'}, which does not honour it — "
            "`config/settings/test.py` REPLACES `DATABASES` wholesale with in-memory "
            "SQLite (law 14 names that file). A run under it would be a SQLite run "
            "wearing a PostgreSQL URL, which is the exact confusion DEF-2395 was "
            f"filed about. Use one of: {', '.join(URL_HONOURING_SETTINGS)}"
        )
    return None


def run() -> tuple[str, str]:
    test_path = common.BACKEND_DIR / PLANT_TEST
    if not test_path.is_file():
        return (
            "FAIL",
            f"{PLANT_TEST} is missing. It is DEF-2395's and DEF-2722's stated "
            "prevention — the only test in the repo that provisions a tenant and then "
            "asserts the sample plant is COMPLETE. A gate whose subject has been "
            "deleted must go red, not quietly skip (law 2: built is not wired)",
        )

    skip_reason = _postgres_reason()
    if skip_reason is not None:
        return "SKIP", skip_reason

    # ⚠ THE INTERPRETER IS ASKED FOR, NOT ASSUMED (`DEF-GOV-7813`). This ran
    # `sys.executable` — bare `python3` under `run_gates`, which has pytest and
    # no Django here — so with a database present it would have reported a
    # collection error as the plant's failure.
    python, tried = common.interpreter_with("pytest", "django")
    if python is None:
        return "SKIP", (
            "no interpreter on this machine can import both pytest and Django "
            "(tried: " + ", ".join(tried) + ")"
        )
    try:
        proc = subprocess.run(
            [python, "-m", "pytest", PLANT_TEST, "-q", "--reuse-db",
             "-p", "no:randomly"],
            capture_output=True,
            text=True,
            cwd=common.BACKEND_DIR,
            timeout=TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return "SKIP", "no python interpreter available to run the suite with"
    except subprocess.TimeoutExpired:
        return (
            "FAIL",
            f"{PLANT_TEST} did not finish in {TIMEOUT_SECONDS // 60} minutes. That is "
            "a FAIL and not a SKIP on purpose: a proof that cannot be completed is "
            "not a proof, and DEF-2395 is a row about exactly that distinction",
        )

    out = (proc.stdout or "").strip()
    tail = out.splitlines()[-1] if out else "no output"

    if proc.returncode == 5:
        return (
            "FAIL",
            f"{PLANT_TEST} exists and pytest collected NOTHING from it. An empty "
            "guard is worse than no guard, because it is trusted",
        )
    if proc.returncode != 0:
        # The assertion message carries the seventeen-line block report and the
        # instruction to read the FIRST non-seeded line. Surface the tally line
        # when we can find it, because that is the number a reader wants first.
        tally = next(
            (ln.strip() for ln in out.splitlines() if "seeded," in ln and "failed," in ln),
            "",
        )
        failed_cases = [
            ln.split("::", 1)[1].strip()
            for ln in out.splitlines()
            if ln.startswith("FAILED ") and "::" in ln
        ]
        named = ", ".join(failed_cases) if failed_cases else "see the run"
        return (
            "FAIL",
            f"the PostgreSQL sample-plant guard is RED ({tail}). Failing case(s): {named}. "
            f"{tally} A case naming the OWNER is DEF-566's stub returning — start there, "
            f"because everything else in the plant is downstream of it. Per-block report: "
            f"cd 06-backend && python -m pytest {PLANT_TEST} -q",
        )
    # ⚠ **THIS SENTENCE SAID "all 17 sample-plant blocks" AND THE ESTATE HAS
    # EIGHTEEN (`DEF-3509`, 2026-09-03).** It is a PASS message, so nothing was
    # ever going to go red about it — a check reporting the WRONG FIGURE while
    # succeeding is worse than one that fails, because the figure is what a
    # person quotes. The count is read from the catalogue this gate exists to
    # prove, so it can only ever be the number the run actually required.
    return (
        "PASS",
        f"one tenant provisioned on real PostgreSQL and all {_expected_blocks()} "
        f"sample-plant blocks seeded ({tail}) — law 14's proof requirement is reachable",
    )


def main() -> int:
    status, detail = run()
    print(f"G68 plant-on-postgres: {status} — {detail}")
    return 0 if status in ("PASS", "SKIP") else 1


if __name__ == "__main__":
    sys.exit(main())
