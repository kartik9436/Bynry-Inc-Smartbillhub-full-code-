/**
 * DEF-FLD-10578 (beta report MQ-023): from INSIDE a job, every door that
 * opens a job-scoped screen opens it for THAT job — never *"Not on this
 * phone. Open it from a job."*
 *
 * The app is mounted the way `session/FieldRuntime.tsx` mounts it: the job
 * services (`JobPortProvider`) AND the on-site data (`FieldDataProvider`)
 * both above the REAL navigator, over one handset store. The job is opened
 * the way Today opens it — FF-15 by address with the order's id — and no job
 * is pre-set in the port, so the only way a later screen can know the job is
 * the one the app really has.
 *
 * Why the old tests missed it: the doors tests assert which SCREEN a door
 * opens, never that it shows the JOB, and the tablet panes pass `workOrderId`
 * explicitly. So each door here asserts the job's number where the screen
 * draws it (the body or the header), and otherwise a fact only WO-4822 has in
 * the fixture (its customer, its crew, its parts, its labour) — the fixture
 * holds four jobs, so a screen showing another job's or no job's data fails.
 *
 * Red proof (law 7), on the code before the fix (824517918): 12 of 13 failed.
 * Every door but Hand back failed on
 * `expect(within(top).queryByTestId('not-on-phone')).toBeNull()`; Hand back
 * (a job screen, which already read the port) and every door once the shared
 * lookup alone was in failed on `expect(current(ref).params.workOrderId)
 * .toBe(WO)` — Received: undefined — until the doors carried the job. Only
 * F3 (no job anywhere still says so) passed, as it must.
 */
import 'react-native-gesture-handler/jestSetup';

import { screen, within } from '@testing-library/react-native';

import type { ScreenId } from '../../../src/navigation/screens';
import type { JobServices } from '../../../src/screens/theJob/JobPort';
import { current, DANA, makeWave, type Wave } from '../onSite/fixture';
import { mountPhone as mount, onTop, open, press } from './phone';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./window').currentWindow(),
}));

const WO = 'wo-4822';

/** The on-site fixture's handset, with the job services over the same store. */
function mountPhone(w: Wave) {
  const services: JobServices = {
    db: w.db,
    captor: () => ({ technicianId: DANA, capturedBy: DANA }),
    displayName: 'D. Ortiz',
    clock: w.clock,
    newId: w.data.newId,
  };
  return mount(services, w.data);
}

interface Case {
  name: string;
  /** The doors pressed, in order, from FF-15: [screen it is on, control]. */
  path: Array<[ScreenId, string]>;
  opens: ScreenId;
  /** What only WO-4822 shows: its number where the screen draws it, else one of its own facts (a field's value when it is typed in one). */
  shows: RegExp | { value: string };
}

const CASES: Case[] = [
  { name: 'Customer', path: [['FF-15', 'door-FF-25']], opens: 'FF-25', shows: /WO-4822/ },
  { name: 'Help and SOPs', path: [['FF-15', 'door-FF-28']], opens: 'FF-28', shows: /Water shut-off SOP/ },
  { name: 'Crew', path: [['FF-15', 'door-FF-29']], opens: 'FF-29', shows: /M\. Chen/ },
  { name: 'Notes', path: [['FF-15', 'door-FF-30']], opens: 'FF-30', shows: /WO-4822/ },
  { name: 'Activity (the row)', path: [['FF-15', 'job-activity']], opens: 'FF-31', shows: /WO-4822/ },
  { name: 'Activity (the ⋮ menu)', path: [['FF-15', 'door-FF-31']], opens: 'FF-31', shows: /WO-4822/ },
  { name: 'Money to check', path: [['FF-15', 'door-FF-61']], opens: 'FF-61', shows: /A-10432/ },
  { name: 'Hand back', path: [['FF-15', 'door-FF-58']], opens: 'FF-58', shows: /WO-4822/ },
  { name: 'Debrief (Readings)', path: [['FF-15', 'door-FF-20'], ['FF-20', 'door-FF-32']], opens: 'FF-32', shows: /1h 12m/ },
  { name: 'Signature (Debrief)', path: [['FF-15', 'door-FF-20'], ['FF-20', 'door-FF-32'], ['FF-32', 'door-FF-33']], opens: 'FF-33', shows: { value: 'Sarah Miller' } },
  { name: 'Close (Photos)', path: [['FF-15', 'door-FF-20'], ['FF-20', 'door-FF-21'], ['FF-21', 'door-FF-34']], opens: 'FF-34', shows: /2 · Water meter 5\/8"/ },
];

describe('DEF-FLD-10578: every job-scoped door, pressed from inside WO-4822', () => {
  test.each(CASES)('$name opens $opens for WO-4822, not "Not on this phone"', async (c) => {
    const w = makeWave();
    const ref = await mountPhone(w);
    await open(ref, 'FF-15', { workOrderId: WO });
    for (const [from, control] of c.path) press(from, control);
    const top = onTop(c.opens);
    expect(within(top).queryByTestId('not-on-phone')).toBeNull();
    // Only the screen on top is visible (the stack hides the ones beneath), so
    // this cannot pass on FF-15's own title.
    if (c.shows instanceof RegExp) expect(screen.getAllByText(c.shows).length).toBeGreaterThan(0);
    else expect(screen.getAllByDisplayValue(c.shows.value).length).toBeGreaterThan(0);
    expect(current(ref).params.workOrderId).toBe(WO);
  });

  test('Reopen (FF-36) opened with no job named reads the open job', async () => {
    const w = makeWave();
    const ref = await mountPhone(w);
    await open(ref, 'FF-15', { workOrderId: WO });
    await open(ref, 'FF-36');
    const top = onTop('FF-36');
    expect(within(top).queryByTestId('not-on-phone')).toBeNull();
    expect(screen.getAllByText(/WO-4822/).length).toBeGreaterThan(0);
  });

  test('F3: with no job named and none open, the screen still says so', async () => {
    const w = makeWave();
    const ref = await mountPhone(w);
    await open(ref, 'FF-32');
    expect(within(onTop('FF-32')).getByTestId('not-on-phone')).toBeTruthy();
  });
});
