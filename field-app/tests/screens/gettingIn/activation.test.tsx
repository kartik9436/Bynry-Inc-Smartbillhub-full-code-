/**
 * FF-56 Activate and FF-57 Your password (T-15) — US-FLD-070 §3. The office
 * made the account; the handset only claims it, with a six-character code,
 * the technician's own password and the device by name (R105).
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import { ServerGapError } from '../../../src/security/authApi';
import { makeHandset } from '../../session/fakes';
import { assertTouchTargets } from '../theDay/support';
import { CHECK, CODE, current, DANA_EMAIL, go, LOOKUP, mountGate, teachActivation } from './gateSupport';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

async function enterCode(code: string, email: string) {
  // Six characters typed asks the server which utility holds them (DEF-FLD-10580); let it answer.
  await act(async () => {
    fireEvent.changeText(screen.getByTestId('activate-code-input'), code);
  });
  fireEvent.changeText(screen.getByTestId('activate-email-input'), email);
}

describe('FF-56 Activate', () => {
  test("'FF-56 → FF-57' a code and work email within seven days opens Your password with who it is for (TC-1)", async () => {
    const handset = makeHandset();
    const log = teachActivation(handset.api);
    const app = await mountGate({ handset });
    await go(app, 'FF-56');
    expect(screen.getByTestId('door-FF-57')).toBeDisabled();
    // Read off a phone call: lower case and a space are the same code.
    await enterCode('k7m 2ab', DANA_EMAIL);
    // The code named the utility first (DEF-FLD-10580), shown under the code box.
    expect(log.looked).toEqual([{ code: CODE, deviceId: 'device-van-14' }]);
    expect(screen.getByTestId('activate-utility')).toHaveTextContent('For Lone Star Water');
    await act(async () => {
      fireEvent.press(screen.getByTestId('door-FF-57'));
    });
    // …and the check ran at THAT utility.
    expect(log.checked).toEqual([{ code: CODE, email: DANA_EMAIL, tenant: LOOKUP.tenant }]);
    expect(`FF-56 → ${current(app)}`).toBe('FF-56 → FF-57');
    expect(await screen.findByTestId('your-password-accepted')).toHaveTextContent(
      'Code accepted. Dana Ortiz · Field Technician · Lone Star Water.',
    );
    app.unmount();
  });

  test('a code the server refuses (old, wrong, or no account) is refused and nothing is created (TC-2, TC-3)', async () => {
    const handset = makeHandset();
    teachActivation(handset.api);
    const app = await mountGate({ handset });
    await go(app, 'FF-56');
    await enterCode('ZZZZZZ', DANA_EMAIL);
    await act(async () => {
      fireEvent.press(screen.getByTestId('door-FF-57'));
    });
    expect(screen.getByTestId('activate-error')).toHaveTextContent('Code not accepted. Call dispatch.');
    expect(current(app)).toBe('FF-56');
    expect(handset.session.snapshot().phase).toBe('signedOut');
    app.unmount();
  });

  test('a code that is not six letters or digits never leaves the phone', async () => {
    const handset = makeHandset();
    const log = teachActivation(handset.api);
    const app = await mountGate({ handset });
    await go(app, 'FF-56');
    await enterCode('K7M2', DANA_EMAIL);
    expect(screen.getByTestId('door-FF-57')).toBeDisabled();
    expect(log.checked).toEqual([]);
    app.unmount();
  });

  test('the activation route does not exist yet: "not ready on the server"', async () => {
    const handset = makeHandset();
    handset.api.lookupActivationCode = async () => LOOKUP;
    handset.api.checkActivationCode = async () => {
      throw new ServerGapError('activation-check');
    };
    const app = await mountGate({ handset });
    await go(app, 'FF-56');
    await enterCode(CODE, DANA_EMAIL);
    await act(async () => {
      fireEvent.press(screen.getByTestId('door-FF-57'));
    });
    expect(screen.getByTestId('activate-error')).toHaveTextContent('Sign-in not ready on the server.');
    app.unmount();
  });

  test("'FF-56 → FF-05' I have a password", async () => {
    const app = await mountGate();
    await go(app, 'FF-05');
    fireEvent.press(screen.getAllByTestId('door-FF-56').at(-1) as never);
    const root = await screen.findByTestId('screen-FF-56');
    fireEvent.press(within(root).getByTestId('door-FF-05'));
    expect(`FF-56 → ${current(app)}`).toBe('FF-56 → FF-05');
    app.unmount();
  });

  test('every control is named and at least 48pt', async () => {
    const app = await mountGate();
    const root = await go(app, 'FF-56');
    expect(assertTouchTargets(within(root).getAllByRole('button'))).toBe(2);
    app.unmount();
  });
});

describe('FF-57 Your password', () => {
  test('the length is the utility\'s minimum; two entries that differ are not saved and the second field says so (TC-5)', async () => {
    const app = await mountGate();
    await go(app, 'FF-57', { check: CHECK, email: DANA_EMAIL });
    expect(screen.getByTestId('your-password-rule-length').props.accessibilityLabel).toMatch(/^At least 10 characters, not yet/);
    fireEvent.changeText(screen.getByTestId('your-password-new-input'), 'valley-day-0730');
    expect(screen.getByTestId('your-password-rule-length').props.accessibilityLabel).toMatch(/met/);
    fireEvent.changeText(screen.getByTestId('your-password-again-input'), 'valley-day-0731');
    expect(screen.getByText('The two do not match.')).toBeTruthy();
    expect(screen.getByTestId('door-FF-07')).toBeDisabled();
    // Reuse is the server's to judge: never ticked on the handset.
    expect(screen.getByTestId('your-password-rule-reuse').props.accessibilityLabel).toMatch(/checked when you save/);
    app.unmount();
  });

  test("'FF-57 → FF-07' saving registers the device by name and signs in, then Permissions (TC-4)", async () => {
    const handset = makeHandset();
    const log = teachActivation(handset.api);
    const app = await mountGate({ handset });
    await go(app, 'FF-57', { check: CHECK, email: DANA_EMAIL, tenant: LOOKUP.tenant, utilityName: LOOKUP.utilityName });
    expect(screen.getByTestId('your-password-device')).toHaveTextContent('Registered as Van 14 tablet');
    fireEvent.changeText(screen.getByTestId('your-password-new-input'), 'creek-morning-12');
    fireEvent.changeText(screen.getByTestId('your-password-again-input'), 'creek-morning-12');
    await act(async () => {
      fireEvent.press(screen.getByTestId('door-FF-07'));
    });
    expect(log.completed).toEqual([{ password: 'creek-morning-12', deviceName: 'Van 14 tablet', deviceId: 'device-van-14' }]);
    expect(await screen.findByTestId('screen-FF-07')).toBeTruthy();
    expect(`FF-57 → ${current(app)}`).toBe('FF-57 → FF-07');
    expect(handset.session.snapshot().active?.technicianId).toBe('tech-dana');
    app.unmount();
  }, 30_000);

  test('a handset with no name yet asks for one, and Save waits for it', async () => {
    const app = await mountGate({ gettingIn: { deviceName: async () => null } });
    await go(app, 'FF-57', { check: CHECK, email: DANA_EMAIL });
    fireEvent.changeText(screen.getByTestId('your-password-new-input'), 'creek-morning-12');
    fireEvent.changeText(screen.getByTestId('your-password-again-input'), 'creek-morning-12');
    expect(screen.getByTestId('door-FF-07')).toBeDisabled();
    fireEvent.changeText(screen.getByTestId('your-password-device-name-input'), 'Van 14 tablet');
    expect(screen.getByTestId('door-FF-07')).not.toBeDisabled();
    app.unmount();
  });

  test("'FF-57 → FF-56' opened without a code it sends you back for one", async () => {
    const app = await mountGate();
    await go(app, 'FF-56');
    await go(app, 'FF-57');
    fireEvent.press(screen.getByTestId('door-FF-56'));
    expect(`FF-57 → ${current(app)}`).toBe('FF-57 → FF-56');
    app.unmount();
  });
});
