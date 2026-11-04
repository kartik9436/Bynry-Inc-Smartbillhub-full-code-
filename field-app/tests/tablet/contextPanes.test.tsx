/**
 * T-29 — the two shared T3 context panes, read from a fixture store under the
 * real navigator at 1024 × 768:
 *
 *   the JOB pane beside FF-16 Safety (and every job T3 screen): the work
 *   order, its steps with their counts — the one on show marked — where, the
 *   customer, the clocks, and *The whole job*;
 *   the ROUTE pane beside RW-09 Read entry: the route, its progress, the stop,
 *   *The walk* and *Progress*.
 *
 * And the two reading screens that used to split themselves because the
 * WINDOW was a tablet now lay out by the pane they are given: RW-09's keypad
 * sits in the content beside the shared route pane (US-FLD-077 TC-2 — moved
 * here from `screens/reads/reading.test.tsx`, which runs at Jest's 750 window
 * where the T3 frame cannot hold two panes), and RW-05's stop sits beside its
 * list — since T-29 the T2 frame's own list and detail panes (TC-1, moved
 * from `route.test.tsx`).
 */
import 'react-native-gesture-handler/jestSetup';

import { fireEvent, screen, within } from '@testing-library/react-native';

import { CONTEXT_PANES } from '../../src/tablet/contextPanes';
import { frameOf, mountTablet, setWindow } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./harness').tabletWindow,
}));

beforeEach(() => setWindow(1024, 768));

test('both families have their pane registered', () => {
  expect(CONTEXT_PANES.job).toBeDefined();
  expect(CONTEXT_PANES.route).toBeDefined();
});

describe('the job pane', () => {
  test("beside FF-16 it shows WO-4822's steps, where, the customer and the clocks", async () => {
    const app = await mountTablet();
    await app.open('FF-16', { workOrderId: 'wo-4822' });
    const frame = frameOf('FF-16');
    expect(frame.props.testID).toBe('tablet-frame-T3');
    const pane = within(within(frame).getByTestId('tablet-pane-context'));
    expect(pane.getByTestId('job-context-number')).toHaveTextContent('WO-4822');
    expect(pane.getByText('Meter exchange')).toBeTruthy();
    // The steps, each with its count; the one on show is marked.
    for (const id of ['FF-16', 'FF-17', 'FF-23', 'FF-20', 'FF-21']) expect(pane.getByTestId(`job-pane-step-${id}`)).toBeTruthy();
    expect(pane.getByTestId('job-pane-step-FF-16').props.accessibilityState).toMatchObject({ selected: true });
    expect(pane.getByTestId('job-pane-step-FF-17').props.accessibilityState).toMatchObject({ selected: false });
    expect(pane.getByTestId('job-pane-step-FF-17')).toHaveTextContent(/Tasks.*0 of 1/);
    expect(pane.getByTestId('job-context-where')).toHaveTextContent(/1400 Elm Street · Unit A.*Austin, TX 78704/);
    expect(pane.getByTestId('job-context-customer')).toHaveTextContent(/Sarah Miller.*A-10432/);
    // 08:00–08:14 travel; 08:46–09:58 on site (D. Ortiz's own clock rows).
    expect(pane.getByTestId('job-context-clocks')).toHaveTextContent(/Travel 14m · on site 1h 12m/);
    // A step opens with the job named; the whole job opens FF-15.
    fireEvent.press(pane.getByTestId('job-pane-step-FF-17'));
    expect(app.current()).toBe('FF-17');
    expect(app.ref.getCurrentRoute()?.params).toMatchObject({ workOrderId: 'wo-4822' });
    const back = within(within(frameOf('FF-17')).getByTestId('tablet-pane-context'));
    expect(back.getByTestId('job-pane-step-FF-17').props.accessibilityState).toMatchObject({ selected: true });
    fireEvent.press(back.getByTestId('job-context-whole'));
    expect(app.current()).toBe('FF-15');
  }, 120_000);

  test('with no job named or open it says so and invents nothing', async () => {
    const app = await mountTablet();
    await app.open('FF-30');
    const pane = within(within(frameOf('FF-30')).getByTestId('tablet-pane-context'));
    expect(pane.getByTestId('job-context-none')).toHaveTextContent('No job open.');
    expect(pane.queryByTestId('job-context-steps')).toBeNull();
  }, 120_000);
});

describe('the route pane', () => {
  test('beside RW-09 it shows Maple Heights, its progress and the stop; the keypad sits beside it (US-FLD-077 TC-2)', async () => {
    const app = await mountTablet();
    await app.open('RW-09', { readId: 'r0471' });
    const frame = frameOf('RW-09');
    const pane = within(within(frame).getByTestId('tablet-pane-context'));
    expect(pane.getByTestId('route-context-name')).toHaveTextContent('Maple Heights');
    expect(pane.getByText('WLK-07 · Water · walk')).toBeTruthy();
    expect(pane.getByTestId('route-context-progress')).toHaveTextContent(/0 of 10/);
    expect(pane.getByTestId('route-context-where')).toHaveTextContent(/1318 Maple Street.*meters · stop 12/);
    const content = within(within(frame).getByTestId('tablet-pane-content'));
    expect(content.getByTestId('keypad')).toBeTruthy();
    // The screen no longer draws its own copy of the route beside the keypad.
    expect(screen.queryByTestId('entry-context')).toBeNull();
    // RW-09 → RW-06, the door the reads sweep records as drawn on the tablet pane.
    fireEvent.press(pane.getByTestId('route-context-stop'));
    expect(app.current()).toBe('RW-06');
    expect(app.ref.getCurrentRoute()?.params).toMatchObject({ stopId: 's1318' });
    await app.open('RW-09', { readId: 'r0471' });
    const again = within(within(frameOf('RW-09')).getByTestId('tablet-pane-context'));
    fireEvent.press(again.getByTestId('route-context-walk'));
    expect(app.current()).toBe('RW-05');
    expect(app.ref.getCurrentRoute()?.params).toMatchObject({ routeId: 'wlk-07' });
  }, 120_000);

  test('RW-05: the stop sits beside the list in the detail pane, and a tap shows it there (US-FLD-077 TC-1)', async () => {
    // T-29 (TABLET-3): RW-05 T is now a filled T2 board — the walk in the
    // list pane, the stop in the detail pane — where it used to split its
    // own single wide pane in two.
    const app = await mountTablet();
    await app.open('RW-05', { routeId: 'wlk-07' });
    const page = within(frameOf('RW-05'));
    const detail = within(within(page.getByTestId('tablet-pane-detail')).getByTestId('walk-stop'));
    expect(detail.getByText('1318 Maple Street')).toBeTruthy();
    expect(detail.getByText('Two dogs. Meters are at the front.')).toBeTruthy();
    fireEvent.press(within(page.getByTestId('tablet-pane-list')).getByTestId('stop-1'));
    expect(app.current()).toBe('RW-05');
    expect(within(within(frameOf('RW-05')).getByTestId('walk-stop')).getByText('1322 Maple Street')).toBeTruthy();
  }, 120_000);
});
