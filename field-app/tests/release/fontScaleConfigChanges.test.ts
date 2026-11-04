/**
 * @jest-environment node
 *
 * DEF-FLD-10589 (MQ-031): a font-size or display-size change must reach the
 * running activity as `onConfigurationChanged`, never as a destroy-and-recreate
 * under a live React host (`plugins/withFontScaleConfigChanges.js` says why).
 *
 * The first test evaluates the REAL project config the way
 * `npx expo config --type introspect` does — `app.config.ts` over `app.json`,
 * every plugin's manifest mod compiled — so a plugin dropped from `app.json`,
 * or a later plugin that rewrites configChanges, goes red here.
 *
 * WHAT WOULD MAKE THIS PASS WRONGLY: a mod that is introspectable but differs
 * from what `expo prebuild` writes. Prebuild runs the same compiled mods; the
 * MainActivity mod is not introspectable, so it is proved on Expo SDK 53's
 * own template (`fixtures/MainActivity.sdk53.kt.txt`, copied from a prebuild).
 */
import { readFileSync } from 'fs';
import { join } from 'path';

import plugin from '../../plugins/withFontScaleConfigChanges';

const ROOT = join(__dirname, '..', '..');
/** MainActivity's configChanges as Expo SDK 53 generated it on 2.594.1. */
const BEFORE = ['keyboard', 'keyboardHidden', 'orientation', 'screenSize', 'screenLayout', 'uiMode', 'locale', 'layoutDirection'];

interface Activity {
  $: Record<string, string>;
}

async function introspectedMainActivity(): Promise<Activity> {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { getPrebuildConfigAsync } = require('@expo/prebuild-config');
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { compileModsAsync } = require('@expo/config-plugins/build/plugins/mod-compiler.js');
  const { exp } = await getPrebuildConfigAsync(ROOT, { platforms: ['android'] });
  const compiled = await compileModsAsync(exp, {
    projectRoot: ROOT,
    introspect: true,
    platforms: ['android'],
    assertMissingModProviders: false,
  });
  const manifest = compiled._internal.modResults.android.manifest;
  const activities: Activity[] = manifest.manifest.application[0].activity;
  const main = activities.find((a) => a.$['android:name'] === '.MainActivity');
  if (!main) throw new Error('no .MainActivity');
  return main;
}

describe('MainActivity configChanges (DEF-FLD-10589)', () => {
  test('the evaluated project config carries fontScale and density, and keeps the eight it had', async () => {
    const values = (await introspectedMainActivity()).$['android:configChanges']!.split('|');
    expect(values).toEqual(expect.arrayContaining(['fontScale', 'density']));
    expect(values).toEqual(expect.arrayContaining(BEFORE));
    // Order is irrelevant to Android (other mods append locale|layoutDirection after ours); count is not.
    expect(values).toHaveLength(BEFORE.length + 2);
    expect(new Set(values).size).toBe(values.length);
  }, 60000);

  test('the manifest transform appends the two, keeps order, and is idempotent', () => {
    const manifest = {
      manifest: {
        $: {},
        application: [
          {
            $: { 'android:name': '.MainApplication' },
            activity: [{ $: { 'android:name': '.MainActivity', 'android:configChanges': BEFORE.join('|') } }],
          },
        ],
      },
    };
    const once = plugin.addFontScaleConfigChanges(manifest);
    const value = once.manifest.application[0]!.activity[0]!.$['android:configChanges'];
    expect(value).toBe([...BEFORE, 'fontScale', 'density'].join('|'));
    const twice = plugin.addFontScaleConfigChanges(once);
    expect(twice.manifest.application[0]!.activity[0]!.$['android:configChanges']).toBe(value);
    expect(plugin.mergeConfigChanges('density|uiMode')).toBe('density|uiMode|fontScale');
    expect(plugin.mergeConfigChanges(undefined)).toBe('fontScale|density');
  });

  test('a manifest with no MainActivity fails the build rather than shipping the old value', () => {
    const empty = { manifest: { $: {}, application: [{ $: {}, activity: [] }] } };
    expect(() => plugin.addFontScaleConfigChanges(empty)).toThrow(/no \.MainActivity/);
  });
});

describe('MainActivity.onConfigurationChanged (DEF-FLD-10589)', () => {
  const template = readFileSync(join(__dirname, 'fixtures', 'MainActivity.sdk53.kt.txt'), 'utf8');

  test("SDK 53's template gains one override that forwards the new scale to React Native", () => {
    const out = plugin.addConfigurationListener(template, 'kt');
    expect(out.match(/override fun onConfigurationChanged/g)).toHaveLength(1);
    expect(out).toContain('super.onConfigurationChanged(newConfig)');
    expect(out).toContain('DisplayMetricsHolder.initDisplayMetrics(applicationContext)');
    expect(out).toContain('DeviceInfoModule::class.java');
    expect(out).toContain('it.onHostResume()');
    expect(out).toContain('it.emitUpdateDimensionsEvent()');
    // Inside the class, before the first member it already had.
    expect(out.indexOf('onConfigurationChanged')).toBeGreaterThan(out.indexOf('class MainActivity : ReactActivity() {'));
    expect(out.indexOf('onConfigurationChanged')).toBeLessThan(out.indexOf('override fun onCreate'));
    // Everything the template had is still there, byte for byte.
    expect(out.replace(/\n  \/\/ @generated[\s\S]*?\/\/ @end [^\n]*\n/, '')).toBe(template);
    expect(plugin.addConfigurationListener(out, 'kt')).toBe(out);
  });

  test('Java, or a MainActivity that already overrides it, fails the build', () => {
    expect(() => plugin.addConfigurationListener(template, 'java')).toThrow(/expected Kotlin/);
    const own = template.replace('override fun onCreate', 'override fun onConfigurationChanged(c: Configuration) {}\n  override fun onCreate');
    expect(() => plugin.addConfigurationListener(own, 'kt')).toThrow(/merge by hand/);
  });
});
