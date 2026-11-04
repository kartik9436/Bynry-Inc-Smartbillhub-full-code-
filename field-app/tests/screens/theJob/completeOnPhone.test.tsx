/**
 * DEF-FLD-10578 (MQ-023): a job completed END TO END on the phone, only by
 * pressing what the screens draw — FF-15 → Safety → Tasks → Readings →
 * Debrief → Parts used → Debrief → Signature → Close — ending with the close
 * in the outbox. Before the fix this could not be done at all: Debrief opened
 * "Not on this phone" from Readings, so no job could ever reach Close.
 *
 * The app is mounted as `FieldRuntime` mounts it (`./phone`), over the
 * boards' WO-4822 (`./fixture`: four safety checks, eight steps — three done —
 * three readings, the planned meter not yet used). The job is opened by
 * address with its id, as Today's card opens it; nothing is pre-set.
 *
 * Red proof (law 7): with the source at 824517918 (before the fix), safety,
 * tasks and readings passed and the walk failed at Debrief —
 * `expect(top('FF-32').queryByTestId('not-on-phone')).toBeNull()`, the
 * reporter's own symptom.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, waitFor, within } from '@testing-library/react-native';
import { Pressable } from 'react-native';

import * as outboxQ from '../../../src/db/queries/outbox';
import * as workOrderQ from '../../../src/db/queries/workOrder';
import { scoped } from '../../../src/db/scoped';
import type { SignaturePadProps, SignaturePort } from '../../../src/screens/closing/signature';
import type { FieldData } from '../../../src/screens/onSite/fieldData';
import { FakeMoneyPort } from '../../../src/screens/onSite/money';
import { fakeDevicePorts } from '../../../src/screens/onSite/ports';
import { unwiredScanner } from '../../../src/screens/raise/scanner';
import { DANA, seedWO4822, WO } from './fixture';
import { mountPhone, onTop, open, press } from './phone';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./window').currentWindow(),
}));

function FakePad(props: SignaturePadProps) {
  return <Pressable accessibilityRole="button" accessibilityLabel={props.label} testID="fake-pad" onPress={() => props.onInk(true)} style={{ minHeight: 56 }} />;
}
const fakeSignature: SignaturePort = {
  Pad: FakePad,
  exportImage: () => Promise.resolve({ localPath: '/sig/1.png', sha256: 'sig', bytes: 900 }),
};

test('WO-4822 is completed on the phone: safety, tasks, readings, parts, debrief, signature, close — and the close is in the outbox', async () => {
  const f = seedWO4822();
  const data: FieldData = {
    db: f.db,
    technicianId: DANA,
    newId: f.services.newId,
    clock: f.clock,
    money: new FakeMoneyPort(),
    device: fakeDevicePorts({ photos: [], words: [], location: null }),
    scanner: unwiredScanner,
    signature: fakeSignature,
  };
  const ref = await mountPhone(f.services, data);
  await open(ref, 'FF-15', { workOrderId: WO });
  const top = (id: Parameters<typeof onTop>[0]) => within(onTop(id));

  // Safety (R3): Continue opens it while it is locked; tick all four.
  press('FF-15', 'job-continue');
  for (const id of ['safety-1', 'safety-2', 'safety-3', 'safety-4']) press('FF-16', `safety-${id}`);
  press('FF-16', 'door-FF-17');

  // Tasks: mark every remaining step done. A short EXPECTED count warns and
  // never blocks (R110); a REQUIRED photo blocks until taken (MQ-017, PO
  // 2026-10-24) — step 8 asks for two, so they are taken on the step first.
  const pressable = () => {
    const button = top('FF-17').queryByTestId('task-mark-done');
    return button !== null && button.props.accessibilityState?.disabled !== true;
  };
  for (let guard = 0; pressable() && guard < 20; guard++) press('FF-17', 'task-mark-done');
  expect(top('FF-17').getByTestId('tasks-count')).toHaveTextContent('7 of 8');
  expect(top('FF-17').getByTestId('task-photo-required')).toHaveTextContent(/Take 2 photos to finish this step\.$/);
  for (let n = 1; n <= 2; n++) {
    await act(async () => {
      press('FF-17', 'task-take-photo');
    });
    await waitFor(() => expect(top('FF-17').getByTestId('task-photo-count')).toHaveTextContent(new RegExp(`${n} so far$`)));
  }
  press('FF-17', 'task-mark-done');
  expect(top('FF-17').getByTestId('tasks-count')).toHaveTextContent('8 of 8');
  press('FF-17', 'door-FF-20');

  // Readings: the two not taken yet — each asks for a dial photo (required), so it is taken first (MQ-020).
  for (const [id, value] of [['r-master', '48500'], ['r-sub-b', '9100']] as const) {
    await act(async () => {
      press('FF-20', `reading-${id}-photo`);
    });
    await waitFor(() => expect(top('FF-20').queryByTestId(`reading-${id}-photo-required`)).toBeNull());
    fireEvent.changeText(top('FF-20').getByTestId(`reading-${id}-field`), value);
    press('FF-20', `reading-${id}-save`);
  }
  expect(top('FF-20').getByTestId('readings-count')).toHaveTextContent('3 of 3');

  // Debrief, from Readings — the door that said "Not on this phone".
  press('FF-20', 'door-FF-32');
  expect(top('FF-32').queryByTestId('not-on-phone')).toBeNull();

  // Parts: the new meter was used (Debrief's "Change what was used" → FF-24 → Done → Tasks).
  press('FF-32', 'door-FF-24');
  press('FF-24', 'part-mat-meter-qty-increase');
  press('FF-24', 'door-FF-17');
  press('FF-17', 'door-FF-20');
  press('FF-20', 'door-FF-32');

  // Debrief → Signature.
  fireEvent.changeText(top('FF-32').getByLabelText('Problem found'), 'Register had stopped.');
  fireEvent.changeText(top('FF-32').getByLabelText('What I did'), 'Fitted W-9044 and sealed.');
  press('FF-32', 'door-FF-33');
  expect(top('FF-33').queryByTestId('not-on-phone')).toBeNull();
  expect(top('FF-33').getByLabelText('Printed name')).toHaveProp('value', 'Sarah Miller');
  press('FF-33', 'fake-pad');
  await act(async () => {
    press('FF-33', 'accept-signature');
  });

  // Close.
  await waitFor(() => expect(top('FF-34').getByTestId('signature-done')).toBeTruthy());
  press('FF-34', 'outcome-passed');
  expect(top('FF-34').getByTestId('close-job')).not.toBeDisabled();
  press('FF-34', 'close-job');

  const rows = outboxQ
    .listMine(scoped(f.db, DANA), { limit: 500 })
    .map((r) => ({ kind: r.kind, wo: r.work_order_id, body: JSON.parse(r.payload) as Record<string, unknown> }));
  const kinds = new Set(rows.filter((r) => r.wo === WO).map((r) => r.kind));
  for (const kind of ['safety_tick', 'task_tick', 'reading', 'material', 'signature', 'close']) expect(kinds).toContain(kind);
  const close = rows.filter((r) => r.kind === 'close');
  expect(close).toHaveLength(1);
  expect(close[0]).toMatchObject({
    wo: WO,
    body: { outcome: 'passed', field_data: { problem_found: 'Register had stopped.', what_i_did: 'Fitted W-9044 and sealed.' } },
  });
  expect(workOrderQ.getMine(scoped(f.db, DANA), WO)).toMatchObject({ outcome: 'passed' });
  // A whole job walked end to end, now with three photographs taken on the way
  // (MQ-017/MQ-020): ~12s alone, so the shared 20s budget is too tight under -w 3.
}, 60000);
