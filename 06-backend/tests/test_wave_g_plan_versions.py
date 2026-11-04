# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-003 (EP-RAT-01) — plan lifecycle & versioning.
#           Screens: PLN-02 Versions tab (r10) / S10 (A1)
# Defects:  DEF-410 (a plan has no version history, so PLN-02's Versions tab can
#           show ONE row and the DATED banner promises something nothing stores)
# Rules:    BR-RAT-111 (a plan version is a FILING RECORD — who, when, why, and
#           what changed) · BR-RAT-037 (append-only versions, a REQUIRED reason
#           on a published plan, assignment snapshots untouched) · BR-RAT-030
#           (draft → published → archived) · CLAUDE.md hard rule 1 (tenant
#           scoping) · hard rule 4's spirit (a version row is never updated) ·
#           hard rule 7 (audit beside the record, never instead of it)
# Questions: OQ-323 (which version prices an account assigned at an older one) ·
#           OQ-324 (does a plan version take effect on save, or pend — CLOSED 2026-10-03 (B), BR-RAT-1066)
# ───────────────────────────────────────────────────────
"""Wave G, half 2 — the plan REMEMBERS what it was.

`rate_plans.version` has been an INTEGER since W1 and `BR-RAT-037` has
incremented it since W1. So the product could say a plan was on v3 and could not
say what v1 held, who changed it or why: the authored reason went to
`rate_change_log`, keyed by `entity_id`, which is a cross-object compliance trail
the plan itself cannot read from. PLN-02's Versions tab therefore drew one row
and stated its own absence in the CHANGE column (`DEF-410`).

CR-013 part 5 wants the opposite — the plan is *"the contract boundary: the plan
version is what makes a bill explicable months later"*.

⚠ **THREE THINGS THIS DELIBERATELY DOES NOT DO, each with a test below.**

1. **It does not price anything.** `resolution` and `billing/gather` never read
   `plan_versions`. WHICH version prices an account already assigned at an older
   one is `OQ-323`, unruled, and a money question.
2. **It carries no effective date.** Part 5 step 8's *Draft / Submit / Activate*
   would make a version PEND; that reading is `OQ-324` (CLOSED 2026-10-03 as (B) — the column
   arrived with `rating/0062` after the ruling). A column added before the
   ruling makes the unruled reading storable.
3. **It carries no docket.** `09-screen-inventory.md` §10: *"Do not normalise the
   other four up to seven columns — a discount has no docket."* Neither does a
   plan, so `FILED AS` is the rate schedule's alone.
"""

import pytest

from apps.rating import models, selectors, services
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, audit_actions, tenant_ctx

pytestmark = pytest.mark.django_db


def _plan(env, publish=True, base="8.00"):
    env.enable("water")
    schedule = env.tiered_schedule("Res Water", "water", RES_WATER_TIERS)
    line = {"service": "water", "tariff": schedule["id"]}
    if base is not None:
        line["base_charge"] = base
    # BR-RAT-890 (DEF-494, PO 2026-08-28): a plan cannot be PUBLISHED without a
    # start date, and half the cases in this file publish through their own call
    # rather than through `publish=True`. Stated here so every plan this helper
    # builds is publishable, on the same 2026-08-01 the schedule above uses.
    return (
        env.plan(
            "Residential Standard",
            "RES-STD",
            [line],
            publish=publish,
            effective_from="2026-08-01",
        ),
        schedule,
    )


# ══════════════════════════════════════════════════════════════════════════
# The record itself (BR-RAT-111, closes DEF-410)
# ══════════════════════════════════════════════════════════════════════════


def test_br_rat_111__the_plan_versions_table_exists(env):
    """RED before this slice: no such table, which is why PLN-02 could serve a
    history of length one and be telling the truth.

    Asserted against the connection's own introspection rather than the model
    registry — a model defined and never migrated is exactly as useful to a
    screen as no model at all (the shape `test_cr013_discounts` uses for its six).
    """
    from django.db import connection

    with connection.cursor() as cursor:
        assert "plan_versions" in set(connection.introspection.table_names(cursor))


def test_br_rat_111__publishing_records_v1_with_its_content(env):
    """⚠ **v1 IS RECORDED AT PUBLISH, NOT AT CREATION, AND THAT IS THE RULE.**

    A plan lands as a DRAFT (BR-RAT-030) and a draft edits freely — `update_plan`
    neither bumps the counter nor asks for a reason. So a `v1` row written at
    creation would go stale on the first draft edit and keep claiming to be what
    v1 holds, which is worse than no row: a filing record that is confidently
    wrong. Publishing is the moment the content stops moving.
    """
    plan, _ = _plan(env, publish=False)
    with tenant_ctx(env.tenant):
        assert selectors.plan_detail(plan["id"])["versions"] == []
        services.publish_plan(env.admin, plan["id"])
        versions = selectors.plan_detail(plan["id"])["versions"]
    assert [row["version_no"] for row in versions] == [1]
    # The snapshot is the plan's CONTENT at that moment.
    with tenant_ctx(env.tenant):
        stored = models.PlanVersion.objects.get(rate_plan_id=plan["id"], version_no=1)
    assert stored.snapshot["code"] == "RES-STD"
    assert stored.snapshot["services"][0]["base_charge"] == "8.000000"


def test_br_rat_111__a_content_change_records_the_next_version_with_WHO_and_WHY(env):
    """The three facts DEF-410 said were unrecoverable: who changed it, when,
    and why."""
    plan, _ = _plan(env)
    with tenant_ctx(env.tenant):
        services.update_plan(
            env.admin,
            plan["id"],
            # ⚠ AMENDED 2026-10-03 (`BR-RAT-1067`): a RENAME no longer makes a
            # version (PO ruling 1, *"Name and details (same version)"*), so the
            # change that files v2 here is a price — the plan's minimum bill.
            {"minimum_bill_amount": "15.00", "reason": "Renamed for the 2027 filing."},
        )
        versions = selectors.plan_detail(plan["id"])["versions"]
    # NEWEST FIRST — §10 orders every one of the five Versions tabs descending.
    assert [row["version_no"] for row in versions] == [2, 1]
    latest = versions[0]
    assert latest["change_reason"] == "Renamed for the 2027 filing."
    # ⚠ DEF-367's `{id, name}` — a NAME, never a bare uuid. Two staff can share a
    # first name; neither shares an id, so both travel.
    assert latest["submitted_by"]["id"] == str(env.admin.id)
    assert latest["submitted_by"]["name"] == env.owner.full_name
    assert latest["created_at"] is not None


def test_br_rat_111__there_is_NO_docket_column__section_10(env):
    """§10, verbatim: *"Do not normalise the other four up to seven columns — a
    discount has no docket."* Neither does a plan, so `FILED AS` is the rate
    schedule's alone and nothing here can fill one even by accident."""
    plan, _ = _plan(env)
    with tenant_ctx(env.tenant):
        row = selectors.plan_detail(plan["id"])["versions"][0]
    assert "version_label" not in row
    assert not hasattr(models.PlanVersion, "version_label")


def test_oq_314__a_plan_version_carries_NO_effective_date(env):
    """Part 5 step 8's *Draft / Submit / Activate* would make a version PEND.
    That reading is unruled, and a column for it would make the unruled reading
    storable — the mistake `plan_discount_rules`' absent value column exists to
    avoid."""
    # ⚠ SUPERSEDED 2026-10-03 — `OQ-324` CLOSED as (B) by the PO-approved plans
    # drawing (`BR-RAT-1066`): a plan version now CARRIES its window. The test
    # keeps its place and asserts the ruled reading instead: the published v1
    # holds the plan's own start date and no end.
    assert hasattr(models.PlanVersion, "effective_from")
    plan, _ = _plan(env)
    with tenant_ctx(env.tenant):
        stored = models.PlanVersion.objects.get(rate_plan_id=plan["id"], version_no=1)
    assert str(stored.effective_from) == "2026-08-01"
    assert stored.effective_to is None
    assert stored.status == "published"


def test_br_rat_111__the_diff_names_the_COMPONENT_that_moved(env):
    """CR-013 part 5 asks for a *"component-level diff"*, and DEF-280's own
    prevention says how: *"descend into the structure and diff component by
    component … naming the component that moved"*.

    ⚠ **THE MONEY STRING IS REPORTED EXACTLY AS STORED — six places, unrounded.**
    This is a RECORD. Re-formatting `8.000000` to `8.00` inside it would be a
    display decision made inside evidence.
    """
    plan, schedule = _plan(env)
    with tenant_ctx(env.tenant):
        services.update_plan(
            env.admin,
            plan["id"],
            {
                "services": [
                    {"service": "water", "base_charge": "9.50", "tariff": schedule["id"]}
                ],
                "reason": "Water base raised for the 2027 filing.",
            },
        )
        versions = selectors.plan_detail(plan["id"])["versions"]
    paths = {field["path"]: field for field in versions[0]["changes"]["fields"]}
    assert "services[0].base_charge" in paths
    assert paths["services[0].base_charge"]["before"] == "8.000000"
    assert paths["services[0].base_charge"]["after"] == "9.500000"
    # `base_charges` — the DERIVED Σ on the row — moved with it, so the diff
    # reports two leaves rather than one and the total is not silently dropped.
    assert versions[0]["changes"]["total"] >= 2


def test_br_rat_111__the_OLDEST_recorded_version_claims_no_diff(env):
    """It has no predecessor, so reporting the whole plan as "new" would be
    inventing a change nobody made."""
    plan, _ = _plan(env)
    with tenant_ctx(env.tenant):
        versions = selectors.plan_detail(plan["id"])["versions"]
    assert versions[0]["version_no"] == 1
    assert versions[0]["changes"] == {"fields": [], "total": 0}


def test_br_rat_111__a_long_diff_is_CAPPED_and_the_count_stays_true(env):
    """A wizard re-post can touch dozens of leaves and a cell holding forty
    paths is a cell nobody reads. `total` is the honest number; `fields` is what
    fits — the same judgement `BLOCKING_PLAN_NAMES_SHOWN` makes for a refusal."""
    plan, schedule = _plan(env)
    with tenant_ctx(env.tenant):
        services.update_plan(
            env.admin,
            plan["id"],
            {
                "name": "Renamed",
                "code": "RES-2027",
                "description": "New description",
                "minimum_bill_amount": "12.00",
                "budget_billing": True,
                "effective_from": "2027-01-01",
                "services": [
                    {
                        "service": "water",
                        "base_charge": "9.50",
                        "minimum_amount": "4.00",
                        "tariff": schedule["id"],
                    }
                ],
                "reason": "Everything at once.",
            },
        )
        changes = selectors.plan_detail(plan["id"])["versions"][0]["changes"]
    assert len(changes["fields"]) <= selectors.PLAN_VERSION_CHANGES_SHOWN
    assert changes["total"] >= len(changes["fields"])


def test_br_rat_037__a_DRAFT_edit_records_no_version_and_bumps_no_counter(env):
    """Unchanged law, re-asserted because the new table could have been wired to
    every save. A draft has never been billed; BR-RAT-030's whole point is that
    it edits freely, and a version row per keystroke is not a filing record."""
    plan, _ = _plan(env, publish=False)
    with tenant_ctx(env.tenant):
        services.update_plan(env.admin, plan["id"], {"name": "Still a draft"})
        detail = selectors.plan_detail(plan["id"])
    assert detail["version"] == 1
    assert detail["versions"] == []


def test_br_rat_037__a_published_content_change_still_REFUSES_without_a_reason(env):
    """The record does not soften the gate. A version with no authored reason is
    the thing DEF-280 was filed about, one object across."""
    plan, _ = _plan(env)
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as caught:
        # ⚠ AMENDED 2026-10-03 (`BR-RAT-1067`, `CR-167-BRC10` §7.3): a name
        # change needs no reason now (same version), so the gate is asserted on
        # a PRICE, and the refusal names the field — a price changes from a date
        # or by a correction, never by a bare PATCH.
        services.update_plan(env.admin, plan["id"], {"minimum_bill_amount": "11.00"})
    assert caught.value.message_key == "rating.plans.field_needs_new_version"


def test_br_rat_1067__a_live_plans_name_and_details_save_on_the_SAME_version(env):
    """PO ruling 1 of the plans redesign (2026-10-03): *"Name and details (same
    version)"*. Renaming *Residential Standard* keeps it v1 with no reason
    asked, and Audit gets one before → after line; no filing row is written."""
    plan, _ = _plan(env)
    with tenant_ctx(env.tenant):
        services.update_plan(env.admin, plan["id"], {"name": "Residential — City"})
        detail = selectors.plan_detail(plan["id"])
        rows = models.PlanVersion.objects.filter(rate_plan_id=plan["id"]).count()
    assert detail["name"] == "Residential — City"
    assert detail["version"] == 1
    assert rows == 1


def test_br_rat_111__a_version_row_is_APPEND_ONLY(env):
    """Hard rule 4's spirit. Editing the plan again must ADD a row, never revise
    the one that describes what v2 held — corrections are new versions."""
    plan, _ = _plan(env)
    with tenant_ctx(env.tenant):
        services.update_plan(env.admin, plan["id"], {"minimum_bill_amount": "11.00", "reason": "First change"})
        first = models.PlanVersion.objects.get(rate_plan_id=plan["id"], version_no=2)
        first_snapshot = dict(first.snapshot)
        services.update_plan(env.admin, plan["id"], {"minimum_bill_amount": "12.00", "reason": "Second change"})
        first.refresh_from_db()
        rows = models.PlanVersion.objects.filter(rate_plan_id=plan["id"]).count()
    assert rows == 3
    assert first.snapshot == first_snapshot
    assert first.change_reason == "First change"


def test_br_rat_111__the_snapshot_never_NESTS_the_version_list(env):
    """⚠ A REAL TRAP, caught before it shipped. `_plan_snapshot` reads
    `plan_detail`, which now SERVES `versions` — so leaving the key in would nest
    v1 inside v2 inside v3, doubling the blob on every save and making the diff
    report the history as the thing that changed."""
    plan, _ = _plan(env)
    with tenant_ctx(env.tenant):
        services.update_plan(env.admin, plan["id"], {"minimum_bill_amount": "11.00", "reason": "Change"})
        stored = models.PlanVersion.objects.get(rate_plan_id=plan["id"], version_no=2)
    assert "versions" not in stored.snapshot
    # …and neither of the other two non-content keys, which was already true.
    assert "version" not in stored.snapshot
    assert "accounts" not in stored.snapshot


def test_hard_rule_7__the_version_record_does_NOT_replace_the_audit_row(env, audit_rows):
    """§10: *"Writing one does not excuse writing the other."* They answer
    different questions and have different readers."""
    plan, _ = _plan(env)
    audit_rows.clear()
    with tenant_ctx(env.tenant):
        services.update_plan(env.admin, plan["id"], {"minimum_bill_amount": "11.00", "reason": "Change"})
        rows = models.PlanVersion.objects.filter(rate_plan_id=plan["id"], version_no=2).count()
    assert rows == 1
    assert "plan.version_created" in audit_actions(audit_rows)


def test_hard_rule_1__a_plans_version_history_is_TENANT_SCOPED(env, other_env):
    """Both tenants publish a plan; neither history contains the other's row.
    The app filter is asserted here; the live-RLS half is the G5 isolation suite's
    (sqlite cannot enforce a policy)."""
    mine, _ = _plan(env)
    theirs, _ = _plan(other_env)
    with tenant_ctx(env.tenant):
        ids = {row["id"] for row in selectors.plan_detail(mine["id"])["versions"]}
        mine_rows = models.PlanVersion.objects.filter(tenant_id=env.tenant.id).count()
    with tenant_ctx(other_env.tenant):
        their_ids = {row["id"] for row in selectors.plan_detail(theirs["id"])["versions"]}
    assert mine_rows == 1
    assert ids and their_ids
    assert ids.isdisjoint(their_ids)


def test_oq_313__the_version_record_is_INERT_and_prices_nothing(env):
    """⚠ **AMENDED 2026-10-03 — HALF OF THIS IS HISTORY (`BR-RAT-1066`).** A plan
    version now has dates and owns its bindings, and the service date picks
    one (`apps.rating.plan_versioning`, read by `resolution_catalogue`). What
    still holds and is still asserted: the ASSIGNMENT's snapshot does not move
    on a version change, and the engine, the R-chain and the pricing stages read
    no `plan_versions` row through the ORM — the version is chosen before them.

    ⚠ **STATED AS A TEST BECAUSE IT IS THE THING A LATER LANE WILL ASSUME.**

    `unit_plan_assignments.plan_version` has stored a snapshot of the version
    NUMBER since W1 (BR-CUS-013) and nothing has ever read it. Now that content
    sits behind that number, the product has two answers on disk to *"which
    version prices this account"* and no rule saying which is right — so the
    assignment's snapshot is untouched by a plan version bump, exactly as
    BR-RAT-037 already required, and nothing in `rating` reads `plan_versions`
    to price anything.
    """
    plan, _ = _plan(env)
    unit = env.unit()
    with tenant_ctx(env.tenant):
        assignment = env.assign(plan["id"], unit, plan_version=1)
        services.update_plan(env.admin, plan["id"], {"minimum_bill_amount": "11.00", "reason": "Change"})
        assignment.refresh_from_db()
        detail = selectors.plan_detail(plan["id"])
    # BR-RAT-037 — the assignment's snapshot does not move when the plan does.
    assert assignment.plan_version == 1
    assert detail["version"] == 2
    # …and no pricing path consults the new table. Asserted by SOURCE rather
    # than by behaviour, because the failure mode is a future import.
    #
    # ⚠ THE NEEDLE IS AN ORM ACCESS, NOT A NAME — AND FINDING THAT OUT WAS THE
    # USEFUL PART. `resolution.py` ALREADY has both names: a dataclass called
    # `PlanVersion` (R1's resolved plan) and a field called `plan_versions` (the
    # tuple of them). Neither has anything to do with this table. So the first
    # two versions of this assertion — searching for `PlanVersion`, then for
    # `plan_versions` — each reported the pricing chain as guilty of reading a
    # table it has never heard of. A check whose output cannot distinguish pass
    # from fail is worse than no check, so this one searches for the only thing
    # that can ONLY mean the model: an ORM access through it.
    import pathlib

    for module in ("engine.py", "resolution.py", "pricing"):
        path = pathlib.Path(services.__file__).parent / module
        text = (
            path.read_text(encoding="utf-8")
            if path.is_file()
            else "".join(p.read_text(encoding="utf-8") for p in path.rglob("*.py"))
        )
        for needle in ("models.PlanVersion", "PlanVersion.objects"):
            assert needle not in text, f"{module} reads the plan version record — see OQ-323"


def test_br_rat_030__deleting_an_unbilled_plan_takes_its_version_rows_with_it(env):
    """`PlanVersion.rate_plan` is `PROTECT`, so omitting the cleanup would turn a
    hard delete into a 500 rather than the audit-lock refusal. The gate has
    already established 0 accounts and never billed, so there is no regulatory
    record to preserve."""
    plan, _ = _plan(env)
    with tenant_ctx(env.tenant):
        services.delete_plan(env.admin, plan["id"])
        assert models.PlanVersion.objects.filter(rate_plan_id=plan["id"]).count() == 0


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-013 PART 5 (verbatim, 12-governance/11-change-requests.md:6305) +
#         04-docs/05-modules/06-rating/09-screen-inventory.md §10 +
#         02-business-rules.md (BR-RAT-111)
# screens: PLN-02 Versions tab (r10) / S10 (A1)
# generated: 2026-08-21 by the Wave G lane (CR-013 part 5 — the plan as a versioned object)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — migrations 0020/0021 🔒 HUMAN-REVIEW-PENDING, ledger rows appended)
# gates: see the commit message — golden✔ makemigrations --check✔ tsc✔ vitest✔
# exceptions: the live-RLS half of the isolation test is the G5 suite's (sqlite
#             cannot enforce a policy); the app-filter half is asserted here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
