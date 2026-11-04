# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-010 (effective-dated versioning & the single rate update,
#           7-year reproducibility) · US-RAT-011 (bulk rate update —
#           rate_change_batches + per-entity log, reason required)
# Rules:    BR-RAT-007 (reprice on the SERVICE date) · BR-RAT-017 (7-year
#           reproducibility) · BR-RAT-025 (D9 single AND bulk) · BR-RAT-037
#           (new version + append-only log row, reason required, never edited
#           in place) · BR-RAT-040 (one atomic all-or-none batch, never re-run)
# Note:     the 202 contract needs a job store — the /jobs table lane owns the
#           real one, so these tests register the BE-07 duck-typed fake and run
#           the job through the kernel harness (same code path as a worker).
# ───────────────────────────────────────────────────────
"""US-RAT-010 / US-RAT-011 — versioning, the single update and bulk batches."""

from datetime import date
from decimal import Decimal

import pytest

from apps.rating import api, models, selectors, services
from core import errors
from core.pagination import ListParams

from tests.isolation_helpers import (  # noqa: F401 — fixtures resolved by name
    assert_denied_without_context,
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import (
    RES_ELECTRIC_TIERS,
    RES_WATER_TIERS,
    FakeUser,
    api_call,
    audit_actions,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

SEPT_TIERS = [
    {"from_qty": "0", "to_qty": "4", "unit_price": "3.45"},
    {"from_qty": "4", "to_qty": "10", "unit_price": "4.80"},
    {"from_qty": "10", "to_qty": None, "unit_price": "7.20"},
]


def _params(**kwargs):
    return ListParams(**{"sort": "changed_at", "dir": "desc", **kwargs})


def _new_version(env, tariff_id, effective_from, tiers, reason="TWDB pass-through 2026"):
    with tenant_ctx(env.tenant):
        return services.create_rate_schedule_version(
            env.admin,
            tariff_id,
            {
                "model": "tiered",
                "uom": "kgal",
                "effective_from": effective_from,
                "reason": reason,
                "structure": {"tiers": tiers},
            },
        )


# ── US-RAT-010 — effective-dated versioning & the single update ─────────────
def test_us_rat_010_tc1__new_version_closes_the_old_window_and_logs_the_change(env, audit_rows):
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    audit_rows.clear()
    _new_version(env, water["id"], "2026-09-01", SEPT_TIERS)
    with tenant_ctx(env.tenant):
        versions = selectors.tariff_versions(models.Tariff.objects.get(pk=water["id"]))
        log = models.RateChangeLog.objects.get(entity_id=water["id"])
    assert [
        (
            version.effective_from.isoformat(),
            version.effective_to and version.effective_to.isoformat(),
        )
        for version in versions
    ] == [("2026-08-01", "2026-08-31"), ("2026-09-01", None)]
    assert log.reason == "TWDB pass-through 2026" and log.actor_id == env.owner.id
    assert log.before["structure"]["tiers"][0]["unit_price"] == "3.200000"
    assert log.after["structure"]["tiers"][0]["unit_price"] == "3.450000"
    assert "tariff.version_created" in audit_actions(audit_rows)


def test_us_rat_010_tc2__an_august_service_date_still_prices_on_the_august_version(env):
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    _new_version(env, water["id"], "2026-09-01", SEPT_TIERS)
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=water["id"])
        august = selectors.in_force_version(tariff, date(2026, 8, 15))
        september = selectors.in_force_version(tariff, date(2026, 9, 15))
        august_tier = models.RateTier.objects.filter(tariff_version=august).order_by("seq").first()
    assert august.effective_from.isoformat() == "2026-08-01"  # BR-RAT-007
    assert september.effective_from.isoformat() == "2026-09-01"
    assert august_tier.unit_price == Decimal("3.200000")


def test_us_rat_010_tc3__history_row_carries_entity_reason_actor_and_no_batch(env):
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    _new_version(env, water["id"], "2026-09-01", SEPT_TIERS)
    with tenant_ctx(env.tenant):
        rows = selectors.history_list(_params())
    assert len(rows) == 1
    row = rows[0]
    assert (row["entity_type"], row["entity_name"]) == ("schedule", "Res Water · Inclining")
    assert row["reason"] == "TWDB pass-through 2026"
    assert row["actor_user_id"] == str(env.owner.id) and row["batch_id"] is None


def test_us_rat_010_tc4__a_seven_year_old_version_stays_resolvable(env):
    water = env.tiered_schedule(
        "Res Water · Inclining", "water", RES_WATER_TIERS, effective_from="2019-08-01"
    )
    _new_version(env, water["id"], "2026-08-01", SEPT_TIERS, reason="2026 rebase")
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=water["id"])
        archived = selectors.in_force_version(tariff, date(2019, 8, 15))
        structure = selectors.version_structure(archived)
    assert archived.effective_from.isoformat() == "2019-08-01"  # BR-RAT-017: nothing purged
    assert [tier["unit_price"] for tier in structure["tiers"]] == [
        "3.200000",
        "4.800000",
        "7.200000",
    ]


def test_us_rat_010_tc5__an_overlapping_window_is_refused(env):
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    _new_version(env, water["id"], "2026-09-01", SEPT_TIERS)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.BizError) as excinfo:
            services.create_rate_schedule_version(
                env.admin,
                water["id"],
                {
                    "model": "tiered",
                    "uom": "kgal",
                    "effective_from": "2026-08-15",  # inside the closed August window
                    "reason": "backdated",
                    "structure": {"tiers": SEPT_TIERS},
                },
            )
        assert models.TariffVersion.objects.filter(tariff_id=water["id"]).count() == 2
    assert excinfo.value.code == errors.BIZ_WINDOW
    assert excinfo.value.message_key == "rating.schedules.window_overlap"


def test_us_rat_010_tc6__a_blank_reason_writes_nothing(env):
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_rate_schedule_version(
                env.admin,
                water["id"],
                {
                    "model": "tiered",
                    "uom": "kgal",
                    "effective_from": "2026-09-01",
                    "structure": {"tiers": SEPT_TIERS},
                },
            )
        assert models.TariffVersion.objects.filter(tariff_id=water["id"]).count() == 1
        assert models.RateChangeLog.objects.count() == 0
    assert excinfo.value.code == errors.VAL_REQUIRED


def test_us_rat_010_tc7__editing_a_version_in_place_is_refused_and_the_attempt_is_audited(
    env, audit_rows
):
    """US-RAT-010 TC-7 — **AMENDED 2026-09-17 (DEF-RAT-6447), AND ITS SUBSTANCE
    IS UNCHANGED.**

    ⚠ **WHAT THIS ASSERTED UNTIL TODAY, AND WHY IT MOVED.** It posted a
    DATELESS `{"structure": …}` and required `409 BIZ_IMMUTABLE`, which froze a
    guard that asked `latest_version(tariff) is not None` — *has anything on
    this schedule ever gone live* — where BR-RAT-037 asks *is the row being
    written one that has been IN FORCE*. A dateless row has not: `in_force_version`
    excludes it by name. So the refusal also swallowed the only way a clerk
    could park an unfinished edit on a live rate, which the PO reported as a
    deadlock in the beta.

    **BR-RAT-037 IS NOT WEAKENED AND THIS CASE STILL PROVES IT.** The rule's
    words are *"in-force … versions are never edited in place"*, and the
    assertion that carries that meaning — the live tier is still `3.200000` —
    is here, unchanged, below. What moved is the mechanism: a dateless post now
    parks a draft (asserted in full by `tests/test_def_rat_5680_park_a_draft.py`,
    including that the in-force row is byte-identical afterwards), and a post
    carrying a DATE — the only content write that can reach an activated
    version — is still refused with the same code and still audited under
    BR-AUD-018.
    """
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    audit_rows.clear()
    response = api_call(
        api.rate_schedule_item,
        "patch",
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
        data={"structure": {"tiers": SEPT_TIERS}, "effective_from": "2026-09-01"},
        tariff_id=water["id"],
    )
    assert response.status_code == 409  # BR-RAT-037 — corrections are new versions
    assert response.data["code"] == errors.BIZ_IMMUTABLE
    assert "security.attempt_refused" in audit_actions(audit_rows)  # BR-AUD-018
    with tenant_ctx(env.tenant):
        tier = models.RateTier.objects.order_by("seq").first()
    assert tier.unit_price == Decimal("3.200000")
    # The dateless form is now a PARKED DRAFT and the live rate still does not
    # move — the half of this TC that was ever about BR-RAT-037.
    audit_rows.clear()
    parked = api_call(
        api.rate_schedule_item,
        "patch",
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
        data={"model": "tiered", "uom": "kgal", "structure": {"tiers": SEPT_TIERS}},
        tariff_id=water["id"],
    )
    assert parked.status_code == 200, parked.data
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=water["id"])
        live = selectors.latest_version(tariff)
        assert (
            models.RateTier.objects.filter(tariff_version=live).order_by("seq").first().unit_price
            == Decimal("3.200000")
        )
        assert selectors.draft_version(tariff) is not None


def test_us_rat_010_tc8__version_chains_are_tenant_scoped(env, other_env):
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    _new_version(env, water["id"], "2026-09-01", SEPT_TIERS)
    other = other_env.flat_schedule("Co-op Water Flat", "water", "3.10")
    with tenant_ctx(other_env.tenant):
        services.create_rate_schedule_version(
            other_env.admin,
            other["id"],
            {
                "model": "flat",
                "uom": "kgal",
                "effective_from": "2026-10-01",
                "reason": "co-op board 2026-3",
                "structure": {"unit_price": "3.25"},
            },
        )
        rows = selectors.history_list(_params())
    assert [row["entity_name"] for row in rows] == ["Co-op Water Flat"]


VERSION_TABLES = ("tariffs", "tariff_versions", "rate_tiers", "rate_change_log")


@pytest.mark.isolation
@requires_postgres
def test_us_rat_010_tc8_rls__version_chains_are_rls_scoped(env, other_env, rls):  # noqa: F811
    """US-RAT-010 TC-8 at the DATABASE, app-layer filter out of the path.

    BR-RAT-017 makes this chain the 7-year reproducibility record: every
    superseded price a utility ever charged. The whole chain is asserted, not
    just the head row — `tariff_versions` and `rate_tiers` carry the money, and
    a version row leaking without its tariff is still a leaked price.
    """
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    _new_version(env, water["id"], "2026-09-01", SEPT_TIERS)

    other = other_env.flat_schedule("Co-op Water Flat", "water", "3.10")
    with tenant_ctx(other_env.tenant):
        services.create_rate_schedule_version(
            other_env.admin,
            other["id"],
            {
                "model": "flat",
                "uom": "kgal",
                "effective_from": "2026-10-01",
                "reason": "co-op board 2026-3",
                "structure": {"unit_price": "3.25"},
            },
        )

    for table in VERSION_TABLES:
        assert_rls_scoped(rls, table, owner=env.tenant, intruder=other_env.tenant)
    with live_tenant_context(other_env.tenant.id):
        assert rls.count("tariffs", "id = %s", [str(water["id"])]) == 0
        prices = {str(row[0]) for row in rls.rows("SELECT unit_price FROM rate_tiers")}
    leaked = prices & {tier["unit_price"] + "0000" for tier in SEPT_TIERS}
    assert not leaked, f"LEAK — the intruder read another tenant's tier prices {leaked}"
    assert_no_foreign_rows_anywhere(rls, other_env.tenant, VERSION_TABLES)
    assert_denied_without_context(rls, *VERSION_TABLES)


# ── US-RAT-011 — bulk rate update ───────────────────────────────────────────
def _bulk_seed(env):
    electric = env.tiered_schedule("Res Electric · Tiered", "electric", RES_ELECTRIC_TIERS)
    water = env.tiered_schedule("Res Water · Inclining", "water", SEPT_TIERS)
    commercial = env.flat_schedule("Comm Water · Flat", "water", "2.90")
    return [electric, water, commercial]


def _batch_payload(schedules, **overrides):
    payload = {
        "entities": [{"type": "schedule", "id": schedule["id"]} for schedule in schedules],
        "change": {"kind": "percent", "value": "3.0"},
        "effective_from": "2027-01-01",
        "reason": "Board order 2026-12 annual adjustment",
    }
    payload.update(overrides)
    return payload


def _run_batch(env, payload):
    """Enqueue in the request's context, then run the job the way a worker
    does — core.jobs.run_job re-enters the tenant context from the record and
    CLEARS it on exit (BE-01 contract), so the job never runs nested inside a
    caller's context."""
    with tenant_ctx(env.tenant):
        accepted = services.request_rate_change_batch(env.admin, payload)
    services.run_rate_change_job(accepted["job_id"])
    return accepted


def test_us_rat_011_tc1__one_batch_three_logs_three_versions(env, job_store, audit_rows):
    schedules = _bulk_seed(env)
    audit_rows.clear()
    accepted = _run_batch(env, _batch_payload(schedules))
    with tenant_ctx(env.tenant):
        batch = models.RateChangeBatch.objects.get()
        logs = models.RateChangeLog.objects.filter(batch=batch)
        prices = {}
        for schedule in schedules:
            tariff = models.Tariff.objects.get(pk=schedule["id"])
            version = selectors.in_force_version(tariff, date(2027, 1, 15))
            prices[tariff.name] = (
                models.RateTier.objects.filter(tariff_version=version).order_by("seq").first()
            ).unit_price
    assert accepted["status_url"].startswith("/api/jobs/")
    assert logs.count() == 3 and batch.reason == "Board order 2026-12 annual adjustment"
    assert prices["Res Electric · Tiered"] == Decimal("0.113300")  # 0.11 × 1.03
    assert prices["Res Water · Inclining"] == Decimal("3.553500")  # 3.45 × 1.03
    assert prices["Comm Water · Flat"] == Decimal("2.987000")  # 2.90 × 1.03
    assert "rating.bulk_rate_update" in audit_actions(audit_rows)


def test_us_rat_011_tc2__history_filters_to_the_batch(env, job_store):
    schedules = _bulk_seed(env)
    _run_batch(env, _batch_payload(schedules))
    with tenant_ctx(env.tenant):
        batch = models.RateChangeBatch.objects.get()
        rows = selectors.history_list(_params(filters={"batch": str(batch.id)}))
    assert len(rows) == 3
    assert {row["reason"] for row in rows} == {"Board order 2026-12 annual adjustment"}
    assert {row["batch_id"] for row in rows} == {str(batch.id)}


def test_us_rat_011_tc3__a_2026_service_date_still_prices_on_the_pre_batch_version(env, job_store):
    schedules = _bulk_seed(env)
    _run_batch(env, _batch_payload(schedules))
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=schedules[0]["id"])
        version = selectors.in_force_version(tariff, date(2026, 8, 15))
        tier = models.RateTier.objects.filter(tariff_version=version).order_by("seq").first()
    assert tier.unit_price == Decimal("0.110000")  # BR-RAT-007 untouched by the batch


def test_us_rat_011_tc4__a_blank_reason_creates_no_batch(env, job_store):
    schedules = _bulk_seed(env)
    payload = _batch_payload(schedules)
    payload.pop("reason")
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.request_rate_change_batch(env.admin, payload)
        assert models.RateChangeBatch.objects.count() == 0
        assert models.TariffVersion.objects.count() == 3
    assert excinfo.value.code == errors.VAL_REQUIRED


def test_us_rat_011_tc5__a_conflicting_entity_aborts_the_whole_batch(env, job_store):
    schedules = _bulk_seed(env)
    _new_version(env, schedules[1]["id"], "2027-06-01", SEPT_TIERS, reason="pending change")
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.BizError) as excinfo:
            services.request_rate_change_batch(env.admin, _batch_payload(schedules))
        assert models.RateChangeBatch.objects.count() == 0  # zero partial writes
        assert models.TariffVersion.objects.count() == 4  # the 3 seeds + the pending one
    assert excinfo.value.code == errors.BIZ_WINDOW
    assert excinfo.value.params["entity"] == "Res Water · Inclining"


def test_us_rat_011_tc6__a_replayed_batch_is_refused_and_a_double_click_folds(env, job_store):
    schedules = _bulk_seed(env)
    payload = _batch_payload(schedules)
    with tenant_ctx(env.tenant):
        first = services.request_rate_change_batch(env.admin, payload)
        second = services.request_rate_change_batch(env.admin, payload)
        assert first["job_id"] == second["job_id"]  # NFR-16: one scope, one job
    services.run_rate_change_job(first["job_id"])
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.BizError) as excinfo:
            services.request_rate_change_batch(env.admin, payload)
        assert models.RateChangeBatch.objects.count() == 1
    assert excinfo.value.code == errors.BIZ_IDEMPOTENT  # BR-RAT-040: never re-run


def test_us_rat_011_tc7__a_clerk_cannot_run_a_bulk_update(env, job_store):
    schedules = _bulk_seed(env)
    response = api_call(
        api.rate_changes,
        "post",
        user=FakeUser(env.owner.id),
        role="billing_clerk",
        tenant=env.tenant,
        data=_batch_payload(schedules),
    )
    assert response.status_code == 403 and response.data["code"] == errors.AUTH_PERMISSION_DENIED
    with tenant_ctx(env.tenant):
        assert models.RateChangeBatch.objects.count() == 0


def test_us_rat_011_tc8__a_batch_touches_only_its_own_tenants_schedules(env, other_env, job_store):
    schedules = _bulk_seed(env)
    other = other_env.flat_schedule("Co-op Water Flat", "water", "3.10")
    payload = _batch_payload(schedules)
    payload["entities"].append({"type": "schedule", "id": other["id"]})
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.request_rate_change_batch(env.admin, payload)
    assert excinfo.value.field_errors[0]["message_key"] == "rating.bulk.unknown_entity"
    with tenant_ctx(other_env.tenant):
        assert models.RateChangeBatch.objects.count() == 0


@pytest.mark.isolation
@requires_postgres
def test_us_rat_011_tc8_rls__batches_are_rls_scoped(env, other_env, rls, job_store):  # noqa: F811
    """US-RAT-011 TC-8 at the DATABASE — the bulk path is the dangerous one.

    A single update touches one row a human just looked at. A BATCH re-prices
    every schedule its entity list resolves, atomically (BR-RAT-040), and the
    app half's `rating.bulk.unknown_entity` refusal is only a selector lookup
    coming back empty. This asserts the two things that must hold when that
    lookup does NOT come back empty: the foreign tariff is unreadable at the
    policy level, and `rate_change_batches` itself never crosses.
    """
    schedules = _bulk_seed(env)
    other = other_env.flat_schedule("Co-op Water Flat", "water", "3.10")
    # ⚠ **THE JOB IS RUN, AND THE COMMENT THAT USED TO STAND HERE CONTRADICTED
    # ITSELF (2026-09-05).** It said *"enqueue only: the batch ROW is what this
    # case probes"* — but `request_rate_change_batch` only VALIDATES, PREVIEWS
    # and ENQUEUES; the `rate_change_batches` row is written by the job body,
    # `apply_rate_change_batch`. So the case probed a table it had not written
    # to.
    # It looked fine because `JOBS_EAGER` defaults TRUE under
    # `config.settings.local`, which runs a dispatched job INLINE — so the row
    # appeared anyway on a developer's run. The isolation proof runs with
    # `JOBS_EAGER=false` (hard-won law 14's own footnote), the job stayed
    # queued, and `assert_rls_scoped` correctly refused to conclude anything
    # from an empty table. `_run_batch` is this file's own helper and runs the
    # job the way a worker does.
    _run_batch(env, _batch_payload(schedules))

    assert_rls_scoped(rls, "rate_change_batches", owner=env.tenant, intruder=other_env.tenant)
    with live_tenant_context(other_env.tenant.id):
        # The id the batch was refused on is not merely un-listed; it is unreadable.
        assert rls.count("tariffs", "id = %s", [str(schedules[0]["id"])]) == 0
        assert rls.ids("tariffs") == {str(other["id"])}
    assert_write_into_other_tenant_refused(
        rls, "rate_change_batches", owner=env.tenant, intruder=other_env.tenant
    )
    assert_denied_without_context(rls, "rate_change_batches")


def test_us_rat_011_tc1_preview__before_after_rows_write_nothing(env, job_store):
    """IS-6 half of TC-1: the preview the confirm modal shows is computed
    without writing (the money action commits only on apply)."""
    schedules = _bulk_seed(env)
    with tenant_ctx(env.tenant):
        result = services.request_rate_change_batch(
            env.admin, _batch_payload(schedules, preview=True)
        )
        assert models.RateChangeBatch.objects.count() == 0
        assert models.TariffVersion.objects.count() == 3
    electric = next(row for row in result["preview"] if row["name"] == "Res Electric · Tiered")
    assert electric["changes"][0] == {
        "field": "tier[1].unit_price",
        "before": "0.110000",
        "after": "0.113300",
    }
