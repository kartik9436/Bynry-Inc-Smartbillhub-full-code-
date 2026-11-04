# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-SHL-10621 — no application rate limit on signed-in API calls
#           (VAPT rate-limiting finding: 30 calls to /premises, no 429).
# Ruling:   decision log 2026-10-27 "VAPT round: five findings ruled" (2).
# Doc:      09-infra/06-vapt-remediation-2026-10.md §2 "Proposed limits",
#           Test table rows 5, 6, 8.
# Code:     06-backend/core/throttling.py · config/settings/base.py
# ───────────────────────────────────────────────────────
"""A1–A4 refuse past their env-set rate, and count by the right thing.

Red first, without the change: nothing throttles a signed-in call, so every
"the Nth is refused" assertion fails with a 200 (or the view's own 4xx).

The limits are OFF in `config/settings/test.py` so the rest of the suite is
never throttled by its own fixtures; every case here turns them ON for itself
with deliberately tiny rates, and clears the counter cache on both sides.
"""

from __future__ import annotations

import pytest
from django.conf import settings as django_settings
from django.core.cache import cache
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver

from core import throttling
from tests.test_cr187_native_auth import DEVICE, _bearer, _token, field  # noqa: F401 (fixture)
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    SC,
    api_get,
    api_path,
    api_post,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

KEY = "api.error.rate_limited"


@pytest.fixture()
def limits(settings):
    """The four limits ON, at rates small enough to reach in a test."""
    cache.clear()
    settings.APP_RATE_LIMITS_ENABLED = True
    settings.RATE_USER_PER_MIN = 300
    settings.RATE_TENANT_PER_MIN = 3000
    settings.RATE_HEAVY_PER_MIN = 10
    settings.RATE_DEVICE_PER_MIN = 120
    yield settings
    cache.clear()


def _refused(response):
    assert response.status_code == 429, (response.status_code, response.content[:300])
    body = response.json()
    assert body["message_key"] == KEY
    assert body["code"] is None
    assert int(response["Retry-After"]) >= 1
    return body


# ══ wiring · defaults, switch, env names ═════════════════════════════════
def test_def_shl_10621__the_four_limits_are_the_platform_default():
    assert django_settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] == [
        "core.throttling.HeavyActionThrottle",
        "core.throttling.DeviceSyncThrottle",
        "core.throttling.UserRateThrottle",
        "core.throttling.TenantRateThrottle",
    ]


def _base_values(**env: str) -> list:
    """Import `config.settings.base` in a CLEAN process with only `env` set, and
    return the five values — reloading a settings module in-process is not safe."""
    import json
    import os
    import pathlib
    import subprocess
    import sys

    clean = {k: v for k, v in os.environ.items() if not k.startswith(("RATE_", "APP_RATE_"))}
    clean.update(env)
    code = (
        "import json; from config.settings import base as b; print(json.dumps(["
        "b.APP_RATE_LIMITS_ENABLED, b.RATE_USER_PER_MIN, b.RATE_TENANT_PER_MIN,"
        " b.RATE_HEAVY_PER_MIN, b.RATE_DEVICE_PER_MIN]))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=pathlib.Path(__file__).resolve().parents[1],
        env=clean,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_def_shl_10621__the_defaults_are_the_documents_numbers():
    """300 / 3000 / 10 / 120 a minute, from RATE_*_PER_MIN, ON by default
    (law 3: the unsafe option is the one you type)."""
    assert _base_values() == [True, 300, 3000, 10, 120]
    assert _base_values(RATE_USER_PER_MIN="42", APP_RATE_LIMITS_ENABLED="false") == [False, 42, 3000, 10, 120]


def test_def_shl_10621__the_suite_runs_with_them_off():
    assert django_settings.APP_RATE_LIMITS_ENABLED is False


# ══ A1 · per user ═════════════════════════════════════════════════════════
def test_def_shl_10621__a1_per_user(idn, limits):
    users = idn.seed_silvercreek()
    limits.RATE_USER_PER_MIN = 3
    limits.RATE_TENANT_PER_MIN = 1000
    alex = signed_in_client(users.alex.email, "Canyon2026rapids")
    for _ in range(3):
        assert api_get(alex, "/me").status_code == 200
    _refused(api_get(alex, "/me"))
    # Another person in the same utility has their own allowance.
    priya = signed_in_client(users.priya.email, "Meadow2026sage")
    assert api_get(priya, "/me").status_code == 200


def test_def_shl_10621__a1_does_not_count_the_sign_in_door(idn, limits):
    """The public doors keep their own throttles; an anonymous call is not A1's."""
    users = idn.seed_silvercreek()
    limits.RATE_USER_PER_MIN = 1
    for _ in range(3):
        client = signed_in_client(users.alex.email, "Canyon2026rapids")
    assert api_get(client, "/me").status_code == 200


def test_def_shl_10621__switched_off_nothing_is_refused(idn, limits):
    users = idn.seed_silvercreek()
    limits.RATE_USER_PER_MIN = 1
    limits.APP_RATE_LIMITS_ENABLED = False
    alex = signed_in_client(users.alex.email, "Canyon2026rapids")
    for _ in range(5):
        assert api_get(alex, "/me").status_code == 200


# ══ A2 · per utility ══════════════════════════════════════════════════════
def test_def_shl_10621__a2_per_utility(idn, limits):
    users = idn.seed_silvercreek()
    jordan, _ = idn.seed_bluemesa_admin()
    limits.RATE_TENANT_PER_MIN = 4
    alex = signed_in_client(users.alex.email, "Canyon2026rapids")
    priya = signed_in_client(users.priya.email, "Meadow2026sage")
    for client in (alex, priya, alex, priya):
        assert api_get(client, "/me").status_code == 200
    _refused(api_get(priya, "/me"))
    # Another utility is untouched by Silver Creek's burst.
    blue = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant="bluemesa")
    assert api_get(blue, "/me", tenant="bluemesa").status_code == 200


# ══ A3 · heavy actions ════════════════════════════════════════════════════
def test_def_shl_10621__a3_heavy_actions_per_user(idn, limits):
    """Test row 6 in miniature: an export 3 times a minute at a limit of 2."""
    users = idn.seed_silvercreek()
    limits.RATE_HEAVY_PER_MIN = 2
    alex = signed_in_client(users.alex.email, "Canyon2026rapids")
    for _ in range(2):
        assert api_post(alex, "/billing/runs", {}).status_code != 429
    _refused(api_post(alex, "/billing/runs", {}))
    # Reading is not heavy: the same person still opens screens.
    assert api_get(alex, "/me").status_code == 200
    # …and another person still runs their own.
    priya = signed_in_client(users.priya.email, "Meadow2026sage")
    assert api_post(priya, "/billing/runs", {}).status_code != 429


def test_def_shl_10621__a3_counts_a_platform_path_export_too(idn, limits):
    users = idn.seed_silvercreek()
    limits.RATE_HEAVY_PER_MIN = 1
    alex = signed_in_client(users.alex.email, "Canyon2026rapids")
    assert alex.post("/api/exports", data={}, content_type="application/json").status_code != 429
    _refused(alex.post("/api/exports", data={}, content_type="application/json"))


def _routes() -> list[str]:
    found: list[str] = []

    def walk(patterns, prefix=""):
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + str(p.pattern))
            elif isinstance(p, URLPattern):
                found.append("/" + (prefix + str(p.pattern)).lstrip("^").replace("^", "").rstrip("$"))

    walk(get_resolver().url_patterns)
    return found


def test_def_shl_10621__every_heavy_pattern_matches_a_real_route():
    """Law 7: a pattern that matches no route protects nothing and must go red.
    Route params are replaced by a sample segment so the patterns can see them."""
    import re

    sample = [re.sub(r"<[^>]+>|\(\?P<[^>]+>[^)]*\)", "x", r).replace("[-a-zA-Z0-9_]+", "t") for r in _routes()]
    counts = {
        label: sum(1 for r in sample if pattern.search(r.rstrip("/")))
        for label, pattern in throttling.HEAVY_ACTION_PATTERNS
    }
    print("\nA3 heavy patterns → routes matched:", counts, f"(of {len(sample)} routes)")
    assert all(counts.values()), {k: v for k, v in counts.items() if not v}
    device = {p.pattern: sum(1 for r in sample if p.search(r.rstrip("/"))) for p in throttling.DEVICE_SYNC_PATTERNS}
    print("A4 sync patterns → routes matched:", device)
    assert all(device.values()), device


# ══ A4 · field-app sync per phone ═════════════════════════════════════════
def test_def_shl_10621__a4_sync_per_phone(field, limits):  # noqa: F811
    limits.RATE_DEVICE_PER_MIN = 2
    access = _token().json()["access_token"]
    sync = api_path("/work/mobile/sync", SC)
    for _ in range(2):
        response = Client().post(sync, data={"items": []}, content_type="application/json", **_bearer(access))
        assert response.status_code != 429, response.content
    _refused(Client().post(sync, data={"items": []}, content_type="application/json", **_bearer(access)))
    # A second handset of the same technician has its own allowance.
    other = _token(device="a1b2c3d4-handset-0002").json()["access_token"]
    assert (
        Client().post(sync, data={"items": []}, content_type="application/json", **_bearer(other)).status_code
        != 429
    )


def test_def_shl_10621__the_sentence_is_in_all_eleven_catalogues():
    import json
    import pathlib

    locales = pathlib.Path(__file__).resolve().parents[2] / "07-frontend/src/i18n/locales"
    files = sorted(locales.glob("*.json"))
    assert len(files) == 11
    for path in files:
        assert json.loads(path.read_text(encoding="utf-8")).get(KEY), path.name
    english = json.loads((locales / "en.json").read_text(encoding="utf-8"))
    assert english[KEY] == "Too many requests. Wait a moment."
