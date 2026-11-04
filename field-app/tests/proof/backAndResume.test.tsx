/**
 * DEF-FLD-10607 — the PO's worked case, on the whole app (decision log
 * 2026-10-26, *"A for back button, A Resume — start"*):
 *
 *   Start → tick both safety checks → back → Today; the card reads Resume;
 *   tapping it opens Tasks with the ticks kept and no second accept.
 *
 * and the two ends of the card's rule: everything done reads *Finish* and
 * opens Debrief (FF-32); a closed job has no button.
 *
 * Escape: the back arrow was a fixed door to the drawn destination (FF-16's
 * arrow opened the job overview, never Today), and the card always read
 * *Start* — no test walked Today → a job → back, and none looked at a card
 * after work had been captured on its job.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import * as outboxQ from '../../src/db/queries/outbox';
import * as woItemQ from '../../src/db/queries/woItem';
import * as workOrderQ from '../../src/db/queries/workOrder';
import { scoped } from '../../src/db/scoped';
import { tickTask } from '../../src/screens/theJob/actions';
import { buildHandset, card, mountHandset, openAt, PEOPLE, ProofServer, settle, signInAs, TENANT, upsert, type Handset } from './runtimeApp';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const DANA = PEOPLE['d.ortiz']!.technicianId;
const MINUTE = 60_000;
const ID = 'wo-7031';

async function dayWithOneJob() {
  const h: Handset = buildHandset({ network: 'wifi' });
  const server = new ProofServer();
  h.servers.set(TENANT, server);
  server.feed([upsert(card(ID, 'WO-0031', new Date(h.clock.now() + 30 * MINUTE), 40), h.iso())]);
  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  // Offline from here, so every item the screens capture stays countable in the outbox.
  h.network.set('none');
  const db = h.holder.current;
  if (!db) throw new Error('the store did not open at sign-in');
  const s = scoped(db, DANA);
  db.transaction(() => {
    woItemQ.upsert(s, { id: `${ID}-safe-1`, workOrderId: ID, kind: 'safety', position: 1, label: 'Isolate supply' }, h.iso());
    woItemQ.upsert(s, { id: `${ID}-safe-2`, workOrderId: ID, kind: 'safety', position: 2, label: 'Cones out' }, h.iso());
    woItemQ.upsert(s, { id: `${ID}-task-1`, workOrderId: ID, kind: 'task', position: 3, label: 'Swap the meter' }, h.iso());
  });
  return { h, m, db, s };
}

const accepts = (s: ReturnType<typeof scoped>) => outboxQ.listMine(s, { limit: 100 }).filter((r) => r.kind === 'job_accept').length;
const cardOf = () => within(screen.getByTestId(`job-${ID}`));

test('Today → Start → tick safety → back is Today (the same one); the card reads Resume and opens Tasks, ticks kept, one accept', async () => {
  const { m, s } = await dayWithOneJob();
  await openAt(m, 'FF-10');
  const today = await screen.findByTestId('screen-FF-10');
  expect(cardOf().getByTestId(`job-${ID}-start`)).toHaveTextContent('Start');

  await act(async () => {
    fireEvent.press(cardOf().getByTestId(`job-${ID}-start`));
  });
  expect(m.ref.getCurrentRoute()?.name).toBe('FF-16');
  const safety = screen.getAllByTestId('screen-FF-16').at(-1)!;
  for (const row of [`${ID}-safe-1`, `${ID}-safe-2`]) {
    await act(async () => {
      fireEvent.press(within(safety).getByTestId(`safety-${row}`));
    });
  }
  const arrow = within(safety).getByTestId('door-FF-15');
  expect(arrow.props.accessibilityLabel).toBe('Back to Today');
  await act(async () => {
    fireEvent.press(arrow);
  });

  // Back is Today — not the job overview — and Today was uncovered, not remounted.
  expect(m.ref.getCurrentRoute()?.name).toBe('FF-10');
  expect(screen.getByTestId('screen-FF-10')).toBe(today);
  expect(cardOf().queryByTestId(`job-${ID}-start`)).toBeNull();
  expect(cardOf().getByTestId(`job-${ID}-resume`)).toHaveTextContent('Resume');

  await act(async () => {
    fireEvent.press(cardOf().getByTestId(`job-${ID}-resume`));
  });
  expect(m.ref.getCurrentRoute()?.name).toBe('FF-17');
  expect(woItemQ.listForOrder(s, ID).filter((i) => i.kind === 'safety' && i.state === 'ticked')).toHaveLength(2);
  expect(accepts(s)).toBe(1);
});

test('every part done reads Finish and opens Debrief (FF-32); a closed job has no button', async () => {
  const { m, s, h } = await dayWithOneJob();
  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  await act(async () => {
    fireEvent.press(cardOf().getByTestId(`job-${ID}-start`));
  });
  const port = m.inside.current.job!;
  await act(async () => {
    for (const row of [`${ID}-safe-1`, `${ID}-safe-2`]) woItemQ.setState(s, row, 'ticked');
    tickTask(port, ID, `${ID}-task-1`);
    port.changed();
  });
  await openAt(m, 'FF-10');
  expect(cardOf().getByTestId(`job-${ID}-finish`)).toHaveTextContent('Finish');
  await act(async () => {
    fireEvent.press(cardOf().getByTestId(`job-${ID}-finish`));
  });
  expect(m.ref.getCurrentRoute()?.name).toBe('FF-32');
  expect(accepts(s)).toBe(1);

  await act(async () => {
    workOrderQ.markClosed(s, ID, h.iso());
    port.changed();
  });
  await openAt(m, 'FF-10');
  expect(workOrderQ.getMine(s, ID)?.closed_at).not.toBeNull();
  for (const act_ of ['start', 'resume', 'finish']) expect(cardOf().queryByTestId(`job-${ID}-${act_}`)).toBeNull();
});
