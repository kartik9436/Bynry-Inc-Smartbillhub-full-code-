/**
 * SyncChip — the outlined *12 to send* chip the boards put in a screen's top
 * bar (FF-15, FF-54, FF-55; FF-44 links it). It opens Sync (R103: *"Sync is
 * one tap from the day"*). `count` null means NOT KNOWN — it shows a dash and
 * never a zero, because "0" reads as "all sent" (R32, ShellStatus).
 */
import { Pressable, Text } from 'react-native';

import { useTheme } from '../theme';
import { textStyle } from './AppText';
import { Glyph } from './Glyph';

export interface SyncChipProps {
  count: number | null;
  /** The visible words after the number ("to send"). */
  suffix: string;
  /** The full sentence for a screen reader ("12 to send"). */
  accessibilityLabel: string;
  onPress: () => void;
  testID?: string;
}

export function SyncChip(props: SyncChipProps) {
  const theme = useTheme();
  const c = theme.colors;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={props.accessibilityLabel}
      onPress={props.onPress}
      testID={props.testID}
      style={{
        minHeight: theme.touch.control,
        paddingHorizontal: theme.space[3],
        flexDirection: 'row',
        alignItems: 'center',
        gap: theme.space[2],
        borderWidth: theme.borderWidth.control,
        borderColor: c.controlBorder,
        borderRadius: theme.radius.md,
        backgroundColor: c.card,
      }}
    >
      <Glyph name="sync" colour={c.text} />
      <Text style={[textStyle(theme, 'body', 'heavy'), { color: c.text }]}>
        {props.count == null ? '–' : String(props.count)} {props.suffix}
      </Text>
    </Pressable>
  );
}
