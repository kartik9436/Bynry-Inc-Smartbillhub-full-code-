# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03) · S114 post-commit state (CR-017)
# Change:   CR-064 (12-governance/11-change-requests.md), PO 2026-09-02 —
#           *"During tenent creation - when we are at the screen where we seed
#           data in backround job, can you show all 17 step - -list down all 17
#           steps and show 1 by 1 when they finish - if step breaks - then show
#           the reason behind it at that step itself , if you skip the step,
#           then show the reason for that step also - this will help us to
#           understand why it is breaking down in real time, you ahve to
#           provide specific error on the screen itself"*
# Defects:  DEF-3280 (the plant records which step it is on and the poll
#           endpoint threw it away — CR-064 task A2)
# Rules:    BR-TEN-060 (an unwired seam is a NAMED line, not a skip) ·
#           BR-TEN-063 (atomic per module, idempotent) · CLAUDE.md rule 1
# ───────────────────────────────────────────────────────
"""CR-064 tasks A1 · A2 · A3 · A4 — the seventeen steps, served.

EVERY TEST HERE WAS PROVED RED BEFORE IT WAS TRUSTED GREEN (hard-won law 7).
The failure each one produced against the un-fixed code is quoted in its own
docstring, so a later reader can tell a genuine assertion from a vacuous one.

⚠ **THE ONE THAT MATTERS MOST IS `tc4`, AND IT WAS WRITTEN BEFORE THE SCREEN.**
CR-064's own sizing section says the genuine risk in this change is the
opposite of the obvious one: *"a step list that reports Done because a row is
missing would be worse than the three lines it replaces"*. A step nothing has
recorded reads `not_started`, and it is asserted here rather than left to the
screen to get right.
"""

import uuid

import pytest

from apps.tenancy import sample_data, selectors
from core import jobs as core_jobs
from core import tenancy as core_tenancy

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    admin_actor,
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


@pytest.fixture()
def plant_tenant():
    """A really-provisioned tenant, through the real service.

    `provisioned_tenant` is a HELPER FUNCTION, not a fixture (it returns the
    row and the whole provisioning result), so it is wrapped here rather than
    named in a signature — which is how a first draft of this file collected
    six `fixture 'provisioned_tenant' not found` errors before it ran a single
    assertion.
    """
    tenant, _result = provisioned_tenant()
    return tenant


def _position_of(key: str) -> int:
    """Where a block sits in the estate today — its 1-based index, never a literal.

    ⚠ **DEF-3320 IS WHY THIS EXISTS, AND THE FAILURE IS SHARPER THAN A COUNT
    GOING UP.** `CR-062`'s Municipal-discount block was **INSERTED AT POSITION
    6**, not appended, because an enrolment needs an account to grant to. An
    insertion moves every step after it, so two positional literals in this file
    (`broken["position"] == 6`, `skipped["position"] == 17`) became wrong at the
    same moment — and one of them was wrong about a step whose position had not
    changed at all, which is the sort of thing a reader spends an hour on.

    A position is ALLOCATION and not law: the block's `key` is its identity, and
    `step_catalogue()`'s own docstring says so in terms (*"the row identity a
    client keys on is `key` (`module:seam`, a stable name)"*). So the assertions
    ask this function where the key sits rather than remembering a number.
    """
    keys = [spec.key for spec in sample_data.SAMPLE_MODULES]
    assert key in keys, f"{key} is not a block of the sample estate"
    return keys.index(key) + 1


def _fake_every_seam(monkeypatch, *, counts: int = 1, raisers: dict | None = None) -> dict:
    """A controlled one-line fake on every block's seam. See CR-039's copy.

    The real seeders plant a whole estate and take minutes; what is under test
    here is what the ORCHESTRATOR RECORDS and what the POLL SERVES, so each
    block becomes a fake that either returns a count or raises.
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


# ── A1 · the catalogue, before anything has run ────────────────────────────
def test_cr064_tc1_the_catalogue_is_seventeen_in_source_order():
    """*"list down all 17 steps"* — the PO's number is the code's number.

    Asserted against `SAMPLE_MODULES` itself rather than against a list typed
    here: a check carrying its own copy of the thing it polices agrees only
    with itself, which is how the signup screen offered six services for ten
    days after eleven were ruled (G47's whole argument).

    RED-PROVED at commit 02abfa48, before `step_catalogue()` existed:

        E       AttributeError: module 'apps.tenancy.sample_data' has no
                attribute 'step_catalogue'
        tests/test_cr064_seventeen_steps.py:106: AttributeError
    """
    catalogue = sample_data.step_catalogue()

    # ⚠ **DERIVED, AND THIS CASE'S OWN DOCSTRING SAID SO WHILE THE LINE BELOW
    # DID THE OPPOSITE (DEF-3320).** It read `== 17` and `range(1, 18)`, so a
    # case whose whole argument is *"a check carrying its own copy of the thing
    # it polices agrees only with itself"* was carrying two copies of the count.
    # `SAMPLE_MODULES` gained the Municipal-discount block on 2026-09-02 and
    # this file went red for a change it is not about.
    steps = len(sample_data.SAMPLE_MODULES)
    assert len(catalogue) == steps
    assert [row["key"] for row in catalogue] == [spec.key for spec in sample_data.SAMPLE_MODULES]
    assert [row["position"] for row in catalogue] == list(range(1, steps + 1))
    # Every entry names its own module, seam, label and tables — the four facts
    # a screen needs to draw a numbered row with nothing seeded yet.
    for row, spec in zip(catalogue, sample_data.SAMPLE_MODULES, strict=True):
        assert row["module"] == spec.module
        assert row["block"] == spec.seam
        assert row["label"] == spec.label
        assert row["tables"] == list(spec.tables)


def test_cr064_tc2_the_catalogue_needs_no_run_and_carries_no_outcome():
    """A1: *"a client can render seventeen named, numbered rows with nothing
    seeded yet"*. It is a TUPLE in source order, so it answers with no tenant
    context, no job and no `sample_data_runs` row in existence.

    And it carries NO outcome at all — an outcome on the catalogue would be a
    second, older answer sitting beside the live one from `step_states()`, and
    the two could disagree.

    RED-PROVED at commit 02abfa48, before `step_catalogue()` existed:

        E       AttributeError: module 'apps.tenancy.sample_data' has no
                attribute 'step_catalogue'
        tests/test_cr064_seventeen_steps.py:133: AttributeError
    """
    catalogue = sample_data.step_catalogue()
    assert catalogue  # no tenant context entered anywhere in this test
    for row in catalogue:
        assert "outcome" not in row
        assert "detail" not in row


# ── A2 · DEF-3280 — the poll serves the checkpoint ─────────────────────────
def test_cr064_tc3_the_poll_serves_the_checkpoint_the_job_wrote(plant_tenant):
    """DEF-3280. `run_provisioning_plant` has written the label of the block it
    just finished into the record since 2026-08-19 and `job_poll` dropped it,
    so `GET /api/jobs/{id}` could answer *"11 of 17"* and never *"Meter
    reads"*. Hard-won law 2 — built is not wired.

    RED-PROVED at commit 02abfa48, against the un-fixed selector:

        E       KeyError: 'checkpoint'
        tests/test_cr064_seventeen_steps.py:158: KeyError
    """
    with tenant_ctx(plant_tenant):
        record = core_jobs.enqueue(sample_data.PLANT_JOB_KIND, payload={})
        core_jobs.start(record["id"])
        core_jobs.record_progress(record["id"], done=11, total=17, checkpoint="Meter reads")

        served = selectors.job_poll(record["id"])

    assert served["checkpoint"] == "Meter reads"
    assert served["progress"] == {"done": 11, "total": 17}


# ── A3 + A4 · the per-step outcomes, while the run is in flight ────────────
def test_cr064_tc4_a_step_with_no_row_reads_not_started(plant_tenant):
    """**THE ONE CR-064 SIZES AS THE REAL RISK, AND IT IS WRITTEN BEFORE THE
    SCREEN.** A step the run has not reached is `not_started` — never `seeded`,
    never `failed`, and never simply absent from the list.

    A list that STOPS at block 6 cannot be told apart from a list that
    finished, which is the exact class of production report this change was
    asked for on 2026-09-02: the product said a thing succeeded and the thing
    had not happened.

    RED-PROVED at commit 02abfa48:

        E       AttributeError: module 'apps.tenancy.sample_data' has no
                attribute 'step_states'
        tests/test_cr064_seventeen_steps.py:179: AttributeError
    """
    with tenant_ctx(plant_tenant):
        steps = sample_data.step_states()

    assert len(steps) == len(sample_data.SAMPLE_MODULES)
    assert {row["outcome"] for row in steps} == {"not_started"}
    assert all(row["detail"] is None for row in steps)
    assert all(row["count"] == 0 for row in steps)
    # And "not started" is NOT one of the three verdicts a run writes, so it
    # can never be merged worst-first into a module line by accident.
    assert sample_data.OUTCOME_NOT_STARTED not in sample_data._OUTCOME_SEVERITY


def test_cr064_tc5_a_skipped_block_carries_its_own_sentence(plant_tenant, monkeypatch):
    """A3: *"if you skip the step, then show the reason for that step also"*.

    ⚠ A SKIP HAS TO BE MANUFACTURED NOW, AND THAT IS GOOD NEWS RATHER THAN
    TEST GYMNASTICS. Every module publishes its seams today, so
    `seed_sample_data` no longer skips anything of its own accord — which is
    exactly what DEF-153 was filed to make true. One seam is removed here so
    the BR-TEN-060 path is a real one and not a simulation: `seams.resolve`
    does a live `getattr` on the owning module's `services`, finds nothing, and
    `_record` writes the sentence that names the missing function.

    RED-PROVED against the un-fixed code:

        AttributeError: module 'apps.tenancy.sample_data' has no attribute
        'step_states'
    """
    from importlib import import_module

    missing = "customers:seed_sample_wizard_parks"
    with tenant_ctx(plant_tenant):
        _fake_every_seam(monkeypatch, counts=4)
        monkeypatch.delattr(
            import_module("apps.customers.services"), "seed_sample_wizard_parks", raising=False
        )
        sample_data.seed_sample_data(admin_actor())
        steps = sample_data.step_states()

    by_key = {row["key"]: row for row in steps}
    assert len(steps) == len(sample_data.SAMPLE_MODULES)

    skipped = by_key[missing]
    assert skipped["outcome"] == "skipped"
    assert skipped["reason_code"] == sample_data.REASON_SEAM_NOT_WIRED
    assert skipped["detail"], "a skipped step with no sentence is the DEF-016 shape"
    # The sentence NAMES the seam, which is what makes it actionable — the
    # SettingsSampleData precedent, one surface earlier.
    assert "seed_sample_wizard_parks" in skipped["detail"]
    assert skipped["error_code"]
    # ⚠ **THE SECOND LINE HERE USED TO READ `== len(SAMPLE_MODULES)` AND IT WAS
    # A CLAIM ABOUT A BLOCK'S POSITION WEARING A DERIVATION'S CLOTHES
    # (`DEF-TEN-4521`).** A literal `17` had already been fixed here once, so
    # deriving the length felt like the cure — but the length is derived and the
    # sentence beside it, *"the parked move-in is the LAST block"*, is not. It
    # stopped being true the moment `CR-082` appended the two portal blocks
    # after it, and stopped again when `CR-083` appended integrations. The
    # subject of this case is a skipped step carrying its own sentence; the
    # position is a passenger, so it is compared with the block's own index and
    # with nothing else.
    assert skipped["position"] == _position_of(missing)

    # And the skip is that STEP's, not the run's: everything else still seeded.
    assert by_key["rating:seed_sample_records"]["outcome"] == "seeded"


def test_cr064_tc6_a_failed_block_carries_its_own_reason_and_the_rest_still_report(
    plant_tenant, monkeypatch
):
    """A3, the half the PO actually asked about: *"if step breaks - then show
    the reason behind it at that step itself"*.

    One block is made to raise; the run continues (BR-TEN-063, atomic per
    module) and the served list still has seventeen rows — the broken one
    carrying its own sentence and its own error code, and the sixteen around
    it carrying theirs.

    RED-PROVED at commit 02abfa48:

        E       AttributeError: module 'apps.tenancy.sample_data' has no
                attribute 'step_states'
        tests/test_cr064_seventeen_steps.py:236: AttributeError
    """
    boom = RuntimeError("relation \"meter_reads\" does not exist")
    with tenant_ctx(plant_tenant):
        _fake_every_seam(monkeypatch, counts=3, raisers={"metering:seed_sample_reads": boom})
        sample_data.seed_sample_data(admin_actor())
        steps = sample_data.step_states()

    by_key = {row["key"]: row for row in steps}
    assert len(steps) == len(sample_data.SAMPLE_MODULES)

    broken = by_key["metering:seed_sample_reads"]
    assert broken["outcome"] == "failed"
    assert broken["reason_code"] == sample_data.REASON_EXCEPTION
    assert "meter_reads" in broken["detail"]
    assert broken["error_code"]
    # It is the step's OWN line that carries it — its own position, named.
    # ⚠ DERIVED (DEF-3320): this read `== 6`, and CR-062's Municipal-discount
    # block was INSERTED at position 6 rather than appended, which moves every
    # step after it. An insertion in the middle is what a positional literal
    # cannot survive.
    assert broken["position"] == _position_of("metering:seed_sample_reads")
    assert broken["label"] == "Meter reads"

    # Everything before it seeded and says so; nothing else inherits its reason.
    assert by_key["rating:seed_sample_records"]["outcome"] == "seeded"
    assert by_key["rating:seed_sample_records"]["reason_code"] is None


def test_cr064_tc7_the_plant_poll_carries_the_steps_and_other_kinds_do_not(
    plant_tenant, monkeypatch
):
    """A3 again, at the wire: the sentence reaches the POLL BODY, not a later
    Settings read. And only the plant kind grows the key — seventeen
    `not_started` steps on an export job would be a lie about a job that never
    had any (the DEF-127 posture: a list nothing wrote is not an empty list).

    RED-PROVED at commit 02abfa48, against the un-fixed selector:

        E       KeyError: 'steps'
        tests/test_cr064_seventeen_steps.py:278: KeyError
    """
    boom = RuntimeError("relation \"invoices\" does not exist")
    with tenant_ctx(plant_tenant):
        _fake_every_seam(monkeypatch, counts=2, raisers={"billing:seed_sample_records": boom})
        sample_data.seed_sample_data(admin_actor())

        plant = core_jobs.enqueue(sample_data.PLANT_JOB_KIND, payload={})
        export = core_jobs.enqueue("audit_export", payload={})

        plant_body = selectors.job_poll(plant["id"])
        export_body = selectors.job_poll(export["id"])

    assert len(plant_body["steps"]) == len(sample_data.SAMPLE_MODULES)
    broken = next(r for r in plant_body["steps"] if r["key"] == "billing:seed_sample_records")
    assert broken["outcome"] == "failed"
    assert "invoices" in broken["detail"]

    assert "steps" not in export_body
    assert export_body["checkpoint"] is None


def test_cr064_tc8_a_foreign_or_unknown_job_is_still_absent(plant_tenant):
    """The new key changes nothing about the refusal. A job id this tenant does
    not hold is ABSENT (HR-1 / 11b G4 — a 403 would confirm it exists), and a
    malformed one is absent for the same reason.

    ⚠ THIS ONE PASSED ON THE UN-FIXED CODE AND IS SAID SO OUT LOUD. It is a
    REGRESSION assertion, not a new behaviour: the refusal already held and
    the point of the test is that adding `steps` did not weaken it. A check
    that cannot fail is worse than none, so its red proof is a separate one —
    pointing `job_poll` at `Job.objects.filter(id=target)` with the tenant
    filter removed makes it fail:

        AssertionError: assert {'id': ...} is None
    """
    with tenant_ctx(plant_tenant):
        assert selectors.job_poll(uuid.uuid4()) is None
        assert selectors.job_poll("not-a-uuid") is None


def test_cr064_tc9_the_commit_response_names_the_steps_before_the_first_poll():
    """A1 at the wire: *"all seventeen visible from the first frame"*.

    The sign-up screen draws its list from the commit response, which lands
    before the first poll can possibly answer. `total: 17` was there since
    CR-017 and a count is not a list, which is precisely what the PO said on
    2026-09-02.

    RED-PROVED at commit 02abfa48, before `sample_plant["steps"]` existed:

        E       KeyError: 'steps'
        tests/test_cr064_seventeen_steps.py:322: KeyError
    """
    from apps.tenancy import services as tenancy_services

    result = tenancy_services.provision_tenant(
        brazosbend_payload(name="Ridgeline Water", subdomain="ridgeline")
    )
    plant = result["sample_plant"]
    assert plant is not None, "the S111 toggle was on; a plant must have been asked for"
    assert plant["total"] == len(sample_data.SAMPLE_MODULES)
    assert [row["key"] for row in plant["steps"]] == [
        spec.key for spec in sample_data.SAMPLE_MODULES
    ]


# ── DEF-TEN-4505 · THE SCREEN'S LIST IS THE SEEDER'S LIST, CHECKED WHERE
#    SOMEBODY ACTUALLY RUNS IT ──────────────────────────────────────────────
def test_def_ten_4505_the_signup_screens_step_list_is_the_seeders():
    """`provisioningSteps.test.ts` ALREADY MAKES THIS ASSERTION AND HAS BEEN RED
    FOR DAYS BECAUSE NOTHING RUNS IT. This is the same claim in the suite lanes
    do run.

    **THE HISTORY IS THE ARGUMENT FOR A SECOND COPY, WHICH IS OTHERWISE EXACTLY
    THE THING THIS REPOSITORY KEEPS BEING BITTEN BY.** Four times now a block
    has been appended to `SAMPLE_MODULES` in Python with no matching entry in
    the screen's hand-typed `PROVISIONING_STEPS`: `rating:seed_sample_enrolments`
    (`DEF-3320`), `payments:seed_sample_multi_account_tender` (`DEF-PAY-3631`),
    and `assets:seed_sample_aged_meters` + `work:seed_sample_records` together
    (`DEF-TEN-4505`). The vitest guard caught every one of them, on the day, by
    name — and CI has no runner for vitest, so its only reader is a lane that
    thinks to run it by hand. A guard nobody reads is not a guard (CLAUDE.md
    hard-won law 7).

    ⚠ **THIS IS NOT A SECOND SOURCE OF TRUTH.** It parses the SAME two files the
    vitest case parses and adds no list of its own; if it and the vitest case
    ever disagree, one of them has a parsing bug and neither is authoritative.

    ⚠ **A LANE ADDING A BLOCK WILL MEET THIS AS A RED, AND THAT IS THE POINT.**
    What it is asking for is three small things in the SAME commit as the
    `SampleModule(...)` row: the key in `PROVISIONING_STEPS`, at the same
    position; a label under
    `tenancy.signup.provisioning.block.<module>.<seam>`; and that label in all
    eleven catalogues (`10-scripts/i18n_fanin.py` does the eleven at once). It
    is red for somebody's block, never for yours alone — read the names it
    prints.
    """
    import json
    import re
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    wizard = (repo / "07-frontend/src/features/tenancy/SignupWizard.tsx").read_text("utf-8")
    catalogue = json.loads(
        (repo / "07-frontend/src/i18n/locales/en.json").read_text("utf-8")
    )

    block = re.search(
        r"export const PROVISIONING_STEPS:[^=]*=\s*\[(.*?)\n\];", wizard, re.S
    )
    # A file that no longer holds the constant is a FAILURE, never a skip —
    # `DEF-524`'s shape, a check whose hardcoded path outlived what it named.
    assert block, "PROVISIONING_STEPS not found in SignupWizard.tsx — the shape moved"
    on_screen = re.findall(r'"([a-z_]+:[a-z_]+)"', block.group(1))
    assert on_screen, "parsed no step keys out of PROVISIONING_STEPS"

    seeded = [spec.key for spec in sample_data.SAMPLE_MODULES]
    missing = [key for key in seeded if key not in on_screen]
    assert not missing, (
        f"{len(missing)} block(s) are seeded and are NOT on the sign-up screen: "
        f"{', '.join(missing)} — add each to PROVISIONING_STEPS in "
        "07-frontend/src/features/tenancy/SignupWizard.tsx, in its seeding position"
    )
    stale = [key for key in on_screen if key not in seeded]
    assert not stale, (
        f"the sign-up screen names {', '.join(stale)}, which the seeder no longer runs"
    )
    assert on_screen == seeded, (
        "the screen lists the same steps in a DIFFERENT ORDER — it narrates the "
        "plant, so the order it draws is a claim about what happens when"
    )

    unlabelled = [
        key
        for key in seeded
        if f"tenancy.signup.provisioning.block.{key.replace(':', '.')}" not in catalogue
    ]
    assert not unlabelled, (
        f"{len(unlabelled)} step(s) have no clerk-facing label and would render the "
        f"server's English sentence in all eleven languages: {', '.join(unlabelled)}"
    )


# ── DEF-3320 · the prose and the tuple say the same number ──────────────────
def test_cr064_tc10_no_sentence_in_sample_data_states_a_count_the_tuple_denies():
    """`DEF-3320` — five sentences said SEVENTEEN while the tuple held eighteen.

    **NOTHING WAS EVER GOING TO GO RED ON IT**, and that is the whole reason
    this case exists. Every other assertion in this file and in
    `provisioningSteps.test.ts` compares the code with the code; the prose is
    read by people and by no check at all, so `step_states()` could carry
    *"THE LENGTH IS ALWAYS SEVENTEEN AND THAT IS THE POINT"* one function away
    from a `step_catalogue()` returning eighteen rows, and the suite agreed
    with the code and disagreed with the sentence. Hard-won law 1 in its
    purest form: **a comment claiming a guarantee is not the guarantee.**

    It is the clause `DEF-3320`'s prevention column asks for, and the same
    shape `G64` uses to hold the two golden numbers together.

    **THE RULE, and it is deliberately narrow:** a spelled-out number from
    THIRTEEN upwards, in this module, can only be describing this list — there
    is nothing else in the file with that many of anything — so the only one
    allowed is the word for `len(SAMPLE_MODULES)`. Smaller words are left
    alone: `one`, `two` and `three` are ordinary English here, and `\bTEN\b`
    matches inside every `BR-TEN-###` citation, so a wider net would be noise
    rather than a check.

    RED-PROVED (law 7) at 05eef3e8, before the sentences were restated:

        AssertionError: sample_data.py states 'SEVENTEEN' at lines
        [1119, 1608, 1649] and 'seventeen' at lines [1597, 1643],
        but len(SAMPLE_MODULES) is 18
    """
    import re
    from pathlib import Path

    # ⚠ **WIDENED TO TWENTY-FIVE ON 2026-09-07, AND IT WAS ALREADY RED WHEN IT
    # WAS (CR-083).** The list stopped at twenty while `SAMPLE_MODULES` held
    # TWENTY-THREE, so the first assertion below fired on every run — the check
    # was refusing to answer rather than answering wrongly, which is the right
    # failure and is exactly what its own message asks for: *"widen it rather
    # than deleting it"*. It is widened here rather than in the commit that
    # crossed twenty because nothing reads this file until a block is added.
    WORDS = {
        13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen",
        17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty",
        21: "twenty-one", 22: "twenty-two", 23: "twenty-three",
        24: "twenty-four", 25: "twenty-five", 26: "twenty-six",
        27: "twenty-seven", 28: "twenty-eight", 29: "twenty-nine", 30: "thirty",
    }
    expected = WORDS.get(len(sample_data.SAMPLE_MODULES))
    assert expected is not None, (
        f"SAMPLE_MODULES holds {len(sample_data.SAMPLE_MODULES)} blocks and this "
        "check's word list stops at twenty — widen it rather than deleting it"
    )

    source = Path(sample_data.__file__).read_text(encoding="utf-8")
    offenders: dict[str, list[int]] = {}
    for number, word in WORDS.items():
        if word == expected:
            continue
        for lineno, line in enumerate(source.split("\n"), start=1):
            # ⚠ **THE HYPHEN GUARDS ARE WHAT LET A COMPOUND WORD IN AT ALL.**
            # `\btwenty\b` matches INSIDE "twenty-four" — a hyphen is a word
            # boundary — so without these the correct sentence for a
            # twenty-four-block tuple would report itself as stating "twenty".
            # A check that cannot tell a number from the first half of a bigger
            # one is a check that fails wrongly, which is worse than one that
            # passes wrongly because nobody trusts it afterwards.
            for hit in re.findall(rf"(?<!-)\b{word}\b(?!-)", line, flags=re.IGNORECASE):
                offenders.setdefault(hit, []).append(lineno)

    assert not offenders, (
        "apps/tenancy/sample_data.py states "
        + " and ".join(f"{w!r} at lines {ls}" for w, ls in sorted(offenders.items()))
        + f", but len(SAMPLE_MODULES) is {len(sample_data.SAMPLE_MODULES)}"
    )

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-064 (12-governance/11-change-requests.md) — tasks A1-A4 + D1
# generated: 2026-09-02 by the CR-064 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
