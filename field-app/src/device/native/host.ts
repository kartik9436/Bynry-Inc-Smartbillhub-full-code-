/**
 * The DEVICE HOST's controller — what the real camera, scanner and stamp need
 * that a plain function cannot do on its own: draw something.
 *
 * `expo-camera` is a VIEW (`CameraView`), not a function, so "take a photo"
 * means putting a full-screen viewfinder up and waiting for the shutter; and
 * burning the stamp into the pixels (R94) with `react-native-view-shot` means
 * laying the photograph and its stamp out in a view and capturing that view.
 * The ports are functions (`takePhoto()`, `start()`, `shrink()`), so they post
 * a REQUEST here and `DeviceHost.tsx` — mounted once at the app root, inside
 * the theme and the words — draws it and answers.
 *
 * Pure TypeScript and no native module, so every rule in it is proved in Node:
 *   - one camera request at a time; a second one while the first is open is
 *     refused rather than queued behind a viewfinder the technician cannot see;
 *   - a scan session draws its own full-screen viewfinder ONLY when no screen
 *     has an inline preview mounted (FF-38 draws one; the reading screens do not);
 *   - with no host mounted, every request is refused in words — a photo is never
 *     "taken" by something that could not show a viewfinder.
 */
import type { RawShot } from '../photo';
import { CameraUnavailableError } from '../photo';
import type { ScanFormat, ScannedCode } from '../scanner';

export interface CameraRequest {
  readonly id: number;
  resolve(shot: RawShot | null): void;
  reject(err: unknown): void;
}

export interface ScanSession {
  readonly id: number;
  readonly formats: readonly ScanFormat[];
  onCode(code: ScannedCode): void;
  /** The technician closed the full-screen viewfinder without a code. */
  onClose?: () => void;
}

export interface StampJob {
  readonly id: number;
  /** The already-resized photograph. */
  readonly uri: string;
  readonly width: number;
  readonly height: number;
  readonly lines: readonly string[];
  /** JPEG quality, 0..1. */
  readonly quality: number;
  resolve(out: { uri: string; width: number; height: number }): void;
  reject(err: unknown): void;
}

export class HostNotMountedError extends Error {
  constructor(what: string) {
    super(`${what} needs the device host, and it is not mounted`);
    this.name = 'HostNotMountedError';
  }
}

export class CameraBusyError extends Error {
  constructor() {
    super('the camera is already open');
    this.name = 'CameraBusyError';
  }
}

/** The same code read again inside this window is the same scan, not a second one. */
export const SCAN_REPEAT_MS = 1500;

export class DeviceHostController {
  private nextId = 1;
  private listeners = new Set<() => void>();
  private hosts = 0;
  private previews = 0;
  private lastCode: { value: string; at: number } | null = null;

  /** Bumped on every change, for `useSyncExternalStore`. */
  version = 0;
  camera: CameraRequest | null = null;
  scan: ScanSession | null = null;
  torch = false;
  stamps: StampJob[] = [];

  constructor(private readonly now: () => number = () => Date.now()) {}

  // ── the host and the inline previews say they are there ─────────────────
  hostMounted(): () => void {
    this.hosts += 1;
    this.emit();
    return () => {
      this.hosts -= 1;
      this.emit();
    };
  }

  get hasHost(): boolean {
    return this.hosts > 0;
  }

  previewMounted(): () => void {
    this.previews += 1;
    this.emit();
    return () => {
      this.previews -= 1;
      this.emit();
    };
  }

  /** The host draws its own viewfinder only when a scan is on and no screen draws one inline. */
  get fullScreenScan(): boolean {
    return this.scan !== null && this.previews === 0;
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(): void {
    this.version += 1;
    for (const l of [...this.listeners]) l();
  }

  // ── the inline camera (DEF-FLD-10630, FB-002) ───────────────────────────
  /**
   * A screen showing the camera's live view (RW-14) registers its shutter
   * here; while it is mounted, `requestPhoto()` takes the picture from THAT
   * view and the full-screen viewfinder never opens — the reader already
   * sees the camera, and a second viewfinder over it is the black panel FB-002
   * reported. Returns the unregister function.
   */
  cameraPreviewMounted(shutter: () => Promise<RawShot | null>): () => void {
    this.inlineShutter = shutter;
    this.emit();
    return () => {
      if (this.inlineShutter === shutter) {
        this.inlineShutter = null;
        this.emit();
      }
    };
  }

  private inlineShutter: (() => Promise<RawShot | null>) | null = null;
  private inlineBusy = false;

  // ── the camera ───────────────────────────────────────────────────────────
  requestPhoto(): Promise<RawShot | null> {
    const inline = this.inlineShutter;
    if (inline) {
      if (this.inlineBusy || this.camera) return Promise.reject(new CameraBusyError());
      this.inlineBusy = true;
      return inline().finally(() => {
        this.inlineBusy = false;
      });
    }
    if (!this.hasHost) return Promise.reject(new CameraUnavailableError());
    if (this.camera) return Promise.reject(new CameraBusyError());
    return new Promise<RawShot | null>((resolve, reject) => {
      const id = this.nextId++;
      const done = () => {
        if (this.camera?.id === id) {
          this.camera = null;
          this.emit();
        }
      };
      this.camera = {
        id,
        resolve: (shot) => {
          done();
          resolve(shot);
        },
        reject: (err) => {
          done();
          reject(err);
        },
      };
      this.emit();
    });
  }

  // ── the scanner ──────────────────────────────────────────────────────────
  startScan(formats: readonly ScanFormat[], onCode: (code: ScannedCode) => void, onClose?: () => void): () => void {
    const id = this.nextId++;
    this.lastCode = null;
    this.scan = { id, formats, onCode, onClose };
    this.emit();
    return () => {
      if (this.scan?.id === id) {
        this.scan = null;
        this.torch = false;
        this.emit();
      }
    };
  }

  /** A code the camera read. Repeats of the same value inside `SCAN_REPEAT_MS` are dropped. */
  codeRead(code: ScannedCode): void {
    const session = this.scan;
    if (!session || !session.formats.includes(code.format)) return;
    const at = this.now();
    if (this.lastCode && this.lastCode.value === code.value && at - this.lastCode.at < SCAN_REPEAT_MS) return;
    this.lastCode = { value: code.value, at };
    session.onCode(code);
  }

  /** The full-screen viewfinder's Close. */
  closeScan(): void {
    const session = this.scan;
    if (!session) return;
    this.scan = null;
    this.torch = false;
    this.emit();
    session.onClose?.();
  }

  setTorch(on: boolean): void {
    this.torch = on;
    this.emit();
  }

  // ── the stamp ────────────────────────────────────────────────────────────
  requestStamp(job: Omit<StampJob, 'id' | 'resolve' | 'reject'>): Promise<{ uri: string; width: number; height: number }> {
    if (!this.hasHost) return Promise.reject(new HostNotMountedError('burning the stamp in'));
    return new Promise((resolve, reject) => {
      const id = this.nextId++;
      const finish = () => {
        this.stamps = this.stamps.filter((s) => s.id !== id);
        this.emit();
      };
      this.stamps = [
        ...this.stamps,
        {
          ...job,
          id,
          resolve: (out) => {
            finish();
            resolve(out);
          },
          reject: (err) => {
            finish();
            reject(err);
          },
        },
      ];
      this.emit();
    });
  }
}
