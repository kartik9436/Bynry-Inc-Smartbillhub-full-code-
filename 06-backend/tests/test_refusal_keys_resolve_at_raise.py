# ── Trace ──────────────────────────────────────────────
# Defect:  the five `work.rules.*` keys of 2026-09-05, which landed as silence
#          within the hour of another lane finishing the same repair on 59
#          others (57 of them in the Work module). A clerk saving a rule with
#          no name, an unknown trigger, an unknown source module, no template,
#          or a trigger belonging to another module clicked Save and NOTHING
#          happened.
# Rules:   PO ruling 2026-08-19 (`bec921e`) — `params.detail` never reaches a
#          screen · CLAUDE.md law 7 (prove a guard RED first, in the harness
#          that will run it) · law 1 (a comment claiming a guarantee is not it)
# Impacts: core/refusal_catalogue.py · core/errors.py::ApiError.__init__
# ───────────────────────────────────────────────────────
"""THE GUARD BITES, AND IT BITES THROUGH `pytest.raises`.

WHY THE SECOND HALF OF THAT SENTENCE IS THE WHOLE TEST
======================================================
The natural way to write this guard is an ordinary `Exception`. It does not
work, and it fails in the most expensive way available: **silently, inside the
one test that was going to catch the fault.**

`tests/test_us_wrk_037_rules.py::test_tc7b_a_rule_with_an_unknown_trigger_is_
refused_at_the_door` exercises two of the five keys that landed silently, and it
is written — correctly — as::

    with pytest.raises(errors.ValidationError):
        rules.create_rule(...)

An `Exception` raised from inside `ValidationError.__init__` is caught by
`except Exception` handlers all over the request path, and this one would have
been swallowed by the assertion itself in tests that assert a refusal *by base
class*. The guard would report green over the exact fault it was written for —
the *check that cannot fail* this repository has recorded against `--stat`,
against `assert x >= 0`, and against `toContain('disabled')` matching a Tailwind
variant.

So `UnresolvedMessageKey` derives from `BaseException`, and
`test_the_guard_is_not_swallowed_by_a_pytest_raises_on_the_refusal_itself`
below is the clause that proves it. Delete the `BaseException` base and that
clause goes red while everything else here stays green.
"""
from __future__ import annotations

import json

import pytest
from django.test import override_settings

from core import errors, refusal_catalogue

#: The five raised by `apps/work/rules.py`. They resolved to nothing for about
#: an hour on 2026-09-05 and a clerk who met one saw the click do nothing.
THE_FIVE_THAT_LANDED_SILENT = [
    "work.rules.nameRequired",
    "work.rules.sourceUnknown",
    "work.rules.templateRequired",
    "work.rules.triggerNotOfSource",
    "work.rules.triggerUnknown",
]


@pytest.fixture
def catalogue(tmp_path):
    """A catalogue this test owns, so a case can add and remove a sentence.

    Pointing `REFUSAL_CATALOGUE_PATH` somewhere else also re-loads the cache —
    it keys on the path — so no case can leak a mutated catalogue into another.
    """

    def _write(keys):
        path = tmp_path / "en.json"
        path.write_text(json.dumps({key: "a sentence" for key in keys}), encoding="utf-8")
        return path

    return _write


def test_a_refusal_with_no_sentence_is_refused_where_it_is_raised(catalogue):
    path = catalogue([])
    with override_settings(REFUSAL_CATALOGUE_PATH=str(path), REFUSAL_KEYS_MUST_RESOLVE=True):
        with pytest.raises(refusal_catalogue.UnresolvedMessageKey) as caught:
            errors.ValidationError(errors.VAL_REQUIRED, message_key="work.rules.nameRequired")
    said = str(caught.value)
    assert "work.rules.nameRequired" in said
    assert "SILENCE" in said, "the message must say what the clerk experiences, not just 'missing key'"
    assert "eleven catalogues" in said, "the message must say what to do about it"


def test_a_refusal_that_has_a_sentence_is_built_normally(catalogue):
    path = catalogue(["work.rules.nameRequired"])
    with override_settings(REFUSAL_CATALOGUE_PATH=str(path), REFUSAL_KEYS_MUST_RESOLVE=True):
        raised = errors.ValidationError(errors.VAL_REQUIRED, message_key="work.rules.nameRequired")
    assert raised.message_key == "work.rules.nameRequired"


def test_an_i18next_plural_form_resolves(catalogue):
    """DEF-323: an exact match called `dashboard.period.age` unrendered when
    i18next answers it through `_one`/`_other`. A guard that is WRONG about a
    working key gets switched off."""
    path = catalogue(["billing.lines.count_one", "billing.lines.count_other"])
    with override_settings(REFUSAL_CATALOGUE_PATH=str(path), REFUSAL_KEYS_MUST_RESOLVE=True):
        errors.ValidationError(errors.VAL_RANGE, message_key="billing.lines.count")


def test_an_inline_field_error_needs_a_sentence_too(catalogue):
    """Field errors render UNDER THE INPUT through `envelopeErrors`. An
    unresolved one turns the field red with no reason written beside it."""
    path = catalogue(["errors.val-001"])
    with override_settings(REFUSAL_CATALOGUE_PATH=str(path), REFUSAL_KEYS_MUST_RESOLVE=True):
        with pytest.raises(refusal_catalogue.UnresolvedMessageKey) as caught:
            errors.ValidationError(
                errors.VAL_REQUIRED,
                field_errors=[{"field": "certified_until", "message_key": "work.tech.certExpired"}],
            )
    assert "work.tech.certExpired" in str(caught.value)
    assert "field_errors" in str(caught.value)


def test_the_guard_is_not_swallowed_by_a_pytest_raises_on_the_refusal_itself(catalogue):
    """THE CLAUSE THAT JUSTIFIES `BaseException`.

    This is how the tests that exercise refusals are actually written — see
    `test_tc7b_a_rule_with_an_unknown_trigger_is_refused_at_the_door`, which
    covers two of the five keys that landed silent. If the guard were an
    ordinary `Exception`, `pytest.raises(errors.ValidationError)` would be
    satisfied by it in tests asserting a refusal by base class, the case would
    PASS, and the key would still resolve to nothing.
    """
    path = catalogue([])
    with override_settings(REFUSAL_CATALOGUE_PATH=str(path), REFUSAL_KEYS_MUST_RESOLVE=True):
        with pytest.raises(refusal_catalogue.UnresolvedMessageKey):
            with pytest.raises(errors.ValidationError):
                raise errors.ValidationError(errors.VAL_REQUIRED, message_key="a.key.with.no.sentence")
    assert not issubclass(refusal_catalogue.UnresolvedMessageKey, Exception), (
        "an Exception subclass is caught by `except Exception` all over the request path and "
        "by the assertions in the very tests that exercise refusals — the guard would report "
        "green over the fault it exists for"
    )


def test_a_missing_catalogue_is_a_hard_failure_and_never_a_pass(tmp_path):
    """A check that silently becomes always-true would have reported a clean run
    over all 57 silent refusals."""
    with override_settings(
        REFUSAL_CATALOGUE_PATH=str(tmp_path / "nothing-here.json"), REFUSAL_KEYS_MUST_RESOLVE=True
    ):
        with pytest.raises(refusal_catalogue.UnresolvedMessageKey) as caught:
            errors.ValidationError(errors.VAL_REQUIRED, message_key="anything")
    assert "catalogue is missing" in str(caught.value)


def test_nothing_is_raised_when_the_setting_is_off(catalogue):
    """Production keeps its 422. A missing sentence must never become a 500 in
    front of a customer — see base.py, where this defaults to False."""
    path = catalogue([])
    with override_settings(REFUSAL_CATALOGUE_PATH=str(path), REFUSAL_KEYS_MUST_RESOLVE=False):
        raised = errors.ValidationError(errors.VAL_REQUIRED, message_key="no.sentence.anywhere")
    assert raised.message_key == "no.sentence.anywhere"


# ── the real keys, against the real catalogue ──────────────────────────────
@pytest.mark.parametrize("key", THE_FIVE_THAT_LANDED_SILENT)
def test_the_five_keys_that_landed_as_silence_have_sentences_today(key):
    """Named one by one rather than counted, so a red says WHICH clerk action
    goes quiet. Reads the repository's own catalogue, not a fixture."""
    refusal_catalogue.load(force=True)
    assert refusal_catalogue.resolves(key), (
        f"{key} resolves to nothing: the clerk clicks and nothing happens"
    )


# ── the derived fallback keys: a closed set of 20, checked all at once ──────
#: `default_message_key(code)` is what a refusal carries when the caller supplies
#: no `message_key`. It is not something a lane writes — it is a fixed list owned
#: by `core/errors.py`, one entry per catalog code — so the useful question is
#: not "did this raise resolve" but "does the whole list resolve", which does not
#: depend on which paths a test run happens to reach.
#:
#: ⚠ **EIGHT OF THE TWENTY RESOLVE TO NOTHING, AND THAT IS A LIVE DEFECT, NOT A
#: TOLERATED STATE.** A refusal raised with one of these codes and no explicit
#: key reaches a clerk as silence. `DEF-SHL-4092` owns them; the one reachable
#: today is `apps/metering/premises_owners.py:883` — a staff member converting a
#: premises owner to a master account, where the owner owns no premises or owns
#: several, clicks and nothing happens.
#:
#: ⚠ **THE LIST BELOW IS NARROW, LOUD AND EXPIRING — the same three properties
#: `g112_computed_key_gaps.txt` is held to, and for the same reason: a park file
#: without them becomes an allowlist.** An entry that no longer reproduces FAILS
#: this test, so the line must be deleted in the same diff as the copy that fixes
#: it. Nothing here licenses a NEW one: a ninth code losing its sentence fails
#: too. The copy itself is not written here on purpose — it is eleven catalogues
#: in eleven languages, and `g112_computed_key_gaps.txt` records the ruling that
#: a lane may not "honestly invent it in ten languages it cannot check" (B14
#: rule 35, PO 2026-09-03).
DERIVED_KEYS_WITH_NO_SENTENCE = {
    "errors.biz-approval",
    "errors.biz-cap",
    "errors.biz-completeness",
    "errors.biz-immutable",
    "errors.biz-locked",
    "errors.biz-sod",
    "errors.biz-window",
    "errors.sys-drift",
}


def test_the_derived_fallback_keys_are_exactly_as_recorded():
    """Every catalog code's default key, measured against the real catalogue.

    Green when reality matches the record above. RED in BOTH directions — a
    ninth code losing its sentence, and one of the eight gaining one without the
    line being deleted. A one-directional check here would let the record rot
    into an allowlist, which is what the expiring property exists to prevent.
    """
    refusal_catalogue.load(force=True)
    silent = {
        errors.default_message_key(code)
        for code in errors.ALL_CODES
        if not refusal_catalogue.resolves(errors.default_message_key(code))
    }
    newly_silent = sorted(silent - DERIVED_KEYS_WITH_NO_SENTENCE)
    assert not newly_silent, (
        f"{newly_silent} now resolve to nothing. A refusal raised with that code and no "
        "explicit message_key reaches a clerk as silence — write the sentence in all "
        "eleven catalogues, or add the key here with a defect row that owns it"
    )
    fixed = sorted(DERIVED_KEYS_WITH_NO_SENTENCE - silent)
    assert not fixed, (
        f"{fixed} have sentences now — delete them from DERIVED_KEYS_WITH_NO_SENTENCE in "
        "the same diff as the copy that fixed them. A record that outlives what it "
        "records is an allowlist (g112_computed_key_gaps.txt's expiring property)"
    )
    assert len(DERIVED_KEYS_WITH_NO_SENTENCE) == 8, "the recorded figure moved without its diff"


def test_a_refusal_that_derives_its_key_is_not_refused_at_the_raise(catalogue):
    """The scope, asserted rather than described (hard-won law 1).

    `test_be02_errors.py` constructs `BizError(BIZ_IMMUTABLE)` at import time
    with no message_key. That is not a lane writing a key it forgot to define —
    it is one of the eight above, which the previous case reports in full. If
    this ever starts raising, the per-raise check has widened by accident and
    a whole module's tests will fail one at a time for a reason the failure
    does not name.
    """
    path = catalogue([])
    with override_settings(REFUSAL_CATALOGUE_PATH=str(path), REFUSAL_KEYS_MUST_RESOLVE=True):
        raised = errors.BizError(errors.BIZ_IMMUTABLE, br_ref="BR-BIL-004")
    assert raised.message_key == "errors.biz-immutable"


# ── the park file: narrow, loud, EXPIRING ──────────────────────────────────
def test_the_park_file_holds_exactly_thirteen_keys_and_every_one_is_still_silent():
    """LOUD: the figure is asserted, not merely stored.

    Thirteen clerk-facing refusals were already raised-and-silent when this
    check landed — four premises-owner refusals and nine discount refusals, all
    in the blind spot `G32` declares about itself (a positional `message_key`
    helper imported from a sibling module). `DEF-MET-4093` owns them.

    ⚠ **TWELVE NOW.** `rating.discounts.proof_kinds_required` was written in
    all eleven catalogues on 2026-09-19 (`DEF-RAT-5816`): a clerk who chose
    *Apply and approve, with proof* and ticked no document was refused at the
    commit by that literal string, printed raw on screen. The park file's
    EXPIRING property is what made moving this number compulsory rather than
    optional — the entry fails the case below the moment the key gains a
    sentence, so the line and the copy land in one diff.
    """
    refusal_catalogue.load(force=True)
    parked = refusal_catalogue.parked()
    assert len(parked) == 12, (
        f"the park file holds {len(parked)} keys, not the 12 DEF-MET-4093 records. "
        "Adding one needs a defect row and a line in the register; removing one needs "
        "the copy that fixed it, in the same diff"
    )
    resolved = sorted(k for k in parked if refusal_catalogue.resolves(k))
    assert not resolved, (
        f"EXPIRED: {resolved} have sentences now — delete them from "
        "core/refusal_keys_parked.txt in the same diff as the copy that fixed them. "
        "A park entry that no longer reproduces is what turns a ratchet into an allowlist"
    )


def test_every_parked_key_is_still_raised_by_shipped_code():
    """EXPIRING, the second way an entry can go stale.

    A key can stop reproducing by gaining a sentence — the case above — or by
    its raise site simply going away. `g112_computed_key_gaps.txt` fails on both
    and this must too, or the file quietly accumulates keys nothing raises and
    the next real finding in that area is waved straight through.
    """
    import pathlib

    apps = pathlib.Path(__file__).resolve().parent.parent / "apps"
    sources = "\n".join(
        p.read_text(encoding="utf-8", errors="replace") for p in apps.rglob("*.py")
    )
    orphaned = sorted(k for k in refusal_catalogue.parked() if f'"{k}"' not in sources)
    assert not orphaned, (
        f"EXPIRED: {orphaned} are parked but no longer raised anywhere under apps/. "
        "Delete the lines — a park file listing keys nothing raises is an allowlist"
    )


def test_a_key_that_is_not_parked_is_still_refused(catalogue):
    """The park file is NARROW: it licenses its own thirteen and nothing else.

    Asserted rather than described, because 'narrow' is exactly the property a
    reader assumes and nobody checks.
    """
    path = catalogue([])
    with override_settings(REFUSAL_CATALOGUE_PATH=str(path), REFUSAL_KEYS_MUST_RESOLVE=True):
        # A sibling of a parked key — one character different — is NOT parked.
        with pytest.raises(refusal_catalogue.UnresolvedMessageKey):
            errors.ValidationError(
                errors.VAL_REQUIRED, message_key="metering.premises_owner.category_requiredx"
            )
