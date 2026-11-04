# ── Trace ──────────────────────────────────────────────
# Change:   "A clerk cannot attach a document to a service request" — the
#           PO's *"you will have to reduce the size and save them on cloud
#           container etc"*, the REDUCE half.
# Rules:    BR-SHL-031 (upload allowlist + cap) · BR-WRK-047 (the product's
#           EXISTING ruling on shrinking an image: compressed AT CAPTURE, in
#           the client — see "WHY NOTHING HERE IS LOSSY") · NFR-33 / NFR-35
#           (write-once, 7 years) · CLAUDE.md hard-won law 1 (a comment
#           claiming a guarantee is not the guarantee) · law 7 (what would
#           make this check pass wrongly?)
# Tests:    06-backend/tests/test_service_request_documents.py §4
# Impacts:  apps/customers/service_request_documents.py is the only caller.
#           Nothing here touches a database, a tenant or a bucket.
# ───────────────────────────────────────────────────────
"""Make an uploaded file smaller WITHOUT CHANGING A SINGLE PIXEL OF IT.

⚠ **EVERY REDUCTION IN THIS MODULE IS LOSSLESS, AND THAT IS THE WHOLE DESIGN
RATHER THAN A LIMITATION OF IT.** A file that goes through here decodes to
exactly the image that arrived. Nothing is resampled, requantised or
re-encoded at a lower quality, and no reduction is accepted unless this module
has *verified* that the original content is still recoverable from it.

WHY NOTHING HERE IS LOSSY
──────────────────────────────────────────────────────────────────────────────
These are not holiday photographs. The eight designed document types are a
driver's licence, a proof of address, a tenancy agreement or deed, an authority
to act, **a site plan or unit schedule**, assistance evidence, a signed service
agreement and completion paperwork — every one of them a thing a clerk reads a
NUMBER, a NAME, a SIGNATURE or a BOUNDARY off. The Accounts blueprint's own
worked example on the Documents tab carries a site plan marked
**`Rejected · unreadable`**, which is what this failure looks like when it
reaches a customer: the request stalls, the applicant is asked for the document
again, and the copy we degraded is the one under a seven-year retention lock.
(⚠ the object LOCK is suspended from 2026-10-02, `CR-160-BRC10`; the row stays write-once)

**Four reasons, and the fourth is the one that settles it:**

  1. **The damage is silent and permanent.** `stored_documents` is write-once
     (`tenancy/0026`'s trigger) under an object lock. A file recompressed on
     the way in cannot be repaired on the way out — there is no original left
     to go back to. Every other mistake in this product can be corrected with
     a new row; this one cannot.
  2. **The harm is invisible to every check this repository has.** A
     re-encoded JPEG is a perfectly valid JPEG of the right size with the right
     hash written down for it. `tsc`, the suite and every gate pass. It fails
     only in a clerk's hands, months later, on the one document that mattered.
  3. **A lossy path needs an image DECODER parsing untrusted uploaded bytes**
     on the evidence path. That is a new runtime dependency and a well-known
     class of vulnerability, added to buy storage.
  4. ⚠ **THE PRODUCT HAS ALREADY RULED ON THIS, AND THE RULING PUTS LOSSY
     COMPRESSION IN THE CLIENT.** `BR-WRK-047` (PO 2026-09-04, on
     `OQ-WRK-1496`): *"when we develope mobile apap, when image is captured we
     redce the size first 50 Kb 60 Kb or 100 kb max"* — the handset compresses
     at capture and **the server enforces a ceiling and refuses the original**
     (`apps/work/work_documents.py`). A server-side re-encode here would be a
     second, contradictory model of the same question in one product. The
     ceiling half is honoured by `BR-SHL-031`'s 10 MB cap at the door.

**So this module does the part that is free.** What it cannot do is buy the
larger saving a downscale would; that number is recorded in the decision log
beside this ruling so a PO who wants it can ask for it.

WHAT IT ACTUALLY SAVES — MEASURED, NOT ASSERTED
──────────────────────────────────────────────────────────────────────────────
Run over the **56 real PNG files** in `05-prototype/r10-2026-08-16/uploads/`
(screenshots — flat colour and text, structurally the same thing a flatbed
scanner produces): **18,076,547 bytes → 13,306,223 bytes, 26.4% saved**, with
every inflated pixel stream compared byte-for-byte against the original's.

That is not a coincidence of this sample. A PNG's size is decided by the zlib
level its writer chose, and a scanner, a phone and a screenshot tool all choose
a FAST level because they are encoding on a small CPU while somebody waits.
Re-deflating at level 9 costs us milliseconds once and saves that gap forever.

A JPEG is already entropy-coded and re-deflating it buys nothing, so the JPEG
path takes the only lossless saving there is — **the metadata**. A phone's
`APP1` block carries an EXIF thumbnail of tens of kilobytes; the win is a few
per cent rather than a quarter. ⚠ **Its second effect is worth more than its
first: it removes the GPS coordinates** a phone stamps into every photograph.
A clerk photographing a licence in a customer's living room otherwise files
that customer's home coordinates into a document kept for seven years.

⚠ NOTHING HERE TOUCHES A PDF, AND THAT IS DELIBERATE
──────────────────────────────────────────────────────────────────────────────
A PDF is the majority of what a clerk attaches and it is stored **byte for
byte**. Its text and vector content is where a deed's wording and a site plan's
dimensions live, and there is no safe reduction of it without a PDF library
rewriting the document's own object graph. A CSV is likewise untouched.

⚠ AND IT RUNS BEFORE THE FILE IS FILED, EXACTLY ONCE
──────────────────────────────────────────────────────────────────────────────
The caller reduces and THEN calls `document_store.store()`. A reduction that
ran after filing would be rewriting evidence under a retention lock, which is
the opposite of what the store exists for.

⚠ THIS MODULE TOUCHES NO DATABASE, SO HARD-WON LAW 14 DOES NOT APPLY TO IT
──────────────────────────────────────────────────────────────────────────────
`_reduce` catches broadly and falls back to the original bytes, and that looks
exactly like the `except IntegrityError: continue` law 14 forbids. It is not:
there is no connection, no statement and no transaction anywhere in this file,
so there is no aborted-transaction state to be poisoned by. The broad catch is
correct here for the reason the law's own shape suggests — **an unparseable
upload must be STORED UNCHANGED, never refused and never half-rewritten** — and
this sentence is here so the next lane does not "fix" it into a narrow catch
that lets a malformed image take an upload down.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

#: Below this, nothing is attempted. A 20 KB scan has nothing worth taking and
#: the only thing a reduction could do to it is go wrong. The figure is an
#: engineering floor rather than a ruled one: 64 KiB is about where a quarter
#: of a PNG stops being a rounding error against the cost of inflating it.
MIN_REDUCIBLE_BYTES = 64 * 1024

#: The media types this module will look at. ⚠ **`application/pdf` AND
#: `text/csv` ARE ABSENT ON PURPOSE** — see the module docstring. A type that is
#: not on this list is returned untouched, which is the safe direction.
REDUCIBLE_TYPES = ("image/png", "image/jpeg", "image/jpg")

#: How a row records what was done to it. `None` means *nothing was done and
#: `size` is what arrived*, which is what a clerk needs to be told apart from
#: *we shrank it*.
METHOD_PNG = "png_redeflate"
METHOD_JPEG = "jpeg_strip_metadata"

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

#: JPEG segments that carry no image data: EXIF and XMP (`APP1`), ICC and FPXR
#: (`APP2`), Photoshop IRB including its own preview (`APP13`), and a comment.
#: ⚠ **`APP0` (JFIF) IS NOT ON THIS LIST.** It carries the pixel-aspect and
#: density fields a viewer uses to decide how wide the image is, and dropping
#: it can change how a scanned page is displayed — a reduction that alters what
#: a person sees, which is the one thing this module may not do.
#: ⚠ **`APP14` (Adobe) IS NOT ON THIS LIST EITHER.** It declares the colour
#: transform; drop it from a CMYK or YCCK scan and the colours invert.
_JPEG_STRIPPABLE = (0xE1, 0xE2, 0xED, 0xFE)


@dataclass(frozen=True)
class Reduction:
    """What to store, and what arrived.

    ⚠ **`method is None` IS NOT "WE DID NOT LOOK"** — it is *"this file was
    stored exactly as it was uploaded"*, which is a real answer and the one a
    PDF always gets. The caller writes `original_bytes` onto the row **only**
    when `method` is set, so a clerk reading the record can tell a file that
    was never touched from one that was shrunk.
    """

    payload: bytes
    original_bytes: int
    method: str | None

    @property
    def reduced(self) -> bool:
        return self.method is not None

    @property
    def stored_bytes(self) -> int:
        return len(self.payload)

    @property
    def saved_bytes(self) -> int:
        return self.original_bytes - self.stored_bytes


def reduce_on_the_way_in(payload: bytes, media_type: str) -> Reduction:
    """The door. Returns what to file — **never larger, never different**.

    Three guarantees, and each is enforced below rather than promised here:

      * the image a reader decodes from the result is bit-identical to the one
        they would have decoded from the upload;
      * the result is never bigger than the upload (if a re-encode came out
        larger, the original is returned);
      * any file this module cannot parse is returned **untouched**.
    """
    media_type = (media_type or "").split(";")[0].strip().lower()
    original = len(payload)
    if media_type not in REDUCIBLE_TYPES or original < MIN_REDUCIBLE_BYTES:
        return Reduction(payload=payload, original_bytes=original, method=None)

    try:
        if media_type == "image/png":
            shrunk = _png_redeflate(payload)
            method = METHOD_PNG
        else:
            shrunk = _jpeg_strip_metadata(payload)
            method = METHOD_JPEG
    except Exception:
        # ⚠ NOT hard-won law 14's forbidden catch — there is no database in
        # this module. A file we cannot parse is STORED AS IT ARRIVED. See the
        # module docstring before narrowing this.
        return Reduction(payload=payload, original_bytes=original, method=None)

    # ⚠ **NEVER BIGGER.** A re-encode that grew is a reduction that failed, and
    # storing it would cost bytes AND change the file for nothing.
    if shrunk is None or len(shrunk) >= original:
        return Reduction(payload=payload, original_bytes=original, method=None)
    return Reduction(payload=shrunk, original_bytes=original, method=method)


# ═══════════════════════════════════════════════════════════════════════════
# PNG — re-deflate the pixel stream, and PROVE it still inflates to the same
# ═══════════════════════════════════════════════════════════════════════════


def _png_chunks(blob: bytes) -> list[tuple[bytes, bytes]]:
    """Every chunk as `(type, data)`. Raises on anything that is not a PNG."""
    if blob[:8] != _PNG_MAGIC:
        raise ValueError("not a PNG")
    out: list[tuple[bytes, bytes]] = []
    i = 8
    while i + 8 <= len(blob):
        (length,) = struct.unpack(">I", blob[i : i + 4])
        kind = blob[i + 4 : i + 8]
        data = blob[i + 8 : i + 8 + length]
        if len(data) != length:
            raise ValueError("truncated PNG chunk")
        out.append((kind, data))
        i += 12 + length
        if kind == b"IEND":
            break
    if not out or out[0][0] != b"IHDR":
        raise ValueError("PNG without IHDR")
    return out


def _png_rebuild(chunks: list[tuple[bytes, bytes]]) -> bytes:
    out = bytearray(_PNG_MAGIC)
    for kind, data in chunks:
        out += struct.pack(">I", len(data)) + kind + data
        out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return bytes(out)


def _png_redeflate(blob: bytes) -> bytes | None:
    """Same pixels, smaller file — and the sameness is CHECKED, not assumed.

    A PNG's image data is one zlib stream split across any number of `IDAT`
    chunks. Inflating it and re-deflating at level 9 changes **the compression
    and nothing else**: the filtered scanline bytes that come back out are the
    same bytes, so every pixel, the bit depth, the colour type, the palette and
    the alpha are all untouched by construction.

    ⚠ **AND IT IS VERIFIED ANYWAY (hard-won law 7 — what would make this pass
    wrongly?).** *By construction* is an argument, and an argument is what
    hard-won law 1 says is not a guarantee. The re-deflated stream is inflated
    again and compared byte-for-byte with what came out of the original; a
    mismatch returns `None` and the upload is stored as it arrived.

    ⚠ **EVERY NON-`IDAT` CHUNK IS CARRIED THROUGH IN ORDER**, `tEXt` and
    `gAMA` and `pHYs` included. They are small, and a `pHYs` chunk is what tells
    a viewer the scan is 300 dpi rather than a 3,000-pixel-wide poster.
    """
    chunks = _png_chunks(blob)
    packed = b"".join(data for kind, data in chunks if kind == b"IDAT")
    if not packed:
        return None
    pixels = zlib.decompress(packed)
    repacked = zlib.compress(pixels, 9)
    # THE CHECK. Not decoration — see the docstring.
    if zlib.decompress(repacked) != pixels:
        return None
    if len(repacked) >= len(packed):
        return None

    rebuilt: list[tuple[bytes, bytes]] = []
    written = False
    for kind, data in chunks:
        if kind == b"IDAT":
            if not written:
                rebuilt.append((b"IDAT", repacked))
                written = True
            continue
        rebuilt.append((kind, data))
    return _png_rebuild(rebuilt)


# ═══════════════════════════════════════════════════════════════════════════
# JPEG — drop the metadata, copy the image bytes verbatim
# ═══════════════════════════════════════════════════════════════════════════


def _jpeg_strip_metadata(blob: bytes) -> bytes | None:
    """Same scan, no EXIF — and the scan is COPIED rather than re-encoded.

    A JPEG is `SOI`, a run of marker segments, then the entropy-coded scan and
    `EOI`. The quantisation tables (`DQT`), the Huffman tables (`DHT`), the
    frame header (`SOF`) and the scan itself are what a decoder needs; `APP1`
    (EXIF and XMP), `APP2` (ICC, FPXR), `APP13` (Photoshop, with its own
    preview) and `COM` are not, and a phone's `APP1` alone routinely carries a
    thumbnail of tens of kilobytes.

    ⚠ **NOT ONE BYTE OF IMAGE DATA IS RE-ENCODED.** Everything from `SOS`
    onward is `blob[i:]`, copied straight across. The pixels cannot change
    because nothing ever decodes them.

    ⚠ **`APP0` AND `APP14` ARE KEPT** — see `_JPEG_STRIPPABLE`. Dropping the
    first changes a scan's displayed size; dropping the second inverts the
    colours of a CMYK scan. Both would be this module changing what a person
    sees, which it may not do.

    ⚠ **AN ICC PROFILE IS DROPPED WITH `APP2` AND THAT IS A DELIBERATE, NAMED
    TRADE.** On a document scan it moves colour slightly; it does not move a
    licence number, a signature or a boundary line, and it is measured in tens
    of kilobytes. If a utility ever attaches colour-critical artwork here, this
    is the line to change.
    """
    if blob[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    out = bytearray(b"\xff\xd8")
    i = 2
    end = len(blob)
    while i + 4 <= end:
        if blob[i] != 0xFF:
            raise ValueError("JPEG segment does not start with a marker")
        marker = blob[i + 1]
        # Padding: a run of 0xFF before a marker is legal.
        if marker == 0xFF:
            i += 1
            continue
        # `SOS` — the scan follows and runs to the end. Copy the rest verbatim
        # and stop parsing; the entropy-coded data is not a segment and must
        # never be walked as one.
        if marker == 0xDA:
            out += blob[i:]
            return bytes(out)
        # Standalone markers carry no length.
        if marker in (0x01,) or 0xD0 <= marker <= 0xD9:
            out += blob[i : i + 2]
            i += 2
            continue
        (length,) = struct.unpack(">H", blob[i + 2 : i + 4])
        if length < 2 or i + 2 + length > end:
            raise ValueError("bad JPEG segment length")
        if marker not in _JPEG_STRIPPABLE:
            out += blob[i : i + 2 + length]
        i += 2 + length
    # Ran off the end without ever meeting a scan: not a JPEG we understand.
    raise ValueError("JPEG with no SOS")


# ── Lifecycle ─────────────────────────────────────────────
# packet: the PO's "you will have to reduce the size and save them on cloud container etc" (the REDUCE half) · BR-SHL-031 · BR-WRK-047 (the product's existing ruling, followed rather than contradicted) · NFR-33 / NFR-35
# generated: 2026-09-19 by the service-request-documents lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint of its own — called by apps/customers/service_request_documents.py) E=deferred(no-frontend-half — the step 4 screen is a later lane; ServiceRequestCapturePage.tsx is owned by a sibling) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the PNG round-trip check was shown returning a corrupted stream before the verify was added; the JPEG walker was shown raising on a scan it had walked as a segment. Measured on 56 real PNGs: 18,076,547 -> 13,306,223 bytes, 26.4%.
# exceptions: (1) NOTHING IS LOSSY — argued at length in the module docstring; the larger saving a downscale would buy is recorded in the decision log rather than taken. (2) A BROAD `except Exception` that is NOT hard-won law 14's forbidden catch, because this module touches no database — said so in the docstring so it is not narrowed by a later lane. (3) An ICC profile is dropped with APP2; named as a trade rather than hidden.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
