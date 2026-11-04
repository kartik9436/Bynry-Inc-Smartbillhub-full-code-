/**
 * MQ-017 / MQ-020 (CR-187-BRC10, PO 2026-10-24: *"B. Block on a required photo
 * - but show warning message to field technician"*) and DEF-FLD-10583.
 *
 * A step whose template marks its photo REQUIRED cannot be marked done until
 * its photographs are taken, and says so in place of a silent grey button; a
 * step whose photo count is only EXPECTED still only warns (R110). A reading
 * prompt with a required dial photo cannot be saved without one, and a saved
 * reading still short of its required photo is not counted in "x of 3".
 * The step's photo line has a real singular ("1 photo", not "1 photos").
 *
 * Mounted under the real navigation over the boards' WO-4822 (`./fixture`):
 * task-4 asks for 3 photos and is NOT required (1 taken); task-8 is REQUIRED
 * with 2 asked for (0 taken); r-master and r-sub-b need a dial photo.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, waitFor, within } from '@testing-library/react-native';

import * as jobQ from '../../../src/db/queries/jobScreens';
import * as woItemQ from '../../../src/db/queries/woItem';
import * as woReadingQ from '../../../src/db/queries/woReading';
import { scoped } from '../../../src/db/scoped';
import { createFieldI18n } from '../../../src/i18n/i18n';
import { tickSafety } from '../../../src/screens/theJob/actions';
import { DANA, seedWO4822, WO } from './fixture';
import { mountJob, onTop } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./window').currentWindow(),
}));

function safe() {
  const f = seedWO4822();
  for (const id of ['safety-1', 'safety-2', 'safety-3', 'safety-4']) tickSafety(f.port(), WO, id);
  return f;
}

const taskState = (f: ReturnType<typeof seedWO4822>, id: string) =>
  woItemQ.listForOrder(scoped(f.db, DANA), WO, 'task').find((t) => t.id === id)?.state ?? null;

describe('FF-17 — a REQUIRED step photo blocks Mark done (MQ-017)', () => {
  test('task-8 (required, 2 asked): Mark done is off and says why; live once both are taken', async () => {
    const f = safe();
    await mountJob(f.services, 'FF-17');
    const top = () => within(onTop('FF-17'));
    fireEvent.press(top().getByTestId('task-task-8'));
    const step = () => within(top().getByTestId('task-task-8'));

    expect(step().getByTestId('task-mark-done')).toBeDisabled();
    expect(step().getByTestId('task-photo-required')).toHaveTextContent(/Take 2 photos to finish this step\.$/);
    // the disabled button is still explained to a screen reader
    expect(step().getByTestId('task-mark-done')).toHaveProp('accessibilityHint', 'Take 2 photos to finish this step.');
    fireEvent.press(step().getByTestId('task-mark-done'));
    expect(taskState(f, 'task-8')).toBeNull();

    await act(async () => {
      fireEvent.press(step().getByTestId('task-take-photo'));
    });
    await waitFor(() => expect(step().getByTestId('task-photo-required')).toHaveTextContent(/Take 1 photo to finish this step\.$/));
    expect(step().getByTestId('task-mark-done')).toBeDisabled();

    await act(async () => {
      fireEvent.press(step().getByTestId('task-take-photo'));
    });
    await waitFor(() => expect(step().queryByTestId('task-photo-required')).toBeNull());
    expect(step().getByTestId('task-mark-done')).not.toBeDisabled();
    fireEvent.press(step().getByTestId('task-mark-done'));
    expect(taskState(f, 'task-8')).toBe('done');
  });

  test('task-4 (3 expected, NOT required): keeps the warning and stays pressable (R110)', async () => {
    const f = safe();
    await mountJob(f.services, 'FF-17');
    const step = within(within(onTop('FF-17')).getByTestId('task-task-4'));
    expect(step.getByTestId('task-photo-count')).toHaveTextContent(/This step needs 3 photos · 1 so far$/);
    expect(step.queryByTestId('task-photo-required')).toBeNull();
    expect(step.getByTestId('task-mark-done')).not.toBeDisabled();
    fireEvent.press(step.getByTestId('task-mark-done'));
    expect(taskState(f, 'task-4')).toBe('done');
  });

  test('DEF-FLD-10583: a step asking for ONE photo reads "1 photo", not "1 photos"', async () => {
    const f = safe();
    woItemQ.upsert(
      scoped(f.db, DANA),
      { id: 'task-9', workOrderId: WO, kind: 'task', position: 9, label: 'Record final read on old meter', photoRequired: true, photoMinCount: 1 },
      f.clock.now().toISOString(),
    );
    await mountJob(f.services, 'FF-17');
    const top = () => within(onTop('FF-17'));
    fireEvent.press(top().getByTestId('task-task-9'));
    const step = within(top().getByTestId('task-task-9'));
    expect(step.getByTestId('task-photo-count')).toHaveTextContent(/This step needs 1 photo · 0 so far$/);
    expect(step.getByTestId('task-photo-required')).toHaveTextContent(/Take 1 photo to finish this step\.$/);
    expect(step.getByTestId('task-mark-done')).toBeDisabled();
  });
});

describe('FF-20 — a REQUIRED dial photo blocks saving the reading (MQ-020)', () => {
  test('r-master: Save is off and says why; the typed figure is not saved; live once the dial is photographed', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-20');
    const top = () => within(onTop('FF-20'));
    const card = () => within(top().getByTestId('reading-r-master'));
    expect(top().getByTestId('readings-count')).toHaveTextContent('1 of 3');

    fireEvent.changeText(card().getByLabelText('Closing read'), '48500');
    expect(card().getByTestId('reading-r-master-save')).toBeDisabled();
    expect(card().getByTestId('reading-r-master-photo-required')).toHaveTextContent(/Take 1 photo to save this reading\.$/);
    expect(card().getByTestId('reading-r-master-save')).toHaveProp('accessibilityHint', 'Take 1 photo to save this reading.');
    fireEvent(card().getByLabelText('Closing read'), 'submitEditing');
    fireEvent.press(card().getByTestId('reading-r-master-save'));
    expect(woReadingQ.listForOrder(scoped(f.db, DANA), WO).find((r) => r.id === 'r-master')?.value).toBeNull();
    expect(top().getByTestId('readings-count')).toHaveTextContent('1 of 3');

    await act(async () => {
      fireEvent.press(card().getByTestId('reading-r-master-photo'));
    });
    await waitFor(() => expect(card().queryByTestId('reading-r-master-photo-required')).toBeNull());
    expect(card().getByTestId('reading-r-master-save')).not.toBeDisabled();
    fireEvent.press(card().getByTestId('reading-r-master-save'));
    expect(woReadingQ.listForOrder(scoped(f.db, DANA), WO).find((r) => r.id === 'r-master')?.value).toBe('48500');
    expect(jobQ.photosForOrder(scoped(f.db, DANA), WO).filter((p) => p.reading_id === 'r-master')).toHaveLength(1);
    expect(top().getByTestId('readings-count')).toHaveTextContent('2 of 3');
  });

  test('a reading saved without its required photo (before the block, or from the office) is not counted, and the card asks for it', async () => {
    const f = seedWO4822();
    woReadingQ.recordValue(scoped(f.db, DANA), 'r-master', { value: '48500', unit: 'gal', flagged: false, unableToRead: false, capturedAt: f.clock.now().toISOString() });
    await mountJob(f.services, 'FF-20');
    const top = () => within(onTop('FF-20'));
    expect(top().getByTestId('readings-count')).toHaveTextContent('1 of 3');
    const card = within(top().getByTestId('reading-r-master'));
    expect(card.getByTestId('reading-r-master-photo-required')).toHaveTextContent(/Take 1 photo to save this reading\.$/);
    // the saved figure can still be corrected: the field edits it
    expect(card.getByLabelText('Closing read')).toHaveProp('value', '48,500');
  });

  test('a reading with no required photo saves as before', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-20');
    const card = () => within(within(onTop('FF-20')).getByTestId('reading-r-sub-a'));
    expect(card().queryByTestId('reading-r-sub-a-photo-required')).toBeNull();
    fireEvent.changeText(card().getByLabelText('Closing read · Unit A'), '12600');
    expect(card().getByTestId('reading-r-sub-a-save')).not.toBeDisabled();
    fireEvent.press(card().getByTestId('reading-r-sub-a-save'));
    expect(woReadingQ.listForOrder(scoped(f.db, DANA), WO).find((r) => r.id === 'r-sub-a')?.value).toBe('12600');
  });
});

describe('plurals (DEF-FLD-10583)', () => {
  test('the step photo line, the warning and All photos each have a singular', () => {
    const { i18n } = createFieldI18n({ language: 'en' });
    expect(i18n.t('field.ff17.photoCount', { count: 1, taken: 0 })).toBe('This step needs 1 photo · 0 so far');
    expect(i18n.t('field.ff17.photoCount', { count: 3, taken: 1 })).toBe('This step needs 3 photos · 1 so far');
    expect(i18n.t('field.ff17.photoToFinish', { count: 1 })).toBe('Take 1 photo to finish this step.');
    expect(i18n.t('field.ff17.photoToFinish', { count: 2 })).toBe('Take 2 photos to finish this step.');
    expect(i18n.t('field.ff20.photoToSave', { count: 1 })).toBe('Take 1 photo to save this reading.');
    expect(i18n.t('field.ff20.allPhotos', { count: 1 })).toBe('1 photo');
    expect(i18n.t('field.ff20.allPhotos', { count: 3 })).toBe('All 3 photos');
  });
});
