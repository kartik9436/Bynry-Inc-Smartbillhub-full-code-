# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-<something_else> (2026-09-05) — `CWP-046`'s *Something
#           else* card was greyed with *"Not online yet — ring us"* over
#           `CWP-054`, a routed and tested screen whose own heading reads ASK
#           US SOMETHING, which landed **73 minutes** after the hold was
#           written. Third outbreak of `DEF-CWP-3925`.
# Rules:    CLAUDE.md hard-won law 2, mirror clause (*"when you write a hold,
#           write the test that fires when the hold expires, in the same
#           commit — assert the destination by ADDRESS and by the screen id it
#           opens"*) · CR-068 R3 (a control is held until its screen lands) ·
#           BR-CWP-056 (visible, disabled, carrying its reason)
# Tests:    this file
# Impacts:  apps/portal/selectors.py `DEFAULT_REQUEST_ERRANDS` ·
#           `ERRAND_HELD_UNTIL` · `ERRAND_ROUTE` ·
#           07-frontend/src/portal/routing/screenIds.ts
# ───────────────────────────────────────────────────────
"""The test that goes RED on the day a held control's screen arrives.

⚠ **THIS IS THE ONE CHECK NOTHING IN THIS REPO WAS MAKING.** Every wave tested
ITS OWN screen at ITS OWN address, and the question *has the door started
pointing at it* belonged to nobody. `tsc`, 42 portal test files, 391 cases and
every gate were green over a shut door on a live screen for a whole day, twice
over — because a hold is a rule with a CLOCK in it, correct on the day it is
written and rotten on the day the screen lands, and landing a screen and
releasing the control that points at it are two acts.

⚠ **IT DELIBERATELY ASSERTS THE OPPOSITE OF WHAT A HOLD TEST NORMALLY DOES.**
`FrontPage.test.tsx` pins its held card with
`expect(CARD_ROUTE.what_things_cost).toBeUndefined()` — a test that PROTECTS a
hold and can only ever fail when someone releases it. That is a promise nobody
is keeping in its most durable form. The assertions here fail when the hold
becomes FALSE, which is the direction that costs a customer something.

WHAT IT READS, AND WHY IT CROSSES THE STACK
-------------------------------------------
The held/live decision is the SERVER's (`request_errands`), and the register of
screens that exist is the FRONT END's (`routing/screenIds.ts`, the mirror of
`CR-068` §9 that `G82` polices). Neither half can answer *is this hold still
true* on its own, so the test reads both — the same posture `G82` takes when it
parses a TypeScript literal from Python.

Python 3.12 + pytest. No database: everything here is module-level data.
"""

from __future__ import annotations

import re
from pathlib import Path

from apps.portal import selectors as portal_selectors

REGISTER = (
    Path(__file__).resolve().parents[2]
    / "07-frontend"
    / "src"
    / "portal"
    / "routing"
    / "screenIds.ts"
)

#: `{ path: "/ask-a-question", id: "CWP-054", blueprint: "P40", title: … }`,
#: over any amount of whitespace and any line breaks the formatter puts in.
#: The same shape `g82_cwp_screen_register.REGISTER_ROW` uses, for the same
#: reason: one literal, two readers, and a divergence in the regex would be a
#: divergence in the answer.
REGISTER_ROW = re.compile(
    r'\{\s*path:\s*"([^"]*)",\s*id:\s*"(CWP-\d{3,5}(?!\d))",\s*blueprint:\s*"([^"]*)"',
    re.S,
)


def routed_screens() -> dict[str, str]:
    """`{CWP id: the portal sub-path it is served at}` — the screens that EXIST."""
    text = REGISTER.read_text(encoding="utf-8")
    rows = {m.group(2): m.group(1) for m in REGISTER_ROW.finditer(text)}
    assert rows, f"no register rows parsed from {REGISTER} — the literal's shape moved"
    return rows


def held_codes() -> set[str]:
    """The errand codes shipping HELD today, from the seed the server answers."""
    return {
        str(row["code"])
        for row in portal_selectors.DEFAULT_REQUEST_ERRANDS
        if not row.get("screen")
    }


def test_cwp_holds_a_held_card_names_what_would_release_it():
    """Every hold states its expiry condition, or the set of holds is a lie.

    A lane adding a seventh card that ships held has to say HERE what would
    release it. Without this the map silently stops covering the holds and the
    check below quietly stops checking anything — a gate that cannot fail.
    """
    assert held_codes() == set(portal_selectors.ERRAND_HELD_UNTIL), (
        "every held errand needs a row in ERRAND_HELD_UNTIL saying which screen "
        "releases it (None where CR-068 §9 allocates no id at all)"
    )


def test_cwp_holds_no_held_card_is_shut_over_a_screen_that_already_exists():
    """**THE ASSERTION THIS FILE EXISTS FOR.**

    The day `CWP-048` lands in `screenIds.ts`, this fails and names *move_out*.
    """
    routed = routed_screens()
    for code, screen in portal_selectors.ERRAND_HELD_UNTIL.items():
        if screen is None:
            continue
        assert screen not in routed, (
            f"CWP-046's '{code}' card is HELD with 'Not online yet — ring us', and "
            f"{screen} is now routed at {routed.get(screen)}. The hold has expired: "
            f"give the card its screen in DEFAULT_REQUEST_ERRANDS and its address in "
            f"ERRAND_ROUTE, and drop it from ERRAND_HELD_UNTIL. "
            f"(hard-won law 2's mirror — DEF-CWP-3925, and this is the fourth time.)"
        )


def test_cwp_holds_every_live_card_opens_a_real_screen_at_the_right_address():
    """A released card is checked BY ID AND BY ADDRESS, never by one of them.

    `ERRAND_ROUTE` is the server's own answer for *where does this card go*, and
    `screenIds.ts` is where that address is actually served. A card pointing at
    a screen id nobody routes is a dead link; a card pointing at a live id with
    the WRONG path is a dead link that looks alive in every id-only assertion.
    """
    routed = routed_screens()
    live = {
        str(row["code"]): str(row["screen"])
        for row in portal_selectors.DEFAULT_REQUEST_ERRANDS
        if row.get("screen")
    }
    assert live, "every card is held — that cannot be right"
    for code, screen in live.items():
        assert screen in routed, f"'{code}' points at {screen}, which no portal route serves"
        assert screen in portal_selectors.ERRAND_ROUTE, (
            f"'{code}' names {screen} and ERRAND_ROUTE has no address for it, so "
            f"request_errands() would serve it HELD — a card that is neither live nor honest"
        )
        assert portal_selectors.ERRAND_ROUTE[screen] == routed[screen], (
            f"'{code}' → {screen}: the server sends a customer to "
            f"{portal_selectors.ERRAND_ROUTE[screen]} and the screen is served at "
            f"{routed[screen]}"
        )


def test_cwp_holds_something_else_opens_ask_us_something():
    """The figure this defect was closed on, pinned so it cannot drift back.

    `CWP-046`'s sixth card opens `CWP-054` at `/ask-a-question`. It was grey for
    a day over that screen; a re-hold has to fail here rather than in a browser.
    """
    row = next(
        one for one in portal_selectors.DEFAULT_REQUEST_ERRANDS if one["code"] == "something_else"
    )
    assert row["screen"] == "CWP-054"
    assert portal_selectors.ERRAND_ROUTE["CWP-054"] == "/ask-a-question"
    assert routed_screens()["CWP-054"] == "/ask-a-question"


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-CWP-<something_else> (CR-068 close-out)
# generated: 2026-09-05
# checklist: A✔ B=n/a C✔ D=n/a E✔(portal/requests/Requests.tsx) F✔ G✔ H=n/a
# gates: pytest tests/test_cwp_holds_expire.py · tests/test_us_cwp_060_request_hub.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
