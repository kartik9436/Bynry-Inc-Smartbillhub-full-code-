/**
 * DEF-FLD-10603 (MQ-036) — *Raise work* from Home, under the real navigator,
 * over a real handset store, with the day's and the wave's data both mounted
 * as the app mounts them (`session/FieldRuntime.tsx`).
 *
 * The defect: Home → Raise work → pick a template → note → Send opened
 * *Completed / Nothing closed* with no word, the order carried no place, the
 * server refused it (`BR-WRK-006`), and the refusal said `raise` on Sync.
 * Every earlier raise test opened FF-37 carried from a job, so none of it was
 * seen. Each case here was run against the code before the fix and failed.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';

import type { TenantDb } from '../../../src/db/database';
import * as premiseQ from '../../../src/db/queries/premise';
import * as templatesQ from '../../../src/db/queries/workOrderTemplates';
import { scoped } from '../../../src/db/scoped';
import { unwiredSignature } from '../../../src/screens/closing/signature';
import { type FieldData as WaveData, FieldDataProvider as WaveDataProvider } from '../../../src/screens/onSite/fieldData';
import { FakeMoneyPort } from '../../../src/screens/onSite/money';
import { fakeDevicePorts } from '../../../src/screens/onSite/ports';
import { unwiredScanner } from '../../../src/screens/raise/scanner';
import * as outboxQ from '../../../src/db/queries/outbox';
import { FakeClock, idSource } from '../../db/support/fixtures';
import { mountApp } from '../../navigation/harness';
import { focusedLeaf } from '../../../src/navigation/routing';
import { DANA, NOW, seedDay } from '../theDay/dayFixture';
import serverTemplate from '../../sync/support/serverTemplate.json';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const FIX = { lat: 30.2612, lng: -97.7431, accuracy_m: 4, fix_at: NOW.toISOString() };

function waveData(db: TenantDb): WaveData {
  return {
    db,
    technicianId: DANA,
    newId: idSource('k'),
    clock: new FakeClock(NOW.getTime()),
    money: new FakeMoneyPort(),
    device: fakeDevicePorts({ location: FIX }),
    scanner: unwiredScanner,
    signature: unwiredSignature,
  };
}

async function mountHome() {
  const db = seedDay();
  // A premises on the handset that no job or stop of Dana's stands on (R132).
  premiseQ.upsert(db, { id: 'p-far', addressLine: '7 Far Lane', locality: 'Austin' }, NOW.toISOString());
  templatesQ.upsert(db, { id: 'tpl-leak', name: 'Leak investigation', version: '3', service: serverTemplate.service, stepCount: 4, safetyCount: 3, readingCount: 1, body: { steps: ['a'] } }, NOW.toISOString());
  const data = waveData(db);
  const app = await mountApp({
    fieldData: { db, now: () => NOW },
    wrap: (ui) => <WaveDataProvider value={data}>{ui}</WaveDataProvider>,
  });
  await screen.findByTestId('screen-FF-63');
  return { app, db };
}

const onTop = (id: string) => within(screen.getAllByTestId(`screen-${id}`).at(-1)!);
const where = (app: Awaited<ReturnType<typeof mountApp>>) => focusedLeaf(app.ref.getRootState());
const waiting = () => Number(/(\d+) waiting to send/.exec(String(within(screen.getAllByTestId('sync-strip').at(-1)!).getAllByText(/waiting to send/)[0]!.props.children))?.[1]);
const raises = (db: TenantDb) =>
  outboxQ
    .listMine(scoped(db, DANA), { limit: 50 })
    .filter((r) => r.kind === 'raise')
    .map((r) => ({ ...r, body: JSON.parse(r.payload) as Record<string, unknown> }));

describe('FF-37 raised from Home (DEF-FLD-10603)', () => {
  test('no job: a Where card, Send waits for a place, the place is the anchor, Send goes back Home and says so', async () => {
    const { app, db } = await mountHome();
    const before = waiting();

    fireEvent.press(screen.getAllByTestId('door-FF-37').at(-1)!);
    expect(where(app)).toBe('FF-37');
    expect(onTop('FF-37').queryByTestId('carried-card')).toBeNull();
    expect(onTop('FF-37').getByTestId('where-card')).toBeTruthy();

    // The template first, through FF-62 — the raise's own params go there and back.
    fireEvent.press(onTop('FF-37').getByTestId('door-FF-62'));
    fireEvent.press(onTop('FF-62').getByTestId('tpl-tpl-leak'));
    expect(where(app)).toBe('FF-37');
    expect(onTop('FF-37').getByTestId('template-name')).toHaveTextContent('Leak investigation');
    expect(onTop('FF-37').getByTestId('send-raise')).toBeDisabled();

    // R132: a premises no job of Dana's stands on never surfaces.
    fireEvent.changeText(onTop('FF-37').getByLabelText('Find the place'), 'Far Lane');
    expect(onTop('FF-37').getByTestId('where-on-phone')).toHaveTextContent('0 on this phone');

    fireEvent.changeText(onTop('FF-37').getByLabelText('Find the place'), 'Cedar');
    fireEvent.press(onTop('FF-37').getByTestId('where-premise:p-cedar'));
    expect(onTop('FF-37').getByTestId('where-address')).toHaveTextContent('22 Cedar Court');
    await waitFor(() => expect(onTop('FF-37').getByTestId('raise-fix')).toHaveTextContent(/30\.2612, -97\.7431 · ±4m$/));
    expect(onTop('FF-37').getByTestId('send-raise')).not.toBeDisabled();

    fireEvent.changeText(onTop('FF-37').getByTestId('raise-note'), 'Hydrant leaking at the kerb');
    await act(async () => {
      fireEvent.press(onTop('FF-37').getByTestId('send-raise'));
    });

    // FB-028 (W2 = B): the screen stays and says the raise is in hand; this
    // fixture has no server, so it waits for a signal. *Done* goes back where
    // it was opened, never *Completed / Nothing closed*.
    expect(screen.getByText('Raised. Sends with signal.')).toBeTruthy();
    expect(onTop('FF-37').getByTestId('raise-confirmation')).toBeTruthy();
    fireEvent.press(onTop('FF-37').getByTestId('door-FF-63'));
    expect(where(app)).toBe('FF-63');
    const [raised] = raises(db);
    expect(raised?.body).toMatchObject({ template_id: 'tpl-leak', premise_id: 'p-cedar', carried_from: null, note: 'Hydrant leaking at the kerb' });
    expect(raised?.lat).toBe(30.2612); // BR-MET-1202: the phone's position at capture
    // The waiting count on Home moved — it read 18 before and after on the beta phone.
    expect(waiting()).toBe(before + 1);
    app.unmount();
  });

  test('Cancel goes back Home too, and captures nothing', async () => {
    const { app, db } = await mountHome();
    fireEvent.press(screen.getAllByTestId('door-FF-37').at(-1)!);
    fireEvent.press(onTop('FF-37').getByTestId('door-FF-63'));
    expect(where(app)).toBe('FF-63');
    expect(raises(db)).toEqual([]);
    app.unmount();
  });
});
