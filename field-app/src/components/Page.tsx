/**
 * Page — the body every screen on the boards sits in: the page colour, a
 * 16pt gutter, blocks 12 apart, and — where the board draws one — a FOOTER
 * pinned to the bottom with a rule above it (FF-07 *Continue*, FF-08 *Skip ·
 * Open my day*, FF-56 *Check the code*, FF-57 *Save and sign in*).
 *
 * Built once so no screen writes its own padding, gap or footer border
 * (B14 rule 43; the no-literals scan holds the screen folders to it).
 *
 * The keyboard: taps persist (`"handled"`) and iOS insets adjust, the same
 * rule as `ScreenFrame` and for the same reason (DEF-FLD-10611).
 */
import type { ReactNode } from 'react';
import { ScrollView, View } from 'react-native';
import type { StyleProp, ViewStyle } from 'react-native';

import { useTheme } from '../theme';

export interface PageProps {
  children?: ReactNode;
  /** Pinned under the scrolling body. */
  footer?: ReactNode;
  /** `false` for a body that does not scroll (the splash). */
  scroll?: boolean;
  /** The page colour by default; a screen may ask for the card colour (FF-02…FF-05 are white). */
  surface?: 'page' | 'card';
  /** Centre the body vertically (the splash, the lock cover). */
  centred?: boolean;
  testID?: string;
  contentStyle?: StyleProp<ViewStyle>;
}

export function Page(props: PageProps) {
  const theme = useTheme();
  const c = theme.colors;
  const bg = props.surface === 'card' ? c.card : c.page;
  const body: ViewStyle = {
    padding: theme.space[4],
    gap: theme.space[3],
    flexGrow: 1,
    justifyContent: props.centred ? 'center' : 'flex-start',
  };
  return (
    <View style={{ flex: 1, backgroundColor: bg }} testID={props.testID}>
      {props.scroll === false ? (
        <View style={[body, { flex: 1 }, props.contentStyle]}>{props.children}</View>
      ) : (
        <ScrollView style={{ flex: 1 }} contentContainerStyle={[body, props.contentStyle]} keyboardShouldPersistTaps="handled" automaticallyAdjustKeyboardInsets>
          {props.children}
        </ScrollView>
      )}
      {props.footer ? (
        <View
          style={{
            flexDirection: 'row',
            gap: theme.touch.clear,
            padding: theme.space[4],
            borderTopWidth: theme.borderWidth.divider,
            borderTopColor: c.border,
            backgroundColor: bg,
          }}
        >
          {props.footer}
        </View>
      ) : null}
    </View>
  );
}
