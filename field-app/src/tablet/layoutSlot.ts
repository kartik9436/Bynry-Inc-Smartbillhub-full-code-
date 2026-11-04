/**
 * The `tabletLayout` slot (T-28): how a screen that genuinely changes shape at
 * width tells its frame what goes in each pane.
 *
 * A wave fills it where it registers the screen, in its own group file, and
 * touches nothing here:
 *
 *   // src/screens/groups/theDay.ts
 *   'FF-10': withTabletLayout(TodayScreen, { frame: 'T2', list: TodayList, detail: JobSummary }),
 *
 * The phone keeps mounting `TodayScreen` exactly as before; on a tablet the
 * frame mounts the panes instead. The `frame` field must be the screen's frame
 * in `frameMap.ts` — a layout drawn for another frame fails loudly at mount
 * rather than rendering in the wrong shape.
 *
 * A screen with NO layout still sits in its frame: its phone screen goes in
 * the frame's main pane (T2's detail, T3's content, T4's wide pane, T1's
 * column), and a T3 screen also gets its family's shared context pane once
 * that is registered (`contextPanes.ts`). A slot nobody fills is counted and
 * printed by `tests/tablet/screensInFrame.test.tsx`, so an empty one cannot
 * pass for a filled one (hard-won law 2).
 */
import { type ComponentType, createElement } from 'react';

import { type FrameId } from './geometry';

/** What a pane is handed: the screen's own navigation props, passed through. */
export type PaneComponent = ComponentType<object>;

export type TabletLayout =
  | { frame: 'T1'; column: PaneComponent }
  | {
      frame: 'T2';
      list: PaneComponent;
      detail: PaneComponent;
      /**
       * The board draws ONE title across both panes (*FF-47 T Timesheet*, and
       * the 25 T-29 boards like it) rather than a header per pane (FF-10 T):
       * the stack's own bar stays on screen over the pair.
       */
      sharedHeader?: boolean;
    }
  | { frame: 'T3'; content: PaneComponent; context?: PaneComponent }
  | { frame: 'T4'; pane: PaneComponent };

export type WithTabletLayout<C> = C & { tabletLayout: TabletLayout };

/** Attach a tablet layout to a screen component. Returns the same component, marked. */
export function withTabletLayout<C extends ComponentType<object>>(screen: C, layout: TabletLayout): WithTabletLayout<C> {
  const marked = screen as WithTabletLayout<C>;
  marked.tabletLayout = layout;
  return marked;
}

/**
 * A T-29 board (T2, one title across both panes): the phone screen as it
 * always was, marked with its list and detail. The mark goes on a FRESH
 * component, so the phone screen itself — which the list pane may mount too —
 * is never marked.
 */
export function listBesideDetail(
  screen: ComponentType<object>,
  list: PaneComponent,
  detail: PaneComponent,
): WithTabletLayout<ComponentType<object>> {
  function Phone(props: object) {
    return createElement(screen, props);
  }
  // The phone screen's own name: a check that the registry mounts the built
  // screen (not the placeholder) reads it.
  Phone.displayName = screen.displayName ?? screen.name;
  return withTabletLayout(Phone, { frame: 'T2', list, detail, sharedHeader: true });
}

export function tabletLayoutOf(screen: unknown): TabletLayout | null {
  if (screen == null) return null;
  const layout = (screen as { tabletLayout?: TabletLayout }).tabletLayout;
  return layout ?? null;
}

export function assertLayoutFits(id: string, expected: FrameId, layout: TabletLayout): void {
  if (layout.frame !== expected) {
    throw new Error(
      `tabletLayout for ${id} is drawn for ${layout.frame}, but ${id} sits in ${expected} (src/tablet/frameMap.ts)`,
    );
  }
}
