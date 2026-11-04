/**
 * What the day's screens read from, in one context: the open handset store,
 * the clock, and the four PORTS a screen needs that nothing on the branch
 * provides yet. Each port has an honest default — it says it is not wired,
 * never answers with a made-up value.
 *
 *   db         the tenant's store (`openTenantDb`), opened at sign-in. NOT
 *              opened by `App.tsx` today: nothing on the branch opens a store
 *              for the signed-in technician, so the app root must provide it
 *              (reported to the coordinator). With no store every day screen
 *              shows that the day is not on the phone — never an empty day,
 *              because "no jobs" and "not loaded" are different facts.
 *   location   where the handset is. No location package is installed
 *              (`expo-location`); without it distances are not shown and
 *              Home's *Nearest stop* falls back to the next stop in walk order
 *              and says so.
 *   nearby     the server's unassigned work and the claim (`nearbyApi.ts`).
 *   sendNow    the sync engine's push, for *Send now*. Absent → no button.
 *   firstSync  FF-08's loader (`gettingIn/firstSync.ts`).
 *   MapView    the map component behind FF-13 / FF-14 (`mapView.tsx`).
 *   crashes    the telemetry crash capture for the screens' error boundaries.
 *
 * ⚠ The context lives in this wave's folder because the screen waves may not
 * edit `src/db/` or `App.tsx`; it should move to `src/db/` (or `src/session/`)
 * once the coordinator wires the store at sign-in. Every other wave needs the
 * same thing.
 */
import { createContext, type ComponentType, type ReactNode, useContext, useMemo } from 'react';

import { type TenantDb } from '../../db/database';
import type { Device } from '../../device';
import { scoped, type ScopedRunner } from '../../db/scoped';
import { useOptionalSession } from '../../session/SessionProvider';
import type { CrashCapture } from '../../telemetry/crashReporter';
import { type FirstSyncPort } from '../gettingIn/firstSync';
import { type MapViewProps, PlaceholderMapView } from './mapView';
import { type NearbyPort, nearbyNotWired } from './nearbyApi';

export interface Position {
  lat: number;
  lng: number;
}

export interface LocationPort {
  /** The last known fix, or null when there is none (no permission, no fix, no package). */
  current(): Position | null;
}

export const noLocation: LocationPort = { current: () => null };

/** This wave's view of the app's one position (`src/device`): the newest fix held. */
export function dayLocationFrom(device: Pick<Device, 'location'>): LocationPort {
  return {
    current: () => {
      const fix = device.location.last();
      return fix ? { lat: fix.lat, lng: fix.lng } : null;
    },
  };
}

export interface FieldData {
  db: TenantDb | null;
  now: () => Date;
  location: LocationPort;
  nearby: NearbyPort;
  sendNow?: () => Promise<unknown>;
  firstSync?: FirstSyncPort;
  MapView: ComponentType<MapViewProps>;
  /** The telemetry crash capture (T-74), once the app root builds it. */
  crashes?: CrashCapture;
  /**
   * Moves every time a sync run has finished writing the store (DEF-FLD-10359).
   * A day screen that memoises its reads keys them on this, so a job the
   * runtime's OWN run removed (the 15-minute timer, coming back into signal)
   * leaves the list on screen — not only after a pull-to-refresh or a refocus.
   */
  storeVersion?: number;
}

const DEFAULTS: FieldData = {
  db: null,
  now: () => new Date(),
  location: noLocation,
  nearby: nearbyNotWired,
  MapView: PlaceholderMapView,
};

const FieldDataContext = createContext<FieldData>(DEFAULTS);

export function FieldDataProvider(props: { value: Partial<FieldData>; children: ReactNode }) {
  const { value, children } = props;
  const merged = useMemo<FieldData>(() => ({ ...DEFAULTS, ...value }), [value]);
  return <FieldDataContext.Provider value={merged}>{children}</FieldDataContext.Provider>;
}

export function useFieldData(): FieldData {
  return useContext(FieldDataContext);
}

/** The signed-in technician's id, or null (signed out, or no session context). */
export function useTechnicianId(): string | null {
  const session = useOptionalSession();
  if (!session || session.snapshot.phase === 'signedOut') return null;
  return session.snapshot.active?.technicianId ?? null;
}

/**
 * The technician's own rows, through the ONE helper (R133). Null when there
 * is no store or nobody signed in — the screen then shows that, rather than
 * reading someone else's day or an empty one.
 */
export function useScoped(): ScopedRunner | null {
  const { db } = useFieldData();
  const technicianId = useTechnicianId();
  return useMemo(() => (db && technicianId ? scoped(db, technicianId) : null), [db, technicianId]);
}
