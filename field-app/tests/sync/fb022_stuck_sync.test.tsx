/**
 * FB-022 (DEF-FLD-10793, -10794, -10795) — a reading that never sends.
 *
 * The PO watched *"The server had a problem. Trying again."* with
 * *Completed work 1 waiting* forever: the phone kept only `HTTP 500`, dropped
 * the server's `trace_id`, never listed the item after five failures, and
 * said the same sentence for a 5xx, a 200 with no receipt and a failed
 * download.
 *
 *  1 — a 5xx keeps the server's `trace_id`; FF-50 shows it as a short Reference;
 *  2 — after five failures the PENDING item is listed under *Needs attention*
 *      with its reason, reference and *Send again*, which clears its wait;
 *  3 — `no_receipt_for_item` and a download 5xx each have their own reason.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import * as outboxQ from '../../src/db/queries/outbox';
import { deviceWide, scoped } from '../../src/db/scoped';
import { createDbMeData } from '../../src/screens/me/dbData';
import { SyncEngine } from '../../src/sync/engine';
import { capture } from '../../src/sync/outbox';
import { applyBatchAnswer } from '../../src/sync/receipts';
import { reasonOfLastError, reasonOfResult, referenceOf, type SyncRunOutcome } from '../../src/sync/syncReason';
import { HttpTransport, TransportError, type SyncFailure, type WireItem } from '../../src/sync/transport';
import { FakeClock, idSource, MemoryFiles, openStore, steadyRandom } from '../db/support/fixtures';
import { DANA, makeFixture, NOW, openScreen } from '../screens/me/support';
import { FakeServer } from './support/fakeServer';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

const TRACE = '7f3a9c21d4e84b0f9a6c55e1b2d3f4a5';

/** What the real `HttpTransport` raises for the server's 500 envelope (`core/errors.py`). */
async function server500(): Promise<TransportError> {
  const fetchImpl = jest.fn(async () => ({
    status: 500,
    ok: false,
    headers: { get: () => null },
    json: async () => ({ code: 'SYS-INTERNAL', message_key: 'errors.internal', trace_id: TRACE }),
  }));
  const t = new HttpTransport({ origin: 'https://x', tenant: 'north', accessToken: () => 'a', fetchImpl: fetchImpl as unknown as typeof fetch, appHeaders: () => ({}) });
  try {
    await t.sendJobBatch('wo-1', []);
  } catch (err) {
    return err as TransportError;
  }
  throw new Error('expected the 500 to raise');
}

/** A store whose one reading has failed with the server's 500 `times` times, through the engine. */
async function failedTimes(times: number) {
  const clock = new FakeClock(NOW.getTime());
  const db = openStore('silver-creek', undefined, clock);
  const key = capture(db, { technicianId: DANA, capturedBy: DANA }, { kind: 'reading', workOrderId: 'wo-1', payload: { value: '0' } }, { newId: idSource('r'), clock }).key;
  const server = new FakeServer();
  const err = await server500();
  server.sendJobBatch = (_id: string, _items: WireItem[]) => Promise.reject(err);
  const engine = new SyncEngine({ db, transport: server, files: new MemoryFiles(), tokens: { tokenFor: () => 't' }, clock, random: steadyRandom });
  for (let i = 0; i < times; i += 1) {
    await engine.sync({ technicianId: DANA, network: 'wifi', skipPull: true });
    clock.advance(11 * 60_000);
  }
  return { db, key, clock };
}

describe('1 — a 5xx keeps the server’s trace_id', () => {
  test('the saved failure carries it, and it reads as a short reference', async () => {
    const { db, key } = await failedTimes(1);
    const row = outboxQ.getMine(scoped(db, DANA), key)!;
    expect(row.state).toBe('pending');
    expect(reasonOfLastError(row.last_error)).toBe('server');
    expect(referenceOf(row.last_error)).toBe('7F3A-9C21');
  });

  test('no trace id (an HTML 502 from a proxy), no reference', () => {
    expect(referenceOf('HTTP 502')).toBeNull();
    expect(referenceOf(null)).toBeNull();
  });
});

describe('2 — five failures: listed under Needs attention', () => {
  test('the port lists the PENDING item with its reason and reference', async () => {
    const { db, key } = await failedTimes(5);
    const items = createDbMeData(db, { newId: idSource('x') }).needsAttention!(DANA)!;
    expect(items.map((i) => i.id)).toEqual([key]);
    expect(items[0]).toMatchObject({ kind: 'reading', reason: 'server', reference: '7F3A-9C21', failures: 5 });
  });

  test('four failures: not yet', async () => {
    const { db } = await failedTimes(4);
    expect(createDbMeData(db, { newId: idSource('x') }).needsAttention!(DANA)).toEqual([]);
  });

  test('FF-50 shows it, and Send again clears its wait and runs a sync; nothing is discarded', async () => {
    const { db, key } = await failedTimes(5);
    const syncNow = jest.fn(async (): Promise<SyncRunOutcome> => ({ reason: 'server', sent: 0 }));
    const f = makeFixture({ sync: { syncNow } });
    // The fixture's store, with the stuck row copied in as the engine left it.
    const row = outboxQ.getMine(scoped(db, DANA), key)!;
    const k2 = capture(f.db, { technicianId: DANA, capturedBy: DANA }, { kind: 'reading', workOrderId: 'wo-1', payload: { value: '0' } }, { newId: f.ids, clock: { now: () => NOW } }).key;
    deviceWide(f.db, 'receipt').run(`UPDATE outbox SET attempts = :a, last_error = :e, next_attempt_at = :n WHERE id = :id`, {
      a: row.attempts,
      e: row.last_error,
      n: '2099-01-01T00:00:00.000Z',
      id: k2,
    });
    const app = await openScreen('FF-50', f);
    const top = within(screen.getAllByTestId('screen-FF-50').at(-1) as Parameters<typeof within>[0]);
    const card = top.getByTestId('ff50-attention');
    expect(card).toHaveTextContent(/Needs attention/);
    expect(top.getByTestId(`ff50-attention-reason-${k2}`)).toHaveTextContent('The server had a problem. Trying again.');
    expect(top.getByTestId(`ff50-attention-ref-${k2}`)).toHaveTextContent('Reference 7F3A-9C21');
    await act(async () => {
      fireEvent.press(top.getByTestId(`ff50-attention-send-${k2}`));
    });
    const after = outboxQ.getMine(scoped(f.db, DANA), k2)!;
    expect(after.state).toBe('pending');
    expect(after.next_attempt_at).toBeNull();
    expect(syncNow).toHaveBeenCalledWith({ manual: true });
    app.unmount();
  });
});

describe('3 — each failure says its own thing', () => {
  test('a 200 with no receipt for the item: its own reason', () => {
    const clock = new FakeClock(NOW.getTime());
    const db = openStore('silver-creek', undefined, clock);
    const key = capture(db, { technicianId: DANA, capturedBy: DANA }, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, { newId: idSource('r'), clock }).key;
    const rows = outboxQ.listMine(scoped(db, DANA), { limit: 5 });
    applyBatchAnswer(db, rows, { accepted: 0, duplicate: 0, refused: 0, acknowledged: [], items: [] }, clock.now(), steadyRandom);
    expect(outboxQ.getMine(scoped(db, DANA), key)!.last_error).toBe('no_receipt_for_item');
    expect(reasonOfLastError('no_receipt_for_item')).toBe('unconfirmed');
  });

  test('a download the server failed is not a failed send', () => {
    const pull: SyncFailure = { kind: 'network', status: 500, message: 'HTTP 500' };
    const result = { data: { waitingForCaptor: 0 }, failures: { pull, bundles: null, templates: null } } as unknown as Parameters<typeof reasonOfResult>[0];
    expect(reasonOfResult(result)).toBe('downloadServer');
  });

  test('FF-50 says it in words', async () => {
    const f = makeFixture();
    const key = capture(f.db, { technicianId: DANA, capturedBy: DANA }, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, { newId: f.ids, clock: { now: () => NOW } }).key;
    outboxQ.retryLater(deviceWide(f.db, 'receipt'), key, null, 'no_receipt_for_item', true);
    const app = await openScreen('FF-50', f);
    const top = within(screen.getAllByTestId('screen-FF-50').at(-1) as Parameters<typeof within>[0]);
    expect(top.getByTestId('ff50-reason')).toHaveTextContent('Sent, not confirmed. Trying again.');
    app.unmount();
  });
});
