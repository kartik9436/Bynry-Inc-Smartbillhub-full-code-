/**
 * T-25 / T-58 — FF-50 Sync, FF-51 Settings, FF-52 Notifications, FF-53 Sign
 * out and the Switch technician sheet (EP-FLD-09 §3), on the real navigation
 * tree over a real handset store and the real session.
 */
import 'react-native-gesture-handler/jestSetup';

import { CommonActions } from '@react-navigation/native';
import { act, fireEvent, screen, within } from '@testing-library/react-native';

import pkg from '../../../package.json';
import * as outboxQ from '../../../src/db/queries/outbox';
import { scoped } from '../../../src/db/scoped';
import { PREF } from '../../../src/screens/me/prefs';
import { MeServicesProvider } from '../../../src/screens/me/services';
import { mountApp } from '../../navigation/harness';
import { DANA, makeFixture, openScreen, seedOrders, seedPhotos, seedRefusal } from './support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

function onTop(id: string) {
  const all = screen.getAllByTestId(`screen-${id}`);
  return within(all.at(-1) as Parameters<typeof within>[0]);
}

describe('FF-50 Sync', () => {
  test('TC-4: completed work all sent · photos 38 uploading · 24 of 62 · 41 MB left', async () => {
    const f = makeFixture();
    seedPhotos(f.db);
    const app = await openScreen('FF-50', f, { status: { syncPending: 0, connection: 'online', availability: null } });
    const s = onTop('FF-50');
    expect(s.getByTestId('ff50-waiting')).toHaveTextContent('0 waiting');
    expect(s.getByTestId('ff50-completed')).toHaveProp('accessibilityLabel', 'Completed work, All sent');
    expect(s.getByTestId('ff50-photos')).toHaveProp('accessibilityLabel', 'Photos, 38 uploading');
    expect(s.getByTestId('ff50-photo-progress')).toHaveTextContent('24 of 62 · 41 MB left');
    expect(s.getByTestId('ff50-connection')).toHaveTextContent(/online/i);
    app.unmount();
  });

  test('R48: a refusal shows the server’s reason and waits for the technician; Send again re-queues the same key', async () => {
    const f = makeFixture();
    seedOrders(f.db);
    const key = seedRefusal(f.db, f.ids);
    const app = await openScreen('FF-50', f);
    expect(onTop('FF-50').getByTestId(`ff50-reason-${key}`)).toHaveTextContent('Reading 180 is impossible for this meter');
    await act(async () => {
      fireEvent.press(onTop('FF-50').getByTestId(`ff50-resend-${key}`));
    });
    expect(outboxQ.getMine(scoped(f.db, DANA), key)?.state).toBe('pending');
    expect(onTop('FF-50').queryByTestId('ff50-refused')).toBeNull();
    app.unmount();
  });

  test('nothing unsent is ever deleted: the screen has no discard, clear or remove control', async () => {
    const f = makeFixture();
    seedOrders(f.db);
    seedRefusal(f.db, f.ids);
    const app = await openScreen('FF-50', f);
    const labels = onTop('FF-50')
      .getAllByRole('button')
      .map((b) => String(b.props.accessibilityLabel ?? ''));
    expect(labels.filter((l) => /delete|discard|clear|remove/i.test(l))).toEqual([]);
    app.unmount();
  });

  test('Sync now, with the engine not mounted (T-10), says it did not run', async () => {
    const f = makeFixture();
    const app = await openScreen('FF-50', f);
    await act(async () => {
      fireEvent.press(onTop('FF-50').getByTestId('ff50-sync-now'));
    });
    expect(onTop('FF-50').getByText('Sync did not run.')).toBeTruthy();
    app.unmount();
  });
});

describe('FF-51 Settings', () => {
  test('TC-1: English → Español switches every word at once, with no restart', async () => {
    const f = makeFixture();
    const app = await openScreen('FF-51', f);
    await act(async () => {
      fireEvent.press(onTop('FF-51').getByTestId('ff51-language-es'));
    });
    expect(app.fieldI18n.language()).toBe('es');
    expect(onTop('FF-51').getByTestId('ff51-language-es')).toHaveProp('accessibilityState', { checked: true, disabled: false });
    app.unmount();
  });

  test('TC-2: Screen → Sunlight switches the theme at once', async () => {
    const f = makeFixture();
    const app = await openScreen('FF-51', f);
    const before = onTop('FF-51').getByTestId('screen-FF-51');
    expect(before).toHaveStyle({ backgroundColor: '#f3f2f2' });
    await act(async () => {
      fireEvent.press(onTop('FF-51').getByTestId('ff51-theme-sunlight'));
    });
    expect(screen.getAllByTestId('screen-FF-51').at(-1)).toHaveStyle({ backgroundColor: '#ffffff' });
    app.unmount();
  });

  test('Bigger text takes the type ramp one step up', async () => {
    const f = makeFixture();
    const app = await openScreen('FF-51', f);
    const size = () => {
      const label = onTop('FF-51').getByText('Bigger text');
      return (Array.isArray(label.props.style) ? Object.assign({}, ...label.props.style.flat()) : label.props.style).fontSize;
    };
    expect(size()).toBe(15);
    await act(async () => {
      fireEvent.press(onTop('FF-51').getByTestId('ff51-bigger-text'));
    });
    expect(size()).toBe(17);
    app.unmount();
  });

  // R54 SUPERSEDED 2026-10-28 (FB-015, option A): the switch is *Photos on wi-fi only*, default off.
  test('TC-3: nearby radius and "Photos on wi-fi only" are kept for the screens that read them', async () => {
    const f = makeFixture();
    const app = await openScreen('FF-51', f);
    expect(onTop('FF-51').getByTestId('ff51-photos-wifi-only')).toHaveProp('accessibilityState', { checked: false, disabled: false });
    fireEvent.press(onTop('FF-51').getByTestId('ff51-nearby-5'));
    fireEvent.press(onTop('FF-51').getByTestId('ff51-photos-wifi-only'));
    expect(f.services.prefs.getString(PREF.NEARBY_RADIUS)).toBe('5');
    expect(f.services.prefs.getString(PREF.PHOTOS_WIFI_ONLY)).toBe('1');
    app.unmount();
  });

  test('TC-4 / T-58: About shows the version from package.json and the diagnostics line (R40, R72)', async () => {
    const f = makeFixture();
    const app = await openScreen('FF-51', f);
    expect(onTop('FF-51').getByTestId('ff51-version')).toHaveProp('accessibilityLabel', `Version, ${pkg.version}`);
    expect(onTop('FF-51').getByTestId('ff51-diagnostics')).toHaveTextContent('Diagnostics on. No customer data.');
    app.unmount();
  });

  test('T-58: the menu shows the same version', async () => {
    const f = makeFixture();
    const app = await openScreen('FF-51', f);
    expect(screen.getByTestId('menu-version')).toHaveTextContent(pkg.version);
    app.unmount();
  });
});

describe('FF-52 Notifications', () => {
  test('every kind has its own row; a choice is kept; Play says sounds are not set up (T-41)', async () => {
    const f = makeFixture();
    const app = await openScreen('FF-52', f);
    const s = onTop('FF-52');
    expect(s.getByTestId('ff52-quiet')).toHaveProp('accessibilityLabel', 'Quiet outside my shift, Emergencies still come through');
    fireEvent.press(s.getByTestId('ff52-badge'));
    expect(f.services.prefs.getString(`${PREF.NOTIFY}dispatchBadge`)).toBe('0');
    await act(async () => {
      fireEvent.press(onTop('FF-52').getByTestId('ff52-play-emergency'));
    });
    expect(onTop('FF-52').getByText('Sounds are not set up yet.')).toBeTruthy();
    app.unmount();
  });
});

describe('FF-53 Sign out', () => {
  test('TC-2: says what is still to send and whose name it sends under; signing out deletes nothing (R64)', async () => {
    const f = makeFixture();
    const third = await openScreenWithOutbox(f);
    expect(onTop('FF-53').getByTestId('ff53-waiting')).toHaveTextContent(
      '2 items and 1 photos to send. They send under your name.',
    );
    const before = third.handset.outbox.unsentKeys();
    await act(async () => {
      fireEvent.press(onTop('FF-53').getByTestId('door-FF-05'));
    });
    expect(third.handset.session.snapshot().phase).toBe('signedOut');
    expect(third.handset.outbox.unsentKeys()).toEqual(before);
    third.unmount();
  });

  test('nothing waiting reads All sent', async () => {
    const f = makeFixture();
    const app = await openScreen('FF-53', f);
    expect(onTop('FF-53').getByTestId('ff53-all-sent')).toBeTruthy();
    app.unmount();
  });

  test('an outbox that cannot be counted is never shown as "all sent"', async () => {
    const f = makeFixture();
    const app = await openScreenWithOutbox(f, true);
    expect(onTop('FF-53').getByTestId('ff53-not-counted')).toHaveTextContent(/^Unsent work not counted. They send under your name.$/);
    expect(onTop('FF-53').queryByTestId('ff53-all-sent')).toBeNull();
    app.unmount();
  });

  test('Hand to the next technician opens the Switch sheet', async () => {
    const f = makeFixture();
    const app = await openScreen('FF-53', f);
    fireEvent.press(onTop('FF-53').getByTestId('door-SWITCH'));
    expect(app.ref.getCurrentRoute()?.name).toBe('SWITCH');
    app.unmount();
  });
});

describe('Switch technician', () => {
  test('a password, always: Hand over is disabled until one is typed, and a wrong one is refused', async () => {
    const f = makeFixture();
    const app = await openScreen('SWITCH', f);
    fireEvent.press(onTop('SWITCH').getByTestId('switch-someone-else'));
    expect(onTop('SWITCH').getByTestId('switch-hand-over')).toBeDisabled();
    fireEvent.changeText(onTop('SWITCH').getByTestId('switch-login-input'), 'm.chen');
    expect(onTop('SWITCH').getByTestId('switch-hand-over')).toBeDisabled();
    fireEvent.changeText(onTop('SWITCH').getByTestId('switch-password-input'), 'wrong');
    expect(onTop('SWITCH').getByTestId('switch-password-input')).toHaveProp('secureTextEntry', true);
    await act(async () => {
      fireEvent.press(onTop('SWITCH').getByTestId('switch-hand-over'));
    });
    expect(onTop('SWITCH').getByTestId('switch-problem')).toBeTruthy();
    expect(app.handset.session.snapshot().active?.technicianId).toBe(DANA);
    fireEvent.changeText(onTop('SWITCH').getByTestId('switch-password-input'), 'evening-1600');
    await act(async () => {
      fireEvent.press(onTop('SWITCH').getByTestId('switch-hand-over'));
    });
    expect(app.handset.session.snapshot().active?.technicianId).toBe('tech-marco');
    app.unmount();
  });
});

/** FF-53 counts through the session's view of the outbox, which the harness builds per mount. */
async function openScreenWithOutbox(f: ReturnType<typeof makeFixture>, refuse = false) {
  const app = await mountApp({
    wrap: (ui) => <MeServicesProvider services={f.services}>{ui}</MeServicesProvider>,
  });
  app.handset.outbox.add(DANA, 'item', 'k1');
  app.handset.outbox.add(DANA, 'item', 'k2');
  app.handset.outbox.add(DANA, 'photo', 'k3');
  if (refuse) app.handset.outbox.unsentCounts = () => Promise.reject(new Error('outbox not wired yet (T-10)'));
  await app.findByTestId('screen-FF-63');
  await act(async () => {
    app.ref.dispatch(CommonActions.navigate('FF-53'));
  });
  await act(async () => {
    await Promise.resolve();
  });
  return app;
}
