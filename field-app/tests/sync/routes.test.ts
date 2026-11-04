/**
 * The route mode's server doors (`sync/routes.ts`, `sync/routeReads.ts`,
 * `HttpTransport`): a reading on the wire as `POST work/mobile/reads/sync`
 * reads it, the server's answer as the outbox's receipts read it, and a route
 * downloaded page by page into the store — never a register without its unit.
 */
import * as routeQ from '../../src/db/queries/route';
import * as routeReadQ from '../../src/db/queries/routeRead';
import * as walkQ from '../../src/db/queries/readsWalk';
import * as settingsQ from '../../src/db/queries/settings';
import { deviceWide, scoped } from '../../src/db/scoped';
import { capture, sendPending } from '../../src/sync/outbox';
import { batchAnswerFromReads, routeItemFromWire } from '../../src/sync/routeReads';
import { CANT_READ_KEY, downloadRoutes, readId, registerOfReadId, type RoutesApi, stopId } from '../../src/sync/routes';
import { HttpTransport, type WireItem } from '../../src/sync/transport';
import { FakeClock, idSource, openStore } from '../db/support/fixtures';

const item: WireItem = {
  key: 'cap-1',
  kind: 'route_read',
  seq: 1,
  captured_at: '2026-10-20T10:42:18.000Z',
  payload: {
    route_read_id: 'r1',
    meter_no: 'MTR-0471',
    premises_id: 'p-1',
    register: 'total',
    value: '52410',
    unit: 'gal',
    reader_status: 'read_with_problem',
    no_read_reason: null,
    warned_accepted: true,
    identified_by: 'scan',
    remark: 'Lid cracked',
    remark_source: 'typed',
    fix_quality: 'good',
  },
  location: { lat: 30.26, lng: -97.74, accuracy_m: 4, fix_at: '2026-10-20T10:42:00.000Z' },
};

test('a route reading on the wire, as the server reads it', () => {
  expect(routeItemFromWire(item, 'route-1')).toEqual({
    key: 'cap-1',
    kind: 'reading',
    route_id: 'route-1',
    captured_at: '2026-10-20T10:42:18.000Z',
    reader_status: 'read_with_problem',
    identified_by: 'scan',
    meter_no: 'MTR-0471',
    premises_id: 'p-1',
    register: 'total',
    value: '52410',
    unit: 'gal',
    remark: 'Lid cracked',
    remark_source: 'typed',
    accepted_anyway: true,
    position: { lat: 30.26, lng: -97.74, accuracy_m: 4, fix_quality: 'good' },
  });
});

test('the server’s answer as receipts: held is kept for the office, refused is shown, an unknown key is no answer', () => {
  const two = { ...item, key: 'cap-2', seq: 2 };
  const three = { ...item, key: 'cap-3', seq: 3 };
  const answer = batchAnswerFromReads([item, two, three], {
    server_time: '2026-10-20T11:00:00Z',
    items: [
      { key: 'cap-1', result: 'held_for_review', outcome: 'held', reason: 'value_unreadable' },
      { key: 'cap-2', result: 'refused', outcome: 'refused' },
      { key: 'someone-else', result: 'accepted' },
    ],
  });
  expect(answer.acknowledged).toEqual(['cap-1']);
  expect(answer.items.map((i) => [i.key, i.result])).toEqual([
    ['cap-1', 'held_for_review'],
    ['cap-2', 'refused'],
  ]);
  expect(answer).toMatchObject({ held_for_review: 1, refused: 1, accepted: 0 });
});

test('HttpTransport posts readings to work/mobile/reads/sync under the bearer token', async () => {
  const calls: Array<[string, RequestInit]> = [];
  const fetchImpl = jest.fn(async (url: string, init: RequestInit) => {
    calls.push([url, init]);
    return { ok: true, status: 200, json: async () => ({ items: [{ key: 'cap-1', result: 'accepted', outcome: 'posted' }] }) };
  });
  const t = new HttpTransport({ origin: 'https://x', tenant: 'silver-creek', accessToken: () => 'acc', fetchImpl: fetchImpl as unknown as typeof fetch });
  const answer = await t.sendRouteReads('route-1', [item]);
  expect(calls[0]?.[0]).toBe('https://x/api/silver-creek/work/mobile/reads/sync');
  expect((calls[0]?.[1].headers as Record<string, string>).Authorization).toBe('Bearer acc');
  expect(JSON.parse(String(calls[0]?.[1].body)).items[0]).toMatchObject({ key: 'cap-1', kind: 'reading', route_id: 'route-1' });
  expect(answer.acknowledged).toEqual(['cap-1']);
});

test('a route downloads page by page; a register with no unit is not stored; the can’t-read list is the utility’s', async () => {
  const db = openStore('silver-creek');
  const meter = (asset: string, no: string, registers: Array<{ register: string; unit: string | null }>) => ({
    asset_id: asset,
    meter_no: no,
    serial_no: `S-${no}`,
    parent_meter_no: null,
    service: 'water',
    size_class: '5/8"',
    read_method: null,
    location_note: null,
    unit_label: 'Unit A',
    account_no: 'ACC-1',
    customer_name: 'Carla Ruiz',
    registers: registers.map((r) => ({ ...r, previous: { value: '48210', read_on: '2026-09-20' }, expected: { low: '40000', high: '56000' } })),
  });
  const card = { id: 'route-1', code: 'WLK-07', name: 'Maple Heights', route_type: 'walk', services: ['water'], window: { start: '2026-10-20T00:00:00Z', end: '2026-10-24T23:00:00Z' } };
  const stop = (premises: string, order: number, meters: ReturnType<typeof meter>[]) => ({
    premises_id: premises,
    premise_no: null,
    position: order,
    walk_order: order,
    address: { line: `${order} Maple Street`, city: 'Austin', state: 'TX', postal_code: '78704' },
    point: { lat: '30.2672', lng: '-97.7431' },
    meters,
  });
  const api: RoutesApi = {
    myRoutes: async () => ({ results: [card], next_page: null }),
    routePage: async (_id, page) =>
      page === 1
        ? { route: card, stops: [stop('p-1', 1, [meter('a-1', 'MTR-1', [{ register: 'total', unit: 'gal' }])])], next_page: 2 }
        : { route: card, stops: [stop('p-2', 2, [meter('a-2', 'MTR-2', [{ register: 'total', unit: null }])])], next_page: null },
    turnIn: async () => ({}),
    cantReadReasons: async () => ({ results: [{ code: 'dog', name: 'Dog' }, { code: 'old', name: 'Old', active: false }] }),
  };
  const summary = await downloadRoutes(db, 'tech-ray', api, () => new Date('2026-10-20T07:00:00Z'));
  expect(summary).toEqual({ routes: 1, stops: 2, readings: 1, skippedNoUnit: 1, removed: 0, keptForUnsentWork: 0 });
  const s = scoped(db, 'tech-ray');
  expect(routeQ.listMine(s).map((r) => [r.id, r.code])).toEqual([['route-1', 'WLK-07']]);
  const id = readId('route-1', 'a-1', 'total');
  expect(walkQ.meter(s, id)).toMatchObject({ unit: 'gal', previous_value: '48210', stop_id: stopId('route-1', 'p-1'), serial: 'MTR-1' });
  expect(registerOfReadId(id, 'route-1')).toBe('total');
  expect(routeReadQ.captureKeysFor(s, 'route-1')).toEqual([]);
  expect(settingsQ.get(db, CANT_READ_KEY)).toEqual([{ code: 'dog', label: 'Dog' }]);
});

test('DEF-FLD-10357/10358: a route reading with a photograph — the reading names it, the declaration is a `photo` item, each carries its captor, and the bytes go to the link the reads door answered', async () => {
  const db = openStore('silver-creek');
  const clock = new FakeClock();
  const ids = idSource('k');
  const { key } = capture(
    db,
    { technicianId: 'ray', capturedBy: 'ray' },
    {
      kind: 'route_read',
      routeId: 'route-1',
      payload: { meter_no: 'MTR-0471', reader_status: 'read', value: '48400', unit: 'kWh' },
      photos: [{ localPath: '/p/plate.jpg', sha256: 'a'.repeat(64), bytes: 9, target: { route_read_id: 'm-1' } }],
    },
    { newId: ids, clock },
  );
  const sent: Array<Record<string, unknown>> = [];
  const fetchImpl = jest.fn(async (url: string, init: RequestInit) => {
    const items = JSON.parse(String(init.body)).items as Array<Record<string, unknown>>;
    sent.push(...items);
    return {
      ok: true,
      status: 200,
      json: async () => ({
        items: items.map((i) =>
          i.kind === 'photo'
            ? { key: i.key, result: 'accepted', outcome: 'recorded', photo_id: i.photo_id, upload_url: `/api/silver-creek/work/mobile/reads/photos/${String(i.photo_id)}` }
            : { key: i.key, result: 'accepted', outcome: 'posted' },
        ),
      }),
    };
  });
  const t = new HttpTransport({ origin: 'https://x', tenant: 'silver-creek', accessToken: () => 'acc', fetchImpl: fetchImpl as unknown as typeof fetch });
  await sendPending(db, t, { clock, tokens: { tokenFor: () => 'capture-of-ray' }, random: () => 0.5 });
  const [reading, declaration] = sent;
  expect(reading).toMatchObject({ key, kind: 'reading', capture_token: 'capture-of-ray' });
  expect(declaration).toMatchObject({ kind: 'photo', sha256: 'a'.repeat(64), capture_token: 'capture-of-ray' });
  expect(reading?.photos).toEqual([declaration?.photo_id]);
  const photo = deviceWide(db, 'count').get<{ upload_url: string | null }>('SELECT upload_url FROM photo');
  expect(photo?.upload_url).toBe(`/api/silver-creek/work/mobile/reads/photos/${String(declaration?.photo_id)}`);
});

// ── DEF-FLD-10592 (MQ-033, PO 2026-10-24) — a route taken away leaves the phone ──

function twoRouteWorld() {
  const card = (id: string, code: string) => ({ id, code, name: code, route_type: 'walk', services: ['water'] });
  const stopFor = (premises: string) => ({
    premises_id: premises,
    premise_no: null,
    position: 1,
    walk_order: 1,
    address: null,
    point: null,
    meters: [
      {
        asset_id: `a-${premises}`,
        meter_no: `MTR-${premises}`,
        serial_no: null,
        parent_meter_no: null,
        service: 'water',
        size_class: null,
        read_method: null,
        location_note: null,
        unit_label: null,
        account_no: null,
        customer_name: null,
        registers: [{ register: 'total', unit: 'gal', previous: null, expected: null }],
      },
    ],
  });
  let assigned = ['route-1', 'route-2'];
  let listPages: 'whole' | 'cut' = 'whole';
  const api: RoutesApi = {
    myRoutes: async () => {
      if (listPages === 'cut') throw new Error('network gone');
      return { results: assigned.map((id) => card(id, id.toUpperCase())), next_page: null };
    },
    routePage: async (id) => ({ route: card(id, id.toUpperCase()), stops: [stopFor(`p-${id}`)], next_page: null }),
    turnIn: async () => ({}),
    cantReadReasons: async () => ({ results: [] }),
  };
  return {
    api,
    reassign: (ids: string[]) => {
      assigned = ids;
    },
    cutTheList: () => {
      listPages = 'cut';
    },
  };
}

const at = () => new Date('2026-10-24T07:00:00Z');

test('a route reassigned to someone else leaves this phone with its stops and readings', async () => {
  const db = openStore('silver-creek');
  const world = twoRouteWorld();
  await downloadRoutes(db, 'tech-ray', world.api, at);
  const s = scoped(db, 'tech-ray');
  expect(routeQ.listMine(s).map((r) => r.id)).toEqual(['route-1', 'route-2']);

  world.reassign(['route-1']);
  const summary = await downloadRoutes(db, 'tech-ray', world.api, at);
  expect(summary).toMatchObject({ routes: 1, removed: 1, keptForUnsentWork: 0 });
  expect(routeQ.listMine(s).map((r) => r.id)).toEqual(['route-1']);
  expect(routeReadQ.progress(s, 'route-2')).toEqual({ total: 0, read: 0 });
  const stops = deviceWide(db, 'count').get<{ n: number }>("SELECT COUNT(*) AS n FROM route_stop WHERE route_id = 'route-2'");
  expect(stops?.n).toBe(0);
});

test('a route taken away while a reading on it is unsent STAYS until it is sent (R60)', async () => {
  const db = openStore('silver-creek');
  const world = twoRouteWorld();
  await downloadRoutes(db, 'tech-ray', world.api, at);
  capture(
    db,
    { technicianId: 'tech-ray', capturedBy: 'tech-ray' },
    { kind: 'route_read', routeId: 'route-2', payload: { meter_no: 'MTR-p-route-2', reader_status: 'read', value: '120', unit: 'gal' } },
    { newId: idSource('k'), clock: new FakeClock() },
  );
  world.reassign(['route-1']);
  const s = scoped(db, 'tech-ray');

  const kept = await downloadRoutes(db, 'tech-ray', world.api, at);
  expect(kept).toMatchObject({ removed: 0, keptForUnsentWork: 1 });
  expect(routeQ.listMine(s).map((r) => r.id)).toEqual(['route-1', 'route-2']);

  // The reading reaches the server; the next download takes the route.
  deviceWide(db, 'receipt').run("UPDATE outbox SET state = 'accepted' WHERE route_id = 'route-2'");
  const gone = await downloadRoutes(db, 'tech-ray', world.api, at);
  expect(gone).toMatchObject({ removed: 1, keptForUnsentWork: 0 });
  expect(routeQ.listMine(s).map((r) => r.id)).toEqual(['route-1']);
});

test('a download that fails part-way removes nothing', async () => {
  const db = openStore('silver-creek');
  const world = twoRouteWorld();
  await downloadRoutes(db, 'tech-ray', world.api, at);
  world.cutTheList();
  await expect(downloadRoutes(db, 'tech-ray', world.api, at)).rejects.toThrow('network gone');
  expect(routeQ.listMine(scoped(db, 'tech-ray')).map((r) => r.id)).toEqual(['route-1', 'route-2']);
});
