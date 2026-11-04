/**
 * DEF-FLD-10612 (beta MQ-027) — FF-50 reads each refusal for what the
 * technician can DO about it, and groups by job and reason.
 *
 *  - the job has gone from them (reassigned · cancelled · declined): no act;
 *  - the capture credential: *Sign in again* — the door to FF-53, then FF-05;
 *  - the server could not apply it just now: *Send again*, the whole group;
 *  - anything else: *Fix and send again*, per item, as before.
 *
 * Proved red before the fix: `readRefusal` did not exist, and every refused
 * item rendered its own *Fix and send again*.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import * as outboxQ from '../../../src/db/queries/outbox';
import { deviceWide, scoped } from '../../../src/db/scoped';
import { groupRefusals, keptForOfficeOf, readRefusal } from '../../../src/screens/me/refusalGroups';
import { capture } from '../../../src/sync/outbox';
import { coldOpen } from '../../navigation/coldOpen';
import { at, DANA, makeFixture, openScreen } from './support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

const j = (x: unknown) => JSON.stringify(x);

describe('readRefusal', () => {
  test.each([
    ['a 404 from a door (no longer theirs)', { status: 404, body: { message: 'not found' } }, 'field.ff50.refused.reassigned', 'none'],
    ['a 404 kept on a batch item', { message: 'not found', status: 404 }, 'field.ff50.refused.reassigned', 'none'],
    ['not your job', { detail: { message_key: 'work.mobile.not_your_job' } }, 'field.ff50.refused.reassigned', 'none'],
    ['cancelled while offline', { message_key: 'work.sync.job_cancelled' }, 'field.ff50.refused.cancelled', 'none'],
    ['declined', { status: 409, body: { message_key: 'work.mobile.job_already_declined' } }, 'field.ff50.refused.declined', 'none'],
    ['finished, feed silent', { status: 409, body: { message_key: 'work.mobile.job_finished' } }, 'work.mobile.job_finished', 'none'],
    ['the capture credential', { message_key: 'work.mobile.capture_token_expired' }, 'work.mobile.capture_token_expired', 'signIn'],
    ['not applied just now', { message_key: 'work.sync.item_not_applied' }, 'work.sync.item_not_applied', 'sendAgain'],
    ['anything else', { message_key: 'work.mobile.reads.out_of_range' }, 'field.reads.refused.out_of_range', 'fix'],
  ])('%s', (_what, refusal, key, action) => {
    expect(readRefusal(j(refusal))).toEqual({ reasonKey: key, action });
  });

  test('finished on a job the feed says is cancelled reads as cancelled', () => {
    expect(readRefusal(j({ body: { message_key: 'work.mobile.job_finished' } }), true).reasonKey).toBe('field.ff50.refused.cancelled');
  });

  test('groups by job and reason, keeping the order of first refusal', () => {
    const item = (id: string, wo: string, reasonKey: string) => ({
      id,
      workOrderId: wo,
      workOrderNumber: wo.toUpperCase(),
      reason: '',
      reasonKey,
      action: 'none' as const,
    });
    const groups = groupRefusals([item('a', 'wo-1', 'r1'), item('b', 'wo-2', 'r1'), item('c', 'wo-1', 'r1'), item('d', 'wo-1', 'r2')]);
    expect(groups.map((g) => g.items.map((i) => i.id))).toEqual([['a', 'c'], ['b'], ['d']]);
  });
});

/** Refused items on WO-4822, each with the same stored refusal. */
function seedRefused(fixture: ReturnType<typeof makeFixture>, n: number, refusal: unknown): string[] {
  const keys: string[] = [];
  for (let i = 0; i < n; i++) {
    const { key } = capture(
      fixture.db,
      { technicianId: DANA, capturedBy: DANA },
      { kind: 'reading', workOrderId: 'wo-4822', payload: { value: String(100 + i) } },
      { newId: fixture.ids, clock: { now: () => new Date(at('09:30')) } },
    );
    outboxQ.refuse(deviceWide(fixture.db, 'receipt'), key, refusal);
    keys.push(key);
  }
  return keys;
}

const waitingKeys = (fixture: ReturnType<typeof makeFixture>, keys: string[]) =>
  keys.filter((k) => outboxQ.getMine(scoped(fixture.db, DANA), k)?.state === 'pending');

test("'FF-50 → FF-53' Sign in again, on work refused for its capture credential, queues it again and opens Sign out", async () => {
  const fixture = makeFixture();
  const keys = seedRefused(fixture, 2, { reason: 'capture_token_expired', message_key: 'work.mobile.capture_token_expired' });
  const app = await openScreen('FF-50', fixture);
  await coldOpen(app.ref, 'FF-50');
  const card = within(screen.getAllByTestId('ff50-refused').at(-1)!);
  expect(card.queryAllByText('Fix and send again')).toHaveLength(0);
  await act(async () => {
    fireEvent.press(card.getByText('Sign in again'));
  });
  expect(`FF-50 → ${app.ref.getCurrentRoute()?.name}`).toBe('FF-50 → FF-53');
  expect(waitingKeys(fixture, keys)).toEqual(keys);
  app.unmount();
});

test('Send again, on work the server could not apply just now, sends the whole group again', async () => {
  const fixture = makeFixture();
  const keys = seedRefused(fixture, 3, { message_key: 'work.sync.item_not_applied' });
  const app = await openScreen('FF-50', fixture);
  const card = within(screen.getAllByTestId('ff50-refused').at(-1)!);
  expect(card.getByText(/3 items · Received but not applied\./)).toBeTruthy();
  await act(async () => {
    fireEvent.press(card.getByText('Send again'));
  });
  expect(waitingKeys(fixture, keys)).toEqual(keys);
  app.unmount();
});

test('an unknown reason keeps Fix and send again, per item, behind the group', async () => {
  const fixture = makeFixture();
  seedRefused(fixture, 2, { message: 'Reading 180 is impossible for this meter' });
  const app = await openScreen('FF-50', fixture);
  const card = within(screen.getAllByTestId('ff50-refused').at(-1)!);
  expect(card.queryAllByText('Fix and send again')).toHaveLength(0);
  await act(async () => {
    fireEvent.press(card.getByText('Show items'));
  });
  expect(card.getAllByText('Fix and send again')).toHaveLength(2);
  app.unmount();
});

// ── CR-194-BRC10 (PO 2026-10-26, "store on both") ─────────────────────────
// The row may say the office will review it ONLY when the server's answer
// said it kept a copy — `kept_for_office`, stored on the outbox row.
describe('kept for the office', () => {
  test('keptForOfficeOf reads the flag where each door puts it, and nothing else', () => {
    expect(keptForOfficeOf(j({ reason: 'not_your_job', message_key: 'work.mobile.not_your_job', kept_for_office: true }))).toBe(true);
    expect(keptForOfficeOf(j({ reason: 'unit_missing', detail: { kept_for_office: true } }))).toBe(true);
    expect(keptForOfficeOf(j({ message_key: 'work.mobile.not_your_job' }))).toBe(false);
    expect(keptForOfficeOf(null)).toBe(false);
  });

  test('a group says it only when EVERY item behind it was kept', () => {
    const item = (id: string, kept: boolean) => ({
      id,
      workOrderId: 'wo-1',
      workOrderNumber: 'WO-0028',
      reason: '',
      reasonKey: 'r',
      action: 'none' as const,
      keptForOffice: kept,
    });
    expect(groupRefusals([item('a', true), item('b', true)])[0]!.keptForOffice).toBe(true);
    expect(groupRefusals([item('a', true), item('b', false)])[0]!.keptForOffice).toBe(false);
  });
});

test('FF-50: WO-0028 reassigned, three readings kept for the office — the row says the office will review them', async () => {
  const fixture = makeFixture();
  seedRefused(fixture, 3, { reason: 'not_your_job', message_key: 'work.mobile.not_your_job', kept_for_office: true });
  const app = await openScreen('FF-50', fixture);
  const card = within(screen.getAllByTestId('ff50-refused').at(-1)!);
  expect(card.getByText('The office will review this.')).toBeTruthy();
  app.unmount();
});

test('FF-50: the same refusal WITHOUT the flag promises nothing about the office', async () => {
  const fixture = makeFixture();
  seedRefused(fixture, 3, { reason: 'not_your_job', message_key: 'work.mobile.not_your_job' });
  const app = await openScreen('FF-50', fixture);
  const card = within(screen.getAllByTestId('ff50-refused').at(-1)!);
  expect(card.queryByText('The office will review this.')).toBeNull();
  app.unmount();
});

test('FF-50: a single kept item says it too', async () => {
  const fixture = makeFixture();
  seedRefused(fixture, 1, { reason: 'unit_missing', message_key: 'work.mobile.reads.unit_missing', kept_for_office: true });
  const app = await openScreen('FF-50', fixture);
  const card = within(screen.getAllByTestId('ff50-refused').at(-1)!);
  expect(card.getByText('The office will review this.')).toBeTruthy();
  app.unmount();
});
