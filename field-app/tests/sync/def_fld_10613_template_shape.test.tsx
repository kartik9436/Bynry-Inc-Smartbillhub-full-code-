/**
 * DEF-FLD-10613 (MQ-034) — Raise > Pick a template showed
 * `{id=01a07f62-…, code=water, name=Water} · 7 steps · …` on every card.
 *
 * The server's catalogue row carries `service` (and `job_type`) as an OBJECT;
 * the phone typed it `string`, stored it into a TEXT column (Android's SQLite
 * kept the Map's `toString`) and FF-62 printed it first. Every phone test seeded
 * templates with `service: 'Water'`, so none ever met the real row.
 *
 * `support/serverTemplate.json` IS the real row — locked to the server by
 * `06-backend/tests/test_def_fld_10613_template_shape.py` — and every case here
 * downloads it through the REAL `downloadTemplates` and reads it back through
 * the real queries and the real screen.
 */
import { fireEvent, waitFor, within } from '@testing-library/react-native';

import * as searchQ from '../../src/db/queries/templateSearch';
import * as templatesQ from '../../src/db/queries/workOrderTemplates';
import { createFieldI18n } from '../../src/i18n/i18n';
import { countsLine } from '../../src/screens/raise/PickTemplateScreen';
import { downloadTemplates } from '../../src/sync/extras';
import type { FieldApi, WirePage, WireTemplate } from '../../src/sync/fieldApi';
import { makeWave, openScreen } from '../screens/onSite/fixture';
import serverTemplate from './support/serverTemplate.json';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

// The fixture IS a wire row: if `WireTemplate` drifts from the server's real
// shape again, this line stops compiling.
const ROW: WireTemplate = serverTemplate;
const ID = ROW.id;
/** What Android's SQLite stored before the fix: the object's `toString`. */
const ANDROID_MAP = '{id=01a07f62-3c4d-4e5f-8a9b-0c1d2e3f4a5b, code=water, name=Water}';
const CARD = 'Water · 7 steps · 3 safety checks · 3 readings';

function catalogue(rows: WireTemplate[]): FieldApi {
  return {
    templates: (_page: number): Promise<WirePage<WireTemplate>> => Promise.resolve({ count: rows.length, next: null, results: rows }),
  } as unknown as FieldApi;
}

const { i18n } = createFieldI18n({ language: 'en' });
const t = i18n.t.bind(i18n) as unknown as Parameters<typeof countsLine>[0];

describe('the catalogue row as the server sends it', () => {
  test('download stores the service NAME, never the object', async () => {
    const w = makeWave();
    await downloadTemplates(w.db, catalogue([ROW]), { clock: w.clock });
    const stored = w.db.ref.get<{ service: string | null }>('SELECT service FROM work_order_templates WHERE id = :id', { id: ID });
    expect(stored?.service).toBe('Water');
    const tpl = searchQ.getPublished(w.db, ID)!;
    expect(countsLine(t, tpl)).toBe(CARD);
  });

  test('FF-62 shows "Water · 7 steps · 3 safety checks · 3 readings", never "{id="', async () => {
    const w = makeWave();
    await downloadTemplates(w.db, catalogue([ROW]), { clock: w.clock });
    const app = await openScreen(w, 'FF-62', { carriedFrom: 'wo-4824' });
    const page = within(app.onTop());
    fireEvent.changeText(page.getByLabelText('Search templates'), 'Meter exchange');
    await waitFor(() => expect(within(app.onTop()).getByTestId(`tpl-${ID}`)).toBeTruthy());
    const card = within(app.onTop()).getByTestId(`tpl-${ID}`);
    expect(within(card).getByText(CARD)).toBeTruthy();
    expect(within(app.onTop()).queryByText(/\{id=|code=|01a07f62/)).toBeNull();
  });

  test('a row stored wrong before the fix is replaced on the next download', async () => {
    const w = makeWave();
    w.db.ref.run(
      `INSERT INTO work_order_templates (id, name, version, service, published, step_count, safety_count, reading_count, updated_at)
       VALUES (:id, 'Meter exchange', '2', :bad, 1, 7, 3, 3, '2026-10-20T10:00:00')`,
      { id: ID, bad: ANDROID_MAP },
    );
    await downloadTemplates(w.db, catalogue([ROW]), { clock: w.clock });
    const stored = w.db.ref.get<{ service: string | null }>('SELECT service FROM work_order_templates WHERE id = :id', { id: ID });
    expect(stored?.service).toBe('Water');
  });

  test('a wrong row the catalogue no longer offers is read clean, so it never shows', () => {
    const w = makeWave();
    const stale: [string, string][] = [
      ['gone-map', ANDROID_MAP],
      ['gone-json', JSON.stringify(serverTemplate.service)],
    ];
    for (const [id, bad] of stale) {
      w.db.ref.run(
        `INSERT INTO work_order_templates (id, name, version, service, published, step_count, safety_count, reading_count, updated_at)
         VALUES (:id, :id, '1', :bad, 1, 7, 3, 3, '2026-10-20T10:00:00')`,
        { id, bad },
      );
      expect(searchQ.getPublished(w.db, id)?.service).toBe('Water');
      expect(countsLine(t, searchQ.getPublished(w.db, id)!)).toBe(CARD);
    }
    expect(searchQ.searchPublished(w.db, 'gone', { limit: 10 }).map((r) => r.service)).toEqual(['Water', 'Water']);
    expect(templatesQ.listPublished(w.db, { limit: 100 }).every((r) => r.service === null || !r.service.includes('{'))).toBe(true);
  });

  test('the display guard prints only plain text', () => {
    const base = searchQ.getPublished(makeWave().db, 'tpl-leak')!;
    // A value that is not a plain string never reaches the card as text.
    expect(countsLine(t, { ...base, service: { id: 'x', code: 'water', name: 'Water' } as unknown as string })).toBe(
      'Water · 4 steps · 3 safety checks · 1 reading',
    );
    expect(countsLine(t, { ...base, service: { id: 'x' } as unknown as string })).toBe('4 steps · 3 safety checks · 1 reading');
    expect(countsLine(t, { ...base, service: '' })).toBe('4 steps · 3 safety checks · 1 reading');
    expect(templatesQ.nameOf({ id: 'x', code: 'water' })).toBe('water');
    expect(templatesQ.nameOf(null)).toBeNull();
    expect(templatesQ.nameOf('Gas')).toBe('Gas');
  });
});
