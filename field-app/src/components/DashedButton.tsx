/**
 * DashedButton — the boards' dashed "add one more" control: FF-17 *+ Add a
 * step*, FF-20 *+ Add a reading*, FF-23 *+ Add material*, and the camera tile
 * on a step (*Two more*, FF-17) and on a missing photograph. Drawn dashed so
 * it reads as a place for something not there yet, never as a filled action.
 *
 * At least 48pt (B14 rule 45); `tall` is the camera tile's height, the same as
 * a small photograph's so it sits in a strip beside them.
 */
import type { ReactNode } from 'react';
import { Pressable, View } from 'react-native';

import { useTheme } from '../theme';
import { textStyle } from './AppText';
import { AppText } from './AppText';
import { PRESSED_OPACITY } from './Button';

export interface DashedButtonProps {
  label: string;
  onPress?: () => void;
  icon?: ReactNode;
  disabled?: boolean;
  /** Fill the remaining width of a row (the camera tile in a strip). */
  grow?: boolean;
  accessibilityLabel?: string;
  testID?: string;
}

export function DashedButton(props: DashedButtonProps) {
  const theme = useTheme();
  const c = theme.colors;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={props.accessibilityLabel ?? props.label}
      accessibilityState={{ disabled: props.disabled === true }}
      disabled={props.disabled}
      onPress={props.onPress}
      testID={props.testID}
      style={({ pressed }) => [
        {
          minHeight: theme.touch.primary,
          paddingHorizontal: theme.space[4],
          borderWidth: theme.borderWidth.emphasis,
          borderStyle: 'dashed',
          borderColor: c.controlBorder,
          backgroundColor: props.disabled ? c.disabledFill : c.surface,
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'center',
          gap: theme.space[2],
          opacity: pressed ? PRESSED_OPACITY : 1,
        },
        props.grow ? { flexGrow: 1, flexBasis: 0 } : null,
      ]}
    >
      {props.icon ? <View accessible={false}>{props.icon}</View> : null}
      <AppText
        accessibilityRole="none"
        style={[textStyle(theme, 'body', 'semibold'), { color: props.disabled ? c.disabledText : c.textMuted }]}
      >
        {props.label}
      </AppText>
    </Pressable>
  );
}
