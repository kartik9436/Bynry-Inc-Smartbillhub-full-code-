/**
 * @jest-environment node
 *
 * R133, PO ruled 2026-10-21: "Every read of a scoped table goes through one
 * helper, and a test fails any statement that bypasses it … The test is the
 * deliverable, not the columns." This is that test, in two halves:
 *
 *  1. RUNTIME — the doors themselves refuse: `db.ref` refuses a scoped table,
 *     `scoped()` refuses a statement that does not filter on :technician_id.
 *  2. STATIC — it walks every source file and fails (a) SQL outside
 *     `src/db/queries/` and the migrations, (b) a scoped-runner query whose SQL
 *     names a technician's table without `technician_id = :technician_id`, (c)
 *     a device-wide query that is not on the list below, (d) a `deviceWide()`
 *     call from a file or for a reason not on the list below, (e) raw access
 *     from anywhere but the two files that own it. It prints how much it read,
 *     so a scan that silently saw nothing cannot pass (CLAUDE.md law 7).
 */
import { readdirSync, readFileSync, statSync } from 'fs';
import { join, relative } from 'path';

import { ScopeViolationError } from '../../src/db/database';
import * as outboxQ from '../../src/db/queries/outbox';
import * as workOrderQ from '../../src/db/queries/workOrder';
import { scoped } from '../../src/db/scoped';
import { SCOPED_TABLES } from '../../src/db/schema';
import { openStore } from './support/fixtures';

const SRC = join(__dirname, '../../src');

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    return statSync(p).isDirectory() ? walk(p) : /\.(ts|tsx)$/.test(name) ? [p] : [];
  });
}

/** Source without comments, so a docstring that MENTIONS a call is not a call. */
const withoutComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

const files = walk(SRC).map((p) => {
  const text = readFileSync(p, 'utf8');
  return { path: relative(SRC, p).replace(/\\/g, '/'), text, code: withoutComments(text) };
});

/** String and template literals that look like SQL. */
function sqlLiterals(text: string): string[] {
  const out: string[] = [];
  const re = /`([^`]*)`|'((?:[^'\\\n]|\\.)*)'/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    const body = m[1] ?? m[2] ?? '';
    if (/\b(SELECT\s[\s\S]*\bFROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|CREATE\s+(TABLE|INDEX|VIRTUAL))\b/i.test(body)) {
      out.push(body);
    }
  }
  return out;
}

const SCOPED_RE = new RegExp(`\\b(${SCOPED_TABLES.join('|')})\\b`, 'i');
const stripLiterals = (sql: string) => sql.replace(/'(?:[^']|'')*'/g, "''");

/** Every query that crosses technicians, and why. Adding one is a decision. */
const DEVICE_WIDE_QUERIES = new Set([
  'outbox.ts:countUnsentByTechnician', // the sign-out warning names everyone's unsent count (E2E-21)
  'outbox.ts:dueGroups', // send every technician's work under its own name
  'outbox.ts:nextBatch',
  'outbox.ts:markSending',
  'outbox.ts:resetInterrupted',
  'outbox.ts:settle', // receipts, by key
  'outbox.ts:refuse',
  'outbox.ts:emptyPhotoActsSettleable', // FB-019's one-time sweep, on the send path (DEF-FLD-10637)
  'outbox.ts:retryLater',
  'outbox.ts:attemptsOf',
  'outbox.ts:unroutedCount',
  'outbox.ts:deleteSettledBefore', // the purge
  'photo.ts:dueForUpload',
  'photo.ts:countWaiting',
  'photo.ts:countWaitingByTechnician', // the sign-out warning, photos on their own line (E2E-21, R65)
  'photo.ts:setUploadUrlByDeclaration',
  'photo.ts:markUploading',
  'photo.ts:markUploaded',
  'photo.ts:markFailed',
  'photo.ts:attemptsOf',
  'photo.ts:release',
  'photo.ts:deleteUploadedBefore',
  'photo.ts:photoFilesDue', // FB-030: photo files go 3 days after a close or turn-in, every technician's (the purge)
  'photo.ts:markFileDeleted',
  'routeRead.ts:setStateByKey',
  'workOrder.ts:closedBefore',
  'route.ts:turnedInBefore',
  'asset.ts:deleteOutOfScope',
  'document.ts:evictionCandidates',
  'document.ts:markEvicted',
]);

/** Which files may open which device-wide door. */
const DEVICE_WIDE_CALLERS: Record<string, string[]> = {
  'sync/outbox.ts': ['send'],
  'sync/receipts.ts': ['receipt'],
  'sync/photos.ts': ['send', 'receipt'],
  'db/purge.ts': ['purge'],
  // The session's view of the outbox: how much is waiting, per technician (no delete).
  'db/storeHolder.ts': ['count'],
};

describe('runtime: the doors refuse', () => {
  const db = openStore();
  afterAll(() => db.close());

  test('the reference runner refuses a technician’s table', () => {
    expect(() => db.ref.all('SELECT * FROM outbox')).toThrow(ScopeViolationError);
    expect(() => db.ref.all('SELECT w.id FROM premise p JOIN work_order w ON w.premise_id = p.id')).toThrow(ScopeViolationError);
    // a literal is not a table name
    expect(() => db.ref.all(`SELECT 'photo' AS kind FROM premise`)).not.toThrow();
  });

  test('a scoped statement must filter on :technician_id, with named parameters', () => {
    const s = scoped(db, 'dana');
    expect(() => s.all('SELECT * FROM outbox')).toThrow(ScopeViolationError);
    expect(() => s.all('SELECT * FROM outbox WHERE technician_id = ?', ['x'] as never)).toThrow(ScopeViolationError);
    expect(() => scoped(db, '')).toThrow(ScopeViolationError);
  });

  test("Marco signed in sees none of Dana's 62 unsent items, and none of her jobs (E2E-21)", () => {
    const dana = scoped(db, 'dana');
    const marco = scoped(db, 'marco');
    for (let i = 1; i <= 62; i++) {
      outboxQ.insert(dana, {
        id: `d-${i}`, workOrderId: 'wo-d', routeId: null, kind: 'task_tick', channel: 'job', payload: {}, seq: i,
        capturedBy: 'dana', capturedAt: '2026-10-21T08:00:00Z', location: null,
      });
    }
    workOrderQ.upsertFromServer(
      dana,
      { id: 'wo-d', number: 'WO-1', type: null, state: null, dispatchState: null, priorityCode: null, priorityRank: null, premiseId: null, windowStart: null, windowEnd: null, dueAt: null, estMinutes: null, accessNotes: null, hazards: null, gateCode: null, extra: null, serverUpdatedAt: null },
      '2026-10-21T08:00:00Z',
    );
    expect(outboxQ.countUnsentMine(marco)).toBe(0);
    expect(outboxQ.listMine(marco, { limit: 100 })).toEqual([]);
    expect(workOrderQ.listDay(marco, { before: '2099-01-01', limit: 10 })).toEqual([]);
    expect(outboxQ.countUnsentMine(dana)).toBe(62);
  });
});

describe('static: the query layer cannot be bypassed', () => {
  test('SQL lives only in db/queries/ and the migrations', () => {
    const allowed = (p: string) => p.startsWith('db/queries/') || p.startsWith('db/migrations/');
    const offenders = files.filter((f) => !allowed(f.path) && sqlLiterals(f.text).length > 0).map((f) => f.path);
    expect(offenders).toEqual([]);
  });

  test('every scoped query filters on the technician; every device-wide one is listed', () => {
    let checked = 0;
    const unfiltered: string[] = [];
    const unlisted: string[] = [];
    const queryFiles = files.filter((f) => f.path.startsWith('db/queries/'));
    for (const f of queryFiles) {
      const chunks = f.text.split(/\nexport function /).slice(1);
      for (const chunk of chunks) {
        const name = chunk.slice(0, chunk.indexOf('('));
        const firstParam = /\(\s*\w+\s*:\s*(\w+)/.exec(chunk)?.[1] ?? '';
        for (const sql of sqlLiterals(chunk)) {
          if (!SCOPED_RE.test(stripLiterals(sql))) continue;
          checked += 1;
          const label = `${f.path.replace('db/queries/', '')}:${name}`;
          if (firstParam === 'ScopedRunner') {
            const isInsert = /^\s*INSERT/i.test(sql);
            const filters = isInsert ? /:technician_id/.test(sql) : /technician_id\s*=\s*:technician_id/.test(sql);
            if (!filters) unfiltered.push(label);
          } else if (!DEVICE_WIDE_QUERIES.has(label)) {
            unlisted.push(`${label} (first parameter: ${firstParam || 'none'})`);
          }
        }
      }
    }
    // law 7: say how much was read, so a scan that saw nothing cannot pass
    // eslint-disable-next-line no-console
    console.log(`scoping: ${queryFiles.length} query files, ${checked} statements naming a technician's table`);
    expect(queryFiles.length).toBeGreaterThanOrEqual(19);
    expect(checked).toBeGreaterThan(40);
    expect(unfiltered).toEqual([]);
    expect(unlisted).toEqual([]);
  });

  test('every listed device-wide query still exists (a stale allow list hides nothing)', () => {
    const all = files.filter((f) => f.path.startsWith('db/queries/')).map((f) => f.path.replace('db/queries/', '') + ':' + f.text);
    for (const label of DEVICE_WIDE_QUERIES) {
      const [file, fn] = label.split(':');
      expect(all.some((x) => x.startsWith(`${file}:`) && x.includes(`export function ${fn}(`))).toBe(true);
    }
  });

  test('deviceWide() is opened only by the files and for the reasons listed', () => {
    const calls: string[] = [];
    for (const f of files) {
      if (f.path === 'db/scoped.ts') continue;
      for (const m of f.code.matchAll(/deviceWide\(\s*\w+\s*,\s*'(\w+)'\s*\)/g)) calls.push(`${f.path}:${m[1]}`);
      const bare = (f.code.match(/deviceWide\(/g) ?? []).length;
      const named = [...f.code.matchAll(/deviceWide\(\s*\w+\s*,\s*'(\w+)'\s*\)/g)].length;
      expect(`${f.path}: ${bare}`).toBe(`${f.path}: ${named}`); // no computed reasons
    }
    const offenders = calls.filter((c) => {
      const [path, reason] = c.split(':') as [string, string];
      return !(DEVICE_WIDE_CALLERS[path] ?? []).includes(reason);
    });
    expect(calls.length).toBeGreaterThan(0);
    expect(offenders).toEqual([]);
  });

  test('raw access comes only from the two files that own it', () => {
    const raw = files
      .filter((f) => /\brawRunner\(|\._raw\b|\._exec\(/.test(f.code))
      .map((f) => f.path)
      .sort();
    expect(raw).toEqual(['db/database.ts', 'db/queries/schemaMigrations.ts', 'db/scoped.ts']);
  });
});
