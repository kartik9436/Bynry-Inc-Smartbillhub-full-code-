/**
 * The handset abilities these screens need and the app does not have yet.
 * Each is a PORT with an unwired default that refuses naming what is missing,
 * and a fake the tests drive. None of them is invented business: they are the
 * camera, the microphone, the position and a document viewer.
 *
 *   CameraPort      — no camera package is installed (expo-camera /
 *                     expo-image-picker). FF-30's photo, FF-33's door hanger.
 *   DictationPort   — no speech-to-text package is installed. R38: dictation
 *                     beside every note (FF-30, FF-32, FF-37).
 *   LocationPort    — expo-location is not installed. FF-37 carries the
 *                     technician's position (requirement 11).
 *   DocumentOpener  — FF-28 opens a document from the phone's own copy
 *                     (R-docs: "open offline"); the native build hands it to
 *                     the phone's own app (FB-031).
 *
 * Since the integration lane these are VIEWS of the app's one `Device`
 * (`src/device/`): `devicePortsFrom(device, language)` builds them from the
 * same camera, microphone, position and viewer every other wave reads.
 */
import { type Device, type DocumentOpener, type TakenPhoto, takeReadyPhoto, UNWIRED_DOCUMENTS } from '../../device';
import type { CaptureLocation } from '../../sync/outbox';
import { FieldGapError } from './money';

export type { DocumentOpener, TakenPhoto };

export interface CameraPort {
  /** Opens the camera; resolves null when the technician backs out. */
  take(): Promise<TakenPhoto | null>;
}

export interface DictationPort {
  /** Listens once and resolves the words heard, or '' for nothing. */
  listen(): Promise<string>;
}

export interface LocationPort {
  /** The best fix now, or null when there is none. */
  current(): Promise<CaptureLocation | null>;
}


export interface DevicePorts {
  camera: CameraPort;
  dictation: DictationPort;
  location: LocationPort;
  documents: DocumentOpener;
}

export const unwiredDevicePorts: DevicePorts = {
  camera: { take: () => Promise.reject(new FieldGapError('camera package', 'expo-camera is not installed')) },
  dictation: { listen: () => Promise.reject(new FieldGapError('speech package', 'no speech-to-text is installed')) },
  location: { current: () => Promise.resolve(null) },
  documents: { open: () => Promise.reject(new FieldGapError('document viewer', 'this build has no document opener')) },
};

/** Fakes the tests drive: queue what the camera and microphone will return. */
export function fakeDevicePorts(init: {
  photos?: TakenPhoto[];
  words?: string[];
  location?: CaptureLocation | null;
} = {}): DevicePorts & { opened: string[] } {
  const photos = [...(init.photos ?? [])];
  const words = [...(init.words ?? [])];
  const opened: string[] = [];
  return {
    camera: { take: () => Promise.resolve(photos.shift() ?? null) },
    dictation: { listen: () => Promise.resolve(words.shift() ?? '') },
    location: { current: () => Promise.resolve(init.location ?? null) },
    documents: {
      open: (path) => {
        opened.push(path);
        return Promise.resolve();
      },
    },
    opened,
  };
}

/** These screens' ports, from the app's one handset (`src/device`). The photo
 *  carries the stamp the camera burns in (R94): when, and where if known. */
export function devicePortsFrom(device: Device, language: () => string): DevicePorts {
  // Where the handset has no such ability, this wave's own refusal (which the
  // screens already turn into a sentence) rather than the device's.
  return {
    camera: device.camera.available === false ? unwiredDevicePorts.camera : {
      take: async () => {
        const fix = device.location.last();
        const lines = [new Date().toISOString(), ...(fix ? [`${fix.lat.toFixed(5)}, ${fix.lng.toFixed(5)} ±${Math.round(fix.accuracy_m)} m`] : [])];
        const ready = await takeReadyPhoto(device.camera, device.shrink, { lines });
        return ready ? { localPath: ready.localPath, sha256: ready.sha256, bytes: ready.bytes, width: ready.width, height: ready.height } : null;
      },
    },
    dictation: device.dictation.available
      ? { listen: async () => (await device.dictation.listen(language())) ?? '' }
      : unwiredDevicePorts.dictation,
    location: { current: () => device.location.current() },
    documents: device.documents === UNWIRED_DOCUMENTS ? unwiredDevicePorts.documents : device.documents,
  };
}
