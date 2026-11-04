/**
 * doors.test — every screen has something that opens it, and every door goes
 * where it says (R98, R99; requirement 79: *"a doors.test.ts that asserts every
 * screen has something that opens it"*).
 *
 * Two halves, because each catches what the other cannot:
 *
 *  1. THE GRAPH. From the doors table, the menu and the tabs: every registered
 *     screen has at least one way in, and — stronger, and the one that found
 *     three closed loops in the design's own links — every screen can be
 *     REACHED from the splash. An inbound count alone passes two screens that
 *     only point at each other.
 *  2. THE BUTTONS. The real tree is mounted and every door on every signed-in
 *     screen is pressed; the screen that comes up must be the door's target.
 *     A table that says FF-15 → FF-25 while the button goes somewhere else
 *     fails here, by address.
 *
 * Proved red (law 7) by deleting the `FROM_THE_IMAGES` entry for FF-44 →
 * FF-51 Settings: *"phone: every screen can be reached from the splash"*
 * failed with `FF-51, FF-52, FF-54, FF-55, RW-29` unreachable — while the
 * inbound-count test beside it stayed GREEN, which is why both exist. The
 * first version of this file checked the phone and tablet menus as one union
 * and passed even then, because the tablet sidebar has a Settings row; the
 * graph is now walked once per form.
 */
import 'react-native-gesture-handler/jestSetup';

import { CommonActions } from '@react-navigation/native';
import { act, fireEvent, screen, within } from '@testing-library/react-native';
import { readdirSync, readFileSync, statSync } from 'fs';
import { join } from 'path';

import { DOORS, FROM_THE_IMAGES } from '../../src/navigation/doors';
import { menuTargets, PHONE_MENU, MENU_FOOT } from '../../src/navigation/drawerEntries';
import { doorKind, routeTo } from '../../src/navigation/routing';
import { ENTRY_SCREEN, MENU_SCREEN, SCREEN_IDS, type ScreenId, screenDef, TAB_SCREENS } from '../../src/navigation/screens';
import { SCREEN_COMPONENTS } from '../../src/screens/registry';
import { mountApp } from './harness';

/**
 * A screen still mounting the placeholder renders its doors as buttons and is
 * pressed here. A BUILT screen draws its doors where the board puts them — a
 * card, a tab, a sheet, a button that is an act — so the button half cannot
 * find them generically; each built screen's own wave test presses them
 * (SCREENS-BRIEF step 5). That is a hand-off, so it is CHECKED rather than
 * trusted: every door of every built screen must be named, as the literal
 * `'<from> → <to>'`, in a test under `tests/screens/`. A built screen whose
 * door no wave test names fails below, by name (law 7: a check says what it
 * did not do itself).
 *
 * Proved red when it was added (T-15/T-16): with 16 screens built and no
 * wave test yet, it failed naming all 44 of their doors; it went green only
 * as `tests/screens/gettingIn/` and `tests/screens/theDay/` pressed each one.
 */
const isPlaceholder = (id: ScreenId) => (SCREEN_COMPONENTS[id].displayName ?? '').startsWith('Placeholder(');
const BUILT = SCREEN_IDS.filter((id) => !isPlaceholder(id));

function testSources(dir: string): string[] {
  let out: string[] = [];
  let names: string[] = [];
  try {
    names = readdirSync(dir);
  } catch {
    return out;
  }
  for (const name of names) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) out = out.concat(testSources(path));
    else if (/\.test\.tsx?$/.test(name)) out.push(readFileSync(path, 'utf8'));
  }
  return out;
}

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

/**
 * Every edge one form of the app offers: the doors table, that form's menu,
 * and — on a phone — the tabs. Checked per form, never as the union: the
 * tablet sidebar has a Settings row the phone menu does not, so a union
 * would let the tablet hide a phone screen nobody can reach.
 */
function edges(tablet: boolean): Array<[ScreenId, ScreenId]> {
  const out: Array<[ScreenId, ScreenId]> = [];
  for (const from of SCREEN_IDS) {
    // FF-09's own row is the phone menu; the menu edges below are per form.
    if (from === MENU_SCREEN) continue;
    for (const to of DOORS[from]) out.push([from, to]);
  }
  for (const to of menuTargets(tablet)) out.push([MENU_SCREEN, to]);
  if (!tablet) {
    for (const tab of TAB_SCREENS) for (const other of TAB_SCREENS) if (tab.id !== other.id) out.push([tab.id, other.id]);
  }
  return out;
}

const FORMS: Array<[string, boolean]> = [
  ['phone', false],
  ['tablet', true],
];

describe('the graph', () => {
  test('there are 92 design screens plus the Switch technician sheet, and every one has a doors row', () => {
    expect(SCREEN_IDS.filter((id) => id.startsWith('FF-'))).toHaveLength(63);
    expect(SCREEN_IDS.filter((id) => id.startsWith('RW-'))).toHaveLength(29);
    expect(SCREEN_IDS).toContain('SWITCH');
    expect(Object.keys(DOORS).sort()).toEqual([...SCREEN_IDS].sort());
  });

  test.each(FORMS)('%s: every door points at a registered screen', (_form, tablet) => {
    for (const [from, to] of edges(tablet)) {
      expect([from, SCREEN_IDS.includes(to)]).toEqual([from, true]);
    }
  });

  test.each(FORMS)('%s: every screen has at least one way in, except the splash, which is named', (_form, tablet) => {
    const inbound = new Map<ScreenId, number>(SCREEN_IDS.map((id) => [id, 0]));
    for (const [, to] of edges(tablet)) inbound.set(to, (inbound.get(to) ?? 0) + 1);
    const orphans = [...inbound].filter(([, n]) => n === 0).map(([id]) => id);
    expect(orphans).toEqual([ENTRY_SCREEN]);
  });

  test.each(FORMS)('%s: every screen can be reached from the splash', (_form, tablet) => {
    const next = new Map<ScreenId, ScreenId[]>();
    for (const [from, to] of edges(tablet)) next.set(from, [...(next.get(from) ?? []), to]);
    const seen = new Set<ScreenId>([ENTRY_SCREEN]);
    const queue: ScreenId[] = [ENTRY_SCREEN];
    while (queue.length) {
      const id = queue.shift() as ScreenId;
      for (const to of next.get(id) ?? []) {
        if (!seen.has(to)) {
          seen.add(to);
          queue.push(to);
        }
      }
    }
    expect(SCREEN_IDS.filter((id) => !seen.has(id))).toEqual([]);
  });

  test('the phone menu opens exactly what the FF-09 board links, in its order', () => {
    const menu = [...PHONE_MENU.flatMap((g) => g.items.map((i) => i.id)), ...MENU_FOOT.map((i) => i.id)];
    expect(menu).toEqual(DOORS[MENU_SCREEN]);
  });

  test('each door added from the images is one the links did not already have', () => {
    for (const { from, to } of FROM_THE_IMAGES) {
      expect(DOORS[from]).toContain(to);
    }
    // 7: FF-15 → FF-32 is the PO's door on MQ-024 (DEF-FLD-10586), and FF-50 → FF-53
    // (Sign in again on a credential refusal) the PO's on MQ-027 (DEF-FLD-10612) — not drawn ones.
    expect(FROM_THE_IMAGES).toHaveLength(7);
  });
});

const SIGNED_IN: ScreenId[] = SCREEN_IDS.filter((id) => {
  const tree = screenDef(id).tree;
  return tree === 'frame' || tree === 'tab' || tree === 'root';
});

describe('the built screens', () => {
  test('every door of every built screen is pressed by a wave test, named as "<from> → <to>"', () => {
    const sources = testSources(join(__dirname, '../screens')).join('\n');
    const unnamed: string[] = [];
    let named = 0;
    for (const from of BUILT) {
      for (const to of DOORS[from]) {
        if (sources.includes(`'${from} → ${to}'`)) named += 1;
        else unnamed.push(`${from} → ${to}`);
      }
    }
    // eslint-disable-next-line no-console
    console.log(`doors: ${BUILT.length} built screens, ${named} doors named by wave tests, ${unnamed.length} not`);
    expect(unnamed).toEqual([]);
  });
});

describe('the buttons', () => {
  test('every door on every signed-in screen opens its target, by address', async () => {
    let pressed = 0;
    const notLinks: string[] = [];
    const placeholders = SIGNED_IN.filter(isPlaceholder);
    for (const from of placeholders) {
      // A fresh tree per screen keeps the stack short, so the screen on top
      // is the last one mounted.
      const app = await mountApp();
      await screen.findByTestId('screen-FF-63');
      for (const to of DOORS[from]) {
        const target = routeTo(from);
        await act(async () => {
          app.ref.dispatch(CommonActions.navigate(target.name, target.params));
        });
        expect(app.ref.getCurrentRoute()?.name).toBe(from);
        const onTop = screen.getAllByTestId(`screen-${from}`).at(-1);
        if (!onTop) throw new Error(`${from} is not mounted`);
        const button = within(onTop).getByTestId(`door-${to}`);
        const kind = doorKind(from, to);
        if (kind !== 'link') {
          notLinks.push(`${from}→${to}:${kind}`);
          continue;
        }
        fireEvent.press(button);
        expect(`${from} → ${app.ref.getCurrentRoute()?.name}`).toBe(`${from} → ${to}`);
        pressed += 1;
      }
      app.unmount();
    }
    // What was pressed and what was not, stated, so a run that silently
    // skipped cannot read as a pass (law 7: a check reports what it skipped).
    // FF-09 is the menu: its door opens the drawer, proven in navigator.test.
    // Counted, not fixed: the numbers fall as screens are built and their
    // doors move to the wave tests checked above.
    const menuDoors = notLinks.filter((n) => n.endsWith('→FF-09:opens-menu'));
    const acts = notLinks.filter((n) => !menuDoors.includes(n));
    expect(acts).toEqual(isPlaceholder('FF-53') ? ['FF-53→FF-05:signs-out'] : []);
    const total = placeholders.reduce((n, id) => n + DOORS[id].length, 0);
    // eslint-disable-next-line no-console
    console.log(`doors: ${placeholders.length} placeholder screens, ${total} doors, ${pressed} pressed, ${menuDoors.length} open the menu`);
    expect(pressed + notLinks.length).toBe(total);
    // Once every signed-in screen is built there is nothing left to press
    // here; every door is then pressed by a wave test, which the hand-off
    // check above refuses to let go unnamed.
    if (placeholders.length > 0) expect(pressed).toBeGreaterThan(0);
    else expect(BUILT).toEqual(expect.arrayContaining(SIGNED_IN));
  }, 240_000);

  test('every door on the signed-out screens opens its target, and the two into the app say they sign you in', async () => {
    const GATE = SCREEN_IDS.filter((id) => screenDef(id).tree === 'gate' && isPlaceholder(id));
    let pressed = 0;
    const notLinks: string[] = [];
    for (const from of GATE) {
      const app = await mountApp({ signedIn: false });
      await screen.findByTestId('screen-FF-01');
      for (const to of DOORS[from]) {
        await act(async () => {
          app.ref.dispatch(CommonActions.navigate(from));
        });
        const onTop = screen.getAllByTestId(`screen-${from}`).at(-1);
        if (!onTop) throw new Error(`${from} is not mounted`);
        const button = within(onTop).getByTestId(`door-${to}`);
        if (doorKind(from, to) !== 'link') {
          notLinks.push(`${from}→${to}`);
          expect(button).toBeDisabled();
          expect(button).toHaveTextContent(/After sign in/);
          continue;
        }
        fireEvent.press(button);
        expect(`${from} → ${app.ref.getCurrentRoute()?.name}`).toBe(`${from} → ${to}`);
        pressed += 1;
      }
      app.unmount();
    }
    const acts = (['FF-05', 'FF-57'] as ScreenId[]).filter(isPlaceholder).map((id) => `${id}→FF-07`);
    expect(notLinks).toEqual(acts);
    expect(pressed).toBe(GATE.reduce((n, id) => n + DOORS[id].length, 0) - acts.length);
  }, 120_000);
});
