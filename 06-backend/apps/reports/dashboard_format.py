# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-019 (S7 / DSH-01 — the landing screen)   Screens: S7
# Rules:    BR-REP-029 (money and counts arrive PRE-FORMATTED; the client does
#           no currency math) · BR-TEN-080 (storage 6 dp · API 4 dp · DISPLAY
#           2 dp) · BR-SHL-023 (one money formatting path — see the tension
#           note below, which is REPORTED and not resolved here) ·
#           CLAUDE.md rule 2 (NUMERIC(18,6) + CHAR(3), never a float; round
#           only at finalization/display)
# Tests:    06-backend/tests/test_cr012_dashboard_dsh01.py
# Impacts:  apps/reports/dashboard_regions.py (the only caller)
# ───────────────────────────────────────────────────────
"""DSH-01's display strings, computed on the SERVER (BR-REP-029).

The PO's build spec for this screen, verbatim: *"Money and counts arrive
pre-formatted as strings — no client-side currency math."* This module is that
sentence. It is the ONLY place in `apps/reports` where a figure is turned into
something a person reads, and it is the only place on the dashboard's path where
money is rounded at all.

════════════════════════════════════════════════════════════════════════════
WHY THE SERVER AND NOT THE CELL — AND THE RULE THIS IS IN TENSION WITH
════════════════════════════════════════════════════════════════════════════
`BR-SHL-023` says *one money formatting path*, and today that path is the
client's `MoneyCell`, which trims 4 dp to 2 dp with `Intl.NumberFormat`'s
`halfExpand`. The PO's DSH-01 spec moves the dashboard's formatting to the
server. **Both cannot be literally true at once, so the tension is stated rather
than smoothed** (hard-won law 1 — a comment claiming a guarantee is not the
guarantee):

  * The reason the PO's direction is right: a client that rounds money can round
    it differently from the bill. Hard rule 2 keeps rounding on the server.
  * The reason this is not a second, divergent path: **every function here is
    built to reproduce `MoneyCell`'s en-US output byte for byte.** `$184,320.00`,
    `-$42.50`, `$0.00`, `€184,320.00` — each was taken from
    `Intl.NumberFormat` itself and is asserted in the test file. The two
    implementations agree by construction, and a drift in either goes RED.
  * Reconciling them permanently — deleting one path — is the platform-shell
    owner's call, not this screen's. It is REPORTED, not taken.

════════════════════════════════════════════════════════════════════════════
NO LOCALE LIBRARY, AND THAT IS DELIBERATE
════════════════════════════════════════════════════════════════════════════
This backend has no `babel` and adding a dependency to format one screen is not
a trade this lane may make. What it DOES have is the tenant's own
`tenant_settings.number_format`, whose value set is exactly two — `"1,234.56"`
and `"1.234,56"` (`apps.tenancy.services.NUMBER_FORMATS`). Those two conventions
are implemented here in full and nothing else is guessed: an unrecognised value
falls back to the first, which is the seeded default.

The currency SYMBOL map covers exactly the five codes this platform seeds
(`SEED_CURRENCIES` = USD, CAD, MXN, EUR, GBP) and each entry is a transcription
of what `Intl.NumberFormat("en-US", {style: "currency"})` emits — not a choice.
**A code outside the five renders as `1,234.56 XYZ`**, the amount beside its
CHAR(3), which is what `MoneyCell` itself falls back to for an unknown currency.
Nothing is invented for a currency this product does not sell.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

#: What a figure that is not there renders as. It is a typographic placeholder
#: and never a number — r10's DSH-01 draws it in the service-mix value column
#: and on every activity row with no amount. Kept here so ONE constant decides
#: it and a screen cannot render an absence as `0.00` by accident.
EM_DASH = "—"

#: BR-TEN-080: what a person reads is two decimals, in every locale.
DISPLAY_PLACES = Decimal("0.01")

#: `apps.tenancy.services.NUMBER_FORMATS`, mirrored rather than imported: this
#: module is in `reports` and importing a neighbour's constant is a cross-module
#: read (B1). A value outside the pair falls back to the first, which is the
#: seeded default (`services.provision_tenant` writes `NUMBER_FORMATS[0]`).
GROUPING = {
    "1,234.56": (",", "."),
    "1.234,56": (".", ","),
}
DEFAULT_NUMBER_FORMAT = "1,234.56"

#: Transcribed from `Intl.NumberFormat("en-US", {style: "currency", currency})`
#: for the five codes `apps.tenancy.services.SEED_CURRENCIES` allows. Not a
#: design choice — the point is that the server's string and the client's string
#: are the same string.
CURRENCY_SYMBOLS = {
    "USD": "$",
    "CAD": "CA$",
    "MXN": "MX$",
    "EUR": "€",
    "GBP": "£",
}

#: The separator `Intl` puts between the amount and a trailing symbol in the
#: `1.234,56` convention (de-DE renders `184.320,00 €` with U+00A0).
NBSP = " "


def _separators(number_format: str | None) -> tuple[str, str]:
    return GROUPING.get(str(number_format or ""), GROUPING[DEFAULT_NUMBER_FORMAT])


def _decimal(value: Any) -> Decimal | None:
    """A served figure as an exact `Decimal`, or None when there is no figure.

    Accepts the `Decimal` an owner computed AND the decimal STRING a published
    read model already serialised (`payments.outstandings` serves its buckets as
    `f"{amount:.4f}"`). It never accepts a float and never constructs one: the
    string path is `Decimal(str)`, which is exact, and CLAUDE.md rule 2's whole
    point is that no money value in this product passes through IEEE-754.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):  # pragma: no cover — nothing here serves one
        raise TypeError("a money figure never arrives as a float (CLAUDE.md rule 2)")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def group(digits: str, thousands: str) -> str:
    """`"184320"` → `"184,320"`. Pure string work over an already-exact figure."""
    out = []
    for index, char in enumerate(reversed(digits)):
        if index and index % 3 == 0:
            out.append(thousands)
        out.append(char)
    return "".join(reversed(out))


def money_display(
    value: Any, *, currency: str | None, number_format: str | None = None
) -> str | None:
    """One money figure as the string a person reads, or None when absent.

    `None` in, `None` out, and that is load-bearing rather than defensive: every
    `None` reaching here is a figure an owning module declined to state, and
    turning one into `$0.00` is DEF-104's shape — the account screen said
    **$0.00** while the ledger held an issued, unpaid **$108.88**. A caller that
    wants an em-dash asks for one by name (`EM_DASH`); it never falls out of a
    formatting failure.

    Rounded ONCE, here, half-up (B4.4 ❄️ / `ROUND_HALF_UP`), to BR-TEN-080's two
    display places — which is the same convention `MoneyCell`'s `halfExpand`
    applies on the client, stated rather than inherited.
    """
    amount = _decimal(value)
    if amount is None:
        return None
    thousands, point = _separators(number_format)
    quantized = amount.quantize(DISPLAY_PLACES, rounding=ROUND_HALF_UP)
    sign = "-" if quantized < 0 else ""
    whole, _, frac = format(abs(quantized), "f").partition(".")
    body = group(whole, thousands) + point + (frac or "00").ljust(2, "0")[:2]
    code = (currency or "").upper()
    symbol = CURRENCY_SYMBOLS.get(code)
    if symbol is None:
        # `MoneyCell`'s own fallback for a currency `Intl` does not know: the
        # amount beside its CHAR(3), never a guessed glyph.
        return f"{sign}{body} {code}".rstrip() if code else f"{sign}{body}"
    if point == ",":  # the `1.234,56` convention puts the symbol after (de-DE)
        return f"{sign}{body}{NBSP}{symbol}"
    return f"{sign}{symbol}{body}"


def money_display_short(
    value: Any, *, currency: str | None, number_format: str | None = None
) -> str | None:
    """r10's abbreviated service-mix value — `$238k`, not `$238,400.00`.

    Transcribed from the reference, whose `.val` column reads `$238k` / `$76k` /
    `$28k` (`05-prototype/r10-2026-08-16/SMARTBillHub.dc.html`). r10 uses ONE
    suffix and so does this: at or above a thousand the figure is expressed in
    whole thousands with `k`, and below that it is the ordinary two-decimal
    string. A million therefore reads `$1,234k` rather than `$1.2M` — a second
    suffix is not in the reference and is not invented here.

    **This is a LABEL, not a figure.** The exact decimal travels beside it on the
    same row, so nothing downstream ever reads money out of an abbreviation.
    """
    amount = _decimal(value)
    if amount is None:
        return None
    if abs(amount) < 1000:
        return money_display(amount, currency=currency, number_format=number_format)
    thousands_of = (amount / 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    thousands, _point = _separators(number_format)
    sign = "-" if thousands_of < 0 else ""
    body = group(format(abs(thousands_of), "f"), thousands) + "k"
    code = (currency or "").upper()
    symbol = CURRENCY_SYMBOLS.get(code)
    if symbol is None:
        return f"{sign}{body} {code}".rstrip() if code else f"{sign}{body}"
    if _point == ",":
        return f"{sign}{body}{NBSP}{symbol}"
    return f"{sign}{symbol}{body}"


def count_display(value: Any, *, number_format: str | None = None) -> str | None:
    """A count as the string a person reads — `1,247`. None in, None out.

    Counts are grouped with the tenant's own separator for the same reason money
    is: `1.247` and `1,247` are the same number to the product and different
    numbers to a reader, and the screen must not be the place that decides.
    """
    if value is None:
        return None
    if isinstance(value, bool):  # pragma: no cover — a flag is not a count
        raise TypeError("a boolean is not a count")
    thousands, _point = _separators(number_format)
    number = int(value)
    sign = "-" if number < 0 else ""
    return sign + group(str(abs(number)), thousands)


def percent_display(value: Any) -> str | None:
    """A whole-number percentage, `86%`. None in, None out.

    **Whole numbers, half-up, and the same rounded figure drives the bar**
    (BR-REP-026 decision 1, from the PO's worked examples): *"the percentage is
    rounded to a whole number and the bar width uses that same rounded figure,
    so the number and the bar can never disagree."* Callers therefore round ONCE
    with `whole_percent` below and pass the integer to both.
    """
    if value is None:
        return None
    return f"{int(value)}%"


def whole_percent(part: Any, whole: Any, *, floor_visible: bool = False) -> int | None:
    """`part / whole` as a whole-number percentage, half-up. None when it cannot.

    `None` when either side is absent or `whole` is zero — **no division is
    performed on an empty month**, which is the PO's worked example D: a
    dashboard on day one of the cycle draws five em-dashes and never a `0%`,
    because `0%` reads as *"we sell this and sold none of it"* while an absence
    reads as *"nothing has been billed yet"*.

    `floor_visible` is the PO's worked example E, stated as arithmetic: a
    NON-ZERO part floors at **1**, so $1,900 beside $238,400 draws a visible 1%
    bar rather than nothing. Zero is the only value that draws nothing.
    """
    numerator = _decimal(part)
    denominator = _decimal(whole)
    if numerator is None or denominator is None or denominator == 0:
        return None
    percent = (numerator * 100 / denominator).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    result = int(percent)
    if floor_visible and result == 0 and numerator > 0:
        return 1
    return result


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-012 (12-governance/11-change-requests.md §CR-012 — the PO's build spec and the FULL DSH-01 requirements, both verbatim · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-026/029/034 · 12-governance/02-decision-log.md 2026-08-18 §"THE MTD-REVENUE FORECAST IS A TYPED TENANT TARGET" and §"THE DASHBOARD SERVICE-MIX BAR IS A SHARE OF THE LARGEST SERVICE")
# screens: S7
# generated: 2026-08-18 by story-coder (CR-012 DSH-01 lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — every formatter below was asserted against the string `Intl.NumberFormat` actually emits, and the first implementation returned `$184320.00` (no grouping) and `184.320,00€` (no NBSP); both failures are quoted in the test file.
# exceptions: (1) BR-SHL-023 says one money formatting path and this is a SECOND one — the tension is stated in the module docstring, the two are built to agree byte for byte, and reconciling them is the platform-shell owner's call, REPORTED not taken · (2) the currency symbol map covers the five SEEDED codes and every entry is transcribed from Intl rather than chosen; an unknown code renders as `amount CODE`, which is MoneyCell's own fallback · (3) `money_display_short` abbreviates with ONE suffix (`k`) because r10's reference uses one; `$1,234k` is deliberate and `$1.2M` is not invented
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
