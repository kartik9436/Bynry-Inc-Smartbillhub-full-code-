/**
 * The REAL scanner behind `ScannerPort` (`../scanner.ts`): `expo-camera`'s
 * built-in barcode reader — Code 128, Code 39, ITF, UPC-A, EAN-13, QR and
 * Data Matrix (requirement 84). No second camera package: the same module
 * takes the photographs.
 *
 * `start()` opens a scan session on the device host. Where a screen draws the
 * live view inline (FF-38 renders `Preview`), the host stays out of the way;
 * where it does not (the reading screens' one-shot `scan()`), the host puts up
 * a full-screen viewfinder with a Close, and Close ends the session.
 *
 * What a code MEANS is not the scanner's business (`db/queries/asset`).
 */
import type { BarcodeType } from 'expo-camera';
import { createElement } from 'react';

import type { ScanFormat, ScannedCode, ScannerPort } from '../scanner';
import type { DeviceHostController } from './host';
import { InlineScanPreview } from './DeviceHost';

/** Our format names → expo-camera's. */
export const BARCODE_TYPE: Record<ScanFormat, BarcodeType> = {
  code128: 'code128',
  code39: 'code39',
  itf: 'itf14',
  upc_a: 'upc_a',
  ean13: 'ean13',
  qr: 'qr',
  datamatrix: 'datamatrix',
};

export function barcodeTypesFor(formats: readonly ScanFormat[]): BarcodeType[] {
  return [...new Set(formats.map((f) => BARCODE_TYPE[f]))];
}

/**
 * expo-camera's `type` string → our format, or null for one we did not ask
 * for. The platforms spell it differently (`code128`, `org.iso.Code128`,
 * `org.gs1.ITF14`, a bare number on old Android builds), so this reads the
 * letters and digits and ignores the rest.
 */
export function formatOf(type: string | number): ScanFormat | null {
  const t = String(type).toLowerCase().replace(/[^a-z0-9]/g, '');
  if (t.includes('datamatrix')) return 'datamatrix';
  if (t.endsWith('qr') || t.includes('qrcode') || t === 'qr') return 'qr';
  if (t.includes('code128')) return 'code128';
  if (t.includes('code39')) return 'code39';
  if (t.includes('itf') || t.includes('interleaved2of5')) return 'itf';
  if (t.includes('upca')) return 'upc_a';
  if (t.includes('ean13')) return 'ean13';
  // Android's ML Kit constants, for builds that pass the number through.
  const n = Number(type);
  if (Number.isInteger(n)) return ({ 1: 'code128', 2: 'code39', 32: 'ean13', 128: 'itf', 256: 'qr', 512: 'upc_a', 16: 'datamatrix' } as Record<number, ScanFormat>)[n] ?? null;
  return null;
}

/** A barcode event from expo-camera → our code, or null. */
export function codeOf(result: { type: string | number; data: string }): ScannedCode | null {
  const format = formatOf(result.type);
  const value = typeof result.data === 'string' ? result.data.trim() : '';
  return format && value ? { value, format } : null;
}

export function expoScanner(host: DeviceHostController): ScannerPort {
  return {
    available: true,
    Preview: function ScanPreview() {
      return createElement(InlineScanPreview, { host });
    },
    start: (formats, onCode, onClose) => host.startScan(formats, onCode, onClose),
    setTorch: (on) => host.setTorch(on),
  };
}
