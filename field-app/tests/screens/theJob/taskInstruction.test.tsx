/**
 * DEF-FLD-10587 (beta MQ-030) — FF-17: the OPEN task card shows the
 * template's instruction as a second line under the title (decision log
 * 2026-10-04, *"A task's instruction (PO answer 3) is a SECOND LINE under the
 * task"*), verbatim and whole. A done card stays title-only as drawn; a step
 * with no instruction (a field-added one, or a template step with none) draws
 * no empty line.
 *
 * The instruction arrives the way it does in the field — through the job
 * bundle (`applyBundle`) — so this is sync-to-screen, not a seeded detail.
 *
 * Proved red (law 7): before the fix (b) failed — `Unable to find an element
 * with testID: task-instruction` — and (d) with it.
 */
import 'react-native-gesture-handler/jestSetup';

import { fireEvent, within } from '@testing-library/react-native';

import { tickSafety } from '../../../src/screens/theJob/actions';
import { applyBundle } from '../../../src/sync/extras';
import type { WireBundle } from '../../../src/sync/fieldApi';
import { DANA, local, seedWO4822, WO } from './fixture';
import { mountJob, onTop } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./window').currentWindow(),
}));

const LID = 'Compare the ID stamped on the lid with the work order. If it does not match, stop and call dispatch.';
const LEAKS = 'Open the main a quarter turn at a time. Watch every joint for one full minute before the next quarter.';

function seeded() {
  const f = seedWO4822();
  for (const id of ['safety-1', 'safety-2', 'safety-3', 'safety-4']) tickSafety(f.port(), WO, id);
  const bundle = {
    order_id: WO,
    order_no: 'WO-4822',
    template_id: 'tpl-ex',
    template_version: 3,
    safety: [],
    tasks: [
      { id: 'task-4', seq: 4, title: 'Fit new meter and seal', instruction: LID, is_mandatory: true },
      { id: 'task-6', seq: 6, title: 'Open main and check for leaks', instruction: LEAKS },
      { id: 'task-7', seq: 7, title: 'Record opening read', instruction: '' },
    ],
    readings: [],
    materials: [],
  } as unknown as WireBundle;
  applyBundle(f.db, DANA, bundle, local(10, 0));
  return f;
}

describe('FF-17 — the task instruction is a second line on the open card (MQ-030)', () => {
  test('(b) the open card shows the instruction verbatim; done cards never do', async () => {
    const f = seeded();
    await mountJob(f.services, 'FF-17');
    const top = within(onTop('FF-17'));
    const step = within(top.getByTestId('task-task-4'));
    expect(step.getByTestId('task-instruction')).toHaveTextContent(LID);
    // the text is the utility's own, once, and only on the open card
    expect(top.getAllByText(LID)).toHaveLength(1);
    expect(within(top.getByTestId('task-task-6')).queryByText(LEAKS)).toBeNull();
  });

  test('(c) a step with no instruction draws no empty line', async () => {
    const f = seeded();
    await mountJob(f.services, 'FF-17');
    const top = () => within(onTop('FF-17'));
    fireEvent.press(within(top().getByTestId('task-task-4')).getByTestId('task-mark-done'));
    // task-5 was added in the field: it has none
    const five = within(top().getByTestId('task-task-5'));
    expect(five.getByTestId('task-mark-done')).toBeTruthy();
    expect(five.queryByTestId('task-instruction')).toBeNull();
    // and a blank instruction from the template stores and draws nothing either
    fireEvent.press(within(top().getByTestId('task-task-7')).getByText('Record opening read'));
    expect(within(top().getByTestId('task-task-7')).queryByTestId('task-instruction')).toBeNull();
  });

  test('(d) once a task is done, the next task opens with its own instruction', async () => {
    const f = seeded();
    await mountJob(f.services, 'FF-17');
    const top = () => within(onTop('FF-17'));
    fireEvent.press(within(top().getByTestId('task-task-4')).getByTestId('task-mark-done'));
    fireEvent.press(within(top().getByTestId('task-task-5')).getByTestId('task-mark-done'));
    expect(within(top().getByTestId('task-task-6')).getByTestId('task-instruction')).toHaveTextContent(LEAKS);
    expect(top().queryByText(LID)).toBeNull();
  });
});
