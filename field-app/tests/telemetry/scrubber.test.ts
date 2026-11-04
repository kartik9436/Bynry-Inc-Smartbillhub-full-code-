/**
 * T-74 — the allow list, unit by unit (R66). The end-to-end proof is
 * `scrubberProof.test.tsx`.
 */
import { createScrubber } from '../../src/telemetry';
import { parseFrames } from '../../src/telemetry/scrubber';

const s = createScrubber(() => 42);

describe('events', () => {
  it('drops an event that is not on the list, whole', () => {
    expect(s.scrubEvent({ name: 'customer_opened', fields: { screen: 'FF-25' } })).toBeNull();
  });

  it('drops fields not listed under the event, and keeps the ones that are', () => {
    const e = s.scrubEvent({ name: 'screen_view', fields: { screen: 'FF-25', customer: 'Sarah Miller' } });
    expect(e).toEqual({ name: 'screen_view', fields: { screen: 'FF-25' }, at: 42 });
  });

  it('drops a listed field whose value breaks its rule — the label is a promise the caller can break', () => {
    expect(s.scrubEvent({ name: 'screen_view', fields: { screen: 'Sarah Miller' } })!.fields).toEqual({});
    expect(s.scrubEvent({ name: 'day_pull', fields: { outcome: 'A-10432', duration_ms: -1 } })!.fields).toEqual({});
    expect(s.scrubEvent({ name: 'day_pull', fields: { duration_ms: 1.5 } })!.fields).toEqual({});
    expect(s.scrubEvent({ name: 'day_pull', fields: { duration_ms: { nested: 'Sarah' } } })!.fields).toEqual({});
  });

  it('does not read inherited names', () => {
    expect(s.scrubEvent({ name: 'toString' })).toBeNull();
    expect(s.scrubEvent({ name: '__proto__' })).toBeNull();
  });
});

describe('identity', () => {
  const base = { tenant: 'carl-water', role: 'technician', deviceId: '3f2b8c1e-9a4d-4e7f-8b21-6c0d5e9a1f47' };

  it('keeps the technician (PO 2026-10-21) and drops every other key', () => {
    expect(
      s.scrubIdentity({ ...base, technicianId: 'u-7', technicianName: ' Dana Reyes ', name: 'Sarah Miller', email: 'x@y' }),
    ).toEqual({ ...base, technicianId: 'u-7', technicianName: 'Dana Reyes' });
  });

  it('is null without tenant, role and a v4 device id', () => {
    expect(s.scrubIdentity({ ...base, deviceId: 'not-a-uuid' })).toBeNull();
    expect(s.scrubIdentity({ ...base, tenant: 'Carl Water' })).toBeNull();
  });

  it('drops a technician name that is not one line of text', () => {
    expect(s.scrubIdentity({ ...base, technicianName: 'Dana\nSarah Miller 1400 Elm' })).toEqual(base);
  });
});

describe('crashes', () => {
  it('keeps the class name and never the message', () => {
    const r = s.scrubCrash({ error: new TypeError('Sarah Miller'), fatal: true, screen: 'FF-25' }, [], null);
    expect(r.errorType).toBe('TypeError');
    expect(JSON.stringify(r)).not.toContain('Sarah');
  });

  it('does not read frame-shaped lines out of a multi-line message', () => {
    const err = new Error('first\n    at SarahMiller (/x/A-10432.ts:1:1)');
    const frames = parseFrames(err);
    expect(JSON.stringify(frames)).not.toContain('SarahMiller');
    expect(frames.length).toBeGreaterThan(0);
  });

  it('a thrown non-Error is typed NonError and carries nothing', () => {
    const r = s.scrubCrash({ error: 'Sarah Miller', fatal: false }, [], null);
    expect(r.errorType).toBe('NonError');
    expect(r.frames).toEqual([]);
  });

  it('a screen that is not an FF/RW id is null', () => {
    expect(s.scrubCrash({ error: new Error(), fatal: false, screen: '1400 Elm Street' }, [], null).screen).toBeNull();
  });
});
