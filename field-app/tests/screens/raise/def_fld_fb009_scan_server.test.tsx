/**
 * DEF-FLD-10634 (beta FB-009) — FF-38 Scan and *Enter manually* find a meter
 * the PHONE does not hold by asking the server, as FF-41 already does
 * (MQ-046: offline the phone's meters, online every meter of the utility,
 * `GET work/mobile/assets/search`, N9).
 *
 * The reported case: reader Sam Curran, online, scans `AR-TEST-SN1` from Home;
 * the meter exists on the web and is on none of his jobs or routes. The phone
 * said *"No meter with this code"*.
 *
 * "Offline" is a build WITH a server search whose call fails as a dropped
 * connection does (`TransportError('network')`, no status) — not a build
 * without one, which is a preview and keeps the phone-only answer.
 *
 * Proved red (law 7) on the code as it stood (ScanScreen at a2af0074a): the
 * online scan and the online manual entry both showed `scan-none`, and the
 * offline case showed *"No meter with this code"* rather than the drawn note.
 */
import { act, fireEvent, waitFor, within } from '@testing-library/react-native';

import * as assetQ from '../../../src/db/queries/asset';
import type { AssetFinder } from '../../../src/screens/onSite/fieldData';
import { FakeScanner } from '../../../src/screens/raise/scanner';
import type { WireAssetHit } from '../../../src/sync/fieldApi';
import { TransportError } from '../../../src/sync/transport';
import { current, makeWave, openScreen } from '../onSite/fixture';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const SN1: WireAssetHit = {
  id: 'a-sn1',
  asset_no: 'AST-00912',
  serial: 'AR-TEST-SN1',
  type: 'meter',
  model: 'Itron 100W',
  size_class: '5/8"',
  sub_meter: false,
  place: { premises: { id: 'p-sn1', premise_no: 'PR-0912', address: '18 Ridge Rd' }, unit_label: null },
};

/** The utility's whole meter list, as the server's search answers it: prefixes match too. */
function serverWith(hits: WireAssetHit[]): AssetFinder & { asked: string[] } {
  const asked: string[] = [];
  return {
    asked,
    async search(q) {
      asked.push(q);
      const k = q.trim().toLowerCase();
      const found = hits.filter((h) => [h.serial, h.asset_no].some((v) => v && v.toLowerCase().startsWith(k)));
      return { hits: found, count: found.length, hasMore: false };
    },
  };
}

function wave(finder?: AssetFinder) {
  const scanner = new FakeScanner();
  const w = makeWave({ scanner });
  if (finder) w.data.assets = finder;
  return { w, scanner };
}

describe('FB-009: Scan asks the server for a meter the phone does not hold', () => {
  test('online, from Home: scanning AR-TEST-SN1 opens that meter (kept on the phone)', async () => {
    const finder = serverWith([SN1]);
    const { w, scanner } = wave(finder);
    expect(assetQ.matchScannedCode(w.db, 'AR-TEST-SN1')).toBeFalsy();
    const app = await openScreen(w, 'FF-38');
    await waitFor(() => expect(scanner.present({ value: 'AR-TEST-SN1', format: 'code128' })).toBe(true));
    await waitFor(() => expect(within(app.onTop()).getByTestId('scan-match')).toHaveTextContent(/Meter found$/));
    expect(within(app.onTop()).queryByTestId('scan-none')).toBeNull();
    expect(finder.asked).toEqual(['AR-TEST-SN1']);
    fireEvent.press(within(app.onTop()).getByTestId('open-asset'));
    await waitFor(() => expect(current(app.ref).name).toBe('FF-39'));
    expect(current(app.ref).params).toEqual(expect.objectContaining({ assetId: 'a-sn1' }));
    expect(assetQ.get(w.db, 'a-sn1')?.serial).toBe('AR-TEST-SN1');
    expect(assetQ.get(w.db, 'a-sn1')?.premise_id).toBe('p-sn1');
  });

  test('online, Enter manually takes the same path — case and spaces do not matter', async () => {
    const { w } = wave(serverWith([SN1]));
    const app = await openScreen(w, 'FF-38');
    fireEvent.press(within(app.onTop()).getByTestId('enter-manually'));
    fireEvent.changeText(app.getByLabelText('Serial, badge or device ID'), '  ar-test-sn1 ');
    await act(async () => {
      fireEvent.press(app.getByTestId('manual-find'));
    });
    await waitFor(() => expect(within(app.onTop()).getByTestId('scan-match')).toBeTruthy());
    fireEvent.press(within(app.onTop()).getByTestId('open-asset'));
    await waitFor(() => expect(current(app.ref).params).toEqual(expect.objectContaining({ assetId: 'a-sn1' })));
  });

  test('the asset number is an exact match too', async () => {
    const { w } = wave(serverWith([SN1]));
    const app = await openScreen(w, 'FF-38');
    fireEvent.press(within(app.onTop()).getByTestId('enter-manually'));
    fireEvent.changeText(app.getByLabelText('Serial, badge or device ID'), 'AST-00912');
    await act(async () => {
      fireEvent.press(app.getByTestId('manual-find'));
    });
    await waitFor(() => expect(within(app.onTop()).getByTestId('scan-match')).toBeTruthy());
  });

  test('online, only a PREFIX hit: No meter with this code (never the first hit)', async () => {
    const { w, scanner } = wave(serverWith([SN1]));
    const app = await openScreen(w, 'FF-38');
    await waitFor(() => expect(scanner.present({ value: 'AR-TEST', format: 'code128' })).toBe(true));
    await waitFor(() => expect(within(app.onTop()).getByTestId('scan-none')).toHaveTextContent('No meter with this code'));
    expect(within(app.onTop()).queryByTestId('open-asset')).toBeNull();
  });

  test('a short busy line while the server is asked', async () => {
    let answer: (v: { hits: WireAssetHit[]; count: number; hasMore: boolean }) => void = () => {};
    const { w, scanner } = wave({ search: () => new Promise((r) => (answer = r)) });
    const app = await openScreen(w, 'FF-38');
    await waitFor(() => expect(scanner.present({ value: 'AR-TEST-SN1', format: 'code128' })).toBe(true));
    await waitFor(() => expect(within(app.onTop()).getByTestId('scan-asking')).toHaveTextContent('Searching the utility…'));
    await act(async () => answer({ hits: [SN1], count: 1, hasMore: false }));
    await waitFor(() => expect(within(app.onTop()).getByTestId('scan-match')).toBeTruthy());
    expect(within(app.onTop()).queryByTestId('scan-asking')).toBeNull();
  });

  test('offline and not on this phone: says so in the drawing’s words', async () => {
    const { w, scanner } = wave({ search: () => Promise.reject(new TransportError('network', 'Network request failed')) });
    const app = await openScreen(w, 'FF-38');
    await waitFor(() => expect(scanner.present({ value: 'AR-TEST-SN1', format: 'code128' })).toBe(true));
    await waitFor(() =>
      expect(within(app.onTop()).getByTestId('scan-offline')).toHaveTextContent(/Not on this phone\. A signal searches the whole utility\.$/),
    );
    expect(within(app.onTop()).queryByTestId('scan-none')).toBeNull();
    expect(within(app.onTop()).queryByTestId('open-asset')).toBeNull();
  });

  test('offline, a meter the phone holds still opens without the server', async () => {
    const asked: string[] = [];
    const { w } = wave({ search: (q) => (asked.push(q), Promise.reject(new TransportError('network', 'down'))) });
    const app = await openScreen(w, 'FF-38');
    fireEvent.press(within(app.onTop()).getByTestId('enter-manually'));
    fireEvent.changeText(app.getByLabelText('Serial, badge or device ID'), 'W-4471');
    await act(async () => {
      fireEvent.press(app.getByTestId('manual-find'));
    });
    await waitFor(() => expect(within(app.onTop()).getByTestId('scan-match')).toBeTruthy());
    expect(asked).toEqual([]);
  });

  test('the server failed: says so, short', async () => {
    const { w, scanner } = wave({ search: () => Promise.reject(new TransportError('network', 'HTTP 503', 503)) });
    const app = await openScreen(w, 'FF-38');
    await waitFor(() => expect(scanner.present({ value: 'AR-TEST-SN1', format: 'code128' })).toBe(true));
    await waitFor(() => expect(within(app.onTop()).getByTestId('scan-failed')).toHaveTextContent('Search failed. Try again.'));
  });

  test("on a job, a server meter that is not the job's: Not this job's meter", async () => {
    const { w, scanner } = wave(serverWith([SN1]));
    const app = await openScreen(w, 'FF-38', { workOrderId: 'wo-4822' });
    await waitFor(() => expect(scanner.present({ value: 'AR-TEST-SN1', format: 'code128' })).toBe(true));
    await waitFor(() => expect(within(app.onTop()).getByTestId('scan-other')).toHaveTextContent("Not this job's meter"));
    fireEvent.press(within(app.onTop()).getByTestId('open-asset'));
    await waitFor(() => expect(current(app.ref).params).toEqual(expect.objectContaining({ assetId: 'a-sn1', workOrderId: 'wo-4822' })));
  });
});
