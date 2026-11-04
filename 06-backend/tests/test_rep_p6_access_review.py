# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` — R36 Access Review, the joining read.
#           Drawing read as an IMAGE (B14 rule 42): p066.
# Rules:    NFR-3 (pagination in SQL — and the drawing refuses the
#           it-is-only-nine-rows exemption BY NAME) · NFR-5 (no hard caps) ·
#           BR-IDN-011 (membership statuses) · BR-IDN-014 (the A4 matrix is the
#           signed grid) · BR-IDN-026 (a session is capped at twelve hours) ·
#           BR-REP-024 (never a 0 where a figure is not derivable) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · B14 rule 31 (no uuid on
#           screen)
# ───────────────────────────────────────────────────────
"""**R36 ACCESS REVIEW** — one row per user of this tenant.

⚠ **EVERY CASE ASSERTS A KNOWN NON-ZERO COUNT.** A query returning nothing
reads as *"no error"*, which is this repository's commonest false pass. The one
case asserting a ZERO — the `never_signed_in` tile on a tenant where everybody
has signed in — sits beside a positive one in the SAME fixture, so an empty
fixture fails the positive case before the zero can pass.

⚠ **NOTHING HERE SKIPS.** Every fixture creates what it needs.

⚠ **THE SUITE RUNS ON IN-MEMORY SQLITE** (`config/settings/test.py` hardcodes
it and ignores `DATABASE_URL`), so these cases prove the SHAPE and the
ARITHMETIC and can prove nothing about LIMIT/OFFSET cost, the query plan or
RLS. Hard-won law 14. The PostgreSQL half is `10-scripts/p6_join_cost.py`.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.identity import access_review as report
from apps.identity.models import A4_MATRIX, Role, TenantMembership, User
from apps.reports import datasets, queries, runner

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: Four staff, chosen so every assertion names a NUMBER and no two subsets
#: share one: an administrator who may approve, a clerk who may only request,
#: an executive who may approve, and one invited account that has never signed
#: in. `9` on the drawing is an illustration (B14 rule 37); the SHAPE is what
#: is asserted.
#:
#: ⚠ **THESE ARE DELTAS, NOT ABSOLUTES, AND THE FIRST DRAFT GOT THAT WRONG.**
#: The `brazos` fixture provisions a tenant that ALREADY HOLDS STAFF — it has
#: to, because a tenant with no administrator cannot be acted on — so the first
#: version asserted `total == 4` against a tenant holding five and
#: `can_approve_money == 2` against three. Both failed, which is the right
#: outcome; a test that had been written to whatever number came back would
#: have been a test of the fixture rather than of the report.
#:
#: **So every case reads a BASELINE first and asserts the MOVEMENT**, and also
#: asserts the absolute is non-zero — so an empty answer still fails, which is
#: the false pass the delta form could otherwise open.
STAFF = 4
ACTIVE = 3
NEVER_SIGNED_IN = 1
CAN_APPROVE = 2  # system_admin + executive — the clerk may only REQUEST


def _baseline():
    """What this tenant already holds, before the fixture adds anything.

    Called INSIDE `tenant_ctx` and before `_four`, so the numbers below are
    movements this fixture caused and nothing else.
    """
    return report.access_review(per=None)["totals"]


def _role(code, name):
    return Role.objects.get_or_create(code=code, defaults={"name": name})[0]


def _four(tenant):
    """Four memberships on one utility, each with a stated role and status."""
    now = timezone.now()
    people = (
        ("okonkwo@example.test", "M. Okonkwo", "system_admin", "Administrator", "active", 0),
        ("dana@example.test", "Dana Whitfield", "billing_clerk", "Billing clerk", "active", 1),
        ("erin@example.test", "E. Vance", "executive", "Executive", "active", 3),
        ("halloran@example.test", "J. Halloran", "billing_clerk", "Billing clerk", "invited", None),
    )
    created = []
    for email, full_name, role_code, role_name, status, days_ago in people:
        user = User.objects.create(tenant=tenant, email=email, full_name=full_name)
        membership = TenantMembership.objects.create(
            tenant=tenant,
            user=user,
            role=_role(role_code, role_name),
            status=status,
            invited_at=now - timedelta(days=30),
            last_active_at=None if days_ago is None else now - timedelta(days=days_ago),
        )
        created.append(membership)
    # The administrator added everybody else — the drawn ADDED BY column.
    for membership in created[1:]:
        membership.invited_by = created[0].user
        membership.save(update_fields=["invited_by"])
    return created


def test_one_row_is_one_user_and_the_tiles_foot_to_the_whole_set_not_the_page(brazos):
    """The grain, the page and the four tiles — p066.

    ⚠ **THE PAGE IS CUT AND THE TILES DO NOT MOVE.** That is the whole of
    §7.2's argument and the reason a tile is a SQL aggregate over the filtered
    set: a page of two must still report four users.
    """
    with tenant_ctx(brazos):
        before = _baseline()
        _four(brazos)
        result = report.access_review(per=2, page=1)

    assert result["grain"] == "one user of this tenant"
    assert len(result["rows"]) == 2  # the page
    totals = result["totals"]
    # ⚠ THE PAGE IS TWO AND THE TILE IS THE WHOLE SET — the two must differ,
    # or this case could not tell a tile struck over the page from one struck
    # over the filtered set, which is the whole thing it exists to check.
    assert result["total"] > len(result["rows"])
    assert result["total"] == totals["users"]
    assert totals["users"] - before["users"] == STAFF
    assert totals["active"] - before["active"] == ACTIVE
    assert totals["never_signed_in"] - before["never_signed_in"] == NEVER_SIGNED_IN
    # The positive case this zero-capable tile sits beside.
    assert totals["users"] > 0
    assert result["pages"] == max(1, -(-result["total"] // 2))


def test_a_billing_clerk_may_request_and_is_NOT_counted_as_able_to_approve_money(brazos):
    """⚠ **THE ONE CASE THAT WOULD HAVE SHIPPED WRONG.**

    `A4_MATRIX`'s `adjustment_approval` row reads system_admin: Approve,
    billing_clerk: **Request**, executive: Approve — and all three are non-dash
    cells, so all three are seeded into `role_permissions`. A join through the
    permission table therefore says YES for a clerk who may only REQUEST, and a
    security report that overstates who can approve money is worse than one
    that does not exist. The drawing draws exactly this distinction.
    """
    with tenant_ctx(brazos):
        before = _baseline()
        _four(brazos)
        result = report.access_review(per=None)

    by_role = {row.role_code: row.can_approve_money for row in result["rows"]}
    assert by_role["system_admin"] is True
    assert by_role["executive"] is True
    assert by_role["billing_clerk"] is False
    # ⚠ THE MOVEMENT IS 2 AND NOT 3: this fixture adds one administrator, one
    # executive and TWO billing clerks, and only the first two may approve. A
    # join through `role_permissions` would move this by 4.
    moved = result["totals"]["can_approve_money"] - before["can_approve_money"]
    assert moved == CAN_APPROVE
    assert result["totals"]["can_approve_money"] > 0
    # And the clerks ARE in the report — otherwise `moved == 2` would also be
    # true of a query that simply dropped them.
    clerks = [row for row in result["rows"] if row.role_code == "billing_clerk"]
    assert len(clerks) >= 2
    assert all(row.can_approve_money is False for row in clerks)
    # And the rule is READ from the signed grid rather than typed here, so the
    # two cannot drift: this asserts the grid still says what the test assumes.
    cells = next(cells for code, _label, cells in A4_MATRIX if code == "adjustment_approval")
    assert cells["billing_clerk"] == "Request"
    assert cells["system_admin"] == "Approve"


def test_the_never_signed_in_row_is_SERVED_which_is_what_the_audit_grain_could_not_do(brazos):
    """The row the `audit_log` dataset is structurally blind to.

    A user who has never signed in has written no audit event, so on an
    event-grain query the NEVER SIGNED IN tile reads 0 over a real dormant
    login. Here the row exists, the flag is on it, and the tile counts it.
    """
    with tenant_ctx(brazos):
        _four(brazos)
        result = report.access_review(per=None)

    dormant = [row for row in result["rows"] if row.never_signed_in]
    mine = [row for row in dormant if row.user_name == "J. Halloran"]
    assert len(mine) == NEVER_SIGNED_IN
    assert mine[0].last_active_at is None
    assert mine[0].status == "invited"
    assert result["totals"]["never_signed_in"] >= NEVER_SIGNED_IN


def test_the_sign_in_substitution_TRAVELS_and_is_never_silent(brazos):
    """The drawn header is LAST SIGN-IN and the served column is LAST ACTIVE.

    The substitution is published in `problems` so a renderer and a reader both
    know. A row field named `last_sign_in_at` would let the drawn header be
    printed over it by accident, which is why no such field exists.
    """
    with tenant_ctx(brazos):
        _four(brazos)
        result = report.access_review()

    codes = {problem["code"] for problem in result["problems"]}
    assert "last_sign_in_is_served_as_last_active" in codes
    assert "membership_status_is_today_s_even_when_as_of_is_not" in codes
    assert not any(field == "last_sign_in_at" for field in vars(result["rows"][0]))


def test_the_restriction_is_RECORDED_in_the_module_and_never_PUBLISHED(brazos):
    """⚠ **RATIONALE IS ZERO WORDS ON SCREEN (B14 rule 33).**

    `problems` is rendered by `ReportViewerPage` through `ReportGapList`, so
    anything put there reaches a clerk. Where `BR-REP-023` is enforced, and why
    this read model does not enforce it itself, are engineering facts — useful
    to the next reader of this file and of no use to a compliance officer
    reading the figures.

    ⚠ **AND IT WAS A SECURITY DISCLOSURE UNTIL `P5.9` LANDED.** The constant
    said the restriction was NOT enforced; printing that ON the report tells
    whoever is reading it that the door is open. `P5.9` closed the hole and the
    constant was amended — **the test kept its shape through both**, which is
    the point of asserting the absence from the payload rather than the wording
    of the sentence.

    ⚠ **NEITHER CONSTANT IS DELETED.** A record dropped is a record nobody can
    find, so both are asserted to still EXIST.
    """
    with tenant_ctx(brazos):
        _four(brazos)
        result = report.access_review()

    codes = {problem["code"] for problem in result["problems"]}
    assert "br_rep_023_is_enforced_by_the_role_gate_not_here" not in codes
    assert "approve_money_reads_the_signed_grid_not_role_permissions" not in codes
    # The constants survive — the record is kept, the screen is not told.
    assert (
        report.WHERE_THE_RESTRICTION_LIVES["code"]
        == "br_rep_023_is_enforced_by_the_role_gate_not_here"
    )
    assert (
        report.CAN_APPROVE_IS_THE_MATRIX_NOT_THE_JOIN["code"]
        == "approve_money_reads_the_signed_grid_not_role_permissions"
    )


def test_it_pages_at_four_rows_because_NFR_3_admits_no_exceptions(brazos):
    """p066: *"it is still served paginated, because `NFR-3` admits no
    exceptions"*. Page two holds the remainder and repeats nothing."""
    with tenant_ctx(brazos):
        _four(brazos)
        whole = report.access_review(per=None)
        # `ceil`, not `// + 2` — `BR-SHL-011` CLAMPS a page past the end to
        # the last one, so an over-run counts the final page twice.
        last_page = max(1, -(-whole["total"] // 3))
        pages = [
            report.access_review(per=3, page=page, sort="user", direction="asc")
            for page in range(1, last_page + 1)
        ]

    total = whole["total"]
    assert total > 3  # or there is only one page and this case proves nothing
    assert len(pages[0]["rows"]) == 3
    seen = [row.membership_id for page in pages for row in page["rows"]]
    assert len(seen) == total
    assert len(set(seen)) == total  # nothing repeated, nothing skipped


def test_the_export_stream_takes_no_page_and_no_per_at_all(brazos):
    """`NFR-5` and §8.2 p91 — a file cannot inherit a screen's page size
    because there is no argument through which to pass one."""
    import inspect

    signature = inspect.signature(report.access_review_stream)
    assert "page" not in signature.parameters
    assert "per" not in signature.parameters

    with tenant_ctx(brazos):
        _four(brazos)
        paged = report.access_review(per=2, page=1)
        streamed = list(report.access_review_stream())
    # NFR-5 — the export is the WHOLE filtered set, not a page of it.
    assert len(streamed) == paged["total"]
    assert len(streamed) > len(paged["rows"])


def test_as_of_narrows_MEMBERSHIP_and_says_it_cannot_narrow_STATUS(brazos):
    """`BR-TEN-043` — an argument, never a clock; and the as-is/as-was gap is
    STATED rather than guessed at."""
    with tenant_ctx(brazos):
        memberships = _four(brazos)
        whole = report.access_review(per=None)
        newcomer = memberships[-1]
        newcomer.invited_at = timezone.now()
        newcomer.save(update_fields=["invited_at"])
        yesterday = (timezone.now() - timedelta(days=1)).date()
        result = report.access_review(as_of=yesterday, per=None)

    assert result["total"] == whole["total"] - 1
    assert result["total"] > 0
    codes = {problem["code"] for problem in result["problems"]}
    assert "membership_status_is_today_s_even_when_as_of_is_not" in codes


def test_the_role_filter_is_HONOURED_and_not_declared_and_dropped(brazos):
    """A chip that changes the URL and nothing else is hard-won law 2's mirror."""
    with tenant_ctx(brazos):
        before = _baseline()
        _four(brazos)
        result = report.access_review(role="billing_clerk", per=None)
        unfiltered = report.access_review(per=None)

    # Two of this fixture's four are billing clerks.
    assert result["total"] >= 2
    assert {row.role_code for row in result["rows"]} == {"billing_clerk"}
    # ⚠ AND THE FILTER MUST NARROW — a chip that changes nothing is the mirror
    # of dead UI, and `result == unfiltered` is exactly what that looks like.
    assert result["total"] < unfiltered["total"]
    assert unfiltered["total"] - before["users"] == STAFF


def test_the_drawn_controls_are_DECLARED_on_the_dataset_so_bind_cannot_drop_them(brazos):
    """⚠ **THE WIRING TEST, AND IT IS THE ONE THAT WOULD HAVE CAUGHT A DEAD
    CONTROL.** `runner.bind` drops any parameter the DATASET does not declare,
    so `As of` and `Role` had to be added to `AUDIT_LOG.filters` — otherwise
    both selects would change the URL and nothing else, and `runner.dropped()`
    would have been the only place in the product that knew."""
    audit = datasets.BY_CODE["audit_log"]
    assert "as_of" in audit.filters
    assert "role" in audit.filters
    definition = runner.resolve("access_review")
    bound = runner.bind(definition, {"as_of": "2026-09-25", "role": "billing_clerk"})
    assert bound["as_of"] == "2026-09-25"
    assert bound["role"] == "billing_clerk"


def test_the_per_key_viewer_wins_over_the_dataset_that_refuses_this_report(brazos):
    """`queries_for` checks `VIEWERS` first, which is the only way a report can
    be served at a grain its own dataset refuses — and `definition_refusal()`
    asks the same map first, so the catalogue card and the viewer agree."""
    assert queries.VIEWERS["access_review"] is queries.access_review
    assert runner.queries_for("access_review", "audit_log") is queries.access_review
    assert queries.definition_refusal("access_review", "audit_log") is None
    # The audit dataset's own refusal is UNCHANGED and still names the report.
    from apps.audit import audit_log_dataset

    reason = audit_log_dataset.unservable_reason("access_review")
    assert reason["drawn_grain"] == "one USER"


def test_the_export_reaches_the_per_key_STREAM_and_not_the_dataset_generator(brazos):
    """⚠ **THREE GENERATORS NOTHING COULD CALL WOULD HAVE BEEN DEAD CODE.**
    `stream_for` looked up by DATASET alone, so R36's export would have fallen
    back to `run(whole=True)` — correct rows, and the whole set materialised
    instead of streamed. Hard-won law 2, caught in the same commit."""
    assert runner.stream_for("access_review", "audit_log") is queries.access_review_rows


def test_no_uuid_is_a_drawn_column(brazos):
    """B14 rule 31. `membership_id` travels for drill-through and is not among
    the columns the viewer publishes."""
    assert "membership_id" not in queries.ACCESS_REVIEW_COLUMNS
    assert "user_name" in queries.ACCESS_REVIEW_COLUMNS
