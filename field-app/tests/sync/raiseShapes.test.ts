/**
 * DEF-FLD-10603 (MQ-036) — the SHAPE LOCK on a raise. The phone's raise from
 * Home carried no place and the server refused it (`BR-WRK-006`), while every
 * test on both sides was green: the phone's tests raised only from inside a
 * job and never sent the body anywhere real, and the server's tests built
 * their own bodies.
 *
 * `support/raiseShapes.json` holds the two bodies the phone sends to
 * `POST work/mobile/orders` — from Home with a picked place, and carried from
 * a job — exactly, through the REAL send path (`sendPending` → `doorCallFor`
 * → `callDoor`). `06-backend/tests/test_def_fld_10603_raise_shapes.py` POSTs
 * exactly those to the real `raise_from_field`. A change on either side
 * without the other turns one of them red.
 */
import * as outboxQ from '../../src/db/queries/outbox';
import * as searchQ from '../../src/db/queries/templateSearch';
import { scoped } from '../../src/db/scoped';
import { loadJob } from '../../src/screens/onSite/job';
import { raiseOrder } from '../../src/screens/raise/RaiseScreen';
import type { DoorExtra } from '../../src/sync/fieldApi';
import { sendPending } from '../../src/sync/outbox';
import { steadyRandom } from '../db/support/fixtures';
import { DANA, local, makeWave, waveOf } from '../screens/onSite/fixture';
import { FakeServer } from './support/fakeServer';
import shapes from './support/raiseShapes.json';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

const FIX = { lat: 30.2612, lng: -97.7431, accuracy_m: 4, fix_at: local(20, 10) };

/** The sync fake plus the raise door, answering as `raise_from_field` does. */
class RaiseServer extends FakeServer {
  readonly bodies: Record<string, unknown>[] = [];
  raiseOrder(body: Record<string, unknown>, _extra?: DoorExtra) {
    this.bodies.push(body);
    return Promise.resolve({ order_id: 'o-1', order_no: 'WO-4870', duplicate: false });
  }
  jobBundle(): never {
    throw new Error('not asked');
  }
}

/** The sent body with its specifics put back as the file's placeholders. */
function asShape(body: Record<string, unknown>, specifics: Record<string, string>): Record<string, unknown> {
  const swap = (v: unknown, k: string): unknown => (typeof v === 'string' && specifics[k] === v ? `{${k}}` : v);
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(body)) {
    if (k === 'location' && v && typeof v === 'object') {
      out[k] = Object.fromEntries(Object.entries(v as Record<string, unknown>).map(([lk, lv]) => [lk, swap(lv, lk)]));
    } else out[k] = swap(v, k);
  }
  return out;
}

async function send(kind: 'home' | 'job') {
  const w = makeWave();
  const wave = waveOf(w);
  const template = searchQ.getPublished(w.db, 'tpl-leak')!;
  const key =
    kind === 'home'
      ? raiseOrder(wave, {
          template,
          from: null,
          place: { premiseId: 'p-22', accountId: null, assetId: null },
          urgency: 'normal',
          note: 'Hydrant leaking at the kerb',
          location: FIX,
        })
      : raiseOrder(wave, { template, from: loadJob(wave, 'wo-4824'), urgency: 'same_day', note: 'Second leak at the meter pit', location: FIX });
  const server = new RaiseServer();
  await sendPending(w.db, server, { clock: w.clock, tokens: { tokenFor: () => 'tok' }, random: steadyRandom });
  const row = outboxQ.getMine(scoped(w.db, DANA), key)!;
  return { body: server.bodies[0]!, key, row };
}

test('from Home: the place picked is the anchor, and the body is the shape the server is tested with', async () => {
  const { body, key, row } = await send('home');
  expect(
    asShape(body, { key, template_id: 'tpl-leak', template_version: '3', premises_id: 'p-22', captured_at: row.captured_at, fix_at: FIX.fix_at }),
  ).toEqual(shapes.fromHome);
  // The server's number lands on the row's answer — FF-50 shows it from there.
  expect(row.state).toBe('accepted');
  expect(JSON.parse(row.answer ?? '{}')).toMatchObject({ order_no: 'WO-4870' });
});

test('carried from a job: unchanged — the job is named and its anchors ride along', async () => {
  const { body, key, row } = await send('job');
  expect(
    asShape(body, {
      key,
      template_id: 'tpl-leak',
      template_version: '3',
      carried_from: 'wo-4824',
      premises_id: 'p-22',
      account_id: 'acc-10588',
      asset_id: 'a-6120',
      captured_at: row.captured_at,
      fix_at: FIX.fix_at,
    }),
  ).toEqual(shapes.fromJob);
});
