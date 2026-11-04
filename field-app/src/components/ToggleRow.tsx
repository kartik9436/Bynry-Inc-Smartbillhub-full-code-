/**
 * ToggleRow — a setting that is on or off, with its label and an optional
 * second line: FF-51 *Bigger text · Easier with gloves on*, every row of FF-52
 * Notifications. The WHOLE ROW is the control (48pt at least, B14 rule 45) and
 * announces itself as a switch with its state; the drawn switch inside it is
 * the picture of that state, not a second target.
 */
import { Pressable, Switch, View } from 'react-native';

import { useTheme } from '../theme';
import { AppText } from './AppText';

export interface ToggleRowProps {
  label: string;
  detail?: string;
  value: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  /** Draw a rule above this row (every row after the first in a card). */
  divider?: boolean;
  testID?: string;
}

export function ToggleRow(props: ToggleRowProps) {
  const theme = useTheme();
  const c = theme.colors;
  return (
    <Pressable
      accessibilityRole="switch"
      accessibilityLabel={props.detail ? `${props.label}, ${props.detail}` : props.label}
      accessibilityState={{ checked: props.value, disabled: props.disabled === true }}
      disabled={props.disabled}
      onPress={() => props.onChange(!props.value)}
      testID={props.testID}
      style={{
        minHeight: theme.touch.control,
        flexDirection: 'row',
        alignItems: 'center',
        gap: theme.space[3],
        borderTopWidth: props.divider ? theme.borderWidth.divider : 0,
        borderTopColor: c.divider,
      }}
    >
      <View style={{ flexGrow: 1, flexShrink: 1 }}>
        <AppText variant="body">{props.label}</AppText>
        {props.detail ? (
          <AppText variant="label" tone="muted">
            {props.detail}
          </AppText>
        ) : null}
      </View>
      <Switch
        accessible={false}
        importantForAccessibility="no"
        value={props.value}
        disabled={props.disabled}
        onValueChange={props.onChange}
        trackColor={{ true: c.status.success.rule, false: c.disabledFill }}
        thumbColor={c.card}
        ios_backgroundColor={c.disabledFill}
      />
    </Pressable>
  );
}
