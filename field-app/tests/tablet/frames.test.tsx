/**
 * The four frames, rendered — and R122's width check run against the RENDERED
 * tree rather than the arithmetic: at every check width the fixed pane's
 * style width is read off the mounted frame and the flexible sibling's width
 * is what the window leaves it. A frame component that ignored `geometry.ts`
 * and hard-wired its pane would pass the arithmetic test and fail here.
 *
 * Also: T2's list and detail share a selection; held upright it collapses to
 * one pane with a way back; panes report their measured width (R121); and
 * the frames render in light, dark and sunlight.
 */
import { fireEvent, render, screen } from '@testing-library/react-native';
import { type ReactNode } from 'react';
import { Pressable, StyleSheet, Text } from 'react-native';

import { ThemeProvider } from '../../src/theme';
import { FormFactorProvider } from '../../src/tablet/FormFactor';
import { CHECK_WIDTHS, findBrokenPanes, type FrameGeometry, type FrameId, GEOMETRY } from '../../src/tablet/geometry';
import {
  ContextFrame,
  ListDetailFrame,
  TabletFrame,
  usePaneWidth,
  useTabletSelection,
} from '../../src/tablet/TabletFrame';

const WIDTHS = [...CHECK_WIDTHS.landscape, ...CHECK_WIDTHS.portrait];
const heightFor = (w: number) => (w >= 1024 ? 768 : 1024);

function at(width: number, ui: ReactNode, mode: 'light' | 'dark' | 'sunlight' = 'light') {
  return render(
    <ThemeProvider initialMode={mode}>
      <FormFactorProvider tablet window={{ width, height: heightFor(width) }}>
        {ui}
      </FormFactorProvider>
    </ThemeProvider>,
  );
}

function PaneProbe({ name }: { name: string }) {
  const pane = usePaneWidth();
  return <Text testID={`probe-${name}`}>{`${pane.kind}:${pane.outer}:${pane.usable}`}</Text>;
}

function styleWidth(testID: string): number | undefined {
  const node = screen.queryByTestId(testID);
  if (!node) return undefined;
  return StyleSheet.flatten(node.props.style)?.width as number | undefined;
}

/** Measure what is mounted: sidebar + the fixed pane's rendered width → what the flexible pane is left. */
function measure(frame: FrameId, width: number): FrameGeometry {
  const fixedId = frame === 'T2' ? 'tablet-pane-list' : 'tablet-pane-context';
  const rendered = styleWidth(fixedId);
  const fixedShown = rendered !== undefined && screen.queryByTestId(frame === 'T2' ? 'tablet-pane-detail' : 'tablet-pane-content') != null;
  const fixedWidth = fixedShown ? (rendered as number) : 0;
  const flexibleOuter = width - GEOMETRY.sidebar - fixedWidth;
  return {
    frame,
    windowWidth: width,
    sidebar: GEOMETRY.sidebar,
    fixed: fixedShown ? { kind: frame === 'T2' ? 'list' : 'context', width: fixedWidth } : null,
    flexibleOuter,
    usable: flexibleOuter - 2 * GEOMETRY.gutter,
    collapsed: !fixedShown,
  };
}

describe('R122 against the rendered frames', () => {
  test('no mounted two-pane frame leaves its flexible pane under 260, at any check width', () => {
    const measured: FrameGeometry[] = [];
    for (const width of WIDTHS) {
      at(width, <ListDetailFrame backLabel="Today" list={<PaneProbe name="list" />} detail={<PaneProbe name="detail" />} />);
      measured.push(measure('T2', width));
      screen.unmount();
      at(width, <ContextFrame context={<PaneProbe name="context" />} content={<PaneProbe name="content" />} />);
      measured.push(measure('T3', width));
      screen.unmount();
    }
    console.log(
      `rendered R122 check: ${measured.length} frames measured — ` +
        measured.map((g) => `${g.frame}@${g.windowWidth}=${g.usable}${g.collapsed ? '(one pane)' : ''}`).join(', '),
    );
    expect(measured).toHaveLength(10);
    expect(findBrokenPanes(measured)).toEqual([]);
  });

  test('at the 1024 board the panes are drawn at their figures and report R122’s usable widths', () => {
    at(1024, <ListDetailFrame backLabel="Today" list={<PaneProbe name="list" />} detail={<PaneProbe name="detail" />} />);
    expect(styleWidth('tablet-pane-list')).toBe(340);
    expect(screen.getByTestId('probe-detail')).toHaveTextContent('detail:464:424');
    screen.unmount();
    at(1024, <ContextFrame context={<PaneProbe name="context" />} content={<PaneProbe name="content" />} />);
    expect(styleWidth('tablet-pane-context')).toBe(300);
    expect(screen.getByTestId('probe-content')).toHaveTextContent('content:504:464');
    screen.unmount();
    at(1024, <TabletFrame frame="T4" main={<PaneProbe name="wide" />} backLabel="x" />);
    expect(screen.getByTestId('probe-wide')).toHaveTextContent('wide:804:764');
  });

  test('T1 is a centred column, no wider than its figure', () => {
    at(1024, <TabletFrame frame="T1" main={<PaneProbe name="col" />} backLabel="x" />);
    expect(screen.getByTestId('tablet-frame-T1')).toBeTruthy();
    expect(styleWidth('tablet-pane-column')).toBe(GEOMETRY.centredColumn);
  });
});

function TodayList() {
  const sel = useTabletSelection();
  return (
    <Pressable accessibilityRole="button" testID="row-WO-1" onPress={() => sel.select('WO-1')}>
      <Text>{sel.split ? 'split' : 'single'}</Text>
    </Pressable>
  );
}

function JobDetail() {
  const sel = useTabletSelection();
  return <Text testID="detail-text">{sel.selected ?? 'nothing picked'}</Text>;
}

describe('T2: the list picks, the detail shows', () => {
  test('landscape: both on screen; picking a row fills the detail and the list stays', () => {
    at(1024, <ListDetailFrame backLabel="Today" list={<TodayList />} detail={<JobDetail />} />);
    expect(screen.getByTestId('detail-text')).toHaveTextContent('nothing picked');
    fireEvent.press(screen.getByTestId('row-WO-1'));
    expect(screen.getByTestId('detail-text')).toHaveTextContent('WO-1');
    expect(screen.getByTestId('row-WO-1')).toHaveTextContent('split');
  });

  test('upright: the list alone, then the detail with a labelled 48pt way back', () => {
    at(768, <ListDetailFrame backLabel="Today" list={<TodayList />} detail={<JobDetail />} />);
    expect(screen.queryByTestId('detail-text')).toBeNull();
    fireEvent.press(screen.getByTestId('row-WO-1'));
    expect(screen.queryByTestId('row-WO-1')).toBeNull();
    expect(screen.getByTestId('detail-text')).toHaveTextContent('WO-1');
    const back = screen.getByTestId('tablet-back-to-list');
    expect(back.props.accessibilityRole).toBe('button');
    expect(back.props.accessibilityLabel).toBe('Today');
    const style = StyleSheet.flatten(typeof back.props.style === 'function' ? back.props.style({ pressed: false }) : back.props.style);
    expect(style.height).toBeGreaterThanOrEqual(48);
    fireEvent.press(back);
    expect(screen.getByTestId('row-WO-1')).toBeTruthy();
  });

  test('outside a frame the selection says so, so a list knows to push instead', () => {
    render(<JobDetail />);
    expect(screen.getByTestId('detail-text')).toHaveTextContent('nothing picked');
    const Probe = () => <Text testID="in">{String(useTabletSelection().inFrame)}</Text>;
    render(<Probe />);
    expect(screen.getByTestId('in')).toHaveTextContent('false');
  });

  test('a two-pane frame whose fixed slot is empty shows one pane, never an empty column', () => {
    at(1024, <ListDetailFrame backLabel="Today" detail={<PaneProbe name="detail" />} />);
    expect(screen.queryByTestId('tablet-pane-list')).toBeNull();
    expect(screen.getByTestId('probe-detail')).toHaveTextContent('detail:804:764');
    screen.unmount();
    at(1024, <ContextFrame content={<PaneProbe name="content" />} />);
    expect(screen.queryByTestId('tablet-pane-context')).toBeNull();
  });
});

describe('the frames read the theme', () => {
  test.each(['light', 'dark', 'sunlight'] as const)('%s: the fixed pane’s border is the theme’s', (mode) => {
    at(1024, <ContextFrame context={<Text>c</Text>} content={<Text>x</Text>} />, mode);
    const style = StyleSheet.flatten(screen.getByTestId('tablet-pane-context').props.style);
    expect(style.borderRightWidth).toBe(mode === 'sunlight' ? 3 : 1);
    expect(typeof style.borderRightColor).toBe('string');
    expect(StyleSheet.flatten(screen.getByTestId('tablet-frame-T3').props.style).backgroundColor).toBeTruthy();
  });
});
