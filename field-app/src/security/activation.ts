/**
 * Activation, client side (FF-56 *First time here*, FF-57 *Your password*;
 * requirement 70, rule R105).
 *
 * The office creates the account; the app only CLAIMS one that exists, with a
 * six-character code good for seven days, the technician's own password, and
 * the device registered by name. Technicians never self-register.
 *
 * What is the client's to check is checked here — the code's SHAPE, the two
 * password entries agreeing, the tenant's own minimum length. Whether a code
 * is real, unexpired and unused, and whether a password was used before, are
 * the SERVER's answers (`activation-check`, `activation-complete` in
 * `SERVER_GAPS`) and are never guessed on the handset.
 */
import { type ActivationCheck, type ActivationLookup, type AuthApi, type SignInResult } from './authApi';

/** FF-56: *"They gave you a six-character code."* */
export const ACTIVATION_CODE_LENGTH = 6;
/** FF-56: *"It lasts seven days."* Enforced by the server; stated here so the copy and the code agree. */
export const ACTIVATION_CODE_VALID_DAYS = 7;

/**
 * Upper-case, spaces and dashes dropped — the code is read off an email or a
 * phone call, and "k7m 2ab" is the same code as "K7M2AB".
 */
export function normaliseActivationCode(raw: string): string {
  return raw.replace(/[\s-]+/g, '').toUpperCase();
}

export function isActivationCodeShaped(raw: string): boolean {
  return new RegExp(`^[A-Z0-9]{${ACTIVATION_CODE_LENGTH}}$`).test(normaliseActivationCode(raw));
}

export interface PasswordCheck {
  /** FF-57: "At least ten characters" — the number is the TENANT's policy, never a constant. */
  longEnough: boolean;
  /** FF-57: "Type it once more". */
  matches: boolean;
  /** Both of the above. Reuse is the server's to refuse. */
  ok: boolean;
}

export function checkNewPassword(password: string, again: string, minLength: number): PasswordCheck {
  const longEnough = password.length >= minLength;
  const matches = again.length > 0 && password === again;
  return { longEnough, matches, ok: longEnough && matches };
}

export class ActivationCodeShapeError extends Error {
  constructor() {
    super('an activation code is six letters or digits');
    this.name = 'ActivationCodeShapeError';
  }
}

export class PasswordNotAcceptedError extends Error {
  readonly check: PasswordCheck;

  constructor(check: PasswordCheck) {
    super('the new password does not pass the checks');
    this.name = 'PasswordNotAcceptedError';
    this.check = check;
  }
}

/**
 * FF-56's first call (`DEF-FLD-10580`): which utility holds this code. No
 * utility is sent — the code is what names it. Refuses a malformed code before
 * spending a request on it (the door is rate-limited per phone).
 */
export async function lookupActivationCode(
  api: AuthApi,
  input: { code: string; deviceId: string },
): Promise<ActivationLookup> {
  if (!isActivationCodeShaped(input.code)) throw new ActivationCodeShapeError();
  return api.lookupActivationCode({ code: normaliseActivationCode(input.code), deviceId: input.deviceId });
}

/** FF-56 → the server. Refuses a malformed code before spending a request on it. */
export async function checkActivationCode(
  api: AuthApi,
  input: { tenant: string; code: string; email: string },
): Promise<ActivationCheck> {
  if (!isActivationCodeShaped(input.code)) throw new ActivationCodeShapeError();
  return api.checkActivationCode({
    tenant: input.tenant,
    code: normaliseActivationCode(input.code),
    email: input.email.trim(),
  });
}

/** FF-57 → the server: own password + device by name, then signed in. */
export async function completeActivation(
  api: AuthApi,
  input: {
    tenant: string;
    check: ActivationCheck;
    password: string;
    again: string;
    deviceId: string;
    deviceName: string;
  },
): Promise<SignInResult> {
  const check = checkNewPassword(input.password, input.again, input.check.passwordMinLength);
  if (!check.ok) throw new PasswordNotAcceptedError(check);
  return api.completeActivation({
    tenant: input.tenant,
    activationTicket: input.check.activationTicket,
    password: input.password,
    deviceId: input.deviceId,
    deviceName: input.deviceName,
  });
}
