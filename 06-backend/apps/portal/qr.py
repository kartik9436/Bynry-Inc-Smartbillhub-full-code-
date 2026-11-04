# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-069 (EP-CWP-12) TC-1 — the address, copyable, WITH a QR code
#           a utility can print on its bills. Screens: CWP-069
# Rules:    US-CWP-069 §1 (*"a QR code for your bills"*) · B14 rule 4 (`↓` is a
#           download)
# Tests:    06-backend/tests/test_us_cwp_069_settings.py TC-1
# Impacts:  backoffice_api.portal_qr · pyproject.toml (`segno`)
# ───────────────────────────────────────────────────────
"""One QR code, as SVG, for the portal address.

`segno` (BSD, pure Python, no dependency) does the encoding; this module only
fixes the two choices — error level M, the level a print shop expects for a
short URL on paper, and SVG, so the bill template can scale it without
pixels. The text encoded is the FULL address a customer would type; the QR is
not a second copy of the slug, it is derived from it on every request.

⚠ **IT IS `save(kind="svg")` AND NOT `svg_inline()`, AND THAT IS THE WHOLE OF
`DEF-CWP-3720`.** `svg_inline()` is built for pasting INTO an HTML document,
where the surrounding HTML parser supplies the SVG namespace — so it
deliberately emits no XML declaration and, crucially, **no `xmlns`**. Served
as its own `image/svg+xml` document and loaded through `<img src>`, the
browser parses it as XML, finds an `<svg>` element in no namespace, and draws
nothing: the Settings screen showed a broken-image icon and its alt text from
the day this shipped.

**Every check in the repo passed on it**, and the reason is worth keeping: the
backend test asserted a 200, the content type, and that the body carried the
address — all three true of a body that cannot be drawn. Nothing loads an
image. So the test now asserts the ONE byte string that decides whether the
picture appears, and it is named here so nobody "simplifies" this back.

⚠ **AND THE DOCUMENT IS ASSEMBLED HERE RATHER THAN BY `code.save(kind="svg")`,
WHICH IS THE OBVIOUS CALL AND IS THE WRONG ONE IN THIS PACKAGE.** `G81` refuses
any `.save(` under `apps/portal/` — the guest surface writes in four places
only, and the gate cannot tell a QR encoder's stream writer from a Django row
being written. That is the gate working: its rule is worth more than the two
lines it costs here, and widening a boundary check to fit a picture would be
the wrong trade. The two things a standalone SVG document has that an inline
element does not are an XML declaration and a namespace, both are constants
below, and assembling them explicitly says out loud what this defect was —
which `save(kind="svg")` would have hidden behind a keyword argument.
"""

from __future__ import annotations

import segno

#: The namespace an `<svg>` must carry to be an SVG at all when it is its own
#: document. Asserted by `test_us_cwp_069_settings.py`, not merely produced.
SVG_NAMESPACE = "http://www.w3.org/2000/svg"

#: What `segno` emits for an element meant to be pasted into HTML.
_INLINE_OPEN = "<svg "
#: The two things a standalone SVG DOCUMENT has that an inline element does not.
_DECLARATION = '<?xml version="1.0" encoding="utf-8"?>\n'
_DOCUMENT_OPEN = f'<svg xmlns="{SVG_NAMESPACE}" '


def portal_qr_svg(url: str, *, scale: int = 6) -> str:
    """The standalone SVG document for `url`, ready to stream as `image/svg+xml`."""
    code = segno.make(url, error="m")
    element = code.svg_inline(scale=scale, border=2, dark="#111111")
    if not element.startswith(_INLINE_OPEN):
        # ⚠ LOUD, NOT SILENT, AND THAT IS THE LESSON OF THIS DEFECT. The bug
        # being fixed here produced a perfectly well-formed body that no
        # browser could draw, and every check passed on it. If a future
        # `segno` changes what it emits, this must fail where a person can see
        # it rather than serve another undrawable picture.
        raise RuntimeError(f"segno emitted markup this module cannot make standalone: {element[:60]!r}")
    return _DECLARATION + element.replace(_INLINE_OPEN, _DOCUMENT_OPEN, 1)
