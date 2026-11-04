/**
 * T-49 — RETENTION, through the real purge as the app runs it: on APP START
 * (`FieldRuntime` opening the tenant store), never on a timer (R63), with a
 * fake clock carried ninety days on.
 *
 *   A  a photograph whose bytes the server CONFIRMED (`staged`). FB-030 (PO
 *      2026-10-31): its file is KEPT — it goes 3 days after its job closes,
 *      and this job stays open — and its settled outbox row goes at 7 days.
 *   B  a photograph merely SENT: the declaration was accepted and the bytes
 *      went up, but the server answered `pending`, not durable. Its file stays
 *      on the handset — through the sync and through the ninety-day purge.
 *   C  a reading captured with no signal and never sent. Ninety days on, after
 *      the app has started again and purged, it is still there, still pending
 *      (R60: "Nothing unsent is ever purged — at any age").
 *
 * A's rows going is what proves the purge RAN — without it, "C is still there"
 * would pass with no purge at all (law 7: what would make this pass wrongly?).
 *
 * Proved RED twice (lane report): with the runtime's purge-on-start removed,
 * A's settled row was still on the handset at day 90; with the purge's
 * "settled only" clause widened to every state, C was gone.
 */
import 'react-native-gesture-handler/jestSetup';

import * as outboxQ from '../../src/db/queries/outbox';
import * as workOrderQ from '../../src/db/queries/workOrder';
import * as woItemQ from '../../src/db/queries/woItem';
import * as woReadingQ from '../../src/db/queries/woReading';
import { scoped } from '../../src/db/scoped';
import { capturePhoto, recordReading } from '../../src/screens/theJob/actions';
import type { ReadyPhoto } from '../../src/screens/theJob/camera';
import { buildHandset, mountHandset, PEOPLE, settle, sha, signInAs, syncNow, TENANT } from './runtimeApp';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const DANA = PEOPLE['d.ortiz']!.technicianId;
const DAY = 24 * 60 * 60 * 1000;

test('T-49: a confirmed photo’s file goes, a merely-sent one stays, and unsent work is still there at ninety days', async () => {
  const h = buildHandset({ network: 'wifi' });
  const server = h.serverFor(TENANT);
  const shot = (name: string): ReadyPhoto => {
    h.files.add(`/p/${name}.jpg`, `jpeg-${name}`);
    return { localPath: `/p/${name}.jpg`, sha256: sha(`jpeg-${name}`), bytes: 10, width: 1600, height: 1200, overCeiling: false };
  };

  // ── Day 0 ──────────────────────────────────────────────────────────────────
  let m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  const db = h.holder.current!;
  const s = scoped(db, DANA);
  workOrderQ.upsertFromServer(s, {
    id: 'wo-8001', number: 'WO-8001', type: null, state: null, dispatchState: 'scheduled', priorityCode: null, priorityRank: null,
    premiseId: null, windowStart: null, windowEnd: null, dueAt: null, estMinutes: null, accessNotes: null, hazards: null,
    gateCode: null, extra: null, serverUpdatedAt: null,
  }, h.iso());
  woItemQ.upsert(s, { id: 't1', workOrderId: 'wo-8001', kind: 'task', position: 1, label: 'Seal' }, h.iso());
  woItemQ.upsert(s, { id: 't2', workOrderId: 'wo-8001', kind: 'task', position: 2, label: 'Tag' }, h.iso());
  woReadingQ.upsert(s, { id: 'r1', workOrderId: 'wo-8001', position: 1, prompt: 'Read', unit: 'kWh' }, h.iso());

  // A — confirmed.
  const a = capturePhoto(m.inside.current.job!, 'wo-8001', shot('a'), { task_id: 't1' });
  await syncNow(m);
  const aRow = s.get<{ id: string; state: string; local_path: string }>(`SELECT id, state, local_path FROM photo WHERE technician_id = :technician_id AND declare_id = :k`, { k: a });
  expect(aRow?.state).toBe('uploaded');
  // FB-030 (PO 2026-10-31, R61 superseded in part): KEPT on confirmed receipt —
  // the purge takes the file 3 days after the job closes, and this job is open.
  expect(h.files.bytes.has('/p/a.jpg')).toBe(true);

  // B — merely sent: the server takes the bytes and answers "pending", not durable.
  server.answerPhotoPending = true;
  const b = capturePhoto(m.inside.current.job!, 'wo-8001', shot('b'), { task_id: 't2' });
  await syncNow(m);
  expect(outboxQ.getMine(s, b)?.state).toBe('accepted'); // the declaration landed
  expect(server.photoRequests.filter((id) => id !== aRow?.id)).toHaveLength(1); // the bytes were SENT
  const bRow = () => s.get<{ state: string }>(`SELECT state FROM photo WHERE technician_id = :technician_id AND declare_id = :k`, { k: b });
  expect(bRow()?.state).not.toBe('uploaded');
  expect(h.files.bytes.has('/p/b.jpg')).toBe(true); // PRESENT while merely sent

  // C — no signal, never sent.
  h.network.set('none');
  const c = recordReading(m.inside.current.job!, 'wo-8001', { id: 'r1', unit: 'kWh' }, { value: '52410.00', flagged: false, unableToRead: false });
  expect(outboxQ.getMine(s, c)?.state).toBe('pending');
  m.unmount(); // the app is closed

  // ── Day 90: the app starts again, still no signal, and Dana signs in ───────
  h.clock.advance(90 * DAY);
  m = mountHandset(h);
  h.api.online = false;
  await signInAs(h, 'd.ortiz');
  await settle();
  const s90 = scoped(h.holder.current!, DANA);

  // The purge RAN on this start: A's settled outbox row is gone. FB-030: A's
  // photo row and file stay with their job, which is still open on the phone.
  expect(outboxQ.getMine(s90, a)).toBeUndefined();
  expect(s90.get(`SELECT id FROM photo WHERE technician_id = :technician_id AND declare_id = :k`, { k: a })).toBeDefined();
  expect(h.files.bytes.has('/p/a.jpg')).toBe(true);
  // B: its file is still on the handset, and so is the row that will send it.
  expect(h.files.bytes.has('/p/b.jpg')).toBe(true);
  expect(h.files.deleted).not.toContain('/p/b.jpg');
  expect(s90.get<{ state: string }>(`SELECT state FROM photo WHERE technician_id = :technician_id AND declare_id = :k`, { k: b })?.state).not.toBe('uploaded');
  // C: ninety days old, unsent, untouched.
  expect(outboxQ.getMine(s90, c)).toMatchObject({ state: 'pending', kind: 'reading' });
  m.unmount();
}, 60_000);
