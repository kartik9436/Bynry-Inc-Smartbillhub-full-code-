# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-012 (S25 reads list — its capability row)   Screens: S25
# Rules:    B14 rule 31 (nothing internal is ever visible to a utility user —
#           the human-facing number is what is shown, the internal value may
#           ride on `title`) · CLAUDE.md hard rule 8 (an address is stored on
#           `premises` and every other entity walks to it) · BR-MET-055 (server
#           pagination, the hot window) · BR-MET-016/053 (lineage heads only)
# ───────────────────────────────────────────────────────
"""The two server changes the Meter Reads blueprint's entry 02 asks for.

**MR-27 — a clerk can find a reading by address.** `read_list` matched
`asset__asset_no__icontains` and nothing else, so S25's search box was written
to say *"Search meter #…"* on purpose: naming a field the endpoint ignores is
the DEF-950 trap and a promise the server does not keep. A clerk on a phone
call has an address, not a meter number. The address is walked to `premises`
(CLAUDE.md hard rule 8) along the SAME `asset → service_point → unit →
premises` chain `read_linkage` composes the Premise column from, so what a
clerk searches and what they see cannot disagree.

**MR-04 — a clerk can read a batch NUMBER.** `read_dict` served
`import_batch_id`, the raw uuid, and S25 rendered it — a live B14 rule 31
breach on the busiest screen in the module, on a column the blueprint names.
`batch_no` is served beside it now. It is a THIRD value rather than a
replacement, because `read_import_batches.batch_no` is NULLABLE: a batch its
series never numbered is a real state, and the screen has to be able to tell
that apart from a batch it simply cannot name.

⚠ **BOTH WERE PROVED RED BEFORE THEY WERE TRUSTED GREEN (hard-won law 7), in
the harness that runs them.** With the widened predicate reverted to
`asset__asset_no__icontains` alone, `…finds_a_reading_by_its_premise_address`
fails `assert 0 == 1`; with `import_batch_no` removed from `read_dict`,
`…serves_the_batch_number_beside_its_id` fails on the absent key.
"""

from decimal import Decimal

import pytest

from apps.metering import models as metering_models
from apps.metering import selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db


def _read_on(actor, *, asset_no, address, day="2026-06-10"):
    """One committed read on a meter at a stated address."""
    asset = a_meter(actor, asset_no=asset_no, address=address)
    commit_read(
        actor,
        asset["id"],
        day=day,
        value="100",
        consumption=Decimal("50"),
        unit="kWh",
    )
    return asset


def _metered(rows):
    return sorted(row.asset.asset_no for row in rows)


# ── MR-27 — the search matches the meter number AND the premise address ────


def test_mr27__finds_a_reading_by_its_premise_address(brazos, dana):
    """The whole point: a clerk holding an address and no meter number."""
    with tenant_ctx(brazos):
        _read_on(dana, asset_no="M-9101", address="77 Gulf Fwy Industrial")
        _read_on(dana, asset_no="M-9102", address="2201 Cane Island Pkwy")

        assert _metered(selectors.read_list(q="Cane Island")) == ["M-9102"]


def test_mr27__still_finds_a_reading_by_its_meter_number(brazos, dana):
    """The half that already worked keeps working — a widened search that
    loses its original match is a regression wearing a feature's clothes."""
    with tenant_ctx(brazos):
        _read_on(dana, asset_no="M-9101", address="77 Gulf Fwy Industrial")
        _read_on(dana, asset_no="M-9102", address="2201 Cane Island Pkwy")

        assert _metered(selectors.read_list(q="M-9101")) == ["M-9101"]


def test_mr27__matches_neither_and_returns_nothing(brazos, dana):
    """An OR that matches everything is the DEF-044 shape one filter over: a
    search returning the WHOLE list while looking like a slice."""
    with tenant_ctx(brazos):
        _read_on(dana, asset_no="M-9101", address="77 Gulf Fwy Industrial")
        _read_on(dana, asset_no="M-9102", address="2201 Cane Island Pkwy")

        assert list(selectors.read_list(q="Nowhere Boulevard")) == []


def test_mr27__one_address_two_meters_returns_two_rows_and_not_four(brazos, dana):
    """The OR joins four forward FKs and must not fan a row out. Two meters at
    one address are two rows — never a cartesian pair."""
    with tenant_ctx(brazos):
        _read_on(dana, asset_no="M-9201", address="77 Gulf Fwy Industrial")
        _read_on(dana, asset_no="M-9202", address="77 Gulf Fwy Industrial")

        assert _metered(selectors.read_list(q="Gulf Fwy")) == ["M-9201", "M-9202"]


# ── MR-04 — the batch NUMBER, because B14 rule 31 forbids the uuid ─────────


def test_mr04__serves_the_batch_number_beside_its_id(brazos, dana):
    """`import_batch_no` is what a clerk reads; the id stays for `title`."""
    with tenant_ctx(brazos):
        asset = _read_on(dana, asset_no="M-9301", address="77 Gulf Fwy Industrial")
        batch = metering_models.ReadImportBatch.objects.create(
            tenant_id=brazos.id,
            batch_no="RB-2608-0044",
            source_kind="csv",
            status="posted",
        )
        read = metering_models.MeterRead.objects.get(asset_id=asset["id"])
        read.import_batch = batch
        read.save(update_fields=["import_batch"])

        served = selectors.read_dict(selectors.read_list().first())
        assert served["import_batch_no"] == "RB-2608-0044"
        assert served["import_batch_id"] == str(batch.id)


def test_mr04__a_batch_its_series_never_numbered_serves_null(brazos, dana):
    """`batch_no` is NULLABLE. A batch with no number is a real state and the
    screen has to tell it apart from a batch it cannot name at all — which is
    why this is a third value and not a replacement for the id."""
    with tenant_ctx(brazos):
        asset = _read_on(dana, asset_no="M-9302", address="77 Gulf Fwy Industrial")
        batch = metering_models.ReadImportBatch.objects.create(
            tenant_id=brazos.id,
            batch_no=None,
            source_kind="csv",
            status="posted",
        )
        read = metering_models.MeterRead.objects.get(asset_id=asset["id"])
        read.import_batch = batch
        read.save(update_fields=["import_batch"])

        served = selectors.read_dict(selectors.read_list().first())
        assert served["import_batch_no"] is None
        assert served["import_batch_id"] == str(batch.id)


def test_mr04__a_reading_with_no_batch_serves_null_for_both(brazos, dana):
    """`commit_read` writes history directly and carries no batch — the most
    common shape in the fixture world, and it must not raise."""
    with tenant_ctx(brazos):
        _read_on(dana, asset_no="M-9303", address="77 Gulf Fwy Industrial")

        served = selectors.read_dict(selectors.read_list().first())
        assert served["import_batch_no"] is None
        assert served["import_batch_id"] is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-012 (S25) + the Meter Reads blueprint entry 02, commitments MR-04 and MR-27
# generated: 2026-09-14 by the Meter Reads step-2 entry-02 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
