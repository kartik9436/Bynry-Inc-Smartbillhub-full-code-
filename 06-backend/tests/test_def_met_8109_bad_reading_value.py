# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-8109 — one bad value in the reading column (a 13+ digit
#           number, `NaN`, `Infinity`) failed the WHOLE reads file with a 500
#           before anything was staged.
# Ruling:   PO 2026-09-30, decision log "READS UPLOAD 500 ON 480 READINGS",
#           fix (D): *"reject a bad reading value as a row error"*.
# Rules:    BR-MET-032 (validate-then-accept: a bad ROW stages with its error
#           attached; only a bad FILE stages nothing) · CLAUDE.md hard rule 2's
#           discipline on quantities (NUMERIC(18,6) — 12 whole digits) ·
#           law 14 (PostgreSQL refuses what SQLite stores — run this file with
#           `--ds=config.settings.pgtest` too)
# ───────────────────────────────────────────────────────
"""A bad reading value is a ROW error with a plain message, never a 500.

`meter_reads.current_value` and the staged row's `value` are `NUMERIC(18,6)`:
twelve whole digits. Every bad value used to reach the database layer, and
each died there with a different exception — all of them 500s, all of them
inside `stage_read_batch`'s one transaction, so NOTHING of the file staged.
Run this file on both databases (`--ds=config.settings.pgtest`): the shapes
differ, and only PostgreSQL shows the one production meets.

RED FIRST, on the branch base `e04a500af` — 9 failed, 1 passed (the
twelve-digit boundary, which must pass on both sides):

    PostgreSQL 16:  django.db.utils.DataError: numeric field overflow
                    DETAIL: A field with precision 18, scale 6 must round to
                    an absolute value less than 10^12.          (x3: 13+ digits)
                    django.core.exceptions.ValidationError: ['"Infinity" value
                    must be a decimal number.']                  (x2: ±Infinity)
                    decimal.InvalidOperation                     (x3: NaN, sNaN)
    SQLite:         decimal.InvalidOperation                     (x5)
                    django.core.exceptions.ValidationError       (x2)
"""

import pytest

from apps.metering import models, read_import

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import a_meter, csv_body, seed_config, stage, tenant_ctx

pytestmark = pytest.mark.django_db


BAD_VALUES = [
    ("1234567890123", read_import.ERR_VALUE_TOO_LARGE),  # 13 whole digits
    ("99999999999999999999", read_import.ERR_VALUE_TOO_LARGE),
    ("1e20", read_import.ERR_VALUE_TOO_LARGE),
    ("NaN", read_import.ERR_VALUE_UNPARSEABLE),
    ("nan", read_import.ERR_VALUE_UNPARSEABLE),
    ("Infinity", read_import.ERR_VALUE_UNPARSEABLE),
    ("-Infinity", read_import.ERR_VALUE_UNPARSEABLE),
    ("sNaN", read_import.ERR_VALUE_UNPARSEABLE),
]


@pytest.mark.parametrize("raw,code", BAD_VALUES)
def test_def_met_8109__a_bad_value_is_a_row_error_and_the_rest_of_the_file_stages(
    brazos, marcus, raw, code
):
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        batch = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                f"M-7002,2026-08-03,{raw},total,E,",
            ),
        )
        rows = {r.row_no: r for r in models.ReadImportRow.objects.filter(batch_id=batch["id"])}

    assert len(rows) == 2, "every row that entered the file is staged (BR-MET-032)"
    good, bad = rows[1], rows[2]
    assert good.severity == "ok" and good.value is not None
    assert bad.severity == "error"
    assert bad.value is None, "a value the column cannot hold is never written"
    parse = [o["detail"] for o in bad.rule_outcomes if o["rule"] == "parse"]
    assert parse and parse[0]["code"] == code and parse[0]["field"] == "reading"
    # What the clerk typed travels back verbatim, so the row can be found.
    assert parse[0]["value"] == raw


def test_def_met_8109__twelve_whole_digits_still_fit(brazos, marcus):
    """The boundary: NUMERIC(18,6) holds twelve whole digits and refuses a
    thirteenth. A refusal one digit early would turn a lawful reading into an
    error. (Twelve NINES rather than `…999.999999`: SQLite stores a decimal as a
    float and cannot read eighteen significant digits back, which is an
    artefact of the test database and not of the rule.)"""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        batch = stage(marcus, csv_body("M-7001,2026-08-03,999999999999,total,E,"))
        row = models.ReadImportRow.objects.get(batch_id=batch["id"])

    assert not [o for o in row.rule_outcomes if o["rule"] == "parse"], row.rule_outcomes
    assert row.value == 999999999999


@pytest.mark.parametrize(
    "raw,message_key",
    [
        ("NaN", "metering.read_row.override_value"),
        ("Infinity", "metering.read_row.override_value"),
        ("1234567890123", "metering.read_import.reading_too_large"),
    ],
)
def test_def_met_8109__an_override_value_is_refused_by_name_not_with_a_500(
    brazos, marcus, raw, message_key
):
    """The review step's *override* takes a typed value too, through the same
    parser — the same three values, refused as a field error the form shows."""
    from apps.metering import services
    from core import errors

    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        services.validate_read_batch(marcus, batch["id"])
        with pytest.raises(errors.ValidationError) as refused:
            services.set_row_disposition(
                marcus,
                batch["id"],
                1,
                {"disposition": "override", "value": raw, "reason": "collector re-read"},
            )

    keys = [fe["message_key"] for fe in refused.value.field_errors]
    assert message_key in keys, keys


def test_def_met_8109__the_parser_names_each_case_without_raising():
    """Pure parser half — no database, so it runs identically everywhere."""
    mapping = {"meter_id": "m", "read_date": "d", "reading": "r"}
    for raw, code in BAD_VALUES:
        parsed = read_import.parse_row(1, {"m": "M-1", "d": "2026-08-03", "r": raw}, mapping)
        assert parsed.value is None, raw
        assert [e["code"] for e in parsed.errors] == [code], (raw, parsed.errors)
