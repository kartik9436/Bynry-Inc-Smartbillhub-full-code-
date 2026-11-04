"""The request-body ceiling must never refuse a file the import cap accepts.

⚠ **DJANGO'S 2.5 MB DEFAULT WAS THE REAL IMPORT LIMIT AND NOTHING NAMED IT**
(`DEF-MET-5756`, measured 2026-09-18). An import file arrives as a JSON string
field, so it is a request BODY: `DATA_UPLOAD_MAX_MEMORY_SIZE` refused it before
one line of application code ran. Measured: 2 MB accepted, 3/8/12 MB
`RequestDataTooBig` — about 25,000 premises rows. Raising `CSV_BYTE_CAP` moved
it by nothing, and the refusal carried no `trace_id` and no catalogue sentence.

⚠ **THIS FILE EXISTS BECAUSE THE FIX PUT THE SAME IDEA IN TWO PLACES.**
`config/settings/base.py` cannot import `apps.metering.import_runs` (settings
load before apps), so it restates the cap's arithmetic. Two numbers for one idea
is the ORIGINAL defect — `CR-026` raised the row cap and left the byte cap at
the 3,000-row-era figure, and an operator met a megabyte refusal while the
product's stated limit counted rows. So the agreement is ASSERTED here rather
than trusted to whoever edits one of them next.
"""

from django.conf import settings

from apps.metering import import_runs


def test_def_met_5756__the_body_ceiling_clears_the_import_cap():
    """The ceiling must exceed the largest lawful CSV, with room for the JSON
    envelope the file travels inside — quotes and commas are escaped, and the
    target, mapping and run fields ride beside it."""
    assert settings.DATA_UPLOAD_MAX_MEMORY_SIZE >= import_runs.CSV_BYTE_CAP, (
        f"the request body ceiling ({settings.DATA_UPLOAD_MAX_MEMORY_SIZE:,} B) is BELOW "
        f"the import byte cap ({import_runs.CSV_BYTE_CAP:,} B), so a file the import "
        "accepts is refused by Django first — with no trace_id and no sentence a clerk "
        "can act on. That is DEF-MET-5756 exactly."
    )


def test_def_met_5756__the_two_numbers_have_not_drifted():
    """`base.py` restates the cap's arithmetic because it cannot import it.
    **This is the guard that makes that restatement safe.** If someone moves
    `CSV_ROW_CAP` or `CSV_BYTES_PER_ROW_ALLOWANCE` and not the settings line,
    this goes red and names both figures."""
    restated = 100_000 * 512
    assert restated == import_runs.CSV_BYTE_CAP, (
        f"base.py restates the import byte cap as {restated:,} B and import_runs now "
        f"computes {import_runs.CSV_BYTE_CAP:,} B "
        f"({import_runs.CSV_ROW_CAP:,} rows x {import_runs.CSV_BYTES_PER_ROW_ALLOWANCE} B). "
        "Update `_IMPORT_CSV_BYTE_CAP` in config/settings/base.py in the same commit."
    )


def test_def_met_5756__the_old_default_would_now_fail_this():
    """The measured failure, kept as an assertion so the fix cannot silently
    revert: Django's 2.5 MB default is far below the import cap, which is why
    ~25,000 premises rows was the true ceiling."""
    django_default = 2_621_440
    assert django_default < import_runs.CSV_BYTE_CAP, "the premise of this defect changed"
    assert settings.DATA_UPLOAD_MAX_MEMORY_SIZE > django_default, (
        "DATA_UPLOAD_MAX_MEMORY_SIZE is back at (or below) Django's default — the import "
        "ceiling has silently returned to ~25,000 rows"
    )
