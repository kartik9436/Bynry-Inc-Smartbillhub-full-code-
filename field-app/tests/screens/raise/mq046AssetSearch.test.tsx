/**
 * DEF-FLD-10604 (beta MQ-046) — FF-41 Asset search OFFLINE finds the meters
 * this phone holds because a SYNC put them there, says what it cannot see in
 * the drawing's words, and a hit opens FF-39 for that meter.
 *
 * Starts from the REAL server shapes (`tests/sync/support/serverJob.json`) and
 * the REAL sync path (`pullChanges` then `fetchBundles`), like
 * `tests/sync/def_fld_10582_job_card.test.tsx`. FF-41's own wave test seeds
 * `search_index` by hand in its fixture, which is how it passed while no sync
 * path ever indexed an asset: on a real phone the search found nothing.
 *
 * "Offline" here is a build WITH a server search whose call fails — what a
 * phone with no signal is — not a build without one.
 *
 * Proved red (law 7) on the code as it stood: *W-5000* gave
 * `0 on this phone` and no `asset-W-5000`; and the note read *"Server not
 * reached. This phone only."* rather than the drawn two lines.
 */
import { act, fireEvent, within } from '@testing-library/react-native';

import type { TenantDb } from '../../../src/db/database';
import { pullChanges } from '../../../src/sync/delta';
import { fetchBundles } from '../../../src/sync/extras';
import type { FieldApi } from '../../../src/sync/fieldApi';
import type { JobCard } from '../../../src/sync/transport';
import { FakeClock } from '../../db/support/fixtures';
import { FakeServer, serverBundle, serverCard } from '../../sync/support/fakeServer';
import { current, DANA, makeWave, openScreen } from '../onSite/fixture';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

async function syncJob(db: TenantDb, card: JobCard) {
  const server = new FakeServer();
  server.pages.push({ changes: [{ change: 'upsert', order_id: card.id, at: 't1', job: card }], count: 1, next_cursor: 'c1', has_more: false });
  server.bundles.set(card.id, serverBundle(card));
  const clock = new FakeClock();
  await pullChanges(db, server, DANA, { clock });
  await fetchBundles(db, server as unknown as FieldApi, DANA, { clock });
}

/** A phone with no signal: the server search is wired and its call fails. */
function offlineWave() {
  const w = makeWave();
  w.data.assets = { search: () => Promise.reject(new Error('Network request failed')) };
  return w;
}

describe('FF-41 offline: the meters a sync put on this phone', () => {
  test('a job’s meter from the real card is found by its number, with the drawn note', async () => {
    const w = offlineWave();
    const card = serverCard({ id: 'wo-0028', order_no: 'WO-0028' });
    await syncJob(w.db, card);

    const app = await openScreen(w, 'FF-41');
    await act(async () => {
      fireEvent.changeText(within(app.onTop()).getByLabelText('Search assets'), 'W-5000');
    });
    const page = within(app.onTop());
    expect(page.getByTestId('on-phone-count')).toHaveTextContent('1 on this phone');
    expect(page.getByTestId('asset-W-5000')).toBeTruthy();
    expect(page.getByTestId('only-today')).toHaveTextContent(/Only today's assets are here\./);
    expect(page.getByTestId('only-today')).toHaveTextContent(/A signal searches the whole utility\.$/);
    expect(page.queryByTestId('server-not-reached')).toBeNull();
  });

  test('the same meter is found by its address and by its true serial', async () => {
    const w = offlineWave();
    await syncJob(w.db, serverCard({ id: 'wo-0028', order_no: 'WO-0028' }));
    const app = await openScreen(w, 'FF-41');
    for (const words of ['88-2041', '1400 Elm']) {
      await act(async () => {
        fireEvent.changeText(within(app.onTop()).getByLabelText('Search assets'), words);
      });
      expect(within(app.onTop()).getByTestId('asset-W-5000')).toBeTruthy();
    }
  });

  test('tapping the hit opens FF-39 for that meter', async () => {
    const w = offlineWave();
    const card = serverCard({ id: 'wo-0028', order_no: 'WO-0028' });
    await syncJob(w.db, card);
    const app = await openScreen(w, 'FF-41');
    await act(async () => {
      fireEvent.changeText(within(app.onTop()).getByLabelText('Search assets'), 'W-5000');
    });
    await act(async () => {
      fireEvent.press(within(app.onTop()).getByTestId('asset-W-5000'));
    });
    expect(current(app.ref)).toEqual({ name: 'FF-39', params: { assetId: card.meter!.id } });
    // … and FF-39, given that assetId, shows the meter the sync stored.
    const asset = await openScreen(w, 'FF-39', { assetId: card.meter!.id });
    expect(within(asset.onTop()).getByTestId('asset-model')).toHaveTextContent('Neptune T-10 · W-58');
  });
});
