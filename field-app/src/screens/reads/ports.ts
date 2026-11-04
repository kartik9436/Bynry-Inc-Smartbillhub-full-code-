/**
 * The handset hardware the reading screens use, as PORTS: the screens call an
 * interface and the app (or a test) supplies the thing behind it.
 *
 * Since the integration lane these are VIEWS of the app's one `Device`
 * (`src/device/`): `readsPortsFrom(device)` gives the reading screens a
 * one-shot `scan()` over the app's continuous scanner and a `take(stamp)` over
 * its camera, shrink and hash, while `Fix`, the dictation port and the refusal
 * are the device's own. Each has an
 * `unavailable…` implementation that REFUSES rather than pretends: the app has
 * no camera, barcode or location library installed today (expo-camera and
 * expo-location are not dependencies), so on a handset these are what run
 * until the real ones are wired — and each screen says so in plain words
 * instead of showing a working-looking control that does nothing.
 */

import type { ComponentType } from 'react';

import { type Device, type DictationDevice, type Fix as DeviceFix, type LocationAccess, PortUnavailableError, SCAN_FORMATS, takeReadyPhoto, UNWIRED_DICTATION } from '../../device';

/** RW-11 / RW-19 / RW-20: a scanned badge or serial plate. */
export interface ScannerPort {
  readonly available: boolean;
  /** Resolves with the code read, or null when the reader cancelled. */
  scan(): Promise<string | null>;
}

/** What a shutter press leaves on disk. The bytes are never in the database (R52). */
export interface CameraShot {
  localPath: string;
  sha256: string;
  bytes: number;
  width?: number;
  height?: number;
  /** FB-003 (PO 2026-10-27): the position AT THE SHUTTER, with its fix time —
   *  null when there was none. Absent on a shot from before this field. */
  location?: Fix | null;
}

/**
 * RW-14: the camera, and ONLY the camera — there is no gallery method, so no
 * screen can offer one (R93). `stamp` is burned INTO the pixels by the
 * implementation, never laid over them (R94).
 */
export interface CameraPort {
  readonly available: boolean;
  /** The camera's live view, drawn in RW-14's panel (DEF-FLD-10630); `take`
   *  then shoots from it. Absent: the panel shows the stamp alone. */
  readonly Preview?: ComponentType;
  take(stamp: readonly string[]): Promise<CameraShot>;
  /** Delete a photo's file that was never kept — a draft photo Removed or
   *  Retaken before the reading was saved (PO 2026-10-27). */
  discard?(localPath: string): Promise<void>;
}

/** A position fix with its accuracy (R90) — the device's own. */
export type Fix = DeviceFix;

/** The reader's own position — the only live thing on the walk (R76). Null is
 *  "no fix", which warns and still accepts (R91). */
export interface LocationPort {
  current(): Promise<Fix | null>;
  /** FB-003: the background watch's best fix, if any (fresh or not — the caller judges). */
  last?(): Fix | null;
  /** FB-003: each fix as the watch accepts it — the live stamp, the late position. */
  subscribe?(onFix: (fix: Fix) => void): () => void;
  /** FB-003: Android's own prompt (and *Turn on location?*) where location is used. */
  ensureOn?(): Promise<LocationAccess>;
  /** FB-003: the app's settings page — the only way back after *Don't ask again*. */
  openSettings?(): Promise<void>;
}

export type { LocationAccess };

/** RW-09 *Remark*: spoken by default, typed as the fallback (R95) — the device's own. */
export type DictationPort = DictationDevice;

export { PortUnavailableError };

export const unavailableScanner: ScannerPort = {
  available: false,
  scan: () => Promise.reject(new PortUnavailableError('scanner')),
};

export const unavailableCamera: CameraPort = {
  available: false,
  take: () => Promise.reject(new PortUnavailableError('camera')),
};

export const noLocation: LocationPort = { current: () => Promise.resolve(null) };

export const unavailableDictation: DictationPort = UNWIRED_DICTATION;

/** The reading screens' ports, from the app's one handset (`src/device`). */
export function readsPortsFrom(device: Device): { scanner: ScannerPort; camera: CameraPort; location: LocationPort; dictation: DictationPort } {
  const scanner: ScannerPort = {
    available: device.scanner.available,
    scan: () =>
      device.scanner.available
        ? new Promise<string | null>((resolve) => {
            let stop: (() => void) | null = null;
            let done = false;
            stop = device.scanner.start(
              SCAN_FORMATS,
              (code) => {
                if (done) return;
                done = true;
                stop?.();
                resolve(code.value);
              },
              // The viewfinder was closed without a code: the reader cancelled.
              () => {
                if (done) return;
                done = true;
                resolve(null);
              },
            );
            if (done) stop?.();
          })
        : Promise.reject(new PortUnavailableError('scanner')),
  };
  const available = device.camera.available !== false;
  const camera: CameraPort = {
    available,
    ...(available && device.camera.Preview ? { Preview: device.camera.Preview } : {}),
    discard: (localPath) => device.shrink.discard(localPath),
    take: async (stamp) => {
      if (!available) throw new PortUnavailableError('camera');
      const ready = await takeReadyPhoto(device.camera, device.shrink, { lines: [...stamp] });
      if (!ready) throw new PortUnavailableError('camera (cancelled)');
      return { localPath: ready.localPath, sha256: ready.sha256, bytes: ready.bytes, width: ready.width, height: ready.height };
    },
  };
  return { scanner, camera, location: device.location, dictation: device.dictation };
}
