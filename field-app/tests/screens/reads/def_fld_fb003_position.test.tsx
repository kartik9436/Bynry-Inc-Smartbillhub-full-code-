/**
 * DEF-FLD-10632 (FB-003, the position half) — the position is captured
 * automatically, never by a button.
 *
 * PO report FB-003 (2026-10-26 18:32, reader Sam Curran, RT-001): a reading
 * saved, RW-13 said *"Caught automatically: No position"* and *"Saved without
 * a position."*, and nothing on the reading, the camera or the saved reading
 * could get one. PO ruling 2026-10-27 (decision log *"FB-003: the position is
 * captured automatically, never by a button"*), verbatim: *"no need of new
 * button , capture the position automatically ; if user has location
 * permission not enabled asked the user to give permission , when user takes
 * the photo record the lat,long positions"*, then *"go with recommendation,
 * start"* on the two figures: wait up to 10 s at save; a late fix attaches
 * within 5 minutes and never after.
 *
 * Worked case put to the PO: a reading saved 18:32:48 with no fix; a ±10 m fix
 * arrives 18:35 → *"Position added at 18:35 ±10 m"*; a fix first arriving
 * 18:38 attaches nothing.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import { scoped } from '../../../src/db/scoped';
import type { Fix } from '../../../src/screens/reads/ports';
import { fixForSave, LATE_POSITION_WINDOW_MS, SAVE_WAIT_MS } from '../../../src/screens/reads/position';
import { routeItemFromWire } from '../../../src/sync/routeReads';
import { HERE, RAY } from './fixture';
import { FakeLocation, mountReads } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

type Page = ReturnType<typeof within>;

async function press(page: Page, id: string) {
  await act(async () => {
    fireEvent.press(page.getByTestId(id));
  });
}

const top = async (id: string) => within((await screen.findAllByTestId(`screen-${id}`)).at(-1)!);

function type(page: Page, digits: string) {
  for (const d of digits) fireEvent.press(page.getByTestId(`keypad-${d}`));
}

interface Row {
  id: string;
  kind: string;
  payload: string;
  captured_at: string;
  lat: number | null;
  lng: number | null;
  accuracy_m: number | null;
  fix_at: string | null;
}

function rows(app: Awaited<ReturnType<typeof mountReads>>, kind: string): Row[] {
  return scoped(app.db, RAY).all<Row>('SELECT * FROM outbox WHERE technician_id = :technician_id AND kind = :kind ORDER BY seq', { kind });
}

const fixAt = (iso: string, accuracy = 10, lat = HERE.lat + 0.0001): Fix => ({ lat, lng: HERE.lng, accuracy_m: accuracy, fix_at: iso });

/** RW-09: type a figure and save, with no fix anywhere. Returns RW-13. */
async function saveWithoutFix(app: Awaited<ReturnType<typeof mountReads>>, withPhoto = false): Promise<Page> {
  let page = within((await app.open('RW-09', { readId: 'r0471' }))!);
  if (withPhoto) {
    await press(page, 'read-photo');
    await press(await top('RW-14'), 'door-RW-13');
    page = await top('RW-09');
  }
  type(page, '52410');
  await press(page, 'door-RW-13');
  return top('RW-13');
}

describe('FB-003 — where location is used, Android is asked for it', () => {
  test('opening the route asks for location (the platform prompt and, if off, the Turn on location dialog)', async () => {
    const location = new FakeLocation();
    const app = await mountReads({ location });
    await app.open('RW-05', { routeId: 'wlk-07' });
    expect(location.ensureOn).toHaveBeenCalledTimes(1);
    app.unmount();
  });

  test('opening the camera asks for location', async () => {
    const location = new FakeLocation();
    const app = await mountReads({ location });
    await app.open('RW-14', { readId: 'r0471' });
    expect(location.ensureOn).toHaveBeenCalled();
    app.unmount();
  });

  test('refused for good: one line, and Open settings is the only control', async () => {
    const location = new FakeLocation(null);
    location.access = 'blocked';
    const app = await mountReads({ location });
    const walk = within((await app.open('RW-05', { routeId: 'wlk-07' }))!);
    expect(walk.getByTestId('location-off')).toHaveTextContent('Location is off for this app.Open settings');
    await press(walk, 'location-open-settings');
    expect(location.openSettings).toHaveBeenCalledTimes(1);
    const cam = within((await app.open('RW-14', { readId: 'r0471' }))!);
    expect(cam.getByTestId('location-off')).toBeTruthy();
    app.unmount();
  });

  test('allowed: no line is shown', async () => {
    const app = await mountReads();
    const walk = within((await app.open('RW-05', { routeId: 'wlk-07' }))!);
    expect(walk.queryByTestId('location-off')).toBeNull();
    app.unmount();
  });
});

describe('FB-003 — saving takes the best recent fix, or waits up to 10 seconds, then saves', () => {
  afterEach(() => jest.useRealTimers());

  test('the background watch holds a fresh fix: it is used at once, nothing waits', async () => {
    const held = fixAt('2026-10-20T10:42:10.000Z', 6);
    const never = new Promise<Fix | null>(() => undefined);
    const fix = await fixForSave({ current: () => never, last: () => held }, () => Date.parse('2026-10-20T10:42:18.000Z'));
    expect(fix).toEqual(held);
  });

  test('no fix held: waits for one and takes it when it comes within 10 s', async () => {
    jest.useFakeTimers();
    let answer: (f: Fix | null) => void = () => undefined;
    const pending = new Promise<Fix | null>((r) => (answer = r));
    const out = fixForSave({ current: () => pending, last: () => null }, () => Date.now());
    await jest.advanceTimersByTimeAsync(3_000);
    answer(fixAt('2026-10-20T10:42:21.000Z'));
    await expect(out).resolves.toMatchObject({ accuracy_m: 10 });
  });

  test('no fix in 10 s: saves without — never blocks longer', async () => {
    jest.useFakeTimers();
    let settled: Fix | null | 'pending' = 'pending';
    const never = new Promise<Fix | null>(() => undefined);
    void fixForSave({ current: () => never, last: () => null }, () => Date.now()).then((f) => (settled = f));
    await jest.advanceTimersByTimeAsync(SAVE_WAIT_MS - 100);
    expect(settled).toBe('pending');
    await jest.advanceTimersByTimeAsync(100);
    expect(settled).toBeNull();
    expect(SAVE_WAIT_MS).toBe(10_000);
  });

  test('a stale held fix is not where the reader is: it is waited past, not used', async () => {
    jest.useFakeTimers();
    const old = fixAt('2026-10-20T10:30:00.000Z');
    const never = new Promise<Fix | null>(() => undefined);
    let settled: Fix | null | 'pending' = 'pending';
    void fixForSave({ current: () => never, last: () => old }, () => Date.parse('2026-10-20T10:42:18.000Z')).then((f) => (settled = f));
    await jest.advanceTimersByTimeAsync(SAVE_WAIT_MS);
    expect(settled).toBeNull();
  });
});

describe('FB-003 — saved without a position: the first fix within 5 minutes is sent as its own fact', () => {
  test('a ±10 m fix 2 minutes after the save is queued as a position item, and RW-13 says so', async () => {
    const location = new FakeLocation(null);
    const app = await mountReads({ location });
    let kept = await saveWithoutFix(app);
    expect(kept.getByTestId('kept-position')).toHaveTextContent('No position');
    const [reading] = rows(app, 'route_read');
    expect(reading!.lat).toBeNull();
    app.clock.advance(2 * 60_000 + 12_000);
    await act(async () => location.emit(fixAt(app.clock.iso())));
    const late = rows(app, 'route_position');
    expect(late).toHaveLength(1);
    expect(JSON.parse(late[0]!.payload)).toMatchObject({ for_key: reading!.id, for_kind: 'reading', route_read_id: 'r0471' });
    expect(late[0]).toMatchObject({ lat: HERE.lat + 0.0001, accuracy_m: 10, fix_at: app.clock.iso() });
    // Never written as if present at save: the reading's own row is untouched.
    expect(rows(app, 'route_read')[0]!.lat).toBeNull();
    kept = await top('RW-13');
    expect(kept.getByTestId('kept-position')).toHaveTextContent(/^Position added at \d\d:\d\d ±10 m$/);
    app.unmount();
  });

  test('only the FIRST fix attaches', async () => {
    const location = new FakeLocation(null);
    const app = await mountReads({ location });
    await saveWithoutFix(app);
    app.clock.advance(60_000);
    await act(async () => location.emit(fixAt(app.clock.iso(), 20)));
    app.clock.advance(60_000);
    await act(async () => location.emit(fixAt(app.clock.iso(), 5)));
    expect(rows(app, 'route_position')).toHaveLength(1);
    expect(rows(app, 'route_position')[0]!.accuracy_m).toBe(20);
    app.unmount();
  });

  test('a fix first arriving after 5 minutes attaches nothing', async () => {
    const location = new FakeLocation(null);
    const app = await mountReads({ location });
    await saveWithoutFix(app);
    app.clock.advance(LATE_POSITION_WINDOW_MS + 60_000);
    await act(async () => location.emit(fixAt(app.clock.iso())));
    expect(rows(app, 'route_position')).toHaveLength(0);
    expect(LATE_POSITION_WINDOW_MS).toBe(5 * 60_000);
    app.unmount();
  });

  test('a photo taken without a fix gets the same late position, against its own declaration', async () => {
    const location = new FakeLocation(null);
    const app = await mountReads({ location });
    await saveWithoutFix(app, true);
    const [declared] = rows(app, 'photo');
    expect(declared!.lat).toBeNull();
    app.clock.advance(90_000);
    await act(async () => location.emit(fixAt(app.clock.iso())));
    const late = rows(app, 'route_position').map((r) => JSON.parse(r.payload) as Record<string, unknown>);
    expect(late).toHaveLength(2);
    expect(late).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ for_kind: 'reading' }),
        expect.objectContaining({ for_kind: 'photo', for_key: declared!.id, photo_id: (JSON.parse(declared!.payload) as { photo_id: string }).photo_id }),
      ]),
    );
    app.unmount();
  });

  test('a reading saved WITH a position gets no late one', async () => {
    const location = new FakeLocation();
    const app = await mountReads({ location });
    let page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    type(page, '52410');
    await press(page, 'door-RW-13');
    app.clock.advance(60_000);
    await act(async () => location.emit(fixAt(app.clock.iso())));
    expect(rows(app, 'route_position')).toHaveLength(0);
    page = await top('RW-13');
    app.unmount();
  });
});

describe('FB-003 — a photo records its OWN position at the shutter', () => {
  test('the fix at the shutter is the photo\'s, with its time — not the save\'s', async () => {
    const shutter = fixAt('2026-10-20T10:42:15.000Z', 7, HERE.lat + 0.0002);
    const location = new FakeLocation(shutter);
    const app = await mountReads({ location });
    let page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    await press(page, 'read-photo');
    await press(await top('RW-14'), 'door-RW-13');
    // The reader walks on before saving: the save's fix is a different one.
    await act(async () => location.emit(fixAt('2026-10-20T10:42:18.000Z', 4, HERE.lat)));
    page = await top('RW-09');
    type(page, '52410');
    await press(page, 'door-RW-13');
    const [declared] = rows(app, 'photo');
    expect(declared).toMatchObject({ lat: shutter.lat, accuracy_m: 7, fix_at: shutter.fix_at });
    expect(rows(app, 'route_read')[0]).toMatchObject({ lat: HERE.lat, accuracy_m: 4 });
    app.unmount();
  });

  test('the burned-in stamp updates live when a fix arrives', async () => {
    const location = new FakeLocation(null);
    const app = await mountReads({ location });
    await app.open('RW-14', { readId: 'r0471' });
    expect((await top('RW-14')).getByTestId('stamp')).toHaveTextContent(/No position/);
    await act(async () => location.emit(fixAt(app.clock.iso(), 9, 30.1)));
    const stamp = (await top('RW-14')).getByTestId('stamp');
    expect(stamp).toHaveTextContent(/30\.100000, -97\.743061 · ±9 m/);
    app.unmount();
  });
});

describe('FB-003 — on the wire', () => {
  const base = { seq: 3, captured_at: '2026-10-20T10:44:30.000Z' };
  test('a late position travels as the reads door\'s `position`, naming what it belongs to', () => {
    const out = routeItemFromWire(
      {
        ...base,
        key: 'k-pos',
        kind: 'route_position',
        payload: { for_key: 'k-read', for_kind: 'reading', route_read_id: 'r0471' },
        location: { lat: 30.2672, lng: -97.743061, accuracy_m: 10, fix_at: '2026-10-20T10:44:30.000Z' },
        capture_token: 'tok',
      },
      'wlk-07',
    );
    expect(out).toEqual({
      key: 'k-pos',
      kind: 'position',
      route_id: 'wlk-07',
      captured_at: base.captured_at,
      for_key: 'k-read',
      for_kind: 'reading',
      position: { lat: 30.2672, lng: -97.743061, accuracy_m: 10, fix_at: '2026-10-20T10:44:30.000Z' },
      capture_token: 'tok',
    });
  });

  test('a photo declaration carries the shutter\'s position', () => {
    const out = routeItemFromWire(
      {
        ...base,
        key: 'k-photo',
        kind: 'photo',
        payload: { photo_id: 'p1', sha256: 'abc', route_read_id: 'r0471' },
        location: { lat: 30.2672, lng: -97.743061, accuracy_m: 7, fix_at: '2026-10-20T10:42:15.000Z' },
      },
      'wlk-07',
    );
    expect(out.position).toEqual({ lat: 30.2672, lng: -97.743061, accuracy_m: 7, fix_at: '2026-10-20T10:42:15.000Z' });
  });
});
