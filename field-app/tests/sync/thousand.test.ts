/**
 * @jest-environment node
 *
 * T-45 / E2E-03 — the thousand-reading route. 1,000 meters read with no
 * signal; eleven out of range and taken anyway; three could not be read and
 * carry a photograph. Back at the depot it sends in batches of fifty, and the
 * connection dies DURING batch 7 and again DURING batch 14. The office must
 * count exactly 1,000 readings — "not 1,048 from the re-sent batches, not 963".
 *
 * ⚠ The route-reading endpoint does not exist on the server yet (see
 * `transport.ts`). This runs the engine against the fake, which implements the
 * job-sync contract's semantics on a route door — the engine half of T-45.
 */
import type { TenantDb } from '../../src/db/database';
import * as routeReadQ from '../../src/db/queries/routeRead';
import { deviceWide, scoped } from '../../src/db/scoped';
import { capture, sendPending } from '../../src/sync/outbox';
import { uploadPhotos } from '../../src/sync/photos';
import { HttpTransport } from '../../src/sync/transport';
import { FakeClock, idSource, MemoryFiles, openStore, steadyRandom } from '../db/support/fixtures';
import { FakeReadsDoor, MAX_ITEMS } from './support/fakeReadsDoor';
import { FakeServer, sha256 } from './support/fakeServer';

const METERS = 1000;
const dana = { technicianId: 'dana', capturedBy: 'dana' };

function count(db: TenantDb, sql: string): number {
  return deviceWide(db, 'count').get<{ n: number }>(sql)?.n ?? 0;
}

test('1,000 readings, 20 batches of 50, the connection killed mid-batch twice: nothing lost, nothing doubled', async () => {
  const clock = new FakeClock();
  const db = openStore('north', undefined, clock);
  const s = scoped(db, 'dana');
  const deps = { newId: idSource('k'), clock };
  const server = new FakeServer();
  const files = new MemoryFiles();

  // The route, downloaded at the depot.
  db.transaction(() => {
    for (let i = 1; i <= METERS; i++) {
      routeReadQ.upsertFromServer(
        s,
        { id: `m-${i}`, routeId: 'r-1', stopId: `s-${Math.ceil(i / 3)}`, assetId: `a-${i}`, unit: 'kWh', previousValue: '48210.50', expectedMin: '48210.50', expectedMax: '56000.00' },
        clock.iso(),
      );
    }
  });

  // Airplane mode. A thousand captures, each its own act, each instant.
  const started = Date.now();
  const unreadable = new Set([100, 500, 900]);
  const outOfRange = new Set([5, 50, 150, 250, 350, 450, 550, 650, 750, 850, 950]);
  for (let i = 1; i <= METERS; i++) {
    clock.advance(20_000);
    const cannot = unreadable.has(i);
    const path = `/photos/m-${i}.jpg`;
    if (cannot) {
      files.add(path);
      server.disk.set(path, `jpeg-bytes-${i}`);
    }
    const value = cannot ? null : outOfRange.has(i) ? '60000.00' : `${48300 + i}.25`;
    capture(
      db,
      dana,
      {
        kind: 'route_read',
        routeId: 'r-1',
        payload: { route_read_id: `m-${i}`, value, unit: 'kWh' },
        location: { lat: 30.2672, lng: -97.7431, accuracy_m: 6, fix_at: clock.iso() },
        photos: cannot
          ? [{ localPath: path, sha256: sha256(`jpeg-bytes-${i}`), bytes: 300_000, target: { route_read_id: `m-${i}` } }]
          : [],
        apply: (sc, key) =>
          routeReadQ.recordCapture(sc, `m-${i}`, {
            captureKey: key,
            value,
            unit: 'kWh',
            readerStatus: cannot ? 'could_not_read' : 'read',
            noReadReason: cannot ? 'dog' : null,
            warnedAccepted: outOfRange.has(i),
            capturedAt: clock.iso(),
            capturedBy: 'dana',
            identifiedBy: 'scan',
            readMethod: 'manual',
          }),
      },
      deps,
    );
  }
  const captureMs = Date.now() - started;
  // ⚠ Raised from 5s to 15s (proof lane, 2026-10-21): load-sensitive under `jest -w 2`.
  expect(captureMs).toBeLessThan(15_000); // "capture is never the bottleneck"
  const items = count(db, 'SELECT COUNT(*) AS n FROM outbox');
  expect(items).toBe(METERS + unreadable.size); // each photo is declared as its own item

  // Back at the depot. Batch 7 dies after 23 items; batch 14 after 9.
  server.killPlan.set(7, 23);
  server.killPlan.set(14, 9);
  const tokens = { tokenFor: () => 'token-of-dana' };
  let runs = 0;
  while (count(db, `SELECT COUNT(*) AS n FROM outbox WHERE state IN ('pending','sending')`) > 0) {
    runs += 1;
    expect(runs).toBeLessThan(10);
    await sendPending(db, server, { clock, tokens, random: steadyRandom });
    clock.advance(10 * 60_000);
  }

  // The arithmetic at the other end.
  const readings = server.applied.filter((a) => a.kind === 'route_read');
  expect(readings).toHaveLength(METERS);
  expect(new Set(readings.map((r) => r.key)).size).toBe(METERS);
  expect(new Set(readings.map((r) => r.payload['route_read_id'])).size).toBe(METERS);
  expect(readings.filter((r) => r.payload['value'] === '60000.00')).toHaveLength(11);
  expect(readings.filter((r) => r.payload['value'] === null)).toHaveLength(3);
  expect(server.applied).toHaveLength(items);

  // The send resumed: clean batches + the two that died, and every batch ≤ 50.
  const cleanBatches = Math.ceil(items / 50);
  expect(server.requests).toHaveLength(cleanBatches + 2);
  expect(Math.max(...server.requests.map((r) => r.size))).toBeLessThanOrEqual(50);
  expect(server.duplicatesAnswered).toBe(23 + 9); // what had landed before each drop, answered, not applied

  // Every row on the handset settled; every reading's own state says so.
  expect(count(db, `SELECT COUNT(*) AS n FROM outbox WHERE state IN ('accepted','duplicate')`)).toBe(items);
  expect(count(db, `SELECT COUNT(*) AS n FROM route_read WHERE state IN ('accepted','duplicate')`)).toBe(METERS);

  // Then the three photographs, on their own phase.
  const photos = await uploadPhotos(db, server, files, { clock, network: 'wifi' });
  expect(photos.uploaded).toBe(3);
  // FB-030: confirmed, and the files kept for the record (the purge takes them 3 days on).
  expect(files.paths.size).toBe(3);
  expect(server.photoBytes.size).toBe(3);
});

/**
 * T-45, the ROUTE DOOR. The same thousand, sent the way the reading mode
 * really sends them: through `HttpTransport.sendRouteReads` and the mapping
 * both ways in `sync/routeReads.ts`, to a fake of `POST work/mobile/reads/sync`
 * that keeps the server's own shape (`support/fakeReadsDoor.ts`): fifty items
 * a request at most, ONE TRANSACTION PER REQUEST, one row per key.
 *
 * On an atomic door a dropped connection means one of two things, and the
 * connection is killed once each way: request 7 is COMMITTED and its answer
 * lost (the resend must come back fifty `duplicate`s and store nothing), and
 * request 14 never arrives (nothing stored; the resend stores it). The office
 * must count exactly 1,000 rows — every meter once, eleven warned-and-kept,
 * three could-not-read with their reason.
 *
 * The three could-not-read meters carry NO photograph here, unlike the test
 * above: a route photograph has no door yet and its declaration is mis-sent
 * as a reading (`tests/proof/findings.test.ts`, held open there).
 *
 * Proved RED (lane report): with `applyBatchFailure` settling a dropped
 * batch as `accepted` instead of pending, the office counted 950 — the batch
 * that never arrived was lost. (Re-minting the key per send was tried first:
 * it HUNG the run instead of failing, which is the send-loop defect held open
 * in `tests/proof/findings.test.ts`.)
 */
test('T-45 through the route door: 1,000 readings, 20 requests of 50, killed once after commit and once before — the office counts 1,000', async () => {
  const clock = new FakeClock();
  const db = openStore('north', undefined, clock);
  const s = scoped(db, 'dana');
  const deps = { newId: idSource('k'), clock };
  const door = new FakeReadsDoor();
  const transport = new HttpTransport({
    origin: 'https://utility.example',
    tenant: 'north',
    accessToken: () => 'access-of-dana',
    fetchImpl: door.fetch as typeof fetch,
  });

  db.transaction(() => {
    for (let i = 1; i <= METERS; i++) {
      routeReadQ.upsertFromServer(s, { id: `m-${i}`, routeId: 'r-1', stopId: `s-${Math.ceil(i / 3)}`, assetId: `a-${i}`, unit: 'kWh', previousValue: '48210.50' }, clock.iso());
    }
  });

  const unreadable = new Set([100, 500, 900]);
  const outOfRange = new Set([5, 50, 150, 250, 350, 450, 550, 650, 750, 850, 950]);
  const started = Date.now();
  for (let i = 1; i <= METERS; i++) {
    clock.advance(20_000);
    const cannot = unreadable.has(i);
    const value = cannot ? null : outOfRange.has(i) ? '60000.00' : `${48300 + i}.25`;
    // The payload `screens/reads/acts.ts saveReading` writes — what the door identifies the meter by.
    capture(
      db,
      dana,
      {
        kind: 'route_read',
        routeId: 'r-1',
        payload: {
          route_read_id: `m-${i}`,
          asset_id: `a-${i}`,
          meter_no: `MTR-${String(i).padStart(4, '0')}`,
          premises_id: `p-${Math.ceil(i / 3)}`,
          register: null,
          value,
          unit: 'kWh',
          reader_status: cannot ? 'could_not_read' : 'read',
          no_read_reason: cannot ? 'dog' : null,
          warned_accepted: outOfRange.has(i),
          identified_by: 'scan',
          read_method: 'manual',
          fix_quality: 'good',
        },
        location: { lat: 30.2672, lng: -97.7431, accuracy_m: 6, fix_at: clock.iso() },
        apply: (sc, key) =>
          routeReadQ.recordCapture(sc, `m-${i}`, {
            captureKey: key,
            value,
            unit: 'kWh',
            readerStatus: cannot ? 'could_not_read' : 'read',
            noReadReason: cannot ? 'dog' : null,
            warnedAccepted: outOfRange.has(i),
            capturedAt: clock.iso(),
            capturedBy: 'dana',
            identifiedBy: 'scan',
            readMethod: 'manual',
          }),
      },
      deps,
    );
  }
  // ⚠ 15s here, not the 5s above (proof lane, 2026-10-21): a thousand synchronous
  // SQLite transactions take about a second alone and can pass 5s under
  // `jest -w 2` with the whole suite on the same cores. The claim is "capture
  // is never the bottleneck", not a benchmark.
  expect(Date.now() - started).toBeLessThan(15_000);
  expect(count(db, 'SELECT COUNT(*) AS n FROM outbox')).toBe(METERS);

  door.killPlan.set(7, 'after');
  door.killPlan.set(14, 'before');
  const tokens = { tokenFor: () => 'capture-of-dana' };
  let runs = 0;
  while (count(db, `SELECT COUNT(*) AS n FROM outbox WHERE state IN ('pending','sending')`) > 0) {
    runs += 1;
    expect(runs).toBeLessThan(10);
    await sendPending(db, transport, { clock, tokens, random: steadyRandom });
    clock.advance(10 * 60_000);
  }

  // THE ARITHMETIC AT THE OTHER END.
  const rows = [...door.rows.values()];
  expect(rows).toHaveLength(METERS);
  expect(new Set(rows.map((r) => r.meter_no)).size).toBe(METERS);
  expect(rows.filter((r) => r.outcome === 'posted')).toHaveLength(METERS);
  expect(rows.filter((r) => r.accepted_anyway)).toHaveLength(11);
  expect(rows.filter((r) => r.value === '60000.00')).toHaveLength(11);
  const couldNot = rows.filter((r) => r.reader_status === 'could_not_read');
  expect(couldNot.map((r) => [r.value, r.cant_read_reason])).toEqual([
    [null, 'dog'],
    [null, 'dog'],
    [null, 'dog'],
  ]);
  expect(rows.every((r) => r.unit === 'kWh' && r.route_id === 'r-1')).toBe(true); // hard rule 3

  // The wire: 20 clean requests + the two that died, none over fifty; the
  // committed-then-lost batch came back as fifty duplicates that stored nothing.
  expect(door.requests).toHaveLength(METERS / 50 + 2);
  expect(door.requests.filter((r) => r.outcome === 'killed-after')).toHaveLength(1);
  expect(door.requests.filter((r) => r.outcome === 'killed-before')).toHaveLength(1);
  expect(Math.max(...door.requests.map((r) => r.size))).toBeLessThanOrEqual(MAX_ITEMS);
  expect(door.duplicatesAnswered).toBe(50);

  // And the handset agrees: every row settled, every reading's own state says so.
  expect(count(db, `SELECT COUNT(*) AS n FROM outbox WHERE state IN ('accepted','duplicate')`)).toBe(METERS);
  expect(count(db, `SELECT COUNT(*) AS n FROM outbox WHERE state = 'duplicate'`)).toBe(50);
  expect(count(db, `SELECT COUNT(*) AS n FROM route_read WHERE state IN ('accepted','duplicate')`)).toBe(METERS);
});
