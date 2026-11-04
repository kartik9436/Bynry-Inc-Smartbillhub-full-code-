# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` — the JOINING READ behind R36 Access Review,
#           one of the fifteen (really seventeen) multi-source reports §9.2
#           lists. Drawing read as an IMAGE (B14 rule 42): p066, rendered at
#           2.6x by `10-scripts/pdf/pdf_render.py`.
# Story:    R36 `access_review` — Compliance › Audit · **As at**
#           (`reports/migrations/0003_seed_catalogue.py` line 254).
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — `tenant_id` on every
#           queryset, RLS FORCE underneath) · NFR-3 (server pagination, applied
#           in SQL, and the drawing REFUSES the it-is-only-nine-rows exemption
#           by name) · NFR-5 (no hard cap) · BR-IDN-011 (membership statuses) ·
#           BR-IDN-014 (the A4 matrix must match the signed grid VERBATIM) ·
#           BR-REP-001 (a report states its basis) · BR-REP-002 (read models
#           only) · BR-REP-023 (this report is restricted — see the gap below)
#           · BR-REP-024 (never a 0 where a figure could not be computed) ·
#           BR-TEN-043 (the business date is an argument, never a clock) ·
#           B14 rule 31 (no database id is ever a visible value)
# Tests:    06-backend/tests/test_rep_p6_access_review.py
#           10-scripts/p6_join_cost.py (the PostgreSQL measurement — hard-won
#           law 14: the default suite is in-memory SQLite)
# Impacts:  apps/reports/report_seams.py (the cross-module caller) ·
#           apps/reports/queries.py (the per-key viewer) ·
#           apps/reports/datasets.py (`AUDIT_LOG.filters` gains `as_of`/`role`)
# ───────────────────────────────────────────────────────
"""**R36 ACCESS REVIEW — one row per USER OF THIS TENANT**, paged and sorted in SQL.

═══════════════════════════════════════════════════════════════════════════════
WHY THIS IS NOT THE `audit_log` DATASET, AND WHY IT IS NOT REALLY TWO SOURCES
═══════════════════════════════════════════════════════════════════════════════
R36 is SEEDED on `audit_log` and its eyebrow line reads *identity + audit*.
`apps/audit/audit_log_dataset.py` refuses it, correctly and by name: that
dataset's grain is one audit EVENT, and **a user who has never signed in has
written no audit events at all**, so the drawn `NEVER SIGNED IN 1` tile would
read 0 over a real dormant login. A security report whose whole purpose is to
find the dormant account cannot be built on a source that is blind to it.

⚠ **MEASURED AGAINST THE DRAWING, AUDIT CONTRIBUTES NOTHING.** p066 draws
`USER · ROLE · ADDED · ADDED BY · LAST SIGN-IN · APPROVE MONEY · STATUS` with
the tiles `USERS 9 · ACTIVE 8 · NEVER SIGNED IN 1 · CAN APPROVE MONEY 3`.
`tenant_memberships` carries `status`, `invited_at`, `invited_by` and
`last_active_at`; `roles` carries the role; `models.A4_MATRIX` carries the
approval cell. **Seven of seven columns and four of four tiles are identity's.**
The brief's own §05 identity row already said so — *"R36 is nine rows and needs
last-sign-in and who-added-whom, which the module has"* — and the source line
on the drawing overstates what audit adds. That correction is filed as
`DEF-REP-6921` rather than left in this docstring to be believed (hard-won law
1), because a comment claiming a measurement is not the measurement.

═══════════════════════════════════════════════════════════════════════════════
THE COLUMN IS `LAST ACTIVE`, NOT `LAST SIGN-IN`, AND THE DIFFERENCE IS THE WHOLE
POINT OF THE REPORT
═══════════════════════════════════════════════════════════════════════════════
The drawing's header reads **LAST SIGN-IN**. The durable column is
`TenantMembership.last_active_at`, whose own comment in `models.py` reads *"null
renders 'Never'"*. The literal sign-in timestamp is `sessions.created_at` — and
**`sessions` is ephemeral**: a session is capped at twelve hours (`BR-IDN-026`)
and rows are cleaned up, so `MAX(sessions.created_at)` for somebody who last
signed in a year ago is **nothing at all**.

So serving `MAX(sessions.created_at)` under a header reading *Last sign-in*
would print **Never** beside a person who signed in last year — **which is the
exact failure this report exists to catch, manufactured by the report itself.**
It is also the same shape as the audit refusal above: a source that cannot see
the dormant case is the wrong source for the dormant case.

**The column is therefore served as `last_active_at` and is LABELLED what it
is.** Coordinator ruling, 2026-09-27: *"Serve `last_active_at` and label it what
it is… Build it as Last active, and say so in the file's own docstring with the
reason. If the PO wants the drawn wording back, that is a copy change and a
small one."* `SIGN_IN_IS_LAST_ACTIVE` publishes the substitution beside the rows
so no reader has to infer it, and the report never claims a fact it does not
hold.

═══════════════════════════════════════════════════════════════════════════════
`CAN APPROVE MONEY` CANNOT BE ANSWERED FROM `role_permissions`, AND THIS IS WHY
═══════════════════════════════════════════════════════════════════════════════
The obvious read is *does this role hold the `adjustment_approval` permission* —
and it is **wrong in the one direction that matters.** `A4_MATRIX`'s
`adjustment_approval` row is::

    system_admin: Approve · billing_clerk: Request · executive: Approve

All three are non-"—" cells, so **all three are seeded into
`role_permissions`** — and the CELL VALUE has no column anywhere in B2
(`models.py` says so: *"the CELL VALUES … have NO B2 column"*). A billing clerk
who may only REQUEST an adjustment therefore holds the same row as an
administrator who may APPROVE one.

The drawing draws that distinction and depends on it: Dana Whitfield, Billing
clerk, reads **No**; M. Okonkwo, Administrator, reads **Yes**. A join through
`role_permissions` would have printed **Yes** for the clerk — a security report
overstating who can approve money, which is worse than one that does not
exist. So the answer is read from `A4_MATRIX`, which is identity's own
transcription of the SIGNED grid (`BR-IDN-014`), keyed on the role code, cell
equal to `Approve`. One source of truth, and it is the signed one.

⚠ `CAN_APPROVE_IS_THE_MATRIX_NOT_THE_JOIN` states that out loud in `problems`,
because a reader who knows the permission table exists will otherwise assume it
was used.

═══════════════════════════════════════════════════════════════════════════════
`As at` IS A REAL BASIS, AND IT NARROWS MEMBERSHIP AND NOT STATUS
═══════════════════════════════════════════════════════════════════════════════
R36 is seeded `EVENT · "As at"` and its drawn bar's first control is
`As of 09/25/2026`. `as_of` is an ARGUMENT (`BR-TEN-043`) and never a clock.

It does exactly ONE thing, because only one is honest: **a membership invited
after `as_of` was not a user of this tenant yet and is excluded.** It does NOT
reconstruct a past STATUS — `tenant_memberships.status` is a pointer a
transition overwrites and there is no effective-dated history on the table, so
`STATUS` and the `ACTIVE` tile describe today even when `as_of` is six months
back. That is published as `GAP_STATUS_IS_AS_IS_NOT_AS_WAS` rather than guessed
at, and it is the same fault line `apps/assets/assets_dataset.py` already
states on its own table.

═══════════════════════════════════════════════════════════════════════════════
IT PAGES IN SQL AT NINE ROWS, DELIBERATELY
═══════════════════════════════════════════════════════════════════════════════
p066, verbatim: *"Ten staff is the whole ICP, so this is nine rows and not a
paginated list — and it is still served paginated, because `NFR-3` admits no
exceptions and the four places that claimed one are the defect `DEF-PAY-4221`
exists to close."*

So the page is a `LIMIT`/`OFFSET` on a QuerySet and the order is an `ORDER BY`.
**Nothing is sorted or sliced in Python in this file.** `access_review_stream()`
is a separate function with no `page` and no `per`, so an export has no argument
through which to inherit a screen's fifty rows — a flag would have had that bug;
a missing parameter cannot.

═══════════════════════════════════════════════════════════════════════════════
WHAT IT WILL NOT DO
═══════════════════════════════════════════════════════════════════════════════
**It writes nothing.** No INSERT, UPDATE, DELETE or `save()`, on any table.

**It serves no uuid as a visible value** (B14 rule 31) — the user's name and
email are the identifiers a person reads; `membership_id` travels for
drill-through and is not a drawn column.

**It never falls back to zero.** `BR-REP-024`: an underivable figure is `None`
beside a named reason.

**It does not enforce `BR-REP-023` and it does not need to.** The restriction
on who may RUN this report is `apps/reports/role_gate.py` — `P5.9`, which
landed on 2026-09-27 while this file was being written — and it resolves
SERVER-SIDE at the catalogue and at the run. This read model adds no
authorisation check of its own: wrong layer, and a second check is how two
answers to *who may see this* come to exist. `WHERE_THE_RESTRICTION_LIVES`
records that, so the absence reads as a decision.

⚠ **THAT CONSTANT SAID THE RULE WAS UNENFORCED UNTIL `P5.9` LANDED, AND IT IS
AMENDED RATHER THAN LEFT.** A stale claim on a SECURITY rule is the worst kind
— `role_gate.py`'s own docstring opens by recording that three files cited
`BR-REP-023` while nothing enforced it — and this file would have shipped the
mirror image of that: a claim of absence over a rule that had just been built.

⚠ **NEITHER IT NOR THE APPROVE-MONEY RATIONALE IS PUBLISHED TO THE SCREEN.**
`problems` is rendered by the viewer, and B14 rule 33 puts RATIONALE at zero
words on screen. When the constant still said *not enforced*, publishing it
would also have told whoever was reading the report that the door was open.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from django.db.models import Count, Q

from apps.identity.models import A4_MATRIX, TenantMembership
from core.pagination import order_terms
from core.tenancy import current_tenant_id

#: `BR-REP-001`'s date label. This report serves NO money column, so there is no
#: posting/clearing basis to name and none is invented; the seeded basis is
#: `EVENT · "As at"` and `as_of` is what it is struck at.
BASIS_DATE = "as_at"

#: The A4 row that decides `CAN APPROVE MONEY`, and the cell value that means
#: yes. ⚠ **`Request` IS NOT `Approve`** — see the docstring; reading the
#: presence of the permission instead of the cell prints Yes for a clerk.
APPROVAL_ROW = "adjustment_approval"
APPROVAL_CELL = "Approve"

#: `BR-IDN-011`'s three membership statuses, spelled as `models.py` spells them.
STATUS_INVITED = "invited"
STATUS_ACTIVE = "active"
STATUS_DEACTIVATED = "deactivated"

#: What a caller may order by. ⚠ **EVERY TUPLE ENDS IN `id`** — a page is a
#: window over an ORDER, and nine staff invited in one provisioning run share an
#: `invited_at` to the second, so a non-total order would show one person twice
#: and another never. `core.pagination.order_terms` refuses to add a tiebreak
#: silently, so it stays this file's stated decision.
#:
#: `approve_money` is a drawn column with NO entry here on purpose: it is
#: computed from `A4_MATRIX` in Python and there is no SQL expression to order
#: by. Offering the caret would be a live control over a dead sort — hard-won
#: law 2's mirror (`DEF-CWP-3925`).
ACCESS_SORTS: tuple[str, ...] = ("user", "role", "added_on", "last_active", "status")
ACCESS_DEFAULT_SORT = "user"
ACCESS_DEFAULT_DIRECTION = "asc"
ACCESS_SORT_COLUMNS: dict[str, tuple[str, ...]] = {
    "user": ("user__full_name", "user__email", "id"),
    "role": ("role__name", "user__full_name", "id"),
    "added_on": ("invited_at", "user__full_name", "id"),
    "last_active": ("last_active_at", "user__full_name", "id"),
    "status": ("status", "user__full_name", "id"),
}

#: The filters this report accepts — and every one of them is applied below. A
#: filter declared and dropped shows the WHOLE staff list under a chip saying
#: otherwise, which is the fault `JOURNAL_LINES.filters`' own comment records.
ACCESS_FILTERS: tuple[str, ...] = ("as_of", "role", "status")


# ── BR-REP-024: named gaps, never a silent zero and never a plausible number ──

SIGN_IN_IS_LAST_ACTIVE = {
    "code": "last_sign_in_is_served_as_last_active",
    "br_ref": "BR-IDN-026 · BR-REP-024 · B14 rule 33",
    "detail": (
        "The drawing's header reads LAST SIGN-IN. The column served is "
        "`tenant_memberships.last_active_at`, and it is labelled `Last active` rather than "
        "renamed to match the drawing. `sessions` is the only table holding a literal "
        "sign-in timestamp and it is ephemeral — a session is capped at twelve hours "
        "(BR-IDN-026) — so MAX(sessions.created_at) is NOTHING for somebody who last "
        "signed in a year ago, and the drawn header over that value would print `Never` "
        "beside a real returning user. That is the exact failure this report exists to "
        "catch, manufactured by the report. Coordinator ruling 2026-09-27; restoring the "
        "drawn wording is a copy change and a small one."
    ),
    "wanted_reads": ("a durable last-sign-in stamp on `tenant_memberships`",),
}

CAN_APPROVE_IS_THE_MATRIX_NOT_THE_JOIN = {
    "code": "approve_money_reads_the_signed_grid_not_role_permissions",
    "br_ref": "BR-IDN-014 · BR-REP-024",
    "detail": (
        "CAN APPROVE MONEY is read from `identity.models.A4_MATRIX` — the signed A4 grid — "
        "and NOT from `role_permissions`. The `adjustment_approval` row reads "
        "system_admin: Approve, billing_clerk: Request, executive: Approve; all three are "
        "non-dash cells so all three are seeded into `role_permissions`, and the CELL VALUE "
        "has no column in B2. A join through the permission table would therefore print "
        "`Yes` for a billing clerk who may only REQUEST — a security report overstating who "
        "can approve money. The drawing draws exactly that distinction (Dana Whitfield, "
        "Billing clerk: No)."
    ),
    "wanted_reads": ("a cell-value column on `role_permissions`",),
}

GAP_STATUS_IS_AS_IS_NOT_AS_WAS = {
    "code": "membership_status_is_today_s_even_when_as_of_is_not",
    "br_ref": "brief §7.2.4 · BR-IDN-011 · BR-REP-024",
    "detail": (
        "`as_of` narrows MEMBERSHIP by `invited_at`, which is a stored date, and it cannot "
        "narrow the STATUS, which is not effective-dated: a transition overwrites "
        "`tenant_memberships.status` and the only trace is `audit_log`, pruned on a "
        "schedule with no row type exempt (ruled 2026-09-23). So STATUS and the ACTIVE "
        "tile describe today even when `as_of` is six months back. Inferring a past status "
        "would be a guess with a date on it."
    ),
    "wanted_reads": ("an effective-dated status history on `tenant_memberships`",),
}

#: ⚠ **THIS CONSTANT SAID `BR-REP-023` WAS UNENFORCED AND THAT STOPPED BEING
#: TRUE WHILE THIS FILE WAS BEING WRITTEN.** `P5.9` landed in
#: `apps/reports/role_gate.py` with `reports/0008_p5_9_min_role.py`, and the
#: restriction is now resolved SERVER-SIDE: a card a role may not run is absent
#: from the catalogue and `GET /reports/access_review` is refused.
#:
#: **It is amended rather than deleted, and rather than left.** Deleted, the
#: next reader has no way to learn that this read model deliberately does not
#: carry its own authorisation check; left as it was, it is a stale claim on a
#: SECURITY rule, which is the worst kind — `CLAUDE.md`'s prime-directive
#: section records three lanes misled in one evening by exactly that, and a
#: sibling's own `role_gate.py` docstring opens with *"`BR-REP-023` has been
#: signed since 2026-08-08 and nothing enforced it"* while three files cited it.
#:
#: **It is NOT published to the screen either way** — see the module docstring.
WHERE_THE_RESTRICTION_LIVES = {
    "code": "br_rep_023_is_enforced_by_the_role_gate_not_here",
    "br_ref": "BR-REP-023 · CR-142-BRC07 P5.9",
    "detail": (
        "R36 reads identity, so a leak is a security defect. BR-REP-023 restricts who may "
        "run it — System Admin and Executive, Billing Clerk excluded — and that is enforced "
        "by `apps/reports/role_gate.py` (`P5.9`, `reports/0008_p5_9_min_role.py`), on the "
        "SERVER, at the catalogue and at the run. This read model deliberately adds no "
        "authorisation check of its own: it is the wrong layer, it would be the only one of "
        "its kind in this module, and a second check is how two answers to `who may see "
        "this` come to exist. Recorded here so the absence reads as a decision rather than "
        "an oversight."
    ),
    "wanted_reads": (),
}


@dataclass(frozen=True)
class AccessReviewRow:
    """One membership — one person who can sign in to THIS tenant.

    ⚠ **`last_active_at` IS NOT NAMED `last_sign_in_at`, ANYWHERE.** The field
    name is the honest one so a renderer cannot accidentally print the drawn
    header over it without noticing; `SIGN_IN_IS_LAST_ACTIVE` carries the
    substitution to the screen.

    ⚠ **`never_signed_in` IS A FACT AND NOT AN ABSENCE.** `last_active_at is
    None` is what the drawing's NEVER SIGNED IN tile counts, and it travels per
    row so the tile and the rows under it are struck over the same set.

    ⚠ **NO UUID IS A DRAWN COLUMN** (B14 rule 31). `membership_id` travels for
    drill-through only.
    """

    membership_id: str
    user_name: str | None
    user_email: str | None
    role_code: str | None
    role_name: str | None
    added_on: date | None
    added_by: str | None
    last_active_at: datetime | None
    never_signed_in: bool
    can_approve_money: bool
    status: str


def _tenant_id() -> Any:
    return current_tenant_id()


def _approving_role_codes() -> frozenset[str]:
    """The role codes whose A4 cell for adjustment approval reads `Approve`.

    Derived from the signed grid rather than typed, so a change to `A4_MATRIX`
    moves this report with it and the two cannot drift (hard-won law 1's shape:
    do not restate what a constant already says).
    """
    for code, _label, cells in A4_MATRIX:
        if code == APPROVAL_ROW:
            return frozenset(role for role, cell in cells.items() if str(cell) == APPROVAL_CELL)
    return frozenset()


def _base(
    *,
    as_of: date | None = None,
    role: str | None = None,
    status: str | None = None,
) -> Any:
    """The filtered set, as a QuerySet — every criterion a `WHERE`.

    Hard rule 1: `tenant_id=_tenant_id()`, with RLS FORCE underneath it. No
    cross-tenant queryset is constructible from here.

    ⚠ **A MEMBERSHIP WITH NO `invited_at` STAYS IN.** A platform-provisioned
    first administrator predates the invite flow and carries none; excluding it
    would silently shrink the staff list against a date that says nothing about
    it — the same posture `assets_dataset` takes for kit with no install date.
    """
    rows = TenantMembership.objects.filter(tenant_id=_tenant_id())
    if as_of is not None:
        rows = rows.filter(Q(invited_at__isnull=True) | Q(invited_at__date__lte=as_of))
    if role:
        rows = rows.filter(Q(role__code__iexact=role) | Q(role__name__iexact=role))
    if status:
        rows = rows.filter(status__iexact=status)
    return rows.select_related("user", "role", "invited_by")


def _shape(membership: Any, *, approving: frozenset[str]) -> AccessReviewRow:
    """One stored membership, in the report's declared column names. No query.

    `invited_by` is `select_related` on the base queryset, so the ADDED BY
    column costs nothing per row — the 40,000-round-trips trap `DEF-324` and
    `P2.21` both measured does not arise here, and it is avoided by structure
    rather than by the list being short.
    """
    user = membership.user
    role = membership.role
    added_by = getattr(membership.invited_by, "full_name", None) or getattr(
        membership.invited_by, "email", None
    )
    return AccessReviewRow(
        membership_id=str(membership.id),
        # B14 rule 31 — the name a person reads, never the uuid.
        user_name=(getattr(user, "full_name", None) or None),
        user_email=getattr(user, "email", None),
        role_code=getattr(role, "code", None),
        role_name=getattr(role, "name", None),
        added_on=membership.invited_at.date() if membership.invited_at else None,
        added_by=added_by,
        last_active_at=membership.last_active_at,
        never_signed_in=membership.last_active_at is None,
        # ⚠ THE SIGNED GRID, NEVER THE PERMISSION JOIN — see the docstring.
        can_approve_money=(getattr(role, "code", None) or "") in approving,
        status=membership.status,
    )


def access_review(
    *,
    as_of: date | None = None,
    role: str | None = None,
    status: str | None = None,
    page: int = 1,
    per: int | None = None,
    sort: str | None = None,
    direction: str = ACCESS_DEFAULT_DIRECTION,
) -> dict[str, Any]:
    """R36, ONE PAGE. One row per membership, paged and sorted in SQL.

    `per=None` is the whole filtered set. `per` is an integer page size; the
    CALLER clamps it and this function invents no cap (`NFR-5`).

    ⚠ **FOR AN EXPORT, CALL `access_review_stream()`** — no `page`, no `per`.

    **`totals` IS A SQL AGGREGATE OVER THE WHOLE FILTERED SET AND NEVER OVER THE
    PAGE**, so the four tiles foot to the report whether a page is cut or not.
    """
    rows = _base(as_of=as_of, role=role, status=status)
    approving = _approving_role_codes()

    # ⚠ ONE aggregate call, so every tile is struck over the same snapshot —
    # and `can_approve_money` is a `role__code__in` over the SIGNED grid's own
    # answer, which is the same rule `_shape` applies to each row. A tile and
    # the rows under it struck with two different rules is the footing failure
    # `apps/assets/assets_dataset._test_due_on` already records once.
    aggregated = rows.aggregate(
        users=Count("id"),
        active=Count("id", filter=Q(status=STATUS_ACTIVE)),
        invited=Count("id", filter=Q(status=STATUS_INVITED)),
        deactivated=Count("id", filter=Q(status=STATUS_DEACTIVATED)),
        never_signed_in=Count("id", filter=Q(last_active_at__isnull=True)),
        can_approve_money=Count("id", filter=Q(role__code__in=tuple(approving))),
    )
    total_users = int(aggregated["users"] or 0)

    # ⚠ **TWO OF THE FOUR GAPS ARE NOT PUBLISHED, AND THE OMISSION IS A
    # DECISION RATHER THAN AN OVERSIGHT.** `problems` reaches the SCREEN —
    # `ReportViewerPage` renders every entry through `ReportGapList` — and
    # B14 rule 33 puts RATIONALE at ZERO WORDS ON SCREEN while rule 32 forbids
    # an internal code in clerk-facing copy.
    #
    #   * `CAN_APPROVE_IS_THE_MATRIX_NOT_THE_JOIN` is pure engineering
    #     rationale: *why* the figure is read from the signed grid is of no use
    #     to a compliance officer reading the figure.
    #   * `WHERE_THE_RESTRICTION_LIVES` is engineering rationale too, and it
    #     was worse than that until `P5.9` landed: it said the restriction was
    #     NOT enforced, and printing that on the report tells whoever is
    #     reading it that the door is open. `P5.9` closed the hole; the
    #     constant is amended and still not published.
    #
    # Both remain module constants, both are asserted by
    # `tests/test_rep_p6_access_review.py`, and neither is deleted — a gap
    # dropped is a gap nobody can count.
    problems: list[dict[str, Any]] = [
        dict(SIGN_IN_IS_LAST_ACTIVE),
        dict(GAP_STATUS_IS_AS_IS_NOT_AS_WAS),
    ]

    # ── the page, cut in SQL ────────────────────────────────────────────────
    ordered = rows.order_by(
        *order_terms(sort, direction, columns=ACCESS_SORT_COLUMNS, default=ACCESS_DEFAULT_SORT)
    )
    served_page = max(1, int(page or 1))
    if per is None:
        window = ordered
        pages = 1
    else:
        size = max(1, int(per))
        pages = max(1, -(-total_users // size)) if total_users else 1
        served_page = min(served_page, pages)
        offset = (served_page - 1) * size
        window = ordered[offset : offset + size]

    shaped = tuple(_shape(membership, approving=approving) for membership in window)

    return {
        "basis": BASIS_DATE,
        "as_of": as_of,
        "grain": "one user of this tenant",
        "rows": shaped,
        "totals": {
            # ⚠ SEMI-ADDITIVE, every one. A headcount is a BALANCE as at a
            # date: staff in July plus staff in August is not staff over the
            # two months, it is most of the same people counted twice. Across
            # ROLE and STATUS they sum freely.
            "users": total_users,
            "active": int(aggregated["active"] or 0),
            "invited": int(aggregated["invited"] or 0),
            "deactivated": int(aggregated["deactivated"] or 0),
            "never_signed_in": int(aggregated["never_signed_in"] or 0),
            "can_approve_money": int(aggregated["can_approve_money"] or 0),
        },
        "additivity": {
            "users": "semi",
            "active": "semi",
            "invited": "semi",
            "deactivated": "semi",
            "never_signed_in": "semi",
            "can_approve_money": "semi",
        },
        "page": served_page,
        "per": per,
        "pages": pages,
        "total": total_users,
        "problems": tuple(problems),
    }


#: A fetch buffer, not a cap (`NFR-5`). The generator runs until the cursor is
#: exhausted and there is no number any row can be beyond.
STREAM_CHUNK = 2_000


def access_review_stream(
    *,
    as_of: date | None = None,
    role: str | None = None,
    status: str | None = None,
    sort: str | None = None,
    direction: str = ACCESS_DEFAULT_DIRECTION,
) -> Iterator[AccessReviewRow]:
    """EVERY row of the filtered set, streamed — **no `page`, no `per`.**

    The absence of those two parameters is the whole design: an export cannot
    inherit a screen's fifty rows because there is no argument through which to
    pass them. The order is applied IN SQL through the same `order_terms` the
    page uses, so the file and the screen sort identically.
    """
    approving = _approving_role_codes()
    rows = _base(as_of=as_of, role=role, status=status).order_by(
        *order_terms(sort, direction, columns=ACCESS_SORT_COLUMNS, default=ACCESS_DEFAULT_SORT)
    )
    for membership in rows.iterator(chunk_size=STREAM_CHUNK):
        yield _shape(membership, approving=approving)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P6.11 (R36 access_review; 12-governance/change-requests/CR-142-BRC07-reports-framework.md §9.2 · 05-prototype/09 Reports Build Brief.pdf p066 read as an image per B14 rule 42 · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-001/002/023/024)
# screens: S46
# generated: 2026-09-27 by lane REP-P6-JOIN
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — `tests/test_rep_p6_access_review.py` could not import this module before it existed, and `GET /reports/access_review` answered the audit dataset's named refusal. ruff✔ black✔ pytest✔ run_gates✔
# exceptions: (0) CAN APPROVE MONEY reads `A4_MATRIX` and NOT `role_permissions`, because the cell value (Approve vs Request) has no B2 column and the join would print Yes for a billing clerk · (1) LAST SIGN-IN is served as `last_active_at` and labelled `Last active`; `sessions` is ephemeral and would print `Never` for a real returning user (coordinator ruling 2026-09-27) · (2) `as_of` narrows MEMBERSHIP and not STATUS — there is no effective-dated status history and none is inferred · (3) BR-REP-023's restriction is REPORTED, not enforced here: it belongs at the endpoint (P5.9) · (4) this file writes nothing
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
