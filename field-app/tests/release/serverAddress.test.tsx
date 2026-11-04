/**
 * The server address is per build (`EXPO_PUBLIC_API_BASE_URL`, `eas.json`
 * profile `env`). With none — empty, or still the placeholder — the app says
 * *No server set* on FF-05 with *Sign in* off, and NOTHING calls a relative
 * `/api/…` address (`src/release/serverAddress.ts`).
 *
 * WHAT WOULD MAKE THIS PASS WRONGLY: a client that builds the URL inside its
 * own try/catch and reports "no signal" instead — the fetch spies below must
 * never be called, and the error must be `NoServerError`, not `OfflineError`.
 */
import 'react-native-gesture-handler/jestSetup';

import { screen, waitFor } from '@testing-library/react-native';

import easJson from '../../eas.json';
import { NoServerError, serverAddress, STAGING_URL_PLACEHOLDER } from '../../src/release/serverAddress';
import { failureKey } from '../../src/screens/gettingIn/signInErrors';
import { createHttpAuthApi } from '../../src/security/httpAuthApi';
import { HttpTransport } from '../../src/sync/transport';
import { go, mountGate } from '../screens/gettingIn/gateSupport';

test('an address is used only when absolute https; empty and the placeholder are none', () => {
  expect(serverAddress('https://smartbillhub.bynry.com')).toBe('https://smartbillhub.bynry.com');
  expect(serverAddress(' https://staging.example.com/ ')).toBe('https://staging.example.com');
  expect(serverAddress('')).toBeNull();
  expect(serverAddress(undefined)).toBeNull();
  expect(serverAddress(STAGING_URL_PLACEHOLDER)).toBeNull();
  expect(serverAddress('/api')).toBeNull();
  expect(serverAddress('smartbillhub.bynry.com')).toBeNull();
});

test('a plain http:// server is refused — https only (CR-195-BRC10)', () => {
  // Pinning is dormant (decision log 2026-10-28, PO "start A1"), so the
  // transport's whole protection is the standard TLS check — which an http
  // address would skip. No build profile uses http, so there is no dev exception.
  expect(serverAddress('http://smartbillhub.bynry.com')).toBeNull();
  expect(serverAddress('HTTP://10.0.2.2:8000')).toBeNull();
  expect(serverAddress('HTTPS://smartbillhub.bynry.com')).toBe('HTTPS://smartbillhub.bynry.com');
});

test('every build profile that names a server names an https one', () => {
  const profiles = (easJson as unknown as { build: Record<string, { env?: Record<string, string> }> }).build;
  for (const [name, profile] of Object.entries(profiles)) {
    const raw = profile.env?.EXPO_PUBLIC_API_BASE_URL;
    if (raw === undefined) continue;
    expect([name, /^https:\/\//i.test(raw.trim())]).toEqual([name, true]);
  }
});

test('the preview profile names a usable server address', () => {
  const preview = (easJson as unknown as { build: { preview: { env?: Record<string, string> } } }).build.preview;
  expect(serverAddress(preview.env?.EXPO_PUBLIC_API_BASE_URL)).toBe('https://smartbillhub.bynry.com');
});

test('no build profile names a utility — the office code does (DEF-FLD-10580)', () => {
  // One build for every utility (PO 2026-10-24, *"the code from the office sets
  // the utility"*). A profile carrying a utility would sign every handset of
  // that build in to one utility, which is beta report MQ-006 itself.
  const profiles = (easJson as unknown as { build: Record<string, { env?: Record<string, string> }> }).build;
  for (const [name, profile] of Object.entries(profiles)) {
    expect([name, Object.keys(profile.env ?? {}).filter((k) => /TENANT|UTILITY/.test(k))]).toEqual([name, []]);
  }
});

test('sign-in with no address never fetches, and refuses as NoServerError (not "no signal")', async () => {
  for (const baseUrl of ['', STAGING_URL_PLACEHOLDER]) {
    const fetchImpl = jest.fn();
    const api = createHttpAuthApi({ baseUrl, fetchImpl: fetchImpl as unknown as typeof fetch });
    await expect(api.signIn({ tenant: 't', login: 'a@b.c', password: 'x', deviceId: 'd' })).rejects.toBeInstanceOf(NoServerError);
    expect(fetchImpl).not.toHaveBeenCalled();
  }
});

test('the sync transport with no address never fetches either', async () => {
  const fetchImpl = jest.fn();
  const t = new HttpTransport({ origin: '', tenant: 't', accessToken: () => 'a', fetchImpl: fetchImpl as unknown as typeof fetch });
  await expect(t.changes(null, 50)).rejects.toBeInstanceOf(NoServerError);
  expect(fetchImpl).not.toHaveBeenCalled();
});

test('the refusal reads as No server set', () => {
  expect(failureKey(new NoServerError())).toBe('field.signIn.noServer');
});

describe('FF-05 with no server in the build', () => {
  test('says No server set, before anything is typed, and Sign in is off', async () => {
    const app = await mountGate({ gettingIn: { serverSet: false } });
    await go(app, 'FF-05');
    await waitFor(() => expect(screen.getByTestId('signin-no-server')).toHaveTextContent('No server set. Ask the office.'));
    expect(screen.getByTestId('door-FF-07')).toBeDisabled();
  });

  test('with a server, the notice is absent', async () => {
    const app = await mountGate();
    await go(app, 'FF-05');
    expect(screen.queryByTestId('signin-no-server')).toBeNull();
  });
});
