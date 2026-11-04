/**
 * Notice — a one-line message on a tint with a strong rule down its left
 * edge: FF-18 "Marked as added in the field." (info), FF-16 "Tasks stay
 * locked. All four required." (warning), FF-34 "1 required photo missing"
 * (danger), FF-23 "1 extra, 1 short. The office sees both." (warning). Drawn
 * on more boards than any other block, so it is a component (B14 rule 43).
 *
 * The web's nearest equivalents are `WarningBox` and `RefusalStrip`; neither
 * covers all three tones, so this takes the boards' word.
 *
 * ANNOUNCED, NOT ONLY SHOWN (portal question 7, DEF-FLD-10361): every notice
 * is a LIVE REGION — `assertive` for danger (also `alert`), `polite` for the
 * rest — so one that appears after an act (FF-21 "Camera not available yet.",
 * RW-26 "Not sent yet. They stay on the phone.") is spoken by TalkBack when it
 * appears or changes, not merely drawn. Before, only danger was announced.
 */
import type { ReactNode } from 'react';
import { Text, View } from 'react-native';

import { useTheme } from '../theme';
import { textStyle } from './AppText';

export type NoticeTone = 'info' | 'warning' | 'danger' | 'success';

export function Notice(props: {
  tone: NoticeTone;
  children: string;
  icon?: ReactNode;
  /** Something to act on inside the notice (FF-20 "Enter again"). */
  action?: ReactNode;
  testID?: string;
}) {
  const theme = useTheme();
  const pair = theme.colors.status[props.tone];
  return (
    <View
      testID={props.testID}
      accessibilityRole={props.tone === 'danger' ? 'alert' : undefined}
      accessibilityLiveRegion={props.tone === 'danger' ? 'assertive' : 'polite'}
      style={{
        backgroundColor: pair.bg,
        borderLeftColor: pair.rule,
        borderLeftWidth: theme.borderWidth.rule,
        paddingHorizontal: theme.space[3],
        paddingVertical: theme.space[3],
        gap: theme.space[3],
      }}
    >
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[2] }}>
        {props.icon ? <View accessible={false}>{props.icon}</View> : null}
        <Text style={[textStyle(theme, 'body', 'semibold'), { color: pair.fg, flexShrink: 1 }]}>
          {props.children}
        </Text>
      </View>
      {props.action ?? null}
    </View>
  );
}
