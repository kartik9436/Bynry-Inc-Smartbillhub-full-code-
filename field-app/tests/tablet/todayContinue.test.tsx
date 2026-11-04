/**
 * DEF-FLD-10590 — the tablet's Today pane (FF-10 with the job beside it)
 * carries the same *Continue* as the phone's FF-15, and it must point at the
 * same NEXT UNFINISHED PART: safety → tasks → materials → readings →
 * *Finish — debrief* (FF-32). (A job closed on this device leaves Today's
 * list, so the pane never shows the *Closed* state; `nextPart` still owns it
 * and the phone's `continue.test.tsx` proves it.)
 *
 * Escape: the MQ-024 fix (DEF-FLD-10586) moved the phone's FF-15 onto
 * `nextPart.ts` and left this pane with its own inline copy of the old
 * safety-or-tasks logic, so with every task done it read *"Continue — step
 * 1 of 1"* and reopened the task list. The only tablet test of this button
 * (`t28Layouts`) accepts FF-16 or FF-17 from a part-way job.
 *
 * Proved red on the code before the fix (law 7): the materials, readings,
 * and debrief cases failed on *"Continue — step 1 of 1"*.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, within } from '@testing-library/react-native';

import * as woReadingQ from '../../src/db/queries/woReading';
import { scoped } from '../../src/db/scoped';
import { DANA, local } from '../screens/onSite/fixture';
import { frameOf, mountTablet, setWindow } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./harness').tabletWindow,
}));

beforeEach(() => setWindow(1024, 768));
afterEach(async () => {
  await act(async () => undefined);
});

const WO = 'wo-4822';
type App = Awaited<ReturnType<typeof mountTablet>>;

/** Safety ticked and every task done on WO-4822. */
function safetyAndTasksDone(app: App) {
  const s = scoped(app.db, DANA);
  s.run(`UPDATE wo_item SET state = 'ticked' WHERE technician_id = :technician_id AND work_order_id = '${WO}' AND kind = 'safety'`);
  s.run(`UPDATE wo_item SET state = 'done' WHERE technician_id = :technician_id AND work_order_id = '${WO}' AND kind = 'task'`);
}
function aPlannedMaterialShort(app: App) {
  scoped(app.db, DANA).run(
    `UPDATE wo_item SET detail = json_set(detail, '$.planned', 2, '$.used', 1) WHERE technician_id = :technician_id AND id = 'm-22-1'`,
  );
}
function readingsDone(app: App) {
  const s = scoped(app.db, DANA);
  const rows = s.all<{ id: string }>(`SELECT id FROM wo_reading WHERE technician_id = :technician_id AND work_order_id = '${WO}'`);
  for (const { id } of rows) {
    woReadingQ.recordValue(s, id, { value: '48500', unit: 'gal', flagged: false, unableToRead: false, capturedAt: local(20, 10) });
  }
}

/** Open Today, pick WO-4822, and hand back its Continue. */
async function continueOn(app: App) {
  await app.open('FF-10');
  fireEvent.press(within(frameOf('FF-10')).getByTestId(`job-${WO}-open`));
  await act(async () => undefined);
  const detail = within(frameOf('FF-10')).getByTestId('today-detail');
  return within(detail).getByTestId('today-detail-continue');
}

describe('DEF-FLD-10590 — the tablet Today pane Continue opens the next unfinished part', () => {
  test('tasks done, a planned material short → Continue — materials → FF-23', async () => {
    const app = await mountTablet();
    safetyAndTasksDone(app);
    aPlannedMaterialShort(app);
    const button = await continueOn(app);
    expect(button).toHaveTextContent('Continue — materials');
    fireEvent.press(button);
    expect(app.current()).toBe('FF-23');
    expect(app.ref.getCurrentRoute()?.params).toMatchObject({ workOrderId: WO });
  }, 120_000);

  test('tasks done, a reading left → Continue — readings → FF-20', async () => {
    const app = await mountTablet();
    safetyAndTasksDone(app);
    const button = await continueOn(app);
    expect(button).toHaveTextContent('Continue — readings');
    fireEvent.press(button);
    expect(app.current()).toBe('FF-20');
    expect(app.ref.getCurrentRoute()?.params).toMatchObject({ workOrderId: WO });
  }, 120_000);

  test('everything done → Finish — debrief → FF-32, carrying the job', async () => {
    const app = await mountTablet();
    safetyAndTasksDone(app);
    readingsDone(app);
    const button = await continueOn(app);
    expect(button).toHaveTextContent('Finish — debrief');
    fireEvent.press(button);
    expect(app.current()).toBe('FF-32');
    expect(app.ref.getCurrentRoute()?.params).toMatchObject({ workOrderId: WO });
  }, 120_000);
});
