#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: PER-JOURNEY E2E fixtures — the cohort each activated journey
#            asserts over, seeded from the journey file's own Fixture paragraph,
#            and a LOUD refusal when a journey has no fixture at all.
# Defect:   DEF-108 (2026-08-15) — *"no catalog journey has a fixture"*: on a
#           freshly booted stack, units 10 / units with a plan 0 /
#           unit_plan_assignments 0 / accounts 1 / meter_reads 0, so
#           `GET /billing/runs/{id}/findings` answers `ready:[] blocked:[6]` and
#           `.../exceptions` answers `rows:[] counts:{} totals:{}` — a journey
#           driving real screens over an EMPTY cohort is a green tick that proves
#           the buttons exist and nothing about the money.
#           DEF-110 (2026-08-15) — the fixture holds none of the state the
#           finance journeys need: one bill whose journal entry is dated 30 June,
#           so a July trial balance answers 0 rows, 0.000000 = 0.000000 at every
#           step, and a month-close journey would close an EMPTY July, export
#           ZERO rows, and PASS.
# Rules:    CLAUDE.md rule 1 (every write inside `tenant_context`; RLS FORCE) ·
#           rule 2 (NUMERIC(18,6) + CHAR(3), never float) · rule 4 (financial
#           immutability — nothing here updates an issued row) · rule 5 (only the
#           ledger posting service writes journal lines) · rule 7 (audit_log) ·
#           hard-won law 3 (defaults fail closed) · law 1 (a comment claiming a
#           guarantee is not the guarantee)
# Golden:   NO FIGURE IS TYPED HERE. The finance state is posted by importing
#           `tests/ledger_le_fixtures.py`, which transcribes the ❄️ signed LE-1
#           workbook; the plan cohort is written through the real metering
#           service. A second copy of a signed figure drifts (hard-won law 5).
# Tests:    `--check` is the machine assertion (an activated journey with no
#           fixture exits 1) and is wired into 08-qa/01-e2e/stack/boot_stack.sh.
# Impacts:  08-qa/01-e2e/stack/boot_stack.sh · 08-qa/01-e2e/stack/seed_e2e_fixture.py
#           (this runs AFTER it — that file seeds the ONE issued bill; this seeds
#           the world a named journey asserts over)
# ───────────────────────────────────────────────────────
"""Seed the fixture a NAMED journey needs, or refuse loudly that it cannot be seeded.

WHY THIS FILE EXISTS, in one sentence: **a journey that cannot be seeded must be
a loud failure at boot, not a green run over an empty cohort.**

`manage.py seed_demo` provisions the W1 world (services, plans, rate schedules,
premises, 10 units, 20 service points) and stops, deliberately. `seed_e2e_fixture.py`
adds ONE account and ONE issued bill. Everything else a journey file's **Fixture**
paragraph describes — a unit that is actually on a plan, a named account, a July
book that foots, a remittance owed — did not exist anywhere, and no gate could
see that it did not, because a browser walking a screen over an empty table still
renders the screen. The counts DEF-108 measured on a freshly booted stack say it
exactly: units 10 · units with a plan **0** · unit_plan_assignments **0** ·
accounts **1** · meter_reads **0**.

HOW A FIXTURE IS DEFINED, and why it is read from the journey file:

    Every journey document carries a `**Fixture.**` paragraph — the cast, the
    dates and the named rows that journey asserts over. That paragraph is the
    specification, and this script QUOTES IT in every message it prints, so a
    seeder that drifts from what the journey asks for is visible to a reader who
    knows neither file. A seeder is registered per journey id; a journey with no
    registered seeder is REFUSED with its own Fixture paragraph printed under it.

WHAT IT WILL NEVER DO (the boundary this lane was given, verbatim in DEF-110's
row): *"the money half needs a finance artefact — an expectation row for the
ledger worked examples or a golden section — and both are finance-signed, so it
is a re-sign route rather than a lane's to add."* So this file seeds STATE and
invents no figure: every money amount it causes to exist is posted by importing
`06-backend/tests/ledger_le_fixtures.py`, which transcribes the signed LE-1
workbook line by line. If a figure a journey needs is not signed anywhere, this
file raises `NotImplementedError("OQ-###")` at that exact point rather than
choosing one.

USAGE (from 06-backend, or through boot_stack.sh which sets the environment):

    python3 ../08-qa/01-e2e/stack/seed_journey_fixture.py --journey J19
    python3 ../08-qa/01-e2e/stack/seed_journey_fixture.py --activated
    python3 ../08-qa/01-e2e/stack/seed_journey_fixture.py --check

`--check` seeds nothing. It reads the wiring index's ACTIVATED list and exits 1
naming every activated journey with no fixture — the boot-time refusal DEF-108
asks for, in a form CI can run without a database.

IDEMPOTENT. Every seeder finds what it already wrote and writes nothing twice, so
a stack can be re-booted without minting a second cohort.

NEVER PRODUCTION — same two-part guard as `seed_demo` and `seed_e2e_fixture.py`.
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "06-backend"
JOURNEY_DIR = REPO_ROOT / "08-qa" / "01-e2e" / "journeys"
INDEX_JSON = REPO_ROOT / "08-qa" / "01-e2e" / "01-journey-story-index.json"

TENANT_SUBDOMAIN = os.environ.get("E2E_TENANT", "brazosbend")

# BR-TEN-043: every business moment is a PARAMETER, never a clock read, so a
# re-boot on a different day seeds the identical world.
SEEDED_AT = datetime(2026, 8, 5, 9, 0, tzinfo=timezone.utc)

FIXTURE_RE = re.compile(r"^\*\*Fixture\.\*\*(.+?)(?=\n\n|\n\|)", re.M | re.S)


class CannotSeed(Exception):
    """This journey's fixture cannot be produced — with the reason, always."""


# ── Reading the journey's own Fixture paragraph ─────────────────────────────


def journey_file(journey_id: str) -> Path | None:
    for path in sorted(JOURNEY_DIR.glob(f"{journey_id}-*.md")):
        return path
    exact = JOURNEY_DIR / f"{journey_id}.md"
    return exact if exact.is_file() else None


def fixture_paragraph(journey_id: str) -> str:
    """The journey's own **Fixture.** paragraph, or a stated absence.

    Quoted in every message this script prints. A seeder is a claim about what a
    journey needs, and the only authority for that claim is the journey file.
    """
    path = journey_file(journey_id)
    if path is None:
        return f"(no journey file matches {journey_id} in 08-qa/01-e2e/journeys/)"
    match = FIXTURE_RE.search(path.read_text(encoding="utf-8", errors="replace"))
    if match is None:
        return f"({path.name} declares no **Fixture.** paragraph — nothing states what it needs)"
    return " ".join(match.group(1).split())


def activated_journeys() -> list[str]:
    if not INDEX_JSON.is_file():
        raise CannotSeed(
            f"{INDEX_JSON} is missing — run 10-scripts/07-e2e-wiring-index.py; without it "
            "nothing knows which journeys are activated"
        )
    return list(json.loads(INDEX_JSON.read_text(encoding="utf-8"))["activated"])


# ── Django bring-up (only when actually seeding) ────────────────────────────


def django_setup() -> None:
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    import django

    django.setup()
    from django.conf import settings

    module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
    if module.endswith("production") or not settings.DEBUG:
        raise CannotSeed(
            "refusing to run: this mints fixture rows against a fixture tenant, and "
            f"DJANGO_SETTINGS_MODULE={module!r} with DEBUG={settings.DEBUG} is not a development "
            "stack. Same rule as `manage.py seed_demo`."
        )


def tenant_and_actor():
    """The seeded owner, carrying THEIR OWN membership role — never a typed one.

    `core/permissions.require_role` reads `actor.role`, and the `User` row does
    not carry one: the role lives on `TenantMembership` (one user = one tenant =
    one role, B2 r11). A fixture that attached `role="system_admin"` by hand
    would be seeding past the guard rather than through it, so this READS the
    membership and refuses when the seeded owner does not in fact hold a role
    that may do the work. If a service refuses this actor, the refusal is real
    and belongs in the report, not routed around.
    """
    from types import SimpleNamespace

    from apps.identity import models as identity_models
    from apps.tenancy import models as tenancy_models
    from core import tenancy as core_tenancy

    tenant = tenancy_models.Tenant.objects.filter(subdomain=TENANT_SUBDOMAIN).first()
    if tenant is None:
        raise CannotSeed(
            f"no tenant `{TENANT_SUBDOMAIN}` — run `manage.py seed_demo` first "
            "(boot_stack.sh does it in order)"
        )
    # ⚠ **DEF-661: THE TWO QUERIES BELOW RUN IN TENANT CONTEXT, AND THE MESSAGES
    # SAY WHERE THEY LOOKED FROM.** `identity.users` and `identity
    # .tenant_memberships` carry `FORCE ROW LEVEL SECURITY`, so a query with no
    # `app.tenant_id` set returns ZERO ROWS — not an error, by design (CLAUDE.md
    # rule 1). This function ran outside any context, and `seed_one` opens its
    # context only AFTER calling it, so on a fully seeded stack the count was 0
    # while three users existed. Measured on a fresh database, 2026-08-24:
    # `users WITHOUT context: 0` · `users WITH context: 3`
    # (dana@brazosbendutilities.com, sam.reyes@sample.test, avery.cole@sample.test).
    # `boot_stack.sh` step 3 then exited non-zero, so Django and the SPA never
    # started, and the reason it printed sent the operator to re-run a step that
    # had already worked.
    #
    # ⚠ **AND THE MESSAGE CHANGED WITH IT (the half that matters).** An RLS
    # denial and an empty table are THE SAME OBSERVATION from inside a query, so
    # *"the tenant has no user"* is a sentence this code can never truthfully
    # say — it can only ever report what is VISIBLE FROM HERE. Running in
    # context makes the count real; the wording now names the context it ran
    # under so a future denial reads as a denial. `tenancy.tenants` is NOT
    # RLS-scoped by `app.tenant_id` (it is the table the id comes FROM), which
    # is why the lookup above sits outside and found its row all along.
    with core_tenancy.tenant_context(tenant.id):
        user = identity_models.User.objects.filter(tenant=tenant).order_by("created_at").first()
        if user is None:
            raise CannotSeed(
                f"no identity.User is VISIBLE for tenant `{TENANT_SUBDOMAIN}` ({tenant.id}) "
                f"with app.tenant_id set to {tenant.id} — so this is a genuinely empty table "
                "and not an RLS denial. `manage.py seed_demo` provisions the owner; re-run it."
            )
        membership = (
            identity_models.TenantMembership.objects.filter(tenant=tenant, user=user)
            .select_related("role")
            .first()
        )
        if membership is None:
            raise CannotSeed(
                f"no TenantMembership is VISIBLE for user {user.email} with app.tenant_id set "
                f"to {tenant.id}, so the user holds no role and every guarded service would "
                "refuse. `manage.py seed_demo` provisions the owner's membership; re-run it."
            )
        role_code = membership.role.code
    return tenant, SimpleNamespace(
        id=user.id, pk=user.id, user=user, email=user.email, role=role_code
    )


# ── J23 · the catalog cohort: units that are actually ON a plan ─────────────


def seed_j23(tenant, actor) -> list[str]:
    """*"Apt 4B, a unit taking electric + water … Residential Standard published"*.

    THE GAP THIS CLOSES IS DEF-108'S FIRST COUNT: `unit_plan_assignments` held
    **zero** rows on a fully seeded stack, so no unit was on a plan, so
    BR-MET-040 blocked every account activation and every downstream journey
    asserted over nothing. `seed_demo` publishes plans and creates units and
    never marries the two, because marrying them is a human act on S15.

    This performs that human act through the REAL service —
    `apps.metering.services.assign_unit_plan` — so the assignment lands the way
    a clerk's would: the plan column and the append-only `unit_plan_assignments`
    history row move together (BR-CUS-013 / BR-MET-041), the write is audited,
    and a plan the tenant has not PUBLISHED is refused by the service rather
    than accepted by this file.

    ⚠ IT DOES NOT PROVE THE SCREEN. DEF-114 (open at the time of writing) is
    that the S15 *Assign plan* picker is filled from `GET /rate-schedules` while
    the endpoint resolves against `rate_plans`, so every option a human can
    click is refused 422. Seeding the row makes the DOWNSTREAM journeys runnable;
    it does not make the picker work, and a green downstream run must not be read
    as evidence that a human can do this. That is stated here because a fixture
    that quietly papers over an open defect is the exact false comfort this lane
    exists to remove.
    """
    from apps.metering import models as metering_models
    from apps.metering import services as metering_services
    from apps.rating import models as rating_models

    published = [
        plan
        for plan in rating_models.RatePlan.objects.filter(tenant=tenant).order_by("code")
        if getattr(plan, "status", None) in ("published", "active")
        or getattr(plan, "published_at", None) is not None
    ]
    if not published:
        raise CannotSeed(
            "the tenant has no PUBLISHED rate plan — seed_demo publishes three; re-run it. "
            "A fixture may not publish one itself: publishing is a rating-owned act with its "
            "own rules (BR-RAT-*), and forcing the column here would seed a plan no human path "
            "produced."
        )
    # WHICH plan comes from the journey's own Fixture paragraph (*"Residential
    # Standard published"*), matched by name — not from `published[0]`, which is
    # alphabetical and put every unit on COM-SM, a water-only Small Commercial
    # plan, for a journey about a residential account. A fixture that seeds the
    # wrong plan still renders a screen and still passes, which is the class of
    # false green this whole file exists to remove.
    asked = fixture_paragraph("J23").lower()
    chosen = [plan for plan in published if plan.name and plan.name.lower() in asked]
    plan = chosen[0] if chosen else published[0]
    if not chosen:
        print(
            f"    ⚠ the journey names no plan this tenant has published; using {plan.code}. "
            "Read the fixture line above before trusting a run over this cohort."
        )

    units = list(metering_models.Unit.objects.filter(tenant=tenant).order_by("unit_no"))
    if not units:
        raise CannotSeed("the tenant has no units — seed_demo seeds six premises and ten units")

    done: list[str] = []
    already = 0
    for unit in units:
        if unit.rate_plan_id is not None:
            already += 1
            continue
        result = metering_services.assign_unit_plan(
            actor,
            str(unit.id),
            {
                # `plan_id` is the service's OWN input name — `rate_plan_id`
                # is refused VAL-001 metering.plan.tariff_required. Written
                # against the service rather than against the column.
                "plan_id": str(plan.id),
                # J23's own window: *"cycle Jun 1–30 (30 days) · change effective
                # Jun 15"*. The FIRST assignment starts at the cycle's start, so
                # the mid-cycle change the journey performs has something to
                # change FROM. The date is the journey file's, not a choice.
                "effective_from": date(2026, 6, 1).isoformat(),
                "reason": "E2E journey fixture (seed_journey_fixture.py, DEF-108)",
            },
        )
        done.append(f"{unit.unit_no or unit.id} → {result.get('plan_name', plan.code)}")

    assignments = metering_models.Unit.objects.filter(
        tenant=tenant, rate_plan_id__isnull=False
    ).count()
    return [
        f"units already on a plan ... {already}",
        f"units put on a plan ....... {len(done)}",
        f"units with a plan NOW ..... {assignments} of {len(units)}",
        f"plan ...................... {plan.code} ({plan.id})",
    ]


# ── OQ-333 · WHICH MONTH THE FIXTURE BOOK LIVES IN ──────────────────────────
#
# **CLOSED 2026-08-22 by PO ruling. Verbatim: _"Chang the month if required"_.**
# Three ways out of DEF-558 were put to the PO — give the E2E suite its own
# tenant, re-date the demo sample slice, or move the FIXTURE's month — and the
# PO took the third. It is the only one that touches no signed figure: LE-1's
# book, its 553.69 month footing, its 598.69 whole-book total and every frozen
# B5 figure stay exactly where finance signed them, and the demo tenant a person
# clicks through is unchanged. Only the BOOK DATE moves.
#
# ⚠ **`if required` is honoured literally.** The book keeps its stated JULY on
# any stack whose July is empty — a fresh test tenant, a stack booted without
# the transactional sample slice — and moves ONLY when July already holds
# entries that are not this book. The move is a repair for a collision, never a
# blanket re-dating, which is why the shift is computed per stack rather than
# baked into the figures.
#
# **THE MOVE IS +3 CALENDAR MONTHS → the fixture month is OCTOBER 2026**, with
# the book's opening cutover at Sep 30 (LE-1 dates its opening entry one day
# before the month on purpose; the shift preserves that relationship). Why three
# and not one: **August** already holds the CR-014 flat cohort's issued bill
# (service date Aug 31 — DEF-556) and **September** is where OQ-218's ruling
# parks LE-4's 500.00 accrual, so both months are spoken for. October is the
# first month nothing in this repo posts into — and it is VERIFIED EMPTY before
# a line is posted. If it is not empty, this refuses by name rather than mixing
# two books again, which is the whole failure OQ-333 was raised about.
FIXTURE_MONTH_SHIFT = 3


def _shift_month(day: date, months: int) -> date:
    """`day`, `months` calendar months later — same day-of-month, clamped.

    Clamping matters for exactly one date in the book: LE-1's opening entry sits
    on the 30th and its month-end entries on the 31st, so a shift into a 30-day
    month must not raise. Nothing else about the book is date-sensitive.
    """
    if not months:
        return day
    index = (day.month - 1) + months
    year, month = day.year + index // 12, index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _fixture_month_shift(tenant, le) -> tuple[int, str]:
    """How far this stack's LE-1 book moves, and the REASON — always both.

    Read in this order, and the order is the point:

    1. **If the book is already posted, its month is read off the book.** A
       re-boot must never re-decide the month: deciding twice would post a
       SECOND book into a different month and the trial balance would carry two
       Julys' worth of a one-July fixture. `invoice|WE-1|issued` is the posting
       key LE-1's own bill carries (hard rule 6), so it is the anchor.
    2. **Otherwise, if July is empty, the book stays in July** — OQ-333's
       *"if required"*, literally.
    3. **Otherwise July belongs to somebody else** (on a demo-seeded stack, the
       transactional sample slice's 47 invoice JEs dated Jul 2 — DEF-558) and
       the fixture's month moves, per the ruling.
    """
    from apps.ledger import models as ledger_models

    posted = ledger_models.JournalEntry.objects.filter(
        tenant=tenant, status=ledger_models.JE_POSTED
    )
    anchor = posted.filter(posting_key="invoice|WE-1|issued").first()
    if anchor is not None:
        months = (anchor.entry_date.year - le.JULY_START.year) * 12 + (
            anchor.entry_date.month - le.JULY_START.month
        )
        return months, (
            f"the LE-1 book is ALREADY posted in {anchor.entry_date:%B %Y} (WE-1 dated "
            f"{anchor.entry_date}) — the month is read off the book, never re-decided"
        )
    occupied = posted.filter(
        entry_date__gte=le.JULY_START, entry_date__lte=le.JULY_END
    ).count()
    if not occupied:
        return 0, (
            "July is EMPTY on this stack, so the book keeps the month J19 states — "
            'OQ-333\'s "if required" is literal and nothing is required here'
        )
    return FIXTURE_MONTH_SHIFT, (
        f"July already holds {occupied} posted entries that are NOT this book (the demo "
        "sample slice — DEF-558), so OQ-333's ruling moves the FIXTURE's month forward "
        f'{FIXTURE_MONTH_SHIFT} months. PO verbatim: "Chang the month if required"'
    )


class _book_dated_forward:
    """Post `tests.ledger_le_fixtures`' book N months later, figure for figure.

    Every entry that module posts is built by its own `a_request()`, so ONE seam
    carries the whole book's dates. Wrapping that seam here moves the BOOK DATE
    and nothing else: no amount is retyped, no posting key changes, no line is
    added or dropped, and the module that transcribes the ❄️ signed LE-1
    workbook is not edited at all. That is the difference between honouring
    OQ-333's ruling and quietly keeping a second copy of a signed book
    (hard-won law 5 — one source, derive the rest).

    A zero shift installs nothing, so the ordinary July path runs the untouched
    module and cannot be affected by this class existing.
    """

    def __init__(self, le, months: int):
        self._le = le
        self._months = months
        self._original = None

    def __enter__(self):
        if not self._months:
            return self
        original = self._le.a_request
        months = self._months
        default_date = self._le.JULY_END

        def dated_forward(lines, *, key, entry_date=default_date, **overrides):
            return original(
                lines, key=key, entry_date=_shift_month(entry_date, months), **overrides
            )

        self._original = original
        self._le.a_request = dated_forward
        return self

    def __exit__(self, *exc_info):
        if self._original is not None:
            self._le.a_request = self._original
            self._original = None
        return False


# ── J19 · the finance state a month-close journey needs (DEF-110) ───────────


def seed_j19(tenant, actor) -> list[str]:
    """*"closing July 2026 on Aug 5 · fixture-month trial balance = the LE-1 book"*.

    DEF-110, verbatim: the E2E fixture *"seeds ONE bill whose journal entry is
    dated 30 June, so a July trial balance answers 0 rows, 0.000000 = 0.000000 at
    every step … the month-close journey would close an EMPTY July and export
    ZERO rows — and it would pass, which is the dangerous part."*

    EVERY FIGURE BELOW COMES OUT OF `tests/ledger_le_fixtures.py`, IMPORTED.
    That module transcribes the ❄️ signed LE-1 workbook
    (04-docs/05-modules/09-ledger/08-worked-examples.md) and posts it through
    `apps.ledger.posting.post` — the sole writer of journal lines (hard rule 5).
    Nothing here retypes an amount, so this file can never disagree with the
    signed book: if the two ever diverge, the import breaks loudly instead.

    WHAT THE JOURNEY ASKS FOR AND WHAT ARRIVES — stated item by item, because the
    difference is the whole value of a fixture:

      · **a July book that foots** — ARRIVES. `post_le1_month` posts LE-1's every
        entry. The WHOLE book foots at 598.69 = 598.69 and the July WINDOW foots
        at 553.69, because LE-1's opening entry is dated at the 2026-06-30
        cutover on purpose. Both are already asserted in the ledger tests; this
        seeds the same book into a running stack so a browser reads it.
      · **an accrual** — **DOES NOT ARRIVE: OQ-218, and the reason is arithmetic.**
        LE-1's July book contains no accrual row, and the July window foots at
        **553.69**. Posting ANY accrual into July moves that total — LE-4's own
        500.00 would make it 1,053.69 — so the amount of a July fixture accrual
        is a figure no signed source states, and choosing one would silently
        restate a signed book. Seeding LE-4 in its own month (Sep 30) leaves July
        untouched but gives J19's Aug-1 epilogue nothing to reverse. Both halves
        are stated to the PO in OQ-218 rather than decided here; `_seed_accrual`
        below stubs to that boundary and names the OQ, as the prime directive
        requires. The close checklist's *"accruals posted"* item is COMPLETE
        either way — it asks whether an EARLIER period's mirror is overdue.
      · **a remittance owed** — ARRIVES as a STATE, not as a row: LE-1 books
        47.38 of 2200-series tax liability and no remittance entry, which is what
        makes the close checklist's *"remittance recorded"* item report INCOMPLETE
        — J19's WARN item, and the reason its step 1 is a confirm-with-reason
        rather than a clean close. Seeding a remittance ROW here would delete the
        very condition the journey exists to exercise.
      · **an export target with its codes** — ARRIVES. Each account carrying a
        July delta is given its `qbo_ref` (the S57 mapping page's own act), so
        LE-5's QuickBooks export has the codes it refuses to run without.
      · **a reconciled deposit batch** — ARRIVES, since 2026-08-22 (DEF-557).
        **OQ-219 was CLOSED 2026-08-16 — RECONCILED, PO verbatim: _"b"_** — and
        for six days this seeder kept reporting it as an open question and left
        the money undeposited, the exact state the PO ruled against. It now
        calls `le.reconcile_the_payment` (written for this ruling: `DR 1000
        Cash 292.87 / CR 1010 Undeposited 292.87`, the shape
        `apps/payments/ledger_seam.post_batch_reconciled` posts), so the
        fixture month renders **realised cash 442.87 / undeposited 0.00** —
        which is what J19's own Fixture line asks for (*deposit batches
        reconciled, locked per BR-PAY-004*). The trial balance is untouched at
        598.69 = 598.69; both states foot, which is why this was a choice and
        not an error. Asserted by
        `tests/test_cr014_journey_cohorts.py::test_cr014_tc4`.
    """
    sys.path.insert(0, str(BACKEND))
    from apps.customers import models as customer_models
    from apps.ledger import models as ledger_models
    from apps.ledger import reporting

    # Imported, never copied: this module carries the signed LE-1 figures.
    from tests import ledger_le_fixtures as le

    notes: list[str] = []

    # OQ-333's ruling, applied: WHICH month, and why, before anything is written.
    shift, why = _fixture_month_shift(tenant, le)
    book_start = _shift_month(le.CUTOVER, shift)
    month_start = _shift_month(le.JULY_START, shift)
    month_end = _shift_month(le.JULY_END, shift)
    notes.append(f"fixture month ............. {month_start} → {month_end} · {why}")

    acc_1042 = customer_models.Account.objects.filter(
        tenant=tenant, account_no="ACC-1042"
    ).first()
    # The window's total BEFORE this seeder writes anything. The signed-footing
    # check below is a DELTA against it, never an equality against the window —
    # see the comment where it is asserted.
    baseline = reporting.trial_balance(start=book_start, end=month_end)
    already = ledger_models.JournalEntry.objects.filter(
        tenant=tenant,
        status=ledger_models.JE_POSTED,
        entry_date__gte=month_start,
        entry_date__lte=month_end,
    ).count()
    posted_this_pass = False
    if already and acc_1042 is not None:
        notes.append(
            f"the fixture month already holds {already} posted entries and the LE cast's "
            "ACC-1042 exists — this book is already seeded; nothing re-posted"
        )
        accounts = {"ACC-1042": acc_1042}
    elif already:
        raise CannotSeed(
            f"OQ-333 / DEF-558 — the fixture month {month_start:%B %Y} already holds "
            f"{already} posted entries and the LE cast's ACC-1042 does not exist, so those "
            "entries are somebody else's book. The PO's ruling moves the FIXTURE's month "
            "onto a CLEAR one; posting LE-1 on top of a foreign month would restate a "
            "signed total, and printing ✔ over it is DEF-108's false green exactly. "
            f"Move FIXTURE_MONTH_SHIFT past {month_start:%B %Y} (it is "
            f"{FIXTURE_MONTH_SHIFT} now) and say so in this file, or clear that month."
        )
    else:
        world: dict = {}
        accounts = le.make_accounts(actor, tenant, world, service="electric")
        with _book_dated_forward(le, shift):
            le.post_le1_month(tenant, accounts)
        posted_this_pass = True
        notes.append(
            f"LE-1's book posted into {month_start:%B %Y} through apps.ledger.posting (the "
            "sole writer) — every AMOUNT is the module's signed transcription; only the "
            "book date moved (OQ-333)"
        )
        authority_accounts = le.ensure_authority_accounts(tenant, actor=actor)
        notes.append(
            f"tax authorities minted through the real service: {', '.join(sorted(authority_accounts))}"
        )

    # OQ-219 CLOSED 2026-08-16 — RECONCILED (PO: "b"). Idempotent: the posting
    # service returns created=False on a replay of the same key (rule 6). The
    # same date shift applies, or the reconciliation would land in July while
    # the payment it clears sits in the fixture month.
    with _book_dated_forward(le, shift):
        le.reconcile_the_payment(tenant, accounts)
    notes.append(
        "deposit batch DEP-0731 RECONCILED per OQ-219's ruling (2026-08-16): realised cash "
        f"{le.LE1_CASH_TOTAL} / undeposited 0.00 — DR 1000 / CR 1010 {le.LE1_PAYMENT}"
    )

    whole_book = reporting.trial_balance(start=book_start, end=month_end)
    fixture_month = reporting.trial_balance(start=month_start, end=month_end)
    notes.append(
        f"trial balance, whole book ({book_start}→{month_end}) ... "
        f"{whole_book['total_debit']} = {whole_book['total_credit']} (balanced={whole_book['balanced']}) over {len(whole_book['rows'])} rows"
    )
    notes.append(
        f"trial balance, FIXTURE-MONTH window ({month_start}→{month_end}) ... "
        f"{fixture_month['total_debit']} = {fixture_month['total_credit']} (balanced={fixture_month['balanced']}) over {len(fixture_month['rows'])} rows"
    )
    if not fixture_month["rows"]:
        raise CannotSeed(
            f"the fixture-month window ({month_start}→{month_end}) is still EMPTY after "
            "seeding — this is exactly DEF-110's state (0 rows, 0.000000 = 0.000000) and a "
            "month-close journey run against it would close an empty month and pass. "
            "Refusing to report success."
        )
    # The point of moving a MONTH rather than a FIGURE: what THIS SEEDER ADDED
    # is still LE-1's signed book, to the cent.
    #
    # ⚠ IT IS A DELTA, NOT AN EQUALITY, and the first version of this check got
    # that wrong — it compared the WINDOW's total to 598.69 and went red the
    # moment anything else lawfully shared the window. Two things routinely do:
    # `seed_e2e_fixture.py`'s one bill posts a journal entry dated 30 June,
    # which is the book's own opening cutover, and on a demo stack the sample
    # slice owns July. Neither restates LE-1 — they are simply other entries in
    # the same date range — so an equality here would refuse a perfectly honest
    # world. It was caught by this lane's own test (a re-boot where the sample
    # slice arrives AFTER the book), which is the only reason it is not in the
    # boot path now — filed as DEF-568, because it did land in a commit first.
    added = Decimal(str(whole_book["total_debit"])) - Decimal(str(baseline["total_debit"]))
    if posted_this_pass and added != Decimal(str(le.LE1_FOOTING)):
        raise CannotSeed(
            f"this pass ADDED {added} to the book window, not LE-1's signed "
            f"{le.LE1_FOOTING} (window went {baseline['total_debit']} → "
            f"{whole_book['total_debit']}). OQ-333's ruling moves the fixture's MONTH and no "
            "figure; a different delta means something other than a date changed, and this "
            "fixture may not report success over a restated book."
        )
    notes.append(
        f"signed footing HELD ....... this pass added {added if posted_this_pass else 0} "
        f"(LE-1's {le.LE1_FOOTING} when it posts) — OQ-333 moved the month, not the money"
        + ("" if posted_this_pass else "; nothing was posted on this pass, so nothing to add")
    )
    notes.append(_seed_export_codes(tenant))
    notes.extend(_close_checklist_state(month_start, month_end))
    notes.append(
        "NO in-month accrual, BY RULING — OQ-218 CLOSED 2026-08-16, option (a), PO verbatim: "
        '"no reason to disturb a signed figure to test a feature September can already test". '
        f"The fixture month keeps its signed {fixture_month['total_debit']}; LE-4's 500.00 "
        "stays where it is signed and J19's auto-reversal epilogue is asserted from that pair."
    )
    return notes


def _seed_accrual(tenant, actor, le):
    """A July accrual — RULED OUT, and kept as a refusal so nobody re-adds one.

    **OQ-218 CLOSED 2026-08-16, option (a). PO verbatim: _"(a) — no reason to
    disturb a signed figure to test a feature September can already test."_**
    The fixture month posts NO accrual: July keeps its signed **553.69**,
    LE-4's **500.00** stays where it is signed (September), and J19's Aug-1
    auto-reversal epilogue (BR-LED-005) is asserted from the September pair.
    The general rule the ruling states, worth more than this fixture: **test
    data is shaped to fit signed figures, never the other way round.**

    This function is deliberately kept (unreachable from `seed_j19`) so that a
    future lane reaching for "the fixture needs an accrual" finds the ruling
    where the temptation is, not a blank.
    """
    raise NotImplementedError(
        "OQ-218 is CLOSED (2026-08-16, option a): the E2E fixture month posts NO July "
        "accrual — posting one would move LE-1's signed July footing (553.69). LE-4's "
        "500.00 lives in September; assert the reversal epilogue from there. Re-opening "
        "this is a finance re-sign (HUMAN-GUIDE §6), not a seeder change."
    )


def _seed_export_codes(tenant) -> str:
    """LE-5's *"each carrying its qbo_ref from the mapping page"* — the S57 act.

    `apps/ledger/exports.py` refuses a QBO export atomically when any account in
    the period carries no `qbo_ref`, which is the correct refusal and exactly
    what an unseeded fixture hits. The code is derived from the account's OWN
    code (`QBO-1200` for 1200 AR) rather than invented: no mapping table anywhere
    in the signed docs states a QuickBooks account name for this tenant, so a
    made-up name would be a figure this file has no authority for, while a
    derived stable reference is plainly a fixture value and cannot be mistaken
    for a real chart mapping.
    """
    from apps.ledger import models as ledger_models

    missing = ledger_models.LedgerAccount.objects.filter(tenant=tenant, qbo_ref__isnull=True)
    count = 0
    for account in missing:
        account.qbo_ref = f"QBO-{account.code}"
        account.save(update_fields=["qbo_ref"])
        count += 1
    total = ledger_models.LedgerAccount.objects.filter(tenant=tenant).count()
    return f"export codes .............. {count} qbo_ref stamped ({total} accounts carry one)"


def _close_checklist_state(period_start: date, period_end: date) -> list[str]:
    """What the close checklist ACTUALLY says now — printed, never assumed.

    J19's fixture asks for *"runs issued ✓, deposit batches reconciled ✓, bank
    rec current ✓, accruals posted ✓, remittance recorded ✗"*. Three of those
    five are computed from registers another module owns, and
    `apps/ledger/close._seam_item` reports UNKNOWN when the read is not published
    — which counts as INCOMPLETE, deliberately, because a green tick nobody
    computed is hard-won law 1 in a checklist. So this prints the real state
    rather than claiming the journey's, and a reader can see which items a
    seeder could not reach and why.
    """
    from apps.ledger import close

    checklist = close.close_checklist(period_start=period_start, period_end=period_end)
    lines = [f"close checklist for {period_start:%B %Y} (computed, not claimed):"]
    for item in checklist["items"]:
        lines.append(f"    {item.state:<10} {item.code}")
    return lines


# ── The CR-014 shared cohorts (2026-08-22, W11 lane) ────────────────────────
#
# CR-014's own sizing note: cohorts SHARE, and the group is the unit of work.
# The flat money ride below is ONE cohort serving the largest group of
# activated journeys. It lives in `06-backend/tests/journey_cohort_fixtures.py`
# (same import seam as `tests.ledger_le_fixtures`) so pytest proves the same
# code a booted stack runs — tests/test_cr014_journey_cohorts.py, red-proved.
#
# WHY IT BILLS AUGUST WHEN MOST PARAGRAPHS SAID JULY — DEF-556: July on
# brazos-bend is the finance-signed LE-1 book (553.69), an issued bill posts
# its journal entry at its service date, and the PO's OQ-218 ruling is that
# test data never restates a signed figure. Details in the cohort module's
# docstring and the decision log (2026-08-22).


def _flat_cohort(tenant, actor):
    from tests import journey_cohort_fixtures as cohort

    result = cohort.ensure_flat_cohort(tenant, actor)
    return cohort, result


def _flat_notes(result) -> list[str]:
    return [
        f"issued bill ............... {result['invoice_no']} = {result['total']} "
        "(money-triples `flat,cycle,full`: 89.00 + 8.41)",
        f"tax lines ................. {' + '.join(result['tax_lines'])} — four authorities, "
        "never one 9.45% (US-BIL-008 §4)",
        f"due date .................. {result['due_date']} (bill date + 21 due-days)",
        f"accounts .................. {result['account_primary']} (Unit 4B, MTR-0451) · "
        f"{result['account_second']} (Unit 4D, MTR-0452)",
        "period .................... Aug 1–31 2026, service date Aug 31 — OUTSIDE the "
        "signed July window, by decision (DEF-556; OQ-218's rule)",
    ]


def seed_j2(tenant, actor) -> list[str]:
    """Read-to-cash. Fixture authored 2026-08-22 (CR-014): the flat cohort IS
    this journey's pre-state — premises→unit+plan+meter→account→committed
    read→issued bill, every hop through the module that owns it. Steps 10–11
    (pay → allocate → post) are the JOURNEY'S OWN ACTS over this state."""
    _, result = _flat_cohort(tenant, actor)
    return _flat_notes(result) + [
        "steps 10–11 (payment, allocation, posting) are the journey's acts — deliberately "
        "not pre-seeded, or the journey would assert over its own answer",
    ]


def seed_j3(tenant, actor) -> list[str]:
    """Exception handling. The flat cohort plus the tenant's validation config;
    the FLAGGED read itself is the journey's act (it imports one), so seeding
    it here would leave the journey nothing to do."""
    from apps.metering import services as metering_services

    _, result = _flat_cohort(tenant, actor)
    metering_services.ensure_read_validation_settings()
    return _flat_notes(result) + [
        "read_validation_settings .. ensured (B2 r5 #15 defaults — BR-MET-020 reads THIS)",
        "the flagged read is the journey's own import act, not fixture state",
    ]


def seed_j4(tenant, actor) -> list[str]:
    """Collections. The unpaid issued bill is the fixture; overdue-ness is the
    journey's clock (due Sep 22 — BR-TEN-043 makes evaluation dates parameters,
    so the journey evaluates past the grace boundary rather than this seeder
    back-dating a bill into the signed July window)."""
    _, result = _flat_cohort(tenant, actor)
    return _flat_notes(result) + [
        f"unpaid at issue ........... {result['total']} outstanding on "
        f"{result['account_primary']} (money-triples `flat,cycle,none`: next fee 5.00 floor)",
        "past-grace is evaluated at a journey-chosen date after the due date — never by "
        "issuing a back-dated bill (that is DEF-556's trap)",
    ]


def seed_j5(tenant, actor) -> list[str]:
    """Month-end, the original coarse pass. J19 is the detailed month-close
    over the SAME month, so this journey asserts over J19's cohort — one July,
    one book, per CR-014's own rule that cohorts share."""
    return ["(J5 asserts over J19's cohort — the LE-1 July book, seeded next)"] + seed_j19(
        tenant, actor
    )


def seed_t4_05(tenant, actor) -> list[str]:
    _, result = _flat_cohort(tenant, actor)
    return _flat_notes(result) + [
        f"fixture amendment 2026-08-22 (DEF-556): the unpaid bill is {result['invoice_no']} on "
        f"{result['account_primary']}, August period — not 'BL-2607-0142 on ACC-1042', whose "
        "July bill is the signed WE-1 247.87",
    ]


def seed_t4_13(tenant, actor) -> list[str]:
    _, result = _flat_cohort(tenant, actor)
    return _flat_notes(result) + [
        f"due-date law under test ... due {result['due_date']} = bill date 2026-09-01 + 21 "
        "cycle due-days (BR-BIL-024)",
    ]


def seed_t5_03(tenant, actor) -> list[str]:
    _, result = _flat_cohort(tenant, actor)
    return _flat_notes(result) + [
        "first financial record .... exists (the issued bill above) — the currency-lock "
        "refusal this journey walks has a real anchor",
    ]


def seed_t5_12(tenant, actor) -> list[str]:
    from tests import journey_cohort_fixtures as cohort

    _, result = _flat_cohort(tenant, actor)
    return _flat_notes(result) + [
        f"prior committed read ...... {cohort.PRIOR_READ_VALUE} kWh on MTR-0451 @ "
        f"{cohort.PRIOR_READ_DAY} (paragraph date amended 2026-08-22: 06-14 predated the "
        "meter's own T5-16 install of Jul 1; the VALUE is the load-bearing part)",
        "the −320 import row (44,890) is the journey's act — the fixture holds the prior "
        "read it computes against (BR-MET-019)",
    ]


def seed_t5_15(tenant, actor) -> list[str]:
    cohort, result = _flat_cohort(tenant, actor)
    cast = cohort.ensure_role_cast(tenant, actor)
    return _flat_notes(result) + [
        f"premises .................. {cohort.PREMISES_ADDRESS}: Unit 4B occupied by "
        f"{result['account_primary']}, Unit 4C vacant",
        f"role cast ................. billing clerk = {cast.get('billing_clerk', 'MISSING')} "
        "(the journey's 'Priya' is a persona; the ROLE is what it asserts)",
    ]


def seed_t5_16(tenant, actor) -> list[str]:
    from apps.assets import models as asset_models

    cohort, result = _flat_cohort(tenant, actor)
    retired = asset_models.Asset.objects.filter(
        tenant=tenant, asset_no=cohort.METER_RETIRED
    ).first()
    if retired is None or retired.status.code != "retired":
        raise CannotSeed(
            f"{cohort.METER_RETIRED} is not retired after the cohort seeded — the terminal "
            "state this journey imports against does not exist."
        )
    return _flat_notes(result) + [
        f"retired meter ............. {cohort.METER_RETIRED} retired {cohort.RETIRE_DATE} "
        "through the REAL retire service (US-AST-008, terminal), replaced_by MTR-0451",
        "the July import row against the retired meter is the journey's act",
    ]


def seed_t5_25(tenant, actor) -> list[str]:
    from tests import journey_cohort_fixtures as cohort

    cast = cohort.ensure_role_cast(tenant, actor)
    return [
        f"role cast ................. { {role: name for role, name in sorted(cast.items())} }",
        "current allowlist ......... the seeded default (unrestricted) — the lockout-risk "
        "refusal this journey walks is triggered by ITS OWN policy edit, not by fixture state",
    ]


def seed_t5_26(tenant, actor) -> list[str]:
    from tests import journey_cohort_fixtures as cohort

    cast = cohort.ensure_role_cast(tenant, actor)
    missing = [role for role in ("system_admin", "billing_clerk", "executive") if role not in cast]
    if missing:
        raise CannotSeed(
            f"the three-role cast is incomplete after seeding: missing {missing}. The "
            "last-admin guard this journey walks needs all three."
        )
    return [
        f"system admin .............. {cast['system_admin']} (the ONLY active one — the "
        "BR-IDN guard under test)",
        f"billing clerk ............. {cast['billing_clerk']}",
        f"executive ................. {cast['executive']}",
    ]


def seed_t7_11(tenant, actor) -> list[str]:
    _, result = _flat_cohort(tenant, actor)
    return _flat_notes(result) + [
        f"ACC-1101 .................. issued {result['total']} bill on Unit 4D (arrives)",
        "NOT SEEDED — the PRE-ASSESSED late fee: assessing one needs a bill already past "
        "grace at seed time, and every period that is past due before September lands its "
        "journal entry inside the finance-signed July window (DEF-556: 553.69 → 748.51 "
        "measured). The journey assesses the fee at its own evaluated date instead "
        "(BR-TEN-043 — business moments are parameters); its paragraph carries the dated "
        "amendment. The 5.00 floor and the 8.13 = 1.5% × 542.15 figures stay the "
        "money-triples rows they always were.",
    ]


# ── CR-014 GROUP 3 · the flat-cohort EXTENSIONS ─────────────────────────────
#
# Each of these is the shared August ride plus ONE more act, which is CR-014's
# own sizing rule ("cohorts SHARE; the group is the unit of work"). The cohort
# code lives in `06-backend/tests/journey_cohort_fixtures.py` so pytest proves
# exactly what a booted stack runs — tests/test_cr014_group3_cohorts.py.
#
# ⚠ EVERY ONE OF THEM OBEYS DEF-556: no extension issues a bill whose service
# date falls inside the finance-signed 2026-06-30 → 2026-07-31 window. Where a
# journey's paragraph asked for a July-dated bill, an already-assessed fee or an
# "overdue at seed time" balance, the seeder either moves it into August with a
# dated amendment on the paragraph or REFUSES BY NAME. It never back-dates.


def _extension(tenant, actor, builder_name: str):
    """Run one group-3 builder, translating its refusal into this file's.

    The two exception types exist for the same reason and must read the same to
    a person at a boot log: `CohortCannotSeed` names a missing artefact,
    `CannotSeed` is what `seed_one` prints under the journey's own Fixture
    paragraph. Losing the message between them would leave a refusal that says
    only "failed".
    """
    from tests import journey_cohort_fixtures as cohort

    builder = getattr(cohort, builder_name)
    try:
        return cohort, builder(tenant, actor)
    except cohort.CohortCannotSeed as exc:
        raise CannotSeed(str(exc)) from exc


def seed_t4_01(tenant, actor) -> list[str]:
    """Plan change mid-cycle. The fixture is the account ON a plan plus a
    PUBLISHED, service-compatible TARGET to change to; the change itself and
    its proration preview are the journey's own acts (steps 1–2)."""
    _, result = _flat_cohort(tenant, actor)
    cohort, plan = _extension(tenant, actor, "ensure_second_plan")
    return _flat_notes(result) + [
        f"change target ............. {plan.code} ({plan.name}), status={plan.status} — "
        "BR-RAT-030 makes only a PUBLISHED plan assignable",
        f"fixture amendment 2026-08-22 (DEF-556): the changing account is "
        f"{result['account_primary']} on the August cycle, not ACC-1042 on Jul 1–31, whose "
        "July bill is the signed WE-1 247.87. The split-group dollar values this journey "
        "asserts are engine-computed (00-e2e-design.md §5), so no signed figure moves.",
    ]


def seed_t4_02(tenant, actor) -> list[str]:
    """Plan change across category. The fixture is a HELD deposit plus BOTH
    category amounts; the change is the journey's act and its assertion is that
    the held figure does NOT move (BR-CUS-062)."""
    _, result = _flat_cohort(tenant, actor)
    _, deposits = _extension(tenant, actor, "ensure_deposit_rules")
    return _flat_notes(result) + [
        f"deposit HELD .............. {deposits['deposit_on_file']} on "
        f"{deposits['account_no']} — the figure step 2 asserts does not move",
        f"plan_deposit_rules ........ Residential {deposits['residential']} · "
        f"Small Commercial {deposits['commercial']} (both rows, or the absence is vacuous)",
    ]


def seed_t4_03(tenant, actor) -> list[str]:
    """Unit-plan override on an OCCUPIED unit, with the wrongly-priced issued
    bill its step 4 routes to the J6 correction door."""
    _, wrong = _extension(tenant, actor, "ensure_wrong_plan_cohort")
    return [
        f"occupied unit ............. {wrong['account_no']} on the WRONG plan "
        f"({wrong['wrong_plan']}); correct plan is {wrong['correct_plan']}",
        f"wrong-plan bill ........... {wrong['invoice_no']} = {wrong['invoice_total']} ISSUED "
        "— engine-computed on the commercial plan (00-e2e-design.md §5)",
        "fixture amendment 2026-08-22 (DEF-556): the wrongly-priced bill is AUGUST's, not "
        "June's — a June service date posts its journal entry inside the finance-signed "
        "LE-1 window. What the journey asserts is that an issued wrong-plan bill exists and "
        "can only be corrected through J6; the month it was issued in is not asserted.",
    ]


def seed_t4_12(tenant, actor) -> list[str]:
    """Exemption certificate expiry. The stored expiry IS the fixture —
    BR-CUS-063 CL-6 makes expired a DERIVED warning, never a stored flip."""
    _, exempt = _extension(tenant, actor, "ensure_expiring_exemption")
    return [
        f"exempt account ............ {exempt['account_no']}, cert {exempt['cert_ref']}, "
        f"expiry {exempt['expires']} (stored; the warning is computed from it)",
        f"cycle ..................... {exempt['cycle']} — and the account is proven READY, "
        "so a zero-tax bill means EXEMPT rather than 'billed nothing'",
        "fixture amendment 2026-08-22 (DEF-556): ACC-1049 → ACC-2049, the ACC-2xxx range "
        "this cohort's accounts live in; cert ref, expiry and the exemption are unchanged.",
    ]


def seed_t4_15(tenant, actor) -> list[str]:
    """Meter swap with a final read. The SWAP is the journey's act (steps 1–2);
    the fixture is the old meter, installed and READ, on an occupied unit."""
    cohort, swap = _extension(tenant, actor, "ensure_swap_pre_state")
    return [
        f"swap pre-state ............ unit {cohort.SWAP_UNIT}, account {swap['account_no']}, "
        f"meter {cohort.SWAP_METER_OLD} with a committed prior read",
        "the final read on M-2201 and the initial read on M-3407 are the journey's own "
        "acts — seeding them would leave it asserting over its own answer",
    ]


def seed_t4_16(tenant, actor) -> list[str]:
    """Sub-meter moves alone. The master group is the fixture; the MOVE is the
    journey's act, and BR-MET-043's final-read capture is what it asserts."""
    _, group = _extension(tenant, actor, "ensure_master_group")
    return [
        f"master .................... {group['master']} with children "
        f"{', '.join(group['children'])} — exactly the pair the Σ-subs arithmetic needs",
        f"mismatch tolerance ........ {group['tolerance_pct']}% (a tenant SETTING per "
        "BR-MET-025; the journey's 3% is its own sample, not a constant)",
    ]


def seed_t4_21(tenant, actor) -> list[str]:
    """Budget level override bounds. The ±30% band is computed from the LEVEL,
    so the level has to be WE-8's or the journey tests a different band."""
    _, budget = _extension(tenant, actor, "ensure_budget_band_account")
    return [
        f"budget enrolment .......... {budget['account_no']} at level {budget['level']} "
        f"— COMPUTED by budget_service.enroll from {budget['trailing_total']} of trailing "
        "actuals (WE-8), never typed into the status row",
        "fixture amendment 2026-08-22 (DEF-556): ACC-1047 → ACC-2047 (the cohort's range). "
        "The $242 level, the $2,904 trailing total and the ±30% band are the paragraph's own.",
    ]


def seed_t5_14(tenant, actor) -> list[str]:
    """Billing without a plan snapshot — a cutover DEFECT, seeded on purpose,
    and PROVED to block the run rather than merely to exist."""
    _, no_plan = _extension(tenant, actor, "ensure_no_plan_account")
    return [
        f"cutover defect ............ {no_plan['account_no']} Active on a unit with NO plan "
        "(BR-MET-040 makes this unreachable by activation — only bad legacy data)",
        f"prepare_run BLOCKS it ..... `{no_plan['blocked_reason']}` on cycle "
        f"{no_plan['cycle']} — asserted at seed time, because a journey saying 'the run "
        "surfaces it as an exception' passes over an EMPTY exception list",
    ]


def seed_t5_19(tenant, actor) -> list[str]:
    """The hand-typed bill amount. The fixture is a DRAFT run whose computed
    lines total the dataset row, plus the TAMPER code money must enter by."""
    _, draft = _extension(tenant, actor, "ensure_draft_cohort")
    return [
        f"DRAFT total ............... {draft['draft_total']} on {draft['account_no']} "
        "(money-triples `flat,cycle,full`) — pre-issue, so BR-BIL-004's 'a draft is not "
        "money' is what the journey probes",
        f"charge code ............... {draft['charge_code']} = {draft['charge_amount']} "
        "(BR-BIL-019: even theft money enters as a CONFIGURED code, never a typed amount)",
        "fixture amendment 2026-08-22 (DEF-556): the draft moves off ACC-1042/RUN-2607-A "
        "(a July run on the signed cast's account); the 97.41 computed total is unchanged.",
    ]


def seed_t7_15(tenant, actor) -> list[str]:
    """Budget parameter change. The running variance is what a settings save
    may never touch, so it has to be REAL before the journey starts."""
    _, budget = _extension(tenant, actor, "ensure_budget_params_account")
    return [
        f"budget account ............ {budget['account_no']} level {budget['level']} · "
        f"variance {budget['variance']} — PRODUCED by record_bill putting the "
        "money-triples `flat,budget` actual 97.41 against the level, never typed",
        f"parameters ................ settle_up_month {budget['settle_up_month']} · "
        f"relevel cadence {budget['relevel_cadence_months']} months · last levelled "
        f"{budget['last_leveled_at']}",
        "NOT SEEDED, and named rather than faked: the paragraph's *'April 2026 settle-up "
        "already billed (its line issued)'*. An issued settle-up line dated April 2026 sits "
        "before the LE-1 cutover (2026-06-30), so it would post a journal entry into the "
        "signed book — DEF-556 exactly. The journey's step is that changing settle_up_month "
        "does not disturb an already-issued settle-up; that assertion needs a bill this "
        "cohort cannot lawfully issue.",
    ]


# ── CR-014 ROUND 3 · the two group-3 remainders ─────────────────────────────


def seed_t4_19(tenant, actor) -> list[str]:
    """Grace calendar → business. Two ISSUED bills, one due a Monday and one
    due a Friday, plus the pre-change grace config; the mode SWITCH is the
    journey's own step 2."""
    cohort, grace = _extension(tenant, actor, "ensure_grace_pre_state")
    return [
        f"grace config BEFORE ....... {grace['grace_days']} days, mode "
        f"{grace['grace_mode']} (BR-BIL-008 defaults, written explicitly so a stack another "
        "journey has edited still starts here)",
        f"bill A .................... {grace['bill_a']} due {grace['bill_a_due']} "
        f"({grace['bill_a_weekday']})",
        f"bill B .................... {grace['bill_b']} due {grace['bill_b_due']} "
        f"({grace['bill_b_weekday']}) — the WE-15e weekday shape, which is what makes five "
        "calendar days and five business days land on different dates",
        f"fixture amendment 2026-08-22 (DEF-556): both due dates move +{grace['shift_days']} "
        "days — TEN WHOLE WEEKS, the only shift that preserves a weekday — from the "
        "paragraph's Mon Jul 20 and Fri Aug 14. A July or mid-August issue posts its journal "
        "entry inside the finance-signed LE-1 window; a one-MONTH shift would have moved "
        "Friday to a Monday and deleted the journey's subject. Neither due date is typed: "
        "both are BR-BIL-024's bill date + the cycle's 21 due-days, and the seeder refuses "
        "if the engine answers a different weekday.",
        "the mode switch, the re-read of bill A and the post-switch evaluation are the "
        "journey's own acts (steps 2–4) — seeding them would leave it asserting over its "
        "own answer",
    ]


def seed_t7_14(tenant, actor) -> list[str]:
    """Overcharge guardrail change. Three issued cycles PRODUCE the trailing
    average; a real one-time back-bill draft sits above it."""
    _, guard = _extension(tenant, actor, "ensure_guardrail_cohort")
    return [
        f"guardrail setting ......... overcharge_guardrail_pct = {guard['guardrail_pct']} "
        "(r10 #6 / BR-BIL-029, written through the real S66 settings service)",
        f"trailing average .......... {guard['trailing_average']} — PRODUCED by three issued "
        f"cycles, never typed: {' · '.join(guard['issued'])}",
        f"back-bill DRAFT ........... {guard['draft_no']} = {guard['draft_total']} over "
        f"{guard['draft_months']} ({guard['ratio']} of the trailing average — above 200%, "
        "below 350%, which is the whole point of the journey's threshold move)",
        f"sibling ................... {guard['sibling_no']} carries the identical world and "
        "is deliberately NOT drafted: T7-14 runs it AFTER the settings change, so a "
        "pre-existing draft would have performed the journey's step 4",
        "fixture amendment 2026-08-22 (DEF-576): the three ISSUED cycles are Aug/Sep/**Nov** "
        "2026 — OCTOBER IS SKIPPED, because OQ-333's applied ruling moves the LE-1 book there "
        "when July is taken, and seed_j19 verifies its destination month is EMPTY before "
        "posting. This cohort first billed October and made J19 refuse: *'the fixture month "
        "October 2026 already holds 2 posted entries … those entries are somebody else's "
        "book'* — the refusal working exactly as designed, on a collision this cohort caused. "
        "The fixture-month calendar every cohort must read before choosing a month to ISSUE "
        "in is written out in journey_cohort_fixtures.T714_CYCLE_MONTHS.",
        "fixture amendment 2026-08-22 (DEF-556): the ISSUED cycles are outside the "
        "finance-signed July window; the back-billed months are Apr–Jun 2026 "
        "and stay where a catch-up belongs, because a DRAFT posts no journal entry "
        "(BR-BIL-004) and therefore restates nothing. The 97.41 and 292.23 figures are the "
        "money-triples rows unchanged, READ from 08-qa/01-e2e/expected/money-triples.csv "
        "rather than retyped.",
        "⚠ A SECOND LIMIT THIS COHORT RAN INTO, recorded because every future fixture shares "
        "it: `meter_reads` is monthly RANGE-partitioned over a FIXED bootstrap window (24 "
        "months back, 3 ahead) that ends 2026-11-30 on this schema, and the create-ahead job "
        "that renews it needs a scheduler this product does not run. A read dated December "
        "2026 or later is `IntegrityError: no partition of relation \"meter_reads\" found for "
        "row`. No fixture may date a read past the last partition.",
        "⚠ NOT SEEDABLE, and named rather than faked: **the guardrail FLAG itself**. "
        "apps/billing/decisions.py refuses its own `overcharge` case in its own words — "
        "*'BR-BIL-029\'s guardrail compares a draft against the account\'s trailing average, "
        "which no selector computes'* — and apps/billing/release.py records that the flag "
        "*'has no store (BR-BIL-054)'*. Steps 1, 2, 4 and 5 drive a surface the product does "
        "not have. The fixture is complete; the journey is not yet runnable end to end, and "
        "a ✔ here means the DATA exists, not that the flag does.",
    ]


# ── CR-014 GROUP 4 · the SECOND-TENANT cohorts ──────────────────────────────
#
# These do NOT seed into `TENANT_SUBDOMAIN`. Each provisions its own tenant
# through `apps.tenancy.services.provision_tenant` — the same service S114
# commits, idempotent on the subdomain — and writes inside THAT tenant's
# context, because RLS is FORCE and a second tenant's rows cannot be written
# from the first tenant's context (hard rule 1, doing its job).
#
# `seed_one` wraps every seeder in brazos-bend's context; the cohort module
# switches explicitly and restores on the way out.


def seed_t4_22(tenant, actor) -> list[str]:
    """Currency set then LOCK. The fixture is a fresh tenant that can produce
    a first bill and has not — the lock is what having one CAUSES, so a
    pre-billed tenant would leave step 1 failing for a reason this journey
    never describes."""
    _, result = _extension(tenant, actor, "ensure_maple_creek_cohort")
    return [
        f"second tenant ............. {result['tenant']} ({result['tenant_id']}) provisioned "
        "through the REAL signup service — trial subscription, owner, chart, number series "
        "and enabled services are all provisioning's OUTPUT, not this file's",
        f"owner ..................... {result['owner']} (T4-22's own address; the System "
        "Admin role is what the journey asserts, the person is a persona)",
        f"currency AT START ......... {result['currency']} and SETTABLE — setting it to CAD "
        "is the journey's step 1, not fixture state",
        f"first bill ready .......... {result['account_no']} on plan {result['plan']}, cycle "
        f"{result['cycle']} — prepare_run reports it READY, so the bill that locks the "
        "currency can actually be produced",
        f"financial records ......... {result['financial_records']} — ZERO, asserted; a "
        "cohort that pre-locked the currency tests nothing",
    ]


def seed_t7_09(tenant, actor) -> list[str]:
    """Currency lifecycle → CAD lock. Same cohort as T4-22 by CR-014's own rule
    that cohorts share: one fresh tenant, one currency lifecycle."""
    cohort, result = _extension(tenant, actor, "ensure_maple_creek_cohort")
    return [
        f"second tenant ............. {result['tenant']} — *'{cohort.MAPLE_CREEK_NAME}'*, "
        "shared with T4-22 (one tenant, one currency lifecycle)",
        f"rates ..................... {result['plan']} — the Brazos Bend flat plan built by "
        "the SAME function, so the two tenants can never drift into pricing differently and "
        "the money-triples row applies here as the paragraph asks",
        f"financial records ......... {result['financial_records']} — ZERO, asserted",
        "NOT SEEDED, and named rather than faked: **Saskatchewan / America-Regina**. Signup "
        "validates `state` against a US-state lookup (`selectors.us_state_code`) with no "
        "Canadian provinces in it, so 'Saskatchewan' is refused `signup.state_unknown` — the "
        "product correctly reporting that it models US states only. The tenant carries NO "
        "state rather than a US one that would render on a bill. The CURRENCY half of this "
        "journey — the part it is named for — is fully seeded.",
    ]


def seed_t5_21(tenant, actor) -> list[str]:
    """Import 10k cap. The fixture is three FILES and a tenant to upload into;
    the 12,481 rows are rejected AT UPLOAD (BR-AST-034) and never reach the
    table, so seeding them would seed the state the product prevents."""
    _, lakeview = _extension(tenant, actor, "ensure_lakeview_cohort")
    from tests import journey_cohort_fixtures as cohort

    files = cohort.ensure_import_cap_csvs(REPO_ROOT)
    lines = [
        f"large tenant .............. {lakeview['tenant']} provisioned (water — a MUD sells "
        "water, and the service gate is real)",
        f"importer cap .............. {files['cap']} rows (BR-AST-034, read from "
        "apps.assets.services.IMPORT_ROW_CAP — never retyped here)",
        f"generated in .............. {files['directory']} (BUILT, not committed: a megabyte "
        "of derived data in git drifts from its generator within a day)",
    ]
    for name, meta in sorted(files["files"].items()):
        lines.append(f"  · {name:<24} {meta['rows']:>6,} rows · {meta['bytes']:>9,} bytes")
    lines.append(
        "the split is proved to REJOIN the whole file byte for byte — otherwise it is not "
        "*'the same content split'* and the journey's second half asserts nothing"
    )
    return lines


def seed_t5_22(tenant, actor) -> list[str]:
    """Pattern-generator 3,000 cap. 40 × 80 = 3,200 units are refused BEFORE
    one is created, so the fixture is the premises the pattern runs on — and
    it must hold no units, or the refusal would be about the wrong number."""
    _, lakeview = _extension(tenant, actor, "ensure_lakeview_cohort")
    return [
        f"tenant .................... {lakeview['tenant']}",
        f"premises .................. {lakeview['premises']} ({lakeview['premises_ref']}) — "
        f"currently {lakeview['units_on_premises']} units, which is the point: the 3,200 the "
        "pattern would create are refused before ANY is created (BR-MET-031's cap)",
        "the 40 × 80 typo, the {floor}-{seq} pattern and the corrected 8/floor are the "
        "journey's own acts on S16 — they are inputs, not fixture rows",
    ]


def seed_t4_11(tenant, actor) -> list[str]:
    """Tax-exempt mid-cycle. The fixture is ONE issued, TAXED bill; setting the
    exemption is the journey's step 1 and the next bill is its step 3."""
    _, we1 = _extension(tenant, actor, "ensure_we1_taxed_bill")
    return [
        f"issued taxed bill ......... {we1['invoice_no']} — taxable {we1['taxable']} → tax "
        f"{we1['tax']} → total {we1['total']}",
        f"authority lines ........... {' + '.join(we1['tax_lines'])} (State 13.87 · City 4.44 "
        "· County 2.22 · PUC 0.44 — step 2 quotes them one by one, so an aggregate that "
        "happens to sum right is not enough)",
        f"exempt at seed time ....... {we1['exempt_at_seed']} — setting the exemption IS "
        "step 1; a pre-exempt account would leave the journey nothing to do and step 2's "
        "'the issued bill did not move' would be vacuous",
        "fixture amendment 2026-08-22 (DEF-556): the bill is AUGUST's on ACC-2411, not "
        "July's on ACC-1042 — ACC-1042's July is the finance-signed WE-1 book itself, and "
        "an issued July bill posts its journal entry inside that window.",
        f"⚠ NOT SEEDED, and named rather than faked: **WE-1's {we1['missing_late_line']} LATE "
        "LINE**, which is why this bill is 242.87 and not 247.87. No path in this product "
        "assesses a late fee onto a bill: apps/billing/late_fee.py is a pure calculation and "
        "its own trailer says *'assess_late_fee has no production caller at all "
        "(S31.2/US-BIL-002 unbuilt)'*. Every figure T4-11 ACTUALLY asserts — 221.90, 20.97 "
        "and the four authority amounts — is present and proved.",
        "⚠ ALSO NOT WE-1'S COMPOSITION. The signed documents state WE-1's usage+base as ONE "
        "figure (221.90); this cohort produces it from one electric service (base 11.90 + "
        "2,100 kWh @ $0.10) rather than inventing a five-service, eleven-line breakdown no "
        "document states. The total, the tax and the per-authority split are WE-1's; the "
        "line composition is this fixture's own.",
    ]


# ── CR-014 GROUP 6 · the finance-period family ──────────────────────────────


def _finance_period_notes(state) -> list[str]:
    return [
        f"CLOSED period ............. {state['closed_period']} — through the real "
        f"close_period, checklist recomputed AT close and snapshotted beside the reason "
        "(BR-LED-018's WARN+CONFIRM receipt)",
        f"checklist at close ........ {state['checklist']}",
        f"export batch .............. target {state['batch_target']}, "
        f"{state['batch_debits']} = {state['batch_credits']}, batch_no "
        f"{state['batch_no']!r} ({state['batch_id']})",
        f"OPEN period ............... {state['open_period']} carrying "
        f"{state['posted_in_open_period']} posted entries — T5-08's refusal is about an OPEN "
        "period, so an empty or closed July would test nothing",
        f"LE-1 book found in ........ {state['le1_book_month']}; June is closed only AFTER "
        "the book is posted, because an entry dated into a closed period AUTO-FORWARDS "
        "(BR-TEN-038) and LE-1's own opening cutover is dated 2026-06-30 — closing first "
        "would move the finance-signed 598.69 footing",
        "fixture amendment 2026-08-22: **the batch NUMBER `EXP-2606-01` is not seeded.** "
        "`export_batches.batch_no` is allocated from the tenant's `export_batch` number "
        "series and tenancy seeds no default format for it (the model says so), so the "
        "recorded batch may carry a NULL number. The batch is real; a typed `EXP-2606-01` "
        "would be a number no series issued.",
    ]


def seed_t5_08(tenant, actor) -> list[str]:
    """Export an OPEN period → refused (BR-LED-017). The fixture is one closed
    month with a recorded batch and one open month that still moves."""
    _, state = _extension(tenant, actor, "ensure_finance_period_cohort")
    return _finance_period_notes(state) + [
        "the export ATTEMPT on the open period is the journey's own act — seeding a refusal "
        "is not possible and seeding a second batch would consume the idempotency key its "
        "step 3 tests",
    ]


def seed_t5_09(tenant, actor) -> list[str]:
    """Post into a closed period → auto-forward (BR-TEN-038). Same cohort: the
    receipt dated 2026-06-28 and received 2026-07-03 is the journey's act."""
    _, state = _extension(tenant, actor, "ensure_finance_period_cohort")
    return _finance_period_notes(state) + [
        "the mailed check (customer-dated 2026-06-28, received 2026-07-03) is the journey's "
        "own step — the fixture is the CLOSED June it lands in and the OPEN July it forwards "
        "to, and seeding the payment would leave the journey asserting over its own answer",
    ]


def seed_t6_09(tenant, actor) -> list[str]:
    """Finance role gates over the same period pair, under three roles."""
    from tests import journey_cohort_fixtures as cohort

    _, state = _extension(tenant, actor, "ensure_finance_period_cohort")
    cast = cohort.ensure_role_cast(tenant, actor)
    return _finance_period_notes(state) + [
        f"role cast ................. {cast} — Marcus = Executive · Priya = Billing Clerk · "
        "Dana = System Admin are personas; the ROLES are what the journey gates on",
        f"LE-4's accounts ........... {state['le4_accounts']} — the pair the journey posts "
        "BETWEEN (DR 1210 Unbilled AR 500.00 / CR 4100 Electric Revenue 500.00). Posting it, "
        "and finding the unbalanced 500.00/480.00 variant refused, is the journey's own act",
        "⚠ NOT SEEDED, and named rather than faked — TWO of this paragraph's items: "
        "**(1) deposit batch DEP-0642 'reconciled with one wrong match'.** A wrong match is a "
        "payment allocated to the wrong account and later found; seeding one means writing a "
        "KNOWN-BAD money row, and no rule in this repo justifies one. "
        "**(2) the remittance filing confirmation #TX-88231 and its 1.2 MB receipt PDF** — "
        "there is no document model and no upload surface anywhere in `apps/` (the same "
        "absence T5-28 is refused for), so a filing receipt has nowhere to be attached.",
    ]


def seed_t4_04(tenant, actor) -> list[str]:
    """Vacation hold mid-cycle. The fixture is the WE-12 four-service world and
    the reads the hold date cuts; setting the status, committing the interim
    read and running the cycle are the journey's own acts."""
    _, we12 = _extension(tenant, actor, "ensure_we12_world")
    return [
        f"plan ...................... {we12['plan']} over {', '.join(we12['services'])} on "
        f"{we12['account_no']} (status {we12['status_at_seed']} — step 1 moves it to "
        "Vacation hold, so an already-held account would have nothing to transition)",
        f"services enabled .......... {we12['services_turned_on'] or '(already on)'} — sewer "
        "and trash ship DISABLED from signup, and BR-MET-003 refuses a premises offering a "
        "service the tenant does not sell (VAL-005 metering.service_not_enabled)",
        f"meters .................... {we12['meters']}; the electric meter carries the THREE "
        "TOU channels (tou_on 60 · tou_mid 95 · tou_off 160 kWh) and the water meter 3.1 kgal",
        f"WE-12 lines CHECKED ....... {' · '.join(we12['checked_lines'])} → taxable "
        f"{we12['taxable']} → tax {we12['tax']} → total {we12['total']}. Every stored rate is "
        "held against the workbook line it must produce, through core.money — the strongest "
        "claim a fixture can make without performing the journey's own bill run.",
        f"hold window ............... {we12['hold_from']} → {we12['hold_to']}, interim read "
        f"{we12['interim_read_day']}",
        "fixture amendment 2026-08-22 (DEF-556): the hold moves +1 MONTH — Jul 16 → Aug 16, "
        "interim read Jul 15 → Aug 15, return Aug 10 → Sep 10 — because the journey's step 2 "
        "ISSUES a bill and a July service date posts its journal entry inside the "
        "finance-signed LE-1 window. The WE-12 figures are untouched: they are quantities "
        "and rates, and neither moved. ACC-1046 → ACC-2046, this cohort's own range.",
        "⚠ NOT SEEDED, deliberately: the HELD status and the issued 105.36 bill. Both are "
        "the journey's own steps 1 and 2; seeding either would leave T4-04 asserting over "
        "its own answer, and its step 5 invariance check (*'ending the hold never re-opens "
        "the hold-period bill'*) would compare a bill this file wrote against itself.",
    ]


def seed_t5_18(tenant, actor) -> list[str]:
    """Demand estimate attempt. The fixture is a demand-metered account with
    history on every register and NOTHING read for the cycle under test."""
    _, demand = _extension(tenant, actor, "ensure_demand_meter_cohort")
    return [
        f"account ................... {demand['account_no']} on {demand['plan']} "
        f"(demand rate {demand['demand_rate_per_kw']}/kW), cycle {demand['cycle']}",
        f"meter ..................... {demand['meter']} — registers "
        f"{' · '.join(demand['kwh_channels'])} · {demand['demand_channel']}, "
        f"{demand['history_rows']} committed history reads",
        f"the SKIPPED cycle .......... {demand['missing_period']} carries "
        f"{demand['reads_in_cycle']} reads — that absence IS the fixture, and the seeder "
        "refuses if anything has read the site, because with a read present nothing is "
        "missing and the demand refusal this journey exists to prove is never reached",
        "the demand register is committed in **kW**, never kWh (CLAUDE.md rule 3): a peak "
        "recorded as energy would price a kW charge off a kWh number, which is the one "
        "mistake a demand journey is about",
        "⚠ NOT SEEDABLE, and named rather than faked: **the paragraph's own 'required "
        "channels (BR-MET-049)'**. BR-MET-049's plan-driven completeness is NOT BUILT — "
        "apps/metering/selectors.py serves `missing: null` with its own stated reason, "
        "*'BR-MET-049 plan-driven completeness not built (US-MET-018)'*, and the API repeats "
        "it. There is nowhere to record that this plan REQUIRES the demand register, so step "
        "2 (*'completeness stays incomplete so billing is gated'*) has no surface. Steps 1, 3 "
        "and 4 are real: apps/metering/estimation.py carries "
        "`REASON_DEMAND_CHANNEL = 'demand_never_estimated'` and refuses BY NAME.",
        "fixture amendment 2026-08-22 (DEF-556): the skipped cycle is AUGUST, not July — the "
        "journey's step 5 recovery ISSUES a catch-up bill, and a July service date posts its "
        "journal entry inside the finance-signed LE-1 window. The trailing history stays in "
        "June and July, because reads are not money.",
    ]


def seed_t4_07(tenant, actor) -> list[str]:
    """Rate version published mid-history. The fixture is a version CHAIN and
    six unbilled months; back-billing them, correcting March and running April
    are the journey's own acts."""
    _, rates = _extension(tenant, actor, "ensure_rate_version_cohort")
    lines = [
        f"plan ...................... {rates['plan']} (water + sewer) on "
        f"{rates['account_no']}",
        f"unbilled months ........... {rates['unbilled_months']} at "
        f"{rates['monthly_kgal']} kgal/mo, {rates['reads']} committed reads, "
        f"{rates['issued_invoices']} invoices — WE-10's six months are UNBILLED by "
        "construction, and the seeder refuses if anything has billed them",
    ]
    for label in ("v3", "v4"):
        version = rates["versions"][label]
        lines.append(
            f"{label} ........................ {version['effective_from']} → "
            f"{version['effective_to']}: base {version['base']} + "
            f"{version['unit_price']}/kgal + sewer at {version['percent']} of water = "
            f"{version['monthly']}/mo"
        )
    lines.extend(
        [
            "the monthly figures are the WORKBOOK's, checked not copied: the stored rate "
            "times WE-10's own 6 kgal, finalized through core.money (the product's own money rule), must come back "
            "to 26.50 / 28.10 — a typo in the sixth decimal is a refusal here rather than a "
            "bill three cents wrong for six months",
            "sewer is modelled as PERCENT OF WATER (BR-RAT-015, r6.1 `percent_of_service`) "
            "because 10.60 is exactly 40% of 26.50 and 11.24 exactly 40% of 28.10 in both "
            "versions — pricing it per-kgal would reproduce the same two numbers from a rule "
            "the workbook does not describe, and would need a sewer METER that a real sewer "
            "connection does not have",
            "fixture amendment 2026-08-22: **v4 IS SEEDED, so the journey's step 1 publishes "
            "a version that already exists — a REPLAY, not a first publication.** The "
            "paragraph states v4 as fixture state (*'v4 published Apr 1'*) AND step 1 as the "
            "publishing act; both cannot be first. Seeding it keeps the paragraph's own "
            "per-version figures checkable at seed time, which seeding v3 alone would not.",
        ]
    )
    return lines


def seed_t5_04(tenant, actor) -> list[str]:
    """Cross-tenant sweep. Tenant B is a THIRD provisioned tenant carrying a
    named, issued CAD bill for the sweep to fail to reach."""
    _, ridge = _extension(tenant, actor, "ensure_maple_ridge_cohort")
    return [
        f"tenant B .................. {ridge['tenant']} ({ridge['tenant_id']}) provisioned "
        f"through the real signup service, currency {ridge['currency']} — set BEFORE the "
        "first bill, the only door BR-TEN-042 leaves open",
        f"foreign account ........... {ridge['account_no']} ({ridge['account_id']}) — "
        f"{ridge['accounts']} account(s) in tenant B",
        f"foreign bill .............. {ridge['invoice_no']} = {ridge['total']} "
        f"{ridge['currency']} ({ridge['invoice_id']}) ISSUED — the sweep needs rows that "
        "EXIST and cannot be reached; an empty tenant B would let every probe answer "
        "'not found' honestly and the journey would pass with RLS switched off",
        f"shared address ............ {ridge['shared_email']} is a user in BOTH tenants and "
        f"they are DIFFERENT rows ({ridge['user_a']} in A, {ridge['user_b']} in B) — "
        "BR-IDN-029, and step 6's whole subject",
        "fixture amendment 2026-08-22: tenant B is `maple-ridge` as this paragraph writes it "
        "and is NOT T7-09's `maple-creek`. The round-2 record read the two names as a "
        "conflict; they are two tenants. T4-22/T7-09 need ZERO financial records (the "
        "currency lock is what having one CAUSES) and this journey needs its tenant B to "
        "CARRY a bill — one tenant cannot be both, so both names stand.",
        "fixture amendment 2026-08-22 (DEF-556): tenant A's named rows are the CR-014 flat "
        "cohort's August bill on ACC-2042, not 'ACC-1042 / BL-2607-0142 / PMT-3308' — "
        "ACC-1042's July is the finance-signed WE-1 247.87. What this journey asserts about "
        "tenant A is that its OWN data is reachable and B's is not; which bill it is is not "
        "asserted.",
    ]


def seed_j1(tenant, actor) -> list[str]:
    """Tenant lands. Fixture authored 2026-08-22 (CR-014): this journey's
    cohort IS the provisioned tenant — J1 walks signup's OUTPUT, so the fixture
    verifies provisioning's contract rows exist rather than minting anything."""
    from apps.ledger import models as ledger_models
    from apps.tenancy import models as tenancy_models

    notes: list[str] = []
    chart = ledger_models.LedgerAccount.objects.filter(tenant=tenant).count()
    if chart < 13:
        raise CannotSeed(
            f"the shared chart holds {chart} accounts, fewer than J1 step 3b's 13 — "
            "provisioning did not complete; re-run seed_demo."
        )
    notes.append(f"chart of accounts ......... {chart} rows (step 3b needs the shared 13)")
    services_enabled = list(
        tenancy_models.TenantService.objects.filter(tenant=tenant).values_list(
            "service__code", flat=True
        )
    )
    if not services_enabled:
        raise CannotSeed("no tenant_services row exists — J1 step 3c has nothing to assert")
    notes.append(f"services enabled .......... {', '.join(sorted(services_enabled))} (step 3c)")
    notes.append(
        "revenue pointers .......... read `tenant_services.revenue_account`, never "
        "chart.SERVICE_REVENUE_ACCOUNTS (step 3c's own warning)"
    )
    return notes


# ── CR-014 GROUP 5 · the notification-queue cohorts ──────────────────────────


def _queue_notes(state) -> list[str]:
    return [
        f"tenant clock .............. {state['timezone']}, quiet hours "
        f"{state['quiet_hours']} (BR-NOT-009's seeded default, and both journeys' own "
        "figures) · dispatch batch size " + str(state["batch_size"]),
        f"reminder cohort ........... {state['accounts']} accounts, each with an EMAIL "
        f"contact — {state['queued_documents']} bulk reminders queued on "
        f"{' + '.join(state['channels'])}",
        f"queued rows ............... {state['rows']} ({state['addressed_rows']} addressed, "
        f"{state['unaddressed_rows']} without an address) — the COUNT is the fixture: a "
        "queue journey over a dozen rows asserts nothing about batching",
        f"held rows ................. {state['held_rows']} — and that is asserted, not "
        "assumed. `outbound_messages.held` is BR-PAY-018's PAPER SUPPRESSION (the address "
        "is known bad), NOT quiet hours: a held row is skipped by every cycle until an "
        "address verification releases it, and a WINDOW change never can. The journeys' "
        "phrase *'queued-and-held'* means status=queued outside the send window, which is "
        "what `dispatcher._within_send_window` decides at cycle time.",
        "⚠ NOT ADDRESSED, and the product is right about it: **every SMS row**. "
        "`customers.selectors.delivery_recipients_for_account` answers SMS "
        "`recipient_not_resolvable` ALWAYS, because the mobile-consent column "
        "(`accounts.sms_reminders`) is PROPOSED-SCHEMA and does not exist — *'nobody has "
        "asked this customer whether they consent to texts'*. The row count both journeys "
        "assert is exact; half of it is unaddressed by a rule, and inventing phone numbers "
        "to fix that would be seeding consent nobody gave.",
    ]


def seed_t5_23(tenant, actor) -> list[str]:
    """Quiet-hours hold. The fixture is the 340-account cohort, the tenant
    clock and the queued rows; running the cycle at 22:15 is the journey."""
    _, state = _extension(tenant, actor, "ensure_reminder_queue_cohort")
    return _queue_notes(state) + [
        f"the 22:15 firing ......... {state['fired_at_local']} TENANT time is the journey's "
        "own act — `dispatch_cycle(now=…)` takes the moment as a PARAMETER (BR-TEN-043), so "
        "the journey names it rather than the fixture back-dating anything",
    ]


def seed_t7_16(tenant, actor) -> list[str]:
    """Quiet-hours window change over T5-23's own queue — same cohort, per
    CR-014's rule that cohorts share."""
    _, state = _extension(tenant, actor, "ensure_reminder_queue_cohort")
    return _queue_notes(state) + [
        "the two window edits (23:00 and 06:30) are the journey's acts; what the fixture "
        "owes it is a queue that is genuinely WAITING — rows that are queued, unheld and "
        "addressed, so a window change is what releases them and nothing else",
        "NOT SEEDED: the paragraph's *'print rows already processed (exempt)'*. Print is not "
        "among the channels a bulk reminder queues here, and marking rows processed would "
        "mean writing a dispatch that never happened — this deployment hands off to no "
        "provider at all (`dispatcher` reports `dispatched=False` every cycle).",
    ]


def seed_t7_17(tenant, actor) -> list[str]:
    """Dispatch batch-size change. 2,000 queued email rows over a batch size
    that divides them into FOUR hand-offs."""
    _, state = _extension(tenant, actor, "ensure_dispatch_drop_cohort")
    return _queue_notes(state) + [
        f"the drop ................. {state['drop_rows']} queued EMAIL rows "
        f"({state['drop_addressed']} addressed) = {state['batches_at_seeded_size']} hand-offs "
        f"at the seeded batch size {state['batch_size']} — and the division is the fixture: "
        "the journey changes the size AFTER THE SECOND hand-off, and a drop that fits in one "
        "batch has no second hand-off to change anything after",
        "NOT SEEDED: *'transactional ESP connected'*. This deployment registers no provider — "
        "`dispatcher.dispatch_cycle` reports `dispatched=False` on every cycle and a test "
        "asserts that rather than trusting a comment. The BATCHING the journey measures is "
        "real (the claim is atomic and per-channel); the hand-off to a provider is not.",
    ]


# ── CR-014 · THE JOURNEYS THAT REFUSE BY NAME (W11 round 3, 2026-08-22) ─────
#
# ⚠ **READ THIS BEFORE ADDING A SEEDER FOR ANY OF THEM.** Each journey below
# describes a surface **the product does not have**, and each is registered so a
# booted stack prints the ABSENCE by name instead of the generic "no fixture
# seeder" — the difference between *"nobody has written this yet"* and *"there
# is nothing to write it against"*.
#
# **They are counted separately by `--check` and they are NOT counted as
# covered.** Registering a refusal that inflated the coverage figure would be
# DEF-108 wearing CR-014's own clothes: the number would go up and no journey
# would be any more runnable than before.
#
# The right resolution for each is a STORY (or the de-activation CR-014
# otherwise forbids — *"a journey for an unbuilt feature is a promise nobody
# made"*), never a fixture that manufactures the missing surface. A fixture
# that built a document store so an upload journey could pass would be the
# product's first document store, written by QA, unowned by any module.
SURFACE_ABSENT = {
    "T4-10": (
        "THE BILL TEMPLATE HAS NO LANGUAGE AXIS. This journey needs an **es-MX variant of "
        "the residential BILL template**, published, with an issued bill pinned to the `en` "
        "one. `apps/billing/templates_service.resolve_for(consumer_category, template_type, "
        "account_override_template_id)` resolves account override → category default → "
        "tenant fallback and takes no language at all, and `invoices` pins `template_id` + "
        "`template_version` with no `template_language` column. So neither half exists: the "
        "variant cannot be published and a bill cannot be pinned to a language.\n"
        "    ⚠ AND THE ROUND-2 RECORD SAID THIS TOO BROADLY — corrected here. It read *'the "
        "product has no template LANGUAGE VARIANTS'*, and NOTIFICATION templates do have "
        "one: `apps/notifications/template_models.py` carries a full `category × language` "
        "variant axis (BR-NOT-006), unique per `(tenant, code, category, language)`, with "
        "`es-MX` named in its own docstring. The absence is on the BILL document "
        "specifically, and saying so is the difference between one story and a rewrite."
    ),
    "T4-17": (
        "THE LANDLORD-AGREEMENT LINK HAS NO COLUMN — OQ-069, still open. The fixture's whole "
        "subject is a premises' landlord link (→ ACC-0009, changed Aug 12 → ACC-9001) and an "
        "EXECUTED transfer of a final bill's 135.90 remainder onto it. "
        "`apps/billing/final_bill.py` states the position in its own trailer: *'THE TRANSFER "
        "PATH CAN NEVER BE OFFERED TODAY. OQ-069's prereq — the landlord-agreement link and "
        "the master-account designation — no such link exists in this repository'*, and "
        "`customers/selectors.py` repeats it.\n"
        "    ⚠ HALF OF ROUND 2's REASON HAS EXPIRED, AND THIS IS THE OTHER HALF. Round 2 "
        "deferred this journey because the master-account surface was being built by another "
        "lane THAT DAY. It has since landed — `accounts.kind='master'`, "
        "`create_master_account`, `master_account_covering_unit` all exist. What blocks it "
        "now is not a moving surface, it is a missing column, and that is a different kind "
        "of wait: OQ-069 has to be RULED before a story can be written."
    ),
    "T4-18": (
        "NOTHING IN THIS PRODUCT ASSESSES A LATE FEE ONTO A BILL. The fixture needs a "
        "pre-change assessment already ISSUED — *'overdue $400.00 → 1.5% = $6.00 LATE line "
        "(issued)'*. `apps/billing/late_fee.py` is a pure calculation and its own trailer "
        "says so: *'`assess_late_fee` has no production caller at all (S31.2/US-BIL-002 "
        "unbuilt)'*; no run, no job and no service writes a LATE line, and "
        "`apps/billing/penalty.py` refuses its charge-code half for a related reason.\n"
        "    ⚠ THIS SUPERSEDES THE ROUND-2 REASON, WHICH WAS TOO KIND. Round 2 filed T4-18 "
        "under the DEF-556 trap — an assessment before September posts inside the signed "
        "July window — which implied a re-dating would fix it. It would not. Every other "
        "DEF-556 case in this CR was repaired by moving a month; this one needs a FEATURE, "
        "and calling it a dating problem would have sent a lane to move dates around a "
        "cohort that can never be built."
    ),
    "T5-27": (
        "THERE IS NO SANDBOX AND NO TENANT CLONE. The fixture is *'a sandboxed clone of "
        "tenant brazos-bend at a green state'* into which drift is then injected. Nothing in "
        "`apps/` defines a sandbox, a clone or a snapshot — a grep for either finds no "
        "module, no model and no service. Injecting drift into the REAL tenant is what the "
        "word *sandboxed* exists to prevent: this journey deliberately breaks a tie-out, and "
        "doing that to the demo tenant would leave every other journey asserting over a "
        "broken book."
    ),
    "T5-28": (
        "THERE IS NO DOCUMENT MODEL AND NO UPLOAD SURFACE. The fixture is four files "
        "uploaded to an account's Documents tab — an EICAR test signature, a disallowed "
        "type, a 14 MB file and a clean one. Nothing in `apps/` defines a document, an "
        "attachment or an upload endpoint, so there is nowhere for any of the four to go and "
        "no scanner, type gate or size gate for them to be refused by. The four files are "
        "trivially generatable; the thing they would be uploaded TO is the whole journey."
    ),
    "T7-07": (
        "THE PER-USER UI LANGUAGE OVERRIDE IS A COLUMN NOBODY WRITES AND NOBODY READS — "
        "hard-won law 2, exactly. `identity.models.User.ui_language` exists (r15 #4) and a "
        "repository-wide grep for `ui_language` returns TWO hits: the model field and the "
        "migration that created it. No service sets it, no selector serves it and no screen "
        "reads it, so *'Priya Nair (override → hi), Dana Kim (no override), both logged in "
        "concurrently'* cannot be established or observed.\n"
        "    The journey's other half is absent for T4-10's reason: its *'issued es-pinned "
        "bill (T7-02 fixture)'* needs a language on the BILL document, which has no language "
        "axis. `accounts.preferred_language` DOES exist and is real — that column is the one "
        "piece of this journey that has a home."
    ),
    "T7-12": (
        "SAME ABSENCE AS T4-18: nothing assesses a late fee onto a bill. This fixture needs "
        "*'account ACC-1110: penalty bill, fee 8.13 already assessed on overdue 542.15'* "
        "plus two more accounts awaiting assessment. The 8.13 is GT-8's own figure and the "
        "calculation is built and golden-verified; what does not exist is anything that "
        "CALLS it and writes the resulting line onto an invoice. A fixture that inserted a "
        "LATE line directly would be writing a money row through no service — the one thing "
        "BR-BIL-019 and hard rule 5 both forbid."
    ),
}


def _refuse_absent(journey_id: str):
    """Build the seeder for one absent-surface journey. Always raises."""

    def seeder(tenant, actor) -> list[str]:
        raise CannotSeed(
            f"{SURFACE_ABSENT[journey_id]}\n\n"
            "    This is a REFUSAL BY NAME, not an unwritten fixture. It is counted "
            "separately by --check and NOT as coverage: a ✔ here would be DEF-108 in the "
            "file written to prevent it. The resolution is a STORY for the missing surface "
            "(or the de-activation CR-014 otherwise forbids), never a fixture that "
            "manufactures it."
        )

    seeder.__name__ = f"seed_{journey_id.lower().replace('-', '_')}_absent"
    seeder.__doc__ = f"{journey_id} — refuses by name: {SURFACE_ABSENT[journey_id][:120]}…"
    return seeder


def seed_j26(tenant, actor) -> list[str]:
    """J26 — request to service. The cohort is the EIGHT `[shot]` service
    requests, planted through the product's own service path.

    ⚠ **THE NUMBERS ARE NOT THE DRAWN NUMBERS, AND NO SPEC MAY ASSERT ONE.**
    `core/sample_fixture.CR030_SERVICE_REQUESTS` draws `SR-26-0039…0048`;
    what lands is `SR-26-0001…0008`, because BR-CUS-093 numbers **at creation**
    from the tenant's own `service_request` series and seeding the drawn numbers
    would mean writing behind the allocator or burning 38 numbers on phantom
    drafts. `J26.spec.ts` asserts the ORDER, the AGE column and the
    `CR030_SR_KEY` cross-wires instead. `06-backend` pins the same fact in
    `test_the_seeded_numbers_are_allocated_not_the_drawn_ones`.

    ⚠ **AND `received_at` IS RELATIVE, WHICH IS WHY THIS SEEDER IS SAFE TO RUN
    ON ANY DAY (DEF-629).** The seeder back-dates each request to *today −
    age_days*, so the ages stay 15 · 11 · 5 · 4 · 3 · 2 · 1 · 0 whenever the
    stack is booted — and BR-CUS-106's accent (7 days, inclusive) therefore
    lands on exactly two of the eight, every time.

    Idempotent: `_seed_cr030_service_requests` skips a request whose applicant +
    `address_as_given` is already on file as a sample row, so a re-boot adds
    nothing and does not burn a second run of numbers.
    """
    from apps.customers import sample_data as customers_sample

    written = customers_sample._seed_cr030_service_requests(actor)
    from apps.customers import models as customers_models

    planted = customers_models.ServiceRequest.objects.filter(
        tenant_id=tenant.id, is_sample=True
    ).count()
    if planted < 8:
        raise CannotSeed(
            f"only {planted} of the eight [shot] service requests are on file — J26 asserts "
            "over all eight (order, AGE, and the CR030_SR_KEY cross-wires), so a partial "
            "cohort would let the spec pass over data it was not written for"
        )
    return [
        f"service_requests ......... {planted} sample rows ({written} writes this run)",
        "numbers are SR-26-0001… — the drawn SR-26-0039…0048 are NOT seeded (BR-CUS-093 "
        "numbers at creation); assert order, AGE and the cross-wires, never a literal number",
        "ages 15 · 11 · 5 · 4 · 3 · 2 · 1 · 0 days, relative to today (DEF-629) — BR-CUS-106 "
        "accents exactly two of them",
        "the six-step capture, the fee collection and the decision are the JOURNEY'S OWN acts; "
        "this seeder plants the register they are performed against",
    ]



# ── The registry ────────────────────────────────────────────────────────────

SEEDERS = {
    "J1": seed_j1,
    "J2": seed_j2,
    "J3": seed_j3,
    "J4": seed_j4,
    "J5": seed_j5,
    "J19": seed_j19,
    "J23": seed_j23,
    # CR-030 W4 task 4.16 — the eight `[shot]` service requests (BR-CUS-106 ages).
    "J26": seed_j26,
    # ── group 1 · the shared flat money ride ───────────────────────────────
    "T4-05": seed_t4_05,
    "T4-13": seed_t4_13,
    "T5-03": seed_t5_03,
    "T5-12": seed_t5_12,
    "T5-15": seed_t5_15,
    "T5-16": seed_t5_16,
    "T5-25": seed_t5_25,
    "T5-26": seed_t5_26,
    "T7-11": seed_t7_11,
    # ── group 3 · the flat-cohort extensions (CR-014, W11 lane 2026-08-22) ──
    "T4-01": seed_t4_01,
    "T4-02": seed_t4_02,
    "T4-03": seed_t4_03,
    "T4-12": seed_t4_12,
    "T4-15": seed_t4_15,
    "T4-16": seed_t4_16,
    "T4-21": seed_t4_21,
    "T5-14": seed_t5_14,
    "T5-19": seed_t5_19,
    "T7-15": seed_t7_15,
    # ── group 3 remainders + group 4 (CR-014, W11 lane round 3, 2026-08-22) ─
    "T4-19": seed_t4_19,
    "T7-14": seed_t7_14,
    "T4-04": seed_t4_04,
    "T4-07": seed_t4_07,
    "T4-11": seed_t4_11,
    "T5-18": seed_t5_18,
    # ── group 6 · the finance-period family (CR-014 round 3) ────────────────
    "T5-08": seed_t5_08,
    "T5-09": seed_t5_09,
    "T6-09": seed_t6_09,
    # ── group 5 · the notification queues (CR-014 round 3) ──────────────────
    "T5-23": seed_t5_23,
    "T7-16": seed_t7_16,
    "T7-17": seed_t7_17,
    # ── group 4 · the second-tenant cohorts (CR-014, W11 lane 2026-08-22) ───
    "T4-22": seed_t4_22,
    "T5-04": seed_t5_04,
    # ── the journeys that REFUSE BY NAME · counted apart, never as coverage ──
    **{journey_id: _refuse_absent(journey_id) for journey_id in SURFACE_ABSENT},
    "T5-21": seed_t5_21,
    "T5-22": seed_t5_22,
    "T7-09": seed_t7_09,
}


def seed_one(journey_id: str, tenant, actor) -> int:
    seeder = SEEDERS.get(journey_id)
    paragraph = fixture_paragraph(journey_id)
    print(f"\n── {journey_id} ─────────────────────────────────────────")
    print(f"  fixture asked for: {paragraph[:400]}{'…' if len(paragraph) > 400 else ''}")
    if seeder is None:
        print(
            f"\n  ✗ NO FIXTURE SEEDER for {journey_id}.\n"
            "    This journey has a spec and NO cohort to assert over. A run against this\n"
            "    stack would drive real screens over empty tables and could still report\n"
            "    green — which is DEF-108 exactly. Register a seeder in SEEDERS, or leave\n"
            "    the journey de-activated until one exists."
        )
        return 1
    from django.db import transaction

    from core import tenancy as core_tenancy

    # ⚠ **ONE SEEDER IS ONE TRANSACTION (found 2026-08-24 while fixing DEF-661,
    # and it is the failure the DEF-661 exit was HIDING).** With step 3 dying at
    # the actor lookup nothing here ever ran, so this was invisible: T5-08's
    # cohort calls `apps.ledger.exports.create_export_batch`, which takes a
    # `select_for_update` lock, and Django refuses that in autocommit —
    # `django.db.transaction.TransactionManagementError: select_for_update
    # cannot be used outside of a transaction`. It passes under pytest only
    # because pytest-django wraps every test in a transaction of its own, which
    # is exactly the difference between the suite and a booted stack.
    #
    # Wrapping the seeder rather than the one call is deliberate on two counts:
    # every service this file drives is written to be called from inside a
    # request's transaction, and a seeder that refuses half-way now leaves NO
    # partial cohort behind for the next boot to trip over.
    with core_tenancy.tenant_context(tenant.id):
        try:
            with transaction.atomic():
                notes = list(seeder(tenant, actor))
        except CannotSeed as exc:
            print(f"\n  ✗ CANNOT SEED {journey_id}: {exc}")
            return 1
        except Exception:  # noqa: BLE001 — deliberate, and the reason is below
            # ⚠ **ONE BROKEN SEEDER MUST NOT TAKE THE BOOT DOWN (2026-08-24,
            # found behind DEF-661).** A `CannotSeed` was already counted and
            # survivable; ANY OTHER exception escaped `main`, printed one
            # traceback and abandoned every journey after it — so `boot_stack.sh`
            # step 3 exited non-zero and Django and the SPA never started, which
            # is DEF-661's own symptom arriving by a second route. Measured:
            # `T5-21` raised `AttributeError: module 'apps.assets.services' has
            # no attribute 'IMPORT_ROW_CAP'` and the twenty journeys after it
            # were never attempted.
            # The traceback is PRINTED IN FULL, not swallowed: this converts a
            # crash into a NAMED failure of one journey, and it is still counted
            # in `failures`, so `--check` and a wave close refuse exactly as
            # before. Only a boot that typed `--tolerate-missing` carries on.
            import traceback

            print(
                f"\n  ✗ {journey_id}'s SEEDER CRASHED — this is a defect in the seeder, not a\n"
                "    missing fixture. It is counted as a failure; the boot continues so the\n"
                "    remaining journeys are still seeded and the stack still comes up."
            )
            traceback.print_exc()
            return 1
    for note in notes:
        print(f"  {note}")
    print(f"  ✔ {journey_id} fixture seeded")
    return 0


def check_only() -> int:
    """No database, no writes: which activated journeys have a WORKING fixture.

    ⚠ **THREE CATEGORIES, NOT TWO, AND THE THIRD IS WHY.** A journey whose
    surface the product does not have is registered in `SURFACE_ABSENT` so a
    boot prints its absence BY NAME rather than the generic "no fixture
    seeder" — but it is **not** counted as covered. Counting a refusal as
    coverage would move CR-014's own number up while leaving the journey
    exactly as unrunnable as before, which is DEF-108's shape in the file
    written to prevent it. The number this prints is the number the CR reports.
    """
    activated = activated_journeys()
    refusing = [jid for jid in activated if jid in SURFACE_ABSENT]
    missing = [jid for jid in activated if jid not in SEEDERS]
    working = [jid for jid in activated if jid in SEEDERS and jid not in SURFACE_ABSENT]
    print(f"activated journeys ........ {len(activated)}")
    print(f"with a WORKING fixture .... {len(working)}")
    print(f"refusing BY NAME .......... {len(refusing)} (the surface does not exist)")
    print(f"WITHOUT any seeder ........ {len(missing)}")
    for jid in refusing:
        first_line = SURFACE_ABSENT[jid].split("\n")[0]
        print(f"  ✗ {jid} — {first_line[:150]}")
    for jid in missing:
        print(f"  · {jid} — {fixture_paragraph(jid)[:160]}")
    if refusing:
        print(
            "\nEvery ✗ above is ACTIVATED and REFUSES: the journey describes something the\n"
            "product does not do, so no fixture can be honest about it. Each needs a STORY\n"
            "for the missing surface, or the de-activation CR-014 otherwise forbids — never\n"
            "a fixture that manufactures the surface to make a run go green."
        )
    if missing:
        print(
            "\nEvery journey above is ACTIVATED — a spec claims it — and has NO fixture, so it\n"
            "asserts over whatever `seed_demo` left behind. DEF-108: that is a green run over\n"
            "an empty cohort, which proves the buttons exist and nothing about the money."
        )
        return 1
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--journey", action="append", default=[], help="journey id, repeatable")
    parser.add_argument("--activated", action="store_true", help="every activated journey")
    parser.add_argument("--check", action="store_true", help="report coverage; seeds nothing")
    parser.add_argument(
        "--tolerate-missing",
        action="store_true",
        help=(
            "report a journey with no seeder and carry on (exit 0). For a boot that "
            "deliberately runs a partial suite; NEVER for a wave close."
        ),
    )
    args = parser.parse_args(argv)

    try:
        if args.check:
            return check_only()
        wanted = list(args.journey)
        if args.activated:
            wanted += [j for j in activated_journeys() if j not in wanted]
        if not wanted:
            parser.error("name --journey <ID>, or --activated, or --check")
        django_setup()
        tenant, actor = tenant_and_actor()
        print(f"tenant ................. {TENANT_SUBDOMAIN} ({tenant.id})")
        failures = sum(seed_one(jid, tenant, actor) for jid in wanted)
    except CannotSeed as exc:
        sys.stderr.write(f"\nseed_journey_fixture: {exc}\n")
        return 2

    if failures:
        print(f"\n{failures} journey(s) could not be seeded.")
        if args.tolerate_missing:
            print("--tolerate-missing was typed, so this exits 0. A wave close must not.")
            return 0
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-108 + DEF-110 (2026-08-15, evidence-integrity lane) · CR-014
#   (2026-08-22, W11 lane — 14 seeders added over the shared cohorts in
#   06-backend/tests/journey_cohort_fixtures.py, red-proved by
#   tests/test_cr014_journey_cohorts.py)
# generated: 2026-08-15 · AMENDED 2026-08-22 (DEF-557: OQ-218/219 closures
#   applied — the fixture month reconciles per the ruling; the stale open-
#   question notes replaced with the rulings' verbatim)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
# gates: run against a live Postgres + migrated + seed_demo'd database; output quoted in the lane report
# exceptions: J24's fixture (1,124 accounts, engine-computed aggregates, three
#   named breaks) still has NO seeder — the ROUTE blocker this trailer used to
#   cite (DEF-116) CLOSED 2026-08-16 and the run issues end-to-end now; what
#   remains is the cohort itself (1,124 accounts with the WE-1/WE-12 named
#   cast), which is CR-014's largest single group and is recorded as undone in
#   the CR's progress record, not silently approximated. J19/J5 REFUSE on a
#   demo-seeded stack naming OQ-333 (DEF-558: the demo sample's July and the
#   LE-1 book cannot share one tenant's July).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
