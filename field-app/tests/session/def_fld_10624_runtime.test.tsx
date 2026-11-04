/**
 * DEF-FLD-10624 — the runtime's run (`session/FieldRuntime.tsx` syncNow), each
 * guarantee alone (decision log 2026-10-27, *"start A to F"*):
 *  - F: a hung step ends the run with *Run timed out*, and the NEXT press
 *    starts a fresh run instead of joining the dead one;
 *  - F: a network check that never answers is *unknown — try anyway*;
 *  - the access token past its hour is RENEWED with a signal before sending
 *    (Security §1) — nothing called `refresh()` before this;
 *  - C: a press never joins an automatic run (that run kept the backoff);
 *  - A: no signal answers *offline*.
 */
import 'react-native-gesture-handler/jestSetup';

import { act } from '@testing-library/react-native';

import * as outboxQ from '../../src/db/queries/outbox';
import { deviceWide, scoped } from '../../src/db/scoped';
import { capture } from '../../src/sync/outbox';
import type { SyncRunOutcome } from '../../src/sync/syncReason';
import type { ChangesPage } from '../../src/sync/transport';
import { buildHandset, mountHandset, PEOPLE, settle, signInAs, TENANT } from '../proof/runtimeApp';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const DANA = PEOPLE['d.ortiz']!.technicianId;
const HOUR = 60 * 60_000;

async function signedIn(network: 'wifi' | 'none' = 'wifi') {
  const h = buildHandset({ network });
  (h.deps as unknown as { limits: object }).limits = { networkMs: 30, stepMs: 300, runMs: 300 };
  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  const db = h.holder.current!;
  const s = scoped(db, DANA);
  let n = 0;
  const work = () =>
    capture(db, { technicianId: DANA, capturedBy: DANA }, { kind: 'task_tick', workOrderId: 'wo-9', payload: {} }, { newId: () => `k-${(n += 1)}`, clock: { now: () => new Date(h.clock.now()) } }).key;
  const press = async (opts?: { manual?: boolean }): Promise<SyncRunOutcome> => {
    let out: SyncRunOutcome | undefined;
    await act(async () => {
      out = await m.inside.current.runtime!.syncNow(opts);
    });
    return out!;
  };
  return { h, m, db, s, work, press, server: h.serverFor(TENANT) };
}

test('F: a hung step ends the run as "timed out", and the next press starts afresh and sends', async () => {
  const t = await signedIn();
  t.work();
  const changes = t.server.changes.bind(t.server);
  let hang = true;
  t.server.changes = (c: string | null, n: number) => (hang ? new Promise<ChangesPage>(() => undefined) : changes(c, n));
  const first = await t.press({ manual: true });
  expect(first.reason).toBe('timedOut');
  hang = false;
  t.work();
  const second = await t.press({ manual: true });
  expect(second.reason).toBeNull();
  expect(outboxQ.countUnsentMine(t.s)).toBe(0);
});

test('F: a network check that never answers is unknown — the run tries anyway and sends', async () => {
  const t = await signedIn();
  t.h.network.kind = () => new Promise(() => undefined);
  t.work();
  const out = await t.press({ manual: true });
  expect(out.sent).toBe(1);
  expect(outboxQ.countUnsentMine(t.s)).toBe(0);
});

test('the access token past its hour is renewed with a signal before sending', async () => {
  const t = await signedIn();
  t.h.clock.advance(2 * HOUR);
  expect(t.h.session.courierAccessToken()).toBeNull();
  t.work();
  const before = t.h.api.calls.filter((c) => c === 'refresh').length;
  await t.press();
  expect(t.h.api.calls.filter((c) => c === 'refresh').length).toBe(before + 1);
  expect(t.h.session.courierAccessToken()).not.toBeNull();
});

test('C: a press clears the backoff; an automatic run keeps it', async () => {
  const t = await signedIn();
  const key = t.work();
  outboxQ.retryLater(deviceWide(t.db, 'receipt'), key, new Date(t.h.clock.now() + 10 * 60_000).toISOString(), 'Network request failed', true);
  await t.press();
  expect(outboxQ.countUnsentMine(t.s)).toBe(1);
  await t.press({ manual: true });
  expect(outboxQ.countUnsentMine(t.s)).toBe(0);
});

test('C: a press never joins an automatic run in flight — it waits it out and runs its own', async () => {
  const t = await signedIn();
  const key = t.work();
  outboxQ.retryLater(deviceWide(t.db, 'receipt'), key, new Date(t.h.clock.now() + 10 * 60_000).toISOString(), 'Network request failed', true);
  let both: [SyncRunOutcome, SyncRunOutcome] | undefined;
  await act(async () => {
    const rt = t.m.inside.current.runtime!;
    both = await Promise.all([rt.syncNow(), rt.syncNow({ manual: true })]);
  });
  expect(both![0]).not.toBe(both![1]);
  expect(outboxQ.countUnsentMine(t.s)).toBe(0);
});

test('A: no signal answers "offline"', async () => {
  const t = await signedIn('none');
  t.work();
  expect((await t.press({ manual: true })).reason).toBe('offline');
});
