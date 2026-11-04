/**
 * The frame map against its source: `08-screen-layouts.md` §2.3, one row per
 * tablet board. Every board's frame code (T1–T4) is parsed out of the
 * document and compared with `FRAME_OF`, so the table and the document cannot
 * drift apart silently — and the parse prints how many rows it read, so a
 * moved or renamed document reads as "0 rows", never as a pass (law 7).
 */
import { readFileSync } from 'fs';
import { resolve } from 'path';

import { SCREEN_IDS, type ScreenId } from '../../src/navigation/screens';
import { contextFamilyOf, FRAME_OF, SHAPE_CHANGING } from '../../src/tablet/frameMap';
import { type FrameId } from '../../src/tablet/geometry';

const DOC = resolve(__dirname, '../../../04-docs/05-modules/18-field-app/08-screen-layouts.md');

function boardsFromDoc(): Map<string, FrameId> {
  const src = readFileSync(DOC, 'utf8');
  const section = src.slice(src.indexOf('### 2.3'));
  const rows = new Map<string, FrameId>();
  for (const m of section.matchAll(/^\| \*\*((?:FF|RW)-\d{2}) T [^|]*\*\* \|.*\| (T[1-4]) [^|]*\|\s*$/gm)) {
    rows.set(m[1] as string, m[2] as FrameId);
  }
  return rows;
}

test('the document gives a frame for 92 tablet boards, and FRAME_OF agrees with every one', () => {
  const doc = boardsFromDoc();
  console.log(`frameMap: ${doc.size} tablet rows read from 08-screen-layouts.md`);
  expect(doc.size).toBe(92);
  const disagree = [...doc].filter(([id, frame]) => FRAME_OF[id as ScreenId] !== frame);
  expect(disagree).toEqual([]);
});

test('every registered screen has a frame (SWITCH included, which has no board)', () => {
  expect(SCREEN_IDS.filter((id) => FRAME_OF[id] == null)).toEqual([]);
  expect(Object.keys(FRAME_OF).sort()).toEqual([...SCREEN_IDS].sort());
  expect(FRAME_OF.SWITCH).toBe('T1');
});

test('the counts the document’s §1 table states: T1 11 · T2 31 · T3 34 · T4 16', () => {
  const boards = SCREEN_IDS.filter((id) => id !== 'SWITCH');
  const count = (f: FrameId) => boards.filter((id) => FRAME_OF[id] === f).length;
  expect([count('T1'), count('T2'), count('T3'), count('T4')]).toEqual([11, 31, 34, 16]);
});

test('the eight screens that change shape (T-28) are eight distinct, framed, two-pane-or-wide screens', () => {
  expect(new Set(SHAPE_CHANGING).size).toBe(8);
  for (const id of SHAPE_CHANGING) expect(FRAME_OF[id]).not.toBe('T1');
});

test('a T3 context pane is the route’s on a reading screen and the job’s otherwise', () => {
  expect(contextFamilyOf('RW-09')).toBe('route');
  expect(contextFamilyOf('FF-25')).toBe('job');
});
