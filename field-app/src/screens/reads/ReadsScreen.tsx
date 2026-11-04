/**
 * The frame every reading screen is built in, and the two hooks they share.
 *
 *  - `readsScreen(id, Body)` makes the routed component. It wraps the body in
 *    the telemetry boundary (a crash is recorded by component NAME, never with
 *    a customer's data) and gives it `screen-<id>`, the address tests find it
 *    by. When the app root has not mounted the reading services, it renders
 *    the PLACEHOLDER — with its doors — rather than a screen that cannot read
 *    its store: the route stays walkable and nothing pretends to work.
 *  - `ScreenBody` is the scrolling page with its action bar pinned under it.
 *  - `useGo()` opens a screen by its id, with the record it is about. A door
 *    button carries `door-<id>` so the doors test presses the real control.
 */
import { CommonActions, DrawerActions, useNavigation, useRoute } from '@react-navigation/native';
import { type ComponentType, type ReactNode, useCallback, useEffect, useLayoutEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ScrollView, useWindowDimensions, View } from 'react-native';

import { AppText, Glyph, IconButton } from '../../components';
import * as walkQ from '../../db/queries/readsWalk';
import { useHistoryBack } from '../../navigation/back';
import { isTabletSize } from '../../navigation/layout';
import { routeTo } from '../../navigation/routing';
import type { ScreenId } from '../../navigation/screens';
import { TelemetryErrorBoundary } from '../../telemetry/TelemetryErrorBoundary';
import { useTheme } from '../../theme';
import { PlaceholderScreen } from '../PlaceholderScreen';
import { useOptionalReads, useReads } from './services';

/** The record a reading screen is about. Every field optional: a screen opened
 *  with none of them (the doors test, a menu entry) picks the reader's first. */
export interface ReadsParams {
  routeId?: string;
  stopId?: string;
  readId?: string;
  /** A scanned or typed code (RW-18, RW-19, RW-20). */
  code?: string;
  /** RW-23's tab, RW-28's period. */
  tab?: string;
  /** RW-14 Retake: the place, in the unsaved reading's photos, the new photo takes. */
  photo?: string;
}

function nest(target: { name: string; params?: object }, leaf: object): { name: string; params?: object } {
  const walk = (p: Record<string, unknown> | undefined): Record<string, unknown> | undefined => {
    if (!p) return undefined;
    if (p.params && typeof p.params === 'object') return { ...p, params: walk(p.params as Record<string, unknown>) };
    return { ...p, params: leaf };
  };
  return { name: target.name, params: walk(target.params as Record<string, unknown> | undefined) };
}

export function useGo(): (id: ScreenId, params?: ReadsParams) => void {
  const navigation = useNavigation();
  return useCallback(
    (id: ScreenId, params?: ReadsParams) => {
      const target = params ? nest(routeTo(id), params) : routeTo(id);
      navigation.dispatch(CommonActions.navigate(target.name, target.params));
    },
    [navigation],
  );
}

export function useParams(): ReadsParams {
  const route = useRoute();
  return (route.params ?? {}) as ReadsParams;
}

/** Re-read whenever the screen comes back into view or anything was written. */
export function useLive<T>(read: () => T, deps: readonly unknown[]): T {
  const { version } = useReads();
  const navigation = useNavigation();
  const [tick, setTick] = useState(0);
  useEffect(() => navigation.addListener('focus', () => setTick((t) => t + 1)), [navigation]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const [value, setValue] = useState<T>(read);
  useEffect(() => {
    setValue(read());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version, tick, ...deps]);
  return value;
}

export function useTablet(): boolean {
  const { width, height } = useWindowDimensions();
  return isTabletSize(width, height);
}

export function readsScreen(id: ScreenId, Body: ComponentType): ComponentType {
  function Screen() {
    const ctx = useOptionalReads();
    if (!ctx) return <PlaceholderScreen id={id} />;
    return (
      <TelemetryErrorBoundary capture={ctx.services.crash} screen={id} fallback={<Failed id={id} />}>
        <View style={{ flex: 1 }} testID={`screen-${id}`}>
          <ReadsHeader id={id} />
          <Body />
        </View>
      </TelemetryErrorBoundary>
    );
  }
  Screen.displayName = `Reads(${id})`;
  return Screen;
}

/**
 * The header's left-hand control, as the boards draw it: a back arrow, or the
 * menu on RW-28 (opened from the menu, drawn as a top-level page). Every back
 * row names the board's own link (`navigation/doors.ts`).
 *
 * BACK GOES WHERE YOU CAME FROM (DEF-FLD-10607; PO 2026-10-26, *"A for back
 * button"*): the arrow pops back through history; the door named here is
 * followed only without history, carrying the route, stop or read it is
 * about (`navigation/back.tsx`). ⚠ Until then this said the stack's back
 * "goes wherever the reader came from rather than to the drawn door" and
 * chose the drawn door — the judgment the ruling superseded.
 */
export const READS_HEADER: Partial<Record<ScreenId, { back: ScreenId } | { menu: true }>> = {
  'RW-02': { back: 'RW-01' },
  'RW-05': { back: 'RW-02' },
  'RW-06': { back: 'RW-05' },
  'RW-12': { back: 'RW-06' },
  'RW-15': { back: 'RW-09' },
  'RW-16': { back: 'RW-15' },
  'RW-25': { back: 'RW-22' },
  'RW-28': { menu: true },
};

function ReadsHeader({ id }: { id: ScreenId }) {
  const { t } = useTranslation();
  const navigation = useNavigation();
  const { s } = useReads();
  const params = useParams();
  const go = useGo();
  const door = READS_HEADER[id];
  const meter = params.readId ? walkQ.meter(s, params.readId) : undefined;
  const stop = params.stopId ? walkQ.stop(s, params.stopId) : undefined;
  const routeId = params.routeId ?? meter?.route_id ?? stop?.route_id;
  const stopId = params.stopId ?? meter?.stop_id;
  const readId = params.readId;
  const to = door && 'back' in door ? door.back : null;
  // DEF-FLD-10607: back through history; the drawn door only without it.
  const { onBack, label } = useHistoryBack(
    to
      ? {
          label: t('field.reads.common.back'),
          follow: () => {
            const carry: ReadsParams | undefined =
              to === 'RW-06' ? (stopId ? { stopId } : undefined)
              : to === 'RW-09' || to === 'RW-15' ? (readId ? { readId } : undefined)
              : to === 'RW-01' ? undefined
              : routeId ? { routeId } : undefined;
            go(to, carry);
          },
        }
      : null,
  );
  useLayoutEffect(() => {
    if (!door) return;
    if ('menu' in door) {
      navigation.setOptions({
        headerLeft: () => (
          <IconButton label={t('field.nav.menu')} onPress={() => navigation.dispatch(DrawerActions.openDrawer())} testID="door-FF-09">
            <Glyph name="drawer" />
          </IconButton>
        ),
      });
      return;
    }
    navigation.setOptions({
      headerBackVisible: false,
      headerLeft: () => (
        <IconButton label={label} onPress={onBack} testID={`door-${door.back}`}>
          <Glyph name="back" />
        </IconButton>
      ),
    });
  }, [navigation, door, t, onBack, label]);
  return null;
}

function Failed({ id }: { id: ScreenId }) {
  const { t } = useTranslation();
  return (
    <View testID={`screen-${id}-failed`} style={{ flex: 1, justifyContent: 'center' }}>
      <AppText variant="section" style={{ textAlign: 'center' }}>
        {t('field.reads.common.failed')}
      </AppText>
    </View>
  );
}

/** A scrolling page with its acts pinned under it (every RW board). */
export function ScreenBody(props: { children: ReactNode; bar?: ReactNode; scroll?: boolean; testID?: string }) {
  const theme = useTheme();
  const content = { padding: theme.space[3], gap: theme.space[3] };
  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.page }} testID={props.testID}>
      {props.scroll === false ? (
        <View style={[{ flex: 1 }, content]}>{props.children}</View>
      ) : (
        <ScrollView keyboardShouldPersistTaps="handled" automaticallyAdjustKeyboardInsets style={{ flex: 1 }} contentContainerStyle={content}>
          {props.children}
        </ScrollView>
      )}
      {props.bar}
    </View>
  );
}
