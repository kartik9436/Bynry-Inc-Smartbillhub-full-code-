/**
 * T-58 — the version on screen names a BUILD (R40). The product version comes
 * from `package.json`; the build number from the running binary, never from
 * `app.json` (an over-the-air update carries a newer `app.json` than the binary
 * it lands on). The menu is mounted at its real place in the frame.
 *
 * WHAT WOULD MAKE THIS PASS WRONGLY: reading the build number from `app.json`.
 * The mocked binary below says 412 and `app.json` says something else, so a
 * label built from `app.json` fails the mounted assertion.
 */
import 'react-native-gesture-handler/jestSetup';

import { screen } from '@testing-library/react-native';

import appJson from '../../app.json';
import pkg from '../../package.json';
import { PRODUCT_VERSION, nativeBuildNumber, versionLabel } from '../../src/release/build';
import { mountApp } from '../navigation/harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('expo-constants', () => ({
  __esModule: true,
  default: { platform: { ios: { buildNumber: '412' } } },
}));

const t = (key: string, o?: Record<string, unknown>) =>
  key === 'field.nav.versionBuild' ? `${String(o?.version)} · build ${String(o?.build)}` : key;

describe('nativeBuildNumber', () => {
  test('iOS: CFBundleVersion of the binary', () => {
    expect(nativeBuildNumber({ platform: { ios: { buildNumber: '412' } } })).toBe('412');
  });
  test('Android: versionCode of the binary', () => {
    expect(nativeBuildNumber({ platform: { android: { versionCode: 37 } } })).toBe('37');
  });
  test('no binary build number (Expo Go, web, a test) is null — never made up', () => {
    expect(nativeBuildNumber({})).toBeNull();
    expect(nativeBuildNumber({ platform: { ios: { buildNumber: null } } })).toBeNull();
    expect(nativeBuildNumber({ platform: { android: { versionCode: 0 } } })).toBeNull();
    expect(nativeBuildNumber({ platform: { ios: { buildNumber: 'abc' } } })).toBeNull();
  });
});

describe('versionLabel', () => {
  test('the shape the boards draw: version · build n', () => {
    expect(versionLabel(t, '2.590.0', '412')).toBe('2.590.0 · build 412');
  });
  test('the version alone when there is no build number', () => {
    expect(versionLabel(t, '2.590.0', null)).toBe('2.590.0');
  });
  test('the product version is package.json’s', () => {
    expect(PRODUCT_VERSION).toBe(pkg.version);
  });
});

describe('app.json carries the store build numbers (T-58)', () => {
  test('ios.buildNumber and android.versionCode are set and agree', () => {
    const expo = (appJson as { expo: { ios: { buildNumber: string }; android: { versionCode: number } } }).expo;
    expect(expo.ios.buildNumber).toMatch(/^\d+$/);
    expect(Number.isInteger(expo.android.versionCode)).toBe(true);
    expect(String(expo.android.versionCode)).toBe(expo.ios.buildNumber);
  });
  test('app.json declares no version of its own — Expo reads package.json, so there is no fourth literal', () => {
    expect((appJson as { expo: Record<string, unknown> }).expo.version).toBeUndefined();
  });
});

test('mounted: the menu foot reads the product version and the RUNNING binary’s build', async () => {
  await mountApp();
  await screen.findByTestId('screen-FF-63');
  expect(screen.getByTestId('menu-version')).toHaveTextContent(`${pkg.version} · build 412`);
});
