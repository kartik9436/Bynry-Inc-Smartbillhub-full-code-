/**
 * The scanner the raise screens read through. The port itself is the app's
 * (`src/device/scanner.ts`, since the integration lane); this file re-exports
 * it and keeps the fake the tests drive.
 */
import type { ScanFormat, ScannedCode, ScannerPort } from '../../device/scanner';

export * from '../../device/scanner';

/** A scanner a test drives: `present()` is a code coming into view. */
export class FakeScanner implements ScannerPort {
  readonly available = true;
  torch = false;
  formats: readonly ScanFormat[] = [];
  private listener: ((code: ScannedCode) => void) | null = null;
  starts = 0;

  start(formats: readonly ScanFormat[], onCode: (code: ScannedCode) => void): () => void {
    this.starts += 1;
    this.formats = formats;
    this.listener = onCode;
    return () => {
      if (this.listener === onCode) this.listener = null;
    };
  }

  setTorch(on: boolean): void {
    this.torch = on;
  }

  /** A code comes into view. Ignored when its format is not being read. */
  present(code: ScannedCode): boolean {
    if (!this.listener || !this.formats.includes(code.format)) return false;
    this.listener(code);
    return true;
  }
}
