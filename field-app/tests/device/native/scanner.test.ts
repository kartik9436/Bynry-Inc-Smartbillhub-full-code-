/**
 * The real scanner over expo-camera's barcode reader: our seven formats map to
 * expo's names and back, a read reaches the screen through the port, and the
 * reading screens' one-shot `scan()` ends with null when the viewfinder is
 * closed without a code.
 */
import { FORMATS_BY_MODE, SCAN_FORMATS, UNWIRED_DEVICE } from '../../../src/device';
import { DeviceHostController } from '../../../src/device/native/host';
import { barcodeTypesFor, codeOf, expoScanner, formatOf } from '../../../src/device/native/scanner';
import { readsPortsFrom } from '../../../src/screens/reads/ports';

test('the seven formats the design names map to expo-camera barcode types (requirement 84)', () => {
  expect(barcodeTypesFor(SCAN_FORMATS)).toEqual(['code128', 'code39', 'itf14', 'upc_a', 'ean13', 'qr', 'datamatrix']);
  expect(barcodeTypesFor(FORMATS_BY_MODE.qr)).toEqual(['qr', 'datamatrix']);
});

test.each([
  ['code128', 'code128'],
  ['org.iso.Code128', 'code128'],
  ['org.iso.Code39', 'code39'],
  ['itf14', 'itf'],
  ['org.ansi.Interleaved2of5', 'itf'],
  ['upc_a', 'upc_a'],
  ['org.gs1.EAN-13', 'ean13'],
  ['qr', 'qr'],
  ['org.iso.QRCode', 'qr'],
  ['datamatrix', 'datamatrix'],
  ['org.iso.DataMatrix', 'datamatrix'],
  [256, 'qr'],
  ['pdf417', null],
  ['aztec', null],
] as Array<[string | number, string | null]>)('platform type %p reads as %p', (type, format) => {
  expect(formatOf(type)).toBe(format);
});

test('a read with no text is no code; text is trimmed', () => {
  expect(codeOf({ type: 'qr', data: '  ' })).toBeNull();
  expect(codeOf({ type: 'code128', data: ' 90118 ' })).toEqual({ value: '90118', format: 'code128' });
});

test('start() opens a session on the host; a read reaches the screen; stop() ends it', () => {
  const host = new DeviceHostController();
  const scanner = expoScanner(host);
  expect(scanner.available).toBe(true);
  expect(scanner.Preview).toBeDefined();
  const codes: string[] = [];
  const stop = scanner.start(FORMATS_BY_MODE.barcode, (c) => codes.push(c.value));
  host.codeRead({ value: '90118', format: 'ean13' });
  scanner.setTorch(true);
  expect(host.torch).toBe(true);
  stop();
  expect(host.scan).toBeNull();
  expect(codes).toEqual(['90118']);
});

test("the reading screens' one-shot scan: the first code, or null when the viewfinder is closed", async () => {
  const host = new DeviceHostController();
  const ports = readsPortsFrom({ ...UNWIRED_DEVICE, scanner: expoScanner(host) });
  expect(ports.scanner.available).toBe(true);

  const first = ports.scanner.scan();
  host.codeRead({ value: 'SN-4471', format: 'code128' });
  await expect(first).resolves.toBe('SN-4471');
  expect(host.scan).toBeNull();

  const second = ports.scanner.scan();
  expect(host.fullScreenScan).toBe(true);
  host.closeScan();
  await expect(second).resolves.toBeNull();
});
