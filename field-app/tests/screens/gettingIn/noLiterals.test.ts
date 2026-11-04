/**
 * The screen folders of the waves gettingIn and theDay name no colour and no
 * pixel — the same rule `tests/components/noLiterals.test.ts` holds the kit
 * to (Stack page: *"Nothing in a screen names a colour or a number
 * directly"*), extended to these screens as the screen brief asks, and to the
 * navigation files whose stand-in `shellStyle.ts` this wave removed.
 *
 * The scanner is the kit test's, restated (importing a test file would run
 * its tests twice); the two are held equal by the proof cases below, which
 * are the kit test's own. It prints how many files it read (law 7).
 */
import { readdirSync, readFileSync } from 'fs';
import { join, resolve } from 'path';

const SRC = resolve(__dirname, '../../../src');
const DIRS = ['screens/gettingIn', 'screens/theDay', 'navigation'];

const SIZE_PROPS =
  'fontSize|lineHeight|letterSpacing|width|height|minHeight|minWidth|maxHeight|maxWidth|' +
  'padding\\w*|margin\\w*|gap|rowGap|columnGap|border\\w*Width|border\\w*Radius|top|bottom|left|right|flexBasis';

const RULES: Array<[string, RegExp]> = [
  ['hex colour', /#[0-9a-fA-F]{3,8}\b/g],
  ['colour function', /\b(?:rgba?|hsla?)\s*\(/g],
  ['named colour', /['"](?:white|black|red|green|blue|gray|grey|orange|yellow)['"]/gi],
  ['pixel literal', new RegExp(`\\b(?:${SIZE_PROPS})\\s*:\\s*-?(?:[1-9]\\d*(?:\\.\\d+)?|0?\\.\\d*[1-9]\\d*)\\b`, 'g')],
];

function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');
}

function findLiterals(src: string): string[] {
  const code = stripComments(src);
  const hits: string[] = [];
  for (const [kind, re] of RULES) for (const m of code.matchAll(re)) hits.push(`${kind}: ${m[0]}`);
  return hits;
}

const files = DIRS.flatMap((d) =>
  readdirSync(join(SRC, d))
    .filter((f) => /\.(ts|tsx)$/.test(f))
    .map((f) => `${d}/${f}`),
);

test('the scan reads every screen and navigation file', () => {
  // eslint-disable-next-line no-console
  console.log(`noLiterals (screens): ${files.length} files read in ${DIRS.join(', ')}`);
  expect(files.length).toBeGreaterThanOrEqual(35);
});

test.each(files)('%s names no colour and no pixel', (file) => {
  expect(findLiterals(readFileSync(join(SRC, file), 'utf8'))).toEqual([]);
});

describe('the scanner itself can fail (law 7)', () => {
  test.each([
    ["backgroundColor: '#e12e13'", 'hex colour'],
    ["color: 'white'", 'named colour'],
    ['fontSize: 15', 'pixel literal'],
    ['paddingHorizontal: 14', 'pixel literal'],
  ])('flags %s', (src, kind) => {
    expect(findLiterals(`const s = { ${src} };`).join()).toContain(kind);
  });
});
