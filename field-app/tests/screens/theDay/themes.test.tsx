/**
 * Every screen of the two waves gettingIn and theDay renders in light, dark
 * and sunlight (AD-09), under the real navigation, from the real store — and
 * none of them falls into its crash fallback. Counted, so a screen that
 * stopped rendering cannot pass by not being looked at.
 */
import 'react-native-gesture-handler/jestSetup';

import { screen } from '@testing-library/react-native';

import { type ScreenId } from '../../../src/navigation/screens';
import type { ThemeName } from '../../../src/theme';
import { CHECK, DANA_EMAIL, go, mountGate } from '../gettingIn/gateSupport';
import { mountDay, open } from './support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

const THEMES: ThemeName[] = ['light', 'dark', 'sunlight'];

const SIGNED_IN: Array<[ScreenId, object | undefined]> = [
  ['FF-63', undefined],
  ['FF-10', undefined],
  ['FF-11', undefined],
  ['FF-12', { job: { id: 'wo-4840', number: 'WO-4840', type: 'Routine read', priorityCode: 'P3', address: '1412 Elm Street', distanceMi: 0.2, dueAt: null, estMinutes: 10, takenBy: null } }],
  ['FF-13', undefined],
  ['FF-14', { jobId: 'wo-4824' }],
  ['FF-07', undefined],
  ['FF-08', undefined],
];

const GATE: Array<[ScreenId, object | undefined]> = [
  ['FF-02', undefined],
  ['FF-03', undefined],
  ['FF-04', undefined],
  ['FF-05', undefined],
  ['FF-06', { login: 'd.ortiz' }],
  ['FF-56', undefined],
  ['FF-57', { check: CHECK, email: DANA_EMAIL }],
];

describe.each(THEMES)('%s', (theme) => {
  test('every signed-in screen of the two waves renders, none crashed', async () => {
    const app = await mountDay({ theme });
    let seen = 0;
    for (const [id, params] of SIGNED_IN) {
      await open(app, id, params);
      expect(await screen.findAllByTestId(`screen-${id}`)).not.toHaveLength(0);
      seen += 1;
    }
    expect(screen.queryAllByTestId(/^crashed-/)).toHaveLength(0);
    expect(seen).toBe(SIGNED_IN.length);
    app.unmount();
  }, 60_000);

  test('the splash and every gate screen renders, none crashed', async () => {
    const app = await mountGate({ theme });
    expect(await screen.findByTestId('screen-FF-01')).toBeTruthy();
    let seen = 1;
    for (const [id, params] of GATE) {
      await go(app, id, params);
      seen += 1;
    }
    expect(screen.queryAllByTestId(/^crashed-/)).toHaveLength(0);
    expect(seen).toBe(GATE.length + 1);
    app.unmount();
  }, 60_000);

  test('the lock cover renders with its form', async () => {
    const app = await mountDay({ theme });
    app.handset.session.lock();
    expect(await screen.findByTestId('lock-password')).toBeTruthy();
    app.unmount();
  });
});
