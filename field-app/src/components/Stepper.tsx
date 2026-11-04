/**
 * Stepper — a count changed by − and +, never typed (R38: *"steppers over
 * number fields"*). FF-23 Materials draws it: two 56pt squares either side of
 * the figure, because it is the MOST-TAPPED control — *"a quantity stepper hit
 * a hundred times with gloves on"* (Stack page; B14 rule 45).
 *
 * To a screen reader the figure is one adjustable control (swipe up / down),
 * and the two buttons carry their own names ("Fewer" / "More") because they
 * are icon-only.
 */
import { View } from 'react-native';

import { useTheme } from '../theme';
import { AppText } from './AppText';
import { Glyph } from './Glyph';
import { Pressable } from 'react-native';

export interface StepperProps {
  value: number;
  onChange: (next: number) => void;
  /** What is being counted ("Meter coupling kit"). */
  label: string;
  decreaseLabel: string;
  increaseLabel: string;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  /** How the figure is written — FF-34's times show a clock ("09:12") for a
   *  value held in minutes (DEF-FLD-10626). Defaults to the number itself. */
  format?: (value: number) => string;
  testID?: string;
}

export function Stepper({
  value,
  onChange,
  label,
  decreaseLabel,
  increaseLabel,
  min = 0,
  max,
  step = 1,
  disabled = false,
  format = String,
  testID,
}: StepperProps) {
  const theme = useTheme();
  const c = theme.colors;
  const canDecrease = !disabled && value - step >= min;
  const canIncrease = !disabled && (max === undefined || value + step <= max);
  const side = theme.touch.mostTapped;

  const square = (enabled: boolean) => ({
    width: side,
    height: side,
    alignItems: 'center' as const,
    justifyContent: 'center' as const,
    borderRadius: theme.radius.md,
    borderWidth: theme.borderWidth.control,
    borderColor: enabled ? c.controlBorder : c.disabledFill,
    backgroundColor: enabled ? c.card : c.disabledFill,
  });

  return (
    <View testID={testID} style={{ flexDirection: 'row', alignItems: 'center', gap: theme.touch.clear }}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={decreaseLabel}
        accessibilityState={{ disabled: !canDecrease }}
        disabled={!canDecrease}
        onPress={() => onChange(value - step)}
        testID={testID ? `${testID}-decrease` : undefined}
        style={square(canDecrease)}
      >
        <Glyph name="fewer" colour={canDecrease ? c.text : c.disabledText} />
      </Pressable>
      <View
        accessible
        accessibilityRole="adjustable"
        accessibilityLabel={label}
        accessibilityValue={format === String ? { min, max, now: value } : { text: format(value) }}
        accessibilityActions={[{ name: 'increment' }, { name: 'decrement' }]}
        onAccessibilityAction={(e) => {
          if (e.nativeEvent.actionName === 'increment' && canIncrease) onChange(value + step);
          if (e.nativeEvent.actionName === 'decrement' && canDecrease) onChange(value - step);
        }}
        style={{ minWidth: side, alignItems: 'center' }}
      >
        <AppText variant="title" accessibilityRole="none" testID={testID ? `${testID}-value` : undefined}>
          {format(value)}
        </AppText>
      </View>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={increaseLabel}
        accessibilityState={{ disabled: !canIncrease }}
        disabled={!canIncrease}
        onPress={() => onChange(value + step)}
        testID={testID ? `${testID}-increase` : undefined}
        style={square(canIncrease)}
      >
        <Glyph name="more" colour={canIncrease ? c.text : c.disabledText} />
      </Pressable>
    </View>
  );
}
