// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-WRK-9641 (a photo is never refused for size) · PO 2026-10-04
//          (compress to 70–100 KB before upload)
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import { compressPhoto, MAX_PHOTO_BYTES, TARGET_MIN_BYTES } from "./compressPhoto";

/** A canvas whose JPEG size falls with quality: 4 MB at 1.0, linear. */
function fakeCanvas(bytesAtFullQuality: number) {
  return () =>
    ({
      getContext: () => ({ drawImage: () => undefined }),
      convertToBlob: async ({ quality }: { quality: number }) =>
        new Blob([new Uint8Array(Math.round(bytesAtFullQuality * quality * quality))], { type: "image/jpeg" }),
    }) as unknown as OffscreenCanvas;
}

const camera = new Blob([new Uint8Array(4 * 1024 * 1024)], { type: "image/jpeg" });
const bitmap = async () => ({ width: 4000, height: 3000 });

describe("compressPhoto — the 70–100 KB band, and never a refusal", () => {
  it("a 4 MB photo comes out between 70 and 100 KB", async () => {
    const out = await compressPhoto(camera, { createBitmap: bitmap, makeCanvas: fakeCanvas(160 * 1024) });
    expect(out.size).toBeGreaterThanOrEqual(TARGET_MIN_BYTES);
    expect(out.size).toBeLessThanOrEqual(MAX_PHOTO_BYTES);
  });

  it("never throws on a photo that will not get under 100 KB — it sends its smallest", async () => {
    const out = await compressPhoto(camera, { createBitmap: bitmap, makeCanvas: fakeCanvas(40 * 1024 * 1024) });
    expect(out.size).toBeGreaterThan(MAX_PHOTO_BYTES);
    expect(out.size).toBeLessThan(camera.size);
  });

  it("a file the phone cannot decode is sent as taken, not dropped", async () => {
    const out = await compressPhoto(camera, {
      createBitmap: async () => {
        throw new Error("undecodable");
      },
      makeCanvas: fakeCanvas(1),
    });
    expect(out).toBe(camera);
  });
});
