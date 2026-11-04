/**
 * Every reading screen, in every theme: it renders under the real navigation
 * from the fixture store, every control has a role and a name and is at least
 * the touch standard's 48, and every door the design draws on it is either a
 * real control on the screen (`door-<id>`) or named below as the frame's.
 *
 * The frame's doors are stated, not skipped silently (law 7: a check says
 * what it did not check): the native stack's back button, the bottom tabs and
 * the menu button belong to the navigator, and a few doors exist only in a
 * state (a search with hits, a figure out of range, a refusal).
 */
import 'react-native-gesture-handler/jestSetup';

import { act, within } from '@testing-library/react-native';

import * as routeReadQ from '../../../src/db/queries/routeRead';
import { scoped } from '../../../src/db/scoped';
import { DOORS } from '../../../src/navigation/doors';
import type { ScreenId } from '../../../src/navigation/screens';
import type { ReadsParams } from '../../../src/screens/reads/ReadsScreen';
import { touchHeight, THEME_NAMES } from '../../components/helpers';
import { RAY } from './fixture';
import { mountReads } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

import { PARAMS } from './params';

/** Doors that are the navigator's, or that exist only in a state — each with why. */
const NOT_ON_THE_SCREEN: Partial<Record<ScreenId, Partial<Record<ScreenId, string>>>> = {
  'RW-01': { 'FF-09': 'the menu button in the tab header', 'FF-63': 'bottom tab', 'FF-10': 'bottom tab', 'RW-27': 'a turned-in route — exists once one is turned in' },
  'RW-02': { 'RW-01': 'back' },
  'RW-05': { 'RW-02': 'back' },
  'RW-06': { 'RW-05': 'back' },
  'RW-08': { 'RW-09': 'a search hit — exists once something is found' },
  'RW-09': { 'RW-06': 'back (drawn on the tablet pane)', 'RW-15': 'the primary once the figure is out of range' },
  'RW-12': { 'RW-06': 'back' },
  'RW-15': { 'RW-09': 'back', 'RW-16': 'once a figure is typed on RW-09', 'RW-06': 'once a figure is typed on RW-09' },
  'RW-16': { 'RW-15': 'back' },
  'RW-25': { 'RW-22': 'back' },
  'RW-27': { 'RW-06': '*Fix and send again* on a refusal — exists once one is refused' },
  'RW-28': { 'FF-09': 'the menu (drawer)' },
};

const IDS = Object.keys(PARAMS) as ScreenId[];

describe.each(THEME_NAMES)('%s', (theme) => {
  test('every reading screen renders, every control is named and at least 48, every door is drawn or named', async () => {
    const app = await mountReads({ theme });
    routeReadQ.recordCapture(scoped(app.db, RAY), 'r0471', {
      captureKey: 'cap-r0471', value: '52410', unit: 'gal', readerStatus: 'read',
      capturedAt: '2026-10-20T10:00:00.000Z', capturedBy: RAY, identifiedBy: 'listed', readMethod: 'walk',
    });
    const missing: string[] = [];
    const small: string[] = [];
    const unnamed: string[] = [];
    let controls = 0;
    for (const id of IDS) {
      const page = within((await app.open(id, PARAMS[id]))!);
      await act(async () => undefined);
      for (const role of ['button', 'radio', 'switch'] as const) {
        for (const el of page.queryAllByRole(role)) {
          controls += 1;
          if (!el.props.accessibilityLabel) unnamed.push(`${id}:${el.props.testID ?? role}`);
          const h = touchHeight(el);
          const w = Number((el.props.style && (Array.isArray(el.props.style) ? Object.assign({}, ...el.props.style.flat()) : el.props.style)).width ?? 0);
          if (Math.max(h, w) < 48 && role !== 'switch') small.push(`${id}:${el.props.testID ?? el.props.accessibilityLabel}:${h}`);
        }
      }
      for (const to of DOORS[id]) {
        if (NOT_ON_THE_SCREEN[id]?.[to]) continue;
        if (!page.queryByTestId(`door-${to}`)) missing.push(`${id} → ${to}`);
      }
    }
    // law 7: say how much was checked.
    // eslint-disable-next-line no-console
    console.log(`reads sweep (${theme}): ${IDS.length} screens, ${controls} controls`);
    expect(IDS).toHaveLength(29);
    expect(controls).toBeGreaterThan(120);
    expect(unnamed).toEqual([]);
    expect(small).toEqual([]);
    expect(missing).toEqual([]);
    app.unmount();
  }, 60_000);
});
