/**
 * ProgressBar — one component for two waves' bars (B14 rule 43; merged in the
 * integration lane):
 *
 *   - a bar in up to three parts — done, done-with-a-problem, the rest
 *     (RW-03 the download, RW-05 the walk, RW-22 *136 of 151*, RW-26 the
 *     send). `problem` is drawn in the warning tone; `tone="strong"` is the ink
 *     bar of RW-03/RW-26, the default the success bar;
 *   - with `left`/`right`, the same bar under FF-17's and FF-19's title with
 *     the line that explains it ("Travel 14m · on site 1h 12m · 45 min est.",
 *     "Meter exchange · 3 of 5 answered").
 *
 * A screen reader hears it as a progress value. The figures are what the bar
 * draws; nothing is stored (Mobile data §11). With a line, `testID` names the
 * block and the bar is `<testID>-bar`; without one, `testID` is the bar.
 */
import { View } from 'react-native';

import { useTheme } from '../theme';
import { AppText } from './AppText';

export interface ProgressBarProps {
  /** Done, out of `total`. */
  done: number;
  /** Of `done`, how many carry a problem (drawn in the warning tone). */
  problem?: number;
  total: number;
  /** Read aloud: "136 of 151 done", "Tasks". */
  label: string;
  /** `strong` is the ink bar of RW-03/RW-26; `progress` the success bar. */
  tone?: 'strong' | 'progress';
  /** The explaining line under the bar (FF-17, FF-19). */
  left?: string;
  right?: string;
  testID?: string;
}

export function ProgressBar({ done, problem = 0, total, label, tone = 'progress', left, right, testID }: ProgressBarProps) {
  const theme = useTheme();
  const c = theme.colors;
  const safeTotal = total > 0 ? total : 1;
  const ok = total > 0 ? Math.max(0, Math.min(done - problem, safeTotal)) : 0;
  const bad = total > 0 ? Math.max(0, Math.min(problem, safeTotal - ok)) : 0;
  const lined = Boolean(left || right);
  const bar = (
    <View
      testID={lined ? (testID ? `${testID}-bar` : undefined) : testID}
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      accessibilityValue={{ min: 0, max: total, now: done }}
      style={{
        flexDirection: 'row',
        height: theme.space[2],
        backgroundColor: c.surface,
        borderRadius: theme.radius.sm,
        overflow: 'hidden',
      }}
    >
      <View style={{ flexGrow: ok, flexBasis: 0, backgroundColor: tone === 'strong' ? c.text : c.status.success.rule }} />
      <View style={{ flexGrow: bad, flexBasis: 0, backgroundColor: c.status.warning.rule }} />
      <View style={{ flexGrow: Math.max(0, safeTotal - ok - bad), flexBasis: 0 }} />
    </View>
  );
  if (!lined) return bar;
  return (
    <View testID={testID} style={{ gap: theme.space[1], paddingHorizontal: theme.space[4], paddingVertical: theme.space[2] }}>
      {bar}
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: theme.space[2] }}>
        <AppText variant="label" tone="muted">
          {left ?? ''}
        </AppText>
        <AppText variant="label" tone="muted">
          {right ?? ''}
        </AppText>
      </View>
    </View>
  );
}
