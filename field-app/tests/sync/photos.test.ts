/**
 * @jest-environment node
 *
 * T-10 photo phase / T-49's photo half: the file goes only on CONFIRMED
 * durable receipt (R61, R125); one at a time, oldest first; a failure moves on.
 */
import * as photoQ from '../../src/db/queries/photo';
import { scoped } from '../../src/db/scoped';
import { capture, sendPending } from '../../src/sync/outbox';
import { uploadPhotos } from '../../src/sync/photos';
import { TransportError } from '../../src/sync/transport';
import { FakeClock, idSource, MemoryFiles, openStore, steadyRandom } from '../db/support/fixtures';
import { FakeServer, sha256 } from './support/fakeServer';

const dana = { technicianId: 'dana', capturedBy: 'dana' };
const tokens = { tokenFor: () => 'token-of-dana' };

function setup(n = 1) {
  const clock = new FakeClock();
  const db = openStore('north', undefined, clock);
  const deps = { newId: idSource('k'), clock };
  const server = new FakeServer();
  const files = new MemoryFiles();
  const ids: string[] = [];
  for (let i = 1; i <= n; i++) {
    clock.advance(1000);
    const path = `/photos/${i}.jpg`;
    files.add(path);
    server.disk.set(path, `bytes-${i}`);
    const out = capture(
      db,
      dana,
      {
        kind: 'reading',
        workOrderId: 'wo-1',
        payload: { reading_id: `r-${i}` },
        photos: [{ localPath: path, sha256: sha256(`bytes-${i}`), bytes: 300_000, target: { reading_id: `r-${i}` } }],
      },
      deps,
    );
    ids.push(out.photoIds[0]!);
  }
  const s = scoped(db, 'dana');
  return { clock, db, server, files, ids, s, opts: { clock, network: 'wifi' as const, random: steadyRandom } };
}

describe('the photo phase', () => {
  test('nothing uploads before its declaration is acknowledged — there is nowhere to send it', async () => {
    const { db, server, files, ids, s, opts } = setup();
    const r = await uploadPhotos(db, server, files, opts);
    expect(r.uploaded).toBe(0);
    expect(server.photoRequests).toEqual([]);
    expect(photoQ.getMine(s, ids[0]!)?.state).toBe('pending');
  });

  test('durably received → the row is confirmed with its remote id and the FILE IS KEPT (FB-030, R61 superseded)', async () => {
    // PO 2026-10-31, *"keep photos only for 3 days"*: the purge takes the file
    // 3 days after the close or the turn-in (`purge.test.ts`), never the upload.
    const { db, server, files, ids, s, opts, clock } = setup();
    await sendPending(db, server, { clock, tokens });
    const r = await uploadPhotos(db, server, files, opts);
    expect(r.uploaded).toBe(1);
    expect(files.deleted).toEqual([]);
    expect(files.paths.has('/photos/1.jpg')).toBe(true);
    expect(photoQ.getMine(s, ids[0]!)).toMatchObject({ state: 'uploaded', file_deleted: 0, remote_id: ids[0] });
    expect(server.photoBytes.get(ids[0]!)).toBe('bytes-1');
  });

  test('a 200 that is NOT durable (still pending at the server) keeps the file', async () => {
    const { db, server, files, ids, s, opts, clock } = setup();
    await sendPending(db, server, { clock, tokens });
    server.answerPhotoPending = true;
    await uploadPhotos(db, server, files, opts);
    expect(files.paths.has('/photos/1.jpg')).toBe(true);
    expect(photoQ.getMine(s, ids[0]!)?.state).toBe('failed');
  });

  test('a dropped upload keeps the file, backs off, and the next photo still goes (R53)', async () => {
    const { db, server, files, ids, s, opts, clock } = setup(3);
    await sendPending(db, server, { clock, tokens });
    server.photoPutFails.set(ids[0]!, new TransportError('network', 'dropped'));
    const r = await uploadPhotos(db, server, files, opts);
    expect(r).toMatchObject({ uploaded: 2, failed: 1 });
    expect(server.photoRequests).toEqual(ids); // oldest first
    expect(server.maxPhotosInFlight).toBe(1);
    expect(files.paths.has('/photos/1.jpg')).toBe(true);
    expect(photoQ.getMine(s, ids[0]!)).toMatchObject({ state: 'failed', attempts: 1, file_deleted: 0 });

    server.photoPutFails.clear();
    await uploadPhotos(db, server, files, opts); // not due yet
    expect(server.photoRequests).toHaveLength(3);
    clock.advance(2_000);
    await uploadPhotos(db, server, files, opts);
    expect(photoQ.getMine(s, ids[0]!)?.state).toBe('uploaded');
    // FB-030: confirmed, and every file still on the phone for its 3 days.
    expect(files.paths.size).toBe(3);
  });

  test('bytes that do not match the declared hash are refused and the file is kept', async () => {
    const { db, server, files, ids, s, opts, clock } = setup();
    await sendPending(db, server, { clock, tokens });
    server.disk.set('/photos/1.jpg', 'corrupted');
    await uploadPhotos(db, server, files, opts);
    expect(files.paths.has('/photos/1.jpg')).toBe(true);
    expect(photoQ.getMine(s, ids[0]!)?.last_error).toBe('HTTP 409');
  });

  test('the upload never deletes a file, so a delete that would fail cannot hold up the confirmation (FB-030)', async () => {
    const { db, server, files, ids, s, opts, clock } = setup();
    await sendPending(db, server, { clock, tokens });
    files.failDeleteFor.add('/photos/1.jpg');
    await uploadPhotos(db, server, files, opts);
    expect(photoQ.getMine(s, ids[0]!)?.state).toBe('uploaded');
    expect(files.paths.size).toBe(1);
  });

  test('a file already gone is confirmed only if the SERVER says it has the bytes', async () => {
    const { db, server, files, ids, s, opts, clock } = setup(2);
    await sendPending(db, server, { clock, tokens });
    server.links.get(ids[0]!)!.state = 'staged'; // it had landed before the crash
    files.paths.clear();
    await uploadPhotos(db, server, files, opts);
    expect(photoQ.getMine(s, ids[0]!)?.state).toBe('uploaded');
    expect(photoQ.getMine(s, ids[1]!)).toMatchObject({ state: 'failed', last_error: 'file_missing' });
  });

  test('on mobile data the photographs wait for wi-fi unless the technician allowed it (R54)', async () => {
    const { db, server, files, opts, clock } = setup();
    await sendPending(db, server, { clock, tokens });
    expect(await uploadPhotos(db, server, files, { ...opts, network: 'cellular' })).toMatchObject({ waitingForWifi: true, uploaded: 0 });
    expect(server.photoRequests).toEqual([]);
    expect((await uploadPhotos(db, server, files, { ...opts, network: 'cellular', allowMobileData: true })).uploaded).toBe(1);
  });
});
