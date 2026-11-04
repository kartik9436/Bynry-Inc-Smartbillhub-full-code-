/**
 * `AuthApi` over HTTP, against the server's native sign-in
 * (`06-backend/apps/identity/native.py`, `CR-187-BRC10` lane SRV-AUTH; wired
 * in the integration lane):
 *
 *   POST   /api/{t}/auth/token                {identifier, password, device_id, device_name}
 *          → 201 {access_token, expires_in, refresh_token, refresh_expires_in,
 *                 user: {id, display_name, role, role_name}, device}
 *   POST   /api/{t}/auth/token/refresh        {refresh_token, device_id}  → a new pair
 *          (SINGLE USE: the refresh token is rotated every time — the access
 *          token is NOT what it takes, which is the mismatch this file used
 *          to have with the server.)
 *   DELETE /api/{t}/auth/token                (the bearer in the header)
 *   POST   /api/{t}/auth/activation/check     {code, identifier}
 *   POST   /api/{t}/auth/activation/complete  {activation_ticket, password, device_id, device_name}
 *   POST   /api/{t}/work/mobile/devices       {device_id, name, platform, push_token?}
 *   POST   /api/{t}/work/mobile/capture-token {device_id, device_label} — bound to
 *          the registered device; an unregistered handset is refused with
 *          `params.reason: "device_not_registered"`, so this client registers
 *          it by name and asks once more.
 *
 * Every refusal is the server's BE-02 envelope `{code, message_key, params, …}`;
 * `params.reason` tells the cases the phone must act on apart:
 *   401 `device_signed_out`        → DeviceSignedOutError (drop the mirror, keep the outbox, R115)
 *   401 `auth.sign_in.locked`     → AccountLockedError(minutes) — the utility's lock period
 *                                    (DEF-IDN-10620); it IS an InvalidCredentialsError
 *   401 `refresh_token_expired`,
 *       `token_revoked`, unknown   → InvalidCredentialsError (a password is needed)
 *   403 `password_change_required` → PasswordChangeRequiredError (FF-56's activation code)
 *   no answer, or 5xx              → OfflineError (capture carries on, sending waits)
 *   a refused certificate          → CertificateRefusedError (an OfflineError that says
 *                                    *Can't verify the server*, DEF-FLD-10617)
 *   a door that is missing, or an
 *   answer that is not its JSON    → ServerOutdatedError (an OfflineError that says
 *                                    *The server needs an update*, DEF-FLD-10617):
 *                                    a 404/405 that is not the BE-02 envelope (an
 *                                    HTML page), a 2xx that is not JSON, or JSON
 *                                    missing what the door must answer
 *   426 `app_too_old`              → OfflineError too, AND the app's one `appUpdate`
 *                                    signal is raised, so *Update the app* covers the
 *                                    screen (DEF-FLD-10355). Nothing held is dropped.
 *
 * Every request carries the build: `X-Field-App-Version`, `-Build`, `-Platform`
 * (`release/appUpdate.ts`), which the server compares with its minimum.
 *
 * ⚠ ONE SIGN-IN FIELD: WORK EMAIL OR PHONE NUMBER (PO 2026-10-21, `CR-187-BRC10`;
 * there is no Technician ID). What is typed on FF-05 is sent as `identifier`
 * and the server decides which it is (`@` → email, else a phone in E.164).
 * The server still accepts the older `email` field. ⚠ THE SERVER NAMES NO
 * TECHNICIAN in the sign-in answer, so the person's USER id is the handset's
 * technician key (it scopes their rows on the phone, R133, and is stable for
 * the person); both are reported.
 */
import { appUpdate, fieldAppHeaders, tooOldMinimum } from '../release/appUpdate';
import { requireServer } from '../release/serverAddress';
import { isCertificateRefusal } from './certificateRefusal';
import {
  AccountLockedError,
  type ActivationCheck,
  type ActivationLookup,
  type AuthApi,
  type CaptureTokenResult,
  CertificateRefusedError,
  DeviceSignedOutError,
  InvalidCredentialsError,
  OfflineError,
  PasswordChangeRequiredError,
  ServerOutdatedError,
  type SignInResult,
} from './authApi';

export interface HttpAuthApiConfig {
  /** e.g. `https://app.example.com` — the API lives under `/api/{tenant}/`. */
  baseUrl: string;
  fetchImpl?: typeof fetch;
  /** `ios` | `android` — what the device registration records. */
  platform?: 'ios' | 'android' | 'web';
  /** The build's headers on every request (default `fieldAppHeaders()`). */
  appHeaders?: () => Record<string, string>;
  /** Told when the server refuses this build (default: the app's one `appUpdate` signal). */
  onAppTooOld?: (minimum: string | null) => void;
}

/** Refuses (`NoServerError`) rather than build a relative `/api/…` address — see `release/serverAddress.ts`. */
function apiUrl(baseUrl: string, tenant: string | null, path: string): string {
  // `tenant: null` is the ONE utility-free door, `auth/activation/lookup` (DEF-FLD-10580).
  return tenant === null
    ? `${requireServer(baseUrl)}/api/${path}`
    : `${requireServer(baseUrl)}/api/${encodeURIComponent(tenant)}/${path}`;
}

/** The server's refusal for a locked login (`apps/identity/services.LOCKED_MESSAGE_KEY`). */
export const LOCKED_MESSAGE_KEY = 'auth.sign_in.locked';

/** The header the lookup door counts tries per device by (`identity.api.DEVICE_ID_HEADER`). */
export const DEVICE_ID_HEADER = 'X-Device-Id';

interface Envelope {
  code?: string | null;
  message_key?: string;
  params?: { reason?: string } & Record<string, unknown>;
}

class HttpRefusal extends Error {
  constructor(
    readonly status: number,
    readonly body: Envelope | null,
  ) {
    super(`HTTP ${status}`);
    this.name = 'HttpRefusal';
  }
  get reason(): string | null {
    return typeof this.body?.params?.reason === 'string' ? this.body.params.reason : null;
  }
}

/** The server's own refusal shape (BE-02): an object naming a code or a message key. */
function isEnvelope(body: unknown): boolean {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return false;
  const b = body as Envelope & { detail?: unknown };
  return typeof b.code === 'string' || typeof b.message_key === 'string' || typeof b.detail === 'string';
}

/** A refusal as the session reads it. */
function asAuthError(err: unknown): unknown {
  if (!(err instanceof HttpRefusal)) return err;
  if (err.reason === 'device_signed_out') return new DeviceSignedOutError();
  if (err.reason === 'password_change_required') return new PasswordChangeRequiredError();
  // DEF-IDN-10620 — a locked login says the utility's minutes. A key with no
  // usable number is not believed: it reads as the one generic refusal.
  const minutes = err.body?.params?.minutes;
  if (
    err.status === 401 &&
    err.body?.message_key === LOCKED_MESSAGE_KEY &&
    typeof minutes === 'number' &&
    Number.isFinite(minutes) &&
    minutes > 0
  ) {
    return new AccountLockedError(minutes);
  }
  if (err.status === 401 || err.status === 403) return new InvalidCredentialsError();
  if (err.status === 404 || err.status === 400 || err.status === 422 || err.status === 429) return new InvalidCredentialsError();
  return new OfflineError(err);
}

interface TokenPair {
  access_token?: unknown;
  expires_in?: unknown;
  refresh_token?: unknown;
}

function accessOf(body: TokenPair): SignInResult['access'] {
  if (typeof body.access_token !== 'string' || body.access_token === '') {
    throw new ServerOutdatedError(new Error('auth/token: no access token in the answer'));
  }
  return {
    token: body.access_token,
    expiresInSeconds: typeof body.expires_in === 'number' ? body.expires_in : 3600,
    refreshToken: typeof body.refresh_token === 'string' ? body.refresh_token : null,
  };
}

function signInOf(body: TokenPair & { user?: { id?: unknown; display_name?: unknown; role?: unknown } }): SignInResult {
  const id = typeof body.user?.id === 'string' ? body.user.id : '';
  const name = typeof body.user?.display_name === 'string' ? body.user.display_name : '';
  if (!id) throw new ServerOutdatedError(new Error('auth/token: no user in the answer'));
  return {
    access: accessOf(body),
    user: { id, displayName: name, role: typeof body.user?.role === 'string' ? body.user.role : '' },
    technician: { id, displayName: name },
  };
}

export function createHttpAuthApi(config: HttpAuthApiConfig): AuthApi {
  const doFetch = config.fetchImpl ?? fetch;
  const platform = config.platform ?? 'android';

  async function call<T>(
    tenant: string | null,
    path: string,
    init: { method: string; body?: unknown; bearer?: string; headers?: Record<string, string> },
  ): Promise<T> {
    // Outside the try: no address is the BUILD's fault, never "no signal".
    const url = apiUrl(config.baseUrl, tenant, path);
    let res: Response;
    try {
      res = await doFetch(url, {
        method: init.method,
        headers: {
          ...(config.appHeaders ?? fieldAppHeaders)(),
          Accept: 'application/json',
          ...(init.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
          ...(init.bearer ? { Authorization: `Bearer ${init.bearer}` } : {}),
          ...(init.headers ?? {}),
        },
        ...(init.body !== undefined ? { body: JSON.stringify(init.body) } : {}),
      });
    } catch (err) {
      // A refused certificate is not "no signal" (DEF-FLD-10617).
      throw isCertificateRefusal(err) ? new CertificateRefusedError(err) : new OfflineError(err);
    }
    if (res.status === 204) return undefined as T;
    const NOT_JSON = Symbol('not json');
    const parsed = (await res.json().catch(() => NOT_JSON)) as unknown;
    const body = parsed === NOT_JSON ? null : parsed;
    const minimum = tooOldMinimum(res.status, body);
    if (minimum !== undefined) {
      // This BUILD is refused, not the person: never read as a wrong password,
      // which would drop the held sign-in. Offline = everything held, sending waits.
      (config.onAppTooOld ?? ((m) => appUpdate.raise(m)))(minimum);
      throw new OfflineError(new Error(`${path} app_too_old`));
    }
    if (res.status >= 500) throw new OfflineError(new Error(`${path} ${res.status}`));
    // The door is not there: a 404/405 that is not the server's own refusal
    // (an HTML page) — this server predates the build (DEF-FLD-10617).
    if ((res.status === 404 || res.status === 405) && !isEnvelope(body)) {
      throw new ServerOutdatedError(new Error(`${path} ${res.status} without the server's refusal`));
    }
    if (!res.ok) throw new HttpRefusal(res.status, body as Envelope | null);
    // Every auth door answers a JSON object; anything else is not this server's answer.
    if (parsed === NOT_JSON || !body || typeof body !== 'object') {
      throw new ServerOutdatedError(new Error(`${path} ${res.status} answered no JSON`));
    }
    return body as T;
  }

  const guarded = async <T>(run: () => Promise<T>): Promise<T> => {
    try {
      return await run();
    } catch (err) {
      throw asAuthError(err);
    }
  };

  const register = (tenant: string, accessToken: string, deviceId: string, name: string, pushToken?: string) =>
    call<{ device_id?: unknown; name?: unknown }>(tenant, 'work/mobile/devices', {
      method: 'POST',
      bearer: accessToken,
      body: { device_id: deviceId, name, platform, ...(pushToken ? { push_token: pushToken } : {}) },
    });

  return {
    signIn: ({ tenant, login, password, deviceId }) =>
      guarded(async () =>
        signInOf(
          await call(tenant, 'auth/token', { method: 'POST', body: { identifier: login, password, device_id: deviceId, device_name: '' } }),
        ),
      ),

    refreshAccess: ({ tenant, refreshToken, deviceId }) =>
      guarded(async () => {
        // The server takes the REFRESH token; with none held, a password is needed.
        if (!refreshToken) throw new InvalidCredentialsError();
        return accessOf(await call(tenant, 'auth/token/refresh', { method: 'POST', body: { refresh_token: refreshToken, device_id: deviceId } }));
      }),

    signOut: ({ tenant, accessToken }) =>
      guarded(async () => {
        await call(tenant, 'auth/token', { method: 'DELETE', bearer: accessToken });
      }),

    issueCaptureToken: ({ tenant, accessToken, deviceName, deviceId }) =>
      guarded(async () => {
        const ask = () =>
          call<{ capture_token?: unknown; max_age_seconds?: unknown; expires_at?: unknown; technician?: { name?: unknown } }>(tenant, 'work/mobile/capture-token', {
            method: 'POST',
            bearer: accessToken,
            body: { device_label: deviceName, ...(deviceId ? { device_id: deviceId } : {}) },
          });
        let body;
        try {
          body = await ask();
        } catch (err) {
          if (!(err instanceof HttpRefusal) || err.reason !== 'device_not_registered' || !deviceId) throw err;
          // An unregistered handset: register it by name, then ask once more.
          await register(tenant, accessToken, deviceId, deviceName);
          body = await ask();
        }
        if (typeof body.capture_token !== 'string' || body.capture_token === '') {
          throw new ServerOutdatedError(new Error('capture-token: no token in the answer'));
        }
        const result: CaptureTokenResult = {
          captureToken: body.capture_token,
          maxAgeSeconds: typeof body.max_age_seconds === 'number' ? body.max_age_seconds : 0,
          technicianName: typeof body.technician?.name === 'string' ? body.technician.name : '',
        };
        const ends = typeof body.expires_at === 'string' ? Date.parse(body.expires_at) : NaN;
        if (Number.isFinite(ends)) result.expiresAt = ends;
        return result;
      }),

    registerDevice: ({ tenant, accessToken, deviceId, name, pushToken }) =>
      guarded(async () => {
        const body = await register(tenant, accessToken, deviceId, name, pushToken);
        return { deviceId: typeof body?.device_id === 'string' ? body.device_id : deviceId, name: typeof body?.name === 'string' ? body.name : name };
      }),

    lookupActivationCode: ({ code, deviceId }) =>
      guarded(async () => {
        const body = await call<{ tenant?: unknown; utility_name?: unknown }>(null, 'auth/activation/lookup', {
          method: 'POST',
          body: { code },
          headers: { [DEVICE_ID_HEADER]: deviceId },
        });
        if (typeof body.tenant !== 'string' || body.tenant === '') {
          throw new ServerOutdatedError(new Error('activation/lookup: no utility in the answer'));
        }
        const out: ActivationLookup = {
          tenant: body.tenant,
          utilityName: typeof body.utility_name === 'string' ? body.utility_name : '',
        };
        return out;
      }),

    checkActivationCode: ({ tenant, code, email }) =>
      guarded(async () => {
        const body = await call<{
          display_name?: unknown;
          role_name?: unknown;
          utility_name?: unknown;
          password_policy?: { min_length?: unknown };
          activation_ticket?: unknown;
        }>(tenant, 'auth/activation/check', { method: 'POST', body: { code, identifier: email } });
        // The tenant's own minimum is the server's to say; never a number made up here.
        if (typeof body.activation_ticket !== 'string' || typeof body.password_policy?.min_length !== 'number') {
          throw new ServerOutdatedError(new Error('activation/check: no ticket or no password policy'));
        }
        const out: ActivationCheck = {
          displayName: typeof body.display_name === 'string' ? body.display_name : '',
          roleLabel: typeof body.role_name === 'string' ? body.role_name : '',
          utilityName: typeof body.utility_name === 'string' ? body.utility_name : '',
          passwordMinLength: Number(body.password_policy?.min_length),
          activationTicket: body.activation_ticket,
        };
        return out;
      }),

    completeActivation: ({ tenant, activationTicket, password, deviceId, deviceName }) =>
      guarded(async () =>
        signInOf(
          await call(tenant, 'auth/activation/complete', {
            method: 'POST',
            body: { activation_ticket: activationTicket, password, device_id: deviceId, device_name: deviceName },
          }),
        ),
      ),
  };
}
