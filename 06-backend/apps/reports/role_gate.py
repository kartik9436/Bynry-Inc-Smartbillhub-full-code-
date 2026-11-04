# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 5 · `P5.9` (role gating on a definition —
#           `min_role` resolved SERVER-SIDE).
#           Screens: 1·1 (the catalogue) · 2·1 (the viewer)
# Rules:    BR-REP-023 (the access-review report is System Admin + Executive
#           only — Billing Clerk excluded; PO AR-1, 2026-08-08, CONFIRMED) ·
#           CLAUDE.md hard rule 1 (tenant scoping — this is a boundary INSIDE
#           one tenant and is the application's, never RLS's) ·
#           B14 rule 33 (rationale is ZERO WORDS ON SCREEN — a card a role may
#           not run is ABSENT, and the screen says nothing about why)
# Tests:    06-backend/tests/test_rep_p5_9_role_gate.py
# Impacts:  apps/reports/models.py (`ReportDefinition.min_role`) ·
#           apps/reports/migrations/0007_p5_9_min_role.py ·
#           apps/reports/catalogue_read.py (the card is absent) ·
#           apps/reports/api.py (the run is refused)
# ───────────────────────────────────────────────────────
"""WHO MAY RUN A REPORT — asked once, in one place, on the server.

⚠ **`BR-REP-023` HAS BEEN SIGNED SINCE 2026-08-08 AND NOTHING ENFORCED IT.**
The rule reads *"Access-review report (SC-2): System Admin + Executive only —
Billing Clerk excluded"*. Measured on 2026-09-27: `apps/reports/catalog.py`
CITED the rule in its trace header, `apps/audit/audit_log_dataset.py` printed a
`security_note` naming it, a test asserted that the NOTE was present — and
**every card was served to every tenant role, and `GET /reports/access_review`
ran for a Billing Clerk.** That is hard-won law 1 word for word: three files
described a guarantee and none of them was it. The note is the claim; this file
is the guarantee.

⚠ **`min_role` IS THE BRIEF'S NAME AND THE FOUR ROLES ARE NOT A LADDER, SO
THE LADDER IS DECLARED HERE RATHER THAN ASSUMED.** `apps/identity/models.py`
holds **four** predefined platform roles — `system_admin`, `billing_clerk`,
`executive` and `field_technician` — as a SET, with no ordering anywhere in
the product. `RANK` below is an ordering minted for this one question and for
nothing else: it says which roles may reach a restricted REPORT, and it is not
a general seniority. `min_role = "executive"` therefore admits Executive and
System Admin and refuses Billing Clerk, which is exactly what `BR-REP-023`
says and is the only restriction the product ships.

⚠ **`field_technician` IS IN THE MAP AT ZERO RATHER THAN LEFT OUT.** Leaving
it out would give the same ANSWER — an absent role scores zero and is refused
— and would leave a reader unable to tell a deliberate rank from a role
nobody thought about. `A4_MATRIX` renders "—" for it on every one of its nine
rows, so zero is the transcription of a signed grid and not a judgment.

⚠ **IT FAILS CLOSED, AND THAT IS THE WHOLE POINT OF A RANK MAP OVER A DICT
LOOKUP.** A role this file has never heard of scores below every rank, so a
role added tomorrow sees an unrestricted report and does NOT see a restricted
one until somebody states where it sits. `dashboard_regions.role_may_see`
takes the same posture for the same reason and says so.

⚠ **A `min_role` OF NULL IS NOT "EVERYONE WITH A ROLE" BY ACCIDENT — IT IS THE
DEFAULT AND 45 OF THE 46 PLATFORM ROWS CARRY IT.** The route already runs
behind `AnyTenantRole`, so the floor is *a staff member of this tenant*. This
file raises that floor for the rows that name one; it never lowers it.

⚠ **A MACHINE PRINCIPAL IS NOT ASKED, AND NOT BECAUSE IT IS TRUSTED.** A
`ServiceAccountPrincipal` carries no `role` attribute at all (that is
`service_account_auth.py`'s deliberate design, so a machine cannot accidentally
satisfy a role test), and it is already gated by something NARROWER: the named
list of report keys it was granted. Asking this gate a question about a
principal with no role would score it below every rank and refuse every
restricted report — which is the right answer, and is the answer it already
gets from its own grant. The two checks are not layered here; `api.report()`
asks the grant first and a machine never reaches this code.

**WHAT THIS FILE DOES NOT DO, STATED SO NOBODY READS IT AS WIDER THAN IT IS.**
It does not gate a SCHEDULE (`apps/reports/schedules.py` runs as the tenant and
not as a person, and a scheduled restricted report is a question nobody has
asked yet — `OQ-REP-12766`). It does not gate an EXPORT that goes through the
scheduler. It gates the two doors a person uses: the catalogue and the viewer.
"""

from __future__ import annotations

from typing import Any

#: The ordering this ONE question uses. Not a seniority; see the docstring.
#: A role absent from this map scores below every rank and is refused any
#: report that names a `min_role` at all.
RANK: dict[str, int] = {
    "field_technician": 0,
    "billing_clerk": 1,
    "executive": 2,
    "system_admin": 3,
}

#: What a restricted report may name. A value outside this set is a typo or a
#: renamed role, and `may_run` refuses on it rather than guessing — an
#: unreadable restriction that admitted everybody would be the defect this
#: whole file exists to close, wearing a column.
MIN_ROLES: tuple[str, ...] = ("executive", "system_admin")


def _rank(role: Any) -> int:
    """Zero for a role this file does not declare, and zero for the one it
    declares AT zero. Both are refused any report carrying a floor, which is
    the only behaviour either needs; the map exists so a reader can tell them
    apart."""
    return RANK.get(str(role or "").strip(), 0)


def may_run(min_role: Any, role: Any) -> bool:
    """May a staff member holding `role` reach a report restricted to `min_role`?

    `min_role` of None/empty is the 45 unrestricted rows: yes, because the
    route's own `AnyTenantRole` already said this is a staff member of this
    tenant.
    """
    wanted = str(min_role or "").strip()
    if not wanted:
        return True
    if wanted not in MIN_ROLES:
        # Fails CLOSED on a value nothing declares — see MIN_ROLES.
        return False
    return _rank(role) >= _rank(wanted)


def refusal(key: str) -> Any:
    """The one refusal, so the viewer and any future caller say the same thing.

    ⚠ **IT NAMES THE REPORT AND NOT THE ROLE THAT WOULD OPEN IT.** Telling a
    Billing Clerk *"this needs Executive"* is RATIONALE, which B14 rule 33 puts
    at zero words on screen, and it is also a map of what the restricted
    reports are. The clerk is told the report is not theirs to run; the reason
    is in this file and in `BR-REP-023`.

    ⚠ **403 AND NOT 404.** A key the catalogue does not draw for this role is
    still a key that EXISTS in this tenant — HR-1 reserves 404 for another
    tenant's resource, and answering 404 here would make a restricted report
    indistinguishable from a typo for a clerk who bookmarked it last month
    while holding a different role.
    """
    from core import errors

    return errors.AuthError(
        errors.AUTH_PERMISSION_DENIED,
        message_key="reports.viewer.role_refused",
        params={"key": key},
    )


def for_key(key: str) -> str | None:
    """The `min_role` a key carries, or None for the 45 rows that carry none.

    ⚠ **COPY ON WRITE IS RESOLVED THE WAY THE CATALOGUE RESOLVES IT** — a
    tenant's own row on a key REPLACES the platform row, so a tenant that
    copied a restricted report and cleared the restriction on its copy gets its
    copy's answer. That is the same precedence `catalogue_read` applies six
    lines from its own gate, and the two must not drift: a viewer that read the
    platform row while the catalogue read the tenant's would refuse a card it
    had just drawn.

    ⚠ **AN UNKNOWN KEY ANSWERS None AND IS NOT AN ERROR HERE.** This function
    is asked BEFORE the key is resolved, deliberately (see the caller), so it
    must be silent about whether a key exists. The caller's own VAL-005 is what
    tells a typo it is a typo.
    """
    from django.db.models import Q

    from apps.reports.models import ReportDefinition
    from core import tenancy as core_tenancy

    # ⚠ **`Q(...) | Q(tenant_id=None)`, NEVER `tenant_id__in=(id, None)`.**
    # The first draft used `__in` and it silently lost every PLATFORM row:
    # Django renders it as SQL `IN (<uuid>, NULL)`, and **SQL `IN` never
    # matches NULL** — so `for_key("access_review")` answered None, the viewer
    # let a Billing Clerk straight through, and the catalogue (which has always
    # used the `Q` form six lines from its own gate) went on hiding the card.
    # A guard that answers *no restriction* is a guard that is not there, and
    # nothing about it would have looked wrong. Caught by the copy-on-write
    # case, which is the only one that asks this function about a key whose
    # answer is not None.
    rows = list(
        ReportDefinition.objects.filter(key=key)
        .filter(Q(tenant_id=core_tenancy.current_tenant_id()) | Q(tenant_id=None))
        .values_list("tenant_id", "min_role")
    )
    if not rows:
        return None
    for tenant_id, min_role in rows:
        if tenant_id is not None:
            return min_role or None
    return rows[0][1] or None
