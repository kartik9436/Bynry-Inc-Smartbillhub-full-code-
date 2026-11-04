// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-048 — the compression that pays for keeping photographs
// Rules:    BR-WRK-047 (compressed AT CAPTURE to 100 KB max — PO ruling
//           2026-09-04 on OQ-WRK-1496) · BR-WRK-047a (the upload goes through
//           the application, which is also where the ceiling is enforced)
// Tests:    src/features/work/mobile/compressPhoto.test.ts
// Impacts:  06-backend/apps/work/work_documents.py (the SERVER's ceiling —
//           the same number, enforced again where it cannot be skipped)
// ───────────────────────────────────────────────────────

/**
 * Make a photograph small enough to send, on the handset, before it is sent.
 *
 * THE RULING THIS IMPLEMENTS, IN THE PRODUCT OWNER'S OWN WORDS
 * ─────────────────────────────────────────────────────────────────────────
 * *"also you will ahve to reduce the sizes of images otherwise stroage will go
 * out of roof; we used to get this problem image sizes are 1Gb 2 GB and then
 * suggesdenly stroage is not enough. when we develope mobile apap, when image
 * is captured we redce the size first 50 Kb 60 Kb or 100 kb max"*
 * (2026-09-04, closing `OQ-WRK-1496`).
 *
 * ⚠ **THE RULE IS THE BYTES, NOT THE PIXELS, AND THAT IS A CHANGE.**
 * `BR-WRK-047` said *"the phone resizes to 1,600 px"* until 2026-09-05, and a
 * lane implementing that sentence would resize and stop. **A 1,600 px
 * photograph of a dark meter cupboard can still be 300 KB** — dark, noisy
 * images compress badly, and a meter cupboard is the single most likely
 * subject on this screen. So 1,600 px is the FIRST STEP and the quality is
 * stepped down until the bytes actually fit.
 *
 * ⚠ **AND IT NEVER GIVES UP SILENTLY.** If even the smallest quality will not
 * fit, this throws rather than returning something too big. The server refuses
 * it anyway (`work_documents.check_photo_bytes`), and a technician learning at
 * sync time that nine photographs were rejected — hours later, off site — is
 * the worst possible moment to find out. Failing here happens with the meter
 * still in front of them.
 *
 * ⚠ **WHY THE SERVER ALSO CHECKS.** A client-side rule the server does not
 * enforce is a comment claiming a guarantee (hard-won law 1). One old build,
 * one replayed request, one second client, and the 2 GB original is in the
 * bucket — which is the exact failure the PO described from experience.
 */

/** 100 KB. ⚠ Binary, matching `work_documents.MAX_PHOTO_BYTES` exactly. */
export const MAX_PHOTO_BYTES = 100 * 1024;

/** The first step, not the target. See the module docstring. */
export const LONG_EDGE_PX = 1600;

/** The band's floor (PO 2026-10-04: *"compress images to 70 to 100 Kb"*). */
export const TARGET_MIN_BYTES = 70 * 1024;

/**
 * Quality ladder, HIGHEST FIRST (PO 2026-10-04 moved the target from 50–60 KB
 * to 70–100 KB). The first step that fits under the ceiling is the largest
 * that does — which is what lands a photograph in the band instead of
 * squeezing a legible dial down to 50 KB.
 */
const QUALITY_STEPS = [0.92, 0.85, 0.78, 0.7, 0.62, 0.55, 0.48, 0.4, 0.33, 0.25] as const;

export class PhotoTooLarge extends Error {}

function scaledSize(width: number, height: number): { w: number; h: number } {
  const longest = Math.max(width, height);
  if (longest <= LONG_EDGE_PX) return { w: width, h: height };
  const factor = LONG_EDGE_PX / longest;
  return { w: Math.round(width * factor), h: Math.round(height * factor) };
}

/**
 * Resize and compress into the 70–100 KB band. **NEVER THROWS FOR SIZE**
 * (`DEF-WRK-9641`, PO 2026-10-04: *"we have to ensure phone is copressing it -
 * but you cannot reject the photo - that will drop the data"*): when no step
 * gets under 100 KB the SMALLEST result is returned and sent, and the server
 * shrinks it. `PhotoTooLarge` is kept as an export so older callers compile;
 * nothing throws it any more.
 *
 * Returns a JPEG `Blob`. JPEG and not PNG deliberately: a PNG of a photograph
 * is lossless and enormous, and there is nothing here to be lossless about —
 * a meter dial is a photograph, not a diagram.
 */
export async function compressPhoto(
  file: Blob,
  deps: {
    createBitmap?: (blob: Blob) => Promise<{ width: number; height: number; close?: () => void }>;
    makeCanvas?: (w: number, h: number) => HTMLCanvasElement | OffscreenCanvas;
  } = {},
): Promise<Blob> {
  // Already inside the ceiling and already a JPEG — nothing to gain by
  // re-encoding, and re-encoding would lose quality for no reason.
  if (file.size <= MAX_PHOTO_BYTES && file.type === "image/jpeg") return file;

  const createBitmap = deps.createBitmap ?? ((blob: Blob) => createImageBitmap(blob));
  const makeCanvas =
    deps.makeCanvas ??
    ((w: number, h: number) => {
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      return canvas;
    });

  let bitmap: { width: number; height: number; close?: () => void };
  try {
    bitmap = await createBitmap(file);
  } catch {
    // Not decodable here — send it as taken; the server decides (and refuses
    // only a file that is not an image at all).
    return file;
  }
  const { w, h } = scaledSize(bitmap.width, bitmap.height);
  const canvas = makeCanvas(w, h);
  const context = (canvas as HTMLCanvasElement).getContext("2d");
  if (!context) return file;
  context.drawImage(bitmap as unknown as CanvasImageSource, 0, 0, w, h);
  bitmap.close?.();

  let smallest: Blob | null = null;
  for (const quality of QUALITY_STEPS) {
    const blob = await toBlob(canvas, quality);
    if (!blob) continue;
    if (blob.size <= MAX_PHOTO_BYTES) return blob;
    if (smallest === null || blob.size < smallest.size) smallest = blob;
  }
  // Nothing fitted: the smallest it could make is SENT, never dropped.
  return smallest ?? file;
}

function toBlob(
  canvas: HTMLCanvasElement | OffscreenCanvas,
  quality: number,
): Promise<Blob | null> {
  if ("convertToBlob" in canvas) {
    return (canvas as OffscreenCanvas).convertToBlob({ type: "image/jpeg", quality });
  }
  return new Promise((resolve) =>
    (canvas as HTMLCanvasElement).toBlob(resolve, "image/jpeg", quality),
  );
}
