/**
 * R122 on the MOUNTED app, at every window the check runs at (landscape 1024,
 * 1194, 1366; portrait 768, 834): no fixed pane leaves its flexible sibling
 * under 260. Three shapes are measured each time —
 *
 *   FF-10 (T2, a filled layout): the list at its width and the detail ≥ 260,
 *     or, where that cannot be, the phone's Today alone in the frame (no list
 *     pane squeezed beside a broken detail);
 *   FF-16 (T3, the shared job pane): the 300 context and content ≥ 260, or
 *     the content alone;
 *   FF-20 (T4, the readings grid): never more columns than `fitColumns`
 *     gives the pane, so no column is under 260.
 *
 * And on a phone there is no frame at all and the status strip is back.
 */
import 'react-native-gesture-handler/jestSetup';

import { screen, within } from '@testing-library/react-native';

import * as woReadingQ from '../../src/db/queries/woReading';
import { scoped } from '../../src/db/scoped';
import { COLUMN_GAP } from '../../src/tablet/columns';
import { CHECK_WIDTHS, fitColumns, GEOMETRY, resolveFrame } from '../../src/tablet/geometry';
import { DANA, local } from '../screens/onSite/fixture';
import { frameOf, mountTablet, paneWidth, setWindow } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./harness').tabletWindow,
}));

const WINDOWS: Array<[number, number]> = [
  [CHECK_WIDTHS.landscape[0], 768],
  [CHECK_WIDTHS.landscape[1], 834],
  [CHECK_WIDTHS.landscape[2], 1024],
  [CHECK_WIDTHS.portrait[0], 1024],
  [CHECK_WIDTHS.portrait[1], 1194],
];

const findings: string[] = [];
afterAll(() => console.log(`tablet widths (mounted): ${findings.join(' · ')}`));

test.each(WINDOWS)('at %i × %i every pane keeps its flexible sibling at 260 or more', async (w, h) => {
  setWindow(w, h);
  const app = await mountTablet();
  const s = scoped(app.db, DANA);
  for (const [id, pos] of [['r-22-2', 2], ['r-22-3', 3], ['r-22-4', 4]] as const) {
    woReadingQ.upsert(s, { id, workOrderId: 'wo-4822', position: pos, prompt: `Sub-meter ${pos}`, unit: 'gal' }, local(20, 7));
  }

  // T2 — Today.
  await app.open('FF-10');
  const t2 = resolveFrame('T2', w);
  const today = within(frameOf('FF-10'));
  if (t2.collapsed) {
    expect(today.queryByTestId('tablet-pane-list')).toBeNull();
    expect(within(today.getByTestId('tablet-pane-detail')).getByTestId('screen-FF-10')).toBeTruthy();
    findings.push(`T2@${w} one pane`);
  } else {
    const list = paneWidth(today.getByTestId('tablet-pane-list'));
    expect(list).toBe(t2.fixed?.width);
    const usable = w - GEOMETRY.sidebar - Number(list) - 2 * GEOMETRY.gutter;
    expect(usable).toBeGreaterThanOrEqual(GEOMETRY.minFlexible);
    expect(today.getByTestId('today-detail')).toBeTruthy();
    findings.push(`T2@${w} ${list}+${usable}`);
  }

  // T3 — Safety beside the job pane.
  await app.open('FF-16', { workOrderId: 'wo-4822' });
  const t3 = resolveFrame('T3', w);
  const safety = within(frameOf('FF-16'));
  if (t3.collapsed) {
    expect(safety.queryByTestId('tablet-pane-context')).toBeNull();
    findings.push(`T3@${w} one pane`);
  } else {
    expect(paneWidth(safety.getByTestId('tablet-pane-context'))).toBe(GEOMETRY.contextPane);
    const usable = w - GEOMETRY.sidebar - GEOMETRY.contextPane - 2 * GEOMETRY.gutter;
    expect(usable).toBeGreaterThanOrEqual(GEOMETRY.minFlexible);
    expect(safety.getByTestId('job-context-pane')).toBeTruthy();
    findings.push(`T3@${w} ${GEOMETRY.contextPane}+${usable}`);
  }

  // T4 — the readings grid.
  await app.open('FF-20', { workOrderId: 'wo-4822' });
  const usable = w - GEOMETRY.sidebar - 2 * GEOMETRY.gutter;
  const columns = fitColumns(usable, COLUMN_GAP, 2);
  const rows = within(frameOf('FF-20')).queryAllByTestId('readings-row');
  if (columns === 1) expect(rows).toHaveLength(0);
  else {
    for (const row of rows) expect(within(row).getAllByTestId('readings-cell').length).toBeLessThanOrEqual(columns);
    expect((usable - COLUMN_GAP * (columns - 1)) / columns).toBeGreaterThanOrEqual(GEOMETRY.minFlexible);
  }
  findings.push(`T4@${w} ${columns} col`);
}, 120_000);

test('on a phone (390 × 844) there is no frame, and the status strip is drawn', async () => {
  setWindow(390, 844);
  const app = await mountTablet();
  await app.open('FF-10');
  expect(screen.getAllByTestId('screen-FF-10').length).toBeGreaterThan(0);
  expect(screen.UNSAFE_root.findAll((n: typeof screen.UNSAFE_root) => n.props.nativeID === 'frame-of-FF-10')).toHaveLength(0);
  expect(screen.getByTestId('shell-status')).toBeTruthy();
}, 120_000);
