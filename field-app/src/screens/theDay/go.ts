/**
 * Opening a screen from inside a screen, by its design id, with params.
 *
 * `routing.routeTo` gives the full path from the root for an id; this adds
 * the screen's own params at the deepest level, so FF-14 opened from the
 * map, from Today or from Home arrives with the same `{ jobId }` wherever
 * the button that opened it sits.
 */
import { CommonActions, type NavigationProp, type ParamListBase } from '@react-navigation/native';

import { routeTo } from '../../navigation/routing';
import { type ScreenId } from '../../navigation/screens';

type Nested = { screen?: string; params?: Nested } & Record<string, unknown>;

function withLeafParams(params: Nested | undefined, leaf: object | undefined): Nested | undefined {
  if (!leaf) return params;
  if (!params) return leaf as Nested;
  if (params.params) return { ...params, params: withLeafParams(params.params, leaf) };
  return { ...params, params: leaf as Nested };
}

export function openScreen(navigation: Pick<NavigationProp<ParamListBase>, 'dispatch'>, id: ScreenId, params?: object): void {
  const target = routeTo(id);
  const nested = withLeafParams(target.params as Nested | undefined, params);
  navigation.dispatch(CommonActions.navigate(target.name, nested));
}
