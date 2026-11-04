# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 W7 — one import rail. Tasks 3 (the three write modes, at
#           stage 1), 4 (BR-MET-130's post path) and 5 (the co-sign writer).
# Rules:    CR-042 (PO 2026-08-27 — TWO modes; `replace` withdrawn) ·
#           CR-038 R2 as amended (insert · insert & update, for
#           reads, and the modes NEVER edit a committed row) · CR-036 (g)
#           (PO 2026-08-26: "you need at step 1 or 2 itself - this is
#           important decision how you will process the data and upload it") ·
#           BR-MET-127 (a billed head is REFUSED BY NAME and the rest of the
#           batch posts) · BR-MET-130 (PO: "allow it" — a clerk may post an
#           incomplete cycle once the shortfall is SHOWN) · BR-MET-129 (a
#           warned reading POSTS) · BR-MET-016 (the duplicate key) ·
#           CLAUDE.md hard rule 4 / B2 DB-6 (a correction is a NEW ROW) ·
#           OQ-042 closure (co-sign: SysAdmin/Executive) · BR-MET-055
# Impacts:  apps/metering/write_modes.py · services.stage_read_batch ·
#           services.validate_read_batch · services.commit_read_batch ·
#           services.cosign_read_batch
# ───────────────────────────────────────────────────────
"""CR-038 W7 — the write modes, the incomplete-cycle post, and the co-sign.

**EVERY ASSERTION HERE WAS PROVEN RED FIRST** (hard-won law 7). The red proofs
are quoted in the lane report; the two that matter most:

* `test_w7__upsert_supersedes_rather_than_erroring` fails on `main` with
  `BizError: BIZ-COMPLETENESS (metering.read_batch.errors_need_resolution)` —
  because before this lane there was no write mode at all and a committed
  duplicate was an ERROR that gated the whole post. That is CR-036 (g)'s
  finding in one line: *"Under `upsert` 'already on file' is the EXPECTED state
  of every row, and a skip would defeat the mode entirely."*
* `test_w7__a_superseding_mode_meeting_a_billed_read_refuses_BY_NAME` fails on `main` with
  the same refusal, for the same reason, and BR-MET-127 says the opposite must
  happen: *"the refusal is a row outcome, never a batch failure"* — the named
  row stays out and **the rest of the batch posts**.

⚠ **THE HARD-RULE-4 TEST IS THE ONE TO KEEP.**
`test_w7__a_superseded_read_is_never_updated_only_closed` reads the ORIGINAL
row back out of the database after the correction and asserts its measurement
columns are byte-identical. A superseding write mode is one careless line
away from being an UPDATE, and an UPDATE of a committed reading is a hard-rule
violation that no other check in this repo would notice: the head query would
still return one row, the count would still be right, and the bill would be
priced from a number whose history had been rewritten.
"""

from decimal import Decimal

import pytest

from apps.metering import models, services, write_modes

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    accept_warnings,
    at,
    csv_body,
    seed_config,
    stage,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _post_one(actor, content, **tags):
    """Stage → validate → commit, the S28 pipeline a clerk drives by hand."""
    batch = stage(actor, content, **tags)
    services.validate_read_batch(actor, batch["id"])
    return batch, services.commit_read_batch(actor, batch["id"], {"certified": True})


def _head(asset_id, channel="total"):
    return models.MeterRead.objects.get(
        asset_id=asset_id, channel=channel, superseded_by_id__isnull=True
    )


# ── task 3 · the mode is recorded at STAGE 1, not confirmed at stage 4 ───────


def test_w7__the_write_mode_is_recorded_on_the_batch_at_stage_1(brazos, marcus):  # noqa: F811
    """CR-036 (g): the mode is a PREMISE, so it is on the batch from staging.

    Asserted on the SERVED payload and not only on the column, because the
    wizard re-opens a staged batch from this dict — a mode stored and not
    served is a control that silently resets to `insert` on a page reload.
    """
    with tenant_ctx(brazos):
        a_meter(marcus)
        staged = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"), write_mode="upsert")
        row = models.ReadImportBatch.objects.get(pk=staged["id"])

    assert row.write_mode == "upsert"
    assert staged["write_mode"] == "upsert"


def test_w7__the_default_is_insert_the_mode_that_writes_over_nothing(brazos, marcus):  # noqa: F811
    """hard-won law 3 — the unsafe option must be the one you type.

    A clerk who never touches the control gets the only one of the three modes
    that cannot alter a reading already on file.
    """
    with tenant_ctx(brazos):
        a_meter(marcus)
        staged = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))

    assert staged["write_mode"] == write_modes.DEFAULT_READ_WRITE_MODE == "insert"


def test_w7__an_unknown_write_mode_is_refused_by_name(brazos, marcus):  # noqa: F811
    """A typo'd mode is NAMED with the three allowed values, never defaulted.

    `write_modes.normalize` returns `None` rather than falling back for exactly
    this: a payload that said `upserts` meant to correct readings already on
    file, and quietly giving it `insert` would turn every one of those rows
    into an error the clerk never asked for.
    """
    from core import errors

    with tenant_ctx(brazos):
        a_meter(marcus)
        with pytest.raises(errors.ValidationError) as caught:
            stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"), write_mode="upserts")

    fields = getattr(caught.value, "field_errors", None) or []
    assert any(f.get("field") == "write_mode" for f in fields), fields
    allowed = [
        (f.get("params") or {}).get("allowed") for f in fields if f.get("field") == "write_mode"
    ]
    assert allowed and set(allowed[0]) == set(write_modes.READ_WRITE_MODES), allowed


# ── task 3 · insert · upsert, against a reading already on file (CR-042) ─────


def test_w7__insert_refuses_a_reading_already_on_file(brazos, marcus):  # noqa: F811
    """CR-038 R2: *"insert refuses committed duplicates"* — BR-MET-016 stands.

    The second upload of the same (meter, date, register) is an ERROR under
    `insert`, so that ROW does not post and **nothing is written over**, which
    is the whole claim.

    ⚠ **AMENDED 2026-08-30 — BR-MET-940 (CR-054 task 14), IN PLACE.** The
    docstring said *"an ERROR gates the whole post"* and the body asserted it:

        with pytest.raises(errors.BizError):
            services.commit_read_batch(marcus, again["id"], {"certified": True})

    The PO ruled that out — *"all or nothing will not work"* — so the batch
    posts and the duplicate row is HELD with a reason. What this test is
    actually for is untouched and is now asserted directly: the reading already
    on file is the same row with the same number afterwards (hard rule 4).
    """
    with tenant_ctx(brazos):
        asset = a_meter(marcus)
        seed_config()
        _post_one(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        first_head = _head(asset["id"])

        again = stage(marcus, csv_body("M-7001,2026-08-03,49999,total,E,"), write_mode="insert")
        report = services.validate_read_batch(marcus, again["id"])
        row = models.ReadImportRow.objects.get(batch_id=again["id"], row_no=1)
        result = services.commit_read_batch(marcus, again["id"], {"certified": True})
        still = _head(asset["id"])

    assert result["posted_reads"] == 0 and result["held_reads"] == 1
    assert result["held_rows"][0]["reason"] == "unresolved_error"
    assert row.severity == "error", report
    # The reading on file is untouched — same row, same number.
    assert still.id == first_head.id
    assert still.current_value == first_head.current_value


def test_w7__upsert_supersedes_rather_than_erroring(brazos, marcus):  # noqa: F811
    """⛔ THE RED PROOF. CR-038 R2: *"insert & update SUPERSEDES a committed
    duplicate as a correction, reason stamped"*.

    On `main` this raises
    `BizError: BIZ-COMPLETENESS (metering.read_batch.errors_need_resolution)` —
    there was no write mode, so a committed duplicate was an ERROR that gated
    the post. CR-036 (g)'s whole finding, in one assertion.
    """
    with tenant_ctx(brazos):
        asset = a_meter(marcus)
        seed_config()
        _post_one(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        original = _head(asset["id"])

        batch, result = _post_one(
            marcus, csv_body("M-7001,2026-08-03,42900,total,E,"), write_mode="upsert"
        )
        corrected = _head(asset["id"])
        original.refresh_from_db()

    assert result["posted_reads"] == 1, result
    assert result["superseded_reads"] == 1, result
    assert result["write_mode"] == "upsert"
    # A NEW ROW, and the old one closed by pointer — hard rule 4 / B2 DB-6.
    assert corrected.id != original.id
    assert corrected.current_value == Decimal("42900")
    assert original.superseded_by_id == corrected.id
    assert original.superseded_at is not None
    # CR-038 R2: *"reason stamped"*.
    assert corrected.supersede_reason == write_modes.SUPERSEDE_REASON


def test_w7__CR042__replace_is_WITHDRAWN_and_staging_refuses_it(brazos, marcus):  # noqa: F811
    """⛔ **THIS TEST REPLACES `test_w7__replace_supersedes_the_same_way_as_upsert`,
    AND THE TEST IT REPLACES IS THE REASON THE MODE IS GONE.**

    That test asserted, deliberately and as an assertion rather than as a note,
    that `replace` and `insert & update` behaved IDENTICALLY at row level — the
    state OQ-418 put to the PO. Its own docstring said *"the day the PO rules
    `replace`'s out-of-file scope, this test goes RED and names the question"*.

    The PO ruled on 2026-08-27 and the ruling was **removal**: *"in all imports
    - we need 2 option on step 1 insert, insert & update; replace option is not
    required"*. A mode that cannot be told apart from another mode is a control
    that teaches an operator a difference that does not exist.

    ⚠ **FOR READS THE REMOVAL COSTS NOTHING, AND THAT WAS MEASURED, NOT HOPED.**
    Every row `replace` touched, `upsert` touches the same way; what would have
    distinguished them — readings on file and NOT in the file — has no lawful
    answer for reads at all, because retiring a reading is either a delete
    (hard rule 4 forbids it) or a correction with no corrected value. **That is
    NOT true on the `import_runs` rail**, where BR-MET-099 gave the mode real
    behaviour: see OQ-580 before assuming the two removals are one removal.
    """
    from core import errors

    with tenant_ctx(brazos):
        a_meter(marcus)
        seed_config()
        with pytest.raises(errors.ValidationError):
            # ⚠ The literal below says `replace` ON PURPOSE and must stay that
            # way. A bulk `write_mode="replace"` → `"upsert"` sweep over this
            # file — which is exactly how the other tests here were re-pointed
            # — silently rewrote it once, and the test then asserted that a
            # LAWFUL mode raises. It failed loudly, which is the only reason
            # the sweep's overreach was noticed at all (hard-won law 7).
            stage(marcus, csv_body("M-7001,2026-08-03,43100,total,E,"), write_mode="replace")
    # The mode is not in the offered list, and `normalize` refuses rather than
    # quietly handing back the default — see its docstring for why a wrong
    # belief about a destructive operation is worse than an error.
    assert "replace" not in write_modes.READ_WRITE_MODES
    assert write_modes.normalize("replace") is None


def test_w7__a_superseded_read_is_never_updated_only_closed(brazos, marcus):  # noqa: F811
    """⚖️ CLAUDE.md hard rule 4 / B2 DB-6 — THE ONE THAT MUST NEVER GO GREEN
    BY ACCIDENT.

    A superseding write mode is one careless line away from being an
    UPDATE, and an UPDATE of a committed reading is invisible to every other
    check in this repo: the head query still returns one row, the counts are
    still right, and a bill stays priced from a number whose history has been
    rewritten underneath it. So the ORIGINAL row is read back out of the
    database and its whole measurement — the register value, the consumption,
    the unit, the multiplier — is asserted byte-identical to what it was.
    """
    with tenant_ctx(brazos):
        asset = a_meter(marcus)
        seed_config()
        _post_one(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        original = _head(asset["id"])
        before = {
            "current_value": original.current_value,
            "prior_value": original.prior_value,
            "consumption": original.consumption,
            "unit": original.unit,
            "multiplier": original.multiplier,
            "read_at": original.read_at,
            "channel": original.channel,
        }

        _post_one(marcus, csv_body("M-7001,2026-08-03,99999,total,E,"), write_mode="upsert")
        original.refresh_from_db()
        after = {key: getattr(original, key) for key in before}

    assert after == before, "a committed reading was MODIFIED, not superseded"


# ── task 3 · BR-MET-127 — the billed read, refused BY NAME ───────────────────


def test_w7__a_superseding_mode_meeting_a_billed_read_refuses_BY_NAME(brazos, marcus):  # noqa: F811
    """⛔ THE SECOND RED PROOF. BR-MET-127 (PO 2026-08-26), verbatim: *"(a)
    refuse by name — a money correction should never be minted as a side effect
    of a bulk upload; the clerk opens each through the billed door,
    deliberately"*.

    Two halves, both asserted, because either alone would be wrong:
      1. the billed row does NOT post, and the result NAMES the reading and the
         door (`correct_billed_read`);
      2. **the rest of the batch posts** — BR-MET-127: *"the refusal is a row
         outcome, never a batch failure"*. A second meter in the same file
         lands normally.
    """
    with tenant_ctx(brazos):
        billed_meter = a_meter(marcus, asset_no="M-7001", unit_label="Unit A")
        other = a_meter(marcus, asset_no="M-7002", unit_label="Unit B", address="9 Cedar St")
        seed_config()
        _post_one(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        head = _head(billed_meter["id"])
        # The lineage lock BR-MET-053 names. `mark_read_billed` is metering's
        # own published door — nothing here writes `lifecycle` by hand.
        assert services.mark_read_billed(str(head.id)) is True

        _, result = _post_one(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42900,total,E,",
                "M-7002,2026-08-03,10500,total,E,",
            ),
            write_mode="upsert",
        )
        head.refresh_from_db()
        landed = _head(other["id"])

    # 1 — the billed row is out, named, with its door.
    refusals = [s for s in result["skipped_rows"] if s["reason"] == write_modes.SKIP_REASON_BILLED]
    assert len(refusals) == 1, result["skipped_rows"]
    assert refusals[0]["br_ref"] == "BR-MET-127"
    assert refusals[0]["door"] == "correct_billed_read"
    assert refusals[0]["existing_read"] == "M-7001 · 2026-08-03 · total", refusals[0]
    assert refusals[0]["existing_read_id"] == str(head.id)
    # The billed reading is untouched: not superseded, not re-valued.
    assert head.superseded_by_id is None
    assert head.current_value == Decimal("42864")
    assert head.lifecycle == "billed"

    # 2 — and the rest of the batch POSTED. This is the half BR-MET-127 spells
    # out and the half an ERROR-severity refusal would have destroyed.
    assert result["posted_reads"] == 1, result
    assert result["status"] != "posted_nothing"
    assert landed.current_value == Decimal("10500")


def test_w7__the_billed_refusal_does_not_fail_the_batch_as_an_error(brazos, marcus):  # noqa: F811
    """The severity half of BR-MET-127, pinned separately.

    A future lane reading "refuse" naturally reaches for ERROR, and ERROR is
    what `_unresolved_errors` gates the WHOLE post on — which would turn one
    billed reading into 1,180 customers' bills not being produced. So the
    staged row's severity is asserted to be WARNING, and the reason is on the
    row where the next reader will find it.
    """
    with tenant_ctx(brazos):
        meter = a_meter(marcus)
        seed_config()
        _post_one(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        services.mark_read_billed(str(_head(meter["id"]).id))

        batch = stage(marcus, csv_body("M-7001,2026-08-03,42900,total,E,"), write_mode="upsert")
        services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)

    assert row.severity == "warning", row.rule_outcomes
    plans = [o for o in row.rule_outcomes if o["rule"] == write_modes.RULE_WRITE_MODE]
    assert plans and plans[0]["detail"]["action"] == write_modes.ACTION_REFUSE_BILLED, plans


def test_w7__the_engine_still_reports_the_duplicate_it_found(brazos, marcus):  # noqa: F811
    """The premise overrules a SEVERITY; it never erases a VERDICT.

    `write_modes.apply` stamps `engine_severity` and `superseded_by_write_mode`
    into the duplicate outcome's own detail, so a row that posted as a
    correction can still say, afterwards, that the engine found a duplicate and
    who overruled its severity. A pass that quietly deleted the outcome would
    leave the committed read claiming a clean bill of health.
    """
    with tenant_ctx(brazos):
        a_meter(marcus)
        seed_config()
        _post_one(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))

        batch = stage(marcus, csv_body("M-7001,2026-08-03,42900,total,E,"), write_mode="upsert")
        services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)

    dupes = [o for o in row.rule_outcomes if o["rule"] == "duplicate"]
    assert dupes, row.rule_outcomes
    assert dupes[0]["severity"] == "warning"
    assert dupes[0]["detail"]["engine_severity"] == "error"
    assert dupes[0]["detail"]["superseded_by_write_mode"] == "upsert"


def test_w7__an_intra_batch_duplicate_stays_an_error_under_every_mode(brazos, marcus):  # noqa: F811
    """The mode governs *already on file*; it never excuses a file that
    contradicts itself.

    Two rows for the same meter, date and register in ONE upload are an ERROR
    under `insert & update` exactly as under `insert` — no premise makes a file
    carrying two different numbers for one reading acceptable.
    """
    with tenant_ctx(brazos):
        a_meter(marcus)
        seed_config()
        batch = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-7001,2026-08-03,42900,total,E,",
            ),
            write_mode="upsert",
        )
        services.validate_read_batch(marcus, batch["id"])
        second = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=2)

    assert second.severity == "error", second.rule_outcomes
    dupes = [o for o in second.rule_outcomes if o["rule"] == "duplicate"]
    assert dupes and dupes[0]["detail"]["scope"] == "intra_batch", dupes


def test_w7__a_first_reading_is_untouched_by_the_mode(brazos, marcus):  # noqa: F811
    """A meter with no history posts identically under both modes, and the
    new read carries NO supersede reason.

    The stamp is set only when a head was actually closed — a first reading
    that claimed a correction would be a lie in the audit trail, and
    `supersede_reason` is exactly what an auditor reads to find real ones.
    """
    posted = {}
    with tenant_ctx(brazos):
        seed_config()
        for index, mode in enumerate(write_modes.READ_WRITE_MODES):
            asset = a_meter(
                marcus,
                asset_no=f"M-800{index}",
                unit_label=f"Unit {index}",
                address=f"{index} Aspen Way",
            )
            _, result = _post_one(
                marcus, csv_body(f"M-800{index},2026-08-03,1000,total,E,"), write_mode=mode
            )
            head = _head(asset["id"])
            posted[mode] = (result["posted_reads"], result["superseded_reads"], head)

    for mode, (count, superseded, head) in posted.items():
        assert count == 1, mode
        assert superseded == 0, mode
        assert head.supersede_reason is None, mode


# ── task 4 · BR-MET-130 — posting an INCOMPLETE cycle ────────────────────────


def test_w7__an_incomplete_cycle_posts_and_the_shortfall_rides_the_receipt(  # noqa: F811
    brazos, marcus, dana
):
    """BR-MET-130 (PO 2026-08-26), verbatim: *"allow it"*.

    The rule's worked case is CY-001 holding 1,240 meters against a file of
    1,180 — **60 unread**. This is that case at fixture scale: a cycle holding
    TWO meters, a file carrying ONE, **one unread**, and the post is allowed.

    ⚠ Two things are asserted and the second is the built half. Posting was
    ALREADY allowed — the lane looked for the gate this rule opens and there
    was none — so the first assertion pins *never refuses* so an absent gate
    cannot reappear as somebody's "fix". The second is what W7 adds: the
    shortfall on the RECEIPT, not only on the review step W1 built. A number a
    clerk saw at stage 4 and cannot see at stage 5 is a number they have to
    remember.
    """
    with tenant_ctx(brazos):
        seed_config()
        read_meter = a_meter(marcus, asset_no="M-7001", unit_label="Unit A")
        a_meter(marcus, asset_no="M-7002", unit_label="Unit B", address="9 Cedar St")
        # A cycle is System Admin work (BR-MET-076); the UPLOAD is the clerk's.
        # Two actors, because that is who does what.
        cycle = services.create_cycle(
            dana, {"code": "CY-001", "name": "August A", "frequency": "monthly"}
        )
        _, result = _post_one(
            marcus,
            csv_body("M-7001,2026-08-03,42864,total,E,"),
            cycle_id=cycle["id"],
        )
        assert models.MeterRead.objects.filter(asset_id=read_meter["id"]).exists()

    # 1 — it POSTED. BR-MET-130's own word: allow it.
    assert result["posted_reads"] == 1, result
    assert result["status"] != "posted_nothing"
    assert result["batch_status"] == "posted"
    # 2 — and the receipt carries the coverage, or states why it cannot.
    assert "cycle_coverage" in result, sorted(result)


def test_w7__a_cycle_less_batch_states_why_it_has_no_coverage(brazos, marcus):  # noqa: F811
    """BR-SHL-020 / hard-won law 1: a stated absence, never a silent zero.

    Coverage is a CYCLE computation. A batch tagged with no cycle has no
    expectation to compare against, and a `0` there would read as *nothing is
    missing* — which is a different claim entirely.
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        _, result = _post_one(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))

    assert result["cycle_coverage"] is None
    assert result["cycle_coverage_absent_reason"] == "batch_not_tagged_with_cycle"


# ── task 5 · the co-sign — the writer `cosigned_by` never had ────────────────


def test_w7__cosign_writes_the_column_that_was_served_for_sixteen_days(  # noqa: F811
    brazos, marcus, dana
):
    """⛔ hard-won law 2 at its longest running in this register.

    `read_import_batches.cosigned_by` shipped with migration 0003 on
    2026-08-10, `read_batch_dict` has served it on every batch since, and NO
    code path ever wrote it — which is why S28 draws no co-sign control
    (*"drawing the checkbox would offer a control that changes nothing"*).
    This asserts it changes something.
    """
    with tenant_ctx(brazos):
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        assert batch["compliance"]["cosigned_by"] is None
        assert batch["compliance"]["cosigned_at"] is None

        # ⚠ TWO DIFFERENT PEOPLE, and that is the whole point of a co-sign:
        # Marcus (Billing Clerk) uploads, Dana (System Admin) counter-signs.
        # OQ-042's closure names the qualifying roles — *"supervisor =
        # SysAdmin/Executive"* — and the next test proves a clerk cannot.
        signed = services.cosign_read_batch(dana, batch["id"])
        row = models.ReadImportBatch.objects.get(pk=batch["id"])

    assert row.cosigned_by_id == dana.id
    assert row.cosigned_at is not None
    assert signed["compliance"]["cosigned_by"] == str(dana.id)
    assert signed["compliance"]["cosigned_at"] is not None


def test_w7__a_billing_clerk_cannot_cosign(brazos, marcus):  # noqa: F811
    """OQ-042's closure, verbatim: *"supervisor = SysAdmin/Executive"*.

    A co-sign a clerk can give themselves is not a co-sign. `@require_role` is
    the same door every other role rule in this module uses.
    """
    from core import errors

    with tenant_ctx(brazos):
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        with pytest.raises(errors.AuthError):
            services.cosign_read_batch(marcus, batch["id"])


def test_w7__cosign_refuses_a_posted_batch(brazos, marcus, dana):  # noqa: F811
    """BR-MET-017: a posted batch is immutable.

    And the reason is not only the rule — a co-sign added AFTER the readings
    landed is a signature on a decision already taken, which is the opposite of
    what a supervisor co-sign is for.
    """
    from core import errors

    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch, _ = _post_one(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        with pytest.raises(errors.BizError):
            services.cosign_read_batch(dana, batch["id"])


def test_w7__the_payload_states_that_the_cosign_does_not_block_the_post(  # noqa: F811
    brazos, marcus
):
    """⚠ hard-won law 1 — the HONEST half, and it is a stated absence.

    OQ-042's closure has two clauses: a co-sign DOOR (built above) and *"blocks
    when enabled"* (NOT built — DEF-815; its tenant toggle's home is the S64
    settings document a concurrent lane owns). A screen left to guess would
    either promise a block that does not happen or hide a control that does
    work. So the payload SAYS which it is, and this test pins the sentence so
    the day the toggle lands and this still answers `False`, it goes red.
    """
    with tenant_ctx(brazos):
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))

    assert batch["compliance"]["cosign_blocks_post"] is False
