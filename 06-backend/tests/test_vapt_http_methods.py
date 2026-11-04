# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-SHL-10622 — no automated evidence for the VAPT "arbitrary HTTP
#           methods" finding (closed as not exploitable, PO 2026-10-27).
# Doc:      09-infra/06-vapt-remediation-2026-10.md §3, evidence E3 and E5:
#           `pytest tests/test_vapt_http_methods.py -v`
# ───────────────────────────────────────────────────────
"""EVERY API path answers 405 to every method it does not declare.

Run it with `-v -s` to get the evidence table the auditor attaches (E3).

HOW IT WORKS. The URL resolver is walked for every route under `/api/`; each
route's DECLARED methods are the view's own handlers (DRF `@api_view([...])`
or a class's `get`/`post`/…, or a viewset's action map) united with the
methods `openapi/schema.json` publishes for the same path. Every route is then
called, signed in as a System Admin from the deployed front end's origin, with
each of `GET POST PUT PATCH DELETE TRACE` it does NOT declare, and must answer
405. Path parameters get syntactically valid sample values (a uuid, an int, a
word): an undeclared method is refused before any handler runs, so no real
record is needed.

⚠ **WHAT IS NOT CHECKED IS COUNTED, NEVER SILENT (hard-won law 7).** DRF runs
authentication and permission BEFORE it looks for a handler, so a route a
System Admin may not reach at all answers 401/403 to every method — that says
nothing about methods, and is counted as `refused before the method check`.
Field-app routes refused to the admin are tried again with a field
technician's bearer token. The test prints checked / skipped / failed with the
routes in each group, and fails on any route that ANSWERS an undeclared method
with anything but 405 — or if the skipped share grows past a stated ceiling, so
a fixture change that quietly skips most routes cannot pass.

Also here (E5): a CORS preflight from a foreign origin gets no
`Access-Control-Allow-Origin`, and our own origin does.
"""

from __future__ import annotations

import json
import pathlib
import re
import uuid
from collections import defaultdict

import pytest
from django.core.cache import cache
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver

from tests.test_cr187_native_auth import _token, field  # noqa: F401 (fixture)
from tests.test_us_idn_helpers import SC, idn, signed_in_client  # noqa: F401

pytestmark = pytest.mark.django_db

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "TRACE")
OWN_ORIGIN = "https://app.bynry.com"
SCHEMA = pathlib.Path(__file__).resolve().parents[1] / "openapi" / "schema.json"
#: The share of /api/ routes allowed to be untestable for methods (refused to
#: both principals before DRF looks for a handler). Measured 2026-10-27; a
#: rise past this means the evidence quietly covers less than it says.
MAX_SKIPPED_SHARE = 0.10

_CONVERTERS = {
    "uuid": lambda: str(uuid.UUID(int=1)),
    "int": lambda: "1",
    "str": lambda: "x",
    "slug": lambda: "x",
    "path": lambda: "x",
}


def _api_routes() -> list[tuple[str, object]]:
    """(route template, callback) for every pattern whose path starts api/."""
    found: list[tuple[str, object]] = []

    def walk(patterns, prefix: str) -> None:
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + str(p.pattern))
            elif isinstance(p, URLPattern):
                found.append((prefix + str(p.pattern), p.callback))

    walk(get_resolver().url_patterns, "")
    return [(r, cb) for r, cb in found if r.lstrip("^").startswith("api/")]


def _concrete(route: str, tenant: str) -> str | None:
    """A real address for a route template, or None when it cannot be built."""
    path = re.sub(r"(^|/)\^", r"\1", route).replace("$", "").replace("\\.", ".")
    path = path.replace("[-a-zA-Z0-9_]+", tenant)
    # Regex groups (a handful of re_path routes): the first alternative, or a word.
    path = re.sub(r"\(\?P<\w+>([^)|]+)(?:\|[^)]*)?\)", lambda m: m.group(1) if re.fullmatch(r"[\w.-]+", m.group(1)) else "x", path)
    path = re.sub(r"<(?:(\w+):)?\w+>", lambda m: _CONVERTERS.get(m.group(1) or "str", lambda: "x")(), path)
    path = path.replace("[^/]+", "x")
    if re.search(r"[\\()\[\]*+?{}|]", path):
        return None
    return "/" + path


def _view_methods(callback) -> set[str] | None:
    cls = getattr(callback, "cls", None)
    actions = getattr(callback, "actions", None)
    if actions:
        return {m.upper() for m in actions}
    if cls is not None:
        return {m.upper() for m in cls.http_method_names if hasattr(cls, m) and m not in ("options", "head")}
    return None  # a plain Django view — counted separately


def _schema_methods() -> dict[str, set[str]]:
    paths = json.loads(SCHEMA.read_text(encoding="utf-8")).get("paths", {})
    out: dict[str, set[str]] = {}
    for path, item in paths.items():
        key = re.sub(r"\{[^}]+\}", "{}", path).rstrip("/")
        out[key] = {m.upper() for m in item if m.lower() in {x.lower() for x in METHODS}}
    return out


def _schema_key(route: str) -> str:
    path = "/" + re.sub(r"(^|/)\^", r"\1", route).replace("$", "")
    path = path.replace("[-a-zA-Z0-9_]+", "{}")
    path = re.sub(r"<[^>]+>|\(\?P<[^>]+>[^)]*\)|\[\^/\]\+", "{}", path)
    return path.rstrip("/")


def _call(client: Client, method: str, url: str, **extra):
    return client.generic(method, url, data=b"", content_type="application/json", HTTP_ORIGIN=OWN_ORIGIN, **extra)


def test_vapt_e3__every_api_route_refuses_the_methods_it_does_not_declare(field, settings):  # noqa: F811
    settings.APP_RATE_LIMITS_ENABLED = False
    admin = signed_in_client(field.users.alex.email, "Canyon2026rapids")
    bearer = {"HTTP_AUTHORIZATION": f"Bearer {_token().json()['access_token']}"}
    schema = _schema_methods()

    checked: dict[str, int] = {}
    failures: list[str] = []
    skipped: dict[str, list[str]] = defaultdict(list)
    schema_disagrees = 0
    wrong_calls = 0
    schema_matched = 0
    routes = _api_routes()

    for route, callback in routes:
        url = _concrete(route, SC)
        if url is None:
            skipped["no sample address could be built"].append(route)
            continue
        declared = _view_methods(callback)
        if declared is None:
            skipped["not a DRF view (plain Django)"].append(route)
            continue
        published = schema.get(_schema_key(route))
        if published is not None:
            schema_matched += 1
            if published != declared:
                schema_disagrees += 1
        declared = declared | (published or set())
        if "GET" in declared:
            declared.add("HEAD")
        undeclared = [m for m in METHODS if m not in declared]
        if not undeclared:
            checked[route] = 0
            continue

        def answers(extra: dict) -> list[tuple[str, int]]:
            # The public doors keep their own per-address throttles (60 a
            # minute); this walk is one address making thousands of calls, so
            # the counters are emptied per route — a 429 here would be the
            # walk's own volume, not an answer about methods.
            cache.clear()
            return [(m, _call(Client(**{}) if extra else admin, m, url, **extra).status_code) for m in undeclared]

        results = answers({})
        if all(code in (401, 403, 404) for _, code in results) and "/work/mobile" in url:
            results = answers(bearer)  # the field app's own principal
        if all(code in (401, 403) for _, code in results):
            skipped["refused before the method check (401/403 to both principals)"].append(route)
            continue
        if all(code == 404 for _, code in results):
            skipped["404 to every method (route needs a real parent record)"].append(route)
            continue
        wrong = [(m, code) for m, code in results if code != 405]
        wrong_calls += len(wrong)
        if wrong:
            failures.append(f"{url}  {wrong}")
        checked[route] = len(undeclared)

    total = len(routes)
    n_skipped = sum(len(v) for v in skipped.values())
    calls = sum(checked.values())
    print(f"\nE3 · /api/ routes: {total} · checked {len(checked)} ({calls} undeclared-method calls,"
          f" {calls - wrong_calls} answered 405, {wrong_calls} did NOT)"
          f" · skipped {n_skipped} · failed {len(failures)}"
          f" · found in openapi/schema.json {schema_matched}, of which disagreeing with the view {schema_disagrees}")
    for reason, items in skipped.items():
        print(f"  skipped — {reason}: {len(items)}")
        for item in items[:15]:
            print(f"      {item}")
        if len(items) > 15:
            print(f"      … and {len(items) - 15} more")
    for failure in failures:
        print(f"  FAILED  {failure}")

    assert not failures, f"{len(failures)} route(s) answered an undeclared method with something other than 405"
    assert total > 500, "the walk found too few /api/ routes to be the whole API"
    assert n_skipped / total <= MAX_SKIPPED_SHARE, (
        f"{n_skipped} of {total} routes could not be checked — more than {MAX_SKIPPED_SHARE:.0%}"
    )


def test_vapt_e3__premises_answers_405_with_an_allow_header(idn):
    """The tester's own retest row: PUT/PATCH/DELETE/TRACE on /premises → 405."""
    users = idn.seed_silvercreek()
    admin = signed_in_client(users.alex.email, "Canyon2026rapids")
    for method in ("PUT", "PATCH", "DELETE", "TRACE"):
        response = _call(admin, method, f"/api/{SC}/premises")
        assert response.status_code == 405, (method, response.status_code)
        allow = {m.strip() for m in response["Allow"].split(",")}
        assert {"GET", "POST"} <= allow and method not in allow


def test_vapt_e5__a_foreign_origin_preflight_gets_no_cors_permission(idn):
    idn.seed_silvercreek()
    foreign = Client().options(
        f"/api/{SC}/premises",
        HTTP_ORIGIN="https://evil.example",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="DELETE",
    )
    assert "Access-Control-Allow-Origin" not in foreign
    assert "Access-Control-Allow-Credentials" not in foreign
    own = Client().options(
        f"/api/{SC}/premises",
        HTTP_ORIGIN=OWN_ORIGIN,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="DELETE",
    )
    # The control: our own origin IS allowed, so the absence above is a refusal
    # and not a CORS layer that is switched off.
    assert own["Access-Control-Allow-Origin"] == OWN_ORIGIN
