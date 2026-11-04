/**
 * IconCircle — an icon in a tinted disc. Drawn at three sizes on the boards:
 * the intro illustrations (FF-02 calendar on green, FF-03 hand on amber,
 * FF-04 sync on blue), the 48pt discs beside FF-06's reset choices and FF-07's
 * permissions, and the sync disc that opens the *waiting to send* strip
 * (FF-10, FF-63). The tint is a STATUS tone's fill and the glyph its ink, so
 * the three themes come for free.
 *
 * Decorative: it is hidden from a screen reader, because the words beside it
 * always say the same thing.
 */
import { View } from 'react-native';

import { useTheme } from '../theme';
import type { StatusTone } from '../theme';
import { Glyph } from './Glyph';
import type { GlyphName } from './Glyph';

export interface IconCircleProps {
  glyph: GlyphName;
  tone: StatusTone;
  /** `sm` a 48pt disc beside a row; `lg` the intro illustration. */
  size?: 'sm' | 'lg';
  testID?: string;
}

/** The illustration disc: four primary-touch units across (224pt on the 4pt scale). */
export const LARGE_DISC_UNITS = 4;

export function IconCircle({ glyph, tone, size = 'sm', testID }: IconCircleProps) {
  const theme = useTheme();
  const pair = theme.colors.status[tone];
  const diameter = size === 'lg' ? theme.touch.primary * LARGE_DISC_UNITS : theme.touch.control;
  const glyphSize = size === 'lg' ? theme.type.title * LARGE_DISC_UNITS : theme.type.title;
  return (
    <View
      accessible={false}
      importantForAccessibility="no-hide-descendants"
      testID={testID}
      style={{
        width: diameter,
        height: diameter,
        borderRadius: diameter / 2,
        backgroundColor: pair.bg,
        alignItems: 'center',
        justifyContent: 'center',
        alignSelf: size === 'lg' ? 'center' : 'auto',
      }}
    >
      <Glyph name={glyph} colour={pair.fg} size={glyphSize} />
    </View>
  );
}
