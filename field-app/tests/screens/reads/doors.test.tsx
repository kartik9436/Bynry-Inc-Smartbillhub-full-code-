/**
 * Every door of every reading screen (RW-01…RW-29), pressed on the real tree
 * and named as `'<from> → <to>'` — the hand-off `tests/navigation/doors.test.tsx`
 * checks for every BUILT screen (added in the integration lane, when the
 * reads wave landed beside four others).
 *
 * A door is the control the screen draws with `testID="door-<to>"`; the
 * header's back arrow and menu are the same (`READS_HEADER`,
 * `screens/reads/ReadsScreen.tsx`). RW-01 is a tab: its menu is the tab
 * header's and its other two doors are the bottom tabs (`CONTROL`). A door
 * that exists only in a state — a turned-in route, a read meter, a reason
 * chosen — gets that state first (`SETUP`, `OPEN`). The doors that are a
 * typed figure or a scan are pressed and named in `reading.test.tsx` and
 * `stop.test.tsx`, which set those up.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';

import * as routeQ from '../../../src/db/queries/route';
import * as routeReadQ from '../../../src/db/queries/routeRead';
import { scoped } from '../../../src/db/scoped';
import type { ScreenId } from '../../../src/navigation/screens';
import { READS_HEADER, type ReadsParams } from '../../../src/screens/reads/ReadsScreen';
import { coldOpen } from '../../navigation/coldOpen';
import { mountReads } from './harness';
import { RAY } from './fixture';
import { PARAMS } from './params';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

type Door = `${ScreenId} → ${ScreenId}`;
type App = Awaited<ReturnType<typeof mountReads>>;

const readIt = (app: App, readId: string) =>
  routeReadQ.recordCapture(scoped(app.db, RAY), readId, {
    captureKey: `cap-${readId}`, value: '2100', unit: 'gal', readerStatus: 'read',
    capturedAt: '2026-10-20T10:00:00.000Z', capturedBy: RAY, identifiedBy: 'listed', readMethod: 'walk',
  });

/** The control, where it is not `door-<to>`. */
const CONTROL: Partial<Record<Door, string>> = {
  'RW-01 → FF-09': 'open-menu',
  'RW-01 → FF-63': 'tab-FF-63',
  'RW-01 → FF-10': 'tab-FF-10',
};

/** Where the door is drawn only for a particular record: what to open, after what. */
const OPEN: Partial<Record<Door, { params: ReadsParams; before: (app: App) => void }>> = {
  // r1240 is the only meter at its stop: once read, *Next meter* goes back to the stop.
  'RW-13 → RW-06': { params: { readId: 'r1240' }, before: (app) => readIt(app, 'r1240') },
  // A photo of a meter already read goes on to its record.
  'RW-14 → RW-13': { params: { readId: 'r1240' }, before: (app) => readIt(app, 'r1240') },
  // 88241 is Carla's meter, r0471 — on this phone, so a swap reads it.
  'RW-18 → RW-09': { params: { readId: 'r0472', code: '88241' }, before: () => undefined },
  'RW-01 → RW-27': { params: {}, before: (app) => routeQ.markTurnedIn(scoped(app.db, RAY), 'wlk-07', '2026-10-20T16:00:00.000Z') },
};

/** Puts the screen in the state that draws the door. */
const pressFirst = (page: ReturnType<typeof within>, pattern: RegExp) => {
  const found = page.queryAllByTestId(pattern);
  if (found[0]) fireEvent.press(found[0]);
};
const SETUP: Partial<Record<Door, (page: ReturnType<typeof within>) => Promise<void>>> = {
  'RW-17 → RW-06': async (page) => pressFirst(page, /^reasons-/),
  // *It was swapped*, and the meter scanned is on this phone: read that one.
  'RW-18 → RW-09': async (page) => {
    fireEvent.press(page.getByTestId('truth-swapped'));
    await act(async () => {
      fireEvent.press(page.getByTestId('plate-photo'));
    });
  },
};

const DOORS: Door[] = [
  'RW-01 → FF-09',
  'RW-01 → RW-08',
  'RW-01 → RW-26',
  'RW-01 → RW-02',
  'RW-01 → RW-27',
  'RW-01 → RW-03',
  'RW-01 → FF-63',
  'RW-01 → FF-10',
  'RW-02 → RW-01',
  'RW-02 → RW-04',
  'RW-02 → RW-03',
  'RW-03 → RW-05',
  'RW-04 → RW-05',
  'RW-04 → RW-06',
  'RW-05 → RW-02',
  'RW-05 → RW-04',
  'RW-05 → RW-22',
  'RW-05 → RW-06',
  'RW-05 → RW-19',
  'RW-06 → RW-05',
  'RW-06 → RW-07',
  'RW-06 → RW-09',
  'RW-06 → RW-12',
  'RW-06 → RW-19',
  'RW-06 → RW-17',
  'RW-07 → RW-06',
  'RW-08 → RW-01',
  // 'RW-09 → RW-06' is drawn on the tablet's route pane (`tablet/RouteContextPane`,
  // *The stop*); this file mounts a phone, so it is pressed in
  // `tests/tablet/contextPanes.test.tsx` at 1024 × 768 instead. Until T-29 it
  // passed here only because Jest's 750 window read as a tablet to RW-09.
  'RW-09 → RW-10',
  'RW-09 → RW-11',
  'RW-09 → RW-17',
  'RW-10 → RW-09',
  'RW-10 → RW-17',
  'RW-10 → RW-06',
  'RW-11 → RW-18',
  'RW-12 → RW-06',
  'RW-12 → RW-09',
  'RW-12 → RW-17',
  'RW-13 → RW-09',
  'RW-13 → RW-14',
  'RW-13 → RW-06',
  'RW-14 → RW-09',
  'RW-14 → RW-13',
  'RW-15 → RW-09',
  'RW-16 → RW-15',
  'RW-17 → RW-09',
  'RW-17 → RW-21',
  'RW-17 → RW-06',
  'RW-18 → RW-11',
  'RW-18 → RW-09',
  'RW-19 → RW-06',
  'RW-19 → RW-09',
  'RW-19 → RW-20',
  'RW-20 → RW-19',
  'RW-22 → RW-05',
  'RW-22 → RW-23',
  'RW-22 → RW-24',
  'RW-22 → RW-25',
  'RW-23 → RW-22',
  'RW-23 → RW-06',
  'RW-23 → RW-04',
  'RW-24 → RW-22',
  'RW-25 → RW-22',
  'RW-25 → RW-23',
  'RW-25 → RW-26',
  'RW-26 → RW-27',
  'RW-27 → RW-01',
  'RW-28 → FF-09',
  'RW-29 → FF-51',
];

test.each(DOORS)('%s', async (door) => {
  const [from, to] = door.split(' → ') as [ScreenId, ScreenId];
  const app = await mountReads();
  const opening = OPEN[door];
  opening?.before(app);
  let top = await app.open(from, opening?.params ?? (PARAMS[from] as ReadsParams));
  await act(async () => undefined);
  // A header back arrow follows its drawn door only when there is no history
  // (DEF-FLD-10607, PO 2026-10-26): open the screen cold to assert it.
  const header = READS_HEADER[from];
  if (header && 'back' in header && header.back === to) {
    await coldOpen(app.ref, from);
    top = screen.getAllByTestId(`screen-${from}`).at(-1);
  }
  const page = within(top!);
  await SETUP[door]?.(page);
  const id = CONTROL[door] ?? `door-${to}`;
  const control = page.queryAllByTestId(id)[0] ?? screen.queryAllByTestId(id).at(-1);
  if (!control) throw new Error(`${door}: no control`);
  await act(async () => {
    fireEvent.press(control);
  });
  if (to === 'FF-09') {
    const open = JSON.stringify(app.ref.getRootState()).includes('"status":"open"');
    expect(open ? door : `${from} → menu closed`).toBe(door);
  } else {
    // Some acts save first (an outbox write, a photo), then move on.
    await waitFor(() => expect(`${from} → ${app.current()}`).toBe(door));
  }
  app.unmount();
});
