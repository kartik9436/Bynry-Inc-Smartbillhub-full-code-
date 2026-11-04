# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4.
# Rules:    BR-RBS-039 (read through a seam this module owns, by name, in
#           process, under the tenant context) · RBR-03 (policy is READ, never
#           duplicated) · CLAUDE.md hard rule 1
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  B2 Addendum r25 (this seam's row in the cross-module interface
#           register, added in the same commit as this file)
# ───────────────────────────────────────────────────────
"""operations → tenancy — settings. POLICY IS READ, NEVER DUPLICATED. READ ONLY.

Every threshold a runbook honours that a utility has **already set** — the
collections ladder's steps, the estimation rules, the tax tolerance, the service
catalogue, the tenant's own timezone that its schedules run in — is read here.

⚠ **`RBR-03`, AND IT IS THE RULE MOST LIKELY TO BE BROKEN BY ACCIDENT.** A
parameter that already exists in Settings is typed `ref:setting`: rendered
**read-only with a link to the screen that owns it**, never copied into the
runbook's own parameters. A runbook that copies a setting has given the utility
two answers to one question and no way to tell which is in force — and the copy
will be the stale one, because the screen that owns the setting is the one
people actually edit.

⚠ **THE TIMEZONE IS THE TENANT'S OWN**, as the notification schedule already
does (`BR-RBS-016`). A sweep that runs at 06:00 UTC for a utility in Texas
arrives at midnight, which is not what *"the list a clerk opens each morning"*
means.

⚠ **THIS FILE DECLARES THE PAIR AND HOLDS NO CALLABLE YET, ON PURPOSE.** Wave A
builds the module and its boundary; each later wave brings the reads its own
runbooks actually need. A selector written here now would be a function nothing
calls (hard-won law 2), and naming one in prose that `tenancy` does not expose
would fail `G20` — the guard that caught `DEF-075`. What this module will need
and `tenancy` does not offer today is inventoried in
`17-runbooks/13-selector-inventory.md`, and **`tenancy` adds each of them** —
never this file reaching past the seam.
"""

from apps.runbooks.boundary import SeamDeclaration

SEAM = SeamDeclaration(
    module="tenancy",
    pair="operations → tenancy",
    crosses="settings — policy is read, never duplicated",
)


# ── CR-075 wave C · the reads runbook 1 makes (US-RBS-001) ────────────────
#
# Added with `definitions/configuration_check.py` in the same commit, because a
# seam function nothing calls is hard-won law 2's dead code in its quietest
# form. Every one below resolves a selector `tenancy` already publishes —
# `apps.tenancy.selectors.services_overview`,
# `apps.tenancy.selectors.number_series_overview`,
# `apps.tenancy.selectors.holidays` and `apps.tenancy.selectors.tenant_today`.
# Nothing here is new work asked of `tenancy`, which is why none of them is a
# row in the selector inventory.
#
# ⚠ **THIS LIST NAMED FOUR SELECTORS THIS FILE NO LONGER CALLS FOR ABOUT AN
# HOUR, AND THAT IS WHY IT IS WORTH A NOTE.** The first draft read
# `enabled_service_codes`, `service_default_uoms`, `service_billed_uoms` and
# `unmetered_service_codes`; `services_overview` replaced all four when the
# retired `metered` question was found (`BR-TEN-1180`), and the comment kept
# listing the old ones. `G20` could not object — every name it listed is real —
# so the only thing wrong was that a reader would believe it, which is hard-won
# law 1 exactly: a comment claiming a guarantee is not the guarantee. **When a
# read changes, the list changes in the same edit.**


def service_basis() -> list[dict[str, object]]:
    """Every ACTIVE service with the tenant's own declaration about it — ONE read.

    `apps.tenancy.selectors.services_overview` returns one row per catalogue
    service carrying `enabled`, `billing_basis`, `primary_uom`, `billed_uom` and
    `conversion_factor`. Runbook 1 steps 1 and 7 both read it, and they read the
    SAME call so they cannot disagree about which services a tenant sells.

    ⚠ **`billing_basis` AND NOT `metered` — THE TWO-STATE QUESTION IS RETIRED**
    (`BR-TEN-1180`, 2026-09-02, a clean cut with no shim: PO verbatim, *"we are
    in beta stage … you can fix it; I will delete the DB and relaunch"*). There
    are THREE bases — `metered`, `share`, `capacity` — and asking *is this
    metered* gets a confident answer for a service that is **neither metered nor
    counted**, which is `DEF-2409` exactly. A first draft of this seam read
    `unmetered_service_codes()` and did precisely that.

    ⚠ **THE COST OF GETTING IT WRONG WAS MEASURED, NOT IMAGINED.** With the
    two-state read, runbook 1 reported *"Sewer says nothing about what it is
    measured in"* as a **blocker on every utility that sells sewer** — and sewer
    has no unit BY DESIGN: its basis is `share`, a percentage of another
    service's money (`BR-RAT-015`), and r10 draws it as an em-dash in both unit
    columns. The finding was a false blocker on a correct configuration, which
    is the fastest way to teach a clerk that this runbook is noise.
    """
    from apps.tenancy import selectors as tenancy_selectors

    return [row for row in tenancy_selectors.services_overview() if row.get("enabled")]


def enabled_services() -> tuple[str, ...]:
    """The services this tenant actually SELLS, in catalogue order.

    ⚠ **THIS IS THE AXIS THE WHOLE RUN IS ORGANISED ON** (`01-overview.md`
    §8.1): one verdict per enabled service, rolled up to a tenant verdict that
    is the worst of them. A tenant that sells Water and Sewer gets two service
    verdicts and never eleven — a verdict over a service nobody sells is noise
    a clerk has to learn to ignore.

    ⚠ **AND IT IS READ WHEN THE RUN STARTS, NEVER STORED ON THE DEFINITION**
    (`BR-RBS-042` clause 1). Runbook 1's service list is permanently *all*, and
    *all* is a RULE rather than a value: a utility that enables Trash tomorrow
    gets a third service verdict on its next run with nothing to reconfigure.
    """
    return tuple(str(row["service"]) for row in service_basis())


def number_series() -> list[dict[str, object]]:
    """Every number series this tenant holds — bills, accounts, receipts.

    A tenant with none cannot issue a bill at all: the series is what stamps
    the number, and `billing` refuses at issue rather than inventing one.
    """
    from apps.tenancy import selectors as tenancy_selectors

    return list(tenancy_selectors.number_series_overview())


def holiday_calendar() -> list[dict[str, object]]:
    """The tenant's holidays — the calendar a due date and a read window land on.

    Empty is a WARNING and never a blocker: a utility that has not entered its
    holidays still bills, it just dates things on days its office is shut.
    """
    from apps.tenancy import selectors as tenancy_selectors

    return list(tenancy_selectors.holidays())


def today():
    """The tenant's OWN today — `apps.tenancy.selectors.tenant_today`.

    ⚠ **THIS IS A SEAM FUNCTION BECAUSE `G115` REFUSED IT ANYWHERE ELSE, AND
    THE GATE WAS RIGHT.** Runbook 1's *As at: Today* was first written as a
    two-line helper inside the definition that imported `tenancy.selectors`
    directly; `G115` failed the merge by file and line
    (`configuration_check.py:825 imports apps.tenancy outside seams/*_seam.py`).
    It is a foreign read like every other, and the fact that it returns a date
    rather than a row makes no difference to the boundary.

    Reading the TENANT's clock rather than the server's is not a nicety: a run
    started at 23:50 in Houston is still the 6th there and the 7th in UTC, and a
    rate version that starts tomorrow must not be in force because the process
    happens to sit in another timezone.
    """
    from apps.tenancy import selectors as tenancy_selectors

    return tenancy_selectors.tenant_today()


def currency() -> str:
    """The tenant's declared book currency, `CHAR(3)`, or `USD` — hard rule 2.

    ⚠ **IT IS TENANCY'S FACT AND IT IS READ HERE RATHER THAN FROM `ledger`.**
    `apps.ledger.exports._currency` answers the same question for the recorded
    handover, and calling THAT across the seam would be a runbook reaching into
    another module's private function for a value its owner publishes. The
    currency lives in `regional_settings`; this is that read, through the door
    `BR-RBS-039` names.

    One export file is ONE currency (decision log 2026-09-06), so the month-end
    journal file checks this before it composes a row — a CAD tenant's file
    labelled USD is a set of books an accountant would post verbatim.
    """
    from apps.tenancy import selectors as tenancy_selectors

    value = (tenancy_selectors.regional_settings() or {}).get("currency")
    return str(value) if value else "USD"



# ── CR-075 wave I · the one read the SCHEDULER makes (US-RBS-007) ──────────


def live_tenants() -> tuple[str, ...]:
    """Every utility that finished provisioning — `apps.tenancy.selectors.live_tenant_subdomains`.

    ⚠ **THIS IS THE ONE READ IN THIS MODULE THAT IS MADE WITH NO TENANT CONTEXT
    SET, AND IT IS LAWFUL** for exactly the reason `tenancy` gives at the
    selector itself: `tenants` is the RLS-exempt REGISTRY (`BR-TEN-003`), not a
    tenant-hosted table, so resolving *who are the utilities* reaches no
    utility's data. The scheduler then enters each tenant's context before it
    touches a single runbook row (hard rule 1).

    ⚠ **AND IT IS A SEAM FUNCTION RATHER THAN A DIRECT IMPORT BECAUSE `G115`
    WOULD HAVE REFUSED IT ANYWHERE ELSE, INCLUDING AS A DYNAMIC IMPORT.**
    `apps/work/rules.py` makes the same read through `importlib.import_module`
    from its own sweep; the census permits that in `work` and not here, and the
    gate is right — a boundary with one convenient exception is a boundary with
    a queue forming at it.

    ⚠ **AN ENVIRONMENT VARIABLE WOULD HAVE BEEN THE OBVIOUS SHORTCUT AND IT IS
    A DEFECT WITH A NUMBER** (`DEF-3422`). The notification dispatcher paced its
    cycle from `NOTIFICATIONS_DISPATCH_TENANTS`; unset — which is every
    deployment — **every firing dispatched to nobody**, silently, in a log
    nobody reads. A scheduler with the same hole would fire for no utility at
    all and every screen would go on saying *next run 06:00*.
    """
    from apps.tenancy import selectors as tenancy_selectors

    return tuple(tenancy_selectors.live_tenant_subdomains())
