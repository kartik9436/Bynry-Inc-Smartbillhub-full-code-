/**
 * FF-10 Today (T-16) — US-FLD-002, -015, -037, -045 §3, mounted under the
 * real navigation with Dana's day in a real store.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';
import { Linking } from 'react-native';

import * as workOrderQ from '../../../src/db/queries/workOrder';
import { scoped } from '../../../src/db/scoped';
import { assertTouchTargets, current, currentParams, drawerOpen, mountDay, open } from './support';
import { DANA } from './dayFixture';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

function cardOrder(): string[] {
  return screen.getAllByTestId(/^job-wo-\d+$/).map((el) => String(el.props.testID).replace('job-', ''));
}

describe('FF-10 Today', () => {
  test('the day in appointment-window order — WO-4824, a P1, sits SECOND (R1, US-FLD-015 TC-2)', async () => {
    const app = await mountDay();
    await open(app, 'FF-10');
    expect(await screen.findByTestId('screen-FF-10')).toBeTruthy();
    expect(cardOrder()).toEqual(['wo-4822', 'wo-4824', 'wo-4831', 'wo-4833']);
    // Its P1 is a badge on the card, never a sort key.
    expect(within(screen.getByTestId('job-wo-4824')).getByText('P1')).toBeTruthy();
    // Done, tomorrow's and Marco's are not on Today.
    expect(screen.queryByTestId('job-wo-4810')).toBeNull();
    expect(screen.queryByTestId('job-wo-4901')).toBeNull();
    expect(screen.queryByTestId('job-wo-9999')).toBeNull();
    expect(screen.getByTestId('today-summary')).toHaveTextContent('4 jobs · 2h 35m');
    app.unmount();
  });

  test('the card says who, where, what and when — state strip, customer, address, number · type, window', async () => {
    const app = await mountDay();
    await open(app, 'FF-10');
    const card = within(await screen.findByTestId('job-wo-4822'));
    expect(card.getByText('On site')).toBeTruthy();
    expect(card.getByText('Sarah Miller')).toBeTruthy();
    expect(card.getByText('1400 Elm Street · Unit A')).toBeTruthy();
    expect(card.getByText('WO-4822 · Meter exchange')).toBeTruthy();
    expect(card.getByText('08:00–12:00')).toBeTruthy();
    app.unmount();
  });

  test('a dispatcher moves WO-4831 to 08:30 — on the next read it takes its new place (US-FLD-015 TC-1)', async () => {
    const app = await mountDay();
    const db = app.db;
    if (!db) throw new Error('no store');
    const s = scoped(db, DANA);
    s.run(`UPDATE work_order SET window_start = :at WHERE technician_id = :technician_id AND id = 'wo-4831'`, {
      at: new Date(2026, 9, 21, 8, 30).toISOString(),
    });
    await open(app, 'FF-10');
    expect((await screen.findAllByTestId(/^job-wo-\d+$/)).map((e) => e.props.testID)).toEqual([
      'job-wo-4822',
      'job-wo-4831',
      'job-wo-4824',
      'job-wo-4833',
    ]);
    app.unmount();
  });

  test('a job reassigned away leaves Today (US-FLD-045 TC-1: a delta removal deletes the mirror row)', async () => {
    const app = await mountDay();
    if (!app.db) throw new Error('no store');
    workOrderQ.deleteMine(scoped(app.db, DANA), 'wo-4831');
    await open(app, 'FF-10');
    await screen.findByTestId('screen-FF-10');
    expect(screen.queryByTestId('job-wo-4831')).toBeNull();
    expect(cardOrder()).toEqual(['wo-4822', 'wo-4824', 'wo-4833']);
    app.unmount();
  });

  test('the next day tab shows only that day', async () => {
    const app = await mountDay();
    await open(app, 'FF-10');
    await screen.findByTestId('screen-FF-10');
    fireEvent.press(screen.getByTestId('day-1'));
    expect(cardOrder()).toEqual(['wo-4901']);
    app.unmount();
  });

  describe('FB-029: Later and All (decision log 2026-10-31, PO C; DEF-FLD-10804)', () => {
    // The fixture's clock is Wed 21 Oct 07:30, so day 3 starts at 00:00 Sat 24 Oct.
    const at = (day: number, h = 0, m = 0) => new Date(2026, 9, day, h, m).toISOString();
    function add(db: NonNullable<Awaited<ReturnType<typeof mountDay>>['db']>, id: string, over: Partial<workOrderQ.WorkOrderFromServer>) {
      workOrderQ.upsertFromServer(
        scoped(db, DANA),
        {
          id, number: id.toUpperCase(), type: 'Meter exchange', state: null, dispatchState: 'scheduled', priorityCode: 'P3',
          priorityRank: null, premiseId: 'p-oak', windowStart: null, windowEnd: null, dueAt: null, estMinutes: 15,
          accessNotes: null, hazards: null, gateCode: null, extra: null, serverUpdatedAt: null, ...over,
        },
        new Date(2026, 9, 21, 7, 30).toISOString(),
      );
    }
    /** Headings and cards, in the order the list draws them. */
    function listOrder(): string[] {
      return screen
        .getAllByTestId(/^(job-wo-\d+|today-heading-[\w-]+)$/)
        .map((el) => String(el.props.testID).replace('job-', '').replace('today-heading-', '# '));
    }

    test('five tabs in the ruled order: Today · the next two days · Later · All', async () => {
      const app = await mountDay();
      await open(app, 'FF-10');
      const tabs = within(await screen.findByTestId('day')).getAllByRole('tab');
      expect(tabs.map((t) => t.props.accessibilityLabel)).toEqual(['Today', 'Thu', 'Fri', 'Later', 'All']);
      expect(assertTouchTargets(tabs)).toBe(5);
      app.unmount();
    });

    test('Later: every job from 00:00 on day 3, under date headings, counted exactly', async () => {
      const app = await mountDay();
      if (!app.db) throw new Error('no store');
      add(app.db, 'wo-5003', { dueAt: at(24, 0, 0), estMinutes: 20 }); // midnight starting day 3
      add(app.db, 'wo-5002', { windowStart: at(23, 23, 0) }); // day after — not Later
      add(app.db, 'wo-5010', { windowStart: at(31, 9), estMinutes: 40 }); // ten days out
      add(app.db, 'wo-5060', { dueAt: at(80, 12), estMinutes: 60 }); // sixty days out
      await open(app, 'FF-10');
      fireEvent.press(await screen.findByTestId('day-later'));
      expect(listOrder()).toEqual(['# 2026-10-24', 'wo-5003', '# 2026-10-31', 'wo-5010', '# 2026-12-19', 'wo-5060']);
      expect(screen.getByTestId('today-summary')).toHaveTextContent('3 jobs · 2h');
      fireEvent.press(screen.getByTestId('day-2'));
      expect(cardOrder()).toEqual(['wo-5002']);
      expect(screen.getByTestId('today-summary')).toHaveTextContent('1 job · 15m');
      app.unmount();
    });

    test('All: overdue and undated included, undated last under No date, counted exactly', async () => {
      const app = await mountDay();
      if (!app.db) throw new Error('no store');
      add(app.db, 'wo-5001', { windowStart: at(19, 10) }); // overdue
      add(app.db, 'wo-5010', { windowStart: at(31, 9) });
      add(app.db, 'wo-5099', {}); // no date at all
      await open(app, 'FF-10');
      fireEvent.press(await screen.findByTestId('day-all'));
      expect(listOrder()).toEqual([
        '# 2026-10-19', 'wo-5001',
        '# 2026-10-21', 'wo-4822', 'wo-4824', 'wo-4831', 'wo-4833',
        '# 2026-10-22', 'wo-4901',
        '# 2026-10-31', 'wo-5010',
        '# none', 'wo-5099',
      ]);
      expect(screen.getByTestId('today-heading-none')).toHaveTextContent('No date');
      // Done (wo-4810) and Marco's (wo-9999) are in no tab.
      expect(cardOrder()).toHaveLength(8);
      expect(screen.getByTestId('today-summary')).toHaveTextContent('8 jobs · 4h 20m');
      // The undated job also sits on Today, and Today counts it (DEF-FLD-10804).
      fireEvent.press(screen.getByTestId('day-0'));
      expect(cardOrder()).toEqual(['wo-5001', 'wo-4822', 'wo-4824', 'wo-4831', 'wo-4833', 'wo-5099']);
      expect(screen.getByTestId('today-summary')).toHaveTextContent('6 jobs · 3h 05m');
      // …and no other day does.
      fireEvent.press(screen.getByTestId('day-1'));
      expect(cardOrder()).toEqual(['wo-4901']);
      expect(screen.getByTestId('today-summary')).toHaveTextContent('1 job · 1h');
      app.unmount();
    });

    test('empty states: Later with nothing further ahead, All with nothing open', async () => {
      const app = await mountDay();
      if (!app.db) throw new Error('no store');
      await open(app, 'FF-10');
      fireEvent.press(await screen.findByTestId('day-later'));
      expect(screen.getByTestId('today-empty')).toHaveTextContent(/No jobs.*Nothing booked further ahead\./);
      expect(screen.queryByTestId(/^today-heading-/)).toBeNull();
      for (const id of ['wo-4822', 'wo-4824', 'wo-4831', 'wo-4833', 'wo-4901']) workOrderQ.deleteMine(scoped(app.db, DANA), id);
      fireEvent.press(screen.getByTestId('day-all'));
      expect(screen.getByTestId('today-empty')).toHaveTextContent(/No jobs.*No open jobs on this phone\./);
      app.unmount();
    });
  });

  test('search "Elm" answers from the handset and says so (US-FLD-037 TC-1, R41, R42); Marco\'s Elm job is not found', async () => {
    const app = await mountDay();
    await open(app, 'FF-10');
    await screen.findByTestId('screen-FF-10');
    fireEvent.changeText(screen.getByTestId('today-search-input'), 'Elm');
    expect(cardOrder()).toEqual(['wo-4822']);
    expect(screen.getByTestId('today-local-only')).toHaveTextContent('Only what is on this phone.');
    app.unmount();
  });

  test('the sync strip counts what is waiting — a number, not a word (R32)', async () => {
    const app = await mountDay();
    await open(app, 'FF-10');
    const strip = within(await screen.findByTestId('sync-strip'));
    expect(strip.getByText('2 waiting to send')).toBeTruthy();
    expect(strip.getByText('1 photo · last sent 10:02')).toBeTruthy();
    // No engine wired → no Send now button (no dead control).
    expect(screen.queryByTestId('sync-strip-send')).toBeNull();
    app.unmount();
  });

  test('Send now runs the wired push and re-reads', async () => {
    const sendNow = jest.fn(async () => undefined);
    const app = await mountDay({ fieldData: { sendNow } });
    await open(app, 'FF-10');
    await screen.findByTestId('screen-FF-10');
    await act(async () => {
      fireEvent.press(screen.getAllByTestId('sync-strip-send')[0] as never);
    });
    expect(sendNow).toHaveBeenCalledTimes(1);
    app.unmount();
  });

  test('with no store on the phone it says the day is not loaded — never an empty day', async () => {
    const app = await mountDay({ noStore: true });
    await open(app, 'FF-10');
    expect(await screen.findByTestId('today-not-loaded')).toHaveTextContent(/Day not loaded/);
    expect(screen.getByTestId('sync-strip')).toHaveTextContent(/Sync not started/);
    app.unmount();
  });

  test('Navigate hands the maps app the street address only (Security §5)', async () => {
    const openURL = jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
    const app = await mountDay();
    await open(app, 'FF-10');
    fireEvent.press(await screen.findByTestId('job-wo-4824-navigate'));
    const url = String(openURL.mock.calls[0]?.[0]);
    expect(decodeURIComponent(url)).toContain('22 Cedar Court, Austin, TX 78704');
    expect(url).not.toMatch(/Bruner|4824/);
    openURL.mockRestore();
    app.unmount();
  });

  test('every control is named and at least 48pt', async () => {
    const app = await mountDay();
    await open(app, 'FF-10');
    const root = await screen.findByTestId('screen-FF-10');
    expect(assertTouchTargets([...within(root).getAllByRole('button'), ...within(root).getAllByRole('tab')])).toBeGreaterThan(10);
    app.unmount();
  });

  describe('its doors, by address', () => {
    test("'FF-10 → FF-15' the card opens the job, with its id", async () => {
      const app = await mountDay();
      await open(app, 'FF-10');
      fireEvent.press(await screen.findByTestId('job-wo-4822-open'));
      expect(`FF-10 → ${current(app)}`).toBe('FF-10 → FF-15');
      expect(currentParams(app)).toEqual({ jobId: 'wo-4822' });
      app.unmount();
    });

    test("'FF-10 → FF-16' Start opens the safety checks", async () => {
      const app = await mountDay();
      await open(app, 'FF-10');
      fireEvent.press(await screen.findByTestId('job-wo-4824-start'));
      expect(`FF-10 → ${current(app)}`).toBe('FF-10 → FF-16');
      expect(currentParams(app)).toEqual({ jobId: 'wo-4824' });
      app.unmount();
    });

    test("'FF-10 → FF-14' ⋮ then Open the stop opens that job's stop", async () => {
      const app = await mountDay();
      await open(app, 'FF-10');
      fireEvent.press(await screen.findByTestId('job-wo-4824-more'));
      fireEvent.press(await screen.findByTestId('today-open-stop'));
      expect(`FF-10 → ${current(app)}`).toBe('FF-10 → FF-14');
      expect(currentParams(app)).toEqual({ jobId: 'wo-4824' });
      app.unmount();
    });

    test("'FF-10 → FF-11' Nearby, 'FF-10 → FF-50' the strip, 'FF-10 → FF-42' the bell", async () => {
      const app = await mountDay();
      await open(app, 'FF-10');
      fireEvent.press(await screen.findByTestId('door-FF-11'));
      expect(`FF-10 → ${current(app)}`).toBe('FF-10 → FF-11');
      await open(app, 'FF-10');
      fireEvent.press((await screen.findAllByTestId('sync-strip-open')).at(-1) as never);
      expect(`FF-10 → ${current(app)}`).toBe('FF-10 → FF-50');
      await open(app, 'FF-10');
      fireEvent.press((await screen.findAllByTestId('door-FF-42')).at(-1) as never);
      expect(`FF-10 → ${current(app)}`).toBe('FF-10 → FF-42');
      app.unmount();
    }, 30_000);

    test("'FF-10 → FF-63' and 'FF-10 → RW-01' are the bottom tabs; 'FF-10 → FF-09' the menu", async () => {
      const app = await mountDay();
      await open(app, 'FF-10');
      fireEvent.press(screen.getByTestId('tab-FF-63'));
      expect(`FF-10 → ${current(app)}`).toBe('FF-10 → FF-63');
      await open(app, 'FF-10');
      fireEvent.press(screen.getByTestId('tab-RW-01'));
      expect(`FF-10 → ${current(app)}`).toBe('FF-10 → RW-01');
      await open(app, 'FF-10');
      fireEvent.press(screen.getAllByTestId('open-menu').at(-1) as never);
      expect(drawerOpen(app) ? 'FF-10 → FF-09' : 'closed').toBe('FF-10 → FF-09');
      app.unmount();
    }, 30_000);
  });
});
