/**
 * FF-13 Map and FF-14 Stop (T-17), on the placeholder map view — the
 * `MapViewProps` port a real Esri map replaces.
 */
import 'react-native-gesture-handler/jestSetup';

import { fireEvent, screen, within } from '@testing-library/react-native';
import { Linking } from 'react-native';

import { project } from '../../../src/screens/theDay/mapView';
import { assertTouchTargets, current, currentParams, drawerOpen, mountDay, open } from './support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

describe('FF-13 Map', () => {
  test("today's jobs with a point are numbered pins in the day's order; the one with no point is counted, not guessed", async () => {
    const app = await mountDay();
    await open(app, 'FF-13');
    await screen.findByTestId('screen-FF-13');
    expect(screen.getAllByTestId(/^map-marker-/).map((m) => [m.props.testID, m.props.accessibilityLabel])).toEqual([
      ['map-marker-wo-4822', 'Stop 1, 1400 Elm Street · Unit A'],
      ['map-marker-wo-4824', 'Stop 2, 22 Cedar Court'],
      ['map-marker-wo-4831', 'Stop 3, 88 Hillcrest Avenue'],
    ]);
    expect(screen.getByTestId('map-off-map')).toHaveTextContent('1 not on the map');
    expect(screen.getByTestId('map-legend')).toHaveTextContent(/In progress.*Scheduled.*Queued/);
    app.unmount();
  });

  test('R31: offline, the map draws its offline state and the stop is still listed', async () => {
    const app = await mountDay({ status: { syncPending: 2, connection: 'offline', availability: 'available' } });
    await open(app, 'FF-13');
    expect(await screen.findByTestId('map-offline')).toHaveTextContent('No signal. The map needs one.');
    expect(screen.queryAllByTestId(/^map-marker-/)).toHaveLength(0);
    expect(screen.getByTestId('door-FF-14')).toBeTruthy();
    app.unmount();
  });

  test("'FF-13 → FF-14' choosing a pin, then the stop row, opens that stop", async () => {
    const app = await mountDay();
    await open(app, 'FF-13');
    fireEvent.press(await screen.findByTestId('map-marker-wo-4824'));
    expect(screen.getByTestId('door-FF-14').props.accessibilityLabel).toMatch(/^2 · 22 Cedar Court/);
    fireEvent.press(screen.getByTestId('door-FF-14'));
    expect(`FF-13 → ${current(app)}`).toBe('FF-13 → FF-14');
    expect(currentParams(app)).toEqual({ jobId: 'wo-4824' });
    app.unmount();
  });

  test("'FF-13 → FF-10' 'FF-13 → FF-42' 'FF-13 → FF-09'", async () => {
    const app = await mountDay();
    await open(app, 'FF-13');
    fireEvent.press((await screen.findAllByTestId('door-FF-10')).at(-1) as never);
    expect(`FF-13 → ${current(app)}`).toBe('FF-13 → FF-10');
    await open(app, 'FF-13');
    fireEvent.press((await screen.findAllByTestId('door-FF-42')).at(-1) as never);
    expect(`FF-13 → ${current(app)}`).toBe('FF-13 → FF-42');
    await open(app, 'FF-13');
    fireEvent.press((await screen.findAllByTestId('door-FF-09')).at(-1) as never);
    expect(drawerOpen(app)).toBe(true);
    app.unmount();
  }, 30_000);

  test('the placeholder projection keeps north up and every pin inside the box', () => {
    const pts = project([{ lat: 30.27, lng: -97.74 }, { lat: 30.25, lng: -97.76 }], 300, 200, 20);
    expect(pts[0]?.y).toBeLessThan(pts[1]?.y ?? 0);
    for (const p of pts) {
      expect(p.x).toBeGreaterThanOrEqual(20);
      expect(p.x).toBeLessThanOrEqual(280);
    }
  });
});

describe('FF-14 Stop', () => {
  test('the stop as drawn: state and priority, Stop 2 of 4, the street and the town, who · number, type · window', async () => {
    const app = await mountDay();
    await open(app, 'FF-14', { jobId: 'wo-4824' });
    const root = within(await screen.findByTestId('screen-FF-14'));
    expect(root.getByText('Scheduled')).toBeTruthy();
    expect(root.getByText('P1')).toBeTruthy();
    expect(root.getByTestId('stop-position')).toHaveTextContent('Stop 2 of 4');
    expect(root.getByTestId('stop-address')).toHaveTextContent('22 Cedar Court');
    expect(root.getByText('Austin, TX 78704')).toBeTruthy();
    expect(root.getByText('Aaron Bruner · WO-4824')).toBeTruthy();
    expect(root.getByText('Disconnect — non-payment · 12:00–17:00')).toBeTruthy();
    // No route time is measured, so none is shown.
    expect(root.queryByText(/Arrive/)).toBeNull();
    app.unmount();
  });

  test('Google Maps and Apple Maps get the street address and nothing else (Security §5)', async () => {
    const openURL = jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
    const app = await mountDay();
    await open(app, 'FF-14', { jobId: 'wo-4824' });
    fireEvent.press(await screen.findByTestId('stop-google'));
    fireEvent.press(screen.getByTestId('stop-apple'));
    const [google, apple] = openURL.mock.calls.map((c) => String(c[0]));
    expect(google).toBe('https://www.google.com/maps/dir/?api=1&destination=22%20Cedar%20Court%2C%20Austin%2C%20TX%2078704');
    expect(apple).toBe('https://maps.apple.com/?daddr=22%20Cedar%20Court%2C%20Austin%2C%20TX%2078704');
    for (const url of [google, apple]) expect(url).not.toMatch(/Bruner|4824|30\.25/);
    openURL.mockRestore();
    app.unmount();
  });

  test('with a position, the straight-line miles', async () => {
    const app = await mountDay({ fieldData: { location: { current: () => ({ lat: 30.27, lng: -97.74 }) } } });
    await open(app, 'FF-14', { jobId: 'wo-4824' });
    expect(await screen.findByTestId('stop-distance')).toHaveTextContent('1.8miles');
    app.unmount();
  });

  test('every control is named and at least 48pt', async () => {
    const app = await mountDay();
    await open(app, 'FF-14', { jobId: 'wo-4824' });
    const root = await screen.findByTestId('screen-FF-14');
    expect(assertTouchTargets(within(root).getAllByRole('button'))).toBeGreaterThanOrEqual(3);
    app.unmount();
  });

  test("'FF-14 → FF-15' Open the job", async () => {
    const app = await mountDay();
    await open(app, 'FF-14', { jobId: 'wo-4824' });
    fireEvent.press(await screen.findByTestId('door-FF-15'));
    expect(`FF-14 → ${current(app)}`).toBe('FF-14 → FF-15');
    expect(currentParams(app)).toEqual({ jobId: 'wo-4824' });
    app.unmount();
  });

  test('opened with no job, it says so and offers Today', async () => {
    const app = await mountDay();
    await open(app, 'FF-14');
    expect(await screen.findByTestId('stop-none')).toHaveTextContent(/No stop chosen/);
    app.unmount();
  });
});
