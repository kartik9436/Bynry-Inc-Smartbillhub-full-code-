# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-042 (EP-INT-12) TC-1..7 — CR-069 wave M task M3
# Rules:    BR-INT-048 (`C14` executor + generated page policy · `C15` latency
#           budget, not a job · `C16` disposition `offer`) · BR-INT-022 (the
#           breaker) · BR-INT-039 (one durable record) · BR-INT-049 (frame) ·
#           BR-INT-003 (no secret to the browser) · OQ-INT-1471 (b) ·
#           OQ-INT-1728 (a)
# ───────────────────────────────────────────────────────
"""US-INT-042 — the inline address search, the write, and the generated policy.

⚠ **TC-4 IS NOT WHAT THE EPIC'S TABLE SAYS, AND THAT IS THE POINT OF READING
THIS DOCSTRING.** `EP-INT-12`'s §3 still expects
`NotImplementedError("OQ-INT-1471")` on the boundary case, and the plan's `M1`
row and `08-screen-layouts.md`'s deviation note say the same. All three were
written before the ruling. **`OQ-INT-1471` was CLOSED on 2026-09-04 — PO
verbatim, *"(b) type it, marked unchecked"*** — and the register's own status
column, the story's §8 table and the plan's *Blocked by* line all say so. The
status column decides (CLAUDE.md, prime directive), so TC-4 below asserts the
BUILD: the premises exists, it carries no parcel key, and it is marked.

⚠ **AND THE TIMING CASES USE A SLEEPING FIXTURE, NEVER A RAISING ONE**
(`US-INT-022` TC-2, quoted in `runtime.py`): a raising fixture returns
instantly, so a version with no deadline and a version with one behave
identically and the test proves nothing.
"""

from __future__ import annotations

import time

import pytest

from apps.integrations import gis, gis_fixtures, live_calls, models, page_policy, runtime
from apps.integrations import api as integrations_api
from apps.integrations import services as integration_services
from apps.integrations.adapters.base import ConnectionView
from apps.integrations.adapters.gis_city import GisCityAdapter
from apps.integrations.runtime import ProviderTimeout
from apps.integrations.registry import (
    Auth,
    Disposition,
    Field,
    Idempotency,
    Manifest,
    ManifestError,
    Operation,
    Registry,
    validate,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_ten_helpers import api_call

CITY = f"https://{gis_fixtures.FAST_HOST}/addr"
SLOW_CITY = f"https://{gis_fixtures.SLOW_HOST}/addr"


@pytest.fixture(autouse=True)
def _clear_caps():
    """The concurrency semaphores are process-local; a suite that changes a
    limit or leaves one held must clear them (`runtime.reset_caps`'s own note)."""
    runtime.reset_caps()
    yield
    runtime.reset_caps()


def _form(actor, **overrides):
    """The create form as the WIZARD sends it, owner included.

    ⚠ **`owner_id` IS IN HERE BECAUSE `BR-MET-401` REQUIRES IT AT CREATE**, and
    leaving it out is what caught the seam dropping every field it did not
    name: the pick refused with `metering.premises.owner_required` while typing
    the same address succeeded. The fixture sends what the screen sends.
    """
    payload = {
        "address_line": "1408 Pec",
        "premises_type": "single_family",
        "owner_id": owner_for(actor, "Whitfield Rentals LLC"),
    }
    payload.update(overrides)
    return payload


def _connect_city(tenant, actor, *, base_url=CITY):
    return integration_services.connect(
        actor=actor,
        tenant_id=tenant.id,
        provider_key=gis.PROVIDER_KEY,
        environment=models.ENVIRONMENT_PRODUCTION,
        config={"base_url": base_url},
        cadence=models.CADENCE_NIGHTLY,
    )


# ═══════════════════════════════════════════════════════════════════════════
# The manifest half — `C14`, `C15` and `C16` as DATA, refused at load
# ═══════════════════════════════════════════════════════════════════════════


def _manifest(**operation_overrides) -> Manifest:
    base = dict(
        name="address_search",
        label="Address search",
        direction="in",
        initiative="us",
        transport="https",
        trigger="inline",
        idempotency=Idempotency(mode="reconcile", source="none"),
        completion="immediate",
        # CR-110-BRC04 — every operation names its ceiling or the registry refuses it.
        rate_limit_per_minute=60,
        latency_budget_ms=1000,
        result_disposition="offer",
    )
    base.update(operation_overrides)
    return Manifest(
        key="fixture_city",
        category="maps",
        display_name="Fixture city",
        summary="A city, for a test.",
        disposition=Disposition(kind="live", phase=4),
        auth=Auth(mode="none", placement="none"),
        # CR-110-BRC04 / DEF-INT-5488 — an operation we dial has to name a host
        # field the manifest actually declares, so a fixture needs one too.
        fields=(Field(name="base_url", label="Service address", kind="host"),),
        operations=(Operation(**base),),
    )


def test_c15_an_inline_server_operation_without_a_budget_is_refused_by_name():
    with pytest.raises(ManifestError) as refusal:
        validate(_manifest(latency_budget_ms=None))
    assert "latency_budget_ms" in str(refusal.value)
    assert "not a job" in str(refusal.value)


def test_c16_a_disposition_outside_the_vocabulary_is_refused_by_name():
    with pytest.raises(ManifestError) as refusal:
        validate(_manifest(result_disposition="write_it"))
    assert "result_disposition" in str(refusal.value)


def test_c15_a_budget_on_a_browser_operation_is_refused_because_we_cannot_enforce_it():
    """We are not the one waiting, so a deadline there is a guarantee we could
    not keep — hard-won law 1, held at load rather than written in a comment."""
    with pytest.raises(ManifestError) as refusal:
        validate(_manifest(name="map_tiles", executor="browser", latency_budget_ms=500))
    assert "not the one waiting" in str(refusal.value)


def test_br_int_003_a_browser_operation_on_a_provider_that_requires_a_secret_is_refused():
    """A browser-executed call puts everything it needs in the page."""
    leaky = Manifest(
        key="leaky_tiles",
        category="maps",
        display_name="Leaky tiles",
        summary="Tiles, with a key.",
        auth=Auth(mode="we_hold_theirs", placement="query"),
        fields=(
            Field(name="base_url", label="Service address", kind="host"),
            Field(name="api_key", label="API key", kind="secret"),
        ),
        operations=(
            Operation(
                name="map_tiles",
                label="Map tiles",
                direction="in",
                initiative="us",
                transport="browser",
                trigger="inline",
                idempotency=Idempotency(mode="reconcile", source="none"),
                completion="immediate",
                # CR-110-BRC04 — every operation names its ceiling.
                rate_limit_per_minute=600,
                executor="browser",
                result_disposition="load",
            ),
        ),
    )
    with pytest.raises(ManifestError) as refusal:
        validate(leaky)
    assert "carries no tenant secret" in str(refusal.value)


def test_the_shipped_gis_manifest_declares_the_story_figures():
    """`C15` = 1,000 ms and `C16` = `offer` — read from the manifest, not typed."""
    from apps.integrations.registry import REGISTRY

    search = next(
        one for one in REGISTRY.get("gis_esri").operations if one.name == "address_search"
    )
    assert search.latency_budget_ms == 1000
    assert search.result_disposition == "offer"
    assert search.executor == "server"
    tiles = next(one for one in REGISTRY.get("gis_esri").operations if one.name == "map_tiles")
    assert tiles.executor == "browser"
    assert tiles.latency_budget_ms is None


# ═══════════════════════════════════════════════════════════════════════════
# The pure half — no database, no clock, no network
# ═══════════════════════════════════════════════════════════════════════════


def test_no_score_reaches_a_screen_as_a_number():
    """`US-INT-042` §1 — *"no score is shown as a number"*. The only way that
    stays true is for the number not to be in the payload at all."""
    shown = gis.presented(dict(gis_fixtures.PECAN_ST, address_line="1408 Pecan St"))
    assert "score" not in shown
    assert "score_scale" not in shown
    assert shown["match"] == "strong"


def test_the_two_words_are_computed_from_their_number_on_either_scale():
    assert gis.match_word("96", "0-100") == "strong"
    assert gis.match_word("58", "0-100") == "close"
    assert gis.match_word("0.9", "0-1") == "strong"
    assert gis.match_word("0.4", "0-1") == "close"
    # A provider that would not say has not made a strong claim.
    assert gis.match_word(None) == "close"


def test_br_int_049_a_candidate_out_of_the_declared_frame_keeps_its_address_and_loses_its_pin():
    projected = dict(gis_fixtures.PECAN_ST, frame="EPSG:3857")
    assert gis.frame_is_declared(projected) is False
    assert gis.frame_is_declared(dict(gis_fixtures.PECAN_ST)) is True


def test_a_candidate_with_no_parcel_key_is_never_offered():
    """Offering one would make the checked and the unchecked case identical on
    screen, which is the danger `OQ-INT-1471` named."""
    from apps.integrations.adapters.gis_city import candidate_from

    assert candidate_from({"address": "1408 Pecan St"}) is None
    assert candidate_from({"parcel": "88214"}) is None


def test_def_int_5600_5602_a_candidate_carries_BOTH_keys_and_the_city_status():
    """`CR-112` names two keys and a status; the search carried one of the three.

    ⚠ **ONE ASSERTION PER KEY, DELIBERATELY.** A case that checked *the City's
    keys were carried* and looked at one of them is the check-that-does-not-check
    this repo keeps meeting — and it is exactly how `units.gis_point_id` reached
    production NULL on every row with 42 tests green.
    """
    from apps.integrations.adapters.gis_city import candidate_from

    # Ann Arbor's own spelling — `PIN` is the parcel, `FULLPIN` the address
    # point. The lower-case aliases are what a stub or another City may send.
    one = candidate_from(
        {"parcel": "09-09-29-001", "FULLPIN": "09-09-29-001-0004",
         "address": "500 Main St", "status": "ACTIVE"}
    )
    assert one is not None
    assert one["parcel"] == "09-09-29-001"
    assert one["point"] == "09-09-29-001-0004"
    assert one["status"] == "ACTIVE"
    # A row with no point key is still OFFERED — the parcel is what makes a
    # candidate worth picking, and some cities publish no per-address key.
    bare = candidate_from({"parcel": "88214", "address": "1408 Pecan St"})
    assert bare is not None and bare["point"] is None and bare["status"] is None
    # …and all three reach the wire, because a screen and a reconciliation that
    # see different candidates cannot both be right about one.
    shown = gis.presented(dict(gis_fixtures.PECAN_ST, address_line="1408 Pecan St"))
    assert shown["parcel"] == "88214"
    assert shown["point"] == "88214-0001"
    assert shown["status"] == "ACTIVE"


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 · candidates inside the budget, ONE inline run row, no job
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc1_candidates_arrive_inside_the_budget_and_write_one_inline_run_row(brazos, dana):
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        _connect_city(brazos, dana)
        started = time.monotonic()
        first = gis.search(brazos.id, query="1408 Pec")
        elapsed_ms = int((time.monotonic() - started) * 1000)

        assert elapsed_ms < first["budget_ms"], f"{elapsed_ms} ms is over the declared budget"
        assert first["budget_ms"] == 1000
        assert len(first["candidates"]) == 4
        assert first["candidates"][0]["parcel"] == "88214"
        assert first["candidates"][0]["address_line"] == "1408 Pecan St"
        assert first["reachable"] is True

        # Thirteen more keystrokes in the SAME session.
        session = first["session"]
        for _ in range(13):
            again = gis.search(brazos.id, query="1408 Pec", session_id=session)
            assert again["session"] == session

        rows = list(models.IntegrationRun.objects.filter(tenant_id=brazos.id))
        assert len(rows) == 1, "one row per SEARCH SESSION, never one per keystroke"
        assert rows[0].trigger == "inline"
        assert rows[0].job_id is None, "an inline operation has no job to poll (C15)"
        assert rows[0].attempted == 14
        assert rows[0].finished_at is None, "nothing is written and nothing is closed by a lookup"

        # C16 — the disposition is `offer`: NOTHING was written.
        from apps.metering import models as metering_models

        assert metering_models.Premises.objects.filter(tenant_id=brazos.id).count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 · the pick, the live re-check, the premises
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc2_the_pick_re_checks_the_parcel_and_writes_the_premises(brazos, dana):
    from core.tenancy import tenant_context
    from apps.metering import models as metering_models

    with tenant_context(brazos.id):
        _connect_city(brazos, dana)
        found = gis.search(brazos.id, query="1408 Pec")
        premises = gis.create_premises(
            dana,
            brazos.id,
            parcel="88214",
            typed=_form(dana),
            session_id=found["session"],
        )

        # ⚠ `external_ref` UNTIL 2026-09-17 — the parcel key moved to its own
        # column (`BR-MET-1173`); `external_ref` is the IMPORT match key and
        # a migrated utility already has a value in it.
        assert premises["gis_parcel_id"] == "88214"
        assert premises["address_line"] == "1408 Pecan St"
        assert premises["postal_code"] == "78702"
        assert premises["gis_unchecked"] is False
        # `DEF-INT-5602` — ruling 10 of 2026-09-17: the City's own word for its
        # own record, stored as given. `payload_from` read this key from the day
        # `CR-112` landed and `candidate_from` never produced one.
        assert premises["gis_status"] == "ACTIVE"

        row = metering_models.Premises.objects.get(tenant_id=brazos.id)
        assert str(row.lat) == "30.267200"
        assert str(row.lng) == "-97.743100"

        run = models.IntegrationRun.objects.get(tenant_id=brazos.id)
        assert run.finished_at is not None
        assert run.changed == 1
        # ⚠ ONE lookup, not two: the live re-check that happens INSIDE Create
        # is part of the pick, not a fifteenth keystroke. `US-INT-042` TC-1's
        # own shape — *14 lookups · 1 pick* — counts them as two different
        # things, and a re-check filed as a lookup would make every session's
        # count one higher than the number of times a clerk typed.
        assert run.summary == "1 lookup · 1 pick"


@pytest.mark.django_db
def test_tc2_a_parcel_the_city_no_longer_returns_is_refused_by_name(brazos, dana):
    from core.tenancy import tenant_context
    from apps.metering import models as metering_models

    with tenant_context(brazos.id):
        _connect_city(brazos, dana)
        with pytest.raises(gis.GisRefusal) as refusal:
            gis.create_premises(
                dana, brazos.id, parcel="00000", typed=_form(dana)
            )
        assert refusal.value.message_key == gis.REFUSAL_PARCEL_GONE
        assert metering_models.Premises.objects.filter(tenant_id=brazos.id).count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 · the slow city, the breaker, the sentence
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc3_a_slow_city_opens_the_breaker_and_the_screen_says_so(brazos, dana):
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        connection = _connect_city(brazos, dana, base_url=SLOW_CITY)
        # Three consecutive timeouts open it (`runtime.DEFAULT_BREAKER_AFTER`).
        answers = [gis.search(brazos.id, query="1408 Pec") for _ in range(3)]
        for answer in answers:
            assert answer["reachable"] is False
            assert answer["message_key"] == gis.REFUSAL_CITY_NOT_ANSWERING
            assert answer["candidates"] == []

        connection.refresh_from_db()
        state = runtime.BreakerState.from_config(connection.config)
        assert state.open_until is not None, "three timeouts open the breaker"
        assert connection.status == models.STATUS_NOT_WORKING

        # A fourth call is NEVER DIALLED — that is what `skipped` means.
        started = time.monotonic()
        fourth = gis.search(brazos.id, query="1408 Pec")
        assert time.monotonic() - started < 1.0, "an open breaker dials nobody"
        assert fourth["reachable"] is False

        outcomes = {
            one.outcome for one in models.IntegrationRun.objects.filter(tenant_id=brazos.id)
        }
        assert models.OUTCOME_SKIPPED in outcomes, "BR-INT-024 — the skip is recorded"


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 · the boundary — `OQ-INT-1471`, ruled (b): a BUILD, not a stub
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc4_with_the_city_unreachable_the_clerk_types_it_and_the_row_is_marked_unchecked(
    brazos, dana
):
    """⚠ The epic's TC-4 still says `NotImplementedError("OQ-INT-1471")`. The
    register closed that question on 2026-09-04 with option (b) and the status
    column decides — so the assertion is the RULING, not the stale table."""
    from core.tenancy import tenant_context
    from apps.metering import models as metering_models

    with tenant_context(brazos.id):
        _connect_city(brazos, dana, base_url=SLOW_CITY)
        offline = gis.search(brazos.id, query="1408 Pec")
        assert offline["reachable"] is False

        premises = gis.create_premises(
            dana,
            brazos.id,
            parcel=None,
            typed=_form(
                dana,
                address_line="1408 Pecan St",
                city="Brazos Bend",
                state="TX",
                postal_code="78702",
            ),
        )

        assert premises["gis_unchecked"] is True, "the MARK is the whole ruling"
        assert premises["gis_parcel_id"] is None, "no parcel key was claimed"
        row = metering_models.Premises.objects.get(tenant_id=brazos.id)
        assert row.gis_unchecked is True
        assert row.gis_parcel_id is None


@pytest.mark.django_db
def test_tc4_the_mark_is_visible_wherever_a_premises_is_read(brazos, dana):
    """A column nothing renders is hard-won law 2, not compliance."""
    from core.tenancy import tenant_context
    from apps.metering import selectors as metering_selectors
    from apps.metering import models as metering_models

    with tenant_context(brazos.id):
        _connect_city(brazos, dana, base_url=SLOW_CITY)
        gis.create_premises(
            dana, brazos.id, parcel=None, typed=_form(dana, address_line="1408 Pecan St")
        )
        row = metering_models.Premises.objects.get(tenant_id=brazos.id)
        assert metering_selectors.premises_detail_dict(row)["gis_unchecked"] is True


@pytest.mark.django_db
def test_tc4_a_failed_re_check_never_silently_downgrades_a_pick(brazos, dana):
    """A clerk who picked a row asked for THAT parcel. Quietly writing an
    unchecked premises instead would create the row `OQ-INT-1471` warns about
    without anybody choosing it."""
    from core.tenancy import tenant_context
    from apps.metering import models as metering_models

    with tenant_context(brazos.id):
        _connect_city(brazos, dana, base_url=SLOW_CITY)
        with pytest.raises(gis.GisRefusal) as refusal:
            gis.create_premises(
                dana, brazos.id, parcel="88214", typed=_form(dana, address_line="1408 Pecan St")
            )
        assert refusal.value.message_key == gis.REFUSAL_CITY_NOT_ANSWERING
        assert metering_models.Premises.objects.filter(tenant_id=brazos.id).count() == 0


@pytest.mark.django_db
def test_def_int_4266_the_mark_means_the_city_has_not_confirmed_it_on_every_path(
    brazos, dana
):
    """⚠ **THREE PATHS SET IT AND EVERY DOCUMENT NAMED ONE.**

    The wave's tests covered a pick (not marked) and the City unreachable
    (marked) and neither of the two in between — a clerk who types the address
    without searching, and one who sees the candidates and types her own
    anyway. Both ARE marked, correctly, and nothing said so. A column whose
    behaviour is wider than its docstring is the shape a later lane "corrects"
    by narrowing the code to match the words.
    """
    from core.tenancy import tenant_context
    from apps.metering import models as metering_models

    with tenant_context(brazos.id):
        _connect_city(brazos, dana)  # a HEALTHY City — this is the point

        # (a) she never searched: no session, no candidates looked at.
        typed_only = gis.create_premises(
            dana,
            brazos.id,
            parcel=None,
            typed=_form(dana, address_line="900 Riverside Dr"),
        )
        assert typed_only["gis_unchecked"] is True
        assert typed_only["gis_parcel_id"] is None

        # (b) she searched, saw four candidates, and typed her own anyway.
        found = gis.search(brazos.id, query="1408 Pec")
        assert len(found["candidates"]) == 4
        her_own = gis.create_premises(
            dana,
            brazos.id,
            parcel=None,
            typed=_form(dana, address_line="1408 Pecan Terrace"),
            session_id=found["session"],
        )
        assert her_own["gis_unchecked"] is True

        # (c) and the pick is still the one case that is NOT marked.
        picked = gis.create_premises(
            dana, brazos.id, parcel="88214", typed=_form(dana)
        )
        assert picked["gis_unchecked"] is False
        assert picked["gis_parcel_id"] == "88214"

        marked = metering_models.Premises.objects.filter(
            tenant_id=brazos.id, gis_unchecked=True
        ).count()
        assert marked == 2, "two of the three writes carry the mark"


@pytest.mark.django_db
def test_def_int_4266_a_form_may_not_send_the_mark_itself(brazos, dana):
    """A client posting `gis_unchecked: false` past an unreachable City would
    erase the ruling from the one row it is about.

    ⚠ **THE PARCEL HALF OF THIS CASE WAS REVERSED ON 2026-09-17
    (`DEF-MET-5604`), AND THE MARK HALF IS UNTOUCHED.** It used to assert
    `premises["gis_parcel_id"] is None` — a parcel a clerk typed past an
    unreachable City was thrown away, the save answered 201, and nothing said
    so. That is not what either ruling asks for: `OQ-INT-1471` ruled
    2026-09-04 option (b) *"type it, marked unchecked"*, and the PO ruled it
    again on 2026-09-17 (`CR-115-BRC05` R24) — **let them type it, mark it
    UNVERIFIED, the sync fixes it later**. The MARK is what makes a typed key
    distinguishable from a confirmed one, and the mark is still ours to set.
    """
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        _connect_city(brazos, dana, base_url=SLOW_CITY)
        premises = gis.create_premises(
            dana,
            brazos.id,
            parcel=None,
            typed={
                **_form(dana, address_line="1408 Pecan St"),
                "gis_unchecked": False,
                "gis_parcel_id": "99999",
                # The City's own word for its own record. A clerk cannot know
                # it, so a typed one would be indistinguishable from a real one
                # — this stays refused whichever branch the write takes.
                "gis_status": "INVENTED",
            },
        )
        # THE MARK IS OURS AND THE FORM CANNOT MOVE IT.
        assert premises["gis_unchecked"] is True
        # THE CITY'S OWN STATUS IS STILL NOT A THING A FORM MAY STATE.
        assert premises["gis_status"] is None
        # …AND THE PARCEL THE CLERK TYPED IS KEPT (`DEF-MET-5604`, R24).
        assert premises["gis_parcel_id"] == "99999"


@pytest.mark.django_db
def test_def_met_5604_a_picked_candidate_still_overrides_what_a_form_sent(brazos, dana):
    """On the PICKED branch the City has spoken, and what it said is written.

    The typed branch now carries three fields forward (`DEF-MET-5604`), so the
    question *does that leak into the branch where the City answered* has to be
    asked out loud rather than assumed from reading the `if`. A form that sends
    its own parcel while a candidate is picked must not be able to write it.
    """
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        _connect_city(brazos, dana)
        premises = gis.create_premises(
            dana,
            brazos.id,
            parcel=gis_fixtures.PECAN_ST["parcel"],
            typed={
                **_form(dana, address_line="1408 Pecan St"),
                "gis_parcel_id": "SNEAKED-IN",
                "gis_unchecked": True,
            },
        )
        assert premises["gis_parcel_id"] == gis_fixtures.PECAN_ST["parcel"]
        assert premises["gis_unchecked"] is False


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 · the generated Content-Security-Policy
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc5_the_policy_names_exactly_the_registered_tile_host_and_nothing_else(brazos, dana):
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        # ⚠ **THIS BLOCK ASSERTED THE DEFECT UNTIL 2026-09-06 (`DEF-INT-4287`).**
        # It read *"Before anything is connected, the policy is the CLOSED one"*
        # and checked `policy_for(...) == BASE_POLICY` — which was true, and was
        # the state EVERY tenant of the deployment was in, because nothing on
        # the provisioning path has ever created these rows. Meanwhile
        # `AssetMapTab.tsx` fell back to Esri's host for exactly that tenant, so
        # the browser refused every tile and the asset map was a grey rectangle.
        # `BASE_POLICY` itself is unchanged and still names no third-party host;
        # what changed is that a REGISTERED browser operation with a shipped
        # default is no longer treated as unregistered.
        assert "arcgisonline" not in page_policy.BASE_POLICY
        assert page_policy.tile_host(brazos.id) == live_calls.ESRI_TILE_HOST
        assert page_policy.hosts_for(brazos.id)["img-src"] == [live_calls.ESRI_TILE_HOST]

        live_calls.provision(dana, brazos.id)
        policy = page_policy.policy_for(brazos.id)
        assert "https://server.arcgisonline.com" in policy
        hosts = page_policy.hosts_for(brazos.id)
        assert hosts["img-src"] == ["https://server.arcgisonline.com"]
        # The SERVER's own outbound host is not in a page policy — no browser
        # governs our process, so granting it would widen for nothing.
        assert "geocoding.geo.census.gov" not in policy


@pytest.mark.django_db
def test_tc5_changing_the_host_on_the_connection_changes_the_policy(brazos, dana):
    """`R-7` — a city that runs its own map server costs ONE field, not a
    code change. The tile URL the browser fetches and the origin the policy
    permits come from one row."""
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        live_calls.provision(dana, brazos.id)
        row = integration_services.connection_for(brazos.id, "map_tiles_public")
        row.config = {"base_url": "https://tiles.brazosbend.example"}
        row.save(update_fields=["config", "updated_at"])

        policy = page_policy.policy_for(brazos.id)
        assert "https://tiles.brazosbend.example" in policy
        assert "arcgisonline" not in policy
        assert live_calls.host_for(brazos.id, "map_tiles_public") == (
            "https://tiles.brazosbend.example"
        )


@pytest.mark.django_db
def test_tc5_a_connection_switched_off_leaves_the_policy_closed(brazos, dana):
    """A switch that a policy ignored would be a decorative switch."""
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        live_calls.provision(dana, brazos.id)
        row = integration_services.connection_for(brazos.id, "map_tiles_public")
        row.enabled = False
        row.save(update_fields=["enabled", "updated_at"])
        assert page_policy.policy_for(brazos.id) == page_policy.BASE_POLICY


@pytest.mark.django_db
def test_def_int_4256_one_connection_with_two_hosts_puts_the_TILE_one_in_the_policy(
    brazos, dana
):
    """⚠ **FOUND BY READING A REAL RESPONSE HEADER, AND NOTHING ELSE COULD.**

    `gis_esri` is one relationship with one city and TWO addresses: an address
    service our server calls (`base_url`) and a tile server the BROWSER draws
    from (`tile_url`). The generator read `base_url` for every browser
    operation, so the header permitted the ADDRESS service as an image source
    and did not permit the tile server at all — the city's own map blocked, and
    the wrong host allowed, in one line. Every test passed, because every test
    asserted a provider with exactly one host.
    """
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        connection = _connect_city(brazos, dana)
        connection.config = {
            "base_url": CITY,
            "tile_url": "https://tiles.brazosbend.example",
        }
        connection.save(update_fields=["config", "updated_at"])

        hosts = page_policy.hosts_for(brazos.id)
        # ⚠ **AMENDED 2026-09-06 (`DEF-INT-4287`).** This read `== ["https://
        # tiles.brazosbend.example"]`, which folded two facts into one: *the
        # city's TILE server is permitted* — this case's subject — and *nothing
        # else is*, which was the defect. `map_tiles_public` is untouched here
        # and still offers its shipped default, so `img-src` now holds two
        # origins and BOTH are correct. The assertions name what is in and what
        # is out rather than the length of the list.
        assert "https://tiles.brazosbend.example" in hosts["img-src"]
        assert page_policy.tile_host(brazos.id) == "https://tiles.brazosbend.example", (
            "a utility that connected its OWN city's tile server must be drawn "
            "that one, not whatever sorted first"
        )
        policy = page_policy.policy_for(brazos.id)
        assert "gis.brazosbend.example" not in policy, (
            "the ADDRESS service is our server's host and has no business being "
            "an image source"
        )


@pytest.mark.django_db
def test_def_int_4256_a_connection_with_no_tile_server_contributes_no_host(brazos, dana):
    """Fails closed (hard-won law 3): the permissive answer is earned.

    ⚠ **AMENDED 2026-09-06 (`DEF-INT-4287`).** It used to assert `hosts_for ==
    {}`, which folded two facts into one: *the city gave us no tile server* and
    *nobody may draw a basemap at all*. The first is what this case is about;
    the second was the defect. `map_tiles_public` is untouched here and still
    offers its shipped default, so the assertions below name the CITY's absence
    rather than the emptiness of the answer.
    """
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        _connect_city(brazos, dana)  # base_url only — no `tile_url`
        assert page_policy.hosts_for(brazos.id)["img-src"] == [live_calls.ESRI_TILE_HOST]
        policy = page_policy.policy_for(brazos.id)
        assert "gis.brazosbend.example" not in policy
        assert page_policy.tile_host(brazos.id) == live_calls.ESRI_TILE_HOST


def test_def_int_4256_the_manifest_declares_which_field_holds_each_host():
    from apps.integrations.registry import REGISTRY

    operations = {one.name: one for one in REGISTRY.get("gis_esri").operations}
    assert operations["map_tiles"].host_field == "tile_url"
    assert operations["address_search"].host_field == "base_url"


@pytest.mark.django_db
def test_def_int_4287_a_tenant_that_has_connected_nothing_gets_the_host_the_map_will_fetch(
    brazos,
):
    """⚠ **THE DEFECT, IN ONE CASE — AND IT WAS EVERY TENANT.**

    The Product Owner reported it from the deployed build `v2.208.1`: *"in
    previous version Map in asset was working now it is not"*. A flat grey
    rectangle with working zoom controls and the SVG markers still on it, which
    is precisely what a browser draws when the tile IMAGES are refused and the
    vector overlay is not.

    Nothing on the tenant-provisioning path creates a `map_tiles_public` row —
    `live_calls.provision` is called by ONE management command and by no
    production code, though its own docstring says otherwise (hard-won law 1) —
    so every tenant was in this state, and `AssetMapTab.tsx` fell back to a host
    this policy forbade.

    **The two must name the same host or the map cannot draw**, so this asserts
    the identity rather than either half.
    """
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        assert integration_services.connection_for(brazos.id, "map_tiles_public") is None
        host = page_policy.tile_host(brazos.id)
        assert host == live_calls.ESRI_TILE_HOST
        # The host the SCREEN will fetch is inside the origin the POLICY permits.
        assert host in page_policy.policy_for(brazos.id)
        described = page_policy.described(brazos.id)
        assert described["tile_host"] == host
        assert host in described["hosts"]["img-src"]
        tiles = [
            row
            for row in described["browser_operations"]
            if row["provider_key"] == "map_tiles_public"
        ]
        assert [row["source"] for row in tiles] == [page_policy.SOURCE_DEFAULT]


@pytest.mark.django_db
def test_def_int_4287_a_switched_off_basemap_leaves_the_screen_nothing_to_draw(brazos, dana):
    """*Off* must be a CHOICE the screen can see, not a grey square.

    A connection row suppresses the shipped default in every state, so the
    switch keeps meaning something — and `tile_host` answering `None` is what
    lets the map draw no tile layer and say so, instead of looking exactly like
    the defect above.
    """
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        live_calls.provision(dana, brazos.id)
        row = integration_services.connection_for(brazos.id, "map_tiles_public")
        row.enabled = False
        row.save(update_fields=["enabled", "updated_at"])

        assert page_policy.tile_host(brazos.id) is None
        assert page_policy.policy_for(brazos.id) == page_policy.BASE_POLICY


@pytest.mark.django_db
def test_def_int_4287_the_tile_host_is_the_operations_own_and_not_the_first_of_img_src(
    brazos, dana
):
    """⚠ **`hosts["img-src"][0]` IS A COIN TOSS DRESSED AS A LOOKUP**, and it is
    what the map read until 2026-09-06.

    `img-src` is a DIRECTIVE. Here it holds two origins — the city's own tile
    server, which this utility has connected, and `map_tiles_public`'s shipped
    default, which it has not. Sorted, the shipped default comes FIRST, so the
    old expression drew Esri's tiles for a utility that had gone to the trouble
    of pointing the map at its own city (`R-7`). A utility's own connection wins.
    """
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        connection = _connect_city(brazos, dana)
        connection.config = {"base_url": CITY, "tile_url": "https://tiles.brazosbend.example"}
        connection.save(update_fields=["config", "updated_at"])

        hosts = page_policy.hosts_for(brazos.id)["img-src"]
        assert hosts == sorted(hosts)
        assert hosts[0] == live_calls.ESRI_TILE_HOST, "the sorted first is NOT the map's"
        assert page_policy.tile_host(brazos.id) == "https://tiles.brazosbend.example"


def test_tc5_a_directive_that_gains_a_host_loses_none():
    """`frame-src 'none' https://cards.example` reads as NO FRAMES AT ALL, and
    it reads that way silently — the shape of a check that cannot fail.

    ⚠ **`frame-src`'s BASE IS `'self'` SINCE `DEF-INT-4410`** — this product
    frames its own bill PDF and embeds its own kept documents, and `'none'`
    blanked both screens. So a granted host now lands BESIDE `'self'` instead
    of replacing `'none'`, and this test's original subject moved out from
    under it.

    The filter itself is unchanged and still load-bearing for every directive
    that does ship `'none'`, so that half is asserted on one of them rather
    than deleted — and the property both halves are really about, *a host is
    never rendered beside `'none'`*, is asserted over the whole policy.
    """
    rendered = page_policy.policy({"frame-src": ["https://cards.example"]})
    frame = next(one for one in rendered.split("; ") if one.startswith("frame-src"))
    assert frame == "frame-src 'self' https://cards.example"

    dropped = page_policy.policy({"base-uri": ["https://cards.example"]})
    base = next(one for one in dropped.split("; ") if one.startswith("base-uri"))
    assert base == "base-uri https://cards.example", "the 'none'-dropping filter is gone"

    for directive in (*rendered.split("; "), *dropped.split("; ")):
        assert not ("'none'" in directive and "https://" in directive), directive


@pytest.mark.django_db
def test_the_page_policy_endpoint_answers_without_a_session(brazos, dana):
    """A document is served before anybody signs in, and an SPA does not reload
    afterwards — see `page_policy.py`'s docstring."""
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        live_calls.provision(dana, brazos.id)

    response = api_call(
        integrations_api.page_policy_view, "get", "/api/brazosbend/integrations/page-policy",
        tenant=brazos,
    )
    assert response.status_code == 200
    assert "https://server.arcgisonline.com" in response.data["policy"]
    assert response.data["hosts"]["img-src"] == ["https://server.arcgisonline.com"]


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 · the two reaches, tested separately
# ═══════════════════════════════════════════════════════════════════════════


def test_tc6_the_server_reach_is_one_real_lookup_not_a_key_parse():
    """`BR-INT-019` — *"a test that cannot fail the way production fails is
    worse than no test"*. One real lookup, and the sentence counts what came
    back."""
    adapter = GisCityAdapter(transport=gis_fixtures.recorded_transport)
    view = ConnectionView(
        provider_key="gis_esri", environment="production", config={"base_url": CITY}
    )
    good = adapter.test(view, {}, recipient="1408 Pec")
    assert good.ok is True
    assert "4 candidates" in good.sentence


def test_tc6_the_test_button_waits_longer_than_a_keystroke_and_that_is_deliberate():
    """⚠ **THE MANUAL TEST'S DEADLINE IS NOT `C15`'s BUDGET, AND THIS CASE
    EXISTS BECAUSE THE FIRST DRAFT ASSUMED IT WAS.** It asserted that *Test it
    now* FAILS against the 4,000 ms City — and it does not, correctly: a person
    who pressed a button is willing to wait five seconds for an answer, where a
    person mid-keystroke is not willing to wait one. Two different numbers for
    two different waits, and asserting the wrong one would have made the button
    report a healthy City as broken."""
    adapter = GisCityAdapter(transport=gis_fixtures.recorded_transport)
    slow_view = ConnectionView(
        provider_key="gis_esri", environment="production", config={"base_url": SLOW_CITY}
    )
    answer = adapter.test(slow_view, {}, recipient="1408 Pec")
    assert answer.ok is True, "four seconds is inside the manual test's five"

    # The SEARCH's budget is the one a keystroke gets, and the same City fails
    # it — which is what makes the breaker open on the screen.
    with pytest.raises(ProviderTimeout):
        adapter.search(slow_view, {}, "1408 Pec", timeout_s=gis.budget_seconds())


def test_tc6_the_browser_half_is_declared_separately_from_the_server_half():
    """*"the test modal tests the page's reach separately from the server's"*
    (`BR-INT-048`). The endpoint says which operations the BROWSER runs, so a
    screen can offer two results without a per-provider branch."""
    hosts = page_policy.browser_operations()
    keys = {(manifest.key, operation.name) for manifest, operation in hosts}
    assert ("gis_esri", "map_tiles") in keys
    assert ("gis_esri", "address_search") not in keys, "the search is OURS to place"


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 · tenant isolation — two cities, two policies
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc7_each_search_goes_to_its_own_city_and_each_policy_is_its_own(
    brazos, dana, lonestar, erin
):
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        _connect_city(brazos, dana, base_url=CITY)
        live_calls.provision(dana, brazos.id)
        row = integration_services.connection_for(brazos.id, "map_tiles_public")
        row.config = {"base_url": "https://tiles.brazosbend.example"}
        row.save(update_fields=["config", "updated_at"])
        brazos_policy = page_policy.policy_for(brazos.id)

    with tenant_context(lonestar.id):
        _connect_city(lonestar, erin, base_url=f"https://{gis_fixtures.EMPTY_HOST}/addr")
        live_calls.provision(erin, lonestar.id)
        lonestar_policy = page_policy.policy_for(lonestar.id)
        # The empty City answers, with nothing — a real state, not a failure.
        answer = gis.search(lonestar.id, query="1408 Pec")
        assert answer["reachable"] is True
        assert answer["candidates"] == []

    assert "tiles.brazosbend.example" in brazos_policy
    assert "tiles.brazosbend.example" not in lonestar_policy
    assert "server.arcgisonline.com" in lonestar_policy

    with tenant_context(brazos.id):
        found = gis.search(brazos.id, query="1408 Pec")
        assert len(found["candidates"]) == 4, "Brazos Bend's own city still answers"


# ═══════════════════════════════════════════════════════════════════════════
# The two live calls that had no connection record (DEF-INT-4244 · 4245)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_two_live_calls_gain_connection_records_and_provisioning_never_overwrites(
    brazos, dana
):
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        first = live_calls.provision(dana, brazos.id)
        assert first == {"geocoder_census": "created", "map_tiles_public": "created"}

        row = integration_services.connection_for(brazos.id, "map_tiles_public")
        row.config = {"base_url": "https://tiles.brazosbend.example"}
        row.save(update_fields=["config", "updated_at"])

        second = live_calls.provision(dana, brazos.id)
        assert second == {"geocoder_census": "kept", "map_tiles_public": "kept"}
        assert live_calls.host_for(brazos.id, "map_tiles_public") == (
            "https://tiles.brazosbend.example"
        ), "a host somebody chose is never reset by provisioning"


# ═══════════════════════════════════════════════════════════════════════════
# The routes resolve through the REAL URLconf
# ═══════════════════════════════════════════════════════════════════════════


def test_the_three_wave_m_routes_resolve_and_page_policy_is_not_swallowed_by_the_key_route():
    """⚠ `integrations/page-policy` is two segments and so is
    `integrations/<str:key>`. `config/urls.py`'s own comment records the same
    collision costing `integrations/subprocessors` a 405, found by a browser."""
    from django.urls import resolve

    assert resolve("/api/brazosbend/integrations/page-policy").func is (
        integrations_api.page_policy_view
    )
    assert resolve("/api/brazosbend/integrations/gis_esri/address-search").func is (
        integrations_api.address_search
    )
    assert resolve("/api/brazosbend/integrations/gis_esri/premises").func is (
        integrations_api.gis_premises
    )


@pytest.mark.django_db
def test_the_search_route_answers_200_with_candidates_and_never_202(brazos, dana):
    """`C15` — an inline operation is a latency budget, not a job. Every other
    provider call in this API answers 202 with a poll url; this one must not."""
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        _connect_city(brazos, dana)

    response = api_call(
        integrations_api.address_search,
        "get",
        "/api/brazosbend/integrations/gis_esri/address-search",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        query={"q": "1408 Pec"},
        key="gis_esri",
    )
    assert response.status_code == 200
    assert "job_id" not in response.data
    assert "status_url" not in response.data
    assert len(response.data["candidates"]) == 4


@pytest.mark.django_db
def test_the_search_route_refuses_any_other_provider_key_as_an_absent_resource(brazos, dana):
    response = api_call(
        integrations_api.address_search,
        "get",
        "/api/brazosbend/integrations/email_smtp/address-search",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        query={"q": "1408 Pec"},
        key="email_smtp",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_def_int_4273_the_same_candidate_twice_is_a_refusal_and_not_a_500(brazos, dana):
    """⚠ **EVERY CASE IN THIS FILE CREATED EACH PARCEL EXACTLY ONCE.**

    ⚠ **WHAT THIS REFUSAL STANDS ON CHANGED ON 2026-09-17 (`BR-MET-1173`).**
    It used to stand on a DATABASE CONSTRAINT: `premises` carries
    `uq_premises_tenant_external_ref_ci` — one value per tenant — and the City
    create path wrote the parcel into `external_ref` with no check
    and no catch, so the SECOND pick of the same candidate came back as a
    `500` with a psycopg message in it. Picking the same row twice is ordinary:
    two clerks, a re-entry, a reloaded page. It was found by running the
    walkthrough script a second time, which is the only thing that could.
    """
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        _connect_city(brazos, dana)
        first = gis.create_premises(dana, brazos.id, parcel="88214", typed=_form(dana))
        assert first["gis_parcel_id"] == "88214"

        with pytest.raises(gis.GisRefusal) as refusal:
            gis.create_premises(dana, brazos.id, parcel="88214", typed=_form(dana))
        assert refusal.value.message_key == gis.REFUSAL_PARCEL_TAKEN

        # …and the route turns it into a refusal a screen can draw, not a 500.
        response = api_call(
            integrations_api.gis_premises,
            "post",
            "/api/brazosbend/integrations/gis_esri/premises",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            data={"parcel": "88214", "premises": _form(dana)},
            key="gis_esri",
        )
        assert response.status_code == 409 or response.status_code == 422, response.data
        assert response.data["message_key"] == gis.REFUSAL_PARCEL_TAKEN


@pytest.mark.django_db
def test_def_int_4273_the_check_is_case_insensitive_like_the_index_it_guards(brazos, dana):
    """A check stricter than the constraint in front of it passes and then
    fails at the write — the same defect wearing a check."""
    from core.tenancy import tenant_context
    from apps.metering import selectors as metering_selectors

    with tenant_context(brazos.id):
        _connect_city(brazos, dana)
        gis.create_premises(dana, brazos.id, parcel="88214", typed=_form(dana))
        # ⚠ **A DIFFERENT SELECTOR SINCE 2026-09-17 (`BR-MET-1173`).** The
        # parcel question is `premises_gis_parcel_taken`;
        # `premises_external_ref_taken` still answers the IMPORT-key
        # question, which is a different fact that kept its own column.
        assert metering_selectors.premises_gis_parcel_taken("88214") is True
        assert metering_selectors.premises_gis_parcel_taken("88-214") is False
        assert metering_selectors.premises_gis_parcel_taken("") is False
        assert metering_selectors.premises_gis_parcel_taken(None) is False


@pytest.mark.django_db
def test_def_int_4267_a_billing_clerk_can_search_and_can_create_from_a_candidate(
    brazos, dana
):
    """⚠ **THE ONLY PERSON THIS SCREEN IS FOR WAS REFUSED BY BOTH ROUTES.**

    They were given `SettingsReadAnyWriteSystemAdmin` because they sit among
    the connect/test/credential routes, which really ARE settings. That class
    allows `{system_admin, executive}` to read and only a System Admin to
    write, because A4's `settings_lookups` row gives a **Billing Clerk no cell
    at all** — so she got `403` on the SEARCH, the panel caught it, decided
    this tenant had no City and removed itself. Silently, for the one role the
    premises wizard exists for.

    Every case in this file drove `gis.search` and `gis.create_premises`
    directly or through an admin, and the browser walkthrough signed in as an
    admin too, so nothing in the wave could see it. These two go through the
    ROUTE, as the clerk's browser does.
    """
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        _connect_city(brazos, dana)

    found = api_call(
        integrations_api.address_search,
        "get",
        "/api/brazosbend/integrations/gis_esri/address-search",
        user=dana.user,
        role="billing_clerk",
        tenant=brazos,
        query={"q": "1408 Pec"},
        key="gis_esri",
    )
    assert found.status_code == 200, found.data
    assert len(found.data["candidates"]) == 4

    with tenant_context(brazos.id):
        typed = _form(dana)
    created = api_call(
        integrations_api.gis_premises,
        "post",
        "/api/brazosbend/integrations/gis_esri/premises",
        user=dana.user,
        role="billing_clerk",
        tenant=brazos,
        data={"parcel": "88214", "session": found.data["session"], "premises": typed},
        key="gis_esri",
    )
    assert created.status_code == 201, created.data
    assert created.data["gis_parcel_id"] == "88214"
    assert created.data["gis_unchecked"] is False


@pytest.mark.django_db
def test_def_int_4267_the_write_still_refuses_twice_for_a_role_that_may_not_create(
    brazos, dana
):
    """Opening the ROUTE to any tenant role does not open the WRITE.

    `metering.services.create_premises` carries
    `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` (`BR-MET-035`), which is why
    `POST /premises` is `AnyTenantRole` too: the service is the narrow guard
    and the route must not be narrower than it in the OTHER direction either.
    An Executive may look at premises and may not create one.
    """
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        _connect_city(brazos, dana)
        typed = _form(dana)

    refused = api_call(
        integrations_api.gis_premises,
        "post",
        "/api/brazosbend/integrations/gis_esri/premises",
        user=dana.user,
        role="executive",
        tenant=brazos,
        data={"parcel": None, "premises": typed},
        key="gis_esri",
    )
    assert refused.status_code == 403, refused.data


@pytest.mark.django_db
def test_the_middleware_puts_the_generated_policy_on_an_api_response(brazos, dana, client):
    """The SECOND of the two places. The one a browser enforces is the
    document's, set by `07-frontend/server.mjs`."""
    from apps.integrations.middleware import HEADER, PagePolicyMiddleware

    calls = {}

    class _Response(dict):
        pass

    def _get_response(request):
        calls["seen"] = True
        return _Response()

    from django.conf import settings

    from apps.integrations.middleware import _with_app_ancestors

    middleware = PagePolicyMiddleware(_get_response)
    response = middleware(object())
    assert calls["seen"] is True
    # No tenant context — it fails CLOSED to the base policy, plus the ONE
    # thing `DEF-INT-9707` adds on every API response: the app origins the API
    # already trusts with its session (`CORS_ALLOWED_ORIGINS`), on
    # `frame-ancestors` only.
    #
    # ⚠ **THIS ASSERTED `== BASE_POLICY` AND WAS RED FROM 2026-10-05 TO
    # 2026-10-07** (GIS Lane D, PO GIS review gap 10). `9b6b8ae50` added
    # `_with_app_ancestors` on purpose and covered it in
    # `test_def_int_9707_frame_ancestors.py`; `b82615107` (2026-09-28) had
    # given the test settings an app origin. The HEADER is right and this
    # line was stale — two lanes reported it as a known red and neither filed
    # it. What it now pins is the part that matters: nothing but
    # `frame-ancestors` moved, and no host was granted.
    assert response[HEADER] == _with_app_ancestors(page_policy.BASE_POLICY)
    sent = dict(part.strip().split(" ", 1) for part in response[HEADER].split(";"))
    base = dict(part.strip().split(" ", 1) for part in page_policy.BASE_POLICY.split(";"))
    assert {k: v for k, v in sent.items() if k != "frame-ancestors"} == {
        k: v for k, v in base.items() if k != "frame-ancestors"
    }
    assert sent["frame-ancestors"].split() == ["'self'", *settings.CORS_ALLOWED_ORIGINS]


@pytest.mark.django_db
def test_def_int_5600_the_point_key_lands_on_the_unit_the_create_makes(brazos, dana):
    """`FULLPIN` → `unit.gis_point_id`, read back out of the database.

    ⚠ **THIS READS THE COLUMN AND NOT THE RESPONSE.** The create's own answer is
    the server's claim about itself; `units.gis_point_id` being NULL on every
    property was invisible to the migration, the model, the selector and the
    screen, all of which were green.
    """
    from core.tenancy import tenant_context
    from apps.metering import models as metering_models

    with tenant_context(brazos.id):
        _connect_city(brazos, dana)
        gis.create_premises(
            dana,
            brazos.id,
            parcel="88214",
            typed={**_form(dana), "units": [{"label": "1"}]},
        )
        unit = metering_models.Unit.objects.get(tenant_id=brazos.id)
        assert unit.gis_point_id == "88214-0001"
        assert unit.gis_status == "ACTIVE"
        premises = metering_models.Premises.objects.get(tenant_id=brazos.id)
        assert premises.gis_parcel_id == "88214"


@pytest.mark.django_db
def test_def_int_5600_several_units_take_NO_point_key_rather_than_a_guessed_one(brazos, dana):
    """One picked candidate IS one address point, so it names at most one unit.

    With four flats the City's single point belongs to one of them and we do not
    know which. Writing it to all four would be four claims where the City made
    one; writing it to the first would be a guess a reconciliation run could
    never tell from a fact. The nightly run fills the rest, point by point.
    """
    from core.tenancy import tenant_context
    from apps.metering import models as metering_models

    with tenant_context(brazos.id):
        _connect_city(brazos, dana)
        gis.create_premises(
            dana,
            brazos.id,
            parcel="88214",
            typed={**_form(dana), "units": [{"label": "1"}, {"label": "2"}]},
        )
        units = list(metering_models.Unit.objects.filter(tenant_id=brazos.id))
        assert len(units) == 2
        assert [u.gis_point_id for u in units] == [None, None]
        # …and the PREMISES key is unaffected: the parcel is the building's.
        assert metering_models.Premises.objects.get(tenant_id=brazos.id).gis_parcel_id == "88214"


@pytest.mark.django_db
def test_def_int_5599_a_socket_that_never_opens_is_a_refusal_and_it_counts(brazos, dana):
    """An UNREACHABLE City, not a slow one — and the two are different branches.

    ⚠ **NO FIXTURE IN THIS FILE COULD PRODUCE THIS STATE UNTIL 2026-09-17, AND
    THAT IS THE WHOLE ESCAPE.** Every test of this path injects a fake transport,
    and a fake transport either returns rows or raises `ProviderTimeout` — the
    two outcomes the code already handled. The third outcome, a socket that never
    opens, is the one a real network produces and the one no fixture produced, so
    42 passing tests said nothing about it. `urllib` raises
    `URLError(ConnectionRefusedError(...))` for a refused connection and
    `URLError(OSError('Tunnel connection failed: 403 Forbidden'))` for this
    environment's egress proxy; both are `OSError`, neither is `TimeoutError`.

    THREE THINGS ARE ASSERTED AND EACH ONE WAS SEPARATELY BROKEN:
      1. the answer is `reachable: false` with the catalogue key the amber box
         renders — it used to be `500 SYS-INTERNAL`;
      2. `BR-INT-022`'s breaker COUNTED it — it used to read
         `consecutive_timeouts = 0` after four failing searches, so it could
         never open;
      3. nothing is written and the session is closed, as on the slow branch.
    """
    import urllib.error

    from core.tenancy import tenant_context
    from apps.integrations.adapters.gis_city import GisCityAdapter

    def refused(url, timeout_s):
        raise urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

    with tenant_context(brazos.id):
        connection = _connect_city(brazos, dana, base_url="https://city.invalid/addr")
        adapter = GisCityAdapter(transport=refused)
        view = ConnectionView(
            provider_key=connection.provider_key,
            environment=connection.environment,
            config=dict(connection.config or {}),
            label=connection.label,
        )
        # The ADAPTER's own answer: silence, translated into the runtime's word.
        with pytest.raises(ProviderTimeout):
            adapter.search(view, {}, "1408 Pec", timeout_s=1.0)

        # …and the whole path, through the real service, with the breaker read
        # back off `integration_connection.config`.
        import apps.integrations.gis_fixtures as fixtures

        original = fixtures.transport_for
        fixtures.transport_for = lambda base_url: refused
        try:
            answer = gis.search(brazos.id, query="1408 Pec")
        finally:
            fixtures.transport_for = original

        assert answer["reachable"] is False
        assert answer["message_key"] == gis.REFUSAL_CITY_NOT_ANSWERING
        assert answer["candidates"] == []

        connection.refresh_from_db()
        breaker = dict(connection.config or {}).get("breaker") or {}
        assert int(breaker.get("consecutive_timeouts") or 0) >= 1, (
            "an unreachable City must move BR-INT-022's breaker; it read 0 after four"
        )


@pytest.mark.django_db
def test_def_int_5599_an_http_error_is_the_city_ANSWERING_and_does_not_touch_the_breaker(brazos, dana):
    """A `401` for a wrong key is the City talking, so it is not this branch.

    `HTTPError` is a subclass of `URLError`, so an adapter that caught the
    superclass first would count a credential problem towards a breaker built
    for a provider that is not there — and then stop dialling a City that was
    answering perfectly well.
    """
    import io
    import urllib.error

    from core.tenancy import tenant_context
    from apps.integrations.adapters.gis_city import GisCityAdapter

    def unauthorised(url, timeout_s):
        raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, io.BytesIO(b""))

    with tenant_context(brazos.id):
        connection = _connect_city(brazos, dana, base_url="https://city.invalid/addr")
        adapter = GisCityAdapter(transport=unauthorised)
        view = ConnectionView(
            provider_key=connection.provider_key,
            environment=connection.environment,
            config=dict(connection.config or {}),
            label=connection.label,
        )
        # ⚠ `HTTPError` itself until 2026-10-07 — re-raised bare, and nothing
        # above caught it (`DEF-INT-5620`). The adapter translates it now; it
        # is still NOT `ProviderTimeout`, which is the half this test guards.
        from apps.integrations.adapters.gis_city import CityRefused

        with pytest.raises(CityRefused) as refused:
            adapter.search(view, {}, "1408 Pec", timeout_s=1.0)
        assert not isinstance(refused.value, ProviderTimeout)
        assert refused.value.status == 401
        # `test()` calls it a refusal in words, and never *not answering*.
        answer = adapter.test(view, {}, recipient="1408 Pec")
        assert answer.ok is False
        assert answer.sentence == "The city refused the lookup."


@pytest.mark.django_db
def test_def_int_5603_the_cap_is_said_out_loud_rather_than_applied_in_silence(brazos, dana):
    """Sixteen matches in, eight out, and the answer SAYS it cut them.

    ⚠ **THE FIXTURE HAS TO BE BIGGER THAN THE CAP OR THE CASE CANNOT FAIL.** No
    fixture in this file returned more than eight rows, so the branch that drops
    the ninth was never taken and a complete-looking list of eight was
    indistinguishable from all the matches there were.
    """
    from core.tenancy import tenant_context
    from apps.integrations.adapters.gis_city import CANDIDATE_CAP

    rows = [
        {"parcel": f"09-09-29-{n:03d}", "point": f"09-09-29-{n:03d}-0001",
         "address": f"500 Main St Unit {n}", "city": "Ann Arbor", "state": "MI",
         "zip": "48104", "lat": "42.2796", "lng": "-83.7438", "score": "90",
         "status": "ACTIVE"}
        for n in range(1, 17)
    ]

    def many(url, timeout_s):
        return {"candidates": rows}

    import apps.integrations.gis_fixtures as fixtures

    with tenant_context(brazos.id):
        _connect_city(brazos, dana, base_url="https://city.invalid/addr")
        original = fixtures.transport_for
        fixtures.transport_for = lambda base_url: many
        try:
            answer = gis.search(brazos.id, query="500 Main")
        finally:
            fixtures.transport_for = original

    assert len(answer["candidates"]) == CANDIDATE_CAP == 8
    assert answer["truncated"] is True, "sixteen matches were cut to eight in silence"

    # …and a list that was NOT cut says nothing, because a notice on every
    # search is a notice a clerk stops reading.
    def few(url, timeout_s):
        return {"candidates": rows[:3]}

    with tenant_context(brazos.id):
        fixtures.transport_for = lambda base_url: few
        try:
            small = gis.search(brazos.id, query="500 Main")
        finally:
            fixtures.transport_for = original
    assert len(small["candidates"]) == 3
    assert small["truncated"] is False


# ═══════════════════════════════════════════════════════════════════════════
# 2026-09-17 · `DEF-INT-5601` — THE ENDPOINT RANKS, AND IT USED TO SERVE THE
# CITY'S OWN ORDER
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE CAP AND THE MISSING ORDER WERE ONE DEFECT WEARING TWO NAMES.** The
# adapter asks the City for nine rows and `shown_and_more` keeps eight, and
# until this wave nothing sorted them — a FeatureServer answers in the layer's
# own order, which is essentially insertion order. So *"8 matches from the
# City's records"* was eight ARBITRARY rows, and a clerk typing `1408 Pecan St`
# could be shown eight addresses without `1408 Pecan St` among them, under a
# count line that reads as a total.
#
# `gis_search` — 295 lines of ranking, grouping and cap — was the module written
# for exactly this and had no importer outside its own test file.


def _scramble(monkeypatch, rows):
    """Put the recording in an order the endpoint must undo.

    ⚠ **A FIXTURE ALREADY IN THE RIGHT ORDER CANNOT FAIL** (hard-won law 7,
    habit 2): the shipped `RECORDED_CANDIDATES` happen to be declared best-first,
    so an assertion over them passes identically whether the endpoint ranks or
    hands back what it was given. These are declared WORST-first.
    """
    monkeypatch.setattr(gis_fixtures, "RECORDED_CANDIDATES", tuple(rows))


@pytest.mark.django_db
def test_def_int_5601_the_endpoint_puts_the_citys_own_relevance_first(
    brazos, dana, monkeypatch
):
    """A geocoder publishes a score, so THEIRS decides and no note is shown."""
    from core.tenancy import tenant_context

    _scramble(
        monkeypatch,
        [
            dict(gis_fixtures.RECORDED_CANDIDATES[2]),  # score 64
            dict(gis_fixtures.RECORDED_CANDIDATES[3]),  # score 58
            dict(gis_fixtures.RECORDED_CANDIDATES[0]),  # score 96
            dict(gis_fixtures.RECORDED_CANDIDATES[1]),  # score 91
        ],
    )
    with tenant_context(brazos.id):
        _connect_city(brazos, dana)
        answer = gis.search(brazos.id, query="1408 Pec")
        assert [one["parcel"] for one in answer["candidates"]] == [
            "88214", "88215", "88301", "88302",
        ]
        assert answer["ranking_note_key"] is None, (
            "the order is the City's own, so claiming it as ours would be a "
            "claim we cannot support"
        )


@pytest.mark.django_db
def test_def_int_5601_an_unscored_layer_is_ordered_by_us_and_the_screen_says_so(
    brazos, dana, monkeypatch
):
    """⚠ **THE ANN ARBOR SHAPE.** An ArcGIS `like` query returns no relevance.

    Nothing then sorts the rows but our own judgment, and the screen must say
    so — which is what `integrations.gis.our_ranking` is for. That key has been
    in all eleven catalogues since `CR-112` and was rendered by nothing.
    """
    from core.tenancy import tenant_context

    _scramble(
        monkeypatch,
        [
            {k: v for k, v in one.items() if k not in ("score", "score_scale")}
            for one in (
                gis_fixtures.RECORDED_CANDIDATES[2],   # 1408 Pecan Grove Rd
                gis_fixtures.RECORDED_CANDIDATES[3],   # 1408 Pecan St W
                gis_fixtures.RECORDED_CANDIDATES[0],   # 1408 Pecan St  ← wanted
            )
        ],
    )
    with tenant_context(brazos.id):
        _connect_city(brazos, dana)
        answer = gis.search(brazos.id, query="1408 Pecan St")
        assert answer["candidates"][0]["address_line"] == "1408 Pecan St", (
            "the row the clerk typed must not be third because the City "
            "happened to return it third"
        )
        assert answer["ranking_note_key"] == "integrations.gis.our_ranking"


@pytest.mark.django_db
def test_def_int_5601_a_search_with_nothing_in_it_claims_no_order(brazos, dana):
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        _connect_city(brazos, dana, base_url=f"https://{gis_fixtures.EMPTY_HOST}/addr")
        answer = gis.search(brazos.id, query="nowhere at all")
        assert answer["candidates"] == []
        assert answer["ranking_note_key"] is None
