/**
 * Crashlytics and PostHog, wired: the SDK is reached only through the
 * scrubbed adapters, and the two SDK paths around the scrubber are closed —
 * proved against the INSTALLED SDK's own source, so a version bump that
 * renames a key or changes the handler goes red here.
 */
import { readFileSync } from 'fs';
import { resolve } from 'path';

import * as RNFBCrashlytics from '@react-native-firebase/crashlytics';

import { createCrashlyticsReporter } from '../../src/telemetry';
import { nativeCrashlytics, reclaimRejectionTracking } from '../../src/telemetry/firebaseCrashlytics';
import { posthogTransport } from '../../src/telemetry/posthogClient';

jest.mock('posthog-react-native', () => ({
  PostHog: jest.fn().mockImplementation((apiKey: string, options: unknown) => ({
    apiKey,
    options,
    capture: jest.fn(),
    flush: jest.fn(async () => undefined),
    register: jest.fn(async () => undefined),
    reloadFeatureFlagsAsync: jest.fn(async () => undefined),
  })),
}));

const SDK = RNFBCrashlytics as unknown as Record<'log' | 'setAttributes' | 'setUserId' | 'recordError' | 'getCrashlytics', jest.Mock>;
const ROOT = resolve(__dirname, '../..');

describe('firebase.json closes the SDK global handler (path 1)', () => {
  const config = JSON.parse(readFileSync(resolve(ROOT, 'firebase.json'), 'utf8'))['react-native'];
  const handlers = readFileSync(resolve(ROOT, 'node_modules/@react-native-firebase/crashlytics/lib/handlers.js'), 'utf8');
  const nativeKeys = readFileSync(
    resolve(ROOT, 'node_modules/@react-native-firebase/crashlytics/android/src/main/java/io/invertase/firebase/crashlytics/Constants.java'),
    'utf8',
  );

  test('the two keys exist under these exact names in the installed SDK', () => {
    expect(nativeKeys).toContain('"crashlytics_is_error_generation_on_js_crash_enabled"');
    expect(nativeKeys).toContain('"crashlytics_javascript_exception_handler_chaining_enabled"');
  });

  test('generation OFF (no message reaches Crashlytics) and chaining ON (React Native still sees the error)', () => {
    expect(config.crashlytics_is_error_generation_on_js_crash_enabled).toBe(false);
    expect(config.crashlytics_javascript_exception_handler_chaining_enabled).toBe(true);
  });

  test('the installed handler behaves as that setting assumes: generation gates the send, chaining gates the hand-on', () => {
    expect(handlers).toMatch(/if \(nativeModule\.isErrorGenerationOnJSCrashEnabled\) \{/);
    expect(handlers).toMatch(/if \(nativeModule\.isCrashlyticsJavascriptExceptionHandlerChainingEnabled\) \{\s*return originalHandler\(error, fatal\);/);
  });

  test('the SDK records unhandled rejections WITH their message — which is why path 2 is reclaimed', () => {
    expect(handlers).toMatch(/setOnUnhandledPromiseRejectionHandler[\s\S]*recordErrorPromise\(createNativeErrorObj\(error/);
  });
});

test('path 2: unhandled rejections go to OUR crash file as non-fatal, not to the SDK', () => {
  const enable = jest.fn();
  const record = jest.fn();
  expect(reclaimRejectionTracking({ record }, { enable })).toBe(true);
  const options = enable.mock.calls[0]?.[0];
  expect(options.allRejections).toBe(true);
  const err = new Error('Sarah Miller owes $241.38');
  options.onUnhandled(7, err);
  expect(record).toHaveBeenCalledWith({ error: err, fatal: false });
});

test('the tracker we reclaim is the very file the SDK enabled (one module, so ours replaces its handler)', () => {
  const fromSdk = require.resolve('promise/setimmediate/rejection-tracking', {
    paths: [resolve(ROOT, 'node_modules/@react-native-firebase/crashlytics/lib')],
  });
  const fromApp = require.resolve('promise/setimmediate/rejection-tracking', { paths: [resolve(ROOT, 'src/telemetry')] });
  expect(fromApp).toBe(fromSdk);
  expect(reclaimRejectionTracking({ record: jest.fn() })).toBe(true);
});

test('the SDK adapter: each scrubbed call reaches the modular API on the one instance', async () => {
  const c = nativeCrashlytics(true);
  expect(c).not.toBeNull();
  const instance = SDK.getCrashlytics.mock.results[0]?.value;
  const reporter = createCrashlyticsReporter(c!);
  await reporter.send({
    errorType: 'TypeError',
    screen: 'FF-25',
    fatal: true,
    frames: [{ fn: 'render', file: 'index.bundle', line: 10, col: 2 }],
    components: ['JobScreen'],
    breadcrumbs: [{ name: 'screen_view', fields: { screen: 'FF-25' }, at: 0 }],
    identity: { tenant: 'silver-creek', role: 'field_app', deviceId: 'd-1', technicianId: 'u-dana', technicianName: 'Dana' },
    at: 0,
  } as never);
  expect(SDK.setAttributes).toHaveBeenCalledWith(instance, expect.objectContaining({ screen: 'FF-25', tenant: 'silver-creek' }));
  expect(SDK.setUserId).toHaveBeenCalledWith(instance, 'u-dana');
  expect(SDK.log).toHaveBeenCalledWith(instance, 'screen_view screen=FF-25');
  expect(SDK.recordError).toHaveBeenCalledWith(instance, expect.objectContaining({ name: 'TypeError', message: 'TypeError on FF-25' }), 'TypeError');
});

describe('PostHog transport', () => {
  test('no key or no host: no client — events wait in the queue', () => {
    expect(posthogTransport({ apiKey: '', host: 'https://eu.i.posthog.com' }, 'd-1')).toBeNull();
    expect(posthogTransport({ apiKey: 'phc_x', host: null }, 'd-1')).toBeNull();
  });

  test('with both: the client is built with every capture path off, the device id as distinct id', async () => {
    const t = posthogTransport({ apiKey: 'phc_x', host: 'https://eu.i.posthog.com' }, 'd-1');
    expect(t).not.toBeNull();
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { PostHog } = require('posthog-react-native') as { PostHog: jest.Mock };
    const [apiKey, options] = PostHog.mock.calls[0]!;
    expect(apiKey).toBe('phc_x');
    expect(options).toMatchObject({
      host: 'https://eu.i.posthog.com',
      enableSessionReplay: false,
      captureAppLifecycleEvents: false,
      errorTracking: { autocapture: false },
      persistence: 'memory',
      bootstrap: { distinctId: 'd-1' },
    });
    const client = PostHog.mock.results[0]!.value;
    await t!.send([{ name: 'screen_view', fields: { screen: 'FF-13' }, at: 0 } as never], null);
    expect(client.capture).toHaveBeenCalledWith('screen_view', expect.objectContaining({ screen: 'FF-13' }));
  });
});
