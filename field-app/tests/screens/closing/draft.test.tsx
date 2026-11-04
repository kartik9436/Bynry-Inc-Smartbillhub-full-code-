/**
 * The close's typed debrief survives the app being killed (integration lane):
 * FF-32 keeps every keystroke in the handset's preferences, a fresh FF-32
 * opened with nothing but the job reads it back, FF-34 closes with it, and the
 * close clears it.
 */
import 'react-native-gesture-handler/jestSetup';

import { fireEvent, within } from '@testing-library/react-native';

import { MemoryKeyValueStore } from '../../../src/security/prefs';
import { loadDraft } from '../../../src/screens/closing/draft';
import { captured, DANA, makeWave, openScreen } from '../onSite/fixture';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

test('typed on FF-32, the app killed, FF-32 opened again: the words are still there', async () => {
  const w = makeWave();
  const prefs = new MemoryKeyValueStore();
  w.data.prefs = prefs;
  let app = await openScreen(w, 'FF-32', { workOrderId: 'wo-4822' });
  fireEvent.changeText(within(app.onTop()).getByTestId('problem-input'), 'Register seized');
  fireEvent.changeText(within(app.onTop()).getByTestId('what-i-did-input'), 'Replaced the meter');
  app.unmount(); // the app is killed: the route params are gone

  expect(loadDraft(prefs, DANA, 'wo-4822')?.debrief).toEqual({ problem: 'Register seized', done: 'Replaced the meter' });
  app = await openScreen(w, 'FF-32', { workOrderId: 'wo-4822' });
  expect(within(app.onTop()).getByTestId('problem-input').props.value).toBe('Register seized');
  expect(within(app.onTop()).getByTestId('what-i-did-input').props.value).toBe('Replaced the meter');
  app.unmount();
});

test('FF-34 opened with only the job closes with the kept debrief, then clears it', async () => {
  const w = makeWave();
  const prefs = new MemoryKeyValueStore();
  w.data.prefs = prefs;
  let app = await openScreen(w, 'FF-32', { workOrderId: 'wo-4824' });
  fireEvent.changeText(within(app.onTop()).getByTestId('problem-input'), 'Arrears');
  fireEvent.changeText(within(app.onTop()).getByTestId('what-i-did-input'), 'Valve closed');
  app.unmount(); // killed between the debrief and the close

  app = await openScreen(w, 'FF-34', { workOrderId: 'wo-4824' });
  fireEvent.press(within(app.onTop()).getByTestId('outcome-passed'));
  fireEvent.press(within(app.onTop()).getByTestId('close-job'));
  const close = captured(w.db).find((c) => c.kind === 'close');
  expect(close?.body).toMatchObject({ field_data: { problem_found: 'Arrears', what_i_did: 'Valve closed' } });
  expect(loadDraft(prefs, DANA, 'wo-4824')).toBeNull();
  app.unmount();
});
