/**
 * The frame every job screen is drawn in: the boards' own top bar, a
 * scrolling body, and a footer of actions pinned to the bottom — and the three
 * things a screen must never forget: its `screen-<id>` test id, its crash
 * boundary, and hiding the stack's own header so there is one bar, as drawn.
 *
 * BACK GOES WHERE YOU CAME FROM (DEF-FLD-10607; PO 2026-10-26, *"A for back
 * button"*). The arrow pops back to the previous screen in history — Today →
 * Start → Safety → back is Today — and the drawn `back.to` is followed only
 * when there is no history (opened from a notification or a cold link),
 * carrying the job as every door does. The phone's own back does the same and
 * the spoken label names the real destination (`navigation/back.tsx`, the one
 * place this rule lives). ⚠ This header read *"back is a DOOR to the screen
 * the drawing's arrow names, not 'go back'"* until then — a build lane's
 * judgment never put to the PO, which the ruling superseded.
 *
 * ⚠ THEME: `useTheme()` throws outside a `ThemeProvider` (by design — a silent
 * light default would never switch). The app root and the navigation test
 * harness do not mount one yet, so this frame mounts one ONLY when none is
 * above it. That keeps the job screens working today; the moment the root
 * mounts the provider, this branch stops running and the technician's chosen
 * theme reaches every screen. Reported to the coordinator: `App.tsx` needs
 * `<ThemeProvider>` above the navigator.
 *
 * THE KEYBOARD (DEF-FLD-10611, MQ-021; PO report: the first tap on Save only
 * closed the keyboard, 2 of 2 tries). The scrolling body persists taps
 * (`"handled"`), so one tap on FF-20's Save saves while the keyboard is up,
 * and adjusts its insets for the keyboard on iOS; Android resizes the window
 * (`app.json` `softwareKeyboardLayoutMode: "resize"`), so the focused field
 * and the footer stay above it. The same approach and its reasons are in
 * `components/ScreenFrame.tsx`; the source scan
 * `tests/components/keyboardPersistTaps.test.ts` holds every container to it.
 *
 * ⚠ CRASHES: wrapped in `TelemetryErrorBoundary` when the app hands the job
 * services a crash capture; nothing provides one yet (same report).
 */
import { CommonActions, type NavigationProp, type ParamListBase, useNavigation, useRoute } from '@react-navigation/native';
import { type ComponentType, type ReactNode, useCallback, useLayoutEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ScrollView, View } from 'react-native';

import { EmptyState, TopBar } from '../../components';
import { useHistoryBack } from '../../navigation/back';
import { DOORS } from '../../navigation/doors';
import { doorAction, routeTo } from '../../navigation/routing';
import { carriesJob, type ScreenId } from '../../navigation/screens';
import { ThemeProvider, useTheme } from '../../theme';
import { TelemetryErrorBoundary } from '../../telemetry/TelemetryErrorBoundary';
import { useJobPort } from './JobPort';

/** True when a ThemeProvider is above. `useTheme` reads context unconditionally, then throws. */
function useHasTheme(): boolean {
  try {
    useTheme();
    return true;
  } catch {
    return false;
  }
}

/**
 * Follow a door the design draws on `from`. A door that is not in the doors
 * table throws — a screen cannot quietly grow a link the design does not have
 * (R98, R99); the doors test then presses every one that is.
 */
export function useDoor(from: ScreenId) {
  const navigation = useNavigation<NavigationProp<ParamListBase>>();
  // The job this screen is about — the route's, else the one open (`useOpenJob`'s order).
  const route = useRoute();
  const port = useJobPort();
  const routeParams = route.params as { workOrderId?: unknown; jobId?: unknown } | undefined;
  const named = [routeParams?.workOrderId, routeParams?.jobId].find((v): v is string => typeof v === 'string' && v !== '');
  const job = named ?? port?.openJobId ?? null;
  return useCallback(
    (to: ScreenId, given?: Record<string, unknown>) => {
      if (!DOORS[from].includes(to)) throw new Error(`${from} has no door to ${to} (navigation/doors.ts)`);
      // DEF-FLD-10578: a door to a job-scoped screen carries the job, so the
      // screen it opens is THIS job's — never "Not on this phone".
      const carry = job && carriesJob(to) && !(given && 'workOrderId' in given);
      const params = carry ? { workOrderId: job, ...given } : given;
      if (!params) {
        const action = doorAction(from, to);
        if (action) navigation.dispatch(action);
        return;
      }
      const target = routeTo(to);
      const nested = target.params as { screen: string; params?: { screen: string } } | undefined;
      const withParams =
        nested?.params !== undefined
          ? { ...nested, params: { ...nested.params, params } }
          : nested !== undefined
            ? { ...nested, params }
            : params;
      navigation.dispatch(CommonActions.navigate(target.name, withParams));
    },
    [from, navigation, job],
  );
}

export interface JobScreenProps {
  id: ScreenId;
  title: string;
  /** The drawing's back arrow: the door it follows when there is no history, and its name then. */
  back?: { to: ScreenId; label: string };
  trailing?: ReactNode;
  menu?: { to: ScreenId; label: string };
  footer?: ReactNode;
  /** A screen that draws its own body (a sheet) instead of the scrolling column. */
  bare?: boolean;
  children?: ReactNode;
}

function Frame(props: JobScreenProps) {
  const theme = useTheme();
  const navigation = useNavigation();
  const go = useDoor(props.id);
  useLayoutEffect(() => {
    navigation.setOptions({ headerShown: false });
  }, [navigation]);
  const back = props.back;
  const menu = props.menu;
  const history = useHistoryBack(back ? { label: back.label, follow: () => go(back.to) } : null);
  return (
    <View testID={`screen-${props.id}`} style={{ flex: 1, backgroundColor: theme.colors.page }}>
      {props.bare ? null : (
        <TopBar
          title={props.title}
          onBack={back ? history.onBack : undefined}
          backLabel={back ? history.label : undefined}
          backTestID={back ? `door-${back.to}` : undefined}
          trailing={props.trailing}
          onMenu={menu ? () => go(menu.to) : undefined}
          menuLabel={menu?.label}
          menuTestID={menu ? `door-${menu.to}` : undefined}
        />
      )}
      {props.bare ? (
        props.children
      ) : (
        <ScrollView keyboardShouldPersistTaps="handled" automaticallyAdjustKeyboardInsets style={{ flex: 1 }} contentContainerStyle={{ padding: theme.space[4], gap: theme.space[3] }}>
          {props.children}
        </ScrollView>
      )}
      {props.footer ? (
        <View
          style={{
            flexDirection: 'row',
            gap: theme.touch.clear,
            padding: theme.space[4],
            backgroundColor: theme.colors.card,
            borderTopWidth: theme.borderWidth.card,
            borderTopColor: theme.colors.border,
          }}
        >
          {props.footer}
        </View>
      ) : null}
    </View>
  );
}

function Fallback({ id }: { id: ScreenId }) {
  const { t } = useTranslation();
  return (
    <View testID={`screen-${id}`} style={{ flex: 1 }}>
      <EmptyState title={t('field.job.crashed.title')} helper={t('field.job.crashed.helper')} />
    </View>
  );
}

export function JobScreen(props: JobScreenProps) {
  return <Frame {...props} />;
}

/**
 * Registers a job screen: the theme (only when none is above — see the
 * header) and the crash boundary go AROUND the whole screen component, so a
 * screen's own hooks run inside both.
 */
export function jobScreen(id: ScreenId, Screen: ComponentType): ComponentType {
  function Registered() {
    const hasTheme = useHasTheme();
    const port = useJobPort();
    const body = port?.crashes ? (
      <TelemetryErrorBoundary capture={port.crashes} screen={id} fallback={<Fallback id={id} />}>
        <Screen />
      </TelemetryErrorBoundary>
    ) : (
      <Screen />
    );
    return hasTheme ? body : <ThemeProvider>{body}</ThemeProvider>;
  }
  Registered.displayName = `JobScreen(${id})`;
  return Registered;
}
