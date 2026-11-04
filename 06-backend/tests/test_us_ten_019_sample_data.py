# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data: seed it, tag it, report
#           it, remove it)
# Rules:    BR-TEN-056 (stops at reads · tagged · background + honest report) ·
#           BR-TEN-057 (the tag is a column on the OWNING row) · BR-TEN-060 (an
#           unwired seam is a NAMED line, not a skip) · BR-TEN-061 (removal
#           order) · BR-TEN-063 (atomic per module, idempotent, audited) ·
#           BR-TEN-064 (never automatic — a human asks) · BR-TEN-013
# Note:     WHAT THESE TESTS CAN AND CANNOT ASSERT. Parts 1-3 of US-TEN-019 (the
#           sample RECORDS, the `is_sample` tag, the removal) are not built and
#           cannot be from this module — every table BR-TEN-057 names belongs to
#           apps/metering or apps/assets. So the TCs below assert the part that
#           IS tenancy's: that a run reports every unreachable module BY NAME,
#           records a machine-readable reason, refuses to call itself a success,
#           and stays isolated per tenant. TC-2/TC-6/TC-7/TC-8/TC-10 of the story
#           need the owning modules' seams and are named here as what they need
#           rather than faked — see test_us_ten_019_tc2_and_tc6__*.
# ───────────────────────────────────────────────────────
"""US-TEN-019 — the sample-data run ledger and its honest report."""

import ast
import pathlib

import pytest

from apps.tenancy import models, sample_data, services

from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    assert_rls_scoped,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (  # noqa: F401
    fake_module_seams,
    admin_actor,
    audit_actions,
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

SAMPLE_MODULE_NAMES = sorted({spec.module for spec in sample_data.SAMPLE_MODULES})


# ── TC-1 · provisioning ENQUEUES the plant, gated by the S111 toggle ────────
# ⚠ INVERTED 2026-08-17 (CR-010 new mandate 1). This test used to assert
# provisioning enqueued NOTHING, pinning BR-TEN-064's on-request trigger (PO
# 2026-08-10). The PO reversed that for NEW tenants on 2026-08-17, verbatim:
# *"TRANSACTION RECORDS — deliberately ZERO at provisioning - this is where
# youa re wrong; we need this seed data … we are offering free trials to
# utilities, they will not able to build all data on their own on day one"*.
# The RULE now under test: provisioning enqueues ONE plant job (the same
# orchestrator the S8 panel calls — never a second seeder), the S111
# load_defaults toggle governs it (BR-TEN-067: the toggle governs sample
# RECORDS), and the signup response never waits on the seeding itself — with
# the test broker off (JOBS_EAGER=False) the record rests `queued` and no
# sample row exists at commit time.
def test_us_ten_019_tc1__provisioning_enqueues_the_plant_behind_the_toggle(
    growth_plan, identity_seam, audit_rows
):
    tenant, result = provisioned_tenant()

    assert result["created"] is True
    from apps.tenancy.models import Job

    plants = Job.objects.filter(tenant_id=tenant.id, kind=sample_data.PLANT_JOB_KIND)
    assert plants.count() == 1, "a new tenant is planted — CR-010 new mandate 1"
    assert plants.first().status == "queued", (
        "JOBS_EAGER is off in the test settings, so the record rests queued — the "
        "signup response never waits on the seeding"
    )
    # …and nothing has actually seeded yet on this broker-less path.
    assert models.SampleDataRun.objects.filter(tenant=tenant).count() == 0
    assert "sample.seeded" not in audit_actions(audit_rows)


def test_us_ten_019_tc1b__the_s111_toggle_off_plants_nothing(
    growth_plan, identity_seam, audit_rows
):
    """BR-TEN-067's narrowing, applied to the new mandate: the structural
    catalogues seed either way, and the TOGGLE governs sample records — an
    unticked `load_defaults` means no plant job at all."""
    tenant, result = provisioned_tenant(
        lonestarridge_payload(load_defaults=False)
    )

    assert result["created"] is True
    from apps.tenancy.models import Job

    assert not Job.objects.filter(
        tenant_id=tenant.id, kind=sample_data.PLANT_JOB_KIND
    ).exists()
    assert models.SampleDataRun.objects.filter(tenant=tenant).count() == 0


def test_us_ten_019_tc1c__eager_plant_runs_the_orchestrator_and_c15_reports_short(
    growth_plan, identity_seam, audit_rows, settings, monkeypatch
):
    """The plant END TO END on an eager box, and C-15's soft check with it.

    JOBS_EAGER on (every dev/demo deployment) → the plant runs inside the
    signup call, through the SAME `seed_sample_data` the S8 panel uses, and a
    run ledger exists for every declared module at commit time. A short run is
    reported SOFTLY (PO ruling 15, 2026-08-17: *"soft: flag on the S62
    checklist + alert support, tenant still opens"*): the ledger rows are the
    S62 flag (BR-TEN-060), a `sample.seed_incomplete` audit row records the
    shortfall and whether a support alert could be delivered, and the tenant
    STILL OPENS — provisioning returned created=True.

    ⚠ **THE SHORTFALL IS NOW ARRANGED, AND UNTIL 2026-09-01 IT WAS AN ACCIDENT
    THIS TEST HAD MISTAKEN FOR A FIXTURE (DEF-566 / DEF-2395).** The old
    version of this case leaned on the identity seam stub: it wrote no `users`
    row, so identity's block could not create its two staff users, so the run
    was short — and this test asserted `"identity" in after["not_loaded"]` as
    though that were the designed state.

    **It was a defect, and asserting it kept it alive.** That stub was the head
    of the collapse three lanes lost an hour each to: on real PostgreSQL a
    harness tenant planted 16 of 17 blocks, and before the seeders had
    savepoints (DEF-2722, DEF-2795) billing and payments failed behind it, so
    the visible failure named the wrong module. A guard that asserts a bug is a
    guard that argues against its own fix.

    So the case now does BOTH halves honestly and they are worth more apart:

      * the eager plant lands **COMPLETE** — every declared block seeded, which
        is the assertion DEF-2722 says no suite in this repo ever made;
      * C-15 is then proved by **arranging** a shortfall — one module's seams
        removed outright — instead of inheriting one from a broken fixture.

    `assets` is the module broken, and it is chosen rather than picked: it owns
    exactly ONE block and nothing later in `SAMPLE_MODULES` declares a
    dependency on it, so the shortfall stays a single named line instead of a
    cascade this case would then have to reason about.

    ⚠ **BOTH HALVES GO THROUGH PROVISIONING, AND THE SECOND ONE HAS TO.**
    `sample.seed_incomplete` is written by `completeness_check`, which is called
    by `run_provisioning_plant` and NOT by `seed_sample_data` — so a second half
    that called the orchestrator directly would arrange a real shortfall, record
    it correctly in the ledger, and still find no C-15 row, which reads as the
    check being broken when it is the test asking the wrong object. Two tenants,
    both provisioned eagerly, is the honest shape.
    """
    settings.JOBS_EAGER = True
    tenant, result = provisioned_tenant(
        brazosbend_payload(subdomain="brazosbend-eager")
    )

    assert result["created"] is True, "C-15 is SOFT — the tenant opens regardless"
    from apps.tenancy.models import Job

    job = Job.objects.get(tenant_id=tenant.id, kind=sample_data.PLANT_JOB_KIND)
    assert job.status == "succeeded", (
        "a SHORT run is a succeeded JOB with named ledger rows — the job fails only "
        f"when the orchestrator itself cannot run (status={job.status}, error={job.error})"
    )
    stored = models.SampleDataRun.objects.filter(tenant=tenant)
    assert set(stored.values_list("module", flat=True)) == set(SAMPLE_MODULE_NAMES)

    actions = audit_actions(audit_rows)
    assert "sample.seeded" in actions

    # HALF ONE — the plant that just ran at provisioning landed COMPLETE.
    with tenant_ctx(tenant):
        summary = sample_data.run_summary()
    assert summary["not_loaded"] == [], (
        "a freshly provisioned tenant's sample set came up SHORT, and everything "
        "downstream of the first gap is empty for whoever is trying the product "
        "(DEF-2722). Read the FIRST line below, not the last — the rest may be its "
        f"consequence: {summary['not_loaded']}"
    )
    assert summary["succeeded"] is True
    assert not [row for row in audit_rows if row["action"] == "sample.seed_incomplete"], (
        "the run was COMPLETE, so C-15 must stay quiet — a shortfall row here means "
        "the check now fires on a healthy tenant, which is how an alert stops being read"
    )

    # HALF TWO — C-15 on an ARRANGED shortfall, through the same door: a SECOND
    # tenant provisioned with the assets seam removed.
    fake_module_seams(monkeypatch, "assets", unwired=("seed_sample_records",))
    _, short_result = provisioned_tenant(
        brazosbend_payload(subdomain="brazosbend-short")
    )
    assert short_result["created"] is True, "C-15 is SOFT — the tenant opens regardless"

    incomplete = [row for row in audit_rows if row["action"] == "sample.seed_incomplete"]
    assert len(incomplete) == 1, (
        "one of the two tenants planted SHORT and C-15 must say so exactly once — "
        f"got {len(incomplete)} row(s)"
    )
    after = incomplete[0]["after"]
    assert "assets" in after["not_loaded"], after["not_loaded"]
    # DEF-2377 — was `after["s62_flag"]`, whose value read "the named
    # sample_data_runs rows this run stored (BR-TEN-060)". The Product Owner read
    # that sentence on the deployed audit log: a rule id and a table name in copy
    # written for a clerk. The row still records that the owner is told; it now
    # says so in words a person can read.
    told = after["what_the_owner_sees"]
    assert "setup screen" in told, told
    assert "BR-" not in told and "sample_data_runs" not in told, told
    assert after["support_alert"], "delivered or not, the answer is recorded"


# ── TC-5 · an unwired module is NAMED (BR-TEN-060, DEF-016) ─────────────────
def test_us_ten_019_tc5__every_unreachable_module_is_named_with_a_reason(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """US-TEN-019 TC-5 — the defect this story exists to prevent, asserted.

    DEF-016 was a skip that went into a summary nobody read. A module that
    cannot be reached gets its own row with a machine-readable `reason_code` and
    a sentence naming the missing function, and the run does NOT report success.

    ⚠ AMENDED 2026-08-16 (DEF-153 closed, DEF-166 fix). This test used to assert
    that **every** module was unreachable and `seeded_total == 0`, because on the
    day it was written no owning module published the seam at all. Seven modules
    publish it now, so that assertion described a state the product had left —
    it was not testing BR-TEN-060, it was pinning the absence of an
    implementation. The RULE is unchanged and is what is asserted here: take one
    seam away and that module is NAMED, with its dotted path, while the rest
    load. Removing a seam rather than removing the assertion is the difference
    between testing the rule and testing the calendar.
    """
    import apps.assets.services as assets_services

    tenant, _ = provisioned_tenant()
    monkeypatch.delattr(assets_services, "seed_sample_records", raising=False)

    with tenant_ctx(tenant):
        summary = sample_data.seed_sample_data(admin_actor())

    assert summary["succeeded"] is False, "a run with any skip must not report success"
    named = {row["module"] for row in summary["not_loaded"]}
    assert "assets" in named, "the module whose seam was removed must be NAMED"
    unwired = [
        row
        for row in summary["not_loaded"]
        if row["reason_code"] == sample_data.REASON_SEAM_NOT_WIRED
    ]
    assert [row["module"] for row in unwired] == ["assets"]
    for row in unwired:
        # NAMED, not counted: the operator gets the missing function's dotted
        # path and the columns BR-TEN-057 still needs.
        assert f"apps.{row['module']}.services." in row["detail"]
        assert "is_sample" in row["detail"]

    stored = models.SampleDataRun.objects.filter(tenant=tenant)
    assert stored.count() == len(SAMPLE_MODULE_NAMES)
    by_module = {row.module: row for row in stored}
    assert by_module["assets"].outcome == sample_data.OUTCOME_SKIPPED
    assert by_module["rating"].outcome == sample_data.OUTCOME_SEEDED


def test_us_ten_019_tc5b__the_report_is_advisory_and_does_not_count_as_progress(
    growth_plan, identity_seam, audit_rows
):
    """BR-TEN-060's second half: the S62 line is ADVISORY.

    BR-TEN-015's completion predicate is "the underlying fields are filled", and
    no operator action can wire a seam — counting an unwired module against a
    checklist the operator is being asked to complete would ask them for
    something they cannot do."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        summary = sample_data.seed_sample_data(admin_actor())
    assert summary["counts_toward_progress"] is False


# ── TC-9 · replay (BR-TEN-063 idempotency) ─────────────────────────────────
def test_us_ten_019_tc9__replay_changes_no_count_and_writes_no_duplicate_row(
    growth_plan, identity_seam, audit_rows
):
    """US-TEN-019 TC-9 — a second run creates nothing and duplicates no row.

    UNIQUE (tenant, module) is what makes this true at the database rather than
    in the loop: `update_or_create` keyed on it means a replay refreshes the
    outcome instead of accumulating a history nobody reads.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
        first = list(
            models.SampleDataRun.objects.filter(tenant=tenant)
            .order_by("module")
            .values_list("module", "outcome", "reason_code")
        )
        sample_data.seed_sample_data(admin_actor())
        second = list(
            models.SampleDataRun.objects.filter(tenant=tenant)
            .order_by("module")
            .values_list("module", "outcome", "reason_code")
        )
    assert first == second
    assert models.SampleDataRun.objects.filter(tenant=tenant).count() == len(SAMPLE_MODULE_NAMES)


# ── BR-TEN-016 / rule 7 · the run is audited even when it seeds nothing ────
def test_us_ten_019_tc9b__the_run_is_audited_with_its_counts(
    growth_plan, identity_seam, audit_rows
):
    """BR-TEN-063: `sample.seeded` with counts, every run.

    Written even when every count is zero — "we ran and seeded nothing" is the
    fact an operator needs and the one a silent job never records."""
    tenant, _ = provisioned_tenant()
    audit_rows.clear()
    with tenant_ctx(tenant):
        summary = sample_data.seed_sample_data(admin_actor())
    rows = [row for row in audit_rows if row["action"] == "sample.seeded"]
    assert len(rows) == 1
    # ⚠ AMENDED 2026-08-16: the assertion was `seeded_total == 0` and *"every
    # module not loaded"*, which was true only while no module implemented the
    # seam. The RULE — one audit row per run, carrying THE RUN'S OWN counts,
    # written even when a count is zero — is asserted against the summary the
    # run returned, so it stays true as blocks land and as they break.
    assert rows[0]["after"]["seeded_total"] == summary["seeded_total"]
    assert rows[0]["after"]["succeeded"] == summary["succeeded"]
    assert {entry["module"] for entry in rows[0]["after"]["not_loaded"]} == {
        entry["module"] for entry in summary["not_loaded"]
    }
    assert summary["seeded_total"] > 0, "the seams are wired now — a run that loads nothing is a bug"


# ── the seam is really consulted, not a constant (RED-proof, mechanised) ───
def test_us_ten_019_tc5c__a_wired_seam_flips_that_modules_row_to_seeded(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """The report reads the SEAM, not a hardcoded "everything is skipped".

    This is the RED-proof of the previous three tests, kept as a test: wire fake
    seeders on apps.metering.services and metering's row flips to `seeded` with
    its count — while the other modules stay named. If `seed_sample_data` ever
    short-circuits to "all skipped", this goes red.

    Metering owns SEVERAL blocks and the ledger key is (tenant, module), so
    every one must be wired for the module to report seeded — and the counts
    ADD UP. How many there are is asked, not typed.
    """
    import apps.assets.services as assets_services

    tenant, _ = provisioned_tenant()
    # ⚠ AMENDED 2026-08-16: the fakes took NO argument, because the seam took
    # none when this was written. It carries the ACTOR now (BR-TEN-064 — a human
    # asks, and every service the seeder drives audits who), so a zero-argument
    # fake fails with `TypeError: <lambda>() takes 0 positional arguments but 1
    # was given` — a stale test, not a broken product.
    # ⚠ **AMENDED AGAIN 2026-09-01 — THE SEAMS ARE NO LONGER NAMED HERE
    # (`DEF-2964`).** This listed metering's blocks by hand and asserted
    # `7 + 3 = 10`; metering went to three blocks that morning and to four by
    # the afternoon, and this test went red both times for a reason its own
    # docstring says nothing about. It asks `SAMPLE_MODULES` which blocks
    # metering owns now, and derives the total from the answer.
    metering_blocks = fake_module_seams(monkeypatch, "metering", count=7)
    # …and assets is genuinely unwired, so "one module skipped" is still the
    # state under test rather than an accident of what had been built that day.
    monkeypatch.delattr(assets_services, "seed_sample_records", raising=False)

    with tenant_ctx(tenant):
        summary = sample_data.seed_sample_data(admin_actor())

    by_module = {row.module: row for row in models.SampleDataRun.objects.filter(tenant=tenant)}
    assert by_module["metering"].outcome == sample_data.OUTCOME_SEEDED
    assert by_module["metering"].seeded_count == 7 * len(metering_blocks)
    assert by_module["metering"].reason_code is None
    assert by_module["assets"].outcome == sample_data.OUTCOME_SKIPPED
    # …and one wired module does not make the RUN a success (BR-TEN-056 (3)).
    assert summary["succeeded"] is False


def test_us_ten_019_tc5e__a_module_with_one_unwired_block_is_not_reported_seeded(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """Worst-first merge: metering's two blocks reconcile into ONE honest row.

    Wire the premises side and leave READS unwired — the state metering will
    genuinely pass through — and the module must NOT read `seeded`. A row saying
    seeded because the earlier block happened to work is the DEF-016 sentence in
    a smaller font: a real gap, reported as a success. The count it did write is
    still carried, because that part is true.
    """

    tenant, _ = provisioned_tenant()
    # ⚠ AMENDED 2026-09-01 (`DEF-2964`): the reads seam is named as the ONE
    # unwired block and every other metering block is faked, whatever they are.
    # Naming the wired ones by hand is what broke this test twice — and leaving
    # one unfaked was worse than noise: it ran for real against a tenant with no
    # estate and refused, so the module read `failed` where this test arranges
    # `skipped`, and worse-first hid the fact under test.
    metering_blocks = fake_module_seams(
        monkeypatch, "metering", count=7, unwired=("seed_sample_reads",)
    )

    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())

    row = models.SampleDataRun.objects.get(tenant=tenant, module="metering")
    assert row.outcome == sample_data.OUTCOME_SKIPPED
    assert row.reason_code == sample_data.REASON_SEAM_NOT_WIRED
    assert "seed_sample_reads" in row.detail
    # DERIVED (`DEF-2964`): every metering block except the unwired one wrote 7.
    assert row.seeded_count == 7 * (len(metering_blocks) - 1)


def test_us_ten_019_tc9c__a_fresh_run_does_not_inherit_yesterdays_verdict(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """The merge is WITHIN a run, never across runs.

    A module fixed since the last run must be able to report seeded again —
    BR-TEN-063's idempotency means a replay changes no count, not that it
    freezes an old verdict into place.
    """
    import apps.metering.services as metering_services

    tenant, _ = provisioned_tenant()
    real_records = metering_services.seed_sample_records
    real_reads = metering_services.seed_sample_reads
    with tenant_ctx(tenant):
        # ⚠ AMENDED 2026-08-16: "everything skipped" used to be the state of the
        # world; it now has to be ARRANGED, because metering publishes both
        # seams. The test's subject is unchanged — a verdict does not carry
        # across runs — and it is stronger this way: the module is genuinely
        # repaired between the two runs rather than merely appearing later.
        # ⚠ AMENDED 2026-09-01 (`DEF-2964`) — every metering block, asked for
        # rather than listed, or "metering unreachable" is not the state this
        # test arranges.
        metering_blocks = fake_module_seams(
            monkeypatch,
            "metering",
            unwired=tuple(
                spec.seam
                for spec in sample_data.SAMPLE_MODULES
                if spec.module == "metering"
            ),
        )
        sample_data.seed_sample_data(admin_actor())  # metering unreachable
        assert (
            models.SampleDataRun.objects.get(tenant=tenant, module="metering").outcome
            == sample_data.OUTCOME_SKIPPED
        )
        fake_module_seams(monkeypatch, "metering", count=7)
        sample_data.seed_sample_data(admin_actor())
    del real_records, real_reads

    row = models.SampleDataRun.objects.get(tenant=tenant, module="metering")
    assert row.outcome == sample_data.OUTCOME_SEEDED
    # DERIVED (`DEF-2964`): this read `10` when metering owned two blocks and
    # `12` when it owned three. It asks how many there are now.
    assert row.seeded_count == 7 * len(
        metering_blocks
    ), "a fresh run recounts; it does not accumulate across runs"


def test_us_ten_019_tc10__one_module_failing_does_not_stop_the_others(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """US-TEN-019 TC-10 (adapted) — BR-TEN-063's atomic-PER-MODULE posture.

    The story's TC-10 kills the job between two modules; the rule underneath is
    that each module's block is its own transaction so one cannot roll back the
    rest. Asserted by making one module's seeder raise: its row records
    `failed / exception` with the exception CLASS, and every other module is
    still recorded.
    """
    import apps.assets.services as assets_services

    def explode(actor):
        raise RuntimeError("assets sample block crashed")

    tenant, _ = provisioned_tenant()
    monkeypatch.setattr(assets_services, "seed_sample_records", explode, raising=False)
    # ⚠ AMENDED 2026-09-01 (`DEF-2964`) — every metering block, so this test
    # still measures "one module failing does not stop the others" rather than
    # metering failing for a reason it never arranged.
    fake_module_seams(monkeypatch, "metering", count=4)

    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())

    by_module = {row.module: row for row in models.SampleDataRun.objects.filter(tenant=tenant)}
    assert by_module["assets"].outcome == sample_data.OUTCOME_FAILED
    assert by_module["assets"].reason_code == sample_data.REASON_EXCEPTION
    # ⚠ AMENDED 2026-08-16 (DEF-166): the stored detail was the exception CLASS
    # and nothing else, so a block that said in one careful sentence exactly
    # what was wrong reached the operator as the single word `BizError`.
    # BR-TEN-060 asks for *"a sentence an operator can act on"*. The class name
    # is kept in front, because a bare message loses the clue.
    assert by_module["assets"].detail == "RuntimeError: assets sample block crashed"
    assert by_module["metering"].outcome == sample_data.OUTCOME_SEEDED
    assert set(by_module) == set(SAMPLE_MODULE_NAMES)


# ── TC-3 (neg) · the sample set stops before every money table ─────────────
def test_us_ten_019_tc3__no_code_path_here_imports_a_money_module(
    growth_plan, identity_seam, audit_rows
):
    """US-TEN-019 TC-3 — BR-TEN-056 clause 1, asserted on the IMPORTS.

    The story's own wording is *"no code path in the job imports those modules'
    write services at all"*. Counting rows in `invoices` would pass trivially
    while the boundary was one import away; parsing this module's imports is the
    assertion the rule actually makes. A sample row in an append-only table
    could never be removed and would have to be excluded from every financial
    report forever, which is why the boundary is absolute.
    """
    source = pathlib.Path(sample_data.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    for module in sample_data.FORBIDDEN_MODULES:
        assert not any(
            name.startswith(f"apps.{module}") for name in imported
        ), f"apps.{module} is inside the money boundary BR-TEN-056 clause 1 draws"


# ── TC-6/TC-2 · what removal would do, and why it does nothing today ───────
def test_us_ten_019_tc2_and_tc6__records_and_removal_are_reported_not_faked(
    growth_plan, identity_seam, audit_rows
):
    """US-TEN-019 TC-2 + TC-6 — the parts this module CANNOT build, named.

    TC-2 expects tagged rows and TC-6 expects them removed in BR-TEN-061's
    order.

    ⚠ AMENDED 2026-08-16 (DEF-153 closed). This used to assert `removable == 0`
    and *"every module blocked"*, because on the day it was written no owning
    module published the seam and the honest substitute was to say so. The
    modules publish them now, so a run really does write rows and the plan
    really can count them. What has NOT changed, and is what this test is for,
    is BR-TEN-061's ORDER — asserted verbatim below so the lane that changes it
    changes the RULE and not a remembered version of it.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
        plan = sample_data.removal_plan()

    assert plan["removable"] > 0, "a loaded tenant has sample rows to remove"
    for row in plan["blocked"]:
        assert row["reason_code"] == sample_data.REASON_SEAM_NOT_WIRED
        assert "is_sample" in row["detail"]

    # BR-TEN-061's order, exactly: reads first, premises last, because B2
    # declares no ON DELETE CASCADE on any of these FKs.
    assert plan["order"][0] == "meter_reads"
    assert plan["order"][-1] == "premises"
    assert plan["order"].index("units") < plan["order"].index("premises")
    assert plan["order"].index("assets") < plan["order"].index("service_points")
    assert plan["order"].index("accounts") < plan["order"].index("asset_assignments")
    assert len(plan["order"]) == 12


# ── TC-4 · reference vocabulary is NOT sample data (BR-TEN-058) ────────────
def test_us_ten_019_tc4__a_run_never_touches_the_reference_catalogues(
    growth_plan, identity_seam, audit_rows
):
    """US-TEN-019 TC-4 — BR-TEN-058: the catalogues arrive by a different
    mechanism, carry no `is_sample`, and removal never touches them.

    Asserted the way it will still be true when the seams land: the run's own
    ledger names no reference list, and the reference-data report is unchanged
    to the row across a run."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        before = {row["list"]: row["count"] for row in services.reference_data_report()["lists"]}
        sample_data.seed_sample_data(admin_actor())
        after = {row["list"]: row["count"] for row in services.reference_data_report()["lists"]}
    assert after == before
    recorded = set(
        models.SampleDataRun.objects.filter(tenant=tenant).values_list("module", flat=True)
    )
    assert recorded.isdisjoint({code for code, _ in services.SEED_LIST_OWNERS})


# ── the DEF-016 constraint: a skip with no reason is refused by the DB ─────
def test_us_ten_019_tc5d__a_reasonless_skip_cannot_be_stored(
    growth_plan, identity_seam, audit_rows
):
    """`ck_sample_run_reason_required` is BR-TEN-060 in the schema.

    The rule "an unwired seam is a NAMED line, not a skip" is only as strong as
    the weakest writer. A CHECK constraint means a future lane cannot record a
    reasonless skip even by accident — which is the difference between a rule
    and a convention."""
    from django.db import IntegrityError, transaction

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant), pytest.raises(IntegrityError):
        with transaction.atomic():
            models.SampleDataRun.objects.create(
                tenant=tenant, module="metering", outcome="skipped", reason_code=None
            )


# ── TC-12 (neg) · production: the job RUNS, seed_demo refuses (BR-TEN-064) ─
def test_us_ten_019_tc12__runs_under_production_settings_and_mints_no_credential(
    growth_plan, identity_seam, audit_rows, settings
):
    """US-TEN-019 TC-12 — three assertions, not one; the guard differs per path.

    (a) provisioning alone seeds nothing — TC-1 above. (b) the operator's action
    RUNS under production settings and creates no tenant, user, credential or
    subscription. (c) `seed_demo` still refuses, because it mints a fixture
    tenant with a PUBLISHED owner password, which this job does not.
    """
    from django.core.management import call_command
    from django.core.management.base import CommandError

    tenant, _ = provisioned_tenant()
    settings.SETTINGS_MODULE = "config.settings.production"
    tenants_before = models.Tenant.objects.count()
    subs_before = models.Subscription.objects.count()

    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())  # runs — no refusal

    assert models.Tenant.objects.count() == tenants_before
    assert models.Subscription.objects.count() == subs_before
    assert len(identity_seam.provisioned) == 1  # no new owner user

    with pytest.raises(CommandError) as caught:
        call_command("seed_demo")
    assert "refuses under production settings" in str(caught.value)


# ── TC-11 (isolation) · one tenant's run can never see another's ──────────
@pytest.mark.isolation
@requires_postgres
def test_us_ten_019_tc11__sample_runs_are_rls_scoped_and_deny_by_default(
    growth_plan, identity_seam, audit_rows, rls
):
    """US-TEN-019 TC-11 — asserted through the DATABASE under the non-superuser
    probe role, so the policy is genuinely consulted.

    Three proofs: Lone Star sees ZERO of Brazos Bend's run rows; with NO tenant
    context the table is denied outright; and running the job for one tenant
    leaves the other's rows unchanged to the row. The third is the one that
    matters for the removal this ledger will one day describe — a predicate-
    driven DELETE with no policy is data loss in somebody else's account.
    """
    brazos, _ = provisioned_tenant(brazosbend_payload())
    lonestar, _ = provisioned_tenant(lonestarridge_payload())

    with tenant_ctx(brazos):
        sample_data.seed_sample_data(admin_actor())
    # Each count is taken under ITS OWN tenant's context. Contextless they all
    # return 0 on a connection row-level security applies to, which would make
    # `lonestar_before == 0` true for the wrong reason and the `exists()` below
    # false for the wrong reason.
    with tenant_ctx(lonestar):
        lonestar_before = models.SampleDataRun.objects.filter(tenant=lonestar).count()
    assert lonestar_before == 0

    with tenant_ctx(brazos):
        assert models.SampleDataRun.objects.filter(tenant=brazos).exists()
    assert_rls_scoped(rls, "sample_data_runs", owner=brazos, intruder=lonestar)
    assert_denied_without_context(rls, "sample_data_runs")

    with tenant_ctx(lonestar):
        sample_data.seed_sample_data(admin_actor())
    with tenant_ctx(brazos):
        assert models.SampleDataRun.objects.filter(tenant=brazos).count() == len(
            SAMPLE_MODULE_NAMES
        )
    with tenant_ctx(lonestar):
        assert models.SampleDataRun.objects.filter(tenant=lonestar).count() == len(
            SAMPLE_MODULE_NAMES
        )


def test_us_ten_019_tc11b__a_run_with_no_tenant_context_is_refused(
    growth_plan, identity_seam, audit_rows
):
    """Deny-by-default at the app layer too (CLAUDE.md rule 1, BR-TEN-003): a
    caller who forgot the context gets a refusal, never a global run."""
    provisioned_tenant()
    with pytest.raises(Exception) as caught:
        sample_data.seed_sample_data(admin_actor())
    assert "tenant context" in str(caught.value)


# ══════════════════════════════════════════════════════════════════════════
# US-TEN-019's SURFACE — added 2026-08-16 by the unreachable-screens lane.
#
# The engine above shipped 2026-08-15 with `E=deferred(no-frontend-half)` and
# no API half either, which is the DEF-112 shape G23 counts: an orchestrator a
# human could not ask anything. These TCs cover the removal ACTION and the
# three endpoints that carry it, and the assertion that matters most in all of
# them is the negative one — a removal that removes nothing must still be
# recorded, and must never come back looking like a success.
# ══════════════════════════════════════════════════════════════════════════
def test_us_ten_019_tc6b__asking_to_remove_is_audited_even_when_it_removes_nothing(
    growth_plan, identity_seam, audit_rows
):
    """BR-TEN-066 + CLAUDE.md rule 7 — the operator asked, and that survives.

    A no-op that writes no audit row is how an operator ends up believing the
    demo data is gone. The row has to exist precisely BECAUSE nothing was
    deleted."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        # ⚠ AMENDED 2026-08-16: the seams are wired, so "removes nothing" is now
        # the state of a tenant that was NEVER LOADED — which is the case the
        # rule is about. Nothing was seeded here on purpose.
        audit_rows.clear()
        result = sample_data.remove_sample_data(admin_actor())

    assert result["removed"] == 0
    assert result["requested"] is True

    rows = [row for row in audit_rows if row["action"] == "sample.removed"]
    assert len(rows) == 1, "a removal that removed nothing still has to be recorded"
    assert rows[0]["after"]["removed"] == 0


def test_us_ten_019_tc6c__removal_refuses_without_tenant_context(
    growth_plan, identity_seam, audit_rows
):
    """Deny-by-default, same as the seed half (CLAUDE.md rule 1, BR-TEN-003)."""
    provisioned_tenant()
    with pytest.raises(Exception) as caught:
        sample_data.remove_sample_data(admin_actor())
    assert "tenant context" in str(caught.value)


def test_us_ten_019_tc13__the_report_distinguishes_never_asked_from_nothing_loaded(
    growth_plan, identity_seam, audit_rows
):
    """The DEF-127 posture, at the story level.

    `seeded_total == 0` is TRUE both for a tenant that has never run the job and
    for one that ran it and loaded nothing — two different facts. The screen
    must not merge them into one zero, so the payload carries `has_run` as its
    own boolean and the endpoint sends it.
    """
    import apps.assets.services as assets_services

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        before = sample_data.run_summary()
        assert before["modules"] == [], "a fresh tenant has no run ledger at all"
        assert before["seeded_total"] == 0
        assert before["succeeded"] is False

        # ⚠ AMENDED 2026-08-16: the two facts this test separates are "never
        # asked" and "asked, and a block did not load". The second used to be
        # the state of every module by default; it is now ARRANGED by taking one
        # seam away, which is what the test always meant.
        original = getattr(assets_services, "seed_sample_records", None)
        if original is not None:
            delattr(assets_services, "seed_sample_records")
        try:
            sample_data.seed_sample_data(admin_actor())
        finally:
            if original is not None:
                assets_services.seed_sample_records = original
        after = sample_data.run_summary()

    # Same zero on one block, different fact: now there IS a ledger, and it
    # names why that block did not load.
    assert after["succeeded"] is False
    assert {row["module"] for row in after["modules"]} == set(SAMPLE_MODULE_NAMES)
    assert "assets" in {row["module"] for row in after["not_loaded"]}
    for row in after["not_loaded"]:
        assert row["detail"], "a not-loaded module without a reason is a silent skip"
