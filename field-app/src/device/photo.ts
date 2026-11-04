/**
 * Taking a photograph: the camera, the shrink, the hash — behind ports, so the
 * screens and their tests never touch a native module. ONE set for the whole
 * app (moved here from `screens/theJob/camera.ts` in the integration lane;
 * that file re-exports it, and every other wave's camera is a view of these —
 * `device/views.ts`).
 *
 * ⚠ **WIRED IN THE NATIVE BUILD** (`native/camera.ts`, 2026-10-21): `expo-camera`,
 * `expo-image-manipulator` and `react-native-view-shot`. What follows is the
 * reasoning from before the packages landed, kept for the refusal path. The real ports need `expo-camera`
 * (the viewfinder and the shutter), `expo-image-manipulator` (resize and JPEG
 * quality) and a way to burn the stamp into the pixels (R94 — e.g.
 * `@shopify/react-native-skia` or `react-native-view-shot`). Adding them is the
 * coordinator's dependency call, so until then `UNAVAILABLE_CAMERA` refuses in
 * words and the screens say the camera is not available — nothing pretends a
 * photograph was taken.
 *
 * WHAT IS BUILT HERE AND PROVED IN NODE: the size rule. `BR-WRK-047` (PO
 * 2026-09-04, re-read 2026-10-04): the phone compresses at capture to the
 * **70–100 KB** band — binary kilobytes, `100 * 1024` (decision log 2026-09-05
 * `BR-WRK-047a`) — resizing the long side to 1,600 px and stepping JPEG
 * quality down until the bytes fit. And (PO 2026-10-04): *"you cannot reject
 * the photo - that will drop the data"* — so a photograph that will not get
 * under the ceiling is KEPT at its smallest and sent; the server finishes the
 * job. This module never refuses a capture for its size.
 *
 * ⚠ **THE BAND IS ONE CONSTANT, AND IT IS QUESTIONED.** The design's Data page
 * draws photographs at ~300 KB. Whether that replaces the signed 70–100 KB is
 * a question put to the PO; until it is answered the SIGNED figure is built,
 * and moving it is a change to `PHOTO_BYTES` and nothing else.
 *
 * A photograph is a FILE PATH on disk and a row, never bytes in the database
 * (R52). Nothing here returns image bytes.
 */
import type { ComponentType } from 'react';

/** BR-WRK-047: the band the compressor aims for, in bytes (binary KB). */
export const PHOTO_BYTES = { target: 70 * 1024, ceiling: 100 * 1024 } as const;

/** The long side the compressor resizes to first (`BR-WRK-047`, the mechanism). */
export const PHOTO_LONG_SIDE_PX = 1600;

/** JPEG quality steps, best first, as the web field app's `compressPhoto` walks them. */
export const PHOTO_QUALITY_STEPS = [0.8, 0.7, 0.6, 0.5, 0.4, 0.3] as const;

/** What the viewfinder returns: a file the camera wrote. */
export interface RawShot {
  uri: string;
  width: number;
  height: number;
}

/** The stamp burned into the pixels (R94): date, time, position ± accuracy, who, which order. */
export interface PhotoStamp {
  lines: string[];
}

export interface CameraPort {
  /** False when this build has no camera; a screen then says so. Absent = available. */
  readonly available?: boolean;
  /**
   * The camera's LIVE view, for a screen that shows the camera inline
   * (RW-14, DEF-FLD-10630). While one is mounted, `takePhoto()` takes the
   * picture from it and no full-screen viewfinder opens. Absent when the
   * build draws only its own viewfinder (or has no camera).
   */
  readonly Preview?: ComponentType;
  /** Opens the camera; `null` when the technician backs out. Camera only — no gallery (R93). */
  takePhoto(): Promise<RawShot | null>;
}

export interface ShrinkResult {
  uri: string;
  bytes: number;
  width: number;
  height: number;
}

export interface ImageShrinkPort {
  /** Resize the long side to `longSide`, burn the stamp in, write a JPEG at `quality`. */
  shrink(uri: string, opts: { longSide: number; quality: number; stamp: PhotoStamp }): Promise<ShrinkResult>;
  /** SHA-256 of the file's bytes, hex — declared with the data before the bytes travel (R123). */
  sha256(uri: string): Promise<string>;
  /** A file the pipeline no longer needs (a larger attempt). */
  discard(uri: string): Promise<void>;
}

export class CameraUnavailableError extends Error {
  constructor() {
    super('no camera module is installed in this build (expo-camera, expo-image-manipulator)');
    this.name = 'CameraUnavailableError';
  }
}

/** The ports as this build ships them: refusing, in words, until the packages land. */
export const UNAVAILABLE_CAMERA: CameraPort = {
  available: false,
  takePhoto: () => Promise.reject(new CameraUnavailableError()),
};

export const UNAVAILABLE_SHRINK: ImageShrinkPort = {
  shrink: () => Promise.reject(new CameraUnavailableError()),
  sha256: () => Promise.reject(new CameraUnavailableError()),
  discard: () => Promise.resolve(),
};

/** A photograph ready to be captured through the outbox. */
export interface ReadyPhoto {
  localPath: string;
  sha256: string;
  bytes: number;
  width: number;
  height: number;
  /** True when no step got it under the ceiling — kept anyway, the server shrinks it (PO 2026-10-04). */
  overCeiling: boolean;
}

/**
 * Shrink a shot into the band. Walks the quality steps from the best; stops at
 * the first result at or under the ceiling. If none gets there, the SMALLEST
 * result is kept — never refused. Every other attempt's file is discarded.
 */
export async function compressToBand(shot: RawShot, shrink: ImageShrinkPort, stamp: PhotoStamp): Promise<ReadyPhoto> {
  let best: ShrinkResult | null = null;
  for (const quality of PHOTO_QUALITY_STEPS) {
    const out = await shrink.shrink(shot.uri, { longSide: PHOTO_LONG_SIDE_PX, quality, stamp });
    if (best === null || out.bytes < best.bytes) {
      if (best !== null) await shrink.discard(best.uri);
      best = out;
    } else {
      await shrink.discard(out.uri);
    }
    if (out.bytes <= PHOTO_BYTES.ceiling) break;
  }
  if (best === null) throw new Error('the quality ladder is empty');
  const sha256 = await shrink.sha256(best.uri);
  return {
    localPath: best.uri,
    sha256,
    bytes: best.bytes,
    width: best.width,
    height: best.height,
    overCeiling: best.bytes > PHOTO_BYTES.ceiling,
  };
}

/** Camera → shrink → hash. `null` when the technician backed out. */
export async function takeReadyPhoto(
  camera: CameraPort,
  shrink: ImageShrinkPort,
  stamp: PhotoStamp,
): Promise<ReadyPhoto | null> {
  const shot = await camera.takePhoto();
  if (!shot) return null;
  return compressToBand(shot, shrink, stamp);
}

/** A document file picked from the phone (FF-60 *A file*, R108). */
export interface PickedFile {
  uri: string;
  name: string;
  bytes: number;
  mimeType: string | null;
}

export interface FilePickerPort {
  pick(): Promise<PickedFile | null>;
}

export class FilePickerUnavailableError extends Error {
  constructor() {
    super('no file picker is installed in this build (expo-document-picker)');
    this.name = 'FilePickerUnavailableError';
  }
}

/** The refusal for builds without a picker (tests); the native build uses `native/files.ts`. */
export const UNAVAILABLE_FILE_PICKER: FilePickerPort = {
  pick: () => Promise.reject(new FilePickerUnavailableError()),
};
