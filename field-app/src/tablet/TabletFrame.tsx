/**
 * The four tablet frames (T-27). A frame is the shape a screen sits in on a
 * tablet; the 220 px sidebar beside it is the shell's (`navigation/
 * MenuContent.tsx`, mounted as the permanent drawer), so a frame lays out
 * everything to the RIGHT of the sidebar and nothing else.
 *
 *   T1 CentredColumnFrame — before sign-in: one centred column, no sidebar.
 *   T2 ListDetailFrame    — a 320–360 list pane and a detail pane that keeps
 *                           the list visible (FF-10 T *Today beside the job*).
 *   T3 ContextFrame       — a ~300 job or route context pane and the content
 *                           (FF-15 T, FF-25 T, RW-09 T).
 *   T4 WidePaneFrame      — one wide pane (FF-63 T, FF-20 T).
 *
 * Every width comes from `geometry.ts` (R121, R122) and every colour and
 * border from the theme; nothing here is a literal. A frame draws no header
 * and no padding of its own — each board's pane header runs edge to edge — and
 * hands its panes their MEASURED width through `usePaneWidth()`, so content is
 * designed to the pane and never to the screen (R121). `PaneBody` applies the
 * gutter that the usable width already subtracts.
 *
 * When a two-pane frame cannot keep its flexible pane at 260 (a tablet held
 * upright) it shows ONE pane: T2 the list, or the detail once something is
 * picked, with a way back to the list; T3 the content without its context.
 */
import { createContext, type ReactNode, useContext, useMemo, useState } from 'react';
import { View } from 'react-native';

import { Glyph } from '../components/Glyph';
import { IconButton } from '../components/Button';
import { lightTheme, type Theme, useTheme } from '../theme';
import { useFormFactor } from './FormFactor';
import { type FrameGeometry, type FrameId, GEOMETRY, resolveFrame, singlePane } from './geometry';

/**
 * The theme, or light where no ThemeProvider is mounted yet. ⚠ `App.tsx` does
 * not mount one on this branch (reported); a frame must not take the whole
 * navigation tree down for that, so it falls back to the light theme. The
 * hook order is fixed — `useTheme` always runs — so the catch is safe.
 */
function useFrameTheme(): Theme {
  try {
    return useTheme();
  } catch {
    return lightTheme;
  }
}

// ── The pane a component sits in ─────────────────────────────────────────

export type PaneKind = 'column' | 'list' | 'context' | 'detail' | 'content' | 'wide' | 'phone';

export interface PaneWidth {
  kind: PaneKind;
  /** The pane's outer width. */
  outer: number;
  /** What content is designed to: the outer width less both gutters (R121). */
  usable: number;
  /** One gutter. `PaneBody` pads with it. */
  gutter: number;
}

const PaneContext = createContext<PaneWidth | null>(null);

/** The measured width of the pane this component is in (R121). On a phone, the window. */
export function usePaneWidth(): PaneWidth {
  const pane = useContext(PaneContext);
  const form = useFormFactor();
  if (pane) return pane;
  return { kind: 'phone', outer: form.width, usable: form.width - 2 * GEOMETRY.gutter, gutter: GEOMETRY.gutter };
}

function Pane(props: { kind: PaneKind; outer: number; children: ReactNode }) {
  const value = useMemo<PaneWidth>(
    () => ({
      kind: props.kind,
      outer: props.outer,
      usable: props.kind === 'column' ? props.outer : props.outer - 2 * GEOMETRY.gutter,
      gutter: GEOMETRY.gutter,
    }),
    [props.kind, props.outer],
  );
  return <PaneContext.Provider value={value}>{props.children}</PaneContext.Provider>;
}

/** A pane's body, padded by the gutter its usable width already allows for. */
export function PaneBody(props: { children: ReactNode; testID?: string }) {
  const pane = usePaneWidth();
  return <View style={{ flex: 1, paddingHorizontal: pane.gutter }} testID={props.testID}>{props.children}</View>;
}

// ── T2's selection: the list picks, the detail shows ─────────────────────

export interface TabletSelection {
  /** True inside a T2 frame on a tablet; false on a phone, where the list pushes the detail instead. */
  inFrame: boolean;
  /** True when list and detail are both on screen. */
  split: boolean;
  selected: string | null;
  /**
   * What the list handed over with the pick, when a door carries a record
   * rather than an id (FF-11's card opens FF-12 with the whole job, because
   * an unassigned job is the server's and is not on the handset to re-read).
   */
  payload: unknown;
  select: (id: string, payload?: unknown) => void;
  clear: () => void;
}

const NO_FRAME: TabletSelection = { inFrame: false, split: false, selected: null, payload: undefined, select: () => {}, clear: () => {} };

const SelectionContext = createContext<TabletSelection>(NO_FRAME);

/**
 * What a T2 list and its detail share. A list row calls `select(id)` when
 * `inFrame` (the detail appears beside it) and navigates when not (the phone
 * pushes the detail screen).
 */
export function useTabletSelection(): TabletSelection {
  return useContext(SelectionContext);
}

// ── The frames ────────────────────────────────────────────────────────────

function useGeometry(frame: FrameId, hasFixedPane: boolean): FrameGeometry {
  const { width } = useFormFactor();
  return hasFixedPane ? resolveFrame(frame, width) : singlePane(frame, width);
}

function frameTag(screenId: string | undefined): string | undefined {
  return screenId ? `frame-of-${screenId}` : undefined;
}

function frameRoot(theme: Theme) {
  return { flex: 1, flexDirection: 'row' as const, backgroundColor: theme.colors.page };
}

function fixedPaneStyle(theme: Theme, width: number) {
  return {
    width,
    borderRightWidth: theme.borderWidth.divider,
    borderRightColor: theme.colors.border,
    backgroundColor: theme.colors.page,
  };
}

/** T1 — a centred column, no sidebar: FF-01 … FF-08, FF-53, FF-56, FF-57. */
export function CentredColumnFrame(props: { children: ReactNode; screenId?: string }) {
  const theme = useFrameTheme();
  const g = useGeometry('T1', false);
  return (
    <View
      testID="tablet-frame-T1" nativeID={frameTag(props.screenId)}
      style={{ flex: 1, alignItems: 'center', backgroundColor: theme.colors.page }}
    >
      <View testID="tablet-pane-column" style={{ flex: 1, width: g.flexibleOuter }}>
        <Pane kind="column" outer={g.flexibleOuter}>
          {props.children}
        </Pane>
      </View>
    </View>
  );
}

/** T4 — one wide pane beside the sidebar. */
export function WidePaneFrame(props: { children: ReactNode; screenId?: string }) {
  const theme = useFrameTheme();
  const g = useGeometry('T4', false);
  return (
    <View testID="tablet-frame-T4" nativeID={frameTag(props.screenId)} style={frameRoot(theme)}>
      <View testID="tablet-pane-wide" style={{ flex: 1 }}>
        <Pane kind="wide" outer={g.flexibleOuter}>
          {props.children}
        </Pane>
      </View>
    </View>
  );
}

/**
 * T2 — the list and, beside it, the detail of what is picked. `list` absent →
 * the detail takes the whole width (its slot not filled yet). `backLabel`
 * names the way back to the list when the frame has collapsed to one pane —
 * the list screen's own title, so it needs no word of its own.
 */
export function ListDetailFrame(props: {
  list?: ReactNode;
  detail: ReactNode;
  backLabel: string;
  initialSelected?: string | null;
  screenId?: string;
}) {
  const theme = useFrameTheme();
  const hasList = props.list != null;
  const g = useGeometry('T2', hasList);
  const [pick, setPick] = useState<{ id: string; payload?: unknown } | null>(
    props.initialSelected ? { id: props.initialSelected } : null,
  );
  const selected = pick?.id ?? null;
  const split = g.fixed != null;
  const selection = useMemo<TabletSelection>(
    () => ({
      inFrame: true,
      split,
      selected,
      payload: pick?.payload,
      select: (id: string, payload?: unknown) => setPick({ id, payload }),
      clear: () => setPick(null),
    }),
    [split, selected, pick],
  );

  let body: ReactNode;
  if (split && g.fixed) {
    body = (
      <>
        <View testID="tablet-pane-list" style={fixedPaneStyle(theme, g.fixed.width)}>
          <Pane kind="list" outer={g.fixed.width}>
            {props.list}
          </Pane>
        </View>
        <View testID="tablet-pane-detail" style={{ flex: 1 }}>
          <Pane kind="detail" outer={g.flexibleOuter}>
            {props.detail}
          </Pane>
        </View>
      </>
    );
  } else if (hasList && selected == null) {
    body = (
      <View testID="tablet-pane-list" style={{ flex: 1 }}>
        <Pane kind="list" outer={g.flexibleOuter}>
          {props.list}
        </Pane>
      </View>
    );
  } else {
    body = (
      <View testID="tablet-pane-detail" style={{ flex: 1 }}>
        {hasList ? (
          <View style={{ flexDirection: 'row', paddingHorizontal: theme.space[2] }}>
            <IconButton label={props.backLabel} onPress={() => setPick(null)} testID="tablet-back-to-list">
              <Glyph name="back" colour={theme.colors.text} />
            </IconButton>
          </View>
        ) : null}
        <Pane kind="detail" outer={g.flexibleOuter}>
          {props.detail}
        </Pane>
      </View>
    );
  }

  return (
    <SelectionContext.Provider value={selection}>
      <View testID="tablet-frame-T2" nativeID={frameTag(props.screenId)} style={frameRoot(theme)}>
        {body}
      </View>
    </SelectionContext.Provider>
  );
}

/** T3 — the job's (or route's) context beside the content. `context` absent → the content alone. */
export function ContextFrame(props: { context?: ReactNode; content: ReactNode; screenId?: string }) {
  const theme = useFrameTheme();
  const g = useGeometry('T3', props.context != null);
  return (
    <View testID="tablet-frame-T3" nativeID={frameTag(props.screenId)} style={frameRoot(theme)}>
      {g.fixed ? (
        <View testID="tablet-pane-context" style={fixedPaneStyle(theme, g.fixed.width)}>
          <Pane kind="context" outer={g.fixed.width}>
            {props.context}
          </Pane>
        </View>
      ) : null}
      <View testID="tablet-pane-content" style={{ flex: 1 }}>
        <Pane kind="content" outer={g.flexibleOuter}>
          {props.content}
        </Pane>
      </View>
    </View>
  );
}

/** The panes a frame can be handed. Which ones a frame reads depends on the frame. */
export interface FrameSlots {
  /** T1, T4 — and T2's detail / T3's content when no split slot is given. */
  main: ReactNode;
  /** T2's list pane. */
  list?: ReactNode;
  /** T3's context pane. */
  context?: ReactNode;
  /** T2's way back to the list when collapsed. */
  backLabel: string;
  /** The screen in the frame, stamped on the frame root as `nativeID="frame-of-<id>"` so a check can find it. */
  screenId?: string;
}

/** One entry point: the frame by its id. */
export function TabletFrame(props: FrameSlots & { frame: FrameId }) {
  switch (props.frame) {
    case 'T1':
      return <CentredColumnFrame screenId={props.screenId}>{props.main}</CentredColumnFrame>;
    case 'T2':
      return <ListDetailFrame list={props.list} detail={props.main} backLabel={props.backLabel} screenId={props.screenId} />;
    case 'T3':
      return <ContextFrame context={props.context} content={props.main} screenId={props.screenId} />;
    case 'T4':
      return <WidePaneFrame screenId={props.screenId}>{props.main}</WidePaneFrame>;
  }
}
