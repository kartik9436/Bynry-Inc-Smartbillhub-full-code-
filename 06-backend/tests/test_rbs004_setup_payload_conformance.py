# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-016 · US-RBS-001 (EP-RBS-01) — CR-075: the SETUP payload half
#           of the conformance pair. Screens: RBS-004 (`S150`).
# Rules:    `07-endpoints.md` row 2 (`GET /runbooks/{key}`) and row 8
#           (`GET /runbooks/runs`) · `BR-RBS-038` (every edit mints a version) ·
#           B14 rule 31 (no database id is ever the visible value of a field).
# Tests:    this file WRITES the fixture;
#           `07-frontend/src/features/runbooks/setupConformance.test.tsx` READS
#           it, runs it through the real client, the real mapper and the real
#           screen, and asserts what a person can see.
# Impacts:  apps/runbooks/api.py::runbook_detail · apps/runbooks/selectors.py ·
#           07-frontend/src/features/runbooks/setupWire.ts · setupModel.ts
# ───────────────────────────────────────────────────────
"""THE SETUP PAYLOAD THE SCREEN ACTUALLY GETS, PINNED SO NEITHER SIDE CAN MOVE
ALONE.

⚠ **THIS FILE EXISTS BECAUSE OF `DEF-RBS-4308`, AND IT IS THE THIRD TIME THE
SAME SHAPE COST A SCREEN IN ONE DAY.** `DEF-RBS-4284`: the engine and the twelve
report blocks disagreed on ALL SIX payloads, both suites green, because only the
block NAMES were checked. `DEF-RBS-4285`: the same thing one level up on the
definition. Then this one, in the live product — `RBS-004` fetched
`GET /runbooks/{key}` as a `RunbookSetupView`, the endpoint served a server
shape, and **the screen threw in a real browser from 16:23 UTC on 2026-09-06**
with `tsc` green, 49 unit cases green and every gate green.

**The pattern each time is two declarations of one thing and nothing checking
them against each other.** `blocks/reportConformance.test.tsx` is what now
protects the report side; this pair is the same cure for the setup side.

WHY A FIXTURE FILE AND NOT A SNAPSHOT
--------------------------------------
The test below does not write the fixture on every run — it ASSERTS the
committed bytes still match what the endpoint serves, and regenerates only under
`RBS_WRITE_FIXTURE=1`. A fixture nobody regenerates deliberately is a fixture
that has stopped checking (hard-won law 7's *proved red, then never read*).

⚠ **WHAT IS NORMALISED, AND WHY THAT DOES NOT WEAKEN IT.** Three kinds of value
in this payload are different on every run and carry no shape information: run
uuids, timestamps, and the generated key of a copy. Comparing them would make
this test fail for reasons that have nothing to do with the contract, and a test
that cries wolf is a test people stop reading. So each is replaced by a fixed
stand-in BEFORE the comparison, in both directions, and everything else — every
key, every nesting level, every enum code, every null — is compared byte for
byte. **The thing that broke `RBS-004` was a missing KEY, not a changed value**,
and a missing key is exactly what survives normalisation.

⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY.** Asserting that the endpoint
answered `200` and stopping there — a `200` carrying `{}` passes that. So the
assertions below name the keys the RENDERER reads, out of the fixture, and the
front-end half then draws the whole payload through the real components and
requires values out of it to appear on screen. Neither half is enough on its
own, which is the point of a pair.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import re

import pytest
from django.utils import timezone

from apps.runbooks import api, models, services
from core.permissions import SYSTEM_ADMIN
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: The pair's shared file. It lives in the FRONT END, beside the test that reads
#: it, for the reason `blocks/__fixtures__/rbs001-report.json` gives: the reader
#: must be able to import it without a build step, and a fixture in two places
#: is two fixtures.
SETUP_FIXTURE = (
    pathlib.Path(__file__).resolve().parents[1].parent
    / "07-frontend"
    / "src"
    / "features"
    / "runbooks"
    / "__fixtures__"
    / "rbs004-setup.json"
)

UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:\d{2}|Z)$")

FIXED_UUID = "00000000-0000-4000-8000-000000000000"
FIXED_WHEN = "2026-09-06T07:00:00+00:00"


def _normalise(value):
    """Volatile values out, shape intact. See the module docstring."""
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalise(v) for v in value]
    if isinstance(value, str):
        if TIMESTAMP_RE.match(value):
            return FIXED_WHEN
        return UUID_RE.sub(FIXED_UUID, value)
    return value


def _wire(response):
    """The bytes that leave the server, not the dict the view handed DRF.

    ⚠ **`response.data` IS THE LAYER BELOW THE WIRE AND READING IT IS
    `DEF-WRK-4119`'s MISTAKE.** That dict still holds `datetime` and `UUID`
    objects; the renderer is what turns them into the strings a browser parses.
    A fixture built from `.data` would describe a shape the front end never
    sees.
    """
    response.render()
    return json.loads(response.content.decode("utf-8"))


@pytest.fixture()
def setup_payload(brazos, dana):
    """One runbook with a history, exactly as a clerk would have made it.

    Added from the shipped library, then edited — which is what puts two
    versions in the Activity tab with real `{field, from, to}` facts behind
    them (`BR-RBS-038`), and it is those facts the screen composes its sentence
    from. A runbook created straight through the ORM would have an empty
    Activity tab and this pair would then check nothing about the tab an auditor
    asks for first.
    """
    runbook = services.add_template(brazos.id, "configuration_check", actor_id=dana.id)
    services.update_runbook(runbook, {"cap": 400, "enabled": False}, actor_id=dana.id)
    runbook.refresh_from_db()

    # ⚠ **ONE CLOSED RUN, BECAUSE TWO OF THE SEVEN TABS ARE EMPTY WITHOUT ONE.**
    # `RBS-004.1`'s *Last run* block and `RBS-004.6`'s whole table read a run, so
    # a fixture with none would leave the pair checking five tabs while reporting
    # on seven — a declared blind spot with no number attached, which is the
    # shape hard-won law 7 names. It is written straight through the ORM rather
    # than executed: what the ENGINE emits is `rbs001-report.json`'s job, and
    # what this pair is about is the SETUP payload's shape.
    #
    # ⚠ **THE TWO ENDS OF THE DURATION ARE DERIVED FROM ONE MOMENT, AND THAT IS
    # NOT TIDINESS.** `selectors._took_seconds` subtracts them, so two separate
    # `timezone.now()` calls put a wall-clock float (`2e-06`, and a different one
    # every run) into the payload — a value the byte comparison below would
    # fail on for a reason that has nothing to do with the contract, which is
    # how a test starts crying wolf and stops being read.
    started = timezone.now()
    with tenant_ctx(brazos):
        models.RunbookRun.objects.create(
            tenant=brazos,
            runbook=runbook,
            version=runbook.current_version,
            status=models.RUN_STATUS_DONE,
            mode=models.MODE_DRY,
            trigger=models.TRIGGER_MANUAL,
            started_at=started,
            finished_at=started + datetime.timedelta(seconds=42),
            report=[],
            counts={"clean": 7, "blocked": 3},
        )

    detail = api_call(
        api.runbook_detail,
        "get",
        f"/api/{brazos.subdomain}/runbooks/{runbook.key}",
        user=dana.user,
        role=SYSTEM_ADMIN,
        tenant=brazos,
        key=runbook.key,
    )
    runs = api_call(
        api.runs_list,
        "get",
        f"/api/{brazos.subdomain}/runbooks/runs",
        user=dana.user,
        role=SYSTEM_ADMIN,
        tenant=brazos,
        query={"f.runbook": runbook.key, "page": 1, "per": 50},
    )
    assert detail.status_code == 200, detail.data
    assert runs.status_code == 200, runs.data
    return {"detail": _wire(detail), "runs": _wire(runs)}


def test_rbs004_setup_fixture_the_renderer_draws_is_current(setup_payload):
    """The committed fixture is what `GET /runbooks/{key}` serves today.

    Run with `RBS_WRITE_FIXTURE=1` to regenerate it after a deliberate change;
    the diff is then reviewed like any other, and
    `setupConformance.test.tsx` fails in the SAME COMMIT if the mapper can no
    longer read it.
    """
    rendered = (
        json.dumps(_normalise(setup_payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )

    if os.environ.get("RBS_WRITE_FIXTURE") == "1":
        SETUP_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        SETUP_FIXTURE.write_text(rendered, encoding="utf-8")

    assert SETUP_FIXTURE.exists(), (
        f"{SETUP_FIXTURE} is missing — the front end's conformance test reads it. "
        "Regenerate with RBS_WRITE_FIXTURE=1."
    )
    assert SETUP_FIXTURE.read_text(encoding="utf-8") == rendered, (
        "GET /runbooks/{key} no longer serves the payload RBS-004's mapper reads. "
        "If the change is deliberate, regenerate with RBS_WRITE_FIXTURE=1 and check that "
        "07-frontend/src/features/runbooks/setupConformance.test.tsx still passes in the "
        "SAME commit — the whole point of the pair is that neither side moves alone "
        "(DEF-RBS-4308)."
    )


def test_rbs004_setup_payload_carries_every_field_the_mapper_reads(setup_payload):
    """Every field `setupModel.toSetupView` reaches for is on the wire.

    ⚠ **NAMED ONE BY ONE RATHER THAN COUNTED.** A key count would pass over a
    rename, which is the failure this pair exists for: on 2026-09-06 the payload
    had 21 keys and the renderer needed two it did not have, and the arithmetic
    of *21* said nothing at all.
    """
    detail = setup_payload["detail"]
    for field in (
        "key",
        "name",
        "kind",
        "category",
        "enabled",
        "cap",
        "gate_mode",
        "schedule",
        "definition",
        "guards",
        "ports",
        "activity",
        "last_run",
    ):
        assert field in detail, f"the mapper reads `{field}` and the payload does not carry it"

    for field in ("trigger_kind", "cron", "event_kind", "timezone", "next_run"):
        assert field in detail["schedule"], f"`schedule.{field}` is gone"

    assert detail["definition"] is not None, "a runbook added from a template has a definition"
    for part in ("steps", "guards", "parameters"):
        assert part in detail["definition"], f"`definition.{part}` is gone"

    # ⚠ **THE FIXTURE MUST NOT SILENTLY GO EMPTY.** `RBS-004.1`'s *Last run*
    # block and `RBS-004.6`'s table are the two tabs a run feeds; if the run
    # stopped being created, every assertion about them would pass over nothing
    # and the pair would report on seven tabs while checking five (hard-won law
    # 7's *reporting zero over a scope it silently excludes*).
    assert detail["last_run"] is not None, "the fixture's run has vanished — two tabs now check nothing"
    assert setup_payload["runs"]["count"] >= 1, "the runs page is empty — RBS-004.6 checks nothing"
    assert setup_payload["runs"]["results"], "the runs envelope carries no rows"


def test_rbs004_activity_carries_facts_and_never_a_sentence(setup_payload):
    """`RBS-004.7`'s change list is `{field, from, to}` and not English.

    `models.RunbookVersion.summary` rules it: *Cap raised to 400* is English and
    `{"field": "cap", "from": 100, "to": 400}` is a fact eleven catalogues can
    each say in their own language (B14 rule 35). The mapper composes the
    sentence; a server that sent one would put screen copy in Python.
    """
    activity = setup_payload["detail"]["activity"]
    assert len(activity) == 2, "add + edit is two versions (BR-RBS-038)"
    assert activity[0]["version"] == 2, "newest first"

    fields = {change["field"] for row in activity for change in row["changes"]}
    assert {"cap", "enabled", "origin"} <= fields, f"the facts the edit made are missing: {fields}"

    for row in activity:
        for change in row["changes"]:
            assert set(change) <= {"field", "from", "to"}, change
        # B14 rule 31 — `id` here is the VERSION NUMBER, never the row's uuid,
        # so there is no database id on this payload to render by accident.
        assert row["id"] == row["version"]
        assert not UUID_RE.search(json.dumps(row)), f"a uuid reached the Activity payload: {row}"


def test_rbs004_setup_payload_names_no_database_id_a_clerk_could_read(setup_payload):
    """B14 rule 31, over the whole detail body except the one legitimate id.

    `last_run.id` is an ADDRESS — `/runs/{id}` is how a run is reached and it is
    never the visible value of a field. Everything else is checked, because the
    way a payload makes rule 31 easy to break is by carrying an id beside a name
    that might be empty (`selectors._person` says so in its own docstring).
    """
    detail = dict(setup_payload["detail"])
    last_run = detail.pop("last_run", None)
    assert not UUID_RE.search(json.dumps(detail)), "a uuid is on the setup payload"
    if last_run is not None:
        assert "id" in last_run, "a run must still be reachable by address"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-016 · US-RBS-001 · CR-075 · 07-endpoints.md rows 2 and 8 · DEF-RBS-4308
# generated: 2026-09-06 by the CR-075 RBS-004 mapper lane
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_rbs004_setup_payload_conformance.py · the front-end half, setupConformance.test.tsx
# exceptions: uuids, timestamps and a generated key are normalised before the byte comparison; the module docstring says exactly which and why
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
