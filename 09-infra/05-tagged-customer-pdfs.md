# Deploy note — tagged customer PDFs (WeasyPrint, Liberation Sans)

`DEF-BIL-10546`, portal accessibility F-06. PO/QA ruling 2026-10-23, decision log
*"Portal accessibility, Group H (bill PDF, F-06)"*.

## What changed in the image

- **Python:** `weasyprint==70.0` in `06-backend/pyproject.toml`. The Dockerfile's
  build stage installs that list, so a rebuild picks it up. It brings pydyf,
  tinyhtml5, tinycss2, cssselect2, Pyphen and fontTools.
- **System libraries** (runtime stage of `06-backend/Dockerfile`): `libpango-1.0-0`,
  `libpangoft2-1.0-0`, `libharfbuzz0b`, `libharfbuzz-subset0`, `fontconfig`,
  `libfontconfig1`.
- **Font:** Liberation Sans 2.1.5 ships inside the source tree, at
  `06-backend/core/fonts/liberation/`, with its SIL OFL 1.1 licence in `OFL.txt`.
  The image copies it with the rest of `/app`. No system font package is needed.
- **Build check:** the Dockerfile renders one tiny page through
  `core.tagged_pdf.render` after copying the source. A missing library or font
  fails the BUILD, not the first bill run.

## What a running host must do

**Rebuild and redeploy the backend image.** Pulling new code into a container that
already runs does nothing: the system libraries come only from the image (hard-won
law 4). A host running the old image with the new code fails at the first issue
with `ModuleNotFoundError: weasyprint` or an `OSError` from Pango. The bill then
stays a draft (BR-BIL-033) and the run reports it, so no bill is lost, but none issues.

No migration, no setting, no `.env` change.

## What customers see

- Every bill issued after the deploy is kept as a tagged PDF/UA-1 file: headings,
  real tables, a language, a title, an embedded font. The same applies to final
  bills, statements and agreements.
- Bills issued before the deploy keep the file they were issued with. Nothing is
  regenerated.
- The layout chooser's preview (Settings → Templates) shows the tagged page.

## Cost

About **0.5 s per bill at issue** (measured 0.524 s against 0.0055 s before, 4
cores, HarfBuzz-subset present). A 2,000-bill cycle run spends about 17 more
minutes of one worker. Bill runs issue in background jobs, not in the 60-second
web request. `DEF-BIL-10557` asks for one real run to be measured.

## How to check a deployed host

```bash
# inside the backend container
python -c "from core import tagged_pdf; r = tagged_pdf.render('<!doctype html><html lang=\"en\"><head><title>t</title></head><body><h1>ok</h1></body></html>'); print(r.page_count, tagged_pdf.markers(r.data))"
```

It should print `1` and markers with `struct_tree_root: True`, `lang: 'en'` and
`embedded_fonts: True`. For a full validation, run
`10-scripts/a11y/verapdf_customer_pdfs.py` (it needs Java and veraPDF; see that
script's docstring).

## Rollback

Redeploy the previous image. Bills issued in between keep their tagged files,
which are write-once and stay valid. The previous image's hand-written writer
serves new bills again.
