/**
 * DEF-FLD-10585 (beta MQ-022): a TEXT reading — a serial, a seal number — is
 * saved exactly as typed, shown verbatim and sent as `value_text`; a NUMBER
 * reading given letters says "Numbers only." instead of silently refusing;
 * and the expected range reads "Expected 0–99,999", not "0.0000–99,999.0000".
 *
 * The readings arrive the way the server sends them: through `applyBundle`,
 * in the shape `apps/work/checklist.py` serves (`kind`, an empty
 * `unit_of_measure` on a text reading, four-place bounds), onto the boards'
 * WO-4822 (`./fixture`).
 */
import 'react-native-gesture-handler/jestSetup';

import { fireEvent, within } from '@testing-library/react-native';

import * as outboxQ from '../../../src/db/queries/outbox';
import * as woReadingQ from '../../../src/db/queries/woReading';
import { scoped } from '../../../src/db/scoped';
import { applyBundle } from '../../../src/sync/extras';
import type { WireBundle } from '../../../src/sync/fieldApi';
import { DANA, seedWO4822, WO } from './fixture';
import { mountJob, onTop } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => require('./window').currentWindow(),
}));

/** The real bundle shape for three of WO-0029's readings (MQ-022). */
const BUNDLE = {
  order_id: WO,
  order_no: 'WO-4822',
  template_id: 'tpl-mx',
  template_version: 3,
  safety: [],
  tasks: [],
  materials: [],
  readings: [
    { id: 'r-serial', seq: 4, prompt: 'New meter serial', unit_of_measure: '', min_value: null, max_value: null, required: true, photo_required: false, posts_as_meter_read: false, value: null, kind: 'text' },
    { id: 'r-seal', seq: 5, prompt: 'Seal number', unit_of_measure: '', min_value: null, max_value: null, required: true, photo_required: false, posts_as_meter_read: false, value: null, kind: 'text' },
    { id: 'r-open', seq: 6, prompt: 'Opening read', unit_of_measure: 'kWh', min_value: '0.0000', max_value: '99999.0000', required: true, photo_required: false, posts_as_meter_read: true, value: null, kind: 'number' },
  ],
} as unknown as WireBundle;

function seeded() {
  const f = seedWO4822();
  applyBundle(f.db, DANA, BUNDLE, f.clock.now());
  return f;
}

const row = (f: ReturnType<typeof seedWO4822>, id: string) => woReadingQ.listForOrder(scoped(f.db, DANA), WO).find((r) => r.id === id);
const sent = (f: ReturnType<typeof seedWO4822>, id: string) =>
  outboxQ
    .listMine(scoped(f.db, DANA), { limit: 500 })
    .filter((r) => r.kind === 'reading')
    .map((r) => JSON.parse(r.payload) as Record<string, unknown>)
    .filter((p) => p.reading_id === id);

describe('DEF-FLD-10585 — a text reading is words (MQ-022)', () => {
  test('the bundle keeps the kind: a text reading lands, with no unit and no range', () => {
    const f = seeded();
    expect(row(f, 'r-serial')).toMatchObject({ kind: 'text', unit: '', min_value: null, max_value: null, value_text: null });
    expect(row(f, 'r-open')).toMatchObject({ kind: 'number', unit: 'kWh' });
  });

  test('SN-2026-0042 and ABC-123 are saved exactly as typed, shown verbatim and sent as value_text', async () => {
    const f = seeded();
    await mountJob(f.services, 'FF-20');
    const top = () => within(onTop('FF-20'));
    const serial = () => within(top().getByTestId('reading-r-serial'));
    expect(serial().getByTestId('reading-r-serial-field-input')).toHaveProp('keyboardType', 'default');
    expect(serial().queryByText(/^Expected/)).toBeNull();

    fireEvent.changeText(serial().getByTestId('reading-r-serial-field'), '  SN-2026-0042 ');
    fireEvent.press(serial().getByTestId('reading-r-serial-save'));
    expect(row(f, 'r-serial')).toMatchObject({ value_text: 'SN-2026-0042', value: null, flagged: 0 });
    expect(serial().getByTestId('reading-r-serial-field-input')).toHaveProp('value', 'SN-2026-0042');
    expect(sent(f, 'r-serial').at(-1)).toMatchObject({ reading_id: 'r-serial', value_text: 'SN-2026-0042' });
    expect(sent(f, 'r-serial').at(-1)).not.toHaveProperty('value');

    const seal = () => within(top().getByTestId('reading-r-seal'));
    fireEvent.changeText(seal().getByTestId('reading-r-seal-field'), 'ABC-123');
    fireEvent(seal().getByTestId('reading-r-seal-field'), 'submitEditing');
    expect(row(f, 'r-seal')?.value_text).toBe('ABC-123');
    expect(sent(f, 'r-seal').at(-1)).toMatchObject({ value_text: 'ABC-123' });
  });

  test('a numeric serial, 20260042, is shown without commas', async () => {
    const f = seeded();
    await mountJob(f.services, 'FF-20');
    const serial = () => within(within(onTop('FF-20')).getByTestId('reading-r-serial'));
    fireEvent.changeText(serial().getByTestId('reading-r-serial-field'), '20260042');
    fireEvent.press(serial().getByTestId('reading-r-serial-save'));
    expect(row(f, 'r-serial')?.value_text).toBe('20260042');
    expect(serial().getByTestId('reading-r-serial-field-input')).toHaveProp('value', '20260042');
  });

  test('a number reading given 12a says Numbers only. and saves nothing', async () => {
    const f = seeded();
    await mountJob(f.services, 'FF-20');
    const open = () => within(within(onTop('FF-20')).getByTestId('reading-r-open'));
    fireEvent.changeText(open().getByTestId('reading-r-open-field'), '12a');
    fireEvent.press(open().getByTestId('reading-r-open-save'));
    expect(open().getByText('Numbers only.')).toBeTruthy();
    expect(row(f, 'r-open')?.value).toBeNull();
    expect(sent(f, 'r-open')).toEqual([]);
    // typing again clears it; a number saves with its unit
    fireEvent.changeText(open().getByTestId('reading-r-open-field'), '120');
    expect(open().queryByText('Numbers only.')).toBeNull();
    fireEvent.press(open().getByTestId('reading-r-open-save'));
    expect(row(f, 'r-open')).toMatchObject({ value: '120', unit: 'kWh', value_text: null });
  });

  test('the range is plain: Expected 0–99,999', async () => {
    const f = seeded();
    await mountJob(f.services, 'FF-20');
    const open = within(within(onTop('FF-20')).getByTestId('reading-r-open'));
    expect(open.getByText('Expected 0–99,999')).toBeTruthy();
  });
});
