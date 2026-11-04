/**
 * ChoiceChips — one choice from a few, on screen rather than in a keyboard or
 * a dropdown (R38, *"A technician taps, never types. Choices on screen over
 * keyboards"*). FF-18 "How long? 5 min · 15 min · 30 min", FF-51 language,
 * date format, clock, units and the Screen theme picker itself.
 *
 * The web kit's equivalent is `SegmentedControl`, and this takes its props:
 * `segments` ({ id, label, disabled? }), `active`, `onSelect`, and `label`
 * for the group's accessible name. Each chip is a radio in a radio group, at
 * least 48pt tall, 8pt apart (B14 rule 45).
 */
import { Pressable, Text, View } from 'react-native';

import { useTheme } from '../theme';
import { textStyle } from './AppText';

export interface Segment {
  id: string;
  label: string;
  disabled?: boolean;
}

export interface ChoiceChipsProps {
  segments: readonly Segment[];
  active: string | null;
  onSelect?: (id: string) => void;
  /** The group's accessible name ("How long?"). */
  label: string;
  /** Share the row equally (FF-18) rather than size to the words (FF-51). */
  fill?: boolean;
  /** Draw at the primary height (FF-51 Screen: 56). */
  size?: 'default' | 'sm';
  testID?: string;
}

export function ChoiceChips(props: ChoiceChipsProps) {
  const theme = useTheme();
  const c = theme.colors;
  return (
    <View
      accessibilityRole="radiogroup"
      accessibilityLabel={props.label}
      testID={props.testID}
      style={{ flexDirection: 'row', flexWrap: 'wrap', gap: theme.touch.clear }}
    >
      {props.segments.map((seg) => {
        const selected = seg.id === props.active;
        return (
          <Pressable
            key={seg.id}
            accessibilityRole="radio"
            accessibilityLabel={seg.label}
            accessibilityState={{ checked: selected, disabled: seg.disabled === true }}
            disabled={seg.disabled}
            onPress={() => props.onSelect?.(seg.id)}
            testID={props.testID ? `${props.testID}-${seg.id}` : undefined}
            style={{
              minHeight: props.size === 'default' ? theme.touch.primary : theme.touch.control,
              paddingHorizontal: theme.space[4],
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: theme.radius.md,
              borderWidth: theme.borderWidth.emphasis,
              borderColor: selected ? c.selectedFill : c.controlBorder,
              backgroundColor: selected ? c.selectedFill : seg.disabled ? c.disabledFill : c.card,
              flexGrow: props.fill ? 1 : 0,
              flexBasis: props.fill ? 0 : 'auto',
            }}
          >
            <Text
              style={[
                textStyle(theme, 'body', selected ? 'heavy' : 'regular'),
                { color: selected ? c.selectedText : seg.disabled ? c.disabledText : c.text },
              ]}
            >
              {seg.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}
