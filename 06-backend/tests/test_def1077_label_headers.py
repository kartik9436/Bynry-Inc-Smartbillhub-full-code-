# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-1077 — the downloaded template's header row was OUR FIELD NAME,
#          so a utility opening `assets_meters_sample.csv` read `unit_ref` and
#          had no way to know what belonged in it. PO verbatim 2026-08-27:
#          "when we add assets we have to tie them to units; and in CSV file
#          that we download there is not unit ID or unit name that we can
#          provide - what about this".
#          DEF-2160 — the accounts template's Unit cell invented `U-00001`.
#          DEF-1077 (second half) — a tenant with no units on file was told nothing.
# Screens: WFL-01 stage 1 (the sample download) and stage 2 (the notes)
# Rules:   BR-MET-088 (the offered columns are DERIVED from the model) ·
#          BR-MET-096 (one runner, every target) · BR-AST-045 (a blank unit is
#          lawful and loads to inventory) · DEF-616 (the shipped sample must
#          map itself) · DEF-962 (a reference cell is the tenant's own row or
#          it is blank — never an invented number)
# ───────────────────────────────────────────────────────
"""The template a human can fill in.

**The property, and it is one sentence:** the file a first-time operator
downloads is headed in THEIR words, and it still maps itself in OURS.

Those two pull in opposite directions, which is why this file exists. Heading
the file `Unit` is worth nothing if stage 1 then cannot recognise it — the
operator would be hand-mapping the product's own sample, which is `DEF-616`'s
whole complaint. And keeping the header `unit_ref` is machine-perfect and
human-useless, which is `DEF-1077`'s.

`test_def1077__every_label_header_maps_back_to_its_OWN_field` is the guard that
holds both at once, and it is STRONGER than the DEF-616 test it sits beside:
DEF-616 asks whether every header was *recognised as something*, this one asks
whether it was recognised as the RIGHT thing. A label that collides with
another column's alias passes the first and fails this one — which is the
failure the 2026-08-27 attempt at this change actually hit (`Owner` claimed by
the free-text `owner_manager`), and the reason it was held back.
"""

from __future__ import annotations

import csv
import io

import pytest

from apps.metering import import_runs

from tests.test_cr028_seed import seeded, silvercreek  # noqa: F401 — fixture chain
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _rows(target: str) -> tuple[list[str], list[str]]:
    header, example = list(csv.reader(io.StringIO(import_runs.sample_csv(target)[1])))
    return header, example


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE HEADER IS THE LABEL
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("target", sorted(import_runs.TARGETS))
def test_def1077__the_header_row_is_the_operators_words_not_ours(seeded, target):  # noqa: F811
    """Every target, because the PO opened one file and the fault was in all six."""
    tenant, _actor = seeded
    with tenant_ctx(tenant):
        header, _example = _rows(target)
        expected = [str(column["label"]) for column in import_runs.sample_columns(target)]
    assert header == expected, f"the `{target}` template still speaks in field names: {header}"


def test_def1077__THE_PO_S_OWN_COLUMN_reads_Unit(seeded):  # noqa: F811
    """The one column the report was about, asserted by name so a future
    refactor cannot quietly rename it back."""
    tenant, _actor = seeded
    with tenant_ctx(tenant):
        header, _example = _rows("assets_meters")
    assert "Unit" in header
    assert "unit_ref" not in header


# ══════════════════════════════════════════════════════════════════════════
# 2 · AND IT STILL MAPS ITSELF — TO THE RIGHT COLUMN
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("target", sorted(import_runs.TARGETS))
def test_def1077__every_label_header_maps_back_to_its_OWN_field(seeded, target):  # noqa: F811
    """⚠ **NOT "is it detected" — "is it detected as the RIGHT column".**

    `test_def616__every_shipped_sample_maps_itself` asks the first question and
    would pass on a file whose `Owner` header landed on `owner_manager`. That
    exact collision existed on 2026-08-27 and is why the header change was
    reverted; it was closed by `DEF-1247`, and this test is what keeps it
    closed for every label on every target.
    """
    tenant, actor = seeded
    with tenant_ctx(tenant):
        _filename, body = import_runs.sample_csv(target)
        columns = import_runs.sample_columns(target)
        run = import_runs.extract(
            actor,
            {
                "target": target,
                "source_kind": "file",
                "file_name": f"{target}_sample.csv",
                "content": body,
                "session_ref": "sess_def1077",
                "ip": "71.42.108.14",
            },
        )
    detected = run["detected_mapping"]
    wrong = {
        str(column["label"]): (detected.get(str(column["label"])), column["target"])
        for column in columns
        if detected.get(str(column["label"])) != column["target"]
    }
    assert wrong == {}, (
        f"`{target}`: a header the product itself wrote did not come back to the column "
        f"that wrote it — got (detected, expected) {wrong}. A label that is another "
        "column's alias silently points a utility's data at the wrong destination."
    )


# ══════════════════════════════════════════════════════════════════════════
# 3 · A TENANT WITH NO UNITS IS TOLD SO, IN THE BUILD ORDER
# ══════════════════════════════════════════════════════════════════════════
#
# `_sample_reference_cells` ships the Unit cell BLANK when the tenant has no
# units, and that is correct — `DEF-962` forbids inventing `U-00001`. But a
# blank cell in a column whose blank is ALSO LAWFUL (BR-AST-045: it loads to
# inventory) is the product stating a fact in the one way nobody can read. The
# PO opened exactly that file and reported the column as missing.


def test_def1077__a_tenant_with_no_units_is_told_the_build_order(brazos):  # noqa: F811
    """Brazos Bend is provisioned and has no units, which is every utility on
    its first day. The Unit column says so, and names what to do first."""
    with tenant_ctx(brazos):
        columns = {c["target"]: c for c in import_runs.target_columns("assets_meters")}
        unit = columns["unit_ref"]
        assert unit.get("blank_reason"), (
            "a tenant with no units downloads a template whose Unit column can only be "
            "left blank, and the product says nothing about why"
        )
        reason = str(unit["blank_reason"])
        # The build order, IN ORDER — asserted by position rather than by
        # presence, because "Premises and Units are both mentioned" is true of
        # a sentence that names them the wrong way round.
        assert reason.index("Premises") < reason.index("Units"), reason
        assert "no units in this utility yet" in reason, reason
        # ⚠ And NOT the sentence that would be true and useless: `DEF-1079`'s
        # pairing is an unfillable unit column plus a summary that calls the
        # resulting load "no remarks at all".
        assert "leave it blank" not in reason.lower(), reason


def test_def1077__a_tenant_that_HAS_units_is_not_told_to_go_and_make_some(seeded):  # noqa: F811
    """The mirror, and it is the half that proves the sentence is READ from the
    tenant rather than printed always. Silver Creek has units, so the column
    carries its worked example and no build-order note."""
    tenant, _actor = seeded
    with tenant_ctx(tenant):
        columns = {c["target"]: c for c in import_runs.target_columns("assets_meters")}
        assert "blank_reason" not in columns["unit_ref"]
        _header, example = _rows("assets_meters")
        cells = dict(
            zip([str(c["label"]) for c in import_runs.sample_columns("assets_meters")], example)
        )
    assert cells["Unit"] != "", "a tenant WITH units still gets a blank worked cell"


# ══════════════════════════════════════════════════════════════════════════
# 4 · AND THE ACCOUNTS TEMPLATE STOPS INVENTING A UNIT NUMBER (DEF-2160)
# ══════════════════════════════════════════════════════════════════════════


def test_def2160__the_accounts_template_names_a_unit_this_tenant_actually_has(seeded):  # noqa: F811
    """`_account_column("unit_ref", …, sample="U-00001")` hardcoded a unit
    number, on the one target where the column is REQUIRED — so the accounts
    sample could not survive its own import on any tenant whose first unit is
    not literally `U-00001`. It is `DEF-962` exactly, on the target `DEF-962`
    did not reach."""
    tenant, _actor = seeded
    with tenant_ctx(tenant):
        labels = [str(c["label"]) for c in import_runs.sample_columns("accounts")]
        _header, example = _rows("accounts")
        cells = dict(zip(labels, example))
        on_file = import_runs._sample_reference_cells()["unit_ref"]
    assert on_file != ""
    assert (
        cells["Unit"] == on_file
    ), f"the accounts template still ships an invented unit number {cells['Unit']!r}"


def test_def2160__and_on_a_tenant_with_no_units_it_ships_blank_rather_than_a_lie(
    brazos,
):  # noqa: F811
    with tenant_ctx(brazos):
        labels = [str(c["label"]) for c in import_runs.sample_columns("accounts")]
        _header, example = _rows("accounts")
        cells = dict(zip(labels, example))
    assert cells["Unit"] == ""


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-1077 (PO report 2026-08-27, verbatim in the Trace block) ·
#         BR-MET-088 · BR-AST-045 · DEF-616 · DEF-962 · DEF-1247
# generated: 2026-08-28 by the meters-template lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
