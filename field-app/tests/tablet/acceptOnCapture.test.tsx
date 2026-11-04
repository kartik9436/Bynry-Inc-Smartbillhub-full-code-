/**
 * DEF-FLD-10612 (beta MQ-027) on the tablet: work saved from the job's pane
 * frame — no Today card, no *Start* — queues the job's accept ahead of it,
 * because the accept now lives where every piece of work is saved
 * (`outbox.capture`), not on three phone buttons.
 *
 * Proved red before the fix: the outbox held the task tick alone.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, within } from '@testing-library/react-native';

import { scoped } from '../../src/db/scoped';
import { DANA } from '../screens/onSite/fixture';
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

test("a step ticked on the tablet's job frame of an unstarted job queues its accept first", async () => {
  const app = await mountTablet();
  // WO-4826 is on the list and not yet taken (no technician_acceptance).
  await app.open('FF-17', { workOrderId: 'wo-4826' });
  const frame = within(frameOf('FF-17'));
  await act(async () => {
    fireEvent.press(frame.getAllByTestId('task-t-26-1')[0]!);
  });
  await act(async () => {
    fireEvent.press(within(frameOf('FF-17')).getByTestId('task-mark-done'));
  });
  const kinds = scoped(app.db, DANA)
    .all<{ kind: string }>(`SELECT kind FROM outbox WHERE technician_id = :technician_id AND work_order_id = 'wo-4826' ORDER BY seq`)
    .map((r) => r.kind);
  expect(kinds[0]).toBe('job_accept');
  expect(kinds.filter((k) => k === 'job_accept')).toHaveLength(1);
  expect(kinds.length).toBeGreaterThan(1);
});
