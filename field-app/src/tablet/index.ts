/**
 * The tablet frame (Phase 12: T-27, and the frame half of T-28 and T-29).
 * See `TabletFrame.tsx` for the four frames, `geometry.ts` for R121/R122's
 * arithmetic, `frameMap.ts` for which screen sits in which, and
 * `layoutSlot.ts` for how a wave gives a screen its tablet shape.
 */
export { FormFactorProvider, useFormFactor } from './FormFactor';
export type { FormFactor } from './FormFactor';
export {
  CentredColumnFrame,
  ContextFrame,
  ListDetailFrame,
  PaneBody,
  TabletFrame,
  WidePaneFrame,
  usePaneWidth,
  useTabletSelection,
} from './TabletFrame';
export type { FrameSlots, PaneKind, PaneWidth, TabletSelection } from './TabletFrame';
export {
  CHECK_WIDTHS,
  FRAME_IDS,
  GEOMETRY,
  drawnFrame,
  findBrokenPanes,
  fitColumns,
  listPaneWidth,
  resolveFrame,
  singlePane,
} from './geometry';
export type { BrokenPane, FrameGeometry, FrameId } from './geometry';
export { FRAME_OF, SHAPE_CHANGING, contextFamilyOf } from './frameMap';
export type { ContextFamily } from './frameMap';
export { withTabletLayout, tabletLayoutOf } from './layoutSlot';
export type { PaneComponent, TabletLayout, WithTabletLayout } from './layoutSlot';
export { CONTEXT_PANES } from './contextPanes';
export { FRAMED_SCREENS, TabletScreen, framed } from './framedScreens';
