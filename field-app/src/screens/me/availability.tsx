/**
 * Availability — Available · On break · Off duty (requirement 6, FF-45) — held
 * on the handset per technician, and the bridge that puts it in the chip that
 * is always on screen (AD-12, `navigation/ShellStatus.tsx`).
 *
 * The CHOICE is the technician's and is kept here the moment it is made, so
 * the chip, the menu and FF-44 agree at once and the choice survives a
 * restart. TELLING DISPATCH goes through the outbox (FB-033,
 * `availabilityPort.ts`: kind `availability`, carrying the tap's own time),
 * and after each sync the office's answer is laid over it
 * (`applyOfficeStatus`, called from `sync/availability.ts`) — so an office
 * *Unavailable* shows here, and after End shift the chip reads *Off duty*.
 *
 * Going off duty holds nothing back: unsent work still sends (US-FLD-006
 * TC-5) — the tap adds its own item and touches no other.
 */
import { type ReactNode, useCallback, useSyncExternalStore } from 'react';

import { type Availability, ShellStatusProvider, type ShellStatusValue, UNKNOWN_STATUS } from '../../navigation/ShellStatus';
import type { KeyValueStore } from '../../security/prefs';
import { useOptionalSession } from '../../session/SessionProvider';
import { useMeServices } from './services';

/** What the technician may CHOOSE. `unavailable` is the office's word only. */
export type Choosable = Exclude<Availability, 'unavailable'>;
export const AVAILABILITIES: readonly Choosable[] = ['available', 'onBreak', 'offDuty'];
const KNOWN: readonly Availability[] = [...AVAILABILITIES, 'unavailable'];

export interface AvailabilityState {
  value: Availability | null;
  /** When the current value was chosen (FF-44 "On duty since 07:40"). */
  since: string | null;
}

const NONE: AvailabilityState = { value: null, since: null };
const keyOf = (technicianId: string) => `handset.availability.${technicianId}`;

interface Store {
  listeners: Set<() => void>;
  cache: Map<string, AvailabilityState>;
}

const stores = new WeakMap<KeyValueStore, Store>();

function storeOf(prefs: KeyValueStore): Store {
  let s = stores.get(prefs);
  if (!s) {
    s = { listeners: new Set(), cache: new Map() };
    stores.set(prefs, s);
  }
  return s;
}

export function readAvailability(prefs: KeyValueStore, technicianId: string | null): AvailabilityState {
  if (!technicianId) return NONE;
  const store = storeOf(prefs);
  const cached = store.cache.get(technicianId);
  if (cached) return cached;
  let state = NONE;
  try {
    const raw = JSON.parse(prefs.getString(keyOf(technicianId)) ?? 'null') as AvailabilityState | null;
    if (raw && raw.value && (KNOWN as readonly string[]).includes(raw.value)) state = raw;
  } catch {
    state = NONE;
  }
  store.cache.set(technicianId, state);
  return state;
}

const onDuty = (v: Availability | null) => v === 'available' || v === 'onBreak';

function put(prefs: KeyValueStore, technicianId: string, next: AvailabilityState): void {
  prefs.set(keyOf(technicianId), JSON.stringify(next));
  const store = storeOf(prefs);
  store.cache.set(technicianId, next);
  store.listeners.forEach((l) => l());
}

export function writeAvailability(prefs: KeyValueStore, technicianId: string, value: Availability, at: Date): void {
  const current = readAvailability(prefs, technicianId);
  // "Since" is when the technician went on duty: it carries across a break.
  const since = onDuty(current.value) && onDuty(value) ? current.since : at.toISOString();
  put(prefs, technicianId, { value, since });
}

/**
 * FB-033 — the office's answer, read back after a sync, laid over the
 * handset's choice. The same value → nothing moves (the "on duty since" the
 * phone holds stays). A new value takes the server's time when it gave one.
 */
export function applyOfficeStatus(prefs: KeyValueStore, technicianId: string, value: Availability, since: string | null): void {
  const current = readAvailability(prefs, technicianId);
  if (current.value === value) return;
  const kept = onDuty(current.value) && onDuty(value) ? current.since : null;
  put(prefs, technicianId, { value, since: kept ?? since ?? current.since });
}

/** The active technician's availability, live. */
export function useAvailability(technicianId: string | null): [AvailabilityState, (v: Choosable) => void] {
  const { prefs, now } = useMeServices();
  const store = storeOf(prefs);
  const subscribe = useCallback(
    (l: () => void) => {
      store.listeners.add(l);
      return () => store.listeners.delete(l);
    },
    [store],
  );
  const state = useSyncExternalStore(subscribe, () => readAvailability(prefs, technicianId));
  const set = useCallback(
    (v: Choosable) => {
      if (technicianId) writeAvailability(prefs, technicianId, v, now());
    },
    [prefs, technicianId, now],
  );
  return [state, set];
}

export const AVAILABILITY_TONE = { available: 'success', onBreak: 'warning', offDuty: 'neutral', unavailable: 'danger' } as const;

/**
 * The always-on chip's source: the shell status the app already has, with the
 * signed-in technician's availability laid over it. Mounted by App.tsx in
 * place of a bare `ShellStatusProvider`.
 */
export function MeShellStatus({ base = UNKNOWN_STATUS, children }: { base?: ShellStatusValue; children: ReactNode }) {
  const session = useOptionalSession();
  const [state] = useAvailability(session?.snapshot.active?.technicianId ?? null);
  return <ShellStatusProvider value={{ ...base, availability: state.value }}>{children}</ShellStatusProvider>;
}
