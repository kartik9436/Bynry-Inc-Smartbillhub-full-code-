/**
 * T-13 — the frame as mounted: three bottom tabs on a phone, the permanent
 * 220px sidebar on a tablet, the status strip on every framed screen, the
 * gate when nobody is signed in, and the cover when the session locks.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen } from '@testing-library/react-native';

import { mountApp } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

describe('phone', () => {
  test('opens on Home with the three tabs FF-63 draws: Home · Jobs · Reads', async () => {
    const app = await mountApp();
    expect(await screen.findByTestId('screen-FF-63')).toBeTruthy();
    expect(screen.getByTestId('tab-FF-63')).toBeTruthy();
    expect(screen.getByTestId('tab-FF-10')).toBeTruthy();
    expect(screen.getByTestId('tab-RW-01')).toBeTruthy();
    fireEvent.press(screen.getByTestId('tab-FF-10'));
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-10');
    fireEvent.press(screen.getByTestId('tab-RW-01'));
    expect(app.ref.getCurrentRoute()?.name).toBe('RW-01');
  });

  test('the sync number and the availability chip are on screen, and each opens its screen', async () => {
    const app = await mountApp({ status: { syncPending: 12, connection: 'offline', availability: 'available' } });
    await screen.findByTestId('screen-FF-63');
    expect(screen.getByTestId('shell-status-sync')).toHaveTextContent('12');
    expect(screen.getByTestId('shell-status-connection-offline')).toBeTruthy();
    expect(screen.getByTestId('shell-status-availability')).toHaveTextContent('Available');
    fireEvent.press(screen.getByTestId('shell-status-sync'));
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-50');
    // Still on screen on a pushed screen.
    expect(screen.getByTestId('shell-status')).toBeTruthy();
    fireEvent.press(screen.getByTestId('shell-status-availability'));
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-45');
  });

  test('an unknown sync state shows a dash, never a zero', async () => {
    await mountApp();
    await screen.findByTestId('screen-FF-63');
    expect(screen.getByTestId('shell-status-sync')).toHaveTextContent('–');
    expect(screen.getByTestId('shell-status-sync')).not.toHaveTextContent('0');
  });

  test('the drawer holds the phone menu and the version, and an entry opens its screen', async () => {
    const app = await mountApp();
    await screen.findByTestId('screen-FF-63');
    expect(screen.getByTestId('menu-drawer')).toBeTruthy();
    expect(screen.queryByTestId('menu-FF-63')).toBeNull(); // Home is a tab on a phone
    expect(screen.getByTestId('menu-version')).toHaveTextContent(/^\d+\.\d+\.\d+$/);
    fireEvent.press(screen.getByTestId('menu-FF-35'));
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-35');
    fireEvent.press(screen.getByTestId('menu-SWITCH'));
    expect(app.ref.getCurrentRoute()?.name).toBe('SWITCH');
  });
});

describe('tablet', () => {
  test('the menu is the permanent sidebar, with Home and Settings, and no bottom tabs', async () => {
    const app = await mountApp({ tablet: true });
    await screen.findByTestId('screen-FF-63');
    expect(screen.getByTestId('menu-sidebar')).toBeTruthy();
    expect(screen.queryByTestId('menu-drawer')).toBeNull();
    expect(screen.getByTestId('menu-FF-63')).toBeTruthy();
    expect(screen.getByTestId('menu-FF-51')).toBeTruthy();
    fireEvent.press(screen.getByTestId('menu-FF-51'));
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-51');
    // The sidebar stays while a screen is pushed beside it.
    expect(screen.getByTestId('menu-sidebar')).toBeTruthy();
  });
});

describe('signed out and locked', () => {
  test('nobody signed in: the gate, starting at the splash, with no menu and no status', async () => {
    await mountApp({ signedIn: false });
    expect(await screen.findByTestId('screen-FF-01')).toBeTruthy();
    expect(screen.queryByTestId('menu-drawer')).toBeNull();
    expect(screen.queryByTestId('shell-status')).toBeNull();
  });

  test('locking covers the screen and keeps the place; unlocking returns to it', async () => {
    const app = await mountApp();
    await screen.findByTestId('screen-FF-63');
    fireEvent.press(screen.getByTestId('tab-RW-01'));
    await act(async () => {
      app.handset.session.lock();
    });
    expect(screen.getByTestId('lock-cover')).toBeTruthy();
    await act(async () => {
      await app.handset.session.unlockWithPassword('valley-day-0730');
    });
    expect(screen.queryByTestId('lock-cover')).toBeNull();
    expect(app.ref.getCurrentRoute()?.name).toBe('RW-01');
  });
});
