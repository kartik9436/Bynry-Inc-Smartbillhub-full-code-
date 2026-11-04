/**
 * The two credentials (design AD-21, rule R113, Security tab §1).
 *
 * Dana signs in at 07:30 on depot wi-fi and drives into a valley. Her access
 * token expires at 08:30. She has nine hours of work left and no signal. So
 * there are two credentials doing two different jobs:
 *
 *  - the ACCESS TOKEN — one hour, refreshed whenever there is a signal. It
 *    authorises TALKING TO THE SERVER and nothing else. Its expiry blocks
 *    SENDING, which is already asynchronous.
 *  - the CAPTURE CREDENTIAL — device-bound, for as long as the TENANT's setting
 *    says (the server states it with the token; default seven days — PO
 *    2026-10-21, corrected the same day), renewed on every
 *    successful contact. It authorises WRITING TO THE LOCAL STORE and is
 *    stamped on every captured item. Its expiry means a password before
 *    anything MORE is captured; the queue is untouched.
 *
 * There is no state in which captured work is thrown away to resolve an auth
 * problem. Nothing in this file, or in `session/`, can delete an outbox row —
 * see `session/outboxPort.ts`.
 */
import { DAY_MS, HOUR_MS } from './clock';

/** Design: *"Short-lived, one hour"*. The server's answer wins when it gives one. */
export const ACCESS_TOKEN_TTL_MS = 1 * HOUR_MS;

/** The FALLBACK only: the tenant's default of seven days, used when the server states no life (`captureExpiry`). */
export const CAPTURE_CREDENTIAL_TTL_MS = 7 * DAY_MS;

export interface AccessToken {
  token: string;
  /** Epoch ms. */
  expiresAt: number;
  /** The server's single-use refresh token (rotated on every refresh), when it gave one. */
  refreshToken?: string | null;
}

export interface CaptureCredential {
  technicianId: string;
  userId: string;
  /** The tenant slug the credential was issued under — the database file it may write. */
  tenant: string;
  /** The handset it was issued to (`deviceRegister.ts`). */
  deviceId: string;
  /**
   * The signed capture token the server already verifies per item
   * (`06-backend/apps/work/mobile.py`, `issue_capture_token`, BR-WRK-059).
   * Opaque to the handset: it cannot read, forge or edit it.
   */
  serverToken: string;
  issuedAt: number;
  expiresAt: number;
}

/**
 * When a freshly issued capture credential stops being good on THIS handset.
 *
 * PO 2026-10-21 (decision log, "the PO corrects four of the ten answers"):
 * the life is a TENANT SETTING on the server, default seven days — so the
 * phone hard-codes neither 36 hours nor 7 days. It takes what the server
 * answers with the token: an absolute `expires_at` if it sends one, else its
 * `max_age_seconds`. Only when the server gives neither does the handset fall
 * back to `CAPTURE_CREDENTIAL_TTL_MS` (seven days, the tenant default).
 */
export function captureExpiry(
  issuedAt: number,
  serverMaxAgeSeconds: number | null | undefined,
  serverExpiresAt?: number | null,
): number {
  if (serverExpiresAt != null && Number.isFinite(serverExpiresAt) && serverExpiresAt > issuedAt) return serverExpiresAt;
  if (serverMaxAgeSeconds != null && Number.isFinite(serverMaxAgeSeconds) && serverMaxAgeSeconds > 0) {
    return issuedAt + serverMaxAgeSeconds * 1000;
  }
  return issuedAt + CAPTURE_CREDENTIAL_TTL_MS;
}

export function isAccessValid(token: AccessToken | null | undefined, now: number): boolean {
  return token != null && now < token.expiresAt;
}

export function isCaptureValid(cred: CaptureCredential | null | undefined, now: number): boolean {
  return cred != null && now < cred.expiresAt;
}
