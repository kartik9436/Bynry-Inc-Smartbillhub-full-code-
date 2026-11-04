# ── Trace ──────────────────────────────────────────────
# Change:   CR-199-BRC10 · lane TPL-SRV-EMAIL · tasks S4 (rich email wording),
#           S7 (link placeholders) and T2 (nothing unsafe reaches an email)
# Rulings:  PO 2026-10-29 — 2A (a simple rich editor: bold, link, button,
#           list, with a SAFE preview) · A2 A (placeholders only from the
#           allowed list; an unknown one blocks saving)
# Rules:    BR-NOT-012 (every value is escaped on render) · BR-BIL-026 (the
#           body a version holds is what it renders, forever)
# Tests:    06-backend/tests/test_cr199_rich_email.py
# ───────────────────────────────────────────────────────
"""The ONE markup an email body is written in, and the only HTML it can become.

╔══════════════════════════════════════════════════════════════════════════╗
║  A CLERK NEVER WRITES HTML. THE HTML IN AN EMAIL IS BUILT HERE, FROM A    ║
║  CLOSED SET OF FIVE THINGS, AND EVERY CHARACTER OF TEXT IS ESCAPED.       ║
╚══════════════════════════════════════════════════════════════════════════╝

The stored form is a small text markup — the one the editor's four buttons
write (decision log 2026-10-29, *"Rich email wording is stored as a closed
text markup"*):

    **bold**                    bold text
    [label](target)             a link
    [[label|target]]            a button
    - item                      a bulleted list line
    a blank line                a new paragraph; a single newline is a line break

and nothing else. Anything that is not one of those is TEXT and is escaped.
A `target` is either an `https://` address or exactly one LINK placeholder
(`{pay_link}`, `{bill_link}`, `{portal_link}`, any `{…_link}` in the class's
palette — `catalogs.is_link_token`). There is no attribute, no style, no image,
no colour and no way to write one.

**Why a markup and not stored HTML or a JSON tree.** It is diff-able in the
history screen as wording, it survives the plain-text part unchanged for a body
with no markup in it (every body written before this file existed renders its
text part byte-identical), and a parser that recognises five shapes and escapes
the rest cannot be talked into emitting a sixth. A sanitiser over stored HTML
is an allow-list that has to be right about every tag a browser knows.

**Raw HTML is refused at save and REMOVED at render.** A `<tag …>` in a body is
a save-time refusal (`raw_html_not_allowed`); a stored body that somehow holds
one (written before this check, or through a path that skipped it) has the
tag-shaped run removed before it is parsed, so `<script>` or
`<img onerror=…>` never reaches an email even as escaped text.

**Values are substituted INSIDE the parsed structure, never before parsing.**
A customer whose name is `[[Click|https://evil.example]]` is a name, printed as
those characters; substituting first and parsing after would turn customer data
into a button. That ordering is the whole of T2 for values.
"""

from __future__ import annotations

import html as _html
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from apps.notifications import catalogs

#: `{token}` — the renderer's own grammar (`rendering.TOKEN_RE`), restated to
#: avoid an import cycle; a test asserts the two patterns are the same string.
TOKEN_PATTERN = r"\{([A-Za-z0-9_]+)\}"
_TOKEN_RE = re.compile(TOKEN_PATTERN)
_TOKEN_ONLY = re.compile(r"^\{([A-Za-z0-9_]+)\}$")

#: A run that looks like an HTML tag: `<script>`, `</p>`, `<!-- x`, `<img …>`.
#: Bounded to one line so a stray `<` cannot swallow the rest of a body. A `<`
#: followed by a digit or a space (`3 < 5`) is text and is left alone.
_RAW_TAG = re.compile(r"<\s*[/!?]?\s*[A-Za-z][^<>\n]*>?")

#: The three inline shapes, tried left to right at each position.
_INLINE = re.compile(
    r"\[\[(?P<blabel>[^\[\]|\n]+)\|(?P<btarget>[^\[\]\n]+)\]\]"
    r"|\[(?P<llabel>[^\[\]\n]+)\]\((?P<ltarget>[^()\s]+)\)"
    r"|\*\*(?P<bold>[^*\n]+?)\*\*"
)

#: A bulleted list line: a dash, then at least one space or tab.
_LIST_LINE = re.compile(r"^(?P<prefix>[ \t]*-[ \t]+)(?P<rest>.*)$")
_BLANK = re.compile(r"^[ \t]*$")

#: Characters no link address may hold — a quote or bracket would end an
#: attribute, a space would end a URL, a backslash is a parser trick.
_URL_FORBIDDEN = frozenset(" \t\r\n\"'<>`\\")

# ── Findings: codes and the message_key the screen draws ────────────────────
ERR_RAW_HTML = "raw_html_not_allowed"
ERR_LINK_TARGET = "link_target_not_allowed"
ERR_UNKNOWN_PLACEHOLDER = "placeholder_unknown"
WARN_LINK_AS_TEXT = "link_placeholder_as_text"

MESSAGE_KEYS = {
    ERR_RAW_HTML: "notifications.templates.htmlNotAllowed",
    ERR_LINK_TARGET: "notifications.templates.linkTargetNotAllowed",
    ERR_UNKNOWN_PLACEHOLDER: "notifications.templates.placeholderUnknown",
    WARN_LINK_AS_TEXT: "notifications.templates.linkAsText",
}


def finding(code: str, **params: str) -> dict[str, object]:
    """One error or warning as the API serves it: a code, the catalogue key the
    screen renders, and the params that key interpolates (`token`, `target`).
    A token also travels as `placeholder` — `{bogus}`, braces included — which
    is how the catalogue sentence prints it (image 17)."""
    values = dict(params)
    if "token" in values:
        values["placeholder"] = "{" + values["token"] + "}"
    return {"code": code, "message_key": MESSAGE_KEYS[code], "params": values}


def has_raw_html(text: str) -> bool:
    return bool(_RAW_TAG.search(text or ""))


def strip_raw_html(text: str) -> str:
    """Remove every tag-shaped run. The render-time half of the raw-HTML rule."""
    return _RAW_TAG.sub("", text or "")


def safe_https(value: object) -> bool:
    """An address a clerk may TYPE: `https://<host>…`, nothing else."""
    if not isinstance(value, str) or not value or any(ch in _URL_FORBIDDEN for ch in value):
        return False
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return (
        parts.scheme == "https"
        and bool(parts.hostname)
        and parts.username is None
        and parts.password is None
    )


def safe_resolved_link(value: object) -> bool:
    """An address a LINK PLACEHOLDER resolved to. Ours, built from
    `PUBLIC_APP_ORIGIN` (`core.public_origin`), which admits `http` on a
    developer's machine — so `http` is accepted here and ONLY here. A clerk can
    never type one: a typed target must pass `safe_https`."""
    if not isinstance(value, str) or not value or any(ch in _URL_FORBIDDEN for ch in value):
        return False
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return parts.scheme in ("https", "http") and bool(parts.hostname) and parts.username is None


# ── Parse ───────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Inline:
    """One inline piece. `kind` is `text` | `bold` | `link` | `button`."""

    kind: str
    text: str
    target: str | None = None


@dataclass(frozen=True)
class Line:
    """One source line: a list item (with its exact prefix) or an ordinary one."""

    pieces: tuple[Inline, ...]
    list_prefix: str | None = None
    blank: bool = False


def parse_inline(text: str) -> tuple[Inline, ...]:
    pieces: list[Inline] = []
    position = 0
    for match in _INLINE.finditer(text):
        if match.start() > position:
            pieces.append(Inline("text", text[position : match.start()]))
        if match.group("blabel") is not None:
            pieces.append(Inline("button", match.group("blabel"), match.group("btarget").strip()))
        elif match.group("llabel") is not None:
            pieces.append(Inline("link", match.group("llabel"), match.group("ltarget")))
        else:
            pieces.append(Inline("bold", match.group("bold")))
        position = match.end()
    if position < len(text):
        pieces.append(Inline("text", text[position:]))
    return tuple(pieces)


def parse(body: str) -> tuple[Line, ...]:
    """The body as lines of inline pieces. Raw HTML is removed FIRST."""
    clean = strip_raw_html((body or "").replace("\r\n", "\n").replace("\r", "\n"))
    lines: list[Line] = []
    for raw in clean.split("\n"):
        if _BLANK.match(raw):
            lines.append(Line(pieces=parse_inline(raw), blank=True))
            continue
        listed = _LIST_LINE.match(raw)
        if listed:
            lines.append(
                Line(pieces=parse_inline(listed.group("rest")), list_prefix=listed.group("prefix"))
            )
        else:
            lines.append(Line(pieces=parse_inline(raw)))
    return tuple(lines)


# ── Check (save + preview) ──────────────────────────────────────────────────
@dataclass
class Findings:
    errors: list[dict[str, object]] = field(default_factory=list)
    warnings: list[dict[str, object]] = field(default_factory=list)

    def error_once(self, code: str, **params: str) -> None:
        entry = finding(code, **params)
        if entry not in self.errors:
            self.errors.append(entry)

    def warn_once(self, code: str, **params: str) -> None:
        entry = finding(code, **params)
        if entry not in self.warnings:
            self.warnings.append(entry)


def target_ok(target: str, palette: frozenset[str]) -> bool:
    token = _TOKEN_ONLY.match(target)
    if token:
        return token.group(1) in palette and catalogs.is_link_token(token.group(1))
    return safe_https(target)


def check(body: str, *, palette: frozenset[str], rich: bool) -> Findings:
    """Everything wrong with an EMAIL body, as data — never a raise.

    Errors block a save: raw HTML, a link or button pointing anywhere but
    `https://` or a link placeholder, a placeholder outside the palette (A2 A).
    The one warning — a link placeholder written as bare text in a RICH body —
    does not: the plain-text part prints the full address either way, and the
    drawing (image 17) shows it as a nudge, *"Make it a button or link."*
    """
    found = Findings()
    if has_raw_html(body):
        found.error_once(ERR_RAW_HTML)
    for line in parse(body):
        for piece in line.pieces:
            if piece.kind in ("link", "button"):
                assert piece.target is not None
                if not target_ok(piece.target, palette):
                    found.error_once(ERR_LINK_TARGET, target=piece.target)
            for name in _TOKEN_RE.findall(piece.text):
                if name not in palette:
                    found.error_once(ERR_UNKNOWN_PLACEHOLDER, token=name)
                elif rich and catalogs.is_link_token(name):
                    found.warn_once(WARN_LINK_AS_TEXT, token=name)
            if piece.target is not None:
                for name in _TOKEN_RE.findall(piece.target):
                    if name not in palette:
                        found.error_once(ERR_UNKNOWN_PLACEHOLDER, token=name)
    return found


# ── Render ──────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Rendered:
    text: str
    #: The email's BODY HTML (no document wrapper — `email_layout` adds the shell).
    html: str


#: Presentation for the four rich shapes. Inline styles only: mail clients strip
#: `<style>` and never load a stylesheet. Colours arrive from the utility's
#: brand and are validated hex before they get here (`email_layout`).
_P = '<p style="margin:0 0 16px 0;">{}</p>'
_UL = '<ul style="margin:0 0 16px 0;padding-left:24px;">{}</ul>'
_LI = '<li style="margin:0 0 4px 0;">{}</li>'
_A = '<a href="{href}" style="color:{link};text-decoration:underline;">{label}</a>'
_BUTTON = (
    '<a href="{href}" style="display:inline-block;background-color:{bg};color:{ink};'
    "padding:12px 20px;border-radius:4px;font-weight:600;text-decoration:none;"
    '">{label}</a>'
)


def render(
    body: str,
    *,
    resolve_text: Callable[[str], str],
    resolve_link: Callable[[str], str | None],
    rich: bool,
    brand_hex: str,
    ink_hex: str,
) -> Rendered:
    """Text + body HTML from ONE walk, so each value is resolved exactly once.

    `resolve_text(segment)` substitutes every `{token}` in a piece of wording
    and returns RAW text (escaping is this function's job, never the caller's).
    `resolve_link(target)` returns the address a target points at, or None
    when there is none to point at — an absent value, or one that is not a
    safe address. A link with no address prints its label alone.
    """
    resolved: list[tuple[Line, list[tuple[Inline, str, str | None]]]] = []
    for line in parse(body):
        pieces: list[tuple[Inline, str, str | None]] = []
        for piece in line.pieces:
            label = resolve_text(piece.text)
            href = resolve_link(piece.target) if piece.target is not None else None
            pieces.append((piece, label, href))
        resolved.append((line, pieces))

    # TEXT — line for line, so a body with no markup is byte-identical.
    text_lines: list[str] = []
    for line, pieces in resolved:
        words = "".join(_plain_piece(piece, label, href) for piece, label, href in pieces)
        text_lines.append((line.list_prefix or "") + words)
    text = "\n".join(text_lines)

    if not rich:
        return Rendered(text=text, html=plain_html(text))

    # HTML — blocks by blank lines; list runs become <ul>, the rest <p>.
    blocks: list[str] = []
    paragraph: list[str] = []
    items: list[str] = []

    def flush() -> None:
        if paragraph:
            blocks.append(_P.format("<br/>".join(paragraph)))
            paragraph.clear()
        if items:
            blocks.append(_UL.format("".join(_LI.format(item) for item in items)))
            items.clear()

    for line, pieces in resolved:
        if line.blank:
            flush()
            continue
        html_line = "".join(
            _html_piece(piece, label, href, brand_hex=brand_hex, ink_hex=ink_hex)
            for piece, label, href in pieces
        )
        if line.list_prefix is not None:
            if paragraph:
                blocks.append(_P.format("<br/>".join(paragraph)))
                paragraph.clear()
            items.append(html_line)
        else:
            if items:
                blocks.append(_UL.format("".join(_LI.format(item) for item in items)))
                items.clear()
            paragraph.append(html_line)
    flush()
    return Rendered(text=text, html="".join(blocks))


def _plain_piece(piece: Inline, label: str, href: str | None) -> str:
    if piece.kind in ("link", "button"):
        if href is None or href == label:
            return label if href is None else href
        return f"{label}: {href}"
    return label


def _html_piece(
    piece: Inline, label: str, href: str | None, *, brand_hex: str, ink_hex: str
) -> str:
    escaped = _html.escape(label, quote=True)
    if piece.kind == "bold":
        return f"<strong>{escaped}</strong>"
    if piece.kind == "link" and href is not None:
        return _A.format(href=_html.escape(href, quote=True), link=brand_hex, label=escaped)
    if piece.kind == "button" and href is not None:
        return _BUTTON.format(
            href=_html.escape(href, quote=True), bg=brand_hex, ink=ink_hex, label=escaped
        )
    return escaped


def plain_html(text: str) -> str:
    """A PLAIN email's HTML body: the text part, escaped, a paragraph per
    blank-line block and a `<br/>` per line — no links, no formatting."""
    blocks = [block.strip("\n") for block in re.split(r"\n[ \t]*\n+", text)]
    return "".join(
        _P.format("<br/>".join(_html.escape(line, quote=True) for line in block.split("\n")))
        for block in blocks
        if block.strip()
    )


def plain_source(body: str) -> str:
    """The body with its markup turned into plain wording, tokens kept — what
    the editor's Rich → Plain switch can offer (`label: {pay_link}`)."""
    return render(
        body,
        resolve_text=lambda segment: segment,
        resolve_link=lambda target: target,
        rich=False,
        brand_hex="#000000",
        ink_hex="#FFFFFF",
    ).text
