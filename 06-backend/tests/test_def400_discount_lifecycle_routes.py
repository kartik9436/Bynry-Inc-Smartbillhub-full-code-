# ── Trace ──────────────────────────────────────────────
# Story:    EP-RAT-12 (CR-013 part 3 — DISCOUNTS)   Screens: DIS-01, DIS-02,
#           CHG-01.discount
# Rules:    BR-RAT-072 (four statuses) · BR-RAT-077 (the second approval —
#           a TENANT SETTING, default $50,000 by PO ruling 2026-08-21,
#           measured against the discount's OWN budget cap, computed at SUBMIT
#           and STORED, and ALWAYS required where there is no budget cap) ·
#           BR-RAT-083 (anyone may DRAFT, Owner/Admin ACTIVATE) · BR-AUD-001
#           (hard rule 7 — every money action writes audit_log)
# Tests:    this file
# Impacts:  apps/rating/api.py (the three routes) · apps/rating/selectors.py
#           (`version_id` on the row + the nested-pair read)
# ───────────────────────────────────────────────────────
"""DEF-400 — the three lifecycle acts, over HTTP.

⚠ **WHAT WAS RED BEFORE THIS FILE, AND HOW IT WAS PROVED.** `submit`, `approve`
and `activate` were built, tested and mounted on NO ROUTE, so a discount could
be created and could never go live: the status column said `Draft` forever.
The first test below reads `apps/rating/api.py`'s own `urlpatterns` and asserts
that every `@require_role` write function in `discount_services` is reachable —
run against HEAD before the routes were added it fails with

    AssertionError: discount_services write functions no route reaches:
    ['activate_discount_version', 'approve_discount_version',
     'submit_discount_version']

which is the defect, in the words of the defect. That check is deliberately
GENERAL rather than a list of three names: DEF-400's own prevention column asks
for exactly this — *"a gate that lists every @require_role write function in a
services module and refuses one that no path() in that module's api.py
reaches"* — and it goes red the next time a lane builds a service and stops.
"""

import inspect
import uuid
from datetime import date
from decimal import Decimal

import pytest

from apps.rating import api as rating_api
from apps.rating import discount_services
from apps.rating import discounts as discount_models

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import api_call, audit_actions, tenant_ctx

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE GAP ITSELF — a write service that no route reaches
# ══════════════════════════════════════════════════════════════════════════

#: Write services that no route in this module reaches, each with the reason it
#: is not the defect. A name may only be added here with a CALLER named, or with
#: a defect id owning the gap — "nothing calls it" is the defect, not an entry.
#:
#: ⚠ **THIS PROBE FOUND SIX ON ITS FIRST RUN AND THEY ARE NOT SILENCED — DEF-478.**
#: DEF-400 named three lifecycle acts; the general check named the other six the
#: same afternoon, which is the whole argument for writing it generally. They sit
#: here citing the defect that owns them, so a SEVENTH goes red rather than
#: joining a list nobody rereads.
REACHED_ELSEWHERE = {
    # BR-RAT-072's fifth status is the one a BILL RUN sets, not a person:
    # `apps/billing` calls it when `price_discounts` reports an exhausted code.
    # A route would be a screen letting staff declare a budget exhausted, which
    # is an accident of arithmetic and not a decision.
    "suspend_discount_for_funding": "called by the bill run, never by a screen",
    # Likewise: `discount_grants` is the append-only subsidy record R6 writes as
    # it reduces a bill. A staff-facing route would let a person mint a subsidy
    # no bill produced.
    "record_grant": "called by R6 during a bill run, never by a screen",
    # The six with no screen and no route — DEF-478. Each is built, tested and
    # unmountable, and each is owed a STORY rather than a bare route: a route
    # with no screen is DEF-400 from the other end.
    "enrol_account": "DEF-478 — the account discount panel is not built",
    "verify_enrolment": "DEF-478 — the proof-verification surface is not built",
    # DEF-478 is FIXED (CR-166 follow-up, 2026-10-03), and not through this
    # function: every screen binds a discount through the PLAN's own write
    # (`services.update_plan` — the plan form, and the discount page's
    # `services.add_discount_to_plan` / `remove_discount_from_plan`), so ruling
    # 2's dated removal and BR-RAT-037's reason cannot be stepped round. This one
    # stays for the sample data and the tests that seed a binding.
    "attach_discount_to_plan": "sample data and test seeding only (screens use services.update_plan)",
    # CR-166-BRC10 r2 t3: `end_enrolment` and `retire_discount` are routed now
    # (`/discount-enrolments/{id}/end`, `/discounts/{id}/retire`) and left this
    # list. `update_discount` is the identity half of `PATCH /discounts/{id}`,
    # reached through `update_discount_details`.
    "update_discount": "reached through update_discount_details (PATCH /discounts/{id})",
}


def _source_of(module) -> str:
    return inspect.getsource(module)


def test_every_discount_write_service_is_reachable_from_a_route():
    """DEF-400's own prevention column, as a check.

    G13 refuses an unwired PROP on a component and has no backend equivalent, so
    three `@require_role` services sat behind no `path()` for two days with 47
    passing tests. This is that equivalent for one module.
    """
    services_source = _source_of(discount_services)
    api_source = _source_of(rating_api)
    guarded: list[str] = []
    for line_no, line in enumerate(services_source.splitlines()):
        if line.strip().startswith("@require_role("):
            following = services_source.splitlines()[line_no + 1 :]
            for candidate in following:
                if candidate.startswith("def "):
                    guarded.append(candidate[4:].split("(")[0])
                    break
    assert guarded, "no @require_role write functions found — the probe itself is broken"
    unreached = sorted(
        name
        for name in guarded
        if name not in REACHED_ELSEWHERE and f"discount_services.{name}(" not in api_source
    )
    assert not unreached, f"discount_services write functions no route reaches: {unreached}"


def test_the_three_lifecycle_paths_are_mounted():
    """The routes themselves, by pattern — so a handler renamed out of
    `urlpatterns` is caught as well as one never added."""
    patterns = {str(entry.pattern) for entry in rating_api.urlpatterns}
    for act in ("submit", "approve", "activate"):
        assert f"discounts/<str:discount_id>/versions/<str:version_id>/{act}" in patterns


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE WALK — Draft → Pending → Scheduled → Active, over HTTP
# ══════════════════════════════════════════════════════════════════════════


def _draft(env, *, code="SOLO", budget_cap="500", discount_type="percentage", value="5"):
    """A discount with ONE version, through the real create service."""
    with tenant_ctx(env.tenant):
        row = discount_services.create_discount(
            env.admin,
            {
                "code": code,
                "name": f"{code} test discount",
                "discount_type": discount_type,
                "value": value,
                "applies_to": "whole_bill",
                "effective_from": date(2026, 8, 1),
                **({} if budget_cap is None else {"budget_cap": budget_cap}),
            },
        )
        version = discount_models.DiscountVersion.objects.get(
            tenant=env.tenant, discount_id=row["id"]
        )
    return row["id"], str(version.id)


def _post(env, view, discount_id, version_id, *, role="system_admin"):
    return api_call(
        view,
        "post",
        user=env.owner,
        role=role,
        tenant=env.tenant,
        discount_id=discount_id,
        version_id=version_id,
    )


def test_a_draft_can_now_be_taken_all_the_way_live(env, audit_rows):
    """The defect's own sentence, inverted: *"a discount can be created and can
    never go live"*. Every hop is an HTTP call, because the services already
    passed and the product still could not do it."""
    discount_id, version_id = _draft(env)

    submitted = _post(env, rating_api.discount_version_submit, discount_id, version_id)
    assert submitted.status_code == 200
    assert submitted.data["status"] == discount_models.VERSION_PENDING_APPROVAL

    # PO ruling 2026-10-03 (1): approval is the LAST act — the version is in
    # force from its own start date, and the retired Activate door says so.
    approved = _post(env, rating_api.discount_version_approve, discount_id, version_id)
    assert approved.status_code == 200
    assert approved.data["status"] == discount_models.VERSION_ACTIVE

    activated = _post(env, rating_api.discount_version_activate, discount_id, version_id)
    assert activated.status_code == 409, activated.data
    assert activated.data["message_key"] == "rating.discounts.activate_retired"

    # BR-RAT-072: approving the first version lifts the DISCOUNT out of draft,
    # which is the column DIS-01 shows and the one the defect is named for.
    with tenant_ctx(env.tenant):
        discount = discount_models.Discount.objects.get(tenant=env.tenant, pk=discount_id)
    assert discount.status == discount_models.DISCOUNT_ACTIVE

    # Hard rule 7 — each act wrote its own row, and the self-approval is named
    # rather than left to be inferred from two matching user ids.
    actions = audit_actions(audit_rows)
    assert "discount.version_submitted" in actions
    assert "discount.version_self_approved" in actions
    assert "discount.version_activated" not in actions  # no Activate any more


def test_the_requirement_is_computed_at_submit_and_stored_with_its_threshold(env):
    """§A7.6 — an approver must see the requirement the SUBMITTER saw, so what
    decided it is written onto the row at submit and never recomputed.

    ⚠ **AMENDED 2026-09-10 (`BR-RAT-964`): THE THRESHOLD NOW STARTS UNSET, SO
    THE STORED PAIR IS `(False, None)` FOR EVERY BUDGET.** PO verbatim: *"Keep
    the plumbing, default it off. The threshold setting stays but starts unset,
    so nothing ever requires a second approval unless a utility deliberately
    turns it on."* This case used to assert `$50,000` (PO 2026-08-21, OQ-290) on
    both sides of the bar. **What it still protects is unchanged and is the
    reason it is not deleted:** whatever the answer was at SUBMIT is what the row
    carries, so a tenant who changes the setting afterwards cannot move the bar
    under a signature already given."""
    discount_id, version_id = _draft(env, code="UNDERBAR", budget_cap="49999.99")
    submitted = _post(env, rating_api.discount_version_submit, discount_id, version_id)
    assert submitted.data["second_approval_required"] is False
    assert submitted.data["second_approval_threshold"] is None

    # ⚠ AMENDED 2026-09-10 (`BR-RAT-964`). The figure that USED to trip the bar
    # trips nothing now, and the row says so rather than storing a threshold
    # nobody set. **What this case protects is unchanged and is why it is not
    # deleted:** whatever the answer was at SUBMIT is what the row carries, so a
    # tenant who turns the setting on afterwards cannot move the bar under a
    # signature already given (§A7.6).
    over_id, over_version = _draft(env, code="OVERBAR", budget_cap="50000.01")
    over = _post(env, rating_api.discount_version_submit, over_id, over_version)
    assert over.data["second_approval_required"] is False
    assert over.data["second_approval_threshold"] is None


def test_no_budget_cap_no_longer_requires_the_second_approval_over_http(env):
    """⚠ **THE CLAUSE THAT HAD TO GO WITH THE REST, OVER HTTP — `BR-RAT-964`.**

    BR-RAT-077 (PO 2026-08-19) said *"a discount with no budget cap ALWAYS
    requires the second approval"*, and that clause reads no threshold at all —
    so with the bar unset it would have gone on firing over the route, and an
    assistance programme with no cap (the one a small utility is most likely to
    write) would still have demanded an approver it may not have. **This case
    asserted `True` until 2026-09-10 and asserts `False` now**, which is the
    ruling and not a weakening: the reasoning behind BR-RAT-077's clause is
    preserved in `BR-RAT-964` and comes back the moment a utility types a figure
    into Settings."""
    discount_id, version_id = _draft(env, code="UNBOUNDED", budget_cap=None)
    submitted = _post(env, rating_api.discount_version_submit, discount_id, version_id)
    assert submitted.data["second_approval_required"] is False
    assert submitted.data["second_approval_threshold"] is None


def test_a_submitter_may_approve_their_own_filing_and_the_route_records_it(env):
    """PO 2026-08-19, verbatim *"yes allow it"* — Silver Creek has 1–2 staff.
    The route does not re-decide it; it carries the service's recorded fact."""
    discount_id, version_id = _draft(env, code="SELFAPP")
    _post(env, rating_api.discount_version_submit, discount_id, version_id)
    approved = _post(env, rating_api.discount_version_approve, discount_id, version_id)
    assert approved.data["self_approved"] is True


# ══════════════════════════════════════════════════════════════════════════
# 3 · WHAT THE ROUTES REFUSE
# ══════════════════════════════════════════════════════════════════════════


def test_a_version_belonging_to_another_discount_is_a_404(env):
    """The nesting is a CLAIM and it is checked. Without the pair read, a
    mistyped discount id would silently act on the version the second id
    names — and the version WOULD move, because the service is keyed by version
    id alone."""
    _, version_id = _draft(env, code="MINE")
    other_id, _ = _draft(env, code="THEIRS")
    response = _post(env, rating_api.discount_version_submit, other_id, version_id)
    assert response.status_code == 404
    # …and the version it named is untouched.
    with tenant_ctx(env.tenant):
        version = discount_models.DiscountVersion.objects.get(tenant=env.tenant, pk=version_id)
    assert version.status == discount_models.VERSION_DRAFT


def test_a_version_of_another_tenant_is_a_404(env, other_env):
    """Hard rule 1. The service is tenant-scoped and so is the pair read; this
    proves the route inherits both."""
    foreign_discount, foreign_version = _draft(other_env, code="FOREIGN")
    response = _post(env, rating_api.discount_version_submit, foreign_discount, foreign_version)
    assert response.status_code == 404


def test_a_malformed_version_id_is_a_404_not_a_database_error(env):
    """A path segment is a string until something validates it. Without the
    `_valid_uuid` guard this is a 500 on PostgreSQL, which tells an attacker
    more than a 404 and tells a clerk nothing."""
    discount_id, _ = _draft(env, code="BADID")
    response = _post(env, rating_api.discount_version_submit, discount_id, "not-a-uuid")
    assert response.status_code == 404


def test_approving_something_that_was_never_submitted_is_refused(env):
    """BR-RAT-077's state machine: approval is an act on a PENDING version, so
    a draft cannot collect a signature it never asked for. The refusal names its
    rule, per B8 — G9's error envelope, not a bare 400."""
    from core import errors

    discount_id, version_id = _draft(env, code="UNSUBMITTED")
    response = _post(env, rating_api.discount_version_approve, discount_id, version_id)
    assert response.status_code == 409
    assert response.data["code"] == errors.BIZ_STATE
    assert response.data["br_ref"] == "BR-RAT-077"


def test_a_clerk_cannot_move_a_discount_through_its_lifecycle(env):
    """BR-RAT-083: anyone with the module may DRAFT; only Owner/Admin may
    ACTIVATE. Defense in depth — the DRF permission class AND the service's own
    `@require_role` both refuse, so this asserts a refusal, not which one."""
    discount_id, version_id = _draft(env, code="CLERKACT")
    response = _post(
        env, rating_api.discount_version_submit, discount_id, version_id, role="billing_clerk"
    )
    assert response.status_code in (401, 403)


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE ID THE SCREEN ACTS ON
# ══════════════════════════════════════════════════════════════════════════


def test_the_detail_serves_the_version_id_the_lifecycle_routes_need(env):
    """`version_status` was served from the day this row was written and
    `version_id` was not, so the definition detail could SAY "Draft" and could
    do nothing about it. RED before the selector change: KeyError/None."""
    from apps.rating import selectors

    discount_id, version_id = _draft(env, code="HASID")
    with tenant_ctx(env.tenant):
        detail = selectors.discount_detail(discount_id)
    assert detail["version_id"] == version_id
    assert detail["version_status"] == discount_models.VERSION_DRAFT
    assert uuid.UUID(detail["version_id"])


def test_a_discount_with_no_version_serves_a_null_version_id(env):
    """`create_discount` always writes v1, so this is the shape a FUTURE caller
    could produce — served as null rather than as a missing key, because the
    client's type says `string | null` and a missing key reads as neither."""
    from apps.rating import selectors

    with tenant_ctx(env.tenant):
        discount = discount_models.Discount.objects.create(
            tenant=env.tenant, code="NOVERSION", name="No version yet"
        )
        detail = selectors.discount_detail(str(discount.id))
    assert detail["version_id"] is None
    assert detail["version_status"] is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-400 (12-governance/10-defect-log.csv) + CR-013 part 3 VERBATIM +
#         BR-RAT-072/077/083 + the PO rulings of 2026-08-19 (a submitter may
#         approve their own filing) and 2026-08-21 (the threshold is $50,000,
#         OQ-290) + CLAUDE.md hard rules 1 and 7
# generated: 2026-08-21 by the Wave C lane (DEF-400 · DEF-444)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the build report on apps/rating/api.py
# exceptions: the guarded-function probe reads SOURCE rather than the module
#             registry, deliberately: a decorator applied dynamically would pass
#             a registry check and is not how any service in this module is
#             written. If that ever changes the probe must change with it.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
