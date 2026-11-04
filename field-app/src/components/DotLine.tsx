/**
 * DotLine — a coloured mark and one short line: how old a figure is (FF-25
 * *Read 40 seconds ago*, FF-61 *Both read 30 seconds ago*), what the office
 * has done with a close (FF-35 *Waiting for the office* · *Accepted by the
 * office*). The tone carries the meaning to the eye and the words carry it to
 * everyone else, so the mark is hidden from screen readers.
 */
import { View } from 'react-native';

import { useTheme } from '../theme';
import type { StatusTone } from '../theme';
import { AppText } from './AppText';
import { Mark, type MarkName } from './Mark';

export function DotLine(props: { tone: StatusTone; children: string; mark?: MarkName; testID?: string }) {
  const theme = useTheme();
  const ink = theme.colors.statusInk[props.tone];
  return (
    <View
      testID={props.testID}
      accessible
      accessibilityLabel={props.children}
      style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[2] }}
    >
      {props.mark ? (
        <Mark name={props.mark} colour={ink} />
      ) : (
        <View
          style={{
            width: theme.space[2],
            height: theme.space[2],
            borderRadius: theme.radius.sm,
            backgroundColor: ink,
          }}
        />
      )}
      <AppText variant="label" weight="semibold" style={{ color: ink, flexShrink: 1 }}>
        {props.children}
      </AppText>
    </View>
  );
}
