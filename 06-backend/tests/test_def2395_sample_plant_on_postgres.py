# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2395 (2026-09-01) — law 14 requires a PostgreSQL proof and no
#           lane could get a seeded tenant to make one on. Its prevention
#           column asks, in its own words, for *"a check that provisions one
#           tenant on PostgreSQL, so the day this breaks again it is a red gate
#           rather than three lanes each losing an hour to it."* This is that
#           check; G68 is what refuses to call a SQLite run of it a proof.
#           DEF-2722 (2026-08-31) — *"NO TEST PROVISIONS A TENANT AND THEN
#           ASSERTS THE SAMPLE PLANT IS COMPLETE"*. Still true until this file.
#           DEF-566  (2026-08-22) — the write-nothing identity stub that was
#           the head of the cascade.
# Story:    US-TEN-019 (tenant sample data) · US-TEN-001/004 (provisioning)
#           Screens: S114 (signup) · S62 (checklist) · S8 (Sample data panel)
# Rules:    BR-TEN-001 (provisioning creates the owner) · BR-TEN-010 (one
#           atomic transaction, idempotent on the subdomain) · BR-TEN-063
#           (the plant is atomic per module and idempotent) · CLAUDE.md hard
#           rule 1 (every write inside tenant context) · law 14 · law 7
# ───────────────────────────────────────────────────────
"""Provision ONE tenant the way a customer does, and assert the sample plant
lands COMPLETE — every block, by name.

WHY IT DID NOT EXIST BEFORE, IN DEF-2722'S OWN WORDS
====================================================
*"NO TEST PROVISIONS A TENANT AND THEN ASSERTS THE SAMPLE PLANT IS COMPLETE.
`seed_demo` hardcodes one subdomain (brazosbend) whose data was seeded by a
different path, so no suite has ever looked at a FRESHLY PROVISIONED tenant's
sample set."* The plant reported its failures honestly, into a job record and a
C-15 audit line, **and nothing read either** — hard-won law 2, "built is not
wired", with the reporting built and wired to nobody.

WHAT IT CATCHES, MEASURED RATHER THAN ASSERTED
----------------------------------------------
Run against the tree of 2026-09-01 with DEF-566's stub still in place, on real
PostgreSQL 16.13, this test goes RED on exactly one line:

    identity  seed_sample_records  failed  n=0
      no sample staff user was created: this tenant has no ACTIVE System Admin,
      and `add_user` records who invited whom (BR-IDN-011) — an invitation from
      nobody would corrupt the trail. Provisioning creates the owner
      (BR-TEN-001); if that failed, the fix is there, not here.

    16 seeded, 1 failed, 0 skipped of 17

With the seam real it is 17 seeded, 0 failed, 0 skipped.

⚠ **THE PARAGRAPH ABOVE IS A MEASUREMENT OF 2026-09-01 AND ITS NUMBER IS NO
LONGER THE ESTATE'S — READ IT AS HISTORY (`DEF-3509`, 2026-09-03).** The
eighteenth block landed at 18:07 on 2026-09-02 and `EXPECTED_BLOCKS` stayed at
17, so this file's own guard was RED on PostgreSQL for a day with nothing able
to say so — `G68` skips wherever there is no database, which is most places.
The count is derived from `SAMPLE_MODULES` now and the reasoning is on the
constant. **Red first (hard-won law 7), and it is the gate's own words:**

    G68 plant-on-postgres: FAIL — the PostgreSQL sample-plant guard is RED
    (1 failed, 2 passed, 4 warnings in 278.35s). Failing case(s):
    test_def2395__a_provisioned_tenant_gets_a_COMPLETE_sample_plant.

The sentence after that is the gate guessing — *"A case naming the OWNER is
DEF-566's stub returning"* — and it was wrong, which is worth knowing about
this gate: it reports the failing case correctly and then offers one cause,
and the cause it offers is the cause it was written for rather than the one
that fired.

⚠ **IT DELIBERATELY DOES NOT USE THE `identity_seam` FIXTURE, AND THAT IS THE
DESIGN AND NOT AN OVERSIGHT.** That fixture is the thing that broke; a guard
that ran through it would be asking the suspect to vouch for itself. This test
takes `db` alone, so `apps.identity.services.provision_owner` — the REAL one —
is what provisioning calls. DEF-566 recommended exactly this shape for CR-014's
group-4 cohort and it is the reason those tests could see the defect at all.

⚠ **THE FAILURE USED TO NAME THE WRONG MODULE, WHICH IS WHY THE ASSERTION
PRINTS EVERY BLOCK.** Before DEF-2722 and DEF-2795 put savepoints in the
seeders, identity's collapse took billing and payments down behind it, so what
a lane saw was a billing or a payments failure — and three lanes each spent an
hour proving the problem was not their code. A message that lists all
seventeen outcomes in plant order lets a reader see the head of a cascade at a
glance instead of inferring it.

ON WHICH DATABASE THIS IS WORTH ANYTHING
----------------------------------------
It runs on both, and it means different things on each. On SQLite it proves the
WIRING — that every seam resolves and every block writes its rows. It cannot
prove law 14's case, because `config/settings/test.py` hardcodes in-memory
SQLite and SQLite has no aborted-transaction state at all. **`G68` is the half
that refuses to report a green SQLite run as a PostgreSQL proof**, which is the
exact confusion DEF-2395 was filed about.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.tenancy import sample_data, services
from core import tenancy as core_tenancy

# ⚠ TWO DIFFERENT REASONS, AND MIXING THEM UP IS HOW THIS FILE WOULD LOSE ITS
# POINT.
#
# `sqlite_guc` is INFRASTRUCTURE and is `autouse`, so importing the name is what
# switches it on for this module. SQLite has no `set_config()`, so without it
# every case here dies on `OperationalError: no such function: set_config` the
# moment it enters tenant context — measured, 2026-09-01. On PostgreSQL it
# fakes NOTHING (DEF-2761): the shipping kernel writes the real GUC and this
# fixture only clears the context around the case.
#
# `growth_plan` and `identity_seam` are for the LAST case ONLY — the one that
# deliberately provisions through the shared harness so a reinstated DEF-566
# stub goes red. The first two cases must NOT use them; see their docstrings.
from tests.test_us_ten_helpers import (  # noqa: F401
    growth_plan,
    identity_seam,
    sqlite_guc,
)

#: ⚠ **THIS WAS A PINNED `17` AND IT WENT STALE IN SEVENTEEN HOURS
#: (`DEF-3509`).** The pin was set at 01:08 on 2026-09-02; `CR-062`'s addendum
#: inserted the Municipal discount block and the eighteenth step reached the
#: screen at 18:07 the SAME DAY. **So this gate — the only one that proves a
#: freshly provisioned tenant's plant lands COMPLETE, and on the vendor law 14
#: says is the one that counts — was RED for a day and nothing said so.**
#:
#: **THE REASON NOTHING SAID SO IS THE INTERESTING PART AND IT IS NOT A
#: MISTAKE.** `G68` SKIPS when `DATABASE_URL` is unset, and it deliberately
#: refuses to call a SQLite run a proof — which is correct, and which means the
#: gate is green-by-absence on every machine with no PostgreSQL up. A hardcoded
#: number inside a check that most runs never execute is a number nothing can
#: keep honest. This is `DEF-3340`'s family for the third time: that sweep moved
#: the step list, eleven locale catalogues and the frontend tests, and could not
#: reach a literal that no default run ever reads.
#:
#: The pin's original reason is quoted here because it was a good one and is
#: preserved rather than discarded: *"`SAMPLE_MODULES` is a ledger of PO rulings
#: — several of its entries say in their own comments that their POSITION in the
#: tuple is the feature — so a block arriving or leaving is a thing somebody
#: should read about, not a number that quietly drifts."*
#:
#: **BOTH HALVES ARE KEPT, WHICH IS WHAT `provisioningSteps.test.ts` ALREADY
#: DOES AFTER `DEF-3320`.** The count is DERIVED from the authority, so a block
#: legitimately ADDED does not make this red; and a FLOOR keeps the derivation
#: honest, so an import that ever returned an empty tuple cannot pass by
#: comparing nothing with nothing. What the pin protected — a block silently
#: LEAVING, or the plant recording fewer rows than the catalogue declares — is
#: still caught, by the assertion below, which is where it belongs.
EXPECTED_BLOCKS = len(sample_data.SAMPLE_MODULES)

#: The floor. Never raise it to today's number — it exists so a broken import
#: cannot make the line above compare zero with zero, not to restate the count.
MINIMUM_BLOCKS = 17


def _signup_payload(subdomain: str) -> dict:
    """The S114 signup form's own shape. Built here rather than imported from
    `tests/test_us_ten_helpers.py` on purpose: this file must not depend on the
    harness whose defect it exists to catch."""
    return {
        "name": "DEF-2395 Plant Probe",
        "subdomain": subdomain,
        "owner": {
            "email": f"owner@{subdomain}.test",
            "full_name": "Plant Probe Owner",
            "password": "S3cure!passw0rd",
        },
        "country": "US",
        "state": "TX",
        "timezone": "America/Chicago",
        "currency": "USD",
        "services": ["water", "sewer"],
        # The S111 toggle. On, because the sample set IS what is under test.
        "load_defaults": True,
    }


def _tally(blocks) -> dict[str, int]:
    counts = {"seeded": 0, "failed": 0, "skipped": 0}
    for row in blocks:
        outcome = getattr(row, "outcome", None) or row["outcome"]
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


def _report(blocks) -> str:
    lines = []
    for row in blocks:
        module = getattr(row, "module", None) or row["module"]
        block = getattr(row, "block", None) or row.get("block")
        outcome = getattr(row, "outcome", None) or row["outcome"]
        detail = getattr(row, "detail", None)
        if detail is None and isinstance(row, dict):
            detail = row.get("detail")
        lines.append(f"  {module:<10} {block:<34} {outcome:<8} {detail or ''}")
    return "\n".join(lines)


@pytest.mark.django_db
def test_def2395__a_provisioned_tenant_gets_a_COMPLETE_sample_plant(settings):
    """Provision one tenant, plant its sample set, and require every block.

    `JOBS_EAGER = True` so the plant runs inside the signup call rather than
    waiting for a broker a test session does not have — which is what a dev and
    demo deployment does anyway (`provision_tenant`'s own comment names the
    three deployment shapes).
    """
    settings.JOBS_EAGER = True
    result = services.provision_tenant(_signup_payload("def2395-plant"))
    assert result["created"] is True, (
        "provisioning refused outright, so there is nothing to say about the plant"
    )

    tenant_id = result["id"]
    with core_tenancy.tenant_context(tenant_id):
        summary = sample_data.run_summary()

    blocks = summary["blocks"]
    counts = _tally(blocks)
    vendor = connection.vendor

    # DEF-3509 — the floor first, because it is what keeps the line under it
    # from comparing nothing with nothing if the import ever breaks.
    assert EXPECTED_BLOCKS >= MINIMUM_BLOCKS, (
        f"SAMPLE_MODULES holds {EXPECTED_BLOCKS} entries and this file has never "
        f"seen fewer than {MINIMUM_BLOCKS}. Either blocks were removed — which is a "
        "PO ruling somebody should read about — or the import is broken and this "
        "guard is about to pass by comparing an empty tuple with an empty result."
    )
    assert len(blocks) == EXPECTED_BLOCKS, (
        f"the plant recorded {len(blocks)} block(s) and SAMPLE_MODULES declares "
        f"{EXPECTED_BLOCKS}. A block the catalogue names and the run did not record "
        "is the failure this line exists for — read the first name missing from the "
        "report below, not the last.\n" + _report(blocks)
    )

    assert counts == {"seeded": EXPECTED_BLOCKS, "failed": 0, "skipped": 0}, (
        f"the sample plant landed SHORT on {vendor}: {counts['seeded']} seeded, "
        f"{counts['failed']} failed, {counts['skipped']} skipped of {len(blocks)}.\n"
        "READ THE FIRST NON-SEEDED LINE, NOT THE LAST — the blocks are printed in "
        "plant order and everything after a failure may be a consequence of it "
        "(DEF-2395: identity collapsing first made three lanes each spend an hour "
        "on a billing or payments failure that was never theirs).\n"
        + _report(blocks)
    )

    assert summary["succeeded"] is True, (
        "BR-TEN-056 clause 3: a run with any skip does not report success"
    )


@pytest.mark.django_db
def test_def2395__provisioning_leaves_the_owner_the_plant_needs(settings):
    """The head of the cascade, asserted on its own so a failure names itself.

    ⚠ THIS IS THE ASSERTION DEF-566 SPENT FOUR MONTHS WITHOUT. The identity
    seam contract in `apps/tenancy/seams.py` says `provision_owner` is
    *"REQUIRED — an owner-less tenant would be half-seeded (BR-TEN-001), so
    provisioning refuses without it"*, and the shared harness stubbed it with a
    function that returned a `uuid.uuid4()` and wrote NO `users` row and NO
    `tenant_memberships` row. **Nothing compared the stub against the module it
    stood in for**, so it outlived its wiring silently and the suite stayed
    green BECAUSE the stub answered.

    Kept SEPARATE from the plant test above deliberately: when both go red, the
    one that names the owner is the one to fix, and a reader should not have to
    work that out from a seventeen-line block report.
    """
    settings.JOBS_EAGER = True
    result = services.provision_tenant(_signup_payload("def2395-owner"))
    tenant_id = result["id"]

    from apps.identity import models as identity_models

    with core_tenancy.tenant_context(tenant_id):
        membership = (
            identity_models.TenantMembership.objects.filter(
                tenant_id=tenant_id,
                role__code="system_admin",
                status=identity_models.TenantMembership.STATUS_ACTIVE,
            )
            .select_related("user")
            .first()
        )

    assert membership is not None, (
        "BR-TEN-001: provisioning must leave an ACTIVE System Admin membership. "
        "`apps/identity/sample_data._owner_as_actor` looks for exactly this row and "
        "refuses the whole identity block without it, which is DEF-2395's first "
        "failing line. If this is red inside the test suite and green in the "
        "product, suspect a stub over `apps.identity.services.provision_owner` "
        "(DEF-566) before you suspect provisioning."
    )
    assert str(membership.user_id) == str(result["owner_user_id"]), (
        "the membership must belong to the owner provisioning reported, or the "
        "audit trail names somebody who does not exist"
    )


@pytest.mark.django_db
def test_def566__the_shared_harness_leaves_a_real_owner_too(growth_plan, identity_seam):
    """The SAME assertion, through the shared harness — and this is the one
    that goes red if DEF-566's stub ever comes back.

    ⚠ **THE TWO TESTS ABOVE CANNOT CATCH THAT, AND THE REASON IS THE WHOLE
    POINT OF THIS ONE.** They take `db` alone, so they never touch
    `identity_seam` and the real `provision_owner` runs whatever the harness
    says. That independence is deliberate — a guard should not ask the suspect
    to vouch for itself — but it also means a stub reinstalled over the seam
    tomorrow would leave them both green while every one of the several hundred
    tests behind `brazos` and `lonestar` quietly went back to having no owner.

    So this case provisions through the harness on purpose. `identity_seam` is
    a RECORDER now rather than a stub; if it is ever made to write nothing
    again, this is the line that says so, and it says it in one sentence
    instead of as a seventeen-block sample-plant report in a module nobody
    changed.

    Measured 2026-09-01: with the stub restored, this fails on the membership
    assertion; the plant behind it came to 16 seeded / 1 failed of 17.
    """
    from tests.test_us_ten_helpers import brazosbend_payload

    from apps.identity import models as identity_models

    result = services.provision_tenant(brazosbend_payload(subdomain="def566-harness"))
    tenant_id = result["id"]

    with core_tenancy.tenant_context(tenant_id):
        membership = identity_models.TenantMembership.objects.filter(
            tenant_id=tenant_id,
            role__code="system_admin",
            status=identity_models.TenantMembership.STATUS_ACTIVE,
        ).first()
        user = identity_models.User.objects.filter(
            tenant_id=tenant_id, email=brazosbend_payload()["owner"]["email"]
        ).first()

    assert user is not None, (
        "DEF-566: `identity_seam` wrote NO `users` row. It called itself "
        "skip-until-wired while the real `apps.identity.services.provision_owner` "
        "had been authored for weeks, so the stub SHADOWED a working "
        "implementation and every tenant this harness provisions had no owner. "
        "Nothing compared the stub against the module it stood in for, so the "
        "suite stayed green BECAUSE the stub answered"
    )
    assert membership is not None, (
        "DEF-566: the harness provisioned a tenant with NO ACTIVE System Admin "
        "membership. That is the row `apps/identity/sample_data._owner_as_actor` "
        "looks for, and its absence is the first failing line of DEF-2395's "
        "sample-plant collapse"
    )
    assert str(membership.user_id) == str(user.id)
    # The recorder half must keep working too: nine assertions in
    # test_us_ten_001_004_provisioning.py and test_us_ten_019_sample_data.py
    # read these, and a fixture that stopped recording would take them with it.
    assert identity_seam.provisioned, "the seam recorder logged no provisioning call"
    assert str(identity_seam.provisioned[-1]["owner_id"]) == str(user.id), (
        "the recorded owner id must be the id of a `users` row that exists — "
        "recording a uuid4 that names nobody is precisely what DEF-566 was"
    )
