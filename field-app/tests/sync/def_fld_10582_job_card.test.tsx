/**
 * DEF-FLD-10582 (beta MQ-015): a job with a customer, a meter and an address
 * read *No customer*, *No asset* and a greyed *Navigate* on the phone.
 *
 * Every case here starts from the REAL server shapes (`support/serverJob.json`,
 * which `06-backend/tests/test_def_fld_10582_job_card_meter_point.py` holds to
 * the server's keys) and goes through the REAL sync path — the change feed
 * (`pullChanges`) and the bundle fetch (`fetchBundles`) — onto FF-15 and FF-25
 * mounted under the real navigation. The handset tests that passed while the
 * defect was live seeded customer, asset and position straight into the
 * handset database and so never met the wire.
 *
 * Proved red on the code as it stood (law 7): see the lane report for the
 * failure quoted.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';
import { Linking, Platform } from 'react-native';

import type { TenantDb } from '../../src/db/database';
import * as assetQ from '../../src/db/queries/asset';
import * as customerQ from '../../src/db/queries/customer';
import * as premiseQ from '../../src/db/queries/premise';
import * as workOrderQ from '../../src/db/queries/workOrder';
import { scoped } from '../../src/db/scoped';
import { pullChanges } from '../../src/sync/delta';
import { fetchBundles } from '../../src/sync/extras';
import type { FieldApi, WireBundle } from '../../src/sync/fieldApi';
import type { JobCard } from '../../src/sync/transport';
import { DANA as ONSITE_DANA, makeWave, openScreen } from '../screens/onSite/fixture';
import { DANA, makeServices } from '../screens/theJob/fixture';
import { mountJob, onTop } from '../screens/theJob/harness';
import { FakeClock, openStore } from '../db/support/fixtures';
import { FakeServer, serverBundle, serverCard } from './support/fakeServer';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('../screens/theJob/window').currentWindow(),
}));

let page = 0;

/** One sync, the way the engine runs it: the feed, then the bundles. */
async function sync(db: TenantDb, server: FakeServer, tech: string, card: JobCard, bundle: WireBundle = serverBundle(card)) {
  page += 1;
  const cursor = `c${server.pages.length + 1}`;
  server.pages.push({ changes: [{ change: 'upsert', order_id: card.id, at: `t${page}`, job: card }], count: 1, next_cursor: cursor, has_more: false });
  server.bundles.set(card.id, bundle);
  const clock = new FakeClock();
  await pullChanges(db, server, tech, { clock });
  await fetchBundles(db, server as unknown as FieldApi, tech, { clock });
}

describe('DEF-FLD-10582 — the real card and bundle reach FF-15 and FF-25', () => {
  test('FF-15: the customer, the meter line and Navigate, from the wire', async () => {
    const f = makeServices();
    const server = new FakeServer();
    const card = serverCard();
    await sync(f.db, server, DANA, card);

    const s = scoped(f.db, DANA);
    const order = workOrderQ.getMine(s, card.id)!;
    expect(order.customer_id).toBe('acct:A-10432');
    expect(order.asset_id).toBe(card.meter!.id);

    const openURL = jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
    await mountJob(f.services, 'FF-15', { params: { workOrderId: card.id }, openJob: card.id });
    const top = within(onTop('FF-15'));
    expect(top.getByTestId('job-customer-name')).toHaveTextContent('Sarah Miller');
    expect(top.getByTestId('job-customer-account')).toHaveTextContent('Account A-10432');
    expect(top.queryByText('No customer')).toBeNull();
    expect(top.getByText('W-5000 · Neptune T-10 · W-58')).toBeTruthy();
    expect(top.queryByText('No asset')).toBeNull();

    const navigate = top.getByTestId('job-navigate');
    expect(navigate).toBeEnabled();
    fireEvent.press(navigate);
    const expected =
      Platform.OS === 'ios'
        ? 'maps:?ll=30.267153,-97.743057&q=1400%20Elm%20Street'
        : 'geo:30.267153,-97.743057?q=30.267153,-97.743057(1400%20Elm%20Street)';
    expect(openURL).toHaveBeenCalledWith(expected);
    openURL.mockRestore();
  });

  test('FF-15: the Asset card opens the meter (FF-39)', async () => {
    // The door carries the job (DEF-FLD-10578) …
    const f = makeServices();
    const card = serverCard();
    await sync(f.db, new FakeServer(), DANA, card);
    const { ref } = await mountJob(f.services, 'FF-15', { params: { workOrderId: card.id }, openJob: card.id });
    await act(async () => {
      fireEvent.press(within(onTop('FF-15')).getByTestId('door-FF-39'));
    });
    expect(ref.getCurrentRoute()).toMatchObject({ name: 'FF-39', params: { workOrderId: card.id } });
    // … and FF-39, opened with that job, shows the synced meter.
    const w = makeWave();
    const job = serverCard({ id: 'wo-0028', order_no: 'WO-0028' });
    await sync(w.db, new FakeServer(), ONSITE_DANA, job);
    const app = await openScreen(w, 'FF-39', { workOrderId: 'wo-0028' });
    expect(within(app.onTop()).getByTestId('asset-model')).toHaveTextContent('Neptune T-10 · W-58');
  });

  test('FF-15: no point on the wire leaves Navigate disabled — nothing invented', async () => {
    const f = makeServices();
    const card = serverCard({ premise: { ...serverCard().premise!, lat: null, lng: null, position_source: null } });
    await sync(f.db, new FakeServer(), DANA, card);
    await mountJob(f.services, 'FF-15', { params: { workOrderId: card.id }, openJob: card.id });
    expect(within(onTop('FF-15')).getByTestId('job-navigate')).toBeDisabled();
  });

  test('a meter changed on the server replaces the old one on the next sync', async () => {
    const db = openStore('north');
    const server = new FakeServer();
    const first = serverCard();
    await sync(db, server, DANA, first);
    const exchanged = serverCard({
      meter: { id: 'asset-w6000', asset_no: 'W-6000', serial_no: '99-1', model: 'Badger M25', size_class: 'W-34', service: 'water' },
    });
    await sync(db, server, DANA, exchanged);

    const order = workOrderQ.getMine(scoped(db, DANA), first.id)!;
    expect(order.asset_id).toBe('asset-w6000');
    expect(assetQ.get(db, 'asset-w6000')).toMatchObject({ serial: 'W-6000', model: 'Badger M25', size: 'W-34', service: 'water' });
  });

  test("a unit's own point stays on the job; the building's row keeps the building's", async () => {
    const db = openStore('north');
    const card = serverCard({
      premise: { ...serverCard().premise!, lat: '30.268000', lng: '-97.744000', position_source: 'unit' },
    });
    await sync(db, new FakeServer(), DANA, card);
    const premise = premiseQ.get(db, card.premise!.id)!;
    expect([premise.lat, premise.lng]).toEqual([null, null]);
    const extra = JSON.parse(workOrderQ.getMine(scoped(db, DANA), card.id)!.extra!) as Record<string, unknown>;
    expect(extra.position).toEqual({ lat: 30.268, lng: -97.744, source: 'unit' });
  });

  test('the server wins on the customer: a bundle with none clears it', async () => {
    const db = openStore('north');
    const server = new FakeServer();
    const card = serverCard();
    await sync(db, server, DANA, card);
    expect(customerQ.get(db, 'acct:A-10432')).toMatchObject({ name: 'Sarah Miller', phone: '(512) 555-0114', account_number: 'A-10432' });
    await sync(db, server, DANA, card, serverBundle(card, { customer: null }));
    expect(workOrderQ.getMine(scoped(db, DANA), card.id)!.customer_id).toBeNull();
  });
});

describe('DEF-FLD-10582 — FF-25 from the wire', () => {
  test('FF-25: the name, the account, Call (tel:) and Navigate', async () => {
    const w = makeWave();
    // A job of the onSite technician's own, synced from the real shapes.
    const card = serverCard({ id: 'wo-0028', order_no: 'WO-0028' });
    await sync(w.db, new FakeServer(), ONSITE_DANA, card);

    const openURL = jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
    const app = await openScreen(w, 'FF-25', { workOrderId: 'wo-0028' });
    const page25 = within(app.onTop());
    expect(page25.getByTestId('customer-name')).toHaveTextContent('Sarah Miller');
    expect(page25.getByText('Account A-10432')).toBeTruthy();
    expect(page25.getByText('W-5000')).toBeTruthy();
    fireEvent.press(page25.getByTestId('call'));
    expect(openURL).toHaveBeenCalledWith('tel:(512) 555-0114');
    const navigate = page25.getByTestId('navigate');
    expect(navigate).toBeEnabled();
    fireEvent.press(navigate);
    expect(openURL).toHaveBeenLastCalledWith(expect.stringMatching(/^(geo|maps):.*30\.267153,-97\.743057/u));
    openURL.mockRestore();
    expect(screen.queryByText('No customer')).toBeNull();
  });
});
