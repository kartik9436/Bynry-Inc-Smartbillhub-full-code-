/**
 * The provider wires the two locks: five minutes away from the app, and
 * five minutes with no touch (Security tab §3 as amended 2026-10-26, MQ-019).
 * It read *"the app going to the background"* until then (DEF-FLD-10614).
 */
import { act, fireEvent, render, screen } from '@testing-library/react-native';
import { AppState, type AppStateStatus, Text } from 'react-native';

import { MINUTE_MS } from '../../src/security/clock';
import { IDLE_CHECK_MS, SessionProvider, useSession } from '../../src/session/SessionProvider';
import { withSystemInteraction } from '../../src/session/systemInteraction';
import { makeHandset, signIn } from './fakes';

function Phase() {
  const { snapshot } = useSession();
  return <Text testID="phase">{snapshot.phase}</Text>;
}

let handler: ((s: AppStateStatus) => void) | undefined;
let spy: jest.SpyInstance;

beforeEach(() => {
  handler = undefined;
  // React Native's own test mock answers addEventListener with nothing; this
  // stands in for the platform and keeps the listener so a test can fire it.
  spy = jest.spyOn(AppState, 'addEventListener').mockImplementation((_type, h) => {
    handler = h as (s: AppStateStatus) => void;
    return { remove: () => undefined } as ReturnType<typeof AppState.addEventListener>;
  });
});

afterEach(() => spy.mockRestore());

test('backgrounding no longer locks at once; five minutes away locks on return (MQ-019)', async () => {
  const h = makeHandset();
  await signIn(h.session, 'd.ortiz');
  render(
    <SessionProvider manager={h.session}>
      <Phase />
    </SessionProvider>,
  );
  expect(screen.getByTestId('phase')).toHaveTextContent('unlocked');
  act(() => handler?.('background'));
  expect(screen.getByTestId('phase')).toHaveTextContent('unlocked');
  h.clock.advance(2 * MINUTE_MS);
  act(() => handler?.('active'));
  expect(screen.getByTestId('phase')).toHaveTextContent('unlocked');
  act(() => handler?.('inactive'));
  h.clock.advance(6 * MINUTE_MS);
  act(() => handler?.('active'));
  expect(screen.getByTestId('phase')).toHaveTextContent('locked');
});

test("the app's own permission dialog reported as background never locks", async () => {
  const h = makeHandset();
  await signIn(h.session, 'd.ortiz');
  render(
    <SessionProvider manager={h.session}>
      <Phase />
    </SessionProvider>,
  );
  let answer!: (v: string) => void;
  let asked!: Promise<string>;
  act(() => {
    asked = withSystemInteraction(() => new Promise<string>((r) => (answer = r)));
  });
  act(() => handler?.('background'));
  h.clock.advance(6 * MINUTE_MS);
  await act(async () => {
    answer('denied');
    await asked;
  });
  act(() => handler?.('active'));
  expect(screen.getByTestId('phase')).toHaveTextContent('unlocked');
});

test('five minutes with no touch locks; a touch keeps it open', async () => {
  jest.useFakeTimers();
  const h = makeHandset();
  await signIn(h.session, 'd.ortiz');
  render(
    <SessionProvider manager={h.session}>
      <Phase />
    </SessionProvider>,
  );
  // Four minutes, a touch, four more: still open.
  h.clock.advance(4 * MINUTE_MS);
  fireEvent(screen.getByTestId('session-activity-root'), 'touchStart');
  h.clock.advance(4 * MINUTE_MS);
  act(() => jest.advanceTimersByTime(IDLE_CHECK_MS));
  expect(screen.getByTestId('phase')).toHaveTextContent('unlocked');
  // One more minute and the next check locks it.
  h.clock.advance(1 * MINUTE_MS + 1);
  act(() => jest.advanceTimersByTime(IDLE_CHECK_MS));
  expect(screen.getByTestId('phase')).toHaveTextContent('locked');
  jest.useRealTimers();
});
