/**
 * DEF-FLD-10640 (PO report FB-015, WO-0171) — photos on mobile data AND wi-fi.
 *
 * PO 2026-10-28, option A (*"it should work on mobile and wifi both"*, then
 * *"go with A"*), superseding R54:
 *  - photos upload on ANY connection by default;
 *  - the one switch left is *Photos on wi-fi only*, OFF by default, and every
 *    phone moves to that default whatever R54's old switch held;
 *  - Sync says *Photos wait for wi-fi.* ONLY while that switch is on.
 *
 * The reported fault: the runtime read the old switch as `=== 'true'` while
 * Settings stored `'1'`, so it never reached the engine; and Sync read the
 * preferences once at mount. Keys are spelt out here as strings, not through
 * `PREF`, so these cases ran against the code as it stood before the fix.
 */
import 'react-native-gesture-handler/jestSetup';

import { CommonActions } from '@react-navigation/native';
import { act, fireEvent, screen, within } from '@testing-library/react-native';

import { routeTo } from '../../src/navigation/routing';
import { writeFlag } from '../../src/screens/me/prefs';
import { SyncEngine, type SyncOptions } from '../../src/sync/engine';
import { buildHandset, mountHandset, settle, signInAs } from '../proof/runtimeApp';
import { makeFixture, openScreen, seedPhotos } from '../screens/me/support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const OLD_KEY = 'handset.sync.photosOnMobileData';
const WIFI_ONLY = 'handset.sync.photosWifiOnly';
const WAIT_LINE = 'Photos wait for wi-fi.';

/** What the runtime asked the engine for, on one press of Sync on a phone on mobile data. */
async function engineOptionsOnCellular(prefs: Record<string, string>): Promise<{ opts: SyncOptions; oldKeyAfter: string | undefined }> {
  const seen: SyncOptions[] = [];
  const spy = jest.spyOn(SyncEngine.prototype, 'sync').mockImplementation(function (this: SyncEngine, opts: SyncOptions) {
    seen.push(opts);
    return Promise.resolve({ data: { accepted: 0, duplicate: 0, held_for_review: 0 } } as never);
  });
  try {
    const h = buildHandset({ network: 'cellular' });
    for (const [k, v] of Object.entries(prefs)) h.prefs.set(k, v);
    const m = mountHandset(h);
    await signInAs(h, 'd.ortiz');
    await settle();
    await act(async () => {
      await m.inside.current.runtime!.syncNow({ manual: true }).catch(() => undefined);
    });
    const opts = seen.find((o) => o.network === 'cellular');
    if (!opts) throw new Error('the engine was never asked to run on cellular');
    return { opts, oldKeyAfter: h.prefs.getString(OLD_KEY) };
  } finally {
    spy.mockRestore();
  }
}

describe('the engine is told photos may go on mobile data', () => {
  test('FB-015 exactly: the old "Send photos over mobile data" switch ON, on mobile data — photos go', async () => {
    const { opts } = await engineOptionsOnCellular({ [OLD_KEY]: '1' });
    expect(opts.allowMobileData).toBe(true);
  });

  test('a phone that never touched a switch: photos go on mobile data (the new default)', async () => {
    const { opts } = await engineOptionsOnCellular({});
    expect(opts.allowMobileData).toBe(true);
  });

  test('the old switch OFF is not carried over either — every phone takes the new default, and the old key is gone', async () => {
    const { opts, oldKeyAfter } = await engineOptionsOnCellular({ [OLD_KEY]: '0' });
    expect(opts.allowMobileData).toBe(true);
    expect(oldKeyAfter).toBeUndefined();
  });

  test('"Photos on wi-fi only" ON, on mobile data — photos wait', async () => {
    const { opts } = await engineOptionsOnCellular({ [WIFI_ONLY]: '1' });
    expect(opts.allowMobileData).toBe(false);
  });
});

function onTop(id: string) {
  const all = screen.getAllByTestId(`screen-${id}`);
  return within(all.at(-1) as Parameters<typeof within>[0]);
}

describe('FF-50 says "Photos wait for wi-fi." only while the switch is on', () => {
  test('off by default: the line is not there', async () => {
    const f = makeFixture();
    seedPhotos(f.db);
    const app = await openScreen('FF-50', f);
    expect(onTop('FF-50').queryByText(WAIT_LINE)).toBeNull();
    app.unmount();
  });

  test('turned on in Settings, Sync says it on return — and stops saying it when turned off', async () => {
    const f = makeFixture();
    seedPhotos(f.db);
    const app = await openScreen('FF-50', f);
    expect(onTop('FF-50').queryByText(WAIT_LINE)).toBeNull();
    const flip = async (expected: boolean) => {
      const settings = routeTo('FF-51');
      await act(async () => {
        app.ref.dispatch(CommonActions.navigate(settings.name, settings.params));
      });
      const toggle = onTop('FF-51').getByTestId('ff51-photos-wifi-only');
      expect(toggle).toHaveProp('accessibilityLabel', 'Photos on wi-fi only');
      await act(async () => {
        fireEvent.press(toggle);
      });
      expect(f.services.prefs.getString(WIFI_ONLY)).toBe(expected ? '1' : '0');
      await act(async () => {
        app.ref.goBack();
      });
    };
    await flip(true);
    expect(onTop('FF-50').getByText(WAIT_LINE)).toBeTruthy();
    await flip(false);
    expect(onTop('FF-50').queryByText(WAIT_LINE)).toBeNull();
    app.unmount();
  });

  test('a write while Sync is open shows at once, with no navigation', async () => {
    const f = makeFixture();
    seedPhotos(f.db);
    const app = await openScreen('FF-50', f);
    expect(onTop('FF-50').queryByText(WAIT_LINE)).toBeNull();
    await act(async () => {
      writeFlag(f.services.prefs, WIFI_ONLY, true);
    });
    expect(onTop('FF-50').getByText(WAIT_LINE)).toBeTruthy();
    app.unmount();
  });

  test('a value changed behind the screen is read again when the screen comes back into focus', async () => {
    const f = makeFixture();
    seedPhotos(f.db);
    const app = await openScreen('FF-50', f);
    expect(onTop('FF-50').queryByText(WAIT_LINE)).toBeNull();
    f.services.prefs.set(WIFI_ONLY, '1');
    const away = routeTo('FF-51');
    const back = routeTo('FF-50');
    await act(async () => {
      app.ref.dispatch(CommonActions.navigate(away.name, away.params));
    });
    await act(async () => {
      app.ref.dispatch(CommonActions.navigate(back.name, back.params));
    });
    expect(onTop('FF-50').getByText(WAIT_LINE)).toBeTruthy();
    app.unmount();
  });
});
