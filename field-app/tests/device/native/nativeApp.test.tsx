/**
 * The shipped entry: `NativeApp` mounts, and the handset it builds is the
 * real one where a package exists and the honest refusal where it does not.
 */
import { render, screen } from '@testing-library/react-native';

import { UNWIRED_DOCUMENTS, unwiredSignature } from '../../../src/device';
import { DeviceHostController, nativeDevice } from '../../../src/device/native';
import NativeApp from '../../../src/NativeApp';

test('the real handset: camera, shrink, scanner, position, files, the signing pad and the document opener are the native ones', () => {
  const device = nativeDevice(new DeviceHostController());
  expect(device.camera.available).toBe(true);
  expect(device.scanner.available).toBe(true);
  expect(device.scanner.Preview).toBeDefined();
  expect(device.location.last()).toBeNull();
  // FB-031 (DEF-FLD-10805): the shipped handset opens a document through the
  // phone's own app. It read UNWIRED_DOCUMENTS, so every SOP said
  // "Cannot open this file." while every test's fake viewer opened it.
  expect(device.documents).not.toBe(UNWIRED_DOCUMENTS);
  // DEF-FLD-10627: the pad is installed (it read "Signing pad not available").
  expect(device.signature).not.toBe(unwiredSignature);
  expect(device.signature.Pad).not.toBeNull();
  // The jest mock has no on-device recogniser, so dictation refuses — as on such a handset.
  expect(device.dictation.available).toBe(false);
});

test('the shipped app mounts', () => {
  render(<NativeApp />);
  expect(screen.getByText('SMART360 Next Field')).toBeTruthy();
});
