/**
 * FB-031 (DEF-FLD-10805) — a job's help document opens, end to end through
 * the running app (`runtimeApp`): the server's `_help_row` → a sync → the
 * handset's `document` table → FF-28 → a tap.
 *
 * Ruling (decision log 2026-10-31, PO **B**): the file is downloaded and kept
 * for offline use and opened through the phone's own app (*Open with…*); no
 * app for it says *No app can open this.* Coordinator judgments: the phone
 * fetches the file from OUR route with the technician's credential; a failed
 * download re-fetches the job's bundle next sync; *No file attached.* and
 * *No number.* replace the false *Downloads at next sync*.
 *
 * WHY THE OLD SUITE COULD NOT SEE IT (the defect's escape reason): every test
 * used a fake viewer that always opens and a bundle whose SOP always had a
 * link. These cases serve the PO's own starter-pack rows — no file, no number
 * — an expired link, and a viewer that has no app.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import { type Device, NoAppError, UNWIRED_DEVICE } from '../../src/device';
import type { WireHelp } from '../../src/sync/fieldApi';
import { FakeServer, helpBundle } from '../sync/support/fakeServer';
import { buildHandset, card, mountHandset, openAt, settle, signInAs, syncNow, TENANT, upsert } from './runtimeApp';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const WO = 'wo-7201';

async function documentsAt(m: ReturnType<typeof mountHandset>) {
  await act(async () => {
    m.ref.resetRoot({ index: 0, routes: [{ name: 'Frame' }] });
  });
  await openAt(m, 'FF-28', { workOrderId: WO });
  const roots = await screen.findAllByTestId('screen-FF-28');
  return within(roots[roots.length - 1]!);
}

async function tap(docs: Awaited<ReturnType<typeof documentsAt>>, id: string) {
  await act(async () => {
    fireEvent.press(docs.getByTestId(`doc-${id}`));
  });
  await settle(2);
}

/** The "Meter exchange" starter pack's three rows as the server now sends them (`ref` None). */
const PACK_ROWS: WireHelp[] = [
  { id: `${WO}-h1`, seq: 1, kind: 'document', label: 'Meter exchange SOP', ref: null, url: null, has_file: false, content_path: null },
  { id: `${WO}-h2`, seq: 2, kind: 'phone', label: 'Supervisor', ref: null, url: null },
  { id: `${WO}-h3`, seq: 3, kind: 'phone', label: 'AMI activation hotline', ref: null, url: null },
];

test("the PO's case: the starter pack's empty rows say No file attached. and No number. — never Downloads at next sync", async () => {
  const h = buildHandset({ network: 'wifi' });
  const server = h.serverFor(TENANT);
  server.feed([upsert(card(WO, 'WO-7201', new Date(h.clock.now() + HOUR)), h.iso())]);
  helpBundle(server, WO, { help: PACK_ROWS });

  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  await syncNow(m);
  await settle();

  expect(h.files.downloads).toEqual([]);
  const docs = await documentsAt(m);
  expect(docs.getByTestId(`doc-${WO}-h1`)).toHaveTextContent(/No file attached\./);
  expect(docs.getByTestId(`doc-${WO}-h1`)).not.toHaveTextContent(/Downloads at next sync/);
  expect(docs.getByTestId(`doc-${WO}-h2`)).toHaveTextContent(/No number\./);
  expect(docs.getByTestId(`doc-${WO}-h3`)).toHaveTextContent(/No number\./);

  await tap(docs, `${WO}-h1`);
  expect(docs.getByTestId('open-note')).toHaveTextContent('No file attached.');
  await tap(docs, `${WO}-h2`);
  expect(docs.getByTestId('open-note')).toHaveTextContent('No number.');
}, 60_000);

test('our own route: the download sends Authorization, lands with its name, and opens in the phone’s own app', async () => {
  const opened: Array<[string, string | undefined]> = [];
  const device: Device = {
    ...UNWIRED_DEVICE,
    documents: { open: (path: string, type?: string) => (opened.push([path, type]), Promise.resolve()) },
  };
  const h = buildHandset({ network: 'wifi', device });
  const server = h.serverFor(TENANT);
  server.feed([upsert(card(WO, 'WO-7201', new Date(h.clock.now() + HOUR)), h.iso())]);
  const path = `/work/mobile/jobs/${WO}/help/${WO}-h1/content`;
  server.documentFiles.set(`${FakeServer.API}${path.slice(1)}`, '%PDF-1.7 meter exchange SOP');
  helpBundle(server, WO, {
    help: [
      {
        id: `${WO}-h1`, seq: 1, kind: 'document', label: 'Meter exchange SOP', ref: '0192a7c4-5b1e-7d2a-9c11-000000000001',
        url: 'https://files.example.test/stored/sop.pdf?X-Amz-Expires=14400', has_file: true, content_path: path,
        file_name: 'Meter exchange SOP.pdf', file_bytes: 27, content_type: 'application/pdf',
      },
    ],
  });

  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  await syncNow(m);
  await settle();

  expect(h.files.downloads).toEqual([`${FakeServer.API}${path.slice(1)}`]);
  expect(h.files.downloadHeaders[0]).toMatchObject({ Authorization: FakeServer.TOKEN });
  const docs = await documentsAt(m);
  expect(docs.getByTestId(`doc-${WO}-h1`)).toHaveTextContent(/on this phone/);
  h.network.set('none');
  await settle();
  await tap(await documentsAt(m), `${WO}-h1`);
  expect(opened).toEqual([[`help/${WO}-h1.pdf`, 'application/pdf']]);
}, 60_000);

test('a refused link re-fetches the bundle at the next sync, and the file lands then', async () => {
  const h = buildHandset({ network: 'wifi' });
  const server = h.serverFor(TENANT);
  server.feed([upsert(card(WO, 'WO-7201', new Date(h.clock.now() + HOUR)), h.iso())]);
  const first = helpBundle(server, WO);
  const stale = first.help![0]!.url!;
  server.documentFiles.delete(stale); // the storage answers 403: the link is dead

  // Signing in runs the first sync on its own.
  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  expect(h.files.downloads).toEqual([stale]);
  expect(server.callsTo('bundle')).toHaveLength(1);

  // The server's next bundle carries a fresh link; nothing in the change feed moved.
  const fresh = 'https://files.example.test/stored/fresh-sop.pdf?X-Amz-Signature=new';
  server.documentFiles.set(fresh, '%PDF-1.7 fresh');
  server.bundles.set(WO, { ...first, help: [{ ...first.help![0]!, url: fresh }, ...first.help!.slice(1)] });
  await syncNow(m);
  await settle();

  expect(server.callsTo('bundle')).toHaveLength(2);
  expect(h.files.downloads).toEqual([stale, fresh]);
  expect((await documentsAt(m)).getByTestId(`doc-${WO}-h1`)).toHaveTextContent(/on this phone/);
}, 60_000);

test('a link more than four hours old is not tried: the bundle is fetched again and the file lands on the next sync', async () => {
  const h = buildHandset({ network: 'wifi' });
  const server = h.serverFor(TENANT);
  server.feed([upsert(card(WO, 'WO-7201', new Date(h.clock.now() + 12 * HOUR)), h.iso())]);
  const first = helpBundle(server, WO);
  const old = first.help![0]!.url!;

  h.files.dropNext = true; // the transfer dies mid-way: no answer, nothing refused
  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz'); // signing in runs the first sync on its own
  await settle();
  expect(h.files.downloads).toEqual([old]);
  expect(server.callsTo('bundle')).toHaveLength(1);

  // Five hours on, the link has expired: it is not tried; the bundle is asked for again.
  // (The row is aged rather than the clock moved: five idle hours would lock the session.)
  h.holder.current!.ref.run('UPDATE document SET updated_at = :at WHERE id = :id', {
    id: `${WO}-h1`,
    at: new Date(h.clock.now() - 5 * HOUR).toISOString(),
  });
  await syncNow(m);
  await settle();
  expect(h.files.downloads).toEqual([old]);
  expect(server.callsTo('bundle')).toHaveLength(1);

  const fresh = 'https://files.example.test/stored/later-sop.pdf?X-Amz-Signature=later';
  server.documentFiles.set(fresh, '%PDF-1.7 later');
  server.bundles.set(WO, { ...first, help: [{ ...first.help![0]!, url: fresh }, ...first.help!.slice(1)] });
  await syncNow(m);
  await settle();
  expect(server.callsTo('bundle')).toHaveLength(2);
  expect(h.files.downloads).toEqual([old, fresh]);
}, 60_000);

test('a phone with no app for the file says No app can open this.', async () => {
  const device: Device = { ...UNWIRED_DEVICE, documents: { open: (path: string) => Promise.reject(new NoAppError(path)) } };
  const h = buildHandset({ network: 'wifi', device });
  const server = h.serverFor(TENANT);
  server.feed([upsert(card(WO, 'WO-7201', new Date(h.clock.now() + HOUR)), h.iso())]);
  helpBundle(server, WO);

  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  await syncNow(m);
  await settle();
  const docs = await documentsAt(m);
  await tap(docs, `${WO}-h1`);
  expect(docs.getByTestId('open-note')).toHaveTextContent('No app can open this.');
}, 60_000);
