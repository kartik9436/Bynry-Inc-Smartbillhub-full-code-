/**
 * Every component reads its colours and sizes from the theme and nothing else
 * (task T-07; Stack page: *"Nothing in a screen names a colour or a number
 * directly"*). This reads the SOURCE of every file in `src/components/` and
 * fails on:
 *   - a hex colour (`#e12e13`), an `rgb()`/`rgba()`/`hsl()` call, or a named
 *     colour string ('white', 'black', 'red' …);
 *   - a non-zero number written straight into a size property (`fontSize: 15`,
 *     `height: 48`, `padding: 14`, `borderRadius: 6` …).
 * Comments are stripped first, so a docstring may quote a figure.
 *
 * It prints how many files it read, so an empty folder or a moved path reads
 * as "0 files" rather than as a pass (law 7).
 */
import { readdirSync, readFileSync } from 'fs';
import { join, resolve } from 'path';

const DIR = resolve(__dirname, '../../src/components');

const SIZE_PROPS =
  'fontSize|lineHeight|letterSpacing|width|height|minHeight|minWidth|maxHeight|maxWidth|' +
  'padding\\w*|margin\\w*|gap|rowGap|columnGap|border\\w*Width|border\\w*Radius|top|bottom|left|right|flexBasis';

const RULES: Array<[string, RegExp]> = [
  ['hex colour', /#[0-9a-fA-F]{3,8}\b/g],
  ['colour function', /\b(?:rgba?|hsla?)\s*\(/g],
  ['named colour', /['"](?:white|black|red|green|blue|gray|grey|orange|yellow)['"]/gi],
  ['pixel literal', new RegExp(`\\b(?:${SIZE_PROPS})\\s*:\\s*-?(?:[1-9]\\d*(?:\\.\\d+)?|0?\\.\\d*[1-9]\\d*)\\b`, 'g')],
];

export function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');
}

export function findLiterals(src: string): string[] {
  const code = stripComments(src);
  const hits: string[] = [];
  for (const [kind, re] of RULES) {
    for (const m of code.matchAll(re)) hits.push(`${kind}: ${m[0]}`);
  }
  return hits;
}

const files = readdirSync(DIR).filter((f) => /\.(ts|tsx)$/.test(f));

/** Screen folders held to the same rule — one per wave that has built screens. */
const SCREEN_DIRS = ['me'].map((wave) => resolve(__dirname, '../../src/screens', wave));
const screenFiles = SCREEN_DIRS.flatMap((dir) =>
  readdirSync(dir)
    .filter((f) => /\.(ts|tsx)$/.test(f))
    .map((f) => join(dir, f)),
);

test('the scan reads the whole kit', () => {
  console.log(`noLiterals: ${files.length} files read in src/components`);
  expect(files.length).toBeGreaterThanOrEqual(12);
});

test.each(files)('%s names no colour and no pixel', (file) => {
  expect(findLiterals(readFileSync(join(DIR, file), 'utf8'))).toEqual([]);
});

test('the scan reads the screen folders too', () => {
  console.log(`noLiterals: ${screenFiles.length} files read in src/screens/{${SCREEN_DIRS.length} folders}`);
  expect(screenFiles.length).toBeGreaterThanOrEqual(15);
});

test.each(screenFiles)('%s names no colour and no pixel', (file) => {
  expect(findLiterals(readFileSync(file, 'utf8'))).toEqual([]);
});

describe('the scanner itself can fail (law 7)', () => {
  test.each([
    ["backgroundColor: '#e12e13'", 'hex colour'],
    ["color: 'rgba(0,0,0,0.4)'", 'colour function'],
    ["color: 'white'", 'named colour'],
    ['fontSize: 15', 'pixel literal'],
    ['height: 48', 'pixel literal'],
    ['paddingHorizontal: 14', 'pixel literal'],
    ['borderRadius: 6', 'pixel literal'],
    ['borderTopWidth: 0.5', 'pixel literal'],
  ])('flags %s', (src, kind) => {
    expect(findLiterals(`const s = { ${src} };`).join()).toContain(kind);
  });

  test.each(['borderWidth: 0', 'height: theme.touch.control', '// fontSize: 15', 'opacity: 0.8'])(
    'allows %s',
    (src) => {
      expect(findLiterals(`const s = { ${src} };`)).toEqual([]);
    },
  );
});
