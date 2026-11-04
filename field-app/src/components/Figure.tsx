/**
 * Figure — a number with its word under (or beside) it: FF-63's *8 left
 * today · 3 done · 1 on hold* and *15 meters left · 129 read · 7 could not
 * be*, FF-11's *0.2 miles*, FF-14's *4.2 miles · 26 min*, FF-08's *72%*.
 *
 * The number is heavy and tabular; the word is a muted label. A tone colours
 * the NUMBER only, and only for status meaning (done in green, on hold in
 * amber) — never decoration. To a screen reader it is one line: "8 left today".
 */
import { Text, View } from 'react-native';

import { useTheme } from '../theme';
import { textStyle } from './AppText';

export type FigureTone = 'default' | 'success' | 'warning' | 'muted';

export interface FigureProps {
  value: string;
  label: string;
  tone?: FigureTone;
  /** `md` the title size (tiles, distances); `xl` FF-08's percentage. */
  size?: 'md' | 'xl';
  /** Label beside the number (FF-11 "0.2 miles") instead of under it. */
  inline?: boolean;
  testID?: string;
}

/** FF-08 draws its percentage as the biggest thing on any board: three title steps. */
export const XL_TITLE_STEPS = 3;

export function Figure({ value, label, tone = 'default', size = 'md', inline = false, testID }: FigureProps) {
  const theme = useTheme();
  const c = theme.colors;
  const ink =
    tone === 'success' ? c.statusInk.success : tone === 'warning' ? c.statusInk.warning : tone === 'muted' ? c.textMuted : c.text;
  // In sunlight a status ink is white on a solid chip; a bare figure on the
  // page reads in the page's own ink instead, so it never turns invisible.
  const numberInk = theme.name === 'sunlight' ? c.text : ink;
  const fontSize = size === 'xl' ? theme.type.title * XL_TITLE_STEPS : theme.type.title;
  return (
    <View
      accessible
      accessibilityRole="text"
      accessibilityLabel={`${value} ${label}`}
      testID={testID}
      style={{
        flexDirection: inline ? 'row' : 'column',
        alignItems: inline ? 'baseline' : size === 'xl' ? 'center' : 'flex-start',
        gap: inline ? theme.space[2] : 0,
      }}
    >
      <Text
        style={[
          textStyle(theme, 'title', 'heavy'),
          { fontSize, lineHeight: Math.round(fontSize * theme.lineHeight.heading) + (theme.measureKey ?? 0), color: numberInk, fontVariant: ['tabular-nums'] },
        ]}
      >
        {value}
      </Text>
      <Text style={textStyle(theme, 'label', 'regular', 'muted')}>{label}</Text>
    </View>
  );
}
