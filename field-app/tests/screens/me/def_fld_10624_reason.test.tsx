/**
 * DEF-FLD-10624 (A, C) — FF-50 says why nothing went, in one short fact, and
 * *Sync now* is a MANUAL run. The PO watched *"16 waiting"* for fifteen
 * minutes with no word of why (decision log 2026-10-27, *"start A to F"*).
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import * as outboxQ from '../../../src/db/queries/outbox';
import { deviceWide } from '../../../src/db/scoped';
import { capture } from '../../../src/sync/outbox';
import type { SyncRunOutcome } from '../../../src/sync/syncReason';
import { DANA, makeFixture, MARCO, NOW, openScreen } from './support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

function onTop(id: string) {
  const all = screen.getAllByTestId(`screen-${id}`);
  return within(all.at(-1) as Parameters<typeof within>[0]);
}

function waitingWith(f: ReturnType<typeof makeFixture>, lastError: string | null) {
  const key = capture(f.db, { technicianId: DANA, capturedBy: DANA }, { kind: 'task_tick', workOrderId: 'wo-1', payload: {} }, { newId: f.ids, clock: { now: () => NOW } }).key;
  if (lastError) outboxQ.retryLater(deviceWide(f.db, 'receipt'), key, null, lastError, false);
  return key;
}

test('the waiting items’ own saved failure is the reason when the screen opens', async () => {
  const f = makeFixture();
  waitingWith(f, 'waiting_for_sign_in');
  const app = await openScreen('FF-50', f);
  expect(onTop('FF-50').getByTestId('ff50-reason')).toHaveTextContent('Sign in again.');
  app.unmount();
});

test('a server failure on the items reads as the server’s problem', async () => {
  const f = makeFixture();
  waitingWith(f, 'HTTP 503');
  const app = await openScreen('FF-50', f);
  expect(onTop('FF-50').getByTestId('ff50-reason')).toHaveTextContent('The server had a problem. Trying again.');
  app.unmount();
});

test('nothing waiting, nothing said', async () => {
  const f = makeFixture();
  const app = await openScreen('FF-50', f);
  expect(onTop('FF-50').queryByTestId('ff50-reason')).toBeNull();
  app.unmount();
});

test('Sync now is a MANUAL run, and its reason is shown', async () => {
  const syncNow = jest.fn(async (): Promise<SyncRunOutcome> => ({ reason: 'timedOut', sent: 0 }));
  const f = makeFixture({ sync: { syncNow } });
  waitingWith(f, null);
  const app = await openScreen('FF-50', f);
  await act(async () => {
    fireEvent.press(onTop('FF-50').getByTestId('ff50-sync-now'));
  });
  expect(syncNow).toHaveBeenCalledWith({ manual: true });
  expect(onTop('FF-50').getByTestId('ff50-reason')).toHaveTextContent('Run timed out. Try again.');
  app.unmount();
});

test('a run that could not reach the server says so', async () => {
  const syncNow = jest.fn(async (): Promise<SyncRunOutcome> => ({ reason: 'noSignal', sent: 0 }));
  const f = makeFixture({ sync: { syncNow } });
  waitingWith(f, null);
  const app = await openScreen('FF-50', f);
  await act(async () => {
    fireEvent.press(onTop('FF-50').getByTestId('ff50-sync-now'));
  });
  expect(onTop('FF-50').getByTestId('ff50-reason')).toHaveTextContent('Could not reach the server.');
  app.unmount();
});

// ── DEF-FLD-10629 (FB-004): H, I and G's other-captor line ──────────────────

test('H: Sync now shows "Sending…" while it runs, then "Sent N."', async () => {
  let finish: (o: SyncRunOutcome) => void = () => undefined;
  const syncNow = jest.fn(() => new Promise<SyncRunOutcome>((r) => (finish = r)));
  const f = makeFixture({ sync: { syncNow } });
  const app = await openScreen('FF-50', f);
  await act(async () => {
    fireEvent.press(onTop('FF-50').getByTestId('ff50-sync-now'));
  });
  expect(onTop('FF-50').getByTestId('ff50-sending')).toHaveTextContent('Sending…');
  expect(onTop('FF-50').getByTestId('ff50-sync-now')).toHaveTextContent('Sending…');
  await act(async () => {
    finish({ reason: null, sent: 3 });
  });
  expect(onTop('FF-50').getByTestId('ff50-sent')).toHaveTextContent('Sent 3.');
  expect(onTop('FF-50').queryByTestId('ff50-sending')).toBeNull();
  app.unmount();
});

test('I: a photograph whose act has not gone waits for it — not counted as uploading', async () => {
  const f = makeFixture();
  const photo = { localPath: 'file:///p/1.jpg', sha256: 'a'.repeat(64), bytes: 1000, target: {} };
  capture(f.db, { technicianId: DANA, capturedBy: DANA }, { kind: 'task_tick', workOrderId: 'wo-1', payload: {}, photos: [photo] }, { newId: f.ids, clock: { now: () => NOW } });
  const app = await openScreen('FF-50', f);
  expect(onTop('FF-50').getByTestId('ff50-photos')).toHaveTextContent(/Waiting for its work/);
  expect(onTop('FF-50').queryByTestId('ff50-photo-meter')).toBeNull();
  app.unmount();
});

test('G: another captor’s work on this phone reads "Waiting for … to sign in."', async () => {
  const syncNow = jest.fn(async (): Promise<SyncRunOutcome> => ({ reason: null, sent: 0 }));
  const f = makeFixture({ sync: { syncNow } });
  const app = await openScreen('FF-50', f);
  app.handset.outbox.add(MARCO, 'item', 'm1');
  await act(async () => {
    fireEvent.press(onTop('FF-50').getByTestId('ff50-sync-now')); // re-reads whose work waits
  });
  expect(onTop('FF-50').getByTestId(`ff50-owner-${MARCO}`)).toHaveTextContent(/Waiting for .+ to sign in\./);
  app.unmount();
});
