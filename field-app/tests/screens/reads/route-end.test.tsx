/**
 * Off the list and the end of the route — RW-19 … RW-29 (EP-FLD-13,
 * EP-FLD-14 §3), under the real navigation over the Maple Heights fixture.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import { fromJson } from '../../../src/db/json';
import * as assetQ from '../../../src/db/queries/asset';
import * as outboxQ from '../../../src/db/queries/outbox';
import * as routeQ from '../../../src/db/queries/route';
import * as routeReadQ from '../../../src/db/queries/routeRead';
import * as walkQ from '../../../src/db/queries/readsWalk';
import * as templatesQ from '../../../src/db/queries/workOrderTemplates';
import * as settingsQ from '../../../src/db/queries/settings';
import { deviceWide, scoped } from '../../../src/db/scoped';
import { periodOf } from '../../../src/screens/reads/mine';
import type { FindingsPort } from '../../../src/screens/reads/services';
import { LIST_KEYS } from '../../../src/screens/reads/records';
import { RAY } from './fixture';
import { mountReads } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

type App = Awaited<ReturnType<typeof mountReads>>;

async function press(page: ReturnType<typeof within>, id: string) {
  await act(async () => {
    fireEvent.press(page.getByTestId(id));
  });
}

function capture(app: App, id: string, v: { value: string | null; status: 'read' | 'could_not_read' | 'read_with_problem'; reason?: string; warned?: boolean; at?: string }) {
  routeReadQ.recordCapture(scoped(app.db, RAY), id, {
    captureKey: `cap-${id}`,
    value: v.value,
    unit: 'gal',
    readerStatus: v.status,
    noReadReason: v.reason ?? null,
    warnedAccepted: v.warned ?? false,
    capturedAt: v.at ?? '2026-10-20T09:00:00.000Z',
    capturedBy: RAY,
    identifiedBy: 'listed',
    readMethod: 'walk',
  });
}

describe('RW-19 Not on the route', () => {
  test('a known meter off the route is read anyway, marked off-route (R84, US-FLD-061 TC-1)', async () => {
    const app = await mountReads();
    const page = within((await app.open('RW-19', { code: '90118', stopId: 's1318' }))!);
    expect(page.getByTestId('known')).toHaveTextContent('Scanned 90118. It is in the system.');
    expect(page.getByTestId('known-card')).toHaveTextContent(/MTR-0903/);
    expect(page.getByTestId('known-card')).toHaveTextContent(/1318 Maple Street/);
    await press(page, 'door-RW-09');
    expect(app.current()).toBe('RW-09');
    const id = app.currentParams()!.readId!;
    const row = walkQ.meter(scoped(app.db, RAY), id)!;
    expect(row).toMatchObject({ asset_id: 'a0903', off_route: 1, unit: 'gal', state: 'unread' });
    const entry = within((await screen.findAllByTestId('screen-RW-09')).at(-1)!);
    for (const d of '1234') fireEvent.press(entry.getByTestId(`keypad-${d}`));
    await press(entry, 'door-RW-13');
    const payload = fromJson<Record<string, unknown>>(outboxQ.listMine(scoped(app.db, RAY), { limit: 10 })[0]!.payload)!;
    expect(payload).toMatchObject({ off_route: true, asset_id: 'a0903', value: '1234', unit: 'gal' });
    app.unmount();
  });

  test('a code the system does not know offers to add the meter', async () => {
    const app = await mountReads();
    const page = within((await app.open('RW-19', { code: '90241', stopId: 's1318' }))!);
    expect(page.getByTestId('unknown')).toHaveTextContent('90241 is not in the system.');
    expect(page.queryByTestId('door-RW-09')).toBeNull();
    await press(page, 'door-RW-20');
    expect(app.current()).toBe('RW-20');
    expect(app.currentParams()).toMatchObject({ code: '90241', stopId: 's1318' });
    app.unmount();
  });

  test('a known meter with no unit cannot be read off-route — the unit is never assumed (hard rule 3)', async () => {
    const app = await mountReads();
    const page = within((await app.open('RW-19', { code: '90876', stopId: 's1318' }))!);
    expect(page.getByTestId('door-RW-09')).toBeDisabled();
    expect(page.getByText('No unit known for this meter.')).toBeTruthy();
    app.unmount();
  });
});

describe('RW-20 Add a meter', () => {
  test('pending until accepted, photo required, address from the premises — never typed (R85, R86, US-FLD-061 TC-2, TC-4, TC-5)', async () => {
    const app = await mountReads();
    settingsQ.set(app.db, LIST_KEYS.services, [{ code: 'water', label: 'Water' }, { code: 'electric', label: 'Electric' }], '2026-10-20T10:00:00.000Z');
    settingsQ.set(app.db, LIST_KEYS.sizes, [{ code: '5_8', label: '5/8"' }, { code: '3_4', label: '3/4"' }], '2026-10-20T10:00:00.000Z');
    const page = within((await app.open('RW-20', { code: '90241', stopId: 's1318' }))!);
    expect(page.getByTestId('add-where')).toHaveTextContent('1318 Maple Street');
    expect(page.queryByLabelText(/address/i)).toBeNull();
    expect(page.getByText('It bills once accepted.')).toBeTruthy();
    await press(page, 'add-service-water');
    await press(page, 'add-size-5_8');
    expect(page.getByTestId('door-RW-06')).toBeDisabled(); // the photo is required
    await press(page, 'add-photo');
    await press(page, 'door-RW-06');
    expect(app.current()).toBe('RW-06');
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`RW-20 → ${app.current()}`).toBe('RW-20 → RW-06');
    const out = outboxQ.listMine(scoped(app.db, RAY), { limit: 10 }).find((o) => o.kind === 'field_asset')!;
    // The reads door takes it as `add_meter` since INTEGRATE-2 (`routeReads.ts`).
    expect(out.channel).toBe('route');
    const p = fromJson<Record<string, unknown>>(out.payload)!;
    expect(p).toMatchObject({ badge: '90241', service: 'water', size: '5_8', premise_id: 'p1318' });
    const added = assetQ.get(app.db, p.asset_id as string)!;
    expect(added).toMatchObject({ status: 'pending', outbox_id: out.id, premise_id: 'p1318' });
    app.unmount();
  });

  test('with no service or size list on the phone it says so rather than offering one from code', async () => {
    const app = await mountReads();
    const page = within((await app.open('RW-20', { code: '90241', stopId: 's1318' }))!);
    expect(page.getAllByText('This list is not on the phone yet.')).toHaveLength(2);
    expect(page.getByTestId('door-RW-06')).toBeDisabled();
    app.unmount();
  });
});

describe('RW-21 Raise it', () => {
  test('filled in for the reader, photo required, sent to the reads door on the route channel (BR-WRK-067)', async () => {
    const app = await mountReads();
    settingsQ.set(app.db, LIST_KEYS.raiseFindings, [{ code: 'leak', label: 'Leak' }, { code: 'damaged', label: 'Damaged meter' }], '2026-10-20T10:00:00.000Z');
    settingsQ.set(app.db, LIST_KEYS.raiseUrgency, [{ code: 'now', label: 'Now' }, { code: 'week', label: 'This week' }], '2026-10-20T10:00:00.000Z');
    const page = within((await app.open('RW-21', { readId: 'r0471' }))!);
    expect(page.getByTestId('filled-in')).toHaveTextContent(/1318 Maple Street · Unit A · ACC-10294 · MTR-0471 · 30\.2672, -97\.7431/);
    await press(page, 'findings-leak');
    await press(page, 'urgency-now');
    expect(page.getByTestId('door-RW-06')).toBeDisabled();
    await press(page, 'raise-photo');
    await press(page, 'door-RW-06');
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`RW-21 → ${app.current()}`).toBe('RW-21 → RW-06');
    const out = outboxQ.listMine(scoped(app.db, RAY), { limit: 10 }).find((o) => o.kind === 'route_finding')!;
    expect(out.channel).toBe('route');
    expect(fromJson<Record<string, unknown>>(out.payload)).toMatchObject({ finding: 'leak', urgency: 'now', premise_id: 'p1318', asset_id: 'a0471' });
    app.unmount();
  });
});

describe('RW-22 Where you are and RW-23 Still to do', () => {
  test('done of total, counted from the readings themselves (US-FLD-040 TC-4); no pace shown (R120)', async () => {
    const app = await mountReads();
    capture(app, 'r0471', { value: '52410', status: 'read', at: '2026-10-20T08:10:00.000Z' });
    capture(app, 'r0472', { value: '71400', status: 'read_with_problem', warned: true, at: '2026-10-20T09:10:00.000Z' });
    capture(app, 'r1206', { value: null, status: 'could_not_read', reason: 'Dog', at: '2026-10-20T09:20:00.000Z' });
    const page = within((await app.open('RW-22', { routeId: 'wlk-07' }))!);
    expect(page.getByTestId('done-of-total')).toHaveTextContent('3 of 10 done');
    expect(page.getByTestId('stat-read')).toHaveTextContent(/2/);
    expect(page.getByTestId('stat-could-not')).toHaveTextContent(/1/);
    expect(page.getByTestId('stat-left')).toHaveTextContent(/7/);
    expect(page.getByTestId('door-RW-23')).toHaveTextContent(/1 flagged for the office/);
    expect(page.queryByText(/minutes left|per hour|pace/i)).toBeNull();
    // Changing a row changes the count — nothing stored.
    capture(app, 'r42', { value: '4100', status: 'read' });
    await app.open('RW-05', { routeId: 'wlk-07' }); // away and back: the screen reads again as it comes into view
    const again = within((await app.open('RW-22', { routeId: 'wlk-07' }))!);
    expect(again.getByTestId('done-of-total')).toHaveTextContent('4 of 10 done');
    for (const [door, to] of [
      ['door-RW-23', 'RW-23'],
      ['door-RW-24', 'RW-24'],
      ['door-RW-25', 'RW-25'],
      ['door-RW-05', 'RW-05'],
    ] as const) {
      const p = within((await app.open('RW-22', { routeId: 'wlk-07' }))!);
      await press(p, door);
      expect(`${door} → ${app.current()}`).toBe(`${door} → ${to}`);
    }
    app.unmount();
  });

  test('RW-23: not read / came back to / flagged, nearest first', async () => {
    const app = await mountReads();
    capture(app, 'r1206', { value: null, status: 'could_not_read', reason: 'Dog', at: '2026-10-20T11:14:00.000Z' });
    capture(app, 'r1240', { value: '2600', status: 'read_with_problem', warned: true });
    const page = within((await app.open('RW-23', { routeId: 'wlk-07' }))!);
    expect(page.getByTestId('still-tabs-not_read')).toHaveTextContent('Not read · 4');
    expect(page.getByTestId('still-tabs-came_back')).toHaveTextContent('Came back to · 1');
    expect(page.getByTestId('still-tabs-flagged')).toHaveTextContent('Flagged · 1');
    expect(page.getByTestId('todo-0')).toHaveTextContent(/1318 Maple Street/);
    await press(page, 'still-tabs-came_back');
    expect(page.getByTestId('todo-0')).toHaveTextContent(/1206 Maple Street.*Dog/);
    await press(page, 'door-RW-06');
    expect(app.currentParams()?.stopId).toBe('s1206');
    app.unmount();
  });
});

describe('RW-24 Photos', () => {
  test('every route photo, by address, sent or waiting (US-FLD-067 TC-2)', async () => {
    const app = await mountReads();
    let page = within((await app.open('RW-09', { readId: 'r1322' }))!);
    for (const d of '1200') fireEvent.press(page.getByTestId(`keypad-${d}`));
    await press(page, 'read-photo');
    await press(within((await screen.findAllByTestId('screen-RW-14')).at(-1)!), 'door-RW-13');
    page = within((await screen.findAllByTestId('screen-RW-09')).at(-1)!);
    await press(page, 'door-RW-13');
    const photos = within((await app.open('RW-24', { routeId: 'wlk-07' }))!);
    expect(photos.getByTestId('photo-line')).toHaveTextContent('0 sent · 1 waiting');
    expect(photos.getByText('1322 Maple Street · 1')).toBeTruthy();
    expect(photos.getAllByTestId(/^photo-.*-waiting$/)).toHaveLength(1);
    await press(photos, 'door-RW-22');
    expect(app.current()).toBe('RW-22');
    app.unmount();
  });
});

describe('RW-25 Turn it in, RW-26 Sending, RW-27 Turned in', () => {
  test('with meters unread, the primary sends the reader back; turning in anyway is second, danger tier (US-FLD-040 TC-2)', async () => {
    const app = await mountReads();
    capture(app, 'r0471', { value: '52410', status: 'read' });
    capture(app, 'r1206', { value: null, status: 'could_not_read', reason: 'Dog' });
    const page = within((await app.open('RW-25', { routeId: 'wlk-07' }))!);
    expect(page.getByTestId('go-read')).toHaveTextContent('Go and read the 8');
    expect(page.getByTestId('door-RW-26')).toHaveTextContent('Turn in 2 of 10');
    expect(page.getByTestId('unread-card')).toHaveTextContent(/8 not read at all/);
    // The ladder: the way back first, the danger act under it.
    const buttons = page.getAllByRole('button').map((b) => b.props.testID).filter((id) => id === 'go-read' || id === 'door-RW-26');
    expect(buttons).toEqual(['go-read', 'door-RW-26']);
    await press(page, 'go-read');
    expect(app.current()).toBe('RW-23');
    const again = within((await app.open('RW-25', { routeId: 'wlk-07' }))!);
    await press(again, 'door-RW-26');
    expect(app.current()).toBe('RW-26');
    expect(routeQ.listMine(scoped(app.db, RAY)).find((r) => r.id === 'wlk-07')?.status).toBe('turned_in');
    expect(app.sent.length).toBeGreaterThan(0);
    app.unmount();
  });

  test('RW-26 shows the readings waiting on the phone while no route door exists', async () => {
    const app = await mountReads();
    capture(app, 'r0471', { value: '52410', status: 'read' });
    const page = within((await app.open('RW-26', { routeId: 'wlk-07' }))!);
    expect(page.getByTestId('sent-of')).toHaveTextContent('0 of 1 sent');
    expect(page.getByTestId('row-waiting')).toHaveTextContent('1 waiting on this phone');
    expect(await page.findByTestId('still-waiting')).toBeTruthy();
    await press(page, 'door-RW-27');
    expect(app.current()).toBe('RW-27');
    app.unmount();
  });

  test('RW-27 names what did NOT land as plainly as what did, refusals included (US-FLD-040 TC-3)', async () => {
    const app = await mountReads();
    capture(app, 'r0471', { value: '52410', status: 'read' });
    capture(app, 'r0472', { value: '30500', status: 'read' });
    capture(app, 'r1206', { value: null, status: 'could_not_read', reason: 'Dog' });
    const s = scoped(app.db, RAY);
    // The office's answers, applied to the rows they answer.
    outboxQ.insert(s, { id: 'cap-r0472', workOrderId: null, routeId: 'wlk-07', kind: 'route_read', channel: 'route', payload: {}, seq: 1, capturedBy: RAY, capturedAt: '2026-10-20T09:00:00.000Z', location: null });
    app.db.transaction(() => {
      routeReadQ.setStateByKey(app.db._raw, 'cap-r0471', 'accepted');
      routeReadQ.setStateByKey(app.db._raw, 'cap-r1206', 'accepted');
      routeReadQ.setStateByKey(app.db._raw, 'cap-r0472', 'refused');
      outboxQ.refuse(app.db._raw, 'cap-r0472', { message: 'the meter was taken out on 14 Oct' });
    });
    const page = within((await app.open('RW-27', { routeId: 'wlk-07' }))!);
    expect(page.getByTestId('office-has-it')).toHaveTextContent('The office has it');
    expect(page.getByTestId('landed-readings')).toHaveTextContent(/2/);
    expect(page.getByTestId('landed-reason')).toHaveTextContent(/1/);
    expect(page.getByTestId('never-read')).toHaveTextContent(/7 never read/);
    expect(page.getByTestId('refused-r0472')).toHaveTextContent(/MTR-0472 — the meter was taken out on 14 Oct/);
    expect(page.getByTestId('refused-r0472')).toHaveTextContent(/Yours/);
    expect(page.getByText('Kept on this phone for 14 days.')).toBeTruthy();
    await press(page, 'door-RW-06');
    expect(app.current()).toBe('RW-06');
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`RW-27 → ${app.current()}`).toBe('RW-27 → RW-06');
    expect(app.currentParams()?.readId).toBe('r0472');
    app.unmount();
  });
});

describe('RW-28 My reads and RW-29 Reading settings', () => {
  test('RW-28: what was read, not how fast (R120, US-FLD-040 TC-5)', async () => {
    const app = await mountReads();
    capture(app, 'r0471', { value: '52410', status: 'read', at: '2026-10-20T09:00:00.000Z' });
    capture(app, 'r1206', { value: null, status: 'could_not_read', reason: 'Dog', at: '2026-10-20T09:05:00.000Z' });
    const page = within((await app.open('RW-28'))!);
    expect(page.getByTestId('mine-read')).toHaveTextContent(/^1/);
    expect(page.getByTestId('mine-could-not')).toHaveTextContent(/^1/);
    expect(page.getByTestId('mine-routes')).toHaveTextContent(/^1/);
    expect(page.getByText('What you read, not how fast.')).toBeTruthy();
    await press(page, 'door-RW-27');
    expect(app.current()).toBe('RW-27');
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`RW-28 → ${app.current()}`).toBe('RW-28 → RW-27');
    app.unmount();
  });

  test('periodOf: last seven days, then the latest cycle, then earlier', () => {
    const now = new Date('2026-10-20T12:00:00.000Z');
    const card = (at: string | null, cycle: string) => ({ last_captured_at: at, turned_in_at: null, cycle }) as unknown as walkQ.RouteCard;
    expect(periodOf(card('2026-10-15T12:00:00.000Z', 'X'), now, 'WTR-M Oct')).toBe('week');
    expect(periodOf(card('2026-10-01T12:00:00.000Z', 'WTR-M Oct'), now, 'WTR-M Oct')).toBe('cycle');
    expect(periodOf(card('2026-09-01T12:00:00.000Z', 'WTR-M Sep'), now, 'WTR-M Oct')).toBe('earlier');
  });

  test('RW-29: the choices stick and change the reading screens', async () => {
    const app = await mountReads();
    const page = within((await app.open('RW-29'))!);
    await press(page, 'set-order-walk');
    await press(page, 'set-scan');
    await press(page, 'set-keypad-largest');
    expect(fromJson<Record<string, unknown>>(app.services.prefs.getString('reads.settings'))).toMatchObject({ order: 'walk', scanFirst: true, keypad: 'largest' });
    // The walk now opens on walk order.
    const walk = within((await app.open('RW-05', { routeId: 'wlk-07' }))!);
    expect(walk.getByTestId('stop-0')).toHaveTextContent(/1240 Maple Street/);
    // Scan before reading: Start goes to the scan, not the keypad.
    const stop = within((await app.open('RW-06', { stopId: 's1318' }))!);
    await press(stop, 'door-RW-09');
    expect(app.current()).toBe('RW-11');
    const back = within((await app.open('RW-29'))!);
    await press(back, 'door-FF-51');
    expect(app.current()).toBe('FF-51');
    app.unmount();
  });

  test('a finding a rule took shows its work order; an open one offers Create work order, once', async () => {
    const created: Array<[string, unknown]> = [];
    const findings: FindingsPort = {
      options: () => Promise.resolve({ kinds: [], urgencies: [], priorities: [{ id: 'pr-1', code: 'P1', name: 'Same day', rank: 1 }] }),
      get: (key) => Promise.resolve({ key, kind: 'broken_seal', status: 'open', conversion: null, work_order: null }),
      createWorkOrder: (key, body) => {
        created.push([key, body]);
        return Promise.resolve({ key, kind: 'broken_seal', status: 'work_order_created', conversion: 'by_hand', work_order: { id: 'wo-1', order_no: 'WO-4871' } });
      },
    };
    const app = await mountReads({ findings });
    templatesQ.upsert(app.db, { id: 'tpl-seal', name: 'Seal check', version: '2' }, '2026-10-20T10:00:00.000Z');
    const s = scoped(app.db, RAY);
    const at = '2026-10-20T10:05:00.000Z';
    const base = { workOrderId: null, routeId: 'rt1', channel: 'route' as const, capturedBy: RAY, location: null };
    outboxQ.insert(s, { ...base, id: 'f-leak', kind: 'route_finding', seq: 1, capturedAt: at, payload: { finding: 'leak', route_read_id: 'r0471' } });
    outboxQ.insert(s, { ...base, id: 'f-seal', kind: 'route_finding', seq: 2, capturedAt: at, payload: { finding: 'broken_seal', route_read_id: 'r0471' } });
    outboxQ.settle(deviceWide(app.db, 'receipt'), 'f-leak', 'accepted', at, { finding: { key: 'f-leak', kind: 'leak', status: 'work_order_created', conversion: 'by_rule', work_order: { id: 'wo-0', order_no: 'WO-4870' } } });
    outboxQ.settle(deviceWide(app.db, 'receipt'), 'f-seal', 'accepted', at, { finding: { key: 'f-seal', kind: 'broken_seal', status: 'open', conversion: null, work_order: null } });
    const page = within((await app.open('RW-21', { readId: 'r0471' }))!);
    expect(page.getByTestId('finding-order-f-leak')).toHaveTextContent('WO-4870 created');
    expect(page.queryByTestId('finding-create-f-leak')).toBeNull();
    await press(page, 'finding-create-f-seal');
    await press(page, 'finding-templates-tpl-seal');
    await press(page, 'finding-priority-pr-1');
    await press(page, 'finding-create-send');
    expect(created).toEqual([['f-seal', { template_id: 'tpl-seal', priority_id: 'pr-1' }]]);
    expect(page.getByTestId('finding-order-f-seal')).toHaveTextContent('WO-4871 created');
    expect(page.queryByTestId('finding-create-f-seal')).toBeNull();
    app.unmount();
  });
});
