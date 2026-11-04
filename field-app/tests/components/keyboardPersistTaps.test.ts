/**
 * DEF-FLD-10611 (MQ-021): every scrolling container in the app declares
 * `keyboardShouldPersistTaps`, so a tap on Save with the keyboard open saves
 * instead of only closing the keyboard.
 *
 * React Native's default is `'never'`: with the keyboard up, a `ScrollView`
 * swallows the first tap on anything inside it. `JobScreen` and `ScreenFrame`
 * — the frames nearly every job screen sits in — were written without the
 * prop while `Page` and `TodayScreen` had it, and the technician had to press
 * Save twice on FF-20. Tests never opened a keyboard, so nothing noticed.
 *
 * This reads the SOURCE of every `.tsx` under `src/` and fails any
 * `<ScrollView>`, `<FlatList>`, `<SectionList>` (or `Animated.` / keyboard-
 * aware variant) whose opening tag does not set the prop to `"handled"` or
 * `"always"`. Every container, not only those holding a field today: a field
 * added to a screen later must not bring the bug back with it.
 *
 * It prints how many files and containers it read, so a moved folder reads as
 * "0" rather than as a pass (law 7).
 */
import { readdirSync, readFileSync, statSync } from 'fs';
import { join, relative, resolve } from 'path';

/** Comments out first, so a docstring may name a ScrollView (the same strip as `noLiterals`). */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');
}

const SRC = resolve(__dirname, '../../src');
const TAG = /<(?:Animated\.)?(?:ScrollView|FlatList|SectionList|KeyboardAwareScrollView|KeyboardAwareFlatList)\b/g;

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return walk(path);
    return /\.tsx$/.test(name) ? [path] : [];
  });
}

/** The opening tag from `start` to its closing `>` — braces and quotes skipped. */
function openingTag(code: string, start: number): string {
  let depth = 0;
  let quote: string | null = null;
  for (let i = start + 1; i < code.length; i++) {
    const ch = code.charAt(i);
    if (quote) {
      if (ch === quote && code[i - 1] !== '\\') quote = null;
    } else if (ch === '"' || ch === "'" || ch === '`') quote = ch;
    else if (ch === '{') depth++;
    else if (ch === '}') depth--;
    else if (ch === '>' && depth === 0) return code.slice(start, i + 1);
  }
  return code.slice(start);
}

const PERSISTS = /\bkeyboardShouldPersistTaps\s*=\s*(?:"(?:handled|always)"|\{\s*['"](?:handled|always)['"]\s*\})/;

/** Every scrolling container in the source that does NOT persist taps (its tag's first line). */
export function containersMissingPersistTaps(code: string): string[] {
  const missing: string[] = [];
  for (const m of code.matchAll(TAG)) {
    const tag = openingTag(code, m.index ?? 0);
    if (!PERSISTS.test(tag)) missing.push(tag.split('\n')[0] ?? tag);
  }
  return missing;
}

const files = walk(SRC);
const found = files.map((file) => {
  const code = stripComments(readFileSync(file, 'utf8'));
  return { file: relative(SRC, file), count: [...code.matchAll(TAG)].length, missing: containersMissingPersistTaps(code) };
});

test('the scan reads the whole app and finds the containers', () => {
  const containers = found.reduce((n, f) => n + f.count, 0);
  console.log(`keyboardPersistTaps: ${files.length} files read, ${containers} scrolling containers`);
  expect(files.length).toBeGreaterThanOrEqual(100);
  expect(containers).toBeGreaterThanOrEqual(17);
});

test('the scan tells a missing prop from a present one', () => {
  expect(containersMissingPersistTaps('<ScrollView style={{ flex: 1 }}>x</ScrollView>')).toHaveLength(1);
  expect(containersMissingPersistTaps('<ScrollView keyboardShouldPersistTaps="never">x</ScrollView>')).toHaveLength(1);
  expect(containersMissingPersistTaps('<FlatList data={a} renderItem={({ item }) => <Row />} />')).toHaveLength(1);
  expect(containersMissingPersistTaps('<ScrollView\n  style={{ flex: 1 }}\n  keyboardShouldPersistTaps="handled"\n>')).toEqual([]);
  expect(containersMissingPersistTaps("<FlatList keyboardShouldPersistTaps={'always'} data={a} />")).toEqual([]);
});

test('Android resizes the window for the keyboard, so the focused field and the footer stay above it', () => {
  const app = JSON.parse(readFileSync(resolve(__dirname, '../../app.json'), 'utf8')) as { expo: { android: Record<string, unknown> } };
  expect(app.expo.android.softwareKeyboardLayoutMode).toBe('resize');
});

test('every scrolling container lets a tap through while the keyboard is up', () => {
  const offenders = found.flatMap((f) => f.missing.map((tag) => `${f.file}: ${tag}`));
  expect(offenders).toEqual([]);
});
