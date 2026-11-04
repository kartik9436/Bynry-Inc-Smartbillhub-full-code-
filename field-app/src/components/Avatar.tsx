/**
 * Avatar — a person's initials in a tinted square: FF-44 Profile (large),
 * the Switch technician sheet and FF-53's header (standard). The drawings
 * draw a circle; the shape comes from the radius tokens, which port the web's
 * square 0 (`shared/tokens.ts`), so it is square until that is ruled.
 *
 * The tint is the NEUTRAL status pair, which passes 4.5:1 in all three themes
 * (sunlight draws it solid black with white letters). A photo is not shown:
 * the handset stores a `photo_path` but nothing yet loads it (reported).
 */
import { Text, View } from 'react-native';

import { useTheme } from '../theme';
import { textStyle } from './AppText';

export interface AvatarProps {
  /** A name to take initials from ("D. Ortiz" → DO), or the glyph to show. */
  name: string;
  size?: 'default' | 'large';
  /** Draw `name` as it is rather than as initials ("+" for "Someone else"). */
  literal?: boolean;
  testID?: string;
}

export function initialsOf(name: string): string {
  return name
    .split(/[\s.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('');
}

export function Avatar({ name, size = 'default', literal = false, testID }: AvatarProps) {
  const theme = useTheme();
  const pair = theme.colors.status.neutral;
  const side = size === 'large' ? theme.touch.primary + theme.space[4] : theme.touch.control;
  return (
    <View
      testID={testID}
      accessible={false}
      importantForAccessibility="no-hide-descendants"
      style={{
        width: side,
        height: side,
        borderRadius: theme.radius.lg,
        backgroundColor: pair.bg,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Text style={[textStyle(theme, size === 'large' ? 'title' : 'body', 'heavy'), { color: pair.fg }]}>
        {literal ? name : initialsOf(name)}
      </Text>
    </View>
  );
}
