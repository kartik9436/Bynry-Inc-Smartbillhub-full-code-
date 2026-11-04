/**
 * FF-63 Home (T-16) — US-FLD-078 §3: both modules at a glance, what is left
 * and what is next, never how fast.
 */
import 'react-native-gesture-handler/jestSetup';

import { fireEvent, screen, within } from '@testing-library/react-native';

import { assertTouchTargets, current, drawerOpen, mountDay } from './support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

describe('FF-63 Home', () => {
  test('Jobs: 4 left today · 1 done · 1 on hold, and NEXT is the first job by window (TC-1)', async () => {
    const app = await mountDay();
    expect(screen.getByTestId('home-jobs-left')).toHaveTextContent('4left today');
    expect(screen.getByTestId('home-jobs-done')).toHaveTextContent('1done');
    expect(screen.getByTestId('home-jobs-hold')).toHaveTextContent('1on hold');
    const jobs = within(screen.getByTestId('home-jobs'));
    expect(jobs.getByText('1400 Elm Street · Unit A')).toBeTruthy();
    expect(jobs.getByText('08:00–12:00')).toBeTruthy();
    app.unmount();
  });

  test('Reads: 4 meters left · 2 read · 1 could not be; with no position the tile says NEXT stop, never nearest', async () => {
    const app = await mountDay();
    expect(screen.getByTestId('home-reads-left')).toHaveTextContent('4meters left');
    expect(screen.getByTestId('home-reads-read')).toHaveTextContent('2read');
    expect(screen.getByTestId('home-reads-could-not')).toHaveTextContent('1could not be');
    const reads = within(screen.getByTestId('home-reads'));
    expect(reads.getByText('Next stop')).toBeTruthy();
    expect(reads.queryByText('Nearest stop')).toBeNull();
    expect(reads.getByText('1318 Maple Street · 3 meters')).toBeTruthy();
    expect(reads.getByText('route WLK-07')).toBeTruthy();
    app.unmount();
  });

  test('with a position it takes the NEAREST stop and says how far', async () => {
    const app = await mountDay({ fieldData: { location: { current: () => ({ lat: 30.28, lng: -97.73 }) } } });
    const reads = within(screen.getByTestId('home-reads'));
    expect(reads.getByText('Nearest stop')).toBeTruthy();
    expect(reads.getByText('9 Oak Ridge · 1 meter')).toBeTruthy();
    expect(reads.getByText(/0\.0 mi away · route WLK-07/)).toBeTruthy();
    app.unmount();
  });

  test('the hours row: 4h 52m today · Travel 48m · on site 3h 04m · admin 1h', async () => {
    const app = await mountDay();
    const row = screen.getByTestId('door-FF-47');
    expect(row.props.accessibilityLabel).toBe('4h 52m today, Travel 48m · on site 3h 04m · admin 1h');
    app.unmount();
  });

  test('no pace, no average, no rank anywhere on Home (TC-3, R120)', async () => {
    const app = await mountDay();
    const root = screen.getByTestId('screen-FF-63');
    expect(within(root).queryByText(/per hour|average|avg|rank|fastest|slowest|pace/i)).toBeNull();
    app.unmount();
  });

  test('every control is named and at least 48pt', async () => {
    const app = await mountDay();
    const root = screen.getByTestId('screen-FF-63');
    expect(assertTouchTargets(within(root).getAllByRole('button'))).toBeGreaterThanOrEqual(6);
    app.unmount();
  });

  test('with no store it says so, and offers Sync', async () => {
    const app = await mountDay({ noStore: true });
    expect(screen.getByTestId('home-not-loaded')).toHaveTextContent(/Day not loaded/);
    app.unmount();
  });

  describe('its doors, by address', () => {
    const cases: Array<[string, string, string]> = [
      ['FF-63 → FF-10', 'door-FF-10', 'FF-10'],
      ['FF-63 → RW-01', 'door-RW-01', 'RW-01'],
      ['FF-63 → FF-38', 'door-FF-38', 'FF-38'],
      ['FF-63 → FF-37', 'door-FF-37', 'FF-37'],
      ['FF-63 → FF-47', 'door-FF-47', 'FF-47'],
      ['FF-63 → FF-50', 'sync-strip-open', 'FF-50'],
      ['FF-63 → FF-42', 'door-FF-42', 'FF-42'],
    ];
    test.each(cases)('%s', async (_name, testID, target) => {
      const app = await mountDay();
      fireEvent.press(screen.getAllByTestId(testID).at(-1) as never);
      expect(`FF-63 → ${current(app)}`).toBe(`FF-63 → ${target}`);
      app.unmount();
    });

    test("'FF-63 → FF-09' the menu button opens the drawer", async () => {
      const app = await mountDay();
      fireEvent.press(screen.getAllByTestId('open-menu').at(-1) as never);
      expect(drawerOpen(app)).toBe(true);
      app.unmount();
    });
  });
});
