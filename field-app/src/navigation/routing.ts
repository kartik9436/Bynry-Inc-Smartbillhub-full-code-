/**
 * How to reach a screen from anywhere: one address per screen id.
 *
 * The signed-in app is nested — the root stack holds the Frame (the drawer)
 * and the screens that sit outside it; the Frame holds the Shell stack; the
 * Shell holds the bottom Tabs and every pushed screen. A door names a screen
 * id and `routeTo` turns it into the full path from the root, so a door works
 * the same from a tab, from a pushed screen and from a sheet.
 */
import { CommonActions, DrawerActions, type NavigationAction } from '@react-navigation/native';

import { type DoorKind } from './doors';
import { type ScreenId, screenDef } from './screens';

export const FRAME = 'Frame';
export const SHELL = 'Shell';
export const TABS = 'Tabs';

export interface RouteTarget {
  name: string;
  params?: object;
}

export function routeTo(id: ScreenId): RouteTarget {
  const tree = screenDef(id).tree;
  // `pop: true` on the Shell stack's step (DEF-FLD-10607): a door to a screen
  // ALREADY on the stack pops back to it instead of pushing a second copy.
  // React Navigation 7's `navigate` pushes a duplicate otherwise, and now that
  // the back arrow follows history (`back.tsx`) a duplicate is a loop: FF-17's
  // door to FF-15 would leave FF-15 → FF-17 → FF-15 to walk back through. The
  // tabs are one route on that stack, so a door to Today from deep in a job
  // pops to the SAME Today rather than mounting a second one.
  if (tree === 'tab') {
    return { name: FRAME, params: { screen: SHELL, params: { screen: TABS, pop: true, params: { screen: id } } } };
  }
  if (tree === 'frame') {
    return { name: FRAME, params: { screen: SHELL, params: { screen: id, pop: true } } };
  }
  // gate, root: top level of whichever root stack is mounted.
  return { name: id };
}

/** What following a door does, given where it starts. */
export function doorKind(from: ScreenId, to: ScreenId): DoorKind {
  const fromGate = screenDef(from).tree === 'gate';
  const toTree = screenDef(to).tree;
  if (toTree === 'drawer') return 'opens-menu';
  if (fromGate && toTree !== 'gate') return 'signs-in';
  if (!fromGate && toTree === 'gate') return 'signs-out';
  return 'link';
}

/** The action a door dispatches. `null` for the two that are an act, not a link. */
export function doorAction(from: ScreenId, to: ScreenId): NavigationAction | null {
  const kind = doorKind(from, to);
  if (kind === 'opens-menu') return DrawerActions.openDrawer();
  if (kind !== 'link') return null;
  const target = routeTo(to);
  return CommonActions.navigate(target.name, target.params);
}

/** The deepest focused route name in a navigation state. */
export function focusedLeaf(state: unknown): string | null {
  let node = state as { index?: number; routes?: Array<{ name: string; state?: unknown }> } | undefined;
  let name: string | null = null;
  while (node && Array.isArray(node.routes) && node.routes.length > 0) {
    const route = node.routes[node.index ?? node.routes.length - 1];
    if (!route) break;
    name = route.name;
    node = route.state as typeof node;
  }
  return name;
}
