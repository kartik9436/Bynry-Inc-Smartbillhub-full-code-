/**
 * NumberDisc — a stop's number in a disc of its state's colour (FF-13 T's
 * *Stops* list: 1 green on site, 2 blue dispatched, 3 grey queued — the same
 * three tones as the map's pins and legend). Decorative: the row beside it
 * says the number and the state in words, so it is hidden from a screen
 * reader.
 */
import { Text, View } from 'react-native';

import { useTheme } from '../theme';
import type { StatusTone } from '../theme';
import { textStyle } from './AppText';

export function NumberDisc(props: { n: number; tone: StatusTone; testID?: string }) {
  const theme = useTheme();
  const pair = theme.colors.status[props.tone];
  const side = theme.touch.control - theme.space[3];
  return (
    <View
      accessible={false}
      importantForAccessibility="no-hide-descendants"
      testID={props.testID}
      style={{
        width: side,
        height: side,
        borderRadius: side / 2,
        alignItems: 'center',
        justifyContent: 'center',
        // The status pair (tint and its ink), as a chip draws it, so the
        // number keeps its contrast in all three themes.
        backgroundColor: pair.bg,
        borderWidth: theme.borderWidth.emphasis,
        borderColor: pair.rule,
      }}
    >
      <Text style={[textStyle(theme, 'label', 'heavy'), { color: pair.fg }]}>{String(props.n)}</Text>
    </View>
  );
}
