/**
 * Every door of every job screen (FF-15…FF-24, FF-58…FF-60), pressed on the
 * real tree, and named as `'<from> → <to>'` — the hand-off
 * `tests/navigation/doors.test.tsx` checks for every BUILT screen (added in
 * the integration lane, when four waves landed together and the doors check
 * named 123 doors no wave test pressed).
 *
 * Each door is the control the screen draws with `testID="door-<to>"`; the
 * two that are acts rather than links are reached the way a technician
 * reaches them: FF-16's *Open tasks* is live only once every safety check is
 * ticked, and FF-58's *Hand back* only once a reason is chosen.
 *
 * Each screen is opened COLD (`tests/navigation/coldOpen.ts`): since the PO's
 * ruling of 2026-10-26 a back arrow goes back through history and follows its
 * drawn door only when there is none (DEF-FLD-10607), so the drawn door is
 * asserted in exactly that state. History is `backHistory.test.tsx`.
 */
import 'react-native-gesture-handler/jestSetup';

import { fireEvent, screen, within } from '@testing-library/react-native';

import type { ScreenId } from '../../../src/navigation/screens';
import { HAND_BACK_REASONS } from '../../../src/screens/theJob/HandBack';
import { coldOpen } from '../../navigation/coldOpen';
import { seedWO4822, WO } from './fixture';
import { mountJob, onTop } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./window').currentWindow(),
}));

type Door = `${ScreenId} → ${ScreenId}`;

/** Before the door can be pressed (an act, not a link). */
const SETUP: Partial<Record<Door, (from: ScreenId) => void>> = {
  'FF-16 → FF-17': (from) => {
    for (const row of within(onTop(from)).getAllByTestId(/^safety-(?!count|locked)/)) fireEvent.press(row);
  },
  'FF-58 → FF-10': (from) => {
    fireEvent.press(within(onTop(from)).getByTestId(`hand-back-${HAND_BACK_REASONS[0]}`));
  },
};

const DOORS: Door[] = [
  'FF-15 → FF-10',
  'FF-15 → FF-50',
  'FF-15 → FF-31',
  'FF-15 → FF-25',
  'FF-15 → FF-39',
  'FF-15 → FF-16',
  'FF-15 → FF-17',
  'FF-15 → FF-23',
  'FF-15 → FF-19',
  'FF-15 → FF-20',
  'FF-15 → FF-60',
  'FF-15 → FF-61',
  'FF-15 → FF-28',
  'FF-15 → FF-29',
  'FF-15 → FF-30',
  'FF-15 → FF-58',
  'FF-16 → FF-15',
  'FF-16 → FF-17',
  'FF-17 → FF-15',
  'FF-17 → FF-18',
  'FF-17 → FF-23',
  'FF-17 → FF-20',
  'FF-18 → FF-17',
  'FF-19 → FF-17',
  'FF-20 → FF-15',
  'FF-20 → FF-59',
  'FF-20 → FF-21',
  'FF-20 → FF-32',
  'FF-21 → FF-15',
  'FF-21 → FF-34',
  'FF-21 → FF-22',
  'FF-22 → FF-21',
  'FF-23 → FF-15',
  'FF-23 → FF-38',
  'FF-23 → FF-49',
  'FF-24 → FF-38',
  'FF-24 → FF-17',
  'FF-58 → FF-15',
  'FF-58 → FF-10',
  'FF-59 → FF-20',
  'FF-59 → FF-38',
  'FF-60 → FF-15',
];

test.each(DOORS)('%s', async (door) => {
  const [from, to] = door.split(' → ') as [ScreenId, ScreenId];
  const f = seedWO4822();
  const params = from === 'FF-15' ? { workOrderId: WO } : undefined;
  const app = await mountJob(f.services, from, { params });
  // Cold, so a back arrow's drawn door is where it goes (DEF-FLD-10607).
  await coldOpen(app.ref, from, params);
  SETUP[door]?.(from);
  const inScreen = within(onTop(from)).queryAllByTestId(`door-${to}`);
  const control = inScreen[0] ?? screen.getAllByTestId(`door-${to}`).at(-1);
  if (!control) throw new Error(`${door}: no control`);
  fireEvent.press(control);
  expect(`${from} → ${app.ref.getCurrentRoute()?.name}`).toBe(door);
  app.unmount();
});
