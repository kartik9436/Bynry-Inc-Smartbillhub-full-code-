/**
 * Facts — labelled values that only state something, never open anything.
 *
 *   FactGrid  — label over value, two to a row: FF-39 IDENTITY (Serial ·
 *               Badge · Device ID · Size).
 *   FactLine  — a muted label column and its value on one line: FF-40's
 *               Problem / Done / Parts / Who, FF-29's Travel / Arrived /
 *               Labour on a recessed strip.
 *
 * Each pair is ONE accessible element ("Serial, W-4471") so a screen reader
 * does not read a column of labels and then a column of values.
 */
import { View } from 'react-native';

import { useTheme } from '../theme';
import { AppText } from './AppText';

export interface Fact {
  label: string;
  value: string;
  /** The value in the success ink (FF-29's labour). */
  tone?: 'default' | 'success' | 'warning';
  /** The whole line in bold (FF-29's Labour row). */
  strong?: boolean;
  testID?: string;
}

export function FactGrid(props: { facts: readonly Fact[]; testID?: string }) {
  const theme = useTheme();
  return (
    <View testID={props.testID} style={{ flexDirection: 'row', flexWrap: 'wrap', rowGap: theme.space[3] }}>
      {props.facts.map((f) => (
        <View
          key={f.label}
          accessible
          accessibilityLabel={`${f.label}, ${f.value}`}
          testID={f.testID}
          style={{ width: '50%', paddingRight: theme.space[2] }}
        >
          <AppText variant="label" tone="muted">
            {f.label}
          </AppText>
          <AppText variant="body" weight="heavy">
            {f.value}
          </AppText>
        </View>
      ))}
    </View>
  );
}

export function FactLines(props: { facts: readonly Fact[]; recessed?: boolean; split?: boolean; testID?: string }) {
  const theme = useTheme();
  const c = theme.colors;
  return (
    <View
      testID={props.testID}
      style={
        props.recessed
          ? { backgroundColor: c.surface, paddingHorizontal: theme.space[3], borderRadius: theme.radius.md }
          : undefined
      }
    >
      {props.facts.map((f, i) => {
        const ink = f.tone === 'success' ? c.statusInk.success : f.tone === 'warning' ? c.statusInk.warning : c.text;
        return (
          <View
            key={f.label}
            accessible
            accessibilityLabel={`${f.label}, ${f.value}`}
            testID={f.testID}
            style={{
              flexDirection: 'row',
              alignItems: 'baseline',
              gap: theme.space[3],
              paddingVertical: theme.space[2],
              borderTopWidth: i > 0 && props.split ? theme.borderWidth.divider : 0,
              borderTopColor: c.divider,
            }}
          >
            <AppText
              variant={props.split ? 'body' : 'label'}
              tone={props.split ? 'default' : 'muted'}
              weight={f.strong ? 'heavy' : 'regular'}
              style={props.split ? { flexGrow: 1 } : { width: '30%' }}
            >
              {f.label}
            </AppText>
            <AppText
              variant="body"
              weight={props.split || f.strong ? 'heavy' : 'regular'}
              style={[{ color: ink, flexShrink: 1 }, props.split ? { textAlign: 'right' } : { flexGrow: 1 }]}
            >
              {f.value}
            </AppText>
          </View>
        );
      })}
    </View>
  );
}
