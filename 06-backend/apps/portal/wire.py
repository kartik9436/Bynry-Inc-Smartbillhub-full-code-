# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-3961 — the server still serialises an engine diagnostic to
#           a customer on eight portal routes. The rule was applied on the
#           ninth (`api._webhook_view`, DEF-CWP-3926) and nowhere else.
# Rules:    US-CWP-006 TC-4 (a refusal must not reveal whether a reference
#           exists) · B14 rule 32 (no internal code in clerk-facing copy, and
#           a customer reads less than a clerk) · rule 33 (a refusal is five or
#           six words) · hard-won law 5 (one source, never a second copy)
# Tests:    06-backend/tests/test_def_cwp_3961_no_diagnostics_on_the_wire.py
# Impacts:  apps/portal/api.py `_no_store` · config/settings/base.py MIDDLEWARE
# ───────────────────────────────────────────────────────
"""THE LAST THING THAT TOUCHES A PORTAL BODY BEFORE A CUSTOMER GETS IT.

`problems[]` is this module's channel for *why a screen is showing you less
than it would like to*. Each entry carries a `code`, sometimes a `br_ref` or an
`oq_ref`, and a `detail` — **and `detail` is a sentence addressed to a
DEVELOPER**:

    "a late fee is an invoice line and no module publishes an account-scoped
     list of them. `P43` draws it as the third step of the timeline…"

    "account '10490b14-078e-45fe-adc5-f91aee40eb28' is not an account of this
     tenant"

The first names our internal design to somebody who does not work here. The
second — `payments`' own refusal, quoted in `api._webhook_view`'s docstring —
**echoes the caller's own id back at them and answers the exact question
`US-CWP-006` TC-4 says must not be answered.** The webhook route was taught to
drop the field when a test caught that one. Nothing taught the other eight.

⚠ **WHY THIS IS A WIRE RULE AND NOT NINE EDITS, WHICH IS THE WHOLE POINT.**
Half the problems on a portal response are not written in this package at all:
`pay_now_seam` does `[dict(one) for one in answer.problems]` and
`payments_seam` does `problems.extend(row.get("problems") or ())` — **whole
dicts copied out of another module**. A list of literals to fix would not have
covered those, and the next module to add a `detail` would be published the day
it was written, silently. The diagnostic channel grows a code whenever a module
finds a gap, so a rule about the CHANNEL is the only kind that stays true.

⚠ **THE CODE TRAVELS AND THE SENTENCE DOES NOT** — `_webhook_view`'s own words.
`code`, `br_ref` and `oq_ref` are stable identifiers a support engineer looks
up; they carry no customer data and no prose. What is dropped is the prose.
Nothing is lost to anybody who needs it: the sentence is in the source, next to
the code that raises it, which is where a developer reads it.

⚠ **AND NOTHING CAN SEE THIS FROM THE FRONT END.** A field a screen does not
render is invisible to `tsc`, to every DOM test and to every gate — the client
type stopped declaring `detail` when `DEF-CWP-3926` was half-fixed, so a screen
reaching for it is a compile error and the ORIGINAL leak cannot recur. That
made the remaining half harder to notice, not easier: the payload went on
carrying it with nothing able to ask.
"""

from __future__ import annotations

from typing import Any

#: The key that carries a developer's sentence. One name, defined once.
DIAGNOSTIC_KEY = "detail"

#: The lists whose entries are scrubbed. `problems` is the portal's own
#: channel; a second name is added HERE rather than by a second function.
DIAGNOSTIC_LISTS = ("problems",)


def customer_safe(payload: Any) -> Any:
    """The same body with every `problems[].detail` removed, at any depth.

    ⚠ **RECURSIVE, BECAUSE `problems` IS NOT ALWAYS AT THE TOP.**
    `selectors.home` nests a balance block that carries its own list, and
    `pay_now` returns a position inside an envelope. A one-level scrub would
    have been true of the payload the author happened to be looking at.

    ⚠ **IT REBUILDS RATHER THAN MUTATES.** These payloads are assembled from
    module-level constants — `DEPOSIT_NOT_PRICED` and `LATE_FEE_NOT_READABLE`
    are `dict`s at import time — and popping a key out of one in place would
    empty it for the life of the process, so the FIRST request would be scrubbed
    and every later one would serve a dict this function had already hollowed
    out. `dict(CONSTANT)` at the call sites is a shallow copy and does not
    protect the inner entries either.

    A value that is neither a mapping nor a list is returned unchanged, so this
    is safe over any JSON body including one with no problems in it.
    """
    if isinstance(payload, dict):
        out: dict[Any, Any] = {}
        for key, value in payload.items():
            if key in DIAGNOSTIC_LISTS and isinstance(value, list):
                out[key] = [_scrub_entry(entry) for entry in value]
            else:
                out[key] = customer_safe(value)
        return out
    if isinstance(payload, list):
        return [customer_safe(item) for item in payload]
    if isinstance(payload, tuple):
        return [customer_safe(item) for item in payload]
    return payload


def _scrub_entry(entry: Any) -> Any:
    """One problem, without its developer sentence. Everything else survives."""
    if not isinstance(entry, dict):
        return customer_safe(entry)
    return {
        key: customer_safe(value)
        for key, value in entry.items()
        if key != DIAGNOSTIC_KEY
    }


class PortalDiagnosticScrub:
    """Middleware — **every portal response, whether or not a view remembered**.

    ⚠ **THIS IS A MIDDLEWARE AND NOT A CHANGE TO `api._no_store`, AND THE
    DIFFERENCE IS THE DEFECT.** `_no_store` wraps 66 of the portal's responses
    and SEVENTEEN return a bare `Response(...)`; `guest_api` uses it not once.
    A rule installed on the wrapper is a rule that holds until somebody writes
    the eighteenth unwrapped route, which is exactly how the first eight
    happened — the ninth was fixed at its own call site and the fix could not
    travel.

    ⚠ **`process_template_response`, NOT `__call__`.** Django renders a
    `TemplateResponse` — which is what DRF returns — AFTER the template-response
    hooks and BEFORE the response middleware chain unwinds. A scrub written in
    `__call__` would edit `response.data` on an already-rendered response and
    change nothing at all about the bytes on the wire, while every test that
    read `response.data` passed. That is a check that cannot fail, and this
    docstring is here so the next lane does not "simplify" it into one.

    Scoped by PATH rather than by view, because the staff app serves `detail` to
    CLERKS deliberately — `problems` is how a clerk is told why a screen is
    showing less than it would like to, and B14 rule 32's budget is a customer's,
    not a clerk's.
    """

    #: The path SEGMENT every customer address carries, signed-in
    #: (`/api/{tenant}/portal/bills`) and guest (`…/portal/public/front`) alike.
    PORTAL_SEGMENT = "portal"

    #: ⚠ **AND THE THREE STAFF SCREENS THAT ALSO SAY `portal`.** `CR-068` wave
    #: D put the portal's own settings in the STAFF app at
    #: `settings/portal/branding`, so a substring test — `"portal/" in path` —
    #: reaches a clerk's screen. A clerk is exactly who `detail` is FOR: it is
    #: how they are told why a screen is showing less than it would like to, and
    #: B14 rule 32's description budget is a customer's and not theirs. Checked
    #: rather than assumed, and the segment test is why this is a tuple of
    #: segments and not an `in`.
    STAFF_SEGMENT = "settings"

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    def __call__(self, request: Any) -> Any:
        return self.get_response(request)

    def _is_customer_path(self, request: Any) -> bool:
        segments = (getattr(request, "path", "") or "").strip("/").split("/")
        return self.PORTAL_SEGMENT in segments and self.STAFF_SEGMENT not in segments

    def process_template_response(self, request: Any, response: Any) -> Any:
        if not self._is_customer_path(request):
            return response
        data = getattr(response, "data", None)
        if data is not None:
            response.data = customer_safe(data)
        return response
