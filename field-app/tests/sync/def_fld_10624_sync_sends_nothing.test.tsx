/**
 * DEF-FLD-10624 — THE PO'S CASE, END TO END: Sync shows ONLINE with work
 * waiting and the phone sends NOTHING (decision log 2026-10-27, *"start A to F"*).
 *
 * What the PO saw on the Android emulator: a job finished offline, airplane
 * mode off, FF-50 showing **ONLINE**, **"16 waiting"**, *Sync now* pressed
 * again and again and the app restarted — for fifteen minutes — and the
 * server's access log held **zero** `/work/mobile/` and **zero**
 * `/auth/token` requests. The office went on reading *"Not accepted yet"*.
 *
 * Built here the way it happened, through the app the handset mounts:
 *   1. the day's job is on the phone; the signal goes; the technician
 *      ticks the safety check and a step (the job's accept is queued ahead
 *      of them, DEF-FLD-10612);
 *   2. the signal comes back but every call dies — the items back off,
 *      run after run, to the ten-minute step, and the hour of the access
 *      token runs out on the way;
 *   3. the connection is good again, NetInfo's check never answers (the
 *      run waited on it with no limit), and the technician opens FF-50 and
 *      presses *Sync now*.
 * The wire here behaves as `HttpTransport` does: with no live access token a
 * call is refused ON THE PHONE (`no access token`) and never counted as a
 * request — which is exactly *zero requests*.
 *
 * Proved RED on the code before this fix (law 7), quoted in the commit that
 * lands the fix.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';

import * as outboxQ from '../../src/db/queries/outbox';
import * as syncStateQ from '../../src/db/queries/syncState';
import * as woItemQ from '../../src/db/queries/woItem';
import { scoped } from '../../src/db/scoped';
import { tickSafety, tickTask } from '../../src/screens/theJob/actions';
import { DELTA_TABLE } from '../../src/sync/delta';
import { TransportError } from '../../src/sync/transport';
import { buildHandset, card, mountHandset, openAt, PEOPLE, settle, signInAs, TENANT, upsert } from '../proof/runtimeApp';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const DANA = PEOPLE['d.ortiz']!.technicianId;
const MINUTE = 60_000;

interface Wire {
  /** Every call dies as a dropped connection. */
  down: boolean;
  /** Calls that LEFT the phone (an access-token refusal on the phone is not one). */
  requests: number;
}

/** The server behind a wire that behaves as `HttpTransport` does. */
function gated<T extends object>(target: T, accessToken: () => string | null, wire: Wire): T {
  return new Proxy(target, {
    get(t, prop) {
      const v = Reflect.get(t, prop, t) as unknown;
      if (typeof v !== 'function') return v;
      return (...args: unknown[]) => {
        if (!accessToken()) return Promise.reject(new TransportError('auth', 'no access token — sending waits for sign-in'));
        if (wire.down) return Promise.reject(new TransportError('network', 'Network request failed'));
        wire.requests += 1;
        return (v as (...a: unknown[]) => unknown).apply(t, args);
      };
    },
  });
}

test('PO case: back online after failures, the token past its hour and NetInfo hung — Sync now sends everything and the count drops', async () => {
  const h = buildHandset({ network: 'wifi' });
  const wire: Wire = { down: false, requests: 0 };
  const server = h.serverFor(TENANT);
  h.deps.transportFor = (tenant, accessToken) => gated(h.serverFor(tenant), accessToken, wire) as never;
  // A hung step ends quickly here; the app's own limits are seconds.
  (h.deps as unknown as { limits: object }).limits = { networkMs: 50, stepMs: 500, runMs: 2000 };
  const id = 'wo-0155';
  server.feed([upsert(card(id, 'WO-0155', new Date(h.clock.now() + 30 * MINUTE), 40), h.iso())]);
  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  const db = h.holder.current!;
  const s = scoped(db, DANA);
  db.transaction(() => {
    woItemQ.upsert(s, { id: `${id}-safe`, workOrderId: id, kind: 'safety', position: 1, label: 'Isolate supply' }, h.iso());
    woItemQ.upsert(s, { id: `${id}-task`, workOrderId: id, kind: 'task', position: 2, label: 'Swap the meter' }, h.iso());
  });

  // 1. No signal: the job is done on the phone.
  await act(async () => h.network.set('none'));
  const port = m.inside.current.job!;
  tickSafety(port, id, `${id}-safe`);
  tickTask(port, id, `${id}-task`);
  const waiting = outboxQ.countUnsentMine(s);
  expect(waiting).toBeGreaterThanOrEqual(3); // the accept, the safety check, the step

  // 2. The signal comes back and every call dies; the automatic runs back off
  //    to ten minutes, and the access token's hour runs out on the way.
  wire.down = true;
  h.api.online = false; // the sign-in server is behind the same dead connection
  await act(async () => h.network.set('wifi'));
  await settle();
  for (let i = 0; i < 7; i++) {
    h.clock.advance(11 * MINUTE);
    await act(async () => {
      await m.inside.current.runtime!.syncNow();
    });
  }
  expect(outboxQ.countUnsentMine(s)).toBe(waiting);
  expect(h.session.courierAccessToken()).toBeNull(); // past the hour
  // The last automatic run left the work backing off.
  h.clock.advance(1 * MINUTE);

  // 3. The connection is good; NetInfo's check never answers.
  wire.down = false;
  h.api.online = true;
  const before = wire.requests;
  h.network.kind = () => new Promise(() => undefined);

  await act(async () => {
    m.inside.current.runtime!.syncNow().catch(() => undefined); // an automatic run, hung on the check
  });
  await openAt(m, 'FF-50');
  const ff50 = within(await screen.findByTestId('screen-FF-50'));
  expect(ff50.getByTestId('ff50-connection')).toHaveTextContent(/online/i);
  await act(async () => {
    fireEvent.press(ff50.getByTestId('ff50-sync-now'));
  });

  await waitFor(() => expect(outboxQ.countUnsentMine(s)).toBe(0), { timeout: 4000 });
  expect(wire.requests).toBeGreaterThan(before);
  expect(server.applied.map((a) => a.kind)).toEqual(expect.arrayContaining(['safety_tick', 'task_tick']));
  await waitFor(() => expect(ff50.getByTestId('ff50-completed')).toHaveTextContent(/All sent/));
  // B: a send that reached the server moves "Last reached the server".
  expect(syncStateQ.get(s, DELTA_TABLE)?.last_push_at).toBe(h.iso());
}, 20_000);
