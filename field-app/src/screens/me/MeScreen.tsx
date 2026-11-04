/**
 * The frame every "me" screen is drawn in: the top bar the boards draw (the
 * drawer button top left on the screens the menu opens — FF-42, FF-44, FF-48,
 * FF-49 — and a back arrow on the ones pushed from them), the page, and a
 * footer for the one action the screen is for (FF-47 *Submit the day*, FF-50
 * *Sync now*).
 *
 * The board's own top bar replaces the navigator's header, so the title is
 * drawn once, where the drawing puts it. Every door is pressed through
 * `useDoor`, which dispatches the door table's own action
 * (`navigation/routing.ts doorAction`) — a door goes to its ADDRESS, so the
 * doors test can hold it to the table.
 *
 * THE BACK ARROW IS THE ONE EXCEPTION (DEF-FLD-10607; PO 2026-10-26, *"A for
 * back button"*): it goes back through history, and follows its drawn door
 * only when there is none (`navigation/back.tsx`).
 */
import { useNavigation } from '@react-navigation/native';
import { type ReactNode, useCallback, useLayoutEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ScrollView, View } from 'react-native';

import { AppText, TopBar } from '../../components';
import { useHistoryBack } from '../../navigation/back';
import { doorAction } from '../../navigation/routing';
import type { ScreenId } from '../../navigation/screens';
import { TelemetryErrorBoundary } from '../../telemetry/TelemetryErrorBoundary';
import { useTheme } from '../../theme';
import { useMeServices } from './services';

/** Follow a door from `from`: the table's own action, by address. */
export function useDoor(from: ScreenId): (to: ScreenId) => void {
  const navigation = useNavigation();
  return useCallback(
    (to: ScreenId) => {
      const action = doorAction(from, to);
      if (action) navigation.dispatch(action);
    },
    [from, navigation],
  );
}

export interface MeScreenProps {
  id: ScreenId;
  title: string;
  /** `drawer` — the menu button (opens FF-09); `{ back }` — a back arrow that is the door to that screen. */
  leading?: 'drawer' | { back: ScreenId };
  trailing?: ReactNode;
  footer?: ReactNode;
  /** Above the scrolling body, under the bar (FF-47's Today · Week tabs). */
  header?: ReactNode;
  children?: ReactNode;
}

export function MeScreen(props: MeScreenProps) {
  const theme = useTheme();
  const { t } = useTranslation();
  const navigation = useNavigation();
  const door = useDoor(props.id);
  const { crash } = useMeServices();

  useLayoutEffect(() => {
    navigation.setOptions({ headerShown: false });
  }, [navigation]);

  const leading = props.leading;
  const back = typeof leading === 'object' ? leading.back : null;
  // DEF-FLD-10607: back through history; the drawn door only without it.
  const history = useHistoryBack(back ? { label: t('field.me.back'), follow: () => door(back) } : null);
  const body = (
    <View testID={`screen-${props.id}`} style={{ flex: 1, backgroundColor: theme.colors.page }}>
      <TopBar
        title={props.title}
        onOpenDrawer={leading === 'drawer' ? () => door('FF-09') : undefined}
        drawerLabel={t('field.nav.menu')}
        drawerTestID="door-FF-09"
        onBack={back ? history.onBack : undefined}
        backLabel={back ? history.label : t('field.me.back')}
        backTestID={back ? `door-${back}` : undefined}
        trailing={props.trailing}
      />
      {props.header ?? null}
      <ScrollView
        keyboardShouldPersistTaps="handled"
        style={{ flex: 1 }}
        contentContainerStyle={{ padding: theme.space[4], gap: theme.space[3] }}
        testID={`screen-${props.id}-body`}
      >
        {props.children}
      </ScrollView>
      {props.footer ? (
        <View
          style={{
            flexDirection: 'row',
            gap: theme.touch.clear,
            padding: theme.space[4],
            borderTopWidth: theme.borderWidth.card,
            borderTopColor: theme.colors.border,
            backgroundColor: theme.colors.page,
          }}
        >
          {props.footer}
        </View>
      ) : null}
    </View>
  );
  return crash ? (
    <TelemetryErrorBoundary capture={crash} screen={props.id}>
      {body}
    </TelemetryErrorBoundary>
  ) : (
    body
  );
}

/** The sheet-shaped frame FF-45, FF-53 and the Switch sheet draw: a title, the content, and the actions at the foot. */
export function MeSheetScreen(props: { id: ScreenId; title: string; children?: ReactNode; footer?: ReactNode }) {
  const theme = useTheme();
  const navigation = useNavigation();
  const { crash } = useMeServices();

  useLayoutEffect(() => {
    navigation.setOptions({ headerShown: false });
  }, [navigation]);

  const body = (
    <View testID={`screen-${props.id}`} style={{ flex: 1, backgroundColor: theme.colors.card }}>
      <ScrollView keyboardShouldPersistTaps="handled" style={{ flex: 1 }} contentContainerStyle={{ padding: theme.space[4], gap: theme.space[3] }}>
        <AppText variant="title">{props.title}</AppText>
        {props.children}
      </ScrollView>
      {props.footer ? <View style={{ padding: theme.space[4], gap: theme.touch.clear }}>{props.footer}</View> : null}
    </View>
  );
  return crash ? (
    <TelemetryErrorBoundary capture={crash} screen={props.id}>
      {body}
    </TelemetryErrorBoundary>
  ) : (
    body
  );
}
