/**
 * The camera and the shrink, faked: a shot is a file name, and each quality
 * step returns the size the test says it would. Nothing here is an image.
 */
import type { CameraPort, ImageShrinkPort, RawShot, ShrinkResult } from '../../../src/screens/theJob/camera';

export class FakeCamera implements CameraPort {
  shots = 0;
  /** `null` = the technician backed out. */
  next: RawShot | null | 'fail' = { uri: 'file:///camera/raw.jpg', width: 4032, height: 3024 };
  async takePhoto(): Promise<RawShot | null> {
    if (this.next === 'fail') throw new Error('camera broke');
    this.shots += 1;
    return this.next ? { ...this.next, uri: `file:///camera/raw-${this.shots}.jpg` } : null;
  }
}

export class FakeShrink implements ImageShrinkPort {
  /** Bytes for each successive quality step; the last repeats. */
  sizes: number[] = [84 * 1024];
  calls: Array<{ quality: number; longSide: number; stamp: string[] }> = [];
  discarded: string[] = [];
  private n = 0;

  async shrink(uri: string, opts: { longSide: number; quality: number; stamp: { lines: string[] } }): Promise<ShrinkResult> {
    const bytes = this.sizes[Math.min(this.calls.length, this.sizes.length - 1)] ?? 0;
    this.calls.push({ quality: opts.quality, longSide: opts.longSide, stamp: opts.stamp.lines });
    this.n += 1;
    return { uri: `${uri}.q${opts.quality}.${this.n}.jpg`, bytes, width: 1600, height: 1200 };
  }

  async sha256(uri: string): Promise<string> {
    return `sha-of-${uri}`;
  }

  async discard(uri: string): Promise<void> {
    this.discarded.push(uri);
  }

  reset(sizes: number[]): void {
    this.sizes = sizes;
    this.calls = [];
    this.discarded = [];
  }
}
