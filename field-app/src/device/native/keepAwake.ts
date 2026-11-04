/**
 * *Keep screen on* (FF-51, `PREF.KEEP_AWAKE`) — `expo-keep-awake`.
 *
 * The setting is read from the handset's preferences and followed LIVE: the
 * store is wrapped (`watchedStore`) so a change on FF-51 takes effect at once,
 * not at the next start. It holds the screen on for the whole app while it is
 * in front; the platform releases it when the app goes to the background.
 * Off by default (prefs.ts) — a phone that never sleeps is a flat battery by
 * lunchtime.
 */
import { activateKeepAwakeAsync, deactivateKeepAwake } from 'expo-keep-awake';

import { PREF } from '../../screens/me/prefs';
import type { KeyValueStore } from '../../security/prefs';

export const KEEP_AWAKE_TAG = 'field-app.keep-awake';

/** A store that says when a key changes. Everything else passes straight through. */
export interface WatchedStore extends KeyValueStore {
  watch(listener: (key: string) => void): () => void;
}

export function watchedStore(inner: KeyValueStore): WatchedStore {
  const listeners = new Set<(key: string) => void>();
  const tell = (key: string) => {
    for (const l of [...listeners]) l(key);
  };
  return {
    getString: (key) => inner.getString(key),
    set(key, value) {
      inner.set(key, value);
      tell(key);
    },
    delete(key) {
      inner.delete(key);
      tell(key);
    },
    watch(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

export function keepAwakeOn(store: KeyValueStore): boolean {
  return store.getString(PREF.KEEP_AWAKE) === '1';
}

/** Follows the setting; returns the stop. */
export function followKeepAwake(store: WatchedStore): () => void {
  let on = false;
  const release = () => {
    void Promise.resolve()
      .then(() => deactivateKeepAwake(KEEP_AWAKE_TAG))
      .catch(() => undefined);
  };
  const apply = () => {
    const want = keepAwakeOn(store);
    if (want === on) return;
    on = want;
    if (want) void activateKeepAwakeAsync(KEEP_AWAKE_TAG).catch(() => undefined);
    else release();
  };
  apply();
  const unwatch = store.watch((key) => {
    if (key === PREF.KEEP_AWAKE) apply();
  });
  return () => {
    unwatch();
    if (on) release();
    on = false;
  };
}
