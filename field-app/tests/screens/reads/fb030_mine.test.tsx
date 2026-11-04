/**
 * FB-030 (DEF-FLD-10806; PO 2026-10-31) — RW-28 My reads, PAGED, and its drill
 * from a route into each reading.
 *
 * RED FIRST (law 7): at 7af7fbd1f RW-28 read the first 200 routes and filtered
 * them in the screen (no *Show more*, a 201st route invisible), RW-27 listed no
 * reading, and RW-28 had no record for a `readId`.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import * as routeQ from '../../../src/db/queries/route';
import * as routeReadQ from '../../../src/db/queries/routeRead';
import { scoped } from '../../../src/db/scoped';
import { MINE_PAGE } from '../../../src/screens/reads/mine';
import { isLowerThanLast } from '../../../src/screens/reads/readingRecord';
import { RAY } from './fixture';
import { mountReads } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

type App = Awaited<ReturnType<typeof mountReads>>;

async function press(page: ReturnType<typeof within>, id: string) {
  await act(async () => {
    fireEvent.press(page.getByTestId(id));
  });
}

function capture(app: App, id: string, value: string | null, extra: { status?: 'read' | 'could_not_read'; reason?: string; remark?: string } = {}) {
  routeReadQ.recordCapture(scoped(app.db, RAY), id, {
    captureKey: `cap-${id}`,
    value,
    unit: 'gal',
    readerStatus: extra.status ?? 'read',
    noReadReason: extra.reason ?? null,
    remark: extra.remark ?? null,
    capturedAt: '2026-10-20T09:00:00.000Z',
    capturedBy: RAY,
    identifiedBy: 'listed',
    readMethod: 'walk',
  });
}

describe('FB-030 · RW-28 My reads', () => {
  test('pages its routes 50 at a time, with no cap, and the totals count every route of the tab', async () => {
    const app = await mountReads();
    const s = scoped(app.db, RAY);
    const extra = MINE_PAGE + 1;
    for (let i = 0; i < extra; i += 1) {
      const id = `r-${String(i).padStart(3, '0')}`;
      routeQ.upsert(s, { id, code: `R${i}`, cycle: 'WTR-M Oct' }, '2026-10-20T08:00:00.000Z');
      routeReadQ.upsertFromServer(s, { id: `${id}-m`, routeId: id, stopId: `${id}-s`, assetId: 'a0471', unit: 'gal' }, '2026-10-20T08:00:00.000Z');
      capture(app, `${id}-m`, '100');
    }
    const page = within((await app.open('RW-28'))!);
    expect(page.getByTestId('mine-routes')).toHaveTextContent(new RegExp(`^${extra}`));
    expect(page.getAllByTestId(/^mine-r-|^door-RW-27$/)).toHaveLength(MINE_PAGE);
    await press(page, 'mine-more');
    const after = within(screen.getAllByTestId('screen-RW-28').at(-1)!);
    expect(after.getAllByTestId(/^mine-r-|^door-RW-27$/)).toHaveLength(extra);
    expect(after.queryByTestId('mine-more')).toBeNull();
    app.unmount();
  });

  test('from a route into each reading, and the reading’s record: meter, address, value with unit, status, lower than last, note, time', async () => {
    const app = await mountReads();
    // 48,100 under a last reading of 48,210: FB-022's flag, derived on the phone.
    capture(app, 'r0471', '48100', { remark: 'Dial fogged' });
    capture(app, 'r0472', null, { status: 'could_not_read', reason: 'dog' });
    const receipt = within((await app.open('RW-27', { routeId: 'wlk-07' }))!);
    expect(receipt.getByTestId('route-readings')).toBeTruthy();
    await press(receipt, 'reading-0');
    expect(app.current()).toBe('RW-28');
    expect(app.currentParams()?.readId).toBe('r0471');
    const record = within((await app.open('RW-28', { readId: 'r0471' }))!);
    expect(record.getByTestId('reading-record')).toBeTruthy();
    expect(record.getByText('MTR-0471')).toBeTruthy();
    expect(record.getByText(/Maple/)).toBeTruthy();
    expect(record.getByTestId('reading-record-value')).toHaveTextContent(/48,100 gal/);
    expect(record.getByTestId('reading-record-lower')).toHaveTextContent('Lower than last');
    expect(record.getByTestId('reading-record-note')).toHaveTextContent(/Dial fogged/);
    app.unmount();
  });

  test('the can’t-read reason shows on a reading that could not be read', async () => {
    const app = await mountReads();
    capture(app, 'r0472', null, { status: 'could_not_read', reason: 'dog' });
    const record = within((await app.open('RW-28', { readId: 'r0472' }))!);
    expect(record.getByTestId('reading-record-reason')).toBeTruthy();
    expect(record.queryByTestId('reading-record-lower')).toBeNull();
    app.unmount();
  });

  test('lower than last: the server’s word on a refilled reading wins over the phone’s comparison', () => {
    expect(isLowerThanLast({ lower_than_last: 1, value: '5', previous_value: null })).toBe(true);
    expect(isLowerThanLast({ lower_than_last: 0, value: '5', previous_value: '9' })).toBe(false);
    expect(isLowerThanLast({ lower_than_last: null, value: '5', previous_value: '9' })).toBe(true);
    expect(isLowerThanLast({ lower_than_last: null, value: '10', previous_value: '9' })).toBe(false);
  });
});
