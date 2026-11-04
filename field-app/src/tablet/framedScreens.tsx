/**
 * The hook-up (T-27): every screen the navigator mounts, wrapped so that on a
 * tablet it sits in its frame and on a phone it is exactly the screen it was.
 *
 * `AppNavigator` mounts `FRAMED_SCREENS[id]` where it used to mount
 * `SCREEN_COMPONENTS[id]`; nothing else in navigation changed. Each wrapper is
 * built ONCE, at module load, so a route's component identity is stable and
 * React Navigation never remounts a screen because its wrapper was re-created.
 */
import { NavigationContext } from '@react-navigation/native';
import { type ComponentType, useContext, useLayoutEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { SCREEN_IDS, type ScreenId, screenDef } from '../navigation/screens';
import { SCREEN_COMPONENTS } from '../screens/registry';
import { CONTEXT_PANES } from './contextPanes';
import { useFormFactor } from './FormFactor';
import { contextFamilyOf, FRAME_OF } from './frameMap';
import { resolveFrame } from './geometry';
import { assertLayoutFits, type PaneComponent, tabletLayoutOf } from './layoutSlot';
import { TabletFrame } from './TabletFrame';

/**
 * The stack's own header, hidden while a layout's panes are on screen (T-28).
 *
 * ⚠ A NAVIGATION CHANGE, AND THIS IS ALL OF IT: the boards draw each pane of
 * a shape-changing screen with its OWN header (FF-10 T *Today* over the list
 * and *WO-4822 · ON SITE* over the detail; FF-35 T, FF-39 T, FF-13 T the
 * same), so the stack's bar above both would be a third title nobody drew.
 * While a filled layout is mounted this sets `headerShown: false` on that
 * route; when the frame collapses to one pane (a tablet turned upright) it
 * puts the header back, but only if it was this code that hid it — a screen
 * that hides its own header (the job screens, the me screens) is never
 * touched. Screens without a layout keep the header exactly as on the phone.
 * (The status strip above the stack is the other half: `AppNavigator` does
 * not draw it on a tablet, where the sidebar carries both of its figures.)
 */
function useOwnPaneHeaders(active: boolean): void {
  const navigation = useContext(NavigationContext);
  const hid = useRef(false);
  useLayoutEffect(() => {
    if (!navigation) return;
    if (active) {
      navigation.setOptions({ headerShown: false });
      hid.current = true;
    } else if (hid.current) {
      navigation.setOptions({ headerShown: true });
      hid.current = false;
    }
  }, [navigation, active]);
}

/**
 * The tablet rendering of one screen: its layout's panes, or its phone screen
 * in the main pane.
 *
 * A T2 or T3 layout that cannot keep its flexible pane at 260 at this width
 * (R122 — a tablet held upright) is NOT mounted: the phone screen is, alone,
 * so the list opens its detail by pushing it exactly as on a phone, rather
 * than a list pane squeezed or a detail with no list to return to.
 */
export function TabletScreen(props: { id: ScreenId; screen: ComponentType<object>; screenProps: object }) {
  const { t } = useTranslation();
  const { width } = useFormFactor();
  const { id, screenProps } = props;
  const frame = FRAME_OF[id];
  const filled = tabletLayoutOf(props.screen);
  if (filled) assertLayoutFits(id, frame, filled);
  const twoPane = filled?.frame === 'T2' || (filled?.frame === 'T3' && filled.context != null);
  const layout = filled && twoPane && resolveFrame(frame, width).collapsed ? null : filled;
  useOwnPaneHeaders(layout != null && layout.frame !== 'T1' && !(layout.frame === 'T2' && layout.sharedHeader));

  const render = (C: PaneComponent | undefined) => (C ? <C {...screenProps} /> : undefined);
  const Phone = props.screen;
  let main = <Phone {...screenProps} />;
  let list;
  let context;
  if (layout?.frame === 'T1') main = <layout.column {...screenProps} />;
  if (layout?.frame === 'T4') main = <layout.pane {...screenProps} />;
  if (layout?.frame === 'T2') {
    main = <layout.detail {...screenProps} />;
    list = render(layout.list);
  }
  if (layout?.frame === 'T3') main = <layout.content {...screenProps} />;
  if (frame === 'T3') {
    const fromLayout = layout?.frame === 'T3' ? layout.context : undefined;
    context = render(fromLayout ?? CONTEXT_PANES[contextFamilyOf(id)]);
  }

  return (
    <TabletFrame
      frame={frame}
      main={main}
      list={list}
      context={context}
      backLabel={t(screenDef(id).titleKey)}
      screenId={id}
    />
  );
}

export function framed(id: ScreenId, screen: ComponentType<object>): ComponentType<object> {
  function Framed(props: object) {
    const { tablet } = useFormFactor();
    if (!tablet) {
      const Screen = screen;
      return <Screen {...props} />;
    }
    return <TabletScreen id={id} screen={screen} screenProps={props} />;
  }
  Framed.displayName = `Framed(${id})`;
  return Framed;
}

/** Every screen id → its framed component. What the navigator mounts. */
export const FRAMED_SCREENS: Readonly<Record<ScreenId, ComponentType<object>>> = Object.fromEntries(
  SCREEN_IDS.map((id) => [id, framed(id, SCREEN_COMPONENTS[id] as ComponentType<object>)]),
) as Record<ScreenId, ComponentType<object>>;
