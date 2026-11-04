/**
 * The number keypad of a reading (RW-09): 1–9, Clear, 0, delete. Three key
 * sizes for gloves (RW-29 *Keypad: Normal · Large · Largest*); the smallest is
 * still the most-tapped size, never below it.
 *
 * It knows nothing about meters: it edits a string of digits and hands it
 * back. The figure's meaning (unit, range) is the screen's.
 */
import { Pressable, View } from 'react-native';

import { useTheme } from '../theme';
import { AppText, textStyle } from './AppText';
import { PRESSED_OPACITY } from './Button';

export type KeypadSize = 'normal' | 'large' | 'largest';

export interface KeypadProps {
  value: string;
  onChange: (next: string) => void;
  /** Read aloud for the two non-digit keys. */
  clearLabel: string;
  deleteLabel: string;
  size?: KeypadSize;
  /** The longest figure a meter can show. */
  maxDigits?: number;
  /** Two columns instead of three — the tablet's narrow keypad column (RW-09-T). */
  columns?: 2 | 3;
  testID?: string;
}

const DIGITS = ['1', '2', '3', '4', '5', '6', '7', '8', '9'];

/** A key's height for a keypad size — never below the most-tapped size. */
export function keyHeight(size: KeypadSize, touch: { mostTapped: number }, space: { 4: number; 8: number }): number {
  if (size === 'largest') return touch.mostTapped + space[8];
  if (size === 'large') return touch.mostTapped + space[4];
  return touch.mostTapped;
}

export function Keypad({
  value,
  onChange,
  clearLabel,
  deleteLabel,
  size = 'large',
  maxDigits = 12,
  columns = 3,
  testID,
}: KeypadProps) {
  const theme = useTheme();
  const c = theme.colors;
  const height = keyHeight(size, theme.touch, theme.space);
  const press = (k: string) => {
    if (k === 'clear') onChange('');
    else if (k === 'del') onChange(value.slice(0, -1));
    else if (value.length < maxDigits) onChange(value === '0' ? k : value + k);
  };
  const keys = [...DIGITS, 'clear', '0', 'del'];
  const rows: string[][] = [];
  for (let i = 0; i < keys.length; i += columns) rows.push(keys.slice(i, i + columns));
  return (
    <View testID={testID} style={{ gap: theme.touch.clear }}>
      {rows.map((row) => (
        <View key={row.join('')} style={{ flexDirection: 'row', gap: theme.touch.clear }}>
          {row.map((k) => {
            const fn = k === 'clear' || k === 'del';
            const label = k === 'clear' ? clearLabel : k === 'del' ? deleteLabel : k;
            return (
              <Pressable
                key={k}
                accessibilityRole="button"
                accessibilityLabel={label}
                onPress={() => press(k)}
                testID={testID ? `${testID}-${k}` : undefined}
                style={({ pressed }) => ({
                  flexGrow: 1,
                  flexBasis: 0,
                  minHeight: height,
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: theme.radius.md,
                  borderWidth: theme.borderWidth.control,
                  borderColor: c.controlBorder,
                  backgroundColor: fn ? c.surface : c.card,
                  opacity: pressed ? PRESSED_OPACITY : 1,
                })}
              >
                <AppText
                  accessibilityRole="none"
                  style={textStyle(theme, fn ? 'section' : 'title', fn ? 'semibold' : 'heavy', fn ? 'muted' : 'default')}
                >
                  {k === 'del' ? '⌫' : label}
                </AppText>
              </Pressable>
            );
          })}
        </View>
      ))}
    </View>
  );
}
