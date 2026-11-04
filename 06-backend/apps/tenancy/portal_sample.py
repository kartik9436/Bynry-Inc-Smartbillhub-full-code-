# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-069 · US-CWP-070 (the switch, the five and the branding) ·
#           US-CWP-071..074 (answers, tips, centres) · US-CWP-016..018 (the
#           customer's own login) — all of them already BUILT, and none of
#           them reachable by a tenant that signed up through the real path.
# Rules:    PO ruling 2026-09-07, verbatim: *"before step 29 this - you ahve to
#           set all the self service data in settings -> configure -> Customer
#           portal - {overview, branding, Help & Answer, Tips  + service
#           centers }"* · BR-TEN-056/057 (a module's block of the sample set) ·
#           BR-TEN-060 (a block that cannot run is NAMED, never swallowed) ·
#           BR-TEN-063 (each block is its own transaction) · CLAUDE.md hard
#           rule 1 (tenant scoping) · hard-won law 2 (built is not wired) ·
#           hard-won law 5 (one source, never a second copy)
# Tests:    06-backend/tests/test_cwp_sample_portal.py
# Impacts:  apps/tenancy/sample_data.SAMPLE_MODULES (the two rows) ·
#           apps/tenancy/services.py (the two seams) ·
#           apps/portal/sample_data.py (the portal-owned half) ·
#           apps/tenancy/published_content_sample.py (the tenancy-owned half) ·
#           07-frontend/src/features/tenancy/SignupWizard.tsx (the steps)
# ───────────────────────────────────────────────────────
"""THE SAMPLE SET'S CUSTOMER PORTAL — configured first, then signed into.

WHAT WAS WRONG, MEASURED RATHER THAN ASSUMED
--------------------------------------------
Counted per tenant on the dev database, 2026-09-07:

  * `pine-hill` (hand-built by `manage.py seed_portal_demo`) had the lot —
    1 portal settings row, 8 help answers with 88 variants, 6 tips, 3 service
    centres with 21 rows of opening hours, and **the only portal login in the
    database**.
  * `brazosbend`, and every tenant provisioned through the real sign-up path,
    had **ZERO of all seven tables** and no login at all.

None of it was unbuilt. `apps/tenancy/published_content_sample.py` has seeded
answers, tips and centres since 2026-09-04 and `apps/portal/sample_data.py` has
saved the switches and the branding for as long; both are reached ONLY by the
demo command that builds Pine Hill and Oak Ridge. `"portal"` appeared in
`SAMPLE_MODULES` exactly zero times. **Built, and not wired** — CLAUDE.md
hard-won law 2, and the same shape the integrations seeder was found in on the
same day.

So this file writes no content of its own. It is a block BODY: it calls the two
seeders that already exist, in the order the Product Owner asked for.

WHY BOTH BLOCKS ARE REGISTERED UNDER `tenancy` AND NOT UNDER `portal`
----------------------------------------------------------------------
`SAMPLE_MODULES` resolves a block as `apps.<module>.services.<seam>`
(`seams.resolve`), and **`G81` refuses a public function in
`apps/portal/services.py` that is not one of the six declared write points** —
*"One more `def` there is one more write, and it fails by name."* A seeding
seam is not a portal write point and adding a row to `write_points.py` to make
room for one would be a ruling about what the customer portal may write, which
is emphatically not what this is.

The gate's own docstring settles it: *"that is the gate doing its job, not an
obstacle to route around."* So the seams live in `apps/tenancy/services.py`,
this file is their body, and **every actual write still happens inside the
module that owns the table** — the switches and the branding through
`apps/portal/settings_service.py`, the credential through
`apps/portal/credentials.py`, the answers, tips and centres through
`apps/tenancy/published_content.py`. Nothing here touches another module's
table; it calls another module's service, which is B2 §2's own contract.

⚠ **THIS IS THE FIRST BLOCK IN `SAMPLE_MODULES` WHOSE MODULE IS NOT THE OWNER
OF EVERY TABLE IT FILLS.** That is recorded in the decision log for 2026-09-07
rather than left for a future reader to discover and "correct".

WHY THE CONFIGURATION AND THE LOGIN ARE TWO BLOCKS AND NOT ONE
---------------------------------------------------------------
Because the Product Owner ordered them as two things and the order is the
point: *"before step 29 this"*. A customer who signs in to an unconfigured
portal sees branding that is not there, no answers, no tips and no counter to
walk into. Two blocks also mean the Sample data panel can say which half
failed — a portal that is branded but has nobody to sign in as is a different
problem from one nobody can configure.
"""

from __future__ import annotations

from typing import Any

from core import tenancy as core_tenancy


def seed_sample_portal_content(actor: Any) -> int:
    """The five things the ruling names — overview, branding, Help & answers,
    Tips, service centres — for the tenant in context.

    Returns **what this tenant has**, which is what the Sample data panel
    counts and how every other block's number reads — 18 on a seeded tenant:
    one settings row, 8 answers, 6 tips and 3 counters. Both halves are
    idempotent BY REFUSAL, so a replay writes nothing and reports the same 18
    rather than dropping to zero on a run that changed nothing.
    """
    from apps.portal import sample_data as portal_sample_data
    from apps.tenancy import published_content_sample

    tenant_id = core_tenancy.current_tenant_id()
    #: ⚠ **THE ACTOR CARRIES A NAME, AND IT IS NOT A PERSON'S.**
    #: `create_answer` stores `getattr(actor, "name", None)` as
    #: `last_changed_by`, which `CWP-072` shows a clerk. The plant's actor has
    #: no `name`, so the column would be null; the demo tenants' fixture signs
    #: with `Sarah Miller`, who does not work at the utility that just signed
    #: up. The sample set signs with the product's own word for what did it —
    #: the same spelling the completeness alert already uses, so the bell and
    #: this screen cannot end up with two nouns for one thing.
    from apps.tenancy.sample_data import SAMPLE_ALERT_OPERATION

    signed_by = _named(actor, SAMPLE_ALERT_OPERATION)

    settings = portal_sample_data.seed_sample_portal_settings(signed_by)
    content = published_content_sample.seed_published_content(tenant_id, who=signed_by)
    #: The centres' opening hours are rows too, and a counter with no hours is
    #: not a counter a person can walk into — so they are counted here rather
    #: than folded silently into `centres`.
    return (
        int(settings.get("settings") or 0)
        + int(content.get("answers") or 0)
        + int(content.get("tips") or 0)
        + int(content.get("centres") or 0)
    )


def seed_sample_portal_login(actor: Any) -> int:
    """One seeded customer who can sign in — the Product Owner's step 29.

    The account is chosen and the refusal is enforced in
    `apps/portal/sample_data.py`: it enrols a SAMPLE account or it enrols
    nothing, so a real customer's records are never given a password by a
    seeder.
    """
    from apps.portal import sample_data as portal_sample_data

    result = portal_sample_data.seed_sample_portal_login(actor)
    return int(result.get("credentials") or 0)


def seed_sample_portal_login_note(*_args: Any, **_kwargs: Any) -> str | None:
    """WHAT THE BLOCK STILL HAS TO SAY WHEN IT SUCCEEDED (`DEF-3224`).

    A block that seeds 0 credentials because the tenant has no sample account
    with an email address on file has NOT failed — but a panel reading
    *"seeded, 0"* under *"A customer who can sign in"* tells an operator
    nothing. The sentence names the address that was enrolled, so the person
    running the demo can find it without opening a database.

    ⚠ It never carries the password. A note is rendered on a screen and copied
    into support tickets; the password is in the code, where the person setting
    up a demo is already looking.
    """
    from apps.portal import credentials
    from apps.portal import sample_data as portal_sample_data

    tenant_id = core_tenancy.current_tenant_id()
    #: ⚠ THE SAME CHOICE THE BLOCK MADE, NOT *the first credential on the
    #: tenant*. A utility whose real customers have started enrolling would
    #: otherwise have one of THEM named on the Sample data panel.
    account, email = portal_sample_data._sample_account_to_enrol(tenant_id)
    if account is None:
        return "No sample account had an email address on file, so nobody was given a login."
    if credentials.credential_by_email(tenant_id, email) is None:
        return "The sample customer has no portal login yet."
    return f"{credentials.mask_email(email)} can sign in to the portal."


def _named(actor: Any, name: str) -> Any:
    """`actor`, with a `name` when it has none — never replacing one it has.

    A `SimpleNamespace` copy would drop `id`, `pk`, `role` and `is_authenticated`,
    every one of which a service downstream reads: `@require_role` reads `role`,
    and `audit_log` reads the id. So this wraps rather than rebuilds.
    """
    if getattr(actor, "name", None):
        return actor
    return _NamedActor(actor, name)


class _NamedActor:
    """Everything `actor` is, plus a name. Attribute lookup falls through."""

    def __init__(self, inner: Any, name: str) -> None:
        self._inner = inner
        self.name = name

    def __getattr__(self, item: str) -> Any:
        return getattr(self._inner, item)


# ── Lifecycle ─────────────────────────────────────────────
# packet: PO ruling 2026-09-07 (the portal's self-service data, before the login)
# generated: 2026-09-07 by the portal sample-data lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cwp_sample_portal.py · G68 (a tenant provisioned and seeded on PostgreSQL) · G81 (this file is NOT under apps/portal, and that is the point)
# exceptions: the first SAMPLE_MODULES block whose module is not the owner of every table it fills — decision log 2026-09-07
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
