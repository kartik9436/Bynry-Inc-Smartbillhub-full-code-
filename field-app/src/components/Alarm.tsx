/**
 * The emergency surface FF-43 draws — the whole page in the danger ink, the
 * words in the card colour on it, panels outlined rather than filled, and two
 * kinds of button: SOLID (the card colour with danger-ink words — *Acknowledge*,
 * the one thing the screen is for) and OUTLINE (*Call dispatch*, *Cannot
 * attend*). The tablet board draws the same surface, so it is a component.
 *
 * Every colour is a theme token: in light the page is danger-700 with white
 * words; in dark the Night board's danger ink with the dark card's words; in
 * sunlight the Sunlight board's danger with white. Each pair passes 4.5:1
 * (the theme walk test measures them).
 */
import type { ReactNode } from 'react';
import { Pressable, Text, View } from 'react-native';

import { useTheme } from '../theme';
import { PRESSED_OPACITY } from './Button';
import { textStyle } from './AppText';
import type { TextVariant, TextWeight } from './AppText';

export function AlarmSurface(props: { children: ReactNode; testID?: string }) {
  const theme = useTheme();
  return (
    <View testID={props.testID} style={{ flex: 1, backgroundColor: theme.colors.dangerAction }}>
      {props.children}
    </View>
  );
}

/** Words on the alarm surface. */
export function AlarmText(props: {
  children: ReactNode;
  variant?: TextVariant;
  weight?: TextWeight;
  center?: boolean;
  kicker?: boolean;
  testID?: string;
}) {
  const theme = useTheme();
  const variant = props.variant ?? 'body';
  return (
    <Text
      testID={props.testID}
      accessibilityRole={variant === 'title' || props.kicker ? 'header' : undefined}
      style={[
        textStyle(theme, variant, props.weight),
        { color: theme.colors.card, textAlign: props.center ? 'center' : 'auto' },
        props.kicker
          ? { textTransform: 'uppercase', letterSpacing: theme.tracking.kicker * theme.type[variant] }
          : null,
      ]}
    >
      {props.children}
    </Text>
  );
}

/** A panel on the alarm surface: outlined in the card colour, transparent. */
export function AlarmPanel(props: { children: ReactNode; testID?: string }) {
  const theme = useTheme();
  return (
    <View
      testID={props.testID}
      style={{
        borderWidth: theme.borderWidth.card,
        borderColor: theme.colors.card,
        borderRadius: theme.radius.lg,
        padding: theme.space[4],
        gap: theme.space[2],
      }}
    >
      {props.children}
    </View>
  );
}

/** The one card that is filled — the countdown: card colour, danger-ink figure. */
export function AlarmCallout(props: { label: string; figure: string; testID?: string }) {
  const theme = useTheme();
  const c = theme.colors;
  return (
    <View
      testID={props.testID}
      accessible
      accessibilityRole="timer"
      accessibilityLabel={`${props.label} ${props.figure}`}
      style={{ backgroundColor: c.card, borderRadius: theme.radius.lg, padding: theme.space[4], alignItems: 'center' }}
    >
      <Text style={[textStyle(theme, 'label'), { color: c.dangerAction }]}>{props.label}</Text>
      {/* The board draws this figure far larger; it stays on the type ramp (B14 rule 45). */}
      <Text style={[textStyle(theme, 'title', 'heavy'), { color: c.dangerAction, fontVariant: ['tabular-nums'] }]}>
        {props.figure}
      </Text>
    </View>
  );
}

export function AlarmButton(props: {
  children: string;
  onPress?: () => void;
  variant?: 'solid' | 'outline';
  disabled?: boolean;
  grow?: boolean;
  testID?: string;
}) {
  const theme = useTheme();
  const c = theme.colors;
  const solid = (props.variant ?? 'outline') === 'solid';
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={props.children}
      accessibilityState={{ disabled: props.disabled === true }}
      disabled={props.disabled}
      onPress={props.onPress}
      testID={props.testID}
      style={({ pressed }) => [
        {
          minHeight: solid ? theme.touch.primary : theme.touch.control,
          paddingHorizontal: theme.space[4],
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: theme.radius.md,
          borderWidth: theme.borderWidth.control,
          borderColor: c.card,
          backgroundColor: solid ? c.card : c.dangerAction,
          opacity: pressed ? PRESSED_OPACITY : 1,
        },
        props.grow ? { flexGrow: 1, flexBasis: 0 } : null,
      ]}
    >
      <Text style={[textStyle(theme, solid ? 'section' : 'body', 'semibold'), { color: solid ? c.dangerAction : c.card }]}>
        {props.children}
      </Text>
    </Pressable>
  );
}
