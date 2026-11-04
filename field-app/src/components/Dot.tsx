/**
 * Dot — the small status mark the boards put before a word: availability on
 * FF-44 / FF-45 (green available, amber on break, grey off duty), the kind of
 * an alert on FF-42. Decoration beside a word, never the only signal, so it is
 * hidden from the screen reader; the word next to it carries the meaning.
 */
import { View } from 'react-native';

import { useTheme } from '../theme';
import type { StatusTone } from '../theme';

export function Dot({ tone, testID }: { tone: StatusTone; testID?: string }) {
  const theme = useTheme();
  const side = theme.space[3];
  return (
    <View
      testID={testID}
      accessible={false}
      importantForAccessibility="no"
      style={{ width: side, height: side, borderRadius: side / 2, backgroundColor: theme.colors.status[tone].rule }}
    />
  );
}
