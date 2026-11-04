/**
 * @jest-environment node
 *
 * The photograph size rule (`BR-WRK-047`, PO 2026-09-04 / 2026-10-04): the
 * phone compresses to the 70–100 KB band — binary KB — and NEVER refuses a
 * photograph for its size: what will not get under the ceiling is kept at its
 * smallest and sent (*"you cannot reject the photo - that will drop the
 * data"*). The band is one constant (`PHOTO_BYTES`), questioned against the
 * design's 300 KB; these tests pin the SIGNED figure so moving it is seen.
 *
 * Proved red (law 7): with `compressToBand` changed to throw when no step gets
 * under the ceiling (the 2026-09-05 behaviour the PO overruled), *"keeps the
 * smallest and never refuses"* failed with `Error: … over the ceiling`.
 */
import {
  CameraUnavailableError,
  compressToBand,
  PHOTO_BYTES,
  PHOTO_LONG_SIDE_PX,
  PHOTO_QUALITY_STEPS,
  takeReadyPhoto,
  UNAVAILABLE_CAMERA,
} from '../../../src/screens/theJob/camera';
import { FakeCamera, FakeShrink } from './fakes';

const KB = 1024;
const STAMP = { lines: ['20 Oct 2026 · 09:18', '30.2651, -97.7494 · ±4m', 'D. Ortiz · WO-4822 · Silver Creek Water'] };
const SHOT = { uri: 'file:///camera/raw.jpg', width: 4032, height: 3024 };

test('the band is the signed one, in binary kilobytes', () => {
  expect(PHOTO_BYTES).toEqual({ target: 70 * 1024, ceiling: 100 * 1024 });
  expect(PHOTO_LONG_SIDE_PX).toBe(1600);
});

test('stops at the first quality step that lands under the ceiling, and discards nothing it keeps', async () => {
  const shrink = new FakeShrink();
  shrink.reset([240 * KB, 130 * KB, 92 * KB, 60 * KB]);
  const ready = await compressToBand(SHOT, shrink, STAMP);
  expect(shrink.calls.map((c) => c.quality)).toEqual([0.8, 0.7, 0.6]);
  expect(ready.bytes).toBe(92 * KB);
  expect(ready.overCeiling).toBe(false);
  expect(ready.localPath).toMatch(/q0\.6/);
  expect(ready.sha256).toBe(`sha-of-${ready.localPath}`);
  // the two larger attempts are thrown away; the kept file is not
  expect(shrink.discarded).toHaveLength(2);
  expect(shrink.discarded).not.toContain(ready.localPath);
  // every step resizes the long side and burns the stamp in
  expect(shrink.calls.every((c) => c.longSide === 1600 && c.stamp === STAMP.lines)).toBe(true);
});

test('a photograph that will not get under the ceiling is KEPT at its smallest, never refused', async () => {
  const shrink = new FakeShrink();
  shrink.reset([400 * KB, 300 * KB, 250 * KB, 180 * KB, 150 * KB, 130 * KB]);
  const ready = await compressToBand(SHOT, shrink, STAMP);
  expect(shrink.calls.map((c) => c.quality)).toEqual([...PHOTO_QUALITY_STEPS]);
  expect(ready.bytes).toBe(130 * KB);
  expect(ready.overCeiling).toBe(true);
  expect(shrink.discarded).toHaveLength(PHOTO_QUALITY_STEPS.length - 1);
});

test('backing out of the camera is not a photograph', async () => {
  const camera = new FakeCamera();
  camera.next = null;
  expect(await takeReadyPhoto(camera, new FakeShrink(), STAMP)).toBeNull();
});

test('this build has no camera, and says so rather than pretending', async () => {
  await expect(UNAVAILABLE_CAMERA.takePhoto()).rejects.toBeInstanceOf(CameraUnavailableError);
});
