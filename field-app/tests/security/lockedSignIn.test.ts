/**
 * A LOCKED SIGN-IN SAYS HOW LONG TO WAIT (`DEF-IDN-10620`; decision log
 * 2026-10-27, *"VAPT round: five findings ruled"*). PO: *"the same message has
 * to appear when the user was locked out"* — on the web and on the phone.
 *
 * The server answers a locked login (the attempt that locks it, and every
 * attempt while it is locked) with 401 `auth.sign_in.locked` and
 * `params.minutes` = the utility's own lock period from Settings › Security.
 * The phone says *"Too many wrong attempts. Try again in {{minutes}} minutes."*
 *
 * WHAT WOULD MAKE THIS PASS WRONGLY: asserting the error class while the
 * screen still maps it to *"Wrong email, phone or password."* So each case is
 * carried through `failureKey` / `failureParams`, the functions FF-05 calls,
 * and the English sentence is read from the shipped catalogue.
 */
import { FIELD_KEYS_EN } from '../../src/i18n/catalogues';
import { AccountLockedError, InvalidCredentialsError } from '../../src/security/authApi';
import { createHttpAuthApi } from '../../src/security/httpAuthApi';
import { failureKey, failureParams } from '../../src/screens/gettingIn/signInErrors';

const EN = FIELD_KEYS_EN as Record<string, string>;

function reply(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, json: async () => body, headers: { get: () => null } };
}

const api = (answer: () => Promise<unknown>) =>
  createHttpAuthApi({
    baseUrl: 'https://x',
    fetchImpl: (async () => answer()) as unknown as typeof fetch,
    appHeaders: () => ({}),
    onAppTooOld: () => undefined,
  });

const SIGN_IN = { tenant: 'north', login: 'd@x', password: 'pw', deviceId: 'dev' };

async function caught(p: Promise<unknown>): Promise<unknown> {
  try {
    await p;
  } catch (err) {
    return err;
  }
  throw new Error('expected a refusal');
}

describe('a locked sign-in (DEF-IDN-10620)', () => {
  test.each([5, 15, 60])('401 auth.sign_in.locked {minutes: %i} says the utility’s minutes', async (minutes) => {
    const err = await caught(
      api(async () =>
        reply(401, { code: 'AUTH-001', message_key: 'auth.sign_in.locked', params: { minutes } }),
      ).signIn(SIGN_IN),
    );
    expect(err).toBeInstanceOf(AccountLockedError);
    expect((err as AccountLockedError).minutes).toBe(minutes);
    expect(failureKey(err)).toBe('field.signIn.error.locked');
    expect(failureParams(err)).toEqual({ minutes });
    expect(EN['field.signIn.error.locked']).toBe('Too many wrong attempts. Try again in {{minutes}} minutes.');
  });

  test('a wrong password is still the one generic sentence, with no minutes', async () => {
    const err = await caught(
      api(async () => reply(401, { code: 'AUTH-001', message_key: 'errors.auth.sign_in_failed', params: {} })).signIn(
        SIGN_IN,
      ),
    );
    expect(err).toBeInstanceOf(InvalidCredentialsError);
    expect(err).not.toBeInstanceOf(AccountLockedError);
    expect(failureKey(err)).toBe('field.signIn.error.invalid');
    expect(failureParams(err)).toEqual({});
  });

  test('a locked key with no usable number is not believed — the generic sentence', async () => {
    const err = await caught(
      api(async () => reply(401, { code: 'AUTH-001', message_key: 'auth.sign_in.locked', params: {} })).signIn(SIGN_IN),
    );
    expect(failureKey(err)).toBe('field.signIn.error.invalid');
  });
});
