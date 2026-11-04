/**
 * DEF-FLD-10608 on screen — FF-08 *Loading your day* when something did not
 * load (decision log 2026-10-26, FA-10): the reason in words, a Retry that
 * re-runs only what failed, *Some jobs are not on the phone.* only when
 * something failed, and *Open my day* still a button — never a jump.
 *
 * The port is the real `engineFirstSync`; only the sync behind it is scripted
 * (the engine's own behaviour is `tests/sync/def_fld_10608_first_sync.test.ts`).
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen } from '@testing-library/react-native';

import { engineFirstSync, type FirstSyncResult } from '../../../src/screens/gettingIn/firstSync';
import { current, mountDay, open } from '../theDay/support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

const ok = (over: Partial<FirstSyncResult> = {}): FirstSyncResult => ({
  pull: { upserts: 11 },
  pullError: null,
  failures: { pull: null, bundles: null, templates: null },
  bundles: { fetched: 11, failed: 0 },
  ...over,
});

/** A scripted sync: each call answers the next result in order. */
function scripted(...results: FirstSyncResult[]) {
  const calls: string[] = [];
  const port = engineFirstSync(async (what) => {
    calls.push(what);
    const r = results.shift();
    if (!r) throw new Error('not scripted');
    return r;
  });
  return { port, calls };
}

async function mountFF08(port: ReturnType<typeof scripted>['port']) {
  const app = await mountDay({ fieldData: { firstSync: port } });
  await open(app, 'FF-08');
  await screen.findByTestId('screen-FF-08');
  await act(async () => undefined);
  return app;
}

const jobsRow = () => screen.getByTestId('first-sync-jobs').props.accessibilityLabel as string;

describe('FF-08 when something did not load', () => {
  test('feed ok + one job’s details 500 → Jobs 10 of 11, Server error, 100%, Open my day ENABLED, Retry and the Skip warning shown', async () => {
    const { port } = scripted(ok({ bundles: { fetched: 10, failed: 1, lastFailure: { kind: 'network', status: 500 } } }));
    const app = await mountFF08(port);
    expect(jobsRow()).toBe('Jobs and checklists, Done, 10 of 11');
    expect(screen.getByTestId('first-sync-percent')).toHaveTextContent(/^100%/);
    expect(screen.getByTestId('first-sync-reason')).toHaveTextContent('Server error.');
    expect(screen.getByTestId('first-sync-retry')).toHaveTextContent('Retry');
    expect(screen.getByTestId('first-sync-skip-warning')).toHaveTextContent('Some jobs are not on the phone.');
    expect(screen.queryByTestId('first-sync-to-come')).toBeNull();
    // A button, never a jump: still on FF-08 until it is pressed.
    expect(current(app)).toBe('FF-08');
    expect(screen.getByTestId('door-FF-10')).not.toBeDisabled();
    fireEvent.press(screen.getByTestId('door-FF-10'));
    expect(current(app)).toBe('FF-10');
    app.unmount();
  });

  test('the template catalogue failing leaves Jobs done — no reason, no Retry, no warning', async () => {
    const { port } = scripted(ok({ templatesError: 'HTTP 503', failures: { pull: null, bundles: null, templates: { kind: 'network', status: 503 } } }));
    const app = await mountFF08(port);
    expect(jobsRow()).toBe('Jobs and checklists, Done, Done');
    expect(screen.queryByTestId('first-sync-reason')).toBeNull();
    expect(screen.queryByTestId('first-sync-retry')).toBeNull();
    expect(screen.queryByTestId('first-sync-skip-warning')).toBeNull();
    expect(screen.getByTestId('door-FF-10')).not.toBeDisabled();
    app.unmount();
  });

  test('signed out → Did not load, "Signed out. Sign in again.", Open my day stays disabled', async () => {
    const { port } = scripted({ pull: null, pullError: null, stoppedForAuth: true });
    const app = await mountFF08(port);
    expect(jobsRow()).toBe('Jobs and checklists, Did not load, Did not load');
    expect(screen.getByTestId('first-sync-reason')).toHaveTextContent('Signed out. Sign in again.');
    expect(screen.getByTestId('door-FF-10')).toBeDisabled();
    expect(screen.getByTestId('first-sync-skip-warning')).toBeTruthy();
    app.unmount();
  });

  test('a call that hit its time limit reads "No signal."; Retry re-runs the whole sync and reaches 100%', async () => {
    const { port, calls } = scripted(
      { pull: null, pullError: 'no answer in 30000 ms', failures: { pull: { kind: 'network' }, bundles: null, templates: null } },
      ok(),
    );
    const app = await mountFF08(port);
    expect(screen.getByTestId('first-sync-reason')).toHaveTextContent('No signal.');
    expect(screen.getByTestId('door-FF-10')).toBeDisabled();
    await act(async () => {
      fireEvent.press(screen.getByTestId('first-sync-retry'));
    });
    expect(calls).toEqual(['all', 'all']);
    expect(screen.getByTestId('first-sync-percent')).toHaveTextContent(/^100%/);
    expect(jobsRow()).toBe('Jobs and checklists, Done, Done');
    expect(screen.queryByTestId('first-sync-reason')).toBeNull();
    expect(screen.queryByTestId('first-sync-retry')).toBeNull();
    expect(screen.queryByTestId('first-sync-skip-warning')).toBeNull();
    expect(screen.getByTestId('door-FF-10')).not.toBeDisabled();
    app.unmount();
  });

  test('Retry after missing details fetches the details alone and clears the warning', async () => {
    const { port, calls } = scripted(
      ok({ bundles: { fetched: 10, failed: 1, lastFailure: { kind: 'network', status: 502 } } }),
      ok({ pull: null, bundles: { fetched: 1, failed: 0 } }),
    );
    const app = await mountFF08(port);
    await act(async () => {
      fireEvent.press(screen.getByTestId('first-sync-retry'));
    });
    expect(calls).toEqual(['all', 'details']);
    expect(jobsRow()).toBe('Jobs and checklists, Done, Done');
    expect(screen.queryByTestId('first-sync-skip-warning')).toBeNull();
    app.unmount();
  });

  test('nothing failed → no reason, no Retry, no Skip warning', async () => {
    const { port } = scripted(ok());
    const app = await mountFF08(port);
    expect(screen.getByTestId('first-sync-percent')).toHaveTextContent(/^100%/);
    expect(screen.queryByTestId('first-sync-reason')).toBeNull();
    expect(screen.queryByTestId('first-sync-retry')).toBeNull();
    expect(screen.queryByTestId('first-sync-skip-warning')).toBeNull();
    app.unmount();
  });
});
