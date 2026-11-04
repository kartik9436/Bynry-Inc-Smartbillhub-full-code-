# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-020 (crews, technicians and their skills — a profile beside
#           an identity, never a second identity) · US-WRK-021 (the crews
#           screen, the technician detail, the skills wizard and the
#           certification watch).  Screens: Work-023 · Work-024
# Rules:    BR-WRK-028 (a technician is a profile beside `identity.User`; a
#           crew and a contractor are rows in the same table as a person) ·
#           BR-WRK-029 (dispatch offers only a skill match — the same test for
#           all three) · BR-WRK-030 (a lapsed certification is SHOWN; whether
#           it blocks or warns is the tenant's choice, ruled 2026-09-04) ·
#           BR-WRK-001/002 (Work owns these tables and writes nobody else's) ·
#           CLAUDE.md hard rule 1 (tenant-scoped; RLS FORCE in work/0007) ·
#           hard rule 7 (every write lands an audit row)
# Tests:    06-backend/tests/test_us_wrk_020_workforce.py ·
#           06-backend/tests/test_us_wrk_021_certification_watch.py
# Impacts:  apps/work/api.py (routes 50–60) · 07-frontend/src/features/work/
#           CrewsPage.tsx · TechnicianDetailPage.tsx
# ───────────────────────────────────────────────────────
"""The workforce — who works for this utility and what they can do.

READS AND WRITES IN ONE FILE, WHICH IS NOT THIS MODULE'S USUAL SHAPE
--------------------------------------------------------------------
`selectors.py` reads and `services.py` writes, everywhere else in `apps/work`.
This file holds both, for the reason `lookups.py` already holds both: the
workforce is one small subject with one set of invariants, and the read that
lists a technician's skills and the write that replaces them are two halves of
the same rule about what a skill row may be. Splitting them would put
`BR-WRK-028` in two files and let the halves disagree.

⚠ **THE UTILISATION FIGURE IS COMPUTED AND NEVER STORED** (`US-WRK-020`
TC-7). `WS-23` shows *82%* beside D. Ortiz; it is booked estimate over shift
length. A stored percentage is a number that is wrong every time a job moves
and right only when something remembers to recompute it.

⚠ **AND THE COUNT IN THE FOOTER IS THE ROWS, NOT THE PEOPLE.** *6 rows · 4
people, 1 crew, 1 contractor* — the sentence exists because a table that mixes
people with crews cannot let a reader assume a row is a person.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.work import models as work_models
from apps.work.seams import identity_seam, tenancy_seam
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.pagination import clamp_page_size

#: `WS-23`'s watch has two windows and they are inclusive of the day named.
WATCH_WINDOWS = (30, 60)

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 200


# ══════════════════════════════════════════════════════════════════════════
# READS
# ══════════════════════════════════════════════════════════════════════════


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _minutes(start, end) -> int | None:
    """Shift length in minutes, or None when there is no shift at all.

    A contractor works *by arrangement* — `WS-23`'s own words — so it has no
    shift, and the utilisation cell renders a dash. Dividing by a shift that
    does not exist is how a screen ends up showing `∞%`.
    """
    if start is None or end is None:
        return None
    minutes = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
    if minutes <= 0:  # a night shift crossing midnight
        minutes += 24 * 60
    return minutes or None


def _shift_text(start, end) -> str | None:
    """*07:00–16:00*, or None. The en dash is `WS-23`'s."""
    if start is None or end is None:
        return None
    return f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}"


def _skill_rows(holder_skills) -> list[dict[str, Any]]:
    return [
        {
            "skill_id": str(row.skill_id),
            "code": row.skill.code,
            "name": row.skill.name,
            "proficiency": row.proficiency,
        }
        for row in holder_skills
    ]


def _certification_rows(
    rows, types_by_id: dict[str, dict[str, Any]], slug: str | None = None
) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        kind = types_by_id.get(str(row.certification_type_id))
        entry = {
            "certification_type_id": str(row.certification_type_id),
            # A type the tenant has since deactivated still has a name in
            # the seam's answer; one that is genuinely gone reads as None
            # and the screen renders a dash rather than a raw uuid — B14
            # rule 31, no database id is ever a visible value.
            "name": (kind or {}).get("name"),
            "expires_on": row.expires_on.isoformat() if row.expires_on else None,
        }
        if slug is not None:
            # Image 33's PROOF — the certificate's own scan, or None (a dash).
            # Served on the technician's page only; the lists do not draw it.
            from apps.work import certificate_proof

            entry["proof"] = certificate_proof.proof_of(row, slug)
        out.append(entry)
    return out


#: ⚠ **`UNSERVED_UNTIL_WAVE_G` IS RETIRED (`CR-168-BRC10` P3.46, lane SRV-3).**
#: It declared TODAY, UTILISATION and the *THIS MONTH* figures unservable
#: because `work_orders` had no assignee column. Wave G landed that column on
#: 2026-09-05 (`assignee_technician`), and the hold stayed a month past the day
#: its reason ended — hard-won law 2's mirror, a refusal nobody re-checked.
#: `technician_detail` now serves `today` and `this_month` from the jobs a
#: person HOLDS; `technician_performance` serves the by-job-type table.
#: UTILISATION is still not served: it is booked estimate over shift length and
#: no image of the redesign (25–34) draws it.

#: The three lists of `Work-023` — PO ruling 30 (24 Sep), *"one table is
#: confusing"*: Technicians · Crews · Contractors, each its own table with its
#: own count (`BR-WRK-028`'s last sentence SUPERSEDED).
VIEW_TECHNICIANS = "technicians"
VIEW_CREWS = "crews"
VIEW_CONTRACTORS = "contractors"
VIEWS = (VIEW_TECHNICIANS, VIEW_CREWS, VIEW_CONTRACTORS)

#: The sorts each list declares. `name` on all three; a technician may also be
#: sorted by crew, a crew by its member count.
CREW_SORTS = ("name", "crew", "members")


def _member_counts() -> Any:
    """`members` — how many technicians name this crew, COUNTED IN SQL.

    ⚠ **THE TYPED `headcount` IS NO LONGER READ FOR DISPLAY** (P3.44: *"a
    crew's headcount becomes a count of its members rather than a number typed
    in"*). A typed figure is wrong the moment somebody moves; a count of the
    rows that say so cannot be. The column stays a lawful container.
    """
    from django.db.models import Count, IntegerField, OuterRef, Subquery
    from django.db.models.functions import Coalesce

    counted = (
        work_models.Technician.objects.filter(crew_id=OuterRef("pk"))
        .order_by()
        .values("crew_id")
        .annotate(n=Count("id"))
        .values("n")
    )
    return Coalesce(Subquery(counted, output_field=IntegerField()), 0)


def _technicians_queryset(term: str) -> Any:
    from django.db.models import TextField, Value
    from django.db.models.functions import Cast, Coalesce, Lower, NullIf

    qs = work_models.Technician.objects.filter(tenant_id=_tenant_id()).annotate(
        sort_name=Lower(
            Coalesce(
                NullIf("user__full_name", Value("")),
                Cast("user__email", TextField()),
                output_field=TextField(),
            )
        )
    )
    if len(term) >= 2:
        matched = work_models.Technician.objects.filter(
            Q(user__full_name__icontains=term)
            | Q(user__email__icontains=term)
            | Q(skills__skill__name__icontains=term)
            | Q(crew__name__icontains=term)
        ).values("id")
        # A subquery rather than `.distinct()` on the joined rows: the page is
        # cut by ORDER BY + LIMIT on the outer query, and DISTINCT over a join
        # to skills would have to sort by every selected column first.
        qs = qs.filter(id__in=matched)
    return qs


def _crews_queryset(term: str, kinds: tuple[str, ...]) -> Any:
    from django.db.models import Case, IntegerField, Value, When
    from django.db.models.functions import Lower

    qs = work_models.Crew.objects.filter(tenant_id=_tenant_id(), kind__in=kinds).annotate(
        members=_member_counts(),
        sort_name=Lower("name"),
        kind_rank=Case(
            When(kind=work_models.Crew.KIND_CREW, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        ),
    )
    if len(term) >= 2:
        matched = work_models.Crew.objects.filter(
            Q(name__icontains=term) | Q(skills__skill__name__icontains=term)
        ).values("id")
        qs = qs.filter(id__in=matched)
    return qs


def _ordering(view: str | None, sort: str | None, direction: str | None) -> list[Any]:
    """ORDER BY for one list — every term ends in `id` so a page boundary is
    stable when two rows share a name (NFR-3: a row is on exactly one page)."""
    from django.db.models import F

    desc = (direction or "asc").lower() == "desc"

    def term(field: str) -> Any:
        return F(field).desc(nulls_last=True) if desc else F(field).asc(nulls_last=True)

    if view == VIEW_TECHNICIANS and sort == "crew":
        return [term("crew__name"), term("sort_name"), "id"]
    if view in (VIEW_CREWS, VIEW_CONTRACTORS) and sort == "members":
        return [term("members"), term("sort_name"), "id"]
    if view is None:
        # The one-table legacy shape (one round, see `crews_page`): people
        # first, then crews, then contractors, each by name.
        return [term("sort_name"), "id"]
    return [term("sort_name"), "id"]


def _since(row: Any) -> str | None:
    """FB-033 — `technicians.status_since` as the utility's wall clock."""
    since = getattr(row, "status_since", None)
    if since is None:
        return None
    from apps.work.seams import tenancy_seam

    return since.astimezone(tenancy_seam.tenant_timezone()).isoformat()


def _shift_ended(row: Any) -> bool:
    if row.status != work_models.Technician.STATUS_OFF_TODAY:
        return False
    from apps.work.shift_models import TechnicianShiftEnd

    return TechnicianShiftEnd.objects.filter(
        tenant_id=_tenant_id(), technician_id=row.id, settled_at__isnull=True
    ).exists()


def _mark_shift_ended(rows: list[dict[str, Any]]) -> None:
    """FB-033 (D4 = B) — `shift_ended` on each person row: *off today* because
    End shift was pressed and still holds (an unsettled `TechnicianShiftEnd`),
    not because the office set it by hand. Crews then reads *Shift ended ·
    17:02* rather than *Off today*. ONE query for the page."""
    from apps.work.shift_models import TechnicianShiftEnd

    off = [r["id"] for r in rows if r.get("status") == work_models.Technician.STATUS_OFF_TODAY]
    ended = {
        str(t)
        for t in TechnicianShiftEnd.objects.filter(
            tenant_id=_tenant_id(), technician_id__in=off, settled_at__isnull=True
        ).values_list("technician_id", flat=True)
    } if off else set()
    for row in rows:
        if row.get("kind", "person") == "person" and "status_since" in row:
            row["shift_ended"] = row["id"] in ended


def _technician_list_row(row: Any, types_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "kind": "person",
        # B14 rule 31 — the NAME is the visible value. `slug` is what a link is
        # built from and is derived from the name, never the id.
        "name": row.user.full_name or row.user.email,
        "slug": technician_slug(row),
        "role_label": row.role_label or None,
        # Image 25's CREW column — a technician's crew, by name; the id is the
        # link target only.
        "crew": {"id": str(row.crew_id), "name": row.crew.name} if row.crew_id else None,
        "skills": _skill_rows(row.skills.all()),
        "certifications": _certification_rows(row.certifications.all(), types_by_id),
        "shift": _shift_text(row.shift_start, row.shift_end),
        "status": row.status,
        # FB-033 — WHEN the status took its value, in the utility's zone
        # (*Off duty · since 15:30*); null = not known (set before 0062).
        "status_since": _since(row),
        "unavailable_reason": row.unavailable_reason or None,
        "phone": None,
        "email": row.user.email or None,
    }


def _crew_list_row(row: Any, *, legacy_name: bool) -> dict[str, Any]:
    contractor = row.kind == work_models.Crew.KIND_CONTRACTOR
    members = int(getattr(row, "members", 0) or 0)
    return {
        "id": str(row.id),
        "kind": row.kind,
        # ⚠ The legacy one-table screen (no `view`) composed *Crew B (3)* into
        # the name; the three lists draw MEMBERS as its own column (image 27),
        # so a `view` answers the plain name. One round only, as SRV-2 did for
        # its twin keys: lane CREWS moves to `view` and the bracket goes.
        "name": f"{row.name} ({members})" if legacy_name and members else row.name,
        "slug": crew_slug(row),
        "role_label": row.role_label or None,
        # Image 27's MEMBERS — counted, never typed (P3.44).
        "members": members,
        # Image 27 draws *D. Ortiz · R. Patel · 2 people* — the NAMES as well as
        # the count (the server gap lane CREWS reported, CR §19; lane SRV-4).
        # From the page's prefetch only, by name; a contractor has none (ruling
        # 36: its people wait for the field-app document).
        "member_names": [
            tech.user.full_name or tech.user.email
            for tech in getattr(row, "member_rows", None) or []
        ],
        "crew": None,
        "skills": _skill_rows(row.skills.all()),
        "certifications": [],
        "shift": _shift_text(row.shift_start, row.shift_end),
        "status": "contractor" if contractor else "crew",
        "unavailable_reason": None,
        # P3.53 — how the office reaches the FIRM; only a contractor has them.
        "phone": (row.phone or None) if contractor else None,
        "email": (row.email or None) if contractor else None,
        "active": row.active,
    }


def _members_prefetch() -> Any:
    """A crew's members, by name, for the PAGE's crews only."""
    from django.db.models import Prefetch

    return Prefetch(
        "technician_set",
        queryset=work_models.Technician.objects.select_related("user").order_by(
            "user__full_name", "user__email", "id"
        ),
        to_attr="member_rows",
    )


def crews_page(
    *,
    q: str | None = None,
    page: Any = 1,
    per: Any = None,
    view: str | None = None,
    sort: str | None = None,
    direction: str | None = None,
) -> dict[str, Any]:
    """`GET /work/crews?view=technicians|crews|contractors` — `Work-023` as
    THREE LISTS (ruling 30), **each cut in SQL** (`CR-168-BRC10` P3.4, NFR-3).

    ⚠ **THIS BUILT EVERY ROW, SORTED AND SLICED IN PYTHON UNTIL 2026-10-04**,
    and a candidate list took one page of it as *everybody* (`DEF-WRK-9531`,
    SRV-2). Now each view is one queryset with `ORDER BY … LIMIT/OFFSET`;
    skills and certifications are prefetched for THE PAGE only. No list has a
    maximum (NFR-5): a utility of 40,000 accounts with 400 technicians pages
    like one with four.

    `counts {technicians, crews, contractors}` are three `COUNT(*)`s over the
    searched set — the three tab badges of image 25.

    ⚠ **NO `view` STILL ANSWERS THE ONE TABLE, FOR ONE ROUND**: people first,
    then crews, then contractors, each by name — the screen at the tip reads
    it. It is paged in SQL too: the page is cut across the two querysets by
    their counts (rows `[start, end)` of people, then of crew rows), so no row
    list is ever built whole. Lane CREWS moves to `view`; the next Work server
    lane retires the no-`view` answer and the legacy `counts` keys.
    """
    if view is not None and view not in VIEWS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP, message_key="work.crews.view_unknown", params={"view": view}
        )
    term = (q or "").strip()
    types_by_id = {row["id"]: row for row in tenancy_seam.certification_types()}
    technicians = _technicians_queryset(term)
    crews = _crews_queryset(term, (work_models.Crew.KIND_CREW,))
    contractors = _crews_queryset(term, (work_models.Crew.KIND_CONTRACTOR,))
    # ⚠ THE THREE BADGES COUNT THE UTILITY, NOT THE SEARCH (the gap lane
    # CREWS reported, CR §19; lane SRV-4): while searching *Sam* the badges read
    # *Technicians 5 · Crews 0*, which told a supervisor the utility had no
    # crews. The page's `count` is the searched list's; the badges are not.
    counts = {
        "technicians": _technicians_queryset("").count(),
        "crews": _crews_queryset("", (work_models.Crew.KIND_CREW,)).count(),
        "contractors": _crews_queryset("", (work_models.Crew.KIND_CONTRACTOR,)).count(),
    }
    searched = {
        "technicians": technicians.count(),
        "crews": crews.count(),
        "contractors": contractors.count(),
    }
    size = clamp_page_size(per)

    def cut(qs: Any, total: int) -> tuple[int, int, int]:
        last = max(1, math.ceil(total / size))
        number = max(1, min(int(page or 1), last))
        return number, (number - 1) * size, total

    tech_joins = ("user", "crew")
    tech_prefetch = ("skills__skill", "certifications")
    if view == VIEW_TECHNICIANS:
        number, start, total = cut(technicians, searched["technicians"])
        page_qs = technicians.select_related(*tech_joins).prefetch_related(*tech_prefetch)
        page_qs = page_qs.order_by(*_ordering(view, sort, direction))[start : start + size]
        rows = [_technician_list_row(row, types_by_id) for row in page_qs]
    elif view in (VIEW_CREWS, VIEW_CONTRACTORS):
        source = crews if view == VIEW_CREWS else contractors
        number, start, total = cut(source, searched[view])
        page_qs = source.prefetch_related("skills__skill", _members_prefetch()).order_by(
            *_ordering(view, sort, direction)
        )[start : start + size]
        rows = [_crew_list_row(row, legacy_name=False) for row in page_qs]
    else:
        everyone = _crews_queryset(
            term, (work_models.Crew.KIND_CREW, work_models.Crew.KIND_CONTRACTOR)
        )
        people = searched["technicians"]
        number, start, total = cut(None, people + searched["crews"] + searched["contractors"])
        end = start + size
        rows = []
        if start < people:
            page_qs = technicians.select_related(*tech_joins).prefetch_related(*tech_prefetch)
            page_qs = page_qs.order_by("sort_name", "id")[start : min(end, people)]
            rows.extend(_technician_list_row(row, types_by_id) for row in page_qs)
        if end > people:
            page_qs = everyone.prefetch_related("skills__skill").order_by(
                "kind_rank", "sort_name", "id"
            )[max(0, start - people) : end - people]
            rows.extend(_crew_list_row(row, legacy_name=True) for row in page_qs)
    _mark_shift_ended(rows)
    return {
        "rows": rows,
        "page": number,
        "per": size,
        "total": total,
        "counts": {
            **counts,
            # ⚠ ONE ROUND ONLY — the one-table footer's keys (*6 rows · 4
            # people, 1 crew, 1 contractor*) that the screen at the tip reads.
            "rows": counts["technicians"] + counts["crews"] + counts["contractors"],
            "people": counts["technicians"],
        },
    }


def staff_page(*, q: str | None = None, page: Any = 1, per: Any = None) -> dict[str, Any]:
    """`GET /work/technicians?q=&page=&per=` — the add-member picker (image 26),
    PAGED IN SQL (NFR-3) and uncapped (NFR-5), each login with the CREW it is
    on now (*on Field crew A* — the gap lane CREWS reported, CR §19; lane
    SRV-4) so the form can say who would move.

    `q` matches the name and the email. The crew is read for the page's logins
    only, through Work's own table.
    """
    size = clamp_page_size(per)
    qs = identity_seam.staff_users_queryset(q)
    total = qs.count()
    last = max(1, math.ceil(total / size))
    try:
        number = max(1, min(int(page or 1), last))
    except (TypeError, ValueError):
        number = 1
    start = (number - 1) * size
    chunk = list(qs[start : start + size])
    user_ids = [m.user_id for m in chunk]
    profiles = {
        str(t.user_id): t
        for t in work_models.Technician.objects.filter(
            tenant_id=_tenant_id(), user_id__in=user_ids
        ).select_related("crew")
    }
    rows = []
    for membership in chunk:
        profile = profiles.get(str(membership.user_id))
        rows.append(
            {
                "user_id": str(membership.user_id),
                "full_name": membership.user.full_name or None,
                "email": membership.user.email,
                "role_code": membership.role.code,
                "status": membership.status,
                "has_profile": profile is not None,
                "technician_id": str(profile.id) if profile is not None else None,
                "crew": (
                    {"id": str(profile.crew_id), "name": profile.crew.name}
                    if profile is not None and profile.crew_id
                    else None
                ),
            }
        )
    return {"rows": rows, "page": number, "per": size, "total": total}


def staff_choices() -> list[dict[str, Any]]:
    """Every login this utility could make a technician of, with the ones that
    already are marked (`Work-023`'s *add a technician* picker).

    ⚠ **THE PICKER IS `BR-WRK-028` MADE UNAVOIDABLE.** A technician is a
    profile beside an existing login; offering the logins that exist is how a
    supervisor is stopped from typing an email that has none, rather than being
    told off afterwards. `create_technician` still refuses — a picker is
    convenience and the server is the enforcement (`BR-SHL-025`).
    """
    taken = {
        str(user_id)
        for user_id in work_models.Technician.objects.filter(
            tenant_id=_tenant_id()
        ).values_list("user_id", flat=True)
    }
    return [
        {**row, "has_profile": row["user_id"] in taken}
        for row in identity_seam.staff_user_choices()
    ]


def crew_directory() -> list[dict[str, Any]]:
    """`BR-AST-533` — WHO WORKS HERE, AS A NAME AND AN EMAIL AND NOTHING ELSE.

    PO ruling 2026-09-12, verbatim: ***"a) Let a clerk read the crew list (name
    + email only)"***. It answers a collision between two signed rules that
    neither could yield on: `BR-AST-038` writes the Log-repair screen FOR a
    Billing Clerk, while `GET /users` is `SystemAdminOnly` — so the one role
    that screen exists for was handed a text box and told to type a uuid, which
    is B14 rule 31 (*"no Databse ID on screen - that is a rule"*) broken for
    precisely that role.

    ⚠ **`GET /users` IS NOT WIDENED AND MUST NOT BE.** Measured on 2026-09-12
    with a real Billing Clerk session on `pine-hill`: `GET /users` answers
    **403 `BR-IDN-009`** and this route answers **200**. That is the ruling's
    whole shape — a NEW narrow read beside the admin one, never a relaxed
    admin one.

    ⚠ **AND IT IS NOT `GET /work/technicians`, WHICH A CLERK COULD ALREADY
    READ.** That route serves the supervisor's *add a technician* picker and
    carries `role_code`, `status` and `has_profile` beside the name — measured,
    7 rows, same session, same tenant. Those three are exactly what the ruling
    names as not-served (*"no role, no permissions, no account"*), and they
    cannot simply be dropped from it because `Work-023` marks who already has a
    profile. **So the two reads have different contracts over one population**,
    and this is the narrow one. A front-end projection would NOT have done:
    `role_code` would still have crossed the wire into the clerk's browser, and
    "role-safe" is a statement about what LEAVES the server.

    **The id is served and is never shown.** `BR-AST-533`: *"The id still
    travels on the wire as the chosen value; what the rule forbids is a person
    reading or typing it."* It is the picker's `value`; the label is the name.

    Deactivated logins are left out — `staff_user_choices` already decides that
    and the reason holds here too: a person who cannot sign in cannot be sent to
    a job. One source for *who works here*, two projections of it.
    """
    return [
        {
            "id": row["user_id"],
            "name": row["full_name"] or row["email"],
            "email": row["email"],
        }
        for row in identity_seam.staff_user_choices()
    ]


def technician_slug(row: work_models.Technician) -> str:
    """`r-patel` — the address `WS-24` draws, built from the NAME.

    B14 rule 31: no database id is the visible value of anything, and a URL is
    the most visible value a screen has. A person with no name yet falls back
    to the local part of their email, because an invited login has no name and
    a blank address is not an address.
    """
    source = row.user.full_name or (row.user.email or "").split("@")[0]
    return _slugify(source)


def crew_slug(row: work_models.Crew) -> str:
    return _slugify(row.name)


def _slugify(value: str) -> str:
    """*R. Patel* → `r-patel`; *Apex Utility Svc* → `apex-utility-svc`."""
    out = []
    for char in (value or "").lower():
        if char.isalnum():
            out.append(char)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-") or "unnamed"


def technician_by_slug(slug: str) -> dict[str, Any] | None:
    """`Work-024` — one technician, or None.

    ⚠ A CROSS-TENANT SLUG ANSWERS None AND THEREFORE 404, IDENTICAL TO ONE THAT
    DOES NOT EXIST (`US-WRK-021` TC-6, CLAUDE.md hard rule 1). The slug is
    computed per tenant, so `/work/crews/r-patel` on the other utility finds
    nothing rather than finding somebody else's technician.
    """
    tenant_id = _tenant_id()
    for row in (
        work_models.Technician.objects.filter(tenant_id=tenant_id)
        .select_related("user", "crew")
        .prefetch_related("skills__skill", "certifications")
    ):
        if technician_slug(row) == slug:
            return technician_detail(row)
    return None


def technician_detail(row: work_models.Technician) -> dict[str, Any]:
    """`Work-024`'s Overview — skills with what each makes them eligible for,
    certifications with their expiry, and the month's figures.

    ⚠ **THE *Not held* ROWS ARE DERIVED HERE AND STORED NOWHERE.** `WS-24`
    draws *Water II · Not held · Main repair · tap and service line*, and the
    card's own reason is the deliverable: *"The Not held row matters as much as
    the two held ones: it tells a supervisor exactly which jobs a training
    course would unlock."* It is the tenant's skill catalogue minus the rows
    this person holds — so a skill added in Settings appears here the same day,
    which a stored row could never do.
    """
    types_by_id = {kind["id"]: kind for kind in tenancy_seam.certification_types()}
    held = {str(skill.skill_id): skill for skill in row.skills.all()}
    eligible = _templates_by_skill()

    skills: list[dict[str, Any]] = []
    for skill in work_models.WorkSkill.objects.filter(
        tenant_id=row.tenant_id, active=True
    ).order_by("name"):
        holder = held.get(str(skill.id))
        skills.append(
            {
                "skill_id": str(skill.id),
                "code": skill.code,
                "name": skill.name,
                # `not_held` is a RENDERED value and not a stored proficiency —
                # `TechnicianSkill` has no such member, deliberately.
                "proficiency": holder.proficiency if holder else "not_held",
                "eligible_for": eligible.get(str(skill.id), []),
            }
        )

    return {
        "id": str(row.id),
        "slug": technician_slug(row),
        "name": row.user.full_name or row.user.email,
        "role_label": row.role_label or None,
        "shift": _shift_text(row.shift_start, row.shift_end),
        "status": row.status,
        "status_since": _since(row),
        # FB-033 (D4 = B) — off today because End shift still holds it.
        "shift_ended": _shift_ended(row),
        "unavailable_reason": row.unavailable_reason or None,
        "van": row.van or None,
        # `CR-168-BRC10` §30 (`work/0038`) — jobs a day this person is expected
        # to carry; advice the Schedule board reads, never a cap.
        "daily_job_limit": row.daily_job_limit,
        # `CR-168-BRC10` §7.3 — the crew as `{id, name}` (image 31's *Field
        # crew A*, a link), where it was a bare name until 2026-10-04.
        "crew": {"id": str(row.crew_id), "name": row.crew.name} if row.crew_id else None,
        "skills": skills,
        "certifications": _certification_rows(
            row.certifications.all(), types_by_id, technician_slug(row)
        ),
        # P3.46 — `today {jobs}` and `this_month {closed, on_time, on_time_of,
        # first_visit_pct, vs_estimate_pct, vs_estimate_minutes}`, counted from
        # the jobs this person HOLDS (`technician_figures`).
        **_figures(row.id),
    }


def _figures(technician_id: Any) -> dict[str, Any]:
    from apps.work import technician_figures

    return technician_figures.figures(technician_id)


def _templates_by_skill() -> dict[str, list[str]]:
    """Which published templates each skill makes a person eligible for.

    `WS-24`'s MAKES THEM ELIGIBLE FOR column, read from the utility's own
    templates through the metering seam rather than from a list typed into a
    screen — so a template published this morning appears against the skill
    this afternoon, and a utility that has never published one sees an honest
    blank instead of somebody else's examples.
    """
    from apps.work.seams import metering_seam

    out: dict[str, list[str]] = {}
    for template in metering_seam.templates_queryset().filter(active=True):
        if template.skill_id:
            out.setdefault(str(template.skill_id), []).append(template.name)
    for names in out.values():
        names.sort()
    return out


def certification_watch(*, today: date | None = None) -> dict[str, Any]:
    """`GET /work/certification-watch` — `Work-023`'s box.

    ⚠ **`OQ-WRK-1493` WAS RULED ON 2026-09-04 AND BOTH SIDES ARE BUILT.** The
    PO chose option (c): a per-tenant setting, defaulting to **warn**. So this
    always returns the expiries and their dates, and `blocks` says whether this
    utility's setting turns them into a refusal. `blocked_template_types` is
    the count `WS-23` draws — the published templates whose skill or safety kit
    NAMES the certification — and it is served either way, because the count is
    a fact about the templates and not about the policy.

    ⚠ **THE SENTENCE *She is blocked from 4 template types until renewed* IS
    RENDERED ONLY WHERE BLOCKING IS ON.** A screen may not claim a guarantee
    the setting has switched off — that is hard-won law 1 in one line, and it
    is why `policy` travels with the rows instead of the browser assuming.
    """
    tenant_id = _tenant_id()
    today = today or date.today()
    types_by_id = {row["id"]: row for row in tenancy_seam.certification_types()}
    policy = lapse_policy()
    naming = _template_types_naming_certifications()

    windows: dict[int, list[dict[str, Any]]] = {days: [] for days in WATCH_WINDOWS}
    for row in (
        work_models.TechnicianCertification.objects.filter(tenant_id=tenant_id)
        .exclude(expires_on=None)
        .select_related("technician__user")
        .order_by("expires_on")
    ):
        days_left = (row.expires_on - today).days
        for days in WATCH_WINDOWS:
            # A certification that has ALREADY lapsed belongs in the nearest
            # window, not in none of them: `days_left` goes negative on 21
            # August and J. Kaur must not vanish from the watch on the one day
            # a supervisor most needs to see her.
            if days_left <= days:
                kind = types_by_id.get(str(row.certification_type_id))
                windows[days].append(
                    {
                        "technician": (
                            row.technician.user.full_name or row.technician.user.email
                        ),
                        "technician_slug": technician_slug(row.technician),
                        "certification": (kind or {}).get("name"),
                        "expires_on": row.expires_on.isoformat(),
                        "expired": days_left < 0,
                        "blocked_template_types": naming.get(
                            str(row.certification_type_id), 0
                        ),
                    }
                )
                break

    return {
        "today": today.isoformat(),
        "policy": policy,
        "blocks": policy == work_models.WorkSettings.LAPSE_BLOCK,
        "windows": [
            {"days": days, "entries": windows[days]}
            for days in WATCH_WINDOWS
            if windows[days]
        ],
    }


def _template_types_naming_certifications() -> dict[str, int]:
    """How many published template types NAME each certification.

    ⚠ **IT COUNTS SAFETY KITS, WHICH IS THE ONLY PLACE A TEMPLATE CAN NAME A
    CERTIFICATION TODAY.** `work_safety_kits.items` is a list of strings —
    *Harness · Gas monitor · Confined space* — and the match is on the
    certification's NAME appearing in that list. A `certification_type_id`
    column on the kit would be the exact shape, and it does not exist; adding
    one is a Settings change that belongs to whoever owns that card, and is
    written down rather than invented here.

    A name-match is honest about what it is: it can miss a kit that spells the
    certification differently, and the count it produces is the count the watch
    shows. It is never used to REFUSE anything on its own — the refusal, where
    a tenant has switched blocking on, is decided by `skill_match` below.
    """
    counts: dict[str, int] = {}
    kits = list(
        work_models.WorkSafetyKit.objects.filter(tenant_id=_tenant_id(), active=True)
    )
    for kind in tenancy_seam.certification_types():
        name = (kind.get("name") or "").strip().lower()
        if not name:
            continue
        counts[kind["id"]] = sum(
            1
            for kit in kits
            if any(name == str(item).strip().lower() for item in (kit.items or []))
        )
    return counts


def lapse_policy() -> str:
    """This tenant's answer to `OQ-WRK-1493` — `warn` (the default) or `block`.

    A tenant with no `work_settings` row reads the seeded default, exactly as
    `security_policies` serves a tenant that has never opened the tab. That is
    what makes the ruling's *"a new tenant starts at warn"* true without a
    backfill.

    ⚠ **ALWAYS `warn` SINCE 2026-10-04** — PO answer 2, *"(a) Warn only, the
    same as skills"*, SUPERSEDES `BR-WRK-030` for every tenant. A row written
    `block` before the ruling is a lawful container read by nothing: this
    answers `warn` whatever it holds, so the watch and the advice never revive
    a block the PO retired (`CR-168-BRC10` P4.5).
    """
    return work_models.WorkSettings.LAPSE_WARN


# ── The skill match — `BR-WRK-029`, published for wave G ──────────────────


def skill_match(*, skill_id: Any, on: date | None = None) -> dict[str, Any]:
    """Who may be offered a job needing this skill — the ONE test for a person,
    a crew and a contractor (`BR-WRK-029`).

    ⚠ **PUBLISHED HERE AND CALLED BY WAVE G**, which is where the assign
    picker lives. It is written now because `US-WRK-020` TC-4 asserts it (offer
    a meter exchange to R. Patel, who holds Water I and Reads, and he is not
    offered) and because a predicate two waves write twice is a predicate that
    disagrees with itself.

    ⚠ **AND THE CERTIFICATION RULING IS APPLIED HERE, NOT IN THE PICKER.**
    Where the tenant's policy is `block`, a candidate whose certification has
    lapsed is returned with `eligible: False` and the reason; where it is
    `warn` — the default — they are returned eligible with the same expiry
    attached, and the dispatcher decides. Both sides come out of one function
    so the two utilities are looking at the same arithmetic with one switch
    flipped.
    """
    tenant_id = _tenant_id()
    on = on or date.today()
    blocking = lapse_policy() == work_models.WorkSettings.LAPSE_BLOCK
    types_by_id = {row["id"]: row for row in tenancy_seam.certification_types()}

    candidates: list[dict[str, Any]] = []
    for row in (
        work_models.Technician.objects.filter(tenant_id=tenant_id, skills__skill_id=skill_id)
        .select_related("user")
        .prefetch_related("certifications")
        .distinct()
    ):
        lapsed = [
            {
                "certification": (types_by_id.get(str(cert.certification_type_id)) or {}).get(
                    "name"
                ),
                "expires_on": cert.expires_on.isoformat(),
            }
            for cert in row.certifications.all()
            if cert.expires_on is not None and cert.expires_on < on
        ]
        candidates.append(
            {
                "kind": "person",
                "id": str(row.id),
                "name": row.user.full_name or row.user.email,
                "lapsed": lapsed,
                "eligible": not (blocking and lapsed),
            }
        )
    for row in work_models.Crew.objects.filter(
        tenant_id=tenant_id, skills__skill_id=skill_id
    ).distinct():
        candidates.append(
            {
                "kind": row.kind,
                "id": str(row.id),
                "name": row.name,
                # A crew holds no certifications today — `technician_
                # certifications` is per person, which is what a certification
                # is. A crew whose members are certified is a shape nothing has
                # specified, and inventing it would be a rule.
                "lapsed": [],
                "eligible": True,
            }
        )
    candidates.sort(key=lambda row: row["name"].lower())
    return {"policy": "block" if blocking else "warn", "candidates": candidates}


# ══════════════════════════════════════════════════════════════════════════
# WRITES
# ══════════════════════════════════════════════════════════════════════════


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _require(payload: dict[str, Any], field: str) -> Any:
    value = payload.get(field)
    if value in (None, ""):
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.field_required", params={"field": field}
        )
    return value


def _time_or_none(value: Any, field: str):
    """`"07:00"` → a time, `None`/`""` → None, anything else → a refusal."""
    if value in (None, ""):
        return None
    from datetime import time as time_cls

    if isinstance(value, time_cls):
        return value
    try:
        hours, _, minutes = str(value).partition(":")
        return time_cls(int(hours), int(minutes or 0))
    except (TypeError, ValueError) as exc:
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="work.time_format", params={"field": field}
        ) from exc


def create_crew(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Add a crew or a contractor (`US-WRK-020` TC-3).

    Both land in the same table with a `kind`, because `BR-WRK-028` says so and
    because the skill test that offers them work must not be able to tell them
    apart.
    """
    payload = dict(payload or {})
    kind = payload.get("kind") or work_models.Crew.KIND_CREW
    if kind not in work_models.Crew.KINDS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP, message_key="work.crew_kind_unknown", params={"kind": kind}
        )
    phone, email = _contact(payload, kind)
    # ⚠ ONE WRITE FOR THE WHOLE FORM (image 29, *+ Add a crew*: Name, Does,
    # Members, Skills, Shift — the gap lane CREWS reported, CR §19; lane
    # SRV-4). `skills` and `members` are optional and travel in the SAME
    # transaction as the crew: a crew that saved while its members did not
    # would sit on the list as *0 people* with nobody knowing why. Anyone on
    # another crew MOVES (the form's EFFECT names them), audited per person.
    skills = _clean_skill_list({"skills": payload["skills"]}, _tenant_id()) if payload.get(
        "skills"
    ) else []
    members = list(payload.get("members") or [])
    if members and kind != work_models.Crew.KIND_CREW:
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="work.crew.members_crew_only", params={}
        )
    moved: list[dict[str, Any]] = []
    with transaction.atomic():
        row = work_models.Crew.objects.create(
            tenant_id=_tenant_id(),
            name=_require(payload, "name"),
            kind=kind,
            headcount=payload.get("headcount") or None,
            role_label=payload.get("role_label") or "",
            shift_start=_time_or_none(payload.get("shift_start"), "shift_start"),
            shift_end=_time_or_none(payload.get("shift_end"), "shift_end"),
            phone=phone,
            email=email,
        )
        core_audit.write_row(
            action="work.crew.created",
            entity_type="crew",
            entity_id=row.id,
            actor_user_id=_actor_id(actor),
            after={
                "name": row.name, "kind": row.kind, "headcount": row.headcount,
                "phone": row.phone, "email": row.email,
                "skills": sorted(f"{sid}:{prof}" for sid, prof in skills),
                "members": len(members),
            },
        )
        if skills:
            work_models.CrewSkill.objects.bulk_create(
                [
                    work_models.CrewSkill(
                        tenant_id=row.tenant_id, crew_id=row.id, skill_id=skill_id,
                        proficiency=proficiency,
                    )
                    for skill_id, proficiency in skills
                ]
            )
        for member in members:
            entry = dict(member or {}) if isinstance(member, dict) else {"technician_id": member}
            technician_id = entry.get("technician_id")
            if not technician_id and entry.get("user_id"):
                existing = work_models.Technician.objects.filter(
                    tenant_id=row.tenant_id, user_id=entry["user_id"]
                ).first()
                technician_id = existing.id if existing is not None else None
            if technician_id:
                was = (
                    work_models.Technician.objects.filter(
                        tenant_id=row.tenant_id, pk=technician_id
                    )
                    .select_related("crew", "user")
                    .first()
                )
                if was is None:
                    raise errors.ValidationError(
                        errors.VAL_UNKNOWN_LOOKUP,
                        message_key="work.crew.unknown",
                        params={"field": "members"},
                    )
                move_technician(actor, was.id, row.id)
                moved.append(
                    {"name": was.user.full_name or was.user.email,
                     "from": was.crew.name if was.crew_id else None}
                )
            elif entry.get("user_id"):
                created = create_technician(actor, {**entry, "crew_id": str(row.id)})
                moved.append({"name": created.get("name"), "from": None})
            else:
                raise errors.ValidationError(
                    errors.VAL_REQUIRED, message_key="work.field_required",
                    params={"field": "members"},
                )
    return {**_crew_answer(row), "moved": moved}


def _crew_answer(row: work_models.Crew) -> dict[str, Any]:
    """What a crew write answers: the row as the three lists draw it."""
    fresh = (
        work_models.Crew.objects.filter(pk=row.pk)
        .annotate(members=_member_counts())
        .prefetch_related("skills__skill", _members_prefetch())
        .get()
    )
    return {**_crew_list_row(fresh, legacy_name=False), "slug": crew_slug(fresh)}


def _contact(payload: dict[str, Any], kind: str) -> tuple[str | None, str | None]:
    """P3.53 — a CONTRACTOR's phone and email: how the office reaches the firm.

    ⚠ **A CREW HAS NONE, AND ONE SENT IS REFUSED BY NAME** rather than quietly
    dropped (`work.crew.contact_contractor_only`): a crew is reached through
    its members, each of whom has a login, and a second phone number on the
    crew row would be a second place for *who do I ring* to be wrong.
    """
    phone = str(payload.get("phone") or "").strip() or None
    email = str(payload.get("email") or "").strip() or None
    if kind != work_models.Crew.KIND_CONTRACTOR and (phone or email):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="work.crew.contact_contractor_only",
            params={"field": "phone" if phone else "email"},
        )
    if email and ("@" not in email or email.startswith("@") or email.endswith("@")):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="work.crew.email_format", params={"field": "email"}
        )
    return phone, email


def update_crew(actor: Any, crew_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    row = work_models.Crew.objects.filter(tenant_id=_tenant_id(), pk=crew_id).first()
    if row is None:  # cross-tenant is INDISTINGUISHABLE from absent (hard rule 1)
        raise errors.NotFoundError()
    payload = dict(payload or {})
    before = {"name": row.name, "kind": row.kind, "active": row.active}
    for field in ("name", "role_label"):
        if field in payload:
            setattr(row, field, payload[field] or "")
    if "headcount" in payload:
        row.headcount = payload["headcount"] or None
    if "active" in payload:
        row.active = bool(payload["active"])
    for field in ("shift_start", "shift_end"):
        if field in payload:
            setattr(row, field, _time_or_none(payload[field], field))
    if "phone" in payload or "email" in payload:
        before.update({"phone": row.phone, "email": row.email})
        phone, email = _contact(
            {
                "phone": payload.get("phone", row.phone),
                "email": payload.get("email", row.email),
            },
            row.kind,
        )
        row.phone, row.email = phone, email
    with transaction.atomic():
        row.save()
        core_audit.write_row(
            action="work.crew.updated",
            entity_type="crew",
            entity_id=row.id,
            actor_user_id=_actor_id(actor),
            before=before,
            after={
                "name": row.name, "kind": row.kind, "active": row.active,
                "phone": row.phone, "email": row.email,
            },
        )
    return _crew_answer(row)


def set_crew_skills(actor: Any, crew_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`PUT /work/crews/{id}/skills` — P3.52, the technician's shape, audited.

    ⚠ **NOTHING WROTE `crew_skills` BEFORE THIS** — only the sample data did,
    directly — so a crew or contractor added through the product could never be
    advised for a skilled job. A REPLACE, like `set_skills`: the screen shows
    the whole set and an unticked skill is meant.
    """
    tenant_id = _tenant_id()
    row = work_models.Crew.objects.filter(tenant_id=tenant_id, pk=crew_id).first()
    if row is None:  # cross-tenant reads as absent (hard rule 1)
        raise errors.NotFoundError()
    wanted = _clean_skill_list(payload, tenant_id)
    before = sorted(
        f"{skill.skill.code}:{skill.proficiency}" for skill in row.skills.select_related("skill")
    )
    with transaction.atomic():
        row.skills.all().delete()
        work_models.CrewSkill.objects.bulk_create(
            [
                work_models.CrewSkill(
                    tenant_id=tenant_id, crew_id=row.id, skill_id=skill_id, proficiency=proficiency
                )
                for skill_id, proficiency in wanted
            ]
        )
        core_audit.write_row(
            action="work.crew.skills_set",
            entity_type="crew",
            entity_id=row.id,
            actor_user_id=_actor_id(actor),
            before={"skills": before},
            after={"skills": sorted(f"{sid}:{prof}" for sid, prof in wanted)},
        )
    return _crew_answer(row)


def move_technician(actor: Any, technician_id: Any, crew_id: Any) -> None:
    """P3.44 — put a technician on another crew, or on none (`crew_id: null`).

    The crew's MEMBERS figure is a count of the technicians naming it, so the
    move is the whole write: *D. Ortiz moved to Field crew B; Field crew A
    reads (1)*. Audited with both crews' NAMES (B14 rule 31 — a history reads
    in words).
    """
    tenant_id = _tenant_id()
    row = (
        work_models.Technician.objects.filter(tenant_id=tenant_id, pk=technician_id)
        .select_related("crew")
        .first()
    )
    if row is None:
        raise errors.NotFoundError()
    crew = None
    if crew_id not in (None, ""):
        crew = work_models.Crew.objects.filter(tenant_id=tenant_id, pk=crew_id).first()
        if crew is None:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP, message_key="work.crew.unknown", params={"field": "crew_id"}
            )
    if str(row.crew_id or "") == str(getattr(crew, "id", "") or ""):
        return
    before = row.crew.name if row.crew_id else None
    with transaction.atomic():
        row.crew = crew
        row.save(update_fields=["crew", "updated_at"])
        core_audit.write_row(
            action="work.technician.crew_moved",
            entity_type="technician",
            entity_id=row.id,
            actor_user_id=_actor_id(actor),
            before={"crew": before},
            after={"crew": crew.name if crew else None},
        )


def add_crew_member(actor: Any, crew_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/crews/{id}/members` — ruling 26, *Add crew member* (4·1a).

    `{technician_id}` moves an existing technician onto this crew; `{user_id}`
    makes a technician profile for a login that has none yet AND puts it on the
    crew in one act (a profile beside an existing login — `BR-WRK-028`'s first
    sentence stands; a person with no login is refused exactly as
    `create_technician` refuses them).

    ⚠ **A CONTRACTOR'S PEOPLE ARE NOT ADDED HERE.** Ruling 36 gives them
    phone-only logins, which wait for the technician field-app document; until
    then a contractor row is refused `work.crew.members_crew_only`.
    """
    tenant_id = _tenant_id()
    crew = work_models.Crew.objects.filter(tenant_id=tenant_id, pk=crew_id).first()
    if crew is None:
        raise errors.NotFoundError()
    if crew.kind != work_models.Crew.KIND_CREW:
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="work.crew.members_crew_only", params={}
        )
    payload = dict(payload or {})
    technician_id = payload.get("technician_id")
    if technician_id:
        move_technician(actor, technician_id, crew.id)
    elif payload.get("user_id"):
        existing = work_models.Technician.objects.filter(
            tenant_id=tenant_id, user_id=payload["user_id"]
        ).first()
        if existing is not None:
            move_technician(actor, existing.id, crew.id)
        else:
            create_technician(actor, {**payload, "crew_id": str(crew.id)})
    else:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.field_required", params={"field": "technician_id"}
        )
    return _crew_answer(crew)


def create_technician(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Add a technician profile to an EXISTING login (`US-WRK-020` TC-1/TC-2).

    ⚠ **THE REFUSAL IS THE STORY.** `BR-WRK-028`: *"a profile beside an
    existing identity.User, not a second identity"*. A `user_id` with no login
    behind it is refused and the message routes the caller to Settings → Team,
    because the alternative — creating the login here — would be a second place
    to invite a person, and then a second place to deactivate them, reset their
    password and audit them. The Product Owner ruled the same shape for field
    technicians on 2026-09-04 (*"will you keep them in user table?"* — yes, one
    table).
    """
    payload = dict(payload or {})
    user_id = _require(payload, "user_id")
    if identity_seam.user(user_id) is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.technician_needs_login",
            params={},
        )
    tenant_id = _tenant_id()
    if work_models.Technician.objects.filter(tenant_id=tenant_id, user_id=user_id).exists():
        raise errors.BizError(
            errors.BIZ_IDEMPOTENT,
            br_ref="BR-WRK-028",
            message_key="work.technician_exists",
        )
    crew_id = payload.get("crew_id") or None
    if crew_id and not work_models.Crew.objects.filter(tenant_id=tenant_id, pk=crew_id).exists():
        raise errors.NotFoundError()
    with transaction.atomic():
        row = work_models.Technician.objects.create(
            tenant_id=tenant_id,
            user_id=user_id,
            crew_id=crew_id,
            role_label=payload.get("role_label") or "",
            shift_start=_time_or_none(payload.get("shift_start"), "shift_start"),
            shift_end=_time_or_none(payload.get("shift_end"), "shift_end"),
            van=payload.get("van") or "",
        )
        core_audit.write_row(
            action="work.technician.created",
            entity_type="technician",
            entity_id=row.id,
            actor_user_id=_actor_id(actor),
            after={"user_id": str(user_id), "role_label": row.role_label},
        )
    row = work_models.Technician.objects.select_related("user", "crew").get(pk=row.pk)
    return technician_detail(row)


def set_skills(actor: Any, technician_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`PUT /work/technicians/{id}/skills` — the skills wizard's confirm.

    A REPLACE and not a merge, because the wizard's third step shows the whole
    set and a supervisor who unticks Water II means it. The audit row carries
    both sides so *what did she hold before* is answerable.
    """
    tenant_id = _tenant_id()
    row = work_models.Technician.objects.filter(tenant_id=tenant_id, pk=technician_id).first()
    if row is None:
        raise errors.NotFoundError()
    wanted = _clean_skill_list(payload, tenant_id)
    before = sorted(
        f"{skill.skill.code}:{skill.proficiency}" for skill in row.skills.select_related("skill")
    )
    with transaction.atomic():
        row.skills.all().delete()
        work_models.TechnicianSkill.objects.bulk_create(
            [
                work_models.TechnicianSkill(
                    tenant_id=tenant_id,
                    technician_id=row.id,
                    skill_id=skill_id,
                    proficiency=proficiency,
                )
                for skill_id, proficiency in wanted
            ]
        )
        core_audit.write_row(
            action="work.technician.skills_set",
            entity_type="technician",
            entity_id=row.id,
            actor_user_id=_actor_id(actor),
            before={"skills": before},
            after={"skills": sorted(f"{sid}:{prof}" for sid, prof in wanted)},
        )
    row = work_models.Technician.objects.select_related("user", "crew").get(pk=row.pk)
    return technician_detail(row)


def _clean_skill_list(payload: dict[str, Any], tenant_id: Any) -> list[tuple[Any, str]]:
    entries = (payload or {}).get("skills")
    if not isinstance(entries, list):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="work.skills_not_a_list", params={}
        )
    known = {
        str(pk)
        for pk in work_models.WorkSkill.objects.filter(tenant_id=tenant_id).values_list(
            "id", flat=True
        )
    }
    cleaned: list[tuple[Any, str]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise errors.ValidationError(
                errors.VAL_FORMAT, message_key="work.skills_not_a_list", params={}
            )
        skill_id = str(entry.get("skill_id") or "")
        proficiency = entry.get("proficiency") or work_models.TechnicianSkill.PROFICIENCY_TRAINED
        if skill_id not in known:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP, message_key="work.skill_unknown", params={}
            )
        if proficiency not in work_models.TechnicianSkill.PROFICIENCIES:
            # `not_held` is the one a caller is most likely to send, because the
            # screen renders it. It is an ABSENCE, so it is refused by name
            # rather than quietly stored as a third proficiency.
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="work.proficiency_unknown",
                params={"proficiency": proficiency},
            )
        if skill_id in seen:
            continue
        seen.add(skill_id)
        cleaned.append((skill_id, proficiency))
    return cleaned


def set_certifications(
    actor: Any, technician_id: Any, payload: dict[str, Any]
) -> dict[str, Any]:
    """`PUT /work/technicians/{id}/certifications`.

    ⚠ **A DATE IN THE PAST IS ACCEPTED** (`US-WRK-021` TC-5). Refusing it would
    lose the record of a lapse, which is the one thing the watch exists to
    show — and a supervisor entering a certification that ran out last week is
    telling the truth about the world.
    """
    tenant_id = _tenant_id()
    row = work_models.Technician.objects.filter(tenant_id=tenant_id, pk=technician_id).first()
    if row is None:
        raise errors.NotFoundError()
    entries = (payload or {}).get("certifications")
    if not isinstance(entries, list):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="work.certifications_not_a_list", params={}
        )
    known = {kind["id"] for kind in tenancy_seam.certification_types()}
    cleaned: list[tuple[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        type_id = str((entry or {}).get("certification_type_id") or "")
        if type_id not in known:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP, message_key="work.certification_unknown", params={}
            )
        expires = (entry or {}).get("expires_on") or None
        if expires:
            try:
                expires = date.fromisoformat(str(expires))
            except ValueError as exc:
                raise errors.ValidationError(
                    errors.VAL_FORMAT,
                    message_key="work.certification_date",
                    params={},
                ) from exc
        if type_id in seen:
            continue
        seen.add(type_id)
        cleaned.append((type_id, expires))

    before = sorted(
        f"{cert.certification_type_id}:{cert.expires_on}" for cert in row.certifications.all()
    )
    # A certificate's PROOF (image 33) survives a renewal: the rows are a
    # replace, so each new row carries the file its predecessor named — a
    # renewal changes a date, and losing the scan to it would be data loss
    # dressed as an edit.
    proofs = {
        str(cert.certification_type_id): cert.evidence_document_id
        for cert in row.certifications.all()
        if cert.evidence_document_id
    }
    with transaction.atomic():
        row.certifications.all().delete()
        work_models.TechnicianCertification.objects.bulk_create(
            [
                work_models.TechnicianCertification(
                    tenant_id=tenant_id,
                    technician_id=row.id,
                    certification_type_id=type_id,
                    expires_on=expires,
                    evidence_document_id=proofs.get(str(type_id)),
                )
                for type_id, expires in cleaned
            ]
        )
        core_audit.write_row(
            action="work.technician.certifications_set",
            entity_type="technician",
            entity_id=row.id,
            actor_user_id=_actor_id(actor),
            before={"certifications": before},
            after={"certifications": sorted(f"{t}:{e}" for t, e in cleaned)},
        )
    row = work_models.Technician.objects.select_related("user", "crew").get(pk=row.pk)
    return technician_detail(row)


def set_unavailable(actor: Any, technician_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/technicians/{id}/unavailable` — `WS-24`'s *Set unavailable*.

    ⚠ **THIS IS WHAT A SUPERVISOR GETS INSTEAD OF DELETE** (`US-WRK-020`
    TC-5). A technician with jobs against their name cannot be removed —
    `work_orders` will point at them from wave G, and a deleted row would leave
    a job assigned to nobody with no way to see it happened. Marking them
    unavailable takes them out of the picker and leaves the history readable.

    Passing `status: on_shift` is how they come back, so this one endpoint is
    both directions rather than a second one nobody would find.
    """
    tenant_id = _tenant_id()
    row = work_models.Technician.objects.filter(tenant_id=tenant_id, pk=technician_id).first()
    if row is None:
        raise errors.NotFoundError()
    payload = dict(payload or {})
    status = payload.get("status") or work_models.Technician.STATUS_UNAVAILABLE
    # FB-033 — On break and Off duty are the technician's to say, from the
    # phone (`availability.py`); the office sets only these three.
    if status not in work_models.Technician.OFFICE_STATUSES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.technician_status_unknown",
            params={"status": status},
        )
    before = {"status": row.status, "reason": row.unavailable_reason}
    with transaction.atomic():
        row.status = status
        row.unavailable_reason = (
            str(payload.get("reason") or "")
            if status != work_models.Technician.STATUS_ON_SHIFT
            else ""
        )
        # FB-033 — the office's change is the newest fact: a phone tap from
        # before this moment never overwrites it (`availability._decide`).
        row.status_since = timezone.now()
        row.save(update_fields=["status", "status_since", "unavailable_reason", "updated_at"])
        # DEF-WRK-10615 — the office's word now holds the status; an End shift
        # left from earlier no longer does, so the morning return leaves it.
        from apps.work import shifts as work_shifts

        work_shifts.settle_shift_ends(row.id)
        core_audit.write_row(
            action="work.technician.availability_set",
            entity_type="technician",
            entity_id=row.id,
            actor_user_id=_actor_id(actor),
            before=before,
            after={"status": row.status, "reason": row.unavailable_reason},
        )
    row = work_models.Technician.objects.select_related("user", "crew").get(pk=row.pk)
    return technician_detail(row)


def set_daily_job_limit(actor: Any, technician_id: Any, value: Any) -> None:
    """`PATCH /work/technicians/{slug} {daily_job_limit}` — CR-168-BRC10 §30.

    PO answer (2), 2026-10-05, verbatim: *"(b) Add a daily limit per technician
    (default 6), editable on the technician's page."* A whole number of at least
    one, with NO upper bound (NFR-5). **It refuses nothing downstream**: the
    Schedule board and the assign advice mark a person over it, and a dispatcher
    may still give them the job (ruling 2). Audited with both figures.
    """
    try:
        limit = int(str(value).strip())
        if str(limit) != str(value).strip() or limit < 1:
            raise ValueError
    except (TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="work.technician.daily_limit_invalid",
            params={"field": "daily_job_limit"},
        ) from None
    row = work_models.Technician.objects.filter(tenant_id=_tenant_id(), pk=technician_id).first()
    if row is None:
        raise errors.NotFoundError()
    if row.daily_job_limit == limit:
        return
    before = row.daily_job_limit
    with transaction.atomic():
        row.daily_job_limit = limit
        row.save(update_fields=["daily_job_limit", "updated_at"])
        core_audit.write_row(
            action="work.technician.daily_limit_set",
            entity_type="technician",
            entity_id=row.id,
            actor_user_id=_actor_id(actor),
            before={"daily_job_limit": before},
            after={"daily_job_limit": limit},
        )


def default_target() -> dict[str, Any] | None:
    """The DEFAULT promise an undated job is measured against (PO answer (1) of
    2026-10-04, judgment J7): `{priority {id, code, name}, hours, chosen}`.

    PO verbatim: *"(b), so every job has a promise to measure against"* — a job
    with no due date and no priority is measured from the time it was raised
    against **the Normal priority's hours** (72 h seeded), a tenant setting.
    The setting NAMES A PRIORITY (`work_settings.default_target_priority_id`);
    NULL — every tenant until somebody changes it — reads the tenant's `NORMAL`
    priority, so the seeded answer holds without a row. `chosen` says which of
    the two it is. None only for a tenant with no Normal priority and no
    choice, which is an absence the screen draws as a dash.

    Worked (J7): a job raised 10/01 09:00 with no date is due 10/04 09:00; a
    tenant that moves Normal to 48 h moves it to 10/03 09:00.
    """
    tenant_id = _tenant_id()
    row = work_models.WorkSettings.objects.filter(tenant_id=tenant_id).first()
    priority = None
    chosen = False
    if row is not None and row.default_target_priority_id:
        priority = row.default_target_priority
        chosen = True
    if priority is None:
        priority = work_models.WorkPriority.objects.filter(
            tenant_id=tenant_id, code__iexact="NORMAL"
        ).first()
    if priority is None:
        return None
    return {
        "priority": {"id": str(priority.id), "code": priority.code, "name": priority.name},
        "hours": priority.sla_hours,
        "chosen": chosen,
        # P5.3 (lane SRV-4, `work/0037`) — the at-risk list's warning window;
        # None reads *at risk once the promise has passed*.
        "at_risk_window_hours": getattr(row, "at_risk_window_hours", None) if row else None,
    }


def set_default_target(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/settings/sla` `{default_target_priority_id}` — which priority's
    hours undated jobs are measured against. Audited (hard rule 7)."""
    data = dict(payload or {})
    tenant_id = _tenant_id()
    priority = None
    if "default_target_priority_id" in data or "at_risk_window_hours" not in data:
        wanted = data.get("default_target_priority_id")
        priority = (
            work_models.WorkPriority.objects.filter(
                tenant_id=tenant_id, pk=wanted, active=True
            ).first()
            if wanted
            else None
        )
        if priority is None:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="work.settings.sla_priority_unknown",
                params={"priority": str(wanted or "")},
            )
    window_given = "at_risk_window_hours" in data
    window = None
    if window_given and data.get("at_risk_window_hours") not in (None, ""):
        # P5.3 (lane SRV-4) — whole hours, 1 or more; blank clears it back to
        # *at risk once the promise has passed*.
        try:
            window = int(str(data.get("at_risk_window_hours")))
        except (TypeError, ValueError):
            raise errors.ValidationError(
                errors.VAL_FORMAT, message_key="work.priorities.sla_not_hours"
            ) from None
        if window < 1:
            raise errors.ValidationError(errors.VAL_RANGE, message_key="work.priorities.sla_negative")
    with transaction.atomic():
        row, _ = work_models.WorkSettings.objects.get_or_create(tenant_id=tenant_id)
        before = {
            "default_target_priority_id": (
                str(row.default_target_priority_id) if row.default_target_priority_id else None
            ),
            "at_risk_window_hours": row.at_risk_window_hours,
        }
        fields = ["updated_at"]
        if priority is not None:
            row.default_target_priority = priority
            fields.append("default_target_priority")
        if window_given:
            row.at_risk_window_hours = window
            fields.append("at_risk_window_hours")
        row.save(update_fields=fields)
        core_audit.write_row(
            action="work.settings.sla_default_set",
            entity_type="work_settings",
            entity_id=row.id,
            actor_user_id=_actor_id(actor),
            before=before,
            after={
                "default_target_priority": priority.code if priority else None,
                "at_risk_window_hours": row.at_risk_window_hours,
            },
        )
    return default_target() or {}


def push_settings() -> dict[str, Any]:
    """`GET /work/settings/push` — whether an assignment rings as its
    priority's push kind (PO answer 9 as corrected 2026-10-21: an OPTION,
    seeded OFF). The per-priority mapping itself is each priority's
    `push_kind` on `/lookups/work_priorities`."""
    row = work_models.WorkSettings.objects.filter(tenant_id=_tenant_id()).first()
    return {"push_by_priority": bool(row.push_by_priority) if row is not None else False}


def set_push_settings(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/settings/push` `{push_by_priority: bool}` — System Admin.
    A strict boolean: anything else is refused by name rather than read as a
    truthy string. Audited `work.settings.push_by_priority_set` (hard rule 7)."""
    data = dict(payload or {})
    value = data.get("push_by_priority")
    if not isinstance(value, bool):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="work.settings.push_by_priority_not_boolean",
            field_errors=[
                {
                    "field": "push_by_priority",
                    "code": errors.VAL_FORMAT,
                    "message_key": "work.settings.push_by_priority_not_boolean",
                    "params": {},
                }
            ],
        )
    tenant_id = _tenant_id()
    with transaction.atomic():
        row, _ = work_models.WorkSettings.objects.get_or_create(tenant_id=tenant_id)
        before = row.push_by_priority
        row.push_by_priority = value
        row.save(update_fields=["push_by_priority", "updated_at"])
        core_audit.write_row(
            action="work.settings.push_by_priority_set",
            entity_type="work_settings",
            entity_id=row.id,
            actor_user_id=_actor_id(actor),
            before={"push_by_priority": before},
            after={"push_by_priority": value},
        )
    return push_settings()


def visit_message_settings() -> dict[str, Any]:
    """`GET /work/settings/visit-messages` — the utility's default preparation
    text (`DEF-WRK-10652`, ruling 3B). `chosen` is False while the utility has
    never set one and the PO's seeded sentence applies."""
    row = work_models.WorkSettings.objects.filter(tenant_id=_tenant_id()).first()
    stored = getattr(row, "visit_prep_default", None) if row is not None else None
    return {
        "visit_prep_default": work_models.VISIT_PREP_DEFAULT if stored is None else stored,
        "chosen": stored is not None,
    }


def set_visit_message_settings(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/settings/visit-messages` `{visit_prep_default}` — blank is
    a utility that wants NO default line; audited (hard rule 7)."""
    from apps.work import templates_svc

    data = dict(payload or {})
    if "visit_prep_default" not in data:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="work.lookups.required",
            params={"field": "visit_prep_default"},
        )
    text = str(data.get("visit_prep_default") or "").strip()
    if len(text) > templates_svc.PREP_MAX_CHARS:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="work.template.prep_too_long",
            params={"field": "visit_prep_default", "max": templates_svc.PREP_MAX_CHARS},
        )
    tenant_id = _tenant_id()
    with transaction.atomic():
        row, _ = work_models.WorkSettings.objects.get_or_create(tenant_id=tenant_id)
        before = row.visit_prep_default
        row.visit_prep_default = text
        row.save(update_fields=["visit_prep_default", "updated_at"])
        core_audit.write_row(
            action="work.settings.visit_prep_default_set",
            entity_type="work_settings",
            entity_id=row.id,
            actor_user_id=_actor_id(actor),
            before={"visit_prep_default": before},
            after={"visit_prep_default": text},
        )
    return visit_message_settings()


def set_lapse_policy(actor: Any, policy: str) -> dict[str, Any]:
    """The tenant's answer to `OQ-WRK-1493` — `warn` or `block`.

    Written through a service rather than edited on a settings screen at this
    wave, because the screen that would carry it is a Settings card and this is
    a Work wave. The row exists so a utility with a safety officer can be
    switched over the day they ask, and the crews screen already reads it.
    """
    if policy not in work_models.WorkSettings.LAPSE_POLICIES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.lapse_policy_unknown",
            params={"policy": policy},
        )
    if policy == work_models.WorkSettings.LAPSE_BLOCK:
        # ⚠ RETIRED — PO answer 2, 2026-10-04, verbatim *"(a) Warn only, the
        # same as skills."* `BR-WRK-030` is SUPERSEDED: a lapsed certification
        # warns and never blocks, for EVERY tenant, so the switch no longer has
        # a second position (`CR-168-BRC10` §7.3, P4.5). The column stays a
        # lawful container read by nothing.
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.settings.lapse_policy_retired",
            br_ref="BR-WRK-030",
        )
    tenant_id = _tenant_id()
    with transaction.atomic():
        row, _ = work_models.WorkSettings.objects.get_or_create(tenant_id=tenant_id)
        before = row.certification_lapse_policy
        row.certification_lapse_policy = policy
        row.save(update_fields=["certification_lapse_policy", "updated_at"])
        core_audit.write_row(
            action="work.settings.lapse_policy_set",
            entity_type="work_settings",
            entity_id=row.id,
            actor_user_id=_actor_id(actor),
            before={"certification_lapse_policy": before},
            after={"certification_lapse_policy": policy},
        )
    return {"certification_lapse_policy": policy}


__all__ = [
    "crews_page",
    "staff_choices",
    "technician_by_slug",
    "technician_detail",
    "certification_watch",
    "lapse_policy",
    "skill_match",
    "create_crew",
    "update_crew",
    "create_technician",
    "set_skills",
    "set_certifications",
    "set_unavailable",
    "set_lapse_policy",
    "push_settings",
    "set_push_settings",
    "technician_slug",
    "crew_slug",
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-020@2b08ba9f · US-WRK-021@2b08ba9f (EP-WRK-04) · 03-field-map.md §2.3 · 07-endpoints.md §4 #50–60 · 10-execution-plan.md wave F task F1
# generated: 2026-09-05 by the CR-070 wave F build lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H✔(work/0007_rls_force_workforce is the 🔒 path; review-ledger row is F5)
# gates: pytest tests/test_us_wrk_020_workforce.py tests/test_us_wrk_021_certification_watch.py · G78 (Work writes nothing foreign) · tests/test_us_wrk_rls_pg.py on PostgreSQL
# exceptions: TODAY · UTILISATION · the *THIS MONTH* figures are NOT served, stored or drawn — `work_orders` has no assignee column until wave G, so nothing in the database can produce them (UNSERVED_UNTIL_WAVE_G, and the stamp in 08-screen-layouts.md's *where the drawing loses* table, beside Work-002's TECHNICIAN column for the same reason)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
