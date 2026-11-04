/**
 * StatusChip — a short status in a tinted box: ON SITE, P3, ACTIVE, 2 PHOTOS,
 * 1 flagged (FF-15, FF-25, FF-20). The web kit calls it `StatusPill` with the
 * same `tone` + label props; both names are exported so a screen ported from
 * the web reads the same.
 *
 * Status meaning only, never decoration (tokens.css on the semantic colours).
 * In sunlight the chip is solid with white text, as FF-55 draws it.
 */
import { Text, View } from 'react-native';

import { useTheme } from '../theme';
import type { StatusTone } from '../theme';
import { textStyle } from './AppText';

export type { StatusTone };

export interface StatusChipProps {
  tone: StatusTone;
  /** Pre-translated. Kept to a FACT's length (B14 rule 33). */
  children: string;
  testID?: string;
}

export function StatusChip({ tone, children, testID }: StatusChipProps) {
  const theme = useTheme();
  const pair = theme.colors.status[tone];
  return (
    <View
      testID={testID}
      accessible
      accessibilityRole="text"
      accessibilityLabel={children}
      style={{
        alignSelf: 'flex-start',
        backgroundColor: pair.bg,
        borderRadius: theme.radius.sm,
        paddingHorizontal: theme.space[2],
        paddingVertical: theme.space[1],
      }}
    >
      <Text
        style={[
          textStyle(theme, 'micro', 'heavy'),
          {
            color: pair.fg,
            textTransform: 'uppercase',
            letterSpacing: theme.tracking.kicker * theme.type.micro,
          },
        ]}
      >
        {children}
      </Text>
    </View>
  );
}

/** The web kit's name for the same component. */
export const StatusPill = StatusChip;
