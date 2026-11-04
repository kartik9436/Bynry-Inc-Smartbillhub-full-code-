/**
 * T-48 — THE HANDOVER (E2E-21, Security §3, R64, BR-WRK-059/060), on one
 * handset through the real app root:
 *
 *   morning  Marco has used this handset before (he is known on it).
 *            Dana signs in with signal; her job is on the phone.
 *   valley   No signal. Dana works her job — a safety row, a task, a reading
 *            with its photograph — and SIGNS OUT with all of it unsent.
 *            Marco signs in (offline, against the verifier this handset
 *            holds), works HIS job, sees Dana's work as hers and not his,
 *            and signs out.
 *   depot    Signal. R. Patel signs in — a third person, the courier.
 *
 * Dana's work survived both sign-outs and Marco's whole session untouched,
 * and it reached the server under DANA's capture credential (the captor), not
 * Marco's and not Patel's (the courier); Marco's under his. Nothing of
 * Patel's travels at all — he captured nothing.
 *
 * Proved RED (law 7): with the runtime handing the sync engine the SIGNED-IN
 * technician's token for every group (`tokenFor: () => …(technicianId)`),
 * every item went up under Patel's credential — quoted in the lane report.
 */
import 'react-native-gesture-handler/jestSetup';

import { waitingToSend } from '../../src/db/queries/day';
import * as outboxQ from '../../src/db/queries/outbox';
import * as workOrderQ from '../../src/db/queries/workOrder';
import * as woItemQ from '../../src/db/queries/woItem';
import * as woReadingQ from '../../src/db/queries/woReading';
import { deviceWide, scoped } from '../../src/db/scoped';
import { recordReading, tickSafety, tickTask } from '../../src/screens/theJob/actions';
import { buildHandset, mountHandset, PEOPLE, settle, sha, signInAs, signOut, syncNow, TENANT } from './runtimeApp';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const DANA = PEOPLE['d.ortiz']!.technicianId;
const MARCO = PEOPLE['m.chen']!.technicianId;
const PATEL = PEOPLE['r.patel']!.technicianId;

const job = (id: string): workOrderQ.WorkOrderFromServer => ({
  id, number: id.toUpperCase(), type: 'Meter exchange', state: null, dispatchState: 'scheduled', priorityCode: 'P3',
  priorityRank: null, premiseId: null, windowStart: null, windowEnd: null, dueAt: null, estMinutes: 30,
  accessNotes: null, hazards: null, gateCode: null, extra: null, serverUpdatedAt: null,
});

function seedJob(db: NonNullable<ReturnType<typeof buildHandset>['holder']['current']>, tech: string, wo: string, at: string) {
  const s = scoped(db, tech);
  workOrderQ.upsertFromServer(s, job(wo), at);
  woItemQ.upsert(s, { id: `${wo}-safe`, workOrderId: wo, kind: 'safety', position: 1, label: 'Isolate' }, at);
  woItemQ.upsert(s, { id: `${wo}-t1`, workOrderId: wo, kind: 'task', position: 2, label: 'Swap meter' }, at);
  woReadingQ.upsert(s, { id: `${wo}-r1`, workOrderId: wo, position: 1, prompt: 'Final read', unit: 'kWh' }, at);
}

test('T-48: Dana’s unsent work survives Marco signing in, working and signing out — and sends under Dana’s name', async () => {
  const h = buildHandset({ network: 'wifi' });
  const server = h.serverFor(TENANT);
  const m = mountHandset(h);

  // Morning: Marco is known on this handset; then Dana signs in with signal.
  await signInAs(h, 'm.chen');
  await signOut(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  const db = h.holder.current!;
  seedJob(db, DANA, 'wo-7001', h.iso());
  seedJob(db, MARCO, 'wo-7101', h.iso());
  const danaToken = h.session.captureCredentialOf(DANA)?.serverToken;
  const marcoToken = h.session.captureCredentialOf(MARCO)?.serverToken;
  expect(danaToken && marcoToken && danaToken !== marcoToken).toBe(true);

  // The valley. Dana works and signs out with everything unsent.
  h.network.set('none');
  h.api.online = false;
  const port = m.inside.current.job!;
  const dKeys = [
    tickSafety(port, 'wo-7001', 'wo-7001-safe'),
    tickTask(port, 'wo-7001', 'wo-7001-t1'),
  ];
  h.files.add('/p/dana-read.jpg', 'dana-jpeg');
  dKeys.push(
    recordReading(port, 'wo-7001', { id: 'wo-7001-r1', unit: 'kWh' }, { value: '52410.00', flagged: false, unableToRead: false }, [
      { localPath: '/p/dana-read.jpg', sha256: sha('dana-jpeg'), bytes: 9, width: 1600, height: 1200, overCeiling: false },
    ]),
  );
  const danaRows = () => deviceWide(h.holder.current ?? db, 'count').all<{ id: string; state: string; kind: string }>(
    `SELECT id, state, kind FROM outbox WHERE technician_id = :t ORDER BY seq`, { t: DANA },
  );
  const danaBefore = danaRows();
  // Three acts + the reading's photo declaration + the job's accept, which her
  // first tick queued ahead of them (DEF-FLD-10612: work on a job takes it).
  expect(danaBefore.map((r) => r.kind)).toEqual(['job_accept', 'safety_tick', 'task_tick', 'reading', 'photo']);
  const danaWork = danaBefore.filter((r) => r.kind !== 'job_accept');
  await signOut(h);
  expect(h.holder.current).toBeNull(); // the store is closed — and closing deletes nothing

  // Marco signs in on the same handset with no signal, and works his own job.
  await signInAs(h, 'm.chen');
  await settle();
  expect(h.holder.current?.tenant).toBe(TENANT);
  const summary = await h.session.unsentSummary();
  expect(summary.mine).toEqual({ items: 0, photos: 0 });
  // DEF-FLD-10363 (fixed): 3 items and 1 photo — the photo's DECLARATION is not
  // an item. The sign-out sheet and Home now count through ONE definition
  // (`outbox.countUnsent…`); before, this said 4 here and 3 on Home.
  // (4 since DEF-FLD-10612: her job's accept is an act waiting to send too.)
  expect(summary.others).toEqual([{ technicianId: DANA, displayName: PEOPLE['d.ortiz']!.name, items: 4, photos: 1 }]);
  const home = waitingToSend(scoped(h.holder.current!, DANA));
  expect({ items: home.items, photos: home.photos }).toEqual({ items: 4, photos: 1 });
  const mPort = m.inside.current.job!;
  const mKeys = [tickSafety(mPort, 'wo-7101', 'wo-7101-safe'), tickTask(mPort, 'wo-7101', 'wo-7101-t1')];
  // Marco cannot reach Dana's job through his own scope.
  expect(workOrderQ.getMine(scoped(h.holder.current!, MARCO), 'wo-7001')).toBeUndefined();
  await syncNow(m); // Send now, still no signal: nothing goes, nothing is lost
  await signOut(h);

  // Dana's work is exactly as she left it.
  expect(danaRows()).toEqual(danaBefore);
  expect(server.requests).toHaveLength(0);

  // The depot: signal, and R. Patel signs in.
  h.network.set('wifi');
  h.api.online = true;
  await signInAs(h, 'r.patel');
  await settle();
  await syncNow(m);

  // Every key once, each under its CAPTOR's credential.
  const byKey = new Map(server.applied.map((a) => [a.key, a]));
  for (const k of danaWork.map((r) => r.id)) expect(byKey.get(k)?.captor).toBe(danaToken);
  for (const k of mKeys) expect(byKey.get(k)?.captor).toBe(marcoToken);
  expect(server.applied).toHaveLength(danaWork.length + mKeys.length);
  // Each job's accept went through its own door under its captor's credential, never Patel's.
  const accepts = server.doorExtras.filter(([d]) => d === 'accept').map(([, x]) => (x as { captureToken?: string } | undefined)?.captureToken);
  expect(accepts.sort()).toEqual([danaToken, marcoToken].sort());
  const patelToken = h.session.captureCredentialOf(PATEL)?.serverToken;
  expect(server.applied.filter((a) => a.captor === patelToken)).toEqual([]);
  expect(dKeys.every((k) => byKey.has(k))).toBe(true);
  expect(outboxQ.getMine(scoped(h.holder.current!, DANA), dKeys[0]!)?.state).toBe('accepted');
  // Her photograph's bytes went too. FB-030 (PO 2026-10-31): the file stays
  // on the handset for her record until 3 days after the turn-in.
  expect([...server.photoBytes.values()]).toEqual(['dana-jpeg']);
  expect(h.files.bytes.has('/p/dana-read.jpg')).toBe(true);
  m.unmount();
}, 60_000);
