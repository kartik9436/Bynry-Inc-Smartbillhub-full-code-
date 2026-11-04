# ── Trace ──────────────────────────────────────────────
# Story:    CR-110-BRC04 wave E — "RULED · EVERY REFUSAL CARRIES A CODE".
#           PO 2026-09-16: "build refusal code in api responses so that we cna
#           know what it is", then, shown all eight with the security
#           consequence written against each: "go with your recommendation -
#           implment all these code". Screens: S142 *Who has been reading*
# Rules:    BR-INT-044 (the refusal reveals nothing — NOT amended by this
#           wave) · BR-INT-035 (every partner read is a run a manager can
#           read) · BR-INT-040 (per-item results, never a batch boolean —
#           which is where the codes are stored) · B14 rule 33 (a fact on
#           screen is six words or fewer) · CLAUDE.md hard-won law 7
#           (ask what would make this check pass wrongly)
# Tests:    this file — the RECORD half. The WIRE half is
#           test_us_int_041_partner_surface.py::test_tc3_the_six_refusals_are_one_refusal,
#           and both walk the SAME six through `_six_refusals` so they can
#           never be proved over different sets.
# Impacts:  apps/integrations/runners/serve.py · partner_api.py
# ───────────────────────────────────────────────────────
"""The eight refusal codes — two on the wire, six in our record only.

⚠ **THE FALSE PASS THIS FILE IS WRITTEN AGAINST IS NAMED, BECAUSE IT IS THE
OBVIOUS ONE.** A test that asserts the eight codes exist and that
`PartnerRefused.causes` names the right one passes perfectly over a build that
has started telling partners which guard refused them — which is the enumeration
oracle `BR-INT-044` exists to close and the exact thing the PO was shown and
ruled against. So this wave is proved by TWO cases that must both hold:

  * the six auth refusals are BYTE-IDENTICAL, status-identical and
    timing-identical on the wire (`test_tc3_the_six_refusals_are_one_refusal`);
  * the same six produce SIX DIFFERENT causes in our record (here).

Either alone is worthless. A build that records nothing passes the first; a
build that leaks the cause passes the second.

⚠ **AND THE RECORD HAS ONE ASYMMETRY, STATED RATHER THAN HIDDEN.** Five of the
six auth causes write an `IntegrationRun` row; `KEY_UNKNOWN` cannot, because a
run row is a row ON A CONNECTION and a key we have never seen names none. It is
recorded on the logger instead, and `test_a_key_we_have_never_seen_has_no_run_row_to_write`
asserts that absence deliberately so it cannot become a silent gap — CLAUDE.md's
own lesson that an absence is invisible to every check this repo has.
"""

from __future__ import annotations

import ast
import inspect
import logging
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.integrations import models, partner_api, rate_limit_store
from apps.integrations.runners import serve
from tests.test_us_int_041_partner_surface import (  # noqa: F401
    BLOCKED_ADDRESS,
    # ⚠ **THE VIEW IS IMPORTED RATHER THAN NAMED** (`CR-110-BRC04` phase 2
    # waves 3 and 4, 2026-09-16). `partner_api.partner_payments` — the phase-1
    # flat route — is RETIRED and answers `410` without reaching the rate
    # limit, so a case driven through it would stop exercising the thing it is
    # named for while still passing its refusal assertions. Every case here is
    # about the DOOR, and the door is the same nine checks at every address.
    PARTNER_PAYMENTS,
    _bytes,
    _full_scope,
    _partner_get,
    _payments,
    _six_refusals,
    aclarian,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

#: ⚠ **READ OFF THE MODULE, NEVER RETYPED (`DEF-INT-5512`).** A logger's NAME is
#: what decides whether anything is printed, because `config/settings/base.py`
#: configures three trees — `django`, `apps` and `core` — and a name outside all
#: three reaches the root logger, which has no handler. Hard-coding a name here
#: would let the test and the product disagree about which logger is being
#: proved, which is how the first draft of this wave shipped a record that was
#: silently discarded in production and green in pytest.
SERVE_LOGGER = serve.logger.name


def test_the_refusal_logger_is_inside_the_configured_tree():
    """⚠ THE GUARD FOR THE FALSE PASS THAT ALREADY HAPPENED ONCE HERE.

    `caplog` attaches its own handler to whatever logger name it is handed, so
    **a logger with no configured handler anywhere looks perfectly healthy in
    pytest** — every assertion about what was logged passes, and the running
    product prints nothing. This wave's first draft named its logger
    `smartbillhub.integrations.serve`, which is under none of the three trees
    `config/settings/base.py` configures, and the `KEY_UNKNOWN` record — the one
    cause with nowhere else to go — was discarded in production. `DEF-2161`
    records the identical mechanism one package along.

    The name is therefore asserted against the settings rather than against a
    string, so this cannot come back by someone renaming a logger.
    """
    from django.conf import settings

    trees = set(settings.LOGGING["loggers"])
    assert any(
        SERVE_LOGGER == one or SERVE_LOGGER.startswith(one + ".") for one in trees
    ), (
        f"{SERVE_LOGGER!r} is under none of {sorted(trees)} — it reaches the root "
        "logger, which has no handler, and nothing it writes is ever printed"
    )


def _recorded_causes(row) -> set[str]:
    """The machine-readable half of one run row — `BR-INT-040`'s items."""
    return {one["ref"] for one in (row.items or [])}


# ══════════════════════════════════════════════════════════════════════════
# The table itself — eight codes, split two ways, and the split is the ruling
# ══════════════════════════════════════════════════════════════════════════


def test_the_eight_codes_are_the_pos_own_table():
    """The PO was shown eight rows and ruled all eight in. This is the list.

    The order matters only in that it is theirs; the SPLIT is the ruling, and
    it is asserted here rather than left to be read out of two constants that
    could drift.

    ⚠ **A NINTH JOINED THEM ON 2026-09-16 AND THE EIGHT DID NOT MOVE**
    (`CR-110-BRC04` phase 2). `UTILITY_INACTIVE` implements the PO's OTHER
    ruling of the same day — *"you have to also check whether connector is
    activae whether tenant is active"* — which adds a CAUSE and therefore adds
    a code. It EXTENDS the table rather than superseding it, so the eight are
    still asserted in their own order, as their own prefix, and the split they
    were ruled into is what decides where the ninth falls: record-only, because
    a distinct code on the wire would answer *does this utility exist and is it
    switched on* to anyone holding any key.
    """
    assert serve.REFUSAL_CODES[:8] == (
        "RATE_LIMIT_REACHED",
        "COUNTER_UNAVAILABLE",
        "KEY_UNKNOWN",
        "KEY_REVOKED",
        "KEY_EXPIRED",
        "ADDRESS_NOT_ALLOWED",
        "CONNECTOR_DISABLED",
        "OPERATION_NOT_IN_SCOPE",
    ), "the PO's own eight, in their order, unmoved"
    assert serve.REFUSAL_CODES[8:] == ("UTILITY_INACTIVE",)
    assert serve.WIRE_CODES == ("RATE_LIMIT_REACHED", "COUNTER_UNAVAILABLE"), (
        "the ninth did NOT join the two a partner may tell apart"
    )
    assert len(serve.RECORD_ONLY_CODES) == 7
    assert set(serve.WIRE_CODES) | set(serve.RECORD_ONLY_CODES) == set(serve.REFUSAL_CODES)
    assert set(serve.CAUSE_TEXT) == set(serve.REFUSAL_CODES), (
        "a code with no sentence would reach S142 as a machine string"
    )


def test_every_cause_sentence_is_six_words_or_fewer_and_names_no_code():
    """B14 rule 33 — a FACT on screen is six words or fewer, no rule id, no
    internal code. These strings ARE the *What they took* column on S142."""
    for code, text in serve.CAUSE_TEXT.items():
        assert len(text.split()) <= 6, f"{code} reads {text!r} — {len(text.split())} words"
        assert "BR-" not in text and "OQ-" not in text and "_" not in text


def test_resolve_caller_still_has_no_early_return():
    """⚠ THE TRAP THIS WAVE WAS WARNED ABOUT, ASSERTED STRUCTURALLY.

    Knowing which guard refused makes branching early tempting, and an early
    return re-opens the timing oracle even when every arm raises identical
    words, because the cheap causes answer sooner. `resolve_caller` therefore
    has exactly ONE `raise` and exactly ONE `return`, and this reads the source
    rather than trusting a comment (hard-won law 1 — a comment claiming a
    guarantee is not the guarantee).
    """
    tree = ast.parse(inspect.getsource(serve.resolve_caller))
    raises = [one for one in ast.walk(tree) if isinstance(one, ast.Raise)]
    returns = [one for one in ast.walk(tree) if isinstance(one, ast.Return)]
    assert len(raises) == 1, f"{len(raises)} raises — the guards have grown a branch"
    assert len(returns) == 1, f"{len(returns)} returns — an early return is the oracle"


# ══════════════════════════════════════════════════════════════════════════
# The record half — six refusals, six causes
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_six_refusals_produce_six_different_causes_in_our_record(
    brazos, dana, aclarian, caplog
):
    """⚠ THE OTHER HALF OF THIS WAVE, AND IT IS WORTHLESS WITHOUT ITS TWIN.

    `test_tc3_the_six_refusals_are_one_refusal` proves a partner cannot tell the
    six apart. This proves WE can — *"WorldPay refused: key expired, 14 times
    since 06:00"* is the sentence the PO asked to be able to read.

    Five causes land on a run row, which is what S142 draws; the sixth is
    `KEY_UNKNOWN` and has no connection to hang a row on, so it lands on the
    logger. **Six distinct causes either way** — a build that recorded one
    generic *refused* six times would pass every wire assertion in this repo.
    """
    caplog.set_level(logging.INFO, logger=SERVE_LOGGER)
    refusals = _six_refusals(brazos, dana)
    assert [one[1] for one in refusals] == list(serve.RECORD_ONLY_CODES[:1]) + [
        serve.CODE_KEY_REVOKED,
        serve.CODE_KEY_EXPIRED,
        serve.CODE_ADDRESS_NOT_ALLOWED,
        serve.CODE_CONNECTOR_DISABLED,
        serve.CODE_OPERATION_NOT_IN_SCOPE,
    ]

    with tenant_ctx(brazos):
        rows = list(models.IntegrationRun.objects.order_by("started_at"))
    recorded = [_recorded_causes(one) for one in rows]

    assert len(rows) == 5, (
        "five of the six auth causes have a connection to file a row against; "
        f"KEY_UNKNOWN has none and is on the logger — got {len(rows)} rows"
    )
    assert recorded == [
        {serve.CODE_KEY_REVOKED},
        {serve.CODE_KEY_EXPIRED},
        {serve.CODE_ADDRESS_NOT_ALLOWED},
        {serve.CODE_CONNECTOR_DISABLED},
        {serve.CODE_OPERATION_NOT_IN_SCOPE},
    ], f"the run rows must tell the five apart, not repeat one word: {recorded}"

    # …and every one of the six is in the record SOMEWHERE, distinctly.
    #
    # ⚠ **COMPARED AGAINST THE CAUSES THIS HELPER ACTUALLY WALKS, AND NOT
    # AGAINST `RECORD_ONLY_CODES` (`CR-110-BRC04` phase 2).** It was the whole
    # constant until 2026-09-16, when a SEVENTH record-only cause was ruled in
    # — `UTILITY_INACTIVE`, from *"you have to also check whether connector is
    # activae whether tenant is active"* — and `_six_refusals` does not produce
    # it, because switching the utility off is not a fact about a key and the
    # six here are. Left as it was, this case went red naming a cause it never
    # set up, which reads as a hole in the record and is not one.
    #
    # The seventh is proved in its own file, and NAMED here so the pair cannot
    # be lost: `tests/test_cr110_phase2_partner_reference.py`'s
    # `test_the_seven_auth_refusals_are_still_one_refusal` walks all seven
    # against the wire, and `test_a_switched_off_utility_is_refused_and_recorded`
    # walks this one against the record.
    logged = " ".join(one.getMessage() for one in caplog.records if one.name == SERVE_LOGGER)
    assert serve.CODE_KEY_UNKNOWN in logged
    walked = {one[1] for one in refusals}
    everywhere = set().union(*recorded) | {code for code in walked if code in logged}
    assert everywhere == walked, (
        f"six refusals, {len(everywhere)} distinguishable causes: {sorted(everywhere)}"
    )
    assert set(serve.RECORD_ONLY_CODES) - walked == {serve.CODE_UTILITY_INACTIVE}, (
        "a record-only cause exists that neither this helper nor the phase-2 "
        "file walks — add it to one of them rather than widening this line"
    )


@pytest.mark.django_db
def test_the_run_row_reads_as_a_sentence_a_manager_can_act_on(brazos, dana, aclarian):
    """S142's *What they took* column, on a refusal. Words, not codes.

    The access log builds that column as `summary.split(" · ")[0]`, so the cause
    text has to be the FIRST field of the summary — and the codes stay in
    `items`, where a person never sees them.
    """
    with tenant_ctx(brazos):
        _payments(brazos, dana, 5)
    _partner_get(brazos, PARTNER_PAYMENTS, address=BLOCKED_ADDRESS)
    with tenant_ctx(brazos):
        row = models.IntegrationRun.objects.get()
    assert row.summary.split(" · ")[0] == "address not on the allowlist"
    assert "refused" in row.summary
    assert "ADDRESS_NOT_ALLOWED" not in row.summary, "a code is not a manager's word"
    assert row.items[0]["outcome"] == "skipped", (
        "we declined; nothing failed at the far end (services.outcome_for keeps "
        "the two apart and S142 draws `skipped` neutral)"
    )


@pytest.mark.django_db
def test_two_causes_true_at_once_are_both_recorded(brazos, dana, aclarian):
    """⚠ FIRST-MATCH-WINS WOULD HAVE THROWN AWAY THE HALF THAT MATTERS.

    An expired key presented from an address that is not on the list is rows 5
    AND 6 of the PO's table. *Which of the guards failed* is the whole
    diagnostic value of this wave, so the record carries ALL that were true —
    and an ordering that picked one would be the branch the module docstring
    forbids, wearing a tidy-up.
    """
    with tenant_ctx(brazos):
        _payments(brazos, dana, 5)
        credential = models.IntegrationCredential.objects.get()
        models.IntegrationCredential.objects.filter(pk=credential.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
    response = _partner_get(brazos, PARTNER_PAYMENTS, address=BLOCKED_ADDRESS)

    assert response.status_code == 404
    assert _bytes(response) == (
        b'{"error": "We cannot serve this request.", "code": "REFUSED"}'
    ), "two causes must not make a different answer than one"

    with tenant_ctx(brazos):
        row = models.IntegrationRun.objects.get()
    assert _recorded_causes(row) == {
        serve.CODE_KEY_EXPIRED,
        serve.CODE_ADDRESS_NOT_ALLOWED,
    }
    assert row.summary.startswith("key expired, address not on the allowlist")


@pytest.mark.django_db
def test_a_key_we_have_never_seen_has_no_run_row_to_write(brazos, dana, aclarian, caplog):
    """⚠ THE ONE ASYMMETRY IN THIS WAVE, ASSERTED SO IT CANNOT GO QUIET.

    `IntegrationRun.connection` is a non-null FK, so a run row is a row ON A
    CONNECTION. A key we have never seen names none — and this surface answers
    for five ERP connectors at once, so choosing one would file a stranger's
    knock against a named partner. The second reason is worth as much: a row per
    unknown key is a row any stranger can make us write, which points an
    amplifier at our own database. Rows 4–8 all need a key WE issued.

    It is recorded on the logger with its code. Stated here rather than left to
    be discovered, because an absence is invisible to every other check we have.
    """
    caplog.set_level(logging.INFO, logger=SERVE_LOGGER)
    with tenant_ctx(brazos):
        _payments(brazos, dana, 5)
    _partner_get(brazos, PARTNER_PAYMENTS, key="sbh_live_never_issued_at_all")

    with tenant_ctx(brazos):
        assert not models.IntegrationRun.objects.exists()
    logged = [one.getMessage() for one in caplog.records if one.name == SERVE_LOGGER]
    assert any(serve.CODE_KEY_UNKNOWN in one for one in logged), logged
    assert not any("never_issued_at_all" in one for one in logged), (
        "a logger is where a secret escapes — the key must not be in the line"
    )


@pytest.mark.django_db
def test_an_unknown_key_reports_one_cause_and_not_four(brazos, dana, aclarian):
    """With no credential there is no connection either, so the allowlist, the
    switch and the scope all answer `False` — truthfully, and about nothing.

    A naive build reports four causes for one stranger and buries the real
    signal. `KEY_UNKNOWN` alone is the honest record of that request.
    """
    with tenant_ctx(brazos):
        with pytest.raises(serve.PartnerRefused) as caught:
            serve.resolve_caller(
                provider_key=partner_api.partner_provider_keys(),
                presented_key="sbh_live_never_issued_at_all",
                source_address=BLOCKED_ADDRESS,
                operation="serve_payment",
            )
    assert caught.value.causes == (serve.CODE_KEY_UNKNOWN,)


# ══════════════════════════════════════════════════════════════════════════
# The wire half — the TWO codes that travel, and the six that never do
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_two_rate_limit_codes_are_distinct_on_the_wire(brazos, dana, aclarian, monkeypatch):
    """⚠ ROW 2 IS WHAT THE PO ACTUALLY NEEDED.

    Until this wave a partner refused because OUR counter store is down got the
    identical sentence as one who genuinely called too fast, and a manager
    reading *rate limit reached* during an outage goes to look at the ceiling
    instead of at the store. Both are `429` and both are safe to distinguish for
    one stated reason: a `429` is only reachable by a caller who has ALREADY
    authenticated, so the code tells them nothing they did not know.
    """
    with tenant_ctx(brazos):
        _payments(brazos, dana, 1)
        models.IntegrationConnection.objects.filter(provider_key=aclarian.provider_key).update(
            config={
                **aclarian.config,
                serve.RATE_LIMIT_CONFIG_KEY: 1,
            }
        )
    serve.reset_partner_limits()
    _partner_get(brazos, PARTNER_PAYMENTS)  # the one call allowed
    over_limit = _partner_get(brazos, PARTNER_PAYMENTS)

    def _raises(**kwargs):
        raise rate_limit_store.CounterUnavailable("the store is unreachable")

    monkeypatch.setattr(rate_limit_store, "take", _raises)
    uncountable = _partner_get(brazos, PARTNER_PAYMENTS)

    assert over_limit.status_code == uncountable.status_code == 429
    assert over_limit["Retry-After"] == uncountable["Retry-After"]
    assert _bytes(over_limit) == (
        b'{"error": "We cannot serve this request.", "code": "RATE_LIMIT_REACHED"}'
    )
    assert _bytes(uncountable) == (
        b'{"error": "We cannot serve this request.", "code": "COUNTER_UNAVAILABLE"}'
    )
    # …and the manager's sentence differs too, which is the half S142 draws.
    with tenant_ctx(brazos):
        windows = [
            one.summary.split(" · ")[0]
            for one in models.IntegrationRun.objects.order_by("started_at")
        ]
    assert windows[-2:] == ["rate limit reached", "call limit could not be counted"]


@pytest.mark.django_db
def test_no_auth_cause_ever_reaches_the_wire(brazos, dana, aclarian):
    """The negative that the whole ruling rests on, written as a sweep.

    Not *the bodies are equal* — that is the other case — but *no body anywhere
    contains any of the six names*, headers included. A lane that put the cause
    in a header, a trace id or a second field would pass a body comparison and
    fail this.
    """
    for name, _code, response, _elapsed in _six_refusals(brazos, dana):
        wire = _bytes(response) + b"".join(
            f"{key}:{value}".encode() for key, value in response.items()
        )
        for code in serve.RECORD_ONLY_CODES:
            assert code.encode() not in wire, f"{name} leaked {code} on the wire"
        for text in serve.CAUSE_TEXT.values():
            assert text.encode() not in wire, f"{name} leaked {text!r} on the wire"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-110-BRC04 wave E, the CR's "RULED · EVERY REFUSAL CARRIES A CODE" section
# generated: 2026-09-16 by the CR-110-BRC04 wave E build lane
# checklist: A✔ B n/a(no screen — the cause already reaches S142 through `outcome` and the summary) C✔ D✔ E✔ F✔ G✔ H=pending(🔒 row in 09-human-review-ledger.md)
# gates: pytest tests/test_cr110_refusal_codes.py · pytest tests/test_us_int_041_partner_surface.py
# exceptions: KEY_UNKNOWN writes no run row — a run row is a row ON A CONNECTION and an unknown key names none; asserted as an absence on purpose
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
