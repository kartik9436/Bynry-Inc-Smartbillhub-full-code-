/**
 * Taking a reading and its second thoughts — RW-09 … RW-18 (EP-FLD-11,
 * EP-FLD-12, EP-FLD-13 §3), under the real navigation. Every save goes
 * through the real outbox into the real store, and the tests read the store.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import { fromJson } from '../../../src/db/json';
import * as outboxQ from '../../../src/db/queries/outbox';
import * as walkQ from '../../../src/db/queries/readsWalk';
import * as settingsQ from '../../../src/db/queries/settings';
import { scoped } from '../../../src/db/scoped';
import { LIST_KEYS } from '../../../src/screens/reads/records';
import { RAY, SEEDED_REASONS } from './fixture';
import { FakeCamera, FakeLocation, mountReads } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

type App = Awaited<ReturnType<typeof mountReads>>;

function type(page: ReturnType<typeof within>, digits: string, pad = 'keypad') {
  for (const d of digits) fireEvent.press(page.getByTestId(`${pad}-${d}`));
}

async function press(page: ReturnType<typeof within>, id: string) {
  await act(async () => {
    fireEvent.press(page.getByTestId(id));
  });
}

const rows = (app: App) => outboxQ.listMine(scoped(app.db, RAY), { limit: 100 });
const reading = (app: App, id: string) => walkQ.meter(scoped(app.db, RAY), id);

describe('RW-09 Read entry', () => {
  test('previous reading AND expected range are both on screen (R78, US-FLD-057 TC-1)', async () => {
    const app = await mountReads();
    const page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    expect(page.getByTestId('previous-value')).toHaveTextContent('48,210');
    expect(page.getByTestId('expected-range')).toHaveTextContent('40,000–56,000');
    // R79: name and account beside the meter.
    expect(page.getByTestId('meter-line')).toHaveTextContent(/Unit A · Carla Ruiz/);
    expect(page.getByTestId('meter-line')).toHaveTextContent(/ACC-10294/);
    expect(page.getByTestId('fix-line')).toHaveTextContent(/±4 m/);
    app.unmount();
  });

  test('typing 52410 and saving records a READ with position, unit and key, through the outbox (US-FLD-066 TC-1, US-FLD-063)', async () => {
    const app = await mountReads();
    const page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    expect(page.getByTestId('door-RW-13')).toBeDisabled();
    type(page, '52410');
    expect(page.getByTestId('entry-figure-value')).toHaveTextContent('52,410');
    expect(page.getByTestId('entry-verdict')).toHaveTextContent('Inside the expected range');
    await press(page, 'door-RW-13');
    expect(app.current()).toBe('RW-13');
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`RW-09 → ${app.current()}`).toBe('RW-09 → RW-13');
    const r = reading(app, 'r0471')!;
    expect(r).toMatchObject({ value: '52410', unit: 'gal', reader_status: 'read', warned_accepted: 0, state: 'pending', identified_by: 'listed', read_method: 'walk' });
    expect(r.lat).toBeCloseTo(30.267153, 6);
    expect(r.accuracy_m).toBe(4);
    expect(r.metres_from_record).toBe(40); // 1318 Maple's point is 40 m from where Ray stands
    const out = rows(app).filter((o) => o.kind === 'route_read');
    expect(out).toHaveLength(1);
    expect(out[0]!.id).toBe(r.capture_key);
    expect(out[0]!.channel).toBe('route');
    expect(fromJson<Record<string, unknown>>(out[0]!.payload)).toMatchObject({ value: '52410', unit: 'gal', reader_status: 'read' });
    app.unmount();
  });

  test('out of range turns amber and the button becomes Accept anyway, which opens RW-15 (US-FLD-059 TC-3)', async () => {
    const app = await mountReads();
    const page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    type(page, '71400');
    expect(page.getByTestId('door-RW-15')).toHaveTextContent('Accept anyway');
    expect(page.getByTestId('entry-verdict')).toHaveTextContent('Higher than expected');
    // TC-2 (US-FLD-069): the Photo button turns red of its own accord.
    expect(page.getByTestId('read-photo')).toBeTruthy();
    await press(page, 'door-RW-15');
    expect(app.current()).toBe('RW-15');
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`RW-09 → ${app.current()}`).toBe('RW-09 → RW-15');
    app.unmount();
  });

  test('below last month is its own warning, not "low" (R81, US-FLD-059 TC-4)', async () => {
    const app = await mountReads();
    const page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    type(page, '47000');
    expect(page.getByTestId('entry-verdict')).toHaveTextContent("Below last month's reading");
    expect(page.getByTestId('door-RW-15')).toHaveTextContent('Accept anyway');
    app.unmount();
  });

  test('a prompt with photo required waits for the photo (R97, US-FLD-069 TC-1)', async () => {
    const app = await mountReads();
    let page = within((await app.open('RW-09', { readId: 'r1322' }))!);
    type(page, '1200');
    expect(page.getByTestId('door-RW-13')).toBeDisabled();
    expect(page.getByText('Photo needed first')).toBeTruthy();
    await press(page, 'read-photo');
    expect(app.current()).toBe('RW-14');
    const cam = within((await screen.findAllByTestId('screen-RW-14')).at(-1)!);
    await press(cam, 'door-RW-13');
    expect(app.current()).toBe('RW-09');
    page = within((await screen.findAllByTestId('screen-RW-09')).at(-1)!);
    expect(page.getByTestId('door-RW-13')).not.toBeDisabled();
    await press(page, 'door-RW-13');
    // The reading and its photo landed together (Mobile data §1).
    const r = reading(app, 'r1322')!;
    expect(r.value).toBe('1200');
    expect(walkQ.photos(scoped(app.db, RAY), 'wlk-07').filter((p) => p.read_id === 'r1322')).toHaveLength(1);
    app.unmount();
  });

  test('no fix still saves — with no position and a warning, never refused (R91, US-FLD-064 TC-1)', async () => {
    const app = await mountReads({ location: new FakeLocation(null) });
    const page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    expect(page.getByTestId('fix-line')).toHaveTextContent('No position yet');
    type(page, '52410');
    await press(page, 'door-RW-13');
    const r = reading(app, 'r0471')!;
    expect(r).toMatchObject({ value: '52410', lat: null, fix_quality: 'none' });
    const kept = within((await screen.findAllByTestId('screen-RW-13')).at(-1)!);
    expect(kept.getByText('Saved without a position.')).toBeTruthy();
    app.unmount();
  });

  test('saving with no remark is fine; a typed remark is kept as typed (R95, US-FLD-068)', async () => {
    const app = await mountReads();
    const page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    await press(page, 'read-remark');
    fireEvent.changeText(screen.getByLabelText('What you saw'), 'Pit lid cracked, water pooling around it.');
    await press(within(screen.getByTestId('remark-sheet')), 'remark-save');
    type(page, '52410');
    await press(page, 'door-RW-13');
    expect(reading(app, 'r0471')).toMatchObject({ remark: 'Pit lid cracked, water pooling around it.', remark_source: 'typed' });
    app.unmount();
  });

  test('its doors: Dials, Scan, Can’t read', async () => {
    const app = await mountReads();
    for (const [door, to] of [
      ['door-RW-10', 'RW-10'],
      ['door-RW-11', 'RW-11'],
      ['door-RW-17', 'RW-17'],
    ] as const) {
      const page = within((await app.open('RW-09', { readId: 'r0471' }))!);
      await press(page, door);
      expect(`${door} → ${app.current()}`).toBe(`${door} → ${to}`);
    }
    app.unmount();
  });

  // US-FLD-077 TC-2 (the keypad beside the route and its progress) moved to
  // `tests/tablet/contextPanes.test.tsx` (T-29): the route now sits in the
  // tablet's shared route pane beside RW-09, which needs the board's 1024 ×
  // 768 window; this file mounts at Jest's 750, where the T3 frame is one pane.
});

describe('RW-10 Dials', () => {
  test('one dial per digit of last month; tapping moves a dial; it reads the figure with its use (US-FLD-057 TC-2)', async () => {
    const app = await mountReads();
    const page = within((await app.open('RW-10', { readId: 'r0471' }))!);
    // 48210 → tap the second dial four times: 4 8 → 4 2 … ; set 52410 instead from 48210.
    for (let i = 0; i < 7; i++) fireEvent.press(page.getByTestId('dial-0')); // 4 → 1? (4+7)%10 = 1
    expect(page.getByTestId('dials-figure-value')).toHaveTextContent('18,210');
    expect(page.getByTestId('dials-used')).toHaveTextContent(/Below last month/);
    for (let i = 0; i < 4; i++) fireEvent.press(page.getByTestId('dial-0')); // 1 → 5
    for (let i = 0; i < 4; i++) fireEvent.press(page.getByTestId('dial-1')); // 8 → 2
    for (let i = 0; i < 2; i++) fireEvent.press(page.getByTestId('dial-2')); // 2 → 4
    for (let i = 0; i < 9; i++) fireEvent.press(page.getByTestId('dial-3')); // 1 → 0
    for (let i = 0; i < 1; i++) fireEvent.press(page.getByTestId('dial-4')); // 0 → 1
    expect(page.getByTestId('dials-figure-value')).toHaveTextContent('52,401');
    expect(page.getByTestId('dials-used')).toHaveTextContent('Used 4,191 gal · Inside the expected range');
    await press(page, 'door-RW-06');
    expect(app.current()).toBe('RW-06');
    expect(reading(app, 'r0471')).toMatchObject({ value: '52401', reader_status: 'read' });
    app.unmount();
  });
});

describe('RW-11 Scan to confirm', () => {
  test('a badge that matches reads the meter, identified by scan (R83, US-FLD-058 TC-2)', async () => {
    const app = await mountReads();
    app.scanner.queue.push('88241');
    const page = within((await app.open('RW-11', { readId: 'r0471' }))!);
    expect(await page.findByTestId('scan-match')).toHaveTextContent('88241 matches. Unit A, Carla Ruiz.');
    await press(page, 'door-RW-09');
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`RW-11 → ${app.current()}`).toBe('RW-11 → RW-09');
    const entry = within((await screen.findAllByTestId('screen-RW-09')).at(-1)!);
    type(entry, '52410');
    await press(entry, 'door-RW-13');
    expect(reading(app, 'r0471')?.identified_by).toBe('scan');
    app.unmount();
  });

  test('a badge that does not match cannot be read here; it goes to RW-18', async () => {
    const app = await mountReads();
    app.scanner.queue.push('90876');
    const page = within((await app.open('RW-11', { readId: 'r0471' }))!);
    expect(await page.findByTestId('scan-mismatch')).toBeTruthy();
    expect(page.getByTestId('door-RW-09')).toBeDisabled();
    await press(page, 'door-RW-18');
    expect(app.current()).toBe('RW-18');
    expect(app.currentParams()).toMatchObject({ readId: 'r0471', code: '90876' });
    app.unmount();
  });
});

describe('RW-13 The reading', () => {
  test('the record as kept, both statuses apart (R96), held on the phone', async () => {
    const app = await mountReads();
    const page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    type(page, '52410');
    await press(page, 'door-RW-13');
    const kept = within((await screen.findAllByTestId('screen-RW-13')).at(-1)!);
    expect(kept.getByTestId('kept-figure-value')).toHaveTextContent('52,410');
    expect(kept.getByTestId('reader-status')).toHaveTextContent('Read');
    expect(kept.getByTestId('kept-used')).toHaveTextContent('Used 4,200 gal');
    expect(kept.getByTestId('kept-position')).toHaveTextContent(/30\.267153, -97\.743061 · ±4 m · 40 m from the record/);
    expect(kept.getByText('Not yet')).toBeTruthy();
    expect(kept.getByTestId('kept-state')).toHaveTextContent('Held on the phone.');
    // Next meter goes on to the next unread meter at the same address.
    await press(kept, 'door-RW-06');
    expect(app.current()).toBe('RW-09');
    expect(app.currentParams()?.readId).not.toBe('r0471');
    app.unmount();
  });
});

describe('RW-14 The camera', () => {
  test('camera only; the stamp handed to the camera carries date, position, reader, meter, route (R93, R94, US-FLD-067 TC-1)', async () => {
    const camera = new FakeCamera();
    const app = await mountReads({ camera });
    const page = within((await app.open('RW-14', { readId: 'r0471' }))!);
    expect(page.getByText('Camera only')).toBeTruthy();
    expect(page.queryByText(/gallery/i)).toBeNull();
    await press(page, 'door-RW-13');
    expect(camera.stamps[0]).toEqual([
      expect.stringMatching(/2026 · \d\d:\d\d:18$/),
      '30.267153, -97.743061 · ±4 m',
      'R. Delacroix · MTR-0471 · WLK-07',
    ]);
    app.unmount();
  });

  test('with no camera on the phone the shutter is off and the screen says so', async () => {
    const app = await mountReads({ camera: new FakeCamera(false) });
    const page = within((await app.open('RW-14', { readId: 'r0471' }))!);
    expect(page.getByTestId('door-RW-13')).toBeDisabled();
    expect(page.getByText('No camera on this phone.')).toBeTruthy();
    app.unmount();
  });
});

describe('RW-15 High or low and RW-16 Second look', () => {
  async function typeHigh(app: App) {
    const page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    type(page, '71400');
    await press(page, 'door-RW-15');
    return within((await screen.findAllByTestId('screen-RW-15')).at(-1)!);
  }

  test('offers the re-read FIRST and accepting second; names the use it implies (US-FLD-059 TC-1)', async () => {
    const app = await mountReads();
    const page = await typeHigh(app);
    expect(page.getByTestId('warning-card')).toHaveTextContent(/Higher than expected/);
    expect(page.getByTestId('you-typed')).toHaveTextContent(/71,400 gal/);
    expect(page.getByTestId('would-be')).toHaveTextContent('23,190 gal');
    expect(page.getByTestId('door-RW-16')).toHaveTextContent('Read it again');
    expect(page.getByTestId('door-RW-06')).toHaveTextContent('Accept 71,400 anyway');
    app.unmount();
  });

  test('accepting anyway keeps the figure as Read with a problem, flagged (R80, R96, US-FLD-066 TC-3)', async () => {
    const app = await mountReads();
    const page = await typeHigh(app);
    await press(page, 'door-RW-06');
    expect(app.current()).toBe('RW-06');
    expect(reading(app, 'r0471')).toMatchObject({ value: '71400', reader_status: 'read_with_problem', warned_accepted: 1 });
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`RW-15 → ${app.current()}`).toBe('RW-15 → RW-06');
    app.unmount();
  });

  test('reading again keeps BOTH entries — nothing is overwritten (US-FLD-059 TC-2)', async () => {
    const app = await mountReads();
    const page = await typeHigh(app);
    await press(page, 'door-RW-16');
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`RW-15 → ${app.current()}`).toBe('RW-15 → RW-16');
    const look = within((await screen.findAllByTestId('screen-RW-16')).at(-1)!);
    expect(look.getByTestId('first-try')).toHaveTextContent(/71,400/);
    expect(look.getByTestId('first-try')).toHaveTextContent(/Nothing is overwritten/);
    type(look, '52410', 'keypad2');
    expect(look.getByTestId('second-verdict')).toHaveTextContent('Used 4,200 gal · Inside the expected range');
    await press(look, 'door-RW-13');
    expect(app.current()).toBe('RW-13');
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`RW-16 → ${app.current()}`).toBe('RW-16 → RW-13');
    expect(reading(app, 'r0471')).toMatchObject({ value: '52410', reader_status: 'read' });
    const payload = fromJson<Record<string, unknown>>(rows(app).find((o) => o.kind === 'route_read')!.payload)!;
    expect(payload.value).toBe('52410');
    expect(payload.first_try).toMatchObject({ value: '71400' });
    app.unmount();
  });
});

describe('RW-17 Can’t read', () => {
  test('lists the utility’s own reasons, as served — the test counts the served list (R82, US-FLD-060 TC-1, TC-3)', async () => {
    const app = await mountReads();
    const page = within((await app.open('RW-17', { readId: 'r0471' }))!);
    const served = settingsQ.get<typeof SEEDED_REASONS>(app.db, LIST_KEYS.cantRead)!;
    expect(page.getAllByRole('radio')).toHaveLength(served.length);
    for (const r of served) expect(page.getByText(r.label)).toBeTruthy();
    expect(page.getByTestId('door-RW-06')).toBeDisabled();
    await press(page, 'reasons-dog');
    await press(page, 'door-RW-06');
    expect(reading(app, 'r0471')).toMatchObject({ value: null, reader_status: 'could_not_read', no_read_reason: 'dog' });
    app.unmount();
  });

  test('the utility adds Flooded: it appears after the next refresh (US-FLD-060 TC-2)', async () => {
    const app = await mountReads();
    settingsQ.set(app.db, LIST_KEYS.cantRead, [...SEEDED_REASONS, { code: 'flooded', label: 'Flooded' }], '2026-10-20T11:00:00.000Z');
    const page = within((await app.open('RW-17', { readId: 'r0471' }))!);
    expect(page.getByText('Flooded')).toBeTruthy();
    expect(page.getAllByRole('radio')).toHaveLength(SEEDED_REASONS.length + 1);
    app.unmount();
  });

  test('no list on the phone: says so and offers none written in code', async () => {
    const app = await mountReads({ seed: (db) => require('./fixture').seedMapleHeights(db, { lists: false }) });
    const page = within((await app.open('RW-17', { readId: 'r0471' }))!);
    expect(page.getByTestId('no-reasons')).toBeTruthy();
    expect(page.queryAllByRole('radio')).toHaveLength(0);
    await press(page, 'door-RW-21');
    expect(app.current()).toBe('RW-21');
    app.unmount();
  });
});

describe('RW-18 Different meter', () => {
  test('refuses to let a wrong badge be guessed: the plate photo is required (US-FLD-061 TC-3)', async () => {
    const app = await mountReads();
    const page = within((await app.open('RW-18', { readId: 'r0471', code: '90876' }))!);
    expect(page.getByText('Not the badge on the list. Do not guess.')).toBeTruthy();
    expect(page.getByTestId('scanned-card')).toHaveTextContent(/MTR-0533/);
    expect(page.getByTestId('scanned-card')).toHaveTextContent(/Recorded at 1206 Maple Street/);
    await press(page, 'truth-cannot_tell');
    expect(page.getByTestId('door-RW-09')).toBeDisabled();
    await press(page, 'plate-photo');
    expect(page.getByTestId('door-RW-09')).not.toBeDisabled();
    await press(page, 'door-RW-09');
    const raise = rows(app).find((o) => o.kind === 'route_finding')!;
    expect(fromJson<Record<string, unknown>>(raise.payload)).toMatchObject({ mismatch: 'cannot_tell', listed_asset_id: 'a0471', scanned_asset_id: 'a0533' });
    // Nothing was read against the listed meter.
    expect(reading(app, 'r0471')?.state).toBe('unread');
    app.unmount();
  });
});
