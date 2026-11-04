/**
 * Meter — a horizontal bar split into parts: FF-47 *Jobs · Travel · Admin*
 * (three tones side by side), FF-50 *Photos 24 of 62* (one tone against the
 * empty track). The parts are drawn in proportion to their values; the words
 * beside the bar carry the figures, and `label` gives the screen reader the
 * same sentence.
 */
import { View } from 'react-native';

import { useTheme } from '../theme';
import type { StatusTone } from '../theme';

export interface MeterPart {
  value: number;
  tone: StatusTone;
}

export interface MeterProps {
  parts: readonly MeterPart[];
  /** The whole bar. Defaults to the sum of the parts (a full bar). */
  total?: number;
  label: string;
  testID?: string;
}

export function Meter({ parts, total, label, testID }: MeterProps) {
  const theme = useTheme();
  const shown = parts.filter((p) => p.value > 0);
  const sum = shown.reduce((n, p) => n + p.value, 0);
  const whole = Math.max(total ?? sum, sum);
  const empty = whole - sum;
  return (
    <View
      testID={testID}
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      accessibilityValue={{ min: 0, max: whole, now: sum }}
      style={{
        flexDirection: 'row',
        height: theme.space[2],
        gap: shown.length > 1 ? theme.space[1] : 0,
        backgroundColor: theme.colors.divider,
        overflow: 'hidden',
      }}
    >
      {shown.map(({ value: share, tone }, i) => (
        // Destructured on purpose: Reanimated's Babel plugin rewrites any
        // `x.value` read inside a `style` object as a shared-value access.
        <View
          key={i}
          testID={testID ? `${testID}-part-${tone}` : undefined}
          style={{ flexGrow: share, flexBasis: 0, backgroundColor: theme.colors.status[tone].rule }}
        />
      ))}
      {empty > 0 ? <View style={{ flexGrow: empty, flexBasis: 0 }} /> : null}
    </View>
  );
}
