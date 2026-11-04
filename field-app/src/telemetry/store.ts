/**
 * Storage for the telemetry queue, the crash file and the flag cache.
 *
 * Synchronous on purpose (T-73: "written to disk at crash time"). A fatal
 * JavaScript error gives the handler no chance to await anything, so the crash
 * report must be on disk before the handler returns. MMKV writes synchronously
 * and survives the process dying; that is why it is used here rather than the
 * SQLite store, whose writes are async — and why telemetry does not share the
 * work database at all: the third queue never contends with the outbox for a
 * write lock (R67).
 *
 * Every read and write is wrapped: a storage fault is telemetry's problem and
 * must never become the technician's (R67).
 */
import type { KeyValueStore } from './types';

export function createMemoryStore(seed: Record<string, string> = {}): KeyValueStore & {
  dump(): Record<string, string>;
} {
  const data = new Map<string, string>(Object.entries(seed));
  return {
    getString: (k) => data.get(k),
    set: (k, v) => void data.set(k, v),
    delete: (k) => void data.delete(k),
    dump: () => Object.fromEntries(data),
  };
}

/** The handset store. Loaded lazily so tests and tooling never touch the native module. */
export function createMmkvStore(id = 'telemetry'): KeyValueStore {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { MMKV } = require('react-native-mmkv') as typeof import('react-native-mmkv');
  const mmkv = new MMKV({ id });
  return {
    getString: (k) => mmkv.getString(k),
    set: (k, v) => mmkv.set(k, v),
    delete: (k) => mmkv.delete(k),
  };
}

export function readJson<T>(store: KeyValueStore, key: string, fallback: T): T {
  try {
    const raw = store.getString(key);
    if (raw === undefined) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeJson(store: KeyValueStore, key: string, value: unknown): boolean {
  try {
    store.set(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}
