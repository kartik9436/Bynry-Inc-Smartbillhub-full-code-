/**
 * MQ-033 (`CR-192-BRC10` task 12) — the utility's own questions, asked on the
 * phone after the figure, under the real navigation and the real outbox.
 *
 * PO, verbatim (decision log 2026-10-24, *"SUMMARY CONFIRMED"*): **asked when**
 * (every reading · out of range · can't read · once per stop), **follow-ups**
 * (an answer reveals another question or requires a photo); answers travel
 * inside the reading's own item. A route with no format reads exactly as today.
 *
 * The questions are `support/serverReadFormat.json`'s — the server's own shape,
 * locked by `06-backend/tests/test_mq033_phone_shape.py`.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import type { TenantDb } from '../../../src/db/database';
import { fromJson } from '../../../src/db/json';
import * as outboxQ from '../../../src/db/queries/outbox';
import * as readFormatQ from '../../../src/db/queries/readFormat';
import * as settingsQ from '../../../src/db/queries/settings';
import { scoped } from '../../../src/db/scoped';
import { askedQuestions, type ReadQuestion, visibleQuestions } from '../../../src/screens/reads/readFormat';
import { LIST_KEYS } from '../../../src/screens/reads/records';
import { applyBatchAnswer } from '../../../src/sync/receipts';
import { batchAnswerFromReads, routeItemFromWire } from '../../../src/sync/routeReads';
import type { ServedReadFormatVersion } from '../../../src/sync/routes';
import server from '../../sync/support/serverReadFormat.json';
import { NOW, RAY, SEEDED_REASONS, seedMapleHeights } from './fixture';
import { mountReads } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

const VERSION = { ...(server.version as unknown as ServedReadFormatVersion), read_format: { ...server.version.read_format, service: 'water' } };
const QUESTIONS = VERSION.questions as unknown as ReadQuestion[];

type App = Awaited<ReturnType<typeof mountReads>>;

function withFormat(db: TenantDb) {
  seedMapleHeights(db);
  settingsQ.set(db, LIST_KEYS.cantRead, SEEDED_REASONS, NOW);
  readFormatQ.putVersion(db, VERSION, NOW);
  readFormatQ.setRouteFormats(scoped(db, RAY), 'wlk-07', [{ service: 'water', source: 'cycle', version_id: VERSION.id }]);
}

function type(page: ReturnType<typeof within>, digits: string) {
  for (const d of digits) fireEvent.press(page.getByTestId(`keypad-${d}`));
}

async function press(id: string) {
  await act(async () => {
    fireEvent.press(screen.getByTestId(id));
  });
}

const reads = (app: App) => outboxQ.listMine(scoped(app.db, RAY), { limit: 100 }).filter((o) => o.kind === 'route_read');
const payloadOf = (row: outboxQ.OutboxRow) => fromJson<Record<string, unknown>>(row.payload)!;
const shown = () => screen.queryAllByTestId(/^question-[a-z_]+$/).map((n) => String(n.props.testID).slice('question-'.length));

async function saveFigure(app: App, readId: string, figure: string) {
  const page = within((await app.open('RW-09', { readId }))!);
  type(page, figure);
  await act(async () => {
    fireEvent.press(page.getByTestId('door-RW-13'));
  });
}

describe('which questions are asked (pure)', () => {
  const ctx = { status: 'read' as const, outOfRange: false, answeredAtStop: new Set<string>() };
  test('every reading — a reading with a figure', () => {
    expect(askedQuestions(QUESTIONS, ctx).map((q) => q.key)).toEqual(['seal_intact', 'photo_of_the_seal', 'meter_condition', 'gate_code']);
  });
  test('out of range — only when the range check flags it or the reader accepted it', () => {
    expect(askedQuestions(QUESTIONS, { ...ctx, status: 'read_with_problem', outOfRange: true }).map((q) => q.key)).toContain('why_so_high');
    expect(askedQuestions(QUESTIONS, ctx).map((q) => q.key)).not.toContain('why_so_high');
  });
  test('can’t read — only a could-not-read, and never the figure questions', () => {
    expect(askedQuestions(QUESTIONS, { ...ctx, status: 'could_not_read' }).map((q) => q.key)).toEqual(['why_not_read', 'gate_code']);
  });
  test('once per stop — not asked again where the stop already answered it today', () => {
    expect(askedQuestions(QUESTIONS, { ...ctx, answeredAtStop: new Set(['gate_code']) }).map((q) => q.key)).not.toContain('gate_code');
  });
  test('a follow-up is shown only for the answer it follows', () => {
    const asked = askedQuestions(QUESTIONS, ctx);
    expect(visibleQuestions(asked, {}).map((q) => q.key)).not.toContain('photo_of_the_seal');
    expect(visibleQuestions(asked, { seal_intact: true }).map((q) => q.key)).not.toContain('photo_of_the_seal');
    expect(visibleQuestions(asked, { seal_intact: false }).map((q) => q.key)).toContain('photo_of_the_seal');
  });
});

describe('RW-09 with a format', () => {
  test('after the figure, the every-reading and once-per-stop questions — in the utility’s own words', async () => {
    const app = await mountReads({ seed: withFormat });
    await saveFigure(app, 'r0471', '52410');
    expect(screen.getByTestId('read-questions')).toBeTruthy();
    expect(shown()).toEqual(['seal_intact', 'meter_condition', 'gate_code']);
    expect(screen.getByText('Seal intact?')).toBeTruthy();
    expect(screen.getByText('Look at the wire seal on the ring.')).toBeTruthy();
    // Nothing saved yet: the answers go IN the reading's item.
    expect(reads(app)).toHaveLength(0);
    app.unmount();
  });

  test('required answers block Done with a warning; a No reveals the photo follow-up; Done sends one item with the answers', async () => {
    const app = await mountReads({ seed: withFormat });
    await saveFigure(app, 'r0471', '52410');
    expect(screen.getByTestId('questions-done')).toBeDisabled();
    expect(screen.getByTestId('questions-required')).toHaveTextContent('Answer 2 more questions.');

    await press('question-seal_intact-answer-no');
    expect(shown()).toContain('photo_of_the_seal');
    expect(screen.getByTestId('questions-required')).toHaveTextContent('Answer 2 more questions.');
    await act(async () => {
      fireEvent.changeText(screen.getByTestId('question-gate_code-answer-input'), '4417');
    });
    expect(screen.getByTestId('questions-required')).toHaveTextContent('Answer 1 more question.');
    await press('question-photo_of_the_seal-take');
    expect(screen.queryByTestId('questions-required')).toBeNull();
    expect(screen.getByTestId('questions-done')).not.toBeDisabled();
    await press('questions-done');

    expect(app.current()).toBe('RW-13');
    const [row] = reads(app);
    const p = payloadOf(row!);
    expect(p.read_format_version_id).toBe(VERSION.id);
    const photoIds = p.photo_ids as string[];
    expect(photoIds).toHaveLength(1);
    expect(p.answers).toEqual([
      { question_key: 'seal_intact', value: false },
      { question_key: 'photo_of_the_seal', photo_id: photoIds[0] },
      { question_key: 'gate_code', value: '4417' },
    ]);
    // The photo answer travels the route-photo path: declared as its own `photo` item.
    const declared = outboxQ.listMine(scoped(app.db, RAY), { limit: 100 }).filter((o) => o.kind === 'photo');
    expect(declared.map((o) => payloadOf(o).photo_id)).toEqual(photoIds);
    // On the wire, the same two keys and the same answer form as the server's contract.
    const wire = routeItemFromWire(
      { key: row!.id, kind: 'route_read', seq: row!.seq, captured_at: row!.captured_at, payload: p },
      'wlk-07',
    );
    expect(wire.read_format_version_id).toBe(VERSION.id);
    for (const a of wire.answers as Array<Record<string, unknown>>) {
      expect(Object.keys(a).sort()).toEqual(Object.keys(server.reading_item.answers.find((x) => x.question_key === a.question_key)!).sort());
    }
    app.unmount();
  });

  test('once per stop: the next meter at the same stop is not asked the gate code again', async () => {
    const app = await mountReads({ seed: withFormat });
    await saveFigure(app, 'r0471', '52410');
    await press('question-seal_intact-answer-yes');
    await act(async () => {
      fireEvent.changeText(screen.getByTestId('question-gate_code-answer-input'), '4417');
    });
    await press('questions-done');
    await saveFigure(app, 'r0472', '30500');
    expect(shown()).toEqual(['seal_intact', 'meter_condition']);
    app.unmount();
  });

  test('the receipt’s needs_review is said on the reading, and blocks nothing', async () => {
    const app = await mountReads({ seed: withFormat });
    await saveFigure(app, 'r0471', '52410');
    await press('question-seal_intact-answer-yes');
    await act(async () => {
      fireEvent.changeText(screen.getByTestId('question-gate_code-answer-input'), '4417');
    });
    await press('questions-done');
    expect(screen.queryByTestId('kept-answers-flagged')).toBeNull();
    const sent = outboxQ.listMine(scoped(app.db, RAY), { limit: 100 });
    const wire = sent.map((o) => ({ key: o.id, kind: o.kind, seq: o.seq, captured_at: o.captured_at, payload: payloadOf(o) }));
    const answer = batchAnswerFromReads(wire, {
      items: sent.map((o) =>
        o.kind === 'route_read'
          ? { key: o.id, result: 'accepted', outcome: 'posted', answers: { ...server.receipt_answers, needs_review: true, issues: [{ question_key: 'meter_condition', issue: 'not_an_option' }] } }
          : { key: o.id, result: 'accepted', outcome: 'recorded' },
      ) as never,
    });
    applyBatchAnswer(app.db, sent, answer, new Date(NOW));
    await app.open('RW-06', { stopId: 's1318' });
    await app.open('RW-13', { readId: 'r0471' });
    expect(screen.getByTestId('kept-answers-flagged')).toHaveTextContent('The office will check the answers.');
    app.unmount();
  });

  test('out of range: accepting anyway asks the out-of-range question', async () => {
    const app = await mountReads({ seed: withFormat });
    const page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    type(page, '71400');
    await act(async () => {
      fireEvent.press(page.getByTestId('door-RW-15'));
    });
    await act(async () => {
      fireEvent.press(within(screen.getAllByTestId('screen-RW-15').at(-1)!).getByTestId('door-RW-06'));
    });
    expect(shown()).toContain('why_so_high');
    app.unmount();
  });

  test('can’t read: the can’t-read question, and not the figure ones', async () => {
    const app = await mountReads({ seed: withFormat });
    const page = within((await app.open('RW-17', { readId: 'r0471' }))!);
    await act(async () => {
      fireEvent.press(page.getByTestId('reasons-dog'));
    });
    await act(async () => {
      fireEvent.press(page.getByTestId('door-RW-06'));
    });
    expect(shown()).toEqual(['why_not_read', 'gate_code']);
    app.unmount();
  });
});

describe('a route with no format', () => {
  test('saves straight through, exactly as today, and the item carries no answers', async () => {
    const app = await mountReads();
    await saveFigure(app, 'r0471', '52410');
    expect(screen.queryByTestId('read-questions')).toBeNull();
    expect(app.current()).toBe('RW-13');
    const [row] = reads(app);
    const wire = routeItemFromWire({ key: row!.id, kind: 'route_read', seq: row!.seq, captured_at: row!.captured_at, payload: payloadOf(row!) }, 'wlk-07');
    expect(wire).not.toHaveProperty('read_format_version_id');
    expect(wire).not.toHaveProperty('answers');
    app.unmount();
  });
});

// DEF-FLD-10598 — the route names a version the phone could not download.
// The reading still saves (never held up for want of a form), but RW-05
// says so instead of reading silently without the questions.
describe('RW-05 when the route’s form did not download (DEF-FLD-10598)', () => {
  function namesAMissingVersion(db: TenantDb) {
    seedMapleHeights(db);
    readFormatQ.setRouteFormats(scoped(db, RAY), 'wlk-07', [{ service: 'water', source: 'cycle', version_id: 'rfv-not-on-this-phone' }]);
  }

  test('a version the phone does not hold → “Form not downloaded.”', async () => {
    const app = await mountReads({ seed: namesAMissingVersion });
    const page = within((await app.open('RW-05', { routeId: 'wlk-07' }))!);
    expect(page.getByTestId('walk-no-form')).toHaveTextContent('Form not downloaded.');
    app.unmount();
  });

  test('the version held → no notice', async () => {
    const app = await mountReads({ seed: withFormat });
    const page = within((await app.open('RW-05', { routeId: 'wlk-07' }))!);
    expect(page.queryByTestId('walk-no-form')).toBeNull();
    app.unmount();
  });

  test('no format at all → no notice', async () => {
    const app = await mountReads();
    const page = within((await app.open('RW-05', { routeId: 'wlk-07' }))!);
    expect(page.queryByTestId('walk-no-form')).toBeNull();
    app.unmount();
  });
});
