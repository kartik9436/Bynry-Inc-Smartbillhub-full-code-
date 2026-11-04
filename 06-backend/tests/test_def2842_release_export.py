# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2842 (2026-08-31) — the release authorisation record had neither
#           the screen the PO declined nor the export the PO chose. The declined
#           option was honoured and the chosen one was not, which reads as
#           compliance: "a ruling that says do B not A is closed by doing B, and
#           the repo recorded not doing A."
# Story:    US-BIL-005 (S31 step 5)
# Rules:    BR-BIL-065 (PO 2026-08-11, OQ-112 option B, verbatim *"B An export
#           only"*) · BR-BIL-056 (the phase-4 panel RECALCULATES, so this row is
#           the only answer to "what did I approve?") · BR-BIL-058 (the gate is
#           FIVE separately recorded facts) · B14 rule 31 (no database id is the
#           visible value of a field) · CLAUDE.md rule 1 · rule 2
# ───────────────────────────────────────────────────────
"""The authorisation record is reachable, and it says what was approved.

**WHAT THIS FILE PINS THAT NOTHING ELSE COULD.** `test_be_list_export.py` proves
the export KERNEL — one header row, UTF-8, the cap, tenant isolation, the
filename shape. It cannot prove that BILLING registered a resource, because a
resource that is never registered simply is not in the list it iterates. That
absence is the defect, so it is asserted here by name.

⚠ **AND THE KERNEL'S CASES DO NOT COVER THIS RESOURCE — SAID PLAINLY, BECAUSE
THE FIRST DRAFT OF THIS PARAGRAPH CLAIMED THEY DID.** It read *"over every
registered resource"*, and they are parametrised over the Product Owner's NINE
lists (and a five-name subset for the audit-row cases). Nothing there drives
`bill_run_releases` through the export path at all. That is a comment claiming a
guarantee — hard-won law 1 — in the file written to enforce it, so the sentence
is corrected and the missing half is built below: the last case runs the JOB
BODY'S OWN four calls and reads the file back off disk.

**THE COLUMNS ARE ASSERTED AS A LIST AND NOT AS A SET.** An auditor reads left to
right and a file whose columns move between two downloads cannot be diffed; the
order is part of the contract, not an accident of a dict.

⚠ **THE FIGURES COME FROM THE STORED ROW AND NOT FROM A RECOMPUTATION, AND THAT
IS THE WHOLE POINT OF THE RECORD.** BR-BIL-056 was overturned in half on
2026-08-11: the phase-4 SCREEN recalculates, so a bill voided next week leaves
the screen's total. This row does not move, and if this export ever started
recomputing it would answer the same question the screen already answers and
nothing would answer *"what did I approve on 1 July?"* at all.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from apps.billing import exports as billing_exports, models
from apps.tenancy import exports as export_kernel
from core.pagination import ListParams

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import a_run

pytestmark = pytest.mark.django_db

CONFIRMED_AT = datetime(2026, 7, 1, 16, 55, tzinfo=timezone.utc)
RELEASED_AT = datetime(2026, 7, 1, 17, 12, tzinfo=timezone.utc)

#: The PO's own worked figure for this record, kept because it is the one they
#: were shown when they ruled: *"You approve 480 bills, $52,847.19."*
SUMMARY = {"accounts": 500, "bills": 480, "amount": "52847.190000"}


def a_release(tenant, run, dana, **overrides):
    values = dict(
        tenant=tenant,
        bill_run=run,
        summary=SUMMARY,
        account_count=500,
        bill_count=480,
        total_amount=Decimal("52847.190000"),
        currency="USD",
        compliance_confirmed=True,
        email_mandate_confirmed=True,
        sms_mandate_confirmed=True,
        autopay_mandate_confirmed=True,
        confirmed_by=dana.user,
        confirmed_at=CONFIRMED_AT,
    )
    values.update(overrides)
    return models.BillRunRelease.objects.create(**values)


def _cells(rows):
    """The formatted cells the CSV writer would emit, for the whole selection.

    `row_stream` is the kernel's own composer — the same one the job body uses —
    so what is asserted below is the file, not a re-derivation of it.
    """
    return [
        cells for cells, _source in export_kernel.row_stream(billing_exports.RELEASES, rows, ZoneInfo("UTC"))
    ]


def test_def2842__billing_registers_the_export_the_PO_CHOSE(brazos):
    """The defect itself: the resource existed nowhere, so `POST /exports`
    answered 404 for it and the ruling's chosen half was unbuilt.

    RED on the branch tip before this fix, and RED again the moment
    `BillingConfig.ready()` stops calling `register()` — which is hard-won law 2
    in its purest form: the file can be complete and unreachable.
    """
    assert "bill_run_releases" in export_kernel.registered_resources()
    spec = export_kernel.export_resource("bill_run_releases")
    assert spec is not None and spec.module == "billing"
    # BR-BIL-065 is "an export only" — the slug is what names the FILE, and a
    # file named after a screen that was declined would be the wrong noun.
    assert spec.slug == "bill-run-releases"
    # An append-only log of approvals is not a money KPI, so the filename's
    # basis segment says what KIND of file it is (the kernel's own rule).
    assert spec.basis == "event-time"


def test_def2842__the_columns_are_the_questions_an_auditor_asks(brazos):
    """Left to right, in order, because a file whose columns move cannot be
    diffed against last month's."""
    spec = export_kernel.export_resource("bill_run_releases")
    assert list(spec.header) == [
        "run_no",
        "cycle",
        "period_start",
        "period_end",
        "accounts",
        "bills",
        "total_amount",
        "currency",
        "compliance_confirmed",
        "email_mandate_confirmed",
        "sms_mandate_confirmed",
        "autopay_mandate_confirmed",
        "confirmed_by",
        "confirmed_at",
        "released_at",
    ]
    # B14 rule 31 — no uuid is a column, and the run is named by its own number.
    assert not any(name.endswith("_id") or name == "id" for name in spec.header)


def test_def2842__the_file_carries_the_figures_that_were_APPROVED(brazos, dana):
    """The stored figures, the four confirmations separately, and WHO — by name.

    Not one of these is recomputed. `total_amount` is stored at six decimals
    (CLAUDE.md rule 2) and the file writes it at two, which is the export
    kernel's own display rule and the PO's ruling of 2026-08-27 (*"Two decimals,
    like the screen — this is okay"*).
    """
    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-07|cycle-A")
        a_release(brazos, run, dana, released_at=RELEASED_AT)

        rows = billing_exports.RELEASES.select(ListParams())
        cells = _cells(rows)

    assert len(cells) == 1
    row = dict(zip(export_kernel.export_resource("bill_run_releases").header, cells[0]))
    assert row["accounts"] == "500"
    assert row["bills"] == "480"
    assert row["total_amount"] == "52847.19"
    assert row["currency"] == "USD"
    # BR-BIL-058 — four separate facts, never one undifferentiated tick.
    assert row["compliance_confirmed"] == "true"
    assert row["email_mandate_confirmed"] == "true"
    assert row["sms_mandate_confirmed"] == "true"
    assert row["autopay_mandate_confirmed"] == "true"
    # WHO, as words. An id here would be B14 rule 31 in a file.
    assert row["confirmed_by"] and "-" not in row["confirmed_by"].replace(" ", "")
    assert row["confirmed_at"].startswith("2026-07-01")
    assert row["released_at"].startswith("2026-07-01")


def test_def2842__authorised_but_not_yet_released_is_an_EMPTY_cell_and_a_real_fact(
    brazos, dana
):
    """`released_at` NULL is the state a crash between phase 4 and phase 5
    leaves behind. An auditor reading a blank there is reading a fact."""
    with tenant_ctx(brazos):
        a_release(brazos, a_run(brazos, key="2026-08|cycle-A"), dana)
        cells = _cells(billing_exports.RELEASES.select(ListParams()))

    row = dict(zip(export_kernel.export_resource("bill_run_releases").header, cells[0]))
    assert row["released_at"] == ""

    with tenant_ctx(brazos):
        pending = billing_exports.RELEASES.select(ListParams(filters={"released": "no"}))
        released = billing_exports.RELEASES.select(ListParams(filters={"released": "yes"}))
        assert pending.count() == 1
        assert released.count() == 0


def test_def2842__a_run_released_TWICE_appears_twice_and_that_is_not_a_duplicate(
    brazos, dana
):
    """APPEND-ONLY (hard rule 4). A catch-up sub-run or a resumed batch writes a
    second authorisation; both happened and both were authorised by somebody.

    Collapsing them would delete the evidence this record exists to hold, so the
    file carries both and `confirmed_at` is what tells them apart.
    """
    later = datetime(2026, 7, 8, 9, 30, tzinfo=timezone.utc)
    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-07|cycle-B")
        a_release(brazos, run, dana)
        a_release(brazos, run, dana, bill_count=6, total_amount=Decimal("410.500000"),
                  confirmed_at=later)

        # ⚠ **THE RESOURCE'S OWN `default_dir`, NOT `ListParams()`'s.** A bare
        # `ListParams` carries the framework default (`asc`); the job body that
        # actually writes the file reads `payload.get("dir") or
        # resource.default_dir`, so a test using the bare default would assert
        # an order production never produces — and would pass while the file a
        # person downloads came out oldest-first.
        spec = export_kernel.export_resource("bill_run_releases")
        assert spec.default_dir == "desc"
        cells = _cells(billing_exports.RELEASES.select(ListParams(dir=spec.default_dir)))

    header = export_kernel.export_resource("bill_run_releases").header
    rows = [dict(zip(header, line)) for line in cells]
    assert len(rows) == 2
    # Newest confirmation first — the resource's own default, so the answer to
    # "what went out most recently" is the first data line rather than the last.
    assert rows[0]["confirmed_at"].startswith("2026-07-08")
    assert rows[1]["confirmed_at"].startswith("2026-07-01")
    assert rows[0]["bills"] == "6" and rows[1]["bills"] == "480"


def test_def2842__the_selection_never_leaves_this_tenant(brazos, dana, lonestar):
    """CLAUDE.md rule 1. RLS FORCE would refuse a cross-tenant row anyway; the
    explicit filter is the belt on a read that leaves the server as a file."""
    with tenant_ctx(brazos):
        a_release(brazos, a_run(brazos, key="2026-09|cycle-A"), dana)

    with tenant_ctx(lonestar):
        assert billing_exports.RELEASES.select(ListParams()).count() == 0


def test_def2842__the_export_PATH_produces_a_real_file_for_this_resource(brazos, dana, tmp_path):
    """End to end, through the four calls the job body itself makes.

    The kernel's own suite never drives this resource — its cases are
    parametrised over the PO's nine lists — so nothing else asks whether
    `bill_run_releases` survives the round trip from a stored payload to a file
    on disk. Every step here is the platform's own function, in the platform's
    own order:

      1. **resolve the resource BY NAME** from the registry, which is what
         `POST /exports` does and what answers 404 on a miss;
      2. **rebuild the caller's list state** with `params_from_payload`, which is
         where the resource's `default_sort` and `default_dir` are applied — the
         reason a bare `ListParams()` is the wrong thing to test with;
      3. **stream it through the real writer**, one header row and nothing else;
      4. **name the file** the way IS-11 names it, five segments, with this
         resource's own `event-time` basis in the fourth.

    `job_id=None` is the one deliberate omission: progress recording needs a real
    job row and is the kernel's business, not this resource's.
    """
    from apps.tenancy.exports import (
        artifact_filename,
        params_from_payload,
        period_segment,
        row_stream,
        write_csv,
    )

    with tenant_ctx(brazos):
        a_release(brazos, a_run(brazos, key="2026-10|cycle-A"), dana, released_at=RELEASED_AT)

        # 1 · BY NAME, from the registry — the route's own lookup.
        resource = export_kernel.export_resource("bill_run_releases")
        assert resource is not None, "POST /exports would answer 404 for this name"

        # 2 · the caller's stored list state, rebuilt as the job body rebuilds it.
        params = params_from_payload(resource, {})
        assert params.sort == "confirmed_at" and params.dir == "desc"

        # 3 · the real writer, into a directory this test owns.
        path = tmp_path / artifact_filename(
            brazos.id,
            report=resource.slug,
            period=period_segment(params.filters, default=resource.period),
            basis=resource.basis,
            now=datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc),
            tz=ZoneInfo("UTC"),
        )
        written = write_csv(
            path, resource.header, row_stream(resource, resource.select(params), ZoneInfo("UTC"))
        )

    assert written == 1
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2, "one header row and one authorisation, nothing else"
    assert lines[0].split(",")[:2] == ["run_no", "cycle"]
    assert "52847.19" in lines[1] and "USD" in lines[1]

    # 4 · IS-11's five segments, and the fourth is this resource's own basis.
    _tenant, report, _period, basis, _generated = path.stem.split("_")
    assert (report, basis) == ("bill-run-releases", "event-time")
    assert path.suffix == ".csv"

# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2842 + BR-BIL-065 (07-billing/02-business-rules.md) +
#         apps/tenancy/exports.py (the kernel's contract)
# generated: 2026-09-01 by the billing defect lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(BR-BIL-065 declines the screen — PO 2026-08-11) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — with the `register()` call removed from
#        BillingConfig.ready() the first case fails on
#        `'bill_run_releases' in registered_resources()`. Verbatim in the report.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
