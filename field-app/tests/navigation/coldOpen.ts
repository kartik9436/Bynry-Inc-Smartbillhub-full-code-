/**
 * Open a screen COLD — as a notification or a link does: it is the only
 * screen on its stack, so there is no history under it (DEF-FLD-10607).
 *
 * Since the PO's ruling of 2026-10-26 (*"A for back button"*) a back arrow
 * goes back through history and follows its DRAWN door only when there is
 * none. The doors tests press every drawn door, so they open each screen cold
 * first: that is the one state in which an arrow's drawn door is where it
 * goes. History itself is proved in `tests/screens/theJob/backHistory.test.tsx`
 * and `tests/proof/backAndResume.test.tsx`.
 *
 * A screen that is not pushed inside the frame (a tab, the gate, a root
 * sheet) has no back arrow and is left where it is.
 */
import { CommonActions, type NavigationContainerRefWithCurrent, type ParamListBase } from '@react-navigation/native';
import { act } from '@testing-library/react-native';

import { FRAME, SHELL } from '../../src/navigation/routing';
import { type ScreenId, screenDef } from '../../src/navigation/screens';

export async function coldOpen(
  ref: NavigationContainerRefWithCurrent<ParamListBase>,
  at: ScreenId,
  params?: Record<string, unknown>,
): Promise<void> {
  if (screenDef(at).tree !== 'frame') return;
  // Left out: the params the screen is already showing, when it is on top.
  const showing = ref.getCurrentRoute();
  if (params === undefined && showing?.name === at) params = showing.params as Record<string, unknown> | undefined;
  await act(async () => {
    ref.dispatch(
      CommonActions.reset({
        index: 0,
        routes: [{ name: FRAME, state: { index: 0, routes: [{ name: SHELL, state: { index: 0, routes: [{ name: at, params }] } }] } }],
      }),
    );
  });
}
