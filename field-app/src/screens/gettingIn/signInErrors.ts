/**
 * What a failed sign-in, unlock or activation SAYS — one short sentence per
 * cause (B14 rule 33: a fact ≤ 6 words), never the error's own text.
 *
 *   locked                — too many wrong attempts: the utility's own minutes,
 *                           from the server (`DEF-IDN-10620`)
 *   wrong ID or password  — the server's refusal; deliberately says no more
 *   claim with a code     — a temporary password: the phone's door is FF-56
 *   can't verify server   — the phone refused the server's certificate
 *                           (`CertificateRefusedError`, DEF-FLD-10617)
 *   server needs update   — the door is missing or answered something that
 *                           is not its JSON (`ServerOutdatedError`)
 *   no signal             — and this technician has never signed in on this
 *                           handset, so there is nothing to check offline
 *   not ready             — the server route does not exist yet
 *                           (`ServerGapError`): the native sign-in, the
 *                           activation calls. Named in code by its gap id.
 *   anything else         — try again
 */
import {
  AccountLockedError,
  CertificateRefusedError,
  InvalidCredentialsError,
  OfflineError,
  PasswordChangeRequiredError,
  ServerGapError,
  ServerOutdatedError,
} from '../../security/authApi';
import { ActivationCodeShapeError } from '../../security/activation';
import { NoServerError } from '../../release/serverAddress';
import { BiometricNotAllowedError } from '../../session/sessionManager';

export function failureKey(err: unknown): string {
  // The BUILD has no server address (`release/serverAddress.ts`) — not the person's fault, not the signal's.
  if (err instanceof NoServerError) return 'field.signIn.noServer';
  if (err instanceof PasswordChangeRequiredError) return 'field.signIn.error.claim';
  // Asked before InvalidCredentialsError, which it extends (DEF-IDN-10620).
  if (err instanceof AccountLockedError) return 'field.signIn.error.locked';
  if (err instanceof InvalidCredentialsError) return 'field.signIn.error.invalid';
  // Both are OfflineErrors (capture carries on) — so they are asked FIRST.
  if (err instanceof CertificateRefusedError) return 'field.signIn.error.certificate';
  if (err instanceof ServerOutdatedError) return 'field.signIn.error.outdated';
  if (err instanceof OfflineError) return 'field.signIn.error.offline';
  if (err instanceof ServerGapError) return 'field.signIn.error.notReady';
  if (err instanceof ActivationCodeShapeError) return 'field.activate.error.shape';
  if (err instanceof BiometricNotAllowedError) return 'field.lock.error.biometric';
  return 'field.signIn.error.other';
}

/** The values `failureKey`'s sentence needs — only a lock has any (`{minutes}`). */
export function failureParams(err: unknown): Record<string, number> {
  return err instanceof AccountLockedError ? { minutes: err.minutes } : {};
}
