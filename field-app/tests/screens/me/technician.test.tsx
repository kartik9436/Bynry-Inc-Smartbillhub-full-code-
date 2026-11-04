/**
 * T-24 — FF-44 Profile, FF-45 Availability, FF-46 Shifts, FF-47 Timesheet,
 * FF-48 Admin tasks, FF-49 Van (EP-FLD-08 §3), on the real navigation tree
 * over a real handset store.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import * as crewTime from '../../../src/db/queries/crewTime';
import * as outboxQ from '../../../src/db/queries/outbox';
import { scoped } from '../../../src/db/scoped';
import { applyOfficeStatus } from '../../../src/screens/me/availability';
import { createAvailabilityPort } from '../../../src/screens/me/availabilityPort';
import { unitPriceText } from '../../../src/screens/me/VanScreen';
import {
  at,
  boardVan,
  boardWeek,
  DANA,
  makeFixture,
  openScreen,
  seedDay,
  seedOrders,
  seedPhotos,
} from './support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

function onTop(id: string) {
  const all = screen.getAllByTestId(`screen-${id}`);
  return within(all.at(-1) as Parameters<typeof within>[0]);
}

describe('FF-44 Profile', () => {
  test('TC-1: D. Ortiz · Water II · Available since 07:40 · 4 done, 7 left, 5h 02m worked · the details', async () => {
    const f = makeFixture({
      profile: {
        facts: async () => ({ role: null, utility: 'Silver Creek Water', employment: null, mobile: '(512) 555-0142', certificationsCurrent: 3 }),
      },
    });
    seedOrders(f.db);
    seedDay(f.db, f.ids);
    f.services.prefs.set(`handset.availability.${DANA}`, JSON.stringify({ value: 'available', since: at('07:40') }));
    const app = await openScreen('FF-44', f);
    const s = onTop('FF-44');
    expect(s.getByTestId('ff44-name')).toHaveTextContent('D. Ortiz');
    expect(s.getByText('Water II')).toBeTruthy();
    expect(s.getByTestId('door-FF-45')).toHaveProp('accessibilityLabel', 'Available, On duty since 07:40');
    expect(s.getByTestId('ff44-done')).toHaveTextContent('4done');
    expect(s.getByTestId('ff44-left')).toHaveTextContent('7left');
    expect(s.getByTestId('ff44-worked')).toHaveTextContent('5h 02mworked');
    for (const v of ['Silver Creek Water', 'Employee', '(512) 555-0142', '3 current']) expect(s.getByText(v)).toBeTruthy();
    // The rows the drawing draws, each a door to its screen.
    for (const [door, to] of [
      ['door-FF-46', 'FF-46'],
      ['door-FF-47', 'FF-47'],
      ['door-FF-51', 'FF-51'],
    ] as const) {
      await act(async () => {
        fireEvent.press(onTop('FF-44').getByTestId(door));
      });
      expect(app.ref.getCurrentRoute()?.name).toBe(to);
      await act(async () => {
        app.ref.goBack();
      });
    }
    app.unmount();
  });

  test('a fact the handset does not hold is left out, never guessed (ME-profile not built)', async () => {
    const f = makeFixture();
    const app = await openScreen('FF-44', f);
    expect(onTop('FF-44').queryByTestId('ff44-details')).toHaveTextContent(/Employee/);
    expect(onTop('FF-44').queryByText('Mobile')).toBeNull();
    app.unmount();
  });
});

describe('FF-45 Availability', () => {
  test('TC-2 / TC-3: what each choice means, and the photos still going up', async () => {
    const f = makeFixture();
    seedPhotos(f.db);
    const app = await openScreen('FF-45', f);
    const s = onTop('FF-45');
    expect(s.getByText('Emergencies still reach you')).toBeTruthy();
    expect(s.getByText('Shift ends. Unsent work still sends.')).toBeTruthy();
    expect(s.getByTestId('ff45-photos')).toHaveTextContent('38 photos still uploading.');
    app.unmount();
  });

  test('FB-033: choosing updates the chip at once and puts ONE availability item in the outbox with the tap time', async () => {
    const f = makeFixture();
    f.services.availability = createAvailabilityPort({ db: f.db, newId: f.ids, now: f.services.now });
    const app = await openScreen('FF-45', f);
    await act(async () => {
      fireEvent.press(onTop('FF-45').getByTestId('ff45-onBreak'));
    });
    expect(onTop('FF-45').getByTestId('ff45-onBreak')).toHaveProp('accessibilityState', { checked: true });
    expect(screen.getAllByTestId('shell-status-availability').at(-1)).toHaveTextContent('On break');
    // "Dispatch not told yet." is retired: the office hears it through the outbox.
    expect(onTop('FF-45').queryByTestId('ff45-not-sent')).toBeNull();
    const rows = outboxQ.listMine(scoped(f.db, DANA), { limit: 10 }).filter((r) => r.kind === 'availability');
    expect(rows.map((r) => [r.state, JSON.parse(r.payload)])).toEqual([
      ['pending', { at: f.services.now().toISOString(), value: 'on_break' }],
    ]);
    app.unmount();
  });

  test('TC-5 (negative): off duty holds back nothing unsent — it only adds its own item', async () => {
    const f = makeFixture();
    f.services.availability = createAvailabilityPort({ db: f.db, newId: f.ids, now: f.services.now });
    seedDay(f.db, f.ids);
    const before = outboxQ.countUnsentMine(scoped(f.db, DANA));
    const app = await openScreen('FF-45', f);
    await act(async () => {
      fireEvent.press(onTop('FF-45').getByTestId('ff45-offDuty'));
    });
    expect(outboxQ.countUnsentMine(scoped(f.db, DANA))).toBe(before + 1);
    expect(outboxQ.countOnTheirWayMine(scoped(f.db, DANA), 'availability')).toBe(1);
    expect(before).toBeGreaterThan(0);
    app.unmount();
  });

  test('FB-033: the office set Dana Unavailable — read back, the chip says so', async () => {
    const f = makeFixture();
    applyOfficeStatus(f.services.prefs, DANA, 'unavailable', at('11:00'));
    const app = await openScreen('FF-45', f);
    expect(screen.getAllByTestId('shell-status-availability').at(-1)).toHaveTextContent('Unavailable');
    app.unmount();
  });
});

describe('FF-46 Shifts', () => {
  test('TC-4: Thu 23 time off approved 02 Oct · Fri 24 Founders Day, depot closed; Request time off', async () => {
    const f = makeFixture({ shifts: { week: async () => boardWeek(), requestTimeOff: async () => undefined, endShift: async () => undefined } });
    const app = await openScreen('FF-46', f);
    const s = onTop('FF-46');
    expect(s.getByTestId('ff46-day-2026-10-22')).toHaveProp('accessibilityLabel', 'Thu 22, Time off, Approved 02 Oct');
    expect(s.getByTestId('ff46-day-2026-10-23')).toHaveProp('accessibilityLabel', 'Fri 23, Founders Day, depot closed');
    expect(s.getByTestId('ff46-day-2026-10-19')).toHaveProp('accessibilityLabel', 'Mon 19, 08:00 – 16:30, Day shift · Route 3');
    expect(s.getByTestId('ff46-current')).toHaveTextContent(/5h 02m/);
    expect(s.getByRole('button', { name: 'Request time off' })).toBeTruthy();
    app.unmount();
  });

  test('not wired: the week is not on this phone, and requesting time off says it was not sent', async () => {
    const f = makeFixture();
    const app = await openScreen('FF-46', f);
    expect(onTop('FF-46').getByTestId('ff46-not-wired')).toBeTruthy();
    await act(async () => {
      fireEvent.press(onTop('FF-46').getByTestId('ff46-request-time-off'));
    });
    expect(onTop('FF-46').getByText('Not sent. Try again later.')).toBeTruthy();
    app.unmount();
  });
});

describe('FF-47 Timesheet', () => {
  test('TC-1: 5h 02m recorded — jobs 3h 38m · travel 54m · admin 30m — and WO-4824 running since 12:28', async () => {
    const f = makeFixture();
    seedOrders(f.db);
    seedDay(f.db, f.ids);
    const app = await openScreen('FF-47', f);
    const s = onTop('FF-47');
    expect(s.getByTestId('ff47-total')).toHaveTextContent('5h 02m');
    expect(s.getByTestId('ff47-legend-success')).toHaveTextContent('Jobs 3h 38m');
    expect(s.getByTestId('ff47-legend-info')).toHaveTextContent('Travel 54m');
    expect(s.getByTestId('ff47-legend-neutral')).toHaveTextContent('Admin 30m');
    expect(s.getByText('Vehicle check')).toBeTruthy();
    expect(s.getByText('07:40 – 08:00 · Admin')).toBeTruthy();
    expect(s.getByText('WO-4822 · Meter exchange')).toBeTruthy();
    expect(s.getByTestId('ff47-entry-l4')).toHaveProp('accessibilityLabel', 'Running now, WO-4824 · Meter exchange · since 12:28, 42m');
    app.unmount();
  });

  test('R9: an entry is correctable — the correction is captured through the outbox and the row moves', async () => {
    const f = makeFixture();
    seedOrders(f.db);
    seedDay(f.db, f.ids);
    const s0 = scoped(f.db, DANA);
    const before = outboxQ.listMine(s0, { limit: 100 }).length;
    const app = await openScreen('FF-47', f);
    fireEvent.press(onTop('FF-47').getByTestId('ff47-entry-l2'));
    fireEvent.press(screen.getByTestId('ff47-start--5'));
    expect(screen.getByTestId('ff47-correction-start')).toHaveTextContent('Start 08:41');
    await act(async () => {
      fireEvent.press(screen.getByTestId('ff47-correction-save'));
    });
    const row = crewTime.listBetween(s0, at('00:00'), '2026-10-22T00:00:00.000Z').find((r) => r.id === 'l2');
    expect(row?.started_at).toBe(at('08:41'));
    const acts = outboxQ.listMine(s0, { limit: 100 });
    expect(acts.length).toBe(before + 1);
    expect(JSON.parse(acts[0]?.payload ?? '{}')).toMatchObject({ action: 'correct', crew_time_id: 'l2', started_at: at('08:41') });
    expect(acts[0]?.state).toBe('pending');
    app.unmount();
  });

  test('TC-4 (negative): submitting with a clock running leaves it running', async () => {
    const f = makeFixture({ timesheet: { submitDay: async () => undefined } });
    seedOrders(f.db);
    seedDay(f.db, f.ids);
    const app = await openScreen('FF-47', f);
    await act(async () => {
      fireEvent.press(onTop('FF-47').getByTestId('ff47-submit'));
    });
    expect(onTop('FF-47').getByText('Sent to the office.')).toBeTruthy();
    expect(crewTime.runningMine(scoped(f.db, DANA))?.id).toBe('l4');
    app.unmount();
  });
});

describe('FF-48 Admin tasks', () => {
  test('TC-2: a vehicle check of 20m at 07:40 is shown as admin, and starting a task starts one clock', async () => {
    const f = makeFixture();
    seedOrders(f.db);
    seedDay(f.db, f.ids);
    // Stop the job clock first so the card says nothing is running.
    f.services.data.stopClock({ technicianId: DANA, capturedBy: DANA }, new Date(at('13:00')));
    const app = await openScreen('FF-48', f);
    const s = onTop('FF-48');
    expect(s.getByTestId('ff48-recorded')).toHaveTextContent('30m recorded today');
    expect(s.getByTestId('ff48-start-vehicleCheck')).toHaveProp('accessibilityLabel', 'Vehicle check, Done 07:40 · 20m');
    await act(async () => {
      fireEvent.press(s.getByTestId('ff48-start-training'));
    });
    const running = crewTime.runningMine(scoped(f.db, DANA));
    expect(running?.kind).toBe('admin');
    expect(onTop('FF-48').getByTestId('ff48-state')).toHaveTextContent(/Training/);
    await act(async () => {
      fireEvent.press(onTop('FF-48').getByTestId('ff48-stop'));
    });
    expect(crewTime.runningMine(scoped(f.db, DANA))).toBeUndefined();
    app.unmount();
  });
});

describe('FF-49 Van', () => {
  test('reads stock and never counts it: no count control, the short part first with its unit price', async () => {
    const f = makeFixture({ van: { stock: async () => boardVan(), askDepot: async () => undefined } });
    const app = await openScreen('FF-49', f);
    const s = onTop('FF-49');
    expect(s.getByTestId('ff49-needed')).toHaveTextContent(/Water meter 5\/8"/);
    expect(s.getByText('MTR-W58 · $92.4000 each')).toBeTruthy();
    expect(s.getByTestId('ff49-count-SEAL-W')).toHaveTextContent('26');
    expect(s.queryByText(/Count the van/i)).toBeNull();
    fireEvent.press(s.getByTestId('door-FF-38'));
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-38');
    app.unmount();
  });

  test('a unit price shows the places it carries, two to four, by string (hard rule 2)', () => {
    expect(unitPriceText('92.4000', 'USD')).toBe('$92.4000');
    expect(unitPriceText('8.9375', 'USD')).toBe('$8.9375');
    expect(unitPriceText('0.1', 'USD')).toBe('$0.10');
    expect(unitPriceText('12', 'EUR')).toBe('EUR 12.00');
  });
});
