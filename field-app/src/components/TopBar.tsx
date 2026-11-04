/**
 * TopBar — the bar every pushed screen on the boards opens with: back, the
 * title, and whatever sits on the right (FF-15 "12 to send" and a menu,
 * FF-16 "2 of 4", FF-23 a scan button, RW-09 "Dials"). 56pt tall, the
 * web's own top-bar height and the touch standard's primary figure.
 *
 * The title is the native ramp's 22 (B14 rule 45 — the web's page head is
 * 32, deliberately not here). Back and menu are icon buttons and each NEEDS a
 * label: an unlabelled back arrow is a silent control.
 */
import type { ReactNode } from 'react';
import { View } from 'react-native';

import { useTheme } from '../theme';
import { AppText } from './AppText';
import { IconButton } from './Button';
import { Glyph } from './Glyph';

export interface TopBarProps {
  title: string;
  /** Present → a back button. */
  onBack?: () => void;
  /** Required with `onBack` ("Back to the job"). */
  backLabel?: string;
  /** Right-hand content: a counter, a sync chip, a scan button. */
  trailing?: ReactNode;
  /** testID of the back button (default `topbar-back`) — a screen names it
   *  after the door it is (`door-FF-44`), so the doors test can press it. */
  backTestID?: string;
  /** Present → the drawer button at the far LEFT, where FF-42, FF-44, FF-48
   *  and FF-49 draw it: the screens the menu opens, which have no back. */
  onOpenDrawer?: () => void;
  /** Required with `onOpenDrawer` ("Menu"). */
  drawerLabel?: string;
  drawerTestID?: string;
  /** Present → a menu button at the far right. */
  onMenu?: () => void;
  menuLabel?: string;
  /** The menu button's test id (default `topbar-menu`). */
  menuTestID?: string;
  testID?: string;
}

export function TopBar(props: TopBarProps) {
  const theme = useTheme();
  if (props.onBack && !props.backLabel) {
    throw new Error('TopBar: onBack needs a backLabel — an icon-only control must have a name');
  }
  if (props.onOpenDrawer && !props.drawerLabel) {
    throw new Error('TopBar: onOpenDrawer needs a drawerLabel — an icon-only control must have a name');
  }
  if (props.onMenu && !props.menuLabel) {
    throw new Error('TopBar: onMenu needs a menuLabel — an icon-only control must have a name');
  }
  return (
    <View
      testID={props.testID}
      style={{
        minHeight: theme.touch.primary,
        flexDirection: 'row',
        alignItems: 'center',
        gap: theme.space[1],
        paddingHorizontal: theme.space[2],
        backgroundColor: theme.colors.page,
        borderBottomWidth: theme.borderWidth.card,
        borderBottomColor: theme.colors.border,
      }}
    >
      {props.onOpenDrawer ? (
        <IconButton label={props.drawerLabel ?? ''} onPress={props.onOpenDrawer} testID={props.drawerTestID ?? 'topbar-drawer'}>
          <Glyph name="drawer" />
        </IconButton>
      ) : null}
      {props.onBack ? (
        <IconButton label={props.backLabel ?? ''} onPress={props.onBack} testID={props.backTestID ?? 'topbar-back'}>
          <Glyph name="back" />
        </IconButton>
      ) : null}
      <AppText variant="title" numberOfLines={1} style={{ flexGrow: 1, flexShrink: 1 }}>
        {props.title}
      </AppText>
      {props.trailing ?? null}
      {props.onMenu ? (
        <IconButton label={props.menuLabel ?? ''} onPress={props.onMenu} testID={props.menuTestID ?? 'topbar-menu'}>
          <Glyph name="menu" />
        </IconButton>
      ) : null}
    </View>
  );
}
