/**
 * FB-028 (DEF-FLD-10802) — PO ruling of 2026-10-31, W2 = B: *"the job appears
 * only once the server has it, so with no signal she waits"*.
 *   * Send on FF-37 starts the outbox run AT ONCE when the phone has signal,
 *     and only queues it when it has none — no provisional job either way.
 *   * The screen stays and says so, with *Send now* and *Open job*; *Open job*
 *     goes live once the server's answer has put the numbered job on Today.
 *   * The carried job's unit travels with the raise (`unit_id`).
 *   * The toast no longer says the number comes from the office.
 *
 * Red proof (law 7): run against the code before FB-028 these failed — Send
 * called nothing, went back to FF-35, sent no `unit_id`, and drew neither
 * button.
 */
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';

import * as outboxQ from '../../../src/db/queries/outbox';
import * as workOrderQ from '../../../src/db/queries/workOrder';
import { deviceWide, scoped } from '../../../src/db/scoped';
import { captured, current, DANA, makeWave, NOW, openScreen } from '../onSite/fixture';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

function withSend(online: boolean) {
  const w = makeWave();
  workOrderQ.setDetails(scoped(w.db, DANA), 'wo-4824', { unit_id: 'unit-22b' });
  const sendNow = jest.fn(async () => {
    // What a real run does when the server answers: the raise row settles
    // with the server's answer, and the change feed brings the job (here the
    // seeded WO-4826 stands in for the new order).
    const raise = captured(w.db).find((a) => a.kind === 'raise');
    if (raise) outboxQ.settle(deviceWide(w.db, 'receipt'), raise.id, 'accepted', NOW.toISOString(), { order_id: 'wo-4826', order_no: 'WO-4826' });
  });
  w.data.sendNow = sendNow;
  w.data.online = () => online;
  return { w, sendNow };
}

describe('FF-37 · a raise is sent at once when there is signal (W2 = B)', () => {
  test('online: Send captures the raise with its unit, sends it now, and Open job opens the numbered job', async () => {
    const { w, sendNow } = withSend(true);
    const app = await openScreen(w, 'FF-37', { carriedFrom: 'wo-4824', templateId: 'tpl-leak' });
    await act(async () => {
      fireEvent.press(within(app.onTop()).getByTestId('send-raise'));
    });
    expect(sendNow).toHaveBeenCalledTimes(1);
    const raise = captured(w.db).find((a) => a.kind === 'raise')!;
    expect(raise.body).toMatchObject({ carried_from: 'wo-4824', unit_id: 'unit-22b' });
    expect(screen.getByText('Raised. Sending now.')).toBeTruthy();
    const page = within(app.onTop());
    await waitFor(() => expect(page.getByTestId('raise-state')).toHaveTextContent('On Today as WO-4826.'));
    expect(page.queryByTestId('raise-send-now')).toBeNull();
    expect(page.getByTestId('send-raise')).toBeDisabled();
    fireEvent.press(page.getByTestId('raise-open-job'));
    expect(current(app.ref)).toEqual({ name: 'FF-15', params: { workOrderId: 'wo-4826' } });
  });

  test('offline: the raise only queues; Send now and Open job are shown, Open job waits', async () => {
    const { w, sendNow } = withSend(false);
    const app = await openScreen(w, 'FF-37', { carriedFrom: 'wo-4824', templateId: 'tpl-leak' });
    await act(async () => {
      fireEvent.press(within(app.onTop()).getByTestId('send-raise'));
    });
    expect(sendNow).not.toHaveBeenCalled();
    expect(captured(w.db).filter((a) => a.kind === 'raise')).toHaveLength(1);
    expect(screen.getByText('Raised. Sends with signal.')).toBeTruthy();
    const page = within(app.onTop());
    expect(page.getByTestId('raise-state')).toHaveTextContent('Waiting for signal.');
    expect(page.getByTestId('raise-open-job')).toBeDisabled();
    // W2 = B — no provisional job: nothing new is on the phone's day.
    expect(workOrderQ.getMine(scoped(w.db, DANA), 'wo-4826')?.number).toBe('WO-4826');
    await act(async () => {
      fireEvent.press(page.getByTestId('raise-send-now'));
    });
    expect(sendNow).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(within(app.onTop()).getByTestId('raise-open-job')).not.toBeDisabled());
  });

  test('the toast and the card never say the number comes from the office', async () => {
    const { w } = withSend(true);
    const app = await openScreen(w, 'FF-37', { carriedFrom: 'wo-4824', templateId: 'tpl-leak' });
    await act(async () => {
      fireEvent.press(within(app.onTop()).getByTestId('send-raise'));
    });
    expect(screen.queryByText(/from the office/)).toBeNull();
  });
});
