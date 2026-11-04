/**
 * PhotoThumb — one photograph from a FILE on the handset (R52: a path, never
 * bytes), at one of two sizes: `small` for the strips on a step and a reading
 * (FF-17 "10:12 · 10:13", FF-20 "Photo of the dial"), `large` for the review
 * and the comparison (FF-21, FF-22), where the stamp lines sit under it.
 *
 * The stamp is R94's — date, time, position ± accuracy, who, which order —
 * and is BURNED INTO THE PIXELS by the camera pipeline; the lines here are the
 * same facts read from the row, so a photograph whose file has already gone
 * to the server (R61) still says what it was.
 *
 * A photograph whose file is gone shows a plain panel with its caption: the
 * row is kept after upload, so the review still shows it was taken.
 */
import { Image, View } from 'react-native';

import { useTheme } from '../theme';
import { AppText } from './AppText';

export interface PhotoThumbProps {
  /** A `file://` path, or null once the file is gone. */
  path: string | null;
  /** What the photograph is, for a screen reader ("Before, 09:18"). */
  label: string;
  size?: 'small' | 'large';
  /** The stamp's lines, drawn under a large photograph. */
  stamp?: string[];
  /** One short line under a small one (its time). */
  caption?: string;
  testID?: string;
}

export function PhotoThumb({ path, label, size = 'small', stamp, caption, testID }: PhotoThumbProps) {
  const theme = useTheme();
  const c = theme.colors;
  const small = size === 'small';
  const box = small
    ? { width: theme.touch.primary + theme.space[6], height: theme.touch.primary }
    : { width: '100%' as const, aspectRatio: PHOTO_ASPECT };
  return (
    <View testID={testID} accessible accessibilityRole="image" accessibilityLabel={label}>
      <View style={[box, { backgroundColor: c.surface, borderWidth: theme.borderWidth.card, borderColor: c.border }]}>
        {path ? (
          <Image source={{ uri: path }} style={{ width: '100%', height: '100%' }} resizeMode="cover" />
        ) : null}
      </View>
      {small && caption ? (
        <AppText variant="micro" tone="muted">
          {caption}
        </AppText>
      ) : null}
      {!small && stamp && stamp.length > 0 ? (
        <View style={{ backgroundColor: c.text, paddingHorizontal: theme.space[3], paddingVertical: theme.space[2] }}>
          {stamp.map((line, i) => (
            <AppText key={i} variant="micro" weight={i === 0 ? 'heavy' : 'regular'} style={{ color: c.page }}>
              {line}
            </AppText>
          ))}
        </View>
      ) : null}
    </View>
  );
}

/** The boards draw photographs at 4 : 3. A ratio, not a size. */
export const PHOTO_ASPECT = 4 / 3;
