/**
 * T-29 — the 25 two-pane boards whose detail is drawn as part of the same
 * screen, each mounted under the REAL navigator at the board's 1024 × 768
 * from one fixture store, by its address (never bare — hard-won law 2's
 * fixture lesson), the way `t28Layouts.test.tsx` mounts the eight.
 *
 * For each board: the T2 frame with BOTH panes, the phone screen in the list
 * pane, the drawn detail beside it, a pick that keeps the route and moves the
 * detail — and EVERY door on the detail pane pressed and followed to the
 * screen it opens (or, for an act that is not a door, to what it does).
 *
 * And held upright (768 × 1024), where the detail pane cannot keep 260
 * (R122): the phone screen alone, no list pane.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import * as documentQ from '../../src/db/queries/document';
import * as outboxQ from '../../src/db/queries/outbox';
import * as routeReadQ from '../../src/db/queries/routeRead';
import { deviceWide, scoped } from '../../src/db/scoped';
import { capture } from '../../src/sync/outbox';
import { type ScreenId } from '../../src/navigation/screens';
import { type NearbyJob } from '../../src/screens/theDay/nearbyApi';
import { boardVan, boardWeek } from '../screens/me/support';
import { DANA, MARCO } from '../screens/onSite/fixture';
import { frameOf, mountTablet, setWindow } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./harness').tabletWindow,
}));

type Instance = typeof screen.UNSAFE_root;
type App = Awaited<ReturnType<typeof mountTablet>>;

const PECAN: NearbyJob = {
  id: 'wo-4840',
  number: 'WO-4840',
  type: 'Routine read',
  priorityCode: 'P3',
  address: '218 Pecan Grove',
  distanceMi: 0.4,
  dueAt: '2026-10-22T17:00:00.000Z',
  estMinutes: 10,
  takenBy: null,
};
const CEDAR: NearbyJob = { ...PECAN, id: 'wo-4838', number: 'WO-4838', type: 'Meter seal check', address: '95 Cedar Court', distanceMi: 0.9 };

function fakeNearby() {
  return {
    list: jest.fn(async () => ({ jobs: [PECAN, CEDAR], count: 2, hasMore: false })),
    claim: jest.fn(async () => ({ ok: true as const })),
  };
}

/** The two panes of the board holding `id`; fails when either is missing. */
function panes(id: ScreenId): { frame: Instance; list: Instance; detail: Instance } {
  const frame = frameOf(id);
  expect(frame.props.testID).toBe('tablet-frame-T2');
  return {
    frame,
    list: within(frame).getByTestId('tablet-pane-list'),
    detail: within(frame).getByTestId('tablet-pane-detail'),
  };
}

const settle = async () => {
  await act(async () => {
    await Promise.resolve();
  });
  await act(async () => undefined);
};

/** Press a door on the board's detail pane and say where the app went; then come back. */
async function door(app: App, from: ScreenId, testID: string, params?: Record<string, unknown>): Promise<string | undefined> {
  fireEvent.press(within(panes(from).detail).getByTestId(testID));
  await settle();
  const went = app.current();
  await app.open(from, params);
  await settle();
  return went;
}

beforeEach(() => setWindow(1024, 768));

describe('the day', () => {
  test('FF-11 Nearby: the list beside the first job; a card picks; On the map and Claim it', async () => {
    const nearby = fakeNearby();
    const app = await mountTablet({ nearby });
    await app.open('FF-11');
    await settle();
    let p = panes('FF-11');
    expect(within(p.list).getByTestId('screen-FF-11')).toBeTruthy();
    const card = within(p.detail).getByTestId('nearby-detail-card');
    expect(within(card).getByText('218 Pecan Grove')).toBeTruthy();
    expect(within(card).getByText('WO-4840 · Routine read')).toBeTruthy();
    fireEvent.press(within(p.list).getByTestId('nearby-wo-4838-pick'));
    expect(app.current()).toBe('FF-11');
    p = panes('FF-11');
    expect(within(p.detail).getByText('95 Cedar Court')).toBeTruthy();
    expect(await door(app, 'FF-11', 'pane-FF-13')).toBe('FF-13');
    expect(await door(app, 'FF-11', 'pane-FF-12')).toBe('FF-12');
  }, 120_000);

  test('FF-12 Claim: Nearby beside the claim; a card’s Claim picks and the list stays', async () => {
    const nearby = fakeNearby();
    const app = await mountTablet({ nearby });
    await app.open('FF-12', { job: PECAN });
    await settle();
    let p = panes('FF-12');
    expect(within(p.list).getByTestId('screen-FF-11')).toBeTruthy();
    expect(within(p.detail).getByTestId('screen-FF-12')).toBeTruthy();
    expect(within(p.detail).getByText('218 Pecan Grove')).toBeTruthy();
    fireEvent.press(within(p.list).getByTestId('nearby-wo-4838-claim'));
    expect(app.current()).toBe('FF-12');
    p = panes('FF-12');
    expect(within(p.detail).getByText('95 Cedar Court')).toBeTruthy();
    // The detail's doors: Claim asks the server for the picked job and lands on Today.
    fireEvent.press(within(p.detail).getByTestId('claim-confirm'));
    await settle();
    expect(nearby.claim).toHaveBeenCalledWith('wo-4838');
    expect(app.current()).toBe('FF-10');
    await app.open('FF-12', { job: PECAN });
    await settle();
    fireEvent.press(within(panes('FF-12').detail).getByTestId('door-FF-11'));
    await settle();
    expect(app.current()).not.toBe('FF-12');
  }, 120_000);
});

const JOB = { workOrderId: 'wo-4822' };

describe('on site', () => {
  test('FF-28 Documents: the papers beside the job’s first; a row picks; Open it opens the tablet’s copy', async () => {
    const app = await mountTablet();
    await app.open('FF-28', JOB);
    await settle();
    let p = panes('FF-28');
    expect(within(p.list).getByTestId('screen-FF-28')).toBeTruthy();
    expect(within(p.detail).getByText('Water shut-off SOP')).toBeTruthy();
    fireEvent.press(within(p.list).getByTestId('doc-d-traffic-pick'));
    expect(app.current()).toBe('FF-28');
    p = panes('FF-28');
    expect(within(p.detail).getByText('Traffic control setup')).toBeTruthy();
    fireEvent.press(within(p.detail).getByTestId('document-open'));
    await settle();
    expect(documentQ.get(app.db, 'd-traffic')?.last_used_at).not.toBeNull();
    expect(within(panes('FF-28').detail).queryByTestId('document-note')).toBeNull();
    // A paper not on the tablet cannot be opened from here.
    fireEvent.press(within(panes('FF-28').list).getByTestId('doc-d-confined-pick'));
    expect(within(panes('FF-28').detail).getByTestId('document-open').props.accessibilityState).toMatchObject({ disabled: true });
  }, 120_000);

  test('FF-29 Crew: the crew beside who is on the job; a card picks its person', async () => {
    const app = await mountTablet();
    await app.open('FF-29', JOB);
    await settle();
    let p = panes('FF-29');
    expect(within(p.list).getByTestId('screen-FF-29')).toBeTruthy();
    expect(within(p.detail).getByTestId('crew-detail-total')).toHaveTextContent('2h 24m');
    expect(within(within(p.detail).getByTestId(`crew-detail-${DANA}`)).getByTestId('crew-detail-picked')).toBeTruthy();
    fireEvent.press(within(p.list).getByTestId(`crew-${MARCO}-pick`));
    expect(app.current()).toBe('FF-29');
    p = panes('FF-29');
    expect(within(within(p.detail).getByTestId(`crew-detail-${MARCO}`)).getByTestId('crew-detail-picked')).toBeTruthy();
    expect(within(within(p.detail).getByTestId(`crew-detail-${DANA}`)).queryByTestId('crew-detail-picked')).toBeNull();
  }, 120_000);

  test('FF-31 Activity: the job’s days beside what happened; a day picks; Notes opens FF-30', async () => {
    const app = await mountTablet();
    await app.open('FF-31', JOB);
    await settle();
    let p = panes('FF-31');
    expect(within(p.list).getByTestId('pick-2026-10-20')).toHaveTextContent(/Today/);
    expect(within(p.detail).getAllByTestId(/^event-/)).toHaveLength(5);
    fireEvent.press(within(p.list).getByTestId('pick-2026-10-17'));
    expect(app.current()).toBe('FF-31');
    p = panes('FF-31');
    expect(within(p.detail).getAllByTestId(/^event-/)).toHaveLength(1);
    expect(await door(app, 'FF-31', 'pane-FF-30', JOB)).toBe('FF-30');
  }, 120_000);
});

const METER = { assetId: 'a-4471' };

describe('the meter and the work', () => {
  test('FF-40 Asset history: the visits beside the newest; a card picks its visit', async () => {
    const app = await mountTablet();
    await app.open('FF-40', METER);
    await settle();
    let p = panes('FF-40');
    expect(within(p.list).getByTestId('screen-FF-40')).toBeTruthy();
    const titleOf = (i: number) => String(within(within(panes('FF-40').list).getByTestId(`visit-${i}`)).getAllByText(/./)[1]!.props.children);
    expect(within(p.detail).getByTestId('visit-detail-card')).toHaveTextContent(new RegExp(titleOf(0)));
    fireEvent.press(within(p.list).getByTestId('visit-2-pick'));
    expect(app.current()).toBe('FF-40');
    p = panes('FF-40');
    expect(within(p.detail).getByTestId('visit-detail-card')).toHaveTextContent(new RegExp(titleOf(2)));
    expect(within(p.detail).getByText('Who')).toBeTruthy();
  }, 120_000);

  test('FF-41 Asset search: the hits beside the meter; a hit picks; Scan one and Open it', async () => {
    const app = await mountTablet();
    await app.open('FF-41');
    await settle();
    let p = panes('FF-41');
    expect(within(p.list).getByTestId('screen-FF-41')).toBeTruthy();
    fireEvent.changeText(within(p.list).getByTestId('asset-search'), 'W-4471');
    fireEvent.press(within(panes('FF-41').list).getByTestId('asset-W-4471'));
    expect(app.current()).toBe('FF-41');
    p = panes('FF-41');
    const card = within(p.detail).getByTestId('search-detail-card');
    expect(within(card).getByText('W-4471')).toBeTruthy();
    expect(within(card).getByText('88-2041')).toBeTruthy();
    expect(within(p.list).getByTestId('asset-search')).toBeTruthy();
    fireEvent.press(within(p.detail).getByTestId('pane-FF-39'));
    await settle();
    expect(app.current()).toBe('FF-39');
    expect(app.ref.getCurrentRoute()?.params).toMatchObject({ assetId: 'a-4471' });
    await app.open('FF-41');
    await settle();
    expect(await door(app, 'FF-41', 'pane-FF-38')).toBe('FF-38');
  }, 120_000);

  test('FF-62 Pick a template: the templates beside the recent one; choosing picks; Use this template opens FF-37', async () => {
    const app = await mountTablet();
    await app.open('FF-62');
    await settle();
    let p = panes('FF-62');
    expect(within(p.list).getByTestId('screen-FF-62')).toBeTruthy();
    expect(within(p.detail).getByTestId('template-detail-card')).toHaveTextContent(/Leak investigation/);
    fireEvent.press(within(p.list).getByTestId('tpl-tpl-seal'));
    expect(app.current()).toBe('FF-62');
    p = panes('FF-62');
    expect(within(p.detail).getByTestId('template-detail-card')).toHaveTextContent(/Broken seal/);
    fireEvent.press(within(p.detail).getByTestId('pane-FF-37'));
    await settle();
    expect(app.current()).toBe('FF-37');
    expect(app.ref.getCurrentRoute()?.params).toMatchObject({ templateId: 'tpl-seal' });
  }, 120_000);
});

describe('me', () => {
  test('FF-43 Emergency: the alerts beside the emergency; opening it keeps the list; Acknowledge', async () => {
    const app = await mountTablet();
    await app.open('FF-43');
    await settle();
    const p = panes('FF-43');
    expect(within(p.list).getByTestId('screen-FF-42')).toBeTruthy();
    expect(within(p.detail).getByTestId('screen-FF-43')).toBeTruthy();
    fireEvent.press(within(p.list).getByTestId('door-FF-43'));
    expect(app.current()).toBe('FF-43');
    fireEvent.press(within(panes('FF-43').detail).getByTestId('door-FF-42'));
    await settle();
    expect(app.alerts.acks).toEqual(['em-1']);
    expect(app.current()).toBe('FF-42');
  }, 120_000);
});

describe('me — the technician’s own', () => {
  test('FF-44 Profile: the profile beside the person; Change availability opens FF-45', async () => {
    const facts = { role: 'Water II', utility: 'Brazos Water', employment: 'employee', mobile: '512 555 0104', certificationsCurrent: 3 };
    const app = await mountTablet({ me: { profile: { facts: async () => facts } } });
    await app.open('FF-44');
    await settle();
    const p = panes('FF-44');
    expect(within(p.list).getByTestId('ff44-name')).toBeTruthy();
    const card = within(p.detail).getByTestId('profile-detail-card');
    expect(card).toHaveTextContent(/Brazos Water/);
    expect(card).toHaveTextContent(/3 current/);
    expect(await door(app, 'FF-44', 'pane-FF-45')).toBe('FF-45');
  }, 120_000);

  test('FF-45 Availability: the three choices beside the state now; a choice moves it', async () => {
    const app = await mountTablet();
    await app.open('FF-45');
    await settle();
    fireEvent.press(within(panes('FF-45').list).getByTestId('ff45-available'));
    await settle();
    expect(within(panes('FF-45').detail).getByTestId('availability-detail-card')).toHaveTextContent(/^Available/);
    fireEvent.press(within(panes('FF-45').list).getByTestId('ff45-onBreak'));
    await settle();
    expect(app.current()).toBe('FF-45');
    expect(within(panes('FF-45').detail).getByTestId('availability-detail-card')).toHaveTextContent(/^On break/);
  }, 120_000);

  test('FF-46 Shifts: the week beside today; a day picks; Ask for time off asks', async () => {
    const requestTimeOff = jest.fn(async () => undefined);
    const app = await mountTablet({
      me: { shifts: { week: async () => boardWeek(), requestTimeOff, endShift: async () => undefined } },
    });
    await app.open('FF-46');
    await settle();
    let p = panes('FF-46');
    expect(within(p.detail).getByTestId('shift-detail-card')).toHaveTextContent(/Tue 20/);
    fireEvent.press(within(p.list).getByTestId('ff46-day-2026-10-22-pick'));
    expect(app.current()).toBe('FF-46');
    p = panes('FF-46');
    expect(within(p.detail).getByTestId('shift-detail-card')).toHaveTextContent(/Time off/);
    fireEvent.press(within(p.detail).getByTestId('shift-detail-time-off'));
    await settle();
    expect(requestTimeOff).toHaveBeenCalled();
  }, 120_000);

  test('FF-47 Timesheet: the week’s days beside the day’s clocks; a clock opens its correction; Admin time', async () => {
    const submitDay = jest.fn(async () => undefined);
    const app = await mountTablet({ me: { timesheet: { submitDay } } });
    await app.open('FF-47');
    await settle();
    let p = panes('FF-47');
    expect(within(p.list).getByTestId('pick-2026-10-20')).toBeTruthy();
    const card = within(p.detail).getByTestId('timesheet-detail-card');
    expect(within(card).getAllByTestId(/^ff47-entry-/).length).toBeGreaterThan(0);
    fireEvent.press(within(card).getAllByTestId(/^ff47-entry-/)[0]!);
    await settle();
    expect(screen.getByTestId('ff47-correction')).toBeTruthy();
    fireEvent.press(screen.getByTestId('ff47-correction-cancel'));
    await settle();
    p = panes('FF-47');
    fireEvent.press(within(p.detail).getByTestId('timesheet-detail-submit'));
    await settle();
    expect(submitDay).toHaveBeenCalled();
    expect(await door(app, 'FF-47', 'pane-FF-48')).toBe('FF-48');
  }, 120_000);

  test('FF-48 Admin: the tasks beside the picked one; a task picks, Start starts its clock', async () => {
    const app = await mountTablet();
    await app.open('FF-48');
    await settle();
    let p = panes('FF-48');
    fireEvent.press(within(p.list).getByTestId('ff48-task-depot-pick'));
    expect(app.current()).toBe('FF-48');
    p = panes('FF-48');
    expect(within(p.detail).getByTestId('admin-detail-card')).toHaveTextContent(/Depot time/);
    fireEvent.press(within(p.detail).getByTestId('admin-detail-start'));
    await settle();
    expect(within(panes('FF-48').detail).getByTestId('admin-detail-stop')).toBeTruthy();
    fireEvent.press(within(panes('FF-48').detail).getByTestId('admin-detail-stop'));
    await settle();
    expect(within(panes('FF-48').detail).getByTestId('admin-detail-start')).toBeTruthy();
  }, 120_000);

  test('FF-49 Van: the stock beside the short part; a part picks; Ask the depot asks', async () => {
    const askDepot = jest.fn(async () => undefined);
    const app = await mountTablet({ me: { van: { stock: async () => boardVan(), askDepot } } });
    await app.open('FF-49');
    await settle();
    let p = panes('FF-49');
    expect(within(p.detail).getByTestId('van-detail-card')).toHaveTextContent(/Water meter 5\/8"/);
    expect(within(p.detail).getByTestId('van-detail-card')).toHaveTextContent(/\$92\.4000/);
    fireEvent.press(within(p.detail).getByTestId('van-detail-ask'));
    await settle();
    expect(askDepot).toHaveBeenCalledWith(expect.any(String), 'MTR-W58');
    fireEvent.press(within(panes('FF-49').list).getByTestId('ff49-item-SEAL-W-pick'));
    expect(app.current()).toBe('FF-49');
    p = panes('FF-49');
    expect(within(p.detail).getByTestId('van-detail-card')).toHaveTextContent(/Wire seal/);
    expect(within(p.detail).queryByTestId('van-detail-ask')).toBeNull();
  }, 120_000);
});

describe('sync, settings, notifications', () => {
  test('FF-50 Sync: the directions beside the picked one; a refusal sent again; Download everything and Sync now', async () => {
    const syncNow = jest.fn(async () => undefined);
    const app = await mountTablet({ me: { sync: { syncNow } } });
    const { key } = capture(
      app.db,
      { technicianId: DANA, capturedBy: DANA },
      { kind: 'reading', workOrderId: 'wo-4822', payload: { value: '180' } },
      { newId: () => 'refused-1', clock: { now: () => new Date(2026, 9, 20, 9, 30) } },
    );
    outboxQ.refuse(deviceWide(app.db, 'receipt'), key, { message: 'Reading 180 is impossible for this meter' });
    await app.open('FF-50');
    await settle();
    let p = panes('FF-50');
    expect(within(p.detail).getByTestId('ff50-status')).toBeTruthy();
    expect(within(p.detail).getByTestId('ff50-completed')).toBeTruthy();
    fireEvent.press(within(p.list).getByTestId('pick-photos'));
    p = panes('FF-50');
    expect(within(p.detail).getByTestId('ff50-photos')).toBeTruthy();
    expect(within(p.detail).queryByTestId('ff50-completed')).toBeNull();
    fireEvent.press(within(p.list).getByTestId('pick-refused'));
    p = panes('FF-50');
    expect(within(p.detail).getByTestId(`ff50-reason-${key}`)).toHaveTextContent('Reading 180 is impossible for this meter');
    fireEvent.press(within(p.detail).getByTestId(`ff50-resend-${key}`));
    await settle();
    // Sent again: it no longer needs the technician, and the list stops offering it.
    expect(within(panes('FF-50').list).queryByTestId('pick-refused')).toBeNull();
    fireEvent.press(within(panes('FF-50').detail).getByTestId('sync-detail-now'));
    await settle();
    expect(syncNow).toHaveBeenCalled();
    expect(await door(app, 'FF-50', 'pane-FF-08')).toBe('FF-08');
  }, 120_000);

  test('FF-51 Settings: the sections beside the picked one; each door on a section is followed', async () => {
    const app = await mountTablet();
    await app.open('FF-51');
    await settle();
    let p = panes('FF-51');
    expect(within(p.detail).getByTestId('ff51-theme')).toBeTruthy();
    fireEvent.press(within(p.list).getByTestId('pick-nearby'));
    expect(app.current()).toBe('FF-51');
    expect(within(panes('FF-51').detail).getByTestId('ff51-nearby')).toBeTruthy();
    fireEvent.press(within(panes('FF-51').list).getByTestId('pick-about'));
    expect(within(panes('FF-51').detail).getByTestId('ff51-version')).toBeTruthy();
    for (const [section, to] of [
      ['reading', 'RW-29'],
      ['notifications', 'FF-52'],
      ['sync', 'FF-50'],
      ['permissions', 'FF-07'],
      ['signOut', 'FF-53'],
    ] as const) {
      fireEvent.press(within(panes('FF-51').list).getByTestId(`pick-${section}`));
      expect(await door(app, 'FF-51', `pane-${to}`)).toBe(to);
      // Back on the board the frame is fresh; pick again for the next section.
    }
    fireEvent.press(within(panes('FF-51').list).getByTestId('pick-screen'));
    expect(await door(app, 'FF-51', 'door-FF-54')).toBe('FF-54');
  }, 120_000);

  test('FF-52 Notifications: the kinds beside the picked one; a switch beside the list moves the list', async () => {
    const app = await mountTablet();
    await app.open('FF-52');
    await settle();
    let p = panes('FF-52');
    expect(within(p.detail).getByTestId('ff52-emergency')).toBeTruthy();
    expect(within(p.list).getByTestId('pick-emergency')).toHaveTextContent(/Always/);
    fireEvent.press(within(p.list).getByTestId('pick-schedule'));
    p = panes('FF-52');
    const before = String(within(p.list).getByTestId('pick-schedule').props.accessibilityLabel);
    fireEvent.press(within(p.detail).getByTestId('ff52-schedule'));
    await settle();
    expect(String(within(panes('FF-52').list).getByTestId('pick-schedule').props.accessibilityLabel)).not.toBe(before);
  }, 120_000);
});

const ROUTE = { routeId: 'wlk-07' };

function readMeter(app: App, id: string, value: string | null, status: 'read' | 'could_not_read', reason?: string) {
  routeReadQ.recordCapture(scoped(app.db, DANA), id, {
    captureKey: `cap-${id}`,
    value,
    unit: 'gal',
    readerStatus: status,
    noReadReason: reason ?? null,
    warnedAccepted: false,
    capturedAt: '2026-10-20T09:00:00.000Z',
    capturedBy: DANA,
    identifiedBy: 'listed',
    readMethod: 'walk',
  });
}

/** The detail card's title — its first line of text. */
const titleIn = (card: Instance) => String(within(card).getAllByText(/./)[0]!.props.children);

describe('the reading route', () => {
  test('RW-05 The walk: the stops beside the stop; a stop picks; On the map and Open the stop', async () => {
    const app = await mountTablet();
    await app.open('RW-05', ROUTE);
    await settle();
    let p = panes('RW-05');
    expect(within(p.list).getByTestId('screen-RW-05')).toBeTruthy();
    const first = String(within(p.list).getByTestId('stop-0').props.accessibilityLabel);
    expect(titleIn(within(p.detail).getByTestId('walk-stop-card'))).toBe(first);
    const third = String(within(p.list).getByTestId('stop-2').props.accessibilityLabel);
    fireEvent.press(within(p.list).getByTestId('stop-2'));
    expect(app.current()).toBe('RW-05');
    p = panes('RW-05');
    expect(titleIn(within(p.detail).getByTestId('walk-stop-card'))).toBe(third);
    expect(await door(app, 'RW-05', 'pane-RW-04', ROUTE)).toBe('RW-04');
    fireEvent.press(within(panes('RW-05').list).getByTestId('stop-2'));
    fireEvent.press(within(panes('RW-05').detail).getByTestId('pane-RW-06'));
    await settle();
    expect(app.current()).toBe('RW-06');
    expect(app.ref.getCurrentRoute()?.params).toMatchObject({ stopId: expect.stringMatching(/^s/) });
  }, 120_000);

  test('RW-06 The stop: the meters beside the first unread; a card picks; every door on the meter', async () => {
    const app = await mountTablet();
    const STOP = { stopId: 's1318' };
    await app.open('RW-06', STOP);
    await settle();
    let p = panes('RW-06');
    expect(within(p.list).getByTestId('screen-RW-06')).toBeTruthy();
    // The first unread at the address is picked, and its card ruled heavy.
    expect(within(p.detail).getByTestId('stop-meter-card')).toBeTruthy();
    fireEvent.press(within(p.list).getByTestId('meter-r0471'));
    p = panes('RW-06');
    expect(within(p.detail).getByTestId('stop-meter-card')).toHaveTextContent(/Carla Ruiz/);
    expect(within(p.detail).getByTestId('stop-meter-card')).toHaveTextContent(/40,000–56,000 gal/);
    fireEvent.press(within(p.list).getByTestId('meter-r0472'));
    expect(app.current()).toBe('RW-06');
    p = panes('RW-06');
    expect(within(p.detail).getByTestId('stop-meter-card')).toHaveTextContent(/Desmond Oyelaran/);
    expect(await door(app, 'RW-06', 'pane-RW-17', STOP)).toBe('RW-17');
    fireEvent.press(within(panes('RW-06').list).getByTestId('meter-r0472'));
    expect(await door(app, 'RW-06', 'pane-RW-09', STOP)).toBe('RW-09');
    fireEvent.press(within(panes('RW-06').list).getByTestId('meter-r0472'));
    expect(await door(app, 'RW-06', 'pane-RW-07', STOP)).toBe('RW-07');
    fireEvent.press(within(panes('RW-06').list).getByTestId('meter-r0470'));
    expect(await door(app, 'RW-06', 'pane-RW-12', STOP)).toBe('RW-12');
  }, 120_000);

  test('RW-08 Find a meter: the hits beside the meter; a hit picks; Read opens the reading', async () => {
    const app = await mountTablet();
    readMeter(app, 'r0471', '52410', 'read');
    await app.open('RW-08');
    await settle();
    // An unread meter: found, picked, and read from beside the search.
    fireEvent.changeText(within(panes('RW-08').list).getByTestId('find-input'), 'MTR-0472');
    await settle();
    fireEvent.press(within(panes('RW-08').list).getByTestId('door-RW-09'));
    expect(app.current()).toBe('RW-08');
    let p = panes('RW-08');
    expect(within(p.list).getByTestId('find-input')).toBeTruthy();
    expect(within(p.detail).getByTestId('found-meter-card')).toHaveTextContent(/Desmond Oyelaran/);
    fireEvent.press(within(p.detail).getByTestId('pane-RW-09'));
    await settle();
    expect(app.current()).toBe('RW-09');
    expect(app.ref.getCurrentRoute()?.params).toMatchObject({ readId: 'r0472' });
    // A meter read today shows its figure and offers no second reading.
    await app.open('RW-08');
    await settle();
    fireEvent.changeText(within(panes('RW-08').list).getByTestId('find-input'), 'MTR-0471');
    await settle();
    fireEvent.press(within(panes('RW-08').list).getByTestId('door-RW-09'));
    p = panes('RW-08');
    expect(within(p.detail).getByTestId('found-meter-card')).toHaveTextContent(/52,410 gal/);
    expect(within(p.detail).queryByTestId('pane-RW-09')).toBeNull();
  }, 120_000);

  test('RW-12 Master and subs: the subs beside So far; Read the next', async () => {
    const app = await mountTablet();
    readMeter(app, 'r0470', '92480', 'read');
    readMeter(app, 'r0470a', '31100', 'read');
    readMeter(app, 'r0470b', '29640', 'read');
    await app.open('RW-12', { readId: 'r0470' });
    await settle();
    const p = panes('RW-12');
    expect(within(p.list).getByTestId('screen-RW-12')).toBeTruthy();
    expect(within(p.list).queryByTestId('balance')).toBeNull();
    expect(within(p.detail).getByTestId('still-to-find')).toHaveTextContent(/31,740 gal/);
    fireEvent.press(within(p.detail).getByTestId('pane-RW-09'));
    await settle();
    expect(app.current()).toBe('RW-09');
    expect(app.ref.getCurrentRoute()?.params).toMatchObject({ readId: 'r0470c' });
  }, 120_000);

  test('RW-23 Still to do: what is left beside the stop; a stop picks; On a map and Open it', async () => {
    const app = await mountTablet();
    await app.open('RW-23', ROUTE);
    await settle();
    let p = panes('RW-23');
    const second = String(within(p.list).getByTestId('todo-1').props.accessibilityLabel);
    fireEvent.press(within(p.list).getByTestId('todo-1'));
    expect(app.current()).toBe('RW-23');
    p = panes('RW-23');
    expect(titleIn(within(p.detail).getByTestId('still-stop-card'))).toBe(second);
    expect(await door(app, 'RW-23', 'pane-RW-04', ROUTE)).toBe('RW-04');
    expect(await door(app, 'RW-23', 'pane-RW-06', ROUTE)).toBe('RW-06');
  }, 120_000);

  test('RW-28 My reads: the routes beside their totals; a route picks; Open it', async () => {
    const app = await mountTablet();
    readMeter(app, 'r0471', '52410', 'read');
    readMeter(app, 'r1206', null, 'could_not_read', 'Dog');
    await app.open('RW-28');
    await settle();
    const p = panes('RW-28');
    expect(within(p.detail).getByTestId('mine-totals-read')).toHaveTextContent(/^1/);
    expect(within(p.detail).getByTestId('mine-totals-could-not')).toHaveTextContent(/^1/);
    expect(within(p.detail).getByTestId('mine-totals-routes')).toHaveTextContent(/^1/);
    fireEvent.press(within(p.list).getByTestId('door-RW-27'));
    expect(app.current()).toBe('RW-28');
    expect(await door(app, 'RW-28', 'pane-RW-27')).toBe('RW-27');
  }, 120_000);

  test('RW-29 Reading settings: the settings beside the keypad; a switch beside the list moves the list', async () => {
    const app = await mountTablet();
    await app.open('RW-29');
    await settle();
    let p = panes('RW-29');
    expect(within(p.detail).getByTestId('set-keypad')).toBeTruthy();
    expect(within(p.detail).getByTestId('set-order')).toBeTruthy();
    fireEvent.press(within(p.list).getByTestId('pick-scanFirst'));
    p = panes('RW-29');
    expect(within(p.list).getByTestId('pick-scanFirst')).toHaveTextContent(/Off/);
    fireEvent.press(within(p.detail).getByTestId('set-scan'));
    await settle();
    expect(within(panes('RW-29').list).getByTestId('pick-scanFirst')).toHaveTextContent(/On/);
    expect(await door(app, 'RW-29', 'pane-FF-51')).toBe('FF-51');
  }, 120_000);
});

describe('held upright (768 × 1024): the phone screen alone', () => {
  const BOARDS: Array<[ScreenId, Record<string, unknown> | undefined]> = [
    ['FF-11', undefined],
    ['FF-12', { job: PECAN }],
    ['FF-28', JOB],
    ['FF-29', JOB],
    ['FF-31', JOB],
    ['FF-40', METER],
    ['FF-41', undefined],
    ['FF-62', undefined],
    ['FF-43', undefined],
    ['FF-44', undefined],
    ['FF-45', undefined],
    ['FF-46', undefined],
    ['FF-47', undefined],
    ['FF-48', undefined],
    ['FF-49', undefined],
    ['FF-50', undefined],
    ['FF-51', undefined],
    ['FF-52', undefined],
    ['RW-05', ROUTE],
    ['RW-06', { stopId: 's1318' }],
    ['RW-08', undefined],
    ['RW-12', { readId: 'r0470' }],
    ['RW-23', ROUTE],
    ['RW-28', undefined],
    ['RW-29', undefined],
  ];
  test.each(BOARDS)('%s', async (id, params) => {
    setWindow(768, 1024);
    const app = await mountTablet({ nearby: fakeNearby() });
    await app.open(id, params);
    await settle();
    const frame = frameOf(id);
    expect(frame.props.testID).toBe('tablet-frame-T2');
    expect(within(frame).queryByTestId('tablet-pane-list')).toBeNull();
    expect(within(frame).getByTestId('tablet-pane-detail')).toBeTruthy();
    expect(within(frame).getByTestId(`screen-${id}`)).toBeTruthy();
  }, 60_000);
});
