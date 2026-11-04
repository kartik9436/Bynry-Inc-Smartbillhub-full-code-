/**
 * `DEF-FLD-10617` on screen — Activate (FF-56), Sign in (FF-05) and First
 * sync's reason line (FF-08) say WHY a connection failed: a refused
 * certificate and an outdated server each have their own words, and only a
 * real dropped connection says *No signal* (decision log 2026-10-26).
 *
 * On 2.603.0 the tester was online and read *"No signal. Sign in with signal
 * once."* on both doors — the phone had refused the server's certificate.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen } from '@testing-library/react-native';

import { CertificateRefusedError, OfflineError, ServerOutdatedError } from '../../../src/security/authApi';
import { engineFirstSync, type FirstSyncResult } from '../../../src/screens/gettingIn/firstSync';
import { makeHandset } from '../../session/fakes';
import { current as currentDay, mountDay, open } from '../theDay/support';
import { CODE, DANA_EMAIL, go, LOOKUP, mountGate } from './gateSupport';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

const CASES = [
  ['a refused certificate', () => new CertificateRefusedError(new Error('Pin verification failed')), "Can't verify the server. Contact the office."],
  ['an outdated server', () => new ServerOutdatedError(new Error('404 text/html')), 'The server needs an update.'],
  ['no connection', () => new OfflineError(new TypeError('Network request failed')), 'No signal. Sign in with signal once.'],
] as const;

describe('FF-05 Sign in', () => {
  test.each(CASES)('%s', async (_what, make, words) => {
    const handset = makeHandset();
    handset.api.signIn = async () => {
      throw make();
    };
    const app = await mountGate({ handset });
    await go(app, 'FF-05');
    fireEvent.changeText(screen.getByTestId('signin-login-input'), 'd.ortiz');
    fireEvent.changeText(screen.getByTestId('signin-password-input'), 'valley-day-0730');
    await act(async () => {
      fireEvent.press(screen.getByTestId('door-FF-07'));
    });
    expect(screen.getByTestId('signin-error')).toHaveTextContent(words);
    app.unmount();
  });
});

describe('FF-56 Activate', () => {
  test.each(CASES)('%s', async (_what, make, words) => {
    const handset = makeHandset();
    handset.api.lookupActivationCode = async () => LOOKUP;
    handset.api.checkActivationCode = async () => {
      throw make();
    };
    const app = await mountGate({ handset });
    await go(app, 'FF-56');
    await act(async () => {
      fireEvent.changeText(screen.getByTestId('activate-code-input'), CODE);
    });
    fireEvent.changeText(screen.getByTestId('activate-email-input'), DANA_EMAIL);
    await act(async () => {
      fireEvent.press(screen.getByTestId('door-FF-57'));
    });
    expect(screen.getByTestId('activate-error')).toHaveTextContent(words);
    app.unmount();
  });

  test('the code lookup itself refused by certificate says so on the same line', async () => {
    const handset = makeHandset();
    handset.api.lookupActivationCode = async () => {
      throw new CertificateRefusedError();
    };
    const app = await mountGate({ handset });
    await go(app, 'FF-56');
    await act(async () => {
      fireEvent.changeText(screen.getByTestId('activate-code-input'), CODE);
    });
    expect(screen.getByTestId('activate-error')).toHaveTextContent("Can't verify the server. Contact the office.");
    app.unmount();
  });
});

describe('FF-08 First sync', () => {
  const failedList = (kind: string, status?: number): FirstSyncResult => ({
    pull: null,
    pullError: 'x',
    failures: { pull: { kind, ...(status !== undefined ? { status } : {}) }, bundles: null, templates: null },
    bundles: null,
  });

  test.each([
    ['certificate', undefined, "Can't verify the server. Contact the office."],
    ['endpoint_missing', 404, 'The server needs an update.'],
    ['network', undefined, 'No signal.'],
  ] as const)('the list failed with %s', async (kind, status, words) => {
    const port = engineFirstSync(async () => failedList(kind, status));
    const app = await mountDay({ fieldData: { firstSync: port } });
    await open(app, 'FF-08');
    await screen.findByTestId('screen-FF-08');
    await act(async () => undefined);
    expect(screen.getByTestId('first-sync-reason')).toHaveTextContent(words);
    expect(currentDay(app)).toBe('FF-08');
    app.unmount();
  });
});
