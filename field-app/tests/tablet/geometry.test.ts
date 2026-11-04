/**
 * R121 / R122 as arithmetic: every frame's usable width at the design board,
 * and THE WIDTH CHECK — at 1024, 1194 and 1366 landscape and 768 and 834
 * portrait, no fixed child may leave its flexible sibling under 260.
 *
 * Red proof (law 7), kept as a test so it stays proved: the frames AS DRAWN
 * (`drawnFrame`, no fallback) fail the check at portrait — the list pane
 * leaves the detail 168 at 768 and 234 at 834, the context pane leaves the
 * content 208 at 768 — and the check names exactly those three. The frames AS
 * MOUNTED (`resolveFrame`) pass at every width, because a frame that cannot
 * keep 260 collapses to one pane.
 */
import {
  CHECK_WIDTHS,
  drawnFrame,
  findBrokenPanes,
  fitColumns,
  FRAME_IDS,
  type FrameGeometry,
  GEOMETRY,
  listPaneWidth,
  resolveFrame,
} from '../../src/tablet/geometry';

const ALL_WIDTHS = [...CHECK_WIDTHS.landscape, ...CHECK_WIDTHS.portrait];

function table(build: (frame: (typeof FRAME_IDS)[number], w: number) => FrameGeometry): FrameGeometry[] {
  return FRAME_IDS.flatMap((frame) => ALL_WIDTHS.map((w) => build(frame, w)));
}

describe('R122: every frame states its usable width (at the 1024 board)', () => {
  test.each([
    ['T4', 764],
    ['T3', 464],
    ['T2', 424],
  ] as const)('%s leaves %i', (frame, usable) => {
    expect(drawnFrame(frame, 1024).usable).toBe(usable);
    expect(resolveFrame(frame, 1024).usable).toBe(usable);
  });

  test('the sidebar is the shell’s 220 and the gutters are R121’s 40', () => {
    expect(GEOMETRY.sidebar).toBe(220);
    expect(2 * GEOMETRY.gutter).toBe(40);
  });

  test('T2’s list pane stays within 320–360, at 340 on the board', () => {
    expect(listPaneWidth(1024)).toBe(340);
    for (const w of [600, 768, 834, 1024, 1194, 1366, 2000]) {
      expect(listPaneWidth(w)).toBeGreaterThanOrEqual(320);
      expect(listPaneWidth(w)).toBeLessThanOrEqual(360);
    }
  });
});

describe('R122: the width check', () => {
  test('the frames as MOUNTED leave no flexible pane under 260, at any of the five widths', () => {
    const resolved = table(resolveFrame);
    const report = resolved.map(
      (g) => `${g.frame}@${g.windowWidth}: ${g.fixed ? `fixed ${g.fixed.width}` : g.collapsed ? 'collapsed' : 'one pane'} → usable ${g.usable}`,
    );
    console.log(`R122 width check, ${resolved.length} frame × width pairs:\n${report.join('\n')}`);
    expect(resolved).toHaveLength(FRAME_IDS.length * 5);
    expect(findBrokenPanes(resolved)).toEqual([]);
  });

  test('RED PROOF: the frames as DRAWN break at portrait, and the check names exactly where', () => {
    const broken = findBrokenPanes(table((f, w) => drawnFrame(f, w)));
    expect(broken.map((b) => `${b.frame}@${b.windowWidth}=${b.usable}`).sort()).toEqual(
      ['T2@768=168', 'T2@834=234', 'T3@768=208'].sort(),
    );
  });

  test('the check fails a fixed child too wide for the board itself', () => {
    // A 560 context pane at 1024 leaves 204; one at 500 leaves 264 and passes.
    expect(findBrokenPanes([drawnFrame('T3', 1024, 560)])).toEqual([
      { frame: 'T3', windowWidth: 1024, fixedWidth: 780, usable: 204 },
    ]);
    expect(findBrokenPanes([drawnFrame('T3', 1024, 500)])).toEqual([]);
  });

  test('landscape keeps every two-pane frame split; portrait collapses only where it must', () => {
    for (const w of CHECK_WIDTHS.landscape) {
      expect(resolveFrame('T2', w).fixed?.kind).toBe('list');
      expect(resolveFrame('T3', w).fixed?.kind).toBe('context');
    }
    expect(resolveFrame('T2', 768).collapsed).toBe(true);
    expect(resolveFrame('T2', 834).collapsed).toBe(true);
    expect(resolveFrame('T3', 768).collapsed).toBe(true);
    expect(resolveFrame('T3', 834).collapsed).toBe(false);
    expect(resolveFrame('T3', 834).usable).toBe(274);
  });

  test('T1 is a centred column that never meets the sidebar', () => {
    expect(resolveFrame('T1', 1024).sidebar).toBe(0);
    expect(resolveFrame('T1', 1024).usable).toBe(GEOMETRY.centredColumn);
    expect(resolveFrame('T1', 600).usable).toBe(600 - 2 * GEOMETRY.gutter);
  });
});

describe('fitColumns — two columns do not fit in 464 (R121)', () => {
  test.each([
    [464, 2, 1],
    [424, 2, 1],
    [764, 2, 2],
    [508, 2, 1], // T4 held upright: the readings grid drops to one column
    [1106, 4, 4],
  ])('usable %i, wanting %i → %i', (usable, wanted, got) => {
    expect(fitColumns(usable, GEOMETRY.gutter, wanted)).toBe(got);
  });
});
