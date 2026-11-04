/**
 * THE BACK ARROW GOES WHERE YOU CAME FROM (DEF-FLD-10607; PO 2026-10-26,
 * *"A for back button"* — decision log *"BACK GOES WHERE YOU CAME FROM"*).
 *
 * Every header back arrow in the field app is built from this one hook —
 * `theJob/JobScreen.tsx` (`back={{ to, label }}`), `onSite/common.tsx`
 * (`BOARD_HEADER`), `me/MeScreen.tsx` (`leading={{ back }}`),
 * `reads/ReadsScreen.tsx` (`READS_HEADER`) and the tablet's job pane
 * (`tablet/layouts/JobLayout.tsx`) — so the rule lives in one place:
 *
 *   · HISTORY FIRST. When this screen's own stack holds a screen below it,
 *     the arrow pops back to that one — Today → Start → Safety → back is
 *     Today, the same Today, with its day tab and its scroll where they were
 *     (a pop never remounts what it uncovers).
 *   · THE DRAWN DOOR ONLY WITHOUT HISTORY. Opened cold — from a notification
 *     or a link, with nothing under it — the arrow follows the door the
 *     drawing names (`navigation/doors.ts`), carrying the job or meter as
 *     before. That is the only thing the drawn destination is for now.
 *   · THE PHONE'S OWN BACK DOES THE SAME. With history, Android's back button
 *     and gesture are React Navigation's default — pop this stack — which is
 *     what the arrow does. Without history the default would leave the app,
 *     so this hook takes the button (while the screen is focused) and follows
 *     the same drawn door the arrow does.
 *   · THE SPOKEN LABEL NAMES THE REAL DESTINATION: *"Back to Today"* when
 *     going back (the previous screen's registry title, `screens.ts`), else
 *     the drawn label the screen passes (*"Back to the job"*).
 *
 * ⚠ "HISTORY" IS THIS SCREEN'S OWN STACK, NOT `navigation.canGoBack()`.
 * `canGoBack()` also answers for every navigator ABOVE this one, so a job
 * screen opened cold right after a sign-in would "go back" out of the frame
 * into First sync (FF-08). A screen has history when a route sits below it
 * on the stack it was pushed onto; then `goBack()` pops exactly that stack.
 *
 * The arrow keeps the test id `door-<drawn destination>`: it names the door
 * the arrow holds for a cold open, which is the door the doors tables list.
 *
 * SUPERSEDES a build lane's undecided judgment that the arrow was a fixed
 * door (*"back is a DOOR to the screen the drawing's arrow names, not 'go
 * back'"*), which was never put to the PO.
 */
import {
  type NavigationProp,
  type NavigationState,
  type ParamListBase,
  useFocusEffect,
  useNavigation,
  useNavigationState,
  useRoute,
} from '@react-navigation/native';
import { useCallback, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { BackHandler } from 'react-native';

import { TABS } from './routing';
import { isScreenId, type ScreenId, screenDef, TAB_SCREENS } from './screens';

type Node = { index?: number; routes?: Array<{ key: string; name: string; state?: unknown }> } | undefined;

/** The focused screen inside a route: a tab inside `Tabs`, or the route itself. */
function screenOf(route: { name: string; state?: unknown }): ScreenId | null {
  if (route.name === TABS) {
    const tabs = route.state as Node;
    const leaf = tabs?.routes?.[tabs.index ?? 0]?.name;
    // Never navigated inside: the tab navigator's first tab (FF-63 Home).
    return leaf && isScreenId(leaf) ? leaf : (TAB_SCREENS[0]?.id ?? null);
  }
  return isScreenId(route.name) ? route.name : null;
}

/**
 * Where back goes from the route `key` on `state` (its own stack):
 * `undefined` — no history; `null` — history, but not a screen of the
 * registry; otherwise the screen under it.
 */
export function previousScreen(state: unknown, key: string): ScreenId | null | undefined {
  const node = state as Node;
  const routes = node?.routes ?? [];
  const at = routes.findIndex((r) => r.key === key);
  if (at <= 0) return undefined;
  const below = routes[at - 1];
  return below ? screenOf(below) : undefined;
}

export interface HistoryBack {
  /** Press the arrow: back through history, else the drawn door. */
  onBack: () => void;
  /** The arrow's spoken label, naming where it really goes. */
  label: string;
  /** True when the arrow will go back through history. */
  hasHistory: boolean;
}

/**
 * @param drawn the drawn door: its label, and how to follow it (with the job
 *   or meter it carries) when there is no history.
 */
export function useHistoryBack(drawn: { label: string; follow: () => void } | null): HistoryBack {
  const { t } = useTranslation();
  const navigation = useNavigation<NavigationProp<ParamListBase>>();
  const route = useRoute();
  const previous = useNavigationState((s: NavigationState) => previousScreen(s, route.key));
  const hasHistory = previous !== undefined;

  // The press reads the stack as it is NOW, never as it was at render.
  const follow = useRef(drawn?.follow);
  useEffect(() => {
    follow.current = drawn?.follow;
  });
  const onBack = useCallback(() => {
    if (previousScreen(navigation.getState(), route.key) !== undefined) navigation.goBack();
    else follow.current?.();
  }, [navigation, route.key]);

  // The phone's own back: with history it is the navigator's default (pop),
  // which is what the arrow does; without, the arrow's drawn door.
  const active = drawn !== null;
  useFocusEffect(
    useCallback(() => {
      if (!active) return undefined;
      const sub = BackHandler.addEventListener('hardwareBackPress', () => {
        if (previousScreen(navigation.getState(), route.key) !== undefined) return false;
        follow.current?.();
        return true;
      });
      return () => sub.remove();
    }, [active, navigation, route.key]),
  );

  const label =
    previous !== undefined && previous !== null
      ? t('field.nav.backTo', { screen: t(screenDef(previous).titleKey) })
      : (drawn?.label ?? '');
  return { onBack, label, hasHistory };
}
