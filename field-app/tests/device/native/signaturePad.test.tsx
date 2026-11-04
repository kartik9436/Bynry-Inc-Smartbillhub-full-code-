/**
 * DEF-FLD-10627 — the real signing pad: the shipped handset HAS one, and its
 * ink comes out as a PNG on disk with the sha256 the server's link checks.
 */
import { act, render, screen } from '@testing-library/react-native';
import { createHash } from 'crypto';
import * as FileSystem from 'expo-file-system';
import * as Canvas from 'react-native-signature-canvas';

import { DeviceHostController, nativeDevice } from '../../../src/device/native';
import { canvasSignature, writeSignature } from '../../../src/device/native/signature';

jest.mock('expo-file-system', () => ({
  EncodingType: { Base64: 'base64', UTF8: 'utf8' },
  cacheDirectory: 'file:///cache/',
  writeAsStringAsync: jest.fn(async () => undefined),
}));

jest.mock('expo-crypto', () => ({
  CryptoDigestAlgorithm: { SHA256: 'SHA-256' },
  digest: jest.fn(async (_alg: string, data: Uint8Array) => {
    const h = (require('crypto') as typeof import('crypto')).createHash('sha256').update(Buffer.from(data)).digest();
    return h.buffer.slice(h.byteOffset, h.byteOffset + h.byteLength);
  }),
}));

const pad = (Canvas as unknown as { __mock: { dataUrl: string | null; clearSignature: jest.Mock; last: { onBegin?: () => void } | null } }).__mock;
const fs = FileSystem as jest.Mocked<typeof FileSystem>;
const PNG_B64 = Buffer.from('a tiny png, as far as this test cares').toString('base64');

beforeEach(() => {
  pad.dataUrl = null;
  pad.clearSignature.mockClear();
  fs.writeAsStringAsync.mockClear();
});

test('the shipped handset has a signing pad (it read "Signing pad not available")', () => {
  const device = nativeDevice(new DeviceHostController());
  expect(device.signature.Pad).not.toBeNull();
});

test('ink exports as a PNG file whose sha256 is the bytes written', async () => {
  const port = canvasSignature();
  const Pad = port.Pad!;
  const onInk = jest.fn();
  render(<Pad onInk={onInk} clearToken={0} label="Sign below" />);
  expect(screen.getByLabelText('Sign below')).toBeTruthy();
  act(() => pad.last?.onBegin?.());
  expect(onInk).toHaveBeenLastCalledWith(true);

  pad.dataUrl = `data:image/png;base64,${PNG_B64}`;
  const image = await port.exportImage();

  const bytes = Buffer.from(PNG_B64, 'base64');
  expect(image).toEqual({
    localPath: expect.stringMatching(/^file:\/\/\/cache\/signature-\d+\.png$/),
    sha256: createHash('sha256').update(bytes).digest('hex'),
    bytes: bytes.length,
  });
  expect(fs.writeAsStringAsync).toHaveBeenCalledWith(image!.localPath, PNG_B64, { encoding: 'base64' });
});

test('an empty pad exports nothing, and Clear wipes it', async () => {
  const port = canvasSignature();
  const Pad = port.Pad!;
  const onInk = jest.fn();
  const view = render(<Pad onInk={onInk} clearToken={0} label="Sign below" />);
  expect(await port.exportImage()).toBeNull();
  expect(fs.writeAsStringAsync).not.toHaveBeenCalled();

  view.rerender(<Pad onInk={onInk} clearToken={1} label="Sign below" />);
  expect(pad.clearSignature).toHaveBeenCalledTimes(1);
  expect(onInk).toHaveBeenLastCalledWith(false);
});

test('no pad on screen: nothing to export', async () => {
  expect(await canvasSignature().exportImage()).toBeNull();
  expect(await writeSignature('data:image/png;base64,')).toBeNull();
});
