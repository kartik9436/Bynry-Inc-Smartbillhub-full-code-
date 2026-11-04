/**
 * The getting-in screens that sit behind the sign-in: FF-07 Permissions,
 * FF-08 First sync, the lock cover's unlock form, and FF-09 the menu brought
 * to its board.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import { engineFirstSync, type FirstSyncPort } from '../../../src/screens/gettingIn/firstSync';
import type { PermissionsPort } from '../../../src/screens/gettingIn/permissions';
import { makeHandset } from '../../session/fakes';
import { assertTouchTargets, current, mountDay, open } from '../theDay/support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

function permissions(states: Partial<Record<'location' | 'camera' | 'notifications', 'granted' | 'denied' | 'unknown'>>): PermissionsPort & { opened: number } {
  const port = {
    opened: 0,
    canRequest: true,
    status: async (k: 'location' | 'camera' | 'notifications') => states[k] ?? 'unknown',
    request: async () => 'granted' as const,
    openSettings: async () => {
      port.opened += 1;
    },
  };
  return port;
}

describe('FF-07 Permissions', () => {
  test('ALLOWED only for what the platform said; notifications off is the red card with Open settings', async () => {
    const port = permissions({ location: 'granted', camera: 'granted', notifications: 'denied' });
    const app = await mountDay({ gettingIn: { permissions: port } });
    await open(app, 'FF-07');
    expect(await screen.findByTestId('permission-location-allowed')).toHaveTextContent('Allowed');
    expect(screen.getByTestId('permission-camera-allowed')).toBeTruthy();
    expect(screen.getByTestId('permission-notifications-off')).toHaveTextContent('Off. You will miss emergencies.');
    fireEvent.press(screen.getByTestId('permission-notifications-settings'));
    expect(port.opened).toBe(1);
    app.unmount();
  });

  test('with no permission package installed, nothing reads ALLOWED — each says Not checked', async () => {
    const app = await mountDay();
    await open(app, 'FF-07');
    await screen.findByTestId('screen-FF-07');
    expect(await screen.findByTestId('permission-location-unknown')).toHaveTextContent('Not checked');
    expect(screen.queryByText('Allowed')).toBeNull();
    app.unmount();
  });

  test("'FF-07 → FF-08' Continue never waits on a permission", async () => {
    const app = await mountDay();
    await open(app, 'FF-07');
    fireEvent.press(await screen.findByTestId('door-FF-08'));
    expect(`FF-07 → ${current(app)}`).toBe('FF-07 → FF-08');
    app.unmount();
  });

  test('every control is named and at least 48pt', async () => {
    const app = await mountDay({ gettingIn: { permissions: permissions({ notifications: 'denied' }) } });
    await open(app, 'FF-07');
    const root = await screen.findByTestId('screen-FF-07');
    await screen.findByTestId('permission-notifications-off');
    expect(assertTouchTargets(within(root).getAllByRole('button'))).toBe(4);
    app.unmount();
  });
});

describe('FF-08 First sync', () => {
  test('a part with no feed says Not available and is left out of the percentage; Open my day waits for 100%', async () => {
    let finish: () => void = () => undefined;
    const port: FirstSyncPort = engineFirstSync(
      () =>
        new Promise((resolve) => {
          finish = () => resolve({ pull: { upserts: 11 }, pullError: null });
        }),
    );
    const app = await mountDay({ fieldData: { firstSync: port } });
    await open(app, 'FF-08');
    await screen.findByTestId('screen-FF-08');
    expect(screen.getByTestId('door-FF-10')).toBeDisabled();
    expect(screen.getByTestId('first-sync-documents').props.accessibilityLabel).toBe('Safety documents, Not available, Not available');
    expect(screen.getByTestId('first-sync-percent')).toHaveTextContent(/^0%/);
    await act(async () => {
      finish();
    });
    expect(screen.getByTestId('first-sync-percent')).toHaveTextContent(/^100%/);
    expect(screen.getByTestId('first-sync-jobs').props.accessibilityLabel).toBe('Jobs and checklists, Done, Done');
    expect(screen.getByTestId('door-FF-10')).not.toBeDisabled();
    fireEvent.press(screen.getByTestId('door-FF-10'));
    expect(`FF-08 → ${current(app)}`).toBe('FF-08 → FF-10');
    app.unmount();
  });

  test('with no loader wired it says the day cannot load yet — no moving bar over nothing — and Skip still opens the day', async () => {
    const app = await mountDay();
    await open(app, 'FF-08');
    expect(await screen.findByTestId('first-sync-not-wired')).toHaveTextContent('Your day cannot load yet.');
    expect(screen.queryByTestId('first-sync-bar')).toBeNull();
    fireEvent.press(screen.getByTestId('first-sync-skip'));
    expect(current(app)).toBe('FF-10');
    app.unmount();
  });
});

describe('the lock cover', () => {
  test('locked: the cover has its unlock form; a wrong password says so, the right one returns to the same place', async () => {
    const app = await mountDay();
    await open(app, 'FF-10');
    await act(async () => {
      app.handset.session.lock();
    });
    const cover = within(screen.getByTestId('lock-cover'));
    expect(cover.getByTestId('lock-name')).toHaveTextContent('D. Ortiz');
    fireEvent.changeText(cover.getByTestId('lock-password-input'), 'wrong');
    await act(async () => {
      fireEvent.press(cover.getByTestId('lock-unlock'));
    });
    expect(cover.getByTestId('lock-error')).toHaveTextContent('Wrong email, phone or password.');
    fireEvent.changeText(cover.getByTestId('lock-password-input'), 'valley-day-0730');
    await act(async () => {
      fireEvent.press(cover.getByTestId('lock-unlock'));
    });
    expect(screen.queryByTestId('lock-cover')).toBeNull();
    expect(current(app)).toBe('FF-10');
    app.unmount();
  });

  test('a fingerprint returns you to your OWN session', async () => {
    const handset = makeHandset();
    const app = await mountDay({ handset });
    await act(async () => {
      handset.session.lock();
    });
    await act(async () => {
      fireEvent.press(screen.getByTestId('lock-biometric'));
    });
    expect(screen.queryByTestId('lock-cover')).toBeNull();
    app.unmount();
  });

  test('with no biometric on the phone it says use your password, and the button goes', async () => {
    const handset = makeHandset();
    handset.biometric.available = false;
    const app = await mountDay({ handset });
    await act(async () => {
      handset.session.lock();
    });
    await act(async () => {
      fireEvent.press(screen.getByTestId('lock-biometric'));
    });
    expect(screen.getByTestId('lock-error')).toHaveTextContent('Use your password.');
    expect(screen.queryByTestId('lock-biometric')).toBeNull();
    expect(screen.getByTestId('lock-cover')).toBeTruthy();
    app.unmount();
  });
});

describe('FF-09 the menu, brought to its board', () => {
  test('counted figures where the handset holds the rows: Today 4, My routes 4 left; the version at the foot', async () => {
    const app = await mountDay({ status: { syncPending: 2, connection: 'online', availability: 'available' } });
    const drawer = within(screen.getByTestId('menu-drawer'));
    expect(drawer.getByTestId('menu-FF-10-count')).toHaveTextContent('4');
    expect(drawer.getByTestId('menu-RW-01-count')).toHaveTextContent('4 left');
    // Counts the handset cannot make are not drawn — never a zero.
    expect(drawer.queryByTestId('menu-FF-35-count')).toBeNull();
    expect(drawer.queryByTestId('menu-FF-42-count')).toBeNull();
    fireEvent.press(drawer.getByTestId('menu-availability'));
    expect(current(app)).toBe('FF-45');
    app.unmount();
  });

  test('every control is named and at least 48pt', async () => {
    const app = await mountDay();
    const drawer = screen.getByTestId('menu-drawer');
    expect(assertTouchTargets(within(drawer).getAllByRole('button'))).toBeGreaterThanOrEqual(17);
    app.unmount();
  });
});
