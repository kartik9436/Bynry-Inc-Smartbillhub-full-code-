/**
 * Button — three tiers, two sizes. The web kit's `Button` (07-frontend/src/
 * components/Button.tsx), same name and the same `variant` / `size` props
 * (decision log 2026-10-21, twelve conflicts, #10), rendered natively.
 *
 *   variant  primary   — the one thing the screen is for. Filled: the
 *                        brand-action orange in light (#e12e13, R100), light
 *                        on dark in dark, black in sunlight.
 *            secondary — outlined (the default, as on the web).
 *            danger    — outlined in the danger ink: a destructive commit or
 *                        a proceed-anyway (FF-27 "Disconnect anyway").
 *   size     default   — 56pt, the primary-action height.
 *            sm        — 48pt, the floor for any control.
 *   (B14 rule 45 / R39: primary 56 · any control 48.)
 *
 * The web's `ghost`, `ghost-danger`, `link` and `row` have no field-app use on
 * the boards and are not ported.
 *
 * A disabled button is still READ — "Tasks locked" on FF-16 tells the
 * technician why nothing happens — so it keeps its label and announces
 * `disabled`.
 */
import { Pressable, View } from 'react-native';
import type { ReactNode } from 'react';
import type { StyleProp, ViewStyle } from 'react-native';

import { useTheme } from '../theme';
import type { Theme } from '../theme';
import { textStyle } from './AppText';
import { AppText } from './AppText';

export type ButtonVariant = 'primary' | 'secondary' | 'danger';
export type ButtonSize = 'default' | 'sm';

export interface ButtonProps {
  children: string;
  onPress?: () => void;
  variant?: ButtonVariant;
  size?: ButtonSize;
  disabled?: boolean;
  /** Shown while the press is being handled; the button cannot be pressed. */
  busy?: boolean;
  /** A leading icon. */
  icon?: ReactNode;
  /** Stretch to share a row with siblings (flex 1). */
  grow?: boolean;
  accessibilityLabel?: string;
  accessibilityHint?: string;
  testID?: string;
  style?: StyleProp<ViewStyle>;
}

export function buttonHeight(theme: Theme, size: ButtonSize): number {
  return size === 'default' ? theme.touch.primary : theme.touch.control;
}

function colours(theme: Theme, variant: ButtonVariant, inactive: boolean) {
  const c = theme.colors;
  if (inactive) return { bg: c.disabledFill, fg: c.disabledText, border: c.disabledFill, width: 0 };
  if (variant === 'primary') return { bg: c.actionFill, fg: c.actionText, border: c.actionFill, width: 0 };
  if (variant === 'danger')
    return { bg: c.card, fg: c.dangerAction, border: c.dangerAction, width: theme.borderWidth.emphasis };
  return { bg: c.card, fg: c.text, border: c.controlBorder, width: theme.borderWidth.control };
}

export function Button({
  children,
  onPress,
  variant = 'secondary',
  size = 'default',
  disabled = false,
  busy = false,
  icon,
  grow = false,
  accessibilityLabel,
  accessibilityHint,
  testID,
  style,
}: ButtonProps) {
  const theme = useTheme();
  const inactive = disabled || busy;
  const k = colours(theme, variant, disabled);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? children}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled: inactive, busy }}
      disabled={inactive}
      onPress={onPress}
      testID={testID}
      style={({ pressed }) => [
        {
          minHeight: buttonHeight(theme, size),
          paddingHorizontal: theme.space[4],
          borderRadius: theme.radius.md,
          backgroundColor: k.bg,
          borderColor: k.border,
          borderWidth: k.width,
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'center',
          gap: theme.space[2],
          opacity: pressed ? PRESSED_OPACITY : 1,
        },
        grow ? { flexGrow: 1, flexBasis: 0 } : null,
        style,
      ]}
    >
      {icon ? <View accessible={false}>{icon}</View> : null}
      <AppText
        style={[
          textStyle(theme, size === 'default' ? 'section' : 'body', 'semibold'),
          { color: k.fg },
        ]}
        accessibilityRole="none"
      >
        {children}
      </AppText>
    </Pressable>
  );
}

/** Feedback on press. A ratio, not a colour or a size. */
export const PRESSED_OPACITY = 0.8;

/**
 * An icon-only button: 48pt square (B14 rule 45: icon-only button 48pt),
 * and a `label` that is REQUIRED, because an icon-only control with no
 * accessible name is a silent control to a screen reader.
 */
export function IconButton(props: {
  label: string;
  onPress?: () => void;
  children: ReactNode;
  disabled?: boolean;
  outlined?: boolean;
  testID?: string;
}) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={props.label}
      accessibilityState={{ disabled: props.disabled === true }}
      disabled={props.disabled}
      onPress={props.onPress}
      testID={props.testID}
      style={({ pressed }) => ({
        width: theme.touch.iconButton,
        height: theme.touch.iconButton,
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: theme.radius.md,
        borderWidth: props.outlined ? theme.borderWidth.control : 0,
        borderColor: theme.colors.controlBorder,
        backgroundColor: props.outlined ? theme.colors.card : 'transparent',
        opacity: props.disabled ? DISABLED_OPACITY : pressed ? PRESSED_OPACITY : 1,
      })}
    >
      {props.children}
    </Pressable>
  );
}

/** An icon button that cannot be pressed. A ratio, not a colour. */
export const DISABLED_OPACITY = 0.4;
