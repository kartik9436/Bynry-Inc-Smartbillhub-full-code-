# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-045 · US-CWP-046 · US-CWP-006 (EP-CWP-08) — the payment
#           journey, built before a vendor exists. Screens: CWP-038 · CWP-039
# Rules:    BR-CWP-057 (a token, never a card number) · BR-INT-038 (an adapter
#           TRANSLATES; it decides nothing) · BR-INT-040 (per-item results,
#           never a batch boolean) · B14 rule 33 (a refusal is six words or
#           fewer) · CLAUDE.md hard rule 6 (idempotency on money)
# Change:   CR-068 phase 5 · PO ruling 2026-09-05 — providers are integrations,
#           and beta ships the whole journey behind a test one
# Tests:    06-backend/tests/test_us_cwp_046_tc*.py · the conformance kit
# Impacts:  apps/integrations/adapters/__init__.py (the ONE line that binds it)
#           · apps/integrations/manifests/payments_sandbox.py
# ───────────────────────────────────────────────────────
"""Test payments — the whole card journey, deterministically, with nobody's money.

⚠ **THIS IS NOT A MOCK AND IT IS NOT IN A TEST DIRECTORY.** It is a shipped
adapter for a shipped provider, and it is the reason the seven payment stories
can be built and clicked through before a vendor is chosen (PO ruling
2026-09-05). A utility connects to it exactly as it will connect to Worldpay.

WHAT IT DOES
--------------
`card_page` answers a tokenisation: a token, a brand, four digits and an expiry.
`charge` answers a debit against a token. Both are pure functions of their
input — no clock, no randomness, no network — so a walkthrough that pays
`$142.18` gets the same answer on every machine and in every replay.

⚠ **THE FOUR DIGITS ARE `4242` AND THE TOKEN IS OBVIOUSLY FAKE** (`tok_test_…`).
That is deliberate and is a safety property rather than laziness: anybody
looking at a screen, a log or a database row can tell at a glance that no real
card is involved. A test provider that produced plausible-looking tokens would
be one screenshot away from somebody believing a real payment had been taken.

WHAT IT DELIBERATELY CANNOT DO
--------------------------------
A real authorisation, a real decline from an issuer, a chargeback, and the card
network's own *confirm it is you* step. Those arrive with a vendor. Nothing here
pretends otherwise, and `test()`'s sentence says so to the person who pressed
the button.

THE BEHAVIOUR SWITCH — WHY A REFUSAL IS CONFIGURABLE
------------------------------------------------------
`behaviour` on the connection is `approve` · `decline` · `timeout`. A tester
changes one field on Settings and the product's **real** refusal path runs: the
screen that says a payment was declined, and the one that says nothing was
taken because the provider never answered. Those two screens are otherwise
provable only by a unit test asserting a branch nobody has ever looked at,
which is the shape hard-won law 2 was written for.

⚠ **`timeout` WRITES NOTHING, AND THAT IS THE POINT OF HAVING IT.** `US-CWP-045`
TC-6 says a gateway that never answers must leave no payment row, and TC-7 says
the retry carries the SAME idempotency key the first attempt used — so the
debit is never taken twice. Neither case can be exercised against a provider
that always says yes.

WHAT THIS FILE DOES NOT DECIDE (BR-INT-038)
---------------------------------------------
It does not allocate a payment to a bill, post to the ledger, write an audit
row, or choose an idempotency key. It translates a request into an answer.
Everything that follows a charge belongs to `apps/payments`, which is exactly
why none of that has to be rebuilt when a real vendor replaces this file.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from apps.integrations.adapters.base import (
    ITEM_FAILED,
    ITEM_SUCCEEDED,
    Adapter,
    ConnectionView,
    FieldError,
    FieldErrors,
    ItemResult,
    RunResult,
    TestResult,
)

#: The three behaviours, and the manifest declares the same closed list. Kept
#: here as constants rather than string literals so a typo is an ImportError
#: rather than a connection that silently always approves.
APPROVE = "approve"
DECLINE = "decline"
TIMEOUT = "timeout"
BEHAVIOURS = (APPROVE, DECLINE, TIMEOUT)

#: ⚠ SIX WORDS OR FEWER (B14 rule 33). These are the only sentences this file
#: can return; none interpolates anything a customer typed.
SENTENCE_OK = "Test payments answered."
SENTENCE_DECLINED = "The test provider declined it."
SENTENCE_TIMEOUT = "The test provider did not answer."
SENTENCE_UNKNOWN_OPERATION = "That operation is not offered."

#: What `test()` says, and it is a warning rather than a boast: a green test
#: here proves the wiring and proves nothing about a card.
TEST_SENTENCE = "Test payments answered. No real money moves."

#: The brand and the last four every token carries. See the module docstring
#: for why they are conspicuous.
TEST_BRAND = "Visa"
TEST_LAST_FOUR = "4242"
TEST_EXPIRES_MONTH = 11
TEST_EXPIRES_YEAR = 2027


def _token_for(reference: str) -> str:
    """A stable fake token for a reference — same input, same token, for ever.

    ⚠ **DERIVED, NOT RANDOM.** A random token would make a replayed walkthrough
    produce a second saved card, and `stored_payment_instruments` refuses two
    live rows carrying one token — so the replay would fail on a uniqueness
    error that says nothing about what went wrong. A digest keeps a replay
    idempotent by construction.
    """
    digest = hashlib.sha256(f"payments_sandbox:{reference}".encode()).hexdigest()[:24]
    return f"tok_test_{digest}"


class PaymentsSandboxAdapter(Adapter):
    """Four methods and only four — the conformance kit refuses a fifth."""

    key = "payments_sandbox"

    def validate(self, config: Mapping[str, Any]) -> FieldErrors:
        """The manifest's shape check has already run; this adds the vocabulary.

        A `behaviour` outside the three is refused BY NAME rather than falling
        back to `approve`: a connection that silently approves when it was asked
        to decline is a test provider that cannot be used to test a refusal.
        """
        behaviour = str(config.get("behaviour") or "").strip()
        #: ⚠ A LIST, NOT A TUPLE. `FieldErrors` is `list[FieldError]` and the
        #: conformance kit checks `isinstance(..., list)` and `== []` — a tuple
        #: is the same thing to a reader and a failure to the kit, which is how
        #: this file failed cases 4 and 7 on its first run.
        if behaviour and behaviour not in BEHAVIOURS:
            return [
                FieldError(
                    field="behaviour",
                    message_key="integrations.payments_sandbox.behaviour_unknown",
                    params={"given": behaviour, "allowed": ", ".join(BEHAVIOURS)},
                )
            ]
        return []

    def test(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        *,
        recipient: str | None = None,
    ) -> TestResult:
        """The smallest real instance: tokenise one card and answer.

        Never raises for a refusal (`BR-INT-019`) — a connection set to
        `decline` answers `ok=False` with the provider's words underneath,
        because that is what a real provider's declined test would do.
        """
        behaviour = self._behaviour(conn)
        if behaviour == DECLINE:
            return TestResult(
                ok=False, sentence=SENTENCE_DECLINED, provider_text="TEST-DECLINE: card declined"
            )
        if behaviour == TIMEOUT:
            return TestResult(
                ok=False, sentence=SENTENCE_TIMEOUT, provider_text="TEST-TIMEOUT: no response"
            )
        return TestResult(ok=True, sentence=TEST_SENTENCE)

    def execute(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        work: Sequence[Mapping[str, Any]],
    ) -> RunResult:
        """One attempt at a batch. Per-item outcomes, never a boolean.

        ⚠ **`confirmed` IS FALSE ON A TIMEOUT AND THAT IS NOT A DETAIL.** The
        runtime turns an unconfirmed run into `unconfirmed` rather than a green
        word (`BR-INT-018`), which is what stops a caller recording a payment
        the provider never acknowledged.
        """
        if not work:
            return RunResult(items=(), confirmed=True)
        behaviour = self._behaviour(conn)
        items: list[ItemResult] = []
        for index, one in enumerate(work):
            ref = str(one.get("ref", index))
            operation = str(one.get("operation") or "charge")
            if operation not in ("charge", "card_page"):
                items.append(
                    ItemResult(
                        ref=ref,
                        outcome=ITEM_FAILED,
                        detail=operation,
                        provider_text=f"TEST-UNKNOWN-OP: {operation}",
                    )
                )
                continue
            if behaviour == TIMEOUT:
                #: Nothing is returned and nothing is written. US-CWP-045 TC-6.
                items.append(
                    ItemResult(
                        ref=ref,
                        outcome=ITEM_FAILED,
                        detail=None,
                        provider_text="TEST-TIMEOUT: no response",
                    )
                )
                continue
            if behaviour == DECLINE:
                items.append(
                    ItemResult(
                        ref=ref,
                        outcome=ITEM_FAILED,
                        detail=None,
                        provider_text="TEST-DECLINE: card declined",
                    )
                )
                continue
            items.append(
                ItemResult(ref=ref, outcome=ITEM_SUCCEEDED, detail=self._detail(operation, one))
            )
        return RunResult(
            items=tuple(items),
            #: A timeout is exactly the case where the far end said nothing.
            confirmed=behaviour != TIMEOUT,
        )

    def describe(self, conn: ConnectionView) -> str:
        """The line on the card. It names the behaviour, because a connection
        set to `decline` that looked identical to one set to `approve` is a
        support call nobody can answer from a screenshot."""
        return f"Test payments · {self._behaviour(conn)} · no real money"

    # ── the rest is private; the conformance kit checks that ──────────────

    def _behaviour(self, conn: ConnectionView) -> str:
        given = str((conn.config or {}).get("behaviour") or "").strip()
        return given if given in BEHAVIOURS else APPROVE

    def _detail(self, operation: str, one: Mapping[str, Any]) -> str:
        if operation == "card_page":
            return f"{TEST_BRAND} ●●●●{TEST_LAST_FOUR}"
        return str(one.get("amount") or "")


def tokenise(reference: str) -> dict[str, Any]:
    """What a `card_page` hands back — the ONLY thing this product ever stores.

    ⚠ **A MODULE FUNCTION AND NOT A FIFTH ADAPTER METHOD.** `US-INT-015` says
    an adapter has four public methods and the conformance kit refuses a fifth,
    so tokenisation — which is a provider-shaped fact rather than a batch of
    work — is exposed beside the class. When a real provider lands, its own
    tokenise lives beside its own adapter the same way.

    There is no card number in the arguments. Nothing in this product ever holds
    one: a real card page is the VENDOR's page, the number is typed there, and
    what comes back is the token below (`BR-CWP-057`).
    """
    return {
        "gateway_token": _token_for(reference),
        "brand": TEST_BRAND,
        "last_four": TEST_LAST_FOUR,
        "expires_month": TEST_EXPIRES_MONTH,
        "expires_year": TEST_EXPIRES_YEAR,
        "kind": "card",
    }
