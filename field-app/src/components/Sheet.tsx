/**
 * Sheet — the bottom sheet FF-18 (Add a step) draws: the page dimmed behind,
 * a grab handle, a title, the content, and a footer of actions.
 *
 * Three ways out, one for each kind of user: tapping the dimmed page (a real
 * button with a name), Android's back button (`onRequestClose`), and the
 * iOS VoiceOver escape gesture (`onAccessibilityEscape`) — needed because the
 * panel is `accessibilityViewIsModal`, which hides the dimmed page from
 * VoiceOver on purpose so focus cannot wander behind the sheet.
 */
import type { ReactNode } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { useTheme } from '../theme';
import { AppText } from './AppText';

export interface SheetProps {
  visible: boolean;
  onClose: () => void;
  title: string;
  /** The accessible name of the dimmed page behind the sheet ("Close"). */
  closeLabel: string;
  children?: ReactNode;
  /** The action row (Cancel / Add step). */
  footer?: ReactNode;
  testID?: string;
}

export function Sheet(props: SheetProps) {
  const theme = useTheme();
  const c = theme.colors;
  return (
    <Modal
      visible={props.visible}
      transparent
      animationType="slide"
      onRequestClose={props.onClose}
      testID={props.testID}
    >
      <View style={{ flex: 1, justifyContent: 'flex-end' }}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={props.closeLabel}
          onPress={props.onClose}
          testID={props.testID ? `${props.testID}-scrim` : undefined}
          style={[StyleSheet.absoluteFill, { backgroundColor: c.scrim }]}
        />
        <View
          accessibilityViewIsModal
          onAccessibilityEscape={props.onClose}
          testID={props.testID ? `${props.testID}-panel` : undefined}
          style={{
            backgroundColor: c.card,
            borderTopLeftRadius: theme.radius.pill,
            borderTopRightRadius: theme.radius.pill,
            borderTopWidth: theme.borderWidth.card,
            borderTopColor: c.border,
            paddingHorizontal: theme.space[4],
            paddingBottom: theme.space[4],
            maxHeight: '90%',
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
              borderRadius: theme.radius.sm,
            }}
          />
          <AppText variant="title" style={{ marginBottom: theme.space[4] }}>
            {props.title}
          </AppText>
          <ScrollView keyboardShouldPersistTaps="handled" automaticallyAdjustKeyboardInsets>{props.children}</ScrollView>
          {props.footer ? (
            <View style={{ flexDirection: 'row', gap: theme.touch.clear, marginTop: theme.space[4] }}>
              {props.footer}
            </View>
          ) : null}
        </View>
      </View>
    </Modal>
  );
}
