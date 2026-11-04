/**
 * THE app's one data provider (integration lane). Below the session and above
 * the navigator, it:
 *
 *   1. OPENS the signed-in technician's tenant store at sign-in
 *      (`field-<tenant>.sqlite`, `db/storeHolder.ts`) and CLOSES it when the
 *      handset is signed out. Closing deletes nothing (R60, R64).
 *   1b. RUNS THE RETENTION PURGE (`db/purge.ts`) ONCE PER APP START for each
 *      tenant store it opens — before the first sync of that start, and never
 *      again until the next start, so it can never run mid-upload (R63). A
 *      sync asked for while it runs waits for it. A purge that fails is
 *      recorded and the day goes on: not purging loses nothing (R60). Wired by
 *      the proof lane (T-49): until then nothing called it.
 *   2. MOUNTS THE SYNC ENGINE (`sync/engine.ts`): every 15 minutes while
 *      connected, when the app comes forward if the last run was over 5
 *      minutes ago, when the connection comes back, and on *Send now* (Data
 *      tab §6). Each item travels under its captor's own capture credential
 *      (`security/captureTokens.ts`). A route turned in on RW-25 is queued on
 *      the handset and told to the server with the next run.
 *   3. REPORTS ITS WORK to telemetry's gate (`gate.reportWork`), so analytics
 *      never competes with captured work for the connection, and feeds the
 *      always-on sync number (AD-12) through the one shell status.
 *   4. FEEDS EVERY WAVE from that one store and the one handset
 *      (`src/device`): the day (`theDay/fieldData`), the job (`theJob/JobPort`),
 *      on-site/closing/raise (`onSite/fieldData`), the reading route
 *      (`reads/services`) and "me" (`me/services`). Each wave keeps the port
 *      it was built against; this file adapts, it does not rewrite a screen.
 *
 *   5. BOUNDS EVERY RUN (DEF-FLD-10624, decision log 2026-10-27 *"start A to
 *      F"*). Every step has a time limit (`sync/runLimits.ts`) — the network
 *      check included, whose silence reads *unknown, try anyway* and never
 *      *no signal* — so a hung step ends the run and the next *Sync now*
 *      starts a fresh one instead of joining a dead one. A run with a signal
 *      first RENEWS THE ACCESS TOKEN when its hour has run out (Security §1:
 *      *"one hour, refreshed whenever there is a signal"*): nothing called
 *      `SessionManager.refresh()` until then, so an hour after sign-in every
 *      call was refused ON THE PHONE and the server saw no request at all. A
 *      MANUAL *Sync now* clears the technician's backoff first; automatic
 *      runs keep it. Each run answers with why nothing went
 *      (`sync/syncReason.ts`), which FF-50 shows.
 *
 * With nobody signed in — or a store that would not open — no wave provider
 * is mounted with data, and every screen shows the state it already has for
 * "not on this phone". The server's online doors (`sync/fieldApi.ts`) reach
 * the waves through `fieldDoors.ts` — nearby and claim, alerts, money,
 * reopen, the asset search (lane INTEGRATE-2). Server routes that still do
 * not exist stay their waves' own *not wired* ports (van, profile, time-off
 * requests…). The week, End shift and Submit the day are wired from the store
 * (`me/shiftsPorts.ts`, CR-193-BRC10), and the week is downloaded after each
 * run and kept, so FF-46 reads it with no signal.
 */
import { type ComponentType, createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { TenantDb } from '../db/database';
import { purgeOnAppStart } from '../db/purge';
import * as outboxQ from '../db/queries/outbox';
import * as photoQ from '../db/queries/photo';
import * as routeReadQ from '../db/queries/routeRead';
import * as walkQ from '../db/queries/readsWalk';
import { scoped } from '../db/scoped';
import { type StoreHolder, storeOutboxPort } from '../db/storeHolder';
import type { Device, NetworkPort } from '../device';
import { type ShellStatusValue, UNKNOWN_STATUS } from '../navigation/ShellStatus';
import { engineFirstSync } from '../screens/gettingIn/firstSync';
import { applyOfficeStatus, MeShellStatus } from '../screens/me/availability';
import { createAvailabilityPort } from '../screens/me/availabilityPort';
import { createDbMeData } from '../screens/me/dbData';
import { migrateHandsetPrefs, photosWifiOnly } from '../screens/me/prefs';
import { MeServicesProvider, NO_DATA, notWiredServices } from '../screens/me/services';
import { createShiftsPort, createTimesheetPort } from '../screens/me/shiftsPorts';
import { setWaveCrashCapture } from '../screens/onSite/common';
import { FieldDataProvider as SiteDataProvider } from '../screens/onSite/fieldData';
import { unwiredMoneyPort } from '../screens/onSite/money';
import { devicePortsFrom } from '../screens/onSite/ports';
import { readsPortsFrom } from '../screens/reads/ports';
import { ReadsServicesProvider } from '../screens/reads/services';
import { dayLocationFrom, FieldDataProvider as DayDataProvider } from '../screens/theDay/fieldData';
import { JobPortProvider } from '../screens/theJob/JobPort';
import { asFieldApi } from '../sync/fieldApi';
import type { CaptureTokens } from '../sync/outbox';
import type { FileStore, NetworkKind } from '../sync/photos';
import { downloadRoutes, type RoutesApi } from '../sync/routes';
import { onRouteWake } from '../sync/routeWake';
import { asShiftsApi, downloadWeek } from '../sync/shifts';
import { asAvailabilityApi, readBack } from '../sync/availability';
import { SyncEngine } from '../sync/engine';
import { DEFAULT_RUN_LIMITS, type RunLimits, StepTimeLimitError, within } from '../sync/runLimits';
import { reasonOfResult, type SyncRunOutcome } from '../sync/syncReason';
import { TransportError, type Transport } from '../sync/transport';
import { appUpdate, type UpdateSignal } from '../release/appUpdate';
import { captureTokensOf } from '../security/captureTokens';
import { asSettingsApi, type SettingsApi } from '../security/pinning';
import type { KeyValueStore } from '../security/prefs';
import type { CrashReporter, Telemetry } from '../telemetry';
import type { MapViewProps } from '../screens/theDay/mapView';
import { httpAlertsPort, httpAssetFinder, httpMoneyPort, httpNearbyPort, httpReopenPort, nearbyFixFrom, storeMoneyMemory } from './fieldDoors';
import { useOptionalSession } from './SessionProvider';
import { RemotePhotoProvider, type RemotePhotoPort } from '../components/RecordPhoto';
import type { SessionManager } from './sessionManager';

/** Data tab §6: *"Every 15 minutes while on shift and connected"*. */
export const SYNC_EVERY_MS = 15 * 60 * 1000;
/** Data tab §6: *"Foreground, if the last pull was over 5 minutes ago"*. */
export const FOREGROUND_AFTER_MS = 5 * 60 * 1000;

export interface AppStateLike {
  addEventListener(type: 'change', listener: (state: string) => void): { remove(): void };
}

export interface FieldRuntimeDeps {
  holder: StoreHolder;
  session: SessionManager;
  prefs: KeyValueStore;
  device: Device;
  network: NetworkPort;
  /** The server for one tenant; the access token is read at each call. */
  transportFor(tenant: string, accessToken: () => string | null): Transport & RoutesApi;
  files: FileStore;
  telemetry: Telemetry;
  newId(): string;
  now?: () => Date;
  appState?: AppStateLike;
  /** Overrides the 15-minute period (tests). */
  syncEveryMs?: number;
  /** Overrides the capture credentials (tests). */
  tokens?: CaptureTokens;
  /** The real map (native build); the day screens' placeholder otherwise. */
  MapView?: ComponentType<MapViewProps>;
  /** Crashlytics (native build). Crash files and events are sent after each sync run, when the work gate is clear. */
  crashReporter?: CrashReporter;
  /** The "server refused this build" signal (default: the app's one `appUpdate`). */
  update?: UpdateSignal;
  /** Certificate pinning (`OQ-FLD-12797`): the server's key list is read after each sync. */
  pinning?: PinRefresher;
  /** Overrides the run's time limits (tests); `DEFAULT_RUN_LIMITS` otherwise. */
  limits?: Partial<RunLimits>;
}

/** The slice of `PinningController` the runtime calls. */
export interface PinRefresher {
  refresh(api: SettingsApi): Promise<unknown>;
}

export interface FieldRuntimeValue {
  db: TenantDb | null;
  technicianId: string | null;
  /**
   * Push, upload, pull — now. Rejects when no store is open. `manual` — the
   * technician pressed *Sync now*: their backoff is cleared first, and a run
   * already going that was NOT manual is waited out rather than joined.
   */
  syncNow(opts?: { manual?: boolean }): Promise<SyncRunOutcome>;
  status: ShellStatusValue;
  /** Why the store did not open, when it did not. */
  openError: string | null;
}

const RuntimeContext = createContext<FieldRuntimeValue | null>(null);

export function useFieldRuntime(): FieldRuntimeValue | null {
  return useContext(RuntimeContext);
}

const TURN_INS = (technicianId: string) => `reads.turnIns.pending.${technicianId}`;

interface PendingTurnIn {
  routeId: string;
  key: string;
  at: string;
}

function readTurnIns(prefs: KeyValueStore, technicianId: string): PendingTurnIn[] {
  try {
    const raw = prefs.getString(TURN_INS(technicianId));
    return raw ? (JSON.parse(raw) as PendingTurnIn[]) : [];
  } catch {
    return [];
  }
}

function writeTurnIns(prefs: KeyValueStore, technicianId: string, rows: PendingTurnIn[]): void {
  try {
    if (rows.length) prefs.set(TURN_INS(technicianId), JSON.stringify(rows));
    else prefs.delete(TURN_INS(technicianId));
  } catch {
    /* the route is still marked turned in on the phone */
  }
}

export function FieldRuntime({ deps, children }: { deps: FieldRuntimeDeps; children: ReactNode }) {
  const { i18n } = useTranslation();
  const session = useOptionalSession();
  const snap = session?.snapshot;
  const signedIn = !!snap && snap.phase !== 'signedOut' && !!snap.active;
  const active = signedIn ? (snap?.active ?? null) : null;
  const tenant = active?.tenant ?? null;
  const technicianId = active?.technicianId ?? null;
  const now = useMemo(() => deps.now ?? (() => new Date()), [deps.now]);
  const clock = useMemo(() => ({ now }), [now]);

  // ── 1. the store: open at sign-in, closed at sign-out ─────────────────────
  const [db, setDb] = useState<TenantDb | null>(deps.holder.current);
  const [openError, setOpenError] = useState<string | null>(null);
  useEffect(() => deps.holder.subscribe(setDb), [deps.holder]);
  // PO 2026-10-28 (FB-015): R54's switch is retired; every phone takes the new default.
  useEffect(() => migrateHandsetPrefs(deps.prefs), [deps.prefs]);
  useEffect(() => {
    if (!tenant) {
      deps.holder.close();
      return;
    }
    try {
      deps.holder.open(tenant);
      setOpenError(null);
    } catch (err) {
      setOpenError(err instanceof Error ? err.message : String(err));
    }
  }, [deps.holder, tenant]);
  useEffect(() => () => deps.holder.close(), [deps.holder]);

  // ── 1b. the retention purge: once per app start per store, before any sync ──
  const purges = useRef(new Map<string, Promise<void>>());
  const purgeOnce = useCallback(
    (store: TenantDb): Promise<void> => {
      let done = purges.current.get(store.tenant);
      if (!done) {
        done = purgeOnAppStart(store, { now: now(), files: deps.files }).then(
          () => undefined,
          (error: unknown) => deps.telemetry.crashes.record({ error, fatal: false }),
        );
        purges.current.set(store.tenant, done);
      }
      return done;
    },
    [now, deps.files, deps.telemetry],
  );
  useEffect(() => {
    if (db) void purgeOnce(db);
  }, [db, purgeOnce]);

  // ── 2. the engine ──────────────────────────────────────────────────────────
  const transport = useMemo(
    () => (tenant ? deps.transportFor(tenant, () => deps.session.courierAccessToken()) : null),
    [deps, tenant],
  );
  const tokens = useMemo(() => deps.tokens ?? captureTokensOf(deps.session, { now: () => now().getTime() }), [deps.tokens, deps.session, now]);
  const limits = useMemo<RunLimits>(() => ({ ...DEFAULT_RUN_LIMITS, ...deps.limits }), [deps.limits]);
  const engine = useMemo(
    () => (db && transport ? new SyncEngine({ db, transport, files: deps.files, tokens, clock, runLimitMs: limits.runMs }) : null),
    [db, transport, deps.files, tokens, clock, limits.runMs],
  );
  const outboxPort = useMemo(() => storeOutboxPort(deps.holder), [deps.holder]);
  // The online doors, when the transport has them (the app's `HttpTransport` does).
  const api = useMemo(() => asFieldApi(transport), [transport]);
  const doors = useMemo(
    () =>
      api
        ? {
            nearby: httpNearbyPort(api, nearbyFixFrom(deps.device.location)),
            // FB-023 F1 — the last figure per job is kept on the handset.
            money: httpMoneyPort(api, db ? storeMoneyMemory(db, now) : null),
            reopen: httpReopenPort(api),
            assets: httpAssetFinder(api),
          }
        : null,
    [api, deps.device, db, now],
  );

  // ── 3. what the run reports ────────────────────────────────────────────────
  const [status, setStatus] = useState<ShellStatusValue>(UNKNOWN_STATUS);
  const network = useRef<NetworkKind>('none');
  // FB-030 — a record's photograph whose file has left the phone loads ON TAP
  // from the server (own work only, never stored), when there is a signal.
  const photoPort = useMemo<RemotePhotoPort | null>(() => {
    const src = transport as unknown as { photoSource?: RemotePhotoPort['source'] } | null;
    const photoSource = src?.photoSource?.bind(src);
    if (!photoSource) return null;
    return { online: () => network.current !== 'none', source: (kind, photoId) => photoSource(kind, photoId) };
  }, [transport]);
  const report = useCallback(
    async (syncing: boolean) => {
      const online = network.current !== 'none';
      try {
        const counts = await outboxPort.unsentCounts();
        const items = counts.reduce((n, c) => n + c.items, 0);
        const photos = counts.reduce((n, c) => n + c.photos, 0);
        deps.telemetry.gate.reportWork({ outbox: items, photos, syncing, online });
        const mine = counts.find((c) => c.technicianId === technicianId);
        setStatus((s) => ({
          ...s,
          syncPending: technicianId ? (mine ? mine.items + mine.photos : 0) : null,
          connection: online ? 'online' : 'offline',
        }));
      } catch {
        // No store: the gate does not know the queue, so it stays shut ("unreported").
        setStatus((s) => ({ ...s, syncPending: null, connection: online ? 'online' : 'offline' }));
      }
    },
    [outboxPort, deps.telemetry, technicianId],
  );

  const lastRun = useRef(0);
  // DEF-FLD-10359: bumped when a sync run has finished, so the day screens re-read.
  const [storeVersion, setStoreVersion] = useState(0);
  const running = useRef<{ promise: Promise<SyncRunOutcome>; manual: boolean } | null>(null);
  const sendTurnIns = useCallback(async () => {
    if (!db || !transport || !technicianId) return;
    const pending = readTurnIns(deps.prefs, technicianId);
    if (!pending.length) return;
    const s = scoped(db, technicianId);
    const left: PendingTurnIn[] = [];
    for (const p of pending) {
      try {
        const t = walkQ.tally(s, p.routeId);
        await transport.turnIn(p.routeId, {
          key: p.key,
          keys: routeReadQ.captureKeysFor(s, p.routeId),
          counts: { done: t.done, could_not: t.could_not, total: t.total },
          captured_at: p.at,
        });
      } catch (err) {
        // No signal or no door: kept, and told with the next run.
        if (!(err instanceof TransportError)) throw err;
        left.push(p);
      }
    }
    writeTurnIns(deps.prefs, technicianId, left);
  }, [db, transport, technicianId, deps.prefs]);

  const syncNow = useCallback(
    async (opts?: { manual?: boolean }): Promise<SyncRunOutcome> => {
      if (!engine) throw new Error('no handset store is open');
      const manual = !!opts?.manual;
      const current = running.current;
      // A press joins a press, and an automatic run joins any run. A PRESS
      // never joins an automatic run: that run kept the backoff the press
      // exists to clear. It waits it out (bounded, F) and starts its own.
      if (current && (current.manual || !manual)) return current.promise;
      if (current) await current.promise.catch(() => undefined);
      if (running.current) return running.current.promise;
      const step = <T,>(work: Promise<T>, name: string): Promise<T> => within(work, limits.stepMs, name);
      const run = (async (): Promise<SyncRunOutcome> => {
        const outcome: SyncRunOutcome = { reason: null, sent: 0 };
        try {
          if (db) {
            // A purge that will not finish is let go: it deletes only settled
            // rows and uploaded photographs, which no send reads (decision log
            // 2026-10-27). Holding every send behind it forever is worse.
            await step(purgeOnce(db), 'purge').catch((error: unknown) => {
              if (!(error instanceof StepTimeLimitError)) throw error;
              purges.current.set(db.tenant, Promise.resolve());
              deps.telemetry.crashes.record({ error, fatal: false });
            });
          }
          // The check that does not answer is UNKNOWN — try anyway, never "no signal".
          const checked = await within(deps.network.kind(), limits.networkMs, 'network check').catch(() => null);
          if (checked) network.current = checked;
          const kind = checked ?? (network.current !== 'none' ? network.current : 'cellular');
          await step(report(true), 'count').catch(() => undefined);
          if (kind === 'none') {
            outcome.reason = 'offline';
            return outcome;
          }
          if (manual && db && technicianId) {
            const mine = scoped(db, technicianId);
            db.transaction(() => {
              outboxQ.clearBackoffMine(mine);
              photoQ.clearBackoffMine(mine);
            });
          }
          // The access token's hour has run out: renew it while there is a
          // signal (Security §1). A refresh the server refuses leaves it out,
          // and the run then says *Sign in again*.
          if (technicianId && !deps.session.courierAccessToken()) {
            await step(deps.session.refresh(), 'sign-in renewal').catch(() => undefined);
          }
          // DEF-FLD-10629 (FB-004, G): the signed-in technician's CAPTURE
          // credential — what every send travels under — missing or expired:
          // ask for a fresh one first. Failing that, the run says *Sign in
          // again to send* (never silence, as it was).
          if (technicianId && !tokens.tokenFor(technicianId)) {
            await step(deps.session.renewCaptureNow(), 'capture renewal').catch(() => undefined);
          }
          const result = await engine.sync({
            technicianId,
            network: kind,
            // PO 2026-10-28 (FB-015, supersedes R54): photos go on mobile data
            // unless *Photos on wi-fi only* is on. Read through the ONE helper
            // the screens use (DEF-FLD-10640: this read '=== "true"' of a '1').
            allowMobileData: !photosWifiOnly(deps.prefs),
            // Refused as too old (DEF-FLD-10355): download nothing; captured
            // work still goes up while the server accepts it (07-endpoints §0 rule 2).
            skipPull: (deps.update ?? appUpdate).get().required,
          });
          outcome.sent = result.data.accepted + result.data.duplicate + result.data.held_for_review;
          outcome.reason = reasonOfResult(result, technicianId);
          await step(sendTurnIns(), 'turn-ins');
          // CR-193-BRC10 — the week rides with the day's sync and is kept for
          // no signal. A failure keeps the last one; it never fails the run.
          const shiftsApi = asShiftsApi(transport);
          if (shiftsApi && technicianId) {
            await step(downloadWeek(shiftsApi, deps.prefs, technicianId, now()), 'week').catch(() => undefined);
          }
          // FB-033 — the office's word on availability, read back after the
          // send, so an office *Unavailable* shows here. A tap still on its
          // way is never overwritten; a failure never fails the run.
          const availabilityApi = asAvailabilityApi(transport);
          if (availabilityApi && technicianId && db) {
            const waiting = () => outboxQ.countOnTheirWayMine(scoped(db, technicianId), 'availability') > 0;
            const apply = (value: Parameters<typeof applyOfficeStatus>[2], since: string | null) =>
              applyOfficeStatus(deps.prefs, technicianId, value, since);
            await step(readBack(availabilityApi, waiting, apply), 'availability').catch(() => undefined);
          }
          // OQ-FLD-12797 — the office's certificate keys ride with each sync.
          // Adopted only over a pinned connection (`security/pinning.ts`);
          // a failure here never fails the run — the last good set stays.
          const settingsApi = asSettingsApi(transport);
          if (deps.pinning && settingsApi) await step(deps.pinning.refresh(settingsApi), 'certificate keys').catch(() => undefined);
          return outcome;
        } catch (err) {
          // A step that did not answer ends the run; the next press starts afresh.
          if (!(err instanceof StepTimeLimitError)) throw err;
          outcome.reason = 'timedOut';
          return outcome;
        } finally {
          lastRun.current = now().getTime();
          setStoreVersion((n) => n + 1);
          await step(report(false), 'count').catch(() => undefined);
          // Telemetry rides behind the work (the gate decides); it never throws.
          void deps.telemetry.flush(deps.crashReporter);
        }
      })();
      const entry = { promise: run, manual };
      running.current = entry;
      void run
        .catch(() => undefined)
        .then(() => {
          if (running.current === entry) running.current = null;
        });
      return run;
    },
    [engine, db, purgeOnce, deps.network, deps.prefs, deps.telemetry, deps.crashReporter, deps.pinning, deps.session, deps.update, transport, tokens, report, technicianId, sendTurnIns, now, limits],
  );

  /** Every other screen's *Send now*: the same run, its outcome not needed. */
  const sendNow = useCallback(async (): Promise<void> => {
    await syncNow();
  }, [syncNow]);

  const quietly = useCallback(() => {
    syncNow().catch(() => undefined);
  }, [syncNow]);

  // The schedule: once on opening, every 15 minutes, on coming forward, on reconnecting.
  useEffect(() => {
    if (!engine) {
      void report(false);
      return;
    }
    quietly();
    const timer = setInterval(quietly, deps.syncEveryMs ?? SYNC_EVERY_MS);
    const unNet = deps.network.subscribe((kind) => {
      const was = network.current;
      network.current = kind;
      if (was === 'none' && kind !== 'none') quietly();
      else void report(false);
    });
    const sub = deps.appState?.addEventListener('change', (state) => {
      if (state === 'active' && now().getTime() - lastRun.current > FOREGROUND_AFTER_MS) quietly();
    });
    return () => {
      clearInterval(timer);
      unNet();
      sub?.remove();
    };
  }, [engine, quietly, report, deps.network, deps.appState, deps.syncEveryMs, now]);

  // DEF-MET-10606 — the office gave or took a route: the push is the doorbell,
  // this is the parcel. The same download the Reads tab runs; a failure waits
  // for the next one (the push carried nothing that matters if lost).
  useEffect(() => {
    if (!db || !transport || !technicianId || !signedIn) return undefined;
    return onRouteWake(() => {
      downloadRoutes(db, technicianId, transport, now, deps.files)
        .then(() => setStoreVersion((n) => n + 1))
        .catch(() => undefined);
    });
  }, [db, transport, technicianId, signedIn, now, deps.files]);

  useEffect(() => {
    setWaveCrashCapture(deps.telemetry.crashes);
    return () => setWaveCrashCapture(null);
  }, [deps.telemetry]);

  const value = useMemo<FieldRuntimeValue>(
    () => ({ db: signedIn ? db : null, technicianId, syncNow, status, openError }),
    [db, signedIn, technicianId, syncNow, status, openError],
  );

  // ── 4. every wave, from the one store and the one handset ──────────────────
  const me = useMemo(() => {
    const base = notWiredServices({
      prefs: deps.prefs,
      data: value.db ? createDbMeData(value.db, { newId: deps.newId }) : NO_DATA,
      sync: { syncNow },
      crash: deps.telemetry.crashes,
      now,
    });
    if (value.db) {
      // CR-193-BRC10 — FF-46's week and End shift, FF-47's Submit the day.
      const shiftDeps = { db: value.db, prefs: deps.prefs, newId: deps.newId, now, sendNow };
      base.shifts = createShiftsPort(shiftDeps, base.shifts);
      base.timesheet = createTimesheetPort(shiftDeps);
      // FB-033 — FF-45's choice reaches dispatch through the outbox.
      base.availability = createAvailabilityPort(shiftDeps);
    }
    return api && value.db ? { ...base, alerts: httpAlertsPort(api, base.alerts) } : base;
  }, [deps.prefs, deps.newId, deps.telemetry, value.db, syncNow, sendNow, now, api]);
  const day = useMemo(
    () => ({
      db: value.db,
      now,
      location: dayLocationFrom(deps.device),
      sendNow: value.db ? syncNow : undefined,
      firstSync: engine
        ? engineFirstSync(async (what, opts) => {
            if (db) await within(purgeOnce(db), limits.stepMs, 'purge').catch(() => undefined);
            const kind = (await within(deps.network.kind(), limits.networkMs, 'network check').catch(() => null)) ?? 'cellular';
            // FF-08's Retry after the list arrived fetches the missing details alone (DEF-FLD-10608).
            return engine.sync({ technicianId, network: kind, onlyDetails: what === 'details', withTemplates: opts?.templates });
          })
        : undefined,
      crashes: deps.telemetry.crashes,
      ...(deps.MapView ? { MapView: deps.MapView } : {}),
      ...(doors ? { nearby: doors.nearby } : {}),
      storeVersion,
    }),
    [value.db, db, purgeOnce, now, deps.device, deps.network, deps.telemetry, deps.MapView, syncNow, engine, technicianId, doors, storeVersion, limits],
  );

  let tree: ReactNode = children;
  if (value.db && technicianId && active) {
    const theDb = value.db;
    const reads = readsPortsFrom(deps.device);
    tree = (
      <JobPortProvider
        services={{
          db: theDb,
          captor: () => ({ technicianId, capturedBy: technicianId }),
          displayName: active.displayName,
          clock,
          newId: deps.newId,
          camera: deps.device.camera,
          shrink: deps.device.shrink,
          files: deps.device.files,
          location: () => deps.device.location.last(),
          crashes: deps.telemetry.crashes,
        }}
      >
        <SiteDataProvider
          value={{
            db: theDb,
            technicianId,
            newId: deps.newId,
            clock,
            money: doors?.money ?? unwiredMoneyPort,
            ...(doors ? { reopen: doors.reopen, assets: doors.assets } : {}),
            // FB-028 (W2 = B) — FF-37 sends a raise at once when there is signal.
            sendNow,
            online: () => network.current !== 'none',
            device: devicePortsFrom(deps.device, () => i18n.language),
            scanner: deps.device.scanner,
            signature: deps.device.signature,
            prefs: deps.prefs,
          }}
        >
          <ReadsServicesProvider
            value={{
              db: theDb,
              technicianId,
              capturedBy: technicianId,
              readerName: active.displayName,
              clock,
              newId: deps.newId,
              prefs: deps.prefs,
              scanner: reads.scanner,
              camera: reads.camera,
              location: reads.location,
              dictation: reads.dictation,
              crash: deps.telemetry.crashes,
              sendNow,
              downloadRoutes: transport
                ? async () => {
                    await downloadRoutes(theDb, technicianId, transport, now, deps.files);
                  }
                : null,
              ...(api
                ? {
                    findings: {
                      options: () => api.findingOptions(),
                      get: (key: string) => api.finding(key),
                      createWorkOrder: (key: string, body: { template_id: string; priority_id?: string }) =>
                        api.findingWorkOrder(key, body),
                    },
                  }
                : {}),
              turnInRoute: (routeId) =>
                writeTurnIns(deps.prefs, technicianId, [
                  ...readTurnIns(deps.prefs, technicianId).filter((p) => p.routeId !== routeId),
                  { routeId, key: `turn-in-${routeId}-${deps.newId()}`, at: now().toISOString() },
                ]),
            }}
          >
            {children}
          </ReadsServicesProvider>
        </SiteDataProvider>
      </JobPortProvider>
    );
  }

  return (
    <RuntimeContext.Provider value={value}>
      <MeServicesProvider services={me}>
        <MeShellStatus base={status}>
          <DayDataProvider value={day}>
            <RemotePhotoProvider value={photoPort}>{tree}</RemotePhotoProvider>
          </DayDataProvider>
        </MeShellStatus>
      </MeServicesProvider>
    </RuntimeContext.Provider>
  );
}
