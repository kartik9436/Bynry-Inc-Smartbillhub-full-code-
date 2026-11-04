/**
 * The drift test for the shared token module (CR-187-BRC10, task T-06).
 *
 * Decision log 2026-10-21, "twelve conflicts", #2: *"A shared tokens.ts becomes
 * the one source; until the web reads it, a test fails when its values drift
 * from tokens.css."* This is that test. It reads `07-frontend/src/styles/
 * tokens.css` from disk, so it measures the web as it is, not a copy of it.
 *
 * Three assertions, because each closes a different false pass:
 *   1. every value `shared/tokens.ts` claims to mirror equals the CSS;
 *   2. every variable it claims to mirror EXISTS in the CSS (a renamed
 *      variable must not turn a check into silence);
 *   3. every CSS variable is either mirrored or named below as deliberately
 *      not mirrored — so a variable added to the web later fails here until
 *      somebody decides which it is. The count of each is printed (law 7: a
 *      blind spot with no number beside it reads as an empty one).
 */
import { readFileSync } from 'fs';
import { resolve } from 'path';

import { WEB_CSS_MIRROR, WEB_TAILWIND_MIRROR } from '../../../shared/tokens';

const TOKENS_CSS = resolve(__dirname, '../../../07-frontend/src/styles/tokens.css');
const TAILWIND_CSS = resolve(__dirname, '../../../07-frontend/src/styles/tailwind.css');

/** CSS variables in tokens.css the shared module does NOT mirror, and why. */
const NOT_MIRRORED: Record<string, string> = {
  '--color-divider': 'a color-mix() expression; native draws dividers from neutral tokens',
  '--shadow-sm': 'a CSS box-shadow; React Native elevation is a different model',
  '--shadow-md': 'a CSS box-shadow; React Native elevation is a different model',
  '--shadow-lg': 'a CSS box-shadow; React Native elevation is a different model',
  '--desc-measure': 'a percentage of a web content column (B14 rule 18); no native meaning',
  '--color-on-accent': 'the web ink on an accent fill, set per frame by the web portal (Group A ruling 3(a), decision 7); native has no brand-filled surface',
  '--color-on-accent-600': 'the web ink on an accent fill, set per frame by the web portal (Group A ruling 3(a), decision 7); native has no brand-filled surface',
  '--color-on-accent-700': 'the web ink on an accent fill, set per frame by the web portal (Group A ruling 3(a), decision 7); native has no brand-filled surface',
  '--color-accent-text': 'a var() reference set per frame by the web portal (Group A decision 2); native has no tenant colour',
};

function normalise(value: string): string {
  return value.replace(/\s+/g, ' ').trim().toLowerCase();
}

/** The `:root` declarations of tokens.css, comments removed. */
function readCssVariables(): Map<string, string> {
  const css = readFileSync(TOKENS_CSS, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
  const root = /:root\s*\{([\s\S]*?)\}/.exec(css);
  if (root === null || root[1] === undefined) {
    throw new Error(`no :root block in ${TOKENS_CSS}`);
  }
  const vars = new Map<string, string>();
  for (const m of root[1].matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/gi)) {
    if (m[1] !== undefined && m[2] !== undefined) vars.set(m[1], normalise(m[2]));
  }
  return vars;
}

const cssVars = readCssVariables();

/** The `@theme` declarations of tailwind.css, for the few keys only it holds. */
function readTailwindTheme(): Map<string, string> {
  const css = readFileSync(TAILWIND_CSS, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
  const block = /@theme\s*\{([\s\S]*?)\n\}/.exec(css);
  if (block === null || block[1] === undefined) {
    throw new Error(`no @theme block in ${TAILWIND_CSS}`);
  }
  const vars = new Map<string, string>();
  for (const m of block[1].matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/gi)) {
    if (m[1] !== undefined && m[2] !== undefined) vars.set(m[1], normalise(m[2]));
  }
  return vars;
}

const twVars = readTailwindTheme();

describe('shared/tokens.ts mirrors 07-frontend/src/styles/tokens.css', () => {
  test('tokens.css was read and is not empty', () => {
    expect(cssVars.size).toBeGreaterThan(50);
  });

  test.each(WEB_CSS_MIRROR.map(([name, value]) => [name, value]))(
    '%s matches the web',
    (name, value) => {
      expect(cssVars.has(name)).toBe(true);
      expect(normalise(value)).toBe(cssVars.get(name));
    },
  );

  test('every CSS variable is either mirrored or deliberately not mirrored', () => {
    const mirrored = new Set(WEB_CSS_MIRROR.map(([name]) => name));
    const unaccounted = [...cssVars.keys()].filter(
      (name) => !mirrored.has(name) && !(name in NOT_MIRRORED),
    );
    // Printed so a reader sees the scope, not only the verdict.
    console.log(
      `tokens.css: ${cssVars.size} variables · ${mirrored.size} mirrored · ` +
        `${Object.keys(NOT_MIRRORED).length} deliberately not mirrored · ${unaccounted.length} unaccounted`,
    );
    expect(unaccounted).toEqual([]);
  });

  test.each(WEB_TAILWIND_MIRROR.map(([name, value]) => [name, value]))(
    '%s matches tailwind.css @theme',
    (name, value) => {
      expect(twVars.has(name)).toBe(true);
      expect(normalise(value)).toBe(twVars.get(name));
    },
  );

  test('nothing is listed as both mirrored and not mirrored, and no stale exclusions', () => {
    const mirrored = new Set(WEB_CSS_MIRROR.map(([name]) => name));
    for (const name of Object.keys(NOT_MIRRORED)) {
      expect(mirrored.has(name)).toBe(false);
      expect(cssVars.has(name)).toBe(true);
    }
    expect(mirrored.size).toBe(WEB_CSS_MIRROR.length);
  });
});
