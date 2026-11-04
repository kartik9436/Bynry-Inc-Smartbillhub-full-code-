# ── Trace ──────────────────────────────────────────────
# Defect:   The five `work.rules.*` keys of 2026-09-05 — a clerk saving a work
#           order rule with no name, an unknown trigger, an unknown source
#           module, no template, or a trigger belonging to another module got
#           NOTHING: the click did nothing and no sentence appeared. They landed
#           within the hour of another lane finishing the same repair on 59
#           other keys, 57 of them across the Work module.
# Rules:    PO ruling 2026-08-19 (`bec921e`) — server `detail` text never
#           reaches a customer screen; a refusal's words come from the
#           catalogue entry for its `message_key` and from nothing else. That
#           ruling is what turns an unresolved key from UGLY into SILENT.
#           CLAUDE.md law 7 (prove a guard RED first) · law 3 (defaults fail
#           closed) · law 1 (a comment claiming a guarantee is not the guarantee)
# Tests:    06-backend/tests/test_refusal_keys_resolve_at_raise.py
# Impacts:  core/errors.py::ApiError.__init__ · gate G32 (the net, unchanged)
# ───────────────────────────────────────────────────────
"""A REFUSAL CANNOT BE RAISED WITHOUT A SENTENCE — checked where it is raised.

WHAT GOES WRONG WITHOUT THIS
============================
The PO ruled on 2026-08-19 that `params.detail` never reaches a screen: the
words a user reads come from the catalogue entry for the refusal's
`message_key`, and from nowhere else. That ruling is correct and it has a sharp
edge, which the ruling itself names:

    "that is worse than the defect being fixed, and it is the exact shape of
     DEF-320: a path that looks handled and communicates nothing."

**An unresolved key does not render as an ugly dotted string. It renders as
NOTHING.** The clerk clicks Save, the server refuses with a perfectly correct
422, the screen has no sentence to show, and the click appears to do nothing at
all. There were 57 of those in the Work module alone on 2026-09-05.

WHY HERE AND NOT ONLY IN G32
============================
G32 reads the tree with `ast` and fails when a raised key resolves to nothing.
It works and it is not going anywhere — it is the net, and it covers raise sites
no test ever executes, which nothing here can.

What it cannot do is arrive first. A gate speaks once the branch has the fault;
by then the wave has landed, the lane has moved on, and somebody else spends an
evening writing eleven catalogues. Both times this happened the recurrence
arrived *while the previous repair was being pushed*.

**The earliest point at which a raised key can be checked is the moment it is
raised**, because there is no tool a lane invokes to "raise a refusal" the way
`file_defect.py` is invoked to file a row — a lane types the raise into a
service and then runs its own test. So the check lives in the constructor every
refusal in this codebase passes through, and it fires the first time the lane
runs the test it is writing in r11 step 2c: their own `pytest`, on their own
file, in seconds, with a traceback pointing at their own raise.

That is deliberately preferred over a `conftest` fixture. A fixture fires in the
same runs, but it belongs to the shared suite, it can be skipped by running a
file that does not import it, and its failure names the TEST rather than the
raise. This fires wherever the code is exercised — pytest, a shell, a management
command — and names the line.

⚠ **WHAT IT CANNOT DO, SAID PLAINLY (hard-won law 1).** It only sees a raise
that something EXECUTES. A refusal on a branch no test takes is invisible here
and is exactly what G32 is for. The two are complements, and neither replaces
the other. Of the five keys that landed silently on 2026-09-05, this would have
caught two — `work.rules.triggerUnknown` and `work.rules.triggerNotOfSource`,
both exercised by `test_tc7b_a_rule_with_an_unknown_trigger_is_refused_at_the_door`
in the same commit that raised them — and G32 caught all five an hour later.

WHY IT IS OFF IN PRODUCTION, AND WHY THAT IS NOT LAW 3 POINTING THE OTHER WAY
============================================================================
`REFUSAL_KEYS_MUST_RESOLVE` is False in `base.py` and True in the test settings.
Law 3 says the unsafe option must be the one you type — and here the UNSAFE
direction is raising. A missing catalogue entry in production would turn a clean
422 refusal into a 500: the customer would lose the refusal they were entitled
to, in exchange for a fault report they cannot read. The catalogue is also a
frontend build artefact that a backend image need not carry at all. So the safe
default is off, and the place it must never be off is the one place it can
actually change an outcome — the run a lane makes before their code exists on
any branch.

⚠ **AND WHEN IT IS ON, A MISSING CATALOGUE IS A HARD FAILURE, NOT A PASS.** If
the file cannot be read, this raises rather than waving every key through. A
check that silently degrades to always-true is the *check that cannot fail* this
repository records against `--stat`, against `>= 0` and against
`toContain('disabled')`; it would have reported a clean run over all 57 silent
refusals.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings

#: i18next answers a `count` call through these suffixes, so a key that is
#: present only in its plural forms IS resolved. G32 learnt this as DEF-323,
#: where an exact match reported `dashboard.period.age` as "renders raw to a
#: user" — a false statement inside a headline count a reader trusts.
PLURAL_SUFFIXES = ("_zero", "_one", "_two", "_few", "_many", "_other")

#: `06-backend/../07-frontend/src/i18n/locales/en.json`. English is the source
#: catalogue: a key is WRITTEN there first and the other ten follow. Checking
#: all eleven here would fail a raise for a missing TRANSLATION, which is a
#: different fault with its own gate (G15 parity), and would refuse a lane's
#: test run for something it is not doing wrong.
_DEFAULT_CATALOGUE = (
    Path(__file__).resolve().parent.parent.parent
    / "07-frontend" / "src" / "i18n" / "locales" / "en.json"
)

#: Keys that were already raised-and-silent when this check landed. See the file
#: itself for the three properties that keep it from becoming an allowlist, and
#: for why the copy is not written here. `DEF-MET-4093` owns every line.
PARK_FILE = Path(__file__).resolve().parent / "refusal_keys_parked.txt"

_keys: frozenset[str] | None = None
_loaded_from: Path | None = None
_parked: frozenset[str] | None = None


def parked() -> frozenset[str]:
    """The keys this check knowingly lets through, read from the park file.

    ⚠ **A MISSING PARK FILE IS A HARD FAILURE, NOT AN EMPTY SET.** An empty set
    would make every parked key start raising — which sounds like the strict
    behaviour and is in fact the opposite of a check working: thirteen tests go
    red at once for a reason none of them names, and the next lane deletes the
    guard rather than the file. Refuse instead, and say which file is gone.
    """
    global _parked
    if _parked is None:
        if not PARK_FILE.is_file():
            raise UnresolvedMessageKey(
                f"the park file {PARK_FILE} is missing. It records the keys that were "
                "already raised-and-silent when this check landed; without it this check "
                "cannot tell a NEW fault from an OLD one. Restore it or turn "
                "REFUSAL_KEYS_MUST_RESOLVE off."
            )
        _parked = frozenset(
            line.split("::", 1)[0].strip()
            for line in PARK_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    return _parked


class UnresolvedMessageKey(BaseException):
    """Raised when a refusal is constructed with a key no catalogue defines.

    ⚠ **IT DERIVES FROM `BaseException`, NOT `Exception`, AND THAT IS THE WHOLE
    POINT OF IT.** The place this fires is inside `raise
    errors.ValidationError(...)`, and the code around such a raise is full of
    handlers that would swallow an ordinary exception: `pytest.raises(
    errors.ValidationError)` in the very test that exercises the refusal,
    `except Exception` in a provider seam, Django's own
    `convert_exception_to_response`. Every one of them would turn this guard
    into silence — which is precisely the failure it exists to prevent, wearing
    the guard's own clothes.

    `test_tc7b_a_rule_with_an_unknown_trigger_is_refused_at_the_door` is the
    concrete case: it wraps the raise in `pytest.raises(errors.ValidationError)`,
    so an `Exception` subclass here would be caught by the assertion, the test
    would PASS, and the key would still resolve to nothing.

    It is never raised outside a test run — see the module docstring.
    """


def _catalogue_path() -> Path:
    return Path(getattr(settings, "REFUSAL_CATALOGUE_PATH", None) or _DEFAULT_CATALOGUE)


def load(force: bool = False) -> frozenset[str]:
    """The catalogue's keys, read once and cached.

    Cached because this runs inside every refusal the API can produce and a
    13,738-key JSON parse per refusal would be felt. `force=True` is for the
    tests that add and remove a key to prove this guard bites.
    """
    global _keys, _loaded_from
    path = _catalogue_path()
    if _keys is None or force or _loaded_from != path:
        if not path.is_file():
            raise UnresolvedMessageKey(
                f"REFUSAL_KEYS_MUST_RESOLVE is on and the catalogue is missing at {path}. "
                "Point REFUSAL_CATALOGUE_PATH at en.json or turn the setting off — this "
                "check does NOT wave keys through when it cannot read the catalogue, "
                "because a check that silently becomes always-true is worse than no check."
            )
        _keys = frozenset(json.loads(path.read_text(encoding="utf-8")))
        _loaded_from = path
    return _keys


def resolves(key: str) -> bool:
    """True when `key`, or any i18next plural form of it, has a sentence."""
    catalogue = load()
    return key in catalogue or any(key + suffix in catalogue for suffix in PLURAL_SUFFIXES)


def assert_resolves(key: str, *, raised_by: str) -> None:
    """Refuse a refusal that would reach a person as silence.

    `raised_by` says which exception class was being constructed, so the message
    reads as an instruction rather than as a puzzle: the lane is looking at their
    own traceback and the next line of it is their own `raise`.
    """
    if not getattr(settings, "REFUSAL_KEYS_MUST_RESOLVE", False):
        return
    if resolves(key):
        return
    if key in parked():
        # Already silent before this check existed, and owned by DEF-MET-4093.
        # Letting it through is what makes this guard a RATCHET rather than a
        # thirteen-test outage that gets the guard deleted instead of the file.
        return
    raise UnresolvedMessageKey(
        f"{raised_by} was raised with message_key {key!r}, which no catalogue defines.\n"
        f"  Since the PO's ruling of 2026-08-19 the server's `detail` text never reaches a\n"
        f"  screen, so this refusal would reach a clerk as SILENCE — the click does nothing\n"
        f"  and no sentence appears anywhere. 57 of these shipped in the Work module alone.\n"
        f"  WRITE THE SENTENCE in all eleven catalogues under 07-frontend/src/i18n/locales/,\n"
        f"  each in its own language rather than translated from English (B14 rule 35), and\n"
        f"  five or six words for a refusal (B14 rule 33). Then this passes and so does G32.\n"
        f"  Catalogue read: {_catalogue_path()}"
    )
