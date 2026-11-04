/**
 * @jest-environment node
 *
 * Every act on the job screens goes through the outbox, and the act, its
 * local change, its photo rows and its key land TOGETHER or not at all
 * (Mobile data §1). Run against a real SQLite store.
 *
 * Proved red (law 7): with `recordReading`'s photographs moved OUT of the
 * capture (a second `capturePhoto` after it), *"a reading and its photograph
 * land in one transaction"* failed — the refused reading left a photo row and
 * its declaration behind (`photo` count 4, expected 3).
 */
import * as documentQ from '../../../src/db/queries/document';
import * as jobQ from '../../../src/db/queries/jobScreens';
import * as outboxQ from '../../../src/db/queries/outbox';
import * as woItemQ from '../../../src/db/queries/woItem';
import * as woReadingQ from '../../../src/db/queries/woReading';
import { scoped } from '../../../src/db/scoped';
import {
  addMaterial,
  addPaper,
  addReading,
  addStep,
  correctClock,
  handBack,
  recordReading,
  setMaterialUsed,
  startClock,
  stopClock,
  tickSafety,
  tickTask,
} from '../../../src/screens/theJob/actions';
import { loadJob, photoReadiness, REQUIRED_PHOTO_BLOCKS_CLOSE } from '../../../src/screens/theJob/jobModel';
import { DANA, local, MARCO, photo, seedWO4822, WO } from './fixture';

function setup() {
  const f = seedWO4822();
  const s = scoped(f.db, DANA);
  const outbox = () => outboxQ.listMine(s, { limit: 500 });
  return { f, s, port: f.port(), outbox };
}

test('FF-15 counts every section from the rows (US-FLD-026 TC-1, TC-4)', () => {
  const { port } = setup();
  const v = loadJob(port, WO);
  if (!v) throw new Error('no job');
  expect({ done: v.safety.done, total: v.safety.total }).toEqual({ done: 0, total: 4 });
  expect({ done: v.tasks.done, total: v.tasks.total, needPhoto: v.tasks.needPhoto }).toEqual({ done: 3, total: 8, needPhoto: 2 });
  expect({ ok: v.materials.satisfied, of: v.materials.planned.length, notOnVan: v.materials.notOnVan, added: v.materials.added.length }).toEqual({ ok: 1, of: 2, notOnVan: 1, added: 1 });
  expect({ answered: v.checklist.answered, total: v.checklist.total }).toEqual({ answered: 3, total: 5 });
  expect({ taken: v.readings.taken, total: v.readings.total, needPhoto: v.readings.needPhoto }).toEqual({ taken: 1, total: 3, needPhoto: 2 });
  expect(v.help).toBe(3);
  expect(v.subMeters).toBe(2);
  // step 4 is where the work is
  expect(v.tasks.currentIndex + 1).toBe(4);
  // the added step is counted in Tasks and marked as a variance (R7)
  expect(v.tasks.items.filter((x) => x.row.added_in_field)).toHaveLength(1);
  // R9: travel and labour apart; labour per person (R8)
  expect(v.travel.minutes).toBe(14);
  expect(v.labour.running).toBe(true);
  expect(v.crew.people.sort()).toEqual([DANA, MARCO].sort());
});

test('FF-15 Help and SOPs counts every help kind, the job’s and its template’s, each once (DEF-FLD-10581)', () => {
  const { f, port } = setup();
  const at = local(7, 5).toISOString();
  const help = (id: string, kind: string, label: string, ref: string) =>
    documentQ.upsertHelp(f.db, { id, workOrderId: WO, kind, label, ref, url: null }, at);
  help('h-phone', 'phone', 'Supervisor', '(512) 555-0142');
  help('h-link', 'link', 'Meter swap video', 'https://video.example.test/meter-swap');
  // The template's own copy of the same number: one entry, not two.
  f.db.ref.run(
    `INSERT INTO document (id, owner_kind, owner_id, title, kind, source, ref, bytes, updated_at)
     VALUES ('tpl-phone', 'template', 'tpl-mx', 'Supervisor', 'phone', 'server', '(512) 555-0142', 0, :at)`,
    { at },
  );
  expect(loadJob(port, WO)!.help).toBe(5);
});

test('R3: a safety tick is one captured item and the row is ticked, together', () => {
  const { port, s, outbox } = setup();
  const key = tickSafety(port, WO, 'safety-1');
  const row = outbox().find((r) => r.id === key);
  expect(row?.kind).toBe('safety_tick');
  expect(JSON.parse(row?.payload ?? '{}')).toEqual({ safety_id: 'safety-1' });
  expect(woItemQ.listForOrder(s, WO, 'safety').find((i) => i.id === 'safety-1')?.state).toBe('ticked');
});

test('R110: a step short of its photographs is still marked done — short warns, never blocks', () => {
  const { port, s } = setup();
  tickTask(port, WO, 'task-4');
  expect(woItemQ.listForOrder(s, WO, 'task').find((i) => i.id === 'task-4')?.state).toBe('done');
});

test('a reading and its photograph land in one transaction — or neither does', () => {
  const { port, s, f } = setup();
  const photosBefore = jobQ.photosForOrder(s, WO).length;
  const outboxBefore = outboxQ.listMine(s, { limit: 500 }).length;
  // a reading whose unit does not match the row is refused (hard rule 3) — and takes its photo with it
  expect(() =>
    recordReading(port, WO, { id: 'r-master', unit: 'kWh' }, { value: '48200', flagged: false, unableToRead: false }, [photo(9)]),
  ).toThrow();
  expect(jobQ.photosForOrder(s, WO)).toHaveLength(photosBefore);
  expect(outboxQ.listMine(s, { limit: 500 })).toHaveLength(outboxBefore);
  // the same with the right unit: the reading, the photo declaration and the photo row
  f.clock.set(11, 2);
  const key = recordReading(port, WO, { id: 'r-master', unit: 'gal' }, { value: '58000', flagged: true, unableToRead: false }, [photo(9)]);
  const rows = outboxQ.listMine(s, { limit: 500 });
  expect(rows).toHaveLength(outboxBefore + 2);
  const reading = rows.find((r) => r.id === key);
  expect(JSON.parse(reading?.payload ?? '{}')).toMatchObject({ reading_id: 'r-master', value: '58000', unit: 'gal', flagged: true });
  const added = jobQ.photosForOrder(s, WO).filter((p) => p.reading_id === 'r-master');
  expect(added).toHaveLength(1);
  expect(added[0]?.local_path).toBe('file:///photos/p9.jpg'); // a FILE path, never bytes (R52)
  const r = woReadingQ.listForOrder(s, WO).find((x) => x.id === 'r-master');
  expect({ value: r?.value, unit: r?.unit, flagged: r?.flagged }).toEqual({ value: '58000', unit: 'gal', flagged: 1 });
});

test('R13: unable to read is an answer at the reading', () => {
  const { port, s } = setup();
  recordReading(port, WO, { id: 'r-sub-b', unit: 'gal' }, { value: null, flagged: false, unableToRead: true });
  const r = woReadingQ.listForOrder(s, WO).find((x) => x.id === 'r-sub-b');
  expect({ value: r?.value, unable: r?.unable_to_read }).toEqual({ value: null, unable: 1 });
});

test('R7: an added step needs what AND why, and carries both as a variance', () => {
  const { port, s, outbox } = setup();
  expect(() => addStep(port, WO, { label: 'Replace valve', reason: ' ', minutes: 15, photoRequired: false, position: 9 })).toThrow(/R7/);
  const key = addStep(port, WO, { label: 'Replace valve', reason: 'Seized open', minutes: 15, photoRequired: true, position: 9 });
  const item = woItemQ.listForOrder(s, WO, 'task').find((i) => i.label === 'Replace valve');
  expect({ added: item?.added_in_field, reason: item?.reason, photo: item?.photo_required }).toEqual({ added: 1, reason: 'Seized open', photo: 1 });
  expect(JSON.parse(outbox().find((r) => r.id === key)?.payload ?? '{}')).toMatchObject({ added_in_field: true, reason: 'Seized open' });
});

test('R7 / requirement 72: an added reading needs a reason, has no range and is never flagged', () => {
  const { port, s } = setup();
  expect(() => addReading(port, WO, { assetId: 'asset-mtr0903', assetLabel: 'MTR-0903', reason: '', value: '124', unit: 'gal', position: 4, prompt: 'MTR-0903' })).toThrow();
  addReading(port, WO, { assetId: 'asset-mtr0903', assetLabel: 'MTR-0903', reason: 'notListed', value: '00124', unit: 'gal', position: 4, prompt: 'MTR-0903' });
  const r = woReadingQ.listForOrder(s, WO).find((x) => x.prompt === 'MTR-0903');
  expect({ value: r?.value, unit: r?.unit, flagged: r?.flagged, min: r?.min_value }).toEqual({ value: '00124', unit: 'gal', flagged: 0, min: null });
});

test('parts used are captured against the step; an added part needs its reason (R7); money is never written (R16)', () => {
  const { port, s, outbox } = setup();
  const v = loadJob(port, WO);
  const meter = v?.materials.items.find((m) => m.row.id === 'mat-meter');
  if (!meter) throw new Error('no meter');
  const key = setMaterialUsed(port, WO, { id: meter.row.id, detail: meter.detail, state: meter.row.state }, 1, 'task-4');
  expect(JSON.parse(outbox().find((r) => r.id === key)?.payload ?? '{}')).toEqual({ material_id: 'mat-meter', used_qty: 1, step_id: 'task-4' });
  expect(() => addMaterial(port, WO, { label: 'Gasket', code: '', qty: 1, reason: '', position: 9 })).toThrow(/R7/);
  addMaterial(port, WO, { label: 'Gasket', code: 'GSK-1', qty: 2, reason: 'Old one perished', position: 9 });
  const after = loadJob(port, WO);
  expect(after?.materials.added).toHaveLength(2);
  for (const row of outbox()) expect(row.payload).not.toMatch(/unit_cost|price|amount/);
  void s;
});

test('R106 / R107: a hand-back carries the reason; an emergency is refused', () => {
  const { port, outbox } = setup();
  expect(() => handBack(port, WO, { reason: 'parts', note: '', emergency: true })).toThrow(/R107/);
  const key = handBack(port, WO, { reason: 'parts', note: 'Need a 3/4" meter', emergency: false });
  const row = outbox().find((r) => r.id === key);
  expect(row?.kind).toBe('hand_back');
  // Its own door since INTEGRATE-2 (`POST jobs/{id}/hand-back`), in the job's group so capture order holds.
  expect(row?.channel).toBe('job');
  expect(JSON.parse(row?.payload ?? '{}')).toEqual({ reason: 'parts', note: 'Need a 3/4" meter' });
});

test('R9: starting labour stops travel; a pause stops labour; a correction is stamped (R10)', () => {
  const { port, s, f } = setup();
  f.clock.set(11, 0);
  stopClock(port, WO, 'ct-labour');
  let v = loadJob(port, WO);
  expect(v?.labour.running).toBe(false);
  expect(v?.labour.minutes).toBe(134); // 08:46 → 11:00, the paused total (US-FLD-029 TC-4)
  f.clock.set(11, 10);
  startClock(port, WO, 'travel');
  f.clock.set(11, 20);
  startClock(port, WO, 'labour');
  v = loadJob(port, WO);
  expect(v?.travel.running).toBe(false);
  expect(v?.labour.running).toBe(true);
  // correct travel's start from 08:00 to 08:02 (TC-3)
  const seg = v?.travel.segments[0];
  if (!seg) throw new Error('no travel');
  correctClock(port, WO, seg, { startedAt: local(8, 2).toISOString(), endedAt: seg.ended_at });
  v = loadJob(port, WO);
  expect(v?.travel.firstStart).toBe(local(8, 2).toISOString());
  const stamped = s.all<{ status: string; author: string }>(
    `SELECT status, author FROM activity WHERE technician_id = :technician_id AND status = 'time_corrected'`,
  );
  expect(stamped).toEqual([{ status: 'time_corrected', author: DANA }]);
});

test('R108: each paper records where it came from', () => {
  const { port, f } = setup();
  addPaper(port, WO, 'asset-mtr0903', { source: 'typed', title: 'Factory seal number', text: 'NT-88-412977' });
  addPaper(port, WO, 'asset-mtr0903', { source: 'camera', title: 'Serial plate', photo: photo(7) });
  addPaper(port, WO, 'asset-mtr0903', { source: 'file', title: 'Plumbing permit', localPath: 'file:///docs/permit.pdf', bytes: 410 * 1024, kind: 'application/pdf' });
  const docs = f.db.ref.all<{ title: string; source: string }>(
    `SELECT title, source FROM document WHERE owner_kind = 'asset' AND owner_id = 'asset-mtr0903' ORDER BY title`,
  );
  expect(docs).toEqual([
    { title: 'Factory seal number', source: 'typed' },
    { title: 'Plumbing permit', source: 'file' },
    { title: 'Serial plate', source: 'camera' },
  ]);
});

test('PO 2026-10-21: a required photograph never taken warns, never blocks; so does one short of the count', () => {
  const { port } = setup();
  expect(REQUIRED_PHOTO_BLOCKS_CLOSE).toBe(false);
  const v = loadJob(port, WO);
  if (!v) throw new Error('no job');
  const { blocking, short } = photoReadiness(v);
  // task-8 and two readings ask for a photograph and have none; task-4 has 1 of 3 — all four warn
  expect(blocking).toEqual([]);
  expect(short.sort()).toEqual(['r-master', 'r-sub-b', 'task-4', 'task-8']);
});

test('another technician on the same handset sees none of this job (R132/R133)', () => {
  const { f } = setup();
  const marcoPort = { ...f.port(), captor: () => ({ technicianId: MARCO, capturedBy: MARCO }) };
  expect(loadJob(marcoPort, WO)).toBeNull();
});
