# A customer's PDF, opened by the clerk in a real PDF viewer — 2026-10-02

`CR-158-BRC10` (2.438.0) left one thing unproved: whether a PDF a customer uploads
is actually DRAWN for the clerk, because headless Chromium has no PDF viewer. This
walk ran Chromium 141 (`/opt/pw-browsers/chromium-1194`) **headed, under
`xvfb-run`**, where its built-in viewer exists.

Spec: `07-frontend/e2e/CR-158-pdf-display-headed.spec.ts` (skips by name unless
`E2E_HEADED=1` and `--headed`). World: Six Rivers Utility, seeded by
`10-scripts/cr158_seed_portal_upload.py`, on PostgreSQL 16, Django, and the built
SPA (`vite build --mode e2e`, so the API is same-origin).

| Screen | What it shows |
|---|---|
| `1-customer-three-files.png` | The applicant attached a 3-page PDF, a PNG and a JPEG |
| `2-clerk-documents-tab.png` | The clerk's Documents tab: three files, type and size |
| `3-pdf-in-chromium-viewer.png` | **The PDF in Chromium's viewer: "SAMPLE ID — page 1", toolbar `1 / 3`** |
| `4-png-opened.png` | The PNG drawn as an image (480×300) |
| `5-jpg-opened.png` | The JPEG drawn as an image (480×300) |

## Proved
- The PDF opens in Chromium's viewer and its text is on screen. The viewer's own
  toolbar was read through its extension target and said **3** pages.
- Served headers for "open": `Content-Type: application/pdf` (the stored type),
  `Content-Disposition: inline; filename="sample-id.pdf"`, `nosniff`, and
  `default-src 'none'` with no `script-src`. None of them blocked the viewer, so
  **no header change was needed and no code changed.**
- "Download" (`as=download`) answers `attachment` and the browser saved
  `sample-id.pdf` instead of drawing it.
- PNG and JPEG answer `image/png` / `image/jpeg`, `inline`, and decode to their
  real size. Bytes served equal bytes uploaded for all three.
- The spec goes red when it should: with "open" forced to `attachment`, the tab
  never reaches the viewer and the run fails.

## Measured on the way, not changed
- Dropping `object-src 'self'` from the policy, or adding `sandbox`, did **not**
  stop Chromium 141's viewer. The code comment says `object-src 'self'` is what
  lets a viewer draw; that is not true of Chromium for a top-level open. It may be
  of another browser, and none was tried, so the policy was left as it is.
- The viewer's title bar reads `content` (the last part of the address), not the
  file's name.

## Not proved
- Firefox and Safari viewers. Only Chromium is on this machine.
- Whether script inside a PDF runs in Chromium's viewer. The page policy does not
  govern the viewer's own PDF engine, so this walk could not test it.
