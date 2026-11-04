/**
 * DEF-FLD-10611 (MQ-021): with the keyboard open, ONE tap on Save records the
 * reading. Before the fix the first tap only closed the keyboard — FF-20's
 * body is `JobScreen`'s ScrollView, which did not persist taps — and the
 * reporter needed a second (2 of 2 tries).
 *
 * The tap goes through `tapWithKeyboardUp` (`tests/components/keyboard.ts`),
 * which delivers it the way React Native does with the keyboard up; a bare
 * `fireEvent.press` reaches the button whatever the frame says, which is
 * exactly how this escaped.
 *
 * Tasks' *Mark done* (FF-17) has no note field to focus, so the second case
 * is the note FF-20 does have: *Unable to read* with its note typed.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, waitFor, within } from '@testing-library/react-native';

import * as woReadingQ from '../../../src/db/queries/woReading';
import { scoped } from '../../../src/db/scoped';
import { tapWithKeyboardUp } from '../../components/keyboard';
import { DANA, seedWO4822, WO } from './fixture';
import { mountJob, onTop } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./window').currentWindow(),
}));

const reading = (f: ReturnType<typeof seedWO4822>, id: string) => woReadingQ.listForOrder(scoped(f.db, DANA), WO).find((r) => r.id === id);

test('FF-20: the field focused, one tap on Save records the reading — 1 of 3 becomes 2 of 3', async () => {
  const f = seedWO4822();
  await mountJob(f.services, 'FF-20');
  const top = () => within(onTop('FF-20'));
  const card = () => within(top().getByTestId('reading-r-master'));
  await act(async () => {
    fireEvent.press(card().getByTestId('reading-r-master-photo'));
  });
  await waitFor(() => expect(card().queryByTestId('reading-r-master-photo-required')).toBeNull());
  expect(top().getByTestId('readings-count')).toHaveTextContent('1 of 3');

  const field = card().getByLabelText('Closing read');
  fireEvent(field, 'focus');
  fireEvent.changeText(field, '48200');
  expect(tapWithKeyboardUp(card().getByTestId('reading-r-master-save'))).toBe('pressed');

  expect(reading(f, 'r-master')?.value).toBe('48200');
  expect(top().getByTestId('readings-count')).toHaveTextContent('2 of 3');
});

test('FF-20: Unable to read with the note focused — one tap on Record records it', async () => {
  const f = seedWO4822();
  await mountJob(f.services, 'FF-20');
  const card = () => within(within(onTop('FF-20')).getByTestId('reading-r-sub-b'));
  fireEvent.press(card().getByTestId('reading-r-sub-b-unable'));
  const note = card().getByTestId('reading-r-sub-b-note');
  fireEvent(note, 'focus');
  fireEvent.changeText(note, 'Gate locked');
  expect(tapWithKeyboardUp(card().getByTestId('reading-r-sub-b-unable-record'))).toBe('pressed');
  expect(reading(f, 'r-sub-b')?.unable_to_read).toBe(1);
});
