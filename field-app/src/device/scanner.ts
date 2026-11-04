/**
 * THE scanner port, one for the whole app (moved here from
 * `screens/raise/scanner.ts` in the integration lane; the reads wave's
 * one-shot `scan()` is a view of it, `device/views.ts`).
 *
 * Scanning — the first-class way to identify a meter; typing is the fallback
 * (R83, US-FLD-038, US-FLD-084).
 *
 * The real one is `native/scanner.ts` (expo-camera's barcode reader, wired by
 * the dependency lane). `unwiredScanner` stays for builds and tests with no
 * camera — FF-38 then offers *Enter manually*, which is exactly the
 * damaged-label path (TC-4) — and `FakeScanner` lets a test present a code.
 *
 * What a code MEANS is not the scanner's business: the screen matches it
 * serial, then badge, then device id (`db/queries/asset.matchScannedCode`,
 * R43), one order everywhere.
 */
import type { ComponentType } from 'react';

/** The symbologies the design names (requirement 84). */
export const SCAN_FORMATS = ['code128', 'code39', 'itf', 'upc_a', 'ean13', 'qr', 'datamatrix'] as const;
export type ScanFormat = (typeof SCAN_FORMATS)[number];

/** FF-38 draws two modes: Barcode (every 1D format) and QR (QR and Data Matrix). */
export type ScanMode = 'barcode' | 'qr';

export const FORMATS_BY_MODE: Record<ScanMode, readonly ScanFormat[]> = {
  barcode: ['code128', 'code39', 'itf', 'upc_a', 'ean13'],
  qr: ['qr', 'datamatrix'],
};

export interface ScannedCode {
  value: string;
  format: ScanFormat;
}

export interface ScannerPort {
  /** False when the handset cannot scan at all — the screen offers typing. */
  readonly available: boolean;
  /** The camera's live view, drawn by the real implementation. */
  readonly Preview?: ComponentType;
  /** Start reading codes of these formats; the camera stays open (continuous
   *  mode, US-FLD-084 TC-1). Returns the stop function. `onClose` is called
   *  when the technician closes a viewfinder the implementation drew itself
   *  (no screen drew `Preview`) — the session is over without a code. */
  start(formats: readonly ScanFormat[], onCode: (code: ScannedCode) => void, onClose?: () => void): () => void;
  setTorch(on: boolean): void;
}

export const unwiredScanner: ScannerPort = {
  available: false,
  start: () => () => undefined,
  setTorch: () => undefined,
};
