/**
 * @jest-environment node
 *
 * The engine's ordering: data, then photographs, then the pull — and never a
 * pull while a push is in flight (R51, R59). A second sync call joins the one
 * running instead of starting a parallel one.
 */
import { SyncEngine } from '../../src/sync/engine';
import { capture } from '../../src/sync/outbox';
import { FakeClock, idSource, MemoryFiles, openStore, steadyRandom } from '../db/support/fixtures';
import { FakeServer } from './support/fakeServer';

test('push, then photos, then pull; overlapping calls share one run', async () => {
  const clock = new FakeClock();
  const db = openStore('north', undefined, clock);
  const server = new FakeServer();
  const log: string[] = [];
  const send = server.sendJobBatch.bind(server);
  server.sendJobBatch = async (id, items) => {
    log.push('push:start');
    const out = await send(id, items);
    log.push('push:end');
    return out;
  };
  const changes = server.changes.bind(server);
  server.changes = async (c, n) => {
    log.push('pull');
    return changes(c, n);
  };
  capture(db, { technicianId: 'dana', capturedBy: 'dana' }, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, { newId: idSource(), clock });

  const engine = new SyncEngine({ db, transport: server, files: new MemoryFiles(), tokens: { tokenFor: () => 't' }, clock, random: steadyRandom });
  const [a, b] = await Promise.all([
    engine.sync({ technicianId: 'dana', network: 'wifi' }),
    engine.sync({ technicianId: 'dana', network: 'wifi' }),
  ]);
  expect(a).toBe(b);
  expect(log).toEqual(['push:start', 'push:end', 'pull']);
  expect(a.data.accepted).toBe(1);
  expect(engine.running).toBe(false);
});

test('signed in as nobody: everything sends, nothing is pulled (E2E-21)', async () => {
  const clock = new FakeClock();
  const db = openStore('north', undefined, clock);
  const server = new FakeServer();
  capture(db, { technicianId: 'dana', capturedBy: 'dana' }, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, { newId: idSource(), clock });
  const engine = new SyncEngine({ db, transport: server, files: new MemoryFiles(), tokens: { tokenFor: (t) => `token-of-${t}` }, clock });
  const r = await engine.sync({ technicianId: null, network: 'wifi' });
  expect(r.data.accepted).toBe(1);
  expect(r.pull).toBeNull();
  expect(server.cursorsSeen).toEqual([]);
});
