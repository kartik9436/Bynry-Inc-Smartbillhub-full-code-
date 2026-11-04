/**
 * The device host's controller — the rules the real camera, scanner and
 * stamp lean on, proved in Node with no native module.
 */
import { CameraUnavailableError } from '../../../src/device/photo';
import { CameraBusyError, DeviceHostController, HostNotMountedError, SCAN_REPEAT_MS } from '../../../src/device/native/host';

describe('the camera request', () => {
  test('with no host mounted the camera refuses in words — no photo is "taken" without a viewfinder', async () => {
    const host = new DeviceHostController();
    await expect(host.requestPhoto()).rejects.toBeInstanceOf(CameraUnavailableError);
  });

  test('one request at a time; the shot resolves it and clears it', async () => {
    const host = new DeviceHostController();
    host.hostMounted();
    const first = host.requestPhoto();
    await expect(host.requestPhoto()).rejects.toBeInstanceOf(CameraBusyError);
    host.camera?.resolve({ uri: 'file:///a.jpg', width: 10, height: 20 });
    await expect(first).resolves.toEqual({ uri: 'file:///a.jpg', width: 10, height: 20 });
    expect(host.camera).toBeNull();
  });

  test('backing out resolves null', async () => {
    const host = new DeviceHostController();
    host.hostMounted();
    const p = host.requestPhoto();
    host.camera?.resolve(null);
    await expect(p).resolves.toBeNull();
  });
});

describe('the inline camera (DEF-FLD-10630, FB-002)', () => {
  test('a screen showing the live camera takes the photo from it — no full-screen viewfinder opens', async () => {
    const host = new DeviceHostController();
    host.hostMounted();
    const unmount = host.cameraPreviewMounted(() => Promise.resolve({ uri: 'file:///live.jpg', width: 4, height: 3 }));
    await expect(host.requestPhoto()).resolves.toEqual({ uri: 'file:///live.jpg', width: 4, height: 3 });
    expect(host.camera).toBeNull();
    unmount();
    // Gone again: the full-screen viewfinder is back.
    const p = host.requestPhoto();
    expect(host.camera).not.toBeNull();
    host.camera?.resolve(null);
    await expect(p).resolves.toBeNull();
  });

  test('one shutter at a time on the inline camera too', async () => {
    const host = new DeviceHostController();
    let release: (v: null) => void = () => undefined;
    host.cameraPreviewMounted(() => new Promise((r) => (release = r)));
    const first = host.requestPhoto();
    await expect(host.requestPhoto()).rejects.toBeInstanceOf(CameraBusyError);
    release(null);
    await expect(first).resolves.toBeNull();
  });
});

describe('the scan session', () => {
  test('the host draws its own viewfinder only when no screen draws a preview', () => {
    const host = new DeviceHostController();
    const stop = host.startScan(['qr'], () => undefined);
    expect(host.fullScreenScan).toBe(true);
    const unmount = host.previewMounted();
    expect(host.fullScreenScan).toBe(false);
    unmount();
    expect(host.fullScreenScan).toBe(true);
    stop();
    expect(host.fullScreenScan).toBe(false);
  });

  test('a code of a format not asked for is ignored; the same code again within the window is one scan', () => {
    let t = 1_000;
    const host = new DeviceHostController(() => t);
    const seen: string[] = [];
    host.startScan(['code128'], (c) => seen.push(c.value));
    host.codeRead({ value: 'X1', format: 'qr' });
    host.codeRead({ value: 'M-90118', format: 'code128' });
    t += SCAN_REPEAT_MS - 1;
    host.codeRead({ value: 'M-90118', format: 'code128' });
    t += 2;
    host.codeRead({ value: 'M-90118', format: 'code128' });
    host.codeRead({ value: 'M-90119', format: 'code128' });
    expect(seen).toEqual(['M-90118', 'M-90118', 'M-90119']);
  });

  test('Close ends the session and tells the caller; the torch goes off with it', () => {
    const host = new DeviceHostController();
    const onClose = jest.fn();
    host.startScan(['qr'], () => undefined, onClose);
    host.setTorch(true);
    host.closeScan();
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(host.scan).toBeNull();
    expect(host.torch).toBe(false);
  });

  test("an old session's stop does not end a newer one", () => {
    const host = new DeviceHostController();
    const stopOld = host.startScan(['qr'], () => undefined);
    host.startScan(['code39'], () => undefined);
    stopOld();
    expect(host.scan?.formats).toEqual(['code39']);
  });
});

describe('the stamp job', () => {
  test('refused without a host — a photograph is never sent unstamped (R94)', async () => {
    const host = new DeviceHostController();
    await expect(host.requestStamp({ uri: 'a', width: 1, height: 1, lines: [], quality: 0.8 })).rejects.toBeInstanceOf(HostNotMountedError);
  });

  test('queued for the host and cleared when answered', async () => {
    const host = new DeviceHostController();
    host.hostMounted();
    const v = host.version;
    const p = host.requestStamp({ uri: 'file:///r.jpg', width: 1600, height: 1200, lines: ['2026-10-21T09:00:00Z'], quality: 0.7 });
    expect(host.version).toBeGreaterThan(v);
    expect(host.stamps).toHaveLength(1);
    expect(host.stamps[0]).toMatchObject({ quality: 0.7, lines: ['2026-10-21T09:00:00Z'] });
    host.stamps[0]?.resolve({ uri: 'file:///s.jpg', width: 1600, height: 1200 });
    await expect(p).resolves.toEqual({ uri: 'file:///s.jpg', width: 1600, height: 1200 });
    expect(host.stamps).toHaveLength(0);
  });
});
