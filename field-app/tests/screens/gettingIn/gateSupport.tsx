/**
 * The signed-out gate, mounted the way the app mounts it — the real
 * navigation tree, the real session manager — with the shared fake server
 * taught the two activation calls it refuses by default.
 */
import { act, screen } from '@testing-library/react-native';

import { type ScreenId } from '../../../src/navigation/screens';
import type { ActivationCheck, ActivationLookup, AuthApi } from '../../../src/security/authApi';
import { InvalidCredentialsError } from '../../../src/security/authApi';
import { openScreen } from '../../../src/screens/theDay/go';
import { mountApp, type MountOptions } from '../../navigation/harness';
import { type FakeAuthApi, makeHandset, PEOPLE, TENANT } from '../../session/fakes';

export const DANA_EMAIL = 'dana.ortiz@lonestarwater.gov';
export const CODE = 'K7M2AB';

/** The utility the office's code names (`DEF-FLD-10580`): the lookup's answer for `CODE`. */
export const LOOKUP: ActivationLookup = { tenant: TENANT, utilityName: 'Lone Star Water' };

export const CHECK: ActivationCheck = {
  displayName: 'Dana Ortiz',
  roleLabel: 'Field Technician',
  utilityName: 'Lone Star Water',
  passwordMinLength: 10,
  activationTicket: 'ticket-1',
};

export interface ActivationLog {
  looked: Array<{ code: string; deviceId: string }>;
  checked: Array<{ code: string; email: string; tenant: string }>;
  completed: Array<{ password: string; deviceName: string; deviceId: string }>;
}

/**
 * The server with an office-made account for Dana's work email: the code
 * checks, the password is set, and her new password then signs her in by
 * that email.
 */
export function teachActivation(fake: FakeAuthApi): ActivationLog {
  // The shared fake declares the two calls as refusals; this widens them to the real interface.
  const api = fake as unknown as AuthApi;
  const log: ActivationLog = { looked: [], checked: [], completed: [] };
  let newPassword: string | null = null;
  const signIn = api.signIn.bind(api);
  api.lookupActivationCode = async (input) => {
    log.looked.push({ code: input.code, deviceId: input.deviceId });
    if (input.code !== CODE) throw new InvalidCredentialsError();
    return LOOKUP;
  };
  api.checkActivationCode = async (input) => {
    log.checked.push({ code: input.code, email: input.email, tenant: input.tenant });
    if (input.code !== CODE || input.email !== DANA_EMAIL) throw new InvalidCredentialsError();
    return CHECK;
  };
  api.completeActivation = async (input) => {
    log.completed.push({ password: input.password, deviceName: input.deviceName, deviceId: input.deviceId });
    newPassword = input.password;
    return signIn({ tenant: input.tenant, login: 'd.ortiz', password: PEOPLE['d.ortiz']?.password ?? '', deviceId: input.deviceId });
  };
  api.signIn = async (input) =>
    input.login === DANA_EMAIL && newPassword !== null && input.password === newPassword
      ? signIn({ ...input, login: 'd.ortiz', password: PEOPLE['d.ortiz']?.password ?? '' })
      : signIn(input);
  return log;
}

export async function mountGate(options: MountOptions = {}) {
  const handset = options.handset ?? makeHandset();
  const app = await mountApp({
    ...options,
    handset,
    signedIn: options.signedIn ?? false,
    gettingIn: {
      api: handset.api,
      deviceId: async () => 'device-van-14',
      deviceName: async () => 'Van 14 tablet',
      ...options.gettingIn,
    },
  });
  return Object.assign(app, { handset });
}

/** Open a screen by its address and wait for it. */
export async function go(app: { ref: unknown }, id: ScreenId, params?: object) {
  await act(async () => {
    openScreen(app.ref as Parameters<typeof openScreen>[0], id, params);
  });
  return screen.findByTestId(`screen-${id}`);
}

export function current(app: { ref: { getCurrentRoute: () => { name: string } | undefined } }): string | undefined {
  return app.ref.getCurrentRoute()?.name;
}
