/**
 * The shared context panes of the T3 frame (T-29): ONE job pane and ONE route
 * pane, each drawn the same on every board of its family — the job boards
 * carry the work order, its steps, where, the customer, the clocks and *The
 * whole job* (FF-16 T, FF-22 T, FF-25 T, FF-33 T, FF-37 T); the reading
 * boards carry the route, its progress, where, *The walk* and *Progress*
 * (RW-09 T).
 *
 * Every T3 screen without a layout of its own gets its family's pane
 * (`framedScreens.tsx`); FF-15 Job draws its own (the job itself beside its
 * tasks) through its layout. `tests/tablet/screensInFrame.test.tsx` counts the
 * T3 screens still waiting on a pane — zero for both families now.
 */
import { type ContextFamily } from './frameMap';
import { JobContextPane } from './JobContextPane';
import { type PaneComponent } from './layoutSlot';
import { RouteContextPane } from './RouteContextPane';

export const CONTEXT_PANES: Partial<Record<ContextFamily, PaneComponent>> = {
  job: JobContextPane,
  route: RouteContextPane,
};
