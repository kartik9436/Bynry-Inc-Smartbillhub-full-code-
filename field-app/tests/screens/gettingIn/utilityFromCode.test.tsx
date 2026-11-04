/**
 * `DEF-FLD-10580` (beta report MQ-006) — ONE build for every utility; the
 * office's code names the utility (PO 2026-10-24: *"A. The code from the
 * office sets the utility"*).
 *
 * Before the fix the preview build carried `EXPO_PUBLIC_TENANT=brookfield-…`,
 * so a Houston technician's handset could only ever ask Brookfield. These
 * cases mount the same app twice — Houston and Brookfield — with nothing in
 * the build naming either, and prove: the code names the utility; the utility
 * is remembered and shown on FF-05 with *Change*; a fresh handset can only
 * activate; and a contractor moving between utilities keeps each one's last
 * login and each one's database file.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import * as premiseQ from '../../../src/db/queries/premise';
import { StoreHolder } from '../../../src/db/storeHolder';
import type { ActivationLookup, AuthApi } from '../../../src/security/authApi';
import { InvalidCredentialsError } from '../../../src/security/authApi';
import { handsetUtilityIn, memoryHandsetUtility } from '../../../src/security/handsetUtility';
import { createHttpAuthApi } from '../../../src/security/httpAuthApi';
import { MemoryKeyValueStore } from '../../../src/security/prefs';
import { memoryFactory } from '../../db/support/nodeDriver';
import { makeHandset } from '../../session/fakes';
import { CHECK, current, DANA_EMAIL, go, mountGate, teachActivation } from './gateSupport';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

const HOUSTON: ActivationLookup = { tenant: 'houston', utilityName: 'City of Houston' };
const BROOKFIELD: ActivationLookup = { tenant: 'brookfield-municipal-utilities', utilityName: 'Brookfield Municipal Utilities' };
/** The two codes the two offices handed out — unique across every utility (the server's register). */
const CODES: Record<string, ActivationLookup> = { K7QM2P: HOUSTON, P3XW9A: BROOKFIELD };

/** A handset of the ONE build: the server answers both utilities' codes. */
function oneBuildHandset() {
  const handset = makeHandset();
  const log = teachActivation(handset.api);
  const checked: string[] = [];
  // The shared fake declares the activation calls as refusals; this widens them to the real interface.
  const api = handset.api as unknown as AuthApi;
  api.lookupActivationCode = async ({ code }) => {
    const found = CODES[code];
    if (!found) throw new InvalidCredentialsError();
    return found;
  };
  api.checkActivationCode = async ({ tenant }) => {
    checked.push(tenant);
    const utility = Object.values(CODES).find((u) => u.tenant === tenant);
    return { ...CHECK, utilityName: utility?.utilityName ?? '' };
  };
  return { handset, log, checked };
}

async function typeCode(code: string) {
  await act(async () => {
    fireEvent.changeText(screen.getByTestId('activate-code-input'), code);
  });
}

async function activate(code: string) {
  await typeCode(code);
  fireEvent.changeText(screen.getByTestId('activate-email-input'), DANA_EMAIL);
  await act(async () => {
    fireEvent.press(screen.getByTestId('door-FF-57'));
  });
  await screen.findByTestId('screen-FF-57');
  fireEvent.changeText(screen.getByTestId('your-password-new-input'), 'creek-morning-12');
  fireEvent.changeText(screen.getByTestId('your-password-again-input'), 'creek-morning-12');
  await act(async () => {
    fireEvent.press(screen.getByTestId('door-FF-07'));
  });
}

describe('one build, the code names the utility (DEF-FLD-10580)', () => {
  test('Houston and Brookfield on ONE build: each code activates at its own utility and is remembered', async () => {
    for (const [code, utility] of Object.entries(CODES)) {
      const { handset, log, checked } = oneBuildHandset();
      const remembered = memoryHandsetUtility();
      const app = await mountGate({ handset, gettingIn: { tenant: null, utility: remembered } });
      await go(app, 'FF-56');
      await activate(code);
      expect(checked).toEqual([utility.tenant]);
      expect(log.completed).toHaveLength(1);
      expect(remembered.current()).toEqual(utility);
      expect(remembered.lastLogin(utility.tenant)).toBe(DANA_EMAIL);
      app.unmount();
    }
  }, 60_000);

  test('a fresh handset knows no utility: FF-05 says to activate and Sign in stays off', async () => {
    const { handset } = oneBuildHandset();
    const app = await mountGate({ handset, gettingIn: { tenant: null, utility: memoryHandsetUtility() } });
    const root = await go(app, 'FF-05');
    expect(within(root).getByTestId('signin-no-utility')).toHaveTextContent('Activate this phone first.');
    expect(within(root).queryByTestId('signin-utility')).toBeNull();
    fireEvent.changeText(screen.getByTestId('signin-login-input'), 'd.ortiz');
    fireEvent.changeText(screen.getByTestId('signin-password-input'), 'valley-day-0730');
    expect(screen.getByTestId('door-FF-07')).toBeDisabled();
    fireEvent.press(screen.getAllByTestId('door-FF-56').at(-1) as never);
    expect(`FF-05 → ${current(app)}`).toBe('FF-05 → FF-56');
    app.unmount();
  });

  test('FF-05 names the remembered utility, pre-fills its last login, and Change goes back to Activate', async () => {
    const { handset } = oneBuildHandset();
    const remembered = memoryHandsetUtility(HOUSTON);
    remembered.rememberLogin(HOUSTON.tenant, DANA_EMAIL);
    const app = await mountGate({ handset, gettingIn: { tenant: null, utility: remembered } });
    const root = await go(app, 'FF-05');
    expect(within(root).getByTestId('signin-utility')).toHaveTextContent('Signing in to City of Houston');
    expect(screen.getByTestId('signin-login-input').props.value).toBe(DANA_EMAIL);
    fireEvent.press(within(root).getByTestId('signin-change-utility'));
    expect(`FF-05 → ${current(app)}`).toBe('FF-05 → FF-56');
    app.unmount();
  });

  test('the wrong utility\'s code shows THAT utility\'s name before anything is claimed', async () => {
    const { handset, checked } = oneBuildHandset();
    const remembered = memoryHandsetUtility(HOUSTON);
    const app = await mountGate({ handset, gettingIn: { tenant: null, utility: remembered } });
    await go(app, 'FF-56');
    await typeCode('P3XW9A'); // Brookfield's code on a Houston handset
    expect(screen.getByTestId('activate-utility')).toHaveTextContent('For Brookfield Municipal Utilities');
    expect(checked).toEqual([]); // nothing asked of either utility yet
    expect(remembered.current()).toEqual(HOUSTON); // and nothing moved
    app.unmount();
  });

  test('a code no utility holds is the one refusal and names no utility', async () => {
    const { handset } = oneBuildHandset();
    const app = await mountGate({ handset, gettingIn: { tenant: null, utility: memoryHandsetUtility() } });
    await go(app, 'FF-56');
    await typeCode('ZZZZZZ');
    expect(screen.getByTestId('activate-error')).toHaveTextContent('Code not accepted. Call dispatch.');
    expect(screen.queryByTestId('activate-utility')).toBeNull();
    app.unmount();
  });
});

describe('a contractor who works for two utilities', () => {
  test('switching utility keeps each one\'s last login and each one\'s database file apart', () => {
    const prefs = new MemoryKeyValueStore();
    const utility = handsetUtilityIn(prefs);
    const factory = memoryFactory();
    const holder = new StoreHolder(factory, { now: () => '2026-10-24T08:00:00.000Z' });

    utility.remember(HOUSTON);
    utility.rememberLogin(HOUSTON.tenant, 'mark@houston.example');
    premiseQ.upsert(holder.open(utility.current()!.tenant), { id: 'p-1', addressLine: '1 Main St' }, '2026-10-24T08:00:00.000Z');

    utility.remember(BROOKFIELD); // Change → Brookfield's code
    utility.rememberLogin(BROOKFIELD.tenant, 'mark@brookfield.example');
    const brookfield = holder.open(utility.current()!.tenant);
    expect(premiseQ.get(brookfield, 'p-1')).toBeUndefined();
    expect([...factory.files.keys()].sort()).toEqual([
      'field-brookfield-municipal-utilities.sqlite',
      'field-houston.sqlite',
    ]);

    utility.remember(HOUSTON); // and back again
    expect(utility.lastLogin(HOUSTON.tenant)).toBe('mark@houston.example');
    expect(utility.lastLogin(BROOKFIELD.tenant)).toBe('mark@brookfield.example');
    expect(premiseQ.get(holder.open(HOUSTON.tenant), 'p-1')?.address_line).toBe('1 Main St');
    // The handset remembers across a restart: a new reader of the same prefs.
    expect(handsetUtilityIn(prefs).current()).toEqual(HOUSTON);
  });
});

describe('the lookup door on the wire', () => {
  test('POSTs to /api/auth/activation/lookup with NO utility in the path and the device id in a header', async () => {
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const fetchImpl = async (url: string, init: RequestInit) => {
      calls.push({ url, init });
      return new Response(JSON.stringify({ tenant: 'houston', utility_name: 'City of Houston' }), { status: 200 });
    };
    const api = createHttpAuthApi({ baseUrl: 'https://smartbillhub.bynry.com', fetchImpl: fetchImpl as unknown as typeof fetch, appHeaders: () => ({}) });
    await expect(api.lookupActivationCode({ code: 'K7QM2P', deviceId: 'dev-1' })).resolves.toEqual(HOUSTON);
    expect(calls[0]?.url).toBe('https://smartbillhub.bynry.com/api/auth/activation/lookup');
    expect((calls[0]?.init.headers as Record<string, string>)['X-Device-Id']).toBe('dev-1');
    expect(JSON.parse(String(calls[0]?.init.body))).toEqual({ code: 'K7QM2P' });
  });

  test('a refused code reads as wrong, never as a utility', async () => {
    const fetchImpl = async () => new Response(JSON.stringify({ code: 'AUTH-001', params: { reason: 'activation_code_not_accepted' } }), { status: 401 });
    const api = createHttpAuthApi({ baseUrl: 'https://x.example', fetchImpl: fetchImpl as unknown as typeof fetch, appHeaders: () => ({}) });
    await expect(api.lookupActivationCode({ code: 'ZZZZZZ', deviceId: 'd' })).rejects.toBeInstanceOf(InvalidCredentialsError);
  });
});
