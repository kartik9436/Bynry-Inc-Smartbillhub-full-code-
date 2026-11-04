/**
 * HONEST CONNECTION ERRORS (`DEF-FLD-10617`; decision log 2026-10-26, PO:
 * *"B. Switch the check off for the beta"* — and, built regardless, a refused
 * certificate and an outdated server each say their own words, never
 * *"No signal"*).
 *
 * On 2.603.0 the phone refused the server's certificate and the tester read
 * *"No signal. Sign in with signal once."* while fully online, because every
 * fetch throw, every 5xx and every bad answer was one `OfflineError`. Three
 * causes, three sentences:
 *   (a) the certificate was refused (the pinning library's refusal, or a
 *       fetch error naming SSL / a certificate)  → *Can't verify the server.
 *       Contact the office.*  (`CertificateRefusedError`)
 *   (b) the server answered and the door is missing or the answer is not
 *       the expected JSON (a 404 HTML page, a 200 that is not JSON)
 *                                                → *The server needs an
 *       update.*  (`ServerOutdatedError`)
 *   (c) no connection at all                      → *No signal.* (unchanged)
 *
 * Both new errors ARE `OfflineError`s, deliberately: a technician who has
 * signed in on this handset before still gets in offline and capture carries
 * on (`sessionManager`), and a refresh that cannot reach the server is still
 * uneventful. Only the WORDS change.
 *
 * WHAT WOULD MAKE THIS PASS WRONGLY: asserting the class alone while the
 * screen still maps it to the old key. Each case is carried through to
 * `failureKey` / `reasonFor`, the functions the screens actually call, and
 * the English sentence is read from the shipped catalogue.
 */
import { FIELD_KEYS_EN } from '../../src/i18n/catalogues';
import {
  CertificateRefusedError,
  InvalidCredentialsError,
  OfflineError,
  ServerOutdatedError,
} from '../../src/security/authApi';
import { isCertificateRefusal, noteCertificateRefusal, resetCertificateRefusals } from '../../src/security/certificateRefusal';
import { createHttpAuthApi } from '../../src/security/httpAuthApi';
import { failureKey } from '../../src/screens/gettingIn/signInErrors';
import { reasonFor } from '../../src/screens/gettingIn/firstSync';
import { HttpTransport, TransportError, failureOf } from '../../src/sync/transport';

const EN = FIELD_KEYS_EN as Record<string, string>;

function reply(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, json: async () => body, headers: { get: () => null } };
}
/** An HTML page — a proxy's, or a server that has no such route. */
function html(status: number) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => {
      throw new SyntaxError('JSON Parse error: Unexpected character: <');
    },
    headers: { get: (n: string) => (n.toLowerCase() === 'content-type' ? 'text/html' : null) },
  };
}

const api = (answer: () => Promise<unknown>) =>
  createHttpAuthApi({ baseUrl: 'https://x', fetchImpl: (async () => answer()) as unknown as typeof fetch, appHeaders: () => ({}), onAppTooOld: () => undefined });

const SIGN_IN = { tenant: 'north', login: 'd@x', password: 'pw', deviceId: 'dev' };

async function caught(p: Promise<unknown>): Promise<unknown> {
  try {
    await p;
  } catch (err) {
    return err;
  }
  throw new Error('expected a refusal');
}

beforeEach(() => resetCertificateRefusals());

describe('sign-in and activation (httpAuthApi)', () => {
  test.each([
    ['Android OkHttp', new Error('java.security.cert.CertificateException: Pin verification failed')],
    ['iOS TrustKit / NSURLSession', new Error('An SSL error has occurred and a secure connection to the server cannot be made.')],
    ['an untrusted chain', new TypeError('Trust anchor for certification path not found.')],
  ])('a certificate refusal (%s) reads "Can\'t verify the server", never "No signal"', async (_where, thrown) => {
    const err = await caught(api(async () => Promise.reject(thrown)).signIn(SIGN_IN));
    expect(err).toBeInstanceOf(CertificateRefusedError);
    expect(err).toBeInstanceOf(OfflineError); // still lets a known technician in offline
    expect(failureKey(err)).toBe('field.signIn.error.certificate');
    expect(EN['field.signIn.error.certificate']).toBe("Can't verify the server. Contact the office.");
  });

  test('React Native says only "Network request failed" — the pinning library\'s own refusal moments before decides it', async () => {
    const plain = () => api(async () => Promise.reject(new TypeError('Network request failed'))).signIn(SIGN_IN);
    // No refusal heard: that is no signal.
    expect(failureKey(await caught(plain()))).toBe('field.signIn.error.offline');
    // The library reported a pin mismatch for this host: the same throw is a refused certificate.
    noteCertificateRefusal();
    expect(await caught(plain())).toBeInstanceOf(CertificateRefusedError);
  });

  test('a real dropped connection stays "No signal."', async () => {
    const err = await caught(api(async () => Promise.reject(new TypeError('Network request failed'))).signIn(SIGN_IN));
    expect(err).toBeInstanceOf(OfflineError);
    expect(err).not.toBeInstanceOf(CertificateRefusedError);
    expect(err).not.toBeInstanceOf(ServerOutdatedError);
    expect(failureKey(err)).toBe('field.signIn.error.offline');
  });

  test('a 404 HTML page (the door is missing) reads "The server needs an update."', async () => {
    const err = await caught(api(async () => html(404)).signIn(SIGN_IN));
    expect(err).toBeInstanceOf(ServerOutdatedError);
    expect(failureKey(err)).toBe('field.signIn.error.outdated');
    expect(EN['field.signIn.error.outdated']).toBe('The server needs an update.');
  });

  test('a 200 that is not JSON on the lookup door reads "The server needs an update."', async () => {
    const err = await caught(api(async () => html(200)).lookupActivationCode({ code: 'K7M2AB', deviceId: 'dev' }));
    expect(err).toBeInstanceOf(ServerOutdatedError);
    expect(failureKey(err)).toBe('field.signIn.error.outdated');
  });

  test('a JSON answer missing what the door must say (no ticket) is an outdated server too', async () => {
    const err = await caught(api(async () => reply(200, { hello: 'world' })).checkActivationCode({ tenant: 'north', code: 'K7M2AB', email: 'd@x' }));
    expect(err).toBeInstanceOf(ServerOutdatedError);
  });

  test("the server's own JSON 404 refusal is still the person's: wrong code / wrong password", async () => {
    const err = await caught(api(async () => reply(404, { code: 'not_found', message_key: 'identity.x', params: {} })).signIn(SIGN_IN));
    expect(err).toBeInstanceOf(InvalidCredentialsError);
  });

  test('a 5xx stays "No signal." (the server is there and failing; capture carries on)', async () => {
    const err = await caught(api(async () => reply(502, null)).signIn(SIGN_IN));
    expect(failureKey(err)).toBe('field.signIn.error.offline');
  });
});

describe('sync (transport) and FF-08\'s reason line', () => {
  const transport = (answer: () => Promise<unknown>) =>
    new HttpTransport({ origin: 'https://x', tenant: 'north', accessToken: () => 'acc', fetchImpl: (async () => answer()) as unknown as typeof fetch, appHeaders: () => ({}) });

  async function failure(answer: () => Promise<unknown>) {
    const err = await caught(transport(answer).changes(null, 50));
    expect(err).toBeInstanceOf(TransportError);
    return failureOf(err);
  }

  test('a refused certificate is kind "certificate" and FF-08 says so', async () => {
    const f = await failure(async () => Promise.reject(new Error('SSLHandshakeException: Pin verification failed')));
    expect(f.kind).toBe('certificate');
    expect(reasonFor(f)).toBe('certificate');
    expect(EN['field.firstSync.reason.certificate']).toBe("Can't verify the server. Contact the office.");
  });

  test('a 404 HTML page is the server needing an update (sending waits; nothing is refused)', async () => {
    const f = await failure(async () => html(404));
    expect(f.kind).toBe('endpoint_missing');
    expect(f.status).toBe(404);
    expect(reasonFor(f)).toBe('outdated');
    expect(EN['field.firstSync.reason.outdated']).toBe('The server needs an update.');
  });

  test('a dropped connection is still "No signal."', async () => {
    const f = await failure(async () => Promise.reject(new TypeError('Network request failed')));
    expect(f.kind).toBe('network');
    expect(reasonFor(f)).toBe('noSignal');
  });

  test("a JSON 404 is still the server's answer about THAT item (kind http)", async () => {
    const f = await failure(async () => reply(404, { code: 'not_found' }));
    expect(f.kind).toBe('http');
  });
});

describe('isCertificateRefusal', () => {
  test('names the SSL / certificate messages and nothing else', () => {
    expect(isCertificateRefusal(new Error('Network request failed'))).toBe(false);
    expect(isCertificateRefusal(new Error('timeout'))).toBe(false);
    expect(isCertificateRefusal(new Error('javax.net.ssl.SSLPeerUnverifiedException: Certificate pinning failure!'))).toBe(true);
    expect(isCertificateRefusal({ name: 'SslPinningError' })).toBe(true);
  });

  test('a library refusal counts only for a short while after it is heard', () => {
    const t0 = 1_000_000;
    noteCertificateRefusal(t0);
    expect(isCertificateRefusal(new Error('Network request failed'), t0 + 5_000)).toBe(true);
    expect(isCertificateRefusal(new Error('Network request failed'), t0 + 60_000)).toBe(false);
  });
});
