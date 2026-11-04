/**
 * FF-59 Add a reading (requirement 72) and FF-60 Asset papers (R108).
 *
 * Proved red (law 7): with FF-59 offering every asset in the store rather
 * than the premises' own, *"only meters at this premises"* failed — MTR-9999
 * at 218 Pecan Grove was offered.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';

import * as outboxQ from '../../../src/db/queries/outbox';
import * as woReadingQ from '../../../src/db/queries/woReading';
import { scoped } from '../../../src/db/scoped';
import { DANA, seedWO4822, WO } from './fixture';
import { mountJob, onTop } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./window').currentWindow(),
}));

describe('FF-59 Add a reading (R7, R12)', () => {
  test('TC-3: only meters at this premises; TC-2: no reason, no Add it; TC-4: the unit is chosen; TC-1: saved, not flagged', async () => {
    const f = seedWO4822();
    const app = await mountJob(f.services, 'FF-59');
    const top = () => within(onTop('FF-59'));
    expect(top().getByText('MTR-0903 · 5/8"')).toBeTruthy();
    expect(top().queryByText(/MTR-9999/)).toBeNull();
    fireEvent.press(top().getByTestId('add-reading-meter-asset-mtr0903'));
    fireEvent.changeText(top().getByLabelText('The reading'), '00,124');
    // no unit chip starts selected — never assumed from the service
    for (const u of ['gal', 'CCF', 'kWh']) expect(top().getByTestId(`add-reading-unit-${u}`)).not.toBeChecked();
    fireEvent.press(top().getByTestId('add-reading-unit-gal'));
    expect(top().getByTestId('add-reading-save')).toBeDisabled();
    fireEvent.press(top().getByTestId('add-reading-reason-notListed'));
    expect(top().getByTestId('add-reading-save')).not.toBeDisabled();
    fireEvent.press(top().getByTestId('add-reading-save'));
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-20');
    const added = woReadingQ.listForOrder(scoped(f.db, DANA), WO).at(-1);
    expect({ value: added?.value, unit: added?.unit, flagged: added?.flagged, min: added?.min_value }).toEqual({ value: '00124', unit: 'gal', flagged: 0, min: null });
    const item = outboxQ.listMine(scoped(f.db, DANA), { limit: 100 }).find((r) => r.kind === 'reading');
    expect(JSON.parse(item?.payload ?? '{}')).toMatchObject({ asset_id: 'asset-mtr0903', added_in_field: true, reason: 'notListed', unit: 'gal' });
  });
});

describe('FF-60 Asset papers — the source recorded on each (R108)', () => {
  test('a typed paper shows its words and says Typed; a file says files are not available yet', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-60');
    const top = () => within(onTop('FF-60'));
    expect(top().getByTestId('papers-asset')).toHaveTextContent(/W-4471 · 5\/8" · Neptune T-10/);
    fireEvent.press(top().getByTestId('papers-typed'));
    const sheet = within(screen.getByTestId('paper-sheet'));
    fireEvent.changeText(sheet.getByLabelText('What is it?'), 'Factory seal number');
    expect(sheet.getByTestId('paper-save')).toBeDisabled();
    fireEvent.changeText(sheet.getByLabelText('What it says'), 'NT-88-412977');
    fireEvent.press(sheet.getByTestId('paper-save'));
    await waitFor(() => expect(top().getByText('Factory seal number')).toBeTruthy());
    expect(top().getByText('NT-88-412977')).toBeTruthy();
    expect(top().getByText('Typed')).toBeTruthy();
    expect(top().getByTestId('papers-done')).toHaveTextContent('Done — 1 attached');
    await act(async () => {
      fireEvent.press(top().getByTestId('papers-file'));
    });
    await waitFor(() => expect(top().getByTestId('papers-file-error')).toHaveTextContent('Files not available yet.'));
  });

  test('a photographed paper is a file from the camera, and says Camera', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-60');
    await act(async () => {
      fireEvent.press(within(onTop('FF-60')).getByTestId('papers-photograph'));
    });
    const sheet = within(await screen.findByTestId('paper-sheet'));
    fireEvent.changeText(sheet.getByLabelText('What is it?'), 'Serial plate');
    fireEvent.press(sheet.getByTestId('paper-save'));
    await waitFor(() => expect(within(onTop('FF-60')).getByText('Camera')).toBeTruthy());
    const doc = f.db.ref.get<{ source: string; local_path: string }>(`SELECT source, local_path FROM document WHERE title = 'Serial plate'`);
    expect(doc?.source).toBe('camera');
    expect(doc?.local_path).toMatch(/^file:\/\//);
  });
});
