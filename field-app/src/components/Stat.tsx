/**
 * A figure with its caption under it — *47 stops*, *151 of 153 meters*,
 * *129 read* (RW-01, RW-02, RW-22, RW-28). `StatRow` lays several side by
 * side; on a narrow pane they wrap rather than shrink.
 */
import type { ReactNode } from 'react';
import { View } from 'react-native';

import { useTheme } from '../theme';
import type { StatusTone } from '../theme';
import { AppText } from './AppText';

export interface StatProps {
  value: string;
  caption: string;
  /** The figure's colour: success for read, warning for could-not (RW-22). */
  tone?: StatusTone | 'default';
  size?: 'section' | 'title';
  testID?: string;
}

export function Stat({ value, caption, tone = 'default', size = 'section', testID }: StatProps) {
  const theme = useTheme();
  const colour = tone === 'default' ? theme.colors.text : theme.colors.statusInk[tone];
  return (
    <View testID={testID} accessible accessibilityRole="text" accessibilityLabel={`${value} ${caption}`}>
      <AppText variant={size} weight="heavy" style={{ color: colour }}>
        {value}
      </AppText>
      <AppText variant="micro" tone="muted">
        {caption}
      </AppText>
    </View>
  );
}

export function StatRow(props: { children: ReactNode; testID?: string }) {
  const theme = useTheme();
  return (
    <View testID={props.testID} style={{ flexDirection: 'row', flexWrap: 'wrap', gap: theme.space[6] }}>
      {props.children}
    </View>
  );
}
