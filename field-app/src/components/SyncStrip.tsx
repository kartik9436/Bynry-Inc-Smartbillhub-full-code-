/**
 * SyncStrip — the *waiting to send* band FF-10 and FF-63 draw above the day
 * (and FF-10 T, FF-63 T): the sync disc, *12 waiting to send*, a second line
 * *8 photos · last sent 10:02*, and *Send now*.
 *
 * Two controls, because the board draws two things to do: the words open
 * Sync (R103, *"Sync is one tap from the day, never three"*) and *Send now*
 * sends. A strip with nothing to send still shows — "0 waiting" is a fact
 * here because it is COUNTED from the outbox, never assumed; a count that is
 * not known yet is passed as a different title by the screen.
 *
 * `onSend` absent → no *Send now* button at all (the web kit's EmptyList
 * lesson, DEF-MET-4764: a button with nothing behind it is not drawn).
 */
import { Pressable, Text, View } from 'react-native';

import { useTheme } from '../theme';
import { textStyle } from './AppText';
import { Button } from './Button';
import { IconCircle } from './IconCircle';

export interface SyncStripProps {
  /** "12 waiting to send" — pre-translated. */
  title: string;
  /** "8 photos · last sent 10:02". */
  detail?: string;
  /** Opens Sync (FF-50). */
  onOpen: () => void;
  /** The accessible hint on the words ("Opens Sync"). */
  openHint?: string;
  sendLabel?: string;
  onSend?: () => void;
  sending?: boolean;
  /** Something is waiting: the disc turns amber. */
  pending?: boolean;
  testID?: string;
}

export function SyncStrip(props: SyncStripProps) {
  const theme = useTheme();
  return (
    <View
      testID={props.testID}
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: theme.space[3],
        paddingHorizontal: theme.space[4],
        paddingVertical: theme.space[3],
        backgroundColor: theme.colors.card,
        borderBottomWidth: theme.borderWidth.divider,
        borderBottomColor: theme.colors.border,
      }}
    >
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={[props.title, props.detail].filter(Boolean).join('. ')}
        accessibilityHint={props.openHint}
        onPress={props.onOpen}
        testID={props.testID ? `${props.testID}-open` : undefined}
        style={{ flexGrow: 1, flexShrink: 1, flexDirection: 'row', alignItems: 'center', gap: theme.space[3], minHeight: theme.touch.control }}
      >
        <IconCircle glyph="sync" tone={props.pending ? 'warning' : 'neutral'} />
        <View style={{ flexShrink: 1 }}>
          <Text style={textStyle(theme, 'body', 'heavy')}>{props.title}</Text>
          {props.detail ? <Text style={textStyle(theme, 'label', 'regular', 'muted')}>{props.detail}</Text> : null}
        </View>
      </Pressable>
      {props.onSend && props.sendLabel ? (
        <Button variant="primary" size="sm" onPress={props.onSend} busy={props.sending} testID={props.testID ? `${props.testID}-send` : undefined}>
          {props.sendLabel}
        </Button>
      ) : null}
    </View>
  );
}
