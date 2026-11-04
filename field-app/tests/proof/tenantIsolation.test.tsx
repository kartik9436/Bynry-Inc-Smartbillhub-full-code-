/**
 * T-50 — TENANT ISOLATION ON THE HANDSET, through the real app root. The
 * tenant is the FILE (R131): `field-<tenant>.sqlite`, opened at sign-in by
 * `FieldRuntime` through the store holder. `tests/db/tenant.test.ts` proves
 * the store half on bare handles; this proves it the way a technician meets it:
 *
 *  1. A contractor (the same technician id) works for two utilities, North and
 *     South, on one handset. Each tenant's feed lands in its own file; the DAY
 *     READ — Today, and Today's search — shows North's jobs signed in to North
 *     and South's signed in to South, never the other's, with the other
 *     tenant's rows sitting in the other file the whole time.
 *  2. A store file stamped for one tenant and reached under another's name (a
 *     copied or renamed file) REFUSES to open: the runtime reports why, opens
 *     nothing, and Today says the day is not on the phone — not North's day.
 *
 * Proved RED (lane report): with `openTenantDb`'s stamp check removed, the
 * mislabelled file opened and Today listed North's job under "east".
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen } from '@testing-library/react-native';

import { TenantMismatchError } from '../../src/db/database';
import type { DriverFactory } from '../../src/db/driver';
import * as workOrderQ from '../../src/db/queries/workOrder';
import { scoped } from '../../src/db/scoped';
import { memoryFactory } from '../db/support/nodeDriver';
import { buildHandset, card, mountHandset, openAt, PEOPLE, settle, signInAs, signOut, upsert } from './runtimeApp';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const DANA = PEOPLE['d.ortiz']!.technicianId;
const MINUTE = 60_000;

function todayIds(): string[] {
  return screen.queryAllByTestId(/^job-wo-[a-z]+-\d+$/).map((el) => String(el.props.testID).replace('job-', ''));
}

async function search(text: string): Promise<void> {
  await act(async () => {
    fireEvent.changeText(screen.getByTestId('today-search'), text);
  });
}

test('T-50: two utilities, one handset — each day read shows its own tenant’s jobs and never the other’s', async () => {
  const base = memoryFactory();
  const h = buildHandset({ network: 'wifi', factory: base });
  const at = new Date(h.clock.now() + 30 * MINUTE);
  h.serverFor('north').feed([upsert(card('wo-north-1', 'WO-1001', at, 60, { premise: { id: 'p-n', address: '1 North Road' } }), h.iso())]);
  h.serverFor('south').feed([upsert(card('wo-south-1', 'WO-2001', at, 60, { premise: { id: 'p-s', address: '9 South Lane' } }), h.iso())]);
  const m = mountHandset(h);

  // North.
  await signInAs(h, 'd.ortiz', 'north');
  await settle();
  expect(h.holder.current?.tenant).toBe('north');
  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  expect(todayIds()).toEqual(['wo-north-1']);
  await signOut(h);

  // South: its own file; North's job is in North's file and nowhere on this screen.
  await signInAs(h, 'd.ortiz', 'south');
  await settle();
  expect(h.holder.current?.tenant).toBe('south');
  expect([...base.files.keys()].sort()).toEqual(['field-north.sqlite', 'field-south.sqlite']);
  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  expect(todayIds()).toEqual(['wo-south-1']);
  // The day read, asked for North's job by number and by street, finds nothing.
  await search('WO-1001');
  expect(todayIds()).toEqual([]);
  await search('North');
  expect(todayIds()).toEqual([]);
  await search('WO-2001');
  expect(todayIds()).toEqual(['wo-south-1']);
  // And the store this screen reads cannot reach North's row; North's file still holds it.
  expect(workOrderQ.getMine(scoped(h.holder.current!, DANA), 'wo-north-1')).toBeUndefined();
  m.unmount();
  const northAgain = buildHandset({ factory: base });
  northAgain.holder.open('north');
  expect(workOrderQ.getMine(scoped(northAgain.holder.current!, DANA), 'wo-north-1')?.number).toBe('WO-1001');
}, 60_000);

test('T-50: a store stamped for North, reached under another tenant’s name, refuses to open — and Today shows no day at all', async () => {
  const base = memoryFactory();
  // A copied or renamed file: "east" reaches North's bytes.
  const factory = ((name: string) => base(name === 'field-east.sqlite' ? 'field-north.sqlite' : name)) as DriverFactory;
  const h = buildHandset({ network: 'none', factory });
  const at = new Date(h.clock.now() + 30 * MINUTE);
  h.serverFor('north').feed([upsert(card('wo-north-1', 'WO-1001', at), h.iso())]);
  h.network.current = 'wifi';
  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz', 'north');
  await settle();
  await signOut(h);

  await signInAs(h, 'd.ortiz', 'east');
  await settle();
  expect(h.holder.current).toBeNull();
  expect(m.inside.current.runtime?.db).toBeNull();
  expect(m.inside.current.runtime?.openError).toMatch(/belongs to tenant "north", not "east"/);
  expect(() => h.holder.open('east')).toThrow(TenantMismatchError);
  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  expect(screen.getByTestId('today-not-loaded')).toBeTruthy();
  expect(todayIds()).toEqual([]);
  m.unmount();
}, 60_000);
