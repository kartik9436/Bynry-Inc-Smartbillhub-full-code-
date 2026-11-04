# ── Trace ──────────────────────────────────────────────
# Component: BE-06 tests (core/numbering.py) — grammar, rendering, allocation contract,
#            forward-only law. Sink is a capturing fake; the real SELECT FOR UPDATE
#            allocator lands with apps.tenancy (US-TEN-012, live number_series TCs).
# ───────────────────────────────────────────────────────
"""BE-06 unit tests: the BR-TEN-035 grammar rejects with the specific problem,
rendering reproduces the US-TEN-012 §4 dataset figures verbatim, allocation is
tenant-context-only through the sink, and next-number edits are forward-only."""

import uuid
from datetime import date

import pytest

from core import errors, numbering

TENANT = uuid.UUID("00000000-0000-0000-0000-00000000000a")
AUG_8 = date(2026, 8, 8)  # US-TEN-012 §4: issue date 2026-08-08, tenant TZ America/Chicago


@pytest.fixture(autouse=True)
def clean_sink():
    numbering.set_series_sink(None)
    yield
    numbering.set_series_sink(None)


@pytest.fixture()
def in_tenant(monkeypatch):
    monkeypatch.setattr(numbering, "current_tenant_id", lambda: TENANT)


# ── format grammar (BR-TEN-035; US-TEN-012 TC-4 shapes) ─────────────────────
def test_be06_tc01_valid_prototype_formats_pass():
    for fmt in (
        "AC-{YYYY}-{00000}",
        "BL-{YY}{MM}-{000000}",
        "PY-{YY}{MM}{DD}-{0000}",
        "ADJ-{000}",
        "AST-{00000}",
    ):
        numbering.validate_format(fmt)  # no raise


def test_be06_tc02_no_sequence_token_rejected_with_specific_problem():
    with pytest.raises(errors.ValidationError) as exc_info:
        numbering.validate_format("BL-{YY}{MM}")
    assert exc_info.value.code == errors.VAL_FORMAT
    assert exc_info.value.params["problem"] == "no_sequence_token"


def test_be06_tc03_two_sequence_tokens_rejected():
    with pytest.raises(errors.ValidationError) as exc_info:
        numbering.validate_format("BL-{000}-{0000}")
    assert exc_info.value.params["problem"] == "multiple_sequence_tokens"


def test_be06_tc04_unknown_token_rejected_and_named():
    with pytest.raises(errors.ValidationError) as exc_info:
        numbering.validate_format("BL-{QQ}-{0000}")
    assert exc_info.value.params["problem"] == "unknown_token"
    assert exc_info.value.params["token"] == "{QQ}"


def test_be06_tc05_empty_or_unbalanced_format_rejected():
    with pytest.raises(errors.ValidationError):
        numbering.validate_format("")
    with pytest.raises(errors.ValidationError) as exc_info:
        numbering.validate_format("BL-{0000")
    assert exc_info.value.params["problem"] == "unbalanced_braces"


# ── rendering (US-TEN-012 §4 dataset VERBATIM — never hand-math) ────────────
def test_be06_tc06_render_reproduces_the_dataset_figures():
    assert numbering.render("AC-{YYYY}-{00000}", 569, AUG_8) == "AC-2026-00569"
    assert numbering.render("PY-{YY}{MM}{DD}-{0000}", 88, AUG_8) == "PY-260808-0088"
    assert numbering.render("ADJ-{000}", 41, AUG_8) == "ADJ-041"
    assert numbering.render("AST-{00000}", 1205, AUG_8) == "AST-01205"


def test_be06_tc07_bill_number_matches_us_ten_012_tc1():
    # TC-1: counter at 18,410, issued Aug 8 2026 → BL-2608-018410.
    assert numbering.render("BL-{YY}{MM}-{000000}", 18410, AUG_8) == "BL-2608-018410"


def test_be06_tc08_sequence_wider_than_pad_is_never_truncated():
    # Truncation could collide with an issued number — all digits survive.
    assert numbering.render("ADJ-{000}", 12345, AUG_8) == "ADJ-12345"


def test_be06_tc09_negative_sequence_refused():
    with pytest.raises(numbering.NumberingError):
        numbering.render("ADJ-{000}", -1, AUG_8)


def test_be06_tc10_preview_renders_without_a_sink_or_tenant():
    # The S8 live preview allocates nothing — pure function of its inputs.
    assert numbering.preview("BL-{YY}{MM}-{000000}", 18411, AUG_8) == "BL-2608-018411"


# ── allocation (tenant from context; sink is the in-transaction allocator) ──
def test_be06_tc11_next_number_allocates_through_the_sink(in_tenant):
    asked = []

    def sink(series, issue_date):
        asked.append((series, issue_date))
        return ("BL-{YY}{MM}-{000000}", 18410)

    numbering.set_series_sink(sink)
    assert numbering.next_number(numbering.BILL, AUG_8) == "BL-2608-018410"
    # Series key + the ISSUE DATE (CR-005: the sink decides a period restart
    # under the same row lock). Tenant is context, never a parameter — that is
    # what is still absent from this tuple and is the point of the assertion.
    assert asked == [("bill", AUG_8)]


def test_be06_tc12_no_tenant_context_refuses_loudly(monkeypatch):
    monkeypatch.setattr(numbering, "current_tenant_id", lambda: None)
    numbering.set_series_sink(lambda series, issue_date: ("ADJ-{000}", 1))
    with pytest.raises(numbering.NumberingError):
        numbering.next_number(numbering.ADJUSTMENT, AUG_8)


def test_be06_tc13_no_sink_refuses_loudly(in_tenant):
    with pytest.raises(numbering.NumberingError):
        numbering.next_number(numbering.BILL, AUG_8)


def test_be06_tc14_issue_date_is_explicit_never_the_wall_clock(in_tenant):
    # BR-TEN-043: the kernel refuses to guess "today" — no default, no now().
    numbering.set_series_sink(lambda series, issue_date: ("ADJ-{000}", 1))
    with pytest.raises(TypeError):
        numbering.next_number(numbering.ADJUSTMENT)  # type: ignore[call-arg]
    with pytest.raises(numbering.NumberingError):
        numbering.next_number(numbering.ADJUSTMENT, "2026-08-08")  # type: ignore[arg-type]


def test_be06_tc15_format_change_applies_to_future_numbers_only(in_tenant):
    # US-TEN-012 TC-2: the sink returns whatever format the settings row holds
    # AT ALLOCATION — an already-stamped number is never recomputed, and this
    # module exposes no renumber/reformat API at all (BR-TEN-035 / CLAUDE.md 4).
    formats = iter([("BL-{YY}{MM}-{000000}", 18410), ("BBU-{YYYY}{MM}-{000000}", 18411)])
    numbering.set_series_sink(lambda series, issue_date: next(formats))
    assert numbering.next_number(numbering.BILL, AUG_8) == "BL-2608-018410"
    assert numbering.next_number(numbering.BILL, AUG_8) == "BBU-202608-018411"
    renumbering = [n for n in dir(numbering) if "renumber" in n.lower() or "reformat" in n.lower()]
    assert renumbering == []


# ── forward-only next-number edits (US-TEN-012 TC-3 / TC-5) ─────────────────
def test_be06_tc16_forward_only_edit_rule():
    numbering.ensure_forward_only(568, 1000)  # forward: allowed (TC-3)
    numbering.ensure_forward_only(568, 568)  # equal: allowed (≥ current)
    with pytest.raises(errors.ValidationError) as exc_info:
        numbering.ensure_forward_only(18411, 500)  # backward: rejected (TC-5)
    assert exc_info.value.code == errors.VAL_RANGE
    assert exc_info.value.params["min"] == 18411


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-06@05736ee (component packet — B13 §3 row + signed contracts; hash = sha256/7 of B12)
# generated: 2026-08-09 by story-coder v1 (W0 kernel lane, B13 rows BE-06..BE-09)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-08)
# gates: ruff✔ black✔ pytest 16/16✔ (this file) · suite 147/147✔ · run_gates 10-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines
# exceptions: none stubbed; E2-candidates reported to the PO batch via the build report (BR-TEN-035 PROPOSED-not-frozen · PY- vs PMT- payment-series default prefix)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
