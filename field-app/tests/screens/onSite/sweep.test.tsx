/**
 * One sweep over the nineteen screens of the on-site, closing and raise
 * waves (FF-25…FF-41, FF-61, FF-62):
 *
 *   1. each renders from the fixture handset, under the real navigator, in
 *      light, dark and sunlight — the real screen, not the "not on this
 *      phone" state and not the crash fallback;
 *   2. every button and radio on it has a name and is at least 48pt (B14
 *      rule 45, R39);
 *   3. no file in the three folders names a colour or a pixel (the kit's
 *      scanner, pointed at these folders too);
 *   4. each is REGISTERED — the registry mounts the built screen, not the
 *      placeholder.
 *
 * The sweep COUNTS what it checked, and the count is asserted, so a screen
 * that stops rendering its controls cannot pass by having nothing to check
 * (law 7). Red proof: with `RadioList`'s option height dropped from
 * `touch.primary` to `space[8]` (32), part 2 fails in every theme.
 */
import { readdirSync, readFileSync } from 'fs';
import { join, resolve } from 'path';
import { within } from '@testing-library/react-native';

import type { ScreenId } from '../../../src/navigation/screens';
import { SCREEN_COMPONENTS } from '../../../src/screens/registry';
import type { ThemeName } from '../../../src/theme';
import { touchHeight, type ReactTestInstance } from '../../components/helpers';
import { findLiterals } from '../../components/noLiterals.test';
import { makeWave, openScreen } from './fixture';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const W = { workOrderId: 'wo-4822' };
export const WAVE_SCREENS: Array<[ScreenId, Record<string, unknown> | undefined]> = [
  ['FF-25', W],
  ['FF-26', { workOrderId: 'wo-4826' }],
  ['FF-27', { workOrderId: 'wo-4824' }],
  ['FF-28', W],
  ['FF-29', W],
  ['FF-30', W],
  ['FF-31', W],
  ['FF-61', { workOrderId: 'wo-4830' }],
  ['FF-32', W],
  ['FF-33', W],
  ['FF-34', W],
  ['FF-35', undefined],
  ['FF-36', W],
  ['FF-37', { carriedFrom: 'wo-4824', templateId: 'tpl-leak' }],
  ['FF-38', W],
  ['FF-39', { assetId: 'a-4471' }],
  ['FF-40', { assetId: 'a-4471' }],
  ['FF-41', undefined],
  ['FF-62', undefined],
];

const THEMES: ThemeName[] = ['light', 'dark', 'sunlight'];

describe.each(THEMES)('%s theme', (theme) => {
  test('every screen renders for real, and every control is named and at least 48pt', async () => {
    let controls = 0;
    for (const [id, params] of WAVE_SCREENS) {
      const w = makeWave();
      const app = await openScreen(w, id, params, { theme });
      const page = within(app.onTop());
      expect([id, page.queryByTestId('not-on-phone')]).toEqual([id, null]);
      expect([id, page.queryByTestId('screen-failed')]).toEqual([id, null]);
      const found: ReactTestInstance[] = [...page.queryAllByRole('button'), ...page.queryAllByRole('radio')];
      for (const el of found) {
        const name = String(el.props.accessibilityLabel ?? '');
        expect([id, name.length > 0]).toEqual([id, true]);
        expect([id, name, touchHeight(el) >= 48]).toEqual([id, name, true]);
      }
      controls += found.length;
      app.unmount();
    }
    // law 7: say how much was checked, so a sweep that saw nothing cannot pass.
    console.log(`wave sweep (${theme}): ${WAVE_SCREENS.length} screens, ${controls} controls`);
    expect(controls).toBeGreaterThanOrEqual(66);
  }, 120_000);
});

describe('no colour and no pixel in the three screen folders', () => {
  const dirs = ['onSite', 'closing', 'raise'].map((d) => resolve(__dirname, '../../../src/screens', d));
  const files = dirs.flatMap((d) => readdirSync(d).filter((f) => /\.(ts|tsx)$/.test(f)).map((f) => join(d, f)));

  test('the scan reads every file', () => {
    console.log(`wave noLiterals: ${files.length} files read`);
    expect(files.length).toBeGreaterThanOrEqual(30);
  });

  test.each(files.map((f) => [f.split('/src/screens/')[1] ?? f, f]))('%s', (_name, file) => {
    expect(findLiterals(readFileSync(file, 'utf8'))).toEqual([]);
  });
});

test('all nineteen are registered: the registry mounts the built screen, not the placeholder', () => {
  for (const [id] of WAVE_SCREENS) {
    expect([id, SCREEN_COMPONENTS[id].displayName]).toEqual([id, `Screen(${id})`]);
  }
});
