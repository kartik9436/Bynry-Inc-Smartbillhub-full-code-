/**
 * DEF-FLD-10607 — THE BACK ARROW GOES WHERE YOU CAME FROM (PO 2026-10-26,
 * *"A for back button"*). Every header back arrow pops back through history;
 * the drawn destination is followed only when there is no history (a
 * notification or a cold link), carrying the job; the phone's own back does
 * the same as the arrow; the arrow's spoken label names where it really goes.
 *
 * Escape: a build lane decided *"back is a DOOR to the screen the drawing's
 * arrow names, not 'go back'"* without putting it to the PO, and the doors
 * tests pressed `door-<drawn>` and asserted the drawn target — so they held
 * the undecided judgment in place.
 *
 * Proved red on the code before the fix (law 7) — quoted in the fix commit.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';
import { BackHandler } from 'react-native';

import { FRAME, SHELL } from '../../../src/navigation/routing';
import { seedWO4822, WO } from './fixture';
import { coldOpen } from '../../navigation/coldOpen';
import { go, mountJob, onTop } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native/Libraries/Utilities/BackHandler', () => ({
  __esModule: true,
  default: require('react-native/Libraries/Utilities/__mocks__/BackHandler'),
}));
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./window').currentWindow(),
}));

afterEach(async () => {
  await act(async () => undefined);
});

type Ref = Awaited<ReturnType<typeof mountJob>>['ref'];

function shellRoutes(ref: Ref): string[] {
  const frame = ref.getRootState()?.routes.find((r) => r.name === FRAME)?.state as { routes: Array<{ name: string; state?: unknown }> } | undefined;
  const shell = frame?.routes.find((r) => r.name === SHELL)?.state as { routes: Array<{ name: string }> } | undefined;
  return shell?.routes.map((r) => r.name) ?? [];
}

function hardwareBack() {
  (BackHandler as unknown as { mockPressBack: () => void }).mockPressBack();
}

test('FF-15 → Tasks → back is FF-15, the same one, and the arrow says so', async () => {
  const f = seedWO4822();
  const app = await mountJob(f.services, 'FF-15', { params: { workOrderId: WO } });
  const job = onTop('FF-15');
  await act(async () => {
    fireEvent.press(within(job).getByTestId('door-FF-17'));
  });
  expect(app.ref.getCurrentRoute()?.name).toBe('FF-17');
  const arrow = within(onTop('FF-17')).getByTestId('door-FF-15');
  expect(arrow.props.accessibilityLabel).toBe('Back to Job');
  await act(async () => {
    fireEvent.press(arrow);
  });
  expect(app.ref.getCurrentRoute()?.name).toBe('FF-15');
  // Popped, not pushed: the stack is the tabs and the job, and it is the same FF-15.
  expect(shellRoutes(app.ref)).toEqual(['Tabs', 'FF-15']);
  expect(onTop('FF-15')).toBe(job);
  app.unmount();
});

test('back from a job screen opened from Home goes to Home, not to the drawn job overview', async () => {
  const f = seedWO4822();
  const app = await mountJob(f.services, 'FF-16', { params: { workOrderId: WO } });
  const arrow = within(onTop('FF-16')).getByTestId('door-FF-15');
  expect(arrow.props.accessibilityLabel).toBe('Back to Home');
  await act(async () => {
    fireEvent.press(arrow);
  });
  expect(app.ref.getCurrentRoute()?.name).toBe('FF-63');
  app.unmount();
});

test('cold open of Safety (no history): the arrow follows the drawn door, FF-15, with the job', async () => {
  const f = seedWO4822();
  const app = await mountJob(f.services, 'FF-63', { openJob: null });
  await coldOpen(app.ref, 'FF-16', { workOrderId: WO });
  expect(shellRoutes(app.ref)).toEqual(['FF-16']);
  const arrow = within(onTop('FF-16')).getByTestId('door-FF-15');
  expect(arrow.props.accessibilityLabel).toBe('Back to the job');
  await act(async () => {
    fireEvent.press(arrow);
  });
  expect(app.ref.getCurrentRoute()?.name).toBe('FF-15');
  expect(app.ref.getCurrentRoute()?.params).toEqual(expect.objectContaining({ workOrderId: WO }));
  app.unmount();
});

test('the phone’s own back matches the arrow — with history, and cold', async () => {
  const f = seedWO4822();
  const app = await mountJob(f.services, 'FF-15', { params: { workOrderId: WO } });
  await go(app.ref, 'FF-17', { workOrderId: WO });
  await act(async () => {
    hardwareBack();
  });
  expect(app.ref.getCurrentRoute()?.name).toBe('FF-15');

  await coldOpen(app.ref, 'FF-16', { workOrderId: WO });
  await act(async () => {
    hardwareBack();
  });
  expect(app.ref.getCurrentRoute()?.name).toBe('FF-15');
  expect(app.ref.getCurrentRoute()?.params).toEqual(expect.objectContaining({ workOrderId: WO }));
  expect((BackHandler as unknown as { exitApp: jest.Mock }).exitApp).not.toHaveBeenCalled();
  app.unmount();
});

test('an on-site arrow (BOARD_HEADER) follows history too, and falls back to its drawn door cold', async () => {
  const f = seedWO4822();
  const app = await mountJob(f.services, 'FF-15', { params: { workOrderId: WO } });
  await go(app.ref, 'FF-17', { workOrderId: WO });
  await go(app.ref, 'FF-30', { workOrderId: WO });
  const arrow = screen.getAllByTestId('door-FF-15').at(-1)!;
  expect(arrow.props.accessibilityLabel).toBe('Back to Tasks');
  await act(async () => {
    fireEvent.press(arrow);
  });
  expect(app.ref.getCurrentRoute()?.name).toBe('FF-17');

  await coldOpen(app.ref, 'FF-30', { workOrderId: WO });
  await act(async () => {
    fireEvent.press(screen.getAllByTestId('door-FF-15').at(-1)!);
  });
  expect(app.ref.getCurrentRoute()?.name).toBe('FF-15');
  expect(app.ref.getCurrentRoute()?.params).toEqual(expect.objectContaining({ workOrderId: WO }));
  app.unmount();
});

test('a door to a screen already on the stack pops back to it — no second copy to walk back through', async () => {
  const f = seedWO4822();
  const app = await mountJob(f.services, 'FF-15', { params: { workOrderId: WO } });
  await go(app.ref, 'FF-17', { workOrderId: WO });
  await go(app.ref, 'FF-23', { workOrderId: WO });
  // A door (not the arrow) to the job, from two screens deep.
  await go(app.ref, 'FF-15', { workOrderId: WO });
  expect(shellRoutes(app.ref)).toEqual(['Tabs', 'FF-15']);
  // A door to Today from inside the job is the SAME tabs route, not a second one.
  await go(app.ref, 'FF-10');
  expect(shellRoutes(app.ref)).toEqual(['Tabs']);
  app.unmount();
});
