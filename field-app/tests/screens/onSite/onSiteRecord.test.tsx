/**
 * T-20 record screens — FF-28 Documents, FF-29 Crew, FF-30 Notes, FF-31
 * Activity — under the real navigator, from the fixture handset
 * (US-FLD-020, US-FLD-022, US-FLD-030, US-FLD-031; R8, R9, R10, R35, R38, R95).
 */
import { fireEvent, waitFor, within } from '@testing-library/react-native';

import * as crewOrderQ from '../../../src/db/queries/crewTimeOrder';
import { scoped } from '../../../src/db/scoped';
import { crewLines, totalLabour } from '../../../src/screens/onSite/crew';
import { captured, current, DANA, makeWave, MARCO, NOW, openScreen, PATEL } from './fixture';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

describe('FF-28 Documents', () => {
  test('the job’s papers, the premise notes, the ones always on the phone, and the shelf totals', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-28', { workOrderId: 'wo-4822' });
    const page = within(app.onTop());
    expect(within(page.getByTestId('job-docs')).getByText('Water shut-off SOP')).toBeTruthy();
    expect(within(page.getByTestId('job-docs')).getByText('Neptune T-10 install guide')).toBeTruthy();
    expect(page.getByText('Dog in the yard. Pit lid is heavy.')).toBeTruthy();
    expect(within(page.getByTestId('always-docs')).getByText('Confined space procedure')).toBeTruthy();
    expect(page.getByTestId('shelf-totals')).toHaveTextContent('3 documents · 22 MB · updated 07:00');
  });

  test('a paper on the phone opens offline from its own copy; one not on the phone says so', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-28', { workOrderId: 'wo-4822' });
    fireEvent.press(within(app.onTop()).getByTestId('doc-d-sop'));
    await waitFor(() => expect(w.device.opened).toEqual(['/docs/sop.pdf']));
    fireEvent.press(within(app.onTop()).getByTestId('doc-d-confined'));
    expect(within(app.onTop()).getByTestId('open-note')).toHaveTextContent('Not on this phone');
    expect(w.device.opened).toHaveLength(1);
  });
});

describe('FF-29 Crew', () => {
  test('TC-1: 2h 24m labour on this job · 2 technicians · 1h 12m each, lead first', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-29', { workOrderId: 'wo-4822' });
    const page = within(app.onTop());
    expect(page.getByTestId('crew-total')).toHaveTextContent('2h 24m');
    expect(page.getByTestId('crew-count')).toHaveTextContent('2 technicians · 1h 12m each');
    const dana = within(page.getByTestId(`crew-${DANA}`));
    expect(dana.getByText('D. Ortiz')).toBeTruthy();
    expect(dana.getByText('Water II · Employee')).toBeTruthy(); // FB-023: the code in words
    expect(dana.getByText('Lead')).toBeTruthy();
    expect(dana.getByLabelText('Travel, 14m')).toBeTruthy();
    expect(dana.getByLabelText('Arrived, 08:14')).toBeTruthy();
    expect(dana.getByTestId(`labour-${DANA}`)).toHaveProp('accessibilityLabel', 'Labor, 1h 12m');
    const marco = within(page.getByTestId(`crew-${MARCO}`));
    expect(marco.getByLabelText('Travel, 0m · came with lead')).toBeTruthy();
    expect(marco.getByLabelText('Arrived, 08:46')).toBeTruthy();
    expect(page.getByText('The lead closes the job.')).toBeTruthy();
  });

  test('R8: labour is per person and the cost is the sum', () => {
    const w = makeWave();
    const lines = crewLines(crewOrderQ.listForOrder(scoped(w.db, DANA), 'wo-4822'), NOW);
    expect(lines.map((l) => [l.personId, l.labourMinutes])).toEqual([
      [DANA, 72],
      [MARCO, 72],
    ]);
    expect(totalLabour(lines)).toBe(144);
  });

  test('TC-3: correcting M. Chen’s time replaces his clocks and is stamped who and when (R9, R10)', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-29', { workOrderId: 'wo-4822' });
    fireEvent.press(within(app.onTop()).getByTestId(`correct-${MARCO}`));
    const sheet = within(app.getByTestId('correct-sheet'));
    for (let i = 0; i < 4; i += 1) fireEvent.press(sheet.getByTestId('correct-labour-increase'));
    fireEvent.press(sheet.getByTestId('correct-save'));
    const marco = crewLines(crewOrderQ.listForOrder(scoped(w.db, DANA), 'wo-4822'), NOW).find((l) => l.personId === MARCO);
    expect(marco?.labourMinutes).toBe(92);
    const act = captured(w.db).at(-1)!;
    expect(act.kind).toBe('crew_time');
    expect(act.body).toMatchObject({ act: 'correct', person_id: MARCO, labour_minutes: 92, travel_minutes: 0 });
    expect(act.captured_by).toBe(DANA);
    expect(act.captured_at).toBe(NOW.toISOString());
    expect(within(app.onTop()).getByTestId('crew-total')).toHaveTextContent('2h 44m');
  });

  test('TC-3 (US-FLD-031) and E2E-20: Add a technician picks from the roster; their clock is their own', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-29', { workOrderId: 'wo-4822' });
    fireEvent.press(within(app.onTop()).getByTestId('add-technician'));
    fireEvent.press(within(app.getByTestId('add-sheet')).getByTestId(`pick-${PATEL}`));
    expect(within(app.onTop()).getByTestId(`crew-${PATEL}`)).toBeTruthy();
    const act = captured(w.db).at(-1)!;
    expect(act.body).toMatchObject({ act: 'join', person_id: PATEL, kind: 'labour' });
    const rows = crewOrderQ.listForOrder(scoped(w.db, DANA), 'wo-4822').filter((r) => r.person_id === PATEL);
    expect(rows).toHaveLength(1);
    expect(rows[0]?.outbox_id).toBe(act.id);
  });

  test('× takes a technician off from now; their time so far stays theirs', async () => {
    const w = makeWave();
    w.clock.advance(0);
    const app = await openScreen(w, 'FF-29', { workOrderId: 'wo-4822' });
    fireEvent.press(within(app.onTop()).getByLabelText('Take M. Chen off'));
    expect(captured(w.db).at(-1)?.body).toMatchObject({ act: 'leave', person_id: MARCO });
  });

  test('Done returns to the job', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-29', { workOrderId: 'wo-4822' });
    fireEvent.press(within(app.onTop()).getByTestId('door-FF-15'));
    expect(current(app.ref)).toEqual({ name: 'FF-15', params: { workOrderId: 'wo-4822' } });
  });
});

describe('FF-30 Notes', () => {
  test('TC-2 (US-FLD-030): dispatch’s note and the on-site notes, each with its author', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-30', { workOrderId: 'wo-4822' });
    const page = within(app.onTop());
    const dispatch = within(page.getByTestId('remark-n-1'));
    expect(dispatch.getByText('Dispatch')).toBeTruthy();
    expect(dispatch.getByText('20 Oct 07:12')).toBeTruthy();
    expect(dispatch.getByText('J. Okafor')).toBeTruthy();
    expect(within(page.getByTestId('remark-n-2')).getByText('On site')).toBeTruthy();
  });

  test('TC-1/TC-2 (US-FLD-022): a dictated note is saved as text, stamped who and when, with its photo', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-30', { workOrderId: 'wo-4822' });
    fireEvent.press(within(app.onTop()).getByTestId('dictate'));
    await waitFor(() => expect(within(app.onTop()).getByLabelText('Write a note')).toHaveProp('value', 'no leaks.'));
    fireEvent.press(within(app.onTop()).getByTestId('note-camera'));
    await waitFor(() => expect(within(app.onTop()).getByTestId('note-photo')).toBeTruthy());
    fireEvent.press(within(app.onTop()).getByTestId('add-note'));
    const acts = captured(w.db);
    const remark = acts.find((a) => a.kind === 'remark')!;
    expect(remark.body).toEqual({ text: 'no leaks.', source: 'on_site' });
    expect(remark.captured_by).toBe(DANA);
    expect(acts.filter((a) => a.kind === 'photo')).toHaveLength(1);
    const added = within(app.onTop()).getByText('no leaks.');
    expect(added).toBeTruthy();
    expect(within(app.onTop()).getAllByText('D. Ortiz').length).toBeGreaterThanOrEqual(2);
    expect(within(app.onTop()).getByText('20 Oct 10:00')).toBeTruthy();
  });

  test('TC-3 negative: an empty note blocks nothing and captures nothing (R95)', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-30', { workOrderId: 'wo-4822' });
    expect(within(app.onTop()).getByTestId('add-note')).toBeDisabled();
    expect(captured(w.db)).toEqual([]);
  });
});

describe('FF-31 Activity', () => {
  test('TC-1: every change, newest first, stamped who and when; never an id (R10, R35)', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-31', { workOrderId: 'wo-4822' });
    const page = within(app.onTop());
    expect(page.getByTestId('event-0')).toHaveProp('accessibilityLabel', 'M. Chen joined the job, 08:47 · D. Ortiz');
    expect(page.getByTestId('event-1')).toHaveProp('accessibilityLabel', 'Work started, 08:46 · D. Ortiz');
    expect(page.getByTestId('event-2')).toHaveProp('accessibilityLabel', 'Arrived, 08:14 · D. Ortiz · 30.2651, -97.7494 · ±4m');
    expect(page.getByTestId('event-5')).toHaveProp('accessibilityLabel', 'Raised, 17 Oct 14:22 · J. Okafor');
    const text = JSON.stringify(app.toJSON());
    expect(text).not.toMatch(/wo-4822|tech-dana|tech-marco|"e-\d"/);
  });

  test('Notes opens FF-30 for the same job', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-31', { workOrderId: 'wo-4822' });
    fireEvent.press(within(app.onTop()).getByTestId('door-FF-30'));
    expect(current(app.ref)).toEqual({ name: 'FF-30', params: { workOrderId: 'wo-4822' } });
  });
});
