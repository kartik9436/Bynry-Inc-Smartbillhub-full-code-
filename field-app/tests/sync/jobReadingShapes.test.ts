/**
 * @jest-environment node
 *
 * DEF-WRK-10601 — the SHAPE LOCK on a job reading. The phone sends three
 * shapes of `reading` item (a figure, words, *Unable to read*), and the server
 * refused one of them while every test on both sides was green: the phone's
 * tests ran against a fake server that accepted everything, and the server's
 * tests only ever sent numbers through the sync door.
 *
 * `support/jobReadingShapes.json` holds the three payloads exactly. This file
 * asserts the phone's own capture functions still PRODUCE exactly those, and
 * `06-backend/tests/test_def_wrk_10601_job_reading_shapes.py` POSTs exactly
 * those through `POST /work/mobile/jobs/{id}/sync`. A change on either side
 * without the other turns one of them red.
 */
import * as outboxQ from '../../src/db/queries/outbox';
import * as woReadingQ from '../../src/db/queries/woReading';
import { scoped } from '../../src/db/scoped';
import { recordReading, recordTextReading } from '../../src/screens/theJob/actions';
import { DANA, seedWO4822, WO } from '../screens/theJob/fixture';
import shapes from './support/jobReadingShapes.json';

function setup() {
  const f = seedWO4822();
  const s = scoped(f.db, DANA);
  woReadingQ.upsert(s, { id: 'r-serial', workOrderId: WO, position: 4, prompt: 'New meter serial', unit: '', kind: 'text' }, f.clock.now().toISOString());
  return { s, port: f.port() };
}

/** The sent payload with its two specifics put back as the file's placeholders. */
function asShape(payload: Record<string, unknown>, readingId: string, unit: string): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(payload)) {
    if (k === 'reading_id' && v === readingId) out[k] = '{reading_id}';
    else if (k === 'unit' && v === unit) out[k] = '{unit}';
    else out[k] = v;
  }
  return out;
}

function sent(s: ReturnType<typeof scoped>, key: string): Record<string, unknown> {
  const row = outboxQ.listMine(s, { limit: 500 }).find((r) => r.id === key);
  expect(row?.kind).toBe('reading');
  return JSON.parse(row?.payload ?? '{}');
}

test('the shape file holds the three shapes and nothing else', () => {
  expect(Object.keys(shapes).sort()).toEqual(['number', 'text', 'unable']);
});

test('a figure is sent exactly as the server is tested to accept it', () => {
  const { s, port } = setup();
  const key = recordReading(port, WO, { id: 'r-sub-b', unit: 'gal' }, { value: '1204', flagged: false, unableToRead: false });
  expect(asShape(sent(s, key), 'r-sub-b', 'gal')).toEqual(shapes.number);
});

test('words on a text reading are sent exactly as the server is tested to accept them', () => {
  const { s, port } = setup();
  const key = recordTextReading(port, WO, 'r-serial', '  W-5000-N ');
  expect(asShape(sent(s, key), 'r-serial', '')).toEqual(shapes.text);
});

test('Unable to read is sent exactly as the server is tested to accept it', () => {
  const { s, port } = setup();
  // DEF-MET-10609 — one reason CODE from the shared can't-read list, plus the note.
  const key = recordReading(port, WO, { id: 'r-sub-b', unit: 'gal' }, {
    value: null,
    flagged: false,
    unableToRead: true,
    unableReason: 'dog',
    note: ' Dog at the gate ',
  });
  expect(asShape(sent(s, key), 'r-sub-b', 'gal')).toEqual(shapes.unable);
});
