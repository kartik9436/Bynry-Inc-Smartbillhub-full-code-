# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-012 (EP-CWP-04) — the fee table and the *IF YOU APPLY* box ·
#           US-CWP-014 — the same figures on Check and send, which *"must not
#           recompute them independently"*. Screens: CWP-008 · CWP-009
# Rules:    CLAUDE.md hard rule 2 (PO re-sign 2026-08-22, verbatim: *"We
#           already confirmed this - MOney 4 decimal, percentage 6 decimal ,
#           display both 2 decimal"*) · CR-068 §2d (the portal computes no
#           money — it reads and it presents) · B4 (rounding happens at
#           finalization or display, never in the middle)
# Tests:    06-backend/tests/test_us_cwp_012_availability.py TC-1 ·
#           test_us_cwp_014_check_and_send.py TC-7
# Impacts:  apps/portal/availability.py · selectors.py · guest_api.py
# ───────────────────────────────────────────────────────
"""ONE money presenter for the whole guest surface: four decimals stored, two
on screen, and BOTH on the wire.

WHY BOTH TRAVEL, WHICH IS THE ONLY DESIGN DECISION IN THIS FILE
---------------------------------------------------------------
Hard rule 2 says money is STORED to four decimals and DISPLAYS at two, and the
wave's exit test is *"every money figure displays two decimals from four
stored"*. A payload that carried only `"185.00"` could not be checked against
that sentence at all — the four-decimal value would have been thrown away
before anything could look at it — and a payload that carried only `"185.0000"`
would leave every screen to format money for itself, which is how two screens
start disagreeing about a rounding rule.

So every money member of every guest response is `{"amount": "185.0000",
"display": "$185.00"}`: the stored value at full fidelity, and the sentence a
person reads, made once, here. The walkthrough asserts the second is on screen
and the test asserts the pair agree.

⚠ **AND THEY ARE STRINGS.** JSON has one number type and it is a double;
`Decimal("185.0000")` serialised as a JSON number reaches the browser as `185`,
and a four-decimal figure reaches it as something that is not the stored value.
Every money member on this surface is a string for the reason
`apps/payments/selectors.py` and `apps/notifications/selectors.py` already give.

THE FOUR KINDS OF CELL, because *"nothing"* is three different facts
--------------------------------------------------------------------
`US-CWP-012` TC-4 is blunt about it: a service the utility does not carry
reads *"Not here"* with no fee — *"⚠ not `$0.00`, which means free"*. So:

  * `amount` — a figure the utility configured: `$185.00`, or `$0.00` when it
    priced it at zero and means it;
  * `included` — no separate charge is attached, so nothing extra is payable;
  * `none` — there is nothing to quote, drawn as an em dash.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from core.money_fields import AMOUNT_PLACES

#: What a display figure is rounded to. Two, by hard rule 2, and named so
#: nobody writes `"0.01"` at a call site and quietly disagrees with the rule.
DISPLAY_PLACES = 2
DISPLAY_QUANTUM = Decimal(1).scaleb(-DISPLAY_PLACES)
STORED_QUANTUM = Decimal(1).scaleb(-AMOUNT_PLACES)

KIND_AMOUNT = "amount"
KIND_INCLUDED = "included"
KIND_NONE = "none"

#: ⚠ **A WORD IS NOT SENT FROM HERE; A KIND IS.** `Included` and the em dash
#: are WORDS, and words on a customer screen come out of the eleven catalogues
#: (B14 rule 35 — a catalogue is written in its own language, not translated
#: from English). A server that helpfully sent the string `"Included"` would
#: have made this one cell English-only on ten of them, silently, with every
#: test green. So `display` is filled in ONLY for a currency figure, which is
#: the same in every catalogue, and the other two kinds carry `display: null`
#: for the screen to name from its own words.


def stored(value: Any) -> str:
    """The value as it is stored — four decimal places, as a string."""
    return str(Decimal(str(value)).quantize(STORED_QUANTUM))


def display(value: Any, *, currency_symbol: str = "$") -> str:
    """The value as a person reads it — two decimal places, with its symbol.

    ⚠ **ROUNDED HERE AND NOWHERE EARLIER.** B4's rule is that rounding happens
    at display; a figure rounded on the way out of the database and then added
    to another rounded figure is how a total stops matching its own lines.
    """
    return f"{currency_symbol}{Decimal(str(value)).quantize(DISPLAY_QUANTUM):,}"


def amount(value: Any, *, currency: str = "USD", currency_symbol: str = "$") -> dict[str, Any]:
    """A money cell: the stored figure, the displayed figure and its currency."""
    return {
        "kind": KIND_AMOUNT,
        "amount": stored(value),
        "display": display(value, currency_symbol=currency_symbol),
        "currency": currency,
    }


def included() -> dict[str, Any]:
    """No separate charge is attached — the screen says `Included`, in its own
    language, and never `$0.00` (`US-CWP-012` TC-4)."""
    return {"kind": KIND_INCLUDED, "amount": None, "display": None, "currency": None}


def nothing() -> dict[str, Any]:
    """Nothing to quote — the screen draws an em dash, and never a zero."""
    return {"kind": KIND_NONE, "amount": None, "display": None, "currency": None}
