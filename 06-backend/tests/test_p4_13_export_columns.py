# ── Trace ──────────────────────────────────────────────
# Change:   P4.13 (Finance blueprint p017 · p070 row 5) — "a download carries
#           the chosen columns". RULED, PO 2026-09-24: *"all selected columns
#           will go in downloaded file"*.
# Rules:    IS-9 (a download is "current filters and visible columns") ·
#           BR-SHL-011 (the export mirrors the list's OWN state; an unknown
#           term FALLS BACK, never 4xx) · BR-SHL-013 (column visibility is a
#           client preference, so the CLIENT must send it) · BR-TEN-031 (the
#           kernel is tenancy's — Finance registers against it, P4.10)
# Tests:    this file
# Impacts:  apps/tenancy/exports.py (columns_for + the job body) ·
#           apps/tenancy/services.request_list_export · apps/tenancy/api.py
#           (POST /exports reads `columns`) · DownloadButton/DataTable send it
# ───────────────────────────────────────────────────────
"""The half of IS-9 the kernel stated it did NOT implement, now implemented.

`apps/tenancy/exports.py` has said so in its own docstring since 2026-08-10:

    **Not implemented, stated rather than papered over:** IS-9's "current
    filters AND VISIBLE COLUMNS". … Every export therefore carries the
    capability row's DEFAULT column set, in the matrix's order.

That sentence was honest and it is now out of date, which is the only reason
this file exists. Four properties, and the third is the one that carries the
PO's words:

1. **No `columns` ⇒ nothing moves.** The default set, in the matrix's order —
   every existing caller, every existing test, byte-identical.
2. **A subset is honoured.** Ask for three of nine and the file has three.
3. **IN THE ORDER ASKED, not the matrix's.** *"all selected columns will go in
   downloaded file"* is about WHICH; p070 row 5 is about ORDER — *"the ticked
   columns, in their order"* — and a chooser that reorders is drawn open on
   the Export view with ↑↓ arrows per column. A file that silently re-sorted
   them back would make the ▦ panel a lie.
4. **An unknown name FALLS BACK, never 4xx** (BR-SHL-011, verbatim: *"fall
   back, never 4xx"*). And a request naming ONLY unknown columns gets the
   DEFAULT set rather than a headerless file — a zero-column CSV is a file
   whose every row is empty, which is worse than ignoring the request.
"""

import csv

import pytest

from apps.tenancy import exports as export_kernel
from apps.tenancy import models as tenancy_models
from core import jobs as core_jobs

from tests.export_helpers import exported_file
from tests.test_be_list_export import (  # noqa: F401 (fixture imports)
    ALEX,
    lists,
    seed_lists,
    wired,
)
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    api_post,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db


def export_file(client, body):
    response = api_post(client, "/exports", body)
    assert response.status_code == 202, response.content
    job_id = response.json()["job_id"]
    row = tenancy_models.Job.objects.get(id=job_id)
    assert row.status == core_jobs.SUCCEEDED, row.error
    path = exported_file(row.id)
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


# ── 1 · silence changes nothing ────────────────────────────────────────────
def test_p4_13__no_columns_key_writes_the_default_set_in_the_matrix_order(lists):
    alex = signed_in_client(*ALEX)
    rows = export_file(alex, {"resource": "premises"})
    spec = export_kernel.export_resource("premises")
    assert rows[0] == list(spec.header)


# ── 2 + 3 · the ticked columns, in their order ─────────────────────────────
def test_p4_13__the_file_holds_exactly_the_ticked_columns_in_the_order_asked(lists):
    """PO 2026-09-24: *"all selected columns will go in downloaded file"*."""
    alex = signed_in_client(*ALEX)
    spec = export_kernel.export_resource("premises")
    # Three of the resource's own columns, deliberately NOT in the matrix's
    # order — that is the whole assertion.
    chosen = [spec.header[2], spec.header[0], spec.header[1]]
    assert chosen != list(spec.header[:3]), "pick a genuinely reordered subset"

    rows = export_file(alex, {"resource": "premises", "columns": chosen})

    assert rows[0] == chosen  # WHICH, and in WHAT ORDER
    assert len(rows) == 2  # header + Silver Creek's one seeded row
    assert len(rows[1]) == 3  # the data row is narrowed too, not just the head


def test_p4_13__the_values_follow_their_headers_when_reordered(lists):
    """A reorder that kept the OLD cells under the NEW headers would pass a
    header-only assertion and hand an accountant a file where every column is
    mislabelled. So the cells are compared against the unreordered file."""
    alex = signed_in_client(*ALEX)
    spec = export_kernel.export_resource("premises")
    natural = export_file(alex, {"resource": "premises"})
    by_name = dict(zip(natural[0], natural[1], strict=True))

    chosen = [spec.header[3], spec.header[1]]
    rows = export_file(alex, {"resource": "premises", "columns": chosen})
    assert rows[1] == [by_name[name] for name in chosen]


# ── 4 · BR-SHL-011 — fall back, never 4xx ──────────────────────────────────
def test_p4_13__an_unknown_column_is_ignored_and_the_known_ones_still_write(lists):
    alex = signed_in_client(*ALEX)
    spec = export_kernel.export_resource("premises")
    kept = spec.header[1]
    rows = export_file(
        alex, {"resource": "premises", "columns": ["not_a_column", kept, "also_not"]}
    )
    assert rows[0] == [kept]


def test_p4_13__only_unknown_columns_falls_back_to_the_default_set(lists):
    """A headerless CSV is a file whose every row is empty. The default set is
    the honest answer to a request that named nothing this list has."""
    alex = signed_in_client(*ALEX)
    spec = export_kernel.export_resource("premises")
    rows = export_file(alex, {"resource": "premises", "columns": ["nope", "still_nope"]})
    assert rows[0] == list(spec.header)


def test_p4_13__a_malformed_columns_value_is_ignored_rather_than_refused(lists):
    """BR-SHL-011 again: the export never 4xxs over list state it cannot read."""
    alex = signed_in_client(*ALEX)
    spec = export_kernel.export_resource("premises")
    for junk in ("premise_no", 17, {"a": 1}, [None, 3]):
        rows = export_file(alex, {"resource": "premises", "columns": junk})
        assert rows[0] == list(spec.header), junk


# ── the kernel's own helper, tested directly ───────────────────────────────
def test_p4_13__columns_for_is_pure_and_dedupes(lists):
    """A chooser that sends the same column twice gets it once — a duplicated
    header is a file Excel opens with two identically-named columns."""
    spec = export_kernel.export_resource("premises")
    first, second = spec.header[0], spec.header[1]
    chosen = export_kernel.columns_for(spec, [second, first, second])
    assert [column.name for column in chosen] == [second, first]
