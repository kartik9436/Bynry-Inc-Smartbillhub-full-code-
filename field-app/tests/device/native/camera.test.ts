/**
 * The real camera and shrink, with the native modules mocked: each maps the
 * platform's answer onto the port, and the size ladder (`compressToBand`,
 * `PHOTO_BYTES`) runs over them unchanged.
 */

import * as FileSystem from 'expo-file-system';
import { manipulateAsync } from 'expo-image-manipulator';

import { compressToBand, PHOTO_BYTES, PHOTO_LONG_SIDE_PX, PHOTO_QUALITY_STEPS, takeReadyPhoto } from '../../../src/device/photo';
import { base64Bytes, expoCamera, expoShrink, resizeFor } from '../../../src/device/native/camera';
import { DeviceHostController } from '../../../src/device/native/host';

jest.mock('expo-file-system', () => ({
  EncodingType: { Base64: 'base64', UTF8: 'utf8' },
  getInfoAsync: jest.fn(),
  readAsStringAsync: jest.fn(),
  deleteAsync: jest.fn(async () => undefined),
}));

jest.mock('expo-crypto', () => ({
  CryptoDigestAlgorithm: { SHA256: 'SHA-256' },
  digest: jest.fn(async (_alg: string, data: Uint8Array) => {
    const h = (require('crypto') as typeof import('crypto')).createHash('sha256').update(Buffer.from(data)).digest();
    return h.buffer.slice(h.byteOffset, h.byteOffset + h.byteLength);
  }),
}));

const fs = FileSystem as jest.Mocked<typeof FileSystem>;
const manipulate = manipulateAsync as jest.MockedFunction<typeof manipulateAsync>;

/** A host that answers every stamp job: quality q → a file whose size the test chose. */
function autoStampingHost(bytesAtQuality: (q: number) => number, onJob?: (job: { lines: readonly string[]; quality: number; width: number; height: number }) => void) {
  const host = new DeviceHostController();
  host.hostMounted();
  const sizes = new Map<string, number>();
  host.subscribe(() => {
    const job = host.stamps[0];
    if (!job) return;
    onJob?.(job);
    const uri = `file:///stamped-${job.quality}.jpg`;
    sizes.set(uri, bytesAtQuality(job.quality));
    job.resolve({ uri, width: job.width, height: job.height });
  });
  fs.getInfoAsync.mockImplementation(async (uri: string) => ({ exists: true, uri, size: sizes.get(uri) ?? 0, isDirectory: false, modificationTime: 0 }) as never);
  return host;
}

beforeEach(() => {
  jest.clearAllMocks();
  manipulate.mockImplementation(async (uri: string, actions?: unknown[]) => {
    const resize = (actions?.[0] as { resize?: { width?: number; height?: number } } | undefined)?.resize;
    if (!resize) return { uri: `${uri}#probe`, width: 3024, height: 4032 };
    // A portrait shot: 3024 × 4032, long side is the height.
    return resize.height ? { uri: `${uri}#resized`, width: 1200, height: resize.height } : { uri: `${uri}#resized`, width: resize.width ?? 0, height: 1200 };
  });
});

test('the long side is resized to 1,600 px on the right axis, and a small shot is never upscaled', () => {
  expect(resizeFor(4032, 3024, 1600)).toEqual({ width: 1600 });
  expect(resizeFor(3024, 4032, 1600)).toEqual({ height: 1600 });
  expect(resizeFor(1200, 900, 1600)).toBeNull();
});

test('base64 decodes to the exact bytes (the hash is of the file, not of its text)', () => {
  expect(Array.from(base64Bytes('YWJj'))).toEqual([97, 98, 99]);
  expect(Array.from(base64Bytes('YWI='))).toEqual([97, 98]);
  expect(Array.from(base64Bytes('YQ=='))).toEqual([97]);
});

test('the camera is the host viewfinder: takePhoto posts a request and returns the shot', async () => {
  const host = new DeviceHostController();
  host.hostMounted();
  const camera = expoCamera(host);
  expect(camera.available).toBe(true);
  const p = camera.takePhoto();
  host.camera?.resolve({ uri: 'file:///camera/shot.jpg', width: 3024, height: 4032 });
  await expect(p).resolves.toEqual({ uri: 'file:///camera/shot.jpg', width: 3024, height: 4032 });
});

test('one shrink attempt: resize once, burn the stamp in at the quality asked, size from the file', async () => {
  const seen: Array<{ lines: readonly string[]; quality: number; width: number; height: number }> = [];
  const host = autoStampingHost(() => 88 * 1024, (j) => seen.push({ lines: j.lines, quality: j.quality, width: j.width, height: j.height }));
  const shrink = expoShrink(host);
  const out = await shrink.shrink('file:///camera/shot.jpg', { longSide: PHOTO_LONG_SIDE_PX, quality: 0.7, stamp: { lines: ['21 Oct 2026 09:14', '41.881234, -87.623177 ±4 m'] } });
  expect(manipulate).toHaveBeenCalledWith('file:///camera/shot.jpg#probe', [{ resize: { height: 1600 } }], expect.objectContaining({ format: 'jpeg' }));
  expect(out).toEqual({ uri: 'file:///stamped-0.7.jpg', bytes: 88 * 1024, width: 1200, height: 1600 });
  // The stamp travels with the job (R94) — drawn INTO the capture by the host.
  expect(seen[0]).toMatchObject({ quality: 0.7, lines: ['21 Oct 2026 09:14', '41.881234, -87.623177 ±4 m'] });
});

test('the ladder over the real shrink stops at the first step inside 100 KB and hashes that file', async () => {
  // 0.8 → 140 KB, 0.7 → 112 KB, 0.6 → 96 KB: stops at 0.6.
  const table: Record<number, number> = { 0.8: 140, 0.7: 112, 0.6: 96, 0.5: 80, 0.4: 70, 0.3: 60 };
  const host = autoStampingHost((q) => (table[q] ?? 0) * 1024);
  fs.readAsStringAsync.mockResolvedValue('YWJj'); // "abc"
  const shrink = expoShrink(host);
  const ready = await compressToBand({ uri: 'file:///camera/shot.jpg', width: 3024, height: 4032 }, shrink, { lines: ['x'] });
  expect(ready.localPath).toBe('file:///stamped-0.6.jpg');
  expect(ready.bytes).toBe(96 * 1024);
  expect(ready.bytes).toBeLessThanOrEqual(PHOTO_BYTES.ceiling);
  expect(ready.overCeiling).toBe(false);
  expect(ready.sha256).toBe('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
  // The resize ran once for the whole ladder, and the larger attempts were deleted.
  expect(manipulate.mock.calls.filter((c) => c[1]?.length)).toHaveLength(1);
  expect(fs.deleteAsync).toHaveBeenCalledWith('file:///stamped-0.8.jpg', { idempotent: true });
  expect(fs.deleteAsync).toHaveBeenCalledWith('file:///stamped-0.7.jpg', { idempotent: true });
});

test('a photo that will not shrink under 100 KB is KEPT at its smallest, never refused (PO 2026-10-04)', async () => {
  const host = autoStampingHost((q) => Math.round((300 - (0.8 - q) * 100) * 1024));
  fs.readAsStringAsync.mockResolvedValue('YWJj');
  const ready = await takeReadyPhoto(
    { takePhoto: async () => ({ uri: 'file:///camera/busy.jpg', width: 3024, height: 4032 }) },
    expoShrink(host),
    { lines: ['x'] },
  );
  const smallest = `file:///stamped-${PHOTO_QUALITY_STEPS[PHOTO_QUALITY_STEPS.length - 1]}.jpg`;
  expect(ready?.localPath).toBe(smallest);
  expect(ready?.overCeiling).toBe(true);
});
