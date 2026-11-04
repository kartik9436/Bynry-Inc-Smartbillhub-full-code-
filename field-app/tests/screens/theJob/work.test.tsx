/**
 * T-19 Doing the work — FF-17 Tasks, FF-18 Add step, FF-19 Checklist, FF-20
 * Readings, FF-21 Photos, FF-22 Compare, FF-23 Materials, FF-24 Parts used —
 * mounted under the real navigation from a seeded store.
 *
 * Proved red (law 7): with FF-20's commit saving the first out-of-range figure
 * straight away (no second entry), US-FLD-009 TC-2 and TC-3 both failed —
 * *"Outside expected range"* never appeared and the typo was saved.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';

import * as jobQ from '../../../src/db/queries/jobScreens';
import * as outboxQ from '../../../src/db/queries/outbox';
import * as settingsQ from '../../../src/db/queries/settings';
import * as woItemQ from '../../../src/db/queries/woItem';
import * as woReadingQ from '../../../src/db/queries/woReading';
import { scoped } from '../../../src/db/scoped';
import { tickSafety } from '../../../src/screens/theJob/actions';
import { CANT_READ_KEY } from '../../../src/sync/routes';
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

const outbox = (f: ReturnType<typeof seedWO4822>) => outboxQ.listMine(scoped(f.db, DANA), { limit: 500 });

describe('FF-17 Tasks — photographs on the step (R6, R110); field additions marked (R7)', () => {
  test('locked until safety is done (R3)', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-17');
    expect(within(onTop('FF-17')).getByTestId('tasks-locked')).toBeTruthy();
    expect(within(onTop('FF-17')).queryByTestId('task-list')).toBeNull();
  });

  test('US-FLD-074 TC-1/TC-2: step 4 needs 3 photos, 1 so far; a photo is taken ON the step; Mark done at 2 of 3 still works', async () => {
    const f = safe();
    await mountJob(f.services, 'FF-17');
    const top = () => within(onTop('FF-17'));
    expect(top().getByTestId('tasks-count')).toHaveTextContent('3 of 8');
    expect(top().getByText('Travel 14m · on site 2h 12m')).toBeTruthy();
    expect(top().getByText('52 min est.')).toBeTruthy();
    const step = () => within(top().getByTestId('task-task-4'));
    expect(step().getByTestId('task-photo-count')).toHaveTextContent(/This step needs 3 photos · 1 so far$/);
    expect(step().getByTestId('task-take-photo')).toHaveTextContent(/2 more$/);

    await act(async () => {
      fireEvent.press(step().getByTestId('task-take-photo'));
    });
    await waitFor(() => expect(step().getByTestId('task-photo-count')).toHaveTextContent(/2 so far$/));
    const photos = jobQ.photosForOrder(scoped(f.db, DANA), WO).filter((p) => p.task_id === 'task-4');
    expect(photos).toHaveLength(2);
    // the camera pipeline stamped it (R94) and it is a file, never bytes (R52)
    expect(f.shrink.calls.at(-1)?.stamp).toEqual(['20 Oct 2026 · 10:58', '30.2651, -97.7494 · ±4m', 'D. Ortiz · WO-4822 · Silver Creek Water']);
    expect(photos[1]?.local_path).toMatch(/^file:\/\//);

    // short of the count warns and never blocks (R110)
    fireEvent.press(step().getByTestId('task-mark-done'));
    expect(woItemQ.listForOrder(scoped(f.db, DANA), WO, 'task').find((t) => t.id === 'task-4')?.state).toBe('done');
    expect(outbox(f).some((r) => r.kind === 'task_tick' && JSON.parse(r.payload).task_id === 'task-4')).toBe(true);
    // the next step opens — the one added in the field, marked as such
    expect(within(top().getByTestId('task-task-5')).getByText('Added in the field')).toBeTruthy();
    expect(within(top().getByTestId('task-task-5')).getByText('15 min · D. Ortiz 09:31')).toBeTruthy();
  });

  test('a build with no camera says so, and takes nothing', async () => {
    const f = safe();
    await mountJob({ ...f.services, camera: undefined, shrink: undefined }, 'FF-17');
    const step = within(within(onTop('FF-17')).getByTestId('task-task-4'));
    await act(async () => {
      fireEvent.press(step.getByTestId('task-take-photo'));
    });
    await waitFor(() => expect(step.getByTestId('task-camera-error')).toHaveTextContent('Camera not available yet.'));
    expect(jobQ.photosForOrder(scoped(f.db, DANA), WO).filter((p) => p.task_id === 'task-4')).toHaveLength(1);
  });
});

describe('FF-18 Add a step (R7)', () => {
  test('TC-3: no reason, not saved; TC-1: with one, listed as added in the field', async () => {
    const f = safe();
    const app = await mountJob(f.services, 'FF-18');
    const top = () => within(onTop('FF-18'));
    expect(top().getByTestId('add-step-save')).toBeDisabled();
    fireEvent.changeText(top().getByLabelText('What did you do?'), 'Replace stop valve');
    expect(top().getByTestId('add-step-save')).toBeDisabled();
    fireEvent.changeText(top().getByLabelText('Why was it needed?'), 'Valve seized open.');
    fireEvent.press(top().getByTestId('add-step-minutes-30'));
    fireEvent.press(top().getByTestId('add-step-photo'));
    expect(top().getByTestId('add-step-photo')).toBeChecked();
    fireEvent.press(top().getByTestId('add-step-save'));
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-17');
    const added = woItemQ.listForOrder(scoped(f.db, DANA), WO, 'task').find((t) => t.label === 'Replace stop valve');
    expect({ added: added?.added_in_field, reason: added?.reason, photo: added?.photo_required, detail: JSON.parse(added?.detail ?? '{}').minutes }).toEqual({
      added: 1,
      reason: 'Valve seized open.',
      photo: 1,
      detail: 30,
    });
  });
});

describe('FF-19 Checklist — questions that branch (requirement 18)', () => {
  test('TC-1/TC-3/TC-2: the branch shows on yes, goes on no; a No shows the template’s line', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-19');
    const top = () => within(onTop('FF-19'));
    expect(top().getByText('3 of 5 answered')).toBeTruthy();
    expect(top().getByTestId('because-q2')).toHaveTextContent('Because you said Yes');
    fireEvent.press(top().getByTestId('answer-q1-no'));
    expect(top().queryByTestId('question-q2')).toBeNull();
    fireEvent.press(top().getByTestId('answer-q4-no'));
    expect(top().getByTestId('hint-q4')).toHaveTextContent('No opens a tamper report');
    expect(top().getByTestId('checklist-submit')).toBeDisabled();
    fireEvent.press(top().getByTestId('answer-q5-yes'));
    expect(top().getByTestId('checklist-submit')).not.toBeDisabled();
  });
});

describe('FF-20 Readings — out of range is flagged, never refused (R11); the unit always shown (R12)', () => {
  // r-master asks for a REQUIRED dial photo, so since MQ-020 (PO 2026-10-24)
  // it cannot be saved without one: TC-2 and TC-3 photograph the dial first.
  const dial = async (card: () => ReturnType<typeof within>) => {
    await act(async () => {
      fireEvent.press(card().getByTestId('reading-r-master-photo'));
    });
    await waitFor(() => expect(card().queryByTestId('reading-r-master-photo-required')).toBeNull());
  };

  test('TC-2: 58,000 → enter it again → the same again is accepted and marked', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-20');
    const card = () => within(within(onTop('FF-20')).getByTestId('reading-r-master'));
    await dial(card);
    expect(card().getByText('gal')).toBeTruthy();
    expect(card().getByText('Expected 40,000–50,000 · last 48,180')).toBeTruthy();
    fireEvent.changeText(card().getByLabelText('Closing read'), '58,000');
    fireEvent.press(card().getByTestId('reading-r-master-save'));
    expect(card().getByTestId('reading-r-master-again')).toHaveTextContent(/Outside expected range\. Enter it again\./);
    expect(woReadingQ.listForOrder(scoped(f.db, DANA), WO).find((r) => r.id === 'r-master')?.value).toBeNull();
    fireEvent.press(card().getByTestId('reading-r-master-enter-again'));
    fireEvent.changeText(card().getByLabelText('Closing read'), '58000');
    fireEvent(card().getByLabelText('Closing read'), 'submitEditing');
    expect(card().getByTestId('reading-r-master-marked')).toHaveTextContent('Accepted. Marked for the office.');
    const row = woReadingQ.listForOrder(scoped(f.db, DANA), WO).find((r) => r.id === 'r-master');
    expect({ value: row?.value, unit: row?.unit, flagged: row?.flagged }).toEqual({ value: '58000', unit: 'gal', flagged: 1 });
  });

  test('TC-3: 58,000 then 48,200 — the typo is not flagged', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-20');
    const card = () => within(within(onTop('FF-20')).getByTestId('reading-r-master'));
    await dial(card);
    fireEvent.changeText(card().getByLabelText('Closing read'), '58000');
    fireEvent.press(card().getByTestId('reading-r-master-save'));
    fireEvent.press(card().getByTestId('reading-r-master-enter-again'));
    fireEvent.changeText(card().getByLabelText('Closing read'), '48200');
    fireEvent.press(card().getByTestId('reading-r-master-save'));
    const row = woReadingQ.listForOrder(scoped(f.db, DANA), WO).find((r) => r.id === 'r-master');
    expect({ value: row?.value, flagged: row?.flagged }).toEqual({ value: '48200', flagged: 0 });
  });

  test('TC-4: Unable to read is recorded at the reading (R13); a dial photo taken first travels with the reading', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-20');
    const card = () => within(within(onTop('FF-20')).getByTestId('reading-r-sub-b'));
    await act(async () => {
      fireEvent.press(card().getByTestId('reading-r-sub-b-photo'));
    });
    await waitFor(() => expect(card().getByText('1 photo')).toBeTruthy());
    expect(jobQ.photosForOrder(scoped(f.db, DANA), WO).filter((p) => p.reading_id === 'r-sub-b')).toHaveLength(0);
    fireEvent.press(card().getByTestId('reading-r-sub-b-unable'));
    // DEF-MET-10609 — it asks why first. This phone holds no list yet: it says
    // so and records without a reason rather than blocking the answer.
    expect(card().getByTestId('no-reasons')).toHaveTextContent('No reasons on this phone yet.');
    fireEvent.press(card().getByTestId('reading-r-sub-b-unable-record'));
    const row = woReadingQ.listForOrder(scoped(f.db, DANA), WO).find((r) => r.id === 'r-sub-b');
    expect(row?.unable_to_read).toBe(1);
    // the held photograph landed with the reading, in its transaction
    expect(jobQ.photosForOrder(scoped(f.db, DANA), WO).filter((p) => p.reading_id === 'r-sub-b')).toHaveLength(1);
  });

  test('DEF-MET-10609: Unable to read picks one reason from the same list as RW-17, plus an optional note', async () => {
    const f = seedWO4822();
    // The list as a job bundle or the route download keeps it (`CANT_READ_KEY`).
    settingsQ.set(f.db, CANT_READ_KEY, [{ code: 'dog', label: 'Dog' }, { code: 'locked', label: 'Locked' }], '2026-10-26T08:00:00Z');
    await mountJob(f.services, 'FF-20');
    const card = () => within(within(onTop('FF-20')).getByTestId('reading-r-sub-b'));
    fireEvent.press(card().getByTestId('reading-r-sub-b-unable'));
    const reasons = within(card().getByTestId('reading-r-sub-b-reasons'));
    expect(reasons.getByLabelText('Dog')).toBeTruthy();
    expect(reasons.getByLabelText('Locked')).toBeTruthy();
    // No reason picked yet: Record does nothing.
    fireEvent.press(card().getByTestId('reading-r-sub-b-unable-record'));
    expect(woReadingQ.listForOrder(scoped(f.db, DANA), WO).find((r) => r.id === 'r-sub-b')?.unable_to_read).toBe(0);
    fireEvent.press(reasons.getByLabelText('Dog'));
    fireEvent.changeText(card().getByTestId('reading-r-sub-b-note'), ' Barking at the gate ');
    fireEvent.press(card().getByTestId('reading-r-sub-b-unable-record'));
    expect(woReadingQ.listForOrder(scoped(f.db, DANA), WO).find((r) => r.id === 'r-sub-b')?.unable_to_read).toBe(1);
    const sent = outboxQ
      .listMine(scoped(f.db, DANA), { limit: 500 })
      .filter((o) => o.kind === 'reading')
      .map((o) => JSON.parse(o.payload) as Record<string, unknown>)
      .find((p) => p.reading_id === 'r-sub-b');
    expect(sent).toMatchObject({ unable_to_read: true, value: null, unable_reason: 'dog', note: 'Barking at the gate' });
  });
});

describe('FF-21 Photos — a review, never the place of capture (R6, R93)', () => {
  test('each photograph under what it proves, stamped; a missing required one is shown missing, not taken here', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-21');
    const top = within(onTop('FF-21'));
    const meterInPlace = within(top.getByTestId('proof-task-1'));
    expect(meterInPlace.getByText('Before')).toBeTruthy();
    expect(meterInPlace.getByText('After')).toBeTruthy();
    expect(meterInPlace.getByText('20 Oct 2026 · 09:18')).toBeTruthy();
    expect(meterInPlace.getAllByText('D. Ortiz · WO-4822 · Silver Creek Water')).toHaveLength(2);
    expect(meterInPlace.getAllByText('Waiting to upload · 84 KB')).toHaveLength(2);
    const fitted = within(top.getByTestId('proof-task-8'));
    expect(fitted.getByText('Required')).toBeTruthy();
    expect(fitted.getByTestId('proof-task-8-missing')).toHaveTextContent('Not taken yet');
    // no capture and no gallery on this screen
    expect(top.queryByTestId('task-take-photo')).toBeNull();
    expect(top.queryByText(/gallery|camera roll|take photo/i)).toBeNull();
    // Three required photographs never taken: shown missing (a warning since PO 2026-10-21, never a block)
    expect(top.getByTestId('photos-missing')).toHaveTextContent(/3 required photos missing$/);
  });
});

describe('FF-22 Compare', () => {
  test('TC-2: before 09:18, after 09:52 · 34 min later, stacked or side by side', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-22', { params: { proofId: 'task-1' } });
    const top = () => within(onTop('FF-22'));
    expect(top().getByTestId('compare-stacked')).toBeTruthy();
    expect(within(top().getByTestId('compare-before')).getByText('09:18')).toBeTruthy();
    expect(within(top().getByTestId('compare-after')).getByText('09:52 · 34 min later')).toBeTruthy();
    fireEvent.press(top().getByTestId('compare-layout-side'));
    expect(top().getByTestId('compare-side')).toBeTruthy();
  });
});

describe('FF-23 Materials and FF-24 Parts used (requirement 16)', () => {
  test('TC-2 of US-FLD-028: one extra, one short; not on the van; Ask the depot is not pretended', async () => {
    const f = seedWO4822();
    const app = await mountJob(f.services, 'FF-23');
    const top = () => within(onTop('FF-23'));
    expect(top().getByTestId('materials-variance')).toHaveTextContent(/1 extra, 1 short\.$/);
    const meter = within(top().getByTestId('material-mat-meter'));
    expect(meter.getByText('Not on your van')).toBeTruthy();
    expect(meter.getByText('MTR-W58 · planned 1 · van 0')).toBeTruthy();
    expect(meter.getByTestId('material-mat-meter-depot')).toBeDisabled();
    // R20: a unit price up to 4 places, no currency guessed
    expect(within(top().getByTestId('material-mat-kit')).getByText('CPL-58 · 18.5000 each')).toBeTruthy();
    fireEvent.press(meter.getByTestId('material-mat-meter-qty-increase'));
    expect(top().getByTestId('materials-variance')).toHaveTextContent(/1 extra, 0 short\.$/);
    fireEvent.press(top().getByTestId('materials-done'));
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-15');
    const item = outbox(f).find((r) => r.kind === 'material');
    expect(JSON.parse(item?.payload ?? '{}')).toEqual({ material_id: 'mat-meter', used_qty: 1, step_id: null });
  });

  test('an added part needs a reason (R7)', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-23');
    const top = () => within(onTop('FF-23'));
    fireEvent.press(top().getByTestId('materials-add'));
    const sheet = within(screen.getByTestId('add-material-sheet'));
    fireEvent.changeText(sheet.getByLabelText('Part'), 'Gasket');
    expect(sheet.getByTestId('add-material-save')).toBeDisabled();
    fireEvent.changeText(sheet.getByLabelText('Why was it needed?'), 'Old one perished');
    fireEvent.press(sheet.getByTestId('add-material-save'));
    expect(within(onTop('FF-23')).getByTestId('materials-variance')).toHaveTextContent(/2 extra, 1 short\.$/);
  });

  test('FF-24 TC-1: the meter used on step 4 — the van drops to 0, recorded against the step', async () => {
    const f = safe();
    const app = await mountJob(f.services, 'FF-24');
    const top = () => within(onTop('FF-24'));
    expect(top().getByText('Fit new meter and seal')).toBeTruthy();
    expect(top().getByText('Step 4 of 8 · WO-4822')).toBeTruthy();
    expect(within(top().getByTestId('part-mat-meter')).getByText('MTR-W58 · serial W-9044 · van 0')).toBeTruthy();
    fireEvent.press(top().getByTestId('part-mat-meter-qty-increase'));
    expect(top().getByTestId('part-mat-meter-van')).toHaveTextContent('Van drops to 0 of Water meter 5/8".');
    fireEvent.press(top().getByTestId('door-FF-17'));
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-17');
    const item = outbox(f).find((r) => r.kind === 'material');
    expect(JSON.parse(item?.payload ?? '{}')).toEqual({ material_id: 'mat-meter', used_qty: 1, step_id: 'task-4' });
  });
});
