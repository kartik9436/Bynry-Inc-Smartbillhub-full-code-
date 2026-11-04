/**
 * The handful of glyphs the kit itself needs — back, forward, more, fewer,
 * close, menu — and the screen waves' chrome marks (T-15/T-16, T-18..T-25).
 *
 * Drawn from `@expo/vector-icons`' Ionicons, the OUTLINE set where it has
 * one: the boards draw stroked line icons (back chevron, scan frame, refresh,
 * warning triangle), and Ionicons is the one family that holds every name
 * here and in `Mark`, so the app ships one icon font (~430 KB) rather than
 * two. Imported per family, so no other icon font enters the bundle. These
 * replace the interim text characters of Phase 1; the NAMES did not change, so
 * no screen changed.
 *
 * A glyph is DECORATION: hidden from screen readers. Every icon-only control
 * takes its accessible name from `IconButton`'s `label`, never from the icon.
 */
import Ionicons from '@expo/vector-icons/Ionicons';
import type { ComponentProps } from 'react';
import { View } from 'react-native';

import { useTheme } from '../theme';

export type GlyphName =
  | 'back'
  | 'forward'
  | 'fewer'
  | 'more'
  | 'close'
  | 'menu'
  | 'drawer'
  | 'check'
  | 'pending'
  | 'waiting'
  | 'sync'
  | 'bell'
  | 'calendar'
  | 'pin'
  | 'camera'
  | 'phone'
  | 'mail'
  | 'message'
  | 'hand'
  | 'scan'
  | 'navigate'
  | 'warning'
  | 'locate'
  | 'person'
  | 'signal'
  | 'mark';

/** Each name's Ionicons glyph — the board's stroked icon of the same name. */
export const GLYPH_ICONS: Record<GlyphName, ComponentProps<typeof Ionicons>['name']> = {
  back: 'chevron-back',
  forward: 'chevron-forward',
  fewer: 'remove',
  more: 'add',
  close: 'close',
  menu: 'ellipsis-vertical',
  drawer: 'menu',
  check: 'checkmark',
  pending: 'time-outline', // under way
  waiting: 'ellipse-outline', // not started
  sync: 'sync',
  bell: 'notifications-outline',
  calendar: 'calendar-outline',
  pin: 'location-outline',
  camera: 'camera-outline',
  phone: 'call-outline',
  mail: 'mail-outline',
  message: 'chatbox-outline',
  hand: 'hand-left-outline',
  scan: 'scan-outline',
  navigate: 'navigate-outline',
  warning: 'warning-outline',
  locate: 'locate-outline',
  person: 'person-outline',
  signal: 'cellular-outline',
  mark: 'diamond', // the product mark
};

export function Glyph(props: { name: GlyphName; colour?: string; size?: number }) {
  const theme = useTheme();
  return (
    // The wrapper carries the test id and the hiding: the icon font renders an empty
    // Text until it has loaded, and that first render keeps no props.
    <View accessible={false} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden testID={`glyph-${props.name}`}>
      <Ionicons
        name={GLYPH_ICONS[props.name]}
        size={props.size ?? theme.type.title}
        color={props.colour ?? theme.colors.text}
      />
    </View>
  );
}
