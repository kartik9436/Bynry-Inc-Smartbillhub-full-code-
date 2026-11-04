/**
 * FF-11 Nearby and FF-12 Claim (T-16) — US-FLD-023 §3, against a fake of the
 * server's two routes (N11, N15), and against the shipped port that names the
 * gap because neither route exists yet.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import { type NearbyJob, type NearbyPort } from '../../../src/screens/theDay/nearbyApi';
import { assertTouchTargets, current, currentParams, drawerOpen, mountDay, open } from './support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

const ELM: NearbyJob = { id: 'wo-4840', number: 'WO-4840', type: 'Routine read', priorityCode: 'P3', address: '1412 Elm Street', distanceMi: 0.2, dueAt: new Date(2026, 9, 22, 12).toISOString(), estMinutes: 10, takenBy: null };
const MAPLE: NearbyJob = { id: 'wo-4838', number: 'WO-4838', type: 'Meter seal check', priorityCode: 'P2', address: '9 Maple Court', distanceMi: 0.6, dueAt: null, estMinutes: 15, takenBy: null };
const BIRCH: NearbyJob = { id: 'wo-4835', number: 'WO-4835', type: 'Final read', priorityCode: 'P3', address: '60 Birch Lane', distanceMi: 1.4, dueAt: null, estMinutes: 20, takenBy: 'R. Patel' };

function fakeNearby(claimAnswer: Awaited<ReturnType<NearbyPort['claim']>> = { ok: true }) {
  const port = {
    list: jest.fn(async () => ({ jobs: [ELM, MAPLE, BIRCH], count: 3, hasMore: false })),
    claim: jest.fn(async () => claimAnswer),
  };
  return port;
}

describe('FF-11 Nearby', () => {
  test('3 unassigned within 2 miles, by distance; the taken one dimmed with no Claim (TC-1)', async () => {
    const nearby = fakeNearby();
    const app = await mountDay({ fieldData: { nearby } });
    await open(app, 'FF-11');
    expect(await screen.findByTestId('nearby-count')).toHaveTextContent('3 unassigned');
    expect(nearby.list).toHaveBeenCalledWith({ radiusMi: 2, page: 1 });
    expect(screen.getAllByTestId(/^nearby-wo-\d+$/).map((e) => e.props.testID)).toEqual(['nearby-wo-4840', 'nearby-wo-4838', 'nearby-wo-4835']);
    expect(screen.getByTestId('nearby-wo-4835-taken')).toHaveTextContent('Taken by R. Patel');
    expect(screen.queryByTestId('nearby-wo-4835-claim')).toBeNull();
    expect(screen.getByTestId('nearby-radius')).toHaveTextContent('Within 2 miles');
    app.unmount();
  });

  test('the radius is a setting: choosing 5 miles asks again with 5 (R34)', async () => {
    const nearby = fakeNearby();
    const app = await mountDay({ fieldData: { nearby } });
    await open(app, 'FF-11');
    fireEvent.press(await screen.findByTestId('nearby-radius'));
    await act(async () => {
      fireEvent.press(screen.getByTestId('nearby-radius-choice-5'));
    });
    expect(nearby.list).toHaveBeenLastCalledWith({ radiusMi: 5, page: 1 });
    app.unmount();
  });

  test('with the shipped port it says Nearby is not ready — never an empty radius', async () => {
    const app = await mountDay();
    await open(app, 'FF-11');
    expect(await screen.findByTestId('nearby-gap')).toHaveTextContent(/Not ready yet/);
    expect(screen.queryByTestId('nearby-count')).toBeNull();
    app.unmount();
  });

  test('every control is named and at least 48pt', async () => {
    const app = await mountDay({ fieldData: { nearby: fakeNearby() } });
    await open(app, 'FF-11');
    const root = await screen.findByTestId('screen-FF-11');
    await screen.findByTestId('nearby-count');
    expect(assertTouchTargets([...within(root).getAllByRole('button'), ...within(root).getAllByRole('tab')])).toBeGreaterThanOrEqual(5);
    app.unmount();
  });

  test("'FF-11 → FF-12' Claim opens the claim with the job; 'FF-11 → FF-10' Mine; 'FF-11 → FF-42' the bell; 'FF-11 → FF-50' the status chip; 'FF-11 → FF-09' the menu", async () => {
    const app = await mountDay({ fieldData: { nearby: fakeNearby() } });
    await open(app, 'FF-11');
    fireEvent.press(await screen.findByTestId('nearby-wo-4840-claim'));
    expect(`FF-11 → ${current(app)}`).toBe('FF-11 → FF-12');
    expect((currentParams(app)?.job as NearbyJob).id).toBe('wo-4840');
    await open(app, 'FF-11');
    fireEvent.press((await screen.findAllByTestId('door-FF-10')).at(-1) as never);
    expect(`FF-11 → ${current(app)}`).toBe('FF-11 → FF-10');
    await open(app, 'FF-11');
    fireEvent.press((await screen.findAllByTestId('door-FF-42')).at(-1) as never);
    expect(`FF-11 → ${current(app)}`).toBe('FF-11 → FF-42');
    await open(app, 'FF-11');
    fireEvent.press(screen.getByTestId('shell-status-sync'));
    expect(`FF-11 → ${current(app)}`).toBe('FF-11 → FF-50');
    await open(app, 'FF-11');
    fireEvent.press((await screen.findAllByTestId('door-FF-09')).at(-1) as never);
    expect(drawerOpen(app) ? 'FF-11 → FF-09' : 'closed').toBe('FF-11 → FF-09');
    app.unmount();
  }, 30_000);
});

describe('FF-12 Claim', () => {
  test('says what claiming does to the day: grows by 10 minutes, 2h 35m becomes 2h 45m (TC-2)', async () => {
    const app = await mountDay({ fieldData: { nearby: fakeNearby() } });
    await open(app, 'FF-12', { job: ELM });
    expect(await screen.findByTestId('claim-day-grows')).toHaveTextContent('Your day grows by 10 minutes. 2h 35m becomes 2h 45m.');
    expect(screen.getByTestId('claim-consequence')).toHaveTextContent('Dispatch is told. No one else can take it.');
    // The date is written by the app language's own rules (`en`: "Oct 22").
    expect(screen.getByText(/^(Oct 22|22 Oct)$/)).toBeTruthy();
    app.unmount();
  });

  test("'FF-12 → FF-10' a claim the server accepts joins the day", async () => {
    const nearby = fakeNearby({ ok: true });
    const app = await mountDay({ fieldData: { nearby } });
    await open(app, 'FF-12', { job: ELM });
    await act(async () => {
      fireEvent.press(await screen.findByTestId('claim-confirm'));
    });
    expect(nearby.claim).toHaveBeenCalledWith('wo-4840');
    expect(`FF-12 → ${current(app)}`).toBe('FF-12 → FF-10');
    app.unmount();
  });

  test('a job R. Patel took a moment ago is refused and says who has it (TC-3)', async () => {
    const app = await mountDay({ fieldData: { nearby: fakeNearby({ ok: false, takenBy: 'R. Patel' }) } });
    await open(app, 'FF-12', { job: ELM });
    await act(async () => {
      fireEvent.press(await screen.findByTestId('claim-confirm'));
    });
    expect(screen.getByTestId('claim-taken')).toHaveTextContent('Taken by R. Patel');
    expect(screen.queryByTestId('claim-confirm')).toBeNull();
    expect(current(app)).toBe('FF-12');
    app.unmount();
  });

  test('with the shipped port the claim says it is not ready, and nothing moves', async () => {
    const app = await mountDay();
    await open(app, 'FF-12', { job: ELM });
    await act(async () => {
      fireEvent.press(await screen.findByTestId('claim-confirm'));
    });
    expect(screen.getByTestId('claim-gap')).toHaveTextContent('Claiming is not ready yet.');
    expect(current(app)).toBe('FF-12');
    app.unmount();
  });

  test("'FF-12 → FF-11' Cancel goes back to Nearby", async () => {
    const app = await mountDay({ fieldData: { nearby: fakeNearby() } });
    await open(app, 'FF-11');
    fireEvent.press(await screen.findByTestId('nearby-wo-4840-claim'));
    fireEvent.press(await screen.findByTestId('door-FF-11'));
    expect(`FF-12 → ${current(app)}`).toBe('FF-12 → FF-11');
    app.unmount();
  });
});
