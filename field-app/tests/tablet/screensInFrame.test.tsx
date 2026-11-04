/**
 * Every registered screen, mounted under the REAL navigation tree at tablet
 * size, sits in its own frame and renders without throwing (T-27, T-29) —
 * signed-in screens through the root/frame/shell/tab addresses the doors use,
 * the gate screens through the signed-out tree.
 *
 * A screen is found by the frame that holds it (`nativeID="frame-of-<id>"`)
 * and that frame must be the one `frameMap.ts` names; a phone mount is checked
 * to carry no frame at all.
 *
 * It also COUNTS the slots nobody has filled yet — T-28's eight `tabletLayout`
 * slots and the two shared T3 context panes — and prints them, so an empty
 * slot cannot pass for a filled one (hard-won law 2). Since T-28/T-29 filled
 * all of them, both counts are also ASSERTED to be zero.
 */
import 'react-native-gesture-handler/jestSetup';

import { CommonActions, createNavigationContainerRef, NavigationContainer, type ParamListBase } from '@react-navigation/native';
import { act, render, screen } from '@testing-library/react-native';

import { createFieldI18n } from '../../src/i18n/i18n';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { AppNavigator } from '../../src/navigation/AppNavigator';
import { routeTo } from '../../src/navigation/routing';
import { SCREEN_IDS, type ScreenId, screenDef } from '../../src/navigation/screens';
import { ShellStatusProvider, UNKNOWN_STATUS } from '../../src/navigation/ShellStatus';
import { SCREEN_COMPONENTS } from '../../src/screens/registry';
import { SessionProvider } from '../../src/session/SessionProvider';
import { CONTEXT_PANES } from '../../src/tablet/contextPanes';
import { contextFamilyOf, FRAME_OF, SHAPE_CHANGING } from '../../src/tablet/frameMap';
import { tabletLayoutOf } from '../../src/tablet/layoutSlot';
import { ThemeProvider } from '../../src/theme';
import { makeHandset, signIn } from '../session/fakes';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

const mockWindow = { width: 1024, height: 768, scale: 2, fontScale: 1 };
jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
  __esModule: true,
  default: () => mockWindow,
}));

async function mount(signedIn: boolean) {
  const h = makeHandset();
  if (signedIn) await signIn(h.session, 'd.ortiz');
  const ref = createNavigationContainerRef<ParamListBase>();
  render(
    <ThemeProvider initialMode="light">
      <I18nProvider fieldI18n={createFieldI18n({ language: 'en' })} prefs={h.prefs}>
        <SessionProvider manager={h.session}>
          <ShellStatusProvider value={UNKNOWN_STATUS}>
            <NavigationContainer ref={ref}>
              <AppNavigator />
            </NavigationContainer>
          </ShellStatusProvider>
        </SessionProvider>
      </I18nProvider>
    </ThemeProvider>,
  );
  return ref;
}

type Instance = typeof screen.UNSAFE_root;

function frameHolding(id: ScreenId): Instance | undefined {
  return screen.UNSAFE_root.findAll((n: Instance) => n.props.nativeID === `frame-of-${id}` && typeof n.type === 'string')[0];
}

async function go(ref: ReturnType<typeof createNavigationContainerRef<ParamListBase>>, id: ScreenId) {
  const target = routeTo(id);
  await act(async () => {
    ref.dispatch(CommonActions.navigate(target.name, target.params));
  });
}

const signedInIds = SCREEN_IDS.filter((id) => ['root', 'frame', 'tab'].includes(screenDef(id).tree));
const gateIds = SCREEN_IDS.filter((id) => screenDef(id).tree === 'gate');

describe('at 1024 × 768, every screen sits in its frame', () => {
  beforeEach(() => {
    Object.assign(mockWindow, { width: 1024, height: 768 });
  });

  test('the mounted window is the tablet board (the mock reached the shell)', async () => {
    await mount(true);
    expect(await screen.findByTestId('menu-sidebar')).toBeTruthy();
    expect(screen.queryByTestId('menu-drawer')).toBeNull();
  });

  test(`signed in: all ${signedInIds.length} screens, each in the frame frameMap names`, async () => {
    const ref = await mount(true);
    await screen.findByTestId('menu-sidebar');
    const wrong: string[] = [];
    for (const id of signedInIds) {
      await go(ref, id);
      expect(ref.getCurrentRoute()?.name).toBe(id);
      const frame = frameHolding(id);
      const got = frame?.props.testID as string | undefined;
      if (got !== `tablet-frame-${FRAME_OF[id]}`) wrong.push(`${id}: ${got ?? 'no frame'}`);
      else expect(frame?.findAll((n: Instance) => typeof n.type === 'string').length).toBeGreaterThan(1);
    }
    console.log(`screensInFrame: ${signedInIds.length} signed-in screens mounted on a tablet, ${wrong.length} wrong`);
    expect(wrong).toEqual([]);
  }, 240_000);

  test(`signed out: all ${gateIds.length} gate screens in the centred column`, async () => {
    const ref = await mount(false);
    const wrong: string[] = [];
    for (const id of gateIds) {
      await go(ref, id);
      const got = frameHolding(id)?.props.testID as string | undefined;
      if (got !== 'tablet-frame-T1') wrong.push(`${id}: ${got ?? 'no frame'}`);
    }
    expect(wrong).toEqual([]);
  }, 60_000);
});

describe('held upright (768 × 1024)', () => {
  beforeEach(() => {
    Object.assign(mockWindow, { width: 768, height: 1024 });
  });

  test('two-pane screens still mount in their frame', async () => {
    const ref = await mount(true);
    await screen.findByTestId('menu-sidebar');
    for (const id of ['FF-10', 'FF-15', 'FF-25', 'RW-05', 'RW-09', 'FF-63'] as ScreenId[]) {
      await go(ref, id);
      expect(frameHolding(id)?.props.testID).toBe(`tablet-frame-${FRAME_OF[id]}`);
    }
  }, 60_000);
});

describe('on a phone there is no frame', () => {
  beforeEach(() => {
    Object.assign(mockWindow, { width: 390, height: 844 });
  });

  test('Today and the Job mount bare', async () => {
    const ref = await mount(true);
    await screen.findByTestId('menu-drawer');
    for (const id of ['FF-10', 'FF-15'] as ScreenId[]) {
      await go(ref, id);
      expect(ref.getCurrentRoute()?.name).toBe(id);
      expect(frameHolding(id)).toBeUndefined();
    }
  }, 60_000);
});

test('the unfilled slots, counted — and now held at zero', () => {
  const unfilledLayouts = SHAPE_CHANGING.filter((id) => tabletLayoutOf(SCREEN_COMPONENTS[id]) == null);
  const t3 = SCREEN_IDS.filter((id) => FRAME_OF[id] === 'T3');
  const waiting = (family: 'job' | 'route') =>
    CONTEXT_PANES[family] ? 0 : t3.filter((id) => contextFamilyOf(id) === family).length;
  console.log(
    `tablet slots: ${unfilledLayouts.length} of ${SHAPE_CHANGING.length} T-28 tabletLayout slots unfilled (${unfilledLayouts.join(', ')}); ` +
      `T3 screens waiting on a context pane — job ${waiting('job')}, route ${waiting('route')}`,
  );
  expect(t3).toHaveLength(34);
  // T-28 and T-29 filled them (TABLET-2): from here an emptied slot is a
  // regression, so the count is asserted, not only printed.
  expect(unfilledLayouts).toEqual([]);
  expect([waiting('job'), waiting('route')]).toEqual([0, 0]);
});

test('every two-pane board has its list and its detail — counted, and held at all 31', () => {
  // T-29 (TABLET-3): the 25 T2 boards whose detail is drawn as part of the
  // same screen now carry a layout too, so no T2 board shows its phone screen
  // in one full-width pane at 1024. A board whose slot is emptied — its
  // registration put back to the bare phone screen — is named here.
  const t2 = SCREEN_IDS.filter((id) => FRAME_OF[id] === 'T2');
  const unfilled = t2.filter((id) => {
    const layout = tabletLayoutOf(SCREEN_COMPONENTS[id]);
    return layout == null || layout.frame !== 'T2' || layout.list == null || layout.detail == null;
  });
  console.log(`T2 boards: ${t2.length - unfilled.length} of ${t2.length} with a list and a detail${unfilled.length ? ` — not: ${unfilled.join(', ')}` : ''}`);
  expect(t2).toHaveLength(31);
  expect(unfilled).toEqual([]);
});
