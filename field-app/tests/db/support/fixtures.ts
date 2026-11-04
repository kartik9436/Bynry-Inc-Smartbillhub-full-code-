/** Shared test fixtures: a fresh tenant store, a hand-driven clock, ids. */
import { openTenantDb, type TenantDb } from '../../../src/db/database';
import type { DriverFactory } from '../../../src/db/driver';
import { memoryFactory } from './nodeDriver';

export class FakeClock {
  constructor(private t: number = Date.parse('2026-10-21T08:00:00.000Z')) {}
  now(): Date {
    return new Date(this.t);
  }
  iso(): string {
    return new Date(this.t).toISOString();
  }
  advance(ms: number): void {
    this.t += ms;
  }
  advanceDays(days: number): void {
    this.t += days * 24 * 60 * 60 * 1000;
  }
}

export function idSource(prefix = 'id'): () => string {
  let n = 0;
  return () => `${prefix}-${String(++n).padStart(6, '0')}`;
}

export function openStore(
  tenant = 'north',
  factory: DriverFactory = memoryFactory(),
  clock: FakeClock = new FakeClock(),
): TenantDb {
  return openTenantDb(factory, tenant, { now: () => clock.iso() });
}

/** Deterministic "jitter": always the middle of the band. */
export const steadyRandom = (): number => 0.5;

/** An in-memory file store: which photo files exist on the "disk". */
export class MemoryFiles {
  readonly paths = new Set<string>();
  readonly deleted: string[] = [];
  failDeleteFor = new Set<string>();
  add(path: string): void {
    this.paths.add(path);
  }
  async exists(path: string): Promise<boolean> {
    return this.paths.has(path);
  }
  async delete(path: string): Promise<void> {
    if (this.failDeleteFor.has(path)) throw new Error(`cannot delete ${path}`);
    this.paths.delete(path);
    this.deleted.push(path);
  }
}
