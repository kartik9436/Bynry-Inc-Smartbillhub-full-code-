/**
 * DEF-FLD-10639 — FB-014 (PO 2026-10-28): a phone whose clock disagrees with
 * the server is never refused. The phone sends its clock on EVERY call
 * (`X-Device-Time`), the server shifts the times, and FF-50 tells the
 * technician to fix the clock past 5 minutes while the work still goes.
 *
 * RED FIRST (2026-10-28): before this the transport sent no clock reading,
 * nothing on the phone measured the difference, FF-50 had no warning, and a
 * `work.labour.moment_in_future` refusal read *Fix and send again* — a button
 * with nothing to fix.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, screen, within } from '@testing-library/react-native';

import { readRefusal } from '../../src/screens/me/refusalGroups';
import { clockOffsetMs, clockWarning, recordServerTime, setClockOffsetMs } from '../../src/sync/deviceClock';
import { HttpTransport } from '../../src/sync/transport';
import { makeFixture, openScreen } from '../screens/me/support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

function reply(headers: Record<string, string>) {
  return {
    status: 200,
    ok: true,
    json: async () => ({ items: [], accepted: 0, duplicate: 0, refused: 0, acknowledged: [] }),
    headers: { get: (name: string) => headers[name] ?? null },
  };
}

afterEach(() => setClockOffsetMs(null));

describe('every call carries the phone clock, and the answer measures it', () => {
  test.each([
    ['30 s fast', 30_000, null],
    ['10 min fast', 600_000, { direction: 'fast', minutes: 10 }],
    ['1 h fast', 3_600_000, { direction: 'fast', minutes: 60 }],
    ['10 min slow', -600_000, { direction: 'slow', minutes: 10 }],
  ])('a phone %s', async (_name, aheadMs, warning) => {
    const server = Date.parse('2026-10-28T12:02:30Z');
    const phone = new Date(server + aheadMs);
    const sent: RequestInit[] = [];
    const fetchImpl = jest.fn(async (_url: string, init: RequestInit) => {
      sent.push(init);
      return reply({ 'X-Server-Time': new Date(server).toISOString() });
    });
    const t = new HttpTransport({
      origin: 'https://x',
      tenant: 'north',
      accessToken: () => 'acc',
      fetchImpl: fetchImpl as unknown as typeof fetch,
      appHeaders: () => ({}),
      now: () => phone,
    });
    await t.sendJobBatch('wo-1', []);
    expect((sent[0]?.headers as Record<string, string>)['X-Device-Time']).toBe(phone.toISOString());
    expect(clockOffsetMs()).toBe(-aheadMs);
    expect(clockWarning(clockOffsetMs())).toEqual(warning);
  });

  test('the PO worked figure: phone 12:07:30, server 12:02:30 → 5 min fast, not yet warned', () => {
    const phone = new Date('2026-10-28T12:07:30Z');
    recordServerTime(phone, phone, '2026-10-28T12:02:30Z');
    expect(clockOffsetMs()).toBe(-300_000);
    expect(clockWarning(clockOffsetMs())).toBeNull();
  });

  test('the travel time is halved out — a slow network is not a wrong clock', () => {
    recordServerTime(new Date('2026-10-28T12:00:00Z'), new Date('2026-10-28T12:00:20Z'), '2026-10-28T12:00:10Z');
    expect(clockOffsetMs()).toBe(0);
  });

  test('an answer with no server time changes nothing', () => {
    setClockOffsetMs(-900_000);
    recordServerTime(new Date(), new Date(), null);
    recordServerTime(new Date(), new Date(), 'not a time');
    expect(clockOffsetMs()).toBe(-900_000);
  });
});

describe('a clock refusal is Send again, never Fix and send again', () => {
  test.each(['work.labour.moment_in_future', 'work.raise.captured_in_future', 'work.shifts.future_day'])('%s', (key) => {
    const refusal = JSON.stringify({ result: 'refused', detail: { message_key: key } });
    expect(readRefusal(refusal).action).toBe('sendAgain');
  });

  test('a finish before the arrival still needs fixing', () => {
    const refusal = JSON.stringify({ detail: { message_key: 'work.labour.finished_before_starting' } });
    expect(readRefusal(refusal).action).toBe('fix');
  });
});

describe('FF-50 says it past 5 minutes, and the work still goes', () => {
  test('10 min fast → "Phone clock is 10 min fast. Fix the time."', async () => {
    setClockOffsetMs(-600_000);
    const app = await openScreen('FF-50', makeFixture(), { status: { syncPending: 0, connection: 'online', availability: null } });
    const s = within(screen.getAllByTestId('screen-FF-50').at(-1) as Parameters<typeof within>[0]);
    expect(s.getByTestId('ff50-clock')).toHaveTextContent('Phone clock is 10 min fast. Fix the time.');
    await act(async () => setClockOffsetMs(120_000));
    expect(s.queryByTestId('ff50-clock')).toBeNull();
    app.unmount();
  });

  test('10 min slow says slow', async () => {
    setClockOffsetMs(600_000);
    const app = await openScreen('FF-50', makeFixture());
    const s = within(screen.getAllByTestId('screen-FF-50').at(-1) as Parameters<typeof within>[0]);
    expect(s.getByTestId('ff50-clock')).toHaveTextContent('Phone clock is 10 min slow. Fix the time.');
    app.unmount();
  });
});
