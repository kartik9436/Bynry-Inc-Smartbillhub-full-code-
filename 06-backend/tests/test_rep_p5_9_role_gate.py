# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 5 task `P5.9`
#          (role gating on a definition, `min_role` resolved server-side).
#          Outcome, verbatim: *"A Billing Clerk cannot run the access-review
#          report."*
# Rules:   BR-REP-023 (access-review: System Admin + Executive only — Billing
#          Clerk excluded; PO AR-1, 2026-08-08, CONFIRMED) ·
#          hard-won law 1 (a comment claiming a guarantee is not the
#          guarantee) · law 3 (defaults fail closed) · law 7 (prove it RED,
#          and ask what would make it pass WRONGLY) · B14 rule 33
# ───────────────────────────────────────────────────────
"""WHO MAY RUN THE ACCESS-REVIEW REPORT — the guarantee, not the note.

⚠ **THIS RULE WAS SIGNED ON 2026-08-08 AND ENFORCED BY NOTHING FOR FIFTY
DAYS.** Three files cited it — `apps/reports/catalog.py`'s trace header,
`apps/audit/audit_log_dataset.py`'s `security_note`, and a test asserting the
NOTE was present — and `GET /reports/access_review` ran for a Billing Clerk.
A test that asserts a rule is MENTIONED is the purest form of hard-won law 1,
and one of them is in this repo today; these cases assert the BEHAVIOUR.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY**, asked of each before it was written:

  · *"a Billing Clerk cannot run it"* would pass over a gate that refuses
    EVERY role, so every case has its positive twin — the same clerk runs an
    unrestricted report in the same test, and an Executive runs the restricted
    one;
  · *"the card is absent"* would pass over a catalogue that returns nothing at
    all, so the case counts the OTHER cards and asserts they are still there;
  · the rank map would pass over a hard-coded `role == "billing_clerk"` check,
    so an UNKNOWN role is asserted refused — that is the fail-closed half, and
    it is the half a `!=` comparison gets backwards;
  · `may_run` over a min_role nothing declares would pass over a permissive
    default, so a garbage value is asserted to refuse rather than admit.
"""

from __future__ import annotations

import pytest

from apps.reports import catalogue_read, role_gate
from apps.reports.models import ReportDefinition

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

RESTRICTED_KEY = "access_review"


# ═══════════════════════════════════════════════════════════════════════════
# THE PURE FUNCTION — no database, so a failure here names the LADDER
# ═══════════════════════════════════════════════════════════════════════════
def test_no_min_role_admits_every_staff_role():
    """45 of the 46 rows carry no floor; the route's own gate is the floor.

    ⚠ **ALL FOUR PREDEFINED ROLES, INCLUDING `field_technician`.** The product
    has four, not three — a lane that writes three here is testing its own
    assumption rather than `apps/identity`'s vocabulary.
    """
    for role in ("billing_clerk", "executive", "system_admin", "field_technician"):
        assert role_gate.may_run(None, role) is True
        assert role_gate.may_run("", role) is True


def test_br_rep_023_exactly_as_signed():
    """*"System Admin + Executive only — Billing Clerk excluded."*"""
    assert role_gate.may_run("executive", "billing_clerk") is False
    assert role_gate.may_run("executive", "executive") is True
    assert role_gate.may_run("executive", "system_admin") is True


@pytest.mark.parametrize(
    "unknown", ["", None, "auditor", "BILLING_CLERK", "admin", "field_technician"]
)
def test_a_role_below_the_floor_or_unknown_to_it_is_refused(unknown):
    """⚠ **FAILS CLOSED, AND THIS IS THE CASE A `!=` CHECK GETS BACKWARDS.**

    A role added to `apps/identity` tomorrow must not silently acquire the
    access-review report. `BILLING_CLERK` is in the list on purpose: the map is
    keyed on the exact code, and a case-folding bug would otherwise read as a
    pass.
    """
    assert role_gate.may_run("executive", unknown) is False


def test_a_min_role_nothing_declares_refuses_rather_than_admits():
    """A typo in the column is a restriction nobody can read. It refuses."""
    assert role_gate.may_run("Executive", "system_admin") is False
    assert role_gate.may_run("superuser", "system_admin") is False


def test_the_refusal_is_403_and_names_the_report_not_the_role():
    """B14 rule 33 — the reason is zero words on screen, and the list of
    restricted reports is not published to the person refused."""
    from core import errors

    refusal = role_gate.refusal(RESTRICTED_KEY)
    assert refusal.code == errors.AUTH_PERMISSION_DENIED
    assert refusal.http_status == 403
    assert refusal.message_key == "reports.viewer.role_refused"
    assert refusal.params == {"key": RESTRICTED_KEY}


# ═══════════════════════════════════════════════════════════════════════════
# THE DATA HALF — the seed carries the restriction `reports/0007` wrote
# ═══════════════════════════════════════════════════════════════════════════
def test_the_access_review_row_carries_the_floor_and_the_others_do_not(brazos):
    with tenant_ctx(brazos):
        restricted = {
            row.key: row.min_role
            for row in ReportDefinition.objects.filter(tenant_id=None).exclude(min_role=None)
        }
    assert restricted == {RESTRICTED_KEY: "executive"}, (
        "exactly one platform row is restricted today — BR-REP-023's. A second "
        "one appearing here is a rule nobody wrote down"
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE CATALOGUE — absent, not greyed, and the rest of the grid survives
# ═══════════════════════════════════════════════════════════════════════════
def _keys(payload):
    return {card["key"] for card in payload["cards"]}


def test_the_clerks_catalogue_omits_it_and_keeps_everything_else(brazos):
    with tenant_ctx(brazos):
        clerk = catalogue_read.catalogue_payload({"per": 200}, role="billing_clerk")
        exec_ = catalogue_read.catalogue_payload({"per": 200}, role="executive")

    clerk_keys, exec_keys = _keys(clerk), _keys(exec_)
    assert RESTRICTED_KEY in exec_keys
    assert RESTRICTED_KEY not in clerk_keys
    # ⚠ THE POSITIVE TWIN. Without it this case passes over a catalogue that
    # returns nothing at all for a clerk.
    assert exec_keys - clerk_keys == {RESTRICTED_KEY}
    assert len(clerk_keys) > 1


def test_the_card_is_absent_rather_than_drawn_unavailable(brazos):
    """⚠ **`available: false` IS A DIFFERENT SENTENCE AND WOULD BE THE WRONG
    ONE.** A card drawn with a reason is hard-won law 2's mirror — a live
    control over a refusal — and it also publishes which reports are
    restricted. The row is simply not in the answer."""
    with tenant_ctx(brazos):
        clerk = catalogue_read.catalogue_payload({"per": 200}, role="billing_clerk")
    for card in clerk["cards"]:
        assert card["key"] != RESTRICTED_KEY


def test_a_role_the_map_does_not_know_sees_no_restricted_card(brazos):
    with tenant_ctx(brazos):
        payload = catalogue_read.catalogue_payload({"per": 200}, role="auditor")
    assert RESTRICTED_KEY not in _keys(payload)


def test_no_role_at_all_still_hides_it(brazos):
    """`role=None` is what an internal caller that forgets to pass one gets.
    It must be the CLOSED answer, not the open one (law 3)."""
    with tenant_ctx(brazos):
        payload = catalogue_read.catalogue_payload({"per": 200})
    assert RESTRICTED_KEY not in _keys(payload)


# ═══════════════════════════════════════════════════════════════════════════
# COPY ON WRITE — the viewer and the catalogue must resolve the same row
# ═══════════════════════════════════════════════════════════════════════════
def test_the_tenants_own_copy_decides_for_that_tenant(brazos):
    """A tenant copy REPLACES the platform row by key, in the catalogue and in
    `for_key` alike. If these two ever disagree, a card is drawn onto an
    address that refuses it."""
    with tenant_ctx(brazos):
        platform = ReportDefinition.objects.get(tenant_id=None, key=RESTRICTED_KEY)
        assert role_gate.for_key(RESTRICTED_KEY) == "executive"

        # ⚠ **`bulk_create`, NOT `create`, AND THE REASON IS NOT TIDINESS.**
        # A `post_save` on this table enqueues an audit job, and under
        # `JOBS_EAGER=false` — the setting CLAUDE.md law 14 tells every lane to
        # run these suites with — that enqueue reaches for a broker on
        # localhost:6379 and the case dies on `Connection refused`, naming
        # kombu rather than anything about roles. `bulk_create` sends no
        # `post_save`. This case is about how the READ resolves copy-on-write;
        # the WRITE path has its own file
        # (`test_rep_p5_definition_crud.py`), and proving it twice here would
        # only couple this file to a broker.
        ReportDefinition.objects.bulk_create([ReportDefinition(
            tenant_id=brazos.id,
            key=RESTRICTED_KEY,
            name=platform.name,
            dataset=platform.dataset,
            group_code=platform.group_code,
            sub_group_code=platform.sub_group_code,
            columns=list(platform.columns or []),
            filters=dict(platform.filters or {}),
            min_role=None,
        )])
        assert role_gate.for_key(RESTRICTED_KEY) is None
        # ⚠ **THE COPY LANDS ON THE *CUSTOM* SUB-TAB, NOT ON *STANDARD*.** A
        # tenant row's `origin` is `shared` or `mine`, never `built_in`, and
        # the read filters by sub-tab — so asking the default sub-tab here
        # would assert the copy is absent and pass for the wrong reason.
        keys = _keys(
            catalogue_read.catalogue_payload(
                {"per": 200, "origin": "custom"}, role="billing_clerk"
            )
        )
    assert RESTRICTED_KEY in keys


def test_an_unknown_key_answers_none_rather_than_raising(brazos):
    """Asked BEFORE the key is resolved, so it must be silent about existence —
    otherwise the pair of refusals is a membership oracle over the catalogue."""
    with tenant_ctx(brazos):
        assert role_gate.for_key("revenue_by_srevice") is None
