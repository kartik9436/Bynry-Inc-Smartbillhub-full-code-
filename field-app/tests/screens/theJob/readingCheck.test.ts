/**
 * @jest-environment node
 *
 * R11 as a function (US-FLD-009 TC-1…TC-3). Proved red (law 7): with
 * `judgeReading` returning `{ kind: 'save', flagged: false }` for any second
 * entry, TC-2 failed (`flagged` false where true was expected) and so did
 * *"a different out-of-range second figure is asked for again"*.
 */
import { compareDecimal, inRange, judgeReading, parseTyped } from '../../../src/screens/theJob/readingCheck';

const RANGE = { min: '40000', max: '50000' };

test('TC-1: 48,200 gal inside 40,000–50,000 is accepted, not flagged', () => {
  expect(judgeReading('48200', RANGE, null)).toEqual({ kind: 'save', value: '48200', flagged: false });
});

test('TC-2: 58,000 asks to be entered again; the same 58,000 again is saved and flagged', () => {
  const first = judgeReading('58000', RANGE, null);
  expect(first).toEqual({ kind: 'again', value: '58000' });
  expect(judgeReading('58000.00', RANGE, '58000')).toEqual({ kind: 'save', value: '58000.00', flagged: true });
});

test('TC-3 (negative): 58,000 then 48,200 — the first was a typo, no flag is raised', () => {
  expect(judgeReading('48200', RANGE, '58000')).toEqual({ kind: 'save', value: '48200', flagged: false });
});

test('a different out-of-range second figure is asked for again, never flagged on the first', () => {
  expect(judgeReading('59000', RANGE, '58000')).toEqual({ kind: 'again', value: '59000' });
});

test('no range (a first reading on a new meter) is never flagged', () => {
  expect(judgeReading('124', { min: null, max: null }, null)).toEqual({ kind: 'save', value: '124', flagged: false });
});

test('figures are compared as decimal strings, never floats', () => {
  expect(compareDecimal('48210.50', '48210.5')).toBe(0);
  expect(compareDecimal('9', '10')).toBe(-1);
  expect(compareDecimal('-1', '0')).toBe(-1);
  expect(compareDecimal('0.3', '0.30000000000000004'.slice(0, 8))).toBe(0);
  expect(inRange('50000', '40000', '50000')).toBe(true);
  expect(inRange('50000.01', '40000', '50000')).toBe(false);
});

test('what was typed: grouping dropped, junk refused', () => {
  expect(parseTyped('58,000')).toBe('58000');
  expect(parseTyped('00,124')).toBe('00124');
  expect(parseTyped('12.5')).toBe('12.5');
  expect(parseTyped('')).toBeNull();
  expect(parseTyped('1e3')).toBeNull();
});
