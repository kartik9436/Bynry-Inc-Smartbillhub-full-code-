/**
 * T-53 — THE ACCESSIBILITY PASS, over EVERY screen id the app routes (the
 * table in `navigation/screens.ts`, counted, so a screen added later is in it
 * without anyone remembering), each opened by its ADDRESS inside the real app
 * root with a real store, in all three themes, with the text at 200%: the
 * handset's font scale at 2 (`useWindowDimensions().fontScale`) AND the app's
 * own *Bigger text* on.
 *
 * Read off the RENDERED tree, per screen, not off the tokens:
 *   1. CONTRAST — every piece of text against the background it actually sits
 *      on (the nearest ancestor that paints one): 4.5:1, or 3:1 for large text
 *      (24pt, or 18.66pt bold); the brand colour as a MARK at 3:1 (R100, where
 *      it is not also the text colour). `tests/theme/contrast.test.ts` proves the token
 *      PAIRS; this proves the screens only ever draw those pairs.
 *   2. SCREEN READER — every control (button, link, checkbox, radio, switch,
 *      tab…) has a name, and every text box has a label (portal question 3).
 *   3. TEXT AT 200% — no text refuses to scale (`allowFontScaling={false}`, a
 *      `maxFontSizeMultiplier` under 2); no text is clipped to nothing (a
 *      zero-sized box); no WORDS sit in a box of fixed height too short for
 *      one line of them at double size; and every control is still REACHABLE —
 *      inside a scrolling body, or in fixed bars that at 200% still take less
 *      than 60% of an 844pt phone. (Icon glyphs and initials in fixed circles
 *      that outgrow the circle are COUNTED and printed, not failed.)
 *   4. A HEADING — every screen names itself with at least one header, either
 *      its own title or the navigation header's (portal question 4).
 * The sweep COUNTS what it checked and prints it; every count has a floor, so
 * a screen that stops rendering cannot pass by having nothing to check (law 7).
 *
 * The eight customer-portal questions (`12-governance/22-product-maintenance-
 * process.md` §6) are answered for this app in `13-device-checks.md` §3 —
 * which are automated here (3, 4, 5, 6), which need a person (1, 2, 7), and
 * which do not apply (8: the field app never moves money, R16).
 *
 * Proved RED (lane report): with `Notice`'s words drawn in `colors.border`,
 * FF-15 failed "contrast 1.27:1 < 4.5 — "2 added in the field""; with
 * `Button`'s label given `allowFontScaling={false}`, FF-10 failed "text
 * refuses to scale — "Navigate"" and every screen with a button did the same.
 * And its first full run is itself a red: SUNLIGHT draws `status.<tone>.fg`
 * (white) as ink on the white card on eight screens — listed in KNOWN_SUNLIGHT
 * below, with the test at the end that goes red when one is fixed.
 */
import './keepMounted';
import 'react-native-gesture-handler/jestSetup';

import { act, render, screen } from '@testing-library/react-native';
import { StyleSheet } from 'react-native';

import * as routeQ from '../../src/db/queries/route';
import { scoped } from '../../src/db/scoped';
import { SCREENS, type ScreenId } from '../../src/navigation/screens';
import { Notice } from '../../src/components';
import { contrastRatio, ThemeProvider, THEMES, type ThemeName } from '../../src/theme';
import { openScreen } from '../../src/screens/theDay/go';
import { seedMapleHeights } from '../screens/reads/fixture';
import { seed as seedOnSite } from '../screens/onSite/fixture';
import { makeServices, seedWO4822 } from '../screens/theJob/fixture';
import { buildHandset, mountHandset, openAt, PEOPLE, settle, signInAs } from './runtimeApp';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);
// A 390 × 844 phone with the handset's text size at 200%.
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => ({ width: 390, height: 844, scale: 3, fontScale: 2 }),
}));

const DANA = PEOPLE['d.ortiz']!.technicianId;
const W = { workOrderId: 'wo-4822' };

/** What each screen is opened with — the same params its own wave's tests use. */
const PARAMS: Partial<Record<ScreenId, object>> = {
  'FF-12': { job: 'wo-4822' },
  'FF-14': { jobId: 'wo-4824' },
  'FF-15': W, 'FF-16': W, 'FF-17': W, 'FF-18': W, 'FF-19': W, 'FF-20': W, 'FF-21': W, 'FF-22': W,
  'FF-23': W, 'FF-24': W, 'FF-58': W, 'FF-59': W, 'FF-60': W,
  'FF-25': W, 'FF-26': { workOrderId: 'wo-4826' }, 'FF-27': { workOrderId: 'wo-4824' }, 'FF-28': W,
  'FF-29': W, 'FF-30': W, 'FF-31': W, 'FF-32': W, 'FF-33': W, 'FF-34': W, 'FF-36': W,
  'FF-37': { carriedFrom: 'wo-4824', templateId: 'tpl-leak' }, 'FF-38': W, 'FF-39': { assetId: 'a-4471' },
  'FF-40': { assetId: 'a-4471' }, 'FF-61': { workOrderId: 'wo-4830' }, 'FF-62': { carriedFrom: 'wo-4824' },
  'RW-02': { routeId: 'wlk-07' }, 'RW-03': { routeId: 'wlk-07' }, 'RW-04': { routeId: 'wlk-07' }, 'RW-05': { routeId: 'wlk-07' },
  'RW-06': { stopId: 's1318' }, 'RW-07': { stopId: 's1318' }, 'RW-09': { readId: 'r0472' }, 'RW-10': { readId: 'r0472' },
  'RW-11': { readId: 'r0472' }, 'RW-12': { readId: 'r0470' }, 'RW-13': { readId: 'r0471' }, 'RW-14': { readId: 'r0472' },
  'RW-15': { readId: 'r0472' }, 'RW-16': { readId: 'r0472' }, 'RW-17': { readId: 'r0472' },
  'RW-18': { readId: 'r0472', code: '90876' }, 'RW-19': { code: '90118', stopId: 's1318' },
  'RW-20': { code: '90241', stopId: 's1318' }, 'RW-21': { readId: 'r0472' }, 'RW-22': { routeId: 'wlk-07' },
  'RW-23': { routeId: 'wlk-07' }, 'RW-24': { routeId: 'wlk-07' }, 'RW-25': { routeId: 'wlk-07' },
  'RW-26': { routeId: 'wlk-07' }, 'RW-27': { routeId: 'wlk-07' },
};

/** What must be true on the handset before a screen has anything to show. */
const BEFORE: Partial<Record<ScreenId, (ses: { h: ReturnType<typeof buildHandset> }) => void>> = {
  // RW-27 is the receipt of a route already turned in.
  'RW-27': ({ h }) => routeQ.markTurnedIn(scoped(h.holder.current!, DANA), 'wlk-07', h.iso()),
};

/**
 * RW-26 starts a send the moment it opens; under the test renderer's `act()`
 * that send's updates never let act's queue drain (measured: outside act the
 * screen sends ONCE and settles), so it is opened outside act and given a
 * quarter of a second of real time. A harness limit, not the app's.
 */
const OUTSIDE_ACT = new Set<ScreenId>(['RW-26']);

/**
 * Findings this sweep made that are REPORTED (lane report, for the register),
 * not failed — each by its exact sentence, so anything else on the same screen
 * still fails. Nothing goes here without a line in the report.
 */
const THEME_LIST: ThemeName[] = ['light', 'dark', 'sunlight'];
/**
 * None left: DEF-FLD-10362 ("FF-01 has no heading" — the splash was one
 * full-screen button whose product name was not a header) was fixed by lane
 * INTEGRATE-2, and this list's last-test check told it to come off.
 */
const KNOWN_ANY_THEME: string[] = [];
/**
 * SUNLIGHT — the outdoor theme — drew `status.<tone>.fg` (WHITE in sunlight,
 * meant for text ON a status fill) as ink on the WHITE card on eight screens,
 * and FF-15's running clock was black on the dark green fill (2.59:1). Found
 * by this sweep as DEF-FLD-10360 and FIXED by lane INTEGRATE-2: the theme now
 * has `statusInk` — a tone drawn as ink on the card or page — and `fg` stays
 * for ink on the tone's own fill. Every finding came off this list, so
 * anything here again is a regression.
 */
const KNOWN_SUNLIGHT: string[] = [];
const KNOWN = new Map<string, string>([
  ...KNOWN_ANY_THEME.flatMap((p) => THEME_LIST.map((t) => [`${t}|${p}`, p] as [string, string])),
  ...KNOWN_SUNLIGHT.map((p) => [`sunlight|${p}`, p] as [string, string]),
]);
/** Which known findings this run actually met — a known finding that stops appearing was FIXED. */
const SEEN = new Set<string>();

const SIGNED_OUT: ScreenId[] = SCREENS.filter((s) => s.tree === 'gate').map((s) => s.id);
/** FF-09 is the drawer itself (opened, not navigated to); swept as the menu of FF-63. */
const SIGNED_IN: ScreenId[] = SCREENS.filter((s) => s.tree !== 'gate' && s.id !== 'FF-09').map((s) => s.id);

const CONTROL_ROLES = new Set(['button', 'link', 'checkbox', 'radio', 'switch', 'tab', 'menuitem', 'togglebutton', 'imagebutton', 'combobox', 'adjustable']);

type Node = {
  type: unknown;
  props: Record<string, unknown>;
  parent: Node | null;
  children: Array<Node | string>;
};

const styleOf = (n: Node): Record<string, unknown> => (StyleSheet.flatten(n.props.style as never) ?? {}) as Record<string, unknown>;
const isHost = (n: Node) => typeof n.type === 'string';
const HEX = /^#([0-9a-f]{6}|[0-9a-f]{3})$/i;

function textOf(n: Node | string): string {
  if (typeof n === 'string') return n;
  return n.children.map(textOf).join('');
}

function hosts(root: Node): Node[] {
  const out: Node[] = [];
  const walk = (n: Node) => {
    if (isHost(n)) out.push(n);
    for (const c of n.children) if (typeof c !== 'string') walk(c);
  };
  walk(root);
  return out;
}

function ancestors(n: Node, stop: Node): Node[] {
  const out: Node[] = [];
  for (let p = n.parent; p && p !== stop.parent; p = p.parent) if (isHost(p)) out.push(p);
  return out;
}

function backgroundOf(n: Node, stop: Node, page: string): string | null {
  for (const a of [n, ...ancestors(n, stop)]) {
    const bg = styleOf(a).backgroundColor;
    if (typeof bg === 'string' && bg !== 'transparent') return HEX.test(bg) ? bg : null;
  }
  return page;
}

function isDisabled(n: Node, stop: Node): boolean {
  return [n, ...ancestors(n, stop)].some((a) => (a.props.accessibilityState as { disabled?: boolean } | undefined)?.disabled === true);
}

function isScroll(n: Node): boolean {
  return n.type === 'RCTScrollView' || 'contentContainerStyle' in n.props || typeof n.props.onScroll === 'function';
}

export interface Report {
  texts: number;
  /** Of `texts`, how many were icon-font glyphs held to the graphic rules (3:1, no scaling) — printed, so the exemption has a number beside it (law 7). */
  icons: number;
  contrastSkipped: number;
  brandMarks: number;
  glyphsPastTheirBox: string[];
  controls: number;
  inputs: number;
  fixedChromePt: number;
  problems: string[];
}

/** A phone's height in points (390 × 844), and how much of it fixed bars may take at 200%. */
const SCREEN_PT = 844;
const FIXED_CHROME_MAX_PT = SCREEN_PT * 0.6;

/**
 * An ICON-FONT GLYPH: a Text whose whole content is in Unicode's Private Use
 * Area (U+E000–U+F8FF, where Ionicons — `@expo/vector-icons` — keeps its
 * glyphs) AND that sits inside a subtree hidden from the screen reader (`Glyph`
 * and `Mark` hide their icon; the word beside it carries the meaning). Such a
 * Text is a PICTURE drawn with a font, not words: the icon library itself sets
 * `allowFontScaling={false}` so the picture keeps its drawn size, and WCAG holds
 * a picture to non-text contrast (1.4.11, 3:1) rather than text contrast. Both
 * conditions are required, so a PUA character that a reader WOULD hear, or a
 * word, is still held to every text rule below. Narrow on purpose: it stops the
 * sweep misreading an icon as text, and weakens no check on text.
 */
const PUA = /^[\uE000-\uF8FF]+$/u;
function isIconGlyph(n: Node, stop: Node): boolean {
  if (!PUA.test(textOf(n).trim())) return false;
  return [n, ...ancestors(n, stop)].some(
    (a) => a.props.accessibilityElementsHidden === true || a.props.importantForAccessibility === 'no-hide-descendants',
  );
}

/** Words, not an icon glyph or a pair of initials. */
const isWords = (t: string) => (t.match(/\p{L}/gu) ?? []).length >= 3;

/** Every check above, on one screen's rendered subtree. */
export function audit(id: string, root: Node, theme: ThemeName): Report {
  const colors = THEMES[theme].colors;
  const r: Report = { texts: 0, icons: 0, contrastSkipped: 0, brandMarks: 0, glyphsPastTheirBox: [], controls: 0, inputs: 0, fixedChromePt: 0, problems: [] };
  const all = hosts(root);
  const fixedRows = new Map<Node, number>();
  for (const n of all) {
    const st = styleOf(n);
    if (n.type === 'Text' && n.children.some((c) => typeof c === 'string' && c.trim())) {
      r.texts += 1;
      const icon = isIconGlyph(n, root);
      if (icon) r.icons += 1;
      // An icon is reported by what it is, not by its private-use code point.
      const words = icon ? '(icon)' : textOf(n).trim().slice(0, 40);
      // 1 · contrast
      const fg = st.color;
      const bg = backgroundOf(n, root, colors.page);
      if (typeof fg === 'string' && HEX.test(fg) && bg && !isDisabled(n, root)) {
        // A nested <Text> inherits its size and weight from the Text around it.
        const textChain = [n, ...ancestors(n, root).filter((a) => a.type === 'Text')];
        const inherited = (k: string) => textChain.map((a) => styleOf(a)[k]).find((v) => v !== undefined);
        const size = Number(inherited('fontSize') ?? 0);
        const bold = Number(inherited('fontWeight') ?? 400) >= 700;
        // R100 (field-app rule): the brand colour is a MARK, held to 3:1 — reported, see the lane report.
        const mark = fg.toLowerCase() === colors.brand.toLowerCase() && colors.brand.toLowerCase() !== colors.text.toLowerCase();
        if (mark) r.brandMarks += 1;
        // An icon glyph is a graphic: non-text contrast, 3:1 (WCAG 1.4.11).
        const need = icon || mark || size >= 24 || (size >= 18.66 && bold) ? 3 : 4.5;
        const ratio = contrastRatio(fg, bg);
        if (ratio < need) r.problems.push(`${id} contrast ${ratio.toFixed(2)}:1 < ${need} — "${words}" (${fg} on ${bg})`);
      } else if (!isDisabled(n, root)) {
        r.contrastSkipped += 1;
      }
      // 3 · text at 200%
      // An icon glyph (Ionicons, added after this sweep was written) is a Text
      // with no words, hidden from the screen reader and sized by its box: it is
      // not text a reader must enlarge, and its outgrowth is counted below.
      const isGlyph = icon || words.trim() === '';
      if (!isGlyph && n.props.allowFontScaling === false) r.problems.push(`${id} text refuses to scale — "${words}"`);
      const cap = n.props.maxFontSizeMultiplier;
      if (!isGlyph && typeof cap === 'number' && cap > 0 && cap < 2) r.problems.push(`${id} text capped at ${cap}× — "${words}"`);
      const line = Number(st.lineHeight ?? Number(st.fontSize ?? 16) * 1.25);
      // An icon glyph keeps its drawn size at any text scale (above), so it cannot
      // outgrow its box; only words and initials are measured against one.
      for (const a of icon ? [] : [n, ...ancestors(n, root)]) {
        const as = styleOf(a);
        if (as.width === 0 || as.maxWidth === 0 || as.height === 0 || as.maxHeight === 0) {
          r.problems.push(`${id} text clipped to nothing (a zero-sized box) — "${words}"`);
          break;
        }
        const h = typeof as.height === 'number' ? as.height : typeof as.maxHeight === 'number' ? as.maxHeight : null;
        if (h !== null && h < 2 * line) {
          // One line at 200% does not fit the fixed box.
          if (isWords(words)) r.problems.push(`${id} words in a box fixed at ${h}pt, under one line at 200% (${2 * line}pt) — "${words}"`);
          else r.glyphsPastTheirBox.push(`${id} "${words}" ${2 * line}pt in ${h}pt`);
          break;
        }
        if (isScroll(a)) break;
      }
    }
    // 2 · names
    const role = n.props.accessibilityRole as string | undefined;
    if (role && CONTROL_ROLES.has(role) && n.props.accessible !== false) {
      r.controls += 1;
      const name = String(n.props.accessibilityLabel ?? '').trim() || textOf(n).trim();
      if (!name) r.problems.push(`${id} ${role} with no name (${String(n.props.testID ?? '?')})`);
      // 3 · reach: a control outside every scrolling body is in a FIXED bar. At 200%
      // its row grows to two lines of its label; controls side by side share a row.
      if (!ancestors(n, root).some(isScroll)) {
        const own = Math.max(Number(styleOf(n).minHeight ?? styleOf(n).height ?? 48), 48);
        const labels = all.filter((x) => x.type === 'Text' && ancestors(x, root).includes(n));
        const lh = Math.max(0, ...labels.map((x) => Number(styleOf(x).lineHeight ?? Number(styleOf(x).fontSize ?? 16) * 1.25)));
        const grown = Math.max(own, 2 * lh + 16);
        const parent = ancestors(n, root)[0] ?? root;
        const row = styleOf(parent).flexDirection === 'row' ? parent : n;
        fixedRows.set(row, Math.max(fixedRows.get(row) ?? 0, grown));
      }
    }
    if (n.type === 'TextInput') {
      r.inputs += 1;
      if (!String(n.props.accessibilityLabel ?? '').trim()) r.problems.push(`${id} text box with no label (${String(n.props.testID ?? '?')})`);
    }
  }
  r.fixedChromePt = [...fixedRows.values()].reduce((x, y) => x + y, 0);
  if (r.fixedChromePt > FIXED_CHROME_MAX_PT) {
    r.problems.push(`${id} fixed bars need ~${Math.round(r.fixedChromePt)}pt at 200% — over ${FIXED_CHROME_MAX_PT}pt of a ${SCREEN_PT}pt screen, so controls are pushed out of reach`);
  }
  return r;
}

interface Session {
  m: ReturnType<typeof mountHandset>;
  h: ReturnType<typeof buildHandset>;
  theme: ThemeName;
  signedIn: boolean;
  totals: { screens: number; texts: number; icons: number; controls: number; inputs: number; contrastSkipped: number; brandMarks: number; glyphs: string[] };
}

async function begin(theme: ThemeName, signedIn: boolean): Promise<Session> {
  const h = buildHandset({ network: 'none' });
  const m = mountHandset(h, { theme, biggerText: true });
  if (signedIn) {
    await signInAs(h, 'd.ortiz');
    await settle(2);
    const db = h.holder.current!;
    seedOnSite(db, DANA);
    seedWO4822({ ...makeServices(), db });
    seedMapleHeights(db, { technician: DANA, lists: true });
  }
  return { m, h, theme, signedIn, totals: { screens: 0, texts: 0, icons: 0, controls: 0, inputs: 0, contrastSkipped: 0, brandMarks: 0, glyphs: [] } };
}

/** Open one screen by its address, from the frame's root, and audit what it draws. */
async function check(ses: Session, id: ScreenId): Promise<string[]> {
  const { m } = ses;
  // Every screen is opened from the same starting place, so the stack never
  // holds more than the one under audit.
  await act(async () => {
    if (ses.signedIn) m.ref.resetRoot({ index: 0, routes: [{ name: 'Frame' }] });
  });
  BEFORE[id]?.(ses);
  if (OUTSIDE_ACT.has(id)) {
    openScreen(m.ref, id, PARAMS[id]);
    await new Promise((r) => setTimeout(r, 250));
  } else {
    await openAt(m, id, PARAMS[id]);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
  }
  const roots = screen.queryAllByTestId(`screen-${id}`);
  const root = roots[roots.length - 1] as unknown as Node | undefined;
  if (!root) return [`${id} did not open at its address`];
  ses.totals.screens += 1;
  const rep = audit(id, root, ses.theme);
  ses.totals.texts += rep.texts;
  ses.totals.icons += rep.icons;
  ses.totals.controls += rep.controls;
  ses.totals.inputs += rep.inputs;
  ses.totals.contrastSkipped += rep.contrastSkipped;
  ses.totals.brandMarks += rep.brandMarks;
  ses.totals.glyphs.push(...rep.glyphsPastTheirBox);
  // 4 · a heading: its own, or the navigation header's title for this route.
  const own = hosts(root).some((n) => n.props.accessibilityRole === 'header');
  const nav =
    own || screen.root.findAll((n: { props?: Record<string, unknown> }) => n.props?.accessibilityRole === 'header' && textOf(n as unknown as Node).trim().length > 0).length > 0;
  return nav ? rep.problems : [...rep.problems, `${id} has no heading`];
}

const THEME_NAMES: ThemeName[] = ['light', 'dark', 'sunlight'];

/**
 * Portal question 7 — "when something happens, is it announced, not just
 * shown?" DEF-FLD-10361, found by this pass and held open by `test.failing`
 * until lane INTEGRATE-2 made every `Notice` a live region: a warning or info
 * notice that appears AFTER an act — FF-21 "Camera not available yet.", RW-26
 * "Not sent yet. They stay on the phone." — was drawn and never spoken.
 */
test('portal question 7 (DEF-FLD-10361, fixed): a warning notice that appears after an act is announced (a live region)', () => {
  const { getByTestId, unmount } = render(
    <ThemeProvider initialMode="light">
      <Notice tone="warning" testID="n">
        Camera not available yet.
      </Notice>
    </ThemeProvider>,
  );
  expect(getByTestId('n').props.accessibilityLiveRegion).toBe('polite');
  unmount();
});

/** The problems that are not known findings; the known ones are logged and remembered as SEEN. */
function unknown(theme: ThemeName, found: string[]): string[] {
  const left: string[] = [];
  for (const p of found) {
    const k = `${theme}|${p}`;
    if (KNOWN.has(k)) {
      SEEN.add(k);
      console.log(`a11y ${theme}: known and reported — ${p}`);
    } else left.push(p);
  }
  return left;
}

describe.each(THEME_NAMES)('%s theme, text at 200%%', (theme) => {
  describe('signed in', () => {
    let ses: Session;
    beforeAll(async () => {
      ses = await begin(theme, true);
    }, 60_000);
    afterAll(() => ses.m.unmount());

    test.each(SIGNED_IN)('%s', async (id) => {
      expect(unknown(theme, await check(ses, id))).toEqual([]);
    }, 60_000);

    test('the sweep checked something on every screen', () => {
      const t = ses.totals;
      console.log(
        `a11y ${theme}: ${t.screens}/${SIGNED_IN.length} screens · ${t.texts} texts (${t.icons} of them icon glyphs held to 3:1 and not scaled, ${t.contrastSkipped} not measurable, ${t.brandMarks} brand marks at 3:1 under R100) · ${t.controls} controls · ${t.inputs} text boxes · ${t.glyphs.length} icon glyphs or initials that outgrow their fixed circle at 200% (reported, not failed): ${[...new Set(t.glyphs.map((g) => g.split(' ')[0]))].join(' ')}`,
      );
      expect(t.screens).toBe(SIGNED_IN.length);
      expect(t.texts).toBeGreaterThan(SIGNED_IN.length * 3);
      expect(t.controls).toBeGreaterThan(SIGNED_IN.length * 2);
    });
  });

  describe('signed out', () => {
    let ses: Session;
    beforeAll(async () => {
      ses = await begin(theme, false);
    }, 60_000);
    afterAll(() => ses.m.unmount());

    test.each(SIGNED_OUT)('%s', async (id) => {
      expect(unknown(theme, await check(ses, id))).toEqual([]);
    }, 60_000);

    test('the sweep checked something on every screen', () => {
      expect(ses.totals.screens).toBe(SIGNED_OUT.length);
      expect(ses.totals.controls).toBeGreaterThan(SIGNED_OUT.length);
    });
  });
});

// Runs last (jest runs a file's tests in order): every known finding must still
// be there. One that has gone was FIXED — this goes RED and names it, so it
// comes off the list instead of hiding the next regression of the same words.
test('every known finding is still met (a fixed one must come off the list)', () => {
  const gone = [...KNOWN.keys()].filter((k) => !SEEN.has(k));
  expect(gone).toEqual([]);
});
