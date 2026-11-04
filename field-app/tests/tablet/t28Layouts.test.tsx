/**
 * T-28 — the eight screens that change shape on a tablet, each mounted under
 * the REAL navigator at the board's 1024 × 768 from one fixture store, by its
 * address (never bare — hard-won law 2's fixture lesson):
 *
 *   FF-10 Today beside the job · FF-15 the job beside its tasks · FF-13 stops
 *   beside the map · FF-39 the asset beside the search · FF-42 alerts beside
 *   the emergency · FF-20 readings in columns · FF-21 the photo wall ·
 *   FF-35 completed work beside its record.
 *
 * For each: the right frame, the right panes in it, the fixed pane at its
 * width (R122), the content each pane shows — and for the list + detail ones,
 * that picking an item keeps the list on screen (the route does not change)
 * and moves the detail.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import * as woReadingQ from '../../src/db/queries/woReading';
import { scoped } from '../../src/db/scoped';
import { GEOMETRY, fitColumns, listPaneWidth } from '../../src/tablet/geometry';
import { COLUMN_GAP } from '../../src/tablet/columns';
import { DANA, local } from '../screens/onSite/fixture';
import { frameOf, mountTablet, paneWidth, setWindow } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./harness').tabletWindow,
}));

type Instance = typeof screen.UNSAFE_root;
const pane = (frame: Instance, id: string) => within(frame).getByTestId(id);

beforeEach(() => setWindow(1024, 768));

describe('at 1024 × 768', () => {
  test('FF-10 Today: the day in a 340 list, the first job beside it; a pick keeps the list', async () => {
    const app = await mountTablet({ status: { syncPending: 12, connection: 'online', availability: 'available' } });
    await app.open('FF-10');
    const frame = frameOf('FF-10');
    expect(frame.props.testID).toBe('tablet-frame-T2');
    const list = pane(frame, 'tablet-pane-list');
    expect(paneWidth(list)).toBe(listPaneWidth(1024));
    expect(within(list).getByTestId('screen-FF-10')).toBeTruthy();
    const detail = pane(frame, 'tablet-pane-detail');
    // The first job of the day is picked and shown, as the board draws it.
    const first = within(list).getAllByTestId(/^job-wo-\d+-open$/)[0]!;
    const firstId = String(first.props.testID).replace(/^job-|-open$/g, '');
    await act(async () => undefined);
    expect(within(detail).getByTestId('today-detail-parts')).toBeTruthy();
    expect(within(list).getByTestId(`job-${firstId}-open`).props.accessibilityState).toMatchObject({ selected: true });

    // Pick WO-4822: the route stays FF-10, the list stays, the detail moves.
    fireEvent.press(within(list).getByTestId('job-wo-4822-open'));
    expect(app.current()).toBe('FF-10');
    expect(within(frameOf('FF-10')).getByTestId('tablet-pane-list')).toBeTruthy();
    const after = within(frameOf('FF-10')).getByTestId('today-detail');
    expect(within(after).getByText('WO-4822')).toBeTruthy();
    expect(within(after).getByText('Sarah Miller')).toBeTruthy();
    expect(within(after).getByTestId('today-detail-continue')).toBeTruthy();
    // The status strip is not drawn on a tablet; the sidebar carries both figures.
    expect(screen.queryByTestId('shell-status')).toBeNull();
    expect(screen.getByTestId('menu-FF-50-count')).toHaveTextContent('12');
    expect(screen.getByTestId('menu-availability')).toBeTruthy();
    // Continue opens the job's step with the job named.
    fireEvent.press(within(after).getByTestId('today-detail-continue'));
    expect(['FF-16', 'FF-17']).toContain(app.current());
    expect(app.ref.getCurrentRoute()?.params).toMatchObject({ workOrderId: 'wo-4822' });
  }, 120_000);

  test('FF-15 Job: the job in the 300 context, its tasks beside it', async () => {
    const app = await mountTablet();
    await app.open('FF-15', { workOrderId: 'wo-4822' });
    const frame = frameOf('FF-15');
    expect(frame.props.testID).toBe('tablet-frame-T3');
    const context = pane(frame, 'tablet-pane-context');
    expect(paneWidth(context)).toBe(GEOMETRY.contextPane);
    expect(within(context).getByTestId('job-pane')).toBeTruthy();
    expect(within(context).getByText('WO-4822')).toBeTruthy();
    expect(within(context).getByTestId('door-FF-25')).toBeTruthy();
    const content = pane(frame, 'tablet-pane-content');
    expect(within(content).getByTestId('screen-FF-15')).toBeTruthy();
    expect(within(content).getByTestId('job-tasks-pane')).toBeTruthy();
    expect(within(content).getByTestId('tasks-count')).toHaveTextContent(/of/);
    // The job's own customer door still goes where FF-15's does.
    fireEvent.press(within(context).getByTestId('door-FF-25'));
    expect(app.current()).toBe('FF-25');
  }, 120_000);

  test('FF-13 Map: the stops in the list, the map beside them; a stop is picked, not opened', async () => {
    const app = await mountTablet();
    await app.open('FF-13');
    const frame = frameOf('FF-13');
    const list = pane(frame, 'tablet-pane-list');
    expect(within(list).getByTestId('stops-pane')).toBeTruthy();
    expect(within(pane(frame, 'tablet-pane-detail')).getByTestId('map-pane')).toBeTruthy();
    expect(within(list).getByTestId('stops-navigate')).toHaveTextContent('Navigate to stop 1');
    const stops = within(list).getAllByTestId(/^stop-wo-/);
    expect(stops.length).toBeGreaterThan(1);
    fireEvent.press(stops[1]!);
    expect(app.current()).toBe('FF-13');
    expect(within(frameOf('FF-13')).getByTestId('stops-navigate')).toHaveTextContent('Navigate to stop 2');
  }, 120_000);

  test('FF-39 Assets: the search beside the meter; a hit picks, the search stays', async () => {
    const app = await mountTablet();
    await app.open('FF-39', { assetId: 'a-4471' });
    const frame = frameOf('FF-39');
    const list = pane(frame, 'tablet-pane-list');
    const detail = pane(frame, 'tablet-pane-detail');
    expect(within(list).getByTestId('asset-search')).toBeTruthy();
    expect(within(detail).getByTestId('asset-detail-pane')).toBeTruthy();
    expect(within(detail).getAllByText('W-4471').length).toBeGreaterThan(0);
    expect(within(detail).getByTestId('identity')).not.toHaveTextContent(/W-4471-A/);
    fireEvent.changeText(within(list).getByTestId('asset-search'), 'W-4471');
    fireEvent.press(within(frameOf('FF-39')).getByTestId('asset-W-4471-A'));
    expect(app.current()).toBe('FF-39');
    const after = within(frameOf('FF-39'));
    expect(after.getByTestId('asset-search')).toBeTruthy();
    expect(within(after.getByTestId('asset-detail-pane')).getByTestId('identity')).toHaveTextContent(/W-4471-A/);
  }, 120_000);

  test('FF-42 Alerts: the list beside the emergency; opening it keeps the list', async () => {
    const app = await mountTablet();
    await app.open('FF-42');
    const frame = frameOf('FF-42');
    const list = pane(frame, 'tablet-pane-list');
    expect(within(list).getByTestId('screen-FF-42')).toBeTruthy();
    expect(within(list).getByText('Aaron Bruner has paid')).toBeTruthy();
    const detail = pane(frame, 'tablet-pane-detail');
    expect(within(detail).getByTestId('screen-FF-43')).toBeTruthy();
    fireEvent.press(within(list).getByTestId('door-FF-43'));
    expect(app.current()).toBe('FF-42');
    expect(within(frameOf('FF-42')).getByTestId('tablet-pane-list')).toBeTruthy();
  }, 120_000);

  test('FF-20 Readings: one wide pane, the cards in as many columns of 260 as it holds', async () => {
    const app = await mountTablet();
    const s = scoped(app.db, DANA);
    for (const [id, pos, prompt] of [['r-22-2', 2, 'Sub-meter A'], ['r-22-3', 3, 'Sub-meter B']] as const) {
      woReadingQ.upsert(s, { id, workOrderId: 'wo-4822', position: pos, prompt, unit: 'gal' }, local(20, 7));
    }
    await app.open('FF-20', { workOrderId: 'wo-4822' });
    const frame = frameOf('FF-20');
    expect(frame.props.testID).toBe('tablet-frame-T4');
    const usable = 1024 - GEOMETRY.sidebar - 2 * GEOMETRY.gutter;
    const columns = fitColumns(usable, COLUMN_GAP, 2);
    expect(columns).toBe(2);
    const rows = within(frame).getAllByTestId('readings-row');
    expect(rows.map((r) => within(r).getAllByTestId('readings-cell').length)).toEqual([2, 1]);
    expect((usable - COLUMN_GAP) / columns).toBeGreaterThanOrEqual(GEOMETRY.minFlexible);
  }, 120_000);

  test('FF-21 Photos: grouped by what each proves, a wall of columns of 260', async () => {
    const app = await mountTablet();
    await app.open('FF-21', { workOrderId: 'wo-4822' });
    const frame = frameOf('FF-21');
    expect(frame.props.testID).toBe('tablet-frame-T4');
    const tasks = within(frame).getByTestId('photos-group-task');
    expect(within(tasks).getByText('From the tasks')).toBeTruthy();
    const columns = fitColumns(1024 - GEOMETRY.sidebar - 2 * GEOMETRY.gutter, COLUMN_GAP, 4);
    for (const row of within(frame).getAllByTestId('photos-row')) {
      expect(within(row).getAllByTestId('photos-cell').length).toBeLessThanOrEqual(columns);
    }
  }, 120_000);

  test('FF-35 Completed: the closed jobs beside the newest record; a card picks', async () => {
    const app = await mountTablet();
    await app.open('FF-35');
    const frame = frameOf('FF-35');
    const list = pane(frame, 'tablet-pane-list');
    expect(within(list).getByTestId('completed-list-pane')).toBeTruthy();
    expect(within(list).getByTestId('completed-WO-4824')).toBeTruthy();
    await act(async () => undefined);
    const detail = within(frameOf('FF-35')).getByTestId('completed-detail');
    expect(within(detail).getByText('WO-4824')).toBeTruthy();
    expect(within(detail).getByText('Passed')).toBeTruthy();
    // FB-030: the shared record (no labour or travel figures in history), with its signature line.
    expect(within(detail).getByTestId('completed-detail-record-signature')).toBeTruthy();
    expect(within(detail).queryByTestId('completed-detail-figures')).toBeNull();
    fireEvent.press(within(list).getByTestId('completed-WO-4824-pick'));
    expect(app.current()).toBe('FF-35');
    expect(within(frameOf('FF-35')).getByTestId('tablet-pane-list')).toBeTruthy();
  }, 120_000);
});

describe('T-29: a T2 board whose detail is already a screen', () => {
  test('RW-01 My routes beside RW-02; a route is picked, the list stays', async () => {
    const app = await mountTablet();
    await app.open('RW-01');
    const frame = frameOf('RW-01');
    const list = pane(frame, 'tablet-pane-list');
    const detail = pane(frame, 'tablet-pane-detail');
    expect(within(list).getByTestId('screen-RW-01')).toBeTruthy();
    expect(within(detail).getByTestId('screen-RW-02')).toBeTruthy();
    // Nothing picked: the reader's first route, the one the list rules heavy.
    const first = String(within(list).getByTestId('door-RW-02').props.accessibilityLabel);
    expect(within(detail).getByTestId('route-name')).toHaveTextContent(first);
    const other = first === 'Maple Heights' ? ['route-drv-02', 'Riverside East'] : ['route-wlk-07', 'Maple Heights'];
    fireEvent.press(within(list).getByTestId(other[0]!));
    expect(app.current()).toBe('RW-01');
    const after = within(frameOf('RW-01'));
    expect(after.getByTestId('tablet-pane-list')).toBeTruthy();
    expect(within(after.getByTestId('tablet-pane-detail')).getByTestId('route-name')).toHaveTextContent(other[1]!);
  }, 120_000);

  test('FF-63 Home: in the wide pane the Jobs and Reads tiles sit side by side (two columns of 260 fit)', async () => {
    const app = await mountTablet();
    await app.open('FF-63');
    const row = within(frameOf('FF-63')).getByTestId('home-tiles-row');
    expect(within(row).getByTestId('home-jobs')).toBeTruthy();
    expect(within(row).getByTestId('home-reads')).toBeTruthy();
  }, 120_000);
});
