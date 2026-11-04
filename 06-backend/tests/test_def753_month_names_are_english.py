# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-753 — *"THE DD-MMM-YY IMPORT FORMAT READS ENGLISH MONTH NAMES
#          ONLY, AND A DOCSTRING SAYS THE OPPOSITE"*. `import_runs._parse_date`
#          uses `%b` in the C locale; `tenancy/services.py` claimed the month
#          name "is produced by Intl in the app's current language … already
#          right in all eleven locales" — true for DISPLAY, false for IMPORT.
# Story:   US-MET-00x (premises/units CSV import)
# Rules:   BR-MET-117 (1) — *"when we match the date we have to compare it date
#          format that utility has selected … otherwise it show the error"*
#          (PO, 2026-08-26). No sniffing, no locale fallback, no trying formats.
# ───────────────────────────────────────────────────────
"""Refusing is the SAFE half; the harm was refusing WITHOUT SAYING WHY.

`3/4/2026` is 4 March in most of the world and 3 April in the United States, and
both readings produce a real date with no error — which is why BR-MET-117 forbids
guessing, and why this fix does NOT teach the parser eleven languages' month
names. A month table per locale would be eleven guesses about a file **our app
did not write** (IS-11 keeps every CSV export on ISO-8601, so the importer never
meets a file the app produced), and a wrong guess is a silently mis-dated
migration — far worse than a rejection.

So the parser is unchanged and deliberately so, and the two things that WERE
wrong are fixed:

  1. the refusal said only *"your settings say DD-MMM-YY and this row has
     25-Okt-26, which does not match"* — a sentence that reads as nonsense to a
     German clerk, for whom `25-Okt-26` **is** `DD-MMM-YY`; and
  2. `tenancy/services.py` told the next reader the opposite of the truth.

Both are asserted below. The parser's REFUSALS are asserted too, so that a later
lane cannot quietly add locale guessing without this file going red.
"""

import datetime

import pytest

from apps.metering import import_runs
from apps.tenancy import services as tenancy_services


def test_def753__the_english_month_name_parses():
    """The baseline, measured: `25-Aug-26` is 2026-08-25."""
    assert import_runs._parse_date("25-Aug-26", "DD-MMM-YY") == "2026-08-25"
    # Case is not the issue — `%b` is case-insensitive — so the refusals below
    # cannot be dismissed as a capitalisation problem.
    assert import_runs._parse_date("25-aug-26", "DD-MMM-YY") == "2026-08-25"
    assert import_runs._parse_date("25-AUG-26", "DD-MMM-YY") == "2026-08-25"


@pytest.mark.parametrize(
    "value",
    [
        "25-Okt-26",  # de
        "25-Mär-26",  # de
        "25-mars-26",  # fr
        "25-ago-26",  # es / it
        "25-Sept-26",  # en-GB's four-letter September
    ],
)
def test_def753__a_non_english_month_name_is_REFUSED_and_stays_refused(value):
    """⚠ **THIS IS AN ASSERTION THAT NOTHING IS GUESSED**, not a wish.

    It goes red the day someone adds a locale month table, which is the point:
    that change must be a deliberate, reviewed act with the PO's ruling behind
    it, not a helpful-looking commit. `None` here means the row is rejected and
    nothing is written — the safe outcome.
    """
    assert import_runs._parse_date(value, "DD-MMM-YY") is None


def test_def753__the_refusal_SAYS_english_and_names_the_twelve_words():
    """THE FIX. The old sentence was true and useless; a clerk looking at
    `25-Okt-26` under a `DD-MMM-YY` setting could not act on it."""
    problem, fix_hint = import_runs._date_problem("25-Okt-26", "DD-MMM-YY")
    assert "ENGLISH month" in problem
    assert "25-Okt-26" in problem  # still names the value as given (BR-MET-117 (2))
    assert "DD-MMM-YY" in problem  # …and the format they chose
    # The twelve it accepts, so nobody has to guess which spelling of October.
    for abbreviation in import_runs.ENGLISH_MONTH_ABBREVIATIONS:
        assert abbreviation in fix_hint
    # …and the way out that avoids month names altogether.
    assert "Settings › Regional" in fix_hint


def test_def753__the_twelve_are_the_ones_strptime_ACTUALLY_accepts():
    """The constant is not a hand-typed list to be trusted (hard-won law 1) —
    every entry is proved against the parser it describes, and no thirteenth
    spelling sneaks in."""
    for index, abbreviation in enumerate(import_runs.ENGLISH_MONTH_ABBREVIATIONS, start=1):
        parsed = datetime.datetime.strptime(f"01-{abbreviation}-26", "%d-%b-%y").date()
        assert parsed.month == index
    assert len(import_runs.ENGLISH_MONTH_ABBREVIATIONS) == 12


def test_def753__only_the_month_NAME_format_gets_that_sentence():
    """Every other format is digits and separators; adding an English clause to
    `DD/MM/YYYY` would be noise, and worse, would imply the same trap exists
    where it does not."""
    assert import_runs.MONTH_NAME_FORMATS == frozenset({"DD-MMM-YY"})
    problem, fix_hint = import_runs._date_problem("1/1/2026", "DD/MM/YYYY")
    assert "ENGLISH" not in problem
    assert "ENGLISH" not in fix_hint and "English" not in fix_hint


def test_def753__the_unset_case_is_untouched():
    """BR-MET-117's unset-format refusal is a different sentence and stays it."""
    problem, _fix = import_runs._date_problem("25-Aug-26", None)
    assert "has not chosen a date format" in problem


def test_def753__the_stale_claim_is_gone_from_the_tenancy_source():
    """⚠ Hard-won law 1, asserted rather than trusted. The false half was a
    COMMENT, so nothing at runtime could ever contradict it — the only way to
    keep it honest is to read the file.

    ⚠ It does NOT assert the false clause is absent, and that is deliberate:
    the fix QUOTES it, stamped as superseded, so the next reader learns what was
    believed and why it was wrong (the same posture B4/B5 take with their
    superseded draft sections — a grep hit inside a stamped quotation is not a
    blocker). What it asserts is that the clause can no longer be read as a
    STANDING claim: wherever it appears, the correction appears with it.
    """
    source = __import__("inspect").getsource(tenancy_services)
    stale = "already right in all eleven locales"
    # It survives once, as a quotation, and nowhere else.
    assert source.count(stale) == 1
    context = source[source.index(stale) : source.index(stale) + 400]
    assert "FALSE FOR IMPORT" in context
    assert "USED TO" in source[max(0, source.index(stale) - 400) : source.index(stale)]
    # …and the truth is stated where the lie was.
    assert "ENGLISH abbreviations only" in source
    # The format itself is still offered — this fixed a claim, not a feature.
    assert "DD-MMM-YY" in tenancy_services.DATE_FORMATS


def test_def753__the_pattern_map_still_mirrors_the_offered_formats():
    """The pre-existing guarantee this lane must not have broken: a key spelled
    differently here is a silently unread setting, not a wrong date."""
    assert set(import_runs.DATE_FORMAT_PATTERNS) == set(tenancy_services.DATE_FORMATS)


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-753 (12-governance/10-defect-log.csv) + BR-MET-117 (1)(2)
#         (PO verbatim, 2026-08-26) + IS-11 (CSV exports are ISO-8601)
# screens: S8 Settings › Regional (the date-format picker) · the import wizard's
#          stage-3 rejects table (where the refusal is read)
# generated: 2026-08-26 by lane DEFSWEEP
# decision: REFUSE-AND-EXPLAIN, not parse-in-the-tenant's-locale. Reported in the
#          lane report as a judgement, with its reason: the CSV is written by the
#          utility's OLD system and nothing tells us what language its month
#          names are in, so "the tenant's UI language" is itself a guess about
#          the file. Eleven hand-built month tables (no `babel` in this venv —
#          MEASURED: ModuleNotFoundError) would be eleven chances to mis-date a
#          migration, which BR-MET-117 exists to prevent.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
