/**
 * Initials — a person shown by their initials (FF-15 CREW "DO MC", the
 * sidebar's own badge). Square, as the token module's radius is 0. Decorative
 * beside a name a screen reader already hears, so it can be hidden from it.
 */
import { View } from 'react-native';

import { useTheme } from '../theme';
import { AppText } from './AppText';

export function Initials(props: { children: string; label?: string; testID?: string }) {
  const theme = useTheme();
  const side = theme.touch.control - theme.space[2];
  return (
    <View
      testID={props.testID}
      accessible={props.label !== undefined}
      accessibilityLabel={props.label}
      style={{
        width: side,
        height: side,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: theme.colors.surface,
        borderWidth: theme.borderWidth.card,
        borderColor: theme.colors.border,
      }}
    >
      <AppText variant="label" weight="heavy" accessibilityRole="none">
        {props.children}
      </AppText>
    </View>
  );
}
