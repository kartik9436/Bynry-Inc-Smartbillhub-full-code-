# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03) — CR-039 wave B, "Say what happened"
#           Screens: S8 (Settings → Company profile → Sample data, BR-TEN-069)
# Change:   CR-039 (12-governance/11-change-requests.md), PO 2026-08-26 —
#           *"we need to look at what of 1 job fails and does not load the data
#           - them what we do with rest of the jobs - we should continue and
#           should not lose entire setup"* · *"Can we write all failed job
#           detialsin audit log of that tenant along wt=ith error code so that
#           we can trace it back later?"*
# Rules:    BR-TEN-060 (an unwired seam is a NAMED line, not a skip) ·
#           BR-TEN-063 (atomic per module, idempotent, audited) · BR-AUD-002
#           (append-only) · BR-AUD-006 (PII masked only) · CLAUDE.md rule 1/7
# ───────────────────────────────────────────────────────
"""CR-039 wave B — per-block outcomes, stable codes, cascades, retry.

EVERY TEST HERE WAS PROVED RED BEFORE IT WAS TRUSTED GREEN (hard-won law 7).
The failure each one produced against the un-fixed code is quoted in its own
docstring, so a later reader can tell a genuine assertion from a vacuous one.
"""

import inspect
import pathlib
from types import SimpleNamespace

import pytest

from apps.tenancy import models, sample_data, sample_errors
from core import sample_fixture as fixture

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    FakeUser,
    admin_actor,
    audit_actions,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _fake_every_seam(monkeypatch, *, counts: int = 1, raisers: dict | None = None) -> dict:
    """Put a controlled fake on EVERY block's seam, and report what ran.

    The real seeders plant an entire estate and take minutes; what is under test
    here is the ORCHESTRATOR's reporting, so each block becomes a one-line fake.
    The returned dict counts calls per block key — which is how the retry test
    proves that retrying one block runs exactly one seeder.
    """
    from importlib import import_module

    calls: dict[str, int] = {}
    raisers = raisers or {}

    for spec in sample_data.SAMPLE_MODULES:
        services = import_module(f"apps.{spec.module}.services")
        key = spec.key

        def make(key=key):
            def fake(actor):
                calls[key] = calls.get(key, 0) + 1
                if key in raisers:
                    raise raisers[key]
                return counts

            return fake

        monkeypatch.setattr(services, spec.seam, make(), raising=False)
    return calls


# ── 1 · the dependency graph is QUOTED, never invented ─────────────────────
def test_cr039__every_declared_edge_is_quoted_from_the_file_it_cites():
    """`BLOCK_DEPENDENCIES` may only say what the code already said.

    CR-039 wave B task 7 is explicit that the dependency order must be derived
    and never invented — *"do NOT invent a dependency graph nobody ratified"*.
    So each edge carries the file it comes from and the words it comes from,
    and this greps them back out. A seeder that rewords its own sentence turns
    the CITATION red, which is a lane being told to re-read the code rather
    than a silent invention left standing behind a passing suite.

    RED-PROVED: with `metering:seed_sample_reads`'s quote altered by one word
    ("check the Meters and Premise blocks above.") this failed with

        AssertionError: BLOCK_DEPENDENCIES claims apps/metering/sample_data.py
        states metering:seed_sample_reads needs assets:seed_sample_records, but
        'check the Meters and Premise blocks above.' does not appear in it
    """
    for block_key, edges in sample_data.BLOCK_DEPENDENCIES.items():
        for upstream, path, quote in edges:
            text = (REPO_ROOT / path).read_text(encoding="utf-8")
            assert quote in text, (
                f"BLOCK_DEPENDENCIES claims {path} states {block_key} needs "
                f"{upstream}, but {quote!r} does not appear in it"
            )


def test_cr039__every_edge_names_blocks_that_exist():
    """A dependency on a block the catalogue does not hold is a dead edge.

    It would silently never fire — `_root_for` only walks into blocks that are
    in `non_seeded`, and a key nothing records can never be there — so the
    cascade marking would quietly stop working with every test still green.

    RED-PROVED: with the `billing:seed_sample_records` edge pointed at a
    renamed `metering:seed_sample_read` this failed with

        AssertionError: billing:seed_sample_records declares a dependency on
        metering:seed_sample_read, which is not a block of the sample set
    """
    known = {spec.key for spec in sample_data.SAMPLE_MODULES}
    for block_key, edges in sample_data.BLOCK_DEPENDENCIES.items():
        assert block_key in known, f"{block_key} is not a block of the sample set"
        for upstream, _path, _quote in edges:
            assert upstream in known, (
                f"{block_key} declares a dependency on {upstream}, which is not "
                "a block of the sample set"
            )


# ── 2 · the audit sentence cannot carry a tenant's or a customer's data ────
def test_cr039__the_audit_catalogue_sentences_interpolate_nothing():
    """`audit_log` is append-only, so what reaches it must be FIXED text.

    The seeders' own sentences embed live values — `payments` puts an
    `invoice_no` and a raw `str(exc)` in one, `customers` puts an account
    BALANCE in another, `metering` puts read-validation row messages in a
    third. On the sample estate those are fixture rows; the same code path runs
    against a real tenant, and a row in `audit_log` has no delete (BR-AUD-002).

    Two assertions, and the second is the structural one: the catalogue holds
    no format placeholder of any kind, and `audit_safe_sentence` accepts ONLY a
    code — a function that could be handed the seeder's message is a function
    that will be, eventually.

    RED-PROVED: with a placeholder added to one catalogue entry ("… named %s")
    this failed with

        AssertionError: SD-PRECONDITION's audit sentence contains '%s' — an
        append-only row may not interpolate anything
    """
    for code, sentence in sample_errors.CATALOGUE.items():
        for marker in ("{", "}", "%s", "%d", "%r"):
            assert marker not in sentence, (
                f"{code}'s audit sentence contains {marker!r} — an append-only "
                "row may not interpolate anything"
            )
    params = list(inspect.signature(sample_errors.audit_safe_sentence).parameters)
    assert params == ["code"], (
        "audit_safe_sentence must take the CODE and nothing else: a signature "
        "that accepts a message is one that will be handed a seeder's message"
    )


def test_cr039__a_failed_block_writes_one_audit_row_carrying_its_code(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """CR-039 wave B task 10 — the PO's request, asserted end to end.

    Before this, one run wrote ONE `sample.seeded` row carrying totals, so the
    permanent trail could say a run went badly and could not say what failed.

    The row must carry the module, the block, a stable code and a sentence —
    and must NOT carry the seeder's own sentence, which is the half a later
    lane would "helpfully" add back.

    RED-PROVED (twice): with `_audit_failed_block` stubbed to `return None`
    this failed with

        AssertionError: no sample.block_failed row was written for the failing
        block — the trail still carries totals only
        assert 'sample.block_failed' in ['reference.seeded', 'reference.seeded',
        'reference.seeded', ...]

    and with the seeder's sentence copied into the row's `after` it failed with

        AssertionError: the failing seeder's own sentence reached audit_log,
        which is append-only — account A-10001 owes 267.30
    """
    tenant, _ = provisioned_tenant()
    secret = "account A-10001 owes 267.30"
    _fake_every_seam(
        monkeypatch,
        raisers={"billing:seed_sample_records": fixture.BlockCannotRun(secret)},
    )

    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())

    assert "sample.block_failed" in audit_actions(audit_rows), (
        "no sample.block_failed row was written for the failing block — the "
        "trail still carries totals only"
    )
    failed = [row for row in audit_rows if row["action"] == "sample.block_failed"]
    assert len(failed) == 1, "one row per failed block, no more and no fewer"
    after = failed[0]["after"]
    assert after["module"] == "billing"
    assert after["block"] == "seed_sample_records"
    assert after["error_code"] == sample_errors.CODE_PRECONDITION
    assert after["meaning"] == sample_errors.audit_safe_sentence(sample_errors.CODE_PRECONDITION)
    assert secret not in str(after), (
        "the failing seeder's own sentence reached audit_log, which is " f"append-only — {secret}"
    )


def test_cr039__the_operator_still_gets_the_seeders_own_sentence(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """The sentence is not deleted — it is kept where it CAN be deleted.

    The audit row carries the code; `sample_data_runs` carries the words, and
    that table is an ordinary tenant table "Remove sample data" deletes. Losing
    the sentence in the name of safety would be BR-TEN-060 broken from the
    other side: *"a sentence an operator can act on"*.

    RED-PROVED: with `detail=None` passed to `_record` on the failure path this
    failed with

        AssertionError: the block's own sentence is not on the S8 line
        assert 'no bill template on this tenant' in ((None or ''))
    """
    tenant, _ = provisioned_tenant()
    sentence = "no bill template on this tenant"
    _fake_every_seam(
        monkeypatch,
        raisers={"billing:seed_sample_records": fixture.BlockCannotRun(sentence)},
    )

    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
        blocks = {
            row["block"]: row for row in sample_data.stored_blocks() if row["module"] == "billing"
        }

    assert sentence in (
        blocks["seed_sample_records"]["detail"] or ""
    ), "the block's own sentence is not on the S8 line"


# ── 3 · a cascade names the block that actually broke ──────────────────────
def test_cr039__a_cascade_marks_consequences_and_names_the_root(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """CR-039 wave B task 7 — five reds, ONE cause, said in the report.

    `apps/assets/sample_data.py` records this happening for real (DEF-660): a
    meter retirement made the reads batch refuse and that took *"billing,
    payments, the payment plan and all plan money with it in a chain of five
    failures that read like five separate bugs."*

    Reads fail; billing and payments then fail behind them, exactly as their
    own seeders do. Every failure is still reported — nothing is hidden — but
    only the reads block is a ROOT, and the other two name it.

    RED-PROVED: with `_failure_class` stubbed to always answer
    `(FAILURE_ROOT, None)` this failed with

        AssertionError: billing failed behind meter reads and is reported as a
        root cause — the operator gets three reds and no first move
        assert 'root' == 'consequence'
    """
    tenant, _ = provisioned_tenant()
    _fake_every_seam(
        monkeypatch,
        raisers={
            "metering:seed_sample_reads": fixture.BlockCannotRun("the read batch will not post"),
            "billing:seed_sample_records": fixture.BlockCannotRun("no cycle to bill"),
            "payments:seed_sample_records": fixture.BlockCannotRun("no issued bill to pay"),
        },
    )

    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
        blocks = {f"{row['module']}:{row['block']}": row for row in sample_data.stored_blocks()}

    reads = blocks["metering:seed_sample_reads"]
    assert reads["failure_class"] == sample_data.FAILURE_ROOT
    assert reads["root_block"] is None

    billing = blocks["billing:seed_sample_records"]
    assert billing["failure_class"] == sample_data.FAILURE_CONSEQUENCE, (
        "billing failed behind meter reads and is reported as a root cause — "
        "the operator gets three reds and no first move"
    )
    assert billing["root_block"] == "metering:seed_sample_reads"

    # …and payments names the SAME root, two edges away, not merely billing.
    payments = blocks["payments:seed_sample_records"]
    assert payments["failure_class"] == sample_data.FAILURE_CONSEQUENCE
    assert payments["root_block"] == "metering:seed_sample_reads"
    assert payments["root_label"] == "Meter reads"


def test_cr039__an_unexplained_failure_stays_a_root(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """A block with no failing upstream is a ROOT, however late it runs.

    The direction matters: an unmarked failure is reported as something to look
    at, which is at worst noise, while a wrongly-marked CONSEQUENCE tells an
    operator to ignore a real, separate fault.

    RED-PROVED: with `_root_for` walking the DECLARED ORDER instead of the
    declared EDGES (every earlier failure counted as a cause) this failed with

        AssertionError: payments failed on its own and was blamed on an
        unrelated earlier block
        assert 'consequence' == 'root'
    """
    tenant, _ = provisioned_tenant()
    _fake_every_seam(
        monkeypatch,
        raisers={
            # identity is EARLIER in the declared order and no edge connects it
            # to payments. Order alone would make payments a consequence of it.
            "identity:seed_sample_records": fixture.BlockCannotRun("no active System Admin"),
            "payments:seed_sample_plan_payments": RuntimeError("something else entirely"),
        },
    )

    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
        blocks = {f"{row['module']}:{row['block']}": row for row in sample_data.stored_blocks()}

    plan_money = blocks["payments:seed_sample_plan_payments"]
    assert (
        plan_money["failure_class"] == sample_data.FAILURE_ROOT
    ), "payments failed on its own and was blamed on an unrelated earlier block"
    assert plan_money["error_code"] == sample_errors.CODE_UNEXPECTED


# ── 4 · the breakdown survives a reload, and the module line does not move ──
def test_cr039__the_block_breakdown_is_readable_after_the_run_is_over(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """Task 6 — *"a screen for the seeding outcome"* means AFTER the run too.

    A response an operator has already navigated away from is not a surface.
    The block lines must come back out of `sample_data_runs`, in planting
    order, with their counts and codes.

    ⚠ It also pins what did NOT change: `modules` is still BR-TEN-060's
    row-per-module line and `metering`'s two blocks still reconcile into one.

    RED-PROVED: with `_record` not writing the `blocks` column this failed with

        AssertionError: nothing about the individual blocks survived the run
        assert 0 == 11
    """
    tenant, _ = provisioned_tenant()
    _fake_every_seam(
        monkeypatch,
        counts=2,
        raisers={"metering:seed_sample_reads": fixture.BlockCannotRun("no meters")},
    )

    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
    # A separate context entry — nothing in memory from the run above.
    with tenant_ctx(tenant):
        summary = sample_data.run_summary()

    assert len(summary["blocks"]) == len(
        sample_data.SAMPLE_MODULES
    ), "nothing about the individual blocks survived the run"
    keys = [f"{row['module']}:{row['block']}" for row in summary["blocks"]]
    assert keys == [spec.key for spec in sample_data.SAMPLE_MODULES], (
        "the blocks are not in planting order, so a cascade cannot be read " "top to bottom"
    )
    reads = next(row for row in summary["blocks"] if row["block"] == "seed_sample_reads")
    assert reads["outcome"] == sample_data.OUTCOME_FAILED
    assert reads["error_code"] == sample_errors.CODE_PRECONDITION
    assert reads["retryable"] is True

    # BR-TEN-060 is UNMOVED: one row per module, worst-first, and metering's
    # blocks are all merged into ONE line.
    #
    # ⚠ **THE TWO FIGURES ARE DERIVED, NOT TYPED, SINCE 2026-09-01.** They read
    # `2` and `2` when metering owned exactly two blocks, and the PO's
    # third-cycle step gave it a third (`seed_sample_next_cycle_reads`) — so a
    # test pinning the RULE ("every block of a module reconciles into one line")
    # was failing on a NUMBER that the rule says nothing about. What is asserted
    # now is the rule: every metering block is on the line, and the count is the
    # sum of the ones that seeded.
    metering_blocks = [
        spec for spec in sample_data.SAMPLE_MODULES if spec.module == "metering"
    ]
    metering = models.SampleDataRun.objects.get(tenant=tenant, module="metering")
    assert metering.outcome == sample_data.OUTCOME_FAILED
    # every metering block except the one that raised wrote `counts=2`
    assert metering.seeded_count == 2 * (len(metering_blocks) - 1)
    assert len(metering.blocks) == len(metering_blocks)


# ── 5 · retry ONE block ────────────────────────────────────────────────────
def test_cr039__retry_runs_exactly_that_block_and_records_a_fresh_outcome(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """CR-039 wave B task 8 — the whole plant could be re-run; one block could not.

    The reads block fails, the operator fixes the named cause, and presses
    retry on that block. Exactly one seeder runs, its row is replaced, and the
    MODULE line recovers — a module row that could never improve would make the
    button a lie.

    RED-PROVED (before `retry_block` existed):

        AttributeError: module 'apps.tenancy.sample_data' has no attribute
        'retry_block'

    and once it existed but re-derived nothing:

        AssertionError: the module line never recovered, so the retry button
        cannot tell an operator anything
        assert 'failed' == 'seeded'
    """
    import apps.metering.services as metering_services

    tenant, _ = provisioned_tenant()
    calls = _fake_every_seam(
        monkeypatch,
        raisers={"metering:seed_sample_reads": fixture.BlockCannotRun("no meters")},
    )

    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
    assert calls["metering:seed_sample_reads"] == 1
    before = dict(calls)

    # The operator fixes the named cause.
    monkeypatch.setattr(metering_services, "seed_sample_reads", lambda actor: 9, raising=False)
    with tenant_ctx(tenant):
        result = sample_data.retry_block(
            admin_actor(), module="metering", block="seed_sample_reads"
        )

    assert result["block"]["outcome"] == sample_data.OUTCOME_SEEDED
    assert result["block"]["count"] == 9
    # EXACTLY that block: no other seeder was called a second time.
    assert {
        key: count for key, count in calls.items() if count != before.get(key)
    } == {}, "retrying one block re-ran another module's seeder"

    row = models.SampleDataRun.objects.get(tenant=tenant, module="metering")
    assert row.outcome == sample_data.OUTCOME_SEEDED, (
        "the module line never recovered, so the retry button cannot tell an " "operator anything"
    )
    # ⚠ DERIVED since 2026-09-01, for the reason given in the test above: this
    # read `10` when metering owned two blocks. One row per metering block that
    # is not the retried one, each writing the fake's `1`, plus the retry's 9.
    metering_blocks = [
        spec for spec in sample_data.SAMPLE_MODULES if spec.module == "metering"
    ]
    assert row.seeded_count == (len(metering_blocks) - 1) + 9
    assert row.reason_code is None
    assert "sample.block_retried" in audit_actions(audit_rows)


def test_cr039__a_retry_that_fails_again_records_the_new_failure(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """A retry is a report, not a promise — a second failure replaces the first.

    RED-PROVED: with `_rerecord_module` keeping the previous entry beside the
    new one this failed with

        AssertionError: the block has two entries in the ledger, so the panel
        would render the same block twice
        assert 2 == 1

    ⚠ **THE ASSERTION BELOW USED TO READ `len(row.blocks) == 1` AND HAD BEEN RED
    SINCE 2026-08-27 (`DEF-1090`).** `row` is the billing MODULE's ledger row,
    and billing owned exactly one block on the day this was written. CR-040 task
    C8 gave it `seed_sample_second_cycle` and task D13 gave it
    `seed_sample_correction`, so a full plant records three entries there and
    the assertion read `3 == 1` — over a product that was behaving perfectly.
    The sentence in its own failure message was always about the RETRIED BLOCK,
    never about the module, so what is asserted now is that sentence.

    ⚠ **AND THE SECOND ASSERTION IS THE ONE THAT KEEPS THE FIRST HONEST.** The
    lazy repair is to filter to one block and stop, which would also pass if a
    retry silently dropped the module's other two blocks from the ledger — the
    panel would then lose two lines and no test would object. Both counts are
    derived from `SAMPLE_MODULES`, so a fourth billing block leaves neither
    stale.
    """
    import apps.billing.services as billing_services

    tenant, _ = provisioned_tenant()
    _fake_every_seam(
        monkeypatch,
        raisers={"billing:seed_sample_records": fixture.BlockCannotRun("no bill template")},
    )
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())

    def still_broken(actor):
        raise fixture.BlockCannotRun("still no bill template")

    monkeypatch.setattr(billing_services, "seed_sample_records", still_broken, raising=False)
    with tenant_ctx(tenant):
        result = sample_data.retry_block(
            admin_actor(), module="billing", block="seed_sample_records"
        )

    assert result["block"]["outcome"] == sample_data.OUTCOME_FAILED
    row = models.SampleDataRun.objects.get(tenant=tenant, module="billing")
    retried = [entry for entry in row.blocks if entry["block"] == "seed_sample_records"]
    assert len(retried) == 1, (
        "the retried block has two entries in the ledger, so the panel would "
        "render the same block twice"
    )
    assert "still no bill template" in retried[0]["detail"]
    # …and the retry did not quietly take billing's OTHER blocks off the row.
    owned = {spec.seam for spec in sample_data.SAMPLE_MODULES if spec.module == "billing"}
    assert {entry["block"] for entry in row.blocks} == owned, (
        "the retry changed which blocks billing's ledger row carries — the panel "
        f"would lose a line. Expected {sorted(owned)}"
    )
    # …and the second failure left its own permanent trail row.
    assert len([r for r in audit_rows if r["action"] == "sample.block_failed"]) == 2


def test_cr039__retry_refuses_a_block_the_catalogue_does_not_hold(
    growth_plan, identity_seam, audit_rows
):
    """A typo must say so, never report success over a block that is not there.

    RED-PROVED: with `retry_block` returning the report for an unknown pair
    this failed with

        Failed: DID NOT RAISE UnknownSampleBlock
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant), pytest.raises(sample_data.UnknownSampleBlock):
        sample_data.retry_block(admin_actor(), module="billing", block="seed_everything")


def test_cr039__retry_refuses_without_tenant_context(growth_plan, identity_seam, audit_rows):
    """CLAUDE.md rule 1, deny-by-default — the same refusal the run makes.

    RED-PROVED: with the guard removed the refusal moved from a named one to
    a database crash three layers down —

        django.db.utils.IntegrityError: NOT NULL constraint failed:
        sample_data_runs.tenant_id

    which is the argument for the guard rather than merely a passing test: an
    unscoped write reaching the database at all is CLAUDE.md rule 1 being held
    up by a column definition.
    """
    from core.audit import AuditWriteError

    provisioned_tenant()
    with pytest.raises(AuditWriteError):
        sample_data.retry_block(
            SimpleNamespace(id=None), module="billing", block="seed_sample_records"
        )


# ── 6 · the vocabulary itself ──────────────────────────────────────────────
def test_cr039__every_failure_carries_a_code_from_the_vocabulary(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """Task "a stable error-code vocabulary" — no non-seeded block without one.

    `reason_code` stays the two coarse values BR-TEN-060 pinned
    (`seam_not_wired` / `exception`); the CODE is the countable one beside it.

    RED-PROVED: with `error_code` left off the seam-missing path this failed with

        AssertionError: identity:seed_sample_records did not load and carries
        no countable code
        assert False
         +  where False = <function is_known at 0x7efc9fcd82c0>(None)
    """
    import apps.identity.services as identity_services

    tenant, _ = provisioned_tenant()
    _fake_every_seam(
        monkeypatch,
        raisers={
            "rating:seed_sample_records": ValueError("boom"),
            "assets:seed_sample_records": fixture.BlockCannotRun("no units"),
        },
    )
    monkeypatch.delattr(identity_services, "seed_sample_records", raising=False)

    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
        blocks = {f"{row['module']}:{row['block']}": row for row in sample_data.stored_blocks()}

    for key, row in blocks.items():
        if row["outcome"] == sample_data.OUTCOME_SEEDED:
            assert row["error_code"] is None
            continue
        assert sample_errors.is_known(
            row["error_code"]
        ), f"{key} did not load and carries no countable code"
    assert blocks["identity:seed_sample_records"]["error_code"] == sample_errors.CODE_SEAM_MISSING
    assert blocks["rating:seed_sample_records"]["error_code"] == sample_errors.CODE_UNEXPECTED
    assert blocks["assets:seed_sample_records"]["error_code"] == sample_errors.CODE_PRECONDITION


def test_cr039__a_seeder_may_declare_its_own_code_and_a_made_up_one_is_ignored():
    """`BlockCannotRun(code=…)` is the declared route for a FINER code.

    The alternative — mining a finer code out of the sentence with regexes —
    would be a vocabulary nobody ratified, decided by string matching, and
    would break the first time a seeder reworded itself. An unregistered code
    is ignored rather than stored: a code with no catalogue entry has no
    audit-safe sentence, and `audit_log` has no delete.

    RED-PROVED: with `declared_code` accepting any string this failed with

        AssertionError: an unregistered code reached the ledger, so
        audit_safe_sentence has nothing to say about it
        assert 'SD-MADE-UP' == 'SD-PRECONDITION'
    """
    declared = fixture.BlockCannotRun("no template", code=sample_errors.CODE_REFUSED)
    assert sample_errors.classify(declared) == sample_errors.CODE_REFUSED

    invented = fixture.BlockCannotRun("no template", code="SD-MADE-UP")
    assert sample_errors.classify(invented) == sample_errors.CODE_PRECONDITION, (
        "an unregistered code reached the ledger, so audit_safe_sentence has "
        "nothing to say about it"
    )

    # And an ApiError's own catalogue code is NOT read as one of ours.
    from core import errors

    api_error = errors.ValidationError(errors.VAL_REQUIRED)
    assert sample_errors.classify(api_error) == sample_errors.CODE_REFUSED


def test_cr039__the_loop_still_continues_past_a_failure(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """The thing CR-039 says must NOT be "fixed": one module does not stop the rest.

    Pinned here because everything else in this file adds reporting AROUND that
    loop, and the cheapest way to break it is an audit write that raises.

    RED-PROVED: with `_audit_failed_block` re-raising instead of logging, the
    exploding sink below took the whole run down —

        RuntimeError: the trail is down

    …raised out of `seed_sample_data` itself, so the six blocks after `rating`
    never ran. One module stopping the rest, from an EXTRA trail row.
    """
    from core import audit as core_audit

    tenant, _ = provisioned_tenant()
    calls = _fake_every_seam(
        monkeypatch,
        raisers={"rating:seed_sample_records": RuntimeError("boom")},
    )

    def exploding_sink(row):
        if row["action"] == "sample.block_failed":
            raise RuntimeError("the trail is down")
        audit_rows.append(row)

    core_audit.set_audit_sink(exploding_sink)
    try:
        with tenant_ctx(tenant):
            summary = sample_data.seed_sample_data(admin_actor())
    finally:
        core_audit.set_audit_sink(audit_rows.append)

    # Every block after the failing one still ran…
    assert calls["payments:seed_sample_plan_payments"] == 1
    # …and the run-level row still landed, so rule 7's "the run was audited"
    # holds even when the extra per-block row could not be written.
    assert "sample.seeded" in audit_actions(audit_rows)
    assert summary["succeeded"] is False


# ── 7 · the HTTP half, because a service nothing can reach is not a feature ─
def test_cr039__the_report_endpoint_serves_the_blocks_and_says_when_it_cannot(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """`GET /settings/sample-data` carries the breakdown and `blocks_recorded`.

    Hard-won law 2 — built is not wired. Every assertion above is at the
    service layer, and a service the screen cannot reach is exactly the shape
    that ships green and does nothing (DEF-112, G23's whole subject).

    `blocks_recorded` is asserted in BOTH states because it exists only to keep
    them apart: empty-because-never-asked and empty-because-the-run-predates-
    the-column are different facts, and a screen that merges them is DEF-127
    one level down.

    RED-PROVED: with `blocks_recorded` left off the response this failed with

        KeyError: 'blocks_recorded'
    """
    from apps.tenancy.api import sample_data_runs
    from tests.test_us_ten_helpers import api_call

    tenant, _ = provisioned_tenant()

    never = api_call(sample_data_runs, "get", tenant=tenant, user=FakeUser(), role="system_admin")
    assert never.status_code == 200
    assert never.data["has_run"] is False
    assert never.data["blocks_recorded"] is False
    assert never.data["blocks"] == []

    _fake_every_seam(
        monkeypatch,
        raisers={"billing:seed_sample_records": fixture.BlockCannotRun("no bill template")},
    )
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())

    after = api_call(sample_data_runs, "get", tenant=tenant, user=FakeUser(), role="system_admin")
    assert after.data["has_run"] is True
    assert after.data["blocks_recorded"] is True
    billing = next(row for row in after.data["blocks"] if row["module"] == "billing")
    assert billing["error_code"] == sample_errors.CODE_PRECONDITION
    assert "no bill template" in billing["detail"]


def test_cr039__the_retry_endpoint_runs_the_block_and_refuses_a_bad_one(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """`POST /settings/sample-data/retry` — the wiring, all three answers.

    RED-PROVED: before the route existed, resolving it raised

        django.urls.exceptions.NoReverseMatch — and with the view present but
        the UnknownSampleBlock branch missing, a made-up block answered 200
        over a block the catalogue does not hold, which is DEF-016's shape.

    And the test's OWN first draft went red, which is worth keeping: it expected
    `pytest.raises(NotFoundError)` and got `Failed: DID NOT RAISE
    NotFoundError`, because `@api_view` turns every refusal into a B12
    envelope. See the comment at (2).
    """
    import apps.billing.services as billing_services
    from apps.tenancy.api import sample_data_retry
    from core import errors
    from tests.test_us_ten_helpers import api_call

    tenant, _ = provisioned_tenant()
    _fake_every_seam(
        monkeypatch,
        raisers={"billing:seed_sample_records": fixture.BlockCannotRun("no bill template")},
    )
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())

    # (1) a block the operator has fixed comes back seeded, through HTTP.
    monkeypatch.setattr(billing_services, "seed_sample_records", lambda actor: 4, raising=False)
    ok = api_call(
        sample_data_retry,
        "post",
        tenant=tenant,
        user=FakeUser(),
        role="system_admin",
        data={"module": "billing", "block": "seed_sample_records"},
    )
    assert ok.status_code == 200
    assert ok.data["block"]["outcome"] == sample_data.OUTCOME_SEEDED
    assert ok.data["block"]["count"] == 4
    assert ok.data["blocks_recorded"] is True

    # (2) a block nobody has is a 404, not a cheerful no-op.
    #
    # ⚠ ASSERTED ON THE RESPONSE, NOT WITH `pytest.raises`. The first draft of
    # this test expected the exception and went red with `Failed: DID NOT RAISE
    # NotFoundError` — because `@api_view` routes every refusal through
    # `core.errors.drf_exception_handler`, which is the whole point of the
    # envelope: a caller sees a STATUS and a code, never a traceback. A test
    # that asserted the exception would have been asserting something no client
    # can observe.
    missing = api_call(
        sample_data_retry,
        "post",
        tenant=tenant,
        user=FakeUser(),
        role="system_admin",
        data={"module": "billing", "block": "seed_everything"},
    )
    assert missing.status_code == 404

    # (3) a body naming nothing is a named validation refusal, not a 500.
    empty = api_call(
        sample_data_retry,
        "post",
        tenant=tenant,
        user=FakeUser(),
        role="system_admin",
        data={},
    )
    assert empty.status_code == 422
    assert empty.data["code"] == errors.VAL_REQUIRED
    assert {row["field"] for row in empty.data["field_errors"]} == {"module", "block"}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-039 wave B (12-governance/11-change-requests.md — "B · Say what happened")
# generated: 2026-08-26 by story-coder (CR-039 wave B lane)
# checklist: A✔ B=n/a(test file) C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: the real seeders are replaced by one-line fakes on EVERY block — what is under test is the ORCHESTRATOR's reporting, and a full estate takes minutes per test. The two tests that must run against the REAL seeders (does a real cascade mark itself correctly on a real tenant) are the walkthrough's, not a unit suite's, and are REPORTED as owed rather than faked here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
