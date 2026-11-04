/**
 * The handset's abilities that every wave shares — position, dictation, the
 * document viewer — as ONE set of ports (integration lane). The camera and
 * shrink are `photo.ts`, the scanner `scanner.ts`, the signing pad
 * `signature.ts`; `index.ts` bundles them as the `Device` the app root builds
 * once, and `views.ts` derives each wave's own port shape from it, so a screen
 * keeps the interface it was built against while the app has one camera, one
 * scanner and one position.
 *
 * ⚠ THE NATIVE BUILD WIRES THE REAL ONES (`native/`, 2026-10-21) — the
 * document opener last (FB-031, 2026-10-31; the signing pad joined 2026-10-27,
 * DEF-FLD-10627). Before that,
 * NONE OF THE NATIVE PACKAGES WAS INSTALLED (expo-camera, expo-location, a
 * speech-to-text module, a PDF viewer, a barcode reader, a signing pad). Each
 * port therefore has an UNWIRED default that refuses, or answers "no fix",
 * naming what is missing — never a made-up value. Wiring the real ones is a
 * dependency decision (the coordinator owns package.json) and touches these
 * files and nothing in a screen.
 */
import type { CaptureLocation, PhotoCapture } from '../sync/outbox';

/** A position fix with its accuracy (R90). The same shape the outbox stores. */
export type Fix = CaptureLocation;

/** A photograph on disk, ready to be captured — what the outbox carries, without its target. */
export type TakenPhoto = Omit<PhotoCapture, 'target'>;

/** A held fix older than this loses to any new one, however rough — and is not "where the handset is". */
export const FIX_STALE_MS = 2 * 60 * 1000;

/** Where the handset is. `current()` asks for a fix now; `last()` is the newest one held. */
export interface LocationDevice {
  current(): Promise<Fix | null>;
  last(): Fix | null;
  /**
   * Start the background watch if it is not running (DEF-FLD-10605): called
   * when location permission arrives after start-up. Idempotent; a port with
   * no watch leaves it out.
   */
  startWatch?(): void;
  /**
   * FB-003 (PO 2026-10-27): make location usable where it is about to be
   * used — the route and the camera. Not allowed yet → the platform's own
   * *Allow location?* prompt; the phone's Location switched off → Android's
   * own *Turn on location?* dialog. Answers what the reader can now expect.
   */
  ensureOn?(): Promise<LocationAccess>;
  /** Every fix the watch accepts, as it arrives (the stamp updates live; a late fix is attached). */
  subscribe?(onFix: (fix: Fix) => void): () => void;
  /** The app's own settings page — the only way back once Android will not ask again. */
  openSettings?(): Promise<void>;
}

/**
 * FB-003: `on` — allowed and switched on; `refused` — refused this time
 * (Android asks again next time); `blocked` — refused with *Don't ask again*
 * (only the settings page can change it); `off` — allowed, but the phone's
 * Location is off and stayed off; `unknown` — this build cannot tell.
 */
export type LocationAccess = 'on' | 'refused' | 'blocked' | 'off' | 'unknown';

/** Speech to text, once (R38: dictation beside every note; R95). */
export interface DictationDevice {
  readonly available: boolean;
  /** Resolves the words heard, or null for nothing. */
  listen(language: string): Promise<string | null>;
}

/**
 * Opens a document from the phone's own copy (FF-28, "open offline") — on the
 * native build through the operating system's *Open with…* (FB-031, PO ruling
 * B, 2026-10-31). `contentType` tells the phone's own apps what the file is.
 * Rejects `NoAppError` when no app on the phone can open it.
 */
export interface DocumentOpener {
  open(localPath: string, contentType?: string): Promise<void>;
}

/** FB-031: nothing installed on the phone can open this file (*No app can open this.*). */
export class NoAppError extends Error {
  constructor(readonly path: string) {
    super(`no app on this phone opens ${path}`);
    this.name = 'NoAppError';
  }
}

export class PortUnavailableError extends Error {
  constructor(readonly port: string) {
    super(`${port} is not wired on this build`);
    this.name = 'PortUnavailableError';
  }
}

/** No location package: no fix, which every screen warns about and still accepts (R91). */
export const NO_LOCATION: LocationDevice = { current: () => Promise.resolve(null), last: () => null };

export const UNWIRED_DICTATION: DictationDevice = {
  available: false,
  listen: () => Promise.reject(new PortUnavailableError('dictation')),
};

export const UNWIRED_DOCUMENTS: DocumentOpener = {
  open: () => Promise.reject(new PortUnavailableError('document viewer')),
};
