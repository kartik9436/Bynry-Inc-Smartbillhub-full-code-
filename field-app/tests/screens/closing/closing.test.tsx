/**
 * T-21 Closing — FF-32 Debrief, FF-33 Signature, FF-34 Close, FF-35
 * Completed, FF-36 Reopen — under the real navigator, from the fixture
 * handset (US-FLD-014, US-FLD-022, US-FLD-024; R4, R8, R17, R21, R22, R30,
 * R110, R111).
 *
 * Red proof (law 7): with FF-34's close held back for a missing required
 * photo, "a required photo missing warns, never blocks" fails on
 * `not.toBeDisabled` (PO 2026-10-21: it warns); with
 * `acceptedAt` returning null, "FF-36 after acceptance" fails on the greyed
 * Reopen.
 */
import { fireEvent, waitFor, within } from '@testing-library/react-native';
import { Pressable } from 'react-native';

import * as activityQ from '../../../src/db/queries/activity';
import * as closedQ from '../../../src/db/queries/workOrderClosed';
import * as workOrderQ from '../../../src/db/queries/workOrder';
import { scoped } from '../../../src/db/scoped';
import * as technicianQ from '../../../src/db/queries/technician';
import { closeJob, defaultCloseTimes } from '../../../src/screens/closing/CloseScreen';
import { capture } from '../../../src/sync/outbox';
import type { SignaturePadProps, SignaturePort } from '../../../src/screens/closing/signature';
import { captured, current, DANA, local, makeWave, MARCO, NOW, openScreen, waveOf } from '../onSite/fixture';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

function FakePad(props: SignaturePadProps) {
  return <Pressable accessibilityRole="button" accessibilityLabel={props.label} testID="fake-pad" onPress={() => props.onInk(true)} style={{ minHeight: 56 }} />;
}
const fakeSignature: SignaturePort = {
  Pad: FakePad,
  exportImage: () => Promise.resolve({ localPath: '/sig/1.png', sha256: 'sig', bytes: 900 }),
};

const setExtra = (w: ReturnType<typeof makeWave>, id: string, extra: object) =>
  scoped(w.db, DANA).run('UPDATE work_order SET extra = :x WHERE technician_id = :technician_id AND id = :id', { id, x: JSON.stringify(extra) });

describe('FF-32 Debrief', () => {
  test('my labour and travel, the parts used, and the dictated words carried to the signature', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-32', { workOrderId: 'wo-4822' });
    const page = within(app.onTop());
    expect(page.getByTestId('my-labour')).toHaveTextContent('1h 12m');
    expect(page.getByText('08:46 – 09:58')).toBeTruthy();
    expect(page.getByLabelText('Travel, 14m')).toBeTruthy();
    expect(page.getByLabelText('Water meter 5/8", 1')).toBeTruthy();
    expect(page.getByLabelText('Wire seal, 1')).toBeTruthy();
    fireEvent.changeText(page.getByLabelText('Problem found'), 'Register had stopped.');
    fireEvent.press(page.getByTestId('dictate'));
    await waitFor(() => expect(within(app.onTop()).getByLabelText('What I did')).toHaveProp('value', 'no leaks.'));
    fireEvent.press(within(app.onTop()).getByTestId('door-FF-33'));
    expect(current(app.ref)).toEqual({
      name: 'FF-33',
      params: { workOrderId: 'wo-4822', debrief: { problem: 'Register had stopped.', done: 'no leaks.' } },
    });
  });

  test('Change what was used opens FF-24 for the job', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-32', { workOrderId: 'wo-4822' });
    fireEvent.press(within(app.onTop()).getByTestId('door-FF-24'));
    expect(current(app.ref)).toEqual({ name: 'FF-24', params: { workOrderId: 'wo-4822' } });
  });
});

describe('FF-33 Signature', () => {
  test('TC-1: Sarah Miller prints her name and signs — captured by D. Ortiz, with the image declared', async () => {
    const w = makeWave({ signature: fakeSignature });
    const app = await openScreen(w, 'FF-33', { workOrderId: 'wo-4822' });
    const page = within(app.onTop());
    expect(page.getByLabelText('Printed name')).toHaveProp('value', 'Sarah Miller');
    expect(page.getByTestId('captured-by')).toHaveTextContent('Captured by D. Ortiz · 20 Oct 10:00');
    expect(page.getByTestId('accept-signature')).toBeDisabled();
    fireEvent.press(page.getByTestId('fake-pad'));
    fireEvent.press(within(app.onTop()).getByTestId('accept-signature'));
    await waitFor(() => expect(current(app.ref).name).toBe('FF-34'));
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`FF-33 → ${current(app.ref).name}`).toBe('FF-33 → FF-34');
    expect(current(app.ref).params).toEqual({ workOrderId: 'wo-4822', signature: { kind: 'signed', name: 'Sarah Miller', at: NOW.toISOString() } });
    const acts = captured(w.db);
    expect(acts.map((a) => a.kind)).toEqual(['signature', 'photo']);
    expect(acts[0]?.body).toMatchObject({ refused: false, printed_name: 'Sarah Miller' });
    expect(acts[0]?.captured_by).toBe(DANA);
    // DEF-WRK-10625: the mark is NAMED on the signature item by the phone's own
    // photo id, with its hash, so the server can link it before the bytes land.
    expect(acts[0]?.body).toMatchObject({ image_photo_id: acts[1]?.body.photo_id, image_sha256: 'sig' });
    expect(acts[1]?.body).toEqual({ photo_id: acts[0]?.body.image_photo_id, sha256: 'sig' });
  });

  test('TC-4 negative: signed with no printed name is not saved', async () => {
    const w = makeWave({ signature: fakeSignature });
    const app = await openScreen(w, 'FF-33', { workOrderId: 'wo-4822' });
    fireEvent.changeText(within(app.onTop()).getByLabelText('Printed name'), '  ');
    fireEvent.press(within(app.onTop()).getByTestId('fake-pad'));
    expect(within(app.onTop()).getByTestId('accept-signature')).toBeDisabled();
    expect(captured(w.db)).toEqual([]);
  });

  test('TC-2 (E2E-24): a refusal records the reason and the door-hanger photo', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-33', { workOrderId: 'wo-4822' });
    fireEvent.press(within(app.onTop()).getByTestId('sig-tab-refused'));
    fireEvent.press(within(app.onTop()).getByTestId('refusal-reason-declined'));
    // TC-3 negative: no photo, no refusal.
    expect(within(app.onTop()).getByTestId('record-refusal')).toBeDisabled();
    fireEvent.press(within(app.onTop()).getByTestId('hanger-photo'));
    await waitFor(() => expect(within(app.onTop()).getByTestId('hanger-taken')).toBeTruthy());
    fireEvent.press(within(app.onTop()).getByTestId('record-refusal'));
    expect(current(app.ref)).toEqual({ name: 'FF-34', params: { workOrderId: 'wo-4822', signature: { kind: 'refused', reason: 'Customer declined', at: NOW.toISOString() } } });
    const acts = captured(w.db);
    expect(acts[0]?.body).toMatchObject({ refused: true, decline_reason: 'Customer declined' });
    expect(acts[0]?.body).not.toHaveProperty('printed_name');
    expect(acts.filter((a) => a.kind === 'photo')).toHaveLength(1);
    // DEF-WRK-10625: the server refused every refusal — the item named no
    // photograph ("A refusal needs a door-hanger photo."). It names it now.
    const photo = acts.find((a) => a.kind === 'photo')!;
    expect(acts[0]?.body).toMatchObject({ door_hanger_photo_id: photo.body.photo_id, door_hanger_sha256: 'aa' });
    expect(typeof photo.body.photo_id).toBe('string');
  });

  test('DEF-FLD-10628: Captured by is a NAME — the signed-in profile when the roster has no name — never an id', async () => {
    const w = makeWave({ signature: fakeSignature });
    technicianQ.upsert(w.db, { id: DANA, name: '', role: 'Water II', employment: 'employee' }, NOW.toISOString());
    const app = await openScreen(w, 'FF-33', { workOrderId: 'wo-4822' });
    const stamp = within(app.onTop()).getByTestId('captured-by');
    expect(stamp).toHaveTextContent('Captured by D. Ortiz · 20 Oct 10:00');
    expect(stamp).not.toHaveTextContent(DANA);
  });

  test('with no signing pad on the handset it says so, and a refusal is still possible', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-33', { workOrderId: 'wo-4822' });
    expect(within(app.onTop()).getByTestId('no-pad')).toHaveTextContent('Signing pad not available.');
    expect(within(app.onTop()).getByTestId('accept-signature')).toBeDisabled();
  });
});

describe('FF-34 Close', () => {
  test('the four outcomes (R4); a required photo missing warns, never blocks, says how many, and travels with the close', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-34', { workOrderId: 'wo-4822' });
    const page = within(app.onTop());
    expect(page.getByTestId('photo-missing')).toHaveTextContent(/1 required photo missing$/);
    expect(page.getAllByRole('radio').map((r) => r.props.accessibilityLabel)).toEqual(['Passed', 'Partly done', 'Failed', 'Waiting on someone']);
    fireEvent.press(page.getByTestId('outcome-partially_done'));
    expect(within(app.onTop()).getByTestId('outcome-partially_done')).toHaveProp('accessibilityState', { checked: true, selected: true });
    expect(within(app.onTop()).getByTestId('close-job')).not.toBeDisabled();
    expect(page.getByLabelText('Labor, 1h 12m')).toBeTruthy();
    expect(page.getByLabelText('Parts used, 2 · Water meter 5/8"')).toBeTruthy();
    expect(page.getByTestId('readings-value')).toHaveTextContent('1');
    fireEvent.press(within(app.onTop()).getByTestId('close-job'));
    const close = captured(w.db).find((a) => a.kind === 'close')!;
    expect(close.body).toMatchObject({ outcome: 'partially_done', field_data: { required_photos_missing: 1 } });
  });

  test('a close is captured once with its outcome, the debrief and the unverified money; the job is closed on the phone', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-34', {
      workOrderId: 'wo-4824',
      debrief: { problem: 'Arrears', done: 'Valve closed' },
      moneyUnverified: { balance: '241.38', as_at: local(17, 9, 12) },
    });
    fireEvent.press(within(app.onTop()).getByTestId('outcome-passed'));
    fireEvent.press(within(app.onTop()).getByTestId('close-job'));
    const close = captured(w.db).find((a) => a.kind === 'close')!;
    // DEF-FLD-10626: nothing tapped and no work saved on wo-4824 — still a
    // pair, five minutes apart, never `arrived_at: null` (refused "Enter both times.").
    expect(close.body).toEqual({
      outcome: 'passed',
      arrived_at: local(20, 9, 55),
      finished_at: NOW.toISOString(),
      field_data: { problem_found: 'Arrears', what_i_did: 'Valve closed', money_unverified: { balance: '241.38', as_at: local(17, 9, 12) } },
    });
    const order = workOrderQ.getMine(scoped(w.db, DANA), 'wo-4824');
    expect(order).toMatchObject({ outcome: 'passed', closed_at: NOW.toISOString() });
    const statuses = activityQ.listForOrder(scoped(w.db, DANA), 'wo-4824').map((a) => a.status);
    expect(statuses).toEqual(['proceeded_unverified', 'closed']);
    expect(current(app.ref)).toEqual({ name: 'FF-15', params: { workOrderId: 'wo-4824' } });
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`FF-34 → ${current(app.ref).name}`).toBe('FF-34 → FF-15');
  });

  test('DEF-FLD-10626: Arrived never tapped — Arrived is the first work saved on the job, Finished is now, both editable and both sent', async () => {
    const w = makeWave();
    // The first work saved on the job: a note at 09:12:30.
    capture(w.db, { technicianId: DANA, capturedBy: DANA }, { kind: 'remark', workOrderId: 'wo-4824', payload: { text: 'on site' } }, {
      newId: w.data.newId,
      clock: { now: () => new Date(2026, 9, 20, 9, 12, 30) },
    });
    const app = await openScreen(w, 'FF-34', { workOrderId: 'wo-4824' });
    const page = within(app.onTop());
    expect(page.getByTestId('arrived-value')).toHaveTextContent('09:12');
    expect(page.getByTestId('finished-value')).toHaveTextContent('10:00');
    // Finished never passes now; Arrived moves in five-minute steps.
    expect(page.getByTestId('finished-increase')).toBeDisabled();
    fireEvent.press(page.getByTestId('arrived-decrease'));
    expect(within(app.onTop()).getByTestId('arrived-value')).toHaveTextContent('09:07');
    fireEvent.press(within(app.onTop()).getByTestId('outcome-passed'));
    fireEvent.press(within(app.onTop()).getByTestId('close-job'));
    const close = captured(w.db).find((a) => a.kind === 'close')!;
    expect(close.body).toMatchObject({ arrived_at: local(20, 9, 7), finished_at: NOW.toISOString() });
  });

  test('DEF-FLD-10626: Arrived tapped (travel ended 08:14) is the default', () => {
    const w = makeWave();
    expect(defaultCloseTimes(waveOf(w), 'wo-4822')).toEqual({ arrivedAt: local(20, 8, 14), finishedAt: NOW.toISOString() });
  });

  test('US-FLD-075 TC-2: a reconnect with the fee unpaid closes as reconnected with the fee outstanding', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-34', { workOrderId: 'wo-4830', feeOutstanding: { amount: '45.00' } });
    fireEvent.press(within(app.onTop()).getByTestId('outcome-passed'));
    fireEvent.press(within(app.onTop()).getByTestId('close-job'));
    expect(captured(w.db).find((a) => a.kind === 'close')?.body.field_data).toEqual({ reconnect_fee_outstanding: { amount: '45.00' } });
  });

  test('US-FLD-020 TC-2 negative: only the lead closes (R8)', async () => {
    const w = makeWave();
    setExtra(w, 'wo-4824', { lead_technician_id: MARCO });
    const app = await openScreen(w, 'FF-34', { workOrderId: 'wo-4824' });
    fireEvent.press(within(app.onTop()).getByTestId('outcome-passed'));
    expect(within(app.onTop()).getByTestId('lead-closes')).toHaveTextContent('The lead closes the job.');
    expect(within(app.onTop()).getByTestId('close-job')).toBeDisabled();
  });

  test('the signature card opens FF-33, signed or refused, carrying the draft', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-34', { workOrderId: 'wo-4824', debrief: { problem: 'a', done: 'b' } });
    fireEvent.press(within(app.onTop()).getByTestId('record-refused'));
    expect(current(app.ref)).toEqual({ name: 'FF-33', params: { workOrderId: 'wo-4824', debrief: { problem: 'a', done: 'b' }, tab: 'refused' } });
  });
});

describe('FF-35 Completed and FF-36 Reopen', () => {
  test('TC-1: today, Waiting for the office, and Reopen is live; This week adds the accepted one with Reopen greyed (TC-2)', async () => {
    const w = makeWave();
    closeJob(waveOf(w), { workOrderId: 'wo-4822' }, 'passed', defaultCloseTimes(waveOf(w), 'wo-4822'));
    const s = scoped(w.db, DANA);
    closedQ.recordClose(s, 'wo-4824', 'passed', local(19, 15));
    setExtra(w, 'wo-4824', { accepted_at: local(19, 16) });
    closedQ.recordClose(s, 'wo-4826', 'waiting_on_someone_else', local(20, 8, 41));

    const app = await openScreen(w, 'FF-35');
    const today = within(app.onTop());
    const card = within(today.getByTestId('completed-WO-4822'));
    expect(card.getByTestId('outcome-strip')).toHaveTextContent('Passed');
    expect(card.getByText('10:00')).toBeTruthy();
    expect(card.getByText('Sarah Miller')).toBeTruthy();
    // FB-030: no speed figures in history — the labour minutes left the card.
    expect(card.getByText('WO-4822 · Meter exchange')).toBeTruthy();
    expect(card.getByText('Waiting for the office')).toBeTruthy();
    expect(card.getByTestId('reopen-WO-4822')).not.toBeDisabled();
    expect(today.getByTestId('completed-WO-4826')).toBeTruthy();
    expect(today.queryByTestId('completed-WO-4824')).toBeNull();

    fireEvent.press(today.getByTestId('range-week'));
    const week = within(app.onTop());
    const accepted = within(week.getByTestId('completed-WO-4824'));
    expect(accepted.getByTestId('outcome-strip')).toHaveTextContent('Passed · Accepted');
    expect(accepted.getByText('Mon')).toBeTruthy();
    expect(accepted.getByText('Accepted by the office')).toBeTruthy();
    expect(accepted.getByTestId('reopen-WO-4824')).toBeDisabled();

    fireEvent.press(week.getByTestId('raise-WO-4824'));
    expect(current(app.ref)).toEqual({ name: 'FF-37', params: { carriedFrom: 'wo-4824' } });
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`FF-35 → ${current(app.ref).name}`).toBe('FF-35 → FF-37');
  });

  test('FF-36: why, when it was closed; with no server to reopen it, it says it was not sent and changes nothing', async () => {
    const w = makeWave();
    closedQ.recordClose(scoped(w.db, DANA), 'wo-4822', 'passed', local(20, 9, 58));
    const app = await openScreen(w, 'FF-36', { workOrderId: 'wo-4822' });
    const page = within(app.onTop());
    expect(page.getByTestId('reopen-title')).toHaveTextContent('Reopen WO-4822?');
    expect(page.getByText('The close is undone. The office is told.')).toBeTruthy();
    expect(page.getByTestId('closed-stamp')).toHaveTextContent('Closed 09:58 · not yet accepted');
    expect(page.getByTestId('reopen')).toBeDisabled();
    fireEvent.press(page.getByTestId('reopen-reason-missedStep'));
    fireEvent.press(within(app.onTop()).getByTestId('reopen'));
    expect(await within(app.onTop()).findByTestId('reopen-failed')).toHaveTextContent('Reopen not sent. Call the office.');
    expect(captured(w.db)).toEqual([]);
    expect(workOrderQ.getMine(scoped(w.db, DANA), 'wo-4822')?.closed_at).not.toBeNull();
  });

  test('FF-36 after acceptance: the office owns it and Reopen is greyed (R22)', async () => {
    const w = makeWave();
    closedQ.recordClose(scoped(w.db, DANA), 'wo-4824', 'passed', local(19, 15));
    setExtra(w, 'wo-4824', { accepted_at: local(19, 16) });
    const app = await openScreen(w, 'FF-36', { workOrderId: 'wo-4824' });
    fireEvent.press(within(app.onTop()).getByTestId('reopen-reason-wrongOutcome'));
    expect(within(app.onTop()).getByTestId('office-owns')).toBeTruthy();
    expect(within(app.onTop()).getByTestId('reopen')).toBeDisabled();
    fireEvent.press(within(app.onTop()).getByTestId('door-FF-35'));
    expect(current(app.ref).name).toBe('FF-35');
  });

});
