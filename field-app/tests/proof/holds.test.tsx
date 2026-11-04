/**
 * T-54 — EVERY HOLD GETS THE TEST THAT FIRES WHEN IT EXPIRES (hard-won law 2,
 * its mirror: a live screen behind a dead control).
 *
 * A HOLD is a control or a capture the app deliberately keeps from working
 * "until" something lands — a server door, a native package, an item kind.
 * Each row below asserts it TWO ways:
 *
 *   1. BY ADDRESS — the screen is opened by its id through the real app root
 *      (`FieldRuntime`, the store, the navigator) and the hold is SEEN there:
 *      the "not ready yet" notice, the missing pad, the "no camera" line.
 *   2. BY WHAT RELEASES IT — the thing it waits for is looked for in the
 *      repository itself: the server's own route table (`path("work/mobile/…")`
 *      in `06-backend/apps/**`), the server's item kinds (`ITEM_KINDS`,
 *      the reads door's `KIND_*`), or `field-app/package.json`.
 *
 * The day the route, kind or package lands, (2) goes RED and names the screen
 * whose hold has expired — so the hold is released in the same change, not
 * found weeks later behind a greyed-out button.
 *
 * RELEASED (lane INTEGRATE-2, 2026-10-21). The Phase 14 proof found most of
 * these holds already expired: the server mounted `nearby`, `alerts` (+
 * `ack`), `assets/search`, `templates`, `orders`, and per job `claim`,
 * `reopen`, `hand-back`, `crew`, `labour`, `money`, `acts` and the job
 * bundle, and the native build had expo-camera and react-native-maps — while
 * the app still held every one. Each is now WIRED (`sync/fieldApi.ts`,
 * `sync/doors.ts`, `sync/extras.ts`, `session/fieldDoors.ts`) and its row
 * here is a working test: the app CALLS the door (by address, read from its
 * source) and the screen WORKS at its address against the proof server.
 * Proved RED (this lane): with `HttpTransport.nearby`'s address misspelt,
 * "FF-11 nearby: the server mounts it and the app calls it" failed; with
 * `FieldRuntime` handing the day a refusing nearby port, FF-11's working test
 * failed on `nearby-gap` and both FF-12 claim tests failed.
 *
 * What is still held below is what still has no door or package: van stock,
 * remarks and asset papers. Each row goes RED the day its door lands.
 *
 * RELEASED (`DEF-FLD-10627`, PO 2026-10-27 *"start ... the signature fix"*):
 * FF-33's signing pad. Its row went RED the day react-native-signature-canvas
 * was installed (*"a signing-pad package has LANDED — release the hold on
 * FF-33"*) and is now the working test in *released — the native packages*.
 *
 * RELEASED (`CR-193-BRC10`, MQ-040 step 1, 2026-10-26): FF-46's week and End
 * shift and FF-47's Submit the day. Their row here went RED the day
 * `work/mobile/week` landed (*"a shifts route … has LANDED — release the hold
 * on FF-46"*), and is now the working test below. *Request time off* is step
 * 2 and NOT approved; it stays not sent (`tests/screens/me/shiftsWired.test.tsx`).
 *
 * Proved RED (Phase 14 lane report): with `path("work/mobile/van-stock", …)`
 * added to `apps/work/field_api.py`, FF-49's row failed: "FF-49 What is on the
 * van: a van-stock route … has LANDED — release the hold on FF-49".
 */
import './keepMounted';
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';
import { readdirSync, readFileSync, statSync } from 'fs';
import { join, resolve } from 'path';

import { View } from 'react-native';

import * as templatesQ from '../../src/db/queries/workOrderTemplates';
import { scoped } from '../../src/db/scoped';
import { type Device, UNWIRED_DEVICE } from '../../src/device';
import { canvasSignature } from '../../src/device/native/signature';
import type { ScreenId } from '../../src/navigation/screens';
import { addTechnician } from '../../src/screens/onSite/crewActions';
import { raiseOrder } from '../../src/screens/raise/RaiseScreen';
import type { MapViewProps } from '../../src/screens/theDay/mapView';
import { handBack, startClock, stopClock } from '../../src/screens/theJob/actions';
import { UNROUTED_KINDS } from '../../src/sync/outbox';
import { routeItemFromWire } from '../../src/sync/routeReads';
import { localDay } from '../../src/sync/shifts';
import { seedMapleHeights } from '../screens/reads/fixture';
import { seed as seedOnSite } from '../screens/onSite/fixture';
import { makeServices, seedWO4822 } from '../screens/theJob/fixture';
import { buildHandset, card, mountHandset, openAt, PEOPLE, type ProofServer, settle, signInAs, syncNow, TENANT, upsert } from './runtimeApp';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => ({ width: 390, height: 844, scale: 3, fontScale: 1 }),
}));

const DANA = PEOPLE['d.ortiz']!.technicianId;
const REPO = resolve(__dirname, '../../..');
const APP_SRC = resolve(__dirname, '../../src');

// ── What releases a hold, read from the repository ──────────────────────────

function filesUnder(dir: string, ext: RegExp): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) {
      if (name !== 'migrations' && name !== '__pycache__' && name !== 'node_modules') out.push(...filesUnder(p, ext));
    } else if (ext.test(name)) out.push(p);
  }
  return out;
}

/** Every `work/mobile/…` route the server mounts, with `<uuid:x>` written `{}`. */
const SERVER_ROUTES: string[] = (() => {
  const routes = new Set<string>();
  for (const f of filesUnder(join(REPO, '06-backend/apps'), /\.py$/)) {
    for (const m of readFileSync(f, 'utf8').matchAll(/path\(\s*"(work\/mobile\/[^"]*)"/g)) {
      routes.add(m[1]!.replace(/<[^>]+>/g, '{}'));
    }
  }
  return [...routes].sort();
})();

/** The job door's item kinds and the reads door's (`apps/work/sync_models.py`, `apps/metering/field_reads.py`). */
const SERVER_KINDS: string[] = (() => {
  const jobs = readFileSync(join(REPO, '06-backend/apps/work/sync_models.py'), 'utf8');
  const block = jobs.slice(jobs.indexOf('ITEM_KINDS = ('), jobs.indexOf(')', jobs.indexOf('ITEM_KINDS = (')));
  const kinds = [...block.matchAll(/"([a-z_]+)"/g)].map((m) => m[1]!);
  const reads = readFileSync(join(REPO, '06-backend/apps/metering/field_reads.py'), 'utf8');
  kinds.push(...[...reads.matchAll(/^KIND_[A-Z_]+ = "([a-z_]+)"/gm)].map((m) => `reads:${m[1]!}`));
  return kinds;
})();

const PACKAGES: string[] = (() => {
  const pkg = JSON.parse(readFileSync(resolve(__dirname, '../../package.json'), 'utf8')) as {
    dependencies?: Record<string, string>;
  };
  return Object.keys(pkg.dependencies ?? {});
})();

/**
 * Does the app CALL this server address — on a line that builds a request
 * (`url(` / `fetch(`), not in a comment and not in the words of a hold that
 * names the door it is waiting for (law 1: naming a door is not using it).
 */
function appCalls(pattern: RegExp): string[] {
  return filesUnder(APP_SRC, /\.tsx?$/).filter((f) =>
    readFileSync(f, 'utf8')
      .split('\n')
      .some((l) => !/^\s*(\*|\/\/|\/\*)/.test(l) && /\burl\(|\bfetch\(/.test(l) && pattern.test(l)),
  );
}

// ── The holds still standing ─────────────────────────────────────────────────

interface Hold {
  /** What is held, in a few words. */
  what: string;
  screen: ScreenId;
  params?: object;
  /** Asserts the hold is visible at the screen's address. */
  shows(page: ReturnType<typeof within>): Promise<void> | void;
  /** What releases it, and whether that has landed in the repository. */
  releasedBy: string;
  landed(): boolean;
}

const route = (wanted: RegExp) => () => SERVER_ROUTES.some((r) => wanted.test(r));
const pkg = (...names: string[]) => () => names.some((n) => PACKAGES.includes(n));

const press = async (page: ReturnType<typeof within>, id: string) => {
  await act(async () => {
    fireEvent.press(page.getByTestId(id));
  });
};

const W = { workOrderId: 'wo-4822' };

const HOLDS: Hold[] = [
  {
    what: 'What is on the van',
    screen: 'FF-49',
    shows: (p) => expect(p.getByTestId('ff49-not-wired')).toBeTruthy(),
    releasedBy: 'a van-stock route (ME-van-stock — not in 07-endpoints)',
    landed: route(/^work\/mobile\/.*(van|stock)/),
  },
];

/** Captured, kept, and NOT sent — each kind waits for a door (`sync/outbox.ts UNROUTED_KINDS`). */
const UNROUTED: Array<{ kind: (typeof UNROUTED_KINDS)[number]; screen: ScreenId; params: object; serverName: string[]; door: RegExp }> = [
  { kind: 'remark', screen: 'FF-30', params: W, serverName: ['remark', 'note'], door: /^work\/mobile\/.*(remark|note)/ }, // N18
  { kind: 'document', screen: 'FF-60', params: W, serverName: ['document'], door: /^work\/mobile\/.*(document|paper)/ },
];

// ── The run: one handset, signed in, every screen opened by its address ─────

/** A handset that HAS the hardware (the native build's): a fix, a camera, a scanner. */
const FIX = { lat: 30.2651, lng: -97.7494, accuracy_m: 6, fix_at: '2026-10-20T13:00:00.000Z' };
const DEVICE: Device = {
  ...UNWIRED_DEVICE,
  location: { current: () => Promise.resolve(FIX), last: () => FIX },
  camera: { available: true, takePhoto: () => Promise.resolve(null) },
  scanner: { available: true, start: () => () => undefined, setTorch: () => undefined },
};

/** A map that is not the placeholder — what `NativeApp` passes (`esriMapView`). */
function NativeMap(props: MapViewProps) {
  return (
    <View testID="native-map">
      {props.markers.map((mk) => (
        <View key={mk.id} testID={`native-map-${mk.id}`} />
      ))}
    </View>
  );
}

let h: ReturnType<typeof buildHandset>;
let m: ReturnType<typeof mountHandset>;
let server: ProofServer;

beforeAll(async () => {
  h = buildHandset({ network: 'wifi', device: DEVICE });
  h.deps.MapView = NativeMap;
  server = h.serverFor(TENANT);
  m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle(2);
  const store = h.holder.current!;
  seedOnSite(store, DANA);
  seedWO4822({ ...makeServices(), db: store });
  seedMapleHeights(store, { technician: DANA, lists: true });
}, 60_000);

afterAll(() => m.unmount());

function db() {
  return h.holder.current!;
}

/** Dana's rows, through the one helper (R133). */
function mine() {
  return scoped(db(), DANA);
}

async function page(id: ScreenId, params?: object) {
  await act(async () => {
    m.ref.resetRoot({ index: 0, routes: [{ name: 'Frame' }] });
  });
  await openAt(m, id, params);
  const roots = await screen.findAllByTestId(`screen-${id}`);
  return within(roots[roots.length - 1]!);
}

async function flush() {
  for (let i = 0; i < 3; i++) {
    await act(async () => {
      await new Promise((r) => setTimeout(r, 5));
    });
  }
}

test('the repository was read: routes, kinds, packages and the app’s own calls were found (a scan that found nothing would pass every row)', () => {
  expect(appCalls(/work\/mobile\/jobs\/[^'"`]*\/sync/)).not.toEqual([]);
  expect(appCalls(/work\/mobile\/reads\/sync/)).not.toEqual([]);
  // A door that is only NAMED (in a comment or a hold's words) is not a call (law 1).
  expect(appCalls(/work\/mobile\/van-stock/)).toEqual([]);
  console.log(`holds: ${SERVER_ROUTES.length} work/mobile routes · ${SERVER_KINDS.length} item kinds · ${PACKAGES.length} packages`);
  expect(SERVER_ROUTES).toContain('work/mobile/changes');
  expect(SERVER_ROUTES).toContain('work/mobile/reads/sync');
  expect(SERVER_KINDS).toContain('task_tick');
  expect(SERVER_KINDS).toContain('reads:reading');
  expect(PACKAGES).toContain('expo-sqlite');
});

describe.each(HOLDS.map((x) => [`${x.screen} ${x.what}`, x] as const))('still held: %s', (_name, hold) => {
  test('is held, at its address', async () => {
    await hold.shows(await page(hold.screen, hold.params));
  }, 60_000);

  test(`has not been released: ${hold.releasedBy}`, () => {
    if (hold.landed()) {
      throw new Error(`${hold.screen} ${hold.what}: ${hold.releasedBy} has LANDED — release the hold on ${hold.screen} and turn this row into the screen's working test`);
    }
  });
});

describe.each(UNROUTED.map((u) => [u.kind, u] as const))('unrouted kind %s', (k, u) => {
  test(`waits on the handset: it is in UNROUTED_KINDS and its screen ${u.screen} opens`, async () => {
    expect(UNROUTED_KINDS).toContain(k);
    await page(u.screen, u.params);
  }, 60_000);

  test('the server has no item kind or door for it yet', () => {
    const named = u.serverName.filter((n) => SERVER_KINDS.includes(n));
    if (named.length) throw new Error(`a door now takes "${named.join('", "')}" — route ${k} and release its hold on ${u.screen}`);
    if (SERVER_ROUTES.some((r) => u.door.test(r))) throw new Error(`a route matching ${u.door.source} has landed — route ${k}`);
  });
});

// ── RELEASED: the native packages (expo-camera, react-native-maps) ──────────

describe('released — the native packages', () => {
  test('the shipped build wires them: camera and scanner from expo-camera, the map from react-native-maps', () => {
    const nativeIndex = readFileSync(join(APP_SRC, 'device/native/index.ts'), 'utf8');
    const nativeApp = readFileSync(join(APP_SRC, 'NativeApp.tsx'), 'utf8');
    expect(PACKAGES).toEqual(expect.arrayContaining(['expo-camera', 'react-native-maps']));
    expect(nativeIndex).toMatch(/camera: expoCamera\(host\)/);
    expect(nativeIndex).toMatch(/scanner: expoScanner\(host\)/);
    // Behind the build's map flag (`release/nativeConfig.ts`): no Android key → the placeholder, never a crashing native view.
    expect(nativeApp).toMatch(/MapView: mapViewFor\(OS, BUILT, \(\) => esriMapView\(/);
  });

  test('FF-33 has a signing pad: react-native-signature-canvas, wired in the shipped build (DEF-FLD-10627)', () => {
    const nativeIndex = readFileSync(join(APP_SRC, 'device/native/index.ts'), 'utf8');
    expect(PACKAGES).toEqual(expect.arrayContaining(['react-native-signature-canvas', 'react-native-webview']));
    expect(nativeIndex).toMatch(/signature: canvasSignature\(\)/);
    expect(canvasSignature().Pad).not.toBeNull();
  });

  test('FF-13 draws the build’s map, not the placeholder', async () => {
    const p = await page('FF-13');
    expect(p.queryByTestId('map-placeholder-note')).toBeNull();
    expect(p.getByTestId('native-map')).toBeTruthy();
  }, 60_000);

  test('RW-14 has a camera: no “No camera on this phone.”', async () => {
    const p = await page('RW-14', { readId: 'r0472' });
    expect(p.queryByText('No camera on this phone.')).toBeNull();
  }, 60_000);

  test('RW-08 has a scanner: no “No scanner on this phone.”', async () => {
    const p = await page('RW-08');
    expect(p.queryByText('No scanner on this phone.')).toBeNull();
  }, 60_000);
});

// ── RELEASED: the server's doors — each USED, by address, and working at its screen ──

describe('released — the server doors', () => {
  test.each([
    ['FF-11 nearby', /^work\/mobile\/nearby$/, /work\/mobile\/nearby/],
    ['FF-12 claim', /^work\/mobile\/jobs\/\{\}\/claim$/, /\/claim['`]/],
    ['FF-42 alerts', /^work\/mobile\/alerts$/, /work\/mobile\/alerts\?/],
    ['FF-43 acknowledge', /^work\/mobile\/alerts\/\{\}\/ack$/, /\/ack['`]/],
    ['FF-36 reopen', /^work\/mobile\/jobs\/\{\}\/reopen$/, /\/reopen['`]/],
    ['FF-27 money (per JOB)', /^work\/mobile\/jobs\/\{\}\/money$/, /work\/mobile\/jobs\/[^'"`]*\/money/],
    ['FF-29 crew time', /^work\/mobile\/jobs\/\{\}\/labour$/, /\/labour['`]/],
    ['FF-29 a technician joins', /^work\/mobile\/jobs\/\{\}\/crew$/, /\/crew['`]/],
    ['FF-37 raise', /^work\/mobile\/orders$/, /work\/mobile\/orders['`]/],
    ['FF-58 hand-back', /^work\/mobile\/jobs\/\{\}\/hand-back$/, /\/hand-back['`]/],
    ['FF-15 the job bundle', /^work\/mobile\/jobs\/\{\}$/, /work\/mobile\/jobs\/\$\{[^}]+\}['`]/],
    ['FF-15 depart and arrive', /^work\/mobile\/jobs\/\{\}\/acts$/, /work\/mobile\/jobs\/[^'"`]*\/acts/],
    ['FF-41 asset search', /^work\/mobile\/assets\/search$/, /work\/mobile\/assets\/search/],
    ['FF-62 templates', /^work\/mobile\/templates$/, /work\/mobile\/templates/],
    // Lane FINDINGS (BR-WRK-067, 2026-10-22) — released from UNROUTED.
    ['RW-21 Create work order', /^work\/mobile\/findings\/\{\}\/work-order$/, /work\/mobile\/findings\/[^'"`]*\/work-order/],
    ['RW-21 finding lists', /^work\/mobile\/findings\/options$/, /work\/mobile\/findings\/options/],
    // CR-193-BRC10 (MQ-040 step 1) — released from HOLDS.
    ['FF-46 the week', /^work\/mobile\/week$/, /work\/mobile\/week/],
    ['FF-46 End shift', /^work\/mobile\/shift\/end$/, /work\/mobile\/shift\/end/],
    ['FF-47 Submit the day', /^work\/mobile\/timesheet\/submit$/, /work\/mobile\/timesheet\/submit/],
  ])('%s: the server mounts it and the app calls it', (_name, mounted, called) => {
    expect(SERVER_ROUTES.some((r) => mounted.test(r))).toBe(true);
    expect(appCalls(called)).not.toEqual([]);
  });

  test('RW-20 a field-added meter goes to the reads door as add_meter, with its photographs', () => {
    expect(SERVER_KINDS).toContain('reads:add_meter');
    const wire = routeItemFromWire(
      {
        key: 'k-am',
        kind: 'field_asset',
        seq: 1,
        captured_at: '2026-10-20T13:00:00Z',
        payload: { asset_id: 'a-new', badge: '88-1', serial: 'S-1', service: 'water', size: '5/8"', premise_id: 'p-1', photo_ids: ['ph-1'] },
      },
      'route-1',
    );
    expect(wire).toMatchObject({ kind: 'add_meter', premises_id: 'p-1', photos: ['ph-1'], meter: { service: 'water', badge: '88-1', serial_no: 'S-1', size_class: '5/8"' } });
  });

  test('crew time, raise, hand-back, the field-added meter and route findings are routed; a claim is online only', () => {
    for (const k of ['crew_time', 'raise', 'hand_back', 'claim', 'field_asset', 'route_finding']) expect(UNROUTED_KINDS).not.toContain(k as never);
  });

  test('RW-21/RW-18 a route finding goes to the reads door as finding (BR-WRK-067); RW-18 travels as meter_mismatch', () => {
    expect(SERVER_KINDS).toContain('reads:finding');
    const raised = routeItemFromWire(
      {
        key: 'k-f',
        kind: 'route_finding',
        seq: 1,
        captured_at: '2026-10-20T13:00:00Z',
        payload: { finding: 'leak', urgency: 'now', remark: 'Pooling', premise_id: 'p-1', asset_id: 'a-1', route_read_id: 'rr-1', photo_ids: ['ph-1'] },
        location: { lat: 30.26, lng: -97.74, accuracy_m: 6, fix_at: '2026-10-20T13:00:00Z' },
      },
      'route-1',
    );
    expect(raised).toMatchObject({ kind: 'finding', finding: 'leak', urgency: 'now', premises_id: 'p-1', asset_id: 'a-1', photos: ['ph-1'], position: { lat: 30.26, lng: -97.74 } });
    const mismatch = routeItemFromWire(
      { key: 'k-m', kind: 'route_finding', seq: 2, captured_at: '2026-10-20T13:01:00Z', payload: { mismatch: 'swapped', listed_asset_id: 'a-2', premise_id: 'p-2', scanned_code: 'X9' } },
      'route-1',
    );
    expect(mismatch).toMatchObject({ kind: 'finding', finding: 'meter_mismatch', mismatch: 'swapped', asset_id: 'a-2', premises_id: 'p-2', scanned_code: 'X9' });
  });

  test('FF-46 the week comes down with the sync and opens at its address; End shift reaches its door', async () => {
    const today = localDay(new Date(h.clock.now()));
    server.week = {
      from: today,
      to: today,
      today,
      days: [{ date: today, weekday: 'mon', kind: 'shift', start: '00:00', end: '23:59', holiday: null, note: null, exception: null }],
      current: { start: '00:00', end: '23:59', started_at: new Date(new Date(h.clock.now()).getTime() - 60 * 60_000).toISOString(), minutes_so_far: 60 },
      ended_at: null,
    };
    await syncNow(m);
    expect(server.callsTo('week')).not.toEqual([]);
    const p = await page('FF-46');
    await flush();
    expect(p.queryByTestId('ff46-not-wired')).toBeNull();
    expect(p.getByTestId(`ff46-day-${today}`)).toBeTruthy();
    await press(p, 'ff46-end-shift');
    await syncNow(m);
    expect(server.callsTo('shiftEnd')).toHaveLength(1);
    const extra = server.doorExtras.find(([door]) => door === 'shiftEnd')?.[1];
    expect(extra?.key).toBeTruthy();
    expect(extra?.captureToken).toBeTruthy();
  }, 60_000);

  test('FF-11 lists the server’s nearby work, measured from the handset’s fix', async () => {
    server.nearbyCards = [
      { id: 'wo-near-1', order_no: 'WO-4840', type: 'Routine read', premise: { id: 'p-near', address: '1412 Elm Street' }, distance_mi: '0.20', due_at: null, est_minutes: 10, priority: { code: 'P3' }, holder: 'unassigned', taken_by: null, claimable: true },
    ];
    const p = await page('FF-11');
    await flush();
    expect(p.queryByTestId('nearby-gap')).toBeNull();
    expect(p.getByTestId('nearby-wo-near-1')).toBeTruthy();
    expect(server.callsTo('nearby').at(-1)?.[0]).toMatchObject({ lat: FIX.lat, lng: FIX.lng, radiusMi: 2, page: 1 });
  }, 60_000);

  const nearJob = { id: 'wo-near-1', number: 'WO-4840', type: 'Routine read', priorityCode: 'P3', address: '1412 Elm Street', distanceMi: 0.2, dueAt: null, estMinutes: 10, takenBy: null };

  test('FF-12 claims through the server and returns to Today', async () => {
    const p = await page('FF-12', { job: nearJob });
    await press(p, 'claim-confirm');
    await flush();
    expect(server.callsTo('claim').at(-1)).toEqual(['wo-near-1']);
    expect(await screen.findAllByTestId('screen-FF-10')).not.toEqual([]);
  }, 60_000);

  test('FF-12 says it is taken when the server answers already_taken', async () => {
    server.takenJobs.add('wo-near-2');
    const p = await page('FF-12', { job: { ...nearJob, id: 'wo-near-2' } });
    await press(p, 'claim-confirm');
    await flush();
    expect(p.getByTestId('claim-taken')).toBeTruthy();
    expect(p.queryByTestId('claim-gap')).toBeNull();
  }, 60_000);

  test('FF-42 lists the server’s alerts', async () => {
    server.alertRows = [
      { id: 'al-1', kind: 'dispatch_message', work_order_id: null, order_no: 'WO-4822', premise: null, message: 'Gate code changed', sent_at: '2026-10-20T12:50:00Z', ack_required: false, ack_due_at: null, acknowledged_at: null },
    ];
    const p = await page('FF-42');
    await flush();
    expect(p.queryByTestId('ff42-not-wired')).toBeNull();
    expect(p.getByTestId('alert-al-1')).toBeTruthy();
  }, 60_000);

  test('FF-36 reopens through the server, with a key, and the job is open on the phone again', async () => {
    const p = await page('FF-36', W);
    await act(async () => {
      fireEvent.press(p.getAllByRole('radio')[0]!);
    });
    await press(p, 'reopen');
    await flush();
    const [jobId, body] = server.callsTo('reopen').at(-1) as [string, { reason: string; key: string }];
    expect(jobId).toBe('wo-4822');
    expect(body.reason).toBe('wrong_outcome');
    expect(body.key).toBeTruthy();
    expect(screen.queryByTestId('reopen-failed')).toBeNull();
    const row = mine().get<{ closed_at: string | null }>('SELECT closed_at FROM work_order WHERE id = :id AND technician_id = :technician_id', { id: 'wo-4822' });
    expect(row?.closed_at).toBeNull();
  }, 60_000);

  test('FF-27 checks the balance through the JOB’s money door', async () => {
    server.money.set('wo-4824', {
      order_no: 'WO-4824',
      as_at: new Date(h.clock.now()).toISOString(),
      fresh_minutes: 5,
      withheld: null,
      account_no: 'A-10588',
      owing: { amount: '312.4000', display: '312.40', currency: 'USD' },
      balance: { amount: '312.4000', display: '312.40', currency: 'USD' },
      currency: 'USD',
      latest_payment: null,
      charges: [],
      unavailable: [],
    });
    const p = await page('FF-27', { workOrderId: 'wo-4824' });
    // FB-023 F1 (PO 2026-10-31): the screen asks on OPEN, not only on a tap.
    await flush();
    expect(server.callsTo('money')).toEqual([['wo-4824']]);
    expect(p.getByTestId('balance-amount')).toHaveTextContent(/312\.40/);
    await press(p, 'check-now');
    await flush();
    expect(server.callsTo('money')).toEqual([['wo-4824'], ['wo-4824']]);
  }, 60_000);

  test('FF-41 asks the server for every meter, and lists what the phone does not hold', async () => {
    server.assetHits = [
      { id: 'a-far', asset_no: 'MTR-9001', serial: 'W-9001', type: 'Water meter', model: 'Neptune T-10', size_class: '5/8"', sub_meter: false, place: { premises: { id: 'p-far', address: '9 Far Lane' } } },
    ];
    const p = await page('FF-41');
    await act(async () => {
      fireEvent.changeText(p.getByTestId('asset-search'), 'W-9');
    });
    await flush();
    expect(server.callsTo('assets').at(-1)).toEqual(['W-9', 1]);
    expect(p.getByTestId('server-asset-W-9001')).toBeTruthy();
  }, 60_000);

  test('a sync fetches each new job’s bundle (FF-15’s steps) and the template catalogue (FF-62)', async () => {
    const start = new Date(h.clock.now() + 60 * 60_000);
    server.feed([upsert(card('wo-7001', 'WO-7001', start), new Date(h.clock.now()).toISOString())]);
    server.bundles.set('wo-7001', {
      order_id: 'wo-7001',
      order_no: 'WO-7001',
      template_id: 'tpl-x',
      template_version: 2,
      safety: [{ id: 's-7001-1', seq: 1, text: 'Cones out', is_mandatory: true }],
      tasks: [{ id: 't-7001-1', seq: 1, title: 'Swap the register', photo_required: true }],
      readings: [
        { id: 'r-7001-1', seq: 1, prompt: 'Final read', unit_of_measure: 'gal', min_value: null, max_value: null, kind: 'number' },
        // DEF-FLD-10585 (MQ-022): a TEXT reading, as the server sends one — no unit, no range.
        { id: 'r-7001-2', seq: 2, prompt: 'New meter serial', unit_of_measure: '', min_value: null, max_value: null, kind: 'text' },
      ],
      materials: [],
    });
    server.templateRows = [{ id: 'tpl-from-server', name: 'Hydrant flush', version: 4, service: 'Water', steps: 3, safety_checks: 1, readings: 0 }];
    await syncNow(m);
    expect(server.callsTo('bundle')).toContainEqual(['wo-7001']);
    const items = mine().all<{ id: string; kind: string }>('SELECT id, kind FROM wo_item WHERE work_order_id = :w AND technician_id = :technician_id ORDER BY id', { w: 'wo-7001' });
    expect(items).toEqual([
      { id: 's-7001-1', kind: 'safety' },
      { id: 't-7001-1', kind: 'task' },
    ]);
    expect(mine().all<{ id: string; kind: string; unit: string }>('SELECT id, kind, unit FROM wo_reading WHERE work_order_id = :w AND technician_id = :technician_id ORDER BY id', { w: 'wo-7001' })).toEqual([
      { id: 'r-7001-1', kind: 'number', unit: 'gal' },
      { id: 'r-7001-2', kind: 'text', unit: '' },
    ]);
    expect(mine().get<{ n: number }>('SELECT needs_bundle AS n FROM work_order WHERE id = :w AND technician_id = :technician_id', { w: 'wo-7001' })?.n).toBe(0);
    expect(db().ref.get<{ name: string }>("SELECT name FROM work_order_templates WHERE id = 'tpl-from-server'")?.name).toBe('Hydrant flush');
  }, 60_000);

  test('FF-15 depart and arrive, a crew member joining, a raise and a hand-back each reach their door on the next sync', async () => {
    const job = m.inside.current.job!;
    const wave = m.inside.current.wave!;
    await act(async () => {
      startClock(job, 'wo-4826', 'travel');
    });
    const running = mine().get<{ id: string }>(
      "SELECT id FROM crew_time WHERE work_order_id = 'wo-4826' AND technician_id = :technician_id AND ended_at IS NULL AND kind = 'travel'",
    )!;
    await act(async () => {
      stopClock(job, 'wo-4826', running.id);
      addTechnician(wave, 'wo-4826', { id: 'tech-marco', name: 'M. Chen' }, 'D. Ortiz');
      const template = templatesQ.listPublished(db(), { limit: 50 }).find((x) => x.id === 'tpl-leak')!;
      raiseOrder(wave, { template, from: null, urgency: 'same_day', note: 'Leak at the curb stop', location: null });
      handBack(job, 'wo-4830', { reason: 'Need a second person', note: '', emergency: false });
    });
    await syncNow(m);
    expect(server.callsTo('labour')).toEqual(
      expect.arrayContaining([
        ['wo-4826', { depart_at: expect.any(String) }],
        ['wo-4826', { arrive_at: expect.any(String) }],
      ]),
    );
    expect(server.callsTo('act')).toEqual(expect.arrayContaining([['wo-4826', 'depart'], ['wo-4826', 'arrive']]));
    expect(server.callsTo('crew')).toContainEqual(['wo-4826', { technician_id: 'tech-marco', key: expect.any(String) }]);
    const raised = server.callsTo('raise').at(-1)![0] as Record<string, unknown>;
    expect(raised).toMatchObject({ template_id: 'tpl-leak', urgency: 'same_day', note: 'Leak at the curb stop' });
    expect(typeof raised.key).toBe('string');
    expect(server.callsTo('handBack')).toContainEqual(['wo-4830', { reason: 'Need a second person', note: null }]);
    const sent = mine().all<{ kind: string; state: string }>(
      "SELECT kind, state FROM outbox WHERE technician_id = :technician_id AND kind IN ('crew_time','raise','hand_back') AND channel = 'job'",
    );
    expect(sent.length).toBe(5);
    expect(sent.filter((r) => r.state !== 'accepted')).toEqual([]);
  }, 60_000);
});
