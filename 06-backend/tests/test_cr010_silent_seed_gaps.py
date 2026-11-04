# ── Trace ──────────────────────────────────────────────
# Change:   CR-010 item 11(b)/(c) — the seed failure-mode map's SILENT findings
#           (12-governance/16-seed-failure-modes.md §7.1, §7.3, §7.6, §7.7).
#           PO verbatim: *"what if some data does not get seed in does process
#           down the line breaks down we need to be sure; what siwll be fall
#           back"* — and the rule the map derives from it: **any object whose
#           absence fails SILENTLY is a defect by definition.**
#           Screens: S8 · S16 · S18 · S25 · S62 · S63
# Defects:  DEF-251 (read-validation settings have a seeder nothing calls) ·
#           DEF-253 (nothing renews the holiday calendar) ·
#           DEF-256 (areas seeded, attached to nothing) ·
#           DEF-257 (account sub-types seeded, attached to nothing)
# Rules:    BR-MET-020 (threshold rules skip when the config row is absent) ·
#           BR-TEN-039 (the calendar is the TENANT's — never re-seed an empty
#           one) · BR-BIL-002 (business-day grace skips holidays) ·
#           BR-MET-083 (premises carry an area) · BR-CUS-067 (the two-level
#           account sub-type tree) · BR-TEN-063 (sample seeding is idempotent)
# Tests:    this file
# Impacts:  apps/tenancy/{seams,services}.py · apps/tenancy/reference_sweep.py ·
#           apps/tenancy/management/commands/seed_demo.py ·
#           apps/metering/{services,sample_data}.py ·
#           apps/customers/sample_data.py
# ───────────────────────────────────────────────────────
"""The four silent seeding gaps, each proved from the product rather than asserted.

Every case here was RED before its fix and the failure it produced is quoted in
its own docstring, because the whole point of the failure-mode map is that these
four break **without saying so**: the suite was green over all four.

  · **DEF-251** — `ensure_read_validation_settings` documents itself as
    *"Provisioning entry point … Tenancy owns provisioning, so it calls this"*
    and the only callers in the repository were two test files. Live: **0 rows**
    for the only tenant on the system, so every threshold read-check reported
    `not_evaluated` and the single-read paths said nothing at all.
  · **DEF-253** — provisioning seeds this year and next; nothing ever renews it.
    `ensure_us_holidays_through` had no production caller, so the calendar ran to
    the end of 2027 and DEF-042's early-and-on-New-Year's-Day late fee returns in
    January 2028. ⚠ The top-up must still LEAVE AN EMPTY CALENDAR ALONE — a
    non-US tenant deleted its dates deliberately (BR-TEN-039).
  · **DEF-256 / DEF-257** — 4 areas and 12 sub-types seeded, and live:
    `premises.area_id` NULL on 50/50, `accounts.account_subtype_id` NULL on
    49/49. A Product Owner reviewing the seeded product saw a configured
    vocabulary that nothing used.
"""

from datetime import date

import pytest

from apps.tenancy import models as tenancy_models
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import tenant_ctx
from tests.test_us_met_helpers import (  # noqa: F401 — brazos/dana are fixtures
    brazos,
    dana,
    lonestar,
)

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# DEF-251 · the read-validation settings row
# ══════════════════════════════════════════════════════════════════════════


def test_def251_provisioning_writes_the_read_validation_settings_row(brazos):
    """RED BEFORE THE FIX: `assert 0 == 1` — provisioning wrote no row.

    The consequence is not a crash. `_read_config()` returns None, the engine
    skips every threshold rule and reports `not_evaluated: validation config
    missing`, and a clerk correcting a single read sees no errors and no
    explanation that no rule ran. That is the silence the map is about.
    """
    from apps.metering import models as metering_models

    with tenant_ctx(brazos):
        rows = metering_models.ReadValidationSettings.objects.filter(tenant_id=brazos.id)
        assert rows.count() == 1, (
            "provisioning must write the read-validation settings row (DEF-251) — "
            "without it every threshold read-check reports not_evaluated and the "
            "single-read paths say nothing at all"
        )


def test_def251_the_seam_is_wired_and_reports_what_it_did(brazos):
    """The repair door, and the honest report — hard-won law 4 in its data form.

    A change to provisioning never reaches a tenant that already exists, so the
    seam has to be callable a second time and has to say whether it created
    anything. RED BEFORE THE FIX: `AttributeError: module 'apps.tenancy.seams'
    has no attribute 'seed_read_validation_settings'`.
    """
    from apps.metering import models as metering_models
    from apps.tenancy import seams

    with tenant_ctx(brazos):
        # Provisioning already planted it, so a replay creates nothing —
        # neither the tenant row nor (since CR-038 A1) the per-service rows.
        assert seams.seed_read_validation_settings() == {
            "created": False,
            "service_rows_created": 0,
        }
        # Delete it the way a tenant on an older build has it — absent — and
        # prove the door repairs. The per-service rows still stand from
        # provisioning, so only the tenant row is (re)created here.
        metering_models.ReadValidationSettings.objects.filter(tenant_id=brazos.id).delete()
        assert seams.seed_read_validation_settings() == {
            "created": True,
            "service_rows_created": 0,
        }
        assert (
            metering_models.ReadValidationSettings.objects.filter(tenant_id=brazos.id).count() == 1
        )


# ══════════════════════════════════════════════════════════════════════════
# DEF-253 · nothing renews the holiday calendar
# ══════════════════════════════════════════════════════════════════════════


def test_def253_the_top_up_has_a_production_caller_and_extends_the_horizon(brazos):
    """RED BEFORE THE FIX: `AttributeError: module 'apps.tenancy.services' has
    no attribute 'top_up_holiday_calendar'`.

    `ensure_us_holidays_through` existed and was correct; nothing in the product
    called it. This asserts the CALLER, not the arithmetic — the arithmetic is
    already pinned by tests/test_us_ten_011_us_holidays.py TC-7.
    """
    from apps.tenancy.us_holidays import us_federal_holidays

    with tenant_ctx(brazos):
        rows = tenancy_models.HolidayCalendar.objects.filter(tenant=brazos)
        # Provisioning leaves the sign-up year and the next.
        this_year = tenancy_selectors.tenant_today().year
        assert rows.filter(holiday_date__year=this_year).exists()

        # Simulate the tenant that has been running for a year: the calendar
        # covers through `this_year` and stops. Nothing renewed it — that is
        # exactly the state a tenant is in on 1 January.
        rows.filter(holiday_date__gt=date(this_year, 12, 31)).delete()
        before = rows.count()

        created = tenancy_services.top_up_holiday_calendar(brazos)
        assert created == len(us_federal_holidays(this_year + 1)), (
            "the top-up must restore next year's dates — with one year seeded a "
            "bill due Thu 24 Dec charges the late fee on Mon 4 Jan, a day early "
            "and ON New Year's Day (DEF-042/DEF-253)"
        )
        assert rows.count() == before + created
        # Idempotent: the horizon is already met, so a replay writes nothing.
        assert tenancy_services.top_up_holiday_calendar(brazos) == 0


def test_def253_the_top_up_leaves_an_empty_calendar_alone(brazos):
    """⚠ THE FAILURE THIS FIX MUST NOT CAUSE.

    BR-TEN-039 makes the calendar the tenant's. A utility outside the US deletes
    every seeded date, legitimately, and an empty calendar is indistinguishable
    in the data from a brand-new one. A top-up that treated empty as "needs
    seeding" would silently re-impose US federal holidays on a tenant that
    removed them — every time the sweep ran.
    """
    with tenant_ctx(brazos):
        rows = tenancy_models.HolidayCalendar.objects.filter(tenant=brazos)
        rows.delete()
        assert tenancy_services.top_up_holiday_calendar(brazos) == 0
        assert rows.count() == 0, (
            "an empty calendar is the tenant's own choice (BR-TEN-039) and the "
            "renewal must never re-impose the US federal dates they deleted"
        )


def test_def253_the_post_migrate_sweep_tops_up_every_tenant(brazos, lonestar):
    """The sweep is the door for tenants that already exist (hard-won law 4).

    RED BEFORE THE FIX: `KeyError: 'holidays_added'` — `sweep_tenant` returned
    no such key because the sweep only ever touched reference lists.
    """
    from apps.tenancy import reference_sweep
    from apps.tenancy.us_holidays import us_federal_holidays

    this_year = None
    with tenant_ctx(brazos):
        this_year = tenancy_selectors.tenant_today().year
        tenancy_models.HolidayCalendar.objects.filter(
            tenant=brazos, holiday_date__gt=date(this_year, 12, 31)
        ).delete()

    result = reference_sweep.sweep_tenant(brazos)
    assert result["holidays_added"] == len(us_federal_holidays(this_year + 1))

    with tenant_ctx(brazos):
        assert tenancy_models.HolidayCalendar.objects.filter(
            tenant=brazos, holiday_date__year=this_year + 1
        ).exists()

    # A dry run computes and writes nothing.
    with tenant_ctx(lonestar):
        tenancy_models.HolidayCalendar.objects.filter(
            tenant=lonestar, holiday_date__gt=date(this_year, 12, 31)
        ).delete()
        before = tenancy_models.HolidayCalendar.objects.filter(tenant=lonestar).count()
    dry = reference_sweep.sweep_tenant(lonestar, dry_run=True)
    assert dry["holidays_added"] == 0
    with tenant_ctx(lonestar):
        assert tenancy_models.HolidayCalendar.objects.filter(tenant=lonestar).count() == before


# ══════════════════════════════════════════════════════════════════════════
# DEF-251 + DEF-253 · the repair door, driven end to end
# ══════════════════════════════════════════════════════════════════════════


def test_the_seed_demo_repair_door_fixes_both_on_a_tenant_that_already_exists(brazos):
    """`seed_demo --tenant <sub>` — RUN, not inspected, and its output read.

    THIS IS THE CASE THE OTHER SEVEN CANNOT COVER. Both defects are of the shape
    hard-won law 4 names: *a change to provisioning never reaches a tenant that
    already exists.* Wiring provisioning fixes nobody who has already signed up,
    and every tenant on every deployment today is exactly that tenant. So the
    repair door is driven here against a tenant put deliberately into the state
    an older build leaves — no read-validation row, and a calendar that stops at
    the end of this year — and the printed report is asserted, because a repair
    that runs silently is a repair nobody can confirm ran.

    It calls the command's own method rather than `call_command` for one reason:
    the command refuses on a non-Postgres vendor before it touches a tenant
    table (tenant context is a Postgres GUC), and that refusal is `_probe` /
    `_blockers`, not this method. Passing no blockers is what a Postgres host
    passes. Everything below the refusal is the real code path.
    """
    import io

    from apps.metering import models as metering_models
    from apps.tenancy.management.commands.seed_demo import Command
    from apps.tenancy.us_holidays import us_federal_holidays

    with tenant_ctx(brazos):
        this_year = tenancy_selectors.tenant_today().year
        # The state an older build leaves behind.
        metering_models.ReadValidationSettings.objects.filter(tenant_id=brazos.id).delete()
        tenancy_models.HolidayCalendar.objects.filter(
            tenant=brazos, holiday_date__gt=date(this_year, 12, 31)
        ).delete()

    command = Command()
    command.stdout = io.StringIO()
    command.stderr = io.StringIO()
    command._backfill_existing_tenant({}, [], brazos.subdomain, allow_empty=True)
    printed = command.stdout.getvalue()

    assert "read validation ....... row created with the ratified defaults" in printed
    assert (
        f"holiday calendar ...... {len(us_federal_holidays(this_year + 1))} date(s) added"
        in printed
    )
    with tenant_ctx(brazos):
        assert (
            metering_models.ReadValidationSettings.objects.filter(tenant_id=brazos.id).count() == 1
        )
        assert tenancy_models.HolidayCalendar.objects.filter(
            tenant=brazos, holiday_date__year=this_year + 1
        ).exists()

    # A REPLAY CLAIMS NOTHING. The DEF-153/7.2 failure shape is a panel that
    # reports work it did not do, so the second run must say so in as many words.
    command.stdout = io.StringIO()
    command._backfill_existing_tenant({}, [], brazos.subdomain, allow_empty=True)
    replayed = command.stdout.getvalue()
    assert "read validation ....... already present — not overwritten" in replayed
    assert "holiday calendar ...... already covers this year and next" in replayed


# ══════════════════════════════════════════════════════════════════════════
# DEF-256 / DEF-257 · the vocabularies attached to nothing
# ══════════════════════════════════════════════════════════════════════════


def _seed_sample_premises(brazos, dana):
    """The two sample blocks these two defects live in, in the orchestrator's
    own order (`apps.tenancy.sample_data.SAMPLE_MODULES`): rating first,
    because BR-MET-040 refuses to ACTIVATE an account on a unit that carries no
    rate plan, then metering's premises/units/service points.
    """
    from apps.metering import sample_data as metering_sample
    from apps.rating import sample_data as rating_sample

    with tenant_ctx(brazos):
        rating_sample.seed_sample_records(dana)
        metering_sample.seed_sample_records(dana)


def test_def256_every_sample_premises_lands_in_a_seeded_area(brazos, dana):
    """RED BEFORE THE FIX: `assert 44 == 0` — every sample premises had
    `area_id` NULL, on a tenant that had just been seeded four districts.

    Live confirmation before the fix: `select count(*) from premises where
    area_id is null` returned **50 of 50**. The Settings card showed four
    districts and every premises row on the demo utility read "—".
    """
    from apps.metering import models as metering_models

    _seed_sample_premises(brazos, dana)
    with tenant_ctx(brazos):
        premises = metering_models.Premises.objects.filter(tenant_id=brazos.id)
        assert premises.count() > 0, "no sample premises were planted at all"
        assert premises.filter(area__isnull=True).count() == 0, (
            "every sample premises must land in one of the seeded areas (DEF-256) "
            "— an area vocabulary nothing points at looks configured and is not"
        )
        used = set(premises.values_list("area__code", flat=True).distinct())
        seeded = set(
            tenancy_models.Area.objects.filter(tenant_id=brazos.id).values_list("code", flat=True)
        )
        assert used <= seeded
        assert (
            len(used) >= 3
        ), f"the demo must exercise more than one district; it used {sorted(used)}"


def test_def256_the_area_assignment_is_idempotent(brazos, dana):
    """BR-TEN-063 — a replay writes nothing and moves nothing."""
    from apps.metering import models as metering_models

    _seed_sample_premises(brazos, dana)
    with tenant_ctx(brazos):
        before = dict(
            metering_models.Premises.objects.filter(tenant_id=brazos.id).values_list(
                "address_line", "area__code"
            )
        )
    _seed_sample_premises(brazos, dana)
    with tenant_ctx(brazos):
        after = dict(
            metering_models.Premises.objects.filter(tenant_id=brazos.id).values_list(
                "address_line", "area__code"
            )
        )
    assert before == after


def test_def257_every_sample_account_carries_a_sub_type(brazos, dana):
    """RED BEFORE THE FIX: `assert 48 == 0` — the two-level tree the PO asked
    for in CR-010 existed as data and the demo utility did not demonstrate it.

    Live confirmation before the fix: `accounts.account_subtype_id` was NULL on
    **49 of 49** sample accounts.
    """
    from apps.customers import models as customers_models
    from apps.customers import sample_data as customers_sample

    _seed_sample_premises(brazos, dana)
    with tenant_ctx(brazos):
        customers_sample.seed_sample_records(dana)
        accounts = customers_models.Account.objects.filter(tenant_id=brazos.id)
        assert accounts.count() > 0, "no sample accounts were planted at all"
        assert accounts.filter(account_subtype__isnull=True).count() == 0, (
            "every sample account must carry a sub-type (DEF-257) — the two-level "
            "tree the PO ratified is invisible on a demo that never uses it"
        )
        # The sub-type must sit under the account's OWN type: a residential
        # account under `small_commercial` would be worse than a NULL.
        for account in accounts.select_related("account_type", "account_subtype"):
            assert account.account_subtype.account_type_id == account.account_type_id, (
                f"{account.account_no}: sub-type "
                f"{account.account_subtype.code} is not a child of "
                f"{account.account_type.code}"
            )
        used = set(accounts.values_list("account_subtype__code", flat=True).distinct())
        assert len(used) >= 2, f"the demo must exercise more than one sub-type; used {used}"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-010 item 11(b)/(c) — 12-governance/16-seed-failure-modes.md §7.1,
#         §7.3, §7.6, §7.7, measured 2026-08-18 against build 2.19.0, seed
#         fixture V2.18.0.0 and the running `sbh_e2e` database
# generated: 2026-08-18 by the CR-010 silent-seed-gaps lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — none of these four is an
#            endpoint; all four are what PROVISIONING and the SAMPLE PLANT
#            write) E=deferred(no-frontend-half, same reason; the on-screen
#            half of CR-010 item 11(a) is measured and reported, not built —
#            07-frontend/** is another lane's territory this session)
#            F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff check✔ · black --target-version py311✔ · pytest this file: 9
#        passed (RED first: 7 failed / 1 passed on the untouched tree, and the
#        1 that passed was the idempotence case, which passes vacuously while
#        every premises has a NULL area — it discriminates only after the fix.
#        The ninth case, the `seed_demo --tenant` repair door, was added after
#        the fix and RED-PROVED by disabling the DEF-251 call: it fails with
#        `assert 'read validation ....... row created with the ratified
#        defaults' in "…"`)
#        · related suites re-run with no regression: test_us_ten_011_us_holidays
#        · test_us_ten_020_sweep · test_us_ten_019_sample_data ·
#        test_us_ten_019_sample_records · test_cr010_subtypes_unit_types ·
#        test_seed_demo · test_br_met_083_cascade ·
#        test_def225_route_activation_cascade = 137 passed / 4 skipped
#        · run_gates 17 PASS / 10 FAIL, and all ten FAIL identically on a
#        pristine `git worktree` of HEAD — enumerated, not assumed; G20 rose
#        143→145 declared seam contracts and 126→128 resolving, which is the
#        new read-validation seam being wired rather than merely documented
# exceptions: DEF-252 (the panel reports success over work it did not do),
#             DEF-254 (tax rates — money, the PO owes the figures), DEF-255
#             (four lists with no consuming column — a product decision, not a
#             seeder), DEF-258 (the rule matrix needs a story) and DEF-259 (the
#             ROUTE half of DEF-256 — routes still carry no area and no
#             service) are all DELIBERATELY out of this lane and stay open.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
