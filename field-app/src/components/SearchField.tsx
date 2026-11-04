/**
 * SearchField — the one free-text box a list screen searches with: FF-41
 * *Serial, badge, device ID or address*, FF-62 *Search 34 templates*. A
 * magnifier mark, the input, and an optional line under it saying what it
 * searches. Two boards draw it, so it is a component (B14 rule 43).
 *
 * The input is 48pt tall (B14 rule 45) and is a `search` field to a screen
 * reader, named by `label`.
 */
import { TextInput, View } from 'react-native';

import { useTheme } from '../theme';
import { AppText, textStyle } from './AppText';
import { Mark } from './Mark';

export interface SearchFieldProps {
  label: string;
  value: string;
  onChangeText: (text: string) => void;
  placeholder?: string;
  /** One line under the box: what it searches. */
  help?: string;
  testID?: string;
}

export function SearchField(props: SearchFieldProps) {
  const theme = useTheme();
  const c = theme.colors;
  return (
    <View style={{ gap: theme.field.inputToHelp }}>
      <View
        style={{
          minHeight: theme.touch.control,
          flexDirection: 'row',
          alignItems: 'center',
          gap: theme.space[2],
          paddingHorizontal: theme.space[3],
          borderWidth: theme.borderWidth.card,
          borderColor: c.controlBorder,
          borderRadius: theme.radius.md,
          backgroundColor: c.card,
        }}
      >
        <Mark name="search" colour={c.textMuted} />
        <TextInput
          accessibilityRole="search"
          accessibilityLabel={props.label}
          value={props.value}
          onChangeText={props.onChangeText}
          placeholder={props.placeholder}
          placeholderTextColor={c.textMuted}
          autoCorrect={false}
          autoCapitalize="none"
          testID={props.testID}
          style={[textStyle(theme, 'body'), { flex: 1, minHeight: theme.touch.control }]}
        />
      </View>
      {props.help ? (
        <AppText variant="label" tone="muted">
          {props.help}
        </AppText>
      ) : null}
    </View>
  );
}
