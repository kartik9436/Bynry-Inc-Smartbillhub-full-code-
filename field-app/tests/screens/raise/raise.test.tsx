/**
 * T-22 Assets and raising work — FF-37 Raise, FF-38 Scan, FF-39 Asset, FF-40
 * History, FF-41 Search, FF-62 Pick a template — under the real navigator,
 * from the fixture handset (US-FLD-010, US-FLD-011, US-FLD-019, US-FLD-038,
 * US-FLD-039, US-FLD-076, US-FLD-084; R24, R41, R42, R43, R83, R112).
 *
 * Red proof (law 7): with FF-41's *only today* notice removed, US-FLD-039
 * TC-4 fails; with `raiseOrder` sending `template: null` instead of its own
 * copy of the body, US-FLD-076 TC-3 fails on `template`.
 */
import { fireEvent, waitFor, within } from '@testing-library/react-native';

import * as templatesQ from '../../../src/db/queries/workOrderTemplates';
import { FakeScanner } from '../../../src/screens/raise/scanner';
import { captured, current, local, makeWave, openScreen } from '../onSite/fixture';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

describe('FF-38 Scan', () => {
  test('TC-1: scan W-4471 on WO-4822 — Matches this job — Open asset', async () => {
    const scanner = new FakeScanner();
    const w = makeWave({ scanner });
    const app = await openScreen(w, 'FF-38', { workOrderId: 'wo-4822' });
    expect(scanner.formats).toEqual(['code128', 'code39', 'itf', 'upc_a', 'ean13']);
    await waitFor(() => expect(scanner.present({ value: 'W-4471', format: 'code128' })).toBe(true));
    const page = within(app.onTop());
    await waitFor(() => expect(page.getByTestId('scan-match')).toHaveTextContent(/Matches this job$/));
    expect(page.getByTestId('scanned-code')).toHaveTextContent('W-4471');
    fireEvent.press(page.getByTestId('open-asset'));
    expect(current(app.ref)).toEqual({ name: 'FF-39', params: { assetId: 'a-4471', workOrderId: 'wo-4822' } });
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`FF-38 → ${current(app.ref).name}`).toBe('FF-38 → FF-39');
    expect(captured(w.db)).toEqual([]); // scanning reads; it changes nothing
  });

  test('TC-2 (US-FLD-038) and R43: a badge finds its meter; QR mode reads QR and Data Matrix; the camera stays open', async () => {
    const scanner = new FakeScanner();
    const w = makeWave({ scanner });
    const app = await openScreen(w, 'FF-38', { workOrderId: 'wo-4822' });
    fireEvent.press(within(app.onTop()).getByTestId('scan-mode-qr'));
    await waitFor(() => expect(scanner.formats).toEqual(['qr', 'datamatrix']));
    expect(scanner.present({ value: '88-6120', format: 'code128' })).toBe(false);
    scanner.present({ value: '88-6120', format: 'datamatrix' });
    await waitFor(() => expect(within(app.onTop()).getByTestId('scan-other')).toHaveTextContent("Not this job's meter"));
    scanner.present({ value: 'W-4471', format: 'qr' });
    await waitFor(() => expect(within(app.onTop()).getByTestId('scan-match')).toBeTruthy());
  });

  test('TC-3 negative and TC-4: nothing found says so; Enter manually finds by typing', async () => {
    const scanner = new FakeScanner();
    const w = makeWave({ scanner });
    const app = await openScreen(w, 'FF-38', { workOrderId: 'wo-4822' });
    await waitFor(() => expect(scanner.present({ value: 'NOPE-1', format: 'ean13' })).toBe(true));
    await waitFor(() => expect(within(app.onTop()).getByTestId('scan-none')).toBeTruthy());
    fireEvent.press(within(app.onTop()).getByTestId('enter-manually'));
    fireEvent.changeText(app.getByLabelText('Serial, badge or device ID'), 'E1P-77412');
    fireEvent.press(app.getByTestId('manual-find'));
    await waitFor(() => expect(within(app.onTop()).getByTestId('scan-match')).toBeTruthy());
  });

  test('the torch is one tap (TC-3, US-FLD-084)', async () => {
    const scanner = new FakeScanner();
    const w = makeWave({ scanner });
    const app = await openScreen(w, 'FF-38', { workOrderId: 'wo-4822' });
    fireEvent.press(within(app.onTop()).getByTestId('torch'));
    expect(scanner.torch).toBe(true);
  });

  test('without a scanner on the handset it says so and typing still works', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-38', { workOrderId: 'wo-4822' });
    expect(within(app.onTop()).getByText('Scanning not available')).toBeTruthy();
    expect(within(app.onTop()).getByTestId('enter-manually')).not.toBeDisabled();
  });
});

describe('FF-39 Asset and FF-40 History', () => {
  test('TC-2: identity, where, sub-meters with their last reads, and the last read with its unit', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-39', { assetId: 'a-4471' });
    const page = within(app.onTop());
    expect(page.getByText('Water meter')).toBeTruthy();
    expect(page.getByTestId('asset-model')).toHaveTextContent('Neptune T-10 · 5/8"');
    expect(page.getByText('Since 14 Mar 2019')).toBeTruthy();
    expect(page.getByLabelText('Serial, W-4471')).toBeTruthy();
    expect(page.getByLabelText('Badge, 88-2041')).toBeTruthy();
    expect(page.getByLabelText('Device ID, E1P-77412')).toBeTruthy();
    expect(page.getByLabelText('Size, 5/8"')).toBeTruthy();
    expect(page.getByText('Pit at the front kerb')).toBeTruthy();
    expect(page.getByTestId('sub-W-4471-A')).toHaveProp('accessibilityLabel', 'W-4471-A, 12,210 gal');
    expect(page.getByTestId('sub-W-4471-B')).toHaveProp('accessibilityLabel', 'W-4471-B, 9,044 gal');
    expect(within(page.getByTestId('last-read')).getByText('48,180')).toBeTruthy();
    expect(within(page.getByTestId('last-read')).getByText('gal')).toBeTruthy();
    expect(within(page.getByTestId('last-read')).getByText('12 Jun 2026 · R. Patel')).toBeTruthy();
    fireEvent.press(page.getByTestId('door-FF-40'));
    expect(current(app.ref)).toEqual({ name: 'FF-40', params: { assetId: 'a-4471' } });
  });

  test('FF-40 TC-1/TC-2: the visits newest first, from the phone’s own copy', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-40', { assetId: 'a-4471' });
    const page = within(app.onTop());
    expect(page.getByTestId('visit-count')).toHaveTextContent('3 visits · cached on this phone');
    const first = within(page.getByTestId('visit-0'));
    expect(first.getByText('12 Jun 2026')).toBeTruthy();
    expect(first.getByText('Routine read')).toBeTruthy();
    expect(first.getByLabelText('Done, Read taken · 48,180 gal')).toBeTruthy();
    expect(first.getByLabelText('Who, R. Patel · 18 min')).toBeTruthy();
    const second = within(page.getByTestId('visit-1'));
    expect(second.getByText('Partly done')).toBeTruthy();
    expect(second.getByLabelText('Parts, 1 · wire seal')).toBeTruthy();
    expect(within(page.getByTestId('visit-2')).getByLabelText('Parts, None')).toBeTruthy();
  });

  test('the job’s own meter opens when only the job is named', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-39', { workOrderId: 'wo-4824' });
    expect(within(app.onTop()).getByLabelText('Serial, W-6120')).toBeTruthy();
  });
});

describe('FF-41 Assets', () => {
  test('TC-1 (US-FLD-039): W-447 finds three on this phone and says only today’s are here', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-41');
    fireEvent.changeText(within(app.onTop()).getByLabelText('Search assets'), 'W-447');
    const page = within(app.onTop());
    expect(page.getByTestId('on-phone-count')).toHaveTextContent('3 on this phone');
    expect(page.getByTestId('asset-W-4471')).toBeTruthy();
    expect(page.getByTestId('asset-W-4471-A')).toHaveProp('accessibilityLabel', 'W-4471-A, 1400 Elm Street · Unit A\nSub-meter');
    expect(page.getByTestId('only-today')).toHaveTextContent(/Only today's assets are here\./);
    expect(page.getByTestId('only-today')).toHaveTextContent(/A signal searches the whole utility\.$/);
    fireEvent.press(page.getByTestId('asset-W-4471'));
    expect(current(app.ref)).toEqual({ name: 'FF-39', params: { assetId: 'a-4471' } });
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`FF-41 → ${current(app.ref).name}`).toBe('FF-41 → FF-39');
  });

  test('TC-4 negative: an offline search with no match still says what it cannot see (R42)', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-41');
    fireEvent.changeText(within(app.onTop()).getByLabelText('Search assets'), 'ZZZ');
    expect(within(app.onTop()).getByTestId('on-phone-count')).toHaveTextContent('0 on this phone');
    expect(within(app.onTop()).getByTestId('only-today')).toBeTruthy();
  });
});

describe('FF-62 Pick a template and FF-37 Raise', () => {
  test('FF-62 TC-1/TC-4: recently used first, then every published one; never a draft', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-62', { carriedFrom: 'wo-4824' });
    const page = within(app.onTop());
    expect(page.getByLabelText('Search templates')).toHaveProp('placeholder', 'Search 3 templates');
    expect(within(page.getByTestId('recent-tpl-leak')).getByText('Leak investigation')).toBeTruthy();
    expect(within(page.getByTestId('recent-tpl-leak')).getByText('Water · 4 steps · 3 safety checks · 1 reading')).toBeTruthy();
    expect(page.getByTestId('use-tpl-leak')).toHaveProp('accessibilityLabel', 'Used 2 days ago, Use it →');
    expect(page.getByText('All templates · 3')).toBeTruthy();
    expect(page.queryByText('Draft thing')).toBeNull();
    fireEvent.changeText(page.getByLabelText('Search templates'), 'seal');
    expect(within(app.onTop()).queryByTestId('tpl-tpl-leak')).toBeNull();
    fireEvent.press(within(app.onTop()).getByTestId('tpl-tpl-seal'));
    expect(current(app.ref)).toEqual({ name: 'FF-37', params: { carriedFrom: 'wo-4824', templateId: 'tpl-seal' } });
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`FF-62 → ${current(app.ref).name}`).toBe('FF-62 → FF-37');
  });

  test('FF-37 TC-1/TC-2 and US-FLD-076 TC-2/TC-3: filled in, no number, the order keeps its own copy of v3', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-37', { carriedFrom: 'wo-4824', templateId: 'tpl-leak' });
    const page = within(app.onTop());
    expect(page.getByTestId('template-name')).toHaveTextContent('Leak investigation');
    expect(page.getByText('v3')).toBeTruthy();
    expect(page.getByTestId('template-counts')).toHaveTextContent('4 steps · 3 safety checks · 1 reading');
    expect(page.getByTestId('no-number')).toHaveTextContent(/Number arrives when this sends$/);
    const carried = within(page.getByTestId('carried-card'));
    expect(carried.getByText('Carried from WO-4824')).toBeTruthy();
    expect(carried.getByText('Aaron Bruner')).toBeTruthy();
    expect(carried.getByText('22 Cedar Court')).toBeTruthy();
    expect(carried.getByText('A-10588 · W-6120')).toBeTruthy();
    // DEF-FLD-10603: carried from a job, nothing asks where — the job says so.
    expect(page.queryByTestId('where-card')).toBeNull();
    await waitFor(() => expect(within(app.onTop()).getByTestId('raise-fix')).toHaveTextContent(/30\.2612, -97\.7431 · ±4m$/));
    fireEvent.press(within(app.onTop()).getByTestId('urgency-same_day'));
    fireEvent.press(within(app.onTop()).getByTestId('send-raise'));

    const raise = captured(w.db).find((a) => a.kind === 'raise')!;
    expect(raise.body).toMatchObject({
      template_id: 'tpl-leak',
      template_version: '3',
      template: { steps: ['a', 'b', 'c', 'd'] },
      carried_from: 'wo-4824',
      premise_id: 'p-22',
      account_id: 'acc-10588',
      customer_id: 'c-aaron',
      asset_id: 'a-6120',
      urgency: 'same_day',
    });
    expect(raise.body).not.toHaveProperty('number'); // R24
    expect(raise.lat).toBe(30.2612);
    // FB-028 (W2 = B): the screen stays with the raise in hand; *Done* goes back.
    expect(within(app.onTop()).getByTestId('raise-confirmation')).toBeTruthy();
    fireEvent.press(within(app.onTop()).getByTestId('door-FF-35'));
    expect(current(app.ref).name).toBe('FF-35');

    // TC-3 negative: the template moves to v4 afterwards — the raised order keeps v3.
    templatesQ.upsert(w.db, { id: 'tpl-leak', name: 'Leak investigation', version: '4', body: { steps: ['changed'] } }, local(20, 11));
    const again = captured(w.db).find((a) => a.kind === 'raise')!;
    expect(again.body).toMatchObject({ template_version: '3', template: { steps: ['a', 'b', 'c', 'd'] } });
  });

  test('with no template chosen, Send waits and Pick a template opens FF-62 carrying the job', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-37', { carriedFrom: 'wo-4824' });
    expect(within(app.onTop()).getByTestId('send-raise')).toBeDisabled();
    fireEvent.press(within(app.onTop()).getByTestId('door-FF-62'));
    expect(current(app.ref)).toEqual({ name: 'FF-62', params: { carriedFrom: 'wo-4824' } });
  });
});
