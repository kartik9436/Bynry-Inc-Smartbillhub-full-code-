# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-659 (2026-08-24, CRITICAL) — a read batch reported `posted`
#           while posting NOTHING. `sample_data._post_batch` read
#           `report.get("rows", [])` off `services.validate_read_batch`, which
#           answers `selectors.read_batch_dict` and has NO `rows` key — so the
#           warning-dispositioning loop iterated an empty list on every run,
#           `commit_read_batch` skipped every undispositioned warning
#           (`disposition = row.disposition or ("accept" if severity == OK else
#           None)`), and the batch still marked itself `posted`.
# Rules:    BR-MET-015 (an error is resolved by a human, never by a fixture) ·
#           ⚠ AMENDED 2026-08-26 (CR-038 W2): BR-MET-129 SUPERSEDES BR-MET-015's
#           warning half — a WARNED reading now POSTS without a disposition,
#           flags carried onto the committed read; only errors still gate. The
#           posts-nothing cases below were RETARGETED (not deleted) onto a
#           REJECTED row, which is the way a batch lawfully posts nothing now ·
#           BR-MET-017 (a posted batch is immutable) · hard-won law 1 (a
#           comment claiming a guarantee is not the guarantee)
# Tests:    this file. It asserts the two halves that needed no ruling.
# Impacts:  apps/metering/services.commit_read_batch ·
#           apps/metering/sample_data._post_batch / _validated_rows
# ───────────────────────────────────────────────────────
"""DEF-659 — a success message over reads that did not land.

**THE COMBINATION IS THE DEFECT.** Either half alone would have been noticed: a
batch that REFUSED would be investigated, and a batch that posted nothing AND
SAID SO would be investigated. A batch that answers `posted` over rows it
skipped is a success message covering a silent data loss, and the operator has
no reason to look.

**WHY THE SUITE COULD NOT SEE IT.** Every existing test on this path calls the
shared `accept_warnings` helper first — the helper exists precisely because a
read on a unit with no active account warns — so every one of them dispositions
its rows BEFORE reaching the dead loop, and the loop's uselessness is invisible
from inside the suite. The two cases below deliberately do NOT call it.

**WHAT IS ASSERTED HERE, AND WHAT IS NOT.** Two questions in DEF-659's row are
rulings and are untouched: whether the sample path should auto-disposition
warnings at all, and whether a batch carrying undispositioned warnings should
REFUSE outright (which is what BR-MET-015 says for errors). Neither is a lane's.
What lands without a ruling is legibility: the result carries the rows it
skipped and it does not call itself `posted` when nothing posted; and the
fixture reads its rows from the batch, refusing loudly when what it staged and
what it can see disagree.

⚠ **BOTH RULINGS ARRIVED — 2026-08-26, BR-MET-129 (CR-038).** An
undispositioned WARNING now POSTS with its flags attached (the PO: *"we can
give the warning, but we cannot reject the reading"*), which DISSOLVES the
seeder question (nothing left to auto-accept — its explicit trail stays as
demo documentation) and answers the refusal question with the opposite: post,
never refuse, for warnings. The two posts-nothing cases below were RETARGETED
onto a rejected row the same day; the legibility contract they pin is
unchanged. The rule half lives in tests/test_cr038_w2_mixed_cycle.py.
"""

import pytest

from apps.metering import models, sample_data, services

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    accept_warnings,
    csv_body,
    seed_config,
    stage,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def test_def659__validate_read_batch_STILL_has_no_rows_key(brazos, marcus):  # noqa: F811
    """The contract half, pinned so the two sides cannot drift apart silently.

    ⚠ This is NOT asking for a `rows` key to be added. `ReadBatchValidation` on
    the frontend already documents the omission and the reason (DEF-115: typing
    it as the detail made `validation.rows` LOOK present and crashed the screen
    with `TypeError: t is not iterable`). The endpoint is right; the CONSUMER
    was wrong. This pins the shape so anyone changing it sees the consumers
    listed in one place — and it asserts the LIVE return value, not a
    reconstruction, because DEF-659 was a disagreement about exactly that.
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        report = services.validate_read_batch(marcus, batch["id"])

    assert "rows" not in report, (
        "`validate_read_batch` has gained a `rows` key. That is not wrong in itself, but "
        "`sample_data._post_batch` was written against a `rows` key that was never there "
        f"(DEF-659) — re-read the consumers before relying on it. Keys: {sorted(report)}"
    )
    # And the keys a consumer CAN rely on are still there, so this test fails on
    # a shape change rather than on the return value being empty for some other
    # reason.
    assert {"id", "status", "counts", "compliance"} <= set(report), sorted(report)


def test_def659__a_batch_that_posts_NOTHING_does_not_report_posted(brazos, marcus):  # noqa: F811
    """THE REGRESSION GUARD — the legibility half of DEF-659, which survives.

    ⚠ RETARGETED 2026-08-26 (CR-038 W2, BR-MET-129). The original fixture was
    an UNDISPOSITIONED warning — the defect row's exact reproduction — and
    BR-MET-129 (PO 2026-08-26) now POSTS that row: *"we can give the warning,
    but we cannot reject the reading"*. That half of the old behaviour is
    reversed by rule (proven in test_cr038_w2_mixed_cycle.py). What this test
    guards is the half that stands: however a batch comes to post nothing —
    now, a clerk REJECTING its only row — the caller is never told `posted`
    over reads that did not land.
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        services.validate_read_batch(marcus, batch["id"])
        services.set_row_disposition(
            marcus, batch["id"], 1, {"disposition": "reject", "reason": "duplicate route sheet"}
        )
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)

    assert row.disposition == "reject"
    assert result["posted_reads"] == 0
    assert result["status"] != "posted", result
    assert result["status"] == "posted_nothing", result
    # The persisted row IS posted and immutable (BR-MET-017) — the CALLER's
    # answer is what changed, and the true batch status is still carried.
    assert result["batch_status"] == "posted"
    assert models.ReadImportBatch.objects.get(pk=batch["id"]).status == "posted"


def test_def659__every_skipped_row_is_counted_and_named(brazos, marcus):  # noqa: F811
    """`skipped_reads` + `skipped_rows` — the minimum DEF-659's row asks for.

    Before this, a commit answered `posted_reads` and nothing else, so a caller
    could not tell "nothing was there to post" from "everything was skipped".

    ⚠ RETARGETED 2026-08-26 (CR-038 W2, BR-MET-129): the skipping row is now a
    REJECTED one — an undispositioned warning no longer skips, it posts
    (BR-MET-129; proven in test_cr038_w2_mixed_cycle.py). The counting-and-
    naming contract this test pins is unchanged.
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        services.validate_read_batch(marcus, batch["id"])
        services.set_row_disposition(
            marcus, batch["id"], 1, {"disposition": "reject", "reason": "wrong meter on sheet"}
        )
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})

    assert result["skipped_reads"] == 1, result
    assert [row["row_no"] for row in result["skipped_rows"]] == [1]
    assert result["skipped_rows"][0]["reason"] == "not_dispositioned_for_posting"
    assert result["skipped_rows"][0]["disposition"] == "reject"
    assert result["skipped_rows"][0]["severity"] == "warning"


def test_def659__a_batch_that_DOES_post_still_reports_posted(brazos, marcus):  # noqa: F811
    """The other side of the guard: nothing above changes the happy path."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        services.validate_read_batch(marcus, batch["id"])
        accept_warnings(marcus, batch["id"])
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})

    assert result["status"] == "posted"
    assert result["posted_reads"] == 1
    assert result["skipped_reads"] == 0 and result["skipped_rows"] == []


def test_def659__the_fixture_refuses_when_it_cannot_see_the_rows_it_staged(
    brazos, marcus
):  # noqa: F811
    """`sample_data._validated_rows` is the LOUD half, and it is loud by COUNT.

    The original bug was a consumer reading an empty list where the rows are.
    Reproducing that mechanism exactly would mean re-introducing it, so this
    asserts the property that catches it whatever the mechanism: a fixture that
    staged N rows and can see fewer than N refuses, rather than dispositioning
    nothing and letting the commit report success.
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        services.validate_read_batch(marcus, batch["id"])

        # The honest call agrees with itself.
        rows = sample_data._validated_rows(batch["id"], staged=1, where="the probe batch")
        assert [row["row_no"] for row in rows] == [1]

        # A miscount — which is what an empty `.get("rows", [])` looked like —
        # refuses by name instead of returning quietly.
        with pytest.raises(Exception) as caught:
            sample_data._validated_rows(batch["id"], staged=2, where="the probe batch")
    message = str(caught.value)
    assert "staged 2 row(s)" in message and "reports 1 back" in message, message
    assert "DEF-659" in message
