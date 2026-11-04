/**
 * Phase 14 (Proof) — ONE handset, mounted the way `App.tsx` mounts it, with
 * nothing replaced but the platform and the server:
 *
 *   ThemeProvider → I18nProvider → SessionProvider → GettingInProvider →
 *   FieldRuntime (the REAL one: store opened at sign-in, the sync engine, every
 *   wave's provider) → NavigationContainer → AppNavigator
 *
 * The session is a real `SessionManager` whose outbox port is the store
 * holder's; the store is better-sqlite3 behind the handset's own driver
 * interface (one in-memory database per FILE NAME, so `field-<tenant>.sqlite`
 * is a real per-tenant file); the network is a switch a test flips to
 * "airplane mode"; the server is `ProofServer` — the fake of the server's
 * per-item contract in `tests/sync/support/fakeServer.ts` (one receipt per
 * key, a refused item's savepoint rolled back, `acknowledged` listing every
 * key but the refused) plus the route door and a scripted change feed.
 *
 * `probe` reaches inside the mounted tree the way a screen does — the job
 * port, the on-site wave, the runtime — so a proof captures through the SAME
 * functions the screens call, against the store the screens read.
 */
import { createNavigationContainerRef, NavigationContainer, type ParamListBase } from '@react-navigation/native';
import { act, render } from '@testing-library/react-native';
import { createHash } from 'crypto';
import { type ReactElement } from 'react';

import { StoreHolder, storeOutboxPort } from '../../src/db/storeHolder';
import type { DriverFactory } from '../../src/db/driver';
import { FakeNetwork, UNWIRED_DEVICE, type Device } from '../../src/device';
import { createFieldI18n } from '../../src/i18n/i18n';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { AppNavigator } from '../../src/navigation/AppNavigator';
import type { ScreenId } from '../../src/navigation/screens';
import { GettingInProvider } from '../../src/screens/gettingIn/gettingInServices';
import { useWave, type Wave } from '../../src/screens/onSite/fieldData';
import { type JobPortValue, useJobPort } from '../../src/screens/theJob/JobPort';
import { openScreen } from '../../src/screens/theDay/go';
import { ManualClock } from '../../src/security/clock';
import { DeviceRegister } from '../../src/security/deviceRegister';
import { MemoryKeyValueStore } from '../../src/security/prefs';
import { MemorySecretStore } from '../../src/security/secretStore';
import { FieldRuntime, type FieldRuntimeDeps, type FieldRuntimeValue, useFieldRuntime } from '../../src/session/FieldRuntime';
import { PasswordVerifier } from '../../src/session/passwordVerifier';
import { SessionProvider } from '../../src/session/SessionProvider';
import { SessionManager } from '../../src/session/sessionManager';
import type { DoorExtra, FieldApi, LabourMoments, WireAlert, WireAssetHit, WireBundle, WireJobMoney, WireNearbyCard, WirePage, WireTemplate } from '../../src/sync/fieldApi';
import { TransportError, type ChangesPage, type JobCard } from '../../src/sync/transport';
import type { ShiftsApi, WireWeek } from '../../src/sync/shifts';
import type { RouteStopsPage, RoutesApi, RoutesPage, TurnInBody } from '../../src/sync/routes';
import { createMemoryStore, createTelemetry } from '../../src/telemetry';
import { ThemeProvider, type ThemeMode } from '../../src/theme';
import { memoryFactory } from '../db/support/nodeDriver';
import { FakeAuthApi, PEOPLE, SHIFT_START, TENANT } from '../session/fakes';
import { FakeServer } from '../sync/support/fakeServer';

export { PEOPLE, SHIFT_START, TENANT };

const page = <T,>(results: T[]): WirePage<T> => ({ count: results.length, next: null, previous: null, results });
const notFound = () => new TransportError('http', 'HTTP 404', 404, { code: null, message_key: 'common.not_found' });

/**
 * The server for one tenant: the job door, the photo door, the feed, the route
 * door — and the online doors (`FieldApi`, lane INTEGRATE-2), each recording
 * what it was asked so a proof can assert the app USED the door, by address.
 */
export class ProofServer extends FakeServer implements RoutesApi, FieldApi, ShiftsApi {
  readonly turnIns: Array<{ routeId: string; body: TurnInBody }> = [];
  /** Every online-door call, in order: `[door, …args]`. */
  readonly doorCalls: Array<[string, ...unknown[]]> = [];
  nearbyCards: WireNearbyCard[] = [];
  /** Jobs another technician has: a claim answers `already_taken`. */
  readonly takenJobs = new Set<string>();
  alertRows: WireAlert[] = [];
  readonly money = new Map<string, WireJobMoney>();
  assetHits: WireAssetHit[] = [];
  templateRows: WireTemplate[] = [];
  readonly raised = new Map<string, { order_id: string; order_no: string }>();

  nearby(q: { lat: number; lng: number; radiusMi: number; page: number }) {
    this.doorCalls.push(['nearby', q]);
    return Promise.resolve({ ...page(this.nearbyCards), unassigned: this.nearbyCards.filter((c) => c.holder === 'unassigned').length });
  }
  claim(jobId: string) {
    this.doorCalls.push(['claim', jobId]);
    if (this.takenJobs.has(jobId)) {
      return Promise.reject(new TransportError('http', 'HTTP 409', 409, { code: 'BIZ-STATE', message_key: 'work.claim.already_taken' }));
    }
    return Promise.resolve({ order_id: jobId, already_yours: false });
  }
  alerts(n: number) {
    this.doorCalls.push(['alerts', n]);
    return Promise.resolve(page(this.alertRows));
  }
  acknowledgeAlert(alertId: string) {
    this.doorCalls.push(['ack', alertId]);
    const row = this.alertRows.find((a) => a.id === alertId);
    if (!row) return Promise.reject(notFound());
    row.acknowledged_at = row.acknowledged_at ?? new Date().toISOString();
    return Promise.resolve(row);
  }
  reopen(jobId: string, body: { reason: string; note?: string | null; key: string }) {
    this.doorCalls.push(['reopen', jobId, body]);
    return Promise.resolve({ order_id: jobId, reopened: true });
  }
  jobMoney(jobId: string) {
    this.doorCalls.push(['money', jobId]);
    const m = this.money.get(jobId);
    return m ? Promise.resolve(m) : Promise.reject(notFound());
  }
  jobBundle(jobId: string): Promise<WireBundle> {
    this.doorCalls.push(['bundle', jobId]);
    return super.jobBundle(jobId);
  }
  /** What each own-door call carried beside its body — key, captor token, whose time (lane S-GAPS). */
  readonly doorExtras: Array<[string, DoorExtra | undefined]> = [];
  jobAct(jobId: string, act: 'depart' | 'arrive', extra?: DoorExtra) {
    this.doorCalls.push(['act', jobId, act]);
    this.doorExtras.push(['act', extra]);
    return Promise.resolve({ act });
  }
  recordLabour(jobId: string, moments: LabourMoments, extra?: DoorExtra) {
    this.doorCalls.push(['labour', jobId, moments]);
    this.doorExtras.push(['labour', extra]);
    return Promise.resolve({ changed: Object.keys(moments) });
  }
  addCrew(jobId: string, body: { technician_id: string; key: string }, extra?: DoorExtra) {
    this.doorCalls.push(['crew', jobId, body]);
    this.doorExtras.push(['crew', extra]);
    return Promise.resolve({ created: true });
  }
  leaveCrew(jobId: string, body: { technician_id: string; ended_at: string | null }, extra?: DoorExtra) {
    this.doorCalls.push(['leave', jobId, body]);
    this.doorExtras.push(['leave', extra]);
    return Promise.resolve({ changed: ['end_at'], duplicate: false });
  }
  handBack(jobId: string, body: { reason: string; note: string | null }, extra?: DoorExtra) {
    this.doorCalls.push(['handBack', jobId, body]);
    this.doorExtras.push(['handBack', extra]);
    return Promise.resolve({ order_id: jobId, assigned: false });
  }
  /** DEF-FLD-10579's two doors. This fake does not apply the acceptance rule;
   *  `acceptOnStart.test.tsx`'s server does. */
  acceptJob(jobId: string, extra?: DoorExtra): Promise<Record<string, unknown>> {
    this.doorCalls.push(['accept', jobId]);
    this.doorExtras.push(['accept', extra]);
    return Promise.resolve({ order_id: jobId, technician_acceptance: { state: 'accepted', at: null, reason: null } });
  }
  declineJob(jobId: string, body: { reason: string; note: string | null }, extra?: DoorExtra): Promise<Record<string, unknown>> {
    this.doorCalls.push(['decline', jobId, body]);
    this.doorExtras.push(['decline', extra]);
    return Promise.resolve({ order_id: jobId, technician_acceptance: { state: 'declined', at: null, reason: body.reason } });
  }
  raiseOrder(body: Record<string, unknown>, extra?: DoorExtra) {
    this.doorCalls.push(['raise', body]);
    this.doorExtras.push(['raise', extra]);
    const key = String(body.key);
    const seen = this.raised.get(key);
    if (seen) return Promise.resolve({ ...seen, duplicate: true });
    const made = { order_id: `raised-${this.raised.size + 1}`, order_no: `WO-9${this.raised.size + 100}` };
    this.raised.set(key, made);
    return Promise.resolve({ ...made, duplicate: false });
  }
  searchAssets(q: string, n: number) {
    this.doorCalls.push(['assets', q, n]);
    return Promise.resolve(page(this.assetHits));
  }
  templates(n: number) {
    this.doorCalls.push(['templates', n]);
    return Promise.resolve(page(this.templateRows));
  }
  findingOptions() {
    this.doorCalls.push(['findingOptions']);
    return Promise.resolve({ kinds: [], urgencies: [], priorities: [] });
  }
  finding(key: string) {
    this.doorCalls.push(['finding', key]);
    return Promise.resolve({ key, kind: 'leak', status: 'open' as const, conversion: null, work_order: null });
  }
  findingWorkOrder(key: string, body: { template_id: string; priority_id?: string }) {
    this.doorCalls.push(['findingWorkOrder', key, body]);
    return Promise.resolve({
      key,
      kind: 'leak',
      status: 'work_order_created' as const,
      conversion: 'by_hand' as const,
      work_order: { id: 'wo-f', order_no: 'WO-4871' },
    });
  }
  /** CR-193-BRC10 — the week the next sync downloads (null: the door answers 404). */
  week: WireWeek | null = null;
  myWeek(from?: string): Promise<WireWeek> {
    this.doorCalls.push(['week', from ?? null]);
    return this.week ? Promise.resolve(this.week) : Promise.reject(notFound());
  }
  endShift(body: { at: string }, extra?: DoorExtra) {
    this.doorCalls.push(['shiftEnd', body]);
    this.doorExtras.push(['shiftEnd', extra]);
    return Promise.resolve({ ended_at: body.at, status: 'off_today', duplicate: false });
  }
  submitTimesheet(body: { date: string }, extra?: DoorExtra) {
    this.doorCalls.push(['timesheetSubmit', body]);
    this.doorExtras.push(['timesheetSubmit', extra]);
    return Promise.resolve({ date: body.date, jobs: 0, labour_minutes: 0, travel_minutes: 0, lines: [], duplicate: false });
  }
  /** The calls to one door. */
  callsTo(door: string): unknown[][] {
    return this.doorCalls.filter((c) => c[0] === door).map((c) => c.slice(1));
  }
  /** Every access token a request travelled under (the COURIER, not the captor). */
  myRoutes(): Promise<RoutesPage> {
    return Promise.resolve({ results: [], next_page: null });
  }
  routePage(): Promise<RouteStopsPage> {
    return Promise.reject(new Error('not asked'));
  }
  turnIn(routeId: string, body: TurnInBody): Promise<unknown> {
    this.turnIns.push({ routeId, body });
    return Promise.resolve({ ok: true });
  }
  cantReadReasons() {
    return Promise.resolve({ results: [] });
  }

  /** Append one page to the change feed; cursors are `c<n>` (the fake's own scheme). */
  feed(changes: ChangesPage['changes']): void {
    const n = this.pages.length;
    this.pages.push({ changes, count: changes.length, next_cursor: `c${n + 1}`, has_more: false });
  }

  /** How many times the far end APPLIED each key — the "nothing doubled" count. */
  appliedPerKey(): Map<string, number> {
    const m = new Map<string, number>();
    for (const a of this.applied) m.set(a.key, (m.get(a.key) ?? 0) + 1);
    return m;
  }
}

/** The handset's photo files: which exist, and their bytes (shared with the server's "disk" read). */
export class HandsetFiles {
  readonly bytes = new Map<string, string>();
  readonly deleted: string[] = [];
  constructor(private readonly servers: () => Iterable<ProofServer>) {}
  add(path: string, content: string): void {
    this.bytes.set(path, content);
    for (const s of this.servers()) s.disk.set(path, content);
  }
  async exists(path: string): Promise<boolean> {
    return this.bytes.has(path);
  }
  async delete(path: string): Promise<void> {
    this.bytes.delete(path);
    this.deleted.push(path);
  }
  /** Every help document fetched at sync, by its link. */
  readonly downloads: string[] = [];
  /** FB-031 — the headers each download carried, in the same order. */
  readonly downloadHeaders: (Record<string, string> | undefined)[] = [];
  /** FB-031 — the next download dies with no answer (no signal mid-transfer). */
  dropNext = false;
  /** A help document's bytes, fetched from its link into the phone's own store. Our own route wants the credential. */
  async download(url: string, name: string, headers?: Record<string, string>): Promise<{ path: string; bytes: number }> {
    this.downloads.push(url);
    this.downloadHeaders.push(headers);
    if (this.dropNext) {
      this.dropNext = false;
      throw new TransportError('network', 'connection dropped');
    }
    if (url.startsWith(FakeServer.API) && headers?.Authorization !== FakeServer.TOKEN) {
      throw new TransportError('http', 'HTTP 401', 401);
    }
    for (const s of this.servers()) {
      const content = s.documentFiles.get(url);
      if (content !== undefined) {
        const path = `help/${name}`;
        this.bytes.set(path, content);
        return { path, bytes: Buffer.byteLength(content) };
      }
    }
    throw new TransportError('http', 'HTTP 403', 403);
  }
}

export function sha(text: string): string {
  return createHash('sha256').update(text).digest('hex');
}

export interface HandsetOptions {
  network?: 'wifi' | 'cellular' | 'none';
  factory?: DriverFactory & { files?: Map<string, unknown> };
  start?: number;
  device?: Device;
}

/** Everything one handset is made of, built once and re-mountable (an app restart is a re-mount). */
export function buildHandset(options: HandsetOptions = {}) {
  const clock = new ManualClock(options.start ?? SHIFT_START);
  const secrets = new MemorySecretStore();
  const prefs = new MemoryKeyValueStore();
  const factory = options.factory ?? memoryFactory();
  const iso = () => new Date(clock.now()).toISOString();
  const holder = new StoreHolder(factory, { now: iso });
  const api = new FakeAuthApi();
  let n = 0;
  const device = new DeviceRegister(secrets, () => `device-${(n += 1)}`);
  const verifier = new PasswordVerifier(secrets, async (s) => `h-${s}`, () => 'salt');
  const session = new SessionManager({ api, secrets, prefs, clock, device, verifier, outbox: storeOutboxPort(holder) });
  const servers = new Map<string, ProofServer>();
  const serverFor = (tenant: string): ProofServer => {
    let s = servers.get(tenant);
    if (!s) {
      s = new ProofServer();
      servers.set(tenant, s);
    }
    return s;
  };
  const network = new FakeNetwork(options.network ?? 'wifi');
  const files = new HandsetFiles(() => servers.values());
  let ids = 0;
  const deps: FieldRuntimeDeps = {
    holder,
    session,
    prefs,
    device: options.device ?? UNWIRED_DEVICE,
    network,
    transportFor: (tenant) => serverFor(tenant),
    files,
    telemetry: createTelemetry({ store: createMemoryStore(), analytics: { send: async () => undefined }, identity: () => null }),
    newId: () => `id-${String((ids += 1)).padStart(6, '0')}`,
    now: () => new Date(clock.now()),
    // The 15-minute timer never fires inside a test: every sync here is one a test asked for.
    syncEveryMs: 24 * 60 * 60 * 1000,
  };
  return { clock, secrets, prefs, factory, holder, api, session, servers, serverFor, network, files, deps, iso };
}

export type Handset = ReturnType<typeof buildHandset>;

/** What the mounted tree offers, read from inside it. */
export interface Inside {
  runtime: FieldRuntimeValue | null;
  job: JobPortValue | null;
  wave: Wave | null;
}

function Probe({ into }: { into: { current: Inside } }) {
  into.current = { runtime: useFieldRuntime(), job: useJobPort(), wave: useWave() };
  return null;
}

/** Mount the handset's app: a cold start (a re-mount is the next app start). */
export function mountHandset(h: Handset, opts: { theme?: ThemeMode; biggerText?: boolean; wrap?: (ui: ReactElement) => ReactElement } = {}) {
  const ref = createNavigationContainerRef<ParamListBase>();
  const inside: { current: Inside } = { current: { runtime: null, job: null, wave: null } };
  const wrap = opts.wrap ?? ((ui: ReactElement) => ui);
  const deps = { ...h.deps };
  const ui = (
    <ThemeProvider initialMode={opts.theme ?? 'light'} initialBiggerText={opts.biggerText ?? false}>
      <I18nProvider fieldI18n={createFieldI18n({ language: 'en' })} prefs={h.prefs}>
        <SessionProvider manager={h.session}>
          <GettingInProvider value={{ api: h.api, tenant: TENANT }}>
            <FieldRuntime deps={deps}>
              <Probe into={inside} />
              {wrap(
                <NavigationContainer ref={ref}>
                  <AppNavigator />
                </NavigationContainer>,
              )}
            </FieldRuntime>
          </GettingInProvider>
        </SessionProvider>
      </I18nProvider>
    </ThemeProvider>
  );
  const utils = render(ui);
  return { ...utils, ref, inside };
}

export type Mounted = ReturnType<typeof mountHandset>;

export async function signInAs(h: Handset, login: string, tenant = TENANT): Promise<void> {
  const p = PEOPLE[login];
  if (!p) throw new Error(login);
  await act(async () => {
    await h.session.signIn({ tenant, login, password: p.password });
  });
}

export async function signOut(h: Handset): Promise<void> {
  await act(async () => {
    await h.session.signOut();
  });
}

/** Open a screen by its ADDRESS, the way every door in the app does. */
export async function openAt(m: Mounted, id: ScreenId, params?: object): Promise<void> {
  await act(async () => {
    openScreen(m.ref, id, params);
  });
}

/** Push, upload, pull — now, through the runtime the app mounts. */
export async function syncNow(m: Mounted): Promise<void> {
  await act(async () => {
    const rt = m.inside.current.runtime;
    if (!rt) throw new Error('no runtime');
    await rt.syncNow();
  });
}

/** Let every effect the runtime started (its first sync, a purge) settle. */
export async function settle(times = 5): Promise<void> {
  for (let i = 0; i < times; i++) {
    await act(async () => {
      await new Promise((r) => setTimeout(r, 2));
    });
  }
}

/** A job card as `GET work/mobile/changes` serves it. */
export function card(id: string, number: string, windowStart: Date, minutes = 60, extra: Partial<JobCard> = {}): JobCard {
  return {
    id,
    order_no: number,
    type: 'Meter exchange',
    premise: { id: `p-${id}`, premise_no: `P-${number}`, address: `${100 + Number(number.replace(/\D/g, '') || 0) % 900} Elm Street` },
    window_start: windowStart.toISOString(),
    window_end: new Date(windowStart.getTime() + minutes * 60_000).toISOString(),
    due_at: null,
    est_minutes: minutes,
    priority: { code: 'P3', rank: 3 },
    state: 'open',
    dispatch_state: 'scheduled',
    access_notes: null,
    hazards: null,
    gate_code: null,
    ...extra,
  };
}

export const upsert = (job: JobCard, at: string) => ({ change: 'upsert' as const, order_id: job.id, at, job });
export const removed = (orderId: string, at: string) => ({ change: 'removed' as const, order_id: orderId, at });
