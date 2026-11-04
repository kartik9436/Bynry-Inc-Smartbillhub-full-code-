# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-INT-9848 (PO GIS review 2026-10-07, gap 2 — Runbook 20 never
#           fetched the City) · DEF-INT-9849 (gap 3 — the parcel check's
#           preview could not finish inside the web worker's 60 seconds)
# Rules:    PO ruling 2026-10-07 (decision log: "THE PARCEL CHECK WILL RUN
#           THROUGH RUNBOOK 20, FIRST BY HAND …") · BR-INT-072 (all or nothing
#           for a write) · BR-INT-074 (a preview writes nothing) · R28 (never
#           touch an address field by default) · BR-RBS-027 (a stop is a state)
# Impacts:  apps/runbooks/definitions/gis_reconciliation.py ·
#           apps/runbooks/seams/integrations_seam.py · apps/integrations/gis.py ·
#           gis_parcels.py · gis_layer.py · gis_esri_fixtures.py · api.py ·
#           apps/runbooks/api.py::runbook_runs (Run ▶, CR-173-BRC10 — the by-hand door)
# ───────────────────────────────────────────────────────
"""Runbook 20 asks the City, and a by-hand check says how much of the City it read.

**RED BEFORE, measured 2026-10-07 at 2.558.5 with these cases:** a tenant with a
working Esri ArcGIS connection ran Runbook 20 and it stopped at step 1 with
*"Nothing has landed yet."* — the City was never dialled
(`test_a_working_connection_gathers_the_citys_parcels_through_the_seam`);
`integrations_seam.city_parcels` did not exist; `gis_layer.walk` took no
`stop_after_pages`; `POST …/reconcile?pages=2` read all three pages of the
recorded layer and said nothing about a limit.

⚠ **THE CITY IS THE RECORDED ONE.** `gis.example` (RFC 2606) is served by
`gis_esri_fixtures.recorded_transport` — seven address points over four parcels,
three rows a page, so three pages — and the four refusing hosts Lane C added
answer 401, 404, 503 and a 200 carrying an error body. No real City is dialled.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.integrations import gis, gis_esri_fixtures, gis_fixtures, gis_layer, gis_parcels, models
from apps.integrations import api as integrations_api
from apps.integrations import services as integration_services
from apps.integrations import custom_apis, runtime
from apps.runbooks import services as runbook_services
from apps.runbooks.definitions import gis_reconciliation as rb20
from apps.runbooks.seams import integrations_seam
from core import errors
from core.permissions import SYSTEM_ADMIN
from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · make_premises
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

LAYER_PATH = "/arcgis/rest/services/Qualified/FeatureServer/0"


@pytest.fixture(autouse=True)
def _clear_caps():
    runtime.reset_caps()
    yield
    runtime.reset_caps()


def _connect(tenant, actor, host=gis_esri_fixtures.FIXTURE_HOST, *, working=True):
    """An Esri ArcGIS connection at a recorded host, marked WORKING as a tested
    connection is (Runbook 20 only opens the City door for a working one)."""
    from core.tenancy import tenant_context

    with tenant_context(tenant.id):
        connection = integration_services.connect(
            actor=actor,
            tenant_id=tenant.id,
            provider_key=gis.PROVIDER_KEY,
            environment=models.ENVIRONMENT_PRODUCTION,
            config={"base_url": f"https://{host}{LAYER_PATH}"},
            cadence=models.CADENCE_NIGHTLY,
        )
        if working:
            models.IntegrationConnection.objects.filter(pk=connection.pk).update(
                status=models.STATUS_WORKING
            )
            connection.refresh_from_db()
    return connection


def _our_estate(tenant, actor):
    """Three of ours: two the City knows by address, one it has never heard of.

    ⚠ The City matches on STREET AND POSTCODE, so a postcode that differs is
    not a difference — it is no match at all. The difference planted here is
    the CITY NAME on 100 N Maple St (ours *Riverbend Twp*, theirs *Riverbend*),
    an address field `R28` says is never touched by default."""
    from core.tenancy import tenant_context

    with tenant_context(tenant.id):
        _make_three(actor)


def _make_three(actor):
    make_premises(actor, address_line="100 N Maple St", city="Riverbend Twp", state="MI",
                  postal_code="48104")  # the City says Riverbend — a difference
    make_premises(actor, address_line="44 W Birch Ln", city="Riverbend", state="MI",
                  postal_code="07001")
    make_premises(actor, address_line="9 Nowhere Rd", city="Riverbend", state="MI",
                  postal_code="48104")


def _snapshot_of_ours(tenant):
    """Every premises and unit row as it stands — compared before and after."""
    from apps.metering import models as metering_models
    from core.tenancy import tenant_context

    with tenant_context(tenant.id):
        premises = sorted(
            tuple(sorted((k, str(v)) for k, v in row.items()))
            for row in metering_models.Premises.objects.values()
        )
        units = sorted(
            tuple(sorted((k, str(v)) for k, v in row.items()))
            for row in metering_models.Unit.objects.values()
        )
    return premises, units


def _run_rb20(tenant, params=None):
    """Runbook 20, DRY, through the product's own run path — the one the
    by-hand command and the schedule's worker both call."""
    from core.tenancy import tenant_context

    with tenant_context(tenant.id):
        runbook = runbook_services.add_template(tenant.id, rb20.KEY)
        run, result = runbook_services.run_to_completion(
            runbook, rb20.RUNBOOK, params=dict(params or {})
        )
    return run, result


def _blocks(result):
    out = {}
    for block in result.report:
        if isinstance(block, dict):
            out[block["block"]] = block["payload"]
        else:
            out[block.block] = block.payload
    return out


# ── gap 3 · the walk, pure ──────────────────────────────────────────────────


def _layer():
    return gis_parcels.config_from_connection({"layer_url": gis_esri_fixtures.FIXTURE_LAYER})


def test_a_walk_asked_for_one_page_stops_and_says_it_is_not_the_register():
    snapshot = gis_layer.walk(
        _layer(), transport=gis_esri_fixtures.recorded_transport, stop_after_pages=1
    )
    assert snapshot.complete is False
    assert snapshot.pages == 1
    assert len(snapshot) == 3
    # The City's own count, never a guess: 7 rows at 3 a page is 3 pages.
    assert snapshot.total_rows == len(gis_esri_fixtures.FEATURES) == 7
    assert snapshot.total_pages == 3


def test_a_limit_above_the_register_reads_the_whole_of_it_and_says_so():
    snapshot = gis_layer.walk(
        _layer(), transport=gis_esri_fixtures.recorded_transport, stop_after_pages=10
    )
    assert snapshot.complete is True
    assert snapshot.pages == 3 and snapshot.total_pages == 3
    assert len(snapshot) == 7


def test_a_city_that_will_not_count_leaves_the_total_unknown_not_guessed():
    def no_count(url, timeout_s):
        if "returnCountOnly" in url:
            return {"error": {"code": 400, "message": "count not supported"}}
        return gis_esri_fixtures.recorded_transport(url, timeout_s)

    snapshot = gis_layer.walk(_layer(), transport=no_count, stop_after_pages=2)
    assert snapshot.complete is False
    assert snapshot.total_rows is None and snapshot.total_pages is None


def test_a_page_limit_below_one_is_refused():
    with pytest.raises(ValueError):
        gis_layer.walk(_layer(), transport=gis_esri_fixtures.recorded_transport,
                       stop_after_pages=0)


def test_a_limited_preview_says_stopped_after_n_of_m_pages():
    report = gis_parcels.run(
        connection_config={"layer_url": gis_esri_fixtures.FIXTURE_LAYER},
        ours={"premises": [], "units_by_premises": {}},
        transport=gis_esri_fixtures.recorded_transport,
        max_pages=2,
    )
    assert report["complete"] is False
    assert report["headline"].startswith("Stopped after 2 of 3 pages. ")
    assert report["counts"]["city_pages"] == 2
    assert report["counts"]["city_pages_total"] == 3
    assert report["counts"]["city_rows"] == 6


def test_an_unlimited_preview_is_complete_and_its_headline_unchanged():
    report = gis_parcels.run(
        connection_config={"layer_url": gis_esri_fixtures.FIXTURE_LAYER},
        ours={"premises": [], "units_by_premises": {}},
        transport=gis_esri_fixtures.recorded_transport,
    )
    assert report["complete"] is True
    assert not report["headline"].startswith("Stopped")
    assert report["counts"]["city_pages_total"] == report["counts"]["city_pages"] == 3


def test_an_apply_with_a_page_limit_is_refused_before_anything_is_dialled():
    dialled = []

    def watch(url, timeout_s):
        dialled.append(url)
        return gis_esri_fixtures.recorded_transport(url, timeout_s)

    with pytest.raises(gis_parcels.GisRunRefused):
        gis_parcels.run(
            connection_config={"layer_url": gis_esri_fixtures.FIXTURE_LAYER},
            ours={"premises": [], "units_by_premises": {}},
            mode=gis_parcels.APPLY,
            transport=watch,
            max_pages=1,
        )
    assert dialled == []


@pytest.mark.parametrize("raw,expected", [(None, None), ("", None), ("3", 3), (2, 2), (" 5 ", 5)])
def test_a_page_count_is_read_as_a_whole_number(raw, expected):
    assert gis.pages_or_refuse(raw) == expected


@pytest.mark.parametrize("raw", ["0", 0, -1, "2.5", 2.5, "three", True])
def test_anything_else_is_refused_by_name_never_read_as_the_whole_register(raw):
    with pytest.raises(gis.GisRefusal) as refusal:
        gis.pages_or_refuse(raw)
    assert refusal.value.message_key == gis.REFUSAL_PAGES_WHOLE_NUMBER


# ── gap 3 · the route a person calls by hand ────────────────────────────────


def _reconcile(tenant, actor, *, data=None, query=None):
    """The route as a person calls it by hand. A query string rides on the
    PATH, because the test client hands a POST its body and not `query`."""
    from urllib.parse import urlencode

    path = f"/api/{tenant.subdomain}/integrations/{gis.PROVIDER_KEY}/reconcile"
    if query:
        path = f"{path}?{urlencode(query)}"
    return api_call(
        integrations_api.gis_reconcile,
        "post",
        path,
        user=actor.user,
        role=SYSTEM_ADMIN,
        tenant=tenant,
        data=data or {"mode": "preview"},
        key=gis.PROVIDER_KEY,
    )


def test_pages_on_the_query_string_is_honoured_and_stated(brazos, dana):
    _connect(brazos, dana)
    response = _reconcile(brazos, dana, query={"pages": "2"})
    assert response.status_code == 200, response.data
    assert response.data["complete"] is False
    assert response.data["counts"]["city_pages"] == 2
    assert response.data["counts"]["city_pages_total"] == 3
    assert response.data["headline"].startswith("Stopped after 2 of 3 pages.")


def test_a_preview_nobody_limited_reads_the_safe_default(brazos, dana, monkeypatch):
    """The route's default, proved by shrinking it below the recorded layer —
    three pages IS the whole recorded layer, so at 3 the case could not fail."""
    monkeypatch.setattr(gis, "MANUAL_PREVIEW_PAGES", 1)
    _connect(brazos, dana)
    response = _reconcile(brazos, dana)
    assert response.status_code == 200, response.data
    assert response.data["counts"]["city_pages"] == 1
    assert response.data["complete"] is False


def test_the_default_is_three_pages(brazos, dana):
    assert gis.MANUAL_PREVIEW_PAGES == 3


def test_a_limited_preview_is_not_recorded_as_confirmed(brazos, dana):
    from core.tenancy import tenant_context

    connection = _connect(brazos, dana)
    response = _reconcile(brazos, dana, query={"pages": "1"})
    assert response.status_code == 200, response.data
    with tenant_context(brazos.id):
        run = models.IntegrationRun.objects.get(id=response.data["run_id"])
    assert run.connection_id == connection.id
    # A part of the register is never *confirmed* — amber, not green.
    assert run.outcome == models.OUTCOME_UNCONFIRMED
    assert run.summary.startswith("Stopped after 1 of 3 pages.")


def test_an_apply_with_pages_is_refused_and_records_nothing(brazos, dana):
    from core.tenancy import tenant_context

    connection = _connect(brazos, dana)
    response = _reconcile(brazos, dana, data={"mode": "apply", "pages": 2})
    assert response.status_code == 422, response.data
    assert gis.REFUSAL_PAGES_PREVIEW_ONLY in json.dumps(response.data)
    with tenant_context(brazos.id):
        assert not models.IntegrationRun.objects.filter(connection=connection).exists()


def test_a_page_count_that_is_not_a_number_is_a_422_never_a_500(brazos, dana):
    _connect(brazos, dana)
    response = _reconcile(brazos, dana, query={"pages": "three"})
    assert response.status_code == 422, response.data
    assert gis.REFUSAL_PAGES_WHOLE_NUMBER in json.dumps(response.data)


def test_an_apply_without_pages_still_reads_the_whole_register(brazos, dana):
    _connect(brazos, dana)
    response = _reconcile(brazos, dana, data={"mode": "apply"})
    assert response.status_code == 200, response.data
    assert response.data["complete"] is True
    assert response.data["counts"]["city_pages"] == 3


def test_both_new_refusals_and_the_screen_sentences_are_in_all_eleven_catalogues():
    locales = Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
    files = sorted(locales.glob("*.json"))
    assert len(files) == 11, [one.name for one in files]
    for one in files:
        catalogue = json.loads(one.read_text(encoding="utf-8"))
        for key in (
            gis.REFUSAL_PAGES_PREVIEW_ONLY,
            gis.REFUSAL_PAGES_WHOLE_NUMBER,
            "integrations.reconcile.stoppedAfterOf",
            "integrations.reconcile.stoppedAfter",
        ):
            assert catalogue.get(key), f"{one.name} has no {key}"


# ── gap 2 · the seam ────────────────────────────────────────────────────────


def test_the_seams_english_matches_the_catalogue_word_for_word():
    """The seam holds a second copy of four sentences; this is what keeps it."""
    locales = Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
    english = json.loads((locales / "en.json").read_text(encoding="utf-8"))
    for key, sentence in integrations_seam.CITY_REFUSAL_SENTENCES.items():
        assert english.get(key) == sentence, key


def test_the_seam_reads_the_city_through_the_existing_parcel_check(brazos, dana):
    from core.tenancy import tenant_context

    _connect(brazos, dana)
    with tenant_context(brazos.id):
        answer = integrations_seam.city_parcels(started_by_name="Dana Whitfield")
        run = models.IntegrationRun.objects.order_by("-started_at").first()
    assert answer.get("refused") is not True
    assert answer["mode"] == gis_parcels.PREVIEW
    assert answer["counts"]["city_rows"] == 7
    # ONE door: the attempt is the parcel check's own run row, by a named person.
    assert run.operation == gis.RECONCILE_OPERATION
    assert run.mode == gis_parcels.PREVIEW
    assert run.started_by_name == "Dana Whitfield"
    json.dumps(answer)  # plain JSON — the frozen report is JSON


def test_the_seam_never_raises_on_a_switched_off_sync(brazos, dana):
    from core.tenancy import tenant_context

    connection = _connect(brazos, dana)
    with tenant_context(brazos.id):
        custom_apis.switch(actor=dana, connection=connection,
                           operation_name=gis.RECONCILE_OPERATION, enabled=False)
        answer = integrations_seam.city_parcels()
    assert answer["refused"] is True
    assert answer["headline"] == "This sync is switched off."


# ── gap 2 · Runbook 20, end to end, DRY ─────────────────────────────────────


def test_a_working_connection_gathers_the_citys_parcels_through_the_seam(brazos, dana):
    """THE DEFECT. Red before: step 1 stopped *"Nothing has landed yet."*."""
    _connect(brazos, dana)
    _our_estate(brazos, dana)
    _run, result = _run_rb20(brazos, {"started_by_name": "Dana Whitfield"})
    gathered = result.set_results[rb20.STEP_GATHER]
    assert "stop" not in gathered, gathered.get("stop")
    assert gathered["checked"]["source"] == "city"
    assert gathered["checked"]["city_rows_read"] == 7
    assert gathered["checked"]["city_read_whole"] is True
    matched = result.set_results[rb20.STEP_MATCH]["checked"]
    assert matched["premises_on_file"] == 3
    assert matched["premises_with_no_parcel"] >= 1  # 9 Nowhere Rd
    blocks = _blocks(result)
    assert blocks["verdict"]["detail"].startswith("The city sent 7 rows over 3 pages.")


def test_a_dry_run_reports_matches_mismatches_and_unmatched(brazos, dana):
    _connect(brazos, dana)
    _our_estate(brazos, dana)
    _run, result = _run_rb20(brazos)
    plan = result.set_results[rb20.STEP_DISPOSITION]["plan"]
    city = [one for one in plan if one["field"] == "city"]
    assert city and city[0]["ours"] == "Riverbend Twp" and city[0]["theirs"] == "Riverbend"
    assert city[0]["parcel_key"] == "09-01-100"  # the parcel it was compared against
    # 9 Nowhere Rd — ours, and no City parcel matched it: queued for a person.
    no_parcel = [one for one in plan if one["difference_class"] == rb20.CLASS_PREMISE_NO_PARCEL]
    assert len(no_parcel) >= 1
    assert {one["disposition"] for one in no_parcel} == {rb20.DISPOSITION_QUEUE}
    by_class = {row["cells"]["class"]["text"] for row in _blocks(result)["breakdown"]["rows"]}
    assert "Premise with no parcel" in by_class


def test_r28_every_address_difference_is_never_touched_whatever_the_parameter_says(brazos, dana):
    """`apply_automatically` defaults to postal code for a FILE. The City's rows
    keep the City check's own disposition — never touch, by the PO's R28."""
    _connect(brazos, dana)
    _our_estate(brazos, dana)
    _run, result = _run_rb20(brazos, {"apply_automatically": "postal_code"})
    plan = result.set_results[rb20.STEP_CAP]["plan"]
    address = [one for one in plan if one["field"] in ("address_line", "city", "state", "postal_code")]
    assert address
    assert {one["disposition"] for one in address} == {rb20.DISPOSITION_NEVER}
    assert not [one for one in plan if one["disposition"] == rb20.DISPOSITION_AUTO]


def test_a_dry_run_writes_no_premises_and_no_unit_and_one_attempt_row(brazos, dana):
    from core.tenancy import tenant_context

    connection = _connect(brazos, dana)
    _our_estate(brazos, dana)
    before = _snapshot_of_ours(brazos)
    with tenant_context(brazos.id):
        runs_before = models.IntegrationRun.objects.filter(connection=connection).count()
    _run_rb20(brazos)
    assert _snapshot_of_ours(brazos) == before
    with tenant_context(brazos.id):
        runs = models.IntegrationRun.objects.filter(connection=connection)
        assert runs.count() == runs_before + 1
        assert runs.order_by("-started_at").first().mode == gis_parcels.PREVIEW


def test_a_page_limit_on_the_runbook_is_honoured_and_stated(brazos, dana):
    _connect(brazos, dana)
    _our_estate(brazos, dana)
    _run, result = _run_rb20(brazos, {"pages": "1"})
    gathered = result.set_results[rb20.STEP_GATHER]["checked"]
    assert gathered["city_pages_read"] == 1
    assert gathered["city_pages_total"] == 3
    assert gathered["city_read_whole"] is False
    detail = _blocks(result)["verdict"]["detail"]
    assert "Stopped after 1 of 3 pages." in detail
    # Found in the browser walkthrough: it read *"over 1 pages"*.
    assert detail.startswith("The city sent 3 rows over 1 page.")


def test_a_premises_nothing_matched_is_not_counted_as_an_ambiguous_match(brazos, dana):
    """Found in the browser walkthrough: *Ambiguous match 16* over sixteen
    premises NO parcel matched — nothing matched is not two things matching."""
    _connect(brazos, dana)
    _our_estate(brazos, dana)
    _run, result = _run_rb20(brazos)
    chips = {one["id"]: one["count"] for one in _blocks(result)["records"]["chips"]}
    plan = result.set_results[rb20.STEP_CAP]["plan"]
    no_parcel = [one for one in plan if one["difference_class"] == rb20.CLASS_PREMISE_NO_PARCEL]
    assert no_parcel
    assert chips["ambiguous"] == 0
    assert chips["queued"] >= len(no_parcel)


@pytest.mark.parametrize(
    "host,headline",
    [
        (gis_fixtures.KEY_REFUSED_HOST, "The city rejected our key."),
        (gis_fixtures.MOVED_HOST, "The city's map layer has moved."),
        (gis_fixtures.DOWN_HOST, "The city's service had an error."),
        (gis_fixtures.TOKEN_BODY_HOST, "The city rejected our key."),
    ],
)
def test_a_city_refusal_stops_the_step_with_its_reason_never_a_500(brazos, dana, host, headline):
    _connect(brazos, dana, host)
    run, result = _run_rb20(brazos)
    stop = result.set_results[rb20.STEP_GATHER]["stop"]
    assert stop["headline"] == headline
    assert stop["fix_route"] == rb20.FIX_INTEGRATIONS
    blocks = _blocks(result)
    assert blocks["verdict"]["word"] == "Stopped"
    assert [cell["note"] for cell in blocks["chain"]["cells"][1:]] == ["Never reached"] * 6
    assert run.status != "failed"


def test_a_switched_off_sync_stops_the_runbook_by_name(brazos, dana):
    from core.tenancy import tenant_context

    connection = _connect(brazos, dana)
    with tenant_context(brazos.id):
        custom_apis.switch(actor=dana, connection=connection,
                           operation_name=gis.RECONCILE_OPERATION, enabled=False)
    _run, result = _run_rb20(brazos)
    assert result.set_results[rb20.STEP_GATHER]["stop"]["headline"] == "This sync is switched off."


def test_a_bad_page_count_on_the_runbook_stops_it_with_a_sentence(brazos, dana):
    _connect(brazos, dana)
    _run, result = _run_rb20(brazos, {"pages": "lots"})
    assert (
        result.set_results[rb20.STEP_GATHER]["stop"]["headline"]
        == "Give pages as a whole number."
    )


def test_def_int_9850_an_apply_at_a_utility_with_runbook_20_answers_200(brazos, dana):
    """`DEF-INT-9850`. Red before (PostgreSQL 16, 2026-10-07): the hand-off's
    `{"source": "gis", …}` reached a UUID lookup — `ValidationError: … is not a
    valid UUID` — and the route answered `500 SYS-INTERNAL` after the apply."""
    from apps.runbooks import models as runbook_models
    from core.tenancy import tenant_context

    _connect(brazos, dana)
    with tenant_context(brazos.id):
        runbook_services.add_template(brazos.id, rb20.KEY)
    response = _reconcile(brazos, dana, data={"mode": "apply"})
    assert response.status_code == 200, response.data
    assert response.data["handed_off"]["started"] is True
    with tenant_context(brazos.id):
        run = runbook_models.RunbookRun.objects.order_by("-started_at").first()
        assert run is not None and run.mode == "dry"
        verdict = next(one["payload"] for one in run.report if one["block"] == "verdict")
    # The descriptor opened the City door; it was never read as a missing file.
    assert verdict["word"] != "Stopped", verdict
    assert verdict["detail"].startswith("The city sent 7 rows over 3 pages."), verdict


# ── by hand, on PostgreSQL (RLS FORCE and the real transaction) ─────────────


@requires_postgres
def test_by_hand_run_pressed_dry_with_two_pages_reads_two_and_writes_nothing(
    brazos, dana, settings
):
    """**Run ▶** on Runbook 20's page (`POST /runbooks/{key}/runs`, built by
    `CR-173-BRC10`), dry, *City pages to read* = 2 — the PO's *"first by hand"*."""
    from apps.runbooks import api as runbook_api
    from apps.runbooks import models as runbook_models
    from core.tenancy import tenant_context

    settings.JOBS_EAGER = True
    connection = _connect(brazos, dana)
    _our_estate(brazos, dana)
    before = _snapshot_of_ours(brazos)
    with tenant_context(brazos.id):
        runbook_services.add_template(brazos.id, rb20.KEY)
    answer = api_call(
        runbook_api.runbook_runs, "post",
        f"/api/{brazos.subdomain}/runbooks/{rb20.KEY}/runs",
        user=dana.user, role=SYSTEM_ADMIN, tenant=brazos,
        data={"mode": "dry", "parameters": {"pages": "2"}},
        key=rb20.KEY,
    )
    assert answer.status_code == 202, getattr(answer, "data", None)
    with tenant_context(brazos.id):
        run = runbook_models.RunbookRun.objects.order_by("-started_at").first()
        attempt = (
            models.IntegrationRun.objects.filter(connection=connection)
            .order_by("-started_at").first()
        )
    assert run.mode == "dry" and run.trigger == "manual"
    verdict = next(one["payload"] for one in run.report if one["block"] == "verdict")
    assert "Stopped after 2 of 3 pages." in verdict["detail"]
    # Who pressed it reaches the City check's own attempt row.
    assert attempt.mode == gis_parcels.PREVIEW and attempt.started_by_name
    assert _snapshot_of_ours(brazos) == before
