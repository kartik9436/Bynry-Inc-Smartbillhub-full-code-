/**
 * How a phone LIST screen becomes a T2 list pane without being rewritten
 * (T-28, T-29): on the phone a row OPENS the detail screen; beside its detail
 * the same row SELECTS, and the list stays where it is (AD-12, *"the list
 * sits beside its detail"*; FF-10 T *Today beside the job*).
 *
 *   `SelectOnOpen` — wraps the list. While both panes are on screen it hands
 *     the list a navigation object whose `dispatch` turns a door to the
 *     detail screen (`opens`) into `select(params[param])`. Every other door
 *     goes through untouched. A list screen therefore needs no tablet code at
 *     all: the door it already has IS the selection.
 *   `SelectedParam` — wraps the detail. It hands the detail screen a route
 *     whose `param` is the selected id, so the detail screen reads the pick
 *     exactly as it reads the param a phone door carries. Nothing picked → the
 *     route's own param, unchanged.
 *   `useDefaultSelection(id)` — the boards draw the first item picked
 *     (FF-10 T, FF-13 T, FF-35 T); a detail pane calls this with the item it
 *     falls back to, so the list marks the same one.
 *
 * Outside a split T2 frame (a phone, a tablet held upright) all three are
 * no-ops: the list's door opens the detail screen as it always did.
 */
import {
  type NavigationAction,
  NavigationContext,
  type NavigationProp,
  NavigationRouteContext,
  type ParamListBase,
  useNavigation,
  useRoute,
} from '@react-navigation/native';
import { type ReactNode, useEffect, useMemo } from 'react';

import { type ScreenId } from '../navigation/screens';
import { useTabletSelection } from './TabletFrame';

type Params = Record<string, unknown> & { screen?: string; params?: Params };

/** The screen a navigate action lands on, and the params it carries there — however deeply nested. */
export function leafOf(action: NavigationAction): { name: string; params: Record<string, unknown> } | null {
  if (action.type !== 'NAVIGATE' || !action.payload) return null;
  const payload = action.payload as { name?: string; params?: Params };
  if (!payload.name) return null;
  let name = payload.name;
  let params: Params | undefined = payload.params;
  while (params && typeof params.screen === 'string') {
    name = params.screen;
    params = params.params;
  }
  return { name, params: (params ?? {}) as Record<string, unknown> };
}

/**
 * The list half: a door to `opens` carrying `param` becomes a selection while
 * the detail is beside it. With no `param` the door itself is the selection
 * (FF-42's emergency card opens FF-43, which names no record): the pick is the
 * screen id.
 */
export function SelectOnOpen(props: { opens: ScreenId; param?: string; children: ReactNode }) {
  const navigation = useNavigation<NavigationProp<ParamListBase>>();
  const sel = useTabletSelection();
  const { opens, param } = props;
  const active = sel.inFrame && sel.split;
  const select = sel.select;
  const wrapped = useMemo(() => {
    if (!active) return null;
    const proxy = Object.create(navigation) as NavigationProp<ParamListBase>;
    proxy.dispatch = ((action: NavigationAction) => {
      const leaf = leafOf(action);
      const value = leaf && leaf.name === opens ? (param ? leaf.params[param] : opens) : undefined;
      if (typeof value === 'string' && value) {
        select(value);
        return;
      }
      // A door that carries a record (FF-11 → FF-12 hands over the job): its
      // `id` is the pick and the record rides with it.
      const recordId = value && typeof value === 'object' ? (value as { id?: unknown }).id : undefined;
      if (typeof recordId === 'string' && recordId) {
        select(recordId, value);
        return;
      }
      navigation.dispatch(action);
    }) as NavigationProp<ParamListBase>['dispatch'];
    return proxy;
  }, [active, navigation, opens, param, select]);
  if (!wrapped) return <>{props.children}</>;
  return <NavigationContext.Provider value={wrapped}>{props.children}</NavigationContext.Provider>;
}

/** The detail half: the selected id, handed to the detail screen as its route param. */
export function SelectedParam(props: { param: string; children: ReactNode }) {
  const route = useRoute();
  const sel = useTabletSelection();
  const { param } = props;
  const picked = sel.inFrame && sel.split ? sel.selected : null;
  const payload = sel.inFrame && sel.split ? sel.payload : undefined;
  const value = useMemo(
    () =>
      picked ? { ...route, params: { ...((route.params ?? {}) as object), [param]: payload !== undefined ? payload : picked } } : route,
    [route, picked, payload, param],
  );
  return <NavigationRouteContext.Provider value={value}>{props.children}</NavigationRouteContext.Provider>;
}

/** Mark `id` picked when nothing is — the item a detail pane shows by default (with its record, where the door carries one). */
export function useDefaultSelection(id: string | null | undefined, payload?: unknown): void {
  const sel = useTabletSelection();
  const { inFrame, split, selected, select } = sel;
  useEffect(() => {
    if (inFrame && split && selected == null && id) select(id, payload);
  }, [inFrame, split, selected, select, id, payload]);
}

/**
 * A list row beside its detail (T-29): `active` while both panes are on
 * screen, `isPicked(id)` to rule the picked row heavy, `pick(id)` to show it.
 * A row whose phone press does something else (opens a paper, starts a clock)
 * asks `active` first and picks instead — the detail beside it carries that
 * act. Outside a split frame `active` is false and the row is the phone's.
 */
export function usePick(): {
  active: boolean;
  selected: string | null;
  payload: unknown;
  isPicked: (id: string) => boolean;
  pick: (id: string, payload?: unknown) => void;
} {
  const sel = useTabletSelection();
  const active = sel.inFrame && sel.split;
  const selected = active ? sel.selected : null;
  return {
    active,
    selected,
    payload: active ? sel.payload : undefined,
    isPicked: (id: string) => active && selected === id,
    pick: (id: string, payload?: unknown) => sel.select(id, payload),
  };
}

/** The picked id inside a split frame, else the route's own `param`. */
export function useSelectedOr(param: string): string | null {
  const route = useRoute();
  const sel = useTabletSelection();
  if (sel.inFrame && sel.split && sel.selected) return sel.selected;
  const v = ((route.params ?? {}) as Record<string, unknown>)[param];
  return typeof v === 'string' && v ? v : null;
}
