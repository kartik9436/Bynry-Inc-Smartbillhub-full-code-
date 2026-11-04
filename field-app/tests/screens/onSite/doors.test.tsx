/**
 * The doors of the on-site, closing and raise screens (FF-25…FF-41, FF-61,
 * FF-62), pressed on the real tree and named as `'<from> → <to>'` — the
 * hand-off `tests/navigation/doors.test.tsx` checks for every BUILT screen
 * (added in the integration lane, when four waves landed together and the
 * doors check named the doors no wave test pressed).
 *
 * Here: every door that is a control drawn with `testID="door-<to>"` —
 * including the header's back arrow and menu (`BOARD_HEADER` in
 * `screens/onSite/common.tsx`). Each screen is opened COLD
 * (`tests/navigation/coldOpen.ts`): since the PO's ruling of 2026-10-26 the
 * arrow goes back through history and follows the board's drawn door only
 * when there is none (DEF-FLD-10607), so that is the state the drawn door is
 * asserted in; history is `tests/screens/theJob/backHistory.test.tsx`. The
 * doors that are ACTS — sign,
 * close, disconnect, reconnect, scan, search, pick — are pressed and named in
 * the wave tests that set up their act (`customerMoney`, `closing`, `raise`).
 */
import 'react-native-gesture-handler/jestSetup';

import { fireEvent, screen, within } from '@testing-library/react-native';

import * as closedQ from '../../../src/db/queries/workOrderClosed';
import { scoped } from '../../../src/db/scoped';
import type { ScreenId } from '../../../src/navigation/screens';
import { coldOpen } from '../../navigation/coldOpen';
import { current, DANA, local, makeWave, openScreen } from './fixture';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

type Door = `${ScreenId} → ${ScreenId}`;
/** What each screen is opened with (the same as the wave's sweep). */
const W = { workOrderId: 'wo-4822' };
const PARAMS = new Map<ScreenId, Record<string, unknown> | undefined>([
  ['FF-25', W],
  ['FF-26', { workOrderId: 'wo-4826' }],
  ['FF-27', { workOrderId: 'wo-4824' }],
  ['FF-28', W],
  ['FF-29', W],
  ['FF-30', W],
  ['FF-31', W],
  ['FF-32', W],
  ['FF-36', W],
  ['FF-37', { carriedFrom: 'wo-4824', templateId: 'tpl-leak' }],
  ['FF-38', W],
  ['FF-39', { assetId: 'a-4471' }],
  ['FF-40', { assetId: 'a-4471' }],
  ['FF-62', { carriedFrom: 'wo-4824' }],
]);

const DOORS: Door[] = [
  'FF-25 → FF-15',
  'FF-25 → FF-26',
  'FF-25 → FF-27',
  'FF-26 → FF-15',
  'FF-26 → FF-17',
  'FF-27 → FF-10',
  'FF-28 → FF-15',
  'FF-29 → FF-15',
  'FF-30 → FF-15',
  'FF-31 → FF-15',
  'FF-31 → FF-30',
  'FF-32 → FF-17',
  'FF-32 → FF-24',
  'FF-32 → FF-33',
  'FF-35 → FF-09',
  'FF-36 → FF-35',
  'FF-36 → FF-15',
  'FF-37 → FF-35',
  'FF-37 → FF-62',
  'FF-38 → FF-15',
  'FF-39 → FF-15',
  'FF-39 → FF-41',
  'FF-39 → FF-38',
  'FF-39 → FF-40',
  'FF-40 → FF-39',
  'FF-41 → FF-09',
  'FF-41 → FF-38',
  'FF-62 → FF-15',
];

test.each(DOORS)('%s', async (door) => {
  const [from, to] = door.split(' → ') as [ScreenId, ScreenId];
  const app = await openScreen(makeWave(), from, PARAMS.get(from));
  await coldOpen(app.ref, from, PARAMS.get(from));
  const inScreen = within(app.onTop()).queryAllByTestId(`door-${to}`);
  const control = inScreen[0] ?? screen.getAllByTestId(`door-${to}`).at(-1);
  if (!control) throw new Error(`${door}: no control`);
  fireEvent.press(control);
  if (to === 'FF-09') {
    const open = JSON.stringify(app.ref.getRootState()).includes('"status":"open"');
    expect(open ? door : `${from} → menu closed`).toBe(door);
  } else {
    expect(`${from} → ${current(app.ref).name}`).toBe(door);
  }
  app.unmount();
});

test('opened cold, the back arrow carries the job, and the meter back to the meter', async () => {
  let app = await openScreen(makeWave(), 'FF-26', { workOrderId: 'wo-4826' });
  await coldOpen(app.ref, 'FF-26', { workOrderId: 'wo-4826' });
  fireEvent.press(screen.getAllByTestId('door-FF-15').at(-1)!);
  expect(current(app.ref)).toEqual({ name: 'FF-15', params: { workOrderId: 'wo-4826' } });
  app.unmount();
  app = await openScreen(makeWave(), 'FF-40', { assetId: 'a-4471' });
  await coldOpen(app.ref, 'FF-40', { assetId: 'a-4471' });
  fireEvent.press(screen.getAllByTestId('door-FF-39').at(-1)!);
  expect(current(app.ref)).toEqual({ name: 'FF-39', params: { assetId: 'a-4471' } });
  app.unmount();
});

test("'FF-35 → FF-36' Reopen on a closed job opens the reopen sheet for that job", async () => {
  const w = makeWave();
  closedQ.recordClose(scoped(w.db, DANA), 'wo-4822', 'passed', local(20, 9, 58));
  const app = await openScreen(w, 'FF-35');
  fireEvent.press(within(app.onTop()).getByTestId('reopen-WO-4822'));
  expect(`FF-35 → ${current(app.ref).name}`).toBe('FF-35 → FF-36');
  expect(current(app.ref).params).toEqual({ workOrderId: 'wo-4822' });
  app.unmount();
});
