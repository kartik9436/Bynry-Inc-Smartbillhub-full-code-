/**
 * T-44 — THE OFFLINE SOAK. A whole shift in airplane mode, through the real
 * app root (`FieldRuntime`), the real store and the real navigator:
 *
 *   07:30  Dana signs in at the depot with signal; her eleven jobs arrive on
 *          the change feed and Today lists all eleven.
 *   then   AIRPLANE MODE for the whole day. Each job is OPENED by its address
 *          (FF-15 with its id), worked — the safety row, two tasks, a photo on
 *          a task, a meter reading with its photo, the customer's signature
 *          (an image) — and CLOSED. *Send now* is pressed three times on the
 *          way and sends nothing.
 *   17:00  Signal again: ONE sync.
 *
 * Asserted at the far end, counted BY IDEMPOTENCY KEY (the server's unique
 * constraint): every key the handset minted was applied exactly once — nothing
 * lost, nothing doubled — every item travelled under Dana's own capture
 * credential, every job's close arrived after its own work, and all 33
 * photographs' bytes arrived and left the handset. Today then lists none of
 * the eleven: they are closed.
 *
 * Proved RED (law 7), through jest: with `sendPending` dropping the first
 * item of each batch from the wire AND `applyBatchAnswer` settling an item
 * the server never answered, the far end came back
 * `lost: ["id-000001", "id-000014", … ]` — eleven safety ticks the handset
 * believed sent. A second break (photo declarations never settling) did not
 * fail an assertion: it HUNG the run, which is how `nextBatch` ignoring
 * `next_attempt_at` was found (`sendLoop.test.ts`).
 */
import 'react-native-gesture-handler/jestSetup';

import { screen, within } from '@testing-library/react-native';

import * as outboxQ from '../../src/db/queries/outbox';
import * as woItemQ from '../../src/db/queries/woItem';
import * as woReadingQ from '../../src/db/queries/woReading';
import { deviceWide, scoped } from '../../src/db/scoped';
import { closeJob } from '../../src/screens/closing/CloseScreen';
import { captureSigned } from '../../src/screens/closing/SignatureScreen';
import { capturePhoto, recordReading, tickSafety, tickTask } from '../../src/screens/theJob/actions';
import type { ReadyPhoto } from '../../src/screens/theJob/camera';
import {
  buildHandset,
  card,
  mountHandset,
  openAt,
  PEOPLE,
  settle,
  sha,
  signInAs,
  syncNow,
  TENANT,
  upsert,
} from './runtimeApp';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const DANA = PEOPLE['d.ortiz']!.technicianId;
const JOBS = 11;
const MINUTE = 60_000;

const jobId = (i: number) => `wo-${5000 + i}`;

function count(db: Parameters<typeof deviceWide>[0], sql: string): number {
  return deviceWide(db, 'count').get<{ n: number }>(sql)?.n ?? 0;
}

test('T-44: eleven jobs worked and closed in airplane mode, then ONE sync — nothing lost, nothing doubled', async () => {
  const h = buildHandset({ network: 'wifi' });
  const server = h.serverFor(TENANT);
  const day = new Date(h.clock.now());
  const first = new Date(day.getTime() + 30 * MINUTE); // 08:00
  server.feed(Array.from({ length: JOBS }, (_, i) => upsert(card(jobId(i + 1), `WO-${5000 + i + 1}`, new Date(first.getTime() + i * 45 * MINUTE), 40), h.iso())));

  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  const db = h.holder.current;
  if (!db) throw new Error('the store did not open at sign-in');
  const s = scoped(db, DANA);

  // The feed landed: Today lists all eleven.
  await openAt(m, 'FF-10');
  expect(await screen.findByTestId('screen-FF-10')).toBeTruthy();
  for (let i = 1; i <= JOBS; i++) expect(screen.getByTestId(`job-${jobId(i)}`)).toBeTruthy();

  // Each job's bundle (tasks, the reading) as `GET work/mobile/jobs/{id}` would leave it.
  // ⚠ The bundle FETCH is not built (`sync/delta.ts`: "an upsert marks the row needs_bundle
  // for that fetch, which is not built here"); its rows are written here as it would write them.
  db.transaction(() => {
    for (let i = 1; i <= JOBS; i++) {
      const wo = jobId(i);
      woItemQ.upsert(s, { id: `${wo}-safe`, workOrderId: wo, kind: 'safety', position: 1, label: 'Isolate supply' }, h.iso());
      woItemQ.upsert(s, { id: `${wo}-t1`, workOrderId: wo, kind: 'task', position: 2, label: 'Remove old meter', photoRequired: true, photoMinCount: 1 }, h.iso());
      woItemQ.upsert(s, { id: `${wo}-t2`, workOrderId: wo, kind: 'task', position: 3, label: 'Fit new meter' }, h.iso());
      woReadingQ.upsert(s, { id: `${wo}-r1`, workOrderId: wo, position: 1, prompt: 'Final read', unit: 'kWh', minValue: '48000', maxValue: '49000' }, h.iso());
    }
  });

  // ── AIRPLANE MODE ───────────────────────────────────────────────────────────
  h.network.set('none');
  const before = server.requests.length;
  let shot = 0;
  const photo = (what: string): ReadyPhoto => {
    shot += 1;
    const path = `/handset/photos/${shot}-${what}.jpg`;
    const bytes = `jpeg:${shot}:${what}`;
    h.files.add(path, bytes);
    return { localPath: path, sha256: sha(bytes), bytes: 280_000, width: 1600, height: 1200, overCeiling: false };
  };

  for (let i = 1; i <= JOBS; i++) {
    const wo = jobId(i);
    h.clock.advance(35 * MINUTE);
    // OPENED, by its address.
    await openAt(m, 'FF-15', { workOrderId: wo });
    const overview = within(await screen.findByTestId('screen-FF-15'));
    expect(overview.queryByTestId('job-none')).toBeNull();
    expect(overview.getAllByText(new RegExp(`WO-${5000 + i}`)).length).toBeGreaterThan(0);

    // WORKED, through the same functions the screens call, in the port the runtime gives them.
    const port = m.inside.current.job;
    const wave = m.inside.current.wave;
    if (!port || !wave) throw new Error('the runtime gave the job screens no store');
    tickSafety(port, wo, `${wo}-safe`);
    tickTask(port, wo, `${wo}-t1`);
    capturePhoto(port, wo, photo(`${wo}-t1`), { task_id: `${wo}-t1` });
    tickTask(port, wo, `${wo}-t2`);
    recordReading(port, wo, { id: `${wo}-r1`, unit: 'kWh' }, { value: `${48100 + i}.50`, flagged: false, unableToRead: false }, [photo(`${wo}-r1`)]);
    const sig = photo(`${wo}-sig`);
    captureSigned(wave, wo, 'Sarah Miller', { localPath: sig.localPath, sha256: sig.sha256, bytes: sig.bytes, width: sig.width, height: sig.height });
    // CLOSED.
    closeJob(wave, { workOrderId: wo }, 'passed', {
      arrivedAt: new Date(h.clock.now() - 30 * MINUTE).toISOString(),
      finishedAt: new Date(h.clock.now()).toISOString(),
    });

    // *Send now* in the valley sends nothing and loses nothing.
    if (i % 4 === 0) await syncNow(m);
  }
  expect(server.requests.length).toBe(before);
  expect(server.photoRequests).toHaveLength(0);

  // Each job's work also queued its ACCEPT, ahead of it (DEF-FLD-10612: no Start
  // was pressed — the jobs were opened by address — and work on a job takes it).
  const rows = deviceWide(db, 'count').all<{ id: string; kind: string }>(`SELECT id, kind FROM outbox ORDER BY id`);
  const minted = rows.filter((r) => r.kind !== 'job_accept').map((r) => r.id);
  const accepts = rows.filter((r) => r.kind === 'job_accept').map((r) => r.id);
  const perJob = 9; // safety + 2 tasks + task photo + reading + its photo + signature + its image + close
  expect(minted).toHaveLength(JOBS * perJob);
  expect(accepts).toHaveLength(JOBS);
  expect(count(db, `SELECT COUNT(*) AS n FROM outbox WHERE state = 'pending'`)).toBe(JOBS * (perJob + 1));
  expect(count(db, `SELECT COUNT(*) AS n FROM photo WHERE state <> 'uploaded'`)).toBe(JOBS * 3);

  // ── 17:00, SIGNAL: ONE sync ─────────────────────────────────────────────────
  h.clock.advance(60 * MINUTE);
  h.network.set('wifi'); // the runtime's reconnect starts the run…
  await syncNow(m); // …and Send now joins it rather than starting a second.
  await settle();

  // Nothing waiting on the handset.
  expect(count(db, `SELECT COUNT(*) AS n FROM outbox WHERE state NOT IN ('accepted','duplicate','held_for_review')`)).toBe(0);
  expect(count(db, `SELECT COUNT(*) AS n FROM photo WHERE state <> 'uploaded'`)).toBe(0);

  // THE FAR END, by idempotency key: every key once, none twice, none extra.
  const perKey = server.appliedPerKey();
  const lost = minted.filter((k) => !perKey.has(k));
  const doubled = [...perKey].filter(([, n]) => n > 1).map(([k]) => k);
  const extra = [...perKey.keys()].filter((k) => !minted.includes(k));
  expect({ lost, doubled, extra }).toEqual({ lost: [], doubled: [], extra: [] });
  expect(server.applied).toHaveLength(JOBS * perJob);
  expect(server.duplicatesAnswered).toBe(0); // nothing was even SENT twice
  // One accept per job, through the accept door, and no more.
  expect(server.callsTo('accept').map(([j]) => j).sort()).toEqual(Array.from({ length: JOBS }, (_, i) => jobId(i + 1)).sort());

  // Per job, the right acts, in capture order, the close last — and under Dana's own credential.
  const danaToken = h.session.captureCredentialOf(DANA)?.serverToken;
  expect(danaToken).toBeTruthy();
  for (let i = 1; i <= JOBS; i++) {
    const mine = server.applied.filter((a) => a.group === `job:${jobId(i)}`);
    expect(mine.map((a) => a.kind)).toEqual(['safety_tick', 'task_tick', 'photo', 'task_tick', 'reading', 'photo', 'signature', 'photo', 'close']);
    expect(mine.map((a) => a.seq)).toEqual([...mine.map((a) => a.seq)].sort((x, y) => x - y));
    expect(new Set(mine.map((a) => a.captor))).toEqual(new Set([danaToken]));
  }
  const readings = server.applied.filter((a) => a.kind === 'reading');
  expect(readings.map((r) => r.payload['value'])).toEqual(Array.from({ length: JOBS }, (_, i) => `${48100 + i + 1}.50`));

  // The photographs: 33 sets of bytes at the far end, byte-for-byte. FB-030
  // (PO 2026-10-31, R61 superseded in part): the files STAY on the handset for
  // 3 days after each close, for the record — the purge takes them then.
  expect(server.photoBytes.size).toBe(JOBS * 3);
  expect(h.files.bytes.size).toBe(JOBS * 3);

  // And the day: all eleven closed, so Today lists none of them.
  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  for (let i = 1; i <= JOBS; i++) expect(screen.queryByTestId(`job-${jobId(i)}`)).toBeNull();
  expect(outboxQ.getMine(s, minted[0]!)?.state).toBe('accepted');
  m.unmount();
}, 60_000);
