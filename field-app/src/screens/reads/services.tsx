/**
 * What every reading screen needs from the app, in one context: the tenant's
 * store, whose readings these are and who is taking them, a clock, ids, the
 * hardware ports, and the act that sends.
 *
 * ⚠ NOTHING ABOVE THE NAVIGATOR PROVIDES THIS YET. `App.tsx` mounts no store
 * and no `ThemeProvider` today (Phase 1 shipped the shell), so a reads route
 * renders its placeholder — with its doors — until the app root mounts
 * `<ThemeProvider>` and `<ReadsServicesProvider>` (see `ReadsScreen.tsx`).
 * That is the coordinator's wiring, reported, not done here.
 *
 * The capture credential's owner (`technicianId`) and the person doing the
 * act (`capturedBy`) are separate on purpose (Security §3).
 */
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import type { TenantDb } from '../../db/database';
import { scoped, type ScopedRunner } from '../../db/scoped';
import type { KeyValueStore } from '../../security/prefs';
import type { CrashCapture } from '../../telemetry/crashReporter';
import type { CameraPort, CameraShot, DictationPort, Fix, LocationPort, ScannerPort } from './ports';
import { attachLatePositions } from './position';
import type { WireFinding, WireFindingOptions } from '../../sync/fieldApi';

export interface ReadsServices {
  db: TenantDb;
  /** Whose readings these are — the scope of every query (R133). */
  technicianId: string;
  /** Who is doing the act, from the capture credential. */
  capturedBy: string;
  /** The reader's name as the photo stamp burns it (R94). */
  readerName: string;
  clock: { now(): Date };
  newId(): string;
  prefs: KeyValueStore;
  scanner: ScannerPort;
  camera: CameraPort;
  location: LocationPort;
  dictation: DictationPort;
  crash: CrashCapture;
  /** Send what is waiting now (the sync engine's act; RW-01, RW-26). */
  sendNow(): Promise<void>;
  /** Download every assigned route (R104). `null` while no server door exists. */
  downloadRoutes: (() => Promise<void>) | null;
  /** RW-25: tell the server the route is turned in. Queued on the handset and
   *  sent with the next sync, so no signal never loses it. Absent → the route
   *  is marked on the phone only. */
  turnInRoute?: (routeId: string) => void;
  /** BR-WRK-067 — a finding's online doors: RW-21's lists, the finding as it
   *  stands, and *Create work order* for one no rule took. Absent → offline
   *  build: the finding still sends; creating a job waits for signal. */
  findings?: FindingsPort;
}

export interface FindingsPort {
  options(): Promise<WireFindingOptions>;
  get(key: string): Promise<WireFinding>;
  createWorkOrder(key: string, body: { template_id: string; priority_id?: string }): Promise<WireFinding>;
}

/** A reading being entered, carried between RW-09, RW-14, RW-15 and RW-16. */
export interface ReadDraft {
  value: string;
  photos: CameraShot[];
  remark: string | null;
  remarkSource: 'voice' | 'typed' | null;
  /** RW-16: the first try, kept whole when the reader reads again (nothing is overwritten). */
  firstTry: { value: string; at: string } | null;
  /** How the meter was identified — `scan` once RW-11 matched it. */
  identifiedBy: 'scan' | 'listed' | 'typed';
}

export const EMPTY_DRAFT: ReadDraft = {
  value: '',
  photos: [],
  remark: null,
  remarkSource: null,
  firstTry: null,
  identifiedBy: 'listed',
};

/** The reader's choices on RW-29. Device-level, remembered in the encrypted prefs. */
export interface ReadingSettings {
  keypad: 'normal' | 'large' | 'largest';
  order: 'nearest' | 'walk';
  confirmEach: boolean;
  scanFirst: boolean;
  // `photosOnMobile` was removed 2026-10-28 (DEF-FLD-10640): it was saved here and read by
  // nothing, so it could never send or hold a photo. The one photo switch is FF-51's
  // *Photos on wi-fi only* (`screens/me/prefs.ts` `photosWifiOnly`), shown on RW-29 too.
}

export const DEFAULT_SETTINGS: ReadingSettings = {
  keypad: 'large',
  order: 'nearest', // R75: nearest first is the default
  confirmEach: false,
  scanFirst: false,
};

export const SETTINGS_KEY = 'reads.settings';

export function loadSettings(prefs: KeyValueStore): ReadingSettings {
  try {
    const raw = prefs.getString(SETTINGS_KEY);
    return raw ? { ...DEFAULT_SETTINGS, ...(JSON.parse(raw) as Partial<ReadingSettings>) } : DEFAULT_SETTINGS;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

interface ContextValue {
  services: ReadsServices;
  s: ScopedRunner;
  /** Bumped after every write, so open screens read again. */
  version: number;
  bump(): void;
  draft(readId: string): ReadDraft;
  setDraft(readId: string, next: ReadDraft): void;
  clearDraft(readId: string): void;
  settings: ReadingSettings;
  setSettings(next: ReadingSettings): void;
  /** The reader's position: refreshed on demand, and LIVE from the watch
   *  (FB-003 — the camera's stamp updates when a fix arrives). */
  here: Fix | null;
  refreshHere(): Promise<void>;
}

const Ctx = createContext<ContextValue | null>(null);

export function ReadsServicesProvider({ value, children }: { value: ReadsServices; children: ReactNode }) {
  const [version, setVersion] = useState(0);
  const drafts = useRef(new Map<string, ReadDraft>());
  const [settings, setSettingsState] = useState<ReadingSettings>(() => loadSettings(value.prefs));
  const [here, setHere] = useState<ContextValue['here']>(null);
  const bump = useCallback(() => setVersion((v) => v + 1), []);
  // FB-003 (PO 2026-10-27): every fix the handset gets is shown at once, and
  // given — as its own fact — to any reading or route photograph saved in the
  // last 5 minutes without one (`position.ts`).
  const onFix = useCallback(
    (fix: Fix) => {
      setHere(fix);
      try {
        const attached = attachLatePositions(value.db, { technicianId: value.technicianId, capturedBy: value.capturedBy }, fix, {
          newId: () => value.newId(),
          clock: value.clock,
        });
        if (attached > 0) bump();
      } catch {
        // A position is evidence, never a reason to fail the screen.
      }
    },
    [value, bump],
  );
  const refreshHere = useCallback(async () => {
    const fix = await value.location.current();
    if (fix) onFix(fix);
    else setHere(null);
  }, [value.location, onFix]);
  useEffect(() => {
    void refreshHere();
  }, [refreshHere]);
  useEffect(() => value.location.subscribe?.(onFix), [value.location, onFix]);
  const ctx = useMemo<ContextValue>(
    () => ({
      services: value,
      s: scoped(value.db, value.technicianId),
      version,
      bump,
      draft: (id) => drafts.current.get(id) ?? EMPTY_DRAFT,
      // A draft is not the store: setting one re-renders nothing by itself.
      // The screen that set it holds its own state; the next screen reads it
      // when it comes into view.
      setDraft: (id, next) => {
        drafts.current.set(id, next);
      },
      clearDraft: (id) => {
        drafts.current.delete(id);
      },
      settings,
      setSettings: (next) => {
        setSettingsState(next);
        value.prefs.set(SETTINGS_KEY, JSON.stringify(next));
      },
      here,
      refreshHere,
    }),
    [value, version, bump, settings, here, refreshHere],
  );
  return <Ctx.Provider value={ctx}>{children}</Ctx.Provider>;
}

/** The reading services, or null when the app root has not mounted them. */
export function useOptionalReads(): ContextValue | null {
  return useContext(Ctx);
}

export function useReads(): ContextValue {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useReads outside ReadsServicesProvider');
  return ctx;
}
