/**
 * @jest-environment node
 *
 * DEF-FLD-10581 (beta MQ-011) — the job bundle's `help` reaches the handset.
 * The bundle is the server's real shape (`helpBundle`, from
 * `mobile._help_row`); the server wins on what it sends; a document's bytes
 * come down at sync inside the 200 MB budget.
 */
import * as documentQ from '../../src/db/queries/document';
import * as workOrderQ from '../../src/db/queries/workOrder';
import { scoped } from '../../src/db/scoped';
import { applyBundle, downloadHelpDocuments, fetchBundles, helpFileName } from '../../src/sync/extras';
import type { FieldApi } from '../../src/sync/fieldApi';
import { FakeClock, openStore } from '../db/support/fixtures';
import { FakeServer, helpBundle } from './support/fakeServer';

const WO = 'wo-7101';

class Disk {
  readonly files = new Map<string, number>();
  readonly deleted: string[] = [];
  constructor(private readonly server: FakeServer) {}
  async delete(path: string) {
    this.files.delete(path);
    this.deleted.push(path);
  }
  async download(url: string, name: string) {
    const body = this.server.documentFiles.get(url);
    if (body === undefined) throw new Error('HTTP 403');
    const path = `help/${name}`;
    this.files.set(path, body.length);
    return { path, bytes: body.length };
  }
}

function setup() {
  const clock = new FakeClock();
  const db = openStore('north', undefined, clock);
  const server = new FakeServer();
  return { clock, db, server, disk: new Disk(server) };
}

const rows = (db: ReturnType<typeof setup>['db']) =>
  documentQ.listForOwner(db, 'work_order', WO).map((d) => ({ id: d.id, kind: d.kind, title: d.title, ref: d.ref }));

test('every help entry of the bundle is stored as the job’s own, kind and ref intact', () => {
  const { db, server, clock } = setup();
  applyBundle(db, 'dana', helpBundle(server, WO), clock.now());
  expect(rows(db)).toEqual([
    { id: `${WO}-h3`, kind: 'link', title: 'Meter swap video', ref: 'https://video.example.test/meter-swap' },
    { id: `${WO}-h2`, kind: 'phone', title: 'Supervisor', ref: '(512) 555-0142' },
    { id: `${WO}-h1`, kind: 'document', title: 'Water shut-off SOP', ref: '0192a7c4-5b1e-7d2a-9c11-000000000001' },
  ]);
});

test('the server wins: an entry it stops sending leaves, a changed file is dropped, a captured paper is untouched', () => {
  const { db, server, clock } = setup();
  const b = helpBundle(server, WO);
  applyBundle(db, 'dana', b, clock.now());
  documentQ.markDownloaded(db, `${WO}-h1`, 'help/old.pdf', 10, clock.now().toISOString());
  documentQ.upsert(db, { id: 'paper-1', ownerKind: 'work_order', ownerId: WO, title: 'Permit', kind: 'pdf', source: 'camera' }, clock.now().toISOString());

  const orphans: string[] = [];
  applyBundle(db, 'dana', { ...b, help: [{ ...b.help![0]!, ref: 'another-file', url: 'https://x.test/new.pdf' }] }, clock.now(), orphans);
  expect(documentQ.listForOwner(db, 'work_order', WO).map((d) => d.id).sort()).toEqual(['paper-1', `${WO}-h1`]);
  expect(orphans).toEqual(['help/old.pdf']);
  expect(documentQ.get(db, `${WO}-h1`)).toMatchObject({ local_path: null, bytes: 0, url: 'https://x.test/new.pdf' });

  // A bundle that does not say what its help is leaves the phone's alone.
  const { help: _omitted, ...noHelp } = b;
  applyBundle(db, 'dana', noHelp, clock.now());
  expect(documentQ.listForOwner(db, 'work_order', WO)).toHaveLength(2);
});

test('a document comes down at sync and keeps its copy while the bundle names the same file', async () => {
  const { db, server, clock, disk } = setup();
  helpBundle(server, WO);
  const s = scoped(db, 'dana');
  const card = { id: WO, number: 'WO-7101', type: null, state: 'open', dispatchState: null, priorityCode: null, priorityRank: null, premiseId: null };
  const when = { windowStart: null, windowEnd: null, dueAt: null, estMinutes: null, accessNotes: null, hazards: null, gateCode: null };
  workOrderQ.upsertFromServer(s, { ...card, ...when, extra: null, serverUpdatedAt: null }, clock.now().toISOString());
  const api = server as unknown as FieldApi;
  const first = await fetchBundles(db, api, 'dana', { clock, files: disk });
  expect(first).toMatchObject({ fetched: 1, documentsDownloaded: 1 });
  expect(documentQ.get(db, `${WO}-h1`)).toMatchObject({ local_path: `help/${WO}-h1.pdf`, url: null });

  // The same bundle again (a fresh link, the same file): nothing re-downloaded, the copy kept.
  workOrderQ.upsertFromServer(s, { ...card, ...when, extra: null, serverUpdatedAt: null }, clock.now().toISOString());
  const again = await fetchBundles(db, api, 'dana', { clock, files: disk });
  expect(again.documentsDownloaded).toBe(0);
  expect(documentQ.get(db, `${WO}-h1`)?.local_path).toBe(`help/${WO}-h1.pdf`);
});

test('the 200 MB budget: a file that lands over it is deleted again and waits; a refused link waits too', async () => {
  const { db, server, clock, disk } = setup();
  applyBundle(db, 'dana', helpBundle(server, WO), clock.now());
  expect(await downloadHelpDocuments(db, disk, { clock, capBytes: 5 })).toBe(0);
  expect(disk.deleted).toEqual([`help/${WO}-h1.pdf`]);
  expect(documentQ.get(db, `${WO}-h1`)).toMatchObject({ local_path: null });

  server.documentFiles.clear();
  expect(await downloadHelpDocuments(db, disk, { clock })).toBe(0);
  expect(documentQ.get(db, `${WO}-h1`)?.url).not.toBeNull();
});

test('the file is named for the entry and keeps its link’s extension', () => {
  expect(helpFileName('h-1', 'https://f.test/a/b/sop.PDF?X-Amz-Signature=x')).toBe('h-1.pdf');
  expect(helpFileName('h/2', 'https://f.test/download/0192a7c4')).toBe('h_2');
});
