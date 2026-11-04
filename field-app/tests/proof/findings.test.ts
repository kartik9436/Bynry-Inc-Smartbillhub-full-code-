/**
 * @jest-environment node
 *
 * DEFECTS THE PHASE 14 PROOFS FOUND, each HELD OPEN as a `test.failing`: the
 * test states the CORRECT behaviour, so today it fails and `test.failing`
 * reports that as a pass; the day the defect is fixed the assertion passes,
 * `test.failing` goes RED and names it — then turn it into a plain `test`.
 * That is hard-won law 2's "write the test that fires when the hold expires",
 * applied to a defect instead of a hold.
 *
 * Each is bounded so it can never hang the suite (the first one HUNG it when
 * met unbounded — the fake below stops answering after 25 requests).
 */
import { deviceWide } from '../../src/db/scoped';
import { capture, sendPending } from '../../src/sync/outbox';
import { routeItemFromWire } from '../../src/sync/routeReads';
import { TransportError, type BatchAnswer, type WireItem } from '../../src/sync/transport';
import { FakeClock, idSource, openStore, steadyRandom } from '../db/support/fixtures';
import { FakeServer } from '../sync/support/fakeServer';

const dana = { technicianId: 'dana', capturedBy: 'dana' };
const tokens = { tokenFor: () => 'capture-of-dana' };

/** A server that answers every item but one — the shape of an answer the handset cannot read. */
class OneUnanswered extends FakeServer {
  calls = 0;
  override async sendJobBatch(workOrderId: string, items: WireItem[]): Promise<BatchAnswer> {
    this.calls += 1;
    if (this.calls > 25) throw new TransportError('network', 'the fake stops answering (bounds the loop)');
    const answer = await super.sendJobBatch(workOrderId, items);
    const drop = items[items.length - 1]?.key;
    return { ...answer, items: answer.items.filter((i) => i.key !== drop), acknowledged: answer.acknowledged.filter((k) => k !== drop) };
  }
}

/**
 * DEFECT 1 — THE SEND LOOP (DEF-FLD-10356, FIXED by lane INTEGRATE-2:
 * `nextBatch` now takes only what is due, up to the first item backing off;
 * the assertion below was the held-open `test.failing` and is now plain). `outboxQ.nextBatch` selects `state = 'pending'`
 * and ignores `next_attempt_at`. An item the server answers without an ack is
 * put back to pending with a backoff (`receipts.applyBatchAnswer`) — and the
 * very next turn of `sendGroup`'s `for (;;)` picks it straight back up. One
 * run never ends: it re-sends that item without pause for as long as the
 * server answers, so the photo phase and the pull never start, and every
 * later Send now JOINS the run that never finishes. Reached by any receipt the
 * handset cannot read — on the route door, `batchAnswerFromReads` drops an
 * item whose `result` word it does not know (a newer server's word, or the
 * `held_for_review` → `refused` change in flight).
 */
test('DEF-FLD-10356 (fixed): an item the server leaves unanswered waits for its backoff — one run sends it once', async () => {
  const clock = new FakeClock();
  const db = openStore('north', undefined, clock);
  const server = new OneUnanswered();
  capture(db, dana, { kind: 'task_tick', workOrderId: 'wo-1', payload: {} }, { newId: idSource('k'), clock });
  capture(db, dana, { kind: 'task_tick', workOrderId: 'wo-1', payload: {} }, { newId: idSource('j'), clock });
  await sendPending(db, server, { clock, tokens, random: steadyRandom });
  expect(server.calls).toBe(1);
  expect(deviceWide(db, 'count').get<{ n: number }>(`SELECT COUNT(*) AS n FROM outbox WHERE state = 'pending'`)?.n).toBe(1);
});

/**
 * DEFECT 2 (DEF-FLD-10357, FIXED by lane INTEGRATE-2: the declaration is the
 * reads door's own `photo` kind, a link in `field_read_photos`, the bytes to
 * `work/mobile/reads/photos/{id}`) — A ROUTE PHOTOGRAPH'S DECLARATION WENT TO
 * THE READS DOOR AS A READING. `outbox.capture` declares every photo as a `photo` item on its
 * act's channel; on a route that is the `route` channel, and
 * `routeItemFromWire` maps EVERY item to `kind: 'reading'`. So the server
 * stores each route photo's declaration as a reading with no reader status —
 * `held_for_review`, `reader_status_unknown` (BR-WRK-063: stored, never
 * dropped) — one bogus held reading in the office's queue per photograph,
 * while the reading it belongs to arrives with no `photos` list (RW-18's
 * plate photo then holds it as `plate_photo_missing`). The bytes have no door
 * either (`PUT work/mobile/photos/<id>` knows no route photo: 404, kept,
 * retried). The server's door takes photos as ids ON the reading.
 */
test('DEF-FLD-10357 (fixed): a route photo is not sent to the reads door as a reading of its own', () => {
  const declaration: WireItem = {
    key: 'k-photo',
    kind: 'photo',
    seq: 2,
    captured_at: '2026-10-21T10:00:00Z',
    payload: { photo_id: 'ph-1', sha256: 'a'.repeat(64), route_read_id: 'm-1' },
  };
  expect(routeItemFromWire(declaration, 'r-1').kind).not.toBe('reading');
});

/**
 * DEFECT 3 (DEF-FLD-10358, FIXED by lane INTEGRATE-2 on both halves: the
 * handset sends `capture_token`, `field_reads` records the token's captor) —
 * ON THE ROUTE DOOR, A READING TRAVELLED UNDER THE COURIER, NOT ITS CAPTOR. `sendPending` puts the captor's capture credential on every item
 * (`capture_token`); `routeItemFromWire` does not copy it, and the server's
 * `field_reads._base_row` sets `reader_id` from the REQUEST's actor. So Dana's
 * route readings sent while Marco is signed in are Marco's readings at the far
 * end — T-48's guarantee holds on the job door (`tests/proof/handover`) and
 * not on this one. Needs both halves: the handset to send it, the server to
 * read it (as `apps/work/sync.py` does for jobs).
 */
test('DEF-FLD-10358 (fixed): a route reading carries its captor’s capture credential on the wire', () => {
  const item: WireItem = {
    key: 'k-1',
    kind: 'route_read',
    seq: 1,
    captured_at: '2026-10-21T10:00:00Z',
    payload: { meter_no: 'MTR-0001', reader_status: 'read', value: '1.00', unit: 'kWh' },
    capture_token: 'capture-of-dana',
  };
  expect(routeItemFromWire(item, 'r-1')).toHaveProperty('capture_token', 'capture-of-dana');
});

