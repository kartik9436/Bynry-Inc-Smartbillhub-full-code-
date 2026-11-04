# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-005 (S8 Company profile → Brand; TC-5 "upload 4.8 MB PNG,
#           then an .svg containing <script>" — neither is stored)
#           Screens: S8
# Rules:    BR-TEN-019 (SUPERSEDED 2026-10-27, DEF-TEN-10618: PNG or JPG ≤ 2 MB, SVG refused; brand
#           colors valid #RRGGBB — the color half lives in services) ·
#           BR-TEN-016 (the upload writes an audit row — services) ·
#           BR-TEN-017 (documents stamp the logo at issue time; re-uploading
#           never re-renders an issued document)
# Tests:    06-backend/tests/test_us_ten_005_006_settings.py (TC-5 + the
#           allowlist / cap / sanitizer cases)
# Impacts:  apps/tenancy/{services,api}.py · every document renderer that draws
#           the letterhead (W6 templates lane) — it consumes the STORED bytes
# ───────────────────────────────────────────────────────
"""Logo upload law: the allowlist, the size cap, and the content check.

⚠ **PNG OR JPG ONLY SINCE 2026-10-27 — BR-TEN-019 SUPERSEDED (`DEF-TEN-10618`).**
PO, verbatim, answering the VAPT stored-XSS finding: *"Allow PNG, JPG"*
(decision log *"VAPT round: five findings ruled"* (1)). An SVG is refused here
by type AND by name (`settings.company.logo_svg_not_accepted`, 415 at the API —
*"SVG files aren't accepted. Use PNG or JPG."*), and a file whose BYTES are not
what its type says — an SVG renamed `.png` or `.jpg` — is refused on its magic
bytes (`settings.company.logo_content_mismatch`). A JPG is stored as uploaded
and gets a PNG copy for print (`print_png`), exactly as a stored SVG has one.

**THE SANITISER BELOW IS KEPT, AND ONLY FOR LOGOS ALREADY STORED.** Utilities
that uploaded an SVG before the ruling keep it: their row and stored documents
are not deleted, `move_logos_to_store` still moves a row-held one (and needs
`clean_legacy_svg` + `raster_png` to do so), and every screen is now served
the PNG copy rather than the SVG itself (`selectors.logo_bytes`). No upload
path reaches `_sanitize_svg` any more. The history below is what it was.

Pure functions — no ORM, no request objects. The writer (services) stores what
`sanitized_logo()` returns; the API layer maps the two TRANSPORT refusals
(415 unsupported type, 413 over cap — B12 r1's HTTP-series rows, which have no
B12 §3 catalog code) and re-checks nothing the law here does not already check.

WHY A HAND-WRITTEN SANITIZER: BR-TEN-019 says "SVG is sanitized server-side".
An SVG is XML that browsers execute — `<script>`, `on*` handlers, `<a
href=javascript:>`, external `<image href=…>` and `<use href=…>` all run or
phone home in a bill preview. The sanitizer is a strict ALLOWLIST (elements,
then attributes, then attribute VALUES): anything not named below is dropped,
so a payload nobody thought of is dropped by default rather than by blacklist.
No new dependency — stdlib `xml.etree.ElementTree` only.

Two deliberate refusals rather than strips:
- a DOCTYPE or ENTITY declaration → refused outright. Entity expansion is the
  billion-laughs / XXE surface; a logo has no legitimate need for a DTD, so
  refusing is safer than trusting a parser's expansion limits.
- content that does not match its declared type (a .docx renamed .png) →
  refused on the magic bytes, not stored.

RASTERISED FOR PRINT — BUILT 2026-10-05 (`CR-172-BRC10`).
BR-TEN-019's second clause, *"rasterized for PDF/print"*, read here as
*"REPORTED, NOT BUILT … needs a rendering dependency (cairosvg/resvg) and a
build decision no lane has taken"* from 2026-08-09. The decision is taken:
`raster_png()` below renders the CLEANED SVG with `resvg-py` (a self-contained
renderer — no system library, no network, no script engine) ONCE, at upload,
and the PNG is stored beside the SVG as a second representation of the same
logo (`apps.tenancy.services._store_logo`). Screens draw the SVG; printed
documents draw the PNG. It renders only what `_sanitize_svg` has already
cleaned, so the allowlist below is still the whole of what reaches a renderer.

⚠ REPORTED, NOT BUILT (named so nobody assumes it exists):
1. PNG bytes are verified by signature only; there is no image re-encode.
   ⚠ **AND THERE IS NO VIRUS SCAN, BY PO RULING — NOT A GAP.** This note read
   *"no malware scan — BR-SHL-031's scanner seam does not exist yet"* from
   2026-08-11; `BR-SHL-253` then scanned every multipart upload on the wire
   from 2026-09-13; and the PO removed the scan on 2026-09-22 and 2026-09-23
   (*"please remove virus scan chek user don't wan't it"*, `DEF-SHL-6347`).
   The magic-byte check above is the content check this endpoint makes, and
   it is not a scan. A comment claiming a guarantee is not the guarantee
   (hard-won law 1) — and neither is one describing a guarantee that was
   removed.
"""

import hashlib
import re
import xml.etree.ElementTree as ET
from typing import Any

from core import errors

# BR-TEN-019 / B12 r1: the whole allowlist and the whole cap, in two constants.
LOGO_MAX_BYTES = 2 * 1024 * 1024  # "max 2MB" (prototype S8 drop-zone copy)
SVG_CONTENT_TYPE = "image/svg+xml"  # REFUSED on upload since 2026-10-27; legacy reads only
PNG_CONTENT_TYPE = "image/png"
JPEG_CONTENT_TYPE = "image/jpeg"
#: `DEF-TEN-10618` (PO 2026-10-27, *"Allow PNG, JPG"*) — the WHOLE allowlist.
LOGO_CONTENT_TYPES: dict[str, tuple[str, ...]] = {
    PNG_CONTENT_TYPE: (".png",),
    JPEG_CONTENT_TYPE: (".jpg", ".jpeg"),
}
#: A non-standard spelling some browsers and scanners send for a JPEG.
_MEDIA_ALIASES = {"image/jpg": JPEG_CONTENT_TYPE, "image/pjpeg": JPEG_CONTENT_TYPE}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
#: The magic bytes each allowed type must START with — the content check.
SIGNATURES = {PNG_CONTENT_TYPE: PNG_SIGNATURE, JPEG_CONTENT_TYPE: JPEG_SIGNATURE}
SVG_NOT_ACCEPTED_KEY = "settings.company.logo_svg_not_accepted"

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
XML_NS = "http://www.w3.org/XML/1998/namespace"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

# Structure + geometry + paint only. Absent on purpose: script, style, a,
# image, foreignObject, iframe/embed/object, every animate*/set element, and
# handler — each is either executable or an external fetch.
ALLOWED_ELEMENTS = frozenset(
    {
        "svg",
        "g",
        "defs",
        "title",
        "desc",
        "path",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "text",
        "tspan",
        "use",
        "symbol",
        "marker",
        "clippath",
        "mask",
        "pattern",
        "lineargradient",
        "radialgradient",
        "stop",
    }
)
ALLOWED_ATTRIBUTES = frozenset(
    {
        "id",
        "class",
        "style",
        "d",
        "fill",
        "fill-opacity",
        "fill-rule",
        "stroke",
        "stroke-width",
        "stroke-opacity",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-dasharray",
        "stroke-dashoffset",
        "stroke-miterlimit",
        "opacity",
        "transform",
        "x",
        "y",
        "dx",
        "dy",
        "x1",
        "y1",
        "x2",
        "y2",
        "cx",
        "cy",
        "r",
        "rx",
        "ry",
        "width",
        "height",
        "points",
        "viewbox",
        "version",
        "preserveaspectratio",
        "offset",
        "stop-color",
        "stop-opacity",
        "gradientunits",
        "gradienttransform",
        "spreadmethod",
        "patternunits",
        "patterntransform",
        "clip-path",
        "clip-rule",
        "mask",
        "marker-end",
        "marker-mid",
        "marker-start",
        "markerwidth",
        "markerheight",
        "refx",
        "refy",
        "orient",
        "font-family",
        "font-size",
        "font-style",
        "font-weight",
        "text-anchor",
        "letter-spacing",
        "dominant-baseline",
        "space",  # xml:space
    }
)
# href/xlink:href survive ONLY as an in-document fragment (`<use href="#id">`).
REFERENCE_ATTRIBUTES = frozenset({"href"})
# Value-level scrub for the attributes that can smuggle a URL (style, fill,
# stroke, clip-path, mask, marker-*: `fill="url(http://evil/x)"` is a fetch).
_URLISH_RE = re.compile(r"url\s*\(|javascript\s*:|expression\s*\(|@import|data\s*:", re.IGNORECASE)
_LOCAL_URL_RE = re.compile(r"^url\(\s*['\"]?#[^)]*\)$", re.IGNORECASE)
_DTD_RE = re.compile(r"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)


def _local_name(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""  # comments / processing instructions carry a callable tag
    return tag.rsplit("}", 1)[-1].lower()


def _namespace(tag: Any) -> str:
    if isinstance(tag, str) and tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return ""


def _refuse(message_key: str, **params: Any) -> None:
    raise errors.ValidationError(
        errors.VAL_FORMAT,
        message_key=message_key,
        params=params,
        field_errors=[
            {
                "field": "file",
                "code": errors.VAL_FORMAT,
                "message_key": message_key,
                "params": {**params, "br": "BR-TEN-019"},
            }
        ],
    )


def _suffix(filename: str | None) -> str:
    if filename and "." in filename:
        return "." + filename.rsplit(".", 1)[-1].strip().lower()
    return ""


def is_svg(declared: str | None, filename: str | None) -> bool:
    """`DEF-TEN-10618` — True when the upload SAYS it is an SVG, by its declared
    type or by its name. Asked first, so an SVG gets its own sentence (*"SVG
    files aren't accepted. Use PNG or JPG."*) rather than the generic one; an
    SVG that says it is something else is caught on its bytes instead."""
    media = (declared or "").split(";", 1)[0].strip().lower()
    return media == SVG_CONTENT_TYPE or _suffix(filename) in (".svg", ".svgz")


def refuse_svg() -> None:
    """The ONE refusal an SVG upload gets (`DEF-TEN-10618`)."""
    _refuse(SVG_NOT_ACCEPTED_KEY, allowed=sorted(LOGO_CONTENT_TYPES))


def normalized_content_type(declared: str | None, filename: str | None) -> str | None:
    """The allowlisted type for this upload, or None → the caller answers 415.

    A declared type must be on the allowlist AND agree with the file extension
    when one is present; a missing/generic declared type falls back to the
    extension. Disagreement is a refusal, not a preference: `report.docx` sent
    as `image/png` is exactly the case BR-TEN-019's allowlist exists for.
    """
    media = (declared or "").split(";", 1)[0].strip().lower()
    media = _MEDIA_ALIASES.get(media, media)
    suffix = _suffix(filename)
    if media in LOGO_CONTENT_TYPES:
        if suffix and suffix not in LOGO_CONTENT_TYPES[media]:
            return None
        return media
    if media in ("", "application/octet-stream"):
        for content_type, suffixes in LOGO_CONTENT_TYPES.items():
            if suffix in suffixes:
                return content_type
    return None


def sanitized_logo(content: bytes, content_type: str) -> tuple[bytes, str, str]:
    """(stored bytes, content type, `sha256:<hex>` reference) or a refusal.

    PNG and JPG pass through after a magic-byte check (`SIGNATURES`) — the
    content check that refuses an SVG or an HTML page renamed `.png`/`.jpg`.
    An SVG is refused outright (`DEF-TEN-10618`). Re-checked against the cap
    here so a job or shell caller cannot bypass the API's 413.
    """
    if content_type == SVG_CONTENT_TYPE:
        refuse_svg()
    if content_type not in LOGO_CONTENT_TYPES:
        _refuse("settings.company.logo_type_not_allowed", allowed=sorted(LOGO_CONTENT_TYPES))
    if len(content) > LOGO_MAX_BYTES:
        _refuse("settings.company.logo_too_large", max_bytes=LOGO_MAX_BYTES, size=len(content))
    if not content:
        _refuse("settings.company.logo_empty")
    if not content.startswith(SIGNATURES[content_type]):
        # Declared PNG/JPG, not one — a renamed SVG, HTML page or .docx.
        _refuse("settings.company.logo_content_mismatch", declared=content_type)
    stored = content

    digest = hashlib.sha256(stored).hexdigest()
    return stored, content_type, f"sha256:{digest}"


#: The longer side of the PNG a logo is printed from, in pixels. A letterhead
#: logo is drawn about 1.5 inches wide; 600px is ~400 dpi there, which is print
#: quality, and a 600px PNG of a logo is a few kilobytes.
RASTER_LONG_SIDE = 600


def clean_legacy_svg(content: bytes) -> bytes:
    """The allowlist sanitiser, for an SVG logo ALREADY STORED before
    2026-10-27 (`DEF-TEN-10618`). No upload reaches it."""
    return _sanitize_svg(content)


def print_png(stored: bytes, content_type: str) -> bytes | None:
    """The PNG a printed document draws for this logo, or None when the logo
    already IS a PNG. A JPG is re-encoded with Pillow (`DEF-TEN-10618`: a JPG
    logo must print, and the bill renderer stamps a PNG); a stored SVG is
    rendered by `raster_png`."""
    if content_type == SVG_CONTENT_TYPE:
        return raster_png(stored)
    if content_type == JPEG_CONTENT_TYPE:
        import io

        from PIL import Image

        try:
            with Image.open(io.BytesIO(stored)) as opened:
                opened.load()
                picture = opened.convert("RGBA" if "A" in opened.getbands() else "RGB")
        except Exception as exc:  # noqa: BLE001 — Pillow raises several types for a bad file
            _refuse("settings.company.logo_content_mismatch", declared=content_type, reason=str(exc)[:120])
        out = io.BytesIO()
        picture.save(out, format="PNG", optimize=True)
        return out.getvalue()
    return None


def raster_png(svg: bytes) -> bytes:
    """BR-TEN-019 — the PNG a document prints, from an ALREADY-CLEANED SVG.

    Only `sanitized_logo()`'s output may be handed here: the cleaning is what
    makes it safe to render, and this function re-checks nothing. Rendered at
    its own aspect ratio with the longer side `RASTER_LONG_SIDE` pixels.
    """
    import resvg_py  # imported here so a screen-only read never loads the renderer

    try:
        text = svg.decode("utf-8")
        first = bytes(resvg_py.svg_to_bytes(svg_string=text))
        width, height = _png_size(first)
        zoom = RASTER_LONG_SIDE / max(width, height, 1)
        png = bytes(resvg_py.svg_to_bytes(svg_string=text, zoom=zoom)) if zoom > 1 else first
    except (ValueError, UnicodeDecodeError) as exc:
        _refuse("settings.company.logo_svg_malformed", reason=str(exc)[:120])
    if not png.startswith(PNG_SIGNATURE):
        _refuse("settings.company.logo_svg_malformed", reason="render produced no image")
    return png


def _png_size(png: bytes) -> tuple[int, int]:
    """Width and height from a PNG's IHDR chunk — no decoder needed."""
    if len(png) < 24 or not png.startswith(PNG_SIGNATURE):
        return 0, 0
    return int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")


def _sanitize_svg(content: bytes) -> bytes:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        _refuse("settings.company.logo_content_mismatch", declared=SVG_CONTENT_TYPE)
    if _DTD_RE.search(text):
        # No DTDs: entity expansion is the XXE / billion-laughs surface.
        _refuse("settings.company.logo_svg_dtd_forbidden")
    try:
        root = ET.fromstring(text)  # noqa: S314 - DTDs refused above; allowlist below
    except ET.ParseError as exc:
        _refuse("settings.company.logo_svg_malformed", reason=str(exc.msg))
    if _local_name(root.tag) != "svg" or _namespace(root.tag) not in ("", SVG_NS):
        _refuse("settings.company.logo_content_mismatch", declared=SVG_CONTENT_TYPE)

    _scrub_element(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=False)


def _scrub_element(element: ET.Element) -> None:
    """Depth-first allowlist pass: drop disallowed children whole (a dropped
    `<script>` takes its payload with it), then scrub the survivors."""
    for child in list(element):
        namespace, name = _namespace(child.tag), _local_name(child.tag)
        if name not in ALLOWED_ELEMENTS or namespace not in ("", SVG_NS):
            element.remove(child)
            continue
        _scrub_element(child)
    _scrub_attributes(element)


def _scrub_attributes(element: ET.Element) -> None:
    for key in list(element.attrib):
        namespace, name = _namespace(key), _local_name(key)
        value = element.attrib[key]
        if name.startswith("on"):  # every event handler, whatever it is called
            del element.attrib[key]
            continue
        if name in REFERENCE_ATTRIBUTES:
            if namespace in ("", SVG_NS, XLINK_NS) and value.strip().startswith("#"):
                continue  # in-document reference: <use href="#glyph">
            del element.attrib[key]
            continue
        if name not in ALLOWED_ATTRIBUTES or namespace not in ("", SVG_NS, XML_NS):
            del element.attrib[key]
            continue
        if _URLISH_RE.search(value) and not _LOCAL_URL_RE.match(value.strip()):
            # `fill="url(http://…)"`, `style="background:url(data:…)"` — the
            # paint survives only when it points inside this document.
            del element.attrib[key]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-005@0733260 (story+rules snapshot hash — EP-TEN-05 company-settings epic)
# generated: 2026-08-09 by story-coder v1 (tenancy settings rule-page + logo gap lane)
# checklist: A✔ B✔ C✔ D=deferred(pure law — the endpoint half is api.py) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: [gap lane 2026-08-09 FINAL] ruff --select E4,E7,E9,F✔ black✔ · migrate from empty✔ makemigrations --check --dry-run✔ · suite `pytest tests -m "not golden and not isolation"` 682 passed / 7 skipped / 47 deselected (594 was the baseline when this lane started; 62 of the new tests are this lane's, the rest arrived from the concurrent audit-viewer / identity / rating lanes) · `-m isolation` 14 passed / 22 postgres-only skipped · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently)
# exceptions: [CR-172-BRC10 2026-10-05] BR-TEN-019's "rasterized for PDF/print" BUILT — `raster_png()` (resvg-py), run once at upload; it was "NOT built — needs a rendering dependency and a build decision no lane has taken" until then · PNG verified by signature only, no re-encode — and NO VIRUS SCAN, by PO ruling of 2026-09-22/23 (BR-SHL-253 superseded, DEF-SHL-6347), which is not a gap · DTD/ENTITY refused rather than stripped (XXE posture) · no DELETE endpoint: neither US-TEN-005 nor the prototype drop-zone anchors logo removal — not invented, REPORTED
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
