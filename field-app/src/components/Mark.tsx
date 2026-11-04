/**
 * Mark — the small pictograms the on-site, closing and asset boards draw
 * beside a word: a tick on a passed check, a clock on an old balance, a
 * warning triangle on an unverified step, a microphone beside a note, a
 * camera, a magnifier, a scan frame, an info ring, a refresh arrow, a torch,
 * a document.
 *
 * `Glyph` holds the chrome's marks (back, forward, close…); these are the
 * content's, kept apart so the two lists can grow without two lanes editing
 * one union. Like `Glyph` they are Ionicons outline glyphs (one icon font for
 * the app), sized on the type ramp, and they are DECORATION: hidden from
 * screen readers, because the word beside them carries the meaning (an
 * icon-only control takes its name from `IconButton`'s `label`).
 */
import Ionicons from '@expo/vector-icons/Ionicons';
import type { ComponentProps } from 'react';
import { View } from 'react-native';

import { useTheme } from '../theme';

export type MarkName =
  | 'check'
  | 'clock'
  | 'warning'
  | 'mic'
  | 'camera'
  | 'search'
  | 'scan'
  | 'info'
  | 'refresh'
  | 'torch'
  | 'document'
  | 'pin'
  | 'alert'
  | 'call'
  | 'link';

export const MARK_ICONS: Record<MarkName, ComponentProps<typeof Ionicons>['name']> = {
  check: 'checkmark',
  clock: 'time-outline',
  warning: 'warning-outline',
  mic: 'mic-outline',
  camera: 'camera-outline',
  search: 'search-outline',
  scan: 'scan-outline',
  info: 'information-circle-outline',
  refresh: 'refresh-outline',
  torch: 'flashlight-outline',
  document: 'document-text-outline',
  pin: 'location-outline',
  alert: 'alert-circle-outline',
  call: 'call-outline',
  link: 'link-outline',
};

export function Mark(props: { name: MarkName; colour?: string; size?: 'body' | 'section' | 'title' }) {
  const theme = useTheme();
  return (
    // The wrapper carries the test id and the hiding: the icon font renders an empty
    // Text until it has loaded, and that first render keeps no props.
    <View accessible={false} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden testID={`mark-${props.name}`}>
      <Ionicons
        name={MARK_ICONS[props.name]}
        size={theme.type[props.size ?? 'body']}
        color={props.colour ?? theme.colors.text}
      />
    </View>
  );
}
