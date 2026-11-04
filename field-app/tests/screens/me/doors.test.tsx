/**
 * Every door of every "me" screen (FF-42…FF-55), pressed on the real tree and
 * named as `'<from> → <to>'` — the hand-off `tests/navigation/doors.test.tsx`
 * checks for every BUILT screen (added in the integration lane, when four
 * waves landed together and the doors check named doors no wave test
 * pressed).
 *
 * A door to FF-09 is the menu: pressing it opens the drawer, read from the
 * navigation state itself. FF-53's two acts are their own tests below.
 *
 * Each screen is opened COLD (`tests/navigation/coldOpen.ts`): a back arrow
 * goes back through history and follows its drawn door only when there is
 * none (DEF-FLD-10607, PO 2026-10-26), so the drawn door is asserted there.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';

import type { ScreenId } from '../../../src/navigation/screens';
import { coldOpen } from '../../navigation/coldOpen';
import { makeFixture, openScreen } from './support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

type Door = `${ScreenId} → ${ScreenId}`;
type App = Awaited<ReturnType<typeof openScreen>>;

const onTop = (id: ScreenId) => {
  const el = screen.getAllByTestId(`screen-${id}`).at(-1);
  if (!el) throw new Error(`${id} is not mounted`);
  return el;
};
const drawerOpen = (app: App) => JSON.stringify(app.ref.getRootState()).includes('"status":"open"');

const DOORS: Door[] = [
  'FF-42 → FF-09',
  'FF-42 → FF-43',
  'FF-42 → FF-10',
  'FF-43 → FF-42',
  'FF-44 → FF-09',
  'FF-44 → FF-45',
  'FF-44 → FF-46',
  'FF-44 → FF-50',
  'FF-44 → FF-47',
  'FF-44 → FF-51',
  'FF-45 → FF-44',
  'FF-46 → FF-44',
  'FF-47 → FF-44',
  'FF-48 → FF-09',
  'FF-48 → FF-47',
  'FF-49 → FF-09',
  'FF-49 → FF-38',
  'FF-50 → FF-10',
  'FF-50 → FF-08',
  'FF-51 → FF-44',
  'FF-51 → FF-54',
  'FF-51 → FF-55',
  'FF-51 → RW-29',
  'FF-51 → FF-52',
  'FF-51 → FF-50',
  'FF-51 → FF-07',
  'FF-51 → FF-53',
  'FF-52 → FF-51',
  'FF-53 → SWITCH',
  'FF-54 → FF-15',
  'FF-54 → FF-25',
  'FF-54 → FF-20',
  'FF-54 → FF-17',
  'FF-54 → FF-21',
  'FF-54 → FF-34',
  'FF-55 → FF-15',
  'FF-55 → FF-25',
  'FF-55 → FF-17',
  'FF-55 → FF-20',
  'FF-55 → FF-21',
  'FF-55 → FF-34',
];

test.each(DOORS)('%s', async (door) => {
  const [from, to] = door.split(' → ') as [ScreenId, ScreenId];
  const app = await openScreen(from, makeFixture());
  // Cold, so a back arrow's drawn door is where it goes (DEF-FLD-10607).
  await coldOpen(app.ref, from);
  const inScreen = within(onTop(from)).queryAllByTestId(`door-${to}`);
  const control = inScreen[0] ?? screen.getAllByTestId(`door-${to}`).at(-1);
  if (!control) throw new Error(`${door}: no control`);
  fireEvent.press(control);
  if (to === 'FF-09') {
    expect(drawerOpen(app) ? door : `${from} → menu closed`).toBe(door);
  } else {
    expect(`${from} → ${app.ref.getCurrentRoute()?.name}`).toBe(door);
  }
  app.unmount();
});

describe('FF-53 Sign out, its two acts', () => {
  test("'FF-53 → FF-05' Sign out anyway ends the session and the gate asks for a password", async () => {
    const app = await openScreen('FF-53', makeFixture());
    await act(async () => {
      fireEvent.press(within(onTop('FF-53')).getByTestId('door-FF-05'));
    });
    // The splash (FF-01) moves on by itself, to sign-in on a handset somebody has used.
    await waitFor(() => expect(`FF-53 → ${app.ref.getCurrentRoute()?.name}`).toBe('FF-53 → FF-05'), { timeout: 5000 });
    app.unmount();
  });

  test("'FF-53 → FF-09' Stay signed in returns to the menu it was opened from", async () => {
    const app = await openScreen('FF-63', makeFixture());
    await act(async () => {
      fireEvent.press(screen.getAllByTestId('open-menu').at(-1)!);
    });
    await act(async () => {
      fireEvent.press(screen.getAllByTestId('menu-FF-53').at(-1)!);
    });
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-53');
    await act(async () => {
      fireEvent.press(within(onTop('FF-53')).getByTestId('door-FF-09'));
    });
    expect(drawerOpen(app) ? 'FF-53 → FF-09' : `FF-53 → ${app.ref.getCurrentRoute()?.name}, menu closed`).toBe('FF-53 → FF-09');
    app.unmount();
  });
});
