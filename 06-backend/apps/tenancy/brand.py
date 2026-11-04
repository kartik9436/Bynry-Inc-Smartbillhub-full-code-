# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-005 (S8 Company profile → Brand)  Screens: S8, shell-chrome
# Change:   CR-048 wave D — the utility's own mark.
# Defect:   DEF-195 (ruled 2026-08-16, drawn nowhere until now)
# Rules:    BR-TEN-019 (brand colours are #RRGGBB) · CR-007 PO ruling
#           2026-08-16 — *"Create name based or initial base dummy logo"* and,
#           on how many letters, *"2 letters"* (12-governance/11-change-requests.md
#           §"CR-007 — the generated logo mark, specified"; OQ-257)
# Decision: OQ-800(a) — the CONTRAST call, decided by this lane and recorded in
#           12-governance/02-decision-log.md 2026-08-30 rather than re-asked.
# Tests:    06-backend/tests/test_cr048_brand_mark.py
# Impacts:  apps/tenancy/selectors.company_profile (publishes `mark`) ·
#           07-frontend SettingsCompanyTab + AppShell · every document
#           renderer that draws a letterhead (the templates wave consumes it)
# ───────────────────────────────────────────────────────
"""The generated two-letter mark, and the ink that is readable on it.

Pure functions — no ORM, no request objects, no I/O. Everything a document
renderer or a screen needs to draw the mark is computed here once, so the
letters on a bill and the letters in the app header cannot disagree.

WHAT THE PO RULED, VERBATIM (CR-007, 2026-08-16)
------------------------------------------------
*"Create name based or initial base dummy logo"* — and, asked how many
letters, *"2 letters"*. So a utility that has uploaded nothing still has
SOMETHING in the logo's place, on every document, from its first day. There is
no unbranded state to design around.

Two details were DERIVED with that ruling and are recorded beside it:
  * the letters come from the **trading name (`dba_name`), falling back to the
    legal name** — which is already what `SettingsCompanyTab`'s letterhead
    preview and `notifications/rendering.py`'s `utility_name` both do, so this
    is the third place agreeing rather than a new opinion;
  * the colour is **`brand_primary_hex`**, the tenant's own. The accent has its
    own job on a bill and a mark wearing it would compete with it.

THE ONE JUDGMENT CALL — WHAT IF THEIR COLOURS ARE UNREADABLE (OQ-800(a))
------------------------------------------------------------------------
A utility may pick a pale yellow. White letters on it are invisible; on a BILL
that is a legal document a customer cannot read. Three options were on the
table: accept anything and let them see it; compute the contrast and pick the
text colour ourselves; or refuse a colour pair below a threshold.

**DECIDED HERE: we keep their colour and choose the ink.** A billing product
does not tell a utility its brand colours are wrong — they will not accept it,
and they are not wrong; they are a brand. What IS ours is the text drawn on
top, so that is what moves.

**THE THRESHOLD, AND WHY IT IS THIS NUMBER RATHER THAN A TASTE.** WCAG's
contrast ratio between two colours is `(L1 + 0.05) / (L2 + 0.05)` over relative
luminance L. Against WHITE a background scores `1.05 / (L + 0.05)`; against
BLACK it scores `(L + 0.05) / 0.05`. Set them equal:

    (L + 0.05)^2 = 1.05 x 0.05 = 0.0525
     L + 0.05    = 0.229128…
     L           = 0.179129…      ← INK_LUMINANCE_THRESHOLD

Above it black wins, below it white wins, and at the crossover BOTH score

    0.229128 / 0.05 = 4.58 : 1

**So picking the better of black and white can never do worse than 4.58:1, for
ANY colour in the RGB cube — and WCAG AA asks 4.5:1 for normal text.** That is
the whole argument: the rule cannot produce an unreadable mark, so it never has
to refuse one. `tests/test_cr048_brand_mark.py` walks the cube and asserts the
4.58 floor, so if anyone moves the constant the suite says so.

**TO OVERRULE IT, MOVE ONE NUMBER.** Raise `WCAG_AA_NORMAL_TEXT` to 7.0 (AAA)
and the floor no longer clears it — the test goes red and names the colour,
which is the honest outcome: with only black and white available, AAA is not
reachable against every brand colour, and the next decision would be to darken
or lighten the BACKGROUND, which changes the tenant's colour and is a different
ruling. Nothing here does that silently.

**WHAT IS DELIBERATELY NOT DONE.** No colour is invented. A tenant with no
`brand_primary_hex` gets a mark with `background_hex = None` and `ink_hex =
None`, and the caller falls back to a token it already owns — B8 forbids hex
literals in the stylesheet, and inventing a platform colour here would put one
in the database instead, which is worse.

**AND NOT RASTERISED.** BR-TEN-019's *"rasterized for PDF/print"* clause is
still deferred. This module states the letters, the two colours and the ratio;
turning that into pixels at print resolution is a separate, unbuilt piece of
work (OQ-257's remaining half). Said plainly so "the logo problem is solved"
cannot mean two things.
"""

import re
from typing import Any

#: The two inks the product may choose between. They are the extremes of the
#: scale, so nothing else can score better against an arbitrary background.
INK_DARK = "#000000"
INK_LIGHT = "#FFFFFF"

#: WCAG 2.x AA, normal text. The floor the rule above is measured against.
WCAG_AA_NORMAL_TEXT = 4.5

#: Relative luminance where white and black tie (derived in the docstring).
INK_LUMINANCE_THRESHOLD = 0.1791287847

#: How many letters the mark carries. PO 2026-08-16: *"2 letters"*.
MARK_LETTERS = 2

_HEX6 = re.compile(r"^#([0-9a-fA-F]{6})$")
_HEX3 = re.compile(r"^#([0-9a-fA-F]{3})$")
#: A "letter" for mark purposes is any alphanumeric character — a name may
#: legitimately begin with a digit (*1st Utility District*, *3M Water*).
_WORD = re.compile(r"[^\W_]+", re.UNICODE)


# ── the letters ────────────────────────────────────────────────────────────
def mark_letters(dba_name: str | None, legal_name: str | None, *, fallback: str = "") -> str:
    """The mark's two letters, from the trading name then the legal name.

    Three sources in order, each used only when the one before it is blank:
    `dba_name` (what a customer sees on the bill) → `legal_name` → `fallback`,
    which callers pass as `tenants.name`, the one name a tenant has from the
    signup form. So the mark is never empty for a real tenant.

    Two words or more → the first letter of the first two words, which is what
    makes *Silver Creek Water* and *Silver Creek Water & Sanitation District*
    both give `SC`. One word → its first two letters (`Aquaflow` → `AQ`), never
    one letter beside a gap. One character → that character, honestly.
    """
    source = _first_non_blank(dba_name, legal_name, fallback)
    words = _WORD.findall(source)
    if not words:
        return ""
    if len(words) >= MARK_LETTERS:
        return "".join(word[0] for word in words[:MARK_LETTERS]).upper()
    return words[0][:MARK_LETTERS].upper()


def _first_non_blank(*candidates: str | None) -> str:
    for candidate in candidates:
        if candidate and candidate.strip():
            return candidate.strip()
    return ""


# ── the colour maths (WCAG 2.x, relative luminance) ────────────────────────
def parse_hex(value: str | None) -> tuple[int, int, int] | None:
    """`#RRGGBB` or `#RGB` → (r, g, b), or None when it is not a colour.

    None rather than a refusal: a mark is decoration, and a tenant halfway
    through typing a hex code must not make the Settings screen raise. The
    WRITE path still validates `#RRGGBB` strictly (services.save_company_profile).
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    match = _HEX6.match(text)
    if match:
        digits = match.group(1)
        return tuple(int(digits[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    match = _HEX3.match(text)
    if match:
        digits = match.group(1)
        return tuple(int(digit * 2, 16) for digit in digits)  # type: ignore[return-value]
    return None


def _channel(value: int) -> float:
    """sRGB channel → linear light (WCAG relative-luminance definition)."""
    srgb = value / 255.0
    return srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4


def relative_luminance(value: str | None) -> float | None:
    """WCAG relative luminance L of a colour, 0.0 (black) … 1.0 (white)."""
    rgb = parse_hex(value)
    if rgb is None:
        return None
    r, g, b = (_channel(channel) for channel in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(first: str | None, second: str | None) -> float | None:
    """WCAG contrast ratio between two colours, 1.0 … 21.0."""
    a, b = relative_luminance(first), relative_luminance(second)
    if a is None or b is None:
        return None
    lighter, darker = (a, b) if a >= b else (b, a)
    return (lighter + 0.05) / (darker + 0.05)


def readable_ink(background: str | None) -> str | None:
    """Black or white — whichever a reader can actually see on `background`.

    The tenant's colour is never changed. See this module's docstring for why
    the crossover luminance is the threshold and why the result cannot fall
    below 4.58:1.
    """
    luminance = relative_luminance(background)
    if luminance is None:
        return None
    return INK_DARK if luminance > INK_LUMINANCE_THRESHOLD else INK_LIGHT


def brand_ink(background: str | None) -> str | None:
    """The text colour on a brand-filled PORTAL surface — portal a11y Group A,
    ruling 3(a), PO/QA 2026-10-23: white when white reaches 4.5:1, otherwise
    the dark ink. Mirrors `07-frontend/src/lib/contrast.ts` `inkOnBrand`; both
    are pinned on `#EC3013` (white 4.20 → black 5.00).

    Differs from `readable_ink` only in the band where white scores 4.50–4.58
    (it keeps white there; the mark picks the better of the two). Both pass.
    """
    white = contrast_ratio(INK_LIGHT, background)
    if white is None:
        return None
    return INK_LIGHT if white >= WCAG_AA_NORMAL_TEXT else INK_DARK


def brand_colour_refused(value: str | None) -> bool:
    """True when `value` reaches 4.5:1 with NEITHER white nor the dark ink —
    Group A ruling 3(b): Company → Profile refuses such a colour by name.

    ⚠ **WITH TODAY'S INKS THIS IS NEVER TRUE.** The dark ink is black, and
    against black or white every colour scores at least 4.58:1 (this module's
    docstring). The refusal is built and wired so that it holds the moment the
    dark ink moves; `tests/test_a11y_group_a_brand.py` proves it both ways.
    Decision log 2026-10-23, "Group A colour build: four judgments" (1).
    """
    white = contrast_ratio(INK_LIGHT, value)
    dark = contrast_ratio(INK_DARK, value)
    if white is None or dark is None:
        return False
    return white < WCAG_AA_NORMAL_TEXT and dark < WCAG_AA_NORMAL_TEXT


#: WCAG 2.1 SC 1.4.11 — the focus ring is a non-text boundary.
WCAG_AA_NON_TEXT = 3.0
#: The two light grounds brand text and the focus ring sit on in the portal:
#: a white card and the page (`--color-bg`).
PAGE_WHITE = "#FFFFFF"
PAGE_BG = "#F3F2F2"
#: Brand-coloured TEXT is the brand mixed this much with black (its hover shade).
TEXT_STEP = 88


def mix_with_black(value: str | None, percent: int) -> str | None:
    """`color-mix(in srgb, <value> <percent>%, black)`, computed with the same
    rounding as `07-frontend/src/lib/contrast.ts` `mixWithBlack`."""
    rgb = parse_hex(value)
    if rgb is None:
        return None
    # Round half up, as JavaScript's Math.round does for these non-negative values.
    return "#" + "".join(f"{int(v * percent / 100 + 0.5):02X}" for v in rgb)


def brand_colour_too_light(value: str | None) -> bool:
    """True when Company → Profile must refuse `value` as the PRIMARY colour —
    portal a11y Group A decision 3, PO/QA 2026-10-23 (*"agreed to your
    recommondation"*): its text shade (88% brand, rest black) cannot reach
    4.5:1 on white, or the colour itself — the focus ring — cannot reach 3:1
    on white AND on `#f3f2f2`.

    Worked: `#F5C518` → shade `#D8AD15` 2.12 on white, ring 1.63 / 1.46 →
    refused. `#EC3013` → 5.22, ring 4.20 / 3.76 → saved. Mirrors
    `lib/contrast.ts` `brandColourTooLight`; both are pinned on these figures
    (`tests/test_a11y_group_a_brand.py`, `lib/contrast.test.ts`). False when
    `value` is not a colour (the hex shape is refused elsewhere, BR-TEN-019).
    """
    shade = mix_with_black(value, TEXT_STEP)
    if shade is None:
        return False
    return (
        contrast_ratio(shade, PAGE_WHITE) < WCAG_AA_NORMAL_TEXT
        or contrast_ratio(value, PAGE_WHITE) < WCAG_AA_NON_TEXT
        or contrast_ratio(value, PAGE_BG) < WCAG_AA_NON_TEXT
    )


def hex_for_luminance(luminance: float) -> str:
    """A grey whose relative luminance is (approximately) `luminance`.

    Only a test helper's job in this repo — it exists so the threshold can be
    probed from both sides with a real colour rather than a hand-picked hex
    that would need re-picking if the constant ever moves.
    """
    target = max(0.0, min(1.0, luminance))
    # Grey ⇒ all three channels equal ⇒ L is the channel's linear value.
    linear = target
    srgb = linear * 12.92 if linear <= 0.0031308 else 1.055 * (linear ** (1 / 2.4)) - 0.055
    level = max(0, min(255, round(srgb * 255)))
    return f"#{level:02X}{level:02X}{level:02X}"


# ── the whole mark, in the shape every surface reads ───────────────────────
def brand_mark(
    *,
    dba_name: str | None,
    legal_name: str | None,
    fallback_name: str = "",
    brand_primary_hex: str | None,
) -> dict[str, Any]:
    """The mark as one dict: letters, its background, its ink, and the ratio.

    `contrast_ratio` rides along deliberately. It is the figure the decision
    above rests on, so a screen or a reviewer can SEE it rather than trust the
    docstring — hard-won law 1, applied to our own reasoning.
    """
    background = brand_primary_hex if parse_hex(brand_primary_hex) else None
    ink = readable_ink(background)
    ratio = contrast_ratio(ink, background) if ink else None
    return {
        "letters": mark_letters(dba_name, legal_name, fallback=fallback_name),
        "background_hex": background,
        "ink_hex": ink,
        "contrast_ratio": round(ratio, 2) if ratio is not None else None,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-048 wave D · CR-007 PO ruling 2026-08-16 · OQ-257 · OQ-800(a)
# generated: 2026-08-30 by the CR-048 wave-D lane
# checklist: A✔ B✔ C✔ D=deferred(pure law — the endpoint half is api.py) E✔ F✔ G✔ H=deferred(PO)
# exceptions: BR-TEN-019's "rasterized for PDF/print" is STILL NOT BUILT — this module states the mark, it does not draw one at print resolution (OQ-257's remaining half) · no platform default colour is invented: no `brand_primary_hex` ⇒ `background_hex`/`ink_hex` are null and the caller falls back to a token it already owns (B8 forbids a hex literal, and putting one in the database instead would be worse) · `parse_hex` is permissive (returns None) because a mark is decoration; the strict `#RRGGBB` validation stays on the WRITE path in services.save_company_profile
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
