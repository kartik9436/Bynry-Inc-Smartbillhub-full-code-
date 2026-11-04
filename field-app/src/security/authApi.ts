/**
 * What the handset needs from the server to sign people in, as an interface.
 *
 * The server's native half landed with `CR-187-BRC10` lane SRV-AUTH
 * (`06-backend/apps/identity/native.py`): bearer sign-in, a single-use rotated
 * refresh token, sign-out, activation check and complete, devices by name, and
 * a capture token bound to the registered device — `httpAuthApi.ts` calls them.
 * `SERVER_GAPS` keeps the list of what the server has NOT got, and a call that
 * needs one of those throws `ServerGapError` naming it. Nothing is guessed.
 */

export interface SignInResult {
  /** The access token (one hour) and, from the native sign-in, the single-use refresh token. */
  access: { token: string; expiresInSeconds: number; refreshToken?: string | null };
  user: { id: string; displayName: string; role: string };
  technician: { id: string; displayName: string };
}

export interface CaptureTokenResult {
  /** `capture_token` — the server's signed token (BR-WRK-059). */
  captureToken: string;
  /** `max_age_seconds` as the server states it (the tenant's setting). */
  maxAgeSeconds: number;
  /** `expires_at`, epoch ms, when the server states an absolute end. */
  expiresAt?: number | null;
  technicianName: string;
}

export interface DeviceRegistration {
  deviceId: string;
  name: string;
}

export interface ActivationCheck {
  /** Who the office created the account for — shown as "Code accepted. Dana Ortiz · Field Technician". */
  displayName: string;
  roleLabel: string;
  utilityName: string;
  /** The tenant's own password policy minimum (identity `pw_min_length`, one of 8 · 10 · 12). */
  passwordMinLength: number;
  /** Opaque, single-use; carries the claim from FF-56 to FF-57. */
  activationTicket: string;
}

/**
 * FF-56's first answer (`DEF-FLD-10580`): which utility holds this code. The
 * app is one build for every utility, so the office's code is how a handset
 * learns where it works (PO 2026-10-24, *"the code from the office sets the
 * utility"*).
 */
export interface ActivationLookup {
  /** The utility's slug — every later call's path, and the store's file name. */
  tenant: string;
  /** *City of Houston*, as the server names it. */
  utilityName: string;
}

export interface AuthApi {
  /** FF-56: `POST /api/auth/activation/lookup` — no utility in the path; the code names it. */
  lookupActivationCode(input: { code: string; deviceId: string }): Promise<ActivationLookup>;
  /** Password sign-in for a native app → a one-hour access token. */
  signIn(input: { tenant: string; login: string; password: string; deviceId: string }): Promise<SignInResult>;
  /** A new access token, while there is a signal. */
  refreshAccess(input: { tenant: string; accessToken: string; refreshToken?: string | null; deviceId: string }): Promise<SignInResult['access']>;
  /** Server sign-out of THIS access token. Never touches the handset's outbox. */
  signOut(input: { tenant: string; accessToken: string }): Promise<void>;
  /** `POST /work/mobile/capture-token` — exists, but only behind a cookie session today. */
  issueCaptureToken(input: { tenant: string; accessToken: string; deviceName: string; deviceId?: string }): Promise<CaptureTokenResult>;
  /** Register this handset by NAME ("Van 14 tablet"), bound to the capture credential. */
  /** `pushToken` (optional) is the platform's push token, which the server moves to whoever registers it (BR-WRK-059). */
  registerDevice(input: { tenant: string; accessToken: string; deviceId: string; name: string; pushToken?: string }): Promise<DeviceRegistration>;
  /** FF-56: check a six-character activation code against a work email (or phone — the server takes either). */
  checkActivationCode(input: { tenant: string; code: string; email: string }): Promise<ActivationCheck>;
  /** FF-57: set the technician's own password with the ticket from FF-56, then sign in. */
  completeActivation(input: {
    tenant: string;
    activationTicket: string;
    password: string;
    deviceId: string;
    deviceName: string;
  }): Promise<SignInResult>;
}

/**
 * The server calls the app asked for. All but `device-signature` were answered
 * by lane SRV-AUTH (2026-10-21) and `httpAuthApi.ts` calls them; the ids are
 * kept because a test fake may still raise one to show the *not ready* state.
 */
export const SERVER_GAPS = {
  'native-sign-in': {
    endpoint: 'POST /api/{tenant}/auth/token',
    need: 'Password sign-in for a native app that returns a bearer access token (1 hour) instead of a browser cookie, bound to a device id.',
  },
  'native-refresh': {
    endpoint: 'POST /api/{tenant}/auth/token/refresh',
    need: 'A new access token while there is a signal, refused for a device the office has signed out.',
  },
  'native-sign-out': {
    endpoint: 'DELETE /api/{tenant}/auth/token',
    need: 'Revoke one bearer access token.',
  },
  'bearer-on-work-mobile': {
    endpoint: 'every /api/{tenant}/work/mobile/* route',
    need: 'Accept the bearer access token. Today they authenticate only the cookie session (identity SessionAuthentication).',
  },
  'device-by-name': {
    endpoint: 'POST /api/{tenant}/work/mobile/devices (extend) or a new devices route',
    need: 'Register a handset by NAME and device id without a push token, bind it to the capture credential, and let the office list and sign out devices. Today the route registers a push token and requires one.',
  },
  'device-signature': {
    endpoint: 'POST /api/{tenant}/work/mobile/jobs/{id}/sync (and photo/signature routes)',
    need: 'Check each item against the device registration. Today the server verifies the capture token alone; a device-held key signature is not designed on the server.',
  },
  'activation-lookup': {
    endpoint: 'POST /api/auth/activation/lookup',
    need: 'Say which utility holds a six-character code, with no utility in the path (DEF-FLD-10580).',
  },
  'activation-check': {
    endpoint: 'POST /api/{tenant}/auth/activation/check',
    need: 'Check a six-character code (good for seven days) against a work email; answer who it is for and the tenant password minimum.',
  },
  'activation-complete': {
    endpoint: 'POST /api/{tenant}/auth/activation/complete',
    need: 'Set the technician\'s own password (policy checked, not a reused one), register the device by name, and sign in.',
  },
  'remote-sign-out': {
    endpoint: 'a signal on refresh or sync (e.g. 401 with a "device_signed_out" code)',
    need: 'Tell the handset its device was signed out from the back office, so it drops the mirror and keeps the outbox.',
  },
} as const;

export type ServerGapId = keyof typeof SERVER_GAPS;

/** Thrown by any call that needs a server endpoint which does not exist yet. */
export class ServerGapError extends Error {
  readonly gap: ServerGapId;

  constructor(gap: ServerGapId) {
    super(`server gap ${gap}: ${SERVER_GAPS[gap].endpoint} — ${SERVER_GAPS[gap].need}`);
    this.name = 'ServerGapError';
    this.gap = gap;
  }
}

/** The server said: wrong login or password. Deliberately says nothing more. */
export class InvalidCredentialsError extends Error {
  constructor() {
    super('invalid credentials');
    this.name = 'InvalidCredentialsError';
  }
}

/**
 * The server said: this login is LOCKED (`DEF-IDN-10620`) — the attempt that
 * locked it, or any attempt while it is locked. `minutes` is the utility's own
 * lock period from Settings › Security, sent by the server; never a constant.
 * An `InvalidCredentialsError`, so every caller that treats a refused password
 * as "a password is needed" still does.
 */
export class AccountLockedError extends InvalidCredentialsError {
  constructor(readonly minutes: number) {
    super();
    this.name = 'AccountLockedError';
  }
}

/** No signal, or the server could not be reached. Capture carries on. */
export class OfflineError extends Error {
  constructor(cause?: unknown) {
    super('offline');
    this.name = 'OfflineError';
    (this as { cause?: unknown }).cause = cause;
  }
}

/**
 * The phone refused the server's certificate (pinning, or a chain it does not
 * trust) — *"Can't verify the server. Contact the office."*, never *No
 * signal* (`DEF-FLD-10617`; decision log 2026-10-26). An `OfflineError` on
 * purpose: nothing was sent, a known technician still gets in offline and
 * capture carries on; only the words differ.
 */
export class CertificateRefusedError extends OfflineError {
  constructor(cause?: unknown) {
    super(cause);
    this.name = 'CertificateRefusedError';
  }
}

/**
 * The server answered, but the door is missing or its answer is not the JSON
 * this build expects (a 404 HTML page, a 200 that is not JSON, an answer with
 * none of the fields the door must carry) — *"The server needs an update."*
 * (`DEF-FLD-10617`). An `OfflineError` for the same reason as the one above.
 */
export class ServerOutdatedError extends OfflineError {
  constructor(cause?: unknown) {
    super(cause);
    this.name = 'ServerOutdatedError';
  }
}

/** The login holds a temporary or expired password: claim it with an activation code (FF-56). */
export class PasswordChangeRequiredError extends Error {
  constructor() {
    super('password change required — use an activation code');
    this.name = 'PasswordChangeRequiredError';
  }
}

/** The office signed this handset out (Security tab §4, R115). */
export class DeviceSignedOutError extends Error {
  constructor() {
    super('device signed out remotely');
    this.name = 'DeviceSignedOutError';
  }
}
