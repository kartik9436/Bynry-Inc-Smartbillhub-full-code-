/**
 * T-15 Getting in, signed out: FF-01 Splash, FF-02/03/04 Intro, FF-05 Sign
 * in, FF-06 Forgot password — US-FLD-003, -032 §3 — and the flow the brief
 * asked to be fixed: a first sign-in goes to FF-07 Permissions, then FF-08
 * First sync, then the day (it used to land on Home).
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { Linking, TextInput } from 'react-native';

import { ServerGapError } from '../../../src/security/authApi';
import { APP_VERSION } from '../../../src/navigation/MenuContent';
import type { FirstSyncPort } from '../../../src/screens/gettingIn/firstSync';
import { makeHandset, signIn } from '../../session/fakes';
import { assertTouchTargets } from '../theDay/support';
import { current, go, mountGate } from './gateSupport';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

const COMPLETE_SYNC: FirstSyncPort = {
  run: async (onProgress) => {
    const done = {
      parts: [
        { id: 'shift' as const, state: 'unavailable' as const, done: 0, total: null },
        { id: 'documents' as const, state: 'unavailable' as const, done: 0, total: null },
        { id: 'jobs' as const, state: 'done' as const, done: 11, total: 11 },
        { id: 'assets' as const, state: 'unavailable' as const, done: 0, total: null },
        { id: 'customers' as const, state: 'unavailable' as const, done: 0, total: null },
      ],
    };
    onProgress(done);
    return done;
  },
};

async function typeSignIn(login: string, password: string) {
  fireEvent.changeText(screen.getByTestId('signin-login-input'), login);
  fireEvent.changeText(screen.getByTestId('signin-password-input'), password);
}

describe('FF-01 Splash', () => {
  test('the version is on screen (R40), and on a fresh handset it moves on to the intro by itself', async () => {
    const app = await mountGate();
    expect(await screen.findByTestId('screen-FF-01')).toBeTruthy();
    expect(screen.getByTestId('splash-version')).toHaveTextContent(APP_VERSION);
    await waitFor(() => expect(current(app)).toBe('FF-02'), { timeout: 4000 });
    app.unmount();
  });

  test('on a handset somebody has signed in on before, it skips the intro to sign-in', async () => {
    const handset = makeHandset();
    await signIn(handset.session, 'd.ortiz');
    await handset.session.signOut();
    const app = await mountGate({ handset });
    await waitFor(() => expect(current(app)).toBe('FF-05'), { timeout: 4000 });
    app.unmount();
  });

  test("'FF-01 → FF-02' a tap moves on at once", async () => {
    const app = await mountGate();
    fireEvent.press(await screen.findByTestId('door-FF-02'));
    expect(`FF-01 → ${current(app)}`).toBe('FF-01 → FF-02');
    app.unmount();
  });
});

describe('FF-02 · FF-03 · FF-04 Intro', () => {
  test.each([
    ['FF-02 → FF-03', 'FF-02', 'door-FF-03', 'FF-03'],
    ['FF-02 → FF-05', 'FF-02', 'door-FF-05', 'FF-05'],
    ['FF-03 → FF-04', 'FF-03', 'door-FF-04', 'FF-04'],
    ['FF-03 → FF-05', 'FF-03', 'door-FF-05', 'FF-05'],
    ['FF-04 → FF-05', 'FF-04', 'door-FF-05', 'FF-05'],
  ] as const)('%s', async (_name, from, testID, to) => {
    const app = await mountGate();
    const root = await go(app, from);
    fireEvent.press(within(root).getByTestId(testID));
    expect(`${from} → ${current(app)}`).toBe(`${from} → ${to}`);
    app.unmount();
  });

  test('each has Skip (but the last) and its own words; headings are three words at most (B14 rule 33)', async () => {
    const app = await mountGate();
    const one = await go(app, 'FF-02');
    expect(within(one).getByText('Your whole day')).toBeTruthy();
    expect(within(one).getByLabelText('1 of 3')).toBeTruthy();
    const three = await go(app, 'FF-04');
    expect(within(three).queryByText('Skip')).toBeNull();
    expect(within(three).getByText('Sign in')).toBeTruthy();
    app.unmount();
  });
});

describe('FF-05 Sign in', () => {
  test('one field for email or phone (PO 2026-10-21: no Technician ID), with the email keyboard', async () => {
    const app = await mountGate();
    await go(app, 'FF-05');
    expect(screen.getByText('Email or phone')).toBeTruthy();
    expect(screen.queryByText('Technician ID')).toBeNull();
    expect(screen.getByTestId('signin-login-input').props.keyboardType).toBe('email-address');
    app.unmount();
  });

  test('Sign in waits for both boxes; a wrong password says so in one line', async () => {
    const app = await mountGate();
    await go(app, 'FF-05');
    expect(screen.getByTestId('door-FF-07')).toBeDisabled();
    await typeSignIn('d.ortiz', 'nope');
    await act(async () => {
      fireEvent.press(screen.getByTestId('door-FF-07'));
    });
    expect(screen.getByTestId('signin-error')).toHaveTextContent('Wrong email, phone or password.');
    expect(current(app)).toBe('FF-05');
    app.unmount();
  });

  test('the native sign-in route does not exist yet: the screen says "not ready on the server" (ServerGapError)', async () => {
    const handset = makeHandset();
    handset.api.signIn = async () => {
      throw new ServerGapError('native-sign-in');
    };
    const app = await mountGate({ handset });
    await go(app, 'FF-05');
    await typeSignIn('d.ortiz', 'valley-day-0730');
    await act(async () => {
      fireEvent.press(screen.getByTestId('door-FF-07'));
    });
    expect(screen.getByTestId('signin-error')).toHaveTextContent('Sign-in not ready on the server.');
    app.unmount();
  });

  test("R. Patel's unsent work is named, under his name (TC-3)", async () => {
    const handset = makeHandset();
    await signIn(handset.session, 'r.patel');
    await handset.session.signOut();
    handset.outbox.add('tech-patel', 'item', 'k1');
    handset.outbox.add('tech-patel', 'item', 'k2');
    const app = await mountGate({ handset });
    await go(app, 'FF-05');
    expect(await screen.findByTestId('signin-others')).toHaveTextContent(/R\. Patel has 2 to send\. They send under their name\./);
    app.unmount();
  });

  test('there is no sign-up — the only way in for a new person is Activate (TC-4, R105)', async () => {
    const app = await mountGate();
    const root = await go(app, 'FF-05');
    expect(within(root).queryByText(/sign up|register|create an account/i)).toBeNull();
    expect(within(root).getByTestId('door-FF-56')).toHaveTextContent('First time here? Activate');
    // A thumb never signs anybody in: there is no session to return to here.
    expect(within(root).queryByText(/fingerprint/i)).toBeNull();
    app.unmount();
  });

  test('every control is named and at least 48pt', async () => {
    const app = await mountGate();
    const root = await go(app, 'FF-05');
    // Forgot · Activate · and *Change* beside the utility's name (DEF-FLD-10580).
    expect(assertTouchTargets([...within(root).getAllByRole('button'), ...within(root).getAllByRole('link')])).toBe(4);
    app.unmount();
  });

  test("'FF-05 → FF-06' carries what was typed; 'FF-05 → FF-56' opens activation", async () => {
    const app = await mountGate();
    await go(app, 'FF-05');
    fireEvent.changeText(screen.getByTestId('signin-login-input'), 'd.ortiz');
    fireEvent.press(screen.getByTestId('door-FF-06'));
    expect(`FF-05 → ${current(app)}`).toBe('FF-05 → FF-06');
    expect(await screen.findByTestId('forgot-who')).toHaveTextContent(/d\.ortiz/);
    await go(app, 'FF-05');
    fireEvent.press(screen.getAllByTestId('door-FF-56').at(-1) as never);
    expect(`FF-05 → ${current(app)}`).toBe('FF-05 → FF-56');
    app.unmount();
  });

  test("'FF-05 → FF-07' a sign-in opens Permissions, 'FF-07 → FF-08' then First sync, 'FF-08 → FF-10' then the day — not Home", async () => {
    const app = await mountGate({ fieldData: { firstSync: COMPLETE_SYNC } });
    await go(app, 'FF-05');
    await typeSignIn('d.ortiz', 'valley-day-0730');
    await act(async () => {
      fireEvent.press(screen.getByTestId('door-FF-07'));
    });
    expect(await screen.findByTestId('screen-FF-07')).toBeTruthy();
    expect(`FF-05 → ${current(app)}`).toBe('FF-05 → FF-07');
    fireEvent.press(screen.getByTestId('door-FF-08'));
    expect(`FF-07 → ${current(app)}`).toBe('FF-07 → FF-08');
    expect(await screen.findByTestId('first-sync-percent')).toHaveTextContent(/^100%/);
    fireEvent.press(screen.getByTestId('door-FF-10'));
    expect(`FF-08 → ${current(app)}`).toBe('FF-08 → FF-10');
    // Back from the day never returns to the loading screen: the root stack was reset to the frame alone.
    expect(app.ref.getRootState()?.routes.map((r) => r.name)).toEqual(['Frame']);
    app.unmount();
  }, 30_000);
});

describe('FF-06 Forgot password', () => {
  test('three choices and NO input box — nothing is typed here (TC-2, R38)', async () => {
    const app = await mountGate();
    const root = await go(app, 'FF-06', { login: 'd.ortiz' });
    expect(within(root).UNSAFE_queryAllByType(TextInput)).toHaveLength(0);
    expect(within(root).getAllByRole('radio')).toHaveLength(3);
    app.unmount();
  });

  test('the masked number and the office number are the server\'s, shown as given', async () => {
    const app = await mountGate({
      gettingIn: {
        reset: {
          contacts: async () => ({ maskedPhone: '(512) 555-••42', officePhone: '(512) 555-0100' }),
          textCode: async () => undefined,
          askOffice: async () => undefined,
        },
      },
    });
    await go(app, 'FF-06', { login: 'd.ortiz' });
    expect(await screen.findByText('(512) 555-••42')).toBeTruthy();
    expect(screen.getByText('(512) 555-0100')).toBeTruthy();
    await act(async () => {
      fireEvent.press(screen.getByTestId('forgot-act'));
    });
    expect(screen.getByTestId('forgot-result-sent')).toHaveTextContent('Code sent. Check your phone.');
    const openURL = jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
    fireEvent.press(screen.getByTestId('forgot-call'));
    expect(screen.getByTestId('forgot-act')).toHaveTextContent('Call the office');
    await act(async () => {
      fireEvent.press(screen.getByTestId('forgot-act'));
    });
    expect(openURL).toHaveBeenCalledWith('tel:5125550100');
    openURL.mockRestore();
    app.unmount();
  });

  test('with the shipped port, sending a code says it is not ready — never a pretend success', async () => {
    const app = await mountGate();
    await go(app, 'FF-06', { login: 'd.ortiz' });
    await act(async () => {
      fireEvent.press(screen.getByTestId('forgot-act'));
    });
    expect(screen.getByTestId('forgot-result-notReady')).toHaveTextContent('Not ready yet. Call the office.');
    app.unmount();
  });

  test("'FF-06 → FF-05' back to sign in", async () => {
    const app = await mountGate();
    await go(app, 'FF-05');
    fireEvent.press(screen.getByTestId('door-FF-06'));
    await screen.findByTestId('screen-FF-06');
    fireEvent.press(screen.getAllByTestId('door-FF-05').at(-1) as never);
    expect(`FF-06 → ${current(app)}`).toBe('FF-06 → FF-05');
    app.unmount();
  });
});
