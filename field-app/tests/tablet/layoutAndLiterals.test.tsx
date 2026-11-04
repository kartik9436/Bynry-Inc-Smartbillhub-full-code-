/**
 * The `tabletLayout` slot, filled — and the no-literals rule extended to
 * `src/tablet/` (SCREENS-BRIEF: *"extend it to scan your screen folder too"*).
 *
 * The scanner's rules are `tests/components/noLiterals.test.ts`'s, restated:
 * importing that file would register its tests a second time inside this one.
 * They are proved able to fail on three frame-shaped lines below.
 */
import { readdirSync, readFileSync } from 'fs';
import { join, resolve } from 'path';

import { render, screen } from '@testing-library/react-native';
import { Text } from 'react-native';

import { ThemeProvider } from '../../src/theme';
import { FormFactorProvider } from '../../src/tablet/FormFactor';
import { TabletScreen } from '../../src/tablet/framedScreens';
import { tabletLayoutOf, withTabletLayout } from '../../src/tablet/layoutSlot';
import { usePaneWidth } from '../../src/tablet/TabletFrame';

function at(width: number, ui: React.ReactNode) {
  return render(
    <ThemeProvider initialMode="light">
      <FormFactorProvider tablet window={{ width, height: 768 }}>
        {ui}
      </FormFactorProvider>
    </ThemeProvider>,
  );
}

const Phone = () => <Text testID="phone-today">phone</Text>;
const List = () => <Text testID="pane-list">{`list ${usePaneWidth().outer}`}</Text>;
const Detail = () => <Text testID="pane-detail">{`detail ${usePaneWidth().usable}`}</Text>;

describe('the tabletLayout slot', () => {
  test('a filled T2 slot mounts its list and detail in the frame, not the phone screen', () => {
    const Today = withTabletLayout(Phone, { frame: 'T2', list: List, detail: Detail });
    expect(tabletLayoutOf(Today)?.frame).toBe('T2');
    at(1024, <TabletScreen id="FF-10" screen={Today} screenProps={{}} />);
    expect(screen.getByTestId('tablet-frame-T2')).toBeTruthy();
    expect(screen.getByTestId('pane-list')).toHaveTextContent('list 340');
    expect(screen.getByTestId('pane-detail')).toHaveTextContent('detail 424');
    expect(screen.queryByTestId('phone-today')).toBeNull();
  });

  test('with no slot, the phone screen sits in the frame’s main pane', () => {
    // A T4 screen: every T3 screen now carries its family's context pane,
    // which reads the route and so is exercised under the real navigator
    // (`contextPanes.test.tsx`), not bare.
    const Bare = () => <Text testID="phone-home">phone</Text>;
    at(1024, <TabletScreen id="FF-63" screen={Bare} screenProps={{}} />);
    expect(screen.getByTestId('tablet-frame-T4')).toBeTruthy();
    expect(screen.getByTestId('phone-home')).toBeTruthy();
  });

  test('a layout drawn for the wrong frame fails loudly, naming the screen', () => {
    const Wrong = withTabletLayout(() => <Text>x</Text>, { frame: 'T4', pane: Detail });
    jest.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => at(1024, <TabletScreen id="FF-10" screen={Wrong} screenProps={{}} />)).toThrow(
      /FF-10 is drawn for T4, but FF-10 sits in T2/,
    );
  });
});

const DIR = resolve(__dirname, '../../src/tablet');
const SIZE_PROPS =
  'fontSize|lineHeight|width|height|minHeight|minWidth|maxHeight|maxWidth|padding\\w*|margin\\w*|gap|border\\w*Width|border\\w*Radius|top|bottom|left|right|flexBasis';
const RULES: RegExp[] = [
  /#[0-9a-fA-F]{3,8}\b/g,
  /\b(?:rgba?|hsla?)\s*\(/g,
  /['"](?:white|black|red|green|blue|gray|grey|orange|yellow)['"]/gi,
  new RegExp(`\\b(?:${SIZE_PROPS})\\s*:\\s*-?(?:[1-9]\\d*(?:\\.\\d+)?|0?\\.\\d*[1-9]\\d*)\\b`, 'g'),
];
const strip = (src: string) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');
const literals = (src: string) => RULES.flatMap((re) => [...strip(src).matchAll(re)].map((m) => m[0]));

// Recursive: the T-28 layouts live in `src/tablet/layouts/` (T-28), and a
// scan that stopped at the top folder would pass over them in silence.
function walk(dir: string, prefix = ''): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(join(dir, e.name), `${prefix}${e.name}/`) : /\.(ts|tsx)$/.test(e.name) ? [`${prefix}${e.name}`] : [],
  );
}
const files = walk(DIR);

test('the scan reads the whole tablet folder', () => {
  console.log(`tablet noLiterals: ${files.length} files read in src/tablet`);
  expect(files.length).toBeGreaterThanOrEqual(7);
  expect(files.filter((f) => f.startsWith('layouts/')).length).toBeGreaterThanOrEqual(7);
});

test.each(files)('src/tablet/%s names no colour and no pixel in a style', (file) => {
  expect(literals(readFileSync(join(DIR, file), 'utf8'))).toEqual([]);
});

test.each(['width: 340', "borderRightColor: '#d7d3d3'", 'paddingHorizontal: 20'])('the scan fails %s', (line) => {
  expect(literals(`const s = { ${line} };`)).not.toEqual([]);
});
