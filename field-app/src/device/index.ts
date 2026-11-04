/**
 * THE handset, as one object the app root builds once (integration lane):
 * camera and shrink, scanner, position, dictation, the document viewer, the
 * file picker and the signing pad. Every wave reads its hardware from this —
 * each wave's own port file derives the shape its screens were built against
 * from a `Device` (`readsPortsFrom`, `devicePortsFrom`, `dayLocationFrom`), so
 * there is one camera, one scanner and one position in the app however many
 * waves look at them.
 *
 * `UNWIRED_DEVICE` is what TESTS and previews use; the shipped app builds
 * `nativeDevice()` (`native/index.ts`, `NativeApp.tsx`). Unwired: no native package for any of
 * them is installed (see `ports.ts`), so each refuses, or answers "no fix",
 * in words a screen can show.
 */
import {
  type CameraPort,
  type FilePickerPort,
  type ImageShrinkPort,
  UNAVAILABLE_CAMERA,
  UNAVAILABLE_FILE_PICKER,
  UNAVAILABLE_SHRINK,
} from './photo';
import { type DictationDevice, type DocumentOpener, type LocationDevice, NO_LOCATION, UNWIRED_DICTATION, UNWIRED_DOCUMENTS } from './ports';
import { type ScannerPort, unwiredScanner } from './scanner';
import { type SignaturePort, unwiredSignature } from './signature';

export interface Device {
  camera: CameraPort;
  shrink: ImageShrinkPort;
  scanner: ScannerPort;
  location: LocationDevice;
  dictation: DictationDevice;
  documents: DocumentOpener;
  files: FilePickerPort;
  signature: SignaturePort;
}

export const UNWIRED_DEVICE: Device = {
  camera: UNAVAILABLE_CAMERA,
  shrink: UNAVAILABLE_SHRINK,
  scanner: unwiredScanner,
  location: NO_LOCATION,
  dictation: UNWIRED_DICTATION,
  documents: UNWIRED_DOCUMENTS,
  files: UNAVAILABLE_FILE_PICKER,
  signature: unwiredSignature,
};

export * from './ports';
export * from './photo';
export * from './scanner';
export * from './signature';
export * from './network';
