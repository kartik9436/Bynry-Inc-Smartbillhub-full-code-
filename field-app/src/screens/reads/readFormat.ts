/**
 * Which of the utility's own questions a reading asks, and what it sends —
 * MQ-033 (`CR-192-BRC10` task 12). Pure: no store, no screen.
 *
 * THE RULING, VERBATIM (decision log 2026-10-24, *"MQ-033 read formats:
 * SUMMARY CONFIRMED, ALL THREE QUESTION BEHAVIOURS IN THE FIRST RELEASE"*):
 * *"this is correct"* — to: each question has **asked when** (every reading ·
 * out of range · can't read · once per stop), **follow-ups** (an answer
 * reveals another question or requires a photo) and raise a work order;
 * answers travel inside the reading's own item, are checked on the server
 * against the same version, and never cause a reading to be dropped.
 *
 * READ THE SAME WAY AS THE SERVER (`apps/metering/read_formats.record_answers`,
 * judgments 2–5 of the server lane), so a phone that asks exactly these never
 * sends an answer the server flags `not_asked` or `not_shown`:
 *   every_reading — a reading with a FIGURE (read, or read with a problem).
 *   out_of_range  — a figure the phone's expected-range check warned about, or
 *                   one the reader accepted anyway (R80). The server judges by
 *                   its engine; a disagreement is flagged there, never refused.
 *   cant_read     — a reading marked could-not-read.
 *   once_per_stop — any reading, but not again at a stop where another reading
 *                   already answered it on the same capture day.
 *   show_if       — a follow-up is shown only when the EARLIER question it
 *                   names is itself shown and holds that answer; its answer is
 *                   dropped from the item when it is not shown.
 *
 * The questions' labels, help and options are the UTILITY'S OWN WORDS: shown
 * verbatim, never translated (they are not ours to translate).
 */
import type { CameraShot } from './ports';

export type ReaderStatus = 'read' | 'could_not_read' | 'read_with_problem';

export interface ReadQuestion {
  key: string;
  seq: number;
  label: string;
  help_text: string | null;
  data_type: string;
  options: string[] | null;
  is_required: boolean;
  asked_when: string;
  show_if: { question_key: string; answer: unknown } | null;
}

/** What a reader has given so far, by question key. A photo answer is the shot, until it is saved. */
export type AnswerValue = string | boolean | string[] | CameraShot;
export type Answers = Record<string, AnswerValue | undefined>;

export interface AskContext {
  status: ReaderStatus;
  outOfRange: boolean;
  /** `once_per_stop` keys another reading at this stop answered today. */
  answeredAtStop: ReadonlySet<string>;
}

/** On the wire (`field_reads.sync_reads`): `{question_key, value}` or `{question_key, photo_id}`. */
export type WireAnswer = { question_key: string; value: string | boolean | string[] } | { question_key: string; photo_id: string };

const tookFigure = (s: ReaderStatus) => s === 'read' || s === 'read_with_problem';

export function askedQuestions(questions: readonly ReadQuestion[], ctx: AskContext): ReadQuestion[] {
  return questions.filter((q) => {
    if (q.asked_when === 'every_reading') return tookFigure(ctx.status);
    if (q.asked_when === 'out_of_range') return tookFigure(ctx.status) && ctx.outOfRange;
    if (q.asked_when === 'cant_read') return ctx.status === 'could_not_read';
    if (q.asked_when === 'once_per_stop') return !ctx.answeredAtStop.has(q.key);
    return false; // a kind this build does not know is not asked
  });
}

export const isPhoto = (q: ReadQuestion) => q.data_type === 'photo';

function isShot(v: AnswerValue | undefined): v is CameraShot {
  return typeof v === 'object' && v !== null && !Array.isArray(v) && 'localPath' in v;
}

const NUMBER = /^-?\d+(\.\d+)?$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

function validDate(text: string): boolean {
  if (!DATE.test(text)) return false;
  const d = new Date(`${text}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === text;
}

/** Whether a typed number or date is in a form the server can read; anything else is not yet an answer. */
export function malformed(q: ReadQuestion, v: AnswerValue | undefined): boolean {
  if (typeof v !== 'string' || !v.trim()) return false;
  if (q.data_type === 'number') return !NUMBER.test(v.trim());
  if (q.data_type === 'date') return !validDate(v.trim());
  return false;
}

/** A lawful answer was given. */
export function answered(q: ReadQuestion, v: AnswerValue | undefined): boolean {
  if (v === undefined) return false;
  if (isPhoto(q)) return isShot(v);
  if (typeof v === 'boolean') return true;
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === 'string') return v.trim().length > 0 && !malformed(q, v);
  return false;
}

/** `answer_matches` on the server: a list answer matches when it CONTAINS it. */
function matches(q: ReadQuestion, v: AnswerValue | undefined, expected: unknown): boolean {
  if (!answered(q, v) || expected === null || expected === undefined) return false;
  if (q.data_type === 'multi_select') return Array.isArray(v) && v.includes(String(expected));
  if (q.data_type === 'boolean') return v === (expected === true || String(expected).toLowerCase() === 'true');
  if (q.data_type === 'number') return Number(v) === Number(expected);
  return String(v).trim().toLowerCase() === String(expected).trim().toLowerCase();
}

/** The asked questions a reader sees now: a follow-up only when what it follows holds its answer. */
export function visibleQuestions(asked: readonly ReadQuestion[], answers: Answers): ReadQuestion[] {
  const out: ReadQuestion[] = [];
  const shown = new Map<string, ReadQuestion>();
  for (const q of [...asked].sort((a, b) => a.seq - b.seq)) {
    if (q.show_if) {
      const parent = shown.get(q.show_if.question_key);
      if (!parent || !matches(parent, answers[parent.key], q.show_if.answer)) continue;
    }
    shown.set(q.key, q);
    out.push(q);
  }
  return out;
}

/** Required questions shown and not yet answered — they block *Done*. */
export function missingRequired(visible: readonly ReadQuestion[], answers: Answers): ReadQuestion[] {
  return visible.filter((q) => q.is_required && !answered(q, answers[q.key]));
}

/**
 * The item's answers, in question order: only questions shown and answered.
 * A photo answer names the photograph's id, minted when the reading is
 * captured (`photoIdOf`), so it travels the route-photo path like any other.
 */
export function toWire(visible: readonly ReadQuestion[], answers: Answers, photoIdOf: (key: string) => string | null): WireAnswer[] {
  const out: WireAnswer[] = [];
  for (const q of visible) {
    const v = answers[q.key];
    if (!answered(q, v)) continue;
    if (isPhoto(q)) {
      const id = photoIdOf(q.key);
      if (id) out.push({ question_key: q.key, photo_id: id });
    } else if (typeof v === 'string') {
      out.push({ question_key: q.key, value: v.trim() });
    } else if (typeof v === 'boolean' || Array.isArray(v)) {
      out.push({ question_key: q.key, value: v });
    }
  }
  return out;
}

/** The photographs the answers hold, in question order. */
export function answerShots(visible: readonly ReadQuestion[], answers: Answers): Array<{ key: string; shot: CameraShot }> {
  return visible.flatMap((q) => {
    const v = answers[q.key];
    return isPhoto(q) && isShot(v) ? [{ key: q.key, shot: v }] : [];
  });
}

/** The capture day of an ISO instant, on the phone's own calendar. */
export function captureDay(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
