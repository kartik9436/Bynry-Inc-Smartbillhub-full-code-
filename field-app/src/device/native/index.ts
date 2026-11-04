/**
 * THE REAL HANDSET — the `Device` the shipped app builds once
 * (`NativeApp.tsx`), from the native packages the dependency lane installed:
 *
 *   camera     expo-camera, through the device host's viewfinder      (camera.ts)
 *   shrink     expo-image-manipulator + react-native-view-shot stamp (camera.ts)
 *   scanner    expo-camera's barcode reader                          (scanner.ts)
 *   location   expo-location, best fix wins                          (location.ts)
 *   dictation  expo-speech-recognition, on-device only               (dictation.ts)
 *   files      expo-document-picker                                  (files.ts)
 *
 *   signature  react-native-signature-canvas on react-native-webview, the
 *              mark written as a PNG and carried as a photo   (signature.tsx)
 *              — DEF-FLD-10627, PO 2026-10-27: install the drawing pad now.
 *   documents  the phone's own app, through the operating system's
 *              *Open with…*: expo-intent-launcher on Android, expo-sharing
 *              on iOS                                           (documents.ts)
 *              — FB-031, PO 2026-10-31 ruling B (DEF-FLD-10805).
 *
 * The tests keep using `UNWIRED_DEVICE` and the fakes; nothing here is imported
 * by a screen.
 */
import type { Device } from '../index';
import { expoCamera, expoShrink } from './camera';
import { expoDictation } from './dictation';
import { osDocumentOpener } from './documents';
import { expoFilePicker } from './files';
import type { DeviceHostController } from './host';
import { expoLocation } from './location';
import { expoScanner } from './scanner';
import { canvasSignature } from './signature';

export function nativeDevice(host: DeviceHostController): Device {
  return {
    camera: expoCamera(host),
    shrink: expoShrink(host),
    scanner: expoScanner(host),
    location: expoLocation(),
    dictation: expoDictation(),
    documents: osDocumentOpener(),
    files: expoFilePicker(),
    signature: canvasSignature(),
  };
}

export { DeviceHostController } from './host';
export { DeviceHost } from './DeviceHost';
