/**
 * PINNING SWITCHED OFF — DORMANT IN EVERY BUILD (`CR-195-BRC10`; decision log
 * 2026-10-28, PO: *"start A1"*; it began as the beta-only switch of
 * `DEF-FLD-10617`, 2026-10-26).
 *
 * A build whose config does not say `extra.pinning: 'on'` never starts the
 * pinning module and never adopts a key list from the server — a list adopted
 * over an unpinned connection is exactly what `decideAdoption` exists to
 * refuse. It says so once in the log and reports
 * `pinningState() === 'off_by_config'` for diagnostics. **Nothing is shown to
 * the user**: Settings › About carried *"Beta build — certificate check off"*
 * until 2026-10-28, and the PO's A1 hides it (pinning is not a go-live
 * requirement, so a line saying it is off reads as a fault).
 *
 * WHAT WOULD MAKE THIS PASS WRONGLY: a controller reporting `off_by_config`
 * while the native module was initialised anyway. The module's call record
 * is asserted empty beside every state assertion. And the About test mounts
 * the real FF-51 in BOTH states, so a line hidden only while pinning is off
 * would still be caught.
 */
import 'react-native-gesture-handler/jestSetup';

import { screen, within } from '@testing-library/react-native';

import { PinningController, type PinningNative, PinStore, pinningState, type SettingsApi } from '../../src/security/pinning';
import type { Pin } from '../../src/security/pins';
import { MemoryKeyValueStore } from '../../src/security/prefs';
import { makeFixture, openScreen } from '../screens/me/support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

const X1: Pin = { spki_sha256: 'C5+lpZ7tcVwmwQIMcRtPbsQtWLABXhQzejna0wHFr8M=', label: 'ISRG Root X1', not_after: '2035-06-04' };
const GTS: Pin = { spki_sha256: 'hxqRlPTu1bMS/0DITB1SSu0vd4u/8l8TjPgfaAp63Gc=', label: 'GTS Root R1', not_after: '2036-06-22' };
const X2: Pin = { spki_sha256: 'diGVwiVYbubAI3RW4hB9xU8e/CH2GnkuvVFZE8zmgzI=', label: 'ISRG Root X2', not_after: '2040-09-17' };

function controller(mode: 'on' | 'off') {
  const calls: unknown[] = [];
  const native: PinningNative = {
    isAvailable: () => true,
    initialize: async (o) => {
      calls.push(o);
    },
  };
  const store = new PinStore(new MemoryKeyValueStore());
  const c = new PinningController({
    native,
    store,
    bootstrap: [X1, GTS],
    origin: 'https://smartbillhub.example',
    now: () => new Date('2026-10-26T12:00:00Z'),
    mode,
  });
  return { c, calls, store };
}

function onTop(id: string) {
  const all = screen.getAllByTestId(`screen-${id}`);
  return within(all.at(-1) as Parameters<typeof within>[0]);
}

describe('pinning off (dormant)', () => {
  test('start() never initialises the module and reports off_by_config', async () => {
    const log = jest.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { c, calls } = controller('off');
    expect(await c.start()).toBe('off_by_config');
    expect(await c.start()).toBe('off_by_config');
    expect(calls).toEqual([]);
    expect(pinningState()).toBe('off_by_config');
    // Said once, not once per start.
    expect(log.mock.calls.filter((a) => String(a[0]).includes('pinning'))).toHaveLength(1);
    log.mockRestore();
  });

  test("the server's list is never adopted, and the settings are not even asked for it", async () => {
    jest.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { c, calls, store } = controller('off');
    await c.start();
    let asked = 0;
    const api: SettingsApi = {
      settings: async () => {
        asked += 1;
        return { field_app_pins: [X1, X2] };
      },
    };
    expect(await c.refresh(api)).toEqual({ adopt: false, reason: 'pinning_off' });
    expect(asked).toBe(0);
    expect(store.read()).toBeNull();
    expect(calls).toEqual([]);
  });

  test('with pinning switched on by config the module IS initialised — the switch changes only what it says', async () => {
    const { c, calls } = controller('on');
    expect(await c.start()).toBe('enforced');
    expect(calls).toHaveLength(1);
    expect(pinningState()).toBe('enforced');
  });

  test('Settings › About shows no certificate line, with pinning off or on', async () => {
    jest.spyOn(console, 'warn').mockImplementation(() => undefined);
    await controller('off').c.start();
    let app = await openScreen('FF-51', makeFixture());
    expect(onTop('FF-51').getByTestId('ff51-version')).toBeTruthy();
    expect(onTop('FF-51').queryByTestId('ff51-pinning-off')).toBeNull();
    expect(screen.queryByText(/certificate/i)).toBeNull();
    app.unmount();

    await controller('on').c.start();
    app = await openScreen('FF-51', makeFixture());
    expect(onTop('FF-51').queryByTestId('ff51-pinning-off')).toBeNull();
    expect(screen.queryByText(/certificate/i)).toBeNull();
    app.unmount();
  });
});
