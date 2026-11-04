/**
 * CR-193-BRC10 (MQ-040 step 1) — FF-46 and FF-47 WIRED, on the real
 * navigation tree over a real handset store: the week the sync kept (shift
 * windows, the utility's holiday in grey), today's shift with *End shift*, and
 * *Submit the day*, after which the day reads Submitted and is read-only.
 * *Request time off* (step 2, not approved) still says it was not sent.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import * as outboxQ from '../../../src/db/queries/outbox';
import { scoped } from '../../../src/db/scoped';
import { createShiftsPort, createTimesheetPort } from '../../../src/screens/me/shiftsPorts';
import { downloadWeek, localDay, type WireWeek } from '../../../src/sync/shifts';
import { DANA, makeFixture, NOW, openScreen, seedDay, seedOrders } from './support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

function onTop(id: string) {
  const all = screen.getAllByTestId(`screen-${id}`);
  return within(all.at(-1) as Parameters<typeof within>[0]);
}

/** The PO's worked example, in the week holding NOW: Mon–Thu 07:00–15:30, Fri a holiday. */
function weekOfNow(): WireWeek {
  const today = new Date(NOW);
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
  const day = (n: number) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + n);
    return localDay(d);
  };
  const codes = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
  return {
    from: day(0),
    to: day(6),
    today: localDay(today),
    days: codes.map((weekday, n) =>
      n < 4
        ? { date: day(n), weekday, kind: 'shift' as const, start: '07:00', end: '15:30', holiday: null, note: n === 1 ? 'Dentist after' : null, exception: null }
        : n === 4
          ? { date: day(n), weekday, kind: 'holiday' as const, start: null, end: null, holiday: 'Founders Day', note: null, exception: null }
          : { date: day(n), weekday, kind: 'off' as const, start: null, end: null, holiday: null, note: null, exception: null },
    ),
    current: { start: '07:00', end: '15:30', started_at: new Date(NOW.getTime() - 130 * 60_000).toISOString(), minutes_so_far: 130 },
    ended_at: null,
  };
}

async function wired(withWeek = true) {
  const f = makeFixture();
  const deps = { db: f.db, prefs: f.services.prefs, newId: f.ids, now: () => NOW };
  f.services.shifts = createShiftsPort(deps, f.services.shifts);
  f.services.timesheet = createTimesheetPort(deps);
  if (withWeek) {
    const api = { myWeek: async () => weekOfNow(), endShift: async () => ({}), submitTimesheet: async () => ({}) };
    await downloadWeek(api, f.services.prefs, DANA, new Date(NOW.getTime() - 60 * 60_000));
  }
  return f;
}

describe('FF-46 Shifts — wired', () => {
  test('the kept week: shift windows, the holiday in grey, weekend off; today on shift for 2h 10m', async () => {
    const f = await wired();
    const app = await openScreen('FF-46', f);
    const s = onTop('FF-46');
    const w = weekOfNow();
    expect(s.queryByTestId('ff46-not-wired')).toBeNull();
    expect(s.getByTestId(`ff46-day-${w.days[0]!.date}`).props.accessibilityLabel).toMatch(/07:00 – 15:30$/);
    expect(s.getByTestId(`ff46-day-${w.days[1]!.date}`).props.accessibilityLabel).toMatch(/07:00 – 15:30, Dentist after$/);
    expect(s.getByTestId(`ff46-day-${w.days[4]!.date}`).props.accessibilityLabel).toMatch(/Founders Day$/);
    expect(s.getByTestId(`ff46-day-${w.days[5]!.date}`).props.accessibilityLabel).toMatch(/Off$/);
    expect(s.getByTestId('ff46-current')).toHaveTextContent(/2h 10m/);
    app.unmount();
  });

  test('End shift is captured once through the outbox, and the shift card goes', async () => {
    const f = await wired();
    const app = await openScreen('FF-46', f);
    await act(async () => {
      fireEvent.press(onTop('FF-46').getByTestId('ff46-end-shift'));
    });
    await act(async () => {
      await Promise.resolve();
    });
    const items = outboxQ.listMine(scoped(f.db, DANA), { limit: 10 }).filter((r) => r.kind === 'shift_end');
    expect(items).toHaveLength(1);
    expect(JSON.parse(items[0]!.payload)).toEqual({ at: NOW.toISOString() });
    expect(onTop('FF-46').queryByTestId('ff46-current')).toBeNull();
    expect(onTop('FF-46').getByText(/^Shift ended /)).toBeTruthy();
    app.unmount();
  });

  test('with no week kept yet it says so — and Request time off (step 2) still says not sent', async () => {
    const f = await wired(false);
    const app = await openScreen('FF-46', f);
    expect(onTop('FF-46').getByTestId('ff46-not-wired')).toBeTruthy();
    await act(async () => {
      fireEvent.press(onTop('FF-46').getByTestId('ff46-request-time-off'));
    });
    expect(onTop('FF-46').getByText('Not sent. Try again later.')).toBeTruthy();
    app.unmount();
  });
});

describe('FF-47 Timesheet — wired', () => {
  test('Submit the day is captured once; the day then reads Submitted and its entries do not open', async () => {
    const f = await wired();
    seedOrders(f.db);
    seedDay(f.db, f.ids);
    const app = await openScreen('FF-47', f);
    await act(async () => {
      fireEvent.press(onTop('FF-47').getByTestId('ff47-submit'));
    });
    const items = outboxQ.listMine(scoped(f.db, DANA), { limit: 50 }).filter((r) => r.kind === 'timesheet_submit');
    expect(items).toHaveLength(1);
    expect(JSON.parse(items[0]!.payload)).toEqual({ date: localDay(NOW) });
    const s = onTop('FF-47');
    expect(s.getByText('Submitted. Sends with next sync.')).toBeTruthy();
    expect(s.getByTestId('ff47-submit')).toHaveTextContent('Submitted');
    expect(s.getByTestId('ff47-submit')).toBeDisabled();
    fireEvent.press(s.getByTestId('ff47-entry-l2'));
    expect(screen.queryByTestId('ff47-correction-start')).toBeNull();
    app.unmount();
  });
});
