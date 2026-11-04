/**
 * The bar pinned to the foot of a screen that holds its one or two acts —
 * *Can't read · Save and next*, *Turn it in · Keep going* (every RW board).
 * A secondary act sits left, the primary takes the rest; two acts that must
 * read as a ladder (RW-25: the way back first, the danger act second) stack
 * instead with `stacked`.
 */
import type { ReactNode } from 'react';
import { View } from 'react-native';

import { useTheme } from '../theme';
import { AppText } from './AppText';

export function ActionBar(props: { children: ReactNode; note?: string; stacked?: boolean; testID?: string }) {
  const theme = useTheme();
  return (
    <View
      testID={props.testID}
      style={{
        backgroundColor: theme.colors.card,
        borderTopColor: theme.colors.border,
        borderTopWidth: theme.borderWidth.divider,
        paddingHorizontal: theme.space[3],
        paddingVertical: theme.space[3],
        gap: theme.space[2],
      }}
    >
      <View style={{ flexDirection: props.stacked ? 'column' : 'row', gap: theme.touch.clear }}>{props.children}</View>
      {props.note ? (
        <AppText variant="label" tone="muted" style={{ textAlign: 'center' }}>
          {props.note}
        </AppText>
      ) : null}
    </View>
  );
}
