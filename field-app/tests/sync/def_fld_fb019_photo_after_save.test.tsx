/**
 * DEF-FLD-10637 (FB-019, PO report 2026-10-28 — technician Jeremy, Android
 * 2.606.0, route reads): a reading saved, then *Add photo* on RW-13 → after
 * Sync, *"This photo is damaged. Take it again."*, and retaking repeats it.
 *
 * Reproduced 2026-10-28 (RED on 2.606.0): adding a photo after saving queued
 * TWO route items of kind `photo` — the declaration (`photo_id`, `sha256`) and
 * an empty "act" carrying neither — and the reads door refuses the empty one
 * `photo_id_required`. The declaration also never named its reading.
 *
 * The fake door below judges a `photo` item the way
 * `06-backend/apps/metering/field_reads._judge_photo` does after this fix: an
 * id and a fingerprint are required, and a named reading must be one the door
 * already holds under that key.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import { fromJson } from '../../src/db/json';
import * as outboxQ from '../../src/db/queries/outbox';
import * as walkQ from '../../src/db/queries/readsWalk';
import { deviceWide, scoped } from '../../src/db/scoped';
import { capture, sendPending } from '../../src/sync/outbox';
import { HttpTransport } from '../../src/sync/transport';
import { RAY } from '../screens/reads/fixture';
import { mountReads } from '../screens/reads/harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

type Page = ReturnType<typeof within>;

async function press(page: Page, id: string) {
  await act(async () => {
    fireEvent.press(page.getByTestId(id));
  });
}

const top = async (id: string) => within((await screen.findAllByTestId(`screen-${id}`)).at(-1)!);

/** The reads door's judgement of the kinds this test sends. */
function fakeReadsDoor() {
  const readings = new Set<string>();
  const sent: Array<Record<string, unknown>> = [];
  const fetchImpl = jest.fn(async (_url: string, init: RequestInit) => {
    const items = JSON.parse(String(init.body)).items as Array<Record<string, unknown>>;
    sent.push(...items);
    const receipts = items.map((i) => {
      const key = String(i.key);
      if (i.kind === 'reading') {
        readings.add(key);
        return { key, result: 'accepted', outcome: 'posted' };
      }
      if (i.kind === 'photo') {
        if (typeof i.photo_id !== 'string' || !i.photo_id) return { key, result: 'refused', reason: 'photo_id_required', message_key: 'work.mobile.reads.photo_id_required' };
        if (typeof i.sha256 !== 'string' || !i.sha256) return { key, result: 'refused', reason: 'photo_sha256_required', message_key: 'work.mobile.reads.photo_sha256_required' };
        if (i.reading_key !== undefined && !readings.has(String(i.reading_key))) {
          return { key, result: 'refused', reason: 'photo_reading_unknown', message_key: 'work.mobile.reads.photo_reading_unknown' };
        }
        return { key, result: 'accepted', outcome: 'recorded', photo_id: i.photo_id, upload_url: `/api/silver-creek/work/mobile/reads/photos/${String(i.photo_id)}` };
      }
      return { key, result: 'accepted', outcome: 'recorded' };
    });
    return { ok: true, status: 200, json: async () => ({ server_time: '2026-10-28T09:20:00Z', items: receipts }) };
  });
  const transport = new HttpTransport({ origin: 'https://x', tenant: 'silver-creek', accessToken: () => 'acc', fetchImpl: fetchImpl as unknown as typeof fetch });
  return { transport, sent };
}

/** RW-09: type a figure and save, then RW-13 → Add photo → Take the photo, `extra` times. */
async function saveThenAdd(app: Awaited<ReturnType<typeof mountReads>>, extra: number) {
  const page = within((await app.open('RW-09', { readId: 'r0471' }))!);
  for (const d of '52410') fireEvent.press(page.getByTestId(`keypad-${d}`));
  await press(page, 'door-RW-13');
  for (let i = 0; i < extra; i += 1) {
    await press(await top('RW-13'), 'door-RW-14');
    await press(await top('RW-14'), 'door-RW-13');
  }
  return top('RW-13');
}

describe('FB-019 — a photo added to a saved reading reaches the server', () => {
  test('save → Add photo → Sync: nothing refused, and the one photo item names its reading', async () => {
    const app = await mountReads();
    const kept = await saveThenAdd(app, 1);
    // FB-002's count is the reading's own, unchanged.
    expect(kept.getByTestId('kept-photos')).toHaveTextContent(/1 photo/);
    const door = fakeReadsDoor();
    const summary = await sendPending(app.db, door.transport, { clock: app.clock, tokens: { tokenFor: () => 'capture-of-ray' }, random: () => 0.5 });
    expect(summary.refused).toBe(0);
    const reading = door.sent.find((i) => i.kind === 'reading');
    const photos = door.sent.filter((i) => i.kind === 'photo');
    // ONE item for the photo: its declaration, never an empty act beside it.
    expect(photos).toHaveLength(1);
    expect(photos[0]).toMatchObject({ reading_key: reading?.key, sha256: 'sha-1', capture_token: 'capture-of-ray' });
    expect(typeof photos[0]?.photo_id).toBe('string');
    // The shutter's own position travels on it (FB-003), with its fix time.
    expect(photos[0]?.position).toMatchObject({ fix_at: expect.any(String) });
    expect(walkQ.readingPhotoCount(scoped(app.db, RAY), 'r0471')).toBe(1);
    app.unmount();
  });

  test('a photo saved WITH the reading and two added after: one reading, three declarations, 0 refused', async () => {
    const app = await mountReads();
    let page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    await press(page, 'read-photo');
    await press(await top('RW-14'), 'door-RW-13');
    page = await top('RW-09');
    for (const d of '52410') fireEvent.press(page.getByTestId(`keypad-${d}`));
    await press(page, 'door-RW-13');
    for (let i = 0; i < 2; i += 1) {
      await press(await top('RW-13'), 'door-RW-14');
      await press(await top('RW-14'), 'door-RW-13');
    }
    expect((await top('RW-13')).getByTestId('kept-photos')).toHaveTextContent(/3 photos/);
    const door = fakeReadsDoor();
    const summary = await sendPending(app.db, door.transport, { clock: app.clock, tokens: { tokenFor: () => 'capture-of-ray' }, random: () => 0.5 });
    expect(summary.refused).toBe(0);
    expect(door.sent.map((i) => i.kind)).toEqual(['reading', 'photo', 'photo', 'photo']);
    const reading = door.sent[0]!;
    // Saved with it: named by the reading's `photos`; added after: by `reading_key`.
    expect((reading.photos as unknown[]).length).toBe(1);
    expect(door.sent.slice(2).every((p) => p.reading_key === reading.key)).toBe(true);
    app.unmount();
  });
});

describe('FB-019 — a phone already holding the refused empty items is cleaned up', () => {
  test('an empty photo act refused beside its accepted declaration is settled at the next sync; nothing else is touched', async () => {
    const app = await mountReads();
    await saveThenAdd(app, 0);
    const s = scoped(app.db, RAY);
    const m = walkQ.meter(s, 'r0471')!;
    // The 2.606.0 shape, exactly as that build queued it.
    const legacy = capture(
      app.db,
      { technicianId: RAY, capturedBy: RAY },
      {
        kind: 'photo',
        routeId: m.route_id,
        payload: { route_read_id: m.id },
        photos: [{ localPath: 'file:///photos/old.jpg', sha256: 'sha-old', bytes: 9, target: { route_read_id: m.id } }],
      },
      { newId: () => app.services.newId(), clock: app.clock },
    );
    // A refusal that is NOT this shape must stay refused.
    const other = capture(
      app.db,
      { technicianId: RAY, capturedBy: RAY },
      { kind: 'route_read', routeId: m.route_id, payload: { meter_no: 'MTR-X', reader_status: 'read', value: 'x', unit: 'gal' } },
      { newId: () => app.services.newId(), clock: app.clock },
    );
    const door = fakeReadsDoor();
    await sendPending(app.db, door.transport, { clock: app.clock, tokens: { tokenFor: () => 'capture-of-ray' }, random: () => 0.5 });
    outboxQ.refuse(deviceWide(app.db, 'receipt'), other.key, { reason: 'value_unreadable' });
    // The declaration went through; the empty act is not left as "needs you".
    expect(outboxQ.getMine(s, legacy.declarationKeys[0]!)?.state).toBe('accepted');
    expect(outboxQ.getMine(s, legacy.key)?.state).toBe('accepted');
    expect(fromJson<Record<string, unknown>>(outboxQ.getMine(s, legacy.key)?.answer)).toMatchObject({ swept: 'DEF-FLD-10637' });
    // And a later sync does not revive it, nor settle the unrelated refusal.
    await sendPending(app.db, door.transport, { clock: app.clock, tokens: { tokenFor: () => 'capture-of-ray' }, random: () => 0.5 });
    expect(outboxQ.getMine(s, other.key)?.state).toBe('refused');
    expect(outboxQ.needsAttentionMine(s, 99).map((r) => r.id)).toEqual([other.key]);
    app.unmount();
  });

  test('an empty act whose declaration was itself refused stays refused — it is settled only beside an accepted declaration', async () => {
    const app = await mountReads();
    await saveThenAdd(app, 0);
    const s = scoped(app.db, RAY);
    const m = walkQ.meter(s, 'r0471')!;
    const legacy = capture(
      app.db,
      { technicianId: RAY, capturedBy: RAY },
      { kind: 'photo', routeId: m.route_id, payload: { route_read_id: m.id }, photos: [{ localPath: 'file:///p/x.jpg', sha256: '', bytes: 9, target: { route_read_id: m.id } }] },
      { newId: () => app.services.newId(), clock: app.clock },
    );
    const door = fakeReadsDoor();
    await sendPending(app.db, door.transport, { clock: app.clock, tokens: { tokenFor: () => 'capture-of-ray' }, random: () => 0.5 });
    expect(outboxQ.getMine(s, legacy.declarationKeys[0]!)?.state).toBe('refused');
    expect(outboxQ.getMine(s, legacy.key)?.state).toBe('refused');
    app.unmount();
  });
});
