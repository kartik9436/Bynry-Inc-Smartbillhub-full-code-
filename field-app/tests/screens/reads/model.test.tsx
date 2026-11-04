/**
 * The reads wave's arithmetic, queries and frame, below the screens:
 *  - figures: TEXT decimals, never floats (hard rule 2); the handset's warning
 *    kept apart from the office's verdict (R80, R81, R96);
 *  - queries: scoped to the reader (R133), two tenants in two files (R131),
 *    nearest-first from the downloaded points (R76), one reader per route as a
 *    row that could become many (R87);
 *  - the frame: with no reading services mounted a route renders its
 *    placeholder and its doors, never a screen that cannot read its store;
 *  - no colour and no pixel in the wave's screen folder.
 */
import 'react-native-gesture-handler/jestSetup';

import { readdirSync, readFileSync } from 'fs';
import { join, resolve } from 'path';

import * as walkQ from '../../../src/db/queries/readsWalk';
import { scoped } from '../../../src/db/scoped';
import { add, compare, distanceText, fixQuality, group, metresBetween, needsWarning, subtract, used, verdict } from '../../../src/screens/reads/figures';
import { findLiterals } from '../../components/noLiterals.test';
import { memoryFactory } from '../../db/support/nodeDriver';
import { openStore } from '../../db/support/fixtures';
import { mountApp } from '../../navigation/harness';
import { HERE, RAY, seedMapleHeights } from './fixture';
import { act, screen, within } from '@testing-library/react-native';
import { CommonActions } from '@react-navigation/native';
import { routeTo } from '../../../src/navigation/routing';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

describe('figures', () => {
  test('decimal arithmetic is exact, with every place kept', () => {
    expect(subtract('52410', '48210')).toBe('4200');
    expect(subtract('0.3', '0.1')).toBe('0.2'); // 0.19999… as floats
    expect(subtract('48210', '52410')).toBe('-4200');
    expect(add(['31100', '29640'])).toBe('60740');
    expect(subtract('92480', add(['31100', '29640']))).toBe('31740');
    expect(compare('9', '10')).toBe(-1);
    expect(group('1234567.25')).toBe('1,234,567.25');
    expect(() => subtract('1e3', '1')).toThrow();
  });

  test('where a figure sits: inside, high, low — and below last month as its own warning (R81)', () => {
    expect(verdict('52410', '48210', '40000', '56000')).toBe('inside');
    expect(verdict('71400', '48210', '40000', '56000')).toBe('high');
    expect(verdict('47000', '48210', '40000', '56000')).toBe('below_previous');
    expect(verdict('39000', null, '40000', '56000')).toBe('low');
    expect(verdict('100', null, null, null)).toBe('unknown');
    expect(needsWarning('inside')).toBe(false);
    expect(needsWarning('below_previous')).toBe(true);
    expect(used('71400', '48210')).toBe('23190');
    expect(used('5', null)).toBeNull();
  });

  test('distances and fixes', () => {
    const a = { lat: HERE.lat, lng: HERE.lng };
    expect(Math.round(metresBetween(a, { lat: HERE.lat + 40 / 111_320, lng: HERE.lng }))).toBe(40);
    expect(distanceText(43)).toBe('40 m');
    expect(distanceText(1530)).toBe('1.5 km');
    expect(fixQuality(null)).toBe('none');
    // The poor-fix threshold is not ruled: a fix is stored as it came, unclassified.
    expect(fixQuality(300)).toBeNull();
  });
});

describe('queries', () => {
  test('nearest-first comes from the downloaded points, in metres order (R76)', () => {
    const db = openStore('silver-creek');
    seedMapleHeights(db);
    const s = scoped(db, RAY);
    const near = walkQ.stops(s, 'wlk-07', { order: 'nearest', from: HERE });
    expect(near.map((x) => x.id)).toEqual(['s1318', 's1322', 's1240', 's1206', 's42']);
    expect(walkQ.stops(s, 'wlk-07', { order: 'walk' }).map((x) => x.walk_position)).toEqual([9, 10, 12, 13, 31]);
    db.close();
  });

  test('another reader on the same handset sees none of Ray’s route (R133)', () => {
    const db = openStore('silver-creek');
    seedMapleHeights(db);
    const dana = scoped(db, 'dana');
    expect(walkQ.routeCards(dana)).toEqual([]);
    expect(walkQ.stops(dana, 'wlk-07', { order: 'walk' })).toEqual([]);
    expect(walkQ.metersAtStop(dana, 's1318')).toEqual([]);
    expect(walkQ.findOnPhone(dana, '882')).toEqual([]);
    expect(walkQ.tally(dana, 'wlk-07').total).toBe(0);
    expect(walkQ.findOnPhone(scoped(db, RAY), '882').length).toBeGreaterThan(0);
    db.close();
  });

  test('a Lone Star route on the same handset lives in another file; Silver Creek’s walk never lists it (TC tenant isolation, R131)', () => {
    const factory = memoryFactory();
    const silver = openStore('silver-creek', factory);
    const lone = openStore('lone-star', factory);
    seedMapleHeights(silver);
    expect(walkQ.routeCards(scoped(lone, RAY))).toEqual([]);
    expect(walkQ.routeCards(scoped(silver, RAY)).map((r) => r.code)).toContain('WLK-07');
    expect(factory.files.size).toBe(2);
    silver.close();
    lone.close();
  });

  test('one reader per route is a row, not a constraint: a second reader can hold the same route (R87, US-FLD-062 TC-2)', () => {
    const db = openStore('silver-creek');
    seedMapleHeights(db);
    seedMapleHeights(db, { technician: 'marco' });
    expect(walkQ.routeCard(scoped(db, RAY), 'wlk-07')?.meters).toBe(10);
    expect(walkQ.routeCard(scoped(db, 'marco'), 'wlk-07')?.meters).toBe(10);
    db.close();
  });
});

describe('the frame', () => {
  test('with no reading services mounted, a reads route shows its placeholder and its doors', async () => {
    const app = await mountApp();
    await screen.findByTestId('screen-FF-63');
    const target = routeTo('RW-05');
    await act(async () => {
      app.ref.dispatch(CommonActions.navigate(target.name, target.params));
    });
    const page = screen.getAllByTestId('screen-RW-05').at(-1)!;
    expect(within(page).getByTestId('door-RW-06')).toBeTruthy();
    expect(within(page).getByText('RW-05')).toBeTruthy();
    app.unmount();
  });
});

describe('no colour and no pixel in the reads screens', () => {
  const DIR = resolve(__dirname, '../../../src/screens/reads');
  const files = readdirSync(DIR).filter((f) => /\.(ts|tsx)$/.test(f));
  test('the scan reads the whole folder', () => {
    // eslint-disable-next-line no-console
    console.log(`reads noLiterals: ${files.length} files read in src/screens/reads`);
    expect(files.length).toBeGreaterThanOrEqual(14);
  });
  test.each(files)('%s names no colour and no pixel', (file) => {
    expect(findLiterals(readFileSync(join(DIR, file), 'utf8'))).toEqual([]);
  });
});
