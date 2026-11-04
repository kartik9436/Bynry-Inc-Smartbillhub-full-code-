/**
 * DEF-FLD-10586 (beta MQ-024) — FF-15's *Continue* points at the NEXT
 * UNFINISHED PART of the job, in the order the PO approved: safety → tasks →
 * materials → readings → *Finish — debrief* (FF-32); a closed job's button is
 * *Closed* and does nothing. A job with no materials or no readings skips that
 * part.
 *
 * Escape: every FF-15 test before this file looked at WO-4822 part-way (step 4
 * of 8), which is also the only state the drawing shows. With every task done
 * the button read *"Continue — step 8 of 8"* and opened the task list again,
 * so there was no way forward from the job screen.
 *
 * Proved red on the code before the fix (law 7): the materials, readings,
 * debrief, no-parts and closed cases failed — e.g. *Expected element to have
 * text content "Continue — materials", Received "Continue — step 8 of 8"*.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, within } from '@testing-library/react-native';

import * as workOrderQ from '../../../src/db/queries/workOrder';
import * as woItemQ from '../../../src/db/queries/woItem';
import * as woReadingQ from '../../../src/db/queries/woReading';
import { scoped } from '../../../src/db/scoped';
import { capturePhoto, tickSafety } from '../../../src/screens/theJob/actions';
import { DANA, type JobFixture, local, photo, seedWO4822, WO } from './fixture';
import { mountJob, onTop } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./window').currentWindow(),
}));

afterEach(async () => {
  await act(async () => undefined);
});

const TASKS = ['task-1', 'task-2', 'task-3', 'task-4', 'task-5', 'task-6', 'task-7', 'task-8'];

function safetyDone(f: JobFixture) {
  for (const id of ['safety-1', 'safety-2', 'safety-3', 'safety-4']) tickSafety(f.port(), WO, id);
}
function tasksDone(f: JobFixture) {
  const s = scoped(f.db, DANA);
  for (const id of TASKS) woItemQ.setState(s, id, 'done');
}
function materialsDone(f: JobFixture) {
  // the 5/8" meter was planned (1) and not yet used (0): use it
  scoped(f.db, DANA).run(
    `UPDATE wo_item SET detail = json_set(detail, '$.used', 1) WHERE technician_id = :technician_id AND id = 'mat-meter'`,
  );
}
function readingsDone(f: JobFixture) {
  const s = scoped(f.db, DANA);
  const at = local(10, 0).toISOString();
  woReadingQ.recordValue(s, 'r-master', { value: '48500', unit: 'gal', flagged: false, unableToRead: false, capturedAt: at });
  woReadingQ.recordValue(s, 'r-sub-b', { value: '9100', unit: 'gal', flagged: false, unableToRead: false, capturedAt: at });
  // Both prompts ask for a REQUIRED dial photo, and since MQ-020 (PO 2026-10-24)
  // a figure without its required photo is not a reading done.
  capturePhoto(f.port(), WO, photo(41), { reading_id: 'r-master' });
  capturePhoto(f.port(), WO, photo(42), { reading_id: 'r-sub-b' });
}

async function continueOn(f: JobFixture) {
  const app = await mountJob(f.services, 'FF-15', { params: { workOrderId: WO } });
  return { app, button: within(onTop('FF-15')).getByTestId('job-continue') };
}

describe('DEF-FLD-10586 — FF-15 Continue opens the next unfinished part (MQ-024)', () => {
  test('safety not passed → Continue — safety first → FF-16', async () => {
    const f = seedWO4822();
    const { app, button } = await continueOn(f);
    expect(button).toHaveTextContent('Continue — safety first');
    fireEvent.press(button);
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-16');
  });

  test('tasks left → Continue — step n of m → FF-17', async () => {
    const f = seedWO4822();
    safetyDone(f);
    const { app, button } = await continueOn(f);
    expect(button).toHaveTextContent('Continue — step 4 of 8');
    fireEvent.press(button);
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-17');
  });

  test('tasks done, a planned material not used → Continue — materials → FF-23', async () => {
    const f = seedWO4822();
    safetyDone(f);
    tasksDone(f);
    const { app, button } = await continueOn(f);
    expect(button).toHaveTextContent('Continue — materials');
    fireEvent.press(button);
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-23');
  });

  test('tasks and materials done, readings left → Continue — readings → FF-20', async () => {
    const f = seedWO4822();
    safetyDone(f);
    tasksDone(f);
    materialsDone(f);
    const { app, button } = await continueOn(f);
    expect(button).toHaveTextContent('Continue — readings');
    fireEvent.press(button);
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-20');
  });

  // The door this fix adds, named as the doors check reads it: 'FF-15 → FF-32'.
  test('FF-15 → FF-32: everything done → Finish — debrief, carrying the job', async () => {
    const f = seedWO4822();
    safetyDone(f);
    tasksDone(f);
    materialsDone(f);
    readingsDone(f);
    const { app, button } = await continueOn(f);
    expect(button).toHaveTextContent('Finish — debrief');
    fireEvent.press(button);
    const route = app.ref.getCurrentRoute();
    expect(route?.name).toBe('FF-32');
    expect(route?.params).toEqual(expect.objectContaining({ workOrderId: WO }));
  });

  test('a job with no materials and no readings goes from its last task straight to the debrief', async () => {
    const f = seedWO4822();
    const s = scoped(f.db, DANA);
    s.run(`DELETE FROM wo_item WHERE technician_id = :technician_id AND kind = 'material'`);
    s.run(`DELETE FROM wo_reading WHERE technician_id = :technician_id`);
    safetyDone(f);
    tasksDone(f);
    const { app, button } = await continueOn(f);
    expect(button).toHaveTextContent('Finish — debrief');
    fireEvent.press(button);
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-32');
  });

  test('a closed job (awaiting the office) → Closed, and the button does nothing', async () => {
    const f = seedWO4822();
    safetyDone(f);
    tasksDone(f);
    materialsDone(f);
    readingsDone(f);
    workOrderQ.markClosed(scoped(f.db, DANA), WO, local(11, 0).toISOString());
    const { app, button } = await continueOn(f);
    expect(button).toHaveTextContent('Closed');
    expect(button).toBeDisabled();
    fireEvent.press(button);
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-15');
  });
});
