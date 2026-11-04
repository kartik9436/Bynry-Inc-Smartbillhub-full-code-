/**
 * ListRow — one line in a card or a list: a label, an optional second line,
 * a value on the right, and a chevron when it opens something. FF-34 DEBRIEF
 * ("Labour · 1h 12m"), FF-15/54 WORK ("Readings · 1 flagged ›"), FF-25
 * SERVICE ("Meter · W-4471"), FF-51's settings rows.
 *
 * A row that opens something is a button and is at least 48pt tall (B14 rule
 * 45); a row that only states a fact is text.
 */
import type { ReactNode } from 'react';
import { Pressable, View } from 'react-native';

import { useTheme } from '../theme';
import { AppText } from './AppText';
import { Glyph } from './Glyph';

export interface ListRowProps {
  label: string;
  /** A second, muted line under the label. */
  detail?: string;
  /** What sits on the right: a figure, or a `StatusChip`. */
  value?: ReactNode;
  /** Something before the label (a check, an avatar). */
  leading?: ReactNode;
  onPress?: () => void;
  /** Draw a rule above this row (every row after the first in a card). */
  divider?: boolean;
  disabled?: boolean;
  accessibilityHint?: string;
  testID?: string;
}

export function ListRow(props: ListRowProps) {
  const theme = useTheme();
  const content = (
    <>
      {props.leading ? <View accessible={false}>{props.leading}</View> : null}
      <View style={{ flexGrow: 1, flexShrink: 1 }}>
        <AppText variant="body">{props.label}</AppText>
        {props.detail ? (
          <AppText variant="label" tone="muted">
            {props.detail}
          </AppText>
        ) : null}
      </View>
      {typeof props.value === 'string' ? (
        <AppText variant="body" weight="heavy">
          {props.value}
        </AppText>
      ) : (
        (props.value ?? null)
      )}
      {props.onPress ? <Glyph name="forward" colour={theme.colors.textMuted} /> : null}
    </>
  );
  const frame = {
    minHeight: theme.touch.control,
    flexDirection: 'row' as const,
    alignItems: 'center' as const,
    gap: theme.space[3],
    borderTopWidth: props.divider ? theme.borderWidth.divider : 0,
    borderTopColor: theme.colors.divider,
  };
  const valueText = typeof props.value === 'string' ? props.value : undefined;
  const a11yLabel = [props.label, props.detail, valueText].filter(Boolean).join(', ');
  if (props.onPress) {
    return (
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={a11yLabel}
        accessibilityHint={props.accessibilityHint}
        accessibilityState={{ disabled: props.disabled === true }}
        disabled={props.disabled}
        onPress={props.onPress}
        testID={props.testID}
        style={frame}
      >
        {content}
      </Pressable>
    );
  }
  return (
    <View testID={props.testID} accessible accessibilityRole="text" accessibilityLabel={a11yLabel} style={frame}>
      {content}
    </View>
  );
}
