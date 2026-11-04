# ── Trace ──────────────────────────────────────────────
# Defect:    DEF-INF-7616 (2026-09-28) — every API call from the deployed SPA was
#            blocked in preflight. Reported from the browser console at
#            app-dev.bynry.com, verbatim: "Request header field x-support-ref is
#            not allowed by Access-Control-Allow-Headers in preflight response."
# Change:    CR-144-BRC07 (X1) — the SPA moved to its own host, which is what made
#            every call cross-origin in the first place.
# Rules:     decision log 2026-09-28 ruling 1 — two hosts, `app[-env].bynry.com`
#            and `api-smart360[-env].bynry.com`.
# Component: config/settings/base.py — CORS_ALLOW_HEADERS / CORS_EXPOSE_HEADERS.
# Impacts:   every screen in the staff app and the customer portal; they all
#            leave through the one fetch site, 07-frontend/src/api/client.ts:570.
# ───────────────────────────────────────────────────────
"""The two halves of a CORS grant that CR-144-BRC07 never wrote.

**THE HALF THAT SHOUTED.** `07-frontend/src/api/client.ts:558` puts
`X-Support-Ref` on EVERY request and `If-None-Match` on a conditional read
(`:564`). Neither is a CORS-safelisted request header, so the browser asks
permission for them in a preflight — and django-cors-headers grants only its six
defaults (`accept, authorization, content-type, user-agent, x-csrftoken,
x-requested-with`) until `CORS_ALLOW_HEADERS` says otherwise. The preflight
answered **200 with the right origin and without `x-support-ref`**, so the real
request was never sent. Every call. Every screen.

**THE HALF THAT DID NOT, AND IT IS THE ONE THIS FILE EXISTS FOR.** The same gap
runs the other way: a browser hides every non-safelisted RESPONSE header from
the script unless `Access-Control-Expose-Headers` names it. Cross-origin, and
with nothing set, `response.headers.get("ETag")` returns **null** — no error, no
console line, no failing test. Conditional caching silently stops working
(`client.ts:596`), `Retry-After` silently stops steering the retry delay
(`:604`), a download loses its server-chosen filename
(`endpoints.ts:14750`), and the audit banner reads the wrong window
(`endpoints.ts:3418`/`:3421`). That is hard-won law 2's mirror — a live screen
behind a control that has quietly stopped answering — and it is why the expose
list is asserted here as hard as the allow list.

⚠ **WHY NOTHING CAUGHT EITHER HALF (the row's `escape_reason`).**
`test_cr144_cors_and_origin.py` sends an `OPTIONS` with
`Access-Control-Request-Method` and **no `Access-Control-Request-Headers` at
all**, so what it exercises is the six defaults; the two headers the client
really sends are named nowhere in the suite. And nothing anywhere asserted
`Access-Control-Expose-Headers`. Neither half can fail a same-origin test, and
every other test in this repository is same-origin.

⚠ **`CORS_ALLOW_HEADERS` REPLACES the defaults, it does not extend them**, so
`test_the_six_defaults_survive` is not padding: dropping `*default_headers`
from that tuple would refuse `content-type` and break every JSON POST in the
product, with this file's first case still green.
"""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client

#: The deployed shape, as `config/settings/test.py` sets it. Asserted rather
#: than assumed so this file cannot quietly start testing emptiness.
ALLOWED = "https://app.bynry.com"
STRANGER = "https://app.bynry.com.attacker.example"

#: ⚠ **THE PATH FROM THE BUG REPORT, ON PURPOSE.** Not `/api/health`: that is
#: short-circuited by `HealthCheckMiddleware`, which sits ABOVE `CorsMiddleware`
#: in `MIDDLEWARE` and returns before it — so a health response carries no CORS
#: headers at all and a test written against it would prove nothing.
A_PUBLIC_READ = "/api/public/subdomain-check"

#: What `07-frontend/src/api/client.ts` sends beyond the safelist.
#: `x-background-refresh` from 2026-10-08 (DEF-IDN-10024).
CLIENT_REQUEST_HEADERS = ("x-support-ref", "if-none-match", "x-background-refresh")

#: What the front end reads back off a response. `X-Support-Ref` is in the
#: setting and is NOT in this tuple, deliberately — see
#: `test_every_header_the_front_end_reads_is_exposed` for why.
CLIENT_READS_BACK = (
    "ETag",
    "Retry-After",
    "Content-Disposition",
    "X-Audit-Window",
    "X-Audit-Window-From",
)

REPO = Path(__file__).resolve().parents[2]


def _allow_list(response) -> list[str]:
    raw = response.headers.get("Access-Control-Allow-Headers", "")
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


def _expose_list(response) -> list[str]:
    raw = response.headers.get("Access-Control-Expose-Headers", "")
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


@pytest.fixture(autouse=True)
def _two_hosts(settings):  # noqa: F811 — the pytest-django fixture, shadowing on purpose
    """⚠ **A FIXTURE AND NOT `@override_settings`** — that decorator only works
    on `SimpleTestCase` subclasses and raises at COLLECTION time on a plain
    pytest class. `test_cr144_cors_and_origin.py` carries the same note; it is
    repeated rather than shared because the note is what stops the next person
    reaching for the decorator."""
    settings.CORS_ALLOWED_ORIGINS = [ALLOWED]
    settings.ORIGIN_GUARD_ALLOWED_ORIGINS = [ALLOWED]


def _preflight(origin: str, request_headers: str) -> object:
    return Client().options(
        A_PUBLIC_READ + "?subdomain=jay-utu",
        HTTP_ORIGIN=origin,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS=request_headers,
    )


class TestThePreflightGrantsWhatTheClientSends:
    def test_x_support_ref_and_if_none_match_are_allowed(self):
        """The reported defect, in one assertion each.

        RED before the fix:
            AssertionError: 'x-support-ref' is not in the preflight's
            Access-Control-Allow-Headers: ['accept', 'authorization',
            'content-type', 'user-agent', 'x-csrftoken', 'x-requested-with']
        """
        response = _preflight(ALLOWED, "x-support-ref, if-none-match")
        assert response.headers.get("Access-Control-Allow-Origin") == ALLOWED
        allowed = _allow_list(response)
        for header in CLIENT_REQUEST_HEADERS:
            assert header in allowed, f"{header!r} is not in {allowed}"

    def test_the_six_defaults_survive(self):
        """⚠ `CORS_ALLOW_HEADERS` REPLACES django-cors-headers' defaults.

        So the setting splats `default_headers` in rather than listing two
        headers. Without this case, a tuple holding only the two new names
        passes the case above and refuses `content-type` — which is every JSON
        POST in the product, broken by a green suite."""
        from corsheaders.defaults import default_headers

        allowed = _allow_list(_preflight(ALLOWED, "content-type, authorization"))
        for header in default_headers:
            assert header.lower() in allowed, f"the default {header!r} was dropped"

    def test_a_stranger_origin_is_still_refused(self):
        """The fix must widen WHAT may be sent, never WHO may send it.

        `https://app.bynry.com.attacker.example` starts with the allowed origin,
        so a prefix match would grant it. The assertion is that the header is
        ABSENT — `Access-Control-Allow-Origin: *` is not a laxer answer but a
        broken one, since a browser refuses the wildcard together with
        credentials and the session cookie IS the credential."""
        response = _preflight(STRANGER, "x-support-ref, if-none-match")
        assert "Access-Control-Allow-Origin" not in response.headers
        assert "Access-Control-Allow-Headers" not in response.headers


class TestTheResponseHeadersReachTheScript:
    @pytest.mark.django_db
    def test_a_real_read_carries_the_expose_list(self):
        """The silent half. A browser hides every non-safelisted response header
        from the script unless this names it.

        Asserted on the HEADERS and not on the status: this endpoint is
        throttled (`PublicOnboardingThrottle`), and a 429 is still a response
        `CorsMiddleware` decorates — so a throttled run must not turn this case
        red for the wrong reason.

        RED before the fix:
            AssertionError: 'etag' is not in the response's
            Access-Control-Expose-Headers: []
        """
        response = Client().get(A_PUBLIC_READ + "?subdomain=jay-utu", HTTP_ORIGIN=ALLOWED)
        assert response.headers.get("Access-Control-Allow-Origin") == ALLOWED
        exposed = _expose_list(response)
        for header in (*CLIENT_READS_BACK, "X-Support-Ref"):
            assert header.lower() in exposed, f"{header!r} is not in {exposed}"

    def test_the_setting_itself_lists_all_six(self):
        """Read off the setting as well as off the wire, so a middleware that
        stopped emitting the header cannot be mistaken for a setting that lost
        a name."""
        configured = [h.lower() for h in settings.CORS_EXPOSE_HEADERS]
        for header in (*CLIENT_READS_BACK, "X-Support-Ref"):
            assert header.lower() in configured


class TestTheListsDoNotGoStale:
    """⚠ **THESE TWO ARE GREPS, AND IT IS SAID OUT LOUD THAT THEY ARE** (law 7 —
    describe the false pass before trusting the green).

    A grep cannot prove a header is sent; it proves that no header NAMED in the
    front end's own code is missing from the grant. That is the failure this
    defect actually was, and the one it will be again: somebody adds a header to
    `client.ts` and the settings file, three directories away in another
    language, is not where they are looking. A header reached through a variable
    this pattern cannot see is the false pass, and it is why the two constant
    declarations are matched as well as the string literals.

    ⚠ **THE SCOPE IS THE WHOLE OF `src/`, AND THAT IS DELIBERATE RATHER THAN
    THOROUGH.** The first draft read `api/client.ts` and `api/endpoints.ts`,
    which is where all four request headers and all five response reads live
    TODAY — and a check scoped to where a thing lives today is law 7's fifth
    shape, reporting zero over a scope it silently excludes. A second client
    (`portal/api/portalClient.ts`, `features/work/mobile/`) that grew a header
    of its own would have been invisible to it. `test_files_scanned` prints the
    count beside the result, because a blind spot with no number attached is
    indistinguishable from an empty one.

    ⚠ **TEST FILES ARE EXCLUDED**, and for a reason rather than for speed: a
    test asserts on headers a mock produced, which is not evidence that the
    product reads one."""

    @staticmethod
    def _sources() -> list[Path]:
        root = REPO / "07-frontend" / "src"
        return sorted(
            p
            for p in root.rglob("*.ts*")
            if p.suffix in {".ts", ".tsx"}
            and ".test." not in p.name
            and "__tests__" not in p.parts
        )

    def test_files_scanned(self):
        """Law 7: print what was covered beside the answer, so the two cases
        below cannot report zero over a scope nobody sized."""
        files = self._sources()
        print(f"scanned {len(files)} non-test .ts/.tsx files under 07-frontend/src")
        assert len(files) > 100, f"only {len(files)} files — the walk is not reaching src/"

    def test_every_request_header_the_client_sets_is_allowed(self):
        """⚠ **A CONSTANT'S NAME DOES NOT SAY WHICH DIRECTION IT TRAVELS**, and
        the first version of this case assumed it did. Matching every
        `export const …HEADER = "…"` under `src/` swept in
        `AUDIT_WINDOW_HEADER` and `AUDIT_WINDOW_FROM_HEADER`, which are
        RESPONSE header names, and demanded they be added to the REQUEST allow
        list — a false failure that would have been "fixed" by granting two
        headers no browser will ever send. (It passed only while the scan was
        narrowed to `client.ts`, which is the accident that hid it.)

        So a constant counts only where it is USED as a request key —
        `[SUPPORT_REF_HEADER]: sentRef` — and the name is then resolved to its
        declared string. Literal `headers["X"] = …` and `headers.set("X", …)`
        are taken directly."""
        source = "\n".join(p.read_text(encoding="utf-8") for p in self._sources())
        literal = set(re.findall(r'headers\["([A-Za-z-]+)"\]', source))
        literal |= set(re.findall(r'headers\.set\("([A-Za-z-]+)"', source))
        # Identifiers used as a COMPUTED KEY in a headers object literal…
        used_as_key = set(re.findall(r"\[([A-Za-z_][A-Za-z0-9_]*HEADER)\]\s*:", source))
        # …resolved to the string each one declares.
        declared = dict(
            re.findall(r'const ([A-Za-z_][A-Za-z0-9_]*HEADER)\s*=\s*"([A-Za-z-]+)"', source)
        )
        unresolved = sorted(used_as_key - declared.keys())
        assert not unresolved, (
            f"{unresolved} are used as request header keys and this test cannot "
            "resolve their value — it would report zero over them (law 7)"
        )
        sent = {h.lower() for h in literal | {declared[name] for name in used_as_key}}
        # `Accept` is CORS-safelisted and needs no grant; it is set as a bare
        # object key rather than by index, so it is not matched here either.
        allowed = {h.lower() for h in settings.CORS_ALLOW_HEADERS}
        missing = sorted(sent - allowed)
        assert not missing, (
            f"{missing} are set on a request by the front end and are not in "
            "CORS_ALLOW_HEADERS — the browser will refuse the preflight (DEF-INF-7616)"
        )

    def test_every_response_header_the_front_end_reads_is_exposed(self):
        names: set[str] = set()
        for path in self._sources():
            source = path.read_text(encoding="utf-8")
            names |= set(re.findall(r'\.headers\.get\("([A-Za-z-]+)"\)', source))
            names |= set(re.findall(r'responseHeader\([^,]+,\s*"([A-Za-z-]+)"\)', source))
            names |= set(re.findall(r'export const \w*HEADER\s*=\s*"(X-Audit[A-Za-z-]*)"', source))
        exposed = {h.lower() for h in settings.CORS_EXPOSE_HEADERS}
        missing = sorted(n for n in names if n.lower() not in exposed)
        assert not missing, (
            f"{missing} are read off a response by the front end and are not in "
            "CORS_EXPOSE_HEADERS — cross-origin the browser returns null for each, "
            "silently (DEF-INF-7616)"
        )
