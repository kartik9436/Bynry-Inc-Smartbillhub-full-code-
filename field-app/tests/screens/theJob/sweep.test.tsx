/**
 * Every job screen, in every theme, from the seeded store: it renders, and
 * every control on it has a name and is at least 48pt (B14 rule 45, R39 —
 * *"Nothing smaller ships"*). The sweep COUNTS what it checked per screen and
 * asserts a floor, so a screen that stops rendering its controls cannot pass
 * by having nothing to check (law 7).
 *
 * And no colour or pixel literal anywhere in the screen folder (the kit's
 * own rule, `tests/components/noLiterals.test.ts`, extended to `screens/theJob`).
 *
 * Proved red (law 7): with `DashedButton`'s `minHeight` removed, every screen
 * drawing one failed the 48pt check (`touchHeight` 0); with `#e12e13` written
 * into `Safety.tsx`, the literal scan named the file.
 */
import 'react-native-gesture-handler/jestSetup';

import { within } from '@testing-library/react-native';
import { readdirSync, readFileSync } from 'fs';
import { join, resolve } from 'path';

import type { ScreenId } from '../../../src/navigation/screens';
import type { ThemeName } from '../../../src/theme';
import { touchHeight } from '../../components/helpers';
import { findLiterals } from '../../components/noLiterals.test';
import { seedWO4822, WO } from './fixture';
import { mountJob, onTop } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./window').currentWindow(),
}));

/** Each screen and the fewest controls it draws from the seeded store. */
const SCREENS: Array<[ScreenId, number]> = [
  ['FF-15', 20],
  ['FF-16', 6],
  ['FF-17', 4],
  ['FF-18', 7],
  ['FF-19', 9],
  ['FF-20', 8],
  ['FF-21', 4],
  ['FF-22', 3],
  ['FF-23', 9],
  ['FF-24', 6],
  ['FF-58', 9],
  ['FF-59', 12],
  ['FF-60', 5],
];

const THEMES: ThemeName[] = ['light', 'dark', 'sunlight'];

describe.each(THEMES)('%s', (theme) => {
  test.each(SCREENS)('%s: every control is named and at least 48pt', async (id, floor) => {
    const f = seedWO4822();
    await mountJob(f.services, id, { theme, params: id === 'FF-15' ? { workOrderId: WO } : undefined });
    const top = within(onTop(id));
    const controls = ['button', 'radio', 'checkbox', 'switch'].flatMap((role) => top.queryAllByRole(role));
    expect(controls.length).toBeGreaterThanOrEqual(floor);
    const bad = controls
      .filter((el) => String(el.props.accessibilityLabel ?? '').length === 0 || touchHeight(el) < 48)
      .map((el) => `${String(el.props.testID ?? el.props.accessibilityLabel ?? '?')}: ${touchHeight(el)}`);
    expect(bad).toEqual([]);
  });
});

describe('no literals in the job screens', () => {
  const dir = resolve(__dirname, '../../../src/screens/theJob');
  const files = readdirSync(dir).filter((n) => /\.(ts|tsx)$/.test(n));

  test('the scan reads the whole folder', () => {
    expect(files.length).toBeGreaterThanOrEqual(20);
  });

  test.each(files)('%s names no colour and no pixel', (file) => {
    expect(findLiterals(readFileSync(join(dir, file), 'utf8'))).toEqual([]);
  });
});
