/**
 * The handset's preferences behind FF-51 Settings and FF-52 Notifications —
 * kept in the encrypted MMKV store (AD-17: *"MMKV (theme, language)"*;
 * US-FLD-033 §5: preferences survive a restart). Per HANDSET, not per
 * technician, the same choice the language already makes (I18nProvider): the
 * design's Settings has one of each row, and on a shared van tablet the
 * setting is the van's until somebody changes it.
 *
 * Every key is spelt here once. Other lanes read some of them:
 *   - `NEARBY_RADIUS` → FF-11 Nearby (R34, default 2 mi);
 *   - `PHOTOS_WIFI_ONLY` → the photo upload phase, read through
 *     `photosWifiOnly()` by the sync engine AND the screens (default OFF —
 *     photos go on mobile data and wi-fi alike);
 *   - `KEEP_AWAKE` → the job screens (`device/native/keepAwake.ts` follows it live in the native build).
 *
 * ⚠ **R54 IS SUPERSEDED (PO 2026-10-28, FB-015, option A).** It read
 * *"Photographs wait for wi-fi unless the technician says otherwise"*, default
 * off on mobile data. The PO: *"it should work on mobile and wifi both"*, then
 * *"go with A"*. Photos now upload on ANY connection; the one switch left is
 * *Photos on wi-fi only*, OFF by default. The old key
 * (`handset.sync.photosOnMobileData`) is deleted by `migrateHandsetPrefs` and
 * never read: every phone moves to the new default whatever it held.
 *
 * ⚠ **ONE READER FOR THE PHOTO SWITCH (DEF-FLD-10640).** The runtime read the
 * old key as `=== 'true'` while `writeFlag` stores `'1'`, so the switch never
 * reached the engine and photos waited for wi-fi with it ON. Everything that
 * asks *may photos go on mobile data?* calls `photosWifiOnly(store)`.
 *
 * Every write goes through `writePref`/`writeFlag`, which tell the open
 * screens (`subscribePrefs`), so a screen already mounted — Sync beside
 * Settings on the tablet — never shows a switch's old value.
 */
import type { KeyValueStore } from '../../security/prefs';
import type { ThemeMode } from '../../theme';

export const PREF = {
  THEME_MODE: 'handset.theme.mode',
  BIGGER_TEXT: 'handset.theme.biggerText',
  DATE_FORMAT: 'handset.format.date',
  CLOCK: 'handset.format.clock',
  UNITS: 'handset.format.units',
  KEEP_AWAKE: 'handset.screen.keepAwake',
  NEARBY_RADIUS: 'handset.nearby.radiusMi',
  PHOTOS_WIFI_ONLY: 'handset.sync.photosWifiOnly',
  NOTIFY: 'handset.notify.',
} as const;

export type DateFormat = 'dayMonthYear' | 'monthDayYear' | 'iso';
export type ClockFormat = 'h24' | 'h12';
export type Units = 'miles' | 'kilometres';
export type NearbyRadius = '1' | '2' | '5' | '10';

export const DATE_FORMATS: readonly DateFormat[] = ['dayMonthYear', 'monthDayYear', 'iso'];
export const CLOCKS: readonly ClockFormat[] = ['h24', 'h12'];
export const UNITS: readonly Units[] = ['miles', 'kilometres'];
export const NEARBY_RADII: readonly NearbyRadius[] = ['1', '2', '5', '10'];
const THEME_MODES: readonly ThemeMode[] = ['automatic', 'light', 'dark', 'sunlight'];

function pick<T extends string>(store: KeyValueStore, key: string, allowed: readonly T[], fallback: T): T {
  const v = store.getString(key);
  return v != null && (allowed as readonly string[]).includes(v) ? (v as T) : fallback;
}

function flag(store: KeyValueStore, key: string, fallback: boolean): boolean {
  const v = store.getString(key);
  return v == null ? fallback : v === '1';
}

export function savedThemeMode(store: KeyValueStore): ThemeMode {
  return pick(store, PREF.THEME_MODE, THEME_MODES, 'automatic');
}

export function savedBiggerText(store: KeyValueStore): boolean {
  return flag(store, PREF.BIGGER_TEXT, false);
}

/** The FF-52 rows. Every one defaults ON: an alert nobody opted into still reaches the technician. */
export const NOTIFY_KEYS = [
  'emergencyVibrate',
  'newJobVibrate',
  'scheduleChange',
  'dispatchMessages',
  'dispatchBadge',
  'quietOffShift',
] as const;
export type NotifyKey = (typeof NOTIFY_KEYS)[number];

export interface HandsetPrefs {
  dateFormat: DateFormat;
  clock: ClockFormat;
  units: Units;
  keepAwake: boolean;
  nearbyRadius: NearbyRadius;
  /** *Photos on wi-fi only* — off by default (PO 2026-10-28, supersedes R54). */
  photosWifiOnly: boolean;
  notify: Record<NotifyKey, boolean>;
}

export function readPrefs(store: KeyValueStore): HandsetPrefs {
  const notify = {} as Record<NotifyKey, boolean>;
  for (const k of NOTIFY_KEYS) notify[k] = flag(store, PREF.NOTIFY + k, true);
  return {
    dateFormat: pick(store, PREF.DATE_FORMAT, DATE_FORMATS, 'dayMonthYear'),
    clock: pick(store, PREF.CLOCK, CLOCKS, 'h24'),
    units: pick(store, PREF.UNITS, UNITS, 'miles'),
    keepAwake: flag(store, PREF.KEEP_AWAKE, false),
    // R34: the default radius is 2 miles.
    nearbyRadius: pick(store, PREF.NEARBY_RADIUS, NEARBY_RADII, '2'),
    photosWifiOnly: photosWifiOnly(store),
    notify,
  };
}

/** May photographs wait for wi-fi? The ONE reader of the switch — engine and screens alike. Default no. */
export function photosWifiOnly(store: KeyValueStore): boolean {
  return flag(store, PREF.PHOTOS_WIFI_ONLY, false);
}

/** The key R54's switch lived under. Deleted on start, never read (PO 2026-10-28). */
export const RETIRED_PHOTOS_ON_MOBILE_DATA = 'handset.sync.photosOnMobileData';

/** Once per start: drop the retired photo switch, so every phone takes the new default. */
export function migrateHandsetPrefs(store: KeyValueStore): void {
  if (store.getString(RETIRED_PHOTOS_ON_MOBILE_DATA) !== undefined) store.delete(RETIRED_PHOTOS_ON_MOBILE_DATA);
}

type Listener = () => void;
const listeners = new WeakMap<KeyValueStore, Set<Listener>>();

/** Told after every write through `writePref`/`writeFlag` on this store. Returns the unsubscribe. */
export function subscribePrefs(store: KeyValueStore, listener: Listener): () => void {
  let set = listeners.get(store);
  if (!set) {
    set = new Set();
    listeners.set(store, set);
  }
  set.add(listener);
  return () => {
    set.delete(listener);
  };
}

export function writePref(store: KeyValueStore, key: string, value: string): void {
  store.set(key, value);
  for (const l of [...(listeners.get(store) ?? [])]) l();
}

export function writeFlag(store: KeyValueStore, key: string, on: boolean): void {
  writePref(store, key, on ? '1' : '0');
}
