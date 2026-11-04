/**
 * SheetScreen — a bottom sheet that IS a screen: FF-18 *Add a step* and FF-24
 * *Parts used* are routes of their own (they have doors in and out), drawn as
 * a panel over the dimmed step they belong to.
 *
 * Why not `Sheet`: `Sheet` is a React Native `Modal`, which floats above the
 * whole app — pushed under a route, it would stay on top of the screen the
 * technician goes to next. This draws the same anatomy (dimmed context above,
 * grab handle, title, content, a footer of actions) INSIDE the route, so the
 * native stack owns it like any other screen.
 *
 * The dimmed area is a real button with a name (it closes the sheet), as
 * `Sheet`'s is; the context line above the panel is what the drawing shows
 * dimmed ("7 · Photograph new meter fitted").
 */
import type { ReactNode } from 'react';
import { Pressable, ScrollView, View } from 'react-native';

import { useTheme } from '../theme';
import { AppText } from './AppText';

export interface SheetScreenProps {
  title: string;
  /** The accessible name of the dimmed area ("Close"). */
  closeLabel: string;
  onClose: () => void;
  /** Drawn dimmed above the panel: what the sheet is about. */
  context?: ReactNode;
  /** Something on the title's right (FF-24's scan button). */
  trailing?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  testID?: string;
  closeTestID?: string;
}

export function SheetScreen(props: SheetScreenProps) {
  const theme = useTheme();
  const c = theme.colors;
  return (
    <View testID={props.testID} style={{ flex: 1, backgroundColor: c.page }}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={props.closeLabel}
        onPress={props.onClose}
        testID={props.closeTestID}
        style={{ flexGrow: 1, minHeight: theme.touch.control, padding: theme.space[4], backgroundColor: c.surface }}
      >
        {props.context ? <View style={{ opacity: SHEET_CONTEXT_OPACITY }}>{props.context}</View> : null}
      </Pressable>
      <View
        style={{
          backgroundColor: c.card,
          borderTopWidth: theme.borderWidth.card,
          borderTopColor: c.border,
          paddingHorizontal: theme.space[4],
          paddingBottom: theme.space[4],
          maxHeight: '85%',
        }}
      >
        <View
          accessible={false}
          style={{
            alignSelf: 'center',
            width: theme.space[8] + theme.space[2],
            height: theme.space[1],
            marginVertical: theme.space[3],
            backgroundColor: c.border,
          }}
        />
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[2], marginBottom: theme.space[4] }}>
          <AppText variant="title" style={{ flexGrow: 1, flexShrink: 1 }}>
            {props.title}
          </AppText>
          {props.trailing ?? null}
        </View>
        <ScrollView keyboardShouldPersistTaps="handled" automaticallyAdjustKeyboardInsets contentContainerStyle={{ gap: theme.space[3] }}>{props.children}</ScrollView>
        {props.footer ? (
          <View style={{ flexDirection: 'row', gap: theme.touch.clear, marginTop: theme.space[4] }}>{props.footer}</View>
        ) : null}
      </View>
    </View>
  );
}

/** The dimmed context above the panel. A ratio, not a colour. */
export const SHEET_CONTEXT_OPACITY = 0.6;
