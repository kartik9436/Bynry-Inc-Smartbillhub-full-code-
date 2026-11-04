/**
 * The REAL camera and shrink behind `CameraPort` / `ImageShrinkPort`
 * (`../photo.ts`): `expo-camera` takes the picture, `expo-image-manipulator`
 * resizes it, `react-native-view-shot` burns the stamp in and writes the JPEG
 * at the quality step asked for, `expo-file-system` reads the size and the
 * bytes, `expo-crypto` hashes them.
 *
 * The SIZE RULE is not here — it is `compressToBand` in `../photo.ts`, one
 * constant `PHOTO_BYTES` (70–100 binary KB, PO 2026-10-21 *"70-100 kb should
 * be readable"*), and it never refuses a photograph for its size: the smallest
 * attempt is kept. This file only answers "make one attempt at this quality".
 *
 * ⚠ **WHY `react-native-view-shot` AND NOT SKIA FOR THE STAMP (R94).** The
 * stamp is a few lines of text over a photograph, once per shutter press.
 * view-shot is a small native module (one capture call on each platform);
 * `@shopify/react-native-skia` is a full 2D engine that adds several MB of
 * native library per architecture to the install. Skia can draw off-screen
 * without a host view, which is its one advantage here — and the device host
 * (`DeviceHost.tsx`) already exists for the camera's viewfinder, so the
 * compositor rides in it at no extra cost. The capture is of a VIEW holding
 * the photograph and its stamp, so the stamp is in the pixels, never laid
 * over them.
 *
 * A shot from the camera is the camera's own file; nothing here reads it
 * back into the database (R52).
 */
import * as Crypto from 'expo-crypto';
import * as FileSystem from 'expo-file-system';
import { manipulateAsync, SaveFormat } from 'expo-image-manipulator';
import { createElement } from 'react';

import type { CameraPort, ImageShrinkPort, PhotoStamp, RawShot, ShrinkResult } from '../photo';
import { InlineCameraPreview } from './DeviceHost';
import type { DeviceHostController } from './host';

/** The camera's own JPEG before our ladder runs: best quality, our ladder does the shrinking. */
export const CAPTURE_QUALITY = 1;
/** The resized intermediate the stamp is drawn over: near-lossless, deleted after the hash. */
export const INTERMEDIATE_QUALITY = 0.95;

export function expoCamera(host: DeviceHostController): CameraPort {
  return {
    available: true,
    // RW-14's live view (DEF-FLD-10630): while it is on screen the shutter
    // takes the picture from it, and the full-screen viewfinder stays shut.
    Preview: function CameraPreview() {
      return createElement(InlineCameraPreview, { host });
    },
    takePhoto: () => host.requestPhoto(),
  };
}

/** The resize that puts the long side at `longSide` — never an upscale. */
export function resizeFor(width: number, height: number, longSide: number): { width: number } | { height: number } | null {
  if (Math.max(width, height) <= longSide) return null;
  return width >= height ? { width: longSide } : { height: longSide };
}

const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

/** Base64 to bytes, without relying on `atob` or `Buffer` being present. */
export function base64Bytes(b64: string): Uint8Array {
  const clean = b64.replace(/[^A-Za-z0-9+/]/g, '');
  const out = new Uint8Array(Math.floor((clean.length * 3) / 4));
  let o = 0;
  for (let i = 0; i < clean.length; i += 4) {
    const n =
      (B64.indexOf(clean[i] ?? 'A') << 18) |
      (B64.indexOf(clean[i + 1] ?? 'A') << 12) |
      ((B64.indexOf(clean[i + 2] ?? 'A') & 63) << 6) |
      (B64.indexOf(clean[i + 3] ?? 'A') & 63);
    if (o < out.length) out[o++] = (n >> 16) & 255;
    if (i + 2 < clean.length && o < out.length) out[o++] = (n >> 8) & 255;
    if (i + 3 < clean.length && o < out.length) out[o++] = n & 255;
  }
  return out;
}

function hex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('');
}

async function sizeOf(uri: string): Promise<number> {
  const info = await FileSystem.getInfoAsync(uri);
  return info.exists && typeof (info as { size?: number }).size === 'number' ? (info as { size: number }).size : 0;
}

export function expoShrink(host: DeviceHostController): ImageShrinkPort {
  // One resize per shot, shared by every quality step; deleted once the
  // chosen attempt is hashed (the last call `compressToBand` makes).
  const resized = new Map<string, Promise<RawShot>>();

  const resizedOf = (uri: string, longSide: number): Promise<RawShot> => {
    const key = `${uri}@${longSide}`;
    let held = resized.get(key);
    if (!held) {
      held = (async () => {
        const probe = await manipulateAsync(uri, [], { compress: INTERMEDIATE_QUALITY, format: SaveFormat.JPEG });
        const resize = resizeFor(probe.width, probe.height, longSide);
        if (!resize) return { uri: probe.uri, width: probe.width, height: probe.height };
        const out = await manipulateAsync(probe.uri, [{ resize }], { compress: INTERMEDIATE_QUALITY, format: SaveFormat.JPEG });
        await FileSystem.deleteAsync(probe.uri, { idempotent: true });
        return { uri: out.uri, width: out.width, height: out.height };
      })();
      held.catch(() => resized.delete(key));
      resized.set(key, held);
    }
    return held;
  };

  return {
    async shrink(uri: string, opts: { longSide: number; quality: number; stamp: PhotoStamp }): Promise<ShrinkResult> {
      const base = await resizedOf(uri, opts.longSide);
      const out = await host.requestStamp({
        uri: base.uri,
        width: base.width,
        height: base.height,
        lines: opts.stamp.lines,
        quality: opts.quality,
      });
      return { uri: out.uri, bytes: await sizeOf(out.uri), width: out.width, height: out.height };
    },

    async sha256(uri: string): Promise<string> {
      const b64 = await FileSystem.readAsStringAsync(uri, { encoding: FileSystem.EncodingType.Base64 });
      const digest = await Crypto.digest(Crypto.CryptoDigestAlgorithm.SHA256, base64Bytes(b64));
      // The ladder is over: drop the shared intermediates.
      const held = [...resized.values()];
      resized.clear();
      for (const p of held) {
        const shot = await p.catch(() => null);
        if (shot && shot.uri !== uri) await FileSystem.deleteAsync(shot.uri, { idempotent: true });
      }
      return hex(digest);
    },

    async discard(uri: string): Promise<void> {
      await FileSystem.deleteAsync(uri, { idempotent: true });
    },
  };
}
