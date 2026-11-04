/**
 * DEF-FLD-10629 — FB-004, THROUGH THE APP: a meter reader's route readings and
 * photographs never left the phone (decision log 2026-10-27, *"yes add G to
 * K to the sync fix, start"*).
 *
 * What the PO saw (Android, reader Sam Curran, route RT-001): FF-50 ONLINE,
 * *"12 waiting"*, *"Last reached the server 18:37"*, *"Photos 4 uploading ·
 * 0 of 4"*, *"Jobs 0 of 0"*; *Sync now* showed nothing at all.
 *
 * The cause, reproduced: the reader's CAPTURE credential — what every send
 * travels under (Security §3) — was not issued at sign-in (that renewal fails
 * silently), so `sendPending` skipped the whole route and only counted it.
 * The pull uses the ACCESS token, so *Last reached* went on moving.
 *
 * Proved RED on the code before this fix (law 7), quoted in the commit.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';

import * as outboxQ from '../../src/db/queries/outbox';
import * as routeQ from '../../src/db/queries/route';
import * as routeReadQ from '../../src/db/queries/routeRead';
import { scoped } from '../../src/db/scoped';
import { capture } from '../../src/sync/outbox';
import { buildHandset, mountHandset, openAt, PEOPLE, settle, sha, signInAs, TENANT } from '../proof/runtimeApp';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const SAM = PEOPLE['d.ortiz']!.technicianId; // the reader on this handset

async function readerWithRoute() {
  const h = buildHandset({ network: 'wifi' });
  const server = h.serverFor(TENANT);
  // The capture credential is not issued at sign-in — and that fails silently.
  const issue = h.api.issueCaptureToken.bind(h.api);
  let refuse = true;
  h.api.issueCaptureToken = (input) => (refuse ? Promise.reject(new Error('capture token: server error')) : issue(input));
  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  expect(h.session.captureValid(SAM)).toBe(false);
  const db = h.holder.current!;
  const s = scoped(db, SAM);
  const now = h.iso();
  db.transaction(() => {
    routeQ.upsert(s, { id: 'rt-001', code: 'RT-001', service: 'water' }, now);
    for (let i = 1; i <= 12; i += 1) {
      routeReadQ.upsertFromServer(s, { id: `rr-${i}`, routeId: 'rt-001', stopId: `st-${i}`, assetId: `m-${i}`, unit: 'm3' }, now);
    }
  });
  // Eight meters read; four with a photograph — the route's own capture path.
  let n = 0;
  const ids = () => `fb-${String((n += 1)).padStart(3, '0')}`;
  for (let i = 1; i <= 8; i += 1) {
    const photos =
      i <= 4
        ? [{ localPath: `file:///rt/${i}.jpg`, sha256: sha(`plate-${i}`), bytes: 900_000, target: { route_read_id: `rr-${i}` } }]
        : [];
    for (const p of photos) h.files.add(p.localPath, `plate-${i}`);
    capture(db, { technicianId: SAM, capturedBy: SAM }, { kind: 'route_read', routeId: 'rt-001', payload: { route_read_id: `rr-${i}`, value: String(100 + i), unit: 'm3' }, photos }, { newId: ids, clock: { now: () => new Date(h.clock.now()) } });
  }
  return { h, m, s, server, allow: () => (refuse = false) };
}

test('FB-004: the capture credential is renewed at Sync now and the route goes — readings and photographs', async () => {
  const t = await readerWithRoute();
  await openAt(t.m, 'FF-50');
  const ff50 = within(await screen.findByTestId('screen-FF-50'));
  const waiting = outboxQ.countUnsentMine(t.s);
  expect(waiting).toBeGreaterThan(0);
  t.allow(); // the server issues credentials again
  await act(async () => {
    fireEvent.press(ff50.getByTestId('ff50-sync-now'));
  });
  await waitFor(() => expect(outboxQ.countUnsentMine(t.s)).toBe(0), { timeout: 4000 });
  expect(t.server.applied.filter((a) => a.kind === 'route_read')).toHaveLength(8);
  await waitFor(() => expect(t.server.photoRequests.length).toBe(4));
  await waitFor(() => expect(ff50.getByTestId('ff50-sent')).toBeTruthy());
});

test('FB-004: when the credential cannot be renewed, FF-50 says so, counts it, and offers the way in — never silence', async () => {
  const t = await readerWithRoute();
  await openAt(t.m, 'FF-50');
  const ff50 = within(await screen.findByTestId('screen-FF-50'));
  // I and J before any press: the photographs wait for their readings; the route is on the phone.
  expect(ff50.getByTestId('ff50-photos')).toHaveTextContent(/Waiting for readings/);
  expect(ff50.getByTestId('ff50-routes')).toHaveTextContent(/1 · 12 meters/);
  await act(async () => {
    fireEvent.press(ff50.getByTestId('ff50-sync-now'));
  });
  await waitFor(() => expect(ff50.getByTestId('ff50-sign-in-to-send')).toHaveTextContent(/Sign in again to send\./));
  expect(ff50.getByTestId('ff50-sign-in-to-send-count')).toHaveTextContent(`${outboxQ.countUnsentMine(t.s)} items wait for you.`);
  expect(ff50.getByTestId('ff50-sign-in-to-send-button')).toBeTruthy();
  expect(t.server.applied).toEqual([]);
});
