/**
 * T-75 flags and the Settings line; the PostHog and Crashlytics adapters.
 */
import {
  createCrashlyticsReporter,
  createFeatureFlags,
  createMemoryStore,
  createPostHogTransport,
  createScrubber,
  diagnosticsLine,
  getOrCreateDeviceId,
  posthogOptions,
  type CrashlyticsLike,
  type ScrubbedEvent,
} from '../../src/telemetry';

describe('feature flags (R71)', () => {
  const defaults = { new_debrief: false, map_style: 'street' } as const;

  it('returns the default when nothing was ever fetched', () => {
    const f = createFeatureFlags(defaults, createMemoryStore());
    expect(f.get('new_debrief')).toBe(false);
    expect(f.source('new_debrief')).toBe('default');
  });

  it('caches what it fetched, and a later offline start reads the cache', async () => {
    const store = createMemoryStore();
    const f = createFeatureFlags(defaults, store);
    expect(await f.refresh(async () => ({ new_debrief: true, map_style: 42, unknown_flag: true }))).toBe('updated');
    expect(f.get('new_debrief')).toBe(true);
    expect(f.get('map_style')).toBe('street'); // wrong type ignored

    const offline = createFeatureFlags(defaults, store);
    expect(offline.get('new_debrief')).toBe(true);
    expect(offline.source('new_debrief')).toBe('cache');
    expect(store.dump()['telemetry.flags.v1']).not.toContain('unknown_flag');
  });

  it('a failed or hung fetch keeps the cache and never throws', async () => {
    const store = createMemoryStore();
    const f = createFeatureFlags(defaults, store);
    await f.refresh(async () => ({ new_debrief: true }));
    expect(await f.refresh(async () => { throw new Error('offline'); })).toBe('failed');
    expect(await f.refresh(() => new Promise(() => {}), 20)).toBe('failed');
    expect(f.get('new_debrief')).toBe(true);
  });
});

describe('the Settings line (R72)', () => {
  it('says diagnostics are on and what they leave out, in six words or fewer', () => {
    const line = diagnosticsLine();
    expect(line).toEqual({ key: 'settings.diagnostics.on', text: 'Diagnostics on. No customer data.' });
    for (const sentence of line.text.split('.').filter((x) => x.trim())) {
      expect(sentence.trim().split(/\s+/).length).toBeLessThanOrEqual(6);
    }
  });
});

describe('device id', () => {
  it('is minted once and reused', () => {
    const store = createMemoryStore();
    const mint = jest.fn(() => '3F2B8C1E-9A4D-4E7F-8B21-6C0D5E9A1F47');
    const a = getOrCreateDeviceId(store, mint);
    const b = getOrCreateDeviceId(store, mint);
    expect(a).toBe('3f2b8c1e-9a4d-4e7f-8b21-6c0d5e9a1f47');
    expect(b).toBe(a);
    expect(mint).toHaveBeenCalledTimes(1);
  });
});

describe('PostHog', () => {
  it('has session replay and every self-capture path off (R68)', () => {
    const o = posthogOptions('https://ph.example', '3f2b8c1e-9a4d-4e7f-8b21-6c0d5e9a1f47');
    expect(o).toMatchObject({
      enableSessionReplay: false,
      captureAppLifecycleEvents: false,
      errorTracking: { autocapture: false },
      persistence: 'memory',
      personProfiles: 'never',
      bootstrap: { distinctId: '3f2b8c1e-9a4d-4e7f-8b21-6c0d5e9a1f47', isIdentifiedId: false },
    });
  });

  it('sends scrubbed events with tenant, role and the technician as super properties', async () => {
    const client = {
      register: jest.fn(async () => {}),
      capture: jest.fn(),
      flush: jest.fn(async () => {}),
      reloadFeatureFlagsAsync: jest.fn(async () => undefined),
    };
    const e = createScrubber(() => 0).scrubEvent({ name: 'screen_view', fields: { screen: 'FF-10' } }) as ScrubbedEvent;
    await createPostHogTransport(client as never).send([e], {
      tenant: 'carl-water',
      role: 'technician',
      deviceId: '3f2b8c1e-9a4d-4e7f-8b21-6c0d5e9a1f47',
      technicianId: 'u-7',
      technicianName: 'Dana Reyes',
    });
    expect(client.register).toHaveBeenCalledWith({
      tenant: 'carl-water',
      role: 'technician',
      technician_id: 'u-7',
      technician_name: 'Dana Reyes',
    });
    expect(client.capture).toHaveBeenCalledWith('screen_view', expect.objectContaining({ screen: 'FF-10' }));
    expect(client.flush).toHaveBeenCalled();
  });
});

describe('Crashlytics adapter (PO 2026-10-21)', () => {
  it('records a rebuilt error that carries no message text, with attributes and breadcrumbs', async () => {
    const calls: { attrs?: Record<string, string>; user?: string; logs: string[]; error?: Error; jsName?: string } = { logs: [] };
    const fake: CrashlyticsLike = {
      log: (m) => void calls.logs.push(m),
      setAttributes: (a) => void (calls.attrs = a),
      setUserId: (u) => void (calls.user = u),
      recordError: (e, n) => {
        calls.error = e;
        calls.jsName = n;
      },
    };
    const scrubber = createScrubber(() => 0);
    const crumb = scrubber.scrubEvent({ name: 'screen_view', fields: { screen: 'FF-25' } })!;
    const report = scrubber.scrubCrash(
      { error: new TypeError('Sarah Miller owes $241.38'), fatal: true, screen: 'FF-25' },
      [crumb],
      { tenant: 'carl-water', role: 'technician', deviceId: '3f2b8c1e-9a4d-4e7f-8b21-6c0d5e9a1f47', technicianId: 'u-7', technicianName: 'Dana Reyes' },
    );
    await createCrashlyticsReporter(fake).send(report);
    expect(calls.jsName).toBe('TypeError');
    expect(calls.error!.message).toBe('TypeError on FF-25');
    expect(calls.error!.stack).not.toContain('Sarah');
    expect(calls.user).toBe('u-7');
    expect(calls.attrs).toMatchObject({ tenant: 'carl-water', technician_name: 'Dana Reyes', screen: 'FF-25', fatal: 'true' });
    expect(calls.logs).toEqual(['screen_view screen=FF-25']);
  });
});
