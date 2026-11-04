/**
 * T-12 — the two credentials and several technicians on one handset, walked
 * through the design's own case: Dana signs in at 07:30 on depot wi-fi, her
 * access token expires at 08:30, and she has nine hours of work left with no
 * signal (Security tab §1).
 */
import { InvalidCredentialsError, OfflineError } from '../../src/security/authApi';
import { CaptureCredentialExpiredError } from '../../src/security/captureStamp';
import { HOUR_MS, MINUTE_MS } from '../../src/security/clock';
import { CAPTURE_CREDENTIAL_TTL_MS, captureExpiry } from '../../src/security/credentials';
import {
  AUTO_LOCK_IDLE_MS,
  BiometricNotAllowedError,
  LockedError,
  OFFLINE_CAPTURE_RENEWAL,
  OpenQuestionError,
} from '../../src/session/sessionManager';
import { makeHandset, PEOPLE, signIn, TENANT } from './fakes';

describe('two credentials: expiry blocks SENDING, never capture', () => {
  test('Dana at 07:30, token gone at 08:30, nine more hours of capture in the valley', async () => {
    const h = makeHandset();
    await signIn(h.session, 'd.ortiz');
    expect(h.session.snapshot()).toMatchObject({ phase: 'unlocked', canSend: true, canCapture: true });
    expect(h.session.courierAccessToken()).not.toBeNull();

    h.api.online = false; // drives into the valley
    h.clock.advance(1 * HOUR_MS); // 08:30 — the access token has expired
    let snap = await h.session.refresh(); // no signal: uneventful
    expect(snap.canSend).toBe(false);
    expect(snap.canCapture).toBe(true);
    expect(h.session.courierAccessToken()).toBeNull();

    // Nine hours of work, a capture every ten minutes, never more than five minutes idle.
    for (let minute = 0; minute < 9 * 60; minute += 4) {
      h.clock.advance(4 * MINUTE_MS);
      h.session.touch();
      h.session.tick();
      if (minute % 12 === 0) {
        const stamp = h.session.stampCapture();
        expect(stamp.captured_by).toBe('tech-dana');
        h.outbox.add(stamp.captured_by, 'item', `k${minute}`);
      }
    }
    snap = h.session.snapshot();
    expect(snap.canCapture).toBe(true);
    expect(snap.canSend).toBe(false);
    expect(h.outbox.unsentKeys()).toHaveLength(45);

    // Back at the depot: a signal, a refresh, and sending is open again.
    h.api.online = true;
    snap = await h.session.refresh();
    expect(snap.canSend).toBe(true);
  });

  test('the capture credential lives as long as the server says (a tenant setting); seven days only when it says nothing', () => {
    expect(captureExpiry(0, 3 * 24 * 3600)).toBe(3 * 24 * HOUR_MS);
    expect(captureExpiry(0, 3600)).toBe(HOUR_MS);
    expect(captureExpiry(0, 3600, 10 * HOUR_MS)).toBe(10 * HOUR_MS);
    expect(captureExpiry(0, null)).toBe(CAPTURE_CREDENTIAL_TTL_MS);
    expect(captureExpiry(0, 0)).toBe(7 * 24 * HOUR_MS);
  });

  test('both expired: a password before anything more is captured, the queue untouched, and the offline case named as a question', async () => {
    const h = makeHandset();
    await signIn(h.session, 'd.ortiz');
    h.outbox.add('tech-dana', 'item', 'reading-1');
    h.outbox.add('tech-dana', 'photo', 'photo-1');
    const before = h.outbox.unsentKeys();
    h.api.online = false;

    h.clock.advance(7 * 24 * HOUR_MS); // off for a week
    h.session.touch();
    const snap = h.session.snapshot();
    expect(snap.canCapture).toBe(false);
    expect(snap.captureNeedsPassword).toBe(true);
    expect(snap.canSend).toBe(false);
    expect(() => h.session.stampCapture()).toThrow(CaptureCredentialExpiredError);
    await expect(h.session.reopenCaptureOffline(PEOPLE['d.ortiz']!.password)).rejects.toThrow(OpenQuestionError);
    await expect(h.session.reopenCaptureOffline('x')).rejects.toThrow(OFFLINE_CAPTURE_RENEWAL);
    expect(h.outbox.unsentKeys()).toEqual(before);

    // With a signal, the password renews both and capture resumes.
    h.api.online = true;
    await signIn(h.session, 'd.ortiz');
    expect(h.session.snapshot()).toMatchObject({ canCapture: true, canSend: true, captureNeedsPassword: false });
    expect(h.outbox.unsentKeys()).toEqual(before);
  });
});

describe('several technicians on one handset', () => {
  test('each has their own capture credential; Marco signing in does not touch Dana’s', async () => {
    const h = makeHandset();
    await signIn(h.session, 'd.ortiz');
    const dana = h.session.captureCredentialOf('tech-dana');
    await h.session.switchTo('tech-dana', PEOPLE['d.ortiz']!.password); // same person, fine
    await signIn(h.session, 'm.chen');
    const marco = h.session.captureCredentialOf('tech-marco');
    expect(marco?.technicianId).toBe('tech-marco');
    expect(h.session.captureCredentialOf('tech-dana')?.technicianId).toBe('tech-dana');
    expect(marco?.serverToken).not.toBe(h.session.captureCredentialOf('tech-dana')?.serverToken);
    expect(dana?.technicianId).toBe('tech-dana');
  });

  test('captured_by comes from the capture credential: Dana’s item still says Dana when Marco is the courier', async () => {
    const h = makeHandset();
    await signIn(h.session, 'd.ortiz');
    const danaStamp = h.session.stampCapture();
    h.outbox.add(danaStamp.captured_by, 'item', 'close-WO-4822');

    await signIn(h.session, 'm.chen'); // hand over
    const marcoStamp = h.session.stampCapture();

    expect(danaStamp.captured_by).toBe('tech-dana');
    expect(danaStamp.capture_token).toContain('tech-dana');
    expect(marcoStamp.captured_by).toBe('tech-marco');
    // The send goes under Marco's access token; the item carries Dana's identity.
    expect(h.session.courierAccessToken()).toContain('tech-marco');
    expect(h.outbox.rows[0]?.technicianId).toBe('tech-dana');
  });

  test('a technician never sees another’s unsent work as their own', async () => {
    const h = makeHandset();
    await signIn(h.session, 'd.ortiz');
    for (let i = 0; i < 3; i += 1) h.outbox.add('tech-dana', 'item', `d${i}`);
    for (let i = 0; i < 38; i += 1) h.outbox.add('tech-dana', 'photo', `p${i}`);
    await signIn(h.session, 'm.chen');
    h.outbox.add('tech-marco', 'item', 'm1');

    const marcoView = await h.session.unsentSummary();
    expect(marcoView.mine).toEqual({ items: 1, photos: 0 });
    expect(marcoView.others).toEqual([{ technicianId: 'tech-dana', displayName: 'D. Ortiz', items: 3, photos: 38 }]);

    await h.session.signOut();
    const nobody = await h.session.unsentSummary();
    expect(nobody.mine).toEqual({ items: 0, photos: 0 });
    expect(nobody.others.map((o) => o.technicianId).sort()).toEqual(['tech-dana', 'tech-marco']);
  });

  test('switching technician always takes a password', async () => {
    const h = makeHandset();
    await signIn(h.session, 'd.ortiz');
    await signIn(h.session, 'm.chen');
    await expect(h.session.switchTo('tech-dana', 'wrong')).rejects.toThrow(InvalidCredentialsError);
    expect(h.session.snapshot().active?.technicianId).toBe('tech-marco');

    // Offline, a technician known on this handset is checked against the verifier.
    h.api.online = false;
    await expect(h.session.switchTo('tech-dana', 'wrong')).rejects.toThrow(InvalidCredentialsError);
    await h.session.switchTo('tech-dana', PEOPLE['d.ortiz']!.password);
    expect(h.session.snapshot().active?.technicianId).toBe('tech-dana');
    // …and someone this handset has never seen cannot sign in without a signal.
    await expect(
      h.session.signIn({ tenant: TENANT, login: 'r.patel', password: PEOPLE['r.patel']!.password }),
    ).rejects.toThrow(OfflineError);
  });

  test('biometric only returns you to your own session — never a switch', async () => {
    const h = makeHandset();
    await signIn(h.session, 'm.chen');
    await signIn(h.session, 'd.ortiz');
    h.session.lock();
    await expect(h.session.unlockWithBiometric('tech-marco', 'Unlock')).rejects.toThrow(BiometricNotAllowedError);
    expect(h.session.snapshot()).toMatchObject({ phase: 'locked' });
    await h.session.unlockWithBiometric('tech-dana', 'Unlock');
    expect(h.session.snapshot()).toMatchObject({ phase: 'unlocked' });

    h.session.lock();
    h.biometric.available = false;
    await expect(h.session.unlockWithBiometric('tech-dana', 'Unlock')).rejects.toThrow(BiometricNotAllowedError);
  });
});

describe('auto-lock', () => {
  test('locks after five minutes idle, not before, and a touch resets the clock', async () => {
    const h = makeHandset();
    await signIn(h.session, 'd.ortiz');
    h.clock.advance(AUTO_LOCK_IDLE_MS - 1000);
    expect(h.session.tick().phase).toBe('unlocked');
    h.session.touch();
    h.clock.advance(AUTO_LOCK_IDLE_MS - 1000);
    expect(h.session.tick().phase).toBe('unlocked');
    h.clock.advance(1000);
    expect(h.session.tick().phase).toBe('locked');
    expect(() => h.session.stampCapture()).toThrow(LockedError);
  });

  test('locks after five minutes away (MQ-019), and unlocks offline with the password', async () => {
    const h = makeHandset();
    await signIn(h.session, 'd.ortiz');
    expect(h.session.onBackground().phase).toBe('unlocked');
    h.clock.advance(AUTO_LOCK_IDLE_MS);
    expect(h.session.onForeground().phase).toBe('locked');
    h.api.online = false;
    await expect(h.session.unlockWithPassword('wrong')).rejects.toThrow(InvalidCredentialsError);
    await h.session.unlockWithPassword(PEOPLE['d.ortiz']!.password);
    expect(h.session.snapshot().phase).toBe('unlocked');
    expect(h.session.stampCapture().captured_by).toBe('tech-dana');
  });
});

describe('what is kept where', () => {
  test('a cold start comes back locked, with each technician’s credentials restored from the keystore', async () => {
    const h = makeHandset();
    await signIn(h.session, 'd.ortiz');
    await signIn(h.session, 'm.chen');
    const restarted = h.build();
    const snap = await restarted.restore();
    expect(snap.phase).toBe('locked');
    expect(snap.active?.technicianId).toBe('tech-marco');
    expect(restarted.captureCredentialOf('tech-dana')?.technicianId).toBe('tech-dana');
  });

  test('no token or credential is ever written to the preference store', async () => {
    const h = makeHandset();
    await signIn(h.session, 'd.ortiz');
    await h.session.refresh();
    const prefsText = [...h.prefs.data.values()].join(' ');
    expect(prefsText).not.toMatch(/access-|capture-|salt-/);
    const secretsText = [...h.secrets.data.values()].join(' ');
    expect(secretsText).toMatch(/capture-tech-dana/);
    expect(secretsText).not.toContain(PEOPLE['d.ortiz']!.password);
  });

  test('a remote sign-out drops the mirror and the credentials, and keeps the outbox', async () => {
    const h = makeHandset();
    await signIn(h.session, 'd.ortiz');
    h.outbox.add('tech-dana', 'item', 'r1');
    h.outbox.add('tech-dana', 'photo', 'p1');
    const before = h.outbox.unsentKeys();
    h.api.signedOutDevices.add(await h.device.deviceId());
    h.clock.advance(10 * MINUTE_MS);
    h.session.touch();
    const snap = await h.session.refresh();
    expect(snap.phase).toBe('signedOut');
    expect(h.outbox.mirrorDrops).toEqual(['tech-dana']);
    expect(h.session.captureCredentialOf('tech-dana')).toBeNull();
    expect(h.outbox.unsentKeys()).toEqual(before);
  });
});
