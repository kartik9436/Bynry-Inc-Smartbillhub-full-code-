/**
 * DEF-FLD-10603 (MQ-036) — what became of a raise, on FF-50 Sync, after the
 * REAL send path (`sendPending` → the raise door) has answered it:
 *   - the server numbered it → *WO-4870 raised* (R24: the server's number);
 *   - the server refused it → the refusal in WORDS under *needs you*, named as
 *     a raised order — it read `raise` and nothing a technician could act on.
 */
import 'react-native-gesture-handler/jestSetup';

import { within, screen } from '@testing-library/react-native';

import * as templatesQ from '../../../src/db/queries/workOrderTemplates';
import { scoped } from '../../../src/db/scoped';
import type { Wave } from '../../../src/screens/onSite/fieldData';
import { raiseOrder } from '../../../src/screens/raise/RaiseScreen';
import * as searchQ from '../../../src/db/queries/templateSearch';
import type { DoorExtra } from '../../../src/sync/fieldApi';
import { sendPending } from '../../../src/sync/outbox';
import { TransportError } from '../../../src/sync/transport';
import { steadyRandom } from '../../db/support/fixtures';
import { FakeServer } from '../../sync/support/fakeServer';
import { DANA, NOW, makeFixture, openScreen, type MeFixture } from './support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

class RaiseServer extends FakeServer {
  constructor(private readonly reply: () => Promise<Record<string, unknown>>) {
    super();
  }
  raiseOrder(_body: Record<string, unknown>, _extra?: DoorExtra) {
    return this.reply();
  }
  jobBundle(): never {
    throw new Error('not asked');
  }
}

function raiseFromHome(f: MeFixture): string {
  templatesQ.upsert(f.db, { id: 'tpl-leak', name: 'Leak investigation', version: '3' }, NOW.toISOString());
  const wave = {
    db: f.db,
    me: DANA,
    s: scoped(f.db, DANA),
    clock: { now: () => NOW },
    captor: { technicianId: DANA, capturedBy: DANA },
    deps: { newId: f.ids, clock: { now: () => NOW } },
  } as unknown as Wave;
  return raiseOrder(wave, {
    template: searchQ.getPublished(f.db, 'tpl-leak')!,
    from: null,
    place: { premiseId: 'p-22', accountId: null, assetId: null },
    urgency: 'normal',
    note: '',
    location: null,
  });
}

const send = (f: MeFixture, reply: () => Promise<Record<string, unknown>>) =>
  sendPending(f.db, new RaiseServer(reply), { clock: { now: () => NOW }, tokens: { tokenFor: () => 'tok' }, random: steadyRandom });

const onTop = () => within(screen.getAllByTestId('screen-FF-50').at(-1)!);

test('waiting, then numbered: the raise shows its WO number once the office has it', async () => {
  const f = makeFixture();
  const key = raiseFromHome(f);
  let app = await openScreen('FF-50', f);
  expect(within(onTop().getByTestId(`ff50-raised-${key}`)).getByText('Waiting to send')).toBeTruthy();
  app.unmount();

  await send(f, () => Promise.resolve({ order_id: 'o-1', order_no: 'WO-4870', duplicate: false }));
  app = await openScreen('FF-50', f);
  expect(onTop().getByTestId(`ff50-raised-order-${key}`)).toHaveTextContent('WO-4870 raised');
  expect(within(onTop().getByTestId(`ff50-raised-${key}`)).getByText('Leak investigation')).toBeTruthy();
  app.unmount();
});

test('refused: the server’s reason in words, named as a raised order', async () => {
  const f = makeFixture();
  const key = raiseFromHome(f);
  await send(f, () => Promise.reject(new TransportError('http', 'HTTP 400', 400, { message_key: 'work.order.anchor_required' })));
  const app = await openScreen('FF-50', f);
  const refused = within(onTop().getByTestId(`ff50-refused-${key}`));
  expect(refused.getByText('Raised order')).toBeTruthy();
  expect(onTop().getByTestId(`ff50-reason-${key}`)).toHaveTextContent('Say what this job is for.');
  app.unmount();
});
