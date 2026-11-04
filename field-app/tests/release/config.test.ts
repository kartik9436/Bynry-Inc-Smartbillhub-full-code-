/**
 * T-57 — the build and over-the-air update configuration, held so a change to
 * it is a red test rather than a surprise in a store review or on a handset.
 * The reasons are in `04-docs/05-modules/18-field-app/15-release-and-rollback.md`.
 *
 * WHAT WOULD MAKE THIS PASS WRONGLY: a config plugin added later that writes a
 * background-location key at prebuild time. This reads `app.json` only; the
 * prebuilt `Info.plist` / manifest is checked by hand before a store upload
 * (the release doc's pre-flight list).
 */
import appJson from '../../app.json';
import easJson from '../../eas.json';

type Expo = {
  runtimeVersion: { policy: string };
  updates: { enabled: boolean; checkAutomatically: string; fallbackToCacheTimeout: number };
  ios: { infoPlist: Record<string, string>; entitlements: Record<string, unknown> };
  android: { permissions: string[]; blockedPermissions: string[] };
};
const expo = (appJson as unknown as { expo: Expo }).expo;
const eas = easJson as unknown as {
  cli: { appVersionSource: string; requireCommit: boolean };
  build: Record<string, { channel?: string; distribution?: string; extends?: string }>;
  submit: { production: { android: { track: string; releaseStatus: string } } };
};

test('one channel per profile, so a preview update can never reach a production handset', () => {
  expect(eas.build.development?.channel).toBe('development');
  expect(eas.build.preview?.channel).toBe('preview');
  expect(eas.build.production?.channel).toBe('production');
  expect(eas.build.production?.distribution).toBe('store');
});

test('runtime version is the native FINGERPRINT — a JS update reaches only a binary with the same native layer', () => {
  expect(expo.runtimeVersion.policy).toBe('fingerprint');
});

test('an update never holds up a start: checked on load, applied on the next cold start, no waiting on the network', () => {
  expect(expo.updates.checkAutomatically).toBe('ON_LOAD');
  expect(expo.updates.fallbackToCacheTimeout).toBe(0);
});

test('the build number is the committed one (appVersionSource local) and a build needs a clean commit', () => {
  expect(eas.cli.appVersionSource).toBe('local');
  expect(eas.cli.requireCommit).toBe(true);
});

test('location is foreground only — background location is never requested, on either platform', () => {
  expect(expo.ios.infoPlist.NSLocationWhenInUseUsageDescription).toBeTruthy();
  expect(expo.ios.infoPlist.NSLocationAlwaysAndWhenInUseUsageDescription).toBeUndefined();
  expect(expo.ios.infoPlist.NSLocationAlwaysUsageDescription).toBeUndefined();
  expect(expo.android.permissions).not.toContain('android.permission.ACCESS_BACKGROUND_LOCATION');
  expect(expo.android.blockedPermissions).toContain('android.permission.ACCESS_BACKGROUND_LOCATION');
});

test('Critical Alerts is requested on iOS (T-01: the PO reports Apple granted it)', () => {
  expect(expo.ios.entitlements['com.apple.developer.usernotifications.critical-alerts']).toBe(true);
});

test('a store submission lands as a DRAFT on the internal track — a person releases it, never the pipeline', () => {
  expect(eas.submit.production.android.track).toBe('internal');
  expect(eas.submit.production.android.releaseStatus).toBe('draft');
});
