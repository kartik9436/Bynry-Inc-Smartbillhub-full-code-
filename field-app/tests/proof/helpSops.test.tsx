/**
 * DEF-FLD-10581 (beta report MQ-011) — "Help and SOPs shows 0", end to end
 * from the REAL bundle shape: the server's `mobile._help_row` output
 * (`{id, seq, kind, label, ref, url}`) → a sync → the handset's `document`
 * table → FF-15's count → FF-28's list → a tap on each kind.
 *
 * BR-WRK-038: *"Help is carried with the job and available offline — the SOP,
 * the supervisor's number, the hotline."* So the SOP's bytes come down AT SYNC
 * and open with no signal; the phone number dials; a link opens in the browser
 * and, with no signal, says it needs one.
 *
 * Proved RED (law 7) on c47790c2f, before the bundle's `help` was ingested:
 * the first test failed on the download (`Expected ["https://files.example
 * .test/stored/wo-7101-sop.pdf?…"]`, `Received []`), the second on FF-15
 * (`Expected element to have text content: /Help and SOPs\s*3/ — Received:
 * Help and SOPs0`).
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';
import { Linking } from 'react-native';

import { type Device, UNWIRED_DEVICE } from '../../src/device';
import { helpBundle } from '../sync/support/fakeServer';
import { buildHandset, card, mountHandset, openAt, settle, signInAs, syncNow, TENANT, upsert } from './runtimeApp';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const MINUTE = 60_000;
const WO = 'wo-7101';

async function screenAt(m: ReturnType<typeof mountHandset>, id: 'FF-15' | 'FF-28') {
  await act(async () => {
    m.ref.resetRoot({ index: 0, routes: [{ name: 'Frame' }] });
  });
  await openAt(m, id, { workOrderId: WO });
  const roots = await screen.findAllByTestId(`screen-${id}`);
  return within(roots[roots.length - 1]!);
}

test('a bundle with an SOP, a phone and a link: FF-15 counts 3, FF-28 lists all three, and each opens its way', async () => {
  const opened: string[] = [];
  const device: Device = { ...UNWIRED_DEVICE, documents: { open: (path: string) => (opened.push(path), Promise.resolve()) } };
  const openURL = jest.spyOn(Linking, 'openURL').mockResolvedValue(true);

  const h = buildHandset({ network: 'wifi', device });
  const server = h.serverFor(TENANT);
  server.feed([upsert(card(WO, 'WO-7101', new Date(h.clock.now() + 60 * MINUTE)), h.iso())]);
  const bundle = helpBundle(server, WO);
  const sopUrl = bundle.help![0]!.url!;

  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  await syncNow(m);
  await settle();

  // At sync, never on a tap: the SOP's bytes are on the phone already.
  expect(server.callsTo('bundle')).toContainEqual([WO]);
  expect(h.files.downloads).toEqual([sopUrl]);

  // FF-15: the job's Help and SOPs row counts every help entry.
  const job = await screenAt(m, 'FF-15');
  expect(job.getByTestId('door-FF-28')).toHaveTextContent(/Help and SOPs\s*3/);

  // FF-28 with NO signal: all three listed; the SOP opens from the phone's own copy.
  h.network.set('none');
  await settle();
  const docs = await screenAt(m, 'FF-28');
  expect(docs.getByTestId(`doc-${WO}-h1`)).toHaveTextContent(/Water shut-off SOP/);
  expect(docs.getByTestId(`doc-${WO}-h2`)).toHaveTextContent(/Supervisor.*\(512\) 555-0142/);
  expect(docs.getByTestId(`doc-${WO}-h3`)).toHaveTextContent(/Meter swap video/);

  await act(async () => {
    fireEvent.press(docs.getByTestId(`doc-${WO}-h1`));
  });
  await settle(2);
  expect(opened).toEqual([`help/${WO}-h1.pdf`]);

  // The phone number dials.
  await act(async () => {
    fireEvent.press(docs.getByTestId(`doc-${WO}-h2`));
  });
  expect(openURL).toHaveBeenLastCalledWith('tel:5125550142');

  // The link needs a signal, and says so rather than opening nothing.
  openURL.mockClear();
  await act(async () => {
    fireEvent.press(docs.getByTestId(`doc-${WO}-h3`));
  });
  expect(openURL).not.toHaveBeenCalled();
  expect(docs.getByTestId('open-note')).toHaveTextContent('Needs a signal to open.');

  // With a signal it opens in the browser.
  h.network.set('wifi');
  await settle();
  const online = await screenAt(m, 'FF-28');
  await act(async () => {
    fireEvent.press(online.getByTestId(`doc-${WO}-h3`));
  });
  expect(openURL).toHaveBeenLastCalledWith('https://video.example.test/meter-swap');
  openURL.mockRestore();
}, 60_000);

test('the server wins on help: an entry it stops sending leaves the phone, and an SOP not yet down says when it will be', async () => {
  const h = buildHandset({ network: 'wifi' });
  const server = h.serverFor(TENANT);
  const job = card(WO, 'WO-7101', new Date(h.clock.now() + 60 * MINUTE));
  server.feed([upsert(job, h.iso())]);
  const first = helpBundle(server, WO);

  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  await syncNow(m);
  await settle();
  expect((await screenAt(m, 'FF-15')).getByTestId('door-FF-28')).toHaveTextContent(/Help and SOPs\s*3/);

  // The office takes the video off the job and swaps the SOP for a new one whose link has not been served yet.
  const sopUrl = 'https://files.example.test/stored/new-sop.pdf?X-Amz-Signature=def';
  server.bundles.set(WO, {
    ...first,
    help: [
      { ...first.help![0]!, ref: '0192a7c4-5b1e-7d2a-9c11-000000000002', url: sopUrl },
      first.help![1]!,
    ],
  });
  server.feed([upsert({ ...job, access_notes: 'Dog in the yard.' }, h.iso())]);
  await syncNow(m);
  await settle();

  expect((await screenAt(m, 'FF-15')).getByTestId('door-FF-28')).toHaveTextContent(/Help and SOPs\s*2/);
  const docs = await screenAt(m, 'FF-28');
  expect(docs.queryByTestId(`doc-${WO}-h3`)).toBeNull();
  expect(docs.getByTestId(`doc-${WO}-h1`)).toHaveTextContent(/Downloads at next sync/);
  // The old SOP's file is gone with it; the new one was asked for and not served.
  expect(h.files.deleted).toContain(`help/${WO}-h1.pdf`);
  expect(h.files.downloads).toContain(sopUrl);
}, 60_000);
