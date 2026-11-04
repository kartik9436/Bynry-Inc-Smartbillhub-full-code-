/**
 * T-26 — the theme walk. EVERY registered screen (`SCREEN_COMPONENTS`,
 * placeholders included) renders in light, dark and sunlight without
 * throwing, and every piece of text on it passes contrast against what is
 * actually behind it (US-FLD-035; requirement 35; R100).
 *
 * How it measures, so a reader can check it:
 *  - each host <Text> with words in it: its colour is its own `color`, or the
 *    nearest enclosing <Text>'s (React Native text inherits);
 *  - what is behind it is the nearest enclosing view with an opaque
 *    `#rrggbb` background — a translucent or `transparent` one is looked
 *    through — falling back to the theme's page;
 *  - the bar is 4.5:1 (WCAG AA), except the brand MARK colour, which R100
 *    holds to 3:1 and which is never body text.
 * A colour that is not `#rrggbb` (a named colour, an `rgb()`) cannot be
 * measured and FAILS rather than being skipped — law 7: a check reports what
 * it could not check.
 *
 * And, for the "me" wave's own screens, every button, radio and switch has a
 * name and is at least 48pt (B14 rule 45, R39).
 *
 * Proved red (law 7) — see the two `the walk itself can fail` cases at the
 * foot, which feed it a pair it must refuse and a colour it cannot measure.
 */
import 'react-native-gesture-handler/jestSetup';

import { NavigationContainer, type ParamListBase } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { act, render, screen } from '@testing-library/react-native';
import { type ComponentType } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { createFieldI18n } from '../../../src/i18n/i18n';
import { I18nProvider } from '../../../src/i18n/I18nProvider';
import { SCREEN_IDS, type ScreenId } from '../../../src/navigation/screens';
import { SCREEN_COMPONENTS } from '../../../src/screens/registry';
import { SCREENS as ME } from '../../../src/screens/groups/me';
import { MeServicesProvider } from '../../../src/screens/me/services';
import { SessionProvider } from '../../../src/session/SessionProvider';
import { contrastRatio, THEMES, ThemeProvider, type ThemeName } from '../../../src/theme';
import { makeHandset, signIn } from '../../session/fakes';
import {
  boardAlerts,
  boardVan,
  boardWeek,
  makeFixture,
  seedDay,
  seedOrders,
  seedPhotos,
  seedRefusal,
} from './support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

type Node = ReturnType<typeof screen.getByText>;

const HEX = /^#[0-9a-f]{6}$/i;
const BRANDS = new Set(Object.values(THEMES).map((x) => x.colors.brand.toLowerCase()));

function styleOf(n: Node): Record<string, unknown> {
  return (StyleSheet.flatten(n.props.style) ?? {}) as Record<string, unknown>;
}

function isText(n: Node): boolean {
  return n.type === 'Text';
}

function ownWords(n: Node): string {
  return (n.children as unknown[]).filter((c): c is string => typeof c === 'string').join('').trim();
}

export interface Finding {
  text: string;
  fg: string;
  bg: string;
  ratio: number;
  need: number;
}

/** Every text pair under `root` that fails, or cannot be measured. */
export function walkContrast(root: Node, theme: ThemeName): { checked: number; failures: Finding[] } {
  const t = THEMES[theme];
  const failures: Finding[] = [];
  let checked = 0;
  const texts = root.findAll((n: Node) => isText(n) && ownWords(n) !== '', { deep: true });
  for (const node of texts) {
    let fg: unknown;
    for (let p: Node | null = node; p && fg === undefined; p = p.parent) {
      if (isText(p)) fg = styleOf(p).color;
    }
    let bg: string | undefined;
    for (let p: Node | null = node; p && !bg; p = p.parent) {
      const b = styleOf(p).backgroundColor;
      if (typeof b === 'string' && HEX.test(b)) bg = b;
    }
    bg ??= t.colors.page;
    const text = ownWords(node);
    if (typeof fg !== 'string' || !HEX.test(fg)) {
      failures.push({ text, fg: String(fg), bg, ratio: 0, need: 4.5 });
      continue;
    }
    checked += 1;
    const ratio = contrastRatio(fg, bg);
    // R100: the brand is a MARK colour, held to 3:1; everything else to 4.5:1.
    // A brand colour is a mark whichever theme it comes from (the shell's own
    // stand-in marks are drawn in the light brand on every theme).
    // WCAG 1.4.3: LARGE text (24px and up) is held to 3:1 — the splash's
    // *SMART360 Next* title, 33pt (added in the integration lane, when the
    // gettingIn wave's splash met this walk for the first time).
    let size: unknown;
    for (let p: Node | null = node; p && size === undefined; p = p.parent) {
      if (isText(p)) size = styleOf(p).fontSize;
    }
    const large = typeof size === 'number' && size >= 24;
    const need = BRANDS.has(fg.toLowerCase()) || large ? 3 : 4.5;
    if (ratio + 1e-9 < need) failures.push({ text, fg, bg, ratio: Math.round(ratio * 100) / 100, need });
  }
  return { checked, failures };
}

const Stack = createNativeStackNavigator<ParamListBase>();

function seededFixture() {
  const f = makeFixture({
    shifts: { week: async () => boardWeek(), requestTimeOff: async () => undefined, endShift: async () => undefined },
    van: { stock: async () => boardVan(), askDepot: async () => undefined },
  });
  seedOrders(f.db);
  seedDay(f.db, f.ids);
  seedPhotos(f.db);
  seedRefusal(f.db, f.ids);
  f.alerts.items = boardAlerts();
  return f;
}

async function mountOne(id: ScreenId, Component: ComponentType, theme: ThemeName) {
  const h = makeHandset();
  await signIn(h.session, 'd.ortiz');
  const f = seededFixture();
  const ui = (
    <ThemeProvider initialMode={theme}>
      <I18nProvider fieldI18n={createFieldI18n({ language: 'en' })} prefs={h.prefs}>
        <SessionProvider manager={h.session}>
          <MeServicesProvider services={f.services}>
            <NavigationContainer>
              <Stack.Navigator screenOptions={{ headerShown: false }}>
                <Stack.Screen name={id} component={Component} />
              </Stack.Navigator>
            </NavigationContainer>
          </MeServicesProvider>
        </SessionProvider>
      </I18nProvider>
    </ThemeProvider>
  );
  const utils = render(ui);
  await act(async () => {
    await Promise.resolve();
  });
  return utils;
}

const THEMES_WALKED: ThemeName[] = ['light', 'dark', 'sunlight'];
const ME_IDS = Object.keys(ME) as ScreenId[];

describe.each(THEMES_WALKED)('%s', (theme) => {
  test('every registered screen renders, and every text pair passes contrast', async () => {
    const report: string[] = [];
    let screens = 0;
    let pairs = 0;
    for (const id of SCREEN_IDS) {
      const app = await mountOne(id, SCREEN_COMPONENTS[id], theme);
      const root = app.UNSAFE_root as unknown as Node;
      const { checked, failures } = walkContrast(root, theme);
      expect([id, checked > 0]).toEqual([id, true]);
      pairs += checked;
      screens += 1;
      for (const x of failures) report.push(`${id} "${x.text}" ${x.fg} on ${x.bg} = ${x.ratio}:1 (needs ${x.need})`);
      app.unmount();
    }
    // What was walked, so a run that silently skipped cannot read as a pass.
    console.log(`themeWalk ${theme}: ${screens} screens, ${pairs} text pairs measured`);
    expect(screens).toBe(SCREEN_IDS.length);
    expect(report).toEqual([]);
  }, 240_000);

  test('the "me" screens: every button, radio and switch is named and at least 48pt', async () => {
    let controls = 0;
    const bad: string[] = [];
    for (const id of ME_IDS) {
      const app = await mountOne(id, SCREEN_COMPONENTS[id], theme);
      const all = [
        ...app.queryAllByRole('button'),
        ...app.queryAllByRole('radio'),
        ...app.queryAllByRole('switch'),
      ];
      for (const el of all) {
        controls += 1;
        const name = String(el.props.accessibilityLabel ?? '').trim();
        const s = styleOf(el as Node);
        const height = Number(s.minHeight ?? s.height ?? 0);
        if (!name) bad.push(`${id}: unnamed ${el.props.testID ?? el.props.accessibilityRole}`);
        if (height < 48) bad.push(`${id}: ${name || el.props.testID} is ${height}pt`);
      }
      app.unmount();
    }
    expect(controls).toBeGreaterThan(100);
    expect(bad).toEqual([]);
  }, 240_000);
});

describe('the walk itself can fail (law 7)', () => {
  test('it refuses a pair under 4.5:1 and a colour it cannot measure', () => {
    const app = render(
      <View style={{ backgroundColor: '#ffffff' }}>
        <Text style={{ color: '#bab6b6' }}>pale grey on white</Text>
        <Text style={{ color: 'red' }}>a named colour</Text>
        <Text style={{ color: '#201e1d' }}>ink on white</Text>
      </View>,
    );
    const { checked, failures } = walkContrast(app.UNSAFE_root as unknown as Node, 'light');
    expect(failures.map((f) => f.text)).toEqual(['pale grey on white', 'a named colour']);
    expect(checked).toBe(2);
  });

  test('it looks through a translucent layer to the opaque one behind', () => {
    const app = render(
      <View style={{ backgroundColor: '#1a1918' }}>
        <View style={{ backgroundColor: 'rgba(0, 0, 0, 0.4)' }}>
          <Text style={{ color: '#201e1d' }}>dark ink on the dark page</Text>
        </View>
      </View>,
    );
    expect(walkContrast(app.UNSAFE_root as unknown as Node, 'dark').failures).toHaveLength(1);
  });
});
