/**
 * ScreenFrame — the page every pushed screen is drawn on: a scrolling column
 * of cards on the page colour, and, when the screen has one, the action bar
 * pinned to the bottom edge with a rule above it (FF-25 *Back to the job*,
 * FF-29 *Done*, FF-34 *Close job*, FF-37 *Cancel · Send*). Drawn on nearly
 * every board, so it is a component (B14 rule 43) rather than a View each
 * screen re-styles.
 *
 * `footer` takes the buttons; two buttons share the row (`Button grow`).
 * `header` sits above the scroll and does not move (FF-29's labour total,
 * FF-41's search box).
 *
 * THE KEYBOARD (DEF-FLD-10611, MQ-021). With the keyboard open, a ScrollView
 * left at React Native's default (`keyboardShouldPersistTaps` `'never'`)
 * swallows the first tap — it only closes the keyboard, and Save had to be
 * pressed twice. So the scroll takes `"handled"`: a tap on a button reaches
 * the button, a tap on empty page still closes the keyboard. To keep the
 * focused field and the controls under it in view:
 *   - iOS — `automaticallyAdjustKeyboardInsets`: the scroll's bottom inset
 *     grows by the keyboard's height and the focused field is scrolled up.
 *   - Android — `app.json` `android.softwareKeyboardLayoutMode: "resize"`
 *     (adjustResize; Expo's default, pinned so nobody changes it unseen): the
 *     window shrinks above the keyboard, the footer rides on top of it, and
 *     the native scroll keeps the focused child visible.
 * Chosen over a `KeyboardAvoidingView` because it adds no wrapper and no
 * per-platform offset to keep in step with the header. Every scrolling
 * container in `src/` is held to the tap rule by
 * `tests/components/keyboardPersistTaps.test.ts`.
 */
import type { ReactNode } from 'react';
import { ScrollView, View } from 'react-native';

import { useTheme } from '../theme';
import { Kicker } from './AppText';

export interface ScreenFrameProps {
  children?: ReactNode;
  header?: ReactNode;
  footer?: ReactNode;
  testID?: string;
}

export function ScreenFrame(props: ScreenFrameProps) {
  const theme = useTheme();
  const c = theme.colors;
  return (
    <View testID={props.testID} style={{ flex: 1, backgroundColor: c.page }}>
      {props.header ? (
        <View
          style={{
            backgroundColor: c.card,
            borderBottomColor: c.border,
            borderBottomWidth: theme.borderWidth.divider,
            paddingHorizontal: theme.space[4],
            paddingVertical: theme.space[3],
            gap: theme.space[2],
          }}
        >
          {props.header}
        </View>
      ) : null}
      <ScrollView keyboardShouldPersistTaps="handled" automaticallyAdjustKeyboardInsets style={{ flex: 1 }} contentContainerStyle={{ padding: theme.space[3], gap: theme.space[3] }}>
        {props.children}
      </ScrollView>
      {props.footer ? (
        <View
          style={{
            backgroundColor: c.card,
            borderTopColor: c.border,
            borderTopWidth: theme.borderWidth.divider,
            padding: theme.space[3],
            flexDirection: 'row',
            gap: theme.space[2],
          }}
        >
          {props.footer}
        </View>
      ) : null}
    </View>
  );
}

/** A small muted heading between groups of cards ("FOR THIS JOB"). */
export function GroupLabel(props: { children: string }) {
  const theme = useTheme();
  return (
    <View style={{ paddingHorizontal: theme.space[1], paddingTop: theme.space[2] }}>
      <Kicker>{props.children}</Kicker>
    </View>
  );
}
