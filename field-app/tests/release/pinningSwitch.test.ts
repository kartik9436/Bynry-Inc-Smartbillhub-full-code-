/**
 * THE RELEASE SWITCH ON CERTIFICATE PINNING — DORMANT BY DEFAULT
 * (`CR-195-BRC10`; decision log 2026-10-28, PO: *"start A1"*).
 *
 * Pinning is no longer a go-live requirement. BOTH the beta (EAS `preview`)
 * and the store build (`production`) build with pinning OFF, and the phone
 * relies on Android's standard certificate validation (system authorities
 * only). The code stays: typing `FIELD_APP_PINNING=on` (with a correct issuer
 * list) switches it back on as configuration alone, in any profile.
 * Each profile's environment is resolved from `eas.json` exactly as EAS does
 * it (the profile's own `env` over the profiles it `extends`), then run
 * through `app.config.ts`'s `buildConfig`, and the `extra` it writes is read
 * back by the same functions the phone uses (`pinningMode`, `bootstrapPins`).
 *
 * Superseded: 2026-10-26's *"production keeps it ON"* (`DEF-FLD-10617`) — a
 * production build with pinning off was REFUSED until 2026-10-28.
 *
 * WHAT WOULD MAKE THIS PASS WRONGLY: reading the profiles by hand instead of
 * through `extends`, so a `FIELD_APP_PINNING=on` put on `base` would reach
 * every build unseen. `envOf` walks the chain.
 */
import { readFileSync } from 'fs';
import { join } from 'path';
import type { ExpoConfig } from 'expo/config';

import appJson from '../../app.json';
import { buildConfig, pinningFromEnv } from '../../app.config';
import { bootstrapPins, pinningMode, usablePins, utcDay, MIN_PINS } from '../../src/security/pins';

interface Profile {
  extends?: string;
  env?: Record<string, string>;
}

const eas = JSON.parse(readFileSync(join(__dirname, '../../eas.json'), 'utf8')) as { build: Record<string, Profile> };
const base = (appJson as unknown as { expo: Partial<ExpoConfig> }).expo;

/** A profile's environment as EAS resolves it, plus the profile name EAS sets on its builders. */
function envOf(name: string): Record<string, string> {
  const profile = eas.build[name];
  if (!profile) throw new Error(`eas.json has no ${name} profile`);
  const inherited = profile.extends ? envOf(profile.extends) : {};
  return { ...inherited, ...(profile.env ?? {}), EAS_BUILD_PROFILE: name };
}

const resolve = (env: Record<string, string>) => buildConfig(base, { exists: () => false, env }).extra;

describe('certificate pinning per build profile (dormant, CR-195-BRC10)', () => {
  test('production (the store build): pinning OFF, and the build is allowed', () => {
    const extra = resolve(envOf('production'));
    expect(extra?.pinning).toBe('off');
    expect(pinningMode(extra)).toBe('off');
  });

  test('preview (the beta APK): pinning OFF', () => {
    const extra = resolve(envOf('preview'));
    expect(extra?.pinning).toBe('off');
    expect(pinningMode(extra)).toBe('off');
  });

  test('both profiles say off EXPLICITLY in eas.json', () => {
    expect(eas.build.preview?.env?.FIELD_APP_PINNING).toBe('off');
    expect(eas.build.production?.env?.FIELD_APP_PINNING).toBe('off');
  });

  test('no FIELD_APP_PINNING at all does not pin; only the exact word "on" does', () => {
    expect(resolve({})?.pinning).toBe('off');
    expect(pinningMode({})).toBe('off');
    expect(pinningMode(undefined)).toBe('off');
    expect(pinningMode({ pinning: 'ON ' })).toBe('off');
    expect(pinningMode({ pinning: true })).toBe('off');
    expect(pinningMode({ pinning: 'on' })).toBe('on');
  });

  test('a value that is neither on nor off fails the build rather than guess', () => {
    expect(() => pinningFromEnv({ FIELD_APP_PINNING: 'maybe' })).toThrow(/FIELD_APP_PINNING/);
    expect(pinningFromEnv({ FIELD_APP_PINNING: ' Off ' })).toBe('off');
    expect(pinningFromEnv({ FIELD_APP_PINNING: ' On ' })).toBe('on');
    expect(pinningFromEnv({ FIELD_APP_PINNING: '' })).toBe('off');
  });

  test('switched back ON by configuration alone: a production build with FIELD_APP_PINNING=on pins with two unexpired keys', () => {
    const extra = resolve({ ...envOf('production'), FIELD_APP_PINNING: 'on' });
    expect(extra?.pinning).toBe('on');
    expect(pinningMode(extra)).toBe('on');
    const pins = usablePins(bootstrapPins(extra), utcDay(new Date()));
    expect(pins.length).toBeGreaterThanOrEqual(MIN_PINS);
  });

  test('switched on with a malformed issuer list still fails the build', () => {
    expect(() => resolve({ ...envOf('production'), FIELD_APP_PINNING: 'on', FIELD_APP_PINS: '[]' })).toThrow(/FIELD_APP_PINS/);
  });
});
