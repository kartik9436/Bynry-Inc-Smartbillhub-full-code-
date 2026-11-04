/**
 * T-12, the security half: activation (FF-56/57), the device register, the
 * capture stamp, and the HTTP client's honesty about what the server lacks.
 */
import {
  ActivationCodeShapeError,
  checkActivationCode,
  checkNewPassword,
  completeActivation,
  isActivationCodeShaped,
  normaliseActivationCode,
  PasswordNotAcceptedError,
} from '../../src/security/activation';
import { type ActivationCheck, type AuthApi, SERVER_GAPS, ServerGapError } from '../../src/security/authApi';
import { CaptureCredentialExpiredError, stampFromCredential } from '../../src/security/captureStamp';
import { HOUR_MS } from '../../src/security/clock';
import { type CaptureCredential } from '../../src/security/credentials';
import { DeviceNameRequiredError, DeviceRegister, normaliseDeviceName } from '../../src/security/deviceRegister';
import { createHttpAuthApi } from '../../src/security/httpAuthApi';
import { randomKey } from '../../src/security/prefs';
import { MemorySecretStore, secretKey } from '../../src/security/secretStore';
import { FakeAuthApi, TENANT } from '../session/fakes';

describe('activation (FF-56, FF-57)', () => {
  test('a six-character code, read off an email or a phone call', () => {
    expect(normaliseActivationCode(' k7m 2-ab ')).toBe('K7M2AB');
    expect(isActivationCodeShaped('k7m2ab')).toBe(true);
    expect(isActivationCodeShaped('K7M2')).toBe(false);
    expect(isActivationCodeShaped('K7M2AB9')).toBe(false);
    expect(isActivationCodeShaped('K7M2A!')).toBe(false);
  });

  test('the password minimum is the tenant’s policy, not a number in the app', () => {
    expect(checkNewPassword('nine-char', 'nine-char', 8)).toEqual({ longEnough: true, matches: true, ok: true });
    expect(checkNewPassword('nine-char', 'nine-char', 10).ok).toBe(false);
    expect(checkNewPassword('long-enough-1', 'long-enough-2', 10)).toMatchObject({ longEnough: true, matches: false, ok: false });
    expect(checkNewPassword('long-enough-1', '', 10).matches).toBe(false);
  });

  test('a malformed code never reaches the server; a good one goes, normalised', async () => {
    const seen: unknown[] = [];
    const api = {
      checkActivationCode: async (input: unknown) => {
        seen.push(input);
        return {} as ActivationCheck;
      },
    } as unknown as AuthApi;
    await expect(checkActivationCode(api, { tenant: TENANT, code: 'K7M', email: 'd@x' })).rejects.toThrow(ActivationCodeShapeError);
    expect(seen).toHaveLength(0);
    await checkActivationCode(api, { tenant: TENANT, code: 'k7m 2ab', email: ' dana.ortiz@lonestarwater.gov ' });
    expect(seen).toEqual([{ tenant: TENANT, code: 'K7M2AB', email: 'dana.ortiz@lonestarwater.gov' }]);
  });

  test('a password that fails the checks is refused before it is sent', async () => {
    const check: ActivationCheck = {
      displayName: 'Dana Ortiz',
      roleLabel: 'Field Technician',
      utilityName: 'Lone Star Water',
      passwordMinLength: 10,
      activationTicket: 't',
    };
    const api = { completeActivation: jest.fn() } as unknown as AuthApi;
    await expect(
      completeActivation(api, { tenant: TENANT, check, password: 'short', again: 'short', deviceId: 'd', deviceName: 'Van 14 tablet' }),
    ).rejects.toThrow(PasswordNotAcceptedError);
    expect(api.completeActivation).not.toHaveBeenCalled();
  });
});

describe('the device register', () => {
  test('one id per install, stable, kept in the keystore', async () => {
    const secrets = new MemorySecretStore();
    let n = 0;
    const reg = new DeviceRegister(secrets, () => `id-${(n += 1)}`);
    expect(await reg.deviceId()).toBe('id-1');
    expect(await reg.deviceId()).toBe('id-1');
    expect(await new DeviceRegister(secrets, () => 'other').deviceId()).toBe('id-1');
  });

  test('registered by NAME; the name is kept even when the server cannot be reached', async () => {
    const secrets = new MemorySecretStore();
    const reg = new DeviceRegister(secrets, () => 'dev-1');
    const api = new FakeAuthApi();
    expect(await reg.register(api, { tenant: TENANT, accessToken: 'a', name: '  Van 14   tablet ' })).toEqual({
      deviceId: 'dev-1',
      name: 'Van 14 tablet',
    });
    expect(await reg.isRegistered()).toBe(true);

    const offlineReg = new DeviceRegister(new MemorySecretStore(), () => 'dev-2');
    api.online = false;
    await expect(offlineReg.register(api, { tenant: TENANT, accessToken: 'a', name: 'Van 9' })).rejects.toThrow();
    expect(await offlineReg.deviceName()).toBe('Van 9');
    expect(await offlineReg.isRegistered()).toBe(false);
  });

  test('a blank name is refused, a long one is cut to the server’s 80', () => {
    expect(() => normaliseDeviceName('   ')).toThrow(DeviceNameRequiredError);
    expect(normaliseDeviceName('x'.repeat(100))).toHaveLength(80);
  });
});

describe('the capture stamp', () => {
  const cred: CaptureCredential = {
    technicianId: 'tech-dana',
    userId: 'user-dana',
    tenant: TENANT,
    deviceId: 'dev-1',
    serverToken: 'signed-by-server',
    issuedAt: 0,
    expiresAt: 36 * HOUR_MS,
  };

  test('captured_by is the credential’s technician, with its token and device', () => {
    expect(stampFromCredential(cred, HOUR_MS)).toEqual({
      captured_by: 'tech-dana',
      capture_token: 'signed-by-server',
      device_id: 'dev-1',
      captured_at: new Date(HOUR_MS).toISOString(),
    });
  });

  test('an expired credential stamps nothing', () => {
    expect(() => stampFromCredential(cred, 36 * HOUR_MS)).toThrow(CaptureCredentialExpiredError);
  });
});

describe('the HTTP client against the server’s native sign-in (lane SRV-AUTH)', () => {
  type Reply = { status: number; body?: unknown };
  function server(replies: Reply[]) {
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const fetchImpl = jest.fn(async (url: string, init: RequestInit) => {
      calls.push({ url, init });
      const r = replies.shift() ?? { status: 500 };
      return { ok: r.status >= 200 && r.status < 300, status: r.status, json: async () => r.body ?? null };
    });
    return { calls, api: createHttpAuthApi({ baseUrl: 'https://app.example.com/', fetchImpl: fetchImpl as unknown as typeof fetch }) };
  }
  const body = (c: { init: RequestInit }) => JSON.parse(String(c.init.body));
  const pair = { access_token: 'sbh_fa_1', expires_in: 3600, refresh_token: 'sbh_fr_1', refresh_expires_in: 604800 };

  test('sign-in posts email, password and the device to auth/token and reads the pair and the person', async () => {
    const { calls, api } = server([{ status: 201, body: { ...pair, user: { id: 'u-dana', display_name: 'D. Ortiz', role: 'FIELD_TECHNICIAN' }, device: {} } }]);
    const res = await api.signIn({ tenant: TENANT, login: 'dana@silver.example', password: 'pw', deviceId: 'dev-1' });
    expect(calls[0]?.url).toBe(`https://app.example.com/api/${TENANT}/auth/token`);
    expect(body(calls[0]!)).toEqual({ identifier: 'dana@silver.example', password: 'pw', device_id: 'dev-1', device_name: '' });
    expect(res).toEqual({
      access: { token: 'sbh_fa_1', expiresInSeconds: 3600, refreshToken: 'sbh_fr_1' },
      user: { id: 'u-dana', displayName: 'D. Ortiz', role: 'FIELD_TECHNICIAN' },
      technician: { id: 'u-dana', displayName: 'D. Ortiz' },
    });
  });

  test('refresh sends the REFRESH token, never the access token, and reads the rotated pair', async () => {
    const { calls, api } = server([{ status: 200, body: { ...pair, access_token: 'sbh_fa_2', refresh_token: 'sbh_fr_2' } }]);
    const res = await api.refreshAccess({ tenant: TENANT, accessToken: 'sbh_fa_1', refreshToken: 'sbh_fr_1', deviceId: 'dev-1' });
    expect(calls[0]?.url).toBe(`https://app.example.com/api/${TENANT}/auth/token/refresh`);
    expect(body(calls[0]!)).toEqual({ refresh_token: 'sbh_fr_1', device_id: 'dev-1' });
    expect(res).toEqual({ token: 'sbh_fa_2', expiresInSeconds: 3600, refreshToken: 'sbh_fr_2' });
  });

  test('the office signing the handset out is told apart from a bad password', async () => {
    const signedOut = server([{ status: 401, body: { code: 'AUTH-001', message_key: 'x', params: { reason: 'device_signed_out' } } }]);
    await expect(signedOut.api.refreshAccess({ tenant: TENANT, accessToken: 'a', refreshToken: 'r', deviceId: 'd' })).rejects.toMatchObject({ name: 'DeviceSignedOutError' });
    const wrong = server([{ status: 401, body: { code: 'AUTH-001', message_key: 'x', params: {} } }]);
    await expect(wrong.api.signIn({ tenant: TENANT, login: 'e', password: 'p', deviceId: 'd' })).rejects.toMatchObject({ name: 'InvalidCredentialsError' });
    const temporary = server([{ status: 403, body: { code: 'AUTH-003', message_key: 'x', params: { reason: 'password_change_required' } } }]);
    await expect(temporary.api.signIn({ tenant: TENANT, login: 'e', password: 'p', deviceId: 'd' })).rejects.toMatchObject({ name: 'PasswordChangeRequiredError' });
  });

  test('sign-out deletes this bearer at auth/token', async () => {
    const { calls, api } = server([{ status: 204 }]);
    await api.signOut({ tenant: TENANT, accessToken: 'sbh_fa_1' });
    expect(calls[0]?.init.method).toBe('DELETE');
    expect((calls[0]?.init.headers as Record<string, string>).Authorization).toBe('Bearer sbh_fa_1');
  });

  test('the capture token is bound to the device; an unregistered handset is registered by name, then asked again', async () => {
    const { calls, api } = server([
      { status: 409, body: { code: 'BIZ-001', message_key: 'work.mobile.device_token_required', params: { reason: 'device_not_registered' } } },
      { status: 201, body: { device_id: 'reg-1', name: 'Van 14 tablet' } },
      { status: 200, body: { capture_token: 'tok', technician: { name: 'D. Ortiz' }, max_age_seconds: 259200, expires_at: '2026-10-24T07:30:00Z' } },
    ]);
    const res = await api.issueCaptureToken({ tenant: TENANT, accessToken: 'acc', deviceName: 'Van 14 tablet', deviceId: 'dev-1' });
    // The life is the tenant's setting, as the server states it (PO 2026-10-21, corrected).
    expect(res).toEqual({ captureToken: 'tok', maxAgeSeconds: 259200, technicianName: 'D. Ortiz', expiresAt: Date.parse('2026-10-24T07:30:00Z') });
    expect(calls.map((c) => c.url.replace(`https://app.example.com/api/${TENANT}/`, ''))).toEqual([
      'work/mobile/capture-token',
      'work/mobile/devices',
      'work/mobile/capture-token',
    ]);
    expect(body(calls[0]!)).toEqual({ device_label: 'Van 14 tablet', device_id: 'dev-1' });
    expect(body(calls[1]!)).toMatchObject({ device_id: 'dev-1', name: 'Van 14 tablet' });
  });

  test('activation: the check reads the person and the tenant’s own minimum; complete signs in', async () => {
    const { calls, api } = server([
      { status: 200, body: { display_name: 'Dana Ortiz', role_name: 'Field Technician', utility_name: 'Silver Creek', password_policy: { min_length: 12 }, activation_ticket: 'tkt' } },
      { status: 201, body: { ...pair, user: { id: 'u-dana', display_name: 'Dana Ortiz', role: 'FIELD_TECHNICIAN' } } },
    ]);
    const check: ActivationCheck = await api.checkActivationCode({ tenant: TENANT, code: 'K7M2AB', email: 'dana@x' });
    // Sent as `identifier`: the server takes a work email or a phone number there.
    expect(body(calls[0]!)).toEqual({ code: 'K7M2AB', identifier: 'dana@x' });
    expect(check).toEqual({ displayName: 'Dana Ortiz', roleLabel: 'Field Technician', utilityName: 'Silver Creek', passwordMinLength: 12, activationTicket: 'tkt' });
    const signed = await api.completeActivation({ tenant: TENANT, activationTicket: 'tkt', password: 'pw', deviceId: 'dev-1', deviceName: 'Van' });
    expect(signed.technician.id).toBe('u-dana');
    expect(body(calls[1]!)).toEqual({ activation_ticket: 'tkt', password: 'pw', device_id: 'dev-1', device_name: 'Van' });
  });

  test('no signal, or a server error, is OfflineError, which the session treats as uneventful', async () => {
    const fetchImpl = jest.fn(async () => {
      throw new TypeError('Network request failed');
    });
    const api = createHttpAuthApi({ baseUrl: 'https://x', fetchImpl: fetchImpl as unknown as typeof fetch });
    await expect(api.issueCaptureToken({ tenant: TENANT, accessToken: 'a', deviceName: 'Van' })).rejects.toMatchObject({ name: 'OfflineError' });
    const down = server([{ status: 503 }]);
    await expect(down.api.signIn({ tenant: TENANT, login: 'e', password: 'p', deviceId: 'd' })).rejects.toMatchObject({ name: 'OfflineError' });
  });

  test('every gap id still names itself (the fakes raise them for the "not ready" state)', () => {
    for (const gap of Object.keys(SERVER_GAPS)) {
      expect(new ServerGapError(gap as keyof typeof SERVER_GAPS).message).toContain(gap);
    }
  });
});

describe('storage helpers', () => {
  test('keystore keys stay inside the keystore’s alphabet', () => {
    expect(secretKey('handset', 'capture', 'tech/42 x')).toBe('handset.capture.tech_42_x');
  });

  test('the preference store’s key is 16 characters from the alphabet', () => {
    const key = randomKey((n) => Uint8Array.from({ length: n }, (_, i) => i * 37));
    expect(key).toHaveLength(16);
    expect(key).toMatch(/^[A-Za-z0-9]{16}$/);
  });
});
