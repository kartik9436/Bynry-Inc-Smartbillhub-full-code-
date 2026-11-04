# Reading a blueprint PDF

**Why this exists (2026-09-10).** `CR-089`'s agreed design arrived as a 113-page PDF
of wireframes. Nothing in this container could read it: `pdftoppm`/poppler will not
install, `PIL` times out on the network, and `pypdf` crashes on a broken
`cryptography` build. **A drawing a lane cannot open is a drawing that will not be
built** — which is exactly how five waves shipped a property Overview that did not
match its design.

Two scripts, stdlib plus `pypdfium2` (a self-contained wheel, no system packages):

| Script | What it does |
|---|---|
| `pdf_text.py <file.pdf>` | Prints the text, page by page. ⚠ **Applies each font's `/ToUnicode` CMap** — the text is written as subset glyph ids (`<2A> Tj`), so a naive extractor returns nothing at all, which is what the first attempt did |
| `pdf_render.py <file.pdf> <outdir> <scale> <1,2,3>` | Renders pages to PNG with no imaging library — zlib and struct only |

⚠ **`pdf_render.py` READS the channel count from the bitmap and never assumes it.**
The first draft assumed BGRA, wrote a 4-channel header over 3-channel BGR data, and
produced a file that is a **structurally valid PNG containing garbage** — every header
check passes and the picture is noise. That is the "looks at the wrong thing" shape
hard-won law 7 names, in an image encoder.
