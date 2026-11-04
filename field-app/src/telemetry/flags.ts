/**
 * Feature flags with cached defaults — T-75, R71, AD-18.
 *
 * An app-store review takes days, so a held feature is released by a flag rather
 * than a build. Every flag has a DEFAULT in code; a read returns, in order:
 *   1. the last value fetched from the server and cached on the handset, or
 *   2. the default, when nothing has ever been fetched.
 * It never waits on the network and never throws, so a handset with no signal
 * behaves the same way twice (R71). A failed refresh keeps the cache it had.
 *
 * The registry of flags is NOT defined here: each feature declares its own flag
 * and default where it is built. This module only guarantees the behaviour.
 * A value of the wrong type, or for a flag this build does not declare, is ignored.
 */
import { readJson, writeJson } from './store';
import type { KeyValueStore } from './types';
import { withTimeout } from './offline';

export type FlagValue = boolean | string;
export type FlagDefaults = Readonly<Record<string, FlagValue>>;

export type FlagFetcher = () => Promise<Record<string, unknown> | undefined>;

export interface FeatureFlags<D extends FlagDefaults> {
  get<K extends keyof D & string>(key: K): D[K];
  /** Where the value came from — for tests and a debug screen, never for a technician. */
  source(key: keyof D & string): 'cache' | 'default';
  refresh(fetch: FlagFetcher, timeoutMs?: number): Promise<'updated' | 'failed'>;
}

const FLAGS_KEY = 'telemetry.flags.v1';

export function createFeatureFlags<D extends FlagDefaults>(
  defaults: D,
  store: KeyValueStore,
): FeatureFlags<D> {
  let cache = readJson<Record<string, FlagValue>>(store, FLAGS_KEY, {});
  if (!cache || typeof cache !== 'object' || Array.isArray(cache)) cache = {};

  const valid = (key: string, value: unknown): value is FlagValue => {
    if (!Object.prototype.hasOwnProperty.call(defaults, key)) return false;
    return typeof value === typeof defaults[key];
  };

  return {
    get(key) {
      const cached = cache[key];
      return (valid(key, cached) ? cached : defaults[key]) as D[typeof key];
    },
    source(key) {
      return valid(key, cache[key]) ? 'cache' : 'default';
    },
    async refresh(fetch, timeoutMs = 10_000) {
      try {
        const remote = await withTimeout(fetch, timeoutMs);
        if (!remote || typeof remote !== 'object') return 'failed';
        const next: Record<string, FlagValue> = { ...cache };
        for (const key of Object.keys(defaults)) {
          const v = remote[key];
          if (valid(key, v)) next[key] = v;
        }
        cache = next;
        writeJson(store, FLAGS_KEY, cache);
        return 'updated';
      } catch {
        return 'failed';
      }
    },
  };
}
