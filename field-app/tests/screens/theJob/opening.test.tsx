/**
 * T-18 Opening a job — FF-15 Job, FF-16 Safety — and FF-58 Hand it back,
 * mounted under the real navigation from a seeded store (`fixture.ts`).
 *
 * Proved red (law 7): with `safetyPassed` returning true whenever ANY row was
 * ticked (half-unlocked), *"two of four ticked is still locked"* failed —
 * *Open tasks* was enabled at 2 of 4.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import * as workOrderQ from '../../../src/db/queries/workOrder';
import * as outboxQ from '../../../src/db/queries/outbox';
import { scoped } from '../../../src/db/scoped';
import { tickSafety } from '../../../src/screens/theJob/actions';
import { DANA, local, seedWO4822, WO } from './fixture';
import { mountJob, onTop } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./window').currentWindow(),
}));

describe('FF-15 Job — the whole template, each section with a count and a state (R5)', () => {
  test('TC-1: every section counted from the rows, with its state', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-15', { params: { workOrderId: WO } });
    const top = within(onTop('FF-15'));
    expect(top.getByText('WO-4822')).toBeTruthy();
    expect(top.getByText('Meter exchange · residential')).toBeTruthy();
    expect(top.getByTestId('count-safety')).toHaveTextContent('0 of 4Not started');
    expect(top.getByTestId('count-tasks')).toHaveTextContent('3 of 8In progress');
    // tasks 4 and 8 short of their photographs; the master and sub-meter B readings likewise
    expect(top.getAllByText('2 need a photo')).toHaveLength(2);
    expect(top.getByTestId('count-materials')).toHaveTextContent('1 of 2In progress');
    expect(top.getByText('1 not on the van')).toBeTruthy();
    expect(top.getByTestId('count-checklist')).toHaveTextContent('3 of 5In progress');
    expect(top.getByTestId('count-readings')).toHaveTextContent('1 of 3In progress');
    expect(top.getByText('Template v3')).toBeTruthy();
    expect(top.getByText('Sarah Miller')).toBeTruthy();
    expect(top.getByText('1400 Elm Street · Unit A')).toBeTruthy();
    expect(top.getByText('W-4471 · Neptune T-10 · 5/8"')).toBeTruthy();
    expect(top.getByText('Badge 88-2041 · 2 sub-meters · last 48,180 gal')).toBeTruthy();
    // TC-4: the step added in the field is counted and shown as a variance (R7)
    expect(top.getByTestId('job-variance')).toHaveTextContent('2 added in the field');
    // R16: a balance is read online, never shown from the handset
    expect(top.getByTestId('door-FF-61')).toHaveTextContent(/^Money to check\W?$/u);
    expect(top.queryByText(/\$/)).toBeNull();
  });

  test('R9: travel and on-site are separate clocks; crew is per person (R8)', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-15');
    const time = within(screen.getByTestId('job-time'));
    expect(time.getByText('14m')).toBeTruthy();
    expect(time.getByText('08:00 → 08:14')).toBeTruthy();
    expect(time.getByText('Running since 08:46')).toBeTruthy();
    expect(within(onTop('FF-15')).getByText('2 technicians')).toBeTruthy();
    // Dana 08:46 → 10:58 (132m) + Marco 08:46 → 09:58 (72m)
    expect(within(onTop('FF-15')).getByText('3h 24m')).toBeTruthy();
    expect(within(onTop('FF-15')).getByTestId('door-FF-50')).toHaveTextContent('12 to send');
  });

  test('TC-2: Continue goes to Safety while it is locked (R3), then to the step the work is at', async () => {
    const f = seedWO4822();
    const app = await mountJob(f.services, 'FF-15');
    const cont = within(onTop('FF-15')).getByTestId('job-continue');
    expect(cont).toHaveTextContent('Continue — safety first');
    fireEvent.press(cont);
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-16');

    for (const id of ['safety-1', 'safety-2', 'safety-3', 'safety-4']) tickSafety(f.port(), WO, id);
    const again = await mountJob(f.services, 'FF-15');
    const next = within(onTop('FF-15')).getByTestId('job-continue');
    expect(next).toHaveTextContent('Continue — step 4 of 8');
    fireEvent.press(next);
    expect(again.ref.getCurrentRoute()?.name).toBe('FF-17');
  });

  test('a tablet shows the steps beside the job (FF-15 T)', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-15', { tablet: true });
    expect(within(onTop('FF-15')).getByTestId('job-tasks-pane')).toBeTruthy();
  });

  test('with no store and no job, the frame and every door are still there, and it says so', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-15', { openJob: null });
    expect(within(onTop('FF-15')).getByTestId('job-none')).toHaveTextContent('No job open.');
    expect(within(onTop('FF-15')).getByTestId('count-tasks')).toHaveTextContent('0 of 0');
  });
});

describe('FF-16 Safety — all four or none (R3)', () => {
  test('two of four ticked is still locked; four of four opens the tasks', async () => {
    const f = seedWO4822();
    const app = await mountJob(f.services, 'FF-16');
    const top = () => within(onTop('FF-16'));
    expect(top().getByTestId('safety-locked')).toHaveTextContent(/Tasks stay locked\. All 4 required\.$/);
    expect(top().getByTestId('door-FF-17')).toBeDisabled();
    expect(top().getByTestId('door-FF-17')).toHaveTextContent('Tasks locked');
    expect(top().getByTestId('safety-locked-tasks')).toHaveTextContent(/1 · Photograph meter in place.*\+ 5 more/);

    fireEvent.press(top().getByTestId('safety-safety-1'));
    fireEvent.press(top().getByTestId('safety-safety-2'));
    expect(top().getByTestId('safety-count')).toHaveTextContent('2 of 4');
    expect(top().getByTestId('door-FF-17')).toBeDisabled();
    // a tick is an act: the row is done and cannot be pressed again
    expect(top().getByTestId('safety-safety-1')).toBeDisabled();

    fireEvent.press(top().getByTestId('safety-safety-3'));
    fireEvent.press(top().getByTestId('safety-safety-4'));
    expect(top().queryByTestId('safety-locked')).toBeNull();
    expect(top().getByTestId('door-FF-17')).toHaveTextContent('Open tasks');
    fireEvent.press(top().getByTestId('door-FF-17'));
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-17');

    const items = outboxQ.listMine(scoped(f.db, DANA), { limit: 100 }).filter((r) => r.kind === 'safety_tick');
    expect(items.map((r) => JSON.parse(r.payload).safety_id).sort()).toEqual(['safety-1', 'safety-2', 'safety-3', 'safety-4']);
  });
});

describe('FF-58 Hand it back (R106, R107)', () => {
  test('TC-1: a reason is required; handed back, the job leaves the day with the reason', async () => {
    const f = seedWO4822();
    const app = await mountJob(f.services, 'FF-58');
    const top = () => within(onTop('FF-58'));
    expect(top().getByTestId('hand-back-order')).toHaveTextContent(/WO-4822 · Meter exchange · residential/);
    const go = top().getByTestId('door-FF-10');
    expect(go).toBeDisabled();
    fireEvent.press(top().getByTestId('hand-back-parts'));
    expect(top().getByTestId('hand-back-parts')).toBeChecked();
    fireEvent.press(top().getByTestId('hand-back-say-more'));
    fireEvent.changeText(top().getByLabelText('A bit more'), 'Need a 3/4 inch meter');
    fireEvent.press(top().getByTestId('door-FF-10'));
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-10');
    const item = outboxQ.listMine(scoped(f.db, DANA), { limit: 100 }).find((r) => r.kind === 'hand_back');
    expect(JSON.parse(item?.payload ?? '{}')).toEqual({ reason: 'parts', note: 'Need a 3/4 inch meter' });
  });

  test('TC-4: Keep it changes nothing', async () => {
    const f = seedWO4822();
    const app = await mountJob(f.services, 'FF-58');
    fireEvent.press(within(onTop('FF-58')).getByTestId('hand-back-keep'));
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-15');
    expect(outboxQ.listMine(scoped(f.db, DANA), { limit: 100 }).some((r) => r.kind === 'hand_back')).toBe(false);
  });

  test('TC-2: an emergency is not offered; the screen says to ring dispatch', async () => {
    const f = seedWO4822();
    const s = scoped(f.db, DANA);
    const wo = workOrderQ.getMine(s, WO);
    if (!wo) throw new Error('no order');
    workOrderQ.upsertFromServer(
      s,
      {
        id: WO, number: wo.number, type: wo.type, state: wo.state, dispatchState: wo.dispatch_state, priorityCode: 'P1',
        priorityRank: 1, premiseId: wo.premise_id, windowStart: wo.window_start, windowEnd: wo.window_end, dueAt: null,
        estMinutes: null, accessNotes: null, hazards: null, gateCode: null, extra: { emergency: true }, serverUpdatedAt: local(7, 0).toISOString(),
      },
      local(7, 0).toISOString(),
    );
    await mountJob(f.services, 'FF-58');
    const top = within(onTop('FF-58'));
    expect(top.getByTestId('hand-back-emergency')).toHaveTextContent('Emergency. Ring dispatch to hand back.');
    expect(top.queryByTestId('hand-back-parts')).toBeNull();
    expect(top.getByTestId('door-FF-10')).toBeDisabled();
  });
});

afterEach(async () => {
  await act(async () => undefined);
});

describe('DEF-FLD-10353 — FF-15 opened from Today / a map stop, with NO job already open', () => {
  test('`{ jobId }` (the name FF-10 and FF-14 pass) opens that job, not "No job open"', async () => {
    const f = seedWO4822();
    await mountJob(f.services, 'FF-15', { params: { jobId: WO }, openJob: null });
    expect(within(onTop('FF-15')).getByText('WO-4822')).toBeTruthy();
  });
});
