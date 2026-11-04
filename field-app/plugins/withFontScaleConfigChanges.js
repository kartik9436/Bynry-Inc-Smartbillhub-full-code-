/**
 * DEF-FLD-10589 (beta report MQ-031): changing the phone's FONT SIZE or
 * DISPLAY SIZE with the app open must not restart the screen under a live
 * React Native host.
 *
 * WHAT WENT WRONG. Expo's generated MainActivity declared
 * `android:configChanges="keyboard|keyboardHidden|orientation|screenSize|
 * screenLayout|uiMode|locale|layoutDirection"` — no `fontScale` and no
 * `density`. For any change NOT on that list Android destroys and recreates
 * the activity. With the new architecture the React host and the native
 * modules (expo-sqlite among them) outlive the activity, so the teardown and
 * the re-attach race: on an Android 16 Pixel 6 emulator, 1.0 → 2.0 aborted
 * the process ~1.7 s later (`SIGABRT` on `mqt_v_js`, Scudo *invalid chunk
 * state*), 1 try in 2. When it survived, every button label sat top-left of
 * its box until force-stop — see `src/theme/measureKey.ts` for why.
 *
 * WHAT THIS PLUGIN DOES, in two mods, both idempotent:
 *
 *  1. **Manifest** — adds `fontScale` and `density` to MainActivity's
 *     `android:configChanges`, keeping every value already there and their
 *     order. The activity now receives `onConfigurationChanged` instead of
 *     being recreated.
 *
 *  2. **MainActivity.kt** — overrides `onConfigurationChanged` to TELL React
 *     Native. Without this, nothing reaches JavaScript: React Native 0.79's
 *     `ReactHostImpl.onConfigurationChanged` forwards a configuration change
 *     to the Appearance module only (light/dark), and `DeviceInfoModule`
 *     re-reads `fontScale` only in `onHostResume`. So the override refreshes
 *     `DisplayMetricsHolder` (display size) and calls the module's own
 *     `onHostResume()` + `emitUpdateDimensionsEvent()`, which emits
 *     `didUpdateDimensions` with the new `fontScale` — the event
 *     `useWindowDimensions()` listens to — and does nothing when nothing
 *     changed. Fully-qualified names, so no import is added.
 *
 * Font scaling is NOT capped anywhere: large text up to 200% is supported.
 *
 * Pure helpers are exported so `tests/release/fontScaleConfigChanges.test.ts`
 * can run them on a fixture of today's manifest and Expo SDK 53's template
 * MainActivity. Plain CommonJS on purpose: `@expo/config` transpiles
 * `app.config.ts` itself and `require`s everything else as-is, so a `.ts`
 * plugin would not load at prebuild.
 */
const { withAndroidManifest, withMainActivity } = require('expo/config-plugins');

/** Values this plugin guarantees on MainActivity's configChanges. */
const REQUIRED_CONFIG_CHANGES = ['fontScale', 'density'];

const TAG = 'DEF-FLD-10589 fontScale';

/** `a|b|c` plus each required value that is missing, order kept. */
function mergeConfigChanges(current) {
  const values = (current || '')
    .split('|')
    .map((v) => v.trim())
    .filter(Boolean);
  for (const v of REQUIRED_CONFIG_CHANGES) if (!values.includes(v)) values.push(v);
  return values.join('|');
}

/** The manifest with MainActivity's configChanges extended. Throws when there is no MainActivity — fail closed. */
function addFontScaleConfigChanges(androidManifest) {
  const app = androidManifest.manifest.application && androidManifest.manifest.application[0];
  const activity = ((app && app.activity) || []).find((a) => a.$['android:name'] === '.MainActivity');
  if (!activity) throw new Error(`${TAG}: no .MainActivity in AndroidManifest.xml`);
  activity.$['android:configChanges'] = mergeConfigChanges(activity.$['android:configChanges']);
  return androidManifest;
}

const KOTLIN_OVERRIDE = `
  // @generated ${TAG} — plugins/withFontScaleConfigChanges.js
  // fontScale and density are in configChanges, so Android no longer recreates
  // this activity on a font or display size change; tell React Native here.
  override fun onConfigurationChanged(newConfig: android.content.res.Configuration) {
    super.onConfigurationChanged(newConfig)
    com.facebook.react.uimanager.DisplayMetricsHolder.initDisplayMetrics(applicationContext)
    reactHost?.currentReactContext
      ?.getNativeModule(com.facebook.react.modules.deviceinfo.DeviceInfoModule::class.java)
      ?.let {
        it.onHostResume()
        it.emitUpdateDimensionsEvent()
      }
  }
  // @end ${TAG}
`;

/** MainActivity.kt with the override added once. Throws on Java or an unrecognised class line. */
function addConfigurationListener(contents, language) {
  if (language !== 'kt') throw new Error(`${TAG}: MainActivity is ${language}, expected Kotlin`);
  if (contents.includes(`@generated ${TAG}`)) return contents;
  if (/override\s+fun\s+onConfigurationChanged\s*\(/.test(contents)) {
    throw new Error(`${TAG}: MainActivity already overrides onConfigurationChanged; merge by hand`);
  }
  const anchor = /class\s+MainActivity\s*:\s*ReactActivity\(\)\s*\{\n/;
  if (!anchor.test(contents)) throw new Error(`${TAG}: MainActivity class line not found`);
  return contents.replace(anchor, (m) => m + KOTLIN_OVERRIDE);
}

function withFontScaleConfigChanges(config) {
  config = withAndroidManifest(config, (c) => {
    c.modResults = addFontScaleConfigChanges(c.modResults);
    return c;
  });
  config = withMainActivity(config, (c) => {
    c.modResults.contents = addConfigurationListener(c.modResults.contents, c.modResults.language);
    return c;
  });
  return config;
}

module.exports = withFontScaleConfigChanges;
module.exports.default = withFontScaleConfigChanges;
module.exports.REQUIRED_CONFIG_CHANGES = REQUIRED_CONFIG_CHANGES;
module.exports.mergeConfigChanges = mergeConfigChanges;
module.exports.addFontScaleConfigChanges = addFontScaleConfigChanges;
module.exports.addConfigurationListener = addConfigurationListener;
